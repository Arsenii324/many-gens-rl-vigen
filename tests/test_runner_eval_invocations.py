"""Every flag the runner hands `eval_grid.py` must be one that parser accepts.

`run_probe.sh` ships as a SEPARATE job input while the payload is a pinned archive, so the runner is
always current and the evaluator inside the payload may not be. A flag the runner passes and the
payload's parser does not know is `argparse` exit 2 -- **after** the ~10-minute bootstrap has been
paid for. `RUNNER_CONTRACT` guards that coarsely, by version; this checks it precisely, by name.

There are two invocations and they are easy to keep in step by accident rather than on purpose:
the endpoint grid in `run_offline_eval` and the trajectory grid in `run_curve_eval`. The curve one
has never run remotely under the current evaluator, so it has no evidence behind it at all.
"""
import ast
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER = (ROOT / "datasphere" / "native" / "run_probe.sh").read_text()
GRID = ROOT / "scripts" / "eval_grid.py"


def declared_options() -> set[str]:
    """Options `eval_grid`'s parser actually defines."""
    tree = ast.parse(GRID.read_text())
    names = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_argument"):
            for arg in node.args:
                if isinstance(arg, ast.Constant) and str(arg.value).startswith("--"):
                    names.add(str(arg.value)[2:])
    return names


def invocations() -> dict[str, list[str]]:
    """Flags passed in each `python3 scripts/eval_grid.py ...` block, keyed by the enclosing marker."""
    found = {}
    for match in re.finditer(r"python3 scripts/eval_grid\.py((?:[^\n]*\\\n)*[^\n]*)", RUNNER):
        block = match.group(1)
        # Attribute the call to its ENCLOSING FUNCTION, found by its definition line. This used
        # to scan backwards for the literal "run_", so any comment mentioning another function by
        # name stole the attribution -- which is exactly what happened when run_curve_eval gained
        # a comment referring to run_endpoint_eval, and this file then reported "no curve
        # invocation found" for a curve invocation that was right there.
        defs = [m for m in re.finditer(r"^([a-z_][a-z0-9_]*)\(\) \{", RUNNER, re.M)
                if m.start() < match.start()]
        name = defs[-1].group(1) if defs else f"at{match.start()}"
        found[name] = re.findall(r"--([a-z][a-z0-9-]*)", block)
    return found


def test_both_eval_invocations_are_found():
    calls = invocations()
    assert len(calls) >= 2, f"expected the endpoint and curve invocations, found {list(calls)}"


@pytest.mark.parametrize("which", sorted(invocations()))
def test_every_flag_passed_is_declared_by_the_parser(which):
    declared = declared_options()
    assert declared, "no options scraped from eval_grid.py; the scraper is broken, not the runner"
    unknown = sorted(set(invocations()[which]) - declared)
    assert not unknown, (
        f"{which} passes flags eval_grid.py does not declare: {unknown}. argparse exits 2, so the "
        "cell would die after the bootstrap was already paid for."
    )


def test_the_curve_invocation_labels_its_scope():
    """Endpoint and curve rows share a schema; without the label they cannot be told apart."""
    calls = invocations()
    curve = next((v for k, v in calls.items() if "curve" in k), None)
    assert curve is not None, "no curve invocation found"
    assert "eval-scope" in curve, "the curve grid does not label its rows"


def test_finiteness_is_checked_before_paid_offline_evaluation():
    """A NaN checkpoint must fail before curve/endpoint grids consume GPU time."""
    retain = RUNNER.index('"$FAMILY_TOOL" retain')
    finite = RUNNER.index('"$FAMILY_TOOL" check-finite')
    # [Claude 2026-09-06] Was `run_curve_eval "$cell_out"` -- the call site moved behind
    # `run_curve_eval_with_policy` (Codex's fail-closed-at-production-scale wrapper). The wrapper
    # calls the unchanged `run_curve_eval` as its first action, so the ordering this test protects
    # (finite-check before any paid evaluation) is unaffected by which name sits at the call site.
    curve = RUNNER.index('run_curve_eval_with_policy "$cell_out"')
    endpoint = RUNNER.index('run_endpoint_eval "$cell_out"')
    assert retain < finite < curve < endpoint
