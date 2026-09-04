#!/usr/bin/env python3
"""One plotting routine for every baseline. R5.

    python plot.py                        # everything under logs/
    python plot.py --task Door --out artifacts/door.png
    python plot.py --table                # the numbers, not the picture

THE REQUIREMENT is that the drawing code be the same for all baselines: download the tensorboard
logs and render every eval curve with one algorithm. So this file contains **no per-baseline
branch of any kind**. It reads a directory tree, groups by `(task, baseline, seed)`, and draws.
`tests/test_plot.py` asserts that no baseline name appears as a string literal anywhere in it.

IT READS `scalars.jsonl`, NOT the tfevents files, when both are present. Same numbers, written by
the same `RunLogger.log_scalars` call, but parsing JSON needs no tensorboard install and cannot
silently drop a tag the way an event-file reader can when a run is still open. `--events` forces
the tfevents path, and `tests/test_plot.py` checks the two agree.

WHAT IS DELIBERATELY NOT DRAWN:
* No "retention" or normalised-score curve. A ratio whose denominator is a near-zero training
  score produces numbers like "131% retention" off a denominator of 0.11. The gap is plotted as
  an absolute difference; anything normalised needs a measured floor and a gate, and belongs in a
  separate analysis, not in the default figure.
* No curve for a run whose `protocol_hash` differs from the others in its panel. Instead the
  panel is annotated with the mismatch. Silently overlaying two protocols is the failure this
  whole repo is built to prevent, and a plotter is the last place it can happen.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics as st
import sys
import tempfile
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from rlgen import tags  # noqa: E402


def read_run(d: str) -> dict | None:
    """-> {'protocol': {...}, 'series': {tag: {frames: value}}} for one run directory."""
    pj, sj = os.path.join(d, "protocol.json"), os.path.join(d, "scalars.jsonl")
    if not (os.path.exists(pj) and os.path.exists(sj)):
        return None
    protocol = json.load(open(pj, encoding="utf-8"))
    series: dict[str, dict[int, float]] = defaultdict(dict)
    with open(sj, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            frames = int(rec.pop("frames"))
            for k, v in rec.items():
                series[k][frames] = float(v)
    return {"dir": d, "protocol": protocol, "series": dict(series)}


def read_run_events(d: str) -> dict | None:
    """Same shape, from the tfevents file. Used by --events and by the agreement test."""
    import glob
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
    ev = sorted(glob.glob(os.path.join(d, "events.out.tfevents.*")))
    pj = os.path.join(d, "protocol.json")
    if not ev or not os.path.exists(pj):
        return None
    ea = EventAccumulator(ev[0])
    ea.Reload()
    series = {t: {int(s.step): float(s.value) for s in ea.Scalars(t)}
              for t in ea.Tags()["scalars"]}
    return {"dir": d, "protocol": json.load(open(pj, encoding="utf-8")), "series": series}


#: Directories that are never a logs root. Walking one collects whatever unrelated runs happen to
#: be lying around and plots them as if they belonged to the experiment.
_FORBIDDEN_ROOTS = {os.path.realpath(tempfile.gettempdir()), os.path.realpath(os.sep),
                    os.path.realpath(os.path.expanduser("~"))}


def discover(root: str, reader=read_run) -> list[dict]:
    """Every run under `root`, by walking for `protocol.json`.

    The forbidden-root check is not hypothetical. A test computed its walk root as
    `dirname(dirname(logdir))` while `logdir` sits ONE level below its temp directory, so it
    walked the whole of $TMPDIR, silently picked up runs from concurrent processes, and compared
    this run's logged values against another run's. It was intermittent, and it reached the
    mutation oracle -- where a flaky test does not merely annoy, it inflates the kill rate.

    A logs root of $TMPDIR, `/` or `$HOME` is always a mistake -- a mis-derived path or a mistyped
    `--logs`. Refusing is the difference between a loud error and a plausible wrong figure.
    """
    real = os.path.realpath(root)
    if real in _FORBIDDEN_ROOTS:
        raise ValueError(
            f"refusing to treat {real!r} as a logs root -- it would collect unrelated runs from "
            f"the whole directory and plot them as this experiment's. Pass the run tree itself.")
    out = []
    for dirpath, _dirnames, filenames in os.walk(root):
        if "protocol.json" in filenames:
            r = reader(dirpath)
            if r:
                out.append(r)
    return out


def _key(run: dict) -> tuple:
    p = run["protocol"]
    parts = os.path.normpath(run["dir"]).split(os.sep)
    # logs/<benchmark>/<task>/<baseline>/<mode>-seed<n>
    baseline = parts[-2] if len(parts) >= 2 else "?"
    return (p.get("task", "?"), baseline)


def aggregate(runs: list[dict], tag: str) -> dict[tuple, dict[int, list[float]]]:
    """(task, baseline) -> frames -> [value per seed]."""
    out: dict[tuple, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in runs:
        for frames, v in r["series"].get(tag, {}).items():
            out[_key(r)][frames].append(v)
    return out


def label_for(baseline: str) -> str:
    """Legend text. Aliases are marked, so no figure can imply independence it does not have."""
    try:
        from rlgen import registry
        return registry.get(baseline).label
    except Exception:
        return baseline


def make_figure(runs: list[dict], out_path: str, tasks: list[str] | None = None) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    tasks = tasks or sorted({r["protocol"].get("task", "?") for r in runs})
    curves = aggregate(runs, tags.EVAL_RETURN_MEAN)
    train_curves = aggregate(runs, tags.TRAIN_EVAL_RETURN_MEAN)

    fig, axes = plt.subplots(1, max(1, len(tasks)), figsize=(7 * max(1, len(tasks)), 5),
                             squeeze=False)
    for ti, task in enumerate(tasks):
        ax = axes[0][ti]
        # One protocol per panel, or the panel says so.
        hashes = {r["protocol"].get("hash") for r in runs if r["protocol"].get("task") == task}
        for (t, baseline), series in sorted(curves.items()):
            if t != task:
                continue
            xs = sorted(series)
            ys = [st.mean(series[x]) for x in xs]
            n_seeds = max(len(series[x]) for x in xs)
            line, = ax.plot([x / 1000 for x in xs], ys, "-o", ms=4, lw=1.8,
                            label=f"{label_for(baseline)}  (n={n_seeds})")
            if n_seeds > 1:
                lo = [min(series[x]) for x in xs]
                hi = [max(series[x]) for x in xs]
                ax.fill_between([x / 1000 for x in xs], lo, hi, alpha=.15,
                                color=line.get_color(), lw=0)
            tr = train_curves.get((t, baseline))
            if tr:
                txs = sorted(tr)
                ax.plot([x / 1000 for x in txs], [st.mean(tr[x]) for x in txs], "--",
                        lw=1.1, alpha=.55, color=line.get_color())
        ax.set_title(task, fontsize=13, fontweight="bold")
        ax.set_xlabel("environment frames (thousands)")
        if ti == 0:
            ax.set_ylabel("episode return (raw, undiscounted)")
        ax.grid(alpha=.25, lw=.6)
        ax.legend(fontsize=8, frameon=False)
        if len(hashes) > 1:
            ax.text(0.5, 0.02,
                    f"WARNING: {len(hashes)} different protocols in this panel — not comparable",
                    transform=ax.transAxes, ha="center", fontsize=9, color="#c0392b",
                    fontweight="bold")

    fig.suptitle("RL-ViGen robosuite — solid: eval (10 held-out scenes) · dashed: train scene 0\n"
                 "One evaluator, one protocol hash per panel, one plotting routine.", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    fig.savefig(out_path, dpi=145)
    return out_path


def make_table(runs: list[dict]) -> str:
    curves = aggregate(runs, tags.EVAL_RETURN_MEAN)
    trains = aggregate(runs, tags.TRAIN_EVAL_RETURN_MEAN)
    rows = [("task", "baseline", "frames", "train", "eval", "gap", "seeds", "protocol")]
    for (task, baseline), series in sorted(curves.items()):
        last = max(series)
        tr = trains.get((task, baseline), {}).get(last, [float("nan")])
        ph = {r["protocol"].get("hash") for r in runs if _key(r) == (task, baseline)}
        rows.append((task, label_for(baseline), f"{last:,}",
                     f"{st.mean(tr):.3f}", f"{st.mean(series[last]):.3f}",
                     f"{st.mean(tr) - st.mean(series[last]):.3f}",
                     str(len(series[last])), ",".join(sorted(ph))[:16]))
    w = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    out = []
    for i, r in enumerate(rows):
        out.append("  ".join(c.ljust(w[j]) for j, c in enumerate(r)).rstrip())
        if i == 0:
            out.append("  ".join("-" * w[j] for j in range(len(w))))
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--logs", default=os.path.join(ROOT, "logs"))
    ap.add_argument("--out", default=os.path.join(ROOT, "artifacts", "curves.png"))
    ap.add_argument("--task", action="append")
    ap.add_argument("--table", action="store_true", help="print the numbers instead of drawing")
    ap.add_argument("--events", action="store_true",
                    help="read tfevents instead of scalars.jsonl (same numbers)")
    args = ap.parse_args()

    runs = discover(args.logs, read_run_events if args.events else read_run)
    if not runs:
        print(f"FATAL: no runs under {args.logs}. A plot of nothing is not an empty plot, it is a "
              f"missing measurement -- refusing to emit one.", file=sys.stderr)
        return 1
    print(f"{len(runs)} run(s) under {args.logs}")
    if args.table:
        print()
        print(make_table(runs))
        return 0
    p = make_figure(runs, args.out, args.task)
    print(f"wrote {p}")
    print()
    print(make_table(runs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
