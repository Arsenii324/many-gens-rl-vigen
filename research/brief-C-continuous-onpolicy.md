# Brief C — porting discrete on-policy generalization methods to a 7-D Gaussian policy

> ## ⚠ STATUS: ANSWERED — see `ext/DR_3_*.md` before re-commissioning
>
> §1 is settled: a continuous PPG **exists** (XuanCe `Gaussian_PPG`, itself unvalidated on
> continuous control), and IDAAC's Appendix E publishes continuous PPG hyperparameters. No
> continuous IBAC-SNI or CTRL was found. §3's rollout question is answered and **applied** —
> IDAAC's own continuous config is *"2048 steps, 1 process"*, so `num_envs > 1` is unnecessary and
> `num_steps` is now 2048.
>
> Still open, and the reason to keep this brief: **§4 — are these four arms scientifically
> reportable?** IDAAC's own §6 names *"episode length variations"* as a condition for expected
> gains and our horizon is fixed at 500, so its named mechanism has no reason to help here.


**Upload with**: `SHARED-CONTEXT.md`, `PREMISES.md`, `FAITHFULNESS.md`.

**Suggested approach**: the first question (§1) is a search problem with a binary answer and should
be scoped with ordinary agentic search before any deep pass — **if a continuous-action PPG,
IBAC-SNI or CTRL already exists, most of this brief is moot and we should read that code instead of
commissioning theory.** Our own search did not find one, but we did not prove absence. Establish
that first, then go deep on whichever of §2–§4 survives.

---

## Why this brief exists

Four of our twelve baselines are Procgen methods with **discrete** action spaces, and we run them
on a **7-D continuous** manipulation task. The released implementations are discrete-only, and not
softly so:

- **PPG**: `distr_builder.py` contains a dead `_make_normal` stub with a hardcoded `scale=1.0`
  that is never dispatched to; any non-`Discrete` action space raises `ValueError`. A user with a
  `Box` action space opened Issue #3 in 2021 and was never answered.
- **IBAC-SNI**: hard-raises `ValueError` on any non-`Discrete` action space.
- **IDAAC**: released code is `Categorical`-only. Its paper **does** report continuous DMControl
  results in Appendix E — but that code was never open-sourced, and the first author has publicly
  stated DAAC "was quite difficult to tune" there and recommends procedural, variable-length
  environments instead.
- **CTRL**: official implementation is JAX; PPO-based; we could not confirm a continuous variant.

**So our continuous action head for `ppg`, `ibac_sni` and `ctrl` is original engineering with no
reference implementation to check against.** The encoder, the PPO core and each method's auxiliary
machinery can be verified against primary sources; the action distribution cannot.

## The decision this feeds

**Whether to keep these four in the benchmark at all, and if so what to claim about them.** The
options are: keep them and label them explicitly as unvalidated continuous adaptations; validate
them against Procgen first (where published numbers exist) and then port; or drop them and report a
smaller, better-grounded matrix. We are currently doing the first by default rather than by
decision.

---

## 1. Does a continuous-action version already exist? (scope this first)

For each of **PPG, IDAAC/DAAC, IBAC-SNI, CTRL**:

- Any public implementation with a Gaussian/tanh-Gaussian/Beta policy head — official, third-party,
  a fork, a thesis, a workshop paper, a CleanRL-style single-file version, anything.
- Any *paper* applying the method to continuous control, even without released code, and what it
  reports about the adaptation.
- For IDAAC specifically: has anyone reconstructed the **Appendix E** DMControl experiments? Their
  hyperparameters are published (γ 0.99, rollout 2048, 3 stacked frames, lr 3e-4, 10 PPO epochs,
  E_V=9, N_π=32, α_a=0.1, α_i=0.1) but the paper never states the **action distribution family**.
  That single missing fact is the thing we most want.

**Please report which searches you ran.** "Not found after searching X, Y, Z" is a usable result;
"does not exist" without that is not.

## 2. The adaptation itself, method by method

Where no reference exists, we want the *principled* answer plus whatever precedent exists in
adjacent work.

### PPG
The auxiliary phase distils the value network's predictions into the policy network's auxiliary
value head via `L_aux` (MSE) **plus `β_clone · KL(π_old, π_θ)`**.

- For a Gaussian policy, what is the right KL? Analytic KL between two diagonal Gaussians is
  available in closed form — is that what a continuous PPG should use, and does `β_clone = 1`
  remain sensible when the KL is no longer bounded the way a categorical KL is?
- PPG's released code has **no gradient clipping at all**. For continuous control, where the
  surrogate can blow up, is that safe to carry over?

### IBAC-SNI
The paper's Eq. 7 is
`G^SNI = λ·G_AC(π̄^r, π̄, V̄) + (1−λ)·G_AC(π̄^r, π, V̄)`,
where **the critic is always the deterministic V̄ in both terms** — SNI mixes only the *policy
gradient's* stochasticity, never the value loss.

- Our benchmark has **two** independent Gaussian noise sources once ported: the VIB latent
  bottleneck and the action distribution itself. The PPO importance ratio then has two noise
  sources where the original had one. **How should SNI's λ-mixing be re-derived?** Which
  distribution should the "deterministic" pass fix — the latent, the action, or both?
- The released code only implements λ ∈ {0, 0.5, 1}, and λ=1 goes through an entirely different
  code path (an L2-on-activations penalty the paper notes is mathematically distinct from the
  VIB-KL used at λ<1). Does that constrain what a continuous port should offer?
- β is per-benchmark (1e-3 toy, 1e-6 Multiroom, 1e-4 CoinRun). Is there a principled way to set it
  for a new domain, or is it purely empirical?

### CTRL
Objective is Sinkhorn-Knopp online clustering plus a MYOW-style cross-cluster predictive loss,
applied to the **encoder only**, with the policy head updated by the separate PPO loss.

- The paper publishes **no coefficient** weighting the SSL loss against the PPO loss — they appear
  to be separate update targets. We invented `ctrl_coef = 0.1`. **Is a weighted sum even the right
  structure, or should the encoder be updated in a separate phase?**
- The paper uses **200 clusters** and samples **T = 2** timesteps per trajectory. We use 8 clusters
  and a `ctrl_window` of 8, which is not even the same quantity. What do these parameters do to the
  objective, and does 200 make sense with our vastly smaller rollout?
- Does the clustering objective degrade gracefully at small batch sizes? Sinkhorn-Knopp normalises
  over a batch, and ours is tiny (see §3).

## 3. The rollout-size problem

This may dominate everything above. Published rollouts per update:

| method | envs × steps | samples/update |
|---|---|---|
| PPG | 256 × 256 | **65 536** |
| IDAAC (Procgen) | 64 × 256 | 16 384 |
| IDAAC (Appendix E, continuous) | — | 2 048 |
| CTRL | 32 × 256 | 8 192 |
| **ours** | **1 × 256** | **256** |

With IDAAC's default `num_mini_batch = 32`, our minibatches are **8 samples**.

- At what rollout size do these methods stop working? Is there published evidence?
- Which matters more for them — total samples per update, or number of parallel environments (i.e.
  decorrelation of the batch)? This decides whether we fix it by raising `num_steps` (cheap) or by
  implementing `num_envs > 1` via subprocesses (correct but costly, given robosuite cannot be
  constructed concurrently in one interpreter).
- **Is IDAAC's instance-invariance loss even well-defined at our scale?** It relies on paired
  same-level embeddings and a discriminator predicting trajectory order. With one environment and
  a 256-step rollout, how many usable pairs exist per update?

## 4. Validating without published continuous numbers

- **Is validating these three against Procgen first the right move?** It is the only place
  published numbers exist. Cost: a second environment stack, a discrete action path, and a
  separate encoder configuration — real work for a benchmark that is otherwise robosuite-only.
- If not Procgen, what is the cheapest credible evidence that a continuous PPG/IBAC-SNI/CTRL is
  correctly implemented? Are there diagnostic signatures — the auxiliary phase measurably reducing
  value error, SNI's λ interpolating monotonically between two known behaviours, CTRL's clusters
  not collapsing — that would constitute evidence short of matching a published score?
- Are there known failure modes when these methods are applied off-distribution that we should
  instrument for rather than discover?

---

## Output we want

1. **A definitive answer to §1**, with the searches you ran.
2. **Per method, a recommended continuous adaptation** — the action distribution, how the
   method-specific loss changes, and what to set the method-specific coefficients to.
3. **A verdict on the rollout problem**: is 256 samples/update salvageable by raising `num_steps`,
   or does this need `num_envs > 1`?
4. **A recommendation on Procgen validation** — worth it or not, given the cost.
5. **An honest assessment**: are these four baselines scientifically reportable on this benchmark,
   or should they be labelled as unvalidated adaptations, or dropped?

The last one is the one we most need an outside view on. We have an incentive to keep twelve
baselines because the brief asks for twelve, and that is exactly the kind of pressure that produces
a table with four rows that do not mean anything.
