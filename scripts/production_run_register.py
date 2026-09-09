#!/usr/bin/env python3
"""One catalogue of every run whose records this repository holds — regenerated, never hand-kept.

    python scripts/production_run_register.py            # write results/PRODUCTION-RUNS.md
    python scripts/production_run_register.py --check    # fail if the file is stale
    python scripts/production_run_register.py --stdout   # print without writing

## Why this exists

Records accumulated as 70 opaque `results/records/<job>__records.jsonl` files. Answering "what runs
do we have, under what circumstances, and what did they measure" meant reading them. A catalogue
that a human maintains goes stale the first busy day, so this one is **generated from the records
themselves** and `--check` fails the build when it drifts.

## What it reports, and the rule it follows

For every job: the cells and seeds, the frame span, the evaluator revision each row was produced
under, the policy modes, the headline numbers, and the path to every file this repo holds for it.

**Circumstances that are NOT visible are listed as not visible.** That is the point of the caveats
section rather than a disclaimer: a catalogue that silently omits what it cannot see teaches its
reader that absence means "fine". Checkpoints are not in this repository at all
(`docs/EVAL-PROTOCOL.md` §6: checkpoints stay remote, records come back), so no run here can be
re-evaluated from what is catalogued.

## What it deliberately does not do

**No ranking, no aggregation across baselines.** `policy_mode` differs across families and
`scripts/comparison_blocks.py` is what adjudicates which numbers may sit beside each other. This is
an inventory.
"""
from __future__ import annotations

import argparse
import collections
import datetime
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
RECORDS = ROOT / "results" / "records"
LOGS = ROOT / "results" / "logs"
OUT = ROOT / "results" / "PRODUCTION-RUNS.md"


def _rows(path: pathlib.Path) -> list[dict]:
    out = []
    for line in path.read_text(errors="replace").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out



#: `eval_grid.py` emits one row per scene AND one pooled row per regime. The pooled row is the
#: AUTHORITATIVE regime statistic and this code must prefer it.
#:
#: [Claude 2026-09-09] Three successive readings of this, each wrong, and the sequence is the lesson.
#: First I episode-weighted all eleven rows: the pooled row repeats the same episodes, so n came out
#: 400 for 200 distinct episodes and every SE was understated by sqrt(2). Then I excluded the pooled
#: row and weighted the ten: n was right, but the SD became the MEAN OF PER-SCENE SDs, which discards
#: between-scene variance -- and on this task the scene means span 11.84 to 49.44, so that understated
#: the SE by a further 1.11x to 1.40x.
#:
#: The pooled row already carries the right thing: `eval_grid.py:1261` builds it from
#: `np.concatenate(per_scene)` with `pooled.std(ddof=1)`, so its SD includes between-scene spread and
#: it costs no extra evaluation. It also self-identifies via `native.aggregate_over_scenes`, which is
#: an explicit marker rather than the comma-in-scene_set heuristic I started with.
#:
#: Every iteration moved the same way -- eval-easy 1.2 sigma, then 0.9, then 0.8 -- so the original
#: numbers overstated confidence. Hence: use the pooled row; fall back to per-scene only when it is
#: absent, and say so, because that fallback's SE is a floor rather than the value.
def is_summary_row(row: dict) -> bool:
    native = row.get("native") or {}
    if native.get("aggregate_over_scenes"):
        return True
    return "," in str(row.get("scene_set", ""))


#: Whether a regime's reset observation is reproducible, and therefore whether a PAIRED claim about
#: it is available. Measured on two independent families and two cells (`idaac` card0-20260909-035152,
#: `ppg` card0-20260909-115331): the fraction of (regime, scene, episode) slots whose reset
#: observation differs across frames or passes was 0 % / 0 % for `train` and `eval-easy` in both, and
#: 62 % / 67 % for `eval-medium`, 10 % / 23 % for `eval-hard`.
#:
#: The cause is upstream and deliberate (`robosuitevgb/utils.py:67-90`: `moving_light`,
#: `except_robot=False`), so this is a property of the benchmark rather than a fault. It is carried
#: into the table because the numbers are read here, and a reader comparing an `eval-medium` figure
#: across passes or frames is comparing different pixels as well as different policies.
PAIRING = {
    "train": "**paired**",
    "eval-easy": "**paired**",
    "eval-medium": "not paired ⚠",
    "eval-hard": "not paired ⚠",
}


def unweightable(rows: list[dict]) -> int:
    """Rows carrying no `episodes`, which any weighted mean silently drops.

    [Claude 2026-09-09] Counted across the collected fleet: `phase=eval` rows exist at **10, 5, 1 and
    None** episodes and `phase=offline-eval` at 3, 5, 10, 20, 30, 100 and 200 -- so a one-episode
    measurement sits in the same stream as a two-hundred-episode one, and 1,440 rows carry no count
    at all. `r.get("episodes") or 0` drops those from every weighted mean. Dropping them is right;
    doing it without saying so is not, which is the whole of this function.
    """
    return sum(1 for r in rows if not (r.get("episodes") or 0))


def regime_stat(rows: list[dict]) -> tuple[float, float | None, int, bool]:
    """(mean, standard error, episodes, exact) for one regime.

    `exact` is False when no pooled row was found and the SE is a per-scene approximation that
    OMITS between-scene variance -- a floor, not the value.
    """
    pooled = [r for r in rows if is_summary_row(r)]
    if pooled:
        r = max(pooled, key=lambda x: x.get("episodes") or 0)
        n = r.get("episodes") or 0
        sd = r.get("episode_return_sd")
        return (r.get("episode_return_mean"),
                (sd / (n ** 0.5)) if (sd and n) else None, n, True)
    per = [r for r in rows if not is_summary_row(r)]
    n = sum(r.get("episodes") or 0 for r in per)
    if not n:
        return (float("nan"), None, 0, False)
    mean = sum((r.get("episode_return_mean") or 0.0) * (r.get("episodes") or 0) for r in per) / n
    sd = sum((r.get("episode_return_sd") or 0.0) * (r.get("episodes") or 0) for r in per) / n
    return (mean, (sd / (n ** 0.5)) if sd else None, n, False)


def _weighted(rows: list[dict], key: str) -> float | None:
    """Episode-weighted mean over the per-scene rows. Used for RATES, where it is exact.

    [Claude 2026-09-09] Deliberately NOT switched to `regime_stat`, and the reason is worth keeping
    so this is not "fixed" later. For a rate, the episode-weighted mean of per-scene rates is
    algebraically the pooled rate -- sum(rate_i * n_i)/sum(n_i) = sum(successes_i)/sum(n_i) -- and
    that is exactly what `eval_grid.py:1263` computes as `successes / pooled.size`. Verified against
    the real records: identical to 0.00e+00.

    The same is true of the MEAN: per-scene weighted 31.5805 against pooled 31.5805. **Only the SD
    differs**, because averaging per-scene SDs discards between-scene variance -- which is why
    `regime_stat` exists for the mean-with-SE and this function does not need to change.
    """
    rows = [r for r in rows if not is_summary_row(r)] or rows
    n = sum(r.get("episodes") or 0 for r in rows)
    if not n:
        return None
    return sum((r.get(key) or 0.0) * (r.get("episodes") or 0) for r in rows) / n


def build() -> str:
    files = sorted(RECORDS.glob("*.jsonl"))
    lines: list[str] = []
    add = lines.append

    add("<!-- GENERATED by scripts/production_run_register.py — do not edit by hand. -->")
    add("<!-- Regenerate: python scripts/production_run_register.py -->")
    add("")
    add("# Production run register")
    add("")
    add("Every run whose records this repository holds, with the circumstances each record carries "
        "and the files that back it. **Generated from `results/records/`**; "
        "`scripts/production_run_register.py --check` fails when it drifts.")
    add("")

    total_rows = 0
    per_job: list[tuple[str, list[dict], pathlib.Path]] = []
    for f in files:
        rows = _rows(f)
        total_rows += len(rows)
        per_job.append((f.name.split("__", 1)[0], rows, f))

    baselines = collections.Counter(r.get("baseline") for _, rows, _ in per_job for r in rows)
    add(f"**{len(per_job)} job(s), {total_rows} record row(s), "
        f"{len([b for b in baselines if b])} baseline(s).**")
    add("")
    add("| baseline | rows |")
    add("|---|---:|")
    for b, n in sorted(baselines.items(), key=lambda kv: (-kv[1], str(kv[0]))):
        add(f"| `{b}` | {n} |")
    add("")

    add("## Runs")
    add("")
    for job, rows, path in sorted(per_job, key=lambda t: t[0]):
        if not rows:
            add(f"### `{job}` — **EMPTY RECORD FILE**")
            add("")
            add(f"- records: [`{path.relative_to(ROOT)}`]({path.relative_to(ROOT)}) — 0 rows. "
                "A job that returned no rows is a finding, not an empty result.")
            add("")
            continue
        cells = sorted({str(r.get("cell")) for r in rows if r.get("cell")})
        seeds = sorted({str(r.get("seed")) for r in rows if r.get("seed") is not None})
        bl = sorted({str(r.get("baseline")) for r in rows if r.get("baseline")})
        frames = sorted({int(float(r["frame"])) for r in rows if r.get("frame") is not None})
        revs = sorted({str(r.get("evaluator_revision"))[:12] for r in rows
                       if r.get("evaluator_revision")})
        modes = sorted({(r.get("evaluator_scope") or {}).get("eval_policy_mode")
                        for r in rows} - {None})
        phases = collections.Counter(r.get("phase") for r in rows)

        add(f"### `{job}` — {', '.join(bl) or '?'}")
        add("")
        add(f"- **cells** `{', '.join(cells) or '?'}` · **seeds** `{', '.join(seeds) or '?'}` · "
            f"**rows** {len(rows)}")
        if frames:
            add(f"- **frames** {frames[0]:,} → {frames[-1]:,} ({len(frames)} distinct)")
        add(f"- **phases** {dict(phases)}")
        add(f"- **policy mode(s)** {', '.join(f'`{m}`' for m in modes) or '`not recorded`'}")
        add(f"- **evaluator revision(s)** {', '.join(f'`{r}`' for r in revs) or '`none`'}")
        add(f"- **records** [`{path.relative_to(ROOT)}`]({path.relative_to(ROOT)})")
        log_hits = sorted(LOGS.glob(f"{job}*")) if LOGS.is_dir() else []
        if log_hits:
            add("- **logs** " + ", ".join(f"[`{p.name}`]({p.relative_to(ROOT)})" for p in log_hits[:4]))
        else:
            # [review B5] "none" conflated "not installed here" with "does not exist". A host run's
            # curve lives at native-out/cells/<cell>/progress-*.csv in its run directory and is
            # never copied into results/logs/, so every host run read as having no curve at all.
            add("- **logs** none installed in `results/logs/`. For a host run the curve is at "
                "`native-out/cells/<cell>/progress-*.csv` **in its run directory**, not here.")

        assembled = sum(1 for r in rows if "_assembled_after_reaping" in r)
        if assembled:
            add(f"- ⚠ **{assembled} row(s) were ASSEMBLED after a reaping**, not delivered by the "
                "runner (`scripts/assemble_reaped_delivery.py`). Each carries "
                "`_assembled_after_reaping`.")
        noprov = sum(1 for r in rows if "_run_provenance_missing" in r)
        if noprov:
            add(f"- ⚠ **{noprov} row(s) carry no run provenance** — auditable for content, not for "
                "the job that produced them.")

        # [review B6] The curve was reported only as a frame count, though for `idaac` it is 484 of
        # 528 rows and it is what makes a plateau visible. First / peak / last on the train regime.
        curve = [r for r in rows
                 if (r.get("evaluator_scope") or {}).get("eval_scope") == "curve"
                 and r.get("regime") == "train" and r.get("frame") is not None]
        if curve:
            byf = collections.defaultdict(list)
            for r in curve:
                byf[int(float(r["frame"]))].append(r)
            pts = [(f, regime_stat(byf[f])[0], regime_stat(byf[f])[1]) for f in sorted(byf)]
            pts = [(f, v, se) for f, v, se in pts if v is not None]
            if pts:
                peak = max(pts, key=lambda kv: kv[1])
                ses = [se for _, _, se in pts if se]
                typical_se = sorted(ses)[len(ses) // 2] if ses else None
                line = (f"- **curve** (train regime, {len(pts)} stamp(s)): "
                        f"first {pts[0][1]:.2f} @{pts[0][0]:,} · "
                        f"**peak {peak[1]:.2f} @{peak[0]:,}** · last {pts[-1][1]:.2f} @{pts[-1][0]:,}")
                if typical_se:
                    line += f" · **SE ≈ {typical_se:.1f} per point**"
                if pts[-1][1] < 0.8 * peak[1]:
                    drop = peak[1] - pts[-1][1]
                    line += ("  — ends below its peak"
                             + (f" by {drop / typical_se:.1f} SE" if typical_se else ""))
                add(line)
                if typical_se:
                    add(f"  <br/>*A move smaller than about {2 * typical_se:.1f} between stamps is "
                        f"inside 2 SE and is not a trend.*")

        # headline numbers, endpoint scope only, split by policy mode so nothing is pooled
        end = [r for r in rows if (r.get("evaluator_scope") or {}).get("eval_scope") == "endpoint"]
        if end:
            add("")
            add("  | policy mode | regime | return | **SE** | success rate | episodes | scenes | paired? |")
            add("  |---|---|---:|---:|---:|---:|---:|---|")
            grouped = collections.defaultdict(list)
            for r in end:
                grouped[((r.get("evaluator_scope") or {}).get("eval_policy_mode"),
                         r.get("regime"))].append(r)
            for key in sorted(grouped, key=lambda k: (str(k[0]), str(k[1]))):
                g = grouped[key]
                ret, se, eps, exact = regime_stat(g)
                sr = _weighted(g, "success_rate")
                scenes = len([x for x in g if not is_summary_row(x)])
                dropped = unweightable(g)
                se_txt = ("± %.2f" % se) if se else "—"
                if se and not exact:
                    se_txt += " ⚠"          # per-scene floor: omits between-scene variance
                eps_txt = f"{eps}" + (f" (+{dropped} unweightable)" if dropped else "")
                add(f"  | `{key[0]}` | {key[1]} | {ret:.2f} | {se_txt} | {sr:.3f} | "
                    f"{eps_txt} | {scenes} | {PAIRING.get(key[1], '?')} |")
        add("")

    host = ROOT / "results" / "host-runs.jsonl"
    if host.is_file():
        entries = _rows(host)
        collected = {f.name.split("__", 1)[0] for f in files}
        pending = [e for e in entries if e.get("run_id") not in collected]
        add("## Runs on the production host not yet collected")
        add("")
        add("Recorded when launched, from each cell's own `effective_config.json`, so a run's "
            "existence does not depend on anyone's memory. Source: "
            "[`host-runs.jsonl`](host-runs.jsonl). **These have no records in this repository "
            "yet** — that is the point of listing them.")
        add("")
        for e in entries:
            state = "**COLLECTED**" if e.get("run_id") in collected else "**not yet collected**"
            add(f"### `{e.get('run_id')}` — {e.get('baseline')} — {state}")
            add("")
            add(f"- **cell** `{e.get('cell')}` · **seed** {e.get('seed')} · "
                f"**frames** {e.get('frames_requested'):,} · **card** {e.get('card')} · "
                f"**profile** `{e.get('host_profile')}`")
            add(f"- **launched** {e.get('launched_msk')} MSK · "
                f"**run dir** `{e.get('run_dir')}` on `{e.get('host')}`")
            add(f"- **eval** curve {e.get('curve_eval_episodes')} ep/scene, endpoint "
                f"{e.get('endpoint_eval_episodes')} ep/scene, policy modes "
                f"`{e.get('endpoint_policy_modes')}`")
            asof = e.get("status_as_of")
            age = ""
            if asof:
                try:
                    dt = datetime.datetime.fromisoformat(asof)
                    hrs = (datetime.datetime.now(datetime.timezone.utc) - dt).total_seconds() / 3600
                    age = (f" — **status recorded {hrs:.0f}h ago**" if hrs >= 1
                           else " — status recorded under an hour ago")
                    if hrs >= 24:
                        age += " ⚠ **likely stale**"
                except ValueError:
                    age = f" — recorded {asof}"
            add(f"- **status** {e.get('status')}{age}")
            if e.get("note"):
                add(f"- ⚠ {e['note']}")
            add("")
        if pending:
            add(f"**{len(pending)} run(s) above have produced no record file here.** Until they "
                "are collected their numbers exist only on the host, and nothing in this "
                "repository can be used to check them.")
            add("")

    add("## Caveats — what this register cannot see")
    add("")
    add("Listed rather than omitted, because a catalogue that silently drops what it cannot see "
        "teaches its reader that absence means fine.")
    add("")
    add("**Derived versus asserted, because `--check` does not cover both.** Everything under "
        "*Runs* is generated from `results/records/` and `--check` fails when it drifts. The "
        "*not yet collected* section is **asserted** — statuses are snapshots written by hand at a "
        "recorded time, and nothing here can verify that those run directories still exist on the "
        "host. `--check` proves the first half current and says nothing about the second.")
    add("")
    add("1. **Checkpoints are not COMMITTED here, but they are not all remote either — the "
        "distinction matters.** `docs/EVAL-PROTOCOL.md` §6 (checkpoints stay remote, records come "
        "back) is about the multi-hundred-MB job archives. A host run's `native-out/` does retain "
        "intermediate checkpoints: measured on `card0-20260909-035152`, **53 MB across 11 files at "
        "4.8 MB each**, inside a 78 MB `native-out` whose sibling `native-work` is 1.9 GB and is "
        "never fetched. So a run CAN be re-evaluated — from a fetched `native-out`, not from this "
        "repository, which holds only the `.jsonl` records below.")
    add("2. **Runs not yet collected do not appear at all.** A cell that ran on the host and was "
        "never fetched is invisible here, not marked absent. `results/submissions.jsonl` and "
        "`results/attempt-outcomes.json` are the attempt-side record; this file is the "
        "records-side one, and they are not the same set.")
    add("3. **Circumstances come from what each row carries.** Renderer, container digest, "
        "resolved packages and source commit live in `_run_provenance`. `collect_record_delivery` "
        "does exactly two things — concatenate the training rows with `cells/*/offline_eval_*.jsonl`, "
        "and stamp that provenance onto the offline rows from `run_manifest.json`. **It computes no "
        "metric**; `eval_grid.py` did that. When a cell is stopped by its watch budget before that "
        "step runs, the rows exist and the bundle does not, and "
        "`scripts/assemble_reaped_delivery.py` performs the same two operations on a fetched copy — "
        "marking every row, and marking provenance as missing rather than inventing it. Rows "
        "without provenance are flagged above.")
    add("4. **`success_rate` and `return` are not independent for Door.** Its reward is 1.0 on "
        "success and at most 0.25+0.25 otherwise, so over a 500-step horizon a policy that never "
        "opens the door cannot exceed 250 and any return above 250 proves a success step. See "
        "[`../notes/what-a-door-return-number-means.md`](../notes/what-a-door-return-number-means.md).")
    add("5. **Returns are not comparable across `policy_mode`.** `idaac`, `ppg` and `ibac_sni` "
        "report a sampled return; the other nine report a mode return. Different estimands. "
        "`scripts/comparison_blocks.py` adjudicates; this register never pools them.")
    add("6. **`paired?` says whether a difference involving that regime is attributable to the "
        "regime.** `train` and `eval-easy` replay identical initial conditions AND identical pixels, "
        "so a gap between them is the regime alone. `eval-medium` and `eval-hard` **resample their "
        "visual perturbation between passes** -- 62 %/67 % of slots on two independent families -- "
        "so their numbers carry perturbation variance on top of episode variance and **no paired "
        "claim is available for them**, including the two policy-mode passes on one checkpoint. "
        "Measured by `scripts/audit_eval_validity.py`; upstream and deliberate, not a fault.")
    add("7. **Episode counts are NOT uniform, and rows without one are dropped from every "
        "weighted mean.** Across the collected fleet, `phase=eval` rows exist at 10, 5, 1 and "
        "**None** episodes and `phase=offline-eval` at 3, 5, 10, 20, 30, 100 and 200 -- a "
        "one-episode measurement in the same stream as a two-hundred-episode one. A row with no "
        "`episodes` cannot be weighted and is excluded; where that happens the episode cell above "
        "says `(+N unweightable)` rather than staying silent about it.")
    add("8. **Most collected rows predate `eval_scope` and cannot be classified.** Counted at "
        "generation time: of the rows here, only those carrying "
        "`evaluator_scope.eval_scope` can be split into curve and endpoint; the rest are reported "
        "without that distinction and contribute to no curve or endpoint summary. **No currently "
        "collected run has curve-scoped rows at all**, so the curve line below appears only for "
        "runs collected after that field existed.")
    add("9. **A superseded evaluator revision is still listed.** Whether a revision is current is "
        "`scripts/audit_row_closure.py`'s question, not this file's.")
    add("")
    add("## Overwrite safety")
    add("")
    add("A job id is the DataSphere job id or, for a host run, the run directory basename "
        "`card0-<YYYYmmdd-HHMMSS>` — unique per launch at second resolution. "
        "`datasphere/native/collect-host-run.sh` **refuses** to install over an existing "
        "`results/records/<job>__records.jsonl` whose content differs, and is idempotent when it "
        "matches, so re-collecting a run cannot destroy a past one "
        "(`tests/test_collect_host_run_guards.py`).")
    add("")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if the written file is stale")
    ap.add_argument("--stdout", action="store_true")
    args = ap.parse_args()

    text = build()
    if args.stdout:
        print(text)
        return 0
    if args.check:
        if not OUT.is_file():
            print(f"{OUT.relative_to(ROOT)} does not exist; run without --check to generate it")
            return 1
        if OUT.read_text() != text:
            print(f"{OUT.relative_to(ROOT)} is STALE. Regenerate: "
                  "python scripts/production_run_register.py")
            return 1
        print(f"{OUT.relative_to(ROOT)} is current.")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
