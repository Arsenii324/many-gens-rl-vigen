# Production-host execution: rationale, defect history, and what the owner still decides

Companion to [`RUNNING-ON-PRODUCTION-HOST.md`](RUNNING-ON-PRODUCTION-HOST.md), which is the
operator runbook and deliberately carries no reasoning. This file holds the reasoning, the history
of what was wrong before, and the decisions that are the owner's rather than mine — the same
two-layer split the DECISION-SHEET uses: implemented at my best now, formally open until ratified.

## Why this surface exists at all

Checked directly on 2026-09-07, not from memory: `PRODUCTION-RUNBOOK.md`, `MIGRATION-T4-TO-V100.md`,
`PRODUCTION-CALENDAR.md`, `draft-codex-parallel-preproduction-plan-under-review.md` and
`remote-infra.txt` between them give the value deltas for the V100, the failure signatures to watch
for, the calendar arithmetic, and the raw hardware facts. **None of them contained a command that
runs a cell on the host.** Every execution tool this project built — `job.sh`, `contract.py`'s
submit path, every `cfg-*.yaml` — targets DataSphere's job API, which `cds2` is not behind.

The gap turned out to be small because `run_probe.sh` was already platform-agnostic: it bootstraps
its own environment from a bare CUDA image with `apt-get`/`pip`, takes positional arguments and
environment variables, and writes a result archive to a local path. It has always been runnable
under a bare `docker run`. What was missing was the wrapper and a document saying so — not a
subsystem.

## Defects found and fixed, 2026-09-07

The first version of the wrapper was written against the *diagnostic* `cfg-*.yaml` configs and
inherited their assumptions. Being asked whether the design suited a genuine production run
surfaced four defects; three were real, and the first would have wasted the canary.

1. **`NATIVE_PRODUCTION` was never forwarded.** `run_probe.sh` exits 3 at `FRAMES >= 600000`
   without it (its line ~404) precisely because `apply_production_settings` would otherwise apply
   nothing and train a full-length run at probe cadence while completing successfully. Since the
   forwarding allow-list was built from diagnostic configs, every production cell — the 600k canary
   included — would have died *after* paying the full container bootstrap, with the failure looking
   like a config error rather than a wrapper bug. Fixed, and both of `run_probe.sh`'s production
   refusals are now raised on the host before the bootstrap.
2. **`NATIVE_CONCURRENT` was never forwarded**, silently disabling cell packing — the capability
   `MIGRATION-T4-TO-V100.md` step 4 exists to use. Fixed. This also corrected a wrong belief I had
   stated earlier in the session: packing is one container running a comma-separated `CELLS` list,
   not two concurrent invocations of the wrapper.
3. **Partial output was not durable.** `run_probe.sh` keeps every checkpoint and `training.log` in
   the container-local `/tmp/native-out` and copies nothing out until its closing
   `tar -czf "$result" -C "$out" .` (line 1546). A container killed before that line lost the whole
   run. Now bind-mounted to the host, defaulting outside the `mktemp -d` the EXIT trap removes —
   the trap fires on a crash too, which would have deleted exactly the partial run the mount
   exists to save.
4. **Not a defect, after checking: `--rm`.** Dropping it would preserve the container's writable
   layer for `docker cp` recovery, but only after the container *exits*, gives nothing during the
   run, and leaves multi-GB dead layers on a shared host. The bind-mount covers the same failures
   strictly better, so `--rm` stays.

## Decisions implemented at my best, still open for ratification

**Disk floor is a single number, not per-family.** The script refuses a production cell below
60 GB free. That figure is derived in the runbook's §5 from `families.json`'s own
`replay_capacity` and `preserve_snapshots` values, but it is one constant covering families whose
real needs differ by an order of magnitude — an off-policy cell needs ~25 GB, an on-policy one a
small fraction. **The better version** is a `disk_gb` field in `families.json` beside the existing
`memory_note`/`fixed_peak_gib`, resolved per cell the way memory already is. Not done, because
adding a disk column means measuring it per family the way the memory figures were measured, and
no measurement exists yet — a guessed column next to measured ones would be worse than one honest
constant. Recommend: measure disk during the step-2 throughput calibration, then replace the
constant.

**Free disk on the host is unmeasured.** `remote-infra.txt` records RAM and GPU occupancy but no
`df`. The 60 GB floor has therefore never been checked against the machine it guards. This is a
one-line check the owner or the first host session can settle; until then the floor could be
either redundant or insufficient.

**Resume is not crash recovery for off-policy cells.** No baseline persists its replay buffer —
for RL-ViGen because upstream hardcodes `_save_snapshot = False` (`replay_buffer.py:94`), for
`dmc_gb` and `alda` because their buffers are in-memory structures never written out. So resuming
one of the nine off-policy cells from a stamp restarts it against an empty buffer, which is a
different experiment from an uninterrupted run. Implemented default: **do not resume; rerun the
seed from zero**, consistent with `EVAL-PROTOCOL.md`'s existing missing-run policy (rerun a crashed
seed under the identical seed, no post-hoc replacement seeds). The alternative — declaring
resumed-with-empty-buffer runs admissible and labelling them — would save wall-clock on a long
crash but introduces a category of run whose comparability nothing currently verifies. Recommend
the rerun; the owner may prefer the saving.

**Curve cadence is profile-dependent.** The DataSphere base profile uses
`preserve_snapshots=100000` for RL-ViGen, keeping six stamps plus the endpoint. The resolved v100
production profile overrides that value to `50000`, so every family keeps twelve stamps plus the
endpoint. The generated checkpoint-semantics table and production gate both resolve the v100
profile; this is the operational production default, pending formal ratification.

**Trajectory-grid cost — RESOLVED 2026-09-07, and it cost nothing to resolve.** This entry
previously recorded a 165 GPU-h uncertainty (160-325) because six of twelve baselines had never had
an evaluation episode timed and carried `audit_job_budgets.UNMEASURED_DEFAULT = 30 s/episode`, and
recommended measuring them during the step-2 throughput calibration on the production host.

**They did not need a host trip.** The v176 evaluator-validation wave already ran an endpoint grid
per family, all seven at the identical scope (2 regimes x 1 scene x 5 episodes = 10 episodes), and
every job's log carries its own `NATIVE_ENDPOINT_EVAL_SECONDS`. Extracting them gives 9.0, 8.6, 9.5,
10.6, 8.9, 9.9 and 10.2 s/episode — **every family between 8.6 and 10.6, against a placeholder of
30**. The method validates itself: drqv2's extracted 90s/10 reproduces the independently measured 9
from a different job at a different scope.

The trajectory grid is therefore **148 GPU-h against 601 of training, 25%** — below even the
optimistic end of the range this entry used to carry, and with no family estimated. The recommendation
to measure on the host is withdrawn as unnecessary; what remains is the caveat that these are
single-scene 10-episode grids against production's ten-scene 800-episode one, which the canary
checks.

**The lesson worth keeping**: the measurement had existed for a day, inside jobs run for a different
purpose, and the plan called for buying it again on scarcer hardware. Before scheduling a
measurement, check whether a completed job already contains it.

**Related, and fixed rather than left open**: `preserve_snapshots` had no mechanism outside
`rlvigen`. `family.py` expressed it as `RLVIGEN_PRESERVE_SNAPSHOTS`, which only P18's patch in
RL-ViGen's `train.py` reads, so for six families the field was inert — a descriptor key that
silently did nothing. `family.py retain` now thins the retained grid by position for every family,
so the field means the same thing everywhere. On the current fleet settings it is a no-op
(preserve equals save_every on v100), which is the correct behaviour, not an absence of one.

**The memory model's two uncovered terms, named rather than implied.** `check_memory` now sizes a
cell as `fixed_peak_gib + memory_margin_gib + replay`, and the replay term agrees with
`plan_production`'s schedule exactly (dmc_gb: 2.58 floor + 16.76 replay = 19.34, the planner's own
`rad` row; rlvigen: 3.33 + 35.49 = 38.82 against the schedule's 38.78). The growth constant is
empirically confirmed — the endurance job's tree RSS moved 10.6 to 15.8 GiB over 100k frames and
the model predicts 5.91 GiB of growth against the 5.2 observed. What it does not cover:

* **The floor is a probe-scale measurement.** rlvigen's 3.33 GiB comes from job
  `bt1anj1cm0ni7p20ted3`, whose own frame budget is not recorded anywhere in this tree — no config
  and no retained record survives — so the double-count of that job's own replay cannot be
  subtracted without inventing provenance, and is not. More importantly a transient that first
  appears later than the probe (the allocator's high-water mark after a checkpoint serialisation,
  say) is not in the floor at all. `memory_margin_gib = 2.0` is what covers that, and it is a
  judgement rather than a measurement of any such transient. `fixed_peak_measured_at_frames` is
  the descriptor field a future measurement should declare.
* **GPU memory is not checked.** `check_memory` is host RAM only. `plan_production.ENVELOPE`
  carries per-baseline `vram_mib` — sgqn's 7142 is the largest, against a 32 GiB V100 — so nothing
  is near that ceiling solo, but a packing decision taken from this function alone is reasoning
  about one resource and not the other.

**No `--memory`/`--cpus` caps.** Deliberate, and I recommend keeping it until step 2 measures peak
RAM/CPU: a cgroup cap guessed before the measurement converts an honest overcommit into an
OOM-kill mid-run. Add them once real numbers exist.

## Still unverifiable from here

~~Nothing in either document has been executed on `cds2`.~~ **Superseded 2026-09-08:** cells have
now been launched there, and first contact settled every assumption in this paragraph.

## First contact, 2026-09-08 — what the assumptions turned out to be

| assumption | settled |
|---|---|
| outbound network access | works, and is **slow**: 1710 MB of wheels at 162–835 kB/s, the largest slowest (`nvidia_cudnn_cu12`, 731.7 MB, 161.6 kB/s). `pip` ran over two hours against `apt` at 71 s |
| `nvidia-container-toolkit` | works for compute; **not for rendering by default** — see below |
| Docker socket without `sudo` | yes; no `sudo` was needed at any point |
| contention with other users | real and normal. Card 1 carried a neighbour's job at 16 GB / 100% for hours while we used card 0; nobody was disturbed, and our watchers confirmed exclusivity on card 0 at every poll |

**The finding that mattered was none of those.** A GPU container gets
`NVIDIA_DRIVER_CAPABILITIES=compute,utility` from docker's `--gpus`, and `graphics` — the
capability that installs `libEGL_nvidia` — was never set anywhere in this repo. The first cell to
reach the renderer died with `RuntimeError: software EGL renderer: llvmpipe (LLVM 15.0.7, 256
bits)`. DataSphere had been setting it for us. Fixed in `run_on_production_host.sh`; measured on the
host both ways before and after.

This is the clearest vindication of the runbook's own premise: the §1 checks are worth running
because the thing that bites is the assumption nobody wrote down, and it bit at the renderer rather
than at any of the four items above.

**What is still unexecuted:** the chain itself. No cell has yet trained, checkpointed, reloaded in a
fresh process, run the endpoint grid and written a record on this host. The 2026-09-08 attempt
stopped at the renderer check, which is progress on the bootstrap and none on the chain.
