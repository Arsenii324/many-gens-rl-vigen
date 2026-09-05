"""Submission must pass command overrides into family memory admission."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_job_submission_forwards_configured_extra_overrides_to_memory_check():
    source = (ROOT / "datasphere/native/job.sh").read_text()
    assert "cfg_extra_overrides" in source
    assert "NATIVE_EXTRA_OVERRIDES=\"$cfg_extra_overrides\"" in source
    assert "check-memory --cells \"$cells\" --tier \"$tier\"" in source
