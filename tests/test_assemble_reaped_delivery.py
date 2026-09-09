"""A reaped cell's rows must be recoverable, and never mistakable for a delivered bundle.

`collect_record_delivery` runs after evaluation, so a cell whose watch expires mid-evaluation has
written every row and assembled none. The measurements are unassembled, not lost.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "assemble_reaped_delivery.py"


def _run(run_dir: pathlib.Path, out: pathlib.Path) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, str(SCRIPT), str(run_dir), "--out", str(out)],
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def _cell(tmp_path: pathlib.Path, *, curve=2, endpoint=3, manifest=False, delivered=0):
    out = tmp_path / "native-out"
    (out / "cells" / "idaac-s101").mkdir(parents=True)
    (out / "records.jsonl").write_text(
        "".join(json.dumps({"phase": "eval", "frame": 1, "baseline": "idaac"}) + "\n"
                for _ in range(2)))
    (out / "cells" / "idaac-s101" / "offline_eval_curve.jsonl").write_text(
        "".join(json.dumps({"phase": "offline-eval", "frame": 100 * i, "baseline": "idaac",
                            "evaluator_scope": {"eval_policy_mode": "sample"}}) + "\n"
                for i in range(curve)))
    (out / "cells" / "idaac-s101" / "offline_eval_endpoint.jsonl").write_text(
        "".join(json.dumps({"phase": "offline-eval", "frame": 598016, "baseline": "idaac",
                            "evaluator_scope": {"eval_policy_mode": "sample"}}) + "\n"
                for _ in range(endpoint)))
    if manifest:
        (out / "run_manifest.json").write_text(json.dumps({"payload": "abc", "image": "def"}))
    if delivered:
        (out / "records_delivery.jsonl").write_text(
            "".join(json.dumps({"phase": "eval"}) + "\n" for _ in range(delivered)))
    return tmp_path


def test_it_assembles_every_source_the_runner_would_have(tmp_path):
    run = _cell(tmp_path)
    out = tmp_path / "bundle.jsonl"
    code, text = _run(run, out)
    assert code == 0, text
    rows = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
    assert len(rows) == 2 + 2 + 3, text


def test_every_row_is_marked_and_cannot_pass_as_delivered(tmp_path):
    run = _cell(tmp_path)
    out = tmp_path / "bundle.jsonl"
    code, text = _run(run, out)
    assert code == 0, text
    rows = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
    assert all("_assembled_after_reaping" in r for r in rows)
    assert all(r["_assembled_after_reaping"]["source"] for r in rows)
    assert "must never be filed as though the runner produced it" in text


def test_it_refuses_when_the_runner_already_delivered(tmp_path):
    run = _cell(tmp_path, delivered=16)
    out = tmp_path / "bundle.jsonl"
    code, text = _run(run, out)
    assert code == 1, text
    assert "REFUSING" in text
    assert not out.exists(), "a refusal must not write a second answer beside the first"


def test_missing_provenance_is_marked_not_invented(tmp_path):
    run = _cell(tmp_path, manifest=False)
    out = tmp_path / "bundle.jsonl"
    code, text = _run(run, out)
    assert code == 0, text
    rows = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
    offline = [r for r in rows if r["phase"] == "offline-eval"]
    assert offline and all("_run_provenance_missing" in r for r in offline)
    assert all("_run_provenance" not in r for r in offline), "provenance must not be invented"
    assert "NO run_manifest.json" in text


def test_present_provenance_is_attached_to_offline_rows_only(tmp_path):
    run = _cell(tmp_path, manifest=True)
    out = tmp_path / "bundle.jsonl"
    code, text = _run(run, out)
    assert code == 0, text
    rows = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
    offline = [r for r in rows if r["phase"] == "offline-eval"]
    other = [r for r in rows if r["phase"] != "offline-eval"]
    assert all(r.get("_run_provenance") == {"payload": "abc", "image": "def"} for r in offline)
    assert all("_run_provenance" not in r for r in other)


def test_an_empty_run_refuses_rather_than_writing_nothing_quietly(tmp_path):
    (tmp_path / "native-out").mkdir()
    code, text = _run(tmp_path, tmp_path / "bundle.jsonl")
    assert code == 2, text
    assert "NOT the same as" in text


def test_the_coverage_table_shows_a_partial_pass(tmp_path):
    """A reaped second policy-mode pass must be visible, not inferred from a row count."""
    run = _cell(tmp_path, endpoint=3)
    out = tmp_path / "native-out" / "cells" / "idaac-s101" / "offline_eval_endpoint.jsonl"
    out.write_text(out.read_text() + json.dumps(
        {"phase": "offline-eval", "frame": 598016, "baseline": "idaac",
         "evaluator_scope": {"eval_policy_mode": "mode"}}) + "\n")
    code, text = _run(run, tmp_path / "bundle.jsonl")
    assert code == 0, text
    assert "'sample'" in text and "'mode'" in text, text
