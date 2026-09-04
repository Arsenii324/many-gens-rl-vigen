"""Has the shared evaluator earned the right to report each baseline's number?

    python scripts/audit_shared_evaluator.py [--strict]

## Why this exists

`docs/EVAL-PROTOCOL.md` proposes that every baseline be evaluated by **our** offline harness rather
than by its own evaluator, because three of twelve run no periodic training-time evaluation at all
and same-axes metrics are therefore unreachable from training logs
(`scripts/audit_eval_cadence.py`). That proposal buys comparability and **incurs a burden of
proof**: a shared evaluator is a new instrument, and for each baseline we must show it measures what
that baseline's own evaluator measures. The burden is ours, per baseline, and it is not discharged
by the harness running without error.

**The asymmetry that makes this urgent.** If our number comes out *lower* than the baseline's own,
the innocent reading ("their evaluator is generous") and the damaging one ("our harness handicaps
their policy") predict the same observation. [C95](../docs/CONSTRUCTION.md#c95) is the precedent and
it was exactly this shape: a whole methodology reading 12-14x low, with nothing crashing. So
**ours-lower is read more suspiciously than ours-higher** -- but the verdict is GRADED, because
"marginally lower" and "strongly collapsing" are different claims. A harness 8% under its reference
is doing sampling; one 10x under is doing something else, and calling both "suspect" makes the
distinction unusable.

**The floor makes weak evidence look like agreement.** Two numbers that straddle the random-policy
floor of 1.82 ([C55](../docs/CONSTRUCTION.md#c55)) agree about nothing: both describe a policy doing
nothing, and any harness reproduces that. A reconciliation on a floored checkpoint is **not
evidence** and is reported as UNDERPOWERED, not as a pass.

## What it does not do

It does not measure anything. It reads the reconciliations that have been performed and says which
baselines may have a shared-evaluator number reported. Adding a row here without running the
comparison is the failure this file exists to prevent, so every row names its evidence.
"""
from __future__ import annotations

import argparse
import sys

#: The random-policy floor on Door: uniform random, 400 episodes, zero successes (C55).
RANDOM_FLOOR = 1.82

BASELINES = ("drqv2", "svea", "drq", "sgqn", "curl", "rad", "soda",
             "alda", "idaac", "ppg", "ibac_sni", "ctrl")

#: baseline -> (ours, theirs, checkpoint, evidence). `None` means no comparison has been run.
#: A row is added ONLY after the comparison is performed; the evidence field must name where.
RECONCILIATIONS: dict[str, dict | None] = {
    "drqv2": {
        "ours": 131.57, "theirs": 135.71, "checkpoint": "60k, train regime scene 0",
        "evidence": "bt1a4gsqf1h3sd5u72tl (ours, container CPU) against the run's own eval.csv; C95",
        # No per-episode returns were retained for this comparison, so it stays a point ratio and
        # is read as one. Recorded as absent rather than approximated.
        "dispersion": None,
    },
    "idaac": {
        "ours": 9.023, "theirs": 5.347, "checkpoint": "99,328 frames, eval-easy scene 0",
        "evidence": "bt1ip5f8c6mqqm7fd2bn (ours, 20 episodes, container CUDA) against the endpoint "
                    "row of bt1lnh6b11u231cvh4ho's own progress-*.csv (test/mean_episode_reward). "
                    "Supersedes the 1.663-vs-3.01 comparison on the 9,216-frame checkpoint, which "
                    "was UNDERPOWERED: both numbers straddled the floor.",
        "dispersion": {"ours_sd": 6.488, "ours_n": 20, "theirs_n": 10, "theirs_sd": None},
    },
    # ctrl is deliberately absent as a RATIO row. Its reference number is not the same estimand as
    # ours, so dividing them measures nothing: `Eprew200` is a trailing window over ~200 episodes of
    # SUCCESSIVE policies, ours is N episodes of the SAVED policy (COMPARABILITY_CONTRACT §5d).
    # Measured 2026-09-04 on the 2,560-frame checkpoint: its cell reported train-regime 3.049 and
    # our harness 36.699 -- 12x HIGHER, which is what a window dominated by early policies should
    # look like beside the terminal one. That is corroboration of the estimand gap, not a
    # reconciliation of the instruments, and recording it as a PASS or a COLLAPSE would be a
    # category error either way. ctrl's burden is discharged only against a fixed-N reference,
    # which requires adapting evaluate_ppo.py -- the known "ADAPT" item.
}


def dispersion_test(ours: float, theirs: float, disp: dict) -> tuple[float, float] | None:
    """Is the gap larger than the two sample means' own noise? Returns (difference, z).

    **This is the check the ratio bands cannot do**, and idaac is the case that shows why. Ours
    reads 1.69x theirs -- a gap no band calls a pass. But ours is a mean of 20 episodes with
    sd 6.49 and theirs a mean of 10 of a stochastic policy, and at those sizes a 3.68 difference
    is z = 1.46: not distinguishable. A one-sample interval on OUR episodes alone would have
    excluded their point estimate ([5.99, 12.06] against 5.35) and read as a real disagreement,
    which is the error this function exists to prevent -- their number has sampling error too, and
    it is the larger of the two because N is smaller.

    When the reference publishes no spread -- the usual case, since these are single logged means
    -- OURS is used as the estimate for theirs. That is an assumption, not a measurement: it says
    the two evaluators see policies of similar variability, which is plausible precisely when the
    instruments agree and least safe when they do not. It makes the test CONSERVATIVE about
    declaring disagreement, so a CONSISTENT verdict here is weaker than it looks and a
    disagreement despite it is correspondingly strong.
    """
    n_o, n_t = disp.get("ours_n"), disp.get("theirs_n")
    sd_o = disp.get("ours_sd")
    if not (n_o and n_t and sd_o):
        return None
    sd_t = disp.get("theirs_sd") or sd_o
    se = ((sd_o ** 2) / n_o + (sd_t ** 2) / n_t) ** 0.5
    if se <= 0:
        return None
    return (ours - theirs, (ours - theirs) / se)


def verdict(ours: float, theirs: float, floored: bool,
            disp: dict | None = None) -> tuple[str, str]:
    """PASS / MARGINAL / WEAK / COLLAPSE / UNDERPOWERED, and why.

    **Graded, because "marginally lower" and "strongly collapsing" are different claims** and an
    earlier version of this function called both SUSPECT at once. A harness reading 8% under its
    reference is doing sampling; one reading 10x under is doing something else. Only the second is
    the [C95](../docs/CONSTRUCTION.md#c95) shape, where a whole methodology read 12-14x low with
    nothing crashing.

    The bands are deliberately coarse and asymmetric-by-interpretation rather than by threshold:
    the same ratio is read more suspiciously downward, because a harness that handicaps a policy and
    a reference that flatters it produce the same number, and only one of those is our bug.

    **No band is a substitute for dispersion.** These are point estimates over ten to twenty
    episodes of policies that are often stochastic; where the records carry per-episode returns, a
    real interval should replace this. Stated here rather than silently approximated.
    """
    if floored:
        return ("UNDERPOWERED",
                f"both numbers are at or near the {RANDOM_FLOOR} floor, so they agree about "
                "nothing: any harness reproduces a policy that does nothing")
    if not theirs:
        return ("UNDERPOWERED", "no reference number")

    # Dispersion outranks the bands where it exists. The bands compare two point estimates and
    # cannot know that a 1.69x gap between a 20-episode mean and a 10-episode one is ordinary
    # sampling; only the spread knows that. Where the records carry it, it decides.
    if disp:
        tested = dispersion_test(ours, theirs, disp)
        if tested:
            difference, z = tested
            if abs(z) < 1.96:
                return ("CONSISTENT",
                        f"ours/theirs = {ours / theirs:.2f}x, but the difference of {difference:+.3f} "
                        f"is z = {z:.2f} against the two means' own sampling error -- not "
                        f"distinguishable at 95%. Above the floor, so this is a real comparison "
                        f"rather than two nulls agreeing. NOTE the reference publishes no spread, "
                        f"so ours stands in for it; that makes this test conservative about "
                        f"declaring disagreement and this verdict correspondingly weaker than PASS")
            return (f"DISTINGUISHABLE",
                    f"ours/theirs = {ours / theirs:.2f}x and the difference of {difference:+.3f} is "
                    f"z = {z:.2f} -- larger than sampling explains. The instruments disagree and "
                    f"the reason has to be found, not banded")
    ratio = ours / theirs
    if 0.9 <= ratio <= 1.15:
        return ("PASS", f"within {abs(1 - ratio) * 100:.0f}%, above the floor")
    if 0.7 <= ratio < 0.9:
        return ("MARGINAL",
                f"ours is {(1 - ratio) * 100:.0f}% lower -- a shortfall, not a collapse, and "
                "inside what ten to twenty episodes of a stochastic policy can produce. Report the "
                "number, carry the caveat, and widen N before drawing on it")
    if 0.4 <= ratio < 0.7:
        return ("WEAK",
                f"ours is {1 / ratio:.1f}x lower. Too large to call sampling and too small to call "
                "a collapse; this is the band where more episodes actually decide it")
    if ratio < 0.4:
        return ("COLLAPSE",
                f"ours is {1 / ratio:.1f}x lower -- the C95 shape. A harness that handicaps the "
                "policy and a reference that flatters it look identical from here, and only one of "
                "those is our defect")
    # [Claude 2026-09-04] This branch used to catch EVERY upward deviation and call all of them
    # MARGINAL -- so a harness reading 10x HIGH would have been reported in the same band as one
    # reading 5% high, and would have counted as a discharged burden. That is the same conflation
    # the downward bands were split to remove, left standing on the other side because "ours is
    # higher" felt benign. It is not: a harness that flatters a policy and a reference that
    # understates it produce the same number, exactly as in the downward case.
    if ratio > 1.5:
        return ("UNEXPLAINED-HIGH",
                f"ours is {ratio:.2f}x higher. Too large to wave through on a point estimate; "
                "either dispersion accounts for it (see the interval line) or something in our "
                "harness is measuring an easier task than theirs")
    return ("MARGINAL", f"ours is {ratio:.2f}x higher; unexplained upward is still unexplained")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 unless every baseline is PASS or MARGINAL")
    a = ap.parse_args(argv)

    print("SHARED-EVALUATOR BURDEN OF PROOF")
    print("  Our harness may report a baseline's number only where it has been shown to")
    print("  measure what that baseline's own evaluator measures. Verdicts are graded by")
    print("  MAGNITUDE -- a marginal shortfall is sampling, a collapse is the C95 shape --")
    print(f"  and a comparison at or below the {RANDOM_FLOOR} floor is UNDERPOWERED, not a pass.")
    print()
    print(f"  {'baseline':10s} {'ours':>9s} {'theirs':>9s}  {'verdict':13s} basis")
    print("  " + "-" * 92)

    passed = []
    for b in BASELINES:
        row = RECONCILIATIONS.get(b)
        if row is None:
            print(f"  {b:10s} {'--':>9s} {'--':>9s}  {'UNRECONCILED':13s} no comparison has been run")
            continue
        ours, theirs = row["ours"], row["theirs"]
        ckpt, evidence = row["checkpoint"], row["evidence"]
        floored = ours <= RANDOM_FLOOR or theirs <= RANDOM_FLOOR
        v, why = verdict(ours, theirs, floored, row.get("dispersion"))
        if v in ("PASS", "MARGINAL", "CONSISTENT"):
            passed.append(b)
        print(f"  {b:10s} {ours:9.3f} {theirs:9.3f}  {v:13s} {ckpt}")
        print(f"  {'':10s} {'':9s} {'':9s}  {'':13s} {why}")
        print(f"  {'':10s} {'':9s} {'':9s}  {'':13s} evidence: {evidence}")

    print()
    print(f"  {len(passed)} of {len(BASELINES)} baselines have a discharged burden: "
          f"{', '.join(passed) if passed else 'none'}")
    print()
    print("  THE BURDEN IS NOT DISCHARGED BY THE HARNESS RUNNING. Six evaluator families exist and")
    print("  all six produce plausible magnitudes; that is a statement about the code, not about")
    print("  the measurement. Until a baseline appears above with a PASS or MARGINAL, a shared number")
    print("  for it is a number from an unvalidated instrument, and `docs/EVAL-PROTOCOL.md` §1's")
    print("  proposal rests for that baseline on construction rather than on evidence.")
    print()
    print("  Discharging one costs a competent checkpoint plus one offline-eval job. The blocker is")
    print("  competence, not compute: at pre-production budgets most baselines sit at the floor,")
    print("  where the comparison cannot say anything.")

    if a.strict and len(passed) != len(BASELINES):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
