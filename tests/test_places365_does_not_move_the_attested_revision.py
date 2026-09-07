"""Configuring Places365 must not change a hashed evaluator member.

`eval_grid.py` stamps `evaluator_family_code_revision` LIVE, from the unpacked tree inside the
container (its own line ~1412). `configure_places365_val.py` runs before that, and it rewrites the
overlay loader -- `RL-ViGen-upstream/utils.py` for the rlvigen flavour,
`runnable/dmc_gb/src/augmentations.py` for dmc_gb. Both are hashed members of their family's
runtime closure.

So every svea/sgqn/soda record carried a revision that could never equal the one
`production_gates.py` computes from our own tree: three of the twelve baselines were unattestable
by construction, and the gate meant to certify them would have rejected them mid-campaign. It had
never been hit because every attestation so far went through drqv2 or rad, neither of which enters
the Places365 block at all (`family.py needs-places365` is false for both).

Measured before the fix, on the dmc_gb flavour: the family code revision moved
6243bd9e903cd8bb -> df01becb3f36a7d4.

The repair was to bake the fallback hardening into the source (apply_patches.py P21 for rlvigen,
the clone patch for dmc_gb) so that the runtime step finds it already applied and changes nothing.
This test holds that property: it runs the real configure step against a real copy of the tree and
requires the revision to be unchanged.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "datasphere" / "native"))

from evaluator_identity import (  # noqa: E402
    CODE_MEMBERS, evaluator_family_code_revision,
)

IGNORE = shutil.ignore_patterns(".git", "__pycache__", "data", "logs", "results", ".DS_Store")


def _fake_root(tmp_path: pathlib.Path) -> pathlib.Path:
    """A tree carrying exactly what the dmc_gb revision hashes."""
    for member in CODE_MEMBERS + ("datasphere/native/families.json",):
        target = tmp_path / member
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / member, target)
    shutil.copytree(ROOT / "runnable/dmc_gb", tmp_path / "runnable/dmc_gb",
                    symlinks=True, ignore=IGNORE)
    vgb = "RL-ViGen-upstream/envs/robosuiteVGB"
    shutil.copytree(ROOT / vgb / "robosuitevgb", tmp_path / vgb / "robosuitevgb",
                    symlinks=True, ignore=IGNORE)
    (tmp_path / vgb / "cfg").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / vgb / "cfg/robo_config.yaml", tmp_path / vgb / "cfg/robo_config.yaml")
    return tmp_path


@pytest.mark.parametrize("split", ["train"])
def test_configuring_places365_leaves_the_dmc_gb_revision_unchanged(tmp_path, split):
    if not (ROOT / "runnable" / "dmc_gb").is_dir():
        pytest.skip("runnable/dmc_gb absent; run setup/bootstrap_sources.py --family dmc_gb")
    root = _fake_root(tmp_path)
    before = evaluator_family_code_revision(root, "dmc_gb")

    dataset_root = root / "ds"
    (dataset_root / "places365_standard" / split).mkdir(parents=True)
    configure = ROOT / "datasphere" / "native" / "configure_places365_val.py"
    common = [sys.executable, str(configure), "--repo", str(root / "runnable/dmc_gb"),
              "--dataset-root", str(dataset_root), "--flavor", "dmc_gb", "--split", split]

    applied = subprocess.run(common, capture_output=True, text=True)
    assert applied.returncode == 0, applied.stderr

    # `--check` must also pass, or the runner refuses after configuring successfully.
    checked = subprocess.run(common + ["--check"], capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr

    after = evaluator_family_code_revision(root, "dmc_gb")
    assert after == before, (
        "configuring Places365 moved a hashed evaluator member, so records from svea/sgqn/soda "
        "can never match the revision production_gates.py computes locally. The loader hardening "
        "must be applied in the SOURCE (apply_patches.py P21 / the dmc_gb clone patch), not at "
        "runtime")


def test_the_hardening_is_present_in_both_loaders_as_source():
    """If it is in the source, the runtime step has nothing left to rewrite."""
    for relative in ("RL-ViGen-upstream/utils.py", "runnable/dmc_gb/src/augmentations.py"):
        path = ROOT / relative
        if not path.is_file():
            pytest.skip(f"{relative} absent")
        text = path.read_text()
        assert "fallback disabled" in text, (
            f"{relative} still carries upstream's silent fallback. A misprovisioned host would "
            "then overlay from the dataset ROOT instead of the requested partition -- a "
            "learning-affecting fault that looks like a successful run for svea/sgqn/soda")
        assert "falling back to" not in text
