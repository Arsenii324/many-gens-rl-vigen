"""`--policy-mode` exists because the evaluation policy mode is the fleet's only UNITS split.

`eval_grid.py` deliberately reproduces each family's own action rule -- `mode` for the eight
RL-ViGen/dmc_gb/alda baselines, `sample` for `idaac`, `ppg`, `ibac_sni`, `ctrl`. Those are
different estimands, not one estimand measured two ways, and two of A25's three fixed cross-group
pairs straddle the split. This flag produces the second, comparable pass.

The default must change nothing: `native` is what every existing record was produced under.
"""
from __future__ import annotations

import ast
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
GRID = ROOT / "scripts" / "eval_grid.py"


def test_the_flag_exists_and_defaults_to_native():
    result = subprocess.run([sys.executable, str(GRID), "--help"],
                            capture_output=True, text=True, cwd=str(ROOT))
    assert result.returncode == 0, result.stderr
    assert "--policy-mode {native,mode}" in result.stdout

    tree = ast.parse(GRID.read_text())
    defaults = [node for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and getattr(node.func, "attr", None) == "add_argument"
                and node.args and getattr(node.args[0], "value", None) == "--policy-mode"]
    assert len(defaults) == 1
    kwargs = {k.arg: k.value for k in defaults[0].keywords}
    assert kwargs["default"].value == "native", "the default must reproduce existing behaviour"


def test_every_sampling_family_honours_it():
    """The THREE sampling call sites -- ppg goes through a Roller and is easy to miss.

    ctrl was the fourth until 2026-09-07, when its native rule was corrected to the mode: its
    released evaluator is greedy (`runnable/ctrl/evaluate_ppo.py:84`). Its two policy modes now
    coincide, so it takes `sample=False` unconditionally and has nothing to honour. The dispatch
    site still FORWARDS the flag -- that is asserted below -- because the scope must still
    canonicalise for a forced-mode pass.
    """
    text = GRID.read_text()
    assert 'agent.act(obs, deterministic=(policy_mode == "mode"))' in text, "idaac"
    assert 'policy_mode == "mode", 1,' in text, "ibac_sni's argmax positional"
    assert "act_fn = agent.act" in text and "pd.mean" in text, "ppg's Roller wrapper"

    assert 'sample=(policy_mode != "mode")' not in text, (
        "ctrl must not branch on policy_mode: its native rule IS the mode, so branching would "
        "reintroduce the sampling estimator this correction removed")
    assert "key, sample=False)" in text, "ctrl takes the mode unconditionally"

    assert text.count("policy_mode=a.policy_mode") == 4, (
        "all four dispatch sites must forward it; a missed one silently reports the native mode")


def test_the_record_reports_the_mode_that_actually_ran():
    """The one way this feature could corrupt rather than help.

    Stamping the family's native rule while --policy-mode mode was in force would make the record
    assert the single thing it exists to certify -- which action rule produced these returns.
    """
    text = GRID.read_text()
    index = text.index('"eval_policy_mode":')
    window = text[index:index + 400]
    assert 'a.policy_mode == "mode"' in window, (
        "the stamped mode must be conditioned on the override, not on the family alone")
    # [Claude 2026-09-07] This used to also require an `eval_policy_mode_source` key IN THE SCOPE.
    # That key is not in SCOPE_FIELDS, so canonical_evaluation_scope would have raised "evaluator
    # scope has unknown fields" on every eval_grid run -- and this test, which reads the file as
    # text, asserted the presence of the very thing that broke it. The provenance is recoverable
    # without a new field: a scope whose eval_policy_mode is "mode" for a family whose native rule
    # is "sample" was forced, and one that matches the native rule was not.
    assert "eval_policy_mode_source" not in window, (
        "the scope must carry only SCOPE_FIELDS; provenance is derivable from the mode itself")


def test_both_scopes_canonicalise_and_get_distinct_revisions():
    """The check my source-parsing tests could not make, and that would have caught a crash.

    `canonical_evaluation_scope` validates the scope dict against SCOPE_FIELDS and enforces the
    family's policy mode. The first version of this feature put an `eval_policy_mode_source` key
    INTO the scope -- which would have raised "evaluator scope has unknown fields" on EVERY
    eval_grid run, native included -- and set `eval_policy_mode: "mode"`, which the identity check
    rejected as unresolved. Neither showed up in tests that read the file as text.
    """
    sys.path.insert(0, str(ROOT / "datasphere" / "native"))
    import evaluator_identity as identity

    base = {
        "family": "idaac", "baseline": "idaac", "task": "Door", "frame": 8192,
        "eval_scope": "endpoint", "regimes": ("train", "eval-easy"), "scenes": (0,),
        "episodes": 5, "episode_seed": 20260903, "seed": 1, "device": "cuda",
        "action_repeat": 1, "frame_stack": 3, "image_size": 64, "episode_length": 500,
        "deterministic_setting": identity.effective_deterministic_setting("idaac", True),
        "eval_policy_mode": identity.family_eval_policy_mode("idaac"),
    }
    native = identity.canonical_evaluation_scope(dict(base))
    forced = identity.canonical_evaluation_scope({**base, "eval_policy_mode": "mode"})

    native_revision = identity.scope_revision(native)
    forced_revision = identity.scope_revision(forced)
    assert native_revision != forced_revision, (
        "the two passes must be distinguishable in the ledger and in every record")

    # A family that already takes the mode gains nothing from the override, but the scope must
    # still resolve -- otherwise a stray flag turns into an unexplained crash.
    rlvigen = identity.canonical_evaluation_scope({
        **base, "family": "rlvigen", "baseline": "drqv2",
        "deterministic_setting": identity.effective_deterministic_setting("rlvigen", True),
        "eval_policy_mode": "mode"})
    assert rlvigen["eval_policy_mode"] == "mode"


def test_the_scope_rejects_keys_eval_grid_does_not_send():
    """The guard that caught the bug stays a guard."""
    sys.path.insert(0, str(ROOT / "datasphere" / "native"))
    import evaluator_identity as identity

    import pytest
    with pytest.raises(ValueError, match="unknown fields"):
        identity.canonical_evaluation_scope({
            "family": "idaac", "baseline": "idaac", "task": "Door", "frame": 8192,
            "eval_scope": "endpoint", "regimes": ("train",), "scenes": (0,), "episodes": 5,
            "episode_seed": 1, "seed": 1, "device": "cuda", "action_repeat": 1,
            "frame_stack": 3, "image_size": 64, "episode_length": 500,
            "deterministic_setting": identity.effective_deterministic_setting("idaac", True),
            "eval_policy_mode": "sample", "eval_policy_mode_source": "not a scope field"})


def test_the_protocol_declaration_beats_a_passed_frame_stack():
    """A fail-closed geometry check its own caller can redefine is not fail-closed.

    `declared_frame_stack = a.frame_stack` made OBSERVATION_GEOMETRY a fallback: a --frame-stack
    disagreeing with the protocol was adopted, recorded as "declared", and hashed into the scope.
    Flagged in the review tail as minor because production is stack 3 anyway -- true, and not the
    point, since the check exists for the case where the caller is wrong.
    """
    text = (ROOT / "scripts" / "eval_grid.py").read_text()
    # Match the ASSIGNMENT, not the string: the explanatory comment quotes the old line.
    import re
    assert not re.search(r"^\s*declared_frame_stack = a\.frame_stack\s*$", text, re.M), (
        "the protocol must not be overwritten by the CLI value")
    # And the per-family resolvers must read the protocol, not a caller-supplied fallback.
    # CODE lines only: the comments above the fix quote the old expression on purpose, and a naive
    # substring search matches the explanation rather than the behaviour -- which it did, twice,
    # while this test was being written.
    code = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
    assert not any("if frame_stack is None else int(frame_stack)" in line for line in code), (
        "a dead alternative branch makes the geometry look caller-supplied when it is not")
    assert "contradicts the protocol declaration for" in text
    # The message wraps across source lines, so match a fragment that does not straddle one.
    assert "geometry it was merely told" in text
