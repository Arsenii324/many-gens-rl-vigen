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

Full detail in procedure §9.5. The short version:

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

- Symptom → cause table: procedure §9.4 and `production-host/15-what-fails-when.md`.
- Decisions already made about failure modes: `DECISIONS-IF-PRODUCTION-GOES-WRONG.md`.
- Every stop mechanism, and which ones actually fire: `model/STOP-MECHANISMS.md`.
- A failed attempt is recorded, not discarded: procedure "Recording an attempt that failed before it
  wrote anything", and `scripts/record_host_run.py`.

## 11. Honest limits of this document

It maps the path that has actually been run: `idaac`, `ppg` and `ibac_sni` at 600k on this host.
Nine baselines have never completed a production cell here, and three of them (`svea`, `sgqn`,
`soda`) are blocked on the Places365 corpus rather than on compute. `ctrl` has never run at 600k and
does not fit beside its own memory floor on a 32 GiB card. Treat the stages above as verified for the
families that have run and as untested elsewhere — the procedure says which is which, and
`campaign_status.py` will not pretend.
