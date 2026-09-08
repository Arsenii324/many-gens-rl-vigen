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


def test_blocking_on_network_input_does_not_change_the_reported_set():
    """`network input` was added on 2026-09-08 and must remain free.

    It was added because the old justification for leaving render size out — "crop policy already
    equalises what the network sees at 84" — was true of `rad`/`soda` and false of the 64-render
    group, where nothing equalises anything. Blocking on what the NETWORK receives fixes that:
    `rad`/`soda` render 100 and crop to 84, so they sit with the RL-ViGen five; the 64 group is
    genuinely 64.

    Adding it changed no pair, because each mechanism group happens to be internally uniform in
    input size — the reported set was correct by COINCIDENCE and is now correct by CONSTRUCTION.
    This test pins that: if a future change makes the axis start demoting pairs, that is a real
    comparability event and must be seen, not absorbed.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_comparison_blocks_under_test", ROOT / "scripts" / "comparison_blocks.py")
    blocks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(blocks)

    assert "network input" in blocks.BLOCKING_AXES
    import itertools
    without = tuple(a for a in blocks.BLOCKING_AXES if a != "network input")
    for members in blocks.GROUPS.values():
        present = [b for b in members if b in OBSERVATION_GEOMETRY]
        for left, right in itertools.combinations(present, 2):
            axes_left, axes_right = blocks.axes_of(left), blocks.axes_of(right)
            primary_now = all(axes_left[a] == axes_right[a] for a in blocks.BLOCKING_AXES)
            primary_before = all(axes_left[a] == axes_right[a] for a in without)
            assert primary_now == primary_before, (
                f"{left} vs {right} changed status when `network input` was added: the axis is no "
                f"longer free, which is a comparability finding rather than a refactor")
