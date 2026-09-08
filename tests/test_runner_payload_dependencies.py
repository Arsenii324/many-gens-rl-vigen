"""Every `scripts/*.py` the runner invokes must be a declared payload member.

[Claude 2026-09-08] `run_measured` began launching `scripts/watch_policy_health.py` and the file
was not in `contract.py::BASE_ALLOWED`, so it would simply not exist on the container. The launch
was guarded by `[[ -f ... ]]`, which meant no error and no marker -- the `log_std` alert silently
never starting, while `notes/PRODUCTION-RUNBOOK.md` told the operator it runs on every cell.

That is this project's recurring failure -- an instrument that cannot run reading as one that ran
-- rebuilt inside the instrument written to catch a different instance of it.

`contract.py`'s own note says to bump `RUNNER_CONTRACT` whenever the runner begins to require a
payload member it did not require before, so the runner refuses a stale archive at the boundary
instead of eight minutes into a bootstrap. This test is what makes that note enforceable.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "datasphere" / "native"))

import contract  # noqa: E402

RUNNER = ROOT / "datasphere" / "native" / "run_probe.sh"


def _invoked() -> set[str]:
    """`python3 scripts/<name>.py` anywhere in the runner."""
    return set(re.findall(r"python3\s+(scripts/[\w./-]+\.py)", RUNNER.read_text()))


def test_every_script_the_runner_invokes_is_a_payload_member():
    missing = sorted(s for s in _invoked() if s not in contract.BASE_ALLOWED)
    assert not missing, (
        "the runner invokes these and the payload does not carry them, so on the container they "
        f"are absent: {missing}. Add them to contract.BASE_ALLOWED and bump RUNNER_CONTRACT.")


def test_the_policy_health_watcher_specifically_ships():
    """The regression, named. It is the alert for the failure that survives every other check."""
    assert "scripts/watch_policy_health.py" in contract.BASE_ALLOWED
    assert "scripts/watch_policy_health.py" in _invoked()


def test_the_watcher_launch_is_not_hidden_behind_an_existence_guard():
    """A `-f` guard converts a contract violation the runner refuses into a silent no-op."""
    text = RUNNER.read_text()
    block = text[text.index("POLICY-HEALTH WATCH"):]
    block = block[:block.index("health_pid=\"$!\"")]
    assert "-f scripts/watch_policy_health.py" not in block, (
        "an existence guard here means the watcher silently does not run wherever the file is "
        "absent -- which is exactly the case the payload contract exists to make loud")


def test_the_contract_was_bumped_for_it():
    assert contract.RUNNER_CONTRACT >= 14, (
        "adding a runner dependency without bumping RUNNER_CONTRACT lets a payload built before "
        "it meet a runner that needs it, and the failure surfaces after the bootstrap is paid for")
