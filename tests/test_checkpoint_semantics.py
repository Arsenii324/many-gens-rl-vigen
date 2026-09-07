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
    for family in ("idaac", "ppg", "ctrl", "ibac_sni"):
        assert by_family[family]["resume"] == "effectively complete"
    assert by_family["rlvigen"]["curve_points"] == 7
    assert by_family["idaac"]["curve_points"] == 13
