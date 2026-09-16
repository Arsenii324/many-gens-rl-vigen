"""Pins register row `ppg-aux-minibatch-geometry`.

Production PPG takes 8 auxiliary minibatches of 8192 samples per aux epoch, because the released
default `aux_mbsize=4` counts (env, segment) pairs and production runs one environment. The
evidence is `results/evidence/ppg-aux-phase-8-minibatches-per-epoch/`.

This test asserts the CURRENT geometry, on purpose. If it fails, something changed the executed
aux phase -- a new `--aux_mbsize` flag, a different environment count, a different split -- and
the register row and the bundle's claim must be re-derived rather than assumed.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import probe_ppg_aux_minibatches as probe  # noqa: E402


def _ppg_constants() -> dict:
    families = json.loads((ROOT / "datasphere" / "native" / "families.json").read_text())
    return families["ppg"]["constants"]


def test_production_takes_eight_aux_minibatches_of_8192_samples():
    constants = _ppg_constants()
    num_envs, nstep = int(constants["num_envs"]), int(constants["nstep"])
    assert (num_envs, nstep) == (1, 2048), f"ppg geometry changed to {num_envs}x{nstep}; re-derive the row"
    count, shapes = probe._count(probe._load(), num_envs, nstep, n_pi=32, aux_mbsize=4)
    assert count == 8 and shapes == [(4, 2048)], (count, shapes)


def test_upstream_single_rank_takes_512_aux_minibatches_of_1024_samples():
    count, shapes = probe._count(probe._load(), 64, 256, n_pi=32, aux_mbsize=4)
    assert count == 512 and shapes == [(4, 256)], (count, shapes)


def test_aux_mbsize_is_still_the_unreachable_default_of_four():
    train = (ROOT / "runnable" / "ppg" / "phasic_policy_gradient" / "train.py").read_text()
    assert re.search(r"^\s*aux_mbsize=4,\s*$", train, re.M), "train.py no longer defaults aux_mbsize to 4"
    assert "'--aux_mbsize'" not in train and '"--aux_mbsize"' not in train, (
        "--aux_mbsize is now a CLI flag; check whether a launcher passes it and re-derive the row")
    for name in ("aux_mbsize", "n_pi", "n_aux_epochs"):
        for path in ("runnable/_launch/ppg_cell.sh", "runnable/_launch/ppg.sh", "datasphere/native/families.json"):
            assert name not in (ROOT / path).read_text(), f"{path} now mentions {name}"


def test_constants_the_probe_assumes_match_the_trainer():
    train = (ROOT / "runnable" / "ppg" / "phasic_policy_gradient" / "train.py").read_text()
    assert re.search(r"^\s*n_pi=32,\s*$", train, re.M)
    assert re.search(r"^\s*n_aux_epochs=6,\s*$", train, re.M)
    assert "parser.add_argument('--n_pi', type=int, default=32)" in train
    assert "parser.add_argument('--n_aux_epochs', type=int, default=6)" in train
