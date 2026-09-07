#!/usr/bin/env python3
"""Read the twelve baselines' logs and put their metrics on one set of axes.

    python scripts/collect_metrics.py /tmp/smoke_all_0418            # a directory of <name>.log
    python scripts/collect_metrics.py <dir> --csv out.csv
    python scripts/collect_metrics.py <dir> --self-test              # parsers vs. known fixtures

## What this is, and the one thing it is careful not to be

Part 2's goal is that reported metrics sit on the same axes. The twelve now emit **comparable
quantities** — episode return and, since RL-ViGen patches P10/P11, robosuite's own task-defined
success rate — in **six different formats**, because each baseline logs with its authors' logger.
This reads those formats and emits one record shape.

**It is a reader. It joins nothing and changes no number.** It does not touch a clone, does not
run anything, and cannot alter what a baseline computed. That matters because a *common training
harness* is precisely the join `docs/RUNNABLE-ORIGINALS.md` exists to avoid; a common *view* over
what the authors' own code already printed is not that.

## The record

    baseline, regime, frames, episode_reward, success_rate, source_line

`regime` is `train` or the held-out visual regime the number belongs to, so a generalisation gap
is `train` minus `eval-easy` for one baseline. `frames` is env frames, which every baseline now
shares (they all run `action_repeat=1`; see docs/PART2-METRIC-INVENTORY.md Finding 3).

## What this cannot see, and where it will silently be wrong

- **It parses printed logs**, not the CSV/JSON some baselines also write. A log line is a
  formatted view: `ibac_sni` prints `SR` to three decimals, so a success rate of 0.0004 reads as
  0.000 here and is 0.0004 in `log.csv`. Prefer the structured file when precision matters.
- **A format change upstream silently yields fewer records, not an error.** That is why
  `--self-test` exists and why the summary prints a per-baseline record COUNT: zero records for
  a baseline whose log exists is the signal, and it is the one this file is most likely to hit.
- **It cannot tell a real 0.0 from an unfilled column.** `tests/test_success_metric.py` is what
  establishes that success rate is live; nothing here re-establishes it.
- **`frames` is absent for some baselines' eval lines** (`alda` logs no step with its eval), and
  is emitted as None rather than guessed.
"""
from __future__ import annotations

import argparse
import csv
import pathlib
import re
import sys
from dataclasses import dataclass, asdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from scripts.metrics import wilson_interval  # noqa: E402
from datasphere.native.family import provenance_for  # noqa: E402

ANSI = re.compile(r"\x1b\[[0-9;]*m")


@dataclass
class Record:
    baseline: str
    regime: str
    frames: int | None
    episode_reward: float | None
    success_rate: float | None
    source_line: str
    source_target: str | None = None
    source_variant: str | None = None

    def __post_init__(self):
        try:
            labels = provenance_for(self.baseline)
        except ValueError:
            return
        self.source_target = labels["source_target"]
        self.source_variant = labels["source_variant"]


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def parse_dmc_gb(name, text):
    """rad / soda: `| eval | S: 0 | ER: 0.89 | ERTEST: 0.86 | SR: 0.0 | SRTEST: 0.0`

    ER/SR are the TRAIN env; ERTEST/SRTEST are the --eval_mode env. dmc_gb's own train.py calls
    evaluate() twice, once per env, which is why one line carries two regimes.
    """
    out = []
    for l in text.splitlines():
        m = re.match(r"\|\s*eval\s*\|\s*S:\s*(\d+)\s*\|\s*ER:\s*([-\d.]+)\s*\|"
                     r"\s*ERTEST:\s*([-\d.]+)\s*(?:\|\s*SR:\s*([-\d.]+)\s*\|"
                     r"\s*SRTEST:\s*([-\d.]+))?", l.strip())
        if not m:
            continue
        s = int(m.group(1))
        out.append(Record(name, "train", s, _f(m.group(2)), _f(m.group(4)), l.strip()))
        out.append(Record(name, "eval-easy", s, _f(m.group(3)), _f(m.group(5)), l.strip()))
    return out


def parse_alda(name, text):
    """`... alda: eval/episode_reward_color: 1.117` — the suffix names the regime.

    ALDA's own vocabulary: no suffix is the train env, `_color` is its colour-randomised eval
    (RL-ViGen eval-easy here), `_distracting` its harder one (eval-hard). No step is logged with
    these lines, so frames stays None rather than being invented.
    """
    SUF = {"": "train", "_color": "eval-easy", "_color_hard": "eval-easy",
           "_distracting": "eval-hard"}
    out = []
    for l in text.splitlines():
        m = re.search(r"eval/(episode_reward|success_rate)(_[a-z_]+)?:\s*([-\d.eE+]+)", l)
        if not m:
            continue
        regime = SUF.get(m.group(2) or "", m.group(2) or "train")
        val = _f(m.group(3))
        out.append(Record(name, regime, None,
                          val if m.group(1) == "episode_reward" else None,
                          val if m.group(1) == "success_rate" else None, l.strip()))
    return out


def parse_idaac(name, text):
    """idaac's logger prints `| key | value |` blocks; train/* and test/* are the two regimes."""
    vals, frames = {}, None
    for l in text.splitlines():
        m = re.match(r"\|\s*(train|test)/([a-z_]+)\s*\|\s*([-\d.e+]+)\s*\|", l.strip())
        if not m:
            continue
        if m.group(2) == "total_num_steps":
            frames = int(float(m.group(3)))
        vals[f"{m.group(1)}/{m.group(2)}"] = _f(m.group(3))
    out = []
    for pre, regime in (("train", "train"), ("test", "eval-easy")):
        if f"{pre}/mean_episode_reward" in vals:
            out.append(Record(name, regime, frames, vals[f"{pre}/mean_episode_reward"],
                              vals.get(f"{pre}/success_rate"), f"{pre}/* block"))
    return out


def parse_ctrl(name, text):
    """`[2584]\tEprew200: 7.177\tEprew0: 4.315\tSR_ID: 0.000\tSR_OOD: 0.000`

    Eprew200 is the in-distribution test env, Eprew0 the out-of-distribution one -- names
    inherited from Procgen's 200-level train split vs the full distribution.
    """
    out = []
    for l in text.splitlines():
        m = re.match(r"\[(\d+)\]\s*Eprew200:\s*([-\d.nan]+)\s*Eprew0:\s*([-\d.nan]+)"
                     r"(?:\s*SR_ID:\s*([-\d.nan]+)\s*SR_OOD:\s*([-\d.nan]+))?", l.strip())
        if not m:
            continue
        fr = int(m.group(1))
        out.append(Record(name, "train", fr, _f(m.group(2)), _f(m.group(4)), l.strip()))
        out.append(Record(name, "eval-easy", fr, _f(m.group(3)), _f(m.group(5)), l.strip()))
    return out


def parse_ibac_sni(name, text):
    """`U 20 | F 001280 | ... | rR:μσmM 3.79 ... | ... | SR 0.000`

    One regime per training run -- whichever RLVIGEN_MODE was set -- so the regime is not
    recoverable from the log alone and is reported as `unknown`.

    **Two line shapes, and they are different measurements.** `scripts/train.py` emits the
    `U <update> | F <frames> | ...` line above. `scripts/evaluate.py` -- the only held-out
    evaluation any of the twelve ships -- emits

        F 5000 | FPS 120 | D 41 | R:mu... | F:mu... | SR 0.1000

    which starts with `F` and carries no update counter. Both are parsed, and they are labelled
    differently (`unknown` vs `eval-script`) because conflating a training-regime number with a
    held-out one is the exact error this whole comparison exists to avoid. What the label does
    NOT claim is *which* regime: that comes from RLVIGEN_EVAL_MODE at launch and appears nowhere
    in the line, so `eval-script` means "produced by the held-out evaluator", not "eval-easy".

    The `SR` field on the evaluate.py line was added 2026-08-17. Before that this script reported
    RETURN only while its own train.py reported success_rate, so ibac_sni's held-out number was
    not the quantity the other eleven report.
    """
    out = []
    for l in text.splitlines():
        s = l.strip()
        m = re.match(r"U \d+ \| F (\d+) \|.*?rR:\S*\s+([-\d.]+)", s)
        regime = "unknown"
        if m is None:
            # evaluate.py: no update counter, FPS present, plain R: rather than rR:
            m = re.match(r"F (\d+) \| FPS \S+ \| D \S+ \| R:\S*\s+([-\d.]+)", s)
            regime = "eval-script"
        if not m:
            continue
        sr = re.search(r"\|\s*SR ([-\d.]+)\s*$", s)
        out.append(Record(name, regime, int(m.group(1)), _f(m.group(2)),
                          _f(sr.group(1)) if sr else None, s))
    return out


def parse_ppg(name, text):
    """PPG's logger prints `| EpRewMean | 5.43 |` blocks. Train distribution only.

    Its train.py has no eval env; runnable/_launch/ppg_eval.py measures a checkpoint in a regime.
    """
    out, cur = [], {}
    for l in text.splitlines():
        m = re.match(r"\|\s*(EpRewMean|EpSuccessMean|Misc/InteractCount)\s*\|\s*([-\d.e+]+)",
                     l.strip())
        if m:
            cur[m.group(1)] = _f(m.group(2))
        if l.strip().startswith("---") and "EpRewMean" in cur:
            out.append(Record(name, "train",
                              int(cur["Misc/InteractCount"]) if "Misc/InteractCount" in cur else None,
                              cur.get("EpRewMean"), cur.get("EpSuccessMean"), "EpRewMean block"))
            cur = {}
    return out


def parse_rlvigen(name, text):
    """RL-ViGen's five: `| eval | F: 1000 | ... | R: 2.058 | ... | SR: 0.0000`.

    THE EVAL REGIME IS READ FROM THE LOG, not assumed. `make_env` prints "Now the mode is X"
    once per env, and `Workspace.setup` builds train_env then eval_env, so the SECOND such line
    is the eval env's regime. This matters because before RL-ViGen patch P12 both envs were
    built with identical arguments and both said `train`: labelling that second env `eval-easy`
    would have manufactured a generalisation gap out of two measurements of the same
    distribution. If only one mode line is present, both envs are that mode.
    """
    modes = re.findall(r"Now the mode is (\S+)", text)
    eval_regime = modes[1] if len(modes) > 1 else (modes[0] if modes else "unknown")
    out = []
    for l in text.splitlines():
        m = re.match(r"\|\s*(train|eval)\s*\|\s*F:\s*(\d+).*?R:\s*([-\d.]+)", l.strip())
        if not m:
            continue
        sr = re.search(r"SR:\s*([-\d.]+)", l)
        out.append(Record(name, "train" if m.group(1) == "train" else eval_regime,
                          int(m.group(2)), _f(m.group(3)),
                          _f(sr.group(1)) if sr else None, l.strip()))
    return out


PARSERS = {
    "rad": parse_dmc_gb, "soda": parse_dmc_gb, "alda": parse_alda, "idaac": parse_idaac,
    "ctrl": parse_ctrl, "ibac_sni": parse_ibac_sni, "ppg": parse_ppg,
    "drqv2": parse_rlvigen, "svea": parse_rlvigen, "sgqn": parse_rlvigen,
    "drq": parse_rlvigen, "curl": parse_rlvigen,
}


# RL-ViGen selects its agent by picking a WHOLE config file, so the run directory name never
# says which baseline ran -- `runnable/_launch/rlvigen.sh` maps drqv2 to `config` and everything
# else to `<name>_config`. The authority is the run's own saved `.hydra/hydra.yaml`, which is the
# same rule this project applies to checkpoints: what the run recorded outranks what a path
# suggests.
CONFIG_TO_BASELINE = {"config": "drqv2", "svea_config": "svea", "drq_config": "drq",
                      "sgqn_config": "sgqn", "curl_config": "curl"}


def baseline_of_run(run: pathlib.Path) -> str | None:
    hy = run / ".hydra" / "hydra.yaml"
    if not hy.exists():
        return None
    m = re.search(r"config_name:\s*(\S+)", hy.read_text(errors="replace"))
    return CONFIG_TO_BASELINE.get(m.group(1)) if m else None


def collect_from_runs(root: pathlib.Path):
    """Walk a hydra output tree and read each run's `eval.csv`.

    `collect()` expects `<logdir>/<baseline>.log` -- the smoke-test layout it was written and
    tested against. Pointing it at the only runs this project has produced returned **0 records
    from 0 baselines**: an instrument for building the comparison table that could not read the
    comparison's data. Then `--from-runs` reading `train.log` returned 0 as well, because
    `train.log` is hydra's log (14 lines of robosuite warnings) and the `| train | F: ... |`
    lines `parse_rlvigen` matches are **stdout**, which a real run does not persist.

    The durable artifact is `eval.csv`, so that is what is read. No regex over console
    formatting, and the regime is not guessed: patch P14 writes `train_regime_reward` and
    `train_regime_success` beside the eval columns, so a post-P14 run states both regimes itself.
    A pre-P14 run has neither column and its eval regime is genuinely not recoverable from the
    CSV -- it is emitted as `eval(unrecorded)` rather than assumed to be `eval-easy`, because
    assuming it is how a generalisation gap gets manufactured out of two measurements of the same
    distribution (the failure `parse_rlvigen`'s own docstring warns about).
    """
    recs, counts = [], {}
    # rglob, not glob("*/*/eval.csv"): only `config.yaml` (drqv2) writes
    # exp_local/<date>/<run>/. svea, drq, sgqn and curl all interpolate ${name} into
    # hydra.run.dir, so they land one level deeper at exp_local/<date>/<name>/<run>/. A
    # fixed-depth pattern finds drqv2 and silently misses four of the five -- and a tree
    # containing only drqv2 runs cannot tell you that. Depth is not part of the contract;
    # having a .hydra/hydra.yaml is.
    for csvf in sorted(root.rglob("eval.csv")):
        name = baseline_of_run(csvf.parent)
        if name is None:
            continue
        rows = list(csv.DictReader(csvf.open()))
        tag = f"{name}:{csvf.parent.name[:13]}"
        got = 0
        for r in rows:
            def num(k):
                v = r.get(k)
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return None
            frames = num("frame")
            frames = int(frames) if frames is not None else None
            has_both = r.get("train_regime_reward") not in (None, "")
            recs.append(Record(name, "eval-recorded" if has_both else "eval(unrecorded)",
                               frames, num("episode_reward"), num("success_rate"),
                               f"{csvf.parent.name[:20]}:{r.get('frame')}"))
            got += 1
            if has_both:
                recs.append(Record(name, "train", frames, num("train_regime_reward"),
                                   num("train_regime_success"),
                                   f"{csvf.parent.name[:20]}:{r.get('frame')}"))
                got += 1
        counts[tag] = got
    return recs, counts


def collect(d: pathlib.Path):
    recs, counts = [], {}
    for name, fn in PARSERS.items():
        f = d / f"{name}.log"
        if not f.exists():
            counts[name] = None
            continue
        got = fn(name, ANSI.sub("", f.read_text(errors="replace")))
        counts[name] = len(got)
        recs += got
    return recs, counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("logdir", type=pathlib.Path)
    ap.add_argument("--csv", type=pathlib.Path)
    ap.add_argument("--episodes", type=int, default=0,
                    help="episodes per eval point; enables Wilson intervals on success rate")
    ap.add_argument("--self-test", action="store_true",
                    help="require every present log to yield at least one record")
    ap.add_argument("--from-runs", action="store_true",
                    help="treat logdir as a hydra output tree (exp_local/<date>/<run>/train.log) "
                         "rather than a flat directory of <baseline>.log")
    a = ap.parse_args()
    if not a.logdir.is_dir():
        print(f"not a directory: {a.logdir}", file=sys.stderr)
        return 2

    recs, counts = (collect_from_runs if a.from_runs else collect)(a.logdir)

    print(f'{"baseline":<10}{"regime":<11}{"frames":>9}{"return":>10}{"success":>9}')
    print("-" * 50)
    for r in recs:
        print(f'{r.baseline:<10}{r.regime:<11}'
              f'{"" if r.frames is None else r.frames:>9}'
              f'{"" if r.episode_reward is None else f"{r.episode_reward:.4f}":>10}'
              f'{"" if r.success_rate is None else f"{r.success_rate:.4f}":>9}')
    print("-" * 50)
    missing = [n for n, c in counts.items() if c is None]
    empty = [n for n, c in counts.items() if c == 0]
    print(f"{len(recs)} records from {sum(1 for c in counts.values() if c)} baselines"
          + (f"; no log for: {', '.join(missing)}" if missing else ""))
    if empty:
        # THE failure mode of this file: a log exists and the parser matched nothing, which looks
        # exactly like a baseline that logged nothing. Loud, and non-zero exit under --self-test.
        print(f"\nPARSED NOTHING from an existing log: {', '.join(empty)}")
        print("A format changed, or the parser was always wrong. Do not read the table above as")
        print("'that baseline produced no metrics'.")

    # SUCCESS RATE WITH AN INTERVAL. A bare point estimate from a handful of episodes is the
    # weakest thing this project reports; `unified-bench` records the normal approximation
    # failing exactly here (zero width at p=0). Wilson does not. Episode counts are not in the
    # logs, so n is passed explicitly rather than guessed -- an interval computed from an
    # invented n would be worse than none.
    if a.episodes:
        latest = {}
        for r in recs:
            if r.success_rate is not None:
                latest[(r.baseline, r.regime)] = r.success_rate
        if latest:
            print(f'\n{"baseline":<10}{"regime":<11}{"success":>9}{"95% Wilson (n=" + str(a.episodes) + ")":>24}')
            print("-" * 54)
            for (b, reg), p in sorted(latest.items()):
                k = round(p * a.episodes)
                lo, hi = wilson_interval(k, a.episodes)
                print(f'{b:<10}{reg:<11}{p:>9.3f}{f"[{lo:.3f}, {hi:.3f}]":>24}')
            print("\nAn interval this wide is what a handful of episodes actually supports.")
            print("RL-ViGen's own paper (\u00a74) specifies 5 seeds and 95% CIs; this is one seed.")

    if a.csv:
        with a.csv.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(asdict(recs[0]).keys()) if recs else
                               ["baseline", "regime", "frames", "episode_reward",
                                "success_rate", "source_line", "source_target",
                                "source_variant"])
            w.writeheader()
            for r in recs:
                w.writerow(asdict(r))
        print(f"wrote {a.csv}")
    return 1 if (a.self_test and empty) else 0


if __name__ == "__main__":
    sys.exit(main())
