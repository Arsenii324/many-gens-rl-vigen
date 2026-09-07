"""Every audit is either consulted by a gate or explicitly declared descriptive.

Seventeen audits existed and ten were standalone. Two of those ten -- `audit_row_closure` and
`audit_observation_geometry` -- were exactly the checks a release needs, and `audit_row_closure`
could not fail at all until 2026-09-07 because it compared `execution_kind` against a string
`contract.py` cannot emit. An audit nobody runs is an unread opinion; an audit nobody runs AND
that cannot fail is decoration.

So the classification is made TOTAL here rather than maintained by memory: a new
`scripts/audit_*.py` that lands in neither set fails this test, which forces the question "should
a release consult this?" at the moment the audit is written.
"""
from __future__ import annotations

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def _gates():
    spec = importlib.util.spec_from_file_location(
        "_production_gates_for_audit_classification", SCRIPTS / "production_gates.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_audit_script_is_classified():
    gates = _gates()
    present = {path.name for path in SCRIPTS.glob("audit_*.py")}
    classified = set(gates.GATING_AUDITS) | set(gates.DESCRIPTIVE_AUDITS)
    unclassified = sorted(present - classified)
    assert not unclassified, (
        f"{unclassified} is neither consulted by a gate (GATING_AUDITS) nor declared an inventory "
        "(DESCRIPTIVE_AUDITS). Decide which: an audit a release never runs is an unread opinion.")
    stale = sorted(classified - present)
    assert not stale, f"{stale} is classified but no longer exists"


def test_gating_audits_can_actually_fail():
    """A gate consulting an audit that cannot return non-zero certifies nothing."""
    gates = _gates()
    for name in gates.GATING_AUDITS:
        text = (SCRIPTS / name).read_text()
        assert any(token in text for token in ("return 1", "sys.exit(1)", "SystemExit(1)")), (
            f"{name} is gated but has no failing path; either give it one or move it to "
            "DESCRIPTIVE_AUDITS. This is the audit_row_closure defect: gated, and unable to fail.")


def test_each_gating_audit_states_the_question_it_answers():
    gates = _gates()
    for name, question in gates.GATING_AUDITS.items():
        assert question and len(question) > 20, (
            f"{name} needs a stated question, so a reader of a FAIL line knows what went unchecked")
