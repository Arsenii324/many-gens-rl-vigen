"""Every refusal in collect-host-run.sh must fire, and the success path must install the BUNDLE.

The success path of this collector had never run on a real completed cell. When it was finally read
against the runner on 2026-09-09 it was pointing at `native-out/records.jsonl`, which no completed
host run produces -- the delivered bundle is `records_delivery.jsonl`. It refused rather than losing
data, but only because the wrong file happened to be absent rather than partial.

So these tests pin two things: that each guard fires, and that the collector's choice of source file
is checked against the log. The offline-row and emitted-count cases are the ones that make a future
divergence loud, and they are the reason this file exists rather than a comment.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "datasphere" / "native" / "collect-host-run.sh"

COMPLETED = "=== NATIVE_CELL_COMPLETED idaac-s101 ===\n"
EVALUATED = "=== NATIVE_CURVE_EVAL_COMPLETED idaac stamps=11 ===\n"


def _row(phase: str) -> str:
    return json.dumps({"schema": 2, "phase": phase, "regime": "train", "baseline": "idaac"})


def _run_dir(tmp_path, *, log: str | None = COMPLETED, bundle: list[str] | None = None,
             egl: dict | None = None, training_rows: list[str] | None = None) -> pathlib.Path:
    run = tmp_path / "card0-20260909-035152"
    out = run / "native-out"
    out.mkdir(parents=True)
    if log is not None:
        (out / "job.log").write_text(log)
    if bundle is not None:
        (out / "records_delivery.jsonl").write_text("".join(r + "\n" for r in bundle))
    if training_rows is not None:
        (out / "records.jsonl").write_text("".join(r + "\n" for r in training_rows))
    if egl is not None:
        (out / "egl.json").write_text(json.dumps(egl))
    return run


def _stub_bp(tmp_path) -> str:
    """A BP that succeeds silently: the ledger and gates are not under test here."""
    stub = tmp_path / "bp-stub"
    stub.write_text("#!/bin/sh\nexit 0\n")
    stub.chmod(0o755)
    return str(stub)


def _collect(run: pathlib.Path, tmp_path, **env_extra) -> tuple[int, str]:
    env = dict(os.environ)
    env["RECORDS_DIR"] = str(tmp_path / "records")
    env["BP"] = _stub_bp(tmp_path)
    env.update(env_extra)
    proc = subprocess.run(["bash", str(SCRIPT), "idaac", str(run)],
                          capture_output=True, text=True, env=env, cwd=str(ROOT))
    return proc.returncode, proc.stdout + proc.stderr


def test_missing_job_log_refuses(tmp_path):
    run = _run_dir(tmp_path, log=None)
    code, out = _collect(run, tmp_path)
    assert code == 2, out
    assert "no job.log" in out


def test_a_failed_cell_refuses(tmp_path):
    run = _run_dir(tmp_path, log=COMPLETED + "=== NATIVE_CELL_FAILED idaac-s101 rc=1 ===\n",
                   bundle=[_row("offline-eval")])
    code, out = _collect(run, tmp_path)
    assert code == 1, out
    assert "NATIVE_CELL_FAILED" in out


def test_no_completion_marker_refuses(tmp_path):
    run = _run_dir(tmp_path, log="=== NATIVE_CELL_BEGIN idaac-s101 ===\n",
                   bundle=[_row("offline-eval")])
    code, out = _collect(run, tmp_path)
    assert code == 1, out
    assert "did not report completion" in out


def test_software_renderer_refuses(tmp_path):
    run = _run_dir(tmp_path, bundle=[_row("offline-eval")],
                   egl={"renderer": "llvmpipe (LLVM 15.0.7, 256 bits)"})
    code, out = _collect(run, tmp_path)
    assert code == 1, out
    assert "rendered in SOFTWARE" in out


def test_absent_bundle_refuses(tmp_path):
    run = _run_dir(tmp_path, bundle=None)
    code, out = _collect(run, tmp_path)
    assert code == 1, out
    assert "records_delivery.jsonl is absent or empty" in out.replace(str(run) + "/native-out/", "")


def test_a_present_records_jsonl_is_named_as_the_wrong_file(tmp_path):
    """The exact defect: records.jsonl is training rows, never the bundle."""
    run = _run_dir(tmp_path, bundle=None, training_rows=[_row("train")])
    code, out = _collect(run, tmp_path)
    assert code == 1, out
    assert "do not point this script at records.jsonl" in out
    assert "ZERO" in out and "offline-eval rows" in out


def test_evaluated_run_whose_bundle_has_no_offline_rows_refuses(tmp_path):
    run = _run_dir(tmp_path, log=COMPLETED + EVALUATED, bundle=[_row("train"), _row("train")])
    code, out = _collect(run, tmp_path)
    assert code == 1, out
    assert "ZERO offline-eval rows" in out


def test_row_count_disagreeing_with_the_runner_refuses(tmp_path):
    run = _run_dir(tmp_path,
                   log=COMPLETED + EVALUATED + "=== NATIVE_RECORDS_EMITTED 528 rows -> records_delivery.jsonl ===\n",
                   bundle=[_row("offline-eval")])
    code, out = _collect(run, tmp_path)
    assert code == 1, out
    assert "emitted 528 rows; this copy has 1" in out


def test_a_good_run_installs_the_bundle(tmp_path):
    rows = [_row("train")] + [_row("offline-eval")] * 3
    run = _run_dir(tmp_path,
                   log=COMPLETED + EVALUATED + "=== NATIVE_RECORDS_EMITTED 4 rows -> records_delivery.jsonl ===\n",
                   bundle=rows, egl={"renderer": "Tesla V100-SXM2-32GB/PCIe/SSE2"})
    code, out = _collect(run, tmp_path)
    assert code == 0, out
    assert "offline-eval rows: 3" in out
    dest = tmp_path / "records" / "card0-20260909-035152__records.jsonl"
    assert dest.is_file(), out
    assert len(dest.read_text().splitlines()) == 4


def test_it_refuses_to_overwrite_a_different_past_run(tmp_path):
    """A job id is unique per launch, so a collision means a re-collection or a re-used name.

    Either way the file already there is a completed production cell's only installed copy.
    """
    rows = [_row("train")] + [_row("offline-eval")] * 3
    run = _run_dir(tmp_path,
                   log=COMPLETED + EVALUATED + "=== NATIVE_RECORDS_EMITTED 4 rows -> records_delivery.jsonl ===\n",
                   bundle=rows, egl={"renderer": "Tesla V100-SXM2-32GB/PCIe/SSE2"})
    records = tmp_path / "records"
    records.mkdir()
    dest = records / "card0-20260909-035152__records.jsonl"
    dest.write_text(json.dumps({"phase": "eval", "precious": True}) + "\n")
    before = dest.read_text()
    code, out = _collect(run, tmp_path, RECORDS_DIR=str(records))
    assert code == 1, out
    assert "already exists and DIFFERS" in out
    assert dest.read_text() == before, "the existing records were modified"


def test_recollecting_the_identical_run_is_idempotent(tmp_path):
    rows = [_row("train")] + [_row("offline-eval")] * 3
    run = _run_dir(tmp_path,
                   log=COMPLETED + EVALUATED + "=== NATIVE_RECORDS_EMITTED 4 rows -> records_delivery.jsonl ===\n",
                   bundle=rows, egl={"renderer": "Tesla V100-SXM2-32GB/PCIe/SSE2"})
    records = tmp_path / "records"
    records.mkdir()
    dest = records / "card0-20260909-035152__records.jsonl"
    dest.write_text((run / "native-out" / "records_delivery.jsonl").read_text())
    code, out = _collect(run, tmp_path, RECORDS_DIR=str(records))
    assert code == 0, out
    assert "byte-identical" in out


def _assembled(phase="offline-eval"):
    r = _row(phase)
    d = json.loads(r)
    d["_assembled_after_reaping"] = {"reason": "watch budget", "source": "x", "tool": "y"}
    return json.dumps(d)


def test_a_watch_stopped_cell_is_refused_by_default_and_names_the_path(tmp_path):
    """NATIVE_CELL_COMPLETED prints after evaluation, so a stopped cell never has it."""
    run = _run_dir(tmp_path, log="=== NATIVE_CELL_BEGIN idaac-s101 ===\n" + EVALUATED,
                   bundle=[_row("offline-eval")])
    (run / "native-out" / "cells" / "idaac-s101").mkdir(parents=True, exist_ok=True)
    (run / "native-out" / "cells" / "idaac-s101" / "offline_eval_endpoint.jsonl").write_text("{}\n")
    code, out = _collect(run, tmp_path)
    assert code == 1, out
    assert "did not report completion" in out
    assert "assemble_reaped_delivery.py" in out, "the refusal must name the recovery path"
    assert "NATIVE_ACCEPT_WATCH_STOP=1" in out


def test_the_flag_collects_an_assembled_bundle_and_marks_it(tmp_path):
    rows = [_assembled("train")] + [_assembled() for _ in range(3)]
    run = _run_dir(tmp_path, log="=== NATIVE_CELL_BEGIN idaac-s101 ===\n" + EVALUATED,
                   bundle=rows, egl={"renderer": "Tesla V100-SXM2-32GB/PCIe/SSE2"})
    code, out = _collect(run, tmp_path, NATIVE_ACCEPT_WATCH_STOP="1")
    assert code == 0, out
    assert "NATIVE_COLLECTED_AFTER_WATCH_STOP" in out
    assert "must not be read as one that finished" in out
    assert "all 4 row(s) marked" in out


def test_the_flag_refuses_a_bundle_that_was_not_assembled(tmp_path):
    """The flag opens the assembler's path, not a general override for incomplete runs."""
    run = _run_dir(tmp_path, log="=== NATIVE_CELL_BEGIN idaac-s101 ===\n" + EVALUATED,
                   bundle=[_row("train")] + [_row("offline-eval")] * 3,
                   egl={"renderer": "Tesla V100-SXM2-32GB/PCIe/SSE2"})
    code, out = _collect(run, tmp_path, NATIVE_ACCEPT_WATCH_STOP="1")
    assert code == 1, out
    assert "_assembled_after_reaping" in out
    assert "not to wave through an arbitrary incomplete run" in out


def test_the_flag_still_refuses_a_log_with_no_cell_begin(tmp_path):
    run = _run_dir(tmp_path, log="nothing useful here\n", bundle=[_assembled()])
    code, out = _collect(run, tmp_path, NATIVE_ACCEPT_WATCH_STOP="1")
    assert code == 1, out
    assert "nothing a watch stop would explain" in out


def test_the_flag_does_not_override_a_failed_cell(tmp_path):
    run = _run_dir(tmp_path,
                   log="=== NATIVE_CELL_BEGIN x ===\n=== NATIVE_CELL_FAILED x rc=1 ===\n",
                   bundle=[_assembled()])
    code, out = _collect(run, tmp_path, NATIVE_ACCEPT_WATCH_STOP="1")
    assert code == 1, out
    assert "NATIVE_CELL_FAILED" in out


# --- Added 2026-09-10: the oversized-delivery class, and the supplementary-pass marker ----------
#
# `records_delivery.jsonl` on card0-20260909-115331 was 1,365,573,627 bytes for 964 rows, because
# `collect_record_delivery` stamps the run manifest onto EVERY row and that manifest inlined the
# resource sampler's whole per-second series. The guard is on BYTES PER ROW, not total bytes: a
# genuinely large run has many rows, so a total-size threshold would refuse it while passing a
# small run with a bloated manifest, which is exactly backwards.

def _fat_row(payload_bytes: int) -> str:
    return json.dumps({"schema": 2, "phase": "offline-eval", "regime": "train",
                       "baseline": "idaac", "_run_provenance": {"blob": "x" * payload_bytes}})


def test_a_delivery_over_a_megabyte_per_row_refuses(tmp_path):
    run = _run_dir(tmp_path, log=COMPLETED + EVALUATED,
                   bundle=[_fat_row(1_200_000) for _ in range(3)])
    code, out = _collect(run, tmp_path)
    assert code == 1, out
    assert "OVERSIZED ROWS" in out
    assert "REFUSING at over 1 MB/row" in out
    # The refusal must name a tool that exists, or it is worse than no refusal.
    assert (ROOT / "scripts" / "explain_delivery_size.py").is_file()
    assert "explain_delivery_size.py" in out


def test_the_fat_delivery_refusal_is_overridable(tmp_path):
    run = _run_dir(tmp_path, log=COMPLETED + EVALUATED,
                   bundle=[_fat_row(1_200_000) for _ in range(3)])
    code, out = _collect(run, tmp_path, NATIVE_ACCEPT_FAT_DELIVERY="1")
    assert "OVERSIZED ROWS" in out
    assert "REFUSING at over 1 MB/row" not in out, out


def test_a_moderately_fat_delivery_warns_but_installs(tmp_path):
    """34.6 KB/row is what the idaac bundle actually is; 100 KB warns without blocking."""
    run = _run_dir(tmp_path, log=COMPLETED + EVALUATED,
                   bundle=[_fat_row(100_000) for _ in range(3)])
    code, out = _collect(run, tmp_path)
    assert "OVERSIZED ROWS" in out
    assert "REFUSING" not in out, out


def test_a_normal_delivery_says_nothing_about_size(tmp_path):
    run = _run_dir(tmp_path, log=COMPLETED + EVALUATED, bundle=[_row("offline-eval")])
    code, out = _collect(run, tmp_path)
    assert "OVERSIZED ROWS" not in out, out


def test_a_missing_supplementary_pass_is_reported_and_does_not_refuse(tmp_path):
    """A cell can now be collectable AND missing its mode comparison; that must be visible.

    Since 2026-09-10 a failing non-native endpoint pass no longer fails the cell -- ppg-s1 lost a
    complete 44-row native grid that way. Nothing else in this collector would mention the gap.
    """
    log = (COMPLETED + EVALUATED
           + "=== NATIVE_ENDPOINT_SUPPLEMENTARY_FAILED ppg policy_mode=mode rc=1 ===\n"
           + "=== NATIVE_ENDPOINT_SUPPLEMENTARY_INCOMPLETE ppg passes=1 ===\n")
    run = _run_dir(tmp_path, log=log, bundle=[_row("offline-eval")])
    code, out = _collect(run, tmp_path)
    assert "SUPPLEMENTARY PASS MISSING" in out, out
    assert "policy_mode=mode" in out
    assert "REFUSING" not in out, out
