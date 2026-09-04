# CleanRL as a fidelity reference — synthesis

> **This is a synthesis, not the source.** The subagent's report is preserved verbatim at
> `raw/cleanrl.md`; read that if you want what was actually said. This document reorganises it
> and adds the blockquoted **"Bearing on us"** notes, which are *this project's* reading and were
> not part of the subagent's output. Where the two differ, the raw file wins.

Commissioned to answer a direct question: **does Procgen work use
`vwxyzjn/cleanrl/cleanrl/ppg_procgen.py` or `openai/phasic-policy-gradient`?** — and, more
broadly, whether CleanRL is a usable reference for our other baselines, our harnesses, and our
algorithms.

Provenance and caveats: `CONTEXT.md`. Subagent report, locators preserved, not independently
re-verified line by line.

---

## 1. The answer: they are different codebases, and CleanRL says so

`cleanrl/ppg_procgen.py` is a **from-scratch single-file reimplementation, not a fork.** Its docs
name the original as a "Reference resource" and state the motivating premise directly
([`docs/rl-algorithms/ppg.md` L13–15](https://github.com/vwxyzjn/cleanrl/blob/master/docs/rl-algorithms/ppg.md),
rendered at <https://docs.cleanrl.dev/rl-algorithms/ppg/>):

> The original code has multiple code level details that are not mentioned in the paper. We found
> these changes to be important for reproducing the results claimed by the paper.

Every implementation detail is pinned to a line in original commit `c789b00`/`7295473`.

**Our `runnable/ppg` clones `openai/phasic-policy-gradient`, i.e. the original**, which is the
correct choice under this project's null. CleanRL is a reference *about* that original, not a
substitute for it.

### 1a. The five details CleanRL had to match — a direct fidelity checklist for our clone

These are things CleanRL found in the original code and not in the paper. Since we run the
original, we get all five for free — but they are exactly the list to check if anyone ever
proposes touching our PPG clone.

1. **Full-rollout sampling in the auxiliary phase** — *"Instead of randomly sampling observations
   over the entire auxiliary buffer, PPG samples full rullouts from the buffer (Sets of 256
   steps). … This change gives a decent performance boost."* (`ppg.py#L173`)
2. **Batch-level advantage normalization** — *"PPG normalizes the full batch of advantage values
   before PPO updates instead of advantage normalization on each minibatch."* (`ppo.py#L70`;
   exposed as flag `adv_norm_fullbatch: bool = True`)
3. **Normalized network initialization** (`impala_cnn.py#L64`) — default torch Kaiming-Uniform,
   then each layer's weights divided by their L2 norm along the `input_channels` axis (axis 1 for
   Linear; 1,2,3 for Conv), then multiplied by a scale: **0.1** for value/policy/auxiliary-value
   heads, **1.4** for the FC after the last conv, **≈0.638** for conv layers. Contrast noted in
   their docs: PPO used orthogonal init on only the policy/value heads with scale 0.01 / 1.0.
4. **Adam epsilon = 1e-8** (torch default) *"instead of 1e-5 which is used in PPO"* (`ppg.py#L239`).
5. **Same `gamma` in the `NormalizeReward` wrapper** — flags that `openai/train-procgen` used
   `gamma=0.99` in `VecNormalize` but `gamma=0.999` for PPO, and calls the mismatch
   *"technically incorrect"* ([cleanrl#209](https://github.com/vwxyzjn/cleanrl/pull/209)).

> **Bearing on us.** Item 3 is the interesting one. CleanRL says *"Normalized network
> initialization scheme seems to matter a lot"* — and the initialisation of the head is precisely
> what `scripts/probe_heads.py` measures for our four authored continuous heads. Our probe checks
> the **log_std** init (all four at σ=1, entropy 9.93257); it does **not** check the trunk's
> normalized init, which is the part CleanRL says matters a lot. That is a real, named gap in our
> instrumentation, and it is cheap to close.

### 1b. CleanRL's three declared deviations from the original

- *"The original PPG code supports LSTM whereas the CleanRL code does not."*
- *"The original PPG code uses separate optimizers for policy and auxiliary phase, but we do not
  implement this as we found it to not make too much difference."*
- *"The original PPG code utilizes multiple GPUs but our implementation does not."*

Plus: *"All the default hyperparameters from the original PPG implementation are used. Except
setting 64 for the number of environments"*; *"Skipping every alternate auxiliary phase gives
similar performance on easy environments"*; *"using layernorm with orthogonal initialization also
works"*; mixed precision is safe in the aux phase but *"makes training unstable"* in the policy
phase.

**Doc bug worth knowing:** the variants table mislabels `ppg_procgen.py` as *"For classic control
tasks like `CartPole-v1`."*

---

## 2. Published numbers — and an explicit non-match

25M steps, `easy` distribution, 3 seeds (`benchmark/ppg.sh`: `--num-seeds 3 --workers 1`):

| Env (easy) | `ppg_procgen.py` | `ppo_procgen.py` | `openai/phasic-policy-gradient` |
|---|---|---|---|
| Starpilot | 34.82 ± 13.77 | 32.47 ± 11.21 | 42.01 ± 9.59 |
| Bossfight | 10.78 ± 1.90 | 9.63 ± 2.35 | 10.71 ± 2.05 |
| Bigfish | 24.23 ± 10.73 | 16.80 ± 9.49 | 15.94 ± 10.80 |

CleanRL **does not claim to match the paper**, and says why: *"the original paper's results were
condcuted with the `hard` distribution mode"*, so they re-ran the original codebase themselves on
`easy` for the comparison column, concluding *"it's challenging to compare our results against
those in the original PPG paper."* They also flag that PPG's own PPO baseline diverges from
`openai/baselines`' PPO, and that Cobbe 2020 used `procgen==0.9.2` while Cobbe 2021 used
`procgen==0.10.4`, *"which also could cause performance difference."*

**Other documented non-matches**, which are worth knowing because they show a mature project's
honest failure surface: DDPG *"seems to be worse than the reference implementation on Walker2d
and Hopper"*; TD3 *"worse than the reference implementation on Walker2d"* — both blamed on
deprecated MuJoCo-v1 envs **and on CleanRL reporting *training* return while the originals report
deterministic *evaluation* return** ([ddpg.md L254](https://docs.cleanrl.dev/rl-algorithms/ddpg/),
[td3.md L148](https://docs.cleanrl.dev/rl-algorithms/td3/)). SAC undershoots published numbers on
HalfCheetah (9634 vs ~11250), Walker2d (3591 vs ~4800), Hopper (2310 vs ~3250)
([sac.md](https://docs.cleanrl.dev/rl-algorithms/sac/)).

Hardware per benchmark run: **UNVERIFIED** — docs give no per-experiment hardware; the README
only says *"our contributors run experiments on a variety of hardware"*.

> **Bearing on us.** The train-vs-eval-regime distinction is the single most transferable item
> here. It is the same axis as our own open question about which regime a reported number was
> collected in, and CleanRL demonstrates it producing a systematic, *documented*, multi-algorithm
> gap against published values. That is external evidence that the distinction is not pedantic.

---

## 3. Coverage of our other eleven baselines: none

The full file list of `cleanrl/` (34 files, fetched via GitHub API) contains **no DrQ, no DrQ-v2,
no SVEA/SGQN/CURL/RAD/SODA, no IDAAC/DAAC, no IBAC-SNI, no CTRL, no ALDA, and no pixel-based
SAC.** Issue search: `DrQv2` → 0 hits, `IDAAC` → 0 hits, `DrQ` → 1 unrelated hit (#266 "SAC
discrete").

Relevant items only:

- **PPO** — `ppo.py`, `ppo_procgen.py`, `ppo_continuous_action.py`, `ppo_atari*`, JAX/XLA,
  multigpu, LSTM, IsaacGym, TrXL. Validated against `openai/baselines` PPO2 (close but slightly
  below on Procgen: 30.99/8.85/16.46 vs 33.97/9.35/20.06).
- **SAC** — `sac_continuous_action.py` (state vectors only) and `sac_atari.py` (discrete).
  `sac_atari` deliberately uses `--target-entropy-scale=0.89` vs the paper's 0.98.
- **RPO** (`rpo_continuous_action.py`) — CleanRL now *recommends it over*
  `ppo_continuous_action.py`, *"because `rpo_continuous_action.py` empirically performs better …
  in 93% of the environments we tested"* (10 seeds, 8M steps).

**Conclusion: CleanRL is a reference point for PPG and PPO only.** For the visual-generalization
half of our set it offers nothing.

---

## 4. Single-file rationale vs. our "duplication is the null"

CleanRL's stated position (README L40 / [docs/index.md L38-40](https://docs.cleanrl.dev/)):

> CleanRL is **not** a modular library and therefore it is not meant to be imported. **At the cost
> of duplicate code**, we make all implementation details of a DRL algorithm variant easy to
> understand.

The JMLR paper adds: *"Despite having duplicate code among these files, the single-file
implementations have the following benefits… It becomes easier to recognize all aspects of the
code in one place… Because of the faster debug experience, it becomes easier to develop new
features,"* motivated by Engstrom et al.'s "implementation matters"
([JMLR 23(274)](https://www.jmlr.org/papers/v23/21-1342.html), preprint
[arXiv:2111.08819](https://arxiv.org/abs/2111.08819)).

**Where it matches us:** the ordering is identical — duplication is accepted as the price, and
what it buys is that every implementation detail is auditable in one place.

**Where it differs, and this is the part worth keeping:** CleanRL's stated benefits are
*pedagogical and prototyping* — readability, debugging, no subclassing. It **never frames a
shared harness as carrying a burden of proof about whether the numbers are still the author's.**
As far as the survey could verify, our framing is stronger and is not stated anywhere in
CleanRL's docs.

Second difference, and it cuts our way: CleanRL duplicates across *its own rewrites*; we
duplicate by keeping *original repos intact*. CleanRL's own results table is a demonstration of
what rewriting costs — the Starpilot gap, the DDPG/TD3 gaps, the SAC gaps.

---

## 5. Continuous heads: the upstream ships a vestigial one

CleanRL's PPG is Procgen-only — *"64x64 RGB image observations, and discrete actions"* — and the
file imports only `Categorical`. **No CleanRL implementation, doc, or issue discusses PPG with
continuous actions** (issue search: 0 relevant hits). UNVERIFIED that any exists there.

The directly useful find is in the original, not in CleanRL:
[`openai/phasic-policy-gradient/phasic_policy_gradient/distr_builder.py`](https://github.com/openai/phasic-policy-gradient/blob/master/phasic_policy_gradient/distr_builder.py)
**does** contain a Gaussian factory — but it is dead code and fixed-variance:

```python
def _make_normal(x, shape):
    warnings.warn("Using stdev=1")
    return dis.Normal(loc=x.reshape(x.shape[:-1] + shape), scale=1.0)
```

`tensor_distr_builder` dispatches only `Discrete(2)`→Bernoulli and `Discrete`→Categorical, and
otherwise raises `ValueError`. So `_make_normal` is **unreachable**, and had it been reachable it
would give a state-independent, non-learned, **unit** std.

> **Bearing on us, and it is load-bearing for the audit.** This establishes that no prior art for
> a continuous PPG head exists upstream. Our authored head is a design decision, not a port — and
> the audit should say so in exactly those words rather than leaving it implied. It also means
> our σ=1 initialisation coincides with the only Gaussian the upstream authors ever wrote down,
> which is a genuinely nice fact: `probe_heads.py` measures 9.93257 for a unit 7-dim Gaussian,
> and `scale=1.0` is what `_make_normal` would have produced.

### The transferable pitfall list

CleanRL's "9 details for continuous action domains"
([blog](https://iclr-blog-track.github.io/2022/03/25/ppo-implementation-details/), mirrored in
[ppo.md L282-293](https://docs.cleanrl.dev/rl-algorithms/ppo/#ppo_continuous_actionpy)):

1. normal distributions;
2. **state-independent `log_std` initialized to 0** — *this is our choice, and it is the PPO
   convention, not a deviation*;
3. independent action components (sum log-probs);
4. **separate MLPs for policy and value** in continuous domains;
5. **clip the action for the env but store the unclipped action** — using the clipped action's
   log-prob is the classic bug; Chou 2017 / Fujita 2018 note the clipping bias, Haarnoja uses
   tanh instead;
6. obs normalization;
7. obs clipping to [-10,10] (their ablation: *"did not help"*);
8. reward scaling by the std of a rolling discounted sum (*"can significantly affect the
   performance"*);
9. reward clipping to [-10,10] (no clear evidence it helps).

> **Two direct hits on our tree.** Detail 5 is our Finding 6, named by the field with citations —
> and note the precise form: *clip for the env, store the unclipped action*. That is the check to
> run against `ppg`, `idaac`, `ibac_sni`, `ctrl`: not merely "is there a clip" but "which action
> is scored". Detail 4 **conflicts with PPG's shared IMPALA trunk**, which is a real tension for
> any continuous PPG and worth recording as an inherited difference rather than a defect.

[DI-engine](https://di-engine-docs.readthedocs.io/en/latest/12_policies/ppg.html) claims its PPG
*"supports both discrete and continuous action spaces"* with per-dimension mu/sigma heads, but
publishes only Atari results — no continuous PPG benchmark numbers anywhere the survey could
verify.

---

## 6. Evaluation protocol

- **3 seeds** is the standard: `cleanrl_utils.benchmark --num-seeds 3` (default 3,
  `--start-seed 1`); `benchmark/ppg.sh` uses exactly that.
- **Metric definition** ([openrlbenchmark README](https://github.com/openrlbenchmark/openrlbenchmark)):
  *"For each random seed i (we have 3 random seeds for each set of experiments), we calculate the
  average episodic return of the last 100 **training** episodes as aᵢ. We then average the aᵢ's
  over all random seeds … and report its standard deviation."* They name this **"implicit
  evaluation"** (Machado et al., 2017) and argue it *"detects issues with catastrophic
  forgetting"* versus best-model evaluation. **This is why their tables systematically undershoot
  papers that report deterministic eval returns.**
- **rliable is integrated, not default**: `python -m openrlbenchmark.rlops --rliable` produces
  IQM + performance profiles (Agarwal et al., 2021) and *"aggregate human-normalized scores with
  Stratified Bootstrap Confidence Intervals"*, tunable via
  `--rc.{sample_efficiency,performance_profile,interval_estimates}_num_bootstrap_reps` (docs show
  10 for quick runs, 2000–50000 for real ones), `--rc.score_normalization_method atari`. It is a
  *plotting/analysis* layer over W&B, **not a required gate**.
- **RLops regression policy** ([contribution.md](https://docs.cleanrl.dev/contribution/)): any
  performance-impacting PR must re-run the benchmark and compare tags — *"regardless of the
  slight difference in performance-impacting changes, we need to re-run the benchmark to ensure
  there is no regression"*, motivated by *"even bug fixes can sometimes lead to performance
  regressions."*
- Open RL Benchmark ([arXiv:2402.03046](https://arxiv.org/abs/2402.03046), Huang, Gallouédec,
  Felten, Raffin et al., Feb 2024) aggregates *"more than 25,000 runs … for a cumulative duration
  of more than 8 years"* — **and tracks runs of `openai/phasic-policy-gradient` itself** at
  <https://wandb.ai/openrlbenchmark/phasic-policy-gradient> (keys `ceik=env_name`, `cen=arch`,
  `metric=charts/episodic_return`).

> **Bearing on us.** Three things. (a) 3 seeds is the field's floor and RL-ViGen's own paper §4
> specifies 5 with 95% CIs; our current single-seed evaluation is below both, and this is the
> citation for saying so. (b) `bootstrap_ci` in `scripts/metrics.py` resamples *episodes within
> one run* and therefore does not address seed variance — CleanRL's protocol is the reference for
> what would. (c) The `rlops` regression rule is a good model for the greenmark discipline this
> project already has: re-run the benchmark on any performance-impacting change rather than
> reasoning about whether it should matter.

---

## Bottom line

- The five PPG implementation details in §1a are a fidelity checklist for our PPG clone —
  especially the ≈0.638/1.4/0.1 normalized-init scales, which we do **not** currently probe.
- The original's dead `_make_normal(scale=1.0)` confirms no continuous-PPG prior art exists
  upstream; our head is authored, and coincidentally matches the only σ the authors wrote.
- CleanRL corroborates our duplication stance but argues it on readability, not fidelity.
- CleanRL contributes nothing to the ten visual-generalization baselines, and its Procgen numbers
  cannot be compared to the PPG paper at all (easy vs hard).
