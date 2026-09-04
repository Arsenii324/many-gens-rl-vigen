# PyTorch-Ecosystem and Newer Training Libraries Survey

**Target Report Path:** `/Users/a2mogus/.claude/jobs/d037da9e/tmp/libsweep-pytorch-ecosystem.md`  
**Date of Survey:** August 17, 2026  

---

## Executive Summary

This report surveys the PyTorch ecosystem and newer training libraries—specifically **torchtune**, **torchforge**, **torchbeast**, **TorchRL / PyTorch RL recipes**, **CleanRL**, and **Stable-Baselines3**—to evaluate their architectural design, policy-gradient implementations, code-sharing philosophy, concrete metric logging vocabulary, and reusability for a `robosuite` pixel-based visual reinforcement learning generalization benchmark.

Every claim in this report cites an authoritative locator (repository file path, documentation URL, or GitHub issue). Where information could not be verified directly, it is explicitly marked as `UNVERIFIED` alongside the exact verification attempts made.

---

## 1. torchtune (`pytorch/torchtune`)

### 1.1 Purpose & Blunt Scope Assessment
* **Primary Scope:** `torchtune` is a PyTorch-native library designed for easily authoring, post-training, fine-tuning, and experimenting with Large Language Models (LLMs) and Vision-Language Models (VLMs).
* **Blunt Assessment:** `torchtune` is **NOT** a visual reinforcement learning library for robotic control. It is exclusively an LLM/VLM post-training library (SFT, KD, DPO, PPO, GRPO, QAT). It does not provide continuous action heads, environmental step loops, or robotic state wrappers.
* **Maintenance Status:** Development wound down in 2025.
* **Locators:**
  * Repository README: [`README.md`](https://raw.githubusercontent.com/pytorch/torchtune/main/README.md)
  * Overview Doc: [`docs/source/overview.rst`](https://raw.githubusercontent.com/pytorch/torchtune/main/docs/source/overview.rst)
  * Maintenance Issue: [Issue #2883: "The future of torchtune"](https://github.com/meta-pytorch/torchtune/issues/2883)

### 1.2 Policy-Gradient & Preference Implementations
* **PPO:** Implemented as `PPOLoss` in [`torchtune/rlhf/loss/ppo.py`](https://raw.githubusercontent.com/pytorch/torchtune/main/torchtune/rlhf/loss/ppo.py). Single-device recipe script: [`recipes/ppo_full_finetune_single_device.py`](https://raw.githubusercontent.com/pytorch/torchtune/main/recipes/ppo_full_finetune_single_device.py).
* **GRPO:** Implemented as `GRPOLoss` and `GRPOCompletionLoss` in [`torchtune/dev/grpo/loss.py`](https://raw.githubusercontent.com/pytorch/torchtune/main/torchtune/dev/grpo/loss.py). Recipes: [`recipes/dev/grpo_full_finetune_distributed.py`](https://raw.githubusercontent.com/pytorch/torchtune/main/recipes/dev/grpo_full_finetune_distributed.py) and [`recipes/dev/async_grpo_full_finetune_distributed.py`](https://raw.githubusercontent.com/pytorch/torchtune/main/recipes/dev/async_grpo_full_finetune_distributed.py).
* **DPO:** Implemented as `DPOLoss` in [`torchtune/rlhf/loss/dpo.py`](https://raw.githubusercontent.com/pytorch/torchtune/main/torchtune/rlhf/loss/dpo.py). Recipes: [`recipes/full_dpo_distributed.py`](https://raw.githubusercontent.com/pytorch/torchtune/main/recipes/full_dpo_distributed.py), [`recipes/lora_dpo_single_device.py`](https://raw.githubusercontent.com/pytorch/torchtune/main/recipes/lora_dpo_single_device.py).
* **How PPO Differs from Standard Control PPO:**
  * **Advantage Estimator:** Uses token-level GAE computed via `estimate_advantages` in [`torchtune/rlhf/sequence_processing.py`](https://raw.githubusercontent.com/pytorch/torchtune/main/torchtune/rlhf/sequence_processing.py). Advantages are computed from sequence scalar rewards produced by a reward model (RM) across generated text tokens.
  * **Value Head:** Token-level scalar value estimator (`phi_values` / `phi_old_values`) predicting scalar value for each generated token in a text sequence.
  * **KL Penalty:** Per-token KL divergence ({KL}(\pi_{policy} \parallel \pi_{ref})$) is subtracted directly from reward scores ({total} = R_{rm} - \beta \cdot KL$) prior to calculating returns/GAE, or logged separately.
  * **Reference Model:** Explicit reference policy model (`ref_policy` or `ref_logprobs`) loaded in parallel with the trainable policy model.

### 1.3 Position on Code Sharing vs. Duplication
`torchtune` explicitly prioritizes **self-contained single-file recipes** over heavy trainer abstractions, favoring intentional code duplication over complex or wrong inheritance hierarchies.
* **Locator:** [`docs/source/deep_dives/recipe_deepdive.rst`](https://raw.githubusercontent.com/pytorch/torchtune/main/docs/source/deep_dives/recipe_deepdive.rst)
* **Direct Quotes:**
  > *"Recipes in torchtune are designed to be: ... Easy to Understand. Each recipe provides a limited set of meaningful features, instead of every possible feature hidden behind 100s of flags. Code duplication is preferred over unnecessary abstractions."*
  > *"Easy to Extend. No dependency on training frameworks and no implementation inheritance. Users don't need to go through layers-upon-layers of abstractions to figure out how to extend core functionality."*

### 1.4 Concrete Logged Metrics
* **PPO Recipe (`recipes/ppo_full_finetune_single_device.py`):**
  * `scores`
  * `num_stop_tokens`
  * `rlhf_reward`
  * `kl`
  * `kl_reward`
  * `lr`
  * `loss`
  * `policy_loss`
  * `value_loss`
  * `clipfrac`
  * `ratios`
  * `approx_policy_kl`
  * `response_lengths`
  * `tokens_per_second_per_gpu_trajectory`
  * `tokens_per_second_per_gpu_ppo`
  * (Optional PyTorch memory metrics via `training.get_memory_stats`: `peak_memory_active`, `peak_memory_alloc`, `peak_memory_reserved`)
* **DPO Recipe (`recipes/full_dpo_distributed.py`):**
  * `rewards/chosen`
  * `rewards/rejected`
  * `rewards/accuracies`
  * `rewards/margins`
  * `log_probs/chosen`
  * `log_probs/rejected`
  * `logits/chosen`
  * `logits/rejected`

### 1.5 Reusability for Robosuite Pixel-Based Benchmark
* **Replay Buffer:** None for continuous state vector/image observations (operates on text token trajectory structures).
* **Environment Wrappers:** None.
* **Visual Encoder Modules:** Contains `VisionTransformer` in [`torchtune/modules/vision_transformer.py`](https://raw.githubusercontent.com/pytorch/torchtune/main/torchtune/modules/vision_transformer.py) (for Llama 3.2 Vision), but it is tightly coupled to LLM token embedding projections.
* **Verdict:** **Nothing directly reusable** for robosuite continuous control visual RL benchmarks.

---

## 2. torchforge (`meta-pytorch/torchforge`)

### 2.1 Establishment: What It Is, Publisher, Release Status & Scope
* **Publisher:** Meta Platforms / PyTorch team under the official [`meta-pytorch/torchforge`](https://github.com/meta-pytorch/torchforge) repository.
* **Release & Creation:** Created June 24, 2025 (`2025-06-24T18:41:45Z`). Default branch: `main`.
* **Current Status:** **Development Paused.** The repository README explicitly includes the following header banner:
  > *"⚠️ Development paused: Development in Forge has paused. LLM training at PyTorch is being consolidated in torchtitan (https://github.com/pytorch/torchtitan)."*
* **Stated Scope:** *"A PyTorch-native agentic RL library that lets you focus on algorithms—not infra."* It was built to decouple distributed infrastructure concerns (actor placement, Monarch compute meshes, vLLM text generation) from RL algorithm logic.
* **Locators:**
  * Repository: [`meta-pytorch/torchforge`](https://github.com/meta-pytorch/torchforge)
  * README: [`README.md`](https://raw.githubusercontent.com/meta-pytorch/torchforge/main/README.md)
  * PyTorch Blog Announcement: [`https://pytorch.org/blog/introducing-torchforge/`](https://pytorch.org/blog/introducing-torchforge/)

### 2.2 Policy-Gradient Implementations
* **Algorithms Implemented:**
  * **GRPO:** Implemented as `GRPOLoss` class in [`src/forge/rl/loss/grpo.py`](https://raw.githubusercontent.com/meta-pytorch/torchforge/main/src/forge/rl/loss/grpo.py). Application script in [`apps/grpo/main.py`](https://raw.githubusercontent.com/meta-pytorch/torchforge/main/apps/grpo/main.py).
  * **DAPO:** Implemented as `DAPOLoss` class in [`src/forge/rl/loss/dapo.py`](https://raw.githubusercontent.com/meta-pytorch/torchforge/main/src/forge/rl/loss/dapo.py).
  * **CISPO / GSPO / SAPO:** Implemented in `src/forge/rl/loss/cispo.py`, `gspo.py`, and `sapo.py`.
* **GRPO Details:**
  * **Advantage Estimator:** Group-relative advantage estimation ( = R_i - \text{mean}(R)$) computed across $ sampled completions per prompt. Eliminates the critic value model.
  * **Value Head:** None.
  * **KL Penalty:** Uses $ KL divergence estimator ( = r_{ref} - \log r_{ref} - 1$, where {ref} = \pi_{ref} / \pi_\theta$) with coefficient `beta = 0.1` (default).
  * **Reference Model:** Explicit `ReferenceModel` actor ([`forge.actors.reference_model.ReferenceModel`](https://raw.githubusercontent.com/meta-pytorch/torchforge/main/apps/grpo/main.py)) evaluated to produce `ref_logprobs`.
  * **DR-GRPO Variant:** Implements "Done Right" GRPO (`agg_type="fixed_horizon"`) to eliminate length bias inherent in sequence-mean division.

### 2.3 Position on Code Sharing vs. Duplication
`torchforge` separates reusable core distributed infrastructure primitives (`src/forge/actors/`, `src/forge/controller/`) from top-level application scripts (`apps/grpo/main.py`, `apps/sft/main.py`).
* **Locator:** [`README.md`](https://raw.githubusercontent.com/meta-pytorch/torchforge/main/README.md)
* **Direct Quote:**
  > *"The primary purpose of the torchforge ecosystem is to separate infra concerns from model concerns thereby making RL experimentation easier. torchforge delivers this by providing clear RL abstractions and one scalable implementation of these abstractions. When you need fine-grained control over placement, fault handling/redirecting training loads during a run, or communication patterns, the primitives are there. When you don’t, you can focus purely on your RL algorithm."*

### 2.4 Concrete Logged Metrics
* **From `src/forge/rl/loss/grpo.py` & `src/forge/rl/loss/ops.py`:**
  * `loss`
  * `pg_loss` / `policy_loss`
  * `kl` / `kl_loss`
  * `entropy`
  * `ratio`
  * `clip_fraction`
* **From `apps/grpo/grading.py`:**
  * `math_reward`
  * `thinking_reward`

### 2.5 Reusability for Robosuite Pixel-Based Benchmark
* **Replay Buffer:** `forge.actors.replay_buffer.ReplayBuffer` is designed for text completion tokens.
* **Distributed Collector:** `Generator` actor integrates with vLLM for high-throughput text sequence sampling.
* **Visual/Robotic Primitives:** None.
* **Verdict:** **Nothing directly reusable** for pixel-based continuous control.

---

## 3. torchbeast (`facebookresearch/torchbeast`)

### 3.1 Purpose & Scope
* **Primary Scope:** `torchbeast` is a PyTorch implementation of IMPALA (Importance Weighted Actor-Learner Architecture) for scalable, asynchronous distributed deep reinforcement learning.
* **Target Domain:** Designed for discrete action environments (Atari).
* **Publisher:** Facebook AI Research (FAIR) in 2019.
* **Locators:**
  * Repository: [`facebookresearch/torchbeast`](https://github.com/facebookresearch/torchbeast)
  * README: [`README.md`](https://raw.githubusercontent.com/facebookresearch/torchbeast/main/README.md)
  * Paper: [arXiv:1910.03552 (Küttler et al., 2019)](https://arxiv.org/abs/1910.03552)

### 3.2 Policy-Gradient Implementations
* **Implemented Algorithm:** IMPALA (V-trace actor-critic algorithm) in [`torchbeast/core/vtrace.py`](https://raw.githubusercontent.com/facebookresearch/torchbeast/main/torchbeast/core/vtrace.py) (`from_logits` function) and [`torchbeast/monobeast.py`](https://raw.githubusercontent.com/facebookresearch/torchbeast/main/torchbeast/monobeast.py).
* **PPO / GRPO / DPO Support:** Does **NOT** implement PPO, GRPO, or DPO.
* **V-trace Details:**
  * **Advantage Estimator:** Truncated importance sampling ratios ($\rho_t, c_t$) to compute 569Xtrace target values $ and policy gradient advantage  = \rho_t (r_t + \gamma v_{t+1} - V(x_t))$.
  * **Value Head:** Scalar baseline head `self.baseline = nn.Linear(512, 1)` predicting state value (s)$.
  * **KL Penalty:** None. Uses entropy loss (`entropy_cost * entropy_loss`) for exploration.
  * **Reference Model:** None (uses old behavior policy log-probs stored during rollout to compute importance ratios $\rho$).

### 3.3 Position on Code Sharing vs. Duplication
`torchbeast` provides two distinct implementations with clear design trade-offs:
1. **MonoBeast ([`torchbeast/monobeast.py`](https://raw.githubusercontent.com/facebookresearch/torchbeast/main/torchbeast/monobeast.py)):** A pure Python + PyTorch single-file implementation (~450 lines) containing the network architecture, environment wrappers, actor threads, learner loop, and queue handling.
2. **PolyBeast ([`torchbeast/polybeast.py`](https://raw.githubusercontent.com/facebookresearch/torchbeast/main/torchbeast/polybeast.py)):** Decouples actor processes via C++ `libtorchbeast` and gRPC for multi-machine scaling.
* **Rationale:** MonoBeast prioritizes hackability, readability, and zero external dependencies; PolyBeast prioritizes high-throughput C++ execution across multi-node GPU clusters.

### 3.4 Concrete Logged Metrics
* **From `torchbeast/monobeast.py` (`stat_keys`):**
  * `step`
  * `total_loss`
  * `mean_episode_return`
  * `pg_loss`
  * `baseline_loss`
  * `entropy_loss`

### 3.5 Reusability for Robosuite Pixel-Based Benchmark
* **Environment Wrappers:** [`torchbeast/atari_wrappers.py`](https://raw.githubusercontent.com/facebookresearch/torchbeast/main/torchbeast/atari_wrappers.py) contains `FrameStack` and `WarpFrame` (84x84 grayscale).
* **Async Infrastructure:** Shared-memory queue pattern for asynchronous actor-learner communication.
* **Verdict:** **Minimal direct reusability**. Robosuite requires 3-channel RGB image processing and continuous control heads, whereas TorchBeast assumes discrete action spaces and 84x84 1-channel frames.

---

## 4. PyTorch's Own RL-Adjacent Recipes (TorchRL / `pytorch/rl`)

### 4.1 Purpose & Scope
* **Primary Scope:** TorchRL ([`pytorch/rl`](https://github.com/pytorch/rl)) is PyTorch's official domain library for Reinforcement Learning, robotics, and decision making.
* **Design Philosophy:** Provides PyTorch-native, modular "Lego blocks" for environments, data buffers (`TensorDictReplayBuffer`), transforms (`Transform`), loss functions (`LossModule`), and execution modules (`DataCollector`).
* **Locators:**
  * Repository: [`pytorch/rl`](https://github.com/pytorch/rl)
  * README: [`README.md`](https://raw.githubusercontent.com/pytorch/rl/main/README.md)
  * Documentation: [`https://pytorch.org/rl/`](https://pytorch.org/rl/)

### 4.2 Policy-Gradient & Off-Policy Implementations
* **Implemented Algorithms:**
  * **PPO:** Implemented as `PPOLoss`, `ClipPPOLoss`, and `KLPENPPOLoss` in [`torchrl/objectives/ppo.py`](https://raw.githubusercontent.com/pytorch/rl/main/torchrl/objectives/ppo.py).
  * **GRPO:** Implemented as `GRPOLoss` in [`torchrl/objectives/llm/grpo.py`](https://raw.githubusercontent.com/pytorch/rl/main/torchrl/objectives/llm/grpo.py).
  * **SAC:** Implemented as `SACLoss` in [`torchrl/objectives/sac.py`](https://raw.githubusercontent.com/pytorch/rl/main/torchrl/objectives/sac.py).
  * **DreamerV3:** Implemented as `DreamerV3Loss` in [`torchrl/objectives/dreamer_v3.py`](https://raw.githubusercontent.com/pytorch/rl/main/torchrl/objectives/dreamer_v3.py).
  * **DDPG / TD3 / A2C / REDQ:** `DDPGLoss`, `TD3Loss`, `A2CLoss`, `REDQLoss` under `torchrl/objectives/`.
* **TorchRL PPO Details:**
  * **Advantage Estimator:** Generalized Advantage Estimation (GAE) via `torchrl.objectives.value.advantages.GAE` module or functional `vec_td_lambda_advantage_estimate`.
  * **Value Head:** Critic network encapsulated as a `ValueOperator` module predicting scalar state value (s)$.
  * **KL Handling:** `ClipPPOLoss` uses PPO epsilon clipping (`clip_epsilon`); `KLPENPPOLoss` computes adaptive KL penalty against a reference policy.
  * **Reference Model:** Supported in `KLPENPPOLoss` or target actor parameters.

### 4.3 Position on Code Sharing vs. Duplication
TorchRL strongly advocates for **reusable, composable modular components** over monolithic training scripts, built around `TensorDict`.
* **Locator:** [`README.md`](https://raw.githubusercontent.com/pytorch/rl/main/README.md)
* **Direct Quote:**
  > *"TorchRL is a PyTorch-native toolkit for reinforcement learning, decision making, robotics, and simulation. It is not a single algorithm implementation or a narrow benchmark suite: it is a collection of composable pieces for building RL systems while keeping the code close to the PyTorch programming model."*
* Reference scripts live in `sota-implementations/` (e.g. [`sota-implementations/ppo/ppo_mujoco.py`](https://raw.githubusercontent.com/pytorch/rl/main/sota-implementations/ppo/ppo_mujoco.py)), consuming shared library primitives (`ClipPPOLoss`, `TensorDictReplayBuffer`, `SyncDataCollector`).

### 4.4 Concrete Logged Metrics
* **From `sota-implementations/ppo/ppo_mujoco.py` & `torchrl/objectives/ppo.py`:**
  * `train/reward`
  * `train/episode_length`
  * `train/loss_objective` (policy surrogate loss)
  * `train/loss_critic` (value function MSE loss)
  * `train/loss_entropy` (policy entropy)
  * `train/lr`
  * `train/clip_epsilon`
  * `eval/reward`
  * `eval/episode_length`
  * `ESS` (Effective Sample Size)

### 4.5 Reusability for Robosuite Pixel-Based Benchmark
* **TensorDictReplayBuffer:** High-performance memory-mapped binary replay buffer (`torchrl.data.TensorDictReplayBuffer` with `LazyMemmapStorage`) for storing high-resolution image transitions on disk/RAM without PyTorch reference cycle memory leaks.
* **Transforms / Preprocessing:** `CatFrames` (frame stacking), `ToTensorImage` (uint8 to float32 normalization), `ResizeImage`.
* **Robosuite Environment Wrappers:** `RobosuiteWrapper` in `torchrl/envs/custom/robosuite.py` and `GymWrapper` in `torchrl/envs/adapters/gym.py`.
* **Verdict:** **HIGH REUSABILITY**. TorchRL's `TensorDictReplayBuffer`, `CatFrames` transform, and `RobosuiteWrapper` are directly reusable for a robosuite pixel-based generalization benchmark.

---

## 5. Other Relevant Visual RL Training Libraries

### 5.1 CleanRL (`vwxyzjn/cleanrl`)
* **1. Purpose:** High-quality single-file implementations of Deep RL algorithms (PPO, PPG, SAC, DDPG, TD3, DQN).
  * Locators: [`README.md`](https://raw.githubusercontent.com/vwxyzjn/cleanrl/master/README.md), [`cleanrl/ppo.py`](https://raw.githubusercontent.com/vwxyzjn/cleanrl/master/cleanrl/ppo.py), [`cleanrl/ppg_procgen.py`](https://raw.githubusercontent.com/vwxyzjn/cleanrl/master/cleanrl/ppg_procgen.py).
* **2. Policy Gradient Implementations:**
  * Implements PPO in `cleanrl/ppo.py`, `cleanrl/ppo_atari.py`, `cleanrl/ppo_continuous_action.py`, `cleanrl/ppo_procgen.py`.
  * Implements PPG (Phasic Policy Gradient) in `cleanrl/ppg_procgen.py` (Procgen!).
  * *UNVERIFIED:* `drqv2.py` in main branch root. *Verification attempt:* Searched git tree of `vwxyzjn/cleanrl` for `drq` or `dmc` paths; no matching files found in the core repository.
* **3. Code Sharing vs. Duplication Position:**
  * Strict single-file philosophy.
  * Quote from [`README.md`](https://raw.githubusercontent.com/vwxyzjn/cleanrl/master/README.md):
    > *"📜 Single-file implementation: Every detail about an algorithm variant is put into a single standalone file. For example, our ppo_atari.py only has 340 lines of code but contains all implementation details on how PPO works with Atari games, so it is a great reference implementation to read for folks who do not wish to read an entire modular library."*
* **4. Concrete Logged Metrics:**
  * `charts/episodic_return`
  * `charts/episodic_length`
  * `losses/policy_loss`
  * `losses/value_loss`
  * `losses/entropy`
  * `losses/old_approx_kl`
  * `losses/approx_kl`
  * `losses/clipfrac`
  * `losses/explained_variance`
  * `charts/SPS` (Steps Per Second)
* **5. Reusability:** CleanRL scripts are designed as copyable single-file templates. Excellent reference code for self-contained PPO or PPG visual loops.

### 5.2 Stable-Baselines3 (`DLR-RM/stable-baselines3`)
* **1. Purpose:** Standard modular PyTorch RL library.
  * Locator: [`README.md`](https://raw.githubusercontent.com/DLR-RM/stable-baselines3/master/README.md)
* **2. Policy Gradient Implementations:** PPO (`PPO` class in `stable_baselines3/ppo/ppo.py`), SAC (`SAC` class in `stable_baselines3/sac/sac.py`).
* **3. Code Sharing Position:** Modular object-oriented framework with shared base abstractions (`BaseAlgorithm`, `OffPolicyAlgorithm`).
* **4. Logged Metrics:** `rollout/ep_rew_mean`, `rollout/ep_len_mean`, `train/policy_gradient_loss`, `train/value_loss`, `train/entropy_loss`, `train/approx_kl`, `train/clip_fraction`, `train/loss`.
* **5. Reusability:** `VecFrameStack`, `VecTransposeImage`, `NatureCNN` / `CombinedExtractor`.

---

## 6. Summary Comparison Matrix

| Library | Primary Target | PPO / GRPO Implemented? | Code Sharing Stance | Robosuite Reusability |
|---|---|---|---|---|
| **torchtune** | LLM / VLM Post-Training | PPO (`PPOLoss`), GRPO (`GRPOLoss`), DPO (`DPOLoss`) | Single-file recipes over abstractions | None (LLM text tokens) |
| **torchforge** | Agentic RL & LLM Scaling | GRPO (`GRPOLoss`), DAPO (`DAPOLoss`), CISPO, GSPO | Decoupled infra + app scripts | None (Development paused) |
| **torchbeast** | Distributed Discrete RL | IMPALA V-trace (No PPO/GRPO) | Single-file MonoBeast vs C++ PolyBeast | Minimal (Atari 84x84 discrete) |
| **TorchRL** | General Modular PyTorch RL | PPO (`ClipPPOLoss`), GRPO (`GRPOLoss`), SAC, DreamerV3 | Modular composable components (`TensorDict`) | **High** (`TensorDictReplayBuffer`, `CatFrames`, `RobosuiteWrapper`) |
| **CleanRL** | Single-File Reference RL | PPO (`cleanrl/ppo.py`), PPG (`cleanrl/ppg_procgen.py`) | Single-file implementation strictly | Moderate (Reference copyable scripts) |
| **Stable-Baselines3** | Standard DRL Benchmark | PPO (`ppo.py`), SAC (`sac.py`) | Modular OOP framework | Moderate (`VecFrameStack`, `NatureCNN`) |
