"""ALDA's rich per-update train diagnostics used to be discarded entirely under production's own
default (`use_wandb=False`) -- computed, averaged, and `.clear()`-ed with no persistent record.

Found auditing metric richness across all twelve baselines. This had previously been reported (in
this same project) as ALDA's strength, on the basis that `logging_info.setdefault(...).append(...)`
calls exist for 14+ metrics -- true, but nobody had verified the values ever reach a sink, which is
exactly the gap this file exists to close mechanically rather than by re-reading the source once.

[Claude 2026-09-06] That persistence write itself then shipped a latent bug no test here caught,
because every test below was a source-text check and none ever called `json.dumps` on data shaped
like what the real training loop produces. `sum(list_of_tensors) / len(list_of_tensors)` (the
averaging loop just above the write, upstream and unmodified) can leave a 0-d `torch.Tensor` in
`self.logging_info[k]` -- `wandb.log` tolerates that silently, `json.dumps` does not. First hit for
real by job `bt10p8oorc64302metk8` (2026-09-06), crashing training at step 1500/10000. Fixed with a
`default=` handler scoped to this addition; `test_tensor_valued_metrics_serialize_without_crashing`
below exercises that handler directly rather than trusting the source text again.
"""
import json
import textwrap
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
TRAINER = ROOT / "runnable" / "alda" / "trainers" / "alda_trainer.py"


def _extract_jsonable_fn():
    """Pull the live `_jsonable` function's source out of the trainer and exec it in isolation,
    so the test exercises the actual shipped code rather than a hand-copied re-implementation
    that could silently drift from it."""
    t = TRAINER.read_text()
    d = t.index("def _jsonable(value):")
    i = t.rindex("\n", 0, d) + 1  # start of that line, keeping its real leading whitespace
    j = t.index("\n                    with open(", d)
    dedented = textwrap.dedent(t[i:j])
    namespace = {"torch": torch, "TypeError": TypeError}
    exec(dedented, namespace)  # noqa: S102 -- extracting real code under test, not untrusted input
    return namespace["_jsonable"]


def test_logging_info_is_persisted_when_wandb_is_off():
    t = TRAINER.read_text()
    i = t.index("if self.use_wandb:\n                    wandb.log(self.logging_info)")
    block = t[i:i + 3000]
    assert "else:" in block, "no fallback branch when wandb is disabled"
    assert 'open(Path(self.exp_dir) / "train_metrics.jsonl", "a")' in block, (
        "the else-branch does not write logging_info anywhere persistent")
    assert "json.dumps(self.logging_info, default=" in block, (
        "the write must tolerate a residual Tensor value -- see "
        "test_tensor_valued_metrics_serialize_without_crashing for why")


def test_tensor_valued_metrics_serialize_without_crashing():
    """Non-vacuity: reproduces the exact shape that crashed bt10p8oorc64302metk8 -- a dict with a
    0-d Tensor value, the residue `sum(list_of_tensors) / len(list_of_tensors)` leaves behind --
    and proves the live `default=` handler serializes it rather than raising."""
    jsonable = _extract_jsonable_fn()
    logging_info = {"critic_loss": torch.tensor(0.4213), "env_step": 1500}
    encoded = json.dumps(logging_info, default=jsonable)
    decoded = json.loads(encoded)
    assert decoded["critic_loss"] == torch.tensor(0.4213).item()
    assert decoded["env_step"] == 1500


def test_a_genuinely_unserializable_value_still_raises():
    """The handler must not silently swallow every failure -- only unwrap Tensors."""
    jsonable = _extract_jsonable_fn()
    with __import__("pytest").raises(TypeError):
        json.dumps({"bad": object()}, default=jsonable)


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
