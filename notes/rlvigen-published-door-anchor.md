# The published RL-ViGen Door numbers — C48's anchor, read at last

Extracted 2026-09-05 from `RL-ViGen-upstream/results/evaluation_score.xlsx`, sheet **Robosuite**,
`door` rows. The file ships inside the `rlvigen-door2-90d8b8c4.tgz` asset;
`scripts/rlvigen_reference.py` expects it at a path that does not exist in this tree, which is
probably why nobody had read it here.

## What they publish for Door

| method (regime) | five seeds | mean |
|---|---|---:|
| **DrQ-v2 (Easy)** | 3, 7, 4, 3, 1 | **3.6** |
| DrQ-v2 (Medium) | 1, 4, 3, 3, 1 | 2.4 |
| DrQ-v2 (Hard) | 1, 3, 2, 3, 1 | 2.0 |
| CURL (Easy) | 3, 11, 4, 2, 13 | 6.6 |
| DrQ (Easy) | 1, 28, 4, 29, 8 | 14.0 |
| **SVEA (Easy)** | 472, 121, 170, 301, 280 | **268.8** |
| SVEA (Medium / Hard) | — | 129.2 / 62.4 |
| **SGQN (Easy)** | 457, 406, 459, 227, 408 | **391.4** |
| SGQN (Medium / Hard) | — | 161.4 / 160.4 |
| PIEG (Easy) | 411, 426, 365, 431, 303 | 387.2 |
| SRM (Easy) | 444, 401, 406, 213, 222 | 337.2 |

## Three consequences, and the first one changes how the whole table should be read

**1. Their own DrQ-v2 does not generalize on Door.** 3.6 against our measured random floor of
**1.82** ([C55](../docs/CONSTRUCTION.md#c55)) is *at the floor*. Same for CURL (6.6) and DrQ (14.0,
carried entirely by two of five seeds — 28 and 29 against 1, 4, 8). Meanwhile SVEA, SGQN, PIEG and
SRM land at 270–390. **So on Door, the published result is already that the augmentation/saliency
family generalizes and the plain-augmentation family does not.** Any table we produce should be read
against that expectation rather than in a vacuum.

**2. Our `drqv2` number is consistent with theirs, and [C37](../docs/CONSTRUCTION.md#c37)'s "130×
gap" was never the comparison to make.** Our 100k `drqv2` cell gave train 480.6, eval-easy **1.44**.
Their DrQ-v2 eval-easy is **3.6**, with a seed range of 1–7. Both are at the floor; ours sits inside
their seed spread's lower end. [C45](../docs/CONSTRUCTION.md#c45)/[C47](../docs/CONSTRUCTION.md#c47)
had already established that the two figures being compared were different quantities — this shows
what the *right* comparison looks like, and it is unremarkable rather than alarming.

**3. C48's anchor is far cheaper than it looked, and may be nearly met.** The obligation
(`porting-directive.md` §3, tier **T3**) is *distributional agreement with the reference's published
results on the reference's own domain*. For `drqv2` on Door that target is a five-seed distribution
of **{1, 3, 3, 4, 7}**. Landing three seeds inside that range is a *reachable* T3 claim, not a
research programme — and it is the positive control C48 says the project has never had.

## What this does to the open decisions

- **A9 (anchor before fleet) — strengthened and made concrete.** The target exists, is small, and is
  budget-matched if we run 6e5, which is RL-ViGen's own Door budget. Recommend: state T3 as
  "`drqv2` Door eval-easy within the published five-seed range 1–7", and check it against the
  production `drqv2` seeds rather than commissioning a separate anchor run. **That makes A9 free** —
  it becomes an acceptance test on data the fleet produces anyway, not an extra cell.
- **A10 / budget — reinforced.** 6e5 is the budget their numbers were produced at, so T3 is a direct
  comparison only at 6e5. A shorter shape would make the anchor incomparable.
- **The competence gate needs care.** If the *reference itself* reports DrQ-v2 at 3.6 on Door, then a
  near-floor eval number is the **expected**, published outcome for that method — not evidence that
  our port is broken. The competence rule must not quietly classify a faithfully-reproduced
  published failure as an implementation defect. Report `R_train` (where drqv2 reaches 480.6 and is
  plainly competent) alongside, and let the eval number be what it is.

## One caution before this is used

The units are not certified. The `door` values sit on the same scale as our returns (SVEA 268.8 vs
our drqv2 train 480.6 is plausible), but `lift` rows are 0–3 while a random arm reportedly scores
~7.5 on Lift, which does not obviously fit a return reading. C45/C47 exist precisely because two
figures were compared that were never the same quantity. **Confirm what the sheet's numbers are —
return, success percentage, or something else — before quoting any of this as agreement.** That
confirmation is the first concrete step of the T3 work, and it is a reading task, not a compute task.

---

## Correction, 2026-09-05 — `drqv2` is the WRONG anchor. `svea`/`sgqn` are the right ones.

Two things I got backwards, found while verifying the `svea` divergence.

**1. The `svea` divergence does not weaken the anchor — it is irrelevant to it.**
`FAITHFULNESS.md` rates `svea` **high** because RL-ViGen's implementation feeds SODA's
`random_overlay` rather than SVEA's random convolution. That is a divergence between **RL-ViGen's
SVEA and the SVEA paper**. It is *not* a divergence between us and RL-ViGen: **we run their code**,
and their published 268.8 was produced by that same code. For T3 — "distributional agreement with
the reference's published results on the reference's own domain" — the comparison is
apples-to-apples. The divergence constrains only what we may *call* the row: **"RL-ViGen's SVEA",
never "SVEA"**.

**2. Anchoring on `drqv2` is anchoring at the floor, which is nearly uninformative.**
Their published DrQ-v2 Door eval-easy is **3.6**, against a random floor of **1.82**. Two numbers
that both sit at the floor agree for reasons that have nothing to do with whether our pipeline is
right — a broken evaluator, a floored policy and a correct reproduction all produce ~2. Agreement
there is weak evidence, and this project has already recorded the general form of that error:
[C45](../docs/CONSTRUCTION.md#c45)/[C47](../docs/CONSTRUCTION.md#c47), where two figures agreed
while never being the same quantity.

**The discriminating targets are the ones far from the floor:**

| candidate | published Door eval-easy | distance from the 1.82 floor |
|---|---:|---|
| **`sgqn`** | **391.4** | 215× — the most discriminating |
| **`svea`** | **268.8** | 148× |
| `drqv2` | 3.6 | 2× — uninformative |

**Revised A9: anchor on `sgqn` and `svea`, and treat `drqv2` as a supporting check only.** If our
`sgqn` lands near 391 and our `svea` near 269, the pipeline is corroborated on numbers that could
easily have come out wrong. If they land at 50, or at 800, we learn something — which is the entire
point of a positive control, and precisely what a floor comparison cannot deliver.

This costs nothing extra: both are production baselines, so the anchor remains a free acceptance
test on data the fleet produces anyway. It only changes **which rows we look at first**.

---

## `scripts/rlvigen_reference.py` now runs — and it was built for exactly this comparison

The script existed all along and **could never execute**: it looked only at
`ROOT/RL-ViGen-upstream/results/evaluation_score.xlsx`, which does not exist in this tree because the
benchmark is supplied to jobs as an *asset archive*. Every invocation printed "absent", so
RL-ViGen's published numbers went unread for the project's whole life — while
[C37](../docs/CONSTRUCTION.md#c37) was rewritten twice trying to explain a gap against them. Fixed to
search the asset archive; `--asset PATH` overrides.

Its own output confirms the manual read and adds two things:

**1. It states the units, which was `OPEN-QUESTIONS` Q2.**

> These are RETURNS. The benchmark does not publish success rates for robosuite, which is C33. And
> they come from RL-ViGen's configuration, not ours — a bound on what is reachable and a
> reproduction target, not a baseline to subtract.

**2. It prints our floor beside theirs, and the Lift puzzle dissolves.**

    DOOR  our random-policy floor, OUR config: mean 1.63, max 6.93
    LIFT  our random-policy floor, OUR config: mean 6.56, max 34.65

So the "~7.5 random on Lift" figure is real (6.56 here), and the published Lift values of 0.2–2.0 for
DrQ-v2/CURL/DrQ **are below a random policy** — while SVEA (43.0) and PIEG (96.4) are well above it.
That is coherent rather than anomalous: with shaped reward, a policy that converges to near-stillness
can earn *less* than a random arm that flails and collects reaching reward. It is not evidence that
the sheet's units differ between tasks.

**3. And it strengthens the anchor correction more than I had.** Our Door random policy reaches a
**max of 6.93**. RL-ViGen's published DrQ-v2 Door mean is **3.6**, CURL 6.6, DrQ 14.0 — so two of
those three sit *inside the range a random policy achieves on our configuration*. Anchoring T3 on
`drqv2` would be anchoring on a number a random policy can produce. **`sgqn` (391.4) and `svea`
(268.8) are the only Door targets far enough from the floor to discriminate.**

**One discrepancy to note:** this script reports the Door floor as **1.63 mean**, where
[C55](../docs/CONSTRUCTION.md#c55) records **1.82**. Small, but they are two homes for one number —
mechanism 2 in [`SYNTHESIS.md`](SYNTHESIS.md). Worth reconciling before either is quoted in a
write-up.

## Refinement 2026-09-05, from the re-measured floor

The floor is now **mean 1.842, sd 2.839, max 28.755** over 200 paired episodes (C55, re-measured).
That sharpens the anchor argument in one direction and softens it in another, and both matter.

**Softened:** it is too strong to say the published DrQ-v2 (3.6) and CURL (6.6) sit *inside* the
floor. Against a floor whose 95% CI on the mean is [1.511, 2.271], a mean of 3.6 is outside it and
6.6 is well outside. On the mean, they are above chance.

**Sharpened, and this is the operative point:** being above chance on the mean is not competence
when the chance distribution has sd 2.84 and a 200-episode max of 28.8. A method scoring 3.6 is
inside one standard deviation of random play, and the difference between "a broken evaluator", "a
floored policy" and "a correct reproduction" is smaller than the noise. So the conclusion in
[`CORRECTIONS.md`](CORRECTIONS.md) #3 stands unchanged and now rests on measurement rather than on
the 1.82 point estimate: **anchor on `sgqn` (391.4) and `svea` (268.8)**, which are two orders of
magnitude above the floor and can therefore discriminate a working pipeline from a broken one.
