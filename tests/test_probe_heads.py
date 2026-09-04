"""`probe_heads` must not report an all-clear when it checked nothing.

The probe builds each authored continuous head in its own subprocess and compares the entropy of
a 7-dim diagonal Gaussian against sigma = 1. It supports the audit's claim that all four authored
heads share the initialisation of the one head copied verbatim from ikostrikov.

Its defect was structural rather than numerical: `return 1 if bad else 0`, where `bad` counts
only heads that were BUILT and found wrong. A run where every head failed to import returned 0
and printed the all-clear, directly above its own warning that a skip is not a pass. These tests
pin the fix, because the failing configuration is one no one runs on purpose — it appears when a
clone moves or a dependency breaks, which is exactly when the status is trusted without reading.
"""
from __future__ import annotations

import math
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.probe_heads as ph  # noqa: E402


def test_the_entropy_target_is_the_closed_form_not_a_recorded_number():
    """H = k/2 * log(2*pi*e) for a k-dim diagonal Gaussian at sigma = 1."""
    assert ph.TARGET == pytest.approx(7 * 0.5 * math.log(2 * math.pi * math.e))
    assert ph.TARGET == pytest.approx(9.93257, abs=1e-5)


def test_there_are_heads_to_check():
    """A registry that emptied would make every run vacuously clean."""
    assert len(ph.HEADS) >= 4, f"only {len(ph.HEADS)} heads registered"
    for name, spec in ph.HEADS.items():
        assert spec.get("code") and spec.get("path"), name


class TestSkipIsNotAPass:
    """The exit code must agree with the prose the script prints."""

    def _run(self, monkeypatch, stdout):
        class R:
            def __init__(self):
                self.stdout, self.stderr, self.returncode = stdout, "", 0
        monkeypatch.setattr(ph.subprocess, "run", lambda *a, **k: R())
        return ph.main()

    def test_every_head_skipping_is_a_failure(self, monkeypatch, capsys):
        code = self._run(monkeypatch, "no entropy line here\n")
        out = capsys.readouterr().out
        assert code == 1, "all heads skipped but the probe reported success"
        assert "NOTHING WAS CHECKED" in out
        # The all-clear sentence must not appear at all -- it is what made the old exit code
        # readable as success. (An `or True` crept into this assertion on the first writing,
        # which would have made it pass on any output whatsoever.)
        assert "constructible head(s) initialise" not in out

    def test_all_heads_reporting_the_target_is_a_pass(self, monkeypatch, capsys):
        code = self._run(monkeypatch, f"ENTROPY {ph.TARGET}\nLOGSTD 0.0\n")
        out = capsys.readouterr().out
        assert code == 0
        assert "NOTHING WAS CHECKED" not in out
        assert f"All {len(ph.HEADS)} constructible head(s)" in out

    def test_a_wrong_entropy_fails(self, monkeypatch, capsys):
        """Guards the comparison itself: sigma != 1 must not pass."""
        code = self._run(monkeypatch, "ENTROPY 5.0\nLOGSTD -1.0\n")
        assert code == 1
        assert "do NOT initialise to sigma = 1" in capsys.readouterr().out

    def test_the_tolerance_is_tight_enough_to_notice_a_real_shift(self, monkeypatch, capsys):
        """log_std = 0.01 moves H by 7*0.01 = 0.07, far outside 1e-4. A loose tolerance would
        let a head drift while still reporting OK."""
        code = self._run(monkeypatch, f"ENTROPY {ph.TARGET + 0.07}\nLOGSTD 0.01\n")
        assert code == 1, "a 0.07 shift in entropy was accepted as sigma = 1"
