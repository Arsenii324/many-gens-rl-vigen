#!/usr/bin/env python3
"""One flat table of every record in the fleet, with a documented schema.

    python scripts/export_fleet.py                       # summary to stdout
    python scripts/export_fleet.py --csv fleet.csv       # the flat table
    python scripts/export_fleet.py --schema              # the column contract, alone
    python scripts/export_fleet.py --current-only        # drop superseded-closure rows

## Why this exists

`notes/production-readiness-by-class.md` lists whole-fleet export as PARTIAL: *"Records are per
job. There is no combined fleet-level table or documented schema, so post-processing means knowing
the layout. Ready with one exporter and a schema note. Cheap, and worth doing before the data
exists rather than after."*

Before, deliberately. An exporter written against real results is written against the shape those
results happen to have, and every ambiguity gets resolved in whichever direction makes that
particular table come out. Written first, the ambiguities have to be decided on their merits, and
the two that matter here are decided below rather than papered over.

## The two decisions this makes, and they are not cosmetic

**A row from a superseded evaluator closure is EXPORTED and MARKED, never dropped.** Silently
dropping it would make the export disagree with `results/records/` for reasons a reader cannot see;
silently keeping it would pool measurements from trees that no longer exist. So every row carries
`closure_current` (true/false) and `--current-only` is an explicit choice the caller makes, not a
default the exporter makes for them. This project has been bitten by pooled closures before -- it
is what `audit_row_closure.py` exists to refuse.

**`episode_return_mean` is NOT comparable across every row and the schema says so in-band.**
`policy_mode` is carried on each row precisely because `idaac`, `ppg` and `ibac_sni` report a
SAMPLED return and the other nine report a mode return -- different estimands, not one quantity
measured twice (`notes/SAME-AXES-VERDICT.md`). An exporter that emitted a bare `return` column
would invite exactly the cross-block ranking `scripts/comparison_blocks.py` refuses.

## What it does not do

No aggregation, no ratios, no retention. Those are analysis, they carry caveats
(`docs/RESEARCH-FRAME.md`'s second-order interaction, C18's near-zero denominator), and a column of
numbers with the caveats stripped is how a caveat gets lost. This is the flat substrate; the
analysis lives where its reasoning lives.
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "datasphere" / "native"))

RECORDS = ROOT / "results" / "records"

#: (column, source, meaning). This IS the schema note -- it is emitted by `--schema`, so it cannot
#: drift away from what the exporter actually writes.
SCHEMA: tuple[tuple[str, str, str], ...] = (
    ("job", "filename", "the DataSphere job id that produced the row"),
    ("baseline", "record", "one of the twelve"),
    ("family", "record", "the evaluator family; seven of them, sharing one payload and evaluator"),
    ("cell", "record", "baseline-seed identifier within the job"),
    ("seed", "record", "training seed"),
    ("frame", "record", "the frame the checkpoint was taken at, as REQUESTED -- eval_grid.py "
                        "takes it from --frame, never from inside the checkpoint"),
    ("phase", "record", "train / eval; which regime family the row belongs to"),
    ("regime", "record", "train, eval-easy, eval-medium, eval-hard"),
    ("scene_set", "record", "which certified scene set was swept"),
    ("episodes", "record", "episodes behind this row's mean"),
    ("episode_return_mean", "record", "mean episode return. NOT comparable across policy_mode -- "
                                      "see that column"),
    ("episode_return_sd", "record", "standard deviation across those episodes"),
    ("success_rate", "record", "fraction of episodes with the task success flag"),
    ("policy_mode", "evaluator_identity", "sample or mode. idaac/ppg/ibac_sni sample; the other "
                                          "nine take the mode. Different ESTIMANDS, so rows "
                                          "differing here may not be ranked against each other"),
    ("evaluator_revision", "record", "the closure that produced the row"),
    ("closure_current", "derived", "whether evaluator_revision equals the live one for that "
                                   "family. FALSE rows describe a tree that no longer exists"),
    ("checkpoint_sha256", "record", "the weights measured, when the row carries one"),
    ("frame_stack", "evaluator_scope", "observation stack depth as actually executed"),
    ("image_size", "evaluator_scope", "render size as actually executed"),
    ("time_limit", "protocol", "bootstrap or terminal; rad/soda/alda bootstrap, the other nine "
                               "zero the value target at truncation"),
    ("train_reward", "protocol", "raw or normalised TRAINING reward. idaac/ppg/ctrl normalise. "
                                 "Every row's reported return is raw regardless"),
    ("schema", "record", "the record schema version the job wrote"),
)


def _live_revisions() -> dict[str, str]:
    from evaluator_identity import FAMILY_ALLOWED_BASELINES, evaluator_family_revision
    return {f: evaluator_family_revision(ROOT, f) for f in FAMILY_ALLOWED_BASELINES}


def _policy_modes() -> dict[str, str]:
    from evaluator_identity import FAMILY_ALLOWED_BASELINES, family_eval_policy_mode
    out = {}
    for family, baselines in FAMILY_ALLOWED_BASELINES.items():
        for baseline in baselines:
            out[baseline] = family_eval_policy_mode(family)
    return out


def rows(current_only: bool = False) -> list[dict]:
    from rlgen.protocol import REWARD_NORMALIZATION, TIME_LIMIT_HANDLING
    live, modes = _live_revisions(), _policy_modes()
    out: list[dict] = []
    for path in sorted(RECORDS.glob("*.jsonl")):
        job = path.name.split("__", 1)[0]
        for line in path.read_text(errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            family = rec.get("family")
            baseline = rec.get("baseline")
            scope = rec.get("evaluator_scope") or {}
            current = (rec.get("evaluator_revision") is not None
                       and rec.get("evaluator_revision") == live.get(family))
            if current_only and not current:
                continue
            out.append({
                "job": job,
                "baseline": baseline,
                "family": family,
                "cell": rec.get("cell"),
                "seed": rec.get("seed"),
                "frame": rec.get("frame"),
                "phase": rec.get("phase"),
                "regime": rec.get("regime"),
                "scene_set": rec.get("scene_set"),
                "episodes": rec.get("episodes"),
                "episode_return_mean": rec.get("episode_return_mean"),
                "episode_return_sd": rec.get("episode_return_sd"),
                "success_rate": rec.get("success_rate"),
                "policy_mode": modes.get(baseline),
                "evaluator_revision": rec.get("evaluator_revision"),
                "closure_current": current,
                "checkpoint_sha256": rec.get("checkpoint_sha256"),
                "frame_stack": scope.get("frame_stack"),
                "image_size": scope.get("image_size"),
                "time_limit": TIME_LIMIT_HANDLING.get(baseline),
                "train_reward": REWARD_NORMALIZATION.get(baseline),
                "schema": rec.get("schema"),
            })
    return out


def print_schema() -> None:
    print("FLEET EXPORT SCHEMA\n")
    for column, source, meaning in SCHEMA:
        print(f"  {column:22} [{source}]")
        for i in range(0, len(meaning), 88):
            print(f"      {meaning[i:i + 88]}")
    print("\n  Two columns exist to STOP a comparison, not to enable one:")
    print("    policy_mode      sampled and mode returns are different estimands; rows differing")
    print("                     here may not be ranked against each other.")
    print("    closure_current  FALSE means the row describes a tree that no longer exists. It is")
    print("                     exported and marked rather than dropped, so this table never")
    print("                     disagrees with results/records for a reason a reader cannot see.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--csv")
    parser.add_argument("--jsonl")
    parser.add_argument("--schema", action="store_true")
    parser.add_argument("--current-only", action="store_true")
    args = parser.parse_args()

    if args.schema:
        print_schema()
        return 0

    data = rows(current_only=args.current_only)
    columns = [c for c, _, _ in SCHEMA]

    if args.csv:
        with open(args.csv, "w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(data)
        print(f"wrote {len(data)} rows to {args.csv}")
    if args.jsonl:
        with open(args.jsonl, "w") as handle:
            for row in data:
                handle.write(json.dumps(row) + "\n")
        print(f"wrote {len(data)} rows to {args.jsonl}")

    current = sum(1 for r in data if r["closure_current"])
    by_baseline: dict[str, int] = {}
    for row in data:
        by_baseline[row["baseline"]] = by_baseline.get(row["baseline"], 0) + 1
    print(f"\n{len(data)} rows, {current} on the CURRENT closure, "
          f"{len(data) - current} superseded")
    print(f"{len(by_baseline)} baselines: "
          + ", ".join(f"{b} {n}" for b, n in sorted(by_baseline.items())))
    if not args.csv and not args.jsonl:
        print("\n(--csv/--jsonl to write; --schema for the column contract)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
