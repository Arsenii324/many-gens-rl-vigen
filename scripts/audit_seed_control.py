#!/usr/bin/env python3
"""Does a seed actually control each baseline's run? -- `docs/CONSTRUCTION.md` C20, screen (a).

The 5-seed plan assumes two things nobody has checked for any of the twelve: that each trainer
*has* a seed knob, and that the knob is *wired to the RNGs*. Those are different claims, and the
gap between them is not hypothetical -- the TorchRL sweep found `ppo`, `a2c` and `impala` shipped
with no seed argument at all while their paper reported five seeds
(`docs/library-survey/raw/torchrl.md` 2.2).

## What this establishes, and what it cannot

This is a **static** screen. It reads source and answers "is there a path from the declared seed
to an RNG call". It therefore catches the strong failure -- a declared-but-unconsumed seed, or no
seed at all -- and it CANNOT establish determinism, because a seeded run can still diverge
through nondeterministic kernels, thread scheduling, or an unseeded third RNG. Determinism is
screen (b) and needs runs, not reading.

A pass here is necessary, not sufficient. Read the verdicts accordingly.

## Why one-hop imports

Scanning a whole tree overstates coverage: `RL-ViGen-upstream` carries 724 Python files, most of
them CARLA and Habitat code no robosuite run touches, and a `manual_seed` in an unreached file is
not evidence about the live path. So the verdict is computed over the entry file plus the modules
it directly imports, which is where seeding is conventionally done. Sites further out are still
counted and reported separately, as context -- a tree whose only seeding lives four hops away is
telling you something, just not something this screen can call a pass.

## The distinction that carries the finding

`torch.manual_seed(args.seed)` is seed-controlled. `torch.manual_seed(0)` is not, however
prominently it appears. The check is on the *argument*, never on the presence of the call.
"""
from __future__ import annotations

import argparse
import ast
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]

# tree -> (root, entry file relative to root, baselines, extra live-path dirs)
#
# `extra` exists because a static import walk cannot follow a DYNAMIC import. ALDA's entry does
# `importlib.import_module(spec['module'])` with the module named in a yaml spec, so `trainers/`
# is on the live path and no amount of AST walking will discover that. Listing it is a declared
# assumption, not a guess -- and a wrong entry here shows up as a tree whose seeding sites sit in
# files the run never imports, which is worth catching too.
TREES = {
    "upstream":  ("RL-ViGen-upstream",        "train.py",
                  ["drqv2", "svea", "sgqn", "curl", "drq"], []),
    "dmc_gb":    ("runnable/dmc_gb",          "src/train.py",       ["rad", "soda"], []),
    "alda":      ("runnable/alda",            "scripts/train.py",   ["alda"],
                  ["trainers"]),
    "ctrl":      ("runnable/ctrl",            "train_ppo.py",       ["ctrl"], []),
    "idaac":     ("runnable/idaac",           "train.py",           ["idaac"], []),
    "ppg":       ("runnable/ppg",             "phasic_policy_gradient/train.py", ["ppg"], []),
    "ibac_sni":  ("runnable/ibac_sni/torch_rl", "scripts/train.py", ["ibac_sni"], []),
}

# Call names that seed an RNG. Recorded with their dotted receiver so agent-side and env-side
# streams can be told apart -- Patterson et al. (Empirical Design in RL) treat their entanglement
# as a distinct defect from an absent seed.
SEED_CALLS = {
    "manual_seed", "manual_seed_all", "seed", "set_seed", "set_seed_everywhere",
    "set_random_seed", "set_global_seeds", "seed_everything", "default_rng", "RandomState",
}
ENV_RECEIVERS = re.compile(r"\b(env|envs|eval_env|train_env|venv|action_space|observation_space)\b")
AGENT_RECEIVERS = re.compile(r"\b(torch|np|numpy|random|cuda|tf)\b")

# Env seeding is usually NOT a `.seed()` call -- it is a seed passed to the env constructor, as
# `robo_make(..., seed=cfg.seed)` or `make_env(task_name=t, seed=args.seed + i)`. The first
# version of this script looked only at call NAMES and so reported `AGENT_ONLY` for three trees
# that do seed their envs (upstream train.py:78, idaac envs.py:101, dmc_gb wrappers.py:33). That
# is the same defect this project keeps finding in its own instruments: asserting on the shape of
# the thing you expect rather than the mechanism that carries it.
ENV_CALLEE = re.compile(r"(make_env|robo_make|make_vec|venv|_env\b|Env\b|gym\.make)", re.I)


def dotted(node) -> str:
    """`torch.cuda.manual_seed` from the Attribute chain; '' if it is not a name/attribute."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    elif isinstance(node, ast.Call):
        parts.append("()")
    return ".".join(reversed(parts))


def unparse(node) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return "<unparseable>"


def parse(path: pathlib.Path):
    try:
        return ast.parse(path.read_text(errors="replace"), filename=str(path))
    except SyntaxError:
        return None          # py2 files in vendored subtrees; counted, not fatal
    except Exception:
        return None


def one_hop(root: pathlib.Path, entry: pathlib.Path) -> list[pathlib.Path]:
    """Entry plus every module it imports that resolves to a file inside this tree."""
    files = [entry]
    tree = parse(entry)
    if tree is None:
        return files
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods.update(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module)
            # `from utils import x` and `from src import utils` both matter
            mods.update(f"{n.module}.{a.name}" for a in n.names)
    for m in sorted(mods):
        rel = m.replace(".", "/")
        for cand in (root / f"{rel}.py", root / rel / "__init__.py",
                     entry.parent / f"{rel}.py", entry.parent / rel / "__init__.py"):
            if cand.exists() and cand not in files:
                files.append(cand)
    return files


def seeding_sites(files) -> list[dict]:
    out = []
    for f in files:
        tree = parse(f)
        if tree is None:
            continue
        for n in ast.walk(tree):
            if not isinstance(n, ast.Call):
                continue
            name = dotted(n.func)
            if not name:
                continue
            leaf = name.rsplit(".", 1)[-1]
            recv = name.rsplit(".", 1)[0] if "." in name else ""
            seed_kw = [k for k in n.keywords if k.arg == "seed"]
            is_seed_call = leaf in SEED_CALLS
            if not is_seed_call and not seed_kw:
                continue
            args = [unparse(a) for a in n.args] + [f"{k.arg}={unparse(k.value)}" for k in n.keywords]
            argsrc = ", ".join(args)
            # A seed reaching an env CONSTRUCTOR is env-side seeding; a `.seed()`-style call is
            # classified by its receiver. Judge the value, never the presence of the call.
            if seed_kw and not is_seed_call:
                side = "env" if ENV_CALLEE.search(name) else "?"
                derived = bool(re.search(r"\bseed\b", unparse(seed_kw[0].value), re.I))
            else:
                side = ("env" if ENV_RECEIVERS.search(recv) or ENV_CALLEE.search(name)
                        else ("agent" if AGENT_RECEIVERS.search(recv) or not recv else "?"))
                derived = bool(re.search(r"\bseed\b", argsrc, re.I))
            out.append({"file": str(f), "line": n.lineno, "call": name, "args": argsrc,
                        "seed_derived": derived, "side": side})
    return out


def declarations(root: pathlib.Path, files) -> list[dict]:
    """Where a seed is offered to the user: argparse flag, hydra/spec yaml field."""
    decls = []
    for f in files:
        tree = parse(f)
        if tree is None:
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and ".DEFINE_" in dotted(n.func):
                consts = [a.value for a in n.args if isinstance(a, ast.Constant)]
                if consts and consts[0] == "seed":
                    decls.append({"kind": "absl", "file": str(f), "line": n.lineno,
                                  "default": repr(consts[1]) if len(consts) > 1 else "<none>"})
            if isinstance(n, ast.Call) and dotted(n.func).endswith("add_argument"):
                flags = [a.value for a in n.args if isinstance(a, ast.Constant)
                         and isinstance(a.value, str)]
                if any(re.fullmatch(r"--?seed", x) for x in flags):
                    default = next((unparse(k.value) for k in n.keywords if k.arg == "default"),
                                   "<none>")
                    decls.append({"kind": "argparse", "file": str(f), "line": n.lineno,
                                  "default": default})
    for y in sorted(root.glob("cfgs/*.yaml")) + sorted(root.glob("specs/*.yaml")) \
            + sorted(root.glob("*.yaml")):
        for i, line in enumerate(y.read_text(errors="replace").splitlines(), 1):
            m = re.match(r"\s*seed\s*:\s*(\S+)", line)
            if m:
                decls.append({"kind": "yaml", "file": str(y), "line": i, "default": m.group(1)})
    return decls


def verdict(decls, sites) -> tuple[str, str]:
    live = [s for s in sites if s["seed_derived"]]
    if not decls and not live:
        return "NO_KNOB", "no seed is declared and no RNG call takes a seed-derived value"
    if not decls:
        return "UNDECLARED_KNOB", "RNGs are seeded from something, but no --seed/`seed:` is offered"
    if not sites:
        return "DECLARED_NEVER_CONSUMED", "a seed is declared and no RNG is seeded at all"
    if not live:
        return "DECLARED_CONSTANT_ONLY", (
            "a seed is declared, but every RNG call takes a constant -- the knob turns nothing")
    sides = {s["side"] for s in live}
    if "env" not in sides:
        return "AGENT_ONLY", ("agent RNGs are seed-controlled; no env-side seeding on this path, "
                              "so env stochasticity may be outside the seed")
    # Deliberately says "reaches", not "controls". `scripts/probe_seed_effect.py` measured that
    # the env-side seed is INERT in train mode (register C49): it is stored as a RandomState that
    # only the visual randomisers read, and those are all off during training. So this verdict is
    # a statement about wiring, and the env half of it buys nothing until eval.
    return "SEED_CONTROLLED", ("seed reaches both agent-side and env-side RNGs (env side is "
                               "inert in train mode -- see C49)")


def audit(name: str) -> dict:
    rel, entry_rel, baselines, extra = TREES[name]
    root = ROOT / rel
    entry = root / entry_rel
    if not entry.exists():
        return {"tree": name, "baselines": baselines, "verdict": "TREE_ABSENT",
                "why": f"{entry} missing", "decls": [], "sites": [], "far_sites": 0}
    near = one_hop(root, entry)
    for d in extra:
        near += [p for p in (root / d).rglob("*.py") if "__pycache__" not in str(p)]
    sites = seeding_sites(near)
    decls = declarations(root, near)
    v, why = verdict(decls, sites)
    far = [p for p in root.rglob("*.py") if p not in near and "__pycache__" not in str(p)]
    return {"tree": name, "baselines": baselines, "verdict": v, "why": why,
            "entry": str(entry.relative_to(ROOT)), "scanned_near": len(near),
            "decls": decls, "sites": sites,
            "far_sites": len([s for s in seeding_sites(far) if s["seed_derived"]])}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tree", choices=sorted(TREES), help="audit one tree")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    names = [a.tree] if a.tree else sorted(TREES)
    results = [audit(n) for n in names]
    if a.json:
        print(json.dumps(results, indent=2))
        return 0
    bad = 0
    for r in results:
        print(f"\n=== {r['tree']}  ({', '.join(r['baselines'])})")
        print(f"    verdict: {r['verdict']} -- {r['why']}")
        if r["verdict"] == "TREE_ABSENT":
            continue
        print(f"    entry {r['entry']}, {r['scanned_near']} files on the one-hop path")
        for d in r["decls"][:4]:
            f = pathlib.Path(d["file"]).relative_to(ROOT)
            print(f"      declared  {d['kind']:<8} {f}:{d['line']}  default={d['default']}")
        if len(r["decls"]) > 4:
            print(f"      declared  ... {len(r['decls']) - 4} more")
        for s in r["sites"]:
            f = pathlib.Path(s["file"]).relative_to(ROOT)
            mark = "seed" if s["seed_derived"] else "CONST"
            print(f"      {mark:<5} [{s['side']:<5}] {s['call']}({s['args'][:40]})  {f}:{s['line']}")
        if r["far_sites"]:
            print(f"      ({r['far_sites']} further seed-derived sites off the one-hop path)")
        if r["verdict"] not in ("SEED_CONTROLLED",):
            bad += 1
    print(f"\n{len(results)} trees, {bad} not fully seed-controlled on the one-hop path.")
    print("Static screen only: a pass here does not establish determinism (C20 screen b).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
