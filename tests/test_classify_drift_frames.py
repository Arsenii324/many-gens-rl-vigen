"""What the drift classifier must not do.

Its job is to say which render condition a stored training frame came from. The failure that
matters is a false SWITCH: reporting that a run changed visual condition partway when it did
not, which would turn placement noise into a finding. The second failure is the mirror --
missing a real switch because one episode of noise broke the run.
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
    m = importlib.import_module("classify_drift_frames")
    importlib.reload(m)
    monkeypatch.setattr(m, "FRAMES", tmp_path / "frames")
    monkeypatch.setattr(m, "CACHE", tmp_path / "refs.npz")
    (tmp_path / "frames").mkdir()
    return m


def cond(rng, base, n=3):
    """A condition: n draws around a base image, differing only by placement noise."""
    return np.clip(base + rng.normal(0, 2.0, (n,) + base.shape), 0, 255).astype(np.uint8)


@pytest.fixture()
def refs(mod):
    rng = np.random.default_rng(0)
    a = np.full((3, 12, 12), 120.0)      # 'train'-like: bright
    b = np.full((3, 12, 12), 89.0)       # 'eval-easy'-like: darker
    return {"train|0": cond(rng, a), "eval-easy|0": cond(rng, b)}


def write(mod, frames):
    for i, f in enumerate(frames):
        np.save(mod.FRAMES / f"ep{i:05d}.npy", f.astype(np.uint8))


def test_a_steady_run_reports_no_switch(mod, refs, monkeypatch, capsys):
    """20 episodes of one condition plus placement noise must NOT produce a switch."""
    rng = np.random.default_rng(1)
    monkeypatch.setattr(mod, "load_references", lambda: refs)
    write(mod, [np.clip(np.full((3, 12, 12), 120.0) + rng.normal(0, 3.0, (3, 12, 12)), 0, 255)
                for _ in range(20)])
    mod.main()
    out = capsys.readouterr().out
    assert "NO SUSTAINED SWITCH" in out
    assert "SWITCH at episode" not in out


def test_a_real_switch_is_found_and_located(mod, refs, monkeypatch, capsys):
    rng = np.random.default_rng(2)
    before = [np.full((3, 12, 12), 120.0) + rng.normal(0, 2.0, (3, 12, 12)) for _ in range(8)]
    after = [np.full((3, 12, 12), 89.0) + rng.normal(0, 2.0, (3, 12, 12)) for _ in range(8)]
    monkeypatch.setattr(mod, "load_references", lambda: refs)
    write(mod, [np.clip(x, 0, 255) for x in before + after])
    mod.main()
    out = capsys.readouterr().out
    assert "SWITCH at episode 8" in out
    assert "train|0 -> eval-easy|0" in out


def test_one_odd_episode_is_not_a_switch(mod, refs, monkeypatch, capsys):
    """A single disagreeing episode is noise. Calling it a transition is the whole failure."""
    rng = np.random.default_rng(3)
    fs = [np.full((3, 12, 12), 120.0) + rng.normal(0, 2.0, (3, 12, 12)) for _ in range(12)]
    fs[5] = np.full((3, 12, 12), 89.0)          # one frame from the other condition
    monkeypatch.setattr(mod, "load_references", lambda: refs)
    write(mod, [np.clip(x, 0, 255) for x in fs])
    mod.main()
    out = capsys.readouterr().out
    assert "NO SUSTAINED SWITCH" in out
    assert "1 episode(s) disagreed transiently" in out


def test_closest_draw_not_mean_draw(mod):
    """A frame matching ONE draw of a spread-out condition belongs to it."""
    rng = np.random.default_rng(4)
    spread = np.stack([np.full((3, 8, 8), v) for v in (40.0, 90.0, 200.0)]).astype(np.uint8)
    tight = np.stack([np.full((3, 8, 8), 110.0)] * 3).astype(np.uint8)
    frame = np.full((3, 8, 8), 92.0, dtype=np.uint8)   # near the spread's middle draw
    ranked = mod.classify(frame, {"spread|0": spread, "tight|0": tight})
    assert ranked[0][1] == "spread|0", (
        "averaging the draws first would put this frame nearer the tight condition, "
        "which no episode ever looked like")


def test_no_frames_is_a_failure_not_an_empty_report(mod, capsys):
    assert mod.main() == 1
    assert "no frames" in capsys.readouterr().out


def test_a_frame_far_from_every_reference_is_unmatched(mod, refs, monkeypatch, capsys):
    """Nearest-neighbour with no reject option always names something.

    A drq run produced five frames whose nearest reference was L1 57-68 away -- against genuine
    matches at 4-12 -- and they were reported as `eval-easy|2`, which reads as live provenance
    drift. They resemble no rendered condition at all.
    """
    rng = np.random.default_rng(9)
    monkeypatch.setattr(mod, "load_references", lambda: refs)
    frames = [np.full((3, 12, 12), 120.0) + rng.normal(0, 2.0, (3, 12, 12)) for _ in range(6)]
    frames[2] = np.full((3, 12, 12), 20.0)      # far from both references
    write(mod, [np.clip(f, 0, 255) for f in frames])
    mod.main()
    out = capsys.readouterr().out
    assert "UNMATCHED" in out, "a frame far from every reference was assigned to the least-bad one"
    assert "match NO reference" in out
