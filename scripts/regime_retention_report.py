#!/usr/bin/env python3
"""Regime retention from paired `eval_across_scenes.py --json` dumps.

`eval_across_scenes.py` reports SCENE retention: held-out scenes against scene 0, with the
regime held fixed. This reports the other axis -- the same scenes under `train` and under
`eval-easy`. C43 is the register entry saying the train-regime denominator was never available;
these are the first numbers that have one.

The two quantities are not combined and not averaged together. They answer different questions
and nothing here has shown them to be the same quantity.

Three things this refuses to do, each because the alternative manufactures a result:

1. **A ratio whose denominator is at chance is not reported.** The 50k drqv2/Door checkpoint
   returns ~2.0 on the training scene; a uniform random policy on the same scene returns ~1.5.
   The agent has not learned the task, so dividing by its score compares two chance-level
   numbers and the ratio carries no information about retention.

   The first version of this guard asked whether the denominator was small relative to the
   *spread of the returns themselves* -- 2.0 with sd 0.8 looks perfectly well-determined, so it
   passed, and the report would have printed a confident ratio. The quantity that matters is
   not statistical precision but whether the agent can do the task at all, and that is only
   visible against a measured random-policy floor. Rows whose denominator does not clear the
   floor report AT-CHANCE and print the raw means.

2. **A difference smaller than the seed floor is not called a difference.** Each run carries a
   within-scene control: scene 0 again at a different episode seed. That spread is the
   resolution limit. A regime gap inside it reports UNRESOLVED, not "no effect" -- the design
   did not resolve it, which is a statement about the design.

3. **Return retention and success-rate retention are reported separately and never averaged.**
   They share a name and a lineage; that is not evidence they are the same quantity.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
# Which archive the report reads.
#
# `results/regime-retention/` holds grids measured before C69/C70, when the evaluator left object
# placement unseeded and torch free to pick nondeterministic kernels. They are real measurements
# and are NOT deleted: C67's byte-identity finding lives in them, and they are the evidence for how
# large the pre-fix variation was.
#
# `results/regime-retention-c69/` holds the same checkpoints re-derived deterministically, so a
# reported number should come from there and it wins when present. The pre-C69 set stays reachable
# with `--archive pre-c69`, because "the old numbers are gone" and "the old numbers are superseded"
# are different claims and only the second is true.
RESULTS_C69 = ROOT / "results" / "regime-retention-c69"
RESULTS_PRE = ROOT / "results" / "regime-retention"
RESULTS = RESULTS_C69 if any(RESULTS_C69.glob("*__train.json")) else RESULTS_PRE
BOOT = 10_000
MODES = ("train", "eval-easy")
FLOOR_TAG = "random-floor"
# A denominator has to represent COMPETENCE, not just a non-zero success count. The guard below
# originally fired only at exactly 0 successes, and an adversarial re-check found the hole: a
# policy scoring 1/20 on every scene -- never more -- passed it and was pooled into a retention
# of 0.947, which read as robustness when it was a shaped-reward plateau from a policy that
# essentially never solves the task. 0.25 is a stated line, not a derived one: below it the
# denominator is dominated by shaping rather than by task success, and a ratio built on it is
# not measuring retention of a skill.
MIN_DENOM_SUCCESS = 0.25

# C65. A retention ratio whose entire confidence interval sits above this is refused rather than
# reported: it says the policy does better away from its declared training regime, which is a
# statement about the checkpoint's provenance rather than about generalisation. 1.0 is the
# meaningful line and is not a tuned threshold -- the random-policy control measures 1.02, so a
# policy with nothing to lose already sits at it, and the separation this screen relies on comes
# from the CI, not from moving this number.
CONTAMINATION_RATIO = 1.0
DENOM = "train"


def boot_ratio(num: np.ndarray, den: np.ndarray, rng: np.random.Generator) -> tuple:
    """Percentile CI on mean(num)/mean(den), resampling episodes within each arm."""
    n = rng.choice(num, size=(BOOT, num.size), replace=True).mean(axis=1)
    d = rng.choice(den, size=(BOOT, den.size), replace=True).mean(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.where(np.abs(d) > 1e-9, n / d, np.nan)
    r = r[np.isfinite(r)]
    if r.size < BOOT // 10:
        return (float("nan"), float("nan"))
    return (float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5)))


def load(tag: str) -> dict | None:
    p = RESULTS / f"{tag}.json"
    return json.loads(p.read_text()) if p.exists() else None


def arm(d: dict, scene: str, key: str = "returns") -> np.ndarray:
    return np.asarray(d["scenes"][scene][key], dtype=float)


def sr(d: dict, scenes) -> tuple[float, int, int]:
    """Success RATE from the per-scene counts. `run_scene` returns a count, not a list."""
    ns = sum(int(d["scenes"][s]["n_success"]) for s in scenes)
    ne = sum(int(d["scenes"][s]["n_episodes"]) for s in scenes)
    return (ns / ne if ne else float("nan")), ns, ne


def above_floor(sample: np.ndarray, floor: np.ndarray, rng) -> tuple[bool, float, float]:
    """Bootstrap CI on mean(sample) - mean(floor); True iff it excludes zero from above."""
    a = rng.choice(sample, size=(BOOT, sample.size), replace=True).mean(axis=1)
    b = rng.choice(floor, size=(BOOT, floor.size), replace=True).mean(axis=1)
    d = a - b
    lo, hi = float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))
    return (lo > 0.0), lo, hi


def report_ckpt(ck: str, rng: np.random.Generator) -> dict | None:
    num_mode = [m for m in MODES if m != DENOM][0]
    tr, ev = load(f"{ck}__{DENOM}"), load(f"{ck}__{num_mode}")
    if tr is None or ev is None:
        have = [m for m, x in ((DENOM, tr), (num_mode, ev)) if x is not None]
        print(f"\n{ck}: incomplete pair (have: {have or 'neither'}) -- nothing reported")
        return None

    # C69. Grids written before 2026-08-25 were measured while `run_scene` left global numpy
    # unseeded, so `UniformRandomSampler` -- which places the door and its handle -- ran on
    # whatever RNG state the process happened to have. Two grids of the same checkpoint at the
    # same recorded seed therefore differ by ~1.6 cm of door position. Announced per checkpoint
    # rather than once, because the archive will be a mix as grids are re-derived, and a reader
    # comparing two numbers needs to know whether BOTH sides are reproducible.
    unseeded = [m for m, d in ((DENOM, tr), (num_mode, ev)) if not d.get("placement_seeded")]
    if unseeded:
        print(f"\n  ! {ck}: object placement NOT seeded in {'/'.join(unseeded)} "
              f"-- pre-C69 grid, not reproducible; the recorded seed did not control where the "
              f"door sat.")

    frames = tr["frames"]
    print(f"\n{'='*74}\n{ck}  --  {tr['task']}, {frames} frames, "
          f"{tr['episodes']} episodes/scene/regime")
    print(f"{'='*74}")

    # Resolution floor from the within-scene control: scene 0, same regime, different seed.
    floors = {}
    for name, d in ((DENOM, tr), (num_mode, ev)):
        c = d.get("control")
        if not c or "0" not in d["scenes"]:
            continue
        a, b = arm(d, "0", "returns"), np.asarray(c["returns"], dtype=float)
        if abs(a.mean()) > 1e-9:
            floors[name] = abs(b.mean() - a.mean()) / abs(a.mean())
        print(f"  control ({name}): scene 0 seed {d['seed']} = {a.mean():7.2f}   "
              f"seed {d['control_seed']} = {b.mean():7.2f}   "
              f"-> seed-only ratio shift {floors.get(name, float('nan')):.3f}")
    floor = max(floors.values()) if floors else float("nan")
    if floors:
        print(f"  RESOLUTION FLOOR: a regime gap below {floor:.1%} is not resolved by this design")
    else:
        print("  no control ran -- every gap below is UNINTERPRETABLE, not merely unresolved")

    scenes = sorted(set(tr["scenes"]) & set(ev["scenes"]), key=int)

    fl = load(f"{FLOOR_TAG}__{DENOM}")
    if fl is None:
        print("\n  NO RANDOM-POLICY FLOOR MEASURED. Every retention below would be a ratio whose")
        print("  denominator has not been shown to differ from chance. Nothing is reported.")
        print(f"  Run: scripts/eval_across_scenes.py --random-policy --mode train "
              f"--json {RESULTS}/{FLOOR_TAG}__{DENOM}.json")
        return None
    floor_pool = np.concatenate([arm(fl, s) for s in sorted(fl["scenes"], key=int)])
    fsr, fns, fne = sr(fl, sorted(fl["scenes"], key=int))
    print(f"\n  random-policy floor ({DENOM} regime): mean {floor_pool.mean():.3f} "
          f"sd {floor_pool.std():.3f}, successes {fns}/{fne}")

    # Column headers are derived from DENOM, never hardcoded. Written literally at first, so
    # that --denominator eval-easy printed the denominator's numbers under a "train ret" header
    # -- a mislabelled results column, which is the failure most likely to be believed.
    print(f"\n  {'scene':>5}  {(DENOM + ' ret'):>12}  {(num_mode + ' ret'):>13}  "
          f"{'retention':>10}  {'95% CI / vs floor':>18}  verdict")
    print(f"  {'-'*72}")
    rows = []
    for s in scenes:
        t, e = arm(tr, s), arm(ev, s)
        ok, dlo, dhi = above_floor(t, floor_pool, rng)
        if not ok:
            print(f"  {s:>5}  {t.mean():12.2f}  {e.mean():13.2f}  {'--':>10}  "
                  f"{f'[{dlo:+.1f},{dhi:+.1f}]':>18}  AT-CHANCE")
            rows.append({"scene": s, "verdict": "AT-CHANCE", "train": t.mean(),
                         "eval": e.mean(), "vs_floor": [dlo, dhi]})
            continue
        r = e.mean() / t.mean()
        lo, hi = boot_ratio(e, t, rng)
        n_succ = int(tr["scenes"][s]["n_success"])
        n_eps = int(tr["scenes"][s]["n_episodes"])
        sr_den = n_succ / n_eps if n_eps else 0.0
        if sr_den < MIN_DENOM_SUCCESS:
            # Clears the random floor on shaped return, but never opens the door. A ratio here
            # is retention of reward SHAPING, not of the task -- the agent has no success to
            # retain. Printed, because it is a real number about a real quantity, but kept out
            # of the pooled figure: pooling it with rows that do solve the task would average
            # two different quantities, which is the one thing this file exists not to do.
            tag = "UNSOLVED-DENOM" if n_succ == 0 else f"WEAK-DENOM({n_succ}/{n_eps})"
            print(f"  {s:>5}  {t.mean():12.2f}  {e.mean():13.2f}  {r:10.3f}  "
                  f"[{lo:7.3f},{hi:7.3f}]  {tag}")
            rows.append({"scene": s, "verdict": "UNSOLVED-DENOMINATOR", "retention_shaping": r,
                         "ci": [lo, hi], "train": t.mean(), "eval": e.mean(),
                         "den_success": sr_den})
            continue
        if np.isfinite(floor) and abs(r - 1.0) < floor:
            v = "UNRESOLVED"
        elif lo <= 1.0 <= hi:
            v = "CI-SPANS-1"
        else:
            v = "RETAINS" if r >= 1.0 else "DROPS"
        print(f"  {s:>5}  {t.mean():12.2f}  {e.mean():13.2f}  {r:10.3f}  "
              f"[{lo:7.3f},{hi:7.3f}]  {v}")
        rows.append({"scene": s, "verdict": v, "retention": r, "ci": [lo, hi],
                     "train": t.mean(), "eval": e.mean()})

    usable = [r for r in rows if "retention" in r]   # excludes AT-CHANCE and UNSOLVED
    n_chance = sum(r["verdict"] == "AT-CHANCE" for r in rows)
    n_unsolved = sum(r["verdict"] == "UNSOLVED-DENOMINATOR" for r in rows)
    print(f"\n  scenes whose denominator clears the random floor AND solves the task at least "
          f"{MIN_DENOM_SUCCESS:.0%} of the time: {len(usable)}/{len(rows)}")
    if n_chance or n_unsolved:
        print(f"    excluded: {n_chance} at chance, {n_unsolved} above chance but never "
              f"successful.\n    Neither is a small retention -- both are absences of one.")
    contaminated = False
    if usable:
        pooled_t = np.concatenate([arm(tr, r["scene"], "returns") for r in usable])
        pooled_e = np.concatenate([arm(ev, r["scene"], "returns") for r in usable])
        R = pooled_e.mean() / pooled_t.mean()
        lo, hi = boot_ratio(pooled_e, pooled_t, rng)
        print(f"  POOLED regime retention (return): {R:.3f}  95% CI [{lo:.3f}, {hi:.3f}]")
        print(f"    pooled over the {len(usable)} usable scenes only -- NOT RL-ViGen's protocol,")
        print(f"    which averages all ten. Dropping scenes changes the estimand; the number")
        print(f"    above answers 'on scenes where the agent had learned something'.")

    # C65: retention above 1 is a provenance alarm, not a result.
    #
    # Computed over ALL scenes, deliberately, and NOT over the guarded `usable` set above. These
    # are different estimands and they point in opposite directions on the very checkpoints this
    # screen exists to catch: `snapshot_100k_frames` pools to 2.51 across all ten scenes and to
    # 0.010 across the one scene that clears the denominator guard. The guarded ratio answers
    # "how much skill survives where the agent had skill"; the all-scene ratio answers "which
    # regime does this policy prefer", and only the second is evidence about provenance. Keying
    # the alarm to the guarded ratio would have made it silent on every checkpoint we already
    # know is contaminated -- the same class of error as pointing the floor guard at the returns'
    # spread (C55) and at significance, twice, before measuring the floor itself.
    #
    # Keyed to the CI's lower bound rather than the point estimate: a ratio slightly above 1 is
    # ordinary noise -- the random-policy control measures 1.02 and is contaminated by nothing.
    all_t = np.concatenate([arm(tr, r["scene"], "returns") for r in rows])
    all_e = np.concatenate([arm(ev, r["scene"], "returns") for r in rows])
    R_all = all_e.mean() / all_t.mean()
    lo_all, hi_all = boot_ratio(all_e, all_t, rng)
    print(f"\n  all-scene pooled ratio (provenance screen, NOT retention): {R_all:.3f} "
          f"95% CI [{lo_all:.3f}, {hi_all:.3f}]")
    if lo_all > CONTAMINATION_RATIO:
        contaminated = True
        print(f"\n  *** CONTAMINATION ALARM -- DO NOT REPORT {R_all:.3f} AS RETENTION ***")
        print(f"    The whole 95% CI [{lo_all:.3f}, {hi_all:.3f}] sits above "
              f"{CONTAMINATION_RATIO:.1f}: this policy performs *better* on the")
        print(f"    held-out regime than on the one it is recorded as training in. A correctly")
        print(f"    trained policy does not do that. The likely reading is that the denominator")
        print(f"    is not the regime this checkpoint trained in -- i.e. a defect in the")
        print(f"    checkpoint's provenance, not in this evaluation. See C54 and C65; re-run with")
        print(f"    --denominator {num_mode} to read it the other way round.")

    # Success rate, separately and deliberately not merged with the above.
    tsr, tn, td = sr(tr, scenes)
    esr, en, ed = sr(ev, scenes)
    print(f"\n  success rate: {DENOM} {tsr:.3f} ({tn}/{td})   "
          f"{num_mode} {esr:.3f} ({en}/{ed})", end="")
    if tsr < 0.02:
        print("   -> SR retention undefined (train SR ~ 0; the agent never solves it)")
    else:
        print(f"   -> SR retention {esr/tsr:.3f}")
    print("    reported beside return retention, not averaged with it. Same name, same "
          "lineage,\n    no evidence they are the same quantity (CLAUDE.md null).")
    return {"ckpt": ck, "frames": frames, "rows": rows, "floor": floor,
            "contaminated": contaminated}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", choices=("auto", "c69", "pre-c69"), default="auto",
                    help="which grid archive to read. 'auto' prefers the deterministic post-C69 "
                         "set and falls back to the pre-C69 one; 'pre-c69' reads the grids "
                         "measured before object placement was seeded -- real measurements, but "
                         "not reproducible (C69).")
    ap.add_argument("--denominator", choices=MODES, default="train",
                    help="which regime goes UNDER the line. This is not a formatting choice: "
                         "retention means 'held-out over training', so naming the denominator "
                         "names which regime you are claiming the policy trained on. For the "
                         "archived drqv2 checkpoints that claim is contested -- see C54 -- and "
                         "the pixel evidence points at eval-easy, not train.")
    a = ap.parse_args(argv)

    # Honour --archive, and always say which one was read: a report that does not name its source
    # invites a reader to assume the deterministic set when it silently fell back to the other.
    global RESULTS
    if a.archive == "c69":
        RESULTS = RESULTS_C69
    elif a.archive == "pre-c69":
        RESULTS = RESULTS_PRE
    print(f"archive: {RESULTS.name}"
          + ("  (deterministic, post-C69)" if RESULTS is RESULTS_C69
             else "  (PRE-C69 -- object placement was not seeded; not reproducible)"))
    global DENOM
    DENOM = a.denominator
    rng = np.random.default_rng(0)
    if not RESULTS.exists():
        print(f"no results at {RESULTS}")
        return 1
    cks = sorted({p.name.split("__")[0] for p in RESULTS.glob("*.json")
                  if not p.name.startswith(FLOOR_TAG)},
                 key=lambda c: (c != "snapshot_50k_frames", c))
    if not cks:
        print(f"no dumps in {RESULTS} yet")
        return 1
    print(f"REGIME RETENTION -- numerator {[m for m in MODES if m != DENOM][0]!r}, "
          f"denominator {DENOM!r}")
    print(f"  The denominator is the regime being claimed as the training condition. For the")
    print(f"  archived checkpoints that claim is contested (C54): their stored training pixels")
    print(f"  match eval-easy, not train. Re-run with --denominator eval-easy to read it the")
    print(f"  other way, and do not report one direction without saying which it is.")
    print("The scene axis is held; the regime varies. This is not the scene retention that")
    print("eval_across_scenes.py prints, and the two are not comparable without an argument.")
    out = [r for ck in cks if (r := report_ckpt(ck, rng))]
    print(f"\n{len(out)} checkpoint(s) reported.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
