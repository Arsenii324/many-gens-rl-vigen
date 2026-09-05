"""Diagnostics and witnesses must be collected while the environment is still alive.

`run_scene_ppg` collected placement witnesses *above* its rollout loop (so `extend` copied only the
construction reset) and called `completed_episode_diagnostics` *below* the `finally` that closed the
venv (so it interrogated a torn-down wrapper stack).  Either one terminates every ppg cell now that
the collector fails closed.  The other six families already had the right order; this test is what
makes that agreement structural instead of coincidental.

Deliberately static: building a faithful fake for seven different vector-env stacks would test the
fakes.  Line order inside one function is the actual invariant, and it is cheap to read.
"""
import ast
import pathlib

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "eval_grid.py"
COLLECTORS = {"completed_episode_diagnostics", "placement_witness"}
CLOSERS = {"close_eval_env", "close", "closer"}


def _called_names(node):
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            func = sub.func
            if isinstance(func, ast.Name):
                yield func.id, sub.lineno
            elif isinstance(func, ast.Attribute):
                yield func.attr, sub.lineno


def test_no_run_scene_collects_after_it_closes_the_environment():
    tree = ast.parse(SOURCE.read_text())
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("run_scene"):
            continue
        collects, closes = [], []
        for name, lineno in _called_names(node):
            if name in COLLECTORS:
                collects.append(lineno)
            elif name in CLOSERS:
                closes.append(lineno)
        if collects and closes and max(collects) > min(closes):
            offenders.append(f"{node.name}: collects at {max(collects)}, closes at {min(closes)}")
    assert not offenders, (
        "these evaluators read the environment after tearing it down, which yields empty "
        f"diagnostics and now raises: {offenders}"
    )


def test_ppg_bounds_its_witness_copy_by_the_episode_count():
    """The witness list is shared and mutable; an unbounded copy mismatches the return count."""
    body = SOURCE.read_text()
    marker = '_placement_witnesses", []))[:episodes]'
    assert marker in body, (
        "run_scene_ppg must slice the shared witness list to `episodes`; an unsliced copy trips "
        "_run_grid's len(witnesses) != len(returns) check"
    )
