# Brief B — Do Any of These Hyperparameters Transfer to 7-DoF Manipulation?

## TL;DR
- **Yes — a defensible manipulation-specific base exists, and you already have three overlapping copies of it.** RL-ViGen's own robosuite tables (Appendix C, Tables 2/6), SECANT's robosuite table (the codebase RL-ViGen forked), and PVM-Robotics' DrQ-v2-on-Panda config independently converge on the same house style: γ=0.99, action_repeat=1, frame-stack 3, replay ≈1e5, batch 256–512, lr 1e-4, n-step 3. Adopt that as one uniform base **(option c)** and layer **(option d)** on 4 knobs that are currently silently miscalibrated.
- **The 10× learning-rate split is SERIOUS, not second-order** — it is the single biggest threat to interpretability, because it lands hardest on exactly the DDPG/DrQ-v2-family arms that are most learning-rate-fragile, while leaving the SAC-family arms (where 1e-3 is canonical) roughly intact — so it confounds the generalization gap along algorithm-family lines.
- **Collapse the discount to γ=0.99 everywhere** (drop the on-policy 0.999). A 500-step dense-reward, action_repeat=1 horizon has effective horizon 1/(1−0.99)=100; Tessler & Mannor's Reward-Tweaking study found practical algorithms degrade once the effective planning horizon exceeds ~100 (γ>0.99). γ=0.999 (horizon 1000) is inherited from Procgen's ~1000-step episodes and is wrong here.

## Key Findings

1. **A manipulation base is well-attested and internally consistent across three independent primary sources.** RL-ViGen's robosuite tables were literally built for five of your twelve arms (drqv2, svea, sgqn, curl, drq). SECANT (the upstream) and PVM-Robotics corroborate the same values on Panda Door/Lift. This makes option (c) concrete and low-risk. **[VERIFIED]**
2. **The paper's replay buffer = int(1e7) is not a RAM tensor.** RL-ViGen inherits DrQ-v2's disk-backed replay (one `.npz` per episode on disk; an in-RAM `IterableDataset` capped at `max_size//num_workers`), so a large nominal cap is feasible; the literal integer lives in the YAML (unreadable this session). Your 1e5 choice is fine — it matches SECANT's robosuite replay of 100K exactly. **[VERIFIED architecture / UNVERIFIED literal integer]**
3. **Discount, n-step, replay size, and UTD are all defensible as-is or with a one-line change**; the real damage is concentrated in learning rate, the PPO minibatch, discount incoherence, the entropy coefficient, exploration-schedule scaling, and SGQN's aux-lr default.
4. **The entropy-coefficient question has a clean published answer.** For continuous control the entropy bonus shows no benefit, and the standard continuous-control PPO convention is entropy coef = 0.0. The sibling project that set it to 0.0 was right.

## Details

### §1 — What visual RL on robosuite/manipulation actually uses

**The three precedent tables (all primary sources).**

*RL-ViGen Appendix C (arXiv 2307.10224 NeurIPS 2023 supplement, Tables 2 & 6) — full text read [VERIFIED]:*
- **Table 2 (common):** Input 84×84; γ=0.99; Replay Buffer size **int(1e7)**; Feature dim **DrQ(v2),CURL: 50, otherwise 256**; Action repeat **Robosuite: 1, otherwise 2**; N-step **DrQ: 1, otherwise 3**; Adam; Hidden dim 1024; Frame stack 3.
- **Table 6 (robosuite):** Training Frames **Door int(6e5), Lift int(8e5)**, TwoArmPegInhole int(8e5); Learning Rate **Door 1e-4 (all)**, **Lift: "DrQ(v2), CURL: 1e-4, otherwise: 8e-5"**, TwoArmPegInhole "SGQN: 1e-4, otherwise: 8e-5"; Level **Door Easy, Lift Medium**; SGQN quantile **Door 0.9, Lift 0.9** (TwoArmPegInhole 0.87); SGQN critic weight **Door 0.7, Lift 0.7** (TwoArmPegInhole 0.7); SGQN aux lr **Door 8e-5, Lift 8e-5** (TwoArmPegInhole 8e-5).
- Governing rule, verbatim: *"We use the same hyper-parameters as the original papers and perform a small-scale grid search to achieve better performance of certain algorithms."*
- Note (from the cross-benchmark check): SGQN aux lr = **8e-5 is used uniformly across every RL-ViGen benchmark** — Table 3 (CARLA), Table 4 (Habitat), Table 5 (Adroit) and Table 6 (Robosuite) all list "SGQN aux lr 8e-5." This strengthens the conclusion that 8e-5 — not the 0.3 constructor default — is the intended value. **[VERIFIED]**

*SECANT (Fan et al., ICML 2021; arXiv 2106.09678, Appendix B.2 table) — table cell read [VERIFIED]:* For Robosuite (9×168×168 input, episode length **500**, training steps **800K**): Stacked frames 3; **γ 0.99**; **SAC replay buffer size 100K**; **SAC batch size 512**; Adam; **Actor lr 1e-4 (Peg-in-hole), 1e-3 otherwise**; **Critic lr 1e-4**; **log α lr 1e-4 (Peg), 1e-3 otherwise**; **Critic target update frequency 4**; Random cropping padding 8. SECANT uses "the Franka Panda robot model with operational space control … task-specific dense reward" — the exact setting of your benchmark.

*DrQ-v2 on Meta-World (arXiv 2203.12677, Table 10) [VERIFIED]:* replay **100K–400K**; **action repeat 2**; frame stack 3; seed frames 4000; exploration steps 2000; **n-step 3**; batch 256; **γ 0.99**; Adam; **lr 1e-4**; update freq 2; **τ 0.01**; feature dim 50; hidden 1024; stddev clip 0.3; **schedule linear(1.0,0.1,500000)**.

*PVM-Robotics (github.com/Yingdong-Hu/PVM-Robotics, README run commands) [VERIFIED]:* DrQ-v2 on `panda_door`/`panda_lift`: **replay_buffer_size=500000, batch_size=512, num_seed_frames=4000**.

**Is there a distinct manipulation house style vs DMControl?** Yes, mildly. Three consistent deltas from the DMControl DrQ-v2 default: (i) **action_repeat=1** (RL-ViGen robosuite; SEAR on Franka-Kitchen; Plan-Seq-Learn; ReinforceGen) vs 2 on DMC; (ii) **larger batch (512)** in the SECANT/PVM-Robotics manipulation lineage vs 256 on DMC; (iii) **smaller replay (1e5–5e5)** driven by RAM, with multiple papers reporting no measured loss (SEAR: 2.5e5, "we did not see any performance decrease during preliminary experiments when reducing the replay buffer"; PSL: 750K). Discount stays 0.99 across essentially every source. **[VERIFIED]**

**Discount, specifically.** With a 500-step episode, dense shaped reward, no early termination and action_repeat=1, the effective horizon at γ=0.99 is 1/(1−0.99)=100 steps. Tessler & Mannor, "Reward Tweaking" (arXiv 2002.03327), report in Section 6.2.2 that "the baseline behaves best at γ≈0.99 … it fails when the effective planning horizon increases above 100 (γ>0.99)," and frame the general motivation (abstract, verbatim) as: "deep reinforcement learning algorithms tend to become unstable when the effective planning horizon is long … recent works refer to γ as a hyper-parameter." Practitioner guidance converges on γ∈[0.98,0.995] for control, γ=0.99 for episodic short-horizon tasks. **Verdict: γ=0.99 is correct; γ=0.999 (effective horizon 1000, inherited from Procgen's ~1000-step episodes) overshoots a 500-step horizon and adds variance for the on-policy arms. Collapse to 0.99 uniformly.** **[VERIFIED reasoning; the γ>0.99 degradation claim is from Tessler & Mannor §6.2.2 on a non-manipulation task — REPORTED for dense manipulation specifically]**

**n-step.** DrQ-v2 is *designed* with n=3; Cetin et al. (ICML 2022) attribute part of DrQ-v2's advantage to n-step returns stabilizing TD-learning under the "visual deadly triad." Fedus et al. (2020) found "uncorrected n-step returns are uniquely beneficial" when sifting a larger buffer (Atari/Q-learning). RL-ViGen already treats n-step as environment-dependent (n=1 for CARLA/Habitat, n=3 for robosuite), so imposing n=3 on the 1-step-canonical methods (DrQ, SVEA, SODA, SGQN, RAD, CURL, ALDA) for robosuite **is the benchmark's own documented choice and is defensible**. Keep n=3. **[VERIFIED that RL-ViGen chooses n=3 for robosuite; REPORTED that it is net-neutral-to-positive on dense manipulation for the non-DrQ-v2 methods — no head-to-head robosuite ablation exists in the literature searched.]**

### §2 — Sensitivity: which knobs actually matter

**Published sensitivity/robustness literature (what each measures, and its transfer risk):**
- **Adkins, Bowling & White, "A Method for Evaluating Hyperparameter Sensitivity in RL" (NeurIPS 2024, arXiv 2412.07165):** proposes a formal *hyperparameter-sensitivity metric*, demonstrated on **normalization variants of PPO**. Headline: "several algorithmic performance improvements may in fact be a result of an increased reliance on hyperparameter tuning." Directly relevant to your on-policy arms; not pixel-manipulation. **[VERIFIED abstract]**
- **Obando-Ceron, Araújo, Courville & Castro, "On the consistency of hyper-parameter selection in value-based deep RL" (RLC 2024, arXiv 2406.17523):** introduces a consistency/reliability score; goal is to "establish which hyper-parameters are most critical to tune … and which tunings remain consistent across training regimes." **Value-based (DQN-family), not continuous control** — transfer to your DDPG/SAC arms is itself uncertain. **[VERIFIED]**
- **Eimer, Lindauer & Raileanu, "Hyperparameters in RL and How to Tune Them" (ICML 2023):** even simple random search over ~10 runs can match best-of-125-seed sweeps, and HPO protocol/budget must be reported for a fair comparison. **[VERIFIED]**
- **Andrychowicz et al., "What Matters in On-Policy RL" (ICLR 2021):** the definitive on-policy knob study (see entropy, §4).
- **Fedus et al., "Revisiting Fundamentals of Experience Replay" (ICML 2020):** replay capacity "substantially increases the performance of certain algorithms while leaving others unaffected"; n-step returns benefit most from larger capacity. **[VERIFIED]**
- **Nikishin et al. primacy bias (ICML 2022) / D'Oro et al. scaled replay ratio:** performance collapse at *high* UTD (8–16) without resets. Your UTD is 0.5. Not a live risk. **[VERIFIED]**

**Ranked sensitivity list (most-costly-first). Marked [MEASURED] where an ablation supports the rank, [INFERRED] otherwise.**

1. **Learning-rate 10× split (some arms 1e-4, rad/soda/alda 1e-3) — SERIOUS.** [MEASURED, indirectly] The cost is *asymmetric across algorithm families*, which is what makes it corrosive to a comparison whose whole point is cross-arm comparability. SAC-family agents are robust to lr∈[3e-4,1e-3] (indeed SECANT's own robosuite config uses actor/critic lr **1e-3** for Door/Lift), so rad/soda at 1e-3 are near a defensible SAC value. But DDPG/DrQ-v2-family agents are markedly more lr-fragile: as Alfred et al.'s SAC-vs-DDPG comparison (IEEE Access) puts it, DDPG has "intrinsic drawbacks, such as unstable training, Q-value overestimation, brittle convergence, and hyperparameter sensitivity … Unlike DDPG, which utilizes only one Q-network in the critic, SAC utilizes two Q-networks … which guarantees its training stability." So if ALDA is DDPG/DrQ-v2-derived, 1e-3 is risky for it specifically. **Fix and make explicit rather than silent.**
2. **PPO family updating on 8-sample minibatches (num_envs 1 × num_steps 256, num_mini_batch 32) + on-policy vs off-policy budget mismatch — SERIOUS.** [INFERRED] A minibatch of 8 gives extremely high-variance policy-gradient estimates; combined with num_envs=1 this is far outside any published PPG/IDAAC regime. This is a bigger threat to the four on-policy arms than any single continuous-control knob.
3. **Discount incoherence (on-policy 0.999 vs off-policy 0.99) — MODERATE-SERIOUS.** [MEASURED, adjacent domains] Higher γ slows convergence and adds variance; 0.999 overshoots the 500-step horizon.
4. **SGQN aux-lr = 0.3 (RL-ViGen constructor default) vs canonical 3e-4 vs RL-ViGen's own robosuite value 8e-5 — SERIOUS *for SGQN specifically*.** [INFERRED] A ~3750× (vs the paper's 8e-5) / 1000× (vs canonical 3e-4) inflated auxiliary learning rate would cripple the saliency-guided auxiliary objective — and SGQN is precisely the augmentation method expected to top the generalization ranking (RL-ViGen reports augmentation methods at ~240–305 on Robo-EASY vs DrQ-v2/DrQ/CURL near 48–59). The wrong value here can invert your headline result. **Use 8e-5** (RL-ViGen's robosuite table, and its uniform value across all four benchmarks).
5. **Exploration schedule not rescaled — MODERATE.** [INFERRED] DrQ-v2's `linear(1.0,0.1,500000)` is its *medium* tier, annealing σ from 1.0→0.1 over 500K env steps. In DrQ-v2's 3.1M-frame DMC regime the anneal completes at ~16% of training, so the agent spends 84% of training near σ=0.1. At your 500K-frame budget with action_repeat=1, the anneal completes exactly at the end of training, so the DDPG-family arms **never train under low-noise conditions** — final policies are evaluated having only ever acted with substantial exploration noise. Principled fix to preserve the 16% fraction: `linear(1.0,0.1,80000)`.
6. **Entropy coefficient mis-set for continuous action — MODERATE (PPO arms).** [MEASURED] See §4.
7. **n-step=3 on 1-step-canonical methods — SECOND-ORDER.** [INFERRED] It is RL-ViGen's own robosuite choice; defensible.
8. **Replay capacity 1e5 — SECOND-ORDER.** [MEASURED, adjacent] Equals SECANT's robosuite value and sits in the 1e5–4e5 band DrQ-v2 used on Meta-World; multiple papers report no loss shrinking to 2.5e5. At a 500K budget it holds the most-recent 20% (SECANT held ~12.5% at 800K). Not a priority.
9. **UTD 0.5 (update_every_frames 2) — SECOND-ORDER / safe.** [MEASURED] Well below the primacy-bias danger zone; no resets needed.

**How much does a 10× learning-rate error cost — fatal / serious / second-order?** **SERIOUS.** Not fatal (1e-3 does not categorically diverge a pixel agent — SECANT ran robosuite at 1e-3), but serious because the harm is algorithm-family-correlated and therefore *confounds the very quantity you are measuring* (the cross-arm generalization gap).

### §3 — The fairness question as methodology

Major multi-algorithm RL benchmarks converge on one norm: **equal tuning budget per method, reported explicitly.** Yu et al.'s MAPPO benchmark states its results are fair only "given access to equally sized compute budgets for hyperparameter optimization"; PyHopper frames the multi-method use case as "not tuning the hyperparameters of each baseline method with a similar budget would introduce a hidden bias." Eimer et al. (ICML 2023) make protocol reporting a requirement. There is no single published scalar for "bias from a shared config tuned around one method," but the qualitative finding is unanimous: a shared base optimized for one arm systematically advantages that arm. **[VERIFIED]**

**Equal frames vs equal gradient steps vs equal wall-clock.** Under your fixed frame budget the off-policy arms take 1 update / 2 frames (UTD 0.5) while the PPO arms take epochs×minibatches per 256-frame rollout — very different gradient-step counts for the same frames. Benchmarks that mix on- and off-policy methods (e.g. the MAPPO study) normalize by *equalized HPO budget* and report learning curves in both step-count and wall-clock, rather than pretending equal frames = equal compute. For your purpose (a *generalization gap* = train-minus-holdout, computed within each arm) the frame budget is a defensible controlled variable **provided each arm is actually converging within it** — which the 8-sample PPO minibatch and the un-annealed exploration noise put in doubt for specific arms.

**Is a shared base uninterpretable?** A *single* shared base tuned for DrQ-v2 (option a) is defensible only as a stated limitation for the five RL-ViGen-native arms and is actively misleading for the PPO arms and for SGQN (whose aux-lr default is broken). It is not fatal to interpretability *if* the family-correlated defects (items 1–6 above) are fixed. Left unfixed, the comparison is uninterpretable along algorithm-family lines.

### §4 — The cheapest defensible rule, and the entropy coefficient

**Smallest set of knobs that MUST be set per-method (with a source to map from):**
- **Learning rate:** DrQ-v2/DDPG-family (drqv2, drq, svea, sgqn, curl, alda) → **1e-4** (RL-ViGen Table 6 Door value, and DrQ-v2 canonical); SAC-family (rad, soda) → their canonical (SECANT ran robosuite SAC at 1e-3; 3e-4 is the safe SAC default). Set explicitly, killing the silent split.
- **SGQN aux-lr → 8e-5**, quantile 0.9, critic weight 0.7 (RL-ViGen Table 6, verbatim).
- **Entropy coefficient (PPO arms) → 0.0** (see below).
- **PPO minibatch:** raise the effective minibatch by lowering `num_mini_batch` (256/8 → e.g. num_mini_batch=4 gives 64-sample minibatches) or accumulate multiple rollouts before an update.
- **Discount → 0.99** uniformly.

**Entropy coefficient — concrete answer.** Procgen's 0.01 is tuned for a 15-way categorical action distribution; your action space is a 7-D Gaussian whose differential entropy sums over dimensions and is unbounded (can go negative), so the 0.01 magnitude is not transferable. The published continuous-control evidence:
- **Andrychowicz et al. (arXiv 2006.05990, ICLR 2021)** "overall find no evidence that the entropy term improves performance on continuous control environments" — pinned to **decision C13, figures 76 and 77** of "What Matters in On-Policy RL." Corroborated by Gan et al. (OpenReview 39JM3A3KS3): PPO "is indifferent to the entropy bonus … as reported in Andrychowicz et al. (2020a)." **[VERIFIED]**
- **Standard continuous-control PPO convention is entropy coef = 0.0**: the Kostrikov reference implementation used by many PPG/IDAAC-lineage works sets **Entropy coef = 0 for MuJoCo** (vs 0.01 for Atari); SB3's PPO defaults `ent_coef=0.0`. (CleanRL's *discrete* PPO uses 0.01; the continuous/MuJoCo lineage does not.) **[VERIFIED]**
- **The sibling project that set entropy coef = 0.0 on the "differential entropy is unbounded" reasoning was correct.** Optionally, if exploration collapse appears, the principled alternative is SAC-style target-entropy control (−dim(A) = −7), but that is not standard for PPO and adds a knob; do not adopt it by default.

### §5–6 — Paper↔code check on RL-ViGen (where cheap)

A dedicated code-audit sub-pass read `train.py` and `replay_buffer.py`, but GitHub blocked automated access to the `cfgs/` and `algos/` directories and to raw file URLs, so the literal YAML/constructor values could not be quoted. Reporting honestly:

- **Replay buffer 1e7 (paper) vs code:** `train.py` builds the buffer via `make_replay_loader(self.work_dir / 'buffer', self.cfg.replay_buffer_size, self.cfg.batch_size, self.cfg.replay_buffer_num_workers, self.cfg.save_snapshot, self.cfg.nstep, self.cfg.discount)`; `replay_buffer.py` stores each episode as an on-disk `.npz` and keeps only `max_size // num_workers` transitions in RAM (evicting oldest when `eps_len + size > max_size`). The base Hydra config is `cfgs/svea_config.yaml` (declared `@hydra.main(config_path='cfgs', config_name='svea_config')`), and the agent is built by `hydra.utils.instantiate(cfg)`. **So int(1e7) is a disk-backed nominal cap, not a single RAM tensor — the "physically impossible" framing is resolved.** The literal integer in the YAML: **[UNVERIFIED — could not open `cfgs/svea_config.yaml`].** Searches run: "gemcollector RL-ViGen cfgs config.yaml replay_buffer_size", "RL-ViGen svea_config.yaml replay_buffer_size", direct raw.githubusercontent fetch (blocked by robots).
- **SGQN aux lr 8e-5 (paper) vs 0.3 (RL-ViGen constructor default) vs 3e-4 (canonical):** **[UNVERIFIED in code]** — `algos/sgqn.py` was not accessible. Paper Table 6 value is 8e-5 (and 8e-5 uniformly across CARLA/Habitat/Adroit/Robosuite); the 0.3 constructor default is a local finding treated as given. Searches run: "RL-ViGen algos sgqn.py aux_lr", "RL-ViGen sgqn quantile critic weight".
- **SGQN quantile/critic weight:** paper 0.9 / 0.7 (Door & Lift) **[VERIFIED in paper]**; code default **[UNVERIFIED]**.
- **Feature dim 50 vs 256:** paper Table 2 = 50 for DrQ(v2)/CURL, 256 otherwise **[VERIFIED in paper]**; code **[UNVERIFIED]**. Whether the rad/soda builders accept an `lr` key at all **[UNVERIFIED — agent files inaccessible]**; this is the mechanism behind the measured 10× split and should be confirmed by opening the rad/soda constructor signatures in a local clone.
- **Learning rate per task:** paper Table 6 = Door 1e-4 all; Lift "DrQ(v2), CURL: 1e-4, otherwise: 8e-5" **[VERIFIED in paper]**.
- **Training frames:** paper Door 6e5, Lift 8e5 **[VERIFIED in paper]**; code literal **[UNVERIFIED]** (`train.py` reads `self.cfg.num_train_frames`).

### §7 — Open questions the literature does not answer

1. **No head-to-head ablation of n-step (1 vs 3) for SVEA/SODA/SGQN/RAD/CURL on dense-reward robosuite** exists in the sources searched. Whether n=3 helps or merely doesn't hurt the non-DrQ-v2 methods on Panda Door/Lift is unmeasured. (Searched: "n-step manipulation dense reward", "n-step DrQ SVEA robosuite ablation".)
2. **No published quantification of the bias magnitude** from a shared config tuned around one arm — only the unanimous qualitative finding. A scalar effect size does not exist in the literature searched.
3. **ALDA's base learner** (DDPG/DrQ-v2 vs SAC) determines whether 1e-3 is risky or safe for it; this is a repo-internal fact, not in the literature.
4. **Whether the RL-ViGen robosuite reward scale interacts with n-step/discount** (SECANT and VRL3 both rescale manipulation rewards; RL-ViGen's robosuite reward magnitude was not documented in the sources read).
5. **The literal RL-ViGen YAML/constructor values** (replay size, SGQN aux-lr, feature dim, per-agent lr-key acceptance) remain unconfirmed from code — must be read from a local clone.

## Manipulation-specific baseline table (per-value provenance)

| Hyperparameter | Recommended | Source of value | Evidence |
|---|---|---|---|
| Discount γ | **0.99** (all arms) | RL-ViGen T2, SECANT, DrQ-v2 MW, PVM-Robotics all agree | [VERIFIED] |
| Action repeat | **1** | RL-ViGen T2 (Robosuite:1); SEAR/PSL on Franka | [VERIFIED] |
| Frame stack | **3** | all three precedents | [VERIFIED] |
| Replay capacity | **1e5** (keep) | = SECANT robosuite 100K; DrQ-v2 MW 1e5–4e5 | [VERIFIED] |
| Batch size | 256 (or 512) | DrQ-v2 MW 256; SECANT/PVM-Robotics 512 | [VERIFIED] |
| n-step | **3** | RL-ViGen T2 (robosuite); DrQ-v2 | [VERIFIED for RL-ViGen] |
| Learning rate (DrQ-v2/DDPG family) | **1e-4** | RL-ViGen T6 Door; DrQ-v2 canonical | [VERIFIED] |
| Learning rate (SAC family: rad/soda) | 3e-4 (or 1e-3) | SECANT robosuite SAC 1e-3; SAC default 3e-4 | [VERIFIED range] |
| τ (critic target) | 0.01 | DrQ-v2 MW | [VERIFIED] |
| Feature dim | 50 (DrQ-v2/CURL) / 256 (else) | RL-ViGen T2 | [VERIFIED paper] |
| Hidden dim | 1024 | RL-ViGen T2; DrQ-v2 | [VERIFIED] |
| Exploration schedule | **linear(1.0,0.1,80000)** (rescaled) | derived from DrQ-v2 medium tier | [INFERRED — no source for the rescaled string] |
| SGQN aux-lr / quantile / critic wt | **8e-5 / 0.9 / 0.7** | RL-ViGen T6 (Door/Lift) | [VERIFIED paper] |
| Training frames | Door 6e5, Lift 8e5 | RL-ViGen T6 | [VERIFIED paper] |
| Entropy coef (PPO arms) | **0.0** | Kostrikov MuJoCo default; SB3 default; Andrychowicz C13 | [VERIFIED] |
| PPO discount / GAE λ | 0.99 / 0.95 | collapse from 0.999; standard | [VERIFIED convention] |
| PPO minibatch | ≥64 (num_mini_batch=4) | derived fix — no direct robosuite source | [INFERRED] |

*Cells with no source: the rescaled exploration string and the PPO minibatch value are engineering derivations, not literature values — flagged as such.*

## Recommendations

**Primary recommendation: HYBRID = (c) a uniform manipulation base + (d) on 4 high-sensitivity knobs.** Reasoning quotable in a write-up: *"We adopt RL-ViGen's own robosuite hyperparameters (Appendix C, Tables 2 and 6) as a single manipulation-calibrated base applied uniformly to all twelve arms — a base that five of the twelve were built for and that SECANT (the upstream codebase) and PVM-Robotics independently corroborate on Panda Door/Lift. On top of this base we correct four family-correlated defects that would otherwise confound a cross-arm generalization comparison: the 10× learning-rate split, the discount incoherence, the collapsed PPO minibatch, and the continuous-control entropy coefficient."*

**What it costs:** a handful of per-arm config lines and one explicit statement that the base is manipulation-calibrated rather than per-method-optimal. **What it buys:** every arm on one base with three independent precedents, with the specific silently-wrong defaults removed — a comparison whose differences are attributable to algorithms rather than to configuration accidents.

**Staged, concrete next steps:**
1. **Before any T4 run (zero extra compute):** set γ=0.99 for all twelve; entropy coef=0.0 for the four PPO arms; SGQN aux-lr=8e-5 (+ quantile 0.9, critic weight 0.7); fix the PPO minibatch (num_mini_batch=4 → 64-sample minibatches, or accumulate 4 rollouts). Open the rad/soda/alda constructors locally, confirm whether `lr` is a recognized key, and set lr explicitly (1e-4 DrQ-v2/DDPG-family; 3e-4 or the documented SAC value for rad/soda), eliminating the silent 10× split.
2. **One cheap ablation (2 arms × 2 seeds) to de-risk the exploration schedule:** run DrQ-v2 and one augmentation arm at `linear(1.0,0.1,500000)` vs the rescaled `linear(1.0,0.1,80000)` on Door. ~4 runs ≈ 7 GPU-hours on the T4 (500k frames ≈ 1.8 h pure env stepping each).
3. **Sanity gate before the full matrix:** confirm the uniform-random control scores near the reward floor and that the augmentation arms exceed DrQ-v2/DrQ/CURL on Robo-EASY, reproducing RL-ViGen's ~240–305 vs ~48–59 ordering. If SGQN does *not* lead the augmentation group, suspect the aux-lr default is still wrong.

**Benchmarks/thresholds that change the recommendation:**
- If opening the rad/soda constructors shows they are DDPG/DrQ-v2-based (not SAC) → their 1e-3 is dangerous; escalate the lr fix to top priority and set them to 1e-4.
- If the schedule ablation shows >1 SD final-return gap between the two schedules → rescaling becomes mandatory for all DDPG-family arms, not optional.
- If the PPO arms fail to converge within 500K even after the minibatch fix → equal-frames is not a fair budget for them; report on-policy arms under equalized *gradient-step* or wall-clock budget and flag it, per the MAPPO/PyHopper norm.

## Caveats
- The literal RL-ViGen YAML/constructor values (replay size, SGQN aux-lr, feature dim, per-agent lr-key acceptance) are **[UNVERIFIED from code]** — GitHub blocked directory/raw access this session. They must be read from a local clone before finalizing configs. All RL-ViGen *paper* table values are **[VERIFIED]** from the NeurIPS supplement.
- The dense-manipulation-specific claims for discount and n-step rest on adjacent-domain ablations (DMControl, Atari, general control), not on a Panda Door/Lift ablation, which does not appear to exist. Marked [REPORTED]/[INFERRED] accordingly. The Tessler & Mannor "fails above horizon 100" quote is from that paper's §6.2.2 experiments on a finite-horizon control task, not on manipulation.
- SECANT's robosuite input is 168×168 (yours is 84×84) and it is SAC-based, so its lr and batch transfer with mild caution; its γ, replay size, frame stack, episode length (500) and action_repeat transfer cleanly.
- ALDA here is arXiv 2410.07441 (ICML 2025), not the unrelated 2001.01046; its base learner determines its lr sensitivity and is a repo-internal open item.
- The one firm code-level finding is that the replay buffer is disk-backed (`.npz` per episode) with in-RAM eviction at `max_size//num_workers`; this is why a nominal 1e7 setting is not a literal RAM allocation.