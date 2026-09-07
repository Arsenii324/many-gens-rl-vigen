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

Found by external review 24. Originally checked as source text on the reasoning that the block
runs only inside the container against a ~24 GB asset. That reasoning was wrong, and
`tests/test_places365_checks_the_split_it_consumes.py` disproves it by EXECUTING the shipped
resolution against synthetic copies of both real archive layouts. The text assertions below are
kept for the properties that are genuinely textual -- which flag `tar` gets, which partition the
final assertion names -- and the behavioural ones now live in that module.
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


def test_both_layouts_are_accepted_for_whichever_split_is_consumed():
    """Generalised from `train` to `$places_split` on 2026-09-08.

    The literal `.../places365_standard/train` is gone because the resolution now runs for the
    split actually consumed: `check-asset` was validating `val/images` UNCONDITIONALLY, so a
    train-split run certified 36,500 images it never opened and the easyformat archive, which has
    no flat `val/images`, would have failed the guard at production scale.
    """
    block = _places_block()
    assert '"$asset_dir/places365_standard/$places_split"' in block, "canonical easyformat layout"
    assert '"$asset_dir/$places_split"' in block, "flat probe-fixture layout"
    assert "REFUSING: NATIVE_PLACES365_SPLIT=$places_split" in block, (
        "a split that is absent from the archive must refuse, not silently link a path "
        "that does not exist")
    assert 'asset_images="$asset_dir/val/images"' not in block, (
        "the integrity check must follow $places_split, not hardcode val")


def test_production_still_refuses_the_val_split_without_an_explicit_deviation():
    """The A22 guard itself must survive these repairs."""
    block = _places_block()
    assert "NATIVE_PLACES365_ACCEPT_VAL" in block
    assert "REFUSING: production scale with Places365 split" in block
