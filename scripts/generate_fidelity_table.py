#!/usr/bin/env python3
"""Emit the per-baseline hyperparameter table FROM SOURCE, so prose cannot drift away from it.

    python scripts/generate_fidelity_table.py            # print
    python scripts/generate_fidelity_table.py --write    # splice into docs/FAITHFULNESS.md
    python scripts/generate_fidelity_table.py --check    # exit 1 if the spliced block is stale

## Why this exists

`scripts/audit_executed_hyperparameters.py` asks the right question -- does the value the table
CLAIMS reach the process -- but it can only ask it about claims written in the one machine-readable
shape it parses, and there are **six** of those. The 2026-09-08 documentation sweep found that
`docs/FAITHFULNESS.md`'s prose tables, which the parser never reaches, are stale on essentially
every numeric claim about the on-policy four:

  - idaac given as gamma 0.999, rollout 256, lr 5e-4, `num_processes=4`. IDAAC-C2 (2026-09-06) made
    those 0.99 / 2048 / 3e-4 / 1.
  - ppg given as `num_envs=8`, lr 1e-4. The descriptor says 1 and 3e-4.
  - "released Procgen geometry remains one frame for `ibac_sni` and `ctrl`", tagged `[LIVE]`.
    A40-REVISED-2 (2026-09-08) raised both to 3; all twelve now stack 3.
  - ctrl's cluster count given as 32 against the released 200.

None of those was a lie when written. Each was true of a port or a decision that has since been
replaced, and the prose was not revisited. That is not a documentation problem to be fixed once by
editing -- it is a class, and it recurs every time a decision lands.

So the numbers stop being prose. This generates them from the same sources the runner resolves,
splices them into a marked block, and `--check` fails when the block no longer matches. A stale
table becomes a failing test rather than a reader's wrong belief.

## Resolution order, and why the column says which

Identical to the audit's, because a table that resolved values differently from the runner would be
a second source of truth rather than a check on the first:

  1. an explicit flag on the launcher's `exec` line   -- `runnable/_launch/*.sh`
  2. a constant in `datasphere/native/families.json`  -- with the `v100` overlay applied where it
     differs, because **`v100` is production and the base entries are the DataSphere tiers**
  3. the clone's own argparse/absl default            -- what applies when nobody passes anything

Case 3 is reported as `default`, never silently as a chosen value. The distinction is the whole
point of the IBAC `beta` incident: a documented 1e-4 that nobody passed, executing as 1.0.

## What it deliberately does not do

It does not evaluate whether a value is RIGHT. Fidelity arguments, paper citations and the
declare-versus-equalise decisions stay in prose, where they belong -- they are judgements, and a
generator that rendered them would be laundering an opinion as a fact. This renders only what the
process will actually receive.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "datasphere" / "native"))

from rlgen.protocol import (  # noqa: E402
    OBSERVATION_GEOMETRY, REWARD_NORMALIZATION, TIME_LIMIT_HANDLING,
)

BEGIN = "<!-- BEGIN GENERATED: scripts/generate_fidelity_table.py -->"
END = "<!-- END GENERATED -->"

BASELINES = ["drqv2", "svea", "sgqn", "curl", "drq", "rad", "soda", "alda",
             "idaac", "ppg", "ibac_sni", "ctrl"]

FAMILY_OF = {"drqv2": "rlvigen", "svea": "rlvigen", "sgqn": "rlvigen", "curl": "rlvigen",
             "drq": "rlvigen", "rad": "dmc_gb", "soda": "dmc_gb", "alda": "alda",
             "idaac": "idaac", "ppg": "ppg", "ibac_sni": "ibac_sni", "ctrl": "ctrl"}

#: Where a family's per-run values actually live, when they are not in `families.json`.
RLVIGEN_CFG = {"drqv2": "config", "svea": "svea_config", "sgqn": "sgqn_config",
               "curl": "curl_config", "drq": "drq_config"}


def _families() -> dict:
    return json.loads((ROOT / "datasphere" / "native" / "families.json").read_text())


def _resolved(family: str, profile: str | None = None) -> dict:
    from family import resolved_descriptor  # noqa: E402
    return (resolved_descriptor(family) if profile is None
            else resolved_descriptor(family, profile=profile))


def _launcher_flag(family: str, flag: str) -> str | None:
    """An explicit flag on the launcher's exec line. Highest precedence, and easy to miss:
    `ibac_sni`'s `--beta`, `--sni_type`, `--use_bottleneck` and `--entropy-coef` live ONLY here,
    in a shell literal, invisible to anyone auditing `families.json`."""
    path = ROOT / "runnable" / "_launch" / f"{family}.sh"
    if not path.is_file():
        return None
    text = path.read_text()
    match = re.search(rf"{re.escape(flag)}[= ]+([^\s\\]+)", text)
    return match.group(1).strip("'\"") if match else None


def _rlvigen_cfg(baseline: str, key: str) -> str | None:
    name = RLVIGEN_CFG.get(baseline)
    if not name:
        return None
    path = ROOT / "RL-ViGen-upstream" / "cfgs" / f"{name}.yaml"
    if not path.is_file():
        return None
    match = re.search(rf"^\s*{re.escape(key)}\s*:\s*([^\s#]+)", path.read_text(), re.M)
    return match.group(1) if match else None


def _absl_default(relpath: str, name: str) -> str | None:
    path = ROOT / relpath
    if not path.is_file():
        return None
    match = re.search(rf"flags\.DEFINE_\w+\(\s*['\"]{re.escape(name)}['\"]\s*,\s*([^,]+),",
                      path.read_text())
    return match.group(1).strip().strip("'\"") if match else None


def _dataclass_default(relpath: str, name: str) -> str | None:
    """A `name: type = value` field on a config dataclass.

    ALDA carries its hyperparameters this way rather than through argparse or the descriptor, so
    the audit's three resolution sites miss it entirely and the row renders empty. An empty cell
    reads as "no such parameter", which is a different and worse claim than the true one.
    """
    path = ROOT / relpath
    if not path.is_file():
        return None
    match = re.search(rf"^\s*{re.escape(name)}\s*:\s*\w+\s*=\s*([^\s#]+)",
                      path.read_text(), re.M)
    return match.group(1) if match else None


def _argparse_default(relpath: str, flag: str) -> str | None:
    path = ROOT / relpath
    if not path.is_file():
        return None
    text = path.read_text()
    match = re.search(rf"add_argument\(\s*['\"]{re.escape(flag)}['\"][^)]*?default\s*=\s*([^,)]+)",
                      text, re.S)
    return match.group(1).strip().strip("'\"") if match else None


def _cell(value, origin: str) -> str:
    if value is None:
        return "&mdash;"
    return f"{value} <sub>{origin}</sub>"


def resolve(baseline: str, key: str) -> tuple[str | None, str]:
    """Return (value, origin) exactly as the running process would receive it."""
    family = FAMILY_OF[baseline]
    constants = _resolved(family, "v100").get("constants", {}) or {}
    entry = _families().get(family, {})
    template = json.dumps(entry.get("options", [])) + json.dumps(entry.get("positional", []))

    flag = {"lr": "--lr", "gamma": "--gamma", "entropy": "--entropy-coef"}.get(key)
    if flag:
        found = _launcher_flag(family, flag)
        if found is not None:
            return found, "launcher"

    alias = {"lr": ("lr",), "gamma": ("gamma", "discount"),
             "entropy": ("entropy_coef", "entcoef")}.get(key, (key,))
    for name in alias:
        if name in constants and "{" + name + "}" in template:
            return constants[name], "descriptor"

    if baseline in RLVIGEN_CFG:
        found = _rlvigen_cfg(baseline, {"lr": "lr", "gamma": "discount",
                                        "entropy": "init_temperature"}.get(key, key))
        if found is not None:
            return found, "cfg yaml"

    probes = {
        "ctrl": ("runnable/ctrl/train_ppo.py", _absl_default,
                 {"lr": "lr", "gamma": "gamma", "entropy": "entropy_coeff"}),
        "idaac": ("runnable/idaac/ppo_daac_idaac/arguments.py", _argparse_default,
                  {"lr": "--lr", "gamma": "--gamma", "entropy": "--entropy_coef"}),
        "ibac_sni": ("runnable/ibac_sni/torch_rl/scripts/train.py", _argparse_default,
                     {"lr": "--lr", "gamma": "--discount", "entropy": "--entropy-coef"}),
        "rad": ("runnable/dmc_gb/src/arguments.py", _argparse_default,
                {"lr": "--actor_lr", "gamma": "--discount", "entropy": "--init_temperature"}),
    }
    probes["soda"] = probes["rad"]
    probes["alda"] = ("runnable/alda/trainers/alda_trainer.py", _dataclass_default,
                      {"lr": "actor_lr", "gamma": "discount", "entropy": "init_temperature"})
    if baseline in probes:
        relpath, fn, names = probes[baseline]
        if key in names:
            found = fn(relpath, names[key])
            if found is not None:
                return found, "default"
    return None, ""


def render() -> str:
    fams = _families()
    rows = []
    for baseline in BASELINES:
        family = FAMILY_OF[baseline]
        image, stack = OBSERVATION_GEOMETRY[baseline]
        lr, lr_src = resolve(baseline, "lr")
        gamma, gamma_src = resolve(baseline, "gamma")
        base_c = (fams.get(family, {}).get("constants") or {})
        prod_c = (_resolved(family, "v100").get("constants") or {})
        overlay = ", ".join(f"`{k}` {base_c[k]}&rarr;{prod_c[k]}"
                            for k in prod_c if base_c.get(k) != prod_c.get(k)) or "&mdash;"
        rows.append((
            f"`{baseline}`", f"`{family}`",
            _cell(lr, lr_src), _cell(gamma, gamma_src),
            f"{stack}", f"{image}",
            TIME_LIMIT_HANDLING[baseline],
            REWARD_NORMALIZATION[baseline],
            overlay,
        ))

    head = ("baseline", "family", "learning rate", "discount", "frame stack",
            "render", "time limit", "train reward", "v100 overlay")
    out = [BEGIN, "",
           "**Generated from source by `scripts/generate_fidelity_table.py`. Do not hand-edit.**",
           "`--check` fails when this block stops matching the tree, which is what stops it going",
           "stale the way the prose tables below it did.", "",
           "The `learning rate` and `discount` cells carry their own provenance: `launcher` means an",
           "explicit flag on the exec line, `descriptor` a `families.json` constant that a template",
           "actually references, `cfg yaml` an RL-ViGen config, and **`default` means nobody passes",
           "it** and the clone's own default applies. That last one is not a detail: the IBAC `beta`",
           "incident was a documented 1e-4 that nobody passed, executing as 1.0.", "",
           "`v100 overlay` is what PRODUCTION changes relative to the DataSphere tiers. Two entries",
           "exist in the whole fleet, and both RESTORE each baseline's own upstream parallelism",
           "rather than compromising it.", "",
           "| " + " | ".join(head) + " |",
           "|" + "|".join(["---"] * len(head)) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    out += ["", END]
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help="splice into docs/FAITHFULNESS.md")
    parser.add_argument("--check", action="store_true", help="exit 1 if the spliced block is stale")
    parser.add_argument("--target", default="docs/FAITHFULNESS.md")
    args = parser.parse_args()

    block = render()
    target = ROOT / args.target
    if not (args.write or args.check):
        print(block)
        return 0

    text = target.read_text()
    if BEGIN in text and END in text:
        head, rest = text.split(BEGIN, 1)
        _, tail = rest.split(END, 1)
        new = head + block + tail
    else:
        # First splice goes directly under the title, where a reader lands.
        lines = text.splitlines(keepends=True)
        cut = 1 if lines and lines[0].startswith("#") else 0
        new = "".join(lines[:cut]) + "\n" + block + "\n" + "".join(lines[cut:])

    if args.check:
        if new != text:
            print(f"STALE: {args.target}'s generated block no longer matches the tree.")
            print("Run: python scripts/generate_fidelity_table.py --write")
            return 1
        print(f"{args.target}'s generated block matches the tree.")
        return 0

    target.write_text(new)
    print(f"wrote the generated block into {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
