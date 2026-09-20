"""The headline reading aggregates seeds, not scenes and not episodes.

Every check here is built so that the WRONG aggregation would fail it. That matters more than
usual: the quantity is what the whole campaign reports, the protocol (`docs/EVAL-PROTOCOL.md` §4c)
is explicit about it, and the first production reading of this project was aggregated by hand and
had to be partly retracted the next day.
"""
from __future__ import annotations

import importlib.util
import json
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
    points, skipped, _gate, _success, dropped = pr.collect(pathlib.Path(pr.cs.DEFAULT_SCHEDULE))
    got = dict(points.get(("idaac", "sample", "train"), []))
    assert got.get(101) == pytest.approx(39.24, abs=0.01), got
    assert got.get(102) == pytest.approx(20.51, abs=0.01), got
    assert skipped.get("MISSING", 0) >= 1, "the skipped tally must be reported, not hidden"
    assert dropped.get("pooled ten-scene row", 0) >= 1, (
        "the real records contain pooled rows; the row tally must see them")
    unreadable = {k: v for k, v in dropped.items() if k not in pr.DROPPED_BY_DESIGN}
    assert not unreadable, f"a DONE cell has rows this reading cannot parse: {unreadable}"


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
    points, _, gate, _success, _dropped = pr.collect(pathlib.Path(pr.cs.DEFAULT_SCHEDULE))
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


def test_the_headline_table_carries_the_success_rate():
    """A return without its success rate is not interpretable: 82 with succ 0.005 is shaped reward."""
    points = {("m", "sample", "train"): [(1, 82.18)]}
    success = {("m", "sample", "train"): [(1, 0.005)]}
    lines, _ = pr.render(points, {}, markdown=False, success=success)
    body = "\n".join(lines)
    assert "0.005" in body, body
    assert "succ" in lines[0], lines[0]


def test_a_row_with_no_policy_mode_is_counted_rather_than_silently_dropped():
    """The defect this closes: a family whose rows lack `conventions.eval_policy_mode` vanished.

    `_by_scene` dropped it with a bare `continue`, so the baseline simply did not appear in the
    table and nothing said why. A check needs its comparison count: the rows that were read and
    the rows that were not are both part of the reading.
    """
    rows = [_row("train", str(s), 1.0) for s in range(10)]
    blind = _row("train", "0", 5.0)
    del blind["conventions"]
    rows.append(blind)
    drops = pr._drop_tally(rows)
    assert drops.get("no conventions.eval_policy_mode") == 1, drops
    assert pr.per_seed_means(rows)[("train", "sample")] == pytest.approx(1.0), (
        "the unreadable row must still be excluded from the mean, only not in silence")


def test_a_row_with_no_return_is_counted():
    rows = [_row("train", "0", 1.0), _row("train", "1", None)]
    assert pr._drop_tally(rows).get("no episode_return_mean") == 1


def test_by_design_drops_are_counted_separately_from_defects():
    """Curve and pooled rows are dropped on purpose; those two must not read as a warning."""
    rows = [_row("train", "0", 1.0), _row("train", "0", 9.0, scope="curve"),
            _row("train", "0,1,2,3,4,5,6,7,8,9", 9.0)]
    for row in rows:
        row["success_rate"] = 0.0
    drops = pr._drop_tally(rows)
    assert drops.get("not an endpoint row") == 1 and drops.get("pooled ten-scene row") == 1
    assert set(drops) <= pr.DROPPED_BY_DESIGN, "no defect reason should be raised by these rows"


def test_the_footer_reports_unreadable_rows_and_marks_them():
    lines, _ = pr.render({("idaac", "sample", "train"): [(101, 1.0)]}, {},
                         markdown=False,
                         dropped={"no conventions.eval_policy_mode": 7, "pooled ten-scene row": 11})
    body = "\n".join(lines)
    assert "no conventions.eval_policy_mode 7" in body, body
    assert "pooled ten-scene row 11" in body, body
    assert "UNREADABLE" in body, "a defect drop must be distinguishable from a by-design one"


def test_a_missing_executed_endpoint_is_derived_and_reported_not_silently_wrong(tmp_path):
    """[2026-09-20] `entry.get("executed_endpoint", schedule.get("frames"))` used to fall back to
    the REQUESTED frame count when a schedule row declared no `executed_endpoint` at all. idaac's
    own checkpoints land at 598,016 for a requested 600,000 (it floors to a whole rollout), so a
    row filtered on `frame in (600000, "600000")` matched nothing and a complete cell read
    MISSING/PARTIAL with no explanation. Uses the real `idaac` s101 records already in
    `results/records/` -- the same data the campaign actually holds -- rather than a synthetic
    stand-in, so this is also a live check that the derivation matches what really shipped."""
    idaac_records = list((ROOT / "results" / "records").glob("*idaac*"))
    if not idaac_records:
        pytest.skip("no idaac records in the tree to exercise this against")
    schedule = {"frames": 600000, "seeds": [101],
                "rows": [{"baseline": "idaac", "family": "idaac"}]}  # no executed_endpoint key
    schedule_path = tmp_path / "schedule.json"
    schedule_path.write_text(json.dumps(schedule))
    points, skipped, gate, success, dropped = pr.collect(schedule_path)
    assert ("idaac", "sample", "train") in points, (
        f"idaac s101 must resolve DONE via the derived endpoint (598016), not fall back to the "
        f"requested 600000 and match nothing; skipped={skipped}")
    assert any("quantises 600000 to 598016" in reason for reason in dropped), (
        f"the derivation must be reported, not silent; dropped={dropped}")
