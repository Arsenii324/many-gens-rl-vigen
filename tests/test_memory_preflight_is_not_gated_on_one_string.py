"""The memory preflight must not be reachable-or-not by a single literal profile name.

`family.py check-memory` is the ONLY memory preflight `run_probe.sh` has. It used to be called
under `if [[ "${NATIVE_HOST_PROFILE:-}" == "v100" ]]`, and `require_production_configuration` only
requires that a profile be *named*, never that the name match the hardware. So
`NATIVE_HOST_PROFILE=datasphere FRAMES=600000` on the production host passed every refusal and ran
with no memory preflight at all -- the configuration that refusal's own comment calls "honest and
wrong". `family.py` records the price: ctrl certified for `gt4.1` that way and SIGKILLed at
11.07 GiB RSS, job `bt1lhobnsq5lq4766np6`, hours into the cell.

This test EXECUTES the real bytes of that block rather than grepping for them. A grep test would
assert that the file says what we wrote, which is the failure mode this project keeps finding in
its own instruments: a check that agrees with our own code and with nothing outside it. Slicing
the block out and running it under bash means the truth table below is a property of the shipped
script, not of a string we also control.
"""
from __future__ import annotations

import pathlib
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROBE = ROOT / "datasphere" / "native" / "run_probe.sh"

START = 'case "${NATIVE_HOST_PROFILE:-datasphere}" in'
# [Claude 2026-09-08] END moved from "python3 -m pip install --upgrade pip" to the marker that now
# immediately follows the preflight. The prebuilt-environment block was added between the two, and
# it OPENS an `if` that closes further down -- so the extracted fragment ended mid-conditional and
# every case here failed with exit 2 for a reason that had nothing to do with memory preflighting.
# The block under test is unchanged; only the boundary moved to stay adjacent to it, which is what
# this file's own docstring asks a future editor to do rather than delete the test.
END = "# [Claude 2026-09-08] PREBUILT ENVIRONMENT."


def _block() -> str:
    text = PROBE.read_text()
    assert START in text, (
        "run_probe.sh no longer contains the profile-to-tier case block. If the memory preflight "
        "moved, move this test with it -- do not delete it. The hole it closes is that "
        "check-memory can be skipped entirely for a profile name nobody mapped.")
    body = text[text.index(START):text.index(END)]
    # Replace the real tool call with a marker: this test is about REACHABILITY, not about what
    # check-memory then concludes, and running family.py here would make it slow and coupled.
    return body.replace('python3 "$FAMILY_TOOL" check-memory --cells "$cells" --tier "$memory_tier"',
                        'echo "RAN:$memory_tier"')


def _run(profile: str, frames: str, tier: str = "") -> tuple[int, str]:
    script = "set -uo pipefail\ncells=drqv2:1\n" + _block()
    proc = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, timeout=60,
        env={"PATH": "/usr/bin:/bin", "NATIVE_HOST_PROFILE": profile, "FRAMES": frames,
             "NATIVE_MEMORY_TIER": tier})
    return proc.returncode, proc.stdout + proc.stderr


def test_v100_at_production_scale_runs_the_preflight():
    code, out = _run("v100", "600000")
    assert code == 0 and "RAN:v100" in out, out


def test_the_hole_that_existed_now_refuses():
    """profile named but not v100, at production scale: previously skipped in silence."""
    code, out = _run("datasphere", "600000")
    assert code == 3, f"expected exit 3, got {code}: {out}"
    assert "REFUSING" in out and "no memory tier" in out, out
    assert "RAN:" not in out, "the preflight must not be reported as having run"


def test_an_unmapped_profile_name_also_refuses():
    """A typo in the profile name must not silently disable the preflight."""
    code, out = _run("v100-1", "600000")
    assert code == 3, f"a profile nobody mapped must refuse, not skip: {out}"


def test_below_production_scale_it_says_it_did_not_run():
    code, out = _run("datasphere", "10000")
    assert code == 0, out
    assert "did NOT run" in out, (
        "skipping is tolerable below production scale; skipping SILENTLY is not -- an instrument "
        "that could not run must never read as one that ran: " + out)


def test_an_explicit_tier_satisfies_any_profile():
    code, out = _run("datasphere", "600000", tier="gt4i.1")
    assert code == 0 and "RAN:gt4i.1" in out, out


@pytest.mark.parametrize("frames", ["600000", "1000000"])
def test_every_production_budget_is_covered(frames):
    assert _run("datasphere", frames)[0] == 3
