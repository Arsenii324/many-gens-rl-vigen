"""Item 3 of the 2026-09-20 stop-mechanisms fix: A TIMEOUT MUST SAY IT WAS A TIMEOUT.

`eval-cost-and-timeout-trace.md` Part 2, 2a (read before this fix): `timeout --foreground
${CELL_TIMEOUT_SECONDS}s` makes the measured command exit 124, and "No timeout-specific marker
exists anywhere in the file" -- `time -v`'s direct child is `timeout` itself, which exits normally
(not by a signal) once its own deadline passes, so neither `run_measured`'s NATIVE_CELL_STALLED
check nor its "Command terminated by signal" check ever fires, and the cell fell through to a bare
`return 124` -- "no distinction recorded anywhere between 'stopped because it was too slow' and
'stopped because it was broken'."

Two things are tested: `_last_frame_hint` (a pure function) directly with canned log text for each
family format it tries, and the real `run_probe.sh --measure-command` entry point (already used by
`tests/test_datasphere_native_contract.py` and others) end to end, with a stub command that exits
124 -- exactly what `timeout` produces -- to show the marker actually appears in the real output
path, not just in an isolated function.
"""
from __future__ import annotations

import os
import pathlib
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROBE = ROOT / "datasphere" / "native" / "run_probe.sh"


def _extract(name: str) -> str:
    text = PROBE.read_text()
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
    raise AssertionError(f"{name} not found")


def _hint(log_text: str, tail_lines: int = 200) -> tuple[int, str]:
    """Runs the shipped `_last_frame_hint` against canned log text; returns (rc, stdout)."""
    script = f'set -uo pipefail\n{_extract("_last_frame_hint")}\n_last_frame_hint "$1" {tail_lines}\n'
    log = pathlib.Path("/tmp") / "frame_hint_test.log"
    log.write_text(log_text)
    try:
        proc = subprocess.run(["bash", "-c", script, "_", str(log)],
                              capture_output=True, text=True, timeout=10)
        return proc.returncode, proc.stdout
    finally:
        log.unlink(missing_ok=True)


@pytest.mark.skipif(not PROBE.exists(), reason="run_probe.sh missing")
@pytest.mark.parametrize("family_log,expected", [
    # RL-ViGen-upstream / dmc_gb console dump (RL-ViGen-upstream/logger.py COMMON_TRAIN_FORMAT).
    ("| train | F: 6000 | S: 6000 | E: 12 | L: 500 | R: 45.2000 | FPS: 59.0 | T: 0:00:12", "6000"),
    # ibac_sni (runnable/ibac_sni/torch_rl/scripts/train.py): space, not colon.
    ("U 12 | F 006000 | FPS 0059 | D 84 | ent 1.2", "006000"),
    # idaac (runnable/idaac/train.py).
    ("Update 10, step 40960:", "40960"),
    # alda (alda_trainer.py, via its `alda: ` logger prefix).
    ("2026-09-20 [INFO] alda: Evaluating episode 5, step 10000", "10000"),
    # ppg (log_save_helper.py) -- only fires at a save, not every iteration.
    ("Saving to  model.jd IC=40960", "40960"),
    # ctrl (train_ppo.py) -- bracketed frame count at the start of a line.
    ("[500000]\tEprew200: 12.340\tEprew0: 8.120", "500000"),
])
def test_each_known_family_format_is_read(family_log, expected):
    rc, out = _hint(f"some preamble\n{family_log}\nsome trailer\n")
    assert rc == 0, out
    assert out.strip() == expected, f"log={family_log!r} out={out!r}"


@pytest.mark.skipif(not PROBE.exists(), reason="run_probe.sh missing")
def test_the_last_matching_line_in_the_tail_wins():
    rc, out = _hint("| train | F: 100 |\n| train | F: 200 |\n| train | F: 300 |\n")
    assert rc == 0, out
    assert out.strip() == "300", out


@pytest.mark.skipif(not PROBE.exists(), reason="run_probe.sh missing")
def test_an_unrecognised_format_says_so_rather_than_guessing():
    rc, out = _hint("nothing here looks like a frame count at all\njust prose\n")
    assert rc != 0, out
    assert out.strip() == "", out


@pytest.mark.skipif(not PROBE.exists(), reason="run_probe.sh missing")
def test_ansi_colour_codes_around_the_prefix_do_not_hide_the_number():
    """Both loggers colourise the `train`/`eval` prefix word (termcolor); the F:/S: fields are not
    colourised themselves, but a naive read of the raw bytes must not be thrown by the codes
    elsewhere on the line."""
    rc, out = _hint("\x1b[32mtrain\x1b[0m | F: 7777 | S: 7777 | E: 1 |")
    assert rc == 0, out
    assert out.strip() == "7777", out


@pytest.mark.skipif(not PROBE.exists(), reason="run_probe.sh missing")
def test_a_missing_log_file_fails_closed_not_with_a_guess():
    script = f'set -uo pipefail\n{_extract("_last_frame_hint")}\n_last_frame_hint "/no/such/file" 200\n'
    proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=10)
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert proc.stdout.strip() == ""


# --- end to end: the real --measure-command entry point, exactly as `run_one_cell` calls it -----


def _measure(tmp_path: pathlib.Path, command: str, timeout_seconds: str | None) -> str:
    out_dir = tmp_path / "out"
    env = dict(os.environ)
    env["NATIVE_NO_POLICY_HEALTH_WATCH"] = "1"
    if timeout_seconds is not None:
        env["CELL_TIMEOUT_SECONDS"] = timeout_seconds
    else:
        env.pop("CELL_TIMEOUT_SECONDS", None)
    # [Claude 2026-09-20] `run_measured`'s OWN existing stall-watchdog subshell (untouched by this
    # fix -- item 3 only adds the marker AFTER it, and item 2 only extends coverage to evaluation,
    # not training) sleeps up to 30s at a time and is only asked to stop, not waited on with a
    # bound, once training exits (`kill "$stall_pid" 2>/dev/null; wait "$stall_pid" 2>/dev/null`).
    # Observed here: that adds up to ~30s of tail latency to EVERY `--measure-command` invocation,
    # success or failure, pre-existing and unrelated to this fix. 45s gives it room without masking
    # a real hang (which would still exceed this).
    proc = subprocess.run(
        ["bash", str(PROBE), "--measure-command", command, "--output", str(out_dir)],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=45)
    return proc.stdout + proc.stderr


@pytest.mark.skipif(not PROBE.exists(), reason="run_probe.sh missing")
def test_a_124_exit_with_a_ceiling_armed_prints_the_timeout_marker_with_a_frame_hint(tmp_path):
    """The real regression: before this fix, nothing distinguished this from any other failure."""
    command = 'echo "| train | F: 12345 | S: 12345 | E: 3 |"; exit 124'
    out = _measure(tmp_path, command, timeout_seconds="100")
    assert "=== NATIVE_CELL_TIMEOUT phase=training limit=100s last_frame_hint=12345 ===" in out, out


@pytest.mark.skipif(not PROBE.exists(), reason="run_probe.sh missing")
def test_a_124_exit_with_no_ceiling_armed_prints_nothing_new(tmp_path):
    """CELL_TIMEOUT_SECONDS unset means no ceiling was ever configured for this invocation (the
    `--measure-command`/test entry point, or a diagnostic run) -- a 124 there is not necessarily
    OUR timeout, so no NATIVE_CELL_TIMEOUT marker is fabricated for it."""
    command = 'echo "F: 999"; exit 124'
    out = _measure(tmp_path, command, timeout_seconds=None)
    assert "NATIVE_CELL_TIMEOUT" not in out, out


@pytest.mark.skipif(not PROBE.exists(), reason="run_probe.sh missing")
def test_a_124_exit_with_no_readable_frame_says_unknown_rather_than_a_wrong_number(tmp_path):
    command = 'echo "nothing frame-shaped here"; exit 124'
    out = _measure(tmp_path, command, timeout_seconds="50")
    assert "=== NATIVE_CELL_TIMEOUT phase=training limit=50s last_frame_hint=unknown ===" in out, out


@pytest.mark.skipif(not PROBE.exists(), reason="run_probe.sh missing")
def test_a_non_timeout_failure_does_not_get_the_timeout_marker(tmp_path):
    """A crash (exit 1) must not be relabelled as a timeout just because a ceiling was armed."""
    command = 'echo "F: 42"; exit 1'
    out = _measure(tmp_path, command, timeout_seconds="50")
    assert "NATIVE_CELL_TIMEOUT" not in out, out


@pytest.mark.skipif(not PROBE.exists(), reason="run_probe.sh missing")
def test_a_clean_success_is_unaffected(tmp_path):
    command = 'echo "F: 42"; exit 0'
    out = _measure(tmp_path, command, timeout_seconds="50")
    assert "NATIVE_CELL_TIMEOUT" not in out, out
