"""`scripts/preprod_table.py` is the twelve-baseline production table -- its own docstring says
the axes are printed WITH the numbers because "a bare column invites a comparison the data does
not support." It already carried columns/footer prose for every other known comparability axis
(C2's frame stack, the sampled-vs-mode estimator split, C95's render backend) but had none for
C1 (time-limit handling), despite C1 being rated the LARGEST comparability defect found
(CONSTRUCTION.md#c1). Found 2026-09-06 auditing whether the C1 split is actually kept out of
cross-baseline tables, not just declared as policy. Fixed additively: a `TIME_LIMIT` dict (same
source `audit_comparability_seam.py::truncation()` and `results_table.py` read) and a `timelimit`
column + footer paragraph, matching this file's own established pattern for the other axes.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("pt", ROOT / "scripts" / "preprod_table.py")
pt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pt)


def test_time_limit_dict_matches_rlgen_protocol_exactly():
    """Read independently from `rlgen/protocol.py`'s own source, the same way this project's
    other axis-readers do, and compared against the canonical dict directly rather than trusted."""
    src = (ROOT / "rlgen" / "protocol.py").read_text(encoding="utf-8")
    ns: dict = {}
    exec(compile(src, "protocol.py", "exec"), ns)
    assert pt.TIME_LIMIT == ns["TIME_LIMIT_HANDLING"]


def test_time_limit_dict_covers_all_twelve_with_exactly_two_values():
    assert set(pt.TIME_LIMIT) == set(pt.ESTIMATOR)  # ESTIMATOR is already the 12-baseline set
    assert set(pt.TIME_LIMIT.values()) == {"bootstrap", "terminal"}
    bootstrap = {b for b, v in pt.TIME_LIMIT.items() if v == "bootstrap"}
    assert bootstrap == {"rad", "soda", "alda"}, (
        "only rad/soda/alda bootstrap through Door's time limit -- if this set changes, "
        "CONSTRUCTION.md#c1's own 3-vs-9 split description is now stale too")


def _fake_row(name, tl_value):
    return dict(baseline=name, frames=10_000, regime="eval-easy", regime_substituted=False,
                episodes=10, mean=5.0, success=0.1, mujoco_gl="egl", source="record")


def test_header_and_separator_column_counts_match(monkeypatch, tmp_path, capsys):
    """A column added to the header without updating the separator produces a malformed
    markdown table that renders wrong without pytest ever noticing, since nothing here diffs
    against a rendered table -- pinned directly on the two literal strings instead."""
    monkeypatch.setattr(pt, "cells_of", lambda job, regime: [_fake_row("drqv2", "terminal")])
    pt.main([str(tmp_path)])
    out = capsys.readouterr().out
    header = next(l for l in out.splitlines() if l.startswith("| baseline"))
    sep = next(l for l in out.splitlines() if l.startswith("|---"))
    assert header.count("|") == sep.count("|"), (
        "header and separator row must have the same column count or the table is malformed")
    assert "timelimit" in header


def test_a_uniform_time_limit_group_does_not_claim_mixing(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(pt, "cells_of", lambda job, regime: [
        _fake_row("drqv2", "terminal"), _fake_row("svea", "terminal")])
    pt.main([str(tmp_path)])
    out = capsys.readouterr().out
    assert "largest comparability defect" in out
    assert "This table currently mixes both" not in out


def test_a_mixed_time_limit_group_is_named_explicitly(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(pt, "cells_of", lambda job, regime: [
        _fake_row("drqv2", "terminal"), _fake_row("rad", "bootstrap")])
    pt.main([str(tmp_path)])
    out = capsys.readouterr().out
    assert "This table currently mixes both: bootstrap, terminal." in out


def test_every_row_prints_its_own_time_limit_value(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(pt, "cells_of", lambda job, regime: [
        _fake_row("drqv2", "terminal"), _fake_row("rad", "bootstrap")])
    pt.main([str(tmp_path)])
    out = capsys.readouterr().out
    drqv2_line = next(l for l in out.splitlines() if l.startswith("| `drqv2`"))
    rad_line = next(l for l in out.splitlines() if l.startswith("| `rad`"))
    assert "| terminal |" in drqv2_line
    assert "| bootstrap |" in rad_line


def test_stack_dict_matches_rlgen_protocol_exactly():
    """`STACK` used to be a hand-typed literal duplicating OBSERVATION_GEOMETRY's frame-stack
    column -- the exact drift shape C1's false-certification half already demonstrated once.
    Now read from the source directly; this pins the two staying identical going forward."""
    src = (ROOT / "rlgen" / "protocol.py").read_text(encoding="utf-8")
    ns: dict = {}
    exec(compile(src, "protocol.py", "exec"), ns)
    expected = {b: geom[1] for b, geom in ns["OBSERVATION_GEOMETRY"].items()}
    assert pt.STACK == expected
