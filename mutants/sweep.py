#!/usr/bin/env python3
"""Unbiased mutation sweep: random operator mutations over `rlgen/`, oracle = `pytest tests`.

WHY THIS EXISTS ALONGSIDE `catalogue.py`. The curated catalogue measures the defects I thought of,
and I wrote both the mutants and the tests that catch them. A 14/14 kill rate on that is a
statement about my imagination, not about the suite's sensitivity. This file removes me from the
loop: it picks mutation sites mechanically, uniformly at random over the AST, with no regard for
whether any test covers them.

    python mutants/sweep.py -n 40 --seed 1

WHAT THE NUMBER MEANS, and what it does not. The kill rate here is a *lower bound* on sensitivity,
because some mutants are semantically EQUIVALENT to the original -- changing `>=` to `>` on a
bound that is never reached, or perturbing a constant inside an error message. Those cannot be
killed by any suite, and counting them as failures understates it. So every survivor is printed
with its exact diff, and triaging them by hand is the point of the exercise rather than an
afterthought. A survivor is either a real gap in the tests or a demonstrably equivalent mutant,
and saying which is a judgement a script must not make silently.

Operators are deliberately the ones that produce *plausible* code: comparison-boundary flips,
arithmetic sign swaps, boolean-connective swaps, small-integer perturbation, and dropped
negations. Deleting whole statements mostly produces obvious crashes and measures nothing.
"""
from __future__ import annotations

import argparse
import ast
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from mutants.run import SKIP, make_copy, run_suite  # noqa: E402

#: Production modules only. Tests, tools and the mutation machinery are not the system under test.
#
# DERIVED, NOT WRITTEN DOWN. This was a hand-maintained list, and it silently omitted
# `trainer_onpolicy.py` for the entire life of that module -- so every sweep number reported so far
# was measured over a codebase that did not include the on-policy budget stop, the GAE bootstrap or
# the shared eval cadence, while reading as if it covered `rlgen/`. A coverage list that does not
# notice new code is a coverage claim that quietly shrinks. `algos/` is excluded on purpose: it is
# vendored upstream algorithm code, judged by faithfulness to its origin (setup/VENDORED.md), not
# by this suite.
def _targets() -> list[str]:
    names = sorted(fn for fn in os.listdir(os.path.join(ROOT, "rlgen"))
                   if fn.endswith(".py") and fn != "__init__.py")
    if not names:
        raise SystemExit("FATAL: no production modules found; a sweep over nothing scores 100%.")
    return names


TARGETS = _targets()

CMP_SWAP = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt,
            ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Is: ast.IsNot, ast.IsNot: ast.Is,
            ast.In: ast.NotIn, ast.NotIn: ast.In}
BIN_SWAP = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult,
            ast.FloorDiv: ast.Div, ast.Mod: ast.Mult}
BOOL_SWAP = {ast.And: ast.Or, ast.Or: ast.And}


class Collector(ast.NodeVisitor):
    """Every mutable site in one module, as (kind, node)."""

    def __init__(self):
        self.sites: list[tuple[str, ast.AST]] = []

    def visit_Compare(self, node):
        for op in node.ops:
            if type(op) in CMP_SWAP:
                self.sites.append(("cmp", node))
                break
        self.generic_visit(node)

    def visit_BinOp(self, node):
        if type(node.op) in BIN_SWAP:
            self.sites.append(("bin", node))
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        if type(node.op) in BOOL_SWAP:
            self.sites.append(("bool", node))
        self.generic_visit(node)

    def visit_UnaryOp(self, node):
        if isinstance(node.op, ast.Not):
            self.sites.append(("not", node))
        self.generic_visit(node)

    def visit_Constant(self, node):
        if isinstance(node.value, bool):
            self.sites.append(("boolconst", node))
        elif isinstance(node.value, int) and 0 <= node.value <= 4096:
            self.sites.append(("int", node))
        self.generic_visit(node)


class Mutate(ast.NodeTransformer):
    def __init__(self, target: ast.AST, kind: str):
        self.target, self.kind, self.done = target, kind, False

    def _hit(self, node):
        return node is self.target and not self.done

    def visit_Compare(self, node):
        self.generic_visit(node)
        if self.kind == "cmp" and self._hit(node):
            node.ops = [CMP_SWAP.get(type(o), type(o))() for o in node.ops]
            self.done = True
        return node

    def visit_BinOp(self, node):
        self.generic_visit(node)
        if self.kind == "bin" and self._hit(node):
            node.op = BIN_SWAP[type(node.op)]()
            self.done = True
        return node

    def visit_BoolOp(self, node):
        self.generic_visit(node)
        if self.kind == "bool" and self._hit(node):
            node.op = BOOL_SWAP[type(node.op)]()
            self.done = True
        return node

    def visit_UnaryOp(self, node):
        self.generic_visit(node)
        if self.kind == "not" and self._hit(node):
            self.done = True
            return node.operand            # drop the negation
        return node

    def visit_Constant(self, node):
        if self._hit(node) and self.kind in ("int", "boolconst"):
            self.done = True
            return ast.copy_location(
                ast.Constant(value=(not node.value) if self.kind == "boolconst"
                             else node.value + 1), node)
        return node


def sample_mutants(seed: int, n: int) -> list[tuple[str, int, str, str, str]]:
    """-> [(relpath, lineno, kind, original_line, mutated_line)] with the new source cached."""
    rng = random.Random(seed)
    pool = []
    for fn in TARGETS:
        path = os.path.join(ROOT, "rlgen", fn)
        if not os.path.exists(path):
            # Was `continue`. Skipping silently means a renamed module drops out of the sweep and
            # the kill rate still prints as though it had been covered.
            raise SystemExit(f"FATAL: target {fn} does not exist at {path}.")
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src)
        c = Collector()
        c.visit(tree)
        for kind, node in c.sites:
            pool.append((fn, kind, getattr(node, "lineno", 0), node))
    rng.shuffle(pool)

    out = []
    for fn, kind, lineno, node in pool:
        if len(out) >= n:
            break
        path = os.path.join(ROOT, "rlgen", fn)
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src)
        # Re-find the node in a fresh tree by (kind, lineno, col).
        c = Collector()
        c.visit(tree)
        match = next((nd for k, nd in c.sites
                      if k == kind and getattr(nd, "lineno", -1) == lineno
                      and getattr(nd, "col_offset", -1) == getattr(node, "col_offset", -2)), None)
        if match is None:
            continue
        new_tree = Mutate(match, kind).visit(tree)
        ast.fix_missing_locations(new_tree)
        try:
            new_src = ast.unparse(new_tree)
            compile(new_src, path, "exec")
        except Exception:
            continue
        orig_line = src.splitlines()[lineno - 1].strip() if lineno else ""
        out.append((fn, lineno, kind, orig_line, new_src))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--max-fail", type=int, default=None,
                    help="stop after this many survivors (default: run them all)")
    args = ap.parse_args()

    mutants = sample_mutants(args.seed, args.n)
    if not mutants:
        print("FATAL: sampled zero mutants. A sweep that mutates nothing reports a perfect score "
              "for any codebase.", file=sys.stderr)
        return 2

    print(f"=== sanity: unmutated copy ===", flush=True)
    tmp = tempfile.mkdtemp(prefix="sweep-sanity-")
    shutil.rmtree(tmp)
    make_copy(tmp)
    ok, tail = run_suite(tmp)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"  {'PASS' if ok else 'FAIL'}  {tail}")
    if not ok:
        print("FATAL: unmutated copy fails; every 'kill' below would be meaningless.",
              file=sys.stderr)
        return 2

    print(f"\n=== {len(mutants)} random operator mutants (seed {args.seed}) ===", flush=True)
    killed, survived = 0, []
    for i, (fn, lineno, kind, orig, new_src) in enumerate(mutants, 1):
        tmp = tempfile.mkdtemp(prefix="sweep-")
        shutil.rmtree(tmp)
        make_copy(tmp)
        open(os.path.join(tmp, "rlgen", fn), "w", encoding="utf-8").write(new_src)
        t0 = time.time()
        ok, tail = run_suite(tmp)
        shutil.rmtree(tmp, ignore_errors=True)
        if ok:
            survived.append((fn, lineno, kind, orig))
            print(f"  [{i:>3}/{len(mutants)}] SURVIVED  rlgen/{fn}:{lineno} ({kind})  {orig[:64]}",
                  flush=True)
        else:
            killed += 1
            print(f"  [{i:>3}/{len(mutants)}] killed    rlgen/{fn}:{lineno} ({kind})  "
                  f"{tail[:56]}", flush=True)
        if args.max_fail and len(survived) >= args.max_fail:
            print("  (stopping early: --max-fail reached)")
            break

    n = killed + len(survived)
    print(f"\n{killed}/{n} killed  ({100.0 * killed / n:.0f}%)")
    if survived:
        print("\nSURVIVORS -- triage each by hand. A survivor is EITHER a real gap in the tests "
              "OR a semantically equivalent mutant; a script must not decide which.")
        for fn, lineno, kind, orig in survived:
            print(f"  rlgen/{fn}:{lineno}  ({kind})")
            print(f"      {orig}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
