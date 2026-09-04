"""`docs/CONSTRUCTION.md` must obey its own rules.

The register exists because decisions were being held in working state and lost — `REGISTER.md`
category 42. A register that nobody is forced to maintain becomes a stale register, which is
worse than none: it reads as a live account of what is open while quietly describing last month.

So the structure is checked, not trusted. Specifically the rules the file states about itself:

  - IDs are unique and every summary-table ID has a detail section, and vice versa.
  - Statuses come from a fixed vocabulary, so "sort of open" cannot appear.
  - An OPEN item carries **Options** — an open decision with no alternatives stated is a
    complaint, not a decision.
  - A RESOLVED item carries a **Decision** and an **Effect**. The effect is the field other
    documents lose, and "we did it and nothing changed" is a result that must survive.
  - A RESOLVED item names a commit, so the claim is checkable against a diff.
  - The counts in the summary line match the entries, because a hand-maintained total is exactly
    the kind of true-once statement this project keeps filing as permanent.

**What this cannot check:** whether an entry is *right*, whether its evidence supports it, or
whether an OPEN item should have been closed months ago. It is a floor under the structure, not
a review of the content.
"""
from __future__ import annotations

import collections
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "CONSTRUCTION.md"
STATUSES = {"OPEN", "READY", "BLOCKED", "MONITORED", "RESOLVED"}
# OPEN   -- needs a judgement between alternatives, so it must state them.
# READY  -- no judgement needed, only a slot. Distinguished from OPEN deliberately: lumping
#           "someone must decide this" together with "someone must find an afternoon" is how the
#           first kind quietly waits on the second.
NEEDS_OPTIONS = {"OPEN"}


@pytest.fixture(scope="module")
def text() -> str:
    assert DOC.exists(), f"{DOC} is missing -- the construction register is the single authority "\
                         "for open decisions; if it moved, update this test to follow it"
    return DOC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sections(text) -> dict:
    """{id: body} for every `### C<n> — ... {#c<n>}` detail section."""
    out, cur, buf = {}, None, []
    for line in text.splitlines():
        m = re.match(r"^###\s+(C\d+)\s+[—-]", line)
        if m:
            if cur:
                out[cur] = "\n".join(buf)
            cur, buf = m.group(1), []
        elif cur:
            buf.append(line)
    if cur:
        out[cur] = "\n".join(buf)
    return out


def summary_rows(text):
    """(id, status) for each row of the summary table."""
    rows = []
    for line in text.splitlines():
        # | id | item | class | status | needs |  -- take column 4, not the first thing that
        # looks like a word in caps. A non-greedy `.*?` here silently matched the CLASS column
        # and reported every class as an illegal status; caught by running it.
        m = re.match(r"^\|\s*\[(C\d+)\]\(#c\d+\)\s*\|[^|]*\|[^|]*\|"
                     r"\s*\*{0,2}([A-Z-]+)\*{0,2}\s*\|", line)
        if m:
            rows.append((m.group(1), m.group(2)))
    return rows


def test_the_register_has_entries(text):
    """A checker that passes on an empty document is not a checker."""
    assert summary_rows(text), "no summary rows parsed -- either the table format changed or "\
                               "this test is now checking nothing while reporting success"


def test_ids_are_unique(text):
    ids = [i for i, _ in summary_rows(text)]
    dupes = [i for i, n in collections.Counter(ids).items() if n > 1]
    assert not dupes, f"duplicate ids in the summary table: {dupes}. Ids are citable from other "\
                      "documents and commits; reusing one silently re-points every citation."


def test_every_status_is_from_the_vocabulary(text):
    bad = {(i, s) for i, s in summary_rows(text) if s not in STATUSES}
    assert not bad, f"statuses outside {sorted(STATUSES)}: {sorted(bad)}. A free-text status is "\
                    "how 'open' becomes 'sort of being looked at'."


def test_summary_and_detail_sections_agree(text, sections):
    summary = {i for i, _ in summary_rows(text)}
    detail = set(sections)
    assert summary == detail, (
        f"summary table and detail sections disagree.\n"
        f"  in summary, no section: {sorted(summary - detail)}\n"
        f"  section, not in summary: {sorted(detail - summary)}\n"
        "Every row must be reachable, or the table becomes a menu of dead links.")


def test_open_items_state_their_options(text, sections):
    """An open decision with no alternatives written down is a complaint, not a decision."""
    missing = [i for i, s in summary_rows(text)
               if s in NEEDS_OPTIONS and "**Options**" not in sections.get(i, "")]
    assert not missing, (
        f"OPEN items with no Options section: {missing}. State the alternatives and their "
        "consequences, or the item cannot actually be decided by anyone but its author.")


@pytest.mark.parametrize("field", ["Decision", "Effect"])
def test_resolved_items_record_decision_and_effect(text, sections, field):
    """The effect is the field other documents lose, and it is the one worth keeping."""
    missing = [i for i, s in summary_rows(text)
               if s == "RESOLVED" and f"**{field}**" not in sections.get(i, "")]
    assert not missing, (
        f"RESOLVED items with no **{field}**: {missing}. 'We did it and nothing changed' is a "
        "result and must survive; an entry without an effect is an intention.")


def test_resolved_items_name_a_commit(text, sections):
    """So the claim can be checked against the diff rather than believed."""
    missing = [i for i, s in summary_rows(text)
               if s == "RESOLVED" and not re.search(r"`[0-9a-f]{7,40}`", sections.get(i, ""))]
    assert not missing, f"RESOLVED items naming no commit: {missing}."


def test_the_named_commits_are_reachable(text, sections):
    """A hash of the right SHAPE is not a commit that exists.

    Found by walking into it: C46 was written with the hash of the commit that carried it, which
    an amend then orphaned. `git cat-file -t` still resolved the old hash — a dangling object
    survives until gc — so nothing was obviously wrong, and this file's shape-only check stayed
    green while the register pointed at a commit no branch reached. That is the same vacuous
    predicate the citation resolver was caught on: a test whose pass condition almost any input
    satisfies.

    Reachability, not existence, is the property worth asserting: an orphaned commit cannot be
    found by a reader with a fresh clone, which is the entire purpose of recording the hash.
    """
    import subprocess
    bad = []
    for i, s in summary_rows(text):
        if s != "RESOLVED":
            continue
        for h in set(re.findall(r"`([0-9a-f]{7,40})`", sections.get(i, ""))):
            r = subprocess.run(["git", "merge-base", "--is-ancestor", h, "HEAD"],
                               cwd=ROOT, capture_output=True, text=True)
            if r.returncode == 128:
                continue          # not a commit-ish at all: a hex-looking string, not a claim
            if r.returncode != 0:
                bad.append((i, h))
    assert not bad, (
        f"RESOLVED entries citing commits not reachable from HEAD: {bad}. A dangling hash reads "
        "as evidence and is not; re-point it at the commit that actually carries the work.")


def test_the_stated_counts_match_the_entries(text):
    """A hand-maintained total is the exact shape of stale claim this project keeps catching."""
    m = re.search(r"\*\*(\d+) OPEN · (\d+) READY · (\d+) BLOCKED · (\d+) MONITORED · "
                  r"(\d+) RESOLVED · (\d+) total\.\*\*", text)
    assert m, "the summary count line is missing or reworded; it is what a reader trusts first"
    claimed = dict(zip(("OPEN", "READY", "BLOCKED", "MONITORED", "RESOLVED"),
                       (int(g) for g in m.group(1, 2, 3, 4, 5))))
    actual = collections.Counter(s for _, s in summary_rows(text))
    for k, v in claimed.items():
        assert actual[k] == v, (f"register says {v} {k}, table has {actual[k]}. "
                                "Re-count; do not adjust the sentence to fit.")
    assert int(m.group(6)) == len(summary_rows(text)), "stated total does not match the rows"


def test_every_entry_declares_a_class(text, sections):
    """The class predicts the fix, so an entry without one has not been diagnosed."""
    missing = [i for i, b in sections.items() if "**Class**" not in b]
    assert not missing, f"entries with no **Class**: {missing}."


def test_the_register_checker_agrees():
    """`scripts/register.py --check` must pass, and it is the single source of this logic.

    The tests above grew first and check structure directly. The script was written afterwards, to
    replace the ad-hoc shell heredocs that damaged this file three times by executing its
    backticks as command substitutions -- so it also carries a mangling heuristic the tests above
    do not have. Running it here means the two cannot disagree silently, and means a future edit
    is checked by whichever of the two is stricter.
    """
    import subprocess
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "register.py"), "--check"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, (
        "scripts/register.py --check reports problems the tests above did not catch:\n"
        f"{r.stdout}\n{r.stderr}")


def test_the_your_decision_list_matches_the_table(text):
    """The header line naming which items need the owner's judgement is what they read first.

    It said "7 items — C1, C2, C3, C4, C16, C29, C30" while the table marked eleven: C33, C37,
    C43 and C45 had been added to the table without the summary being updated. Four decisions the
    owner was never told were waiting, including C45, which the same session had just opened.

    Hand-maintained lists about this file's own contents keep going stale; the fix is to derive
    them.
    """
    ids = re.findall(
        r"^\| \[(C\d+)\]\(#c\d+\)\s*\|[^|]*\|[^|]*\|[^|]*\|\s*your decision", text, re.M)
    m = re.search(r"\*\*(\d+) items need a judgement that is yours\*\* — ([^.]+)\.", text)
    assert m, "the 'items need a judgement' summary line is missing or reworded"
    assert int(m.group(1)) == len(ids), (
        f"the line claims {m.group(1)} items; the table marks {len(ids)}: {ids}")
    named = set(re.findall(r"C\d+", m.group(2)))
    assert named == set(ids), (
        f"named {sorted(named)} but the table marks {sorted(set(ids))}")


def test_no_heading_hardcodes_a_count_of_its_own_contents(text):
    """Section headings must not state how many items they contain.

    `test_the_your_decision_list_matches_the_table` was added because the *count line* went stale
    while the table moved. It did not cover the **heading two lines below it**, which read "The
    four that need your judgement" for as long as the register had seventeen — a hand-maintained
    number about this file's own contents, which is precisely the shape that test exists to
    forbid, sitting immediately beside the thing it fixed.

    The general rule this pins: derive counts or omit them. A heading cannot be derived, so it
    omits.
    """
    import re as _re
    bad = _re.findall(
        r"^##+ .*\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\d+)\b.*"
        r"(item|entry|entries|that need|which need)", text, _re.M | _re.I)
    assert not bad, (
        f"a heading states a count of its own contents: {bad}. Headings go stale silently because "
        "nothing derives them; say 'the ones that…' instead.")


def test_summary_and_detail_agree_on_STATUS_not_just_presence(text, sections):
    """The table's status must match the entry's own `**Status**` line.

    `test_summary_and_detail_sections_agree` compares the *set of ids*, so an entry can be RESOLVED
    in its detail and OPEN in the table and nothing fails — which happened to C53 on 2026-08-26,
    when a decision closed it and the row was not updated. The table is what a reader scans and
    what `test_the_stated_counts_match_the_entries` counts, so a stale row makes both the summary
    and the totals wrong while every existing check stays green.
    """
    import re as _re
    rows = dict(_re.findall(
        r"^\| \[(C\d+)\]\(#c\d+\)\s*\|[^|]*\|[^|]*\|\s*\*{0,2}([A-Z-]+)\*{0,2}\s*\|", text, _re.M))
    details = dict(_re.findall(r"\{#c(\d+)\}\s*\n\*\*Class\*\*[^\n]*?\*\*Status\*\*\s*(\w+)", text))
    details = {f"C{k}": v for k, v in details.items()}
    mismatched = {c: (rows[c], details[c]) for c in rows if c in details and rows[c] != details[c]}
    assert not mismatched, (
        f"table and entry disagree on status: {mismatched}. The table is what readers scan and what "
        "the totals are computed from, so a stale row is wrong twice over.")
