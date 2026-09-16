#!/usr/bin/env python3
"""Count PPG's auxiliary-phase minibatches by executing the vendored code, not a re-derivation.

    python scripts/probe_ppg_aux_minibatches.py

`runnable/ppg/phasic_policy_gradient/ppg.py::make_minibatches` is the function production calls
once per auxiliary epoch. Importing the package pulls in mpi4py and gym3, which this machine does
not need for this question, so the probe lifts the exact source of `make_minibatches` and of the
three `torch_util` helpers it uses out of the vendored files with `ast` and executes that source
unchanged against dummy segments shaped like the real `seg_buf`: `n_pi` segments, each with a
leading `(num_envs, nstep)` pair of axes.

It prints one row per configuration: the upstream single-rank default, what production executes,
and every `aux_mbsize` the production geometry can express.
"""
from __future__ import annotations

import ast
import itertools
import pathlib
import types

import torch as th

ROOT = pathlib.Path(__file__).resolve().parents[1]
PPG = ROOT / "runnable" / "ppg" / "phasic_policy_gradient"


def _lift(path: pathlib.Path, names: set[str]) -> str:
    tree = ast.parse(path.read_text())
    found = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    missing = names - {n.name for n in found}
    if missing:
        raise SystemExit(f"{path}: functions not found: {sorted(missing)}")
    return "\n\n".join(ast.get_source_segment(path.read_text(), n) for n in found)


def _load():
    tree_util_ns: dict = {}
    exec(compile((PPG / "tree_util.py").read_text(), str(PPG / "tree_util.py"), "exec"), tree_util_ns)
    tu_ns = {"th": th, "tree_util": types.SimpleNamespace(**tree_util_ns),
             "tree_map": tree_util_ns["tree_map"]}
    exec(_lift(PPG / "torch_util.py", {"batch_len", "tree_slice", "tree_stack"}), tu_ns)
    ppg_ns = {"th": th, "itertools": itertools, "tu": types.SimpleNamespace(**tu_ns)}
    exec(_lift(PPG / "ppg.py", {"make_minibatches"}), ppg_ns)
    return ppg_ns["make_minibatches"]


def _count(make_minibatches, num_envs: int, nstep: int, n_pi: int, aux_mbsize: int):
    segs = [{"ob": th.zeros(num_envs, nstep, 1), "vtarg": th.zeros(num_envs, nstep)} for _ in range(n_pi)]
    shapes = [tuple(mb["vtarg"].shape) for mb in make_minibatches(segs, aux_mbsize)]
    return len(shapes), sorted(set(shapes))


def main() -> int:
    make_minibatches = _load()
    n_aux_epochs, n_pi = 6, 32
    rows = [("upstream 1-rank default", 64, 256, 4)]
    rows += [("production (families.json)" if m == 4 else "expressible", 1, 2048, m) for m in (1, 2, 4, 8, 16, 32)]
    print(f"n_pi={n_pi} n_aux_epochs={n_aux_epochs}  (source: {PPG.relative_to(ROOT)}/ppg.py::make_minibatches)")
    print("label | num_envs | nstep | aux_mbsize | minibatches/aux_epoch | per_N_pi | mb vtarg shape "
          "| samples/mb | aux_steps/aux_phase | frames/aux_phase | aux_steps/frame")
    for label, envs, nstep, mbsize in rows:
        count, shapes = _count(make_minibatches, envs, nstep, n_pi, mbsize)
        samples = shapes[0][0] * shapes[0][1]
        steps = count * n_aux_epochs
        frames = envs * nstep * n_pi
        print(f"{label} | {envs} | {nstep} | {mbsize} | {count} | {count / n_pi:g} | {shapes} "
              f"| {samples} | {steps} | {frames} | {steps / frames:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
