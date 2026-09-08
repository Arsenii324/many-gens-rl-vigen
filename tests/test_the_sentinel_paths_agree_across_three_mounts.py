"""The sentinel and the marker must name the same file from three different points of view.

[Claude 2026-09-08] The yield mechanism spans three containers' filesystems and the host's:

    host                      $W/native-work/yield.sentinel
    watcher container         /work/yield.sentinel            (-v $W/native-work:/work)
    cell container            /tmp/native-work/yield.sentinel (-v $W/native-work:/tmp/native-work)

If any of the three drifts, NOTHING fails. The watcher writes a sentinel the cell never reads, so a
neighbour's arrival never stops our training; and the cell writes a `cell-active` marker the
watchers never see, so they expect zero processes of ours forever and every run reports a breach.
One direction is silent, the other is a permanent false alarm, and neither is a crash.

`cell-active` is not configured anywhere -- both sides DERIVE it from the sentinel's directory. That
is the property worth pinning, because it is what keeps them together, and it is invisible.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
LAUNCHER = (ROOT / "datasphere" / "native" / "launch-card-cell.sh").read_text()
PROBE = (ROOT / "datasphere" / "native" / "run_probe.sh").read_text()
HOST = (ROOT / "datasphere" / "native" / "run_on_production_host.sh").read_text()


def test_the_work_dir_is_mounted_at_the_path_the_cell_is_told_to_use():
    assert 'NATIVE_YIELD_SENTINEL=/tmp/native-work/yield.sentinel' in LAUNCHER
    # run_on_production_host.sh is what actually mounts it for the cell.
    assert '-v "$NATIVE_WORK_HOST_DIR:/tmp/native-work"' in HOST, (
        "the cell is told /tmp/native-work but nothing mounts the run directory there")
    assert 'NATIVE_WORK_HOST_DIR="$W/native-work"' in LAUNCHER


def test_the_watchers_see_the_same_directory_under_their_own_name():
    # Three watchers now: exclusivity, yield, and disk. All must see the SAME directory, because
    # the disk watch stops the cell through the same sentinel the yield watch uses.
    assert LAUNCHER.count('-v "$W/native-work:/work"') == 3, (
        "every watcher must mount the run directory, and at the same place; the disk watch writes "
        "the sentinel run_probe.sh polls for, so a different mount would stop nothing")
    # Two writers of the same sentinel now: the yield daemon (a neighbour needs the card) and the
    # disk watch (we are consuming a shared filesystem). One stop mechanism, two reasons to use it.
    assert LAUNCHER.count("--sentinel /work/yield.sentinel") == 2
    assert LAUNCHER.count("--active-file /work/cell-active") == 2   # card watches only


def test_the_marker_is_derived_from_the_sentinel_on_both_sides():
    """Nothing configures `cell-active`. Both sides compute it, which is what keeps them agreeing."""
    # The cell derives it from the sentinel's directory, twice: on write and on retraction.
    derived = re.findall(r'"\$\(dirname "\$NATIVE_YIELD_SENTINEL"\)/cell-active"', PROBE)
    assert len(derived) >= 2, (
        f"the cell derives the marker path {len(derived)} time(s); expected write AND retraction")
    # The watcher side is the same directory, so the basenames must match exactly.
    assert "/work/cell-active" in LAUNCHER
    assert "cell-active" in PROBE


def test_the_sentinel_is_named_once_and_the_marker_is_derived_twice():
    """Two different disciplines, and both are deliberate.

    `yield.sentinel` is spelled ONLY in the launcher. run_probe.sh never writes the basename -- it
    takes `$NATIVE_YIELD_SENTINEL` whole -- so there is exactly one place to change and no second
    copy to drift. `cell-active` is the opposite: nothing passes it, both sides compute it from the
    sentinel's directory, so the guarantee comes from the derivation rather than from a shared
    constant. Pinning the wrong discipline on either would invite a "fix" that breaks it.
    """
    assert "yield.sentinel" in LAUNCHER
    assert "yield.sentinel" not in PROBE, (
        "run_probe.sh has started spelling the sentinel basename; it should use "
        "$NATIVE_YIELD_SENTINEL whole, or there are now two places to keep in step")
    assert PROBE.count("/cell-active") >= 2 and LAUNCHER.count("/cell-active") == 2

    # No near-miss spellings that would look right in a diff but match nothing.
    for wrong in ("cell_active", "cell-active.txt", "yield-sentinel", "yield_sentinel"):
        assert wrong not in LAUNCHER, f"{wrong} in the launcher will not match run_probe.sh"
        assert wrong not in PROBE, f"{wrong} in run_probe.sh will not match the launcher"


def test_the_editable_import_check_uses_the_module_names_not_the_directory_names():
    """`envs/robosuiteVGB` is the directory; `robosuitevgb` is the module.

    [Claude 2026-09-09] The first version of this check imported `robosuiteVGB` and failed on a cell
    whose install had just printed `Successfully installed robosuitevgb-1.0.0`. It killed a healthy
    run. A check that refuses a correct state is worse than no check at all, because a refusal is
    believed.
    """
    text = PROBE
    line = [l for l in text.splitlines() if l.strip().startswith("for _mod in")]
    assert line, "the editable import check is gone"
    assert "robosuitevgb" in line[0], f"wrong module spelling: {line[0].strip()}"
    assert "robosuiteVGB" not in line[0], (
        f"checks the DIRECTORY name, which is not importable: {line[0].strip()}")
    # And the codebase must agree that this is the importable name.
    repo_imports = (ROOT / "datasphere" / "native" / "run_probe.sh").read_text()
    assert "envs/robosuiteVGB" in repo_imports, "the directory spelling should still be used for paths"
