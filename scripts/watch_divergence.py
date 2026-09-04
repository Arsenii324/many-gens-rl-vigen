#!/usr/bin/env python3
"""Catch a NaN-diverged run from its LIVE log, in minutes. [C57](../docs/CONSTRUCTION.md#c57), C79.

    python scripts/watch_divergence.py --match num_train_frames=105000    # a whole batch
    python scripts/watch_divergence.py --run <exp_local run dir>          # one run, until it dies
    python scripts/watch_divergence.py --run <dir> --once                 # one check, exit 1 if dead

## Why this can exist now, and could not before

[C57](../docs/CONSTRUCTION.md#c57) found a `drqv2` run that diverged to NaN around frame 35 000,
trained 70 000 more frames, and wrote a snapshot of 7.4M NaNs. Its finding was that the divergence
was **invisible in every artifact this project kept**, and that was true of the artifacts it had:
across all eight `train.csv` files then in existence, none carried a loss or Q column. Their header
is `buffer_size,episode,episode_length,episode_reward,fps,frame,step,total_time` — episode
bookkeeping only. The only tell was indirect: episode return with **standard deviation 0.00**,
because NaN actions clip to the same constant and score identically where a bad policy would vary.

**`use_tb=True` changed that, and nobody noticed.** It was turned on 2026-08-20 partly *for* C57
detection, and it added `actor_loss`, `actor_logprob`, `critic_loss`, `critic_q1`, `critic_q2` and
`critic_target_q` to `train.csv`. Those columns go **literally `nan`** the moment the update
diverges. So the thing C57 called invisible now sits in a text file, in the clear, from the first
bad update — while this project still only checked *checkpoints*, after the run, with
`check_checkpoint_finite.py`.

The cost of not looking, measured on the run that prompted this: `drqv2` seed 7, 2026-08-26.
**First NaN at frame 7 000, 5.9 minutes in.** It was allowed to continue to frame 50 000 --
**64 minutes** -- and would have run another 1.2 hours to write a checkpoint of NaNs. A ten-fold
waste, and the evidence was in the log the whole time.

## What it will not do

**It does not kill anything.** It reports and exits non-zero, and the caller decides. A watcher
that terminated runs would be one bug away from killing a healthy one, and this file cannot know
whether a run is worth continuing for reasons outside the log.

**It refuses rather than guesses when the columns are absent.** `drq` cannot run with `use_tb=True`
at all — `algos/drq.py:328` calls `entropy()` on a `SquashedNormal`, which torch does not implement
— so a `drq` log has no loss columns and this instrument is **blind** to it. It says so, and exits
with a distinct code. Reporting "healthy" for a run it cannot see would be worse than not running:
it would convert an absence of evidence into a clean bill of health, which is the failure mode this
repository's own null names.
"""
from __future__ import annotations

import argparse
import csv
import math
import pathlib
import time

#: Columns whose value is a direct readout of the update. If any is NaN, the update diverged.
#: Episode bookkeeping (`episode_reward`, `fps`) is deliberately NOT here: it stays finite through
#: a divergence, which is precisely what made C57 hard to see.
LOSS_COLUMNS = ("actor_loss", "actor_logprob", "critic_loss",
                "critic_q1", "critic_q2", "critic_target_q")

OK, DEAD, BLIND = 0, 1, 2


def _rows(run: pathlib.Path) -> list[dict]:
    f = run / "train.csv"
    if not f.exists():
        return []
    with f.open(newline="", encoding="utf-8", errors="replace") as fh:
        return list(csv.DictReader(fh))


def inspect(run: pathlib.Path, tail: int = 5) -> tuple[int, str]:
    """(code, human-readable reason). Never raises on a malformed or half-written row."""
    rows = _rows(run)
    if not rows:
        return OK, "no train.csv yet"

    present = [c for c in LOSS_COLUMNS if c in rows[0]]
    if not present:
        return BLIND, (
            "train.csv carries no loss columns, so divergence CANNOT be seen from this log "
            f"(header: {','.join(rows[0])}). That is what a use_tb=False run looks like -- `drq` "
            "is always one, by C57's own tb regression. Fall back to "
            "check_checkpoint_finite.py on the snapshot, and to the standard-deviation tell: a "
            "NaN policy scores identically every episode where a bad one would vary")

    for row in rows[-tail:]:
        for c in present:
            # `csv.DictReader` yields None -- not "" -- for a column missing from a short row, and
            # train.csv is appended to while this runs, so a poll can land mid-write. float(None)
            # raises TypeError, not ValueError; catching only the latter crashed the watcher on
            # its first half-written row, found by its own test rather than in production.
            raw = (row.get(c) or "").strip().lower()
            if raw in ("nan", "-nan", "+nan"):
                return DEAD, f"{c} is nan at frame {row.get('frame', '?')}"
            try:
                if math.isnan(float(raw)):
                    return DEAD, f"{c} is nan at frame {row.get('frame', '?')}"
            except (ValueError, TypeError):
                continue

    # The C57 tell, kept as a second opinion for the case where losses are finite but the policy
    # has collapsed to a constant. Reported, never fatal: a genuinely converged policy on a
    # deterministic task could also hold return steady, and this instrument does not get to decide
    # that from twenty rows.
    rets = []
    for row in rows[-20:]:
        try:
            rets.append(float(row.get("episode_reward") or "nan"))
        except (ValueError, TypeError):
            pass
    rets = [r for r in rets if not math.isnan(r)]
    note = ""
    if len(rets) >= 10:
        m = sum(rets) / len(rets)
        sd = math.sqrt(max(0.0, sum((r - m) ** 2 for r in rets) / len(rets)))
        # A coefficient of variation, not `sd == 0.0`. Exact equality never fires: returns are
        # parsed from decimal strings, so twenty copies of "0.68" sum to something whose variance
        # is ~1e-17 rather than 0. It also would not fire on the real case that prompted this,
        # where the log alternated 0.68 and 0.69 -- visually constant, numerically not. 1% of the
        # mean is the threshold at which a human reading the column calls it flat.
        if m and sd < 0.01 * abs(m):
            note = (f"  NOTE: episode return varies by sd {sd:.4f} about mean {m:.2f} over "
                    f"{len(rets)} episodes -- under 1%, which is C57's indirect tell. Losses are"
                    " finite, so this is a collapsed policy rather than a NaN one, but it is not"
                    " learning")
    return OK, f"finite over the last {tail} logged updates ({len(present)} columns watched){note}"


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_EXP = ROOT / "RL-ViGen-upstream" / "exp_local"


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--run", help="one exp_local run directory containing train.csv")
    g.add_argument("--match",
                   help="watch EVERY run directory under --exp whose name contains this "
                        "substring, including ones that appear later. Mirrors "
                        "preserve_intermediate_snapshot.py, so one process covers a whole batch "
                        "and a run launched afterwards is not silently unwatched")
    ap.add_argument("--exp", default=str(DEFAULT_EXP))
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=float, default=60.0)
    ap.add_argument("--seconds", type=float, default=80000.0)
    a = ap.parse_args()

    started = time.time()

    if a.run:
        run = pathlib.Path(a.run)
        while True:
            code, why = inspect(run)
            if code == DEAD:
                print(f"DIVERGED: {why}. Any checkpoint from here is not a network (C57). "
                      f"run={run.name[:60]}", flush=True)
                return DEAD
            if code == BLIND:
                print(f"BLIND: {why}", flush=True)
                return BLIND
            if a.once:
                print(f"ok: {why}", flush=True)
                return OK
            if time.time() - started > a.seconds:
                print(f"ok at exit: {why}", flush=True)
                return OK
            time.sleep(a.interval)

    exp = pathlib.Path(a.exp)
    # Reported once per run, not once per poll: a diverged run stays diverged, and repeating the
    # line every interval would bury the next run's first report under the previous one's.
    announced: dict[pathlib.Path, int] = {}
    print(f"watching {exp} for '{a.match}'", flush=True)
    while True:
        for csv_path in sorted(exp.rglob("train.csv")):
            run = csv_path.parent
            if a.match not in run.name or announced.get(run) in (DEAD, BLIND):
                continue
            code, why = inspect(run)
            if code in (DEAD, BLIND) and announced.get(run) != code:
                seed = next((x for x in run.name.split(",") if x.startswith("seed=")), "seed=?")
                label = "DIVERGED" if code == DEAD else "BLIND"
                print(f"{label} [{seed}]: {why}"
                      + (". Any checkpoint from here is not a network (C57)" if code == DEAD else ""),
                      flush=True)
                announced[run] = code
        if a.once or time.time() - started > a.seconds:
            live = sum(1 for r, c in announced.items() if c == DEAD)
            print(f"exiting; {live} diverged run(s) reported", flush=True)
            return DEAD if live else OK
        time.sleep(a.interval)


if __name__ == "__main__":
    raise SystemExit(main())
