#!/usr/bin/env python3
"""Rebuild a delivery bundle for a cell that was reaped before it could assemble its own.

    python scripts/assemble_reaped_delivery.py <fetched-run-dir> --out <bundle.jsonl>

## Why this is needed

`collect_record_delivery` runs **after** evaluation. A cell whose watch expires mid-evaluation has
written every row it produced -- the evaluators append as they go -- and assembled none of them.
`collect-host-run.sh` then refuses, correctly: there is no bundle. The measurements are not lost,
they are unassembled, and the difference is worth a tool rather than an afternoon.

This was not hypothetical when it was written. `EVAL_ALLOWANCE` defaulted to the *training* budget
and was 69% short (`launch-card-cell.sh`, fixed 2026-09-09), so `card0-20260909-035152` is projected
to reach its reaper roughly thirty rows into a second endpoint pass. Earlier cells ran under the same
short allowance.

## What it refuses to do

**It never presents an assembled bundle as a delivered one.** Every row gets
`_assembled_after_reaping`, carrying the reason and the source file, so a row that came home through
this path can always be told from one the runner produced. A record that could not be produced
normally must never read as one that was.

**It does not invent provenance.** `collect_record_delivery` enriches offline rows with
`_run_provenance` from `run_manifest.json`. When that file is present it is attached identically;
when it is absent -- and on the production host it is **not readable by the fetching account**, so
this is the normal case, not the exception -- rows are marked `_run_provenance_missing` rather than
shipped as though they had it. The runner's own rule is that an unprovenanced row is a finding and
not a reason to discard a run.

**It does not decide the cell succeeded.** It assembles what exists and reports what is missing. A
partial second policy-mode pass stays partial and is counted per `(frame, regime, eval_policy_mode)`
so the gap is visible in the output rather than inferred later from a row count.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys


def _rows(path: pathlib.Path) -> list[dict]:
    out = []
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def sources(root: pathlib.Path) -> list[pathlib.Path]:
    """The same set `collect_record_delivery` concatenates, in the same order."""
    found = [root / "native-out" / "records.jsonl"]
    found += sorted((root / "native-out").glob("offline_eval_*.jsonl"))
    found += sorted((root / "native-out").glob("cells/*/offline_eval_*.jsonl"))
    return [p for p in found if p.is_file() and p.stat().st_size > 0]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run_dir")
    ap.add_argument("--out", required=True)
    ap.add_argument("--reason", default="cell reaped before collect_record_delivery ran")
    args = ap.parse_args()

    root = pathlib.Path(args.run_dir)
    if not root.is_dir():
        print(f"not a directory: {root}")
        return 2

    delivered = root / "native-out" / "records_delivery.jsonl"
    if delivered.is_file() and delivered.stat().st_size > 0:
        print(f"REFUSING: {delivered} already exists with "
              f"{len(_rows(delivered))} rows. The runner assembled its own bundle; use that.")
        print("Assembling a second one beside it would put two answers in the tree.")
        return 1

    manifest_path = root / "native-out" / "run_manifest.json"
    manifest = None
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text())
        except (OSError, ValueError):
            manifest = None

    src = sources(root)
    if not src:
        print(f"No record sources under {root}. Nothing to assemble, which is NOT the same as")
        print("nothing having been measured -- check that the fetch included cells/*/.")
        return 2

    out_rows: list[dict] = []
    per_file: list[tuple[str, int]] = []
    for path in src:
        rows = _rows(path)
        per_file.append((str(path.relative_to(root)), len(rows)))
        for row in rows:
            row["_assembled_after_reaping"] = {
                "reason": args.reason,
                "source": str(path.relative_to(root)),
                "tool": "scripts/assemble_reaped_delivery.py",
            }
            if "offline_eval_" in path.name:
                if manifest is not None:
                    row.setdefault("_run_provenance", manifest)
                else:
                    row["_run_provenance_missing"] = (
                        "run_manifest.json absent or unreadable at assembly time; the runner would "
                        "have attached it. This row is auditable for its own content but not for "
                        "the job that produced it.")
            out_rows.append(row)

    out_path = pathlib.Path(args.out)
    with out_path.open("w") as fh:
        for row in out_rows:
            fh.write(json.dumps(row) + "\n")

    print(f"ASSEMBLED {len(out_rows)} row(s) -> {out_path}\n")
    for name, n in per_file:
        print(f"  {n:>5}  {name}")
    print()
    if manifest is None:
        print("  NO run_manifest.json: every offline row carries `_run_provenance_missing`.")
        print("  On the production host that file is not readable by the fetching account, so this")
        print("  is the normal case. The rows are usable; the JOB behind them is not independently")
        print("  auditable from this bundle alone.\n")

    coverage: dict[tuple, int] = collections.Counter()
    for row in out_rows:
        scope = row.get("evaluator_scope") or {}
        coverage[(row.get("frame"), row.get("phase"), scope.get("eval_policy_mode"))] += 1
    print("  coverage by (frame, phase, policy mode) -- a short cell shows its gap here:")
    for key, n in sorted(coverage.items(), key=lambda kv: str(kv[0]))[:20]:
        print(f"    {str(key):<52} {n:>4} row(s)")
    print()
    print("  EVERY ROW IS MARKED `_assembled_after_reaping`. This bundle is not a delivered one and")
    print("  must never be filed as though the runner produced it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
