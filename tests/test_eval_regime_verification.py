"""The six non-rlvigen evaluators must refuse a silently-ignored regime.

`eval_across_scenes.run_scene` has verified this since 2026-08-25 and states the stake: a `mode`
that fails to take effect evaluates the "eval" grid in the TRAINING regime and yields a retention
of about 1.0 -- a clean-looking null that reads as invariance. The other six families in
`eval_grid.py` had no such check until 2026-09-04, so the same failure was available to all of
them and would have looked like a result. These tests pin the helper's three outcomes.
"""
import subprocess, sys, textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(body):
    """Exercise `verify_regime` without importing eval_grid (whose module-level imports need the
    container's torch/jax stack). The function is extracted by source, which also pins that it
    stays free of module-level dependencies."""
    src = (ROOT / "scripts" / "eval_grid.py").read_text()
    start = src.index("def verify_regime(")
    end = src.index("\ndef ", start + 1)
    prog = "import sys\n" + src[start:end] + "\n" + textwrap.dedent(body)
    return subprocess.run([sys.executable, "-c", prog], capture_output=True, text=True)


class _Node:
    def __init__(self, mode=None, info=None, child=None):
        if mode is not None:
            self._mode = mode
        self.last_info = info or {}
        self.env = child


def test_helper_is_wired_into_every_family():
    src = (ROOT / "scripts" / "eval_grid.py").read_text()
    for fam in ("dmc_gb", "ibac_sni", "idaac", "ppg", "alda", "ctrl"):
        assert f'verify_regime(' in src and f'"{fam}", strict=True)' in src, fam


def test_mismatched_mode_raises():
    r = _run('''
        class N:
            _mode = "train"
            last_info = {}
        try:
            verify_regime(N(), "eval-easy", 0, "ppg")
            print("NO-RAISE")
        except RuntimeError as e:
            print("RAISED", "wrong regime" in str(e) or "did not take effect" in str(e))
        ''')
    assert "RAISED True" in r.stdout, r.stdout + r.stderr


def test_matching_mode_passes_quietly():
    r = _run('''
        class N:
            _mode = "eval-easy"
            last_info = {"scene_id": 3}
        verify_regime(N(), "eval-easy", 3, "ctrl"); print("OK")
        ''')
    assert "OK" in r.stdout and "??" not in r.stderr, r.stdout + r.stderr


def test_unreadable_env_abstains_loudly_rather_than_passing():
    """A check that cannot run and a check that passed must not look the same."""
    r = _run('''
        class N:
            last_info = {}
            env = None
        verify_regime(N(), "eval-easy", 0, "alda"); print("OK")
        ''')
    assert "OK" in r.stdout, r.stdout + r.stderr
    assert "UNVERIFIED" in r.stderr and "not a pass" in r.stderr, r.stderr


def test_strict_mode_invalidates_unreadable_env():
    """Production evaluation must not emit a row when the intervention is not observable."""
    r = _run('''
        class N:
            last_info = {}
            env = None
        try:
            verify_regime(N(), "eval-easy", 0, "ibac_sni", strict=True)
            print("NO-RAISE")
        except RuntimeError as e:
            print("RAISED", "UNVERIFIED" in str(e))
        ''')
    assert "RAISED True" in r.stdout, r.stdout + r.stderr


def test_ibac_environment_request_is_checked_without_touching_env():
    """IBAC's original constructor ingress is its two RLVIGEN_* variables."""
    src = (ROOT / "scripts" / "eval_grid.py").read_text()
    start = src.index("def verify_env_request(")
    end = src.index("\ndef ", start + 1)
    prog = "import os\n" + src[start:end] + "\nos.environ.update(RLVIGEN_MODE='eval-hard', RLVIGEN_SCENE_ID='7')\nverify_env_request('eval-hard', 7, 'ibac_sni')\nprint('OK')\n"
    r = subprocess.run([sys.executable, "-c", prog], capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip() == "OK", r.stdout + r.stderr


def test_mismatched_scene_raises_where_last_info_exists():
    r = _run('''
        class N:
            _mode = "eval-easy"
            last_info = {"scene_id": 1}
        try:
            verify_regime(N(), "eval-easy", 4, "idaac"); print("NO-RAISE")
        except RuntimeError as e:
            print("RAISED", "duplicate" in str(e))
        ''')
    assert "RAISED True" in r.stdout, r.stdout + r.stderr


def test_dmc_evaluation_seed_matches_upstream_train_and_test_envs():
    """dmc_gb's test env is deliberately seeded 42 past its training env."""
    src = (ROOT / "scripts" / "eval_grid.py").read_text()
    start = src.index("def dmc_eval_seed(")
    end = src.index("\ndef ", start + 1)
    prog = src[start:end] + "\nprint(dmc_eval_seed('train', 7), dmc_eval_seed('eval-easy', 7))\n"
    r = subprocess.run([sys.executable, "-c", prog], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == "7 49", r.stdout + r.stderr


def test_nested_vector_and_gym3_wrappers_are_verified_without_stepping():
    """The real IDAAC/PPG stacks hide the VGB env in envs[]/gym_env attributes."""
    r = _run('''
        class Base:
            _mode = "eval-easy"
            last_info = {"scene_id": 2}
            def reset(self): raise AssertionError("verification must not reset")
            def step(self, _): raise AssertionError("verification must not step")
        class Gym3Adapter:
            gym_env = Base()
        class Vector:
            envs = [Gym3Adapter()]
        verify_regime(Vector(), "eval-easy", 2, "ppg"); print("OK")
        ''')
    assert "OK" in r.stdout and "UNVERIFIED" not in r.stderr, r.stdout + r.stderr


def test_idaac_adapter_hoists_the_vigen_readback_without_resetting():
    """IDAAC bypasses P3, so the vector stack must retain its base env's evidence."""
    source = (ROOT / "runnable" / "idaac" / "ppo_daac_idaac" / "envs.py").read_text()
    assert '"mode": getattr(bases[0], "_mode", None)' in source
    assert '"scene_id": getattr(bases[0], "_scene_id", None)' in source
    assert "wrapped._vigen_regime = dict(applied_regime)" in source


def test_direct_rlvigen_adapters_hoist_construction_readback_without_stepping():
    """PPG and IBAC bypass P3, so their own wrappers must retain the base env's evidence.

    ibac's path moved to `ibac_sni_runtime.py` when Codex's Door-specific picklable-factory repair
    (procs=16 spawn support) extracted env construction out of `torch_rl/utils/general.py` -- update
    this path in the same edit if it moves again.
    """
    ppg = (ROOT / "runnable" / "ppg" / "phasic_policy_gradient" / "envs.py").read_text()
    ibac = (ROOT / "runnable" / "ibac_sni" / "torch_rl" / "ibac_sni_runtime.py").read_text()
    for source in (ppg, ibac):
        assert '"mode": getattr(base, "_mode", None)' in source
        assert '"scene_id": getattr(base, "_scene_id", None)' in source
        assert "_vigen_regime = dict(applied_regime)" in source
