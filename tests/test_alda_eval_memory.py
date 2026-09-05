"""Offline ALDA evaluation must not construct the training replay buffer twice."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRAINER = ROOT / "runnable" / "alda" / "trainers" / "alda_trainer.py"
GRID = ROOT / "scripts" / "eval_grid.py"


def test_alda_eval_uses_single_env_build_with_small_non_prefilled_replay():
    trainer = TRAINER.read_text()
    grid = GRID.read_text()
    build_start = trainer.index("    def build(")
    build_end = trainer.index("    def train_mode(", build_start)
    build = trainer[build_start:build_end]
    eval_start = grid.index("def _alda_trainer(")
    eval_end = grid.index("\ndef run_scene_alda(", eval_start)
    evaluator = grid[eval_start:eval_end]

    assert "replay_capacity=None" in build
    assert "prefill=True" in build
    assert "capacity=self.buffer_capacity if replay_capacity is None else replay_capacity" in build
    assert "prefill=prefill" in build
    assert "trainer.initialize_env_dmc(spec)" not in evaluator
    assert "trainer.build(spec, replay_capacity=1, prefill=False)" in evaluator
