"""The reported endpoint and the descriptive curve are different depths and must stay separable.

Before 2026-09-05 the runner had ONE `CURVE_EVAL_*` scope and no terminal grid on the training
path, so a training job produced intermediate rows and **no reportable endpoint**: the headline
number had to come from a separate offline job, paying a second bootstrap and moving a checkpoint
out of the container C95 says it must be evaluated in.

Sharing one scope forces a choice between a full grid at every stamp (12x the endpoint's cost) and
a shallow endpoint. Keeping them apart is what makes decision A20's costed middle option possible.

Both grids also label their rows, because they share `phase="offline-eval"` and a schema; without a
label nothing stops a shallow trajectory stamp being pooled with the reported number.
"""
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER = (ROOT / "datasphere" / "native" / "run_probe.sh").read_text()
GRID = (ROOT / "scripts" / "eval_grid.py").read_text()


def test_the_runner_has_a_terminal_grid_for_the_training_path():
    assert "run_endpoint_eval()" in RUNNER, (
        "no terminal grid: a training cell would finish with no reportable endpoint number"
    )
    assert "run_endpoint_eval " in RUNNER, "run_endpoint_eval is defined but never called"


def test_an_absent_endpoint_grid_is_announced_rather_than_silent():
    assert "NATIVE_NO_ENDPOINT_GRID" in RUNNER, (
        "a training cell that produced no endpoint grid must say so; an absent endpoint must not "
        "look the same as a completed one"
    )


def test_the_two_scopes_do_not_share_their_settings():
    endpoint = set(re.findall(r"ENDPOINT_EVAL_([A-Z]+)", RUNNER))
    curve = set(re.findall(r"CURVE_EVAL_([A-Z]+)", RUNNER))
    for axis in ("REGIMES", "SCENES", "EPISODES"):
        assert axis in endpoint, f"the endpoint grid has no independent {axis} setting"
        assert axis in curve, f"the curve grid has no independent {axis} setting"


def test_the_endpoint_default_is_the_full_reported_grid():
    """4 regimes x 10 scenes x 20 episodes is what families.json specifies for production."""
    assert "ENDPOINT_EVAL_REGIMES:-train,eval-easy,eval-medium,eval-hard" in RUNNER
    assert "ENDPOINT_EVAL_SCENES:-0,1,2,3,4,5,6,7,8,9" in RUNNER
    assert "ENDPOINT_EVAL_EPISODES:-20" in RUNNER


def test_both_grids_label_their_rows():
    assert "--eval-scope curve" in RUNNER, "curve rows are unlabelled"
    assert "--eval-scope" in RUNNER and "OFFLINE_EVAL_SCOPE:-endpoint" in RUNNER, (
        "endpoint rows are unlabelled"
    )
    assert '"--eval-scope"' in GRID and '"eval_scope": a.eval_scope' in GRID, (
        "eval_grid must accept the scope and stamp it into the record context"
    )


def test_every_record_context_carries_the_scope():
    """A context that omits it emits rows indistinguishable from the other scope's."""
    contexts = GRID.count('context = {"cell"')
    labelled = GRID.count('"eval_scope": a.eval_scope')
    assert contexts == labelled, (
        f"{contexts} record contexts but only {labelled} carry eval_scope; the unlabelled ones "
        "emit rows that cannot be told apart from the other scope's"
    )


def test_the_endpoint_does_not_inherit_the_curves_depth_or_grid():
    """A20 set the curve to 3 episodes. The endpoint must stay at 20.

    The offline/endpoint invocation used to fall back through the CURVE_EVAL_* variables:
    `${OFFLINE_EVAL_EPISODES:-${CURVE_EVAL_EPISODES:-20}}`, and likewise for regimes and scenes. So
    setting the curve's depth -- the one free parameter in A20 -- would silently have changed the
    depth of the measurement that carries the headline claim, whenever the endpoint's own variable
    happened to be unset. Two scopes, one knob, and the coupling ran in the damaging direction.
    """
    text = RUNNER
    assert '"${CURVE_EVAL_EPISODES:-3}"' in text, "A20's decided curve depth is 3"
    assert '"${OFFLINE_EVAL_EPISODES:-20}"' in text, "the endpoint depth is 20 and is its own number"
    for knob in ("EPISODES", "REGIMES", "SCENES"):
        assert f"${{OFFLINE_EVAL_{knob}:-${{CURVE_EVAL_{knob}" not in text, (
            f"the endpoint's {knob} still falls back to the curve's")
