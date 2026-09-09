"""The navigation tool must report provenance, and must not imply an answer.

[Claude 2026-09-09] Built after answering "why is idaac num_processes=1" cost a subagent, a grep
sweep and `git log -S` archaeology -- which found the answer AND six documents still asserting the
discarded value in the present tense.

The hazard in automating that is making it worse: a tool that prints a newest-first list invites a
reader to take the top row as the answer. Two of this repo's own failure modes say why that is
wrong. Recency is last-touched, which a typo fix moves. And several notes here were written by an
assistant from whatever happened to be in its context, so a confident, exhaustive-sounding review
may have seen a subset -- breadth is a claim, not a property of tone.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts" / "where_is_this_decided.py"


def _run(*args):
    return subprocess.run([sys.executable, str(TOOL), *args],
                          capture_output=True, text=True, timeout=300, cwd=str(ROOT))


def test_it_finds_a_known_topic_and_orders_it():
    out = _run("num_processes", "--files-only", "--limit", "6")
    assert out.returncode == 0, out.stderr
    assert "NEWEST FILE FIRST" in out.stdout


def test_it_refuses_to_imply_a_ruling():
    out = _run("num_processes", "--files-only", "--limit", "3")
    body = out.stdout
    assert "ORDERING, not a ruling" in body
    assert "Read the set, not the top row" in body, "invites settling on the first hit"
    assert "last-touched" in body.lower() or "LAST-TOUCHED" in body, (
        "does not warn that recency is last-touched, which a typo fix also moves")
    assert "subset" in body, (
        "does not warn that an exhaustive-sounding note may have seen only part of the tree")


def test_it_flags_documents_carrying_supersession_markers():
    out = _run("num_processes", "--files-only", "--limit", "12")
    assert "supersession marker" in out.stdout, (
        "stale-but-marked documents are indistinguishable from current ones")


def test_it_points_at_the_change_rather_than_the_file_mtime():
    out = _run("num_processes", "--files-only", "--limit", "2")
    assert "git log -S" in out.stdout, (
        "a reader is left with file recency and no route to the commit that changed the value")


def test_a_missing_topic_is_not_silent_success():
    """The term is built at runtime because the tool searches tests/ and would find this file.

    [Claude 2026-09-09] The first version hard-coded a "no such topic" string, and the tool duly
    found it -- in this test. A literal in a test is part of the tree the test searches.
    """
    import uuid
    absent = "absent" + uuid.uuid4().hex[:12]
    out = _run(absent)
    assert out.returncode == 1, "an empty result exits 0 and reads like 'nothing to worry about'"
    assert "no occurrences" in out.stdout
