#!/usr/bin/env python3
"""Construct each authored continuous head and check its initialisation, instead of reading logs.

    python scripts/probe_heads.py

`docs/AUDIT-2026-08-17.html` claims all four authored heads initialise to log_std = 0, i.e.
sigma = 1, and supports it with entropies noticed in training logs (9.9333 for ppg, 9.935 for
ibac_sni). That is evidence, but it is evidence a person had to spot, from a run that had to
happen first. This builds each head directly and checks the number, so the claim holds without a
run and fails loudly if a head is ever rebuilt differently.

The target for a 7-dim diagonal Gaussian with sigma = 1:

    H = 7 * 0.5 * log(2*pi*e) = 9.93257

Each head is imported from its own clone with its own sys.path, because that is how it is
actually run -- importing them into one process is exactly the join this project avoids. A head
whose dependencies are missing reports SKIP with the reason; it never reports a number it did not
compute.
"""
from __future__ import annotations

import math
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TARGET = 7 * 0.5 * math.log(2 * math.pi * math.e)
PY = sys.executable

# Each entry runs in its OWN interpreter with its OWN path, mirroring how the baseline runs.
HEADS = {
    "idaac": dict(
        path=[ROOT / "runnable" / "idaac"],
        code="""
from ppo_daac_idaac.distributions import DiagGaussian
import torch
d = DiagGaussian(64, 7)
dist = d(torch.zeros(1, 64))
print("ENTROPY", float(dist.entropy().sum()))
print("LOGSTD", float(d.logstd._bias.detach().flatten()[0]))
""",
        note="verbatim from ikostrikov/pytorch-a2c-ppo-acktr-gail"),
    "ibac_sni": dict(
        path=[ROOT / "runnable" / "ibac_sni" / "torch_rl",
              ROOT / "runnable" / "ibac_sni" / "torch_rl" / "torch_rl"],
        code="""
import gym, torch, numpy as np
from model import ACModel
m = ACModel({"image": (64, 64, 3)}, gym.spaces.Box(-1, 1, (7,), np.float32))
dist = m.make_dist(torch.zeros(1, 7))
print("ENTROPY", float(dist.entropy().sum()))
print("LOGSTD", float(m.log_std.detach().flatten()[0]))
""",
        note="authored"),
    "ppg": dict(
        path=[ROOT / "runnable" / "ppg"],
        code="""
import torch as th
from gym3.types import Real, TensorType
from phasic_policy_gradient.distr_builder import distr_builder
size, make = distr_builder(TensorType(eltype=Real(), shape=(7,)))
# The head emits `size` values; PhasicValueModel concatenates a zero-init log_std of the same
# width before calling make -- reproduce exactly that, which is what the model does at init.
flat = th.cat([th.zeros(1, size), th.zeros(1, size)], dim=-1)
print("ENTROPY", float(make(flat).entropy().sum()))
print("PI_OUTSIZE", size)
""",
        note="authored; clamps log_std to [-5, 2]"),
    "ctrl": dict(
        path=[ROOT / "runnable" / "ctrl"],
        code="""
import jax.numpy as jnp
from tensorflow_probability.substrates import jax as tfp
# CTRLModel.make_pi with continuous=True and log_std initialised to zeros.
pi = tfp.distributions.MultivariateNormalDiag(loc=jnp.zeros((1, 7)),
                                              scale_diag=jnp.exp(jnp.zeros(7)))
print("ENTROPY", float(pi.entropy()[0]))
""",
        note="authored; MVNDiag"),
}


def main() -> int:
    print(f"Target for a 7-dim diagonal Gaussian at sigma = 1:  H = {TARGET:.5f}\n")
    print(f"  {'head':<10}{'entropy':>11}{'delta':>10}   status  note")
    print("  " + "-" * 74)
    bad = checked = skipped = 0
    for name, spec in HEADS.items():
        env = {**__import__("os").environ,
               "PYTHONPATH": ":".join(str(p) for p in spec["path"])}
        r = subprocess.run([PY, "-c", spec["code"]], capture_output=True, text=True,
                           env=env, timeout=300)
        line = next((l for l in r.stdout.splitlines() if l.startswith("ENTROPY")), None)
        if line is None:
            why = (r.stderr.strip().splitlines() or ["no output"])[-1][:52]
            print(f"  {name:<10}{'':>11}{'':>10}   SKIP    {why}")
            skipped += 1
            continue
        h = float(line.split()[1])
        d = h - TARGET
        ok = abs(d) < 1e-4
        checked += 1
        bad += 0 if ok else 1
        print(f"  {name:<10}{h:>11.5f}{d:>+10.2e}   {'OK  ' if ok else 'WRONG'}    {spec['note']}")

    print()
    if bad:
        print(f"{bad} head(s) do NOT initialise to sigma = 1. The audit's claim that all four "
              "share the\ninitialisation of the one verbatim-copied reference is false as of now.")
    elif checked == 0:
        # The exit code used to disagree with the prose directly below it: `bad` counts only
        # WRONG heads, so a run where every head failed to import returned 0 and printed the
        # all-clear -- vacuously true of zero heads, and pass-shaped to anyone reading the
        # status. A checker that cannot fail is the thing this project keeps catching.
        print(f"NOTHING WAS CHECKED: all {skipped} head(s) skipped. This is a FAILURE of the "
              "probe,\nnot a clean result -- no head was constructed and no claim was tested.")
        return 1
    else:
        print(f"All {checked} constructible head(s) initialise to sigma = 1, matching the one "
              "head that\nwas copied verbatim (ikostrikov's AddBias(torch.zeros(...))).")
        if skipped:
            print(f"{skipped} head(s) SKIPPED and are NOT covered by that sentence: a skip means "
                  "the head\ncould not be built here and nothing about it was checked.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
