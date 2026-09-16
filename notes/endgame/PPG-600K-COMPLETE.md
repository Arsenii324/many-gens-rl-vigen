# ppg on Door, 600k — the first complete production result

Two files, both on the live closure `248751f7caca`, both accepted by
`populate_evaluator_ledger.py` with `paired=True, diagnostics_complete=True`:

| file | rows | what |
|---|---|---|
| `reeval-v214-ppg-endpoint__records.jsonl` | 88 | 4 regimes x 11 scene sets x 20 ep, **both policy modes** |
| `reeval-v214-ppg-curve__records.jsonl` | 528 | 12 stamps x 4 regimes x 11 scene sets x 3 ep |

Cost: **zero training.** The weights are from `card0-20260909-115331`, trained 2026-09-09, whose 14
checkpoints were sha-verified against their own rows before any of this ran.

## The curve — mean over the ten individual scenes, 3 episodes each

```
   frame    train  eval-easy  eval-med  eval-hard
  51,200      4.7       4.5       9.9       3.8
 100,352     10.3       9.7       7.9      13.2
 151,552      5.3       6.4       6.7       5.1
 200,704      5.9       4.9       6.6       5.1
 251,904      8.6       8.4       5.4       7.6
 301,056      9.4       9.2       8.5       8.5
 350,208     27.6      25.4      18.2      27.5
 401,408     21.4      22.9      16.1      21.5
 450,560     21.9      23.1      11.2      23.3
 501,760     18.6      22.4      16.1      21.8
 550,912     31.0      26.5      15.6      27.2
 600,064     20.5      18.5      10.1      16.6
```

Endpoint at 20 episodes, `sample`: train **22.69**, eval-easy **17.96**, eval-medium **11.67**,
eval-hard **16.70**.

## What it shows, and what it does not

**ppg learns on Door.** From ~4.7 at 51k to the 20-31 band from 350k on. The jump is concentrated
between 301,056 and 350,208 (9.4 -> 27.6), not spread evenly.

**The curve is noisy, by design and not by accident.** Three episodes per cell is A20's decision
(2026-09-05, "three episodes/stamp, not five"), taken knowing that intermediate points carry SHAPE
while the endpoint carries the NUMBER. The swings -- 27.6 at 350k, 21.4 at 401k, 31.0 at 551k --
are what three episodes buy. They should not be read as the policy improving and regressing.

**The endpoint agrees with the curve within that noise.** Curve at 600,064 reads train 20.5 on 3
episodes; the endpoint reads 22.69 on 20. Consistent, and the second is the one that may be quoted.

**eval-medium is lowest at every late stamp.** Same property measured on the endpoint and recorded
before: `eval-medium` alone sets `except_robot=False`, randomising the robot's own appearance. It
is not "between" easy and hard on a difficulty axis; it is a different perturbation, and for a
policy trained on one robot appearance it is the hardest.

**No generalisation claim is made here.** train vs eval-easy is a paired comparison and the gap is
small (22.69 vs 17.96 at the endpoint). eval-medium and eval-hard are NOT paired across passes --
60% and 6% of their slots vary -- so a gap involving them carries perturbation variance on top of
episode variance. That is `audit_eval_validity.py`'s standing caveat, measured again on these rows.


---

## Provenance cross-check: the `--nminibatch 32` in the training log

The suite's fidelity-table check went stale today because ppg's descriptor reads `nminibatch: 1`
while `docs/FAITHFULNESS.md` still said 32. Chasing that turned up an apparent problem with THIS
run: `card0-20260909-115331`'s training log declares **`--nminibatch 32`**, and the descriptor now
declares 1. A headline result trained under a configuration the project has since changed would be
a serious caveat.

**It is not one, and the repo had already established why.** Commit `237f876` (2026-09-10 08:44)
investigated this exact run:

> card0-20260909-115331 ran 600,000 frames declaring `--nminibatch 32` and **executing 1**, logging
> `Warning: nminibatch > ntrain!! (32 > 1)` 293 times. `minibatch_optimize` splits the LEADING axis
> and `Roller.singles_to_multi` documents that axis as "(batch, time)", so `ntrain` is `num_envs`
> and any nminibatch above 1 is inexpressible at `num_envs=1`.

And on fidelity:

> Against PPG's own released 1-rank recipe -- 64x256 = 16384 with 1 epoch x 8 minibatches, 8
> gradient steps of 2048 samples, 0.00048828 steps per env frame -- our executed 1 step of 2048
> samples per 2048 frames is 0.00048828 per env frame. Density AND per-step batch size are
> identical. The clamp did not damage fidelity to PPG; the declared 32 would have... **the run
> itself is a faithful PPG needing no re-run.**

So the 32 is a DECLARATION that the trainer clamped, not an executed setting. The descriptor was
corrected to 1 to describe what actually runs, and the clamp now raises instead of warning, so the
same silent substitution cannot recur.

**These weights are faithful PPG at `num_envs=1, nstep=2048, nminibatch=1`.** The result stands.

**Scope of that verdict, added 2026-09-16.** `237f876`'s "density identical" argument covers the
POLICY phase. It does not cover the AUXILIARY phase, and a parallel evidence pass found those
differ: at `num_envs=1, nstep=2048, aux_mbsize=4` (upstream hard-codes it, no CLI flag) production
took **8 aux minibatches per aux epoch of 8192 samples**, where Table A.1 specifies 16 per N_pi,
i.e. 512 per aux epoch. Against the 4-rank release that is 0.5x the aux gradient steps per env
frame at 2x the batch; against the 1-rank release, 0.125x steps at 8x batch. The run logged 54 aux
epochs, ~432 aux steps.

This does NOT invalidate the result -- it is a faithful run of released DEFAULTS -- but it is a
fidelity row the reconciliation had missed, and the claim above should be read as policy-phase
only. `aux_mbsize=2` would match the 4-rank release exactly; no setting at `num_envs=1` matches the
1-rank release. Evidence bundles under `results/evidence/ppg-aux-phase-8-minibatches-per-epoch/`.

Worth keeping as method rather than trivia: the discrepancy was found by a stale DOCUMENT, chased
into the training log, and resolved by a commit message that had already done the work from the
producer's source. Reading the repo before concluding turned a would-be retraction into a
confirmation.
