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


# --- the symmetric blind spot, at the other end of the run -------------------------------------
# [Claude 2026-09-08] Creating the marker fixed the bootstrap window. Never removing it left the
# mirror-image defect: once the cell exits, our process count returns to zero while the watcher goes
# on expecting one of ours, so a neighbour taking the card we have just VACATED reads as a breach.
# The alarm would fire at precisely the moment the card is legitimately somebody else's.


def test_standing_down_when_the_cell_retracts_its_marker(tmp_path, monkeypatch, capsys):
    watcher = _load("watch_card_exclusivity")
    marker = tmp_path / "cell-active"
    marker.write_text("")

    # The marker vanishes after the second check, and a stranger's process arrives at the same
    # time -- the exact race the false alarm would fire on.
    calls = {"n": 0}

    def card(device):
        calls["n"] += 1
        if calls["n"] >= 2 and marker.exists():
            marker.unlink()
        return {"procs": 1, "used": 4000, "free": 28000, "util": 50}

    monkeypatch.setattr(watcher, "card", card)
    monkeypatch.setattr(sys, "argv", [
        "watch_card_exclusivity.py", "--device", "0", "--expect-ours", "1",
        "--max-seconds", "30", "--interval", "0.01", "--stop-when-inactive",
        "--active-file", str(marker)])
    rc = watcher.main()
    err = capsys.readouterr().err
    assert rc == 0, err
    assert "STANDING DOWN" in err, err
    assert "IS NOT OURS ALONE" not in err, "raised a breach on a card we had already vacated:\n" + err
    # It must not be mistaken for the timer running out, which is an alarm, not a clean end.
    assert "FROM NOW ON NOBODY IS WATCHING" not in err, err


def test_a_marker_that_never_appeared_does_not_stand_the_watch_down(tmp_path, monkeypatch, capsys):
    """A cell that dies during bootstrap leaves the card unwatched -- when a watch matters most."""
    watcher = _load("watch_card_exclusivity")
    marker = tmp_path / "cell-active"          # never created
    monkeypatch.setattr(watcher, "card", _fake_card(0))
    monkeypatch.setattr(sys, "argv", [
        "watch_card_exclusivity.py", "--device", "0", "--expect-ours", "1",
        "--max-seconds", "0.15", "--interval", "0.05", "--stop-when-inactive",
        "--active-file", str(marker)])
    watcher.main()
    err = capsys.readouterr().err
    assert "STANDING DOWN" not in err, "stood down without the cell ever having started:\n" + err
    assert "FROM NOW ON NOBODY IS WATCHING" in err, err


def test_the_runner_actually_retracts_the_marker():
    runner = (ROOT / "datasphere" / "native" / "run_probe.sh").read_text()
    assert 'rm -f "$(dirname "$NATIVE_YIELD_SENTINEL")/cell-active"' in runner, (
        "run_probe.sh must remove the marker when the cell exits, or --stop-when-inactive never "
        "fires and the vacated-card false alarm comes back")
    assert "NATIVE_CELL_ACTIVE_MARKER_CLEARED" in runner
