#!/usr/bin/env python3
"""Do the seeds pooled into one reported row come from ONE scientific closure?

[Claude 2026-09-07, external recommendation 22 item 15.] "A rerun never silently incorporates a
newly fixed tree." If production code is fixed after seed 101 fails, seeds produced under the old
closure are a different revision and must not be mixed without explicit treatment.

**The evidence for this has always existed and nothing checked it.** Every record carries
`native.run_provenance.payload_sha256`, `manifest_sha256` and `requirements_native_sha256`, plus a
top-level `evaluator_revision`, `evaluator_scope_revision` and `checkpoint_sha256`. A row that pools
three seeds built from two different payloads is therefore fully detectable in the artifacts and was
entirely invisible in practice, because no instrument asked.

That asymmetry -- recorded but unchecked -- is the same shape as `eval_grid.py`'s claim that "no
table pools the two" policy modes, which was true of the intent and unenforced until today.

    python scripts/audit_row_closure.py                  # every record file under results/records
    python scripts/audit_row_closure.py --strict         # exit 1 when any row is mixed
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
RECORDS = ROOT / "results" / "records"

#: What must agree across the seeds of one reported row. Not everything in a record: `seed` differs
#: by construction, and wall-clock, host and job id are execution facts rather than scientific ones.
CLOSURE_FIELDS = (
    ("payload_sha256", lambda r: (r.get("native", {}).get("run_provenance") or {}).get("payload_sha256")),
    ("requirements_native_sha256",
     lambda r: (r.get("native", {}).get("run_provenance") or {}).get("requirements_native_sha256")),
    ("container_image",
     lambda r: (r.get("native", {}).get("run_provenance") or {}).get("container_image")),
    ("evaluator_revision", lambda r: r.get("evaluator_revision")),
    ("evaluator_scope_revision", lambda r: r.get("evaluator_scope_revision")),
    ("eval_policy_mode", lambda r: (r.get("conventions") or {}).get("eval_policy_mode")),
)


def rows(paths):
    """Group records by what a reported row is: one baseline, one regime, one frame, one scope."""
    grouped = collections.defaultdict(list)
    grouped_kind: dict = {}
    for path in paths:
        for line in path.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict) or record.get("baseline") is None:
                continue
            # `evaluator_scope` is a dict and unhashable; its revision is the hashable identity
            # of exactly the same thing, and is what the ledger attests anyway.
            key = (record.get("baseline"), record.get("regime"), record.get("frame"),
                   record.get("evaluator_scope_revision"))
            grouped_kind[key] = ((record.get("_delivery_provenance") or {}).get("execution_kind")
                                 or grouped_kind.get(key))
            grouped[key].append((path.name, record))
    return grouped, grouped_kind


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 when a row mixes closures, rather than only reporting")
    parser.add_argument("--records", default=str(RECORDS))
    args = parser.parse_args()

    directory = pathlib.Path(args.records)
    paths = sorted(directory.glob("*.jsonl")) if directory.is_dir() else []
    if not paths:
        print(f"no record files under {directory}")
        return 0

    grouped, kinds = rows(paths)
    multi_seed = {key: entries for key, entries in grouped.items()
                  if len({r.get("seed") for _, r in entries}) > 1}
    mixed = []
    for key, entries in sorted(multi_seed.items(), key=lambda kv: str(kv[0])):
        for field, get in CLOSURE_FIELDS:
            values = {get(record) for _, record in entries}
            values.discard(None)
            if len(values) > 1:
                mixed.append((key, field, values, sorted({name for name, _ in entries})))

    print("ROW CLOSURE AUDIT -- do the seeds pooled into one row share one scientific closure?")
    print(f"  {len(paths)} record file(s), {len(grouped)} row group(s), "
          f"{len(multi_seed)} of them pooling more than one seed")
    if not multi_seed:
        print("  NOTHING TO CHECK YET: no row in this corpus pools multiple seeds. This audit is")
        print("  written for the production fleet, where every reported row is n=3, and it says so")
        print("  rather than printing a green it has not earned.")
        return 0
    if not mixed:
        print(f"  every multi-seed row agrees on all {len(CLOSURE_FIELDS)} closure fields")
        return 0
    # Separate the two, because they mean different things. An exploratory corpus SHOULD contain
    # rows built from several payloads -- that is what development looks like -- and reporting those
    # as findings would train a reader to ignore this audit by the time it matters.
    production = [item for item in mixed if kinds.get(item[0]) == "production"]
    exploratory = [item for item in mixed if kinds.get(item[0]) != "production"]
    if exploratory:
        print(f"  {len(exploratory)} mixed-closure group(s) among EXPLORATORY/probe records --")
        print("  expected, and not a finding: development runs legitimately span payloads.")
    if not production:
        print("  no PRODUCTION row mixes closures.")
        return 0
    print(f"  {len(production)} MIXED-CLOSURE finding(s) in PRODUCTION rows:")
    for key, field, values, files in production:
        baseline, regime, frame, _ = key
        print(f"    {baseline} / {regime} / frame {frame}: {field} differs across seeds")
        for value in sorted(str(v) for v in values):
            print(f"      {value[:64]}")
        print(f"      files: {', '.join(files)}")
    print("  A25/A24: seeds from different closures are different revisions and must not be pooled")
    print("  without explicit treatment. Rerun under one closure, or report them separately.")
    return 1 if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
