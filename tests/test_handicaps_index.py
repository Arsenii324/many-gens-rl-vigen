#!/usr/bin/env python3
"""The handicap index must stay wired to the register — SYSTEM.md's "no home" gap.

`scripts/handicaps.py` inverts the register's `**Handicap — affects:**` markers into a
per-baseline view. Its whole value is that there is no second document to drift: the register is
the source, and the view is generated.

That design has one failure mode, and it is silent. If the markers are edited away, renamed, or
lost in a reformat, the script prints a *smaller* index — or an empty one — and nothing looks
wrong. An index that quietly stops listing a handicap is worse than no index, because a reader who
consults it concludes the baseline is unencumbered.

So these tests assert a floor and the specific memberships that were established by measurement,
each of which cost real work to determine (`rlgen/protocol.py:127-138` for the 3/9 split, C49's
classifier run for IDAAC's labels, the per-file entropy audit for C61).
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("hc", ROOT / "scripts" / "handicaps.py")
hc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hc)


@pytest.fixture(scope="module")
def entries():
    return hc.parse()


def test_the_markers_are_still_there(entries):
    """The silent failure: markers removed, index shrinks, nothing looks wrong."""
    assert len(entries) >= 4, (
        f"only {len(entries)} current handicap entries parsed. SYSTEM.md lists four as the known set "
        "(C1, C5, C50, C61); fewer means the `**Handicap — affects:**` markers were lost, not "
        "that the handicaps went away.")


def test_every_marker_names_only_real_baselines(entries):
    """A typo would invent a thirteenth baseline and silently under-report a real one."""
    named = {b for e in entries for b in e["affects"]}
    unknown = named - set(hc.BASELINES)
    assert not unknown, f"marker names non-baselines: {sorted(unknown)}"


def test_the_memberships_that_were_measured(entries):
    """Spot-check the three that were established by measurement rather than by reading.

    Not an exhaustive pin: the point is that a reformat which drops a *baseline* from a marker
    should fail, and these three are where a drop would do the most damage.
    """
    by_id = {e["id"]: set(e["affects"]) for e in entries}
    assert not by_id.get("C3"), "C3 is historical after the production Impala repair and must not be indexed as live"
    assert "idaac" in by_id.get("C50", set()), "C50 is IDAAC's inert instance-invariance loss"
    assert by_id.get("C61", set()) == {"idaac", "ppg", "ctrl", "ibac_sni"}, (
        "C61 covers exactly the four Procgen-native clones, verified per file; a change here means "
        "either the audit changed or the marker drifted")
    # The 3/9 split: the NINE that zero the bootstrap are handicapped, not the three that don't.
    c1 = by_id.get("C1", set())
    assert len(c1) == 9, f"C1 should name the nine terminal-treating baselines, got {len(c1)}"
    assert not ({"rad", "soda", "alda"} & c1), "rad/soda/alda bootstrap; they are not handicapped here"


def test_the_inversion_covers_every_baseline(entries):
    """C5 alone touches all twelve, so a baseline with zero handicaps means the index broke."""
    covered = {b for e in entries for b in e["affects"]}
    missing = set(hc.BASELINES) - covered
    assert not missing, f"baselines absent from the handicap index entirely: {sorted(missing)}"


def test_the_asymmetry_is_visible(entries):
    """The index exists to make this answerable, so it is worth asserting it can be answered.

    Handicaps are not evenly distributed: the Procgen-native clones carry several, the DMC-GB
    lineage carries one. A reader comparing `idaac` against `rad` is comparing across that gap,
    and before this index there was no way to see it without reading the register by date.
    """
    counts = {b: sum(b in e["affects"] for e in entries) for b in hc.BASELINES}
    assert counts["ibac_sni"] > counts["rad"], (
        "the index no longer distinguishes a heavily-handicapped baseline from a lightly-"
        "handicapped one, which is the one question it was built to answer")


def test_faithfulness_points_at_the_handicap_index():
    """The per-algorithm document must route to the per-baseline handicap view.

    `SYSTEM.md` predicted this gap in words — handicaps are "findable by date through the register
    and invisible by algorithm, which is the axis a reader of `idaac`'s FAITHFULNESS section is
    on" — and building `scripts/handicaps.py` did not close it, because nothing in FAITHFULNESS
    mentioned the index. The concrete case: that file's `idaac` section still says nothing about
    the instance-invariance loss being inert here, while C49 measured the label at chance.

    Pinned because a pointer is exactly the kind of line that gets lost in a reformat, and its
    absence is silent — the document reads complete either way.
    """
    text = (ROOT / "docs" / "FAITHFULNESS.md").read_text(encoding="utf-8")
    assert "scripts/handicaps.py" in text, (
        "FAITHFULNESS.md no longer routes to the handicap index. A reader asking 'is this "
        "baseline's number fair to call that method's result?' needs what was left alone and "
        "still costs it, and this file structurally cannot record that.")
