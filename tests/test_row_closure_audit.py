"""A reported row must not pool seeds from two scientific closures.

External recommendation 22, item 15: "a rerun never silently incorporates a newly fixed tree."
Every record has carried `payload_sha256`, `requirements_native_sha256`, `container_image`,
`evaluator_revision` and `evaluator_scope_revision` for weeks. Nothing compared them across the
seeds of one row, so a row built from two payloads was fully detectable in the artifacts and
entirely invisible in practice.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts" / "audit_row_closure.py"


def _record(seed, payload, kind="production", **overrides):
    record = {
        "baseline": "drqv2", "regime": "train", "frame": 600000.0, "seed": seed,
        "evaluator_revision": "rev", "evaluator_scope_revision": "scope",
        "conventions": {"eval_policy_mode": "mode"},
        "_delivery_provenance": {"execution_kind": kind},
        "native": {"run_provenance": {"payload_sha256": payload,
                                      "requirements_native_sha256": "req",
                                      "container_image": "img"}},
    }
    record.update(overrides)
    return record


def _run(tmp_path, records, strict=False):
    directory = tmp_path / "records"
    directory.mkdir()
    (directory / "a__records.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records) + "\n")
    argv = [sys.executable, str(AUDIT), "--records", str(directory)]
    if strict:
        argv.append("--strict")
    return subprocess.run(argv, capture_output=True, text=True, cwd=str(ROOT))


def test_one_closure_across_three_seeds_passes(tmp_path):
    result = _run(tmp_path, [_record(s, "same-payload") for s in (1, 2, 3)])
    assert result.returncode == 0, result.stdout
    # The clean path reports agreement directly; the "no PRODUCTION row" line is the OTHER green,
    # reached when findings exist but all of them are exploratory.
    assert "agrees on all" in result.stdout, result.stdout


def test_a_row_built_from_two_payloads_is_caught(tmp_path):
    records = [_record(1, "payload-A"), _record(2, "payload-A"), _record(3, "payload-B")]
    result = _run(tmp_path, records, strict=True)
    assert result.returncode == 1, result.stdout
    assert "payload_sha256 differs across seeds" in result.stdout


def test_a_row_mixing_policy_modes_is_caught(tmp_path):
    """The UNITS split again: two seeds at the mode and one sampling is not one row."""
    records = [_record(1, "p"), _record(2, "p"),
               _record(3, "p", conventions={"eval_policy_mode": "sample"})]
    result = _run(tmp_path, records, strict=True)
    assert result.returncode == 1
    assert "eval_policy_mode differs across seeds" in result.stdout


def test_exploratory_rows_are_reported_separately_not_as_findings(tmp_path):
    """A development corpus SHOULD span payloads; calling that a finding trains readers to ignore
    the audit by the time it matters."""
    records = [_record(1, "payload-A", kind="exploratory"),
               _record(2, "payload-B", kind="exploratory")]
    result = _run(tmp_path, records, strict=True)
    assert result.returncode == 0, result.stdout
    assert "EXPLORATORY" in result.stdout
    assert "no PRODUCTION row mixes closures" in result.stdout


def test_single_seed_rows_do_not_claim_a_green_they_have_not_earned(tmp_path):
    result = _run(tmp_path, [_record(1, "p")])
    assert result.returncode == 0
    assert "NOTHING TO CHECK YET" in result.stdout
