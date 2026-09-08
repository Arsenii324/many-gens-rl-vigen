"""`RUNNER_CONTRACT` is maintained in `contract.py` and read in `run_probe.sh`. They must agree.

[Claude 2026-09-08] Bumping `contract.py` to 14 without the runner's `--require-runner-contract`
made every payload built afterwards unrunnable, and job bt1tceje08tpvq8cchhj died on it:
"payload was built for runner contract 14 but this runner needs 13". The check itself worked
perfectly -- it refused at the boundary, which is what it is for. The defect was that one number
had two homes and only one was updated.

This project has had that exact shape three times now: SAVE_EVERY vs SAVE_EVERY_FRAMES (three cfgs
validating nothing while reporting SUCCESS), curve_eval_episodes declared in two places with
different values, and this. The pattern is worth a test rather than a third recurrence.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "datasphere" / "native"))

import contract  # noqa: E402


def test_the_runner_requires_exactly_the_contract_the_builder_stamps():
    text = (ROOT / "datasphere" / "native" / "run_probe.sh").read_text()
    required = re.findall(r"--require-runner-contract\s+(\d+)", text)
    assert required, "run_probe.sh no longer pins a runner contract at all"
    mismatched = sorted({int(v) for v in required} - {contract.RUNNER_CONTRACT})
    assert not mismatched, (
        f"run_probe.sh requires contract {mismatched} while contract.py stamps "
        f"{contract.RUNNER_CONTRACT}. Every payload built after the bump is refused at the "
        "boundary -- which is the check working, and the number having two homes failing.")
