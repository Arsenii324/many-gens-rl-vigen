"""The wave collector must refuse, not skip.

[Claude 2026-09-08] Written alongside `datasphere/native/collect-wave.sh`, because a collector that
quietly passes over a failed cell leaves the ledger reporting 6/7 with no indication which family is
missing or why -- and this project's standing rule is that an instrument which could not run must
never read as one that ran.

Three ways a family can fail to be collected, and all three must be fatal:
  - the job is not SUCCESS
  - it is SUCCESS and emitted no records, which is itself a finding
  - the records exist and `populate_evaluator_ledger.py` REFUSES them because their evaluator
    revision is not the live one

The third is the subtle one: the populate step's output was piped through `tail`, which discards
its exit status, so the collector printed "Do NOT write this entry" and then exited 0.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "datasphere" / "native" / "collect-wave.sh"


def test_it_exists_and_parses():
    assert SCRIPT.is_file()
    import subprocess
    assert subprocess.run(["bash", "-n", str(SCRIPT)]).returncode == 0


def test_a_non_success_job_is_recorded_as_failed():
    text = SCRIPT.read_text()
    assert 'if [[ "$state" != "SUCCESS" ]]' in text
    assert re.search(r'!= "SUCCESS".{0,400}failed\+=\("\$family:\$job:\$state"\)', text, re.S), (
        "the non-SUCCESS branch must add to `failed`, not just print and continue")


def test_success_with_no_records_is_a_finding_not_a_skip():
    text = SCRIPT.read_text()
    assert "SUCCESS with no records is itself a finding" in text
    assert 'failed+=("$family:$job:no-records")' in text


def test_a_ledger_refusal_is_captured_and_not_swallowed_by_tail():
    """The regression: piping populate through `tail` discarded its exit status."""
    text = SCRIPT.read_text()
    assert "status=$?" in text, "the populate exit status must be captured before any pipe"
    assert 'grep -q "Do NOT write this entry"' in text, (
        "the ledger's own refusal wording is the second signal, in case the exit code changes")
    assert 'failed+=("$family:$job:stale-revision")' in text


def test_it_exits_non_zero_when_anything_was_not_collected():
    text = SCRIPT.read_text()
    tail = text[text.index("NOT COLLECTED"):]
    assert "exit 1" in tail, "a short ledger must not exit 0"
    assert "must not be reported as such" in tail
