"""ppg's deterministic action rule must run under `no_grad`, and this executes it to prove it.

## The production failure this reproduces

`card0-20260909-115331` trained ppg-s1 for 3.6 hours, emitted 572 curve rows, completed 44 of 88
endpoint rows in the SAMPLED pass, then died 9 seconds into the MODE pass:

    File "scripts/eval_grid.py", line 660, in run_scene_ppg
        roller.multi_step(32)
      ...
      File "runnable/ppg/phasic_policy_gradient/torch_util.py", line 324, in th2np
        return tharr.cpu().numpy()
    RuntimeError: Can't call numpy() on Tensor that requires grad.
                  Use tensor.detach().numpy() instead.

The sampled pass worked and the mode pass did not, from the same checkpoint in the same process.
The asymmetry is the whole diagnosis: `PpoModel.act` carries `@tu.no_grad`
(`runnable/ppg/phasic_policy_gradient/ppg.py:26`), the sampled path calls it, and the mode path
replaced it with a direct `forward` call -- taking the behaviour and leaving the decorator.

## Why the test executes rather than greps

A text check ("`no_grad` appears in the mode branch") would pass on a version where the context
manager wrapped the wrong lines, and would fail on a correct version that spelled it differently.
The property is that the action tensor survives `th2np`, so the test calls `th2np`'s exact
expression on the real function's real output. It needs no GPU, no robosuite and no checkpoint.

A second test anchors the diagnosis OUTSIDE our own code: it reads the vendored source and
requires `act` to still be decorated. If upstream ever drops that decorator, the sampled path
acquires the same defect, and this file says so rather than the next production cell saying it.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("scripts", "datasphere/native", "runnable/ppg"):
    sys.path.insert(0, str(ROOT / extra))

torch = pytest.importorskip("torch")


class _Pd:
    """Stands in for the Normal head; only `.mean` is read by the rule under test."""

    def __init__(self, mean):
        self.mean = mean


class _Model(torch.nn.Module):
    """A model whose output carries grad exactly as the real policy head's does.

    The parameter is the point: without it `pd.mean` would be a plain tensor and the test would
    pass against the broken code, which is the failure mode this whole file exists to avoid.
    """

    def __init__(self):
        super().__init__()
        self.w = torch.nn.Parameter(torch.ones(1, 1, 4))

    def forward(self, ob, first, state_in):
        mean = self.w * ob.sum()          # (1, 1, 4), requires grad outside no_grad
        vpred = self.w.sum().reshape(1, 1)
        return _Pd(mean), vpred, {}, state_in


def _act():
    from eval_grid import ppg_mode_act_fn
    return ppg_mode_act_fn(_Model())


def test_the_mode_action_survives_th2np():
    """`torch_util.th2np` is literally `tharr.cpu().numpy()`; call it on the real output."""
    action, _state, _extra = _act()(
        ob=torch.ones(1, 3), first=torch.zeros(1, dtype=torch.bool), state_in=None)
    try:
        array = action.cpu().numpy()          # exactly what th2np does
    except RuntimeError as exc:                # pragma: no cover -- this IS the regression
        pytest.fail(
            f"the mode action rule reproduces the card0-20260909-115331 failure: {exc}\n"
            f"PpoModel.act carries @tu.no_grad (ppg.py:26); an override standing in for it must "
            f"carry that decorator too."
        )
    assert array.shape == (1, 4)


def test_the_mode_action_does_not_require_grad():
    action, _state, extra = _act()(
        ob=torch.ones(1, 3), first=torch.zeros(1, dtype=torch.bool), state_in=None)
    assert action.requires_grad is False
    assert extra["vpred"].requires_grad is False
    assert extra["logp"].requires_grad is False


def test_the_test_would_have_caught_it():
    """Guard the guard: the stub must actually produce a grad-carrying tensor outside no_grad."""
    model = _Model()
    pd, vpred, _aux, _state = model(ob=torch.ones(1, 1, 3),
                                    first=torch.zeros(1, 1, dtype=torch.bool), state_in=None)
    assert pd.mean.requires_grad is True and vpred.requires_grad is True
    with pytest.raises(RuntimeError, match="requires grad"):
        pd.mean.cpu().numpy()


def test_upstream_still_decorates_the_method_the_override_replaces():
    """The diagnosis anchored on vendored source, not on ours."""
    source = (ROOT / "runnable/ppg/phasic_policy_gradient/ppg.py").read_text()
    assert re.search(r"@tu\.no_grad\s*\n\s*def act\(", source), (
        "PpoModel.act is no longer decorated with @tu.no_grad. The SAMPLED evaluation path relies "
        "on that decorator; if it is gone, ppg's sampled rows have the same defect the mode rows "
        "had, and eval_grid.run_scene_ppg must supply no_grad for both paths."
    )


def test_the_other_two_mode_families_still_have_their_no_grad():
    """The sweep that found ppg was the only broken one, kept as a check rather than a claim.

    idaac's `act` is undecorated (`ppo_daac_idaac/model.py:332`), so the HARNESS wraps it.
    ibac_sni's `Agent.get_actions` holds its own. Either moving is the same class of defect.
    """
    grid = (ROOT / "scripts/eval_grid.py").read_text()
    idaac_call = grid.index("agent.act(obs, deterministic=(policy_mode ==")
    assert "with torch.no_grad():" in grid[idaac_call - 400:idaac_call], (
        "run_scene_idaac no longer wraps agent.act in no_grad, and idaac's act is undecorated"
    )
    agent_src = (ROOT / "runnable/ibac_sni/torch_rl/utils/agent.py").read_text()
    assert "with torch.no_grad():" in agent_src
