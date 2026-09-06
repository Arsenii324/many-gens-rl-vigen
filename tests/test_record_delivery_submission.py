"""Submission-time record-delivery admission tests."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JOB = ROOT / "datasphere/native/job.sh"
IMAGE = json.loads((ROOT / "datasphere/native/source-lock.json").read_text())["container_image"]


def _config(
    tmp_path: Path,
    *,
    kind: str,
    records: bool,
    tier: str = "gt4.1",
) -> Path:
    if kind == "eval":
        assignments = [
            "timeout --foreground 60s env",
            "NATIVE_V100_RESERVATION_MINUTES=1",
            "OFFLINE_EVAL_SNAPSHOT=/tmp/snapshot",
        ]
    elif kind == "production":
        assignments = [
            "NATIVE_HOST_PROFILE=datasphere",
            "NATIVE_PRODUCTION=1",
            "FRAMES=600000",
        ]
    elif kind == "preflight":
        assignments = ["PREFLIGHT_ONLY=1"]
    else:
        assignments = ["CELLS=drqv2:1", "FRAMES=10000"]
    if records:
        source = tmp_path / "records-source.jsonl"
        source.write_text("placeholder\n")
        assignments.append("RECORDS_OUT=${RECORDS}")
        input_block = f"inputs:\n  - {source}: RECORDS\n"
        output_block = "outputs:\n  - records.jsonl: RECORDS\n"
    else:
        input_block = ""
        output_block = "outputs:\n  - result.tgz: RESULT\n"
    assignments.append("echo submit-placeholder")
    config = tmp_path / f"{kind}-{'with' if records else 'without'}-records.yaml"
    config.write_text(
        f"name: record-delivery-{kind}\n"
        "cmd: >-\n"
        + "  " + " ".join(assignments) + "\n"
        + input_block
        + output_block
        + "env:\n"
        + f"  docker:\n    image: {IMAGE}\n"
        + f"cloud-instance-type: {tier}\n"
    )
    return config


def _fake_datasphere(tmp_path: Path) -> tuple[Path, Path]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    invoked = tmp_path / "datasphere-invoked"
    cli = fake_bin / "datasphere"
    cli.write_text(
        "#!/bin/sh\n"
        "touch \"$FAKE_DATASPHERE_INVOKED\"\n"
        "out=''\n"
        "while [ $# -gt 0 ]; do\n"
        "  if [ \"$1\" = '-o' ]; then out=$2; shift 2; else shift; fi\n"
        "done\n"
        "printf '%s\\n' bt1abcdefghijklmnopq > \"$out\"\n"
    )
    cli.chmod(0o755)
    return fake_bin, invoked


def _submit(tmp_path: Path, config: Path) -> subprocess.CompletedProcess[str]:
    fake_bin, invoked = _fake_datasphere(tmp_path)
    return subprocess.run(
        ["bash", str(JOB), "submit", str(config)],
        cwd=ROOT,
        env={
            **os.environ,
            "PATH": f"{fake_bin}:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin",
            "FAKE_DATASPHERE_INVOKED": str(invoked),
            "NATIVE_EVIDENCE_LOG": str(tmp_path / "actions.log"),
            "NATIVE_V100_BUDGET_STATE": str(tmp_path / "v100-budget.json"),
        },
        text=True,
        capture_output=True,
    )


def test_eval_only_without_records_is_rejected_before_cloud_or_v100_reservation(tmp_path):
    result = _submit(tmp_path, _config(tmp_path, kind="eval", records=False, tier="g1.1"))

    assert result.returncode != 0
    assert "RECORDS_OUT" in result.stderr
    assert not (tmp_path / "datasphere-invoked").exists()
    assert not (tmp_path / "v100-budget.json").exists()


def test_production_without_records_is_rejected_before_cloud(tmp_path):
    result = _submit(tmp_path, _config(tmp_path, kind="production", records=False))

    assert result.returncode != 0
    assert "RECORDS_OUT" in result.stderr
    assert not (tmp_path / "datasphere-invoked").exists()


def test_valid_eval_only_records_binding_reaches_cloud(tmp_path):
    result = _submit(tmp_path, _config(tmp_path, kind="eval", records=True, tier="g1.1"))

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "datasphere-invoked").exists()


def test_valid_production_records_binding_reaches_cloud(tmp_path):
    result = _submit(tmp_path, _config(tmp_path, kind="production", records=True))

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "datasphere-invoked").exists()


def test_preflight_without_records_remains_admissible(tmp_path):
    result = _submit(tmp_path, _config(tmp_path, kind="preflight", records=False))

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "datasphere-invoked").exists()


def test_exploratory_without_records_remains_admissible(tmp_path):
    result = _submit(tmp_path, _config(tmp_path, kind="exploratory", records=False))

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "datasphere-invoked").exists()


def test_required_delivery_rejects_a_records_binding_without_its_output(tmp_path):
    config = _config(tmp_path, kind="eval", records=True, tier="gt4.1")
    config.write_text(config.read_text().replace("outputs:\n  - records.jsonl: RECORDS\n", ""))

    result = _submit(tmp_path, config)

    assert result.returncode != 0
    assert "corresponding" in result.stderr
    assert not (tmp_path / "datasphere-invoked").exists()


def test_required_delivery_rejects_ambiguous_records_bindings(tmp_path):
    config = _config(tmp_path, kind="production", records=True)
    config.write_text(config.read_text().replace(
        "RECORDS_OUT=${RECORDS} echo submit-placeholder",
        "RECORDS_OUT=${RECORDS} RECORDS_OUT=records.jsonl echo submit-placeholder",
    ))

    result = _submit(tmp_path, config)

    assert result.returncode != 0
    assert "ambiguous" in result.stderr
    assert not (tmp_path / "datasphere-invoked").exists()


def test_required_delivery_rejects_an_unparseable_forwarded_command(tmp_path):
    config = _config(tmp_path, kind="production", records=False)
    config.write_text(config.read_text().replace("echo submit-placeholder", 'echo "unterminated'))

    result = _submit(tmp_path, config)

    assert result.returncode != 0
    assert "cannot parse" in result.stderr
    assert not (tmp_path / "datasphere-invoked").exists()
