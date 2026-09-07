"""Each family's `native` action rule must match its own released EVALUATOR, not its training loop.

This exists because the two disagreed for `ctrl` for three days and nothing caught it. The
2026-09-04 entry reasoned from `train_ppo.py`'s sampling calls -- the TRAINING path -- and set
`ctrl` to `sample`, while `runnable/ctrl/evaluate_ppo.py:84` calls
`select_action(..., greedy=True)`, whose greedy branch is `logits.argmax(1)`. Three files agreed
with each other and all three were wrong together, which is exactly what an internal-consistency
test cannot see.

So this test anchors against the vendored upstream source, not against another of our own tables.
"""
from __future__ import annotations

import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

from datasphere.native.evaluator_identity import family_eval_policy_mode  # noqa: E402


def test_ctrl_native_is_the_mode_because_its_released_evaluator_is_greedy():
    assert family_eval_policy_mode("ctrl") == "mode"

    source = ROOT / "runnable" / "ctrl" / "evaluate_ppo.py"
    if not source.is_file():
        pytest.skip(f"{source} is absent; run setup/bootstrap_sources.py --family ctrl")
    text = source.read_text()
    assert "greedy=True" in text, (
        "ctrl's released evaluator no longer selects greedily; the native policy mode was set to "
        "'mode' on the strength of that call and must be re-derived if it is gone")
    assert "argmax" in text


def test_sampling_families_are_the_ones_whose_evaluators_sample():
    for family in ("idaac", "ibac_sni", "ppg"):
        assert family_eval_policy_mode(family) == "sample", family
    for family in ("rlvigen", "dmc_gb", "alda", "ctrl"):
        assert family_eval_policy_mode(family) == "mode", family


def test_idaac_evaluator_does_not_ask_for_determinism():
    """`act(self, inputs, deterministic=False)` and test.py omits the flag."""
    model = ROOT / "runnable" / "idaac" / "ppo_daac_idaac" / "model.py"
    if not model.is_file():
        pytest.skip(f"{model} is absent")
    assert "def act(self, inputs, deterministic=False)" in model.read_text()


def test_ibac_sni_argmax_flag_defaults_off():
    """Its evaluator's `--argmax` is store_true, so the released default samples."""
    evaluate = ROOT / "runnable" / "ibac_sni" / "torch_rl" / "scripts" / "evaluate.py"
    if not evaluate.is_file():
        pytest.skip(f"{evaluate} is absent")
    text = evaluate.read_text()
    assert "--argmax" in text and "store_true" in text
