#!/usr/bin/env python3
"""Do the tabulated numbers come from the runs they claim? Provenance invariants, per cell.

    python scripts/verify_cells.py
    python scripts/verify_cells.py --strict     # exit 1 if any invariant fails

## Why this exists

`scripts/results_table.py` divides an `eval-easy` grid by a `train` grid and calls the ratio
retention. **That is only retention if both grids evaluated the same weights**, and nothing checked
it: the table reads `snapshot_md5` and prints it, which is not the same as verifying the two agree.
A cell whose two halves came from different checkpoints would produce a beautifully-formatted
number that means nothing, and every downstream instrument would carry it forward.

This project has already been bitten by the general shape twice —
[C54](../docs/CONSTRUCTION.md#c54) (checkpoints trained on pixels their config did not declare) and
[C69](../docs/CONSTRUCTION.md#c69) (two evaluations recording the same `seed` that were not the
same experiment). Both were found by comparing artifacts, not by reading code, and neither was
visible in the number.

## The invariants

Per cell, the `train` and `eval-easy` grids must agree on **everything except the regime**:

| # | invariant | what its failure would mean |
|---|---|---|
| 1 | identical `snapshot_md5` | the ratio compares two different policies |
| 2 | the snapshot file still hashes to that md5 | the checkpoint was replaced after measurement |
| 3 | `mode` differs, and is exactly the pair claimed | the regime manipulation did not happen ([C19](../docs/CONSTRUCTION.md#c19), and RL-ViGen's own runner measured `train` twice — PART2 Finding 7) |
| 4 | identical `episodes`, `seed`, `action_repeat`, `task` | the two halves were measured under different protocols |
| 5 | identical scene set | the numerator and denominator average different scenes |
| 6 | `placement_seeded` true on both | pre-[C69](../docs/CONSTRUCTION.md#c69) grid; not reproducible, not a controlled comparison |
| 7 | `trained_step` matches the cell's label | a `50k` row built from a 100k checkpoint, or the reverse |
| 8 | `control_seed` differs from `seed` | the seed-only control is not a control |

## The floor's provenance, since this file changed it

On its first run (2026-08-29) the only failure was the **random floor**: `placement_seeded` was
absent, while every cell recorded `True`. It was an unwritten field on the `--random-policy` branch
of `eval_across_scenes.py`, not a seeding failure — the two floor grids are byte-identical across
200 episodes in two different regimes, which is impossible without deterministic placement. The
field was added and the floor re-measured.

**The re-measurement is also a determinism result worth keeping**: 19 hours and two processes
apart, `random-floor__train` and `random-floor__eval-easy` came back **400/400 episodes
byte-identical, max |diff| exactly 0**. The v2 files were promoted to the canonical names and the
originals kept as `random-floor-v1-preserved__*.json`; no number in any table moved, because the
bytes are the same.

## What it does not do

It does not check that a number is *right* — only that it came from where it says. A cell can pass
every invariant here and still be a bad measurement for reasons this file cannot see: one seed,
a budget below the learning threshold, a denominator at chance. Those are the retention report's
job and the table's, and this is the layer beneath both.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
GRIDS = ROOT / "results" / "regime-retention-c69"

#: Taken from the table itself, so the two cannot drift: whatever is tabulated is what is verified.
_spec = importlib.util.spec_from_file_location("_rt", ROOT / "scripts" / "results_table.py")
_rt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_rt)

EXPECTED_STEP = {"50k": 50000, "100k": 100000}


def check(name: str, seed: int, budget: str, tag: str) -> list[str]:
    bad = []
    paths = {m: GRIDS / f"{tag}__{m}.json" for m in ("train", "eval-easy")}
    if not all(p.exists() for p in paths.values()):
        return [f"{tag}: missing grid(s): "
                f"{[m for m, p in paths.items() if not p.exists()]}"]
    g = {m: json.loads(p.read_text()) for m, p in paths.items()}
    tr, ev = g["train"], g["eval-easy"]

    # 1 -- the same weights on both sides of the ratio
    if tr.get("snapshot_md5") != ev.get("snapshot_md5"):
        bad.append(f"{tag}: snapshot_md5 DIFFERS between regimes "
                   f"({tr.get('snapshot_md5','?')[:8]} vs {ev.get('snapshot_md5','?')[:8]}) -- "
                   "the ratio compares two different policies, not one policy in two regimes")

    # 2 -- and those weights are still the ones on disk
    snap = tr.get("snapshot")
    if snap:
        f = pathlib.Path(snap)
        if not f.is_absolute():
            f = ROOT / snap
        if f.exists():
            h = hashlib.md5(f.read_bytes()).hexdigest()
            if h != tr.get("snapshot_md5"):
                bad.append(f"{tag}: the checkpoint on disk no longer hashes to the md5 recorded "
                           f"at measurement ({h[:8]} vs {tr.get('snapshot_md5','?')[:8]})")
        else:
            bad.append(f"{tag}: NOTE the measured checkpoint is no longer on disk ({snap[-48:]}) "
                       "-- the grid stands, but it can no longer be re-measured")

    # 3 -- the regime actually differed
    if tr.get("mode") != "train" or ev.get("mode") != "eval-easy":
        bad.append(f"{tag}: modes are {tr.get('mode')!r}/{ev.get('mode')!r}, not train/eval-easy -- "
                   "RL-ViGen's own runner measured the training distribution twice (PART2 Finding 7)")

    # 4 -- same protocol on both sides
    for k in ("episodes", "seed", "action_repeat", "task"):
        if tr.get(k) != ev.get(k):
            bad.append(f"{tag}: {k} differs between regimes ({tr.get(k)!r} vs {ev.get(k)!r})")

    # 5 -- same scenes
    if set(tr["scenes"]) != set(ev["scenes"]):
        bad.append(f"{tag}: scene sets differ -- numerator and denominator average different scenes")

    # 6 -- post-C69 determinism
    for m, d in g.items():
        if not d.get("placement_seeded"):
            bad.append(f"{tag}/{m}: placement_seeded is not true -- a pre-C69 grid, where two "
                       "evaluations recording the same seed were not the same experiment")

    # 7 -- the budget label is the checkpoint's own
    want = EXPECTED_STEP.get(budget)
    if want is not None and tr.get("trained_step") != want:
        bad.append(f"{tag}: labelled {budget} but trained_step is {tr.get('trained_step')!r}")

    # 8 -- the control is a control
    for m, d in g.items():
        if d.get("control_seed") == d.get("seed"):
            bad.append(f"{tag}/{m}: control_seed equals seed -- the seed-only control re-measures "
                       "the same draw and its 'resolution floor' is meaningless")
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args(argv)

    print("CELL PROVENANCE — do the tabulated numbers come from the runs they claim?\n")
    print("  Verified per cell: same weights on both sides of the ratio, the regime actually")
    print("  differed, same protocol, same scenes, post-C69 seeding, the budget label is the")
    print("  checkpoint's own, and the control is a genuine control.\n")

    total = 0
    for name, seed, budget, tag in _rt.CELLS:
        bad = check(name, seed, budget, tag)
        real = [b for b in bad if "NOTE" not in b]
        mark = "ok " if not real else "FAIL"
        print(f"  [{mark}] {name:<6} seed {seed} @{budget:<5} {tag}")
        for b in bad:
            print(f"         {b}")
        total += len(real)

    # The floor is a denominator for every row, so it is verified too.
    fl = GRIDS / "random-floor__train.json"
    if fl.exists():
        d = json.loads(fl.read_text())
        note = "ok " if d.get("placement_seeded") else "FAIL"
        print(f"\n  [{note}] random-floor  episodes={d['episodes']} seed={d['seed']} "
              f"placement_seeded={d.get('placement_seeded')}")
        if not d.get("placement_seeded"):
            total += 1
    else:
        print("\n  [FAIL] no random floor measured -- every row's denominator is unchecked")
        total += 1

    print(f"\n  {total} invariant failure(s).")
    print("  This checks PROVENANCE, not correctness: a cell can pass every line here and still")
    print("  be a poor measurement -- one seed, a budget below threshold, a denominator at")
    print("  chance. Those belong to the retention report and the table; this is the layer under")
    print("  both, and it is the one that was missing.")
    return 1 if (a.strict and total) else 0


if __name__ == "__main__":
    raise SystemExit(main())
