"""The metric definitions, pinned by their properties rather than by golden numbers.

A golden number tells you a function changed. A property tells you *what broke*. So each test
below states the property that makes the metric the right choice over the obvious alternative --
which is also the reason it is in `scripts/metrics.py` at all.

The one place a literal is used is `diag_gaussian_entropy`, because there the literal IS the
property: 7 x 0.5*log(2*pi*e) = 9.9326 is what a correctly built 7-dim unit-Gaussian head must
report at initialisation, and it is the value all four authored heads were checked against by
hand in `docs/AUDIT-2026-08-17.html`.
"""
from __future__ import annotations

import math
import pathlib
import sys

import numpy as np
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from scripts.metrics import (action_saturation_frac, approx_kl, bootstrap_ci,  # noqa: E402
                             clip_fraction, diag_gaussian_entropy, effective_sample_size,
                             explained_variance, histogram_tv_distance, interframe_absdiff, iqm,
                             target_network_divergence, wilson_interval)


class TestWilson:
    """The reason Wilson is used instead of p +- z*sqrt(p(1-p)/n)."""

    def test_zero_successes_still_has_width(self):
        """The normal approximation gives width ZERO at p=0, which reads as certainty.

        Every success rate this project currently reports is 0.000. If the interval around them
        were also zero-width, the reports would claim to have proven the policies never succeed,
        from ten episodes.
        """
        lo, hi = wilson_interval(0, 10)
        assert lo == 0.0
        assert hi > 0.2, f"width {hi:.3f} is too small to be honest about n=10"

    def test_never_leaves_the_unit_interval(self):
        for k, n in ((0, 3), (3, 3), (1, 2), (7, 7), (0, 1)):
            lo, hi = wilson_interval(k, n)
            assert 0.0 <= lo <= hi <= 1.0, f"({k}/{n}) -> ({lo}, {hi})"

    def test_more_evidence_narrows_it(self):
        w = [wilson_interval(n // 2, n)[1] - wilson_interval(n // 2, n)[0]
             for n in (10, 100, 1000)]
        assert w[0] > w[1] > w[2]

    def test_no_episodes_is_total_ignorance(self):
        assert wilson_interval(0, 0) == (0.0, 1.0)

    def test_rejects_impossible_counts(self):
        with pytest.raises(ValueError):
            wilson_interval(11, 10)


class TestReturnStatistics:
    def test_iqm_discards_the_tails(self):
        assert abs(iqm([0, 1, 1, 1, 1, 100]) - 1.0) < 1e-9

    def test_bootstrap_of_a_constant_has_no_width(self):
        lo, hi = bootstrap_ci([2.5] * 25)
        assert abs(hi - lo) < 1e-9

    def test_bootstrap_is_reproducible(self):
        assert bootstrap_ci(range(30), seed=7) == bootstrap_ci(range(30), seed=7)


class TestObservationGeometry:
    """`interframe_absdiff` is the measurement behind the frame-stack finding."""

    def test_identical_frames_carry_no_motion(self):
        still = np.tile(np.full((3, 8, 8), 120, np.uint8), (3, 1, 1))
        assert interframe_absdiff(still, 3) == 0.0

    def test_differing_frames_carry_motion(self):
        moving = np.concatenate([np.full((3, 8, 8), v, np.uint8) for v in (0, 128, 255)])
        assert interframe_absdiff(moving, 3) > 0.4

    def test_single_frame_is_not_measurable(self):
        """Returns 0.0, and the caller must not read that as 'no motion'.

        This is the whole point of the 8/4 split: four baselines receive one frame, so the
        quantity does not exist for them. `probe_geometry.py` prints the frame count beside the
        value so the two readings cannot be confused.
        """
        assert interframe_absdiff(np.zeros((3, 8, 8), np.uint8), 1) == 0.0

    def test_scale_invariant_so_baselines_are_comparable(self):
        """Baselines normalise pixels differently ([0,1] vs [-0.5,0.5] vs raw); the metric must
        not reward one of them for its input convention."""
        moving = np.concatenate([np.full((3, 8, 8), v, np.uint8) for v in (0, 128, 255)])
        assert abs(interframe_absdiff(moving, 3) - interframe_absdiff(moving / 255.0, 3)) < 1e-9

    def test_channels_last_agrees_with_channels_first(self):
        m = np.concatenate([np.full((3, 4, 4), v, np.uint8) for v in (0, 100, 200)])
        assert abs(interframe_absdiff(m, 3, channels_first=True)
                   - interframe_absdiff(np.moveaxis(m, 0, -1), 3, channels_first=False)) < 1e-9


class TestRegimeSeparation:
    """`histogram_tv_distance` decides whether the eval regimes differ from train at all."""

    def test_identical_sets_are_zero(self):
        rng = np.random.default_rng(0)
        x = rng.integers(0, 255, size=(4, 3, 16, 16), dtype=np.uint8)
        assert histogram_tv_distance(x, x) == 0.0

    def test_disjoint_intensities_are_one(self):
        dark = np.zeros((4, 3, 16, 16), np.uint8)
        bright = np.full((4, 3, 16, 16), 255, np.uint8)
        assert abs(histogram_tv_distance(dark, bright) - 1.0) < 1e-9

    def test_it_is_bounded(self):
        rng = np.random.default_rng(1)
        for _ in range(5):
            a = rng.integers(0, 255, size=(3, 3, 8, 8), dtype=np.uint8)
            b = rng.integers(0, 255, size=(3, 3, 8, 8), dtype=np.uint8)
            assert 0.0 <= histogram_tv_distance(a, b) <= 1.0

    def test_a_bigger_shift_reads_bigger(self):
        base = np.full((4, 3, 16, 16), 100, np.uint8)
        near = np.full((4, 3, 16, 16), 110, np.uint8)
        far = np.full((4, 3, 16, 16), 200, np.uint8)
        assert histogram_tv_distance(base, far) >= histogram_tv_distance(base, near)

    def test_channels_are_not_collapsed(self):
        """A colour randomisation moves channels differently; greyscaling first would hide it.

        Two sets with identical *overall* intensity distributions but swapped channels must not
        read as identical.
        """
        a = np.zeros((2, 3, 8, 8), np.uint8); a[:, 0] = 255
        b = np.zeros((2, 3, 8, 8), np.uint8); b[:, 2] = 255
        assert histogram_tv_distance(a, b) > 0.5

    def test_mismatched_channel_counts_are_an_error(self):
        with pytest.raises(ValueError):
            histogram_tv_distance(np.zeros((2, 3, 8, 8)), np.zeros((2, 4, 8, 8)))


class TestActionGeometry:
    def test_interior_actions_are_unsaturated(self):
        assert action_saturation_frac([[0.0, 0.5, -0.5]]) == 0.0

    def test_counts_components_not_actions(self):
        assert abs(action_saturation_frac([[1.0, 0.0, 0.0, 0.0]]) - 0.25) < 1e-9

    def test_matches_the_closed_form_for_a_unit_gaussian(self):
        """The number the audit reports for ppg / idaac / ibac_sni / ctrl at initialisation.

        P(|z| >= 1) = 2(1 - Phi(1)) = 0.3173. If this drifts, either the metric or the claim
        that ~a third of action components are decided by the environment's clip is wrong.
        """
        rng = np.random.default_rng(0)
        empirical = action_saturation_frac(rng.normal(0, 1, size=(200_000, 7)))
        closed = 2 * (1 - 0.5 * (1 + math.erf(1 / math.sqrt(2))))
        assert abs(empirical - closed) < 0.005, f"{empirical:.4f} vs {closed:.4f}"

    def test_squashed_policies_do_not_saturate(self):
        rng = np.random.default_rng(0)
        assert action_saturation_frac(np.tanh(rng.normal(0, 1, size=(50_000, 7)))) < 0.001


class TestOnPolicyFamily:
    """The eight PPO-family baselines. Names are TorchRL's, so the numbers are comparable."""

    def test_perfect_critic_explains_everything(self):
        y = [1.0, 2.0, 3.0, 4.0]
        assert abs(explained_variance(y, y) - 1.0) < 1e-12

    def test_mean_predictor_explains_nothing(self):
        y = [1.0, 2.0, 3.0, 4.0]
        assert abs(explained_variance(y, [2.5] * 4)) < 1e-12

    def test_a_critic_worse_than_the_mean_goes_negative(self):
        """The value actually worth watching: below 0, every advantage it produces is noise."""
        assert explained_variance([1.0, 2.0, 3.0, 4.0], [4.0, 3.0, 2.0, 1.0]) < 0

    def test_constant_returns_are_undefined_not_zero(self):
        """nan, not 0.0. 0.0 would read as 'explains nothing', a different and wrong claim.

        Common on a sparse manipulation reward, where a batch of all-zero returns is routine.
        """
        assert math.isnan(explained_variance([2.0] * 5, [1.0, 2.0, 3.0, 2.0, 2.0]))

    def test_clip_fraction_counts_only_what_left_the_band(self):
        # ratios 1.0, 1.0, e^0.5=1.65, e^-0.5=0.61 -> two outside [0.8, 1.2]
        assert abs(clip_fraction([0.0, 0.0, 0.5, -0.5], clip_eps=0.2) - 0.5) < 1e-12

    def test_an_unmoved_policy_clips_nothing(self):
        assert clip_fraction(np.zeros(100)) == 0.0

    def test_k3_is_never_negative_but_k1_can_be(self):
        """The whole reason k3 is the default rather than deferring to TorchRL's k1-only value.

        A KL that prints a negative number is unusable as an early-stopping trigger, and invites
        someone to 'fix' the sign. Constructed so k1 is negative on this sample.
        """
        lr = np.array([0.3, 0.4, 0.5])          # log r > 0 everywhere -> k1 = -mean(lr) < 0
        assert approx_kl(lr, "k1") < 0
        assert approx_kl(lr, "k3") > 0

    def test_all_estimators_vanish_for_an_identical_policy(self):
        for est in ("k1", "k2", "k3"):
            assert abs(approx_kl(np.zeros(50), est)) < 1e-12, est

    def test_the_default_estimator_is_k3(self):
        """Every other test here passes `estimator` explicitly, so nothing constrained the
        DEFAULT -- a change of default would have shipped silently.

        Found by mutation testing, not by review: `mutants/catalogue.py` M24 flips the default to
        k1 and the whole suite stayed green. That is what a survivor is for.
        """
        lr = np.array([0.3, 0.4, 0.5])          # k1 is negative here, k3 is not
        assert approx_kl(lr) == approx_kl(lr, "k3")
        assert approx_kl(lr) > 0, "the default must be an estimator that cannot go negative"

    def test_k3_matches_its_closed_form(self):
        lr = np.array([0.1, -0.2, 0.35])
        assert abs(approx_kl(lr, "k3") - float((np.exp(lr) - 1 - lr).mean())) < 1e-12

    def test_unknown_estimator_is_rejected(self):
        with pytest.raises(ValueError):
            approx_kl([0.1], "k9")

    def test_equal_weights_give_full_effective_sample_size(self):
        assert abs(effective_sample_size(np.zeros(64)) - 1.0) < 1e-12

    def test_one_dominant_weight_collapses_it(self):
        """A batch where one sample carries the update should not look like a full batch."""
        lr = np.concatenate([[20.0], np.zeros(99)])
        assert effective_sample_size(lr) < 0.02

    def test_ess_is_invariant_to_a_constant_shift(self):
        """Importance weights are only defined up to scale, so ESS must not depend on it."""
        lr = np.array([0.1, -0.4, 0.7, 0.0])
        assert abs(effective_sample_size(lr) - effective_sample_size(lr + 5.0)) < 1e-9


class TestOffPolicyFamily:
    """The DrQv2 five and SAC three. `target_network_divergence` is measured nowhere in TorchRL."""

    def test_a_freshly_copied_target_has_not_diverged(self):
        w = np.array([1.0, -2.0, 3.0])
        assert target_network_divergence(w, w) == 0.0

    def test_divergence_is_relative_so_it_compares_across_networks(self):
        small = target_network_divergence(np.array([1.0, 1.0]), np.array([1.1, 1.1]))
        big = target_network_divergence(np.array([100.0, 100.0]), np.array([110.0, 110.0]))
        assert abs(small - big) < 1e-9

    def test_it_accepts_a_list_of_per_layer_arrays(self):
        """Callers hold parameters per layer; making them flatten first invites a wrong order."""
        o = [np.array([1.0, 2.0]), np.array([[3.0, 4.0]])]
        t = [np.array([1.0, 2.0]), np.array([[3.0, 4.0]])]
        assert target_network_divergence(o, t) == 0.0

    def test_mismatched_shapes_are_an_error_not_a_number(self):
        with pytest.raises(ValueError):
            target_network_divergence(np.zeros(4), np.zeros(5))

    def test_a_larger_gap_reads_larger(self):
        o = np.ones(10)
        assert (target_network_divergence(o, o + 0.5) > target_network_divergence(o, o + 0.1))


class TestHeadInitialisation:
    def test_unit_gaussian_entropy_is_the_value_the_heads_were_checked_against(self):
        assert abs(diag_gaussian_entropy(np.zeros(7)) - 9.93257) < 1e-4

    def test_entropy_increases_with_sigma(self):
        assert diag_gaussian_entropy(np.full(7, 0.5)) > diag_gaussian_entropy(np.zeros(7))

    def test_scalar_log_std_broadcasts_to_the_action_dim(self):
        assert abs(diag_gaussian_entropy([0.0], dim=7)
                   - diag_gaussian_entropy(np.zeros(7))) < 1e-12
