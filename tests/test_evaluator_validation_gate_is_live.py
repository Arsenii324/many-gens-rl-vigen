"""`gate_shared_evaluator_validated` must track the world, not repeat one string forever.

The gate used to hardcode "ZERO of twelve evaluator burdens are discharged", unconditionally --
which is the exact failure mode this project has fixed seven times elsewhere: an instrument whose
verdict does not depend on what actually happened. It stayed wrong through two rewrites because
nobody could prove it wrong without re-deriving the whole validation history by hand.

This pins three behaviors against a scratch ledger, so a future edit that reintroduces a hardcoded
verdict fails immediately rather than being trusted for another day.
"""
import importlib.util
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
LEDGER = ROOT / "datasphere" / "native" / "validated_evaluator_families.json"


def _gates():
    spec = importlib.util.spec_from_file_location("_pg_eval", ROOT / "scripts" / "production_gates.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["_pg_eval"] = m
    spec.loader.exec_module(m)
    return m


def _current_revisions(family):
    sys.path.insert(0, str(ROOT))
    from scripts.eval_provenance import (evaluator_family_code_revision,
                                         evaluator_family_config_revision)
    return (evaluator_family_code_revision(ROOT, family),
            evaluator_family_config_revision(ROOT, family))


def test_the_ledger_is_well_formed():
    """Structure check only -- NOT a completeness claim. ppg/ibac_sni may genuinely be absent
    while their validation jobs are still in flight; that is real, current state, not a defect."""
    ledger = json.loads(LEDGER.read_text())
    gates = _gates()
    for key in ledger:
        if key.startswith("_"):
            continue
        assert key in gates.EVALUATOR_FAMILIES, f"'{key}' in the ledger is not a known family"
    for family, entry in ledger.items():
        if family.startswith("_"):
            continue
        assert {"job", "family_code_revision", "family_config_revision",
                "runtime_imports_checked", "paired", "diagnostics_complete"} <= entry.keys()


def _with_fake_ledger(gates, monkeypatch, fake: dict):
    real_read_text = pathlib.Path.read_text

    def patched(self, *a, **k):
        if self.name == "validated_evaluator_families.json":
            return json.dumps(fake)
        return real_read_text(self, *a, **k)

    monkeypatch.setattr(pathlib.Path, "read_text", patched)


def test_a_stale_revision_entry_does_not_count(monkeypatch):
    """The exact defect this replaces: alda's real validation predates CORRECTIONS #47's hash move.

    Confirms the gate treats a superseded-revision entry as NOT current, by construction rather than
    by re-reading prose.
    """
    gates = _gates()
    fake = {f: {"family_code_revision": "not-the-current-hash",
                "family_config_revision": "not-the-current-hash",
                "runtime_imports_checked": True, "job": "x", "paired": True,
                "diagnostics_complete": True} for f in gates.EVALUATOR_FAMILIES}
    _with_fake_ledger(gates, monkeypatch, fake)
    verdict, reason = gates.gate_shared_evaluator_validated()
    assert verdict == gates.OWNER
    assert "needs re-run" in reason


def test_all_current_and_complete_passes(monkeypatch):
    gates = _gates()
    fake = {f: {"family_code_revision": _current_revisions(f)[0],
                "family_config_revision": _current_revisions(f)[1],
                "runtime_imports_checked": True, "job": "x", "paired": True,
                "diagnostics_complete": True} for f in gates.EVALUATOR_FAMILIES}
    _with_fake_ledger(gates, monkeypatch, fake)
    verdict, reason = gates.gate_shared_evaluator_validated()
    assert verdict == gates.PASS
    assert "all 7" in reason


def test_real_ledger_reflects_a_real_gap_right_now():
    """Non-vacuity against the ACTUAL ledger: it must not already claim full coverage, or this
    test's sibling above is not distinguishing anything."""
    gates = _gates()
    verdict, reason = gates.gate_shared_evaluator_validated()
    if verdict == gates.PASS:
        pytest.skip("all seven are validated on the current hash -- the gap this test checks for "
                    "is closed, which is good news, not a test failure")
    assert verdict == gates.OWNER
