#!/usr/bin/env bash
# Recipe for this bundle. Re-running it re-captures every excerpt and rewrites manifest.json.
# It refuses when a source is gone, so after the host run directory is reclaimed this file is the
# record of HOW the evidence was taken, and raw/ is the evidence itself.
set -euo pipefail
cd "$(dirname "$0")/../../.."
PY=${PY:-/Users/a2mogus/build-projs/barannikov-work/.venv/bin/python}
C() { "$PY" scripts/capture_host_evidence.py "$@"; }
S=ppg-nminibatch-declared-32-executed-1
L='~/rlvigen-runs/card0-20260909-115331/native-out/cells/ppg-s1/training.log'
U=ext/phasic-policy-gradient/phasic_policy_gradient

# --- what the production run declared, executed and saved (host) ---
C $S clamp-warnings --host-path "$L" --grep 'nminibatch > ntrain' --max 3 \
  --note 'the optimiser clamped nminibatch at every one of the 293 policy phases' \
  --fact clamp_warning_count=293 --anchor 'header:# matched-lines: 293 ' \
  --fact declared_nminibatch=32 --anchor 'Warning: nminibatch > ntrain!! (32 > 1)' \
  --fact executed_nminibatch=1 --anchor 'Warning: nminibatch > ntrain!! (32 > 1)'
C $S declared-config --host-path "$L" --grep 'NATIVE_PPG_EFFECTIVE_CONFIG|Command being timed' \
  --note 'what the cell declared: nminibatch 32, nstep 2048, 600k interacts; no num_envs flag' \
  --fact effective_config_nminibatch=32 --anchor 'nminibatch=32 entcoef=0' \
  --fact command_nstep=2048 --anchor '--nstep 2048' \
  --fact command_interacts_total=600000 --anchor '--interacts_total 600000' \
  --fact command_num_envs_positional=1 --anchor 'ppg_cell.sh Door 1 600064 10'
C $S checkpoint-saves --host-path "$L" --grep 'Saving to .*IC=' --max 20 \
  --note 'the run reached its end: 13 IC-stamped checkpoints, the last at 600,064' \
  --fact checkpoint_count=13 --anchor 'header:# matched-lines: 13 ' \
  --fact final_ic=600064 --anchor 'model012.jd IC=600064'

C $S effective-config --host-path "${L%/training.log}/effective_config.json" --max 0 \
  --note 'the cell record written at launch: argv, host profile, runner environment' \
  --fact argv_num_envs_positional=1 --anchor $'"Door",\n    "1",\n    "600064",' \
  --fact argv_nminibatch=32 --anchor $'"--nminibatch",\n    "32",' \
  --fact host_profile=v100 --anchor '"host_profile": "v100"'
C $S cell-positional --local-path runnable/_launch/ppg_cell.sh --grep 'NENV' \
  --note 'ppg_cell.sh: positional 2 is the environment count, handed to ppg.sh unchanged (file unchanged since 2026-09-07, before the run)' \
  --fact positional_2_is_num_envs=true --anchor 'NENV="${2:?num envs}"'
C $S launcher-num-envs --local-path runnable/_launch/ppg.sh --grep 'NENV' \
  --note 'ppg.sh: the environment count becomes --num_envs' \
  --fact launcher_passes_num_envs=true --anchor '--num_envs "$NENV"'

# --- the pristine upstream the verdict compares against (repo, read-only ext/) ---
C $S upstream-recipe --local-path $U/train.py --lines 12:30 \
  --note 'pristine upstream PPG defaults: 64 envs, nminibatch 8, one pi and vf epoch, 6 aux epochs' \
  --fact upstream_num_envs=64 --anchor '16:    num_envs=64,' \
  --fact upstream_n_epoch_pi=1 --anchor '17:    n_epoch_pi=1,' \
  --fact upstream_nminibatch=8 --anchor '22:    nminibatch=8,' \
  --fact upstream_n_aux_epochs=6 --anchor '26:    n_aux_epochs=6,'
C $S upstream-nstep --local-path $U/ppo.py --lines 118:121 \
  --note 'pristine upstream default rollout length' \
  --fact upstream_nstep=256 --anchor 'number of serial timesteps" = 256'
C $S upstream-readme-ranks --local-path ext/phasic-policy-gradient/README.md --grep 'mpiexec' --max 1 \
  --note 'the released PPG results were produced with 4 MPI ranks' \
  --fact upstream_release_ranks=4 --anchor 'mpiexec -np 4 python -m phasic_policy_gradient.train'
C $S upstream-clamp --local-path $U/minibatch_optimize.py --lines 42:60 \
  --note 'pristine upstream: ntrain is the leading axis; nminibatch above it is warned about and clamped' \
  --fact ntrain_is_batch_len=true --anchor '52:    ntrain = tu.batch_len(tensordict)' \
  --fact clamp_rule='nminibatch = ntrain when nminibatch > ntrain' --anchor '55:        nminibatch = ntrain'
C $S upstream-batch-len --local-path $U/torch_util.py --lines 83:94 \
  --note 'pristine upstream: batch_len is shape[0] of the first leaf' \
  --fact batch_len_is_shape0=true --anchor 'b = flatlist[0].shape[0]'
C $S upstream-axis-doc --local-path $U/roller.py --lines 100:104 \
  --note 'pristine upstream: rollouts carry (batch, time) leading axes, so shape[0] is the env count' \
  --fact leading_axes='(batch, time)' --anchor 'leading axes (batch, time)'

# --- how the project changed after the finding (repo) ---
C $S vendored-clamp-now-fatal --local-path runnable/ppg/phasic_policy_gradient/minibatch_optimize.py --lines 42:70 \
  --note 'the vendored copy now raises instead of silently clamping'
C $S descriptor-then --command 'git show 672202d:datasphere/native/families.json' --grep '"nminibatch"' \
  --note 'the production descriptor at the time of the run (commit 672202d, 2026-09-09) declared 32' \
  --fact descriptor_then_nminibatch=32 --anchor '"nminibatch": "32"'
C $S descriptor-now --local-path datasphere/native/families.json --grep '"nminibatch"' \
  --note 'the descriptor now declares what executes' \
  --fact descriptor_now_nminibatch=1 --anchor '"nminibatch": "1"'
C $S decision-commit --command 'git log -1 --format="commit %H%nDate: %ci%n%n%B" 237f876' \
  --note 'the commit that recorded the finding and made the clamp fatal' \
  --fact decision_commit=237f876bb51b --anchor 'commit 237f876bb51b'

# --- the arithmetic, executed rather than typed ---
C $S arithmetic --command "\"$PY\" -c \"
f = lambda x: format(x, '.8f')
print('policy phases executed      293 * 2048 =', 293 * 2048)
print('upstream 1-rank density     (1 epoch * 8 mb) / (64*256) =', f(8 / (64 * 256)))
print('upstream 1-rank batch/step  (64*256) / 8 =', (64 * 256) // 8)
print('executed density            (1 epoch * 1 mb) / (1*2048) =', f(1 / (1 * 2048)))
print('executed batch/step         (1*2048) / 1 =', 2048)
print('declared-32 density         (1 epoch * 32 mb) / (1*2048) =', f(32 / 2048))
print('upstream 4-rank density     8 / (4*64*256) =', f(8 / (4 * 64 * 256)), '; global batch/step', 4 * 64 * 256 // 8)
\"" --note 'the arithmetic the verdict rests on' \
  --fact executed_frames=600064 --anchor '293 * 2048 = 600064' \
  --fact upstream_1rank_density=0.00048828 --anchor '(64*256) = 0.00048828' \
  --fact executed_density=0.00048828 --anchor '(1*2048) = 0.00048828' \
  --fact declared_32_density=0.01562500 --anchor '(1*2048) = 0.01562500' \
  --fact upstream_4rank_density=0.00012207 --anchor '(4*64*256) = 0.00012207' \
  --fact upstream_4rank_global_batch=8192 --anchor 'global batch/step 8192'
