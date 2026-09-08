"""A watch that expires before the work it covers must refuse to arm.

[Claude 2026-09-08] From a live near-miss rather than from theory. A cell was launched on the
production host with both card watchers armed for 4500s, chosen by hand from an assumed ~10 minute
bootstrap. The real bootstrap was still downloading 51 minutes in -- the host pulls the torch CUDA
stack at 162-835 kB/s and
`nvidia_cublas_cu12` alone took 14m15s. So the watchers would have stood down at 21:29 and the
cell would have reached the GPU at ~22:25: the entire GPU phase, the only part where exclusivity
and yielding mean anything, would have run with nothing watching it.

Nothing failed. Both instruments would have reported a clean run and exited 0, and the operator
would have believed the card was covered throughout. That is the project's own defect class -- an
instrument that could not run must never read as one that ran -- appearing in the instruments
themselves.

The fix is not a better-chosen number; the next number would be guessed too. It is that the caller
must DECLARE what the watch has to cover, and the instrument refuses when its budget is short. The
declaration is checkable; a mental estimate is not.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
WATCHERS = ("watch_card_exclusivity", "yield_gpu_to_neighbour")


def _run(script: str, max_seconds: str, must_cover: list[str]):
    argv = [sys.executable, str(ROOT / "scripts" / f"{script}.py"), "--device", "0",
            "--max-seconds", max_seconds, *must_cover]
    argv += (["--expect-ours", "1"] if script == "watch_card_exclusivity"
             else ["--sentinel", "/tmp/never-written-by-this-test"])
    return subprocess.run(argv, capture_output=True, text=True, timeout=120)


@pytest.mark.parametrize("script", WATCHERS)
def test_a_budget_shorter_than_the_declared_cover_is_refused(script):
    out = _run(script, "4500", ["--must-cover-seconds", "12600"])
    assert out.returncode == 3, f"armed anyway: rc={out.returncode}\n{out.stdout}{out.stderr}"
    both = out.stdout + out.stderr
    assert "REFUSING TO ARM" in both, both
    # The shortfall must be stated as a number. "Too short" does not tell an operator what to fix.
    assert "8100s before the work does" in both, both


@pytest.mark.parametrize("script", WATCHERS)
def test_no_declaration_means_no_refusal(script):
    """--must-cover-seconds is opt-in; omitting it must not break every existing caller."""
    out = _run(script, "0.05", [])
    assert out.returncode != 3, out.stdout + out.stderr
    assert "REFUSING TO ARM" not in (out.stdout + out.stderr)


@pytest.mark.parametrize("script", WATCHERS)
def test_an_adequate_budget_arms(script):
    out = _run(script, "0.05", ["--must-cover-seconds", "0.01"])
    assert out.returncode != 3, out.stdout + out.stderr
    assert "REFUSING TO ARM" not in (out.stdout + out.stderr)


@pytest.mark.parametrize("script", WATCHERS)
def test_a_short_budget_is_told_apart_from_a_card_it_cannot_read(script):
    """Both are refusals to arm; they need different fixes, so they carry different codes.

    Exit 2 means the instrument cannot see the card. Exit 3 means the operator gave it a budget
    that ends before the work. Collapsing them would send someone hunting for a driver problem
    when the answer is a larger number.
    """
    short = _run(script, "4500", ["--must-cover-seconds", "12600"])
    assert short.returncode == 3
    assert "exit 3" in (short.stdout + short.stderr), (
        "the code must be explained where it is printed, or it is a bare number in a log")


def test_the_refusal_is_not_silent_on_stdout_redirect():
    """`docker run ... >/dev/null` is how these are launched; the refusal must survive it."""
    out = _run("watch_card_exclusivity", "4500", ["--must-cover-seconds", "12600"])
    assert "REFUSING TO ARM" in out.stderr, (
        "the exclusivity refusal goes to stdout, so the documented launch form "
        "`docker run -d ... >/dev/null` would discard it entirely")
