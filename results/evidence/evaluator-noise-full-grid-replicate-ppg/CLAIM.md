# Two full ppg endpoint grids from one invocation: the evaluator varies run to run even without sampling

The ppg endpoint evaluation ran twice to completion, with the same checkpoint, invocation and
evaluator revision. Grid 1 is the committed one. Grid 2 was a retry started because a corrupted
wrapper never printed the completion marker; it was never committed. Together they are an
88-row paired replicate, twenty times larger than the three-run check in
[`../evaluator-run-to-run-noise-ppg`](../evaluator-run-to-run-noise-ppg/CLAIM.md), and they cover
both policy modes.

## Status

**Resolved.** The run-to-run nondeterminism is not explained by the unseeded torch sampling
stream, because the `mode` rows, which draw no samples, vary about as much as the `sample` rows.
Its source is traced no further here.

It stays small: a mean of 0.21 SE (mode) and 0.33 SE (sample) per row.

## Chain

1. **Same everything.**
   - Both grids ran on evaluator revision fact:grid1_revision / fact:grid2_revision
     (`raw/grid1-rows.txt`, `raw/grid2-rows.txt`).
   - Their invocation keys are identical (fact:invocation_key_differences,
     `raw/invocation-diff.txt`). The keys were taken from the result archives, because the run
     manifests in `native-out` are root-only.
   - The committed file is grid 1 (fact:committed_sha, equal to the grid 1 source hash).
   - All fact:rows_paired rows pair up.
2. **Placements reproduce everywhere** (fact:mode_placements_identical, and the same for
   `sample`).
3. **Episodes do not, even without sampling.** The `mode` rule takes the Normal's mean
   (fact:mode_is_mean, `raw/mode-act-fn.txt`), so it consumes no torch randomness. Yet:
   - only fact:mode_rows_identical per-scene mode rows reproduce exactly;
   - only fact:mode_episodes_identical mode episodes do;
   - for `sample`, fact:sample_episodes_identical do.
   The two modes are within a few percent of each other, so the sampling stream adds little or
   nothing to the run-to-run variation (`raw/paired.txt`).
4. **Where it happens.**
   - In `train` and `eval-easy`, most episodes reproduce: mode fact:mode_train_identical and
     fact:mode_easy_identical, sample fact:sample_train_identical.
   - In `eval-medium` and `eval-hard`, none do: fact:mode_eval_medium_identical and
     fact:mode_eval_hard_identical. That matches `audit_eval_validity.py`'s standing caveat that
     their perturbation slots vary between passes, and here it is total.
   - Identical episodes are spread evenly over episode index 0-19, with no drift, so nothing
     visibly carries over from one episode to the next.
5. **How large.** |mean difference| per row averages fact:mode_z_mean SE (mode) and
   fact:sample_z_mean SE (sample). Two of 44 rows exceed 1 SE in each mode, which is fewer than
   independent noise would give. Most episodes in two of the regimes are identical.

## What this does not show

- **The source of the train/easy divergence.** CUDA kernel nondeterminism in the policy forward,
  EGL rendering and MuJoCo stepping all remain candidates. None is tested.
- **That the eval-medium/eval-hard differences are only perturbation sampling.** They include it.
  Evaluator noise on top of that is not separated out.
- **Other baselines.** Only ppg's two grids exist.
- **The breadth dependence claimed in the sibling bundle.** A narrow re-run consumes torch RNG
  differently from a full grid. Both grids here are full grids, so they do not test it.

## What changes because of this

- The sibling bundle's mechanism paragraph offered the unseeded torch stream as the likely cause.
  For identical invocations, that is now ruled out as the main cause.
- Any row-level comparison between runs should use the paired design on `train` and `eval-easy`
  only. `eval-medium` and `eval-hard` rows are never reproduced, even by the same run twice.

## Falsifier

- A third full grid of the same checkpoint in which `mode` rows reproduce exactly while `sample`
  rows do not.
- A fix that makes `train` mode rows bit-identical across runs.

## Sources

Both grids come from the host run directories `card1-20260915-160000` and `card1-20260916-035335`,
plus the retry's archive under `reeval-v214/`. Re-take everything with `bash capture.sh`.
