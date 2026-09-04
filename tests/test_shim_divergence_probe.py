"""The arithmetic behind C41's "bounded, not growing" claim.

`scripts/probe_shim_divergence.py` reports a *growth ratio* -- the relative loss difference at the
last step over the first -- and C41 reads a growth of 1x as "an MPS run is a noisy copy of a CPU
run, so ordinal claims survive". Everything that claim carries rests on that one ratio being
computed and interpreted correctly, and the script had no test.

This does not re-run the probe: that needs torch and MPS and takes real time. It pins `report()`,
which is where the ratio is formed, against traces whose correct answer is known by construction
-- including the two cases that would silently break the reading:

- a **flat** divergence must report growth ~1 (the "noisy copy" verdict), and
- a **compounding** divergence must report growth >> 1 (the "different trajectory" verdict).

If those two ever return the same number, C41 stops being evidence of anything.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

torch = pytest.importorskip("torch")
from scripts.probe_shim_divergence import report  # noqa: E402


def params(*vals):
    return torch.tensor(vals, dtype=torch.float32)


class TestGrowthRatioSeparatesTheTwoVerdicts:
    def test_a_constant_relative_offset_reports_growth_of_one(self):
        """The bounded case: every step differs by the same relative amount."""
        a = np.array([1.0, 0.5, 0.25, 0.125])
        b = a * (1 + 1e-5)
        first, last, _ = report("flat", params(1.0), params(1.0), a, b)
        assert first == pytest.approx(1e-5, rel=1e-3)
        assert last / first == pytest.approx(1.0, rel=1e-3), (
            "a constant relative offset must not read as growth, or every run looks divergent")

    def test_a_compounding_divergence_reports_large_growth(self):
        """The unbounded case: this must NOT be reportable as 1x."""
        a = np.array([1.0, 1.0, 1.0, 1.0, 1.0])
        b = a * np.array([1 + 1e-6, 1 + 1e-5, 1 + 1e-4, 1 + 1e-3, 1 + 1e-2])
        first, last, _ = report("growing", params(1.0), params(1.0), a, b)
        assert last / first > 1e3, (
            "a divergence compounding by four orders of magnitude read as bounded; C41's "
            "verdict would be produced by a design that cannot see the failure it rules out")

    def test_identical_traces_do_not_divide_by_zero(self):
        a = np.array([1.0, 2.0, 3.0])
        first, last, pd = report("identical", params(1.0, 2.0), params(1.0, 2.0), a, a.copy())
        assert first == 0.0 and last == 0.0
        assert pd == 0.0


class TestParameterDistanceIsRelative:
    def test_scale_free(self):
        """Reported as a relative L2, so a big model is not automatically 'more divergent'."""
        small = report("s", params(1.0, 1.0), params(1.0 + 1e-3, 1.0), np.array([1.0]),
                       np.array([1.0]))[2]
        big = report("b", params(1000.0, 1000.0), params(1000.0 + 1.0, 1000.0),
                     np.array([1.0]), np.array([1.0]))[2]
        # 1e-3, not 1e-6: the norms are accumulated in float32, so agreement is limited by
        # the dtype (observed 7.0714e-4 vs 7.0711e-4, a relative gap of ~5e-5). Asserting
        # tighter than the arithmetic can deliver produces a test that fails for being right.
        assert small == pytest.approx(big, rel=1e-3)

    def test_a_real_difference_is_not_reported_as_zero(self):
        pd = report("d", params(1.0, 0.0), params(0.0, 1.0), np.array([1.0]), np.array([1.0]))[2]
        assert pd > 0.5


def test_the_probe_declares_what_it_did_not_measure():
    """C41 is bounded by scope, not just by numbers. The script must keep saying so: it uses a
    representative conv+MLP update, not any baseline's real loss, and says nothing about CUDA."""
    src = (ROOT / "scripts" / "probe_shim_divergence.py").read_text(errors="replace")
    assert "CUDA" in src and "not any baseline's exact loss" in src, (
        "the probe's stated limits were edited away; C41 would then read as a stronger claim "
        "than the measurement supports")
