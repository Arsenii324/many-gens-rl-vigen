#!/usr/bin/env python3
"""`scripts/audit_static_classes.py` must keep finding the defect that motivated it — C77/C79/C80.

The owner asked why findings that changed experiment results were not found at implementation.
Sorting them by whether a RUN was needed gives an uncomfortable split: C70 and C84 needed one, and
C77, C79 and C80 did not — they were readable, and cost a 3.5-hour run, 64 minutes of a NaN run,
and an unmeasured suite respectively.

This audit exists so those three questions get asked on every run. Its positive control is C77
itself: if `RL-ViGen-upstream/train.py:309` stops being flagged, the instrument has gone blind to
the exact defect it was built from.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("asc", ROOT / "scripts" / "audit_static_classes.py")
asc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(asc)


def test_it_still_finds_C77_itself():
    """The positive control. RIGOR.md §2: name an arm that MUST move if the instrument works."""
    hits = asc.loop_boundary_hits()
    assert any("RL-ViGen-upstream/train.py:309" in h for h in hits), (
        "the audit no longer flags train.py:309, which is C77 — the defect it was built from. "
        f"Either the file changed or the detector went blind. Hits: {hits}")


def test_the_ibac_sni_candidate_is_reported_and_is_not_a_defect():
    """A hit is a question. This one was asked and answered, and the answer is recorded here.

    `runnable/ibac_sni/torch_rl/scripts/train.py` saves on `update % save_interval` inside
    `while num_frames < args.frames`. It does NOT have C77's shape: the increment and the save are
    both in the body with the save AFTER the increment, so the final iteration's save runs. C77's
    defect is that RL-ViGen puts the save at the TOP of the body while `global_step += 1` is at the
    BOTTOM, so the iteration reaching N never begins.

    Pinned so that a future reader does not re-investigate it, and so that if the file is
    restructured the difference has to be re-argued rather than inherited.
    """
    src = (ROOT / "runnable" / "ibac_sni" / "torch_rl" / "scripts" / "train.py").read_text()
    inc = src.index("update += 1")
    save = src.index("if args.save_interval > 0 and update % args.save_interval == 0")
    assert inc < save, (
        "ibac_sni's save moved above its update increment — it now has C77's shape and a run "
        "landing on the boundary may write no checkpoint")


def test_a_logged_quantity_nobody_reads_is_reported(tmp_path, monkeypatch):
    """C79's class: an instrument already paid for and never read."""
    f = tmp_path / "w.py"
    f.write_text("log('a_metric_nobody_reads', 1)\n")
    monkeypatch.setattr(asc, "_files", lambda: iter([f]))
    hits = asc.written_never_read({"a_metric_nobody_reads": ["w.py"]})
    assert hits and "a_metric_nobody_reads" in hits[0]

    g = tmp_path / "r.py"
    g.write_text("x = row['a_metric_nobody_reads']\ny = row['a_metric_nobody_reads']\n")
    monkeypatch.setattr(asc, "_files", lambda: iter([f, g]))
    assert not asc.written_never_read({"a_metric_nobody_reads": ["w.py"]}), (
        "a quantity that IS read back was still reported — the check would cry wolf on every "
        "column and be ignored, which is how C79 survived six days")


def test_the_audit_no_longer_flags_itself_as_never_executed():
    """Self-consistency, and the cheapest possible proof that C80's class check works.

    Before this test existed, the audit flagged ITSELF: no test named it, nothing called it. That
    was correct. Writing this test is what clears it, which is the point — the class is 'nothing
    establishes it has ever run', and a test is what establishes that.
    """
    assert not any("audit_static_classes.py" in h for h in asc.never_executed()), (
        "the audit still reports itself as never-executed even though this test names it — the "
        "detector is not seeing test files")
