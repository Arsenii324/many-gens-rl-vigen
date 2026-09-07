from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_external_review_artifact.py"


def _run(source: Path, output: Path, mode: str = "source-fidelity", transcript: Path | None = None):
    command = [
        sys.executable,
        str(BUILDER),
        "--source",
        str(source),
        "--output",
        str(output),
        "--mode",
        mode,
    ]
    if transcript is not None:
        command += ["--test-transcript", str(transcript)]
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True)


def _tree(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    for rel, text in {
        "docs/guide.md": "review guide\n",
        "notes/EXTERNAL-REVIEW-ARTIFACT-BLUEPRINT.md": "blueprint\n",
        "notes/PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md": "reconciliation\n",
        "scripts/check.py": "print('ok')\n",
        "tests/check_test.py": "def test_ok(): pass\n",
        "setup/README.md": "setup\n",
        "datasphere/native/config.yaml": "mode: test\n",
        "runnable/agent/model.py": "class Agent: pass\n",
        "baselines/ibac_sni/README.md": "IBAC source record\n",
        "rlgen/protocol.py": "PROTOCOL = 1\n",
        "third_party/README.md": "third-party closure\n",
        "configs/main.yaml": "profile: main\n",
        "compute/runbook.md": "remote run notes\n",
        "mutants/example.txt": "mutation fixture\n",
        "research/question.md": "research note\n",
        "tools/check.py": "print('tool')\n",
        "results/records/old.jsonl": '{"status":"historical"}\n',
        "RL-ViGen-upstream/cfgs/config.yaml": "image_size: 84\n",
        "ext/baseline_resources/paper.pdf": "not a real pdf\n",
        "ext/drqv2/drqv2.py": "class DrQV2: pass\n",
        "ext/baselines/baselines/common.py": "# required IDAAC closure\n",
        "ext/ctrl_rl/supp_mat_revision_2/code.zip": "official source bundle\n",
        "README.md": "root\n",
    }.items():
        path = source / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    (source / "payload.tgz").write_bytes(b"payload")
    (source / "checkpoints" / "model.pt").parent.mkdir(parents=True)
    (source / "checkpoints" / "model.pt").write_bytes(b"checkpoint")
    (source / "media.png").write_bytes(b"image")
    (source / "__pycache__").mkdir()
    (source / "__pycache__" / "x.pyc").write_bytes(b"cache")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    try:
        (source / "runnable" / "outside-link").symlink_to(outside)
        (source / "datasets").symlink_to(tmp_path / "missing-datasets", target_is_directory=True)
    except OSError as exc:  # pragma: no cover - only relevant on a no-symlink filesystem
        pytest.skip(f"symlinks unavailable: {exc}")
    return source


def _manifest(output: Path) -> dict:
    return json.loads((output / "artifact-manifest.json").read_text(encoding="utf-8"))


def test_source_fidelity_builds_hashed_directory_and_declares_exclusions(tmp_path: Path):
    source = _tree(tmp_path)
    output = tmp_path / "artifact"

    result = _run(source, output)

    assert result.returncode == 0, result.stderr
    manifest = _manifest(output)
    included = {row["source_relative_path"]: row for row in manifest["included_files"]}
    assert "scripts/check.py" in included
    for rel in (
        "baselines/ibac_sni/README.md",
        "rlgen/protocol.py",
        "third_party/README.md",
        "configs/main.yaml",
        "compute/runbook.md",
        "mutants/example.txt",
        "research/question.md",
        "tools/check.py",
    ):
        assert rel in included, rel
    assert "ext/baselines/baselines/common.py" in included
    assert "ext/ctrl_rl/supp_mat_revision_2/code.zip" in included
    assert included["scripts/check.py"]["sha256"] == hashlib.sha256(
        b"print('ok')\n"
    ).hexdigest()
    assert (output / "scripts/check.py").read_text(encoding="utf-8") == "print('ok')\n"
    excluded_paths = {row.get("source_relative_path") for row in manifest["exclusions"]}
    assert "payload.tgz" in excluded_paths
    assert "checkpoints/model.pt" in excluded_paths
    assert "media.png" in excluded_paths
    assert "__pycache__/x.pyc" in excluded_paths
    assert "results/records/old.jsonl" in excluded_paths
    symlink_paths = {row["source_relative_path"] for row in manifest["symlinks"]}
    assert symlink_paths == {"runnable/outside-link", "datasets"}
    outside_link = next(row for row in manifest["symlinks"]
                        if row["source_relative_path"] == "runnable/outside-link")
    assert outside_link["target"] == "<redacted>"
    assert outside_link["target_redacted"] is True
    assert len(outside_link["target_fingerprint"]) == 64
    assert not (output / "runnable/outside-link").exists()
    assert not (output / "outside.txt").exists()
    assert manifest["selection_rules"]["never_follow_symlinks"] is True
    assert manifest["excluded"] == manifest["exclusions"]
    assert all(
        row["present_in_project"] is True and row["count"] == 1 and row["pattern"]
        for row in manifest["exclusions"]
    )
    assert len(manifest["source"]["source_tree_digest"]) == 64
    assert len(manifest["source"]["builder_sha256"]) == 64
    assert any(
        row["source_relative_path"] == "ext/baseline_resources/11_ibac_sni/paper_1901.10902.pdf"
        for row in manifest["selection_rules"]["known_unrelated_sources"]
    )
    excluded_jsonl = [
        json.loads(line)
        for line in (output / "excluded-files.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert excluded_jsonl == manifest["exclusions"]
    readme = (output / "README-ARTIFACT.md").read_text(encoding="utf-8")
    assert "SOURCE-FIDELITY REVIEW NOW" in readme
    assert "EXTERNAL-REVIEW-ARTIFACT-BLUEPRINT.md" in readme
    assert "PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md" in readme


def test_known_unrelated_ibac_pdf_is_excluded_but_correct_paper_is_included(tmp_path: Path):
    source = _tree(tmp_path)
    wrong = source / "ext/baseline_resources/11_ibac_sni/paper_1901.10902.pdf"
    wrong.parent.mkdir(parents=True, exist_ok=True)
    wrong.write_bytes(b"INFOBOT: Transfer and Exploration via the Information Bottleneck\n")
    correct = source / "ext/papers-sorted/IBAC-SNI/IBAC-SNI_paper_neurips2019.pdf"
    correct.parent.mkdir(parents=True, exist_ok=True)
    correct.write_bytes(b"Generalization in Reinforcement Learning with Selective Noise Injection and Information Bottleneck\n")
    output = tmp_path / "artifact"

    result = _run(source, output)

    assert result.returncode == 0, result.stderr
    manifest = _manifest(output)
    included_paths = {row["source_relative_path"] for row in manifest["included_files"]}
    assert "ext/papers-sorted/IBAC-SNI/IBAC-SNI_paper_neurips2019.pdf" in included_paths
    assert "ext/baseline_resources/11_ibac_sni/paper_1901.10902.pdf" not in included_paths
    assert not (output / "ext/baseline_resources/11_ibac_sni/paper_1901.10902.pdf").exists()
    exclusion = next(
        row for row in manifest["exclusions"]
        if row.get("source_relative_path") == "ext/baseline_resources/11_ibac_sni/paper_1901.10902.pdf"
    )
    assert exclusion["rule"] == "known-unrelated-source"
    assert exclusion["reason"] == (
        "unrelated InfoBot paper; arXiv:1901.10902 is not IBAC-SNI "
        "(arXiv:1910.12911)"
    )


def test_existing_output_refusal_leaves_sentinel_unchanged(tmp_path: Path):
    source = _tree(tmp_path)
    output = tmp_path / "artifact"
    output.mkdir()
    sentinel = output / "sentinel.txt"
    sentinel.write_text("do not touch\n", encoding="utf-8")

    result = _run(source, output)

    assert result.returncode != 0
    assert "already exists" in result.stderr.lower()
    assert sentinel.read_text(encoding="utf-8") == "do not touch\n"
    assert sorted(p.name for p in output.iterdir()) == ["sentinel.txt"]


def test_output_nested_within_source_is_refused_without_staging(tmp_path: Path):
    source = _tree(tmp_path)
    output = source / "artifact"

    result = _run(source, output)

    assert result.returncode != 0
    assert "nested" in result.stderr.lower()
    assert not output.exists()
    assert not list(source.glob(".artifact.staging-*"))


def test_secret_filename_fails_closed_without_printing_contents(tmp_path: Path):
    source = _tree(tmp_path)
    secret = source / "config" / "wandb_key.txt"
    secret.parent.mkdir()
    secret.write_text("THIS-MUST-NOT-APPEAR-IN-OUTPUT\n", encoding="utf-8")
    output = tmp_path / "artifact"

    result = _run(source, output)

    assert result.returncode != 0
    assert "secret" in result.stderr.lower() or "credential" in result.stderr.lower()
    assert "THIS-MUST-NOT-APPEAR-IN-OUTPUT" not in result.stdout
    assert "THIS-MUST-NOT-APPEAR-IN-OUTPUT" not in result.stderr
    assert not output.exists()


def test_transcript_under_secret_directory_is_refused(tmp_path: Path):
    source = _tree(tmp_path)
    transcript_dir = tmp_path / "secrets"
    transcript_dir.mkdir()
    transcript = transcript_dir / "pytest.txt"
    transcript.write_text("23 passed\n", encoding="utf-8")
    output = tmp_path / "artifact"

    result = _run(source, output, transcript=transcript)

    assert result.returncode != 0
    assert "credential" in result.stderr.lower() or "secret" in result.stderr.lower()
    assert not output.exists()


def test_private_mailbox_cannot_be_reintroduced_as_transcript(tmp_path: Path):
    source = _tree(tmp_path)
    transcript = source / "notes" / "ask-claude.md"
    transcript.write_text("private coordination\n", encoding="utf-8")
    output = tmp_path / "artifact"

    result = _run(source, output, transcript=transcript)

    assert result.returncode != 0
    assert "private" in result.stderr.lower()
    assert not output.exists()


def _git_clean_source(tmp_path: Path) -> Path:
    source = _tree(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=source, check=True)
    subprocess.run(["git", "config", "user.name", "Artifact Test"], cwd=source, check=True)
    subprocess.run(["git", "add", "."], cwd=source, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=source, check=True)
    return source


def test_final_production_requires_clean_source_and_existing_transcript(tmp_path: Path):
    source = _git_clean_source(tmp_path)
    output = tmp_path / "artifact"
    transcript = tmp_path / "pytest-transcript.txt"
    transcript.write_text("23 passed\n", encoding="utf-8")

    missing_transcript = _run(source, output, mode="final-production")
    assert missing_transcript.returncode != 0
    assert "transcript" in missing_transcript.stderr.lower()
    assert not output.exists()

    success = _run(source, output, mode="final-production", transcript=transcript)
    assert success.returncode == 0, success.stderr
    manifest = _manifest(output)
    assert manifest["mode"] == "final-production"
    assert manifest["test_transcript"]["supplied"] is True
    transcript_copy = output / manifest["test_transcript"]["artifact_relative_path"]
    assert transcript_copy.read_text(encoding="utf-8") == "23 passed\n"


def test_final_production_refuses_dirty_source_before_publishing(tmp_path: Path):
    source = _git_clean_source(tmp_path)
    (source / "docs" / "dirty.md").write_text("dirty\n", encoding="utf-8")
    output = tmp_path / "artifact"
    transcript = tmp_path / "pytest-transcript.txt"
    transcript.write_text("23 passed\n", encoding="utf-8")

    result = _run(source, output, mode="final-production", transcript=transcript)

    assert result.returncode != 0
    assert "dirty" in result.stderr.lower()
    assert not output.exists()


def test_manifest_paths_are_relative_and_all_copied_hashes_verify(tmp_path: Path):
    source = _tree(tmp_path)
    output = tmp_path / "artifact"

    result = _run(source, output)

    assert result.returncode == 0, result.stderr
    manifest = _manifest(output)
    for row in manifest["included_files"]:
        rel = Path(row["artifact_relative_path"])
        assert not rel.is_absolute()
        assert ".." not in rel.parts
        copied = output / rel
        assert hashlib.sha256(copied.read_bytes()).hexdigest() == row["sha256"]


def test_included_file_mode_is_recorded_and_preserved(tmp_path: Path):
    source = _tree(tmp_path)
    script = source / "scripts" / "check.py"
    script.chmod(0o751)
    output = tmp_path / "artifact"

    result = _run(source, output)

    assert result.returncode == 0, result.stderr
    row = next(row for row in _manifest(output)["included_files"]
               if row["source_relative_path"] == "scripts/check.py")
    assert row["mode"] == 0o751
    assert (output / "scripts/check.py").stat().st_mode & 0o7777 == 0o751
