# Library survey — what the established RL libraries do, and where we differ

Commissioned 2026-08-17 to answer three questions that the audit
(`docs/AUDIT-2026-08-17.html`) could otherwise only assert:

1. **Can we borrow anything?** Does any established library already implement our twelve
   baselines, so that some part of this work is redundant?
2. **Where does our practice differ from the field's?** Especially on continuous action heads,
   which we had to author for four Procgen-native algorithms with no upstream reference.
3. **Is our stance defensible?** "Duplication across baselines is free; any join carries a
   burden of proof" — who in the field agrees, who disagrees, and on what grounds.

## Method, and its limits

Each survey was run by a subagent that **had not read** `docs/AUDIT-2026-08-17.html` or anything
else in this `docs/` tree. That was deliberate: a reviewer who has read the report tends to
confirm it. The cost is that they occasionally re-derive something we already knew, which is
cheap, and the benefit is that agreement means something.

Every job was given the same brief: cite a locator for each claim, write `UNVERIFIED` plus what
was tried rather than guessing, and keep *implements* / *documents* / *benchmarks with published
numbers* as three separate columns, because they diverge constantly.

**These are subagent reports, lightly edited for structure and not independently re-verified
line by line.** Claims marked UNVERIFIED are the reports' own admissions. Where two reports
covered the same library and disagreed, both readings are preserved and the disagreement is
flagged in place rather than resolved by picking one. Before anything here becomes load-bearing
for a result, re-check it against the primary source — the locators are recorded so that is
cheap.

## What is here

**`raw/` holds every subagent output verbatim and unedited, and is the source of record.**
Nothing there has been merged or reconciled — the two passes over Pearl/Dopamine/Acme/Mushroom-RL
are kept as two separate files precisely because they disagree in places, and a merge would
destroy that. Read `raw/` when you want to know what was actually said.

| file | scope |
|---|---|
| `raw/broad-sweep-14-libraries.md` | fourteen libraries: SKRL, SB3 + sb3-contrib + Zoo + sbx, Tianshou, jaxrl/jaxrl2/jaxrl_m, CleanRL, PureJaxRL, Brax, Acme, Dopamine, Pearl, Mushroom-RL, garage, AgileRL |
| `raw/cleanrl.md` | CleanRL in depth: `ppg_procgen.py` vs `openai/phasic-policy-gradient`, declared deviations, published numbers, eval protocol |
| `raw/pearl-dopamine-acme-mushroom-run1.md` | Pearl / Dopamine / Acme / Mushroom-RL, first pass |
| `raw/pearl-dopamine-acme-mushroom-run2.md` | same four libraries, second independent pass |
| `raw/torchrl.md` | TorchRL in depth: coverage, how fidelity is (not) established, ~20 cited cases of a shared component silently changing an algorithm's numbers, continuous heads, metric vocabulary, robosuite |
| `raw/pytorch-ecosystem-agy.md` | torchtune, torchforge, torchbeast, PyTorch RL recipes (agy, `gemini-3.6-flash-high`) |
| `raw/_brief-given-to-jobs.md` | the brief they were all handed |

Anything named `synthesis-*.md` is **this project's reading of** the raw material, not the
material itself, and says so in its own header:

| file | derived from |
|---|---|
| `synthesis-cleanrl.md` | `raw/cleanrl.md` |

The other four raw reports have **no synthesis yet.** All the sweeps have now landed, so the
reason has changed: it is no longer "wait for the evidence" but "the synthesis has not been
written." The raw files are complete and are the source of record until it is.

## The TorchRL sweep landed — and it answers the question this section used to pose

TorchRL is the most direct counter-example to this project's stance: a modular library where
algorithms share `objectives/`, `collectors/`, `data/replay_buffers/`, `modules/`. The question
put to it was *has sharing ever silently changed an algorithm's behaviour there?* — with a
well-searched "no" counting as evidence against our framing and a cited "yes" as the strongest
external support it could have.

**It is a cited yes, roughly twenty times over** (`raw/torchrl.md` §3.2). The four that matter:

- **Issue #1662 / PR #1661** — the shared value estimators read `terminated` from the `done` key,
  so **every algorithm using GAE or TD(λ) bootstrapped as if time-limit truncations were
  terminations.** Nothing crashed. This is our own D1 finding, in the field's flagship library,
  as a two-line diff. It compounds with issue #1837, where the shared `StepCounter` transform
  *blanks* native truncation — two individually-defensible components whose composition destroys
  bootstrapping silently.
- **PR #3679** — the shared `PPOTrainer` shipped `gamma=0.9` and an **inverted** `lmbda=0.99`,
  while the duplicated `sota-implementations/ppo/` script had the right values all along. The
  join was wrong; the duplicate was right.
- **Issue #4063** — migrating a hand-written PPO loop to the shared trainer recomputes GAE once
  per epoch against a moved critic, "selected implicitly by the hook placement", so that
  *"migrating to PPOTrainer can otherwise silently change the training semantics."*
- **Issue #2199 / PR #4080** — one shared `TanhNormal` produced wrong scores and gradients across
  SAC, CQL, CrossQ, REDQ, A2C, PPO, Decision Transformer, GRPO and V-trace. Open 26 months.

And the reason none of it was caught: TorchRL's benchmarks are **wall-clock only**
(`alert-threshold: '200%'`, and `benchmarks/test_objectives_benchmarks.py` is 1389 lines with
**zero asserts**); its 25,275-line objectives suite compares TorchRL against TorchRL, never
against a reference — which is exactly why #1662 stayed green, since both code paths shared the
misinterpretation. The report's own conclusion: *"TorchRL's CI can prove a loss module is fast,
differentiable, shape-correct, non-mutating, key-consistent and self-consistent across its own
implementations — and cannot prove its value is right."*

**Two things it gives us that are not arguments but citations:**

- `AddStateIndependentNormalScale` (`tensordict/nn/distributions/continuous.py:90-190`) — a
  trainable per-dimension parameter, `init_value=0.0`, `scale_mapping="exp"` — **is our four
  authored heads**, and it is what TorchRL uses for every on-policy MuJoCo actor it ships. Our
  head is the field's standard for that family, not an improvisation.
- `knowledge_base/DEBUGGING_RL.md` §"Action Space" endorses env-side clipping as the *correct*
  framing (*"This should be thought of as part of the environment"*) and names the actual error
  as scoring the **clipped** action — which is what we avoid and what SKRL does.

**And the convergence worth keeping:** TorchRL's own recipes duplicate rather than join —
*"each example is independent of each other for the sake of simplicity"* — with nine
identically-named helpers reimplemented across eight off-policy `utils.py` files. The library is
the most-shared thing in the ecosystem; the scripts on top of it are not.

Three of these reports overlap: `broad-sweep-14-libraries.md` and the two
`pearl-dopamine-acme-mushroom-run*.md` files independently cover Pearl, Dopamine, Acme and
Mushroom-RL. All three readings are kept rather than reconciled.

## The short version, if you read nothing else

*Written 2026-08-17, after all sweeps had landed, including TorchRL.*

**Four things the fourteen-library sweep added, two of which change a plan:**

- **SKRL is not the robosuite answer, and the premise that it was is false.** SKRL **removed**
  robosuite support in v2.0.0 (2026-04-08), and even in v1.4.3 its wrapper flattened all
  observations into a 1-D vector — pixel-based robosuite was impossible there without rewriting
  the wrapper. This closes off the one library that looked like a shortcut for our env.
- **SB3's fidelity position is narrower than its reputation.** Its validation target is SB2 and
  the gSDE paper's PyBullet table, *not* the original algorithm papers, and the RL Zoo's own
  benchmark table carries the disclaimer *"this is not a quantitative benchmark as it corresponds
  to only one run."* Do not cite SB3 as though it reproduces the papers.
- **CleanRL's JMLR paper argues our exact case, from the maintainer's side.** Its "painless
  performance attribution" is our "a join can silently change whose numbers you are reporting."
  This is stronger than the readability-only reading in `raw/cleanrl.md`, and supersedes it. SB3
  partially agrees in its own developer guide: *"The library is not meant to be modular."*
- **On the clipping bias, SB3 and SKRL do opposite things.** SB3 stores the **unclipped** action
  (the correct choice, and CleanRL's detail 5). SKRL stores the **clipped** one and takes its
  density under the unclipped Normal — in its own shipped manipulation examples, undocumented.
  That is our Finding 6 occurring in a maintained library, which is the strongest available
  evidence that it is a real failure mode and not a pedantic one.

**Nothing to borrow.** Across all eight libraries actually surveyed, not one implements any of
DrQ-v2, CURL, RAD, SVEA, SGQN, SODA, PPG, IDAAC/DAAC, IBAC-SNI, CTRL, or ALDA as a runnable
agent. SAC is universal; Dopamine has a *discrete Atari* DrQ that is a different algorithm from
the continuous one RL-ViGen uses and would be a false positive if counted; Acme has DrQ-v2's
visual torso grafted onto DMPO's training loop in an example script, which is a join of exactly
the kind this project treats as work. **robosuite appears in none of them** — zero grep hits,
repo-wide, in every case checked.

**Our stance has a PyTorch-official ally, on our own grounds.** torchtune's own design
documentation says *"Code duplication is preferred over unnecessary abstractions"* and *"No
dependency on training frameworks and no implementation inheritance."* Dopamine is close behind:
*"a relatively flat class hierarchy, with no abstract base class... we recommend modifying the
agent code directly."* CleanRL accepts duplication explicitly but argues it on **readability and
debugging** grounds, never on fidelity — our framing is stronger than anything found in its docs.
Acme, Pearl and Mushroom-RL sit at the opposite pole, and Pearl markets modularity against
Dopamine by name.

**Our four authored heads are the field's minority choice, and the field documents why.** Every
continuous head found — Pearl, Dopamine SAC, Acme, Mushroom-RL — uses **state-dependent** log_std
and **tanh squashing**. Ours use state-independent log_std initialised to 0 and rely on the
environment's `np.clip`. Both halves of that are defensible and one is even standard practice for
PPO — CleanRL's own "9 details for continuous action domains" lists *"state-independent log_std
initialized to 0"* as the PPO convention — but the clipping half is the one the libraries write
warnings about. Acme's `TanhTransformedDistribution` carries a closed-form correction for the
probability mass outside the clip; Mushroom-RL and Dopamine both clip only for numerical
stability in the *inverse*, never in a way that biases the density. We clip in the forward
direction and score the unclipped action. `scripts/probe_geometry.py` measures the size of that:
**31.8% of action components at initialisation**, against ~0% for the eight squashed baselines.

**Prior art for the heads: there is none, and that is now established rather than assumed.**
`openai/phasic-policy-gradient/phasic_policy_gradient/distr_builder.py` does contain a Gaussian
factory, but it is unreachable dead code (`tensor_distr_builder` dispatches only `Discrete(2)`
and `Discrete`, else raises) and it is fixed-variance — `warnings.warn("Using stdev=1")`,
`scale=1.0`. So the upstream ships a vestigial unit-variance Gaussian and no learned one. Any
learned-`log_std` head is our design decision, not a port. That is worth stating in exactly those
terms in the audit.
