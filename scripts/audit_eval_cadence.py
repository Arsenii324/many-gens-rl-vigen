#!/usr/bin/env python3
"""Per baseline: does training-time evaluation exist, how often, and over what? — C43 / C45 / R3.

## Why this exists

`audit_eval_axis.py` answers *which scenes* each baseline evaluates. It does not answer whether
the baseline evaluates **at all** during training, how often, or in how many regimes — and those
turn out to differ more than the scene axis does. A production configuration that sets one
`eval_every` and one `eval_episodes` across twelve baselines looks uniform and is fiction: five
families consume neither flag, and two run no periodic evaluation whatsoever.

That is the same error shape C45 records — a claim verified on one baseline generalised to the
set — so it gets the same remedy: make the claim enumerable, one row per baseline, derived from
the code rather than asserted in prose.

## What it reads, and what it cannot see

It finds calls whose name evaluates a policy (`evaluate`, `eval`, `_eval_regime`) and walks
outward to the nearest enclosing `if` whose test contains a `%` — the periodicity guard — and
reports that modulus expression verbatim. A call with no such guard is reported as unguarded,
which means either continuous evaluation or a single call at the end; the two are distinguished
by hand below and marked as audited rather than derived.

**The units are not derivable and are the whole point.** `idaac`'s modulus counts *updates*, each
worth `num_processes x num_steps` frames; `alda`'s counts environment steps; RL-ViGen's counts
frames. A cadence table that omits units invites exactly the comparison it cannot support, so
UNITS below carries a file:line for every entry and `--check` fails if the anchor stops matching.
"""
from __future__ import annotations

import argparse
import ast
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]

# The TRAINING ENTRY POINT per baseline, not its whole tree: scanning a repository catches
# `nn.Module.eval()` in every algorithm file and reports evaluation where there is none.
TREES = {
    "drqv2": "RL-ViGen-upstream/train.py", "svea": "RL-ViGen-upstream/train.py",
    "sgqn": "RL-ViGen-upstream/train.py", "curl": "RL-ViGen-upstream/train.py",
    "drq": "RL-ViGen-upstream/train.py",
    "rad": "runnable/dmc_gb/src/train.py", "soda": "runnable/dmc_gb/src/train.py",
    "alda": "runnable/alda/trainers/alda_trainer.py", "idaac": "runnable/idaac/train.py",
    "ctrl": "runnable/ctrl/train_ppo.py",
    "ibac_sni": "runnable/ibac_sni/torch_rl/scripts/train.py",
    "ppg": "runnable/ppg/phasic_policy_gradient/train.py",
}
EVAL_CALLS = ("evaluate", "eval", "_eval_regime", "_eval_single")
SKIP = ("__pycache__", "third_party", "/tests/", "coinrun", "gym-minigrid", "toy-classification")

# Audited, not derived: what the modulus counts, and the regimes one evaluation covers.
# `anchor` must still be found at `file`:`line` or --check fails.
UNITS = {
    "drqv2": {"file": "RL-ViGen-upstream/train.py", "line": 152, "unit": "frames",
              "anchor": "per = max(1, self.cfg.num_eval_episodes",
              "regimes": ["eval-easy x10 scenes", "train x scene 0"],
              "episodes": "num_eval_episodes // len(scenes), floored at 1 -- a TOTAL, not per-scene",
              "controllable": "eval_every_frames, num_eval_episodes"},
    "rad":   {"file": "runnable/dmc_gb/src/train.py", "line": 141, "unit": "steps",
              "anchor": "evaluate(test_env, agent, video, args.eval_episodes, L, step, test_env=True)",
              "regimes": ["train (env)", "--eval_mode (test_env)"],
              "episodes": "--eval_episodes, per regime",
              "controllable": "--eval_freq, --eval_episodes, --eval_mode"},
    "idaac": {"file": "runnable/idaac/train.py", "line": 271, "unit": "updates",
              "anchor": "eval_episode_rewards, eval_episode_successes = evaluate(",
              "regimes": ["eval-easy, from RLVIGEN_EVAL_MODE (test.py:29-30) -- but scene 0, so "
                          "the level split its Procgen lineage assumes does not exist here"],
              "episodes": "evaluate()'s internal default",
              "controllable": "--log_interval, in updates of num_processes x num_steps frames"},
    "alda":  {"file": "runnable/alda/trainers/alda_trainer.py", "line": 148, "unit": "steps",
              "anchor": "self.distract_env = _build('eval-hard')",
              "regimes": ["train (env)", "eval-easy (color_env)", "eval-hard (distract_env)"],
              "episodes": "n_eval_episodes = 10, per regime",
              "controllable": "spec override of eval_n_steps / n_eval_episodes"},
    "ctrl":  {"file": "runnable/ctrl/train_ppo.py", "line": 141, "unit": "continuous",
              "anchor": 'env_test_OOD = _mk("eval-easy"',
              "regimes": ["train (env_test_ID)", "eval-easy (env_test_OOD)"],
              "episodes": "not episodic: both test envs are stepped inside the training loop",
              "controllable": "no cadence exists to control"},
    "ibac_sni": {"file": "runnable/ibac_sni/torch_rl/scripts/train.py", "line": 206, "unit": "none",
              "anchor": "if update % args.log_interval == 0:",
              "regimes": [],
              "episodes": "none: training logs only. Evaluation is scripts/evaluate.py, offline.",
              "controllable": "n/a"},
    "ppg":   {"file": "runnable/ppg/phasic_policy_gradient/train.py", "line": 131, "unit": "none",
              "anchor": "parser.add_argument('--interacts_total'",
              "regimes": [],
              "episodes": "none: train.py evaluates nothing at any point",
              "controllable": "n/a"},
}
UNITS["svea"] = UNITS["drq"] = UNITS["sgqn"] = UNITS["curl"] = UNITS["drqv2"]
UNITS["soda"] = UNITS["rad"]


def is_periodicity_guard(test: ast.expr) -> bool:
    """A periodicity guard is a modulus test OR a call to an `Every`-style scheduler.

    RL-ViGen uses neither a modulus nor a flag: `eval_every_step = utils.Every(...)` at train.py:277
    and `if eval_every_step(self.global_step)` at 315. A modulus-only heuristic reports that as
    unguarded, which is a false negative on five of the twelve baselines -- the largest family.
    """
    if any(isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.Mod) for sub in ast.walk(test)):
        return True
    for sub in ast.walk(test):
        if isinstance(sub, ast.Call):
            name = sub.func.attr if isinstance(sub.func, ast.Attribute) else getattr(sub.func, "id", "")
            if "every" in name.lower() or "interval" in name.lower():
                return True
    return False


def guarded_eval_calls(root: pathlib.Path):
    """Every policy-evaluating call, with its nearest enclosing periodicity guard."""
    found = []
    files = [root] if root.is_file() else sorted(root.rglob("*.py"))
    for path in files:
        if any(s in str(path) for s in SKIP):
            continue
        try:
            text = path.read_text(errors="replace")
            tree = ast.parse(text)
        except (SyntaxError, OSError):
            continue
        parents = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            attribute = isinstance(node.func, ast.Attribute)
            name = node.func.attr if attribute else getattr(node.func, "id", "")
            if name not in EVAL_CALLS:
                continue
            # `self.eval()` is the training loop's evaluation; `self.actor.eval()` is
            # nn.Module.eval() putting a network in inference mode. Only the first is evaluation.
            if attribute and not isinstance(node.func.value, ast.Name):
                continue
            if attribute and node.func.value.id not in ("self",):
                continue
            guard, walker = None, parents.get(node)
            while walker is not None:
                if isinstance(walker, ast.If) and is_periodicity_guard(walker.test):
                    guard = ast.unparse(walker.test)
                    break
                walker = parents.get(walker)
            found.append({
                "file": str(path.relative_to(ROOT)), "line": node.lineno,
                "call": name, "guard": guard,
            })
    return found


def rows():
    for baseline, tree in TREES.items():
        calls = guarded_eval_calls(ROOT / tree)
        audited = UNITS[baseline]
        yield {
            "baseline": baseline,
            "eval_calls": len(calls),
            "guards": sorted({c["guard"] for c in calls if c["guard"]}),
            "unguarded_calls": sum(1 for c in calls if not c["guard"]),
            "cadence_unit": audited["unit"],
            "regimes": audited["regimes"],
            "regime_count": len(audited["regimes"]),
            "episodes": audited["episodes"],
            "controllable": audited["controllable"],
            "anchor": f"{audited['file']}:{audited['line']}",
        }


def check() -> int:
    """Every audited anchor must still be where the audit says it is."""
    bad = []
    for baseline, audited in UNITS.items():
        path = ROOT / audited["file"]
        if not path.is_file():
            bad.append(f"{baseline}: {audited['file']} is missing")
            continue
        lines = path.read_text(errors="replace").splitlines()
        window = lines[max(0, audited["line"] - 4): audited["line"] + 3]
        if not any(audited["anchor"] in line for line in window):
            bad.append(f"{baseline}: {audited['file']}:{audited['line']} no longer reads "
                       f"{audited['anchor']!r}")
    for message in bad:
        print("STALE  " + message)
    print(f"\n{len(UNITS) - len(bad)}/{len(UNITS)} audited anchors still hold.")
    return 1 if bad else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        return check()
    table = list(rows())
    if args.json:
        print(json.dumps(table, indent=2))
        return 0
    print(f"{'baseline':10s} {'evals':>5} {'regimes':>7} {'unit':11s} cadence guard")
    for row in table:
        guard = row["guards"][0] if row["guards"] else ("-" if row["cadence_unit"] == "none" else "unguarded")
        print(f"{row['baseline']:10s} {row['eval_calls']:5d} {row['regime_count']:7d} "
              f"{row['cadence_unit']:11s} {guard}")
    print("\nR3 note: three of twelve run no periodic training-time evaluation at all (ppg, "
          "ibac_sni: none; ctrl: continuous, not episodic), so 'metrics on the same axes' is not "
          "reachable from training logs by construction. It is reachable offline, from "
          "checkpoints, which is why the evaluator is a separate harness.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
