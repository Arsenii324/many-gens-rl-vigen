"""`scripts/plan_seed_budget.py` -- C18's arithmetic, and the properties that make it usable.

The output of this script is a number someone will spend GPU-months against, so the failure that
matters is a quiet one: an estimator that returns a plausible CV for input that carries no
information, or an inverse that disagrees with its own forward direction. Both are checked here
against inputs whose answer is known without running anything.

Verified by mutation on 2026-08-19, all three mutants killed: `sqrt(2/n)` -> `sqrt(1/n)` in the
detectable-effect formula, the factor 2 dropped from its inverse, and the paired-runs `sqrt(2)`
dropped from the CV estimator. Each of those misprices a run budget by a large factor while
leaving output that looks entirely reasonable.
"""
from __future__ import annotations

import math
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import plan_seed_budget as B  # noqa: E402


class TestTheEstimator:
    def test_identical_runs_imply_no_spread(self):
        """Two runs that agreed everywhere must not produce a positive CV."""
        pairs = [(f, 100.0, 100.0) for f in (10, 20, 30)]
        assert B.cv_from_pairs(pairs) == 0.0

    def test_a_known_spread_recovers_the_textbook_constant(self):
        """E|A-B| = sigma*sqrt(2)*sqrt(2/pi); a constant 10% gap must invert to that CV."""
        pairs = [(f, 95.0, 105.0) for f in (10, 20, 30)]      # rel diff exactly 0.10
        expected = 0.10 / math.sqrt(2 / math.pi) / math.sqrt(2)
        assert B.cv_from_pairs(pairs) == pytest.approx(expected, rel=1e-12)

    def test_spread_scales_with_disagreement(self):
        small = B.cv_from_pairs([(1, 99.0, 101.0)])
        large = B.cv_from_pairs([(1, 90.0, 110.0)])
        assert large > small > 0


class TestTheBudgetArithmetic:
    def test_more_seeds_resolve_smaller_differences(self):
        cv = 0.17
        vals = [B.detectable(cv, n) for n in (1, 3, 5, 10, 20, 50)]
        assert vals == sorted(vals, reverse=True), "detectable effect must shrink with n"

    def test_it_follows_the_root_n_law_at_a_FIXED_multiplier(self):
        """Quadrupling the seeds must halve the detectable difference; anything else means the
        sqrt(2/n) was mistyped, which no eyeball on the output would catch.

        Pinned at an explicit multiplier since 2026-09-05: `detectable()` now uses a t multiplier
        that DEPENDS on n (df = 2n-2), so the raw law no longer holds end to end -- and must not,
        or the small-n correction would not be doing anything. The sqrt(2/n) term is still exactly
        a root-n law and is what this test exists to protect.
        """
        cv = 0.17
        z = B.Z_80_POWER
        assert B.detectable(cv, 40, z) == pytest.approx(B.detectable(cv, 10, z) / 2, rel=1e-12)

    def test_the_t_correction_binds_at_small_n_and_vanishes_at_large_n(self):
        """The whole point of the 2026-09-05 correction: the normal approximation is optimistic
        exactly where this project plans to sit (n=3), and harmless where it does not."""
        cv = 0.174
        z = B.Z_80_POWER
        at3 = B.detectable(cv, 3)
        assert at3 > B.detectable(cv, 3, z) * 1.25, (
            "the t multiplier must raise the n=3 detectable difference well above the normal "
            "approximation -- if it does not, detectable() is silently still using z")
        assert at3 == pytest.approx(0.527, abs=0.002), (
            "n=3 must resolve ~52.7%; this is the number CONSTRUCTION.md and A28 carry")
        assert B.detectable(cv, 50) == pytest.approx(B.detectable(cv, 50, z), rel=0.01), (
            "at n=50 t and z must agree to within 1% -- disagreement there means the correction "
            "is wrong, not just conservative")

    def test_the_inverse_agrees_with_the_forward_direction(self):
        cv = 0.17
        for d in (0.05, 0.10, 0.20, 0.50):
            n = B.seeds_for(cv, d)
            assert B.detectable(cv, n) <= d + 1e-12, (
                f"seeds_for said {n} seeds resolve {d}, but detectable() disagrees")
            if n > 1:
                assert B.detectable(cv, n - 1) > d, f"{n} seeds is not the minimum for {d}"


def test_the_five_seed_plan_resolves_tens_of_percent_not_units():
    """The load-bearing sentence for C18, kept honest against the shipped data.

    If this ever reads below ~10% the input pairs changed and the plan's premise changed with
    them; that is a result to write down, not a test to relax.
    """
    cv = B.cv_from_pairs(B.C41_PAIRS)
    d5 = B.detectable(cv, 5)
    assert 0.20 < d5 < 0.45, f"five seeds resolve {100*d5:.1f}% -- restate C18 before editing this"
    assert B.seeds_for(cv, 0.05) > 100, "a 5% difference must still look expensive"
