#!/usr/bin/env python3
"""Apply the frame-stack pilots' PREDECLARED criterion to a returned cell.

    python scripts/read_stack_pilot.py --cell <dir>            # one extracted cell
    python scripts/read_stack_pilot.py --cell <dir> --strict   # exit 1 if INDICTED

## Written before the results exist, and that is the point

`notes/DECISIONS-IF-PRODUCTION-GOES-WRONG.md` requires a short cell for `ctrl` and `ibac_sni`
before three production seeds, because A40-REVISED-2 raised both from `frame_stack=1` to 3 on
2026-09-08 by AUTHORING stacking code on a path that had none. It states the criterion as
*non-degenerate learning* -- finite losses, a non-collapsed action distribution, some separation
from the floor -- and says explicitly:

> A method that is faithfully implemented and simply performs badly is a result, not a defect.

That sentence is the whole reason this file exists rather than a person reading a log. A criterion
applied after seeing the numbers is a criterion fitted to them, and the temptation with a
disappointing pilot is to decide afterwards which quantity mattered. So the thresholds below are
committed while all five jobs are still EXECUTING and no pilot has returned anything.

## The four checks, and why these and not a score

1. **FINITE.** No NaN or inf in any logged loss. Cheap, and it is the check that does NOT catch the
   failure that actually happened -- see 2.

2. **NOT SATURATED.** `notes/PRODUCTION-RUNBOOK.md:18` records the real failure: `ibac_sni` sat at
   sigma ~ 4.3 with entropy climbing 9.95 -> 20.03 and success 0.00 throughout, **perfectly finite
   the entire time**. So finiteness is necessary and nowhere near sufficient. The quantity that
   moves first is `mean_log_std`, and its consequence is
   `scripts/metrics.py::gaussian_boundary_fraction` -- the fraction of sampled coordinates that
   land outside [-1, 1] and get clipped. That file's own note fixes the threshold: 0.317 at
   sigma=1, 0.617 at sigma=2, and *"a head whose boundary fraction is climbing past ~0.6 is
   emitting mostly saturated actions whatever its mean says."* Past 0.6 AND rising is the
   indictment.

3. **NOT COLLAPSED.** The opposite failure: sigma driven to zero leaves a deterministic policy that
   cannot explore. Flagged below `sigma < 0.05`.

4. **SEPARATION FROM THE FLOOR.** Door's measured random floor is 1.842 (C55, 200 episodes) with a
   standard deviation of 2.839 -- which is why this is the WEAKEST of the four and is reported as
   information rather than as a gate. A random policy can reach 6.93 on that measurement, so at
   102400 frames -- between 0.06% and 2.5% of these two baselines' own training horizons -- a
   return near the floor indicts nothing at all.

## What a verdict means

PASS is "nothing here says the authored stacking code is broken", not "the method works". The only
outcome that blocks production seeds is INDICTED on check 2 or 3, because those are the two that
say the policy stopped being a controller. A43 predeclared the disambiguation if `ibac_sni` is
indicted: revert its `lr` first, re-pilot, and if the failure survives that it is the stack.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from metrics import gaussian_boundary_fraction  # noqa: E402

#: `docs/CONSTRUCTION.md` C55, 200 episodes.
DOOR_RANDOM_FLOOR = 1.842
DOOR_FLOOR_SD = 2.839

SATURATED_BOUNDARY = 0.60      # scripts/metrics.py's own stated threshold
COLLAPSED_SIGMA = 0.05
TAIL_FRACTION = 0.25           # the last quarter of the curve is "late"


def _floats(text: str, pattern: str) -> list[float]:
    out = []
    for match in re.finditer(pattern, text):
        try:
            out.append(float(match.group(1)))
        except ValueError:
            pass
    return out


def _wandb_sink(cell: pathlib.Path) -> dict[str, list[float]]:
    """`wandb_offline.jsonl`, which for `ctrl` is the ONLY place `mean_log_std` exists.

    [Claude 2026-09-08] Found before the ctrl pilot returned, not after. `train_ppo.py:392-396`
    folds the C61 policy-health diagnostics into the dict it hands `wandb.log`, and
    `runnable/_shim/wandb.py` writes those to a jsonl sink -- never to `training.log` and never to
    a `.csv`. So both of this file's original readers would have missed ctrl's log_std entirely and
    reported UNREADABLE on the one check the pilot exists for, which reads as "not cleared" rather
    than "not looked at" only because that distinction was built in deliberately.
    """
    out: dict[str, list[float]] = {}
    for path in cell.glob("**/wandb_offline.jsonl"):
        for line in path.read_text(errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = row.get("data") if isinstance(row.get("data"), dict) else row
            if not isinstance(payload, dict):
                continue
            for key, value in payload.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    # keys are namespaced like `Door/train/mean_log_std`; keep the leaf
                    out.setdefault(key.rsplit("/", 1)[-1], []).append(float(value))
    return out


def _series(cell: pathlib.Path) -> dict[str, list[float]]:
    """Pull whatever the family happens to log. ctrl writes a wandb sink, ibac_sni a CSV."""
    series: dict[str, list[float]] = dict(_wandb_sink(cell))
    csv_path = next(iter(cell.glob("**/log.csv")), None)
    if csv_path is not None:
        with csv_path.open() as handle:
            rows = list(csv.DictReader(handle))
        for key in (rows[0].keys() if rows else []):  # CSV wins where both exist
            values = []
            for row in rows:
                try:
                    values.append(float(row[key]))
                except (TypeError, ValueError):
                    pass
            if values:
                series[key] = values
        return series

    text = "\n".join(p.read_text(errors="replace")
                     for p in cell.glob("**/*.log") if p.is_file())
    for name, pattern in (
        ("return", r"(?:rreturn_mean|R:|return[^\d\-]{0,12})\s*([\-\d.]+)"),
        ("entropy", r"entropy[^\d\-]{0,12}([\-\d.]+)"),
        ("mean_log_std", r"(?:mean_)?log_std[^\d\-]{0,12}([\-\d.]+)"),
        ("policy_loss", r"(?:policy_loss|pi_loss|Opt/loss_policy)[^\d\-]{0,12}([\-\d.]+)"),
        ("value_loss", r"(?:value_loss|vf_loss|Opt/loss_value)[^\d\-]{0,12}([\-\d.]+)"),
    ):
        found = _floats(text, pattern)
        if found:
            series[name] = found
    return series


def _pick(series: dict[str, list[float]], *names: str) -> list[float]:
    for name in names:
        for key in series:
            if key.lower() == name or name in key.lower():
                return series[key]
    return []


def _tail(values: list[float]) -> list[float]:
    if not values:
        return []
    cut = max(1, int(len(values) * TAIL_FRACTION))
    return values[-cut:]


def read(cell: pathlib.Path) -> tuple[list[tuple[str, str, str]], bool]:
    series = _series(cell)
    if not series:
        return [("PARSE", "INDICTED", f"no curve found under {cell}")], True

    checks: list[tuple[str, str, str]] = []
    indicted = False

    # 1 -- finite. LOSSES, not every logged series.
    #
    # [Claude 2026-09-08] The first version checked everything and indicted a real, healthy ctrl
    # cell (bt1d8jicbkdu1jv87ogp) on `ep_return_200` and `ep_return_all` -- running episode-return
    # accumulators that are NaN until the first episode finishes. That is a startup artifact, and
    # an instrument that indicts every cell for it would have been discarded within a day, taking
    # the checks that matter with it.
    #
    # The criterion in DECISIONS-IF-PRODUCTION-GOES-WRONG is "finite LOSSES". Non-finite values
    # elsewhere are still reported, as information, because a NaN in a return accumulator LATE in
    # a run is a different thing from one at step 0 -- and silently dropping them would trade one
    # wrong answer for another.
    def _bad(keys):
        return sorted(k for k in keys
                      if any(math.isnan(x) or math.isinf(x) for x in series[k]))

    loss_keys = [k for k in series if "loss" in k.lower() or "grad_norm" in k.lower()]
    other_keys = [k for k in series if k not in loss_keys]
    bad_losses, bad_other = _bad(loss_keys), _bad(other_keys)

    if bad_losses:
        checks.append(("FINITE", "INDICTED", f"non-finite LOSS series: {', '.join(bad_losses)}"))
        indicted = True
    else:
        note = f"{len(loss_keys)} loss series, all finite"
        if bad_other:
            first_nan = {}
            for k in bad_other:
                v = series[k]
                idx = next(i for i, x in enumerate(v) if math.isnan(x) or math.isinf(x))
                first_nan[k] = f"{k} (first at row {idx} of {len(v)})"
            note += ("; non-finite elsewhere, NOT indicted: "
                     + ", ".join(first_nan[k] for k in bad_other[:3])
                     + " -- accumulators are NaN before the first episode completes")
        checks.append(("FINITE", "pass", note))

    # 2 -- saturation. The failure that finiteness does not catch.
    log_std = _pick(series, "mean_log_std", "log_std")
    if log_std:
        early = gaussian_boundary_fraction([log_std[0]])
        late_values = _tail(log_std)
        late = gaussian_boundary_fraction([sum(late_values) / len(late_values)])
        sigma_late = math.exp(sum(late_values) / len(late_values))
        rising = late > early + 0.02
        if late > SATURATED_BOUNDARY and rising:
            checks.append(("NOT SATURATED", "INDICTED",
                           f"boundary fraction {early:.3f} -> {late:.3f} (sigma {sigma_late:.2f}); "
                           f"past {SATURATED_BOUNDARY} and rising -- saturated noise, not control"))
            indicted = True
        else:
            checks.append(("NOT SATURATED", "pass",
                           f"boundary fraction {early:.3f} -> {late:.3f} (sigma {sigma_late:.2f})"))
        # 3 -- collapse
        if sigma_late < COLLAPSED_SIGMA:
            checks.append(("NOT COLLAPSED", "INDICTED",
                           f"sigma {sigma_late:.4f} < {COLLAPSED_SIGMA}; policy is effectively "
                           "deterministic and cannot explore"))
            indicted = True
        else:
            checks.append(("NOT COLLAPSED", "pass", f"sigma {sigma_late:.3f}"))
    else:
        checks.append(("NOT SATURATED", "UNREADABLE",
                       "no log_std series -- this is the check that catches the finite-but-useless "
                       "failure, so a cell without it is not cleared, merely unexamined"))

    # 4 -- separation. Information, deliberately not a gate.
    returns = _pick(series, "return", "rreturn_mean", "eprewmean")
    if returns:
        late_values = _tail(returns)
        mean_late = sum(late_values) / len(late_values)
        margin = (mean_late - DOOR_RANDOM_FLOOR) / DOOR_FLOOR_SD
        checks.append(("SEPARATION (informational)", "info",
                       f"late-window return {mean_late:.2f} vs floor {DOOR_RANDOM_FLOOR} "
                       f"({margin:+.2f} floor-sd). Not a gate: a random policy reaches 6.93 on "
                       "that measurement, and this is <2.5% of either baseline's own horizon"))
    else:
        checks.append(("SEPARATION (informational)", "info", "no return series parsed"))

    return checks, indicted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cell", required=True, help="an extracted cell directory")
    parser.add_argument("--strict", action="store_true", help="exit 1 if INDICTED")
    args = parser.parse_args()

    cell = pathlib.Path(args.cell)
    checks, indicted = read(cell)

    print(f"FRAME-STACK PILOT -- {cell}\n")
    for name, status, detail in checks:
        print(f"  {status.upper():10} {name}")
        print(f"             {detail}")
    print()
    if indicted:
        print("  VERDICT: INDICTED. Do not start production seeds for this baseline.")
        print("  For ibac_sni, A43 predeclared the order: revert `lr` first, re-pilot; if the")
        print("  failure survives that, it is the stack.")
    else:
        print("  VERDICT: nothing here says the authored stacking code is broken.")
        print("  That is NOT a claim the method works -- a faithfully implemented method that")
        print("  simply performs badly is a result, not a defect.")
    return 1 if (indicted and args.strict) else 0


if __name__ == "__main__":
    raise SystemExit(main())
