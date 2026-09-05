"""A production row without physical diagnostics must not be recorded.

External review 10: "No row should count as a paired-condition result unless those physical
diagnostics exist." Realized placement, reward components, clipping rates and termination reason
cannot be reconstructed after a fleet finishes -- it is the one loss with no repair.

This was tolerant because I feared closing it would kill families whose wrappers sit behind a vector
boundary. That fear was measured away: ppg, ctrl, idaac, ibac_sni and dmc_gb all return complete
diagnostics on real environments. Keyed on ENDPOINT_EVAL so exploratory probes stay tolerant and
production cannot inherit the probe's leniency by omission.
"""
import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _prov():
    spec = importlib.util.spec_from_file_location("_prov_fc", ROOT / "scripts" / "eval_provenance.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["_prov_fc"] = module
    spec.loader.exec_module(module)
    return module


class _Bare:
    """A handle exposing no diagnostics anywhere on the traversal."""


def test_production_refuses_a_row_without_diagnostics(monkeypatch):
    prov = _prov()
    monkeypatch.setenv("ENDPOINT_EVAL", "1")
    monkeypatch.delenv("RLGEN_REQUIRE_DIAGNOSTICS", raising=False)
    with pytest.raises(RuntimeError, match="production measurement"):
        prov.completed_episode_diagnostics(_Bare(), 0.0, 3)


def test_an_exploratory_probe_still_records_the_absence(monkeypatch):
    prov = _prov()
    monkeypatch.delenv("ENDPOINT_EVAL", raising=False)
    monkeypatch.delenv("RLGEN_REQUIRE_DIAGNOSTICS", raising=False)
    rows = prov.completed_episode_diagnostics(_Bare(), 0.0, 3)
    assert len(rows) == 3 and all(r["diagnostics_available"] is False for r in rows)


def test_the_refusal_can_be_overridden_only_explicitly(monkeypatch):
    prov = _prov()
    monkeypatch.setenv("ENDPOINT_EVAL", "1")
    monkeypatch.setenv("RLGEN_REQUIRE_DIAGNOSTICS", "0")
    rows = prov.completed_episode_diagnostics(_Bare(), 0.0, 2)
    assert len(rows) == 2, "an explicit override must still record the rows, marked unavailable"
