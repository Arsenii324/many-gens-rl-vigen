"""THE evaluator. There is exactly one, and it cannot see which algorithm it is running.

The supervisor's requirement is that evaluation be identical across baselines in six respects:
how we step the environment, how often, how many episodes, how we collect reward, how we average
it, and what we log it under. Those six are properties of THIS FILE, and of no other.

WHY THE SIGNATURE IS THE WHOLE DESIGN.

    evaluate(protocol, policy: Callable[[np.ndarray], np.ndarray], ...) -> EvalResult

`policy` is an opaque callable from observation to action. The evaluator receives no algorithm
name, no config, no model object, and no flags derived from any of those. It therefore *cannot*
treat two baselines differently -- not as a matter of discipline, but as a matter of what
information is in scope. Review discipline decays; a missing parameter does not.

This is a direct response to how the requirement fails in practice. In the group's own reference
repo the eval loop lives inside `agents/ppo_ibac.py`, so the baseline that was added has an eval
curve and the baseline it is compared against has none; two protocol axes (return normalisation
and full-vs-held-out level sampling) are set invisibly in that agent file. In this repo's previous
state there were three incompatible eval paths and the two halves ran on different benchmarks.

`tests/test_eval_identity.py` enforces the structural claims:
  * exactly one function in the tree steps an environment for evaluation;
  * `evaluate` takes no parameter that could carry an algorithm identity;
  * every emitted tag comes from `rlgen/tags.py` rather than a string literal.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import statistics as st
import zlib
from dataclasses import dataclass, asdict, field
from typing import Callable, Iterable, Sequence

import numpy as np

from . import tags
from .envs import Env, EnvSpec, make_env, spec_from_protocol
from .protocol import Protocol

#: obs (C, H, W) uint8  ->  action (act_dim,) float32 in [-1, 1].
#: The ONLY thing the evaluator knows about a baseline.
Policy = Callable[[np.ndarray], np.ndarray]


@dataclass
class EpisodeRecord:
    """One episode. The atom everything post-hoc is computed from.

    Storing episodes rather than means is the single irreversible logging decision: any other
    aggregation, episode count or scene subset is recoverable from these rows and from nothing
    else. `frames` is the TRAINING frame count of the evaluated checkpoint; `episode_len` is the
    episode's length. Conflating the two is how a re-scoring programme quietly becomes impossible.
    """
    baseline: str
    backbone: str
    task: str
    mode: str
    scene_id: int
    seed: int
    frames: int
    checkpoint: str
    episode_idx: int
    return_raw: float
    episode_len: int
    terminated: bool
    truncated: bool
    success: bool | None
    policy_mode: str
    protocol_hash: str
    weights_source: str
    code_commit: str

    def row(self) -> list:
        d = asdict(self)
        return [d[c] for c in tags.EPISODE_COLUMNS]


@dataclass
class EvalResult:
    records: list[EpisodeRecord]
    protocol_hash: str
    mode: str
    #: tag -> value, using ONLY constants from rlgen.tags
    scalars: dict[str, float] = field(default_factory=dict)

    @property
    def returns(self) -> list[float]:
        return [r.return_raw for r in self.records]

    def per_scene(self) -> dict[int, list[float]]:
        out: dict[int, list[float]] = {}
        for r in self.records:
            out.setdefault(r.scene_id, []).append(r.return_raw)
        return out


def _reduce(xs: Sequence[float], how: str) -> float:
    if not xs:
        return float("nan")
    if how == "mean":
        return float(st.mean(xs))
    if how == "median":
        return float(st.median(xs))
    if how == "iqm":
        s = sorted(xs)
        n = len(s)
        lo, hi = n // 4, n - n // 4
        w = s[lo:hi] or s
        return float(st.mean(w))
    raise ValueError(f"unknown aggregation {how!r}")


def bootstrap_ci(xs: Sequence[float], *, key: str, n: int = 4000, alpha: float = 0.05,
                 how: str = "mean") -> tuple[float, float]:
    """Percentile bootstrap. Seeded from `key` so a figure is byte-reproducible.

    Uses the SAME reduction as the headline statistic -- a mean point estimate with a
    median-bootstrap interval is a different quantity wearing the same label.
    """
    if len(xs) < 2:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(zlib.crc32(key.encode()))
    arr = np.asarray(xs, dtype=float)
    stats = [_reduce(rng.choice(arr, size=arr.size, replace=True).tolist(), how) for _ in range(n)]
    stats.sort()
    return (float(stats[int(alpha / 2 * n)]), float(stats[int((1 - alpha / 2) * n)]))


def _episode_seed(protocol_hash: str, mode: str, scene_id: int, seed: int, episode_idx: int) -> int:
    """A distinct, reproducible seed per episode.

    Reusing one seed across episodes collapses across-episode variance to zero and makes a policy
    look far more consistent than it is; it is mutant M6 in docs/RIGOR.md. Deriving the seed from
    the protocol hash means an accidental protocol change also changes the seeds, so a stale
    cached result cannot masquerade as a fresh one.

    CORRECTED 2026-08-13. This docstring previously claimed the seed does NOT make an episode
    byte-reproducible ("robosuite carries internal state across resets that the global numpy seed
    does not control") and cited a test by that name as evidence. That test never existed in this
    repo -- the claim was written, not measured, and it was wrong. Measured now, on the real
    backend: re-seeding to the SAME value before `env.reset()` DOES give a byte-identical episode
    (`tests/test_real_env.py::test_real_env_reseeded_episode_reproducibility`), and a different
    seed reliably diverges. So this gives you BOTH properties: episodes are decorrelated across
    the seed sequence, AND evaluating the same checkpoint twice reproduces the same numbers --
    which is exactly the property the sibling gen-rebuttal project had to add separately (its
    R20), achieved here by a different, finer-grained mechanism (per-episode rather than
    per-worker seeding) that nobody had actually verified until now.
    """
    key = f"{protocol_hash}|{mode}|{scene_id}|{seed}|{episode_idx}"
    return zlib.crc32(key.encode()) & 0x7FFFFFFF


def _read_success(env: Env) -> bool | None:
    """robosuite's own task-completion predicate, if reachable. `None` when it is not.

    Never fabricated: a success rate invented from a return threshold is a different quantity, and
    reporting it under the same name is how two baselines end up incomparable.
    """
    # The wrapper chain does not use one attribute name throughout:
    #   ExtendedTimeStep -> FrameStack -> action_scale -> ActionRepeat -> ActionDType   via `_env`
    #   Gym2DMC                                                                          via `_gym_env`
    #   VGBWrapper                                                                       via `env`
    #   robosuite task  -- has _check_success
    # Walking only `_env` stops at Gym2DMC, which is why success was silently absent from every
    # row of the first real run. Absent is recorded as None; it is never synthesised from a
    # return threshold, because that is a different quantity under the same name.
    LINKS = ("_env", "_gym_env", "env", "_environment", "unwrapped")
    node = getattr(env, "_env", None)
    for _ in range(16):
        if node is None:
            return None
        fn = getattr(node, "_check_success", None)
        if callable(fn):
            try:
                return bool(fn())
            except Exception:
                return None
        nxt = None
        for link in LINKS:
            cand = getattr(node, link, None)
            if cand is not None and cand is not node:
                nxt = cand
                break
        node = nxt
    return None


def run_episode(env: Env, policy: Policy, *, max_steps: int) -> tuple[float, int, bool, bool, bool | None]:
    """One episode. THE stepping loop -- the only one in the repo.

    Returns (raw undiscounted return, length, terminated, truncated, success).
    """
    obs = env.reset()
    total, steps = 0.0, 0
    terminated = truncated = False
    while steps < max_steps:
        action = policy(obs)
        obs, reward, terminated, truncated, _info = env.step(action)
        total += float(reward)
        steps += 1
        if terminated or truncated:
            break
    return total, steps, bool(terminated), bool(truncated), _read_success(env)


def evaluate(protocol: Protocol,
             policy: Policy,
             *,
             mode: str,
             scene_ids: Iterable[int] | None = None,
             episodes_per_scene: int | None = None,
             frames: int = 0,
             checkpoint: str = "",
             baseline: str = "",
             backbone: str = "",
             backend: str = "robosuite",
             progress: Callable[[str], None] | None = None) -> EvalResult:
    """Evaluate one policy under one protocol.

    NOTE ON THE PARAMETERS. `baseline` and `backbone` are recorded into the output rows so a
    result can say what produced it; they are never read by any control-flow statement in this
    function, and `tests/test_eval_identity.py` asserts that by mutating them and requiring the
    returned numbers to be unchanged. They are labels on the output, not inputs to the procedure.
    """
    scenes = list(scene_ids if scene_ids is not None else protocol.eval_scene_ids)
    per_scene = int(episodes_per_scene if episodes_per_scene is not None
                    else protocol.episodes_per_scene)
    phash = protocol.hash()
    records: list[EpisodeRecord] = []

    for scene in scenes:
        spec = spec_from_protocol(protocol, mode=mode, scene_id=scene, seed=protocol.seed,
                                  backend=backend)
        env = make_env(spec)
        try:
            for ep in range(per_scene):
                # Distinct per episode and a deterministic function of the protocol. This
                # decorrelates episodes; it does NOT make a real-simulator episode replayable --
                # see _episode_seed's docstring.
                s = _episode_seed(phash, mode, scene, protocol.seed, ep)
                np.random.seed(s)
                ret, length, term, trunc, success = run_episode(
                    env, policy, max_steps=protocol.steps_per_episode)
                records.append(EpisodeRecord(
                    baseline=baseline, backbone=backbone, task=protocol.task, mode=mode,
                    scene_id=scene, seed=protocol.seed, frames=frames, checkpoint=checkpoint,
                    episode_idx=ep, return_raw=ret, episode_len=length,
                    terminated=term, truncated=trunc, success=success,
                    policy_mode=protocol.policy_mode, protocol_hash=phash,
                    weights_source=protocol.weights_source, code_commit=protocol.code_commit))
            if progress:
                progress(f"    scene {scene}: {per_scene} ep, "
                         f"mean {st.mean([r.return_raw for r in records[-per_scene:]]):.3f}")
        finally:
            env.close()

    return EvalResult(records=records, protocol_hash=phash, mode=mode,
                      scalars=summarize(records, protocol, mode))


def _diag_pstdev(rets):
    if len(rets) <= 1:
        return 0.0
    try:
        return float(st.pstdev(rets))
    except AttributeError as error:
        import sys
        print("DIAG_PSTDEV_FAILURE", [(type(x).__name__, repr(x)) for x in rets], file=sys.stderr)
        raise


def summarize(records: Sequence[EpisodeRecord], protocol: Protocol, mode: str) -> dict[str, float]:
    """Records -> scalars, using only tag constants. The single place aggregation happens."""
    if not records:
        return {}
    rets = [r.return_raw for r in records]
    lens = [r.episode_len for r in records]
    succ = [r.success for r in records if r.success is not None]
    is_train = mode == protocol.train_mode
    T = tags
    out: dict[str, float] = {}
    if is_train:
        out[T.TRAIN_EVAL_RETURN_MEAN] = _reduce(rets, protocol.aggregation)
        out[T.TRAIN_EVAL_RETURN_STD] = _diag_pstdev(rets)
        if succ:
            out[T.TRAIN_EVAL_SUCCESS_RATE] = float(sum(succ) / len(succ))
    else:
        out[T.EVAL_RETURN_MEAN] = _reduce(rets, protocol.aggregation)
        out[T.EVAL_RETURN_STD] = _diag_pstdev(rets)
        out[T.EVAL_RETURN_MEDIAN] = float(st.median(rets))
        out[T.EVAL_EPISODE_LEN_MEAN] = float(st.mean(lens))
        out[T.EVAL_EPISODES] = float(len(rets))
        if succ:
            out[T.EVAL_SUCCESS_RATE] = float(sum(succ) / len(succ))
    return out


def checkpoint_fingerprint(path: str) -> str:
    """`checkpoint:<sha256[:12]>` for a real file. Never blank, never guessed."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return f"checkpoint:{h.hexdigest()[:12]}"
