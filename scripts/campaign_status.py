#!/usr/bin/env python3
"""Campaign state across all 36 cells in one view, derived from artifacts.

    python scripts/campaign_status.py                    # the v100 production schedule
    python scripts/campaign_status.py --strict           # exit 1 if any cell is BLOCKED
    python scripts/campaign_status.py --schedule <path>

## Why this exists

`notes/PRODUCTION-RUNBOOK.md` lists three things as *"Not yet built, and worth having before day
one"*, and the first is **"a single command that reports campaign state across cells (currently
per-job)"**. `scripts/audit_attempt_ledger.py` answers "what became of this submission"; nothing
answered "how much of the campaign exists". Over a 9-28 day run across 12 baselines x 3 seeds,
that second question is the one an operator asks every morning, and reconstructing it by hand from
36 job ids is how a missing seed goes unnoticed until the table is being written.

## Derived, never maintained

Every state below is computed from artifacts the run already emits -- the schedule, the submission
ledger, `results/records/*.jsonl`, and the evaluator ledger. Nothing here asks the runner to keep a
new file up to date, because a ledger somebody must remember to update is a ledger that will be
wrong, and this project has already been bitten by exactly that (`SAVE_EVERY` vs
`SAVE_EVERY_FRAMES`, where a cadence knob nobody read let three jobs report success while
validating nothing).

## The states

    DONE        a record exists for this (baseline, seed) at the scheduled endpoint, and it
                carries the family's CURRENT evaluator revision
    SUPERSEDED  a record exists but its evaluator revision is not the live one. It is evidence
                about a tree that no longer exists, and re-running is the only way to fix it
    RUNNING     submitted, no records yet. Note the honest ambiguity: from disk alone RUNNING and
                a crash that emitted nothing are indistinguishable, which is why the state is read
                against the submission ledger rather than guessed
    MISSING     scheduled and never submitted
    BLOCKED     the family has no current evaluator attestation, so a cell run now would produce a
                record nothing can validate. This is the state that should stop a launch

A campaign is launchable when no row is BLOCKED. It is COMPLETE when every cell is DONE -- and the
gap between those two is the campaign itself.
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

DEFAULT_SCHEDULE = ROOT / "datasphere" / "native" / "production-schedule-v100.json"


def _live_revisions() -> dict[str, str]:
    from evaluator_identity import FAMILY_ALLOWED_BASELINES, evaluator_family_revision
    out = {}
    for family in FAMILY_ALLOWED_BASELINES:
        out[family] = evaluator_family_revision(ROOT, family)
    return out


def _attested() -> set[str]:
    path = ROOT / "datasphere" / "native" / "validated_evaluator_families.json"
    if not path.is_file():
        return set()
    data = json.loads(path.read_text())
    live = _live_revisions()
    families = data.get("families", data)
    out = set()
    for family, entry in families.items():
        if not isinstance(entry, dict):
            continue
        recorded = entry.get("evaluator_revision")
        if recorded and recorded == live.get(family):
            out.add(family)
    return out


def _records_index() -> dict[tuple[str, int], list[dict]]:
    """(baseline, seed) -> the records that exist for it."""
    index: dict[tuple[str, int], list[dict]] = collections.defaultdict(list)
    for path in (ROOT / "results" / "records").glob("*.jsonl"):
        for line in path.read_text(errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            baseline, seed = row.get("baseline"), row.get("seed")
            if baseline is None or seed is None:
                continue
            try:
                index[(baseline, int(seed))].append(row)
            except (TypeError, ValueError):
                continue
    return index


def _submitted() -> set[tuple[str, int]]:
    path = ROOT / "results" / "submissions.jsonl"
    out: set[tuple[str, int]] = set()
    if not path.is_file():
        return out
    for line in path.read_text(errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        for cell in (row.get("cells") or "").split(","):
            if ":" in cell:
                baseline, _, seed = cell.partition(":")
                try:
                    out.add((baseline.strip(), int(seed)))
                except ValueError:
                    pass
    return out


def state_of(baseline, family, seed, endpoint, records, submitted, attested, live):
    if family not in attested:
        return "BLOCKED", "family has no current evaluator attestation"
    rows = records.get((baseline, seed), [])
    at_endpoint = [r for r in rows if r.get("frame") in (endpoint, str(endpoint))]
    if at_endpoint:
        current = [r for r in at_endpoint if r.get("evaluator_revision") == live.get(family)]
        if current:
            return "DONE", f"{len(current)} record(s) at frame {endpoint}, current closure"
        return "SUPERSEDED", f"{len(at_endpoint)} record(s) at frame {endpoint}, stale closure"
    if rows:
        frames = sorted({r.get("frame") for r in rows if r.get("frame") is not None})
        return "RUNNING", f"records exist but none at {endpoint} (have: {frames[:4]})"
    if (baseline, seed) in submitted:
        return "RUNNING", "submitted, no records yet"
    return "MISSING", "scheduled, never submitted"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--schedule", default=str(DEFAULT_SCHEDULE))
    parser.add_argument("--strict", action="store_true", help="exit 1 if any cell is BLOCKED")
    args = parser.parse_args()

    schedule = json.loads(pathlib.Path(args.schedule).read_text())
    live, attested = _live_revisions(), _attested()
    records, submitted = _records_index(), _submitted()

    rows = schedule.get("rows", [])
    seeds = schedule.get("seeds", [])
    print(f"CAMPAIGN STATUS -- {pathlib.Path(args.schedule).name}, "
          f"host_profile={schedule.get('host_profile')}, {schedule.get('frames')} frames\n")
    print(f"  {'baseline':10} {'family':10} " + " ".join(f"seed {s}" for s in seeds))

    tally: collections.Counter = collections.Counter()
    detail: list[str] = []
    for row in rows:
        baseline, family = row["baseline"], row["family"]
        endpoint = row.get("executed_endpoint", schedule.get("frames"))
        cells = []
        for seed in row.get("seeds", seeds):
            state, why = state_of(baseline, family, seed, endpoint,
                                  records, submitted, attested, live)
            tally[state] += 1
            cells.append(f"{state:<8}")
            if state in ("BLOCKED", "SUPERSEDED"):
                detail.append(f"    {baseline}:{seed}  {state}  -- {why}")
        print(f"  {baseline:10} {family:10} " + " ".join(cells))

    total = sum(tally.values())
    print(f"\n  {total} cells: " + ", ".join(f"{n} {s}" for s, n in tally.most_common()))
    if detail:
        print("\n  needing attention:")
        for line in detail[:20]:
            print(line)

    blocked = tally.get("BLOCKED", 0)
    print()
    if blocked:
        print(f"  NOT LAUNCHABLE: {blocked} cell(s) BLOCKED. A cell run against a family with no")
        print("  current attestation produces a record nothing can validate.")
        missing = sorted({r["family"] for r in rows if r["family"] not in attested})
        print(f"  Families needing attestation: {', '.join(missing)}")
    elif tally.get("DONE", 0) == total:
        print("  COMPLETE: every scheduled cell has a record at its endpoint on the current"
              " closure.")
    else:
        print("  LAUNCHABLE: every family is attested. The remaining states are work, not defects.")
    return 1 if (blocked and args.strict) else 0


if __name__ == "__main__":
    raise SystemExit(main())
