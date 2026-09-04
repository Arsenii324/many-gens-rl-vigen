"""`TIME_LIMIT_HANDLING` must describe the runs, and the hash must separate them.

C1: Door and Lift have no early termination, so every episode ends by time limit and this choice
applies on every episode of every run. Three baselines bootstrap through it; nine zero the
bootstrap. `Protocol.time_limit_handling` was a single string, `"truncate_with_bootstrap"`,
**inside the hash**, and it was true of three — so the hash certified a convention nine baselines
do not have, and two runs differing in it hashed identically. That is the precise failure a
comparability hash exists to prevent, and it was independent of any claim decision.

Closed 2026-08-19 by the option C1's own note called "the consistent one": split per baseline, the
way `OBSERVATION_GEOMETRY` splits frame stacking.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rlgen.protocol import TIME_LIMIT_HANDLING, Protocol  # noqa: E402


def test_every_baseline_is_covered_and_nothing_else_is():
    from rlgen.registry import BASELINES
    real = {n for n, s in BASELINES.items()
            if s.status == "implemented" and n != "random" and not n.startswith("__")}
    assert set(TIME_LIMIT_HANDLING) == real, (
        "the map and the registry disagree about which baselines exist; a baseline with no entry "
        "silently inherits the sentinel and its runs stop being distinguishable")


def test_the_split_is_three_and_nine():
    vals = list(TIME_LIMIT_HANDLING.values())
    assert vals.count("bootstrap") == 3 and vals.count("terminal") == 9


class TestTheMapDescribesTheCodeNotABelief:
    """Read the sites. A map that drifts from the clones is worse than no map."""

    def test_the_bootstrappers_zero_done_at_the_limit(self):
        t = (ROOT / "runnable/dmc_gb/src/train.py").read_text(errors="replace")
        assert "done_bool = 0 if episode_step + 1 == env._max_episode_steps" in t, (
            "rad/soda no longer bootstrap through the time limit; TIME_LIMIT_HANDLING is stale")

    def test_the_others_zero_the_discount_at_done(self):
        t = (ROOT / "RL-ViGen-upstream/wrappers/robo_wrapper.py").read_text(errors="replace")
        assert "discount = 0.0" in t, (
            "the RL-ViGen five no longer treat the time limit as terminal; the 3/9 split moved")


class TestTheHashNowSeparatesWhatItCertifies:
    def test_two_baselines_with_different_conventions_do_not_hash_alike(self):
        assert Protocol(name="drq").hash() != Protocol(name="rad").hash(), (
            "the whole point of the fix: a terminal-treatment run and a bootstrap run must not "
            "carry the same comparability hash")

    def test_two_baselines_sharing_a_convention_still_differ_only_by_name(self):
        a, b = Protocol(name="drqv2"), Protocol(name="svea")
        assert a.time_limit_handling == b.time_limit_handling == "terminal"

    def test_the_canonical_protocol_asserts_nothing_about_any_baseline(self):
        """It used to claim `truncate_with_bootstrap` for all twelve. That was the false part."""
        assert Protocol().time_limit_handling == "per-baseline"
        assert Protocol().name not in TIME_LIMIT_HANDLING

    def test_an_explicit_value_is_not_overwritten(self):
        assert Protocol(name="drq", time_limit_handling="bootstrap").time_limit_handling == "bootstrap"

    def test_the_field_is_still_inside_the_hash(self):
        """If it ever leaves the hash, the separation above becomes decorative."""
        p = Protocol(name="drq")
        import dataclasses
        other = dataclasses.replace(p, time_limit_handling="bootstrap")
        assert p.hash() != other.hash()
