"""Dependency-free evaluator identity primitives shared by build and remote preflight."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from pathlib import Path


# Hoisted out of `evaluator_revision` so it is addressable: every one of these files must also be
# shippable, or the stamp raises on the remote side after the job has already paid for its
# bootstrap. `rlgen/protocol.py` is a hash input, not an import; shipping it alone is sufficient
# and no `rlgen/__init__.py` is needed.
#
# [Split 2026-09-05.] The revision used to be ONE hash over code and configuration together. That
# was right about under-sensitivity -- a descriptor edit really can change what is measured -- and
# wrong about consequences: every `families.json` edit invalidated every family already validated.
# Two stamps instead: evaluator source changes move `evaluator_code_revision`, while the resolved
# measurement scope moves `evaluator_scope_revision` and `evaluator_measurement_revision`. The
# retained config-revision API is a schema/semantics token, not a hash of training configuration.
#
# `CODE_MEMBERS` remains the identity of the COMMON evaluator harness. It is deliberately not a
# claim that these files are all the code which computes a row: each family has an additional
# closure below. The old implementation used this common term as the entire evaluator identity,
# which made a checkpoint-writing edit invalidate all seven evaluators while an edit to CTRL's
# actual `vec_env.py` went unnoticed. Use `evaluator_family_code_revision()` for validity decisions.
CODE_MEMBERS = (
    "scripts/eval_grid.py",
    "scripts/eval_across_scenes.py",
    "scripts/eval_provenance.py",
    "datasphere/native/evaluator_identity.py",
    "datasphere/native/normalize_curves.py",
    "scripts/metrics.py",
    "datasphere/native/rlvigen-source.json",
)
CONFIG_MEMBERS = ("datasphere/native/families.json",)
REVISION_MEMBERS = CODE_MEMBERS + CONFIG_MEMBERS

# Deliberately NOT hashed: `run_probe.sh` is uploaded separately, so hashing the payload's copy
# would stamp an identity the run did not have. Checkpoint bytes, host profile and effective
# training configuration are separate provenance facts carried per record. `CONFIG_MEMBERS` and
# `REVISION_MEMBERS` remain exported for payload/provenance coverage compatibility; they are not
# the source of family evaluator configuration identity.
#
# The seven paths actually selected by eval_grid.  These are source roots rather than an import
# graph: pickle globals, ALDA's factory and worker deserialisation add dynamic edges.  The
# exclusions below keep training drivers out, so checkpoint-writing changes do not relabel an
# evaluation of already-saved bytes.
EVALUATOR_FAMILIES = ("rlvigen", "dmc_gb", "idaac", "alda", "ppg", "ibac_sni", "ctrl")
FAMILY_RUNTIME_MEMBERS = {
    "rlvigen": (
        "RL-ViGen-upstream/algos",
        "RL-ViGen-upstream/wrappers",
        "RL-ViGen-upstream/envs/robosuiteVGB/robosuitevgb",
        "RL-ViGen-upstream/envs/robosuiteVGB/cfg/robo_config.yaml",
        "RL-ViGen-upstream/envs/robosuiteVGB/cfg/setting/robo_setting.yaml",
        # eval_across_scenes.py imports this file live; its action distribution and augmentations
        # therefore affect the measurement and belong in the static closure.
        "RL-ViGen-upstream/utils.py",
    ),
    "dmc_gb": (
        "runnable/dmc_gb/src/algorithms",
        "runnable/dmc_gb/src/env",
        "runnable/dmc_gb/src/utils.py",
        "runnable/dmc_gb/src/augmentations.py",
        "RL-ViGen-upstream/envs/robosuiteVGB/robosuitevgb",
        "RL-ViGen-upstream/envs/robosuiteVGB/cfg/robo_config.yaml",
    ),
    "idaac": (
        "runnable/idaac/ppo_daac_idaac",
        "runnable/_shim/no_tf",
        "ext/baselines/baselines",
        "RL-ViGen-upstream/envs/robosuiteVGB/robosuitevgb",
        "RL-ViGen-upstream/envs/robosuiteVGB/cfg/robo_config.yaml",
    ),
    "alda": (
        "runnable/alda/trainers",
        "runnable/alda/common",
        "runnable/alda/autoencoders",
        "runnable/alda/disentangle",
        "runnable/alda/dmcontrol_generalization_benchmark/src/env",
        "runnable/alda/dmcontrol_generalization_benchmark/src/utils.py",
        "runnable/alda/dmcontrol_generalization_benchmark/src/augmentations.py",
        "runnable/alda/specs/train_alda_robosuite_door.yaml",
        "third_party/alda/models",
        "runnable/_shim/alda_models/models",
        "RL-ViGen-upstream/envs/robosuiteVGB/robosuitevgb",
        "RL-ViGen-upstream/envs/robosuiteVGB/cfg/robo_config.yaml",
    ),
    "ppg": (
        "runnable/ppg/phasic_policy_gradient",
        # `phasic_policy_gradient/__init__.py` imports train.py unconditionally. The generic
        # training-driver exclusion below therefore has a family-specific evaluator exception.
        "runnable/ppg/phasic_policy_gradient/train.py",
        "RL-ViGen-upstream/envs/robosuiteVGB/robosuitevgb",
        "RL-ViGen-upstream/envs/robosuiteVGB/cfg/robo_config.yaml",
    ),
    "ibac_sni": (
        "runnable/ibac_sni/torch_rl/utils",
        "runnable/ibac_sni/torch_rl/torch_rl/torch_rl",
        "runnable/ibac_sni/torch_rl/model.py",
        "runnable/ibac_sni/torch_rl/bottleneck.py",
        "runnable/ibac_sni/torch_rl/ibac_sni_runtime.py",
        "RL-ViGen-upstream/envs/robosuiteVGB/robosuitevgb",
        "RL-ViGen-upstream/envs/robosuiteVGB/cfg/robo_config.yaml",
    ),
    "ctrl": (
        "runnable/ctrl/algo.py",
        "runnable/ctrl/models.py",
        "runnable/ctrl/buffer.py",
        "runnable/ctrl/vec_env.py",
        # [Claude 2026-09-06, CORRECTIONS #97] door.xml was here, and it should not have been.
        # scripts/deviations.py's own "untracked but not counted" list already calls it out as a
        # RUN ARTIFACT -- "a robosuite task model dumped at cwd during a run" -- not authored
        # source. Two jobs on two different payload archives both reported a ctrl evaluator
        # identity matching no local computation; a diagnostic job that hashes the remote
        # filesystem live (after ctrl's own training has run and robosuite has dumped its own
        # copy of this file) found the mismatch isolated to exactly this one member -- every other
        # of the 36 hashed files matched. Static source cannot be a file the environment overwrites
        # as a side effect of running; hashing it stamped "identity" with whatever robosuite
        # happened to write during that specific job, not with anything that changes only when the
        # code does.
        "runnable/_shim",
        "RL-ViGen-upstream/envs/robosuiteVGB/robosuitevgb",
        "RL-ViGen-upstream/envs/robosuiteVGB/cfg/robo_config.yaml",
    ),
}

_TRAINING_ONLY_RUNTIME_BASENAMES = {"train.py", "train_ppo.py", "evaluate.py", "evaluate_ppo.py"}
IDENTITY_SCHEMA = 2

# `families.json` remains a payload/training descriptor and is intentionally not an evaluator
# configuration hash input. The actual measurement configuration is the canonical scope stamped
# on every eval row; static evaluator-specific YAML/XML/config modules are already in each family's
# runtime closure. This token makes the retained config-revision API explicit without pretending
# that every training descriptor edit changes fixed-checkpoint evaluation.
EVALUATOR_CONFIG_SEMANTICS = "scope-attested-static-runtime-config-v1"

# A payload binds the static evaluator closure.  A row additionally binds the resolved measurement
# scope: endpoint versus curve, the exact regimes/scenes/sample sizes, device, and the policy rule.
# This is deliberately JSON/stdlib-only because it runs before pip and before evaluator imports.
SCOPE_FIELDS = (
    "family", "baseline", "task", "frame", "eval_scope", "regimes", "scenes", "episodes",
    "episode_seed", "seed", "device", "action_repeat", "frame_stack", "image_size",
    "episode_length", "deterministic_setting", "eval_policy_mode",
)
FAMILY_ALLOWED_BASELINES = {
    "rlvigen": ("drqv2", "svea", "drq", "sgqn", "curl"),
    "dmc_gb": ("rad", "soda"),
    "alda": ("alda",),
    "idaac": ("idaac",),
    "ppg": ("ppg",),
    "ibac_sni": ("ibac_sni",),
    "ctrl": ("ctrl",),
}
KNOWN_EVAL_SCOPES = ("endpoint", "curve")
KNOWN_REGIMES = ("train", "eval-easy", "eval-medium", "eval-hard")
FAMILY_EVAL_POLICY_MODE = {
    "rlvigen": "mode", "dmc_gb": "mode", "alda": "mode",
    "idaac": "sample", "ppg": "sample", "ibac_sni": "sample", "ctrl": "sample",
}


def family_eval_policy_mode(family: str) -> str:
    _validate_family(family)
    return FAMILY_EVAL_POLICY_MODE[family]


def policy_mode_for(family: str, baseline: str) -> str:
    """Return the action rule actually used by the evaluator, not a training setting."""
    _validate_family(family)
    if baseline not in FAMILY_ALLOWED_BASELINES[family]:
        raise ValueError(f"evaluator scope baseline {baseline!r} is not valid for family {family!r}")
    return family_eval_policy_mode(family)


def effective_deterministic_setting(family: str, requested: bool) -> dict[str, object]:
    """Resolve the backend-specific deterministic setting before evaluator setup/import."""
    _validate_family(family)
    if family == "ctrl":
        return {"backend": "jax", "mode": "seeded-prng", "enabled": True}
    return {"backend": "torch", "mode": "torch.use_deterministic_algorithms",
            "enabled": bool(requested)}


def _scope_sequence(value, field: str, cast):
    if isinstance(value, str):
        value = [item.strip() for item in value.split(",") if item.strip()]
    if not isinstance(value, (tuple, list)) or not value:
        raise ValueError(f"evaluator scope {field} is unresolved")
    try:
        return [cast(item) for item in value]
    except (TypeError, ValueError) as error:
        raise ValueError(f"evaluator scope {field} is unresolved") from error


def canonical_evaluation_scope(values: Mapping[str, object]) -> dict[str, object]:
    """Normalize the effective eval-grid arguments; reject omissions instead of inventing values."""
    missing = [field for field in SCOPE_FIELDS if field not in values]
    if missing:
        raise ValueError("evaluator scope is unresolved: missing " + ", ".join(missing))
    if set(values) != set(SCOPE_FIELDS):
        extra = sorted(set(values) - set(SCOPE_FIELDS))
        raise ValueError("evaluator scope has unknown fields: " + ", ".join(extra))
    family = str(values["family"])
    baseline = str(values["baseline"])
    _validate_family(family)
    if baseline not in FAMILY_ALLOWED_BASELINES[family]:
        raise ValueError(f"evaluator scope baseline {baseline!r} is not valid for family {family!r}")
    policy_mode = str(values["eval_policy_mode"])
    # [Claude 2026-09-07, DECISION-SHEET A25 addendum] Two scopes are resolvable, not one. The
    # family's own rule is the headline path and stays the default. `"mode"` is the deterministic
    # override `eval_grid.py --policy-mode mode` produces, which exists because the sampling /
    # deterministic divide is the fleet's only UNITS-class comparability split and two of A25's
    # fixed cross-group pairs straddle it.
    #
    # It is admitted HERE rather than waved through, because a scope that cannot be canonicalised
    # cannot be attested, and an un-attestable second pass would be evidence nothing could certify.
    # Note the asymmetry: `"mode"` is always resolvable because taking the mode is well defined for
    # every family, while a family whose native rule IS `mode` gains nothing from the override --
    # `family.py` therefore requests the second pass only for the four sampling families.
    if policy_mode not in (family_eval_policy_mode(family), "mode"):
        raise ValueError(f"evaluator scope eval_policy_mode is unresolved for {family}/{baseline}")
    deterministic = values["deterministic_setting"]
    expected_backend = "jax" if family == "ctrl" else "torch"
    expected_mode = "seeded-prng" if family == "ctrl" else "torch.use_deterministic_algorithms"
    if (not isinstance(deterministic, Mapping)
            or deterministic.get("backend") != expected_backend
            or deterministic.get("mode") != expected_mode
            or not isinstance(deterministic.get("enabled"), bool)):
        raise ValueError("evaluator scope deterministic_setting is unresolved")
    task = str(values["task"])
    if not task.strip():
        raise ValueError("evaluator scope task is unresolved")
    result = {
        "family": family,
        "baseline": baseline,
        "task": task,
        "frame": int(values["frame"]),
        "eval_scope": str(values["eval_scope"]),
        # Order is retained: the global placement RNG and emitted row order make it semantic.
        "regimes": _scope_sequence(values["regimes"], "regimes", str),
        "scenes": _scope_sequence(values["scenes"], "scenes", int),
        "episodes": int(values["episodes"]),
        "episode_seed": int(values["episode_seed"]),
        "seed": int(values["seed"]),
        "device": str(values["device"]),
        "action_repeat": int(values["action_repeat"]),
        "frame_stack": int(values["frame_stack"]),
        "image_size": int(values["image_size"]),
        "episode_length": int(values["episode_length"]),
        "deterministic_setting": {str(key): deterministic[key] for key in sorted(deterministic)},
        "eval_policy_mode": policy_mode,
    }
    if result["eval_scope"] not in KNOWN_EVAL_SCOPES:
        raise ValueError(f"evaluator scope eval_scope {result['eval_scope']!r} is unresolved")
    if any(regime not in KNOWN_REGIMES for regime in result["regimes"]):
        raise ValueError("evaluator scope contains an unknown regime")
    if any(scene < 0 or scene > 9 for scene in result["scenes"]):
        raise ValueError("evaluator scope scene must be between 0 and 9")
    if not result["device"].strip():
        raise ValueError("evaluator scope device is unresolved")
    if (result["frame"] < 0 or result["episodes"] <= 0 or result["action_repeat"] <= 0
            or result["frame_stack"] <= 0 or result["image_size"] <= 0
            or result["episode_length"] <= 0):
        raise ValueError("evaluator scope contains an invalid non-positive measurement value")
    json.dumps(result, sort_keys=True, separators=(",", ":"))
    return result


def scope_revision(scope: Mapping[str, object]) -> str:
    canonical = canonical_evaluation_scope(scope)
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def measurement_revision(static_family_revision: str, resolved_scope_revision: str) -> str:
    payload = {"static_family_revision": str(static_family_revision),
               "scope_revision": str(resolved_scope_revision)}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _validate_family(family: str) -> None:
    if family not in EVALUATOR_FAMILIES:
        raise ValueError(f"unknown evaluator family {family!r}")


def _runtime_tree_members(root: Path, relative: str) -> tuple[str, ...]:
    path = root / relative
    if not path.is_dir():
        return (relative,) if path.is_file() else ()
    files = []
    for candidate in path.rglob("*"):
        if not candidate.is_file() or candidate.suffix not in {".py", ".yaml", ".yml", ".xml"}:
            continue
        if candidate.name in _TRAINING_ONLY_RUNTIME_BASENAMES or candidate.name.endswith("_test.py"):
            continue
        # [Claude 2026-09-06] macOS's `tar` silently folds AppleDouble sidecar files
        # (`._<name>`, extended-attribute/resource-fork data) into the parent file's metadata on
        # extraction -- they never appear as visible files on this development machine. GNU tar on
        # the remote Linux container has no such concept and extracts them as literal, ordinary
        # files, and `._curl.py`'s suffix is still `.py`. First exercised for real by
        # bt18a8fjl3qrp5jv50g6 (2026-09-06): every one of ~30 "only in the fresh recomputation"
        # files this check found was a `._`-prefixed sidecar of a real member (e.g. `._curl.py`
        # beside `curl.py`), invisible on every machine this code had run on until it hit Linux.
        if candidate.name.startswith("._"):
            continue
        files.append(candidate.relative_to(root).as_posix())
    return tuple(sorted(files))


def evaluator_runtime_members(root: Path, family: str) -> tuple[str, ...]:
    _validate_family(family)
    members = list(CODE_MEMBERS)
    missing = []
    for relative in FAMILY_RUNTIME_MEMBERS[family]:
        expanded = _runtime_tree_members(root, relative)
        if not expanded:
            missing.append(relative)
        members.extend(expanded)
    if missing:
        raise RuntimeError("evaluator runtime manifest names missing source: " + ", ".join(missing))
    return tuple(sorted(set(members)))


def _selected_host_profile(root: Path) -> str:
    profile = os.environ.get("NATIVE_HOST_PROFILE", "datasphere")
    try:
        known_profiles = json.loads((root / "datasphere/native/families.json").read_text()).get(
            "_host_profiles", {})
    except (OSError, ValueError) as error:
        raise RuntimeError(f"cannot validate host profile: {error}") from error
    if profile not in known_profiles:
        raise RuntimeError(f"unknown host profile {profile!r}; known: {', '.join(sorted(known_profiles))}")
    return profile


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _digest_of(members, root: Path) -> str:
    # Validate the selector at the identity boundary, but never mix training-host choice into the
    # evaluator byte digest. An unknown profile remains an input error without making known
    # datasphere/v100 profiles different evaluator implementations.
    _selected_host_profile(root)
    digest = hashlib.sha256()
    for relative in members:
        path = root / relative
        if not path.is_file():
            raise RuntimeError(f"cannot stamp evaluator revision: missing {relative}")
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def evaluator_revision(root: Path, family: str | None = None) -> str:
    if family is not None:
        return evaluator_family_revision(root, family)
    return _combine_revisions(evaluator_code_revision(root), evaluator_config_revision(root))


def evaluator_code_revision(root: Path, family: str | None = None) -> str:
    if family is not None:
        return evaluator_family_code_revision(root, family)
    return _digest_of(CODE_MEMBERS, root)


def evaluator_config_revision(root: Path, family: str | None = None) -> str:
    if family is not None:
        return evaluator_family_config_revision(root, family)
    _selected_host_profile(root)
    payload = {
        "identity_schema": IDENTITY_SCHEMA,
        "semantics": EVALUATOR_CONFIG_SEMANTICS,
        "families": list(EVALUATOR_FAMILIES),
        "scope_fields": list(SCOPE_FIELDS),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def evaluator_family_code_revision(root: Path, family: str) -> str:
    return _digest_of(evaluator_runtime_members(root, family), root)


def evaluator_family_config_revision(root: Path, family: str) -> str:
    _validate_family(family)
    _selected_host_profile(root)
    payload = {
        "identity_schema": IDENTITY_SCHEMA,
        "semantics": EVALUATOR_CONFIG_SEMANTICS,
        "family": family,
        "scope_fields": list(SCOPE_FIELDS),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def evaluator_family_revision(root: Path, family: str) -> str:
    return _combine_revisions(evaluator_family_code_revision(root, family),
                              evaluator_family_config_revision(root, family))


def _combine_revisions(code_revision: str, config_revision: str) -> str:
    payload = str(code_revision) + "\0" + str(config_revision)
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def runtime_member_hashes(root: Path, family: str) -> dict[str, str]:
    return {relative: sha256_file(root / relative)
            for relative in evaluator_runtime_members(root, family)}


def _rlvigen_pin(root: Path) -> dict[str, str]:
    try:
        pin = json.loads((root / "datasphere/native/rlvigen-source.json").read_text())
        return {"sha256": str(pin["sha256"]), "commit": str(pin["commit"])}
    except (OSError, ValueError, KeyError) as error:
        raise RuntimeError(f"cannot read pinned RL-ViGen source identity: {error}") from error


def family_binding(root: Path, family: str) -> dict:
    pin = _rlvigen_pin(root)
    return {
        "code_revision": evaluator_family_code_revision(root, family),
        "config_revision": evaluator_family_config_revision(root, family),
        "revision": evaluator_family_revision(root, family),
        "runtime_members": runtime_member_hashes(root, family),
        "rlvigen_archive_sha256": pin["sha256"],
        "rlvigen_commit": pin["commit"],
    }


def family_bindings(root: Path, families: tuple[str, ...]) -> dict[str, dict]:
    return {family: family_binding(root, family) for family in families}


def verify_bindings(root: Path, manifest: dict, families: tuple[str, ...],
                    rlvigen_archive: Path | None = None) -> None:
    if manifest.get("evaluator_identity_schema") != IDENTITY_SCHEMA:
        raise ValueError("payload has no supported evaluator identity schema")
    bindings = manifest.get("evaluator_bindings")
    if not isinstance(bindings, dict):
        raise ValueError("payload has no evaluator bindings")
    expected_pin = _rlvigen_pin(root)
    if rlvigen_archive is not None:
        if not rlvigen_archive.is_file():
            raise ValueError(f"RL-ViGen archive is absent: {rlvigen_archive}")
        actual = sha256_file(rlvigen_archive)
        if actual != expected_pin["sha256"]:
            raise ValueError(f"RL-ViGen archive hash {actual} differs from pinned {expected_pin['sha256']}")
    for family in families:
        if family not in bindings:
            raise ValueError(f"payload has no evaluator binding for required family {family}")
        actual = bindings[family]
        expected = family_binding(root, family)
        if actual.get("runtime_members") != expected["runtime_members"]:
            raise ValueError(f"evaluator runtime member hash mismatch for {family}")
        for field in ("code_revision", "config_revision", "revision",
                      "rlvigen_archive_sha256", "rlvigen_commit"):
            if actual.get(field) != expected[field]:
                raise ValueError(f"evaluator {field} mismatch for {family}")
