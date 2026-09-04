#!/usr/bin/env python3
"""The offline evaluation grid: regimes x scenes, from one checkpoint — R3 / R7 / C43.

    python scripts/eval_grid.py --snapshot out/cells/drqv2-s1/snapshot.pt \
        --regimes train,eval-easy,eval-medium,eval-hard --scenes 0,1,2,3,4,5,6,7,8,9 \
        --episodes 20 --out grid.jsonl

## Why this is a separate harness, and not a training-loop patch

Three independent findings say the comparable measurement cannot come from training logs.
`audit_eval_axis` shows five baselines sweep ten scenes and seven pin scene 0. `audit_eval_cadence`
shows `ppg` and `ibac_sni` evaluate nothing during training and `ctrl` evaluates continuously
rather than in episodes. And C43 needs two regimes measured against each other, which most training
loops never produce together. Patching seven training loops would be seven authored deviations in
what is measured; reading one checkpoint afterwards is none.

It is also what the arithmetic demands. Twenty episodes per scene across four regimes and ten
scenes is 800 episodes — inside the training loop, at RL-ViGen's evaluation cadence, that costs
more wall-clock than the training it interrupts. Offline it costs nothing but its own time, and it
runs once at the end instead of twenty-four times along the way.

## What it does NOT do

**It evaluates three families: the RL-ViGen five, dmc_gb's `rad`/`soda`, and `idaac`.** `scripts/audit_eval_state.py` records what the
other seven need, and two of them (`ppg`, `ctrl`) have no usable evaluator at all — `ppg` ships no
evaluation code and `ctrl`'s is discrete-only against a 7-DoF continuous action space. Those are
authored work, not a flag on this script, and pretending one entry point covers twelve is the
error C45 is about.

**It does not aggregate across regimes.** Each row names its regime and its scene set. `eval-hard`
is not `eval-medium` plus more: medium randomises the robot and hard fixes the robot and adds a
moving light and a video background, and measured in observation space medium sits *further* from
train than hard does. A single ordered "difficulty" column would assert something the instrument
contradicts.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import pathlib
import sys
import tempfile
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.eval_across_scenes import _setup, find_snapshot, run_scene  # noqa: E402


def seed_the_placement_rng(seed: int) -> None:
    """Seed the GLOBAL RNGs before an env is built, for the families that are not `rlvigen`.

    [Claude 2026-09-03, found by a blind-spot pass] `eval_across_scenes.run_scene` has done this
    since [C69](../docs/CONSTRUCTION.md#c69); `run_scene_dmc_gb`, `run_scene_idaac` and
    `run_scene_ppg` never did. C69's point is that robosuite's `UniformRandomSampler` calls bare
    `np.random.uniform` and holds no `random_state`, so **the door's position on every reset comes
    from the global numpy RNG** -- not from the `seed` threaded through `robo_make`, which reaches
    only the texture/colour wrapper.

    So for three of the four implemented families the evaluation seed did not reach the door. Two
    consequences, and the second is the one that matters here:

    1. Their evaluations were not reproducible across processes -- C69 measured ~1.6 cm of spread
       in the door's x position between runs recording an identical seed.
    2. **Their door placements did not match the natives'**, so "same scene set, same seed set
       across the twelve" was false by construction, which is the property the whole common-grid
       proposal in `docs/EVAL-PROTOCOL.md` rests on.

    Seeded here rather than inside each family so there is one place to read, and called before the
    env is constructed in every one, because that is when the sampler draws.
    """
    import random as _random

    import numpy as _np
    _random.seed(seed)
    _np.random.seed(seed)
    try:
        import torch as _torch
        _torch.manual_seed(seed)
        if _torch.cuda.is_available():
            _torch.cuda.manual_seed_all(seed)
    except Exception:
        # torch is absent in a JAX-only family's environment; the placement RNG is numpy's and is
        # already seeded above, which is the half that decides the door.
        pass


def _dmc_gb_setup() -> None:
    """dmc_gb evaluates through its own `make_env` and its agent's own `select_action`.

    Kept in this file rather than a second script because the RECORD is the deliverable and there
    should be one place that emits it. What is NOT shared is the env or the policy call: those are
    each family's own, and pretending otherwise is how a grid measures twelve different things
    under one column.
    """
    root = ROOT / "runnable" / "dmc_gb" / "src"
    os.environ.setdefault("RLVIGEN_ROOT", str(ROOT / "RL-ViGen-upstream"))
    os.environ.setdefault("MUJOCO_GL", "glfw" if sys.platform == "darwin" else "egl")
    if sys.platform == "darwin":
        os.environ.setdefault("PYGLFW_LIBRARY", "/opt/homebrew/lib/libglfw.dylib")
    for path in (root, root / "env" / "dmc2gym", ROOT / "runnable" / "_shim"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


def run_scene_dmc_gb(agent, task, scene_id, mode, episodes, seed, image_size, episode_length):
    """One (regime, scene) cell for rad/soda, through dmc_gb's own env and action path.

    `select_action` is the deterministic one (`mu`); `sample_action` is the stochastic one, and
    train.py's own `evaluate` uses `select_action`. The success convention is the any-step one
    every baseline here shares -- see scripts/eval_across_scenes for why it is read per step.
    """
    seed_the_placement_rng(seed)
    import torch
    import utils
    from env.wrappers import make_env

    env = make_env(domain_name="robosuite", task_name=task, seed=seed,
                   episode_length=episode_length, action_repeat=1,
                   image_size=image_size, mode=mode, scene_id=scene_id)
    returns, successes, flags = [], 0, []
    for _ in range(episodes):
        obs = env.reset()
        total, succeeded = 0.0, False
        done = False
        while not done:
            # [Claude 2026-09-04] `utils.eval_mode(agent)`, matching `src/train.py::evaluate`
            # EXACTLY, where this previously used a bare `torch.no_grad()`. The two are not the
            # same thing: theirs is a context manager that calls `model.train(False)` and restores
            # afterwards, and it does NOT disable gradients (their `select_action` already does
            # that internally, so our `no_grad` was redundant rather than equivalent).
            #
            # On TODAY's action path the two produce identical actions, and that was verified
            # rather than assumed: `Actor` is encoder + Linear/ReLU, and the encoder is Conv2d,
            # ReLU, LayerNorm, Tanh, Linear -- not one train/eval-sensitive layer among them.
            # **But that is a property of the architecture, not of the code**, and the hazard is
            # one instantiation away: `modules.SODAMLP` contains an `nn.BatchNorm1d`, which at the
            # batch size of 1 this loop uses would read a single sample's own statistics in train
            # mode. Matching their call removes the dependence on that coincidence for free.
            with torch.no_grad(), utils.eval_mode(agent):
                action = agent.select_action(obs)
            obs, reward, done, info = env.step(action)
            total += float(reward)
            succeeded = succeeded or bool((info or {}).get("success", False))
        returns.append(total)
        successes += int(succeeded)
        flags.append(int(succeeded))
    return np.array(returns), successes, flags


def _idaac_setup() -> None:
    """idaac evaluates through OUR RL-ViGen adapter and its own `act`.

    **The render size is part of the policy's input contract, not a preference.** idaac trains at
    64x64 with a single frame -- its own paper's geometry, which `rlgen/protocol.py`'s
    OBSERVATION_GEOMETRY records and patch P6 makes reachable. Building the evaluation env at
    RL-ViGen's default 84 instead produces a 3,872-wide flattened encoder output against a linear
    layer expecting 2,048, and the grid dies on the first action with a shape error. Every family's
    offline grid has to reproduce its own geometry; this is where idaac's is set.
    """
    os.environ.setdefault("RLVIGEN_IMAGE_SIZE", "64")
    os.environ.setdefault("RLVIGEN_ROOT", str(ROOT / "RL-ViGen-upstream"))
    os.environ.setdefault("MUJOCO_GL", "glfw" if sys.platform == "darwin" else "egl")
    if sys.platform == "darwin":
        os.environ.setdefault("PYGLFW_LIBRARY", "/opt/homebrew/lib/libglfw.dylib")
    # [Claude 2026-09-03] idaac's OWN entry point installs this shim at `train.py:5` before it
    # imports anything -- legacy OpenAI baselines reference `np.bool`, which NumPy 1.24 removed.
    # This harness imports idaac's modules directly and therefore never executed `train.py`, so the
    # shim never ran and the first container evaluation died on
    # `AttributeError: module 'numpy' has no attribute 'bool'` (job bt1c6vj2iv6ucu9683nk).
    #
    # Applied identically to theirs, not "fixed" differently: the point of driving a baseline's own
    # act is that it runs in the environment its own trainer would have built, and an import-time
    # shim is part of that environment.
    import numpy as _np
    if not hasattr(_np, "bool"):
        _np.bool = bool
    # The order and the members are families.json's own `import_gate.pythonpath` for idaac, not a
    # guess: `ext/baselines` imports tensorflow unconditionally and `_shim/no_tf` is the stub that
    # answers it. Omitting it fails at `running_mean_std`, several seconds in.
    for path in (ROOT / "runnable" / "idaac", ROOT / "ext" / "baselines",
                 ROOT / "runnable" / "_shim" / "no_tf", ROOT / "runnable" / "_shim"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


def run_scene_idaac(agent, task, scene_id, mode, episodes, seed):
    """One (regime, scene) cell for idaac, through the VecEnv stack its own evaluator uses.

    **It SAMPLES.** `model.py:332` is `def act(self, inputs, deterministic=False)` and `test.py`
    calls `act(obs)` without the flag, so idaac's own evaluation draws from the policy where nine
    other baselines take the mode. Reproduced here rather than corrected: the estimator is the
    method's, and `conventions.eval_policy_mode` records it as `sample` so no table pools the two.

    The scene sweep is possible because `make_rlvigen_venv` -- our adapter, not idaac's code --
    now takes `scene_id`. Its own evaluator pins 0, which is C45.
    """
    seed_the_placement_rng(seed)
    import torch
    from ppo_daac_idaac.envs import make_rlvigen_venv

    class _Args:
        pass

    args = _Args()
    args.seed = seed
    args.env_name = f"robosuite:{task}"
    device = torch.device("cpu")
    envs = make_rlvigen_venv(args, device, mode, 1, scene_id=scene_id)

    # THE RETURN COMES FROM VecMonitor, NOT FROM step().
    #
    # The stack is DummyVecEnv -> VecMonitor -> VecNormalize, so the reward `step()` hands back is
    # the NORMALISED one the agent trains on, while the monitor -- sitting inside the normaliser --
    # records the raw episode return under `info['episode']['r']`. Summing `step()`'s reward gave
    # 22.4 against the run's own logged 1.55 for the same checkpoint and regime: a 14x error, in
    # normalised units, that would have read as a generalisation result. idaac's own `test.py`
    # reads `info['episode']['r']`, and so does this.
    returns, successes, flags = [], 0, []
    obs = envs.reset()
    succeeded = False
    while len(returns) < episodes:
        with torch.no_grad():
            out = agent.act(obs)
        action = out[1] if len(out) == 3 else out[2]
        obs, _, _, infos = envs.step(action)
        for info in (infos or []):
            succeeded = succeeded or bool((info or {}).get("success", False))
            episode = (info or {}).get("episode")
            if episode is not None:
                returns.append(float(episode["r"]))
                successes += int(succeeded)
                flags.append(int(succeeded))
                succeeded = False   # the VecEnv auto-resets; the next episode starts clean
    return np.array(returns[:episodes]), successes, flags[:episodes]


def _ppg_setup() -> None:
    """ppg evaluates through its OWN gym3 venv and its own sampling `act`.

    Two things here are contract, not preference. **64x64**: the launcher
    (`runnable/_launch/ppg_cell.sh`) exports `RLVIGEN_IMAGE_SIZE=64` before training, so ImpalaCNN's
    flattened width was fixed at that geometry; building the grid's env at RL-ViGen's default 84
    mismatches the first linear layer exactly as it did for idaac. **`runnable/ppg` on the path**:
    `phasic_policy_gradient` is imported as a top-level package by the pickled model itself, so it
    must be importable before `torch.load`, not after.
    """
    os.environ.setdefault("RLVIGEN_IMAGE_SIZE", "64")
    os.environ.setdefault("RLVIGEN_ROOT", str(ROOT / "RL-ViGen-upstream"))
    os.environ.setdefault("MUJOCO_GL", "glfw" if sys.platform == "darwin" else "egl")
    if sys.platform == "darwin":
        os.environ.setdefault("PYGLFW_LIBRARY", "/opt/homebrew/lib/libglfw.dylib")
    path = ROOT / "runnable" / "ppg"
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def run_scene_ppg(agent, task, scene_id, mode, episodes, seed):
    """One (regime, scene) cell for ppg, through PPG's own Roller and VecMonitor2.

    **It SAMPLES.** `PpoModel.act` draws from the policy distribution and this repository ships no
    deterministic-action path to call instead -- the same statement `ppg_eval.py` makes at length,
    reproduced here because the grid must report the same estimator its own launcher does.

    Episodes are counted by `roller.episode_count`, which PPG's `VecMonitor2` increments when an
    env resets. Counting closed episodes rather than steps is what makes the sample size the
    requested one; a step-counted loop would truncate the last episode and bias the mean low.
    """
    seed_the_placement_rng(seed)
    from phasic_policy_gradient.envs import get_venv
    from phasic_policy_gradient.roller import Roller

    venv = get_venv(num_envs=1, env_name=f"robosuite:{task}", mode=mode, seed=seed,
                    scene_id=scene_id)
    try:
        roller = Roller(venv=venv, act_fn=agent.act, initial_state=agent.initial_state(1),
                        keep_buf=max(100, episodes))
        while roller.episode_count < episodes:
            roller.multi_step(32)
        returns = np.array(roller.recent_eprets[:episodes], dtype=float)
        infos = roller.recent_epinfos[:episodes]
    finally:
        # One mujoco context per scene, ten scenes per regime: without this the grid accumulates
        # them until the renderer refuses. gym3 venvs do not all define close(), hence the getattr.
        closer = getattr(venv, "close", None)
        if callable(closer):
            closer()
    vals = [float(item.get("episode_success", 0.0) or 0.0) for item in infos]
    successes = int(sum(vals))
    flags = [int(bool(v)) for v in vals]
    return returns, successes, flags


def _ibac_sni_setup() -> None:
    """ibac_sni evaluates through its OWN `utils.Agent` and its own gym env.

    64x64 and `torch_rl` on the path, matching `runnable/_launch/ibac_sni_cell.sh`. The regime and
    the scene are passed through the environment, because `general.py` reads `RLVIGEN_MODE` and
    (since 2026-09-03) `RLVIGEN_SCENE_ID` rather than taking arguments -- the clone's own callers
    are its scripts, and widening their signatures would be a deviation for no gain.
    """
    os.environ.setdefault("RLVIGEN_IMAGE_SIZE", "64")
    os.environ.setdefault("RLVIGEN_ROOT", str(ROOT / "RL-ViGen-upstream"))
    os.environ.setdefault("MUJOCO_GL", "glfw" if sys.platform == "darwin" else "egl")
    if sys.platform == "darwin":
        os.environ.setdefault("PYGLFW_LIBRARY", "/opt/homebrew/lib/libglfw.dylib")
    base = ROOT / "runnable" / "ibac_sni" / "torch_rl"
    for path in (base, base / "torch_rl"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


def run_scene_ibac_sni(model_dir, task, scene_id, mode, episodes, seed):
    """One (regime, scene) cell for ibac_sni, through its own `Agent` and `get_actions`.

    **It SAMPLES.** `Agent.__init__` takes `argmax=False` by default and `scripts/evaluate.py`
    never passes the flag, so `dist.sample()` is what its own evaluation does. Reproduced, not
    corrected -- `COMPARABILITY_CONTRACT.md` §5c.

    **The "agent" here is a DIRECTORY, not a loaded object**, because `utils.load_model` takes a
    model_dir and appends `model.pt` itself. `main()` stages the snapshot under that name rather
    than reaching past their loader, so the object doing the acting is the one their own evaluator
    would have built.
    """
    seed_the_placement_rng(seed)
    os.environ["RLVIGEN_MODE"] = mode
    os.environ["RLVIGEN_SCENE_ID"] = str(scene_id)
    import utils as ibac_utils

    env_id = f"robosuite:{task}"
    env = ibac_utils.make_rlvigen_env(env_id, seed)
    agent = ibac_utils.Agent(env_id, env.observation_space, str(model_dir), False, 1)

    returns, successes, flags = [], 0, []
    for _ in range(episodes):
        obs = env.reset()
        if isinstance(obs, tuple):
            obs = obs[0]
        total, succeeded, done = 0.0, False, False
        while not done:
            action = agent.get_actions([obs])[0]
            step = env.step(action)
            obs, reward, done = step[0], step[1], step[2]
            if len(step) > 4:
                done = bool(step[2] or step[3])
            total += float(reward or 0.0)
            info = step[-1] if isinstance(step[-1], dict) else {}
            succeeded = succeeded or bool(info.get("success", False)) or bool(
                (getattr(env, "last_info", None) or {}).get("success", False))
        returns.append(total)
        successes += int(succeeded)
        flags.append(int(succeeded))
    return np.array(returns), successes, flags


def _alda_setup() -> None:
    """alda evaluates through its OWN trainer, wrappers and `select_action`.

    64x64 per the render-resolution axis, and `runnable/alda` on the path so `trainers.alda_trainer`
    and its vendored `dmcontrol_generalization_benchmark` import as they do for its own entry point.
    """
    os.environ.setdefault("RLVIGEN_IMAGE_SIZE", "64")
    os.environ.setdefault("RLVIGEN_ROOT", str(ROOT / "RL-ViGen-upstream"))
    os.environ.setdefault("MUJOCO_GL", "glfw" if sys.platform == "darwin" else "egl")
    if sys.platform == "darwin":
        os.environ.setdefault("PYGLFW_LIBRARY", "/opt/homebrew/lib/libglfw.dylib")
    # Exactly families.json's own `import_gate.pythonpath` for alda, in its order -- alda vendors
    # dmc2gym inside dmcontrol_generalization_benchmark and resolves `models` through a shim, so a
    # shorter path fails at `import dmc2gym` several frames into the trainer's own import.
    for rel in ("runnable/alda",
                "runnable/alda/dmcontrol_generalization_benchmark/src/env/dmc2gym",
                "runnable/_shim/alda_models",
                "runnable/_shim"):
        path = str(ROOT / rel)
        if path not in sys.path:
            sys.path.insert(0, path)


def _alda_trainer(snapshot, device: str):
    """Build alda's trainer through ITS OWN factory, then load the checkpoint into it.

    The order is the one `runnable/alda/scripts/train.py` uses and is not optional: `__init__` sets
    every module to `None`, `initialize_env_dmc` builds the envs, `build` constructs the modules
    from the env's shapes, and only then can `load_checkpoint` fill state dicts. Constructing the
    trainer is cheap despite alda's 15.3 GiB replay law, because `__init__` sets `self.buffer =
    None` -- the allocation happens in training, which is never reached here.
    """
    import yaml
    from common.utils import create_instance_from_spec

    spec_path = ROOT / "runnable" / "alda" / "specs" / "train_alda_robosuite_door.yaml"
    spec = yaml.load(spec_path.read_text(encoding="utf-8"), Loader=yaml.loader.FullLoader)
    spec["trainer"]["config"]["device"] = device
    spec["trainer"]["config"]["use_wandb"] = False
    spec["trainer"]["config"]["debug"] = True
    spec["trainer"]["config"]["exp_dir"] = tempfile.mkdtemp(prefix="alda_eval_")
    trainer = create_instance_from_spec(spec["trainer"], name=spec["name"])
    trainer.initialize_env_dmc(spec)
    trainer.build(spec)
    trainer.load_checkpoint(str(snapshot))
    trainer.eval()
    return trainer, spec


def run_scene_alda(built, task, scene_id, mode, episodes, seed):
    """One (regime, scene) cell for alda, through its own wrapper chain and `select_action`.

    **The env is built with alda's own `_build` chain, not `robo_make`.** alda feeds
    `DMCObsWrapper(FrameStack(_RoboRGB(...)))`, which yields the `{'rgb', 'state'}` dict its encoder
    expects; a `robo_make` env yields a dmc-style TimeStep and a different observation object. Using
    its chain is what makes this its own policy acting in its own environment.

    **alda ships only three regimes** -- `train`, `eval-easy` (its `color_env`) and `eval-hard` (its
    `distract_env`). `_build` takes the mode as an argument, so any RL-ViGen regime including
    `eval-medium` can be constructed through the same chain; that is a wider grid than alda's own
    `evaluate()` offers, and it is our harness widening it, not a change to alda.

    **It takes the mode**: `select_action` returns `mu` with `compute_pi=False`, so alda is one of
    the nine deterministic reporters.
    """
    seed_the_placement_rng(seed)
    trainer, spec = built
    from dmcontrol_generalization_benchmark.src.env.wrappers import FrameStack, DMCObsWrapper
    from trainers.alda_trainer import _RoboRGB
    from robosuitevgb.utils import make_env as robo_make_env

    env_config = spec["trainer"]["config"]["env"]
    inner = _RoboRGB(robo_make_env(task_name=task, seed=seed, scene_id=scene_id, mode=mode),
                     env_config["episode_length"])
    env = DMCObsWrapper(FrameStack(inner, env_config["frame_stack"]))

    returns, successes, flags = [], 0, []
    for _ in range(episodes):
        obs = env.reset()
        if isinstance(obs, tuple):
            obs = obs[0]
        total, succeeded, done = 0.0, False, False
        while not done:
            # Exactly alda's own evaluate(): `select_action(preprocess_obs(obs['rgb'][None]))`.
            # `select_action` takes an array and DMCObsWrapper yields a {'rgb','state'} dict, so the
            # extraction, the batch axis and the preprocessing are all part of how alda acts -- not
            # harness plumbing to be improvised. DMCObsWrapper returns a 5-tuple and info is 5th.
            action = trainer.select_action(trainer.preprocess_obs(obs["rgb"][None]))
            obs, reward, done, _truncated, info = env.step(action)
            total += float(reward or 0.0)
            info = info if isinstance(info, dict) else {}
            succeeded = succeeded or bool(info.get("success", False))
        returns.append(total)
        successes += int(succeeded)
        flags.append(int(succeeded))
    return np.array(returns), successes, flags


def _ctrl_setup() -> None:
    """ctrl evaluates through its OWN JAX model, `algo.select_action`, and its own vec env.

    64x64 per the render axis. `runnable/ctrl` on the path, and the `_shim` after it because ctrl's
    `train_ppo` imports wandb unconditionally and the offline sink answers that.
    """
    os.environ.setdefault("RLVIGEN_IMAGE_SIZE", "64")
    os.environ.setdefault("RLVIGEN_ROOT", str(ROOT / "RL-ViGen-upstream"))
    os.environ.setdefault("MUJOCO_GL", "glfw" if sys.platform == "darwin" else "egl")
    if sys.platform == "darwin":
        os.environ.setdefault("PYGLFW_LIBRARY", "/opt/homebrew/lib/libglfw.dylib")
    for rel in ("runnable/ctrl", "runnable/_shim"):
        path = str(ROOT / rel)
        if path not in sys.path:
            sys.path.insert(0, path)


#: ctrl's own flag defaults, from `train_ppo.py`. They are needed to rebuild the TrainState that the
#: checkpoint deserialises INTO -- flax's `from_bytes` fills a target, it does not construct one --
#: so a wrong value here silently produces a differently-shaped model rather than an error.
CTRL_DEFAULTS = dict(num_clusters=200, n_att_heads=2, embedding_type="concat",
                     cluster_len=10, lr=5e-4, lr_ctrl=1e-4, max_grad_norm=0.5)


def _ctrl_train_state(snapshot, n_actions: int = 7):
    """Rebuild ctrl's TrainState and fill it from the msgpack checkpoint.

    `train_ppo.py` writes `flax.serialization.to_bytes(train_state)` -- one file rather than an
    orbax directory, deliberately, because a single serialised TrainState is what an offline
    evaluator needs. Reading it back requires reconstructing the same structure first: the model
    with ctrl's own dims and flags, `model.init` on the same fake batch shapes, and the same optax
    chain, because the optimiser state is part of what was serialised.
    """
    import jax
    import jax.numpy as jnp
    import optax
    from flax.serialization import from_bytes

    from algo import TrainState
    from models import CTRLModel

    d = CTRL_DEFAULTS
    model = CTRLModel(dims=(256, 256), n_cluster=d["num_clusters"], n_actions=n_actions,
                      continuous=True, n_att_heads=d["n_att_heads"],
                      embedding_type=d["embedding_type"])
    key = jax.random.PRNGKey(0)
    fake_state = jnp.zeros((1, d["cluster_len"], 64, 64, 3))
    fake_act = jnp.zeros((1, d["cluster_len"], n_actions))
    params = model.init(key, state=fake_state, action=fake_act, reward=fake_act)
    tx_ppo = optax.chain(optax.clip_by_global_norm(d["max_grad_norm"]),
                         optax.adam(d["lr"], eps=1e-5))
    tx_cluster = optax.chain(optax.clip_by_global_norm(d["max_grad_norm"]),
                             optax.adam(d["lr_ctrl"], eps=1e-5))
    train_state = TrainState.create(apply_fn=model.apply, params=params, tx=(tx_ppo, tx_cluster))
    train_state = from_bytes(train_state, pathlib.Path(snapshot).read_bytes())
    return train_state, model


def run_scene_ctrl(built, task, scene_id, mode, episodes, seed):
    """One (regime, scene) cell for ctrl, through its own vec env and `algo.select_action`.

    **It SAMPLES**, and that is the correction of 2026-09-04: `select_action(..., sample=False)`
    returns `pi.mode()`, but `train_ppo.py:244` and `:253` -- the calls behind the numbers a ctrl
    cell reports -- both pass `sample=True`. Reproducing the reporting path means sampling.

    **The observation scaling is theirs**: `state.astype(float32) / 255.`, exactly as at those call
    sites. `RLViGenVecEnvCustom` yields the stacked-frame layout the model expects.
    """
    seed_the_placement_rng(seed)
    import jax
    import jax.numpy as jnp
    from algo import select_action
    from vec_env import RLViGenVecEnvCustom

    train_state, model = built
    env = RLViGenVecEnvCustom(f"robosuite:{task}", mode=mode, num_envs=1, seed=seed,
                              scene_id=scene_id)
    key = jax.random.PRNGKey(seed)

    returns, successes, flags = [], 0, []
    for _ in range(episodes):
        state = env.reset()
        total, succeeded, done = 0.0, False, False
        while not done:
            action, _, _, key = select_action(train_state.params, train_state.apply_fn, model.ac,
                                              jnp.asarray(state).astype(jnp.float32) / 255.,
                                              key, sample=True)
            state, reward, done_arr, infos = env.step(np.asarray(action))
            done = bool(np.asarray(done_arr).reshape(-1)[0])
            total += float(np.asarray(reward).reshape(-1)[0])
            info = infos[0] if isinstance(infos, (list, tuple)) and infos else {}
            succeeded = succeeded or bool((info or {}).get("success", False))
        returns.append(total)
        successes += int(succeeded)
        flags.append(int(succeeded))
    return np.array(returns), successes, flags


def _run_grid(a, agent, record, regimes, scenes, context, frame) -> int:
    """The grid loop, shared by every family.

    Extracted 2026-09-03 when `ibac_sni` needed a different way of *obtaining* the agent (a
    staged directory rather than a loaded object) while running the identical loop. Two
    copies of a streaming JSONL writer would be two places for the record schema to drift.
    """

    # Streamed, not buffered. A production grid is four regimes x ten scenes x twenty episodes --
    # hours of environment stepping -- and the first version wrote its JSONL only at the end, so an
    # interrupted run kept nothing it had already measured. Each record is appended and flushed as
    # it is produced; the file is therefore always a valid prefix of the full grid.
    rows: list[dict] = []
    sink = open(a.out, "w", buffering=1) if a.out else None

    def emit(row: dict) -> None:
        rows.append(row)
        if sink is not None:
            sink.write(json.dumps(row) + "\n")
            sink.flush()

    started = time.time()
    for regime in regimes:
        per_scene: dict[int, np.ndarray] = {}
        successes = 0
        for scene in scenes:
            print(f"  {regime:12s} scene {scene} ...", file=sys.stderr, flush=True)
            if a.family == "idaac":
                returns, succ, flags = run_scene_idaac(agent, a.task, scene, regime, a.episodes,
                                                a.episode_seed)
            elif a.family == "ctrl":
                returns, succ, flags = run_scene_ctrl(agent, a.task, scene, regime, a.episodes,
                                               a.episode_seed)
            elif a.family == "alda":
                returns, succ, flags = run_scene_alda(agent, a.task, scene, regime, a.episodes,
                                               a.episode_seed)
            elif a.family == "ibac_sni":
                returns, succ, flags = run_scene_ibac_sni(agent, a.task, scene, regime, a.episodes,
                                                   a.episode_seed)
            elif a.family == "ppg":
                returns, succ, flags = run_scene_ppg(agent, a.task, scene, regime, a.episodes,
                                              a.episode_seed)
            elif a.family == "dmc_gb":
                returns, succ, flags = run_scene_dmc_gb(agent, a.task, scene, regime, a.episodes,
                                                 a.episode_seed, a.image_size, a.episode_length)
            else:
                returns, succ, flags = run_scene(agent, a.task, scene, regime, a.episodes,
                                          a.episode_seed, a.action_repeat, a.frame_stack, frame)
            per_scene[scene] = np.asarray(returns, dtype=float)
            successes += succ
            emit(record(**context, phase="offline-eval", frame=frame, regime=regime,
                               scene_set=str(scene), episodes=len(returns),
                               episode_return_mean=float(np.mean(returns)),
                               episode_return_sd=float(np.std(returns, ddof=1))
                               if len(returns) > 1 else None,
                               success_rate=succ / max(1, len(returns)),
                               native={"returns": [float(x) for x in returns],
                                       "successes": int(succ),
                                       # Aligned index-for-index with `returns`. A pooled count
                                       # answers "how often", never "what did the episodes that
                                       # succeeded score" -- the question that separates a policy
                                       # opening the door from one banking shaped reaching reward.
                                       # It also puts a Wilson interval on SR per scene, which the
                                       # scalar rate cannot carry.
                                       "episode_success": [int(x) for x in flags]}))
        # The aggregate a table shows, kept beside the per-scene rows rather than instead of them:
        # a mean over ten scenes hides which scene collapsed, and that is usually the finding.
        pooled = np.concatenate([per_scene[s] for s in scenes]) if per_scene else np.array([])
        if pooled.size:
            emit(record(**context, phase="offline-eval", frame=frame, regime=regime,
                               scene_set=",".join(str(s) for s in scenes),
                               episodes=int(pooled.size),
                               episode_return_mean=float(pooled.mean()),
                               episode_return_sd=float(pooled.std(ddof=1)) if pooled.size > 1 else None,
                               success_rate=successes / pooled.size,
                               native={"aggregate_over_scenes": scenes,
                                       "per_scene_mean": {str(s): float(per_scene[s].mean())
                                                          for s in scenes}}))

    if sink is not None:
        sink.close()
        print(f"{len(rows)} records -> {a.out} in {time.time() - started:.0f}s", file=sys.stderr)
    else:
        sys.stdout.write("\n".join(json.dumps(row) for row in rows) + "\n")
    return 0


def _record_factory():
    """normalize_curves owns the record envelope; import it by path, not by package."""
    spec = importlib.util.spec_from_file_location(
        "normalize_curves", ROOT / "datasphere" / "native" / "normalize_curves.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["normalize_curves"] = module
    spec.loader.exec_module(module)
    return module.record


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snapshot", default=None)
    ap.add_argument("--family", default="rlvigen", choices=("rlvigen", "dmc_gb", "idaac", "ppg", "ibac_sni", "alda", "ctrl"),
                    help="which evaluation path; each family drives its own env and action call")
    ap.add_argument("--baseline", default="drqv2", help="names the records")
    ap.add_argument("--image-size", type=int, default=100, help="dmc_gb only; its own render size")
    ap.add_argument("--episode-length", type=int, default=500, help="dmc_gb only")
    ap.add_argument("--seed", type=int, default=0, help="the SEED OF THE RUN being evaluated")
    ap.add_argument("--frame", type=int, default=None,
                    help="the training frame this checkpoint is from; read from the filename when "
                         "it is a P18 stamped snapshot_<frame>.pt and required otherwise")
    ap.add_argument("--task", default="Door")
    ap.add_argument("--regimes", default="train,eval-easy,eval-medium,eval-hard")
    ap.add_argument("--scenes", default="0,1,2,3,4,5,6,7,8,9")
    ap.add_argument("--episodes", type=int, default=20,
                    help="PER SCENE. 20 is what the dispersion measurement supports: at one "
                         "episode the held-out gap is 1.24x the same-scene gap (noise), at twenty "
                         "it is 3.58x")
    ap.add_argument("--episode-seed", type=int, default=0)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--action-repeat", type=int, default=1)
    ap.add_argument("--frame-stack", type=int, default=3)
    ap.add_argument("--out", default=None, help="JSONL destination; stdout when absent")
    a = ap.parse_args()

    if a.family == "dmc_gb":
        _dmc_gb_setup()
    elif a.family == "idaac":
        _idaac_setup()
    elif a.family == "ppg":
        _ppg_setup()
    elif a.family == "ibac_sni":
        _ibac_sni_setup()
    elif a.family == "alda":
        _alda_setup()
    elif a.family == "ctrl":
        _ctrl_setup()
    else:
        _setup()
    snap = find_snapshot(a.snapshot)
    if snap is None:
        print("no snapshot found; nothing was measured", file=sys.stderr)
        return 1

    frame = a.frame
    if frame is None:
        stem = snap.stem
        if stem.startswith("snapshot_") and stem[9:].isdigit():
            frame = int(stem[9:])
        else:
            print(f"--frame is required: {snap.name} does not carry one in its name. A record "
                  "whose x-axis is unknown is not a record.", file=sys.stderr)
            return 1

    if a.family == "ctrl":
        # flax `from_bytes` fills a TARGET; it does not construct one. The TrainState must be
        # rebuilt with ctrl's own flags first, which is why this cannot go through the generic
        # torch.load path below.
        agent = _ctrl_train_state(snap)
        record = _record_factory()
        regimes = [item.strip() for item in a.regimes.split(",") if item.strip()]
        scenes = [int(item) for item in a.scenes.split(",") if item.strip()]
        context = {"cell": f"{a.baseline}-s{a.seed}", "baseline": a.baseline,
                   "family": a.family, "seed": a.seed}
        return _run_grid(a, agent, record, regimes, scenes, context, frame)

    if a.family == "alda":
        # alda's modules do not exist until `initialize_env_dmc` + `build` have run, so the
        # checkpoint cannot be loaded standalone -- `load_checkpoint` fills state dicts into an
        # already-constructed trainer. `_alda_trainer` runs that sequence through alda's own
        # factory, which is why the object acting is the one its own entry point would have made.
        agent = _alda_trainer(snap, a.device)
        record = _record_factory()
        regimes = [item.strip() for item in a.regimes.split(",") if item.strip()]
        scenes = [int(item) for item in a.scenes.split(",") if item.strip()]
        context = {"cell": f"{a.baseline}-s{a.seed}", "baseline": a.baseline,
                   "family": a.family, "seed": a.seed}
        return _run_grid(a, agent, record, regimes, scenes, context, frame)

    if a.family == "ibac_sni":
        # [Claude 2026-09-03] ibac_sni's `utils.load_model` takes a DIRECTORY and appends
        # "model.pt" itself, and `Agent.__init__` calls it. Staging the checkpoint under that name
        # lets THEIR loader load it -- reaching past it to torch.load here would mean the object
        # doing the acting is one we built, which is the one thing driving a foreign `act` must not
        # do. The runner names every family's retained checkpoint `snapshot.pt`, hence the copy.
        import shutil
        import tempfile
        staged = pathlib.Path(tempfile.mkdtemp(prefix="ibac_sni_model_"))
        shutil.copy2(snap, staged / "model.pt")
        agent = staged
        record = _record_factory()
        regimes = [item.strip() for item in a.regimes.split(",") if item.strip()]
        scenes = [int(item) for item in a.scenes.split(",") if item.strip()]
        context = {"cell": f"{a.baseline}-s{a.seed}", "baseline": a.baseline,
                   "family": a.family, "seed": a.seed}
        return _run_grid(a, agent, record, regimes, scenes, context, frame)

    import torch
    with snap.open("rb") as handle:
        payload = torch.load(handle, map_location="cpu", weights_only=False)
    # RL-ViGen pickles a dict around the agent; dmc_gb pickles the agent itself
    # (`torch.save(agent, ...)` at train.py:147). One line, and getting it wrong is a TypeError
    # several minutes into a grid rather than at the load.
    # idaac saves a list whose first element is the actor-critic; RL-ViGen a dict; dmc_gb the
    # agent itself. Three families, three shapes, one line -- and getting it wrong is a TypeError
    # minutes into a grid rather than at the load.
    if isinstance(payload, dict) and "agent" in payload:
        agent = payload["agent"]
    elif isinstance(payload, (list, tuple)) and payload:
        agent = payload[0]
    else:
        agent = payload
    device = torch.device(a.device)
    agent.device = device
    for attribute in vars(agent).values():
        if isinstance(attribute, torch.nn.Module):
            attribute.to(device)

    if a.family == "ppg":
        # PpoModel IS an nn.Module (RL-ViGen's and dmc_gb's agents are plain objects holding
        # modules), so the attribute walk above moves nothing and `.to` has to be called on it.
        agent.to(device)
        agent.eval()

    record = _record_factory()
    regimes = [item.strip() for item in a.regimes.split(",") if item.strip()]
    scenes = [int(item) for item in a.scenes.split(",") if item.strip()]
    context = {"cell": f"{a.baseline}-s{a.seed}", "baseline": a.baseline,
               "family": a.family, "seed": a.seed}
    return _run_grid(a, agent, record, regimes, scenes, context, frame)


if __name__ == "__main__":
    raise SystemExit(main())
