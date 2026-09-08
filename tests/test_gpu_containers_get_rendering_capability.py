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


# --- the second half: the driver library the old toolkit does not inject -------------------------
# [Claude 2026-09-09] `graphics` alone was necessary and not sufficient. Driver 580's
# `libnvidia-eglcore` depends on `libnvidia-gpucomp.so.<driver>`, which libnvidia-container only
# began injecting in 1.13.5; this host runs 1.13.2. Confirmed inside the container:
#     ldd libnvidia-eglcore.so.580.126.09 -> libnvidia-gpucomp.so.580.126.09 => not found
# MuJoCo reports "Cannot initialize a EGL device display ... EGL_EXT_platform_device", naming the
# wrong cause -- the extension is present; the vendor library cannot load. With the library
# supplied read-only the renderer became 'Tesla V100-SXM2-32GB/PCIe/SSE2'.


def test_the_wrapper_injects_the_missing_driver_library():
    text = WRAPPER.read_text()
    assert "libnvidia-gpucomp" in text, (
        "nothing supplies libnvidia-gpucomp, so on a host with toolkit < 1.13.5 the NVIDIA EGL "
        "vendor cannot load and rendering silently falls back to software")
    # The actual mount line, not the first mention -- the first mention is a comment.
    mounts = [l for l in text.splitlines()
              if "--mount" in l and "libnvidia-gpucomp" in l]
    assert mounts, "libnvidia-gpucomp is discussed but never mounted"
    for line in mounts:
        assert "readonly" in line, (
            f"the driver library must be mounted read-only; a writable mount of a host driver "
            f"component is the hazard 03-docker-discipline rule 3 exists to prevent: {line.strip()}")


def test_the_injected_library_is_pinned_to_the_running_driver():
    """A userspace driver library must match the kernel driver, or it is worse than the bug."""
    text = WRAPPER.read_text()
    block = text[text.index("NATIVE_INJECT_GPUCOMP"):][:1200]
    assert "nvidia-smi --query-gpu=driver_version" in block, (
        "the driver version is not read from the running driver")
    assert "libnvidia-gpucomp.so.$_drv" in block, "the library is not pinned to that version"
    assert "ldconfig -p" in block, "the path is guessed rather than resolved"


def test_it_is_a_single_file_never_a_directory():
    """The rule-3 carve-out is bounded to one file; a directory mount is the original hazard."""
    text = WRAPPER.read_text()
    block = text[text.index("NATIVE_INJECT_GPUCOMP"):][:1200]
    assert "dst=/usr/lib/x86_64-linux-gnu/libnvidia-gpucomp.so.$_drv" in block
    assert "src=/usr/lib\"" not in block and "src=/usr/lib," not in block


def test_a_host_without_the_library_is_not_fatal():
    """A newer toolkit injects it already; refusing there would break correct hosts."""
    block = WRAPPER.read_text()
    block = block[block.index("NATIVE_INJECT_GPUCOMP"):][:1400]
    assert "relying on the toolkit" in block, (
        "absence must be reported and tolerated -- the renderer check is what actually decides")


def test_the_runner_registers_the_egl_vendor_and_refreshes_the_loader():
    text = PROBE.read_text()
    assert "10_nvidia.json" in text, (
        "no NVIDIA EGL ICD is written, so libglvnd sees only 50_mesa.json and picks llvmpipe")
    assert "__EGL_VENDOR_LIBRARY_FILENAMES" in text, (
        "the ICD is written but not forced, so Mesa can still be selected")
    assert "ldconfig" in text, (
        "the loader cache predates the gpucomp bind mount, so the vendor cannot resolve")
    assert "NATIVE_EGL_DEPENDENCY_MISSING" in text, (
        "an unloadable EGL vendor must name itself; MuJoCo blames the wrong thing")
