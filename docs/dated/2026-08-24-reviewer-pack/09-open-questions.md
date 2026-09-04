# What we most want challenged

**Written 2026-08-24. Dated snapshot, not a living document.**

Real questions, not rhetorical ones. Each states what we currently believe, so you can attack the
belief rather than guess at it.

---

## Q1. Given the replicate, is *any* of this measurable at the current protocol?

The same checkpoint, same seed, gives **19/200 vs 28/200** successes
([03](03-what-was-measured.md) §2). Our four fresh cells have ratios 0.030, 0.176, 0.280, 0.877.

**What we believe:** the extremes separate; the middle two probably do not; and 20 episodes/scene is
too few.

**What we want:** tell us what the protocol *should* be. Is the fix more episodes, more seeds, a
different statistic, a paired design that reuses episode seeds across arms, or something structural?
And is there a reason to think a fixed policy at a fixed seed *should* be reproducible here at all —
i.e. is our expectation of determinism itself naive for MuJoCo-on-Metal?

**Cheapest thing we could do that we have not:** re-run one grid three times and read the spread
directly. It costs an evaluation pass. **We should have done this already.**

---

## Q2. Why finish a study where nothing is attributable to the algorithm?

Method identity is perfectly collinear (r = 1) with seven configuration choices, so no observed
difference is attributable to the mechanism ([01](01-question-and-design.md) §4).

**What we believe:** the deliverable is a *benchmark-style* claim — "under each method's own
recommended configuration, here is how much each retains" — not a causal one, and that this is worth
producing because it is what a practitioner choosing a method actually faces.

**What we want:** is that defensible, or is it a rationalisation of a design that cannot answer the
question it was posed? If it is defensible, what must the write-up say so that no reader takes the
table as mechanism evidence? If it is not, what is the minimum change that makes it a real study —
and would that change mean abandoning fidelity for controlled equalisation, which is the one thing the
design was built to refuse?

---

## Q3. Is C54 disqualifying for the archived checkpoints, or recoverable?

Those checkpoints were **provably not trained on the distribution their config declares**, and no
mechanism has been found despite ruling out the obvious causes
([05](05-what-would-embarrass-us.md) §2).

**What we believe:** the remaining hypothesis is run length, because the replay buffer unlinks each
episode as it is consumed and so cannot testify about a run's middle. The witness tooling exists to
settle this and the decisive experiment — one 120k-frame run retaining every episode's reset frame —
has not been run.

**What we want:** should any result from those checkpoints be used at all before the mechanism is
found? We have been treating them as usable-with-caveats. The alternative is treating them as void,
which costs three of our eight grids.

---

## Q4. Is the contamination screen (C65) sound, or are we over-reading a small sample?

All eight grids split by the sign of the train→eval change: four fresh cells below 1 (0.03–0.88),
three archived checkpoints above (1.89–2.79), random-policy control at **1.02**.

**What we believe:** a correctly-trained policy does not do better away from its declared training
condition, so a ratio significantly above 1 is a provenance alarm rather than a result. It is now
enforced in `scripts/regime_retention_report.py`.

**What we want:** the honest weakness is that the "above 1" side is **three grids of one run**, so it
is closer to n=1 than n=3. Is the screen sound reasoning that happens to have thin support, or is it
pattern-matching on a single contaminated run? What would you require before enforcing it in a tool?

---

## Q5. Does the shaping-ceiling reinterpretation of RL-ViGen's published numbers hold?

Their `DrQ-v2` on Door Easy is **3.6**, which we read as **1.4% of a 250 shaping ceiling** — i.e. an
agent that essentially never approached the handle. Ours reads 3.49 at 50k and 131.05 by 100k, at one
twelfth of their budget ([03](03-what-was-measured.md) §4).

**What we believe:** their runs genuinely failed to learn Door, and this is visible in their own
number once the reward structure is understood.

**What we want:** this is a strong claim about someone else's published work, resting on a ceiling we
derived by reading the reward function and **never verified empirically**
([07](07-unknown-unknowns.md) §4). Is the derivation sound? And is there a reading in which the two
numbers are simply not the same quantity, which would make the comparison void rather than damning?

---

## Q6. How many seeds does this design actually need?

`drqv2` seed 6 solves 59/200; seed 7 solves 0/200. C41 puts run-to-run variation near 49%.

**What we believe:** n=1 is indefensible and we have been proceeding anyway because each cell is
expensive.

**What we want:** the calculation. Given the effect sizes we hope to detect and the variance we have
measured — plus the evaluation noise from Q1, which stacks on top — how many seeds per cell, and how
many cells, does a twelve-row table need to mean anything? **If the answer is "more than you can
afford", we would rather know now**, because the honest response is to narrow the claim rather than
run out of compute discovering it.

---

## Q7. Should SGQN run upstream's shipped value or the paper's? (C64)

Upstream ships `aux_lr: 1e-4`, `sgqn_quantile: 0.93`. RL-ViGen's own paper Table 6 says **8e-5 / 0.9**.
Our clone runs the shipped values, and a document incorrectly certifies otherwise
([04](04-the-twelve-baselines.md)).

**What we believe:** run what upstream ships. The null is "the original repository, running its own
`train.py`", and hand-tuning one baseline toward its paper is exactly the join the founding rule
exists to refuse.

**What we want:** the counter-argument is that RL-ViGen's *published curves* — the ones this
comparison is calibrated against — were produced at Table 6's values, so matching the repo makes our
SGQN incomparable to the very numbers it is meant to sit beside. Which fidelity wins when a
benchmark's code and its own paper disagree? And does the answer generalise, given that **four of
twelve** baselines have this paper-versus-repo ambiguity (CURL 5 hyperparameters, SODA aux lr, RAD
batch size three ways, SGQN)?

---

## Q8. Is the process itself the problem?

Roughly 29 lines are written about the work per line of the work, for three measured cells
([08](08-methodology-under-review.md)).

**What we believe:** the register and the falsifier discipline have caught real defects that would
otherwise have shipped — C54, C55, C64 are concrete instances — so the machinery is earning its cost.

**What we want:** an outside read on whether that is true or whether it is a story we tell ourselves.
A specific version: every defect the project has found sits at a **join**, and every instrument it has
built checks an **artifact** ([06](06-unknown-knowns.md) §1). That was written down four days before
C64 — another join defect, found by hand — arrived. Is there an instrument that checks seams, or is
this only fixable as a habit? We deliberately have not tried to build one, on the grounds that
building before understanding is how the last several instruments went wrong.
