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

    # [Claude 2026-09-17] Staleness is checked BEFORE the endpoint-scope requirement below. A record
    # that certifies a tree which no longer exists is the more fundamental error and the more
    # actionable message ("rebuild the payload and re-run the wave"); reporting "no endpoint rows"
    # for a stale curve file would send the reader after the wrong thing. Found when the scope check,
    # added earlier the same day, started pre-empting the staleness test.
    code_rev = evaluator_family_code_revision(ROOT, family)
    config_rev = evaluator_family_config_revision(ROOT, family)
    static_rev = evaluator_family_revision(ROOT, family)
    if offline[0]["evaluator_revision"] != static_rev:
        raise SystemExit(
            f"{family}: the record attests {offline[0]['evaluator_revision'][:12]}... but the live tree is "
            f"{static_rev[:12]}...\n"
            "  A closure member changed after this job was submitted. Do NOT write this entry: it "
            "would certify a tree that no longer exists.\n"
            "  Rebuild the payload from the current tree and re-run the wave.")

    # [Claude 2026-09-17] The attesting row must be an ENDPOINT row, and this used to take offline[0].
    # The entry below is `validation_kind: functional_endpoint`, and production_gates.py:269 rejects
    # any entry whose evaluator_scope is not `eval_scope == "endpoint"`. That held while attestation
    # jobs emitted endpoint rows only. A production delivery runs its curve grid FIRST, so offline[0]
    # is a curve row -- and a curve-only sweep file has no endpoint row at all.
    #
    # The failure was silent and cumulative, because every run of this script overwrites the family's
    # entry and the most recent one wins. Measured on 2026-09-17: idaac's entry had been rewritten
    # from `reeval-v214-idaac-s102-partial-curve` (a curve file, from a SUPERSEDED trajectory) and
    # ppg's from `reeval-v214-ppg-curve`; both read "evaluator_scope is not an endpoint scope". Then
    # collecting ibac_sni s101's production run took ibac_sni from validated to invalid the same way,
    # dropping the gate from 5/7 to 4/7. Nothing errored at any point.
    #
    # So: choose an endpoint row, preferring the family's native policy pass over the `mode` pass
    # (earlier attestations were native), and REFUSE when there is no endpoint row. Refusing keeps an
    # existing valid attestation in place; silently writing a curve row is what removed three.
    # [Claude 2026-09-17] build() no longer RAISES when there is no endpoint row. It reports the
    # fact and lets main() refuse in a deliberate order: staleness first, then paired/diagnostics,
    # then scope. Raising here pre-empted the pairing and diagnostics messages, so a record that was
    # both unpaired AND curve-only reported the scope problem and hid the pairing one.
    endpoint = [r for r in offline if (r.get("evaluator_scope") or {}).get("eval_scope") == "endpoint"]
    native = [r for r in endpoint if (r.get("evaluator_scope") or {}).get("eval_policy_mode") != "mode"]
    row = (native or endpoint or offline)[0]
    for other in offline:
        if other["evaluator_revision"] != row["evaluator_revision"]:
            raise SystemExit(f"{family}: rows disagree on evaluator_revision within one job")

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
        "_endpoint_rows": len(endpoint),
        "_offline_rows": len(offline),
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
    # [Claude 2026-09-17] Validate the candidate with the GATE'S OWN check before writing it. This
    # script and production_gates.py used to judge an entry by different rules, so it wrote entries
    # the gate then rejected -- and because each write replaces the family's entry, a rejected write
    # REMOVES a valid attestation. Selecting an endpoint row (above) was necessary and not
    # sufficient: the gate also requires EVERY offline-eval row in the evidence file to share one
    # scope and one measurement revision. A production delivery never does -- its curve spans twelve
    # frames and its endpoint runs two policy passes -- so a production file can never be attestation
    # evidence, by the gate's design. Writing one anyway took ibac_sni from validated to
    # "offline-eval row 44 disagrees with ledger identity" on 2026-09-17.
    #
    # Importing the gate's function rather than re-implementing its rules is the point: two copies of
    # one rule will disagree, and this script's copy was the one that drifted.
    if not entry.pop("_endpoint_rows", 0):
        n = entry.pop("_offline_rows", 0)
        print(f"  REFUSING to write: {n} offline-eval row(s) and NONE is endpoint-scope. This entry is\n"
              "  a functional_endpoint attestation and production_gates rejects any other scope.\n"
              "  Overwriting the family's current entry with a curve row would un-validate it\n"
              "  silently -- which is exactly what happened to idaac and ppg. Populate from the\n"
              "  run's ENDPOINT records instead.", file=sys.stderr)
        return 1
    entry.pop("_offline_rows", None)

    sys.path.insert(0, str(ROOT / "scripts"))
    from production_gates import _validation_entry_problem  # noqa: E402
    problem = _validation_entry_problem(
        ROOT, args.family, entry, entry["family_code_revision"],
        entry["family_config_revision"], entry["evaluator_revision"])
    if problem:
        print(f"  REFUSING to write: production_gates would reject this entry -- {problem}.\n"
              "  The family's CURRENT entry is left untouched. Writing this one would replace a\n"
              "  possibly-valid attestation with one the gate rejects. Attestation evidence must be a\n"
              "  single-scope evaluation (one frame, one policy pass), such as an attest-v2xx job;\n"
              "  a production run's records never are.", file=sys.stderr)
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
