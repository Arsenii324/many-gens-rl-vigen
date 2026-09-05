"""CTRL's measured episode *i* must run placement condition index *i*, not 2*i*.

`_SyncVecEnv` auto-resets on done (`vec_env.py::step_wait`) and `_reset_one` advances
`_episode_indices[index] += 1` on **every** reset. So an explicit `env.reset()` per measured episode
consumed a second condition index each time: measured episode i ran index **2i**, while the record
claimed i. That unpaired ctrl from every other family and made its recorded
`placement_condition_seeds` wrong.

Reviews 8 and 9 both reported it. I refuted it once from `runnable/_patches/ctrl.patch`, which is a
**provenance snapshot** and was stale -- the live clone passes `condition_seed` through. The clone is
the artifact; the patch is a record of it.

The structural half is checked here; the behavioural half (counter 0->1->2->3 across two real
episodes) was verified against a constructed env and is covered by the smoke file.
"""
import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GRID = (ROOT / "scripts" / "eval_grid.py").read_text()
VEC = ROOT / "runnable" / "ctrl" / "vec_env.py"


def _ctrl_block() -> str:
    start = GRID.index("def run_scene_ctrl")
    return GRID[start:GRID.index("\ndef ", start + 10)]


def test_the_vector_env_still_auto_resets_and_counts():
    """If either stops being true, the reasoning below needs redoing rather than trusting."""
    if not VEC.is_file():                                          # pragma: no cover
        pytest.skip("ctrl clone is not present")
    body = VEC.read_text()
    assert "_episode_indices[index] += 1" in body, (
        "the condition counter no longer advances per reset; re-derive the pairing argument"
    )
    assert "_reset_one" in body and "step_wait" in body, "the auto-reset path changed"


def test_ctrl_resets_once_not_once_per_episode():
    block = _ctrl_block()
    resets = block.count("env.reset()")
    assert resets == 1, (
        f"run_scene_ctrl calls env.reset() {resets} times. It must reset ONCE: _SyncVecEnv "
        "auto-resets on done and advances its condition counter, so an explicit reset per episode "
        "makes measured episode i run condition index 2i while the record claims i."
    )


def test_the_reset_is_outside_the_episode_loop():
    block = _ctrl_block()
    reset_at = block.index("env.reset()")
    loop_at = block.index("for episode_index in range(episodes)")
    assert reset_at < loop_at, (
        "the single reset must precede the episode loop; inside it, it runs every episode again"
    )


def test_witnesses_are_still_captured_for_every_episode():
    """Resetting once must not cost the per-episode placement witnesses."""
    block = _ctrl_block()
    assert block.count("LAST_PLACEMENT_WITNESSES.append") >= 2, (
        "ctrl must record a witness for the first episode and for each auto-reset that begins a "
        "subsequent one, or _run_grid's witness/return count check will fire"
    )
    assert "len(LAST_PLACEMENT_WITNESSES) < episodes" in block, (
        "the witness capture must be capped at `episodes`; the final auto-reset begins an episode "
        "nobody measures"
    )
