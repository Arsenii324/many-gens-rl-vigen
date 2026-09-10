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
