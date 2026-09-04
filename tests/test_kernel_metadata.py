"""Kaggle kernel metadata must pin the two things that are silently wrong by default.

Both are lessons this project already paid for once and wrote down in
`docs/RUNNABLE-ORIGINALS.md`, and neither was enforced by anything until now.

**`machine_shape`.** `enable_gpu: true` on its own does not mean "a GPU that works". It
provisions Kaggle's default accelerator, a Tesla **P100** — sm_60, Pascal, no tensor cores —
which Kaggle's own preinstalled `torch 2.10.0+cu128` does not support at all. The run does not
fall back or warn; it fails at the first kernel launch, remotely, after the queue wait. So
`machine_shape` is not optional, and the default is not merely slower but unusable.

**`is_private`.** This is unpublished lab work. A Kaggle kernel defaults to public, and a kernel
that has been public is not made unpublished by later flipping the flag.

Neither belongs in prose alone: a metadata file is edited far more often than a document is
re-read, and `enable_gpu: true` looks complete on its own to anyone who has not hit the P100.
"""
from __future__ import annotations

import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
METADATA = sorted((ROOT / "compute").glob("*/kernel-metadata.json"))

# Accelerators this project is willing to be scheduled on. T4 is what the workspace actually
# uses; the point of the list is that anything absent from it -- P100 above all -- must be an
# explicit decision by a person, not a default Kaggle picked.
ALLOWED_SHAPES = {"NvidiaTeslaT4", "NvidiaTeslaP100", "NvidiaTeslaV100", "NvidiaTeslaA100",
                  "NvidiaTeslaT4x2", "TpuVmV38"}


def test_there_is_at_least_one_kernel_to_check():
    """A checker that passes on an empty input is not a checker.

    If `compute/*/kernel-metadata.json` ever stops matching, every test below would vacuously
    pass and this file would report green while checking nothing.
    """
    assert METADATA, ("no compute/*/kernel-metadata.json found -- either the layout moved or "
                      "this file is now checking nothing while reporting success")


@pytest.mark.parametrize("path", METADATA, ids=lambda p: p.parent.name)
def test_gpu_kernels_pin_a_machine_shape(path: pathlib.Path):
    meta = json.loads(path.read_text())
    if not meta.get("enable_gpu"):
        pytest.skip(f"{path.parent.name} requests no GPU")
    shape = meta.get("machine_shape")
    assert shape, (
        f"{path.parent.name} sets enable_gpu without machine_shape. Kaggle will schedule this on "
        "its default accelerator, a Tesla P100 (sm_60), which its own torch build does not "
        "support -- the run fails remotely at the first kernel launch. Pin NvidiaTeslaT4.")
    assert shape in ALLOWED_SHAPES, (
        f"{path.parent.name} asks for machine_shape={shape!r}, which is not one this project "
        f"has decided on. Known-good: {sorted(ALLOWED_SHAPES)}. If this is deliberate, add it "
        "to ALLOWED_SHAPES with a reason rather than loosening the check.")


@pytest.mark.parametrize("path", METADATA, ids=lambda p: p.parent.name)
def test_kernels_are_private(path: pathlib.Path):
    """Private by default, because this is unpublished lab work.

    Stated as a standing constraint by the owner, and irreversible in the direction that matters:
    a kernel that was public for ten minutes has been published.
    """
    meta = json.loads(path.read_text())
    assert meta.get("is_private") is True, (
        f"{path.parent.name} has is_private={meta.get('is_private')!r}. Kaggle kernels default "
        "to public and this is unpublished work; flipping the flag afterwards does not un-share "
        "what was already visible.")
