#!/usr/bin/env python3
"""R1-R7 from the brief, checked against the repo as it is now.

## Why this exists

`docs/TASK.md` is the contract and says so: *"If the repo and this file disagree, one of them is
wrong and the disagreement is itself a finding."* It routes the reader to `REVIEW.md` for
*"state of the code against this contract"*.

`REVIEW.md` is a **dated snapshot** — 2026-08-09, and its header records a different repository
path. It is correctly scoped and it is not stale in the sense of being wrong; it is a photograph.
But it is the only place requirement status lives, so the question an outside reader asks first —
*did you meet the brief?* — has had no current answer for ten days. R1 reads "not met — the repo's
only non-vendor .sh is submit_kaggle.sh", and there are now thirteen `train.sh` files.

So requirement status belongs in the **Measurement** layer of `docs/SYSTEM.md`'s table:
recomputed, never remembered. This does not replace `REVIEW.md`'s judgement, and it does not try
to: it reports what can be checked mechanically and **refuses to assert the rest**.

## What it will not do

Say MET for anything it cannot demonstrate. R4 (equal budget "unless the algorithm forbids it")
and R6 ("genuine implementations") turn on judgements a script has no access to, and R7 needs a
run. Those print NEEDS JUDGEMENT with what is known, which is the honest output — a checker that
graded them would be the vacuous-predicate failure this project has already recorded twice.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def implemented() -> set[str]:
    from rlgen.registry import BASELINES
    return {n for n, s in BASELINES.items()
            if s.status == "implemented" and n != "random" and not n.startswith("__")}


def r1() -> tuple[str, str]:
    want = implemented()
    have = {p.parent.name for p in (ROOT / "baselines").glob("*/train.sh")}
    missing = want - have
    if missing:
        return "NOT MET", f"no train.sh for {', '.join(sorted(missing))}"
    return "MET", f"baselines/<X>/train.sh present for all {len(want)}"


def r2() -> tuple[str, str]:
    want = implemented()
    have = {p.parent.name for p in (ROOT / "baselines").glob("*/README.md")
            if p.stat().st_size > 200}
    missing = want - have
    if missing:
        return "NOT MET", f"no substantive README for {', '.join(sorted(missing))}"
    return "MET", f"a non-trivial README under baselines/<X>/ for all {len(want)}"


def r3(audit=None) -> tuple[str, str]:
    """Graded against the RELAXED R3, and it can never return MET on its own. See below.

    R3 was *"код эвалюэйшена должен быть ИДЕНТИЧЕН у всех бейзлайнов"* and was relaxed by the
    owner on 2026-08-26 to **"evaluation code should produce metrics that are fully on the same
    axes and directly comparable"**. The previous predicate here counted per-baseline parsers in
    `collect_metrics.py` and graded NOT MET because twelve parsers exist -- which is grading the
    OLD requirement. Under the relaxed one, twelve parsers reading one quantity is not a violation
    at all; it is the hermetic null working as designed. A predicate that keeps failing a
    requirement for a reason the requirement no longer contains is worse than no predicate, because
    it looks like evidence.

    So this now asks the relaxed question, through `scripts/audit_comparability_seam.py`:

    - **UNITS** axes decide what a reported number *means*. A split here makes two numbers
      incommensurable and R3 cannot hold.
    - **CONDITIONS** axes decide what was *measured*. A split here is survivable -- it is what
      `RESEARCH-FRAME.md`'s claim declares and quantifies rather than equalises -- provided each
      split is actually declared.
    - **UNDERIVED** axes are the ones nobody has checked. While any remain, the enumeration is
      incomplete by the audit's own admission.

    **Why MET is unreachable from here.** The null is that two baselines' numbers are NOT the same
    quantity (project `CLAUDE.md`; owner, 2026-08-26: *"the reasonable absence of unknown unknowns
    should be established before they're concluded same"*). A finite list of uniform axes removes
    the ways somebody thought to check; it says nothing about the ways nobody enumerated, and
    completeness is a judgement rather than a checklist result. The best grade a script may
    therefore reach is **NEEDS JUDGEMENT**, with the enumeration handed over -- exactly as R4 and
    R6 already do. Anything stronger would be this project's vacuous-predicate failure a third
    time.
    """
    # `audit` is an injection point for the test that drives this predicate to its most
    # favourable input (every axis uniform, nothing underived) and requires it to STILL refuse to
    # grade MET. Without it the test would have to re-implement the rule below, which is not a
    # test of the rule. Production callers pass nothing.
    acs = audit
    if acs is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_acs", ROOT / "scripts" / "audit_comparability_seam.py")
        acs = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(acs)

    units_split, cond_split = [], []
    for title, kind, fn in acs.AXES:
        values, _ = fn()
        key = acs.VALUE_OF.get(title, lambda v: v)
        if len({key(str(values[b])) for b in acs.BASELINES}) > 1:
            (units_split if kind == acs.UNITS else cond_split).append(title)
    n_underived = len(acs.NOT_COVERED)

    if units_split:
        return "NOT MET", (
            f"{len(units_split)} UNITS axis/axes -- the ones deciding what a number MEANS -- "
            f"disagree across the twelve ({'; '.join(units_split)}). Numbers differing on a UNITS "
            "axis are not the same quantity, and no declaring or rescaling repairs that: it has to "
            "be removed or converted. The CONDITIONS splits are survivable; this is not")
    if n_underived:
        return "NOT MET", (
            f"every derived UNITS axis is uniform and all {len(cond_split)} splits are CONDITIONS "
            f"({'; '.join(cond_split)}) -- which the claim declares rather than equalises -- but "
            f"{n_underived} named axis/axes have never been derived by anything, so the "
            "enumeration is incomplete by the audit's own account. Run "
            "`python scripts/audit_comparability_seam.py` for the list")
    return "NEEDS JUDGEMENT", (
        f"every derived UNITS axis is uniform, all {len(cond_split)} splits are CONDITIONS and "
        "declared, and no axis is left underived. What remains is not mechanical: whether the "
        "enumeration is COMPLETE is a judgement about unknown unknowns, and the null is "
        "non-comparability until that judgement is made and recorded")


def r4() -> tuple[str, str]:
    return "NEEDS JUDGEMENT", (
        "equal budget 'unless the algorithm forbids it' -- the exception is the judgement, and "
        "no run set exists yet to compare budgets across")


def r5() -> tuple[str, str]:
    import re
    # Detect an actual IMPORT, not a mention. The first version regex-matched "matplotlib" in any
    # file and so matched THIS one, whose own source contains the word -- reporting R5 MET with
    # "plotter (requirements.py)". A checker that satisfies its own predicate is the vacuity
    # failure `docs/SYSTEM.md` records; it took one run to appear here too.
    import ast as _ast
    plot = []
    for f in (ROOT / "scripts").glob("*.py"):
        if f.name == pathlib.Path(__file__).name:
            continue
        try:
            tree = _ast.parse(f.read_text(errors="replace"))
        except SyntaxError:
            continue
        for node in _ast.walk(tree):
            mods = ([a.name for a in node.names] if isinstance(node, _ast.Import)
                    else [node.module or ""] if isinstance(node, _ast.ImportFrom) else [])
            if any(m.split(".")[0] == "matplotlib" for m in mods):
                plot.append(f)
                break
    src = (ROOT / "scripts" / "collect_metrics.py").read_text(errors="replace")
    n = len(re.findall(r"def parse_([a-z_]+)", src))
    if not plot:
        return "PARTLY", (
            f"collection done: collect_metrics.py reads all twelve into one record shape via {n} "
            "parsers. Plotting absent -- no matplotlib/savefig anywhere in scripts/. Note the "
            "brief asked for 'no per-algorithm branch'; the branch was moved into the collector "
            "deliberately, which meets R5's OUTCOME and inverts its MECHANISM")
    # R5's check is four parts, and grading the whole thing on "a matplotlib import exists
    # somewhere" was an overclaim this file made the moment plot_curves.py landed. Graded per
    # item, because three of the four have different answers and two of those are easy to
    # misread as done:
    #   1. identical tag names ACROSS BASELINES -- open, and it is C53.
    #   2. a constants module owning the strings -- done: rlgen/tags.py, and
    #      test_no_tag_literals_outside_tags_module forbids literals at call sites.
    #   3. one script over event files, no per-algorithm branch -- done, plot_curves.py.
    #   4. a test that each baseline's emitted tag set equals the canonical one -- exists as
    #      test_every_runnable_baseline_emits_the_required_tags, BUT it builds agents from
    #      rlgen.registry against backend="synthetic". That is the SUPERSEDED rlgen/ port, not
    #      the twelve cloned originals that are the deliverable. Satisfied for the wrong tree.
    tags_mod = (ROOT / "rlgen" / "tags.py").exists()
    lit_test = "test_no_tag_literals_outside_tags_module" in (
        ROOT / "tests" / "test_eval_identity.py").read_text(errors="replace")
    done = sum((tags_mod and lit_test, bool(plot)))
    return "PARTLY", (
        f"{done} of 4 items done for the deliverable. (2) constants module: rlgen/tags.py with a "
        f"literals test. (3) one routine, no per-algorithm branch: {', '.join(p.name for p in plot)}. "
        "(1) identical tag names across baselines is C53 -- an open decision, not a work item. "
        "(4) the canonical-tag-set test exists but runs against rlgen/'s superseded port on a "
        "synthetic backend, not the twelve clones. Separately, only the five RL-ViGen-native "
        "baselines write tensorboard at all (C58), so 'every baseline's eval curve' is five of "
        "twelve")



def r6() -> tuple[str, str]:
    n = len(implemented())
    return ("NEEDS JUDGEMENT" if n == 12 else "NOT MET",
            f"{n} baselines declare `implemented` in rlgen/registry.py. Whether each is a GENUINE "
            "implementation is the judgement -- the registry's own docstring records three that "
            "were previously present in name only")


def r7() -> tuple[str, str]:
    """The chain `clone -> sh script -> log -> shared plotter -> eval curve`, graded link by link.

    This used to return a hardcoded string: *"Stage 8 (production) has not started; no result set
    exists, so there is no curve to reach."* **That stopped being true on 2026-08-20** and was
    flatly false by 2026-08-27, when [C81] and [C83] recorded completed retention measurements from
    two baselines. A requirement graded by a constant cannot notice the world changing under it,
    which is the same defect the R3 predicate had — and both said NOT MET / NEEDS RUN, so neither
    looked wrong.

    The links are now checked. One of them cannot be: R7's own text asks for the sequence to be
    run *"on a clean machine by someone who has not seen the repo"*, and no script can certify that
    — it is the acceptance test the supervisor will actually attempt. So the best reachable
    mechanical answer names which links hold and which does not, and leaves the rest explicitly to
    a person.
    """
    root = ROOT
    links = {}

    # 1. sh script per baseline -- R1 already grades this; reuse it rather than re-deriving.
    links["sh script"] = (r1()[0] == "MET")

    # 2. a log the plotter could read: any completed training run's own csv.
    logs = list((root / "RL-ViGen-upstream" / "exp_local").rglob("train.csv"))
    links["training log"] = bool(logs)

    # 3. an eval curve/result set: retention grids produced by the evaluator.
    grids = list((root / "results").rglob("*__train.json"))
    links["eval result set"] = len(grids) >= 2

    # 4. the shared plotter -- checked DIRECTLY, not inferred from R5's overall grade.
    #
    # The first version of this link read `r5()[0] == "MET"` and reported "there is no shared
    # plotting routine". **That was false**: `scripts/plot_curves.py` exists and imports
    # matplotlib. R5 is PARTLY for reasons that have nothing to do with the plotter's existence --
    # identical tag names across baselines is C53, an OPEN OWNER DECISION, and its canonical-tag
    # test runs against the superseded port. Grading one requirement by another's summary verdict
    # is the same proxy-inference error `scripts/audit_static_classes.py` was built for, committed
    # in the predicate written the same day.
    import ast as _ast
    plotters = []
    for f in (root / "scripts").glob("*.py"):
        if f.name == pathlib.Path(__file__).name:
            continue
        try:
            t = _ast.parse(f.read_text(errors="replace"))
        except SyntaxError:
            continue
        for node in _ast.walk(t):
            mods = ([al.name for al in node.names] if isinstance(node, _ast.Import)
                    else [node.module or ""] if isinstance(node, _ast.ImportFrom) else [])
            if any(m.split(".")[0] == "matplotlib" for m in mods):
                plotters.append(f.name)
                break
    links["shared plotter"] = bool(plotters)

    missing = [k for k, ok in links.items() if not ok]
    have = [k for k, ok in links.items() if ok]

    if missing:
        return "NOT MET", (
            f"the chain breaks at: {', '.join(missing)}. Present: {', '.join(have)} "
            f"({len(logs)} training log(s), {len(grids)} eval grid(s), "
            f"plotter{'s' if len(plotters) != 1 else ''}: {', '.join(plotters) or 'none'})")
    return "NEEDS JUDGEMENT", (
        f"every mechanical link holds — sh script, {len(logs)} training log(s), "
        f"{', '.join(plotters)}, {len(grids)} eval grid(s). **What remains is not work.** R7 asks "
        "for the sequence run END TO END on a CLEAN machine by SOMEONE WHO HAS NOT SEEN THE REPO, "
        "timed and recorded — the acceptance test the supervisor will actually attempt, and one "
        "only a person can perform. Note R5 is separately DEFERRED by the owner (2026-08-26) "
        "until the results table's shape is settled, so the plotter that exists may yet change; "
        "that is a decision, not a missing artifact")


CHECKS = {"R1": ("one sh script trains any baseline", r1),
          "R2": ("structural separation, per-baseline README", r2),
          "R3": ("metrics on the same axes and directly comparable (relaxed 2026-08-26)", r3),
          "R4": ("equal training length, or a stated reason", r4),
          "R5": ("one plotting routine over tensorboard logs", r5),
          "R6": ("all twelve present as genuine implementations", r6),
          "R7": ("the clone-to-curve path works", r7)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="exit 1 if any requirement is NOT MET")
    a = ap.parse_args()
    bad = 0
    for rid, (title, fn) in CHECKS.items():
        try:
            state, why = fn()
        except Exception as e:  # a checker that cannot run must say so, not pass
            state, why = "UNCHECKABLE", f"{type(e).__name__}: {e}"
        bad += state == "NOT MET"
        print(f"  {rid}  {state:<16} {title}")
        print(f"      {why}")
    print(f"\n  Recomputed from the repo. `docs/REVIEW.md` is a dated snapshot (2026-08-09) and is")
    print("  not this; it carries judgement this cannot, and its status column is that old.")
    return 1 if (a.strict and bad) else 0


if __name__ == "__main__":
    raise SystemExit(main())
