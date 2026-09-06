"""Behavioral tests for native record finalization and its archive boundary."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "datasphere/native/contract.py"
RUNNER = ROOT / "datasphere/native/run_probe.sh"
PYTHON = "/Users/a2mogus/build-projs/barannikov-work/.venv/bin/python"


def _manifest(kind: str) -> dict:
    return {
        "finalization_schema": 1,
        "execution_kind": kind,
        "record_delivery": "pending",
        "record_artifacts": {"inputs": [], "output": None},
        "final_evaluation_marker": "NATIVE_FINAL_EVALUATION_COMPLETED frame=100",
        "failure_marker": None,
    }


def _run_finalizer(
    tmp_path: Path,
    kind: str,
    content: str | None,
    *,
    status: int = 0,
    internal: dict[str, str] | None = None,
):
    manifest = tmp_path / "run_manifest.json"
    manifest.write_text(json.dumps(_manifest(kind)) + "\n")
    for relative, source in (internal or {}).items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
    records = tmp_path / "records.out"
    if content is not None:
        records.write_text(content)
    command = [PYTHON, str(CONTRACT), "finalize-records", "--manifest", str(manifest),
               "--execution-status", str(status)]
    if content is not None:
        command += ["--records-out", str(records)]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return result, json.loads(manifest.read_text()), records


def test_production_empty_records_is_failed_and_carries_auditable_metadata(tmp_path):
    result, manifest, records = _run_finalizer(tmp_path, "training_production", "")

    assert result.returncode != 0
    assert manifest["record_delivery"] == "failed"
    assert manifest["final_evaluation_marker"] is None
    assert manifest["failure_marker"].startswith("NATIVE_RECORD_DELIVERY_FAILED")
    output = manifest["record_artifacts"]["output"]
    assert output["path"] == records.name
    assert output["row_count"] == output["canonical_row_count"] == 0
    assert output["sha256"] == hashlib.sha256(b"").hexdigest()


def test_eval_only_offline_row_succeeds_without_training_records_jsonl(tmp_path):
    result, manifest, _ = _run_finalizer(
        tmp_path, "eval_only_validation", '{"frame": 100, "return": 3.5}\n',
        internal={"offline_eval_cuda.jsonl": '{"frame": 100, "return": 3.5}\n'},
    )

    assert result.returncode == 0
    assert manifest["record_delivery"] == "complete"
    assert manifest["failure_marker"] is None
    assert manifest["record_artifacts"]["output"]["row_count"] == 1


@pytest.mark.parametrize(
    ("kind", "source_path"),
    [("training_production", "records.jsonl"),
     ("eval_only_validation", "offline_eval_cuda.jsonl")],
)
def test_required_delivery_rejects_a_partial_bundle_even_when_remaining_row_is_valid(
    tmp_path, kind, source_path,
):
    result, manifest, _ = _run_finalizer(
        tmp_path,
        kind,
        '{"frame": 100, "return": 3.5}\n',
        internal={source_path: '{"frame": 100, "return": 3.5}\n{"frame": 200, "return": 4.5}\n'},
    )

    assert result.returncode != 0
    assert manifest["record_delivery"] == "failed"
    assert "record_content_mismatch" in manifest["record_delivery_error"]
    assert "expected_rows=2" in manifest["record_delivery_error"]
    assert "delivered_rows=1" in manifest["record_delivery_error"]


def test_exploratory_partial_bundle_is_failed_not_empty_tolerated(tmp_path):
    result, manifest, _ = _run_finalizer(
        tmp_path,
        "exploratory",
        '{"frame": 100, "return": 3.5}\n',
        internal={"records.jsonl": '{"frame": 100, "return": 3.5}\n{"frame": 200, "return": 4.5}\n'},
    )

    assert result.returncode != 0
    assert manifest["record_delivery"] == "failed"
    assert "record_content_mismatch" in manifest["record_delivery_error"]


def test_offline_provenance_enrichment_is_ignored_only_for_content_comparison(tmp_path):
    result, manifest, _ = _run_finalizer(
        tmp_path,
        "eval_only_validation",
        '{"_run_provenance": {"execution_kind": "eval_only_validation"}, '
        '"frame": 100, "return": 3.5}\n',
        internal={"offline_eval_cuda.jsonl": '{"frame": 100, "return": 3.5}\n'},
    )

    assert result.returncode == 0
    assert manifest["record_delivery"] == "complete"
    assert manifest["record_artifacts"]["inputs"][0]["canonical_sha256"] == \
        manifest["record_artifacts"]["output"]["canonical_sha256"]


def test_completed_mixed_delivery_stamps_every_row_with_final_provenance(tmp_path):
    result, manifest, records = _run_finalizer(
        tmp_path,
        "training_production",
        '{"frame": 100, "return": 3.5}\n'
        '{"_run_provenance": {"execution_kind": "training_production"}, '
        '"frame": 200, "return": 4.5}\n',
        internal={
            "records.jsonl": '{"frame": 100, "return": 3.5}\n',
            "offline_eval_cuda.jsonl": '{"frame": 200, "return": 4.5}\n',
        },
    )

    assert result.returncode == 0
    output_rows = [json.loads(line) for line in records.read_text().splitlines()]
    assert len(output_rows) == 2
    for row in output_rows:
        assert row["_delivery_provenance"] == {
            "finalization_schema": 1,
            "execution_kind": "training_production",
            "record_delivery": "complete",
            "source_row_count": 2,
            "source_canonical_sha256": manifest["record_artifacts"]["expected"][
                "canonical_sha256"
            ],
        }
    assert manifest["record_artifacts"]["output"]["sha256"] == hashlib.sha256(
        records.read_bytes()
    ).hexdigest()


def test_delivery_provenance_cannot_hide_a_source_measurement_mismatch(tmp_path):
    fake = {
        "finalization_schema": 1,
        "execution_kind": "training_production",
        "record_delivery": "complete",
        "source_row_count": 1,
        "source_canonical_sha256": "anything",
    }
    result, manifest, _ = _run_finalizer(
        tmp_path,
        "training_production",
        json.dumps({"frame": 100, "return": 999.0, "_delivery_provenance": fake}) + "\n",
        internal={"records.jsonl": '{"frame": 100, "return": 3.5}\n'},
    )

    assert result.returncode != 0
    assert manifest["record_delivery"] == "failed"
    assert "record_content_mismatch" in manifest["record_delivery_error"]


def test_delivery_stamp_write_failure_is_a_failed_delivery(tmp_path, monkeypatch):
    from datasphere.native import contract

    manifest_path = tmp_path / "run_manifest.json"
    manifest_path.write_text(json.dumps(_manifest("training_production")) + "\n")
    source = tmp_path / "records.jsonl"
    source.write_text('{"frame": 100, "return": 3.5}\n')
    records = tmp_path / "records.out"
    records.write_text(source.read_text())

    def fail_stamp(*_args, **_kwargs):
        raise OSError("simulated delivery output write failure")

    monkeypatch.setattr(contract, "_write_delivery_records", fail_stamp)
    accepted = contract.finalize_records(manifest_path, records)
    manifest = json.loads(manifest_path.read_text())

    assert not accepted
    assert manifest["record_delivery"] == "failed"
    assert "delivery_stamp_failed" in manifest["record_delivery_error"]


def test_preflight_without_records_is_not_applicable(tmp_path):
    result, manifest, _ = _run_finalizer(tmp_path, "preflight", None)

    assert result.returncode == 0
    assert manifest["record_delivery"] == "not_applicable"


def test_exploratory_empty_records_is_explicitly_tolerated_and_nonfinal(tmp_path):
    result, manifest, _ = _run_finalizer(tmp_path, "exploratory", "")

    assert result.returncode == 0
    assert manifest["record_delivery"] == "empty_tolerated"
    assert manifest["final_evaluation_marker"] is not None


def test_production_without_records_destination_fails_closed(tmp_path):
    result, manifest, _ = _run_finalizer(tmp_path, "training_production", None)

    assert result.returncode != 0
    assert manifest["record_delivery"] == "failed"
    assert "missing_records_out" in manifest["record_delivery_error"]


def test_invalid_json_row_is_a_delivery_failure(tmp_path):
    result, manifest, _ = _run_finalizer(tmp_path, "training_production", '{"ok": 1}\nnot-json\n')

    assert result.returncode != 0
    assert manifest["record_delivery"] == "failed"
    assert "invalid_json" in manifest["record_delivery_error"]


def _extract_function(name: str) -> str:
    source = RUNNER.read_text()
    start = source.index(f"{name}() {{")
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise AssertionError(f"missing {name}")


def test_runner_archives_a_production_delivery_failure_before_returning_nonzero(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "run_manifest.json").write_text(json.dumps(_manifest("training_production")) + "\n")
    (out / "records.jsonl").write_text(
        '{"frame": 100, "return": 3.5}\n{"frame": 200, "return": 4.5}\n'
    )
    records = tmp_path / "records.out"
    records.write_text("")
    archive = tmp_path / "result.tgz"
    script = tmp_path / "harness.sh"
    script.write_text(
        "set -euo pipefail\n"
        + _extract_function("finalize_record_delivery")
        + "\n"
        + f'finalization_status=0; finalize_record_delivery "{out}" "{records}" 0 || '
          'finalization_status=$?\n'
        + f'tar -czf "{archive}" -C "{out}" .\n'
        + 'exit "$finalization_status"\n'
    )
    result = subprocess.run(["bash", str(script)], cwd=ROOT, text=True, capture_output=True)

    assert result.returncode != 0
    assert archive.is_file()
    with tarfile.open(archive) as handle:
        manifest = json.loads(handle.extractfile("./run_manifest.json").read())
    assert manifest["record_delivery"] == "failed"


def test_collector_write_failure_reaches_archive_boundary(tmp_path):
    source = RUNNER.read_text()
    start = source.index('if [[ -n "${RECORDS_OUT:-}" ]]')
    end = source.index("\n# Finalization is part of the evidence boundary.", start)
    collection = source[start:end]
    out = tmp_path / "out"
    out.mkdir()
    (out / "records.jsonl").write_text('{"frame": 100}\n')
    destination = tmp_path / "records-destination"
    destination.mkdir()
    archive = tmp_path / "result.tgz"
    script = tmp_path / "collector-harness.sh"
    script.write_text(
        "set -euo pipefail\n"
        f'out="{out}"; RECORDS_OUT="{destination}"; record_collection_status=0\n'
        + collection
        + '\n[[ "$record_collection_status" -eq 1 ]]\n'
        + f'tar -czf "{archive}" -C "{out}" .\n'
    )

    result = subprocess.run(["bash", str(script)], cwd=ROOT, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr
    assert archive.is_file()
    assert "NATIVE_RECORDS_OUT_UNWRITABLE" in result.stderr


def test_collector_rejects_source_alias_before_truncation_and_archives_failure(tmp_path):
    source = RUNNER.read_text()
    start = source.index('if [[ -n "${RECORDS_OUT:-}" ]]')
    end = source.index("\n# Finalization is part of the evidence boundary.", start)
    collection = source[start:end]
    out = tmp_path / "out"
    out.mkdir()
    source_records = out / "records.jsonl"
    original = b'{"frame": 100, "return": 3.5}\n'
    source_records.write_bytes(original)
    (out / "run_manifest.json").write_text(json.dumps(_manifest("training_production")) + "\n")
    aliased_destination = tmp_path / "records-alias.jsonl"
    aliased_destination.symlink_to(source_records)
    archive = tmp_path / "result.tgz"
    script = tmp_path / "alias-harness.sh"
    script.write_text(
        "set -euo pipefail\n"
        f'out="{out}"; RECORDS_OUT="{aliased_destination}"; record_collection_status=0\n'
        + collection
        + '\n[[ "$record_collection_status" -eq 1 ]]\n'
        + _extract_function("finalize_record_delivery")
        + "\n"
        + f'finalization_status=0; finalize_record_delivery "{out}" "{aliased_destination}" 0 '
          '"$record_collection_status" || finalization_status=$?\n'
        + f'tar -czf "{archive}" -C "{out}" .\n'
        + 'exit "$finalization_status"\n'
    )

    result = subprocess.run(["bash", str(script)], cwd=ROOT, text=True, capture_output=True)

    assert result.returncode != 0
    assert source_records.read_bytes() == original
    assert "NATIVE_RECORDS_OUT_SOURCE_ALIAS" in result.stderr
    assert archive.is_file()
    with tarfile.open(archive) as handle:
        manifest = json.loads(handle.extractfile("./run_manifest.json").read())
        archived_source = handle.extractfile("./records.jsonl").read()
    assert manifest["record_delivery"] == "failed"
    assert archived_source == original


def test_collector_keeps_separate_destination_behavior(tmp_path):
    source = RUNNER.read_text()
    start = source.index('if [[ -n "${RECORDS_OUT:-}" ]]')
    end = source.index("\n# Finalization is part of the evidence boundary.", start)
    collection = source[start:end]
    out = tmp_path / "out"
    out.mkdir()
    source_records = out / "records.jsonl"
    original = b'{"frame": 100, "return": 3.5}\n'
    source_records.write_bytes(original)
    destination = tmp_path / "records.out"
    script = tmp_path / "separate-destination-harness.sh"
    script.write_text(
        "set -euo pipefail\n"
        f'out="{out}"; RECORDS_OUT="{destination}"; record_collection_status=0\n'
        + collection
        + '\n[[ "$record_collection_status" -eq 0 ]]\n'
    )

    result = subprocess.run(["bash", str(script)], cwd=ROOT, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr
    assert source_records.read_bytes() == original
    assert destination.read_bytes() == original


def test_normalized_rows_carry_execution_kind_from_the_pre_normalization_manifest(tmp_path):
    from datasphere.native.normalize_curves import normalize

    manifest = _manifest("training_production")
    manifest.update({"payload_sha256": "payload", "asset_sha256": "asset"})
    (tmp_path / "run_manifest.json").write_text(json.dumps(manifest) + "\n")
    cell = tmp_path / "cells" / "rlvigen-s1"
    cell.mkdir(parents=True)
    (cell / "retained.json").write_text(json.dumps({"family": "rlvigen"}))
    (cell / "eval.csv").write_text(
        "frame,episode_reward,success_rate\n100,2.5,0.5\n"
    )

    rows = normalize(tmp_path)

    assert rows[0]["native"]["run_provenance"]["execution_kind"] == "training_production"


def test_summary_refuses_failed_production_delivery_by_default_but_allows_diagnostic_view(tmp_path):
    manifest = _manifest("training_production")
    manifest["record_delivery"] = "failed"
    (tmp_path / "run_manifest.json").write_text(json.dumps(manifest) + "\n")

    command = [PYTHON, str(ROOT / "datasphere/native/summarize_result.py"),
               "--directory", str(tmp_path)]
    refused = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    diagnostic = subprocess.run(command + ["--diagnostic"], cwd=ROOT, text=True, capture_output=True)

    assert refused.returncode != 0
    assert "record delivery" in refused.stderr
    assert diagnostic.returncode == 0


def test_summary_refuses_old_eval_only_artifact_without_explicit_diagnostic(tmp_path):
    manifest = {"execution_kind": "eval_only_validation"}
    (tmp_path / "run_manifest.json").write_text(json.dumps(manifest) + "\n")

    command = [PYTHON, str(ROOT / "datasphere/native/summarize_result.py"),
               "--directory", str(tmp_path)]
    refused = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    diagnostic = subprocess.run(command + ["--diagnostic"], cwd=ROOT, text=True, capture_output=True)

    assert refused.returncode != 0
    assert diagnostic.returncode == 0
