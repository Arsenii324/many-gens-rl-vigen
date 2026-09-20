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
    """The live evaluator revision per family.

    [Claude 2026-09-08] This called `evaluator_family_revision(family)` while the real signature is
    `(root, family)`, and the `except Exception: continue` swallowed the resulting TypeError. The
    map therefore came back EMPTY, every recorded revision compared against `None`, and ppg's first
    genuine attestation reported SUPERSEDED at the same moment `populate_evaluator_ledger.py`
    asserted the revision was current. Two instruments disagreeing is what exposed it.

    A broad `except` around a call whose signature can drift converts a crash into a wrong answer,
    which is strictly worse: the crash is visible. It now raises.
    """
    from evaluator_identity import FAMILY_ALLOWED_BASELINES, evaluator_family_revision
    return {family: evaluator_family_revision(ROOT, family)
            for family in FAMILY_ALLOWED_BASELINES}


OUTCOMES = ROOT / "results" / "attempt-outcomes.json"

#: The states an operator may record for an attempt that produced no artifacts. Deliberately
#: small: this file exists for the one case artifacts CANNOT express, not as a general override.
RECORDABLE = {"FAILED-TRAIN", "FAILED-EVAL", "CANCELLED", "SUPERSEDED-BEFORE-RUN"}


def _recorded_outcomes() -> dict[str, dict]:
    """Operator-recorded terminal states for attempts that emitted nothing.

    Everything else in this file is derived, on the stated principle that a ledger the runner must
    remember to update will be wrong in the direction of looking complete. This is the exception,
    and it is a narrow one: a job that failed before writing records leaves NO artifact saying so,
    so `--strict` would refuse a legitimate resubmission forever and the gate would be permanently
    red with no way to clear it. A rule that cannot be satisfied is not a safeguard; people route
    around it, and then it protects nothing.

    So the escape exists, and it is deliberately made expensive to misuse: it accepts only terminal
    FAILURE states (never ELIGIBLE -- a result must still come from records), it demands a reason
    string, and every entry is printed in full on every run, so using it is visible rather than
    quiet.

        {"bt1abc...": {"state": "FAILED-TRAIN", "reason": "OOM at 40k, log line 812"}}
    """
    if not OUTCOMES.is_file():
        return {}
    try:
        data = json.loads(OUTCOMES.read_text())
    except json.JSONDecodeError:
        return {}
    return {job: entry for job, entry in data.items()
            if isinstance(entry, dict) and entry.get("state") in RECORDABLE and entry.get("reason")}


def _outcome(job_id: str, live: dict[str, str], recorded: dict[str, dict]) -> tuple[str, str]:
    path = RECORDS / f"{job_id}__records.jsonl"
    if not path.is_file():
        if job_id in recorded:
            entry = recorded[job_id]
            return entry["state"], f"operator-recorded: {entry['reason']}"
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
    # ONLY rows the evaluator produced can say anything about the evaluator's closure. A records
    # file also carries training-curve rows (`phase` train/eval) written by the trainer, and those
    # legitimately have no `evaluator_revision` at all.
    #
    # [Claude 2026-09-08] This compared every row, so ppg's first real attestation read SUPERSEDED
    # -- "4/10 rows carry an evaluator revision the live tree no longer has" -- at the same moment
    # `populate_evaluator_ledger.py` asserted the revision MATCHED. Two instruments disagreeing is
    # what exposed it, and the other one was right: 4 offline-eval rows carried the live revision
    # and 6 curve rows carried None, which this counted as six mismatches.
    evaluated = [r for r in rows if r.get("evaluator_revision") is not None]
    if not evaluated:
        return "NO-EVAL-ROWS", f"{len(rows)} rows, none produced by the evaluator"
    families = {r.get("family") for r in evaluated}
    stale = [r for r in evaluated if r.get("evaluator_revision") != live.get(r.get("family"))]
    kinds = {(r.get("_delivery_provenance") or {}).get("execution_kind") for r in evaluated}
    if stale:
        return "SUPERSEDED", (f"{len(stale)}/{len(evaluated)} evaluator rows carry a revision the live "
                              f"tree no longer has ({', '.join(sorted(f or '?' for f in families))})")
    if kinds == {"training_production"}:
        return "ELIGIBLE", f"{len(evaluated)} evaluator rows, current closure, production"
    return "DIAGNOSTIC", (f"{len(evaluated)} evaluator rows, current closure, "
                          f"kind {sorted(str(k) for k in kinds)}")


#: Host runs are a SECOND attempt system and nothing gated them until 2026-09-16.
#:
#: This audit's promise -- "a rerun never silently replaces a failed seed" -- was built against
#: `results/submissions.jsonl`, which records DataSphere jobs. Production no longer runs there: it
#: runs on the V100 host, whose attempts are recorded in `results/host-runs.jsonl` by
#: `scripts/record_host_run.py`. So the guarantee held for the jobs we had stopped running and not
#: for the ones we had started.
#:
#: It became concrete on 2026-09-16, when FIVE ibac_sni cells failed on the host in one day. A sixth
#: attempt at the same (baseline, seed) could have been launched with nothing refusing, and nothing
#: on disk saying what became of its predecessors -- exactly the shape this file exists to catch.
#:
#: The check is the same one, in the same spirit: for a (baseline, seed) attempted more than once,
#: every attempt but the newest must carry a terminal status. "running", empty, or absent on an
#: EARLIER attempt is the refusal. The newest attempt is never flagged, because the currently
#: running cell legitimately has no outcome yet.
HOST_LEDGER = ROOT / "results" / "host-runs.jsonl"
_TERMINAL_HINTS = ("fail", "complete", "done", "collected", "stopped", "yield", "cancel",
                   "superseded", "abandoned")


def _host_attempts() -> dict[tuple[str, object], list[tuple[str, str]]]:
    """{(baseline, seed): [(run_id, status), ...]} ordered oldest first.

    [Claude 2026-09-20] A row with no parseable `seed` used to key as `(baseline, None)` -- which
    does not collide with a real seed's own key, but DOES silently merge every such row for one
    baseline together, as if they were repeated attempts of one (nonexistent) cell. See
    `_host_attempts_unkeyable()` for those rows, counted and reported by `main()` instead.
    """
    out: dict[tuple[str, object], list[tuple[str, str]]] = collections.defaultdict(list)
    if not HOST_LEDGER.is_file():
        return out
    for line in HOST_LEDGER.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            seed = int(row.get("seed"))
        except (TypeError, ValueError):
            continue
        key = (row.get("baseline"), seed)
        out[key].append((str(row.get("run_id") or "?"), str(row.get("status") or "")))
    for key in out:
        out[key].sort(key=lambda pair: pair[0])
    return out


def _host_attempts_unkeyable() -> list[dict]:
    """Host-ledger rows excluded from `_host_attempts()` because their seed did not parse."""
    out: list[dict] = []
    if not HOST_LEDGER.is_file():
        return out
    for line in HOST_LEDGER.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            int(row.get("seed"))
        except (TypeError, ValueError):
            out.append(row)
    return out


def _host_problems() -> list[str]:
    problems: list[str] = []
    for (baseline, seed), rows in sorted(_host_attempts().items(), key=lambda kv: str(kv[0])):
        if len(rows) < 2:
            continue
        for run_id, status in rows[:-1]:          # never the newest
            low = status.lower()
            if not low or not any(h in low for h in _TERMINAL_HINTS):
                problems.append(
                    f"{baseline}:{seed} attempt {run_id} has status {status!r}, which is not a "
                    "terminal outcome, and a later attempt exists. Record what became of it with "
                    "`scripts/record_host_run.py <dir> --update-status ...`")
    return problems


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
    recorded = _recorded_outcomes()

    print("ATTEMPT LEDGER -- every submission and what the artifacts say became of it\n")
    print(f"  {'job':22} {'config':38} {'state':12} detail")
    print("  " + "-" * 110)
    by_config: dict[str, list] = collections.defaultdict(list)
    for attempt in attempts:
        job = attempt.get("job_id") or "-"
        config = pathlib.Path(str(attempt.get("config") or "-")).name
        state, detail = _outcome(job, live, recorded)
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
        # All attempts EXCEPT the most recent. The ledger is append-ordered, so the last row for
        # a config is the attempt that may legitimately still be running -- flagging that would
        # make the gate red for the entire duration of every wave, which is how a safeguard gets
        # routed around. What must never be unknown is a PREDECESSOR: that is the one whose result
        # a rerun could silently replace.
        unresolved = {c: r for c, r in repeats.items()
                      if any(state == "NO-OUTCOME" for _job, state in r[:-1])}
        if unresolved:
            print()
            print(f"  {len(unresolved)} of those has an attempt with NO recorded outcome, so which")
            print("  attempt the results came from cannot be read off disk. Resolve with")
            print("  `bash datasphere/native/job.sh status <id>`, then record the terminal state in")
            print(f"  {OUTCOMES.relative_to(ROOT)} as {{\"<job>\": {{\"state\": ..., \"reason\": ...}}}}")
            print(f"  with state one of {sorted(RECORDABLE)}. A job that failed before writing")
            print("  records leaves no artifact saying so, and that is the only case this file is for.")
            if args.strict:
                return 1
    else:
        print("  no config was submitted twice.")

    if recorded:
        print(f"  {len(recorded)} attempt(s) carry an operator-recorded outcome, listed in full so")
        print("  that using the escape is visible rather than quiet:")
        for job, entry in sorted(recorded.items()):
            print(f"    {job}  {entry['state']}  {entry['reason']}")
        print()

    host = _host_attempts()
    host_problems = _host_problems()
    host_unkeyable = _host_attempts_unkeyable()
    print()
    print(f"  HOST attempts (results/host-runs.jsonl): {sum(len(v) for v in host.values())} run(s) "
          f"across {len(host)} (baseline, seed) pair(s).")
    if host_unkeyable:
        print(f"    WARNING: {len(host_unkeyable)} row(s) have no parseable seed and are EXCLUDED "
              "above -- never merged into any (baseline, seed):")
        for row in host_unkeyable[:10]:
            print(f"      run_id={row.get('run_id')!r} baseline={row.get('baseline')!r} "
                  f"seed={row.get('seed')!r}")
    if host_problems:
        for prob in host_problems:
            print(f"    REFUSING: {prob}")
    else:
        print("    every re-attempted (baseline, seed) has a terminal status on all but its newest "
              "run.")
    print()

    counts = collections.Counter(state for rows in by_config.values() for _job, state in rows)
    print()
    print("  " + "  ".join(f"{state}={n}" for state, n in sorted(counts.items())))
    if host_problems and args.strict:
        return 1
    print("\n  ELIGIBLE means: records complete, evaluator revision equal to the live tree, and")
    print("  execution_kind training_production. Nothing else may enter a reported row.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
