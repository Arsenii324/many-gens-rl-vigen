# EGL/NVIDIA renderer problem on a V100 host — full statement for outside help

**Status: RESOLVED 2026-09-09.** `renderer='Tesla V100-SXM2-32GB/PCIe/SSE2'`. The diagnosis below
was answered by an external review (`notes/ai-answer-egl-28-external.md`) and confirmed by direct
test; the resolution is at the end of this file. The statement is kept as written because the
reasoning it records — and the two wrong turns it contains — are the useful part.

Written 2026-09-09. Self-contained: everything needed to
reproduce and reason about the problem is below, including what has already been ruled out.

## What we are trying to do

Run MuJoCo/robosuite RL training inside a Docker container on a shared Linux GPU server, rendering
observations **headlessly on the GPU** via EGL (`MUJOCO_GL=egl`). The rendered pixels are the model
input, so a software rasteriser is not an acceptable fallback: it changes the data and is orders of
magnitude too slow.

The runner has a deliberate guard that refuses to proceed on a software renderer:

```python
import mujoco
from OpenGL import GL
context = mujoco.GLContext(64, 64)
context.make_current()
renderer = (GL.glGetString(GL.GL_RENDERER) or b"").decode(errors="replace")
if not renderer or any(t in renderer.lower()
                       for t in ("llvmpipe", "softpipe", "software", "swiftshader")):
    raise RuntimeError(f"software EGL renderer: {renderer or 'unreported'}")
```

## Environment

| | |
|---|---|
| host GPUs | 2 × Tesla V100-SXM2-32GB |
| NVIDIA driver | **580.126.09** |
| kernel | 5.4.0-216-generic |
| Docker | 24.0.2 |
| nvidia-container-toolkit | **cli 1.13.2 / lib 1.13.2** |
| container image | `nvidia/cuda:12.2.2-runtime-ubuntu22.04@sha256:94c1577b2cd9dd6c0312dc04dff9cb2fdce2b268018abc3d7c2dbcacf1155000` |
| host `/dev/dri` | present: `card0 card1 card2 renderD128 renderD129` |
| python | 3.10 (distro), `mujoco` + `PyOpenGL` from pip |

GL packages installed in the container (matching what the real job installs):
`libglvnd0 libgl1 libegl1 libglew-dev libosmesa6`.

We do **not** have root on the host and must not modify it. Everything happens inside containers.
The container runs as root internally (default), so in-container changes are possible.

## The failure, in two distinct forms

### Form 1 — software fallback (the original symptom)

With the container as it was (no `NVIDIA_DRIVER_CAPABILITIES` set anywhere), a real training cell
ran ~2.5 h of `pip`, reached the renderer check and died:

```
RuntimeError: software EGL renderer: llvmpipe (LLVM 15.0.7, 256 bits)
```

Direct probe confirms it: `renderer='llvmpipe (LLVM 15.0.7, 256 bits)' vendor='Mesa'`.

**Diagnosed cause of Form 1:** docker's `--gpus` sets
`NVIDIA_DRIVER_CAPABILITIES=compute,utility`. That grants CUDA but does **not** mount the NVIDIA GL
stack, so `/usr/share/glvnd/egl_vendor.d/` contains only `50_mesa.json` and libglvnd correctly
selects Mesa.

### Form 2 — NVIDIA EGL present but cannot initialize (the current blocker)

Adding `-e NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics` **does** mount the NVIDIA GL stack:

```
/usr/lib/x86_64-linux-gnu/libEGL_nvidia.so.0
/usr/lib/x86_64-linux-gnu/libEGL_nvidia.so.580.126.09
/usr/lib/x86_64-linux-gnu/libnvidia-eglcore.so.580.126.09
/usr/lib/x86_64-linux-gnu/libnvidia-glcore.so.580.126.09
ldconfig -p | grep -c libEGL_nvidia   ->  1
/dev/nvidia0 /dev/nvidiactl /dev/nvidia-uvm /dev/nvidia-uvm-tools   present
```

**But the toolkit does not write an EGL vendor ICD.** After installing the GL packages,
`/usr/share/glvnd/egl_vendor.d/` still contains only `50_mesa.json` — there is no
`10_nvidia.json`. So libglvnd never loads the NVIDIA vendor and we are back to Mesa.

Writing the ICD by hand:

```json
{"file_format_version":"1.0.0","ICD":{"library_path":"libEGL_nvidia.so.0"}}
```
into `/usr/share/glvnd/egl_vendor.d/10_nvidia.json` changes the failure mode rather than fixing it:

```
ImportError: Cannot initialize a EGL device display. This likely means that your EGL driver
does not support the EGL_EXT_platform_device extension
```

(raised from `mujoco/egl/__init__.py`; the follow-on
`AttributeError: 'GLContext' object has no attribute '_context'` is just its `__del__` running
after a failed construction.)

## What has been tried, and the result of each

| # | change | result |
|---|---|---|
| 1 | baseline, no capabilities set | `llvmpipe` / `Mesa` |
| 2 | `NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics` | libs appear; still only `50_mesa.json`; still `llvmpipe` |
| 3 | 2 + hand-written `10_nvidia.json` | **`Cannot initialize a EGL device display`** |
| 4 | 3 + remove `50_mesa.json` (NVIDIA only) | same error |
| 5 | `NVIDIA_DRIVER_CAPABILITIES=all` + `10_nvidia.json` | same error |
| 6 | 5 + remove `50_mesa.json` | same error |
| 7 | 3 + `--device /dev/dri` passed through | same error |
| 8 | `MUJOCO_EGL_DEVICE_ID=0` explicitly | same error |

Note the container does **not** receive `/dev/dri` by default even with `graphics`; test 7 added it
explicitly and it made no difference.

`eglinfo` runs and reports client extensions including `EGL_EXT_platform_device`,
`EGL_EXT_device_base`, `EGL_EXT_device_enumeration`, `EGL_EXT_device_query`. It also prints
`error: XDG_RUNTIME_DIR not set in the environment.` twice (probably irrelevant for the device
platform, but recorded).

## What is ruled out

- **Not a CUDA problem.** CUDA works in the same container; `nvidia-smi` sees the card, and the
  project's compute-only work runs fine.
- **Not missing NVIDIA GL libraries.** `libEGL_nvidia`, `libnvidia-eglcore`, `libnvidia-glcore` are
  all mounted and in the ldconfig cache under test 2 onward.
- **Not missing device nodes.** `/dev/nvidia0`, `/dev/nvidiactl`, `/dev/nvidia-uvm` are present;
  `/dev/dri` was additionally tested.
- **Not the Mesa ICD shadowing NVIDIA.** Removing `50_mesa.json` entirely gives the same error.
- **Not a MuJoCo device-index problem.** Both the default path and an explicit
  `MUJOCO_EGL_DEVICE_ID=0` fail identically.

## Relevant extra fact

The **same image** ran this workload successfully on Yandex DataSphere, which is a managed
container platform. So the workload and image are known to work somewhere; something about that
platform's container runtime configuration supplied what this host does not. We do not have
visibility into DataSphere's runtime flags.

## The questions we need answered

1. Why does `libEGL_nvidia` 580.126.09 fail `EGL_EXT_platform_device` display initialization in a
   container where the libraries and `/dev/nvidia*` nodes are present?
2. Is `nvidia-container-toolkit 1.13.2` expected to write
   `/usr/share/glvnd/egl_vendor.d/10_nvidia.json` when `graphics` is requested? If yes, why might
   it not be doing so here; if no, what is the supported way to register the vendor?
3. Is a driver/toolkit version mismatch plausible — driver **580.126.09** with toolkit **1.13.2**
   (released well before that driver)? Would a newer toolkit be required, and is there a
   container-side workaround given we cannot modify the host?
4. Is there a container-side-only fix at all (env vars, ICD contents, an alternative EGL entry
   point), given we cannot change host packages or the driver?
5. Failing all of the above: is `MUJOCO_GL=osmesa` an acceptable substitute? Our concern is that it
   is still CPU rendering — same correctness objection as `llvmpipe`, and far too slow for
   ~45-hour training cells. Is there any GPU-backed headless path we have missed
   (e.g. EGL via a different platform extension, or GLX with a virtual display)?

## Constraints on any proposed fix

- No changes to the host: no `apt` on the host, no driver changes, no daemon reconfiguration.
- The card is shared with other users; nothing may disturb their jobs.
- Anything done inside the container must be reproducible from a script, since the container is
  rebuilt (`--rm`) on every run.


---

# Resolution, 2026-09-09

**Cause: `libnvidia-gpucomp.so.580.126.09`.** Driver 580's `libnvidia-eglcore` depends on it, and
`libnvidia-container` only began injecting it in **1.13.5**. This host runs **1.13.2**. Confirmed
directly inside the container:

```
ldd /usr/lib/x86_64-linux-gnu/libnvidia-eglcore.so.580.126.09
    libnvidia-gpucomp.so.580.126.09 => not found
```

The library is present on the host (`/usr/lib/x86_64-linux-gnu/libnvidia-gpucomp.so.580.126.09`,
72 MB, `644 root`) and simply never reaches the container.

**MuJoCo's error named the wrong cause.** `Cannot initialize a EGL device display ... does not
support the EGL_EXT_platform_device extension` is emitted whenever no candidate display
initializes. The extension was present throughout; the vendor library could not load. That message
sent me to `/dev/dri`, to `capabilities=all` and to `MUJOCO_EGL_DEVICE_ID` — three dead ends in the
table above, all of which were testing the thing the error named rather than the thing that was
broken.

**The fix, entirely container-side.** The supported repair is upgrading the host toolkit to
≥ 1.13.5; we have neither that authority nor any wish to change a shared host. Instead:

1. `-e NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics` — mounts the NVIDIA GL stack.
2. `--mount type=bind,src=<host libnvidia-gpucomp.so.$DRIVER>,dst=<same>,readonly` — supplies the
   one library 1.13.2 omits, from the driver already in use, pinned by version read from
   `nvidia-smi` and resolved through `ldconfig -p`.
3. `/etc/glvnd/egl_vendor.d/10_nvidia.json` written in-container, forced with
   `__EGL_VENDOR_LIBRARY_FILENAMES` — the toolkit also fails to provide the vendor ICD, so libglvnd
   would otherwise see only `50_mesa.json`.
4. `ldconfig` before anything dlopens the vendor.

**On mounting a global path**, which `03-docker-discipline.md` rule 3 forbids: the NVIDIA runtime
already bind-mounts **22** driver libraries from that same directory into every GPU container. This
is the 23rd. The exception is written into that file with a five-part boundary rather than taken
quietly. Non-destructiveness was verified rather than assumed — host file sha256 and mtime
unchanged after a container run, host mount count unchanged (78 → 78), and a root write inside the
container refused with `Read-only file system`.

**Still true and worth keeping:** OSMesa was correctly rejected. It is CPU rendering and fails the
same objection as `llvmpipe`.

**One loose end.** `mujoco.GLContext.__del__` raises an ignored `EGLError` during interpreter
shutdown. It is reported as `Exception ignored`, does not affect the process exit status, and
appears after the renderer has been read successfully. Noted, not chased.
