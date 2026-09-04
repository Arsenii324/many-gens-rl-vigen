"""The checker must fail on a dead checkpoint and pass on a live one.

C57's checkpoint had 7.4M NaN parameters and produced eval logs, a train log and a snapshot that
all looked ordinary. A checker that cannot go red on that input would be decoration.

Each checkpoint is opened in a SUBPROCESS with only its own baseline's paths, because these
baselines ship colliding module names -- dmc_gb and RL-ViGen both have `utils` -- and putting
both on one sys.path breaks whichever loses. `test_two_families_do_not_shadow_each_other` pins
that, since a shared path is the obvious implementation and it silently corrupts one family.
"""
from __future__ import annotations

import importlib
import pathlib
import sys
import textwrap

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
torch = pytest.importorskip("torch")

FIXTURE_SRC = textwrap.dedent('''
    import torch

    class Tiny(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.fc = torch.nn.Linear(4, 4)

    class Agent:
        def __init__(self, nan=False):
            self.encoder = Tiny()
            self.actor = Tiny()
            if nan:
                with torch.no_grad():
                    self.actor.fc.weight.fill_(float("nan"))
                    self.encoder.fc.weight.fill_(float("nan"))
''')


@pytest.fixture()
def mod():
    m = importlib.import_module("check_checkpoint_finite")
    importlib.reload(m)
    return m


def write(tmp_path, nan, name="ck.pt", modname="fixture_agent"):
    """The agent class lives beside the checkpoint, so the subprocess can import it."""
    (tmp_path / f"{modname}.py").write_text(FIXTURE_SRC)
    sys.path.insert(0, str(tmp_path))
    m = importlib.import_module(modname)
    importlib.reload(m)
    p = tmp_path / name
    with p.open("wb") as f:
        torch.save({"agent": m.Agent(nan), "_global_step": 1000}, f)
    sys.path.remove(str(tmp_path))
    del sys.modules[modname]
    return p


def test_a_nan_checkpoint_is_reported_dead(mod, tmp_path):
    r = mod.inspect(write(tmp_path, nan=True))
    assert r["bad"] > 0, "a checkpoint full of NaN was reported finite"
    assert r["bad"] / r["total"] > 0.5


def test_a_healthy_checkpoint_is_clean(mod, tmp_path):
    r = mod.inspect(write(tmp_path, nan=False))
    assert r["bad"] == 0, "a healthy checkpoint was flagged"


def test_exit_code_is_nonzero_for_dead(mod, tmp_path, monkeypatch, capsys):
    p = write(tmp_path, nan=True)
    monkeypatch.setattr(sys, "argv", ["x", str(p)])
    assert mod.main() == 1
    assert "DEAD" in capsys.readouterr().out


def test_unreadable_is_not_reported_as_dead(mod, tmp_path, monkeypatch, capsys):
    """UNREADABLE says the checker could not look; DEAD says the weights are NaN.

    The first version printed 'not a network' for a file it merely failed to open."""
    bad = tmp_path / "junk.pt"
    bad.write_bytes(b"not a checkpoint")
    monkeypatch.setattr(sys, "argv", ["x", str(bad)])
    mod.main()
    out = capsys.readouterr().out
    assert "UNREADABLE" in out
    assert "could not be OPENED" in out
    assert "not a network" not in out, "an unopenable file was called a dead network"


def test_two_families_do_not_shadow_each_other(mod, tmp_path):
    """Both 'baselines' define a module of the same name; each must load against its own."""
    a, b = tmp_path / "famA", tmp_path / "famB"
    a.mkdir(); b.mkdir()
    pa = write(a, nan=False, modname="shared_name")
    pb = write(b, nan=True, modname="shared_name")
    ra, rb = mod.inspect(pa), mod.inspect(pb)
    assert ra["bad"] == 0 and rb["bad"] > 0, (
        f"one family's modules shadowed the other: {ra['bad']=} {rb['bad']=}")


def test_no_snapshots_is_a_failure_not_a_pass(mod, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["x", "--all"])
    assert mod.main() == 1
    assert "not a pass" in capsys.readouterr().out
