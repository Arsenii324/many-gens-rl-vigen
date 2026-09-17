# Operator guide — the whole path, end to end

**You are here because you have this repository and a production host, and nothing else.** This
file is the **map**: what exists, what produces what, what runs after what, and which tool belongs
to which stage. It deliberately does **not** restate commands. The executable procedure is
[`RUNNING-ON-PRODUCTION-HOST.md`](RUNNING-ON-PRODUCTION-HOST.md) (referred to below as **the
procedure**, cited by section), and duplicating it here would create two copies of one rule that
drift apart — a failure this project has already had more than once.

Read this once, top to bottom, before running anything. It is about 15 minutes. Then work from the
procedure with this page open beside it.

- **What is true right now** (what is running, what is banked, what is blocked):
  [`CURRENT-STATE-AND-RESPONSIBILITY.md`](CURRENT-STATE-AND-RESPONSIBILITY.md). It goes stale by
  design; re-run the commands it names rather than trusting its numbers.
- **Why things are the way they are**, and every incident behind a rule:
  [`production-host/README.md`](production-host/README.md), 34 numbered notes.
- **What someone was thinking mid-flight**, including unproven suspicions:
  [`HANDOFF.md`](HANDOFF.md).
- **Index of every surface**: [`START-HERE.md`](START-HERE.md).

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

## 4. The stages, in order, with a finish line for each

| # | Stage | You are done when | Procedure |
|---|---|---|---|
| 0 | Read the prohibitions | You can state the host rule in §2 from memory | `production-host/README.md` |
| 1 | Laptop environment | The interpreter in §0c runs `scripts/production_gates.py` | §0c |
| 2 | Sources reconstructed | `setup/verify_sources.py` passes | `setup/SOURCE-BOOTSTRAP.md` |
| 3 | Datasets present | `setup/verify_datasets.py` passes for the families you will run | §2b |
| 4 | Payload built | `contract.py verify-payload` accepts the tgz you will ship | §2 |
| 5 | Host preconditions | The ten checks pass on the host | §1 |
| 6 | Dry run | The wrapper completes a short cell end to end | §2c |
| 7 | Launch | The launch banner prints its watch budget, disk floor and eval workload | §3, §9.2 |
| 8 | Watch | A monitor is reporting to **you**, not to a file on the host | §9.5 |
| 9 | Collect | Rows are in `results/records/` and `campaign_status.py` moved | §9.6 |

Stages 0–4 are laptop-only and can be done before you have the host. Do them first.

## 4b. Cold start: a fresh clone to a shipped payload

Stages 1–4 need no host. Each step produces something the next one consumes, and each has a
verifier that proves the step rather than asserting it. Commands live in the procedure §2 and
`setup/SOURCE-BOOTSTRAP.md`; what follows is the ordering and what each check actually establishes.

| Step | Command (see §2 / SOURCE-BOOTSTRAP) | Proves |
|---|---|---|
| 1 | `python3 -c "import numpy, json, pathlib"` | you have an interpreter these scripts can use (3.10+, numpy; matplotlib only for plots) |
| 2 | `setup/bootstrap_sources.py [--family F]` | the pinned upstream trees are reconstructed under `runnable/` |
| 3 | `setup/verify_sources.py` | they reconstruct **without network access** — a clean clone is self-sufficient |
| 4 | `setup/verify_datasets.py [--split train]` | an external corpus this repo deliberately does not carry is present. **Only `svea`, `sgqn`, `soda` need it**; a clone without Places365 is correctly reconstructed and simply cannot run those three |
| 5 | `contract.py build-payload --source . --output payload-vNNN-<family>.tgz --families <family>` | a source-only archive; the allowlist rejects `results`, `logs`, `models`, `data`, `.git`, `.venv`, credentials |
| 6 | `contract.py verify-payload --archive … --require-evaluator-identity --require-runner-contract 19` | the archive carries the per-family identity and matches the runner contract the host expects |
| 7 | `contract.py verify-evaluator-binding --archive …` | the evaluator in the archive binds to the families it claims |
| 8 | `scp payload… <asset tgz> user@host:~/` | the host has what it needs |

`RUNNER_CONTRACT` is **19** today (`contract.py:154`). It is written in two places — that constant
and the `--require-runner-contract` argument in the procedure — and them drifting apart has killed a
job before, so read it from the source rather than from memory.

**The payload is source only.** Everything third-party — apt packages, pip, RL-ViGen upstream — is
fetched *inside the container at run time*, so **the host needs outbound network access**. A cell on
an air-gapped host will fail in its bootstrap, not at launch.

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

## 5. What to launch with, and why there are three layers

    wait-and-train-v3.sh   waits for a sustained free card, then calls ↓   (use this by default)
    train-production-cell-v5.sh   sets the production environment, calls ↓
    launch-card-cell.sh    sizes the watches, starts the containers

Use the **waiter** unless you have a reason not to. It enforces a **ten-minute sustained vacancy**
(`HOLD=10` polls at `POLL=60`), and that number is measured, not chosen: over 30 hours of the
occupancy log the co-tenant's absences were 2, 1, 1, 36, 1, 1, 171, 1, 5, 1, 1 and 4 minutes. Ten of
twelve were **restarts between its jobs**, not vacancies. Launching into one of those killed a cell
twice on 2026-09-17. Procedure §9.5b has the arithmetic; note 34 has the campaign consequence.

It also takes a `flock` and holds it for the life of the cell it started, so a second waiter
refuses. That lock is duplicate prevention, not a capacity limit.

## 6. The containers, per cell

One launch creates **four** containers plus one optional host process. Names carry the card and the
launcher's PID, e.g. `cell-c1-1437491`.

| Container | Role | Stops the cell? |
|---|---|---|
| `cell-c<card>-<pid>` | the cell: training, then the in-cell evaluation grid | — |
| `cell-c<card>-yield-<pid>` | GPU memory floor, re-checked every 20 s for the cell's whole life | **yes**, via the sentinel |
| `cell-c<card>-disk-<pid>` | disk headroom against **this cell's own floor**, every 60 s | **yes**, via the sentinel |
| `cell-c<card>-exclusivity-<pid>` | counts foreign processes on the card | no — it only reports |
| `self-vram-cap.sh` (host, optional) | stops **our** container if **our** usage crosses a cap | yes, by name |

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
a cell, about 17 hours against 45 minutes of training for an on-policy family — neither the sentinel
poller nor the stall watchdog is active. A grid that hangs will not be killed by the cell itself.
That is what the reaper in `launch-card-cell.sh` and your own monitor are for; it is also why the
watch budget must cover training **plus** evaluation, and why §3b treats the wall-clock ceiling as
required rather than advisory.

Evidence:
[`results/evidence/only-a-training-cell-obeys-the-sentinel`](../results/evidence/only-a-training-cell-obeys-the-sentinel/CLAIM.md).

## 7. Watching a run, and the traps that make a monitor lie

Full detail in procedure §9.5; the complete tool list is §10.4. What you actually reach for:

| What you want to know | Tool | Runs on |
|---|---|---|
| is the cell alive, progressing, and is the card/disk safe | `datasphere/native/prod-monitor-laptop.sh` | **laptop**, against the host over ssh |
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

1. **A cell stopped mid-grid never writes `result.tgz`.** Collect it with
   `assemble_reaped_delivery.py` into `<run-dir>/native-out/records_delivery.jsonl` — that exact
   path — then `NATIVE_ACCEPT_WATCH_STOP=1 bash collect-host-run.sh …`. The collector prints this
   recipe in its own refusal message; read the stderr rather than guessing.
2. **Never run `populate_evaluator_ledger.py` on a production run.** That script records a
   family's *evaluator attestation*, and the gate accepts only single-scope endpoint evidence
   (one frame, one policy pass) such as an `attest-v2xx` job. A production delivery has a twelve-frame
   curve and a two-pass endpoint, so it can never qualify — and because every run **replaces** the
   family's entry, writing one **removes a valid attestation with no error**. It silently
   un-validated three families before being caught. The script now refuses using the gate's own
   check; do not work around that refusal.

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

    # 1. Did it stop, and how?            (nothing, FAILED, YIELDED or COMPLETED)
    grep -aoE 'NATIVE_CELL_(COMPLETED|FAILED|YIELDED)' "$LOG" | tail -1

    # 2. WHY did it stop? The marker never says. The sentinel does.
    cat "$RUN/native-work/yield.sentinel"

    # 3. Is it actually dead, or just quiet?
    docker ps --format '{{.Names}}' | grep -E '^cell-c1-[0-9]+$'
    docker stats --no-stream <cell-container>        # ~100% CPU means working, not stalled

    # 4. What survived?
    ls "$RUN/native-out/cells/<cell>/checkpoints/"        # only after training COMPLETED
    ls "$RUN/native-work/runs/<cell>/cell/"*.pt           # while training, or if it stopped early
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

Further reading, in order of usefulness during an incident:
`production-host/15-what-fails-when.md` (symptom → cause), `model/STOP-MECHANISMS.md` (every stop
mechanism and which actually fire), `DECISIONS-IF-PRODUCTION-GOES-WRONG.md` (decisions already
taken, so you do not re-litigate them at 3 a.m.).

## 11. Honest limits of this document

It maps the path that has actually been run: `idaac`, `ppg` and `ibac_sni` at 600k on this host.
Nine baselines have never completed a production cell here, and three of them (`svea`, `sgqn`,
`soda`) are blocked on the Places365 corpus rather than on compute. `ctrl` has never run at 600k and
does not fit beside its own memory floor on a 32 GiB card. Treat the stages above as verified for the
families that have run and as untested elsewhere — the procedure says which is which, and
`campaign_status.py` will not pretend.
