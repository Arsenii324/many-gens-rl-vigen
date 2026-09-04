"""Build and verify the fail-closed native DataSphere payload."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import sys
import tarfile
from pathlib import Path


# [Claude 2026-09-02 04:35 MSK: the allowlist is now base + per-family. Every job needs the runner,
# the contract, the shim and the patch set; only a dmc_gb job may contain dmc_gb's source, and no
# job may contain a clone it does not run. The families it was built for are recorded IN the
# archive manifest, so the remote verifier applies the same allowlist without being told.]
BASE_ALLOWED = (
    "datasphere/native/contract.py",
    "datasphere/native/configure_places365_val.py",
    "datasphere/native/families.json",
    "datasphere/native/family.py",
    "datasphere/native/measure_resources.py",
    "datasphere/native/normalize_curves.py",
    "datasphere/native/robosuite-import-closure.json",
    "datasphere/native/rlvigen-source.json",
    "datasphere/native/run_probe.sh",
    "datasphere/native/source-lock.json",
    "requirements-native.txt",
    "runnable/_shim",
    # Named explicitly although it sits inside runnable/_shim, because the package MUST be called
    # `models` -- ALDA's trainer does `from models.sac import ...` -- and FORBIDDEN_PARTS rejects a
    # `models` component in whatever part of a path no declaration names. It is about a kilobyte
    # and inert for every family but alda, so it ships in the base rather than being conditional.
    "runnable/_shim/alda_models/models",
    "scripts/check_checkpoint_finite.py",
    "scripts/eval_across_scenes.py",
    "scripts/eval_grid.py",
    "scripts/metrics.py",
    "scripts/preserve_intermediate_snapshot.py",
    "scripts/watch_divergence.py",
    "setup/apply_patches.py",
)
DEFAULT_FAMILIES = ("rlvigen",)
# [Claude 2026-09-02 06:45 MSK: run_probe.sh is uploaded as a separate job input, so the runner is
# always current while the payload is a pinned archive from whenever it was built. Job
# bt1p2nhbap9p3ih73vvg spent a full bootstrap and about 33 RUB discovering that: the runner had
# started calling family.py and the payload predated it. Bump this whenever the runner begins to
# require a payload member it did not require before; the runner refuses a mismatch immediately
# after extraction instead of eight minutes later.]
# Bumped to 9 on 2026-09-02: run_probe.sh now reads datasphere/native/rlvigen-source.json to
# verify the shipped RL-ViGen archive before extracting it. A payload built before that file
# existed would leave the runner reading a path that is not there, at the point where it has just
# stopped cloning -- i.e. with no tree at all and no useful error.
RUNNER_CONTRACT = 10


def family_members(source: Path, families: tuple[str, ...]) -> tuple[str, ...]:
    descriptors = json.loads((source / "datasphere/native/families.json").read_text())
    members: list[str] = []
    for family in families:
        if family not in descriptors or family.startswith("_"):
            fail(f"unknown payload family: {family}")
        members.extend(descriptors[family]["payload_members"])
    return tuple(members)


def allowed_for(source: Path, families: tuple[str, ...]) -> tuple[str, ...]:
    return BASE_ALLOWED + family_members(source, families)
FORBIDDEN_NAMES = {"wandb_key.txt", ".netrc", "id_rsa", "id_ed25519"}
FORBIDDEN_PARTS = {"results", "logs", "models", "data", "wandb", ".git", ".venv", "__pycache__"}


def fail(message: str) -> None:
    raise ValueError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_allowed(relative: str, allowed: tuple[str, ...]) -> bool:
    return permitting_entry(relative, allowed) is not None


def permitting_entry(relative: str, allowed: tuple[str, ...]) -> str | None:
    """The most specific declared entry that admits this member, if any."""
    matches = [item for item in allowed if relative == item or relative.startswith(item + "/")]
    return max(matches, key=len) if matches else None


# [Claude 2026-09-02 10:00 MSK: the forbidden-part check applies to the part of a path the
# declaration did NOT name. `models` is forbidden because `runnable/idaac/models/` is where a run
# writes its agents; but `third_party/alda/models` IS ALDA's source package and is declared as a
# payload member by name. Testing the remainder after the declared prefix keeps the guard against
# an undeclared results directory while letting a declared source directory through.]
def forbidden_remainder(relative: str, allowed: tuple[str, ...]) -> str | None:
    entry = permitting_entry(relative, allowed)
    remainder = relative[len(entry) + 1:] if entry and relative != entry else relative
    if Path(relative).name in FORBIDDEN_NAMES:
        return Path(relative).name
    for part in Path(remainder).parts:
        if part in FORBIDDEN_PARTS:
            return part
    return None


def reject_forbidden_source(source: Path) -> None:
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        if path.name in FORBIDDEN_NAMES:
            fail(f"forbidden payload member in source: {relative}")


def payload_members(source: Path, allowed_entries: tuple[str, ...]) -> list[Path]:
    members: list[Path] = []
    for allowed in allowed_entries:
        path = source / allowed
        if not path.exists():
            fail(f"required payload member is absent: {allowed}")
        if path.is_file():
            members.append(path)
        else:
            # `.git` is SKIPPED here rather than left to trip FORBIDDEN_PARTS below. The clones
            # carry it -- it is what `scripts/deviations.py` diffs against, 296 MB of it -- and no
            # job needs a byte of it. Before this, restoring that metadata made every payload build
            # fail with "forbidden payload member: runnable/alda/.git/COMMIT_EDITMSG", which reads
            # like a smuggling attempt rather than "you kept your history".
            members.extend(sorted(
                child for child in path.rglob("*")
                if child.is_file() and not child.is_symlink()
                and child.name != ".DS_Store"
                and "__pycache__" not in child.parts
                and ".git" not in child.parts
                and child.suffix != ".pyc"))
    return members


def write_payload(source: Path, output: Path, command: str, families: tuple[str, ...] = DEFAULT_FAMILIES) -> None:
    reject_forbidden_source(source)
    members = payload_members(source, allowed_for(source, families))
    if output.exists():
        fail(f"refusing to overwrite payload: {output}")
    source_lock = json.loads((source / "datasphere/native/source-lock.json").read_text())
    manifest = {
        "command": command,
        "runner_contract": RUNNER_CONTRACT,
        "families": list(families),
        "accepted_adaptations": source_lock["accepted_adaptations"],
        "nested_repository_commits": source_lock["nested_repository_commits"],
        "members": {str(path.relative_to(source)): sha256(path) for path in members},
    }
    with tarfile.open(output, "w:gz") as archive:
        for path in members:
            archive.add(path, arcname=str(path.relative_to(source)), recursive=False)
        encoded = json.dumps(manifest, sort_keys=True, indent=2).encode()
        info = tarfile.TarInfo("payload_manifest.json")
        info.size = len(encoded)
        archive.addfile(info, __import__("io").BytesIO(encoded))
    # [Claude 2026-09-02 10:05 MSK: a payload that fails its own verification must not survive on
    # disk. It did once, and the next build then refused to overwrite it -- so the failure looked
    # like a naming problem rather than the allowlist violation it was.]
    try:
        verify_payload(output)
    except ValueError:
        output.unlink(missing_ok=True)
        raise


def verify_contains(archive_path: Path, expectations: tuple[str, ...]) -> None:
    """Assert that named members actually CONTAIN given text. `path:marker` per expectation.

    [Claude 2026-09-04] A payload's version number certifies WHEN it was built, never WHAT it
    contains, and every job config names it by filename. `cfg-metrics-probe-ctrl-ppg-v66` was
    submitted against a payload built before the very edit it existed to validate; the archive
    built, verified, uploaded and would have run green, and the green would have been read as
    covering code that was not in it. A passing test that never ran the code is worse than a
    failing one, because nothing looks wrong afterwards.

    `verify_payload` cannot catch this: its job is that every member is DECLARED, which a stale
    archive satisfies perfectly. This is the complementary check and it is deliberately dumb --
    a substring, named by the caller who just made the edit, because the caller is the only one
    who knows which identifier is new.
    """
    wanted: dict[str, list[str]] = {}
    for item in expectations:
        path, _, marker = item.partition(":")
        if not marker:
            fail(f"--expect takes path:marker, got {item!r}")
        wanted.setdefault(path, []).append(marker)
    with tarfile.open(archive_path, "r:gz") as archive:
        present = set(archive.getnames())
        for path, markers in wanted.items():
            if path not in present:
                fail(f"{path} is not in the payload at all")
            member = archive.extractfile(path)
            body = member.read().decode("utf-8", "replace") if member else ""
            for marker in markers:
                if marker not in body:
                    fail(f"{path} is in the payload but does not contain {marker!r} -- the "
                         "archive predates that edit; rebuild before submitting")
                print(f"  contains  {path}  <- {marker}")


def verify_payload(archive_path: Path, require_runner_contract: int | None = None) -> None:
    with tarfile.open(archive_path, "r:gz") as archive:
        names = [member.name.rstrip("/") for member in archive.getmembers() if member.isfile()]
        manifest_member = archive.extractfile("payload_manifest.json") if "payload_manifest.json" in archive.getnames() else None
        manifest = json.loads(manifest_member.read()) if manifest_member else {}
        families = tuple(manifest.get("families") or DEFAULT_FAMILIES)
        descriptor_member = archive.extractfile("datasphere/native/families.json") if "datasphere/native/families.json" in archive.getnames() else None
        descriptors = json.loads(descriptor_member.read()) if descriptor_member else {}
    if require_runner_contract is not None:
        found = manifest.get("runner_contract")
        if found != require_runner_contract:
            fail(
                f"payload was built for runner contract {found!r} but this runner needs "
                f"{require_runner_contract}; rebuild the payload before submitting"
            )
    allowed = list(BASE_ALLOWED)
    for family in families:
        if family in descriptors:
            allowed.extend(descriptors[family]["payload_members"])
        elif family == "rlvigen":
            allowed.append("runnable/_launch/rlvigen.sh")
        else:
            fail(f"payload declares a family its own descriptor file does not: {family}")
    allowed_entries = tuple(allowed)
    for name in names:
        if name == "payload_manifest.json":
            continue
        if not is_allowed(name, allowed_entries):
            fail(f"undeclared payload member: {name}")
        offending = forbidden_remainder(name, allowed_entries)
        if offending:
            fail(f"forbidden payload member: {name} (contains {offending})")


def asset_digest(asset: Path) -> tuple[int, str]:
    files = sorted(path for path in asset.rglob("*.jpg") if path.is_file())
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(asset).as_posix().encode() + b"\0")
        digest.update(bytes.fromhex(sha256(path)))
    return len(files), digest.hexdigest()


def check_asset(asset: Path, expected_count: int, expected_sha256: str) -> None:
    if not asset.is_dir():
        fail(f"Places365 validation asset is absent: {asset}")
    count, digest = asset_digest(asset)
    if count != expected_count:
        fail(f"Places365 validation image count {count} != expected {expected_count}")
    if digest != expected_sha256:
        fail("Places365 validation asset hash differs from the declared private asset")


# [Codex 2026-09-01 15:20 MSK: fail locally and remotely when the audited Robosuite import graph no longer matches its exact dependency closure]
def verify_robosuite_closure(source: Path, requirements_path: Path, closure_path: Path) -> None:
    closure = json.loads(closure_path.read_text())
    requirements = {
        line.strip()
        for line in requirements_path.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith(("#", "--"))
    }
    audited = closure["audited_source_files"]
    for relative, expected_hash in audited.items():
        path = source / relative
        if not path.is_file():
            fail(f"audited closure source is absent: {relative}")
        if sha256(path) != expected_hash:
            fail(f"audited closure source hash differs: {relative}")
    for entry in closure["exceptional_imports"]:
        relative = entry["source"]
        tree = ast.parse((source / relative).read_text(), filename=relative)
        imports = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            for alias in (node.names if isinstance(node, ast.Import) else ())
        }
        imports.update(
            node.module.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module
        )
        if entry["module"] not in imports:
            fail(f"audited closure import is absent: {entry['module']} in {relative}")
        if entry["requirement"] not in requirements:
            fail(f"missing exact closure requirement: {entry['requirement']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build-payload")
    build.add_argument("--source", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--run-command", default="bash datasphere/native/run_probe.sh")
    build.add_argument("--families", default="rlvigen")
    verify = commands.add_parser("verify-payload")
    verify.add_argument("--archive", type=Path, required=True)
    verify.add_argument("--require-runner-contract", type=int, default=None)
    verify.add_argument("--expect", action="append", default=[], metavar="PATH:MARKER",
                        help="assert a payload member contains this text; repeatable. Use it "
                             "after every build that carries an edit you are about to rely on.")
    asset = commands.add_parser("check-asset")
    asset.add_argument("--asset", type=Path, required=True)
    asset.add_argument("--expected-count", type=int, required=True)
    asset.add_argument("--expected-sha256", required=True)
    closure = commands.add_parser("verify-robosuite-closure")
    closure.add_argument("--source", type=Path, required=True)
    closure.add_argument("--requirements", type=Path, required=True)
    closure.add_argument("--closure", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "build-payload":
            write_payload(args.source.resolve(), args.output.resolve(), args.run_command,
                          tuple(item.strip() for item in args.families.split(",") if item.strip()))
        elif args.command == "verify-payload":
            verify_payload(args.archive.resolve(), args.require_runner_contract)
            if args.expect:
                verify_contains(args.archive.resolve(), tuple(args.expect))
        elif args.command == "verify-robosuite-closure":
            verify_robosuite_closure(args.source.resolve(), args.requirements.resolve(), args.closure.resolve())
        else:
            check_asset(args.asset.resolve(), args.expected_count, args.expected_sha256)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
