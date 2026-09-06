"""The offline grid must carry the evaluator-side action diagnostic into each scene row."""

import ast
import importlib.util
import pathlib
import sys
from types import SimpleNamespace

import numpy as np


ROOT = pathlib.Path(__file__).resolve().parents[1]


def _function_node(source: pathlib.Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(source.read_text(), filename=str(source))
    matches = [node for node in ast.walk(tree)
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name]
    assert len(matches) == 1, f"expected one {name} in {source.name}, found {len(matches)}"
    return matches[0]


def _call_lines(node: ast.AST, predicate) -> list[int]:
    return sorted(getattr(call, "lineno", -1) for call in ast.walk(node)
                  if isinstance(call, ast.Call) and predicate(call))


def _attribute_call(call: ast.Call, attribute: str) -> bool:
    return isinstance(call.func, ast.Attribute) and call.func.attr == attribute


def test_every_real_grid_adapter_observes_before_its_env_boundary_and_finishes_probe():
    """The diagnostic must not be protected only by the synthetic shared-adapter test.

    This is intentionally structural: importing or executing any remote-family environment here
    would make a wiring regression slow and renderer-dependent. The line-order assertion catches a
    probe moved after the adapter's environment call, while the family-specific names prevent a
    generic helper elsewhere in the module from satisfying the check.
    """
    grid = ROOT / "scripts" / "eval_grid.py"
    across = ROOT / "scripts" / "eval_across_scenes.py"
    adapters = {
        "rlvigen": (across, "run_scene", "ActionDiagnosticsAccumulator", "finish", "step"),
        "dmc_gb": (grid, "run_scene_dmc_gb", "_new_action_probe", "_finish_action_probe", "step"),
        "idaac": (grid, "run_scene_idaac", "_new_action_probe", "_finish_action_probe", "step"),
        "ppg": (grid, "run_scene_ppg", "_new_action_probe", "_finish_action_probe", "original_venv_act"),
        "ibac_sni": (grid, "run_scene_ibac_sni", "_new_action_probe", "_finish_action_probe", "step"),
        "alda": (grid, "run_scene_alda", "_new_action_probe", "_finish_action_probe", "step"),
        "ctrl": (grid, "run_scene_ctrl", "_new_action_probe", "_finish_action_probe", "step"),
    }
    for family, (source, function, setup_name, finish_name, boundary_name) in adapters.items():
        node = _function_node(source, function)
        setup = _call_lines(node, lambda call: isinstance(call.func, ast.Name)
                            and call.func.id == setup_name)
        observe = _call_lines(node, lambda call: _attribute_call(call, "observe"))
        finish = _call_lines(
            node,
            lambda call: ((isinstance(call.func, ast.Name) and call.func.id == finish_name)
                          or (isinstance(call.func, ast.Attribute) and call.func.attr == finish_name)),
        )
        boundary = _call_lines(node, lambda call: (
            (isinstance(call.func, ast.Attribute) and call.func.attr == boundary_name)
            or (boundary_name == "original_venv_act" and isinstance(call.func, ast.Name)
                and call.func.id == boundary_name)
        ))
        assert setup, f"{family}: no action probe construction in {source.name}:{function}"
        assert observe, f"{family}: no pre-env action observation in {source.name}:{function}"
        assert finish, f"{family}: no action diagnostic publication in {source.name}:{function}"
        assert boundary, f"{family}: no adapter/environment boundary in {source.name}:{function}"
        assert min(setup) < min(observe) < min(boundary), (
            f"{family}: action observation is not structurally before the env boundary")
        assert max(observe) < max(finish), (
            f"{family}: action diagnostic is published before all observations finish")


def test_grid_record_emitter_attaches_family_diagnostic_to_native_rows():
    """The shared emitter must publish the family result, including the RL-ViGen adapter."""
    node = _function_node(ROOT / "scripts" / "eval_grid.py", "_run_grid")
    diagnostic_dicts = []
    for item in ast.walk(node):
        if not isinstance(item, ast.Dict):
            continue
        pairs = {
            key.value: value for key, value in zip(item.keys, item.values)
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        }
        if "policy_action_diagnostics" in pairs:
            diagnostic_dicts.append(pairs["policy_action_diagnostics"])
    names = {item.id for item in ast.walk(node) if isinstance(item, ast.Name)}
    assert diagnostic_dicts, "_run_grid no longer attaches the action diagnostic to a native dict"
    assert any(isinstance(value, ast.Name) and value.id == "policy_action_diagnostics"
               for value in diagnostic_dicts)
    assert "LAST_POLICY_ACTION_DIAGNOSTICS" in names
    source = (ROOT / "scripts" / "eval_grid.py").read_text()
    assert "_eval_across_scenes.LAST_POLICY_ACTION_DIAGNOSTICS" in source


def _grid():
    spec = importlib.util.spec_from_file_location("_action_grid", ROOT / "scripts" / "eval_grid.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_grid_emits_pre_env_action_diagnostic_on_scene_rows(monkeypatch):
    grid = _grid()
    expected = {
        "available": True,
        "scope": "policy_output_before_env_action_boundary",
        "actions_observed": 2,
        "action_clip_rate_vector": 0.5,
        "controller_clipping_observed": False,
    }

    def fake_run_scene(*_args):
        grid._eval_across_scenes.LAST_PLACEMENT_WITNESSES = ["w0", "w1"]
        grid._eval_across_scenes.LAST_EPISODE_DIAGNOSTICS = [
            {"diagnostics_available": True}, {"diagnostics_available": True}
        ]
        grid._eval_across_scenes.LAST_POLICY_ACTION_DIAGNOSTICS = expected
        return np.asarray([1.0, 2.0]), 1, [0, 1]

    monkeypatch.setattr(grid, "run_scene", fake_run_scene)
    args = SimpleNamespace(
        append=False, out=None, family="rlvigen", task="Door", episodes=2,
        episode_seed=7, action_repeat=1, frame_stack=3,
    )
    rows = []

    def record(**row):
        rows.append(row)
        return row

    rc = grid._run_grid(
        args, None, record, ["train"], [0],
        {"cell": "drqv2-s1", "baseline": "drqv2", "family": "rlvigen", "seed": 1},
        100,
    )

    assert rc == 0
    assert rows[0]["native"]["policy_action_diagnostics"] == expected
