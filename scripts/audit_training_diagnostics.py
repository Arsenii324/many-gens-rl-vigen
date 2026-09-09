#!/usr/bin/env python3
"""Did the optimiser behave, or did the run only *look* like it ran?

    python scripts/audit_training_diagnostics.py <run-dir|csv|log> [--strict]

## Why this exists

The first two production cells both produced a null on Door, and the records could not say why: a
record carries return, not whether the policy was being updated sanely. Reading the training logs by
hand on 2026-09-09 found two *opposite* pathologies in the two runs, neither visible in any artifact
the pipeline checks:

* **`idaac`** — `approx_kl_k3` reaching **1.0-1.5 nats** against PPO's usual 0.01-0.05, `clip_fraction`
  saturated at **0.82**, policy sigma collapsing **0.996 -> 0.188**. It over-updates.
* **`ppg`** — `Opt/clipfrac` **exactly 0.000** across all 256 iterations, `approxkl` at **1e-13**,
  sigma unmoved at **1.00 -> 1.01**. Whatever that means, it is not a policy being trained the way
  the diagnostics describe.

Ten more baselines are queued. Finding this by hand once is luck; the point of this file is that the
eleventh run cannot hide it. **This is a report, not a verdict** -- see the two refusals below.

## What it will NOT do

**It never compares one family's diagnostics against another's.** `idaac`'s `clip_fraction` and
`ppg`'s `Opt/clipfrac` come from different loggers in different codebases; 0.82 against 0.000 is not
one quantity measured twice. Every check below is against a *fixed* range that describes what PPO-family
optimisation looks like, never against a sibling run -- the same discipline
`scripts/comparison_blocks.py` enforces for returns, which diagnostics have no `policy_mode` column to
protect them from.

**It does not decide that a run is bad.** A flag says a column left the range where the algorithm's
own hyperparameters were chosen. That is a question to answer, and for a deliberate deviation it may
be the expected answer. `--strict` exists for a gate that wants to stop; the default reports.
"""
from __future__ import annotations

import argparse
import csv
import os
import pathlib
import re
import sys

#: canonical name -> the column names different family loggers use for it.
SERIES = {
    "kl":        ("train/approx_kl_k3", "Opt/approx_kl_k3", "Opt/approxkl", "approx_kl", "kl"),
    "clipfrac":  ("train/clip_fraction", "Opt/clipfrac", "clip_fraction", "clipfrac"),
    "entropy":   ("train/dist_entropy", "Opt/entropy", "train/entropy", "dist_entropy"),
    "sigma":     ("train/sigma_mean", "sigma_mean"),
    "ev":        ("VFStats/EV", "train/explained_variance", "explained_variance"),
    "ep_reward": ("train/mean_episode_reward", "EpRewMean", "ep_rew_mean"),
    "frame_reward": ("Misc/FrameRewMean", "FrameRewMean"),
    "ep_len":    ("EpLenMean", "train/mean_episode_length", "ep_len_mean"),
    "steps":     ("train/total_num_steps", "Misc/InteractCount", "total_num_steps"),
}

#: (canonical, human question, predicate, scope, why this range).
#:
#: **scope matters and getting it wrong hid a real finding.** "sustained" checks read the SECOND
#: HALF, because an early transient is not a defect -- clip_fraction is high in the first updates of
#: every healthy run. "trajectory" checks read the WHOLE series, because they are about where a
#: quantity started and ended.
#:
#: [Claude 2026-09-09] The first version ran every check on the tail. On the real idaac cell, sigma
#: falls 0.996 -> 0.167 -- an unmistakable collapse -- and the tail-scoped test did NOT flag it,
#: because within the second half sigma only goes 0.35 -> 0.167, which is not a quarter. The auditor
#: reported two flags where three were present, and reported them on the one run whose diagnostics
#: had already been read by hand. A test written against synthetic data caught it.
CHECKS = (
    ("kl", "policy updates far outside the trust region",
     lambda v: median(v) > 0.2, "sustained",
     "PPO targets roughly 0.01-0.05 nats per update and implementations that early-stop on KL "
     "trigger near 0.015. A sustained median above 0.2 means the step the hyperparameters were "
     "tuned for is not the step being taken."),
    ("clipfrac", "most of the batch is on the clipping boundary",
     lambda v: median(v) > 0.5, "sustained",
     "A healthy PPO run clips 0.1-0.3 of samples. Above 0.5 the surrogate is mostly flat and the "
     "gradient is dominated by the clip edge rather than by the advantage."),
    ("kl", "the policy is not moving between sampling and update",
     lambda v: median(v) < 1e-6, "sustained",
     "A KL at 1e-6 or below is float noise, not a small step. Either the policy genuinely does not "
     "move, or the diagnostic is evaluated where the ratio is 1 by construction -- both mean this "
     "column cannot be read as evidence that training happened."),
    ("sigma", "the policy has collapsed toward determinism",
     lambda v: v[-1] < 0.25 * v[0] if v[0] else False, "trajectory",
     "Sigma falling below a quarter of its initial value with no entropy bonus resisting it is the "
     "signature of a run that has stopped exploring. idaac reached 0.188 from 0.996."),
    ("sigma", "the policy scale never moved",
     lambda v: abs(v[-1] - v[0]) < 0.02 * abs(v[0]) if v[0] else False, "trajectory",
     "Sigma unchanged to within 2% over an entire run means the scale head received no effective "
     "gradient. ppg moved 1.00 -> 1.01 over half a million frames."),
    ("ev", "the value function does not explain the returns",
     lambda v: median(v) < 0.1, "sustained",
     "Explained variance near zero means the critic is not fitting, so advantages are noise and no "
     "policy-gradient method can work regardless of the policy-side settings."),
)


def median(values: list[float]) -> float:
    s = sorted(values)
    n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def _from_csv(path: pathlib.Path) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    with path.open() as fh:
        for row in csv.DictReader(fh):
            for key, raw in row.items():
                if not key or raw in (None, ""):
                    continue
                try:
                    out.setdefault(key, []).append(float(raw))
                except ValueError:
                    continue
    return out


TABLE_ROW = re.compile(r"^\|\s*([A-Za-z_][A-Za-z0-9_/]*)\s*\|\s*(-?[0-9][0-9.eE+-]*)\s*\|\s*$")

#: Warnings a trainer prints about its OWN optimisation being reduced. These are not diagnostics to
#: be ranged-checked -- they are the trainer saying it could not do what it was configured to do, and
#: the reason this list exists is that one of them was printed 289 times and nobody read it.
#:
#: [Claude 2026-09-09] `Warning: nminibatch > ntrain!! (32 > 1)` in the live ppg cell. PPG minibatches
#: along the BATCH dimension, `num_envs=1` leaves nothing to split, so `nminibatch` was clamped 32 to
#: 1 and, with `n_epoch_pi=1`, the policy took exactly ONE gradient step per iteration -- 256 for the
#: whole 524k-frame run instead of 8,192. It also explains that run's `clipfrac` of exactly 0.000 and
#: `approxkl` of 1e-13: with a single minibatch the ratio is 1 by construction every time it is
#: measured, so the diagnostics could never have reported the problem they were being read for.
TRAINER_WARNINGS = (
    (re.compile(r"nminibatch > ntrain!!\s*\((\d+) > (\d+)\)"),
     "the trainer CLAMPED its own minibatch count",
     "PPG-family code splits minibatches along the batch (environment) dimension. With one "
     "environment there is nothing to split, so `nminibatch` collapses to 1 and the policy takes a "
     "single gradient step per iteration. Whatever `--nminibatch` says, that many updates did not "
     "happen. It also pins clipfrac at 0 and approxkl at float noise, because a single minibatch is "
     "always measured at ratio 1 -- so the range checks above CANNOT see this and this line must."),
)


def _from_log(path: pathlib.Path) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for line in path.read_text(errors="replace").splitlines():
        m = TABLE_ROW.match(line.strip())
        if not m:
            continue
        try:
            out.setdefault(m.group(1), []).append(float(m.group(2)))
        except ValueError:
            continue
    return out


#: Below this many points a trajectory check compares a run against itself over almost no history.
#: [Claude 2026-09-09] A 2-iteration smoke run tripped "the policy scale never moved" and "the value
#: function does not explain the returns", both of which are simply true of any run that has barely
#: started. A check that fires on every smoke run is a check people learn to ignore.
MIN_POINTS = 6


def trainer_warnings(target: pathlib.Path) -> list[tuple[str, str, str, int]]:
    """Warnings the trainer printed about its own optimisation, counted."""
    files = [target] if target.is_file() else sorted(target.rglob("*.log"))
    out = []
    for pattern, headline, why in TRAINER_WARNINGS:
        total, sample = 0, ""
        for f in files:
            try:
                text = f.read_text(errors="replace")
            except OSError:
                continue
            found = pattern.findall(text)
            if found:
                total += len(found)
                if not sample:
                    m = pattern.search(text)
                    sample = m.group(0) if m else ""
        if total:
            out.append((headline, why, sample, total))
    return out


def collect(target: pathlib.Path) -> list[tuple[str, dict[str, list[float]]]]:
    """One entry PER CELL, never pooled.

    [Claude 2026-09-09] The first version merged every log under the target into one series set. On
    `card0-20260909-013936`, which ran `idaac-s101` and `ppg-s1` in one job, that concatenated two
    families' diagnostics into a single column and reported flags against the mixture -- the exact
    cross-family pooling this file's own header refuses. Each log or CSV is its own unit, named.
    """
    if target.is_file():
        files = [target]
    else:
        files = sorted(target.rglob("progress*.csv")) + sorted(target.rglob("*.log"))
    out: list[tuple[str, dict[str, list[float]]]] = []
    for f in files:
        got = _from_csv(f) if f.suffix == ".csv" else _from_log(f)
        if got:
            out.append((str(f), got))
    # [Claude 2026-09-09] The job-level log is a POOLED superset: the runner tees every cell's
    # output into it, so on a two-cell job its table blocks are idaac's and ppg's interleaved, and
    # checking it means checking the mixture. Per-cell files exist beside it and are the real unit.
    # Verified on card0-20260909-013936, where the job.log unit flagged two conditions produced by
    # the concatenation while every per-cell unit was correctly reported as too short to judge.
    per_cell = [(name, raw) for name, raw in out if f"{os.sep}cells{os.sep}" in name]
    return per_cell if per_cell else out


def resolve(raw: dict[str, list[float]]) -> dict[str, tuple[str, list[float]]]:
    found: dict[str, tuple[str, list[float]]] = {}
    for canonical, aliases in SERIES.items():
        for alias in aliases:
            if raw.get(alias):
                found[canonical] = (alias, raw[alias])
                break
    return found


def reward_scale_check(found: dict[str, tuple[str, list[float]]]) -> str | None:
    """EpRew must equal EpLen x FrameRew when both are raw. When it does not, one is normalised."""
    if not all(k in found for k in ("ep_reward", "frame_reward", "ep_len")):
        return None
    ep = found["ep_reward"][1][-1]
    fr = found["frame_reward"][1][-1]
    ln = found["ep_len"][1][-1]
    if not fr or not ln:
        return None
    implied = fr * ln
    if implied and abs(ep - implied) > 0.25 * max(abs(ep), abs(implied)):
        return (f"episode reward {ep:.4g} but episode length {ln:.4g} x frame reward {fr:.4g} = "
                f"{implied:.4g}. These cannot both be raw, so ONE IS NORMALISED and a summary that "
                f"quotes the wrong one can report the opposite direction. Records carry RAW return "
                f"regardless of training normalisation -- read the offline evaluation, never this.")
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("target", help="a fetched run directory, a progress CSV, or a training log")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any check flags")
    args = ap.parse_args()

    target = pathlib.Path(args.target)
    if not target.exists():
        print(f"no such path: {target}")
        return 2

    units = collect(target)
    units = [(name, resolve(raw)) for name, raw in units]
    units = [(name, found) for name, found in units if found]
    if not units:
        print(f"No recognised diagnostic series under {target}.")
        print("Nothing was checked, which is NOT the same as nothing being wrong. If this run does")
        print("emit diagnostics under other names, add them to SERIES rather than reading it clean.")
        return 2

    print(f"TRAINING DIAGNOSTICS -- {target}")
    print(f"  {len(units)} unit(s), reported separately: diagnostics from different families come "
          f"from\n  different loggers and are never pooled or compared.\n")
    worst = 0
    for name, found in units:
        worst = max(worst, report(name, found))

    warned = trainer_warnings(target)
    for headline, why, sample, total in warned:
        print(f"  TRAINER WARNING x{total}: {headline}")
        print(f"      {sample}")
        for i in range(0, len(why), 86):
            print(f"      {why[i:i + 86]}")
        print()
    if warned:
        print("  A trainer warning outranks every range check above: the ranges describe how an")
        print("  optimiser behaved, and this says it did not run the optimisation configured.\n")

    return 1 if (args.strict and (worst or warned)) else 0


def report(name: str, found: dict[str, tuple[str, list[float]]]) -> int:
    print(f"=== {name}")

    steps = found.get("steps")
    if steps:
        print(f"  {steps[0]:<24} {steps[1][0]:.4g} -> {steps[1][-1]:.4g}  ({len(steps[1])} points)")
    for canonical in ("kl", "clipfrac", "entropy", "sigma", "ev", "ep_reward", "frame_reward"):
        if canonical not in found:
            continue
        name, v = found[canonical]
        print(f"  {name:<24} first={v[0]:<12.4g} median={median(v):<12.4g} last={v[-1]:.4g}")
    print()

    flags: list[tuple[str, str, str]] = []
    longest = max((len(v) for _, v in found.values()), default=0)
    if longest < MIN_POINTS:
        print(f"  ONLY {longest} POINT(S). Too short to judge: a run that has barely started has a")
        print("  flat sigma and an unfitted critic by definition. Reported, not checked.\n")
        return 0
    for canonical, question, predicate, scope, why in CHECKS:
        if canonical not in found:
            continue
        name, v = found[canonical]
        window = v if scope == "trajectory" else (v[len(v) // 2:] or v)
        try:
            hit = predicate(window)
        except (IndexError, TypeError, ZeroDivisionError):
            continue
        if hit:
            flags.append((name, question, why))

    scale = reward_scale_check(found)

    missing = [c for c in ("kl", "clipfrac", "sigma", "ev") if c not in found]
    if missing:
        print(f"  NOT CHECKED, no series found: {', '.join(missing)}")
        print("  A check that could not run must not read as one that passed.\n")

    if flags:
        print(f"  {len(flags)} FLAG(S):\n")
        for name, question, why in flags:
            print(f"    [{name}] {question}")
            for i in range(0, len(why), 86):
                print(f"        {why[i:i + 86]}")
            print()
    else:
        print("  No diagnostic left its expected range.\n")

    if scale:
        print("  REWARD SCALES DISAGREE:")
        for i in range(0, len(scale), 86):
            print(f"      {scale[i:i + 86]}")
        print()

    print("  These ranges describe PPO-family optimisation, not a comparison to another run.")
    print("  A flag is a question to answer, and for a deliberate deviation it may be expected.\n")
    return 1 if (flags or scale) else 0


if __name__ == "__main__":
    raise SystemExit(main())
