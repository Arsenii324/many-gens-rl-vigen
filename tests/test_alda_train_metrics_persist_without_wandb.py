"""ALDA's rich per-update train diagnostics used to be discarded entirely under production's own
default (`use_wandb=False`) -- computed, averaged, and `.clear()`-ed with no persistent record.

Found auditing metric richness across all twelve baselines. This had previously been reported (in
this same project) as ALDA's strength, on the basis that `logging_info.setdefault(...).append(...)`
calls exist for 14+ metrics -- true, but nobody had verified the values ever reach a sink, which is
exactly the gap this file exists to close mechanically rather than by re-reading the source once.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRAINER = ROOT / "runnable" / "alda" / "trainers" / "alda_trainer.py"


def test_logging_info_is_persisted_when_wandb_is_off():
    t = TRAINER.read_text()
    i = t.index("if self.use_wandb:\n                    wandb.log(self.logging_info)")
    block = t[i:i + 1400]
    assert "else:" in block, "no fallback branch when wandb is disabled"
    assert 'open(Path(self.exp_dir) / "train_metrics.jsonl", "a")' in block, (
        "the else-branch does not write logging_info anywhere persistent")
    assert "json.dumps(self.logging_info)" in block


def test_the_clear_still_happens_after_either_path():
    """Regression guard: the fix must not accidentally skip clearing (which would leak averaged
    values from one interval into the next interval's sum)."""
    t = TRAINER.read_text()
    i = t.index('open(Path(self.exp_dir) / "train_metrics.jsonl", "a")')
    after = t[i:i + 400]
    assert "self.logging_info.clear()" in after


def test_json_is_imported():
    t = TRAINER.read_text()
    assert "import json" in t.splitlines()
