#!/usr/bin/env python3
"""R6: is each of the twelve a GENUINE implementation, or the name of one?

R6 asks whether all twelve are present as real implementations. `requirements.py` can only report
that twelve declare themselves implemented; the registry's own docstring records three that were
once present in name only, so the declaration is not the evidence. This script supplies the
evidence, on the standard the runbook sets: **the distinctive mechanism must be DEFINED in the
clone and must ACTUALLY EXECUTE in a run of the length we intend to report.**

The second half is the one that bites, and it is not hypothetical. `ppg`'s auxiliary phase -- the
phase the algorithm is named for -- runs only once `curr_iteration >= n_pi` with `n_pi=32`, and an
iteration is 2048 interacts, so it first fires at **65,536 frames**. Every ppg number this project
holds was produced at 10,000 frames. Those runs are PPO. Not a broken PPG: PPO, exactly, because
the auxiliary phase never executed once.

So a baseline can be perfectly faithful, run clean, produce a plausible number, and still not be
the algorithm the column claims -- and nothing in a return curve reveals it. That is what this
audit is for, and why its verdict depends on the budget you pass.

    python scripts/audit_implementations.py --frames 600000
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSET = Path("/Users/a2mogus/build-projs/rlgen-assets/rlvigen-door2-90d8b8c4.tgz")

# `first_active` is the frame at which the mechanism first runs. `None` means "from the first
# update", which is the ordinary case and the one that needs no budget argument.
#
# `seed` is the random-policy warmup a family serves before ANY gradient update. It does not make
# an implementation ungenuine -- it is the algorithm's own setting -- but at a short budget it
# silently converts most of the run into a random policy, so it is reported beside the verdict.
MECHANISMS = [
    # RL-ViGen's five live in the asset archive, not this tree: they are supplied to a job as an
    # input, so `where` is resolved inside the tarball rather than on disk.
    ("drqv2",    "random-shift augmentation + n-step(3) critic + scheduled exploration stddev",
     # n-step lives in `cfgs/config.yaml` (`nstep: 3`) and is consumed by the replay loader, not
     # by the algorithm file -- looking for it here reported drqv2 NOT DEFINED, which it plainly is.
     "asset:RL-ViGen-upstream/algos/drqv2.py", ("RandomShiftsAug", "stddev_schedule"), None, 4000),
    ("drq",      "random-shift augmentation, n-step(1)",
     "asset:RL-ViGen-upstream/algos/drq.py", ("RandomShiftsAug",), None, 4000),
    ("svea",     "augmented-consistency critic loss (svea alpha/beta over aug and clean views)",
     # NOT `svea_alpha`/`svea_beta`: RL-ViGen writes SVEA in its unbatched form -- a clean critic
     # loss and an augmented one, averaged 0.5/0.5 -- with the concatenated equivalent left in the
     # file as comments. That IS SVEA at alpha = beta = 0.5, the paper's own default, but the
     # coefficients are hardcoded rather than read from the config.
     "asset:RL-ViGen-upstream/algos/svea.py", ("aug_obs", "aug_loss"), None, 4000),
    ("sgqn",     "saliency-guided attribution mask over the critic's inputs",
     "asset:RL-ViGen-upstream/algos/sgqn.py", ("attrib", "mask"), None, 4000),
    ("curl",     "contrastive objective against a momentum encoder",
     "asset:RL-ViGen-upstream/algos/curl.py", ("compute_logits", "W"), None, 4000),
    # dmc_gb supplies rad and soda from this tree.
    ("rad",      "random crop from a 100-pixel render to 84 (P6 supplies the 100)",
     # `rad.py` is thirteen lines and overrides nothing: RAD's crop is applied by the replay
     # buffer's sampler, so that is where the mechanism has to be looked for.
     "runnable/dmc_gb/src/utils.py", ("random_crop",), None, None),
    ("soda",     "BYOL-style auxiliary head over overlaid views",
     "runnable/dmc_gb/src/algorithms/soda.py", ("random_overlay", "predictor"), None, None),
    ("alda",     "ALDA's own latent-disentanglement objective",
     "runnable/alda/trainers/alda_trainer.py", ("alda",), None, None),
    ("ppg",      "auxiliary phase: value distillation into the policy every n_pi iterations",
     "runnable/ppg/phasic_policy_gradient/ppg.py", ("compute_aux_loss", "n_pi"), 65536, None),
    ("idaac",    "adversarial advantage head (the encoder is trained to make advantage unpredictable)",
     "runnable/idaac/ppo_daac_idaac/algo/daac.py", ("adv_loss", "adv_loss_coef"), None, None),
    ("ibac_sni", "information bottleneck (VIB) with selective noise injection",
     "runnable/ibac_sni/torch_rl/model.py", ("use_bottleneck", "sni_type"), None, None),
    ("ctrl",     "prototype clustering objective, updated every iteration",
     "runnable/ctrl/algo.py", ("update_cluster", "num_clusters"), None, None),
]


# [Claude 2026-09-05] WHAT THIS AUDIT CANNOT SEE, discovered by reading FAITHFULNESS.md properly.
#
# The check below is marker PRESENCE in the source. That is too weak in two ways this project has
# real examples of:
#
#   * `svea` PASSES on `aug_obs`/`aug_loss` while feeding the WRONG AUGMENTATION into that loss --
#     `RL-ViGen-upstream/algos/svea.py:12` imports `random_overlay` (SODA's) and applies it at :298,
#     where canonical SVEA uses random convolution. The consistency-loss form is present; its input
#     is not the paper's.
#   * `ctrl` would have PASSED even in its RELEASED state, where two commented-out lines made
#     `loss_cluster` raise NameError on first call so ctrl_public could not run its own algorithm.
#     A symbol exists whether or not it reaches the gradient.
#
# A mechanism is genuine when its term reaches the GRADIENT and its INPUTS are the paper's. Presence
# establishes neither. These caveats are attached to the verdicts so the limitation travels with the
# result instead of living in a document nobody opens.
MECHANISM_CAVEATS = {
    "svea": ("feeds SODA's `random_overlay`, not SVEA's random convolution "
             "(svea.py:12,298) -- the loss form is SVEA's, the augmentation is not. This is "
             "RL-ViGen's SVEA, which is exactly what their published 268.8 Door number measures"),
    "ctrl": ("FAITHFULNESS records `L_clust` absent and positives drawn from the same partition "
             "rather than a neighbouring one. The first half looks superseded -- `loss_cluster` is "
             "defined (algo.py:173) and its gradient applied (:558) after this project restored two "
             "lines the authors had commented out -- the second is UNVERIFIED"),
    "curl": "paper and official code disagree on 5 hyperparameters; DrQ-v2-based, not SAC",
    "ppg": "rollout 256 vs upstream 65,536; the continuous head has no reference at all",
    "idaac": "rollout 256 vs 2048 continuous; 8-sample minibatches",
}


def _asset_members() -> dict:
    if not ASSET.is_file():
        return {}
    out = {}
    with tarfile.open(ASSET) as tar:
        for member in tar:
            if member.name.endswith(".py"):
                out[member.name] = member
    return out


def _read(where: str, asset_index: dict) -> str | None:
    if where.startswith("asset:"):
        name = where.split(":", 1)[1]
        if not ASSET.is_file():
            return None
        with tarfile.open(ASSET) as tar:
            for candidate in (name, name.replace("/algos/", "/algorithms/")):
                try:
                    handle = tar.extractfile(candidate)
                except KeyError:
                    continue
                if handle is not None:
                    return handle.read().decode("utf-8", "replace")
        return None
    path = ROOT / where
    return path.read_text(errors="replace") if path.is_file() else None


def audit(frames: int) -> list[dict]:
    asset_index = _asset_members()
    rows = []
    for name, mechanism, where, markers, first_active, seed in MECHANISMS:
        source = _read(where, asset_index)
        if source is None:
            verdict, note = "UNRESOLVED", f"source not found at {where}"
            present = []
        else:
            present = [m for m in markers if m in source]
            if len(present) != len(markers):
                missing = [m for m in markers if m not in present]
                verdict, note = "NOT DEFINED", f"markers absent: {missing}"
            elif first_active is not None and frames < first_active:
                verdict = "DEFINED, NEVER RUNS"
                note = (f"first activates at {first_active:,} frames; a {frames:,}-frame run "
                        f"executes it {0} times -- this column would not be {name}")
            elif first_active is not None:
                verdict = "GENUINE"
                note = f"activates {frames // first_active}x at {frames:,} frames"
            else:
                verdict = "GENUINE"
                note = "runs from the first update"
        if seed and verdict == "GENUINE":
            share = 100.0 * seed / frames if frames else 0.0
            note += f"; {seed:,} seed frames = {share:.0f}% of this budget is a random policy"
            if share >= 20:
                verdict = "GENUINE, BUDGET-MARGINAL"
        caveat = MECHANISM_CAVEATS.get(name)
        if caveat and verdict.startswith("GENUINE"):
            verdict = "GENUINE (PRESENCE ONLY)"
        rows.append({"baseline": name, "mechanism": mechanism, "where": where,
                     "verdict": verdict, "note": note, "caveat": caveat})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--frames", type=int, default=600_000,
                        help="the budget the reported numbers would come from (default 6e5)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    rows = audit(args.frames)
    if args.json:
        print(json.dumps({"frames": args.frames, "rows": rows}, indent=2))
        return 0

    print(f"R6 -- genuine implementation, judged at a {args.frames:,}-frame budget\n")
    width = max(len(r["baseline"]) for r in rows)
    bad = 0
    for row in rows:
        flag = " " if row["verdict"].startswith("GENUINE") else "!"
        if flag == "!":
            bad += 1
        print(f"{flag} {row['baseline']:<{width}}  {row['verdict']}")
        print(f"  {' ' * width}  {row['mechanism']}")
        print(f"  {' ' * width}  {row['note']}")
        if row.get("caveat"):
            print(f"  {' ' * width}  !! {row['caveat']}")
        print()
    print(f"{len(rows) - bad}/{len(rows)} genuine at this budget.")
    if bad:
        print("A baseline whose mechanism never runs is not a weak result for that algorithm --\n"
              "it is a result for a DIFFERENT algorithm under that algorithm's name.")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
