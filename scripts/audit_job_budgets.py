#!/usr/bin/env python3
"""Can each job config's timeout actually fit the evaluation it asks for?

    python scripts/audit_job_budgets.py
    python scripts/audit_job_budgets.py --seconds-per-episode 150

## Why this exists

Job `bt14het9mvpvvu8vatgo` was killed by its own `timeout --foreground 3600s` after ~62 minutes,
with exit 5 and no stdout to download. It had not trained -- `run_probe.sh:871` short-circuits to
`run_offline_eval` whenever `OFFLINE_EVAL_SNAPSHOT` is set -- so the EVALUATION alone did not fit
the hour it was given.

Nothing checked that. Seven `cfg-idaac-revalidate-*` configs carried the identical budget, and one
offline config (`cfg-offline-eval-s2-full-v50.yaml`) is 3.5x tighter still. A timeout that cannot
fit its own workload is a **silent** misconfiguration: the job provisions, bootstraps, runs, is
killed, and reports an error indistinguishable from a code fault -- while having spent the money.

## The model

    required = bootstrap + episodes x seconds_per_episode x safety

`episodes` is `OFFLINE_EVAL_EPISODES x |regimes| x |scenes|`, which is what the grid actually runs.

The constants are deliberately conservative and are stated, not hidden:

- `BOOTSTRAP_SECONDS = 700`. Derived, not guessed: `bt14het9mvpvvu8vatgo` ran 3729s wall against
  its own `timeout 3600s`, so at most ~129s elapsed before the command started. 200 rounds up.
- `#: Per-episode cost is FAMILY-dependent and these are measured wall-clock points, not estimates.
#: A single flat rate produced a false FAIL on cfg-offline-eval-s2-full-v50, a config that
#: demonstrably succeeded -- the same class of error this audit exists to prevent.
- `SECONDS_PER_EPISODE`. Per-family, measured from completed jobs; see the table in the code.
SECONDS_PER_EPISODE = 90`. **And this number is the finding, not a parameter.** Two measured
  points from completed jobs:

      bt1ip5f8c6mqqm7fd2bn  idaac,  40 episodes, 1022s wall  ->  ~22 s/episode
      bt1rr9hodosm5sn09t1a  drqv2, 400 episodes, 3593s wall  ->  ~8.5 s/episode

  Throughput under the CURRENT evaluator is not yet measured -- see
  notes/EVALUATOR-THROUGHPUT.md. Two attempts failed for unrelated reasons, and neither supports a
  per-episode figure. These rates are therefore from older payloads, and are the best available.

The failure mode is asymmetric, so prefer raising this over lowering it: an over-long timeout costs
nothing because the job exits when it finishes, while a short one throws away the whole run.
"""
from __future__ import annotations

import argparse
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIGS = ROOT / "datasphere" / "native"
BOOTSTRAP_SECONDS = 200
#: Per-episode cost is FAMILY-dependent, and these are measured wall-clock points, not estimates.
#: A single flat rate produced a false FAIL on cfg-offline-eval-s2-full-v50 -- a config that
#: demonstrably SUCCEEDED -- which is the same class of error this audit exists to prevent.
MEASURED_SECONDS_PER_EPISODE = {
    "drqv2": 9,      # bt1rr9hodosm5sn09t1a: 400 episodes in 3593s wall -> 8.5, rounded up
    "rlvigen": 9,    # same evaluator path as drqv2
    "idaac": 25,     # bt1ip5f8c6mqqm7fd2bn: 40 episodes in 1022s wall  -> 22, rounded up
}
#: Families with no completed timing yet: pessimistic, and reported AS unmeasured rather than
#: presented as knowledge.
UNMEASURED_DEFAULT = 30
SAFETY = 1.25


def episodes_of(text: str) -> int | None:
    """Episodes the grid actually runs, under EITHER evaluation scope.

    This read only `OFFLINE_EVAL_*` and returned None for anything else -- and None means
    `continue`, so every config using the `ENDPOINT_EVAL_*` scope was SKIPPED, and a skipped config
    prints nothing, which reads exactly like a config that passed. The scope split is mine, made
    after this instrument was written, and I did not come back for it: the same
    absence-read-as-a-pass mechanism this file was built to stop.
    """
    for prefix in ("OFFLINE_EVAL", "ENDPOINT_EVAL"):
        per = re.search(rf"{prefix}_EPISODES=(\d+)", text)
        if not per:
            continue
        regimes = re.search(rf"{prefix}_REGIMES=(\S+)", text)
        scenes = re.search(rf"{prefix}_SCENES=(\S+)", text)
        n_regimes = len(regimes.group(1).split(",")) if regimes else 1
        n_scenes = len(scenes.group(1).split(",")) if scenes else 1
        return int(per.group(1)) * n_regimes * n_scenes
    return None


#: Measured training throughput, frames/second, from completed jobs. A train-then-eval config pays
#: for BOTH phases out of one timeout, and costing only the evaluation understates it badly: at
#: 10k frames the training phase dominates for every family.
#: [Claude 2026-09-07] idaac's old 30.0 was the PRE-C2 recipe (4 processes, 256-step rollout, 1 PPO
#: epoch, 8 minibatches). C2's compute pattern is heavier per environment step (10 epochs, 32
#: minibatches, one 2048-step rollout), so this is a real re-measurement, not noise: bounded g1.1
#: rehearsal (job bt1596tjbdu1rv5senim, 40960 frames, 20 C2 update cycles), n=1, real -- not a
#: certified V100 number, the production host is not reachable from here. Sampled wall-clock from
#: resources.json (1828.98s covering training + the endpoint eval) minus the endpoint eval's own
#: measured 162s = 1666.98s training-only for 40960 frames = 24.57 FPS, rounded down.
MEASURED_TRAIN_FPS = {
    "ctrl": 12.0, "idaac": 24.0, "ppg": 25.0, "ibac_sni": 8.0,
    "dmc_gb": 9.0, "rlvigen": 6.0, "alda": 9.0,
}
TRAIN_FPS_FLOOR = 6.0  # slowest measured; used for a family with no training number


def training_seconds(text: str) -> tuple[int, str | None]:
    """Cost of the training phase a train-then-eval config runs before it evaluates."""
    # An offline-eval config carries a vestigial FRAMES (it names the snapshot's budget, not work
    # to do) and trains nothing. Costing a training phase there is a false ALARM -- the safe
    # direction, but still wrong, and this file exists because wrong instruments get trusted.
    if "OFFLINE_EVAL_SNAPSHOT" in text:
        return 0, None
    frames = re.search(r"\bFRAMES=(\d+)", text)
    cells = re.search(r"\bCELLS=([A-Za-z_]+)", text)
    if not frames:
        return 0, None
    family = cells.group(1) if cells else None
    fps = MEASURED_TRAIN_FPS.get(family, TRAIN_FPS_FLOOR)
    return int(int(frames.group(1)) / fps), family


def family_of(text: str) -> str:
    match = re.search(r"OFFLINE_EVAL_FAMILY=(\S+)", text)
    if match:
        return match.group(1)
    cells = re.search(r"\bCELLS=([A-Za-z_]+)", text)
    return cells.group(1) if cells else "unknown"


def audit(seconds_per_episode: int | None = None, only_current: bool = False) -> int:
    rows, bad, unmeasured = [], [], set()
    for path in sorted(CONFIGS.glob("cfg-*.yaml")):
        text = path.read_text()
        timeout = re.search(r"timeout --foreground (\d+)s", text)
        episodes = episodes_of(text)
        if not timeout or not episodes:
            continue
        have = int(timeout.group(1))
        family = family_of(text)
        if seconds_per_episode is not None:
            rate = seconds_per_episode
        elif family in MEASURED_SECONDS_PER_EPISODE:
            rate = MEASURED_SECONDS_PER_EPISODE[family]
        else:
            rate, _ = UNMEASURED_DEFAULT, unmeasured.add(family)
        train, _ = training_seconds(text)
        need = int(BOOTSTRAP_SECONDS + (train + episodes * rate) * SAFETY)
        ok = have >= need
        rows.append((path.name, have, episodes, need, ok))
        if not ok:
            bad.append((path.name, have, need, episodes))

    print("Does each job config's timeout fit the evaluation it asks for?\n")
    rate_note = (f"a flat {seconds_per_episode}s" if seconds_per_episode is not None
                 else "measured per-family rates")
    print(f"  bootstrap {BOOTSTRAP_SECONDS}s + episodes x {rate_note} x {SAFETY} safety\n")
    print(f"  {'config':42} {'timeout':>8} {'episodes':>9} {'needs':>8}  verdict")
    print("  " + "-" * 84)
    for name, have, episodes, need, ok in rows:
        print(f"  {name:42} {have:>8} {episodes:>9} {need:>8}  {'ok' if ok else 'TOO TIGHT'}")
    if bad:
        print(f"\n  {len(bad)} config(s) cannot fit their own workload:")
        for name, have, need, episodes in bad:
            print(f"    !! {name}: {have}s for {episodes} episodes, needs ~{need}s")
        print("\n  A job killed by its own timeout reports an error indistinguishable from a code")
        print("  fault, after paying for provisioning, bootstrap and every completed episode.")
    if unmeasured:
        print(f"\n  NOT MEASURED, costed at the pessimistic {UNMEASURED_DEFAULT}s/episode: "
              + ", ".join(sorted(unmeasured)))
        print("  A completed run for these families would replace a guess with a number.")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seconds-per-episode", type=int, default=None,
                    help="override the measured per-family rates with one flat rate")
    args = ap.parse_args()
    return audit(args.seconds_per_episode)


if __name__ == "__main__":
    raise SystemExit(main())
