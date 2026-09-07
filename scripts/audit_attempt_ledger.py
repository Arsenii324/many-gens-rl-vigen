#!/usr/bin/env python3
"""Every submitted attempt and what became of it, DERIVED from artifacts.

    python3 scripts/attempt_ledger.py
    python3 scripts/attempt_ledger.py --strict     # exit 1 if a rerun silently replaces an attempt

## Why this is derived and not maintained

`results/submissions.jsonl` answers "what did we launch": job id, config, commit, input hashes,
written at submit time by `job.sh`. It has no outcome half, so "a rerun never silently replaces a
failed seed" rested on discipline rather than on a record -- and discipline is exactly what a
27-hour cell at 3am does not have.

The obvious fix is to have the runner write outcomes as they happen. That fix is wrong: a ledger
the runner must remember to update is a ledger that will be wrong, and it will be wrong in the
direction of looking complete. So nothing new is written. Every state below is read back out of
artifacts that already exist for other reasons:

  - `results/records/<job_id>__records.jsonl`         -- the job id is the filename
  - `evaluator_revision` in each record               -- against the live tree, computed here
  - `_delivery_provenance.record_delivery`            -- whether the file is whole
  - `_delivery_provenance.execution_kind`             -- production versus exploratory

## What it deliberately does NOT claim

An attempt with no records file is reported as `NO-OUTCOME`, not as `RUNNING` and not as `FAILED`.
Those two are indistinguishable from disk, and guessing which would be the whole failure this file
exists to prevent -- a ledger that says FAILED for a running job invites a duplicate submission.
Ask DataSphere (`bash datasphere/native/job.sh status <id>`) when the difference matters.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "datasphere" / "native"))

LEDGER = ROOT / "results" / "submissions.jsonl"
RECORDS = ROOT / "results" / "records"


def _live_revisions() -> dict[str, str]:
    from evaluator_identity import FAMILY_ALLOWED_BASELINES, evaluator_family_revision
    out = {}
    for family in FAMILY_ALLOWED_BASELINES:
        try:
            out[family] = evaluator_family_revision(family)
        except Exception:
            continue
    return out


def _outcome(job_id: str, live: dict[str, str]) -> tuple[str, str]:
    path = RECORDS / f"{job_id}__records.jsonl"
    if not path.is_file():
        return "NO-OUTCOME", "no records file; RUNNING and FAILED are indistinguishable from disk"
    rows = []
    for line in path.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not rows:
        return "EMPTY", "records file exists but carries no parsable row"
    delivery = {(r.get("_delivery_provenance") or {}).get("record_delivery") for r in rows}
    if delivery != {"complete"}:
        return "PARTIAL", f"record_delivery {sorted(str(d) for d in delivery)}"
    families = {r.get("family") for r in rows}
    stale = [r for r in rows if r.get("evaluator_revision") != live.get(r.get("family"))]
    kinds = {(r.get("_delivery_provenance") or {}).get("execution_kind") for r in rows}
    if stale:
        return "SUPERSEDED", (f"{len(stale)}/{len(rows)} rows carry an evaluator revision the live "
                              f"tree no longer has ({', '.join(sorted(f or '?' for f in families))})")
    if kinds == {"training_production"}:
        return "ELIGIBLE", f"{len(rows)} rows, current closure, production"
    return "DIAGNOSTIC", f"{len(rows)} rows, current closure, kind {sorted(str(k) for k in kinds)}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 if one config was submitted more than once without both "
                             "outcomes being visible")
    args = parser.parse_args()

    if not LEDGER.is_file():
        print(f"no submission ledger at {LEDGER}; nothing has been recorded at submit time yet")
        return 0
    attempts = []
    for line in LEDGER.read_text().splitlines():
        try:
            attempts.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    live = _live_revisions()

    print("ATTEMPT LEDGER -- every submission and what the artifacts say became of it\n")
    print(f"  {'job':22} {'config':38} {'state':12} detail")
    print("  " + "-" * 110)
    by_config: dict[str, list] = collections.defaultdict(list)
    for attempt in attempts:
        job = attempt.get("job_id") or "-"
        config = pathlib.Path(str(attempt.get("config") or "-")).name
        state, detail = _outcome(job, live)
        dirty = attempt.get("source_dirty")
        if dirty is True:
            detail += "  [submitted from a DIRTY tree]"
        print(f"  {job:22} {config:38} {state:12} {detail}")
        by_config[config].append((job, state))

    repeats = {config: rows for config, rows in by_config.items() if len(rows) > 1}
    print()
    if repeats:
        print(f"  {len(repeats)} config(s) submitted more than once. A rerun is legitimate; a rerun")
        print("  whose predecessor's outcome is invisible is how a failed seed gets replaced")
        print("  silently, which is the thing this ledger exists to make impossible:")
        for config, rows in sorted(repeats.items()):
            states = ", ".join(f"{job}={state}" for job, state in rows)
            print(f"    {config}: {states}")
        unresolved = {c: r for c, r in repeats.items()
                      if any(state == "NO-OUTCOME" for _job, state in r)}
        if unresolved:
            print()
            print(f"  {len(unresolved)} of those has an attempt with NO recorded outcome, so which")
            print("  attempt the results came from cannot be read off disk. Resolve with")
            print("  `bash datasphere/native/job.sh status <id>` and record it.")
            if args.strict:
                return 1
    else:
        print("  no config was submitted twice.")

    counts = collections.Counter(state for rows in by_config.values() for _job, state in rows)
    print()
    print("  " + "  ".join(f"{state}={n}" for state, n in sorted(counts.items())))
    print("\n  ELIGIBLE means: records complete, evaluator revision equal to the live tree, and")
    print("  execution_kind training_production. Nothing else may enter a reported row.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
