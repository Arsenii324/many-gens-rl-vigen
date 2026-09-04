# Research briefs for external deep-research agents

Four independent briefs. They do not depend on each other and can run in parallel, but they are
listed in priority order — **A is worth the most**, because it closes a gap the local audit could
not reach at all.

## What to upload, per agent

Each agent takes up to five documents. Every brief needs the same three companions:

| # | file | why |
|---|---|---|
| 1 | the brief itself | the questions and the decision each feeds |
| 2 | [`SHARED-CONTEXT.md`](SHARED-CONTEXT.md) | what the project is, where each implementation came from, the hardware and compute limits, **and which of our findings are solid vs provisional** |
| 3 | [`../docs/PREMISES.md`](../docs/PREMISES.md) | the decision surface and the degrees of freedom |
| 4 | [`../docs/FAITHFULNESS.md`](../docs/FAITHFULNESS.md) | per-algorithm canonical-vs-ours, with source tags |

That leaves a fifth slot free. Use it for a paper the agent should read before planning — for
**Brief A**, the RL-ViGen paper or its supplementary is the obvious candidate if you have it
locally.

## The four

| brief | question | decision it feeds |
|---|---|---|
| **[A — RL-ViGen as implemented](brief-A-rlvigen-as-implemented.md)** | What does RL-ViGen itself document about its ports, its robosuite hyperparameters, and its evaluation protocol? | Whether to change its inherited hyperparameters or treat them as the benchmark's definition. **We are holding a one-line `sgqn` fix on this.** |
| **[B — hyperparameters for manipulation](brief-B-hyperparameters-for-manipulation.md)** | Do DMC-locomotion and Procgen hyperparameters transfer to 7-DoF manipulation, and which knobs actually matter? | What rule sets hyperparameters across arms — shared base, published per-method, manipulation-specific base, or partial tuning. |
| **[C — continuous on-policy](brief-C-continuous-onpolicy.md)** | How should PPG / IBAC-SNI / CTRL be adapted to a 7-D Gaussian policy, and does any such port already exist? | Whether those four baselines are scientifically reportable here, need Procgen validation first, or should be dropped. |
| **[D — evaluation protocol](brief-D-evaluation-protocol.md)** | Is the protocol we built without a reference defensible? | Whether to change it **before** spending real compute — it is hashed, so changing it later invalidates every prior number by design. |

## Status, 2026-08-10

**A, B, C and D have all been returned** (`ext/DR_1..DR_4`). A and C carry an ANSWERED banner
naming the parts still worth re-asking. Their most valuable outcome was not any single number but
the division of labour: **every pass was robots-blocked from the code, and none was blocked from
the papers.** The repositories are now cloned into `ext/`, so the standing rule is —
**code questions to whoever holds the tree, literature questions outward.**

## Scoping first

Briefs A, B and C each say so in their own text, but in general: **ask for an ordinary agentic
search pass before committing to deep research.** Two of these have a cheap short-circuit —

- **A**: if RL-ViGen's supplementary contains a full robosuite hyperparameter table, most of the
  brief becomes transcription and the deep pass should move to its §3–§4.
- **C**: if a continuous-action PPG or IBAC-SNI already exists anywhere, the theory sections are
  moot and we should read that code instead.

## What we are trying to avoid

The whole audit exists because plausible-looking values turned out to be silently wrong — a
learning rate 1000× off canonical, sitting in a default no config mentioned, producing numbers that
did not crash and did not mean anything.

So: **an explicit "I could not confirm this" is worth more to us than a confident number**, and
"searched X, Y, Z and did not find it" is a usable result where a bare "does not exist" is not.
Disagreement with `PREMISES.md` or `FAITHFULNESS.md` is welcome — `SHARED-CONTEXT.md` §3 marks
exactly which of their claims are provisional and why.
