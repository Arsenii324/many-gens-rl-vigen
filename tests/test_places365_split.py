"""The Places365 overlay split is a NAMED production setting, and production refuses the deviation.

DECISION-SHEET A22. The overlay distribution IS the mechanism for svea, sgqn and soda, so drawing
it from the validation partition is learning-affecting. Both arguments for keeping it collapsed:
the "all three share the split so ordering is unaffected" inference does not follow (they consume
overlays through different objectives), and the cost was priced at 105 GB when DMC-GB's own README
points at places365standard_easyformat.tar, ~21 GB at the same 256x256 per-image shape.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER = ROOT / "datasphere" / "native" / "run_probe.sh"
SCRIPT = ROOT / "datasphere" / "native" / "configure_places365_val.py"


def test_the_split_is_a_named_choice_not_an_implicit_one():
    text = SCRIPT.read_text()
    assert '"--split", default="val", choices=("val", "train")' in text
    # train must look for the class directories, not a val/images level
    assert 'dataset_root / "places365_standard" / "train"' in text


def test_train_means_the_absence_of_the_rewrite():
    """Upstream's own default already selects train, so fidelity is NOT patching it."""
    text = SCRIPT.read_text()
    assert "unpatched_signature, patched_signature = patched_signature, unpatched_signature" in text, (
        "for the train split the faithful configuration is to leave use_val=False alone")


def test_a_missing_partition_fails_rather_than_falling_back(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(tmp_path), "--dataset-root", str(tmp_path),
         "--split", "train"],
        capture_output=True, text=True, cwd=str(ROOT))
    assert result.returncode != 0
    assert "train images are absent" in (result.stdout + result.stderr)


def test_production_refuses_the_val_split_unless_it_is_declared():
    runner = RUNNER.read_text()
    assert 'places_split="${NATIVE_PLACES365_SPLIT:-val}"' in runner, "probes keep val"
    guard = runner[runner.index('places_split="${NATIVE_PLACES365_SPLIT'):][:1400]
    assert '"${FRAMES:-10000}" -ge 600000' in guard, "the refusal is production-scale only"
    assert "NATIVE_PLACES365_ACCEPT_VAL" in guard, "and the deviation must be stated, not inherited"
    assert "NATIVE_PLACES365_DECLARED_DEVIATION" in guard, (
        "an accepted deviation must leave a marker in the log")


def test_both_loader_flavours_get_the_same_split():
    """soda loads overlays through dmc_gb's own copy; a split applied to one and not the other
    would have the two families overlaying from different distributions."""
    runner = RUNNER.read_text()
    assert runner.count('--split "$places_split"') == 4, (
        "rlvigen and dmc_gb, each configured and then checked")
