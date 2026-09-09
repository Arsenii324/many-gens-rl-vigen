"""The watch budget must cover the evaluation that is actually scheduled, including BOTH passes.

`CELL_TIMEOUT_SECONDS` wraps training only. Evaluation runs after it, and the failure a short
allowance causes is not a lost evaluation pass -- it is a lost DELIVERY, because
`collect_record_delivery` runs after evaluation and a reaped cell never reaches it. Every record of
a twelve-hour cell, unassembled.

Measured on the idaac 600k cell: 4.95h training, 4.60h curve, 5.52h endpoint -- the endpoint being
double because `ENDPOINT_EVAL_POLICY_MODES` defaults to `native,mode` and sweeps the whole grid
twice. The allowance was the training budget, 6h, against 10.12h of evaluation. That cell's endpoint
is projected to finish one minute inside its reaper.
"""
from __future__ import annotations

import pathlib
import re
import subprocess

LAUNCHER = pathlib.Path(__file__).resolve().parents[1] / "datasphere" / "native" / "launch-card-cell.sh"


def _derive(**env: str) -> tuple[int, str]:
    """Run only the allowance block, with the surrounding launcher's requirements stubbed."""
    text = LAUNCHER.read_text()
    start = text.index("_csv_count() {")
    end = text.index('-> ${_derived}s derived')
    block = text[start:text.index("\n", end) + 1]
    base = {"CELL_TIMEOUT_SECONDS": "21600", "FRAMES": "600000", "EVAL_EVERY_FRAMES": "50000"}
    base.update(env)
    assign = "\n".join(f'export {k}="{v}"' for k, v in base.items())
    proc = subprocess.run(["bash", "-c", assign + "\n" + block + '\necho "ALLOWANCE=$EVAL_ALLOWANCE"'],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout + proc.stderr
    return int(re.search(r"ALLOWANCE=(\d+)", out).group(1)), out


PRODUCTION = dict(
    CURVE_EVAL_REGIMES="train,eval-easy,eval-medium,eval-hard",
    CURVE_EVAL_SCENES="0,1,2,3,4,5,6,7,8,9", CURVE_EVAL_EPISODES="3",
    ENDPOINT_EVAL_REGIMES="train,eval-easy,eval-medium,eval-hard",
    ENDPOINT_EVAL_SCENES="0,1,2,3,4,5,6,7,8,9", ENDPOINT_EVAL_EPISODES="20",
)


def test_the_allowance_covers_the_measured_evaluation():
    """10.12h of evaluation actually ran. The allowance must exceed it."""
    allowance, out = _derive(**PRODUCTION, ENDPOINT_EVAL_POLICY_MODES="native,mode")
    assert allowance > 10.12 * 3600, f"{allowance}s does not cover the 10.12h that ran:\n{out}"


def test_the_allowance_beats_the_old_default_that_was_69_percent_short():
    allowance, _ = _derive(**PRODUCTION, ENDPOINT_EVAL_POLICY_MODES="native,mode")
    assert allowance > 21600, "the old default was the training budget and it was 69% short"


def test_a_second_policy_mode_raises_the_allowance():
    """The missed term. `native,mode` sweeps the endpoint grid TWICE."""
    one, _ = _derive(**PRODUCTION, ENDPOINT_EVAL_POLICY_MODES="native")
    two, _ = _derive(**PRODUCTION, ENDPOINT_EVAL_POLICY_MODES="native,mode")
    assert two > one, "adding a policy mode doubles the endpoint grid and must raise the allowance"


def test_more_episodes_raise_the_allowance():
    few, _ = _derive(**dict(PRODUCTION, ENDPOINT_EVAL_EPISODES="5"),
                     ENDPOINT_EVAL_POLICY_MODES="native")
    many, _ = _derive(**dict(PRODUCTION, ENDPOINT_EVAL_EPISODES="40"),
                      ENDPOINT_EVAL_POLICY_MODES="native")
    assert many > few


def test_it_never_falls_below_the_previous_default():
    """A tiny evaluation must not shrink the budget below what shipped before."""
    allowance, _ = _derive(CURVE_EVAL_REGIMES="train", CURVE_EVAL_SCENES="0",
                           CURVE_EVAL_EPISODES="1", ENDPOINT_EVAL_REGIMES="train",
                           ENDPOINT_EVAL_SCENES="0", ENDPOINT_EVAL_EPISODES="1",
                           ENDPOINT_EVAL_POLICY_MODES="native", FRAMES="2000")
    assert allowance >= 21600, "floored at CELL_TIMEOUT_SECONDS; this can only be more generous"


def test_an_explicit_override_still_wins():
    allowance, _ = _derive(**PRODUCTION, ENDPOINT_EVAL_POLICY_MODES="native,mode",
                           NATIVE_EVAL_ALLOWANCE_SECONDS="1234")
    assert allowance == 1234
