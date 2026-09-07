"""No test may write into `results/submissions.jsonl`.

`results/submissions.jsonl` is the production attempt record: job id, config, commit, dirtiness and
input hashes at submit time. It is what `scripts/attempt_ledger.py` reads to say which attempt
produced which result, and therefore what makes "a rerun never silently replaces a failed seed" a
record rather than a habit.

It had 32 rows when `attempt_ledger.py` first ran, and **every one was a fixture** —
`bt1abcdefghijklmnopq` repeated, against configs named `production-with-records.yaml` and
`eval-with-records.yaml`. Three test modules stub the DataSphere CLI and run `job.sh submit`, and
`job.sh` appended to the repo path because `SUBMISSION_LEDGER` defaults to it.

Nothing failed. The ledger simply became unusable while continuing to look like a ledger, which is
the worst shape a provenance artifact can take. This is derived rather than listed so a fourth test
module cannot reintroduce it.
"""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
JOB = ROOT / "datasphere" / "native" / "job.sh"


def test_the_ledger_path_is_overridable():
    """If it were hardcoded, no test could avoid the repo path and this rule would be unkeepable."""
    assert 'SUBMISSION_LEDGER="${SUBMISSION_LEDGER:-results/submissions.jsonl}"' in JOB.read_text()


def test_every_test_that_submits_redirects_the_ledger():
    offenders = []
    for path in sorted(TESTS.glob("test_*.py")):
        if path.name == pathlib.Path(__file__).name:
            continue
        text = path.read_text()
        submits = '"submit"' in text and "JOB" in text
        if submits and "SUBMISSION_LEDGER" not in text:
            offenders.append(path.name)
    assert not offenders, (
        "these test modules invoke `job.sh submit` without redirecting SUBMISSION_LEDGER, so they "
        f"append fixture rows to the real attempt record: {offenders}")


def test_the_repo_ledger_holds_no_fixture_rows():
    """Absent is fine -- job.sh creates it on the first real submit. Poisoned is not."""
    ledger = ROOT / "results" / "submissions.jsonl"
    if not ledger.is_file():
        return
    import json
    fixtures = []
    for line in ledger.read_text().splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        job = str(row.get("job_id", ""))
        # Real DataSphere ids are opaque and mixed; the stub id is a literal alphabet run.
        if "abcdefghijklmnop" in job or not job.startswith("bt1"):
            fixtures.append(job)
    assert not fixtures, (
        f"the production attempt record carries {len(fixtures)} fixture row(s): {fixtures[:5]}")
