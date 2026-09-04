"""Every baseline's held-out regime is `eval-easy`, reached seven different ways.

The seam that makes twelve numbers comparable has four legs, and this is the last of them:
the y-axis (`test_success_convention.py`), the x-axis (`test_x_axis_invariant.py`), the horizon
(`test_truncation_seam.py`), and the regime evaluated in. If one baseline's held-out regime were
`eval-medium`, its number would sit on a different axis while looking identical — and
[C27](../docs/CONSTRUCTION.md#c27) records that the regimes are not a monotone ladder, so
"slightly harder" is not even a safe reading of such a mistake.

Seven mechanisms, because each baseline reaches the regime through its own stack:

    env var, defaulted   `rlvigen.sh`, `idaac.sh`  -> RLVIGEN_EVAL_MODE, default eval-easy
    CLI flag             `dmc_gb.sh`               -> --eval_mode eval-easy
    argparse default     `ppg_eval.py`             -> --mode, default eval-easy
    literal in the clone `alda`, `ctrl`            -> _build('eval-easy') / _mk("eval-easy", ...)
    training-regime var  `ibac_sni.sh`             -> RLVIGEN_MODE, default train (see below)

**`ibac_sni` is the trap this file most exists for.** It reads `RLVIGEN_MODE`, not
`RLVIGEN_EVAL_MODE`, and it defaults to `train` — correctly, because for `ibac_sni` that variable
selects the *training* regime and evaluation is a separate checkpoint pass. Two variables, one
letter apart in meaning, and setting the wrong one silently does nothing at all. A future edit
that "unified" them would either make `ibac_sni` train on the eval distribution or make the others
evaluate on the training one, and neither would raise anything.
"""
from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGIME = "eval-easy"


def code(rel: str) -> str:
    """Comment lines removed -- prose restating a setting satisfies a search for it."""
    p = ROOT / rel
    if not p.exists():
        pytest.skip(f"{rel} absent")
    return "\n".join(l for l in p.read_text(errors="replace").splitlines()
                     if not l.strip().startswith("#"))


@pytest.mark.parametrize("rel", ["runnable/_launch/rlvigen.sh", "runnable/_launch/idaac.sh"])
def test_env_var_launchers_default_to_the_held_out_regime(rel):
    assert re.search(rf'RLVIGEN_EVAL_MODE="\$\{{RLVIGEN_EVAL_MODE:-{REGIME}\}}"', code(rel)), (
        f"{rel} no longer defaults RLVIGEN_EVAL_MODE to {REGIME}")


def test_dmc_gb_launcher_passes_the_flag():
    assert re.search(rf"--eval_mode\s+{REGIME}\b", code("runnable/_launch/dmc_gb.sh"))


def test_ppg_eval_defaults_to_the_held_out_regime():
    t = code("runnable/_launch/ppg_eval.py")
    assert re.search(rf'"--mode",\s*default="{REGIME}"', t) or \
           re.search(rf"'--mode',\s*default='{REGIME}'", t), \
        "ppg_eval.py's --mode no longer defaults to eval-easy"


def test_alda_builds_the_held_out_env_at_the_right_regime():
    t = code("runnable/alda/trainers/alda_trainer.py")
    assert re.search(rf"color_env\s*=\s*_build\(\s*['\"]{REGIME}['\"]\s*\)", t), (
        "alda's color_env is no longer eval-easy; it is the env its held-out number comes from")


def test_ctrl_builds_its_ood_env_at_the_right_regime():
    t = code("runnable/ctrl/train_ppo.py")
    assert re.search(rf"env_test_OOD\s*=\s*_mk\(\s*['\"]{REGIME}['\"]", t), (
        "ctrl's OOD env is no longer eval-easy")


def test_ibac_sni_uses_the_training_regime_variable_and_not_the_eval_one():
    """The collision guard. These are two variables and unifying them is silent in both directions."""
    t = code("runnable/_launch/ibac_sni.sh")
    assert re.search(r'RLVIGEN_MODE="\$\{RLVIGEN_MODE:-train\}"', t), (
        "ibac_sni.sh no longer sets RLVIGEN_MODE=train. That variable selects its TRAINING regime; "
        "evaluation is a separate checkpoint pass. If it now sets eval-easy, the run trains on the "
        "held-out distribution.")
    assert "RLVIGEN_EVAL_MODE" not in t, (
        "ibac_sni.sh now mentions RLVIGEN_EVAL_MODE. Its stack reads RLVIGEN_MODE; the other "
        "variable is inert here, so setting it looks like configuring the regime and does nothing.")


def test_no_launcher_silently_selects_a_different_regime():
    """A blanket sweep, so a launcher added later is covered without editing this file."""
    # Matches a regime being SELECTED, not merely named. Three things defeated a token search
    # here: a trailing `# train | eval-easy | eval-medium | eval-hard` comment (full-line
    # stripping does not reach it), and an argparse `help=` string enumerating the same options.
    # Both are documentation of the mechanism, which a token matcher cannot tell from the
    # mechanism -- the third time that shape appeared in this session. Asserting on the shape of
    # an assignment rather than on the presence of a word is what actually separates them.
    SELECTS = re.compile(
        r"(--eval_mode\s+|--mode\s+|MODE:-|default\s*=\s*[\"']|mode\s*=\s*[\"']|_mk\(\s*[\"']|_build\(\s*[\"'])"
        r"eval-(medium|hard)")
    wrong = []
    for p in sorted((ROOT / "runnable" / "_launch").glob("*")):
        if p.suffix not in (".sh", ".py"):
            continue
        for n, line in enumerate(code(str(p.relative_to(ROOT))).splitlines(), 1):
            if SELECTS.search(line):
                wrong.append(f"{p.name}:{n}: {line.strip()[:60]}")
    assert not wrong, (
        f"a launcher selects a regime other than {REGIME}: {wrong}. C27 records that the regimes "
        "are not a monotone ladder, so this is a different axis, not a harder point on the same "
        "one. alda's in-clone eval-hard env is deliberate and lives in the clone, not a launcher.")
