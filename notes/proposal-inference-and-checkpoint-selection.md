# Proposal — inference and checkpoint selection

Written 2026-09-04. **Revised 2026-09-05 after the third external review corrected it.** Drafted in
`notes/` rather than edited into `EVAL-PROTOCOL.md` to avoid colliding with concurrent work; merge
it there when ownership is settled.

Both are **analysis** decisions, not code. Both must be frozen *before* the fleet runs — #29 in
particular, because a held-out validation set has to be reserved in advance.

> **What the third review corrected, and it was right on every count.** My first draft said
> `(baseline, seed, regime, scene)` was "the smallest unit that is not internally correlated by
> design". **That is wrong**: all ten scene results for one seed share the *same trained policy*, so
> they stay correlated. Ten scene cells do not turn three trained agents into thirty replicates. It
> also caught that I had (a) proposed bootstrapping scenes without deciding whether the ten scenes
> are a fixed grid or a sample from a population, (b) claimed cross-method *training-seed* pairing
> that the design does not establish, (c) left "not distinguishable from the floor" undefined while
> simultaneously banning p-values, and (d) kept retention as a headline when a difference avoids the
> denominator pathology entirely. All four are fixed below.

---

## 1. Statistical inference

### 1.1 The unit of analysis

**The training seed is the only outer replicate.** One seed produces one learned policy; that policy
is then measured on ten scenes in four regimes. Aggregate inward-out:

    Y[m,r,g,s]  = mean over episodes e of R[m,r,g,s,e]        # an analysis CELL, not a replicate
    Ȳ[m,r,g]    = mean over the ten scenes s of Y[m,r,g,s]     # one number per trained policy
    replicates  = { Ȳ[m,1,g], Ȳ[m,2,g], Ȳ[m,3,g] }             # n = 3, and that is the whole n

Scene-level results are still reported — visual-generalisation *heterogeneity* across scenes is one
of the more interesting things this experiment can show — but they are descriptive, never treated as
independent observations.

### 1.2 Fixed scenes or a sample of scenes — decide before writing the bootstrap

The ten certified scenes are either **a fixed benchmark grid** (the estimand is "performance on
these ten prescribed appearances") or **a sample** from a population of possible RL-ViGen
appearances. These are different scientific questions and they imply different resampling.

**Recommendation: treat the ten as a fixed grid.** They are certified and prescribed by the
protocol, not drawn; and nothing in the project defines the population they would be sampling from.
Consequently: **resample whole training-seed vectors** — when seed 2 is resampled, all ten of its
scene results travel with it — and do **not** resample scenes. Do not let the implementation of a
bootstrap function silently choose the estimand.

### 1.3 Reporting with n = 3

A bootstrap cannot manufacture independent trained agents. For every headline value show:

- all **three** seed-level points, individually;
- their mean;
- their SD or range;
- optionally a seed-clustered interval, clearly labelled as such.

Never let an interval visually obscure that there are three learned policies behind it. Report
effect sizes and intervals, not p-values.

### 1.4 What is actually paired, and what is not

Common evaluation placements ([C69](../docs/CONSTRUCTION.md#c69), one fixed eval seed) give pairing
in **regime, scene and episode placement**. That reduces *measurement* noise and is worth having.

**It does not give cross-method training-seed pairing.** "Seed 1" for `ibac_sni` and "seed 1" for
`drqv2` are not a common-random-number block: the algorithms consume RNG differently, use different
libraries and rollout structures, and matching the integer proves nothing about correlated training
outcomes. So compare **distributions of three independently trained policies**, and use the shared
placements only to make each of those three numbers less noisy.

**And no paired analysis at all until pairing is verified in the data** — the native evaluator
probed with `reset()+step()` while the grid evaluator did not, which broke the premise. Per §1.6,
prove it rather than assume it.

### 1.5 Competence: a preregistered number, not a significance test

"Not distinguishable from the floor" was underspecified and contradicted the no-p-values rule.
Replace it with a deterministic threshold fixed before the fleet runs. **Recommendation:**

> A baseline is **competent** in the training regime if its per-seed mean return exceeds
> `R_floor + δ` in **at least 2 of 3 seeds**, with `R_floor = 1.82` ([C55](../docs/CONSTRUCTION.md#c55))
> and `δ` fixed now. A ratio-style generalisation number is reported only for competent baselines.

Raw training and OOD scores are **always** reported, competent or not. Suppressing a ratio must
never look like suppressing a result.

### 1.6 Make pairing provable, not inferred

Record, for every episode row, an `eval_episode_id` **and a hash of the realized initial Door
placement**. This is the third review's addition and it is cheap insurance: it makes pairing
empirically auditable, makes any future RNG-stream divergence detectable the moment it happens
rather than months later, and lets reanalysis pair episodes without reconstructing RNG state. Given
that stream asymmetry has already occurred once in this project, it should not be optional.

### 1.7 Pre-register the comparisons and the missing-run policy

Twelve baselines admit **66** pairwise comparisons; with three seeds it is easy to narrate whichever
handful look attractive. Either name the small set of primary comparisons in advance, or publish the
complete pairwise matrix and highlight nothing selectively.

With n = 3, losing one seed is statistically severe, so decide **now**: whether a crashed seed is
rerun under the identical seed, whether replacement seeds are forbidden, what happens when a method
is missing a scene, and whether an incomplete method stays in the headline table. Deciding after
seeing which seed went badly is survivorship bias.

---

## 2. The primary outcome, and why retention is demoted

A raw return ratio is **not invariant to reward offsets**, and Door's reward is dense, shaped and
floored — so a constant shaping offset moves "retention" with no behavioural change.

**Primary quantities:** `R_train`, `R_OOD`, and the **difference** `Δ = R_OOD − R_train`, plus
**success rate**, which is offset-invariant and is the only quantity that distinguishes a policy
that opens the door from one accumulating shaped reaching reward.

**Secondary, and only for competent baselines:** the ratio `ρ = R_OOD / R_train`, or the
floor-adjusted `(R_OOD − R_floor)/(R_train − R_floor)`. If a log-ratio is used, state the rule for
zero or non-positive returns — "use log scale" alone is not a specification.

This ordering makes a failed agent read as a failed agent, instead of converting a denominator
pathology into an interesting-looking generalisation percentage.

---

## 3. Checkpoint selection

**Headline = the exact endpoint. The trajectory is descriptive supplementary material. No
"best checkpoint" headline at all.** That is the recommendation, and the reasoning is that every
alternative needs machinery the project would have to get exactly right:

1. **Winner's curse survives selecting on the training regime.** If `k* = argmax_k R_train,val(k)`
   and you then report `R_train,val(k*)`, that reported number is optimistically biased. A rigorous
   procedure needs *validation* episodes to choose `k*` and **fresh reporting episodes at `k*`** —
   the validation set can be a reserved subset of training-regime placements, so it need not cost an
   OOD regime.
2. **Equal opportunity.** "The same rule for everyone" is not enough if one method offers 13
   eligible checkpoints and another 25 — more candidates is more chance to win on noise. Freeze the
   target frame stamps and define how each method maps an update boundary onto a stamp.
3. **Per-seed and per-method selection are different procedures.** Per-seed `k*[m,r]` simulates
   early stopping of each real run; per-method `k*[m]` chooses one training horizon from three seeds
   jointly. Say which.
4. **Tie-breaking and missing stamps** need a rule.

The endpoint avoids all four. If a best-over-trajectory column is wanted anyway, it needs all four
resolved in advance and should be labelled as an upper envelope, not an estimate of the policy you
would obtain by training once.

---

## Why both belong before the run

Nothing here changes what is *collected* — per-episode, per-scene, per-seed rows are already
retained, which is the right shape — with two exceptions that do: **the placement hash of §1.6**,
and **the reserved validation episodes** of §3, if a selected checkpoint is ever wanted. Neither can
be reconstructed after the fact.
