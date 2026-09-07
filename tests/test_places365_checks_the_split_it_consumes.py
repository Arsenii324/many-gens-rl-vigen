"""The Places365 integrity check must describe the split the run actually consumes.

`check-asset` validated `$asset_dir/val/images` unconditionally, even under
`NATIVE_PLACES365_SPLIT=train`. External review 24 found exactly this defect in the
loader-selection assertion and it was fixed there; the same mistake one call earlier survived,
because nothing executed the train path at production layout.

Both consequences are invisible below production scale, which is why they need a test rather than
a reading:

  - the canary `bt1f8b5gb39jgadqngke` passed a check over 36,500 VAL images while training on the
    fixture's 1,000 TRAIN ones -- the split that IS the mechanism for svea/sgqn/soda was the one
    never checked;
  - `places365standard_easyformat.tar` carries `places365_standard/<split>/<class>/` and no flat
    `val/images`, so the first real production cell would have failed at the guard after paying
    the 21 GB upload.

This EXECUTES the shipped resolution block out of `run_probe.sh` rather than restating it. A test
that re-implements the logic it checks agrees with itself and with nothing else -- the recurring
shape of every defect this project has had to find twice.
"""
from __future__ import annotations

import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROBE = ROOT / "datasphere" / "native" / "run_probe.sh"

BEGIN = '  places_link_source=""'
END = '  ln -sfn "$places_link_source" "$dataset_root/places365_standard/$places_split"'


def _shipped_block() -> str:
    text = PROBE.read_text()
    start = text.index(BEGIN)
    end = text.index(END) + len(END)
    block = text[start:end]
    # The check-asset call needs a python3 and the repo on the path; the resolution above it is
    # what this test exercises, so the call itself is stubbed out by the harness, not removed here.
    return block


def _run(tmp_path: pathlib.Path, layout: str, split: str) -> tuple[int, str]:
    asset = tmp_path / "places365-val"
    if layout == "easyformat":
        for part in ("train", "val"):
            (asset / "places365_standard" / part / "airfield").mkdir(parents=True)
            (asset / "places365_standard" / part / "airfield" / "a.jpg").write_bytes(b"x")
    elif layout == "fixture":
        (asset / "val" / "images").mkdir(parents=True)
        (asset / "val" / "images" / "a.jpg").write_bytes(b"x")
        (asset / "train" / "airfield").mkdir(parents=True)
        (asset / "train" / "airfield" / "a.jpg").write_bytes(b"x")
    elif layout == "val-only":
        (asset / "val" / "images").mkdir(parents=True)
        (asset / "val" / "images" / "a.jpg").write_bytes(b"x")
    root = tmp_path / "places365-root"
    (root / "places365_standard").mkdir(parents=True)

    harness = (
        "set -euo pipefail\n"
        f'asset_dir="{asset}"\n'
        f'dataset_root="{root}"\n'
        f'places_split="{split}"\n'
        # Stub the integrity call so this test measures WHICH path is chosen, not the digest.
        # Argument order is `contract.py check-asset --asset <path> ...`, so the path is $4.
        'export PLACES365_EXPECTED_COUNT=1 PLACES365_EXPECTED_SHA256=deadbeef\n'
        'python3() { echo "CHECKED $4"; }\n'
        + _shipped_block()
        + '\necho "LINKED $(readlink "$dataset_root/places365_standard/$places_split")"\n'
    )
    done = subprocess.run(["bash", "-c", harness], capture_output=True, text=True)
    return done.returncode, done.stdout + done.stderr


def test_train_split_checks_the_train_tree_not_val(tmp_path):
    """The defect itself: split=train must not certify the val images."""
    code, out = _run(tmp_path, "fixture", "train")
    assert code == 0, out
    checked = re.search(r"CHECKED (\S+)", out).group(1)
    assert checked.endswith("/train"), f"checked {checked}, which is not the consumed split"
    assert "val" not in pathlib.Path(checked).name


def test_val_split_still_checks_the_nested_images_directory(tmp_path):
    """Back-compat: every declared val sha256 is computed over `val/images`, so that must not move."""
    code, out = _run(tmp_path, "fixture", "val")
    assert code == 0, out
    checked = re.search(r"CHECKED (\S+)", out).group(1)
    assert checked.endswith("/val/images"), checked


def test_production_easyformat_layout_resolves_for_both_splits(tmp_path):
    """`places365standard_easyformat.tar` has no flat `val/images`; the guard must still resolve."""
    for split in ("train", "val"):
        code, out = _run(tmp_path / split, "easyformat", split)
        assert code == 0, out
        checked = re.search(r"CHECKED (\S+)", out).group(1)
        assert checked.endswith(f"places365_standard/{split}"), checked


def test_a_missing_split_is_refused_loudly(tmp_path):
    """Refuse rather than link a path that does not exist -- the failure must name what it wanted."""
    code, out = _run(tmp_path, "val-only", "train")
    assert code == 3, f"expected refusal exit 3, got {code}: {out}"
    assert "no such split" in out


def test_the_unconditional_val_path_is_gone():
    """The literal defect, so it cannot be reintroduced by an edit that looks unrelated."""
    text = PROBE.read_text()
    assert 'asset_images="$asset_dir/val/images"' not in text, (
        "check-asset is hardcoded to val again; it must follow $places_split")
