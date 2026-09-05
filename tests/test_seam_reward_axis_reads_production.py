"""The comparability audit's reward axis must read the PRODUCTION evaluator, not only the clones.

`audit_comparability_seam.py`'s own header says the final number is produced by `eval_grid.py`, but
its `reward pipeline` axis derived the REPORTED units from each family's NATIVE evaluator and
hardcoded "raw" for all twelve. So when external review 8 found `eval_grid`'s ctrl evaluator summing
the outermost `VecNormalize` reward, the axis was reporting UNIFORM while ctrl's production return
was in units of a running statistic.

Its docstring had already named the hazard exactly -- "reading the venv's reward instead of the
monitor's silently changes the units of every number a baseline reports, and nothing raises". It was
prose. This test exists so it stays a check.
"""
import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _seam():
    spec = importlib.util.spec_from_file_location(
        "_seam", ROOT / "scripts" / "audit_comparability_seam.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["_seam"] = module
    try:
        spec.loader.exec_module(module)
    except Exception as error:                                     # pragma: no cover
        pytest.skip(f"seam audit not importable here: {type(error).__name__}: {error}")
    return module


def test_the_reward_axis_reports_raw_for_every_baseline_today():
    seam = _seam()
    values, provenance = seam.reward_pipeline()
    assert "eval_grid.py" in provenance, (
        "the reward axis must state that it derives the reported half from the production "
        "evaluator; a provenance string that omits it is describing the native evaluators"
    )
    for baseline, value in values.items():
        assert value.startswith("raw |"), (
            f"{baseline} reports a transformed return from the production evaluator: {value}"
        )


def test_the_axis_is_not_satisfied_by_its_own_comment():
    """A regex over the ctrl block matched the COMMENT explaining the flag, not the call."""
    source = (ROOT / "scripts" / "audit_comparability_seam.py").read_text()
    assert "ast.walk" in source and "RLViGenVecEnvCustom" in source, (
        "the ctrl reward-units check must parse the call, not grep the block: the block contains "
        "an explanatory comment carrying the same string, and a regex passed on that alone"
    )
