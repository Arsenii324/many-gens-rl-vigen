#!/usr/bin/env python3
"""What every baseline ACTUALLY constructs, as opposed to what the config appears to say.

    python tools/dump_constructed_hyperparams.py            # table
    python tools/dump_constructed_hyperparams.py --json     # machine-readable

WHY THIS EXISTS. `configs/vigen.yaml` presents a single shared `base` with one learning rate and a
short per-baseline deviation list. That presentation is wrong, and the difference is not visible by
reading the file:

  * `_drqv2_family` reads `hyper.get("lr", 1e-4)`, so `lr` reaches drqv2/svea/sgqn/curl/drq.
  * `_sac_family` filters with `if k in SAC_DEFAULTS`, and `lr` is NOT a key there (the SAC stack
    names its rates `actor_lr`/`critic_lr`/`alpha_lr`). So `lr` is silently DROPPED for rad/soda,
    which then run at SAC_DEFAULTS' 1e-3 -- ten times the configured value.
  * `_alda_build` and the four on-policy hermetic builders (`_ppg_hermetic_build`,
    `_ibac_sni_hermetic_build`, `_ctrl_hermetic_build`, plus `idaac`'s own inline construction)
    each filter with `if hasattr(cfg, k)`, each dropping a different subset.

The result is a 10x learning-rate split across the table produced entirely by silent key drops --
the same failure family as docs/RIGOR.md section 6.8, "operations that fail by doing nothing".

This script was originally two throwaway heredocs during the 2026-08-10 audit, and its output was
transcribed by hand into docs/PREMISES.md P8. That left a committed measurement with no
reproducible artifact behind it, which is exactly what docs/RIGOR.md section 5 forbids. Promoting
it here makes the claim re-runnable after any config change, and
`tests/test_contract.py::test_constructed_learning_rates_match_the_recorded_audit` asserts against
it so a future silent drop fails the build instead of waiting for the next audit.

NOTE ON METHOD. Adapters hide their agent behind different private handles (`_m` for SacAdapter,
`learner` for PPOFamilyAdapter, and DrQV2Adapter wraps the upstream agent directly), so this walks
a small set of known handles rather than guessing. If a new adapter appears and its optimizers do
not show up, add its handle to `_HANDLES` -- a silently empty row is the failure mode to avoid.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

#: Attribute names under which an adapter may keep the object that owns the optimizers.
_HANDLES = ("_m", "learner", "_a", "agent", "_agent", "policy")

PROTOCOL_KEYS = {
    "task", "total_frames", "eval_every_frames", "eval_mode", "train_mode", "episodes_per_scene",
    "policy_mode", "aggregation", "seed", "image_size", "frame_stack", "action_repeat", "horizon",
    "eval_scene_ids", "train_scene_ids", "checkpoint_selection", "reward_shaping", "name",
}
TRAINER_KEYS = {
    "batch_size", "replay_capacity", "num_seed_frames", "update_every_frames", "nstep",
    "discount", "device", "save_every_frames", "backend",
}


def _optimizers(obj, depth: int = 0) -> dict[str, list[float]]:
    """-> {attribute name: sorted distinct param-group learning rates}."""
    import torch
    found: dict[str, list[float]] = {}
    if obj is None or depth > 2:
        return found
    for name in dir(obj):
        if name.startswith("__"):
            continue
        try:
            v = getattr(obj, name)
        except Exception:
            continue
        if isinstance(v, torch.optim.Optimizer):
            found[name] = sorted({float(g["lr"]) for g in v.param_groups})
    if not found:
        for h in _HANDLES:
            inner = getattr(obj, h, None)
            if inner is not None and not isinstance(inner, (str, int, float, bool)):
                found.update(_optimizers(inner, depth + 1))
                if found:
                    break
    return found


def collect() -> dict:
    import yaml

    from rlgen import registry
    from rlgen.protocol import Protocol

    cfg_all = yaml.safe_load(open(os.path.join(ROOT, "configs", "vigen.yaml"), encoding="utf-8"))
    protocol = Protocol(task="Door", total_frames=0)
    out: dict[str, dict] = {}
    for name in sorted(registry.runnable()):
        spec = registry.get(name)
        entry = dict(cfg_all.get(name, {}))
        entry.pop("baseline", None)
        hyper = {k: v for k, v in entry.items()
                 if k not in PROTOCOL_KEYS and k not in TRAINER_KEYS}
        rec: dict = {"backbone": spec.backbone,
                     "config_lr": entry.get("lr"),
                     "hyper_keys_passed": sorted(hyper)}
        try:
            agent = spec.build(protocol, protocol.obs_shape, 7, "cpu", {**hyper, "seed": 0})
        except Exception as e:  # a baseline that cannot be built is a finding, not a crash
            rec["error"] = f"{type(e).__name__}: {e}"
            out[name] = rec
            continue
        opts = _optimizers(agent)
        rec["optimizers"] = {k: (v[0] if len(v) == 1 else v) for k, v in sorted(opts.items())}
        rec["adapter"] = type(agent).__name__
        out[name] = rec
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    os.environ.setdefault("MUJOCO_GL", "glfw" if sys.platform == "darwin" else "egl")
    data = collect()

    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
        return 0

    print(f"{'baseline':10s} {'backbone':9s} {'config lr':>10s}  optimizers actually constructed")
    print("-" * 96)
    for name, rec in data.items():
        if "error" in rec:
            print(f"{name:10s} {rec['backbone']:9s} {'':>10s}  BUILD FAILED: {rec['error']}")
            continue
        opts = rec["optimizers"]
        shown = ", ".join(f"{k}={v:g}" if isinstance(v, float) else f"{k}={v}"
                          for k, v in opts.items())
        cl = "-" if rec["config_lr"] is None else f"{rec['config_lr']:g}"
        print(f"{name:10s} {rec['backbone']:9s} {cl:>10s}  {shown or '(none found -- see _HANDLES)'}")

    rates: dict[float, list[str]] = {}
    for name, rec in data.items():
        for k, v in rec.get("optimizers", {}).items():
            if isinstance(v, float) and ("actor" in k or "policy" in k):
                rates.setdefault(v, []).append(name)
    if len(rates) > 1:
        print("\nDISTINCT ACTOR/POLICY LEARNING RATES ACROSS THE TABLE:")
        for lr in sorted(rates):
            print(f"  {lr:<10g} {', '.join(sorted(set(rates[lr])))}")
        print("\nconfigs/vigen.yaml shows ONE learning rate. See docs/PREMISES.md P8.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
