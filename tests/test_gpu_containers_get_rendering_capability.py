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


def _gpucomp_block(text: str) -> str:
    """The whole gpucomp guard, not a fixed number of characters.

    [Claude 2026-09-09] These slices were 1200 chars and the explanatory comment above the mount
    grew past that, so the assertions stopped seeing the code they were about and failed on
    correct source. A window measured in characters is a window that expires.
    """
    start = text.index("NATIVE_INJECT_GPUCOMP")
    end = text.index("DOCKER_MOUNT_ARGS=(-v", start)
    return text[start:end]


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
    block = _gpucomp_block(text)
    assert "nvidia-smi --query-gpu=driver_version" in block, (
        "the driver version is not read from the running driver")
    assert "libnvidia-gpucomp.so.$_drv" in block, "the library is not pinned to that version"
    assert "ldconfig -p" in block, "the path is guessed rather than resolved"


def test_it_is_a_single_file_never_a_directory():
    """The rule-3 carve-out is bounded to one file; a directory mount is the original hazard."""
    text = WRAPPER.read_text()
    block = _gpucomp_block(text)
    assert "dst=/usr/lib/x86_64-linux-gnu/libnvidia-gpucomp.so.$_drv" in block
    assert "src=/usr/lib\"" not in block and "src=/usr/lib," not in block


def test_a_host_without_the_library_is_not_fatal():
    """A newer toolkit injects it already; refusing there would break correct hosts."""
    block = _gpucomp_block(WRAPPER.read_text())
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


def test_the_driver_lookup_survives_a_multi_gpu_host():
    """`nvidia-smi | head -1` on a two-GPU host kills the whole wrapper.

    [Claude 2026-09-09] Observed as a bare `CELL EXIT=141` with no other output. `head` exits after
    the first of two lines, `nvidia-smi` takes SIGPIPE, `set -o pipefail` reports 141 and `set -e`
    aborts run_on_production_host.sh before it validates anything. Third variant of the same family
    tonight, after `cmd | tail` swallowing an exit status and `grep '^FAILED'` on coloured pytest
    output -- a filter that finishes early, and a status read through it.

    Executed with a stub `nvidia-smi` that prints TWO lines, which is what the real host does.
    """
    import subprocess
    import textwrap

    text = WRAPPER.read_text()
    start = text.index('_drv="$(nvidia-smi')
    end = text.index("\n", text.index('_drv="${_drv//', start))
    snippet = textwrap.dedent(text[start:end])

    import tempfile, os, pathlib as _p
    with tempfile.TemporaryDirectory() as tmp:
        stub = _p.Path(tmp) / "nvidia-smi"
        stub.write_text("#!/bin/sh\nprintf '580.126.09\\n580.126.09\\n'\n")
        stub.chmod(0o755)
        script = (f"set -euo pipefail\nexport PATH={tmp}:$PATH\n"
                  f"{snippet}\nprintf 'DRV[%s]\\n' \"$_drv\"\n")
        out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=60)

    assert out.returncode == 0, (
        f"the driver lookup aborts on a multi-GPU host (rc={out.returncode}); "
        f"141 means SIGPIPE\n{out.stdout}{out.stderr}")
    assert "DRV[580.126.09]" in out.stdout, out.stdout + out.stderr
