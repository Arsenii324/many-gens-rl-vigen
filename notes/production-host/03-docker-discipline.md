# Docker discipline

**All work happens strictly inside a container.** The host provides Docker and the GPU; it provides
nothing else, and we add nothing to it.

## The shape of a correct run

1. Start from a pinned image. This project's is in `datasphere/native/source-lock.json`
   (`container_image`, pinned by digest). `datasphere/native/run_on_production_host.sh` reads it —
   it is not retyped.
2. Install what the run needs **into the container**, at run time, exactly as
   `run_probe.sh` already does.
3. Mount **only our own directories**. Never a global path, never `/`, never another user's home,
   never a shared scratch area. See `07-this-repo-s-own-hazards.md` for where this repo's mounts
   actually resolve to.
4. Let the container exit and be removed (`--rm`). State that must survive lives in our own mounted
   output directory.

## A GPU run needs `graphics`, and `--gpus` does not give it

```
-e NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics
```

`--gpus` alone yields `compute,utility`. `graphics` is the capability that installs
`libEGL_nvidia`; without it a container has CUDA but no NVIDIA EGL, and `MUJOCO_GL=egl` silently
falls back to Mesa `llvmpipe` — CPU rasterisation. Measured on this host, same image and card:

| capabilities | `libEGL_nvidia` |
|---|---|
| `compute,utility` (docker default) | absent |
| `compute,utility,graphics` | `libEGL_nvidia.so.580.126.09` |

`run_on_production_host.sh` sets it now (override with `NATIVE_DRIVER_CAPABILITIES`). It is here
because it is a **container-runtime** property, not an image property — pinning the image digest,
which this project does carefully, does not pin the renderer. Found on 2026-09-08 when the first
cell to get past `pip` died at the renderer check after a two-and-a-half hour bootstrap.

## Deleting a container or image

Permitted **only** with positive proof that we created it and that it did not exist beforehand.
"Proof" means both of:

- the name or id matches one this session created and recorded, **and**
- it was absent before that creation, established by having listed beforehand — not inferred

`ubuntu:24.04`, `nvidia/cuda:*`, or any other base or shared image is **never** ours to remove,
however unused it looks. Someone else's next job may pull against a warm cache, and re-pulling a
multi-gigabyte image on a shared link is a real cost imposed on a real person.

**`docker system prune`, `docker image prune`, `docker volume prune` are prohibited outright.**
They cannot distinguish ours from theirs, which is precisely the property that makes them unusable
here.

## Naming

Give every container a name that identifies it as ours and as this run.
`run_on_production_host.sh` already does: `rlvigen-<result-stem>-<timestamp>`. Keep that, so a
listing shows unambiguously which containers are ours — and so nobody else has to guess either.

## When a container misbehaves

Stop the one we started, by its known name. Never `docker kill` by pattern, never "kill the ones
that look stuck". A pattern that matches ours today matches someone else's tomorrow.
