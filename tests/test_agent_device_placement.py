"""The evaluator must move the weights, whatever shape the family pickled the agent in.

Job `bt16ikro8c3mu3id9p8n` died mid-episode with

    model.py:77 RuntimeError: Input type (torch.cuda.FloatTensor) and weight type
    (torch.FloatTensor) should be the same

because idaac pickles an `nn.Module` directly, and the loader only walked `vars(agent)` for module
ATTRIBUTES. An nn.Module keeps its children in `_modules`, so that walk moves nothing: idaac's
weights stayed on CPU while `agent.device` said cuda and the env produced cuda observations.

ppg had an explicit `if a.family == "ppg"` branch for the same shape. Keying on the family name
meant idaac -- identical in shape -- inherited the bug instead of the fix. This test is written
against the SHAPE for that reason.
"""
import importlib.util
import pathlib
import sys

import pytest

torch = pytest.importorskip("torch")
ROOT = pathlib.Path(__file__).resolve().parents[1]


def _grid():
    spec = importlib.util.spec_from_file_location("_grid_dev", ROOT / "scripts" / "eval_grid.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["_grid_dev"] = module
    spec.loader.exec_module(module)
    return module


class _ModuleAgent(torch.nn.Module):
    """idaac's and ppg's shape: the agent IS the module."""
    def __init__(self):
        super().__init__()
        self.conv = torch.nn.Conv2d(3, 4, 3)


class _HolderAgent:
    """RL-ViGen's and dmc_gb's shape: a plain object holding modules."""
    def __init__(self):
        self.actor = torch.nn.Linear(4, 4)


def test_a_module_shaped_agent_has_its_own_parameters_moved():
    grid = _grid()
    agent = _ModuleAgent()
    grid.place_agent_on_device(agent, torch.device("cpu"))
    assert all(p.device.type == "cpu" for p in agent.parameters())
    assert not agent.training, "a module-shaped agent must be put in eval mode"


def test_a_holder_shaped_agent_has_its_attribute_modules_moved():
    grid = _grid()
    agent = _HolderAgent()
    grid.place_agent_on_device(agent, torch.device("cpu"))
    assert all(p.device.type == "cpu" for p in agent.actor.parameters())


def test_the_walk_alone_would_miss_a_module_shaped_agent():
    """The regression itself: prove `vars()` cannot see an nn.Module's own children."""
    agent = _ModuleAgent()
    found = [v for v in vars(agent).values() if isinstance(v, torch.nn.Module)]
    assert not found, (
        "if vars() ever exposes an nn.Module's children directly, this test's premise is gone and "
        "place_agent_on_device should be re-derived rather than trusted"
    )


def test_placement_is_keyed_on_shape_not_on_a_family_name():
    source = (ROOT / "scripts" / "eval_grid.py").read_text()
    start = source.index("def place_agent_on_device")
    end = source.index("def placement_witness")
    body = source[start:end]
    assert "isinstance(agent, torch.nn.Module)" in body, (
        "placement must test the agent's shape; keying on a family name is how idaac inherited "
        "the bug that ppg already had a branch for"
    )
    assert 'family == "ppg"' not in body and 'family == "idaac"' not in body, (
        "no family names in placement: the next family to pickle a module must inherit the fix"
    )
