"""A stranger arriving during the bootstrap window must not be credited as ours.

Both card watchers count compute processes against a baseline. During the ~10 minute apt/pip
bootstrap our cell has ZERO processes on the card, so the first process to appear was credited to
us -- and a stranger arriving in that window was silently absorbed. Neither instrument would have
said anything.

`run_probe.sh` now touches a `cell-active` marker when the cell goes on the card, and both watchers
expect zero processes of ours until it exists. This pins that behaviour, because it is a
conditional nobody will remember and its failure mode is silence.

Driven through the real modules with only `nvidia-smi` replaced -- the arithmetic under test is the
watcher's, not a mock's.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_card(procs: int, used: int = 4000, free: int = 28000, util: int = 50):
    return lambda device: {"procs": procs, "used": used, "free": free, "util": util,
                           "used_mib": used, "free_mib": free, "utilization_pct": util}


@pytest.mark.parametrize("marker_present, procs, expect_breach", [
    # No marker: the cell is still bootstrapping, so ANY process is somebody else's.
    (False, 1, True),
    (False, 0, False),
    # Marker present: one process is legitimately ours; two is a stranger.
    (True, 1, False),
    (True, 2, True),
])
def test_exclusivity_expects_zero_until_the_cell_announces_itself(
        tmp_path, monkeypatch, capsys, marker_present, procs, expect_breach):
    watcher = _load("watch_card_exclusivity")
    marker = tmp_path / "cell-active"
    if marker_present:
        marker.write_text("")
    monkeypatch.setattr(watcher, "card", _fake_card(procs))
    monkeypatch.setattr(sys, "argv", [
        "watch_card_exclusivity.py", "--device", "0", "--expect-ours", "1",
        "--max-seconds", "0.1", "--interval", "0.05", "--active-file", str(marker)])
    rc = watcher.main()
    breached = rc != 0
    assert breached is expect_breach, (
        f"marker_present={marker_present} procs={procs}: expected "
        f"{'a breach' if expect_breach else 'silence'}, got rc={rc}\n"
        + capsys.readouterr().err)


def test_the_marker_is_actually_written_by_the_runner():
    """A flag no producer sets is a flag that silently disables the guard it gates."""
    runner = (ROOT / "datasphere" / "native" / "run_probe.sh").read_text()
    assert "cell-active" in runner, (
        "run_probe.sh must touch the cell-active marker, or --active-file makes both watchers "
        "expect zero processes FOREVER and every run screams")
    assert 'NATIVE_CELL_ACTIVE_MARKER' in runner, "the marker must be announced in the log too"
