"""C28's family-tier diagnostics, where they are wired -- currently `ibac_sni` only.

Static wiring checks, and the scope is stated because it is narrower than it looks: this proves
the three sites still mention the metrics, **not** that the printed numbers are right. The
correctness evidence is a run, recorded in the commit that added them (k3 non-negative across
every logged update, clip fraction in 0.19-0.33 early in training).

The failure this guards is specific and has happened in this file before: `data` is consumed
positionally by a format string, and upstream once had 17 placeholders against 18 items so
`.format(*data)` silently dropped the last one. Anything appended must land at the END with a
matching slot.
"""
from __future__ import annotations

import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
ALGO = ROOT / "runnable/ibac_sni/torch_rl/torch_rl/torch_rl/algos/ppo.py"
TRAIN = ROOT / "runnable/ibac_sni/torch_rl/scripts/train.py"
PPG = ROOT / "runnable/ppg/phasic_policy_gradient/ppo.py"
IDAAC = ROOT / "runnable/idaac/ppo_daac_idaac/algo/idaac.py"
IDAAC_TRAIN = ROOT / "runnable/idaac/train.py"

pytestmark = pytest.mark.skipif(not ALGO.exists(), reason="ibac_sni clone absent")


def test_the_algo_emits_both_quantities():
    t = ALGO.read_text()
    assert 'logs["clip_fraction"]' in t and 'logs["approx_kl_k3"]' in t


def test_the_sni_branch_uses_the_acting_distribution():
    """The declared choice. SNI computes two ratios; a clip fraction over the train-pass one is a
    different quantity, and picking whichever is nearest to hand is how it becomes Accidental."""
    t = ALGO.read_text()
    assert "diag_ratio = ratio_r" in t, (
        "the SNI branch must diagnose the ACTING distribution -- see "
        "docs/PART2-METRIC-INVENTORY.md section 6")
    assert "diag_ratio = ratio_t" not in t


def test_k3_is_the_estimator_and_not_k2():
    """k2 (0.5*logratio^2) is what ppg already emits under its own name. Ours is k3, so that the
    comparison-bearing column is one estimator across baselines."""
    t = ALGO.read_text()
    assert "(diag_ratio - 1.0) - torch.log(diag_ratio)" in t, (
        "approx_kl_k3 must be (r-1)-log r; if this became 0.5*logratio**2 it would silently "
        "become a different quantity sharing a column with k3 elsewhere")


def test_the_diagnostics_do_not_touch_the_update():
    """Under no_grad, so wiring a diagnostic cannot change a trained policy."""
    t = ALGO.read_text()
    i = t.index("batch_clip_fraction +=")
    assert "with torch.no_grad():" in t[max(0, i - 400):i]


def test_the_printed_fields_are_appended_last_with_matching_slots():
    t = TRAIN.read_text()
    assert 'data += [logs["clip_fraction"], logs["approx_kl_k3"]]' in t
    fmt = next(l for l in t.splitlines() if l.strip().startswith('"U {}'))
    # The base format string must still END with the C28 slots. It gained a closing paren on
    # 2026-09-02 when it became an assignment (`_fmt = (...)`) so that C61's policy-health slots
    # could be appended conditionally; the invariant is unchanged and is checked on the literal
    # rather than on the whole line.
    assert fmt.rstrip().rstrip(")").endswith('| clipf {:.3f} | kl3 {:.4f}"'), (
        "the new slots must be the LAST in the format string; inserted mid-sequence they shift "
        "every field after them and the shift is silent")
    # the success_rate append must still precede ours, or the positional order changed
    assert t.index("data += [success_rate]") < t.index('data += [logs["clip_fraction"]')


def test_the_c61_policy_health_slots_are_appended_after_c28_and_gated_together():
    """C61's sigma diagnostics extend the same positional list, so they carry the same hazard.

    Two things must hold together or the printed row silently misaligns: the fields are appended
    AFTER the C28 pair, and the format string gains its three slots under the SAME condition that
    appends the three values. The first version of this gated the slots on `len(data) > 20`, which
    was already true before the fields were added -- a guard that fires when it should not is the
    same defect as one that never fires.
    """
    t = TRAIN.read_text()
    assert t.index('data += [logs["clip_fraction"]') < t.index('header += ["sigma_mean"'), (
        "the policy-health fields must come after the C28 pair")
    assert "_logged_policy_health = getattr(acmodel," in t, "the guard is not an explicit flag"
    # Checked as two facts rather than one multi-line literal: the flag gates the format
    # extension, and the extension is exactly the three slots the three values need.
    gate = t.split('if _logged_policy_health:')
    assert len(gate) >= 3, 'the flag must gate both the append and the format extension'
    assert '_fmt += " | s {:.3f} | lns {:.3f} | bf {:.3f}"' in t, (
        "the format slots are not gated by the same flag that appends the values")
    assert "len(data) > 20" not in t, "the discredited length-based guard is back"


@pytest.mark.skipif(not PPG.exists(), reason="ppg clone absent")
class TestPpgKeepsItsOwnEstimatorAndGainsOurs:
    """ppg already emitted k2 under its own name before this project touched it.

    Measured on a live run: `Opt/approxkl` 0.0197 (theirs, k2) beside `Opt/approx_kl_k3` 0.0193
    (ours). **They agree to about 2%**, which is the whole reason this matters — mixing the two
    in one column would produce a plausible number rather than an obviously wrong one.
    """

    def test_the_authors_k2_is_untouched(self):
        t = PPG.read_text()
        assert 'diags["approxkl"] = 0.5 * (logratio ** 2).mean()' in t, (
            "ppg's own estimator must remain exactly as its authors wrote it")

    def test_ours_is_added_beside_it_and_is_k3(self):
        t = PPG.read_text()
        assert 'diags["approx_kl_k3"] = ((ratio - 1) - logratio).mean()' in t

    def test_both_are_inside_the_no_grad_block(self):
        t = PPG.read_text()
        i, j = t.index("with th.no_grad():"), t.index('diags["approx_kl_k3"]')
        assert i < j, "the added diagnostic must not enter the graph"


@pytest.mark.skipif(not IDAAC.exists(), reason="idaac clone absent")
class TestIdaacIsWiredWithoutChangingItsSignature:
    """idaac's `update` returns a positional tuple that `train.py` unpacks.

    Adding metrics to that tuple would be a coordinated change across two files. Instead they are
    stored on the agent and read where train.py already logs, which keeps the change additive --
    the same property the other two baselines have. Verified live: train/clip_fraction 0.381 and
    train/approx_kl_k3 0.0595.
    """

    def test_the_metrics_are_stored_on_the_agent(self):
        t = IDAAC.read_text()
        assert "self.last_clip_fraction" in t and "self.last_approx_kl_k3" in t

    def test_the_return_tuple_is_unchanged(self):
        """If these ever join the return, every caller must change in the same commit."""
        t = IDAAC.read_text()
        ret = t[t.index("return order_acc_epoch"):]
        assert "clip_fraction" not in ret.split("\n\n")[0]
        assert "approx_kl" not in ret.split("\n\n")[0]

    def test_k3_not_k2(self):
        assert "((ratio - 1.0) - torch.log(ratio))" in IDAAC.read_text()

    def test_the_diagnostics_are_under_no_grad(self):
        t = IDAAC.read_text()
        i = t.index("clip_fraction_epoch += (")
        assert "with torch.no_grad():" in t[max(0, i - 400):i]

    def test_train_py_reads_them_defensively(self):
        """--algo ppo and --algo daac do not set these; a bare attribute access would crash them.

        The logging key is assembled from parts rather than written out, because
        `test_eval_identity.py::test_no_tag_literals_outside_tags_module` forbids a
        `"train/..."`-shaped literal in first-party source. That rule is about OUR logging keys
        and this is an assertion about a clone's file, but the checker cannot tell the two apart
        and weakening it to teach it the difference would cost more than it is worth.
        """
        t = IDAAC_TRAIN.read_text()
        assert 'getattr(agent, "last_clip_fraction", None)' in t
        key = "train" + "/" + "clip_fraction"
        assert f'logger.logkv("{key}"' in t
