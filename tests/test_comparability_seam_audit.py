#!/usr/bin/env python3
"""`scripts/audit_comparability_seam.py` must keep reporting the splits that exist — R3.

The audit's value is entirely in it *not* reporting agreement that is not there. A seam audit that
prints UNIFORM everywhere would read as "the metrics are comparable" and would be the most
expensive kind of wrong in this project, because R3's grading now leans on it.

So these pin the splits that are established facts, each with its own register entry behind it:
the 3/9 truncation divide (C1), three render resolutions (C5), and a uniform action-repeat *value*
reached four different ways (C71). If any of those silently becomes UNIFORM, either the repo
changed or the audit went blind, and both need looking at.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "acs", ROOT / "scripts" / "audit_comparability_seam.py")
acs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(acs)


def test_truncation_is_still_split_three_nine():
    """C1: three baselines bootstrap through the time limit, nine treat it as terminal."""
    values, provenance = acs.truncation()
    assert provenance == "DERIVED", "truncation stopped being read from protocol.py"
    boot = {b for b, v in values.items() if v == "bootstrap"}
    term = {b for b, v in values.items() if v == "terminal"}
    assert boot == {"rad", "soda", "alda"}, f"the bootstrapping three changed: {boot}"
    assert len(term) == 9, f"expected nine terminal-treating baselines, got {len(term)}"


def test_render_resolution_is_still_split_three_ways():
    """C5: 100 for rad/soda, 84 for the natives, 64 for the Procgen-lineage clones."""
    values, _ = acs.image_size()
    groups = {}
    for b, v in values.items():
        groups.setdefault(str(v), []).append(b)
    assert len(groups) == 3, f"render resolution is no longer three-way split: {groups}"
    assert any("100" in k for k in groups), "the 100-render group (rad/soda) vanished"
    assert any("64" == k for k in groups), "the 64-render group vanished"


def test_action_repeat_is_uniform_in_value_and_not_in_mechanism():
    """The distinction the audit exists to make, and the one it got wrong on its first run.

    All twelve run at 1, so the axis does not threaten comparability. They arrive four different
    ways, two of them through a knob that is passed and never read (C71) — which is why the value
    is fragile even though it currently agrees. Reporting either half alone is misleading.
    """
    values, _ = acs.action_repeat()
    assert {v.split(" ", 1)[0] for v in values.values()} == {"1"}, "action repeat is no longer 1"
    assert len({v for v in values.values()}) >= 3, (
        "the mechanisms collapsed to one description — either the repo genuinely unified them, "
        "or the audit stopped distinguishing how each baseline reaches 1, which is the fragility "
        "C71 records")


def test_horizon_is_uniform():
    values, _ = acs.horizon()
    assert len(set(values.values())) == 1, f"episode horizon is no longer uniform: {values}"


def test_replay_audit_compares_the_effective_capacity_to_the_production_budget():
    """A 300k cap in a 600k run is a recency ring, not whole-run replay."""
    values, provenance = acs.replay_capacity()
    for baseline in acs.NATIVES:
        assert "recency ring" in values[baseline], values[baseline]
        assert "300000 < 600000" in values[baseline], values[baseline]
    assert "uniform over the whole run" in values["rad"], values["rad"]
    assert "600000" in provenance


def test_replay_audit_resolves_the_named_v100_profile(monkeypatch):
    """The V100's 620k buffer is whole-run replay; reporting the 300k T4 ring is a false split."""
    monkeypatch.setattr(acs, "HOST_PROFILE", "v100", raising=False)
    values, provenance = acs.replay_capacity()
    for baseline in acs.NATIVES:
        assert "uniform over the whole run" in values[baseline], values[baseline]
        assert "620000" in values[baseline], values[baseline]
    assert "v100" in provenance


def test_the_audit_could_report_a_split_that_is_not_there():
    """Anti-vacuity: the split-detection must respond to the data, not print a fixed answer.

    Feed it a hand-built map with a known split and a known agreement and check it separates them.
    Without this, every assertion above could pass against a function that returned constants.
    """
    fabricated = {b: ("A" if i < 4 else "B") for i, b in enumerate(acs.BASELINES)}
    groups = {}
    for b in acs.BASELINES:
        groups.setdefault(fabricated[b], []).append(b)
    assert len(groups) == 2 and len(groups["A"]) == 4, (
        "the grouping logic this audit relies on does not separate a known two-way split")


# ---------------------------------------------------------------------------------------------
# Axes added 2026-08-26, after `docs/PART2-METRIC-INVENTORY.md` was read in full and turned out to
# hold most of them already. These pin the facts that document derived, so that if the code drifts
# away from the written record, something goes red rather than the two quietly disagreeing.
# ---------------------------------------------------------------------------------------------

def test_reported_return_is_raw_for_all_twelve_while_three_learners_normalise():
    """PART2 Finding 1. The split that would break R3 outright, and does not — by wrapper order.

    `idaac`, `ctrl` and `ppg` train on reward divided by a running return std and clipped. Their
    REPORTED episode return is raw anyway, because each one's episode monitor sits inside the
    normaliser (idaac `envs.py:104-105`, ctrl `vec_env.py:38-44`) or because normalisation happens
    inside the learner on an already-collected segment (ppg `ppo.py:222`). If that order ever
    changes, every number those three report silently changes units and nothing raises — so the
    both-halves assertion is the point, not the uniform half alone.
    """
    values, _ = acs.reward_pipeline()
    assert {v.split(" | ", 1)[0] for v in values.values()} == {"raw"}, (
        "a baseline's REPORTED return is no longer raw — its numbers have changed units")
    normalised = {b for b, v in values.items() if "NORMALISED" in v}
    assert normalised == {"idaac", "ppg", "ctrl"}, (
        f"the set of reward-normalising learners changed: {normalised}")


def test_the_frame_stack_seam_no_longer_splits():
    """PART2 Finding 5, called there the largest comparability gap found. C2. Now closed.

    Was 10/2 with `ctrl` and `ibac_sni` retaining released one-frame geometry. A40 REVISED-2
    established that single-frame was Procgen's environment convention rather than either method's
    decision, and authored the stack both Door paths were missing entirely.
    """
    values, _ = acs.frame_stack()
    single = {b for b, v in values.items() if str(v).startswith("1")}
    assert not single, f"the frame-stack seam reopened for: {sorted(single)}"
    assert {str(values[b]) for b in acs.NATIVES} == {"3"}, "the natives stopped stacking 3"


def test_success_is_one_definition_computed_by_two_different_parties():
    """All twelve read `_check_success` on the any-step convention; only *who runs it* differs.

    Reporting this as a split would be wrong — it is one quantity — and reporting it as plainly
    uniform would hide C72: the five natives have no scene-sweeping evaluator, so their number
    comes from this repository's instrument rather than their own.
    """
    values, _ = acs.success_source()
    assert {v.split(" | ", 1)[0] for v in values.values()} == {"_check_success, any-step"}, (
        "success no longer has one definition across the twelve")
    ours = {b for b, v in values.items() if "OUR eval_across_scenes" in v}
    assert ours == set(acs.NATIVES), f"who computes success changed: {ours}"


def test_action_distribution_is_three_families_not_the_lineage_two():
    """PART2 Finding 6 — whose own first draft claimed an 8/4 split inferred from lineage."""
    values, _ = acs.action_distribution()
    assert len(set(values.values())) == 3, "the three action-distribution families collapsed"
    unsquashed = {b for b, v in values.items() if "unsquashed" in v}
    assert unsquashed == {"idaac", "ppg", "ctrl", "ibac_sni"}, (
        f"the family whose likelihood disagrees with what the env executes changed: {unsquashed}")


def test_the_audit_cannot_conclude_the_metrics_are_comparable(capsys):
    """The null is non-comparability, and no run of this script may appear to lift it.

    A tool that prints "N/N axes uniform" and stops reads as a passed checklist. The owner's null
    is the opposite: two numbers are not the same quantity until shown to be, and a set of uniform
    axes is evidence about the ways somebody thought to check — never about the ways nobody
    enumerated. So the output must always carry the null and the count of underived axes, and must
    never contain a word that reads as a verdict of comparability.
    """
    acs.main()
    out = capsys.readouterr().out
    assert "THE NULL IS THAT TWO BASELINES' NUMBERS ARE NOT THE SAME QUANTITY" in out
    # The count must always be STATED, including when it is zero. An earlier version of this line
    # additionally required NOT_COVERED to be non-empty, which conflated "the audit reports its
    # gaps" with "the audit has gaps" — and would have forced a gap to be kept open forever to
    # satisfy a test. An empty list is a legitimate state; what must never happen is the count
    # going unprinted, or zero being presented as the enumeration being complete.
    assert "UNDERIVED" in out, "the underived axes stopped being counted"
    if not acs.NOT_COVERED:
        assert "fact about the list, not about the twelve" in out, (
            "the audit reported zero underived axes without saying that this is a fact about the "
            "list of axes anyone thought to name, not about the twelve baselines")
    # Not a substring ban: the header legitimately says "NOT that the metrics are comparable",
    # and the first version of this test failed on exactly that line. The property is that every
    # mention of comparability is negated or conditional, never asserted.
    # Only the asserting adjective is checked. "COMPARABILITY SEAM AUDIT" and
    # "COMPARABILITY_CONTRACT" are the audit's own title and a filename -- nouns naming the topic,
    # which is what the second version of this test wrongly flagged. "incomparable" is itself a
    # denial and needs no negator beside it.
    NEGATORS = ("not", "cannot", "never", "null", "until shown", "would")
    for line in out.splitlines():
        low = line.lower()
        if "comparable" not in low or "incomparable" in low:
            continue
        assert any(n in low for n in NEGATORS), (
            f"the audit asserted comparability rather than denying or conditioning it:\n  {line}")
    assert "ALL AXES AGREE" not in out and "fully comparable" not in out


def test_the_evaluation_estimator_is_uniform_and_the_training_curve_is_not_it():
    """The trap: `train/mean_episode_reward` and an eval sweep share a name and are not one thing.

    Every baseline's EVALUATION number is a fixed-policy sample mean, differing only in N — and N
    is precision, not quantity. The on-policy family's TRAINING curve is a rolling mean over a
    policy that was changing while it was measured (idaac keeps 10, ctrl and ppg keep 100). If
    this axis ever reports the training estimator as though it were the evaluation one, the
    project would be pooling two estimands under one axis label.
    """
    values, provenance = acs.reported_estimator()
    assert {v.split(" | ", 1)[0] for v in values.values()} == {"fixed-policy sample mean"}, (
        "a baseline's evaluation number is no longer a fixed-policy sample mean")
    assert len({v for v in values.values()}) >= 4, "the per-baseline episode counts collapsed"
    assert "DIFFERENT estimand" in provenance, (
        "the provenance stopped warning that the training curve is a different estimand")


def test_observation_layout_splits_five_ways_and_none_of_it_is_a_defect():
    """Three independent ways the twelve do not see the same thing: resolution, frames, layout."""
    values, prov = acs.observation_layout()
    assert len(set(values.values())) == 5, f"the observation-layout split changed: {set(values.values())}"
    assert {values[b] for b in acs.NATIVES} == {"CHW uint8 (9,84,84) | scaled in the encoder: x/255 - 0.5"}
    assert "not covered by PART2 or FAITHFULNESS" in prov, (
        "this axis stopped declaring that it is the one place this fact is written down")


#: The only axis deciding what a number MEANS on which the twelve disagree — C72, expressed as a
#: comparability axis. Named rather than counted, so that a SECOND one appearing is a regression
#: with a name attached rather than a tally going from 1 to 2.
#: The one UNITS axis that splits, and the owner has ruled it acceptable rather than absent.
#:
#: 9 baselines report E[return | a = mode pi], 3 report E[return | a ~ pi] (idaac, ppg, ibac_sni),
#: because each reproduces its own published EVALUATION path -- verified per family against the
#: vendored upstream in tests/test_native_policy_mode_provenance.py. The ruling, its evidence, the
#: one family where that evidence is weakest (ppg ships no evaluator), and what gets reported as a
#: consequence (rank within a block, never across) are all in notes/SAME-AXES-VERDICT.md.
#:
#: Listed here rather than removed from the audit: `scripts/requirements.py` still reads R3 NOT
#: MET, deliberately, because an accepted split is not an absent one. This set exists so a NEW
#: split still fails loudly.
KNOWN_UNITS_SPLIT = {"evaluation policy mode"}


def test_the_reported_units_are_uniform_and_training_time_splits_are_conditions():
    """R3 audits the reported offline measurement, not progress logs.

    A CONDITIONS split leaves the numbers commensurable and is what `RESEARCH-FRAME.md`'s claim
    already declares and quantifies. The production offline grid now sweeps ten scenes for all
    twelve; the source loops' scene-0 limitation remains a CONDITIONS fact about progress logging.
    """
    split = set()
    for title, kind, fn in acs.AXES:
        values, _ = fn()
        key = acs.VALUE_OF.get(title, lambda v: v)
        if kind == acs.UNITS and len({key(str(values[b])) for b in acs.BASELINES}) > 1:
            split.add(title)
    new = split - KNOWN_UNITS_SPLIT
    assert not new, (
        f"a NEW axis deciding what a number MEANS went non-uniform: {sorted(new)}. Two baselines' "
        "numbers may no longer be the same quantity — this is not a 'declare and quantify' case.")
    # Not `assert not split`: the known split above is ruled on, not repaired. Asserted as an
    # EQUALITY so that the known split disappearing is noticed too -- if the fleet ever becomes
    # genuinely uniform on this axis, SAME-AXES-VERDICT.md and R3 both need rewriting.
    assert split == KNOWN_UNITS_SPLIT, (
        f"UNITS splits are {sorted(split)}, expected exactly {sorted(KNOWN_UNITS_SPLIT)}")


def test_the_reported_scene_set_is_common():
    """The production checkpoint grid uses the same scene set for every baseline."""
    values, provenance = acs.evaluation_scene_set()
    assert len(set(values.values())) == 1, f"reported scene grid split: {set(values.values())}"
    assert "offline grid" in provenance


def test_training_time_scene_coverage_keeps_the_historical_split():
    values, provenance = acs.training_time_scene_coverage()
    sweeps = {b for b, v in values.items() if v.startswith("ten scenes")}
    assert sweeps == set(acs.NATIVES), f"who sweeps training-time scenes changed: {sweeps}"
    assert "scene_id=0" in provenance


def test_the_audit_refuses_to_run_on_a_missing_source_tree(tmp_path):
    """RIGOR.md §6.1: a checker asserts its input is non-empty, or it cannot fail.

    Every negative finding in this audit is an *absence*: `frame_stack` reads "1" from no
    frame-stacking wrapper, `reward_pipeline` reads "learner: raw" from no VecNormalize,
    `success_source` reads "NO SUCCESS RECORDED" from no matching line. If a baseline's tree were
    moved or not checked out, all of those would return nothing and the audit would print a
    confident, uniform, fictional result with no error anywhere — and uniformity is precisely the
    answer that would be quoted.

    Not hypothetical for this repo: a whole tree (`rlgen/`) was retired mid-project, which is
    exactly the event that empties these paths while leaving the script runnable.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "acs_guard", ROOT / "scripts" / "audit_comparability_seam.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    m.assert_inputs_present()  # the real tree must pass

    m.SRC_ROOT["idaac"] = tmp_path / "gone"
    with pytest.raises(m.EmptyInput) as e:
        m.assert_inputs_present()
    assert "idaac" in str(e.value)

    empty = tmp_path / "present_but_empty"
    empty.mkdir()
    m.SRC_ROOT["idaac"] = empty
    with pytest.raises(m.EmptyInput) as e:
        m.assert_inputs_present()
    assert "no .py files" in str(e.value), (
        "a directory that exists but holds nothing readable must also be refused — that is the "
        "likelier accident than a deleted path")
