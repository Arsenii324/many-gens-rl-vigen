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
