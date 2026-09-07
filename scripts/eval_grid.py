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

**It evaluates all seven implementation families covering the twelve baselines:** the RL-ViGen
five, dmc_gb's `rad`/`soda`, and the four authored paths `idaac`, `ppg`, `ibac_sni`, `alda` and
`ctrl`. The latter paths each drive the baseline's own policy and environment construction; they
are not a shared substitute for the original algorithms. `scripts/audit_eval_state.py` remains the
record of the historical coverage gap, while this entry point is now the completed production
evaluator.

**It does not aggregate across regimes.** Each row names its regime and its scene set. `eval-hard`
is not `eval-medium` plus more: medium randomises the robot and hard fixes the robot and adds a
moving light and a video background, and measured in observation space medium sits *further* from
train than hard does. A single ordered "difficulty" column would assert something the instrument
contradicts.
"""
from __future__ import annotations

import argparse
import atexit
import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import sys
import tempfile
import time

# [Added 2026-09-05.] MUST be set before torch initialises CUDA, hence module scope and not inside
# main().  `torch.use_deterministic_algorithms(True)` SUCCEEDS on CUDA and then raises at the first
# CuBLAS operation -- a linear layer -- with:
#
#   RuntimeError: Deterministic behavior was enabled ... but this operation is not deterministic
#   because it uses CuBLAS and you have CUDA >= 10.2 ... you must set CUBLAS_WORKSPACE_CONFIG
#
# so determinism has NEVER completed a CUDA evaluation since it was added. The try/except around
# the setting call could not catch it: the error comes from the operation, not the flag. Job
# bt1s5a6pub9muqgcoil9 died on it after the two earlier defects in front of it were fixed.
#
# `:4096:8` is the larger of the two documented settings; it costs a little device memory and,
# unlike `:16:8`, does not restrict CuBLAS to a single stream.  `setdefault` so a caller can still
# choose, and so RLGEN_DETERMINISTIC_EVAL=0 runs are unaffected either way.
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from datasphere.native.evaluator_identity import (  # noqa: E402
    canonical_evaluation_scope,
    effective_deterministic_setting,
    family_eval_policy_mode,
    measurement_revision,
    scope_revision,
)
from rlgen.protocol import OBSERVATION_GEOMETRY  # noqa: E402

from scripts import eval_across_scenes as _eval_across_scenes  # noqa: E402
from scripts.eval_across_scenes import _setup, find_snapshot, run_scene  # noqa: E402
from scripts.eval_provenance import (  # noqa: E402
    ActionDiagnosticsAccumulator,
    completed_episode_diagnostics,
    evaluator_code_revision,
    evaluator_config_revision,
    evaluator_family_code_revision,
    evaluator_family_config_revision,
    evaluator_family_revision,
    evaluator_revision,
    placement_hash,
    policy_scale,
    runtime_import_manifest,
)


LAST_PLACEMENT_WITNESSES: list[str] = []
LAST_EPISODE_DIAGNOSTICS: list[dict] = []
LAST_POLICY_ACTION_DIAGNOSTICS: dict | None = None
DETERMINISTIC_ALGORITHMS = False
# Filled after argparse selects a family.  A global value at import time can only describe the
# shared harness; production rows need the selected family's loaded policy/environment closure.
EVALUATOR_REVISION = None
EVALUATOR_CODE_REVISION = None
EVALUATOR_CONFIG_REVISION = None
EVALUATOR_SCOPE = None
EVALUATOR_SCOPE_REVISION = None
EVALUATOR_MEASUREMENT_REVISION = None


def _new_action_probe(env):
    """Start observing adapter output without changing the action sent to the environment."""
    global LAST_POLICY_ACTION_DIAGNOSTICS
    LAST_POLICY_ACTION_DIAGNOSTICS = None
    return ActionDiagnosticsAccumulator(env)


def _finish_action_probe(probe):
    global LAST_POLICY_ACTION_DIAGNOSTICS
    LAST_POLICY_ACTION_DIAGNOSTICS = probe.finish()


# `completed_episode_diagnostics` is imported from scripts.eval_provenance, not defined
# here.  This file used to carry a second copy: same traversal, same tolerant/partial
# semantics, but WITHOUT the required-field validation.  The tests exercised the strict
# helper while production ran the permissive one, so a malformed diagnostics row could
# pass every test and still be recorded.  External review 7 named the seam; one
# definition closes it.


def place_agent_on_device(agent, device):
    """Put whatever holds the weights on `device`, whatever shape the family pickled.

    Three shapes reach here: RL-ViGen and dmc_gb pickle a plain object whose attributes are the
    modules; ppg and idaac pickle an `nn.Module` directly.

    The attribute walk handles the first. For the second it moves NOTHING, because an nn.Module
    keeps its children in `_modules` rather than as plain attributes -- so `vars(agent)` contains
    dicts, not modules. ppg had an explicit branch for that; idaac, the same shape, had none, so
    its weights stayed on CPU while `agent.device` said cuda and the env produced cuda
    observations. Job bt16ikro8c3mu3id9p8n died on exactly that:

        model.py:77 RuntimeError: Input type (torch.cuda.FloatTensor) and weight type
        (torch.FloatTensor) should be the same

    It surfaced only once the regime read-back was fixed, because construction failed first: one
    fail-closed guard was hiding a second defect behind it.

    Keyed on the SHAPE rather than the family name, so the next family to pickle a module inherits
    the fix instead of the bug.
    """
    import torch
    agent.device = device
    for attribute in vars(agent).values():
        if isinstance(attribute, torch.nn.Module):
            attribute.to(device)
    if isinstance(agent, torch.nn.Module):
        agent.to(device)
        agent.eval()
    return agent


def placement_witness(observation) -> str:
    """Hash the first post-reset observation as an auditable realized-placement witness."""
    digest = hashlib.sha256()

    def add(value):
        if isinstance(value, dict):
            for key in sorted(value):
                digest.update(str(key).encode())
                add(value[key])
            return
        if isinstance(value, (tuple, list)):
            for item in value:
                add(item)
            return
        try:
            if hasattr(value, "detach"):
                value = value.detach().cpu().numpy()
            array = np.asarray(value)
            digest.update(str(array.shape).encode())
            digest.update(str(array.dtype).encode())
            digest.update(array.tobytes())
        except Exception:
            digest.update(repr(value).encode())

    add(observation)
    return digest.hexdigest()


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


def placement_condition_seed(eval_seed: int, scene_id: int, episode_index: int) -> int:
    """Stable per-episode seed, independent of family-specific construction/reset machinery."""
    return int(np.random.SeedSequence([int(eval_seed), int(scene_id), int(episode_index)])
               .generate_state(1, dtype=np.uint32)[0])


def seed_episode_placement(eval_seed: int, scene_id: int, episode_index: int) -> int:
    condition = placement_condition_seed(eval_seed, scene_id, episode_index)
    import random as _random
    _random.seed(condition)
    np.random.seed(condition)
    return condition


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


def verify_regime(env, mode, scene_id, family, *, strict=False):
    """Read back the regime and scene the env ACTUALLY applied, and refuse a silent fallback.

    [Claude 2026-09-04] `eval_across_scenes.run_scene` has done this for the RL-ViGen five since
    2026-08-25 and says exactly why: `make_env` falls back to `robo_config.yaml` for anything it is
    not given, so a mode or scene that fails to take effect leaves every cell identical and yields
    **a retention of about 1.0** -- a clean-looking null that means the opposite of what it appears
    to. The other six families had no such check, so the same silent failure was available to all
    of them and would have looked like a result.

    Best effort by construction: the six build their envs through different stacks (gym, dm_control
    TimeStep, three kinds of vector env), and `VGBWrapper` stores the regime as `_mode` somewhere
    down a chain whose shape differs per family. So this walks for it, and when it cannot read a
    value it **says so on stderr and abstains** rather than returning quietly -- a check that cannot
    run and a check that passed must not look the same.

    Deliberately does NOT probe with `reset()`+`step()`, which is how the rlvigen check reads the
    scene back. That probe consumes draws from the GLOBAL numpy RNG ([C69](../docs/CONSTRUCTION.md#c69):
    `UniformRandomSampler` calls bare `np.random.uniform`), so it shifts the door placements of
    every episode that follows it. `eval_across_scenes` can afford that because it has always paid
    the cost, uniformly, in every cell it has ever run. Adding it to these six now would change the
    episodes they evaluate and so silently invalidate comparison against the numbers already in
    `results/records/` -- `ctrl` 36.699 and the `idaac` 9.023 that discharged its burden. So the
    scene half of this check reads `last_info` only where a family already populates it, and the
    mode half -- the regime axis, the one retention is a ratio across -- is what is enforced.

    Raises on a POSITIVE mismatch: something was read back and it was wrong. With ``strict=True``
    it also raises when either axis cannot be read back; production records must never turn an
    unverified intervention into a plausible-looking result. The default remains non-strict for
    exploratory callers and for old archives whose wrapper does not expose these fields.
    """
    node, seen_mode = env, None
    # RL-ViGen's dm_env adapter hoists the authoritative values to the outer wrapper. Prefer this
    # compact read-back before descending, while retaining the descent for the other families.
    hoisted = getattr(env, "_vigen_regime", None)
    if isinstance(hoisted, dict):
        seen_mode = hoisted.get("mode")
        seen_scene = hoisted.get("scene_id")
    else:
        seen_scene = None
    for _ in range(10):
        if node is None:
            break
        node_info = getattr(node, "last_info", None)
        if seen_scene is None and isinstance(node_info, dict):
            seen_scene = node_info.get("scene_id")
        if hasattr(node, "_mode") and seen_mode is None:
            seen_mode = getattr(node, "_mode")
        if seen_scene is None:
            seen_scene = getattr(node, "_scene_id", getattr(node, "scene_id", None))
        if seen_mode is not None and seen_scene is not None:
            break
        children = []
        for attr in ("env", "_env", "_gym_env", "venv", "gym_env", "bv_env", "unwrapped"):
            child = getattr(node, attr, None)
            if child is not None:
                children.append(child)
        # IDAAC's DummyVecEnv and PPG's gym3 ConcatEnv expose their real env only through a
        # sequence. Inspect the first one (the evaluator constructs one env) without reset/step;
        # touching the environment would consume C69's global placement RNG.
        envs = getattr(node, "envs", None)
        if envs is not None:
            try:
                children.extend(list(envs)[:1])
            except TypeError:
                pass
        node = children[0] if children else None
    info = getattr(env, "last_info", None) or {}
    if seen_scene is None:
        seen_scene = info.get("scene_id") if isinstance(info, dict) else None

    if seen_mode is not None and seen_mode != mode:
        raise RuntimeError(
            f"{family}: asked for mode {mode!r}, env reports {seen_mode!r} -- the regime did not "
            "take effect. Every row of this grid would be measured in the wrong regime, and a "
            "retention near 1.0 would look like invariance.")
    if seen_scene is not None and int(seen_scene) != int(scene_id):
        raise RuntimeError(
            f"{family}: asked for scene {scene_id}, env reports {seen_scene!r} -- the scene did "
            "not take effect and this row would duplicate another.")
    if seen_mode is None or seen_scene is None:
        print(f"    ?? {family}: could not read back mode or scene; regime {mode!r}/scene "
              f"{scene_id} is UNVERIFIED for this cell. This is not a pass.", file=sys.stderr)
        if strict:
            raise RuntimeError(
                f"{family}: regime {mode!r}/scene {scene_id} is UNVERIFIED; refusing to emit "
                "a production evaluation record")


def verify_env_request(mode, scene_id, family):
    """Check the environment-variable seam used by ibac_sni before construction.

    ibac_sni's original constructor reads these two variables rather than accepting mode/scene
    arguments. The subsequent ``verify_regime`` read-back still provides the stronger check; this
    catches a runner/environment mutation before the constructor is called and documents the only
    valid ingress for this family.
    """
    requested_mode = os.environ.get("RLVIGEN_MODE")
    requested_scene = os.environ.get("RLVIGEN_SCENE_ID")
    if requested_mode != mode or requested_scene != str(scene_id):
        raise RuntimeError(
            f"{family}: request seam disagrees: mode={requested_mode!r}, scene_id="
            f"{requested_scene!r}, expected {mode!r}/{scene_id}")


def close_eval_env(env) -> None:
    """Release one family's renderer/env resources before the next grid cell is built."""
    closer = getattr(env, "close", None)
    if callable(closer):
        closer()


def dmc_eval_seed(mode, seed):
    """Match dmc_gb's train.py: test/eval environments use the seed+42 offset."""
    return seed if mode == "train" else seed + 42


def run_scene_dmc_gb(agent, task, scene_id, mode, episodes, seed, image_size, episode_length,
                     baseline="rad"):
    """One (regime, scene) cell for rad/soda, through dmc_gb's own env and action path.

    `select_action` is the deterministic one (`mu`); `sample_action` is the stochastic one, and
    train.py's own `evaluate` uses `select_action`. The success convention is the any-step one
    every baseline here shares -- see scripts/eval_across_scenes for why it is read per step.
    """
    env_seed = dmc_eval_seed(mode, seed)
    global LAST_PLACEMENT_WITNESSES
    global LAST_EPISODE_DIAGNOSTICS
    LAST_PLACEMENT_WITNESSES = []
    LAST_EPISODE_DIAGNOSTICS = []
    seed_the_placement_rng(env_seed)
    import torch
    import utils
    from env.wrappers import make_env

    env = make_env(domain_name="robosuite", task_name=task, seed=env_seed,
                   episode_length=episode_length, action_repeat=1,
                   image_size=image_size, mode=mode, scene_id=scene_id)
    verify_regime(env, mode, scene_id, "dmc_gb", strict=True)
    action_probe = _new_action_probe(env)
    returns, successes, flags = [], 0, []
    for episode_index in range(episodes):
        seed_episode_placement(seed, scene_id, episode_index)
        obs = env.reset()
        if episode_index == 0:
            _eval_across_scenes.verify_runtime_observation_geometry(
                obs, image_size=OBSERVATION_GEOMETRY[baseline][0],
                frame_stack=OBSERVATION_GEOMETRY[baseline][1], family=baseline)
        LAST_PLACEMENT_WITNESSES.append(placement_witness(obs))
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
            action_probe.observe(action)
            obs, reward, done, info = env.step(action)
            total += float(reward)
            succeeded = succeeded or bool((info or {}).get("success", False))
        returns.append(total)
        successes += int(succeeded)
        flags.append(int(succeeded))
    LAST_EPISODE_DIAGNOSTICS.extend(completed_episode_diagnostics(
        env, policy_scale(agent), len(returns)))
    _finish_action_probe(action_probe)
    close_eval_env(env)
    return np.array(returns), successes, flags


def _idaac_setup() -> None:
    """idaac evaluates through OUR RL-ViGen adapter and its own `act`.

    **The render size is part of the policy's input contract, not a preference.** idaac trains at
    64x64 with the current DMC-informed three-frame C2 profile; historical C1 checkpoints use one
    frame only through an explicit override. `rlgen/protocol.py`'s OBSERVATION_GEOMETRY records
    this and patch P6 makes reachable. Building the evaluation env at
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


def run_scene_idaac(agent, task, scene_id, mode, episodes, seed, frame_stack=None, policy_mode="native"):
    """One (regime, scene) cell for idaac, through the VecEnv stack its own evaluator uses.

    **It SAMPLES.** `model.py:332` is `def act(self, inputs, deterministic=False)` and `test.py`
    calls `act(obs)` without the flag, so idaac's own evaluation draws from the policy where nine
    other baselines take the mode. Reproduced here rather than corrected: the estimator is the
    method's, and `conventions.eval_policy_mode` records it as `sample` so no table pools the two.

    The scene sweep is possible because `make_rlvigen_venv` -- our adapter, not idaac's code --
    now takes `scene_id`. Its own evaluator pins 0, which is C45.
    """
    global LAST_PLACEMENT_WITNESSES
    global LAST_EPISODE_DIAGNOSTICS
    LAST_PLACEMENT_WITNESSES = []
    LAST_EPISODE_DIAGNOSTICS = []
    seed_the_placement_rng(seed)
    import torch
    from ppo_daac_idaac.envs import make_rlvigen_venv

    class _Args:
        pass

    args = _Args()
    args.seed = seed
    args.env_name = f"robosuite:{task}"
    args.condition_seed = seed
    # [Claude 2026-09-06, DECISION-SHEET A35, found completing IDAAC-C2] Without this, a checkpoint
    # trained at OBSERVATION_GEOMETRY["idaac"]'s frame_stack (now 3) would be evaluated at
    # `make_rlvigen_venv`'s own default of 1 -- a hard channel-count crash at the first conv layer,
    # not a silent mismatch, but broken either way. OBSERVATION_GEOMETRY is the same single source
    # of truth C98 already uses for this baseline's recorded evaluator_scope; read it here too
    # rather than hardcoding the value a second place.
    # [Claude 2026-09-07] Reads the protocol DIRECTLY. `main()` now refuses a --frame-stack that
    # contradicts OBSERVATION_GEOMETRY, so the old `if frame_stack is None else int(frame_stack)`
    # branch could no longer take its second path -- it was a dead alternative that made the
    # geometry look caller-supplied when it is protocol-supplied. The parameter is kept in the
    # signature so the call sites stay unchanged.
    args.frame_stack = OBSERVATION_GEOMETRY["idaac"][1]
    device = getattr(agent, "device", torch.device("cpu"))
    if not isinstance(device, torch.device):
        device = torch.device(device)
    envs = make_rlvigen_venv(args, device, mode, 1, scene_id=scene_id)
    verify_regime(envs, mode, scene_id, "idaac", strict=True)
    action_probe = _new_action_probe(envs)
    original_step_async = envs.venv.step_async

    def _observed_step_async(actions):
        # VecPyTorchProcgen converts its tensor argument to NumPy immediately before forwarding
        # to `venv`; observing here avoids a second host copy while still seeing the exact numeric
        # action that enters the vector environment.
        action_probe.observe(actions)
        return original_step_async(actions)

    envs.venv.step_async = _observed_step_async

    # THE RETURN COMES FROM VecMonitor, NOT FROM step().
    #
    # The stack is DummyVecEnv -> VecMonitor -> VecNormalize, so the reward `step()` hands back is
    # the NORMALISED one the agent trains on, while the monitor -- sitting inside the normaliser --
    # records the raw episode return under `info['episode']['r']`. Summing `step()`'s reward gave
    # 22.4 against the run's own logged 1.55 for the same checkpoint and regime: a 14x error, in
    # normalised units, that would have read as a generalisation result. idaac's own `test.py`
    # reads `info['episode']['r']`, and so does this.
    returns, successes, flags = [], 0, []
    seed_episode_placement(seed, scene_id, 0)
    obs = envs.reset()
    _eval_across_scenes.verify_runtime_observation_geometry(
        obs, image_size=OBSERVATION_GEOMETRY["idaac"][0],
        frame_stack=OBSERVATION_GEOMETRY["idaac"][1], family="idaac")
    LAST_PLACEMENT_WITNESSES.append(placement_witness(obs))
    succeeded = False
    while len(returns) < episodes:
        with torch.no_grad():
            # A25 addendum: `deterministic` defaults False in model.py:332, which is
            # what test.py relies on; `mode` asks for the other branch explicitly.
            out = agent.act(obs, deterministic=(policy_mode == "mode"))
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
                if len(LAST_PLACEMENT_WITNESSES) < episodes:
                    LAST_PLACEMENT_WITNESSES.append(placement_witness(obs))
    LAST_EPISODE_DIAGNOSTICS.extend(completed_episode_diagnostics(
        envs, policy_scale(agent), len(returns)))
    _finish_action_probe(action_probe)
    close_eval_env(envs)
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


def run_scene_ppg(agent, task, scene_id, mode, episodes, seed, frame_stack=None, policy_mode="native"):
    """One (regime, scene) cell for ppg, through PPG's own Roller and VecMonitor2.

    **It SAMPLES, on a weaker claim than the other three.** `PpoModel.act` draws from the policy
    distribution and this repository ships no deterministic-action path to call instead.

    State the provenance precisely (external review 24): OpenAI's release contains NO dedicated
    evaluation runner. Native sampling here follows the only released `PpoModel.act()` convention;
    it is NOT independently verified evaluation-time behaviour, as it is for idaac and ibac_sni,
    whose released evaluation paths sample, or for ctrl, whose released evaluator takes the mode.
    This is the one family whose `native` rests on a rollout convention rather than on an
    evaluator, and the deterministic `--policy-mode mode` pass is the check against it.

    Episodes are counted by `roller.episode_count`, which PPG's `VecMonitor2` increments when an
    env resets. Counting closed episodes rather than steps is what makes the sample size the
    requested one; a step-counted loop would truncate the last episode and bias the mean low.
    """
    global LAST_PLACEMENT_WITNESSES
    global LAST_EPISODE_DIAGNOSTICS
    LAST_PLACEMENT_WITNESSES = []
    LAST_EPISODE_DIAGNOSTICS = []
    seed_the_placement_rng(seed)
    from phasic_policy_gradient.envs import get_venv
    from phasic_policy_gradient.roller import Roller

    venv = get_venv(num_envs=1, env_name=f"robosuite:{task}", mode=mode, seed=seed,
                    scene_id=scene_id, condition_seed=seed,
                    frame_stack=OBSERVATION_GEOMETRY["ppg"][1])   # protocol, not the caller
    verify_regime(venv, mode, scene_id, "ppg", strict=True)
    initial_observation = venv.observe()
    _eval_across_scenes.verify_runtime_observation_geometry(
        initial_observation[1] if isinstance(initial_observation, tuple) else initial_observation,
        image_size=OBSERVATION_GEOMETRY["ppg"][0],
        frame_stack=OBSERVATION_GEOMETRY["ppg"][1], family="ppg")
    action_probe = _new_action_probe(venv)
    original_venv_act = venv.act

    def _observed_venv_act(action):
        action_probe.observe(action)
        return original_venv_act(action)

    # Roller owns the policy-to-environment call, so observing this boundary preserves its
    # callback signature and avoids moving a CUDA tensor to CPU solely for diagnostics.
    venv.act = _observed_venv_act
    try:
        # [Claude 2026-09-07, A25 addendum] PpoModel.act draws `pd.sample()` and this repo ships no
        # deterministic path to call instead, so `mode` is implemented HERE, in our harness, rather
        # than by editing runnable/ppg -- the same principle as every other evaluator delta. The
        # continuous head is torch.distributions.Normal (distr_builder.py:28), whose mode is its
        # mean; `pd.mean` rather than `pd.mode()` because the latter is not in every torch version
        # this project pins.
        act_fn = agent.act
        if policy_mode == "mode":
            def act_fn(ob, first, state_in, _model=agent):
                from phasic_policy_gradient import tree_util as _tu
                pd, _vpred, _aux, state_out = _model(
                    ob=_tu.tree_map(lambda x: x[:, None], ob), first=first[:, None],
                    state_in=state_in)
                deterministic = pd.mean
                return (_tu.tree_map(lambda x: x[:, 0], deterministic), state_out,
                        dict(vpred=_vpred[:, 0], logp=_vpred[:, 0] * 0.0))

        roller = Roller(venv=venv, act_fn=act_fn, initial_state=agent.initial_state(1),
                        keep_buf=max(100, episodes))
        while roller.episode_count < episodes:
            roller.multi_step(32)
        returns = np.array(roller.recent_eprets[:episodes], dtype=float)
        infos = roller.recent_epinfos[:episodes]
        # [Corrected 2026-09-05, external review 7] Both of these used to run in the wrong place and
        # each would have terminated every ppg cell.
        #
        # The witness collection was ABOVE the rollout loop.  `extend` copies what the list holds at
        # that moment -- the construction reset alone -- and keeps no reference to the appends that
        # `roller.multi_step` then makes, so `_run_grid`'s `len(witnesses) != len(returns)` check
        # would fire with 1 witness against 20 returns.  envs.py appends on every reset and episode
        # i begins at reset i, so the first `episodes` entries are the placements the episodes
        # actually ran under; the [:episodes] slice matches the convention at :480.
        LAST_PLACEMENT_WITNESSES.extend(list(getattr(venv, "_placement_witnesses", []))[:episodes])
        # The diagnostics call was BELOW the `finally` that closes the venv, so it interrogated a
        # torn-down wrapper stack.  That was survivable while missing diagnostics were tolerated;
        # it is fatal now that the collector raises when it finds fewer than `episodes` of them.
        vals = [float(item.get("episode_success", 0.0) or 0.0) for item in infos]
        successes = int(sum(vals))
        flags = [int(bool(v)) for v in vals]
        LAST_EPISODE_DIAGNOSTICS.extend(completed_episode_diagnostics(
            venv, policy_scale(agent), len(returns)))
        _finish_action_probe(action_probe)
    finally:
        # One mujoco context per scene, ten scenes per regime: without this the grid accumulates
        # them until the renderer refuses. gym3 venvs do not all define close(), hence the getattr.
        closer = getattr(venv, "close", None)
        if callable(closer):
            closer()
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


def run_scene_ibac_sni(built, task, scene_id, mode, episodes, seed, policy_mode="native"):
    """One (regime, scene) cell for ibac_sni, through its own `Agent` and `get_actions`.

    **It SAMPLES.** `Agent.__init__` takes `argmax=False` by default and `scripts/evaluate.py`
    never passes the flag, so `dist.sample()` is what its own evaluation does. Reproduced, not
    corrected -- `COMPARABILITY_CONTRACT.md` §5c.

    **The "agent" here is a DIRECTORY, not a loaded object**, because `utils.load_model` takes a
    model_dir and appends `model.pt` itself. `main()` stages the snapshot under that name rather
    than reaching past their loader, so the object doing the acting is the one their own evaluator
    would have built.
    """
    global LAST_PLACEMENT_WITNESSES
    global LAST_EPISODE_DIAGNOSTICS
    LAST_PLACEMENT_WITNESSES = []
    LAST_EPISODE_DIAGNOSTICS = []
    seed_the_placement_rng(seed)
    os.environ["RLVIGEN_MODE"] = mode
    os.environ["RLVIGEN_SCENE_ID"] = str(scene_id)
    verify_env_request(mode, scene_id, "ibac_sni")
    import utils as ibac_utils

    model_dir, device = built
    env_id = f"robosuite:{task}"
    env = ibac_utils.make_rlvigen_env(env_id, seed)
    # The fourth positional is `argmax`: False samples (evaluate.py's own default),
    # True takes the mode.
    agent = ibac_utils.Agent(env_id, env.observation_space, str(model_dir),
                             policy_mode == "mode", 1,
                             device=device)
    verify_regime(env, mode, scene_id, "ibac_sni", strict=True)
    action_probe = _new_action_probe(env)

    returns, successes, flags = [], 0, []
    for episode_index in range(episodes):
        seed_episode_placement(seed, scene_id, episode_index)
        obs = env.reset()
        if isinstance(obs, tuple):
            obs = obs[0]
        if episode_index == 0:
            _eval_across_scenes.verify_runtime_observation_geometry(
                obs, image_size=OBSERVATION_GEOMETRY["ibac_sni"][0],
                frame_stack=OBSERVATION_GEOMETRY["ibac_sni"][1], family="ibac_sni")
        LAST_PLACEMENT_WITNESSES.append(placement_witness(obs))
        total, succeeded, done = 0.0, False, False
        while not done:
            action = agent.get_actions([obs])[0]
            action_probe.observe(action)
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
    LAST_EPISODE_DIAGNOSTICS.extend(completed_episode_diagnostics(
        env, policy_scale(agent), len(returns)))
    _finish_action_probe(action_probe)
    close_eval_env(env)
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
    from the env's shapes, and only then can `load_checkpoint` fill state dicts.

    **CORRECTED 2026-09-05, external review 13 section 3.** This used to say construction was cheap
    because "the allocation happens in training, which is never reached here" -- false.
    `alda_trainer.build()` allocates the replay buffer unconditionally as part of model
    construction, not training, and its 1,000,000-capacity default pre-fills ~11.4 GiB of image
    payload before Python-object overhead, matching the project's measured ~15.3 GiB training
    footprint. Every evaluator startup was paying that cost for a buffer evaluation never reads
    from (evaluation never calls `update()`). `build()` below is called ONCE (a prior version also
    called `initialize_env_dmc` separately first, double-constructing the env stack) with
    `replay_capacity=1, prefill=False`, which `alda_trainer.build()` accepts precisely so a caller
    can skip the training allocation -- model construction is unaffected, only the buffer shrinks.
    """
    import yaml
    from common.utils import create_instance_from_spec

    spec_path = ROOT / "runnable" / "alda" / "specs" / "train_alda_robosuite_door.yaml"
    spec = yaml.load(spec_path.read_text(encoding="utf-8"), Loader=yaml.loader.FullLoader)
    spec["trainer"]["config"]["device"] = device
    spec["trainer"]["config"]["use_wandb"] = False
    spec["trainer"]["config"]["debug"] = True
    spec["trainer"]["config"]["exp_dir"] = tempfile.mkdtemp(prefix="alda_eval_")
    atexit.register(shutil.rmtree, spec["trainer"]["config"]["exp_dir"], ignore_errors=True)
    trainer = create_instance_from_spec(spec["trainer"], name=spec["name"])
    # build() initializes the env exactly once and normally pre-fills the training replay buffer.
    # Evaluation never calls update(), so a one-slot empty buffer preserves the trainer's model
    # construction while avoiding an unnecessary ~15 GiB allocation per evaluator process.
    trainer.build(spec, replay_capacity=1, prefill=False)
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
    global LAST_PLACEMENT_WITNESSES
    global LAST_EPISODE_DIAGNOSTICS
    LAST_PLACEMENT_WITNESSES = []
    LAST_EPISODE_DIAGNOSTICS = []
    seed_the_placement_rng(seed)
    trainer, spec = built
    from dmcontrol_generalization_benchmark.src.env.wrappers import FrameStack, DMCObsWrapper
    from trainers.alda_trainer import _RoboRGB
    from robosuitevgb.utils import make_env as robo_make_env

    env_config = spec["trainer"]["config"]["env"]
    inner = _RoboRGB(robo_make_env(task_name=task, seed=seed, scene_id=scene_id, mode=mode),
                     env_config["episode_length"])
    # int(): ALDA's own YAML-native env_config["frame_stack"] is already an int, but the string
    # "frame_stack" is now ALSO a families.json descriptor key for a different baseline (idaac,
    # DECISION-SHEET A35) -- test_descriptor_values_are_converted.py's scan matches on key name
    # only, with no dict-identity awareness, so it flags this line too. Harmless no-op conversion,
    # not a real bug here, but it makes this line unambiguously safe either way.
    env = DMCObsWrapper(FrameStack(inner, int(env_config["frame_stack"])))
    verify_regime(env, mode, scene_id, "alda", strict=True)
    action_probe = _new_action_probe(env)

    returns, successes, flags = [], 0, []
    for episode_index in range(episodes):
        seed_episode_placement(seed, scene_id, episode_index)
        obs = env.reset()
        if isinstance(obs, tuple):
            obs = obs[0]
        if episode_index == 0:
            _eval_across_scenes.verify_runtime_observation_geometry(
                obs, image_size=OBSERVATION_GEOMETRY["alda"][0],
                frame_stack=OBSERVATION_GEOMETRY["alda"][1], family="alda")
        LAST_PLACEMENT_WITNESSES.append(placement_witness(obs))
        total, succeeded, done = 0.0, False, False
        while not done:
            # Exactly alda's own evaluate(): `select_action(preprocess_obs(obs['rgb'][None]))`.
            # `select_action` takes an array and DMCObsWrapper yields a {'rgb','state'} dict, so the
            # extraction, the batch axis and the preprocessing are all part of how alda acts -- not
            # harness plumbing to be improvised. DMCObsWrapper returns a 5-tuple and info is 5th.
            action = trainer.select_action(trainer.preprocess_obs(obs["rgb"][None]))
            action_probe.observe(action)
            obs, reward, done, _truncated, info = env.step(action)
            total += float(reward or 0.0)
            info = info if isinstance(info, dict) else {}
            succeeded = succeeded or bool(info.get("success", False))
        returns.append(total)
        successes += int(succeeded)
        flags.append(int(succeeded))
    LAST_EPISODE_DIAGNOSTICS.extend(completed_episode_diagnostics(
        env, policy_scale(trainer), len(returns)))
    _finish_action_probe(action_probe)
    close_eval_env(env)
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


def _ctrl_config() -> dict:
    """Read the evaluator's reconstruction values from the production descriptor.

    Flax's ``from_bytes`` fills a target; it does not construct one.  Keeping a second literal
    copy here meant the evaluator could silently reconstruct a different CTRL model after a
    descriptor edit.  The descriptor is already the source of truth for the training argv, so it
    owns these reconstruction values too.
    """
    descriptor = json.loads((ROOT / "datasphere" / "native" / "families.json").read_text())
    return descriptor["ctrl"]["constants"]


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

    d = _ctrl_config()
    model = CTRLModel(dims=(256, 256), n_cluster=int(d["num_clusters"]), n_actions=n_actions,
                      continuous=True, n_att_heads=int(d["n_att_heads"]),
                      embedding_type=d["embedding_type"])
    key = jax.random.PRNGKey(0)
    # `families.json` stores constants as STRINGS -- they become CLI flags -- so every numeric use
    # must convert. Every sibling here does (`int(d["num_clusters"])`, `float(d["lr"])`); these two
    # did not, and JAX refuses a shape containing '10', so EVERY ctrl evaluation died at load with
    # `Shapes must be 1D sequences of concrete values of integer type`. Training was unaffected,
    # which is why it survived to be found by the first ctrl cell that trained to completion.
    cluster_len = int(d["cluster_len"])
    fake_state = jnp.zeros((1, cluster_len, 64, 64, 3))
    fake_act = jnp.zeros((1, cluster_len, n_actions))
    params = model.init(key, state=fake_state, action=fake_act, reward=fake_act)
    tx_ppo = optax.chain(optax.clip_by_global_norm(float(d["max_grad_norm"])),
                         optax.adam(float(d["lr"]), eps=1e-5))
    tx_cluster = optax.chain(optax.clip_by_global_norm(float(d["max_grad_norm"])),
                             optax.adam(float(d["lr_ctrl"]), eps=1e-5))
    train_state = TrainState.create(apply_fn=model.apply, params=params, tx=(tx_ppo, tx_cluster))
    train_state = from_bytes(train_state, pathlib.Path(snapshot).read_bytes())
    return train_state, model


def run_scene_ctrl(built, task, scene_id, mode, episodes, seed, policy_mode="native"):
    """One (regime, scene) cell for ctrl, through its own vec env and `algo.select_action`.

    **It TAKES THE MODE**, and that reverses the 2026-09-04 entry this docstring used to carry.

    That entry reasoned from `train_ppo.py:244,253`, which pass `sample=True`, and concluded that
    reproducing "the reporting path" meant sampling. Wrong criterion: those are TRAINING calls. The
    convention this evaluator reproduces is each baseline's own EVALUATION-time rule, and ctrl
    ships one -- `runnable/ctrl/evaluate_ppo.py:84` calls `select_action(..., greedy=True)`, whose
    greedy branch is `logits.argmax(1)` (:71-72). The continuous analogue of that discrete argmax
    is `pi.mode()`, i.e. `sample=False`.

    So ctrl's `native` and `mode` policy modes coincide, and `FAMILY_EVAL_POLICY_MODE["ctrl"]` is
    `mode`. Found by external review 24 and confirmed against the pinned upstream.

    **The observation scaling is theirs**: `state.astype(float32) / 255.`, exactly as at those call
    sites. `RLViGenVecEnvCustom` yields the stacked-frame layout the model expects.
    """
    global LAST_PLACEMENT_WITNESSES
    global LAST_EPISODE_DIAGNOSTICS
    LAST_PLACEMENT_WITNESSES = []
    LAST_EPISODE_DIAGNOSTICS = []
    seed_the_placement_rng(seed)
    import jax
    import jax.numpy as jnp
    from algo import select_action
    from vec_env import RLViGenVecEnvCustom

    train_state, model = built
    # normalize_rewards=False is NOT a tuning choice -- it is CTRL's own evaluation convention.
    # `RLViGenVecEnvCustom` is added by runnable/_patches/ctrl.patch:686 (NOT the ProcgenVecEnvCustom
    # at vec_env.py:17); its __init__ defaults normalize_rewards=True and then puts VecNormalize
    # OUTSIDE VecMonitor, so `step()` hands back a reward divided by a running return std and
    # clipped at 10 -- units of its own moving statistics, not Door's.
    #
    # REGISTER.md:198 established that all twelve baselines report RAW returns *in their training
    # loops*, because the monitor sits inside the normalizer.  That is a different quantity from
    # this one: the loop below sums the OUTERMOST `step()` reward and never reads the monitor, so
    # ctrl's evaluated return was the only one of the twelve not in Door units.  That same register
    # entry anticipated this fix -- "normalize_rewards is a live parameter ... so the offline
    # harness can construct a raw-reward env deliberately rather than by luck".
    #
    # ctrl's own evaluator already does exactly this: evaluate_ppo.py:38 passes False, while
    # train_ppo.py:91,99,106 pass True.  Both are byte-identical in ext/ctrl_public.
    # Found by external review 8.
    env = RLViGenVecEnvCustom(f"robosuite:{task}", mode=mode, num_envs=1, seed=seed,
                              scene_id=scene_id, condition_seed=seed,
                              normalize_rewards=False)
    verify_regime(env, mode, scene_id, "ctrl", strict=True)
    action_probe = _new_action_probe(env)
    key = jax.random.PRNGKey(seed)

    # [Corrected 2026-09-05, external reviews 8 and 9 -- and I refuted this once before, wrongly.]
    #
    # ONE reset before the loop, and none inside it. `_SyncVecEnv` AUTO-RESETS on done
    # (`vec_env.py`, `step_wait` calls `_reset_one`) and `_reset_one` advances
    # `_episode_indices[index] += 1` on EVERY reset. So an explicit reset per measured episode
    # consumed a SECOND condition index each time: measured episode i actually ran condition index
    # **2i**, while the record claimed i.
    #
    # That silently unpaired ctrl from every other family and made its recorded
    # `placement_condition_seeds` wrong. This is the idaac and ppg pattern -- reset once, let the
    # vector env's auto-reset begin each subsequent episode -- which is why those two were correct.
    #
    # Note `seed_episode_placement` cannot fix it from out here: `_reset_one` re-seeds numpy AFTER
    # this function does, so the wrapper's counter wins regardless of what we seed.
    returns, successes, flags = [], 0, []
    seed_episode_placement(seed, scene_id, 0)
    state = env.reset()
    _eval_across_scenes.verify_runtime_observation_geometry(
        state, image_size=OBSERVATION_GEOMETRY["ctrl"][0],
        frame_stack=OBSERVATION_GEOMETRY["ctrl"][1], family="ctrl")
    LAST_PLACEMENT_WITNESSES.append(placement_witness(state))
    for episode_index in range(episodes):
        total, succeeded, done = 0.0, False, False
        while not done:
            action, _, _, key = select_action(train_state.params, train_state.apply_fn, model.ac,
                                              jnp.asarray(state).astype(jnp.float32) / 255.,
                                              # ctrl's native rule IS the deterministic one, so
                                              # both policy modes coincide here. See the docstring.
                                              key, sample=False)
            action_for_env = np.asarray(action)
            action_probe.observe(action_for_env)
            state, reward, done_arr, infos = env.step(action_for_env)
            done = bool(np.asarray(done_arr).reshape(-1)[0])
            total += float(np.asarray(reward).reshape(-1)[0])
            info = infos[0] if isinstance(infos, (list, tuple)) and infos else {}
            succeeded = succeeded or bool((info or {}).get("success", False))
        returns.append(total)
        successes += int(succeeded)
        flags.append(int(succeeded))
        # `state` now holds the observation `_SyncVecEnv`'s auto-reset produced, i.e. the first
        # frame of the NEXT episode -- so this is that episode's placement witness. Capped at
        # `episodes` because the final auto-reset begins an episode nobody measures, exactly as
        # idaac does at its own loop.
        if len(LAST_PLACEMENT_WITNESSES) < episodes:
            LAST_PLACEMENT_WITNESSES.append(placement_witness(state))
    LAST_EPISODE_DIAGNOSTICS.extend(completed_episode_diagnostics(
        env, policy_scale(train_state), len(returns)))
    _finish_action_probe(action_probe)
    close_eval_env(env)
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
    sink = open(a.out, "a" if a.append else "w", buffering=1) if a.out else None

    def emit(row: dict) -> None:
        rows.append(row)
        if sink is not None:
            sink.write(json.dumps(row) + "\n")
            sink.flush()

    started = time.time()
    measurement_fields = {
        "evaluator_scope": EVALUATOR_SCOPE,
        "evaluator_scope_revision": EVALUATOR_SCOPE_REVISION,
        "evaluator_measurement_revision": EVALUATOR_MEASUREMENT_REVISION,
    }
    for regime in regimes:
        per_scene: dict[int, np.ndarray] = {}
        successes = 0
        for scene in scenes:
            print(f"  {regime:12s} scene {scene} ...", file=sys.stderr, flush=True)
            if a.family == "idaac":
                returns, succ, flags = run_scene_idaac(agent, a.task, scene, regime, a.episodes,
                                                a.episode_seed, a.frame_stack, policy_mode=a.policy_mode)
            elif a.family == "ctrl":
                returns, succ, flags = run_scene_ctrl(agent, a.task, scene, regime, a.episodes,
                                               a.episode_seed, policy_mode=a.policy_mode)
            elif a.family == "alda":
                returns, succ, flags = run_scene_alda(agent, a.task, scene, regime, a.episodes,
                                               a.episode_seed)
            elif a.family == "ibac_sni":
                returns, succ, flags = run_scene_ibac_sni(agent, a.task, scene, regime, a.episodes,
                                                   a.episode_seed, policy_mode=a.policy_mode)
            elif a.family == "ppg":
                returns, succ, flags = run_scene_ppg(agent, a.task, scene, regime, a.episodes,
                                              a.episode_seed, a.frame_stack, policy_mode=a.policy_mode)
            elif a.family == "dmc_gb":
                returns, succ, flags = run_scene_dmc_gb(agent, a.task, scene, regime, a.episodes,
                                                 a.episode_seed, a.image_size, a.episode_length,
                                                 baseline=a.baseline)
            else:
                # [Claude 2026-09-07] `declared_image_size` is a local of `main()`; referencing it
                # here raised `NameError: name 'declared_image_size' is not defined` for every
                # rlvigen cell, which is why this branch alone failed while the other six families
                # passed the same wave. Read the protocol directly, the same authority rule the
                # frame-stack check now follows -- `_run_grid` has the baseline and needs no
                # value threaded from a caller to know the geometry.
                returns, succ, flags = run_scene(agent, a.task, scene, regime, a.episodes,
                                          a.episode_seed, a.action_repeat, a.frame_stack, frame,
                                          image_size=OBSERVATION_GEOMETRY[a.baseline][0])
                witnesses = list(_eval_across_scenes.LAST_PLACEMENT_WITNESSES)
                diagnostics = list(_eval_across_scenes.LAST_EPISODE_DIAGNOSTICS)
            if a.family != "rlvigen":
                witnesses = list(LAST_PLACEMENT_WITNESSES)
                diagnostics = list(LAST_EPISODE_DIAGNOSTICS)
                policy_action_diagnostics = LAST_POLICY_ACTION_DIAGNOSTICS
            else:
                policy_action_diagnostics = _eval_across_scenes.LAST_POLICY_ACTION_DIAGNOSTICS
            if policy_action_diagnostics is None:
                policy_action_diagnostics = {
                    "available": False,
                    "reason": "adapter_did_not_expose_pre_env_action",
                    "scope": "policy_output_before_env_action_boundary",
                    "execution_boundary": "declared_action_space_before_controller",
                    "controller_clipping_observed": False,
                    "actions_observed": 0,
                }
            if len(witnesses) != len(returns):
                raise RuntimeError(f"{a.family}: placement witness count {len(witnesses)} does not "
                                   f"match measured episode count {len(returns)}")
            if len(diagnostics) != len(returns):
                raise RuntimeError(f"{a.family}: episode diagnostics count {len(diagnostics)} does not "
                                   f"match measured episode count {len(returns)}")
            # [Corrected 2026-09-05, external review 7] The determinism stamp must name the backend
            # that actually computed the measurement.  requirements-native.txt installs torch for
            # every family, so `import torch` succeeds even on the JAX-only ctrl path and the old
            # single boolean recorded `deterministic_algorithms: true` for a measurement in which
            # torch.use_deterministic_algorithms governs nothing at all.
            backend = "jax" if a.family == "ctrl" else "torch"
            stamp = {"determinism_backend": backend,
                     "torch_deterministic_algorithms": DETERMINISTIC_ALGORITHMS,
                     # Kept present for every family so the field is never absent, but it now means
                     # "the backend that computed THIS row was put in a reproducible mode".  ctrl's
                     # reproducibility is its explicitly seeded PRNGKey, not a torch global.
                     "deterministic_algorithms": (True if backend == "jax"
                                                  else DETERMINISTIC_ALGORITHMS)}
            diagnostics = [{**item, **stamp} for item in diagnostics]
            # Pickle globals and ALDA's factory are dynamic dependencies.  Retain the local module
            # files the fresh evaluator process actually imported beside each row; the validation
            # ledger cannot certify this term until a human has reviewed the manifest from a real
            # container job.  Do not fail a costly row merely because a newly observed import needs
            # to be added to the static closure -- record it so the next submission is informed.
            import_manifest = runtime_import_manifest(ROOT, a.family)
            per_scene[scene] = np.asarray(returns, dtype=float)
            successes += succ
            emit(record(**context, **measurement_fields, evaluator_revision=EVALUATOR_REVISION,
                               evaluator_code_revision=EVALUATOR_CODE_REVISION,
                               evaluator_config_revision=EVALUATOR_CONFIG_REVISION,
                               phase="offline-eval", frame=frame, regime=regime,
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
                                       "episode_success": [int(x) for x in flags],
                                       "runtime_import_manifest": import_manifest,
                                       "placement_condition_seeds": [
                                           placement_condition_seed(a.episode_seed, scene, i)
                                           for i in range(len(returns))],
                                       "placement_witnesses": witnesses,
                                       "policy_action_diagnostics": policy_action_diagnostics,
                                       # [Added 2026-09-05, external review 7 §4] The spec promises
                                       # an episode identifier and the record carried only position.
                                       # Index-aligned like every array beside it, so a row can be
                                       # named rather than merely located -- which is what a later
                                       # join, a re-evaluation, or a query about one anomalous
                                       # episode actually needs. Composite rather than a counter so
                                       # it stays stable under re-runs and unique across the fleet.
                                       "eval_episode_ids": [
                                           f"{context['baseline']}-s{context['seed']}-f{frame}"
                                           f"-{regime}-sc{scene}-e{i}"
                                           for i in range(len(returns))],
                                       "episode_diagnostics": diagnostics}))
        # The aggregate a table shows, kept beside the per-scene rows rather than instead of them:
        # a mean over ten scenes hides which scene collapsed, and that is usually the finding.
        pooled = np.concatenate([per_scene[s] for s in scenes]) if per_scene else np.array([])
        if pooled.size:
            emit(record(**context, **measurement_fields, evaluator_revision=EVALUATOR_REVISION,
                               evaluator_code_revision=EVALUATOR_CODE_REVISION,
                               evaluator_config_revision=EVALUATOR_CONFIG_REVISION,
                               phase="offline-eval", frame=frame, regime=regime,
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
    # C95: a production checkpoint must be evaluated in the CUDA/EGL container. CPU remains an
    # explicit diagnostic override, not the accidental default of the production entry point.
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--action-repeat", type=int, default=1)
    ap.add_argument("--frame-stack", type=int, default=None,
                    help="explicit observation stack; omitted uses baseline geometry (C2=3 for "
                         "ppg/idaac, while 1 remains an explicit legacy override)")
    ap.add_argument("--out", default=None, help="JSONL destination; stdout when absent")
    ap.add_argument("--append", action="store_true",
                    help="append JSONL records instead of replacing --out")
    # [Added 2026-09-05, Codex Q7.] Endpoint and curve rows have the same `phase`, the same schema
    # and different DEPTH -- the endpoint is 4 regimes x 10 scenes x 20 episodes, an intermediate
    # stamp is deliberately shallower. Pooling them would silently mix a headline number with a
    # descriptive one, and nothing in the record distinguished them.
    # [Claude 2026-09-07, DECISION-SHEET A25 addendum] The evaluation policy mode is the fleet's
    # ONLY UNITS-class comparability split (audit_comparability_seam.py): eight baselines report
    # E[return | a = argmax pi] and four report E[return | a ~ pi], because this evaluator
    # deliberately reproduces each family's own action rule. Those are different estimands, and two
    # of A25's three fixed cross-group pairs straddle the split.
    #
    # `native` is the default and changes nothing: each family acts exactly as its own reporting
    # path does, which is the fidelity property EVALUATOR-DELTA.md exists to protect. `mode` takes
    # the deterministic action everywhere, producing a second pass that IS comparable across all
    # twelve. The intended use is both -- native for the headline, mode for cross-group contrasts.
    ap.add_argument("--policy-mode", default="native", choices=("native", "mode"),
                    help="native: each family's own action rule. mode: deterministic everywhere, "
                         "for comparisons that cross the sampling/deterministic split")
    ap.add_argument("--eval-scope", default="endpoint", choices=("endpoint", "curve"),
                    help="what this grid is FOR: the reported endpoint, or a trajectory stamp")
    a = ap.parse_args()

    global EVALUATOR_REVISION, EVALUATOR_CODE_REVISION, EVALUATOR_CONFIG_REVISION
    global EVALUATOR_SCOPE, EVALUATOR_SCOPE_REVISION, EVALUATOR_MEASUREMENT_REVISION
    global DETERMINISTIC_ALGORITHMS
    # Resolve every measurement-affecting value before family setup, checkpoint loading, or
    # evaluator construction.  The runner has already translated its environment overrides into
    # these explicit arguments; the scope identity never hashes raw environment text.
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
    want_deterministic = os.environ.get("RLGEN_DETERMINISTIC_EVAL", "1") != "0"
    requested_deterministic_setting = effective_deterministic_setting(
        a.family, True if a.family == "ctrl" else want_deterministic)
    # [Historical bug, fixed 2026-09-07] `--image-size`/`--frame-stack` defaulted to 100/3
    # (dmc_gb's own geometry) and `run_probe.sh` NEVER passes either flag for a real production
    # cell -- confirmed by grep, no cfg or script sets them. So every family but rad/soda got its
    # OWN evaluator_scope stamped with dmc_gb's geometry regardless of what it actually runs at:
    # verified directly against retained records, idaac and ppg both carry
    # `evaluator_scope={"frame_stack": 3, "image_size": 100, ...}` while older C1 checkpoints
    # actually ran 64x64, one frame. Current main geometry is `(64, 3)` for both PPG and IDAAC. The
    # measurements themselves are unaffected -- each family's real construction path is driven by
    # its own launcher's `RLVIGEN_IMAGE_SIZE` / hardcoded wrapper, never by these two CLI flags,
    # `dmc_gb` excepted (`run_scene_dmc_gb` does take `a.image_size` as a real parameter) -- but
    # the RECORDED metadata was false for eleven of twelve baselines' frame_stack or image_size or
    # both. `OBSERVATION_GEOMETRY` is this project's own declared single source of truth for
    # exactly this ("the field that must be consulted per baseline", `rlgen/protocol.py`'s own
    # docstring) -- use it here instead of the CLI passthrough. `a.image_size`/`a.frame_stack`
    # keep their existing real-construction roles for dmc_gb/rlvigen/alda unchanged; only what
    # gets RECORDED changes. Still validated here, before family setup, same as every other
    # scope field: they remain real construction inputs for those three families, so garbage
    # CLI input for them should fail fast regardless of whether THIS baseline happens to read it.
    declared_image_size, declared_frame_stack = OBSERVATION_GEOMETRY[a.baseline]
    if a.frame_stack is None:
        a.frame_stack = declared_frame_stack
    if a.frame_stack <= 0 or a.image_size <= 0:
        raise ValueError(
            "evaluator scope --frame-stack/--image-size must be positive "
            f"(got frame_stack={a.frame_stack}, image_size={a.image_size})")
    # [Claude 2026-09-07] The PROTOCOL is the authority, not the caller. This line used to read
    # `declared_frame_stack = a.frame_stack`, which made `OBSERVATION_GEOMETRY` a mere fallback:
    # a `--frame-stack` that disagreed with the protocol was adopted, recorded as "declared", and
    # hashed into the scope revision. A fail-closed geometry check that its own caller can redefine
    # is not fail-closed -- it confirms whatever it was told. Flagged as a minor hardening gap in
    # the review tail on the grounds that production is stack 3 anyway; that is true and is not the
    # point, since the check exists precisely for the case where the caller is wrong.
    #
    # A mismatch is now refused rather than absorbed. Passing the protocol's own value stays legal,
    # so every existing command line keeps working.
    if a.frame_stack != declared_frame_stack:
        raise ValueError(
            f"--frame-stack {a.frame_stack} contradicts the protocol declaration for "
            f"{a.baseline} ({declared_frame_stack}). rlgen/protocol.py's OBSERVATION_GEOMETRY is "
            "the authority for this baseline's observation shape; the evaluator will not record a "
            "geometry it was merely told.")
    resolved_scope = canonical_evaluation_scope({
        "family": a.family, "baseline": a.baseline, "task": a.task, "frame": frame,
        "eval_scope": a.eval_scope, "regimes": a.regimes, "scenes": a.scenes,
        "episodes": a.episodes, "episode_seed": a.episode_seed, "seed": a.seed,
        "device": a.device, "action_repeat": a.action_repeat, "frame_stack": declared_frame_stack,
        "image_size": declared_image_size, "episode_length": a.episode_length,
        "deterministic_setting": requested_deterministic_setting,
        # [Claude 2026-09-07] MUST reflect what ran, not what the family natively does. Stamping the
        # native rule while `--policy-mode mode` was in force would make the record assert the one
        # thing it exists to certify -- which action rule produced these returns.
        "eval_policy_mode": ("mode" if a.policy_mode == "mode"
                             else family_eval_policy_mode(a.family)),
    })
    EVALUATOR_SCOPE = resolved_scope
    EVALUATOR_SCOPE_REVISION = scope_revision(resolved_scope)

    # Apply the resolved backend setting only after scope validation and before family setup.
    # CTRL's JAX path does not use torch's global switch even if torch happens to be installed.
    if a.family == "ctrl":
        DETERMINISTIC_ALGORITHMS = False
    else:
        try:
            import torch
            if want_deterministic:
                torch.use_deterministic_algorithms(True)
                DETERMINISTIC_ALGORITHMS = True
            else:
                DETERMINISTIC_ALGORITHMS = False
                print("=== NATIVE_EVAL_DETERMINISM_DISABLED by RLGEN_DETERMINISTIC_EVAL=0 ===",
                      file=sys.stderr)
        except (ImportError, RuntimeError) as error:
            raise RuntimeError("requested evaluator determinism could not be resolved before "
                               "setup/import") from error

    # The selected path determines which restored model classes, wrappers and factory code can
    # execute.  Compute the family closure only after argparse; a process-wide common hash cannot
    # distinguish a change to CTRL's vec_env from an IBAC checkpoint-writing change.
    EVALUATOR_REVISION = evaluator_family_revision(ROOT, a.family)
    EVALUATOR_CODE_REVISION = evaluator_family_code_revision(ROOT, a.family)
    EVALUATOR_CONFIG_REVISION = evaluator_family_config_revision(ROOT, a.family)
    EVALUATOR_MEASUREMENT_REVISION = measurement_revision(
        EVALUATOR_REVISION, EVALUATOR_SCOPE_REVISION)

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
    # Determinism was resolved and applied before family setup above; this value is now part of
    # the scope attestation and the per-row diagnostics stamp.
    # A path such as `snapshot.pt` identifies a role, not bytes. The digest travels on every row so
    # endpoint and intermediate records cannot be confused after staging, copying, or resuming.
    checkpoint_sha256 = hashlib.sha256(snap.read_bytes()).hexdigest()

    if a.family == "ctrl":
        # flax `from_bytes` fills a TARGET; it does not construct one. The TrainState must be
        # rebuilt with ctrl's own flags first, which is why this cannot go through the generic
        # torch.load path below.
        agent = _ctrl_train_state(snap)
        record = _record_factory()
        regimes = [item.strip() for item in a.regimes.split(",") if item.strip()]
        scenes = [int(item) for item in a.scenes.split(",") if item.strip()]
        context = {"cell": f"{a.baseline}-s{a.seed}", "baseline": a.baseline,
                   "family": a.family, "seed": a.seed, "eval_scope": a.eval_scope,
                   "checkpoint_sha256": checkpoint_sha256}
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
                   "family": a.family, "seed": a.seed, "eval_scope": a.eval_scope,
                   "checkpoint_sha256": checkpoint_sha256}
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
        atexit.register(shutil.rmtree, staged, ignore_errors=True)
        shutil.copy2(snap, staged / "model.pt")
        agent = (staged, a.device)
        record = _record_factory()
        regimes = [item.strip() for item in a.regimes.split(",") if item.strip()]
        scenes = [int(item) for item in a.scenes.split(",") if item.strip()]
        context = {"cell": f"{a.baseline}-s{a.seed}", "baseline": a.baseline,
                   "family": a.family, "seed": a.seed, "eval_scope": a.eval_scope,
                   "checkpoint_sha256": checkpoint_sha256}
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
    agent = place_agent_on_device(agent, device)

    record = _record_factory()
    regimes = [item.strip() for item in a.regimes.split(",") if item.strip()]
    scenes = [int(item) for item in a.scenes.split(",") if item.strip()]
    context = {"cell": f"{a.baseline}-s{a.seed}", "baseline": a.baseline,
               "family": a.family, "seed": a.seed, "eval_scope": a.eval_scope,
               "checkpoint_sha256": checkpoint_sha256}
    return _run_grid(a, agent, record, regimes, scenes, context, frame)


if __name__ == "__main__":
    raise SystemExit(main())
