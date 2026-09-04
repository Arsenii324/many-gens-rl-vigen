"""`scripts/decisions.py` — the instrument that keeps a decision findable as a decision.

The failure it exists to catch is quiet: a register entry leaves the judgement queue because a
choice was made, the choice survives as a sentence inside a resolved entry, and nobody can
enumerate it afterwards. It has then been forgotten *as a decision* — it reads as the way things
are, which is the state in which nobody reopens it. It caught C33 that way on its first run.

So the failure mode to guard against here is the flattering one: an extractor that reports every
decision complete because it cannot see an incomplete one.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import decisions as D  # noqa: E402

FULL = """**P99 — a worked example** (register C99)

| §4 field | |
|---|---|
| **Structural property of the original the mechanism depends on** | something |
| **What the target actually offers** | something else |
| **Options** | (1) a; (2) b |
| **Choice** | **(1), owner, 2026-01-01.** |
| **What would show the choice was wrong** | b turning out cheaper |
"""


def home(tmp_path: pathlib.Path, text: str) -> pathlib.Path:
    f = tmp_path / "H.md"
    f.write_text(text)
    return f


def test_a_complete_decision_parses_with_every_field(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "HOMES", [home(tmp_path, FULL)])
    d, = D.parse()
    assert d["missing"] == []
    assert d["settled"] is True
    assert d["entries"] == ["C99"]


def test_a_missing_falsifier_is_reported(tmp_path, monkeypatch):
    """§4's fourth field is the one that stops a decision fossilising into an assumption."""
    monkeypatch.setattr(D, "HOMES", [home(
        tmp_path, FULL.replace("| **What would show the choice was wrong** | b turning out cheaper |\n", ""))])
    d, = D.parse()
    assert "wrong" in d["missing"], (
        "a decision with no overturning result must not read as complete; that is the field the "
        "whole instrument is for")


@pytest.mark.parametrize("choice", [
    "**Not yet made — owner's decision.**",
    "**NOT MADE — the owner's.**",
    "**Undecided.** Both options remain live",
    "**Not decided**; recorded as a branch point",
    "**Deferred** until the production runs land",
    "**Open** — needs DZ",
    "**Pending** the evaluation-protocol choice",
])
def test_an_undecided_block_reads_pending_however_it_is_phrased(tmp_path, monkeypatch, choice):
    """The instrument fails in its worst direction if it misreads "undecided" as "decided".

    This test used to try exactly one phrasing — "Not yet made" — which was the single literal the
    predicate tested for. It therefore passed while the bug was live, and on 2026-08-26 a real
    block whose Choice read **NOT MADE — the owner's** was counted as DECIDED and vanished from
    the list of things awaiting a judgement. A ledger of open decisions that silently closes one
    is worse than no ledger, because its count is trusted.
    """
    monkeypatch.setattr(D, "HOMES", [home(
        tmp_path, FULL.replace("| **Choice** | **(1), owner, 2026-01-01.** |",
                               f"| **Choice** | {choice} |"))])
    d, = D.parse()
    assert d["settled"] is False, (
        f"a Choice reading {choice!r} was counted as a settled decision")


def test_a_real_decision_is_still_read_as_settled(tmp_path, monkeypatch):
    """The other direction: broadening the markers must not turn decided blocks into pending ones.

    "Open" and "the owner's" are broad words, and a Choice cell that records who decided and when
    ("(1), owner, 2026-08-18") legitimately contains "owner". If this goes red, the marker list has
    grown greedy and the ledger will start nagging about decisions that were made.
    """
    monkeypatch.setattr(D, "HOMES", [home(tmp_path, FULL)])
    d, = D.parse()
    assert d["settled"] is True

    for real in ("**(1), owner, 2026-08-18.** Success rate is not deleted",
                 "**(1), owner, 2026-08-19.** It costs nothing and does not foreclose (2)"):
        monkeypatch.setattr(D, "HOMES", [home(
            tmp_path, FULL.replace("| **Choice** | **(1), owner, 2026-01-01.** |",
                                   f"| **Choice** | {real} |"))])
        d, = D.parse()
        assert d["settled"] is True, f"a settled decision was demoted to pending by: {real!r}"


def test_a_wrapped_title_still_parses(tmp_path, monkeypatch):
    """A bolded name with its register citation on the next line is the natural way to write one.

    The parser forbade it at first, which would have made the record serve the instrument.
    """
    monkeypatch.setattr(D, "HOMES", [home(
        tmp_path, FULL.replace("**P99 — a worked example** (register C99)",
                               "**P99 — a worked example** (register\n[C99](CONSTRUCTION.md#c99))"))])
    d, = D.parse()
    assert d["entries"] == ["C99"]


def test_entries_come_from_the_title_not_the_whole_block(tmp_path, monkeypatch):
    """Citing C47 while explaining a decision does not mean C47 was decided.

    Counting every mention would let a measurement vanish from the unlogged list for being
    referenced, which is the opposite of what this instrument is for.
    """
    monkeypatch.setattr(D, "HOMES", [home(
        tmp_path, FULL.replace("| **Options** | (1) a; (2) b |",
                               "| **Options** | (1) a, per C47; (2) b |"))])
    d, = D.parse()
    assert d["entries"] == ["C99"], f"C47 was cited, not decided; got {d['entries']}"


def test_it_reads_every_declared_home(tmp_path, monkeypatch):
    """Decisions live in more than one document by design; missing one hides decisions."""
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    a.write_text(FULL)
    b.write_text(FULL.replace("P99", "P98").replace("C99", "C98"))
    monkeypatch.setattr(D, "HOMES", [a, b])
    assert sorted(x["entries"][0] for x in D.parse()) == ["C98", "C99"]


def test_the_real_repository_has_its_decisions_complete():
    ds = D.parse()
    bad = {d["title"][:40]: d["missing"] for d in ds if d["missing"]}
    assert ds, "no decisions parse at all — the ledger or the parser is broken"
    assert not bad, f"incomplete standing decisions: {bad}"


def test_a_pending_decision_flags_premises_that_have_since_settled(monkeypatch):
    """The "decisions build on later" problem, which is what breaks at N decisions.

    C50's option 2 was written as "collides with C45". Once C45 was decided that option meant
    something different, and nothing would have said so. A decision whose premises moved is not
    wrong; it is unreviewed, which is worse, because it still reads as current.
    """
    d = {"entries": ["C50"], "settled": False, "options": "collides with C45 and C99"}
    assert D.shifted_under(d, {"C45": "RESOLVED", "C99": "OPEN"}) == ["C45"]


def test_it_does_not_flag_the_decision_s_own_entries(monkeypatch):
    d = {"entries": ["C45"], "settled": False, "options": "about C45 itself"}
    assert D.shifted_under(d, {"C45": "RESOLVED"}) == []
