"""Build and verify the fail-closed native DataSphere payload."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import sys
import subprocess
import tarfile
import tempfile
from pathlib import Path

try:
    from datasphere.native.evaluator_identity import (IDENTITY_SCHEMA, family_bindings,
                                                       verify_bindings)
except ModuleNotFoundError:  # direct `python datasphere/native/contract.py` execution
    import importlib.util

    _identity_path = Path(__file__).with_name("evaluator_identity.py")
    _identity_spec = importlib.util.spec_from_file_location("_native_evaluator_identity", _identity_path)
    _identity = importlib.util.module_from_spec(_identity_spec)
    _identity_spec.loader.exec_module(_identity)
    IDENTITY_SCHEMA = _identity.IDENTITY_SCHEMA
    family_bindings = _identity.family_bindings
    verify_bindings = _identity.verify_bindings


# [Claude 2026-09-02 04:35 MSK: the allowlist is now base + per-family. Every job needs the runner,
# the contract, the shim and the patch set; only a dmc_gb job may contain dmc_gb's source, and no
# job may contain a clone it does not run. The families it was built for are recorded IN the
# archive manifest, so the remote verifier applies the same allowlist without being told.]
BASE_ALLOWED = (
    "datasphere/native/contract.py",
    "datasphere/native/evaluator_identity.py",
    "datasphere/native/configure_places365_val.py",
    "datasphere/native/families.json",
    "datasphere/native/family.py",
    "datasphere/native/measure_resources.py",
    "datasphere/native/normalize_curves.py",
    # [Claude 2026-09-08] family.py:421 imports this at RUNTIME via spec_from_file_location, so
    # every code path reaching _replay_gib -- check-memory and disk-requirement both -- dies with
    # FileNotFoundError inside the container without it. It went unnoticed because check-memory
    # used to be gated on NATIVE_HOST_PROFILE == "v100" and every previous run was on the
    # datasphere profile, so the path had never executed in a container. The first real host cell
    # found it in two minutes:
    #   FileNotFoundError: '/tmp/native-work/datasphere/native/plan_production.py'
    "datasphere/native/plan_production.py",
    "datasphere/native/robosuite-import-closure.json",
    "datasphere/native/rlvigen-source.json",
    "datasphere/native/run_probe.sh",
    "datasphere/native/source-lock.json",
    # [Claude 2026-09-08] `run_probe.sh` copies this to `$work/.vram-cap/sitecustomize.py` and puts
    # it on PYTHONPATH when NATIVE_VRAM_CAP_MIB is set, so the runner REQUIRES a member it did not
    # before -- which is exactly what RUNNER_CONTRACT exists to catch, bumped to 15 below. Omitting
    # it here would have made the cp fail inside the container after the whole bootstrap was paid
    # for, and under `set -e` that ends the job with no useful message. This is the same shape as
    # the watch_policy_health.py omission that cost a job on 2026-09-08.
    # [Claude 2026-09-08] run_probe.sh sources this before anything else and REFUSES if it is not
    # running in a container -- the guard that stops a job body apt-getting into a host's python.
    # A payload without it would make run_probe.sh warn and continue unguarded, so it is a member
    # and RUNNER_CONTRACT goes to 16.
    "datasphere/native/require_container.sh",
    "datasphere/native/vram_cap.py",
    "requirements-native.txt",
    # A hash INPUT for scripts/eval_provenance.py's evaluator revision, never an import: the remote
    # side reads its bytes and nothing else, so the single file ships without `rlgen/__init__.py`.
    # It is here because the stamp must come out identical whether it was computed locally or on the
    # remote -- that identity is the whole point of a revision stamp -- and because omitting it
    # raised "cannot stamp evaluator revision: missing rlgen/protocol.py" remotely, after the job
    # had paid for its bootstrap.  Note normalize_curves.py:62 records that `rlgen` is deliberately
    # NOT a payload package; that still holds.  This is one file shipped as data, not the package.
    "rlgen/protocol.py",
    "runnable/_shim",
    # Named explicitly although it sits inside runnable/_shim, because the package MUST be called
    # `models` -- ALDA's trainer does `from models.sac import ...` -- and FORBIDDEN_PARTS rejects a
    # `models` component in whatever part of a path no declaration names. It is about a kilobyte
    # and inert for every family but alda, so it ships in the base rather than being conditional.
    "runnable/_shim/alda_models/models",
    "scripts/check_checkpoint_finite.py",
    "scripts/eval_across_scenes.py",
    "scripts/eval_grid.py",
    "scripts/eval_provenance.py",
    "scripts/metrics.py",
    "scripts/preserve_intermediate_snapshot.py",
    "scripts/watch_divergence.py",
    "scripts/watch_policy_health.py",
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
# Bumped to 11 on 2026-09-05: both offline evaluator entry points import eval_provenance.py after
# extraction.  A payload built before it was allowlisted would otherwise spend remote bootstrap
# before failing an import, so the runner must reject that archive at the contract boundary.
# Bumped to 12 the same day: offline rows now require an evaluator revision, so the runner checks
# that the payload has the stamping path before it is allowed to measure a checkpoint.
# Bumped to 13 the same day: the runner now passes `--eval-scope` to eval_grid on BOTH evaluator
# paths, so endpoint rows and trajectory-stamp rows can be told apart in the record. run_probe.sh
# ships as a separate job input and is therefore always current, while the payload is a pinned
# archive -- so a payload built before that flag existed would meet a runner that passes it, and
# argparse would exit 2 after the bootstrap had already been paid for. This is the same drift that
# cost two jobs over SAVE_EVERY vs SAVE_EVERY_FRAMES; the contract is where it gets caught.
# Bumped to 14 on 2026-09-08: `run_measured` now launches scripts/watch_policy_health.py beside
# the stall watchdog, so the runner requires a payload member it did not require before. This is
# the exact case the note above describes, and it was nearly missed in the way that matters most:
# the first version of the launch was guarded by `[[ -f scripts/watch_policy_health.py ]]`, which
# would have turned a contract violation the runner refuses loudly into a SILENT no-op -- the
# `log_std` alert simply never starting on the container, with PRODUCTION-RUNBOOK stating it runs
# on every cell. An instrument that cannot run must never read as one that ran; building that
# failure into the instrument written to catch it is how it would have survived.
# Bumped to 15 on 2026-09-08: `run_probe.sh` installs `datasphere/native/vram_cap.py` as
# `sitecustomize` when NATIVE_VRAM_CAP_MIB is set, so the runner requires a payload member it did
# not require before. Same case as 14, and caught the same way -- by asking, before shipping,
# whether the runner now reads something the payload might not carry.
# Bumped to 16 on 2026-09-08: run_probe.sh sources
# `datasphere/native/require_container.sh` and refuses to run outside a container, so the runner
# requires another payload member it did not require before.
# Bumped to 17 on 2026-09-08: plan_production.py is now a member, because family.py imports it at
# runtime and the runner therefore requires it.
# Bumped to 18 on 2026-09-08: `run_probe.sh` changed two runtime behaviours the host side must
# agree with. It now (a) makes `--no-cache-dir` conditional on NATIVE_PIP_CACHE, which only means
# anything if the host bind-mounts /root/.cache/pip, and (b) REMOVES the `cell-active` marker when
# the cell exits, which the card watchers read to decide whether the card is still ours. A payload
# built before this paired with a host script after it would mount a cache the runner ignores; the
# reverse would leave the marker set forever and re-create the vacated-card false alarm. Neither
# fails loudly on its own, which is exactly what the contract number is for.
# Bumped to 19 on 2026-09-08: `run_probe.sh` can now SKIP the pip bootstrap entirely and run
# against a prebuilt venv, which it does when NATIVE_VENV is set -- and it refuses outright unless
# NATIVE_IMAGE_DIGEST is also forwarded, because the venv records the image it was built under and
# an unverifiable record is not the same as a good one. Both variables are set by
# run_on_production_host.sh and by nothing else, so a payload from before this paired with a host
# script from after it would mount a read-only venv the runner never activates and then try to pip
# install into a container that has one -- slow, confusing, and not a crash.
# NOT bumped to 20 on 2026-09-09 for the EGL renderer repair, and the reasoning is recorded because
# the criterion matters more than the number. `run_probe.sh` now writes the NVIDIA EGL ICD and runs
# `ldconfig`; `run_on_production_host.sh` injects `libnvidia-gpucomp`. That is a paired change, which
# usually earns a bump. The test for a bump is whether a mismatched pair fails SILENTLY, and here
# neither direction does: an old payload under the new wrapper gets Mesa and the renderer check
# refuses; a new payload under an old wrapper gets an unloadable NVIDIA vendor and the same check
# refuses, after NATIVE_EGL_DEPENDENCY_MISSING names the missing library. Both are loud, so the
# number stays where it is. Bumping reflexively would invalidate every built payload for no gain and
# would make the contract mean less each time it moved.
RUNNER_CONTRACT = 19


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
    # [Claude 2026-09-07] A `.gitignore` that upstream ships INSIDE an otherwise-forbidden
    # directory is source, not output. IBAC-SNI commits `toy-classification/results/.gitignore`,
    # and the source manifest requires it present -- so `verify_sources.py` demanded the file and
    # this builder refused it, two checkers disagreeing about one upstream placeholder. Narrow on
    # purpose: only this exact filename, which cannot carry result data.
    if Path(relative).name == ".gitignore":
        return None
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
    seen: set[Path] = set()

    def add(path: Path) -> None:
        if path not in seen:
            seen.add(path)
            members.append(path)

    for allowed in allowed_entries:
        path = source / allowed
        if not path.exists():
            fail(f"required payload member is absent: {allowed}")
        if path.is_file():
            add(path)
        else:
            # `.git` is SKIPPED here rather than left to trip FORBIDDEN_PARTS below. The clones
            # carry it -- it is what `scripts/deviations.py` diffs against, 296 MB of it -- and no
            # job needs a byte of it. Before this, restoring that metadata made every payload build
            # fail with "forbidden payload member: runnable/alda/.git/COMMIT_EDITMSG", which reads
            # like a smuggling attempt rather than "you kept your history".
                for child in sorted(
                    child for child in path.rglob("*")
                    if child.is_file() and not child.is_symlink()
                    and child.name != ".DS_Store"
                    and "__pycache__" not in child.parts
                    and ".git" not in child.parts
                    and child.suffix != ".pyc"):
                    add(child)
    return members


def _git_identity(source: Path) -> dict:
    """The commit this payload was built from, and whether the tree was clean.

    Best-effort by design: a source tree with no git (an extracted tarball, a fixture) still
    builds a valid payload, and saying "unknown" is honest where inventing a hash would not be.
    """
    def _run(*args: str) -> str | None:
        try:
            done = subprocess.run(["git", "-C", str(source), *args],
                                  capture_output=True, text=True, timeout=30)
        except Exception:
            return None
        return done.stdout.strip() if done.returncode == 0 else None

    commit = _run("rev-parse", "HEAD")
    if commit is None:
        return {"source_commit": "unknown", "source_dirty": "unknown"}
    status = _run("status", "--porcelain")
    if status is None:
        return {"source_commit": commit, "source_dirty": True}
    # Same exclusion as job.sh's ledger writer, for the same reason: `results/submissions.jsonl` is
    # untracked and is written by every submission, so once one job has been submitted this would
    # report dirty forever regardless of the tree. The two files listed here are outputs of the
    # provenance machinery itself and cannot describe the source it is recording.
    IGNORED = {"results/submissions.jsonl", "results/attempt-outcomes.json"}
    # Parse the PATH, not a fixed offset: `_run` strips the whole output, so porcelain's leading
    # status space is gone on the first line and `line[3:]` would drop a character of the path.
    return {"source_commit": commit,
            "source_dirty": bool([line for line in status.splitlines()
                                  if line.split(maxsplit=1)[-1].strip() not in IGNORED])}


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
        # [Claude 2026-09-08] Git identity, so every RESULT carries it transitively.
        #
        # `results/submissions.jsonl` records commit and dirtiness at SUBMIT time, which answers
        # "what did we launch". It does not travel with the artifact: a records file retrieved from
        # a job, read a month later, could not say which tree produced it. The payload manifest is
        # the one thing present in the container and referenced by every record's provenance, so it
        # is where this belongs. It is a between-waves change because it moves payload bytes.
        #
        # `source_dirty` is recorded rather than refused. A dirty build is legitimate for a probe
        # and illegitimate for a wave, and `production_gates.py::gate_source_tree_frozen` is where
        # that judgement already lives -- duplicating it here would put the same rule in two places
        # and let them disagree.
        **_git_identity(source),
    }
    # A source-only test fixture may intentionally omit the pinned RL-ViGen tree. Such an archive
    # remains buildable for generic contract tests, but it is explicitly unbound and cannot pass a
    # validation submission. Real production payloads have every requested family binding here.
    try:
        manifest["evaluator_identity_schema"] = IDENTITY_SCHEMA
        manifest["evaluator_bindings"] = family_bindings(source, families)
    except (KeyError, RuntimeError) as error:
        manifest["identity_unavailable"] = str(error)
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


def verify_payload(
    archive_path: Path,
    require_runner_contract: int | None = None,
    require_families: tuple[str, ...] = (),
    require_evaluator_identity: bool = False,
) -> None:
    with tarfile.open(archive_path, "r:gz") as archive:
        members = [member for member in archive.getmembers() if member.isfile()]
        names = [member.name.rstrip("/") for member in members]
        if len(names) != len(set(names)):
            fail("payload contains duplicate file members")
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
    missing_families = sorted(set(require_families) - set(families))
    if missing_families:
        fail(
            f"payload does not carry required family {', '.join(missing_families)} "
            f"(it declares {', '.join(families)}); rebuild with --families including it"
        )
    if require_evaluator_identity:
        if manifest.get("evaluator_identity_schema") != IDENTITY_SCHEMA:
            fail("payload has no supported evaluator identity schema; rebuild before validation")
        bindings = manifest.get("evaluator_bindings")
        if not isinstance(bindings, dict):
            fail("payload has no evaluator bindings; rebuild before validation")
        missing_bindings = sorted(set(require_families) - set(bindings))
        if missing_bindings:
            fail("payload has no evaluator binding for required family " + ", ".join(missing_bindings))
    declared_hashes = manifest.get("members")
    if isinstance(declared_hashes, dict):
        actual_names = set(names) - {"payload_manifest.json"}
        expected_names = set(declared_hashes)
        if actual_names != expected_names:
            missing = sorted(expected_names - actual_names)
            extra = sorted(actual_names - expected_names)
            fail(f"payload member manifest differs from archive (missing={missing}, extra={extra})")
        with tarfile.open(archive_path, "r:gz") as hash_archive:
            for member in hash_archive.getmembers():
                if not member.isfile() or member.name == "payload_manifest.json":
                    continue
                body = hash_archive.extractfile(member).read()
                digest = hashlib.sha256(body).hexdigest()
                if digest != declared_hashes.get(member.name):
                    fail(f"payload member hash differs: {member.name}")
    elif require_evaluator_identity:
        fail("payload has no member hash manifest")
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


def verify_evaluator_binding(
    archive_path: Path,
    source: Path,
    families: tuple[str, ...],
    rlvigen_archive: Path | None = None,
) -> None:
    """Compare the manifest with the current post-patch source closure.

    This command intentionally imports only evaluator_identity.py, which is standard-library-only;
    it is used after P1-P21 and before any Robosuite or family import.
    """
    verify_payload(archive_path, require_families=families, require_evaluator_identity=True)
    with tarfile.open(archive_path, "r:gz") as archive:
        member = archive.extractfile("payload_manifest.json")
        manifest = json.loads(member.read()) if member else {}
    verify_bindings(source, manifest, families, rlvigen_archive)


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


RECORD_EXECUTION_KINDS = {
    "preflight",
    "eval_only_validation",
    "training_production",
    "exploratory",
}
RECORD_DELIVERY_STATUSES = {
    "pending",
    "complete",
    "archive_only",
    "failed",
    "not_applicable",
    "empty_tolerated",
}
RECORD_DELIVERY_CHANNELS = {"external", "archive_internal"}


def _record_artifact(path: Path, root: Path) -> dict | None:
    if not path.is_file():
        return None
    body = path.read_bytes()
    try:
        name = path.relative_to(root).as_posix()
    except ValueError:
        name = path.name
    return {
        "path": name,
        "row_count": sum(bool(line.strip()) for line in body.splitlines()),
        "sha256": hashlib.sha256(body).hexdigest(),
    }


def _record_source_paths(root: Path) -> list[Path]:
    """Mirror run_probe.sh's declared concatenation order exactly."""
    return [
        root / "records.jsonl",
        *sorted(root.glob("offline_eval_*.jsonl")),
        *sorted(root.glob("cells/*/offline_eval_*.jsonl")),
    ]


def _record_inputs(root: Path) -> list[dict]:
    return [artifact for path in _record_source_paths(root)
            if (artifact := _record_artifact(path, root))]


def _jsonl_objects(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line_number, raw_line in enumerate(path.read_text().splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except (TypeError, ValueError) as error:
            raise ValueError(f"invalid_json path={path.name} line={line_number}") from error
        if not isinstance(row, dict):
            raise ValueError(f"invalid_json_row path={path.name} line={line_number} expected=object")
        rows.append(row)
    return rows


def _canonical_row(row: dict) -> bytes:
    row = dict(row)
    # Both fields are runner-added metadata. They are excluded from the source comparison, while
    # every ordinary measurement field remains exact. `_delivery_provenance` is added only after
    # comparison succeeds; `_run_provenance` is added earlier to offline rows by the collector.
    row.pop("_run_provenance", None)
    row.pop("_delivery_provenance", None)
    return json.dumps(row, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode() + b"\n"


def _canonical_jsonl(path: Path) -> list[bytes]:
    """Return the ordered semantic rows, ignoring only runner-added delivery metadata."""
    return [_canonical_row(row) for row in _jsonl_objects(path)]


def _canonical_sha256(rows: list[bytes]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(row)
    return digest.hexdigest()


def _stamp_canonical_artifact(artifact: dict, rows: list[bytes]) -> None:
    artifact["canonical_row_count"] = len(rows)
    artifact["canonical_sha256"] = _canonical_sha256(rows)


def _write_delivery_records(path: Path, rows: list[dict], provenance: dict) -> None:
    """Atomically add final delivery provenance to every delivered JSON object."""
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            for row in rows:
                stamped = dict(row)
                stamped["_delivery_provenance"] = provenance
                json.dump(stamped, handle, sort_keys=True, ensure_ascii=False)
                handle.write("\n")
        os.replace(temporary, path)
    except BaseException:
        if temporary is not None:
            try:
                temporary.unlink()
            except OSError:
                pass
        raise


def _write_json_atomically(path: Path, value: dict) -> None:
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False,
    ) as handle:
        temporary = Path(handle.name)
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, path)


def finalize_records(
    manifest_path: Path,
    records_out: Path | None = None,
    execution_status: int = 0,
    collection_status: int = 0,
    delivery_channel: str = "external",
) -> bool:
    """Finalize the JSONL delivery contract after all record sources are collected.

    The manifest is deliberately updated even for a failed delivery: the caller archives it and
    only then propagates the nonzero status.  Returning ``False`` means the artifact is not safe as
    a successful production/evaluation result (or contains malformed exploratory data).
    """
    if not manifest_path.is_file():
        fail(f"record finalization manifest is absent: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("finalization_schema") != 1:
        fail("run manifest has no supported finalization_schema=1")
    if manifest.get("record_delivery") not in RECORD_DELIVERY_STATUSES:
        fail(f"run manifest has unsupported record_delivery: {manifest.get('record_delivery')!r}")
    kind = manifest.get("execution_kind")
    if kind not in RECORD_EXECUTION_KINDS:
        fail(f"run manifest has unsupported execution_kind: {kind!r}")
    if delivery_channel not in RECORD_DELIVERY_CHANNELS:
        fail(f"unsupported record delivery channel: {delivery_channel!r}")

    root = manifest_path.parent
    output_artifact = _record_artifact(records_out, root) if records_out else None
    input_artifacts = _record_inputs(root)
    artifacts = {"inputs": input_artifacts, "expected": None, "output": output_artifact}
    manifest["record_artifacts"] = artifacts
    manifest["record_delivery_channel"] = delivery_channel
    manifest["record_delivery_error"] = None

    if kind == "preflight":
        manifest["record_delivery"] = "not_applicable"
        _write_json_atomically(manifest_path, manifest)
        return True

    required = kind in {"training_production", "eval_only_validation"}
    error: str | None = None
    expected_rows = 0
    valid_rows = 0
    if collection_status != 0:
        error = "collector_write_failed"
    elif execution_status != 0:
        error = "execution_failed"
    else:
        try:
            expected_sequence: list[bytes] = []
            for path, artifact in zip(
                (path for path in _record_source_paths(root) if path.is_file()), input_artifacts,
            ):
                rows = _canonical_jsonl(path)
                _stamp_canonical_artifact(artifact, rows)
                expected_sequence.extend(rows)
            expected_rows = len(expected_sequence)
            expected_hash = _canonical_sha256(expected_sequence)
            artifacts["expected"] = {
                "row_count": expected_rows,
                "canonical_sha256": expected_hash,
            }
            if records_out is None or not records_out.is_file():
                error = "missing_records_out"
            else:
                actual_objects = _jsonl_objects(records_out)
                actual_sequence = [_canonical_row(row) for row in actual_objects]
                valid_rows = len(actual_sequence)
                if output_artifact is not None:
                    _stamp_canonical_artifact(output_artifact, actual_sequence)
                actual_hash = _canonical_sha256(actual_sequence)
                if expected_sequence != actual_sequence:
                    error = (
                        "record_content_mismatch "
                        f"expected_rows={expected_rows} delivered_rows={valid_rows} "
                        f"expected_sha256={expected_hash} delivered_sha256={actual_hash}"
                    )
                elif valid_rows == 0:
                    error = "zero_rows"
                else:
                    provenance = {
                        "finalization_schema": 1,
                        "execution_kind": kind,
                        "record_delivery": (
                            "complete" if delivery_channel == "external" else "archive_only"
                        ),
                        "source_row_count": expected_rows,
                        "source_canonical_sha256": expected_hash,
                    }
                    try:
                        _write_delivery_records(records_out, actual_objects, provenance)
                        stamped_sequence = _canonical_jsonl(records_out)
                        if stamped_sequence != expected_sequence:
                            error = "delivery_stamp_changed_content"
                        else:
                            output_artifact = _record_artifact(records_out, root)
                            _stamp_canonical_artifact(output_artifact, stamped_sequence)
                            artifacts["output"] = output_artifact
                    except (OSError, ValueError) as failure:
                        error = f"delivery_stamp_failed {failure}"
        except ValueError as failure:
            error = str(failure)

    if error is not None:
        if (
            not required and execution_status == 0 and expected_rows == 0
            and error in {"missing_records_out", "zero_rows"}
        ):
            manifest["record_delivery"] = "empty_tolerated"
            manifest["record_delivery_error"] = error
            _write_json_atomically(manifest_path, manifest)
            return True
        manifest["record_delivery"] = "failed"
        manifest["record_delivery_error"] = error
        manifest["final_evaluation_marker"] = None
        if not manifest.get("failure_marker"):
            marker = "NATIVE_RECORD_DELIVERY_FAILED reason=" + error
            manifest["failure_marker"] = marker
        _write_json_atomically(manifest_path, manifest)
        return False

    manifest["record_delivery"] = (
        "complete" if delivery_channel == "external" else "archive_only"
    )
    manifest["record_rows"] = valid_rows
    _write_json_atomically(manifest_path, manifest)
    return True


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
    verify.add_argument("--require-families", default="",
                        help="comma-separated families the upcoming job will execute")
    verify.add_argument("--require-evaluator-identity", action="store_true",
                        help="require the versioned per-family identity and member hashes")
    verify.add_argument("--expect", action="append", default=[], metavar="PATH:MARKER",
                        help="assert a payload member contains this text; repeatable. Use it "
                             "after every build that carries an edit you are about to rely on.")
    binding = commands.add_parser("verify-evaluator-binding")
    binding.add_argument("--archive", type=Path, required=True)
    binding.add_argument("--source", type=Path, required=True)
    binding.add_argument("--families", required=True,
                         help="comma-separated families whose post-patch closures must match")
    binding.add_argument("--rlvigen-archive", type=Path, default=None)
    asset = commands.add_parser("check-asset")
    asset.add_argument("--asset", type=Path, required=True)
    asset.add_argument("--expected-count", type=int, required=True)
    asset.add_argument("--expected-sha256", required=True)
    closure = commands.add_parser("verify-robosuite-closure")
    closure.add_argument("--source", type=Path, required=True)
    closure.add_argument("--requirements", type=Path, required=True)
    closure.add_argument("--closure", type=Path, required=True)
    finalize = commands.add_parser("finalize-records")
    finalize.add_argument("--manifest", type=Path, required=True)
    finalize.add_argument("--records-out", type=Path, default=None)
    finalize.add_argument("--execution-status", type=int, default=0)
    finalize.add_argument("--collection-status", type=int, default=0)
    finalize.add_argument("--delivery-channel", choices=sorted(RECORD_DELIVERY_CHANNELS),
                          default="external")
    args = parser.parse_args(argv)
    try:
        if args.command == "build-payload":
            write_payload(args.source.resolve(), args.output.resolve(), args.run_command,
                          tuple(item.strip() for item in args.families.split(",") if item.strip()))
        elif args.command == "verify-payload":
            verify_payload(
                args.archive.resolve(),
                args.require_runner_contract,
                tuple(item.strip() for item in args.require_families.split(",") if item.strip()),
                args.require_evaluator_identity,
            )
            if args.expect:
                verify_contains(args.archive.resolve(), tuple(args.expect))
        elif args.command == "verify-evaluator-binding":
            verify_evaluator_binding(
                args.archive.resolve(),
                args.source.resolve(),
                tuple(item.strip() for item in args.families.split(",") if item.strip()),
                args.rlvigen_archive.resolve() if args.rlvigen_archive else None,
            )
        elif args.command == "verify-robosuite-closure":
            verify_robosuite_closure(args.source.resolve(), args.requirements.resolve(), args.closure.resolve())
        elif args.command == "finalize-records":
            if not finalize_records(
                args.manifest.resolve(),
                args.records_out.resolve() if args.records_out else None,
                args.execution_status,
                args.collection_status,
                args.delivery_channel,
            ):
                return 4
        else:
            check_asset(args.asset.resolve(), args.expected_count, args.expected_sha256)
    except ValueError as error:
        print(error, file=sys.stderr)
        # [Claude 2026-09-04: 4, not 2. argparse exits 2 on a malformed invocation, so while this
        # returned 2 a mistyped command and a FAILED CONTRACT were the same exit code -- and a
        # caller that only reads the status, as `for ... && echo PRESENT || echo MISSING` does,
        # reports a present marker as missing. That happened today and nearly triggered a payload
        # rebuild that was not needed. A check that could not run must never be readable as a
        # check that ran and failed.]
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
