#!/usr/bin/env python3
"""Extract a per-family VRAM peak from returned job archives, so the upper-bound rule can be met.

    python scripts/measure_vram_bounds.py <dir> [<dir> ...]
    python scripts/measure_vram_bounds.py --write <dir> ...   # write measured-vram-bounds.json

## Why this exists

`notes/production-host/10-resource-upper-bound-rule.md`: *if you do not know an upper bound on what
you will occupy, do not run it.* Applying that to ourselves produced a blocking finding —
`families.json` records a measured host-RSS peak for every family and a **VRAM figure for none of
them** (idaac's 2.23 GiB exists only inside a prose `memory_note`). So no cell could be started on
a shared GPU: we could not say what it would take.

The data was there the whole time. `datasphere/native/measure_resources.py` samples `nvidia-smi`
throughout every cell and writes `gpu_devices` (per-card `used_memory_mib`) and
`gpu_compute_processes` (per-pid `used_memory_mib`) into each `resources.json`. Nothing ever read
them back. This does.

## Two numbers, and the difference is the whole point

For each cell it reports both:

- **`ours_peak_mib`** — the maximum over samples of the summed `used_memory_mib` of the
  `gpu_compute_processes` belonging to this cell's process tree. This is what OUR run occupies, and
  it is the number that belongs in a bound.
- **`card_peak_mib`** — the maximum `used_memory_mib` on the card, whoever caused it. On an
  exclusive card these coincide; where they do not, something else was resident and `ours` is the
  honest attribution.

Reporting only the card total would silently inflate our bound with someone else's usage; reporting
only ours would hide that the card was shared during the measurement. Both, always.

## What a number here IS and IS NOT

It **is** the observed peak of a specific past run: one profile, one frame budget, one tier's GPU.

It is **not** an upper bound on a different configuration, and it must never be scaled into one.
`ctrl`'s 54.28 GiB host-RAM figure is exactly that mistake already made once — `13.57 × 4`, an
extrapolation from 16 environments to 64, and `families.json` marks it as such. A peak from a 10k
cell on a 23 GiB L4 says nothing certain about a 600k cell on a 32 GiB V100.

So the output carries the frames, the profile and the card for every row, and the summary states
plainly which families still have no measurement at the production configuration. **A row here is
evidence toward a bound, not the bound itself**, and the rule is only satisfied when the intended
configuration has been measured or capped.

## Deliberately NOT written into families.json

`families.json` is a `CONFIG_MEMBER` of the evaluator closure: writing to it moves every family's
evaluator revision and invalidates every attestation. These bounds are operational facts about the
host, not part of what an evaluator computes, so they live in
`datasphere/native/measured-vram-bounds.json` — which is not a closure member and costs no
re-attestation.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "datasphere" / "native" / "measured-vram-bounds.json"

FAMILIES = ("rlvigen", "dmc_gb", "idaac", "alda", "ppg", "ibac_sni", "ctrl")
BASELINE_FAMILY = {
    "drqv2": "rlvigen", "svea": "rlvigen", "sgqn": "rlvigen", "curl": "rlvigen", "drq": "rlvigen",
    "rad": "dmc_gb", "soda": "dmc_gb", "alda": "alda", "idaac": "idaac", "ppg": "ppg",
    "ibac_sni": "ibac_sni", "ctrl": "ctrl",
}


def _cell_identity(cell_dir: pathlib.Path) -> tuple[str | None, str | None, int | None, str | None]:
    """(family, baseline, frames, profile) from the cell's own effective_config.json."""
    cfg = cell_dir / "effective_config.json"
    baseline = frames = profile = None
    if cfg.is_file():
        try:
            data = json.loads(cfg.read_text())
        except json.JSONDecodeError:
            data = {}
        blob = json.dumps(data)
        for name in BASELINE_FAMILY:
            if re.search(rf'"{re.escape(name)}[-:"]', blob):
                baseline = name
                break
        m = re.search(r'"(?:FRAMES|frames)"\s*:\s*"?(\d+)', blob)
        frames = int(m.group(1)) if m else None
        m = re.search(r'"NATIVE_HOST_PROFILE"\s*:\s*"([^"]+)"', blob)
        profile = m.group(1) if m else None
    if baseline is None:
        stem = cell_dir.name.split("-")[0]
        baseline = stem if stem in BASELINE_FAMILY else None
    return (BASELINE_FAMILY.get(baseline or ""), baseline, frames, profile)


def read_cell(resources: pathlib.Path) -> dict | None:
    try:
        data = json.loads(resources.read_text())
    except Exception:
        return None
    samples = data.get("samples") or []
    if not samples:
        return None

    card_peak = 0
    ours_peak = 0
    card_total = 0
    saw_gpu = False
    for sample in samples:
        for dev in sample.get("gpu_devices") or []:
            saw_gpu = True
            card_peak = max(card_peak, int(dev.get("used_memory_mib") or 0))
            card_total = max(card_total, int(dev.get("total_memory_mib") or 0))
        procs = sample.get("gpu_compute_processes") or []
        if procs:
            ours_peak = max(ours_peak, sum(int(p.get("used_memory_mib") or 0) for p in procs))
    if not saw_gpu:
        return None

    family, baseline, frames, profile = _cell_identity(resources.parent)
    return {
        "cell": resources.parent.name,
        "family": family,
        "baseline": baseline,
        "frames": frames,
        "host_profile": profile,
        "ours_peak_mib": ours_peak,
        "card_peak_mib": card_peak,
        "card_total_mib": card_total,
        "samples": len(samples),
        # `gpu_compute_processes` is empty in some archives; then `ours` cannot be attributed and
        # the card total is all there is. Say so rather than passing the card total off as ours.
        "attribution": "per-process" if ours_peak else "card-total-only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dirs", nargs="+")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    rows = []
    for root in args.dirs:
        for res in sorted(pathlib.Path(root).glob("**/resources.json")):
            row = read_cell(res)
            if row:
                rows.append(row)

    if not rows:
        print("no resources.json with GPU samples found. Nothing measured -- which is NOT the "
              "same as nothing to measure.")
        return 1

    print(f"{'cell':22} {'family':9} {'frames':>8} {'ours':>9} {'card':>9} {'of':>7}  attribution")
    best: dict[str, dict] = {}
    for r in sorted(rows, key=lambda x: (-(x["ours_peak_mib"] or 0), x["cell"])):
        print(f"  {r['cell']:20} {str(r['family']):9} {str(r['frames']):>8} "
              f"{r['ours_peak_mib']:>7} Mi {r['card_peak_mib']:>7} Mi "
              f"{r['card_total_mib']:>5} Mi  {r['attribution']}")
        fam = r["family"]
        if fam and (fam not in best or r["ours_peak_mib"] > best[fam]["ours_peak_mib"]):
            best[fam] = r

    print()
    missing = [f for f in FAMILIES if f not in best or not best[f]["ours_peak_mib"]]
    print(f"per-family observed peak (ours), from {len(rows)} cell(s):")
    for fam in FAMILIES:
        r = best.get(fam)
        if r and r["ours_peak_mib"]:
            print(f"  {fam:9} {r['ours_peak_mib']/1024:6.2f} GiB   at {r['frames']} frames, "
                  f"profile={r['host_profile']}, card {r['card_total_mib']/1024:.0f} GiB")
        else:
            print(f"  {fam:9}      --      no attributable measurement")

    print()
    if missing:
        print(f"  {len(missing)} family(ies) still without an attributable VRAM measurement: "
              f"{', '.join(missing)}")
    print("  These are OBSERVED PEAKS OF PAST RUNS, not upper bounds on a different configuration.")
    print("  None was measured at the 600k production budget on a V100. Do not scale them.")

    if args.write:
        OUT.write_text(json.dumps({
            "_comment": [
                "Observed GPU memory peaks per family, extracted from returned job archives by",
                "scripts/measure_vram_bounds.py. NOT part of the evaluator closure -- deliberately",
                "not in families.json, which is a CONFIG_MEMBER whose modification would",
                "invalidate every attestation.",
                "A row is an OBSERVED PEAK of one past configuration. It is evidence toward an",
                "upper bound, never the bound itself, and it must not be scaled to another",
                "configuration -- see notes/production-host/10-resource-upper-bound-rule.md.",
            ],
            "cells": rows,
            "per_family_observed_peak_mib": {
                f: (best[f]["ours_peak_mib"] if f in best else None) for f in FAMILIES},
            "families_without_measurement": missing,
        }, indent=2) + "\n")
        print(f"\n  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
