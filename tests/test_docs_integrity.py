"""Structural integrity of the document set: nothing orphaned, no link pointing at nothing.

Distinct from `test_docs_not_stale.py`, which checks whether the *numbers* in prose still match
the tools that produce them. This checks whether the documents can still be navigated at all.

Both failures here were real when these tests were written, which is why they exist rather than
being hypothetical hygiene:

- **`AUDIT-2026-08-17.md` was absent from `PROJECT-INDEX.md`** — the report is the most
  externally visible artifact this project has, and the index that exists to make documents
  findable did not mention it in either format.
- Five further documents were unreachable from the index. Most are genuinely historical, which is
  a different thing from forgotten, and the index now says which.

A document nobody can find is a document nobody maintains, and this project has already been
caught three times by prose that quietly stopped being true.
"""
from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
INDEX = DOCS / "PROJECT-INDEX.md"


def anchors_of(text: str) -> set[str]:
    """Explicit `{#id}` anchors plus GitHub-style slugs derived from headings."""
    out = {m.lower() for m in re.findall(r"\{#([\w-]+)\}", text)}
    for h in re.findall(r"^#{1,6}\s+(.+)$", text, re.M):
        out.add(re.sub(r"[^a-z0-9 -]", "", h.lower()).replace(" ", "-"))
    return out


def md_files() -> list[pathlib.Path]:
    return sorted(DOCS.glob("*.md"))


def linked_files() -> list[pathlib.Path]:
    """Documents whose links are checked: `docs/` plus the repo root.

    Root-level files were outside every check until 2026-08-18, which is how `CLAUDE.md` came to
    live there with nothing verifying its links resolved. They are deliberately NOT added to
    `md_files()`, because the orphan test requires an entry in `PROJECT-INDEX.md` and the index
    routes documents rather than repo furniture.
    """
    return sorted(set(md_files()) | set(ROOT.glob("*.md")))


def test_there_are_documents_to_check():
    """A checker that passes on an empty input is not a checker."""
    assert md_files(), f"no .md files under {DOCS} -- this file would report green while " \
                       "checking nothing"
    assert INDEX.exists(), f"{INDEX} is missing; it is what makes the rest findable"


def test_no_document_is_orphaned_from_the_index():
    """Every `docs/*.md` must be reachable from `PROJECT-INDEX.md`.

    Historical documents count as reachable: the index has a section for them, so "not in the
    live path" is stated rather than left as silence. The distinction that matters is
    *deliberately set aside* versus *forgotten*, and only one of those is acceptable.
    """
    index_text = INDEX.read_text(encoding="utf-8")
    orphans = [f.name for f in md_files()
               if f.name != INDEX.name and f.name not in index_text]
    assert not orphans, (
        f"documents unreachable from PROJECT-INDEX.md: {orphans}. Add them, or list them under "
        "'Historical and single-purpose documents' with what they are. A document nobody can "
        "find is a document nobody maintains.")


DATED = DOCS / "dated"


def dated_files() -> list[pathlib.Path]:
    """Recursive on purpose.

    A first version of this globbed `*.md` and would have missed any snapshot filed in a
    subdirectory — which is the same non-recursive blind spot that lets `docs/dated/` escape
    `md_files()` in the first place, reintroduced one level down. A reviewer pack is exactly the
    shape that arrives as a subdirectory, so the bug would have shipped the day the rule did.
    """
    return sorted(DATED.rglob("*.md")) if DATED.is_dir() else []


def test_dated_snapshots_declare_their_write_time():
    """Every `docs/dated/*.md` states its write date in its own prose, and the folder is indexed.

    `md_files()` globs `docs/*.md` without recursing, so a subdirectory is invisible to the orphan
    test above — silently, which is the failure mode that test exists to prevent. `docs/dated/`
    is therefore exempt by *accident* unless something says otherwise. This is that something.

    The trade the folder makes: one index row for the folder, none for its files, so the index
    stops growing a row per snapshot. What it must not also cost is traceability, hence both
    halves below.

    The date must be in the prose, not only the filename. A snapshot gets quoted by paragraph, and
    a filename does not survive a paste — `SYSTEM.md` records a finding that crossed a compaction
    "more confident and less correct" for exactly this reason.
    """
    assert "dated/" in INDEX.read_text(encoding="utf-8"), (
        "docs/dated/ is not named in PROJECT-INDEX.md. The folder is exempt from the per-file "
        "orphan check, so the folder itself must be reachable or the whole subtree is invisible.")

    undated = []
    for f in dated_files():
        head = "\n".join(f.read_text(encoding="utf-8").splitlines()[:15])
        if not re.search(r"[Ww]ritten\s+\d{4}-\d{2}-\d{2}", head):
            undated.append(f.name)
    assert not undated, (
        f"dated snapshots with no 'Written YYYY-MM-DD' in their first 15 lines: {undated}. "
        "Put the date in the prose, not just the filename — a paragraph pasted out of this file "
        "has to carry the date with it, or it reads as a current claim.")


@pytest.mark.parametrize("doc", linked_files(), ids=lambda p: p.name)
def test_internal_links_resolve(doc: pathlib.Path):
    """Every relative markdown link must reach a real file, and a `#fragment` a real anchor.

    External links are not checked: this must stay offline and deterministic, and a test that
    fails because a third-party site is down teaches nothing about this repository.
    """
    text = doc.read_text(encoding="utf-8", errors="replace")
    own = anchors_of(text)
    broken = []
    for link in re.findall(r"\[[^\]]*\]\(([^)\s]+)\)", text):
        if link.startswith(("http://", "https://", "mailto:")):
            continue
        path, _, frag = link.partition("#")
        if not path:
            if frag.lower() not in own:
                broken.append((link, "no such anchor in this file"))
            continue
        target = (doc.parent / path).resolve()
        if not target.exists():
            broken.append((link, "file does not exist"))
        elif frag and target.suffix == ".md":
            if frag.lower() not in anchors_of(target.read_text(encoding="utf-8",
                                                               errors="replace")):
                broken.append((link, f"no such anchor in {target.name}"))
    assert not broken, f"{doc.name} has links that point at nothing: {broken}"
