"""The declared frame stack must reach BOTH the trainer and the offline evaluator.

`RLVIGEN_IMAGE_SIZE` is the precedent and the reason this file exists. It was set for the training
process and not for the eval paths, so `rad` trained at 100x100 and was evaluated at 84 -- surfaced
only as `expected ... 100x100, observed (9, 84, 84)`, from a runtime assertion, after the cell had
been paid for. The declaration was right and unreachable.

`RLVIGEN_FRAME_STACK` has exactly the same shape: `families.json`'s `environment` block is applied
by the runner to the TRAINING process, and `scripts/eval_grid.py` runs in a different process that
never sees it. So the value is asserted from both ends against one source of truth,
`rlgen.protocol.OBSERVATION_GEOMETRY`:

  - the trainer gets it because `families.json` declares it and `family.py environment` emits it;
  - the evaluator gets it because `eval_grid.py` sets it from OBSERVATION_GEOMETRY itself.

A stack that is declared but not passed does not fail loudly at training time -- it just trains a
velocity-blind policy while every record says otherwise.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rlgen.protocol import OBSERVATION_GEOMETRY  # noqa: E402

FAMILIES = json.loads((ROOT / "datasphere" / "native" / "families.json").read_text())
FAMILY_TOOL = ROOT / "datasphere" / "native" / "family.py"

#: The two baselines whose stack is carried by an environment variable rather than a CLI flag,
#: because their clones take no such flag: the stack is authored at the env-construction seam.
ENV_CARRIED = {"ctrl": "ctrl", "ibac_sni": "ibac_sni"}


@pytest.mark.parametrize("family,baseline", sorted(ENV_CARRIED.items()))
def test_families_json_declares_the_stack_the_protocol_declares(family, baseline):
    declared = OBSERVATION_GEOMETRY[baseline][1]
    passed = FAMILIES[family].get("environment", {}).get("RLVIGEN_FRAME_STACK")
    assert passed is not None, (
        f"{family} carries its stack by environment and families.json passes none, so the trainer "
        f"would silently use the runtime default of 1 while every record claims {declared}")
    assert int(passed) == declared, f"{family}: families.json {passed} vs protocol {declared}"


@pytest.mark.parametrize("family,baseline", sorted(ENV_CARRIED.items()))
def test_the_runner_actually_emits_it(family, baseline):
    """Not the descriptor -- what `family.py environment` resolves, which is what runs."""
    done = subprocess.run(
        [sys.executable, str(FAMILY_TOOL), "environment", "--family", family,
         "--baseline", baseline, "--task", "Door", "--run-dir", "/tmp/frame-stack-probe"],
        capture_output=True, text=True, cwd=str(ROOT))
    assert done.returncode == 0, done.stderr
    emitted = dict(line.split("=", 1) for line in done.stdout.split() if "=" in line)
    assert int(emitted["RLVIGEN_FRAME_STACK"]) == OBSERVATION_GEOMETRY[baseline][1]


@pytest.mark.parametrize("baseline", sorted(ENV_CARRIED.values()))
def test_the_offline_evaluator_sets_it_from_the_declaration(baseline):
    """The eval process does not inherit the family environment; it must derive the value."""
    source = (ROOT / "scripts" / "eval_grid.py").read_text()
    expected = f'os.environ["RLVIGEN_FRAME_STACK"] = str(OBSERVATION_GEOMETRY["{baseline}"][1])'
    assert expected in source, (
        f"eval_grid.py does not set RLVIGEN_FRAME_STACK for {baseline} from OBSERVATION_GEOMETRY, "
        f"so the evaluator would build a one-frame env for a three-frame checkpoint")


def test_the_flag_carried_families_still_agree_too():
    """idaac and ppg pass a CLI flag instead; same invariant, different mechanism."""
    for family in ("idaac", "ppg"):
        assert int(FAMILIES[family]["constants"]["frame_stack"]) == OBSERVATION_GEOMETRY[family][1]


def test_the_runtime_default_is_one_so_an_unset_variable_is_never_a_silent_three():
    """Absent must mean the historical behaviour, never a half-applied stack."""
    for path in ("runnable/ibac_sni/torch_rl/ibac_sni_runtime.py", "runnable/ctrl/vec_env.py"):
        source = (ROOT / path).read_text()
        assert 'os.environ.get("RLVIGEN_FRAME_STACK", "1")' in source, path
