#!/usr/bin/env python3
"""What an OFFLINE evaluator needs from each baseline beyond the weights — R3 / R7 / C43.

## Why this exists

The base version keeps training and evaluation in separate harnesses, and three independent
findings now say the comparable measurement can only come from the offline one: `audit_eval_axis`
shows five baselines sweep ten scenes and seven do not; `audit_eval_cadence` shows three run no
periodic training-time evaluation at all; and C43 shows retention needs two regimes that most
training loops never produce together.

Writing that harness needs an answer per baseline to a question nobody had enumerated: **what does
evaluating this checkpoint require besides the network?** Observation scaling, whether any running
statistic must be restored, whether the policy is read deterministically or sampled, and whether
the baseline's own evaluator can be reused at all on this target.

## The two findings that motivated the columns

`idaac` evaluates with `actor_critic.act(obs)`, whose `deterministic` argument defaults to False —
so it **samples**, while the RL-ViGen five take `dist.mean` and `dmc_gb` takes `mu`. Same word
("evaluation"), different estimator, and the difference is not small for a policy with a wide
action distribution.

`ctrl` ships `evaluate_ppo.py`, and it is **discrete-only**: `logits.argmax(1)` or
`jax.random.categorical`. robosuite Door is a 7-DoF continuous action space, and the continuous
head this project gave `ctrl` emits a mean and a log-std, not logits. Its own evaluator therefore
cannot read our checkpoints — not a portability inconvenience but a hard "must be authored".

Reward normalisation is deliberately NOT a column: it exists in `ctrl`, `idaac` and `ppg` and
changes no reported number, because in all three the episode monitor sits inside the normaliser.
That was verified rather than assumed, and the register carries the correction where it was first
recorded the other way round.
"""
from __future__ import annotations

import argparse
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

# `policy_mode`   how the action is read at evaluation
# `obs_scaling`   what maps raw uint8 pixels to network input, and whether it carries state
# `reusable`      can the baseline's own evaluation code run against our checkpoints on Door
# `anchor`/`expect` are checked live -- tests/test_record_conventions.py::
# test_eval_state_audit_anchors_still_hold fails STALE if the file moved. Update the anchor in the
# SAME edit that moves the code, not after the test catches it.
STATE = {
    "drqv2": {"policy_mode": "deterministic (dist.mean)", "obs_scaling": "stateless: /255 - 0.5 in the encoder",
              "running_stats": "none", "reusable": "yes -- Workspace.eval via agent.act(eval_mode=True)",
              "anchor": "RL-ViGen-upstream/algos/drqv2.py:169-172", "expect": "action = dist.mean"},
    "rad":   {"policy_mode": "deterministic (mu)", "obs_scaling": "stateless: /255 in the encoder, random_crop to 84",
              "running_stats": "none", "reusable": "yes -- evaluate(env, agent, ...) takes any env",
              "anchor": "runnable/dmc_gb/src/algorithms/sac.py:73", "expect": "def select_action(self, obs):"},
    "alda":  {"policy_mode": "deterministic (mu)", "obs_scaling": "stateless",
              "running_stats": "none",
              "reusable": "yes, and it is the richest -- evaluate(step, distracting_env, color_env) "
                          "already drives three regimes",
              "anchor": "runnable/alda/trainers/alda_trainer.py:525", "expect": "def evaluate(self, step, distracting_env=False, color_env=False):"},
    "idaac": {"policy_mode": "STOCHASTIC (dist.sample) -- `deterministic` defaults False and test.py does not pass it",
              "obs_scaling": "VecNormalize(ob=False): the wrapper does NOT scale observations; the model does",
              "running_stats": "ret_rms exists but is training-only; VecMonitor is inside VecNormalize so returns are raw",
              "reusable": "yes -- test.py::evaluate builds its own robosuite venv",
              "anchor": "runnable/idaac/ppo_daac_idaac/model.py:332", "expect": "def act(self, inputs, deterministic=False):"},
    "ppg":   {"policy_mode": "STOCHASTIC (samples) -- `runnable/_launch/ppg_eval.py` now exists "
                          "and calls `PpoModel.act`, which samples; there is no deterministic-"
                          "action path in this repo to call instead "
                          "[found stale and corrected 2026-09-06: this entry said 'no evaluation "
                          "code exists' after the eval loop below had already been written -- "
                          "preprod_table.py's own ESTIMATOR dict already had 'ppg': 'SAMPLE' "
                          "correctly, so only this audit's description had drifted, not any "
                          "actual comparability decision]",
              "obs_scaling": "stateless", "running_stats": "RewardNormalizer is training-only and applied after logging",
              "reusable": "yes -- runnable/_launch/ppg_eval.py builds its own venv via get_venv "
                          "and reuses Roller/VecMonitor2, the same rollout/episode accounting "
                          "training uses",
              "anchor": "runnable/_launch/ppg_eval.py:75", "expect": "frame_stack=args.frame_stack"},
    "ibac_sni": {"policy_mode": "STOCHASTIC (samples) -- evaluate.py's `--argmax` is "
                             "store_true defaulting False, so the flag that would take the "
                             "mode is off unless asked for [resolved 2026-09-03]",
              "obs_scaling": "stateless",
              "running_stats": "none",
              "reusable": "yes in principle -- upstream keeps evaluation in scripts/evaluate.py by design",
              "anchor": "runnable/ibac_sni/torch_rl/scripts/train.py:233", "expect": "if update % args.log_interval == 0:"},
    "ctrl":  {"policy_mode": "deterministic (pi.mode) -- evaluate_ppo.py:84 calls select_action("
                         "..., greedy=True) and its greedy branch is logits.argmax(1) (:71-72), so "
                         "ctrl's RELEASED EVALUATOR takes the greedy action "
                         "[re-corrected 2026-09-07, external review 24 + owner verification]. "
                         "The 2026-09-04 entry this replaces cited train_ppo.py:244,:217 passing "
                         "sample=True -- but those are TRAINING calls, and the convention being "
                         "reproduced is the evaluation-time one. It dismissed evaluate_ppo.py's "
                         "helper as 'discrete-only and the wrong function to call'; that confuses "
                         "the helper's action-space support with its SELECTION RULE. The rule is "
                         "greedy, and pi.mode() is its continuous analogue",
              "obs_scaling": "stateless: state.astype(float32) / 255.",
              "running_stats": "none at eval -- evaluate_ppo passes normalize_rewards=False",
              "reusable": "ADAPT -- evaluate_ppo.py:67-74 calls a local discrete-only select_action "
                          "(logits.argmax / jax.random.categorical); algo.py:40-61 has one that "
                          "returns a DISTRIBUTION and does pi.mode() or pi.sample() for either "
                          "action space. Use algo.py's helper with sample=False: that preserves the "
                          "evaluator's GREEDY RULE while supporting the continuous action space",
              "anchor": "runnable/ctrl/evaluate_ppo.py:84",
              "expect": "action, value, rng = select_action(loaded_state, state, rng, greedy=True)"},
}
STATE["svea"] = STATE["drq"] = STATE["sgqn"] = STATE["curl"] = STATE["drqv2"]
STATE["soda"] = STATE["rad"]


def check() -> int:
    bad = []
    for baseline, entry in STATE.items():
        path, line = entry["anchor"].rsplit(":", 1)
        target = ROOT / path
        if not target.is_file():
            bad.append(f"{baseline}: {path} is missing")
            continue
        lines = target.read_text(errors="replace").splitlines()
        index = int(line.split("-")[0])
        window = lines[max(0, index - 4): index + 3]
        if not any(entry["expect"] in item for item in window):
            bad.append(f"{baseline}: {entry['anchor']} no longer reads {entry['expect']!r}")
    for message in bad:
        print("STALE  " + message)
    print(f"\n{len(STATE) - len(bad)}/{len(STATE)} audited anchors still hold.")
    return 1 if bad else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        return check()
    if args.json:
        print(json.dumps(STATE, indent=2))
        return 0
    print(f"{'baseline':10s} {'policy at evaluation':62s} own evaluator usable here")
    for baseline in sorted(STATE):
        entry = STATE[baseline]
        print(f"{baseline:10s} {entry['policy_mode'][:62]:62s} {entry['reusable'].split(' --')[0]}")
    print("\nTen of twelve reuse their own evaluation path. Two need work and NEITHER needs a policy")
    print("written: ctrl's eval loop calls a discrete-only helper while algo.select_action already")
    print("handles both action spaces, and ppg has the distribution but no loop around it.")
    print("The policy-mode axis is NOT uniform: idaac, ibac_sni and ppg SAMPLE, where the other")
    print("nine take a mode. THREE of twelve report a SAMPLED return -- a different quantity")
    print("from a mode return, usually lower, and not one a table may average over.")
    print("ppg's case is the weakest-evidenced: OpenAI ships no evaluation runner at all, so its")
    print("native rule rests on PpoModel.act(), a ROLLOUT convention, where every other family's")
    print("rule was read off a released EVALUATOR.")
    print()
    print("ctrl was 4-of-12 until 2026-09-07 and is now on the mode side. The 2026-09-04 entry")
    print("read train_ppo.py:244/:253 -- TRAINING calls -- and concluded ctrl sampled. Its own")
    print("evaluator is greedy: evaluate_ppo.py:84 passes greedy=True, whose branch is")
    print("logits.argmax(1). The earlier reading dismissed that helper as discrete-only and so")
    print("'the wrong function to call', which confuses the helper's action-space support with")
    print("its SELECTION RULE. The rule is greedy; pi.mode() is its continuous analogue.")
    print()
    print("Verified against each family's own EVALUATION path, not its API surface and not its")
    print("training loop: rlvigen five via train.py::_eval_regime's act(eval_mode=True);")
    print("rad/soda via src/train.py::evaluate -> select_action -> actor(compute_pi=False);")
    print("alda via its evaluate()'s select_action; idaac via test.py omitting deterministic;")
    print("ibac_sni via evaluate.py's --argmax default; ctrl via evaluate_ppo.py's greedy=True.")
    print("tests/test_native_policy_mode_provenance.py holds these against the vendored source.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
