"""A GPU container must be given the `graphics` driver capability, or EGL falls back to software.

[Claude 2026-09-08] From the first cell that got past `pip` on the production host. It spent over
two hours bootstrapping and then died at the renderer check with:

    RuntimeError: software EGL renderer: llvmpipe (LLVM 15.0.7, 256 bits)

`llvmpipe` is Mesa's CPU rasteriser. The container had CUDA and no NVIDIA EGL, so every rendered
observation would have been produced by software -- different pixels from every result this project
has, and orders of magnitude slower. `run_probe.sh` refused, which is the behaviour that turned a
silent wrong-answer into a stopped job.

The cause was a docker default that nothing in this repo had ever set. `--gpus` alone yields
`NVIDIA_DRIVER_CAPABILITIES=compute,utility`; `graphics` is the capability that installs
`libEGL_nvidia`. Measured on the host, same image, same card:

    default     compute,utility            -> no libEGL_nvidia
    +graphics   compute,utility,graphics   -> libEGL_nvidia.so.580.126.09

DataSphere set this for us, which is why it appeared only on the first real host cell. That is the
general lesson worth keeping: a platform default the project never wrote down is invisible until
the platform changes.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "datasphere" / "native" / "run_on_production_host.sh"
PROBE = ROOT / "datasphere" / "native" / "run_probe.sh"


def test_the_wrapper_requests_the_graphics_capability():
    text = WRAPPER.read_text()
    assert "NVIDIA_DRIVER_CAPABILITIES" in text, (
        "nothing sets NVIDIA_DRIVER_CAPABILITIES, so docker defaults to compute,utility and EGL "
        "falls back to llvmpipe")
    match = re.search(r'NVIDIA_DRIVER_CAPABILITIES=\$\{NATIVE_DRIVER_CAPABILITIES:-([a-z,]+)\}', text)
    assert match, "the capability set is not a documented default with an override"
    assert "graphics" in match.group(1).split(","), (
        f"capabilities {match.group(1)!r} omit `graphics`, which is the one that matters")


def test_it_is_attached_to_the_gpu_arguments_not_the_cpu_path():
    """A CPU-only run has no driver to ask, so the flag belongs with the GPU arguments."""
    text = WRAPPER.read_text()
    gpu_at = text.index('DOCKER_GPU_ARGS=(--gpus "$DOCKER_GPUS")')
    cap_at = text.index("DOCKER_GPU_ARGS+=(-e \"NVIDIA_DRIVER_CAPABILITIES=")
    assert cap_at > gpu_at
    none_branch = text[text.index('if [[ "$DOCKER_GPUS" == "none" ]]; then'):gpu_at]
    assert "NVIDIA_DRIVER_CAPABILITIES" not in none_branch, (
        "the capability is set on the CPU-only path, where there is no driver to request it from")


def test_the_renderer_check_still_exists_to_catch_the_next_one():
    """The fix is a default; the check is what makes a future regression loud instead of silent."""
    text = PROBE.read_text()
    assert "software EGL renderer" in text, (
        "the renderer check is gone -- a software rasteriser would now produce results silently")
