# SUPERSEDED — use `projects/many-gens-rl-vigen/datasphere/` instead

> **Read this before touching anything here.** A second, *verified* DataSphere setup exists at the
> project root: [`../../datasphere/`](../../datasphere/). It was working end to end on
> **2026-08-10** — `cuda_available=True`, GL rendering confirmed non-software, and a protocol hash
> equal to the laptop's — with `gt4.1` for probes and **`gt4i.1`** (interruptible, cheaper, and the
> right choice for a measurement that can be re-run) for training.
>
> **This directory is the older smoke and it does not pin torch.** On 2026-08-24 I spent an
> afternoon fixing three CLI schema changes here and then hit
> `torch 2.13.0+cu130 / driver 535 / available False / NO GPU` — on both a V100 and a T4.
> `../../datasphere/train_fps_job.sh:48` carries the fix, and the reason, verbatim:
>
> > *"torch pinned to a cu12x wheel: an unpinned torch pulled a CUDA-13 wheel the T4 driver cannot
> > use"*
>
> That diagnosis is **two weeks old**. I reproduced the bug because I never looked for a second
> implementation, and nothing in either directory pointed at the other. **This is the fourth time
> this week that re-deriving a recorded fact has cost real time** — after the chance floor
> ([C17](../../docs/CONSTRUCTION.md#c17)), `curl`-on-MPS ([C52](../../docs/CONSTRUCTION.md#c52)),
> and the collector's layout assumption, twice.
>
> What survives from the work here and is worth keeping: the three CLI schema tightenings recorded
> below (`type` in the env block, the load-bearing `__main__` guard, comment-free requirements) are
> **new since 2026-08-10** and will bite the root setup too the next time it is submitted.
>
> Do not delete this directory yet — its base-image report is the only measurement showing
> `MjModel.tex_rgb True` on DataSphere, which is the fact that rules Kaggle out.

# DataSphere job — the CUDA smoke where the eval regimes also work

**Why here and not Kaggle.** RL-ViGen's texture modder reads `MjModel.tex_rgb`, removed in
mujoco 3.0, so every `eval-*` regime needs mujoco 2.x. The last 2.x release with wheels is
`2.3.7`, and it stops at **cp311**. Kaggle runs python **3.12**, so on Kaggle only the `train`
regime is reachable — useless for a generalisation benchmark. DataSphere pins **3.11**, where
that wheel exists. `main.py` asserts this in its first lines by printing
`MjData.qM` and `MjModel.tex_rgb`, both of which must be True.

**To launch.** The project id is **`bt12q57tmrs03pnt8drc`** (`arsen4ikvar-datasphere-project`),
found and verified 2026-08-24 — `project get` returns 200 and `job list` returns jobs. The id
recorded previously (`bt14qn4u9t3n09nfjoqu`) is dead and returns 403; this one was created the
same day it died. Not obtainable from `yc`, which has no `datasphere` group at all — it was found
by grepping the workspace for the id pattern and testing each candidate against the REST API.

```bash
cd compute/datasphere
GRPC_DNS_RESOLVER=native datasphere project job execute -p bt12q57tmrs03pnt8drc -c config.yaml
```

The CLI writes pages of `ev_poll_posix.cc … FD from fork parent` to **stderr**; filter stderr
rather than stdout or the job table is unreadable. `:unitBalance` returns `NOT_FOUND` for this
project despite `project get` succeeding, so **cost is not checkable headlessly** — this is paid
compute (~$1.38/h for the `g1.1` T4 below), so treat that as a reason to keep runs short and
counted rather than as permission to ignore it.

`GRPC_DNS_RESOLVER=native` is not optional — see `ccm-intro/docs/compute-yandex-datasphere.md`
§"Local DNS quirk", where grpc's bundled resolver fails in a sandboxed shell and the error names
neither DNS nor the resolver.

**Cost.** `cloud-instance-type: g1.1` is a single T4. The smoke is ~20 min of compute. Raise the
instance only for a real run, and read §3 of the compute doc first.

## What it checks, in order

1. Image: python, GPU, torch+CUDA, and **mujoco's two attributes** that decide whether the eval
   regimes can run at all.
2. Clones `RL-ViGen` and `dmc_gb` from their **public** urls at the SHAs in `PINS.json`, and
   prints asked-vs-got rather than assuming the fetch landed where it was told.
3. Applies P1–P12 with `setup/apply_patches.py`, then re-runs it with `--check`, which also
   verifies the tree carries nothing undeclared.
4. Applies `patches/dmc_gb.patch`. `git apply` fails loudly on any context mismatch, so this is a
   real test that the exported patch belongs to that commit.
5. **RAD at `--eval_mode eval-easy`** — the regime Kaggle cannot reach.
6. **SVEA on RL-ViGen's own `train.py`**, with the eval env in `eval-easy` via P12. Carries
   `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python` and `replay_buffer_num_workers=0`, both of
   which were needed to get any signal out of this stage on Kaggle, and `-X faulthandler` so a
   fatal signal names a file and a line instead of vanishing.

## Keeping this in sync

`PINS.json`, `apply_patches.py` and `patches/` are copies. Refresh before any real run:

```bash
python scripts/deviations.py --export
cp runnable/_patches/*.patch compute/datasphere/patches/
cp setup/apply_patches.py compute/datasphere/
```

Two copies of one source of truth drift silently — `ccm-intro/docs/compute-procgen.md` §2.1
records that happening once already, where a stale uploaded snapshot would have reproduced bugs
that were already fixed locally.

## Why these pins — moved out of `requirements.txt` 2026-08-24

The CLI's requirements parser rejects full-line comments (`Expected package name at the start of
dependency spec`), so the rationale lives here instead of beside the pins. Do not re-add comments
to that file; it fails locally in under a second and nothing reaches the cloud.

- **`mujoco==2.3.7` is the entire point of using DataSphere.** RL-ViGen's texture modder reads
  `MjModel.tex_rgb`, removed in mujoco 3.0, so every `eval-*` regime needs 2.x — and 2.3.7 is the
  last 2.x release with wheels, stopping at **cp311**. Kaggle is cp312 and therefore cannot run
  the eval regimes at all; this job pins python 3.11, where the wheel exists.
- The set is pinned to what this workspace actually runs, verified end to end by
  `bash runnable/_launch/smoke_all.sh` (12/12 TRAINED, 2026-08-17).
- `hydra-submitit-launcher` — `cfgs/config.yaml` declares `override hydra/launcher: submitit_local`.
- `tensorboard` — RL-ViGen's `logger.py:13` imports `SummaryWriter` unconditionally.

## First cloud run, 2026-08-24 — what it settled and what it did not

The job reached the cloud and printed its base-image report. Three results, in order of how much
they matter:

**1. The eval regimes are reachable here. This is the finding the whole job existed for.**

```
python 3.11.13 | mujoco 2.3.7 | MjData.qM True | MjModel.tex_rgb True
```

Both flags True, so `eval-easy` runs. Kaggle cannot do this at any python version it offers
(C29), which makes DataSphere the only remote route to a retention number.

**2. `torch` could not see the GPU, and that is why the job returned 1.**

```
Tesla V100-PCIE-32GB | driver 535.261.03
torch 2.13.0+cu130 | cuda 13.0 | available False | NO GPU
```

The image ships a **cu130** torch against a **535** driver. CUDA 13.0 needs r580+; 535 tops out
around 12.2. So the GPU is present and unusable. `requirements.txt` does not pin torch, so this
is whatever the image supplies — pinning a cu12x build is the obvious fix, but it also changes
the dependency stack away from the local one, which is exactly the un-hashed axis
[C29](../../docs/CONSTRUCTION.md#c29) is about. Decide that deliberately rather than by pinning
whatever works.

**3. `g1.1` is not a T4, and this file said it was.** The line read
`cloud-instance-type: g1.1  # one T4`. Per the price table, `g1.1` is a **1× V100 at $2.76/h** —
double `gt4.1`'s $1.38 and above the ceiling set for this project. A job was submitted on it
before the table was checked; it ran ~5–9 minutes. Corrected to `gt4.1`. **The comment was the
error, and a wrong comment on a cost line is worse than none.**
