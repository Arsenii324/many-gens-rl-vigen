#!/usr/bin/env python3
"""How much does the MPS path change the numbers? A golden trace, not an argument.

    python scripts/probe_shim_divergence.py
    python scripts/probe_shim_divergence.py --steps 100

This is `docs/CONSTRUCTION.md` C41. `runnable/_shim/sitecustomize.py` downcasts float64 to float32
because MPS has no float64, and it *announces* that at runtime — but the size of the effect has
never been measured, only declared. Until it is, [C35]'s learning result is defensible as an
ordinal claim ("it learns") and not as a numerical one, and nothing bounds what an MPS number
would mean if it appeared in a table.

## Two separable questions, and they need different controls

**Q1 — does the dtype downcast matter?** Device-independent: run the same updates at float64 and
float32 on the SAME device. Nothing about MPS is involved, so this isolates the shim's *declared*
behaviour from the backend's.

**Q2 — do MPS kernels differ from CPU at the same dtype?** Run identical weights and identical
batches on both devices at float32. Any difference here is the backend, not the shim.

Reporting them together would confound the shim with the platform, which is the mistake this
whole project exists to avoid making.

## The question that actually decides transferability

Not *"do they differ"* — at float32 they always will, by reordered reductions alone. The question
is **whether the divergence stays bounded or grows**. Bounded means an MPS run is a noisy copy of
a CPU run and ordinal claims survive. Growing means the two are different trajectories after
enough steps, and no numerical claim transfers however small the first step looked.

So this reports divergence AS A FUNCTION OF STEP, and the ratio between the last and first, rather
than a single number at the end.

## What this cannot tell you

It uses a representative conv+MLP update, not any baseline's exact loss. It bounds what the
substrate does to a gradient trajectory; it does not prove a particular baseline is safe. And it
says nothing about CUDA, which is a third backend nobody here has measured at all.
"""
from __future__ import annotations

import argparse
import copy
import sys

import numpy as np
import torch
import torch.nn as nn


def build(seed: int, dtype, device):
    """Identical initial weights on every device: built once on CPU under a fixed seed."""
    torch.manual_seed(seed)
    m = nn.Sequential(
        nn.Conv2d(9, 32, 3, 2), nn.ReLU(),
        nn.Conv2d(32, 32, 3, 1), nn.ReLU(),
        nn.Flatten(),
        nn.Linear(32 * 39 * 39, 50), nn.LayerNorm(50), nn.Tanh(),
        nn.Linear(50, 1),
    )
    return m.to(device=device, dtype=dtype)


def trace(steps: int, seed: int, dtype, device: str, batch: int = 32):
    dev = torch.device(device)
    m = build(seed, dtype, dev)
    opt = torch.optim.Adam(m.parameters(), lr=1e-3)
    g = torch.Generator().manual_seed(seed + 1)          # data identical across runs
    losses = []
    for _ in range(steps):
        x = torch.rand(batch, 9, 84, 84, generator=g).to(device=dev, dtype=dtype)
        y = torch.rand(batch, 1, generator=g).to(device=dev, dtype=dtype)
        opt.zero_grad()
        loss = ((m(x) - y) ** 2).mean()
        loss.backward()
        opt.step()
        losses.append(float(loss.detach().cpu()))
    flat = torch.cat([p.detach().float().cpu().flatten() for p in m.parameters()])
    return np.array(losses), flat


def report(name, a, b, la, lb):
    rel = np.abs(la - lb) / np.maximum(np.abs(la), 1e-12)
    pd = float(torch.norm(a - b) / torch.norm(a))
    first = float(rel[0]) if len(rel) else float("nan")
    last = float(rel[-1]) if len(rel) else float("nan")
    growth = last / first if first > 0 else float("inf")
    print(f"\n  {name}")
    print(f"    loss rel-diff  step 1: {first:.3e}   step {len(rel)}: {last:.3e}"
          f"   growth: {growth:,.0f}x" if first > 0 else
          f"    loss rel-diff  step 1: {first:.3e}   step {len(rel)}: {last:.3e}")
    print(f"    final parameter relative L2: {pd:.3e}")
    q = np.quantile(rel, [0.5, 0.9, 1.0])
    print(f"    rel-diff median {q[0]:.3e}   p90 {q[1]:.3e}   max {q[2]:.3e}")
    return first, last, pd


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--steps", type=int, default=60)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    print(f"\nPROBE -- shim divergence, {a.steps} identical updates, seed {a.seed}")
    print(f"  torch {torch.__version__}   mps={torch.backends.mps.is_available()}")

    print("\n  Q1: does the float64 -> float32 downcast matter?  (CPU, same device, both dtypes)")
    l64, p64 = trace(a.steps, a.seed, torch.float64, "cpu")
    l32, p32 = trace(a.steps, a.seed, torch.float32, "cpu")
    report("cpu-float64  vs  cpu-float32", p64, p32, l64, l32)

    if torch.backends.mps.is_available():
        print("\n  Q2: do MPS kernels differ from CPU at the SAME dtype?  (both float32)")
        lm, pm = trace(a.steps, a.seed, torch.float32, "mps")
        report("cpu-float32  vs  mps-float32", p32, pm, l32, lm)
    else:
        print("\n  Q2 SKIPPED: no MPS. A SKIP is not a pass -- nothing about the backend was measured.")

    print("\n  Reading this: at float32 the two WILL differ -- reordered reductions alone guarantee")
    print("  it. What matters is whether the relative difference stays flat across steps (a noisy")
    print("  copy: ordinal claims survive) or grows by orders of magnitude (a different")
    print("  trajectory: no numerical claim transfers, however small step 1 looked).")
    print("\n  Not measured here: CUDA. It is a third backend and nobody in this project has a")
    print("  single datapoint from it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
