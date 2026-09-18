"""The headline reading aggregates seeds, not scenes and not episodes.

Every check here is built so that the WRONG aggregation would fail it. That matters more than
usual: the quantity is what the whole campaign reports, the protocol (`docs/EVAL-PROTOCOL.md` §4c)
is explicit about it, and the first production reading of this project was aggregated by hand and
had to be partly retracted the next day.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "production_reading.py"
sys.path.insert(0, str(ROOT / "scripts"))

spec = importlib.util.spec_from_file_location("_production_reading", SCRIPT)
pr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pr)


def _row(regime, scene_set, mean, mode="sample", episodes=20, scope="endpoint"):
    return {"eval_scope": scope, "regime": regime, "scene_set": scene_set,
            "episode_return_mean": mean, "episodes": episodes,
            "conventions": {"eval_policy_mode": mode}}


def test_a_scene_mean_is_the_unweighted_mean_of_the_ten_scene_cells():
    rows = [_row("train", str(s), float(s)) for s in range(10)]
    assert pr.per_seed_means(rows)[("train", "sample")] == pytest.approx(4.5)


def test_the_pooled_ten_scene_row_is_dropped_rather_than_counted_again():
    """The evaluator writes ten scene rows AND a pooled one; counting both skews toward the pool."""
    rows = [_row("train", str(s), 10.0) for s in range(10)]
    rows.append(_row("train", "0,1,2,3,4,5,6,7,8,9", 100.0))
    assert pr.per_seed_means(rows)[("train", "sample")] == pytest.approx(10.0), (
        "the pooled row was counted as an eleventh scene")


def test_episodes_do_not_weight_a_scene():
    """A scene evaluated with more episodes is not a bigger replicate -- the protocol averages scenes."""
    rows = [_row("train", "0", 0.0, episodes=200), _row("train", "1", 10.0, episodes=20)]
    assert pr.per_seed_means(rows)[("train", "sample")] == pytest.approx(5.0)


def test_sampled_and_mode_rows_never_mix():
    rows = [_row("train", "0", 0.0, mode="sample"), _row("train", "0", 100.0, mode="mode")]
    means = pr.per_seed_means(rows)
    assert means[("train", "sample")] == 0.0 and means[("train", "mode")] == 100.0


def test_curve_rows_are_not_read_as_endpoint_rows():
    rows = [_row("train", "0", 1.0), _row("train", "0", 99.0, scope="curve")]
    assert pr.per_seed_means(rows)[("train", "sample")] == pytest.approx(1.0)


def test_seeds_are_the_replicates_and_every_one_is_printed():
    points = {("idaac", "sample", "train"): [(101, 39.24), (102, 20.51), (103, 30.0)]}
    lines, provisional = pr.render(points, {}, markdown=False)
    body = "\n".join(lines)
    assert not provisional, "three seeds is the full n; nothing provisional about it"
    assert "101:39.24" in body and "102:20.51" in body and "103:30.00" in body, body
    assert "29.92" in body, "the mean over the three seed points must be shown"
    assert "20.51-39.24" in body, "the range must be shown beside the mean"


def test_fewer_than_three_seeds_is_marked_and_strict_refuses():
    points = {("idaac", "sample", "train"): [(101, 39.24), (102, 20.51)]}
    lines, provisional = pr.render(points, {}, markdown=False)
    assert provisional and "PROVISIONAL" in "\n".join(lines)


def test_the_footer_says_how_many_cells_were_not_read():
    """A thin table must say it is thin; silence about skipped cells reads as coverage."""
    lines, _ = pr.render({("idaac", "sample", "train"): [(101, 1.0)]}, {"MISSING": 32, "PARTIAL": 1},
                         markdown=False)
    body = "\n".join(lines)
    assert "MISSING 32" in body and "PARTIAL 1" in body


def test_it_runs_against_the_real_records_and_agrees_with_the_hand_reading():
    """Ground truth: the two idaac seeds were aggregated by hand on 2026-09-17 before this existed."""
    points, skipped, _gate = pr.collect(pathlib.Path(pr.cs.DEFAULT_SCHEDULE))
    got = dict(points.get(("idaac", "sample", "train"), []))
    assert got.get(101) == pytest.approx(39.24, abs=0.01), got
    assert got.get(102) == pytest.approx(20.51, abs=0.01), got
    assert skipped.get("MISSING", 0) >= 1, "the skipped tally must be reported, not hidden"


def test_the_competence_gate_refuses_a_ratio_built_on_shaped_reward():
    """A policy that never opens the door has no skill to retain; its gap would read as robustness."""
    floor = 1.842
    ok, why = pr.competence(train_mean=82.18, train_success=0.005, floor=floor)
    assert not ok and "shaped reward" in why, why


def test_the_competence_gate_refuses_a_denominator_at_the_floor():
    ok, why = pr.competence(train_mean=1.5, train_success=0.9, floor=1.842)
    assert not ok and "floor" in why, why


def test_the_competence_gate_admits_a_policy_that_actually_solves_the_task():
    ok, why = pr.competence(train_mean=96.21, train_success=0.27, floor=1.842)
    assert ok and why == ""


def test_retention_is_printed_only_for_a_competent_cell():
    points = {("m", "sample", "train"): [(1, 100.0)], ("m", "sample", "eval-easy"): [(1, 50.0)]}
    refused = pr.render_retention(points, {("m", "sample", 1): (False, "train success 0.000 below 0.25",
                                                                100.0, 0.0)})
    assert any("DID NOT REACH COMPETENCE" in l for l in refused)
    assert not any("0.500" in l for l in refused), "a refused cell must not also print its ratio"

    allowed = pr.render_retention(points, {("m", "sample", 1): (True, "", 100.0, 0.5)})
    assert any("eval-easy 0.500" in l for l in allowed), allowed


def test_the_real_records_are_all_refused_a_ratio_today():
    """Ground truth as of 2026-09-18: every 600k production cell sits at ~0 task success."""
    points, _, gate = pr.collect(pathlib.Path(pr.cs.DEFAULT_SCHEDULE))
    assert gate, "no cells were gated at all"
    assert all(not competent for competent, *_ in gate.values()), gate


def test_a_scene_measured_twice_is_still_one_scene():
    """idaac s101 was measured by its in-cell grid AND by an offline re-evaluation sweep.

    Appending both to one list weights those scenes twice. Averaging within the scene first makes a
    repeat measurement a better estimate of that scene, which is what it is.
    """
    rows = [_row("train", "0", 0.0), _row("train", "0", 10.0),   # scene 0, measured twice
            _row("train", "1", 20.0)]                            # scene 1, once
    assert pr.per_seed_means(rows)[("train", "sample")] == pytest.approx(12.5), (
        "expected mean(mean(0,10), 20) = 12.5; a flat list would give 10.0")
