"""The IBAC offline evaluator must honour its declared device end to end."""
import importlib.util
import sys
import types
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "runnable" / "ibac_sni" / "torch_rl" / "utils" / "agent.py"


def _load_agent(monkeypatch, model, seen):
    fake_utils = types.ModuleType("utils")
    def preprocess(_obs, device=None):
        seen["obs_device"] = device
        return {"image": device}

    fake_utils.get_obss_preprocessor = lambda *_: (None, preprocess)
    fake_utils.load_model = lambda _path: model
    monkeypatch.setitem(sys.modules, "utils", fake_utils)
    spec = importlib.util.spec_from_file_location("_ibac_agent_under_test", AGENT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_agent_places_model_and_preprocessed_observations_on_requested_device(monkeypatch):
    """A CUDA-capable host must still allow a deliberate CPU diagnostic evaluation."""
    seen = {}

    class Distribution:
        def sample(self):
            import torch
            return torch.zeros((1, 7))

    class Model:
        def to(self, device):
            seen["model_device"] = device
            return self

        def compute_run(self, observation):
            seen["forward_device"] = observation["image"]
            return Distribution(), None, None

    module = _load_agent(monkeypatch, Model(), seen)
    agent = module.Agent("robosuite:Door", object(), "unused", device="cpu")
    action = agent.get_actions([object()])

    assert str(seen["model_device"]) == "cpu"
    assert str(seen["obs_device"]) == "cpu"
    assert str(seen["forward_device"]) == "cpu"
    assert action.shape == (1, 7)


def test_grid_forwards_its_device_to_ibac_agent_construction():
    """The grid's --device must reach the special directory-loading IBAC path."""
    source = (ROOT / "scripts" / "eval_grid.py").read_text()
    cell = source[source.index("def run_scene_ibac_sni("):source.index("\ndef ",
                                                               source.index("def run_scene_ibac_sni(") + 1)]
    assert "device=device" in cell


def test_argmax_uses_the_mean_for_a_continuous_ibac_policy(monkeypatch):
    """`probs.max` is categorical-only; deterministic Gaussian action means its mean."""
    seen = {}

    class Distribution:
        @property
        def mean(self):
            import torch
            return torch.full((1, 7), 0.25)

        def sample(self):
            raise AssertionError("argmax evaluation must not sample")

    class Model:
        def to(self, _device):
            return self

        def compute_run(self, _observation):
            return Distribution(), None, None

    module = _load_agent(monkeypatch, Model(), seen)
    agent = module.Agent("robosuite:Door", object(), "unused", argmax=True, device="cpu")
    np.testing.assert_allclose(agent.get_actions([object()]), np.full((1, 7), 0.25))
