"""The one property of the scene probe worth guarding is logical, not numerical.

`scripts/probe_scenes.py` answers whether the evaluation SCENE axis carries signal — the
measurement that decides whether C45 is a bookkeeping defect or a reason none of our numbers are
comparable to RL-ViGen's. Its numbers come from rendering robosuite, which this suite must not
do. What can be tested without an environment is the part that decides what the numbers are
allowed to mean.

**A flat scene result and a broken instrument produce the same table.** One says "scene identity
does not matter"; the other says "this run could not have detected it either way". Reporting the
first when the truth is the second is the failure `docs/research-evidence` names as the highest-
value thing to check, and the post-mortem behind it had three separate instances. So `summarise`
must refuse to say NOT SEPARATED whenever the positive control did not fire, however flat the
scene numbers are.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.probe_scenes import summarise  # noqa: E402

FLAT = {1: 0.16, 2: 0.15}          # scenes indistinguishable from the floor
WIDE = {1: 0.41, 2: 0.45}          # clearly separated
FLOOR = {0: 0.15, 1: 0.15}


class TestThePositiveControlCanVetoTheVerdict:
    def test_flat_scenes_with_a_dead_control_are_uninterpretable_not_negative(self):
        r = summarise(FLOOR, FLAT, control=0.15, threshold=2.0)
        assert r["verdict"] == "UNINTERPRETABLE"
        assert r["interpretable"] is False

    def test_flat_scenes_with_no_control_at_all_are_uninterpretable(self):
        assert summarise(FLOOR, FLAT, control=None, threshold=2.0)["verdict"] == "UNINTERPRETABLE"

    def test_flat_scenes_with_a_live_control_ARE_a_negative_result(self):
        """The control firing is exactly what licenses reading a flat result as a finding."""
        r = summarise(FLOOR, FLAT, control=0.60, threshold=2.0)
        assert r["verdict"] == "NOT SEPARATED"
        assert r["interpretable"] is True

    def test_separated_scenes_require_the_control_too(self):
        """A positive result from an unvalidated instrument is not better than a negative one."""
        assert summarise(FLOOR, WIDE, control=0.15, threshold=2.0)["verdict"] == "UNINTERPRETABLE"

    def test_separated_scenes_with_a_live_control(self):
        r = summarise(FLOOR, WIDE, control=0.60, threshold=2.0)
        assert r["verdict"] == "SEPARATED"
        assert r["median_ratio"] == pytest.approx(2.867, rel=1e-2)


class TestTheFloorIsRequired:
    def test_no_within_scene_control_means_no_verdict(self):
        """Between-scene distances alone are uninterpretable; the run must say so."""
        r = summarise({}, WIDE, control=0.60, threshold=2.0)
        assert r["verdict"] == "NO CONTROL"
        assert r["interpretable"] is False and r["floor"] is None

    def test_the_floor_is_the_median_not_the_minimum(self):
        """Using the smallest floor would inflate every ratio. Observed floors on Door spanned
        0.064 to 0.182 -- a 2.8x spread -- so this choice moves the headline number."""
        r = summarise({0: 0.05, 1: 0.15, 2: 0.25}, {1: 0.30}, control=0.60, threshold=2.0)
        assert r["floor"] == pytest.approx(0.15)
        assert r["ratios"][1] == pytest.approx(2.0)


def test_the_recorded_door_result_reproduces_from_its_own_numbers():
    """Pins the measurement C45 now cites, so a later edit to the entry cannot drift from it.

    Raw TV distances from `python scripts/probe_scenes.py` on Door at eval-easy, 2026-08-18.
    """
    within = {0: 0.0641, 1: 0.1378, 2: 0.1818, 3: 0.1594}
    between = {1: 0.4069, 2: 0.3304, 3: 0.4149, 4: 0.3152,
               5: 0.4478, 6: 0.4653, 7: 0.3706, 8: 0.3793, 9: 0.3980}
    r = summarise(within, between, control=0.4735, threshold=2.0)
    assert r["floor"] == pytest.approx(0.1486, abs=5e-4)
    assert r["verdict"] == "SEPARATED"
    assert r["control_ok"] is True
    assert r["control_ratio"] == pytest.approx(3.19, abs=0.02)
    assert r["median_ratio"] == pytest.approx(2.68, abs=0.02)
    assert min(r["ratios"].values()) >= 2.0, "every scene separated, not just the median"


def test_the_headline_claim_survives_the_harshest_floor():
    """C46's load-bearing number must not depend on which within-scene control is chosen.

    "9 of 9 scenes separated" does depend on it: under the most conservative floor (the largest
    of the four controls) two scenes fall below 2x and it becomes 7 of 9. What survives is the
    floor-independent comparison, because it is a ratio of two distances and the floor cancels.
    Pinned so a later edit cannot promote the fragile half back to the headline.
    """
    import statistics as st
    within = {0: 0.0641, 1: 0.1378, 2: 0.1818, 3: 0.1594}
    between = {1: 0.4069, 2: 0.3304, 3: 0.4149, 4: 0.3152, 5: 0.4478,
               6: 0.4653, 7: 0.3706, 8: 0.3793, 9: 0.3980}
    control = 0.4735

    harsh = summarise(within | {9: max(within.values())}, between, control, threshold=2.0)
    strict = {s: d / max(within.values()) for s, d in between.items()}
    assert sum(r >= 2.0 for r in strict.values()) == 7, "the fragile half: 7 of 9, not 9 of 9"
    assert min(strict.values()) == pytest.approx(1.73, abs=0.01)

    # the control fires under every floor choice, so no reading makes this an instrument failure
    for floor in (min(within.values()), st.median(within.values()), max(within.values())):
        assert control / floor >= 2.0

    # the claim C46 actually rests on
    assert st.median(between.values()) / control == pytest.approx(0.84, abs=0.01)
    assert min(between.values()) / control == pytest.approx(0.67, abs=0.01)
    assert harsh["verdict"] in ("SEPARATED", "NOT SEPARATED")   # interpretable either way


def test_the_train_regime_replication_reproduces_from_its_own_numbers():
    """Second regime, same conclusion -- pinned like the first so the entry cannot drift.

    Raw TV distances from `python scripts/probe_scenes.py --mode train`, Door, 2026-08-18.
    The floor halves when per-reset randomisation is removed while the between-scene distance
    barely moves, which is what "scene is a separate axis from appearance" predicts.
    """
    import statistics as st
    within = {0: 0.0780}          # median of the four controls recorded in C46
    between_median, control = 0.4421, 0.4666
    r = summarise({0: 0.0780, 1: 0.0780}, {1: between_median}, control, threshold=2.0)
    assert r["verdict"] == "SEPARATED" and r["control_ok"]
    assert r["control_ratio"] == pytest.approx(5.98, abs=0.02), (
        "the control no longer reproduces C19's independently-measured 6-7x for the mode axis")
    assert between_median / control == pytest.approx(0.95, abs=0.01)


def test_the_positive_control_must_use_a_different_regime_than_the_one_tested():
    """The control was hardcoded as 'vs train', which is degenerate when testing `--mode train`.

    It compared train against train, measured TV 0.0245, and reported FAILED -- the guard worked,
    but the run was wasted. Pinned as a property of the source because the fix is a choice of
    regime made before any environment is built.
    """
    src = (pathlib.Path(__file__).resolve().parents[1] / "scripts" / "probe_scenes.py").read_text()
    assert 'ctrl_mode = "eval-easy" if a.mode == "train" else "train"' in src, (
        "the positive control regime is no longer chosen relative to the regime under test; "
        "with --mode train it degenerates to comparing a regime against itself")


def test_the_recorded_pairwise_structure_supports_the_centrality_claim():
    """C46 claims scene 0 is the most CENTRAL of the ten, which is load-bearing.

    It is the reason the entry concludes that what remains is a coverage claim rather than a bias
    claim: if the one scene we evaluate is the centroid, our number is the least unrepresentative
    single choice available. Pinned from the recorded 45-pair matrix (Door, eval-easy,
    2026-08-18) so the arithmetic behind that sentence cannot drift out of it.
    """
    import statistics as st
    mean_dist = {0: 0.3885, 1: 0.4203, 2: 0.4152, 3: 0.4481, 4: 0.4610,
                 5: 0.4479, 6: 0.4212, 7: 0.4086, 8: 0.3984, 9: 0.4046}
    vals = list(mean_dist.values())
    assert min(vals) == mean_dist[0], "scene 0 is no longer the most central"
    assert sorted(mean_dist, key=mean_dist.get)[0] == 0
    # spread: modest, so "most central" is a rank claim and not a large-effect claim
    assert st.pstdev(vals) == pytest.approx(0.0225, abs=5e-4)
    z = (mean_dist[0] - st.mean(vals)) / st.pstdev(vals)
    assert z == pytest.approx(-1.46, abs=0.02), "the centrality z-score moved"
    assert -2.0 < z, "z is reported as suggestive, not significant; a stronger claim needs seeds"
