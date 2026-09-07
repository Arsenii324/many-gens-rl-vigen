from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "setup"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_reconstruction_manifest_covers_all_source_families_and_auxiliary_source():
    manifest = json.loads((SETUP / "source-reconstruction.json").read_text())
    assert set(manifest["families"]) == {
        "rlvigen", "dmc_gb", "alda", "ppg", "idaac", "ibac_sni", "ctrl",
    }
    for name, entry in manifest["families"].items():
        assert len(entry["commit"]) == 40, name
        assert len(entry["tree"]) == 40, name
        assert entry["url"].startswith("https://github.com/")
    assert manifest["auxiliary"]["openai_baselines"]["commit"] == (
        "ea25b9e8b234e6ee1bca43083f8f3cf974143998"
    )


def test_legacy_pin_copies_match_reconstruction_manifest():
    manifest = json.loads((SETUP / "source-reconstruction.json").read_text())
    pin_names = {"rlvigen": "rl_vigen"}
    expected = {
        pin_names.get(name, name): {"url": entry["url"], "sha": entry["commit"]}
        for name, entry in manifest["families"].items()
    }
    for relative in ("compute/datasphere/PINS.json", "compute/kaggle-src/PINS.json"):
        pins = json.loads((ROOT / relative).read_text())
        assert {name: pins[name] for name in expected} == expected


def test_normalized_tree_hash_ignores_only_declared_generated_paths(tmp_path: Path):
    module = _load("bootstrap_sources_for_test", SETUP / "bootstrap_sources.py")
    source = tmp_path / "source"
    (source / ".git").mkdir(parents=True)
    (source / "__pycache__").mkdir()
    (source / "results").mkdir()
    (source / "code.py").write_text("value = 1\n")
    (source / "door.xml").write_text("generated\n")
    (source / "results" / "old.jsonl").write_text("generated\n")
    (source / "__pycache__" / "code.pyc").write_bytes(b"generated")

    excluded = ("door.xml", "results")
    first = module.normalized_tree_hash(source, excluded)
    (source / "door.xml").write_text("different generated\n")
    (source / "results" / "new.jsonl").write_text("generated\n")
    assert module.normalized_tree_hash(source, excluded) == first

    (source / "code.py").write_text("value = 2\n")
    assert module.normalized_tree_hash(source, excluded) != first


def test_case_sensitive_requirement_is_detectable(tmp_path: Path):
    module = _load("bootstrap_sources_case_test", SETUP / "bootstrap_sources.py")
    probe = tmp_path / "probe"
    assert isinstance(module.filesystem_is_case_sensitive(probe), bool)


def test_exact_clone_rejects_wrong_commit(tmp_path: Path):
    module = _load("bootstrap_sources_clone_test", SETUP / "bootstrap_sources.py")
    source = tmp_path / "source"
    subprocess.run(["git", "init", "--quiet", str(source)], check=True)
    (source / "code.py").write_text("value = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(source), "add", "code.py"], check=True)
    subprocess.run(
        ["git", "-C", str(source), "-c", "user.name=test", "-c",
         "user.email=test@example.invalid", "commit", "--quiet", "-m", "fixture"],
        check=True,
    )
    commit = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    tree = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD^{tree}"], text=True).strip()
    destination = tmp_path / "destination"
    manifest_entry = {"url": str(source), "commit": commit, "tree": tree}
    module._clone_exact(manifest_entry, destination)
    assert (destination / "code.py").read_text(encoding="utf-8") == "value = 1\n"
    with pytest.raises(module.BootstrapError):
        module._verify_base(destination, {"commit": "0" * 40, "tree": tree})


def test_patch_checksum_mismatch_refuses_before_apply(tmp_path: Path):
    module = _load("bootstrap_sources_patch_test", SETUP / "bootstrap_sources.py")
    patch = tmp_path / "fixture.patch"
    patch.write_text("diff --git a/code.py b/code.py\n", encoding="utf-8")
    with pytest.raises(module.BootstrapError, match="patch hash mismatch"):
        module._verify_patch_hash(patch, {"patch_sha256": "0" * 64})


def test_publish_refuses_existing_destination(tmp_path: Path):
    module = _load("bootstrap_sources_publish_test", SETUP / "bootstrap_sources.py")
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    with pytest.raises(module.BootstrapError, match="refusing to replace"):
        module._publish(source, destination)

def test_bootstrap_root_parameter_is_authoritative(tmp_path):
    """`root=` must actually redirect writes, or an isolated test targets the real project.

    It did not: `bootstrap(root=...)` accepted the argument and then used the module-global ROOT
    for destinations, patch paths, case-sensitivity and verification. One of Luna's disposable
    safety probes hit the real checkout because of it (external review 24).

    Checked without a network clone: a destination that already exists must be seen at `root`,
    not at ROOT. With an empty `root`, every family looks absent, so the refusal this asserts can
    only come from the code consulting `root`.
    """
    bs = _load("bootstrap_sources", SETUP / "bootstrap_sources.py")

    calls = []

    def _no_network(name, entry, temporary, root=bs.ROOT):
        calls.append((name, root))
        raise bs.BootstrapError("stop before any clone")

    original = bs._prepare_family
    bs._prepare_family = _no_network
    try:
        with pytest.raises(bs.BootstrapError):
            bs.bootstrap(root=tmp_path, families=["ctrl"])
    finally:
        bs._prepare_family = original

    assert calls, "bootstrap never reached _prepare_family"
    assert calls[0][1] == tmp_path, (
        f"bootstrap passed {calls[0][1]} instead of the requested root {tmp_path}; the root "
        "parameter is decorative and an isolated run would write into the real project")
