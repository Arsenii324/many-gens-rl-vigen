"""The campaign view must not report a launchable campaign when a family is unattested.

`notes/PRODUCTION-RUNBOOK.md` lists "a single command that reports campaign state across cells" as
not built and worth having before day one. The risk with such a summary is the opposite of the one
it solves: a green board that is green because it did not look.
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from campaign_status import state_of  # noqa: E402

LIVE = {"rlvigen": "abc", "ctrl": "def"}


def test_an_unattested_family_blocks_every_one_of_its_cells():
    state, why = state_of("svea", "rlvigen", 101, 600000, {}, set(), attested=set(), live=LIVE)
    assert state == "BLOCKED", (state, why)


def test_a_record_on_the_live_closure_is_done():
    records = {("svea", 101): [{"frame": 600000, "evaluator_revision": "abc"}]}
    state, _ = state_of("svea", "rlvigen", 101, 600000, records, set(), {"rlvigen"}, LIVE)
    assert state == "DONE"


def test_a_record_on_a_dead_closure_is_superseded_not_done():
    """The failure this project has actually had: a record that looks complete and describes a
    tree that no longer exists."""
    records = {("svea", 101): [{"frame": 600000, "evaluator_revision": "OLD"}]}
    state, why = state_of("svea", "rlvigen", 101, 600000, records, set(), {"rlvigen"}, LIVE)
    assert state == "SUPERSEDED", (state, why)


def test_submitted_without_records_is_running_not_missing():
    state, _ = state_of("svea", "rlvigen", 101, 600000, {}, {("svea", 101)}, {"rlvigen"}, LIVE)
    assert state == "RUNNING"


def test_never_submitted_is_missing():
    state, _ = state_of("svea", "rlvigen", 101, 600000, {}, set(), {"rlvigen"}, LIVE)
    assert state == "MISSING"


def test_a_record_short_of_the_endpoint_is_not_done():
    """A 550k record must never satisfy a 600k cell -- the terminal-checkpoint concern in its
    reporting form."""
    records = {("svea", 101): [{"frame": 550000, "evaluator_revision": "abc"}]}
    state, _ = state_of("svea", "rlvigen", 101, 600000, records, set(), {"rlvigen"}, LIVE)
    assert state == "RUNNING"


def test_the_real_schedule_parses_and_covers_thirty_six_cells():
    schedule = json.loads(
        (ROOT / "datasphere" / "native" / "production-schedule-v100.json").read_text())
    cells = sum(len(r.get("seeds", schedule["seeds"])) for r in schedule["rows"])
    assert cells == 36, f"the campaign is 12 baselines x 3 seeds; schedule says {cells}"
