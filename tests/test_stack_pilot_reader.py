"""The pilot reader must catch the failure that finiteness does not.

`notes/PRODUCTION-RUNBOOK.md:18` records the one that actually happened: `ibac_sni` at sigma ~ 4.3,
entropy climbing 9.95 -> 20.03, success 0.00 throughout -- and **perfectly finite the whole way**.
A reader that only checked for NaN would have cleared it.

So the two fixtures below are not decoration. The runaway one reproduces that trajectory, and if
this file ever passes it, the instrument has stopped doing the only job it was built for.
"""
from __future__ import annotations

import csv
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from read_stack_pilot import read  # noqa: E402


def _write(cell: pathlib.Path, log_std_of, ret=2.0):
    cell.mkdir(parents=True, exist_ok=True)
    with (cell / "log.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["frames", "mean_log_std", "rreturn_mean", "policy_loss"])
        for i in range(40):
            writer.writerow([i * 2560, log_std_of(i), ret + 0.4 * i, -0.01])


def test_a_healthy_curve_is_not_indicted(tmp_path):
    _write(tmp_path / "healthy", lambda i: -0.02 * i)
    checks, indicted = read(tmp_path / "healthy")
    assert not indicted, checks


def test_the_documented_runaway_is_indicted_despite_being_finite(tmp_path):
    """sigma 1 -> 4.3, finite throughout. This is the RUNBOOK's own case."""
    cell = tmp_path / "runaway"
    _write(cell, lambda i: (math.log(4.3) / 39) * i, ret=1.8)
    checks, indicted = read(cell)
    assert indicted, "the finite-but-saturated policy must be indicted"
    finite = [c for c in checks if c[0] == "FINITE"][0]
    assert finite[1] == "pass", (
        "the fixture must stay FINITE -- if it goes non-finite the test starts passing for the "
        "wrong reason and stops proving anything about saturation")
    saturated = [c for c in checks if c[0] == "NOT SATURATED"][0]
    assert saturated[1] == "INDICTED"


def test_a_collapsed_policy_is_indicted(tmp_path):
    """The opposite failure: sigma driven to zero cannot explore."""
    _write(tmp_path / "collapsed", lambda i: -0.2 * i)
    checks, indicted = read(tmp_path / "collapsed")
    assert indicted
    assert [c for c in checks if c[0] == "NOT COLLAPSED"][0][1] == "INDICTED"


def test_a_missing_log_std_is_not_silently_cleared(tmp_path):
    """A cell that cannot be checked must not read as a cell that was checked and passed."""
    cell = tmp_path / "nostd"
    cell.mkdir(parents=True)
    with (cell / "log.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["frames", "rreturn_mean"])
        for i in range(20):
            writer.writerow([i * 2560, 3.0])
    checks, _ = read(cell)
    assert [c for c in checks if c[0] == "NOT SATURATED"][0][1] == "UNREADABLE"
