"""The retention arithmetic, before a checkpoint depends on it.

`scripts/eval_across_scenes.py` produces the number [C46] names as its follow-up: what the
evaluation-scene axis costs in RETURN. Two of its rules are judgement rather than division, and
both fail in the flattering direction if they are wrong, so they are pinned here.

No environment is built. The measurement needs robosuite and a trained snapshot; the arithmetic
that turns episode returns into a headline does not, and that is the part that can quietly
manufacture a result.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.eval_across_scenes import retention  # noqa: E402


def rows(**kw):
    """rows(s0=[..], s1=[..]) -> {scene: (returns, successes)}"""
    return {int(k[1:]): (np.array(v, dtype=float), 0) for k, v in kw.items()}


class TestTheTrainingSceneIsTheDenominator:
    def test_retention_is_held_out_over_scene_zero(self):
        r = retention(rows(s0=[10.0, 12.0], s1=[5.0, 7.0]))
        assert r["ok"] and r["train_mean"] == 11.0 and r["held_mean"] == 6.0
        assert r["retention"] == pytest.approx(6.0 / 11.0)

    def test_without_scene_zero_there_is_no_retention(self):
        """Scene 0 is the TRAINING scene. A mean over held-out scenes with nothing to divide by
        is just a number, and reporting it as retention would invent an in-distribution baseline."""
        r = retention(rows(s1=[5.0], s2=[6.0]))
        assert not r["ok"] and "scene 0" in r["why"]

    def test_without_any_held_out_scene_there_is_no_retention(self):
        assert not retention(rows(s0=[10.0]))["ok"]

    def test_all_held_out_scenes_pool_into_one_mean(self):
        """Pooling episodes, not averaging per-scene means: a scene with fewer episodes must not
        carry the same weight as one with more."""
        r = retention({0: (np.array([10.0]), 0), 1: (np.array([2.0, 2.0, 2.0]), 0),
                       2: (np.array([10.0]), 0)})
        assert r["held_mean"] == pytest.approx((2 + 2 + 2 + 10) / 4)
        assert r["n_held"] == 4


class TestTheDegenerateCasesRefuseRatherThanFlatter:
    def test_a_zero_scoring_training_scene_gives_no_retention(self):
        """A policy that scores 0 in-distribution cannot have held-out scores expressed as a
        fraction of it. Dividing would emit an enormous ratio from a failed run."""
        r = retention(rows(s0=[0.0, 0.0], s1=[5.0]))
        assert not r["ok"] and "undefined" in r["why"]
        assert r["held_mean"] == 5.0, "the raw numbers are still reported, only the ratio refused"

    def test_a_negative_training_mean_also_refuses(self):
        assert not retention(rows(s0=[-3.0], s1=[5.0]))["ok"]

    def test_perfect_retention_is_reported_as_one_not_as_success(self):
        """1.0 means "no difference detected at this episode count", which the caller must be
        able to distinguish from a large positive finding."""
        r = retention(rows(s0=[10.0, 10.0], s1=[10.0, 10.0]))
        assert r["retention"] == pytest.approx(1.0)


class TestSuccessCountsTravelWithTheReturns:
    def test_held_out_successes_exclude_the_training_scene(self):
        """The training scene's successes are in-distribution and must not inflate held-out SR."""
        r = retention({0: (np.array([10.0]), 1), 1: (np.array([5.0]), 0), 2: (np.array([5.0]), 1)})
        assert r["held_succ"] == 1 and r["held_eps"] == 2
