#!/usr/bin/env python3
"""One plotting routine over TensorBoard event files. [TASK.md](../docs/TASK.md) R5, item 3.

R5's check has four parts: identical tag names across baselines, a constants module owning the
tag strings, **one script over a directory of event files with no per-algorithm branch**, and a
test that each baseline's tag set equals the canonical one. This is the third.

The first draft of this file claimed items 1, 2 and 4 were all undone. That was wrong about
item 2 and cost a red suite to find out: `rlgen/tags.py` already owns the canonical strings and
`tests/test_eval_identity.py::test_no_tag_literals_outside_tags_module` already forbids literals
at call sites — a rule this file broke on its first commit by hardcoding
`"eval/episode_reward"`. Checking what exists before describing it as missing is the standing
lesson here and it was not applied.

Item 1 is genuinely open and is [C53](../docs/CONSTRUCTION.md#c53): the canonical names are
`eval/return_mean`, `eval/success_rate`; what RL-ViGen's loop actually emits is
`eval/episode_reward`. The defaults below are therefore the **canonical** set, which means a run
of this script over today's logs reports every canonical tag as absent. That is not a bug to
route around — it is C53's gap, shown by the acceptance-test path rather than argued about. Pass
`--tags` to read what is emitted instead.

There is **no per-algorithm branch here** and there must not be one: the script plots whatever
scalar tags it is asked for, for whatever runs it finds. A tag a baseline does not emit is a gap
in that baseline's logging, reported as such, not something for this file to special-case.

    python scripts/plot_curves.py RL-ViGen-upstream/exp_local --out results/curves
"""
from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT))
from rlgen import tags as _tags   # noqa: E402  the canonical strings live in exactly one module

# Canonical, per R5 -- deliberately NOT the strings RL-ViGen's loop emits. See the module
# docstring: the difference between these and what is emitted is C53, and defaulting to the
# canonical set makes that difference visible instead of quietly plotting around it.
DEFAULT_TAGS = (_tags.EVAL_RETURN_MEAN, _tags.EVAL_SUCCESS_RATE, _tags.TRAIN_RETURN_MEAN)


def find_runs(root: pathlib.Path) -> dict:
    """Map run label -> event file. Depth-agnostic: only `config.yaml` writes a flat tree."""
    out = {}
    for ev in sorted(root.rglob("events.out.tfevents*")):
        run = ev.parent.parent if ev.parent.name == "tb" else ev.parent
        out[run.name[:38]] = ev
    return out


def read(ev: pathlib.Path, tags):
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
    ea = EventAccumulator(str(ev))
    ea.Reload()
    have = set(ea.Tags().get("scalars", []))
    series = {}
    for t in tags:
        if t in have:
            pts = ea.Scalars(t)
            series[t] = ([p.step for p in pts], [p.value for p in pts])
    return series, have


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("logdir", type=pathlib.Path)
    ap.add_argument("--out", type=pathlib.Path, default=ROOT / "results" / "curves")
    ap.add_argument("--tags", default=",".join(DEFAULT_TAGS))
    a = ap.parse_args(argv)

    tags = [t.strip() for t in a.tags.split(",") if t.strip()]
    runs = find_runs(a.logdir)
    if not runs:
        print(f"no event files under {a.logdir}. A SKIP is not a pass: nothing was plotted.")
        print("Runs written before 2026-08-20 have none -- the launcher passed use_tb=False.")
        return 1

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    a.out.mkdir(parents=True, exist_ok=True)
    missing, made = {}, []
    for tag in tags:
        fig, ax = plt.subplots(figsize=(7, 4))
        drawn = 0
        for label, ev in runs.items():
            series, have = read(ev, [tag])
            if tag not in series:
                missing.setdefault(tag, []).append(label)
                continue
            xs, ys = series[tag]
            ax.plot(xs, ys, linewidth=1.2, label=label[:26])
            drawn += 1
        if not drawn:
            plt.close(fig)
            continue
        ax.set_xlabel("frames")
        ax.set_ylabel(tag)
        ax.set_title(f"{tag}   ({drawn} run{'s' if drawn > 1 else ''})")
        ax.legend(fontsize=6, loc="best")
        fig.tight_layout()
        p = a.out / f"{tag.replace('/', '_')}.png"
        fig.savefig(p, dpi=130)
        plt.close(fig)
        made.append(p)
        print(f"  wrote {p.relative_to(ROOT) if p.is_relative_to(ROOT) else p}  ({drawn} runs)")

    for tag, labels in missing.items():
        print(f"  NOT LOGGED: {tag} absent from {len(labels)} run(s) -- "
              f"a logging gap in those runs, not a plotting one")
    if not made:
        print("  nothing plotted: no requested tag was present in any run.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
