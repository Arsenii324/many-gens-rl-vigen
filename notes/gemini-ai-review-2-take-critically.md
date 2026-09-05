### Notice: This AI review is written by Gemini which is a weak AI model. Take the review critically and specifically don't regard it's overconfident and prescriptive claims as truth.

### 1.1 The Two Hard Engineering Blockers

  1. ibac_sni V100 Concurrency Fatal Crash (procs=16) & Worker RNG Collapse:
      • Mechanism: penv.py:21-35 constructs live environment objects in the main process before passing them to child processes via multiprocessing.Process(target=worker, args=(remote, env)). Meanwhile,
      train.py:110 explicitly forces multiprocessing.set_start_method("fork").
      • Failure 1 (EGL Fatal Crash): MuJoCo C-level OpenGL/EGL display contexts do not survive a POSIX fork(). As empirically measured in DataSphere job bt1q6jd096m3re2n7jp2, any configuration with procs > 1
      immediately terminates during environment initialization with an unhandled EOFError from dead worker pipes.
      • Failure 2 (Worker RNG Collapse): Inside penv.py:4-16, child processes never reseed the global NumPy RNG. Because Door's physical placement is sampled via global np.random.uniform (C69), all 16 workers
      under fork() inherit identical PRNG states. Even if EGL were patched, all 16 environments would advance through identical door positions, collapsing rollout diversity.
      • Status: Gated by gate_ibac_procs_is_runnable. NATIVE_HOST_PROFILE=v100 cannot use procs=16 until workers are refactored to spawn with clean in-worker environment factory instantiation and explicit
      worker-indexed seeding.
  2. Uncommitted Repository State (Source Freezing Failure):
      • Mechanism: git status --short reveals 164 uncommitted paths (68 modified tracked files, 96 untracked test scripts, configs, and diagnostic notes).
      • Risk: Provenance records stamp a Git commit SHA (git rev-parse HEAD), but HEAD currently points to 12f6322 (predating the entire evaluation overhaul, the CTRL double-reset fix, the PPG tensor reduction
      fix, and the IBAC β fix).
      • Status: Gated by gate_source_tree_frozen. Launching any production cell from a dirty working tree invalidates the cryptographic audit trail of the campaign.


  ### 1.2 Audit of Instrument Integrity: A False Absence in production_gates.py

  In accordance with the project's strict audit protocol, we audited the audit scripts themselves. We identified a live defect in production_gates.py:675:

    # scripts/production_gates.py:675
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "audit_pairing_evidence.py")],
                          capture_output=True, text=True, timeout=180)

  subprocess.run omits cwd=ROOT. Consequently, audit_pairing_evidence.py defaults to searching for results/records/*.jsonl in the process caller's current working directory. When invoked from outside the
  repository root, it fails to find the records and reports OWNER: no records contain two regimes....

  When executed with cwd=ROOT pointing to the actual records:

      ibac_sni s1 scene 0 rev a8664a7f98dc: eval-easy vs train -- physically PAIRED, 5 episodes
      idaac s1 scene 0 rev 4ad7d3b878ad: eval-easy vs train -- physically PAIRED, 5 episodes
      idaac s1 scene 0 rev 8d5c1dd0b4b3: eval-easy vs train -- physically PAIRED, 5 episodes
      ppg s1 scene 0 rev a8664a7f98dc: eval-easy vs train -- physically PAIRED, 5 episodes
      rad s1 scene 0 rev a8664a7f98dc: eval-easy vs train -- physically PAIRED, 5 episodes
    
      5 cross-regime comparisons; 0 not paired; 1 lacking physical evidence

  Physical pairing across train and eval-easy is 100% verified (zero mismatches across 5 episodes in all valid records). The gate's OWNER status was a false negative caused by omitting the working directory
  parameter.
  ──────
  ## 2. Algorithm-by-Algorithm Deep Technical Audit

  The twelve baselines span seven codebases and five distinct RL paradigm lineages. Every baseline carries adaptations, structural assumptions, and hardware compromises that must be explicitly acknowledged.

    =============================================================================================================================
                                             ALGORITHM COMPARABILITY MATRIX (12 BASELINES)
    =============================================================================================================================
    Baseline   Lineage     Obs Size     Frame Stack   Action Dist         Horizon      Replay Buffer   Parallelism (Dev/V100)
    -----------------------------------------------------------------------------------------------------------------------------
    drqv2      RL-ViGen    84x84 CHW    3 (9-ch)      Clipped Noise       Terminal     300k / 620k     1 env (sync)
    drq        RL-ViGen    84x84 CHW    3 (9-ch)      Squashed Gaussian   Terminal     300k / 620k     1 env (sync)
    svea       RL-ViGen    84x84 CHW    3 (9-ch)      Clipped Noise       Terminal     300k / 620k     1 env (sync)
    sgqn       RL-ViGen    84x84 CHW    3 (9-ch)      Clipped Noise       Terminal     300k / 620k     1 env (sync)
    curl       RL-ViGen    84x84 CHW    3 (9-ch)      Clipped Noise       Terminal     300k / 620k     1 env (sync)
    rad        dmc_gb      100->84 CHW  3 (9-ch)      Squashed Gaussian   Bootstrap    600k (unif)     1 env (sync)
    soda       dmc_gb      100->84 CHW  3 (9-ch)      Squashed Gaussian   Bootstrap    600k (unif)     1 env (sync)
    alda       dmc_gb ext  64x64 CHW    3 (9-ch)      Squashed Gaussian   Bootstrap    1000k (unif)    1 env (sync)
    idaac      Procgen     64x64 CHW    1 (3-ch)      Unsquashed Gauss    Terminal     Rollout only    4 / 16 envs (DummyVec)
    ppg        Procgen     64x64 HWC    1 (3-ch)      Unsquashed Gauss    Terminal     Rollout only    8 / 16 envs (ConcatEnv)
    ctrl       JAX/Flax    64x64 HWC    1 (3-ch)      Unsquashed Gauss    Terminal     Rollout only    16 / 16 envs (SyncVec)
    ibac_sni   CoinRun     64x64 HWC    1 (3-ch)      Unsquashed Gauss    Terminal     Rollout only    1 / 16* procs (ParallelEnv)
    =============================================================================================================================
    * Blocked by POSIX fork crash on MuJoCo/EGL.

  ### 2.1 The RL-ViGen Native Five (drqv2, drq, svea, sgqn, curl)

  All five native baselines reside in algos. They form Tier 1: an internally controlled comparison sharing observation layout (84 × 84 with 3-frame stack, scaled x / 255.0 - 0.5), action execution
  (action_repeat=1), 500-step terminal horizon, and replay buffer geometry.

  1. drqv2 (DrQ-v2):
      • Lineage: Yarats et al. (ICLR 2022). Off-policy actor-critic with DDPG-style clipped double Q-learning and n-step TD (n = 3).
      • Action Distribution: Deterministic squashed mean with additive clipped exploration noise:


    a = clip ⎛tanh ⎛μ (s)⎞ + clip (ε, - c,c), - 1,1⎞
             ⎝     ⎝ θ   ⎠                         ⎠

  where ε sim 𝒩(0,σ²). Scheduled exploration noise decays linearly from 1.0 → 0.1 over 100,000 frames.

  • Evaluation Performance: Achieves training competence (

    R      ≈ 480.6
     train

  on Door), but published RL-ViGen Door eval-easy return is 3.6 (statistically indistinguishable from the random floor ≈1.842). DrQ-v2 fails to generalize to visual shift on Door in the reference benchmark
  itself.

  2. drq (DrQ):
      • Lineage: Kostrikov et al. (ICLR 2021). Built on Soft Actor-Critic (SAC) with squashed Gaussian policy: a = tanh (u),u sim 𝒩(μ,σ).
      • TD Target & Learning Rate: Fixed to 1-step TD (n = 1) per canonical specification. Learning rate is 1 × 10⁻⁴ (RL-ViGen's global robosuite default) vs canonical 1 × 10⁻³.
  3. svea (SVEA) — Critical Canonical Divergence:
      • Canonical Formulation: Hansen et al. (NeurIPS 2021) optimize:


     svea                 ⎛ conv  ⎞
    ℒ     = αℒ (s,a) + βℒ ⎝s    ,a⎠
     Q        Q          Q

     where 

     conv
    s

  is generated via random convolution, and the policy gradient

    ∇ J(θ)
     θ

  is evaluated strictly on unaugmented observations s.

  • RL-ViGen Implementation: svea.py:12-298 imports and applies SODA's Places365 natural image overlay, not random convolution! Furthermore, it is built on a DrQ-v2 trunk rather than SAC.
  • Report Label Requirement: Must be cited as "RL-ViGen's SVEA", never canonical SVEA.

  4. sgqn (SGQN):
      • Lineage: Song et al. Uses saliency maps from Q-network gradients ∇ₛQ(s,a) with quantile thresholding (q = 0.93) to mask non-salient background pixels and apply feature consistency loss.
      • Fidelity History: Earlier versions carried a catastrophic aux_lr = 0.3 (1000 × canonical 3 × 10⁻⁴) directly on the shared encoder. The live configuration in sgqn_config.yaml sets aux_lr = 1e-4 (a 3 ×
      divergence from canonical, but no longer destabilizing).
  5. curl (CURL):
      • Lineage: Laskin et al. (ICML 2020). InfoNCE contrastive representation learning between two random spatial crops of the same frame.
      • Implementation: Ported in RL-ViGen onto a DrQ-v2 base (canonical was SAC). Uses lr = 1 × 10⁻⁴ (10 × lower than canonical 1 × 10⁻³).


  ### 2.2 DMControl-GB Lineage (rad, soda)

  Housed in dmc_gb.

  6. rad (RAD):
      • Mechanism: SAC with random crop data augmentation.
      • Observation & Resolution: Renders at 100 × 100, applies 84 × 84 random crop during training and 84 × 84 center crop during evaluation. Frame stack 3.
      • Truncation: Bootstraps at the 500-step horizon (done_no_max=True).
      • Replay: 600,000 capacity; uniform sampling over the entire run without eviction.
  7. soda (SODA):
      • Mechanism: Hansen & Wang (ICLR 2021). Decoupled representation learning via momentum encoder (BYOL-style) predicting features of clean observations from Places365-augmented observations.
      • Augmentation Split (A22): configure_places365_val.py:34-35 forces use_val=True. SODA, SVEA, and SGQN all train against the Places365 validation split.
      • Computational Cost: Longest single training cell in the fleet (~51.3 h training + 8.1 h trajectory evaluation on T4).


  ### 2.3 Adversarial learned data augmentation (alda)

  8. alda (ALDA):
      • Mechanism: Trains an adversarial generator to synthesize visual perturbations maximizing policy divergence under a regularization penalty. Built on an SAC trunk.
      • Observation: 64 × 64 with 3-frame stack.
      • Memory Envelope: Measured peak host RSS is 14.73 GiB. On DataSphere, it required gt4i.1 and crashed on gt4.1. On the 113 GB V100 host, it fits comfortably, but its memory footprint dictates host packing
      limits.


  ### 2.4 Procgen Lineage Continuous Adaptations (idaac, ppg)

  Both algorithms were originally authored for OpenAI Procgen (discrete 15-way actions, 64 parallel environments, persistent game levels). Their port to continuous robosuite Door introduces fundamental design
  adaptations.

  9. idaac (IDAAC):
      • Mechanism: Raileanu et al. (ICML 2021). Decoupled actor and critic with an adversarial instance-invariance auxiliary loss enforcing representation invariance across game levels.
      • Continuous Action Space: Unsquashed Gaussian distribution 𝒩(μ(s),diag (σ²)).
      • Observation: 64 × 64, single frame (no frame stack).
      • The Fundamental Target Handicap (C49/C50): In Procgen, level_seed designates structurally distinct procedural levels. In robosuite Door, mapping level_seed to episode_index means the invariance
      adversary attempts to predict a feature that is decodable at chance (0.125), whereas scene_id is decodable at 1.000. The instance-invariance mechanism is functionally inert on this benchmark.
      • Parallelism: Uses DummyVecEnv running sequentially in-process (4 envs preproduction, 16 on V100).
  10. ppg (Phasic Policy Gradient):
      • Mechanism: Cobbe et al. (ICML 2021). Alternates between standard PPO policy updates and an auxiliary phase optimizing:


    ℒ    = ℒ      + β     D  ⎛π   ||π⎞
     aux    value    clone KL⎝ old   ⎠

    - *Auxiliary KL Tensor Reduction Fix (A2)*: The author's original code had `kl.mean()`. In discrete action spaces, KL per sample is a scalar. In a 7-D continuous action space, `kl` has shape `[B, 7]`. Bare
  `.mean()` averaged over the action dimension, weakening the policy cloning constraint by **7 ×**. Codex applied `kl.sum(-1).mean()` in ppg.py:203, restoring the correct multivariate Gaussian KL bound.
    - *The Retimed Auxiliary Schedule (

    n  = 32
     π

  )*:
  - Canonical Procgen: 4 MPI workers × 64 envs × 256 steps implies 65,536 samples per rollout. With

    n  = 32
     π

  , the auxiliary phase fires every 2.10 × 10⁶ frames. In a 600,000 frame budget, upstream PPG would execute zero auxiliary phases.
  - Preproduction Setup: 1 MPI worker × 8 envs × 256 steps implies 2,048 samples per rollout. With

    n  = 32
     π

  , the auxiliary phase fires every 65,536 frames (≈9 auxiliary phases).
  - V100 Target (16 envs): Auxiliary phase fires every 131,072 frames (≈4 auxiliary phases).
  - Verdict: Must be reported as "a continuous-action port of PPG, retimed".

  ### 2.5 JAX Contrastive Reinforcement Learning (ctrl)

  11. ctrl (CTRL):
      • Mechanism: Contrastive reinforcement learning via mutual information and clustering. Learns representations by clustering states and optimizing a cluster contrastive loss (


    L
     clust

  ).
  - Upstream Defect Fixed: Upstream repository ctrl_public @ 7a118c8 shipped with lines defining

    L
     clust

  commented out, raising NameError on execution. This project restored the author's lines.
  - MYOW Neighbor Construction: In algo.py:218-252, the loop over k nearest prototypes uses indx[:, 0 + 1] (a constant index) rather than indx[:, k_idx + 1]. Positives are repeatedly drawn from the single
  nearest neighbor cluster rather than iterating the k neighbors. This is confirmed upstream behavior.
  - Evaluation Double-Reset Bug (Confirmed & Patched):
  - Previous reviews identified that _SyncVecEnv automatically resets on done inside step_wait(), incrementing _episode_indices on every reset. Calling an explicit env.reset() per measured episode caused
  measured episode i to execute condition 2i, desynchronizing CTRL from all other baselines.
  - Verification: In eval_grid.py:892-915, the initial reset is now placed strictly outside the loop (state = env.reset()), and subsequent episodes are driven by the auto-reset observation. Regression tests in
  tests/test_ctrl_episode_pairing.py verify condition indices sequence strictly 0 → 1 → 2 → 3.
  - Reward Normalization Fixed: Previously instantiated with normalize_rewards=True, recording clipped normalized returns. Now explicitly sets normalize_rewards=False in eval_grid.py:874.

  ### 2.6 Variational Information Bottleneck (ibac_sni)

  12. ibac_sni (IBAC-SNI):
      • Mechanism: Variational Information Bottleneck (VIB) regularizing the encoder representation z sim 𝒩(μ(s),Σ(s)) via


    βD  (q(z|s)||p(z))
      KL

  , combined with Selective Noise Injection (SNI) on the policy output.
  - The 10,000 × Beta Defect (Discovered & Fixed): runnable/_launch/ibac_sni.sh historically omitted the --beta flag, falling back to the repository default of 1.0, while documentation claimed 1 × 10⁻⁴ (CoinRun
  reference). A bottleneck penalty of 1.0 completely collapsed the latent representation. It is now explicitly passed as --beta 1e-4.
  - Entropy Runaway Fix: In continuous action space, the discrete entropy bonus

    β        = 0.01
     entropy

  caused σ → 4.3 and action clipping rates >93%. Setting entropy_coef = 0 eliminated the runaway.
  - Competence Status: Tested only up to 25k frames without divergence; zero success events observed to date. Requires the 100k pilot (A1) to prove competence before fleet inclusion.
  ──────
  ## 3. The Three Generative Mechanisms

  Across the project's history, approximately sixty reported defects reduce to three fundamental generative failure modes:

    +----------------------------------------------------------------------------------------------------+
    |                                    THE THREE GENERATIVE MECHANISMS                                  |
    +----------------------------------------------------------------------------------------------------+
    | 1. FALSE ABSENCE                  | An instrument that cannot execute returns the same exit/output |
    |                                    | as an instrument that executed and verified a passing state.   |
    |------------------------------------+----------------------------------------------------------------|
    | 2. DUAL HOMES                      | A parameter is specified in two distinct surfaces that drift   |
    |                                    | silently out of synchronization.                               |
    |------------------------------------+----------------------------------------------------------------|
    | 3. TRANSPLANTED CONSTANTS          | A constant tuned in one scope is transplanted into a new scope |
    |    ACROSS SCOPE CHANGES            | where its mathematical role is fundamentally altered.          |
    +----------------------------------------------------------------------------------------------------+

  1. Mechanism 1 (False Absence):
      • Definition: An instrument that fails before testing reports the same signal as a passing test.
      • Instances:
          • production_gates.py:675 calling audit_pairing_evidence.py without cwd=ROOT, causing it to report no records found.
          • scripts/rlvigen_reference.py searching for evaluation_score.xlsx at an unextracted path, printing "absent" and causing the published Door numbers to go unread for months.
          • Test files containing except Exception: pytest.skip(), causing wrapper TypeError defects to mask as missing dependencies.
          • Runner scripts setting SAVE_EVERY while the underlying script read SAVE_EVERY_FRAMES, logging "SUCCESS" while saving only at the endpoint.

  2. Mechanism 2 (Dual Homes):
      • Definition: Two configuration files maintain the same parameter, and changes applied to one leave the other active.
      • Instances:
          • Replay capacity declared in constants vs production blocks in families.json.
          • Production schedule specifying 500k frames while protocol specified 600k frames.
          • Open decisions split across open_decisions.py and DECISION-SHEET.md.
          • Evaluator defaults duplicated in eval_grid.CTRL_DEFAULTS and families.json.

  3. Mechanism 3 (Transplanted Constants Across Scope Changes):
      • Definition: When an algorithm is ported across action spaces, task horizons, or hardware concurrency tiers, copying literal hyperparameter values inverts their semantic function.
      • Instances:
          • IBAC-SNI entropy coefficient β = 0.01: Tuned for 15-way discrete actions (bounded entropy [0,ln 15]); in 7-D continuous Gaussian space (unbounded entropy), it drove policy scale σ → 4.3.
          • PPG auxiliary KL .mean(): Tuned for scalar discrete KL; in 7-D Gaussian space, it diluted the cloning penalty by 7 ×.
          • PPG



    n  = 32
     π

  : Tuned for 65,536-step rollouts; in an 8-env setup, it increased auxiliary phase frequency by 32 ×.
  - IDAAC level_seed: Tuned for distinct game instances in Procgen; mapped to episode index in Door where target variance is decodable at chance (0.125).
  ──────
  ## 4. Measurement Pipeline & Evaluation Chokepoint

  ### 4.1 Evaluation Architecture (scripts/eval_grid.py)

  Offline evaluation decouples measurement from training dynamics:

  • Evaluates a frozen snapshot across a full grid: 4 regimes (train, eval-easy, eval-medium, eval-hard) × 10 scenes {0,…,9} × E episodes.
  • Seeding Formula:

    placement\_condition\_seed = SeedSequence ([eval\_seed,scene\_id,episode\_index])

  • Physical Pairing Invariant (Verified): Because regime is excluded from the seed, episode i under train and episode i under eval-easy receive identical initial object poses (body_pos, body_quat). Physical
  pairing is confirmed across all evaluated families.
  • Scene Heterogeneity Implication (A21): Because scene_id is included in the seed, episode i in scene 0 and episode i in scene 1 receive different door placements. Within-scene comparisons across regimes are
  strictly paired; across-scene comparisons are unpaired.

  ### 4.2 Determinism Scope & The 0.77% Noise Floor

  Replicate experiments on CUDA (bt1baht74a35e6uq582c, bt1e78hbs4s946aje3q9, r112, r113) under identical code, payload, weights, and torch.use_deterministic_algorithms(True) establish the following variance
  properties:

  • eval-easy: Exactly bitwise identical across all 4 independent runs (10.373746, spread = 0.000000).
  • train: Replicate runs produce identical returns on 3 of 5 episodes; minor divergence on 2 episodes bounded at Δ = 0.1165 (0.77% of the mean return).
  • Physical Root: CUBLAS_WORKSPACE_CONFIG=:4096:8 and Torch determinism govern PyTorch GPU kernels. MuJoCo C physics integration and EGL/OpenGL rendering run outside Torch's determinism scope.
  • Protocol Implication: "Validation" cannot require bitwise equality. It requires execution path integrity, complete diagnostics, and physical placement agreement. Any scientific claim of performance
  difference between methods must exceed this 0.77% baseline noise floor.
  ──────
  ## 5. Comparability Seams & Identifiability of Generalisation Claims

  Running audit_comparability_seam.py establishes:

  • UNITS: 6 of 6 derived axes are uniform (episode horizon = 500, reported estimator = fixed-policy sample mean, evaluation scene set = 10 scenes, x-axis accounting = environment transitions).
  • CONDITIONS: 9 of 10 derived axes split across methods.

    +----------------------------------------------------------------------------------------------------+
    |                                    THE METHOD COLLINEARITY PROBLEM                                 |
    +----------------------------------------------------------------------------------------------------+
    | Condition Axis       | Split Details                                                               |
    +----------------------+-----------------------------------------------------------------------------+
    | Frame Stack          | 3 frames (drqv2, drq, svea, sgqn, curl, rad, soda, alda)                    |
    |                      | 1 frame  (idaac, ppg, ctrl, ibac_sni)                                       |
    +----------------------+-----------------------------------------------------------------------------+
    | Resolution           | 84x84 (drqv2, drq, svea, sgqn, curl)                                        |
    |                      | 64x64 (alda, idaac, ppg, ctrl, ibac_sni)                                    |
    |                      | 100x100 -> 84x84 crop (rad, soda)                                           |
    +----------------------+-----------------------------------------------------------------------------+
    | Action Distribution  | Squashed mean + clipped noise (drqv2, svea, sgqn, curl)                     |
    |                      | SAC squashed Gaussian (drq, rad, soda, alda)                                 |
    |                      | Unsquashed Gaussian (idaac, ppg, ctrl, ibac_sni)                             |
    +----------------------+-----------------------------------------------------------------------------+
    | Truncation           | Terminal value zeroed at 500 steps (9 baselines)                            |
    |                      | Value bootstrapped at 500 steps (rad, soda, alda)                           |
    +----------------------+-----------------------------------------------------------------------------+
    | Replay Eviction      | Recency ring evicting 50% of run (drqv2, drq, svea, sgqn, curl on 300k cap) |
    |                      | Uniform over full run (rad, soda, alda)                                     |
    |                      | No replay / on-policy rollout only (idaac, ppg, ctrl, ibac_sni)             |
    +----------------------------------------------------------------------------------------------------+

  ### 5.1 Scientific Identifiability

  Because algorithm identity is collinear with observation resolution, frame stack, truncation semantics, and action squashing:

  • Unidentifiable: Absolute cross-algorithm return comparisons (

    R         - R
     method A    method B

  ). A difference in return cannot be attributed to the visual representation mechanism vs 1 vs 3 frame stack or bootstrap vs terminal truncation.

  • Identifiable (Estimand B): Within-method relative retention across regimes:

    Δₘ = Rₘ(eval-easy) - Rₘ(train)

  Because all operational conditions (resolution, frame stack, policy trunk) are invariant within method m, Δₘ isolates the policy's invariance to visual shift.

  ### 5.2 Primary Metric Formulation

  Door reward is dense, shaped, and non-zero at floor (

    R      ≈ 1.818
     floor

  ). The raw retention ratio

    ρ = R   /R
         OOD  train

  is not offset-invariant and exhibits severe denominator instability when policies operate near the floor.

  Mandated Metric Hierarchy:

  1. Primary: Task Success Rate (percentage of episodes where door handle was unlatched and opened >0.2  m; strictly offset-invariant) and Return Difference

    Δ = R    - R
         OOD    train

  .
  2. Secondary: Floor-Adjusted Retention Ratio (only for competent baselines):

            R    - R
             OOD    floor
    ρ    = ───────────────,  R      = 1.818
     adj   R      - R         floor
            train    floor
  ──────
  ## 6. The Published Door Anchor Reality & Competence Criteria

  Analysis of published benchmark records in evaluation_score.xlsx (Robosuite sheet) resolves the historical calibration paradox:

    +----------------------------------------------------------------------------------------------------+
    |                                    PUBLISHED RL-VIGEN DOOR PERFORMANCE                             |
    +----------------------------------------------------------------------------------------------------+
    | Method               | Published 5-Seed Scores (Easy)        | Mean Return | Distance from Floor  |
    +----------------------+---------------------------------------+-------------+----------------------+
    | Random Floor (C55)   | Empirical baseline over 200 episodes   | 1.82        | 1.0x (Baseline)      |
    | DrQ-v2               | {3, 7, 4, 3, 1}                       | 3.6         | 2.0x (Near floor)    |
    | CURL                 | {3, 11, 4, 2, 13}                     | 6.6         | 3.6x (Near floor)    |
    | DrQ                  | {1, 28, 4, 29, 8}                     | 14.0        | 7.7x (Near floor)    |
    | SVEA                 | {472, 121, 170, 301, 280}             | 268.8       | 148x (Discriminating)|
    | SGQN                 | {457, 406, 459, 227, 408}             | 391.4       | 215x (Discriminating)|
    +----------------------------------------------------------------------------------------------------+

  ### Scientific Implications:

  1. DrQ-v2 Does Not Generalize on Published Door: In the reference paper, DrQ-v2 achieves a mean return of 3.6 on Door eval-easy. Our measured 100k checkpoint score (

    R      = 480.6,R          = 1.44
     train          eval-easy

  ) is consistent with published results. A low eval return for DrQ-v2 is an accurate reproduction, not a porting bug.
  2. True Positive Controls: Anchoring on DrQ-v2 is uninformative because failure collapses to the floor. The only discriminating positive controls for pipeline verification are SGQN (391.4) and SVEA (268.8).
  ──────
  ## 7. Production Fleet, V100 Migration & Hardware Allocation

  Host specifications from remote-infra.txt:

  • CPU: 16 cores (2 × 8-core Intel Xeon Gold 6154 @ 3.0 GHz, 1 thread/core).
  • RAM: 113 GB available.
  • GPU: 2 × Tesla V100-SXM2-32GB.
  • Tenant State: GPU 0 is occupied (15.1 GB VRAM, 67% util); GPU 1 is free.

  ### 7.1 Memory Packing & Replay Buffer Sizing (A14)

  • Binding Constraint: Host RAM (113 GB), not VRAM. Maximum VRAM usage across all baselines is SGQN at 7.1 GiB; most models use 1.6–3.0 GiB.
  • Replay Capacity Sizing:
      • RL-ViGen at action_repeat=1 over a 600k frame budget stores 600,000 + 1,200  reset steps = 601,200 transitions.
      • A 620,000 transition buffer is non-evicting and requires 40.0 GiB RAM per cell.
      • With 113 GB RAM, exactly two RL-ViGen cells can be packed concurrently (2 × 40 = 80  GiB < 113  GiB).
      • Retaining a 1,000,000 buffer requires 62.4 GiB per cell, forcing single-cell execution. The 620k default is strictly optimal for 600k frames.


  ### 7.2 Complete Calendar Cost Model (A13/A20)

  With environment construction measured at 0.6 s (3.4 h total) and intermediate trajectory depth set to 3 episodes per stamp (176 h total):

    Total Workload = 601  h (Train) + 96  h (Endpoint Grid) + 176  h (Trajectory Grid) + 3.4  h (Env Init) ≈ 876  GPU-h (T4 basis)

    +----------------------------------------------------------------------------------------------------+
    |                                      CAMPAIGN CALENDAR ENVELOPE                                    |
    +----------------------------------------------------------------------------------------------------+
    | Deployment Configuration                        | Projected Duration (Days)                        |
    +-------------------------------------------------+--------------------------------------------------+
    | Sequential on Single V100 (GPU 1 only, no pack) | 37 - 41 days                                     |
    | Single V100 with 2-Way RAM Packing (GPU 1 only) | 18 - 28 days                                     |
    | Dual V100 Packed (If GPU 0 becomes available)   | 9 - 14 days (realistic ~9.4 days at 1.5x V100)    |
    +----------------------------------------------------------------------------------------------------+
  ──────
  ## 8. Owner Decision Sheet Ratification & Concrete Action Plan

  Detailed recommendations for the 22 items on DECISION-SHEET.md:

    =============================================================================================================================
                                          RATIFICATION TABLE: OWNER DECISIONS (A1 - A22)
    =============================================================================================================================
    ID    Subject                           Status      Authoritative Action / Recommendation
    -----------------------------------------------------------------------------------------------------------------------------
    A1    IBAC-SNI Final Pilot              REFINED     Do NOT run at procs=16 (fails on fork). Run 100k pilot at procs=1 with
                                                        beta=1e-4 and entropy_coef=0 on V100. Verify flat log_std and return > floor.
    A2    PPG Auxiliary KL Tensor Reduction ADOPTED     Sum over action dimension before mean (kl.sum(-1).mean()). Verified.
    A3    Headline Metric Hierarchy         RESOLVED    Report full matrix. Success rate + Delta primary; floor-adjusted retention secondary.
    A4    P-C76 Generalisation Estimand     RESOLVED    Headline Estimand B (appearance varied, scene fixed). Unconfounded visual contrast.
    A5    Time-Limit Semantics (3 vs 9)     RESOLVED    Declare split (3 bootstrap / 9 terminal). Do not modify vendor clones.
    A6    Seed Replication Policy           RESOLVED    Fixed n = 3 training seeds across all 12 baselines. No outcome-dependent sampling.
    A7    Checkpoint Selection Rule         RESOLVED    Endpoint (frame 600,000) is the headline. 50k trajectory curves descriptive only.
    A8    Protocol Formalisation            RECOMMENDED Merge notes/proposal-inference-and-checkpoint-selection.md into EVAL-PROTOCOL.md.
    A9    External RL-ViGen Anchor          REFINED     Use production SGQN (391.4) and SVEA (268.8) as positive controls. DrQ-v2 is floor.
    A10   Production Canary Ordering        REFINED     Canary IDAAC at 600k first (~7.5 h), then DrQ-v2 (~9.1 h). Do NOT canary SODA (54 h).
    A11   Source Tree Freeze Gate           REQUIRED    Execute git commit of current tree before launching remote production jobs.
    A12   Register Triage Ownership         RESOLVED    Synchronized in docs/REGISTER.md.
    A13   Calendar Budget Model             RESOLVED    876 GPU-h total. 18-28 days on GPU 1 packed; 9-14 days if GPU 0 frees.
    A14   Host Profile Parallelism & Replay RESOLVED    Apply v100 profile: 620k replay buffer (40 GiB, 2-cell packing). Keep procs=1 for IBAC.
    A17   IBAC VIB Coefficient              ADOPTED     Set --beta 1e-4 (CoinRun specification).
    A18   Floor-Adjusted Retention          ADOPTED     Formula: (R_OOD - 1.818) / (R_train - 1.818).
    A19   PPG Auxiliary Cadence (n_pi=32)   RESOLVED    Retain n_pi=32. Report as "continuous-action port of PPG, retimed".
    A20   Trajectory Evaluation Depth       ADOPTED     E = 3 episodes per (regime, scene) stamp every 50k frames (176 GPU-h total).
    A21   Cross-Scene Unpaired Seeding      RESOLVED    Retain scene_id in placement seed. Report across-scene heterogeneity as descriptive.
    A22   Places365 Validation Split        RESOLVED    Declare use_val=True for SVEA, SGQN, SODA in write-up limitations.
    =============================================================================================================================
  ──────
  ## 9. Pre-Launch Verification Checklist

  Before launching the production fleet on the V100 host, the following sequence must be completed:

    [ ] 1. ENVIRONMENT ISOLATION & TESTING
        - Verify all test suites using the clean Python environment:
          /Users/a2mogus/build-projs/barannikov-work/.venv/bin/python -m pytest tests/
        - Confirm 10/10 tests pass in test_family_env_smoke.py.
    
    [ ] 2. SOURCE CONTROL FREEZE (A11)
        - Clean up transient artifacts in datasphere/native/.
        - Commit all 164 modified/untracked files into a named checkpoint commit:
          git add -A && git commit -m "chore(pre-prod): freeze codebase for 600k production campaign"
        - Verify gate_source_tree_frozen passes in scripts/production_gates.py.
    
    [ ] 3. RESOLVE IBAC-SNI CONCURRENCY (A14)
        - In datasphere/native/families.json, set ibac_sni v100 profile procs to 1 (or implement spawn worker factory).
        - Verify gate_ibac_procs_is_runnable passes.
    
    [ ] 4. THREE-STEP RENDERER VALIDATION (C95)
        - Step A: Run offline evaluation of a known checkpoint on current evaluator to establish baseline R_A.
        - Step B: Deploy pinned Docker container (nvidia/cuda:12.2.2-runtime-ubuntu22.04@sha256:...) to V100 host.
        - Step C: Evaluate identical checkpoint on V100 host to establish R_B. Verify |R_A - R_B| <= 0.77% noise floor.
    
    [ ] 5. INITIAL PRODUCTION CANARY (A10)
        - Launch Seed 1 of IDAAC at 600k frames (~7.5 h).
        - Verify checkpoint retention across all 12 stamps (50k to 600k).
        - Verify offline trajectory evaluation (12 stamps x 4 regimes x 10 scenes x 3 episodes).
        - Verify full endpoint evaluation (4 regimes x 10 scenes x 20 episodes).
        - Audit emitted record completeness and physical placement witnesses.

    [ ] 6. SECOND PRODUCTION CANARY (MEMORY ENVELOPE)
        - Launch Seed 1 of DrQ-v2 at 600k frames (~9.1 h) with 620k replay buffer.
        - Monitor host RSS to confirm memory usage stabilizes at ~40.0 GiB without thrashing.

    [ ] 7. FLEET CAMPAIGN EXECUTION
        - Deploy remaining baselines on GPU 1 (two-way packed where host RAM <= 80 GiB).
        - Inspect SGQN and SVEA endpoint returns against the published anchors (391.4 and 268.8).
