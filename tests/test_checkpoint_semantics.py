"""The runbook's checkpoint-semantics table must stay derived, not hand-maintained.

The first hand-typed version of that table stated a seven-point curve density as though it applied
to all seven families, when only `rlvigen` sets `preserve_snapshots`. That is the drift this check
exists to prevent.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_checkpoint_semantics.py"


def test_runbook_block_matches_the_generated_table():
    result = subprocess.run([sys.executable, str(SCRIPT), "--check"],
                            capture_output=True, text=True, cwd=str(ROOT))
    assert result.returncode == 0, result.stdout + result.stderr


def test_source_evidence_for_every_checkpoint_claim_still_matches():
    """A clone edit that started persisting a replay buffer must fail this, not pass silently."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import audit_checkpoint_semantics as audit

    assert audit.check_evidence() == []


def test_off_policy_resume_is_not_advertised_as_a_full_restart():
    sys.path.insert(0, str(ROOT / "scripts"))
    import audit_checkpoint_semantics as audit

    by_family = {row["family"]: row for row in audit.rows()}
    for family in ("rlvigen", "dmc_gb", "alda"):
        assert "NOT a full restart" in by_family[family]["resume"]
    assert by_family["idaac"]["resume"] == "policy + observation statistics; no optimizer/RNG state"
    assert by_family["ppg"]["resume"] == "policy only; no optimizer/rollout state"
    assert by_family["ibac_sni"]["resume"] == "policy only; no optimizer/rollout state"
    assert by_family["ctrl"]["resume"] == "model + optimizer state; no environment/RNG state"
    assert "optional save_buffer" in by_family["alda"]["buffer"]
    assert all(audit.FAMILIES_META[family]["evidence"] for family in audit.FAMILIES_META)
    # On the v100 profile the fleet is uniform: twelve stamps plus the endpoint for everyone.
    # rlvigen's base 100000 is a DataSphere container-disk value its v100 profile overrides.
    assert by_family["rlvigen"]["curve_points"] == 13
    assert by_family["idaac"]["curve_points"] == 13
    assert audit.rows(profile=None)[0]["curve_points"] == 7, (
        "the base descriptor must still show rlvigen's DataSphere cadence -- the point is that the "
        "default resolves the production profile, not that the base value changed")


def test_trajectory_cost_is_derived_from_measured_rates_not_training_fps():
    """PRODUCTION-CALENDAR.md's trajectory term must come from this function, not from hand arithmetic.

    The hand-computed version drifted twice: it kept the superseded five-episode per-baseline hours
    (8.08 h/cell) beside an updated four-term table, and stated "12 stamps x 240 episodes" where the
    production grid is 120 per stamp.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_plan_production", ROOT / "datasphere" / "native" / "plan_production.py")
    plan = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plan)

    result = plan.curve_eval_hours(600_000, 3)
    rows = result["rows"]
    assert len(rows) == 12, "twelve baselines, and no invented thirteenth"
    for baseline, row in rows.items():
        assert row["stamps_evaluated"] == 13, f"{baseline}: v100 fleet cadence is 12 stamps + endpoint"
        assert row["episodes_per_stamp"] == 120, (
            f"{baseline}: 4 regimes x 10 scenes x 3 episodes, not the 240 the calendar once claimed")
    # [Claude 2026-09-07, updated later the same day] This asserted `not rows["soda"]["measured"]`,
    # which was true when written and stopped being true two hours later: the v176 wave's own logs
    # carried NATIVE_ENDPOINT_EVAL_SECONDS for all seven families, so the placeholder is gone
    # entirely. The assertion now pins the stronger property -- no family is estimated -- because
    # a silent return to the 30 s/episode default is the regression worth catching.
    assert all(row["measured"] for row in rows.values()), (
        [b for b, r in rows.items() if not r["measured"]])
    # gt4.1 basis, after converting the four gt4i.1 measurements by the 1.14 tier factor.
    assert 150 < result["total_hours"] < 185, result["total_hours"]
