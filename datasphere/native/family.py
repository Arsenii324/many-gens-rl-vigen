"""Resolve one family descriptor into a command line and a retained artifact set.

[Claude 2026-09-02 03:15 MSK] The native runner used to hard-code RL-ViGen's launcher, its hydra
override syntax, its `snapshot.pt` and its `train.csv`. That is one of seven source families. This
module keeps the runner family-agnostic: it answers three questions -- what argv runs this cell,
which files prove the cell finished, and does this cell need the private overlay asset -- from
`families.json`, so adding a baseline is data plus a test, not another branch in a shell script.

What it deliberately does not do is normalise the metrics. Each family keeps its own curve files,
in its own format, under its own names. The only normalised name is the retained checkpoint, so a
later offline evaluator has one path to open per cell; `retained.json` records where it came from.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
DESCRIPTORS = HERE / "families.json"


def fail(message: str) -> None:
    raise ValueError(message)


def load(path: Path | None = None) -> dict:
    descriptors = json.loads((path or DESCRIPTORS).read_text())
    return {name: value for name, value in descriptors.items() if not name.startswith("_")}


def descriptor(family: str, path: Path | None = None) -> dict:
    families = load(path)
    if family not in families:
        fail(f"unknown family: {family} (known: {', '.join(sorted(families))})")
    return families[family]


def host_profile(path: Path | None = None, selected: str | None = None) -> str:
    """Resolve the named machine profile, refusing a typo before a training command is built.

    The descriptor has deliberately separate DataSphere-safe and V100 production values.  Reading
    the selector from the environment lets the same hermetic runner serve both, while retaining a
    safe default for every existing probe configuration.
    """
    raw = json.loads((path or DESCRIPTORS).read_text())
    selected = selected or os.environ.get("NATIVE_HOST_PROFILE", "datasphere")
    known = raw.get("_host_profiles", {})
    if selected not in known:
        fail(f"unknown host profile {selected!r}; known: {', '.join(sorted(known))}")
    return selected


def resolved_descriptor(family: str, path: Path | None = None,
                        profile: str | None = None) -> dict:
    """Apply the selected host's declared overrides without mutating the source descriptor."""
    entry = descriptor(family, path)
    override = entry.get("host_profiles", {}).get(host_profile(path, profile), {})
    unknown = set(override) - {
        "constants", "production", "environment",
        "constants_reason", "production_reason", "environment_reason",
    }
    if unknown:
        fail(f"{family}: unsupported host-profile override section(s): {sorted(unknown)}")
    resolved = dict(entry)
    for section in ("constants", "production", "environment"):
        if section in override:
            resolved[section] = {**entry.get(section, {}), **override[section]}
    return resolved


def family_of(baseline: str, path: Path | None = None) -> str:
    for name, value in load(path).items():
        if baseline in value["baselines"]:
            return name
    fail(f"no family declares baseline: {baseline}")
    raise AssertionError  # unreachable; fail raises


def provenance_for(baseline: str, path: Path | None = None) -> dict[str, str]:
    """Return the descriptor's disclosure labels for one baseline.

    These labels identify the source target and the operational variant. They are deliberately
    not inferred from a method name or from a result, and they are not a faithfulness score.
    Keeping the lookup beside the family descriptor makes every record writer use the same source
    of truth.
    """
    family = family_of(baseline, path)
    labels = descriptor(family, path).get("provenance", {}).get(baseline)
    if not isinstance(labels, dict) or set(labels) != {"source_target", "source_variant"}:
        fail(f"{family}: missing or malformed provenance labels for {baseline}")
    if not all(isinstance(value, str) and value.strip() for value in labels.values()):
        fail(f"{family}: empty provenance label for {baseline}")
    return dict(labels)


def all_provenance(path: Path | None = None) -> dict[str, dict[str, str]]:
    """Return all declared baseline disclosure labels, validating completeness."""
    out = {}
    for family in load(path):
        for baseline in descriptor(family, path).get("baselines", []):
            out[baseline] = provenance_for(baseline, path)
    return out


def substitutions(**fields: str) -> dict:
    return {key: str(value) for key, value in fields.items()}


def render(template: str, fields: dict) -> str:
    try:
        return template.format(**fields)
    except KeyError as error:
        fail(f"template {template!r} needs an unknown field: {error}")
        raise AssertionError


def full_fields(family: str, fields: dict, path: Path | None = None) -> dict:
    """Descriptor constants plus the derived `{endpoint}`, resolved once for every consumer.

    `{endpoint}` is the executed frame count this family's own rule predicts. A launcher that has
    to print the completion marker itself, and a checkpoint whose filename carries the step, both
    need it; deriving it in one place is what stops them from disagreeing with the code that
    verifies the marker.
    """
    entry = resolved_descriptor(family, path)
    merged = with_constants(entry, fields)
    if "frames" in merged and "endpoint" not in merged:
        merged["endpoint"] = str(expected_endpoint(family, int(merged["frames"]), path))
    # [Claude 2026-09-02 11:35 MSK: save_every defaults to the whole budget, which means "save once,
    # at the end". A production job sets it to the checkpoint cadence it wants; families that write
    # a step-stamped file then leave a budget curve behind at no training cost.]
    merged.setdefault("save_every", merged.get("frames", ""))
    return merged


def with_constants(entry: dict, fields: dict) -> dict:
    """Descriptor-level constants, so one value can appear in several templates.

    IDAAC's rollout quantum is `num_processes * num_steps`; those numbers appear in the launcher
    positional, in the argparse options and in the endpoint rule. Declaring them once is what stops
    the endpoint arithmetic from silently disagreeing with the command that was actually run.
    """
    return {**entry.get("constants", {}), **fields}


def command(family: str, fields: dict, path: Path | None = None) -> list[str]:
    entry = resolved_descriptor(family, path)
    fields = full_fields(family, fields, path)
    argv = [entry["launcher"]]
    argv += [render(item, fields) for item in entry["positional"]]
    argv += [render(item, fields) for item in entry["options"]]
    return argv



#: Families whose stored `min_frames` is "one full rollout" and therefore SCALES with a
#: process-count constant the profile can change. Mapping to the two constants whose product is
#: that rollout. Every other family's `min_frames` is about warmup (RL-ViGen's `num_seed_frames`)
#: or a fixed segment size, neither of which moves with the host profile.
ROLLOUT_QUANTUM_CONSTANTS = {
    "idaac": ("num_processes", "num_steps"),
    "ibac_sni": ("procs", "frames_per_proc"),
}


def check_budget(cells: str, frames: int, path: Path | None = None,
                  profile: str | None = None) -> None:
    """Refuse a budget too small to produce a training curve, before anything is paid for.

    Every RL-ViGen config sets `num_seed_frames: 4000` and the training log gets its first row
    only after the seed phase. A cell budgeted below that trains nothing, writes no curve, and
    fails `retain()` -- but only after the bootstrap, the run and a full evaluation have already
    happened. Found by a local rehearsal at 3,000 frames that did exactly this.

    [Corrected 2026-09-05, external review 14 section 13.] `min_frames` for idaac and ibac_sni is
    "one full rollout" and was stored as a STATIC number computed from the BASE process count.
    A host profile that changes `num_processes` changes the rollout quantum with it, so a floor
    stored as a static number goes stale the moment a profile moves the geometry: a canary could
    satisfy the stale check while completing ZERO rollouts
    (`num_updates = frames // num_steps // num_processes == 0`), training nothing and proving
    nothing about the profile it claims to validate. `profile` now re-derives the floor from
    ROLLOUT_QUANTUM_CONSTANTS against the profile's RESOLVED constants for the two affected
    families, instead of trusting the stored number.

    [Claude 2026-09-08] This paragraph used to cite idaac's V100 override raising `num_processes`
    4 -> 16 for a 4096-frame rollout. BOTH halves are now stale and are removed rather than
    updated: `families.json` REMOVED that override under IDAAC-C2 (`num_processes` is 1 on every
    profile), and the 4096/1024 figures came from a configuration where `num_steps` was 256, not
    today's 2048. Verified by execution, not by reading -- `expected-endpoint --baseline idaac
    --frames 10000` returns 8192 under `datasphere` and under `v100` alike, so the two profiles
    now share one geometry. The hazard the paragraph describes is real and general; the example
    was specific and no longer true, which is the worse of the two things to leave in place.
    """
    import os
    import re as _re

    # The RL-ViGen floor IS num_seed_frames, and that is overridable -- a rehearsal routinely
    # lowers it to train inside a few thousand frames. A gate that ignored the override would
    # refuse exactly the runs it exists to make cheap, so derive the floor from the effective
    # value and fall back to the declared default only when nothing overrides it.
    override = _re.search(r"num_seed_frames=(\d+)", os.environ.get("NATIVE_EXTRA_OVERRIDES", ""))
    try:
        resolved = sorted(families_of_cells(cells, path))
    except ValueError:
        # An unknown baseline is a real error, and it is NOT this gate's error to report. The
        # runner already fails on it with a message pointing at the cell list, and preempting that
        # here replaced seven specific diagnostics with "no family declares baseline: alpha".
        # A gate added to save money should not take over the reporting of unrelated failures.
        return
    for family in resolved:
        settings = production(family, path, profile)
        floor = settings.get("min_frames")
        reason = settings.get("min_frames_reason", "no reason recorded")
        quantum_keys = ROLLOUT_QUANTUM_CONSTANTS.get(family)
        if quantum_keys:
            entry = resolved_descriptor(family, path, profile)
            constants = entry.get("constants", {})
            a_key, b_key = quantum_keys
            if a_key in constants and b_key in constants:
                rollout = int(constants[a_key]) * int(constants[b_key])
                if floor is None or rollout != floor:
                    floor = rollout
                    reason = (f"one full rollout at this profile is {a_key}={constants[a_key]} x "
                              f"{b_key}={constants[b_key]} = {rollout} frames; a smaller budget "
                              "completes zero rollouts and trains nothing")
        if family == "rlvigen" and override:
            floor = int(override.group(1)) + 1
            reason = (f"num_seed_frames is overridden to {override.group(1)}, so the floor is that "
                      "plus one rather than the configured 4000")
        if floor is not None and frames < floor:
            raise SystemExit(f"{family}: {frames} frames is below its floor of {floor} -- {reason}")


def production(family: str, path: Path | None = None, profile: str | None = None) -> dict:
    """The resolved production configuration for a family, or {} if it declares none."""
    return resolved_descriptor(family, path, profile).get("production", {})


def admission_tier_for(tier: str) -> str:
    """The tier to run this module's own admission checks against, for a `cloud-instance-type`
    this module has no RAM/vCPU model for.

    [Claude 2026-09-06] The ONE home for the g1.1 -> gt4i.1 substitution -- job.sh's real submit
    path and scripts/audit_submission_configs.py's own simulation of it each used to carry this
    mapping independently, and the audit's copy was missing, so it reported "unknown job tier:
    g1.1" and FAILED two configs that had already submitted and run successfully for real
    (bt18a8fjl3qrp5jv50g6, bt1vsfov1mmg9shjp898). Exactly the "same fact computed twice" class
    this project keeps finding elsewhere (Q12's DOOR_RANDOM_FLOOR, CORRECTIONS #88's AppleDouble
    hash) -- fixed here by giving both callers one function to call instead of one to mirror.

    g1.1 is one V100 with 8 vCPU and 48-96 GiB RAM. This module's own tier table only has the
    8-vCPU/32-GiB gt4i.1 shape, used as a conservative admission floor. This does NOT select
    NATIVE_HOST_PROFILE=v100, which names the separate, larger owner host -- it only lets a G1.1
    DataSphere job clear the same family-fit checks a gt4i.1 job would.
    """
    return "gt4i.1" if tier == "g1.1" else tier


def check_tier(cells: str, tier: str, path: Path | None = None) -> None:
    """Reject a job tier below a family's budget-independent minimum."""
    rank = {"gt4.1": 1, "gt4i.1": 2}
    if tier not in rank:
        fail(f"unknown job tier: {tier}")
    for family in families_of_cells(cells, path):
        entry = resolved_descriptor(family, path)
        required = entry.get("minimum_tier", "gt4.1")
        if rank[tier] < rank[required]:
            fail(f"{family} requires {required}, job uses {tier}")


def check_memory(cells: str, tier: str, path: Path | None = None,
                 allow_unmeasured: bool = False, frames: int | None = None) -> None:
    """Reject a tier that cannot hold its measured working set plus safety margin.

    Most families have one fixed peak.  IBAC-SNI also has an explicitly measured process-tree
    model: spawned MuJoCo/EGL workers do not share the parent's address space, so a one-process
    peak cannot certify a command that asks for sixteen.  The runner's extra overrides are part of
    the effective command and therefore part of this preflight, rather than a loophole around it.
    """
    # [Claude 2026-09-07, external review 21 #4] `v100` was absent, so the production host had no
    # memory preflight of any kind -- `check_memory` could only certify DataSphere tiers, and
    # `run_probe.sh` never called it at all. 100.0 of the host's 113 GiB available
    # (notes/remote-infra.txt, measured 2026-09-05), reserving 13 GiB for the OS, page cache and
    # the other user whose process notes/remote-infra.txt records on GPU 0. That reserve is a
    # judgement, not a measurement, and is deliberately generous: the failure it prevents is an
    # OOM-kill hours into a 600k cell.
    usable = {"gt4.1": 14.5, "gt4i.1": 27.0, "v100": 100.0}
    if tier not in usable:
        fail(f"unknown job tier: {tier}")
    # PROFILE-AWARE. Reading the base descriptor here would certify ctrl's v100 cell against its
    # 16-environment 13.57 GiB peak while the v100 profile restores 64 environments, whose own
    # descriptor estimates ~54 GiB. Same class of error as validating a cadence from the base
    # profile: the number is real, it just belongs to a configuration that is not the one running.
    profile = os.environ.get("NATIVE_HOST_PROFILE") or None
    unmeasured: list[str] = []
    estimated: list[str] = []
    # [Claude 2026-09-08] Per-family requirements, kept so the CONCURRENT case can be summed. The
    # loop below checks each family against the tier ALONE, which is correct for the default
    # sequential execution -- run_cell_list runs cells one at a time unless NATIVE_CONCURRENT=1 --
    # and silently wrong when they run together, because then the peaks coexist.
    per_family_required: dict[str, float] = {}
    for family in families_of_cells(cells, path):
        entry = resolved_descriptor(family, path, profile=profile)
        settings = entry.get("production", {})
        peak = settings.get("fixed_peak_gib")
        # A host profile may carry its own model for a configuration whose peak was never measured
        # at that geometry. It is used, and it is recorded as an ESTIMATE, never pooled with a
        # measurement -- `basis` says which it is.
        model = settings.get("host_memory_model") or {}
        if model.get("cell_ram_gib") is not None:
            peak = float(model["cell_ram_gib"])
            if "extrapolat" in str(model.get("basis", "")).lower() or "estimate" in str(
                    model.get("basis", "")).lower():
                estimated.append(family)
        margin = settings.get("memory_margin_gib", 0.0)
        if peak is None:
            # This used to `continue`, so a family with no measured peak fell through to the
            # caller printing "memory ok" -- an unmeasured family certified as fitting. ctrl was
            # certified for gt4.1 that way and SIGKILLed at 11.07 GiB RSS (bt1lhobnsq5lq4766np6).
            # An absent measurement is not a passing one.
            unmeasured.append(family)
            continue
        required = float(peak) + float(margin) + _replay_gib(family, settings, frames)
        parallel = settings.get("parallel_rollout_memory")
        if parallel:
            # `--procs=16` is how the launcher receives this field; accept the whitespace form as
            # well so a hand-written diagnostic config cannot bypass the check by changing syntax.
            import re
            override = re.search(r"(?:^|\s)--procs(?:=|\s+)(\d+)(?:\s|$)",
                                 os.environ.get("NATIVE_EXTRA_OVERRIDES", ""))
            procs = int(override.group(1)) if override else int(entry.get("constants", {}).get("procs", 1))
            tree_required = (float(parallel["parent_gib"]) +
                             procs * float(parallel["per_worker_gib"]) +
                             float(parallel.get("margin_gib", 0.0)))
            if tree_required > usable[tier]:
                fail(f"{family}: parallel rollout memory for procs={procs} is at least "
                     f"{tree_required:.2f} GiB (parent + workers + margin), but {tier} has "
                     f"{usable[tier]:.1f} GiB usable")
            required = max(required, tree_required)
        if required > usable[tier]:
            fail(f"{family}: measured fixed peak plus margin is {required:.2f} GiB, "
                 f"but {tier} has {usable[tier]:.1f} GiB usable")
        per_family_required[family] = required
    # [Claude 2026-09-08] CONCURRENCY. Everything above asks "does ONE cell of this family fit",
    # which is the right question when `run_cell_list` runs cells one after another -- and it does,
    # unless NATIVE_CONCURRENT=1, in which case it dispatches every cell with `&` and waits. Then
    # the peaks COEXIST and nothing here added them up.
    #
    # The gap was not hypothetical and not caught by the guard below: that one refuses to pack when
    # a figure is ESTIMATED, which catches ctrl's extrapolated 54.28 GiB. Two `rlvigen` cells have
    # MEASURED figures, so `NATIVE_CONCURRENT=1 CELLS=drqv2:101,drqv2:102` passed every check at
    # ~42 GiB each while actually needing ~84 GiB -- on a 125 GB host shared with about twenty
    # other people, where exhausting RAM evicts their processes, not ours.
    #
    # Read from the environment rather than taken as an argument because that is how the runner
    # already passes it, and a check that has to be told about concurrency separately is a check
    # that will be called without it.
    cell_specs = [c.strip() for c in cells.split(",") if c.strip()]
    if os.environ.get("NATIVE_CONCURRENT") == "1" and len(cell_specs) > 1:
        total = 0.0
        breakdown = []
        for spec in cell_specs:
            fam = families_of_cells(spec, path)[0]
            need = per_family_required.get(fam)
            if need is None:
                continue
            total += need
            breakdown.append(f"{spec} ({fam}) {need:.2f}")
        if total > usable[tier]:
            fail(f"refusing to run {len(cell_specs)} cells CONCURRENTLY: their peaks coexist and "
                 f"sum to {total:.2f} GiB, but {tier} has {usable[tier]:.1f} GiB usable. "
                 f"Breakdown: {'; '.join(breakdown)}. Run them sequentially (unset "
                 f"NATIVE_CONCURRENT), or pack fewer.")

    # Packing on an estimate is the specific thing external review 21 refused to accept, and it is
    # right: two cells sharing a host on the strength of a linear extrapolation is how a 600k run
    # dies at hour six. One cell against a generous reserve is a different risk from two.
    if estimated and len(cells.split(",")) > 1:
        fail(f"refusing to pack {len(cells.split(','))} cells: "
             f"{', '.join(sorted(set(estimated)))} has an ESTIMATED memory figure, not a measured "
             "one. Run the bounded memory measurement first (cfg-ctrl-v100-memory-v130.yaml is "
             "that shape), then pack against the result")
    if unmeasured and not allow_unmeasured:
        fail("no measured memory peak for " + ", ".join(sorted(unmeasured))
             + f"; cannot certify {tier}. Record `fixed_peak_gib` from a completed run, or pass "
               "--allow-unmeasured to accept the risk explicitly")



def _replay_gib(family: str, settings: dict, frames: int | None = None) -> float:
    """Replay memory a cell holds, from the planner's model -- ONE memory truth, not two.

    [Claude 2026-09-07, external review 21 #12] `check_memory` sized a cell as
    `fixed_peak_gib + margin`, and for the two replay-holding families that peak excludes the
    replay entirely: rlvigen's 3.33 GiB is the SVEA process measured at a 10k probe, while the
    v100 profile restores a 620,000-transition buffer -- 36.7 GiB of worker-resident replay that
    `plan_production` has always modelled and this check never saw. The schedule therefore said
    38.78 GiB for a drqv2 cell while this function would have certified 5.33. Review 21 called this
    "one memory truth, not two" and that is exactly right; the planner's constants are imported
    here rather than restated, so there is still only one.

    Budget-dependent, so it reads FRAMES the same way the runner does: rlvigen's buffer grows to
    its cap or to the budget, whichever is smaller, and dmc_gb allocates `train_steps` up front at
    construction with no cap available.

    The growth term is not a guess. `plan_production`'s endurance-job note records tree RSS moving
    10.6 -> 15.8 GiB monotonically over 100k frames, and this model predicts 5.91 GiB of growth for
    that interval against the 5.2 GiB observed -- the right size, slightly conservative.

    TWO THINGS THIS MODEL DOES NOT COVER, stated rather than implied:

    * The floor comes from a 10k cell. A transient that first appears later -- the allocator's
      high-water mark after a 50k checkpoint serialisation, say -- is not in it. That is what
      `memory_margin_gib` is for, and 2.0 GiB is a judgement, not a measurement of such a
      transient.
    * GPU memory is not checked here at all; this is host RAM. `plan_production.ENVELOPE` carries
      per-baseline `vram_mib` (sgqn's 7142 is the largest) against a 32 GiB V100, so nothing is
      close to that ceiling solo -- but a packing decision that starts from this function is
      reasoning about the wrong resource if VRAM ever becomes the binding one.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_plan_production_for_family", Path(__file__).resolve().with_name("plan_production.py"))
    plan = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plan)

    # The CALLER's budget when it has one -- `audit_submission_configs` audits 10k probe configs
    # and must not have a 600k production replay charged against them. FRAMES from the environment
    # is the runner's own path; the default is the production budget, the conservative direction.
    if frames is None:
        frames = int(os.environ.get("FRAMES", 600_000) or 600_000)
    # The measured peak is not replay-free: the cell it came from already held whatever replay its
    # own budget had produced, so charging the full buffer on top double-counts that part. The
    # correction needs the measurement's budget, and `fixed_peak_measured_at_frames` is where a
    # descriptor declares it. rlvigen's does NOT: `memory_note` names job bt1anj1cm0ni7p20ted3 but
    # not its frame count, and no config or retained record for that job survives in this tree. So
    # nothing is subtracted there -- an assumed 10k would be invented provenance for the sake of
    # 0.59 GiB, and the error runs in the safe direction.
    measured_at = settings.get("fixed_peak_measured_at_frames") or 0
    if family == "rlvigen":
        capacity = settings.get("replay_capacity")
        retained = min(int(capacity), frames) if capacity else frames
        already = min(int(capacity), measured_at) if capacity else measured_at
        return max(retained - already, 0) * plan.BYTES_PER_TRANSITION / plan.GIB
    if family == "dmc_gb":
        # utils.ReplayBuffer takes capacity=args.train_steps and prefill_memory touches every slot
        # at construction, so the BUDGET sets the resident size and no cap is reachable.
        return max(frames - measured_at, 0) * plan.DMC_GB_BYTES_PER_FRAME / plan.GIB
    return 0.0


#: The Places365 train corpus, charged to the three overlay baselines that actually open it.
#:
#: [Claude 2026-09-09] The 45.0 that stood here asked to be replaced "with the real number at the
#: first host provisioning", and it conflated the project's TWO consumption paths.
#:
#:   * **Archive path.** `run_probe.sh` untars `places365standard_easyformat.tar` into the work
#:     directory, so the tarball and the expanded tree are resident together: ~21 GiB (DMC-GB's own
#:     README figure) + the expansion. That is where 45.0 came from and it remains right for it.
#:   * **Pre-extracted path.** With `NATIVE_PLACES365_DIR` set, `run_probe.sh` prints
#:     `NATIVE_PLACES365_PREEXTRACTED ... (no copy, no extraction this job)` and mounts the corpus
#:     read-only. **No archive, no second copy.**
#:
#: MEASURED on the only corpus this project has (`data/places365_standard`, 2026-09-09):
#: **train 26.46 GiB across 1,803,461 files**, whole tree 27.05 GiB, and no archive exists at all --
#: so the pre-extracted path is the one we can actually take, and charging 45.0 for it over-books
#: ~19 GiB per overlay cell. On a host with 283 GiB free that is the difference between fitting a
#: second cell and refusing it.
PLACES365_TRAIN_EXTRACTED_GIB = 26.5     # measured
PLACES365_TRAIN_ARCHIVE_GIB = 21.0       # DMC-GB README, places365standard_easyformat.tar


def places365_train_gib() -> float:
    """Cost of the ARCHIVE path: the tarball and its expansion, resident together.

    Deliberately NOT branching on `NATIVE_PLACES365_DIR`. The caller below already decides that, and
    decides it better than a size would: a mounted read-only corpus costs the job **nothing**, not
    26.5 GiB, because it is on the disk whether we run or not. Two places keying on one variable is
    how a model drifts from the runtime it is meant to predict -- and the first version of this
    function did exactly that before the existing check was read.
    """
    return PLACES365_TRAIN_EXTRACTED_GIB + PLACES365_TRAIN_ARCHIVE_GIB


#: The archive path's total, kept under its old name so existing callers and tests resolve.
#: Was a flat 45.0 estimate; now 47.5 = a measured 26.5 plus DMC-GB's cited ~21.
PLACES365_TRAIN_GIB = PLACES365_TRAIN_EXTRACTED_GIB + PLACES365_TRAIN_ARCHIVE_GIB
PLACES365_BASELINES = ("svea", "sgqn", "soda")


def disk_requirement_gib(cells: str, frames: int, path: Path | None = None,
                         profile: str | None = None) -> dict:
    """Host disk one job of these cells needs, derived per family rather than assumed.

    [Claude 2026-09-07] `run_on_production_host.sh` refused a production cell below a single
    60 GB constant, which is right for an off-policy cell and roughly thirty times too strict for
    an on-policy one -- `idaac` holds no replay and retains 0.06 GiB of checkpoints. A constant
    that is wrong for half the fleet gets overridden as a matter of routine, and an override that
    is routine is not a guard.

    Three terms, each from a measurement this project already holds:
      * replay episode files, from the same model check_memory uses;
      * retained checkpoints, stamps x plan_production.CHECKPOINT_MB;
      * the result archive, which holds a compressed copy of those same checkpoints -- counted at
        full size rather than discounted, because compressing already-compressed tensors saves
        little and the failure this guards is running out of room while writing it.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_plan_production_for_disk", Path(__file__).resolve().with_name("plan_production.py"))
    plan = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plan)

    rows = {}
    total = 0.0
    for cell in cells.split(","):
        cell = cell.strip()
        if not cell:
            continue
        baseline = cell.split(":")[0]
        family = family_of(baseline, path) if "family_of" in globals() else None
        family = family or families_of_cells(cell, path)[0]
        settings = (resolved_descriptor(family, path, profile=profile).get("production") or {})
        # [Claude 2026-09-08] THIS TERM IS THE HOST-RAM MODEL, REUSED AS IF IT WERE DISK, AND IT
        # IS WRONG FOR BOTH REPLAY FAMILIES. It is left in place because it errs HIGH and the
        # honest replacement is a measurement nobody has taken, not a smaller number reasoned out
        # from source. Read before trusting it:
        #
        #   * `dmc_gb` (rad, soda) holds replay ENTIRELY IN RAM -- `runnable/dmc_gb/src/utils.py`
        #     line 107, a plain Python list with `prefill_memory` preallocating `capacity` slots.
        #     It writes NOTHING to disk. The 16.76 GiB charged here is real memory and zero bytes
        #     of storage; `check_memory` charges it again, correctly, as RAM.
        #   * `rlvigen` (drqv2, svea, sgqn, curl, drq) is disk-backed, but disk is a TRANSPORT, not
        #     a store. `RL-ViGen-upstream/replay_buffer.py` writes one `savez_compressed` .npz per
        #     episode, and the DataLoader workers DELETE each file as they load it -- line 116,
        #     `if not self._save_snapshot: eps_fn.unlink(missing_ok=True)`, with line 94 hardcoding
        #     `self._save_snapshot = False` and discarding the constructor argument entirely. What
        #     sits on disk is the window between the trainer writing and a worker fetching
        #     (`fetch_every=1000` samples), not the 620,000-transition buffer.
        #
        # The same line 116 is why an interrupted off-policy cell cannot resume even in principle:
        # the episodes are not merely unloaded, they are gone. That is the mechanism behind
        # `ai-recommendation-22`, which had recorded the symptom without the cause.
        #
        # DO NOT lower this to the true figure from reading alone. Measure `du -sh` on a running
        # cell's `buffer/` directory first; the guard protects a filesystem that is 99% full and
        # shared with about twenty other people, and over-refusing is the survivable error.
        replay = _replay_gib(family, settings, frames=frames)
        save_every = settings.get("save_every")
        preserve = settings.get("preserve_snapshots")
        stamps = ((frames // preserve) if preserve else (frames // save_every if save_every else 0)) + 1
        checkpoints = stamps * plan.CHECKPOINT_MB.get(family, 0.0) / 1024.0
        # THREE copies coexist at peak, not two: the originals the trainer wrote under {run_dir},
        # the set `retain` COPIES (shutil.copy2, not move) into the cell output, and the compressed
        # copy inside result.tgz. The archive is written while both others are still on disk.
        # [Claude 2026-09-08, A55 -- external review 27 sec.4] The Places365 corpus was missing
        # from this model entirely, so a host could pass this preflight and then run out of space
        # during extraction. Production copies the ~21 GiB compressed archive onto the host AND
        # expands the ~1.8M-image train tree beside the normal RL state, and both live on the work
        # filesystem this number is checked against.
        #
        # `PLACES365_TRAIN_GIB` is the compressed archive plus the expanded tree; it is a stated
        # estimate from the published asset size, NOT a measurement, and the first real
        # provisioning on the host should replace it with one. An estimate that is present and
        # labelled is worth more than a term that is absent.
        #
        # [Claude 2026-09-08] This comment used to read "Charged per CELL because each cell
        # extracts into its own work root", and that is FALSE. `provide_places365` sits at TOP
        # LEVEL in run_probe.sh (line 1464, outside run_cell_list), runs ONCE per job, and
        # extracts into `$work/places365-val` and `$work/places365-root` -- both under the shared
        # work root, neither under `runs/<cell>`. Every cell in the job reads the same tree.
        #
        # The row below still reports what this cell needs STANDALONE, which is the useful number
        # when planning one cell. The job total subtracts the duplicates afterwards, so a 3-seed
        # svea job is charged 45 GiB for the corpus rather than 135. The old arithmetic erred
        # conservatively -- it refused jobs that would have fitted -- but on a filesystem with
        # 325 GB free and 99% used, a phantom 90 GiB is the difference between "run it" and
        # "cannot run it", and a guard that refuses valid work gets overridden as a matter of
        # routine. A routinely-overridden guard is not a guard.
        # [Claude 2026-09-08] A pre-extracted corpus mounted READ-ONLY costs this job nothing: it
        # is neither copied into the staging directory nor expanded into the work root, and it is
        # already on the disk whether we run or not. Charging 45 GiB for it would make check_disk
        # refuse jobs that need none of it -- and a guard that refuses valid work is one that gets
        # overridden as a matter of routine.
        #
        # Read from the environment, the same variable run_on_production_host.sh sets when it
        # mounts one, so the model cannot disagree with the runtime about whether the copy happens.
        places_mounted = bool(os.environ.get("NATIVE_PLACES365_DIR"))
        places = 0.0 if places_mounted else (
            places365_train_gib() if baseline in PLACES365_BASELINES else 0.0)
        cell_total = replay + 3 * checkpoints + places
        rows[cell] = {"family": family, "replay_gib": round(replay, 2),
                      "checkpoints_written_gib": round(checkpoints, 2),
                      "checkpoints_retained_copy_gib": round(checkpoints, 2),
                      "archive_gib": round(checkpoints, 2),
                      "places365_gib": round(places, 2), "total_gib": round(cell_total, 2)}
        total += cell_total
    # One shared extraction, charged once. See the note above the `places` term.
    overlay_cells = sum(1 for row in rows.values() if row["places365_gib"] > 0)
    duplicated = places365_train_gib() * max(0, overlay_cells - 1)
    total -= duplicated
    # [Claude 2026-09-08] MEASURED, replacing a 5.0 GiB judgement that was under by about 2x.
    # `margin` is the only term covering everything that is not replay, checkpoints or Places365,
    # and all of it lands on the same /dev/sda2 that check_disk reads -- the container's writable
    # layer included, since /var/lib/docker has no separate mount on cds2.
    #
    # Measured on the host, in the pinned image, installing requirements-native.txt:
    #
    #     site-packages           5.8 GB   nvidia 2.8G, torch 1.6G, triton 420M, llvmlite 129M,
    #                                      scipy 97M, opencv 90M+79M, imageio_ffmpeg 71M
    #     RL-ViGen extracted      0.9 GB   plus 0.23 GB for the archive beside it
    #     apt (python3, pip, git) ~0.3 GB
    #     payload                 0.0 GB   249 KB
    #     ----------------------------------
    #     steady                  ~7.3 GB
    #
    # pip's own cache added a further 3.0 GB, which is why run_probe.sh now passes --no-cache-dir:
    # the cache buys nothing in a layer that `docker run --rm` discards, and it was 3 GB of peak on
    # a filesystem at 99%. 8.0 keeps roughly 10% over the measured steady figure. This is a
    # MEASUREMENT of one requirement set in one image; a family whose extra pip set is large (ctrl
    # pulls its own JAX/CUDA stack) is not covered by it, and check_disk's refusal is what stands
    # between that and a full shared disk.
    margin = 8.0   # measured: site-packages 5.8 + RL-ViGen 1.1 + apt ~0.3, over-provisioned ~10%
    return {"cells": rows,
            # Per-cell rows report STANDALONE need; these two say how the job total differs.
            "places365_charged_once_gib": round(PLACES365_TRAIN_GIB if overlay_cells else 0.0, 2),
            "places365_duplicates_removed_gib": round(duplicated, 2),
            "margin_gib": margin, "required_gib": round(total + margin, 2)}


def production_env(cells: str, path: Path | None = None) -> dict:
    """Production settings for these cells, as environment the runner can apply.

    families.json is where the production defaults were argued and recorded; this is what makes
    them the ones a job actually runs. Retyping them into a job config is how a schedule and its
    justification drift apart, and the drift is invisible because both look deliberate.

    A cell list spanning families is refused rather than merged: the settings differ in kind, not
    just in value -- `eval_every` is frames for RL-ViGen, environment steps for dmc_gb and alda,
    and meaningless for three families that run no periodic evaluation at all.
    """
    families = sorted(families_of_cells(cells, path))
    if len(families) != 1:
        raise SystemExit(
            f"production settings are per family and these cells span {families}; "
            "submit one family per job, as production-schedule.json assumes")
    family = families[0]
    entry = resolved_descriptor(family, path)
    settings = production(family, path)
    if not settings:
        raise SystemExit(f"{family} declares no production block in families.json")

    out: dict[str, str] = {}
    has_eval_option = any("{eval_every}" in str(option) for option in entry.get("options", []))
    if settings.get("eval_every") is None and has_eval_option:
        # The training loops' online evaluators consume the same global NumPy stream that places
        # Door. Production measurements come from the offline grid, so disable those evaluators
        # explicitly rather than allowing the runner's numeric fallback to turn them back on.
        out["NATIVE_DISABLE_ONLINE_EVAL"] = "1"
        # [Claude 2026-09-07, external review 21 P0] The spelling matters, not just the intent.
        # 2147483647 was not a disable: `step % 2147483647 == 0` is TRUE at step 0, so every one
        # of these eight baselines ran an unrequested initial evaluation under a manifest saying
        # online evaluation was off -- and advanced Door's placement stream by a different amount
        # per family. RL-ViGen's own `utils.Every` returns False for a None cadence, so it is
        # disabled through upstream's own path; the other two guard their call sites explicitly.
        out["NATIVE_ONLINE_EVAL_DISABLED_SPELLING"] = str(
            settings.get("online_eval_disabled_spelling", "2147483647"))
    if settings.get("online_eval_rng_isolated") is True:
        out["NATIVE_ISOLATE_ONLINE_EVAL"] = "1"
    # A production cell has two measured products: one reportable endpoint grid and a shallower
    # trajectory grid.  The runner deliberately leaves both opt-in for cheap probes, so this is
    # where production explicitly enables them.  The shared offline fields are the full endpoint
    # specification; a family may override only the curve depth (currently three episodes) while
    # retaining the same certified regimes and scenes.
    out["ENDPOINT_EVAL"] = "1"
    out["CURVE_EVAL"] = "1"
    # [Claude 2026-09-07, DECISION-SHEET A25 addendum] A second endpoint pass at the deterministic
    # action, for the four families whose native reporting path SAMPLES. Their native pass stays the
    # headline; the `mode` pass is what makes a cross-group contrast comparable, since E[return |
    # a = argmax pi] and E[return | a ~ pi] are different estimands and two of A25's three fixed
    # cross-group pairs straddle that split.
    #
    # Only the sampling families. Asking a family that already takes the mode for a second `mode`
    # pass would re-run an identical 800-episode grid at full price for an identical answer.
    #
    # [Claude 2026-09-08] This comment said FOUR and the cost said "~29 GPU-h". Both are stale, and
    # the code below is not: it derives the set from FAMILY_EVAL_POLICY_MODE, so when external
    # review 24 moved `ctrl` from `sample` to `mode` the set silently became three -- idaac, ppg,
    # ibac_sni -- while the prose kept saying four. That is the same defect shape as
    # audit_job_budgets' BOOTSTRAP_SECONDS (docstring 700, code 200), and the prose number is the
    # one that gets quoted: `notes/SAME-AXES-VERDICT.md` carries it into an owner ruling.
    #
    # Cost as actually scoped: THREE baselines x three seeds x ~2.4 h = ~21.6 GPU-h against a
    # campaign near 893, about 2.4% -- not the ~3.2% the four-family figure implies.
    import importlib.util as _il
    _spec = _il.spec_from_file_location(
        "_evaluator_identity_for_modes", Path(__file__).resolve().with_name("evaluator_identity.py"))
    _identity = _il.module_from_spec(_spec)
    _spec.loader.exec_module(_identity)
    if _identity.FAMILY_EVAL_POLICY_MODE.get(family) == "sample":
        out["ENDPOINT_EVAL_POLICY_MODES"] = "native,mode"
    for axis in ("regimes", "scenes", "episodes"):
        endpoint_key = f"offline_eval_{axis}"
        endpoint_value = settings.get(endpoint_key)
        curve_value = settings.get(f"curve_eval_{axis}", endpoint_value)
        for value, name in ((endpoint_value, f"ENDPOINT_EVAL_{axis.upper()}"),
                            (curve_value, f"CURVE_EVAL_{axis.upper()}")):
            if value is None:
                continue
            if isinstance(value, list):
                value = ",".join(str(item) for item in value)
            out[name] = str(value)
    for key, name in (("eval_every", "EVAL_EVERY_FRAMES"), ("eval_episodes", "EVAL_EPISODES"),
                      ("save_every", "SAVE_EVERY_FRAMES")):
        value = settings.get(key)
        if value is not None:
            out[name] = str(value)
    if settings.get("preserve_snapshots") is not None:
        out["RLVIGEN_PRESERVE_SNAPSHOTS"] = str(settings["preserve_snapshots"])

    capacity = settings.get("replay_capacity")
    option = settings.get("replay_capacity_option")
    if capacity is not None:
        if option:
            out["NATIVE_EXTRA_OVERRIDES"] = render(option, {"replay_capacity": str(capacity)})
        else:
            # Declared and unreachable. dmc_gb takes `capacity=args.train_steps` with no flag, so
            # saying nothing here would let a job run at the full-budget buffer while the schedule
            # believed it was capped -- and the schedule's tier arithmetic depends on the cap.
            out["NATIVE_PRODUCTION_UNAPPLIED"] = (
                f"replay_capacity={capacity} is declared for {family} but no option exposes it; "
                "capping needs a source change")
    return out

def environment_for(family: str, fields: dict, path: Path | None = None) -> dict:
    """Environment a cell needs that is not expressible as an argument.

    ALDA takes its results directory from `ALDA_RESULTS` because its launcher reads that, not a
    flag; declaring it here keeps the runner from growing a per-family export.
    """
    entry = resolved_descriptor(family, path)
    fields = full_fields(family, fields, path)
    return {key: render(value, fields) for key, value in entry.get("environment", {}).items()}


def artifact_root(family: str, fields: dict, path: Path | None = None) -> Path:
    entry = resolved_descriptor(family, path)
    return Path(render(entry["artifact_root"], full_fields(family, fields, path)))


def retain(family: str, fields: dict, output: Path, path: Path | None = None) -> dict:
    """Copy this family's proof-of-completion into the cell's output directory.

    Fails closed on an absent required curve or an absent/empty checkpoint: a run that returns
    neither a plottable curve nor a loadable terminal checkpoint is not a usable run, and saying
    so here is cheaper than discovering it after a seven-hour production job.
    """
    entry = descriptor(family, path)
    root = artifact_root(family, fields, path)
    fields = full_fields(family, fields, path)
    output.mkdir(parents=True, exist_ok=True)
    retained: dict[str, object] = {"family": family, "artifact_root": str(root), "curves": [], "directories": []}

    # [Claude 2026-09-02 07:20 MSK: curve names are templates too. IDAAC's logger writes
    # `progress-robosuite:Door-idaac-s1.csv` -- the environment, the algorithm and the seed are all
    # in the filename -- so rendering only the checkpoint left the curve unfindable.]
    # [Claude 2026-09-02 10:20 MSK: two families have no structured sink at all. ALDA's file log is
    # created and left empty (its metrics go to the python logger's stream handler and to W&B, which
    # does not run here); CTRL logs through W&B and prints one line per log step. For those, the
    # console log IS the curve -- and the fail-closed property is kept by requiring the console log
    # the runner captured to be non-empty, rather than by dropping the requirement.]
    if not entry["required_curves"]:
        console = output / "training.log"
        if not console.is_file() or console.stat().st_size == 0:
            fail(f"this family's curve is its console log, and it is absent or empty: {console}")
        retained["curves"].append("training.log (console)")
    for name in entry["required_curves"]:
        name = render(name, fields)
        source = root / name
        if not source.is_file() or source.stat().st_size == 0:
            fail(f"required curve is absent or empty: {source}")
        shutil.copy2(source, output / name)
        retained["curves"].append(name)
    for name in entry["optional_curves"]:
        name = render(name, fields)
        source = root / name
        if source.is_file() and source.stat().st_size > 0:
            shutil.copy2(source, output / name)
            retained["curves"].append(name)
    for name in entry["optional_directories"]:
        name = render(name, fields)
        source = root / name
        if source.is_dir():
            shutil.copytree(source, output / name, dirs_exist_ok=True)
            retained["directories"].append(name)

    # [Claude 2026-09-02 08:45 MSK: some families name the checkpoint after a value only the run
    # knows. ALDA writes `checkpoints/sac_<its own env name>_step_<step>.pt`, so the pattern pins
    # the step -- the part that must be right -- and globs the part that is the family's business.
    # Exactly one match is required: several would mean the endpoint is ambiguous.]
    pattern = render(entry["checkpoint"], fields)
    if "*" in pattern:
        matches = sorted(root.glob(pattern))
        if len(matches) != 1:
            fail(f"expected exactly one terminal checkpoint matching {root / pattern}, found {len(matches)}")
        checkpoint = matches[0]
    else:
        checkpoint = root / pattern
    if not checkpoint.is_file() or checkpoint.stat().st_size == 0:
        fail(f"terminal checkpoint is absent or empty: {checkpoint}")
    # One normalised name across families, so a downstream evaluator has a single path to open.
    shutil.copy2(checkpoint, output / "snapshot.pt")
    retained["checkpoint_source"] = str(checkpoint)
    retained["checkpoint_bytes"] = checkpoint.stat().st_size

    # [Claude 2026-09-02 11:35 MSK: intermediate checkpoints, when the run was asked to keep them.
    # A 500k run writes ten and upstream keeps one; the nine it discards are the same policy at
    # 50k, 100k, ... and evaluating them offline costs no training at all. Kept under their own
    # directory so the terminal one stays unambiguous.]
    intermediate = entry.get("intermediate_checkpoints")
    if intermediate:
        matches = [item for item in sorted(root.glob(render(intermediate, fields)))
                   if item.is_file() and item.resolve() != checkpoint.resolve()]
        # [Claude 2026-09-07] Thin the retained grid to `preserve_snapshots`, for EVERY family.
        #
        # This cadence existed only on the write side and only for RL-ViGen: `family.py` emits
        # RLVIGEN_PRESERVE_SNAPSHOTS, which P18's patch in RL-ViGen's own train.py reads. The
        # other six families write every stamp and kept every stamp, so a 600k cell produced a
        # 7-point curve for the RL-ViGen five and a 13-point curve for everyone else -- two x-grids
        # in one figure, from a descriptor field that six families simply could not honour rather
        # than from any decision. The trajectory grid is evaluated per retained stamp, so the same
        # asymmetry doubled their evaluation cost: measured at 3 episodes x 4 regimes x 10 scenes,
        # 13 stamps is 10.8 GPU-h/cell for idaac against 2.1 for drqv2 (plan_production.
        # curve_eval_hours), and idaac's own training is only ~4.8 h -- a curve costing twice its
        # run.
        #
        # Thin by FRAME, not by position. Position was the first attempt and it is wrong for the one
        # family whose write side already honours this cadence: RL-ViGen's P18 patch writes only
        # multiples of `preserve_snapshots`, so keeping every k-th of an already-thinned set thins
        # it a second time -- 100k, 200k, 300k... becomes 200k, 400k... The full test suite caught
        # it, which is the argument for running it.
        #
        # By frame the rule is idempotent everywhere: keep a stamp when its frame is a multiple of
        # the cadence. Six families name their files by frame. `ppg` names by save INDEX, so its
        # frame is `(index + 1) * save_every` -- the same reconstruction `run_probe.sh`'s
        # `ppg_checkpoint_frame` falls back to when the training log is unavailable.
        settings = entry.get("production", {}) or {}
        preserve = settings.get("preserve_snapshots")
        save_every = settings.get("save_every")
        # Only thin where the TRAINER does not already do it. rlvigen's P18 patch writes stamps at
        # the cadence, so applying it again here thins twice.
        applied_by = settings.get("preserve_snapshots_applied_by", "retain")
        if (preserve and save_every and int(preserve) > int(save_every) and matches
                and applied_by == "retain"):
            def _frame_of(item, position):
                if family == "ppg":
                    return (position + 1) * int(save_every)
                return _stamp_order(item.name)

            ordered = sorted(matches, key=lambda item: _stamp_order(item.name))
            kept = [item for position, item in enumerate(ordered)
                    if _frame_of(item, position) % int(preserve) == 0]
            # A run shorter than one cadence step has no stamp at a multiple of it, and thinning to
            # nothing is never what the cadence means -- `run_curve_eval` treats an empty stamp set
            # as fatal in production, so a coarse cadence on a short budget would turn a working
            # probe into a failed one. Keep everything in that case and say so.
            if kept:
                retained["intermediate_thinned_to"] = {
                    "preserve_snapshots": preserve, "rule": "frame % preserve_snapshots == 0",
                    "kept": len(kept), "written": len(ordered)}
                matches = kept
            else:
                retained["intermediate_thinned_to"] = {
                    "preserve_snapshots": preserve,
                    "rule": "cadence exceeds the whole run; every stamp kept",
                    "kept": len(ordered), "written": len(ordered)}
        if matches:
            (output / "checkpoints").mkdir(exist_ok=True)
            retained["intermediate_checkpoints"] = {}
            for item in matches:
                shutil.copy2(item, output / "checkpoints" / item.name)
                retained["intermediate_checkpoints"][item.name] = item.stat().st_size
    (output / "retained.json").write_text(json.dumps(retained, indent=2, sort_keys=True) + "\n")
    return retained



def _stamp_order(name: str) -> int:
    """The trailing integer a stamped checkpoint carries: a frame for six families, a save index
    for ppg. Only its ORDER is used here, and both orderings agree."""
    digits = re.findall(r"\d+", name)
    return int(digits[-1]) if digits else 0

def option_value(entry: dict, flag: str) -> str | None:
    """The literal an option carries, still in template form if the descriptor wrote one."""
    options = entry["options"]
    if flag in options:
        index = options.index(flag)
        if index + 1 < len(options):
            return options[index + 1]
    for item in options:
        if item.startswith(flag + "="):
            return item.split("=", 1)[1]
    return None


def quantum_component(entry: dict, flag: str) -> int:
    constants = entry.get("constants", {})
    raw = option_value(entry, flag)
    if raw is None:
        raw = constants.get(flag.lstrip("-"))
    if isinstance(raw, str) and raw.startswith("{") and raw.endswith("}"):
        raw = constants.get(raw[1:-1])
    if raw is None:
        fail(f"endpoint rule needs {flag}, which this descriptor neither sets nor declares")
    return int(raw)


def expected_endpoint(family: str, requested: int, path: Path | None = None,
                      profile: str | None = None) -> int:
    """The frame count this family's own loop will actually reach for a requested budget.

    An exact rule, not a tolerance. RL-ViGen and dmc_gb stop on the requested number. IDAAC
    computes `num_env_steps // num_steps // num_processes` updates and therefore floors to a whole
    rollout; PPG tests its budget before taking a segment and therefore overshoots to the next
    one. A run that lands anywhere else has not done what was asked and is a failure, which is
    the whole point of computing this instead of accepting a percentage.
    """
    entry = resolved_descriptor(family, path, profile)
    endpoint = entry.get("endpoint") or {"rule": "exact"}
    rule = endpoint["rule"]
    if rule == "exact":
        return requested
    quantum = 1
    for flag in endpoint["quantum_flags"]:
        quantum *= quantum_component(entry, flag)
    if rule == "floor_to_quantum":
        return (requested // quantum) * quantum
    if rule == "ceil_to_quantum":
        return -(-requested // quantum) * quantum
    fail(f"unknown endpoint rule: {rule}")
    raise AssertionError


def dependency_list(family: str, key: str, path: Path | None = None) -> list[str]:
    """Per-family system and pip dependencies.

    They are declared per family rather than in requirements-native.txt because they are not
    universal: PPG needs an MPI runtime that nothing else uses, and installing it into every job
    would make every job's bootstrap slower and its resolved-package manifest less honest about
    what that job actually needed.
    """
    return list(resolved_descriptor(family, path).get(key, []))


def import_gate(family: str, root: Path, cells: str = "", path: Path | None = None) -> None:
    """Import the family's real entry point before any timed cell.

    This is the gate that already caught termcolor, numba, matplotlib and h5py on the RL-ViGen
    path, each time for the price of a bootstrap instead of the price of a calibration. A family
    that declares no gate is skipped rather than silently passed.
    """
    entry = resolved_descriptor(family, path)
    gate = entry.get("import_gate")
    if not gate:
        return
    import os
    import subprocess

    environment = dict(os.environ)
    environment["PYTHONPATH"] = ":".join(str((root / item).resolve()) for item in gate["pythonpath"])
    environment.setdefault("RLVIGEN_ROOT", str((root / "RL-ViGen-upstream").resolve()))
    modules = list(gate["modules"])
    template = entry.get("baseline_module")
    if template:
        for spec in (item.strip() for item in cells.split(",") if item.strip()):
            baseline = spec.split(":", 1)[0]
            if baseline in entry["baselines"]:
                module = render(template, {"baseline": baseline})
                if module not in modules:
                    modules.append(module)
    program = "import " + ", ".join(modules)
    result = subprocess.run(
        [sys.executable, "-c", program],
        cwd=str((root / gate["cwd"]).resolve()),
        env=environment,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        fail(f"{family} import gate failed before any timed cell:\n{result.stderr.strip()}")


def filtered_requirements(cells: str, requirements: Path, path: Path | None = None) -> str:
    """The base requirements minus anything a family in this job cannot have installed.

    Only a family that already cannot share a job may exclude a base requirement, so there is never
    a question of whose exclusion wins.
    """
    excluded: set[str] = set()
    for family in families_of_cells(cells, path):
        entry = descriptor(family, path)
        names = entry.get("excluded_base_requirements") or []
        if names and entry.get("co_schedulable") is not False:
            fail(f"{family} excludes base requirements but is not marked co_schedulable false")
        excluded.update(name.lower() for name in names)
    if not excluded:
        return requirements.read_text()

    kept = []
    for line in requirements.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("--index-url") and "download.pytorch.org" in stripped and "torch" in excluded:
            continue
        name = stripped.split("==")[0].split("[")[0].strip().lower()
        if stripped and not stripped.startswith(("#", "--")) and name in excluded:
            continue
        kept.append(line)
    return "\n".join(kept) + "\n"


def excludes_base_requirements(cells: str, path: Path | None = None) -> bool:
    """Does any family in this job run without part of the shared base environment?"""
    return any(descriptor(name, path).get("excluded_base_requirements")
               for name in families_of_cells(cells, path))


def check_co_schedulable(cells: str, path: Path | None = None) -> None:
    """Refuse a job that mixes a family which cannot share an environment.

    CTRL's jax[cuda12] install replaces numpy and cudnn with versions torch, numba and matplotlib
    reject; the runner's own `pip check` then fails and the whole job dies during bootstrap. That
    happened once (bt1a8q6ee090jh1k9npp) and cost a bootstrap. Refusing here costs nothing.
    """
    families = families_of_cells(cells, path)
    exclusive = [name for name in families if descriptor(name, path).get("co_schedulable") is False]
    if exclusive and len(families) > 1:
        fail(
            f"{', '.join(exclusive)} cannot share a job with another family "
            f"(this job asks for {', '.join(families)}); submit it on its own"
        )


def families_of_cells(cells: str, path: Path | None = None) -> list[str]:
    """The distinct families a cell list touches, in first-appearance order."""
    seen: list[str] = []
    for spec in (item.strip() for item in cells.split(",") if item.strip()):
        family = family_of(spec.split(":", 1)[0], path)
        if family not in seen:
            seen.append(family)
    return seen


FINITENESS_PROBE = r"""
import json, pickle, sys

path = sys.argv[1]
bad = total = 0
tensors = 0
stubbed = set()


# A snapshot pickles the agent, so unpickling it normally needs that family's own modules on the
# path. That coupling makes a gate about NaNs fail on a path instead: the same probe run outside
# the payload root -- a local rehearsal, a moved tree -- reports ModuleNotFoundError and the cell
# is marked failed after its training already succeeded. Only floating-point values are wanted
# here, and those live in torch storages, which unpickle without their owning class. So substitute
# a placeholder for any class that will not import and report which ones, rather than refusing.
class _Stub(object):
    def __init__(self, *args, **kwargs):
        pass

    def __setstate__(self, state):
        self.__dict__.update(state if isinstance(state, dict) else {"state": state})


class _Unpickler(pickle.Unpickler):
    def find_class(self, module, name):
        try:
            return pickle.Unpickler.find_class(self, module, name)
        except Exception:
            stubbed.add(module + "." + name)
            return type(str(name), (_Stub,), {})


class _forgiving_pickle(object):
    Unpickler = _Unpickler
    load = staticmethod(pickle.load)
    loads = staticmethod(pickle.loads)
    dump = staticmethod(pickle.dump)
    dumps = staticmethod(pickle.dumps)
    HIGHEST_PROTOCOL = pickle.HIGHEST_PROTOCOL


def walk(node, depth=0):
    global bad, total, tensors
    if depth > 12:
        return
    try:
        import torch
    except Exception:
        torch = None
    if torch is not None and isinstance(node, torch.Tensor):
        if node.is_floating_point():
            value = node.detach().float()
            bad += int(torch.isnan(value).sum() + torch.isinf(value).sum())
            total += value.numel()
            tensors += 1
        return
    try:
        import numpy
    except Exception:
        numpy = None
    if numpy is not None and isinstance(node, numpy.ndarray):
        if node.dtype.kind == "f":
            bad += int((~numpy.isfinite(node)).sum())
            total += node.size
            tensors += 1
        return
    if torch is not None and isinstance(node, torch.nn.Module):
        for value in node.state_dict().values():
            walk(value, depth + 1)
        return
    if isinstance(node, dict):
        for value in node.values():
            walk(value, depth + 1)
        return
    if isinstance(node, (list, tuple, set)):
        for value in node:
            walk(value, depth + 1)
        return
    attributes = getattr(node, "__dict__", None)
    if isinstance(attributes, dict):
        for value in attributes.values():
            walk(value, depth + 1)


# Dispatch on CONTENT, not on the file name. This read `path.endswith(".msgpack")` and took the
# torch branch for everything else -- but the runner copies every family's checkpoint to
# `snapshot.pt` whatever it was called, so `ctrl`'s flax msgpack arrived here as a .pt and the
# probe answered "ModuleNotFoundError: No module named 'torch'". ctrl is JAX and EXCLUDES torch
# from its environment on purpose, so that was a gate failing a cell whose training had already
# succeeded and reached its endpoint (bt1f1kg6kiemsj7j8f6q, 2026-09-03).
#
# The project has made this exact mistake before, and it is recorded: an alda terminal save was
# once "verified" by its filename rather than its bytes. A loader chosen by extension is the same
# error wearing a different hat.
#
# Torch archives are zip files ("PK\x03\x04"); legacy torch pickles start with 0x80. Anything
# else is tried as msgpack first. Every loader is attempted regardless, in the order the sniff
# suggests, because a wrong guess should cost an exception and not a failed cell.
def _load_torch(target):
    import torch
    try:
        return torch.load(target, map_location="cpu", weights_only=False)
    except Exception:
        return torch.load(
            target, map_location="cpu", weights_only=False, pickle_module=_forgiving_pickle
        )


def _load_msgpack(target):
    from flax.serialization import msgpack_restore
    with open(target, "rb") as handle:
        return msgpack_restore(handle.read())


def _load_numpy(target):
    import numpy
    return dict(numpy.load(target, allow_pickle=True))


with open(path, "rb") as _probe_handle:
    _magic = _probe_handle.read(4)
_torch_shaped = _magic[:4] == b"PK\x03\x04" or _magic[:1] == b"\x80"
_loaders = [("torch", _load_torch), ("msgpack", _load_msgpack), ("numpy", _load_numpy)]
if not _torch_shaped:
    _loaders = [_loaders[1], _loaders[0], _loaders[2]]

payload = None
loader_used = None
attempts = []
for _name, _loader in _loaders:
    try:
        payload = _loader(path)
        loader_used = _name
        break
    except Exception as error:
        attempts.append("%s: %s: %s" % (_name, type(error).__name__, str(error)[:80]))

if loader_used is None:
    print(json.dumps({"error": "no loader could read it -- " + " | ".join(attempts)}))
    raise SystemExit(0)

try:
    walk(payload)
except Exception as error:
    print(json.dumps({"error": "%s: %s" % (type(error).__name__, str(error)[:160])}))
    raise SystemExit(0)

# Is this checkpoint the TRAINED model, or the one the trainer constructed?
#
# `ppg` retained an untrained model on 2026-09-02 and every gate passed it: the file existed, was
# the right size, and contained finite floats. LogSaveHelper saves once in its own __init__ before
# any gradient step, `ic_per_save` defaults to 100_000, and a 4,096-interact probe crosses no
# boundary -- so the only save on disk was the construction one. It was caught by arithmetic
# afterwards, which is the wrong time to catch it.
#
# A general "is this trained?" test does not exist, but a good partial one does for the four
# continuous-head baselines: their state-independent log-std is initialised to EXACTLY zero, so a
# saved value of exactly zero in every dimension means no optimiser step reached it. Reported, not
# failed on -- a short run can legitimately barely move it, and this probe should not decide that.
policy = {}
try:
    import torch as _t
    def _scan(node, depth=0):
        if depth > 6 or policy:
            return
        if isinstance(node, _t.nn.Module):
            for name, param in node.named_parameters():
                if "log_std" in name.lower() or "logstd" in name.lower():
                    values = param.detach().float().reshape(-1).tolist()
                    policy["name"] = name
                    policy["log_std"] = values
                    policy["mean_log_std"] = sum(values) / max(1, len(values))
                    policy["min_log_std"] = min(values) if values else None
                    policy["max_log_std"] = max(values) if values else None
                    policy["all_exactly_zero"] = all(v == 0.0 for v in values)
                    return
        if isinstance(node, dict):
            for value in node.values():
                _scan(value, depth + 1)
        elif isinstance(node, (list, tuple)):
            for value in node:
                _scan(value, depth + 1)
        else:
            attributes = getattr(node, "__dict__", None)
            if isinstance(attributes, dict):
                for value in attributes.values():
                    _scan(value, depth + 1)
    _scan(payload)
except Exception:
    policy = {}

print(json.dumps({"non_finite": bad, "float_values": total, "arrays": tensors,
                  "stubbed_classes": sorted(stubbed), "policy_log_std": policy,
                  "loader": loader_used}))
"""


def check_finite(family: str, root: Path, checkpoint: Path, path: Path | None = None) -> dict:
    """Is this checkpoint a network, or NaNs?

    docs/CONSTRUCTION.md#c57 records a drqv2 run that diverged to NaN around frame 35,000, trained
    for 70,000 more, logged seven evaluations and wrote a snapshot -- every artifact this project
    keeps looked like a run that had merely trained badly. On a seven-hour production run that
    failure mode is expensive twice: the run, and everything computed from it afterwards.

    scripts/check_checkpoint_finite.py is the project's instrument for this and it walks a pickled
    agent's nn.Modules. Half the families here do not save one -- ALDA saves a dict of state dicts,
    IDAAC a list, CTRL a msgpack -- so this walks any nested structure for floating-point values,
    in a subprocess carrying the family's own import path because a pickled agent needs its own
    modules and those namespaces collide across families.
    """
    import os
    import subprocess

    entry = descriptor(family, path)
    gate = entry.get("import_gate") or {}
    search = [str((root / item).resolve()) for item in gate.get("pythonpath", [])]
    search.append(str((root / "runnable" / "_shim").resolve()))
    environment = dict(os.environ)
    environment["PYTHONPATH"] = ":".join(search)
    environment.setdefault("RLVIGEN_ROOT", str((root / "RL-ViGen-upstream").resolve()))

    # the probe needs the family's import path, not its working directory; fall back when the
    # declared one is not present (a test tree, or a family whose repository is cloned at run time)
    working = (root / gate.get("cwd", ".")).resolve()
    if not working.is_dir():
        working = root
    result = subprocess.run(
        [sys.executable, "-c", FINITENESS_PROBE, str(checkpoint)],
        cwd=str(working),
        env=environment,
        text=True,
        capture_output=True,
    )
    line = next((item for item in result.stdout.splitlines() if item.startswith("{")), None)
    if line is None:
        fail(f"could not inspect {checkpoint}: {(result.stderr.strip().splitlines() or ['no output'])[-1][:160]}")
    report = json.loads(line)
    if "error" in report:
        fail(f"could not load {checkpoint}: {report['error']}")
    if not report["float_values"]:
        fail(f"found no floating-point values in {checkpoint}; it is not a usable checkpoint")
    if report["non_finite"]:
        fail(
            f"{report['non_finite']} of {report['float_values']} floating-point values in "
            f"{checkpoint} are NaN or infinite"
        )
    return report


def cells_need_places365(cells: str, path: Path | None = None) -> bool:
    families = load(path)
    for spec in (item.strip() for item in cells.split(",") if item.strip()):
        baseline = spec.split(":", 1)[0]
        for value in families.values():
            if baseline in value.get("places365_baselines", ()):
                return True
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    def add_cell_arguments(sub):
        sub.add_argument("--family")
        sub.add_argument("--baseline", required=True)
        sub.add_argument("--task", default="Door")
        sub.add_argument("--frames", default="10000")
        sub.add_argument("--eval-every", default="10000")
        sub.add_argument("--eval-episodes", default="2")
        sub.add_argument("--save-every", default=None)
        sub.add_argument("--seed", default="1")
        sub.add_argument("--run-dir", required=True)

    build = commands.add_parser("command")
    add_cell_arguments(build)

    keep = commands.add_parser("retain")
    add_cell_arguments(keep)
    keep.add_argument("--output", type=Path, required=True)

    prod = commands.add_parser("production-env")
    prod.add_argument("--cells", required=True)
    profile = commands.add_parser("host-profile")
    excluded = commands.add_parser("excluded-modules")
    excluded.add_argument("--cells", required=True)
    budget = commands.add_parser("check-budget")
    budget.add_argument("--cells", required=True)
    budget.add_argument("--frames", type=int, required=True)
    finite = commands.add_parser("check-finite")
    finite.add_argument("--family", required=True)
    finite.add_argument("--root", type=Path, default=Path("."))
    finite.add_argument("--checkpoint", type=Path, required=True)

    variables = commands.add_parser("environment")
    add_cell_arguments(variables)

    which = commands.add_parser("family-of")
    which.add_argument("--baseline", required=True)

    launcher = commands.add_parser("launcher")
    launcher.add_argument("--family", required=True)

    flavor = commands.add_parser("places365-flavor")
    flavor.add_argument("--family", required=True)

    needs = commands.add_parser("needs-places365")
    needs.add_argument("--cells", required=True)

    endpoint = commands.add_parser("expected-endpoint")
    endpoint.add_argument("--family")
    endpoint.add_argument("--baseline")
    endpoint.add_argument("--frames", type=int, required=True)

    apt = commands.add_parser("apt-packages")
    apt.add_argument("--family", required=True)

    pips = commands.add_parser("pip-requirements")
    pips.add_argument("--family", required=True)

    filtered = commands.add_parser("filtered-requirements")
    filtered.add_argument("--cells", required=True)
    filtered.add_argument("--requirements", type=Path, default=Path("requirements-native.txt"))

    excludes = commands.add_parser("excludes-base-requirements")
    excludes.add_argument("--cells", required=True)

    schedulable = commands.add_parser("check-co-schedulable")
    schedulable.add_argument("--cells", required=True)

    admission = commands.add_parser("admission-tier")
    admission.add_argument("--tier", required=True)

    tier = commands.add_parser("check-tier")
    tier.add_argument("--cells", required=True)
    tier.add_argument("--tier", required=True)
    disk = commands.add_parser("disk-requirement")
    disk.add_argument("--cells", required=True)
    disk.add_argument("--frames", type=int, required=True)
    disk.add_argument("--profile")
    # [Claude 2026-09-08] `run_on_production_host.sh` needs ONE integer, and used to get it by
    # piping this command's JSON into a second `python3 -c` -- two python invocations ON THE HOST,
    # outside any container. The production host's rule is that nothing but small python-unrelated
    # actions and docker itself runs outside a container, so the wrapper now makes a single
    # containerised call and this flag is what it calls. One number, one process, no host parser.
    disk.add_argument("--ceil-total", action="store_true",
                      help="print only required_gib rounded up, for a caller that wants a number "
                           "rather than a document")
    memory = commands.add_parser("check-memory")
    memory.add_argument("--frames", type=int,
                        help="the budget this cell will run; sizes the replay charge")
    memory.add_argument("--cells", required=True)
    memory.add_argument("--tier", required=True)
    memory.add_argument("--allow-unmeasured", action="store_true",
                        help="accept a family with no recorded fixed_peak_gib; the risk is then "
                             "explicit and attributable rather than inherited from a silent skip")

    grouping = commands.add_parser("families-of-cells")
    grouping.add_argument("--cells", required=True)

    gate = commands.add_parser("import-gate")
    gate.add_argument("--family", required=True)
    gate.add_argument("--root", type=Path, default=Path("."))
    gate.add_argument("--cells", default="")

    listing = commands.add_parser("baselines")
    listing.add_argument("--family", required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "host-profile":
            print(host_profile())
            return 0
        if args.command == "needs-places365":
            return 0 if cells_need_places365(args.cells) else 1
        if args.command == "family-of":
            print(family_of(args.baseline))
            return 0
        if args.command == "launcher":
            print(descriptor(args.family)["launcher"])
            return 0
        if args.command == "places365-flavor":
            print(descriptor(args.family)["places365_flavor"])
            return 0
        if args.command == "expected-endpoint":
            name = args.family or family_of(args.baseline)
            print(expected_endpoint(name, args.frames))
            return 0
        if args.command == "apt-packages":
            print(" ".join(dependency_list(args.family, "apt_packages")))
            return 0
        if args.command == "pip-requirements":
            print(" ".join(dependency_list(args.family, "pip_requirements")))
            return 0
        if args.command == "filtered-requirements":
            print(filtered_requirements(args.cells, args.requirements.resolve()), end="")
            return 0
        if args.command == "excludes-base-requirements":
            return 0 if excludes_base_requirements(args.cells) else 1
        if args.command == "check-co-schedulable":
            check_co_schedulable(args.cells)
            return 0
        if args.command == "admission-tier":
            print(admission_tier_for(args.tier))
            return 0
        if args.command == "check-tier":
            check_tier(args.cells, args.tier)
            return 0
        if args.command == "families-of-cells":
            for name in families_of_cells(args.cells):
                print(name)
            return 0
        if args.command == "excluded-modules":
            # the import NAME, which is not always the requirement name
            aliases = {"torchvision": "torchvision", "opencv-python": "cv2",
                       "scikit-learn": "sklearn", "pillow": "PIL"}
            seen = set()
            for family in families_of_cells(args.cells):
                for item in descriptor(family).get("excluded_base_requirements", ()):
                    name = aliases.get(item.lower(), item.replace("-", "_"))
                    if name not in seen:
                        seen.add(name)
                        print(name)
            return 0
        if args.command == "check-budget":
            check_budget(args.cells, args.frames)
            print(f"budget ok: {args.frames} frames")
            return 0
        if args.command == "disk-requirement":
            import json as _json
            result = disk_requirement_gib(
                args.cells, args.frames, profile=args.profile or os.environ.get("NATIVE_HOST_PROFILE"))
            if args.ceil_total:
                print(int(result["required_gib"] + 0.999))
            else:
                print(_json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "check-memory":
            check_memory(args.cells, args.tier, allow_unmeasured=args.allow_unmeasured,
                         frames=getattr(args, "frames", None))
            print(f"memory ok: {args.cells} on {args.tier}")
            return 0
        if args.command == "production-env":
            resolved = production_env(args.cells)
            for key, value in resolved.items():
                print(f"{key}={value}")
            if not resolved:
                # An empty result and a broken command look identical otherwise, and for three
                # families empty is the correct answer -- they have no runtime dial to set.
                family = sorted(families_of_cells(args.cells))[0]
                shape = production(family).get("training_time_eval", "not recorded")
                print(f"# {family}: no runtime dial applies -- {shape.splitlines()[0]}")
            return 0
        if args.command == "check-finite":
            print(json.dumps(check_finite(args.family, args.root.resolve(), args.checkpoint.resolve())))
            return 0
        if args.command == "import-gate":
            import_gate(args.family, args.root.resolve(), args.cells)
            return 0
        if args.command == "baselines":
            print(",".join(descriptor(args.family)["baselines"]))
            return 0

        family = args.family or family_of(args.baseline)
        fields = substitutions(
            baseline=args.baseline,
            task=args.task,
            frames=args.frames,
            eval_every=args.eval_every,
            eval_episodes=args.eval_episodes,
            seed=args.seed,
            run_dir=args.run_dir,
        )
        if args.save_every:
            fields["save_every"] = str(args.save_every)
        if args.command == "environment":
            for key, value in sorted(environment_for(family, fields).items()):
                print(f"{key}={value}")
            return 0
        if args.command == "command":
            for item in command(family, fields):
                print(item)
            return 0
        retain(family, fields, args.output)
        return 0
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
