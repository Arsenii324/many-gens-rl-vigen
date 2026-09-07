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
    """All four sampling call sites, not three -- ppg goes through a Roller and is easy to miss."""
    text = GRID.read_text()
    assert 'agent.act(obs, deterministic=(policy_mode == "mode"))' in text, "idaac"
    assert 'sample=(policy_mode != "mode")' in text, "ctrl"
    assert 'policy_mode == "mode", 1,' in text, "ibac_sni's argmax positional"
    assert "act_fn = agent.act" in text and "pd.mean" in text, "ppg's Roller wrapper"

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
    assert "eval_policy_mode_source" in window, "and it must say which of the two it was"
