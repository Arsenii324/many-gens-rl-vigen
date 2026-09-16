#!/usr/bin/env python3
"""For each of the twelve baselines: what does a production cell need, and can this host give it?

    python scripts/campaign_feasibility.py                  # the table
    python scripts/campaign_feasibility.py --host           # read the live cards too
    python scripts/campaign_feasibility.py --strict         # exit 1 if any baseline is BLOCKED

## Why this exists

`campaign_status.py` answers "what is DONE" and reports 35 of 36 cells MISSING. It cannot answer
the question anyone actually asks next -- **why** -- and the reasons are not the same reason:

- `svea`, `sgqn`, `soda` are blocked on an ASSET that was never fetched. No amount of GPU fixes it.
- `ctrl` needs 32,435 MiB and cannot satisfy peak-plus-floor on a 32,494 MiB card AT ALL.
- `ibac_sni` has no measured footprint, because six attempts were stood down before it settled.
- Five baselines have no production record and **no blocker at all** -- they were simply never
  attempted, which is a different fact and deserves to look different.

Reporting those four situations as one word is how "35 MISSING" becomes a number nobody can act
on. This separates them, from measurements the repository already holds.

## Every number here is traced, and unmeasured says unmeasured

VRAM comes from `measured-vram-bounds.json`, disk from `family.py disk-requirement --profile v100`,
the asset dependency from `family.PLACES365_BASELINES`. Where a figure does not exist, the row says
UNMEASURED rather than substituting an estimate -- this project spent a day on three wrong VRAM
numbers, one of which was an estimate written in a comment and later quoted as a measurement.

## The launch criterion, and the version of it that was wrong

A multi-hour cell is worth starting only if it survives the co-tenant's PEAK, not the co-tenant's
current state. `rlvigen_kalugin_df` holds ~21.3 GiB and cycles within tens of minutes; a cell sized
against momentary free memory died twice on 2026-09-16, once at 41% and once eight minutes in.

**The first version of this file got the arithmetic wrong**, and running it is what showed that.
It computed `window = peak + floor + co-tenant hold` and compared that to CURRENT free memory --
which double-counts whenever the co-tenant is already resident, because their hold is already
subtracted from `free`. It reported ppg as needing 32,446 MiB on a 32,494 MiB card, and idaac as
unschedulable while a card sat with 9,190 MiB free and idaac needs 6,638.

The correct form asks what the card can durably give US:

    capacity(card) = card total - the co-tenant's PEAK hold on that card - floor
    runnable       = family peak <= capacity(card)

The co-tenant's peak is the honest unknown. It is estimated as `card total - free - ours` at the
moment of reading, which UNDERSTATES it whenever they are between cycles -- so the number is a
lower bound on their hold and therefore an upper bound on our capacity. The row says so.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "datasphere" / "native"))

#: Measured 2026-09-16: two processes of `rlvigen_kalugin_df`, which cycles within tens of minutes.
CO_TENANT_HOLD_MIB = 21_300
#: The launcher's own floor. Never waived, never lowered.
FLOOR_MIB = 4_000
#: One eval cell, measured: 841 MiB, one core, 2.1 GiB RAM.
EVAL_CELL_MIB = 841


#: One V100 as nvidia-smi reports memory.total. used+free sums to ~32,494; the ~274 MiB gap is
#: reserved, so capacity arithmetic uses the used+free figure an operator can actually observe.
CARD_TOTAL_MIB = 32_494


def _our_mib() -> dict[int, int]:
    """MiB held by OUR cell containers, per card, so the co-tenant estimate excludes us."""
    out = {0: 0, 1: 0}
    try:
        res = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20",
             "varaksin_as@100.98.2.11",
             "for c in $(docker ps --format '{{.Names}}' | grep -E '^cell-c[01]-[0-9]+$'); do "
             "card=${c#cell-c}; card=${card%%-*}; "
             "for p in $(docker top $c 2>/dev/null | awk 'NR>1{print $2}'); do "
             "m=$(nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader,nounits "
             "| awk -F, -v P=$p '$1+0==P{print $2+0}'); "
             "[ -n \"$m\" ] && echo \"$card $m\"; done; done"],
            capture_output=True, text=True, timeout=60)
        for line in res.stdout.splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                out[int(parts[0])] = out.get(int(parts[0]), 0) + int(parts[1])
    except Exception:
        pass
    return out


def _bounds() -> dict[str, int]:
    path = ROOT / "datasphere" / "native" / "measured-vram-bounds.json"
    return json.loads(path.read_text()).get("per_family_observed_peak_mib", {})


def _disk_gib(cells: str) -> float | None:
    try:
        out = subprocess.run(
            [sys.executable, str(ROOT / "datasphere" / "native" / "family.py"),
             "disk-requirement", "--cells", cells, "--frames", "600000", "--profile", "v100"],
            capture_output=True, text=True, timeout=120, cwd=ROOT)
        return json.loads(out.stdout).get("required_gib")
    except Exception:
        return None


def _host_free() -> tuple[int, int] | None:
    try:
        out = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20",
             "varaksin_as@100.98.2.11",
             "nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=60)
        vals = [int(v) for v in out.stdout.split() if v.strip().isdigit()]
        return (vals[0], vals[1]) if len(vals) >= 2 else None
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--host", action="store_true", help="also read the live cards")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any baseline is BLOCKED")
    args = ap.parse_args()

    import family
    from evaluator_identity import FAMILY_ALLOWED_BASELINES

    bounds = _bounds()
    fam_of = {b: f for f, bs in FAMILY_ALLOWED_BASELINES.items() for b in bs}
    free = _host_free() if args.host else None
    ours = _our_mib() if args.host else {0: 0, 1: 0}
    capacity = None
    if free:
        capacity = {}
        for idx, f in enumerate(free):
            cotenant = max(0, CARD_TOTAL_MIB - f - ours.get(idx, 0))
            capacity[idx] = max(0, CARD_TOTAL_MIB - cotenant - FLOOR_MIB)

    print("CAMPAIGN FEASIBILITY -- what a 600k cell needs, and whether this host can give it\n")
    if free and capacity:
        for idx in sorted(capacity):
            cot = max(0, CARD_TOTAL_MIB - free[idx] - ours.get(idx, 0))
            print(f"  card {idx}: {free[idx]} MiB free, co-tenants ~{cot} MiB, "
                  f"capacity for us {capacity[idx]} MiB (card {CARD_TOTAL_MIB} - co-tenants - "
                  f"{FLOOR_MIB} floor)")
    print(f"\n  A co-tenant peak read while they are between cycles UNDERSTATES their hold, so"
          f"\n  every capacity above is an UPPER bound on what we can durably take.\n")
    print(f"  {'baseline':10} {'family':9} {'peak MiB':>9} {'need':>8} {'disk GiB':>9}  verdict")

    blocked = []
    for baseline in sorted(fam_of):
        fam = fam_of[baseline]
        peak = bounds.get(fam)
        disk = _disk_gib(f"{baseline}:101")
        needs_places = baseline in family.PLACES365_BASELINES

        need = None if peak is None else peak + FLOOR_MIB
        if peak is None:
            verdict = "UNMEASURED -- no VRAM figure; cannot be sized, so cannot be scheduled"
        elif need > CARD_TOTAL_MIB:
            verdict = "NEEDS AN EMPTY CARD -- peak+floor exceeds one whole card, and a floor decision"
        elif capacity is not None:
            best = max(capacity.values())
            where = max(capacity, key=lambda k: capacity[k])
            if need <= best:
                verdict = f"RUNNABLE on card {where} -- needs {need}, capacity {best}"
            else:
                verdict = f"WAIT -- needs {need} MiB, best card capacity {best}"
        else:
            verdict = f"needs {need} MiB beside the co-tenant's peak"
        if needs_places:
            verdict = "BLOCKED ON ASSET -- Places365 corpus absent; the host holds the 20-class fixture"
        if peak is None or needs_places or "EMPTY CARD" in verdict:
            blocked.append(baseline)

        pk = f"{peak}" if peak else "--"
        wd = f"{need}" if need else "--"
        dk = f"{disk:.1f}" if disk else "--"
        print(f"  {baseline:10} {fam:9} {pk:>9} {wd:>8} {dk:>9}  {verdict}")

    print()
    print(f"  An EVAL cell is {EVAL_CELL_MIB} MiB and coexists with the co-tenant; eleven completed")
    print("  on card 0 on 2026-09-16 while co-tenants held 26 GiB of it. Where a baseline already")
    print("  has retained checkpoints, evaluation is available even when training is not.")
    print()
    if blocked:
        print(f"  {len(blocked)} baseline(s) cannot be scheduled by adding GPU time alone: "
              f"{', '.join(blocked)}")
        print("  Those are asset, card-size and measurement problems, not queue problems.")
    return 1 if (blocked and args.strict) else 0


if __name__ == "__main__":
    raise SystemExit(main())
