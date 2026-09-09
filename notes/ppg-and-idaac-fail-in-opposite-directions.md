# `ppg` and `idaac` fail in opposite directions, and `ppg`'s two reward series disagree in sign

**2026-09-09**, read from the live `ppg` cell (`card0-20260909-115331`, 257 logged iterations to
~524k frames) beside the completed `idaac` cell.

## The two runs are mirror images

| | `idaac` @ ~540k | `ppg` @ ~524k |
|---|---|---|
| `clipfrac` | **0.82** | **0.000** for all 256 iterations |
| approximate KL | **0.7-1.5 nats** | **5.7e-14 → 2.5e-13** |
| policy entropy | 9.92 → **−1.75** | 9.93 → **9.98** (flat) |
| policy σ | 0.996 → **0.188** | 1.00 → **1.01** (flat) |
| value fit | `value_loss` 0.45 → 0.02 | `VFStats/EV` 0.011 → **0.81** |

`idaac` updates its policy far outside the trust region
([`idaac-on-door-is-a-trust-region-blowout.md`](idaac-on-door-is-a-trust-region-blowout.md)).
`ppg`'s logged policy-phase diagnostics show **no departure from the sampling policy at all**, and
its σ is unmoved after half a million frames — `log_std_raw_mean` drifts 0 → 0.0062, i.e. σ from
1.000 to 1.006, with `log_std_clamped_fraction` at 0 throughout, so nothing is clamping it.

**Both value functions learn.** `ppg`'s explained variance reaches 0.81. Whatever is wrong is on the
policy side in both cases, in opposite directions.

## What is NOT concluded, having nearly been

`Opt/pg` and `Opt/loss_pi` sit at 1e-8 to 1e-9, and my first reading of that was "no gradient
reaches the policy". **That inference is wrong and is recorded here so it is not made again.** With
advantages normalised to zero mean and the ratio at 1 in the first epoch, the PPO surrogate's
*value* is exactly `−mean(A) ≈ 0` while its *gradient*, `−mean(A ∇log π)`, is not. A zero loss is the
expected reading, not a symptom.

`VFStats/AdvStd` is 0.12-0.28 throughout, so there is a real advantage signal to learn from.

What remains unexplained is `clipfrac ≡ 0` and KL at machine epsilon across **all** 256 iterations.
Two readings, and this run does not separate them:

1. **The policy genuinely is not moving** — consistent with σ frozen at 1.0, a 7-DoF Gaussian at
   σ=1 being near-random, and `EpSuccessMean` at 0.01.
2. **The diagnostics are vacuous** — logged before the epoch loop, or over the first minibatch where
   the ratio is 1 by construction, in which case they say nothing and the σ evidence has to carry
   the whole claim alone.

Either is serious. The second would mean `ppg` has been running with instruments that cannot report
what they name, which is the failure class this project keeps meeting.

## The reward series disagree in sign, and reading the wrong one inverts the result

| series | first | last | direction |
|---|---|---|---|
| `EpRewMean` | 0.804 | **18.1** | **up ~22x** |
| `Misc/FrameRewMean` | 0.0206 | **0.00746** | **down ~2.8x** |
| `EpLenMean` | 500 | 500 | constant |

**`EpLenMean` is exactly 500 for every iteration**, so these two cannot both be raw: a constant
episode length forces `EpRewMean = 500 × FrameRewMean`, which would be **3.73**, not 18.1.

`REWARD_NORMALIZATION` in `rlgen/protocol.py` marks `ppg` as normalising **training** reward, so one
of these is on the normalised scale and drifts with the running statistic. **Which one is which is
not settled here, and it must not be guessed:** if `EpRewMean` is the normalised series, `ppg`'s raw
return is *falling*, and a summary quoting `EpRewMean` would report a 22x improvement on a run that
is getting worse.

**The arbiter is already defined and needs no new decision.** Records report **raw** return
regardless of training normalisation, so `ppg`'s offline evaluation curve — which runs after training
— settles it directly and on the same axis as every other baseline. Nothing about `ppg` should be
reported from the training log.

## What to do with this, given `ppg` is still running

**Let it finish.** It is at ~524k of 600k with the evaluation still to come, the evaluation is the
measurement that matters, and stopping it would destroy the one artifact that resolves the ambiguity
above.

When it completes, in order:

1. **Plot the offline curve on raw return.** That answers both the direction question and whether
   `ppg` learned, on the benchmark's own axis.
2. **If raw return is flat or falling while `EpRewMean` rose**, the training-log reward series is
   established as misleading for normalising families (`idaac`, `ppg`, `ctrl`) and should be labelled
   in `families.json` rather than left for the next reader to trip over.
3. **Read `clipfrac` in the source** — `runnable/ppg/` — to decide between the two readings above.
   That is a code question, answerable without GPU time, and it should be answered before `ctrl`
   runs, since `ctrl` is the third on-policy family with Procgen-tuned constants.

## The comparison this does not license

`idaac`'s `clipfrac` and `ppg`'s `clipfrac` come from **different loggers in different codebases**.
0.82 against 0.000 is not one quantity measured twice, and the mirror-image framing at the top of
this note is a description of two separate pathologies, not a ranking. The same caution
`scripts/comparison_blocks.py` enforces for returns applies to diagnostics, which have no
`policy_mode` column to protect them.
