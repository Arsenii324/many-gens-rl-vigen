"""Assemble the twelve-baseline pre-production table from returned job archives.

    python scripts/preprod_table.py /path/to/probe-results/bt1... [more dirs...]

**What this is for.** R7 asks that the clone-to-curve path work; R4 asks for equal training length
or a stated reason; R3 asks that the metrics be on the same axes. Twelve rows assembled by hand
across seven families is exactly the boilerplate that goes stale, so it is generated.

**The axes are printed WITH the numbers, not in a separate document, because the whole finding of
docs/COMPARABILITY_CONTRACT.md is that a bare column invites a comparison the data does not
support.** Three of the twelve report a SAMPLED return where nine report a mode return (§5c); four
receive a single frame where eight receive three, which makes them a different POMDP on a
manipulation task (C2); and every number is only comparable with numbers from the same platform
(C95). A row therefore carries its estimator and its stack, and the footer refuses to rank.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tarfile
from pathlib import Path

# The two axes that decide whether two rows may be compared at all. Sources: audit_eval_state.py
# for the estimator, CONSTRUCTION.md C2 for the stack.
# [Claude 2026-09-04] `ctrl` moved mode -> SAMPLE, found while establishing its evaluator family.
# `algo.select_action` CAN take the mode (`pi.mode()` when sample=False), and that is what
# audit_eval_state recorded. But the calls that produce the numbers a ctrl cell actually reports --
# `train_ppo.py:244` and `:253`, the ID and OOD test-env steps behind Eprew200/Eprew0 -- both pass
# `sample=True`. The capability is not the usage, and the column has to say what was used.
ESTIMATOR = {
    "drqv2": "mode", "svea": "mode", "drq": "mode", "sgqn": "mode", "curl": "mode",
    "rad": "mode", "soda": "mode", "alda": "mode",
    "idaac": "SAMPLE", "ibac_sni": "SAMPLE", "ppg": "SAMPLE", "ctrl": "SAMPLE",
}
STACK = {b: 3 for b in ("drqv2", "svea", "drq", "sgqn", "curl", "rad", "soda", "alda")}
STACK.update({b: 1 for b in ("ppg", "idaac", "ibac_sni", "ctrl")})

# The uniform-random-policy floor on Door, measured over 400 episodes with zero successes
# (C55). A return at or below this is indistinguishable from acting randomly, and no ratio
# may be built on it -- C18/RIGOR.md: retention over a near-floor denominator is not a small
# number, it is an undefined one that looks like a number.
RANDOM_FLOOR = 1.82

FRAME_RE = re.compile(r"NATIVE_FINAL_EVALUATION_COMPLETED frame=(\d+)")


def _ibac_eval_line():
    """The one regex, borrowed from the normalizer so the two cannot drift apart."""
    try:
        import importlib.util
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location(
            "normalize_curves", root / "datasphere" / "native" / "normalize_curves.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("normalize_curves", module)
        spec.loader.exec_module(module)
        return getattr(module, "IBAC_EVAL_LINE", None)
    except Exception:
        return None


def cells_of(job: Path, target_regime: str = "eval-easy") -> list[dict]:
    ex = job / "ex"
    archive = job / "result.tgz"
    if not ex.is_dir() and archive.exists():
        ex.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive) as handle:
            handle.extractall(ex)
    if not ex.is_dir():
        return []

    records = []
    record_file = next(iter(ex.rglob("records.jsonl")), None)
    if record_file:
        for line in record_file.read_text(errors="replace").splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    rows = []
    for log in sorted(ex.rglob("training.log")):
        regime_substituted = False
        cell = log.parent.name
        baseline = cell.rsplit("-s", 1)[0]
        text = log.read_text(errors="replace")
        frame = FRAME_RE.search(text)
        evals = [r for r in records
                 if r.get("phase") == "eval" and r.get("baseline") == baseline
                 and r.get("episode_return_mean") is not None]
        # Pick the record for the TARGET REGIME, not simply the last one.
        #
        # [Claude 2026-09-03] This read `evals[-1]`, and for the RL-ViGen family that is the
        # *train-regime* row: patch P14 emits `episode_reward` (the eval regime) and
        # `train_regime_reward` (the denominator) as two records, and the denominator is written
        # second. The table therefore showed `drqv2` at 21.06 and `svea` at 28.67 under a column
        # of seven eval-easy numbers -- four train-regime values pooled with seven held-out ones,
        # which is the exact error the table was built to prevent, committed by the table.
        #
        # Caught only because the regime is a printed column. A generator that had shown the
        # number without its regime would have produced a clean-looking and wrong table.
        want = [r for r in evals if r.get("regime") == target_regime]
        final = want[-1] if want else None
        if final is None and evals:
            # No record for the target regime: report the last one and mark the row, rather than
            # silently substituting a different measurement.
            final = evals[-1]
            regime_substituted = True
        source = "record"
        if final is None:
            # The record set can be missing an eval row while the cell DID evaluate -- `ibac_sni`
            # printed `SR 0.0000` and normalize_curves had no parser for it until 2026-09-03. Fall
            # back to the container's own log rather than re-normalising locally, because
            # re-normalising here would stamp THIS laptop into `recorded_on` for a number the
            # container measured (see normalize_curves._recorded_on). One regex, imported, not
            # duplicated.
            match = _ibac_eval_line() and _ibac_eval_line().search(text)
            if match:
                total, mean, sd, low, high, ep_len, sr = (float(g) for g in match.groups())
                final = {"regime": "eval-easy",
                         "episodes": int(round(total / ep_len)) if ep_len else None,
                         "episode_return_mean": mean, "success_rate": sr}
                source = "log"
        platform = (final or {}).get("native", {}).get("recorded_on", {}) if final else {}
        if source == "log":
            # every returned archive was produced by run_probe.sh, which exports MUJOCO_GL=egl
            platform = {"mujoco_gl": "egl"}
        rows.append({
            "baseline": baseline,
            "cell": cell,
            "frames": int(frame.group(1)) if frame else None,
            "regime": (final or {}).get("regime"),
            "episodes": (final or {}).get("episodes"),
            "mean": (final or {}).get("episode_return_mean"),
            "success": (final or {}).get("success_rate"),
            "mujoco_gl": platform.get("mujoco_gl"),
            "job": job.name,
            "source": source,
            "regime_substituted": regime_substituted,
        })
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("jobs", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--regime", default="eval-easy",
                    help="the regime every row must report; a row that has no record for it "
                         "is marked rather than silently substituted")
    a = ap.parse_args(argv)

    rows = []
    for job in a.jobs:
        rows.extend(cells_of(job, a.regime))
    rows.sort(key=lambda r: (STACK.get(r["baseline"], 9), r["baseline"]))

    import datetime
    lines = []
    # docs/dated/ snapshots must declare when they were written -- tests/test_docs_integrity.py
    # ::test_dated_snapshots_declare_their_write_time. Emitted by the generator so a regenerated
    # table cannot lose it, which is what happened the first time this wrote into docs/dated/.
    lines.append(f"Written {datetime.date.today().isoformat()} by `scripts/preprod_table.py`.")
    lines.append("")
    lines.append("# Pre-production validation table")
    lines.append("")
    lines.append("| baseline | frames | regime | eps | return | success | estimator | stack | render |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        at_floor = isinstance(r["mean"], (int, float)) and r["mean"] <= RANDOM_FLOOR
        mean = (f"{r['mean']:.3f}{' ⌊' if at_floor else ''}"
                if isinstance(r["mean"], (int, float)) else "—")
        succ = f"{r['success']:.2f}" if isinstance(r["success"], (int, float)) else "—"
        lines.append(
            f"| `{r['baseline']}`{' ⚠' if r['baseline'] == 'ctrl' else ''} | {r['frames'] or '—'} | "
            f"{(str(r['regime']) + ('!' if r.get('regime_substituted') else '') + ('*' if r['baseline'] == 'alda' else '')) if r['regime'] else '—'} | "
            f"{r['episodes'] or '—'} | {mean} | {succ} | "
            f"{ESTIMATOR.get(r['baseline'], '?')} | {STACK.get(r['baseline'], '?')} | "
            f"{r['mujoco_gl'] or '—'} |")

    missing = [r["baseline"] for r in rows if r["mean"] is None]
    have = {r["baseline"] for r in rows}
    absent = sorted(set(ESTIMATOR) - have)

    lines.append("")
    lines.append(f"**{len(have)} of 12 baselines present**"
                 + (f"; absent: {', '.join(absent)}" if absent else "; all twelve present"))
    if missing:
        lines.append(f"**No eval number for**: {', '.join(missing)} — the cell ran but its "
                     "evaluation did not land, which is an R7 break, not a low score.")
    lines.append("")
    lines.append("**This table may not be sorted by return.** Three baselines report a SAMPLED "
                 "return (`idaac`, `ibac_sni`, `ppg`) and nine report a mode return; the two are "
                 "different quantities. Four receive a single frame and eight receive three, which "
                 "on a manipulation task makes them velocity-blind — a different POMDP, not a "
                 "weaker algorithm (C2). Rows are grouped by stack for that reason.")
    lines.append("")
    lines.append("**Budgets are equal by intent, not exactly** (R4): `ppg` floors to a 2048 "
                 "quantum and `ctrl` to a multiple of `num_envs`, so their frame counts differ "
                 "from the requested budget by construction. The `frames` column is what actually "
                 "executed.")
    lines.append("")
    floored = [r["baseline"] for r in rows
               if isinstance(r["mean"], (int, float)) and r["mean"] <= RANDOM_FLOOR]
    lines.append(f"**⌊ marks a return at or below the random-policy floor of {RANDOM_FLOOR}** "
                 "(C55: uniform random, 400 episodes, zero successes on Door). "
                 + (f"At this budget that is {len(floored)} of {len(rows)}: "
                    f"{', '.join('`'+b+'`' for b in floored)}. " if floored else "")
                 + "**No retention ratio may be computed from a floored row.** A ratio over a "
                 "near-floor denominator is not a small number, it is an undefined one that looks "
                 "like a number (C18, RIGOR.md). This is the expected result of a 10k budget and "
                 "is why the pass validates the pipeline rather than measuring generalisation.")
    lines.append("")
    lines.append("**`alda`'s regime is a MAPPING, marked `*`.** It reports "
                 "dmcontrol-generalization-benchmark's own names — `color` and `distracting` — "
                 "which `normalize_curves.read_alda` maps to the nearest RL-ViGen regime and "
                 "explicitly labels *a mapping rather than an identity*; the original key survives "
                 "in the record's `native` block. The mapping is reasonable (colour randomisation "
                 "≈ eval-easy, distracting background ≈ eval-hard) and it is still not the same "
                 "generator, so an alda row and a native row under one regime label are close "
                 "neighbours, not the same condition.")
    lines.append("")
    lines.append("**`ctrl`'s row is NOT comparable with the others and is marked accordingly.** "
                 "`audit_comparability_seam.py::reported_estimator` states that the estimator axis "
                 "is uniform *conditional on only ever reading the evaluation number*, and warns "
                 "that training-curve numbers are a different estimand which pooling would "
                 "corrupt. `ctrl`'s cell reports `Eprew200`/`Eprew0` — training-curve numbers — "
                 "because its fixed-policy evaluator is unbuilt: `evaluate_ppo.py` calls a "
                 "discrete-only helper while `algo.select_action` already handles both action "
                 "spaces. So this pass violates that condition for exactly one baseline. Until "
                 "the evaluator is adapted, `ctrl` is a pipeline check only.")
    lines.append("")
    lines.append("**A blank `eps` is the symptom of that, not a formatting gap.** "
                 "`ctrl` never performs a terminal evaluation: `train_ppo.py` steps an ID and an "
                 "OOD test env *inside* the training loop and reports `Eprew200`/`Eprew0`, a "
                 "running mean over a trailing window. Every other baseline here reports a "
                 "fixed-N evaluation of the final policy. A windowed running mean and a terminal "
                 "N-episode mean are different estimators of different quantities: the first is "
                 "smeared over the policies of the last N episodes, the second measures only the "
                 "policy that was saved. Comparing them as if they were the same column overstates "
                 "`ctrl` when it is improving and understates it when it has just diverged.")
    lines.append("")
    lines.append("**`render` must be identical across rows to compare them at all** (C95): a "
                 "container-trained policy evaluated under a different rasteriser reads 12–14x "
                 "low. Any row showing `glfw` beside rows showing `egl` is not comparable.")

    text = "\n".join(lines)
    if a.out:
        a.out.write_text(text + "\n")
        print(f"wrote {a.out}")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
