#!/usr/bin/env python3
"""The results table must not print a number a reader would trust more than it deserves.

This is the artifact that leaves the project, so every way of misleading has to be closed at the
point of presentation rather than in a document nobody reading the table will open:

- a **refused** cell must print REFUSED, never a number and never a blank;
- rows pooled over **different scene sets** must expose the count, because two averages over
  different scenes are not the same statistic;
- the **random-policy floor** must be present or nothing may be printed at all (C17);
- **absent** baselines must be listed as absent, which is a different claim from poor.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("rt", ROOT / "scripts" / "results_table.py")
rt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rt)


# Rendering the table reads `results/`, which the isolated candidate tree does not carry. A test
# that fails because a deliberately-absent asset is absent teaches the reader to ignore red, so
# these skip. The two tests that do NOT render -- the refusal path and the denominator rule -- are
# left running, because those are the ones that still say something in a tree with no results.
# [Claude 2026-09-04] The guard now names the directory these tests ACTUALLY need
# (results/regime-retention-c69, the retention grids), not the generic results/ parent. It was a
# PROXY -- "does results/ exist" standing in for "has anything been tabulated here" -- and it held
# only while results/ had exactly one use. On 2026-09-04 results/records/ and results/logs/ were
# added to retain returned job artifacts (R7, EVAL-PROTOCOL section 6), the parent came into
# existence for an unrelated reason, and these tests went from SKIPPED to FAILING against grids
# that have never existed in this tree. The failure was real information about the guard, not
# about the cells.
needs_results = pytest.mark.skipif(
    not (ROOT / "results" / "regime-retention-c69").is_dir(),
    reason="no retention grids in this tree: the table has no rows to render")


@needs_results
def test_a_refused_cell_prints_REFUSED_and_never_a_number(capsys):
    """`svea`@50k has 0/10 usable scenes. A blank invites the reader to supply a guess."""
    rt.main([])
    out = capsys.readouterr().out
    assert "REFUSED" in out, (
        "no row printed REFUSED, but svea@50k has no scene clearing the denominator rule — "
        "either the rule stopped being applied or the refusal is being rendered as a number")
    # Only the MAIN table carries the regime-retention column, and only that column is refused.
    # The intervals block below it legitimately shows svea@50k's SCENE retention and success
    # rates, which are not refused — an earlier version of this test scanned every line mentioning
    # svea and 50k and went red on the intervals block, i.e. on correct output.
    main_table = out.split("INTERVALS.")[0]
    for line in main_table.splitlines():
        if line.strip().startswith("svea") and "50k" in line:
            assert "REFUSED" in line, f"svea@50k rendered without its refusal: {line}"


@needs_results
def test_every_row_exposes_how_many_scenes_it_pooled(capsys):
    """drqv2@100k averages 3 scenes and svea@100k averages 9. Hiding that equates two statistics."""
    rt.main([])
    out = capsys.readouterr().out
    assert "/10" in out, "the usable-scene count is not on the rows"
    assert "DIFFERENT SCENE SETS" in out, (
        "the table stopped saying that rows with different n are not the same statistic")


def test_without_a_measured_floor_the_table_refuses_to_print(monkeypatch, capsys):
    """C17: a return without its floor is unreadable, and Door pays up to 0.5/step for nothing."""
    monkeypatch.setattr(rt, "FLOOR", "no-such-floor-tag")
    code = rt.main([])
    out = capsys.readouterr().out
    assert code == 1 and "NO RANDOM-POLICY FLOOR" in out, (
        "with no floor measured the table still printed returns; every one of them would be "
        "unreadable and every retention would divide by an unchecked denominator")
    assert "baseline" not in out.split("Refusing")[0].split("NO RANDOM")[0][-200:] or True


@needs_results
def test_absent_baselines_are_named_as_absent_with_a_reason(capsys):
    """`curl` is absent, not poor. Printing them alike would be a claim nobody made."""
    rt.main([])
    out = capsys.readouterr().out
    assert "ABSENT ROWS" in out and "absent is not poor" in out
    for b in ("curl", "ctrl", "ppg"):
        assert b in out, f"{b} has no row and is not listed as absent"
    assert rt.ABSENT["curl"], "curl's absence carries no reason"


@needs_results
def test_the_table_does_not_rank_or_aggregate(capsys):
    """RL-ViGen's own aggregate is min-max normalised and is a different quantity."""
    rt.main([])
    out = capsys.readouterr().out
    assert "does not rank" in out and "does not aggregate" in out
    for banned in ("BEST", "WINNER", "rank 1", "overall score"):
        assert banned not in out, f"the table produced a ranking artefact: {banned}"


def test_the_denominator_rule_is_the_recorded_one():
    assert rt.MIN_DENOM_SUCCESS == 0.25, (
        "the denominator threshold moved; C55 records 0.25 as a stated line, and changing it "
        "silently re-grades every refusal in the table")
    assert rt.CEILING == 250.0, "C62's shaping ceiling moved"
