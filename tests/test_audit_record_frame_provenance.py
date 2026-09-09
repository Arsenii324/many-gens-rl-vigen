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


def test_the_real_ppg_alternating_cadence_is_NOT_flagged(tmp_path):
    """51200/49152 alternating is ic_per_save=50000 quantised onto a 2048-frame rollout.

    Every correct ppg run produces it. The first version of the check flagged all twelve gaps.
    """
    frames = [0, 51200, 100352, 151552, 200704, 251904, 301056, 350208, 401408, 450560,
              501760, 550912, 600064]
    (tmp_path / "job.log").write_text(
        "".join(f"Saving to  /run/model{i:03d}.jd IC={f}\n" for i, f in enumerate(frames)))
    _write(tmp_path, [{"baseline": "ppg", "regime": "train",
                       "checkpoint_sha256": _sha(b"absent"), "frame": 1}])
    code, out = _run(tmp_path)
    assert code == 0, out
    assert "SAVE CADENCE IS UNEVEN" not in out, out
    assert "Save cadence even across 13 logged saves" in out


def test_uneven_save_cadence_is_reported_from_the_log_alone(tmp_path):
    # No records reference these, and no checkpoints exist: the cadence check must still fire.
    (tmp_path / "job.log").write_text(
        "Saving to  /run/model001.jd IC=50000\n"
        "Saving to  /run/model002.jd IC=100000\n"
        "Saving to  /run/model003.jd IC=150000\n"
        "Saving to  /run/model004.jd IC=200000\n"
        "Saving to  /run/model005.jd IC=400000\n")
    _write(tmp_path, [{"baseline": "ppg", "regime": "train",
                       "checkpoint_sha256": _sha(b"absent"), "frame": 1}])
    code, out = _run(tmp_path)
    assert code == 0, out
    assert "SAVE CADENCE IS UNEVEN" in out
    assert "200000 -> 400000 is 200000" in out


def test_even_save_cadence_says_so(tmp_path):
    (tmp_path / "job.log").write_text(
        "Saving to  /run/model001.jd IC=50000\n"
        "Saving to  /run/model002.jd IC=100000\n"
        "Saving to  /run/model003.jd IC=150000\n"
        "Saving to  /run/model004.jd IC=200000\n")
    _write(tmp_path, [{"baseline": "ppg", "regime": "train",
                       "checkpoint_sha256": _sha(b"absent"), "frame": 1}])
    code, out = _run(tmp_path)
    assert code == 0, out
    assert "Save cadence even across 4 logged saves" in out


def test_an_unnamed_snapshot_is_corroborated_through_its_frame_named_alias(tmp_path):
    """The endpoint measures snapshot.pt, which carries no frame. Its twin does.

    Measured on card0-20260909-013936: every row with a checkpoint_sha256 matched `snapshot.pt`,
    so the auditor's first version read the entire endpoint grid as UNVERIFIABLE -- the headline
    measurement being the one with no checkable label, for every family.
    """
    blob = b"terminal-weights"
    (tmp_path / "snapshot.pt").write_bytes(blob)
    (tmp_path / "agent-robosuite:Door-idaac-s101_598016.pt").write_bytes(blob)
    _write(tmp_path, [{"baseline": "idaac", "regime": "train",
                       "checkpoint_sha256": _sha(blob), "frame": 598016}])
    code, out = _run(tmp_path, "--strict")
    assert code == 0, out
    assert _count(out, "corroborated") == 1, out
    assert "byte-identical frame-named alias" in out
    assert _count(out, "unverifiable") == 0


def test_an_unnamed_snapshot_with_no_alias_stays_unverifiable(tmp_path):
    """The alias must be a real file, not an assumption that one exists."""
    blob = b"terminal-weights"
    (tmp_path / "snapshot.pt").write_bytes(blob)
    _write(tmp_path, [{"baseline": "idaac", "regime": "train",
                       "checkpoint_sha256": _sha(blob), "frame": 598016}])
    code, out = _run(tmp_path, "--strict")
    assert code == 0, out
    assert _count(out, "unverifiable") == 1, out
    assert _count(out, "corroborated") == 0


def test_an_alias_disagreeing_with_the_record_is_still_a_mismatch(tmp_path):
    blob = b"terminal-weights"
    (tmp_path / "snapshot.pt").write_bytes(blob)
    (tmp_path / "agent-robosuite:Door-idaac-s101_550912.pt").write_bytes(blob)
    _write(tmp_path, [{"baseline": "idaac", "regime": "train",
                       "checkpoint_sha256": _sha(blob), "frame": 598016}])
    code, out = _run(tmp_path, "--strict")
    assert code == 1, out
    assert _count(out, "MISMATCHED") == 1


def test_the_delivery_bundle_is_not_counted_beside_its_own_sources(tmp_path):
    """records_delivery.jsonl IS the concatenation; globbing both doubled every total.

    Measured on card0-20260909-035152: a 553-row bundle audited as 1,106 records.
    """
    blob = b"w"
    (tmp_path / "agent-robosuite:Door-idaac-s101_100352.pt").write_bytes(blob)
    row = {"baseline": "idaac", "regime": "train",
           "checkpoint_sha256": _sha(blob), "frame": 100352}
    cells = tmp_path / "cells" / "idaac-s101"
    cells.mkdir(parents=True)
    (cells / "offline_eval_curve.jsonl").write_text(json.dumps(row) + "\n")
    (tmp_path / "records_delivery.jsonl").write_text(json.dumps(row) + "\n")
    code, out = _run(tmp_path)
    assert code == 0, out
    assert "1 record(s)" in out, f"the bundle must not be counted beside its sources:\n{out}"
    assert _count(out, "corroborated") == 1


def test_a_bundle_alone_is_still_audited(tmp_path):
    """Skipping the bundle must not mean skipping it when it is all there is."""
    blob = b"w"
    (tmp_path / "agent-robosuite:Door-idaac-s101_100352.pt").write_bytes(blob)
    (tmp_path / "records_delivery.jsonl").write_text(json.dumps(
        {"baseline": "idaac", "regime": "train",
         "checkpoint_sha256": _sha(blob), "frame": 100352}) + "\n")
    code, out = _run(tmp_path)
    assert code == 0, out
    assert _count(out, "corroborated") == 1, out
