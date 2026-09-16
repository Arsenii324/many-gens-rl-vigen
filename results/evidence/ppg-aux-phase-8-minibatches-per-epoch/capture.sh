#!/usr/bin/env bash
# Recipe for this bundle. Re-running it re-captures every excerpt and rewrites manifest.json.
# It refuses when a source is gone, so after the host run directory is reclaimed this file is the
# record of HOW the evidence was taken, and raw/ is the evidence itself.
set -euo pipefail
cd "$(dirname "$0")/../../.."
PY=${PY:-/Users/a2mogus/build-projs/barannikov-work/.venv/bin/python}
C() { "$PY" scripts/capture_host_evidence.py "$@"; }
S=ppg-aux-phase-8-minibatches-per-epoch
CELL='~/rlvigen-runs/card0-20260909-115331/native-out/cells/ppg-s1'
U=ext/phasic-policy-gradient/phasic_policy_gradient
V=runnable/ppg/phasic_policy_gradient
PAPER=ext/baseline_resources/10_ppg/paper_2009.04416.pdf
SUPP=ext/idaac/raileanu21a-supp.pdf

# --- what the sources specify ---
C $S paper-identity --command "shasum -a 256 $PAPER $SUPP; pdftotext -v 2>&1 | head -1" \
  --note 'which PDF files the two text excerpts below were extracted from, and with what'
C $S paper-table-a1 --command "pdftotext -layout $PAPER -" --lines 471:495 \
  --note 'PPG paper, Appendix A: 16 minibatches per aux epoch per N_pi; 4 workers x 64 envs; rollout 256' \
  --fact paper_n_pi=32 --anchor 'Nπ                      32' \
  --fact paper_e_aux=6 --anchor 'Eaux                      6' \
  --fact paper_aux_minibatches_per_epoch_per_n_pi=16 --anchor '# minibatches per aux epoch per Nπ      16' \
  --fact paper_rollout=256 --anchor '# timesteps per rollout           256' \
  --fact paper_workers=4 --anchor '# workers                      4' \
  --fact paper_envs_per_worker=64 --anchor '# environments per worker             64'
C $S supp-ppg-recipe --command "pdftotext -layout $SUPP -" --lines 502:513 \
  --note 'IDAAC supplement SS E: the continuous-control PPG search names five constants; the aux minibatch count is not among them, and unnamed values follow Procgen' \
  --fact supp_ppg_constants='N_pi 32, E_pi 1, E_V 1, E_aux 6, beta_clone 1' --anchor 'found Nπ = 32, Eπ = 1, EV = 1, Eaux = 6, and βclone = 1' \
  --fact supp_unnamed_follow_procgen=true --anchor 'not mentioned here were set to the same values as the ones used for Procgen' \
  --fact supp_rollout='2048 steps, 1 process' --anchor '2048 steps, 1 process'
C $S upstream-readme-ranks --local-path ext/phasic-policy-gradient/README.md --grep 'mpiexec' --max 1 \
  --note 'the released PPG results were produced with 4 MPI ranks' \
  --fact upstream_release_ranks=4 --anchor 'mpiexec -np 4 python -m phasic_policy_gradient.train'

# --- what the released code does with those numbers ---
C $S upstream-aux-defaults --local-path $U/train.py --grep 'num_envs=|aux_mbsize|n_aux_epochs|n_pi=' \
  --note 'pristine upstream train.py: aux_mbsize is 4 (a count of env-segment pairs, not of samples)' \
  --fact upstream_aux_mbsize=4 --anchor '23:    aux_mbsize=4,' \
  --fact upstream_num_envs=64 --anchor '16:    num_envs=64,'
C $S upstream-make-minibatches --local-path $U/ppg.py --lines 163:176 \
  --note 'pristine upstream: aux minibatches are groups of mbsize (env, segment) pairs' \
  --fact aux_split_unit='(env, segment) pairs' --anchor 'itertools.product(range(nenv), range(nseg))' \
  --fact aux_split_size=mbsize --anchor '.split(mbsize)'
C $S upstream-sync-grads --local-path $U/torch_util.py --grep 'def all_mean_|x /= dist_get_world_size|def sync_grads|all_mean_\(flatgrad' \
  --note 'pristine upstream: sync_grads all-reduces then divides by world size, so 4 ranks take one averaged step over 4x the samples' \
  --fact sync_is_mean=true --anchor 'x /= dist_get_world_size(group=group)' \
  --fact sync_grads_uses_mean=true --anchor 'all_mean_(flatgrad, group=group)'
C $S upstream-aux-sync --local-path $U/ppg.py --grep 'sync_grads' \
  --note 'pristine upstream: every aux step syncs gradients across ranks' \
  --fact aux_step_syncs=true --anchor 'tu.sync_grads(model.parameters())'

# --- what production executes ---
C $S vendored-make-minibatches-identical --command "bash -c 'diff <(sed -n \"/^def make_minibatches/,/^def aux_train/p\" $U/ppg.py) <(sed -n \"/^def make_minibatches/,/^def aux_train/p\" $V/ppg.py) && echo IDENTICAL-make_minibatches'" \
  --note 'the vendored make_minibatches is byte-identical to upstream' \
  --fact vendored_make_minibatches_identical=true --anchor 'IDENTICAL-make_minibatches'
C $S vendored-aux-call-sites --local-path $V/ppg.py --grep 'make_minibatches\(|aux_mbsize|Aux epoch|n_aux_epochs|n_pi=' \
  --note 'the vendored learn() passes aux_mbsize straight to make_minibatches, once per aux epoch' \
  --fact aux_train_uses_make_minibatches=true --anchor 'for mb in make_minibatches(segs, mbsize):' \
  --fact learn_passes_aux_mbsize=true --anchor 'mbsize=aux_mbsize,'
C $S vendored-train-defaults --local-path $V/train.py --grep 'aux_mbsize|n_aux_epochs|n_pi' \
  --note 'the vendored train.py keeps aux_mbsize=4 and exposes n_pi and n_aux_epochs, but not aux_mbsize, on the CLI' \
  --fact vendored_aux_mbsize=4 --anchor '44:    aux_mbsize=4,'
C $S aux-mbsize-not-a-cli-flag --local-path $V/train.py --grep "add_argument\('--aux_mbsize'" --allow-empty \
  --note 'absence: no --aux_mbsize flag exists, so no launcher could have changed it' \
  --fact aux_mbsize_cli_flag_count=0 --anchor 'header:# matched-lines: 0 '
C $S aux-mbsize-not-passed --command 'cat runnable/_launch/ppg_cell.sh runnable/_launch/ppg.sh datasphere/native/families.json' \
  --grep 'aux_mbsize|n_pi|n_aux_epochs' --allow-empty \
  --note 'absence: neither launcher nor the descriptor mentions aux_mbsize, n_pi or n_aux_epochs' \
  --fact launch_path_mentions=0 --anchor 'header:# matched-lines: 0 '
C $S run-argv-no-aux-override --host-path "$CELL/effective_config.json" --grep 'aux_mbsize|n_pi|n_aux' --allow-empty \
  --note 'absence: the production run record passed none of the three' \
  --fact run_argv_mentions=0 --anchor 'header:# matched-lines: 0 '
C $S run-aux-epochs --host-path "$CELL/training.log" --grep 'Aux epoch [0-9]' --max 12 \
  --note 'the production run logged 54 aux epochs: 9 aux phases x 6, one per 32 of its 293 policy phases' \
  --fact aux_epoch_lines=54 --anchor 'header:# matched-lines: 54 ' \
  --fact aux_epoch_indices='0..5' --anchor 'Aux epoch 5'

# --- the count, by executing the vendored function ---
C $S probe --command "\"$PY\" scripts/probe_ppg_aux_minibatches.py" \
  --note 'vendored make_minibatches executed on dummy segments shaped like seg_buf' \
  --fact upstream_1rank_row='512 mb/epoch, 1024 samples, 0.005859 aux steps/frame' \
  --anchor 'upstream 1-rank default | 64 | 256 | 4 | 512 | 16 | [(4, 256)] | 1024 | 3072 | 524288 | 0.005859' \
  --fact production_row='8 mb/epoch, 8192 samples, 0.000732 aux steps/frame' \
  --anchor 'production (families.json) | 1 | 2048 | 4 | 8 | 0.25 | [(4, 2048)] | 8192 | 48 | 65536 | 0.000732' \
  --fact aux_mbsize_2_row='16 mb/epoch, 4096 samples, 0.001465 aux steps/frame' \
  --anchor 'expressible | 1 | 2048 | 2 | 16 | 0.5 | [(2, 2048)] | 4096 | 96 | 65536 | 0.001465' \
  --fact aux_mbsize_1_row='32 mb/epoch, 2048 samples, 0.002930 aux steps/frame' \
  --anchor 'expressible | 1 | 2048 | 1 | 32 | 1 | [(1, 2048)] | 2048 | 192 | 65536 | 0.002930'
C $S arithmetic --command "\"$PY\" -c \"
f = lambda x: format(x, '.6f')
print('aux phases in the run            293 // 32 =', 293 // 32, '; aux epochs', 293 // 32 * 6)
print('4-rank release aux global batch  4 ranks * 4 pairs * 256 =', 4 * 4 * 256)
print('4-rank release aux steps/frame   6 * 512 / (4*64*256*32) =', f(6 * 512 / (4 * 64 * 256 * 32)))
print('1-rank release aux steps/frame   6 * 512 / (64*256*32) =', f(6 * 512 / (64 * 256 * 32)))
print('production aux steps/frame       6 * 8 / (1*2048*32) =', f(6 * 8 / (1 * 2048 * 32)))
print('production vs 4-rank             density x', (6 * 8 / 65536) / (6 * 512 / 2097152), '; batch x', 8192 / 4096)
print('production vs 1-rank             density x', (6 * 8 / 65536) / (6 * 512 / 524288), '; batch x', 8192 / 1024)
print('aux steps in the run             9 * 6 * 8 =', 9 * 6 * 8, '; at aux_mbsize 2:', 9 * 6 * 16, '; at 1-rank density:', 9 * 6 * 64)
\"" --note 'the comparison the verdict rests on' \
  --fact run_aux_phases=9 --anchor '293 // 32 = 9 ; aux epochs 54' \
  --fact release_4rank_aux_global_batch=4096 --anchor '4 pairs * 256 = 4096' \
  --fact release_4rank_aux_density=0.001465 --anchor '(4*64*256*32) = 0.001465' \
  --fact release_1rank_aux_density=0.005859 --anchor '(64*256*32) = 0.005859' \
  --fact production_vs_4rank='density x0.5, batch x2' --anchor 'density x 0.5 ; batch x 2.0' \
  --fact production_vs_1rank='density x0.125, batch x8' --anchor 'density x 0.125 ; batch x 8.0' \
  --fact run_aux_steps=432 --anchor '9 * 6 * 8 = 432'

# --- what the project recorded before ---
C $S retired-port-prior-art --local-path rlgen/algos/ppg/config.py --grep 'aux_num_mini_batch|aux_mbsize=4|minibatch SIZE|directly portable' \
  --note 'the retired rlgen port had flagged aux_mbsize=4 as a Procgen-scale size and replaced it; the production runnable port did not inherit that' \
  --fact retired_port_flagged=true --anchor 'is a raw'
C $S reconciliation-row --local-path notes/PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md --grep 'EXACT SOURCE MATCH\*\* for the phasic' \
  --note 'the primary-source reconciliation lists five of the six Table A.1 rows as an exact match; the aux minibatch row is absent' \
  --fact reconciliation_lists='n_pi, E_pi, E_V, E_aux, beta_clone' --anchor 'auxiliary epochs6, βclone1'
C $S nminibatch-verdict-scope --local-path datasphere/native/families.json --grep 'Which value is right is settled by arithmetic' \
  --note 'the nminibatch verdict compares the POLICY phase only' \
  --fact verdict_scope=policy-phase --anchor '1 epoch x 8 minibatches: 8 gradient steps of 2048 samples each'
