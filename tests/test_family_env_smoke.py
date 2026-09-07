"""Construct each family's real evaluation env, step it, and collect what a record needs.

Four defects were found on 2026-09-05 by running a remote job, each hidden behind the previous:
the payload contract, two regime read-backs, agent device placement, and CuBLAS determinism. **The
suite was green through all of them**, because no test built a real environment. Three of the four
lived in code no test ever executed.

This file is the cheap half of the fix. It cannot replace a remote CUDA run -- C95 forbids reading
NUMBERS from a local evaluation of a container-trained checkpoint -- but the defects above were not
about numbers. They were about whether the code path executes at all, and that is answerable here in
seconds, for every family, with no checkpoint and no GPU.

Skips rather than fails when a family's stack is not importable, and says which, so an absent
dependency never reads as a pass.
"""
import os
import pathlib
import sys
import types

import numpy as np
import pytest



#: Errors that genuinely mean "this stack is not present on this machine". Anything else is a
#: DEFECT and must fail, not skip. Review 9 asked for this specifically; the file's own docstring
#: already argued it, because three of four defects found overnight were invisible to the suite for
#: exactly this reason -- and then the diagnostic tests kept the swallowing pattern themselves.
ABSENCE = (ImportError, ModuleNotFoundError, FileNotFoundError)
#: A headless machine with no GL context is an absence too, but it arrives as a generic error whose
#: TYPE says nothing. Matched on the message, deliberately narrowly.
ABSENT_RENDERER = ("egl", "opengl", "gl context", "display", "libgl", "mujoco_gl", "glfw")


def _absence_or_fail(error, message):
    """Skip only for a prerequisite that is genuinely missing; fail for everything else.

    A skip line is a claim about the world, exactly like an assertion. `except Exception -> skip`
    claims "this machine cannot run it" while actually reporting "something went wrong", so a
    TypeError from our own wrapper reads as a clean skip forever.
    """
    if isinstance(error, ABSENCE):
        pytest.skip(f"{message} (absent prerequisite: {type(error).__name__}: {error})")
    text = str(error).lower()
    if any(token in text for token in ABSENT_RENDERER):
        pytest.skip(f"{message} (no renderer on this host: {type(error).__name__}: {error})")
    raise AssertionError(
        f"{message} -- but this is NOT an absent prerequisite, it is "
        f"{type(error).__name__}: {error}. That is a defect in the code under test."
    ) from error

ROOT = pathlib.Path(__file__).resolve().parents[1]
EPISODE_STEPS = 60          # enough to exercise the loop; not a measurement


@pytest.fixture
def family_paths():
    """Add every family's import root, then take them all off again.

    The stubs and shims here (`no_tf`, `alda_models`) leak into later tests if left on `sys.path`,
    and leaving a stubbed `tensorflow` in `sys.modules` turned four unrelated tests red once.
    """
    rlv = ROOT / "RL-ViGen-upstream"
    if not rlv.is_dir():
        pytest.skip("RL-ViGen-upstream is not in this tree")
    os.environ.setdefault("RLVIGEN_ROOT", str(rlv))
    if sys.platform == "darwin":
        os.environ.setdefault("MUJOCO_GL", "glfw")
        os.environ.setdefault("PYGLFW_LIBRARY", "/opt/homebrew/lib/libglfw.dylib")
    candidates = [rlv, rlv / "envs" / "robosuiteVGB", ROOT / "ext" / "baselines",
                  ROOT / "runnable" / "_shim" / "no_tf", ROOT / "runnable" / "_shim" / "alda_models",
                  ROOT / "runnable" / "idaac", ROOT / "runnable" / "ppg",
                  ROOT / "runnable" / "ctrl", ROOT / "runnable" / "dmc_gb",
                  ROOT / "runnable" / "dmc_gb" / "src",
                  ROOT / "runnable" / "ibac_sni" / "torch_rl", ROOT / "runnable" / "alda"]
    added = [str(p) for p in candidates if p.exists() and str(p) not in sys.path]
    for path in added:
        sys.path.insert(0, path)
    before = set(sys.modules)
    try:
        yield
    finally:
        for path in added:
            if path in sys.path:
                sys.path.remove(path)
        for name in list(set(sys.modules) - before):
            if name.split(".")[0] in {"tensorflow", "baselines", "ppo_daac_idaac", "dmc2gym",
                                      "phasic_policy_gradient", "vec_env", "models", "trainers",
                                      "dmcontrol_generalization_benchmark", "env", "utils"}:
                sys.modules.pop(name, None)


def _grid():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_grid_smoke", ROOT / "scripts" / "eval_grid.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["_grid_smoke"] = module
    spec.loader.exec_module(module)
    return module


def _build_ctrl():
    from vec_env import RLViGenVecEnvCustom
    return RLViGenVecEnvCustom("robosuite:Door", mode="train", num_envs=1, seed=1,
                               scene_id=0, condition_seed=1, normalize_rewards=False)


def _build_ibac_sni():
    os.environ["RLVIGEN_MODE"] = "train"
    os.environ["RLVIGEN_SCENE_ID"] = "0"
    from utils.general import make_rlvigen_env
    return make_rlvigen_env("robosuite:Door", 1)


def _build_idaac():
    import torch
    from ppo_daac_idaac.envs import make_rlvigen_venv
    args = types.SimpleNamespace(env_name="robosuite:Door", seed=1, condition_seed=1)
    return make_rlvigen_venv(args, torch.device("cpu"), "train", 1, scene_id=0)


def _build_ppg():
    from phasic_policy_gradient.envs import get_venv
    return get_venv(num_envs=1, env_name="robosuite:Door", mode="train", seed=1,
                    scene_id=0, condition_seed=1)


@pytest.mark.parametrize("family", ["idaac", "ppg"])
def test_continuous_main_stack_has_nine_channels_and_legacy_stack_is_explicit(family, family_paths):
    """Both continuous-control C2 paths build 9 channels; C1 remains an explicit 1-frame path."""
    if family == "idaac":
        import torch
        from ppo_daac_idaac.envs import make_rlvigen_venv

        def build(stack):
            args = types.SimpleNamespace(env_name="robosuite:Door", seed=1,
                                         condition_seed=1, frame_stack=stack)
            return make_rlvigen_venv(args, torch.device("cpu"), "train", 1, scene_id=0)
    else:
        from phasic_policy_gradient.envs import get_venv

        def build(stack):
            return get_venv(num_envs=1, env_name="robosuite:Door", mode="train", seed=1,
                            scene_id=0, condition_seed=1, frame_stack=stack)

    env3 = build(3)
    env1 = build(1)
    try:
        if family == "idaac":
            obs3 = env3.reset()
            obs1 = env1.reset()
            shape3 = tuple(obs3.shape)
            shape1 = tuple(obs1.shape)
            assert shape3[1] == 9 and shape1[1] == 3, (shape3, shape1)
        else:
            shape3 = tuple(env3.ob_space.shape)
            shape1 = tuple(env1.ob_space.shape)
            assert shape3[-1] == 9 and shape1[-1] == 3, (shape3, shape1)
    except Exception as error:
        _absence_or_fail(error, f"{family} frame-stack smoke failed: {type(error).__name__}: {error}")
    finally:
        for env in (env3, env1):
            closer = getattr(env, "close", None)
            if callable(closer):
                closer()


BUILDERS = {"ctrl": _build_ctrl, "ibac_sni": _build_ibac_sni,
            "idaac": _build_idaac, "ppg": _build_ppg}


@pytest.mark.parametrize("family", sorted(BUILDERS))
def test_family_env_constructs_and_verifies_its_regime(family, family_paths):
    grid = _grid()
    try:
        env = BUILDERS[family]()
    except Exception as error:
        _absence_or_fail(error, f"{family} stack not importable here: {type(error).__name__}: {error}")
    try:
        grid.verify_regime(env, "train", 0, family, strict=True)
    except RuntimeError as error:
        raise AssertionError(
            f"{family}: strict regime verification fails on a freshly constructed env -- "
            f"every production cell for this family would abort. {error}"
        ) from error


def test_the_evaluator_sets_cublas_config_before_torch_sees_cuda(family_paths):
    """Cheap guard for the defect that made determinism unusable on CUDA."""
    _grid()
    assert os.environ.get("CUBLAS_WORKSPACE_CONFIG") in (":4096:8", ":16:8"), (
        "importing eval_grid must set CUBLAS_WORKSPACE_CONFIG, or "
        "torch.use_deterministic_algorithms(True) raises at the first CuBLAS op on CUDA"
    )


def _step_ppg(venv, steps):
    import numpy as _np
    for _ in range(steps):
        venv.act(_np.zeros((1, 7), dtype="float32"))


def _step_ctrl(env, steps):
    import numpy as _np
    env.reset()
    for _ in range(steps):
        env.step(_np.zeros((1, 7), dtype="float32"))


def _step_idaac(envs, steps):
    import torch as _torch
    envs.reset()
    action = _torch.zeros((1, 7), dtype=_torch.float32)
    for _ in range(steps):
        envs.step(action)


STEPPERS = {"ppg": _step_ppg, "ctrl": _step_ctrl, "idaac": _step_idaac}


@pytest.mark.parametrize("family", sorted(STEPPERS))
def test_a_completed_episode_exposes_full_diagnostics(family, family_paths):
    """P20's per-episode diagnostics must be REACHABLE from the handle the evaluator holds.

    `completed_episode_diagnostics` walks the wrapper chain and, when it finds nothing, records
    `diagnostics_available: false` for every episode -- realized placement, reward statistics,
    clipping rates and termination reason all silently absent, and unrecoverable without re-running.
    External review 7 flagged that as tolerated in production; measuring it is cheaper than arguing
    about it.

    A full episode is stepped because P20 appends at episode END: a partial episode legitimately
    finds an EMPTY list, which the collector correctly treats as an error rather than an absence.
    """
    grid = _grid()
    try:
        env = BUILDERS[family]()
    except Exception as error:
        _absence_or_fail(error, f"{family} stack not importable here: {type(error).__name__}: {error}")
    try:
        STEPPERS[family](env, 505)          # Door's horizon is 500; one full episode plus slack
    except Exception as error:              # pragma: no cover
        _absence_or_fail(error, f"{family} could not be stepped here: {type(error).__name__}: {error}")
    rows = grid.completed_episode_diagnostics(env, 0.0, 1)
    assert rows, f"{family}: no diagnostics rows returned at all"
    row = rows[0]
    assert row.get("diagnostics_available") is True, (
        f"{family}: a completed episode still reports diagnostics_available={row.get('diagnostics_available')!r}. "
        "Every production row for this family would omit realized placement, reward statistics and "
        "clipping diagnostics, and none of it can be recovered without re-running the cell."
    )
    for field in ("episode_length", "termination_reason", "reward_sum", "initial_placement",
                  "applied_mode", "action_clip_rate_vector"):
        assert field in row, f"{family}: diagnostics row is missing {field!r}"


def test_placement_conditions_are_reproducible_and_scene_specific(family_paths):
    """The paired design rests on this, and it had only ever been argued from the seed formula.

    Every cross-regime and cross-baseline comparison in this project assumes episode *i* runs the
    same physical placement wherever it appears. That is derived from
    `SeedSequence(seed, scene, i)` -- but a derivation is not a measurement, and the reset path
    involves the global NumPy stream (C69), a wrapper counter, and robosuite's own sampler.

    Two independent constructions must give byte-identical placement witnesses, and a different
    scene must give different ones. The second half matters as much as the first: witnesses that
    were identical *everywhere* would also pass the first check while proving the scene argument
    reaches nothing.
    """
    import numpy as _np
    grid = _grid()

    def witnesses(seed, scene, episodes):
        try:
            venv = BUILDERS["ppg"]() if (seed, scene) == (1, 0) else None
        except Exception as error:                                 # pragma: no cover
            _absence_or_fail(error, f"ppg stack not importable here: {type(error).__name__}: {error}")
        from phasic_policy_gradient.envs import get_venv
        venv = get_venv(num_envs=1, env_name="robosuite:Door", mode="train", seed=seed,
                        scene_id=scene, condition_seed=seed)
        for _ in range(episodes * 505):
            venv.act(_np.zeros((1, 7), dtype="float32"))
        return list(getattr(venv, "_placement_witnesses", []))[:episodes]

    try:
        first = witnesses(1, 0, 2)
        second = witnesses(1, 0, 2)
        other_scene = witnesses(1, 4, 2)
    except Exception as error:                                     # pragma: no cover
        _absence_or_fail(error, f"could not build the ppg venv here: {type(error).__name__}: {error}")

    assert first and len(first) == 2, f"expected two witnesses, got {first}"
    assert first == second, (
        "the same seed and scene produced DIFFERENT placements across two runs; the paired design "
        f"assumes they are identical.\n  run A: {first}\n  run B: {second}"
    )
    assert first != other_scene, (
        "scene 0 and scene 4 produced the SAME placements, so the scene argument is reaching "
        "nothing and the ten-scene grid would be ten copies of one scene"
    )


def test_ctrl_reset_pattern_decides_the_condition_index(family_paths):
    """Both reset patterns, executed, so the difference is demonstrated rather than asserted.

    This does NOT detect the evaluator bug on its own -- an earlier version of this test claimed to
    and did not, because it drove the env directly and never touched `run_scene_ctrl`. It passed on
    the broken code. Recording that, because it is the same shape as review 10's criticism of the
    gate: a check that exercises the mechanism while the defect lives in the caller.

    What this establishes is the PREMISE: that the reset pattern changes which condition a measured
    episode runs under. `tests/test_ctrl_episode_pairing.py` then checks that the evaluator uses the
    right pattern. Neither alone is sufficient; together they are.
    """
    import numpy as _np

    def counter_after(explicit_reset_each_episode: bool, episodes: int = 2):
        try:
            env = BUILDERS["ctrl"]()
        except Exception as error:                                 # pragma: no cover
            _absence_or_fail(error, f"ctrl stack not importable here: {type(error).__name__}: {error}")
        inner = env.env
        while inner is not None and not hasattr(inner, "_episode_indices"):
            inner = getattr(inner, "venv", None)
        if inner is None:                                          # pragma: no cover
            pytest.skip("no _SyncVecEnv with a condition counter in this stack")
        env.reset()
        for _ in range(episodes):
            if explicit_reset_each_episode:
                env.reset()                       # what the evaluator used to do, on top of auto-reset
            done, steps = False, 0
            while not done and steps < 520:
                _, _, d, _ = env.step(_np.zeros((1, 7), dtype="float32"))
                done = bool(_np.asarray(d).reshape(-1)[0])
                steps += 1
        return list(inner._episode_indices)[0]

    correct = counter_after(False)
    doubled = counter_after(True)
    assert correct == 3, f"one reset plus two auto-resets should reach 3, got {correct}"
    assert doubled > correct, (
        f"resetting explicitly per episode must consume extra conditions: {doubled} vs {correct}. "
        "If these are equal the vector env has stopped auto-resetting and the pairing argument in "
        "tests/test_ctrl_episode_pairing.py needs re-deriving."
    )
