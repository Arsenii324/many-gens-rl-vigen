"""P14: `train.py`'s evaluation sweeps the certified scenes and measures both regimes.

One patch closing two register entries, because it is one edit to one loop: [C45] the protocol
declares ten evaluation scenes and the training loop evaluated scene 0 forever, and [C43] nothing
built a train-regime denominator, so retention was not computable from a training run at all.

Verified live 2026-08-19 before these assertions were written: a `drqv2` run at
`num_eval_episodes=10` built **24** environments — two at startup plus two eval points of ten
eval-easy scenes and one train-regime env — and produced `train_regime_reward` 0.8525 beside a
ten-scene `episode_reward` of 0.8718. These tests hold that shape; they do not re-establish it.

The assertions are on the vendored tree because that is what a re-clone silently reverts.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
TRAIN = ROOT / "RL-ViGen-upstream" / "train.py"
sys.path.insert(0, str(ROOT))

pytestmark = pytest.mark.skipif(not TRAIN.exists(), reason="RL-ViGen-upstream clone absent")


def src() -> str:
    return TRAIN.read_text(errors="replace")


def test_eval_rebuilds_the_env_per_scene():
    t = src()
    assert "_eval_regime" in t and "for scene_id in scene_ids:" in t, (
        "the scene sweep is gone; train.py is back to evaluating whatever env it built once")
    assert "self._make_eval_env(mode, scene_id)" in t


def test_the_scene_list_defaults_to_the_ten_the_protocol_certifies():
    from rlgen.protocol import Protocol
    assert re.search(r"'0,1,2,3,4,5,6,7,8,9'", src()), "the default scene list changed"
    assert list(Protocol().eval_scene_ids) == list(range(10)), (
        "Protocol and train.py must agree on which scenes are certified; they are the two halves "
        "of the claim that a reported number covers them")


def test_a_train_regime_denominator_is_measured_and_not_swept():
    """Retention needs the distribution the agent trained on, which is scene 0 in train mode.

    Sweeping the denominator too would put scenes the agent never trained on into the
    denominator and make the ratio uninterpretable.
    """
    t = src()
    assert "self._eval_regime('train', scenes[:1], per)" in t, (
        "the train-regime denominator is gone, or it started sweeping scenes")
    assert "log('train_regime_reward'" in t and "log('train_regime_success'" in t


def test_the_other_domains_keep_the_original_loop():
    """`dmc` and `habitat` have no scene axis; P14 must not have changed what they run."""
    t = src()
    assert "if not hasattr(self, '_make_eval_env'):" in t
    assert "return self._eval_single()" in t
    assert "def _eval_single(self):" in t, (
        "the original loop was removed rather than preserved; dmc and habitat now run code that "
        "was never written for them")


def test_p14_is_declared_where_it_changes_the_hash():
    """The whole point of declaring it: pre- and post-P14 numbers must not pool silently."""
    from rlgen.protocol import Protocol
    p = Protocol()
    assert any("P14" in x for x in p.env_patches)
    assert p.hash() != Protocol(env_patches=tuple(
        x for x in p.env_patches if "P14" not in x)).hash(), (
        "dropping P14 from the patch list must change the protocol hash, or the hash cannot "
        "distinguish a ten-scene number from a one-scene one")


def test_p14_is_classified_as_enables():
    """It changes WHICH distribution is evaluated, so the number is ours, not RL-ViGen's."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "apply_patches", ROOT / "setup" / "apply_patches.py")
    ap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ap)
    assert ap.PATCH_CLASS["P14"] == "ENABLES"
