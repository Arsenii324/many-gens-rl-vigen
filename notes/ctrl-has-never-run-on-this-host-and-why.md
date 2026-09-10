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

## THE LEAD, found 2026-09-10 after the jaxlib theory collapsed: GPU ARCHITECTURE

`ctrl` has succeeded exactly once and failed exactly twice, and the two sets differ by the card:

| where | GPU | compute capability | outcome |
|---|---|---|---|
| DataSphere, job `bt1n0in75mc91n6btmpv` | **NVIDIA L4**, 23,034 MiB, driver 535.261.03 | **8.9** (Ada) | **attested** |
| cds2 (this host) | **Tesla V100-SXM2-32GB**, driver 580.126.09 | **7.0** (Volta) | every cuDNN engine rejects the first conv |

**`ctrl` has only ever run on sm_89 and only ever failed on sm_70.** No torch family shows this,
because `ctrl` is the fleet's only JAX/XLA baseline — `audit_environment_drift.py` already records
that its CUDA stack differs from every other family's by design.

That reframes the failure. `All algorithms tried for (f32[10,16,64,64], u8[0]) custom-call(...)
failed` with 32 GB free is what XLA's autotuner reports when **no cuDNN engine it knows covers this
shape on this architecture** — not a resource problem and not a version mismatch between jax and
jaxlib, which pip has since confirmed is the pairing upstream intends.

### What would confirm or kill it, cheapest first

1. **Run any trivial JAX convolution on this V100** in the same image. If a bare
   `jax.lax.conv_general_dilated` on `f32[1,3,8,8]` also fails, the stack does not support Volta at
   all and nothing about `ctrl` is special.
2. **`XLA_FLAGS=--xla_gpu_autotune_level=0`** — if the failure is autotuner-only, a default
   algorithm may run. Changes numerics selection, so it is a diagnostic, not a fix.
3. **An older jax/jaxlib that predates the Volta drop**, if there is one. `runnable/ctrl`'s own
   `requirements.txt` still pins `jax[cuda110]==0.2.17`, which is the era when Volta was primary.

### What it means for the battery if confirmed

`ctrl` is 3 of the 36 cells. If this JAX build cannot target sm_70, `ctrl` cannot run on cds2 at
any profile, and the options are an older JAX, a different card, or reporting `ctrl` as
not-run-on-this-host. **It is not a configuration mistake to be found by more careful reading** --
which is where the previous two theories both went wrong.

## CORRECTION 2026-09-10 — the jax/jaxlib split is NOT the cause, and pinning it made things worse

Everything below about `jax 0.4.35 against jaxlib 0.4.34` being a mismatch is **wrong**. pip's own
resolver states the intent:

    jax[cuda12] 0.4.35 depends on jaxlib==0.4.34; extra == "cuda12"

**`jax[cuda12]==0.4.35` requires jaxlib 0.4.34 by design.** The cuda12 extra pins it. What I read as
a broken pair is the pairing upstream ships.

Adding `jaxlib==0.4.35` to `families.json` therefore did not fix ctrl — it made the environment
**uninstallable**: `ERROR: ResolutionImpossible`, `NATIVE_IMPORT_GATE_SKIPPED ctrl (its dependencies
did not install)`, and the cell failed in 3.5 minutes instead of reaching a convolution at all.
Reverted.

**A second thing I got wrong, in the other direction.** I recorded that landing this pin would move
every family's evaluator revision, and built a plan reordering on it. It does not.
`evaluator_family_config_revision` hashes `identity_schema`, `semantics`, `family` and
`scope_fields` — **it never reads families.json's contents**. `pip_requirements` is environment, not
evaluator-configuration identity, and `gate_environment_manifest` is what covers it. The pin could
have landed at any time for free, and reverting it cost nothing: all seven revisions are byte-identical
before and after, so the four attestations completed against the frozen tree still stand.

**So ctrl's real cause is still unknown.** What is established: every cuDNN engine rejects a
`f32[10,9,64,64]` 3x3 convolution with 32 GB free, and ctrl has never completed on this host while
its DataSphere attestation succeeded. The environment difference between the two hosts is the place
to look, not the jax pin.

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

---

## SUPERSEDED — this section's conclusion is WRONG. See the correction below.

Step 1 of the plan above ("run any trivial JAX convolution on this V100 in the same image") was
executed. Artifact: [`../results/logs/volta-conv-probe-2026-09-10.log`](../results/logs/volta-conv-probe-2026-09-10.log).

```
jax=0.4.35 jaxlib=0.4.34
device: Tesla V100-SXM2-32GB compute_capability=7.0
MATMUL OK  sum=134217728
CONV FAILED  INTERNAL: All algorithms tried for %cudnn-conv ... failed
```

The probe isolates the cause completely. 32 GB free, so it is not memory. A matmul returning the
exactly-correct 134217728, so it is not the card, the driver or XLA. No ctrl code in the process,
so it is not the baseline. A minimal `f32[1,3,64,64] x f32[32,3,3,3]` convolution — the smallest
case that could fail — and every cuDNN engine rejects it.

**`ctrl` cannot run on cds2 with this build.** It is 3 of the battery's 36 cells.

### Two failures wore the same label, and only one was real

This note previously held both, correctly, and the distinction is the thing to preserve:

- **Attempt 2** — a real conv failure at `CUDNN_STATUS_EXECUTION_FAILED`. This is the finding, now
  reproduced in isolation.
- **v212** — `ERROR: ResolutionImpossible`, `NATIVE_IMPORT_GATE_SKIPPED ctrl (its dependencies did
  not install)`, dead in 3.5 minutes without reaching a convolution. That was the jaxlib pin, an
  error of mine, since reverted. **The revert works**: this probe's `pip install 'jax[cuda12]==0.4.35'`
  resolved cleanly to jaxlib 0.4.34 and still could not convolve.

Had the pin not been reverted first, this probe would have died at the import gate and the sm_70
question would have stayed open behind a fixable install error.

### What this does NOT say

It does not say ctrl is broken, or that sm_70 cannot do convolutions. It says *this jax/cuDNN
build* has no engine covering this conv on this card. A build whose kernels cover sm_70 retires
this row rather than contradicting it. Re-run `~/rlvigen-work/jax-volta-probe-v2.sh`: exit 0
refutes, exit 10 confirms.

### The first probe measured nothing and reported success

The queued probe ran in `ubuntu:24.04`, which has no interpreter. It printed `python3: command not
found`, ran no convolution, and **exited rc=0**. A JAX probe has to run in the image carrying the
JAX stack, and it must exit non-zero when it proves nothing. Recorded as its own register row.


---

## CORRECTION, same day — the cause is cuDNN x card, and ctrl RUNS here

**The section above is wrong and is kept only so the reasoning that produced it stays visible.**
It concluded "ctrl cannot run on cds2 with this build". ctrl can. Artifact:
[`../results/logs/volta-cudnn-pin-2026-09-10.log`](../results/logs/volta-cudnn-pin-2026-09-10.log).

Holding the card fixed at one V100 and jax fixed at 0.4.35 / jaxlib 0.4.34, varying only cuDNN:

| card | nvidia-cudnn-cu12 | conv |
|---|---|---|
| L4, sm_89 (the attestations) | 9.25.1.1 | OK |
| V100, sm_70 | 9.26.0.51 | **FAILS**, every engine |
| V100, sm_70 | 9.5.1.17 | **OK**, sum=3465600 |
| V100, sm_70 | 9.1.0.70 | **OK**, sum=3465600 |

`3465600` is the arithmetically exact answer, so those runs computed correctly rather than merely
not raising: 3844x27 + 248x18 + 4x12 = 108300 per channel, x32 channels.

**Recent cuDNN dropped Volta kernels while keeping Ada.** That is why the L4 attested on a cuDNN
essentially as new as the one failing here, and why no XLA flag helped: at
`xla_gpu_autotune_level=0` the failure moved out of the autotuner and came straight from
`cudnnConvolutionForward` with the same status.

### The fix

`ctrl` now pins `nvidia-cudnn-cu12==9.5.1.17` in `families.json` — the highest version measured
working on sm_70. Its `pip_requirements` previously pinned `jax` and `jaxlib` and left every
`nvidia-*` transitive floating, so the executed CUDA stack was whatever pip resolved **on the day
the cell ran**. That is the reproducibility hole `gate_environment_manifest` carries as OWNER,
materialising as a hard failure rather than as drift between two numbers.

The pin does **not** move ctrl's evaluator revision (`pip_requirements` is not hashed by
`evaluator_family_config_revision`), so it costs no re-attestation. It **does** move
`resolved_descriptor_sha256`, so `production-schedule-v100.json` was re-synced in the same commit.

### Why two wrong causes got recorded first

Neither single-variable probe could separate them, and each looked conclusive alone:

1. **"sm_70 is uncovered"** — necessary but not sufficient. The same card convolves fine on 9.5.
2. **"plain version skew"** — refuted by the L4 having attested on 9.25.1.1.

Only the 2x2 decides it. The tell was in the error from the beginning:
`<unknown cudnn status: 5003>` is XLA reporting a status **its build does not recognise**, which is
a version statement. A genuine architecture problem prints a recognised `ARCH_MISMATCH`. I read
"every cuDNN engine rejects the conv" as being about the engines' hardware coverage when it was
about the library's identity.
