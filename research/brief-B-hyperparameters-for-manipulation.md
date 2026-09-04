# Brief B — do any of these hyperparameters transfer to 7-DoF manipulation?

**Upload with**: `SHARED-CONTEXT.md`, `PREMISES.md`, `FAITHFULNESS.md`.

**Suggested approach**: scope first with ordinary agentic search to find out how much literature
exists on visual RL for robosuite/Meta-World/ManiSkill manipulation with these specific method
families. If it is thin, say so early — the answer "there is no precedent, here is the closest
thing" is a perfectly good deliverable and should redirect the deep pass toward §4.

---

## Why this brief exists

Every hyperparameter in our benchmark is *mapped*, never *inherited*, because **none of the twelve
methods was ever published on robosuite 7-DoF manipulation**:

- DrQ, DrQ-v2, CURL, RAD, SVEA, SODA, SGQN, ALDA → DMControl / DMControl-GB **locomotion**.
- PPG, IDAAC, IBAC-SNI, CTRL → Procgen, **discrete action**.

Of the four DMC-GB methods that evaluated manipulation at all: RAD never did; SVEA used a Kinova
Gen3 restricted to a **2-D action space** with the environment **never released**; SODA likewise,
unreleased; only SGQN released manipulation code (an xArm7), shipped with author-admitted broken
files. So there is no public precedent for these methods on full 7-DoF continuous manipulation.

We currently apply **DrQ-v2's published hyperparameter set as a shared base to all twelve**. That
is defensible as a protocol choice and indefensible as a claim of fairness, and we would like to
know how much it costs.

## The decision this feeds

**What rule should set hyperparameters across arms?** The candidates:

- **(a)** Keep one shared base and report it as a stated limitation.
- **(b)** Use each method's published values, accepting that they come from a different benchmark
  and that paper and code disagree for several of them.
- **(c)** Adopt a manipulation-specific base from whatever the visual-manipulation literature
  actually uses, applied uniformly.
- **(d)** Tune a small number of high-sensitivity knobs per arm, within a fixed budget.

We need evidence for which of these produces a comparison that means something. **A concrete
recommendation is wanted, not a survey.**

---

## 1. What does visual RL on robosuite/manipulation actually use?

For pixel-based continuous control on robosuite, Meta-World, ManiSkill, RLBench or similar:

- Typical **learning rate**, **batch size**, **replay capacity**, **n-step**, **discount**,
  **target tau**, **encoder architecture and feature dim**, **frame stack**, **action repeat**.
- Do manipulation papers use DMC's conventions unchanged, or is there a distinct house style?
- **Discount specifically.** Our episodes are 500 steps with no early termination and dense shaped
  reward. Is 0.99 right, or does the horizon argue for something else? (Our on-policy arms
  currently run 0.999, inherited from Procgen where episodes are long; our off-policy arms run
  0.99. We think that is incoherent and want to fix it in one direction.)
- **n-step.** DrQ-v2 uses 3; RAD/SVEA/SODA/SGQN/DrQ/ALDA are all 1-step TD. We apply 3 to all
  off-policy arms. Is there evidence on whether n-step helps or hurts on dense-reward manipulation?

## 2. Sensitivity — which knobs actually matter?

The most useful thing you can tell us. With finite compute we can tune very few things.

- Is there published sensitivity analysis for visual RL (DMC or manipulation) ranking
  hyperparameters by effect size? Learning rate vs batch vs n-step vs replay size vs target tau.
- Specifically: **how much does a 10× learning-rate error cost?** We have a measured 10× split
  across our arms (some at 1e-4, some at 1e-3) and need to know whether that is fatal to the
  comparison or second-order.
- **Replay capacity**: we use 1e5 where DrQ-v2 uses 1e6. At a 500k-frame budget that means the
  buffer holds the most recent 20% and evicts the rest. Is there evidence on how much this costs
  for off-policy visual RL?
- **Exploration schedule**: we use DrQ-v2's `linear(1.0,0.1,500000)`, which is its *medium-tier*
  string designed for a 3.1M-frame budget — noise finishes annealing at 16% of training there, and
  at 100% of training for us. How much does this matter?

## 3. The fairness question, treated seriously

This is a methodological question and we want the methodological literature, not opinion.

- What is the accepted practice for hyperparameter selection in **multi-algorithm comparison
  papers**? Shared values, per-method published values, or per-method tuning under equal budget?
- Is there work quantifying the bias introduced by tuning a shared configuration around one
  method? (The RL reproducibility literature — Henderson et al., Agarwal et al., Engstrom et al.
  on PPO implementation details, Andrychowicz et al.'s on-policy study — is the obvious place.)
- **Equal frames vs equal gradient steps vs equal wall-clock.** Our arms consume frames very
  differently per gradient step: an off-policy method takes one update per 2 frames; a PPO-family
  method takes several epochs per 256-frame rollout. Under a fixed frame budget, is that comparison
  meaningful, and what do multi-algorithm papers do about it?
- If the honest answer is "a shared base makes the comparison uninterpretable", say so — we would
  rather learn that now than after spending T4 hours.

## 4. If precedent is thin: what is the cheapest defensible rule?

Assume you find little direct precedent. Then:

- What is the smallest set of knobs that must be set per-method rather than shared, for the
  comparison to be worth running at all?
- For each, is there a published value we can map from, or a principled default?
- **The entropy coefficient problem, concretely**: Procgen's 0.01 is designed for a 15-way
  categorical distribution. Our action space is a 7-D Gaussian, where differential entropy sums
  over dimensions and is unbounded. A sibling project set it to 0.0 on that reasoning. Is that
  right? Is there a principled way to set it for continuous control, or a published
  continuous-control value from the same method families?

---

## Output we want

1. **A recommendation among (a)–(d)**, with reasoning we can quote in a write-up.
2. **A ranked sensitivity list** — which knobs to spend tuning budget on, most-costly-first.
3. **A manipulation-specific hyperparameter baseline** with sources, if one can be assembled.
4. **A verdict on the 10× learning-rate split**: fatal, serious, or second-order.
5. **A defensible answer on the discount**, given a 500-step dense-reward horizon.

Cite primary sources. Where the literature genuinely does not answer a question, say so — we will
record it as an open question rather than invent a number, and that is a better outcome than a
confident guess.
