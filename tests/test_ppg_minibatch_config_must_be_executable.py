"""A declared `nminibatch` that the geometry cannot run must fail, not be silently substituted.

## What happened

`minibatch_optimize` splits the LEADING axis of the rollout, and `Roller.singles_to_multi`
documents that axis as `(batch, time)` -- so `ntrain` is `num_envs`, never `num_envs * nstep`. At
`num_envs=1` any `nminibatch > 1` is inexpressible. Upstream logged
`Warning: nminibatch > ntrain!! (32 > 1)` and set `nminibatch = ntrain`.

On `card0-20260909-115331` that warning printed **293 times** while the cell ran 600,000 frames
declaring `--nminibatch 32` and executing 1. A record whose config says 32 and whose trainer did 1
cannot support a claim about either number, so the substitution is now fatal.

## Why the answer was 1 and not "raise num_envs"

Arithmetic, not taste. PPG's released 1-rank recipe is `64x256 = 16384` with 1 epoch x 8
minibatches -- **8 gradient steps of 2048 samples**, `0.00048828` steps per env frame. Our
`num_envs=1, nstep=2048, nminibatch=1` is **1 gradient step of 2048 samples** per 2048 frames --
`0.00048828` per env frame. Density *and* per-step batch size are identical to the release.
Declaring 32 would have been **32x** upstream density at 64 samples per step.

So the executed run was already a faithful PPG and only the declaration was false. Fixing the
declaration costs no GPU time; "fixing" the geometry would have invented a rollout shape
(`32x64`) that appears in neither PPG's code nor raileanu21a-supp.pdf SS E.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runnable" / "ppg"))

torch = pytest.importorskip("torch")


class _Comm:
    """Enough of an MPI communicator for `minibatch_optimize`."""

    def allgather(self, value):
        return [value]


def _optimise(nminibatch, num_envs, nstep=8):
    from phasic_policy_gradient.minibatch_optimize import minibatch_optimize
    tensordict = {"x": torch.zeros(num_envs, nstep, 2)}
    return minibatch_optimize(
        lambda **mb: {"loss": 0.0},
        tensordict,
        nepoch=1,
        nminibatch=nminibatch,
        comm=_Comm(),
    )


def test_an_inexpressible_nminibatch_raises(tmp_path):
    with pytest.raises(ValueError, match="exceeds ntrain"):
        _optimise(nminibatch=32, num_envs=1)


def test_the_error_names_the_axis_and_the_file_to_edit():
    with pytest.raises(ValueError) as excinfo:
        _optimise(nminibatch=32, num_envs=1)
    message = str(excinfo.value)
    assert "environment" in message and "families.json" in message, message


def test_an_expressible_nminibatch_still_runs():
    assert _optimise(nminibatch=1, num_envs=1) is not None
    assert _optimise(nminibatch=4, num_envs=8) is not None


def test_families_json_declares_a_value_this_geometry_can_execute():
    """The config and the guard must agree, or the guard fires in production instead of here."""
    import json
    doc = json.loads((ROOT / "datasphere" / "native" / "families.json").read_text())

    def find(node):
        if isinstance(node, dict):
            if "ppg" in node and isinstance(node["ppg"], dict) and "constants" in node["ppg"]:
                return node["ppg"]["constants"]
            for value in node.values():
                found = find(value)
                if found is not None:
                    return found
        return None

    constants = find(doc)
    assert constants is not None, "ppg constants block not found"
    num_envs = int(constants["num_envs"])
    nminibatch = int(constants["nminibatch"])
    assert nminibatch <= num_envs, (
        f"families.json declares nminibatch={nminibatch} at num_envs={num_envs}; "
        f"minibatch_optimize now raises on that rather than clamping, so every ppg cell would "
        f"die at its first optimisation call"
    )
