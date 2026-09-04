#!/usr/bin/env python3
"""Train ALDA with an entry point shaped like DZ's own `Nd_ln.py` — the CLI flag names,
the periodic single-scene eval feed, the console output shape — over this repo's own verified
training loop. Wraps; does not reimplement.

    python nd_ln_style_train.py --seed 0 --total_timesteps 500000
    python nd_ln_style_train.py --task_name Door --eval_frequency 50000 --eval_episodes 10

WHY THIS EXISTS, AND WHY IT IS NOT A REWRITE OF `Nd_ln.py`. DZ's brief asks for our training/eval
pipeline to be based on `Nd_ln.py`'s architecture. Read directly (the sibling gen-rebuttal
project's `ext/alda/Nd_ln.py`, and its own `DISCREPANCY_MATRIX.md`), that script trains a
DIFFERENT method from ALDA -- a disentangled encoder plus a gradient-reversal background
discriminator, not ALDA's VQ codebook (DISCREPANCY_MATRIX.md T11/X6 calls it correctly "a 3rd
distinct algorithm rather than an ALDA baseline") -- and its OWN protocol has measured, documented
defects: single-scene evaluation (E1, ~64% relative standard error against the 10-scene mean on
this exact benchmark), no truncation bootstrapping at the horizon (T1, which is why SAC trained
poorly in it), and an update-to-data ratio 4x too high once `action_repeat` changes from 4 to 1
(T6 -- the exact `AldaConfig.utd` bug this repo fixed 2026-08-13, independently confirmed by the
sibling project's real GPU runs). Reimplementing Nd_ln.py's shape from scratch would mean
reimplementing its measured defects along with it, on top of running the wrong algorithm.

The `faithful_nd_ln.py` lineage in the sibling project already learned this the hard way: its
first revision reimplemented SAC/ALDA to match Nd_ln.py's shape and every one of ten found bugs
lived in the reimplementation; its later revisions abandoned that and became a thin driver that
CALLS the already-audited agent directly ("do not restate the reference; call it").

So this script does the same thing, for THIS repo's already-verified ALDA port
(`rlgen/algos/alda/agent.py`, byte-identical to the sibling project's own audited version --
`docs/FAITHFULNESS.md` sec. alda). It is a CLI- and console-output-level adapter, not a second
training loop: every line below that touches the environment, the replay buffer, the optimiser or
the evaluation protocol calls straight into `rlgen.trainer.train`, the SAME function
`train.py --config alda` calls. Nothing here can silently diverge from the verified path, because
there is no second path -- only a second set of argument names and a second-shaped printout on
top of the first.

WHAT IS DELIBERATELY *NOT* CHANGED. The full 10-scene, 100-episode evaluation protocol still runs
and still gets written to `episodes.csv` exactly as it does for every other baseline -- this
script adds a periodic single-scene READ of that same data for its Nd_ln-shaped console feed
(`tools/nd_ln_parity.py`'s own principle: report both aggregations from one measurement, never
run a second one). `--eval_episodes` maps to `episodes_per_scene`, not to a narrower protocol.
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    # Names mirror Nd_ln.py's own argparse block (ext/alda/Nd_ln.py:357-370 in the sibling
    # project) wherever a corresponding concept exists in this repo. Nd_ln.py's noise-scheduler
    # flags (--noise_strategy, --target_noise, --step_switch, --cycles, --q) are that OTHER
    # method's own mechanism -- ALDA has no such thing, so they are not reproduced here; adding
    # them would be inventing a knob this baseline does not have, exactly the failure class this
    # project's audits keep finding in others.
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--total_timesteps", type=int, default=500_000,
                    help="frames, with action_repeat folded in -- same accounting as every "
                         "other baseline in this repo (rlgen/trainer.py's own docstring)")
    ap.add_argument("--task_name", type=str, default="Door", choices=["Door", "Lift"])
    ap.add_argument("--train_mode", type=str, default="train")
    ap.add_argument("--eval_mode", type=str, default="eval-easy")
    ap.add_argument("--eval_frequency", type=int, default=50_000)
    ap.add_argument("--eval_episodes", type=int, default=10,
                    help="episodes PER SCENE, all 10 scenes still evaluated -- see the module "
                         "docstring for why this is not a protocol narrowing")
    ap.add_argument("--device", default="auto", help="auto|cpu|mps|cuda")
    ap.add_argument("--backend", default="robosuite", choices=["robosuite", "synthetic"])
    ap.add_argument("--logdir", default=os.path.join(ROOT, "logs"))
    ap.add_argument("--quiet", action="store_true")
    return ap.parse_args(argv)


def seed_everything(seed: int) -> None:
    """FOUND 2026-08-14 by the differential test below: `rlgen.trainer.train`/`train_onpolicy`
    did not seed torch's global RNG before construction, so weight initialisation depended on
    ambient process state, not on the declared seed. FIXED there (rlgen/trainer.py,
    rlgen/trainer_onpolicy.py); duplicated here because `_canonical_alda_agent` and
    `preflight_check` build agents DIRECTLY through the registry, bypassing `train()`'s own
    preamble entirely (that is the point -- they compare construction in isolation from
    training), so they must reproduce the same seeding step by hand."""
    import random
    import numpy as np
    import torch
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)
    random.seed(seed)


def _canonical_alda_agent(seed: int, device: str = "cpu"):
    """Builds ALDA the way `train.py --config alda` does: read `configs/vigen.yaml`'s `alda:`
    block through the SAME key-filtering `train.py` uses, and construct through the registry.
    The single source of truth for "what does the canonical path build" -- both
    `preflight_check` below and `tests/test_nd_ln_style_train.py`'s differential tests call this,
    so there is exactly one definition of "canonical" to drift out of sync, not two."""
    import yaml
    from rlgen import registry
    from rlgen.protocol import Protocol

    with open(os.path.join(ROOT, "configs", "vigen.yaml"), encoding="utf-8") as f:
        allcfg = yaml.safe_load(f)
    cfg = dict(allcfg["alda"])
    cfg.pop("baseline", None)
    PROTOCOL_KEYS = {"task", "total_frames", "eval_every_frames", "eval_mode", "train_mode",
                     "episodes_per_scene", "policy_mode", "aggregation", "seed", "image_size",
                     "frame_stack", "action_repeat", "horizon", "eval_scene_ids",
                     "train_scene_ids", "checkpoint_selection", "reward_shaping", "name"}
    TRAINER_KEYS = {"batch_size", "replay_capacity", "num_seed_frames", "update_every_frames",
                    "nstep", "discount", "device", "save_every_frames", "backend"}
    hyper = {k: v for k, v in cfg.items() if k not in PROTOCOL_KEYS and k not in TRAINER_KEYS}
    protocol = Protocol(name="alda_canonical", task="Door", total_frames=0)
    seed_everything(seed)
    return registry.get("alda").build(protocol, protocol.obs_shape, 7, device,
                                      {**hyper, "seed": seed})


def preflight_check(seed: int = 0) -> tuple:
    """MONITORING, not just testing: this runs at every real invocation of this script, before
    any environment or GPU time is spent, and compares the hyperparameters this wrapper's OWN
    construction path (registry.get("alda").build with only {"seed": ...} as hyper, exactly what
    main() below does) would produce against the canonical train.py-equivalent path above.

    Returns (ok, human_readable_report). The report always NAMES the fields it checked -- an
    opaque "OK" proves nothing was actually compared; naming utd/action_repeat/init_steps/lr
    means a human reading the console output, or a future edit reviewer, can see exactly what
    was verified rather than trusting a green checkmark.
    """
    from dataclasses import asdict, fields
    from rlgen import registry
    from rlgen.protocol import Protocol

    canonical = _canonical_alda_agent(seed)
    protocol = Protocol(name="nd_ln_style_preflight", task="Door", total_frames=0)
    seed_everything(seed)
    via_wrapper = registry.get("alda").build(protocol, protocol.obs_shape, 7, "cpu",
                                             {"seed": seed})

    cfg_a, cfg_b = asdict(canonical._m.cfg), asdict(via_wrapper._m.cfg)
    checked = sorted(cfg_a)
    mismatches = {k: (cfg_a[k], cfg_b[k]) for k in checked if cfg_a.get(k) != cfg_b.get(k)}
    watch = ("utd", "action_repeat", "lr", "init_steps", "buffer_capacity", "num_latents")
    report = (f"checked {len(checked)} AldaConfig fields (incl. {', '.join(watch)}); "
             f"{len(mismatches)} mismatch(es)"
             + (f": {mismatches}" if mismatches else ""))
    return not mismatches, report


def main(argv=None) -> int:
    args = parse_args(argv)

    from rlgen import registry
    from rlgen.logging_ import run_dir
    from rlgen.protocol import Protocol
    from rlgen.trainer import TrainConfig, train

    protocol = Protocol(
        name="nd_ln_style", task=args.task_name, total_frames=args.total_timesteps,
        eval_every_frames=args.eval_frequency, eval_mode=args.eval_mode,
        train_mode=args.train_mode, episodes_per_scene=args.eval_episodes, seed=args.seed)
    cfg = TrainConfig(device=args.device, backend=args.backend)

    spec = registry.get("alda")
    if not spec.trainable:
        print(f"alda: status {spec.status!r} -- not trainable.\n  {spec.notes}", file=sys.stderr)
        return 2

    # MONITORING LAYER (c): refuse to spend a single environment step under a silently-drifted
    # hyperparameter set. Cheap -- two CPU-only agent constructions, no environment involved --
    # and it is exactly the class of check `predictions.py` in the sibling gen-rebuttal project
    # runs before every real launch there ("nothing expensive starts on an unverified decision").
    ok, report = preflight_check(seed=args.seed)
    if not args.quiet:
        print(f"[nd_ln_style_train] preflight: {report}")
    if not ok:
        print(f"[nd_ln_style_train] PREFLIGHT FAILED -- refusing to train under a "
              f"hyperparameter set that disagrees with the canonical alda registry path.\n"
              f"  {report}", file=sys.stderr)
        return 3

    logdir = run_dir(args.logdir, protocol, "alda")
    if not args.quiet:
        print(f"[nd_ln_style_train] ALDA on {protocol.task} | seed {args.seed} | "
              f"{protocol.total_frames:,} frames | protocol {protocol.hash()}")
        print(f"[nd_ln_style_train] eval every {args.eval_frequency:,} frames, "
              f"{args.eval_episodes} episodes/scene x 10 scenes (full protocol; "
              f"see module docstring)")
        print(f"[nd_ln_style_train] this calls rlgen.trainer.train() directly -- the SAME "
              f"function `python train.py --config alda` calls. No second training loop exists.")

    train(protocol, "alda", cfg, {"seed": args.seed}, logdir, verbose=not args.quiet)

    _print_nd_ln_shaped_summary(logdir, quiet=args.quiet)
    return 0


def _print_nd_ln_shaped_summary(logdir: str, *, quiet: bool) -> None:
    """The Nd_ln-recognisable final printout: `eval_metrics/episode_return` etc., DZ's own tag
    names (`Nd_ln.py::log_eval_metrics`), for the LAST evaluated checkpoint -- read from the
    episodes.csv the training loop already wrote, via the same reader `tools/nd_ln_parity.py`
    uses, so there is exactly one measurement and two ways of printing it."""
    if quiet:
        return
    from tools.nd_ln_parity import load_episodes, group_by_run, nd_ln_parity_row

    rows = load_episodes(logdir)
    if not rows:
        print("[nd_ln_style_train] no episodes.csv rows found under the run directory -- "
              "nothing to summarise (a total_timesteps below the first eval point, most likely)")
        return
    groups = group_by_run(rows)
    last_key = max(groups, key=lambda k: int(k[3]))
    r = nd_ln_parity_row(groups[last_key], min_train_denominator=1.0)

    print(f"\n[nd_ln_style_train] final checkpoint at {last_key[3]} frames -- "
          f"Nd_ln-shaped eval_metrics (scene 0 only, {r['n_eval_scene0_episodes']} episodes, "
          f"mean; full 10-scene protocol logged separately in episodes.csv):")
    print(f"  eval_metrics/episode_return   {r['eval_scene0_mean']}")
    ep_lens = [float(row["episode_len"]) for row in groups[last_key]
              if row["mode"] == "eval-easy" and row["scene_id"] == "0"]
    print(f"  eval_metrics/episode_length   "
          f"{(sum(ep_lens) / len(ep_lens)) if ep_lens else None}")
    print(f"  train_scene0/episode_return    {r['train_scene0_mean']}")
    print(f"  retention (scene-0-only, DZ-parity)     {r['retention_nd_ln_parity']}")
    print(f"  retention (10-scene, this repo's protocol)  {r['retention_full_protocol']}")
    print(f"  [tools/nd_ln_parity.py {logdir}  -- full per-checkpoint table]")


if __name__ == "__main__":
    sys.exit(main())
