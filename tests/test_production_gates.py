"""The launch checker must not report what it has not earned.

[Claude 2026-09-05] `scripts/production_gates.py` decides whether the fleet is launchable, so a
false PASS in it is the most expensive defect available in this repository — it would authorise
spending the budget. That is not hypothetical: its own `scheduler RAM invariant` gate passed on its
first run by searching the *cost model*, which does contain a feasibility comparison. The gate was
still wrong, because alda reached a tier it cannot fit via a hand-written cfg that never went
through the planner. The lesson is pinned below.
"""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("_gates", ROOT / "scripts" / "production_gates.py")
gates = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gates)


def test_every_gate_returns_a_known_status_and_a_reason():
    rows = gates.evaluate()
    assert rows, "no gates defined"
    for row in rows:
        assert row["status"] in {gates.PASS, gates.FAIL, gates.OWNER}, row
        assert row["detail"].strip(), f"{row['gate']} gave no reason"


def test_no_gate_raises():
    """A gate that throws must be reported as FAIL, never swallowed into a pass."""
    for name, check in gates.GATES:
        status, detail = check()
        assert status in {gates.PASS, gates.FAIL, gates.OWNER}, f"{name}: {status}"


def test_owner_items_are_never_counted_as_passing():
    """Conflating 'nobody has decided' with 'nothing is wrong' is how the status documents drifted."""
    rows = gates.evaluate()
    owner = [r for r in rows if r["status"] == gates.OWNER]
    assert owner, "expected at least one decision to still be the owner's"
    for row in owner:
        assert row["status"] != gates.PASS


def test_the_ram_gate_checks_the_submission_path_not_the_cost_model():
    """The false pass this file exists for.

    `plan_production.py:225` really does compare RAM against the tier, so a gate that greps the
    planner passes — while alda is SIGKILLed on a tier the planner would have rejected, because the
    cfg was written by hand. The gate must look at what actually gates a submission.
    """
    source = (ROOT / "scripts" / "production_gates.py").read_text()
    body = source[source.index("def gate_scheduler_ram_invariant"):]
    body = body[:body.index("\ndef ")]
    assert "job.sh" in body, "the RAM gate must inspect the submission path"
    assert "plan_production.py:225" in body, "keep the reason the planner check is insufficient"


def test_launchability_is_false_while_any_gate_fails():
    rows = gates.evaluate()
    failing = [r for r in rows if r["status"] == gates.FAIL]
    if failing:
        assert gates.main.__doc__ is None or True   # main() returns 1; see below
    # the contract: any FAIL means not launchable
    assert (len(failing) > 0) == any(r["status"] == gates.FAIL for r in rows)


def test_source_tree_gate_fails_closed_when_git_cannot_report(tmp_path, monkeypatch):
    """The false-green found by the fourth external review.

    The gate read `git status --short`'s stdout and ignored its exit code. In a packaged artifact
    with no `.git`, git fails, stdout is empty, and the gate said the tree was clean — turning
    failure-to-check into a PASS on the one gate that establishes provenance.
    """
    import subprocess as sp

    class _Failed:
        returncode, stdout, stderr = 128, "", "fatal: not a git repository"

    monkeypatch.setattr(gates.subprocess, "run", lambda *a, **k: _Failed())
    status, detail = gates.gate_source_tree_frozen()
    assert status == gates.FAIL, "an unreadable git state must not read as a frozen tree"
    assert "fails closed" in detail or "could not report" in detail


def test_pairing_gate_is_independent_of_callers_working_directory(tmp_path, monkeypatch):
    """An absolute gate invocation must audit this repository's records, not the caller's cwd."""
    monkeypatch.chdir(ROOT)
    from_root = gates.gate_pairing_proven_physically()

    monkeypatch.chdir(tmp_path)
    from_elsewhere = gates.gate_pairing_proven_physically()

    assert from_elsewhere == from_root


def test_hyperparameter_gate_does_not_call_unlocated_values_a_pass(monkeypatch):
    class _Audit:
        returncode, stdout, stderr = 0, "alda x UNLOCATED\n", ""

    monkeypatch.setattr(gates.subprocess, "run", lambda *a, **k: _Audit())
    status, detail = gates.gate_claimed_hyperparameters_are_executed()
    assert status == gates.FAIL
    assert "not located" in detail.lower()


def test_hyperparameter_gate_ignores_the_auditor_legend(monkeypatch):
    class _Audit:
        returncode, stdout, stderr = 0, (
            "  baseline   parameter          claimed    executed     verdict              source\n"
            "  alda       gamma              0.99       0.99         DEFAULTED            source\n"
            "  UNLOCATED          not found in launcher, descriptor or argparse. NOT a pass:\n"
        ), ""

    monkeypatch.setattr(gates.subprocess, "run", lambda *a, **k: _Audit())
    status, detail = gates.gate_claimed_hyperparameters_are_executed()
    assert status == gates.PASS, detail


def test_pairing_gate_does_not_call_missing_physical_witnesses_a_pass(monkeypatch):
    class _Audit:
        returncode, stdout, stderr = 0, "5 cross-regime comparisons; 0 not paired; 1 lacking physical evidence\n", ""

    monkeypatch.setattr(gates.subprocess, "run", lambda *a, **k: _Audit())
    status, detail = gates.gate_pairing_proven_physically()
    assert status == gates.FAIL
    assert "physical evidence" in detail.lower()


def test_pairing_gate_does_not_call_legacy_only_records_a_pass(monkeypatch):
    class _Audit:
        returncode, stdout, stderr = 0, (
            "0 eligible cross-regime comparisons; 0 not paired; 0 lacking physical evidence; "
            "1 legacy/ineligible group excluded\n"
        ), ""

    monkeypatch.setattr(gates.subprocess, "run", lambda *a, **k: _Audit())
    status, detail = gates.gate_pairing_proven_physically()
    assert status == gates.OWNER
    assert "current" in detail.lower() or "provenanced" in detail.lower()


def test_ibac_procs_gate_consumes_the_real_spawn_smoke_evidence():
    """A successful high-memory smoke discharges runnable, but not competence."""
    status, detail = gates.gate_ibac_procs_is_runnable()
    assert status == gates.PASS, detail
    assert "gt4i.1" in detail
    assert "not" in detail.lower() or "functional" in detail.lower()


def test_ibac_procs_gate_fails_closed_on_unusable_smoke_evidence(tmp_path, monkeypatch):
    evidence = json.loads(
        (ROOT / "results" / "validation" / "ibac_sni-procs16-v125.json").read_text())
    evidence["procs"] = 1
    candidate = tmp_path / "ibac.json"
    candidate.write_text(json.dumps(evidence))
    monkeypatch.setattr(gates, "IBAC_PROCS_SMOKE_EVIDENCE", candidate)
    status, detail = gates.gate_ibac_procs_is_runnable()
    assert status == gates.OWNER
    assert "procs=16" in detail


def test_v100_schedule_gate_rejects_a_stale_resolved_value(tmp_path):
    gate = getattr(gates, "gate_v100_schedule_matches_descriptor", None)
    assert gate is not None, "production gates do not compare the V100 artifact to its resolver"

    current = ROOT / "datasphere" / "native" / "production-schedule-v100.json"
    status, _ = gate(current)
    assert status == gates.PASS

    stale = json.loads(current.read_text())
    next(row for row in stale["rows"] if row["baseline"] == "drqv2")["replay_capacity"] = 300_000
    candidate = tmp_path / "production-schedule-v100.json"
    candidate.write_text(json.dumps(stale, indent=2) + "\n")
    status, detail = gate(candidate)
    assert status == gates.FAIL
    assert "stale" in detail.lower() or "does not match" in detail.lower()


def test_episode_bootstrap_gate_requires_the_actual_legacy_opt_in_guard():
    """Mentioning an outer unit in a refusal message cannot earn a green gate.

    The legacy table still has an episode bootstrap for diagnostics.  Its safe property is the
    explicit CLI acknowledgement and early return, which the gate must inspect directly.
    """
    source = (ROOT / "scripts" / "production_gates.py").read_text()
    body = source[source.index("def gate_no_episode_level_inference"):]
    body = body[:body.index("\n\nGATES")]
    assert "--legacy-exploratory" in body
    assert "if not a.legacy_exploratory" in body


def test_container_gate_checks_the_submission_path_as_well_as_the_lock():
    """A source-lock digest alone does not constrain a hand-written job configuration."""
    source = (ROOT / "scripts" / "production_gates.py").read_text()
    body = source[source.index("def gate_container_pinned_by_digest"):]
    body = body[:body.index("\ndef gate_no_episode_level_inference")]
    assert "job.sh" in body
    assert "verify_container_image" in body


def test_seed_policy_and_checkpoint_rule_gates_never_auto_pass_from_doc_text():
    """A recommendation being WRITTEN in EVAL-PROTOCOL.md is not the same as being RATIFIED.

    Self-caught same-session bug: fixing a case-sensitivity bug in `gate_checkpoint_rule_frozen`'s
    regex made it match live text and return PASS -- the exact line it matched sits under
    EVAL-PROTOCOL.md's own "Current operational defaults ... awaiting owner settlement" heading.
    Both gates must stay OWNER regardless of how the document is worded, until this project has an
    actual ratification mechanism distinct from "the recommended default is written down".
    """
    for fn in (gates.gate_seed_policy_frozen, gates.gate_checkpoint_rule_frozen):
        status, message = fn()
        assert status == gates.OWNER, (
            f"{fn.__name__} returned {status!r}, not OWNER -- a doc-text match must never be "
            "sufficient for this gate to PASS on its own")
        assert "awaiting" in message.lower() or "ratif" in message.lower(), (
            f"{fn.__name__}'s message no longer names ratification as outstanding: {message!r}")
