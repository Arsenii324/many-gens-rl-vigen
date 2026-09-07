"""The ledger writer must refuse a stale record, and must not invent its own flags.

This step caught the v191 wave writing a false attestation: four jobs returned SUCCESS whose
`evaluator_revision` no longer matched the live tree, because closure members changed while the
wave ran. Had it trusted the job status, the ledger would have claimed seven attestations against
code that is not there.

It also used to write `paired` and `diagnostics_complete` as hardcoded `True`. An entry that
asserts pairing without checking it is the kind of claim `production_gates.py` exists to refuse.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "populate_evaluator_ledger.py"


def _rows(revision: str, *, paired: bool = True, complete: bool = True) -> list[dict]:
    def row(regime, seeds):
        entry = {
            "phase": "offline-eval", "baseline": "idaac", "regime": regime,
            "evaluator_revision": revision, "evaluator_measurement_revision": "m",
            "evaluator_scope": {"family": "idaac"}, "evaluator_scope_revision": "s",
            "episode_return_mean": 1.0, "episodes": 5,
            "native": {"placement_condition_seeds": seeds},
        }
        if not complete:
            entry["episode_return_mean"] = None
        return entry
    return [row("train", [1, 2, 3]), row("eval-easy", [1, 2, 3] if paired else [9, 9, 9])]


def _run(tmp_path, rows, job="jobid"):
    records = ROOT / "results" / "records" / f"{job}__records.jsonl"
    records.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    try:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "idaac", job, "--dry-run"],
            capture_output=True, text=True, cwd=str(ROOT))
    finally:
        records.unlink(missing_ok=True)


def _live_revision() -> str:
    sys.path.insert(0, str(ROOT))
    from datasphere.native.evaluator_identity import evaluator_family_revision
    return evaluator_family_revision(ROOT, "idaac")


def test_a_stale_record_is_refused_not_written(tmp_path):
    result = _run(tmp_path, _rows("0" * 64))
    assert result.returncode != 0
    assert "certify a tree that no longer exists" in result.stderr + result.stdout


def test_unpaired_records_do_not_produce_a_paired_entry(tmp_path):
    result = _run(tmp_path, _rows(_live_revision(), paired=False))
    assert result.returncode != 0, "an unpaired family must not be written as paired"
    assert "paired=False" in result.stdout


def test_incomplete_diagnostics_are_refused(tmp_path):
    result = _run(tmp_path, _rows(_live_revision(), complete=False))
    assert result.returncode != 0
    assert "diagnostics_complete=False" in result.stdout


def test_a_current_paired_complete_record_is_accepted(tmp_path):
    result = _run(tmp_path, _rows(_live_revision()))
    assert result.returncode == 0, result.stderr
    assert "paired=True" in result.stdout and "diagnostics_complete=True" in result.stdout
