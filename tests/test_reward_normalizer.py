"""The reward-normalizer placement decision (`docs/REGISTER.md`, 2026-08-14).

`porting-directive.md` §2: the reference's own reward normalizer is part of the algorithm and
stays, but only for what training consumes -- the harness must still see the true raw reward.
§1: stateful normalizers are never lifted into shared code, so each on-policy baseline transcribes
its own from its own reference rather than sharing one parametrized class.

This file covers: `idaac`, `ppg`, `ibac_sni`, and `ctrl`'s real transcriptions -- each verified
against an independently hand-computed closed form, and `ppg`/`ibac_sni`/`ctrl` additionally
verified once by directly RUNNING that baseline's own reference reward-normalization code
side-by-side (dependency-free copies in the scratch dir, since the packages' own `__init__`s pull
in unrelated heavy dependencies) -- not just the closed form; plus that the trainer's storage
wiring keeps `rewards_raw` genuinely untouched while `rewards` carries the normalized value. All
four on-policy baselines' reward normalizers are real as of `ctrl` landing here (tasks #20-23).
"""
from __future__ import annotations

import math

import torch

from rlgen.algos.ctrl.algo import Learner as CTRLHermeticLearner
from rlgen.algos.ctrl.config import Config as CTRLConfig
from rlgen.algos.ibac_sni.algo import Learner as IBACSNILearner
from rlgen.algos.ibac_sni.config import Config as IBACSNIConfig
from rlgen.algos.idaac.algo import Learner as IdaacLearner
from rlgen.algos.idaac.config import Config as IdaacConfig
from rlgen.algos.idaac.storage import RolloutStorage
from rlgen.algos.ppg.algo import Learner as PPGLearner
from rlgen.algos.ppg.config import Config as PPGConfig

OBS_SHAPE = (9, 84, 84)
ACT_DIM = 7


def _idaac_cfg(**overrides):
    cfg = IdaacConfig()
    cfg.algo = "ppo"
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def test_idaac_normalize_reward_matches_a_hand_computed_welford_closed_form():
    cfg = _idaac_cfg(normalize_reward=True, reward_clip=10.0, gamma=0.9)
    learner = IdaacLearner(cfg, OBS_SHAPE, ACT_DIM, "cpu")

    raw = [1.0, 2.0, -1.0, 0.5]
    dones = [False, False, True, False]

    # Independent re-derivation of the same closed form (porting-directive.md §6: re-derive when
    # load-bearing, don't just read the module's own code back at itself).
    mean, var, count = 0.0, 1.0, 1e-4
    disc_ret = 0.0
    expected = []
    for r, done in zip(raw, dones):
        disc_ret = disc_ret * cfg.gamma + r
        d = disc_ret - mean
        tot = count + 1
        mean = mean + d / tot
        var = (var * count + d * d * count / tot) / tot
        count = tot
        e = r / math.sqrt(var + 1e-8)
        e = max(-cfg.reward_clip, min(cfg.reward_clip, e))
        expected.append(e)
        if done:
            disc_ret = 0.0

    got = [learner.normalize_reward(r, done) for r, done in zip(raw, dones)]
    for g, e in zip(got, expected):
        assert math.isclose(g, e, rel_tol=1e-9), (got, expected)


def test_idaac_normalize_reward_is_the_identity_when_the_config_flag_is_off():
    cfg = _idaac_cfg(normalize_reward=False)
    learner = IdaacLearner(cfg, OBS_SHAPE, ACT_DIM, "cpu")
    for r in (1.0, -3.5, 0.0, 100.0):
        assert learner.normalize_reward(r, False) == r


def test_idaac_normalize_reward_resets_the_discounted_return_accumulator_on_done():
    cfg = _idaac_cfg(normalize_reward=True, gamma=0.9)
    learner = IdaacLearner(cfg, OBS_SHAPE, ACT_DIM, "cpu")
    learner.normalize_reward(5.0, False)
    assert learner._disc_ret != 0.0
    learner.normalize_reward(3.0, True)
    assert learner._disc_ret == 0.0


def test_the_trainers_storage_wiring_keeps_rewards_raw_genuinely_raw():
    """Reproduces `trainer_onpolicy.py`'s own insert pattern directly against `RolloutStorage`,
    the same way `tests/test_ppg_algo.py`'s `_rollout` fixture drives its storage -- not the full
    `train_onpolicy` loop, which doesn't expose `storage` afterward. With normalization live,
    `rewards` and `rewards_raw` must diverge; with it off, they must match exactly.
    """
    def run(normalize_reward):
        cfg = _idaac_cfg(normalize_reward=normalize_reward, gamma=0.9)
        learner = IdaacLearner(cfg, OBS_SHAPE, ACT_DIM, "cpu")
        storage = RolloutStorage(4, 1, OBS_SHAPE, ACT_DIM, "cpu")
        obs = torch.randint(0, 256, (1, *OBS_SHAPE), dtype=torch.uint8)
        storage.init_obs(obs)
        raw_rewards = [1.0, 2.0, -1.0, 0.5]
        for t, r in enumerate(raw_rewards):
            done = t == len(raw_rewards) - 1
            nxt = torch.randint(0, 256, (1, *OBS_SHAPE), dtype=torch.uint8)
            with torch.no_grad():
                a, lp = learner.policy.act(storage.obs[t], deterministic=False)
                v = learner.value_of(storage.obs[t])
            reward_for_training = learner.normalize_reward(r, done)
            storage.insert(
                nxt, a, lp, v,
                torch.tensor([float(reward_for_training)]), torch.tensor([float(r)]),
                torch.tensor([float(done)]), torch.tensor([0.0]),
                torch.zeros((1, 1)), cfg.gamma)
        return storage.rewards.clone(), storage.rewards_raw.clone()

    rewards_on, raw_on = run(normalize_reward=True)
    assert not torch.allclose(rewards_on, raw_on), (
        "rewards_raw must diverge from rewards once normalization is live -- if they match, "
        "the trainer is not actually routing through normalize_reward")

    rewards_off, raw_off = run(normalize_reward=False)
    assert torch.allclose(rewards_off, raw_off), (
        "with normalize_reward=False, rewards and rewards_raw must be identical")


def test_ppg_normalize_reward_matches_a_hand_computed_closed_form():
    """Independent re-derivation of `reward_normalizer.py`'s own formula
    (`update_mean_var_count_from_moments` specialized to a batch of size 1, `backward_discounted_sum`
    specialized to one env/one step per call -- both derivations spelled out in
    `ppg/algo.py::_RunningMeanStd`'s and `Learner.normalize_reward`'s own docstrings).

    This exact equivalence was ALSO verified once by running the reference's own
    `RewardNormalizer`/`backward_discounted_sum` directly (a dependency-free copy of
    `reward_normalizer.py`, since the package `__init__` pulls in `mpi4py` unrelated to this
    math) side by side with this method, step by step across an episode boundary -- both
    sequences matched to floating-point precision. That run is not repeated as a permanent test
    here (it depended on a session-scratch file path, not durable across sessions/CI); this
    closed-form check is what stays in the suite, same pattern as `idaac`'s own reward-normalizer
    test.
    """
    cfg = PPGConfig()
    learner = PPGLearner(cfg, OBS_SHAPE, ACT_DIM, "cpu")

    raw = [1.0, 2.0, -1.0, 0.5, 3.0]
    dones = [False, False, True, False, True]

    mean, var, count = 0.0, 1.0, 1e-4
    ret = 0.0
    expected = []
    for r, done in zip(raw, dones):
        ret = ret * cfg.gamma + r
        d = ret - mean
        tot = count + 1
        mean = mean + d / tot
        var = (var * count + d * d * count / tot) / tot
        count = tot
        e = r / math.sqrt(var + 1e-8)
        e = max(-cfg.reward_clip, min(cfg.reward_clip, e))
        expected.append(e)
        if done:
            ret = 0.0

    got = [learner.normalize_reward(r, done) for r, done in zip(raw, dones)]
    for g, e in zip(got, expected):
        assert math.isclose(g, e, rel_tol=1e-9), (got, expected)


def test_ppg_normalize_reward_is_the_identity_when_the_config_flag_is_off():
    cfg = PPGConfig()
    cfg.normalize_reward = False
    learner = PPGLearner(cfg, OBS_SHAPE, ACT_DIM, "cpu")
    for r in (1.0, -3.5, 0.0, 100.0):
        assert learner.normalize_reward(r, False) == r


def test_ibac_sni_normalize_reward_matches_a_hand_computed_closed_form():
    """Independent re-derivation of `procgen_wrappers.py::VecNormalize.step_wait`'s own formula
    (`ret = ret*gamma + rews`, Welford update, clip-and-normalize, reset on done -- spelled out in
    `ibac_sni/algo.py::Learner.normalize_reward`'s own docstring).

    ALSO verified once by running the reference's own `RunningMeanStd`/`VecNormalize.step_wait`
    logic directly (a dependency-free extract of `procgen_wrappers.py`, isolating the
    reward-normalization slice from the `VecEnvWrapper` base class) side by side with this method
    across an episode boundary -- exact match to floating-point precision. Not repeated as a
    permanent test here for the same reason as `ppg`'s own note above (session-scratch path, not
    durable); this closed-form check is what stays in the suite.
    """
    cfg = IBACSNIConfig()
    learner = IBACSNILearner(cfg, OBS_SHAPE, ACT_DIM, "cpu")

    raw = [1.0, 2.0, -1.0, 0.5, 3.0]
    dones = [False, False, True, False, True]

    mean, var, count = 0.0, 1.0, 1e-4
    ret = 0.0
    expected = []
    for r, done in zip(raw, dones):
        ret = ret * cfg.gamma + r
        d = ret - mean
        tot = count + 1
        mean = mean + d / tot
        var = (var * count + d * d * count / tot) / tot
        count = tot
        e = r / math.sqrt(var + 1e-8)
        e = max(-cfg.reward_clip, min(cfg.reward_clip, e))
        expected.append(e)
        if done:
            ret = 0.0

    got = [learner.normalize_reward(r, done) for r, done in zip(raw, dones)]
    for g, e in zip(got, expected):
        assert math.isclose(g, e, rel_tol=1e-9), (got, expected)


def test_ibac_sni_normalize_reward_is_the_identity_when_the_config_flag_is_off():
    cfg = IBACSNIConfig()
    cfg.normalize_reward = False
    learner = IBACSNILearner(cfg, OBS_SHAPE, ACT_DIM, "cpu")
    for r in (1.0, -3.5, 0.0, 100.0):
        assert learner.normalize_reward(r, False) == r


def test_ctrl_normalize_reward_matches_a_hand_computed_closed_form():
    """Independent re-derivation of `ext/ctrl_public/vec_env.py::VecNormalize.step_wait`'s own
    formula (`ret = ret*gamma + rews`, Welford update, clip-and-normalize, reset on done -- spelled
    out in `ctrl/algo.py::Learner.normalize_reward`'s own docstring).

    ALSO verified once by running the reference's own `RunningMeanStd`/`VecNormalize.step_wait`
    logic directly (a dependency-free extract of `vec_env.py`, isolating the reward-normalization
    slice from the unrelated `VecEnvWrapper` base class) side by side with this method across an
    episode boundary -- exact match to floating-point precision, same verification strength as
    `ppg`/`ibac_sni`'s. Not repeated as a permanent test here for the same reason as those two
    (session-scratch path, not durable); this closed-form check is what stays in the suite.
    """
    cfg = CTRLConfig()
    cfg.ctrl_window = 4
    cfg.ctrl_clusters = 4
    learner = CTRLHermeticLearner(cfg, OBS_SHAPE, ACT_DIM, "cpu")

    raw = [1.0, 2.0, -1.0, 0.5, 3.0]
    dones = [False, False, True, False, True]

    mean, var, count = 0.0, 1.0, 1e-4
    ret = 0.0
    expected = []
    for r, done in zip(raw, dones):
        ret = ret * cfg.gamma + r
        d = ret - mean
        tot = count + 1
        mean = mean + d / tot
        var = (var * count + d * d * count / tot) / tot
        count = tot
        e = r / math.sqrt(var + 1e-8)
        e = max(-cfg.reward_clip, min(cfg.reward_clip, e))
        expected.append(e)
        if done:
            ret = 0.0

    got = [learner.normalize_reward(r, done) for r, done in zip(raw, dones)]
    for g, e in zip(got, expected):
        assert math.isclose(g, e, rel_tol=1e-9), (got, expected)


def test_ctrl_normalize_reward_is_the_identity_when_the_config_flag_is_off():
    cfg = CTRLConfig()
    cfg.ctrl_window = 4
    cfg.ctrl_clusters = 4
    cfg.normalize_reward = False
    learner = CTRLHermeticLearner(cfg, OBS_SHAPE, ACT_DIM, "cpu")
    for r in (1.0, -3.5, 0.0, 100.0):
        assert learner.normalize_reward(r, False) == r
