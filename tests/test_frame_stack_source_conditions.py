"""`ibac_sni`'s single frame was conditional on painted velocity; `ctrl`'s was not.

A40 first read both single-frame settings as "inherited by omission". The vendored source says
something sharper, and says it differently for each -- which is why this is pinned as a test rather
than left in prose. If either upstream fact changes, the A40-REVISED decision must be re-derived.
"""
from __future__ import annotations

import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    path = ROOT / relative
    if not path.is_file():
        pytest.skip(f"{relative} absent; run setup/bootstrap_sources.py")
    return path.read_text(errors="replace")


def test_ibac_sni_ties_its_single_frame_to_painted_velocity():
    """Their own comment, directly above `frame_stack` defaulting to 1."""
    config = _read("runnable/ibac_sni/coinrun/coinrun/config.py")
    assert "No frame stack is necessary if PAINT_VEL_INFO = 1" in config
    assert "'frame_stack', int, 1" in config.replace('"', "'"), "the default they justify is 1"


def test_ibac_sni_paints_velocity_by_default_on_its_own_benchmark():
    """PAINT_VEL_INFO smart-defaults to 1 for GAME_TYPE 'standard' (CoinRun), their benchmark.

    This is the half that makes Door different: Door paints nothing, so the condition under which
    they declared one frame sufficient does not hold there.
    """
    config = _read("runnable/ibac_sni/coinrun/coinrun/config.py")
    assert "will default to 1 if GAME_TYPE is 'standard'" in config
    assert "'game_type', str, 'standard'" in config.replace('"', "'")


def test_ctrl_trains_without_painted_velocity_so_its_single_frame_is_unconditional():
    """The distinction ai-help-26 misses: ctrl's own trainer overrides the wrapper default."""
    vec_env = _read("runnable/ctrl/vec_env.py")
    train = _read("runnable/ctrl/train_ppo.py")
    assert "paint_vel_info=True" in vec_env, "the class default is True"
    assert "paint_vel_info=False" in train, (
        "ctrl's own training path passes False, so it trained single-frame WITHOUT painted "
        "velocity -- keeping frame_stack=1 for ctrl on Door is faithful, unlike for ibac_sni")


def test_only_ibac_sni_hardcodes_its_input_channel_count():
    """The whole code cost of moving ibac_sni to three frames is this one literal."""
    model = _read("runnable/ibac_sni/torch_rl/model.py")
    assert "nn.Conv2d(3, 32," in model, (
        "if this literal moved, re-derive the A40-REVISED cost: it was the only channel constant")
