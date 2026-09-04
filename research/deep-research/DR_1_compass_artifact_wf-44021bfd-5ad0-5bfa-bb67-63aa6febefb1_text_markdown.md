# Brief A — RL-ViGen (NeurIPS 2023, arXiv:2307.10224) robosuite backend: audit against primary sources

**Bottom line:** For the robosuite backend, "treat RL-ViGen as the benchmark's definition" is not a single answer — *paper-RL-ViGen* and *code-RL-ViGen* are demonstrably different experiments, and every one of the anomalies you flagged is a real paper-vs-code (or paper-vs-canonical) gap. The published tables (which I fully verified against the NeurIPS supplementary PDF) say SGQN uses **aux_lr = 8e-5, quantile = 0.9, critic weight = 0.7** for Door and Lift; canonical SGQN uses **quantile 0.95 / aux_lr 3e-4**; and the value your scoping pass read out of `algos/sgqn.py` (**0.3 / 0.95**) matches *neither*. **I recommend fixing SGQN's `aux_lr` to `8e-5`** because that is the number attached to the returns your project compares against. However — and this is the single most important caveat in this brief — **I could not retrieve a single line of RL-ViGen's actual source code** (GitHub blob/raw/tree, jsDelivr, Software Heritage, and code-search mirrors were all robots-blocked or never surfaced in search, for both my own fetches and a dedicated subagent). So the *code-side* half of every disagreement below is transcribed from your scoping pass and marked **UNVERIFIED-FROM-SOURCE**; the *paper-side* half is verified verbatim.

## TL;DR
- **The tables are confirmed; the code is not reachable.** I verified Table 2 and Table 6 of the NeurIPS supplementary word-for-word — every cell your scoping pass reported is correct. I could **not** open `algos/sgqn.py`, `cfgs/`, or any repo file, so the shipped defaults (aux_lr 0.3, quantile 0.95, hardcoded critic weight 0.5, action_repeat 2, replay 1e5, drq nstep 3) remain **UNVERIFIED against source** and rest solely on your project's reading.
- **SGQN has three wrong knobs, and the fix target is 8e-5 for aux_lr, 0.9 for quantile, 0.7 for critic weight** — the paper's Door/Lift values — because those are the numbers behind the returns you benchmark against. Canonical SGQN (3e-4 / 0.95) is the wrong target here precisely *because* RL-ViGen deliberately re-tuned. The shipped 0.3 aux_lr default is almost certainly a defect (a leftover, not a documented re-tune): it appears in no RL-ViGen table, is ~1000× canonical and ~3750× the paper's robosuite value, and is the same failure mode your audit was created to catch.
- **The `action_repeat` contradiction is genuine and unresolved in the paper's own framing.** Table 2 states "Action repeat — Robosuite: 1"; your project's 500k-frames-at-action_repeat=1 budget therefore matches the paper's stated Robosuite setting. If the shipped `config.yaml` really defaults to 2 with no robosuite override, that is a paper-vs-code split of a factor of two on every frame budget — but I could not confirm the code side.

## Key Findings

### 1. RL-ViGen's robosuite hyperparameter table — transcribed verbatim, per-row sourced

All rows below are quoted from the NeurIPS 2023 supplementary PDF (`proceedings.neurips.cc/paper_files/paper/2023/file/15c9f64ec172b046470d2a4d2b7669fc-Supplemental-Datasets_and_Benchmarks.pdf`), Appendix C, which is identical to Appendix C of arXiv:2307.10224v3. Your scoping pass was accurate on **every** cell.

**Table 2 (common hyper-parameters), verbatim:**
| Row | Value |
|---|---|
| Input size | 84 × 84 |
| Discount factor γ | 0.99 |
| Replay Buffer size | int(1e7) |
| Feature dim | DrQ(v2), CURL: 50, otherwise: 256 |
| Action repeat | **Robosuite: 1**, otherwise: 2 |
| N-step return | **DrQ: 1**, otherwise: 3 |
| Optimizer | Adam |
| Hidden dim | 1024 |
| Frame stack | 3 |

**Table 6 (robosuite hyper-parameters), verbatim:**
| Row | Door | Lift | TwoArmPegInHole |
|---|---|---|---|
| Training Frames | int(6e5) | int(8e5) | int(8e5) |
| Learning Rate | 1e-4 (all algos) | DrQ(v2),CURL: 1e-4, otherwise: 8e-5 | SGQN: 1e-4, otherwise: 8e-5 |
| Level | Easy | Medium | Medium |
| SGQN quantile | 0.9 | 0.9 | 0.87 |
| SGQN critic weight | 0.7 | 0.7 | 0.7 |
| SGQN aux lr | 8e-5 | 8e-5 | 8e-5 |

**Rows that are NOT published anywhere** (searched the full main paper + all six appendix tables): **batch size, target-network τ, actor/critic update ratio, exploration/`std_schedule` for robosuite, and the OSC_POSE controller gains.** For robosuite, the paper gives only the nine Table 2 rows plus the six Table 6 rows. The std_schedule is mentioned only for CARLA ("we standardized the std_schedule across all algorithms"), not robosuite. So "batch size = X for robosuite" is a *decide-and-record* item, not a *look-it-up* item.

**Cross-table note on the "8e-5 everywhere" claim.** Your scoping pass suspected SGQN aux_lr = 8e-5 also appears in the CARLA, Habitat and Adroit tables — **confirmed**: Table 3 (CARLA) SGQN aux lr 8e-5, quantile 0.9, critic weight 0.5; Table 4 (Habitat) SGQN aux lr 8e-5, quantile 0.93, critic weight 0.9; Table 5 (Adroit) SGQN aux lr 8e-5 for Hammer/Door/Pen, quantile 0.9, critic weight 0.9/0.5/0.9. So **8e-5 is RL-ViGen's universal SGQN aux-lr constant across all five environments** — a strong signal it was a deliberate benchmark-wide choice, not a per-task typo.

### 2. Verdict on SGQN's three wrong knobs

**`aux_lr` — verdict: the shipped 0.3 default is a defect; the correct benchmark value is 8e-5.**
- Three candidate values, as you found: **8e-5** (RL-ViGen paper, all robosuite tasks and indeed all five environments), **3e-4** (canonical SGQN), **0.3** (your reading of the shipped `algos/sgqn.py` default — UNVERIFIED-FROM-SOURCE, as I could not open the file).
- The case for **8e-5**: it is the value attached to Figure 19 / Table 6, i.e. the number behind the SGQN returns (257/146/142 aggregated) that your generalization-gap comparison is implicitly calibrated against. If you want your SGQN to *be* RL-ViGen's SGQN, this is the only defensible target.
- The case for **3e-4**: it is canonical, and if your thesis were "reproduce the algorithm as published by its authors" you would use it. But RL-ViGen *explicitly* re-tuned SGQN's auxiliary optimizer for its unified DrQ-v2 backbone (Appendix C: "We use the same hyper-parameters as the original papers and perform a small-scale grid search to achieve better performance of certain algorithms"). Using 3e-4 would reproduce *neither* canonical SGQN's setup (which is SAC-based with a different architecture) *nor* RL-ViGen's numbers. It is the wrong target for a benchmark faithfulness audit.
- **Recommendation: set `aux_lr = 8e-5`.** The shipped 0.3 is ~3,750× the benchmark value and ~1,000× canonical, appears in no table, and is exactly the "plausible-looking value that is silently wrong, does not crash, and does not mean anything" failure your audit exists to catch. Treat it as a defect, not a re-tune. **Caveat:** because I could not read the file, I cannot rule out that a `cfgs/` YAML or a `scripts/*.sh` flag overrides 0.3 to 8e-5 at launch — you should grep your vendored tree for `aux_lr` before concluding the running value was 0.3. "Searched: GitHub blob/raw/tree, jsDelivr CDN, Software Heritage, grep.app/Sourcegraph — all blocked; could not confirm or refute an override."

**`sgqn_quantile` — verdict: fix to 0.9 (Door and Lift).** Paper Table 6 says 0.9 for both. Canonical SGQN uses 0.95 (the DeGuV paper corroborates: SGQN "is sensitive to hyperparameter sgqn-quantile (often set to 95%–98%)"). The shipped 0.95 default (UNVERIFIED-FROM-SOURCE) happens to equal *canonical* but not *RL-ViGen-robosuite*. Since quantile directly controls how many pixels the saliency mask keeps, a 0.95-vs-0.9 gap is a real behavioral difference. Fix to **0.9** for Door/Lift to match the benchmark.

**Critic weight — verdict: fix to 0.7 (Door and Lift).** Paper Table 6 says 0.7 for all three robosuite tasks. Your project reportedly hardcodes 0.5. Note 0.5 is the *CARLA* value (Table 3) — so if the project applied 0.5 uniformly, it imported CARLA's SGQN critic weight into robosuite. Fix to **0.7**.

**Does canonical SGQN disagree with itself (paper vs repo), like CURL/SODA/RAD?** Partially unresolvable. The canonical SGQN paper (Bertoin, Zouitine, Zouitine & Rachelson, "Look where you look! Saliency-guided Q-networks for generalization in visual Reinforcement Learning," NeurIPS 2022, arXiv:2209.09203) documents in Table 3 the SAC/SGQN hyperparameters: self-supervised-update optimizer Adam **lr = 3e-4**, quantile ρ = 0.95 (0.98 for Cartpole/Ball-in-cup), overlay augmentation. I could open the paper but **not** the `SuReLI/SGQN` code files (only the repo landing page, which confirms the DMC environment is inherited from Nicklas Hansen's DMControl-GB and the robotic env from `jangirrishabh/look-closer`). So I can confirm the canonical *paper* value is 3e-4/0.95 but **cannot verify whether SuReLI/SGQN's code matches its own paper** — searched GitHub blob/raw for `SuReLI/SGQN` train/config files, all blocked. Mark this **UNVERIFIED** either way.

### 3. The base-learner substitutions (SVEA and CURL on DrQ-v2)

**This is documented as a deliberate unification, and the numbers are reported unqualified.** The main paper (§3.1) states the entire contribution is "a unified codebase … In previous studies, different algorithms adopt distinct optimization schemes, RL baselines, and hyperparameters. For example, SRM and SVEA rely on SAC-based RL algorithms, while PIE-G utilizes a DDPG-based approach … providing a unified framework is of great importance." The README confirms "Our training code is based on DrQv2." So all baselines are re-homed onto the DrQ-v2/DDPG backbone by design, and SVEA/CURL results are reported as "SVEA" and "CURL" with no asterisk.

- **CURL's deviation IS documented** (Appendix A and Appendix F.3, verbatim): "In our implementation, we only apply a single encoder to produce visual representations instead of two polyak-averaging encoders. This alteration improves the sample efficiency of CURL." Appendix F.3 adds: "we do not utilize a target encoder and remove the update of momentum parameters." So citing RL-ViGen's rationale is defensible; you need not re-derive it.
- **SVEA's `random_overlay` substitution is NOT documented.** Appendix A's SVEA paragraph describes only the objective (Eq. 4, using un-augmented Q-values as targets); it says nothing about which augmentation RL-ViGen's SVEA uses. This is a genuine "not documented at all" item. (For context: canonical SGQN's paper states it "used a random overlay augmentation … blending together original observations with random images from the Places365 dataset … for all the methods except for RAD and DrQ," and the RL-ViGen README confirms the framework downloads Places365 for augmentation — but RL-ViGen never states SVEA's specific augmentation in prose.)

### 4. The `drq` n-step divergence

**Confirmed: Table 2 says "N-step return — DrQ: 1, otherwise: 3."** So n-step 3 is RL-ViGen's documented benchmark constant for DrQ-v2, CURL, SVEA, SGQN (four of your five inherited arms), and the *only* genuine per-arm divergence is DrQ itself: RL-ViGen documents 1-step for DrQ, canonical DrQ (Kostrikov et al. 2020) is 1-step, and your vendored `algos/drq.py` reportedly uses 3. **I could not open `algos/drq.py`** to confirm whether upstream RL-ViGen's DrQ is 1-step in code as well as in the table — searched, blocked, **UNVERIFIED-FROM-SOURCE**. But the paper is unambiguous: the intended DrQ is 1-step. If your vendored tree runs DrQ at nstep=3, that is a divergence from *both* RL-ViGen's table and canonical DrQ, and since your project has locally modified `algos/drq.py`, the divergence may be yours rather than inherited — worth checking against the pristine upstream file.

### 5. Reported robosuite numbers, and derivative-paper per-task data

**RL-ViGen's own numbers are aggregated over all three tasks — there is no per-task Door/Lift number anywhere in the paper.** The supplementary is explicit: "The aggregated return is calculated by averaging over all three tasks." Figure 19 values (verified verbatim), by difficulty:
- **Robo EASY:** SGQN 257, PIE-G 305, SRM 275, SVEA 242, DrQ-v2 48, DrQ 59, CURL 52
- **Robo MEDIUM:** SGQN 146, PIE-G 175, SRM 156, SVEA 144, DrQ-v2 52, DrQ 58, CURL 50
- **Robo HARD:** SGQN 142, PIE-G 142, SRM 64, SVEA 75, DrQ-v2 45, DrQ 55, CURL 50

(Your scoping pass had these right; note the figure's column order is SGQN/PIE-G/SRM/SVEA/DrQ-v2/**DrQ/CURL** in EASY but the bar labels reorder slightly across panels — the seven values per panel are as listed.) **Protocol:** 5 random seeds, mean ± 95% confidence interval (main paper §4). Figure 22 gives per-task sample-efficiency curves (Door 0–6e5, Lift 0–8e5, TwoArmPegInHole 0–8e5) **but with training steps normalized to (0,1)**, so there is no absolute-budget axis to read per-task asymptotes from — confirming your scoping pass. The naming inconsistency you flagged is **confirmed**: Appendix D.1.1 names the robosuite levels **Easy / Hard / Extreme**, while Figure 19 labels them **EASY / MEDIUM / HARD**. These are the same three levels under two different names in the authors' own text.

**Best available per-task Door/Lift comparison — the DeGuV paper.** "DeGuV: Depth-Guided Visual Reinforcement Learning for Generalization and Interpretability in Manipulation" (Pham, Chi, Nguyen, Huber, Cangelosi; arXiv:2509.04970v1, 2025) trains *on RL-ViGen's robosuite backend* and reports per-task episode returns (mean ± std) across train/easy/medium/hard, **3 seeds, 1,000,000 frames** (note: their re-run, SAC-based DeGuV pipeline, not RL-ViGen's own runs). Selected values from their Table I:
- **Door** — DrQv2: train 387.35 / easy 365.66 / medium 160.44 / hard 113.39; CURL: 438.12 / 436.39 / 190.40 / 135.65; SGQN: 441.61 / 440.87 / 236.71 / 126.73; SVEA: 475.82 / 464.73 / 247.97 / 256.17.
- **Lift** — DrQv2: train 242.21 / easy 17.14 / medium 0.11 / hard 0.16; CURL: 125.65 / 74.16 / 9.70 / 13.73; SGQN: 142.86 / 57.16 / 39.65 / 23.92; SVEA: 234.25 / 118.84 / 12.74 / 12.24.

Two things to take from DeGuV: (a) **Door trains to several-hundred return and Lift is much harder to generalize** (medium/hard collapse to near-zero for most methods) — consistent with your project's finding that Lift's shaped reward lets a poor policy accumulate return in-distribution while failing out-of-distribution; and (b) DeGuV independently confirms RL-ViGen's baselines are DrQv2-backbone re-implementations (they cite DrQv2 [37] as the base and CURL as contrastive add-on). I found **no derivative paper reporting a random/untrained-policy robosuite return** under RL-ViGen's protocol — your Door ≈ 1.5 / Lift ≈ 7.5 with zero successes, and the sibling reproduction, remain the only such numbers I can corroborate the *plausibility* of (a random arm under Lift's `1 − tanh(10·d)` per-step shaping would indeed accumulate small positive return without lifting). DeGuV's DrQv2 Lift medium/hard values of 0.11/0.16 are the closest published "near-floor" datapoints.

**Reward shaping — not stated in the paper.** The supplementary says only that RL-ViGen builds on SECANT's robosuite codebase; SECANT's own paper states it trained robosuite "with task-specific dense reward." RL-ViGen never states whether it uses shaped or sparse reward for Door/Lift. This is a **"not documented"** item; the SECANT lineage strongly implies **dense/shaped** (robosuite's default), which is consistent with your observation that Lift's shaped reward inflates random-policy return. Mark the shaped-reward assumption as inherited-from-SECANT-by-default, not stated by RL-ViGen.

### 6. Provenance of the vendored tree (Section 4)

- **Environment versions (documented):** INSTALLATION.md states "we have employed the 1.4.0 version of Robosuite, concurrently utilizing mujoco version 2.3.0." The supplementary corroborates: "we adopt one of the latest versions — Robosuite 1.4.0 and mujoco 2.3.0." So the *documented* working set is **robosuite 1.4.0 + mujoco 2.3.0**. Your project's pin of `mujoco==2.3.7` (to stay on the 2.x line and avoid the 3.x `tex_rgb` rename that breaks eval modes) is a reasonable within-2.x bump; **RL-ViGen documents no note about the 2.x/3.x break** — that is your finding, not theirs, and it is worth recording as an undocumented hazard.
- **SECANT lineage (confirmed as the origin of the robosuite fork):** The supplementary states plainly: "SECANT [12] previously employed Robosuite for generalization testing. **Building on its codebase**, we adopt … Robosuite 1.4.0 and mujoco 2.3.0 … Meanwhile, we also introduce a range of new classes of visual generalization." The README's acknowledgements thank "the codebase of VRL3, DMC-GB, SECANT, and kyoran." SECANT (Fan et al., ICML 2021) shipped its own modified robosuite: its install instructions use `pip install git+git://github.com/wangguanzhi/robosuite.git` ("robosuite adapted for SECANT"), and `secant.envs.robosuite.make_robosuite(task="Door", mode="train", scene_id=0)` shows SECANT already carried the **task/mode/scene_id** interface and Panda + operational-space-control setup that RL-ViGen inherits. **So much of the 761-file divergence your project measured against PyPI robosuite is very likely SECANT's visual-randomization fork (`wangguanzhi/robosuite`), with RL-ViGen's "new classes of visual generalization" layered on top.** The `Custom01..Custom40` texture names that resolve only through the fork's XML are consistent with this SECANT-derived visual-randomization machinery. **What exactly RL-ViGen changed on top of SECANT is NOT documented** beyond the one-sentence "we also introduce a range of new classes of visual generalization"; I could not open the `third_party/robosuite` tree to diff it. This is the single richest thread for a follow-up: diff your vendored `third_party/robosuite` against `wangguanzhi/robosuite` (SECANT's fork), not against PyPI robosuite 1.4.0 — the latter comparison over-counts because it attributes SECANT's changes to RL-ViGen.
- **Known-broken paths / parallel training:** Issue #6 "About parallel training" (opened by RayYoh, 20 Oct 2023) is confirmed to exist and be directly on-point, but **its body text and any author reply were not retrievable** — the GitHub issue page is robots-blocked and the text never surfaced in search snippets. I therefore **cannot confirm whether a working parallel/subprocess path exists**; your `num_envs=1` workaround (GlobalHydra.clear() on every construction + GL-backend-before-mujoco-import) stands as the safe assumption, and nothing I found contradicts it. "Searched: issues list (visible), issue #6 direct URL (blocked), Google/Bing cache (not surfaced) — could not read the thread."

## Details

### Consolidated list of paper-vs-code (and paper-vs-canonical) disagreements for the robosuite backend

This is the highest-leverage section. Each row states the **paper value (verified)**, the **code value (from your scoping pass, UNVERIFIED-FROM-SOURCE)**, and the canonical value where relevant.

| Knob | Paper (verified, Table 2/6) | Shipped code (per your audit; I could not open the file) | Canonical | Disagreement type |
|---|---|---|---|---|
| SGQN aux_lr | 8e-5 (Door, Lift) | 0.3 default in `algos/sgqn.py` | 3e-4 | **Three-way; code matches nothing** |
| SGQN quantile | 0.9 (Door, Lift) | 0.95 default | 0.95 | Code matches canonical, not benchmark |
| SGQN critic weight | 0.7 (Door, Lift) | 0.5 hardcoded (project) | n/a | Code matches CARLA value, not robosuite |
| Action repeat | Robosuite: 1 | config.yaml default 2, no robosuite override | — | **Factor-of-2 on frame budget** |
| N-step (DrQ) | 1 | 3 (in project's modified drq.py) | 1 | Code matches neither paper nor canonical |
| N-step (others) | 3 | (assumed 3) | varies | Consistent if code = 3 |
| Replay buffer | int(1e7) | 1e5 (project shared capacity) | — | **100× smaller in project** |
| Feature dim | 50 (DrQ-v2/CURL), 256 (SVEA/SGQN/others) | possibly one dim applied uniformly | — | If uniform, SVEA/SGQN bottleneck wrong |

**Interpretation.** Rows 1–3 mean SGQN is the worst-affected arm: on your reading, all three of its distinctive knobs are set to values that are individually plausible (0.3 looks like a default, 0.95 is canonical, 0.5 is *a* value from the paper) but none of which is the robosuite value behind the published SGQN curve. Rows 4 and 7 are the ones that most distort the *comparison across arms*: a 100×-smaller replay buffer (1e5 vs 1e7) and a possibly-uniform feature dim would put SVEA and SGQN at a fraction of their intended representational bottleneck, and action_repeat=2-vs-1 halves or doubles the effective interaction budget. **The replay-capacity gap deserves emphasis:** RL-ViGen documents 1e7, which at 500k frames is effectively "never evict" — a project using 1e5 is running a materially different (much more on-policy) algorithm for the augmentation-heavy arms. This is a defensible deviation *if recorded*, but it is a deviation from the benchmark's definition, not a neutral implementation detail.

### Where I disagree with / cannot corroborate your audit documents

- Your `PREMISES.md`/`FAITHFULNESS.md` framing that RL-ViGen can be treated as "the benchmark's definition" needs the paper-vs-code split made explicit: **there is no single RL-ViGen.** The paper defines one experiment (aux_lr 8e-5, action_repeat 1, replay 1e7, DrQ 1-step); the shipped code, on your reading, defines another. Every "leave it alone, it's the benchmark" decision should specify *which* RL-ViGen.
- I **cannot independently confirm** the code-side values (0.3, 0.95, 0.5, action_repeat 2, replay 1e5, drq nstep 3) because the repository was unreachable. Your audit's reading is the only evidence for them; I did not find anything contradicting it, but "absence of contradiction" is not confirmation. Before shipping the one-line `aux_lr` fix, grep the vendored tree for `aux_lr`, `sgqn_quantile`, `action_repeat`, and `replay_buffer_size` to confirm no `cfgs/*.yaml` or `scripts/*.sh` override changes the running value — several of these "defaults" may be overridden at launch, which would change the verdict from "defect" to "config sets it correctly."

### What is not documented at all (decide-and-record, not look-it-up)
1. Batch size, target τ, and update ratio for robosuite (no table row exists).
2. Whether robosuite reward is shaped or sparse (SECANT lineage implies dense/shaped; RL-ViGen never says).
3. SVEA's specific augmentation in RL-ViGen (Appendix A gives only the objective).
4. Exactly what RL-ViGen changed in `third_party/robosuite` on top of SECANT's fork (one sentence: "new classes of visual generalization").
5. The mujoco 2.x/3.x break (`tex_rgb` rename) — undocumented hazard; your pin is the mitigation.
6. Whether a working parallel/subprocess env path exists (issue #6 unreadable).
7. Whether the training scene (scene 0) appears in the eval set — see below.

### Evaluation protocol (reproducible detail)
- **Scenes/trials:** "each difficulty level comprises 10 distinct scenes. We perform 10 trials for each of these scenes (100 trials in total)" (supplementary D.1.1). Main paper §4: **5 random seeds, mean ± 95% CI.**
- **Policy:** zero-shot evaluation (train in fixed scenario, evaluate in unseen scenarios); the paper describes Stage 1 train / Stage 2 zero-shot generalization (Figure 2). It does **not** explicitly state deterministic vs stochastic action selection at eval — treat as **not documented** (DrQ-v2 backbone default is deterministic/mean action at eval, which is the reasonable assumption).
- **Training scene in eval set?** The paper's three eval levels (Easy/Hard/Extreme, or EASY/MEDIUM/HARD in Fig. 19) are all described as *unseen* generalization scenarios distinct from the training scene. Your scoping pass's reading — the training scene is **not** part of any eval level — is consistent with the paper's zero-shot framing. Your project's protocol (10 scene ids, train on scene 0, evaluate 0–9) therefore *adds* an in-distribution point (scene 0) that RL-ViGen's protocol does not include in its aggregated eval — a reasonable extension for measuring the generalization gap, but note it is your design, not RL-ViGen's.

## Recommendations

**Stage 1 — ship the SGQN fixes now (they are the point of this brief).**
1. Set SGQN **`aux_lr = 8e-5`**, **`sgqn_quantile = 0.9`**, **critic weight = 0.7** for both Door and Lift. These are the paper's Door/Lift values and are the numbers behind the SGQN returns your generalization-gap comparison is calibrated against. Do this rather than reverting to canonical 3e-4/0.95, because RL-ViGen deliberately re-tuned and canonical would reproduce neither.
2. **Before committing, grep the vendored tree** for `aux_lr`, `sgqn_quantile`, and the critic-weight symbol. If a `cfgs/` YAML or launch script already overrides the Python default to the paper value, the "defect" is only in the unused default and the fix is a no-op — record that finding either way. This is the one check that separates "our runs were wrong" from "our runs were fine but the default is a trap."

**Stage 2 — resolve the two comparison-distorting knobs.**
3. **Action repeat:** adopt **1** for robosuite (matches Table 2 and your current 500k/action_repeat=1 budget). If your vendored `config.yaml` defaults to 2, add an explicit robosuite override and record that the paper's Table 2 is the authority.
4. **Replay capacity:** if compute allows, raise the shared capacity toward RL-ViGen's **1e7** for the robosuite arms (at 500k frames this is effectively "no eviction"); at minimum, record that 1e5 is a deliberate 100× deviation and re-check whether SVEA/SGQN sample efficiency is penalized. **Feature dim:** confirm SVEA/SGQN get **256** and DrQ-v2/CURL get **50**; a uniform value silently changes the representational bottleneck for the augmentation arms.

**Stage 3 — provenance, if the fork behavior matters.**
5. Diff your vendored `third_party/robosuite` against **SECANT's fork (`wangguanzhi/robosuite`)**, not against PyPI robosuite 1.4.0 — the PyPI diff over-attributes SECANT's changes to RL-ViGen. The `Custom01..Custom40` textures are almost certainly SECANT-derived visual-randomization assets.

**Benchmarks/thresholds that would change these recommendations:**
- If a grep reveals a `cfgs`/script override setting SGQN's knobs to the paper values, downgrade the `aux_lr` finding from "defect that corrupted runs" to "harmless unused default" — no re-runs needed.
- If your DrQ arm's `nstep` is 3 and you want RL-ViGen-faithful DrQ, change it to **1** (matches both the table and canonical); if you want a self-consistent internal benchmark, keeping 3 is defensible but must be recorded as a divergence.
- If you can recover issue #6's contents or an authenticated repo read, revisit the parallel-training constraint and the code-side values I had to leave UNVERIFIED.

## Caveats
- **The dominant caveat: no RL-ViGen source code was retrievable.** GitHub blob/tree/raw, jsDelivr CDN, Software Heritage, and code-search mirrors were all robots-disallowed or never surfaced in search, for both my direct fetches and a dedicated subagent. Every *code-side* value in this brief (SGQN 0.3/0.95, hardcoded critic weight 0.5, config action_repeat 2, replay 1e5, drq nstep 3, wrapper internals, GlobalHydra.clear()) is transcribed from your scoping pass and marked **UNVERIFIED-FROM-SOURCE**. Everything I label "verified" is from the arXiv/NeurIPS PDFs, which I read in full.
- All Table 2 / Table 6 / Figure 19 values are verified verbatim against the NeurIPS supplementary and are identical in arXiv v3. The paper had three arXiv versions (v1 15 Jul 2023, v2 9 Aug 2023, v3 26 Sep 2023); I found **no errata or corrigendum** correcting the tables, and no author blog/talk correcting them.
- The **OpenReview thread and reviewer criticisms could not be read** — the forum is behind a browser check and the API endpoint was not fetchable in this environment. I therefore cannot report whether reviewers challenged the baseline implementations or whether authors responded about hyperparameters. "Searched: openreview forum URL (blocked), api.openreview.net notes endpoint (not fetchable), cached mirrors (not surfaced)."
- DeGuV's per-task numbers are that paper's **own re-runs** (SAC-based DeGuV pipeline, 1M frames, 3 seeds) on the RL-ViGen backend, not RL-ViGen's own published numbers; use them as an independent per-task sanity check, not as RL-ViGen ground truth.
- I did not find a third independent random-policy robosuite return under RL-ViGen's protocol; your Door ≈ 1.5 / Lift ≈ 7.5 (zero successes) and the sibling reproduction remain the only such measurements, and they are consistent with Lift's `1 − tanh(10·d)` shaped reward and with DeGuV's near-floor DrQv2 Lift medium/hard values (0.11 / 0.16).