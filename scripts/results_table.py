#!/usr/bin/env python3
"""The presentation-ready results table, built only from what the cells actually support.

    python scripts/results_table.py                  # the table
    python scripts/results_table.py --markdown       # same, as markdown for a write-up
    python scripts/results_table.py --strict         # exit 1 if any row would mislead

## What this is, and what decided its shape

The owner, 2026-08-28: *"I don't have a 'final results table' in mind; you can build metrics
however you see … and the final presentation-ready table, or anything, I'll decide when you have
your best results."* So the shape here is a proposal, not an instruction being followed, and every
column below exists because some specific way of being wrong was already paid for in this project.

**Only common-tier quantities share a column.** `TASK.md` R5 records the owner's three-tier model —
*common* (episode return, success rate: all twelve), *family* (`clip_fraction`, contrastive loss:
within a family), *individual* (a method's own auxiliary term). This table carries **common tier
only**. Family-tier diagnostics are real and are deliberately absent: they explain a row, they do
not compare rows ([C28](../docs/CONSTRUCTION.md#c28)).

**Every row carries its floor.** [C17](../docs/CONSTRUCTION.md#c17): a return without the
random-policy floor beside it is unreadable, and Door's shaped reward pays up to 0.5/step for
never opening the door ([C62](../docs/CONSTRUCTION.md#c62)).

**A refusal is printed as a refusal.** The denominator rule
([C47](../docs/CONSTRUCTION.md#c47)/[C55](../docs/CONSTRUCTION.md#c55)) declines to divide by a
denominator that has not been shown to differ from chance, or that solves the task under 25% of the
time. `svea` at 50k has **no** retention number for exactly this reason, and the row says so rather
than leaving a blank a reader would fill in with a guess.

**The cross-method headline never selects scenes by their performance.** The ten-scene protocol is
used when every denominator scene clears the floor/competence gate; otherwise retention is refused.
`usable/10` remains printed as a diagnostic, so a reader can see whether refusal came from one
scene or all ten. This prevents a baseline-specific scene filter from turning a test set into a
different estimand for every row.

**The resolution floor is a column, not a footnote.** Each cell's own seed-only control — the same
scene re-evaluated at a different placement seed — bounds what this design can distinguish from
noise. A gap smaller than it is not a small effect; it is an unresolved one.

## What it deliberately does not do

It does not rank. It does not aggregate across baselines into a single score — RL-ViGen's own
headline aggregate is min–max normalised and is a different quantity from anything here
([PART2-METRIC-INVENTORY.md](../docs/PART2-METRIC-INVENTORY.md) §6.1). And it does not fill an
absent row: `curl`, `ctrl`, `ppg` and the rest are **absent rather than poor**, which is a
different claim and is printed as one.
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import re
import statistics as st
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.metrics import wilson_interval  # noqa: E402  -- the project's own, not re-derived
# [Claude 2026-09-06] MIN_DENOM_SUCCESS was a second `= 0.25` literal beside
# regime_retention_report.py's own -- the exact "two homes for one number" pattern Q12 and the
# g1.1 admission-tier bug already caught elsewhere in this project. That file's comment carries the
# adversarial-re-check story behind the value (an 0.947 retention read as robustness that was
# actually a 1/20-every-scene shaped-reward plateau), so it is the one authoritative home; DOOR
# 0.25's still-open status (DECISION-SHEET.md A23) makes silent divergence a live risk, not a
# hypothetical one.
from scripts.regime_retention_report import MIN_DENOM_SUCCESS  # noqa: E402


def _time_limit_handling() -> dict:
    """Per-baseline truncation-vs-termination, read the same way `audit_comparability_seam.py`'s
    own `truncation()` does -- from `rlgen/protocol.py`'s source text, not by importing the module.

    [Claude 2026-09-06] C1: nine baselines zero the value bootstrap at Door's time limit, three
    (`rad`/`soda`/`alda`) bootstrap through it -- CONSTRUCTION.md#c1 rates this the largest
    comparability defect found, and its own DEFAULT says the split "must be stated wherever these
    numbers appear" and "must never be averaged across." This table's rows never mixed the two
    groups so far (every CELLS entry today is `drqv2`/`svea`/`drq`, all "terminal") -- but `rad`,
    `soda` and `alda` are explicitly ABSENT-with-reason above as "not yet run", so a future cell
    from any of the three would silently mix groups in the same `regime`/`scene ret` columns with
    no warning, which is exactly the failure C1's DEFAULT exists to prevent. Checked here rather
    than left to a reader.
    """
    src = (ROOT / "rlgen" / "protocol.py").read_text(encoding="utf-8")
    m = re.search(r"TIME_LIMIT_HANDLING\s*=\s*\{(.*?)\n\}", src, re.S)
    if not m:
        return {}
    return dict(re.findall(r'"(\w+)":\s*"(\w+)"', m.group(1)))


TIME_LIMIT_HANDLING = _time_limit_handling()
GRIDS = ROOT / "results" / "regime-retention-c69"

CEILING = 250.0        # C62: max return with the door never opening, over horizon 500
FLOOR = "random-floor"

#: Cells produced by the 105k protocol (C77) with verified provenance. Older tags in the same
#: directory are earlier or contaminated runs and are deliberately not tabulated; they remain on
#: disk as evidence. Listed rather than globbed so that adding a row is a deliberate act.
CELLS = [
    ("drqv2", 7, "50k",  "drqv2-s7-105k-at50k"),
    ("drqv2", 7, "100k", "drqv2-s7-105k-at100k"),
    ("svea",  1, "50k",  "svea-s1-105k-at50k"),
    ("svea",  1, "100k", "svea-s1-105k-at100k"),
    ("drq",   1, "100k", "drq-s1-105k-at100k"),
]

#: RL-ViGen's own published Door Easy figures -- mean episode return over ten scenes, 5 seeds,
#: from `RL-ViGen-upstream/results/evaluation_score.xlsx` (read by `scripts/rlvigen_reference.py`,
#: C31). Included because ours is now the SAME CONSTRUCTION for the first time: C45/C47 established
#: that every earlier comparison put our scene-0 figure against their ten-scene mean, and
#: `eval_across_scenes.py` now sweeps ten scenes. See C87 for what the comparison does and does not
#: license -- in particular it is NOT C48's reproduction, because it runs OUR evaluator.
PUBLISHED_DOOR_EASY = {"drqv2": 3.6, "drq": 14.0, "svea": 268.8,
                       "curl": 6.6, "sgqn": 391.4}

#: Baselines with no row, and why. "Absent" and "poor" are different claims and must not be
#: printed the same way -- FAITHFULNESS.md section 5 item 10 makes this point for ctrl and ppg.
ABSENT = {
    "curl": "cannot run under the MPS shim (scatter: index -1); needs CUDA",
    "sgqn": "~11h per cell locally; not yet run at the 105k protocol",
    "rad": "no cell run at the 105k protocol yet",
    "soda": "no cell run at the 105k protocol yet",
    "alda": "no cell run at the 105k protocol yet",
    "idaac": "no cell run at the 105k protocol yet",
    "ppg": "no cell run at the 105k protocol yet",
    "ctrl": "no cell run at the 105k protocol yet",
    "ibac_sni": "no cell run at the 105k protocol yet",
}


def load(tag: str, mode: str):
    f = GRIDS / f"{tag}__{mode}.json"
    return json.loads(f.read_text()) if f.exists() else None


def scene_means(d) -> dict[int, float]:
    return {int(k): st.mean(v["returns"]) for k, v in d["scenes"].items()}


def successes(d) -> dict[int, int]:
    return {int(k): v.get("n_success", 0) for k, v in d["scenes"].items()}


def boot_ci(num: list[float], den: list[float], n: int = 2000, seed: int = 0):
    """Percentile bootstrap on the ratio of pooled means. Returns (lo, hi) or None."""
    import random
    if not num or not den or st.mean(den) <= 0:
        return None
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        a = st.mean([num[rng.randrange(len(num))] for _ in num])
        b = st.mean([den[rng.randrange(len(den))] for _ in den])
        if b > 0:
            out.append(a / b)
    if not out:
        return None
    out.sort()
    return out[int(0.025 * len(out))], out[int(0.975 * len(out))]


def boot_scene_ret(d, n: int = 4000, seed: int = 0):
    """CI on (mean of held-out scenes) / (scene 0), by resampling EPISODES within each scene.

    It bounds **within-run sampling noise only**. Between-seed variance is not in it and is
    unmeasured everywhere in this project -- one seed per cell. Two intervals failing to overlap
    here means the episode sample distinguishes them; it does not mean a second seed would land
    inside either.
    """
    import random
    rng = random.Random(seed)
    sc = {int(k): v["returns"] for k, v in d["scenes"].items()}
    out = []
    for _ in range(n):
        m = {k: st.mean([r[rng.randrange(len(r))] for _ in r]) for k, r in sc.items()}
        if m[0] > 0:
            out.append(st.mean([m[k] for k in m if k != 0]) / m[0])
    if not out:
        return None
    out.sort()
    return out[int(0.025 * len(out))], out[int(0.975 * len(out))]


def row(name: str, seed: int, budget: str, tag: str, floor_mean: float):
    tr, ev = load(tag, "train"), load(tag, "eval-easy")
    if tr is None or ev is None:
        return None
    mtr, mev = scene_means(tr), scene_means(ev)
    str_, sev = successes(tr), successes(ev)
    eps = tr["episodes"]

    ctrl = st.mean(tr["control"]["returns"])
    res_floor = abs(ctrl - mtr[0]) / mtr[0] if mtr[0] else float("nan")

    held = [mtr[k] for k in sorted(mtr) if k != 0]
    scene_ret = st.mean(held) / mtr[0] if mtr[0] else float("nan")
    # [Claude 2026-09-06] A18 (DECISION-SHEET.md), adopted but never emitted anywhere until now --
    # EVAL-PROTOCOL.md:23 lists "retention AND floor-adjusted retention" as both reported, per
    # regime AND scene; this project had the first half of each pair and never wrote the second.
    # Floor-adjusted = (num - floor) / (den - floor): invariant to the shared additive offset a
    # ratio of raw returns is not, since Door's reward is shaped with a non-zero floor (C17/C18).
    # Refused (None), not a number, when the floor-adjusted denominator would not be positive --
    # printing a ratio over a non-positive denominator would look like a number and isn't one.
    scene_ret_floor_adj = ((st.mean(held) - floor_mean) / (mtr[0] - floor_mean)
                           if mtr[0] > floor_mean else None)

    # Usable scenes: denominator above the floor AND solving at least MIN_DENOM_SUCCESS. Keep this
    # count as a diagnostic, but do not select on it: selecting different scenes per baseline is
    # post-selection bias and defeats the common ten-scene headline.
    usable = [k for k in sorted(mtr)
              if mtr[k] > floor_mean and (str_.get(k, 0) / eps) >= MIN_DENOM_SUCCESS]
    common = sorted(mtr) if len(usable) == len(mtr) else []
    if common:
        num = [x for k in common for x in ev["scenes"][str(k)]["returns"]]
        den = [x for k in common for x in tr["scenes"][str(k)]["returns"]]
        regime = st.mean(num) / st.mean(den)
        ci = boot_ci(num, den)
        # `usable` already requires every pooled scene's TRAIN mean to clear floor_mean, so the
        # pooled `den` mean clears it too (a weighted average of means each above a bound is above
        # that bound) -- this is regime's counterpart to scene_ret_floor_adj's own explicit guard.
        regime_floor_adj = ((st.mean(num) - floor_mean) / (st.mean(den) - floor_mean)
                            if st.mean(den) > floor_mean else None)
    else:
        regime, ci, regime_floor_adj = None, None, None

    tot_tr = sum(str_.values()); tot_ev = sum(sev.values())
    n_ep = eps * len(mtr)
    return dict(name=name, seed=seed, budget=budget, scene0=mtr[0], held=st.mean(held),
                scene_ret=scene_ret, scene_ret_floor_adj=scene_ret_floor_adj, scene_ci=boot_scene_ret(tr),
                regime=regime, regime_floor_adj=regime_floor_adj, ci=ci, usable=len(usable), n_scenes=len(mtr),
                sr_tr=tot_tr / n_ep, sr_ev=tot_ev / n_ep,
                sr_tr_ci=wilson_interval(tot_tr, n_ep), sr_ev_ci=wilson_interval(tot_ev, n_ep),
                n_ep=n_ep, n_tr=tot_tr, n_ev=tot_ev, res_floor=res_floor,
                md5=tr.get("snapshot_md5", "?")[:8], eps=eps,
                over_ceiling=sum(1 for k in mtr for x in tr["scenes"][str(k)]["returns"] if x > CEILING),
                tl=TIME_LIMIT_HANDLING.get(name, "?"))


CELLS_BY_NAME = [(n, t) for n, _, b, t in CELLS if b == "100k"]


def main(argv: list[str] | None = None) -> int:
    # argv is an explicit parameter so a test can call main([]) -- otherwise argparse reads
    # pytest's own command line and exits 2 before the table is ever built.
    ap = argparse.ArgumentParser()
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--legacy-exploratory", action="store_true",
                    help="acknowledge that this one-seed, episode-bootstrap table is diagnostic "
                         "only and cannot be a production headline")
    a = ap.parse_args(argv)

    if not a.legacy_exploratory:
        print("REFUSING TO RENDER THE LEGACY RESULTS TABLE WITHOUT --legacy-exploratory.")
        print("Its interval resamples episodes from one trained policy; the production outer unit "
              "is the training seed. Use the production reporting path for headline numbers.")
        return 2

    fl = load(FLOOR, "train")
    if fl is None:
        print("NO RANDOM-POLICY FLOOR MEASURED. Every return below would be unreadable and every")
        print("retention would divide by a denominator not shown to differ from chance. Refusing.")
        return 1
    floor_mean = st.mean([x for s in fl["scenes"].values() for x in s["returns"]])
    floor_succ = sum(s.get("n_success", 0) for s in fl["scenes"].values())

    rows = [r for c in CELLS if (r := row(*c, floor_mean))]

    print("LEGACY EXPLORATORY RETENTION ON ROBOSUITE DOOR — not a production headline\n")
    print(f"  Random-policy floor (train regime): mean {floor_mean:.2f}, "
          f"successes {floor_succ}/200. Every return reads against this.")
    print(f"  Shaping ceiling {CEILING:.0f}: a return above it proves the door opened (C62).")
    print(f"  Denominator rule: a scene counts only if it clears the floor AND succeeds "
          f"in >= {MIN_DENOM_SUCCESS:.0%} of episodes (C47/C55).\n")

    hdr = (f"  {'baseline':<8} {'seed':>4} {'budget':>7} {'scene0':>8} {'held-out':>9} "
           f"{'scene ret':>10} {'regime ret':>12} {'95% CI':>16} {'n':>5} {'SR tr>ev':>12} "
           f"{'res floor':>10}")
    print(hdr); print("  " + "-" * (len(hdr) - 2))
    for r in rows:
        reg = f"{r['regime']:.3f}" if r["regime"] is not None else "REFUSED"
        ci = f"[{r['ci'][0]:.3f}, {r['ci'][1]:.3f}]" if r["ci"] else "--"
        print(f"  {r['name']:<8} {r['seed']:>4} {r['budget']:>7} {r['scene0']:>8.2f} "
              f"{r['held']:>9.2f} {r['scene_ret']:>9.1%} {reg:>12} {ci:>16} "
              f"{str(r['usable'])+'/'+str(r['n_scenes']):>5} "
              f"{r['sr_tr']:>5.1%}>{r['sr_ev']:<5.1%} {r['res_floor']:>9.1%}")

    print("\n  INTERVALS. Scene retention by bootstrap over episodes; success rate by Wilson.")
    print(f"  {'cell':<14} {'scene ret':>9} {'95% CI':>16}   {'SR train':>20} {'SR eval-easy':>20}")
    for r in rows:
        sc = f"[{r['scene_ci'][0]:.3f}, {r['scene_ci'][1]:.3f}]" if r["scene_ci"] else "--"
        print(f"  {r['name']+'@'+r['budget']:<14} {r['scene_ret']:>8.1%} {sc:>16}   "
              f"{r['n_tr']:>3}/{r['n_ep']} [{r['sr_tr_ci'][0]:.3f},{r['sr_tr_ci'][1]:.3f}]  "
              f"{r['n_ev']:>3}/{r['n_ep']} [{r['sr_ev_ci'][0]:.3f},{r['sr_ev_ci'][1]:.3f}]")
    print("  These bound WITHIN-RUN sampling noise only. Between-seed variance is unmeasured --")
    print("  one seed per cell — so two non-overlapping intervals mean the episode sample")
    print("  separates them, NOT that a second seed would land inside either. `wilson_interval`")
    print("  is used for the success rate because it is a proportion; `iqm` is deliberately not")
    print("  used anywhere (see scripts/metrics.py: its home is aggregation across runs).")

    print("\n  FLOOR-ADJUSTED RETENTION (A18, DECISION-SHEET.md) -- adopted, never emitted until now.")
    print("  Plain retention divides two raw returns; Door's reward is shaped with a non-zero")
    print("  floor, so that ratio is not invariant to the shared offset (C17/C18). Floor-adjusted")
    print(f"  subtracts the measured random-policy floor ({floor_mean:.3f}) from both terms first:")
    print("  (num - floor) / (den - floor). REFUSED where the floor-adjusted denominator would")
    print("  not be positive -- printing a ratio over a non-positive denominator would look like a")
    print("  number and would not be one. This does not replace plain retention above; both are")
    print("  reported, per EVAL-PROTOCOL.md's own metrics-reported row.")
    print(f"  {'cell':<14} {'scene ret*':>11} {'regime ret*':>12}")
    for r in rows:
        sc = f"{r['scene_ret_floor_adj']:.3f}" if r["scene_ret_floor_adj"] is not None else "REFUSED"
        rg = f"{r['regime_floor_adj']:.3f}" if r["regime_floor_adj"] is not None else "REFUSED"
        print(f"  {r['name']+'@'+r['budget']:<14} {sc:>11} {rg:>12}")
    print("  * floor-adjusted, per above. Not directly comparable to the un-starred columns.")

    print("\n  COLUMNS, and why each is here rather than in a footnote:")
    print("    scene0     mean return on the TRAINED scene, train regime.")
    print("    held-out   mean over scenes 1-9, train regime. Its ratio to scene0 is scene ret.")
    print("    regime ret pooled eval-easy / train over ALL ten scenes, only when every denominator")
    print("               scene clears the rule. REFUSED means at least one scene did not: an")
    print("               absence of retention, not a small one; no baseline-specific scene filter")
    print("               is allowed to define the headline.")
    print("    n          usable / total scenes, diagnostic only. Read it before regime ret.")
    print("    SR tr>ev   success rate, train -> eval-easy. Reported beside return, never averaged")
    print("               with it: same name, same lineage, no evidence they are one quantity.")
    print("    res floor  this cell's own seed-only control — the same scene at a different")
    print("               placement seed. A gap SMALLER than this is unresolved, not small.")

    print("\n  AGAINST RL-ViGen'S PUBLISHED Door Easy — the same construction (10-scene mean),")
    print("  which C45/C47 showed was never true of earlier comparisons. Theirs: 5 seeds at their")
    print("  own budget; ours: 1 seed at 100k. NOT a reproduction — this runs OUR evaluator, and")
    print("  C48's test is running THEIRS on a policy, which remains undone.")
    print(f"    {'method':<8} {'ours (10-scene eval-easy)':>26} {'published':>10} {'ratio':>8} "
          f"{'ours/floor':>11} {'theirs/floor':>13}")
    seen_pub = []
    for r in rows:
        if r["budget"] != "100k" or r["name"] not in PUBLISHED_DOOR_EASY or r["name"] in seen_pub:
            continue
        seen_pub.append(r["name"])
        ev = load(dict(CELLS_BY_NAME)[r["name"]], "eval-easy")
        if ev is None:
            continue
        mine = st.mean([st.mean(v["returns"]) for v in ev["scenes"].values()])
        pub = PUBLISHED_DOOR_EASY[r["name"]]
        print(f"    {r['name']:<8} {mine:>26.2f} {pub:>10.1f} {mine/pub:>7.2f}x "
              f"{mine/floor_mean:>10.1f}x {pub/floor_mean:>12.1f}x")
    if seen_pub:
        print("    Their `drqv2` at 3.6 is TWICE the measured floor and their `drq` at 14.0 is")
        print("    7.7x it, against a shaping ceiling of 250 — so two of RL-ViGen's own natives")
        print("    barely solve Door Easy in their hands either. Ours exceeding them is not")
        print("    evidence of a better implementation; it is a low bar. `svea` is the cell with")
        print("    real headroom, and there we sit at a quarter of theirs on a sixth of the budget.")
        print("    The ORDERING reproduces — but with three methods that happens 1 in 6 times by")
        print("    chance, so it is suggestive alone and leans on `drq` landing within 16%.")

    print("\n  ABSENT ROWS — absent is not poor, and the two must not print alike:")
    for b, why in ABSENT.items():
        print(f"    {b:<9} {why}")

    print("\n  WHAT THIS TABLE IS NOT. It does not rank and does not aggregate into one score:")
    print("  RL-ViGen's own headline aggregate is min-max normalised and is a different quantity")
    print("  from anything here. Every row is one seed; between-seed variance is unmeasured, and")
    print("  the seed-only control bounds placement noise WITHIN a checkpoint, not the spread")
    print("  ACROSS checkpoints. The cross-baseline comparison is licensed only inside the five")
    print("  RL-ViGen natives, where the seam audit splits on 0 of 12 axes (RESEARCH-FRAME.md).")

    if a.markdown:
        print("\n\n---\n\n| baseline | seed | budget | scene 0 | held-out | scene ret. | "
              "regime ret. | 95% CI | usable | SR train→eval | res. floor | scene ret.* | "
              "regime ret.* |")
        print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for r in rows:
            reg = f"**{r['regime']:.3f}**" if r["regime"] is not None else "**REFUSED**"
            ci = f"[{r['ci'][0]:.3f}, {r['ci'][1]:.3f}]" if r["ci"] else "—"
            sc_fa = f"{r['scene_ret_floor_adj']:.3f}" if r["scene_ret_floor_adj"] is not None else "REFUSED"
            rg_fa = f"{r['regime_floor_adj']:.3f}" if r["regime_floor_adj"] is not None else "REFUSED"
            print(f"| `{r['name']}` | {r['seed']} | {r['budget']} | {r['scene0']:.2f} | "
                  f"{r['held']:.2f} | {r['scene_ret']:.1%} | {reg} | {ci} | "
                  f"{r['usable']}/{r['n_scenes']} | {r['sr_tr']:.1%} → {r['sr_ev']:.1%} | "
                  f"{r['res_floor']:.1%} | {sc_fa} | {rg_fa} |")
        print("\n\n\* floor-adjusted (A18): (num - floor) / (den - floor). Not directly "
              "comparable to the un-starred columns.")

    bad = [r for r in rows if r["regime"] is not None and r["usable"] < 2]
    if bad:
        print(f"\n  WARNING: {len(bad)} row(s) pool over fewer than 2 scenes.")

    # [Claude 2026-09-06] C1: never let a single table pool rows across the time-limit-handling
    # split without saying so loudly. See _time_limit_handling()'s docstring above -- today's
    # CELLS never triggers this (drqv2/svea/drq all share "terminal"), so this has not yet fired,
    # but rad/soda/alda are explicitly "not yet run" in ABSENT above and WOULD trigger it silently
    # otherwise the moment a cell for any of them is added.
    tl_groups = sorted({r["tl"] for r in rows})
    mixed_tl = len(tl_groups) > 1
    if mixed_tl:
        by_group = {g: sorted({r["name"] for r in rows if r["tl"] == g}) for g in tl_groups}
        print(f"\n  WARNING (C1): this table pools {tl_groups} time-limit conventions in one "
              "comparison:")
        for g, names in by_group.items():
            print(f"    {g:<10} {', '.join(names)}")
        print("    CONSTRUCTION.md#c1's DEFAULT is declare-and-never-rank-across. `scene ret` / "
              "`regime ret` / `SR tr>ev` above are NOT safe to compare between these groups.")

    return 1 if (a.strict and (bad or mixed_tl)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
