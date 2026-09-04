# Brief A — RL-ViGen as implemented: the layer we never audited

> ## ⚠ STATUS: ANSWERED — do not re-commission this brief
>
> Returned as `ext/DR_1_*.md` and since **verified directly against the primary sources**, which
> that pass could not reach (GitHub was robots-blocked for it; the repo is now cloned locally, and
> the NeurIPS supplementary has been read).
>
> **§1.1 SGQN — resolved.** RL-ViGen's Table 6 specifies `aux_lr = 8e-5`, and 8e-5 appears in all
> five of its benchmark tables. Their `cfgs/sgqn_config.yaml` supplies 1e-4 through hydra, so
> upstream never runs at the `0.3` constructor default; we hit it only because we bypass hydra.
> **Applied: 8e-5, quantile 0.9** (0.9 being both canonical SGQN's argparse default and Table 6).
>
> **§2 hyperparameters — transcribed and verified.** See `docs/FAITHFULNESS.md` §0a.
> **§4 provenance — partly open.** The SECANT-fork diff (§4, `wangguanzhi/robosuite` vs our
> `third_party/robosuite`) is the one part still worth doing; SECANT is now in `ext/`.
>
> Kept for the record and because §5 (reception, reuse, OpenReview) is still unanswered.


**Upload with**: `SHARED-CONTEXT.md`, `PREMISES.md`, `FAITHFULNESS.md`.

**Suggested approach**: scope first with ordinary agentic search — locate the RL-ViGen paper, its
NeurIPS Datasets & Benchmarks supplementary, the OpenReview thread, and the GitHub repository, and
find out *whether the hyperparameter and adaptation documentation exists at all*. Then decide where
deep research is warranted. If the supplementary turns out to contain a full hyperparameter table
for the robosuite baselines, most of this brief collapses into transcription and the deep pass
should go to §3 and §4 instead.

---

## Why this brief exists

Our audit compared **canonical papers** against **our code**. But five of our twelve baselines are
RL-ViGen's own implementations, loaded unmodified by file path, and the entire environment is its
code. RL-ViGen therefore sits in the middle of the chain and we have never read what it says about
itself.

This matters because we found things in its code we cannot currently explain, and "is this a bug or
a deliberate re-tune?" is exactly the question its own documentation should answer.

## The decision this feeds

**Whether to change RL-ViGen's inherited hyperparameters, or to treat them as the benchmark's
definition and leave them alone.** These are opposite actions and we cannot pick without knowing
what RL-ViGen intended. Concretely, we are holding a one-line change to `sgqn`'s `aux_lr` that we
will not make until this is settled.

---

## 1. The anomalies, in priority order

### 1.1 SGQN's auxiliary learning rate — the one that matters

RL-ViGen's `algos/sgqn.py` declares:

```python
def __init__(self, aux_lr=0.3, aux_beta=0.9, sgqn_quantile=0.95, **kwargs):
```

Canonical SGQN (Bertoin et al., NeurIPS 2022, arXiv:2209.09203, repo `SuReLI/SGQN`) uses
`aux_lr = 3e-4` for the attribution-predictor optimizer. That is a factor of **1000**, and `0.3`
is not a plausible Adam learning rate.

- Does RL-ViGen's paper, appendix, supplementary, or repo **document** an SGQN learning rate?
- Is `0.3` used in any RL-ViGen experiment whose numbers were published, or is it a default that
  their own launch scripts/configs override? **Check their `cfgs/` tree and shell scripts, not just
  the Python default.**
- Is there any sign this was deliberate — a sweep, an issue, a commit message, a note about
  re-tuning for robosuite?
- Is the same value present in other RL-ViGen-derived forks, and has anyone raised it?

**If it is undocumented and unoverridden, we will treat it as a defect and fix it.** Say so
plainly if that is what the evidence supports.

### 1.2 SVEA's strong augmentation

RL-ViGen's `algos/svea.py` imports `random_overlay` (the Places365-based augmentation belonging to
**SODA**) and applies it as SVEA's strong augmentation. Canonical SVEA uses **random convolution**.

- Does RL-ViGen document this substitution? The SVEA paper does report overlay variants, so this
  may be a considered choice rather than an error.
- Does it affect what their reported SVEA numbers mean, and do they say?
- Practical consequence for us: it is the *only* reason our SVEA needs a 2 GB external dataset, and
  it makes our `svea` and `soda` rows share an augmentation source rather than contrast two.

### 1.3 The base learner substitutions

RL-ViGen implements SVEA and CURL on a **DrQ-v2** backbone, where both were published on **SAC**.

- Is this documented as a deliberate unification (it would be a reasonable benchmark-design choice
  — one backbone, many augmentation strategies)?
- Do they report the resulting numbers as "SVEA" and "CURL" without qualification?
- **Is there a stated rationale we should adopt and cite, rather than re-deriving?**

## 2. RL-ViGen's own hyperparameters and protocol

The core ask. For the **robosuite** backend specifically (not DMC, not CARLA, not Habitat):

- The full hyperparameter table for every baseline they ran. Learning rates, batch size, replay
  capacity, n-step, discount, target tau, encoder dims, exploration schedule, training budget.
- **`action_repeat` for robosuite.** Their `cfgs/config.yaml` defaults to 2 and no task config
  appears to override it, but their robosuite tasks may assume 1. We chose 1 deliberately; we want
  to know what they actually ran, because it is a factor-of-two on every frame budget.
- Training budget in frames or steps, and **which unit** they report.
- Their evaluation protocol: how many episodes, over how many scenes/seeds, deterministic or
  stochastic policy, which statistic, and **whether the training scene is included in the
  evaluation set**. (We include it; we want to know if they do.)
- Whether they used `nstep > 1`, given that most of these methods are 1-step TD in their originals.

## 3. Their published numbers on robosuite Door and Lift

We want a comparison target that is not our own code.

- What returns/success rates do they report for each baseline on `Door` and `Lift`, in `train`,
  `eval-easy` and `eval-hard`?
- At what budget, over how many seeds, with what uncertainty measure?
- **What does a random policy score under their protocol, if they report it?** We measured
  Door ≈ 1.5 and Lift ≈ 7.5 mean raw return with zero successes, and an independent
  implementation in a sibling project reproduced both. A third number would be valuable.
- Are their reward-shaping settings the same as the robosuite defaults? Our protocol records
  `reward_shaping: True`; `Lift`'s shaped reward pays `1 − tanh(10·d)` every step, which is what
  makes a random arm accumulate a large return without ever lifting the block.

## 4. Provenance of the vendored tree

- RL-ViGen vendors a **fork of robosuite** under `third_party/robosuite`. Our own notes say it
  differs from PyPI robosuite of the same version number in **761 files**, and that the
  `Custom01..Custom40` texture names used by the eval regimes are resolved through XML only the
  fork carries. **What exactly did they change, and is it documented?** We need this to state
  what "the environment" is.
- Which robosuite/mujoco versions is their code actually built against? We pin `mujoco==2.3.7`
  because 3.x renames `tex_rgb` and breaks every eval mode while `train` keeps working — a
  particularly nasty asymmetry. Do they document a working set?
- Are there known-broken paths in their robosuite backend — GitHub issues, forks with fixes?

## 5. Reception and reuse

- Who else has used RL-ViGen's robosuite backend, and did they report reproduction problems?
- Are there published critiques of RL-ViGen's baseline implementations?
- Any errata, corrigenda, or v2 of the paper.

---

## Output we want

1. **A verdict on §1.1**, with the evidence: defect, deliberate re-tune, or undocumented-and-unused.
2. **RL-ViGen's robosuite hyperparameter table**, transcribed with a source citation per row, or an
   explicit statement that it is not published.
3. **Their evaluation protocol**, in enough detail that we could reproduce it.
4. **Their reported robosuite numbers**, with budget, seeds and uncertainty.
5. A short list of anything you found that contradicts `FAITHFULNESS.md` §2.

Where the answer is "not documented", say that — it is itself a finding, and it converts several of
our open questions from "look it up" into "decide and record".
