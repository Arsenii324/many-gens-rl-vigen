"""Every per-baseline axis table must describe the same twelve baselines.

`REWARD_NORMALIZATION` was added on 2026-09-08 because the reward-normalisation split had never
been enumerated -- review 2 §29 said "several on-policy Procgen-derived families normalize
rewards" and no review, and no file here, ever said which. A table that silently omits a baseline
answers "does this one normalise?" with a KeyError at best and with a wrong default at worst.

The 3/9 assertions are not decoration. `time limit` and `reward scale` both split 3/9 over
DISJOINT sets, so a reader who has learned "the three that differ are rad, soda, alda" will read
the reward axis exactly backwards. If either split changes, that is a comparability fact the
report has to state, and this test is where it surfaces.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rlgen.protocol import (  # noqa: E402
    OBSERVATION_GEOMETRY, REWARD_NORMALIZATION, TIME_LIMIT_HANDLING,
)

TABLES = {
    "OBSERVATION_GEOMETRY": OBSERVATION_GEOMETRY,
    "TIME_LIMIT_HANDLING": TIME_LIMIT_HANDLING,
    "REWARD_NORMALIZATION": REWARD_NORMALIZATION,
}


def test_every_axis_table_covers_the_same_baselines():
    reference = set(OBSERVATION_GEOMETRY)
    assert len(reference) == 12, sorted(reference)
    for name, table in TABLES.items():
        assert set(table) == reference, (
            f"{name} does not describe the same fleet: "
            f"missing {sorted(reference - set(table))}, extra {sorted(set(table) - reference)}")


def test_the_two_three_nine_splits_are_disjoint():
    """The fact most likely to be misread, asserted so a change to either cannot pass silently."""
    bootstrap = {b for b, v in TIME_LIMIT_HANDLING.items() if v == "bootstrap"}
    normalised = {b for b, v in REWARD_NORMALIZATION.items() if v == "normalised"}
    assert bootstrap == {"rad", "soda", "alda"}, sorted(bootstrap)
    assert normalised == {"idaac", "ppg", "ctrl"}, sorted(normalised)
    assert not (bootstrap & normalised), (
        "the two 3/9 splits have stopped being disjoint; the report's phrasing depends on it")


def test_reward_normalisation_values_are_from_a_closed_vocabulary():
    assert set(REWARD_NORMALIZATION.values()) <= {"normalised", "raw"}
