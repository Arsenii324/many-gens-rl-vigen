"""The fleet export must not quietly change what the records say.

`notes/production-readiness-by-class.md` asked for this "before the data exists rather than after",
and that is the point: an exporter written against real results resolves every ambiguity in
whichever direction makes that particular table come out. Two decisions are pinned here.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from export_fleet import SCHEMA, rows  # noqa: E402


def test_it_exports_every_record_including_superseded_ones():
    """Dropping them would make the export disagree with results/records invisibly."""
    total = sum(len([l for l in p.read_text(errors="replace").splitlines() if l.strip()])
                for p in (ROOT / "results" / "records").glob("*.jsonl"))
    assert len(rows()) == total, "every record line must produce exactly one row"


def test_superseded_rows_are_marked_not_dropped():
    all_rows = rows()
    assert any(r["closure_current"] is False for r in all_rows), (
        "the corpus contains superseded rows; if none is marked, the flag is not being computed")
    assert all("closure_current" in r for r in all_rows)


def test_current_only_is_a_strict_subset():
    assert len(rows(current_only=True)) <= len(rows())
    assert all(r["closure_current"] for r in rows(current_only=True))


def test_policy_mode_is_present_on_every_row():
    """Sampled and mode returns are different estimands. A return column without this invites the
    cross-block ranking comparison_blocks.py refuses."""
    for r in rows():
        if r["baseline"]:
            assert r["policy_mode"] in ("sample", "mode"), r


def test_the_schema_note_matches_the_columns_actually_written():
    """A schema note that can drift from the writer is worse than none."""
    declared = [c for c, _, _ in SCHEMA]
    sample = rows()[0]
    assert list(sample) == declared, (
        "the emitted columns and the documented schema disagree; the note is emitted by --schema "
        "precisely so it cannot drift from the writer")


def test_the_two_stopping_columns_carry_their_warning_in_the_schema():
    text = " ".join(m for _, _, m in SCHEMA)
    assert "may not be ranked" in text
    assert "no longer exists" in text
