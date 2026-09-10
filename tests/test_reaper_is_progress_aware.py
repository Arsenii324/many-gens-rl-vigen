"""The container reaper must stop a HUNG cell and spare a WORKING one.

## What it replaced

`sleep "$WATCH_SECONDS"; docker stop "$CELL_NAME"`. Blind wall-clock: a cell one minute from
writing its delivery died exactly like a cell that had hung hours earlier.

`launch-card-cell.sh`'s own comment records how close that came -- an endpoint projected to finish
at **18:36** against a reaper at **18:37** -- and what it would have cost. Not a lost evaluation
pass: a lost DELIVERY. `collect_record_delivery` runs *after* evaluation, so every record of a
12-hour cell would have been left unassembled on the bind mount.

## Why a better estimate is not the fix

Deriving the eval allowance from scheduled episodes (done 2026-09-09) moved the cliff; it did not
remove it. Every budget is a guess, and on the 45-hour cells this fleet is scheduled around a guess
10 % low destroys the run. So the budget decides **when to look**, and the container's own output
decides **whether to stop**.

`run_probe.sh` exports `PYTHONUNBUFFERED=1` and emits continuously -- training rows, per-stamp eval
markers, per-row endpoint markers -- so silence means stopped rather than buffered. That is the
property these tests pin, in both directions, plus the bound that stops this becoming "no reaper".
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import textwrap

ROOT = pathlib.Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "datasphere" / "native" / "launch-card-cell.sh"


def _reaper_block() -> str:
    """The reaper subshell, lifted verbatim from the launcher."""
    source = LAUNCHER.read_text()
    start = source.index('  sleep "$WATCH_SECONDS"\n  _grace_used=0')
    end = source.index(") &", start)
    return "(\n" + source[start:end] + ") &\nwait\n"


def _run(tmp_path, *, emitting: bool, grace_max: int = 1800) -> str:
    """Run the reaper with a stub `docker`. `emitting` decides what `docker logs` returns."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stopped = tmp_path / "stopped"
    logs_output = "some output from the cell" if emitting else ""
    (bin_dir / "docker").write_text(textwrap.dedent(f"""\
        #!/usr/bin/env bash
        case "$1" in
          ps)   [[ -f "{stopped}" ]] && exit 0; echo "containerid" ;;
          logs) printf '%s' {logs_output!r} ;;
          stop) echo stopped > "{stopped}" ;;
        esac
        exit 0
    """))
    (bin_dir / "docker").chmod(0o755)
    script = tmp_path / "reap.sh"
    script.write_text(
        "set -uo pipefail\n"
        f'export PATH="{bin_dir}:$PATH"\n'
        'CELL_NAME=cell-c0-test\nWATCH_SECONDS=0\n'
        f'NATIVE_REAP_MAX_GRACE_SECONDS={grace_max}\nNATIVE_REAP_STALL_SECONDS=1\n'
        + _reaper_block()
    )
    proc = subprocess.run(["bash", str(script)], stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, timeout=180)
    return proc.stdout + ("\nSTOPPED" if stopped.exists() else "\nNOT-STOPPED")


def test_a_silent_cell_is_reaped(tmp_path):
    output = _run(tmp_path, emitting=False)
    assert "STOPPED" in output and "NOT-STOPPED" not in output, output
    assert "SILENT" in output, output


def test_a_still_emitting_cell_is_granted_grace(tmp_path):
    """The regression: a working cell past its budget must not be stopped on the first check."""
    output = _run(tmp_path, emitting=True, grace_max=3)
    assert "STILL EMITTING" in output, (
        "a cell producing output past its budget was reaped without a grace grant:\n" + output
    )
    assert output.index("STILL EMITTING") < output.index("REAPING"), output


def test_grace_is_bounded_so_the_reaper_still_exists(tmp_path):
    output = _run(tmp_path, emitting=True, grace_max=2)
    assert "out of grace" in output and "STOPPED" in output, output
    # ...and it says plainly that this stop cost work, unlike the silent case.
    assert "DOES cost work" in output, output


def test_the_launcher_no_longer_stops_on_the_clock_alone():
    """Anchored on the launcher's text: the old one-shot form must not come back."""
    source = LAUNCHER.read_text()
    assert not re.search(r'sleep "\$WATCH_SECONDS"\s*\n\s*if \[\[ -n "\$\(docker ps', source), (
        "the blind wall-clock reaper is back"
    )
    assert "docker logs --since" in source
