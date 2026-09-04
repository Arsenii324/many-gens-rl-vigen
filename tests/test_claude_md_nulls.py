"""`CLAUDE.md`'s nulls claim to be verbatim. This checks that they are.

The file says of itself: *"The lines are taken from their sources unchanged unless marked
otherwise; do not paraphrase them here, because a second wording drifts from the first and nothing
notices."* That is a mechanically checkable claim about our own work, so it should not be a
sentence in a preamble.

It is also not hypothetical. Two of the nine drifted **within minutes of being written**, before
any of them had been read by anyone: one said "a defect in the contract" where the source says
"a defect in *this* contract", and one paraphrased the runbook's rule about checkers into a
sentence that appears nowhere in it. Both were caught by running this comparison by hand once;
without a test the third would be found by nobody.

What this does not check: that the null is a *good* one, or that the section it cites is the right
section. Those are judgement.
"""
from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CLAUDE = ROOT / "CLAUDE.md"

# A bullet carrying this marker is a deliberate rendering, not a quote. Naming the marker rather
# than the bullet means a second rendered null must announce itself the same way.
RENDERED_MARKER = "Rendered plainly"


def norm(s: str) -> str:
    """Compare on words, not on markup: bold, backticks, blockquote markers and quote style."""
    s = re.sub(r"^\s*>\s?", "", s, flags=re.M)
    s = s.replace("*", "").replace("`", "")
    s = s.replace("“", '"').replace("”", '"').replace("’", "'")
    return re.sub(r"\s+", " ", s).strip()


def nulls() -> list[str]:
    """The bullets under `## Nulls`, one string each."""
    assert CLAUDE.exists(), f"{CLAUDE} missing"
    text = CLAUDE.read_text(encoding="utf-8")
    m = re.search(r"^## Nulls\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert m, "CLAUDE.md has no `## Nulls` section"
    body = m.group(1)
    return [b.strip() for b in re.split(r"\n- ", "\n" + body) if b.strip().startswith(("A ", "The ", "Two ", "Which ", "Step ", "Record ", "Reach ", "Hermetic ", "Every "))]


def sources_of(bullet: str) -> list[pathlib.Path]:
    """Files named on the bullet's `→ [text](path)` line."""
    return [(ROOT / p).resolve() for p in re.findall(r"→.*?\]\(([^)#]+)\)", bullet)] or \
           [(ROOT / p).resolve() for p in re.findall(r"\]\(([^)#]+)\)", bullet)]


def claim_of(bullet: str) -> str:
    """The bullet minus its arrow line and any parenthetical note about provenance."""
    body = bullet.split("→")[0]
    return re.sub(r"\([^)]*\)", " ", body)


def test_there_are_nulls_to_check():
    got = nulls()
    assert len(got) >= 5, f"only {len(got)} nulls parsed -- this checker may have gone blind"


@pytest.mark.parametrize("i", range(20))
def test_each_null_names_a_source_that_exists(i):
    got = nulls()
    if i >= len(got):
        pytest.skip("fewer nulls than the parametrisation covers")
    srcs = sources_of(got[i])
    assert srcs, f"null {i} names no source: {got[i][:70]!r}"
    for s in srcs:
        assert s.exists(), f"null {i} points at a missing file: {s}"


@pytest.mark.parametrize("i", range(20))
def test_each_quoted_null_is_verbatim_in_its_source(i):
    got = nulls()
    if i >= len(got):
        pytest.skip("fewer nulls than the parametrisation covers")
    bullet = got[i]
    if RENDERED_MARKER in bullet:
        pytest.skip("declared a rendering rather than a quote")
    haystack = " ".join(norm(s.read_text(errors="replace")) for s in sources_of(bullet))
    # Sentence by sentence: a null may pull two adjacent sentences from one section.
    for sentence in re.split(r"(?<=[.])\s+", norm(claim_of(bullet))):
        sentence = sentence.strip()
        if len(sentence) < 25:
            continue
        # A quote may stop early: several nulls take a clause up to an em dash and close it with
        # a period the source does not have. A verbatim prefix is still verbatim.
        sentence = sentence.rstrip(".")
        assert sentence in haystack, (
            f"null {i} is not verbatim in the source it names.\n  CLAUDE.md: {sentence!r}\n"
            "  Fix the quote to match the source, or mark the bullet as a rendering.")


def test_the_file_still_states_the_rule_it_is_checked_against():
    """If the no-paraphrase rule is deleted, this test is enforcing something nobody claims."""
    t = CLAUDE.read_text(encoding="utf-8")
    assert "taken from their sources unchanged" in t
    assert "do not paraphrase them here" in t
