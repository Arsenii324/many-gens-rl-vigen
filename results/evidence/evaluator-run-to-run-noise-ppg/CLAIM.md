# The offline evaluator is nondeterministic run to run for ppg, by about a tenth of one standard error

The question: the same ppg checkpoint was re-evaluated after the evaluator revision moved. Did the
measured quantity change, or is the difference noise? The narrative is
`notes/endgame/RESOLVED-ppg-reeval-is-within-evaluator-noise.md`. This bundle is its evidence.

## Status

- **Resolved.** The difference is evaluator noise, not a changed estimand.
- **One new fact, established only here.** The placements are identical across all three runs, and
  most episode returns still differ. So the run-to-run noise is in the action stream, not in where
  the door is.
  **[Refined 2026-09-16:]** it is in the trajectory, not specifically in action sampling. Deterministic
  `mode` rows diverge too; see the full-grid replicate.

## Chain

1. **Three evaluations of one checkpoint.** All three rows carry checkpoint fact:checkpoint
   (fact:run2_checkpoint, fact:old_checkpoint):
   - run 1: fact:run1_mean, sd fact:run1_sd (`raw/run1-row.txt`);
   - run 2: fact:run2_mean, sd fact:run2_sd (`raw/run2-row.txt`);
   - the original full-grid row: fact:old_mean, under evaluator revision
     fact:old_evaluator_revision (`raw/old-row.txt`). Both re-runs ran under
     fact:new_evaluator_revision (fact:run2_evaluator_revision).
2. **Runs 1 and 2 were the same invocation.** Their `run_manifest.json` files
   (`raw/run1-manifest.txt`, `raw/run2-manifest.txt`) differ on fact:manifest_diff_lines lines
   (`raw/manifest-diff.txt`). Those lines are disk free and used space (fact:diff_touches_free)
   plus the hashes of the results themselves. None of the invocation-defining keys changed
   (fact:invocation_keys_changed). Run 1 recorded payload fact:payload_sha256
   (`raw/run1-invocation.txt`). Both rows also record the narrow scope fact:narrow_scope_regimes,
   scene 0. The original row used fact:full_scope_regimes over ten scenes.
3. **The instrument claims determinism and is not deterministic.** Each row records
   `torch.use_deterministic_algorithms` as enabled (fact:deterministic_flag_enabled), yet runs 1
   and 2 differ.
4. **The placements did not move; the actions did.** Recomputed from the captured per-episode
   returns and seeds (`raw/derived.txt`), not from the recorded means:
   - all three runs used the same 20 placement seeds (fact:placement_seeds_identical);
   - fact:episodes_differing_run1_run2 episode returns differ between runs 1 and 2.
   In the code (`raw/seeding-code.txt`), torch is seeded once per family setup
   (fact:torch_seeded_once), while the per-episode reseed touches `random` and `numpy` only
   (fact:per_episode_reseeds_numpy). ppg samples its actions from torch (fact:ppg_act_samples,
   `raw/ppg-samples-from-torch.txt`). That is consistent with the observation. It is not proven to
   be the only source: CUDA kernels could also contribute.
5. **In scale.** The spread of the three means is fact:spread. One standard error at n=20 is
   fact:se_n20. So the spread is fact:spread_in_se SE, and old minus the mean of the two new runs
   is fact:old_vs_new_in_se SE.

## What this does not show

- **[Refined 2026-09-16 by [`../evaluator-noise-full-grid-replicate-ppg`](../evaluator-noise-full-grid-replicate-ppg/CLAIM.md)]**
  Between two IDENTICAL full-grid invocations, `mode` rows, which draw no samples, diverge about as
  often as `sample` rows. So the torch stream is not the main source of run-to-run variation.
  It can still explain breadth dependence between a narrow and a full sweep, which is what this
  bundle compared.
- **Which mechanism dominates.** Torch RNG consumption, which depends on sweep breadth, and CUDA
  nondeterminism both fit. Four of twenty episodes reproduced exactly, which weakly suggests the
  divergence starts partway through some episodes, but that is not tested.
- **The nine mode baselines.** They take an argmax or mean action. They were not tested here, and
  the claim is only about sampling-policy rows (`idaac`, `ppg`, `ibac_sni`). Only ppg was measured.
  **[Corrected 2026-09-16:]** do not assume the mode baselines reproduce. ppg's own `mode` rows do not
  (282/800 episodes identical across two identical runs).
- **More than one scene.** Only train/scene 0 was re-run. Other scenes are assumed to behave
  alike, not measured.
- **Exact reproducibility of any sampling row.** It is not available. Only agreement within
  noise is.

## Falsifier

- A third run of the same invocation that lands several SE away from these would falsify
  "a tenth of an SE".
- Per-episode torch reseeding that makes runs 1 and 2 bit-identical would confirm the mechanism,
  and then the breadth dependence must be re-measured.

## Sources

`~/rlvigen-runs/reeval-v214/ppg-smoke-run1.tgz` and `ppg-smoke-result.tgz` on the production host
are finished scratch; their hashes are in the excerpt headers. The old row is committed in
`results/superseded-runs/`. Re-take everything with `bash capture.sh`.
