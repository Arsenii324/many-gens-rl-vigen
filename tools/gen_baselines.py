#!/usr/bin/env python3
"""Generate `baselines/<name>/{train.sh, README.md}` from the registry and the config.

WHY GENERATED. Seven near-identical launch scripts and seven near-identical READMEs, hand-written,
are seven places for the truth to drift -- and drift in a launch script is invisible until a run
finishes with the wrong budget. The registry (`rlgen/registry.py`) and the config
(`configs/vigen.yaml`) are the single source of truth; these files are a projection of them.

The generated files ARE committed, because the brief's use case is "clone and run one sh script"
and a user must not have to run a generator first. `tests/test_baselines.py` regenerates into a
temp dir and diffs, so a stale committed file fails the build.

    python tools/gen_baselines.py            # write
    python tools/gen_baselines.py --check    # exit 1 if anything is stale
"""
from __future__ import annotations

import argparse
import os
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from rlgen import registry  # noqa: E402

CONFIG = os.path.join(ROOT, "configs", "vigen.yaml")


def config_entries() -> dict:
    with open(CONFIG, encoding="utf-8") as f:
        return yaml.safe_load(f)


def deviations(entry: dict, base: dict) -> dict:
    return {k: v for k, v in entry.items()
            if k != "baseline" and (k not in base or base[k] != v)}


def train_sh(name: str, spec, entry: dict, base: dict) -> str:
    dev = deviations(entry, base)
    dev_txt = ("\n".join(f"#   {k}: {v}" for k, v in sorted(dev.items()))
               if dev else "#   (none — identical to `base`)")
    return f"""#!/usr/bin/env bash
# Train {spec.method} on RL-ViGen robosuite.
#
#   bash baselines/{name}/train.sh                  # Door, seed 0, the config's full budget
#   bash baselines/{name}/train.sh Lift 1           # task, seed
#   bash baselines/{name}/train.sh Door 0 --smoke   # same code path, tiny budget
#
# This script names a CONFIG, not an algorithm. `configs/vigen.yaml:{name}` is `base` plus only
# this method's own keys, so equal training conditions are the default and every deviation is one
# diffable line. Deviations from `base` for this baseline:
{dev_txt}
#
# Environment: see baselines/{name}/README.md. Evaluation is NOT configured here -- it is
# identical for every baseline by construction (rlgen/evaluate.py).
set -euo pipefail

HERE="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
cd "$REPO"

TASK="${{1:-Door}}"
SEED="${{2:-0}}"
shift 2 2>/dev/null || true

# macOS renders through GLFW; dm_control's validator rejects "cgl". Linux GPU boxes want "egl".
if [[ "$(uname -s)" == "Darwin" ]]; then export MUJOCO_GL="${{MUJOCO_GL:-glfw}}"
else export MUJOCO_GL="${{MUJOCO_GL:-egl}}"; fi
export PYTHONPATH="$REPO:${{PYTHONPATH:-}}"

PY="${{PYTHON:-python}}"
exec "$PY" train.py --config {name} --task "$TASK" --seed "$SEED" "$@"
"""


def readme(name: str, spec, entry: dict, base: dict) -> str:
    dev = deviations(entry, base)
    dev_rows = ("\n".join(f"| `{k}` | `{v}` |" for k, v in sorted(dev.items()))
                if dev else "| — | identical to `base` |")
    status_note = {
        "implemented": "A real, distinct training rule. Trainable.",
        "alias": (f"**Declared alias of `{spec.alias_of}`.** Identical inference network; the "
                  f"method's novelty is in a training objective not implemented here. It is "
                  f"labelled as an alias on every figure rather than given an independent row."),
        "eval_only": "Inference path only — it can score a checkpoint, not produce one.",
        "absent": "**Not implemented here.** Named in the supervisor's brief and listed so the "
                  "gap is countable.",
    }[spec.status]
    extra_block = ""
    if spec.extra_requirements:
        pkgs = " ".join(spec.extra_requirements)
        extra_block = (f"**This baseline needs {len(spec.extra_requirements)} package(s) beyond "
                       f"the shared set:**\n\n```bash\npip install {pkgs}\n```\n\n"
                       f"Discovered by running it, not by reading: nothing upstream declares "
                       f"them, and the import happens at module scope so the failure is at "
                       f"construction time.\n\n")
    if spec.data_requirements:
        from rlgen.registry import DATASETS
        rows = "\n".join(f"- **{d}** — {DATASETS[d][0]}" for d in spec.data_requirements)
        extra_block += (f"**This baseline needs external data to TRAIN:**\n\n{rows}\n\n"
                        f"`train.py` refuses to start without it and says so before writing any "
                        f"artifact — a run that cannot finish must not leave a directory that "
                        f"looks like one that can. **Evaluating an existing checkpoint does not "
                        f"need it**: the augmentation lives in `update()`, not `act()`.\n\n")
    runline = (f"```bash\nbash baselines/{name}/train.sh Door 0\n```"
               if spec.trainable else
               f"Not trainable (`status: {spec.status}`). `train.py --config {name}` exits 2 with "
               f"an explanation rather than producing a number.")
    return f"""# {spec.method}  (`{name}`)

| | |
|---|---|
| status | `{spec.status}` |
| backbone | `{spec.backbone}` |
| paper | {spec.paper} |

{status_note}

{spec.notes}

## Run

{runline}

## Environment

This baseline needs the shared RL-ViGen robosuite environment and nothing else. One environment
serves every baseline in this repo, so there is one install:

```bash
bash setup/install.sh          # creates .venv, installs pins, patches and verifies upstream
```

{extra_block}Pins that matter, and why (full reasoning in [`setup/VENDORED.md`](../../setup/VENDORED.md)):

- `robosuite` is **RL-ViGen's vendored fork, installed editable**. It calls itself 1.4.0 and
  differs from PyPI robosuite 1.4.0 in 761 files; a wheel build drops its assets.
- `mujoco==2.3.7`. 3.x renames `tex_rgb`, which RL-ViGen's texture modder uses, so every eval mode
  dies on 3.x while `train` keeps working — a failure confined to the path whose numbers matter.
- `MUJOCO_GL=glfw` on macOS (`dm_control` rejects `cgl`), `egl` on Linux. `train.sh` sets it.

Verify before trusting a number:

```bash
python setup/apply_patches.py --check    # exit 1 if the upstream patches are missing
pytest tests -q
```

## Hyperparameters

`configs/vigen.yaml:{name}` — `base` plus only the keys below.

| key | value |
|---|---|
{dev_rows}

Everything the *protocol* fixes — episode count, eval scenes, aggregation, budget, action repeat —
is in [`rlgen/protocol.py`](../../rlgen/protocol.py) and is identical for every baseline. It is
not settable here, by design.

<!-- generated by tools/gen_baselines.py — edit that, or the registry, not this file -->
"""


def targets() -> dict[str, tuple[str, str]]:
    cfg = config_entries()
    base = cfg.get("base", {})
    out = {}
    for name in ["random"] + list(registry.BRIEF_BASELINES):
        spec = registry.get(name)
        entry = cfg.get(name, {"baseline": name})
        out[os.path.join("baselines", name, "train.sh")] = (
            train_sh(name, spec, entry, base), "x")
        out[os.path.join("baselines", name, "README.md")] = (
            readme(name, spec, entry, base), "")
    out[os.path.join("baselines", "README.md")] = (index_readme(), "")
    return out


def index_readme() -> str:
    rows = []
    for name in ["random"] + list(registry.BRIEF_BASELINES):
        s = registry.get(name)
        run = f"`bash baselines/{name}/train.sh`" if s.trainable else "—"
        rows.append(f"| [`{name}`]({name}/) | `{s.status}` | `{s.backbone}` | {run} |")
    return f"""# Baselines

One directory per baseline. Each contains a `train.sh` that launches it and a `README.md` naming
its environment and its deviations from the shared config.

| baseline | status | backbone | launch |
|---|---|---|---|
{chr(10).join(rows)}

**`status` is load-bearing.** `implemented` is a real training rule; `alias` is deliberately the
same network as another baseline and is labelled as such on every figure; `absent` is named in the
supervisor's brief and not implemented here. An undeclared alias is what corrupts a results table,
so the declaration is machine-readable in [`rlgen/registry.py`](../rlgen/registry.py) and
[`plot.py`](../plot.py) reads it.

**Evaluation is not configurable per baseline.** There is one evaluator
([`rlgen/evaluate.py`](../rlgen/evaluate.py)); it receives the policy as an opaque callable and
cannot see which algorithm it is running. That is what makes the comparison fair, and it is
enforced by `tests/test_eval_identity.py` rather than by convention.

<!-- generated by tools/gen_baselines.py -->
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    stale = []
    for rel, (content, mode) in sorted(targets().items()):
        path = os.path.join(ROOT, rel)
        cur = open(path, encoding="utf-8").read() if os.path.exists(path) else None
        if cur == content:
            continue
        stale.append(rel)
        if args.check:
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        if mode == "x":
            os.chmod(path, 0o755)

    if args.check:
        if stale:
            print("STALE (run `python tools/gen_baselines.py`):")
            for s in stale:
                print("  -", s)
            return 1
        print("OK — every generated baseline file matches the registry and the config.")
        return 0
    print(f"{len(stale)} file(s) written" if stale else "already up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
