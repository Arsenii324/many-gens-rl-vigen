#!/usr/bin/env python3
"""A heading scan of a two-era document must not silently mislead. [C82](../docs/CONSTRUCTION.md#c82)

Three wrong claims were written about `FAITHFULNESS.md` on 2026-08-27, each corrected by the owner,
all three from the same move: concluding from `grep '^## '` instead of from reading. The headings
said "Summary", "The PPO family", "What would raise fidelity most" — and none of them said whether
the section describes the retired `rlgen/` port or what runs today. The costliest consequence was
that §5 *is* the file's current-state section, re-triaged in the clone era, and a banner got written
over the whole document claiming it did not know the clone tree existed.

These tests do not check that a tag is *correct* — nothing can. They check it is present and from
the vocabulary, because a missing tag is what let the wrong claims through, while a wrong tag is
visible to the next reader.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("css", ROOT / "scripts" / "check_section_scope.py")
css = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(css)


def test_every_scoped_document_tags_every_section():
    missing = []
    for rel in css.SCOPED:
        for lineno, text, tag in css.scan(ROOT / rel):
            if tag is None:
                missing.append(f"{rel}:{lineno} {text[:60]}")
    assert not missing, (
        "a `##` heading in a two-era document carries no era tag, so a heading scan of it is "
        "silently misleading — the exact failure C82 records:\n  " + "\n  ".join(missing))


def test_no_scoped_document_uses_a_tag_outside_the_vocabulary():
    bad = []
    for rel in css.SCOPED:
        for lineno, text, tag in css.scan(ROOT / rel):
            if tag is not None and tag.removesuffix(css.UNVERIFIED_SUFFIX) not in css.VOCABULARY:
                bad.append(f"{rel}:{lineno} [{tag}]")
    assert not bad, (
        f"unknown scope tag(s) {bad}; the vocabulary is {sorted(css.VOCABULARY)}. An ad-hoc tag "
        "reads as meaningful and is not, which is worse than none")


def test_at_most_one_current_state_section_per_document():
    """CURRENT-STATE means 'start here'. Two of them means neither is the entry point."""
    for rel in css.SCOPED:
        n = sum(1 for _, _, t in css.scan(ROOT / rel) if t == "CURRENT-STATE")
        assert n <= 1, f"{rel} marks {n} sections CURRENT-STATE; at most one can be the entry point"


def test_faithfulness_still_marks_its_triage_as_the_entry_point():
    """The specific fact whose absence caused C82, pinned by name rather than by count.

    `FAITHFULNESS.md` §5 is the section that resolves and re-opens everything above it. If that
    mark disappears, the next reader repeats the mistake this whole file exists to prevent.
    """
    heads = css.scan(ROOT / "docs" / "FAITHFULNESS.md")
    current = [t for _, txt, tag in heads if tag == "CURRENT-STATE" for t in [txt]]
    assert len(current) == 1 and "raise fidelity" in current[0], (
        f"FAITHFULNESS.md's CURRENT-STATE mark is no longer on its triage section: {current}")
    tags = {t.removesuffix("-U") for _, _, t in heads if t}
    # Not "PORT-ERA must appear": an earlier version required exactly that, and then §4 was
    # correctly re-tagged MIXED because it carries durable paper research — so the test failed for
    # the fix. What must hold is that the file DISTINGUISHES its eras at heading level, which
    # LIVE + (MIXED or PORT-ERA) does.
    assert "LIVE" in tags and ({"MIXED", "PORT-ERA"} & tags), (
        f"the file stopped distinguishing its two eras at heading level (tags: {sorted(tags)}); "
        "the split runs THROUGH sections there, which is why it has to be visible per section")


def test_the_checker_reports_an_untagged_heading(tmp_path, monkeypatch):
    """Anti-vacuity: it must go red on a document that lacks tags."""
    doc = tmp_path / "docs" / "FAKE.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("# t\n\n## A section with no tag\n\nbody\n")
    monkeypatch.setattr(css, "ROOT", tmp_path)
    monkeypatch.setattr(css, "SCOPED", {"docs/FAKE.md": "test fixture"})
    heads = css.scan(doc)
    assert heads == [(3, "A section with no tag", None)]

    doc.write_text("# t\n\n## A section with no tag  ·  [LIVE]\n\nbody\n")
    assert css.scan(doc)[0][2] == "LIVE"

    doc.write_text("# t\n\n## A section  ·  [INVENTED]\n\nbody\n")
    assert css.scan(doc)[0][2] == "INVENTED"
    assert "INVENTED" not in css.VOCABULARY, "the vocabulary silently grew to accept anything"


def test_an_unverified_tag_is_accepted_and_visible():
    """`-U` marks a tag as believed rather than read. It must parse, and it must not be silent."""
    assert css.UNVERIFIED_SUFFIX == "-U"
    tagged = [t for _, _, t in css.scan(ROOT / "docs" / "COMPARABILITY_CONTRACT.md") if t]
    assert any(t.endswith("-U") for t in tagged), (
        "COMPARABILITY_CONTRACT's tags were inferred from C30 rather than read section by section; "
        "dropping the -U marks would present a guess as a finding")
    for t in tagged:
        assert t.removesuffix("-U") in css.VOCABULARY, f"unknown base tag in {t}"


def test_no_section_carrying_durable_research_is_tagged_as_a_single_dead_era():
    """A tag must not invite a reader to discard live material — the owner's warning, pinned.

    `FAITHFULNESS.md` §4 carries IDAAC's Appendix E column, PPG's 65 536-sample update and the
    first author's caution about DAAC on DMC — durable research about papers, unaffected by which
    of our trees ran. It was briefly tagged PORT-ERA, which would have read as "discard".
    """
    heads = {txt: tag for _, txt, tag in css.scan(ROOT / "docs" / "FAITHFULNESS.md")}
    ppo = [t for txt, t in heads.items() if "PPO family" in txt]
    assert ppo and ppo[0].removesuffix("-U") in ("MIXED", "DURABLE"), (
        f"the PPO-family section is tagged {ppo}; it carries durable paper research alongside "
        "port-era implementation claims, so a single dead-era tag would invite discarding it")
    assert css.NEVER_DISCARD, "the never-discard rule was removed from the checker"
