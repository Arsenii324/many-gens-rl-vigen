"""The Places365 train branch must be internally consistent end to end.

A22 decided the production overlay comes from the upstream TRAIN split, because the overlay
distribution IS the augmentation mechanism for svea, sgqn and soda. The runner then:

  - extracted with `-xzf`, which forces gzip, while the canonical asset
    `places365standard_easyformat.tar` is not gzipped;
  - assumed a flat `train/` layout, while that archive unpacks as `places365_standard/train`;
  - and, after configuring the loader for `$places_split`, asserted the loader root equalled a
    HARDCODED `.../val`.

So the decided production value could not run: the loader correctly resolved to the train root and
the check then failed it. Every one of these is invisible for the other nine baselines, whose
`cells_need_places365` is false and who never enter the block at all.

Found by external review 24. Checked as source text because the block runs only inside the
container, against a ~24 GB asset.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUN_PROBE = ROOT / "datasphere" / "native" / "run_probe.sh"


def _places_block() -> str:
    """Exactly the Places365 provisioning block, not a fixed-size window past it."""
    text = RUN_PROBE.read_text()
    start = text.index('if cells_need_places365 "$cells"; then')
    end = text.index("BLOCKED_FAMILIES=", start)
    return text[start:end]


def test_extraction_does_not_force_gzip():
    block = _places_block()
    # The word appears in the explanatory comment; check the executed command.
    assert "tar --no-same-owner -xzf" not in block, (
        "the canonical production asset places365standard_easyformat.tar is NOT gzipped; -xzf "
        "refuses it. -xf reads either, since both tar implementations detect compression")
    assert re.search(r"tar --no-same-owner -xf", block)


def test_the_final_assertion_names_the_configured_partition():
    block = _places_block()
    assert '"$dataset_root/places365_standard/$places_split"' in block, (
        "the runtime loader check must assert the partition that was actually configured; "
        "hardcoding val makes it contradict every train-split run")
    assert '- "$dataset_root/places365_standard/val" <<' not in block


def test_both_train_layouts_are_accepted_and_a_missing_one_refuses():
    block = _places_block()
    assert '"$asset_dir/places365_standard/train"' in block, "canonical easyformat layout"
    assert '"$asset_dir/train"' in block, "flat probe-fixture layout"
    assert "REFUSING: NATIVE_PLACES365_SPLIT=train" in block, (
        "a train split that is absent from the archive must refuse, not silently link a path "
        "that does not exist")


def test_production_still_refuses_the_val_split_without_an_explicit_deviation():
    """The A22 guard itself must survive these repairs."""
    block = _places_block()
    assert "NATIVE_PLACES365_ACCEPT_VAL" in block
    assert "REFUSING: production scale with Places365 split" in block
