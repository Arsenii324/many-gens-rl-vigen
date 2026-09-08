The most likely root cause is a concrete NVIDIA userspace-driver dependency that your host’s old container toolkit does not inject:

**driver 580.126.09 needs `libnvidia-gpucomp.so.580.126.09`, while `libnvidia-container 1.13.2` predates support for injecting that library.**

That fits your failure extremely well. Your statement confirms that the container receives `libEGL_nvidia`, `libnvidia-eglcore`, and `libnvidia-glcore`, but does not mention `libnvidia-gpucomp`; after manually registering the NVIDIA EGL ICD, MuJoCo gets past the Mesa-selection problem and then fails while attempting to initialize the NVIDIA vendor. 

### What is actually happening

There are two independent problems.

The first one is exactly what you already diagnosed: with Docker's default `compute,utility`, the NVIDIA graphics stack is not injected, so GLVND sees Mesa and you get `llvmpipe`. Your statement captures that correctly.  NVIDIA's documentation confirms that `graphics` is the capability required for OpenGL/EGL/Vulkan, while the default capabilities are just `compute,utility`. 

The second failure is more subtle. NVIDIA announced `libnvidia-gpucomp.so` as a new driver component and specifically stated that `libnvidia-eglcore.so`, `libnvidia-glcore.so`, and `libnvidia-rtcore.so` would depend on it. NVIDIA explicitly warned projects that maintain explicit lists of driver libraries—including GPU container runtimes—to add this library. 

Your 580.126.09 driver does indeed contain `libnvidia-gpucomp.so.580.126.09` as part of the graphics-driver userspace stack. 

The key version detail is that NVIDIA Container Toolkit **1.13.5 added `libnvidia-gpucomp.so` to its injected libraries**. Your server is using **1.13.2**. 

So this is not merely a hypothetical “580 might be too new for 1.13.2” incompatibility. There is a known, specific library that 1.13.2 does not know about and newer toolkit versions were changed to inject.

MuJoCo's error then obscures the real problem. Current MuJoCo code attempts `eglQueryDevicesEXT()`, `eglGetPlatformDisplayEXT(EGL_PLATFORM_DEVICE_EXT, ...)`, and `eglInitialize()`. If none of the candidate displays initializes, it emits:

> `Cannot initialize a EGL device display...`

That message does **not** establish that `EGL_EXT_platform_device` is absent. A vendor library that fails to load completely, or an `eglInitialize()` failure caused by a missing NVIDIA dependency, reaches the same message. 

That also explains why `eglinfo` listing `EGL_EXT_platform_device` did not settle the issue.

## Confirm it before changing anything

Run this in the failing container with `graphics` enabled and your manually supplied NVIDIA ICD:

```bash
set -eux

EGLCORE="$(ldconfig -p |
  awk '/libnvidia-eglcore\.so\.580\.126\.09/ {print $NF; exit}')"

echo "eglcore=$EGLCORE"

ls -l /usr/lib/x86_64-linux-gnu/libnvidia-gpucomp.so* \
      /lib/x86_64-linux-gnu/libnvidia-gpucomp.so* 2>/dev/null || true

readelf -d "$EGLCORE" | grep -E 'NEEDED|gpucomp' || true

ldd "$EGLCORE" | grep -E 'gpucomp|not found' || true
```

I expect one of these two outcomes:

```text
libnvidia-gpucomp.so.580.126.09 => not found
```

or simply no `libnvidia-gpucomp.so.580.126.09` anywhere in the container.

For an even stronger confirmation:

```bash
LD_DEBUG=libs \
__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/10_nvidia.json \
MUJOCO_GL=egl \
python3 - <<'PY' 2>/tmp/egl-loader.log
import mujoco
c = mujoco.GLContext(64, 64)
c.make_current()
print("success")
PY

grep -iE 'gpucomp|not found|EGL_nvidia|eglcore' /tmp/egl-loader.log
```

If that shows the loader searching unsuccessfully for `libnvidia-gpucomp.so.580.126.09`, the diagnosis is conclusive.

## The supported fix

The correct host-side fix is to upgrade the NVIDIA Container Toolkit/libnvidia-container.

**1.13.5 is the first 1.13.x release whose notes explicitly say it injects `libnvidia-gpucomp.so`.** I would not stop there on a machine running a 2026-era 580 driver; upgrading to a current supported toolkit is preferable. Current NVIDIA documentation explicitly treats `graphics` as supplying OpenGL, EGL, and Vulkan resources. 

So the clean configuration is conceptually:

```bash
docker run --rm \
  --gpus all \
  -e NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics \
  -e MUJOCO_GL=egl \
  ...
```

with a modern host NVIDIA Container Toolkit.

Unfortunately, **installing a newer `nvidia-container-toolkit` inside your application container will not fix the outer Docker runtime**. The host runtime performs its driver-library injection before the container process starts. The runtime architecture specifically uses the NVIDIA container hook/library to alter the container prior to startup. 

So if the administrator will not update the host, you need to compensate for the missing injected component at `docker run` time.

## No-host-modification workaround

Because you control Docker invocation, you can bind-mount the one missing **host driver library** into your container. This changes nothing on the host and does not disturb other jobs.

First, on the host as your ordinary user:

```bash
GPUCOMP="$(ldconfig -p |
  awk '$1 == "libnvidia-gpucomp.so.580.126.09" {print $NF; exit}')"

printf 'GPUCOMP=%s\n' "$GPUCOMP"
test -n "$GPUCOMP"
test -r "$GPUCOMP"
```

It should produce something resembling:

```text
/usr/lib/x86_64-linux-gnu/libnvidia-gpucomp.so.580.126.09
```

Then launch:

```bash
docker run --rm \
  --gpus all \
  -e NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics \
  -e MUJOCO_GL=egl \
  -e PYOPENGL_PLATFORM=egl \
  --mount \
    type=bind,src="$GPUCOMP",dst=/usr/lib/x86_64-linux-gnu/libnvidia-gpucomp.so.580.126.09,readonly \
  YOUR_IMAGE \
  bash -lc '
    ldconfig
    exec YOUR_REAL_COMMAND
  '
```

This is preferable to copying a random `libnvidia-gpucomp` package into the image because NVIDIA userspace driver libraries need to correspond to the host driver. Here you are taking the exact `580.126.09` library from the exact host whose kernel driver you are using.

If `ldconfig -p` on the host doesn't expose it, locate it with:

```bash
find /usr/lib /lib -type f \
  -name 'libnvidia-gpucomp.so.580.126.09' \
  -print 2>/dev/null
```

If **the host itself does not contain `libnvidia-gpucomp.so.580.126.09`**, then its 580 graphics-driver installation is incomplete, and there is no clean container-only way to manufacture the missing matching driver component. NVIDIA's own 580.126.09 component list says that library is part of the driver. 

## Fixing `10_nvidia.json`

There is an important distinction here: the NVIDIA Container Toolkit generally **mounts an existing driver configuration file from the host; it does not need to synthesize one dynamically**. Current toolkit graphics discovery explicitly looks for:

```text
glvnd/egl_vendor.d/10_nvidia.json
```

and injects it along with NVIDIA graphics components.  Existing toolkit/CDI output likewise shows `/usr/share/glvnd/egl_vendor.d/10_nvidia.json` being bind-mounted from host to container. 

Therefore, seeing graphics libraries injected but not `10_nvidia.json` suggests either that the file is missing/unlocatable on this host's driver installation or that the old runtime's discovery is failing for that configuration file.

Your hand-written JSON is valid:

```json
{
  "file_format_version": "1.0.0",
  "ICD": {
    "library_path": "libEGL_nvidia.so.0"
  }
}
```

There is no need to abandon that workaround. Similar container configurations use precisely this NVIDIA ICD. 

I would make it more deterministic by storing it under `/etc` and forcing GLVND to load only it:

```dockerfile
RUN mkdir -p /etc/glvnd/egl_vendor.d && \
    printf '%s\n' \
      '{"file_format_version":"1.0.0","ICD":{"library_path":"libEGL_nvidia.so.0"}}' \
      > /etc/glvnd/egl_vendor.d/10_nvidia.json

ENV __EGL_VENDOR_LIBRARY_FILENAMES=/etc/glvnd/egl_vendor.d/10_nvidia.json
ENV MUJOCO_GL=egl
ENV PYOPENGL_PLATFORM=egl
```

`__EGL_VENDOR_LIBRARY_FILENAMES` is an official libglvnd discovery override: when set, GLVND loads exactly the listed JSON files and does not enumerate the other vendor files. 

That is cleaner than deleting `50_mesa.json`, and guarantees that accidental Mesa availability cannot mask a broken NVIDIA path.

So your practical combination is:

```text
modern/repaired NVIDIA userspace library set
+
libnvidia-gpucomp.so.580.126.09
+
10_nvidia.json
+
__EGL_VENDOR_LIBRARY_FILENAMES pointing at it
+
MUJOCO_GL=egl
```

## A reproducible launch wrapper

Given your `--rm` requirement, I would use something like this:

```bash
#!/usr/bin/env bash
set -euo pipefail

DRIVER="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader |
          head -1 | tr -d '[:space:]')"

if [[ "$DRIVER" != "580.126.09" ]]; then
    echo "Unexpected NVIDIA driver: $DRIVER" >&2
    exit 1
fi

GPUCOMP="$(ldconfig -p |
    awk '$1 == "libnvidia-gpucomp.so.580.126.09" {print $NF; exit}')"

if [[ -z "$GPUCOMP" || ! -r "$GPUCOMP" ]]; then
    echo "Host libnvidia-gpucomp.so.580.126.09 not found" >&2
    exit 1
fi

exec docker run --rm \
    --gpus all \
    -e NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics \
    -e MUJOCO_GL=egl \
    -e PYOPENGL_PLATFORM=egl \
    -e __EGL_VENDOR_LIBRARY_FILENAMES=/etc/glvnd/egl_vendor.d/10_nvidia.json \
    --mount \
      type=bind,src="$GPUCOMP",dst=/usr/lib/x86_64-linux-gnu/libnvidia-gpucomp.so.580.126.09,readonly \
    YOUR_IMAGE \
    bash -lc '
        ldconfig

        python3 - <<'"'"'PY'"'"'
import mujoco
from OpenGL import GL

ctx = mujoco.GLContext(64, 64)
ctx.make_current()

renderer = (GL.glGetString(GL.GL_RENDERER) or b"").decode()
vendor   = (GL.glGetString(GL.GL_VENDOR)   or b"").decode()

print("EGL renderer:", renderer)
print("EGL vendor:  ", vendor)

bad = ("llvmpipe", "softpipe", "software", "swiftshader")
if not renderer or any(x in renderer.lower() for x in bad):
    raise SystemExit("software renderer detected")

if "nvidia" not in vendor.lower():
    raise SystemExit(f"unexpected GL vendor: {vendor!r}")
PY

        exec YOUR_TRAINING_COMMAND
    '
```

The ICD should already be baked into `YOUR_IMAGE` using the Dockerfile fragment above.

Run that probe before the 2.5-hour install/training setup so this class of failure costs seconds, not hours.

## `/dev/dri` and `/dev/nvidia-modeset`

I would not make these the first fix.

Your test with `/dev/dri` did not alter the result.  Furthermore, MuJoCo is deliberately using `EGL_PLATFORM_DEVICE_EXT`, not the GBM EGL platform. NVIDIA has supported direct EGL device selection as a mechanism for headless rendering without an X server for years. 

There are NVIDIA EGL configurations where `/dev/nvidia-modeset` and DRM nodes matter, particularly display/GBM/default-display paths, and NVIDIA's graphics stack contains a modeset component.  But that is a secondary diagnostic here. It does not explain nearly as well the exact **1.13.2 → missing new library → 580 dependency** sequence.

If adding `libnvidia-gpucomp` still leaves `eglInitialize()` failing, then the next thing I would test is:

```bash
ls -l /dev/nvidia-modeset /dev/dri/* 2>&1
```

and a run with:

```bash
--device=/dev/nvidia-modeset
--device=/dev/dri
```

provided `/dev/nvidia-modeset` exists on the host. But I would do that only after verifying the dynamic-library dependency closure.

## OSMesa is not an acceptable substitute here

Your concern is correct. `MUJOCO_GL=osmesa` selects MuJoCo's OSMesa GL context instead of EGL.  In your Ubuntu container with `libosmesa6`, that is a Mesa software-rendering path rather than native NVIDIA GPU rendering.

So it fails both of your stated requirements: performance and equivalence of rendered observations. Your application specifically requires GPU-rendered pixels and deliberately rejects software renderers. 

I would not remove that guard.

GLX under Xvfb is also not a useful replacement. Xvfb itself does not magically turn the NVIDIA OpenGL driver into a headless GPU renderer; a genuinely NVIDIA-backed X path requires an NVIDIA Xorg setup with access to the appropriate devices. That is substantially more invasive and fragile on a shared server than fixing native EGL.

GBM is another GPU-backed EGL platform, and driver 580 ships NVIDIA's GBM external-platform library, but it needs the DRM path and additional injected pieces such as `libnvidia-egl-gbm` and its JSON.  MuJoCo's current Python EGL backend already has the simpler, appropriate headless route—`EGL_PLATFORM_DEVICE_EXT`—so switching platforms would be treating the symptom rather than fixing the incomplete NVIDIA userspace stack.

## Answers to the five questions

1. **Why does initialization fail?**  
   Almost certainly because the NVIDIA vendor stack is incomplete inside the container. The prime missing component is `libnvidia-gpucomp.so.580.126.09`, which driver 580's EGL core needs but libnvidia-container 1.13.2 does not know to inject. MuJoCo's exception is generic and incorrectly makes this look like lack of `EGL_EXT_platform_device`.

2. **Should toolkit 1.13.2 provide `10_nvidia.json`?**  
   The graphics integration is supposed to make the NVIDIA GLVND vendor configuration available. The toolkit normally mounts a host driver JSON rather than inventing one. Its absence is another runtime/host-packaging defect. Your synthesized JSON is a valid workaround; forcing it with `__EGL_VENDOR_LIBRARY_FILENAMES` is preferable to deleting Mesa.

3. **Is driver 580.126.09 + toolkit 1.13.2 mismatch plausible?**  
   **Yes, and there is specific evidence for it.** NVIDIA added `libnvidia-gpucomp` support to toolkit 1.13.5 after explicitly announcing that EGL/GL driver components would depend on it. 

4. **Is there a container-only workaround?**  
   For the ICD, yes: bake the JSON into the image. For the missing driver library, an ordinary in-container package cannot change what the outer NVIDIA runtime injects. But you can make a reproducible, non-invasive `docker run` workaround by read-only bind-mounting the exact `libnvidia-gpucomp.so.580.126.09` from the host into the container. No host package or daemon changes are required.

5. **Should you use OSMesa or another route?**  
   No. OSMesa is not the GPU-equivalent substitute you require. Native NVIDIA EGL device rendering is still the correct path. GLX/Xvfb and GBM add moving parts without addressing the likely incomplete-driver injection.

The first command I would run is therefore just:

```bash
ldd "$(ldconfig -p |
  awk '/libnvidia-eglcore\.so\.580\.126\.09/ {print $NF; exit}')" |
  grep -E 'gpucomp|not found'
```

If it prints `libnvidia-gpucomp.so.580.126.09 => not found`, you have the blocker identified.


---

(User Question)
We are forbidden from change of the host's global environment like apt-get, pip install, or changing drivers or settings. This is a communal host that's high-reliability for GPU.
Will the proposed plan result in any safety/reliability issues in this regard?

---

Yes—with a few restrictions, the proposed workaround can be made compatible with your “no host changes” requirement. The core workaround is read-only from the host’s perspective and does not modify packages, drivers, daemon configuration, kernel state, or other users’ environments. Your stated constraint is that nothing may modify the host or disturb other jobs. 

The safe parts are:

- Reading the host driver version with `nvidia-smi`.
- Reading `ldconfig -p`.
- Reading/searching `/usr/lib` or `/lib`.
- Bind-mounting exactly one driver library into the container with `readonly`.
- Creating `10_nvidia.json` inside the container image or container filesystem.
- Setting `MUJOCO_GL`, `PYOPENGL_PLATFORM`, `__EGL_VENDOR_LIBRARY_FILENAMES`, and `NVIDIA_DRIVER_CAPABILITIES` as container environment variables.
- Running `ldconfig` inside the container.
- Installing packages with `apt`/`pip` inside the disposable container, since the container runs as root internally and your statement explicitly permits in-container changes. 

None of those changes the host's global environment.

There are, however, three changes I would make to the previous plan for a high-reliability communal machine.

First, do not use `--gpus all` unless your scheduler/allocation really gives you both GPUs. Bind only the assigned GPU, preferably by UUID:

```bash
docker run --rm \
  --gpus '"device=GPU-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"' \
  ...
```

or, if your environment reliably assigns indices:

```bash
--gpus '"device=0"'
```

This matters more for communal-host safety than the EGL workaround itself. `--gpus all` gives the container visibility of both V100s and makes accidental use of another user's GPU possible.

Second, use only:

```bash
NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics
```

not:

```bash
NVIDIA_DRIVER_CAPABILITIES=all
```

`all` needlessly exposes extra driver capabilities such as video/display components. For MuJoCo EGL you need `graphics`; CUDA needs `compute`; monitoring commonly uses `utility`. Keep the privilege surface minimal.

Third, I would not use either of these initially:

```bash
--device=/dev/dri
--device=/dev/nvidia-modeset
```

Your own test already showed that adding `/dev/dri` made no difference.  Those devices are not required for the first `EGL_PLATFORM_DEVICE_EXT` diagnosis, and exposing extra graphics/modesetting devices provides capabilities you do not need. On a shared machine, minimizing device exposure is preferable.

The safest version of the workaround therefore looks like this:

```bash
GPUCOMP="$(ldconfig -p |
    awk '$1 ~ /^libnvidia-gpucomp\.so/ {print $NF; exit}')"

test -n "$GPUCOMP"
test -r "$GPUCOMP"

docker run --rm \
  --gpus '"device=YOUR_ASSIGNED_GPU"' \
  -e NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics \
  -e MUJOCO_GL=egl \
  -e PYOPENGL_PLATFORM=egl \
  -e __EGL_VENDOR_LIBRARY_FILENAMES=/etc/glvnd/egl_vendor.d/10_nvidia.json \
  --mount \
    type=bind,src="$GPUCOMP",dst=/usr/lib/x86_64-linux-gnu/libnvidia-gpucomp.so.580.126.09,readonly \
  YOUR_IMAGE
```

The important property is:

```text
host file
    ↓ read-only bind mount
container
```

The container cannot alter that mounted library because the mount is explicitly read-only. It merely maps the existing host file into its own mount namespace.

Likewise, this:

```bash
ldconfig -p
```

on the host is purely a query. It does not modify the cache. Be careful not to run plain:

```bash
sudo ldconfig
```

on the host—that would be a host-level administrative operation and is unnecessary.

Inside the container, plain:

```bash
ldconfig
```

is fine. It updates `/etc/ld.so.cache` inside that disposable container, not the host's cache. That remains true provided you have not done something unsafe such as writable bind-mounting the host's `/etc` or `/usr`.

I would also explicitly avoid all of the following on this machine:

```text
sudo apt install ...                 # on host
sudo pip install ...                 # on host
sudo ldconfig                        # on host
nvidia-ctk runtime configure         # on host
systemctl restart docker             # host daemon change
editing /etc/docker/daemon.json      # host configuration
editing NVIDIA files under /usr      # host filesystem
--privileged                         # unnecessarily broad
mounting /usr or /lib read-write     # dangerous
changing persistence/MIG/clocks      # global GPU state
nvidia-smi -pm/-pl/-lgc/etc.         # can affect other workloads
```

There is one residual reliability consideration: **executing GPU rendering itself obviously consumes resources on the assigned physical V100**. EGL contexts and CUDA contexts share the actual GPU, so normal GPU memory, compute, thermal, and scheduling contention still applies. But that is ordinary workload behavior, not a host configuration modification. If the server's allocation mechanism already permits your RL workload on that GPU, EGL rendering does not introduce a fundamentally different administrative risk.

The read-only `libnvidia-gpucomp` mount is therefore the part I would be comfortable testing first on a communal host. It is considerably less invasive than changing the NVIDIA Container Toolkit, Docker daemon, host driver, DRM configuration, or X server.

I would use this progression:

1. Run the read-only `ldd`/`readelf` diagnosis.
2. If `gpucomp => not found`, bind-mount that single exact host library read-only.
3. Supply the NVIDIA ICD inside the container.
4. Restrict the container to the GPU assigned to you.
5. Test a 64×64 EGL context.
6. Do **not** expose DRM/modeset devices unless the preceding test still fails and there is evidence they are actually required.

That sequence satisfies the host-safety constraints substantially better than any solution involving host toolkit/driver changes.
