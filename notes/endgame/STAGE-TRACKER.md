# Stage tracker — what must be true, and what I actually know

Two axes deliberately. **Top-down** is what would have to hold for the end goal to be reached,
derived from the goal rather than from what happens to be done. **Bottom-up** is what I have
verified, with how. They are kept apart so that "lots of work happened" can never be mistaken for
"the thing is true".

**The end goal**, restated so the decomposition can be checked against it: run the 12 baselines on
RL-ViGen Door and obtain genuinely same-axes measurements, good enough to say which setups
(ports and adaptations alike) succeeded or failed, on a best-effort basis.

Status key: **HELD** (verified this session, with the check named) · **INHERITED** (verified by
prior work I have not re-derived; a re-check is a decision, not an oversight) · **PARTIAL** ·
**OPEN** · **NOT STARTED**.

---

## Stage 1 — are the algorithms in `runnable/` valid?

**What must be true:** each baseline is either the upstream code or an adaptation whose every
deviation is deliberate, recorded, and bounded; and no hardware-dependent setting (batch, norm
groups, clip, process count) has silently moved a deviation past its bound.

| element | status | basis |
|---|---|---|
| deviations enumerated and classified | **INHERITED** | `docs/FAITHFULNESS.md`, `notes/faithfulness-reconciliation.md`, patch classes PLATFORM/RESTORES/ENABLES visible in every cell log ("29 already present, 0 unresolved") |
| deviation review closed | **INHERITED** | five external reviews triaged; `notes/external-review-triage.md`, `review-4-5-triage.md` |
| hardware-dependent settings do not breach a deviation bound | **HELD** | Checked 2026-09-15. Exactly TWO constants move with host profile, and both move TOWARD upstream. See below. |

### The hardware-vs-fidelity interaction, checked

Enumerated by resolving every family's `constants` under both profiles and diffing. Only two keys
differ anywhere:

| family | key | datasphere | v100 | what the descriptor says |
|---|---|---|---|---|
| `ctrl` | `num_envs` | 16 | **64** | *"the upstream 64-env rollout ... Restore the author's parallelism on the host with enough RAM; DataSphere remains at 16 because its 27 GiB usable envelope cannot hold the estimate"* |
| `ibac_sni` | `procs` | 1 | **16** | *"Use the upstream IBAC-SNI process count after the Door-specific spawn/factory repair"* |

`n_steps`, `n_minibatch`, `n_minibatch_ctrl` and `frames_per_proc` are FIXED across profiles, so the
effective batch does scale -- 4x for ctrl, 16x for ibac_sni -- with nothing compensating. **That
scaling restores upstream rather than departing from it.** The deviation was the small-envelope
DataSphere setting; the production host is the faithful configuration. I nearly filed this as a
risk, which is the failure the owner warned about: a parameter that looks wrong alone and is right
in combination.

**One residual, and it is real.** `ctrl` at the v100 profile is modelled at `cell_ram_gib 54.28` by
the descriptor's own words "linear extrapolation of the measured 13.57 GiB 16-env peak to 64 envs;
direct V100 measurement still required", and at 64 envs it takes ~31 GB of a 32 GB card, which is
why v212 deliberately ran ctrl at the DATASPHERE profile. So ctrl is the one family where fidelity
(64 envs) and runnability (16 envs) currently disagree, and the disagreement is unmeasured. Any
ctrl production number must state which profile produced it.

**I am not re-deriving stage 1.** Prior work did it and the project has been bitten by an agent
"finding" a wrong parameter that was right in combination. The one thing I would add is the OPEN
row above, because it is about the *interaction* of fidelity with host settings, which is exactly
what a per-parameter review does not see.

## Stage 2 — is the train/eval harness understood end to end?

| element | status | basis |
|---|---|---|
| execution order | **HELD** | `run_probe.sh:506-538`: train (blocking) → `verify_final_evaluation` → `retain` → `check-finite` → curve → endpoint → retract. All eval is post-training and sequential. |
| online eval is off, and why | **HELD** | `eval_every=None` for all 7 families; reason recorded in `families.json`: online eval consumes Door's global placement RNG |
| durability of artifacts | **HELD** | `/tmp/native-out` and `/tmp/native-work` both bind-mounted (`run_on_production_host.sh:774-775`); history of the 27-hour loss recorded at :604 |
| what "collection" is | **HELD** | delivery is written by the cell to the mounted volume; collection is a copy into `results/records/` plus `populate_evaluator_ledger.py`, which refuses a stale closure |
| checkpoint stamping | **HELD** | frame-keyed for 6 families; ppg is save-index keyed and mapped via the log's authoritative `IC=`; `NATIVE_CURVE_EVAL_SKIPPED` has never fired |
| eval determinism | **HELD, and NOT what was assumed** | two identical invocations differ by 0.095 SE; `seed_episode_placement` re-seeds numpy/random but not torch. See `RESOLVED-ppg-reeval-is-within-evaluator-noise.md` |
| a written clean model of the whole pipeline | **NOT STARTED** | this table is an index, not the model the owner asked for |

## Stage 3 — will a long run succeed?

Four defects found today, all of which would have damaged a production run:

| defect | status | consequence if unfixed |
|---|---|---|
| watch budget sized from host defaults, 11x low | **HELD (fixed)** | 15 of 36 cells reaped mid-eval; a reaped cell never reaches delivery |
| preflight could never read card 1 | **HELD (fixed)** | no cell could ever start on card 1 |
| `neighbour-yield.sh` hardcoded `cell-c0-` | **HELD (fixed)** | card-1 cells ran with NO process yield; found live, one hour in |
| `cell-c1-yield-*` container vanished mid-run | **OPEN** | the memory-floor yield is currently unexplained-absent on a running cell |
| VRAM cap does not bind (`PYTHONPATH` overwritten) | **INHERITED, still true** | our footprint is unbounded; hence no co-occupancy |
| no timer may fire without notice | **PARTIAL** | `cell-heartbeat.sh` warns before the budget ends a cell; the watches still kill without warning |

## Stage 4 — hardware packing

| element | status | basis |
|---|---|---|
| campaign does not fit the window | **HELD** | 800.9 job-hours = 33.4 card-days against ~2.7 card-days of booking |
| triage: evaluation of banked checkpoints beats new training | **HELD** | two 600k runs already trained; ppg's 14 checkpoints sha-verified |
| use published RL-ViGen numbers to skip baselines | **NOT STARTED** | `notes/rlvigen-published-door-anchor.md` exists; whether any baseline can be reported from it rather than run is unexamined |
| which baselines are VRAM-lean enough to pack two per card | **NOT STARTED** | and blocked by the unbound VRAM cap above |

## Stage 5 — submit

| element | status |
|---|---|
| ppg endpoint grid running on card 1 | **IN PROGRESS** (started 15:59:58 MSK, ~5.7 h) |
| idaac's 3 missing eval-hard mode rows | NOT STARTED |
| ppg curve pass | NOT STARTED |
| monitoring that speaks on failure | **HELD** — `cell-heartbeat.sh`, `gpu-occupancy-log.sh`, both detached and writing their own files |

---

## What I am least sure of, in order

1. **Stage 1's OPEN row.** Hardware-dependent settings interacting with fidelity bounds. Not
   checked, and not checkable by re-reading a parameter table.
2. **The vanished yield container.** An unexplained disappearance of a safety component during a
   live run is worse than a known absence.
3. **Stage 2's missing clean model.** Everything above is traced but scattered; the model the owner
   asked for does not exist yet, so "I understand the harness" rests on my memory of today rather
   than on a document anyone can check.
4. **Stage 4's unexamined half.** We may be about to spend the last of a booking on runs that a
   published number could have supplied.
