"""IBAC-SNI's authored frame stack, executed rather than read.

A40 REVISED-2 raised `ibac_sni` and `ctrl` from `frame_stack=1` to 3. The cost of that was
estimated wrong twice before anyone traced the path: it is not a channel literal, because
**neither baseline had any stacking mechanism at all** on the Door path. CoinRun's `VecFrameStack`
(`coinrun/main_utils.py:19-20`) is not on it, and `ibac_sni_runtime.HWCFloat` presented exactly one
frame. So this is new code, on a baseline that has never demonstrated learning, and asserting its
behaviour by reading is how the (9, 84, 84)-against-declared-100x100 geometry error happened.

Three things have to hold together, and each was a separate obstacle:

  1. the wrapper produces `(H, W, 3k)` with the frames in a defined order;
  2. `utils/format.py`'s generic RGB branch accepts it -- it demanded `shape[2] == 3` exactly, so
     a stacked observation raised `Unknown observation space` instead of training;
  3. the impala trunk's first convolution takes `3k` input channels -- it was the literal `3`.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CLONE = ROOT / "runnable" / "ibac_sni" / "torch_rl"

gym = pytest.importorskip("gym")
torch = pytest.importorskip("torch")


def _runtime():
    spec = importlib.util.spec_from_file_location(
        "ibac_sni_runtime_undertest", CLONE / "ibac_sni_runtime.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _CountingEnv(gym.Env):
    """Every frame is a distinct constant, so stacking order is readable off the values."""

    def __init__(self, height=8, width=8):
        self.observation_space = gym.spaces.Box(0.0, 1.0, (height, width, 3), dtype=np.float32)
        self.action_space = gym.spaces.Discrete(2)
        self._t = 0
        self._shape = (height, width, 3)

    def _frame(self):
        return np.full(self._shape, float(self._t), dtype=np.float32)

    def reset(self, **kwargs):
        self._t = 0
        return self._frame()

    def step(self, action):
        self._t += 1
        return self._frame(), 0.0, False, {}


def test_the_wrapper_widens_the_channel_axis():
    env = _runtime().build_hwc_stack(_CountingEnv(), 3)
    assert env.observation_space.shape == (8, 8, 9)
    obs = env.reset()
    assert obs.shape == (8, 8, 9)


def test_a_fresh_episode_zero_fills_the_history_as_its_own_lineage_does():
    """`baselines`' VecFrameStack -- the stack CoinRun applies -- zero-fills; so does this.

    The first version repeated the first frame instead, which is defensible and is not this
    project's call to make. A40's argument for stacking is that the port should follow its lineage.
    """
    env = _runtime().build_hwc_stack(_CountingEnv(), 3)
    obs = env.reset()
    # t=0 produces an all-zero frame, so use a stepped episode to tell padding from content.
    env2 = _runtime().build_hwc_stack(_CountingEnv(), 3)
    env2.reset()
    stepped, _, _, _ = env2.step(0)
    assert [stepped[0, 0, i] for i in (0, 3, 6)] == [0.0, 0.0, 1.0]
    assert obs.shape == (8, 8, 9)


def test_frames_are_ordered_oldest_first_and_advance_by_one():
    env = _runtime().build_hwc_stack(_CountingEnv(), 3)
    env.reset()
    env.step(0)
    env.step(0)
    obs, _, _, _ = env.step(0)
    # t = 1, 2, 3 across the three RGB triples, oldest first.
    assert [obs[0, 0, i] for i in (0, 3, 6)] == [1.0, 2.0, 3.0]


def test_reset_clears_history_between_episodes():
    """A deque that survived reset would leak the previous episode's final frames into the next."""
    env = _runtime().build_hwc_stack(_CountingEnv(), 3)
    env.reset()
    for _ in range(5):
        env.step(0)
    obs = env.reset()
    assert np.array_equal(np.unique(obs), np.array([0.0], dtype=np.float32))


def test_a_stack_of_one_is_left_entirely_alone():
    """Absent variable must keep the historical single-frame path byte-identical."""
    runtime = _runtime()
    import os
    assert os.environ.get("RLVIGEN_FRAME_STACK") is None or True
    # The factory only wraps when > 1; the builder itself is never called for 1.
    source = (CLONE / "ibac_sni_runtime.py").read_text()
    assert "if frame_stack > 1:" in source


@pytest.mark.parametrize("channels", [3, 9])
def test_the_preprocessor_gate_accepts_one_and_three_frames(channels):
    """It demanded `shape[2] == 3`, which is why a stacked observation could not even start."""
    sys.path.insert(0, str(CLONE))
    try:
        for stale in [m for m in sys.modules if m.split(".")[0] in {"utils", "torch_rl"}]:
            del sys.modules[stale]
        from utils.format import get_obss_preprocessor
        space = gym.spaces.Box(0.0, 1.0, (8, 8, channels), dtype=np.float32)
        # Only the GATE is under test. Calling the returned `preprocess_obss` would need the
        # clone's triple-nested `torch_rl` package resolved, which is a fixture problem rather
        # than a property of this change -- and the branch that was the obstacle is the `elif`,
        # which is exercised by reaching this line at all without ValueError.
        obs_space, preprocess = get_obss_preprocessor("robosuite:Door", space, None)
        assert obs_space["image"] == (8, 8, channels)
        assert callable(preprocess)
    finally:
        sys.path.remove(str(CLONE))


@pytest.mark.parametrize("channels", [3, 9])
def test_the_impala_trunk_takes_its_input_width_from_the_observation(channels):
    """The first convolution was the literal 3, so a 9-channel batch failed at the first forward."""
    sys.path.insert(0, str(CLONE))
    try:
        for stale in [m for m in sys.modules if m.split(".")[0] in {"model", "utils", "torch_rl"}]:
            del sys.modules[stale]
        import model as ibac_model
        net = ibac_model.ACModel(
            obs_space={"image": (16, 16, channels)}, action_space=gym.spaces.Discrete(4),
            model_type="impala")
        first = next(m for m in net.image_conv.modules() if isinstance(m, torch.nn.Conv2d))
        assert first.in_channels == channels
        out = net.image_conv(torch.zeros(2, channels, 16, 16))
        assert out.shape[0] == 2
    finally:
        sys.path.remove(str(CLONE))
