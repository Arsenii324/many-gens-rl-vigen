"""Exercise `normalize_eval_sentinel`'s shell logic before it runs on a paid GPU.

[Claude 2026-09-08] `EVAL_EVERY_FRAMES=2147483647` was never a disable. Every one of these
training loops gates on `step % cadence == 0`, and `0 % 2147483647 == 0` is True, so a full
evaluation ran at step 0 under a manifest saying online evaluation was off -- consuming the
process-global NumPy stream Door's placement draws from. Job `bt1utl06n6mqffrt2jdn`'s own log
carries the proof: an eval row at `F: 0` with `R: 7.6385`.

The project fixed the class on 2026-09-07 (external review 21 P0), but only on the branch where
`EVAL_EVERY_FRAMES` is UNSET, and twenty cfgs set it explicitly -- taking the else branch straight
back to the value the fix removes.

This function normalizes it in the runner instead, so it covers the cfgs that already exist and the
production cfgs that do not. It has three branches and, at the time this test was written, exactly
one of them had ever executed on a real job. The branch that matters most -- a family WITH an eval
cadence and a declared spelling -- had not.

Same extraction technique as `test_curve_eval_shell.py`: pull the function out of the runner and
run it against stubbed inputs, so no job is needed.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "datasphere" / "native" / "run_probe.sh"


def _extract(name: str) -> str:
    text = RUNNER.read_text()
    start = text.index(f"{name}() {{")
    depth, i = 0, start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1
    raise AssertionError(f"{name} not found in {RUNNER}")


def _run(env_every: str | None, spelling: str | None) -> tuple[int, str, str]:
    """Run the function with FAMILY_TOOL stubbed to emit whatever spelling we want to test."""
    body = _extract("normalize_eval_sentinel")
    stub = (f'echo "NATIVE_ONLINE_EVAL_DISABLED_SPELLING={spelling}"'
            if spelling is not None else 'true')
    script = f"""
set -uo pipefail
FAMILY_TOOL=/dev/null
python3() {{ {stub}; }}
{body}
{'EVAL_EVERY_FRAMES=' + env_every if env_every is not None else 'EVAL_EVERY_FRAMES='}
normalize_eval_sentinel "svea:1"
status=$?
echo "AFTER_EVAL_EVERY=[${{EVAL_EVERY_FRAMES:-}}]"
echo "AFTER_SPELLING=[${{NATIVE_ONLINE_EVAL_DISABLED_SPELLING:-}}]"
echo "AFTER_DISABLE=[${{NATIVE_DISABLE_ONLINE_EVAL:-}}]"
exit $status
"""
    proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def test_the_sentinel_is_replaced_by_the_families_own_spelling():
    """rlvigen's spelling is `null`, which Hydra parses to None and utils.Every returns False for."""
    code, out, err = _run("2147483647", "null")
    assert code == 0, err
    assert "AFTER_EVAL_EVERY=[]" in out, (
        "EVAL_EVERY_FRAMES must be cleared so the guarded branch downstream is the one taken")
    assert "AFTER_SPELLING=[null]" in out
    assert "NATIVE_EVAL_SENTINEL_NORMALIZED" in err, (
        "the substitution must be announced -- a silent rewrite makes a run that relied on the "
        "sentinel unidentifiable in its own log")


def test_a_real_cadence_is_left_completely_alone():
    """The fix must not touch a run that genuinely wants periodic evaluation."""
    code, out, _ = _run("50000", "null")
    assert code == 0
    assert "AFTER_EVAL_EVERY=[50000]" in out


def test_a_family_with_no_eval_option_passes_through_silently():
    """idaac, ppg, ibac_sni and ctrl have no `{eval_every}` option, so the value never reaches
    their loops. Refusing here would break four families to fix a defect they never had."""
    code, out, err = _run("2147483647", None)
    assert code == 0, err
    assert "AFTER_EVAL_EVERY=[2147483647]" in out
    assert "NATIVE_EVAL_SENTINEL_NORMALIZED" not in err
    assert "REFUSING" not in err


def test_an_unset_cadence_is_untouched():
    code, out, _ = _run(None, "null")
    assert code == 0
    assert "AFTER_EVAL_EVERY=[]" in out


def test_it_also_sets_the_disable_flag_the_guarded_branch_reads():
    """The half the first version missed, found by job bt1kj79a5o9gs61qkl96.

    The branch that resolves the spelling is `NATIVE_DISABLE_ONLINE_EVAL == 1 AND -z
    EVAL_EVERY_FRAMES`, and that flag is exported only by `apply_production_settings`, which
    returns immediately unless NATIVE_PRODUCTION is set. No diagnostic cfg sets it. So clearing
    EVAL_EVERY_FRAMES alone dropped through to `${EVAL_EVERY_FRAMES:-$frames}` -- the whole budget
    as a cadence. That cell reported eval_every_frames=10000 and evaluated at F: 0 AND F: 10000,
    which is strictly worse than the sentinel it replaced.
    """
    code, out, _ = _run("2147483647", "null")
    assert code == 0
    assert "AFTER_DISABLE=[1]" in out, (
        "without this the guarded branch is unreachable on every non-production cfg, and the "
        "cadence silently becomes the whole frame budget")


def test_a_real_cadence_does_not_get_the_disable_flag():
    code, out, _ = _run("50000", "null")
    assert code == 0
    assert "AFTER_DISABLE=[]" in out, "a run that wants periodic evaluation must keep it"
