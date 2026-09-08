"""Free disk must be watched CONTINUOUSLY, and breaching the floor must stop our own cell.

[Claude 2026-09-09] `run_on_production_host.sh` checks disk once, before the container starts. A
cell then writes for hours -- pip into the container layer, checkpoints in triplicate (trainer copy,
`retain()` copy and the closing archive all live at once), Places365 for the families that need it.
The production filesystem is SHARED and sits at 99% used, 317 GB free of 20 TB.

The failure guarded here is not our job dying. It is somebody else's job dying, or a host threshold
firing, because we filled a disk we do not own. That asymmetry is why the watch STOPS US rather
than warning: by the time a human reads a warning, the space is gone.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
WATCHER = ROOT / "scripts" / "watch_disk_headroom.py"
LAUNCHER = ROOT / "datasphere" / "native" / "launch-card-cell.sh"


def _run(args, timeout=60):
    return subprocess.run([sys.executable, str(WATCHER)] + args,
                          capture_output=True, text=True, timeout=timeout)


def test_a_healthy_disk_is_left_alone(tmp_path):
    sentinel = tmp_path / "yield.sentinel"
    out = _run(["--path", str(tmp_path), "--floor-gib", "1", "--sentinel", str(sentinel),
                "--max-seconds", "5", "--interval", "0.2"])
    assert not sentinel.exists(), "wrote a stop sentinel without a breach"
    assert "DISK WATCH armed" in out.stderr, out.stderr


def test_a_breach_during_the_run_writes_the_sentinel(tmp_path, monkeypatch, capsys):
    """The whole point of the watcher, driven through the real module with a falling disk.

    Arm-time space is healthy; it then falls below the floor, which is the case a preflight cannot
    see and this file exists for.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location("watch_disk_headroom", WATCHER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    sentinel = tmp_path / "nested" / "yield.sentinel"      # parent does not exist yet
    readings = iter([500.0, 400.0, 10.0])                  # healthy, healthy, breach

    monkeypatch.setattr(mod, "free_gib", lambda path: next(readings, 10.0))
    monkeypatch.setattr(sys, "argv", [
        "watch_disk_headroom.py", "--path", str(tmp_path), "--floor-gib", "100",
        "--sentinel", str(sentinel), "--max-seconds", "30", "--interval", "0.01"])

    rc = mod.main()
    err = capsys.readouterr().err
    assert rc == 1, err
    assert "DISK FLOOR BREACHED" in err, err
    assert sentinel.exists(), "breached the floor and did NOT stop the cell:\n" + err
    body = sentinel.read_text()
    assert "disk floor breached" in body and "10.0 GiB free" in body, body
    # It must say how much WE moved, not only the absolute figure.
    assert "fallen 490.0 GiB since this watch armed" in err, err


def test_an_impossible_floor_refuses_to_arm_rather_than_stopping_a_healthy_cell(tmp_path):
    """Below the floor at arm time means do not start -- not: start and immediately stop."""
    sentinel = tmp_path / "yield.sentinel"
    out = _run(["--path", str(tmp_path), "--floor-gib", "99999999", "--sentinel", str(sentinel),
                "--max-seconds", "5"])
    assert out.returncode == 4, out.stderr
    assert "ALREADY BELOW THE FLOOR" in out.stderr
    assert not sentinel.exists(), (
        "wrote a stop sentinel for a cell that never started; a later run would find it and "
        "stop itself for a reason that no longer exists")


def test_dry_run_reports_without_stopping_anything(tmp_path):
    sentinel = tmp_path / "yield.sentinel"
    out = _run(["--path", str(tmp_path), "--floor-gib", "99999999", "--sentinel", str(sentinel),
                "--max-seconds", "5", "--dry-run"])
    assert not sentinel.exists()


def test_a_short_budget_is_refused_like_the_card_watches():
    out = _run(["--path", "/", "--floor-gib", "1", "--sentinel", "/tmp/never-written",
                "--max-seconds", "4500", "--must-cover-seconds", "12600"])
    assert out.returncode == 3, out.stderr
    assert "REFUSING TO ARM" in out.stderr
    assert "exit 3" in out.stderr


def test_an_unreadable_path_refuses_rather_than_reporting_healthy():
    out = _run(["--path", "/definitely/not/a/path/here", "--floor-gib", "1",
                "--sentinel", "/tmp/never-written", "--max-seconds", "5"])
    assert out.returncode == 2, out.stdout + out.stderr
    assert "cannot stat" in out.stderr


def test_the_launcher_arms_it_and_derives_the_floor():
    code = "\n".join(l for l in LAUNCHER.read_text().splitlines()
                     if not l.lstrip().startswith("#"))
    assert "watch_disk_headroom.py" in code, "the disk watch is never armed"
    assert "--must-cover-seconds" in code
    # Derived from measured free space, not a typed constant.
    assert 'df -PBG "$W"' in code, "free space is not measured"
    assert "DISK_FLOOR_GIB=$(( _free_gib - DISK_ALLOWANCE_GIB ))" in code
    assert "DISK_ABS_FLOOR_GIB" in code, "no absolute floor protecting the machine itself"


def test_the_launcher_stands_the_disk_watch_down():
    code = LAUNCHER.read_text()
    stop = [l for l in code.splitlines() if "docker stop" in l and "$EXCL" in l]
    assert stop and '"$DISK"' in stop[0], f"the disk watch is never stopped: {stop}"


def test_it_uses_the_same_sentinel_the_cell_polls():
    """A private stop-file nobody reads would be a watch that stops nothing."""
    code = LAUNCHER.read_text()
    assert code.count("/work/yield.sentinel") >= 2, (
        "the disk watch must write the SAME sentinel run_probe.sh polls for")
