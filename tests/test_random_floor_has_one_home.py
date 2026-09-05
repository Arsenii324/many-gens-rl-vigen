"""The Door random-policy floor must exist in exactly one place.

On 2026-09-05 the literal `1.82` was live in five places -- two `RANDOM_FLOOR = 1.82` constants and
three prose statements -- while the measured value had moved to **1.842** after the floor was
re-measured over 200 paired episodes. Raised by Codex as Q12.

This is `SYNTHESIS` Mechanism 2 in its most literal form, and the failure it invites is not
cosmetic: the floor is the denominator guard for the competence gate, so a stale copy silently
turns "at chance" into "competent" and back.
"""
import importlib.util
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONSUMERS = ("scripts/audit_shared_evaluator.py", "scripts/preprod_table.py")


def _canonical() -> float:
    spec = importlib.util.spec_from_file_location(
        "_ref_floor", ROOT / "scripts" / "rlvigen_reference.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["_ref_floor"] = module
    spec.loader.exec_module(module)
    return float(module.DOOR_RANDOM_FLOOR)


def test_the_canonical_floor_is_the_measured_one():
    assert _canonical() == pytest.approx(1.842), (
        "the canonical floor no longer matches the 200-episode measurement recorded at C55"
    )


@pytest.mark.parametrize("relative", CONSUMERS)
def test_consumers_import_the_floor_rather_than_copying_it(relative):
    path = ROOT / relative
    if not path.is_file():                                         # pragma: no cover
        pytest.skip(f"{relative} is not in this tree")
    body = path.read_text()
    assert "_door_random_floor()" in body, (
        f"{relative} must obtain the floor from rlvigen_reference, not hold its own literal"
    )
    literals = re.findall(r"RANDOM_FLOOR\s*=\s*([0-9]+\.[0-9]+)", body)
    assert not literals, f"{relative} still hardcodes the floor: {literals}"


@pytest.mark.parametrize("relative", CONSUMERS)
def test_each_consumer_resolves_to_the_canonical_value(relative):
    """Importing the right symbol is not the same as getting the right number."""
    path = ROOT / relative
    if not path.is_file():                                         # pragma: no cover
        pytest.skip(f"{relative} is not in this tree")
    name = path.stem
    spec = importlib.util.spec_from_file_location(f"_floor_{name}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"_floor_{name}"] = module
    try:
        spec.loader.exec_module(module)
    except Exception as error:                                     # pragma: no cover
        pytest.skip(f"{relative} not importable here: {type(error).__name__}: {error}")
    assert float(module.RANDOM_FLOOR) == pytest.approx(_canonical())
