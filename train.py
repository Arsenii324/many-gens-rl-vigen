#!/usr/bin/env python3
"""One entry point for every baseline.

    python train.py --config drqv2
    python train.py --config drqv2 --task Lift --seed 1
    python train.py --config drqv2 --smoke          # same code, tiny budget
    python train.py --list                          # what exists and what does not

The launch scripts under `baselines/<name>/train.sh` call this and nothing else. A baseline is
selected by naming a CONFIG in `configs/vigen.yaml`; the config carries `baseline`, which the
registry resolves. That indirection is what makes "the same training length for everyone" a
default you must opt out of in a diffable file, rather than a convention.

This script contains NO evaluation logic and no logging keys. It parses arguments, builds a
Protocol, and calls the shared trainer.
"""
from __future__ import annotations

import argparse
import os
import sys

import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from rlgen import registry  # noqa: E402
from rlgen.protocol import Protocol  # noqa: E402
from rlgen.trainer import TrainConfig, train  # noqa: E402
from rlgen.trainer_onpolicy import train_onpolicy  # noqa: E402

CONFIG_PATH = os.path.join(ROOT, "configs", "vigen.yaml")

#: Keys of `Protocol`. Everything else in a config entry belongs to the trainer or the agent.
PROTOCOL_KEYS = {
    "task", "total_frames", "eval_every_frames", "eval_mode", "train_mode", "episodes_per_scene",
    "policy_mode", "aggregation", "seed", "image_size", "frame_stack", "action_repeat", "horizon",
    "eval_scene_ids", "train_scene_ids", "checkpoint_selection", "reward_shaping", "name",
}
TRAINER_KEYS = {
    "batch_size", "replay_capacity", "num_seed_frames", "update_every_frames", "nstep",
    "discount", "device", "save_every_frames", "backend",
}


def load_config(name: str) -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        allcfg = yaml.safe_load(f)
    if name not in allcfg:
        raise SystemExit(f"no config {name!r} in {CONFIG_PATH}. "
                         f"Available: {', '.join(k for k in allcfg if k not in ('base', 'smoke'))}")
    cfg = dict(allcfg[name])
    cfg.setdefault("baseline", name)
    return cfg


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", help="entry in configs/vigen.yaml")
    ap.add_argument("--task", choices=["Door", "Lift"])
    ap.add_argument("--seed", type=int)
    ap.add_argument("--total-frames", type=int)
    ap.add_argument("--eval-mode")
    ap.add_argument("--device", default="auto", help="auto|cpu|mps|cuda")
    ap.add_argument("--backend", default="robosuite", choices=["robosuite", "synthetic"],
                    help="'synthetic' runs the identical pipeline without mujoco; for tests only")
    ap.add_argument("--logdir", default=os.path.join(ROOT, "logs"))
    ap.add_argument("--smoke", action="store_true",
                    help="tiny budget through the SAME code path; used by tests and by "
                         "baselines/*/train.sh --smoke")
    ap.add_argument("--list", action="store_true", help="print the baseline status table and exit")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if args.list:
        print(registry.status_table())
        print(f"\nrunnable: {', '.join(registry.runnable())}")
        print("A baseline marked `absent` is named in the supervisor's brief and not implemented "
              "here.\nSee rlgen/registry.py for why, per baseline.")
        return 0

    if not args.config:
        ap.error("--config is required (or use --list)")

    cfg = load_config(args.config)
    if args.smoke:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg.update(yaml.safe_load(f)["smoke"])
    for k, v in (("task", args.task), ("seed", args.seed), ("total_frames", args.total_frames),
                 ("eval_mode", args.eval_mode)):
        if v is not None:
            cfg[k] = v

    baseline = cfg.pop("baseline")
    protocol = Protocol(name=args.config,
                        **{k: v for k, v in cfg.items() if k in PROTOCOL_KEYS})
    tcfg = TrainConfig(device=args.device, backend=args.backend,
                       **{k: v for k, v in cfg.items() if k in TRAINER_KEYS})
    hyper = {k: v for k, v in cfg.items()
             if k not in PROTOCOL_KEYS and k not in TRAINER_KEYS}

    from rlgen.logging_ import run_dir
    logdir = run_dir(args.logdir, protocol, baseline)

    spec = registry.get(baseline)
    if not spec.trainable:
        print(f"baseline {baseline!r}: status {spec.status!r} -- not trainable.\n  {spec.notes}")
        if spec.status == "alias":
            print(f"  It IS runnable for evaluation as an alias of {spec.alias_of!r}; "
                  f"train that instead and label the row as an alias.")
        return 2

    # On-policy methods consume rollouts, not replay batches. The registry says which, so the
    # choice is not a per-baseline branch anyone has to remember.
    runner = train_onpolicy if getattr(spec, "on_policy", False) else train
    runner(protocol, baseline, tcfg, hyper, logdir, verbose=not args.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
