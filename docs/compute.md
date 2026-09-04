# Compute

## What runs locally

Everything in the verification path. Measured on an M2 Pro (MPS, **no CUDA anywhere**):

| | |
|---|---|
| robosuite pixel stepping | 79–118 steps/s per environment, all six task × mode combinations |
| `pytest tests` | the full suite; `-m "not slow"` skips the simulator. Current timings in [`VALIDATION.md`](VALIDATION.md) |
| `mutants/run.py` | ~4 min, 14 curated mutants |
| `mutants/sweep.py -n 40` | ~15 min, unbiased operator sweep |
| smoke train + eval + plot | ~6 min end to end on the real environment |

`train.sh` selects MPS automatically (`TrainConfig.resolve_device`: cuda → mps → cpu). Conv-heavy
work is roughly 60× faster on MPS than CPU **in general on this machine** (undated in this file
until now — the figure predates this note and its own origin measurement isn't cited here), so the
fallback matters — and it is *reported*, never silent, because a run demoted to CPU that still
claims otherwise poisons every later timing. **For the specific idaac/Door training-loop workload
measured 2026-08-16 below, the real ratio was ~5.2×, not ~60×** — see that entry for the numbers
and the contention caveat. Both can be true (a workload with a smaller/cheaper encoder, or a
robosuite-physics-stepping-dominated one, could plausibly see less MPS benefit than a
larger-network, GPU-bound one); the 60× figure should not be assumed to transfer to every workload
in this codebase without its own measurement.

## What does not

A full matrix is 500k frames × 12 baselines × 2 tasks × ≥3 seeds. At the local ~100 steps/s that
is months of wall-clock, and evaluation alone (100 episodes × 500 steps per point, 10 points per
run) is ~8 min per point sequentially. Full runs are remote work.

> **A third route exists, noted by the owner 2026-08-25: a V100 that is reasonably free to them,
> and NOT DataSphere.** This matters because it is outside the standing DataSphere cost ceiling
> (T4-class `gt4.1`/`gt4i.1` only, at most two parallel runs) — that constraint is about DataSphere
> pricing and does not govern this machine.
>
> **What it unblocks, concretely.** Two of the five RL-ViGen natives are stuck on hardware rather
> than on any decision:
>
> - **`curl`** cannot run under the MPS shim at all (`scatter: index -1`, [C52](CONSTRUCTION.md#c52)),
>   and CPU is ~60x slower for conv work here. CUDA is the only route, so a V100 is the difference
>   between a `curl` cell existing and not.
> - **`sgqn`** is ~11h per cell locally ([C60](CONSTRUCTION.md#c60)). On a V100 it becomes an
>   ordinary run rather than an overnight commitment — **but it is gated by
>   [C64](CONSTRUCTION.md#c64), not by hardware**, and running it before its `aux_lr` is settled
>   spends the run on a configuration that may be discarded.
>
> Access is described as theoretic, so treat it as an option to plan against rather than a resource
> to assume. Nothing here has been run on it.
>
> **Corrected 2026-08-26 after reading [`RUNNABLE-ORIGINALS.md`](RUNNABLE-ORIGINALS.md) in full —
> the V100 is preferable to Kaggle for `curl`, and the reason is not speed.**
>
> 1. **`curl` is not unrunnable locally.** It trains on **CPU**, exit 0 (`RUNNABLE-ORIGINALS.md`'s
>    status table); what fails is the MPS shim ([C52](CONSTRUCTION.md#c52)). `run_cell.sh` refuses
>    it because CPU is ~60× slower for conv work, not because it cannot run. "Needs CUDA" was too
>    strong.
> 2. **Kaggle would train `curl` under a different physics version.** Kaggle is Python 3.12,
>    `mujoco 2.3.7` has no cp312 wheel, so a kernel resolves to mujoco 3.2.7. That satisfies
>    robosuite and breaks only the *eval* regimes — so training does work — but the resulting
>    checkpoint would be the only one in the project trained under **mujoco 3.x** while every other
>    cell is 2.3.7. Evaluating it locally does not undo that. [C29](CONSTRUCTION.md#c29) already
>    records that the protocol hash omits dependency versions, so nothing would catch it.
> 3. **A V100 on Python ≤ 3.11 installs `mujoco==2.3.7` from a wheel and matches this machine
>    exactly** — the environment `RUNNABLE-ORIGINALS.md` names as belonging in any real run's spec,
>    alongside `dm-control==1.0.14`, `gym==0.25.2` and robosuite from `third_party`.
>
> **Answered 2026-08-26: the owner will use Docker, so the host's Python is not the constraint —
> we choose it. And tag-specified images are already prior art in this workspace, not new work.**
>
> | image, already in use | base | Python | `mujoco==2.3.7` wheel |
> |---|---|---|---|
> | `nvidia/cuda:12.2.2-runtime-ubuntu22.04` | 22.04 | 3.10 | **cp310 — yes** |
> | `nvidia/cudagl:11.4.2-runtime-ubuntu20.04` | 20.04 | 3.8 | **cp38 — yes** |
> | `nvidia/opengl:1.2-glvnd-runtime-ubuntu20.04` | 20.04 | 3.8 | **cp38 — yes** |
>
> The first is used by this project's own `datasphere/cfg-probe.yaml:18` and
> `cfg-train-fps.yaml:15`; all three are used by the sibling `projects/gen-rebuttal/datasphere/`.
> The `cudagl` and `opengl` variants exist because that project needed GL inside a container, which
> is the same requirement robosuite rendering has here.
>
> **So the environment-parity problem is solved by prior art**: pick a GL-capable image on ≤3.11,
> `pip install mujoco==2.3.7 dm-control==1.0.14 gym==0.25.2` plus robosuite from `third_party`, and
> the container matches this machine. `curl` and (behind [C64](CONSTRUCTION.md#c64)) `sgqn` then
> have a clean route with no cross-version checkpoint.
>
> **The earlier "a custom Docker image is not worth building" note does not apply and should not be
> cited here.** That measured *building a bespoke image* against pip time on DataSphere — an
> 8.5%-of-runtime speed argument. Using a **standard tagged** image is not that, and what it buys
> is not speed but environment parity, which is a correctness requirement.

> **Superseded — the V100's own Python no longer matters, see above.** If ≤3.11 it is the clean route for `curl` and for
> `sgqn` (behind [C64](CONSTRUCTION.md#c64)). If it is 3.12, it inherits Kaggle's exact problem and
> the choice becomes "cross-version checkpoint" versus "slow CPU run", which is a decision rather
> than an obvious win.

**Kaggle was noted exhausted for this account as of some earlier, undated point before this
file's 2026-08-16 entries below** — that claim itself was never timestamped when first written,
which is the actual defect (an unstamped claim decays silently and nobody can tell when it needs
re-checking). Re-checked 2026-08-16: `kaggle quota` fails with a CLI bug (`not enough values to
unpack`, CLI 2.2.3, all output formats) rather than reporting a number; `kaggle kernels list -m`
shows real completed activity as recent as 2026-08-15, which doesn't prove GPU-hour quota is
free but does mean the account is live. **Status as of 2026-08-16: not confirmed exhausted, not
confirmed available — genuinely unknown, re-check via kaggle.com's own quota page or a fixed CLI
before relying on either answer.**

> **Resolved 2026-08-24. It is neither exhausted nor free: `26.12h` of `30.00h` used, leaving
> `3.88` GPU-hours, refreshing `2026-08-29 00:00:00`.** Read as a log entry, not a description of
> the present — the figure moves whenever any kernel runs, and most of the 26h was spent by
> unrelated `tlab-*`/`geometry-*` kernels on this account, not by this project.
>
> **The CLI genuinely cannot tell you this, and the reason is a client-side parsing bug rather
> than a permissions or account problem.** `kaggle quota` fails with `not enough values to unpack
> (expected 2, got 1)` because `kagglesdk/kaggle_object.py`'s `TimeDeltaSerializer` documents its
> own format as `"<seconds>.<nanoseconds>s"` and splits on the `.` — but the server returns whole
> seconds as `"108000s"`, with no decimal point at all. So the bug fires precisely when a duration
> happens to be a round number, which is why it looks intermittent. Patch it in memory and ask the
> API directly (the `kaggle` package lives in **`/Users/a2mogus/anaconda3/bin/python`**, not in
> either project venv):
>
> ```python
> import kagglesdk.kaggle_object as ko
> _o = ko.TimeDeltaSerializer._from_dict_value
> ko.TimeDeltaSerializer._from_dict_value = staticmethod(
>     lambda v: _o(v[:-1] + ".0s" if isinstance(v, str) and v.endswith("s") and "." not in v else v))
> from kaggle import api
> q = api.quota_view()
> print(q.gpu_quota.time_used, q.gpu_quota.total_time_allowed, q.quota_refresh_time)
> ```
>
> Account is `arsen4ikvar` (verified from `~/.kaggle/kaggle.json`), `has_ever_run: True`.
> TPU quota is untouched at 0 of 20h — irrelevant here, since nothing in this project targets TPU.
>
> **What this does and does not unblock.** It does not make Kaggle a route for the *eval* regimes:
> those need `mujoco` 2.x for `MjModel.tex_rgb` (robosuite's texture modder), there is no cp312
> wheel, and Kaggle runs Python 3.12 — established by three real T4 kernel runs on 2026-08-17
> ([`RUNNABLE-ORIGINALS.md`](RUNNABLE-ORIGINALS.md), and [C29](CONSTRUCTION.md#c29)). It does
> unblock `train`-regime work, and headless GL/EGL rendering itself is **not** the obstacle —
> `RUNNABLE-ORIGINALS.md` records RAD training end-to-end on a real T4 with real robosuite envs.
> Use `machine_shape: NvidiaTeslaT4`; `enable_gpu` alone yields a P100 (sm_60) that Kaggle's torch
> build does not support. The other remaining route is **Yandex DataSphere** — the
workspace notes are in [`../../docs/compute-yandex-datasphere.md`](../../../docs/compute-yandex-datasphere.md)
and account details in [`../../docs/compute-yandex-accounts.md`](../../../docs/compute-yandex-accounts.md).

**Measured 2026-08-16, real end-to-end training (not just env stepping): `idaac`, Door, MPS,
`num_steps=256`, `epochs_policy=10` (default), 2048 frames, 8 real PPO updates.** Steady-state
throughput `train/fps: 12.16` (trainer's own log — 2048 frames / 168.4s of pure training
wallclock, excluding eval). This is the actual bottleneck being NN forward/backward through the
IMPALA encoder plus the 10-epoch PPO update, not env stepping (the "79–118 steps/s" figure above
is pure `env.step()`, no policy or gradient work — likely a real overstatement of achievable
*training* throughput if read as the training rate, though see the caveat below on how clean this
number is). At this measured rate, one baseline/one seed at the real launch budget
(`configs/vigen.yaml`'s `total_frames: 500000` — NOT `idaac/config.py`'s own dataclass default of
`1_000_000`, which is dead at every real launch, the same "declared but overridden" shape this
project's audit has found elsewhere) is **~11.4 hours**; 12 baselines × 3 seeds
(`docs/rl-experiment-runbook.md`'s own stated floor for a defensible claim) run sequentially is
**~411 hours ≈ 17.1 days**. Not (yet) measured: whether the 8 SAC/DrQ-family baselines cost less
per frame (likely, cheaper off-policy updates) or whether PPG/IBAC-SNI/CTRL cost more than IDAAC
specifically — this number is a single-method anchor, not a matrix-wide one.

**Caveat, found after the fact, 2026-08-16: this number was NOT measured in isolation.** A
completely unrelated job on this same machine (`rl_algorithms.disentaglement.code_ppo.model`,
`--num-envs 128`, a different project entirely) was running the whole time the MPS probe ran, and
system swap was already at ~80% (`vm.swapusage`) before the probe even started. Load average
during the measurement was ~6.9–7.5. **12.16 fps is therefore a lower bound measured under real
contention, not a clean number for this hardware's actual ceiling** — it could be meaningfully
faster run alone. Treat every "hours"/"days" figure above as pessimistic until re-measured on an
otherwise-idle machine; the qualitative conclusion (a full sequential sweep is a multi-day-to-
multi-week undertaking, not an hours-scale one) is unlikely to flip even at 2–3× faster, but the
exact numbers should not be treated as precise. A CPU-only comparison run (`device=cpu`), launched alongside the MPS one under the same
contention, completed at 875s pure-training time (2048 frames, same 8 updates) vs. MPS's 168.4s —
**~5.2× MPS speedup for this specific workload**, not the ~60× figure quoted above for this
machine's conv-heavy work in general (see that entry's own correction). Since both runs shared the
same contention, the ratio between them is more trustworthy than either absolute number, though
not perfectly clean if the competing job contends unevenly for MPS vs. CPU resources specifically
(plausible but not checked).

**Kaggle status is also unverified, not confirmed exhausted, as of this note.** The CLI's own
`kaggle quota` command errors (`not enough values to unpack (expected 2, got 1)`, CLI 2.2.3, both
table and JSON output formats) — a tool bug, not obviously an auth or account-state signal.
`kaggle kernels list -m` does show real, successfully-completed activity as recent as
2026-08-15T23:19 (yesterday, relative to this note), so the account is reachable and being used —
that doesn't by itself prove GPU-hour quota is available (a kernel can complete on CPU only), but
it does mean "exhausted" above should be read as **last confirmed at some earlier, undated point,
not re-verified live** — check kaggle.com's own account/quota page (or fix the CLI bug) before
treating it as current. Corrected here because a stale "exhausted" claim was about to be relied on
for a real scope decision without being re-checked.

**Given the above, the earlier framing in this file — "no remote route was available, full stop" —
overstated the certainty.** What is actually established: (1) local-only, sequential, this hardware
alone is genuinely a multi-day-to-multi-week undertaking for a defensible 12×3-seed study, even
allowing the contention caveat above; (2) Yandex DataSphere was explicitly excluded by the user for
the arc of work that produced this note; (3) whether Kaggle specifically is actually available was
not resolved, only assumed from a note that wasn't re-checked. The decision actually made — do not
launch a full local sweep, continue the porting-directive.md fidelity/comparability work instead —
still stands on its own terms (that work is real, durable progress independent of whether a study
is later run), but was not, in fact, forced by "no remote option exists at all." If Kaggle turns
out to be live, that changes what's *possible* for a future study; it does not retroactively make
the porting-directive.md work the wrong thing to have prioritized in the meantime.

### What a remote box needs beyond `setup/install.sh`

1. **`MUJOCO_GL=egl`**, set *before* mujoco is imported, in the process that builds the
   environment. `baselines/*/train.sh` already branches on `uname`, so it is handled if you launch
   through the script.
2. **A headless GL stack.** RL-ViGen renders offscreen; on a bare Linux image that means the
   NVIDIA EGL libraries plus `libglew`/`libosmesa` depending on the driver.
3. **The vendored robosuite, editable.** `setup/install.sh` does it; a wheel build silently drops
   the assets (see [`../setup/VENDORED.md`](../setup/VENDORED.md)).
4. **Checkpoint resume.** Sessions are time-capped. `rlgen/trainer.py` writes
   `checkpoint.pt` every `save_every_frames`; resuming from it is **not yet implemented** —
   `train(..., resume=...)` is accepted and ignored. Wire it before launching anything longer than
   a session limit.
5. **Private uploads only.** This is unpublished lab work: datasets, notebooks and artifacts stay
   private. The W&B key lives at `ccm-intro/secrets/wandb_key.txt`, is never printed and never
   committed; on a remote box install it with a piped `printf` into a `chmod 600` file.

### Sizing

One 500k-frame Door run is ~500k env steps plus ~250k gradient steps. On a T4 the physics is
CPU-bound (RL-ViGen renders on CPU for robosuite), so throughput is governed by vCPU count more
than by the GPU — budget by *steps/s measured on the target box*, not by GPU class. Measure one
10k-frame run before committing to a matrix, and record the number in this file.

## Before any remote launch

```bash
python setup/apply_patches.py --check
python setup/install_assets.py --check
pytest tests -q
python mutants/run.py
```

An unpatched upstream evaluates on the training distribution and reports it as generalisation
(see [`../instruction.md`](../instruction.md) §3). That is the failure worth spending four minutes
to exclude.
