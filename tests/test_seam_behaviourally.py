"""The seam, asserted by building the environment rather than by reading the source.

Every other seam check in this suite matches text: `test_eval_regime_invariant.py`,
`test_x_axis_invariant.py`, `test_truncation_seam.py`, `test_scene_coverage_contract.py`. That
method has a demonstrated weakness — three times in one session a check matched the *documentation*
of a setting rather than the setting: a shell comment restating `action_repeat=1`, a docstring
listing `_max_episode_steps`, an argparse `help=` enumerating the regimes. Each passed on its own
first run.

This file closes that gap for the parts that are cheap to observe. It builds an env through the
same `robo_make` path the baselines use and asks what it actually is, reading the regime and scene
back out of `last_info` — which `vgb_wrapper.py` populates from the env's own state, not from the
argument we passed.

Slow by nature: it constructs robosuite environments. Skipped wherever that is unavailable, and a
skip here is not a pass — the textual checks still run, and they are what covers this ground on a
machine without MuJoCo.
"""
from __future__ import annotations

import os
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytestmark = [
    pytest.mark.slow,   # constructs real robosuite environments (see module docstring)
    pytest.mark.skipif(not (ROOT / "RL-ViGen-upstream").exists(), reason="upstream clone absent"),
]


@pytest.fixture(scope="module")
def robo():
    """`robo_make` with the project's env path set up, or a skip explaining why not."""
    try:
        from scripts.eval_across_scenes import _setup
        _setup()
        os.environ.setdefault("RLVIGEN_IMAGE_SIZE", "84")
        from wrappers.robo_wrapper import robo_make
    except Exception as e:                      # say what failed; never substitute a guess
        pytest.skip(f"cannot build robosuite here: {type(e).__name__}: {str(e)[:80]}")
    return robo_make


def _probe(robo_make, *, scene_id: int, mode: str):
    """Build, step once, and return what the env says about itself."""
    env = robo_make(name="Door", frame_stack=3, action_repeat=1, seed=0,
                    scene_id=scene_id, mode=mode)
    env.reset()
    env.step(np.zeros(env.action_spec().shape, dtype=np.float32))
    return dict(getattr(env, "last_info", None) or {}), env


def test_the_env_reports_the_regime_it_was_asked_for(robo):
    """Not "the launcher passes eval-easy" but "the env is in eval-easy"."""
    info, _ = _probe(robo, scene_id=0, mode="eval-easy")
    assert info.get("mode") == "eval-easy", (
        f"asked for eval-easy, env reports {info.get('mode')!r}. `make_env` falls back to "
        "robo_config.yaml for anything it is not given, so this is the failure P1 exists for.")


def test_the_env_reports_the_scene_it_was_asked_for(robo):
    """The C45 mechanism, observed rather than read: a silent fallback yields scene 0 for every
    request, which would make a ten-scene sweep ten copies of one scene."""
    info, _ = _probe(robo, scene_id=7, mode="eval-easy")
    assert info.get("scene_id") == 7, (
        f"asked for scene 7, env reports {info.get('scene_id')!r}")


def test_the_observation_geometry_matches_the_protocol(robo):
    """`Protocol.obs_shape` is derived, not declared — this checks the derivation against reality."""
    from rlgen.protocol import Protocol
    _, env = _probe(robo, scene_id=0, mode="eval-easy")
    assert tuple(env.observation_spec().shape) == Protocol().obs_shape


def test_the_episode_ends_exactly_at_the_declared_horizon(robo):
    """Return is a sum over an episode, so a horizon that is not 500 is a different quantity.
    Door has no early termination, so every episode should run the full length."""
    from rlgen.protocol import Protocol
    _, env = _probe(robo, scene_id=0, mode="eval-easy")
    ts, steps = env.reset(), 0
    zero = np.zeros(env.action_spec().shape, dtype=np.float32)
    while not ts.last() and steps < Protocol().horizon + 50:
        ts = env.step(zero)
        steps += 1
    assert steps == Protocol().horizon, (
        f"episode ran {steps} steps against a declared horizon of {Protocol().horizon}")
