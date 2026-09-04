# First-hand materials I do not have

Written 2026-08-10 after the first deep-research result (`ext/DR_1_*.md`) landed. Ordered by what
it blocks. **"Blocked" means a claim I currently cannot verify and would otherwise have to state on
someone else's authority.**

## 0. What is NOT blocked, so it does not appear below

The DR pass on RL-ViGen could not read a line of its source — GitHub blob/raw/tree, jsDelivr,
Software Heritage and code-search mirrors were all robots-blocked. **I have that source vendored
locally**, so every item it marked `UNVERIFIED-FROM-SOURCE` is now closed by direct reading. See
`docs/FAITHFULNESS.md` §0a. That pattern will repeat: an external agent is often blocked on exactly
the code I already hold, so **send code questions to me and literature questions outward.**

---

## A. Blocking — I cannot verify a claim I am relying on

### A1. ~~RL-ViGen paper + NeurIPS supplementary~~ — **CLOSED 2026-08-10**

Delivered into `ext/baseline_resources/benchmarks/` and read directly. **Every cell of Table 2 and
Table 6 that this project acted on is VERIFIED verbatim** against the supplementary, cross-checked
with arXiv 2307.10224v3. The SGQN fix (8e-5 / 0.9 / 0.7), `action_repeat=1`, DrQ `nstep=1`,
`feature_dim` 256-for-SVEA/SGQN and the Door 6e5 / Lift 8e5 budgets all stand.

Also settled: 5 seeds and 95% CIs are in the **main paper §4**, not the supplementary; reward
shaping for robosuite is **never characterised anywhere**; batch size, target tau and the
exploration schedule are **absent for robosuite** and are therefore decide-and-record items.

Caution recorded: `rlvigen_2304.08479.pdf` is a *different paper* (vision-language prompts), not an
earlier RL-ViGen draft.

### A2. The canonical algorithm repositories, as source
Everything in `FAITHFULNESS.md` §2–§4 about *canonical* behaviour is from subagent reports. They
were careful and flagged their own gaps, but for the five arms we inherit and the three we wrote,
I am comparing our code against a **description** of the reference, not the reference.
**Want**, in priority order:

| repo | why it matters here |
|---|---|
| `SuReLI/SGQN` | the canonical 3e-4 / 0.95 claim, and whether its own code matches its paper (the DR could not check) |
| `nicklashansen/dmcontrol-generalization-benchmark` | SVEA **and** SODA. Settles the random-conv-vs-overlay question at source, and SODA's aux-lr paper/code split |
| `denisyarats/drq` + `facebookresearch/drqv2` | the `base` block is DrQ-v2's; I should read it rather than trust a table |
| `MishaLaskin/curl` | the five paper-vs-code disagreements |
| `openai/phasic-policy-gradient`, `rraileanu/idaac`, `microsoft/IBAC-SNI`, `bmazoure/ctrl_public` | the four we wrote ourselves, with no reference to check against |
| `SumeetBatra/ALDA_Official` | confirm our `AldaConfig` matches |

A shallow clone of each is a few hundred MB total and would let me diff instead of paraphrase.

### A3. SECANT's robosuite fork — `wangguanzhi/robosuite`
Our `setup/install_assets.py` records "the two robosuites differ in 761 files" — measured against
**PyPI** robosuite. The DR points out that is the wrong baseline: RL-ViGen builds on SECANT's
already-modified fork, so that 761 over-attributes SECANT's changes to RL-ViGen.
**Want**: the SECANT fork, to diff against instead.
**Unblocks**: an honest statement of what "the environment" actually is — currently one of the
weakest claims in the repo.

---

## B. Blocked and only you or DZ can unblock

### B1. ~~The reference evaluation~~ — WITHDRAWN as a blocker, 2026-08-10

Previously listed here as the highest-value blocked item, on the grounds that DZ had mentioned a
defect in an existing evaluation. **That was the wrong framing and I am dropping it.** Identifying
and managing evaluation caveats is my responsibility, not something to wait on: there is no known
"proper" version to be handed, `Nd_ln.py` was never a standard, and neither a prior in-house
implementation nor a paper config for a *different* benchmark is a gold standard either.

What replaces it is work, not a request: RL-ViGen's `eval.py::robo_eval` is now readable here and
is the closest thing to an external reference that exists, and `DISCREPANCY_MATRIX.md` supplies a
failure-derived list of eval traps (B31's denominator, B33's checkpoint oscillation, the
truncation-as-termination bug). Both are being used. See `docs/PREMISES.md` P4.

### B2. Confirmation on the ALDA citation
`docs/SUPERVISOR-BRIEFING.md` §1.1. Needs a human answer, not a search.

---

## C. Wanted, not blocking

- **DeGuV paper (arXiv:2509.04970)** — the only published *per-task* Door/Lift numbers on this
  backend (RL-ViGen aggregates over three tasks, so it has no per-task figure). Would give an
  independent sanity target. The DR quoted its table; I have not read it.
- **RL-ViGen OpenReview thread** — blocked for the DR too (browser check). Would say whether
  reviewers challenged the baseline implementations.
- **RL-ViGen GitHub issue #6** ("About parallel training") — blocked for the DR. Bears directly on
  whether our `num_envs=1` constraint is real or worked around upstream, which is the single
  biggest lever on the PPO family (`PREMISES.md` P9).
- **Procgen environment stack** — only if we decide to validate PPG/IBAC-SNI/CTRL against published
  numbers (brief C). Not needed unless that decision is taken.

---

## D. How to get these to me most usefully

- **Papers**: PDF into `ext/`. I copy out and cite by table/line.
- **Code**: a clone under `ext/` is ideal — then I diff rather than paraphrase, and the diff is
  reproducible. Shallow clones are fine; I only need source, not history.
- **If web access were available to me directly**, A1–A3 and C would mostly close without you
  fetching anything. That is the highest-leverage change to my situation, and worth knowing whether
  the robots-blocking that stopped the DR agent would stop me too.

---

## Update 2026-08-10 (late): most of this list is now closed

`ext/papers-sorted/` delivered eleven OpenReview PDFs plus SECANT's paper and supplementary, and
the reference repositories are cloned. Status:

- **A1 RL-ViGen paper/supplementary** — CLOSED, tables verified verbatim.
- **A2 canonical repos** — CLOSED for SGQN, SVEA/SODA, PPG, CTRL, IDAAC, ALDA; all cloned and read.
- **A3 SECANT robosuite fork** — **CLOSED, and the premise was wrong.** SECANT's fork is robosuite
  **1.0.0**; RL-ViGen vendors **1.4.0**. Diffing them isolates nothing. Our original PyPI-1.4.0
  comparison was correct. SECANT's own papers never mention forking robosuite at all.
- **C OpenReview** — CLOSED for RL-ViGen, SVEA, SGQN, RAD, DrQ, DrQ-v2, ALDA, CTRL, IBAC-SNI.
- **B1/B2 supervisor items** — B1 withdrawn as a blocker (ours to manage); B2 (ALDA citation)
  remains a correction to report, not a question to ask.

**Still genuinely wanted:**
- A pristine **PyPI robosuite 1.4.0** sdist, to re-measure the "761 files differ" claim. The venv's
  `robosuite` is RL-ViGen's own editable install, so it cannot serve as the comparison baseline.
- **RL-ViGen main paper Appendix D (lines 645–693)**, where the reward and max-step settings were
  moved during rebuttal. Not present in the OpenReview PDF. SECANT covers the reward question well
  enough that this is now a nice-to-have.
- **DeGuV (arXiv 2509.04970)** per-task Door/Lift numbers — the only published per-task figures on
  this backend.
