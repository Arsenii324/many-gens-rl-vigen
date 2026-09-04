"""THE SEAM. RL-ViGen lives below this file; every baseline lives above it.

The contract, asserted at construction rather than documented and hoped for:

    reset()      -> obs (3*frame_stack, H, W) uint8
    step(a)      -> obs, reward_raw, terminated, truncated, info
    a            : (act_dim,) float32 in [-1, 1]; the env clips
    info["scene_id"], info["mode"]  always present
    info["episode"] = {"r": raw_return, "l": length}  present iff the episode ended

Five things this file exists to get right. The first four are each a defect that was observed,
not a hypothetical; the fifth (below, after the synthetic-backend paragraph) is proactive
instrumentation, not a fix for anything already caught going wrong.

1. MODE MUST BE VERIFIED, NOT REQUESTED. Upstream `make_env` read the visual regime from a hydra
   config and ignored its caller, so every env was a *train* env whatever was asked for, and
   "generalisation" numbers were measured on the training distribution. setup/apply_patches.py P1
   makes it an argument; this file then ASSERTS the env was built in the mode requested. A silent
   fallback here produces a plausible number, not a crash, which is the worst kind.

2. TRUNCATION IS DERIVED FROM THE HORIZON. Door and Lift have a fixed horizon and no early
   termination, so every episode end is a time limit. The env's own `discount` field cannot be
   used to detect it -- ExtendedTimeStepWrapper turns the terminal 0.0 back into 1.0 -- so the
   flag is computed from the step count instead. A bootstrap that treats a time limit as a
   terminal state silently biases every value estimate downward.

3. RAW REWARD IS NEVER TOUCHED. Whatever normalisation a baseline wants happens above this line.
   The number reported as an episode return is the raw undiscounted sum, always. The group's
   reference Procgen repo wraps its eval env in VecNormalize and reports the normalised return
   under a name that reads like a raw one; its curves are therefore not comparable with any
   published table.

4. ONE PROCESS PER ENVIRONMENT. `robosuitevgb.make_env` calls `GlobalHydra.clear()` on every
   construction, so two envs cannot be built concurrently in one interpreter, and the GL backend
   must be selected before mujoco is imported. Threads satisfy neither. Anything that needs more
   than one env at a time goes through a subprocess.

A `synthetic` backend implements the identical contract without mujoco. It exists so the test
suite and the mutation catalogue run anywhere, and so that fixtures are DERIVED from a factory
rather than hand-declared -- the previous test harness declared `(3, 84, 84)` by hand while the
pipeline produced `(9, 84, 84)`, and therefore tested a shape that never occurs.

5. THIS FILE IS THE ONE ENVIRONMENT-CONSTRUCTION CHOKE POINT, INSTRUMENTED TO STAY ONE. Every
   baseline's environment interaction -- training and eval alike -- must go through this file,
   never a per-baseline near-original construction path, because that is what makes different
   baselines' reported frame-axes and metrics comparable even when their training internals are
   completely independent (they are allowed to be). `step()` therefore counts every real call
   (`step_calls`) and records action-clipping behaviour (`action_clip_events`,
   `max_abs_action_seen`) so a baseline's own reported frame count and action scale can be
   cross-checked against this file's own ground truth, rather than trusted on say-so.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from .protocol import (DEFAULT_ACTION_REPEAT, DEFAULT_FRAME_STACK,
                       DEFAULT_HORIZON, DEFAULT_IMAGE_SIZE)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPSTREAM = os.path.join(ROOT, "RL-ViGen-upstream")

#: macOS: dm_control's validator rejects "cgl", so the on-screen-capable backend is the only
#: option; Linux GPU boxes want "egl". Set before mujoco is imported, never after.
DEFAULT_MUJOCO_GL = "glfw" if sys.platform == "darwin" else "egl"

#: FOUND 2026-08-15. The Python `glfw` bindings package (a `dm_control`/`mujoco` transitive
#: dependency, imported by `RL-ViGen-upstream/wrappers/dmc.py`, which `robo_wrapper.py` itself
#: imports even though robosuite renders via a different path) locates its native shared library
#: via `ctypes.util.find_library` plus a handful of hardcoded search directories
#: (`glfw/library.py::_get_library_search_paths`) -- none of which include Homebrew's Apple
#: Silicon prefix (`/opt/homebrew/lib`; the package's defaults assume `/usr/local`, the Intel
#: prefix). Result: `import glfw` raised `ImportError: Failed to load GLFW3 shared library` on
#: this machine even with `brew install glfw` already done and the `.dylib` genuinely present at
#: `/opt/homebrew/lib/libglfw.dylib` -- confirmed by hand (`find /opt/homebrew -iname
#: 'libglfw*'`). This is the actual cause behind
#: `tests/test_sweep_gaps.py::test_preflight_does_not_fire_for_a_baseline_with_no_data_needs`
#: failing identically across every run this whole session -- not a narrow test gap, a total
#: block on constructing the real robosuite backend at all, on this machine, for any baseline.
#: The `glfw` package itself provides the escape hatch (`library.py`: `if 'PYGLFW_LIBRARY' in
#: os.environ: glfw = ctypes.CDLL(os.environ['PYGLFW_LIBRARY'])`, checked first, before any
#: search). Set it here, once, before anything imports `glfw` transitively -- but only to a path
#: that actually exists, and only if the caller hasn't already set it explicitly, so this stays
#: inert on Linux/Intel-Mac/any machine where the default lookup already works.
if sys.platform == "darwin" and "PYGLFW_LIBRARY" not in os.environ:
    for _candidate in ("/opt/homebrew/lib/libglfw.dylib",   # Apple Silicon Homebrew
                       "/usr/local/lib/libglfw.dylib"):      # Intel Homebrew
        if os.path.exists(_candidate):
            os.environ["PYGLFW_LIBRARY"] = _candidate
            break


@dataclass(frozen=True)
class EnvSpec:
    """Everything needed to build one environment. Derived from a Protocol, never hand-written."""
    task: str
    mode: str
    scene_id: int
    seed: int
    image_size: int = DEFAULT_IMAGE_SIZE
    frame_stack: int = DEFAULT_FRAME_STACK
    action_repeat: int = DEFAULT_ACTION_REPEAT
    horizon: int = DEFAULT_HORIZON
    backend: str = "robosuite"

    @property
    def obs_shape(self) -> tuple:
        return (3 * self.frame_stack, self.image_size, self.image_size)

    @property
    def steps_per_episode(self) -> int:
        return self.horizon // self.action_repeat


def spec_from_protocol(p, *, mode: str, scene_id: int, seed: int, backend: str = "robosuite") -> EnvSpec:
    return EnvSpec(task=p.task, mode=mode, scene_id=scene_id, seed=seed,
                   image_size=p.image_size, frame_stack=p.frame_stack,
                   action_repeat=p.action_repeat, horizon=p.horizon, backend=backend)


class ContractError(AssertionError):
    """The env did not satisfy the seam contract. Never downgraded to a warning."""


def _assert_contract(spec: EnvSpec, obs: np.ndarray, act_dim: int) -> None:
    if obs.dtype != np.uint8:
        raise ContractError(f"obs dtype {obs.dtype}, expected uint8. Normalisation belongs in "
                            f"the baseline, not here.")
    if tuple(obs.shape) != spec.obs_shape:
        raise ContractError(f"obs shape {tuple(obs.shape)}, expected {spec.obs_shape} "
                            f"(3 channels x frame_stack {spec.frame_stack})")
    if act_dim < 1:
        raise ContractError(f"act_dim {act_dim}")


def _assert_action_contract(action: np.ndarray, act_dim: int) -> None:
    """The counterpart of `_assert_contract` for the other half of the seam: what a baseline
    hands IN, not what it reads out. A wrong-shape action that numpy would otherwise silently
    broadcast or truncate is exactly the kind of defect this file exists to turn into a raised
    error rather than a plausible-looking number -- see this module's docstring, point 1."""
    if action.shape != (act_dim,):
        raise ContractError(f"action shape {action.shape}, expected ({act_dim},)")


class Env:
    """Uniform interface. Baselines see only this."""

    spec: EnvSpec
    obs_shape: tuple
    act_dim: int

    #: Choke-point instrumentation (module docstring, point 5). `step_calls` is a lifetime count
    #: of real `step()` calls -- NOT reset by `reset()`, unlike `_t` -- so it is independent ground
    #: truth for how many times this environment instance actually stepped, regardless of what any
    #: baseline's own pipeline believes its frame count is. `action_clip_events` counts how many of
    #: those calls arrived with an action outside [-1, 1] in any dimension (clipped silently, as
    #: this file has always done); `max_abs_action_seen` is the largest such pre-clip magnitude.
    #: Neither one changes step()'s existing behaviour -- clipping already happened before this was
    #: added -- they only make behaviour that was already occurring observable to a test.
    step_calls: int
    action_clip_events: int
    max_abs_action_seen: float

    def reset(self) -> np.ndarray: raise NotImplementedError
    def step(self, action: np.ndarray): raise NotImplementedError
    def close(self) -> None: pass


class RoboEnv(Env):
    """RL-ViGen robosuite, one env per process."""

    def __init__(self, spec: EnvSpec):
        os.environ.setdefault("MUJOCO_GL", DEFAULT_MUJOCO_GL)
        # RL-ViGen's wrappers use absolute imports rooted at the repo directory.
        for p in (UPSTREAM, os.path.join(UPSTREAM, "envs", "robosuiteVGB")):
            if p not in sys.path:
                sys.path.insert(0, p)
        from wrappers.robo_wrapper import robo_make  # noqa: E402

        self.spec = spec
        self._env = robo_make(name=spec.task, frame_stack=spec.frame_stack,
                              action_repeat=spec.action_repeat, seed=spec.seed,
                              scene_id=spec.scene_id, mode=spec.mode)

        # (1) VERIFY the regime rather than trusting that the request propagated.
        regime = getattr(self._env, "_vigen_regime", None)
        if regime is None:
            raise ContractError(
                "the env did not report a regime. setup/apply_patches.py P3 is not applied, so "
                "there is no way to tell which visual mode was actually built. Refusing to "
                "measure anything under an unverified regime.")
        if regime.get("mode") != spec.mode:
            raise ContractError(
                f"asked for mode {spec.mode!r}, env was built as {regime.get('mode')!r}. "
                f"This is the defect that made every 'generalisation' number in the upstream "
                f"pipeline a training-distribution number.")
        if regime.get("scene_id") != spec.scene_id:
            raise ContractError(
                f"asked for scene {spec.scene_id}, env reports {regime.get('scene_id')}")
        self.regime = regime

        self.act_dim = int(self._env.action_spec().shape[0])
        self.obs_shape = spec.obs_shape
        self._t = 0
        self._ret = 0.0
        self._checked = False
        self.step_calls = 0
        self.action_clip_events = 0
        self.max_abs_action_seen = 0.0

        # WARM-UP RESET, discarded. robosuite's first reset after construction does not draw from
        # the same distribution as later ones: measured, the first episode is not reproducible from
        # a given numpy seed while every later one is, and with a zero policy on Door it scored
        # ~45% higher (0.0251 vs 0.0172 at horizon 6; 0.0846 vs 0.0583 at horizon 20).
        #
        # `evaluate()` builds a fresh env per scene, so without this, episode 0 of EVERY scene came
        # from a different distribution than episodes 1..n -- a systematic effect on one tenth of
        # the data at the default `episodes_per_scene=10`, invisible in any curve.
        #
        # Pinned by `test_real_env.py::test_same_seed_reproduces_from_the_very_first_episode`.
        self._env.reset()

    def reset(self) -> np.ndarray:
        ts = self._env.reset()
        obs = np.asarray(ts.observation)
        if not self._checked:
            _assert_contract(self.spec, obs, self.act_dim)
            self._checked = True
        self._t, self._ret = 0, 0.0
        return obs

    def step(self, action: np.ndarray):
        raw = np.asarray(action, dtype=np.float32)
        _assert_action_contract(raw, self.act_dim)
        self.step_calls += 1
        mag = float(np.abs(raw).max()) if raw.size else 0.0
        self.max_abs_action_seen = max(self.max_abs_action_seen, mag)
        if mag > 1.0:
            self.action_clip_events += 1
        a = np.clip(raw, -1.0, 1.0)
        ts = self._env.step(a)
        obs = np.asarray(ts.observation)
        # (3) raw reward, untouched.
        r = float(ts.reward if ts.reward is not None else 0.0)
        self._t += 1
        self._ret += r
        # (2) truncation from the known horizon, not from the env's discount.
        truncated = self._t >= self.spec.steps_per_episode
        terminated = False
        info: dict[str, Any] = {"scene_id": self.spec.scene_id, "mode": self.spec.mode}
        if terminated or truncated:
            info["episode"] = {"r": self._ret, "l": self._t}
        return obs, r, terminated, truncated, info

    def close(self) -> None:
        try:
            self._env.close()
        except Exception:
            pass


class SyntheticEnv(Env):
    """Same contract, no mujoco. Deterministic given (spec, episode index).

    NOT a mock of robosuite's dynamics -- it makes no claim about them. It exists so that the
    contract, the evaluator, the logging schema and the mutation catalogue can be exercised
    without a simulator, and so that a test's obs shape comes from a factory rather than a
    hand-typed tuple.

    THE REWARD IS DELIBERATELY OBSERVATION-COUPLED. The first version paid `0.05 * a.mean()`,
    which a constant action maximises: a trained DrQ-v2 saturated to `[1,1,1,1,1,1,-1]` for every
    observation and scored identically at two checkpoints 750 updates apart. That is a correct
    result for that reward and a useless one for a test instrument -- an env an observation-blind
    policy can max cannot detect a mutation that severs the observation from the action. So the
    reward now pays for matching a target derived from the observation itself.

    Its sensitivity, stated rather than assumed (docs/RIGOR.md: a null needs a resolvable effect):
    returns respond to the scene id, to the episode seed, to the policy, and to whether the policy
    reads its input. It says nothing about robosuite's dynamics and is not a model of them.
    """

    def __init__(self, spec: EnvSpec, act_dim: int = 7):
        self.spec = spec
        self.act_dim = act_dim
        self.obs_shape = spec.obs_shape
        self.regime = {"mode": spec.mode, "scene_id": spec.scene_id, "video_background": False}
        self._ep = -1
        self._t = 0
        self._ret = 0.0
        self._rng = np.random.default_rng(seed=spec.seed)
        self.step_calls = 0
        self.action_clip_events = 0
        self.max_abs_action_seen = 0.0

    def _obs(self) -> np.ndarray:
        g = np.random.default_rng(seed=(self.spec.seed, self.spec.scene_id, self._ep, self._t))
        return g.integers(0, 256, size=self.obs_shape, dtype=np.uint8)

    def _target(self, obs: np.ndarray) -> np.ndarray:
        """The action this observation asks for, in [-1, 1]^act_dim.

        Derived from coarse block means of the frame, so a policy must actually look at its input
        to score. Cheap and deterministic.
        """
        flat = obs.reshape(-1)[: self.act_dim * 64].astype(np.float64)
        blocks = flat.reshape(self.act_dim, -1).mean(axis=1)
        return np.tanh((blocks - 127.5) / 32.0)

    def reset(self) -> np.ndarray:
        self._ep += 1
        self._t, self._ret = 0, 0.0
        self._last = self._obs()
        _assert_contract(self.spec, self._last, self.act_dim)
        return self._last

    def step(self, action: np.ndarray):
        raw = np.asarray(action, dtype=np.float32)
        _assert_action_contract(raw, self.act_dim)
        self.step_calls += 1
        mag = float(np.abs(raw).max()) if raw.size else 0.0
        self.max_abs_action_seen = max(self.max_abs_action_seen, mag)
        if mag > 1.0:
            self.action_clip_events += 1
        a = np.clip(raw, -1.0, 1.0)
        # Pay for matching the target implied by the observation the action was chosen from.
        # An observation-blind policy scores at chance here; the previous `0.05 * a.mean()`
        # reward was maximised by a constant.
        err = float(np.abs(a - self._target(self._last)).mean())
        self._t += 1
        r = float((1.0 - err) * 0.1 + 0.01 * (1 + self.spec.scene_id) * np.cos(self._t / 7.0))
        self._ret += r
        truncated = self._t >= self.spec.steps_per_episode
        info: dict[str, Any] = {"scene_id": self.spec.scene_id, "mode": self.spec.mode}
        if truncated:
            info["episode"] = {"r": self._ret, "l": self._t}
        self._last = self._obs()
        return self._last, r, False, truncated, info


def make_env(spec: EnvSpec) -> Env:
    if spec.backend == "robosuite":
        return RoboEnv(spec)
    if spec.backend == "synthetic":
        return SyntheticEnv(spec)
    raise ValueError(f"unknown backend {spec.backend!r}; expected 'robosuite' or 'synthetic'")


#: An env factory is the unit the evaluator accepts. It is a *thunk* rather than an env so the
#: evaluator can build one env per scene in a fresh process without the caller knowing.
EnvFactory = Callable[[], Env]


def factory(spec: EnvSpec) -> EnvFactory:
    return lambda: make_env(spec)
