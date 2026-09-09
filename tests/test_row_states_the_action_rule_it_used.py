"""A row's `eval_policy_mode` must be what the evaluator DID, not the family's default.

## The defect

`normalize_curves.py` built a row's `conventions` from `CONVENTIONS.get(baseline)` -- a static
per-baseline table -- so a `--policy-mode mode` pass was stamped with the family's NATIVE rule.
Its own header (`:57-61`) states the requirement exactly right and the code did the opposite:

    `eval_policy_mode` ... records the action rule used by the evaluator that produced the row,
    not merely whether the original repository shipped a suitable evaluator ... Two runs whose
    returns differ because one sampled and one did not are not comparable, and the row must say
    which happened.

Measured on `card0-20260909-035152`: all 85 endpoint rows claimed `sample`, while
`evaluator_scope` correctly held 41 `mode` and 44 `sample`. Two pooled rows per regime carried
the SAME label and different means -- eval-medium 11.55 and 14.32, train 33.69 and 34.00 -- so a
reader keying on `conventions` saw 400 episodes per regime where there were 200 each of two
estimands `SAME-AXES-VERDICT.md` forbids pooling. That is where an earlier note's "400 episodes"
came from.

`scripts/audit_row_closure.py` read `conventions.eval_policy_mode`, so the audit whose purpose is
to prevent this pooling was reading the one field that could not distinguish the passes.

## The aliasing hazard, which the fix had to introduce a copy to avoid

`CONVENTIONS.get(baseline)` returns the SAME mapping object to every row of that baseline. The old
code assigned it straight onto the record, so writing `row["conventions"]["eval_policy_mode"]`
would have edited the module-level table and every row built afterwards. The override is exactly
such a write, so `dict(...)` is load-bearing, not tidiness.
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "datasphere" / "native"))
sys.path.insert(0, str(ROOT / "scripts"))


def _record_builder():
    """`normalize_curves.record`, by name.

    Deliberately not a search over candidate names ending in `pytest.skip`: a rename would then
    make every test below silently not run, which is this project's own "an instrument that could
    not run must never read as one that ran". A rename should break this line loudly instead.
    """
    import normalize_curves
    return normalize_curves.record


def test_a_mode_pass_is_not_stamped_as_the_family_default():
    build_row = _record_builder()
    row = build_row(baseline="idaac", regime="train", frame=598016,
                    evaluator_scope={"eval_policy_mode": "mode"})
    assert row["conventions"]["eval_policy_mode"] == "mode", (
        "a --policy-mode mode pass is still stamped with idaac's native `sample`; a reader keying "
        "on conventions will pool two estimands"
    )


def test_the_family_default_still_applies_when_the_scope_is_silent():
    build_row = _record_builder()
    row = build_row(baseline="idaac", regime="train", frame=598016)
    assert row["conventions"]["eval_policy_mode"] == "sample"   # idaac's native rule
    row = build_row(baseline="drqv2", regime="train", frame=1000)
    assert row["conventions"]["eval_policy_mode"] == "mode"     # nine families take the mode


def test_the_override_does_not_edit_the_shared_table():
    """The aliasing hazard: one row's stamp must not become every later row's stamp."""
    import normalize_curves
    before = dict(normalize_curves.CONVENTIONS["idaac"])
    build_row = _record_builder()
    build_row(baseline="idaac", regime="train", frame=1,
              evaluator_scope={"eval_policy_mode": "mode"})
    assert normalize_curves.CONVENTIONS["idaac"] == before, (
        "the module-level CONVENTIONS table was mutated by building one row"
    )
    later = build_row(baseline="idaac", regime="train", frame=2)
    assert later["conventions"]["eval_policy_mode"] == "sample", (
        "a previous row's mode override leaked into a later row"
    )


def test_the_audit_reports_a_row_that_contradicts_itself(tmp_path):
    import audit_row_closure
    path = tmp_path / "r.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in [
        {"baseline": "idaac", "regime": "train", "frame": 598016,
         "evaluator_scope": {"eval_policy_mode": "mode"},
         "conventions": {"eval_policy_mode": "sample"}},
        {"baseline": "idaac", "regime": "train", "frame": 598016,
         "evaluator_scope": {"eval_policy_mode": "sample"},
         "conventions": {"eval_policy_mode": "sample"}},
    ]) + "\n")
    found = audit_row_closure.policy_mode_disagreements([path])
    assert len(found) == 1 and found[0][4] == "mode" and found[0][5] == "sample"


def test_the_audit_groups_by_the_authoritative_field():
    """Grouping must use the scope, or the two passes land in one closure group."""
    import audit_row_closure
    getter = dict((name, fn) for name, fn, in
                  ((n, f) for n, f in audit_row_closure.CLOSURE_FIELDS))["eval_policy_mode"]
    assert getter({"evaluator_scope": {"eval_policy_mode": "mode"},
                   "conventions": {"eval_policy_mode": "sample"}}) == "mode"
    # ...and old records with no scope still resolve through conventions.
    assert getter({"conventions": {"eval_policy_mode": "sample"}}) == "sample"
