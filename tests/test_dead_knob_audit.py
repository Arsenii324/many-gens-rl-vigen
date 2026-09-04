#!/usr/bin/env python3
"""`scripts/audit_dead_knobs.py` must find the defects it was written for, and stay silent
otherwise — C71.

This project's standing rule is that a checker without an input that makes it red is decoration
(`CLAUDE.md`'s nulls, `docs/RIGOR.md`). `check_citations` once reported 0 defects across 677
citations with a predicate that could not fail, so the tests below are written against
**synthetic sources with a known answer** rather than only against the repo, which could drift.

The repo-facing test is kept as well, but deliberately asserts a *floor* rather than an exact
count: pinning the exact number would turn every legitimate change to a clone tree into a red
test, and this instrument is a lead generator, not a specification.
"""
from __future__ import annotations

import ast
import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("adk", ROOT / "scripts" / "audit_dead_knobs.py")
adk = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adk)


def findings_for(src: str) -> list[dict]:
    tree = ast.parse(src)
    out = []
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        out += adk.audit_function(fn, "<synthetic>")
    return out


PARAM_CASE = '''
def make_env(domain_name, action_repeat=4, image_size=100, frame_stack=3):
    if domain_name == 'robosuite':
        env = build(frame_stack)
        return env
    return dmc2gym.make(frame_skip=action_repeat, height=image_size)
'''

CONFIG_CASE = '''
def initialize_env(self, spec):
    cfg = spec['env']
    if cfg.get('domain_name') == 'robosuite':
        self.env = build(cfg['task_name'])
        return
    self.env = dmc2gym.make(frame_skip=cfg['action_repeat'])
'''

CLEAN_CASE = '''
def make_env(domain_name, action_repeat=4, frame_stack=3):
    if domain_name == 'robosuite':
        return build(frame_stack, action_repeat)
    return dmc2gym.make(frame_skip=action_repeat, stack=frame_stack)
'''

NO_RETURN_CASE = '''
def make_env(domain_name, action_repeat=4):
    if domain_name == 'robosuite':
        note()
    return dmc2gym.make(frame_skip=action_repeat)
'''


def test_it_catches_the_parameter_shape():
    """Instances #1 and #5: a named parameter consumed only after the early return."""
    got = {f["param"] for f in findings_for(PARAM_CASE)}
    assert "action_repeat" in got, "missed the defect this instrument exists for"
    assert "image_size" in got
    assert "frame_stack" not in got, "frame_stack IS used inside the branch; flagging it is noise"


def test_it_catches_the_config_key_shape():
    """Instance #2: `alda`'s config arrives as dict keys, not parameters.

    The first version of the checker handled only parameters and reported `alda` clean. This is
    the case that failure would fail on.
    """
    got = {f["param"] for f in findings_for(CONFIG_CASE)}
    assert "action_repeat" in got, "the config-key idiom regressed; alda would read as clean"
    assert "task_name" not in got, "task_name IS read inside the branch"


def test_it_stays_silent_when_the_branch_consumes_everything():
    """The mirror. Without this, a checker that flagged unconditionally would pass the two above."""
    assert findings_for(CLEAN_CASE) == []


def test_a_branch_that_does_not_return_is_not_a_dead_knob():
    """Falling through is not dropping: the code after the `if` still runs.

    Written because the natural implementation — 'find an `if` on a domain name' — is wrong
    without the return check, and would flag every domain-specific tweak in the codebase.
    """
    assert findings_for(NO_RETURN_CASE) == []


def test_the_real_trees_still_show_the_known_instances():
    """A floor, not an exact count, and it names why.

    C71 records five dead knobs; three share this shape. If this drops to zero the instrument has
    gone blind — which is the failure that matters, since a dead-knob audit reporting clean is
    exactly the false reassurance C71 exists to prevent.
    """
    missing = [p for p in adk.DEFAULT_PATHS if not (ROOT / p).exists()]
    if missing:
        pytest.skip(f"clone trees absent: {missing}")
    found = []
    for rel in adk.DEFAULT_PATHS:
        tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
            found += adk.audit_function(fn, rel)
    params = {(f["file"].split("/")[1], f["param"]) for f in found}
    assert ("dmc_gb", "action_repeat") in params, "C71 #1 no longer detected"
    assert ("dmc_gb", "image_size") in params, "C71 #5 no longer detected"
    assert ("alda", "action_repeat") in params, "C71 #2 no longer detected"
