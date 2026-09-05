"""IDAAC's episode identity must describe the observation at the same rollout index."""

import sys
from pathlib import Path

import gym
import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ext" / "baselines"))
sys.path.insert(0, str(ROOT / "runnable" / "idaac"))

from baselines.common.vec_env import DummyVecEnv
from ppo_daac_idaac import envs as idaac_envs
from ppo_daac_idaac.storage import IDAACRolloutStorage


class ActionBox:
    shape = (1,)


class TwoStepEpisode(gym.Env):
    """Observation 10*episode+timestep makes an auto-reset visible without MuJoCo."""

    observation_space = gym.spaces.Box(0, 255, shape=(1,), dtype=np.uint8)
    action_space = gym.spaces.Box(-1, 1, shape=(1,), dtype=np.float32)
    spec = None

    def __init__(self):
        self.episode = -1
        self.timestep = 0

    def reset(self):
        self.episode += 1
        self.timestep = 0
        return np.array([10 * self.episode], dtype=np.uint8)

    def step(self, action):
        self.timestep += 1
        return (
            np.array([10 * self.episode + self.timestep], dtype=np.uint8),
            0.0,
            self.timestep == 2,
            {},
        )


def _insert(storage, observation, level, nstep):
    one = torch.zeros(1, 1)
    storage.insert(
        torch.tensor([[observation]], dtype=torch.float32),
        one,
        one,
        one,
        one,
        torch.ones(1, 1),
        one,
        torch.tensor([level]),
        torch.tensor([nstep]),
    )


def test_storage_writes_episode_metadata_at_the_observations_index():
    """Moving metadata after the circular-pointer advance must break this alignment."""
    storage = IDAACRolloutStorage(2, 1, (1,), ActionBox())
    storage.obs[0, 0, 0] = 10
    storage.levels[0, 0] = 100
    storage.nsteps[0, 0] = 0

    _insert(storage, observation=11, level=100, nstep=1)
    _insert(storage, observation=20, level=101, nstep=0)

    assert storage.obs[:, 0, 0].tolist() == [10, 11, 20]
    assert storage.levels[:, 0].tolist() == [100, 100, 101]
    assert storage.nsteps[:, 0].tolist() == [0, 1, 0]


def test_auto_reset_reports_the_identity_of_the_returned_observation():
    """On done, DummyVecEnv returns the next reset observation but keeps terminal info."""
    wrapper = getattr(idaac_envs, "EpisodeLevelSeed", None)
    identities = getattr(idaac_envs, "observation_level_seeds", None)
    assert wrapper is not None and identities is not None

    vector = DummyVecEnv([lambda: wrapper(TwoStepEpisode(), 100, level_stride=1)])
    assert vector.reset().tolist() == [[0]]

    vector.step_async(np.zeros((1, 1), dtype=np.float32))
    observation, _, done, infos = vector.step_wait()
    assert observation.tolist() == [[1]]
    assert identities(infos, done) == [100]

    vector.step_async(np.zeros((1, 1), dtype=np.float32))
    observation, _, done, infos = vector.step_wait()
    assert done.tolist() == [True]
    assert observation.tolist() == [[10]], "DummyVecEnv must have auto-reset to episode 1"
    assert infos[0]["level_seed"] == 100, "terminal info still describes episode 0"
    assert identities(infos, done) == [101]


def test_dummy_vecenv_observation_identity_and_storage_stay_aligned_end_to_end():
    """Exercise the actual wrapper, Baselines auto-reset, and IDAAC storage in one chain."""
    vector = DummyVecEnv([
        lambda: idaac_envs.EpisodeLevelSeed(TwoStepEpisode(), 100, level_stride=1)
    ])
    storage = IDAACRolloutStorage(2, 1, (1,), ActionBox())
    storage.device = "cpu"

    initial = vector.reset()
    storage.obs[0].copy_(torch.from_numpy(initial).float())
    storage.levels[0, 0] = 100

    nstep = 0
    for _ in range(2):
        vector.step_async(np.zeros((1, 1), dtype=np.float32))
        observation, _, done, infos = vector.step_wait()
        nstep = 0 if bool(done[0]) else nstep + 1
        _insert(
            storage,
            observation=int(observation[0, 0]),
            level=idaac_envs.observation_level_seeds(infos, done)[0],
            nstep=nstep,
        )

    assert storage.obs[:, 0, 0].tolist() == [0, 1, 10]
    assert storage.levels[:, 0].tolist() == [100, 100, 101]
    assert storage.nsteps[:, 0].tolist() == [0, 1, 0]

    torch.manual_seed(0)
    storage.before_update()
    source_episodes = (storage.obs[:, 0, 0] // 10).tolist()
    paired_episodes = (storage.other_obs[:, 0, 0] // 10).tolist()
    assert paired_episodes == source_episodes, "IDAAC paired observations across Door episodes"
