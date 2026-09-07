"""Fail-closed evaluator identity binding at the payload and post-patch boundary."""

from __future__ import annotations

import io
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "datasphere/native/contract.py"
RUNNER = ROOT / "datasphere/native/run_probe.sh"


def _runner_contract() -> int:
    match = re.search(r"RUNNER_CONTRACT = (\d+)", TOOL.read_text())
    assert match
    return int(match.group(1))


@pytest.fixture(scope="module")
def idaac_payload(tmp_path_factory):
    output = tmp_path_factory.mktemp("identity-payload") / "idaac.tgz"
    result = subprocess.run(
        [sys.executable, str(TOOL), "build-payload", "--source", str(ROOT),
         "--output", str(output), "--families", "idaac"],
        text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    return output


def _manifest(archive: Path) -> dict:
    with tarfile.open(archive, "r:gz") as handle:
        return json.loads(handle.extractfile("payload_manifest.json").read())


def _rewrite(archive: Path, output: Path, mutate):
    with tarfile.open(archive, "r:gz") as source, tarfile.open(output, "w:gz") as target:
        for member in source.getmembers():
            body = source.extractfile(member).read() if member.isfile() else None
            if body is not None:
                body = mutate(member.name, body)
                member.size = len(body)
                target.addfile(member, io.BytesIO(body))
            else:
                target.addfile(member)


def _temporary_identity_root(tmp_path, family="idaac"):
    """Copy only the helper's declared closure; never mutate the shared source tree."""
    from datasphere.native import evaluator_identity

    root = tmp_path / "identity-source"
    members = set(evaluator_identity.evaluator_runtime_members(ROOT, family))
    members.update(("datasphere/native/families.json", "datasphere/native/rlvigen-source.json"))
    for relative in members:
        source = ROOT / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return root


def test_payload_manifest_carries_exact_family_identity(idaac_payload):
    manifest = _manifest(idaac_payload)
    assert manifest["evaluator_identity_schema"] == 2
    binding = manifest["evaluator_bindings"]["idaac"]
    assert set(binding) >= {
        "code_revision", "config_revision", "revision", "runtime_members",
        "rlvigen_archive_sha256", "rlvigen_commit",
    }
    assert binding["runtime_members"]


def test_payload_member_byte_mutation_is_refused(idaac_payload, tmp_path):
    mutated = tmp_path / "mutated.tgz"
    _rewrite(idaac_payload, mutated, lambda name, body:
             body + b"\n# stale payload mutation\n" if name == "scripts/eval_grid.py" else body)

    result = subprocess.run(
        [sys.executable, str(TOOL), "verify-payload", "--archive", str(mutated),
         "--require-runner-contract", str(_runner_contract()), "--require-families", "idaac",
         "--require-evaluator-identity"],
        text=True, capture_output=True,
    )
    assert result.returncode != 0
    assert "hash" in result.stderr.lower()


def test_payload_without_requested_family_binding_is_refused(idaac_payload, tmp_path):
    mutated = tmp_path / "unbound.tgz"

    def remove_binding(name, body):
        if name != "payload_manifest.json":
            return body
        manifest = json.loads(body)
        manifest["evaluator_bindings"].pop("idaac")
        return json.dumps(manifest, sort_keys=True, indent=2).encode()

    _rewrite(idaac_payload, mutated, remove_binding)
    result = subprocess.run(
        [sys.executable, str(TOOL), "verify-payload", "--archive", str(mutated),
         "--require-families", "idaac", "--require-evaluator-identity"],
        text=True, capture_output=True,
    )
    assert result.returncode != 0
    assert "binding" in result.stderr.lower()


def test_current_contract_does_not_rescue_stale_evaluator_binding(idaac_payload, tmp_path):
    mutated = tmp_path / "stale-current-contract.tgz"

    def stale_binding(name, body):
        if name != "payload_manifest.json":
            return body
        manifest = json.loads(body)
        manifest["evaluator_bindings"]["idaac"]["revision"] = "0" * 64
        return json.dumps(manifest, sort_keys=True, indent=2).encode()

    _rewrite(idaac_payload, mutated, stale_binding)
    result = subprocess.run(
        [sys.executable, str(TOOL), "verify-evaluator-binding", "--archive", str(mutated),
         "--source", str(ROOT), "--families", "idaac"],
        text=True, capture_output=True,
    )
    assert result.returncode != 0
    assert "revision" in result.stderr.lower()


def test_evaluator_runtime_config_change_is_refused(idaac_payload, tmp_path):
    from datasphere.native import evaluator_identity

    manifest = _manifest(idaac_payload)
    source = _temporary_identity_root(tmp_path)
    target = source / "RL-ViGen-upstream/envs/robosuiteVGB/cfg/robo_config.yaml"
    target.write_text(target.read_text() + "\n# evaluator runtime config mutation\n")
    with pytest.raises(ValueError, match="runtime member|code_revision|revision"):
        evaluator_identity.verify_bindings(source, manifest, ("idaac",))


def test_pinned_archive_digest_mismatch_is_refused(idaac_payload, tmp_path):
    wrong_archive = tmp_path / "wrong-rlvigen.tgz"
    wrong_archive.write_bytes(b"not the pinned RL-ViGen archive")
    result = subprocess.run(
        [sys.executable, str(TOOL), "verify-evaluator-binding", "--archive", str(idaac_payload),
         "--source", str(ROOT), "--families", "idaac", "--rlvigen-archive", str(wrong_archive)],
        text=True, capture_output=True,
    )
    assert result.returncode != 0
    assert "archive" in result.stderr.lower()


def test_verifier_is_dependency_free(idaac_payload):
    result = subprocess.run(
        [sys.executable, "-S", str(TOOL), "verify-payload", "--archive", str(idaac_payload),
         "--require-families", "idaac", "--require-evaluator-identity"],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert "numpy" not in result.stderr.lower()


def test_training_only_patch_provenance_does_not_change_evaluator_identity(idaac_payload, tmp_path):
    mutated = tmp_path / "training-only-provenance.tgz"

    def change_broad_provenance(name, body):
        if name != "payload_manifest.json":
            return body
        manifest = json.loads(body)
        manifest.setdefault("provenance", {})["apply_patches_sha256"] = "f" * 64
        return json.dumps(manifest, sort_keys=True, indent=2).encode()

    _rewrite(idaac_payload, mutated, change_broad_provenance)
    result = subprocess.run(
        [sys.executable, str(TOOL), "verify-evaluator-binding", "--archive", str(mutated),
         "--source", str(ROOT), "--families", "idaac"],
        text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr


def test_postpatch_member_mutation_is_refused(idaac_payload, tmp_path):
    from datasphere.native import evaluator_identity

    manifest = _manifest(idaac_payload)
    source = _temporary_identity_root(tmp_path)
    target = source / "RL-ViGen-upstream/envs/robosuiteVGB/robosuitevgb/__init__.py"
    target.write_bytes(target.read_bytes() + b"\n# stale post-patch clone\n")
    with pytest.raises(ValueError, match="runtime member|code_revision|revision"):
        evaluator_identity.verify_bindings(source, manifest, ("idaac",))


def test_eval_provenance_has_no_local_identity_definitions():
    path = ROOT / "scripts/eval_provenance.py"
    tree = ast.parse(path.read_text(), filename=str(path))
    names = {
        "CODE_MEMBERS", "CONFIG_MEMBERS", "REVISION_MEMBERS", "EVALUATOR_FAMILIES",
        "FAMILY_RUNTIME_MEMBERS", "evaluator_runtime_members", "evaluator_revision",
        "evaluator_code_revision", "evaluator_config_revision",
        "evaluator_family_code_revision", "evaluator_family_config_revision",
        "evaluator_family_revision",
    }
    local_defs = [node.name for node in ast.walk(tree)
                  if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
    local_assignments = []
    for node in ast.walk(tree):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        for target in targets:
            if isinstance(target, ast.Name) and target.id in names:
                local_assignments.append(target.id)
    assert not local_defs, f"legacy identity definitions remain: {local_defs}"
    assert not local_assignments, f"legacy identity declarations remain: {local_assignments}"


def test_eval_provenance_identity_api_is_canonical():
    from datasphere.native import evaluator_identity
    from scripts import eval_provenance

    for name in ("CODE_MEMBERS", "CONFIG_MEMBERS", "REVISION_MEMBERS", "EVALUATOR_FAMILIES",
                 "FAMILY_RUNTIME_MEMBERS", "evaluator_revision", "evaluator_config_revision",
                 "evaluator_family_revision"):
        assert getattr(eval_provenance, name) is getattr(evaluator_identity, name)


def test_runner_places_postpatch_identity_before_import_gate():
    source = RUNNER.read_text()
    identity = source.index("verify-evaluator-binding")
    patches = source.index("python3 setup/apply_patches.py --check")
    imports = source.index("NATIVE_IMPORT_GATE")
    assert patches < identity < imports


def test_submit_rejects_current_contract_but_unbound_payload_before_cloud(tmp_path):
    """A current runner contract must not make an unbound evaluator payload admissible."""
    archive = tmp_path / "unbound-submit.tgz"
    manifest = tmp_path / "payload_manifest.json"
    manifest.write_text(json.dumps({"runner_contract": _runner_contract(),
                                    "families": ["idaac"]}))
    with tarfile.open(archive, "w:gz") as handle:
        handle.add(manifest, arcname="payload_manifest.json")

    rlvigen = tmp_path / "rlvigen.tgz"
    rlvigen.write_bytes(b"placeholder")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    invoked = tmp_path / "datasphere-invoked"
    fake_cli = fake_bin / "datasphere"
    fake_cli.write_text("#!/bin/sh\ntouch \"$FAKE_DATASPHERE_INVOKED\"\nexit 0\n")
    fake_cli.chmod(0o755)
    image = json.loads((ROOT / "datasphere/native/source-lock.json").read_text())["container_image"]
    config = tmp_path / "unbound.yaml"
    config.write_text(
        "name: unbound-submit\n"
        "cmd: >-\n"
        "  CELLS=idaac:1 FRAMES=10000 bash ${JOB} ${CODE} ${RESULT}\n"
        "inputs:\n"
        f"  - {archive}: CODE\n"
        f"  - {rlvigen}: RLVIGEN\n"
        "env:\n"
        "  docker:\n"
        f"    image: {image}\n"
        "cloud-instance-type: gt4.1\n"
    )
    result = subprocess.run(
        ["bash", str(ROOT / "datasphere/native/job.sh"), "submit", str(config)],
        cwd=ROOT,
        env={**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}",
             "FAKE_DATASPHERE_INVOKED": str(invoked),
             "NATIVE_EVIDENCE_LOG": str(tmp_path / "actions.log"),
             # [2026-09-08] Keep `job.sh` out of the repo's real attempt record.
             "SUBMISSION_LEDGER": str(tmp_path / "submissions.jsonl")},
        text=True, capture_output=True,
    )
    assert result.returncode != 0
    assert "evaluator identity" in result.stderr.lower()
    assert not invoked.exists(), "unbound payload reached datasphere execute"


def test_runtime_tree_members_excludes_macos_appledouble_sidecar_files(tmp_path):
    """First-ever real exercise of this check (job bt18a8fjl3qrp5jv50g6, 2026-09-06) failed with
    an unhelpful "runtime member hash mismatch" -- diagnosed by adding temporary verbose output
    and resubmitting: every extra file the remote recomputation saw was a `._`-prefixed macOS
    AppleDouble sidecar (e.g. `._curl.py` beside `curl.py`). macOS's own `tar` folds these into
    extended attributes on extraction and they are invisible on this development machine, which is
    exactly why nobody caught this before the first Linux run. `._curl.py`'s suffix is still
    `.py`, so the suffix-only filter let them through as if they were real runtime members.
    """
    from datasphere.native import evaluator_identity

    tree = tmp_path / "some_family_dir"
    tree.mkdir()
    (tree / "curl.py").write_text("real content")
    (tree / "._curl.py").write_bytes(b"\x00\x05\x16\x07")  # AppleDouble sidecars are binary
    (tree / ".___init__.py").write_bytes(b"\x00\x05\x16\x07")
    (tree / "__init__.py").write_text("")

    members = evaluator_identity._runtime_tree_members(tmp_path, "some_family_dir")

    assert "some_family_dir/curl.py" in members
    assert "some_family_dir/__init__.py" in members
    assert not any(Path(m).name.startswith("._") for m in members), (
        f"AppleDouble sidecar file leaked into runtime members: {members}"
    )
    assert len(members) == 2, f"expected exactly the two real files, got: {members}"
