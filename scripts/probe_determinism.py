#!/usr/bin/env python3
"""Do two same-seed runs of a clone agree? -- `docs/CONSTRUCTION.md` C20, screen (b).

Screen (a) (`scripts/audit_seed_control.py`) established that eleven of twelve baselines declare
a seed and wire it to the RNGs. That is a claim about SOURCE. It does not establish that two runs
with that seed produce the same trajectory, because a seeded run still diverges through
nondeterministic kernels, thread scheduling, or an RNG nobody seeded. Only running it settles it.

## The two questions, which are not the same

    same seed, twice   -> agree?    determinism. If no, a "seed" does not name a run.
    different seeds    -> differ?   liveness. If no, the knob turns nothing.

**The cross-seed arm is the positive control.** If different seeds also agree, this probe cannot
distinguish runs at all -- a truncated log, a fingerprint over constant columns -- and the
same-seed agreement is an artefact rather than determinism. That is reported UNINTERPRETABLE,
never as a pass. A null needs a stated detectable effect or it is an unfinished measurement.

## What is fingerprinted, and what is deliberately dropped

Wall-clock columns (`fps`, `total_time`, `time`, `duration`) are dropped: they differ between any
two runs on any machine and would make every comparison read as nondeterministic -- a false
positive in the direction that looks like rigour. The metric stream itself is kept.

Run sizes come from `runnable/_launch/smoke_all.sh`, which already tunes each clone to the
smallest run that takes real gradient steps. Runs are strictly SEQUENTIAL: one GPU, and a swap
budget the owner has asked not to exhaust.

## What a DETERMINISTIC verdict here does NOT mean

It is a claim about a few hundred steps, and it does not extend to a full run. C41 measured two
runs of the same configuration AND the same seed agreeing exactly at frames 0 and 10,000 and then
separating -- disagreeing by up to 48.5% at intermediate eval points, with the ranking inverting
at 40k -- while **both finished at `success_rate` 1.0**. Same destination, noisy path. So this
probe detects a **dead seed knob** and **gross
nondeterminism** -- both of which would invalidate a 5-seed design outright -- and says nothing
about whether a 100k-frame run is reproducible. On this hardware, at least one baseline is known
not to be.

Stated because "rad is deterministic" is exactly the sentence that would otherwise get quoted
back later at a scale it was never measured at.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import pathlib
import re
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
LAUNCH = ROOT / "runnable" / "_launch"
DROP = re.compile(r"^(fps|total_time|time|duration|eta|elapsed)$", re.I)


# Set by main() so a follow-up can vary ONE thing against an otherwise identical recipe --
# `--procs 1` to ask whether parallel collection is a baseline's reason for not reproducing,
# `--extra device=cpu` to ask whether the backend is. Kept as module state rather than threaded
# through every recipe branch, because the recipes are deliberately per-clone and duplicated.
PROCS: str | None = None
EXTRA: list[str] = []


def recipe(name: str, seed: int | None, out: pathlib.Path) -> tuple[list[str], str]:
    L = str(LAUNCH)
    nproc = PROCS or "4"
    if name in ("rad", "soda"):
        return (["bash", f"{L}/dmc_gb.sh", name, "Door", str(seed), "--train_steps", "400",
                 "--init_steps", "100", "--eval_freq", "300", "--eval_episodes", "1"], "stdout")
    if name == "idaac":
        return (["bash", f"{L}/idaac.sh", "idaac", "Door", nproc, "--num_steps", "128",
                 "--num_mini_batch", "4", "--log_interval", "4", "--num_env_steps", "2560",
                 "--seed", str(seed)], "stdout")
    if name == "ibac_sni":
        return (["bash", f"{L}/ibac_sni.sh", "Door", "1", "--frames", "1300",
                 "--frames-per-proc", "64", "--batch-size", "32", "--epochs", "1",
                 "--seed", str(seed)], "stdout")
    if name == "ctrl":
        return (["bash", f"{L}/ctrl.sh", "Door", nproc, "--n_steps=16", "--n_minibatch=2",
                 "--train_steps=2600", "--cluster_len=4", "--n_minibatch_ctrl=1",
                 f"--seed={seed}"], "stdout")
    if name == "ppg":
        # No seed knob exists (C20). Two runs are compared anyway: the question for ppg is not
        # "does the seed control it" but "how far apart do two identical invocations land".
        return (["bash", f"{L}/ppg.sh", "Door", "8", "--n_pi", "1", "--n_aux_epochs", "1",
                 "--arch", "dual"], "stdout")
    if name == "alda":
        return (["bash", f"{L}/alda.sh", "--spec.trainer.config.n_train_steps=1200",
                 f"--spec.trainer.config.seed={seed}"], "stdout")
    extra = ["device=cpu"] if name == "curl" else []
    return (["bash", f"{L}/rlvigen.sh", name, "Door", "num_train_frames=1300",
             "num_seed_frames=600", "eval_every_frames=1000", "num_eval_episodes=1",
             f"seed={seed}", f"hydra.run.dir={out}"] + extra + EXTRA, "csv")


def fingerprint_csv(d: pathlib.Path) -> tuple[str, int]:
    chunks, rows = [], 0
    for fn in ("eval.csv", "train.csv"):
        p = d / fn
        if not p.exists():
            continue
        with p.open() as f:
            r = csv.DictReader(f)
            keep = [c for c in (r.fieldnames or []) if not DROP.match(c)]
            for row in r:
                chunks.append("|".join(f"{c}={row[c]}" for c in keep))
                rows += 1
    return hashlib.sha1("\n".join(chunks).encode()).hexdigest()[:16], rows


# Strip the timing FIELD, never the line that carries it. Dropping whole lines threw away every
# metric `ibac_sni` emits: it prints `FPS 0071` in the same line as H, V, pL, vL, kl and SR, so a
# line-level filter discarded 21 updates of real signal and left a one-value fingerprint. The
# probe reported UNINTERPRETABLE rather than a false verdict -- the control did its job -- but the
# measurement was lost.
TIMING_FIELD = re.compile(r"(?i)\b(fps|total_time|elapsed|duration|eta|sec|s/it|it/s)\b"
                          r"\s*[:=]?\s*-?[\d.]+")
# Wall-clock also appears with the NUMBER FIRST ("PPO took 1.134254 seconds") and inside absl /
# glog line prefixes ("I0819 07:27:14.912374 ..."). Neither matches TIMING_FIELD, which expects
# keyword-then-number. Both slipped into `ctrl`'s fingerprint and produced a NONDETERMINISTIC
# verdict for a baseline that is reproducible -- twice, at four envs and at one. Lines matching
# either are dropped whole: they carry no metric.
TIMING_LINE = re.compile(r"(?i)took\s+[\d.]+\s*second|^[IWE]\d{4} \d{2}:\d{2}:\d{2}\.\d+"
                         r"|\d{2}:\d{2}:\d{2}\.\d{6}")


def fingerprint_stdout(text: str) -> tuple[str, int]:
    """Every decimal number on a line, once timing fields are removed.

    The first version required **three or more decimal places**, on the theory that metric-
    precision floats are the signal and short numbers are counters. That was wrong in the
    direction that matters. `idaac` logs `test/mean_episode_reward` as `1.27`, and two runs of it
    at one process differ *there* while agreeing on the six high-precision values the filter did
    keep. The probe therefore called it DETERMINISTIC, and that verdict was published before a
    full-output comparison caught it.

    The lesson is specific: a fingerprint that samples a *subset* of the output can only ever
    produce false agreements, never false disagreements, so its errors all point the same way --
    toward "reproducible". Any DETERMINISTIC verdict is only as strong as the fraction of output
    it actually read, which is why `n_values` is reported beside every verdict and why a thin one
    should be distrusted.
    """
    plain = re.sub(r"\x1b\[[0-9;]*m", "", text)
    nums = []
    for line in plain.splitlines():
        if TIMING_LINE.search(line.strip()):
            continue
        nums += re.findall(r"-?\d+\.\d+", TIMING_FIELD.sub(" ", line))
    return hashlib.sha1("\n".join(nums).encode()).hexdigest()[:16], len(nums)


def trial(name, seed, tag, workdir, timeout) -> dict:
    out = workdir / f"{name}_{tag}"
    out.mkdir(parents=True, exist_ok=True)
    argv, kind = recipe(name, seed, out)
    if EXTRA and kind != "csv":
        argv = argv + EXTRA
    t0 = time.time()
    env = dict(os.environ, ALDA_RESULTS=str(out / "alda_results"))
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                           cwd=str(ROOT), env=env)
        rc, text = p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired as e:
        got = e.stdout or b""
        rc, text = -9, (got.decode(errors="replace") if isinstance(got, bytes) else got) + "[TIMEOUT]"
    (out / "run.log").write_text(text)
    fp, n = fingerprint_csv(out) if kind == "csv" else fingerprint_stdout(text)
    # A crashed run still prints numbers, and comparing two crashes measures nothing. Exit code
    # alone cannot tell: `ctrl` exits 1 on SUCCESS (absl calls sys.exit on a tuple return), while
    # `alda` under a forced CPU device exits 1 from an unconditional `.cuda()` in its replay
    # sampler. The traceback is the discriminator that works for both.
    crashed = bool(re.search(r"^Traceback \(most recent call last\):", text, re.M))
    return {"seed": seed, "tag": tag, "rc": rc, "fp": fp, "n_values": n,
            "crashed": crashed, "secs": round(time.time() - t0, 1)}


def verdict(a, b, c) -> tuple[str, str]:
    if a["n_values"] == 0 or b["n_values"] == 0:
        return "NO_SIGNAL", "the run produced no metric values; nothing is established"
    # A run that hit the wall-clock cap did a DIFFERENT AMOUNT OF WORK than its twin, because
    # machine load differs between trials. Its fingerprint therefore differs for reasons that
    # have nothing to do with RNG, and comparing them measures the scheduler. `ppg` is the live
    # case: `interacts_total=100_000_000` is a train_fn default with no CLI flag, so no launcher
    # can bound it by steps. Refusing is the honest answer; a NONDETERMINISTIC verdict here would
    # be an artefact presented as a finding.
    if any(t is not None and t.get("crashed") for t in (a, b, c)):
        return "RUN_FAILED", (
            "a trial ended in a Python traceback, so its numbers are error output rather than a "
            "measurement -- comparing two crashes says nothing about determinism")
    if any(t is not None and t["rc"] == -9 for t in (a, b, c)):
        return "UNBOUNDED_RUN", (
            "a trial hit the wall-clock cap, so the trials did different amounts of work and "
            "their fingerprints are not comparable -- this baseline needs a step budget before "
            "determinism can be asked about it at all")
    same = a["fp"] == b["fp"]
    # `ppg` has no seed knob at all (C20), so its third trial is a THIRD IDENTICAL INVOCATION,
    # not a cross-seed control. Reporting "the control fired" there would be false: nothing was
    # varied, so a disagreement is evidence of nondeterminism and an agreement is evidence of
    # nothing in particular. The unseeded case gets its own verdict rather than borrowing the
    # seeded one's vocabulary.
    if a["seed"] is None:
        if same and (c is None or c["fp"] == a["fp"]):
            return "UNSEEDED_BUT_REPRODUCIBLE", (
                "three identical invocations agreed; the run is reproducible despite having no "
                "seed knob, but nothing here can make it produce a DIFFERENT run on purpose")
        return "UNSEEDED_AND_NONDETERMINISTIC", (
            "identical invocations disagreed and there is no seed to control it -- this baseline "
            "cannot contribute a reproducible row, let alone a 5-seed one")
    if c is None or c["n_values"] == 0:
        return ("AGREES_NO_CONTROL" if same else "DIFFERS_NO_CONTROL",
                "no usable cross-seed control, so liveness is unestablished")
    if c["fp"] == a["fp"]:
        return "UNINTERPRETABLE", (
            "a different seed produced the SAME fingerprint, so this probe cannot resolve runs; "
            "same-seed agreement here is not evidence of determinism")
    return ("DETERMINISTIC" if same else "NONDETERMINISTIC",
            "cross-seed control fired, so the comparison resolves runs")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("baselines", nargs="+")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--other-seed", type=int, default=7)
    ap.add_argument("--timeout", type=int, default=2400)
    ap.add_argument("--workdir", default=os.environ.get("DET_WORK", "/tmp/rlgen_det"))
    ap.add_argument("--out", default="")
    ap.add_argument("--procs", help="override the parallel-env/process count in recipes that take one")
    ap.add_argument("--extra", nargs="*", default=[], help="extra argv appended to the recipe")
    a = ap.parse_args()
    global PROCS, EXTRA
    PROCS, EXTRA = a.procs, list(a.extra)
    work = pathlib.Path(a.workdir); work.mkdir(parents=True, exist_ok=True)
    results = []
    for name in a.baselines:
        seeded = name != "ppg"
        s = a.seed if seeded else None
        print(f"\n=== {name} (seed knob: {'yes' if seeded else 'NO -- C20'})", flush=True)
        A = trial(name, s, "a", work, a.timeout); print(f"    a {A}", flush=True)
        B = trial(name, s, "b", work, a.timeout); print(f"    b {B}", flush=True)
        C = trial(name, a.other_seed if seeded else None, "c", work, a.timeout)
        print(f"    c {C}", flush=True)
        v, why = verdict(A, B, C)
        print(f"    VERDICT {v} -- {why}", flush=True)
        results.append({"baseline": name, "verdict": v, "why": why, "trials": [A, B, C]})
        if a.out:
            pathlib.Path(a.out).write_text(json.dumps(results, indent=2))
    print("\n" + "=" * 58)
    for r in results:
        print(f"  {r['baseline']:<10} {r['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
