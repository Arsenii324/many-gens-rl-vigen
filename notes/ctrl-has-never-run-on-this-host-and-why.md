# `ctrl` has never completed on the production host, and the cause is a jax/jaxlib mismatch

**2026-09-10.** Found while attesting the seven evaluator families on the V100. `ctrl` failed twice,
for two different reasons, and the second is a blocker for the battery.

## Attempt 1 — it yielded to itself

    yielded at 1789026735: free memory 1210 MiB is below the 4000 MiB floor
    free_mib=1210 procs=1 util=0

**`procs=1`: the only process on the card was ours.** `ctrl` is `num_envs=16` under the `datasphere`
profile and **64 under `v100`**, and at 64 it takes ~31 GB of a 32 GB card. The yield watch did
exactly its job — a neighbour arriving then would have failed — and the consequence is that
**`ctrl` at the v100 profile is a whole-card job**, joining `ppg` (26,653 MiB at its auxiliary
phase). Neither can share a card.

## Attempt 2 — every cuDNN engine rejects the first convolution

Re-run at `NATIVE_HOST_PROFILE=datasphere` (`num_envs=16`), which is what the v205 attest configs
used. No yield this time; a hard failure:

    Original error: INTERNAL: All algorithms tried for
      (f32[10,16,64,64], u8[0]) custom-call(f32[10,9,64,64], f32[16,9,3,3]), window={size=3x3 ...}
      Profiling failure on cuDNN engine eng28{k2=3,k3=0}: UNKNOWN: <unknown cudnn status: 5003>
      Profiling failure on cuDNN engine eng2{k2=4,k3=0}: UNKNOWN: CUDNN_STATUS_EXECUTION_FAILED
      ... every engine, same shape

Nine input channels is `frame_stack=3 x RGB`, so this is the first conv of the policy encoder under
A40 REVISED-2. **Every engine failing on a single ordinary 3x3 convolution is a stack problem, not a
model or memory problem** — the card had 32 GB free.

## The cause

What the job installed:

    jax-0.4.35    jax-cuda12-pjrt-0.4.35    jax-cuda12-plugin-0.4.35    jaxlib-0.4.34

**jax 0.4.35 against jaxlib 0.4.34.** JAX requires jaxlib to match; a split pair is a textbook source
of exactly this "all algorithms tried ... failed" symptom.

Two declarations are in play and they disagree:

| source | pin |
|---|---|
| `datasphere/native/families.json:1009` | `jax[cuda12]==0.4.35` |
| `runnable/ctrl/requirements.txt:3` | `jax[cuda110]==0.2.17` — an ancient CUDA 11.0 pin |

Nothing pins `jaxlib` anywhere. The clone's own requirements are evidently installed as well, and
after the resolver settles, `jax` ends at 0.4.35 while `jaxlib` is left at 0.4.34.

**`ctrl` has never completed on this host.** Checked: no `NATIVE_CELL_COMPLETED ctrl` in any
`rlvigen-runs/*/native-out/job.log`. Its ledger attestation `bt1n0in75mc91n6btmpv` is a DataSphere
job, where the environment resolved differently — which is precisely what
`gate_environment_manifest` warns about and what `audit_environment_drift.py` was built to detect:
*"the job still runs apt-get/pip inside it, so the executed environment is not frozen and two jobs
from this digest can differ."* Here they did, and the difference is fatal on one host and not the
other.

## The fix, and why it is not applied here

Pin `jaxlib` to match: `jax[cuda12]==0.4.35` **and** `jaxlib==0.4.35`, and stop the clone's
`requirements.txt` from contributing a second, older jax resolution for this family.

**Not done now.** `families.json` is a `CONFIG_MEMBER`, so editing it moves every family's evaluator
revision and would void the four attestations completed today. It belongs in the same single bump as
the `eval_grid.py` docstring correction. Recorded in
[`PRODUCTION-GRADE-PLAN.md`](PRODUCTION-GRADE-PLAN.md).

**Consequence for the battery:** `ctrl` is 3 of the 36 cells and cannot run on this host until this
is fixed. The other eleven baselines are unaffected — this is a JAX-only stack, and
`audit_environment_drift.py` already records that `ctrl`'s CUDA differs from every torch family's.
