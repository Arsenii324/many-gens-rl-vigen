#!/usr/bin/env python3
"""Does the value the fidelity table CLAIMS actually reach the process?

    python scripts/audit_executed_hyperparameters.py
    python scripts/audit_executed_hyperparameters.py --baseline ibac_sni

## Why this exists

`docs/FAITHFULNESS.md` records per-baseline hyperparameters as sourced claims -- for example
"`vib_beta: 1e-4` matches CoinRun `[P]`".  On 2026-09-05 external review 8 established that
`runnable/_launch/ibac_sni.sh` passed no `--beta` at all, so `torch_rl/scripts/train.py`'s default
of **1.0** applied: a bottleneck penalty 10,000x the value the table claimed, on the term that is
the whole IBAC mechanism.

The value had been researched, sourced and written down.  It simply never reached the process.

Nothing in this tree looked for that.  `audit_implementations.py` asks whether a MECHANISM is
present; `audit_comparability_seam.py` asks whether an AXIS is uniform; `audit_eval_cadence.py`
asks whether documented cadences match code.  None of them asks the question this file asks:
**for a parameter the project claims a value for, what value does the process actually use?**

## What it can and cannot see

It reads three sources of an executed value, in the order the process would resolve them:

1. an explicit flag on the launcher's `exec` line -- authoritative;
2. a constant in `datasphere/native/families.json` -- authoritative for remote cells;
3. the clone's own `argparse` default -- what applies when nobody passed anything.

Case 3 is the dangerous one and is reported separately as **DEFAULTED**: the claim is only true by
luck, and if the default disagrees with the claim it is **DEFAULTED-MISMATCH**, which is the beta
bug exactly.

It cannot see values set in Python config objects, YAML specs, or computed at runtime.  Those are
reported **UNLOCATED** and are never counted as agreement -- an instrument that cannot run must
not read as one that ran and passed (SYNTHESIS Mechanism 1).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: Claim names in prose do not always equal flag names in code.  Every alias here is a deliberate,
#: auditable mapping rather than a fuzzy match; an unmapped name simply stays UNLOCATED.
ALIASES = {
    "vib_beta": ("beta", "vib_beta"),
    "sni_lambda": ("sni_lambda", "sni_coef"),
    "n_policy_phases": ("n_pi", "n_policy_phases"),
    "num_steps": ("num_steps", "n_steps", "nsteps"),
    "total_frames": ("frames", "total_frames", "num_env_steps"),
    "gamma": ("gamma", "discount"),
    "nstep": ("nstep", "n_step"),
    "entropy_coef": ("entropy-coef", "entropy_coef", "entropy_coeff"),
    "aux_epochs": ("n_aux_epochs", "aux_epochs"),
    "aux_beta_clone": ("beta_clone", "aux_beta_clone"),
}

#: Which clone a baseline's training process lives in.
CLONE = {"ibac_sni": "ibac_sni", "ppg": "ppg", "idaac": "idaac", "ctrl": "ctrl",
         "alda": "alda", "rad": "dmc_gb", "soda": "dmc_gb"}
#: Which LAUNCHER each baseline is started by. The five RL-ViGen natives share one, and without
#: this the audit looked for `drqv2.sh` and found nothing -- so it never saw the hydra overrides
#: that decide what those five actually run, `action_repeat=1` among them.
LAUNCHER_OF = {"drqv2": "rlvigen", "svea": "rlvigen", "drq": "rlvigen",
               "sgqn": "rlvigen", "curl": "rlvigen",
               "rad": "dmc_gb", "soda": "dmc_gb"}


def read(relative: str) -> str:
    path = ROOT / relative
    return path.read_text() if path.is_file() else ""


#: Claims that are not claims about the live production process. They stay in the fidelity
#: document as historical or canonical reference material, but must not be compared with the
#: production launcher's values. Every exclusion is explicit because a heuristic scope filter
#: previously hid real ALDA claims.
EXCLUDED: list[tuple[str, str, str]] = []

#: Claims listed one by one with the reason they are not production-value claims. Adding an entry
#: is a deliberate act and requires a test update in `test_executed_hyperparameters_audit.py`.
EXCLUDED_CLAIMS = {
    ("alda", "num_steps", "2048"):
        "Retired `rlgen/` port setting. Production ALDA uses the runnable spec's "
        "`n_train_steps: 600000` (raised from its prior 500000 2026-09-06, Q55/A64, to match this "
        "project's common production budget); the old `num_steps` claim is not its launch value.",
    ("ctrl", "ctrl_clusters", "32"):
        "Retired `rlgen/` port setting. Production CTRL is the released clone's "
        "`num_clusters=200`; repeated historical table rows are not live claims.",
    ("ctrl", "ctrl_window", "8"):
        "Retired `rlgen/` port terminology. Production CTRL calls this `cluster_len` and "
        "uses the released default 10.",
    ("ctrl", "ctrl_coef", "0.1"):
        "Retired `rlgen/` invented weighted-loss setting. The production CTRL clone has no "
        "`ctrl_coef` knob.",
    ("ctrl", "nstep", "1"):
        "Retired shared-`rlgen` trainer setting; production CTRL uses GAE `n_steps`, not "
        "TD `nstep`.",
    ("ctrl", "nstep", "3"):
        "Retired shared-`rlgen` trainer setting; production CTRL uses GAE `n_steps`, not "
        "TD `nstep`.",
    ("ibac_sni", "sni_lambda", "0.5"):
        "Canonical/reference-only lambda value. The live production torch port implements the "
        "released discrete SNI choices and deliberately exposes no continuous lambda knob; "
        "the no-knob invariant is tested separately.",
    ("sgqn", "aux_update_freq", "2"):
        "Canonical SGQN N_SL reference, not a live RL-ViGen config field. Production SGQN's "
        "config has no update-frequency setting.",
    ("ctrl", "gamma", "0.99"):
        "Retired `rlgen/` port setting. Production CTRL uses the released clone's "
        "`gamma=0.999`; this claim describes the discarded shared trainer.",
    ("sgqn", "aux_beta", "0.9"):
        "Retired `rlgen/` port setting. Production SGQN loads RL-ViGen's config, where "
        "`aux_beta=0.99`; this claim describes the discarded shared trainer.",
}

# Backward-compatible name for notes/tools that imported the old narrower mapping.
LEGACY_CLAIMS = EXCLUDED_CLAIMS


def claims() -> dict[str, list[tuple[str, str]]]:
    """Per baseline, the `name: value` pairs FAITHFULNESS states."""
    EXCLUDED.clear()
    text = read("docs/FAITHFULNESS.md")
    out: dict[str, list[tuple[str, str]]] = {}
    sections = re.split(r"^### `([a-z_0-9]+)`", text, flags=re.MULTILINE)
    for i in range(1, len(sections) - 1, 2):
        name, body = sections[i], sections[i + 1]
        # Blockquoted lines are this document's convention for QUOTED and historical analysis --
        # including correction blocks, which must keep the pre-correction wording findable. Reading
        # them would make the audit permanently red on claims the document has already retracted,
        # and the only way to green it would be deleting the record. Live claims are plain prose.
        live = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith(">"))
        pairs = []
        for match in re.finditer(r"`([a-z_][a-z_0-9]*): ([0-9][0-9a-zA-Z.e_-]*)`", live):
            # A claim whose own sentence names the legacy `rlgen/` path is a statement about that
            # path, not about production. Production runs runnable/_launch/rlvigen.sh, which loads
            # RL-ViGen's own <agent>_config.yaml. Comparing such a claim against the production
            # config would report a mismatch that is really a difference of subject.
            # Scope the exclusion to the SENTENCE the claim sits in, not a fixed character
            # window. A 400-char window silently dropped `alda`'s claims entirely and cut sgqn's
            # from four to one, because those sections mention the legacy path nearby while making
            # claims about production. An over-broad exclusion turns this audit into exactly the
            # kind of instrument it was written to replace.
            key = (name, match.group(1), match.group(2))
            if key in EXCLUDED_CLAIMS:
                EXCLUDED.append(key)
                continue
            pairs.append((match.group(1), match.group(2)))
        if pairs:
            out.setdefault(name, []).extend(pairs)
    return out


def launcher_flags(baseline: str) -> dict[str, str]:
    """Flags explicitly passed on the launcher's exec line."""
    for candidate in (f"runnable/_launch/{LAUNCHER_OF.get(baseline, baseline)}.sh",
                      f"runnable/_launch/{baseline}.sh",
                      f"runnable/_launch/{CLONE.get(baseline, baseline)}.sh"):
        body = read(candidate)
        if not body:
            continue
        match = re.search(r"^exec .*?(?=\n(?!\s))", body, re.MULTILINE | re.DOTALL)
        if not match:
            continue
        line = " ".join(match.group(0).split())
        flags = dict(re.findall(r"--([A-Za-z0-9_-]+)[= ]+([^\s\"']+)", line))
        # HYDRA OVERRIDES, which are `key=value` with no leading dashes. The RL-ViGen five are
        # launched this way -- `rlvigen.sh:78` passes `action_repeat=1` over the config's 2, and
        # line 61 calls that "this project's declared protocol". Parsing only `--flags` made this
        # audit blind to every value those five actually run, which is how I published a wrong
        # correction (CORRECTIONS #35/#36) computed from the config default instead of the override.
        #
        # These take PRECEDENCE over the config file below, because that is the order hydra
        # resolves them in: a command-line override wins over the yaml it overrides.
        for key, value in re.findall(r"(?<![-\w])([a-z_][a-z0-9_]*)=([^\s\"']+)", line):
            if key not in flags and not value.startswith("$"):
                flags[key] = value
        return flags
    return {}


def descriptor_constants(baseline: str) -> dict[str, str]:
    try:
        entry = json.loads(read("datasphere/native/families.json")).get(baseline, {})
    except ValueError:
        return {}
    values = dict(entry.get("constants", {}) or {})
    production = entry.get("production", {}) or {}
    for key, value in production.items():
        if isinstance(value, (int, float, str)):
            values.setdefault(key, str(value))
    return values


#: The RL-ViGen five are not launched with flags: `runnable/_launch/rlvigen.sh:23` picks a WHOLE
#: config file, `<agent>_config.yaml`, and hydra loads it. That file is therefore the authoritative
#: source of an executed value for those baselines -- NOT `configs/vigen.yaml`, which belongs to the
#: legacy `rlgen/` package path and is not what production runs.
RLVIGEN = ("drqv2", "svea", "drq", "sgqn", "curl")


def rlvigen_config_value(baseline: str, name: str) -> tuple[str, str] | None:
    stem = "config" if baseline == "drqv2" else f"{baseline}_config"
    path = ROOT / "RL-ViGen-upstream" / "cfgs" / f"{stem}.yaml"
    if not path.is_file():
        return None
    for line in path.read_text().splitlines():
        hit = re.match(r"\s*" + re.escape(name) + r"\s*:\s*([^\s#]+)", line)
        if hit:
            return hit.group(1), f"{stem}.yaml {name}"
    return None


def argparse_default(baseline: str, flag: str) -> str | None:
    clone = CLONE.get(baseline)
    if not clone:
        return None
    for path in sorted((ROOT / "runnable" / clone).rglob("*.py")):
        try:
            body = path.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        hit = re.search(r'add_argument\(\s*["\']--' + re.escape(flag) +
                        r'["\'][^)]*?default\s*=\s*([^,)\s]+)', body, re.S)
        if hit:
            return hit.group(1).strip()
        # ctrl does not use argparse: train_ppo.py declares its knobs with absl
        # `flags.DEFINE_<type>("name", default, help)`.  Without this branch every ctrl claim reads
        # UNLOCATED, which is honest but blind -- and blind is how the beta defect survived.
        absl = re.search(r'flags\.DEFINE_[a-z]+\(\s*["\']' + re.escape(flag) +
                         r'["\']\s*,\s*([^,)]+)', body)
        if absl:
            return absl.group(1).strip().replace("_", "")
    return None


def python_callable_default(baseline: str, name: str) -> str | None:
    """Read a default from the production callable's signature.

    PPG keeps `beta_clone` in `train_fn` rather than exposing it as an argparse flag.
    Limiting this resolver to the named production entry function avoids treating arbitrary Python
    assignments as executed configuration.
    """
    function = {"ppg": "train_fn"}.get(baseline)
    clone = CLONE.get(baseline)
    if not function or not clone:
        return None
    for path in sorted((ROOT / "runnable" / clone).rglob("*.py")):
        try:
            body = path.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        hit = re.search(
            r"def\s+" + re.escape(function) + r"\s*\((?P<args>.*?)\)\s*:",
            body, re.S)
        if not hit:
            continue
        default = re.search(
            r"(?:^|,)\s*" + re.escape(name) + r"\s*=\s*([^,\n)]+)",
            hit.group("args"))
        if default:
            return default.group(1).strip()
    return None


def same(a: str, b: str) -> bool:
    try:
        return abs(float(a) - float(b)) <= 1e-12 * max(1.0, abs(float(b)))
    except (TypeError, ValueError):
        return str(a).strip().strip("'\"") == str(b).strip().strip("'\"")


def audit(only: str | None = None) -> int:
    rows, worst = [], 0
    for baseline, pairs in sorted(claims().items()):
        if only and baseline != only:
            continue
        flags, constants = launcher_flags(baseline), descriptor_constants(baseline)
        for name, claimed in pairs:
            candidates = ALIASES.get(name, (name, name.replace("_", "-")))
            verdict = source = actual = None
            for candidate in candidates:
                for key in (candidate, candidate.replace("_", "-"), candidate.replace("-", "_")):
                    if key in flags:
                        actual, source = flags[key], f"launcher --{key}"
                        break
                    if key in constants:
                        actual, source = constants[key], f"families.json {key}"
                        break
                if actual is not None:
                    break
            if actual is None and baseline in RLVIGEN:
                for candidate in candidates:
                    found = rlvigen_config_value(baseline, candidate)
                    if found:
                        actual, source = found
                        break
            if actual is None:
                for candidate in candidates:
                    for key in (candidate, candidate.replace("_", "-"), candidate.replace("-", "_")):
                        default = argparse_default(baseline, key)
                        if default is None:
                            default = python_callable_default(baseline, key)
                        if default is not None:
                            actual = default
                            source = (f"DEFAULT of train_fn {key}"
                                      if baseline == "ppg" else f"DEFAULT of --{key}")
                            break
                    if actual is not None:
                        break
                verdict = ("DEFAULTED" if actual is not None and same(actual, claimed)
                           else "DEFAULTED-MISMATCH" if actual is not None else "UNLOCATED")
            else:
                verdict = "AGREES" if same(actual, claimed) else "MISMATCH"
            worst = max(worst, {"AGREES": 0, "DEFAULTED": 1, "UNLOCATED": 1,
                                "MISMATCH": 2, "DEFAULTED-MISMATCH": 2}[verdict])
            rows.append((baseline, name, claimed, actual, source, verdict))

    print("Does the value FAITHFULNESS claims reach the process?\n")
    print(f"  {'baseline':10} {'parameter':18} {'claimed':10} {'executed':12} {'verdict':20} source")
    print("  " + "-" * 100)
    for baseline, name, claimed, actual, source, verdict in rows:
        print(f"  {baseline:10} {name:18} {claimed:10} {str(actual):12} {verdict:20} {source or '-'}")

    print("\n  AGREES             the launcher or descriptor passes the claimed value explicitly")
    print("  DEFAULTED          nobody passes it; the clone's own default happens to match the claim")
    print("  DEFAULTED-MISMATCH nobody passes it and the default DISAGREES -- the beta bug's shape")
    print("  MISMATCH           a value is passed and it is not the claimed one")
    print("  UNLOCATED          not found in launcher, descriptor or argparse. NOT a pass:")
    print("                     it may live in a YAML spec, a config object, or be computed.")
    if EXCLUDED:
        print(f"\n  {len(EXCLUDED)} claim(s) excluded from the production-value audit "
              "(historical or canonical reference material):")
        for baseline, name, value in EXCLUDED:
            print(f"    -- {baseline}.{name} = {value}")
            print(f"       {EXCLUDED_CLAIMS[(baseline, name, value)]}")
    bad = [r for r in rows if r[5] in ("MISMATCH", "DEFAULTED-MISMATCH")]
    if bad:
        print(f"\n  {len(bad)} claim(s) the process does not honour:")
        for baseline, name, claimed, actual, _, verdict in bad:
            print(f"    !! {baseline}.{name}: table says {claimed}, process uses {actual} ({verdict})")
    return 1 if worst >= 2 else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--baseline")
    return audit(ap.parse_args().baseline)


if __name__ == "__main__":
    raise SystemExit(main())
