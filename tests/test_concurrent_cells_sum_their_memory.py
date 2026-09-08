"""Concurrent cells' peaks coexist, so the memory preflight must ADD them.

`check_memory` asks "does ONE cell of this family fit". That is the right question for the default
execution path -- `run_cell_list` runs cells one after another -- and silently wrong under
`NATIVE_CONCURRENT=1`, where it dispatches every cell with `&` and waits, so the peaks are
simultaneous.

The pre-existing packing guard did not cover this. It refuses to pack when a figure is ESTIMATED,
which catches `ctrl`'s extrapolated 54.28 GiB, and says nothing about families whose figures are
MEASURED. Two `rlvigen` cells are measured, so `NATIVE_CONCURRENT=1` with
`drqv2:101,drqv2:102,drqv2:103` passed every check at ~40.8 GiB each while needing ~122 GiB -- on a
125 GB host shared with about twenty other people, where exhausting RAM evicts their processes.

These tests drive the real `check_memory` against the real descriptors. No mock: the point is the
arithmetic on the numbers we would actually run with.
"""
from __future__ import annotations

import os
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "datasphere" / "native"))

import family as family_mod  # noqa: E402


def _check(cells: str, concurrent: bool, monkeypatch):
    monkeypatch.setenv("NATIVE_HOST_PROFILE", "v100")
    if concurrent:
        monkeypatch.setenv("NATIVE_CONCURRENT", "1")
    else:
        monkeypatch.delenv("NATIVE_CONCURRENT", raising=False)
    return family_mod.check_memory(cells, "v100", frames=600000)


def test_one_cell_fits_either_way(monkeypatch):
    _check("drqv2:101", False, monkeypatch)
    _check("drqv2:101", True, monkeypatch)


def test_sequential_cells_are_not_summed(monkeypatch):
    """Three cells run one at a time peak at one cell. Summing here would refuse valid work."""
    _check("drqv2:101,drqv2:102,drqv2:103", False, monkeypatch)


def test_concurrent_cells_are_summed_and_refused(monkeypatch):
    with pytest.raises(Exception) as caught:
        _check("drqv2:101,drqv2:102,drqv2:103", True, monkeypatch)
    message = str(caught.value)
    assert "CONCURRENTLY" in message, message
    assert "coexist" in message, message
    # The refusal must carry the arithmetic, not just a verdict: an operator deciding whether to
    # drop a cell needs the per-cell figures.
    assert "Breakdown" in message and "drqv2:101" in message, message


def test_the_refusal_names_the_way_out(monkeypatch):
    """A guard that blocks without saying what to do instead gets overridden blindly."""
    with pytest.raises(Exception) as caught:
        _check("drqv2:101,drqv2:102,drqv2:103", True, monkeypatch)
    assert "sequentially" in str(caught.value), str(caught.value)
