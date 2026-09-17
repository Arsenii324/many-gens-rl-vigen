#!/usr/bin/env python3
"""Merge a re-evaluation sweep's result archives into one records file, refusing on disagreement.

    # fetch the archives first (they stay on the host until you ask for them)
    rsync -a 'HOST:~/rlvigen-runs/reeval-v214/idaac-s101-curve-*-result.tgz' ./fetched/

    python scripts/collect_reeval_sweep.py ./fetched --tag reeval-v214-idaac-curve
    python scripts/collect_reeval_sweep.py ./fetched --tag ... --write

## Why this exists

A curve sweep produces ONE ARCHIVE PER STAMP -- twelve for ppg, eleven for idaac -- and each holds
its own `records_delivery.jsonl`. Turning that into the single
`results/records/<tag>__records.jsonl` the ledger reads was done **by hand** for ppg's 528 rows,
and the operator guide's "after a run" steps do not cover it: `collect-host-run.sh` takes a run
directory, and a sweep is not a run directory.

Hand-merging eleven archives is exactly the shape of task that goes wrong quietly. A stamp silently
omitted leaves a curve with a hole that looks like a curve; a stamp included twice doubles a point's
weight; and an archive from a superseded closure pools two trees into one file, which is the thing
`audit_row_closure.py` exists to refuse after the fact.

## What it refuses, rather than warns about

- **A row whose `evaluator_revision` is not the family's live one.** Same rule as
  `populate_evaluator_ledger.py`, applied before the file is written rather than after.
- **Rows disagreeing on `evaluator_revision` within the sweep.** That is two closures in one file.
- **The same (cell, frame, regime, scene_set, policy mode) appearing twice.** A duplicated stamp.
- **Writing over an existing records file.** Collection is not a thing to do twice by accident.

It reports the stamps it found and their frames, so a missing one is visible as a gap in a printed
list rather than as an absence nobody counted.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys
import tarfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "datasphere" / "native"))
RECORDS = ROOT / "results" / "records"
MEMBER = "records_delivery.jsonl"


def _live_revisions() -> dict[str, str]:
    from evaluator_identity import FAMILY_ALLOWED_BASELINES, evaluator_family_revision
    return {f: evaluator_family_revision(ROOT, f) for f in FAMILY_ALLOWED_BASELINES}


def _row_key(row: dict) -> tuple:
    """What makes a row unique within a sweep.

    [Claude 2026-09-16] The policy mode lives in `conventions.eval_policy_mode`, NOT at the top
    level -- the top-level `eval_policy_mode` is absent on these records and reads None. A first
    version of this key used the top-level field and therefore produced **44 distinct keys for the
    88 rows of a ppg endpoint sweep**: the endpoint grid runs TWICE, once sampling and once taking
    the mode, and both passes carry identical cell/frame/regime/scene_set. Collecting with that key
    would have rejected an entire endpoint sweep as duplicated, or silently kept half of it.

    Caught by checking the key against a real committed endpoint file before trusting the tool, not
    by reading the code. `evaluator_measurement_revision` is included as well because it differs
    between the two passes and is identical between two copies of the same archive -- so a genuine
    duplicate still collides, which is the behaviour this key exists to produce.

    [Claude 2026-09-17] And `conventions.eval_policy_mode` is NOT the authoritative field either,
    which the reeval files hide because on them the two agree. Measured across the committed record
    sets:

        reeval-v214-ppg-endpoint      conventions 44/44 split   evaluator_scope 44/44 split
        reeval-v214-idaac-endpoint    conventions 44/44 split   evaluator_scope 44/44 split
        card0-20260909-035152         conventions 569x 'sample' evaluator_scope 528 + 41 'mode'

    The last line is an IN-RUN delivery rather than a sweep, and on that path `conventions`
    carries the FAMILY's native rule -- a constant -- while `evaluator_scope.eval_policy_mode`
    carries the pass that actually ran. eval_grid.py:1462 says so in as many words: it "MUST reflect
    what ran, not what the family natively does".

    **What this did NOT do, checked before it was written down.** It is tempting to say the old
    order "would have collapsed 41 mode rows onto their native twins". It would not have, and the
    measurement says so: over that file's 85 endpoint rows the old order and the new one both yield
    85 distinct keys. `evaluator_measurement_revision` differs between the two passes and is already
    part of the key, so the passes stayed apart by way of a field that happens to vary rather than
    the field that names the difference.

    That is the actual argument for reordering, and it is weaker than a bug but not nothing: the
    key's mode component should MEAN the pass that ran, and separation should not rest on a
    coincidence in a neighbouring field. Reordering is free -- on all four committed sweep files the
    two fields agree and every key count is unchanged (88, 88, 484, 528) -- so it costs nothing to
    stop depending on the coincidence.
    """
    conventions = row.get("conventions") or {}
    scope = row.get("evaluator_scope") or {}
    mode = (scope.get("eval_policy_mode")
            or conventions.get("eval_policy_mode")
            or (row.get("evaluator_identity") or {}).get("policy_mode")
            or row.get("eval_policy_mode"))
    return (row.get("cell"), row.get("frame"), row.get("regime"), row.get("scene_set"),
            mode, row.get("evaluator_measurement_revision"))


def rows_of(archive: pathlib.Path) -> list[dict]:
    try:
        with tarfile.open(archive, "r:gz") as tar:
            member = next((m for m in tar.getmembers() if m.name.endswith(MEMBER)), None)
            if member is None:
                return []
            handle = tar.extractfile(member)
            if handle is None:
                return []
            out = []
            for line in handle.read().decode("utf-8", "replace").splitlines():
                if line.strip():
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            return out
    except (tarfile.TarError, OSError) as exc:
        print(f"  UNREADABLE {archive.name}: {exc}")
        return []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("directory", help="directory holding the *-result.tgz archives")
    ap.add_argument("--tag", required=True, help="output name: results/records/<tag>__records.jsonl")
    ap.add_argument("--write", action="store_true", help="write the file; otherwise dry-run")
    args = ap.parse_args()

    archives = sorted(pathlib.Path(args.directory).glob("*-result.tgz"))
    if not archives:
        print(f"no *-result.tgz under {args.directory}. Nothing collected -- which is NOT the same "
              "as nothing to collect.")
        return 1

    live = _live_revisions()
    merged: list[dict] = []
    problems: list[str] = []
    seen: dict[tuple, str] = {}
    per_archive: list[tuple[str, int, set]] = []

    for archive in archives:
        rows = rows_of(archive)
        if not rows:
            problems.append(f"{archive.name}: no {MEMBER} rows -- a result with no records is "
                            "itself a finding")
            continue
        frames = {r.get("frame") for r in rows}
        per_archive.append((archive.name, len(rows), frames))
        for row in rows:
            family = row.get("family")
            revision = row.get("evaluator_revision")
            expected = live.get(family)
            if expected and revision != expected:
                problems.append(f"{archive.name}: family {family} row carries evaluator_revision "
                                f"{str(revision)[:12]}..., live is {str(expected)[:12]}...")
                continue
            key = _row_key(row)
            if key in seen and seen[key] != archive.name:
                problems.append(f"duplicate row {key} in both {seen[key]} and {archive.name}")
                continue
            seen[key] = archive.name
            merged.append(row)

    print(f"{len(archives)} archive(s), {len(merged)} row(s) accepted\n")
    for name, count, frames in per_archive:
        fr = ", ".join(str(f) for f in sorted(x for x in frames if x is not None))
        print(f"  {name:52} {count:4} rows   frames {fr[:60]}")
    all_frames = sorted({f for _n, _c, fs in per_archive for f in fs if f is not None})
    print(f"\n  stamps covered ({len(all_frames)}): {', '.join(str(f) for f in all_frames)}")

    revisions = {r.get("evaluator_revision") for r in merged}
    if len(revisions) > 1:
        problems.append(f"the sweep spans {len(revisions)} evaluator revisions; that is two "
                        "closures in one file")

    out = RECORDS / f"{args.tag}__records.jsonl"
    if out.exists():
        problems.append(f"{out.relative_to(ROOT)} already exists; refusing to overwrite a "
                        "collection")

    if problems:
        print(f"\n  REFUSING ({len(problems)}):")
        for p in problems:
            print(f"    {p}")
        return 1

    if not args.write:
        print(f"\n  dry run. --write to create {out.relative_to(ROOT)}")
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(r) for r in merged) + "\n")
    fams = collections.Counter(r.get("family") for r in merged)
    print(f"\n  wrote {out.relative_to(ROOT)} ({len(merged)} rows)")
    # [Claude 2026-09-17] This used to print
    #     next: python scripts/populate_evaluator_ledger.py <family> <tag>
    # for every sweep, which is the one command that must NOT be run on one. That script records a
    # family's evaluator ATTESTATION, and production_gates accepts only single-scope endpoint
    # evidence -- one frame, one policy pass. A curve sweep is many frames, so the entry would be
    # rejected; and because each run REPLACES the family's entry, writing a rejected one REMOVES a
    # valid attestation with no error. It had already done that to idaac and ppg before being
    # caught. populate_evaluator_ledger now refuses using the gate's own check, so this hint was
    # advice that its own target would reject.
    endpoint_only = all((r.get("evaluator_scope") or {}).get("eval_scope") == "endpoint"
                        for r in merged)
    for family, n in fams.most_common():
        print(f"    {family}: {n} rows")
    if endpoint_only:
        print("\n  These rows are endpoint-scope. If this sweep is a single-scope attestation job,")
        print("  populate_evaluator_ledger.py may accept it; it verifies with the gate's own check")
        print("  and refuses otherwise.")
    else:
        print("\n  Do NOT run populate_evaluator_ledger.py on this: it is not single-scope endpoint")
        print("  evidence, and a rejected write would REMOVE the family's current attestation.")
    print("  Next: scripts/campaign_status.py, and scripts/audit_record_frame_provenance.py")
    print("  --checkpoints <dir> to bind these rows to the files they measured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
