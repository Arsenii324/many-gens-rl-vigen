"""Item 2 of the 2026-09-20 stop-mechanisms fix: THE STALL WATCHDOG MUST COVER EVALUATION.

`eval-cost-and-timeout-trace.md` Part 2, 2b, read before this fix: "**Not active during
evaluation**: [the stall watchdog] is spawned only inside `run_measured`, and `run_measured` is
called for training ... curve/endpoint eval ... invoke `python3 scripts/eval_grid.py` directly ...
hence no stall watchdog during evaluation." A hung evaluation (a DataLoader worker, an EGL/render
lock, anything that stops without exiting) would previously run until `CELL_TIMEOUT_SECONDS`, sized
for the longest legitimate 45-hour RUN -- a useless bound on a hang, per `run_measured`'s own
comment about why the training-side watchdog exists at all.

This drives the REAL shipped `run_watched_eval` (used by both `run_curve_eval` and
`run_endpoint_eval`) against a stub `eval_grid.py` that writes ONE row to its `--out` file and then
goes completely silent -- on both its own stdout (which feeds `training.log`) and its output file
-- for longer than `CELL_STALL_SECONDS`. `NATIVE_STALL_CHECK_SECONDS` (default 30, matching
training's hardcoded cadence) is set to 1 here so the test does not need a 30-minute stub; the
default is unchanged. `CELL_STALL_SECONDS` itself (the actual threshold) is NOT shortened or
lengthened in the shipped code -- only set small here, as any caller may.
"""
from __future__ import annotations

import pathlib
import subprocess
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROBE = ROOT / "datasphere" / "native" / "run_probe.sh"

FUNCTIONS = ["cell_yield_requested", "run_watched_eval", "run_curve_eval", "run_endpoint_eval"]


def _extract(text: str, name: str) -> str:
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


def _shipped_functions() -> str:
    text = PROBE.read_text()
    return "\n".join(_extract(text, name) for name in FUNCTIONS)


# Writes exactly one row, then goes silent forever on BOTH channels a stall watchdog can watch:
# its own stdout (piped into training.log) and its --out file. A real hang (a wedged DataLoader
# worker, an EGL lock) looks exactly like this from the outside: something started, then nothing.
STALLING_EVAL_GRID = (
    "#!/usr/bin/env bash\n"
    'out=""\n'
    'while [[ $# -gt 0 ]]; do\n'
    '  case "$1" in --out) out="$2"; shift 2;; *) shift;; esac\n'
    'done\n'
    'echo "starting eval"\n'
    'echo \'{"partial": true}\' > "$out"\n'
    'exec sleep 30\n'   # `exec`: no orphan child left holding the fifo open once killed
)


def _make_cell(tmp_path: pathlib.Path) -> pathlib.Path:
    cell_out = tmp_path / "cell"
    (cell_out / "checkpoints").mkdir(parents=True)
    (cell_out / "checkpoints" / "model_2000.pt").write_bytes(b"weights")
    (cell_out / "snapshot.pt").write_bytes(b"weights")
    return cell_out


def _stub_python3(tmp_path: pathlib.Path) -> pathlib.Path:
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir(exist_ok=True)
    stub = stub_dir / "python3"
    stub.write_text(STALLING_EVAL_GRID)
    stub.chmod(0o755)
    return stub_dir


def _run_and_wait_for_stall(tmp_path: pathlib.Path, cell_out: pathlib.Path,
                            call: str) -> tuple[str, float]:
    stub_dir = _stub_python3(tmp_path)
    script = tmp_path / "harness.sh"
    script.write_text(
        "set -uo pipefail\n"
        f'export PATH="{stub_dir}:$PATH"\n'
        "export CELL_STALL_SECONDS=2\n"
        "export NATIVE_STALL_CHECK_SECONDS=1\n"
        "CURVE_EVAL_EPISODES=1\nENDPOINT_EVAL_EPISODES=1\nENDPOINT_EVAL_REGIMES=train\n"
        "ENDPOINT_EVAL_SCENES=0\n"
        + _shipped_functions() + "\n"
        'rc=0\n'
        f"{call} || rc=$?\n"
        'echo "PHASE_RC=$rc"\n'
    )
    log = tmp_path / "out.log"
    started = time.monotonic()
    with open(log, "wb") as fh:
        proc = subprocess.Popen(["bash", str(script)], stdout=fh, stderr=subprocess.STDOUT)
    try:
        proc.wait(timeout=25)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    elapsed = time.monotonic() - started
    return log.read_text(), elapsed


@pytest.mark.skipif(not PROBE.exists(), reason="run_probe.sh missing")
def test_a_hung_curve_eval_is_stalled_and_stopped_with_the_phase_named(tmp_path):
    cell_out = _make_cell(tmp_path)
    out, elapsed = _run_and_wait_for_stall(
        tmp_path, cell_out, f'run_curve_eval "{cell_out}" ctrl ctrl 1 2000')
    assert "=== NATIVE_CELL_STALLED phase=curve-eval" in out, out
    assert "limit 2s" in out, out
    assert "NATIVE_CURVE_EVAL_COMPLETED" not in out, out
    # 30s stub sleep would dominate if the watchdog were inert; must stop well before that.
    assert elapsed < 20, f"took {elapsed:.1f}s -- looks like the 30s stub sleep ran to completion:\n{out}"


@pytest.mark.skipif(not PROBE.exists(), reason="run_probe.sh missing")
def test_a_hung_endpoint_eval_is_stalled_and_stopped_with_the_phase_named(tmp_path):
    cell_out = _make_cell(tmp_path)
    out, elapsed = _run_and_wait_for_stall(
        tmp_path, cell_out, f'run_endpoint_eval "{cell_out}" ctrl ctrl 1 600000')
    assert "=== NATIVE_CELL_STALLED phase=endpoint-eval" in out, out
    assert "NATIVE_ENDPOINT_EVAL_COMPLETED" not in out, out
    assert elapsed < 20, f"took {elapsed:.1f}s:\n{out}"


@pytest.mark.skipif(not PROBE.exists(), reason="run_probe.sh missing")
def test_the_threshold_default_is_not_shortened_or_lengthened():
    """The 1800s default -- item 2's own constraint -- must survive this fix unchanged."""
    text = PROBE.read_text()
    block = _extract(text, "run_watched_eval")
    assert 'stall_seconds="${CELL_STALL_SECONDS:-1800}"' in block, block


@pytest.mark.skipif(not PROBE.exists(), reason="run_probe.sh missing")
def test_a_healthy_eval_that_keeps_writing_is_never_stalled(tmp_path):
    """The control: continuous output must not be mistaken for a hang."""
    cell_out = _make_cell(tmp_path)
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    stub = stub_dir / "python3"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        'out=""\n'
        'while [[ $# -gt 0 ]]; do\n'
        '  case "$1" in --out) out="$2"; shift 2;; *) shift;; esac\n'
        'done\n'
        'for i in 1 2 3 4 5; do echo "{\\"row\\":$i}" >> "$out"; sleep 0.5; done\n'
    )
    stub.chmod(0o755)
    script = tmp_path / "harness.sh"
    script.write_text(
        "set -uo pipefail\n"
        f'export PATH="{stub_dir}:$PATH"\n'
        "export CELL_STALL_SECONDS=2\n"
        "export NATIVE_STALL_CHECK_SECONDS=1\n"
        + _shipped_functions() + "\n"
        'rc=0\n'
        f'run_curve_eval "{cell_out}" ctrl ctrl 1 2000 || rc=$?\n'
        'echo "PHASE_RC=$rc"\n'
    )
    proc = subprocess.run(["bash", str(script)], capture_output=True, text=True, timeout=15)
    out = proc.stdout + proc.stderr
    assert "NATIVE_CELL_STALLED" not in out, out
    assert "NATIVE_CURVE_EVAL_COMPLETED" in out, out
