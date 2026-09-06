"""Small, dependency-light provenance helpers used by the offline evaluators.

These helpers deliberately record facts at the environment boundary.  An observation hash is
useful for detecting a changed stream, but it is not a substitute for the realized object pose;
the latter is what permits a later performance-versus-placement analysis.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import deque
from pathlib import Path

import numpy as np

from datasphere.native.evaluator_identity import (
    CODE_MEMBERS,
    CONFIG_MEMBERS,
    EVALUATOR_FAMILIES,
    FAMILY_RUNTIME_MEMBERS,
    REVISION_MEMBERS,
    canonical_evaluation_scope,
    effective_deterministic_setting,
    evaluator_code_revision,
    evaluator_config_revision,
    evaluator_family_code_revision,
    evaluator_family_config_revision,
    evaluator_family_revision,
    evaluator_revision,
    evaluator_runtime_members,
    family_eval_policy_mode,
    measurement_revision,
    policy_mode_for,
    scope_revision,
)


# Canonical evaluator identity lives in datasphere.native.evaluator_identity. This module keeps
# only provenance-specific helpers; the import is near the module boundary rather than a late
# re-export so a second local identity implementation cannot silently return.
def _json_value(value):
    """Convert numpy scalars/arrays and nested mappings to stable JSON values."""
    if isinstance(value, dict):
        return {str(k): _json_value(value[k]) for k in sorted(value)}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


def runtime_import_manifest(root: Path, family: str) -> dict:
    """Record repository-local modules that this fresh evaluator process actually loaded.

    Static closures protect the gate before a job is run.  Pickle globals, ALDA's factory and
    worker deserialisation are dynamic edges that source inspection cannot honestly prove away, so
    every record also retains the observed import tail for the job reviewer.  It is evidence, not
    an untested allowlist: the validation ledger cannot claim this check happened until the job's
    captured manifest was examined.
    """
    declared = set(evaluator_runtime_members(root, family))
    observed = {}
    for module_name, module in sorted(sys.modules.items()):
        filename = getattr(module, "__file__", None)
        if not filename:
            continue
        try:
            relative = Path(filename).resolve().relative_to(root.resolve()).as_posix()
        except (OSError, ValueError):
            continue
        # Python normally exposes a .py source file here.  If only bytecode is present, retain its
        # path rather than inventing a source path; that is precisely a reviewable deviation.
        observed[module_name] = relative
    unlisted = sorted(set(observed.values()).difference(declared))
    encoded = json.dumps(observed, sort_keys=True, separators=(",", ":"))
    return {
        "module_files": observed,
        "module_files_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        "unlisted_local_files": unlisted,
    }


def placement_hash(placement: dict) -> str:
    """Hash canonical realized placement data, not an observation proxy."""
    import json
    payload = json.dumps(_json_value(placement), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def find_realized_placement(root):
    """Find the VGBWrapper's post-reset placement through known wrapper links.

    The evaluator families use several unrelated wrapper stacks.  This bounded walk follows only
    wrapper/container links and refuses to invent a placement when a stack does not expose one.
    """
    queue = deque([root])
    seen = set()
    links = ("env", "_env", "_gym_env", "gym_env", "venv", "_venv", "unwrapped")
    while queue:
        node = queue.popleft()
        if node is None or id(node) in seen:
            continue
        seen.add(id(node))
        value = getattr(node, "last_initial_placement", None)
        if isinstance(value, dict):
            return _json_value(value)
        for attr in links:
            try:
                child = getattr(node, attr, None)
            except Exception:
                child = None
            if child is not None and child is not node:
                queue.append(child)
        # CTRL's small vector env stores the actual gym envs in this list.
        for attr in ("envs", "_envs"):
            try:
                children = getattr(node, attr, None)
            except Exception:
                children = None
            if isinstance(children, (list, tuple)):
                queue.extend(children)
    return None


def completed_episode_diagnostics(root, policy, episodes):
    """Return the most recent completed environment summaries, with derived hashes."""
    queue = deque([root])
    seen = set()
    links = ("env", "_env", "_gym_env", "gym_env", "venv", "_venv", "unwrapped")
    found = None
    while queue:
        node = queue.popleft()
        if node is None or id(node) in seen:
            continue
        seen.add(id(node))
        value = getattr(node, "episode_diagnostics", None)
        if isinstance(value, list):
            found = value
            break
        for attr in links:
            try:
                child = getattr(node, attr, None)
            except Exception:
                child = None
            if child is not None and child is not node:
                queue.append(child)
        for attr in ("envs", "_envs"):
            try:
                children = getattr(node, attr, None)
            except Exception:
                children = None
            if isinstance(children, (list, tuple)):
                queue.extend(children)
    # Some legitimate family adapters cross a vector/subprocess boundary that does not expose the
    # VGBWrapper object.  Do not turn an optional diagnostic into a discarded evaluation; make its
    # absence explicit in every episode record.  A *partial* list is different: it proves data was
    # lost within a reachable path and remains an error.
    if found is None:
        # [2026-09-05] Fail CLOSED when this is a production measurement, tolerant otherwise.
        #
        # External review 10: "No row should count as a paired-condition result unless those
        # physical diagnostics exist." That is right, and it is the one loss that cannot be
        # repaired after a fleet finishes -- realized placement, reward components, clipping rates
        # and termination reason are gone for good.
        #
        # It was tolerant because I feared it would kill families whose wrappers sit behind a
        # vector boundary. That fear is now MEASURED AWAY: ppg, ctrl, idaac, ibac_sni and dmc_gb all
        # return complete diagnostics on real environments. So closing it costs nothing today and
        # buys a guarantee -- and if `alda` or the RL-ViGen five turn out not to expose them, a
        # failed validation cell is exactly how we should find that out, rather than a fleet of rows
        # that quietly say `false`.
        #
        # Keyed on ENDPOINT_EVAL, which production_env sets, so a cheap exploratory probe keeps the
        # tolerant behaviour and production cannot inherit the probe's leniency by omission.
        if os.environ.get("RLGEN_REQUIRE_DIAGNOSTICS",
                          os.environ.get("ENDPOINT_EVAL", "0")) == "1":
            raise RuntimeError(
                "no environment diagnostics were reachable, and this is a production measurement: "
                "a row without realized placement cannot support a paired-condition claim. Set "
                "RLGEN_REQUIRE_DIAGNOSTICS=0 to record it anyway as an explicit exploratory choice")
        return [{"diagnostics_available": False, "policy_scale": policy}
                for _ in range(episodes)]
    if len(found) < episodes:
        raise RuntimeError(f"completed {episodes} episodes but only {len(found or [])} "
                           "environment diagnostics were exposed")
    required = {"episode_length", "termination_reason", "reward_sum", "reward_mean",
                "reward_min", "reward_max", "initial_placement", "applied_mode",
                "applied_scene_id", "action_clip_rate_coordinate", "action_clip_rate_vector",
                "action_raw_executed_l1"}
    output = []
    for item in found[-episodes:]:
        missing = sorted(required.difference(item))
        if missing:
            raise RuntimeError("episode diagnostics missing required fields: " + ", ".join(missing))
        row = dict(item)
        row["diagnostics_available"] = True
        row["placement_hash"] = placement_hash(row["initial_placement"])
        row["policy_scale"] = policy
        output.append(row)
    return output


def action_bounds(root, default_dim=7):
    """Return the normalized action bounds exposed by a family wrapper."""
    low, high, _source = _action_bounds(root, default_dim=default_dim)
    return low, high


def _action_bounds(root, default_dim=7):
    """Return bounds and whether they were observed on a wrapper, not assumed."""
    queue = deque([root])
    seen = set()
    links = ("env", "_env", "_gym_env", "gym_env", "venv", "_venv", "unwrapped")
    while queue:
        node = queue.popleft()
        if node is None or id(node) in seen:
            continue
        seen.add(id(node))
        try:
            space = getattr(node, "action_space", None)
            low_value = getattr(space, "low", None) if space is not None else None
            high_value = getattr(space, "high", None) if space is not None else None
            if low_value is None or high_value is None:
                raise ValueError("action space has no numeric bounds")
            low = np.asarray(low_value, dtype=float)
            high = np.asarray(high_value, dtype=float)
            if (low.size and high.size and low.shape == high.shape and
                    np.isfinite(low).all() and np.isfinite(high).all()):
                return low, high, "action_space"
        except Exception:
            pass
        for attr in links:
            try:
                child = getattr(node, attr, None)
            except Exception:
                child = None
            if child is not None and child is not node:
                queue.append(child)
        # gym3's ConcatEnv keeps Gym wrappers in `envs` and exposes only `ac_space` itself.  Walking
        # the members reaches the VGB action_space without confusing gym3's abstract TensorType
        # (which has no numeric low/high) with an observed bound.
        for attr in ("envs", "_envs"):
            try:
                children = getattr(node, attr, None)
            except Exception:
                children = None
            if isinstance(children, (list, tuple)):
                queue.extend(children)
    return -np.ones(default_dim), np.ones(default_dim), "normalized_fallback"


def _action_array(raw_action):
    """Convert one action or a batch of actions to (N, action_dim), without changing values."""
    if hasattr(raw_action, "detach"):
        raw_action = raw_action.detach().cpu().numpy()
    raw = np.asarray(raw_action, dtype=float)
    if raw.size == 0 or raw.ndim == 0:
        raise RuntimeError("policy emitted an empty or scalar action")
    if raw.ndim == 1:
        return raw.reshape(1, -1)
    return raw.reshape(-1, raw.shape[-1])


def action_diagnostics(raw_action, root):
    """Summarize policy output against the declared environment action boundary.

    This is deliberately a measurement of the value supplied to the environment adapter.  It does
    not replace or mutate that value, and it does not claim to observe controller-internal torque
    clipping.  A batch is accepted because PPG and the vector adapters expose one-environment
    actions with a leading dimension.
    """
    raw = _action_array(raw_action)
    low, high, bounds_source = _action_bounds(root, default_dim=raw.shape[-1])
    if low.size == 1:
        low = np.full((raw.shape[-1],), low.item())
        high = np.full((raw.shape[-1],), high.item())
    low = np.broadcast_to(low, raw.shape)
    high = np.broadcast_to(high, raw.shape)
    executed = np.clip(raw, low, high)
    finite = np.isfinite(raw)
    if not finite.all():
        raise RuntimeError("policy emitted a non-finite action")
    delta = np.abs(raw - executed)
    vector_clipped = np.any(delta > 1e-12, axis=1)
    return {
        "action_clip_rate_coordinate": float(np.count_nonzero(delta > 1e-12) / raw.size),
        "action_clip_rate_vector": float(np.count_nonzero(vector_clipped) / raw.shape[0]),
        "action_raw_executed_l1": float(delta.sum()),
        "action_raw_min": float(raw.min()),
        "action_raw_max": float(raw.max()),
        "action_bounds_source": bounds_source,
    }


class ActionDiagnosticsAccumulator:
    """Accumulate the exact pre-environment actions observed by an evaluator adapter.

    The accumulator calls :func:`action_diagnostics` for every observation, so the standalone
    helper is part of the live record path rather than a parallel formula.  The returned scope is
    intentionally narrow: it compares policy output after the family's adapter conversion with
    the VGB/Gym action-space boundary.  The robosuite controller may clip derived torques later;
    that hidden transformation is explicitly not claimed here.
    """

    def __init__(self, root):
        self._root = root
        _low, _high, self._bounds_source = _action_bounds(root)
        self._actions = 0
        self._coordinates = 0
        self._clipped_actions = 0
        self._clipped_coordinates = 0
        self._l1 = 0.0
        self._raw_min = float("inf")
        self._raw_max = float("-inf")

    def observe(self, raw_action):
        raw = _action_array(raw_action)
        # Convert a tensor once. The public helper remains the single metric implementation, while
        # the accumulator avoids a second CUDA/CPU transfer when a family exposes a tensor action.
        row = action_diagnostics(raw, self._root)
        self._actions += raw.shape[0]
        self._coordinates += raw.size
        self._clipped_actions += round(row["action_clip_rate_vector"] * raw.shape[0])
        self._clipped_coordinates += round(row["action_clip_rate_coordinate"] * raw.size)
        self._l1 += row["action_raw_executed_l1"]
        self._raw_min = min(self._raw_min, row["action_raw_min"])
        self._raw_max = max(self._raw_max, row["action_raw_max"])

    def finish(self):
        base = {
            "scope": "policy_output_before_env_action_boundary",
            "execution_boundary": "declared_action_space_before_controller",
            "controller_clipping_observed": False,
            "bounds_source": self._bounds_source,
            "actions_observed": self._actions,
        }
        if not self._actions:
            return {**base, "available": False, "reason": "no_actions_observed"}
        if self._bounds_source != "action_space":
            return {**base, "available": False, "reason": "action_bounds_not_observed"}
        return {
            **base,
            "available": True,
            "coordinates_observed": self._coordinates,
            "action_clip_rate_coordinate": self._clipped_coordinates / self._coordinates,
            "action_clip_rate_vector": self._clipped_actions / self._actions,
            "action_raw_executed_l1": self._l1,
            "action_raw_min": self._raw_min,
            "action_raw_max": self._raw_max,
        }


def policy_scale(root):
    """Read a stochastic policy's state-independent log standard deviation when available."""
    candidates = []
    seen = set()

    def walk(node, depth=0):
        if node is None or depth > 5 or id(node) in seen:
            return
        seen.add(id(node))
        if isinstance(node, dict):
            for key, value in node.items():
                if str(key).split("/")[-1] in {"log_std", "pi_logstd", "logstd"}:
                    candidates.append(value)
                walk(value, depth + 1)
            return
        for attr in ("log_std", "pi_logstd", "logstd", "dist", "actor", "actor_critic",
                     "model", "params"):
            try:
                value = getattr(node, attr, None)
            except Exception:
                value = None
            if value is not None:
                if attr in {"log_std", "pi_logstd", "logstd"}:
                    candidates.append(value)
                walk(value, depth + 1)

    walk(root)
    for value in candidates:
        try:
            if hasattr(value, "_bias"):
                value = value._bias
            if hasattr(value, "detach"):
                value = value.detach().cpu().numpy()
            elif hasattr(value, "numpy"):
                value = value.numpy()
            array = np.asarray(value, dtype=float).ravel()
            if array.size and np.isfinite(array).all():
                return {
                    "log_std_mean": float(array.mean()),
                    "log_std_min": float(array.min()),
                    "log_std_max": float(array.max()),
                }
        except Exception:
            continue
    return None
