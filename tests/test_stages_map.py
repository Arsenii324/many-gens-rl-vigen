"""`docs/STAGES.md` must be derived from the register, not asserted over it.

The staging map is a *virtual* view: it names groupings over register entries it does not own. A
view that drifts from what it views is worse than no view, because it reads as a status report.
These tests are what makes "derived" a checkable word rather than a claim in a preamble.

They deliberately do not check that the *assignment* of an entry to a stage is correct — that is
judgement and cannot be tested. They check that every entry named exists, and that no stage is
decorative.
"""
from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
STAGES = ROOT / "docs" / "STAGES.md"
REGISTER = ROOT / "docs" / "CONSTRUCTION.md"

# Stage 9 has no register entries because nothing has been written yet. Named rather than
# tolerated by a threshold, so that closing the gap requires deleting the exemption.
STAGES_WITHOUT_ENTRIES = {"9"}


def stages_text() -> str:
    assert STAGES.exists(), f"{STAGES} missing"
    return STAGES.read_text(encoding="utf-8")


def register_ids() -> set[str]:
    text = REGISTER.read_text(encoding="utf-8")
    return set(re.findall(r"^\| \[(C\d+)\]\(#c\d+\)", text, re.M))


def stage_blocks(text: str) -> dict[str, str]:
    """{stage number: its body} — split on the `**N · Name.**` headings."""
    marks = list(re.finditer(r"\*\*(\d) · ([^.*]+)\.\*\*", text))
    assert marks, "no stage headings found -- this checker went blind"
    out = {}
    for i, m in enumerate(marks):
        # Bound at the next stage heading, or at the next section break -- otherwise the LAST
        # stage runs to end-of-file and swallows the status table and everything after it, which
        # is how the first version of this test reported stage 9 as citing six entries.
        limits = [marks[i + 1].start()] if i + 1 < len(marks) else []
        for sep in ("\n---\n", "\n## "):
            j = text.find(sep, m.end())
            if j != -1:
                limits.append(j)
        end = min(limits) if limits else len(text)
        out[m.group(1)] = text[m.start():end]
    return out


def test_there_are_stages_to_check():
    blocks = stage_blocks(stages_text())
    assert len(blocks) == 9, f"expected 9 stages, found {sorted(blocks)}"


def test_every_entry_cited_exists_in_the_register():
    """Catches renumbering, deletion, and invention."""
    cited = set(re.findall(r"CONSTRUCTION\.md#(c\d+)", stages_text()))
    known = {i.lower() for i in register_ids()}
    missing = sorted(c for c in cited if c not in known)
    assert not missing, (
        f"STAGES.md cites entries the register does not have: {missing}. The register is "
        "authoritative; fix the map, not the register.")


@pytest.mark.parametrize("stage", [str(i) for i in range(1, 10)])
def test_no_stage_is_decorative(stage):
    """A stage naming no real work is a heading pretending to be a finding."""
    block = stage_blocks(stages_text()).get(stage, "")
    cited = re.findall(r"CONSTRUCTION\.md#c\d+", block) or re.findall(r"P1.{0,3}P13", block)
    if stage in STAGES_WITHOUT_ENTRIES:
        assert not cited, (
            f"stage {stage} is exempt from citing entries but now cites some -- delete the "
            "exemption in STAGES_WITHOUT_ENTRIES rather than leaving it stale")
        return
    assert cited, f"stage {stage} cites no register entry and no patch range"


def test_the_status_table_covers_every_stage():
    """The map and its status table must not drift apart."""
    text = stages_text()
    rows = re.findall(r"^\| (\d) ([A-Za-z][^|]*?)\s*\|", text, re.M)
    assert len(rows) == 9, f"status table has {len(rows)} stage rows, expected 9"
    for num, _ in rows:
        assert num in stage_blocks(text), f"status table has stage {num} with no section"


def test_it_declares_that_it_is_not_an_instruction():
    """The framing is load-bearing: this file must not read as builder rules.

    Pinned because the failure is silent — a later edit that drops the disclaimer turns a human
    orientation aid into a process document, and nothing else would notice.
    """
    text = stages_text()
    assert "Not an instruction to the builder" in text
    assert "Not error containment" in text
    assert "Not a partition" in text
