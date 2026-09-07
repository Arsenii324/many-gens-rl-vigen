"""A job config that cannot run must be caught before it is submitted, not after it is billed.

Three jobs died on 2026-09-05 for reasons fully derivable from the tree: two asked for a tier below
their family's declared minimum (one SIGKILLed at 11.07 GiB), one named an evaluator family where a
baseline was required. `gate_scheduler_ram_invariant` passed throughout, because it checks that the
SUBMIT SCRIPT contains a memory check -- true, and irrelevant to a hand-written cfg sent straight to
`datasphere project job execute`.

Pins three things: the auditor rejects each defect, and `check_memory` no longer treats an unmeasured
family as a passing one.
"""
import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
NATIVE = ROOT / "datasphere" / "native"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def _family():
    sys.path.insert(0, str(NATIVE))
    return _load("_fam_audit", NATIVE / "family.py")


def test_an_unmeasured_family_is_not_certified(monkeypatch, tmp_path):
    """The defect that killed ctrl: `if peak is None: continue` then printing "memory ok".

    Written against a REAL family name twice (idaac, then dmc_gb) and both times the project's own
    progress overnight measured it, turning the test vacuous rather than failing loudly -- a chase
    that would repeat forever. Uses a synthetic descriptor instead, so certification coverage
    catching up with the test can never again be mistaken for the test catching a regression.
    """
    fam = _family()
    fake = {"_comment": "synthetic, for this test only",
            "phantom": {"baselines": ["phantom"], "production": {}}}
    fake_path = tmp_path / "families.json"
    fake_path.write_text(__import__("json").dumps(fake))
    with pytest.raises((ValueError, SystemExit)):
        fam.check_memory("phantom:1", "gt4.1", path=fake_path)           # dmc_gb has no fixed_peak_gib


def test_the_escape_hatch_makes_the_risk_explicit():
    # [Claude 2026-09-07] `frames` is explicit now. check_memory charges the replay allocation that
    # fixed_peak_gib excludes, and that charge is budget-dependent: at the 600k default a soda cell
    # needs 21.4 GiB and gt4.1's 14.5 correctly refuses it, which is a TIER verdict and not what
    # this test is about. The escape hatch is about an absent MEASUREMENT.
    _family().check_memory("soda:1", "gt4.1", allow_unmeasured=True, frames=10_000)


def test_a_production_scale_cell_is_refused_on_a_tier_its_replay_does_not_fit():
    """The other half of the same change, asserted rather than left implicit."""
    fam = _family()
    with pytest.raises((ValueError, SystemExit)):
        fam.check_memory("soda:1", "gt4.1", allow_unmeasured=True, frames=600_000)


def test_a_measured_family_that_does_not_fit_is_refused():
    fam = _family()
    with pytest.raises((ValueError, SystemExit)):
        fam.check_memory("alda:1", "gt4.1")           # 14.73 + 1.0 margin vs 14.5 usable


def test_ctrl_now_carries_the_peak_its_sigkill_measured():
    fam = _family()
    peak = (fam.production("ctrl") or {}).get("fixed_peak_gib")
    assert peak is not None, "the kill measured it; leaving it unrecorded repeats the failure"
    with pytest.raises((ValueError, SystemExit)):
        fam.check_memory("ctrl:1", "gt4.1")
    fam.check_memory("ctrl:1", "gt4i.1")


def test_a_family_name_is_not_a_valid_cell():
    audit = _load("_sub_audit", ROOT / "scripts" / "audit_submission_configs.py")
    baselines = audit.declared_baselines()
    assert "rlvigen" not in baselines, "rlvigen is a family; naming it as a cell cost a job"
    assert baselines.get("drqv2") == "rlvigen"


def test_every_live_config_passes_the_auditor():
    audit = _load("_sub_audit2", ROOT / "scripts" / "audit_submission_configs.py")
    assert audit.audit() == 0, "a live job config would die on submission"


def test_superseded_is_opt_in_so_forgetting_is_safe():
    audit = _load("_sub_audit3", ROOT / "scripts" / "audit_submission_configs.py")
    live = [p for p in sorted(NATIVE.glob("cfg-*functional-v11*.yaml"))
            if "# SUPERSEDED" not in p.read_text()]
    assert live, "the live validation configs must not be marked superseded"
    assert audit.is_submittable(live[0].read_text())
