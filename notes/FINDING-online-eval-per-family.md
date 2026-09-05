# During-training evaluation, per family — what runs, what's suppressed, and why it's safe

Written 2026-09-05 answering directly: "if we have or don't have during-training eval for each of
the 12 and how it impacts sturdiness against bugs." Traced every mechanism end to end rather than
trusting the `families.json` field names — one self-caught false alarm along the way (my first pass
missed that `dmc_gb` has the same protection as `rlvigen`, from checking the wrong dict path).

## The risk this is actually about

Door placement is seeded from **global** NumPy state (C69). If a periodic online-eval call resets
an env or samples an action mid-training, it can consume RNG draws the training trajectory would
otherwise have used — silently making a run's later frames different from what the exact same job
would have produced without the eval call. That is the failure class every mechanism below exists
to prevent, and it is a real one: it is exactly why `NATIVE_ISOLATE_ONLINE_EVAL` and the
`2147483647`-sentinel both exist as named, tested mechanisms rather than an afterthought.

## The seven families, verified individually

| family | online eval exists? | production behavior | mechanism | verified how |
|---|---|---|---|---|
| `rlvigen` (5) | yes, periodic | **suppressed** | `eval_every_frames=2147483647` (a sentinel past any real budget), set when `NATIVE_DISABLE_ONLINE_EVAL=1` | `run_probe.sh:722-724`, `family.py`'s `has_eval_option` check |
| `dmc_gb` (rad, soda) | yes, periodic, 2 regimes | **suppressed** | same sentinel mechanism, `--eval_freq 2147483647` | confirmed `{eval_every}` IS a template placeholder in `families.json`'s dmc_gb options (a first check of mine missed this — corrected before writing this file) |
| `alda` | yes, periodic, richest of the 12 (train/eval-easy/eval-hard) | **suppressed** | same sentinel mechanism via `--spec.trainer.config.eval_n_steps={eval_every}` | confirmed template placeholder present |
| `idaac` | yes, periodic (every `log_interval=25` updates) | **RUNS, RNG-isolated** | `NATIVE_ISOLATE_ONLINE_EVAL=1` -> `_evaluate_without_training_rng` saves numpy/python/torch/cuda RNG state, calls `evaluate()`, restores all four in a `finally` block | read the full save/restore implementation directly, `train.py:26-45` |
| `ctrl` | yes, continuous (steps both `env_test_ID` and `env_test_OOD` every training step) | **RUNS, partially RNG-isolated** | `NATIVE_ISOLATE_ONLINE_EVAL=1`; restores NumPy physical state but not the JAX policy PRNG stream | already reviewed (review 14 section 11), accepted as source-style behavior rather than a blocker, **not re-litigated here** |
| `ibac_sni` | **no** — upstream ships evaluation as a separate script by design | n/a | n/a | `production.training_time_eval` states this explicitly |
| `ppg` | **no** — `train.py` has no eval call, no test env, no cadence at all | n/a | n/a | `production.training_time_eval` states this explicitly |

## Why idaac's and ctrl's approach is better where it's available

Suppressing eval (rlvigen/dmc_gb/alda) trades away real diagnostic value: no in-loop generalization
signal until the offline grid runs, and no cheap early warning if a run has gone visibly wrong.
Isolating eval (idaac/ctrl) keeps that signal AND the RNG guarantee — strictly better where the
isolation is actually complete (idaac). ctrl's is knowingly partial, and that gap is already
tracked, not new.

**Why rlvigen/dmc_gb/alda don't use isolation instead of suppression**: unclear from the code
whether it was considered and rejected, or simply not needed given RL-ViGen's checkpoint-based
offline grid already covers the same regimes at higher fidelity (more episodes, all scenes). Worth
a one-line question to whoever owns that choice next, not worth guessing at here.

## What this means for "sturdiness against bugs"

None of the three suppressed families lose diagnostic depth they'd otherwise have and don't already
get elsewhere: their training-time richness comes from `train/*` loss/Q/entropy logging (verified
family-by-family this session, including the RAD/SODA gap just fixed), not from periodic eval. The
offline 50k-stamp curve is what would catch a mid-run divergence for these three, at higher latency
(one stamp interval, not every eval_freq) but no lower fidelity. `scripts/watch_divergence.py`
(added to `PRODUCTION-RUNBOOK.md` this session) is the tool that closes the remaining latency gap
for NaN-shaped divergence specifically.

---

## Addendum 2026-09-05 (same day, later) — the "don't drop the expensive trajectory" property, traced end to end

Answering directly: "not dropping the whole expensive trajectory over a small bug and making it
sturdy against bugs." Traced the actual failure-containment granularity at every layer, not just
the ones already found tonight (the manifest completion-marker fix, CORRECTIONS #65).

**Per-episode/scene, inside one stamp's evaluation** — `scripts/eval_grid.py`'s regime x scene loop
calls `emit(record(...))` once per scene, and `emit()` writes+flushes to the JSONL sink
IMMEDIATELY (`buffering=1`), with the file's own design comment stating the property directly:
*"Streamed, not buffered... an interrupted run kept nothing it had already measured... the file is
therefore always a valid prefix of the full grid."* If scene 3 of 10 crashes, scenes 0-2's records
are already durable; only 3-9 are lost — for that one stamp, not the cell.

**Per-stamp, inside one cell's curve evaluation** — `run_curve_eval` (`run_probe.sh`) does not stop
its loop on a stamp's nonzero exit; it counts the failure and continues to the next stamp
(`CORRECTIONS`-adjacent fix, T6/Codex Q10). A failed stamp is reported (`NATIVE_CURVE_EVAL_PARTIAL`)
rather than silently absent.

**Per-job, at the final archive** — `tar -czf "$result" ...` runs UNCONDITIONALLY before the
job's own exit-code check, with the reasoning stated directly in the script: *"archive first, then
fail. The evidence for the baselines that did run is exactly what the next decision needs."* A
failed job still returns everything it computed.

**All three layers share one design principle, applied consistently rather than once**: a failure
downstream must never retroactively invalidate or discard data already durably written upstream.
Combined with tonight's manifest fix (a failed CELL's record can no longer claim COMPLETED), the
full chain from one episode up to one job is now coherently fail-safe in the same direction at
every level checked.
