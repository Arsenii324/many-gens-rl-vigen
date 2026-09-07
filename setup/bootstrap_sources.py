#!/usr/bin/env python3
"""Reconstruct pinned source trees for local development and payload building."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = Path(__file__).with_name("source-reconstruction.json")
ALWAYS_IGNORED_NAMES = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
ALWAYS_IGNORED_SUFFIXES = {".pyc", ".pyo"}


class BootstrapError(RuntimeError):
    pass


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _excluded(relative: str, patterns: Iterable[str]) -> bool:
    path = Path(relative)
    if any(part in ALWAYS_IGNORED_NAMES for part in path.parts):
        return True
    if path.name == ".DS_Store" or path.suffix in ALWAYS_IGNORED_SUFFIXES:
        return True
    for pattern in patterns:
        if pattern == ".egg-info" and any(part.endswith(".egg-info") for part in path.parts):
            return True
        if relative == pattern or relative.startswith(pattern.rstrip("/") + "/"):
            return True
    return False


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _records(root: Path, exclude: Iterable[str] = ()) -> list[tuple[str, tuple]]:
    records: list[tuple[str, tuple]] = []

    def walk(directory: Path, prefix: str = "") -> None:
        for entry in sorted(os.scandir(directory), key=lambda item: item.name):
            relative = f"{prefix}/{entry.name}" if prefix else entry.name
            path = Path(entry.path)
            if _excluded(relative, exclude):
                continue
            info = os.lstat(path)
            mode = stat.S_IMODE(info.st_mode)
            if stat.S_ISLNK(info.st_mode):
                records.append((relative, ("symlink", mode, os.readlink(path))))
            elif stat.S_ISDIR(info.st_mode):
                walk(path, relative)
            elif stat.S_ISREG(info.st_mode):
                records.append((relative, ("file", mode, info.st_size, _file_hash(path))))
            else:
                raise BootstrapError(f"unsupported source entry: {relative}")

    walk(root)
    return records


def normalized_tree_hash(root: Path, exclude: Iterable[str] = ()) -> str:
    digest = hashlib.sha256()
    for relative, record in _records(root, exclude):
        digest.update(json.dumps([relative, record], separators=(",", ":")).encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def filesystem_is_case_sensitive(path: Path) -> bool:
    path.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".case-probe-", dir=path) as raw:
        probe = Path(raw)
        first = probe / "CaseProbe"
        second = probe / "caseprobe"
        first.write_text("x", encoding="utf-8")
        if second.exists():
            return False
        second.write_text("y", encoding="utf-8")
        return first.read_text(encoding="utf-8") == "x"


def _run(command: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip().splitlines()
        raise BootstrapError(f"command failed ({result.returncode}): {' '.join(command)}\n"
                             f"{detail[-1] if detail else 'no output'}")
    return result.stdout.strip()


def _git(path: Path, *args: str) -> str:
    return _run(["git", "-C", str(path), *args])


def _verify_base(path: Path, entry: dict) -> None:
    if _git(path, "rev-parse", "HEAD") != entry["commit"]:
        raise BootstrapError(f"wrong source commit at {path}")
    if _git(path, "rev-parse", "HEAD^{tree}") != entry["tree"]:
        raise BootstrapError(f"wrong source tree at {path}")
    if _git(path, "status", "--porcelain=v1", "--untracked-files=all"):
        raise BootstrapError(f"source checkout is not pristine before patching: {path}")


def _clone_exact(entry: dict, destination: Path) -> None:
    _run(["git", "init", "--quiet", str(destination)])
    _git(destination, "remote", "add", "origin", entry["url"])
    _run(["git", "-C", str(destination), "fetch", "--quiet", "--depth", "1",
          "origin", entry["commit"]])
    _git(destination, "checkout", "--quiet", "--detach", entry["commit"])
    _verify_base(destination, entry)


def _verify_patch_hash(path: Path, entry: dict) -> None:
    expected = entry.get("patch_sha256")
    if expected and _file_hash(path) != expected:
        raise BootstrapError(f"patch hash mismatch: {path}")


def _apply_family_patch(source: Path, entry: dict) -> None:
    patch = ROOT / entry["patch_file"]
    _verify_patch_hash(patch, entry)
    _run(["git", "-C", str(source), "apply", "--check", str(patch)])
    _run(["git", "-C", str(source), "apply", str(patch)])


def _copy_materialized(source: Path, destination: Path, exclude: list[str]) -> None:
    if destination.exists() or destination.is_symlink():
        raise BootstrapError(f"refusing to overwrite existing destination: {destination}")
    destination.mkdir(parents=True)
    for relative, _record in _records(source, exclude):
        source_path = source / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source_path.is_symlink():
            link_target = os.readlink(source_path)
            if os.path.isabs(link_target):
                raise BootstrapError(f"absolute source symlink refused: {relative}")
            target.symlink_to(link_target)
        else:
            shutil.copy2(source_path, target)


def _copy_subtree(source: Path, destination: Path) -> None:
    if destination.exists() or destination.is_symlink():
        raise BootstrapError(f"refusing to overwrite existing destination: {destination}")
    _copy_materialized(source, destination, [])


def _check_expected_hash(root: Path, entry: dict) -> None:
    expected = entry.get("expected_tree_hash")
    if not expected:
        raise BootstrapError(f"manifest has no expected tree hash for {root}")
    actual = normalized_tree_hash(root, entry.get("exclude", []))
    if actual != expected:
        raise BootstrapError(f"source closure hash mismatch at {root}: {actual}")


def _retain_git_metadata(source: Path, destination: Path) -> None:
    metadata = source / ".git"
    if metadata.is_dir():
        shutil.copytree(metadata, destination / ".git", symlinks=True)
    elif metadata.is_file():
        shutil.copy2(metadata, destination / ".git")
    else:
        raise BootstrapError(f"source has no Git metadata: {source}")


def _case_sensitive_requirement() -> None:
    if not filesystem_is_case_sensitive(ROOT):
        raise BootstrapError(
            "RL-ViGen reconstruction requires a case-sensitive filesystem; "
            "use Linux or a case-sensitive volume because upstream contains both "
            "cfgs/task/TwoArmHandover.yaml and cfgs/task/TwoArmHandOver.yaml"
        )


def _publish(source: Path, destination: Path) -> None:
    if destination.exists() or destination.is_symlink():
        raise BootstrapError(f"refusing to replace existing destination: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix=f".{destination.name}.publish-", dir=destination.parent))
    shutil.rmtree(staged)
    shutil.copytree(source, staged, symlinks=True)
    os.rename(staged, destination)


def _prepare_family(name: str, entry: dict, temporary: Path) -> list[tuple[Path, Path]]:
    if name == "rlvigen":
        _case_sensitive_requirement()
    raw = temporary / name / "raw"
    raw.parent.mkdir(parents=True, exist_ok=True)
    _clone_exact(entry, raw)
    if entry["patch_kind"] == "git_patch":
        _apply_family_patch(raw, entry)
    else:
        work = temporary / name / "registry-work"
        (work / "setup").mkdir(parents=True)
        shutil.copy2(ROOT / "setup/apply_patches.py", work / "setup/apply_patches.py")
        shutil.move(raw, work / "RL-ViGen-upstream")
        raw = work / "RL-ViGen-upstream"
        _run(["python3", "setup/apply_patches.py"], cwd=work)
        _run(["python3", "setup/apply_patches.py", "--check"], cwd=work)
    output = temporary / name / "output"
    _copy_materialized(raw, output, entry.get("exclude", []))
    _retain_git_metadata(raw, output)
    _check_expected_hash(output, entry)
    outputs = [(output, ROOT / entry["destination"])]
    for relocation in entry.get("relocate", []):
        source = raw / relocation["from"]
        target = temporary / name / "relocated" / relocation["to"]
        _copy_subtree(source, target)
        _check_expected_hash(target, relocation)
        outputs.append((target, ROOT / relocation["to"]))
    return outputs


def _prepare_auxiliary(entry: dict, temporary: Path) -> tuple[Path, Path]:
    raw = temporary / "openai_baselines" / "raw"
    raw.parent.mkdir(parents=True, exist_ok=True)
    _clone_exact(entry, raw)
    output = temporary / "openai_baselines" / "output"
    _copy_materialized(raw, output, entry.get("exclude", []))
    _retain_git_metadata(raw, output)
    _check_expected_hash(output, entry)
    return output, ROOT / entry["destination"]


def _verify_destination(root: Path, entry: dict) -> None:
    destination = root / entry["destination"]
    if _git(destination, "rev-parse", "HEAD") != entry["commit"]:
        raise BootstrapError(f"wrong source commit at {destination}")
    if _git(destination, "rev-parse", "HEAD^{tree}") != entry["tree"]:
        raise BootstrapError(f"wrong source tree at {destination}")
    if entry.get("patch_sha256"):
        _verify_patch_hash(root / entry["patch_file"], entry)
    expected = entry.get("expected_tree_hash")
    if not expected:
        raise BootstrapError(f"manifest has no expected tree hash for {entry['destination']}")
    actual = normalized_tree_hash(destination, entry.get("exclude", []))
    if actual != expected:
        raise BootstrapError(f"source closure hash mismatch at {destination}: {actual}")


def verify_all(root: Path = ROOT, families: Iterable[str] | None = None) -> None:
    manifest = load_manifest()
    selected = set(families or manifest["families"])
    unknown = selected - set(manifest["families"])
    if unknown:
        raise BootstrapError(f"unknown family: {', '.join(sorted(unknown))}")
    for name in sorted(selected):
        entry = manifest["families"][name]
        _verify_destination(root, entry)
        for relocation in entry.get("relocate", []):
            target = root / relocation["to"]
            if not target.is_dir():
                raise BootstrapError(f"required relocated source is absent: {target}")
            _check_expected_hash(target, relocation)
    if "idaac" in selected:
        auxiliary = manifest["auxiliary"]["openai_baselines"]
        _verify_destination(root, auxiliary)


def bootstrap(root: Path = ROOT, families: Iterable[str] | None = None) -> None:
    manifest = load_manifest()
    selected = set(families or manifest["families"])
    unknown = selected - set(manifest["families"])
    if unknown:
        raise BootstrapError(f"unknown family: {', '.join(sorted(unknown))}")
    if "idaac" in selected:
        selected_auxiliary = True
    else:
        selected_auxiliary = False
    with tempfile.TemporaryDirectory(prefix="many-gens-bootstrap-") as raw_temporary:
        temporary = Path(raw_temporary)
        outputs: list[tuple[Path, Path]] = []
        for name in sorted(selected):
            entry = manifest["families"][name]
            destinations = [ROOT / entry["destination"]]
            destinations.extend(ROOT / item["to"] for item in entry.get("relocate", []))
            if name == "idaac":
                destinations.append(ROOT / manifest["auxiliary"]["openai_baselines"]["destination"])
            present = [path.exists() or path.is_symlink() for path in destinations]
            if any(present):
                if not all(present):
                    raise BootstrapError(f"partial existing source tree for {name}; refusing overwrite")
                try:
                    verify_all(families=[name])
                except BootstrapError as error:
                    raise BootstrapError(
                        f"existing source tree for {name} does not match manifest; refusing overwrite"
                    ) from error
                continue
            outputs.extend(_prepare_family(name, manifest["families"][name], temporary))
        if selected_auxiliary and not (ROOT / manifest["auxiliary"]["openai_baselines"]["destination"]).exists():
            outputs.append(_prepare_auxiliary(manifest["auxiliary"]["openai_baselines"], temporary))
        for source, destination in outputs:
            if destination.exists() or destination.is_symlink():
                raise BootstrapError(f"refusing to overwrite existing destination: {destination}")
            _publish(source, destination)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", action="append", choices=sorted(load_manifest()["families"]))
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.verify_only:
            verify_all()
        else:
            bootstrap(families=args.family)
    except BootstrapError as error:
        print(f"error: {error}", file=os.sys.stderr)
        return 2
    print("source reconstruction verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())