"""populate_evaluator_ledger.py must never write an entry production_gates.py would reject.

[Claude 2026-09-17] Each run replaces the family's entry, so a rejected write REMOVES a valid
attestation, and nothing errors. That is how idaac and ppg lost theirs: the entries were rewritten
from curve sweeps (`reeval-v214-idaac-s102-partial-curve`, `reeval-v214-ppg-curve`), and collecting
ibac_sni s101's production run later did the same to ibac_sni, taking the gate from 5/7 to 4/7.

Two rules were missing, and both are asserted here against real committed record files, via
--dry-run so the suite can never touch the ledger:
  1. a file with no endpoint-scope rows is refused (the gate requires eval_scope == endpoint);
  2. a file whose offline rows span more than one scope is refused (the gate requires EVERY row to
     share the entry's identity; a production endpoint runs two policy passes, a curve twelve
     frames) -- enforced by calling the gate's own _validation_entry_problem.
And the positive control, without which a script that refused everything would pass: a real
single-scope attestation file is accepted.
"""
import hashlib
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "populate_evaluator_ledger.py"
LEDGER = ROOT / "datasphere" / "native" / "validated_evaluator_families.json"


def _dry_run(family: str, job: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), family, job, "--dry-run"],
                          capture_output=True, text=True, cwd=ROOT)


def _need(job: str) -> None:
    if not (ROOT / "results" / "records" / f"{job}__records.jsonl").exists():
        pytest.skip(f"{job} records not present in this checkout")


def test_a_curve_only_sweep_is_refused_and_not_written():
    job = "reeval-v214-ppg-curve"
    _need(job)
    before = hashlib.sha256(LEDGER.read_bytes()).hexdigest()
    result = _dry_run("ppg", job)
    assert result.returncode != 0, "a curve-only file was accepted as endpoint attestation evidence"
    assert "no endpoint-scope" in result.stderr + result.stdout
    assert hashlib.sha256(LEDGER.read_bytes()).hexdigest() == before


def test_a_two_pass_production_endpoint_is_refused():
    """Rows 0-43 are the native pass and row 44 onward the mode pass; they differ in scope."""
    job = "reeval-v214-ppg-endpoint"
    _need(job)
    result = _dry_run("ppg", job)
    assert result.returncode != 0, "a multi-scope production file was accepted as evidence"
    assert "production_gates would reject" in result.stderr


def test_a_real_single_scope_attestation_is_accepted():
    """Positive control. Skipped, not failed, if the attestation has gone stale against the tree."""
    job = "attest-v212-ppg"
    _need(job)
    result = _dry_run("ppg", job)
    if "live tree is" in result.stdout + result.stderr:
        pytest.skip("attest-v212-ppg no longer matches the live evaluator revision")
    assert result.returncode == 0, (
        "the validator refused genuine attestation evidence -- a writer that refuses everything "
        f"would pass the two tests above:\n{result.stdout}\n{result.stderr}")
