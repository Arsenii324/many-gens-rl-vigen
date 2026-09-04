#!/usr/bin/env python3
"""Derive the production schedule from measured throughput and the replay memory law.

datasphere/native/production-schedule.json used to be written by hand, and it carried a claim --
that disk binds a pack at 500k -- which the memory law later overturned: ReplayBuffer hardcodes
`self._save_snapshot = False` (RL-ViGen-upstream/replay_buffer.py:94), so every episode file is
unlinked as it is loaded and disk stays flat for the length of a run. What accumulates is worker
resident memory. A hand-maintained schedule cannot be re-checked against a corrected premise;
this one is regenerated, so a premise that changes changes the plan.

    python datasphere/native/plan_production.py --frames 600000 > datasphere/native/production-schedule.json

Nothing submits from this. It exists so the production shape is arithmetic.
"""

from __future__ import annotations

import argparse
import json

# Completed-cell throughput, one cell alone on gt4.1, from returned artifacts parsed by
# summarize_result.py. Anything absent here is unmeasured and stays unmeasured in the output --
# an estimate pooled silently with a measurement is the error this file exists to avoid.
#
# [Claude 2026-09-04] **These rates are 10k rates, and a 10k rate is not a long-run rate.** The
# first 100k cell (`bt15e9v1k2ngmb71hnjn`, drqv2) measured **26.05 fps whole-run** and **26.49 fps
# steady-state** between the 25k and 75k stamps -- against the 17.53 recorded here from 10k, a
# **1.49x** discrepancy in the direction that matters: a 10k cell amortises a fixed bootstrap
# (clone, dependency install, env build, seed phase) over a tenth of the frames, so it reports the
# baseline as slower than it runs. drqv2's projected solo cost falls from 9.51 h/seed to ~6.4.
#
# Only drqv2 is updated, because only drqv2 has a long cell. **The other nine remain 10k-based and
# are therefore probably conservative by a similar factor** -- which makes the totals below an
# upper bound rather than an estimate, and makes them internally INCONSISTENT across baselines
# (one long-run rate beside nine short-run ones). That is stated rather than hidden: the
# alternative was to leave a 1.49x error standing on the single largest cost driver.
MEASURED_FPS_GT4_1 = {
    "drqv2": 26.05, "curl": 13.11, "drq": 12.48, "svea": 9.99, "sgqn": 6.50,
    "rad": 6.14, "soda": 3.25, "idaac": 34.82, "ppg": 28.14, "ibac_sni": 26.63,
    # [Claude 2026-09-04] alda and ctrl were absent because this file's header said they "have no
    # successful CUDA run yet". **Stale on both counts, and the totals were excluding a sixth of
    # the fleet**: `alda` completed bt13km8g093do0fdtc58 (all five NATIVE_ALDA_STAGE markers,
    # NATIVE_FINAL_EVALUATION_COMPLETED frame=10000, a finite 27.8M-value snapshot) and `ctrl`
    # completed bt1ums2q8170s3cq5p9l the same way.
    #
    # **CONVERTED, not directly measured** -- flagged rather than dropped in beside the others.
    # Both cells ran on gt4i.1: alda 10,000 frames in 1001.92 s (9.98 fps), ctrl 10,000 in
    # 587.83 s (17.01 fps), divided by the 1.14 tier factor this file already measures on drqv2
    # (20.05 vs 17.53) to reach the gt4.1 basis the dict is defined in. FPS_BASIS records which is
    # which, because this file's own rule is that an estimate must not be pooled silently with a
    # measurement.
    "alda": 8.75, "ctrl": 14.92,
}

#: How each rate was obtained: a directly timed gt4.1 cell, or a gt4i.1 cell converted by 1.14.
FPS_BASIS = {b: "measured" for b in
             ("drqv2", "curl", "drq", "svea", "sgqn", "rad", "soda", "idaac", "ppg", "ibac_sni")}
FPS_BASIS.update({"alda": "converted from gt4i.1 x1.14", "ctrl": "converted from gt4i.1 x1.14"})
#: Which budget each rate above was measured at, so a reader can see the inconsistency rather than
#: infer it. Anything at 10000 should be re-measured before a production commitment.
FPS_MEASURED_AT_FRAMES = {
    "drqv2": 100000, "curl": 10000, "drq": 10000, "svea": 10000, "sgqn": 10000,
    "rad": 10000, "soda": 10000, "idaac": 10000, "ppg": 10000, "ibac_sni": 10000,
    "alda": 10000, "ctrl": 10000,
}

# Resident set and device memory of one cell at 10k, same source. `rss_gib` is the floor a cell
# occupies before its replay grows; for the RL-ViGen five the growth term is added below.
ENVELOPE = {
    "drqv2": {"rss_gib": 3.29, "vram_mib": 1650, "cores": 1.27},
    "curl":  {"rss_gib": 3.24, "vram_mib": 2194, "cores": 1.20},
    "drq":   {"rss_gib": 3.35, "vram_mib": 2950, "cores": 1.17},
    "svea":  {"rss_gib": 3.74, "vram_mib": 2358, "cores": 2.52},
    "sgqn":  {"rss_gib": 3.98, "vram_mib": 7142, "cores": 1.90},
    "rad":   {"rss_gib": 2.58, "vram_mib": 1476, "cores": 1.04},
    "soda":  {"rss_gib": 3.66, "vram_mib": 2582, "cores": 1.66},
    "idaac": {"rss_gib": 2.90, "vram_mib": 1204, "cores": 1.35},
    "ppg":   {"rss_gib": 4.20, "vram_mib": 1588, "cores": 1.80},
    "ibac_sni": {"rss_gib": 3.10, "vram_mib": 1102, "cores": 1.10},
}

# `units_per_hour` is the currency the DataSphere GRANT is denominated in, and it is the one that
# decides feasibility -- docs/compute-yandex-datasphere.md records the arsen4ikvar grant at
# 5,000,000 units, which is about 38.6 hours of gt4.1. gt4.1's rate is published; gt4i.1's is not,
# so it is scaled by the RUB ratio and marked derived.
TIERS = {
    "gt4.1":  {"rub_per_hour": 168.48, "units_per_hour": 129_600, "units_source": "published",
               "cores": 4, "ram_gib": 16.0, "usable_ram_gib": 14.5, "vram_mib": 15360},
    "gt4i.1": {"rub_per_hour": 234.00, "units_per_hour": 180_000, "units_source": "derived from "
               "the RUB ratio 234.00/168.48; gt4i.1 is not in the published unit table",
               "cores": 8, "ram_gib": 32.0, "usable_ram_gib": 27.0, "vram_mib": 23034},
}

GRANT_UNITS = 5_000_000

RLVIGEN = ("drqv2", "svea", "drq", "sgqn", "curl")
DMC_GB = ("rad", "soda")
ONPOLICY = ("idaac", "ppg", "ibac_sni", "ctrl")

# Bytes of worker-resident replay per retained transition, RL-ViGen five. Two 84x84x9 uint8
# observations dominate; derived from source and confirmed against the endurance job's resident
# samples (tree RSS 10.6 -> 15.8 GiB monotonic over 100k frames, four workers).
BYTES_PER_TRANSITION = 63_504

# rad/soda allocate their whole buffer up front at construction, so the budget -- not the frames
# actually run -- sets the resident size, and a cap is the only lever.
DMC_GB_BYTES_PER_FRAME = 30_000

# ALDA's trainer holds a fixed working set independent of budget (measured 15.3 GiB at 10k).
ALDA_FIXED_GIB = 15.3

GIB = 1024 ** 3


def cell_ram_gib(baseline: str, frames: int, capacity: int | None) -> tuple[float, str]:
    """Resident memory one cell reaches at the end of a run, and what sets it."""
    if baseline in RLVIGEN:
        retained = min(frames, capacity) if capacity else frames
        floor = ENVELOPE[baseline]["rss_gib"]
        return floor + retained * BYTES_PER_TRANSITION / GIB, "replay grows to the cap"
    if baseline in DMC_GB:
        retained = min(frames, capacity) if capacity else frames
        return ENVELOPE[baseline]["rss_gib"] + retained * DMC_GB_BYTES_PER_FRAME / GIB, \
            "replay preallocated at construction"
    if baseline == "alda":
        return ALDA_FIXED_GIB, "fixed working set, budget-independent"
    return ENVELOPE.get(baseline, {}).get("rss_gib", 4.2), "on-policy rollout only, budget-independent"


def plan_row(baseline: str, frames: int, capacity: int | None, seeds: list[int]) -> dict:
    ram, ram_reason = cell_ram_gib(baseline, frames, capacity)
    vram = ENVELOPE.get(baseline, {}).get("vram_mib")
    row: dict = {
        "baseline": baseline,
        "frames": frames,
        "seeds": seeds,
        "replay_capacity": capacity,
        "cell_ram_gib": round(ram, 2),
        "cell_ram_set_by": ram_reason,
        "cell_vram_mib": vram,
    }

    fps = MEASURED_FPS_GT4_1.get(baseline)
    row["throughput_source"] = FPS_BASIS.get(baseline, "measured") if fps else "unmeasured"
    if fps:
        row["solo_hours_per_seed_gt4_1"] = round(frames / fps / 3600, 2)

    # Smallest tier that holds one cell, then how many cells fit beside it.
    for name in ("gt4.1", "gt4i.1"):
        tier = TIERS[name]
        if ram <= tier["usable_ram_gib"] and (vram is None or vram <= tier["vram_mib"]):
            row["tier"] = name
            by_ram = int(tier["usable_ram_gib"] // ram)
            by_vram = int(tier["vram_mib"] // vram) if vram else by_ram
            by_cores = max(1, int(tier["cores"] // max(1.0, ENVELOPE.get(baseline, {}).get("cores", 1.0))))
            row["max_cells_per_job"] = max(1, min(by_ram, by_vram, by_cores))
            row["packing_limited_by"] = min(
                (("host memory", by_ram), ("device memory", by_vram), ("cores", by_cores)),
                key=lambda item: item[1],
            )[0] if row["max_cells_per_job"] > 0 else "host memory"
            break
    else:
        row["tier"] = None
        row["max_cells_per_job"] = 0
        row["packing_limited_by"] = "no allowed tier holds one cell"

    if fps and row["tier"]:
        # gt4i.1 measured 1.14x gt4.1 on drqv2 (20.05 vs 17.53); packed cells retain 0.658 of
        # solo throughput at four cells, measured at 10k on gt4i.1.
        speed = 1.14 if row["tier"] == "gt4i.1" else 1.0
        retention = 0.658 if row["max_cells_per_job"] > 1 else 1.0
        per_seed_hours = frames / (fps * speed * retention) / 3600
        jobs = -(-len(seeds) // row["max_cells_per_job"])
        row["job_hours"] = round(per_seed_hours, 2)
        row["jobs_for_all_seeds"] = jobs
        row["rub_all_seeds"] = round(jobs * per_seed_hours * TIERS[row["tier"]]["rub_per_hour"])
        row["units_all_seeds"] = round(jobs * per_seed_hours * TIERS[row["tier"]]["units_per_hour"])
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=600_000)
    parser.add_argument("--rlvigen-capacity", type=int, default=300_000)
    # dmc_gb's buffer is `capacity=args.train_steps` with no flag (train.py:111), so a cap is not
    # reachable without a source change. The default models the world as it is; pass the flag to
    # price what that change would buy.
    parser.add_argument("--dmc-gb-capacity", type=int, default=None)
    parser.add_argument("--seeds", default="101,102,103")
    args = parser.parse_args()

    seeds = [int(item) for item in args.seeds.split(",")]
    order = RLVIGEN + DMC_GB + ("alda",) + ONPOLICY
    rows = []
    for baseline in order:
        capacity = args.rlvigen_capacity if baseline in RLVIGEN else (
            args.dmc_gb_capacity if baseline in DMC_GB else None)
        if baseline in DMC_GB and capacity is None:
            capacity = args.frames  # uncapped: the budget IS the resident size, preallocated
        rows.append(plan_row(baseline, args.frames, capacity, seeds))

    measured = [row for row in rows if row.get("rub_all_seeds")]
    total_rub = sum(row["rub_all_seeds"] for row in measured)
    total_units = sum(row["units_all_seeds"] for row in measured)
    total_job_hours = sum(row["jobs_for_all_seeds"] * row["job_hours"] for row in measured)

    print(json.dumps({
        "_comment": [
            "GENERATED by datasphere/native/plan_production.py -- do not hand-edit; regenerate.",
            "Nothing submits from this file. It makes the production shape arithmetic.",
            "Costs cover all TWELVE baselines as of 2026-09-04. Ten rates are measured directly",
            "on gt4.1; alda and ctrl are CONVERTED from timed gt4i.1 cells by the 1.14 tier factor",
            "and are marked `converted` in throughput_source, never pooled silently as measured.",
            "This note previously said alda and ctrl had no successful CUDA run and excluded them,",
            "which understated every total by a sixth of the fleet after both had in fact",
            "completed (bt13km8g093do0fdtc58, bt1ums2q8170s3cq5p9l).",
        ],
        "frames": args.frames,
        "seeds": seeds,
        "tiers": TIERS,
        "memory_law": {
            "rlvigen_bytes_per_retained_transition": BYTES_PER_TRANSITION,
            "dmc_gb_bytes_per_budgeted_frame": DMC_GB_BYTES_PER_FRAME,
            "alda_fixed_gib": ALDA_FIXED_GIB,
            "dmc_gb_cap_reachable": args.dmc_gb_capacity is not None,
            "dmc_gb_cap_note": "rad/soda take capacity=args.train_steps with no flag; a cap needs "
                               "a source change. Default here is uncapped.",
            "disk": "flat: ReplayBuffer sets _save_snapshot=False (replay_buffer.py:94) and unlinks "
                    "each episode as it loads it, and eviction unlinks too. Disk does not bind.",
        },
        "rows": rows,
        "totals_measured_only": {
            "baselines_counted": [row["baseline"] for row in measured],
            "job_hours": round(total_job_hours, 1),
            "rub": total_rub,
            "units": total_units,
            "grant_units": GRANT_UNITS,
            "grant_multiples": round(total_units / GRANT_UNITS, 1),
            "wall_clock_days_at_two_parallel_jobs": round(total_job_hours / 2 / 24, 1),
            "wall_clock_days_at_four_parallel_jobs": round(total_job_hours / 4 / 24, 1),
            "note": "`units` is the currency the grant is in and is what decides feasibility. "
                    "Whether this project draws on the 5,000,000-unit grant or on a paid RUB "
                    "balance is NOT established here -- both are reported so the answer picks the "
                    "column rather than needing a re-derivation.",
        },
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
