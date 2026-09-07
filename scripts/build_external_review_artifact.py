#!/usr/bin/env python3
"""Build a non-destructive, directory-first external review artifact.

The builder intentionally has no project-specific imports and never follows source symlinks.
Selection is explicit so that an excluded path is evidence in the artifact rather than an
unexplained absence.  The output is published only after source and destination hashes have been
verified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA = 1
BUILDER = "build_external_review_artifact.py"

# These are the review surfaces named by notes/EXTERNAL-REVIEW-ARTIFACT-BLUEPRINT.md.  Root-level
# files are included separately because README, source locks, requirements and project indexes
# carry provenance too.
INCLUDED_TOP_LEVEL = (
    "baselines",
    "compute",
    "configs",
    "docs",
    "mutants",
    "notes",
    "research",
    "rlgen",
    "scripts",
    "tests",
    "setup",
    "datasphere",
    "runnable",
    "RL-ViGen-upstream",
    "third_party",
    "tools",
)
EXT_INCLUDED_ROOTS = (
    "ext/baseline_resources",
    "ext/papers-sorted",
    "ext/drqv2",
    "ext/drq",
    "ext/SGQN",
    "ext/curl",
    "ext/rad",
    "ext/ALDA_Official",
    "ext/idaac",
    "ext/phasic-policy-gradient",
    "ext/IBAC-SNI",
    "ext/ctrl_public",
    "ext/ctrl_rl",
    "ext/rl_vigen",
    "ext/dmcontrol-generalization-benchmark",
    "ext/robosuite",
    "ext/secant_robosuite",
    "ext/pytorch-a2c-ppo-acktr-gail",
    "ext/baselines",
)
EXT_EXCLUDED_ROOTS = (
    "ext/_duplicates",
    "ext/ctrl_WRONG_llm_critic_2502.03492",
)
KNOWN_UNRELATED_SOURCES = {
    "ext/baseline_resources/11_ibac_sni/paper_1901.10902.pdf": (
        "known-unrelated-source",
        "unrelated InfoBot paper; arXiv:1901.10902 is not IBAC-SNI (arXiv:1910.12911)",
    ),
}

PRIVATE_PATHS = {
    "notes/ask-claude.md",
    "notes/claude-answers.md",
}
PRIVATE_PARTS = {".claude"}
PRIVATE_NAME_RE = re.compile(r"(?:mailbox|session-transcript|conversation|chat-history)", re.I)

# Credential-like names are a hard error, including when the path would otherwise be excluded.
# This prevents a future rule change from accidentally turning a credential into a copied file.
SECRET_NAME_RE = re.compile(
    r"^(?:\.env(?:\..*)?|.*(?:wandb[_-]?key|api[_-]?key|access[_-]?token|secret[_-]?key|"
    r"credentials?|service[_-]?account|id[_-](?:rsa|ed25519))(?:\..*)?|.*\.(?:pem|key|token))$",
    re.I,
)
SECRET_PARTS = {"secrets", "credentials"}

CACHE_NAMES = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox"}
DATA_DIR_NAMES = {"checkpoints", "datasets", "data"}
MEDIA_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".mp4", ".avi", ".mov", ".wav",
}
ARCHIVE_SUFFIXES = {".tgz", ".tar", ".gz", ".zip", ".7z", ".whl"}
# This is an official source bundle named by the CTRL source closure, not a run/payload archive.
# Keep it as raw evidence; all other archive suffixes remain explicitly excluded.
SOURCE_ARCHIVE_EXCEPTIONS = {"ext/ctrl_rl/supp_mat_revision_2/code.zip"}
CHECKPOINT_SUFFIXES = {
    ".pt", ".pth", ".ckpt", ".msgpack", ".jd", ".h5", ".hdf5", ".pkl", ".pickle",
}
NUMERIC_DATA_SUFFIXES = {".npy", ".npz", ".parquet", ".sqlite", ".db", ".bin"}


class BuildError(RuntimeError):
    """An expected, fail-closed builder refusal."""


def _posix(rel: str) -> str:
    return rel.replace(os.sep, "/")


def _safe_relative(rel: str) -> str:
    """Validate a source-relative path before it becomes a destination path or manifest value."""
    rel = _posix(rel)
    path = Path(rel)
    if not rel or path.is_absolute() or ".." in path.parts:
        raise BuildError(f"unsafe relative path refused: {rel!r}")
    return rel


def _open_regular(path: Path) -> tuple[int, os.stat_result]:
    """Open a regular file without following a symlink, then return fd and stat."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise BuildError(f"cannot open regular source file safely: {path}") from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise BuildError(f"regular source file required: {path}")
    except Exception:
        os.close(fd)
        raise
    return fd, info


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    fd, _ = _open_regular(path)
    with os.fdopen(fd, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_secret_path(rel: str) -> bool:
    parts = Path(rel).parts
    if any(part.lower() in SECRET_PARTS for part in parts[:-1]):
        return True
    return bool(SECRET_NAME_RE.match(parts[-1]))


def _is_private_path(rel: str) -> bool:
    if rel in PRIVATE_PATHS or any(part in PRIVATE_PARTS for part in Path(rel).parts):
        return True
    return bool(PRIVATE_NAME_RE.search(Path(rel).name))


def _is_forbidden_transcript(path: Path) -> bool:
    if _is_secret_path(_posix(str(path))) or _is_private_path(_posix(str(path))):
        return True
    return path.name in {Path(private_path).name for private_path in PRIVATE_PATHS}


def _under(rel: str, root: str) -> bool:
    return rel == root or rel.startswith(root + "/")


def _symlink_target_record(source: Path, rel: str, path: Path) -> dict[str, Any]:
    raw_target = os.readlink(path)
    target_path = Path(raw_target)
    target_is_secret = _is_secret_path(_posix(raw_target))
    target_redacted = target_path.is_absolute() or target_is_secret
    resolved = (path.parent / target_path).resolve(strict=False)
    try:
        inside = os.path.commonpath((str(source), str(resolved))) == str(source)
    except ValueError:
        inside = False
    try:
        target_stat = os.stat(path)
    except OSError:
        target_type = "missing-or-inaccessible"
    else:
        if stat.S_ISDIR(target_stat.st_mode):
            target_type = "directory"
        elif stat.S_ISREG(target_stat.st_mode):
            target_type = "file"
        else:
            target_type = "other"
    return {
        "target": "<redacted>" if target_redacted else raw_target,
        "target_fingerprint": hashlib.sha256(raw_target.encode("utf-8")).hexdigest(),
        "target_redacted": target_redacted,
        "target_inside_source": inside,
        "target_type": target_type,
    }


def _ext_selection(rel: str) -> tuple[bool, str | None]:
    if any(_under(rel, root) for root in EXT_EXCLUDED_ROOTS):
        return False, "unrelated or duplicate external source tree"
    if any(_under(rel, root) for root in EXT_INCLUDED_ROOTS):
        return True, None
    return False, "external tree is outside the declared original-source closure"


def _exclusion(rel: str, kind: str) -> tuple[str, str] | None:
    """Return (rule, reason), or None when a regular file is allowed."""
    known_exclusion = KNOWN_UNRELATED_SOURCES.get(rel)
    if known_exclusion is not None:
        return known_exclusion

    parts = Path(rel).parts
    lower_parts = {part.lower() for part in parts}
    name = Path(rel).name
    suffix = Path(name).suffix.lower()

    if ".git" in lower_parts:
        return "cache-or-git", "git metadata/history"
    if any(part in CACHE_NAMES for part in parts):
        return "cache-or-git", "generated cache"
    if _is_private_path(rel):
        return "private-coordination", "private mailbox or session surface"
    if any(part.lower() in DATA_DIR_NAMES for part in parts):
        return "explicit-data-directory", "dataset/checkpoint data directory"

    ext_ok, ext_reason = _ext_selection(rel)
    if parts and parts[0] == "ext" and not ext_ok:
        return "external-selection", ext_reason or "external source not selected"
    if parts and parts[0] not in INCLUDED_TOP_LEVEL and parts[0] not in {"ext"}:
        # Root files are included; a non-root directory not listed above is not.
        if len(parts) > 1:
            return "top-level-selection", "project tree outside the declared review surfaces"

    if suffix in ARCHIVE_SUFFIXES and rel not in SOURCE_ARCHIVE_EXCEPTIONS:
        return "payload-or-source-archive", "archive excluded from directory review artifact"
    if suffix in CHECKPOINT_SUFFIXES:
        return "checkpoint-or-model-binary", "checkpoint/model binary excluded"
    if suffix in MEDIA_SUFFIXES:
        return "media", "media binary excluded; source-relative omission is declared"
    if suffix in NUMERIC_DATA_SUFFIXES:
        return "binary-or-data", "generated numeric/database data excluded"
    if name in {".DS_Store", "Thumbs.db"}:
        return "generated-metadata", "desktop/generated metadata"
    return None


def _walk_nodes(source: Path) -> Iterable[tuple[str, str, Path]]:
    """Yield (kind, source-relative path, absolute path) without following symlinks."""
    stack = [source]
    while stack:
        directory = stack.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError as exc:
            raise BuildError(f"cannot scan source directory {directory.name!r}") from exc
        for entry in entries:
            path = Path(entry.path)
            rel = _safe_relative(_posix(os.path.relpath(path, source)))
            if entry.is_symlink():
                yield "symlink", rel, path
            elif entry.is_dir(follow_symlinks=False):
                yield "directory", rel, path
                stack.append(path)
            elif entry.is_file(follow_symlinks=False):
                yield "file", rel, path
            else:
                yield "other", rel, path


def _git_metadata(source: Path) -> dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "-C", str(source), "status", "--porcelain=v1", "--untracked-files=all"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        branch = subprocess.run(
            ["git", "-C", str(source), "symbolic-ref", "--quiet", "--short", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        ).stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return {
            "git_available": False,
            "commit": None,
            "branch": None,
            "tree_dirty": None,
            "uncommitted_paths": [],
            "status_porcelain": [],
        }
    paths = set()
    for line in status:
        # Keep status text (including rename notation) without exposing file contents.  The
        # manifest needs the full dirty surface, not a count that hides a changed file.
        path_text = line[3:] if len(line) >= 3 else line
        rename_parts = path_text.split(" -> ")
        paths.update(rename_parts)
    return {
        "git_available": True,
        "commit": commit or None,
        "branch": branch,
        "tree_dirty": bool(status),
        "uncommitted_paths": sorted(paths),
        "status_porcelain": status,
    }


def _scan_plan(source: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    included: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    symlinks: list[dict[str, Any]] = []
    for kind, rel, path in _walk_nodes(source):
        if _is_secret_path(rel):
            # Never read or print this file.  The relative name is enough to correct the source.
            raise BuildError(f"credential-like source path refused: {rel}")
        exclusion = _exclusion(rel, kind)
        if kind == "symlink":
            row = {
                "kind": "symlink",
                "source_relative_path": rel,
                "bytes": None,
                "rule": "symlink-never-followed",
                "reason": "symlink is recorded but never copied or traversed",
            }
            row.update(_symlink_target_record(source, rel, path))
            symlinks.append(row)
            exclusions.append(row)
        elif exclusion is not None:
            rule, reason = exclusion
            info = os.lstat(path)
            exclusions.append({
                "kind": kind,
                "source_relative_path": rel,
                "bytes": info.st_size if stat.S_ISREG(info.st_mode) else None,
                "mode": stat.S_IMODE(info.st_mode),
                "rule": rule,
                "reason": reason,
            })
        elif kind == "file":
            try:
                mode = stat.S_IMODE(os.lstat(path).st_mode)
            except OSError as exc:
                raise BuildError(f"cannot inspect source file safely: {rel}") from exc
            included.append({
                "kind": "file",
                "source_relative_path": rel,
                "artifact_relative_path": rel,
                "mode": mode,
                "bytes": os.lstat(path).st_size,
            })
    return included, exclusions, symlinks


def _plan_signature(plan: tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]):
    included, exclusions, symlinks = plan
    return (
        tuple((row["source_relative_path"], row.get("mode"), row.get("bytes")) for row in included),
        tuple((row["kind"], row["source_relative_path"], row.get("rule"), row.get("mode"), row.get("bytes")) for row in exclusions),
        tuple((row["source_relative_path"], row["target_fingerprint"]) for row in symlinks),
    )


def _plan_digest(plan: tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]) -> str:
    encoded = json.dumps(_plan_signature(plan), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _fully_included_roots(exclusions: list[dict[str, Any]]) -> list[str]:
    return [
        f"{root}/**"
        for root in INCLUDED_TOP_LEVEL
        if not any(_under(row["source_relative_path"], root) for row in exclusions)
    ]


def _copy_and_verify(source: Path, stage: Path, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        rel = _safe_relative(row["source_relative_path"])
        src = source / Path(rel)
        dest = stage / Path(_safe_relative(row["artifact_relative_path"]))
        dest.parent.mkdir(parents=True, exist_ok=True)
        before = _sha256(src)
        try:
            source_info = os.lstat(src)
        except OSError as exc:
            raise BuildError(f"source disappeared during staging: {rel}") from exc
        if not stat.S_ISREG(source_info.st_mode) or stat.S_IMODE(source_info.st_mode) != row["mode"]:
            raise BuildError(f"source type/mode changed during staging: {rel}")
        source_fd, _ = _open_regular(src)
        dest_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        try:
            dest_fd = os.open(dest, dest_flags, 0o600)
        except OSError as exc:
            os.close(source_fd)
            raise BuildError(f"cannot create staged file safely: {rel}") from exc
        copied = hashlib.sha256()
        try:
            with os.fdopen(source_fd, "rb") as source_handle, os.fdopen(dest_fd, "wb") as dest_handle:
                for block in iter(lambda: source_handle.read(1024 * 1024), b""):
                    copied.update(block)
                    dest_handle.write(block)
                dest_handle.flush()
                os.fchmod(dest_handle.fileno(), row["mode"])
        except Exception:
            # fdopen closes both descriptors on normal exception paths.
            raise
        if copied.hexdigest() != before:
            raise BuildError(f"source changed while staging {rel}")
        after = _sha256(dest)
        if before != after or stat.S_IMODE(os.lstat(dest).st_mode) != row["mode"]:
            raise BuildError(f"hash mismatch while staging {rel}")
        row["sha256"] = after
        row["bytes"] = dest.stat().st_size


def _copy_transcript(transcript: Path, stage: Path) -> dict[str, Any]:
    if transcript.is_symlink() or not transcript.is_file():
        raise BuildError("test transcript must be an existing regular file, not a symlink")
    if _is_forbidden_transcript(transcript):
        raise BuildError("private or credential-like test transcript refused")
    dest_rel = _safe_relative(f"evidence/{transcript.name}")
    dest = stage / Path(dest_rel)
    dest.parent.mkdir(parents=True, exist_ok=True)
    before = _sha256(transcript)
    source_fd, _ = _open_regular(transcript)
    dest_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        dest_fd = os.open(dest, dest_flags, 0o600)
    except OSError as exc:
        os.close(source_fd)
        raise BuildError("cannot create staged transcript safely") from exc
    with os.fdopen(source_fd, "rb") as source_handle, os.fdopen(dest_fd, "wb") as dest_handle:
        for block in iter(lambda: source_handle.read(1024 * 1024), b""):
            dest_handle.write(block)
        dest_handle.flush()
    after = _sha256(dest)
    if before != after:
        raise BuildError("hash mismatch while staging test transcript")
    return {
        "supplied": True,
        "input_basename": transcript.name,
        "artifact_relative_path": dest_rel,
        "sha256": after,
        "bytes": dest.stat().st_size,
        "mode": stat.S_IMODE(os.lstat(dest).st_mode),
    }


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _validate_manifest_paths(value: Any, key: str = "") -> None:
    if isinstance(value, dict):
        for child_key, child in value.items():
            _validate_manifest_paths(child, child_key)
    elif isinstance(value, list):
        for child in value:
            _validate_manifest_paths(child, key)
    elif isinstance(value, str) and key.endswith("relative_path"):
        _safe_relative(value)


def _readme(mode: str, transcript_supplied: bool) -> str:
    if mode == "source-fidelity":
        scope = "SOURCE-FIDELITY REVIEW NOW"
        note = "This is a pre-freeze source snapshot; a clean production claim is not licensed."
    else:
        scope = "FINAL PRODUCTION-READINESS REVIEW LATER"
        note = "This snapshot was accepted only from a clean source tree with a supplied test transcript."
    return f"""# External review artifact

**Scope:** {scope}

{note}

This is a directory artifact. `artifact-manifest.json` is authoritative for provenance, selection
rules, included-file hashes, exclusions, and symlinks. `included-files.jsonl`,
`excluded-files.jsonl`, and `symlinks.jsonl` are line-oriented navigation copies of the same
machine-readable evidence. No source symlink was dereferenced.

The intended review blueprint is `notes/EXTERNAL-REVIEW-ARTIFACT-BLUEPRINT.md`; the primary-source
reconciliation is `notes/PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md` when those files are present in
the source snapshot. Read the manifest and exclusions before interpreting absence as a project
deletion.

Test transcript supplied: **{str(transcript_supplied).lower()}**.
"""


def _publish_without_replacement(stage: Path, output: Path) -> None:
    """Claim output without allowing rename() to replace a concurrent empty directory."""
    try:
        output.mkdir()
    except FileExistsError as exc:
        raise BuildError("output appeared during build; refusing publication") from exc
    try:
        for child in sorted(stage.iterdir(), key=lambda path: path.name):
            destination = output / child.name
            if os.path.lexists(destination):
                raise BuildError("output changed during publication; refusing replacement")
            os.rename(child, destination)
        stage.rmdir()
    except Exception:
        # Keep partial output and stage for inspection. Never delete another process's data.
        raise


def build(source_arg: str, output_arg: str, mode: str, transcript_arg: str | None) -> Path:
    source = Path(source_arg)
    if source.is_symlink() or not source.is_dir():
        raise BuildError("source must be an existing real directory")
    source = Path(os.path.abspath(source))
    output = Path(os.path.abspath(output_arg))
    if os.path.lexists(output):
        raise BuildError("output already exists; refusing to overwrite it")
    source_real = Path(os.path.realpath(source))
    output_real = Path(os.path.realpath(output))
    try:
        if os.path.commonpath((str(source_real), str(output_real))) == str(source_real):
            raise BuildError("output may not be nested within source")
    except ValueError as exc:
        raise BuildError("source and output are on incompatible path roots") from exc
    if mode == "final-production" and not transcript_arg:
        raise BuildError("final-production requires --test-transcript")

    transcript = Path(transcript_arg).absolute() if transcript_arg else None
    if transcript is not None and (transcript.is_symlink() or not transcript.is_file()):
        raise BuildError("test transcript must be an existing regular file, not a symlink")

    scan_started = datetime.now(timezone.utc).isoformat()
    git = _git_metadata(source)
    if mode == "final-production":
        if not git["git_available"]:
            raise BuildError("final-production requires a readable git working tree")
        if git["tree_dirty"]:
            raise BuildError("final-production refuses a dirty source tree")

    plan = _scan_plan(source)
    stage_parent = output.parent
    stage_parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=str(stage_parent)))
    # Deliberately leave a failed stage for inspection.  No source or pre-existing destination is
    # ever removed, and a failed build cannot silently clean evidence another process may need.
    try:
        included, exclusions, symlinks = plan
        for record_id, row in enumerate(exclusions):
            row["record_id"] = record_id
            row["pattern"] = row["source_relative_path"]
            row["present_in_project"] = True
            row["count"] = 1
        _copy_and_verify(source, stage, included)
        transcript_record = {"supplied": False}
        if transcript is not None:
            transcript_record = _copy_transcript(transcript, stage)

        # Detect source additions/removals/symlink changes during staging, then independently check
        # every source and destination hash.  A changed source is a refusal, not a mixed snapshot.
        if _plan_signature(_scan_plan(source)) != _plan_signature(plan):
            raise BuildError("source file/symlink selection changed during staging")
        for row in included:
            rel = _safe_relative(row["source_relative_path"])
            if _sha256(source / Path(rel)) != row["sha256"]:
                raise BuildError(f"source changed during staging: {rel}")
            if _sha256(stage / Path(row["artifact_relative_path"])) != row["sha256"]:
                raise BuildError(f"staged hash verification failed: {rel}")

        scan_finished = datetime.now(timezone.utc).isoformat()
        source_tree_digest = _plan_digest(plan)
        manifest: dict[str, Any] = {
            "artifact_schema": SCHEMA,
            "artifact_built": datetime.now(timezone.utc).isoformat(),
            "builder": BUILDER,
            "mode": mode,
            "source_commit": git["commit"],
            "source_branch": git["branch"],
            "uncommitted_paths": git["uncommitted_paths"],
            "included_fully": _fully_included_roots(exclusions),
            "excluded": exclusions,
            "source": {
                "root_name": source.name,
                "root_absolute_path": str(source),
                "root_realpath": str(source_real),
                "git_commit": git["commit"],
                "git_branch": git["branch"],
                "git_available": git["git_available"],
                "tree_dirty": git["tree_dirty"],
                "uncommitted_paths": git["uncommitted_paths"],
                "status_porcelain": git["status_porcelain"],
                "scan_started": scan_started,
                "scan_finished": scan_finished,
                "builder_sha256": _sha256(Path(__file__).resolve()),
                "source_tree_digest": source_tree_digest,
                "python": sys.version,
            },
            "test_transcript": transcript_record,
            "selection_rules": {
                "included_top_level": list(INCLUDED_TOP_LEVEL),
                "included_ext_roots": list(EXT_INCLUDED_ROOTS),
                "excluded_ext_roots": list(EXT_EXCLUDED_ROOTS),
                "private_paths": sorted(PRIVATE_PATHS),
                "never_follow_symlinks": True,
                "known_unrelated_sources": [
                    {
                        "source_relative_path": path,
                        "rule": rule,
                        "reason": reason,
                    }
                    for path, (rule, reason) in sorted(KNOWN_UNRELATED_SOURCES.items())
                ],
                "excluded_patterns": {
                    "cache_or_git": sorted(CACHE_NAMES),
                    "data_directories": sorted(DATA_DIR_NAMES),
                    "archives": sorted(ARCHIVE_SUFFIXES),
                    "archive_exceptions": sorted(SOURCE_ARCHIVE_EXCEPTIONS),
                    "checkpoints_or_models": sorted(CHECKPOINT_SUFFIXES),
                    "media": sorted(MEDIA_SUFFIXES),
                    "binary_or_data": sorted(NUMERIC_DATA_SUFFIXES),
                },
            },
            "included_files": included,
            "external_files": [transcript_record] if transcript_record["supplied"] else [],
            "exclusions": exclusions,
            "symlinks": symlinks,
            "verification": {
                "source_rescanned_after_copy": True,
                "included_source_and_destination_hashes_verified": True,
            },
        }
        _validate_manifest_paths(manifest)
        _write_json(stage / "artifact-manifest.json", manifest)
        _write_json(stage / "provenance.json", manifest["source"])
        (stage / "source-status.porcelain-v1.txt").write_text(
            "\n".join(git["status_porcelain"]) + ("\n" if git["status_porcelain"] else ""),
            encoding="utf-8",
        )
        _write_jsonl(stage / "included-files.jsonl", included)
        _write_jsonl(stage / "excluded-files.jsonl", exclusions)
        _write_jsonl(stage / "symlinks.jsonl", symlinks)
        (stage / "README-ARTIFACT.md").write_text(
            _readme(mode, transcript_record["supplied"]), encoding="utf-8"
        )

        # Claim the destination with mkdir: os.rename(stage, output) could replace a concurrent
        # empty directory on POSIX. Move validated children only after that no-replace claim.
        _publish_without_replacement(stage, output)
    except Exception:
        # Do not remove stage: leaving it is safer than destructive cleanup and preserves forensic
        # evidence for a failed local build.  The caller receives only a bounded error message.
        raise
    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="source project directory")
    parser.add_argument("--output", required=True, help="new directory artifact destination")
    parser.add_argument(
        "--mode", required=True, choices=("source-fidelity", "final-production"),
        help="review phase represented by the artifact",
    )
    parser.add_argument("--test-transcript", help="existing pytest transcript to include")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        output = build(args.source, args.output, args.mode, args.test_transcript)
    except BuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
