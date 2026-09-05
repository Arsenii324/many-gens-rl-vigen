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
    idaac's V100 profile raises `num_processes` 4 -> 16, so one rollout is 4096 frames, not the
    stored 1024 -- a canary submitted at, say, 2000 frames would satisfy the stale check while
    completing ZERO rollouts (`num_updates = frames // num_steps // num_processes == 0`), training
    nothing and proving nothing about the profile it claims to validate. `profile` now re-derives
    the floor from ROLLOUT_QUANTUM_CONSTANTS against the profile's RESOLVED constants for the two
    affected families, instead of trusting the stored number once a profile changes the geometry.
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
                 allow_unmeasured: bool = False) -> None:
    """Reject a tier that cannot hold its measured working set plus safety margin.

    Most families have one fixed peak.  IBAC-SNI also has an explicitly measured process-tree
    model: spawned MuJoCo/EGL workers do not share the parent's address space, so a one-process
    peak cannot certify a command that asks for sixteen.  The runner's extra overrides are part of
    the effective command and therefore part of this preflight, rather than a loophole around it.
    """
    usable = {"gt4.1": 14.5, "gt4i.1": 27.0}
    if tier not in usable:
        fail(f"unknown job tier: {tier}")
    unmeasured: list[str] = []
    for family in families_of_cells(cells, path):
        entry = resolved_descriptor(family, path)
        settings = entry.get("production", {})
        peak = settings.get("fixed_peak_gib")
        margin = settings.get("memory_margin_gib", 0.0)
        if peak is None:
            # This used to `continue`, so a family with no measured peak fell through to the
            # caller printing "memory ok" -- an unmeasured family certified as fitting. ctrl was
            # certified for gt4.1 that way and SIGKILLed at 11.07 GiB RSS (bt1lhobnsq5lq4766np6).
            # An absent measurement is not a passing one.
            unmeasured.append(family)
            continue
        required = float(peak) + float(margin)
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
    if unmeasured and not allow_unmeasured:
        fail("no measured memory peak for " + ", ".join(sorted(unmeasured))
             + f"; cannot certify {tier}. Record `fixed_peak_gib` from a completed run, or pass "
               "--allow-unmeasured to accept the risk explicitly")


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
    if settings.get("online_eval_rng_isolated") is True:
        out["NATIVE_ISOLATE_ONLINE_EVAL"] = "1"
    # A production cell has two measured products: one reportable endpoint grid and a shallower
    # trajectory grid.  The runner deliberately leaves both opt-in for cheap probes, so this is
    # where production explicitly enables them.  The shared offline fields are the full endpoint
    # specification; a family may override only the curve depth (currently three episodes) while
    # retaining the same certified regimes and scenes.
    out["ENDPOINT_EVAL"] = "1"
    out["CURVE_EVAL"] = "1"
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
        if matches:
            (output / "checkpoints").mkdir(exist_ok=True)
            retained["intermediate_checkpoints"] = {}
            for item in matches:
                shutil.copy2(item, output / "checkpoints" / item.name)
                retained["intermediate_checkpoints"][item.name] = item.stat().st_size
    (output / "retained.json").write_text(json.dumps(retained, indent=2, sort_keys=True) + "\n")
    return retained


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

    tier = commands.add_parser("check-tier")
    tier.add_argument("--cells", required=True)
    tier.add_argument("--tier", required=True)
    memory = commands.add_parser("check-memory")
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
        if args.command == "check-memory":
            check_memory(args.cells, args.tier, allow_unmeasured=args.allow_unmeasured)
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
