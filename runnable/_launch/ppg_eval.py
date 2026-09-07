"""Evaluate a saved PPG policy in an RL-ViGen visual regime.

    bash runnable/_launch/ppg.sh Door 8            # train; LogSaveHelper writes /tmp/ppg/model.jd
    python runnable/_launch/ppg_eval.py --model /tmp/ppg/model.jd --mode eval-easy --frame_stack 3

## Why this file exists, and why it is HERE and not in the clone

`ppg` is the only baseline of the twelve that reports no generalisation gap. Its `train.py` builds
one venv and never evaluates; the paper evaluates in separate runs. It *saves* -- `LogSaveHelper`
does `th.save(self.model, ...)`, the whole model pickled -- but ships **no loader and no
evaluation entry point at all**. `graph.py` plots CSVs; nothing else reads a checkpoint. (Checked:
the only `load` in the package is a comment in `impala_cnn.py`.)

So the gap has to be closed by something we write. This is that thing, and it lives under
`runnable/_launch/` on purpose: it changes **zero lines** in the clone, and the ledger
(`scripts/deviations.py`) stays an honest account of what was done to the original.

## What it reuses rather than reimplements

Everything that could bias a number: `get_venv` builds the env through the same guarded branch
training uses; `Roller` and `VecMonitor2` are PPG's own rollout and episode accounting, so
returns and lengths are accumulated by the authors' code; `PpoModel.act` is the policy's own
sampling path. The only thing here is the loop that stops after N episodes.

## What it does NOT do, stated because it changes the number

**It samples; it does not take the mode.** `PpoModel.act` draws from the policy distribution, and
there is no deterministic-action path in this repo to call instead. Every other baseline's eval
in this project is likewise stochastic except where its own code offers a mode, so this is
consistent -- but it is a choice, and a Gaussian policy's mean would give a different (usually
higher) number.

**Checkpoint selection is `--model`, i.e. yours.** `Protocol.checkpoint_selection` exists for
this and is unset for `ppg`; nothing here decides it.

**Observation geometry is explicit.** Current production C2 defaults to three RGB frames (9
channels). Pass `--frame_stack 1` only when evaluating a historical C1 checkpoint.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ppg"))

import numpy as np
import torch as th

from phasic_policy_gradient import torch_util as tu
from phasic_policy_gradient.envs import get_venv
from phasic_policy_gradient.roller import Roller


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, help="path written by LogSaveHelper.save()")
    ap.add_argument("--task", default="Door")
    ap.add_argument("--mode", default="eval-easy",
                    help="RL-ViGen visual regime: train | eval-easy | eval-medium | eval-hard")
    ap.add_argument("--num_envs", type=int, default=4)
    ap.add_argument("--episodes", type=int, default=10)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--frame_stack", type=int, default=3,
                    help="RGB frames to concatenate; 3 is current C2, 1 is explicit historical C1")
    args = ap.parse_args()

    # weights_only=False: LogSaveHelper pickles the whole model, not a state_dict, so torch>=2.6's
    # default refuses it. The checkpoint is one this project produced.
    model = th.load(args.model, map_location=tu.dev(), weights_only=False)
    model.eval()

    venv = get_venv(num_envs=args.num_envs, env_name=f"robosuite:{args.task}",
                    mode=args.mode, seed=args.seed, frame_stack=args.frame_stack)
    roller = Roller(venv=venv, act_fn=model.act,
                    initial_state=model.initial_state(args.num_envs),
                    keep_buf=max(100, args.episodes))

    # Step until enough episodes have CLOSED. VecMonitor2 records an episode when its env resets,
    # so counting `episode_count` -- not steps -- is what makes the sample size the requested one.
    while roller.episode_count < args.episodes:
        roller.multi_step(32)

    rets = np.array(roller.recent_eprets[:args.episodes], dtype=np.float64)
    lens = np.array(roller.recent_eplens[:args.episodes], dtype=np.float64)
    infos = roller.recent_epinfos[:args.episodes]
    succ = np.array([float(i.get("episode_success", np.nan)) for i in infos], dtype=np.float64)

    print(f"\nppg eval | task={args.task} mode={args.mode} episodes={len(rets)} "
          f"envs={args.num_envs} seed={args.seed}")
    print(f"  episode_reward mean/median : {rets.mean():.4f} / {np.median(rets):.4f}")
    print(f"  episode_length mean        : {lens.mean():.1f}")
    print(f"  success_rate               : "
          + ("nan (no success key -- is RL-ViGen patch P10 applied?)"
             if np.isnan(succ).all() else f"{np.nanmean(succ):.4f}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
