"""Collecting a host run must refuse a bad one, not file it beside the good ones.

[Claude 2026-09-09] `collect-wave.sh` is the DataSphere equivalent and cannot be reused: it calls
`datasphere project job get` to confirm the job reached SUCCESS, and a host run has no job. What a
host run has is a directory, and every fact that collector checks is present there in another form.

The refusals are the point. A completed-looking run that rendered in software, or that failed one
of its cells, or that produced no records, must not enter `results/records/` -- once there, nothing
distinguishes it from a good one.
"""
from __future__ import annotations

import pathlib
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "datasphere" / "native" / "collect-host-run.sh"


def _run_dir(tmp_path, *, log: str, egl: str | None, records: str | None):
    out = tmp_path / "native-out"
    out.mkdir(parents=True, exist_ok=True)
    (out / "job.log").write_text(log)
    if egl is not None:
        (out / "egl.json").write_text(egl)
    if records is not None:
        (out / "records.jsonl").write_text(records)
    return tmp_path


def _collect(run_dir):
    return subprocess.run(["bash", str(COLLECTOR), "idaac", str(run_dir)],
                          capture_output=True, text=True, timeout=120, cwd=str(ROOT))


def test_a_missing_log_is_refused(tmp_path):
    out = _collect(tmp_path / "nothing-here")
    assert out.returncode == 2, out.stdout + out.stderr
    assert "Nothing to judge the run by" in out.stderr


def test_a_failed_cell_is_refused(tmp_path):
    d = _run_dir(tmp_path, log="NATIVE_CELL_COMPLETED idaac-s101\nNATIVE_CELL_FAILED ppg-s1\n",
                 egl='{"renderer": "Tesla V100"}', records='{}\n')
    out = _collect(d)
    assert out.returncode == 1, out.stdout + out.stderr
    assert "NATIVE_CELL_FAILED" in out.stderr


def test_a_software_renderer_is_refused(tmp_path):
    """A record produced by llvmpipe is not comparable with anything else this project holds."""
    d = _run_dir(tmp_path, log="NATIVE_CELL_COMPLETED idaac-s101\n",
                 egl='{"renderer": "llvmpipe (LLVM 15.0.7, 256 bits)"}', records='{}\n')
    out = _collect(d)
    assert out.returncode == 1, out.stdout + out.stderr
    assert "rendered in SOFTWARE" in out.stderr


def test_completion_without_records_is_refused(tmp_path):
    """SUCCESS with no records is a finding, not an empty result to file away."""
    d = _run_dir(tmp_path, log="NATIVE_CELL_COMPLETED idaac-s101\n",
                 egl='{"renderer": "Tesla V100"}', records="")
    out = _collect(d)
    assert out.returncode == 1, out.stdout + out.stderr
    assert "produced no records" in out.stderr


def test_no_completion_marker_is_refused(tmp_path):
    d = _run_dir(tmp_path, log="some output but no marker\n",
                 egl='{"renderer": "Tesla V100"}', records='{}\n')
    out = _collect(d)
    assert out.returncode == 1, out.stdout + out.stderr
    assert "did not report completion" in out.stderr


def test_the_ledger_status_is_captured_not_piped_away():
    """`populate_evaluator_ledger.py | tail` would print its refusal and exit 0.

    The same defect is documented in collect-wave.sh's own header, because it happened there.
    """
    text = COLLECTOR.read_text()
    assert 'out="$("$BP" scripts/populate_evaluator_ledger.py' in text, (
        "the ledger call is piped, so its exit status is the filter's")
    assert "status=$?" in text
    assert "Do NOT write this entry" in text, (
        "the ledger can refuse while exiting 0; that string is the refusal")
