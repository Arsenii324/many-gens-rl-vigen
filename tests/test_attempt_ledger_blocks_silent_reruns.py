"""The attempt ledger must block exactly one thing, and must be clearable.

`scripts/audit_attempt_ledger.py --strict` is a gating audit. Its job is to make "a rerun never
silently replaces a failed seed" a record rather than a habit. Two ways to get that wrong, and the
first draft of this audit had the second:

  - too loose: a resubmission whose predecessor's outcome nobody can read passes, and which
    attempt produced the reported number is unknowable afterwards;
  - too tight: it blocks on the attempt that is still RUNNING, so the gate is red for the whole
    duration of every wave and there is no way to clear a job that failed before writing records.
    A rule that cannot be satisfied is not a safeguard -- people route around it.

The escape for a genuinely failed attempt is `results/attempt-outcomes.json`, and it is deliberately
narrow: terminal FAILURE states only, a reason required, every entry printed on every run. A result
must still come from records, so `ELIGIBLE` cannot be asserted by hand.

These run the real script against a temporary ledger rather than restating its logic.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts" / "audit_attempt_ledger.py"
LEDGER = ROOT / "results" / "submissions.jsonl"
OUTCOMES = ROOT / "results" / "attempt-outcomes.json"


@pytest.fixture
def ledger():
    """Writes the real paths, because the audit reads them -- so it must restore them."""
    saved = {p: (p.read_text() if p.is_file() else None) for p in (LEDGER, OUTCOMES)}
    try:
        yield lambda rows: LEDGER.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    finally:
        for path, text in saved.items():
            if text is None:
                path.unlink(missing_ok=True)
            else:
                path.write_text(text)


def _strict() -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(AUDIT), "--strict"],
                          cwd=str(ROOT), capture_output=True, text=True, timeout=300)


TWICE = [
    {"job_id": "bt1probeaaa", "config": "cfg-probe.yaml", "name": "p", "tier": "gt4.1"},
    {"job_id": "bt1probebbb", "config": "cfg-probe.yaml", "name": "p", "tier": "gt4.1"},
]


def test_a_rerun_over_an_unresolved_predecessor_is_refused(ledger):
    ledger(TWICE)
    OUTCOMES.unlink(missing_ok=True)
    assert _strict().returncode == 1, "a predecessor with no readable outcome must block"


def test_recording_the_predecessors_failure_clears_it(ledger):
    ledger(TWICE)
    OUTCOMES.write_text(json.dumps(
        {"bt1probeaaa": {"state": "FAILED-TRAIN", "reason": "OOM at 40k, log line 812"}}))
    done = _strict()
    assert done.returncode == 0, done.stdout[-1500:]
    assert "FAILED-TRAIN" in done.stdout and "OOM at 40k" in done.stdout, (
        "using the escape must be visible in the report, not quiet")


def test_a_result_cannot_be_asserted_by_hand(ledger):
    """ELIGIBLE is not in RECORDABLE: a reported number must come from records."""
    ledger(TWICE)
    OUTCOMES.write_text(json.dumps(
        {"bt1probeaaa": {"state": "ELIGIBLE", "reason": "trust me"}}))
    assert _strict().returncode == 1, "an operator must not be able to declare an attempt eligible"


def test_the_running_attempt_itself_is_not_flagged(ledger):
    """Otherwise the gate is red for the whole duration of every wave."""
    ledger(TWICE)
    OUTCOMES.write_text(json.dumps(
        {"bt1probeaaa": {"state": "CANCELLED", "reason": "superseded by the v197 payload"}}))
    assert _strict().returncode == 0, "only a PREDECESSOR's unknown outcome may block"


def test_a_single_attempt_per_config_never_blocks(ledger):
    ledger([TWICE[0]])
    OUTCOMES.unlink(missing_ok=True)
    assert _strict().returncode == 0
