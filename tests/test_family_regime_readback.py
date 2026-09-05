"""Each family's adapter must expose the regime it was CONSTRUCTED with, on a real env.

Job `bt1p4ei1s64o50oka946` died at `runnable/idaac/ppo_daac_idaac/envs.py`:

    RuntimeError: RL-ViGen adapter lost P3's applied regime read-back during construction

The guard read `_vigen_regime` off `venv.envs[0]`, but P3 sets that attribute inside RL-ViGen's
`robo_make`, and this adapter calls `robosuitevgb.utils.make_env` directly -- which P3 does not
patch. So the attribute was never set on anything in the stack and the guard raised on EVERY
construction: idaac could not be evaluated at all.

The change that introduced it landed with a green suite, because **no test constructed an
environment**. That is the gap this file closes. It is deliberately an integration test: the defect
is invisible to any check that does not build the real wrapper stack.

`ibac_sni` already did it correctly -- read `_mode`/`_scene_id` off the base env and hoist -- and
that is now the shape idaac uses too.
"""
import os
import pathlib
import re
import sys
import types

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


@pytest.fixture
def prepared_paths():
    """Put the family stacks on sys.path, and TAKE THEM OFF AGAIN.

    `runnable/_shim/no_tf` has to be here because `ext/baselines` imports tensorflow, but leaving
    it on sys.path -- and worse, leaving the stub in `sys.modules['tensorflow']` -- makes every
    LATER test in the session import the stub. The first version of this file did exactly that and
    turned four passing tests in test_plot_curves.py and test_plot_and_success.py red, while
    passing in isolation. Test pollution is the same shape as everything else found tonight: a
    thing that looks fine alone and is wrong in the arrangement that actually runs.
    """
    rlv = ROOT / "RL-ViGen-upstream"
    if not rlv.is_dir():
        pytest.skip("RL-ViGen-upstream is not in this tree")
    os.environ.setdefault("RLVIGEN_ROOT", str(rlv))
    if sys.platform == "darwin":
        os.environ.setdefault("MUJOCO_GL", "glfw")
        os.environ.setdefault("PYGLFW_LIBRARY", "/opt/homebrew/lib/libglfw.dylib")
    added = []
    for path in (rlv, rlv / "envs" / "robosuiteVGB", ROOT / "runnable" / "idaac",
                 ROOT / "ext" / "baselines", ROOT / "runnable" / "_shim" / "no_tf"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
            added.append(str(path))
    before = set(sys.modules)
    try:
        yield
    finally:
        for path in added:
            if path in sys.path:
                sys.path.remove(path)
        for name in list(set(sys.modules) - before):
            if name == "tensorflow" or name.startswith(("tensorflow.", "baselines",
                                                        "ppo_daac_idaac")):
                sys.modules.pop(name, None)


def test_idaac_adapter_exposes_the_applied_regime(prepared_paths):
    try:
        import torch
        from ppo_daac_idaac.envs import make_rlvigen_venv
    except Exception as error:                                     # pragma: no cover
        _absence_or_fail(error, f"idaac stack not importable here: {type(error).__name__}: {error}")
    args = types.SimpleNamespace(env_name="robosuite:Door", seed=1, condition_seed=1)
    try:
        venv = make_rlvigen_venv(args, torch.device("cpu"), "train", 1, scene_id=0)
    except RuntimeError as error:
        _absence_or_fail(error, f"idaac env could not be built here: {error}")
    except Exception as error:                                     # pragma: no cover
        _absence_or_fail(error, f"idaac env could not be built here: {type(error).__name__}: {error}")
    regime = getattr(venv, "_vigen_regime", None)
    assert isinstance(regime, dict), "the constructed venv exposes no _vigen_regime"
    assert regime.get("mode") == "train", f"asked for train, got {regime.get('mode')!r}"
    assert regime.get("scene_id") == 0, f"asked for scene 0, got {regime.get('scene_id')!r}"


def test_idaac_construction_does_not_skip_a_generic_runtime_defect():
    """Only an absent prerequisite may skip this real-environment integration test.

    The old special case skipped every RuntimeError except the one whose message contained
    ``regime``.  That made a constructor bug, CUDA mismatch, or wrapper TypeError look like a
    machine limitation.  Keep this assertion tied to the call site so the loophole cannot return
    when the next adapter edit moves the exception handling around.
    """
    source = pathlib.Path(__file__).read_text()
    block = re.search(r"    except RuntimeError as error:.*?(?=\n    except Exception as error:)",
                      source, flags=re.DOTALL)
    assert block, "the IDAAC construction RuntimeError handler disappeared; inspect it manually"
    body = block.group(0)
    assert "_absence_or_fail(error" in body, (
        "generic IDAAC construction RuntimeErrors must fail through the narrow absence classifier"
    )
    assert "pytest.skip" not in body, (
        "a generic IDAAC construction RuntimeError must not be converted into a skip"
    )


def test_no_adapter_reads_vigen_regime_off_an_object_p3_never_touches():
    """The static half: P3 patches `robo_make`, so an adapter calling `make_env` cannot rely on it."""
    idaac = (ROOT / "runnable" / "idaac" / "ppo_daac_idaac" / "envs.py")
    if not idaac.is_file():                                        # pragma: no cover
        pytest.skip("idaac clone is not present")
    body = idaac.read_text()
    if "from robosuitevgb.utils import make_env" in body:
        assert 'getattr(bases[0], "_mode"' in body or '"_mode"' in body, (
            "this adapter builds envs with robosuitevgb.utils.make_env, which P3 does NOT patch, "
            "so it must derive the regime from `_mode`/`_scene_id` rather than expect _vigen_regime"
        )
