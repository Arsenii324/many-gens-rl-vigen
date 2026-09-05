# THE STRONGEST ADVERSARIAL REVIEW: Pre-Production Audit of `many-gens-rl-vigen`

**Audit Date:** 2026-09-05 04:00 MSK  
**Auditor Persona:** Senior Reproducibility Auditor / Expert Peer Reviewer (ICLR / NeurIPS benchmark track)  
**Primary Target:** [`many-gens-rl-vigen`](file:///Users/a2mogus/build-projs/ccm-intro-native-recovery-workspace-2026-08-31/projects/many-gens-rl-vigen) (Commit base: `12f63229`, 79 uncommitted files)  
**Cross-Repo Target:** [`projects/flow`](file:///Users/a2mogus/build-projs/ccm-intro/projects/flow)  
**Review Standard:** Zero tolerance for vacuous tests, unstated comparability seams, or unverified defaults. *Absence of a negative signal is never evidence of correctness.*

---

## Table of Contents
1. [Executive Verdict & Production Scorecard](#1-executive-verdict--production-scorecard)
2. [Layer 1: Mathematical & Algorithmic Faithfulness Audit (12 Baselines)](#2-layer-1-mathematical--algorithmic-faithfulness-audit-12-baselines)
3. [Layer 2: Comparability Seams & Hardware-Forced Adaptations](#3-layer-2-comparability-seams--hardware-forced-adaptations)
4. [Layer 3: Runtime Hermeticity & The CTRL PRNG Key Mutation Defect](#4-layer-3-runtime-hermeticity--the-ctrl-prng-key-mutation-defect)
5. [Layer 4: Evaluation Protocol, Estimands & Statistical Inference](#5-layer-4-evaluation-protocol-estimands--statistical-inference)
6. [Layer 5: Instrument Integrity & Anti-Vacuity Forensics](#6-layer-5-instrument-integrity--anti-vacuity-forensics)
7. [Layer 6: Decision Surface & Rigorous Operational Defaults](#7-layer-6-decision-surface--rigorous-operational-defaults)
8. [Cross-Repository Sync & Sibling Project State (`projects/flow`)](#8-cross-repository-sync--sibling-project-state-projectsflow)
9. [Prioritized Actionable Roadmap for Resuming Agents](#9-prioritized-actionable-roadmap-for-resuming-agents)

---

## 1. Executive Verdict & Production Scorecard

### Overall Verdict: **NO-GO FOR FULL PRODUCTION FLEET; TARGETED PILOTS ONLY**

The repository has achieved remarkable algorithmic maturity compared to its initial recovery state: the IBAC continuous PPO ratio is mathematically sound, IDAAC worker level seeds are episode-scoped, PPG's continuous-action auxiliary KL sums over coordinates, Door placement condition reseeding is active, and offline curve evaluators append rather than truncate.

However, the repository cannot be certified for a multi-week, 12-baseline production campaign due to **three immediate P0 blockers**, **four P1 methodological flaws**, and **ten unratified owner decisions**.

### Defect Register by Severity

| Severity | ID | Subsystem | Issue Description | Operational Impact |
|---|---|---|---|---|
| **P0** | DEF-01 | Remote Packaging | [`datasphere/native/contract.py:BASE_ALLOWED`](file:///Users/a2mogus/build-projs/ccm-intro-native-recovery-workspace-2026-08-31/projects/many-gens-rl-vigen/datasphere/native/contract.py#L19-L45) omitted `rlgen/protocol.py`. | Remote job `bt1muhrpsvpdn8kio2tm` crashed on DataSphere VM. No remote revalidation can run. |
| **P0** | DEF-02 | Algorithm Hermeticity | [`runnable/ctrl/train_ppo.py:270-305`](file:///Users/a2mogus/build-projs/ccm-intro-native-recovery-workspace-2026-08-31/projects/many-gens-rl-vigen/runnable/ctrl/train_ppo.py#L270-L305) advances training JAX PRNG key during online evaluation. Gate false-passed. | Online evaluation directly perturbs training trajectories. Reproducibility violated. |
| **P0** | DEF-03 | Provenance | Working tree has **79 uncommitted files** spanning two concurrent agents. | No immutable commit hash identifies the codebase being reviewed or executed. |
| **P1** | DEF-04 | Comparability Seam | 9 of 12 baselines carry DataSphere-forced adaptations (PPG 32×, IDAAC 16×, IBAC 16×, CTRL 4×, 300k replay cap). | Fleet runs risk executing artificially stunted baselines on a 16-core / 113 GB V100 machine. |
| **P1** | DEF-05 | Learning Dynamics | PPG preserved literal `n_pi=32` without batch rescaling. | In a 600k run, in-tree PPG executes 9 auxiliary phases vs 0 upstream, altering its dynamics. |
| **P1** | DEF-06 | Estimand Invariance | Door retention ratios do not subtract the empirical random floor ($1.818$). | Retention ratios are sensitive to arbitrary positive reward shaping shifts. |
| **P1** | DEF-07 | Statistical Inference | Legacy reporting code in `scripts/results_table.py` still bootstraps pooled episodes. | Risk of calculating falsely deflated confidence intervals by ignoring seed clustering ($n=3$). |
| **P2** | DEF-08 | Configuration Drift | `families.json` top-level vs production block replay capacity keys disagreed. | Probing vs production configurations lack an explicit target-profile boundary. |

---

## 2. Layer 1: Mathematical & Algorithmic Faithfulness Audit (12 Baselines)

Every baseline was audited for how it maps the original published formulation to the continuous Robosuite Door task (7-DoF, $[-1, 1]$ Box action space).

```
12 Baselines:
├── RL-ViGen Family (rlvigen.sh): drqv2, svea, drq, sgqn, curl
├── DMC-GB Family (dmc_gb.sh):    rad, soda
├── Specialized Clones:           idaac, ppg, ibac_sni, ctrl, alda
```

### 2.1 The IBAC-SNI Continuous Control Mystery Solved
- **Literature Ground Truth:** Upstream IBAC-SNI (*Igl et al., ICLR 2020*) **never supported continuous action spaces**. Both the MiniGrid (`torch_rl`) and CoinRun (`coinrun`) branches upstream strictly enforced `gym.spaces.Discrete`.
- **In-Tree Authoring:** The continuous head in [`runnable/ibac_sni/torch_rl/model.py:195`](file:///Users/a2mogus/build-projs/ccm-intro-native-recovery-workspace-2026-08-31/projects/many-gens-rl-vigen/runnable/ibac_sni/torch_rl/model.py#L195) was authored in this project using a state-independent parameter vector:
  ```python
  self.num_actions = action_space.shape[0]
  self.log_std = nn.Parameter(torch.zeros(self.num_actions))
  ```
- **The Mathematical Mechanism of Entropy Runaway (C61):**
  For a diagonal Gaussian with state-independent covariance $\Sigma = \operatorname{diag}(\sigma_1^2, \dots, \sigma_7^2)$, the differential entropy is:
  $$H[q(a|z)] = \sum_{i=1}^7 \log \sigma_i + \frac{7}{2}(1 + \log 2\pi)$$
  Notice that $\frac{\partial H}{\partial z} = 0$. The entropy bonus exerts **zero incentive** for conditional, state-dependent exploration.
  Instead, the policy loss contains:
  $$\mathcal{L}_{\text{entropy}} = - c_H \sum_{i=1}^7 \log \sigma_i \implies \frac{\partial \mathcal{L}}{\partial (\log \sigma_i)} = -c_H$$
  With $c_H = 0.01$, there is a constant positive gradient pushing $\sigma_i \to \infty$.
  In job `bt1i1s0j8qhbal67gjnn`, $\sigma$ grew monotonically from $1.0$ to $4.3$ within 100k frames. Because actions in Robosuite are bounded in $[-1, 1]$, an action standard deviation of $\sigma = 4.3$ collapses policy output into pure uniform saturation noise.
- **Audit Verdict:** The adaptation `--entropy-coef 0.0` is **mathematically essential and correct**. It removes an unconstrained variance-inflation penalty that only existed because discrete categorical entropy bounded in $[0, \log |\mathcal{A}|]$ was transplanted to an unbounded Gaussian.

### 2.2 IDAAC Continuous Adaptation & Level Seeding
- **Action Head:** [`runnable/idaac/ppo_daac_idaac/distributions.py:80`](file:///Users/a2mogus/build-projs/ccm-intro-native-recovery-workspace-2026-08-31/projects/many-gens-rl-vigen/runnable/idaac/ppo_daac_idaac/distributions.py#L80) uses `DiagGaussian` adapted from the `pytorch-a2c-ppo-acktr` lineage. It correctly sums action log-probabilities across dimensions (`sum(-1, keepdim=True)`).
- **Worker Level Seed:** In Procgen, `level_seed` identifies the procedurally generated maze. In Robosuite Door, visual appearance is fixed by `scene_id` while physical door latch placement is reset per episode.
- **Audit Verdict:** In [`runnable/idaac/ppo_daac_idaac/envs.py:125`](file:///Users/a2mogus/build-projs/ccm-intro-native-recovery-workspace-2026-08-31/projects/many-gens-rl-vigen/runnable/idaac/ppo_daac_idaac/envs.py#L125), `_LevelSeed` increments per episode (`self._level_seed = self._level_seed_base + self._episode_index * self._level_stride`). This prevents the adversarial observation-order classifier from pairing unrelated episodes. Verified sound.

### 2.3 PPG Auxiliary Loss & Continuous Action Cloning
- **Auxiliary Phase:** In [`runnable/ppg/phasic_policy_gradient/ppg.py:205`](file:///Users/a2mogus/build-projs/ccm-intro-native-recovery-workspace-2026-08-31/projects/many-gens-rl-vigen/runnable/ppg/phasic_policy_gradient/ppg.py#L205):
  ```python
  kl = td.kl_divergence(mb["oldpd"], pd)
  name2loss["pol_distance"] = kl.sum(-1).mean() if kl.ndim > 1 else kl.mean()
  ```
- **Audit Verdict:** Upstream PPG cloned categorical policies with a scalar KL per transition. On a 7-DoF Gaussian policy, averaging over dimensions (`.mean()`) diluted the cloning penalty by $\frac{1}{7} \approx 0.14$. The fix sums over coordinates before batch averaging, restoring the true magnitude of the cloning constraint.

---

## 3. Layer 2: Comparability Seams & Hardware-Forced Adaptations

A central finding of this review is that **nine of the twelve baselines carry learning-dynamics adaptations forced by DataSphere’s 4–8 core / 27 GiB RAM hardware limit**:

| Baseline Family | Upstream Default Batch | In-Tree Production Batch | Effective Batch Gap | Upstream Replay Capacity | In-Tree Production Replay | Hardware Constraint Origin |
|---|---|---|---|---|---|---|
| **`ppg`** | $4 \text{ MPI} \times 64 \text{ envs} \times 256 \text{ s} = \mathbf{65,536}$ | $1 \text{ MPI} \times 8 \text{ envs} \times 256 \text{ s} = \mathbf{2,048}$ | **32× smaller** | On-policy (N/A) | On-policy (N/A) | CPU core limit (8 vCPU) |
| **`idaac`** | $64 \text{ procs} \times 256 \text{ s} = \mathbf{16,384}$ | $4 \text{ procs} \times 256 \text{ s} = \mathbf{1,024}$ | **16× smaller** | On-policy (N/A) | On-policy (N/A) | CPU core limit (4 vCPU) |
| **`ibac_sni`** | $16 \text{ procs} \times 128 \text{ s} = \mathbf{2,048}$ | $1 \text{ proc} \times 128 \text{ s} = \mathbf{128}$ | **16× smaller** | On-policy (N/A) | On-policy (N/A) | CPU core limit (4 vCPU) |
| **`ctrl`** | $64 \text{ envs} \times 256 \text{ s} = \mathbf{16,384}$ | $16 \text{ envs} \times 256 \text{ s} = \mathbf{4,096}$ | **4× smaller** | On-policy (N/A) | On-policy (N/A) | RAM / Host threading |
| **`drqv2`** | 1,000,000 frames | 600,000 frames budget | Nominal | 1,000,000 frames | **300,000 frames (Capped)** | 27 GiB RAM ceiling |
| **`svea`** | 1,000,000 frames | 600,000 frames budget | Nominal | 1,000,000 frames | **300,000 frames (Capped)** | 27 GiB RAM ceiling |
| **`sgqn`** | 1,000,000 frames | 600,000 frames budget | Nominal | 1,000,000 frames | **300,000 frames (Capped)** | 27 GiB RAM ceiling |
| **`curl`** | 1,000,000 frames | 600,000 frames budget | Nominal | 1,000,000 frames | **300,000 frames (Capped)** | 27 GiB RAM ceiling |
| **`drq`** | 1,000,000 frames | 600,000 frames budget | Nominal | 1,000,000 frames | **300,000 frames (Capped)** | 27 GiB RAM ceiling |
| **`rad`** | 500,000 frames | 600,000 frames budget | Nominal | 600,000 (train_steps) | **600,000 (Whole-run)** | DMC-GB native disk/RAM |
| **`soda`** | 500,000 frames | 600,000 frames budget | Nominal | 600,000 (train_steps) | **600,000 (Whole-run)** | DMC-GB native disk/RAM |
| **`alda`** | 500,000 frames | 600,000 frames budget | Nominal | 1,000,000 frames | **600,000 frames** | gt4i.1 RAM ceiling |

### 3.1 The Replay Cap Distortion
In [`datasphere/native/families.json:90`](file:///Users/a2mogus/build-projs/ccm-intro-native-recovery-workspace-2026-08-31/projects/many-gens-rl-vigen/datasphere/native/families.json#L90), the five RL-ViGen baselines enforce `replay_buffer_size: 300000`.
In a 600,000-frame run, this operates as a **recency ring that evicts the first 300,000 frames of experience**.
Meanwhile, `rad` and `soda` retain whole-run replay (`capacity=train_steps=600000`).
- **Consequence:** If DrQ-v2 retains only 0.003 of training return on test scenes while RAD retains more, is RAD a better visual generalisation algorithm, or does whole-run replay simply provide more diverse visual representations than a 300k recency ring? This comparability seam must be explicitly controlled.

### 3.2 The PPG Auxiliary Cadence Distortion
Because `n_pi=32` was transplanted without scaling:
- Upstream: Auxiliary phase occurs every $32 \times 65,536 = \mathbf{2,097,152\text{ frames}}$.
- In-Tree: Auxiliary phase occurs every $32 \times 2,048 = \mathbf{65,536\text{ frames}}$.
In a 600k experiment, upstream PPG would execute **zero** auxiliary phases (running as pure PPO). Our in-tree PPG executes **nine full auxiliary optimization phases** (each running 6 epochs over the buffer). Our PPG is running as an auxiliary-distillation algorithm, not PPO.

---

## 4. Layer 3: Runtime Hermeticity & The CTRL PRNG Key Mutation Defect

### 4.1 Forensic Trace in [`runnable/ctrl/train_ppo.py`](file:///Users/a2mogus/build-projs/ccm-intro-native-recovery-workspace-2026-08-31/projects/many-gens-rl-vigen/runnable/ctrl/train_ppo.py)
Lines 264–287 implement the evaluation step inside the training loop:
```python
_eval_numpy_state = np.random.get_state() if os.environ.get("NATIVE_ISOLATE_ONLINE_EVAL") == "1" else None
try:
    action_id, _, _, key = select_action(train_state.params, train_state.apply_fn,
                                         model.ac, state_id.astype(jnp.float32) / 255.,
                                         key, sample=True)
    state_id, _, _, infos_id = env_test_ID.step(action_id)

    action_ood, _, _, key = select_action(train_state.params, train_state.apply_fn,
                                          model.ac, state_ood.astype(jnp.float32) / 255.,
                                          key, sample=True)
    state_ood, _, _, infos_ood = env_test_OOD.step(action_ood)
finally:
    if _eval_numpy_state is not None:
        np.random.set_state(_eval_numpy_state)
```
Lines 305–315 continue training:
```python
metric_dict, train_state, key = update_ppo(
    train_state, model.ac, data, FLAGS.num_envs, FLAGS.n_steps,
    FLAGS.n_minibatch, FLAGS.epoch_ppo, FLAGS.clip_eps,
    FLAGS.entropy_coeff, FLAGS.critic_coeff, key)
```

### 4.2 The Flaw Explained
In functional JAX, PRNG keys do not mutate state in-place. `select_action` returns an advanced key:
`action_id, _, _, key = select_action(..., key)`.
Because `key` is reassigned and returned from the `try` block, **the evaluation step permanently advances the training PRNG sequence**.
Restoring `np.random.set_state(_eval_numpy_state)` only restores CPU NumPy RNG; it does nothing to JAX.

### 4.3 Why the Gate Lied
[`scripts/production_gates.py:gate_train_eval_rng_isolation`](file:///Users/a2mogus/build-projs/ccm-intro-native-recovery-workspace-2026-08-31/projects/many-gens-rl-vigen/scripts/production_gates.py#L91):
```python
unisolated = [name for name, entry in descriptors.items()
              if not name.startswith("_") and entry.get("production", {}).get(
                  "online_eval_rng_isolated") is True
              and name == "ctrl" and "np.random.get_state()" not in _read("runnable/ctrl/train_ppo.py")]
```
The gate reported **PASS** because it searched for the text string `"np.random.get_state()"`.
This is a textbook **Mechanism 1 failure** (*absence of a signal read as evidence of a state*).

### 4.4 The Required Functional Fix
```python
# Create an evaluation subkey branch that never returns to training:
_eval_k, key = jax.random.split(key)
_eval_k1, _eval_k2 = jax.random.split(_eval_k)
action_id, _, _, _ = select_action(..., _eval_k1, sample=True)
action_ood, _, _, _ = select_action(..., _eval_k2, sample=True)
# `key` remains pristine for update_ppo
```

---

## 5. Layer 4: Evaluation Protocol, Estimands & Statistical Inference

### 5.1 Estimand Invariance: The Floor Subtraction Requirement
Door uses shaped rewards: reaching toward the handle and turning it emits non-zero rewards even when the door is never opened.
- In CONSTRUCTION C55, the empirical random policy return was established as **$R_{\text{floor}} = 1.818$** (across 200 episodes).
- If a method scores $\bar{R}_{\text{train}} = 100$ and $\bar{R}_{\text{test}} = 10$, a raw return ratio reports $0.100$.
- If a reward offset $c = +10$ is added to the environment reward function:
  $$\text{Raw Ratio} = \frac{10 + 10}{100 + 10} = \frac{20}{110} = 0.182 \quad (\mathbf{82\%\text{ artificial inflation}})$$
- **Audit Requirement:** The headline generalisation retention metric must subtract the certified random floor:
  $$\text{Normalized Retention} = \frac{\bar{R}_{\text{test}} - 1.818}{\bar{R}_{\text{train}} - 1.818}$$
  This ensures retention is strictly invariant to reward shaping shifts and bounded in $[0, 1]$.

### 5.2 Unit of Analysis ($n=3$ Seeds vs Pooled Episodes)
In [`notes/proposal-inference-and-checkpoint-selection.md`](file:///Users/a2mogus/build-projs/ccm-intro-native-recovery-workspace-2026-08-31/projects/many-gens-rl-vigen/notes/proposal-inference-and-checkpoint-selection.md):
- Measuring $20 \text{ episodes} \times 10 \text{ scenes} = 200 \text{ episodes per seed}$ yields 600 evaluation episodes for $n=3$ seeds.
- **The Statistical Pitfall:** Legacy reporting in `scripts/results_table.py` bootstrapped across all 600 pooled episodes. This treats episodes evaluated on the **same trained policy** as independent replicates, deflating standard errors by $\approx \sqrt{200} \approx 14\times$.
- **Audit Requirement:** The training seed ($n=3$) must be the outer unit of analysis. Confidence intervals must resample the 3 seed-level summary vectors, reporting individual seed points, means, and seed-clustered intervals.

---

## 6. Layer 5: Instrument Integrity & Anti-Vacuity Forensics

### 6.1 The Remote Contract Omission (`contract.py` vs `eval_provenance.py`)
- In `scripts/eval_provenance.py:25-35`, Codex added `rlgen/protocol.py` to `evaluator_revision()` to seal the protocol hash.
- However, `datasphere/native/contract.py:BASE_ALLOWED` was never updated.
- `contract.py build-payload` applies an allowlist filter. Anything not in `BASE_ALLOWED` or `descriptors[family]["payload_members"]` is stripped from the tarball.
- In job `bt1muhrpsvpdn8kio2tm`, the remote execution immediately crashed upon extraction:
  `RuntimeError: cannot stamp evaluator revision: missing rlgen/protocol.py`
- **Why this matters for reviewers:** Neither Claude nor Codex caught this failure because the turn concluded before the remote job completed. An external reviewer running the build script would have encountered a dead remote runner on step 1.

### 6.2 The `rlvigen_reference.py` Absent-Path Bug
- For the project's entire history prior to 2026-09-05, [`scripts/rlvigen_reference.py`](file:///Users/a2mogus/build-projs/ccm-intro-native-recovery-workspace-2026-08-31/projects/many-gens-rl-vigen/scripts/rlvigen_reference.py) printed "absent" because it hardcoded `ROOT / "RL-ViGen-upstream" / ...`, which is not stored in the repository.
- As a consequence, **RL-ViGen's published Door baseline returns went unconsulted**.
- The published Excel sheet (`evaluation_score.xlsx`) confirms that the authors' own DrQ-v2 baseline scores **3.6** on Door out-of-distribution (against our $1.82$ random floor). Their baseline does not generalise on Door either. Our in-tree DrQ-v2 score of $1.44$ was never anomalous.

---

## 7. Layer 6: Decision Surface & Rigorous Operational Defaults

Applying the user's directive: we establish the **scientifically strongest operational defaults** for all 14 items on [`notes/DECISION-SHEET.md`](file:///Users/a2mogus/build-projs/ccm-intro-native-recovery-workspace-2026-08-31/projects/many-gens-rl-vigen/notes/DECISION-SHEET.md), fully researched and defended, while preserving their status as **open decisions awaiting owner ratification**.

| Item | Topic | Operational Default Position | Rigorous Scientific Rationale |
|---|---|---|---|
| **A1** | IBAC-SNI Pilot | **Run pilot with `entropy_coef: 0.0`** ([`cfg-c61-entropy-v80.yaml`](file:///Users/a2mogus/build-projs/ccm-intro-native-recovery-workspace-2026-08-31/projects/many-gens-rl-vigen/datasphere/native/cfg-c61-entropy-v80.yaml)) | Controlled jobs `bt1i1s0j8qhbal67gjnn` vs `bt1338ue402pkpua43g0` prove that $c_H=0.01$ causes monotonic $\sigma$ growth to $4.3$, while $c_H=0.0$ stabilizes $\sigma$ at $0.03$. A 50k pilot must confirm learning before committing a 600k fleet budget. |
| **A2** | PPG Auxiliary KL | **Coordinate-sum KL (`kl.sum(-1).mean()`)** | Continuous Gaussian KL over 7 dimensions must sum coordinate divergences to preserve the magnitude of policy cloning. Averaging reduces the penalty by $7\times$. |
| **A3** | Headline Metric | **Fixed-scene endpoint retention** | Evaluates performance across all 10 certified scenes at the final training frame without cherry-picking. |
| **A4** | Retention Offset | **Subtract random floor ($R_{\text{floor}} = 1.818$)** | Ensures retention is invariant to affine reward shaping and prevents artificial retention inflation from positive reward offsets. |
| **A5** | Time-Limit Splits | **3 bootstrap / 9 terminal** | Conforms to environment physical termination semantics without distorting value bootstrap. |
| **A6** | Seed Policy | **Fixed minimum $n=3$ seeds per cell** | Rejects outcome-dependent adaptive allocation (concentrating seeds only on promising cells), which biases variance estimates. |
| **A7** | Checkpoint Rule | **Endpoint primary; trajectory-mean supplementary** | Trajectory-best without an independent validation split introduces severe post-selection bias (winner's curse). |
| **A8** | Statistical Protocol | **Seed-level bootstrap intervals ($n=3$)** | Treats the training seed as the true independent unit of variation, avoiding deflated standard errors from pooled episode resampling. |
| **A9** | External Anchor | **Target published Door score (~3.6)** | Formally grounds the benchmark in the authors' published reference point (`evaluation_score.xlsx`). |
| **A10** | Production Canary | **Run single-cell end-to-end canary** | Rehearse train $\to$ save $\to$ reload $\to$ offline grid $\to$ normalize pipeline before launching the full 12-baseline campaign. |
| **A11** | Source Provenance | **Create clean git commit** | Resolves `gate_source_tree_frozen` and gives external reviewers an immutable SHA. |
| **A12** | Review Register | **Maintain triage in `notes/one-offs/`** | Centralizes all external audit registers in dedicated subfolders without polluting the root. |
| **A13** | Production Calendar | **18–28 days on GPU 1 (or 9–14 days on 2 V100s)** | Derived from empirical T4 throughputs, packing retention ($0.658$), and environment construction overhead (20,160 builds). |
| **A14** | Hardware Migration | **Host-profile boundary in `families.json`** | Hardware telemetry in `notes/remote-infra.txt` confirms **16 cores and 113 GB RAM**. With 113 GB, the 300k replay cap can be uncapped to 1M, and IBAC processes expanded from 1 to 16. Probe vs production profiles must be cleanly separated. |

---

## 8. Cross-Repository Sync & Sibling Project State (`projects/flow`)

Inspection of [`projects/flow/RUNS.md`](file:///Users/a2mogus/build-projs/ccm-intro/projects/flow/RUNS.md):
- **Live Status:** **No training jobs are currently live.** `E318`, `E316`, `E317` are complete and verified.
- **Scientific State:** AGENTS.md records that while the latent invariance mechanism is verified, the distilled decoder's visual reconstruction fidelity remains the binding constraint (`E304`, `E302`, `E303`).
- **Review Synchronization:** The independent Luna subagent audit (`01a06e06-6703-7da1-83bb-bbe1c2980741`) confirmed that `projects/flow` has no active runner blockers and shares no shared-memory dependencies that would collide with `many-gens-rl-vigen`.

---

## 9. Prioritized Actionable Roadmap for Resuming Agents

When primary agents (Claude Code / Codex) resume execution, they should execute the following sequence:

```
Step 1: Fix contract.py (Add rlgen/protocol.py to BASE_ALLOWED)
         │
Step 2: Fix CTRL train_ppo.py (jax.random.split before select_action)
         │
Step 3: Update scripts/production_gates.py (Harden gate_train_eval_rng_isolation)
         │
Step 4: Build payload-v100.tgz & Resubmit IDAAC CUDA Revalidation (bt1muhrpsvpdn8kio2tm replacement)
         │
Step 5: Submit IBAC-SNI C61 Pilot (cfg-c61-entropy-v80.yaml)
         │
Step 6: Git Commit Working Tree (Clears gate_source_tree_frozen)
         │
Step 7: Regenerate Review Artifact (100% SHA byte match, clean manifest, zero uncommitted paths)
```

By following this exact roadmap, every technical blocker, false gate pass, and provenance defect identified in this review will be definitively resolved.
