#!/usr/bin/env python3
"""Per baseline: how many evaluation scenes, and how many visual regimes? — C45 / C43.

## Why this exists

P14 gave `RL-ViGen-upstream/train.py` a ten-scene sweep and a train-regime denominator, and
`tests/test_p14_eval_axis.py` pins it. That covers **five** baselines. The other seven have their
own training loops and were not touched — and on 2026-08-19 C45 and C43 were briefly marked
RESOLVED as though all twelve were done. Four of the seven still pin `scene_id=0`.

The error was possible because the claim "we evaluate ten scenes" had no per-baseline form. A
patch was verified on one baseline and the conclusion was drawn about the set. So the fix is not
"be more careful": it is to make the claim enumerable, one row per baseline, computed from the
code that builds each env.

## What it reads, and what it cannot see

It finds calls that construct a robosuite env — `robo_make`, `make_env`, `_robo_make_env` — and
reports, per baseline, whether `scene_id` is a literal `0` (pinned) or an expression (variable),
and how many distinct `mode` values reach construction.

**A variable `scene_id` is not proof of a sweep**, only that a sweep is expressible; and a literal
`0` IS proof of a pin. So the pinned column is a verdict and the swept column is a lead. That
asymmetry is the same one the determinism fingerprints had, and it is stated for the same reason.
"""
from __future__ import annotations

import argparse
import ast
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

# baseline -> the tree whose env construction serves it
TREES = {
    "drqv2": "RL-ViGen-upstream", "svea": "RL-ViGen-upstream", "sgqn": "RL-ViGen-upstream",
    "curl": "RL-ViGen-upstream", "drq": "RL-ViGen-upstream",
    "rad": "runnable/dmc_gb", "soda": "runnable/dmc_gb",
    "alda": "runnable/alda/trainers", "idaac": "runnable/idaac/ppo_daac_idaac",
    "ctrl": "runnable/ctrl", "ibac_sni": "runnable/ibac_sni/torch_rl",
    "ppg": "runnable/ppg/phasic_policy_gradient",
}
MAKERS = ("robo_make", "make_env", "_robo_make_env", "_robo")
SKIP = ("__pycache__", "third_party", "/tests/", "coinrun", "gym-minigrid")


def maker_calls(root: pathlib.Path):
    for f in sorted(root.rglob("*.py")):
        if any(s in str(f) for s in SKIP):
            continue
        try:
            tree = ast.parse(f.read_text(errors="replace"))
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            if not isinstance(n, ast.Call):
                continue
            fn = n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
            if fn in MAKERS:
                yield f, n


def audit_one(name: str) -> dict:
    root = ROOT / TREES[name]
    pinned = swept = 0
    modes: set[str] = set()
    mode_is_variable = False
    for _f, call in maker_calls(root):
        kw = {k.arg: k.value for k in call.keywords if k.arg}
        if "scene_id" in kw:
            v = kw["scene_id"]
            if isinstance(v, ast.Constant) and v.value == 0:
                pinned += 1
            else:
                swept += 1
        if "mode" in kw:
            v = kw["mode"]
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                modes.add(v.value)
            else:
                mode_is_variable = True
    # A non-literal `scene_id=` argument only shows a sweep is EXPRESSIBLE. Six trees thread a
    # parameter that nothing ever moves, and reading that as "sweeps" is how the five-of-twelve
    # overclaim happened in the first place. So sweeping additionally requires evidence of
    # variation in the tree: an iteration over scenes, or a list of them.
    import re as _re
    txt = "\n".join(f.read_text(errors="replace") for f in root.rglob("*.py")
                    if not any(x in str(f) for x in SKIP))
    varies = bool(_re.search(r"for\s+\w*scene\w*\s+in|scene_ids\s*=|RLVIGEN_EVAL_SCENES", txt))
    return {"baseline": name, "tree": TREES[name], "scene_pinned": pinned,
            "scene_expressible": swept, "scene_varied": varies,
            "sweeps": bool(varies and swept), "literal_modes": sorted(modes),
            "mode_variable": mode_is_variable}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    rows = [audit_one(n) for n in TREES]
    if a.json:
        print(json.dumps(rows, indent=2))
        return 0
    print(f"  {'baseline':<10}{'scene_id':<22}{'regimes reaching make':<34}tree")
    print("  " + "-" * 92)
    for r in rows:
        if r["sweeps"]:
            scene = "SWEEPS (varied)"
        elif r["scene_expressible"]:
            scene = "threaded, never varied"
        elif r["scene_pinned"]:
            scene = f"PINNED 0 ({r['scene_pinned']} site)"
        else:
            scene = "no scene_id passed"
        m = ", ".join(r["literal_modes"]) or "-"
        if r["mode_variable"]:
            m = (m + " + variable").lstrip("- ")
        print(f"  {r['baseline']:<10}{scene:<22}{m:<34}{r['tree']}")
    sweep = [r["baseline"] for r in rows if r["sweeps"]]
    print(f"\n  sweeps the scene axis: {', '.join(sweep) if sweep else 'none'}  "
          f"({len(sweep)} of {len(rows)})")
    print("  Everything else evaluates ONE scene -- either pinned to a literal 0, or threading a")
    print("  parameter that nothing in its tree ever moves. Both are single-scene in practice.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
