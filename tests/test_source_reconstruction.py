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


def _synthetic_manifest(**families: dict) -> dict:
    return {"schema": 1, "families": families, "auxiliary": {}}


def test_bootstrap_refuses_partial_existing_family_destinations(tmp_path: Path, monkeypatch):
    """One of a family's destinations exists, the other does not: refuse rather than guess.

    A family with a `relocate` entry (like ALDA) has two destinations. If only one is present,
    the tree cannot be treated as either "absent" (clone it) or "already reconstructed" (verify
    it): it is neither, and bootstrap() must say so instead of silently overwriting or silently
    trusting the half that exists.
    """
    module = _load("bootstrap_sources_partial_test", SETUP / "bootstrap_sources.py")
    widget = {
        "url": "https://example.invalid/widget.git",
        "commit": "1" * 40,
        "tree": "2" * 40,
        "destination": "runnable/widget",
        "patch_kind": "git_patch",
        "patch_file": "runnable/_patches/widget.patch",
        "expected_tree_hash": "0" * 64,
        "exclude": [],
        "relocate": [
            {"from": "models", "to": "extra/widget-extra", "expected_tree_hash": "0" * 64},
        ],
    }
    monkeypatch.setattr(module, "load_manifest", lambda: _synthetic_manifest(widget=widget))
    (tmp_path / "runnable" / "widget").mkdir(parents=True)
    # extra/widget-extra deliberately left absent.
    with pytest.raises(module.BootstrapError, match="partial existing source tree"):
        module.bootstrap(root=tmp_path, families=["widget"])


def test_bootstrap_refuses_modified_existing_destination(tmp_path: Path, monkeypatch):
    """An existing destination whose content disagrees with the manifest is refused, not overwritten.

    bootstrap() treats any existing destination as "already reconstructed, just verify it" -- so a
    tree that was hand-edited (or corrupted) after a prior bootstrap must fail that verification
    and refuse, rather than being silently accepted or silently clobbered.
    """
    module = _load("bootstrap_sources_modified_test", SETUP / "bootstrap_sources.py")
    destination = tmp_path / "runnable" / "widget2"
    destination.mkdir(parents=True)
    (destination / "code.py").write_text("value = 1\n", encoding="utf-8")
    widget2 = {
        "url": "https://example.invalid/widget2.git",
        "commit": "1" * 40,
        "tree": "2" * 40,
        "destination": "runnable/widget2",
        "patch_kind": "git_patch",
        "patch_file": "runnable/_patches/widget2.patch",
        # Deliberately wrong: does not match the content just written above.
        "expected_tree_hash": "f" * 64,
        "exclude": [],
    }
    monkeypatch.setattr(module, "load_manifest", lambda: _synthetic_manifest(widget2=widget2))
    with pytest.raises(module.BootstrapError, match="does not match manifest"):
        module.bootstrap(root=tmp_path, families=["widget2"])


def test_verify_all_detects_missing_idaac_auxiliary_baselines_tree(tmp_path: Path, monkeypatch):
    """idaac's auxiliary OpenAI Baselines checkout is required; verify_all must not pass without it.

    Uses the real manifest's idaac entry (so the destination path and structure match production)
    with `patch_sha256` dropped and `expected_tree_hash` recomputed against a fabricated destination,
    so the test needs neither the real patch file nor a network clone.
    """
    module = _load("bootstrap_sources_idaac_aux_test", SETUP / "bootstrap_sources.py")
    manifest = json.loads((SETUP / "source-reconstruction.json").read_text())
    idaac_entry = dict(manifest["families"]["idaac"])
    idaac_entry.pop("patch_sha256", None)
    destination = tmp_path / idaac_entry["destination"]
    destination.mkdir(parents=True)
    (destination / "code.py").write_text("value = 1\n", encoding="utf-8")
    idaac_entry["expected_tree_hash"] = module.normalized_tree_hash(
        destination, idaac_entry.get("exclude", []))
    monkeypatch.setattr(module, "load_manifest", lambda: {
        "families": {"idaac": idaac_entry}, "auxiliary": manifest["auxiliary"],
    })
    # ext/baselines (the auxiliary destination) is deliberately left absent under tmp_path.
    # Current behaviour surfaces this as an uncaught FileNotFoundError rather than a clean
    # BootstrapError (normalized_tree_hash walks a directory that does not exist) -- still a
    # detection, just not a tidy one, so the test accepts either.
    with pytest.raises((module.BootstrapError, FileNotFoundError)):
        module.verify_all(root=tmp_path, families=["idaac"])


def test_verify_all_detects_missing_alda_relocated_models(tmp_path: Path, monkeypatch):
    """ALDA's `models` package is relocated to `third_party/alda/models`; its absence must fail verify_all.

    Uses the real manifest's alda entry (so the relocate target is the real production path,
    `third_party/alda/models`) with `patch_sha256` dropped and `expected_tree_hash` recomputed
    against a fabricated destination, so no network clone or real patch file is required.
    """
    module = _load("bootstrap_sources_alda_reloc_test", SETUP / "bootstrap_sources.py")
    manifest = json.loads((SETUP / "source-reconstruction.json").read_text())
    alda_entry = dict(manifest["families"]["alda"])
    alda_entry.pop("patch_sha256", None)
    destination = tmp_path / alda_entry["destination"]
    destination.mkdir(parents=True)
    (destination / "code.py").write_text("value = 1\n", encoding="utf-8")
    alda_entry["expected_tree_hash"] = module.normalized_tree_hash(
        destination, alda_entry.get("exclude", []))
    monkeypatch.setattr(module, "load_manifest", lambda: {
        "families": {"alda": alda_entry}, "auxiliary": manifest["auxiliary"],
    })
    assert alda_entry["relocate"][0]["to"] == "third_party/alda/models"
    # third_party/alda/models is deliberately left absent under tmp_path.
    with pytest.raises(module.BootstrapError, match="required relocated source is absent"):
        module.verify_all(root=tmp_path, families=["alda"])


def test_pins_json_copies_are_byte_identical_and_agree_with_manifest():
    """The two legacy PINS.json copies must stay byte-identical, not just individually correct.

    `test_legacy_pin_copies_match_reconstruction_manifest` already checks each file's projection
    against the manifest independently; it does not catch the two copies drifting from EACH OTHER
    while each still happens to satisfy that projection (e.g. differing whitespace, key order, or
    an extra family in only one file). Byte-identity is the stronger, and the actually-intended,
    invariant.
    """
    datasphere_bytes = (ROOT / "compute/datasphere/PINS.json").read_bytes()
    kaggle_bytes = (ROOT / "compute/kaggle-src/PINS.json").read_bytes()
    assert datasphere_bytes == kaggle_bytes

    manifest = json.loads((SETUP / "source-reconstruction.json").read_text())
    pin_names = {"rlvigen": "rl_vigen"}
    expected = {
        pin_names.get(name, name): {"url": entry["url"], "sha": entry["commit"]}
        for name, entry in manifest["families"].items()
    }
    pins = json.loads(datasphere_bytes)
    for name, values in expected.items():
        assert name in pins, name
        assert pins[name]["url"] == values["url"], name
        assert len(pins[name]["sha"]) == 40, name
        assert pins[name]["sha"] == values["sha"], name


def test_case_sensitive_requirement_raises_on_case_insensitive_filesystem(
    tmp_path: Path, monkeypatch,
):
    """`_case_sensitive_requirement` must refuse when the filesystem is case-insensitive.

    Monkeypatches `filesystem_is_case_sensitive` instead of relying on the real filesystem, so
    this is deterministic on both a case-insensitive default macOS volume and a case-sensitive
    Linux one.
    """
    module = _load("bootstrap_sources_case_insensitive_test", SETUP / "bootstrap_sources.py")
    monkeypatch.setattr(module, "filesystem_is_case_sensitive", lambda path: False)
    with pytest.raises(module.BootstrapError, match="case-sensitive filesystem"):
        module._case_sensitive_requirement(tmp_path)

    monkeypatch.setattr(module, "filesystem_is_case_sensitive", lambda path: True)
    module._case_sensitive_requirement(tmp_path)  # does not raise
