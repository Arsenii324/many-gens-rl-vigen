"""Item 1 of the 2026-09-20 stop-mechanisms fix: THE YIELD MUST COVER THE WHOLE CELL.

Before this, the sentinel poller lived inside `run_measured()` in `run_probe.sh` and looped
`while kill -0 "$training_pid"`, so it died the moment training finished. Curve and endpoint
evaluation -- 2.04x the training time (measured, idaac 600k) -- ran with nothing reading
`NATIVE_YIELD_SENTINEL` at all. Observed 2026-09-20 (`notes/production-host/38-...md`): free memory
fell to 1,905 MiB under the 4,000 MiB floor during `drqv2`'s endpoint grid; the sentinel was
written; the cell kept evaluating for 50 minutes because nothing was polling for it.

This drives the REAL shipped functions (`start_cell_yield_watch`, `cell_yield_requested`,
`run_watched_eval`, `run_curve_eval`, `run_endpoint_eval`) end to end, with a stubbed `eval_grid.py`
that just sleeps, and writes the sentinel WHILE that stub is running -- exactly the scenario the
`production-host/38` note asks for: "It needs a test that writes the sentinel during a stubbed
evaluation phase and sees the cell stop -- red against today's script."

`NATIVE_YIELD_POLL_SECONDS` (default 15 in production, unchanged) is set small here so the test
does not need a multi-minute stub to give the poller a chance to notice; the poller's own logic is
otherwise untouched.

Output is captured to real FILES, not pipes: the poller this starts is not explicitly reaped by
these minimal harnesses (only `retract_cell_from_card`, exercised in `run_one_cell` itself, does
that), so a `capture_output=True`/PIPE-based subprocess call can hang waiting for EOF on a pipe an
orphaned background poller still holds open, even after the harness script itself has exited.
"""
from __future__ import annotations

import pathlib
import subprocess
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROBE = ROOT / "datasphere" / "native" / "run_probe.sh"

FUNCTIONS = ["start_cell_yield_watch", "cell_yield_requested", "run_watched_eval",
             "run_curve_eval", "run_endpoint_eval"]


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


STUB_SLEEP_SECONDS = 8
# `exec` replaces this stub's own process image with `sleep`, rather than forking a child that
# would inherit this function's fifo write-end -- setsid is unavailable on this laptop (macOS ships
# none), so without `exec` a killed stub would leave an orphaned `sleep` holding the fifo open,
# stalling `tee` (and this test) until the orphan's OWN timer ran out regardless of the kill. A
# real `eval_grid.py` is a single python process with no worker pool (see run_watched_eval's own
# comment), so `exec` here is the more faithful stand-in, not a workaround for the test alone.
SLEEPY_EVAL_GRID = f"#!/usr/bin/env bash\nexec sleep {STUB_SLEEP_SECONDS}\n"


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
    stub.write_text(SLEEPY_EVAL_GRID)
    stub.chmod(0o755)
    return stub_dir


def _run_phase_and_yield_mid_flight(tmp_path: pathlib.Path, cell_out: pathlib.Path, call: str,
                                    functions: str) -> tuple[str, int, float]:
    """Starts the whole-cell poller (polling every 1s, not production's 15s -- see module
    docstring), runs `call` (a run_curve_eval/run_endpoint_eval invocation) against a stub that
    sleeps `STUB_SLEEP_SECONDS`, and writes the sentinel ~1s in. Returns (log, returncode,
    elapsed_seconds) so a caller can assert BOTH the marker text and that it actually stopped early
    rather than waiting out the full stub sleep. The caller must already have built cell_out (via
    `_make_cell`) and referenced the same path inside `call`."""
    stub_dir = _stub_python3(tmp_path)
    sentinel = tmp_path / "yield.sentinel"
    script = tmp_path / "harness.sh"
    script.write_text(
        "set -uo pipefail\n"
        f'export PATH="{stub_dir}:$PATH"\n'
        f'export NATIVE_YIELD_SENTINEL="{sentinel}"\n'
        "export NATIVE_YIELD_POLL_SECONDS=1\n"
        "CURVE_EVAL_EPISODES=1\nENDPOINT_EVAL_EPISODES=1\nENDPOINT_EVAL_REGIMES=train\n"
        "ENDPOINT_EVAL_SCENES=0\n"
        + functions + "\n"
        f'start_cell_yield_watch "{cell_out}"\n'
        # `... || rc=$?`, not a bare call: run_watched_eval leaves `-e` ON when it returns
        # non-zero (matching run_probe.sh's own top-level `set -euo pipefail`, which every
        # OTHER caller already sits under), and this harness -- like
        # test_supplementary_eval_does_not_fail_the_cell.py's -- deliberately does not, so a
        # bare call would abort here rather than let the test see the return code.
        'rc=0\n'
        f"{call} || rc=$?\n"
        'echo "PHASE_RC=$rc"\n'
    )
    log = tmp_path / "out.log"
    started = time.monotonic()
    with open(log, "wb") as fh:
        proc = subprocess.Popen(["bash", str(script)], stdout=fh, stderr=subprocess.STDOUT)
    time.sleep(1.5)
    sentinel.write_text("yielded at 1789912622: free memory 1905 MiB is below the 4000 MiB floor\n"
                        "free_mib=1905 procs=2 util=100\n")
    try:
        proc.wait(timeout=STUB_SLEEP_SECONDS + 10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    elapsed = time.monotonic() - started
    return log.read_text(), proc.returncode, elapsed


@pytest.mark.skipif(not PROBE.exists(), reason="run_probe.sh missing")
def test_a_sentinel_during_curve_eval_stops_the_cell_and_names_the_phase(tmp_path):
    cell_out = _make_cell(tmp_path)
    out, _, elapsed = _run_phase_and_yield_mid_flight(
        tmp_path, cell_out, f'run_curve_eval "{cell_out}" ctrl ctrl 1 2000', _shipped_functions())
    assert "=== NATIVE_CELL_YIELDED phase=curve-eval" in out, out
    assert "below the 4000 MiB floor" in out, out
    assert "PHASE_RC=0" not in out, out
    assert "NATIVE_CURVE_EVAL_COMPLETED" not in out, (
        "the stub ran to completion -- the cell did not actually stop:\n" + out)
    assert elapsed < STUB_SLEEP_SECONDS - 1, (
        f"took {elapsed:.1f}s -- close to the stub's {STUB_SLEEP_SECONDS}s sleep, so it likely "
        f"ran on:\n{out}")


@pytest.mark.skipif(not PROBE.exists(), reason="run_probe.sh missing")
def test_a_sentinel_during_endpoint_eval_stops_the_cell_and_names_the_phase(tmp_path):
    cell_out = _make_cell(tmp_path)
    out, _, elapsed = _run_phase_and_yield_mid_flight(
        tmp_path, cell_out,
        f'run_endpoint_eval "{cell_out}" ctrl ctrl 1 600000',
        _shipped_functions())
    assert "=== NATIVE_CELL_YIELDED phase=endpoint-eval" in out, out
    assert "below the 4000 MiB floor" in out, out
    assert "NATIVE_ENDPOINT_EVAL_COMPLETED" not in out, (
        "the stub ran to completion -- the cell did not actually stop:\n" + out)
    assert elapsed < STUB_SLEEP_SECONDS - 1, f"took {elapsed:.1f}s:\n{out}"


@pytest.mark.skipif(not PROBE.exists(), reason="run_probe.sh missing")
def test_the_cell_exits_through_its_normal_failure_path_not_a_crash(tmp_path):
    """A yield must be a clean, non-zero RETURN from the function -- not a bash crash -- so
    run_one_cell's `|| return 1` gates handle it exactly like any other failure."""
    cell_out = _make_cell(tmp_path)
    out, _, _ = _run_phase_and_yield_mid_flight(
        tmp_path, cell_out, f'run_curve_eval "{cell_out}" ctrl ctrl 1 2000', _shipped_functions())
    assert "PHASE_RC=" in out, out
    rc_line = [l for l in out.splitlines() if l.startswith("PHASE_RC=")][0]
    rc = int(rc_line.split("=")[1])
    assert rc != 0, out
    assert "NATIVE_CURVE_EVAL_ABORTED_ON_YIELD" in out, out


@pytest.mark.skipif(not PROBE.exists(), reason="run_probe.sh missing")
def test_a_yield_during_the_other_gap_still_stops_the_cell_before_the_next_phase(tmp_path):
    """A yield that lands in the synchronous gap between phases (phase="other", nothing to kill)
    must still be caught before the NEXT phase starts -- run_one_cell's `cell_yield_requested`
    guards, not this test's stub sleeping through it."""
    cell_out = _make_cell(tmp_path)
    sentinel = tmp_path / "yield.sentinel"
    script = tmp_path / "harness.sh"
    script.write_text(
        "set -uo pipefail\n"
        f'export NATIVE_YIELD_SENTINEL="{sentinel}"\n'
        "export NATIVE_YIELD_POLL_SECONDS=1\n"
        + _shipped_functions() + "\n"
        f'start_cell_yield_watch "{cell_out}"\n'
        # Simulate the gap: phase is "other" (the default), nothing running, sentinel appears.
        f'echo "yielded at 1: reason" > "{sentinel}"\n'
        'sleep 2\n'  # give the (1s-interval) poller a chance to notice
        f'if cell_yield_requested "{cell_out}"; then echo YIELD_SEEN; else echo YIELD_MISSED; fi\n'
    )
    log = tmp_path / "out.log"
    with open(log, "wb") as fh:
        proc = subprocess.Popen(["bash", str(script)], stdout=fh, stderr=subprocess.STDOUT)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    out = log.read_text()
    assert "YIELD_SEEN" in out, out
    assert "=== NATIVE_CELL_YIELDED phase=other" in out, out
