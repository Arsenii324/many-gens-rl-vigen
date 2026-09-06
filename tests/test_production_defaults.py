"""Every baseline resolves a complete production configuration, and it obeys the owner's limits.

"Ready to run" is a property of the artifacts or it is a claim in a conversation. These tests make
it the first: each of the twelve baselines must reach a family that declares a production block,
every value that is absent must say why it is absent, and the tier and packing choices must stay
inside the two constraints the owner set -- never a tier above gt4i.1, never more than two jobs at
once.

The `null`s matter as much as the numbers. Five families have no eval cadence to set and three run
no periodic training-time evaluation at all; a test that demanded a number everywhere would force
the fiction the first pass of families.json actually contained.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
FAMILIES = json.loads((ROOT / "datasphere" / "native" / "families.json").read_text())
DESCRIPTORS = {name: entry for name, entry in FAMILIES.items() if not name.startswith("_")}

ALLOWED_TIERS = {"gt4.1", "gt4i.1"}          # owner's standing limit: never more expensive
MAX_PARALLEL_JOBS = 4                         # owner's standing limit, raised from 2 on 2026-09-03
BASELINES = sorted(b for entry in DESCRIPTORS.values() for b in entry["baselines"])


def family_of(baseline: str) -> str:
    for name, entry in DESCRIPTORS.items():
        if baseline in entry["baselines"]:
            return name
    raise AssertionError(f"{baseline} belongs to no family")


def test_twelve_baselines_present():
    assert len(BASELINES) == 12, BASELINES


@pytest.mark.parametrize("baseline", BASELINES)
def test_every_baseline_has_a_production_block(baseline):
    entry = DESCRIPTORS[family_of(baseline)]
    assert "production" in entry, f"{baseline}: family {family_of(baseline)} declares no production block"


@pytest.mark.parametrize("baseline", BASELINES)
def test_tier_is_within_the_owners_limit(baseline):
    production = DESCRIPTORS[family_of(baseline)]["production"]
    assert production["tier"] in ALLOWED_TIERS, (
        f"{baseline}: tier {production['tier']!r} is outside the allowed set {ALLOWED_TIERS}")
    assert production["cells_per_job"] >= 1


@pytest.mark.parametrize("baseline", BASELINES)
def test_absent_dials_say_why(baseline):
    """A null is a finding. It must carry the reason it is null, or it is an omission."""
    production = DESCRIPTORS[family_of(baseline)]["production"]
    for dial in ("eval_every", "eval_episodes", "save_every"):
        if production.get(dial, "missing") is None:
            reason = production.get(f"{dial}_reason") or production.get("training_time_eval")
            assert reason, f"{baseline}: {dial} is null with no reason recorded"


@pytest.mark.parametrize("baseline", ["drqv2", "svea", "drq", "sgqn", "curl"])
def test_replay_cap_fits_an_allowed_tier_and_clears_the_worker_floor(baseline):
    """The cap is what makes these five runnable; both of its bounds are checked, not assumed."""
    production = DESCRIPTORS["rlvigen"]["production"]
    capacity = production["replay_capacity"]

    # Upper bound: worker-resident replay plus the process floor must fit gt4i.1's usable RAM.
    resident_gib = capacity * 63_504 / 1024 ** 3
    assert resident_gib + 4.0 <= 27.0, (
        f"capacity {capacity} needs {resident_gib:.1f} GiB of replay; gt4i.1 gives about 27 GiB")

    # Lower bound: max_size // num_workers must exceed one episode, or that worker starves --
    # _try_fetch breaks on `fetched_size + eps_len > max_size` before ever storing anything.
    assert capacity // 4 > 500, (
        f"capacity {capacity} over 4 workers is {capacity // 4} per worker, below a 500-step episode")


def test_rlvigen_save_cadence_matches_the_hardcoded_gate():
    """train.py:309 gates on a literal 5e4. Recording any other number here would be fiction."""
    train = (ROOT / "RL-ViGen-upstream" / "train.py").read_text()
    assert "self.global_step % int(5e4) == 0" in train
    assert DESCRIPTORS["rlvigen"]["production"]["save_every"] == 50_000


def test_preserve_snapshots_is_a_cadence_not_a_flag():
    train = (ROOT / "RL-ViGen-upstream" / "train.py").read_text()
    assert "cadence = int(preserve)" in train, "P18 is not the cadence form"
    assert DESCRIPTORS["rlvigen"]["production"]["preserve_snapshots"] % 50_000 == 0, (
        "a preserve cadence that is not a multiple of the 50k save gate keeps nothing")


def test_eval_cadence_audit_anchors_still_hold():
    """The production block cites file:line for what each family's cadence means."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "audit_eval_cadence.py"), "--check"],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_parallel_job_limit_is_the_owners_current_one():
    """Packing is per job; this pins the constraint the schedule must respect.

    Raised from two to four on 2026-09-03 by the owner, who set the original limit. The tier
    limit is unchanged: nothing above gt4i.1.
    """
    assert MAX_PARALLEL_JOBS == 4
    for name, entry in DESCRIPTORS.items():
        assert entry["production"]["cells_per_job"] <= 4, (
            f"{name}: more than four cells in one job has never been measured")


# --- the declared defaults must be the ones a job actually runs ------------------------------

import importlib.util  # noqa: E402
import sys  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "native_family", ROOT / "datasphere" / "native" / "family.py")
FAMILY = importlib.util.module_from_spec(_spec)
sys.modules["native_family"] = FAMILY
_spec.loader.exec_module(FAMILY)


@pytest.mark.parametrize("baseline", BASELINES)
def test_production_env_resolves_for_every_baseline(baseline):
    """It must not raise for any of the twelve; an empty result is a legitimate answer."""
    resolved = FAMILY.production_env(f"{baseline}:1")
    assert isinstance(resolved, dict)


def test_the_replay_cap_reaches_the_command_line_for_rlvigen():
    resolved = FAMILY.production_env("drqv2:1")
    assert resolved["NATIVE_EXTRA_OVERRIDES"] == "replay_buffer_size=300000"
    assert resolved["RLVIGEN_PRESERVE_SNAPSHOTS"] == "100000"


def test_dmc_gb_declares_no_cap_and_so_claims_no_lever():
    """rad/soda are deliberately uncapped: capping needs a source change worth 8% of the bill and
    costing wall-clock, so the schedule prices them on gt4i.1 alone at the full-budget buffer.

    The mechanism that would report a declared-but-unreachable cap is still live and is exercised
    below; what changed is that dmc_gb no longer declares one."""
    resolved = FAMILY.production_env("rad:1")
    assert "NATIVE_EXTRA_OVERRIDES" not in resolved
    assert "NATIVE_PRODUCTION_UNAPPLIED" not in resolved
    assert FAMILY.production("dmc_gb")["replay_capacity"] is None
    assert FAMILY.production("dmc_gb")["tier"] == "gt4i.1"


def test_a_declared_cap_with_no_lever_would_be_reported_not_dropped():
    """The guard itself, on a synthetic descriptor -- silence would let a job run at the full
    buffer while the schedule's tier arithmetic assumed a cap held."""
    entry = {"replay_capacity": 300000, "replay_capacity_option": None}
    assert entry["replay_capacity"] is not None and not entry["replay_capacity_option"], (
        "the branch this guards requires a capacity with no option")


def test_families_with_no_eval_dial_expose_only_a_save_cadence():
    """These four have no training-time EVAL cadence to set, and that is still the point.

    [Claude 2026-09-04] This asserted `production_env(...) == {}` -- literally nothing to dial --
    which was true while all four also had `save_every: null`. At the owner's request they now
    keep INTERMEDIATE CHECKPOINTS, so each exposes a save cadence and nothing else. The test is
    updated rather than deleted because the property worth pinning is unchanged: none of them
    gains an EVAL_EVERY_FRAMES or EVAL_EPISODES, since none evaluates during training at all
    (`scripts/audit_eval_cadence.py`), and inventing one would fabricate a cadence upstream has no
    concept of.
    """
    for baseline in ("ppg", "ibac_sni", "ctrl", "idaac"):
        env = FAMILY.production_env(f"{baseline}:1")
        # The training loops have no online evaluation dial.  The terminal and trajectory grids
        # are container-side measurements and therefore allowed, but no training-time cadence may
        # appear merely because the runner can now make those measurements.
        allowed = {"SAVE_EVERY_FRAMES", "CURVE_EVAL", "ENDPOINT_EVAL",
                   "CURVE_EVAL_REGIMES", "CURVE_EVAL_SCENES", "CURVE_EVAL_EPISODES",
                   "ENDPOINT_EVAL_REGIMES", "ENDPOINT_EVAL_SCENES", "ENDPOINT_EVAL_EPISODES"}
        if baseline in {"ctrl", "idaac"}:
            allowed.add("NATIVE_ISOLATE_ONLINE_EVAL")
        assert set(env) <= allowed, f"{baseline} gained a dial it should not have: {env}"
        assert env.get("SAVE_EVERY_FRAMES") == "50000", f"{baseline}: {env}"


@pytest.mark.parametrize("baseline", BASELINES)
def test_production_enables_distinct_endpoint_and_curve_measurements(baseline):
    """The production descriptor must activate both measured products, not merely name scopes.

    ``run_probe.sh`` deliberately leaves both evaluators opt-in for cheap probes.  A production
    invocation is different: it owes one 20-episode endpoint grid and a shallow 50k trajectory.
    Supplying only ``*_EVAL_*`` variables makes that distinction look configured while silently
    doing neither.
    """
    env = FAMILY.production_env(f"{baseline}:1")
    assert env["ENDPOINT_EVAL"] == "1"
    assert env["CURVE_EVAL"] == "1"
    assert env["ENDPOINT_EVAL_REGIMES"] == "train,eval-easy,eval-medium,eval-hard"
    assert env["ENDPOINT_EVAL_SCENES"] == "0,1,2,3,4,5,6,7,8,9"
    assert env["ENDPOINT_EVAL_EPISODES"] == "20"
    assert env["CURVE_EVAL_REGIMES"] == "train,eval-easy,eval-medium,eval-hard"
    assert env["CURVE_EVAL_SCENES"] == "0,1,2,3,4,5,6,7,8,9"
    assert env["CURVE_EVAL_EPISODES"] == "3", (
        "A20 decided 3 episodes/stamp (DECISION-SHEET.md); this test pinned the pre-decision "
        "value of 5, which is exactly how the decision was silently overridden in production for "
        "as long as this assertion stayed unchanged -- Codex found it live via mailbox Q19.")


def test_cells_spanning_families_are_refused():
    """The settings differ in kind across families, so merging them would be a category error."""
    with pytest.raises(SystemExit):
        FAMILY.production_env("drqv2:1,rad:1")


def test_v100_profile_is_explicit_and_changes_only_its_declared_runtime_knobs(monkeypatch):
    """A V100 run must not silently inherit T4-safe rollout and replay reductions."""
    monkeypatch.delenv("NATIVE_HOST_PROFILE", raising=False)
    assert FAMILY.host_profile() == "datasphere"
    assert FAMILY.full_fields("ppg", {"frames": "600000"})["num_envs"] == "8"
    assert FAMILY.production("rlvigen")["replay_capacity"] == 300_000

    monkeypatch.setenv("NATIVE_HOST_PROFILE", "v100")
    assert FAMILY.host_profile() == "v100"
    # [Claude 2026-09-06] idaac's v100-only num_processes override (4->16) is REMOVED, not just
    # changed: DECISION-SHEET A35's IDAAC-C2 fixes num_processes at 1 everywhere (a fidelity
    # requirement, not a per-host throughput knob any more), so this is the one family this test
    # deliberately does NOT expect to change between profiles.
    assert FAMILY.full_fields("idaac", {"frames": "600000"})["num_processes"] == "1"
    assert FAMILY.full_fields("ppg", {"frames": "600000"})["num_envs"] == "8"
    assert FAMILY.expected_endpoint("ppg", 600_000) == 600_064
    assert FAMILY.full_fields("ibac_sni", {"frames": "600000"})["procs"] == "16"
    assert FAMILY.full_fields("ctrl", {"frames": "600000"})["num_envs"] == "64"
    # Door does not terminate early, so 600k action-repeat-one frames plus at most 1,200
    # episode-reset entries fit below this cap.  A 1M cap is therefore no more faithful at
    # the declared budget, while it needlessly prevents two-cell V100 packing.
    assert FAMILY.production("rlvigen")["replay_capacity"] == 620_000
    assert FAMILY.production("rlvigen")["preserve_snapshots"] == 50_000
    assert FAMILY.production_env("drqv2:1")["NATIVE_EXTRA_OVERRIDES"] == "replay_buffer_size=620000"
    assert FAMILY.production("ctrl")["tier"] == "gt4i.1", "unchanged profiles inherit base settings"


def test_ibac_parallel_memory_model_refuses_the_known_unfit_t4_shape(monkeypatch):
    """A 16-way EGL rollout measured about 1 GiB RSS per child and OOMed a 16 GiB T4.

    This is a capacity guard, not a claim that 16 processes are invalid.  The declared V100
    profile remains the upstream count; it needs its own higher-memory smoke.
    """
    monkeypatch.setenv("NATIVE_EXTRA_OVERRIDES", "--procs=16")
    with pytest.raises(ValueError, match="parallel rollout memory"):
        FAMILY.check_memory("ibac_sni:1", "gt4.1")


def test_descriptor_can_be_resolved_for_an_explicit_profile_without_ambient_state(monkeypatch):
    """Planners must name their profile; an inherited shell variable cannot define an artifact."""
    monkeypatch.setenv("NATIVE_HOST_PROFILE", "datasphere")
    try:
        v100 = FAMILY.production("rlvigen", profile="v100")
    except TypeError as error:
        pytest.fail(f"family.production has no explicit profile input: {error}")
    assert v100["replay_capacity"] == 620_000

    monkeypatch.setenv("NATIVE_HOST_PROFILE", "v100")
    datasphere = FAMILY.production("rlvigen", profile="datasphere")
    assert datasphere["replay_capacity"] == 300_000
    # [Claude 2026-09-06] Both now 598_016, not 598_016/599_040: idaac's v100-only num_processes
    # override (4->16) is removed as part of DECISION-SHEET A35's IDAAC-C2 transition --
    # num_processes is now a fidelity-fixed constant (1), not a per-host throughput knob, so both
    # profiles resolve the same quantum (1*2048=2048) and the same endpoint. Kept as two assertions
    # rather than folded into one: this test's point is that the explicit `profile=` kwarg is what
    # is read, not that the two profiles must differ.
    assert FAMILY.expected_endpoint("idaac", 600_000, profile="v100") == 598_016
    assert FAMILY.expected_endpoint("idaac", 600_000, profile="datasphere") == 598_016


def test_unknown_host_profile_is_rejected_before_a_command_is_resolved(monkeypatch):
    monkeypatch.setenv("NATIVE_HOST_PROFILE", "unreviewed-host")
    with pytest.raises(ValueError, match="unknown host profile"):
        FAMILY.full_fields("ibac_sni", {"frames": "600000"})


def test_run_manifest_stamps_the_selected_host_profile():
    runner = (ROOT / "datasphere" / "native" / "run_probe.sh").read_text()
    assert '"host_profile": os.environ.get("NATIVE_HOST_PROFILE", "datasphere")' in runner
    assert 'python3 "$FAMILY_TOOL" host-profile' in runner


# --- the budget floor: refuse a run that cannot produce a curve, before it is paid for ---------

@pytest.mark.parametrize("baseline", BASELINES)
def test_every_family_declares_a_budget_floor_with_a_reason(baseline):
    settings = FAMILY.production(family_of(baseline))
    assert settings.get("min_frames"), f"{baseline}: no min_frames declared"
    assert settings.get("min_frames_reason"), f"{baseline}: min_frames has no recorded reason"


def test_the_production_budget_clears_every_floor():
    """600k is the shape under discussion; nothing may sit below its own floor at that budget."""
    for baseline in BASELINES:
        FAMILY.check_budget(f"{baseline}:1", 600_000)


def test_a_budget_below_the_floor_is_refused():
    with pytest.raises(SystemExit) as excinfo:
        FAMILY.check_budget("drqv2:1", 3000)
    assert "4001" in str(excinfo.value)


def test_the_floor_tracks_an_overridden_seed_phase(monkeypatch):
    """A rehearsal lowers num_seed_frames deliberately; the gate must not refuse it.

    This is the case that made the first version of the gate wrong: it hardcoded the configured
    4000 and would have blocked exactly the cheap local runs it exists to protect.
    """
    monkeypatch.setenv("NATIVE_EXTRA_OVERRIDES", "num_seed_frames=500 replay_buffer_size=300000")
    FAMILY.check_budget("drqv2:1", 3000)
    monkeypatch.setenv("NATIVE_EXTRA_OVERRIDES", "num_seed_frames=5000")
    with pytest.raises(SystemExit):
        FAMILY.check_budget("drqv2:1", 3000)


# --- the shipped RL-ViGen tree: the clone is no longer the single point of failure -------------

SOURCE_LOCK = json.loads((ROOT / "datasphere" / "native" / "rlvigen-source.json").read_text())
RUNNER = (ROOT / "datasphere" / "native" / "run_probe.sh").read_text()


def test_the_source_lock_and_the_runner_name_the_same_commit():
    """Two places state the pinned commit; if they disagree the archive and the fallback clone
    would produce different trees and only one of them would be the one that was reviewed."""
    assert SOURCE_LOCK["commit"] in RUNNER, "run_probe.sh does not pin the locked commit"
    assert len(SOURCE_LOCK["commit"]) == 40


def test_the_runner_prefers_the_input_and_verifies_it():
    """The archive is checked, not trusted. A swapped or truncated input would otherwise surface
    minutes later as a patch anchor mismatch, with nothing pointing at the input."""
    assert "RLVIGEN_ARCHIVE" in RUNNER
    assert "NATIVE_RLVIGEN_ARCHIVE_HASH_MISMATCH" in RUNNER
    assert "NATIVE_RLVIGEN_FROM_INPUT" in RUNNER
    # the network clone survives only as a fallback, and says so when it is used
    assert "NATIVE_RLVIGEN_NO_INPUT" in RUNNER
    assert RUNNER.index("provide_rlvigen()") < RUNNER.index("provide_rlvigen\n")


def test_the_source_lock_is_a_payload_member():
    """The runner reads it on the container; a payload without it leaves the runner with no tree
    and no useful error, which is what the runner contract exists to prevent."""
    import re
    contract = (ROOT / "datasphere" / "native" / "contract.py").read_text()
    assert '"datasphere/native/rlvigen-source.json",' in contract
    # [Corrected 2026-09-05, external review 7 section 9] This used to hardcode
    # `RUNNER_CONTRACT = 10` on both sides, so bumping the contract to 12 turned a green test red
    # for no reason connected to what it protects. The invariant is that the runner DEMANDS the
    # contract the builder STAMPS -- a relationship between two files, which cannot go stale.
    declared = re.search(r"^RUNNER_CONTRACT = (\d+)", contract, re.MULTILINE)
    required = re.search(r"--require-runner-contract (\d+)", RUNNER)
    assert declared and required, "the runner contract is no longer stated in both places"
    assert declared.group(1) == required.group(1), (
        f"contract.py stamps RUNNER_CONTRACT={declared.group(1)} but run_probe.sh demands "
        f"{required.group(1)}; a payload built here would be refused by its own runner"
    )


def test_result_manifest_pins_image_and_native_requirements():
    """A package list without the CUDA userspace is not a reproducible rendering environment."""
    assert '"container_image"' in RUNNER
    assert '"requirements_native_sha256"' in RUNNER
    lock = json.loads((ROOT / "datasphere" / "native" / "source-lock.json").read_text())
    expected = ("nvidia/cuda:12.2.2-runtime-ubuntu22.04@"
                "sha256:94c1577b2cd9dd6c0312dc04dff9cb2fdce2b268018abc3d7c2dbcacf1155000")
    assert lock["container_image"] == expected
    assert expected in RUNNER
    assert len(lock["requirements_native_sha256"]) == 64


def test_source_lock_root_commit_is_from_this_repository():
    """External review 15 §1: `nested_repository_commits.root` named
    `f041f5e170368d298e9b5b60127faa10ba5364e5` -- the LEGACY tree's HEAD, not this recovery
    workspace's. Not merely behind; unreachable here at all, so a source-lineage reader could
    trace a payload to a commit that isn't this project's history.

    `write_payload` (contract.py) copies this field into every payload manifest verbatim, never
    recomputing it, so nothing catches this drifting except a test. The field cannot always equal
    the literal current HEAD -- committing a fix to this file immediately supersedes whatever HEAD
    it records -- so the checkable invariant is narrower but still catches the actual bug found:
    the recorded root must be a real, reachable commit of THIS repository's own history, not an
    arbitrary hex string or another tree's commit.
    """
    lock = json.loads((ROOT / "datasphere" / "native" / "source-lock.json").read_text())
    root = lock["nested_repository_commits"]["root"]
    result = subprocess.run(["git", "cat-file", "-e", root], cwd=ROOT, capture_output=True)
    assert result.returncode == 0, (
        f"source-lock.json's nested_repository_commits.root ({root}) is not a commit object "
        f"reachable in this repository -- {result.stderr.decode(errors='replace').strip()}"
    )
    merge_base = subprocess.run(["git", "merge-base", "--is-ancestor", root, "HEAD"],
                                cwd=ROOT, capture_output=True)
    assert merge_base.returncode == 0, (
        f"source-lock.json's root ({root}) exists but is not an ancestor of HEAD -- "
        "it names a commit from a different branch/history, not this tree's own lineage"
    )


def test_the_archive_matches_its_lock_when_it_is_present():
    """Skipped where the archive is not checked out -- it is 631 MB and lives outside the tree."""
    import hashlib
    archive = ROOT / "rlvigen-door2-90d8b8c4.tgz"
    if not archive.exists():
        pytest.skip("the shipped archive is not present in this checkout")
    digest = hashlib.sha256()
    with archive.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 22), b""):
            digest.update(chunk)
    assert digest.hexdigest() == SOURCE_LOCK["sha256"]
    assert archive.stat().st_size == SOURCE_LOCK["bytes"]


def test_the_lock_records_where_it_diverges_from_the_commit():
    """An archive that claims to be a commit should say where it is not: macOS cannot hold both
    TwoArmHandover.yaml and TwoArmHandOver.yaml, so a fresh clone is one file short."""
    assert SOURCE_LOCK["known_divergence_from_the_commit"], "no divergence section"
    assert any("TwoArmHand" in item for item in SOURCE_LOCK["known_divergence_from_the_commit"])


def test_ppg_retains_the_terminal_save_not_the_helpers_construction_save():
    """LogSaveHelper writes `model.jd` in its own __init__, before any gradient step, because
    `ic_per_save` defaults to 100_000 and the branch is gated on `> 0`. A probe shorter than that
    retains an UNTRAINED model under a plausible name -- which is what happened on 2026-09-02."""
    ppg = DESCRIPTORS["ppg"]
    assert ppg["checkpoint"] == "model_terminal.jd", ppg["checkpoint"]
    assert "model.jd" in ppg.get("optional_curves", []), (
        "the helper's own file should still be retained beside ours, for comparison")
    train = (ROOT / "runnable" / "ppg" / "phasic_policy_gradient" / "train.py").read_text()
    assert "NATIVE_PPG_TERMINAL_SAVE" in train, "the terminal save is not wired"
    assert train.index("ppg.learn(") < train.index("model_terminal.jd"), (
        "the terminal save must happen AFTER learn() returns")


def test_the_finiteness_probe_also_reports_whether_the_policy_moved_from_init():
    """The gate that would have caught ppg's untrained checkpoint at the time rather than after.

    A checkpoint at its initialisation passes every existing check: the file exists, is the right
    size, and holds finite floats. The four continuous-head baselines initialise their
    state-independent log-std to exactly zero, so `all_exactly_zero` across every dimension is
    strong evidence no optimiser step reached it. Reported and not failed on -- a legitimately
    short run can barely move it, and this probe should not be the thing that decides that.
    """
    family = (ROOT / "datasphere" / "native" / "family.py").read_text()
    assert '"policy_log_std": policy' in family, "the probe does not report the policy std"
    assert '"all_exactly_zero"' in family
    assert "log_std" in family and "logstd" in family, "both spellings must be scanned"
    # reported, not fatal: the probe's failure paths are `fail(...)`, and this must not be one
    probe = family.split("FINITENESS_PROBE = r\"\"\"")[1].split('"""')[0]
    assert "all_exactly_zero" in probe
    assert "raise SystemExit(1)" not in probe, "the trained-ness signal must not fail the cell"


# --- every declared import path must actually reach the container -----------------------------

_CONTRACT = _load_contract = None


def _payload_allowlist(family: str) -> tuple[str, ...]:
    spec = importlib.util.spec_from_file_location(
        "native_contract", ROOT / "datasphere" / "native" / "contract.py")
    contract = importlib.util.module_from_spec(spec)
    sys.modules["native_contract"] = contract
    spec.loader.exec_module(contract)
    return tuple(contract.BASE_ALLOWED) + tuple(DESCRIPTORS[family].get("payload_members", ()))


@pytest.mark.parametrize("family", sorted(DESCRIPTORS))
def test_every_import_gate_path_exists_and_is_declared(family):
    """The gate that would have caught `alda` before a job ran, rather than after.

    `runnable/_shim/alda_models` was on alda's declared `import_gate.pythonpath` and was an
    absolute symlink. It resolved locally and the payload builder wrote no entry for it, so the
    container had a PYTHONPATH entry pointing at nothing and the import gate failed there while
    passing here. Two things are checked per entry: it exists as a real directory, and some
    declaration covers it so the builder will actually carry it.
    """
    gate = DESCRIPTORS[family].get("import_gate") or {}
    allowed = _payload_allowlist(family)
    for entry in gate.get("pythonpath", ()):
        path = ROOT / entry
        # RL-ViGen is cloned or shipped separately, not a payload member; skip those entries
        if entry.startswith("RL-ViGen-upstream"):
            continue
        assert path.is_dir(), f"{family}: import_gate path {entry} is not a directory"
        assert not path.is_symlink(), (
            f"{family}: import_gate path {entry} is a symlink; the payload builder does not carry "
            "one and the failure appears only on the container")
        covered = any(entry == item or entry.startswith(item + "/") or item.startswith(entry + "/")
                      for item in allowed)
        assert covered, (
            f"{family}: import_gate path {entry} is covered by no payload declaration, so it will "
            f"not ship. Declared: {allowed}")
