"""`audit_eval_validity` check 4 must not report a rate it has not measured — in either direction.

## Two bugs, in opposite directions, one day apart

**First**, the check collected placement witnesses into a `set` per `(regime, scene, index)` and
called a slot varying when the set held more than one value. On a file holding a single pass at a
single frame every slot has exactly one witness, so it printed **"200/200 reproducible (0% vary)"**
for all four regimes across 800 slots having compared nothing — and that number was repeated into
two notes as a measurement.

**Second**, the fix for that treated a set of size one as "observed once". But a set of size one
also describes a slot observed ten times *identically*, which is perfect reproducibility. That
version turned the real result into `NOT COMPARED` — the same failure pointing the other way.

So the property is not "count distinct values" and not "count slots". It is: **a slot is evidence
only when observed more than once, and observations must be counted separately from distinct
values.** Both directions are pinned below, because fixing one is what broke the other.

Real figures on `card0-20260909-035152`'s full bundle, for reference: train 200/200 reproducible,
eval-easy 200/200, eval-hard 145/166 (13% vary), eval-medium 75/200 (62% vary).
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_eval_validity.py"


def _row(regime, scene, witnesses, frame=100):
    n = len(witnesses)
    returns = [1.0] * n
    return json.dumps({
        "schema": 2, "phase": "offline-eval", "eval_scope": "endpoint", "frame": frame,
        "baseline": "idaac", "family": "idaac", "seed": 1, "regime": regime,
        "scene_set": str(scene), "episodes": n,
        "episode_return_mean": 1.0, "episode_return_sd": 0.0, "success_rate": 0.0,
        "native": {
            "returns": returns,
            "episode_success": [0] * n,
            "placement_witnesses": witnesses,
            "placement_condition_seeds": list(range(n)),
            "eval_episode_ids": [f"idaac-s1-f{frame}-{regime}-sc{scene}-e{i}" for i in range(n)],
        },
    })


def _run(tmp_path, rows):
    path = tmp_path / "r.jsonl"
    path.write_text("".join(r + "\n" for r in rows))
    proc = subprocess.run([sys.executable, str(SCRIPT), str(path)],
                          capture_output=True, text=True, timeout=180)
    return proc.stdout + proc.stderr


def test_a_single_pass_reports_not_compared(tmp_path):
    """One observation per slot is evidence of nothing and must not read as 0% vary."""
    output = _run(tmp_path, [_row("train", 0, ["w0", "w1", "w2"])])
    assert "NOT COMPARED" in output, output
    assert "0% vary" not in output.replace(" ", ""), (
        "a single-pass file still reports a reproducibility rate:\n" + output
    )


def test_repeated_identical_observations_are_reproducible_not_uncompared(tmp_path):
    """The second bug: many identical observations must NOT read as 'observed once'."""
    output = _run(tmp_path, [
        _row("train", 0, ["w0", "w1", "w2"], frame=100),
        _row("train", 0, ["w0", "w1", "w2"], frame=200),
    ])
    assert "NOT COMPARED" not in output, (
        "identical repeats were misread as never compared -- this is the regression that fixing "
        "the first bug introduced:\n" + output
    )
    assert "3/3 reproducible" in output and "0% vary" in output.replace("  ", " "), output


def test_repeated_differing_observations_are_reported_as_varying(tmp_path):
    output = _run(tmp_path, [
        _row("eval-medium", 0, ["a0", "a1", "a2"], frame=100),
        _row("eval-medium", 0, ["b0", "b1", "b2"], frame=200),
    ])
    assert "NOT COMPARED" not in output
    assert "0/3 reproducible" in output and "100% vary" in output.replace("  ", " "), output
    assert "NOT paired" in output


def test_mixed_regimes_report_independently(tmp_path):
    """A compared regime and an uncompared one in one file must not contaminate each other."""
    output = _run(tmp_path, [
        _row("train", 0, ["w0", "w1"], frame=100),
        _row("train", 0, ["w0", "w1"], frame=200),
        _row("eval-hard", 0, ["h0", "h1"], frame=100),
    ])
    train_line = next(l for l in output.splitlines() if "train" in l and "reproducible" in l)
    hard_line = next(l for l in output.splitlines() if "eval-hard" in l)
    assert "2/2 reproducible" in train_line, train_line
    assert "NOT COMPARED" in hard_line, hard_line
