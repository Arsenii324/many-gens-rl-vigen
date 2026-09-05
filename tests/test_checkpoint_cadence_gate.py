"""Non-vacuity for gate_checkpoint_cadence_matches_fleet: must genuinely fail on the pre-fix state
(rlvigen v100 cadence stuck at the DataSphere-era 100000), not just always pass.
"""
import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _gates():
    spec = importlib.util.spec_from_file_location("_pg_cadence", ROOT / "scripts" / "production_gates.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["_pg_cadence"] = m
    spec.loader.exec_module(m)
    return m


def test_passes_against_the_real_tree_now():
    gates = _gates()
    verdict, _ = gates.gate_checkpoint_cadence_matches_fleet()
    assert verdict == gates.PASS


def test_would_fail_on_the_original_stale_state(monkeypatch):
    gates = _gates()
    stale = json.loads((ROOT / "datasphere" / "native" / "families.json").read_text())
    del stale["rlvigen"]["host_profiles"]["v100"]["production"]["preserve_snapshots"]
    monkeypatch.setattr(gates, "_read",
                        lambda path: json.dumps(stale) if "families.json" in path else "")
    verdict, reason = gates.gate_checkpoint_cadence_matches_fleet()
    assert verdict == gates.FAIL and "100000" in reason
