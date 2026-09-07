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

- `BOOTSTRAP_SECONDS = 620`. Measured, and it had been wrong in two ways at once. The code used
  200, inferred from `bt14het9mvpvvu8vatgo` running 3729s wall against its own `timeout 3600s`
  ("at most ~129s elapsed before the command started") -- a job with a far smaller dependency
  closure than the fleet's. This docstring simultaneously claimed 700. The two disagreed for as
  long as both existed, and the prose number is the one that gets quoted. The soda attestation
  canary `bt1f8b5gb39jgadqngke` settles it by arithmetic anyone can re-run: its in-cell log
  accounts for 2993.8s of a 3600s wall, leaving 606.2s of image pull, apt/pip bootstrap and
  payload extraction before the first training line. 620 rounds that up.
- `PLACES365_LOAD_SECONDS = 600`, charged to `svea`, `sgqn` and `soda` only. The one-time
  surcharge the first overlay episode pays inside `_load_places`. Measured on the same canary:
  episode 3 took 732.9s against a 171.1s steady state, so ~561.8s.

  **It is constant in dataset size, not linear**, and that distinction is the whole reason the
  number is safe to carry. The fixture's train split is 1,000 images and `ImageFolder`'s directory
  scan measures ~2 us/image, so the scan is at most a few seconds of the 561.8s; the rest is
  DataLoader worker startup (`num_workers=16`) plus the first decoded batch. The production split
  is ~1.8M images -- had this cost been per-image it would have extrapolated to roughly 7.7 hours
  per cell, and every svea/sgqn/soda budget in the fleet would have been unrunnable.
- `SECONDS_PER_EPISODE`. Per-family, measured from completed jobs; see the table in the code.
  Two of the original measured points:

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
# Measured on bt1f8b5gb39jgadqngke: 3600s wall - 2993.8s of in-cell log = 606.2s. See the
# docstring; the previous 200 was inferred from a job with a much smaller dependency closure.
BOOTSTRAP_SECONDS = 620
#: The first overlay episode's one-time `_load_places` cost, for the three Places365
#: baselines. Measured 561.8s on the same canary, and CONSTANT in image count -- see the
#: docstring for why that is established rather than assumed.
PLACES365_LOAD_SECONDS = 600
PLACES365_BASELINES = ("svea", "sgqn", "soda")
#: Per-episode cost is FAMILY-dependent, and these are measured wall-clock points, not estimates.
#: A single flat rate produced a false FAIL on cfg-offline-eval-s2-full-v50 -- a config that
#: demonstrably SUCCEEDED -- which is the same class of error this audit exists to prevent.
#: [Claude 2026-09-07] Extended from two families to all seven, at zero compute cost: the v176
#: evaluator-validation wave already ran an endpoint grid per family, every one at the SAME scope
#: (ENDPOINT_EVAL_REGIMES=train,eval-easy x ENDPOINT_EVAL_SCENES=0 x ENDPOINT_EVAL_EPISODES=5 = 10
#: episodes), and each job's log carries its own NATIVE_ENDPOINT_EVAL_SECONDS. Six of twelve
#: baselines had been carrying UNMEASURED_DEFAULT = 30 s/episode.
#:
#: **CORRECTED the same day, before these numbers were used for anything.** The first version of
#: this block pooled the seven raw figures and called them comparable. They are not: the v176 wave
#: ran on TWO tiers -- rlvigen, dmc_gb, alda and ctrl on gt4i.1, ppg, ibac_sni and idaac on gt4.1 --
#: and this project's own measurement puts gt4i.1 at 1.14x gt4.1 (20.05 vs 17.53 fps on drqv2). A
#: gt4i.1 second is a faster second, so a gt4i.1 duration MULTIPLIED by 1.14 is its gt4.1
#: equivalent. Everything below is stated on the gt4.1 basis this file and plan_production already
#: use, with each entry's own tier recorded, exactly as FPS_BASIS does for throughput.
#:
#: **These are T4-class, NOT V100.** The production host's factor is unmeasured for evaluation just
#: as it is for training, and PRODUCTION-CALENDAR.md is explicit that its whole basis is T4-class
#: and therefore an upper bound. These belong there on that footing and nowhere else.
MEASURED_SECONDS_PER_EPISODE = {
    # gt4.1 basis. Converted entries are marked; raw gt4i.1 durations are in the comment.
    "drqv2": 9,      # bt1rr9hodosm5sn09t1a, gt4.1 native: 400 episodes in 3593s -> 8.5, rounded up
    "rlvigen": 11,   # bt1lmtfcqafcpbh02ai7, gt4i.1: 90s/10 = 9.0 raw -> x1.14 = 10.3, rounded up
    "dmc_gb": 10,    # bt1k600n8r2e4divs2dk, gt4i.1: 86s/10 = 8.6 raw -> x1.14 = 9.8, rounded up
    "alda": 11,      # bt1m638bct3b2rs1g844, gt4i.1: 95s/10 = 9.5 raw -> x1.14 = 10.8, rounded up
    "ctrl": 12,      # bt13vlerk8p1vop3bmep, gt4i.1: 99s/10 = 9.9 raw -> x1.14 = 11.3, rounded up
    "ppg": 11,       # bt11qhufomconlujompu, gt4.1 native: 106s/10 = 10.6, rounded up
    "ibac_sni": 9,   # bt1crbkhqkpi8s7ngqf9, gt4.1 native: 89s/10 = 8.9, rounded up
    "idaac": 11,     # bt1vcs013fq6lk17crou, gt4.1 native, C2 recipe: 102s/10 = 10.2, rounded up.
                     # Supersedes 25 from bt1ip5f8c6mqqm7fd2bn, which predates C2.
}
#: On one basis every family lands between 8.9 and 11.3 s/episode, against a placeholder of 30 --
#: so the placeholder was roughly 3x too high for all of them, which is the finding that survives
#: the tier correction. The `drqv2` and `rlvigen` rows differ by 2 s only because one is a native
#: gt4.1 measurement and the other a converted gt4i.1 one; that is the conversion's own error bar,
#: and it is why the raw durations stay in the comments.
#: What these numbers do NOT establish: they are 10-episode grids over ONE scene, while production
#: runs 800 episodes over ten. Per-episode cost should be equal or slightly lower there, since the
#: fixed environment construction amortises over more episodes -- but that is reasoning, not
#: measurement, and the production canary is where it gets checked.
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
# [Claude 2026-09-08] Keyed by whatever `CELLS=` names, which is a BASELINE -- so the family keys
# below were only ever hit for the families whose name IS a baseline (ctrl, idaac, ppg, ibac_sni).
# `soda`, `rad`, `drqv2`, `svea`, `sgqn`, `curl` all missed the dict and silently took the floor.
#
# That is not academic: it certified cfg-dmc_gb-attest-v196 (CELLS=soda:1, 10k frames) as fitting a
# 3600s timeout, and job bt1f8b5gb39jgadqngke was cut off mid-training at S:8000 with no error --
# a gate saying "ok" to a job that cannot finish, which is the failure this file was written for.
#
# soda is 3.2x slower than rad IN THE SAME FAMILY: the Places365 random_overlay draws and decodes a
# fresh image batch per update, and rad does not overlay at all. A family-level rate cannot express
# that, so the measured numbers are per baseline where they differ.
MEASURED_TRAIN_FPS = {
    # measured, job bt1f8b5gb39jgadqngke: 500 frames per 172.6 s
    "soda": 2.9,
    # measured, job bt14gjjdtoa5j54dr2n6: 500 frames per 54.8 s
    "rad": 9.1,
    # measured, job bt15e9v1k2ngmb71hnjn: 99,500 frames in 3659.8s of its own train.csv.
    # This entry exists because its ABSENCE was a defect: `drqv2` fell through to
    # TRAIN_FPS_FLOOR (soda's 2.9), costing a 10k drqv2 cell at 3448s instead of 368s and failing
    # cfg-rlvigen-revalidate-v191/v192/v194 -- configs that had demonstrably SUCCEEDED at 3600s
    # (external review 24 records those three jobs completing; their records were stale, not late).
    "drqv2": 27.19,
    "ctrl": 12.0, "idaac": 24.0, "ppg": 25.0, "ibac_sni": 8.0,
    "dmc_gb": 9.0, "rlvigen": 6.0, "alda": 9.0,
}
# The slowest MEASURED rate, not a round number: a floor above a real baseline's throughput is an
# optimistic budget, and an optimistic budget is what kills a cell after it has spent the money.
#
# But the floor is only safe for a baseline whose rate is UNKNOWN. Applied to one that is merely
# missing from the table, it manufactures a false FAIL -- see the `drqv2` entry above. So an
# unmeasured baseline is now NAMED in the report rather than silently costed, and the two rates
# below are recorded even though they are not adopted, because each is faster than the table's
# conservative entry and lowering a budget is the direction that kills cells:
#
#   ibac_sni  bt1cj6rgeptsu9f3v0o6  100,096 frames / 1706s = 58.7 fps  (its `procs` is not
#             recoverable from the retained log, and the rate is roughly linear in `procs`, so
#             this cannot be attributed to the production configuration. Table keeps 8.0.)
#   ppg       bt1apmmvvtfvjveil6ko    4,096 frames / 55.1s = 74.3 fps  (an 8x256 run; A36 measured
#             the adopted 1x2048 geometry at 59.44 IPS on the same tier. Table keeps 25.0.)
TRAIN_FPS_FLOOR = 2.9


def training_seconds(text: str) -> tuple[int, str | None]:
    """Cost of the training phase a train-then-eval config runs before it evaluates."""
    # An offline-eval config carries a vestigial FRAMES (it names the snapshot's budget, not work
    # to do) and trains nothing. Costing a training phase there is a false ALARM -- the safe
    # direction, but still wrong, and this file exists because wrong instruments get trusted.
    if "OFFLINE_EVAL_SNAPSHOT" in text:
        return 0, None
    # [Claude 2026-09-08] The baseline pattern EXCLUDED DIGITS, so `CELLS=drqv2:1` parsed as
    # "drqv" -- a name in no table. Both the train rate and the per-episode rate then fell to
    # their pessimistic defaults, and the audit failed cfg-rlvigen-revalidate-v190/191/192/194,
    # four configs that had already run to completion at the budget it called too tight.
    frames = re.search(r"\bFRAMES=(\d+)", text)
    cells = re.search(r"\bCELLS=([A-Za-z_0-9]+)", text)
    if not frames:
        return 0, None
    family = cells.group(1) if cells else None
    fps = MEASURED_TRAIN_FPS.get(family, TRAIN_FPS_FLOOR)
    return int(int(frames.group(1)) / fps), family


def _uses_places365(text: str) -> bool:
    """Does this config actually load the overlay dataset?

    Two independent signals rather than one: a config that names a Places365 asset, and a config
    whose cells include an overlay baseline. Either alone is enough to pay the cost.
    """
    # NOT the presence of the asset. cfg-rlvigen-revalidate-v191/v194 both PASS a Places365
    # archive and both run `CELLS=drqv2`, which never opens it -- the same fact
    # notes/DECISIONS-IF-PRODUCTION-GOES-WRONG.md records as the v194 attestation lesson. Keying
    # on the asset charged those two 600s they do not pay and failed configs that had already
    # succeeded, which is the exact error this file's docstring says it exists to prevent.
    cells = re.search(r"\bCELLS=(\S+)", text)
    return bool(cells) and any(name in cells.group(1) for name in PLACES365_BASELINES)


def family_of(text: str) -> str:
    match = re.search(r"OFFLINE_EVAL_FAMILY=(\S+)", text)
    if match:
        return match.group(1)
    cells = re.search(r"\bCELLS=([A-Za-z_0-9]+)", text)
    return cells.group(1) if cells else "unknown"


def audit(seconds_per_episode: int | None = None) -> int:
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
        train, train_baseline = training_seconds(text)
        # An unmeasured baseline is NAMED rather than silently costed at the floor: applied to a
        # baseline that is merely missing from the table, the floor manufactures a false FAIL.
        if train_baseline and train_baseline not in MEASURED_TRAIN_FPS:
            unmeasured.add(f"{train_baseline} (train rate, at the {TRAIN_FPS_FLOOR} fps floor)")
        # cfg-dmc_gb-attest-v196 passed this audit at 3600s and then died at S: 8000 of 10000,
        # because the model had no term for the Places365 load at all. A budget audit that omits a
        # cost the job certainly pays is worse than none: it certifies.
        places = PLACES365_LOAD_SECONDS if _uses_places365(text) else 0
        need = int(BOOTSTRAP_SECONDS + places + (train + episodes * rate) * SAFETY)
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
