"""`scripts/requirements.py` — R1-R7 against the repo, recomputed rather than remembered.

`docs/TASK.md` routes "state of the code against this contract" to `REVIEW.md`, which is a dated
snapshot (2026-08-09, and at a different repository path). It says R1 is "not met — the repo's
only non-vendor .sh is submit_kaggle.sh"; there are now thirteen `train.sh` files. The snapshot is
not wrong, it is a photograph — but it was the only answer to the first question an outside reader
asks, and it was ten days old.

The failure to guard against here is a checker that grades what it cannot demonstrate. Two of the
seven turn on judgements a script has no access to and one needs a run; those must never print
MET.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import requirements as R  # noqa: E402

# [Claude 2026-09-04: R4 moved from JUDGEMENT to MECHANICAL, and the reason is that its question
# changed hands, not that this test was relaxed to let a new verdict through.
#
# R4 asks whether the twelve can be given an EQUAL training length. That was treated as a
# judgement while `r4()` said "no run set exists yet to compare budgets across" -- but the question
# never needed results: each family's executed budget is its request rounded to its own rollout
# quantum, which the descriptors state. Computed, the seven runner families that carry the twelve
# baselines execute 599,040-600,064 frames against a 600,000 request: equal to 0.17%, and the
# residual is arithmetic no one can choose away without editing a clone.
#
# What stays a judgement is the BUDGET ITSELF (§3b #5) -- a different question, and one this file
# must not let `r4()` answer. R6 and R7 stay here: R6 needs someone to accept the evidence
# `audit_implementations.py` produces, and R7 needs a person on a clean machine.]
MECHANICAL = {"R1", "R2", "R3", "R4", "R5"}
JUDGEMENT = {"R6", "R7"}


def test_all_seven_criteria_are_covered():
    assert set(R.CHECKS) == MECHANICAL | JUDGEMENT


def test_no_judgement_criterion_is_ever_graded_met():
    """A script that grades 'genuine implementations' would be asserting what it cannot see."""
    for rid in JUDGEMENT:
        state, _ = R.CHECKS[rid][1]()
        assert state != "MET", f"{rid} reported MET; it is not mechanically decidable"


def test_r5_does_not_count_the_checker_itself_as_a_plotter():
    """The defect this checker shipped with, for one run.

    Its first version regex-matched "matplotlib" in any file under scripts/ — including its own
    source, whose search pattern contains the word. R5 came back MET, evidence
    "plotter (requirements.py)". A checker that satisfies its own predicate is exactly the vacuity
    failure this project has recorded twice before.
    """
    state, why = R.r5()
    assert "requirements.py" not in why, "the checker matched itself as evidence again"
    assert state == "PARTLY", (
        f"R5 is {state}. If a real plotter was added, say so here and in the register; if the "
        "collector stopped covering twelve, that is a regression")


def test_r3_grades_the_relaxed_requirement_not_the_withdrawn_one():
    """R3 was relaxed 2026-08-26; a predicate still failing it for identity would be false evidence.

    The old predicate counted per-baseline parsers in `collect_metrics.py` and graded NOT MET
    because twelve exist. Under *"metrics fully on the same axes and directly comparable"* twelve
    parsers are not a violation at all — they are the hermetic null working. A checker that keeps
    failing a requirement for a reason the requirement no longer contains looks like evidence and
    is not, so this pins that the grade now comes from the seam audit's axes.
    """
    state, why = R.r3()
    assert state in ("NOT MET", "NEEDS JUDGEMENT"), f"R3 graded {state}"
    assert "parsers" not in why, (
        "R3 is being graded on per-baseline parser count again — that is the WITHDRAWN "
        "requirement, not the relaxed one")
    assert any(k in why for k in ("UNITS", "CONDITIONS", "underived", "enumeration")), (
        f"R3's reason no longer refers to the comparability axes it is supposed to grade: {why}")


def test_r3_can_never_grade_itself_met():
    """The null is non-comparability, and no mechanical predicate may be the thing that lifts it.

    Drives the REAL `requirements.r3` — via its `audit` injection point, not a re-implementation —
    to the most favourable input it can ever receive: every axis uniform, nothing left underived.
    It must still stop at NEEDS JUDGEMENT, because whether the axis enumeration is COMPLETE is a
    judgement about unknown unknowns and the owner's, not a checklist result. If this ever returns
    MET, a script has silently concluded that two baselines' numbers are the same quantity.
    """
    import importlib.util
    import types

    spec = importlib.util.spec_from_file_location(
        "_acs_probe", ROOT / "scripts" / "audit_comparability_seam.py")
    real = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(real)

    forced = types.SimpleNamespace(
        BASELINES=real.BASELINES,
        UNITS=real.UNITS,
        VALUE_OF={},
        AXES=[(t, k, lambda: ({b: "identical" for b in real.BASELINES}, "DERIVED"))
              for t, k, _ in real.AXES],
        NOT_COVERED=[],
    )
    state, why = R.r3(audit=forced)
    assert state == "NEEDS JUDGEMENT", (
        f"with every axis uniform and nothing underived, R3 graded {state!r} — a script concluded "
        "comparability, which the null forbids")
    assert "unknown unknowns" in why


def test_r3_reports_not_met_when_a_units_axis_splits():
    """The other direction: a split in what a number MEANS must never be softened to a judgement."""
    import importlib.util
    import types

    spec = importlib.util.spec_from_file_location(
        "_acs_probe2", ROOT / "scripts" / "audit_comparability_seam.py")
    real = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(real)

    def split():
        return ({b: ("A" if i < 6 else "B") for i, b in enumerate(real.BASELINES)}, "DERIVED")

    forced = types.SimpleNamespace(
        BASELINES=real.BASELINES, UNITS=real.UNITS, VALUE_OF={},
        AXES=[("reward pipeline", real.UNITS, split)], NOT_COVERED=[])
    state, why = R.r3(audit=forced)
    assert state == "NOT MET" and "MEANS" in why, (
        f"a UNITS split graded {state!r}: {why}")


def test_r1_and_r2_are_measured_against_the_registry_not_a_constant():
    """If a baseline is added, the requirement must cover it without anyone editing this test."""
    want = R.implemented()
    assert len(want) == 12
    for rid in ("R1", "R2"):
        state, why = R.CHECKS[rid][1]()
        assert str(len(want)) in why, f"{rid} does not report its coverage against the registry"


def test_r4_ignores_descriptor_metadata_when_computing_budgets():
    """Host-profile metadata must not become a fictional runner family.

    R4 deliberately derives its answer from the same descriptor consumed by the runner.  The
    descriptor also carries top-level metadata, so this pin prevents a future metadata addition
    from turning the requirement report into an ``unknown family`` abstention.
    """
    state, why = R.r4()
    assert state in {"MET", "NEEDS JUDGEMENT"}
    assert "could not compute" not in why
