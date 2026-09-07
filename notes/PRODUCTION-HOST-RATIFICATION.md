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

**The reported curve is seven points, and a disk decision set that.** `SAVE_EVERY_FRAMES=50000`
writes twelve stamps plus the endpoint; `preserve_snapshots=100000` retains six plus the endpoint;
curve evaluation runs against what retention kept. `families.json`'s own reason is that a
50k-spaced curve is "twice as dense as any plot needs" — defensible, and I agree with it, but it
means a presentation parameter is currently set by a storage argument. Recommend leaving it at
100k and stating the spacing in the results write-up; raising it is a `preserve_snapshots` change
plus the §5 disk arithmetic, nothing structural.

**Trajectory-grid cost is the campaign's largest unmeasured term.** Corrected here after I got
it wrong twice in one session, which is the useful part of the record. I first reported that the
curve is seven points for the RL-ViGen five and thirteen for the others, and proposed unifying it.
Both the finding and the proposal were artefacts of reading the **base** descriptor: `rlvigen`'s
base `preserve_snapshots` of 100000 is a DataSphere container-disk value, and its v100 profile
already overrides it to 50000. On the profile production runs, all twelve baselines keep twelve
stamps plus the endpoint — which `production_gates.gate_checkpoint_cadence_matches_fleet`
independently pins, and which is what failed when I "fixed" the non-problem in `families.json`.
Both instruments are now profile-aware and default to v100.

What is genuinely open is the cost. `plan_production.curve_eval_hours`, rewritten to read the
resolved descriptor and the measured per-episode wall-clock rather than training FPS, puts the
trajectory grid at **325 GPU-h** against 601 GPU-h of training — where `PRODUCTION-CALENDAR.md`
had 176, computed by hand against a flat 12 s/episode. The gap is not a modelling preference: the
measured rates are 9 s/episode for `rlvigen` and 25 for `idaac`, and **six of twelve baselines have
no measurement at all** and carry `audit_job_budgets.UNMEASURED_DEFAULT = 30`. So the true figure
lies between roughly 160 and 325 GPU-h, and which end decides whether the trajectory grid costs a
week.

Implemented default: leave the cadence alone (uniform 13 points is the fleet decision and is what
makes curves comparable) and **measure the six missing per-episode rates during the step-2
throughput calibration**, which is one number per family from a run that has to happen anyway.
Recommend against pre-emptively thinning the grid on an estimate — the same estimate that has been
wrong by 2x once already in this file.

**Related, and fixed rather than left open**: `preserve_snapshots` had no mechanism outside
`rlvigen`. `family.py` expressed it as `RLVIGEN_PRESERVE_SNAPSHOTS`, which only P18's patch in
RL-ViGen's `train.py` reads, so for six families the field was inert — a descriptor key that
silently did nothing. `family.py retain` now thins the retained grid by position for every family,
so the field means the same thing everywhere. On the current fleet settings it is a no-op
(preserve equals save_every on v100), which is the correct behaviour, not an absence of one.

**No `--memory`/`--cpus` caps.** Deliberate, and I recommend keeping it until step 2 measures peak
RAM/CPU: a cgroup cap guessed before the measurement converts an honest overcommit into an
OOM-kill mid-run. Add them once real numbers exist.

## Still unverifiable from here

Nothing in either document has been executed on `cds2`. Outbound network access, a working
`nvidia-container-toolkit`, whether the SSH user can reach the Docker socket without `sudo`, and
host contention with other users are all assumptions the runbook's §1 checks are designed to
settle on first contact.
