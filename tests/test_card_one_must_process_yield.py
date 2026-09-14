"""Card 1 is not ours to take, and the launcher must enforce that rather than trust the caller.

[Claude 2026-09-10] The standing rule for this host: card 0 may run with the memory floor alone;
any other card must process-yield or not run. Before this, the rule held only because
`battery-chain.sh` hardcodes `CARD=0` -- `launch-card-cell.sh` itself did not know the difference,
so `CARD=1 bash launch-card-cell.sh ...` would have armed a memory-only yield and said nothing.

These pin the DECLARATION, not the runtime: the launcher's real behaviour needs a GPU host and a
payload, so a unit test cannot execute it. What a unit test can refuse is the guard being deleted,
weakened, or reordered after the watch it protects -- which is how this class of rule actually
dies. The runtime proof is the abort message appearing in a real card-1 launch.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "datasphere" / "native" / "launch-card-cell.sh"


def test_the_launcher_is_syntactically_valid():
    """A guard inside a script that will not parse protects nothing."""
    assert subprocess.run(["bash", "-n", str(LAUNCHER)]).returncode == 0


def test_a_non_zero_card_without_process_yield_aborts():
    source = LAUNCHER.read_text()
    assert 'if [[ "$CARD" != "0" ]]; then' in source
    assert 'NATIVE_YIELD_ON_PROCESSES' in source
    assert re.search(r'ABORTING: CARD=\$CARD is not card 0', source), (
        "the card-1 guard's refusal is gone")
    assert "exit 4" in source


def test_the_guard_runs_BEFORE_the_yield_watch_it_protects():
    """Ordering is the whole point: a check after the watch arms has already lost."""
    source = LAUNCHER.read_text()
    guard = source.index('if [[ "$CARD" != "0" ]]; then')
    watch = source.index("STEP 2: yield watch")
    assert guard < watch, "the card guard must precede the yield watch, not follow it"


def test_process_yield_actually_reaches_the_yielder():
    """Refusing to launch is half; the other half is passing the flag when it does launch."""
    source = LAUNCHER.read_text()
    assert "YIELD_PROCS=(--yield-on-processes)" in source
    assert 'yield_gpu_to_neighbour.py' in source
    yielder = source.index("yield_gpu_to_neighbour.py")
    tail = source[yielder:yielder + 400]
    assert 'YIELD_PROCS[@]' in tail, "the flag array is built but never passed to the yielder"


def test_the_battery_still_only_uses_card_zero():
    """If the campaign ever moves off card 0 it must do so deliberately, not by drift."""
    chain = (ROOT / "datasphere" / "native" / "battery-chain.sh").read_text()
    cards = set(re.findall(r"\bCARD=(\d+)", chain))
    assert cards == {"0"}, f"battery-chain.sh now targets cards {sorted(cards)}"


# --- preflight must refuse a card someone else is already on -------------------------------------
# [Claude 2026-09-14] Measured on the live host: card 0 held a colleague's job at 5173 MiB / 42%
# util with 27,322 MiB free, and the preflight printed "OK to start" and exited 0. The memory floor
# saw 27 GB of room; the util test only fires above --max-util 50. Both thresholds are about how
# BUSY a card is, and neither answers whether it is OURS. At preflight our cell has not started, so
# any compute process on the card belongs to someone else -- which needs no ownership test at all.

def _headroom():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_headroom", ROOT / "scripts" / "watch_gpu_headroom.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(**kw):
    base = dict(index=0, used_mib=5173, free_mib=27322, utilization_pct=42, compute_processes=1)
    base.update(kw)
    return base


def test_preflight_refuses_a_card_with_a_foreign_process(monkeypatch):
    m = _headroom()
    monkeypatch.setattr(m, "read", lambda device: _row())
    assert m.preflight(0, 4000, 50, require_exclusive=True) == 1


def test_the_same_card_passes_without_the_flag_which_is_the_bug_this_fixes(monkeypatch):
    """Pins the old behaviour so the fix cannot be silently reverted to it."""
    m = _headroom()
    monkeypatch.setattr(m, "read", lambda device: _row())
    assert m.preflight(0, 4000, 50) == 0


def test_an_empty_card_still_passes_with_the_flag(monkeypatch):
    """The check must not refuse everything -- that would be a gate nobody can satisfy."""
    m = _headroom()
    monkeypatch.setattr(m, "read", lambda device: _row(compute_processes=0, used_mib=0,
                                                       free_mib=32768, utilization_pct=0))
    assert m.preflight(0, 4000, 50, require_exclusive=True) == 0


def test_the_launcher_passes_require_exclusive_by_default():
    source = LAUNCHER.read_text()
    assert "EXCLUSIVE=(--require-exclusive)" in source
    assert "NATIVE_ALLOW_SHARED_CARD" in source, "the deliberate override must exist"
    pre = source.index("watch_gpu_headroom.py --preflight")
    assert "EXCLUSIVE[@]" in source[pre:pre + 300], "the flag is built but never reaches preflight"


def test_the_neighbour_yield_is_in_the_repo_and_wired():
    """It lived only on the host, unversioned and referenced by nothing."""
    script = ROOT / "datasphere" / "native" / "neighbour-yield.sh"
    assert script.is_file(), "neighbour-yield.sh is not in the repo"
    assert subprocess.run(["bash", "-n", str(script)]).returncode == 0
    source = LAUNCHER.read_text()
    assert "NEIGHBOUR_YIELD=" in source and "$REPO/datasphere/native/neighbour-yield.sh" in source
    assert "nohup bash \"$NEIGHBOUR_YIELD\"" in source, "declared but never started"
