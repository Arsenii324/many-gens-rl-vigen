"""Deterministic torch on CUDA needs CUBLAS_WORKSPACE_CONFIG, set before CUDA initialises.

`torch.use_deterministic_algorithms(True)` SUCCEEDS on CUDA and then raises at the first CuBLAS
operation -- a linear layer -- unless the variable is set:

    RuntimeError: Deterministic behavior was enabled ... but this operation is not deterministic
    because it uses CuBLAS and you have CUDA >= 10.2 ... you must set CUBLAS_WORKSPACE_CONFIG

The try/except around the setting call cannot catch that, because the error comes from the
OPERATION. So determinism never completed a single CUDA evaluation from the day it was added
(C70) until 2026-09-05; job `bt1s5a6pub9muqgcoil9` is where it finally surfaced, after two other
defects standing in front of it were fixed.

Both evaluator entry points enable determinism, so both must set it, and both must do so at MODULE
scope -- setting it inside `main()` is too late if anything has already initialised CUDA.
"""
import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
ENTRY_POINTS = ("scripts/eval_grid.py", "scripts/eval_across_scenes.py")


def _module_level_env_defaults(path: pathlib.Path) -> dict[str, int]:
    """Return {env var: line number} for `os.environ.setdefault(...)` at module scope."""
    tree = ast.parse(path.read_text())
    found = {}
    for node in tree.body:                       # module scope only, deliberately
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if (isinstance(call.func, ast.Attribute) and call.func.attr == "setdefault"
                    and call.args and isinstance(call.args[0], ast.Constant)):
                found[call.args[0].value] = node.lineno
    return found


@pytest.mark.parametrize("relative", ENTRY_POINTS)
def test_entry_point_sets_cublas_config_at_module_scope(relative):
    path = ROOT / relative
    if not path.is_file():                                         # pragma: no cover
        pytest.skip(f"{relative} is not in this tree")
    source = path.read_text()
    if "use_deterministic_algorithms" not in source:
        pytest.skip(f"{relative} no longer enables deterministic algorithms")
    defaults = _module_level_env_defaults(path)
    assert "CUBLAS_WORKSPACE_CONFIG" in defaults, (
        f"{relative} enables deterministic algorithms but never sets CUBLAS_WORKSPACE_CONFIG at "
        "module scope, so every CUDA evaluation raises at the first CuBLAS operation"
    )


@pytest.mark.parametrize("relative", ENTRY_POINTS)
def test_the_config_is_set_before_any_torch_import(relative):
    path = ROOT / relative
    if not path.is_file() or "use_deterministic_algorithms" not in path.read_text():
        pytest.skip(f"{relative} not applicable")
    line = _module_level_env_defaults(path).get("CUBLAS_WORKSPACE_CONFIG")
    assert line is not None
    source = path.read_text().splitlines()
    torch_imports = [i + 1 for i, text in enumerate(source)
                     if text.strip() in ("import torch",) and not text.startswith((" ", "\t"))]
    for lineno in torch_imports:
        assert line < lineno, (
            f"{relative}: CUBLAS_WORKSPACE_CONFIG is set at line {line}, after a module-level "
            f"`import torch` at line {lineno}; CuBLAS reads it when the CUDA context initialises"
        )


def test_the_value_is_one_of_the_two_documented_settings():
    defaults = _module_level_env_defaults(ROOT / "scripts" / "eval_grid.py")
    assert "CUBLAS_WORKSPACE_CONFIG" in defaults
    source = (ROOT / "scripts" / "eval_grid.py").read_text()
    assert ':4096:8' in source or ':16:8' in source, (
        "CUBLAS_WORKSPACE_CONFIG must be ':4096:8' or ':16:8'; any other value leaves torch raising"
    )
