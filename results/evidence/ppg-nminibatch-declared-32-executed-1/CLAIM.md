# ppg declared `--nminibatch 32` and executed 1, and the executed policy phase matches PPG's single-rank release

Production run `card0-20260909-115331`, cell `ppg-s1` (600,064 frames, Door, seed 1).

## Status

**Resolved, for the policy phase only.** This is the evidence behind register row `ppg-nminibatch`
(`docs/resolved-register.json`) and commit `237f876`. The auxiliary phase takes a different code
path, and it is **not** at release density. See
[`../ppg-aux-phase-8-minibatches-per-epoch/CLAIM.md`](../ppg-aux-phase-8-minibatches-per-epoch/CLAIM.md).

## Chain

Every `fact:` below is a key in `manifest.json`. Each one is bound to a substring of the excerpt it
cites, and `tests/test_evidence_bundles_hold.py` fails if the substring is gone.

1. **The run declared 32.** The launch record passes `--nminibatch 32` (fact:argv_nminibatch,
   `raw/effective-config.txt`). The trainer's own config line says `nminibatch=32`
   (fact:effective_config_nminibatch, `raw/declared-config.txt`). The run used rollouts of
   fact:command_nstep steps over fact:command_interacts_total interactions.
2. **It ran one environment.** The second positional argument is `1` (fact:argv_num_envs_positional,
   fact:command_num_envs_positional). `ppg_cell.sh` reads that argument as the environment count
   (fact:positional_2_is_num_envs), and `ppg.sh` passes it as `--num_envs`
   (fact:launcher_passes_num_envs). Neither file has changed since 2026-09-07, before the run.
3. **The trainer executed 1.** The log line `Warning: nminibatch > ntrain!! (32 > 1)` shows the
   declared fact:declared_nminibatch and the executed fact:executed_nminibatch. It appears
   fact:clamp_warning_count times (`raw/clamp-warnings.txt`), once per policy phase:
   293 × 2048 = fact:executed_frames, which is exactly the last checkpoint's stamp fact:final_ic.
4. **Why the executed value is 1.** Upstream's `minibatch_optimize` sets `ntrain` from `batch_len`
   (fact:ntrain_is_batch_len) and clamps any larger request (fact:clamp_rule,
   `raw/upstream-clamp.txt`). `batch_len` is `shape[0]` (fact:batch_len_is_shape0), and rollouts are
   stacked with leading axes fact:leading_axes (`raw/upstream-axis-doc.txt`). So `ntrain` equals
   `num_envs`, which is 1.
5. **The executed update matches the single-rank release.** Upstream's defaults are
   fact:upstream_num_envs envs, rollout fact:upstream_nstep, fact:upstream_nminibatch minibatches
   and fact:upstream_n_epoch_pi policy epoch. That gives fact:upstream_1rank_density gradient steps
   per env frame, at 2048 samples per step. The executed configuration gives
   fact:executed_density, also at 2048 samples per step (`raw/arithmetic.txt`). The declared 32
   would have given fact:declared_32_density.
6. **The run finished.** It saved fact:checkpoint_count checkpoints, the last at fact:final_ic
   (`raw/checkpoint-saves.txt`).
7. **What the project changed afterwards.** At run time the descriptor declared
   fact:descriptor_then_nminibatch (`raw/descriptor-then.txt`, commit `672202d`). It now declares
   fact:descriptor_now_nminibatch. The vendored clamp now raises instead of warning
   (`raw/vendored-clamp-now-fatal.txt`, the file as it is now, not as it ran). Decision commit:
   fact:decision_commit.

## What this does not show

- **Agreement with the 4-rank release run.** The released results were produced with
  fact:upstream_release_ranks MPI ranks. Against that run, the executed policy phase takes 4×
  more steps per frame (fact:upstream_4rank_density upstream) on a quarter of the global batch
  (fact:upstream_4rank_global_batch). The verdict chose the single-rank reference, and the
  reasoning is in `raw/decision-commit.txt`. This bundle records that choice. It does not add a
  justification.
- **The auxiliary phase.** See the sibling bundle.
- **ppg's other deviations from the Procgen recipe:** γ .99, lr 3e-4, entropy 0, three stacked
  frames, the continuous head. These come from `raileanu21a-supp.pdf` §E and are recorded in
  `datasphere/native/families.json` and `docs/FAITHFULNESS.md`, not here.
- **Whether the run learned well.** That is a result question. The endpoint and curve records
  answer it (`notes/endgame/PPG-600K-COMPLETE.md`).

## Falsifier

This claim no longer holds if either of these happens:

- `minibatch_optimize` is changed to split a flattened `num_envs × nstep` axis. Then `ntrain` stops
  being `num_envs`, and 32 becomes expressible.
- The run record turns out to have a different environment count. That would change the
  `ppg_cell.sh Door 1` line or the `"1"` in the launch argv.

Either change must first appear in the cited excerpts or their sources.
`scripts/recheck_evidence.py` shows which sources still exist unchanged.

## Sources

The three host excerpts come from `~/rlvigen-runs/card0-20260909-115331/` on the production host,
which is finished scratch and may be reclaimed. Their source hashes are in each excerpt header. The
repo excerpts come from the read-only `ext/` copy and from git history. Re-take them with
`bash capture.sh`.
