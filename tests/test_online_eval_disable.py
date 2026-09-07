"""Disabling online evaluation must be EXECUTED, not merely declared.

External review 21, P0. The runner spelled "disabled" as a cadence of 2147483647, and every
affected training loop gates on `step % cadence == 0` -- true at step 0 for any cadence. So
drqv2, svea, drq, sgqn, curl, rad, soda and alda each ran an unrequested initial evaluation while
the manifest recorded online evaluation as off. That evaluation consumes the process-global NumPy
stream Door's placement draws from, so the eight baselines received different training-placement
perturbations -- precisely what disabling it was meant to prevent.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_a_huge_cadence_does_not_disable_anything_at_step_zero():
    """The arithmetic the old mechanism got wrong, pinned so it cannot come back."""
    sys.path.insert(0, str(ROOT / "RL-ViGen-upstream"))
    import utils

    assert utils.Every(2147483647, 1)(0) is True, (
        "0 % anything == 0; a sentinel cadence never disabled step 0")
    assert utils.Every(None, 1)(0) is False, (
        "upstream's own disable path: a None cadence returns False at every step")


def test_rlvigen_disables_through_upstreams_own_none_path():
    result = subprocess.run(
        [sys.executable, str(ROOT / "datasphere" / "native" / "family.py"),
         "production-env", "--cells", "drqv2"],
        capture_output=True, text=True, cwd=str(ROOT))
    assert result.returncode == 0, result.stderr
    assert "NATIVE_DISABLE_ONLINE_EVAL=1" in result.stdout
    assert "NATIVE_ONLINE_EVAL_DISABLED_SPELLING=null" in result.stdout, (
        "rlvigen must disable via a None cadence, not a numeric sentinel")


def test_int_cadence_families_guard_their_call_sites():
    """dmc_gb and alda take the cadence through argparse/a typed spec and cannot express None."""
    for relative, marker in (
            ("runnable/dmc_gb/src/train.py", "step % args.eval_freq == 0"),
            ("runnable/alda/trainers/alda_trainer.py", "step % self.eval_n_steps == 0"),
    ):
        text = (ROOT / relative).read_text()
        index = text.index(marker)
        window = text[index:index + 220]
        assert "NATIVE_DISABLE_ONLINE_EVAL" in window, (
            f"{relative}: the periodic-evaluation call site has no disable guard, so step 0 "
            "evaluates even when the runner asked for no online evaluation")


def test_the_runner_takes_the_spelling_from_the_family():
    text = (ROOT / "datasphere" / "native" / "run_probe.sh").read_text()
    assert "NATIVE_ONLINE_EVAL_DISABLED_SPELLING" in text
    assert "eval_every=2147483647" not in text, "the hardcoded sentinel must be gone"


def test_every_affected_family_declares_a_spelling():
    descriptors = json.loads((ROOT / "datasphere" / "native" / "families.json").read_text())
    affected = [name for name, entry in descriptors.items()
                if not name.startswith("_")
                and (entry.get("production") or {}).get("eval_every") is None
                and any("{eval_every}" in str(option) for option in entry.get("options", []))]
    assert sorted(affected) == ["alda", "dmc_gb", "rlvigen"], affected
    for family in affected:
        spelling = descriptors[family]["production"].get("online_eval_disabled_spelling")
        assert spelling is not None, f"{family} does not declare how it spells 'never evaluate'"


def test_the_gate_reads_the_mechanism_not_the_descriptor():
    sys.path.insert(0, str(ROOT / "scripts"))
    import production_gates

    status, detail = production_gates.gate_online_eval_disable_is_executed()
    assert status == production_gates.PASS, detail


def test_production_host_has_a_memory_preflight(tmp_path):
    """External review 21 #4: the v100 host had no memory check of any kind.

    check_memory knew only DataSphere tiers, was never invoked by run_probe.sh, and resolved the
    BASE descriptor -- so ctrl's 64-environment v100 cell would have been sized by its
    16-environment 13.57 GiB measurement.
    """
    import os

    sys.path.insert(0, str(ROOT / "datasphere" / "native"))
    import family

    previous = os.environ.get("NATIVE_HOST_PROFILE")
    os.environ["NATIVE_HOST_PROFILE"] = "v100"
    try:
        family.check_memory("ctrl", "v100")          # solo fits the 100 GiB reserve
        family.check_memory("drqv2", "v100")
        try:
            family.check_memory("ctrl,ctrl", "v100")
        except (ValueError, SystemExit) as error:
            assert "ESTIMATED" in str(error), str(error)
        else:
            raise AssertionError("packing on an extrapolated memory figure must be refused")
    finally:
        if previous is None:
            os.environ.pop("NATIVE_HOST_PROFILE", None)
        else:
            os.environ["NATIVE_HOST_PROFILE"] = previous

    runner = (ROOT / "datasphere" / "native" / "run_probe.sh").read_text()
    assert "check-memory --cells" in runner, "the runner must run the preflight, not just own one"


def test_memory_preflight_charges_replay_the_way_the_planner_does():
    """External review 21 #12: one memory truth, not two.

    families.json's fixed_peak_gib for rlvigen is 3.33 GiB -- the process, measured at a 10k probe,
    with the worker-resident replay excluded. plan_production has always modelled that replay
    (63,504 B per retained transition); check_memory never did, so it would have certified a
    drqv2 v100 cell at 5.33 GiB while the schedule said 38.78.
    """
    import os

    sys.path.insert(0, str(ROOT / "datasphere" / "native"))
    import family

    settings = family.resolved_descriptor("rlvigen", profile="v100")["production"]
    replay = family._replay_gib("rlvigen", settings, frames=600_000)
    assert 30 < replay < 40, f"620k transitions at 63,504 B is about 36 GiB, got {replay}"

    probe = family._replay_gib("rlvigen", settings, frames=10_000)
    assert probe < 1.0, "a 10k probe holds 10k transitions, not the cap -- budget-dependent"

    assert family._replay_gib("idaac", {}, frames=600_000) == 0.0, "on-policy holds no replay"

    dmc = family._replay_gib("dmc_gb", {}, frames=600_000)
    assert 15 < dmc < 20, "dmc_gb preallocates train_steps at construction"


def test_effective_config_captures_the_variables_that_change_the_experiment():
    """External review 21 #11: the capture list had fallen behind the runner."""
    text = (ROOT / "datasphere" / "native" / "run_probe.sh").read_text()
    body = text.split("python3 -c '", 1)[1].split("' > \"$cell_out/effective_config.json\"", 1)[0]
    import json
    import os as _os

    env = dict(_os.environ)
    env.update({
        "NATIVE_ISOLATE_ONLINE_EVAL": "1",
        "NATIVE_ONLINE_EVAL_DISABLED_SPELLING": "null",
        "ENDPOINT_EVAL_SCENES": "0,1,2",
        "CURVE_EVAL_EPISODES": "3",
        "OFFLINE_EVAL_REGIMES": "train",
        "WANDB_API_KEY": "secret-must-not-appear",
    })
    result = subprocess.run([sys.executable, "-c", body], input=b"", capture_output=True, env=env)
    captured = json.loads(result.stdout)["runner_environment"]
    for name in ("NATIVE_ISOLATE_ONLINE_EVAL", "NATIVE_ONLINE_EVAL_DISABLED_SPELLING",
                 "ENDPOINT_EVAL_SCENES", "CURVE_EVAL_EPISODES", "OFFLINE_EVAL_REGIMES"):
        assert name in captured, f"{name} changes the experiment and must be stamped"
    assert not any("secret" in str(value) for value in captured.values())
