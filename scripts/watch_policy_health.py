#!/usr/bin/env python3
"""Watch a running cell's policy for saturation or collapse, and say so while it can still matter.

    python scripts/watch_policy_health.py --log <training.log>          # follow a live cell
    python scripts/watch_policy_health.py --log <training.log> --once   # scan and exit

## Why this exists

`notes/PRODUCTION-RUNBOOK.md` lists as **not yet built and worth having before day one**: *"an
alert on `log_std` drift rather than post-hoc inspection."* At 45 hours for the longest cell,
post-hoc means the run is over before anyone knows, and this project's characteristic failure is
one that survives every other check:

> `ibac_sni` at sigma ~ 4.3 -- **perfectly finite**, entropy climbing 9.95 -> 20.03, success 0.00
> throughout.  (`PRODUCTION-RUNBOOK.md:18`)

Finite. Non-crashing. Producing numbers all the way to the end, and none of them worth anything.
A NaN check clears it and a wall-clock check clears it.

## It warns and never kills

Deliberate, and it is the same rule `DECISIONS-IF-PRODUCTION-GOES-WRONG.md` states for the pilots:
*"A method that is faithfully implemented and simply performs badly is a result, not a defect."*
A watchdog that aborted on saturation would silently convert a real, reportable negative result
into a missing cell -- and it would do it to whichever baseline happened to be hardest, which is
the worst possible selection rule. So this emits a marker into the log the archive already returns,
and the decision stays with a person.

## What it measures

`scripts/metrics.py::gaussian_boundary_fraction`, the project's own function, on whatever
`mean_log_std` the cell logs. That is the fraction of sampled action coordinates falling outside
[-1, 1] and being clipped: 0.317 at sigma=1, 0.617 at sigma=2, 0.841 at sigma=5. Its own note fixes
the threshold -- past ~0.6 a head is emitting mostly saturated actions whatever its mean says.

Two markers, both grep-able in a returned `training.log`:

    NATIVE_POLICY_SATURATION_WARNING   boundary fraction past 0.60 and rising
    NATIVE_POLICY_COLLAPSE_WARNING     sigma below 0.05, the opposite failure

Each fires at most once per run. A watcher that repeated itself every thirty seconds for forty
hours would bury the rest of the log, and the second occurrence carries no information the first
did not.
"""
from __future__ import annotations

import argparse
import math
import pathlib
import re
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from metrics import gaussian_boundary_fraction  # noqa: E402

SATURATED_BOUNDARY = 0.60
COLLAPSED_SIGMA = 0.05
RISE = 0.02

#: `mean_log_std` is emitted by several loops in several shapes; accept them all rather than
#: coupling this to one family's formatter.
PATTERNS = [
    # [Claude 2026-09-16] `|` added to every separator class, and it is not cosmetic. idaac writes
    # a pipe-delimited table -- `| train/mean_log_std          | 0.000676 |` -- and the classes
    # here were ["'\s:=] only, so the pattern could not match it. Pointed at a live 3,105-line
    # idaac log this script printed NOTHING and exited 0, which is indistinguishable from "healthy,
    # nothing to report". A watcher that exists to catch a run producing finite, non-crashing,
    # worthless numbers was itself producing a finite, non-crashing, worthless silence.
    #
    # Found by running it against a real cell rather than by reading it. Verified after the fix:
    # the same log yields 7 readings.
    re.compile(r"mean_log_std[\"'\s:=|]+(-?\d+\.?\d*(?:[eE][-+]?\d+)?)"),
    re.compile(r"\bpi_logstd[\"'\s:=|]+(-?\d+\.?\d*(?:[eE][-+]?\d+)?)"),
]


#: Door's action space is Box(-1, 1, (7,)) and every head here is a diagonal Gaussian over it.
ACTION_DIMS = 7
_GAUSS_ENTROPY_PER_DIM = 0.5 * __import__("math").log(2 * __import__("math").pi * __import__("math").e)
#: ibac_sni's torch_rl progress line: `... | H <entropy> | V ...`. It logs entropy, never log_std.
ENTROPY_PATTERN = re.compile(r"\|\s*H\s+(-?\d+\.?\d*(?:[eE][-+]?\d+)?)\s*\|")


def log_std_from_entropy(entropy: float, dims: int = ACTION_DIMS) -> float:
    """Mean log(sigma) of a diagonal Gaussian, recovered from its total entropy.

    H = D * 0.5 * log(2*pi*e) + sum_i log(sigma_i), so mean log(sigma) = (H - D*0.5*log(2*pi*e)) / D.

    [Claude 2026-09-16] Added because this watcher was SILENT on ibac_sni -- the one baseline whose
    documented failure it was written for. PRODUCTION-RUNBOOK records ibac_sni at "sigma ~4.3,
    entropy climbing 9.95 -> 20.03, success 0.00 throughout", and ibac's torch_rl loop logs entropy
    `H` but never a log_std field, so values_in parsed zero readings from a 3,392-line live ibac log.

    Checked against that ground truth before use: H = 20.03 over 7 dims gives
    sigma = exp((20.03 - 9.9326) / 7) = 4.23, against the runbook's recorded ~4.3. It assumes a
    DIAGONAL Gaussian over exactly ACTION_DIMS dimensions; a squashed or categorical head has a
    different entropy and must not be fed through this.
    """
    return (entropy - dims * _GAUSS_ENTROPY_PER_DIM) / dims


def values_in(text: str) -> list[float]:
    out: list[float] = []
    for pattern in PATTERNS:
        for match in pattern.finditer(text):
            try:
                out.append(float(match.group(1)))
            except ValueError:
                pass
    # Only when no direct log_std field exists: a family that logs mean_log_std keeps its direct
    # reading, and the entropy route never overrides it.
    if not out:
        for match in ENTROPY_PATTERN.finditer(text):
            try:
                out.append(log_std_from_entropy(float(match.group(1))))
            except ValueError:
                pass
    return out


def verdicts(series: list[float]) -> list[str]:
    """Return the markers this series earns. Pure, so the thresholds are testable without a log."""
    if len(series) < 4:
        return []
    first, last = series[0], series[-1]
    early = gaussian_boundary_fraction([first])
    late = gaussian_boundary_fraction([last])
    sigma = math.exp(last)
    out = []
    if late > SATURATED_BOUNDARY and late > early + RISE:
        out.append(
            f"NATIVE_POLICY_SATURATION_WARNING boundary_fraction {early:.3f} -> {late:.3f} "
            f"(sigma {sigma:.3f}) past {SATURATED_BOUNDARY}; the head is emitting mostly clipped "
            f"actions. This is the finite-but-useless failure PRODUCTION-RUNBOOK:18 records. "
            f"NOT aborting: a faithfully implemented method performing badly is a result.")
    if sigma < COLLAPSED_SIGMA:
        out.append(
            f"NATIVE_POLICY_COLLAPSE_WARNING sigma {sigma:.5f} below {COLLAPSED_SIGMA}; the policy "
            f"is effectively deterministic and cannot explore. NOT aborting.")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--log", required=True)
    parser.add_argument("--once", action="store_true", help="scan what exists and exit")
    parser.add_argument("--interval", type=float, default=60.0)
    parser.add_argument("--max-seconds", type=float, default=0.0, help="0 = until the log stops")
    args = parser.parse_args()

    log = pathlib.Path(args.log)
    # `ctrl` never writes log_std to training.log -- train_ppo.py:392-396 folds the C61
    # diagnostics into wandb.log, and runnable/_shim/wandb.py sends those to a jsonl sink. Watch
    # both, or this alert is silent for exactly the family whose head has no squashing at all.
    sink = log.parent / "wandb_offline.jsonl"
    fired: set[str] = set()
    started, quiet = time.time(), 0.0
    last_size = -1

    while True:
        text = (log.read_text(errors="replace") if log.is_file() else "")
        if sink.is_file():
            text += "\n" + sink.read_text(errors="replace")
        for marker in verdicts(values_in(text)):
            name = marker.split()[0]
            if name not in fired:
                fired.add(name)
                print(f"=== {marker} ===", file=sys.stderr, flush=True)
        if args.once:
            break
        size = len(text)
        quiet = quiet + args.interval if size == last_size else 0.0
        last_size = size
        # Stop when the cell stops writing; the stall watchdog in run_probe.sh owns the killing.
        if quiet > 1800:
            break
        if args.max_seconds and time.time() - started > args.max_seconds:
            break
        time.sleep(args.interval)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
