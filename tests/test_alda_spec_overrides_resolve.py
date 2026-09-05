"""Every `--spec.trainer.config.X` alda's descriptor passes must exist in alda's spec.

[Claude 2026-09-05] ALDA's override mechanism (`parse_spec_overrides`) accepts only keys ALREADY
PRESENT in the spec file; an absent key is a hard startup failure, not a default. So adding an
option to `families.json` without declaring the key silently breaks *every* alda cell.

That has now happened twice in one evening — `checkpoint_n_steps` (job bt1nmsbsf7u1o4618eks) and
`eval_n_steps` (job bt1763ukgansn5t7t5tv), each costing a job to discover. Two occurrences of one
shape is what this project treats as a class, so it is checked here instead of on a GPU.
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "runnable" / "alda" / "specs" / "train_alda_robosuite_door.yaml"
FAMILIES = ROOT / "datasphere" / "native" / "families.json"


def _alda_options():
    data = json.loads(FAMILIES.read_text())
    return (data.get("families", data))["alda"].get("options", [])


def test_every_spec_override_key_is_declared_in_the_spec():
    if not SPEC.is_file():
        pytest.skip("alda clone not present")
    spec_text = SPEC.read_text()
    missing = []
    for option in _alda_options():
        m = re.match(r"--spec\.trainer\.config\.([A-Za-z_][A-Za-z0-9_]*)", option)
        if not m:
            continue
        key = m.group(1)
        # the key must appear as a yaml mapping key, not merely inside a comment
        if not re.search(rf"^\s*{re.escape(key)}\s*:", spec_text, re.M):
            missing.append(key)
    assert not missing, (
        "families.json passes these alda overrides but the spec does not declare them, so every "
        f"alda cell will fail at startup: {missing}. Declare each at ALDA's own default in "
        f"{SPEC.relative_to(ROOT)} — that keeps behaviour identical while making the knob reachable.")


def test_the_two_cadence_keys_are_present_and_at_upstream_defaults():
    """Behaviour must be unchanged by declaring them; only reachability changes."""
    if not SPEC.is_file():
        pytest.skip("alda clone not present")
    import yaml
    config = yaml.safe_load(SPEC.read_text())["trainer"]["config"]
    assert config["checkpoint_n_steps"] == 50_000, "must match alda_trainer.py:73's own default"
    assert config["eval_n_steps"] == 10_000, "must match alda_trainer.py:72's own default"
