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
import hashlib
import importlib.util
import json
import pathlib

_HERE = pathlib.Path(__file__).resolve().parent
_DESCRIPTORS = json.loads(_HERE.joinpath("families.json").read_text())
_family_spec = importlib.util.spec_from_file_location("_native_family_for_plan", _HERE / "family.py")
_family = importlib.util.module_from_spec(_family_spec)
_family_spec.loader.exec_module(_family)
MINIMUM_TIER = {baseline: entry.get("minimum_tier", "gt4.1")
                for entry in _DESCRIPTORS.values() if isinstance(entry, dict)
                for baseline in entry.get("baselines", [])}
DECLARED_PACKING_CAP = {baseline: entry.get("production", {}).get("cells_per_job", 1)
                        for entry in _DESCRIPTORS.values() if isinstance(entry, dict)
                        for baseline in entry.get("baselines", [])}

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
    "rad": 6.14, "soda": 3.25,
    # [Claude 2026-09-07] idaac 34.82 is a PRE-C2 measurement: 4 processes, a 256-step
    # rollout, 1 PPO epoch, 8 minibatches. C2 runs 1 process x 2048 steps, 10 epochs, 32
    # minibatches -- heavier per environment step, and a bounded g1.1 V100 rehearsal (job
    # bt1596tjbdu1rv5senim) measured 24.57 fps for the current recipe. The two numbers are
    # on different tiers AND different recipes, so this one is not simply replaced: it is
    # flagged, because substituting a V100 figure into a dict defined on the gt4.1 basis
    # would be the pooling-an-estimate-with-a-measurement error this file forbids. Treat
    # idaac hours below as PRE-C2 until a gt4.1 C2 cell or a V100 schedule replaces them.
    "idaac": 34.82,
    # [Claude 2026-09-07, A36 RESOLVED] 28.14 was measured at the RETIRED 8x256 geometry.
    # Production now runs SS E's 1x2048, measured 32% slower on a same-tier paired probe
    # (78.54 vs 59.44 IPS, gt4i.1, 65,536 frames each). 28.14 x 0.757 = 21.3. The RATIO is
    # a real same-tier measurement; the absolute is still the gt4.1 basis this dict is
    # defined in, so a ratio is the only honest way to carry it across.
    "ppg": 21.3, "ibac_sni": 26.63,
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
FPS_BASIS.update({"alda": "converted from gt4i.1 x1.14", "ctrl": "converted from gt4i.1 x1.14",
                  "ppg": "gt4.1 8x256 measurement scaled by a same-tier 1x2048/8x256 ratio",
                  "idaac": "measured PRE-C2; the C2 recipe measured 24.57 fps on g1.1 V100"})
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
    "ctrl": {"rss_gib": 13.40, "vram_mib": None, "cores": 8.0},
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

V100_HOST = {
    "cpu_cores": 16,
    "ram_gib_available": 113,
    "gpu_count": 2,
    "gpu_model": "Tesla V100-SXM2-32GB",
    "gpu_vram_mib": 32 * 1024,
    "gpus_available_when_measured": 1,
    "availability_is_runtime_state": True,
    "source": "notes/remote-infra.txt (measured 2026-09-05)",
}

# [Claude 2026-09-04: checkpoint bytes, MEASURED from `retained.json` on real jobs -- not estimated.
# This block exists because enabling intermediate checkpoints changed the storage question and
# nobody had recomputed it: with a 50k grid a 6e5 cell writes TWELVE stamps plus the terminal one,
# so the archive is thirteen checkpoints where it used to be one.]
CHECKPOINT_MB = {
    "rlvigen": 104.1,   # drqv2 snapshot.pt, bt15e9v1k2ngmb71hnjn
    "dmc_gb": 104.1,    # not separately measured; same SAC-shaped encoder+critic+target as rlvigen
    "alda": 103.9,      # sac_None_step_10000.pt
    "ctrl": 39.8,       # checkpoint_10000.msgpack
    "ibac_sni": 27.6,   # model.pt, default (non-impala) architecture -- impala is 19x SMALLER
    "idaac": 5.0,
    "ppg": 5.0,
}
FAMILY_OF = {**{b: "rlvigen" for b in RLVIGEN}, **{b: "dmc_gb" for b in DMC_GB},
             "alda": "alda", "ctrl": "ctrl", "ibac_sni": "ibac_sni", "idaac": "idaac", "ppg": "ppg"}


#: Measured wall-clock per evaluation episode, by family. Imported rather than restated: this is
#: the same measurement `scripts/audit_job_budgets.py` uses to check that a job's timeout covers its
#: own grid, and the project has already paid once (Q12) for keeping one number in several places.
def _seconds_per_episode() -> dict:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_audit_job_budgets", _HERE.parents[1] / "scripts" / "audit_job_budgets.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return dict(module.MEASURED_SECONDS_PER_EPISODE), module.UNMEASURED_DEFAULT


def curve_eval_hours(frames: int, seeds: int, path: Path | None = None,
                     profile: str | None = "v100") -> dict:
    """Job-hours added by evaluating the intermediate grid in the container.

    [Claude 2026-09-07] Rewritten. The previous version took `save_every`, `episodes` and `regimes`
    as arguments with defaults of 10 and 2, modelled no scene axis at all, and had NO CALLERS --
    so `PRODUCTION-CALENDAR.md`'s trajectory numbers were computed by hand against it and then
    drifted: the calendar's per-baseline table still carried the superseded five-episode figure
    (8.08 h/cell = 291 GPU-h / 36) beside a four-term table that had been updated to the
    three-episode decision (176 GPU-h), and its prose said "12 stamps x 240 episodes" where the
    production grid is 4 regimes x 10 scenes x 3 episodes = 120.

    This version reads the real thing instead: each family's `save_every` and `preserve_snapshots`
    give the number of stamps that actually survive `retain` and therefore get evaluated, and the
    curve scope comes from the descriptor the way `family.py` resolves it -- `curve_eval_<axis>`
    falling back to `offline_eval_<axis>`, which is why the production curve runs the full ten
    scenes and four regimes at three episodes rather than the runner's shallow probe defaults.

    Cost per episode is measured wall-clock, not derived from training FPS. The old docstring
    argued an eval episode is "at worst as slow as training at that family's FPS", which is wrong
    in the direction that matters: idaac trains at 34.8 fps on gt4.1 but its measured evaluation
    is 25 s/episode, so training-FPS arithmetic understated its curve by an order of magnitude.
    """
    # PROFILE-AWARE, and that is not a detail: `rlvigen`'s base `preserve_snapshots` is 100000 --
    # a DataSphere container-disk decision -- while its v100 profile overrides it to 50000, because
    # the 113 GiB production host has no such limit. Reading the base descriptor here would model a
    # 7-stamp curve for five baselines that in production retain all thirteen, and understate their
    # trajectory cost by half. `production_gates.gate_checkpoint_cadence_matches_fleet` pins the
    # fleet at 12 stamps + endpoint at 50k on this profile.
    per_episode, unmeasured = _seconds_per_episode()
    rows = {}
    for baseline, family in FAMILY_OF.items():
        settings = (_family.resolved_descriptor(family, path=path, profile=profile)
                    .get("production") or {})
        save_every = settings.get("save_every")
        if not save_every:
            continue
        preserve = settings.get("preserve_snapshots")
        written = max(frames // save_every, 0)
        # `retain` keeps the stamps at multiples of `preserve_snapshots`, plus the endpoint; with
        # no cadence every written stamp survives.
        kept = (frames // preserve if preserve else written) + 1
        regimes = settings.get("curve_eval_regimes", settings.get("offline_eval_regimes")) or ""
        scenes = settings.get("curve_eval_scenes", settings.get("offline_eval_scenes")) or []
        episodes = settings.get("curve_eval_episodes", settings.get("offline_eval_episodes")) or 0
        n_regimes = len(regimes.split(",")) if isinstance(regimes, str) and regimes else 1
        n_scenes = len(scenes) if isinstance(scenes, list) else 1
        per_stamp = n_regimes * n_scenes * episodes
        seconds = per_episode.get(baseline, per_episode.get(family, unmeasured))
        hours = kept * per_stamp * seconds / 3600.0
        rows[baseline] = {
            "stamps_written": written + 1, "stamps_evaluated": kept,
            "episodes_per_stamp": per_stamp, "seconds_per_episode": seconds,
            "measured": baseline in per_episode or family in per_episode,
            "hours_per_seed": hours, "hours_all_seeds": hours * seeds,
        }
    total = sum(v["hours_all_seeds"] for v in rows.values())
    return {"rows": rows, "total_hours": total}


def endpoint_eval_hours(frames: int, seeds: int, path: Path | None = None,
                        profile: str | None = "v100") -> dict:
    """Job-hours added by the ENDPOINT grid, which nothing modelled at all.

    [Claude 2026-09-10] `curve_eval_hours` above is correct and, until today, had NO CALLERS -- the
    exact defect its own docstring describes having fixed in its predecessor. So the schedule's
    headline `job_hours` was `frames / fps` and nothing else: TRAINING ONLY. On the one production
    cell measured to completion (idaac 600k) evaluation was **2.04x** the training it followed --
    4.95 h training against 4.60 h curve and 5.52 h endpoint -- so the published campaign understated
    itself by more than half, and `wall_clock_days_at_two_parallel_jobs` with it.

    The endpoint is `offline_eval_regimes x offline_eval_scenes x offline_eval_episodes` episodes,
    run once per entry in `ENDPOINT_EVAL_POLICY_MODES`. That last term is the one
    `launch-card-cell.sh` was also missing on 2026-09-09: it defaults to `native,mode`, so the three
    SAMPLING families (`idaac`, `ppg`, `ibac_sni`) run the whole grid TWICE. Omitting it halves
    their endpoint estimate, which is how a cell came within one minute of losing its delivery.
    """
    per_episode, unmeasured = _seconds_per_episode()
    identity = _load_identity()
    rows = {}
    for baseline, family in FAMILY_OF.items():
        settings = (_family.resolved_descriptor(family, path=path, profile=profile)
                    .get("production") or {})
        regimes = settings.get("offline_eval_regimes") or ""
        scenes = settings.get("offline_eval_scenes") or []
        episodes = settings.get("offline_eval_episodes") or 0
        if not episodes:
            continue
        n_regimes = len(regimes.split(",")) if isinstance(regimes, str) and regimes else 1
        n_scenes = len(scenes) if isinstance(scenes, list) else 1
        passes = 2 if identity.FAMILY_EVAL_POLICY_MODE.get(family) == "sample" else 1
        per_pass = n_regimes * n_scenes * episodes
        seconds = per_episode.get(baseline, per_episode.get(family, unmeasured))
        hours = per_pass * passes * seconds / 3600.0
        rows[baseline] = {
            "episodes_per_pass": per_pass, "policy_mode_passes": passes,
            "seconds_per_episode": seconds,
            "measured": baseline in per_episode or family in per_episode,
            "hours_per_seed": hours, "hours_all_seeds": hours * seeds,
        }
    total = sum(v["hours_all_seeds"] for v in rows.values())
    return {"rows": rows, "total_hours": total}


def _load_identity():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_identity_for_plan", _HERE / "evaluator_identity.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def checkpoint_storage_gb(frames: int, save_every: int, seeds: int) -> dict:
    """What retaining the intermediate grid actually costs, per baseline and in total.

    The answer decides a design question, not just a number. If the weights must come home, a
    3-seed 6e5 run does not fit on this laptop; if they are evaluated where they were produced and
    only the records travel, the same run costs kilobytes. C95 already forces the second option --
    a container-trained checkpoint CANNOT be validly evaluated here -- so retaining the weights
    buys nothing that retaining the records does not, and costs four orders of magnitude more.
    """
    stamps = max(frames // save_every, 0) + 1   # the 50k grid plus the terminal checkpoint
    rows = {}
    for baseline, family in FAMILY_OF.items():
        per_cell_gb = CHECKPOINT_MB[family] * stamps / 1000.0
        rows[baseline] = {"stamps": stamps, "per_cell_gb": per_cell_gb,
                          "all_seeds_gb": per_cell_gb * seeds}
    total = sum(r["all_seeds_gb"] for r in rows.values())
    return {"stamps": stamps, "rows": rows, "total_gb": total}


def resolved_fleet(profile: str) -> tuple[dict, str]:
    """Resolve every family through the launcher's own overlay logic and hash that result."""
    resolved = {
        name: _family.resolved_descriptor(name, profile=profile)
        for name in sorted(_family.load())
    }
    canonical = json.dumps(resolved, sort_keys=True, separators=(",", ":")).encode()
    return resolved, hashlib.sha256(canonical).hexdigest()


def v100_schedule(frames: int, seeds: list[int]) -> dict:
    """Production-host shape without pretending T4 throughput was measured on a V100."""
    resolved, descriptor_hash = resolved_fleet("v100")
    rows = []
    order = RLVIGEN + DMC_GB + ("alda",) + ONPOLICY
    for baseline in order:
        family = _family.family_of(baseline)
        entry = resolved[family]
        settings = entry.get("production", {})
        capacity = settings.get("replay_capacity")
        if baseline in DMC_GB:
            # This implementation allocates `capacity=args.train_steps`; there is no separate
            # option, so its effective capacity is the requested budget on every host.
            capacity = frames
        if baseline in RLVIGEN:
            max_retained = frames + -(-frames // 500)  # one reset entry per full Door horizon
            evicts = capacity is None or int(capacity) < max_retained
        elif baseline in DMC_GB:
            max_retained, evicts = frames, False
        else:
            max_retained, evicts = None, None
        ram, ram_reason = cell_ram_gib(baseline, frames, capacity, entry)
        rows.append({
            "baseline": baseline,
            "family": family,
            "requested_frames": frames,
            "executed_endpoint": _family.expected_endpoint(
                family, frames, profile="v100"),
            "seeds": seeds,
            "runtime_constants": entry.get("constants", {}),
            # [Claude 2026-09-08] `environment` was omitted here while `constants` was
            # printed. The descriptor HASH already covered it -- `resolved_fleet` hashes
            # the whole resolved entry -- so nothing was unbound. But a learning-affecting
            # value that a reader of this schedule cannot see is a value nobody checks:
            # `RLVIGEN_FRAME_STACK=3` is how `ctrl` and `ibac_sni` carry the A40 REVISED-2
            # stack, because their clones take no such CLI flag.
            "runtime_environment": entry.get("environment", {}),
            "replay_capacity": capacity,
            "maximum_retained_transitions": max_retained,
            "evicts_before_endpoint": evicts,
            "save_every_frames": settings.get("save_every"),
            "endpoint_eval_episodes": settings.get("offline_eval_episodes"),
            "curve_eval_episodes": settings.get(
                "curve_eval_episodes", settings.get("offline_eval_episodes")),
            "offline_eval_regimes": settings.get("offline_eval_regimes"),
            "offline_eval_scenes": settings.get("offline_eval_scenes"),
            "cell_ram_gib_model": round(ram, 2),
            "cell_ram_model_basis": ram_reason,
            "v100_completed_frames_per_second": None,
            "throughput_source": "UNMEASURED_ON_V100",
            "t4_completed_frames_per_second_reference": MEASURED_FPS_GT4_1.get(baseline),
            "t4_reference_basis": FPS_BASIS.get(baseline),
        })
    return {
        "_comment": [
            "GENERATED by plan_production.py --host-profile v100; nothing submits from this file.",
            "Runtime settings are resolved by family.py from the explicit v100 profile.",
            "Every V100 throughput is null until measured on that host; T4 rates are references,",
            "not estimates silently relabelled as production measurements.",
        ],
        "host_profile": "v100",
        "resolved_descriptor_sha256": descriptor_hash,
        "host": V100_HOST,
        "frames": frames,
        "seeds": seeds,
        "rows": rows,
        "calendar_status": "BLOCKED_ON_MEASURED_V100_THROUGHPUT",
    }



def cell_ram_gib(baseline: str, frames: int, capacity: int | None,
                  entry: dict | None = None) -> tuple[float, str]:
    """Resident memory one cell reaches at the end of a run, and what sets it.

    [Corrected 2026-09-05.] The on-policy fallback branch read a single static `ENVELOPE` figure
    per baseline regardless of process count -- ibac_sni's 3.10 GiB was measured at `procs=1` and
    stayed 3.10 GiB in this function even once the resolved profile asked for `procs=16`, while
    `family.check_memory`'s SEPARATE `parallel_rollout_memory` model (also in families.json)
    correctly modeled the same 16-worker process tree at 17.91 GiB. Same underlying fact, two
    consumers, one of them stale -- caught by `tests/test_production_schedule_not_stale.py`.
    `entry` (the resolved descriptor already available at every call site in `v100_schedule`) lets
    this function read the SAME `parallel_rollout_memory` model instead of a second hardcoded copy.
    """
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
    if entry is not None:
        host_memory = entry.get("production", {}).get("host_memory_model")
        if host_memory:
            return float(host_memory["cell_ram_gib"]), str(host_memory["basis"])
        parallel = entry.get("production", {}).get("parallel_rollout_memory")
        if parallel:
            procs = int(entry.get("constants", {}).get("procs", 1))
            total = (float(parallel["parent_gib"]) + procs * float(parallel["per_worker_gib"])
                     + float(parallel.get("margin_gib", 0.0)))
            return total, (f"process tree model: parent {parallel['parent_gib']} + "
                            f"{procs}x{parallel['per_worker_gib']} workers + "
                            f"{parallel.get('margin_gib', 0.0)} margin (source: "
                            f"{parallel.get('source_job', 'unrecorded')})")
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
    tier_rank = {"gt4.1": 1, "gt4i.1": 2}
    minimum = MINIMUM_TIER.get(baseline, "gt4.1")
    for name in ("gt4.1", "gt4i.1"):
        if tier_rank[name] < tier_rank[minimum]:
            continue
        tier = TIERS[name]
        if ram <= tier["usable_ram_gib"] and (vram is None or vram <= tier["vram_mib"]):
            row["tier"] = name
            by_ram = int(tier["usable_ram_gib"] // ram)
            by_vram = int(tier["vram_mib"] // vram) if vram else by_ram
            by_cores = max(1, int(tier["cores"] // max(1.0, ENVELOPE.get(baseline, {}).get("cores", 1.0))))
            row["max_cells_per_job"] = max(1, min(by_ram, by_vram, by_cores,
                                                   DECLARED_PACKING_CAP[baseline]))
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
    parser.add_argument("--host-profile", choices=("datasphere", "v100"), default="datasphere",
                        help="resolve runtime settings for this named host; never read ambient "
                             "NATIVE_HOST_PROFILE when generating an artifact")
    parser.add_argument("--frames", type=int, default=600_000)
    parser.add_argument("--rlvigen-capacity", type=int, default=300_000)
    # dmc_gb's buffer is `capacity=args.train_steps` with no flag (train.py:111), so a cap is not
    # reachable without a source change. The default models the world as it is; pass the flag to
    # price what that change would buy.
    parser.add_argument("--dmc-gb-capacity", type=int, default=None)
    parser.add_argument("--seeds", default="101,102,103")
    parser.add_argument("--sync-schedule", action="store_true",
                        help="rewrite production-schedule.json's throughput table from this "
                             "module, which is the source of truth for it")
    args = parser.parse_args()

    if args.host_profile == "v100":
        seeds = [int(item) for item in args.seeds.split(",")]
        payload = json.dumps(v100_schedule(args.frames, seeds), indent=2) + "\n"
        if args.sync_schedule:
            schedule = pathlib.Path(__file__).with_name("production-schedule-v100.json")
            schedule.write_text(payload)
            print(f"synced {schedule.name}: explicit v100 profile, {len(seeds)} seeds")
            return 0
        print(payload, end="")
        return 0

    if args.sync_schedule:
        # [Claude 2026-09-04: the schedule carried its own copy of the FPS table and drifted --
        # drqv2 stayed at 17.53 after re-grounding at 26.05, and five baselines stayed 'estimated'
        # after all five had completed CUDA runs. One number, one home.]
        import json as _json
        schedule = pathlib.Path(__file__).with_name("production-schedule.json")
        data = _json.loads(schedule.read_text())
        data["measured_completed_frames_per_second_gt4_1"] = dict(sorted(MEASURED_FPS_GT4_1.items()))
        data["throughput_basis"] = dict(sorted(FPS_BASIS.items()))
        data["estimated_baselines"] = [b for b, basis in sorted(FPS_BASIS.items())
                                       if basis != "measured"]
        schedule.write_text(_json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        print(f"synced {schedule.name}: {len(MEASURED_FPS_GT4_1)} baselines, "
              f"{len(data['estimated_baselines'])} not directly measured")
        return 0

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
    # [Claude 2026-09-10] TRAINING IS NOT THE CAMPAIGN. `row["job_hours"]` is `frames / fps` and
    # nothing else, so every total derived from it -- including
    # `wall_clock_days_at_two_parallel_jobs`, which is what anyone schedules against -- described
    # only the training half. On the one production cell measured to completion, evaluation was
    # 2.04x the training it followed. `curve_eval_hours` existed and was correct and had no
    # callers; the endpoint grid was not modelled at all.
    _curve = curve_eval_hours(args.frames, len(seeds))
    _endpoint = endpoint_eval_hours(args.frames, len(seeds))
    total_eval_hours = _curve["total_hours"] + _endpoint["total_hours"]
    total_campaign_hours = total_job_hours + total_eval_hours

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
        # Keep these explicit in the generated artifact: the schedule test reads them directly,
        # and omitting them made the documented regeneration command create a file that its own
        # stale-file checks could no longer load.
        "measured_completed_frames_per_second_gt4_1": dict(sorted(MEASURED_FPS_GT4_1.items())),
        "throughput_basis": dict(sorted(FPS_BASIS.items())),
        "estimated_baselines": [b for b, basis in sorted(FPS_BASIS.items())
                               if basis != "measured"],
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
            "job_hours_note": ("TRAINING ONLY -- frames/fps. Kept under its historical name so "
                               "nothing that quotes it changes meaning silently. The campaign is "
                               "campaign_hours below."),
            "curve_eval_hours": round(_curve["total_hours"], 1),
            "endpoint_eval_hours": round(_endpoint["total_hours"], 1),
            "eval_hours": round(total_eval_hours, 1),
            "campaign_hours": round(total_campaign_hours, 1),
            "eval_share_of_campaign": round(total_eval_hours / total_campaign_hours, 3),
            "campaign_days_at_two_parallel_jobs": round(total_campaign_hours / 2 / 24, 1),
            "campaign_days_on_one_card": round(total_campaign_hours / 24, 1),
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
