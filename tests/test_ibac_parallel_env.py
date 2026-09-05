"""The IBAC Door adapter must build MuJoCo environments inside spawned workers.

The upstream process count is 16.  Passing already-constructed Door environments to forked
children is not a faithful or runnable way to recover that count: EGL state is inherited and the
worker's NumPy stream is duplicated.  This test uses a tiny picklable environment to exercise the
same factory boundary without requiring a CUDA or MuJoCo test process.
"""
import functools
import base64
import os
import pickle
import subprocess
import sys
from pathlib import Path

import gym
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
IBAC_PACKAGE = ROOT / "runnable" / "ibac_sni" / "torch_rl" / "torch_rl"
if str(IBAC_PACKAGE) not in sys.path:
    sys.path.insert(0, str(IBAC_PACKAGE))

from torch_rl.utils.penv import ParallelEnv  # noqa: E402


class SeedReportingEnv(gym.Env):
    def __init__(self):
        self.observation_space = gym.spaces.Box(0, 2**31 - 1, (1,), dtype=np.int64)
        self.action_space = gym.spaces.Discrete(1)

    def reset(self):
        return np.array([np.random.randint(0, 2**31 - 1)], dtype=np.int64)

    def step(self, _action):
        return self.reset(), 0.0, False, {}


def make_seeded_env(seed):
    np.random.seed(seed)
    return SeedReportingEnv()


def test_factory_workers_use_spawn_and_keep_independent_rng_streams():
    envs = [
        make_seeded_env(101),
        functools.partial(make_seeded_env, 102),
        functools.partial(make_seeded_env, 103),
    ]
    parallel = ParallelEnv(envs, start_method="spawn")
    try:
        observations = parallel.reset()
        values = [int(observation[0]) for observation in observations]
        assert len(set(values)) == len(values)
    finally:
        parallel.close()


def test_ibac_training_driver_does_not_execute_in_spawned_main_import():
    """A spawn worker imports the driver as __mp_main__, so training must be main-guarded."""
    source = (ROOT / "runnable" / "ibac_sni" / "torch_rl" / "scripts" / "train.py").read_text()
    assert "def _run_training():" in source
    assert "if __name__ == '__main__':\n    _run_training()" in source
    assert source.index("def _run_training():") < source.rindex("if __name__ == '__main__':")


def test_ibac_driver_puts_outer_compatibility_modules_first():
    """The spawned interpreter must resolve bare utils to the clone compatibility layer."""
    source = (ROOT / "runnable" / "ibac_sni" / "torch_rl" / "scripts" / "train.py").read_text()
    assert "_IBAC_BASE = pathlib.Path(__file__).resolve().parents[1]" in source
    assert source.index("sys.path.insert(0, str(_IBAC_BASE))") < source.index("import torch_rl")


def test_ibac_spawn_factory_has_a_collision_free_module_identity():
    """Spawn unpickles the factory before the driver's bootstrap can repair bare ``utils``.

    RL-ViGen ships ``utils.py`` while IBAC's compatibility layer is the ``utils`` *package*.
    A pickle reference to ``utils.general`` can therefore load the former first and fail before a
    worker reaches any of our code.  The factory must have an IBAC-specific import identity.
    """
    base = ROOT / "runnable" / "ibac_sni" / "torch_rl"
    train = (base / "scripts" / "train.py").read_text()
    evaluate = (base / "scripts" / "evaluate.py").read_text()
    assert "from ibac_sni_runtime import make_rlvigen_env_process" in train
    assert "from ibac_sni_runtime import make_rlvigen_env_process" in evaluate
    assert "functools.partial(make_rlvigen_env_process" in train
    assert "functools.partial(make_rlvigen_env_process" in evaluate


def test_ibac_factory_unpickles_when_rlvigen_utils_is_first_on_a_fresh_interpreter():
    """Reproduce the worker's actual failure boundary without creating a MuJoCo environment."""
    base = ROOT / "runnable" / "ibac_sni" / "torch_rl"
    sys.path.insert(0, str(base))
    try:
        from ibac_sni_runtime import make_rlvigen_env_process
        factory = functools.partial(make_rlvigen_env_process, "robosuite:Door", 10001)
        encoded = base64.b64encode(pickle.dumps(factory)).decode("ascii")
    finally:
        sys.path.remove(str(base))

    # RL-ViGen's own top-level utils.py shadows IBAC's old utils package in exactly the way the
    # spawned container did.  Unpickling must not depend on which one happens to win that name.
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join((str(base), str(base / "torch_rl")))
    code = ("import base64, pickle; "
            f"factory = pickle.loads(base64.b64decode({encoded!r})); "
            "print(factory.func.__module__)" )
    proc = subprocess.run([sys.executable, "-c", code], cwd=ROOT / "RL-ViGen-upstream",
                          env=env, capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "ibac_sni_runtime"
