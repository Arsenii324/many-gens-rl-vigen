"""One logger. Per-episode rows, tensorboard scalars, and a protocol card, for every baseline.

Three properties, each because its absence caused a specific failure:

1. PER-EPISODE ROWS ARE WRITTEN, ALWAYS. Means are recoverable from episodes; episodes are not
   recoverable from means. Every post-hoc question -- a different statistic, a different episode
   count, a scene subset, a bootstrap interval -- is free if the rows exist and impossible if they
   do not.

2. TAGS ARE VALIDATED AGAINST rlgen/tags.py. `log_scalars` raises on an unknown key. A baseline
   cannot invent a tensorboard tag, so the shared plotter never has to guess and no curve can be
   silently missing from one baseline's logs.

3. THE CARD IS WRITTEN BEFORE ANY NUMBER IS. A run that cannot say what protocol produced it is
   not admissible, and writing the card last means a crashed run leaves numbers with no protocol.

The derived quantity `gap/absolute` is computed HERE, from the two curves, rather than by any
baseline. Anything computed in twelve places is defined in twelve ways.
"""
from __future__ import annotations

import csv
import json
import os
import time
from typing import Iterable, Mapping

from . import tags
from .evaluate import EpisodeRecord, EvalResult
from .protocol import Protocol


class RunLogger:
    def __init__(self, logdir: str, protocol: Protocol, *, baseline: str, tensorboard: bool = True):
        self.logdir = os.path.abspath(logdir)
        self.protocol = protocol
        self.baseline = baseline
        os.makedirs(self.logdir, exist_ok=True)

        # (3) protocol first.
        protocol.write_card(os.path.join(self.logdir, "protocol_card.md"))
        protocol.write_json(os.path.join(self.logdir, "protocol.json"))

        self._episodes_path = os.path.join(self.logdir, "episodes.csv")
        # A NEW logger opening a non-empty episodes.csv means a PREVIOUS run wrote here. Appending
        # to it silently concatenates two runs into one file, and the run directory is keyed by
        # (task, baseline, mode-seed) -- so re-running a baseline lands in exactly the same place.
        #
        # This is not hypothetical. `logs/.../Door/drqv2/eval-easy-seed0` holds two runs at
        # commits 621ddfc and de879a0-dirty; `.../soda/...` holds six runs' worth of rows at
        # frames=0 and only three at frames=1500 and 3000. An aggregate over that double-counts,
        # unevenly along the x-axis, and any CI is too narrow because n is inflated by repeats.
        # Nothing in the file marks where one run ends and the next begins.
        #
        # Appending WITHIN one run -- the same instance, many eval points -- is correct and is
        # what `log_episodes` keeps doing. Only re-opening is refused.
        if os.path.exists(self._episodes_path) and os.path.getsize(self._episodes_path) > 0:
            with open(self._episodes_path, encoding="utf-8") as f:
                n_rows = max(0, sum(1 for _ in f) - 1)
            if n_rows:
                raise FileExistsError(
                    f"{self._episodes_path} already holds {n_rows} episode row(s) from an earlier "
                    f"run. Appending would merge two runs into one file with nothing marking the "
                    f"boundary. Move or delete the directory, or pass a different logdir.")
        if not os.path.exists(self._episodes_path):
            with open(self._episodes_path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(tags.EPISODE_COLUMNS)

        self._scalars_path = os.path.join(self.logdir, "scalars.jsonl")
        self._writer = None
        if tensorboard:
            try:
                from torch.utils.tensorboard import SummaryWriter
                self._writer = SummaryWriter(self.logdir)
            except Exception as e:  # tensorboard is optional; the CSV/JSONL are not
                print(f"[logger] tensorboard unavailable ({e}); scalars still go to "
                      f"scalars.jsonl and episodes.csv")
        self._t0 = time.time()
        self._latest: dict[int, dict[str, float]] = {}

    # -- episodes -----------------------------------------------------------------------------
    def log_episodes(self, records: Iterable[EpisodeRecord]) -> int:
        n = 0
        with open(self._episodes_path, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            for r in records:
                if r.protocol_hash != self.protocol.hash():
                    raise ValueError(
                        f"episode carries protocol {r.protocol_hash} but this run is "
                        f"{self.protocol.hash()}. Two protocols in one log is exactly the "
                        f"condition that makes a table uncomparable; refusing to write.")
                w.writerow(r.row())
                n += 1
        return n

    # -- scalars ------------------------------------------------------------------------------
    def log_scalars(self, scalars: Mapping[str, float], frames: int) -> None:
        unknown = set(scalars) - tags.ALL_TAGS
        if unknown:
            raise KeyError(
                f"unknown log tag(s) {sorted(unknown)}. Every key must be a constant in "
                f"rlgen/tags.py -- that is what makes the plotter able to draw all baselines "
                f"with one routine. Add it there if it is genuinely new.")
        self._latest.setdefault(frames, {}).update(scalars)
        with open(self._scalars_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"frames": int(frames), **{k: float(v) for k, v in scalars.items()}},
                               sort_keys=True) + "\n")
        if self._writer is not None:
            for k, v in scalars.items():
                self._writer.add_scalar(k, float(v), int(frames))
            self._writer.flush()

    def log_eval(self, result: EvalResult, frames: int) -> None:
        """Write one evaluation: its episodes, its scalars, and the gap if both sides are in."""
        self.log_episodes(result.records)
        self.log_scalars(result.scalars, frames)
        got = self._latest.get(frames, {})
        if tags.EVAL_RETURN_MEAN in got and tags.TRAIN_EVAL_RETURN_MEAN in got:
            # (derived centrally) An ABSOLUTE difference, not a ratio. A ratio whose denominator
            # is a near-zero training score produces percentages like "131% retention" off a
            # denominator of 0.11 -- see docs/RIGOR.md section 3.3. If a normalised quantity is
            # wanted, compute it from episodes.csv with a measured floor and a gate.
            self.log_scalars({tags.GAP_ABSOLUTE: got[tags.TRAIN_EVAL_RETURN_MEAN]
                              - got[tags.EVAL_RETURN_MEAN]}, frames)

    def log_train(self, *, frames: int, n_updates: int, return_mean: float | None = None) -> None:
        s = {tags.TRAIN_UPDATES: float(n_updates),
             tags.TRAIN_WALLCLOCK: time.time() - self._t0,
             tags.TRAIN_FPS: frames / max(1e-9, time.time() - self._t0)}
        if return_mean is not None:
            s[tags.TRAIN_RETURN_MEAN] = float(return_mean)
        self.log_scalars(s, frames)

    def close(self) -> None:
        if self._writer is not None:
            self._writer.close()

    def __enter__(self): return self
    def __exit__(self, *exc): self.close()


def run_dir(root: str, protocol: Protocol, baseline: str) -> str:
    """`logs/<benchmark>/<task>/<baseline>/<mode>-seed<seed>`.

    The same shape as the group's reference repo (`logs/procgen/<env>/<algo>/<run>/`), so the
    shared plotter can walk it without configuration.
    """
    return os.path.join(root, protocol.benchmark, protocol.task, baseline,
                        f"{protocol.eval_mode}-seed{protocol.seed}")
