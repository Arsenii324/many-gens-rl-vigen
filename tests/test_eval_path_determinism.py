#!/usr/bin/env python3
"""Screen (b) for the OFFLINE EVALUATOR: do two same-seed evaluations agree? — C69.

`scripts/audit_seed_control.py` is screen (a) and reads source. Its own docstring states the
limit that then bit us verbatim: *"a seeded run can still diverge through nondeterministic
kernels, thread scheduling, or an unseeded third RNG. Determinism is screen (b) and needs runs,
not reading."*

Screen (b) existed — `scripts/probe_determinism.py` — but it fingerprints **training** runs
(`eval.csv`/`train.csv` from `smoke_all.sh`). **Nothing ever ran it against
`scripts/eval_across_scenes.py`**, which is our own code and the source of every retention number
this project reports. That is precisely where the defect lived: `UniformRandomSampler`
(`third_party/robosuite/robosuite/utils/placement_samplers.py:167,183,196,198`) draws the door's
position from bare global `np.random`, our evaluator never seeded it, and the door moved ~1.6 cm
between processes recording an identical seed.

So the failure mode was named in advance, in writing, by the instrument that could not check it —
and the complementary instrument was never pointed at the file that needed it. This test is that
missing coverage.

## Why subprocesses rather than two in-process calls

An in-process repeat would share whatever RNG state the first call left behind, which can make a
non-reproducible evaluator look reproducible — the second call inherits the first's seeding. The
defect is specifically about *process* state, so each arm gets its own interpreter. This is also
why C69 was invisible to ordinary use: within one process, consecutive scenes did agree.

## Episode count, and why the first version of this file was too weak to matter

The first version ran **two** episodes and passed against a build that was still nondeterministic
(C70): torch's runtime CPU-kernel selection perturbs the actor's output by ~1e-7, which only shows
up when an episode sits near Door's success threshold. Two episodes of a random policy never get
near it. Raised to six, and the agent-path case is covered by
`test_construction_register`-adjacent evidence rather than here, because loading a checkpoint makes
this test slow enough to stop being run.

**This is the honest limit of this file**: it pins that the *environment* path is reproducible. The
full guarantee — same weights, same observations, same actions — additionally needs
`torch.use_deterministic_algorithms(True)`, which `run_scene` now sets and which was measured
against 20 episodes of a real checkpoint, where its absence flipped one episode from 372.34 to 6.01.

## Why the random policy

No checkpoint is required to detect the defect: the placement sampler runs on `reset()`, before
any action is chosen. The random policy is seeded through its own `np.random.default_rng(seed)`,
so if two runs differ, the difference is environment state, not action selection — which makes
the failure attributable rather than merely visible. It also keeps this test to a few seconds.

There is no cross-seed positive control here, deliberately: this asserts a *fixed* seed reproduces
itself, and a different seed producing different numbers is already pinned by
`test_regime_retention_report.py`'s floor fixtures. What this could not catch is an evaluator that
returns a constant — so the test also asserts the returns are not all identical.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
RLV = ROOT / "RL-ViGen-upstream"

pytestmark = [
    pytest.mark.slow,  # builds real robosuite environments in two subprocesses
    pytest.mark.skipif(not RLV.exists(), reason="upstream clone absent"),
]

SNIPPET = """
import json, sys, importlib.util
sys.argv = ["x"]
spec = importlib.util.spec_from_file_location("eas", {script!r})
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m._setup()
rets, succ, _ = m.run_scene(None, "Door", 0, "train", {episodes}, {seed}, 1, 3, 0)
print("RESULT" + json.dumps({{"returns": [float(x) for x in rets], "succ": int(succ)}}))
"""


def _one_process(episodes: int = 6, seed: int = 0) -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([
        str(RLV), str(RLV / "algos"), str(RLV / "envs" / "robosuiteVGB"),
        str(ROOT / "runnable" / "_shim"), str(ROOT)])
    env.setdefault("MUJOCO_GL", "glfw" if sys.platform == "darwin" else "egl")
    if sys.platform == "darwin":
        env.setdefault("PYGLFW_LIBRARY", "/opt/homebrew/lib/libglfw.dylib")
    code = SNIPPET.format(script=str(ROOT / "scripts" / "eval_across_scenes.py"),
                          episodes=episodes, seed=seed)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         env=env, cwd=str(ROOT), timeout=900)
    line = [ln for ln in out.stdout.splitlines() if ln.startswith("RESULT")]
    if not line:
        pytest.fail(f"evaluator subprocess produced no result.\n"
                    f"stdout tail:\n{out.stdout[-2000:]}\nstderr tail:\n{out.stderr[-2000:]}")
    return json.loads(line[-1][len("RESULT"):])


def test_two_processes_at_the_same_seed_agree_exactly():
    """The screen. Bit-identical returns, or the recorded seed does not name a measurement.

    Mutation-verified against the real defect: removing `utils.set_seed_everywhere(seed)` from
    `run_scene` makes this fail — measured before the fix at `[2.265003, 0.748782]` versus
    `[1.650736, 0.712101]` for the same seed.
    """
    a = _one_process()
    b = _one_process()
    assert a["returns"] == b["returns"], (
        "two processes evaluating the SAME checkpoint at the SAME seed disagree:\n"
        f"  A: {a['returns']}\n  B: {b['returns']}\n"
        "Something on the evaluation path draws from an RNG nobody seeded. The known instance is "
        "`UniformRandomSampler`, which places the door from global `np.random` and is seeded only "
        "by `utils.set_seed_everywhere(seed)` inside `run_scene` (C69).")
    assert a["succ"] == b["succ"]


def test_the_probe_could_have_failed():
    """A run whose returns are all identical would pass the test above while measuring nothing.

    The anti-vacuity check this repo's own history demands: `check_citations` once reported 0
    defects across 677 citations with a predicate that could not fail. Episode returns on Door
    under a random policy vary; if they ever stop varying, the test above is no longer evidence.
    """
    a = _one_process(episodes=3)
    assert len(set(a["returns"])) > 1, (
        f"all episode returns identical ({a['returns']}) — the determinism assertion above would "
        "pass against a constant and would not be evidence of anything")
