#!/usr/bin/env bash
# Run every baseline briefly and print one table. The claim "all twelve run" should be a command,
# not a paragraph in a document that was true once.
#
#   bash runnable/_launch/smoke_all.sh                # all twelve
#   bash runnable/_launch/smoke_all.sh rad soda ctrl  # a subset
#
# Each entry is deliberately tiny -- enough to build the env, take real gradient steps, and log
# at least one metric line. It is a SMOKE, not an experiment: nothing here says anything about
# whether an algorithm learns. Logs land in $OUT so a failure can be read afterwards.
#
# EXPECTED EXIT CODES, because two of them are not 0 and that is upstream, not breakage:
#   ctrl  exits 1 on success -- main() returns a tuple and absl.app.run does sys.exit(main(argv)),
#         which Python turns into 1. It prints its final line first.
#   curl  fails under the MPS shim ("scatter: index -1 ...") and is therefore run with device=cpu
#         here. The same command on CUDA needs no such thing. See docs/RUNNABLE-ORIGINALS.md.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
OUT="${SMOKE_OUT:-/tmp/rlgen_smoke_$(date +%H%M%S)}"
mkdir -p "$OUT"
ALL=(rad soda alda ppg idaac ibac_sni ctrl drqv2 svea sgqn drq curl)
TARGETS=("${@:-}")
[[ -z "${TARGETS[0]:-}" ]] && TARGETS=("${ALL[@]}")

run_one() {
  case "$1" in
    rad|soda)
      timeout 1500 bash "$HERE/dmc_gb.sh" "$1" Door 0 --train_steps 400 --init_steps 100 \
        --eval_freq 300 --eval_episodes 1 ;;
    alda)
      ALDA_RESULTS="$OUT/alda_results" timeout 1800 bash "$HERE/alda.sh" \
        --spec.trainer.config.n_train_steps=1200 ;;
    ppg)
      # ppg has no natural stopping point below 100M interacts, so it is capped by `timeout` and
      # judged on whether it completed a full PPG cycle (a PPO phase AND an auxiliary phase).
      timeout 900 bash "$HERE/ppg.sh" Door 8 --n_pi 1 --n_aux_epochs 1 --arch dual ;;
    idaac)
      timeout 2400 bash "$HERE/idaac.sh" idaac Door 4 --num_steps 128 --num_mini_batch 4 \
        --log_interval 4 --num_env_steps 2560 ;;
    ibac_sni)
      # --procs 1: MuJoCo GL contexts do not survive fork on macOS, and its train.py hardcodes
      # multiprocessing.set_start_method("fork").
      timeout 1500 bash "$HERE/ibac_sni.sh" Door 1 --frames 1300 --frames-per-proc 64 \
        --batch-size 32 --epochs 1 ;;
    ctrl)
      timeout 2400 bash "$HERE/ctrl.sh" Door 4 --n_steps=16 --n_minibatch=2 --train_steps=2600 \
        --cluster_len=4 --n_minibatch_ctrl=1 ;;
    curl)
      # device=cpu: MPS-only failure, see the header.
      timeout 2400 bash "$HERE/rlvigen.sh" curl Door device=cpu num_train_frames=1300 \
        num_seed_frames=600 eval_every_frames=1000 num_eval_episodes=1 ;;
    *)
      timeout 2400 bash "$HERE/rlvigen.sh" "$1" Door num_train_frames=1300 num_seed_frames=600 \
        eval_every_frames=1000 num_eval_episodes=1 ;;
  esac
}

# A baseline passes only if it produced EVIDENCE OF TRAINING, not merely a zero exit. An exit
# code alone would pass a run that built an env and stopped.
#
# The ANSI strip is load-bearing, not cosmetic: dmc_gb's logger colours its prefix, so `| eval`
# never appears literally and the first version of this reported rad as NO-TRAIN on a run that
# had in fact trained. A checker that reads the wrong thing is worse than none.
evidence() {
  local plain; plain=$(sed 's/\x1b\[[0-9;]*m//g' "$2")
  case "$1" in
    rad|soda)     grep -qE '\| *eval *\|' <<<"$plain" ;;
    alda)         grep -q 'eval/episode_reward' <<<"$plain" ;;
    ppg)          grep -q 'Aux epoch' <<<"$plain" ;;
    idaac)        grep -q 'test/success_rate' <<<"$plain" ;;
    ibac_sni)     grep -qE '^U [0-9]+ \|' <<<"$plain" ;;
    ctrl)         grep -q 'Eprew200' <<<"$plain" ;;
    *)            grep -qE '\| *train *\|' <<<"$plain" ;;
  esac
}

printf '%-10s %-6s %-9s %s\n' baseline exit evidence log
printf '%s\n' "------------------------------------------------------------------"
fail=0
for b in "${TARGETS[@]}"; do
  log="$OUT/$b.log"
  run_one "$b" > "$log" 2>&1
  code=$?
  if evidence "$b" "$log"; then ev="TRAINED"; else ev="NO-TRAIN"; fail=1; fi
  # ctrl's 1 is upstream (see header); ppg is capped by timeout, so 124 is expected.
  case "$b:$code" in ctrl:1|ppg:124) note="(expected)";; *:0) note="";; *) note="<-- CHECK"; fail=1;; esac
  printf '%-10s %-6s %-9s %s %s\n' "$b" "$code" "$ev" "$log" "$note"
done
printf '%s\n' "------------------------------------------------------------------"
echo "logs in $OUT"
exit $fail
