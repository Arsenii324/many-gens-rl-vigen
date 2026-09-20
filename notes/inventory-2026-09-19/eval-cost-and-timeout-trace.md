> **Executor output, not a finding of record.** Produced 2026-09-20 by a read-only Sonnet executor, by reading code only. Re-checked by the lead in the code: the pooled scene-set row is `np.concatenate` of already-executed per-scene results (`scripts/eval_grid.py:1305`) and costs no rollouts; every `run_scene_*` calls `seed_the_placement_rng`, which resets `random`, `numpy` and `torch` absolutely (`:217-223`); the launcher's own comment records the measured `idaac` cell at 4.95 h training, 4.60 h curve evaluation, 5.52 h endpoint grid (`launch-card-cell.sh:98-105`). Not re-checked: the timeout control flow (Part 2) and the `ctrl` in-loop evaluation reading (1e).

# Evaluation cost and training-timeout trace

READ-ONLY. Nothing executed, nothing edited.

## NOT CHECKED / limits
- Did not read `scripts/eval_grid.py`'s per-family `run_scene_*` bodies beyond idaac's (in full) and
  a structural skim of the other five (dmc_gb, ppg, ibac_sni, alda, ctrl) for env-construction
  placement and `seed_the_placement_rng` call sites — confirmed call sites by line number, not full
  bodies.
- Did not read `runnable/ctrl/algo.py`, `buffer.py`, `vec_env.py`, `evaluate_ppo.py` — only
  `train_ppo.py`'s `main()` loop (lines 160-470ish).
- Did not read `notes/EVALUATOR-THROUGHPUT.md` end-to-end (400 lines) — read headers + the final
  ~50 lines (conclusion) + two "ANSWERED"/"cost model closes" sections via targeted grep.
- Did not open `notes/model/HARNESS-MODEL.md` outside §§0-4 (read those four sections).
- Did not verify empirically (cannot, read-only) whether GNU `time -v`'s wrapped-`timeout` exit
  reporting behaves as I describe (no "terminated by signal" line for a plain 124 exit) against a
  real run; I found no repo comment or test asserting this directly for the `time -v timeout`
  combination specifically, only inferred it from reading the two programs' documented behavior and
  the absence of any "124" or "NATIVE_CELL_TIMEOUT" string anywhere in `run_probe.sh` (grep, whole
  file, 0 hits beyond the two already-known lines that set up the timeout).
- `production-schedule.json`'s `solo_hours_per_seed_gt4_1` field (used by the new v5/v6 guard) was
  read only via the test file's docstring and the embedded schedule table in v5.sh; I did not
  independently open and print the full JSON field list for `production-schedule.json` in this task
  (I did for `production-schedule-v100.json`).

---

## PART 1

### 1a. Episode-count decomposition

| factor | value | file:line | stated reason |
|---|---|---|---|
| regimes | 4 (`train,eval-easy,eval-medium,eval-hard`) | `families.json:442` (idaac; identical string in every family's `production.offline_eval_regimes`, confirmed by grep across the whole file) | none given at the descriptor; `docs/EVAL-PROTOCOL.md:38` states it's "the full endpoint specification" |
| scenes | 10 declared + 1 pooled = 11 "scene sets" | `families.json:443-453` (`offline_eval_scenes: [0..9]`) | pooled row is emitted by `eval_grid.py:1305-1311` — see below |
| endpoint episodes/scene | 20 | `families.json:455` | `docs/EVAL-PROTOCOL.md:38`, cost-vs-precision (1f) |
| curve episodes/scene | 3 | `families.json:456` | `notes/DECISION-SHEET.md:945` "A20 DECIDED, 2026-09-05 — 3 episodes per stamp" (1f) |
| curve regimes/scenes | **same as endpoint** (4 regimes, 10+1 scenes) — no family declares its own `curve_eval_regimes`/`curve_eval_scenes` | `family.py:711-721` (`production_env()`: `curve_value = settings.get(f"curve_eval_{axis}", endpoint_value)`); confirmed no family overrides it (`grep '"curve_eval_regimes"\|"curve_eval_scenes"' families.json` → 0 hits) | none stated; the mechanism defaults curve to endpoint's axis unless told otherwise |
| policy-mode passes | 2 ("native,mode") **only for idaac, ppg, ibac_sni** | `family.py:709-710` (`if FAMILY_EVAL_POLICY_MODE.get(family) == "sample": out["ENDPOINT_EVAL_POLICY_MODES"] = "native,mode"`) | comment at `family.py:686-703`: a second deterministic pass "for the four families whose native reporting path SAMPLES" (now three, since ctrl moved to `mode`) — the two passes ARE genuinely different rollouts for these three (native = `model.act(obs)` without `deterministic=True`, i.e. sampled; `mode` = deterministic/argmax). For every other family the condition is false and only ONE pass runs — **no family gets a redundant duplicate pass** |
| stamps | 13 (theoretical, every 50k of 600k) / **11 measured** on the cited real idaac cell | `launch-card-cell.sh:128` ("13 stamps"); `launch-card-cell.sh:102-105` (measured idaac cell: "11 checkpoints") | 50k save cadence is `train.py:309`'s hardcoded `global_step % int(5e4)`, per `notes/DECISION-SHEET.md`'s A20 table row "frequency ... not free" |
| **the pooled scene-set row** | **recomputed from already-executed per-scene episodes; costs ZERO new rollouts** | `scripts/eval_grid.py:1178` (`for scene in scenes:` — the real rollout loop, calls `run_scene_*`), `:1252` (`per_scene[scene] = np.asarray(returns, ...)` — stores the already-executed per-scene array), `:1305` (`pooled = np.concatenate([per_scene[s] for s in scenes])` — pure numpy concatenation of the SAME arrays), `:1311` (emits the pooled row) | confirmed by reading the loop: the pooled emit happens AFTER the per-scene loop completes, using its saved outputs, with no intervening call to any `run_scene_*` function |

**Correction to the "3,476 episodes" figure** (`notes/model/HARNESS-MODEL.md:193`, `launch-card-cell.sh:128-130`, both say the same number): since the pooled row is free, the REAL rollout count is 10/11 of the naive "44 rows × episodes" arithmetic, not 11/11. Naive: curve `13 × 44 × 3 = 1,716`, endpoint `44 × 20 × 2 = 1,760`, total 3,476. Real rollouts: curve `13 × 40 × 3 = 1,560`, endpoint `40 × 20 × 2 = 1,600`, total **3,160** — about 9% fewer actual episodes than the documented figure, because 4 of the 44 "rows" per pass are arithmetic, not rollouts.

**A second, unreconciled arithmetic disagreement, found by reading the source, not trusting it:**
`launch-card-cell.sh:100-105` states, from the SAME measured idaac cell: "curve evaluation 4.60 h ... 1,452 episodes" and "endpoint grid 5.52 h ... 1,760 episodes", "evaluation total 10.12 h". Two lines later (`:127-130`), the SAME comment block gives the GENERIC formula for a full 13-stamp cell as "3,476 episodes (17.4 h)". But `:115` states both phases cost "11.4 s curve, 11.2 s episode" — and 3,476 × ~11.3s ≈ 39,300s ≈ **10.9 h**, not 17.4h. I could not find where 17.4h comes from arithmetically inside this file; I present it as written and flag the inconsistency rather than resolve it.

**Episode horizon:** Door = **500 steps**, `action_repeat=1`. `RL-ViGen-upstream/envs/robosuiteVGB/robosuitevgb/cfg/robo_config.yaml` (`task_def.horizon: 500`, confirmed by direct read); `families.json` Table-2-sourced `action_repeat` constant (Robosuite: 1) cross-referenced in the prior budget-research task's Part C. 500 real physics/render steps per episode, uniformly (per `docs/CONSTRUCTION.md:3522`: "Door has a fixed 500-step horizon", "no early termination").

### 1b. Per-episode cost structure

`eval_grid.py`'s `main()` (idaac path, representative — checkpoint load ~`:229-243`, once) → `_run_grid()` (`:1148`) →
`for regime in regimes:` (`:1175`) → `for scene in scenes:` (`:1178`) → `run_scene_idaac(...)` (per-scene call)
→ inside it: `seed_the_placement_rng(seed)` (`:495`, resets numpy/random/torch RNG), THEN
`envs = make_rlvigen_venv(args, device, mode, 1, scene_id=scene_id)` (`:521`, **env construction happens
here — once per scene**, not once per episode, not once per invocation) → an internal episode loop
(inside `run_scene_idaac`, not shown above but confirmed present by the function's `episodes` parameter
and `close_eval_env(envs)` at `:571` closing it only after all episodes for that scene finish).

- **Checkpoint/agent loading: once per eval_grid.py process** (i.e. once per curve stamp, once per
  endpoint policy-mode pass) — `main()`'s `torch.load`/family-specific loader runs before `_run_grid`
  is ever called (`:229-243`), and the SAME `agent` object is reused across all 4×10 scene calls.
- **Environment construction: once per (regime, scene) — 40 times per invocation** (`eval_grid.py:521`
  for idaac; same pattern confirmed structurally for dmc_gb `:397`, ppg `:672`, ibac_sni `:781`,
  alda `:911`, ctrl `:1089` — each `run_scene_*` builds its own env near its own top and calls
  `close_eval_env` near its own bottom). Measured construction cost: **0.6 s** — `notes/DECISION-SHEET.md:947`
  ("It has been measured: 0.6 s, i.e. 3.4 GPU-h across all 20,160 constructions in the campaign") and
  `notes/EVALUATOR-THROUGHPUT.md:191` ("construction 0.6s, episode ~12s").
- **eval_grid.py process (python startup) frequency:** once per curve **stamp** (`run_probe.sh`'s
  `run_curve_eval`, looping stamps, one `python3 scripts/eval_grid.py` call per stamp) and once per
  endpoint **policy-mode pass** (`run_endpoint_eval`'s `for policy_mode in "${mode_list[@]}"` loop) —
  NOT once per regime, NOT once per row. `--regimes`/`--scenes` are passed as multi-value CSV to a
  single process that loops both internally.
- **Per-episode rate, three slightly different measured numbers across three documents:**
  `notes/EVALUATOR-THROUGHPUT.md:159,191` — "**~12 s/episode**" (dated 2026-09-05, the original
  measurement); `launch-card-cell.sh:115` — "**11.4 s curve, 11.2 s endpoint**" (measured on the idaac
  600k cell, later, `:95` "2026-09-09"); `notes/model/HARNESS-MODEL.md:194` — "**11.65 s/episode**"
  (a single blended constant). All three agree to within ~5% but are not the same number; I did not
  reconcile them.

### 1c. Parallelism facts

- **No multiprocessing/worker-pool inside `eval_grid.py` or `run_probe.sh`'s curve/endpoint
  functions.** Grepped both files for `device`/`multiprocessing`/`Pool`/`worker` — the only
  device-related knobs are `--device` (single CUDA device string, `eval_grid.py:1361`) and
  `OFFLINE_EVAL_DEVICES`/`ENDPOINT_EVAL_DEVICE`/`CURVE_EVAL_DEVICE` in `run_probe.sh`. Reading
  `run_probe.sh:1320,1343`, `OFFLINE_EVAL_DEVICES` (plural, only in the separate `run_offline_eval`
  diagnostic path, not the production curve/endpoint path) **repeats the whole grid once per listed
  device sequentially, for cross-device verification** — comment: "runs the same grid once per device
  inside ONE job" — this is a correctness cross-check, not a speedup mechanism.
- **Real, already-built, host-level parallelism exists, but outside the live production path.**
  `datasphere/native/host-scripts/curve-sweep-v3.sh` (full read) launches up to `MAXCELLS` (default
  **6**, `:23`) separate DOCKER CONTAINERS concurrently, each running one `reeval-cell-cached.sh` →
  one `eval_grid.py` process for one stamp, gated by a live re-check of running-container count, free
  VRAM, and free disk before each launch (`:46-53`), spaced 90s apart (`:71`). Own comment (`:8-10`):
  "one eval cell uses 101% CPU (one core), 841 MiB of VRAM and 2.1 GiB of RAM, on a 16-core node...
  Running them one at a time would spend the booking at a sixteenth of the machine." This tool is
  classified REFERENCED-not-LIVE in the prior inventory task (a standalone re-evaluation script, not
  wired into `run_probe.sh`'s in-container sequential curve/endpoint calls).
- **Row independence, confirmed in code.** `eval_grid.py:192-227` (`seed_the_placement_rng`) is called
  at the top of every `run_scene_*` function (`:392,495,668,765,904,1058` — one call site per family),
  always with the SAME argument (`a.episode_seed`, a single CLI constant for the whole invocation), and
  it does `_random.seed`, `_np.random.seed`, and `_torch.manual_seed` — all ABSOLUTE resets, not
  increments. Per-episode PLACEMENT is separately re-seeded by `seed_episode_placement` (`:236-241`,
  `SeedSequence([eval_seed, scene_id, episode_index])`, `:230-233` docstring: "Stable per-episode seed,
  independent of family-specific construction/reset machinery"), confirming door placement is
  content-addressed and does not depend on call order.
- **The one caveat, as the task named it, quoted and checked against the code:**
  `notes/model/HARNESS-MODEL.md:174-177`: "**torch is NOT re-seeded per episode.** It is seeded once at
  family setup (`eval_grid.py:221`). For the three SAMPLING baselines (idaac, ppg, ibac_sni) the action
  stream therefore depends on how much torch RNG was consumed before a cell." Reading the code: torch
  IS reset (via the same `seed_the_placement_rng` call) at the start of **every row** (every scene),
  not merely once for the whole invocation — so between ROWS, torch's RNG is not accumulating; within a
  ROW's own multi-episode loop (`episodes` count executed inside one `run_scene_*` call), only
  PLACEMENT is reseeded per episode, and torch is not — so episode *i*'s sampled action, for a sampling
  family, depends on episodes 0..i-1 of the SAME row having already consumed RNG state. I present both:
  the note's own framing ("once at family setup") and my reading (reset per row, not per episode within
  a row) without deciding which framing the lead should adopt; the measured empirical consequence is
  real either way — `notes/model/HARNESS-MODEL.md:176-177`: "two byte-identical invocations gave
  25.794515705108644 and 26.052958893775940 — a spread of **0.095 SE** at n=20."
- **Conclusion on splitting work across N workers:** since every ROW (regime, scene) resets its RNGs
  absolutely and independently of call order, **N worker processes could run disjoint ROW subsets
  against the same checkpoint and reproduce each row's PLACEMENT deterministically for every family**,
  and would reproduce the ACTIONS deterministically too for the 9 "mode"/deterministic-estimand
  families (no torch sampling involved). **What breaks for the 3 sampling families (idaac, ppg,
  ibac_sni) is not row-splitting itself, but reproducing a SPECIFIC PRIOR ordering** — if a row is
  re-run alone vs. as the Nth row of a longer sequential run in the same process, its own internal
  episode-to-episode action stream is unaffected (each row always starts its own local episode loop
  from the same freshly-reset torch state, per row, regardless of what ran before it in the same
  process) — so by my reading, row-level splitting across workers should not change the SAMPLED
  actions either, since each row already fully re-seeds torch before it runs. I flag this as a
  disagreement with HARNESS-MODEL's stated mechanism (which frames the exposure as "before a cell",
  i.e. across the whole grid) rather than resolve it myself, and note the measured spread is real
  regardless of which framing is right.

### 1d. Could curve stamps evaluate while training continues?

No — by control flow, not by a stated policy. `run_measured()` (`run_probe.sh:67-291`) launches
training in the background, and **blocks**: `wait "$training_pid"` at `:235` does not return until the
training process group has fully exited. `run_one_cell`'s call to `run_measured` (`:506-508`) is
followed, strictly sequentially with `|| return 1` gates and no `&` backgrounding anywhere in between,
by: `expected_endpoint` computation (`:513-514`), `verify_final_evaluation` (`:514`), `retain` (`:516-518`),
`check-finite` (`:522-523`), then (only if `CURVE_EVAL=1`) `run_curve_eval_with_policy` (`:524`), then
(only if `ENDPOINT_EVAL=1`) `run_endpoint_eval` (`:534`). This is one bash script executing top to
bottom in one process; nothing forks the evaluation phase to run concurrently with a still-running
training subprocess.

### 1e. CTRL's in-training evaluation

`runnable/ctrl/train_ppo.py:185-186`: `env_test_ID = _mk("train", num_levels=200, start_level=0)` and
`env_test_OOD = _mk("eval-easy", num_levels=0, start_level=0)` — both constructed at
`num_envs=FLAGS.num_envs` (default **64**, `:114`), i.e. the same vectorised width as the training env.
Stepped every training iteration: `:301` `for step in range(1, int(FLAGS.train_steps // FLAGS.num_envs + 1)):`,
`:318` `state_id, _, _, infos_id = env_test_ID.step(action_id)`, `:327`
`state_ood, _, _, infos_ood = env_test_OOD.step(action_ood)`. Own comment, `:305-307`: "The test envs
are part of CTRL's original progress reporting, but their Door resets use the process-global NumPy
placement stream. In production, preserve the training stream around these steps so changing the
reporting cadence cannot change later train scenes."

**What the statistics feed into: logging only.** `infos_id`/`infos_ood` populate `succ_id`/`succ_ood`
and two `deque(maxlen=100)` buffers (`epinfo_buf_id`, `epinfo_buf_ood`, `:286-287,294-295,332-346`),
which are read only inside a `print`/`wandb.log`-style block at `:402-422` (`safe_mean(...)` calls).
The actual training update (`update_ppo`/`update_daac`/`update_cluster`, `:349-370`) consumes `batch`,
which is filled exclusively by `get_transition(train_state, model.ac, env, state, batch, key)` at
`:302-303` using the MAIN training env `env` — never `env_test_ID`/`env_test_OOD`. Checkpoint saving
(`:439-443`) is gated only on `FLAGS.checkpoint_interval` and frame count, not on the test-env buffers.
**No upstream flag disables or thins this.** Full `flags.DEFINE_*` list read (`:112-159`) — no
eval-interval/disable-eval/test-env flag exists; the test envs are unconditionally constructed and
stepped every iteration, tied only to `num_envs` and the loop's own cadence.

### 1f. Statistical precision target

- `docs/EVAL-PROTOCOL.md:38`: "**3 per scene at each 50k trajectory stamp; 20 per scene at the
  endpoint.** Per-scene and per-episode rows are retained, never only the pooled mean."
- `notes/DECISION-SHEET.md:503-594` (A20, then revised, then restated 2026-09-05): the ORIGINAL
  recommendation was **5** episodes/stamp (`:576-598`, table: "episode length | 500 steps | not free";
  "episodes per (regime,scene) per stamp | 5 | the only free parameter"), costed at "288 GPU-h if
  construction is free, 384 GPU-h at 40s per construction... not yet measured".
- `notes/DECISION-SHEET.md:945-972` ("A20 DECIDED, 2026-09-05 — 3 episodes per stamp", the number
  actually shipped): construction was then measured at **0.6s** ("3.4 GPU-h across all 20,160
  constructions"), collapsing the two-term uncertainty; formula given: `per cell = 12 stamps × 4
  regimes × 10 scenes × E episodes × 12 s` (note: **12 stamps and 12s/episode here**, slightly
  different from the "13 stamps"/"11.4-11.65s" figures elsewhere — see 1a/1b). Table: E=3 → 173 GPU-h
  (+3.4 construction = 176 total) = 29% of the 601h training budget, "30 episodes per (stamp, regime)".
  Decision quote: "**Decision: E = 3.**... The curve's job is the shape of learning and a sanity check
  on checkpoint selection. It carries no inferential claim — the headline estimand is the endpoint
  grid, which stays at 20 episodes per (regime, scene)."
- `notes/retention-and-eval-depth.md:4-8` (self-correcting banner at the top of the file): "Section 1's
  recommendation of **5 episodes per intermediate stamp is not what ships.** **A20 decided three**,
  2026-09-05, and `families.json`'s `curve_eval_episodes: 3` is what every production cell runs...
  This note is kept for the **cost shape**... its specific 5-episode figure is not [what ships]."
- `notes/EVALUATOR-THROUGHPUT.md` (400 lines; NOT a duplicate of the above — it is primarily about
  **evaluator determinism/reproducibility**, not episode-count precision). Dated across 2026-09-05
  (multiple same-day revisions, including a retraction of its own opening claim). What it measured and
  concluded, in order: (1) an earlier "the shared evaluator got ~4x slower" claim was **withdrawn**
  (`:3-5`, "inferred from a job with no logs... do not support it"); (2) determinism (`torch.use_deterministic_algorithms`)
  "is essentially free" in wall-clock cost, throughput ~12s/episode either way (`:159-191`); (3) an
  A/B with both arms instrumented showed determinism "costs NOTHING" in time but "**changes the
  NUMBERS**" (headers `:228,259`); (4) **the reproducibility test FAILS**: even with determinism on,
  re-running the identical config does not reproduce byte-identical results in general (`:301`); (5)
  measured variance, 4 replicates of one config: `eval-easy`/scene 0 was byte-identical across all 4
  runs (spread 0.0000), but `train`/scene 0 spread was **0.1165** on a mean of ~15.1 (**0.77% of the
  cell mean, on 5 episodes**) — "the instability is episodic, not per-run noise... three of the four
  runs agree exactly". Conclusion (last lines): "A discharge comparison on a 5-episode cell must
  tolerate at least 0.12 absolute / ~0.8%... The production endpoint uses 20 episodes... the cell-mean
  tolerance there should be smaller — but that has not been measured and should not be extrapolated."

---

## PART 2

### 2a. What happens when `timeout --foreground ${CELL_TIMEOUT_SECONDS}s` fires

Built at `run_probe.sh:400-402`: `cell_timeout=(timeout --foreground "${CELL_TIMEOUT_SECONDS}s")`, then
passed into `run_measured "$cell_out" ${time_wrapper[@]} ${cell_timeout[@]} env ${cell_environment[@]}
bash "${argv[@]}" ${extra_overrides[@]}` (`:506-508`) — so the actual process tree is
`/usr/bin/time -v timeout --foreground Ns env VARS... bash <launcher-script> <args>`. `timeout` sends
**SIGTERM** to its child (the `env ... bash ...` launcher) when the deadline passes; `--foreground`
keeps it in the same foreground process group `setsid` already placed the cell in (`run_measured`'s own
`setsid` at `:97/99`), so the signal reaches the actual training process rather than being absorbed by
an extra session layer. `timeout` itself then exits normally with status **124** (it is not itself
killed by a signal).

**No timeout-specific marker exists anywhere in the file** — I grepped `run_probe.sh` for `124`,
`NATIVE_CELL_TIMEOUT`, `NATIVE_CELL_TIMED_OUT`: zero hits beyond the two lines that construct the
`timeout` invocation. `run_measured`'s post-mortem checks, in order (`:271-289`): (1) `NATIVE_CELL_STALLED`
in the log (the SEPARATE stall watchdog's own marker — not this path); (2) `"Command terminated by
signal"` in the log — this is `time -v`'s own text for when **`time`'s direct child** dies by a signal.
Since `time -v`'s direct child here is `timeout` (not the trainer), and `timeout` exits normally with
124 rather than being signaled itself, I could not find where this text would be printed for a plain
timeout — it falls through to (3) `if [[ "$training_status" -ne 0 ]]; then return "$training_status";
fi` (`:287`), returning **124 with no diagnostic line printed by `run_measured` at all**. `run_one_cell`
treats this exactly like any other non-zero return: `run_measured ... || return 1` (`:508`) — a bare
failure, same code path as an OOM, a crash, or any other non-zero exit, with **no distinction recorded
anywhere between "stopped because it was too slow" and "stopped because it was broken"**. I did not
find a caller further up that prints a distinguishing marker for this case either.

**What's left on disk / is it collectable:** checkpoints already retained before the kill remain on the
`/tmp/native-out`/`/tmp/native-work` bind mounts (durable regardless of how the cell died, per
`run_on_production_host.sh`'s own mounting rationale, read in the prior trace task). `retain`,
`check-finite`, `run_curve_eval_with_policy`, `run_endpoint_eval` (`:513-535`) are only reached if
`run_measured` returns 0 — a timeout means these never run, so **no curve/endpoint grid is produced for
a timed-out cell**, only whatever training-log/checkpoint state existed at the moment of the kill.
`collect-host-run.sh` (read in the prior inventory task) does not special-case a timed-out cell either
way — it reads `native-out/records_delivery.jsonl` if present; a timed-out cell that never reached
`normalize_records`/`collect_record_delivery` would leave a missing or incomplete
`records_delivery.jsonl`, and the script's own documented behavior for that case (from the prior
session) is to print `NATIVE_RECORDS_EMPTY` rather than refuse outright.

### 2b. Stall watchdog and reaper

**Stall watchdog** (`run_probe.sh:108-160`, inside `run_measured`, wraps TRAINING ONLY): measures **log
size growth**, not frame count or any semantic progress signal — `size="$(wc -c < "$log")"` every 30s
(`:136-137`); if unchanged for `CELL_STALL_SECONDS` (default **1800**, `:128`) consecutive seconds, it
prints `NATIVE_CELL_STALLED no output for ${quiet}s (limit ${stall_seconds}s)` (`:145`) and kills the
process GROUP (`kill -TERM "-$pgid"`, 20s grace, then `kill -KILL "-$pgid"`, `:146-154`). Own comment
(`:78-91`) documents it depends on `PYTHONUNBUFFERED=1` to be sound at all (block-buffered stdout would
look identical to a hang). **Not active during evaluation**: it is spawned only inside `run_measured`,
and `run_measured` is called for training (`:506`) — curve/endpoint eval (`run_curve_eval`,
`run_endpoint_eval`) invoke `python3 scripts/eval_grid.py` directly with `set +e ... | tee`, no
`run_measured` wrapper, hence no stall watchdog during evaluation.

**Reaper** (`launch-card-cell.sh:372-401`, host-side, wraps the WHOLE container including eval): a
subshell sleeps `WATCH_SECONDS` (the derived total budget), then loops: checks `docker logs --since
"${_stall_window}s" "$CELL_NAME"` for any output (`:379`) — this IS "progress-aware" in the sense the
coordinator asked: it does not kill on schedule alone, it checks for continued container-level log
emission. If the container emitted anything in the last `_stall_window` seconds (default
`NATIVE_REAP_STALL_SECONDS:-900`, `:376`) AND grace remains (`_grace_used < _grace_max`, default
`NATIVE_REAP_MAX_GRACE_SECONDS:-10800` = 3h, `:375`), it grants another `_stall_window` and loops
(`:380-388`); if over budget and genuinely silent, or over budget and out of grace, it stops the
container (`docker stop`, `:397`) with a distinguishing log line for each case (`:389-395`: "STILL
EMITTING" vs "SILENT for ${_stall_window}s"). So the reaper's progress signal is coarser than the
in-container stall watchdog's (any container log output at all, over a 900s window, vs. the
watchdog's 1800s-of-total-silence-in-the-training-log rule) but genuinely distinguishes "still
producing output past budget" from "gone silent past budget", unlike the plain training-side `timeout`.

### 2c. Every timeout/budget default in the chain

| variable | file:line | default | derivation stated? |
|---|---|---|---|
| `CELL_TIMEOUT_SECONDS` (via `TIMEOUT_S`) | `train-production-cell-v5.sh:115` (`${TIMEOUT_S:-43200}`) | 43200 (12h) | **bare number** — but as of `:51-109` (dated **2026-09-20**, today), the wrapper now REFUSES to use this default for any baseline except idaac/ppg/ibac_sni unless `TIMEOUT_S` is passed explicitly, citing `production-schedule.json`'s T4-tier `solo_hours_per_seed_gt4_1` per baseline (embedded table `:73-86`, kept in sync by `tests/test_train_production_cell_timeout.py`) — added directly because "svea launched 2026-09-19 with the 12h default and would have been cut near 430k/600k frames with no warning" (`:64-65`, same file) |
| `CELL_STALL_SECONDS` | `run_probe.sh:128` | 1800 | **derived**: `:118-122` "Longest measured silent phase is the Places365 first load at 561.8s... The 1800s default is 3.2x the longest silence anyone has measured." |
| `NATIVE_BOOTSTRAP_ALLOWANCE_SECONDS` | `launch-card-cell.sh:71,73` | 600 (with `NATIVE_VENV_HOST`) / 9000 (without) | **derived/measured**: `:64-69` "pip ran past two hours on 2026-09-08... With NATIVE_VENV_HOST... only apt, measured at 71 seconds" |
| `NATIVE_WATCH_SLACK_SECONDS` | `launch-card-cell.sh:91` | 900 | bare number, no derivation comment at the assignment site |
| `NATIVE_EVAL_ALLOWANCE_SECONDS` | `launch-card-cell.sh:170` | derived from episode count × seconds/episode × 1.5, or `CELL_TIMEOUT_SECONDS` if larger | **derived** — the whole `:122-173` block computes it from `family.py production-env`'s actual regime/scene/episode counts, explicitly "ASK THE DESCRIPTOR, DO NOT GUESS" (`:123`) |
| `NATIVE_SECONDS_PER_EVAL_EPISODE` | `launch-card-cell.sh:168` | 12 | **measured, stated inline**: "Both evaluation phases cost the same per episode (11.4 s curve, 11.2 s endpoint)" (`:115`, rounded to 12 for the allowance formula) |
| `NATIVE_REAP_STALL_SECONDS` | `launch-card-cell.sh:376` | 900 | bare number at the assignment; the reaper's surrounding comments justify the overall grace MECHANISM (avoiding the wall-clock-kill failure mode) but not this specific number |
| `NATIVE_REAP_MAX_GRACE_SECONDS` | `launch-card-cell.sh:375` | 10800 (3h) | bare number, no derivation given at the site |
| `MUST_COVER` / `WATCH_SECONDS` | `launch-card-cell.sh:174-175` | `CELL_TIMEOUT_SECONDS + EVAL_ALLOWANCE + BOOTSTRAP_ALLOWANCE`, `+ SLACK` | derived (sum of the above) |

### 2d. Does anything warn before a limit is hit?

**No projection mechanism found.** Grepped `run_probe.sh`, `launch-card-cell.sh`, and
`host-scripts/watch-cell.sh` for any computation comparing elapsed time/frames against the remaining
budget; found none. What DOES exist:
- The reaper's own log lines when it grants grace (`launch-card-cell.sh:381-384`, quoted in 2b) —
  these fire only AFTER the budget is already exceeded, not before.
- `train-production-cell-v5.sh:106-108`'s new (2026-09-20) launch-time WARNING — fires once, at
  launch, if `TIMEOUT_S` is explicitly set below the baseline's scheduled T4 time; it does not track
  progress during the run.
- `host-scripts/watch-cell.sh` (full read): its heartbeat line (`:76`, `"HOST $(date +%H:%M) ${CELL}
  curve rows ${cv} endpoint ${ep}+${em} (${age}s) | card1 free ${f1} | disk ${d}GiB | groups: ${h}"`)
  prints **row counts, log-staleness age, free VRAM, free disk** — it does NOT print training frame
  count, FPS, or a projected-finish-vs-limit comparison. Its own stall check (`:71`,
  `[ "$age" -gt 2400 ]`) is a fixed 2400s threshold on log staleness, independent of and different from
  both the in-container watchdog's 1800s and the reaper's 900s — a third, different stall threshold.
  Training logs (per the coordinator's own example, RL-ViGen's `F: ... FPS: ... T: ...` lines) carry
  everything needed to compute a projection, but I found no code anywhere in the chain that reads FPS
  or frame count from the training log to compute one.

### 2e. `production-schedule-v100.json` fields

Full field list per row (`rows[i].keys()`, read directly with Python): `baseline`, `family`,
`requested_frames`, `executed_endpoint`, `seeds`, `runtime_constants`, `runtime_environment`,
`replay_capacity`, `maximum_retained_transitions`, `evicts_before_endpoint`, `save_every_frames`,
`endpoint_eval_episodes`, `curve_eval_episodes`, `offline_eval_regimes`, `offline_eval_scenes`,
`cell_ram_gib_model`, `cell_ram_model_basis`, **`v100_completed_frames_per_second`** (currently `null`
for all 12), **`throughput_source`** (currently `"UNMEASURED_ON_V100"` for all 12),
`t4_completed_frames_per_second_reference`, `t4_reference_basis`. Top-level: `_comment`, `host_profile`,
`resolved_descriptor_sha256`, `host`, `frames` (600000), `seeds` ([101,102,103]), `calendar_status`
(`"BLOCKED_ON_MEASURED_V100_THROUGHPUT"`). So the two fields to write back once a native cell runs to
completion are exactly `v100_completed_frames_per_second` (a number) and `throughput_source` (a string,
presumably `"measured"` once real) — same shape the T4 fields already use, per baseline row.
