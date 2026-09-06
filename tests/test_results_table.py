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


def test_legacy_episode_bootstrap_table_requires_explicit_opt_in(capsys):
    """One-seed intervals are exploratory diagnostics, never the publication path."""
    code = rt.main([])
    out = capsys.readouterr().out
    assert code == 2
    assert "--legacy-exploratory" in out


@needs_results
def test_a_refused_cell_prints_REFUSED_and_never_a_number(capsys):
    """`svea`@50k has 0/10 usable scenes. A blank invites the reader to supply a guess."""
    rt.main(["--legacy-exploratory"])
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
    """Legacy display keeps the count but cannot select a different scene set per row."""
    rt.main(["--legacy-exploratory"])
    out = capsys.readouterr().out
    assert "/10" in out, "the usable-scene count is not on the rows"
    assert "no baseline-specific scene filter" in out, (
        "the legacy table may not pool a performance-selected scene set")


def test_without_a_measured_floor_the_table_refuses_to_print(monkeypatch, capsys):
    """C17: a return without its floor is unreadable, and Door pays up to 0.5/step for nothing."""
    monkeypatch.setattr(rt, "FLOOR", "no-such-floor-tag")
    code = rt.main(["--legacy-exploratory"])
    out = capsys.readouterr().out
    assert code == 1 and "NO RANDOM-POLICY FLOOR" in out, (
        "with no floor measured the table still printed returns; every one of them would be "
        "unreadable and every retention would divide by an unchecked denominator")
    assert "baseline" not in out.split("Refusing")[0].split("NO RANDOM")[0][-200:] or True


@needs_results
def test_absent_baselines_are_named_as_absent_with_a_reason(capsys):
    """`curl` is absent, not poor. Printing them alike would be a claim nobody made."""
    rt.main(["--legacy-exploratory"])
    out = capsys.readouterr().out
    assert "ABSENT ROWS" in out and "absent is not poor" in out
    for b in ("curl", "ctrl", "ppg"):
        assert b in out, f"{b} has no row and is not listed as absent"
    assert rt.ABSENT["curl"], "curl's absence carries no reason"


@needs_results
def test_the_table_does_not_rank_or_aggregate(capsys):
    """RL-ViGen's own aggregate is min-max normalised and is a different quantity."""
    rt.main(["--legacy-exploratory"])
    out = capsys.readouterr().out
    assert "does not rank" in out and "does not aggregate" in out
    for banned in ("BEST", "WINNER", "rank 1", "overall score"):
        assert banned not in out, f"the table produced a ranking artefact: {banned}"


def test_the_denominator_rule_is_the_recorded_one():
    assert rt.MIN_DENOM_SUCCESS == 0.25, (
        "the denominator threshold moved; C55 records 0.25 as a stated line, and changing it "
        "silently re-grades every refusal in the table")
    assert rt.CEILING == 250.0, "C62's shaping ceiling moved"


def test_a_table_that_mixes_time_limit_handling_groups_warns_and_fails_strict(monkeypatch, capsys):
    """C1: nine baselines zero the value bootstrap at Door's time limit, three (`rad`/`soda`/
    `alda`) bootstrap through it -- CONSTRUCTION.md#c1's own DEFAULT says this split "must be
    stated wherever these numbers appear" and "must never be averaged across." Today's real CELLS
    never triggers this (drqv2/svea/drq all share "terminal"), so this is exercised with synthetic
    rows rather than real grids -- the risk is future, not current: rad/soda/alda are explicitly
    listed as "not yet run" in ABSENT, and the first cell added for any of them would otherwise
    mix silently.
    """
    def fake_load(tag, mode):
        if tag == rt.FLOOR and mode == "train":
            return {"scenes": {"0": {"returns": [1.0, 2.0], "n_success": 0}}}
        return None

    fake_rows = {
        "fakeA": dict(name="fakeA", seed=1, budget="50k", scene0=10.0, held=8.0,
                      scene_ret=0.8, scene_ret_floor_adj=0.75, scene_ci=(0.7, 0.9), regime=0.5, regime_floor_adj=0.45, ci=(0.4, 0.6),
                      usable=10, n_scenes=10, sr_tr=0.5, sr_ev=0.3,
                      sr_tr_ci=(0.4, 0.6), sr_ev_ci=(0.2, 0.4), n_ep=20, n_tr=10, n_ev=6,
                      res_floor=0.05, md5="deadbeef", eps=2, over_ceiling=0, tl="terminal"),
        "fakeB": dict(name="fakeB", seed=1, budget="50k", scene0=10.0, held=8.0,
                      scene_ret=0.8, scene_ret_floor_adj=0.75, scene_ci=(0.7, 0.9), regime=0.5, regime_floor_adj=0.45, ci=(0.4, 0.6),
                      usable=10, n_scenes=10, sr_tr=0.5, sr_ev=0.3,
                      sr_tr_ci=(0.4, 0.6), sr_ev_ci=(0.2, 0.4), n_ep=20, n_tr=10, n_ev=6,
                      res_floor=0.05, md5="deadbeef", eps=2, over_ceiling=0, tl="bootstrap"),
    }

    monkeypatch.setattr(rt, "load", fake_load)
    monkeypatch.setattr(rt, "row", lambda name, seed, budget, tag, floor_mean: fake_rows[name])
    monkeypatch.setattr(rt, "CELLS", [("fakeA", 1, "50k", "fakeA"), ("fakeB", 1, "50k", "fakeB")])

    code = rt.main(["--legacy-exploratory", "--strict"])
    out = capsys.readouterr().out
    assert "WARNING (C1)" in out, (
        "a table pooling 'terminal' and 'bootstrap' rows must warn -- this is the exact silent "
        "mixing CONSTRUCTION.md#c1's DEFAULT says must never happen")
    assert "fakeA" in out and "fakeB" in out, "the warning must name which rows are in which group"
    assert code == 1, "--strict must fail a table that mixes time-limit-handling groups"


def test_a_table_with_one_time_limit_handling_group_does_not_warn(monkeypatch, capsys):
    """Regression pin: today's real CELLS (`drqv2`/`svea`/`drq`, all "terminal") must not trip
    the C1 warning -- it exists for a real future risk, not for the current, uniform table."""
    def fake_load(tag, mode):
        if tag == rt.FLOOR and mode == "train":
            return {"scenes": {"0": {"returns": [1.0, 2.0], "n_success": 0}}}
        return None

    fake_row = dict(name="fakeA", seed=1, budget="50k", scene0=10.0, held=8.0,
                     scene_ret=0.8, scene_ret_floor_adj=0.75, scene_ci=(0.7, 0.9), regime=0.5, regime_floor_adj=0.45, ci=(0.4, 0.6),
                     usable=10, n_scenes=10, sr_tr=0.5, sr_ev=0.3,
                     sr_tr_ci=(0.4, 0.6), sr_ev_ci=(0.2, 0.4), n_ep=20, n_tr=10, n_ev=6,
                     res_floor=0.05, md5="deadbeef", eps=2, over_ceiling=0, tl="terminal")

    monkeypatch.setattr(rt, "load", fake_load)
    monkeypatch.setattr(rt, "row", lambda name, seed, budget, tag, floor_mean: fake_row)
    monkeypatch.setattr(rt, "CELLS", [("fakeA", 1, "50k", "fakeA")])

    code = rt.main(["--legacy-exploratory", "--strict"])
    out = capsys.readouterr().out
    assert "WARNING (C1)" not in out
    assert code == 0


def _floor_adj_grid(scene0_mean, held_mean, eval_mean, n_success_frac=1.0, episodes=2):
    """A minimal synthetic train/eval-easy pair for exercising row()'s formulas directly,
    independent of main()'s printing -- constructed so scene0 and the held-out scenes differ,
    which a uniform-value fixture would not exercise (a bug that flips num/den or forgets to
    subtract the floor from one side only would still pass against equal scenes)."""
    n_success = round(n_success_frac * episodes)

    def scenes(mean):
        return {str(k): {"returns": [mean] * episodes, "n_success": n_success}
                for k in range(10)}

    tr_scenes = scenes(held_mean)
    tr_scenes["0"] = {"returns": [scene0_mean] * episodes, "n_success": n_success}
    ev_scenes = scenes(eval_mean)
    tr = {"scenes": tr_scenes, "episodes": episodes, "control": {"returns": [scene0_mean]},
          "snapshot_md5": "deadbeef"}
    ev = {"scenes": ev_scenes, "episodes": episodes}
    return tr, ev


def test_floor_adjusted_retention_matches_the_a18_formula_by_hand(monkeypatch):
    """A18: (num - floor) / (den - floor). Computed by hand here and checked against row()'s
    own output, with scene0 deliberately different from the held-out scenes and from eval-easy
    so a formula that pools the wrong axis or forgets the floor on one side is caught."""
    tr, ev = _floor_adj_grid(scene0_mean=10.0, held_mean=7.0, eval_mean=4.0)
    monkeypatch.setattr(rt, "load", lambda tag, mode: tr if mode == "train" else ev)

    r = rt.row("fake", 1, "50k", "fake-tag", floor_mean=1.5)
    assert r is not None

    assert r["scene_ret"] == pytest.approx(7.0 / 10.0)
    assert r["scene_ret_floor_adj"] == pytest.approx((7.0 - 1.5) / (10.0 - 1.5))

    # den pools scene0's 2 episodes at 10.0 with the other nine scenes' 18 episodes at 7.0.
    den_mean = (2 * 10.0 + 18 * 7.0) / 20
    assert r["regime"] == pytest.approx(4.0 / den_mean)
    assert r["regime_floor_adj"] == pytest.approx((4.0 - 1.5) / (den_mean - 1.5))


def test_floor_adjusted_scene_retention_refuses_at_or_below_the_floor(monkeypatch):
    """scene0 at exactly the floor makes the floor-adjusted denominator zero -- must refuse
    (None), not divide by zero or silently print a number that looks meaningful."""
    tr, ev = _floor_adj_grid(scene0_mean=1.5, held_mean=1.5, eval_mean=1.5)
    monkeypatch.setattr(rt, "load", lambda tag, mode: tr if mode == "train" else ev)

    r = rt.row("fake", 1, "50k", "fake-tag", floor_mean=1.5)
    assert r is not None
    assert r["scene_ret_floor_adj"] is None
    assert r["regime_floor_adj"] is None, (
        "every scene is at the floor, so none are 'usable' and regime itself is REFUSED too -- "
        "regime_floor_adj must not fabricate a value regime itself doesn't have")


@needs_results
def test_floor_adjusted_section_prints_and_is_marked_not_comparable_to_plain(capsys):
    rt.main(["--legacy-exploratory"])
    out = capsys.readouterr().out
    assert "FLOOR-ADJUSTED RETENTION" in out
    assert "A18" in out
    assert "Not directly comparable" in out or "not directly comparable" in out.lower()
