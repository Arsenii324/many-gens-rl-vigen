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
