#!/usr/bin/env python3
"""Which configuration parameters does an early-returning branch silently drop? — C71.

    python scripts/audit_dead_knobs.py                 # audit the known clone trees
    python scripts/audit_dead_knobs.py --paths a.py b.py

## The defect this exists for

Five times now, a value has been written, passed, and never read on the robosuite path:

  1. `--action_repeat 1` for `rad`/`soda`   (`dmc_gb/src/env/wrappers.py`)
  2. `action_repeat: 1` for `alda`          (`alda/trainers/alda_trainer.py`)
  3. the whole of `configs/vigen.yaml`      (configures the retired `rlgen/` port)
  4. `DEFAULT_ACTION_REPEAT` in `protocol.py` (declared, never consulted by runners)
  5. `image_size` for `rad`/`soda`          (`dmc_gb/src/env/wrappers.py`)

Instances 1, 2 and 5 share **one shape**, and it is the only shape this script looks for:

    def make_env(domain_name, ..., action_repeat=4, image_size=100, ...):
        if domain_name == 'robosuite':
            ...
            return FrameStack(env, frame_stack)      # <-- returns here
        env = dmc2gym.make(..., frame_skip=action_repeat, height=image_size)   # <-- never reached

A parameter consumed **after** the early return but not **inside** it is accepted by the signature,
settable by a caller, and inert on that path. That is worse than a missing parameter: an absent one
announces itself to `grep`, while a dead one invites tuning that does nothing.

## Why this is not general dead-code analysis, deliberately

A real reachability analysis over these trees would be a large piece of work whose failure mode is
reporting green because its approximation was too coarse — the vacuity failure this project has hit
repeatedly. This checks one syntactic pattern that has produced three of the five known instances,
and it says so. **A clean run here is not evidence that no dead knobs exist**; it is evidence that
this pattern is absent, which is a much smaller claim and the only one the code supports.

Instances 3 and 4 are a different shape — a whole file or constant orphaned from its consumers —
and are NOT detectable here. They are listed above so the gap between "what C71 records" and "what
this instrument covers" stays visible.

## Reading the output

Each finding names the function, the branch's discriminator, the dropped parameter, and the line
where the unreachable consumer sits. **Verify before acting**: a parameter may be legitimately
irrelevant to a branch (a robosuite env has no use for `background_dataset_paths`), and the script
cannot tell "inert by design" from "inert by accident". It narrows twenty parameters to three.
"""
from __future__ import annotations

import argparse
import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: Trees whose env-construction paths branch per domain. Kept explicit rather than globbed: a
#: whole-repo sweep drowns the signal in argparse boilerplate, and these are the files where the
#: shape has actually occurred.
DEFAULT_PATHS = [
    "runnable/dmc_gb/src/env/wrappers.py",
    "runnable/alda/trainers/alda_trainer.py",
    "runnable/dmc_gb/src/train.py",
    "runnable/dmc_gb/src/eval.py",
]

#: A branch test naming one of these is treated as a domain discriminator. The point is to find
#: *conditional early returns keyed on which environment we are in*, not every early return.
DISCRIMINATORS = ("domain_name", "env", "domain", "task_name", "backend", "mode")


def _names_in(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _returns(node: ast.AST) -> bool:
    """Does this branch definitely leave the function?

    `ast.walk` would also find returns inside a nested def, which is not the same thing — hence
    the explicit recursion that refuses to descend into nested functions.
    """
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.Return):
            return True
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if _returns(child):
            return True
    return False


def _config_keys_in(node: ast.AST) -> set[str]:
    """Config keys read as `cfg['k']` or `cfg.get('k')`.

    Added after the first version found instances #1 and #5 and **missed #2** — `alda`'s branch
    tests `env_config.get('domain_name')`, so its configuration arrives as dict keys rather than
    named parameters and the parameter-based scan could not see it. Same defect, different access
    idiom; a checker that only handled one of them would have reported `alda` clean, which is the
    failure mode this file's docstring warns about.
    """
    keys = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) \
                and isinstance(n.slice.value, str):
            keys.add(n.slice.value)
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr == "get" and n.args \
                and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
            keys.add(n.args[0].value)
    return keys


def audit_function(fn: ast.FunctionDef, path: str) -> list[dict]:
    params = [a.arg for a in fn.args.args + fn.args.kwonlyargs]
    findings = []
    for stmt in fn.body:
        if not isinstance(stmt, ast.If) or not _returns(stmt):
            continue
        test_names = _names_in(stmt.test) | _config_keys_in(stmt.test)
        if not (test_names & set(DISCRIMINATORS)):
            continue
        consumed_inside, keys_inside = set(), set()
        for s in stmt.body:
            consumed_inside |= _names_in(s)
            keys_inside |= _config_keys_in(s)
        # Everything textually after this `if` is unreachable when the branch is taken.
        after = [s for s in fn.body if getattr(s, "lineno", 0) > stmt.end_lineno]
        branch = ast.unparse(stmt.test) if hasattr(ast, "unparse") else "?"

        # Two idioms, one defect: a named parameter, and a config-dict key.
        for p in params:
            if p in consumed_inside or p in test_names:
                continue
            for s in after:
                if p in _names_in(s):
                    findings.append({"file": path, "func": fn.name, "line": stmt.lineno,
                                     "branch": branch, "param": p, "kind": "param",
                                     "consumer_line": s.lineno})
                    break
        # Deduped by key: `alda` reads `env_config['action_repeat']` at three separate lines
        # after the branch, and reporting it three times would inflate the count and read as three
        # defects. First consumer line is kept, since that is where a reader should look.
        seen_keys = set()
        for s in after:
            for k in sorted(_config_keys_in(s) - keys_inside - test_names):
                if k in seen_keys:
                    continue
                seen_keys.add(k)
                findings.append({"file": path, "func": fn.name, "line": stmt.lineno,
                                 "branch": branch, "param": k, "kind": "config key",
                                 "consumer_line": s.lineno})
    return findings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--paths", nargs="*", default=None)
    a = ap.parse_args(argv)
    paths = a.paths or DEFAULT_PATHS

    print("DEAD-KNOB AUDIT -- parameters dropped by an early-returning domain branch (C71)")
    print("  ONE syntactic pattern only. A clean run does NOT mean no dead knobs exist;")
    print("  instances 3 and 4 in C71 are a different shape and are invisible here.\n")

    all_findings, scanned, missing = [], 0, []
    for rel in paths:
        p = ROOT / rel
        if not p.exists():
            missing.append(rel)
            continue
        scanned += 1
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for fn in [n for n in ast.walk(tree)
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            all_findings += audit_function(fn, rel)

    for f in all_findings:
        print(f"  {f['file']}:{f['line']}  in {f['func']}()  branch `{f['branch']}`")
        print(f"      drops {f.get('kind','param')} `{f['param']}` -- consumed at line {f['consumer_line']}, unreachable "
              f"when the branch is taken")

    if missing:
        # Announced, never silent: a path that vanished would otherwise reduce coverage invisibly,
        # which is exactly how a green checker stops being evidence.
        print(f"\n  !! {len(missing)} path(s) not found and therefore NOT scanned: "
              f"{', '.join(missing)}")
    print(f"\n  {len(all_findings)} finding(s) across {scanned} file(s) scanned.")
    if not all_findings and scanned:
        print("  Nothing found in THIS pattern. See the docstring for what that does not cover.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
