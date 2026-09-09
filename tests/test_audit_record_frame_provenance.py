"""Every grade the frame-provenance auditor can print must be reachable, and MISMATCH must fail.

An auditor that cannot distinguish its own grades is worse than none: it lends the authority of a
check to rows nothing checked. So each case below constructs the exact situation and asserts the
grade, and the two mismatch cases assert a non-zero `--strict` exit -- the property that makes the
tool usable in a gate rather than only in a report.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "audit_record_frame_provenance.py"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run(directory: pathlib.Path, *extra: str) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, str(SCRIPT), str(directory), *extra],
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def _write(directory: pathlib.Path, records: list[dict]) -> None:
    with (directory / "records.jsonl").open("w") as fh:
        for row in records:
            fh.write(json.dumps(row) + "\n")


def _count(out: str, label: str) -> int:
    for line in out.splitlines():
        stripped = line.strip()
        if stripped.startswith(label):
            return int(stripped[len(label):].split()[0])
    raise AssertionError(f"no {label!r} line in:\n{out}")


def test_named_frame_agreeing_is_corroborated(tmp_path):
    blob = b"idaac-weights"
    (tmp_path / "agent-robosuite:Door-idaac-s101_100352.pt").write_bytes(blob)
    _write(tmp_path, [{"baseline": "idaac", "regime": "train",
                       "checkpoint_sha256": _sha(blob), "frame": 100352}])
    code, out = _run(tmp_path, "--strict")
    assert code == 0, out
    assert _count(out, "corroborated") == 1
    assert _count(out, "tied") == 0


def test_named_frame_disagreeing_is_a_mismatch_and_fails_strict(tmp_path):
    blob = b"idaac-weights"
    (tmp_path / "agent-robosuite:Door-idaac-s101_100352.pt").write_bytes(blob)
    _write(tmp_path, [{"baseline": "idaac", "regime": "train",
                       "checkpoint_sha256": _sha(blob), "frame": 100000}])
    code, out = _run(tmp_path, "--strict")
    assert code == 1, out
    assert _count(out, "MISMATCHED") == 1
    assert "named 100352" in out


def test_index_named_checkpoint_with_a_log_line_is_tied_not_corroborated(tmp_path):
    blob = b"ppg-weights"
    (tmp_path / "model008.jd").write_bytes(blob)
    (tmp_path / "job.log").write_text(
        "Saving to  /tmp/native-work/runs/ppg-s1/model008.jd IC=401408\n")
    _write(tmp_path, [{"baseline": "ppg", "regime": "train",
                       "checkpoint_sha256": _sha(blob), "frame": 401408}])
    code, out = _run(tmp_path, "--strict")
    assert code == 0, out
    assert _count(out, "tied") == 1
    # The whole point: this must NOT be promoted to corroboration.
    assert _count(out, "corroborated") == 0
    assert "TIED IS WEAKER THAN CORROBORATED" in out


def test_log_line_disagreeing_with_the_record_is_a_mismatch(tmp_path):
    blob = b"ppg-weights"
    (tmp_path / "model008.jd").write_bytes(blob)
    (tmp_path / "job.log").write_text(
        "Saving to  /tmp/native-work/runs/ppg-s1/model008.jd IC=401408\n")
    _write(tmp_path, [{"baseline": "ppg", "regime": "train",
                       "checkpoint_sha256": _sha(blob), "frame": 400000}])
    code, out = _run(tmp_path, "--strict")
    assert code == 1, out
    assert _count(out, "MISMATCHED") == 1
    assert "IC=401408" in out


def test_index_named_checkpoint_without_a_log_line_stays_unverifiable(tmp_path):
    blob = b"ppg-weights"
    (tmp_path / "model008.jd").write_bytes(blob)
    _write(tmp_path, [{"baseline": "ppg", "regime": "train",
                       "checkpoint_sha256": _sha(blob), "frame": 401408}])
    code, out = _run(tmp_path, "--strict")
    assert code == 0, out
    assert _count(out, "unverifiable") == 1
    assert _count(out, "tied") == 0
    assert "UNVERIFIABLE IS NOT OK" in out


def test_a_row_whose_hash_matches_nothing_is_unverifiable(tmp_path):
    _write(tmp_path, [{"baseline": "ppg", "regime": "train",
                       "checkpoint_sha256": _sha(b"absent"), "frame": 401408}])
    code, out = _run(tmp_path)
    assert code == 0, out
    assert _count(out, "unverifiable") == 1


def test_uneven_save_cadence_is_reported_from_the_log_alone(tmp_path):
    # No records reference these, and no checkpoints exist: the cadence check must still fire.
    (tmp_path / "job.log").write_text(
        "Saving to  /run/model001.jd IC=50000\n"
        "Saving to  /run/model002.jd IC=100000\n"
        "Saving to  /run/model003.jd IC=150000\n"
        "Saving to  /run/model004.jd IC=250000\n")
    _write(tmp_path, [{"baseline": "ppg", "regime": "train",
                       "checkpoint_sha256": _sha(b"absent"), "frame": 1}])
    code, out = _run(tmp_path)
    assert code == 0, out
    assert "SAVE CADENCE IS UNEVEN" in out
    assert "150000 -> 250000 is 100000" in out


def test_even_save_cadence_says_so(tmp_path):
    (tmp_path / "job.log").write_text(
        "Saving to  /run/model001.jd IC=50000\n"
        "Saving to  /run/model002.jd IC=100000\n"
        "Saving to  /run/model003.jd IC=150000\n")
    _write(tmp_path, [{"baseline": "ppg", "regime": "train",
                       "checkpoint_sha256": _sha(b"absent"), "frame": 1}])
    code, out = _run(tmp_path)
    assert code == 0, out
    assert "Save cadence even across 3 logged saves" in out
