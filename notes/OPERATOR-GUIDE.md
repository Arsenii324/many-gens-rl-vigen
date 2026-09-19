# Operator guide — the whole path, end to end

**You are here because you have this repository and a production host, and nothing else.** This
file is the **map**: what exists, what produces what, what runs after what, and which tool belongs
to which stage. The executable procedure with its reasoning is
[`RUNNING-ON-PRODUCTION-HOST.md`](RUNNING-ON-PRODUCTION-HOST.md) (referred to below as **the
procedure**, cited by section). This page restates commands in one place only: §5.2, the sequence
for one cell, copied from the sessions that ran it on 2026-09-16/17. Anywhere else, a command here
that disagrees with the procedure is a defect in one of the two.

Read this once, top to bottom, before running anything. It is about 15 minutes. Then work from the
procedure with this page open beside it.

- **What is true right now** (what is running, what is banked, what is blocked):
  [`CURRENT-STATE-AND-RESPONSIBILITY.md`](CURRENT-STATE-AND-RESPONSIBILITY.md). It goes stale by
  design; re-run the commands it names rather than trusting its numbers.
- **Why things are the way they are**, and every incident behind a rule:
  [`production-host/README.md`](production-host/README.md), 35 numbered notes.
- **What someone was thinking mid-flight**, including unproven suspicions:
  [`HANDOFF.md`](HANDOFF.md).
- **Index of every surface**: [`START-HERE.md`](START-HERE.md).
- **Getting from `git clone` to a submitted run, on any Docker host**:
  [`../docs/RUN-THIS-PROJECT.md`](../docs/RUN-THIS-PROJECT.md). That is the canonical cold start and
  this page does not repeat it; §4b says how the two fit together.

What this page deliberately does **not** cover, and where it lives instead. Read these when the
question is *what a number means* rather than *how to produce it*:

- **What was asked, as checkable criteria (R1–R7):** [`../docs/TASK.md`](../docs/TASK.md).
- **Which claim the design can support:** [`../docs/RESEARCH-FRAME.md`](../docs/RESEARCH-FRAME.md);
  where the project stands against the original goal:
  [`../docs/STATUS-AGAINST-THE-GOAL.md`](../docs/STATUS-AGAINST-THE-GOAL.md).
- **The evaluation protocol** — the grid, the endpoint-as-headline rule, the seed rule; its own
  status line says PROPOSED: [`../docs/EVAL-PROTOCOL.md`](../docs/EVAL-PROTOCOL.md).
- **When two baselines' numbers may be compared:**
  [`../docs/COMPARABILITY_CONTRACT.md`](../docs/COMPARABILITY_CONTRACT.md), and per baseline what is
  actually emitted: [`../docs/PART2-METRIC-INVENTORY.md`](../docs/PART2-METRIC-INVENTORY.md).
- **The nine OWNER judgements and what to do if results look wrong because of one:**
  [`DECISIONS-IF-PRODUCTION-GOES-WRONG.md`](DECISIONS-IF-PRODUCTION-GOES-WRONG.md).
- **Every project document, routed:** [`../docs/PROJECT-INDEX.md`](../docs/PROJECT-INDEX.md).

---

## 1. What the campaign is, in five lines

Twelve reinforcement-learning baselines are trained on one RL-ViGen task (robosuite **Door**) for
600,000 frames each, at three seeds, and then evaluated on a fixed grid of visual regimes. The
question is **generalisation**: how much return survives moving from the training distribution to
held-out ones. A **cell** is one (baseline, seed) run — train, then evaluate. The campaign is
36 cells. A cell that has trained but not been evaluated and collected is **not** a result, and
`campaign_status.py` will keep saying so.

## 2. Three places code runs, and the rule that separates them

| Where | What runs there | Rule |
|---|---|---|
| **Your laptop** | every `scripts/*.py`, payload building, collection, audits, gates | Use the interpreter named in the procedure §0c. Not the system Python. |
| **The host shell** | `docker` commands, `ls`/`df`/`grep`, the wrapper shell scripts under `~/rlvigen-work/` | **Nothing else.** No `pip install`, no `apt`, no arbitrary Python, no global state changes. The host is shared. |
| **Inside a container** | the training and evaluation code, which installs its own dependencies | Self-contained by design; you never install anything for it. |

If a step seems to need Python on the host, it belongs on the laptop or in a container. That rule
has no exceptions, and the reasoning is in `production-host/`.

## 3. The objects, and what turns into what

This is the integration spine. Each arrow is a real producer/consumer relationship.

    setup/bootstrap_sources.py ──> reconstructed source trees under runnable/
              │                     (verified by setup/verify_sources.py)
              v
    contract.py build-payload ──> payload-vNNN-<family>.tgz ──┐
                                                              │   (scp to the host)
    setup/install_assets.py / the RL-ViGen asset archive ─────┤
    Places365 corpus (svea, sgqn, soda only; procedure §2b) ──┤
                                                              v
                                 launch-card-cell.sh <payload> <result> [rlvigen] [places365]
                                                              │
                                          ┌───────────────────┴───────────────────┐
                                          v                                       v
                              run_on_production_host.sh                    three watch containers
                                          │                                (§6 below)
                                          v
                                     run_probe.sh   (inside the cell container)
                                          │
                        ┌─────────────────┼──────────────────────┐
                        v                 v                      v
                 native-work/       native-out/            <tag>-result.tgz
                 (live, incl.       (retained AFTER        (only on clean
                  checkpoints        training: rows,        completion)
                  while training)     checkpoints)
                        │                 │
                        └────────┬────────┘
                                 v   (rsync to the laptop)
                     collect-host-run.sh <family> <run-dir>
                                 │
                                 v
                  results/records/<run-id>__records.jsonl
                                 │
              ┌──────────────────┼─────────────────────────┐
              v                  v                         v
     campaign_status.py   audit_record_frame_      populate_evaluator_ledger.py
     export_fleet.py      provenance.py            (ATTESTATION jobs only — see §8)
              │
              v
       production_gates.py  ──> launchable / not

**The one asymmetry worth memorising:** `native-out/` receives checkpoints only **after training
completes**. A cell stopped mid-training leaves them in `native-work/`, which the documented rsync
**excludes**. Fetch them explicitly or you will silently lose the only salvage from a failed run.

## 3b. The stage contract — what each stage leaves, and how to redo only it

The diagram above says what feeds what. This says, per stage: what it leaves **as a file**, who
reads that file, the one command that proves the stage worked, how to redo only that stage without
touching the ones around it, and — the column that most often gets assumed rather than checked —
what it does **not** leave. This table is written from stages that have actually run, not from what
should be true of them.

| stage | target state | artifact (exact path) | consumer | proves it worked | redo only this stage | does NOT leave |
|---|---|---|---|---|---|---|
| reconstruct sources | pinned upstream trees rebuilt | `runnable/<family>/` | `contract.py build-payload` | `setup/verify_sources.py` | re-run `setup/bootstrap_sources.py`; it overwrites `runnable/<family>/` in place | no payload, no verification of a *built* environment — only that the trees match the pin |
| build payload | one tgz per family, hash-bound | `payload-vNNN-<family>.tgz` | `launch-card-cell.sh` (scp'd to host) | `contract.py verify-payload <tgz>` | `contract.py build-payload <family>`; old tgz is not deleted, so a stale one can be scp'd by mistake — check the version number in the launch banner | no host-side install; the tgz is inert until a cell unpacks it |
| provision datasets | corpus present **on the host** | `~/rlvigen-assets/...` (host, outside git) | the cell's data loader at run time | `setup/verify_datasets.py --root <dir> --split <s>` **run on the host** | re-run the transfer step in procedure §2b; verifying on the laptop proves nothing about the host | no record on the laptop that this ran — nothing in `results/` reflects dataset presence |
| launch | one cell container, one watch budget | `docker ps` entry `cell-c<card>-<pid>`; launcher log `prod-v214/<tag>.log` | `watch-cell.sh`; `record_host_run.py` | banner line `container: cell-c<card>-<pid>` + disk floor printed in the log | re-run the launch block in §5.2 (checks for an existing result archive first, so it refuses rather than double-launches) | no entry in `results/host-runs.jsonl` — that is a separate, manual step (§5.2 "record the attempt") |
| train | checkpoints written as training proceeds | `native-work/<run-id>/...` (root-owned, host-side) | nothing yet — this is live state, not a delivered artifact | `training.log` growing; `free -g` and `docker ps` at the checkpoints in §7 | not redoable in place; a stopped cell is relaunched from zero (§6c: no family's resume path is exercised in this campaign) | no `native-out/` entry until training completes (§3's one asymmetry) — a mid-training stop leaves nothing there |
| complete / retain | checkpoints promoted, result archived | `native-out/<run-id>/...`; `<tag>-result.tgz` | `collect-host-run.sh` | the result tgz exists and its tag matches the launch | cannot be redone without re-running the whole cell; there is no "just re-package the outputs" | no laptop-side copy until collection runs — `native-out/` alone is not evidence anything was fetched |
| collect | rows on the laptop, on this closure | `results/records/<run-id>__records.jsonl` | `campaign_status.py`, `export_fleet.py`, `production_reading.py` | `audit_record_frame_provenance.py <records> --checkpoints <dir>` → MISMATCHED 0 | `BP=<interpreter> collect-host-run.sh <family> <run-dir>`; re-running it is safe, it does not mutate the host | no ledger entry — `record_host_run.py --update-status` is separate and easy to skip |
| ledger / gate | the run has a terminal status, gates see it | `results/host-runs.jsonl`; `production_gates.py` output | `audit_attempt_ledger.py`, the next launch's "does a result already exist" check | `audit_attempt_ledger.py --strict` → exit 0 | `record_host_run.py <run-id> --update-status` | nothing forces this step to happen; a completed cell with no ledger update looks, to the ledger, like it never finished |

And a companion list of **state that lives nowhere in this table**, because every defect found
during the 2026-09-18 adversarial pass came from state with no file behind it:

- **the pulled Docker image digest and layer cache** — a cell's runtime environment is rebuilt
  inside the container on every launch from whatever `docker pull` resolves to that day; no file
  records which digest actually ran a given cell;
- **the host's own checkout**, `~/rlvigen-work/repo` — at commit `672202d` (9 Sep) with 34 locally
  changed paths as of this writing. **Its git log is not evidence of what runs.** Compare file
  hashes against the payload that was actually shipped, never `git log` on the host checkout;
- **detached processes holding `flock`s** — a killed script's `sleep` child inherits the open file
  descriptor and keeps a lock held long after the parent is gone (§5.1, hit three times on
  2026-09-18). Wait for the **lock** to clear, verify with `pgrep`, never assume killing the parent
  released it;
- **files written by containers, as root** — the operator's own shell cannot `ls`, `du` or delete
  them; doing any of that needs another container mounting the same path;
- **`~/.prod-monitor-seen`** — makes a "new group" notice fire once per group, ever. A group that
  reappears after being purged from this file re-notifies; one that was already seen does not, even
  across an unrelated restart of the monitor.

What this table deliberately does not do: add a new checker script that walks it and reports
PASS/FAIL per stage. Three checkers built during this project passed vacuously before being caught
by an independent read of the data they were meant to check. A stage-contract table that points at
commands already run and already trusted is safer than a fresh script on the critical path.

## 4. The stages, in order, with a finish line for each

| # | Stage | You are done when | Procedure |
|---|---|---|---|
| 0 | Read the prohibitions | You can state the host rule in §2 from memory | `production-host/README.md` |
| 1 | Laptop environment | The interpreter in §0c runs `scripts/production_gates.py` | §0c |
| 2 | Sources reconstructed | `setup/verify_sources.py` passes | `docs/RUN-THIS-PROJECT.md` §1 |
| 3 | Datasets present **on the machine that runs the cell** | `setup/verify_datasets.py` passes there — see §4b | `docs/RUN-THIS-PROJECT.md` §3, procedure §2b |
| 4 | Payload built | `contract.py verify-payload` accepts the tgz you will ship | `docs/RUN-THIS-PROJECT.md` §4, procedure §2 |
| 5 | Host preconditions | The ten checks pass on the host | §1 |
| 6 | Dry run | The wrapper completes a short cell end to end | §2c |
| 7 | Launch | The launch banner prints its watch budget, disk floor and eval workload | §3, §9.2 |
| 8 | Watch | A monitor is reporting to **you**, not to a file on the host | §9.5 |
| 9 | Collect | Rows are in `results/records/` and `campaign_status.py` moved | §9.6 |

Stages 0–4 are laptop-only and can be done before you have the host. Do them first.

## 4b. Cold start — use `docs/RUN-THIS-PROJECT.md`, not this page

**The canonical cold start already exists**:
[`../docs/RUN-THIS-PROJECT.md`](../docs/RUN-THIS-PROJECT.md), which the repository README calls
"start here from a fresh clone". It runs clone → reconstruct pinned sources → build the environment
→ provision Places365 → build and check a payload → submit, and each step states what proves it
worked. It also carries a portable route (§5a) for any Linux host with Docker and a GPU, not just
this one.

Do not work from a second copy of those steps. [Claude 2026-09-17] An earlier revision of this
section restated them, which is the duplication this project keeps paying for; it was written
without checking whether the document existed. It does, and it is better.

What this page adds on top of it, and the order to take them in:

- Stages 1–4 of §4 map onto its §§0–4. **Do them before you have the host.**
- Then come back here for §5 (which launcher), §6 (the containers), §7 (watching) and §8
  (collection), which are specific to the shared V100 box rather than to any Docker host.
- Two facts that belong to the host and so live here rather than there:
  - `RUNNER_CONTRACT` is **19** today (`contract.py:154`). It is written in two places — that
    constant and `--require-runner-contract` in the procedure — and them drifting apart has killed a
    job before. Read it from the source.
  - `setup/verify_datasets.py` checks **wherever you run it**. Passing on your laptop says nothing
    about the host, and the cell reads Places365 from an archive passed to the launcher
    *positionally*. Stage 3's finish line is "present on the machine that will run the cell".

## 4c. Per-family divergences — the table that decides what bites you

Every column below is read from `datasphere/native/families.json`, `rlgen/protocol.py`
(`OBSERVATION_GEOMETRY`) and `datasphere/native/measured-vram-bounds.json`, not from prose.

| family | baselines | terminal checkpoint | intermediates | render | estimand | observed peak |
|---|---|---|---|---|---|---|
| `rlvigen` | drqv2, svea, drq, sgqn, curl | `snapshot.pt` | `snapshot_*.pt` | 84×84, fs 3 | mode | 4,549 MiB |
| `dmc_gb` | rad, soda | `model/{frames}.pt` | `model/*.pt` | 100→84, fs 3 | mode | 2,529 MiB |
| `alda` | alda | `checkpoints/sac_*_step_{…}` | `checkpoints/sac_*_step_*` | 64×64, fs 3 | mode | 2,397 MiB |
| `idaac` | idaac | `models/agent-robosuite:{task}…` | same, frame-stamped | 64×64, fs 3 | **sample** | 2,638 MiB |
| `ppg` | ppg | `model_terminal.jd` | `model[0-9]*.jd` | 64×64, fs 3 | **sample** | 7,146 MiB |
| `ibac_sni` | ibac_sni | `model.pt` | `model_[0-9]*.pt` | 64×64, fs 3 | **sample** | 7,421 MiB |
| `ctrl` | ctrl | `models/robosuite:{task}/check…` | same | 64×64, fs 3 | mode | **32,435 MiB** |

What the columns mean for you:

- **estimand** — `idaac`, `ppg` and `ibac_sni` report a **sampled** return; the other nine report the
  **mode**. These are different quantities. `comparison_blocks.py` blocks on it, and the three
  sampled families are exactly the set that can be compared to each other without the extra pass.
- **observed peak** — read `per_family_observed_peak_mib` from the JSON. **Do not aggregate the
  `cells` array yourself**: it contains rows from shared cards and partial ramps, and taking a `max`
  over it reports `ibac_sni` at 22,675 MiB — a retracted number that is 94% a colleague's memory. I
  made exactly that mistake while writing this table.
- `ibac_sni`'s 7,421 MiB is a **card delta**: 2,199 MiB of compute apps plus 5,222 MiB of EGL render
  contexts. Per-process sums miss EGL entirely, so a tool that adds up compute processes will
  under-report this family by a factor of three.
- `ctrl` at 32,435 MiB does not fit beside the 4,000 MiB floor on a 32,494 MiB card. It needs an
  empty card and an explicit decision about the floor; it has never run at 600k here.
- **checkpoint names differ per family**, which matters at collection: the frame-provenance audit
  ties a row to a file by name or by hash, and `ppg` names by save index rather than frame. See §8.

### 4c.1 Resources other than VRAM — and which numbers were measured

The host is 16 cores, 113 GiB RAM, two V100-32GB (`families.json` `_host_profiles.v100`). Free disk
on the shared filesystem was about 175 GiB on 2026-09-17 and moves with other users' work.

| baseline | disk need at 600k | host RAM | CPU | 600k training time on this host |
|---|---|---|---|---|
| `drqv2`, `drq`, `curl` | 48 GiB, computed | **≈40 GiB per cell**: 36.7 GiB of replay at the v100 cap of 620k (computed) plus a 3.3 GiB fixed peak (measured on DataSphere, for `svea`); never measured here | trainer plus 4 replay-loader workers | **never run** |
| `svea`, `sgqn` | 95 GiB, computed (47.5 of it Places365) | as above | as above | **never run** |
| `rad` | 29 GiB, computed | **≈22 GiB**: 19.3 GiB of replay **preallocated at start** (30,000 B per budgeted frame, computed) plus a 2.6 GiB fixed peak (measured on DataSphere) | — | **never run** |
| `soda` | 77 GiB, computed (includes Places365) | **≈23 GiB**: 20.4 GiB preallocated replay (computed) plus the fixed peak, which is not measured for `soda` | — | **never run** |
| `alda` | 12 GiB, computed | **15.3 GiB** fixed working set, independent of budget (`families.json`; not measured here) | — | **never run** |
| `idaac` | 9 GiB, computed | max RSS 2.8 GiB, **measured** | 1 process, 100% of one core, **measured** | **4 h 50 min** (s101), **7 h 15 min** (s102, sharing the host with another cell's grid), **measured** |
| `ppg` | 9 GiB, computed | max RSS 4.7 GiB, **measured** | 1 env, ~100% of one core, **measured** | **3 h 34 min** (s1), **measured** |
| `ibac_sni` | 10 GiB, computed | max RSS of the largest process 2.6 GiB, **measured**; the 16 workers together were not | **16 processes, 626% CPU, measured** — a whole-host job | **31 min 32 s** (s101), **measured** |
| `ctrl` | 10 GiB, computed | **54.3 GiB at 64 envs — a linear extrapolation** of a 13.6 GiB 16-env peak, not a measurement | 64 envs | **never run at 600k** |

Where each number comes from, so you can re-derive it:

- **Disk need**: `python datasphere/native/family.py disk-requirement --cells <baseline>:1 --frames
  600000 --profile v100 --ceil-total`, run on the laptop. The launcher runs the same computation and
  sets this cell's disk floor to *free at launch − 2 × need*, clamped at 50 GiB. For `svea`, `sgqn`
  and `soda` at today's free space, that clamp binds, so the disk watch guards only the last 50 GiB.
  For the RL-ViGen five the figure includes a 35.5 GiB replay line; `families.json`'s own replay note
  says loader workers delete episode files once read, so disk stays roughly flat. That line is
  probably conservative, and it has never been checked on this host.
- **Training time, CPU and RSS**: GNU `time -v` output at the end of each cell's `training.log`
  (`Elapsed (wall clock)`, `Percent of CPU`, `Maximum resident set size`).
- **Evaluation time is not in this table** because it barely depends on the family: the in-cell grid
  took about 13.5–14 hours in both complete cells of 16–17 Sep. Budget for it (§6b, reaper row).
- **Launch to training** is a further 7–22 minutes of bootstrap (§6d).
- **Where our own disk goes**, measured 2026-09-18 from a container (much of it is root-owned, so
  the host shell under-reports): 94 GB total — 66 GB of run directories, of which **24 GiB is in 60
  directories holding neither records nor checkpoints**. Reclaimable, and the "permission wall" that
  said otherwise is not one: a container whose only mount is that directory bounds the delete.
  [`production-host/27`](production-host/27-disk-not-vram-is-what-caps-parallelism.md) addendum.
- **Host RAM is not checked by the launcher.** Nothing in `launch-card-cell.sh` compares a cell's
  RAM figure with what the host has free, and the host's other users take an unknown share of its
  113 GiB. For the five RL-ViGen baselines, `rad`, `soda` and `ctrl`, RAM rather than VRAM is the
  largest number in the row. Only the three families that have run have a RAM figure measured here.
  The RAM figures above come from `families.json` (`memory_note`, `tier_reason`, `replay_semantics`,
  `host_memory_model`).

## 5. What to launch with, and why there are three layers

    wait-and-train-v4.sh   waits for a sustained vacancy, then calls ↓   (optional; see below)
    train-production-cell-v5.sh / -v6.sh   sets the production environment, calls ↓
    launch-card-cell.sh    sizes the watches, starts the watcher containers, calls ↓
    run_on_production_host.sh   guards, mounts, forwards an ALLOWLIST of env vars, `docker run`

[Corrected 2026-09-19, each line read in the scripts.] **`wait-and-train-v4.sh` defaults to the v5
wrapper** (`WRAPPER="${WRAPPER:-train-production-cell-v5.sh}"`, its line 51). v5 has no `PAYLOAD` or
`PLACES365_DIR`, so a waiter armed for `svea`, `sgqn` or `soda` without
`WRAPPER=train-production-cell-v6.sh` launches the wrong wrapper with the default payload and no
corpus. Everything above runs from the host's checkout (`~/rlvigen-work/`); `run_probe.sh` and
everything after it runs from the **payload**, inside the container. A fix therefore ships by a
different route depending on which side of `docker run` it is on — compare hashes, not `git log`.

**The launch rule is a ten-minute sustained vacancy**: no foreign holder on the card, and enough
free memory, for ten consecutive one-minute samples. That number is measured, not chosen: over
30 hours of the occupancy log the co-tenant's absences were 2, 1, 1, 36, 1, 1, 171, 1, 5, 1, 1 and
4 minutes. Ten of twelve were **restarts between its jobs**, not vacancies. On 2026-09-17 a cell
launched two minutes into one of those gaps was stopped eleven minutes in. A second launch that
waited out a 15-minute absence was still stopped 32 minutes in, when the co-tenant came back. The
rule lowers the risk; it does not remove it. Procedure §9.5b has the arithmetic; note 34 has the
campaign consequence.

**Two ways to apply that rule, and one script that does not.** [Corrected 2026-09-17: this section
called `wait-and-train-v3.sh` the default and said it enforced the vacancy.]

- `wait-and-train-v3.sh` counts polls with **free memory ≥ `NEED`** (default 15,000 MiB) and nothing
  else. It does not look at who holds the card. Beside a co-tenant holding 12 GiB, a card still has
  about 20 GiB free, so it would launch — the case §5.1 exists to prevent. It launched one cell,
  `ibac_sni` s101 at 20:35 on 16 Sep, into what happened to be a real vacancy.
- **`wait-and-train-v4.sh`** applies the validated rule: no foreign holder **and** ≥ `NEED` MiB free
  for ten consecutive samples of the occupancy log, re-checked against `nvidia-smi` at the instant of
  launch. Use it when nobody will be watching. It was written after a real window opened at 21:39 on
  2026-09-17, was reported correctly, and passed unused because no one was at the keyboard.
- **By hand**, with §5.2, when you are there: `capacity-check.sh`, then the launch block.

Whichever launches the cell, **the attempt still has to be recorded from the laptop** — no waiter
does it, and `audit_attempt_ledger.py --strict` fails later on a run that never got a status. The
same goes for `watch-cell.sh`: a waiter watches the card, not the cell it started.

**A trap that silences a waiter for a day.** `wait-and-train-v3.sh` takes
`~/rlvigen-runs/.wait-and-train.lock` and holds it for the life of the cell it starts. The reaper
subshell inside `launch-card-cell.sh` — a plain `sleep $WATCH_SECONDS` — **inherits that open file
descriptor**, so the lock outlives the cell by the whole remaining watch budget. Measured on
2026-09-18: `ibac_sni` s101 finished at 11:16 on 17 Sep, and at 01:07 the next morning the lock was
still held by `sleep 115668` started at 20:35 on 16 Sep. A second waiter sharing that file refuses
every window until the sleep ends. `wait-and-train-v4.sh` therefore uses its own lock file and
checks what is actually *running* (`train-production-cell-v5.sh`, `wait-and-train-v3.sh`, any
`cell-c*` container) rather than trusting a descriptor.

**This is a property of every self-locking script here, not a bug in one of them.** It bit three
different ones on 2026-09-18: `wait-and-train-v3.sh` (lock held 14 hours past its cell by the
reaper's `sleep`), `wait-and-train-v4.sh` on restart (its own `sleep` child), and
`gpu-occupancy-log.sh` — where it did real damage. Killing the logger and starting a replacement two
seconds later left the host with **no logger at all**: the new one printed *"another logger holds
…; not starting a second"* and exited, because the dead parent's `sleep` still held the lock. A
waiter with a stale log refuses to launch, correctly, so that would have produced a silent night.

**The rule when restarting any of them: wait for the LOCK to clear, not for the process to die.**
Retry the start until it actually appears in `pgrep`, and check afterwards rather than assuming —
`renew-monitoring.sh` in the session scratchpad does both, and prints a loud line if no logger is
running at the end.

### 5.1 Why the vacancy rule applies to every family, not only the big ones

The ten-minute rule was first derived for `ibac_sni`, which needs 7,421 MiB plus the 4,000 MiB floor.
It is tempting to conclude that a small cell — `idaac` trains in about 2,640 MiB — can simply sit
beside the co-tenant. On 2026-09-17 I nearly launched on exactly that reasoning, and checked the
co-tenant's history first. The check refuted it.

Over the whole occupancy log, `rlvigen_kalugin_df`'s peak on card 1 with no cell of ours present was
**32,346 MiB of 32,768** — the entire card, held by **one process**, **flat** for about 1 h 45 m on
2026-09-16 while its utilisation swung between 28% and 85%. A memory figure that never moves while
the work varies is the signature of a framework **preallocating whatever is free**, not of a job
whose working set is 32 GiB. It happened in four separate episodes over three days. On the single
day I looked at first, its peak was about 22.8 GiB, which is why one day's view was misleading.

What that means, and what it does not:

- Beside that peak, **nothing of ours fits** — 422 MiB remain.
- Whether its allocator **adapts** to the memory available when a job starts (then our presence only
  shrinks what it takes) or needs a **fixed** amount (then our presence could make its job fail at
  startup) **cannot be determined from outside**, and inspecting another group's process or
  container is not permitted here. Twenty hours of co-residence on 2026-09-17 produced no visible
  failure, and the co-tenant started new jobs beside our cells — but that is consistent with both.
- Our memory floor protects the co-tenant against **gradual** growth: the yield watch polls every
  20 s. It cannot help against an **atomic** allocation that fails before the next poll.

So the rule is: **launch any cell only after the co-tenant has been absent from the card for ten
consecutive minutes**, and when a window opens, launch the **smallest** useful cell first. This is a
risk the design reduces, not one it removes; the residual case is a fixed-size allocation by the
co-tenant arriving while we hold memory. Record every launch so that, if a co-tenant ever reports a
failure, the timeline can be checked against ours.

The check that caught this, for reuse:

```bash
grep "card=1 " ~/rlvigen-runs/gpu-occupancy.log | grep -v "cell-c1" \
  | awk '{m=$0; sub(/.*mem=/,"",m); sub(/ .*/,"",m); print m, substr($1,1,16)}' | sort -rn | head -5
```

If you do use `wait-and-train-v3.sh` anyway — for instance to catch a window while you are asleep,
knowing what it does not check — note that it takes a `flock` for the life of the cell it starts and
refuses when `train-production-cell-v5.sh` is already running. That is duplicate prevention, not a
capacity limit, and it is worth having: a stale waiter once double-launched a production cell.

### 5.2 One cell from vacancy to collected rows, as it was actually run

Everything in this subsection was executed on 2026-09-16/17 for `idaac` s102 and `ibac_sni` s102;
the commands are copied from those sessions with only the seed and names left as placeholders. It
is the golden path at the level of what you type. The procedure has the reasoning behind each piece.

**Laptop, before anything: is a card genuinely vacant?**

    bash datasphere/native/host-scripts/capacity-check.sh
    # card 1 as of 2026-09-17T11:00: AVAILABLE  (10/10 clear samples; ...)
    # To be told instead of polling, run watch-capacity.sh trip in the background.

`AVAILABLE` means ten consecutive minutes with no foreign holder and at least 11,421 MiB free.
Anything else: wait. The launch that ignored it, at 07:50 on 2026-09-17, was stopped eleven minutes
in. Passing it is not a guarantee either: the 11:00 launch waited out a 15-minute absence, passed,
and was stopped 32 minutes in when the co-tenant returned.

**Host, one ssh session: re-check at the moment of launch, preserve the old log, launch detached.**
This is the 11:00 launch of `ibac_sni` s102, verbatim apart from the placeholders:

    ssh <host> 'bash -s' <<'EOF'
    set -u
    A="$HOME/rlvigen-runs/prod-v214"
    if [ -f "$A/<baseline>-s<seed>-prod-result.tgz" ]; then echo "RESULT EXISTS -- abort"; exit 1; fi
    # re-verify the vacancy now, not from a sample taken a minute ago
    recent=$(grep "card=1 " ~/rlvigen-runs/gpu-occupancy.log | tail -10 | grep -c rlvigen_kalugin_df)
    f1=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits -i 1)
    if [ "$recent" -ne 0 ] || [ "$f1" -lt 15000 ]; then echo "VACANCY NOT SUSTAINED -- aborting"; exit 2; fi
    # Host RAM. Nothing else in the launch chain looks at it (§4c.1), and a hand launch does not
    # go through the waiter, which is where the only RAM floor lives.
    ram=$(free -g | awk 'NR==2{print $7}')
    if [ "$ram" -lt 55 ]; then echo "ONLY ${ram} GiB RAM AVAILABLE -- aborting"; exit 2; fi
    echo "disk: $(df -Pk ~ | awk 'NR==2{printf "%d", $4/1048576}') GiB | load: $(cut -d' ' -f1 /proc/loadavg)"
    # v5 truncates <tag>.log; keep a failed earlier attempt's log under an exact new name
    if [ -f "$A/<baseline>-s<seed>-prod.log" ]; then
      cp -p "$A/<baseline>-s<seed>-prod.log" "$A/<baseline>-s<seed>-prod-attempt<N>-<why>-<date>.log"
    fi
    nohup setsid env CARD=1 YIELD_PROCS=1 FAMILY=<family> BASELINE=<baseline> SEED=<seed> \
      EXPECT_OURS=20 VRAM_MIB=4096 \
      bash "$HOME/rlvigen-work/train-production-cell-v5.sh" \
      > "$A/<baseline>-s<seed>-launch.log" 2>&1 &
    sleep 25; tail -1 "$A/<baseline>-s<seed>-launch.log"
    EOF

Three things about that block that are easy to get wrong:

- **`train-production-cell-v5.sh` exits with `SKIP` if a result archive for the tag already
  exists**, and it **truncates** `<tag>.log` on every launch. The block checks the first and
  preserves the second.
- **`YIELD_PROCS=1` is required on card 1.** `launch-card-cell.sh:269-270` refuses a non-zero card
  without it. `EXPECT_OURS=20` is what keeps process-count yield from firing on our own 16 workers.
- **`VRAM_MIB` does not protect anyone** (§6b). v5 passes it on as `NATIVE_VRAM_CAP_MIB` (default
  4096), which exists because the wrapper refuses a GPU container without one.
- **The re-check greps for one co-tenant by name**, `rlvigen_kalugin_df`, the only one seen on
  card 1. On another card or another day, check `capacity-check.sh`'s `last holders` and grep for
  whoever is there.
- **The RAM line is in this template because a hand launch has no other RAM guard.** `MIN_RAM_GIB`
  lives in `wait-and-train-v4.sh`, and typing the launch yourself goes around it. An RL-ViGen cell
  is ~40 GiB resident on a 125 GiB host that already had 43 GiB in use on 2026-09-18; starting one
  at the wrong moment can make the kernel OOM killer pick a co-tenant's process, which is the one
  outcome the standing rule forbids outright. 55 GiB is the floor armed for `svea`; a smaller
  family needs less, but *check something* rather than nothing — and note the number checked is
  `free -g` column 7 (`available`), not `free`.

**[Claude 2026-09-20] `TIMEOUT_S` is not automatic for most baselines.** The template above omits
it because `ibac_sni` is one of the three baselines (with `idaac`, `ppg`) that have a MEASURED
sub-12h V100 training time — for those three, and only those three, the wrappers' 12h default
(`CELL_TIMEOUT_SECONDS=43200`) is left alone. `train-production-cell-v5.sh`/`-v6.sh` now REFUSE to
launch (exit 2, before anything reaches the card) if `TIMEOUT_S` is unset for any other baseline,
known or not — the 12h default cut `svea` near 430k/600k frames on 2026-09-19 with no warning. Pass
`TIMEOUT_S` explicitly for the rest; V100 throughput is unmeasured for every row below, so the
suggested value is 1.5× the DataSphere T4-tier scheduled training time
(`production-schedule.json`), rounded up to the hour, not a promise a V100 will actually need it:

  | baseline | scheduled hours (T4) | suggested `TIMEOUT_S` |
  |---|---|---|
  | `drqv2` | 6.40 | 36000 (10 h) |
  | `ctrl` | 11.17 | 61200 (17 h) |
  | `curl` | 12.71 | 72000 (20 h) |
  | `drq` | 13.35 | 75600 (21 h) |
  | `svea` | 16.68 | 93600 (26 h) |
  | `alda` | 19.05 | 104400 (29 h) |
  | `sgqn` | 25.64 | 140400 (39 h) |
  | `rad` | 27.14 | 147600 (41 h) |
  | `soda` | 51.28 | 277200 (77 h) |

  `svea`, `sgqn` and `soda` are additionally blocked by G10 (`notes/ACCOUNTABILITY.md`) — their own
  scheduled hours above are from a since-banned loader configuration, not just an unmeasured V100 —
  see §5.3 before launching any of the three.

**Host, within the first minutes: read the banner, then arm the self-cap.** The launcher log
`prod-v214/<tag>.log` prints, near the top, `container: cell-c1-<pid>`, the watch budget and
`disk: <free> GiB free, floor <N> GiB`. Write down the container name and the floor. Then:

    ssh <host> 'nohup setsid bash ~/rlvigen-work/self-vram-cap.sh cell-c1-<pid> 1 <cap_mib> \
      ~/rlvigen-runs/self-vram-cap-<baseline>-s<seed>.log >/dev/null 2>&1 &'

The caps used were 5,000 MiB for `idaac` and 8,000 MiB for `ibac_sni`. The script sums compute
processes only, so for `ibac_sni` 8,000 is far above the 2,199 MiB it can see (§6b).

**Laptop: record the attempt, then watch it.** `record_host_run.py` reads the cell's own
`effective_config.json`, so fetch just that file first:

    rsync -a --prune-empty-dirs --include='*/' --include='effective_config.json' --exclude='*' \
      <host>:'~/rlvigen-runs/<run-id>' ./runs/
    python scripts/record_host_run.py ./runs/<run-id> --status running --note "<why now, what card>"
    python scripts/production_run_register.py
    python scripts/audit_attempt_ledger.py --strict          # exit 0

    RUN=<run-id> LOG=<tag>.log CELL=<baseline>-s<seed> FLOOR=<N> \
      bash datasphere/native/host-scripts/watch-cell.sh trip  # in the background, no timeout

**When the watcher reports COMPLETED** — about 14 hours later for a fast-training family:

    rsync -a --exclude 'native-work' <host>:'~/rlvigen-runs/<run-id>' ./fetched/
    BP=<interpreter from procedure §0c> bash datasphere/native/collect-host-run.sh <family> ./fetched/<run-id>
    python scripts/audit_record_frame_provenance.py results/records/<run-id>__records.jsonl \
      --checkpoints ./fetched/<run-id>/native-out/cells/<baseline>-s<seed>/checkpoints   # MISMATCHED 0
    python scripts/record_host_run.py <run-id> --update-status --status "complete: <rows>"
    python scripts/production_run_register.py
    python scripts/audit_attempt_ledger.py --strict
    python scripts/campaign_status.py

`collect-host-run.sh` prints a NOTE, not an error, when the evaluator ledger declines a production
run; that is correct (§8 item 3). Do **not** run `populate_evaluator_ledger.py` afterwards.

**When the watcher reports YIELDED or FAILED** — the other branch, also executed:

    ssh <host> 'cat ~/rlvigen-runs/<run-id>/native-work/yield.sentinel'     # why
    rsync -a --exclude 'native-work' <host>:'~/rlvigen-runs/<run-id>' ./fetched/
    # the stamps are ONLY in native-work after a mid-training stop; fetch them by name (§6c)
    rsync -a <host>:'~/rlvigen-runs/<run-id>/native-work/runs/<baseline>-s<seed>/<artifact path>/<stamp glob>' ./fetched/<run-id>/native-work/...
    python scripts/record_host_run.py ./fetched/<run-id> --status failed --note "<sentinel text, frame reached, stamps kept>"
    python scripts/production_run_register.py
    python scripts/audit_attempt_ledger.py --strict

Then decide between evaluating the stamps offline as a partial curve (§11.2, `curve-sweep-v3.sh`)
and a rerun from zero, which is a new attempt with a new run directory. Collect a partial curve under
a distinct tag, such as `reeval-v214-<baseline>-s<seed>-attempt<N>-partial-curve`. A later sweep
of the same seed would otherwise collide with it and silently pool two trajectories.

### 5.3 Launching a Places365 baseline (`svea`, `sgqn`, `soda`) — what differs

> **STOP before launching `svea`, `sgqn` or `soda` — two open defects, found 2026-09-20.**
> (1) Their scheduled training times (16.7 h, 25.6 h, 51.3 h) were measured with 8 overlay-loader
> workers, a configuration since banned for heap corruption; at the current default of 0 workers
> the only sample is `svea` at ~2.4 frames/s on this host — about 69 h per seed. (2) The wrappers
> default `TIMEOUT_S` to 43,200 s (12 h), so a cell launched without an explicit `TIMEOUT_S` is
> reaped long before 600k frames; the same applies to `rad`, `alda`, `curl` and `drq`, whose scheduled
> training also exceeds 12 h (seven baselines in all). Since 2026-09-20 the wrappers REFUSE such a
> launch when `TIMEOUT_S` is unset (§5.2 has the table) — on the laptop copies; the host's copies are
> swapped in only when no cell is running. Detail: `CURRENT-STATE-AND-RESPONSIBILITY.md` §2, `ACCOUNTABILITY.md` G10.


Nothing here has run a cell yet; the wrapper path is dry-run proven (§11.2) and the corpus arrives
2026-09-18. Three things differ from §5.2, and each is a number rather than a preference.

**Use `train-production-cell-v6.sh`, with the corpus mounted rather than copied:**

    PLACES365_DIR=$HOME/rlvigen-assets/places365-train PAYLOAD=$HOME/rlvigen-work/payload-v215-rlvigen.tgz \
      CARD=1 YIELD_PROCS=1 FAMILY=rlvigen BASELINE=svea SEED=101 EXPECT_OURS=20 VRAM_MIB=5000 \
      NATIVE_DISK_ALLOWANCE_GIB=95 bash ~/rlvigen-work/train-production-cell-v6.sh

**Why `NATIVE_DISK_ALLOWANCE_GIB` is set by hand here, and only here.** `family.py
disk-requirement` prices `svea` at **94.95 GiB**, of which **47.5 GiB is Places365** — the archive
copied in and expanded per cell. With `PLACES365_DIR` the corpus is a read-only mount and that
47.5 GiB is never spent, so the derived allowance (2 × 95 = 190 GiB) exceeds the whole free disk
and the floor silently clamps to its 50 GiB absolute minimum. Passing 95 — twice the real ~47.5 —
restores a floor that means something: free-at-launch minus 95.

**RAM, not VRAM, is this family's binding number, and nothing checks it.** An RL-ViGen cell is
about **40 GiB resident** (36.7 GiB of replay at the v100 cap of 620k, plus a 3.3 GiB fixed peak).
Measured on the host 2026-09-18: **125 GiB total, 79 GiB available**, load 6.85 of 16 cores with
the co-tenant present. One cell fits with room; **two do not**, and the launcher would not stop
you. Check `free -g` before launching and do not pack two of these.

**What is still untested**, stated so it is not discovered at hour nine: no cell has yet consumed
the corpus through `/opt/places365`. The dry run proves the mount and the environment, not the
loader. Watch the first minutes of `training.log` for the Places365 loader lines before trusting
the run, and expect the bootstrap to be longer than 7–22 minutes for a family whose payload is
55 MB rather than 5 MB.

## 6. The containers, per cell

One launch creates **four** containers plus one optional host process. Names carry the card and the
launcher's PID, e.g. `cell-c1-1437491`.

| Container | Role | Stops the cell? |
|---|---|---|
| `cell-c<card>-<pid>` | the cell: training, then the in-cell evaluation grid | — |
| `cell-c<card>-yield-<pid>` | GPU memory floor, re-checked every 20 s **until it fires once** — then it writes the sentinel and exits (see below) | **yes**, via the sentinel |
| `cell-c<card>-disk-<pid>` | disk headroom against **this cell's own floor**, every 60 s | **yes**, via the sentinel |
| `cell-c<card>-exclusivity-<pid>` | counts foreign processes on the card | no — it only reports |
| `self-vram-cap.sh` (host, optional) | stops **our** container if **our** usage crosses a cap | yes, by name |

**The memory-floor watch is one-shot.** [Claude 2026-09-17, corrected — this table said "for the
cell's whole life", which is wrong.] After writing the sentinel, `yield_gpu_to_neighbour.py:270` does
`return 0`, and `--rm` removes its container. Combine that with the rule below — a cell past training
ignores the sentinel — and a cell in its evaluation grid that has *already seen its watcher fire once*
carries on with **no memory-floor watch at all** for the rest of its life. Observed: `idaac` s102's
watcher fired at 08:01:35 during a card crunch, `idaac` was past training and kept going, and from then
on `docker ps` showed only its `cell`, `disk` and `exclusivity` containers. Its footprint by then was
~820 MiB, so the practical risk to a co-tenant was small, but the cell was unwatched on that axis for
the rest of the day. If a missing `-yield-` container surprises you, this is why; check the run's
`native-work/yield.sentinel` for when it fired.

Two images are involved: a **helper** (`python:3.11-slim`) for small tasks, and the **cell** image
pinned by digest in `datasphere/native/source-lock.json`
(`nvidia/cuda:12.2.2-runtime-ubuntu22.04@sha256:94c1577b…`). The cell installs its own apt and pip
dependencies inside that image; you never prepare it.

**Who obeys a stop signal is not uniform, and this decides what dies first.** The sentinel poller
lives only as long as the *training* process (`run_probe.sh:197`). A cell that has finished training
and moved into its evaluation grid **ignores the sentinel**. So when the card fills, the
still-training cell is stopped and the evaluating ones continue. That ordering follows from process
lifetime, not from policy.

The **stall watchdog shares that lifetime**: `run_probe.sh:135` runs the same
`while kill -0 "$training_pid"` loop. So during the evaluation grid — which is the *longer* half of
a cell: about 13.5–14 hours in both complete cells of 16–17 Sep, against 31 minutes of training for
`ibac_sni` and 7.3 hours for `idaac` (`time -v` in each `training.log`) — neither the sentinel
poller nor the stall watchdog is active. A grid that hangs will not be killed by the cell itself.
That is what the reaper in `launch-card-cell.sh` and your own monitor are for; it is also why the
watch budget must cover training **plus** evaluation, and why §3b treats the wall-clock ceiling as
required rather than advisory.

Evidence:
[`results/evidence/only-a-training-cell-obeys-the-sentinel`](../results/evidence/only-a-training-cell-obeys-the-sentinel/CLAIM.md).

## 6b. Every way a cell ends early, and what each leaves behind

No trainer in this campaign stops on performance: a search of all seven families' training code for
early stopping, patience or KL-based stops finds none. A cell runs to its frame budget, then its grid,
unless one of the mechanisms below ends it. Read from `launch-card-cell.sh`, `run_probe.sh` and
`self-vram-cap.sh` on 2026-09-17. [`model/STOP-MECHANISMS.md`](model/STOP-MECHANISMS.md) has the
history behind each; its "state now" column dates from 2026-09-16.

| Mechanism | Fires when | Active during | Launcher-log marker | What survives |
|---|---|---|---|---|
| **Training wall clock** — `timeout --foreground ${CELL_TIMEOUT_SECONDS}s` (`run_probe.sh:400-402`); v5 sets 43,200 s | training runs past it | training only | expected `NATIVE_CELL_FAILED` (exit 124); **never observed here** | stamps so far, in `native-work/` |
| **Stall watchdog** (`run_probe.sh:127-159`) | `training.log` unchanged for `CELL_STALL_SECONDS` (default 1,800 s) | training PID lifetime only | `NATIVE_CELL_STALLED`, then `NATIVE_CELL_FAILED_STALLED` | stamps so far |
| **Memory floor** — the `-yield-` container, `yield_gpu_to_neighbour.py --floor-mib ${NATIVE_FLOOR_MIB:-4000} --interval 20`, one-shot | card free memory below the floor | obeyed only while the training PID lives (`run_probe.sh:197`) | `NATIVE_CELL_YIELDED`, **then** `NATIVE_CELL_FAILED`; the reason is only in `native-work/yield.sentinel` | stamps so far — **observed five times on 2026-09-16 and twice on 2026-09-17** |
| **Disk floor** — the `-disk-` container, `watch_disk_headroom.py --interval 60` | free space under `/work` below this cell's floor: free at launch minus 2 × the family's disk need, never below 50 GiB (`launch-card-cell.sh:425-453`) | same sentinel, same training-only obedience | as the memory floor; the sentinel says `free_gib=` | stamps so far; **never fired here** |
| **Reaper** (`launch-card-cell.sh:370-399`) | once the watch budget (training + eval allowance + bootstrap + slack, printed in the banner) is spent: stops the container if it emitted nothing for 900 s (`NATIVE_REAP_STALL_SECONDS`), otherwise grants 900 s at a time up to 10,800 s (`NATIVE_REAP_MAX_GRACE_SECONDS`) | the whole container, grid included | `!! REAPING <cell>` on the launcher's stderr; no `result.tgz` | every row already written; collect as in §8 item 2 |
| **`self-vram-cap.sh`** (host, optional) | the summed **compute-app** memory of our container's PIDs exceeds the cap, sampled every 20 s | the whole container | its own log: `NATIVE_SELF_VRAM_CAP_TRIPPED`; `docker stop -t 30` | as a reap |
| **Post-training checks** (`run_probe.sh:508-535`) | the executed endpoint is not the family's expected one; `retain` fails; the terminal checkpoint is non-finite; a strict curve is incomplete; the endpoint grid fails | after training | `NATIVE_CELL_FAILED` | checkpoints, if `retain` ran before the failing step |
| **Terminal checkpoint write fails** (e.g. `idaac/train.py:351`, RL-ViGen `train.py:373`) | the safe write of the terminal file still fails after its wait | end of training | the trainer's `RuntimeError`, then `NATIVE_CELL_FAILED` | earlier stamps |
| **Killed by a signal** — OOM killer, `kill` | the training process receives a fatal signal | training | `NATIVE_CELL_SIGNALLED` (ignore the `Exit status: 0` that `time -v` prints after it) | stamps so far |
| **You** — `docker stop <exact cell name>` | — | the whole container | nothing | as a reap |

Three things this table implies for an operator:

- **A yield prints two markers, and the second hides the first.** `NATIVE_CELL_YIELDED` is followed
  by `NATIVE_CELL_FAILED` a few lines later (for example lines 2612 and 2616 of the 16 Sep job log in
  [`ibac-sni-16sep-three-stops`](../results/evidence/ibac-sni-16sep-three-stops/CLAIM.md)). Reading
  only the last marker reports a yield as a plain failure. §10.1 question 1 reads all of them.
- **`NATIVE_VRAM_CAP_MIB` is not in this table on purpose.** `train-production-cell-v5.sh` sets it
  to 4096, and it prints `NATIVE_VRAM_CAP_APPLIED`, but every family launcher overwrites
  `PYTHONPATH` (`runnable/_launch/*.sh`, still true on 2026-09-17), so the cap has never reached a
  trainer ([`production-host/26`](production-host/26-the-vram-cap-never-reached-a-trainer.md)).
  It protects nobody.
- **`self-vram-cap.sh` cannot see EGL render memory.** It sums compute apps. For `ibac_sni` that is
  2,199 of 7,421 MiB, so a cap set from the family's observed peak would never trip on it; size the
  cap against the compute part.

### 6b.1 Every auto-stop, with its knob, in one place

Every mechanism in the table above can be loosened, tightened or disabled. This section exists
because that was previously true but not obvious — an operator would have had to find each knob in
its own script's comments. **Read this before launching anything**, not after a stop surprises you.

| stop | env var | default | to loosen | to disable | real cost of disabling |
|---|---|---|---|---|---|
| Training wall clock | `CELL_TIMEOUT_SECONDS` | 43,200 (v5/v6) | raise it | set larger than any plausible run | a genuinely hung process runs until the reaper or the host itself intervenes |
| Stall watchdog | `CELL_STALL_SECONDS` | 1,800 | raise it | `0` (`run_probe.sh` checks `[[ "$stall_seconds" != "0" ]]`) | a silently hung cell (no crash, no output) is invisible until the wall clock fires, hours later |
| Memory floor | `NATIVE_FLOOR_MIB` | 4,000 | lower it | cannot be disabled outright — it is the mechanism that keeps a co-tenant's job alive; lowering it below their actual need defeats its purpose without saying so | the standing rule this whole host runs under ("never CUDA OOM, including other people's jobs") is what this floor exists to satisfy |
| Disk floor | `NATIVE_DISK_ALLOWANCE_GIB`, `NATIVE_DISK_ABS_FLOOR_GIB` | `2×` the computed need; 50 GiB absolute minimum | raise the allowance (lowers the floor, i.e. lets the cell get closer to the edge before stopping) | not designed to be disabled; can be set arbitrarily low, which is the same hazard as lowering the memory floor | on a shared filesystem, filling it is *someone else's* job dying, not just yours (§5.1, `watch_disk_headroom.py`'s own docstring) |
| Reaper (post-watch-budget) | the watch budget printed in the launch banner (training + eval allowance + bootstrap + slack) | computed per cell | none exposed directly — the budget is derived, not a flat number | cannot be disabled; it exists to reclaim a card once a booking is over | none of ours; the reaper protects the *next* booking, not this cell |
| `self-vram-cap.sh` | its own VRAM cap argument, passed at arm time (§5.2) | sized by hand, per family, from the observed compute-process peak | raise the cap | don't arm it (nothing requires it) | **it does not currently protect anything real anyway** — see the two bullets above this section: it cannot see EGL memory, and `NATIVE_VRAM_CAP_MIB` never reaches a trainer. Not arming it changes nothing measurable today. |

**The one gap this table does not close**: nothing here tells you *when* it's actually safe to
loosen the disk floor for a single long run tracking close to its own predicted need (the scenario
is real — `family.py disk-requirement`'s estimate can be tight, and a false-positive stop near a
cell's own endpoint is a full rerun-from-zero given no family has a working resume path, §6c). The
mechanical answer is the row above (raise `NATIVE_DISK_ALLOWANCE_GIB`); the judgement answer —
*how much headroom is actually safe to give up, for which family, on this specific host, today* —
is not something a table can respond with, because it depends on the shared disk's live state at
the moment of the decision, not on a constant this guide could print. Check `df` on the shared
filesystem yourself before loosening it, the same way you would before launching at all (§5.2).

## 6c. Checkpoints, restart and resume, per family

**Where the checkpoints are while a cell trains.** Each family writes under its `artifact_root`
from `families.json`, inside `<run>/native-work/runs/<baseline>-s<seed>/`. `family.py retain` copies
them to `native-out/cells/<cell>/checkpoints/` only **after** training passes its endpoint check
(`run_probe.sh:515-516`). So a cell stopped mid-training has them only here:

| family | under `native-work/runs/<baseline>-s<seed>/` | stamp is named by |
|---|---|---|
| `rlvigen` | `snapshot.pt`, `snapshot_<frame>.pt` | frame |
| `dmc_gb` | `robosuite_{task}/{baseline}/{seed}/model/<step>.pt` | step |
| `alda` | `alda_robosuite_door/seed_{seed}/checkpoints/sac_*_step_<n>.pt` | step |
| `idaac` | `models/agent-robosuite:{task}-{baseline}-s{seed}[_<frames>].pt` | frame |
| `ppg` | `model<NNN>.jd`, `model_terminal.jd` | **save index**, not frame |
| `ibac_sni` | `<model_name>/model.pt`, `model_<frames>.pt`, `status.json` — `<model_name>` was `cell` in every executed run | frame |
| `ctrl` | `models/robosuite:{task}/checkpoint_<frames>.msgpack` | frame |

The `ibac_sni` row is the only one fetched from a stopped cell so far (seven stamps from s102
attempt 2). The others are read from `families.json` and the trainers, not from a stopped cell.

**Can a stopped cell be continued?** Read from each trainer's code; none of it has been executed.

| family | a checkpoint holds | code that would restore it | what a restore loses | wired in a launcher |
|---|---|---|---|---|
| `rlvigen` | the pickled agent — networks **and** their Adam optimizers (`algos/drqv2.py:148-150`) — plus timer, global step and episode (`train.py:354`) | **automatic**: `train.py:409-412` loads `snapshot.pt` if the run directory has one | the **replay buffer**: loader workers delete each episode file once read (`replay_buffer.py:94,116-117`), so nothing on disk can refill it | only `RESUME_SNAPSHOT` (`run_probe.sh:361-371`), written for a diagnostic and never used to restart |
| `dmc_gb` | the pickled agent, optimizers included (`algorithms/sac.py:39-45`) | **none**: `train.py:140` starts at step 0 and never loads | would need a code change; the buffer is in memory only | no |
| `alda` | networks, all optimizers, `log_alpha`, `env_steps` (`alda_trainer.py:767-784`) | `--load_from_checkpoint` (`scripts/train.py:28,140-142`) | the replay buffer (its reload is commented out, `alda_trainer.py:818-819`); and the loop is `range(self.n_train_steps)` from zero (`:610`), so a resumed run would train a **full** budget more, not the remainder | no launcher passes the flag |
| `idaac` | `[actor_critic, ob_rms]` (`train.py:345`) — no optimizer, no update counter | **none** | would need a code change | no |
| `ppg` | the pickled model (`log_save_helper.py:146`); the optimizers are not on it — `opts` in `ppo.py:194-197`, the auxiliary one in `ppg.py:256` | **none** | would need a code change | no |
| `ibac_sni` | the pickled model (`model.pt`) and `status.json` with frames and update count (`train.py:326,354`); **no optimizer** — checked across the whole tree and in the pickle itself (37 tensors, no optimizer attribute) | **automatic**: `train.py:176,183` loads both if the model directory has them | Adam's moment estimates, rollout storage and environment state | no. Each launch makes a fresh run directory (`launch-card-cell.sh:177`), so nothing is found. Setting `NATIVE_RUN_DIR` to an old run **would** trigger the automatic load — never tried |
| `ctrl` | the serialized `train_state`, including `opt_state` (`train_ppo.py:40-60`, `algo.py:623`); `train_state_target` is not saved | **none** in `train_ppo.py`; `evaluate_ppo.py:65` restores for evaluation only | would need a code change | no |

What the campaign has actually done with a stopped cell, and what remains a judgement:

- **Practice so far:** record the stopped attempt as failed (§10.3), keep its stamps, and rerun the
  seed **from zero** as a new attempt. `ibac_sni` s102 is queued that way.
- **A stopped cell's stamps are still worth evaluating**, one by one, as a partial curve —
  `curve-sweep-v3.sh` did this for `ibac_sni` s102 (§11.2). That is a separate record, not a
  substitute for the seed.
- **Open, not decided:** whether a continued run could stand in for the seed. For the off-policy
  families it restarts with an empty buffer, which is a different experiment. For `ibac_sni` it
  resets Adam's state, a smaller difference, but a difference. It is an owner question, and if it
  is ever tried the attempt should say so in its record.
- **A hazard that follows from the table:** the two automatic loaders (`rlvigen`, `ibac_sni`) fire
  on whatever is in the run directory. Reusing a run directory via `NATIVE_RUN_DIR` without meaning
  to would silently continue an old run under a new attempt.

## 6d. Images, the Docker settings that matter, and where a cell's environment comes from

Values as the executed production launches used them (`train-production-cell-v5.sh` →
`launch-card-cell.sh` → `run_on_production_host.sh`). The procedure's §3.0b and §3.0c have the
incidents behind the last three rows.

| What | Value in the executed launches | Set at | Why you care |
|---|---|---|---|
| Cell image | `nvidia/cuda:12.2.2-runtime-ubuntu22.04@sha256:94c1577b…` | `source-lock.json` `container_image`, read at `run_on_production_host.sh:285` | printed as `image:` near the top of every launch log; check it there |
| Helper image | `python:3.11-slim` (`NATIVE_HELPER_IMAGE`) | `launch-card-cell.sh:120`, `run_on_production_host.sh:277` | runs the preflight, the disk-need computation and the three watch containers, with the repo mounted read-only. The preflight, exclusivity and yield containers get `--gpus all` so they can **query** both cards; they allocate nothing |
| Which card the cell gets | `DOCKER_GPUS='"device=<CARD>"'` | `launch-card-cell.sh:471`, from `CARD` | the wrapper refuses when it is unset (`run_on_production_host.sh:123`); its old default was every card |
| Rendering | `NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics` | `run_on_production_host.sh:219` | without `graphics`, EGL silently falls back to a CPU rasteriser — procedure §3.0c |
| Durable output | host `<run>/native-work` → `/tmp/native-work`, `<run>/native-out` → `/tmp/native-out` | `launch-card-cell.sh:473` | the only things that outlive the container; `--rm` removes the rest |
| CPU and RAM limits | none, deliberately (`run_on_production_host.sh:80`) | — | a cell may use every core; `ibac_sni` at 16 processes is a whole-host CPU job |
| The Python environment | **built inside the container on every launch**: apt, then about 1.7 GB of pip wheels with `--no-cache-dir` (the log says `NATIVE_PIP_CACHE_DISCIPLINE off`). v5 sets no `NATIVE_VENV_HOST` | `run_probe.sh` bootstrap | **7–22 minutes from launch to the cell first holding GPU memory** in the four launches of 16–17 Sep (occupancy log, 60 s resolution: 20:35→20:48, 21:32→21:54, 07:50→07:57, 11:00→11:07). A pip cache **cannot** work on this image. The one prebuilt environment on the host was built for `idaac` only (`"editable": []`) and would be refused for `rlvigen`. The bootstrap's transient disk use is what ate into an older cell's disk margin (procedure §9.5c) |

Two environments cover the fleet: eleven baselines share the torch requirement set, and `ctrl` needs
the JAX one. So `ctrl` cannot be packed into a container with any other family (`check-co-schedulable`).

**Which code the host actually runs.** Three sources meet in a launch, and they are updated
differently:

- **Everything that runs inside the cell container** comes from the payload tgz
  (`~/rlvigen-work/payload-v214-<family>.tgz`), extracted into `/tmp/native-work`: the trainers, the
  evaluator, and also `run_probe.sh`, `family.py`, `families.json` and the in-cell
  `watch_policy_health.py` (`contract.py:89`). The binding check ties those hashes to a tree (§8b).
  So the in-cell `watch_policy_health.py` is the one in the payload: by hash, the version of commit
  `229ed01` (8 Sep). That predates the 16 Sep fixes that let it read `idaac`'s and `ibac_sni`'s log
  formats, so inside those cells it cannot report on the policy. It only warns, so nothing stops;
  run the current copy from the laptop against a fetched `training.log` instead (§7).
- **The launcher and the watch containers** run from the host's own checkout,
  `~/rlvigen-work/repo`: `train-production-cell-v5.sh` does `cd "$R/repo"`, and the helper
  containers mount it read-only. That covers `launch-card-cell.sh`, `run_on_production_host.sh`,
  and the `watch_*` and `yield_*` scripts. The checkout's `git log` says commit `672202d` of 9 Sep,
  with 34 locally changed paths, because files have been deployed by copying rather than by
  `git pull`. **Its git history is not evidence of what runs; compare hashes.** On 2026-09-17 the
  launch-path files matched laptop `HEAD` byte for byte, except comment-only differences in
  `run_on_production_host.sh`.
**Anything a container writes to a bind mount is owned by root**, because the cell runs as root
inside its image. Your own scratch directory is no exception: after the reconstruction test of
2026-09-17, `rm -rf ~/bootstrap-test` as `varaksin_as` returned `Permission denied` on every file
the container had written. Removing it needed a second container with **that directory as its only
mount** — the mount is what bounds a root `rm -rf` — and then `rmdir` for the empty parent. The same
wall is why 13.4 GB of old, empty run directories still sit on this host
([`production-host/README`](production-host/README.md), the disk notes).

- **The wrappers** — `train-production-cell-v5.sh`, `self-vram-cap.sh`, `gpu-occupancy-log.sh`,
  the sweep scripts — sit loose in `~/rlvigen-work/`. The authoritative copies are in
  `datasphere/native/host-scripts/`. The host's `v5` and `self-vram-cap.sh` differed from those
  only in comments on 2026-09-17.

## 7. Watching a run, and the traps that make a monitor lie

Full detail in procedure §9.5; its complete tool list is procedure §10.4. What you actually reach for:

| What you want to know | Tool | Runs on |
|---|---|---|
| is the cell alive, progressing, and is the card/disk safe | `datasphere/native/host-scripts/watch-cell.sh` (`trip` / `beat`) — **the watcher that actually ran production**, verified against a really-stopped cell and a healthy one | **laptop**, against the host over ssh |
| an older, broader monitor | `datasphere/native/prod-monitor-laptop.sh` — predates today's fixes to stop detection and per-cell disk floors; prefer `watch-cell.sh` | laptop |
| was a card free while nobody was watching | `datasphere/native/gpu-occupancy-log.sh` | host, detached; it outlives the ssh session |
| is our own footprint about to endanger a co-tenant | `datasphere/native/self-vram-cap.sh` | host; stops **our** container by exact name |
| is the policy healthy, or saturating/collapsing | `scripts/watch_policy_health.py --log <training.log>` | laptop; warns, never kills |
| has the run gone NaN | `scripts/watch_divergence.py` | laptop |
| will a cell fit on this card right now | `scripts/watch_gpu_headroom.py` | pre-launch verdict |
| where is the campaign as a whole | `scripts/campaign_status.py`, `scripts/production_gates.py` | laptop |

`gpu-occupancy-log.sh` is the one to start **before** you need it. It is the only record that can
answer "was the card free at 04:00", which is what the ten-minute vacancy rule in §5 was derived
from. It has a 24-hour default life (`GPU_LOG_HOURS`); if you want tomorrow morning covered, say so
when you start it.

The traps, each of which has produced a false reading here:

- **Run the monitor from your laptop.** A monitor writing to a file on the host is not monitoring.
- **Test the alarm branch against a log of a cell that really stopped.** Alarm code never executes
  while things are healthy, so it is never exercised. Five monitors here shared one defect — the
  stop marker is `=== NATIVE_CELL_YIELDED stopping this cell; … ===`, so the usual `awk '{print $2}'`
  yields `NATIVE_CELL_YIELDED`, and `case "$mk" in FAILED|YIELDED)` never matches. A cell died
  unreported for 18 minutes. Use `*FAILED|*YIELDED`.
- **A stop marker does not say why.** The reason is in that run's `native-work/yield.sentinel`.
- **Ask about one run directory, never a glob.** `~/rlvigen-runs/` keeps every attempt, so a glob
  over sentinels returns years of history and reads like a fleet-wide outage.
- **Check `docker stats` before believing a stall or a load average.** Cells sit near one core each;
  a host load of 40 has been someone else's job every time so far.
- **Retire a handled failure from the monitor**, or the dead cell becomes the permanent headline and
  hides the runs that still matter.

## 8. Collection, and the one trap that deletes a result

Procedure §9.6 has the commands. Two things that are not obvious:

0. **Know which file a cell's rows are in — it depends on the kind of cell.** A training cell's
   in-cell grid writes `native-out/cells/<cell>/offline_eval_{curve,endpoint,endpoint_mode}.jsonl`.
   An offline re-evaluation cell launched by `curve-sweep-v3.sh` writes
   **`native-out/offline_eval_cuda.jsonl`**, one run directory per stamp, and packages it into
   `~/rlvigen-runs/reeval-v214/<baseline>-s<seed>-curve-<frame>-result.tgz`. Looking for the first
   path in a sweep's run directory finds nothing and reads like a stalled cell; on 2026-09-17 it
   nearly produced a false stall report about two cells that were at 99% CPU and 42 of 44 rows. A
   sweep is collected with `scripts/collect_reeval_sweep.py`, not `collect-host-run.sh` (procedure §9.6).
1. **Set the interpreter explicitly.** `collect-host-run.sh` runs repo Python as `BP="${BP:-python3}"`,
   so without `BP` it uses whatever `python3` is first on `PATH`. On 2026-09-17 the collection of
   `ibac_sni` s101 was run as `BP=<the interpreter from procedure §0c> bash collect-host-run.sh …`
   and succeeded; that is the executed form.
2. **A cell stopped mid-grid never writes `result.tgz`.** Collect it with
   `assemble_reaped_delivery.py` into `<run-dir>/native-out/records_delivery.jsonl` — that exact
   path — then `NATIVE_ACCEPT_WATCH_STOP=1 bash collect-host-run.sh …`. The collector prints this
   recipe in its own refusal message; read the stderr rather than guessing.
3. **Expect a large "unverifiable" count, and know what it is made of.** Run
   `audit_record_frame_provenance.py <records> --checkpoints <dir>` — without `--checkpoints` it has
   nothing to match and calls *everything* unverifiable. With it, a complete cell decomposes
   predictably. Measured on `idaac` s102's 598 rows (2026-09-17):

   | count | what | why |
   |---|---|---|
   | 484 | curve rows | **corroborated** — frame in the checkpoint's name, frame in the record, hashes agree |
   | 0 | — | **mismatched**: this is the number that must stay zero |
   | 88 | endpoint rows | unverifiable: the terminal checkpoint has no frame in its name (same for `ppg` and `ibac_sni`) |
   | 26 | `phase: "eval"` rows | unverifiable: in-training evaluation, logged during the run, carries no `checkpoint_sha256` at all |

   The tool prints "UNVERIFIABLE IS NOT OK" over the total, which is right as a default and
   misleading here: 114 of 598 were unverifiable for two understood reasons, and **MISMATCHED was
   zero**. Read the decomposition, not the headline, and treat a non-zero MISMATCHED as the alarm.

4. **Never run `populate_evaluator_ledger.py` on a production run.** That script records a
   family's *evaluator attestation*, and the gate accepts only single-scope endpoint evidence
   (one frame, one policy pass) such as an `attest-v2xx` job. A production delivery has a twelve-frame
   curve and a two-pass endpoint, so it can never qualify — and because every run **replaces** the
   family's entry, writing one **removes a valid attestation with no error**. It silently
   un-validated three families before being caught. The script now refuses using the gate's own
   check; do not work around that refusal.

## 8b. The checks: what each proves, when it runs, and whether it has run

A check proves one narrow thing. The column "does **not** prove" is there because most false
confidence in this project came from reading a check as broader than it is.

**Before a launch (laptop)**

| Check | Proves | Does not prove | Ran in this campaign |
|---|---|---|---|
| `setup/verify_sources.py` | the reconstructed trees match their pins | that a fresh reconstruction works (§11.1) | yes, exit 0, in an already-built tree |
| `setup/verify_datasets.py --split train` | Places365 is complete **where you ran it** | anything about the host | yes, laptop only |
| `contract.py verify-payload --require-evaluator-identity --require-runner-contract 19 <tgz>` | the payload is complete and carries the evaluator identity the host runner expects | that the evaluator is the attested one | yes, `idaac` |
| `contract.py verify-evaluator-binding --archive <tgz> --source . --families <family>` | the payload's evaluator hashes equal the live tree's | that the live tree is attested | yes, `idaac` |
| `scripts/production_gates.py` | the mechanical gates (37 pass, 0 fail on 2026-09-17); that the evaluator is attested for all seven families; that the tree is committed | the 9 OWNER items, which are decisions | yes, many times. It **FAILs on any uncommitted file**, including a doc edit — commit, then rerun |
| `scripts/operator_readiness.py` | every path the procedure names exists and every live script's interface is documented | that the procedure is correct (its own output says so) | yes, exit 0, including in a fresh clone |

**At launch (inside the launcher, automatic)**

| Check | Where | Stops the launch when |
|---|---|---|
| GPU preflight | `watch_gpu_headroom.py --preflight --need-mib ${NATIVE_NEED_MIB:-4000}` (`launch-card-cell.sh:238`) | the card lacks the stated free memory **now** — a snapshot, not a vacancy; §5.1 |
| Watch arming | each watch container must start and still be running ten seconds later (`launch-card-cell.sh:254,302,334,456-459`) | a watch refuses its arguments, e.g. a budget that cannot cover the cell |
| `DOCKER_GPUS` and the VRAM-cap variable are set | `run_on_production_host.sh:123,171` | either is unset |
| `NATIVE_HOST_DRY_RUN=1` | `run_on_production_host.sh` | — it runs every guard and prints mounts and environment without executing. **Not run before the 16–17 Sep launches**; earlier sessions used it (`production-host/14`) |

**Inside the cell, after training (automatic; a failure is `NATIVE_CELL_FAILED`)**

| Check | Where | Proves |
|---|---|---|
| Endpoint marker | `verify_final_evaluation` (`run_probe.sh:305`) requires `NATIVE_FINAL_EVALUATION_COMPLETED frame=<expected>` | training reached exactly the family's own endpoint (`family.py expected-endpoint`) |
| Retain | `family.py retain` | the declared checkpoints exist and were copied to `native-out` |
| Finite weights | `family.py check-finite` on the retained terminal checkpoint | no NaN or Inf in the policy that will be evaluated |
| Strict curve | `CURVE_EVAL_STRICT`, on by default in production | every intermediate stamp produced its rows |

**After collection (laptop)**

| Check | Proves | Ran in this campaign |
|---|---|---|
| `collect-host-run.sh` | eight steps: the run succeeded by its own markers, the renderer was real (not `llvmpipe`), the bundle is non-empty, its source matches the log, the row count matches what the runner said it wrote, two audits that need host artifacts; then installs rows in `results/records/` | yes: `ibac_sni` s101 (910 rows), `idaac` s102 (598) |
| `audit_record_frame_provenance.py <records> --checkpoints <dir>` | each curve row's frame agrees with the checkpoint it names; **MISMATCHED must be 0** | yes, `idaac` s102: 484 corroborated, 0 mismatched (§8 item 3) |
| `campaign_status.py` | which (baseline, seed) cells are DONE / PARTIAL / MISSING against the schedule | yes |
| `export_fleet.py` | one flat table of every record, and how many are on the current evaluator closure | yes: 6,193 rows, 2,932 current |
| `production_reading.py` | the headline reading: endpoint returns aggregated episodes → scenes → **seeds**, per EVAL-PROTOCOL §4c, with every seed point printed and fewer than three marked PROVISIONAL | yes, 2026-09-18: reproduces the hand-computed two-seed `idaac` numbers exactly |
| `audit_attempt_ledger.py --strict` | no rerun silently replaces an earlier attempt; host attempts come from `results/host-runs.jsonl` | yes, exit 0 on 2026-09-17 |
| `populate_evaluator_ledger.py` | **attestation jobs only** (§8 item 4) | yes: accepted three `attest-v212` files, refused two production files |

## 9. What you must not improvise

The grid, the checkpoint cadence and the seed set are fixed, and changing them makes the numbers
incomparable with everything already banked. Procedure §10.2. The evaluator closure is hashed: editing
any hashed file — **comment bytes included** — moves every family's revision and invalidates
attestations built against the old one.

## 10. When something goes wrong

### 10.1 The four questions, in order

Paths below assume the conventions this host uses: a run directory
`~/rlvigen-runs/card<N>-<YYYYmmdd-HHMMSS>/`, and a launcher log
`~/rlvigen-runs/prod-v214/<baseline>-s<seed>-prod.log`.

    # 1. Did it stop, and how? Read the last FEW markers, not the last one: a yield prints
    #    NATIVE_CELL_YIELDED and then NATIVE_CELL_FAILED (§6b). This is the grep
    #    train-production-cell-v5.sh itself runs at the end of every launch.
    grep -aoE "NATIVE_(CELL_[A-Z_]+|RECORDS_EMITTED [0-9]+|ENDPOINT[A-Z_]*)[^=]*|CELL EXIT=[0-9]+" "$LOG" | tail -4

    # 2. WHY did it stop? The marker never says. The sentinel does.
    cat "$RUN/native-work/yield.sentinel"

    # 3. Is it actually dead, or just quiet?
    docker ps --format '{{.Names}}' | grep -E '^cell-c1-[0-9]+$'
    docker stats --no-stream <cell-container>        # ~100% CPU means working, not stalled

    # 4. What survived?
    ls "$RUN/native-out/cells/<cell>/checkpoints/"        # only after training COMPLETED
    ls "$RUN/native-work/runs/<baseline>-s<seed>/"        # while training, or if it stopped early;
                                                          # each family's subpath is in §6c
    wc -l "$RUN/native-out/cells/<cell>/"offline_eval_*.jsonl

Question 3 has saved a healthy cell more than once: a quiet log is not a dead cell, and a host load
average of 40 has so far always been someone else's job.

### 10.2 Symptoms seen on this host, and what each cost

| Symptom | Where it shows | What it was | What survived |
|---|---|---|---|
| Cell gone minutes after launch, sentinel says `free memory … below the 4000 MiB floor` | sentinel | the co-tenant reclaimed the card during the cell's ramp | **nothing** if it stopped before the first 50k checkpoint; everything up to the last stamp otherwise |
| Same, but hours in | sentinel | co-tenant returned mid-run | all stamped checkpoints, in `native-work/` |
| Cell exits ~24 s in, no floor message | launcher log: `EGL_NOT_INITIALIZED` | rendering never initialised | nothing; relaunch |
| Cell vanishes at the end of a long grid, no `result.tgz` | launcher log: watch budget exhausted | the watch expired mid-evaluation | every row already written; collect with `assemble_reaped_delivery.py` |
| Log silent 10–20 min, cell alive at ~100% CPU | `docker stats` | normal cadence for `idaac` (~11 min) or a slow endpoint row | nothing lost — **do not intervene** |
| Disk alarm, cells still running | `df` vs each cell's banner floor | a *new* cell's bootstrap ate into an older cell's margin | nothing, if it recovered inside one 60 s sample (§9.5c) |

**The rule underneath the first two rows:** a training cell stamps a checkpoint every 50,000 frames,
so the question "what survived" reduces to "did it pass frame 51,200". Attempt 1 of `ibac_sni` s102
died at 28,672 and kept nothing; attempt 2 died at 376,832 and kept seven checkpoints, each
separately evaluable. That difference is the whole argument for the ten-minute vacancy rule in §5.

### 10.3 After any failure

Record it. A failed attempt is part of the record, not something to discard — otherwise a rerun
silently replaces a failed seed and nobody can tell. `scripts/record_host_run.py` takes a terminal
status and a note; `scripts/audit_attempt_ledger.py --strict` fails when an earlier attempt has no
outcome. The procedure section "Recording an attempt that failed before it wrote anything" covers
the case where there is no run directory to point at.

### 10.4 Off the golden path: what you see, what it means, what to do next

Keyed on the exact text the scripts print. **Seen** means it happened on this host in this
campaign. **Code** means the text was read from the script and the branch has not been hit here.

**Before the cell starts** — nothing ran, nothing to salvage, nothing to record beyond a note:

| You see | From | Meaning | Next |
|---|---|---|---|
| `SKIP <tag> (result present)` | `train-production-cell-v5.sh` (code) | a result archive for this baseline and seed already exists | check `campaign_status.py`; do not delete the archive to relaunch |
| `VACANCY NOT SUSTAINED -- aborting` | the §5.2 launch block (seen) | the co-tenant is back or memory is short | wait for `capacity-check.sh` to say AVAILABLE again |
| `ABORTING: preflight refused the card.` | `launch-card-cell.sh:243` (code) | the card lacks the free memory the preflight needs right now | wait; do not lower `NATIVE_NEED_MIB` (§5.1) |
| `ABORTING: CARD=1 is not card 0, and NATIVE_YIELD_ON_PROCESSES is not 1.` | `launch-card-cell.sh:270` (code) | card 1 needs process yield armed | relaunch with `YIELD_PROCS=1` |
| `ABORTING: the … watch refused to arm.` / `… is not running ten seconds after launch. It refused:` | `launch-card-cell.sh:254,302,334,456-459` (code) | a watch container rejected its arguments; the reason is printed below the line | read it; usually a budget that cannot cover the cell |
| `refusing: DOCKER_GPUS is unset` / `… with no NATIVE_VRAM_CAP_MIB` | `run_on_production_host.sh:124,172` (code) | called the wrapper outside `launch-card-cell.sh` | use the layers in §5 |
| `refusing: FRAMES=… is production scale and <X> is unset.` | `run_on_production_host.sh:311-349` (code) | a production-scale run without its required setting | set it; v5 sets all of them |
| `refusing: NATIVE_RESULT_MIRROR is on the SAME filesystem …` | `run_on_production_host.sh:421` (code) | `cds2` has one data disk | v5 passes `NATIVE_ACCEPT_SAME_DEVICE=1`, which prints `NATIVE_RESULT_MIRROR_SINGLE_DEVICE_HOST` instead. That means **the host copy has no second failure domain; your laptop fetch is the only other copy** |
| `refusing: … GB free at …, below the … GB this job needs.` | `run_on_production_host.sh:529` (code) | not enough disk for this family (§4c.1) | wait, or run a family with a smaller need |
| `=== NATIVE_EDITABLE_NOT_INSTALLED <module> ===` | `run_probe.sh:1801` (code) | a prebuilt environment without the RL-ViGen editable installs | drop `NATIVE_VENV_HOST` (§6d) |
| Places365 split refusal naming `NATIVE_PLACES365_ACCEPT_VAL` | `run_probe.sh:2088-2093` (code) | a Places365 baseline pointed at `val` | O1 in §11.4; accepting `val` is an owner decision |

**During or after training** — something may have survived; record the attempt either way (§10.3):

| You see | Meaning | What survives | Next |
|---|---|---|---|
| `NATIVE_CELL_YIELDED`, then `NATIVE_CELL_FAILED` (**seen**, seven times across `ibac_sni` and `idaac` attempts) | the memory or disk floor fired; the sentinel says which | stamps in `native-work/` | §5.2 failure branch; rerun only after a real vacancy |
| `EGL_NOT_INITIALIZED` about 24 s in (**seen** once) | rendering failed to start | nothing | relaunch; not a capacity problem |
| `NATIVE_CELL_FAILED_STALLED` (code on this host; seen on DataSphere) | no output for 30 min during training | stamps so far | read the last lines of `training.log` before relaunching; a deadlock recurs |
| `NATIVE_CELL_SIGNALLED` (code on this host) | the trainer was killed, e.g. by the kernel OOM killer | stamps so far | find out whose memory ran out before relaunching; on a shared host this may have hurt someone else |
| `final evaluation marker missing: NATIVE_FINAL_EVALUATION_COMPLETED frame=<n>` (code) | training ended somewhere other than the family's own endpoint | stamps; no retained checkpoints | a trainer or budget defect; do not rerun unchanged |
| `NATIVE_CURVE_EVAL_NO_STAMPS` / `NATIVE_ENDPOINT_SUPPLEMENTARY_INCOMPLETE` (code) | the in-cell grid could not find stamps, or one endpoint pass failed | retained checkpoints and any rows written | the rows can be re-made offline from the checkpoints (§11.2 sweep) |
| `!! REAPING <cell>` (code; a watch-budget stop was **seen** on `idaac` s101 on 9 Sep, before the reaper printed this text) | the watch budget ran out; the reason (silent or out of grace) is on the next line | every row written | `assemble_reaped_delivery.py`, then `NATIVE_ACCEPT_WATCH_STOP=1 collect-host-run.sh` (§8 item 2) |
| `NATIVE_SELF_VRAM_CAP_TRIPPED` in the cap log (code) | our compute memory crossed the cap you set | as a reap | the cap or the family's peak figure is wrong; recheck §4c before relaunching |

**At collection:**

| You see | Meaning | Next |
|---|---|---|
| `REFUSING: no NATIVE_CELL_COMPLETED marker.` plus a two-line recipe (code; the recipe's path was used for `idaac` s101) | the cell was stopped mid-grid | run the printed recipe exactly |
| a NOTE that the evaluator ledger declined a production run (**seen**) | correct behaviour | nothing; never run `populate_evaluator_ledger.py` on it |
| `audit_record_frame_provenance.py` MISMATCHED > 0 (never seen) | a row's frame disagrees with its checkpoint | stop and investigate; do not report those rows |

Further reading, in order of usefulness during an incident:
`production-host/15-what-fails-when.md` (symptom → cause), `model/STOP-MECHANISMS.md` (every stop
mechanism and which actually fire), `DECISIONS-IF-PRODUCTION-GOES-WRONG.md` (decisions already
taken, so you do not re-litigate them at 3 a.m.).

## 11. What has actually been executed — the boundary

**The adversarial half of this section** — what can still go wrong, which guard actually fires, and
what a first run will meet — is
[`OPERATOR-READINESS-ADVERSARIAL-2026-09-18.md`](OPERATOR-READINESS-ADVERSARIAL-2026-09-18.md).
Read it before the first cell of any family that has not run here.

This section separates **what someone ran and saw work** from **what is written down but was never
run**. The first kind is evidence. The second is a proposal, however careful, and on 2026-09-17
running four "documented" commands for the first time found two that exit 2 as written. Treat
anything in the right-hand column as untested until you have run it yourself.

Everything in the left column was run between 2026-09-09 and 2026-09-17 on the production host
(`cds2`, 2× V100-32GB, shared) or the maintainer's macOS laptop, and is recorded in
`results/host-runs.jsonl`, `results/records/` or `results/evidence/`.

### 11.1 Laptop side

| Executed and worked | Written but not executed here, and why |
|---|---|
| `setup/verify_sources.py`, `setup/bootstrap_sources.py --verify-only`, `setup/verify_datasets.py --split train` and `--split val` — all exit 0 **in an already-reconstructed tree** | ~~**`setup/bootstrap_sources.py` doing a real reconstruction.**~~ **Executed 2026-09-17/18** in a container on the host: bootstrap, `verify_sources.py`, then payload build + verify + binding for all seven families, every exit code 0 (§11.4 O8). It still refuses on macOS, so it cannot be run here. |
| `contract.py build-payload --source . --output <tgz> --families <family>`, then `verify-payload --require-evaluator-identity --require-runner-contract 19` and `verify-evaluator-binding --archive … --source . --families <family>` — all exit 0 for **all seven families**, on the laptop for `idaac`, `rlvigen`, `dmc_gb`, `alda` and `ctrl`, and on Linux from a freshly reconstructed tree for all seven (§11.4 O8). (`rlvigen`'s payload is 284 KB because it never carries `RL-ViGen-upstream/`; the cell clones that at run time.) | `operator_readiness.py` → exit 0 and `campaign_status.py` → a readable instruction were also run in a fresh clone. What no one has done is take a fresh clone through to a **running cell** — the payloads are verified, not exercised. |
| `collect-host-run.sh ibac_sni <run-dir>` on a cleanly completed cell → 910 rows installed. **Needed `BP=<python>` set explicitly**; the script falls back to `python3` otherwise | `collect-host-run.sh` on a **reaped** cell with `NATIVE_ACCEPT_WATCH_STOP=1` was run for `idaac` s101 earlier in the campaign, not in this session |
| `assemble_reaped_delivery.py` as a dry run on a mid-flight `ibac_sni` copy → 528 rows, correctly marked | |
| `populate_evaluator_ledger.py`: refused two production files, accepted three `attest-v212-*` files; gate went 5/7 → 7/7 | |
| `production_gates.py` (37 pass / 0 fail / 9 owner), `campaign_status.py`, `operator_readiness.py` | |

### 11.2 Host side

| Executed and worked | Written but not executed here, and why |
|---|---|
| **Launch through `wait-and-train-v3.sh`** — `ibac_sni` s101, 2026-09-16 20:35, trained 600k in 31.5 min (`time -v`; 44 min counted from launch) and completed its full grid | `wait-and-train-v3.sh` has launched **one** cell. Its lock and hold logic are proven by that one run and by reading, not by repetition. |
| **Launch through `train-production-cell-v5.sh` directly** — `idaac` s102 (21:32), `ibac_sni` s102 twice (07:50, 11:00) | |
| `self-vram-cap.sh` armed on three cells; `gpu-occupancy-log.sh` as the only record of card vacancy | |
| **Two and three cells packed on one card** — throughput ratio measured at r = 0.90 | Packing more than three, or two *training* cells at once |
| **The Places365 launch path, dry-run** — `NATIVE_HOST_DRY_RUN=1` for `svea:101` printed the read-only corpus mount, the forwarded split, the pinned image, `rc=0` | A Places365 cell actually running: the corpus reaches the container by a path no cell has yet consumed |
| **The memory floor stopping a training cell** — seen twice on 2026-09-17, both documented with their sentinels; grid cells ignored the same event | The disk watch actually **firing**: it came within one 60 s sample of doing so and did not |
| **A mid-training stop leaving checkpoints in `native-work/`** — 7 salvaged from `ibac_sni` s102 attempt 2 and fetched explicitly | |
| **Offline re-evaluation of stamped checkpoints with `curve-sweep-v3.sh`** — `ibac_sni` s102, launched 15:54 on 2026-09-17 with `MAXCELLS=3`. The first result was checked, not assumed: 44 rows, curve scope, frame 100,352 on every row, 3 episodes, and `checkpoint_sha256` equal to the sha256 of `model_100352.pt` on the host, with the evaluator revision binding to the live tree. It skipped the frame-less `model.pt` and held at 3 cells as configured. (Moved here from the right column once it had worked, as §11.5 says to.) | |
| `watch-cell.sh` in both modes; verified against a really-stopped cell and a healthy one | |

### 11.3 Never run in this campaign, at all

The short list. §11.4 takes each item apart into what is missing, the target, and the operation.

- **Nine of twelve baselines have never completed a production cell here**: `drqv2`, `svea`, `drq`,
  `sgqn`, `curl`, `rad`, `soda`, `alda`, `ctrl`. Every per-family quirk this guide records comes from
  `idaac`, `ppg` and `ibac_sni`. Expect new ones.
- **Places365 on the host.** The ~24 GB corpus has never been placed there. `svea`, `sgqn` and `soda`
  need it and have never run. The laptop has it, which proves nothing about the host.
- **`ctrl` at 600k.** Its observed peak, 32,435 MiB, does not fit beside the 4,000 MiB floor on a
  32,494 MiB card. It needs an empty card and an explicit decision about the floor.
- **`docs/RUN-THIS-PROJECT.md` §5a** (any Linux host with Docker) and **§5b** (DataSphere) were not
  exercised in this session.
- **Resuming a stopped cell, in any family.** §6c reads each trainer's restore path from code; none
  has been executed. Two families load automatically from their run directory, one has a flag no
  launcher passes, four have no restore path at all, and every restore loses something.
- **Any host other than `cds2`.**

### 11.4 Out of reach so far — each item narrowed to its part, with the state to reach

Each entry names **the part** that is missing, **why** it has not been done, **the target state**,
**the operation** that reaches it, and **how to tell** it worked. Where an operation has never been
executed, the entry says so; treat it as a proposal until it has run.

**O1 — Places365 train split on the host** (blocked `svea`, `sgqn`, `soda`) — **CLOSED 2026-09-18 10:50**

- *The blocker was misdiagnosed, and measuring it changed the answer.* `fetch-places.sh` was
  abandoned at ~55 kB/s, which read as "this host cannot fetch it". Measured on 2026-09-18 from a
  container on the host: **GitHub 13.7 MB/s** (116 MB in 8.5 s), **`data.csail.mit.edu` 623 B/s**.
  The host's link is fine; that one source is dead slow.
- *What is being done instead:* the laptop already holds the corpus this project validated —
  26 GB, 1,803,461 files, 365 classes, `verify_datasets --split train` PASS — so it is being
  shipped as a single `tar` stream into a container that extracts it to
  `~/rlvigen-assets/places365-train/places365_standard/train`. Measured uplink 2.4 MB/s, so about
  three hours. Shipping our own validated copy keeps provenance identical to what every attestation
  used; a third-party mirror would not.
- *The launch path is now dry-run proven, which it never was.* On 2026-09-18,
  `NATIVE_HOST_DRY_RUN=1` through `run_on_production_host.sh` for `svea:101` printed the corpus
  mounted `-v …/places365-train:/opt/places365:ro`, `NATIVE_PLACES365_DIR=/opt/places365` and
  `NATIVE_PLACES365_SPLIT=train` in the cell's environment, the digest-pinned image and the
  graphics capability — `rc=0`, nothing executed. `train-production-cell-v6.sh` wires it, and
  `payload-v215-rlvigen.tgz` and `payload-v215-dmc_gb.tgz` are on the host, hash-verified against
  the laptop. What remains untested is the cell's own consumption of the corpus at run time.
- *Accepted, with the checks that make it a corpus rather than a directory:* 26 GB,
  **1,803,462 files, 365 classes**, at `~/rlvigen-assets/places365-train/places365_standard/train`.
  `chmod -R a+rX` in a container (the extractor writes as root — even `du` was refused), then
  `verify_datasets --root /data --split train` on the host: **PASS**. Then **200 randomly sampled
  files compared by sha256 against the laptop copy: 200 identical, 0 mismatched, 0 missing** — so
  it is verified byte-for-byte, not merely present. No archive copy was kept; the tar was streamed.
- *Still untested, and it is the next thing to learn:* no cell has consumed the corpus at run time.
  The wrapper path is dry-run proven (§11.2); the loader is not.

*Original entry, kept because the target and the check are unchanged:*

- *State now, checked 2026-09-17 in the helper container:* `~/rlvigen-assets/places365/train/` has 20
  classes and 1,000 files, the attestation fixture. `val/` is complete (36,500 images).
- *Why not done:* the ~24 GB tarball downloaded at about 55 kB/s inside a container (`fetch-places.sh`)
  and was abandoned. It needs 47.5 GiB of a shared disk that had about 175 GiB free.
- *Target:* a train tree with 365 class directories on the host, which the launcher receives either
  as the fourth positional archive or as a directory through `NATIVE_PLACES365_DIR_HOST`
  (`run_on_production_host.sh:662-694`). Keep it apart from the fixture, which the attestation
  check expects to hold exactly 1,000 files.
- *Operation:* get the tarball onto the host by a faster route. The laptop holds a copy that passes
  `verify_datasets.py --split train`; copying it across has **not** been tried, and its rate is
  unknown. Extract inside a container. **Also needed:** `train-production-cell-v5.sh` passes no
  Places365 argument, so as written it cannot launch these three baselines.
- *Done when:* the container check in procedure §2b prints `class directories: 365` and
  `dataset usable: PASS`.
- *Or, instead:* run against `val` with `NATIVE_PLACES365_ACCEPT_VAL=1`, a recorded deviation from
  A22. That is an owner decision, not an operator one.

**O2 — Current payloads for the four families that have not run** (`rlvigen`, `dmc_gb`, `alda`, `ctrl`)
- *State now:* the host has `payload-v214-*` for `idaac`, `ibac_sni` and `ppg` only, and older
  `v212` payloads for all seven. Whether a `v212` payload binds to today's tree has not been checked.
- *Target:* each family's payload on the host, built from the committed tree, with the same sha256
  as on the laptop.
- *Operation:* on the laptop, `contract.py build-payload --source . --output <tgz> --families
  <family>`, `verify-payload --require-evaluator-identity --require-runner-contract 19`,
  `verify-evaluator-binding --archive <tgz> --source . --families <family>`, then `scp`.
  **The laptop half is done:** on 2026-09-17 all three steps ran and exited 0 for `rlvigen`,
  `dmc_gb`, `alda` and `ctrl` against the committed tree. What is left is the copy to the host.
  **The payload-naming caveat this used to carry is closed, not open.** `train-production-cell-v5.sh`
  does read `payload-v214-$FAMILY.tgz` by that literal name — but §5.3's `train-production-cell-v6.sh`
  already takes `PAYLOAD=<path>` as an override, and is behaviourally identical to v5 for every family
  that does not set `PLACES365_DIR` (verified 2026-09-18: `v6` is `v5` verbatim plus that one
  substitution — `diff`'d line by line). It has already been exercised for real: `svea`'s armed
  waiter passes `WRAPPER=train-production-cell-v6.sh PAYLOAD=$HOME/rlvigen-work/payload-v215-rlvigen.tgz`
  right now. So for any of these four families, ship the new build under its own honest name and
  launch with `WRAPPER=train-production-cell-v6.sh PAYLOAD=<that name>` — no naming compromise and
  no new code needed.
- *Done when:* the binding check exits 0 and the host copy's sha256 matches.

**O3 — The first 600k cell of an off-policy baseline** (`drqv2` first: it needs no Places365)
- *Why not done:* O2, and then capacity. None of `drqv2`, `drq`, `curl`, `rad`, `soda`, `alda` has
  trained here, so their training time, CPU use and real host RAM are unknown (§4c.1).
- *Target:* one `drqv2` cell `COMPLETED` and collected.
- *Operation:* §5.2 with `FAMILY=rlvigen BASELINE=drqv2`, one such cell at a time. RAM is the
  unmeasured bound (≈40 GiB computed, of a shared 113 GiB), and the launcher does not check it, so
  look at `free -g` on the host before launching and during the first hour. The upper-bound rule in
  the project `CLAUDE.md` applies. Its replay buffer cannot be restored (§6c), so a stop means a
  rerun from zero.
- *Done when:* `campaign_status.py` shows the cell DONE; record its `time -v` figures in §4c.1.

**O4 — `ctrl` at 600k**
- *Why not done:* observed peak 32,435 MiB on a 32,494 MiB card leaves no room for the 4,000 MiB
  floor. Its 64-environment RAM figure (54.3 GiB) is a linear extrapolation.
- *Target:* one `ctrl` cell completed on an otherwise empty card.
- *Operation:* needs (a) a card with no co-tenant for the whole run, which has not happened on this
  host, (b) an owner decision about the memory floor for this one cell, and (c) a RAM measurement.
- *Done when:* the cell completes with the floor decision written in its record.

**O5 — A stopped cell continued rather than rerun**
- *Why not done:* §6c. Four families have no restore path, one has a flag no launcher passes, and two
  load automatically but lose the replay buffer or the optimizer state.
- *Target:* an owner decision on whether a continued run may stand in for a seed. Only if yes,
  launcher support for it.
- *Done when:* the decision is written down. Until then, rerun from zero.

**O6 — Renderer parity between the validation platform and this host** (an OWNER gate,
**substituted 2026-09-18** — see below)
- *Original target:* procedure §0, item 3. Evaluate one known checkpoint with the current evaluator
  where it was validated (R_A), then with the same checkpoint, evaluator and container on this host
  (R_B), and compare returns and rendered-observation witnesses.
- *Owner's ruling, 2026-09-18:* the full three-step numeric comparison is not needed. This
  campaign's returns already sit on the published table's axis
  (`notes/CAMPAIGN-REPORT-2026-09-18.md` §2), so what remains open is not whether the axis matches
  but whether the rendered pixels look right — a question a human answers by looking, not a new
  measurement pipeline.
- *Substitute, built and unit-tested but NOT yet run on the host:* `scripts/visual_render_probe.py`
  resets the Door environment at each of `train`/`eval-easy`/`eval-medium`/`eval-hard` and saves one
  PNG per regime, through the same `wrappers.robo_wrapper.robo_make` constructor every cell and
  evaluation uses. Its frame-extraction and file-writing logic is proven against a fake environment
  in `tests/test_visual_render_probe.py` (6/6 pass, no robosuite/mujoco/GPU needed for that).
- *Why it has not been run on the host yet:* it needs `MUJOCO_GL=egl` and robosuite/mujoco, which
  are pip-installed inside the pinned cell image at container start (§6d) — the same bootstrap cost
  and risk as launching a real cell, for a script that produces four PNGs. C95 rules out a cheaper
  local/CPU substitute: the same checkpoint reads train 131.5 under `MUJOCO_GL=egl` and 13.85 under
  `glfw` on this laptop, so a non-EGL render answers a different question than the one being asked.
  Spending a card window on this alone, while the card is the scarcest resource in the campaign, is
  not worth it as a standalone action.
- *Recommended way to close it:* run it inside the next real cell's container, after its bootstrap
  has already paid the install cost and before or after training —
  `python scripts/visual_render_probe.py --out results/evidence/visual-render-probe/frames`, then
  build the evidence bundle (`CLAIM.md` + `capture.sh` + `manifest.json`, per
  `results/evidence/README.md`) from the PNGs and the container's own `MUJOCO_GL` setting, with the
  `CLAIM.md`'s Status stated as a question for the operator: "do these look like robosuite Door
  under progressively harder visual shift, and does `train` look like the environment the agent
  trained in?" No bundle exists yet — creating one with no captured evidence would itself be the
  kind of unverified claim this project's evidence-bundle discipline exists to prevent.

**O7 — Stop paths that have never fired here:** the training wall clock, the disk floor, the
reaper on a genuinely hung grid, `self-vram-cap.sh` tripping. *Target:* none; do not provoke them on
a shared host. *What to do if one fires:* §6b gives the marker and what survives, and §10.1 the order
of questions. The disk floor came within one 60-second sample of firing on 2026-09-17.

**O8 — A fresh clone reconstructed on Linux** — **CLOSED 2026-09-17**
- *What was done:* the committed tree (`git archive HEAD`, 37 MB — what a clone gives you) was
  shipped to the host and reconstructed inside a `python:3.11-slim` container with its own network:
  `setup/bootstrap_sources.py` then `setup/verify_sources.py`, both exit 0, both printing
  `source reconstruction verified`. 9 min 40 s, about 1.7 GB of disk, removed afterwards. Evidence:
  [`results/evidence/linux-reconstruction-from-a-fresh-tree`](../results/evidence/linux-reconstruction-from-a-fresh-tree/CLAIM.md),
  which carries the recipe as `capture.sh` (`RERUN=1` does the whole thing again).
- *And the rest of the cold start, same night:* from the same fresh tree, `build-payload`,
  `verify-payload --require-evaluator-identity --require-runner-contract 19` and
  `verify-evaluator-binding` were run for **all seven families** — every exit code 0, against a
  `RUNNER_CONTRACT` of 19 read out of that tree. So clone → reconstruct → build → verify holds end
  to end on Linux. The same bundle carries that run as `raw/clone-to-payload.txt`.

**O9 — A prebuilt Python environment for the torch families** — **CLOSED 2026-09-19**, which would
remove the 7–22 minutes of in-container `pip` per launch (§6d)
- *What was wrong, found across three attempts:* first, `build-env.sh`'s cache key
  (`${stack}-${reqhash}-${digest}`) can't distinguish "built with `RL-ViGen-upstream/`" from "built
  without," so a 2026-09-08 `idaac`-only build permanently occupied the slot any torch-stack rebuild
  needed. Deleting and rebuilding from a payload believed to carry `RL-ViGen-upstream/` (2026-09-18)
  changed nothing — `editable: []` both times — because **no payload contract.py has ever built
  carries that tree**; `run_probe.sh:1788-1789` already said so directly: it is always cloned live,
  into the cell's own work directory, at launch time.
- *The real fix:* `build-env.sh` now clones the pinned commit and applies this project's own
  patches itself when the payload lacks `RL-ViGen-upstream/` (which is always), mirroring exactly
  what `run_probe.sh` does for a real cell — cloning without patching would have been worse than
  doing nothing, since unpatched upstream imports cleanly and is silently wrong.
- *Verified, not assumed:* ran it for real against `svea:101` — `Successfully installed
  robosuite-1.4.0` and `robosuitevgb-1.0.0`, `ENVIRONMENT.json` now reads
  `"editable": ["robosuite", "robosuitevgb"]`. The patch step's own `--check` sits before those
  installs under `set -euo pipefail`; since the installs succeeded, the check necessarily passed
  first — the script's own control flow rules out a false "imports fine but unpatched" pass, which
  is the failure class the rest of this codebase has been bitten by before.
- One env now serves `idaac` and the four other torch-stack families
  (`rlvigen`, `dmc_gb`, `alda`, `ppg`, `ibac_sni` — all resolve to the same package hash). `ctrl`
  (the JAX stack) is untouched by this and still builds its own environment separately.

### 11.5 How to use this section

Run a left-column item and it should behave as described; if it does not, something changed and it
is worth a note. Run a right-column item and **assume nothing** — read its output, check what it
wrote, and move it to the left column in this file once it has worked for you.
