#!/usr/bin/env python3
"""`scripts/open_decisions.py` must not inflate the queue the owner is asked to clear.

The standing instruction is to work until only decisions remain. That is checkable, and this is
what checks it — so its failure mode is specific: **listing work as though it were a decision**
makes the finish state unreachable and unfalsifiable at the same time, because nobody can clear an
item that is waiting on me.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("od", ROOT / "scripts" / "open_decisions.py")
od = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(od)


def test_it_reads_all_four_sources():
    groups = [od.register_items(), od.pending_branch_points(),
              od.judgement_requirements(), od.fidelity_items()]
    assert all(isinstance(g, list) for g in groups)
    assert sum(len(g) for g in groups) > 0, "every source came back empty — a parser broke"


def test_an_item_the_document_marks_as_MINE_is_not_listed_as_a_decision():
    """FAITHFULNESS §5 item 11 says `**Whose:** mine, and it is now default for every new cell.`

    It is work that is already done, not a judgement anyone is waiting to make. Listing it would
    ask the owner to decide something nobody is asking them to decide — and the document already
    says so, which is why the annotation is honoured rather than a heuristic applied.
    """
    keys = [k for k, _ in od.fidelity_items()]
    assert "§5 item 11" not in keys, (
        "an item FAITHFULNESS §5 explicitly marks as mine is being presented to the owner as a "
        f"decision. Listed: {keys}")


def test_the_register_group_uses_the_register_s_own_column():
    """Not a guess about which entries look decision-shaped — the table has a column that says."""
    items = dict(od.register_items())
    assert "C1" in items and "C2" in items, (
        "the register's 'your decision' column stopped being read; C1 and C2 are its "
        "longest-standing entries")
    txt = (ROOT / "docs" / "CONSTRUCTION.md").read_text()
    for cid in items:
        assert f"[{cid}](#{cid.lower()})" in txt


def test_it_states_that_it_is_not_a_completeness_claim(capsys):
    """A list of open decisions that reads as exhaustive is worse than none."""
    od.main([])
    out = capsys.readouterr().out
    assert "NOT A COMPLETENESS CLAIM" in out
    assert "waiting on a person" in out.lower() and "waiting on work" in out.lower(), (
        "the distinction the tool exists to draw is no longer stated in its output")
