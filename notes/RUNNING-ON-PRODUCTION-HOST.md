# Running on the actual production host — the surface that did not exist until now

**Written 2026-09-07 in direct answer to a pointed question: does any existing surface actually
say how to execute on the production host, or only what values to use once you're there?** Checked
`notes/PRODUCTION-RUNBOOK.md`, `notes/MIGRATION-T4-TO-V100.md`, `notes/PRODUCTION-CALENDAR.md`,
`notes/draft-codex-parallel-preproduction-plan-under-review.md`, and `notes/remote-infra.txt`
directly before writing this, not from memory of what they probably said.

**The honest finding: no such surface existed before this file.** What those five documents give
you, thoroughly: the *value deltas* between DataSphere and V100 (`MIGRATION-T4-TO-V100.md`), the
*failure signatures to watch for* once something is running (`PRODUCTION-RUNBOOK.md`), the
*calendar/scheduling* math (`PRODUCTION-CALENDAR.md`), and the *raw hardware facts*
(`remote-infra.txt`: `varaksin_as@cds2`, plain SSH, 16 cores, 113 GiB RAM, 2×V100-32GB, reached the
same way anyone reaches any Linux box — nothing DataSphere-specific about the host itself). None of
them contain an actual command to run. Every piece of *execution* tooling this project built —
`datasphere/native/job.sh`, `contract.py`, every `cfg-*.yaml` — talks to DataSphere's own job API
(`datasphere project job execute`), which this host is not behind at all. `job.sh`'s own submit
path would refuse to even try (it hardcodes the DataSphere project ID and CLI).

## What actually closes the gap: `run_probe.sh` was already portable

The reason this is a small fix, not a new subsystem: `datasphere/native/run_probe.sh` — the actual
per-cell training/eval driver every `cfg-*.yaml` sends to DataSphere — does **not** call anything
DataSphere-specific. It bootstraps its own environment from a bare `nvidia/cuda:...` image via
plain `apt-get`/`pip install` (its own lines ~481-482, ~787-793), reads its configuration from
positional arguments and environment variables, and writes `result.tgz`/`records.jsonl` to a local
path. It has always been runnable via a bare `docker run`; nothing about it assumed DataSphere's
orchestration. The missing piece was purely a wrapper that constructs that `docker run` invocation
and a doc saying so — not a reimplementation.

## The two new pieces

1. **`datasphere/native/run_on_production_host.sh`** — takes the same payload archive, RL-ViGen
   archive, and environment variables every `cfg-*.yaml`'s `cmd:` block already sets, and runs
   `run_probe.sh` inside `docker run --gpus ...` against the exact same digest-pinned image
   (`datasphere/native/source-lock.json`) DataSphere jobs use. Extra file inputs (a retained
   checkpoint, e.g. for an R_A/R_B comparison) go through `EXTRA_MOUNT_N` variables. Full usage
   and a worked example (C95's own R_A config, `v178`, translated line for line) are in the
   script's own header comment.
2. **This file** — the concrete, ordered steps to actually use it.

## The steps, concretely

1. **SSH to the host.** `ssh varaksin_as@cds2` (the exact prompt recorded in `remote-infra.txt`).
   This agent has never had network access to this host and cannot confirm the hostname resolves
   or that this credential still works — verify both before trusting anything below.
2. **Check `nvidia-smi` first, every time**, not from the week-old snapshot in `remote-infra.txt`
   (GPU 0 occupied 15.1 GB/67%, GPU 1 free, as of 2026-09-05 — may no longer be true). Pick a free
   GPU and export `CUDA_VISIBLE_DEVICES` accordingly, or accept `--gpus all` and let both be used.
3. **Get the payload there.** Do **not** invent a new transfer mechanism — reuse the one already
   proven all session: `contract.py build-payload --source . --output payload-vNNN-<family>.tgz
   --families <family>` (locally, on this machine, exactly as done for every DataSphere job this
   session), verify it (`contract.py verify-payload --require-evaluator-identity` and
   `verify-evaluator-binding`, same as always), then `scp` the resulting `.tgz` (plus whatever
   asset archives/checkpoints the specific cell needs, e.g. `rlvigen-door2-90d8b8c4.tgz`,
   `s2-snapshot-100000.pt`) to the host. This repo has no configured git remote
   (`git remote -v` is empty) — scp-ing the same payload artifact this project already builds and
   verifies for every remote job is the consistent choice, not a new one invented for this host.
4. **Run it**: `bash datasphere/native/run_on_production_host.sh payload-vNNN-<family>.tgz
   result.tgz rlvigen-door2-90d8b8c4.tgz` (plus `EXTRA_MOUNT_1=...` for a checkpoint, plus every
   `CELLS`/`FRAMES`/`TASK`/`SEED`/`OFFLINE_EVAL_*`/`ENDPOINT_EVAL*` variable the target
   `cfg-*.yaml` already sets in its `cmd:` block — copy them verbatim from that file).
5. **Retrieve `result.tgz` and `records.jsonl`** from wherever you pointed the second argument;
   process them exactly as `bash datasphere/native/job.sh diagnose <id>` does for a real DataSphere
   job, since the archive shape is identical by construction (same `run_probe.sh`, same output
   layout) — there is no `job.sh diagnose`-equivalent for a local run because there is no job ID;
   read `result.tgz`'s contents directly the way `job.sh diagnose` itself does internally.
6. **Follow `notes/PRODUCTION-RUNBOOK.md`** for what to watch for while it runs, and
   `notes/MIGRATION-T4-TO-V100.md`'s numbered steps 1-8 for what order to do things in (this file
   only supplies step 2's *mechanism*, not a replacement for the sequencing those steps already
   specify — in particular, do not skip step 1's GPU/factor measurement or step 2's R_A/R_B control
   just because execution is now possible).

## Production-length runs: four things a diagnostic probe does not need

Added 2026-09-07, after being asked directly whether this design actually suits a *production* run
rather than a short probe. Three of the four were real defects in the first version of the script,
found by reading `run_probe.sh` again rather than by reasoning about the wrapper alone.

1. **`NATIVE_PRODUCTION` must reach the container — it did not.** `run_probe.sh` refuses outright
   (`exit 3`) at `FRAMES >= 600000` when `NATIVE_PRODUCTION` is unset, because
   `apply_production_settings` would otherwise silently apply *nothing* and train a 600k run at
   probe-scale cadence and replay settings, completing successfully and looking fine. The first
   version of `run_on_production_host.sh` built its forwarded-variable allow-list from what a
   *diagnostic* `cfg-*.yaml` sets, so `NATIVE_PRODUCTION` never reached the container and **every
   production-scale cell, the 600k canary included, would have died after paying the full container
   bootstrap** — with the failure reading as a config error rather than a wrapper bug. Fixed; the
   script now also raises both of `run_probe.sh`'s production refusals on the host, before the
   bootstrap is paid for, and `tests/test_run_on_production_host.py` pins both.
2. **Partial output was not durable.** `run_probe.sh` keeps every `SAVE_EVERY_FRAMES` checkpoint,
   `training.log`, and per-cell run directory in `out=/tmp/native-out` — container-local — and
   copies nothing to the mounted result path until its single closing
   `tar -czf "$result" -C "$out" .` (its own line 1546). A container killed at any point before
   that line lost the entire run, unrecoverably, because none of it had ever touched host storage.
   The script now bind-mounts `/tmp/native-out` onto the host (`NATIVE_OUT_HOST_DIR`, defaulting to
   a timestamped directory beside the result archive, deliberately *outside* the `mktemp -d` the
   EXIT trap removes). Checkpoints are now durable as they are written, and the run is inspectable
   while it runs — which is also what `scripts/watch_divergence.py --run <dir>` needs, and could
   not have had before.
3. **Detach the whole script, not the container.** `docker run` here is foreground and blocking.
   `dockerd` keeps the container alive across an SSH drop, but this script dies with its SSH
   session and never reaches its result-retrieval `cp` steps. Wrap the whole invocation:
   `nohup bash datasphere/native/run_on_production_host.sh ... > run.log 2>&1 &`, or run it under
   `tmux`. With fix 2 in place a lost wrapper no longer costs the run, only the final packaging.
4. **Packing is one container, not two.** `run_probe.sh` takes a comma-separated `CELLS` list and
   runs the entries concurrently when `NATIVE_CONCURRENT=1` (its own line ~303), serially
   otherwise — so `MIGRATION-T4-TO-V100.md` step 4's two-cell packing is
   `CELLS=drqv2:1,drqv2:2 NATIVE_CONCURRENT=1` in a single container, not two invocations of this
   script. `NATIVE_CONCURRENT` was missing from the allow-list too, which silently disabled packing
   entirely; fixed. Two separate invocations would each pay their own bootstrap, neither would see
   the other's memory use, and nothing would arbitrate between them. Note the constraint
   `run_probe.sh`'s own `check-co-schedulable` enforces: families that cannot share one Python
   environment cannot be packed together (`ctrl` is JAX and strips torch — `jax[cuda12]`'s cudnn 9
   and torch's pinned cudnn 8.9.2.26 have no common version).

**GPU pinning belongs at the Docker level.** `DOCKER_GPUS='"device=1"'` attaches exactly one card
to the container. `CUDA_VISIBLE_DEVICES` is deliberately *not* in the forwarded-variable list: it
would look like it pinned the run while the container still had both cards attached, and a library
that ignores it could still reach the occupied GPU.

**No `--memory` or `--cpus` limits are set, deliberately.** `MIGRATION-T4-TO-V100.md` step 4 gates
the packing decision on *measured* peak RAM/CPU headroom; a cgroup cap guessed before that
measurement exists would convert an honest overcommit into an OOM-kill mid-run. Add them after
step 2's measurement, not before.

## What this does NOT establish, named explicitly rather than left implicit

- **Not tested on the actual host.** No SSH access from this session. Every command above is
  derived from `run_probe.sh`'s own already-exercised contract (read directly, not assumed) and
  from `docker run`'s ordinary semantics, not from a real execution on `cds2`.
- **Outbound network access on `cds2` is assumed, not confirmed** — `run_probe.sh`'s own
  `apt-get`/`pip install` calls need it. If the host is air-gapped or behind a restrictive proxy,
  this fails at that step and needs a pre-provisioned image instead (not built here, since nothing
  indicates one is needed).
- **Docker + NVIDIA Container Toolkit on `cds2` is assumed, not confirmed.** `nvidia-smi` working
  at the host level (per `remote-infra.txt`) does not by itself prove `docker run --gpus all` is
  configured — that needs `nvidia-container-toolkit` installed and Docker's daemon configured to
  use it. Check `docker run --rm --gpus all nvidia/cuda:12.2.2-runtime-ubuntu22.04 nvidia-smi`
  succeeds before trusting a real cell's result.
- **Concurrent use of the host is the owner's to arbitrate**, not this script's — it does not
  reserve, queue, or coordinate with any other process that might be using the free GPU or the
  113 GiB of RAM at the same time.
