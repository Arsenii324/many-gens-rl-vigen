"""Bound this process's GPU reservation, so a co-tenant's growth cannot be starved by ours.

Installed as `sitecustomize` by `run_probe.sh` when `NATIVE_VRAM_CAP_MIB` is set, so it applies at
interpreter start -- before any framework import, and without editing seven launchers.

## The asymmetry this exists for

A CUDA caching allocator reserves blocks from the driver and, in practice, never gives them back.
So a reservation is a FLOOR on a process's future usage, not a ceiling: it cannot shrink, and it
grows whenever a high-water mark is exceeded -- at an eval pass with a different batch, a
validation stage, a concurrent evaluator beside training.

On a shared card that produces a one-sided failure. Whoever asks the driver SECOND is the one that
fails. If we take the free memory first and a neighbour's allocator then asks for more, **their
process raises the OOM and ours never notices**. We would be the cause of a failure we could not
see, which is precisely the outcome `notes/production-host/02-absolute-prohibitions.md` forbids.

A headroom ratio does not protect against this, because it is computed from what the neighbour
holds NOW. A cap does, because it bounds what we can ever take regardless of what we later want.

## What it does, and what it deliberately does not

`torch.cuda.set_per_process_memory_fraction` makes an allocation beyond the cap raise
`torch.cuda.OutOfMemoryError` **in our process**. That is the point: our cell fails loudly and
theirs continues, which is the correct way round. A cell that dies against its own cap is a cell
whose bound was wrong, and that is a finding rather than an accident.

It does NOT cap anything outside PyTorch's allocator -- cuDNN workspaces, NCCL buffers and any
library allocating through the driver directly are outside it. The JAX side is handled separately
and by environment, in `run_probe.sh`: `XLA_PYTHON_CLIENT_PREALLOCATE=false` with
`XLA_PYTHON_CLIENT_MEM_FRACTION`.

Fails OPEN, with a loud marker, and never blocks a run: a cell that cannot cap itself must say so
rather than die, because the caller may have set a cap on a CPU-only step where it is meaningless.
"""
from __future__ import annotations

import os
import sys

#: [Claude 2026-09-09] An explicit marker so the runner can VERIFY this module is importable rather
#: than inferring it from a filename. The cap was silently discarded from PYTHONPATH for a day while
#: every run printed that it had been requested; "requested" and "in force" are different claims and
#: only one of them is checkable. This makes the checkable one exist.
_rlvigen_vram_cap = True

# Chain to any pre-existing sitecustomize before doing anything of our own. Shadowing another
# module of this name would be a silent, surprising side effect of setting an unrelated variable.
try:  # pragma: no cover - environment dependent
    import sitecustomize as _previous  # noqa: F401
except Exception:
    pass


def _apply() -> None:
    raw = os.environ.get("NATIVE_VRAM_CAP_MIB", "").strip()
    if not raw:
        return
    try:
        cap_mib = int(raw)
    except ValueError:
        print(f"=== NATIVE_VRAM_CAP_INVALID {raw!r} is not an integer; no cap applied ===",
              file=sys.stderr, flush=True)
        return
    if cap_mib <= 0:
        return
    try:
        import torch
    except Exception:
        return
    try:
        if not torch.cuda.is_available():
            return
        index = torch.cuda.current_device()
        total_mib = torch.cuda.get_device_properties(index).total_memory / (1024 * 1024)
        fraction = cap_mib / total_mib
        if fraction >= 1.0:
            print(f"=== NATIVE_VRAM_CAP_VACUOUS {cap_mib} MiB is not below the card's "
                  f"{total_mib:.0f} MiB; a cap that cannot bind is not a cap ===",
                  file=sys.stderr, flush=True)
            return
        torch.cuda.set_per_process_memory_fraction(fraction, index)
        print(f"=== NATIVE_VRAM_CAP_APPLIED {cap_mib} MiB "
              f"({fraction:.4f} of {total_mib:.0f} MiB) on cuda:{index} ===",
              file=sys.stderr, flush=True)
    except Exception as error:  # fail open, loudly
        print(f"=== NATIVE_VRAM_CAP_FAILED {type(error).__name__}: {error} ===",
              file=sys.stderr, flush=True)


_apply()
