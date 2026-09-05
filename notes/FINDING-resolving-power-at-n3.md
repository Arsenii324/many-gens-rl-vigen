# What the production design can actually resolve, and why the number in circulation is the
# wrong one

Found 2026-09-05 in the full-project audit, by asking the question the owner framed as "are the
reported results actually going to show the true performance of the algorithms".

## The number that would be quoted is for a plan that no longer exists

`docs/CONSTRUCTION.md:805-845` does this analysis properly and reaches a sentence it explicitly
marks as the one to carry forward:

> **So the five-seed plan resolves differences of about thirty percent, not five points.** That is
> the sentence to carry into any comparison this project reports.

**The plan is no longer five seeds.** `datasphere/native/production-schedule-v100.json` sets
`"seeds": [101, 102, 103]` — **n = 3**. The same table's n=3 row says **39.7%**, but the prose
headline, the part written to be quoted, is the five-seed number. Anyone reading the reasoning
rather than the table row carries ~31% into a design that is not the one being run.

## And the n=3 row is itself optimistic, for a checkable reason

`scripts/plan_seed_budget.py:32,44` computes `d = z * CV * sqrt(2/n)` with `Z_80_POWER = 2.802`
— the **normal** approximation (1.960 + 0.842). At n = 3 per arm the relevant distribution is t
with df = 2n-2 = 4, where the correct multiplier is `t(.975,4) + t(.80,4) = 3.717`. The normal
approximation is asymptotic and the plan sits at the one place it is least valid.

Recomputed (scipy, `CV = 17.4%` mid-curve and `12.2%` at convergence, both from C41 as the doc
uses them):

| seeds/arm | script (z) | **t-corrected** | t-corrected at convergence CV |
|---:|---:|---:|---:|
| **3** | 39.8% | **52.8%** | 37.0% |
| 5 | 30.8% | 35.2% | 24.7% |
| 10 | 21.8% | 23.1% | 16.2% |
| 20 | 15.4% | 15.8% | 11.1% |
| 50 | 9.8% | 9.8% | 6.9% |

The two methods **agree at n = 50** and diverge only at small n, which is the signature of a
correct t-correction rather than an arithmetic error. Seeds needed for a 20% difference: **13**,
not the doc's 12.

## What this means, stated the way the doc asks — and corrected once more, review 14 section 24

**The operative sentence for the production design is: three seeds resolve differences of roughly
fifty percent, not thirty.**

**CORRECTED 2026-09-05, same day, by review 14 §24 — the word "lower bound" above overclaimed
what one same-seed pair can support, and I had missed this on my own first pass.** The DIRECTION of
both adjustments is real and defensible: the CV comes from C41's pair sharing *a configuration and
a seed*, so it captures backend nondeterminism only, and genuine seed-to-seed variation is
additional on top of that; the t-correction is exact given the CV. But the CV *itself* — 17.4% — is
a point estimate from a single pair (one degree of freedom's worth of information about backend
noise), and a point estimate from n=1 has enormous sampling uncertainty of its own. Calling 53% a
"guaranteed lower bound" conflates "the adjustment direction is structurally correct" with "the
specific number is reliably known" — the second claim the evidence does not support. **Treat ~53%
as an illustrative resolution calculation under the current, thin variance evidence, not as a known
property of the benchmark.** The qualitative conclusion is unaffected: n=3 resolves only coarse
effects, and if exact ranking matters, more independent seeds — not more arithmetic — is what would
actually tighten this number.

## Why this matters beyond bookkeeping

Twelve baselines admit **66 pairwise comparisons**
(`notes/proposal-inference-and-checkpoint-selection.md:98`, which already warns that with three
seeds "it is easy to narrate whichever comparison came out favourably"). If the design cannot
resolve differences below about half the return scale, then most of those 66 comparisons are
unresolvable in principle, and the risk is not a wrong number — it is a **true number narrated as
if it were a ranking**.

Published generalization gaps among these methods are typically far below 50%. This design is
therefore well suited to answering *"does this method generalize at all, and by roughly how much"*
and poorly suited to *"method A beats method B"* for any close pair.

## What I recommend

1. **Do not silently increase seeds.** Going from 3 to 5 buys 52.8% → 35.2%; still above most
   effects of interest, at +67% compute. It is not obviously the right purchase, and it is the
   owner's call — raised as **A28**.
2. **Fix the carried sentence now.** Whatever n is chosen, the report must state the design's
   resolving power in the terms this project already decided to hold itself to. That costs nothing
   and is the single highest-leverage honesty measure available.
3. **Correct `plan_seed_budget.py` to use t.** One-line change to the multiplier; the script is
   otherwise sound and its derivation of CV from paired runs is careful.
4. **Prefer within-method claims and effect sizes with intervals over a cross-method ranking table**
   — which is what `proposal-inference-and-checkpoint-selection.md` already recommends. This finding
   strengthens that recommendation rather than changing it.

**What would change this:** a real between-seed CV measurement. Every number here rests on ONE
same-seed pair. `docs/ASSURANCE.md:57` already lists between-seed variance as a known gap with a
first measurement launched 2026-08-29. That measurement, not more arithmetic, is what would improve
the estimate — as CONSTRUCTION.md itself says: "a second pair would improve the estimate more than
any refinement of the arithmetic."
