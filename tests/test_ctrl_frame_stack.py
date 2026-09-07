"""CTRL's authored frame stack, executed against the real methods.

Like `ibac_sni`, `ctrl` had NO stacking mechanism on the Door path: `_SyncVecEnv`, `VecMonitor`
and `VecNormalize` all preserve the observation shape, so the policy never saw velocity. A40
REVISED-2 raised it to 3 on the grounds that single-frame is Procgen's environment convention and
CTRL's clustering objective works over rollout timesteps (`algo.py:90,539`), not stacked channels.

The layout is the trap here, and it is a documented inversion rather than a bug:
`observation_space` is declared **(C, H, W)** while `_SyncVecEnv._obs` emits **(H, W, C)**, because
`buffer.py:50-52` permutes with `[shape[1], shape[2], shape[0]]`. Door's frames are square, so
(3, 64, 64) and (64, 64, 3) are indistinguishable by shape alone -- until a stack makes one of them
9. A buffer built on the declaration rather than the data would have rolled the wrong axis and
produced a plausible, wrong observation with no error anywhere.

`RLViGenVecEnvCustom.__init__` needs robosuite and MuJoCo, so these bind the real `reset`/`step`
to a fake inner env. The methods under test are the shipped ones, not copies.
"""
from __future__ import annotations

import importlib.util
import pathlib

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CLONE = ROOT / "runnable" / "ctrl"

pytest.importorskip("gym")


def _vec_env_module():
    spec = importlib.util.spec_from_file_location("ctrl_vec_env_undertest", CLONE / "vec_env.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeInner:
    """Emits (n, H, W, C) uint8 frames whose value is the timestep, per env."""

    def __init__(self, num_envs=2, height=4, width=4, channels=3):
        self.shape = (num_envs, height, width, channels)
        self._t = np.zeros(num_envs, dtype=np.int64)
        self.dones = np.zeros(num_envs, dtype=bool)

    def _frames(self):
        out = np.zeros(self.shape, dtype=np.uint8)
        for i, t in enumerate(self._t):
            out[i] = t
        return out

    def reset(self):
        self._t[:] = 0
        return self._frames()

    def step(self, action):
        self._t += 1
        # _SyncVecEnv auto-resets on done and returns the NEW episode's first observation.
        for i, done in enumerate(self.dones):
            if done:
                self._t[i] = 0
        return self._frames(), np.zeros(len(self._t)), self.dones.copy(), [{} for _ in self._t]


def _stacked_env(nstack=3, num_envs=2, height=4, width=4, channels=3):
    module = _vec_env_module()
    env = object.__new__(module.RLViGenVecEnvCustom)
    env.env = _FakeInner(num_envs, height, width, channels)
    env._nstack = nstack
    env._frame_channels = channels
    env._stackedobs = np.zeros((num_envs, height, width, channels * nstack), dtype=np.uint8)
    return env


def test_the_buffer_is_channel_last_to_match_the_data_not_the_declaration():
    env = _stacked_env()
    obs = env.reset()
    assert obs.shape == (2, 4, 4, 9), (
        "the stack must follow _SyncVecEnv._obs's (H, W, C), not observation_space's (C, H, W)")
    assert obs.dtype == np.uint8, "buffer.py allocates uint8; a float stack would silently upcast"


def test_reset_zero_fills_exactly_as_baselines_vec_frame_stack_does():
    env = _stacked_env()
    obs = env.reset()
    # t=0 at reset, so every slot is 0 either way -- assert the SHAPE of the fill by stepping once.
    stepped, _, _, _ = env.step(np.zeros(2))
    assert list(stepped[0, 0, 0]) == [0, 0, 0, 0, 0, 0, 1, 1, 1], (
        "oldest frame first, newest in the last C channels")


def test_frames_advance_oldest_first():
    env = _stacked_env()
    env.reset()
    env.step(np.zeros(2))
    env.step(np.zeros(2))
    obs, _, _, _ = env.step(np.zeros(2))
    assert list(obs[0, 0, 0]) == [1, 1, 1, 2, 2, 2, 3, 3, 3]


def test_a_done_member_has_its_history_cleared_and_the_others_do_not():
    """The auto-reset seam: without this, a new episode's first stack carries the old episode."""
    env = _stacked_env()
    env.reset()
    for _ in range(3):
        env.step(np.zeros(2))
    env.env.dones[0] = True
    obs, _, dones, _ = env.step(np.zeros(2))
    assert dones[0] and not dones[1]
    assert list(obs[0, 0, 0]) == [0, 0, 0, 0, 0, 0, 0, 0, 0], "env 0 restarted; history must be gone"
    assert list(obs[1, 0, 0]) == [2, 2, 2, 3, 3, 3, 4, 4, 4], "env 1 was untouched"


def test_a_stack_of_one_returns_the_inner_observation_unchanged():
    """Absent variable must leave the historical single-frame path byte-identical."""
    module = _vec_env_module()
    env = object.__new__(module.RLViGenVecEnvCustom)
    env.env = _FakeInner()
    env._nstack = 1
    inner = env.env.reset()
    env.env._t[:] = 0
    assert np.array_equal(env.reset(), inner)


def test_the_declared_space_stays_channel_first_so_buffer_py_is_untouched():
    """buffer.py permutes [1],[2],[0]; declaring (H, W, C*k) would make it allocate nonsense."""
    source = (CLONE / "vec_env.py").read_text()
    assert "Box(shape=(c * self._nstack, h, w), low=0, high=255)" in source
    buffer_source = (CLONE / "buffer.py").read_text()
    assert "state_space.shape[1], state_space.shape[2], state_space.shape[0]" in buffer_source
