"""Build and verify the candidate-only ALDA DataSphere source payload."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import tarfile
from pathlib import Path


# [Codex 2026-09-01 21:42 MSK: seal only ALDA Door's audited source boundary so it cannot inherit the unrelated SVEA archive]
ALLOWED = (
    "datasphere/alda/contract.py",
    "datasphere/alda/source-lock.json",
    "runnable/_launch/alda.sh",
    "runnable/_shim/wandb.py",
    "runnable/alda/scripts",
    "runnable/alda/trainers",
    "runnable/alda/common",
    "runnable/alda/autoencoders",
    "runnable/alda/disentangle",
    "runnable/alda/specs",
    "runnable/alda/door.xml",
    "runnable/alda/dmcontrol_generalization_benchmark/src/env/wrappers.py",
    "runnable/alda/dmcontrol_generalization_benchmark/src/env/dmc2gym/dmc2gym",
    "runnable/alda/dmcontrol_generalization_benchmark/src/utils.py",
    "third_party/alda/models",
    "RL-ViGen-upstream/envs/robosuiteVGB",
    "RL-ViGen-upstream/third_party/robosuite",
)
FORBIDDEN_NAMES = {"wandb_key.txt", ".netrc", "id_rsa", "id_ed25519"}
FORBIDDEN_PARTS = {"results", "logs", "checkpoints", "data", "datasets", "wandb", ".git", ".venv", "__pycache__"}


def fail(message: str) -> None:
    raise ValueError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_allowed(relative: str) -> bool:
    return any(relative == item or relative.startswith(item + "/") for item in ALLOWED)


def reject_secrets(source: Path) -> None:
    for path in source.rglob("*"):
        if path.name in FORBIDDEN_NAMES:
            fail(f"forbidden payload member in source: {path.relative_to(source)}")


def payload_members(source: Path) -> list[Path]:
    members: list[Path] = []
    for allowed in ALLOWED:
        path = source / allowed
        if not path.exists():
            fail(f"required ALDA payload member is absent: {allowed}")
        candidates = [path] if path.is_file() else sorted(child for child in path.rglob("*") if child.is_file())
        for child in candidates:
            relative = child.relative_to(source)
            if child.name == ".DS_Store" or child.suffix == ".pyc" or "__pycache__" in child.parts:
                continue
            if any(part in FORBIDDEN_PARTS for part in relative.parts):
                fail(f"forbidden payload member: {relative}")
            members.append(child)
    return members


def verify_source_lock(source: Path) -> dict:
    lock = json.loads((source / "datasphere/alda/source-lock.json").read_text())
    for relative, expected in lock["required_source_hashes"].items():
        path = source / relative
        if not path.is_file():
            fail(f"source lock member is absent: {relative}")
        if sha256(path) != expected:
            fail(f"source lock hash differs: {relative}")
    return lock


def write_payload(source: Path, output: Path, command: str) -> None:
    reject_secrets(source)
    if output.exists():
        fail(f"refusing to overwrite payload: {output}")
    lock = verify_source_lock(source)
    members = payload_members(source)
    manifest = {
        "command": command,
        "accepted_adaptations": lock["accepted_adaptations"],
        "required_source_hashes": lock["required_source_hashes"],
        "members": {str(path.relative_to(source)): sha256(path) for path in members},
    }
    with tarfile.open(output, "w:gz") as archive:
        for path in members:
            archive.add(path, arcname=str(path.relative_to(source)), recursive=False)
        encoded = json.dumps(manifest, sort_keys=True, indent=2).encode()
        info = tarfile.TarInfo("payload_manifest.json")
        info.size = len(encoded)
        archive.addfile(info, io.BytesIO(encoded))
    verify_payload(output)


def verify_payload(archive_path: Path) -> None:
    with tarfile.open(archive_path, "r:gz") as archive:
        names = [member.name.rstrip("/") for member in archive.getmembers() if member.isfile()]
    for name in names:
        if name == "payload_manifest.json":
            continue
        if not is_allowed(name):
            fail(f"undeclared payload member: {name}")
        if Path(name).name in FORBIDDEN_NAMES or any(part in FORBIDDEN_PARTS for part in Path(name).parts):
            fail(f"forbidden payload member: {name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build-payload")
    build.add_argument("--source", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--run-command", default="bash datasphere/alda/run_probe.sh")
    verify = commands.add_parser("verify-payload")
    verify.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "build-payload":
            write_payload(args.source.resolve(), args.output.resolve(), args.run_command)
        else:
            verify_payload(args.archive.resolve())
    except ValueError as error:
        print(error, file=__import__("sys").stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
