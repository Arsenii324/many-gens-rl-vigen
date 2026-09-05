"""Every flag the production command passes must be one its target script declares.

An unknown flag does not degrade gracefully: argparse exits 2 and absl aborts, so the cell dies
seconds in, having paid for provisioning and bootstrap. Nothing checked this, and the composed
command is assembled from `families.json` options plus a launcher's own `exec` line -- two places,
neither of which validates against the parser it feeds.

This is the train-side counterpart to `scripts/audit_executed_hyperparameters.py`, which asks
whether a claimed VALUE reaches the process. This asks whether the FLAG exists at all.

Hydra families (`rlvigen`) and spec-driven ones (`alda`) pass `key=value` overrides rather than
`--flags`, so only their `--` arguments are checked.
"""
import json
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "datasphere" / "native"))

#: Where each family's argument declarations live. Several scripts declare in a sibling module
#: (`arguments.py`), so more than one file may need reading.
DECLARERS = {
    "dmc_gb": ["runnable/dmc_gb/src/arguments.py", "runnable/dmc_gb/src/train.py"],
    "idaac": ["runnable/idaac/ppo_daac_idaac/arguments.py", "runnable/idaac/train.py"],
    "ppg": ["runnable/ppg/phasic_policy_gradient/train.py"],
    "ibac_sni": ["runnable/ibac_sni/torch_rl/scripts/train.py"],
    "ctrl": ["runnable/ctrl/train_ppo.py"],
}
#: Flags consumed by our own launcher wrapper before the target script sees argv.
LAUNCHER_CONSUMED = {"--spec.trainer.config.n_train_steps"}


def declared_flags(family: str) -> set[str]:
    names: set[str] = set()
    for relative in DECLARERS[family]:
        path = ROOT / relative
        if not path.is_file():
            continue
        body = path.read_text(errors="replace")
        names |= set(re.findall(r'add_argument\(\s*["\']--([A-Za-z0-9_-]+)', body))
        names |= set(re.findall(r'flags\.DEFINE_[a-z]+\(\s*["\']([A-Za-z0-9_-]+)', body))
    return names


def production_flags(family: str) -> set[str]:
    import family as family_module
    fields = dict(frames=600000, eval_every=2147483647, eval_episodes=2, save_every=50000,
                  run_dir="/tmp/run", task="Door", seed=101, baseline="x", cell="x", scene_id=0,
                  model_dir="/tmp/m", work="/tmp/w", out="/tmp/o")
    argv = [str(item) for item in family_module.command(family, fields)]
    return {token[2:].split("=")[0] for token in argv if token.startswith("--")}


@pytest.mark.parametrize("family", sorted(DECLARERS))
def test_every_production_flag_is_declared_by_its_target_script(family):
    declared = declared_flags(family)
    if not declared:
        pytest.skip(f"{family}'s argument declarations are not readable in this tree")
    passed = production_flags(family)
    unknown = sorted(name for name in passed
                     if name not in declared
                     and name.replace("-", "_") not in declared
                     and name.replace("_", "-") not in declared
                     and f"--{name}" not in LAUNCHER_CONSUMED)
    assert not unknown, (
        f"{family}: the production command passes flags its target script does not declare: "
        f"{unknown}. argparse exits 2 and absl aborts on an unknown flag, so the cell would die "
        "seconds in, after paying for provisioning and bootstrap."
    )


def test_the_declaration_scraper_actually_finds_flags():
    """A scraper that silently finds nothing would make every family vacuously clean."""
    for family in DECLARERS:
        found = declared_flags(family)
        if not found:
            continue
        assert len(found) > 5, f"{family}: only {len(found)} flags scraped, which looks like a miss"
