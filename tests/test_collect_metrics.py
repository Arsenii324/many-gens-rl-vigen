"""The log parsers, pinned against the exact line shapes the baselines emit.

`scripts/collect_metrics.py` already guards its worst failure at runtime: a log that exists while
the parser matches nothing looks identical to a baseline that logged nothing, so `--self-test`
exits non-zero on it. But that guard only fires when a real log is present, which on a fresh
checkout it is not. These tests pin the formats directly, so a parser that stops matching fails
in the fast loop rather than silently producing an empty comparison table months later.

Fixtures are the format strings the baselines actually use, copied from their source rather than
from a remembered example -- a parser test written against an imagined line proves the parser
matches the imagination.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from scripts.collect_metrics import parse_ibac_sni  # noqa: E402


# runnable/ibac_sni/torch_rl/scripts/train.py -- the `U <update> | F <frames> | ...` shape
IBAC_TRAIN = "U 20 | F 001280 | FPS 100 | D 12 | rR:\u03bc\u03c3mM 3.79 0.5 3.0 4.5 | SR 0.000"
# runnable/ibac_sni/torch_rl/scripts/evaluate.py -- no update counter, FPS present, plain R:
IBAC_EVAL = ("F 5000 | FPS 120 | D 41 | R:\u03bc\u03c3mM 3.79 0.50 3.00 4.50 "
             "| F:\u03bc\u03c3mM 500.0 0.0 500 500 | SR 0.1000")


class TestIbacSni:
    """Two line shapes that are two different measurements, and must not be conflated."""

    def test_training_line_parses(self):
        (r,) = parse_ibac_sni("ibac_sni", IBAC_TRAIN)
        assert (r.frames, r.episode_reward, r.success_rate) == (1280, 3.79, 0.0)

    def test_held_out_eval_line_parses(self):
        """Added 2026-08-17 together with the `SR` field on that line.

        Before it, `evaluate.py` reported return only while its own `train.py` reported
        success_rate -- so the one held-out number ibac_sni produced was not the quantity the
        other eleven baselines report.
        """
        (r,) = parse_ibac_sni("ibac_sni", IBAC_EVAL)
        assert (r.frames, r.episode_reward, r.success_rate) == (5000, 3.79, 0.1)

    def test_the_two_are_labelled_differently(self):
        """Conflating a training-regime number with a held-out one is the error this whole
        comparison exists to avoid, so it must be visible in the regime column."""
        recs = parse_ibac_sni("ibac_sni", IBAC_TRAIN + "\n" + IBAC_EVAL)
        assert [r.regime for r in recs] == ["unknown", "eval-script"]

    def test_the_label_does_not_overclaim_which_regime(self):
        """`eval-script` means 'produced by the held-out evaluator', NOT 'eval-easy'.

        Which regime it ran in comes from RLVIGEN_EVAL_MODE at launch and appears nowhere in the
        line. A label that named a specific regime would be inventing it.
        """
        (r,) = parse_ibac_sni("ibac_sni", IBAC_EVAL)
        assert r.regime == "eval-script"
        assert "easy" not in r.regime and "hard" not in r.regime

    def test_a_line_without_SR_yields_no_success_rate_rather_than_zero(self):
        """None, not 0.0. A missing measurement and a measured zero must not look alike -- that
        ambiguity is the whole reason tests/test_success_metric.py exists."""
        (r,) = parse_ibac_sni("ibac_sni", IBAC_TRAIN.rsplit("|", 1)[0].strip())
        assert r.success_rate is None

    def test_unrelated_lines_are_ignored(self):
        assert parse_ibac_sni("ibac_sni", "Model successfully loaded\n\nCUDA available: True") == []
