"""Every environment knob a job cfg sets must be read by the runner that receives it.

[Claude 2026-09-04] The instance: three cfgs set `SAVE_EVERY`, `run_probe.sh` read only
`SAVE_EVERY_FRAMES`, and the runner silently fell back to "save once, at the end". Job
`bt1791fdh5uctgr1ckhk` then launched `--checkpoint_interval=10000` under a 10000-frame budget,
produced exactly one checkpoint, retained no intermediates -- and reported SUCCESS. Its entire
purpose was to validate a cadence and it validated none.

The class: a knob name is a contract between a yaml written by hand and a shell script, with
nothing in between to check it. An unread name is indistinguishable from a default. This test is
the missing link, so the next misspelled knob fails here instead of on a paid GPU.
"""
from pathlib import Path
import json
import re
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "datasphere" / "native"

# Set by the platform or consumed by the `env` prefix itself rather than by the runner's own reads.
PLATFORM = {
    "RLVIGEN_ARCHIVE", "RECORDS_OUT", "JOB", "CODE", "RESULT", "RLVIGEN", "RECORDS",
    "CUDA_ROOT", "MUJOCO_GL", "PYOPENGL_PLATFORM", "WANDB_API_KEY", "WANDB_MODE",
    "GRPC_DNS_RESOLVER", "XLA_PYTHON_CLIENT_PREALLOCATE", "TOKENIZERS_PARALLELISM",
    "NATIVE_DISABLE_ONLINE_EVAL", "NATIVE_ISOLATE_ONLINE_EVAL",
    # [Claude 2026-09-06] Read entirely by job.sh's own local submit-time preflight (the V100
    # budget reservation), which `_in_job_surface()` deliberately does not scan -- job.sh never
    # runs INSIDE the job, it runs on this machine before submission. Genuinely platform-local,
    # not a typo: grep confirms the only readers are job.sh and the two v100 cfgs that set it.
    "NATIVE_V100_RESERVATION_MINUTES",
}

# [Claude 2026-09-06] (cfg, knob) pairs whose reader was deliberately REMOVED after a one-time
# use, not left behind by accident. `cfg-ctrl-diag-v159.yaml` set `NATIVE_DIAGNOSE_EVALUATOR_
# IDENTITY` to drive a temporary block in `scripts/eval_grid.py` that root-caused CORRECTIONS.md
# #97 (the `door.xml` evaluator-identity bug); the block was reverted immediately afterward so the
# diagnostic code itself would not join `evaluator_identity.py`'s CODE_MEMBERS closure and move
# every family's hash. The cfg is kept as the historical record of the job that found the bug, not
# as something meant to be resubmitted -- resubmitting it today would silently do nothing. Scoped
# to the exact pair, not the knob name globally, so a future cfg reintroducing this knob by
# copy-paste is still caught.
RETIRED_KNOBS = {("cfg-ctrl-diag-v159.yaml", "NATIVE_DIAGNOSE_EVALUATOR_IDENTITY")}


def _knobs(cfg: Path) -> set[str]:
    """KEY=VALUE assignments inside the cmd block, which is where a cfg passes knobs."""
    found = set()
    for line in cfg.read_text().splitlines():
        if line.lstrip().startswith("#"):
            continue
        for key in re.findall(r"\b([A-Z][A-Z0-9_]{2,})=", line):
            found.add(key)
    return found


def _in_job_surface() -> str:
    """Everything that runs INSIDE the job and so inherits the cfg's environment: the runner, the
    python it invokes, and the clone patches it applies. A knob read by any of these is live --
    the first version of this test checked only the runner and called two working knobs dead
    (`RLVIGEN_PRESERVE_SNAPSHOTS`, read by `family.py`; `RLVIGEN_PLACES_WORKERS`, read by a
    clone patch)."""
    parts = [(NATIVE / "run_probe.sh").read_text()]
    for pattern in ("datasphere/native/*.py", "setup/*.py", "scripts/*.py",
                    "runnable/_patches/*.patch", "runnable/_launch/*.sh"):
        for path in sorted(ROOT.glob(pattern)):
            parts.append(path.read_text(errors="ignore"))
    return "\n".join(parts)


def _stem(key: str) -> str:
    for suffix in ("_FRAMES", "_SECONDS", "_STEPS", "_EPISODES"):
        if key.endswith(suffix):
            return key[: -len(suffix)]
    return key


def test_no_cfg_knob_is_dead():
    """A knob no in-job code reads is a typo that takes its default in silence."""
    surface = _in_job_surface()
    dead: dict[str, set[str]] = {}
    for cfg in sorted(NATIVE.glob("cfg-*.yaml")):
        for key in _knobs(cfg) - PLATFORM:
            if (cfg.name, key) in RETIRED_KNOBS:
                continue
            if not re.search(rf"\b{re.escape(key)}\b", surface):
                dead.setdefault(cfg.name, set()).add(key)
    assert not dead, ("cfg sets knobs no in-job code reads:\n"
                      + "\n".join(f"  {n}: {sorted(k)}" for n, k in sorted(dead.items())))


def test_no_cfg_knob_is_a_near_miss_of_a_runner_knob():
    """The defect that cost job bt1791fdh5uctgr1ckhk its purpose, generalised.

    `SAVE_EVERY` was not dead -- `family.py` reads it, so a presence check passes it -- yet
    `run_probe.sh` defaulted `SAVE_EVERY_FRAMES` and never saw it, and the cadence silently became
    "the whole budget". Two spellings of one stem, where the runner owns one and a cfg writes the
    other, is the shape of that bug. Flag it whatever the direction."""
    runner = (NATIVE / "run_probe.sh").read_text()
    # names the runner itself defaults, e.g. ${EVAL_EVERY_FRAMES:-...}
    owned = set(re.findall(r"\$\{([A-Z][A-Z0-9_]{2,}):-", runner))
    stems = {}
    for key in owned:
        stems.setdefault(_stem(key), set()).add(key)
    clashes = []
    for cfg in sorted(NATIVE.glob("cfg-*.yaml")):
        for key in _knobs(cfg) - PLATFORM:
            if key in owned:
                continue
            twin = stems.get(_stem(key))
            if twin and not re.search(rf"\b{re.escape(key)}\b", runner):
                clashes.append(f"  {cfg.name}: sets {key}, runner reads {sorted(twin)}")
    assert not clashes, ("cfg knob differs from the runner's own spelling of the same stem, so the "
                         "runner takes its default and the setting is inert:\n" + "\n".join(clashes))


def test_save_every_alias_is_honoured_not_ignored():
    """The specific regression, pinned: both spellings must reach `save_every`."""
    runner = (NATIVE / "run_probe.sh").read_text()
    assert 'save_every="${SAVE_EVERY_FRAMES:-${SAVE_EVERY:-$frames}}"' in runner
    assert "NATIVE_KNOB_CONFLICT" in runner, "differing spellings must fail, not pick one"


def test_family_py_emits_the_name_the_runner_reads():
    family = (NATIVE / "family.py").read_text()
    assert '("save_every", "SAVE_EVERY_FRAMES")' in family


def test_job_tier_satisfies_every_declared_cell():
    """A packed job inherits one tier; no cell may require a larger one.

    ALDA had already proven it needs gt4i.1, but cfg-curve-preflight2-v82 packed it into gt4.1 and
    repeated the known 11.5 GiB SIGKILL. The descriptor is the source of truth for this constraint.
    """
    import sys
    sys.path.insert(0, str(NATIVE))
    import family
    with pytest.raises(ValueError, match="alda requires gt4i.1"):
        family.check_tier("rad:1,alda:1", "gt4.1")
    family.check_tier("rad:1,alda:1", "gt4i.1")

    runner = (NATIVE / "job.sh").read_text()
    assert "check-tier" in runner, "the check must run before a cfg is submitted"


def test_submit_path_rejects_alda_on_the_measured_ram_ceiling():
    """The planner's RAM knowledge must also guard a hand-written submission cfg."""
    import sys
    sys.path.insert(0, str(NATIVE))
    import family
    with pytest.raises(ValueError, match="alda.*14.5"):
        family.check_memory("alda:1", "gt4.1")
    family.check_memory("alda:1", "gt4i.1")
    runner = (NATIVE / "job.sh").read_text()
    assert "check-memory" in runner


def test_submission_image_must_match_the_source_lock(tmp_path):
    """A digest in source-lock is useless if a hand-written job cfg can use a mutable tag.

    This exercises the shell entry point directly, before it can reach the paid DataSphere CLI.
    """
    expected = json.loads((NATIVE / "source-lock.json").read_text())["container_image"]
    cfg = tmp_path / "pinned.yaml"
    cfg.write_text(f"env:\n  docker:\n    image: {expected}\n")
    pinned = subprocess.run(
        ["bash", str(NATIVE / "job.sh"), "verify-image", str(cfg)],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert pinned.returncode == 0, pinned.stderr

    mutable = tmp_path / "mutable.yaml"
    mutable.write_text("env:\n  docker:\n    image: nvidia/cuda:12.2.2-runtime-ubuntu22.04\n")
    rejected = subprocess.run(
        ["bash", str(NATIVE / "job.sh"), "verify-image", str(mutable)],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert rejected.returncode != 0
    assert "MUTABLE OR MISMATCHED CONTAINER IMAGE" in rejected.stderr


def test_runner_requires_payload_families_before_remote_bootstrap():
    """The archive's declared family set must cover an offline evaluator too.

    `OFFLINE_EVAL_FAMILY` becomes `cells` without this explicit payload check, so a valid but
    rlvigen-only archive reaches IDAAC's unpickler after the expensive bootstrap and fails there.
    """
    runner = (NATIVE / "run_probe.sh").read_text()
    assert "--require-families" in runner
    check = runner.index("--require-families")
    assert check < runner.index("python3 -m pip install --upgrade pip")


def test_launcher_checkpoint_names_match_the_descriptor():
    """A launcher that asserts a checkpoint filename must assert one the descriptor declares.

    [Claude 2026-09-04] Same shape as the knob bug, one layer down: `families.json` declared ppg's
    terminal checkpoint as `model_terminal.jd` (what `--save_mode all` writes) while
    `ppg_cell.sh` still asserted `model.jd` (what upstream's default `save_mode='last'` writes).
    Job bt16323qtaqci9p8vke8 trained ppg to completion, printed NATIVE_PPG_TERMINAL_SAVE naming
    the file it had just written, and then failed the cell for not having written a different one.
    Two places naming one artefact, with nothing tying them together.
    """
    import json
    families = json.loads((NATIVE / "families.json").read_text())
    families = families.get("families", families)
    launch = ROOT / "runnable" / "_launch"
    bad = []
    for name, entry in families.items():
        if not isinstance(entry, dict) or not entry.get("checkpoint"):
            continue
        declared = {Path(str(entry["checkpoint"])).name}
        if entry.get("intermediate_checkpoints"):
            declared.add(Path(str(entry["intermediate_checkpoints"])).name)
        for script in sorted(launch.glob(f"{name}*.sh")):
            text = script.read_text()
            for asserted in set(re.findall(r'\$LOG_DIR/([A-Za-z0-9_.:{}*-]+\.(?:pt|jd|msgpack|pkl))', text)):
                # a name is fine if the descriptor declares it, or if it is a documented fallback
                # kept alongside a declared one in the same check
                if asserted in declared:
                    continue
                if any(d in text for d in declared):
                    continue   # declared name is asserted too; this is an accepted alternative
                bad.append(f"  {script.name} asserts {asserted!r}; {name} declares {sorted(declared)}")
    assert not bad, ("launcher asserts a checkpoint filename the descriptor does not declare, so a "
                     "correctly-saved run fails its own post-condition:\n" + "\n".join(bad))
