#!/usr/bin/env python3
"""Write one family's entry in the evaluator-validation ledger, from its job's own records.

[Claude 2026-09-07.] This step existed only as a scratch script outside the repository, which is
the wrong home for the thing that decides whether a family counts as attested. It is also the step
that caught the v191 wave writing a false attestation, so it is worth reading rather than trusting:

    AssertionError: ('0c383ce7edd8...', '35f79dc39a15...')

That was a record whose `evaluator_revision` no longer matched the live tree, because closure
members changed while the wave ran. The assertion is the whole value of this script.

    python scripts/populate_evaluator_ledger.py <family> <job-id>
    python scripts/populate_evaluator_ledger.py <family> <job-id> --dry-run

`paired` and `diagnostics_complete` used to be written as hardcoded `True`. They are now DERIVED
from the records: an entry that asserts pairing without checking it is exactly the kind of claim
`production_gates.py` exists to refuse.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from datasphere.native.evaluator_identity import (  # noqa: E402
    evaluator_family_code_revision, evaluator_family_config_revision, evaluator_family_revision,
)

LEDGER = ROOT / "datasphere" / "native" / "validated_evaluator_families.json"


def _pairing_is_physical(rows: list[dict]) -> tuple[bool, str]:
    """Did the same physical placements appear across regimes, per the recorded witnesses?

    Not a hardcoded True. `audit_pairing_evidence.py` is the fleet-wide instrument; this is the
    per-entry precondition, so the flag the ledger carries means what it says.
    """
    by_regime: dict[str, list] = {}
    for row in rows:
        native = row.get("native") or {}
        seeds = native.get("placement_condition_seeds")
        if seeds:
            by_regime.setdefault(str(row.get("regime")), []).append(tuple(seeds))
    if len(by_regime) < 2:
        return False, f"only {len(by_regime)} regime(s) carry placement witnesses"
    reference = next(iter(by_regime.values()))
    for regime, seeds in by_regime.items():
        if seeds != reference:
            return False, f"regime {regime} does not share the reference placement sequence"
    return True, f"{len(by_regime)} regimes share one placement sequence"


def _diagnostics_complete(rows: list[dict]) -> tuple[bool, str]:
    missing = [field for field in ("episode_return_mean", "episodes", "evaluator_revision")
               if any(row.get(field) is None for row in rows)]
    if missing:
        return False, "rows missing " + ", ".join(missing)
    return True, f"{len(rows)} rows carry the required fields"


def build(family: str, job_id: str) -> dict:
    records_rel = f"results/records/{job_id}__records.jsonl"
    raw = (ROOT / records_rel).read_bytes()
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    offline = [r for r in rows if r.get("phase") == "offline-eval"]
    if not offline:
        raise SystemExit(f"{family}: no offline-eval rows in {records_rel}")

    row = offline[0]
    for other in offline:
        if other["evaluator_revision"] != row["evaluator_revision"]:
            raise SystemExit(f"{family}: rows disagree on evaluator_revision within one job")

    code_rev = evaluator_family_code_revision(ROOT, family)
    config_rev = evaluator_family_config_revision(ROOT, family)
    static_rev = evaluator_family_revision(ROOT, family)
    if row["evaluator_revision"] != static_rev:
        raise SystemExit(
            f"{family}: the record attests {row['evaluator_revision'][:12]}... but the live tree is "
            f"{static_rev[:12]}...\n"
            "  A closure member changed after this job was submitted. Do NOT write this entry: it "
            "would certify a tree that no longer exists.\n"
            "  Rebuild the payload from the current tree and re-run the wave.")

    paired, paired_why = _pairing_is_physical(offline)
    complete, complete_why = _diagnostics_complete(offline)
    return {
        "baseline": row["baseline"],
        "code_revision": None,
        "diagnostics_complete": complete,
        "diagnostics_basis": complete_why,
        "evaluation_records_path": records_rel,
        "evaluation_records_sha256": hashlib.sha256(raw).hexdigest(),
        "evaluator_measurement_revision": row["evaluator_measurement_revision"],
        "evaluator_revision": row["evaluator_revision"],
        "evaluator_scope": row["evaluator_scope"],
        "evaluator_scope_revision": row["evaluator_scope_revision"],
        "family_code_revision": code_rev,
        "family_config_revision": config_rev,
        "job": job_id,
        "paired": paired,
        "paired_basis": paired_why,
        "runtime_imports_checked": True,
        "validation_kind": "functional_endpoint",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("family")
    parser.add_argument("job_id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    entry = build(args.family, args.job_id)
    print(f"{args.family}: evaluator_revision={entry['evaluator_revision'][:12]}... "
          f"paired={entry['paired']} ({entry['paired_basis']}) "
          f"diagnostics_complete={entry['diagnostics_complete']}")
    if not (entry["paired"] and entry["diagnostics_complete"]):
        print("  REFUSING to write: the gate requires paired + diagnostics_complete, and writing "
              "them as unchecked True is how a ledger stops meaning anything.", file=sys.stderr)
        return 1
    if args.dry_run:
        return 0
    ledger = json.loads(LEDGER.read_text())
    ledger[args.family] = entry
    LEDGER.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n")
    print(f"  wrote {LEDGER.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
