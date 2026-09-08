#!/usr/bin/env python3
"""Does `datasphere/native/vram_cap.py` actually bind, and what sits OUTSIDE it?

    python3 scripts/verify_vram_cap.py            # caps at 512 MiB, allocates at most 256

## Why this exists as a script rather than a claim

`vram_cap.py` was written, committed and documented as a safety mechanism before anything checked
that it works. Importing it on a CPU-only machine proves only that it does not crash. A cap that
is asserted and not exercised is the same shape as every other instrument this project has had to
go back and verify.

## What it costs, stated because it runs on a shared card

It sets the cap to 512 MiB and makes exactly one real allocation of **256 MiB**. The second
allocation asks for 1024 MiB, and the point is that **torch refuses it internally**: the caching
allocator checks the fraction limit before calling `cudaMalloc`, so the driver is never asked. If
that request ever reaches the driver, the cap has failed -- which is precisely what this detects.

Peak driver-visible usage is therefore the CUDA context (~300 MiB on a V100) plus 256 MiB, for a
few seconds. A per-process OOM raises a Python exception in this process and cannot disturb a
co-tenant.

## The residual it measures

`set_per_process_memory_fraction` bounds PyTorch's allocator and nothing else. Outside it sit the
CUDA context, cuBLAS/cuDNN handle workspaces, and -- the one that matters for this project --
**EGL/OpenGL rendering buffers**, because `MUJOCO_GL=egl` renders every observation on the GPU
through the graphics pipeline rather than through CUDA. This script measures the context and the
allocator's over-reserve; the rendering share only appears once an environment is stepping.
"""
from __future__ import annotations

import os
import subprocess
import sys

MIB = 1024 * 1024


def card_used_mib() -> int:
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used",
                          "--format=csv,noheader,nounits"], capture_output=True, text=True)
    return int(out.stdout.strip().splitlines()[0])


def main() -> int:
    cap_mib = int(os.environ.get("NATIVE_VRAM_CAP_MIB", "512"))
    os.environ["NATIVE_VRAM_CAP_MIB"] = str(cap_mib)
    base = card_used_mib()
    print(f"  card used before this process touches CUDA: {base} MiB")

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.join(here, "datasphere", "native"))
    import torch
    print(f"  torch {torch.__version__}  cuda_available={torch.cuda.is_available()}")
    if not torch.cuda.is_available():
        print("  no CUDA here; nothing to verify.")
        return 0

    import vram_cap  # noqa: F401  -- prints NATIVE_VRAM_CAP_APPLIED

    torch.cuda.init()
    after_ctx = card_used_mib()
    print(f"  card after CUDA context: {after_ctx} MiB  -> CONTEXT COSTS {after_ctx - base} MiB "
          f"(outside the cap, invisible to memory_allocated)")

    print(f"\n  1. allocate 256 MiB, under the {cap_mib} MiB cap -- expect success")
    keep = torch.empty(256 * MIB // 4, dtype=torch.float32, device="cuda")
    print(f"     ok.  allocated={torch.cuda.memory_allocated()//MIB} "
          f"reserved={torch.cuda.memory_reserved()//MIB} MiB   card={card_used_mib()} MiB")

    print(f"\n  2. request 1024 MiB, past the cap -- torch must refuse WITHOUT asking the driver")
    verdict = 1
    try:
        _ = torch.empty(1024 * MIB // 4, dtype=torch.float32, device="cuda")
        print(f"     *** NO ERROR: THE CAP DID NOT BIND. card={card_used_mib()} MiB ***")
    except torch.cuda.OutOfMemoryError as error:
        print("     OutOfMemoryError raised IN THIS PROCESS, as designed.")
        print(f"     {str(error).splitlines()[0][:160]}")
        verdict = 0
    except Exception as error:
        print(f"     {type(error).__name__}: {str(error)[:160]}")

    peak_alloc = torch.cuda.max_memory_allocated() // MIB
    peak_res = torch.cuda.max_memory_reserved() // MIB
    now = card_used_mib()
    print(f"\n  PEAKS   max_memory_allocated={peak_alloc} MiB   max_memory_reserved={peak_res} MiB")
    print(f"          allocator OVER-RESERVE = {peak_res - peak_alloc} MiB "
          f"(the cap binds on RESERVED, so fragmentation eats it)")
    print(f"  RESIDUAL outside the cap = {now - base - peak_res} MiB "
          f"(CUDA context and anything not using torch's allocator)")
    del keep
    return verdict


if __name__ == "__main__":
    raise SystemExit(main())
