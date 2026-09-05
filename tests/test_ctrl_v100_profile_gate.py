"""Non-vacuity for gate_ctrl_v100_profile_restored: it must actually PASS once the profile exists,
not just always report OWNER regardless of the tree -- the exact failure this project has hit with
gates before.
"""
import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _gates():
    spec = importlib.util.spec_from_file_location("_pg_ctrl", ROOT / "scripts" / "production_gates.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["_pg_ctrl"] = m
    spec.loader.exec_module(m)
    return m


def test_reports_pass_against_the_real_tree_right_now():
    gates = _gates()
    verdict, _ = gates.gate_ctrl_v100_profile_restored()
    assert verdict == gates.PASS, "the V100 profile is now explicitly restored in the live descriptor"


def test_would_pass_if_the_profile_existed(monkeypatch):
    gates = _gates()
    fake = json.dumps({"ctrl": {"host_profiles": {"v100": {"constants": {"num_envs": "64"}}}}})
    monkeypatch.setattr(gates, "_read", lambda path: fake if "families.json" in path else
                        gates._read.__wrapped__(path) if hasattr(gates._read, "__wrapped__") else "{}")
    verdict, _ = gates.gate_ctrl_v100_profile_restored()
    assert verdict == gates.PASS
