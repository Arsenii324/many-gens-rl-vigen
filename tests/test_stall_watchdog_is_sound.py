"""The stall watchdog must measure the process, not its stdout buffer.

[Claude 2026-09-08] Python block-buffers stdout when it is not a tty, and a cell's stdout is
`run_measured`'s fifo. A healthy cell can therefore emit nothing for a long time simply because its
8 KB buffer has not filled -- indistinguishable, to a watchdog reading the log's size, from a hang.

It killed two healthy `ctrl` cells (`bt1hvkmei18hasgj5bbv`, `bt17gfr8pq5astv4g3n3`), and both were
initially misdiagnosed as a CUDA driver/runtime problem because their last visible line was a
`cuStreamGetGreenCtx` warning. The 10k `ctrl` cell that SUCCEEDED printed that same warning, the
same 8.27 GiB allocator message and the same buffer-comparator diffs, then ran to 1851 lines.

`runnable/ctrl/train_ppo.py` has five `print()` calls and one `flush=True`. Nothing obliges a
baseline's upstream code to flush, so the runner has to make the environment unbuffered rather than
each clone remember to.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER = ROOT / "datasphere" / "native" / "run_probe.sh"


def test_the_cell_runs_unbuffered():
    text = RUNNER.read_text()
    supervisor = re.search(r"local supervisor_script='([^']*)'", text)
    assert supervisor, "the supervisor script line moved; re-point this test"
    assert "PYTHONUNBUFFERED=1" in supervisor.group(1), (
        "without this the stall watchdog measures a stdout buffer's flush cadence, not the "
        "process's liveness -- and would kill a 45-hour production cell at thirty minutes")


def test_the_watchdog_still_exists_and_kills_the_group():
    text = RUNNER.read_text()
    assert "NATIVE_CELL_STALLED" in text
    assert 'kill -TERM "-$pgid"' in text, (
        "the thing that hangs is often a child -- a DataLoader worker, a vectorised env worker -- "
        "so killing the parent alone can leave it")


def test_the_stall_limit_exceeds_the_longest_measured_silent_phase():
    """Places365's first load is 561.8s; the endpoint eval grid is 96s."""
    text = RUNNER.read_text()
    default = re.search(r'stall_seconds="\$\{CELL_STALL_SECONDS:-(\d+)\}"', text)
    assert default, "the default moved"
    assert int(default.group(1)) >= 1800, (
        "1800s is 3.2x the longest measured silent phase; lowering it re-opens the false positive "
        "that killed two healthy ctrl cells")
