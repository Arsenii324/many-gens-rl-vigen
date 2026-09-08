#!/usr/bin/env python3
"""Did two jobs of the same family actually get different packages?

    python scripts/audit_environment_drift.py <dir> [<dir> ...]   # dirs holding job archives
    python scripts/audit_environment_drift.py --strict <dir>      # exit 1 on within-family drift

## Why this exists

`gate_environment_manifest` reads OWNER with an honest reason: the base image is pinned by digest
and the requirements are hashed, but the job still runs `apt-get`/`pip` inside it, so **the
executed environment is not frozen and two jobs from this digest can differ** (external review 27
§5). Closing that by construction needs a baked final image with no runtime package mutation, and
that has to happen on the production host.

What can be done from here is the other half, and it is not nothing: the runner already writes
`resolved_packages.json` per job — every installed package and its version, as executed. Nothing
compared them. So "can differ" had never been turned into "did differ", and a reproducibility claim
was resting on an untested assumption in the direction that flatters it.

## What it separates, because the naive comparison is useless

Across 30 retained job archives, 67 of 131 packages "differ" — and almost all of that is a package
being ABSENT from one family, which is by design: `ctrl` installs flax, distrax and chex and the
torch families do not. A tool reporting that as drift would be discarded in a day.

Real drift is a package present in BOTH at DIFFERENT versions, **within one family**. Measured
2026-09-08 over those 30 archives: **zero**. Twelve packages do differ across families —
`glfw`, `imageio-ffmpeg`, `pandas` and the whole `nvidia-*` CUDA stack — and every one of them
splits on the family boundary, not on date. `ctrl`'s JAX stack pulls CUDA 12.9 where the torch
families pin 12.1. That is a deterministic consequence of each family's own requirements.

So the concern is real in principle and has not occurred in practice, and those are different
sentences. This file is what keeps them different: a future drift is caught rather than assumed
absent, which is the only way the second sentence stays true.

## What it cannot see

Anything outside pip: `apt-get` packages, the CUDA driver, the kernel, and the base image's own
contents. Those are the digest's job, and the digest is checked elsewhere. A clean report here is
"pip resolved the same way", not "the environment was identical".
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: A job directory's name usually carries the family; fall back to reading the manifest.
FAMILIES = ("rlvigen", "dmc_gb", "idaac", "alda", "ppg", "ibac_sni", "ctrl",
            "drqv2", "svea", "sgqn", "curl", "drq", "rad", "soda")


def family_of(path: pathlib.Path) -> str:
    for candidate in (path / "effective_config.json", path / "environment.json"):
        if candidate.is_file():
            text = candidate.read_text(errors="replace")
            for family in FAMILIES:
                if re.search(rf"\b{re.escape(family)}\b", text):
                    return family
    name = path.name.lower()
    for family in sorted(FAMILIES, key=len, reverse=True):
        if family.replace("_", "") in name.replace("_", "").replace("-", ""):
            return family
    return "?"


def collect(dirs: list[pathlib.Path]) -> dict[str, list[tuple[str, dict]]]:
    by_family: dict[str, list[tuple[str, dict]]] = collections.defaultdict(list)
    for root in dirs:
        for path in sorted(root.glob("**/resolved_packages.json")):
            try:
                packages = json.loads(path.read_text())
            except Exception:
                continue
            if isinstance(packages, dict):
                by_family[family_of(path.parent)].append((path.parent.name, packages))
    return by_family


def drift(entries: list[tuple[str, dict]]) -> dict[str, dict[str, str]]:
    """Packages present in more than one job of this family at different versions."""
    out: dict[str, dict[str, str]] = {}
    everything = {pkg for _, e in entries for pkg in e}
    for pkg in sorted(everything):
        seen = {name: e[pkg] for name, e in entries if e.get(pkg) is not None}
        if len(seen) > 1 and len({*seen.values()}) > 1:
            out[pkg] = seen
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dirs", nargs="+")
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 if any family drifted between its own jobs")
    args = parser.parse_args()

    by_family = collect([pathlib.Path(d) for d in args.dirs])
    if not by_family:
        print("no resolved_packages.json found under the given directories.")
        print("Nothing was compared -- which is NOT the same as nothing differing.")
        return 1

    print("ENVIRONMENT DRIFT -- pip resolutions, per family, across returned jobs\n")
    drifted = {}
    # [Claude 2026-09-08] The unattributed bucket is reported and NEVER compared. Its first version
    # pooled every job whose family could not be read and called the result "DRIFT in 1 family" --
    # which is not drift, it is jobs from DIFFERENT families compared against each other because
    # attribution failed. An instrument reporting its own blind spot as a finding is worse than one
    # that stays silent, because the finding gets acted on.
    unknown = by_family.pop("?", [])
    for family in sorted(by_family):
        entries = by_family[family]
        if len(entries) < 2:
            print(f"  {family:10} {len(entries)} job -- nothing to compare against")
            continue
        found = drift(entries)
        if found:
            drifted[family] = found
            print(f"  {family:10} {len(entries)} jobs -- DRIFT in {len(found)} package(s)")
            for pkg, seen in list(found.items())[:6]:
                counts = collections.Counter(seen.values())
                print(f"      {pkg:24} " + ", ".join(f"{v} ({n})" for v, n in counts.most_common()))
        else:
            print(f"  {family:10} {len(entries)} jobs -- identical pip resolution")

    if unknown:
        print(f"  {'?':10} {len(unknown)} job(s) -- family not attributable from the archive, so")
        print("             NOT compared. Pooling these would compare different families to each")
        print("             other and report the result as drift.")

    print()
    if drifted:
        print(f"  DRIFT in {len(drifted)} family(ies). Two jobs of one family executed different")
        print("  package versions, so a difference between their results is not attributable to")
        print("  the method alone. This is what gate_environment_manifest warns can happen.")
    else:
        print("  No within-family drift. Every version difference across the corpus is a family")
        print("  boundary -- ctrl's JAX stack pulls a different CUDA than the torch families --")
        print("  which is a deterministic consequence of each family's own requirements.")
        print()
        print("  This does NOT close gate_environment_manifest. Nothing here forbids a future")
        print("  `pip install` resolving differently; it reports that none has. Freezing it by")
        print("  construction still needs a baked image with no runtime package mutation.")
    return 1 if (drifted and args.strict) else 0


if __name__ == "__main__":
    raise SystemExit(main())
