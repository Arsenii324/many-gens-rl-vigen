"""R6's evidence must not rot: every baseline's distinctive mechanism stays locatable.

[Claude 2026-09-04] `scripts/audit_implementations.py` answers R6 -- "are all twelve genuine
implementations" -- by requiring each algorithm's distinctive mechanism to be DEFINED in the clone
and to ACTUALLY EXECUTE at the budget being reported. Its weakness is its markers: a renamed symbol
turns a working baseline into a false NOT DEFINED, and three of twelve markers were wrong on the
first run (drqv2's n-step lives in the cfg, SVEA is written unbatched so there is no `svea_alpha`,
RAD's crop is in the replay buffer and `rad.py` overrides nothing). A false verdict from an audit
is worse than no audit, so the markers are pinned here.
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("_audit", ROOT / "scripts" / "audit_implementations.py")
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)

_ASSET_PRESENT = audit.ASSET.is_file()


def test_all_twelve_are_covered():
    assert len(audit.MECHANISMS) == 12
    assert len({m[0] for m in audit.MECHANISMS}) == 12


@pytest.mark.parametrize("row", audit.audit(600_000), ids=lambda r: r["baseline"])
def test_every_mechanism_resolves_and_is_genuine_at_the_production_budget(row):
    if row["verdict"] == "UNRESOLVED" and "asset:" in row["where"] and not _ASSET_PRESENT:
        pytest.skip("RL-ViGen asset archive not present on this machine")
    assert row["verdict"].startswith("GENUINE"), (
        f"{row['baseline']}: {row['verdict']} -- {row['note']}\n"
        "Either the clone lost its mechanism, or this audit's marker went stale. Both matter; "
        "check the source before changing the marker.")


def test_ppg_is_not_ppg_below_its_auxiliary_phase():
    """The finding this audit exists for, pinned as a fact about the budget.

    PPG's auxiliary phase runs when `curr_iteration >= n_pi` (n_pi=32) and an iteration is 2048
    interacts, so it first fires at 65,536 frames. Every ppg number this project holds came from a
    10,000-frame run: those runs executed the auxiliary phase zero times and are PPO exactly.
    """
    short = {r["baseline"]: r for r in audit.audit(10_000)}["ppg"]
    assert short["verdict"] == "DEFINED, NEVER RUNS", short
    at_floor = {r["baseline"]: r for r in audit.audit(65_536)}["ppg"]
    assert at_floor["verdict"].startswith("GENUINE"), at_floor
    assert "activates 1x" in {r["baseline"]: r for r in audit.audit(100_000)}["ppg"]["note"]
