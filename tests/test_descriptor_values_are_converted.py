"""Descriptor constants are strings; every numeric use must convert.

`families.json` stores constants as strings because they become CLI flags. `eval_grid.py`'s ctrl
loader built a JAX shape straight from `d["cluster_len"]`, so JAX received `(1, '10', 64, 64, 3)`
and raised `Shapes must be 1D sequences of concrete values of integer type`. **Every ctrl evaluation
died at checkpoint load.** Training was unaffected, so it survived until the first ctrl cell that
trained to completion on a tier large enough not to be SIGKILLed first -- two bugs deep.

Scanning rather than asserting the one line, because the next constant added here will have the same
shape of mistake.
"""
import ast
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GRID = ROOT / "scripts" / "eval_grid.py"
#: Keys whose values are genuinely strings and must NOT be wrapped in a numeric conversion.
TEXTUAL = {"embedding_type", "task", "baseline", "regime", "launcher", "algo", "obs_type"}


def _descriptor_string_keys() -> set[str]:
    raw = json.loads((ROOT / "datasphere" / "native" / "families.json").read_text())
    keys = set()
    for family, entry in raw.items():
        if family.startswith("_") or not isinstance(entry, dict):
            continue
        for key, value in (entry.get("constants") or {}).items():
            if isinstance(value, str):
                keys.add(key)
    return keys


def test_the_descriptor_really_does_store_numbers_as_strings():
    """Guards the premise: if this ever stops being true, the test below is measuring nothing."""
    assert "cluster_len" in _descriptor_string_keys()


def _offenders_in(source: str, string_keys: set[str]) -> list[str]:
    tree = ast.parse(source)
    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.converted = set()

        def visit_Call(self, node):
            if isinstance(node.func, ast.Name) and node.func.id in ("int", "float", "str", "bool"):
                for arg in ast.walk(node):
                    self.converted.add(id(arg))
            self.generic_visit(node)

    visitor = Visitor()
    visitor.visit(tree)
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Subscript):
            continue
        key = node.slice
        if not (isinstance(key, ast.Constant) and key.value in string_keys):
            continue
        if id(node) not in visitor.converted:
            offenders.append(f'd["{key.value}"] at line {node.lineno}')
    return offenders


def test_the_scan_catches_the_bug_it_was_written_for():
    """Non-vacuity: run the check against the code as it actually was, and require a hit."""
    broken = 'fake_state = jnp.zeros((1, d["cluster_len"], 64, 64, 3))\n'
    fixed = 'fake_state = jnp.zeros((1, int(d["cluster_len"]), 64, 64, 3))\n'
    assert _offenders_in(broken, {"cluster_len"}), "the scan does not catch the original defect"
    assert not _offenders_in(fixed, {"cluster_len"}), "the scan flags correctly converted code"


def test_no_descriptor_value_is_used_numerically_without_conversion():
    string_keys = _descriptor_string_keys() - TEXTUAL
    offenders = _offenders_in(GRID.read_text(), string_keys)
    assert not offenders, (
        "these descriptor values are strings and are used without int()/float(): "
        + "; ".join(offenders)
        + ". JAX and numpy reject a string in a shape, and the failure lands at checkpoint load.")


@pytest.mark.parametrize("key", ["cluster_len", "num_clusters", "n_att_heads"])
def test_the_specific_values_the_ctrl_loader_needs_parse_as_integers(key):
    raw = json.loads((ROOT / "datasphere" / "native" / "families.json").read_text())
    assert int(raw["ctrl"]["constants"][key]) > 0
