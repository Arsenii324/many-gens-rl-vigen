"""The watcher's only job is not to lose episodes.

It races a process that deletes the files it is reading. The two failures that matter are
losing an episode to a half-written read (which would silently thin the record) and capturing
one twice under different names (which would fake a longer run).
"""
from __future__ import annotations

import importlib
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture()
def mod(tmp_path, monkeypatch):
    m = importlib.import_module("watch_training_frames")
    importlib.reload(m)
    monkeypatch.setattr(m, "EXP", tmp_path / "exp_local")
    (tmp_path / "exp_local" / "d" / "num_train_frames=99" / "buffer").mkdir(parents=True)
    return m


def buf(mod):
    return mod.EXP / "d" / "num_train_frames=99" / "buffer"


def episode(n=4):
    return np.random.default_rng(0).integers(0, 255, (n, 9, 84, 84), dtype=np.uint8)


def test_captures_each_episode_once(mod, tmp_path):
    out = tmp_path / "out"; out.mkdir()
    seen = set()
    for ep in (0, 1, 2):
        np.savez(buf(mod) / f"20260820T00_{ep}_500.npz", observation=episode())
    assert mod.sweep(out, "num_train_frames=", seen) == 3
    assert mod.sweep(out, "num_train_frames=", seen) == 0, "an episode was captured twice"
    assert sorted(p.name for p in out.glob("*.npy")) == ["ep00000.npy", "ep00001.npy",
                                                         "ep00002.npy"]


def test_a_half_written_file_is_retried_not_dropped(mod, tmp_path):
    """The file the run is mid-write on must come back on the next sweep, not be lost."""
    out = tmp_path / "out"; out.mkdir()
    seen = set()
    bad = buf(mod) / "20260820T00_7_500.npz"
    bad.write_bytes(b"not an npz yet")
    assert mod.sweep(out, "num_train_frames=", seen) == 0
    assert not seen, "a failed read was marked seen, so the episode would never be retried"
    np.savez(bad, observation=episode())
    assert mod.sweep(out, "num_train_frames=", seen) == 1


def test_saves_only_the_reset_frame(mod, tmp_path):
    out = tmp_path / "out"; out.mkdir()
    np.savez(buf(mod) / "20260820T00_3_500.npz", observation=episode())
    mod.sweep(out, "num_train_frames=", set())
    got = np.load(out / "ep00003.npy")
    assert got.shape == (3, 84, 84) and got.dtype == np.uint8


def test_match_excludes_other_runs(mod, tmp_path):
    other = mod.EXP / "d" / "some_other_run" / "buffer"
    other.mkdir(parents=True)
    np.savez(other / "20260820T00_0_500.npz", observation=episode())
    out = tmp_path / "out"; out.mkdir()
    assert mod.sweep(out, "num_train_frames=", set()) == 0
