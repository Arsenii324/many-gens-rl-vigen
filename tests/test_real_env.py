"""The REAL robosuite environment, not the synthetic stand-in.

WHY THIS FILE EXISTS. Every other test runs on `backend="synthetic"`, which is fast and portable
-- and means `RoboEnv`'s own logic was never executed by the suite. The unbiased sweep proved it:
mutating `truncated = self._t >= self.spec.steps_per_episode` in `RoboEnv.step` SURVIVED, while the
identical mutation in `SyntheticEnv.step` was killed. A synthetic backend that lets the real one
go untested reproduces, in miniature, the exact failure this repo is built against: a check that
passes without touching the thing it claims to check.

These tests are slow (each env build is ~1 s, each step ~10 ms) and are skipped when the vendored
upstream is absent, so they do not block a checkout that has not run `setup/install.sh`. They are
NOT optional in CI on a machine that has it: `test_upstream_patches_are_applied` and these
together are what stand between the repo and a silently-training-distribution evaluation.
"""
from __future__ import annotations

import os

import numpy as np
import pytest

from rlgen.envs import UPSTREAM, ContractError, EnvSpec, make_env
from rlgen.evaluate import _read_success, evaluate, run_episode
from rlgen.protocol import Protocol
from rlgen import registry

pytestmark = [pytest.mark.slow, pytest.mark.skipif(
    not os.path.isdir(UPSTREAM),
    reason="RL-ViGen-upstream not present; run setup/install.sh")]


def real(**kw):
    d = dict(task="Door", mode="train", scene_id=0, seed=0, horizon=6, backend="robosuite")
    d.update(kw)
    return EnvSpec(**d)


@pytest.fixture(scope="module")
def env():
    e = make_env(real())
    yield e
    e.close()


def test_real_env_satisfies_the_contract(env):
    obs = env.reset()
    assert obs.dtype == np.uint8
    assert obs.shape == env.spec.obs_shape == (9, 84, 84)
    assert env.act_dim == 7
    assert obs.min() >= 0 and obs.max() <= 255


def test_real_env_contract_is_checked_once_on_the_first_reset_not_every_reset_and_not_never(monkeypatch):
    """`RoboEnv._checked` gates a single call to `_assert_contract` on the first `reset()`.
    Found surviving mutation testing (Stage 3, comparability-contract meta-plan): flipping either
    the flag's initial value, the `if not self._checked:` condition, or the post-check assignment
    all survived the full suite -- meaning no test distinguished "the contract check actually
    ran" from "it silently never ran but nothing noticed," on the ONE backend
    (`RoboEnv`/robosuite) where a real contract violation could plausibly occur. Counts real
    calls via monkeypatch rather than only inspecting the `_checked` flag, so a bug that flips the
    flag without the check ever having run (or vice versa) cannot pass by accident."""
    import rlgen.envs as envs_mod
    calls = []
    real_assert = envs_mod._assert_contract

    def counting_assert(*a, **k):
        calls.append(1)
        return real_assert(*a, **k)

    monkeypatch.setattr(envs_mod, "_assert_contract", counting_assert)
    e = envs_mod.make_env(real())
    try:
        assert e._checked is False, "must start unchecked"
        e.reset()
        assert e._checked is True, "must be marked checked after the first reset"
        assert len(calls) == 1, f"_assert_contract must run exactly once on the first reset, ran {len(calls)}x"
        e.reset()
        e.reset()
        assert len(calls) == 1, f"_assert_contract must NOT re-run on later resets, ran {len(calls)}x total"
    finally:
        e.close()


def test_real_env_truncates_exactly_on_the_horizon(env):
    """The sweep's surviving mutant. Door has no early termination, so the ONLY episode end is
    the time limit, and it must land on `horizon // action_repeat` and not one step later."""
    n = env.spec.steps_per_episode
    assert n == 6
    env.reset()
    for t in range(1, n + 1):
        _o, _r, term, trunc, info = env.step(np.zeros(env.act_dim, dtype=np.float32))
        assert term is False, "Door reported early termination; truncation logic assumes it cannot"
        assert trunc == (t == n), f"step {t}/{n}: truncated={trunc}"
    assert info["episode"]["l"] == n


def test_real_env_action_repeat_changes_the_episode_length():
    a = make_env(real(horizon=6, action_repeat=1))
    b = make_env(real(horizon=6, action_repeat=3))
    try:
        assert a.spec.steps_per_episode == 6 and b.spec.steps_per_episode == 2
        for e, n in ((a, 6), (b, 2)):
            e.reset()
            for t in range(1, n + 1):
                _o, _r, _term, trunc, _i = e.step(np.zeros(e.act_dim, dtype=np.float32))
            assert trunc, f"action_repeat={e.spec.action_repeat} did not end at step {n}"
    finally:
        a.close(); b.close()


def test_real_env_choke_point_instrumentation_matches_the_synthetic_backend():
    """The sweep's own lesson (this file's docstring): SyntheticEnv-only coverage misses
    RoboEnv-only bugs. tests/test_contract.py pins step_calls/action_clip_events/
    max_abs_action_seen against SyntheticEnv; this confirms RoboEnv wasn't left behind by a
    copy-paste that forgot one of the two classes."""
    e = make_env(real(horizon=6, action_repeat=1))
    try:
        e.reset()
        assert e.step_calls == 0 and e.action_clip_events == 0 and e.max_abs_action_seen == 0.0
        e.step(np.full(e.act_dim, 0.5, dtype=np.float32))
        assert e.step_calls == 1
        assert e.action_clip_events == 0
        assert e.max_abs_action_seen == pytest.approx(0.5)
        e.step(np.full(e.act_dim, 3.0, dtype=np.float32))
        assert e.step_calls == 2
        assert e.action_clip_events == 1
        assert e.max_abs_action_seen == pytest.approx(3.0)
        # Exact boundary, RoboEnv's own copy of the `mag > 1.0` check -- found missing by
        # mutation testing (Stage 3): a separate mutable site from SyntheticEnv's, so it needs
        # its own boundary check, not just one shared between the two classes.
        e.step(np.full(e.act_dim, 1.0, dtype=np.float32))
        assert e.step_calls == 3
        assert e.action_clip_events == 1, "exactly at the clip bound must not count as a new event"
    finally:
        e.close()


@pytest.mark.parametrize("name", registry.BRIEF_BASELINES)
def test_every_baseline_step_calls_matches_ground_truth_on_the_real_backend(name):
    """`tests/test_contract.py::test_every_baseline_step_calls_matches_ground_truth` covers this
    on the synthetic backend for all 12; docs/COMPARABILITY_CONTRACT.md §5 explicitly recorded
    the real-backend equivalent as NOT run for individual baselines (only the shared
    instrumentation itself, generically, via test_real_env_choke_point_instrumentation_matches_
    the_synthetic_backend above). Closes that gap: same pattern, real robosuite, all 12 -- an
    agent built through the real registry path acting against the real environment, cross-checked
    against step_calls' independent ground truth."""
    from rlgen.agents import policy_for

    p = Protocol(task="Door", total_frames=0, horizon=6, action_repeat=1)
    agent = registry.get(name).build(p, p.obs_shape, 7, "cpu", {"seed": 0})
    pol = policy_for(agent, True)
    e = make_env(real(horizon=6, action_repeat=1))
    try:
        obs = e.reset()
        n = 3
        for _ in range(n):
            obs, _r, _term, _trunc, _info = e.step(pol(obs))
        assert e.step_calls == n, (
            f"{name}: step_calls={e.step_calls} after {n} real steps on the real backend through "
            f"the actual registry build path -- ground truth and the environment's own count "
            f"disagree")
    finally:
        e.close()


def test_real_env_reward_is_raw_and_unnormalised(env):
    """Door's shaped reward is small and positive early. What matters is that it is not
    z-scored or clipped by anything between robosuite and us."""
    env.reset()
    rs = [env.step(np.zeros(env.act_dim, dtype=np.float32))[1] for _ in range(5)]
    assert all(isinstance(r, float) for r in rs)
    assert all(0.0 <= r < 1.5 for r in rs), f"reward outside robosuite's shaped range: {rs}"
    assert len(set(rs)) > 1, "reward is constant; it is not tracking the state"


def test_mode_is_verified_not_trusted():
    """Every eval mode must build AND report itself. This is the P1 guard."""
    for mode in ("train", "eval-easy", "eval-hard"):
        e = make_env(real(mode=mode))
        try:
            assert e.regime["mode"] == mode
            assert e.regime["video_background"] is (mode == "eval-hard")
        finally:
            e.close()


def test_scene_id_is_verified():
    e = make_env(real(scene_id=4))
    try:
        assert e.regime["scene_id"] == 4
    finally:
        e.close()


def test_eval_modes_actually_look_different_from_train():
    """A regime that is requested, reported, and visually identical to train would satisfy every
    other check in this file while measuring nothing. Compare the pixels."""
    frames = {}
    for mode in ("train", "eval-easy"):
        e = make_env(real(mode=mode, seed=0))
        try:
            frames[mode] = e.reset().astype(np.int16)
        finally:
            e.close()
    diff = float(np.abs(frames["train"] - frames["eval-easy"]).mean())
    assert diff > 1.0, (f"eval-easy differs from train by only {diff:.3f} grey levels per pixel; "
                        f"the visual randomisation is not taking effect")


def test_success_is_readable_through_the_wrapper_chain(env):
    """Regression: the chain links via `_env`, `_gym_env` and `env` at different depths, and a
    walk that only followed `_env` stopped at Gym2DMC -- so `success` was empty in every row of
    the first real run. Absent is `None`; it must not be silently absent."""
    env.reset()
    env.step(np.zeros(env.act_dim, dtype=np.float32))
    assert _read_success(env) is False, "success is unreachable, or wrongly True at step 1"


def test_a_short_real_evaluation_produces_well_formed_records():
    p = Protocol(task="Door", total_frames=0, episodes_per_scene=1, eval_scene_ids=(0, 1),
                 horizon=4)
    r = evaluate(p, lambda o: np.zeros(7, np.float32), mode="eval-easy",
                 backend="robosuite", baseline="random", backbone="none")
    assert len(r.records) == 2
    assert sorted(rec.scene_id for rec in r.records) == [0, 1]
    for rec in r.records:
        assert rec.episode_len == 4 and rec.truncated and not rec.terminated
        assert rec.success is False
        assert rec.protocol_hash == p.hash()


def test_every_episode_of_a_run_comes_from_one_distribution():
    """The warm-up reset in `RoboEnv.__init__`, and the artifact it removes.

    MEASURED: robosuite's FIRST reset after construction does not draw from the same distribution
    as later ones. On Door with a zero policy the first episode scored ~45% higher (0.0251 vs
    0.0172 at horizon 6; 0.0846 vs 0.0583 at horizon 20), and it was not reproducible from a numpy
    seed while later episodes were. `evaluate()` builds one env per scene, so episode 0 of EVERY
    scene was systematically off -- a tenth of the data at the default `episodes_per_scene=10`,
    and invisible in any curve.

    THE PROPERTY TO TEST is that consecutive episodes of the SAME env, given the same seed, agree.
    An earlier version of this test compared two FRESH envs instead, which are identical to each
    other with or without the warm-up -- it passed either way and the mutation catalogue caught it
    (`M16-no-warmup-reset` survived). Same-env is the comparison that can see the defect.
    """
    pol = lambda o: np.zeros(7, np.float32)  # noqa: E731
    e = make_env(real(horizon=8))
    try:
        def episode(seed):
            np.random.seed(seed)
            return run_episode(e, pol, max_steps=e.spec.steps_per_episode)[0]

        first, second = episode(123), episode(123)
        assert first == second, (
            f"episode 1 and episode 2 of one env differ under the same seed "
            f"({first} vs {second}) -- the first reset draws from a different distribution, so "
            f"episode 0 of every scene is biased. The warm-up reset in RoboEnv.__init__ exists "
            f"to remove exactly this.")
        assert episode(999) != first, "different seeds gave identical episodes"
    finally:
        e.close()


# ============================================================== reproducibility of a re-seeded episode
# `rlgen/evaluate.py::evaluate` calls `np.random.seed(s)` immediately before every `env.reset()`,
# with `s` a deterministic function of the protocol (`_episode_seed`). Its docstring USED TO claim
# this does not make an episode byte-reproducible, citing a test by name
# (`test_real_env_episodes_vary_but_are_not_byte_reproducible`) as evidence. That test never
# existed anywhere in this repo -- the claim was written, not measured.
#
# Found while cross-checking against the sibling gen-rebuttal project's R20 (object placement
# there was unseeded, fixed by seeding once per worker at construction, achieving bit-identical
# repeat evaluations). This repo seeds per EPISODE instead, which is finer-grained, and MEASURED
# HERE for the first time: it also achieves byte-identical episodes on the real backend. Two
# separate evaluations of the same checkpoint therefore produce identical numbers -- the
# reproducibility property gen-rebuttal had to add is already present here, just via a different
# mechanism, and now it is actually verified rather than asserted either way in prose.
# `evaluate.py`'s docstring corrected 2026-08-13 to state this, with this test as its evidence.
def test_real_env_reseeded_episode_reproducibility(env):
    """Two episodes on the SAME persisting env, re-seeded to the SAME value before each reset,
    are byte-identical -- confirming `_episode_seed` really is a reproducibility mechanism, not
    only a decorrelation one. Two DIFFERENT seeds must still differ, so this test cannot pass
    vacuously by the seed simply not reaching anything."""
    def run(seed):
        np.random.seed(seed)
        obs = env.reset()
        frames = [obs.copy()]
        rewards = []
        for _ in range(5):
            a = np.zeros(env.act_dim, dtype=np.float32)
            obs, r, term, trunc, _info = env.step(a)
            frames.append(obs.copy())
            rewards.append(r)
            if term or trunc:
                break
        return frames, rewards

    frames_a, rewards_a = run(12345)
    frames_b, rewards_b = run(12345)
    frames_c, rewards_c = run(67890)

    assert len(frames_a) == len(frames_b) and rewards_a == rewards_b and all(
        np.array_equal(x, y) for x, y in zip(frames_a, frames_b)), (
        "the same seed produced two different trajectories -- reproducibility regressed")

    different = (len(frames_a) != len(frames_c) or rewards_a != rewards_c
                or not all(np.array_equal(x, y) for x, y in zip(frames_a, frames_c)))
    assert different, (
        "two DIFFERENT seeds produced byte-identical trajectories -- the seed is not reaching "
        "anything, which would make both this test and _episode_seed's decorrelation purpose "
        "vacuous regardless of the same-seed result above")
