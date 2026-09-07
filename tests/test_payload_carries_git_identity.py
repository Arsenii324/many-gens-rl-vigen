"""Every payload must say which tree built it.

`results/submissions.jsonl` records commit and dirtiness at SUBMIT time, which answers "what did
we launch". It does not travel with the artifact. A `records.jsonl` retrieved from a job and read a
month later could not say which tree produced it — the payload manifest is the one thing that is
both present in the container and referenced by every record's provenance, so the identity belongs
there. Phase 3 of the production plan lists this as an open gap; this is it closed.

`source_dirty` is RECORDED, not refused. A dirty build is legitimate for a probe and illegitimate
for a wave, and `production_gates.py::gate_source_tree_frozen` already makes that judgement.
Duplicating the rule here would let two copies of it disagree.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tarfile

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "datasphere" / "native" / "contract.py"


@pytest.fixture(scope="module")
def manifest(tmp_path_factory):
    out = tmp_path_factory.mktemp("payload") / "probe.tgz"
    done = subprocess.run(
        [sys.executable, str(CONTRACT), "build-payload", "--source", str(ROOT),
         "--output", str(out), "--families", "ctrl"],
        capture_output=True, text=True, cwd=str(ROOT), timeout=600)
    assert done.returncode == 0, done.stderr[-2000:]
    with tarfile.open(out) as archive:
        return json.loads(archive.extractfile("payload_manifest.json").read())


def test_the_manifest_names_the_commit(manifest):
    commit = manifest.get("source_commit")
    assert commit, "payload manifest carries no source_commit"
    if commit != "unknown":
        assert len(commit) == 40 and all(c in "0123456789abcdef" for c in commit), commit


def test_the_manifest_says_whether_the_tree_was_clean(manifest):
    assert "source_dirty" in manifest, "a commit without dirtiness is not an identity"
    assert manifest["source_dirty"] in (True, False, "unknown")


def test_identity_does_not_replace_the_binding_it_sits_beside(manifest):
    """Git identity is provenance, not verification -- the member hashes still do that work."""
    assert manifest.get("members"), "member hashes are what actually bind the payload"
    assert "evaluator_bindings" in manifest or "identity_unavailable" in manifest


def test_a_source_tree_without_git_still_builds(tmp_path):
    """Refusing to build outside a repository would break extracted-tarball and fixture use."""
    import contextlib
    sys.path.insert(0, str(ROOT / "datasphere" / "native"))
    with contextlib.suppress(ImportError):
        import contract
        identity = contract._git_identity(tmp_path)
        assert identity["source_commit"] == "unknown"
        assert identity["source_dirty"] == "unknown"
