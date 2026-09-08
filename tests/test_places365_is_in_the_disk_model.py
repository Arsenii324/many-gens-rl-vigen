"""The Places365 corpus must be charged to the baselines that expand it.

External review 27 §4: `disk_requirement_gib()` accounted for replay, checkpoints, retained copies
and the result archive — and not for the ~1.8M-image Places365 train tree that `svea`, `sgqn` and
`soda` copy onto the host and expand beside all of it. A host could therefore pass the project's
own disk preflight and then run out of space during extraction, which is the failure a preflight
exists to make impossible.

The number is a stated estimate, not a measurement, and the code says so. An estimate that is
present and labelled is worth more than a term that is absent: the absent term reports 20.73 GiB
for a soda cell that actually needs about 65.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "datasphere" / "native"))

import family  # noqa: E402


def test_the_three_overlay_baselines_are_charged():
    for baseline in ("svea", "sgqn", "soda"):
        cell = f"{baseline}:1"
        row = family.disk_requirement_gib(cell, 600000)["cells"][cell]
        assert row["places365_gib"] > 0, (
            f"{baseline} expands the Places365 train corpus and is charged nothing for it")


def test_nobody_else_is_charged():
    """Charging a baseline that never opens the dataset would inflate every other preflight."""
    for baseline in ("drqv2", "drq", "curl", "rad", "alda", "idaac", "ppg", "ibac_sni", "ctrl"):
        cell = f"{baseline}:1"
        row = family.disk_requirement_gib(cell, 600000)["cells"][cell]
        assert row["places365_gib"] == 0, f"{baseline} does not use Places365 but is charged for it"


def test_the_charge_actually_moves_the_requirement():
    """A term that rounds away is not a term."""
    soda = family.disk_requirement_gib("soda:1", 600000)["cells"]["soda:1"]
    assert soda["total_gib"] > soda["replay_gib"] + 3 * soda["checkpoints_written_gib"] + 20, (
        "the Places365 term must dominate a soda cell's footprint, as it does in reality")


def test_the_estimate_is_labelled_as_one():
    """It is derived from a published archive size, not measured on the host."""
    text = (ROOT / "datasphere" / "native" / "family.py").read_text()
    assert "PLACES365_TRAIN_GIB" in text
    assert "not a measurement" in text or "NOT a measurement" in text, (
        "an unlabelled estimate in a preflight will eventually be quoted as a measurement")
