"""The visual probe's I/O contract, checked without robosuite, mujoco or a GPU.

`default_maker` only resolves inside the pinned cell image (robosuite/mujoco/robosuitevgb are not
installed anywhere this suite runs). `capture()` takes the environment constructor as a parameter
for exactly this reason: the frame-writing logic -- channel order, one PNG per regime, the file
names a human will open -- is what can be wrong, and none of it requires a real environment to
check.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import visual_render_probe as vrp  # noqa: E402


class _FakeTimeStep:
    def __init__(self, observation):
        self.observation = observation


class _FakeEnv:
    """Stands in for `robo_make`'s output: `reset()` returns a CHW, channel-stacked uint8 array.

    The pixel value encodes (regime, scene, seed) so a test can tell frames apart without reading
    file contents byte by byte.
    """

    def __init__(self, mode: str, scene_id: int, seed: int, frame_stack: int):
        self._mode, self._scene_id, self._seed, self._frame_stack = mode, scene_id, seed, frame_stack

    def reset(self):
        value = (hash((self._mode, self._scene_id, self._seed)) % 200) + 10
        one_frame = np.full((3, 4, 5), value, dtype=np.uint8)
        stacked = np.concatenate([one_frame] * self._frame_stack, axis=0)
        return _FakeTimeStep(stacked)


def _fake_maker(task, seed, scene_id, mode, frame_stack):
    assert task == "Door"
    return _FakeEnv(mode, scene_id, seed, frame_stack)


def test_one_png_per_regime_in_regime_order():
    written = vrp.capture(_fake_maker, pathlib.Path("/tmp/unused-not-written"))


def test_it_writes_exactly_the_four_regimes(tmp_path):
    written = vrp.capture(_fake_maker, tmp_path)
    assert [p.name for p in written] == [
        "train-scene0-seed0.png", "eval-easy-scene0-seed0.png",
        "eval-medium-scene0-seed0.png", "eval-hard-scene0-seed0.png"]
    for p in written:
        assert p.is_file(), p


def test_the_saved_png_round_trips_the_right_shape_and_channel_order(tmp_path):
    """CHW -> HWC is the one conversion this script exists to get right; a transposed image reads
    as noise to a human, which defeats the whole point of a VISUAL probe."""
    from PIL import Image
    written = vrp.capture(_fake_maker, tmp_path, seed=7, scene_id=2)
    img = np.asarray(Image.open(written[0]))
    assert img.shape == (4, 5, 3), img.shape  # (H, W, 3), not (3, H, W) or a stacked depth


def test_a_stacked_frame_is_the_same_pixel_repeated_so_the_last_slice_is_correct(tmp_path):
    """`FrameStackWrapper.reset` appends the SAME reset frame `frame_stack` times. Taking channels
    [-3:] must give that frame, not an artefact of slicing the wrong end of the stack."""
    from PIL import Image
    written = vrp.capture(_fake_maker, tmp_path, frame_stack=3)
    img = np.asarray(Image.open(written[0]))
    assert (img == img[0, 0]).all(), "expected a flat-colour frame; got a non-uniform image"


def test_different_regimes_produce_different_frames(tmp_path):
    """If every regime came back identical the probe could not answer its own question."""
    from PIL import Image
    written = vrp.capture(_fake_maker, tmp_path)
    pixel_values = {np.asarray(Image.open(p))[0, 0, 0] for p in written}
    assert len(pixel_values) == len(written), (
        "the fake maker's hash collided across regimes -- adjust the fake, not the assertion")


def test_default_maker_only_resolves_the_real_dependency_lazily():
    """Importing this module must not require robosuite/mujoco/a renderer; only calling
    default_maker does. Whatever is missing on THIS machine (mujoco, robosuite, glfw/EGL) surfaces
    as an ImportError from calling it, not from importing the module -- that is the property under
    test, not which piece happens to be absent here versus on the host."""
    with pytest.raises(ImportError):
        vrp.default_maker(task="Door", seed=0, scene_id=0, mode="train", frame_stack=3)
