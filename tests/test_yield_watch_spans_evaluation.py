"""The yield poller and the cell-active marker must outlive TRAINING, because the card does.

## The gap

`run_probe.sh` armed an in-container sentinel poller and touched a `cell-active` marker when
training began, and released BOTH when training returned -- at lines 239 and 248, inside the
training helper's cleanup. Evaluation runs afterwards, at `run_one_cell`'s lines ~525/528, on
`cuda`.

Measured on the idaac 600k cell: **4.95 h training, 10.12 h evaluation.** So both instruments stood
down for **two thirds of the cell's GPU life**:

- the poller is what makes a yield request actionable -- without it the cell cannot respond;
- the marker is what keeps the HOST-side exclusivity and yield watches armed, because
  `launch-card-cell.sh` passes them `--stop-when-inactive`.

A neighbour arriving during those hours would have found us resident on the card and unresponsive,
which is the exact failure `yield_gpu_to_neighbour.py` exists to prevent: *"We yield; they never
fail."*

The marker's own comment already said the right rule -- *"Marker present means a cell is on the
card"* -- and during evaluation a cell is on the card. The placement contradicted the comment.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER = ROOT / "datasphere" / "native" / "run_probe.sh"


def source() -> str:
    return RUNNER.read_text()


def _line_of(text: str, needle: str) -> int:
    for number, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return number
    raise AssertionError(f"not found: {needle}")


def test_the_marker_is_not_cleared_before_evaluation_runs():
    text = source()
    cleared = _line_of(text, 'echo "=== NATIVE_CELL_ACTIVE_MARKER_CLEARED ===" >&2')
    endpoint = _line_of(text, 'run_endpoint_eval "$cell_out"')
    assert cleared > endpoint, (
        f"the cell-active marker is retracted at line {cleared}, before run_endpoint_eval at line "
        f"{endpoint}. That stands the host-side yield and exclusivity watches down for the whole "
        f"evaluation phase, which is 2.04x the training it follows."
    )


def test_the_poller_is_not_killed_before_evaluation_runs():
    text = source()
    endpoint = _line_of(text, 'run_endpoint_eval "$cell_out"')
    for number, line in enumerate(text.splitlines(), 1):
        if re.search(r'kill "\$(yield_pid|NATIVE_YIELD_POLLER_PID)"', line) and number < endpoint:
            raise AssertionError(
                f"the yield poller is killed at line {number}, before evaluation at {endpoint}; "
                f"the cell cannot act on a yield request during evaluation"
            )


def test_retraction_exists_and_is_idempotent():
    text = source()
    assert "retract_cell_from_card()" in text
    # guarded removal, so a second call is not an error
    block = text[text.index("retract_cell_from_card()"):]
    block = block[:block.index("\n}\n") + 3]
    assert '[[ -e "$_marker" ]]' in block, block
    assert 'NATIVE_YIELD_POLLER_PID=""' in block, block


def test_retraction_runs_on_the_failure_path_too():
    """A failed cell that leaves the marker up keeps the watches armed against a free card."""
    text = source()
    failed = _line_of(text, 'echo "=== NATIVE_CELL_FAILED $(cell_id "$spec") ===" >&2')
    after = text.splitlines()[failed:failed + 8]
    assert any("retract_cell_from_card" in line for line in after), (
        "nothing retracts the marker after a cell fails:\n" + "\n".join(after)
    )
