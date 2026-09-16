# PPG's auxiliary phase takes 8 minibatches of 8192 samples per aux epoch in production

Compared with the release, that is half the aux-step density of the 4-rank release run and an
eighth of the single-rank one.

Found 2026-09-16 while capturing the evidence for `ppg-nminibatch`. That verdict says the executed
run matches the release's "update density and per-step batch size". Its arithmetic covers the
**policy** phase only. PPG's auxiliary phase batches through a different function, and nobody had
counted it at `num_envs=1`.

## Status

- **Resolved for the geometry.** The count of what executes comes from running the vendored
  function, and the comparison with both release configurations is arithmetic. Pinned by
  `tests/test_ppg_aux_geometry_is_declared.py`.
- **Traced for the consequence.** The effect on Door returns has not been measured.
- **Not a defect.** The admissible ppg 600k result is a faithful execution of the released
  defaults. The result stands, with a new fidelity row.

## Chain

1. **What the sources specify.**
   - PPG's Appendix A.1 gives fact:paper_aux_minibatches_per_epoch_per_n_pi minibatches per aux
     epoch per N_pi, with N_pi = fact:paper_n_pi and E_aux = fact:paper_e_aux. Appendix A.2 gives
     fact:paper_workers workers × fact:paper_envs_per_worker envs and a rollout of
     fact:paper_rollout (`raw/paper-table-a1.txt`).
   - The released run uses fact:upstream_release_ranks ranks.
   - The IDAAC supplement's continuous-control PPG search names only fact:supp_ppg_constants, at a
     rollout of fact:supp_rollout. Anything it does not name follows Procgen
     (fact:supp_unnamed_follow_procgen), and the aux minibatch count is one of those.
2. **What the released code does with those numbers.**
   - `aux_mbsize` defaults to fact:upstream_aux_mbsize. It counts fact:aux_split_unit, split by
     fact:aux_split_size (`raw/upstream-make-minibatches.txt`), not samples. At 64 envs × 32
     segments that gives 512 minibatches per aux epoch, which is 16 per N_pi, so code and paper
     agree (fact:upstream_1rank_row).
   - Each aux step synchronises gradients (fact:aux_step_syncs), and the synchronisation is a mean
     (fact:sync_is_mean, fact:sync_grads_uses_mean). So 4 ranks take one step over a global batch
     of fact:release_4rank_aux_global_batch samples, at fact:release_4rank_aux_density aux steps
     per env frame.
   - A single rank takes fact:release_1rank_aux_density.
3. **Production runs the same function with the same default.**
   - The vendored `make_minibatches` is identical to upstream
     (fact:vendored_make_minibatches_identical). `aux_train` calls it (fact:aux_train_uses_make_minibatches),
     and `learn` passes `aux_mbsize` through (fact:learn_passes_aux_mbsize). The default is still
     fact:vendored_aux_mbsize.
   - Nothing could have changed that default. `--aux_mbsize` does not exist as a flag
     (fact:aux_mbsize_cli_flag_count). The launchers and descriptor never mention it
     (fact:launch_path_mentions), and the production run record passed none of `aux_mbsize`,
     `n_pi` or `n_aux_epochs` (fact:run_argv_mentions).
   - The run's one environment and 2048-step rollout are established in the sibling bundle
     ([`../ppg-nminibatch-declared-32-executed-1/CLAIM.md`](../ppg-nminibatch-declared-32-executed-1/CLAIM.md)).
4. **The count, by execution.** `scripts/probe_ppg_aux_minibatches.py` lifts the vendored source
   unchanged and runs it on segments shaped like `seg_buf`: fact:production_row (`raw/probe.txt`).
   Compared with the 4-rank release: fact:production_vs_4rank. Compared with the single-rank
   release: fact:production_vs_1rank (`raw/arithmetic.txt`).
5. **The run did execute its aux phases.** The log holds fact:aux_epoch_lines aux-epoch lines with
   indices fact:aux_epoch_indices (`raw/run-aux-epochs.txt`). That is fact:run_aux_phases phases
   × 6, one per 32 of its 293 policy phases, and about fact:run_aux_steps aux gradient steps in
   total.
6. **What the geometry can express.** At one environment the smallest unit is one 2048-step
   segment. With `aux_mbsize` = 2 the result is fact:aux_mbsize_2_row, which equals the 4-rank
   release on both global batch and density. With `aux_mbsize` = 1 it is fact:aux_mbsize_1_row,
   still half the single-rank density at twice its batch. No setting matches the single-rank
   release.
7. **Why this went unnoticed.**
   - The nminibatch verdict's arithmetic is about the policy phase (fact:verdict_scope).
   - The primary-source reconciliation lists five of the six Table A.1 rows as exact matches
     (fact:reconciliation_lists). The aux minibatch row is absent.
   - The retired `rlgen` port had flagged `aux_mbsize=4` as a Procgen-scale size and replaced it
     (fact:retired_port_flagged). Production runs `runnable/ppg`, which kept the default. This is
     the same class as `notes/CORRECTIONS.md` #59: a finding that protects a path production does
     not run.

## What this does not show

- **That the difference changes PPG's returns on Door.** It has not been measured.
- **That 4 is the wrong value.** It is the released default, executed faithfully. The deviation
  is the relation between that default and our environment count, the same class as nminibatch.
- **A setting that matches one release on both phases.** None exists. The policy phase matches the
  single-rank release and runs 4× the 4-rank density. The aux phase matches neither.
  `aux_mbsize=2` would make the aux phase match the 4-rank run, which mixes two references.
- **A change in sample reuse.** E_aux is 6 in every row, so each stored sample is still seen six
  times per aux phase. What differs is how many steps those passes are cut into.
- **An observed per-epoch count.** The probe executes the lifted function on dummy tensors, not
  the training loop. The log prints aux epochs, but not the minibatches within them.
- **Distributed averaging, executed.** The 4-rank figures assume `sync_grads` is active under
  `mpiexec`, which is not run here. Its body is quoted, not executed.

## Recommendation

Keep the ppg 600k result admissible, and declare this row alongside ppg's other adaptations. A
re-run is not justified by this finding alone. Against the paper's own run configuration the gap
is a factor of 2, and the sensitivity is unmeasured.

If ppg is re-run for any other reason, one option is to expose `--aux_mbsize` without changing its
default and to pass 2. Whether that is worth mixing references is an owner decision, recorded as
such in the register.

## Falsifier

- `make_minibatches` changes its unit of splitting.
- `aux_mbsize`, `n_pi` or `n_aux_epochs` becomes reachable from the launch path.
- The environment count or rollout length changes.

Any of these changes the production row. `tests/test_ppg_aux_geometry_is_declared.py` fails in
each case.

## Sources

The host excerpts come from `~/rlvigen-runs/card0-20260909-115331/`, which may be reclaimed. The
PDF text was extracted with the `pdftotext` version and file hashes in `raw/paper-identity.txt`.
Re-take everything with `bash capture.sh`.
