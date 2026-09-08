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


# --- packing: "ours" is one process per CELL, not one per RUN --------------------------------
# [Claude 2026-09-09] The first packed run (idaac+ppg, NATIVE_CONCURRENT=1) yielded to ITSELF. Two
# cells put two processes on the card; the daemon added a hardcoded 1 to its baseline, read the
# second as a co-tenant, wrote the sentinel and stopped both healthy cells:
#     yielded at ...: compute processes went 0(+ours) -> 2
# Nothing failed. The mechanism worked exactly as written against an expectation that was wrong,
# which is why no error appeared anywhere -- the run simply stopped and blamed a neighbour who did
# not exist.


def test_the_yield_daemon_does_not_yield_to_its_own_packed_cells(tmp_path, monkeypatch, capsys):
    daemon = _load("yield_gpu_to_neighbour")
    marker = tmp_path / "cell-active"
    marker.write_text("")
    sentinel = tmp_path / "yield.sentinel"

    # Baseline empty, then TWO processes appear -- both ours, because we packed two cells.
    seq = iter([{"procs": 0, "free_mib": 30000, "util": 0},
                {"procs": 2, "free_mib": 29000, "util": 8},
                {"procs": 2, "free_mib": 29000, "util": 8}])
    last = {"procs": 2, "free_mib": 29000, "util": 8}
    monkeypatch.setattr(daemon, "card", lambda d: next(seq, last))
    monkeypatch.setattr(sys, "argv", [
        "yield_gpu_to_neighbour.py", "--device", "0", "--sentinel", str(sentinel),
        "--active-file", str(marker), "--expect-ours", "2",
        "--max-seconds", "0.4", "--interval", "0.05", "--floor-mib", "1000"])
    daemon.main()
    err = capsys.readouterr()
    assert not sentinel.exists(), (
        "yielded to our own packed cells:\n" + err.out + err.err)


def test_it_still_yields_when_a_real_neighbour_joins_a_packed_run(tmp_path, monkeypatch, capsys):
    """Raising --expect-ours must not blind the daemon to an actual co-tenant."""
    daemon = _load("yield_gpu_to_neighbour")
    marker = tmp_path / "cell-active"
    marker.write_text("")
    sentinel = tmp_path / "yield.sentinel"

    seq = iter([{"procs": 0, "free_mib": 30000, "util": 0},
                {"procs": 2, "free_mib": 29000, "util": 8}])
    stranger = {"procs": 3, "free_mib": 20000, "util": 60}
    monkeypatch.setattr(daemon, "card", lambda d: next(seq, stranger))
    monkeypatch.setattr(sys, "argv", [
        "yield_gpu_to_neighbour.py", "--device", "0", "--sentinel", str(sentinel),
        "--active-file", str(marker), "--expect-ours", "2",
        "--max-seconds", "3", "--interval", "0.05", "--floor-mib", "1000"])
    daemon.main()
    assert sentinel.exists(), (
        "a third process joined a 2-cell packed run and the daemon did not yield:\n"
        + capsys.readouterr().err)
    assert "-> 3" in sentinel.read_text(), sentinel.read_text()


def test_the_launcher_derives_the_count_from_the_cell_list():
    launcher = (ROOT / "datasphere" / "native" / "launch-card-cell.sh").read_text()
    assert 'EXPECT_OURS="${NATIVE_EXPECT_OURS:-$_cell_count}"' in launcher, (
        "the expected process count is not derived from CELLS")
    assert "awk -F, '{print NF}'" in launcher, "the cell list is not counted"
    assert '--expect-ours "$EXPECT_OURS"' in launcher
    assert launcher.count('--expect-ours "$EXPECT_OURS"') == 2, (
        "both card watchers must receive it; the yield daemon was the one that got this wrong")


# --- presence is debounced, starvation is not ---------------------------------------------------
# [Claude 2026-09-09] A 600k production cell was killed ~90 seconds in by `procs -> 6` while 28836
# MiB of 32494 was FREE and utilisation was 21%. Our two cells declare one process each, so the rest
# were other people's -- and on a box running a dozen containers, brief GPU touches are normal
# traffic rather than a claim on the card. What we owe a co-tenant is memory, because the process
# that asks the driver second is the one that fails.


def _run_daemon(monkeypatch, tmp_path, readings, *, expect_ours=2, after=3, floor=4000,
                max_seconds=5):
    daemon = _load("yield_gpu_to_neighbour")
    marker = tmp_path / "cell-active"
    marker.write_text("")
    sentinel = tmp_path / "yield.sentinel"
    seq = iter(readings)
    last = readings[-1]
    monkeypatch.setattr(daemon, "card", lambda d: next(seq, last))
    monkeypatch.setattr(sys, "argv", [
        "yield_gpu_to_neighbour.py", "--device", "0", "--sentinel", str(sentinel),
        "--active-file", str(marker), "--expect-ours", str(expect_ours),
        "--yield-after-checks", str(after), "--floor-mib", str(floor),
        "--max-seconds", str(max_seconds), "--interval", "0.01"])
    daemon.main()
    return sentinel


def test_a_transient_cotenant_does_not_kill_a_long_run(tmp_path, monkeypatch, capsys):
    ours = {"procs": 2, "free_mib": 28000, "util": 8}
    blip = {"procs": 6, "free_mib": 28836, "util": 21}          # the real 2026-09-09 reading
    sentinel = _run_daemon(monkeypatch, tmp_path,
                           [{"procs": 0, "free_mib": 32000, "util": 0}, ours, blip, ours, ours])
    assert not sentinel.exists(), (
        "a one-poll blip killed the run:\n" + capsys.readouterr().out)


def test_a_persistent_cotenant_still_triggers_a_yield(tmp_path, monkeypatch, capsys):
    ours = {"procs": 2, "free_mib": 28000, "util": 8}
    guest = {"procs": 6, "free_mib": 20000, "util": 60}
    sentinel = _run_daemon(monkeypatch, tmp_path,
                           [{"procs": 0, "free_mib": 32000, "util": 0}, ours,
                            guest, guest, guest, guest, guest])
    assert sentinel.exists(), (
        "a co-tenant present across several checks did not trigger a yield:\n"
        + capsys.readouterr().out)


def test_memory_starvation_yields_on_the_first_reading(tmp_path, monkeypatch, capsys):
    """Debouncing presence must not debounce actual harm."""
    ours = {"procs": 2, "free_mib": 28000, "util": 8}
    starved = {"procs": 2, "free_mib": 500, "util": 90}
    sentinel = _run_daemon(monkeypatch, tmp_path,
                           [{"procs": 0, "free_mib": 32000, "util": 0}, ours, starved])
    assert sentinel.exists(), (
        "free memory fell below the floor and the daemon waited:\n" + capsys.readouterr().out)
    assert "free memory" in sentinel.read_text().lower() or "floor" in sentinel.read_text().lower()
