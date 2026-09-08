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

# [Claude 2026-09-08] `datasphere` is a plain directory with no `__init__.py`, so this import only
# resolves when the repo root is on sys.path. Every other script that imports it inserts the root
# first (`collect_metrics.py:50`, `eval_grid.py`, `eval_provenance.py`); this one did not, so the
# file has been unrunnable -- `ModuleNotFoundError: No module named 'datasphere'` on import, before
# argparse, so even `--help` failed. Found by running it rather than reading it.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datasphere.native.family import provenance_for  # noqa: E402

# The two axes that decide whether two rows may be compared at all. Sources: audit_eval_state.py
# for the estimator, CONSTRUCTION.md C2 for the stack.
# [Claude 2026-09-04] `ctrl` moved mode -> SAMPLE, found while establishing its evaluator family.
# `algo.select_action` CAN take the mode (`pi.mode()` when sample=False), and that is what
# audit_eval_state recorded. But the calls that produce the numbers a ctrl cell actually reports --
# `train_ppo.py:244` and `:253`, the ID and OOD test-env steps behind Eprew200/Eprew0 -- both pass
# `sample=True`. The capability is not the usage, and the column has to say what was used.
# [Claude 2026-09-07] DERIVED, not typed. This dict was the last hand-written literal in this
# file, sitting directly above the comment explaining why STACK and TIME_LIMIT stopped being
# literals -- "a hand-typed per-baseline literal drifts silently from its source, which is exactly
# how C1's false-certification half happened". The authoritative source is
# evaluator_identity.FAMILY_EVAL_POLICY_MODE, which is what eval_grid.py actually acts on, so a
# change there now propagates here instead of leaving the table describing a run it did not
# produce. Verified equal to the previous literal at the time of this change.
def _estimator_by_baseline() -> dict:
    import importlib.util

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "_evaluator_identity_for_table", root / "datasphere" / "native" / "evaluator_identity.py")
    identity = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(identity)
    out = {}
    for family, baselines in identity.FAMILY_ALLOWED_BASELINES.items():
        mode = identity.FAMILY_EVAL_POLICY_MODE[family]
        for baseline in baselines:
            out[baseline] = "mode" if mode == "mode" else "SAMPLE"
    return out


ESTIMATOR = _estimator_by_baseline()
# [Claude 2026-09-06] Read from rlgen/protocol.py's OBSERVATION_GEOMETRY (render size, frame
# stack) rather than hand-duplicated, the same fix TIME_LIMIT below already needed: a
# hand-typed per-baseline literal drifts silently from its source, which is exactly how C1's
# false-certification half happened in the first place. Verified equal to the previous literal
# at the time of this change; a future OBSERVATION_GEOMETRY edit now propagates instead of drifting.
def _stack_by_baseline() -> dict:
    src = (Path(__file__).resolve().parents[1] / "rlgen" / "protocol.py").read_text(encoding="utf-8")
    m = re.search(r"OBSERVATION_GEOMETRY\s*=\s*\{(.*?)\n\}", src, re.S)
    if not m:
        return {}
    return {b: int(stack) for b, stack in
            re.findall(r'"(\w+)":\s*\(\s*\d+,\s*(\d+)\s*\)', m.group(1))}


STACK = _stack_by_baseline()

# [Claude 2026-09-06] C1, rated the largest comparability defect found (CONSTRUCTION.md#c1): on
# Door every episode ends by time limit, and nine of twelve zero the value bootstrap there (biasing
# every critic target downward, every episode, throughout training) while three (`rad`/`soda`/
# `alda`) bootstrap through it correctly. This table already declares STACK and ESTIMATOR beside
# every row for exactly this reason -- "a bare column invites a comparison the data does not
# support" (this file's own docstring) -- but had no column or footer note for C1 at all, despite
# it outranking both in the project's own severity rating. Read the same way
# `audit_comparability_seam.py::truncation()` and `results_table.py` do: from `rlgen/protocol.py`'s
# own source text, not by importing the module.
def _time_limit_handling() -> dict:
    src = (Path(__file__).resolve().parents[1] / "rlgen" / "protocol.py").read_text(encoding="utf-8")
    m = re.search(r"TIME_LIMIT_HANDLING\s*=\s*\{(.*?)\n\}", src, re.S)
    if not m:
        return {}
    return dict(re.findall(r'"(\w+)":\s*"(\w+)"', m.group(1)))


TIME_LIMIT = _time_limit_handling()

# The uniform-random-policy floor on Door, measured over 400 episodes with zero successes
# (C55). A return at or below this is indistinguishable from acting randomly, and no ratio
# may be built on it -- C18/RIGOR.md: retention over a near-floor denominator is not a small
# number, it is an undefined one that looks like a number.
# [2026-09-05] The floor has ONE home: scripts/rlvigen_reference.DOOR_RANDOM_FLOOR, measured over
# 200 paired episodes. A local literal here drifted to 1.82 while the measurement moved to 1.842.
# Imported rather than copied, and it fails LOUDLY rather than falling back to a stale default --
# a wrong floor silently turns "at chance" into "competent" and back.
def _door_random_floor() -> float:
    import importlib.util as _u
    import pathlib as _p
    _spec = _u.spec_from_file_location(
        "_rlvigen_reference", _p.Path(__file__).resolve().parent / "rlvigen_reference.py")
    _module = _u.module_from_spec(_spec)
    _spec.loader.exec_module(_module)
    return float(_module.DOOR_RANDOM_FLOOR)


RANDOM_FLOOR = _door_random_floor()

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
        provenance = (final or {}).get("provenance") or provenance_for(baseline)
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
            "provenance": provenance,
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
    lines.append("| baseline | source target | source variant | frames | regime | eps | return | success | estimator | stack | timelimit | render |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        at_floor = isinstance(r["mean"], (int, float)) and r["mean"] <= RANDOM_FLOOR
        mean = (f"{r['mean']:.3f}{' ⌊' if at_floor else ''}"
                if isinstance(r["mean"], (int, float)) else "—")
        succ = f"{r['success']:.2f}" if isinstance(r["success"], (int, float)) else "—"
        lines.append(
            f"| `{r['baseline']}`{' ⚠' if r['baseline'] == 'ctrl' else ''} | "
            f"{r['provenance']['source_target']} | {r['provenance']['source_variant']} | "
            f"{r['frames'] or '—'} | "
            f"{(str(r['regime']) + ('!' if r.get('regime_substituted') else '') + ('*' if r['baseline'] == 'alda' else '')) if r['regime'] else '—'} | "
            f"{r['episodes'] or '—'} | {mean} | {succ} | "
            f"{ESTIMATOR.get(r['baseline'], '?')} | {STACK.get(r['baseline'], '?')} | "
            f"{TIME_LIMIT.get(r['baseline'], '?')} | "
            f"{r['mujoco_gl'] or '—'} |")

    missing = [r["baseline"] for r in rows if r["mean"] is None]
    have = {r["baseline"] for r in rows}
    # [Claude 2026-09-07] The estimator split is the fleet's ONLY UNITS-class comparability split
    # (audit_comparability_seam.py, "evaluation policy mode"), and until now this table displayed it
    # per row without ever saying that rows on opposite sides are not comparable. eval_grid.py's own
    # comment claims "no table pools the two"; that claim was unenforced -- only C1's time-limit
    # split had a guard, in the LEGACY results_table.py. A UNITS split is stronger than C1's: a
    # CONDITIONS split makes a difference unattributable, this one makes the numbers different
    # quantities. E[return | a = argmax pi] is not E[return | a ~ pi].
    estimator_groups = sorted({ESTIMATOR.get(r["baseline"], "?") for r in rows})
    if len(estimator_groups) > 1:
        by_estimator = {g: sorted({r["baseline"] for r in rows
                                   if ESTIMATOR.get(r["baseline"], "?") == g})
                        for g in estimator_groups}
        print("\n  WARNING (UNITS): this table pools two EVALUATION POLICY MODES in one comparison:")
        for group, names in by_estimator.items():
            print(f"    {group:<8} {', '.join(names)}")
        print("    These are different estimands, not the same estimand measured differently, so")
        print("    returns are NOT rankable across the two groups. eval_grid.py reproduces each")
        print("    family's own action rule deliberately (evaluator_identity.FAMILY_EVAL_POLICY_MODE),")
        print("    taken from each one's released EVALUATOR. The owner has ruled the split")
        print("    acceptable rather than absent (notes/SAME-AXES-VERDICT.md), and no secondary")
        print("    deterministic pass is scheduled, so a cross-group comparison here is")
        print("    DESCRIPTIVE ONLY: rank within a group, never across.")

    absent = sorted(set(ESTIMATOR) - have)

    lines.append("")
    lines.append(f"**{len(have)} of 12 baselines present**"
                 + (f"; absent: {', '.join(absent)}" if absent else "; all twelve present"))
    if missing:
        lines.append(f"**No eval number for**: {', '.join(missing)} — the cell ran but its "
                     "evaluation did not land, which is an R7 break, not a low score.")
    lines.append("")
    # Counted from ESTIMATOR, not typed: this sentence said "four ... and eight" and went wrong
    # the moment ctrl was corrected from SAMPLE to mode (its released evaluator is greedy).
    _sampled = sorted(b for b, e in ESTIMATOR.items() if e == "SAMPLE")
    _moded = sorted(b for b, e in ESTIMATOR.items() if e != "SAMPLE")
    lines.append(f"**This table may not be sorted by return.** {len(_sampled)} baselines report a "
                 f"SAMPLED return ({', '.join('`' + b + '`' for b in _sampled)}) and {len(_moded)} "
                 "report a mode return; the two are different quantities. Rows are also grouped by "
                 "frame stack, because a single-frame baseline on a manipulation task is "
                 "velocity-blind — a different POMDP, not a weaker algorithm (C2).")
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
    lines.append("**`ctrl`'s native training metrics remain separate from its offline row.** "
                 "The offline evaluator drives `algo.select_action(..., sample=False)` -- ctrl's "
                 "released evaluator is greedy (`evaluate_ppo.py:84`), so the mode is its native "
                 "rule -- on a "
                 "continuous 7-DoF environment and records a fixed-policy episode mean, so it is "
                 "the same *kind* of measurement as the other offline rows. Its native "
                 "`Eprew200`/`Eprew0` values are still successive-policy trailing-window metrics and "
                 "must not be promoted into the shared return column.")
    lines.append("")
    lines.append("**A blank `eps` in a native ctrl record remains meaningful, not a formatting gap.** "
                 "`ctrl`'s training loop reports `Eprew200`/`Eprew0`, a running mean over a trailing "
                 "window; its offline evaluator reports the declared fixed-N endpoint estimate. "
                 "The two are different quantities and are kept under their native names.")
    lines.append("")
    lines.append("**`render` must be identical across rows to compare them at all** (C95): a "
                 "container-trained policy evaluated under a different rasteriser reads 12–14x "
                 "low. Any row showing `glfw` beside rows showing `egl` is not comparable.")
    lines.append("")
    tl_present = sorted({TIME_LIMIT.get(r["baseline"], "?") for r in rows})
    lines.append("**`timelimit` is C1, rated the largest comparability defect found.** Door has no "
                 "early termination, so every episode ends by time limit. `terminal` baselines "
                 "(`drqv2 svea sgqn curl drq ctrl idaac ppg ibac_sni`) zero the value bootstrap "
                 "there on every episode throughout training; `bootstrap` baselines (`rad soda "
                 "alda`) bootstrap through it correctly. This biases every `terminal` critic's "
                 "target downward relative to every `bootstrap` one before a single episode is "
                 "evaluated, and it is not visible in `return` or `success` above -- both are "
                 "summed real reward, not the value function. **Rows may not be ranked across this "
                 "column** (CONSTRUCTION.md#c1's DEFAULT: declare, do not equalise)."
                 + (f" This table currently mixes both: {', '.join(tl_present)}."
                    if len(tl_present) > 1 else ""))

    text = "\n".join(lines)
    if a.out:
        a.out.write_text(text + "\n")
        print(f"wrote {a.out}")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
