# Primary-source fidelity reconciliation: all twelve active baselines

**Status:** Phase 2 working reconciliation, written 2026-09-06 from the live tree.  This is a
source-and-current-implementation audit, not a production approval and not a replacement for the
external-review package.  No remote job was launched for this note.

The purpose of this document is to make the source decisions visible before a reviewer or a
production run treats the twelve names as if they had the same provenance.  Every row below is
classified against the current effective implementation, not against a plausible intended port.
The current line references are live-tree references; they must be refreshed if the source tree is
edited.

## 1. Method and classification

I read the relevant pages/tables/appendices of the primary PDFs under `ext/baseline_resources/`,
the corresponding author-source mirrors under `ext/`, the active runnable source, the launchers,
the RL-ViGen task configuration, and the production descriptors.  Where paper and code disagree,
both are recorded.  The implementation source is the authority for what actually runs; the paper
is the authority for what the method authors say the method/configuration is.  RL-ViGen is the
authority for the Door task and its own common reproduction recipe, not for an unrelated method's
algorithmic hyperparameters.

The labels mean:

* **EXACT SOURCE MATCH** — the current value/mechanism matches the cited source at the level that
  matters for this axis, allowing a source code default to implement a paper statement.
* **SOURCE VARIANT WITH CONTEXT** — it differs, but the difference is an explicit protocol,
  benchmark, resource, or source-code-versus-paper distinction that is documented and not being
  hidden as fidelity.
* **UNSUPPORTED/NECESSARY ADAPTATION** — the source does not provide a runnable setting for Door
  (usually because it uses Procgen/DMC rather than robosuite), so an adaptation is necessary; it
  still needs to be declared and, where it changes method identity, owner acceptance.
* **SOURCE CONFLICT** — the live effective value contradicts a directly applicable paper/source
  value without a satisfactory explanation.
* **NOT SPECIFIED** — the source does not settle this axis, or the current effective value cannot
  be reconstructed from the checked files.  This is not a claim of equivalence.

`SOURCE VARIANT WITH CONTEXT` is not a green light.  It identifies a conscious and reportable
variant; `UNSUPPORTED/NECESSARY ADAPTATION` is the honest status for a port whose source domain
does not define the Door setting.

## 2. Primary-source index

| Baseline | Primary paper / supplement actually consulted | Official/local source closure consulted |
|---|---|---|
| drqv2 | `ext/baseline_resources/01_drqv2/paper_2107.09645.pdf`, pp. 4–6, 18 (Algorithm 1 and Table 2) | `ext/drqv2/drqv2.py`, `train.py`, `replay_buffer.py`, `config.yaml` |
| svea | `ext/baseline_resources/03_svea/paper_2107.00644.pdf`, pp. 21–23, Table 5 and the SVEA objective discussion | `ext/dmcontrol-generalization-benchmark/src/algorithms/svea.py`, `modules.py`, `arguments.py`, `train.py` |
| drq | `ext/baseline_resources/02_drq/paper_2004.13649.pdf`, pp. 4–5, 13–14 and Table 2/3 material | `ext/drq/drq.py`, `train.py`, `replay_buffer.py`, `config.yaml` |
| sgqn | `ext/baseline_resources/04_sgqn/paper_2209.09203.pdf`, pp. 15–16 and Table 3; source algorithm sections | `ext/SGQN/robot_env/src/algorithms/`, `train.py`, `arguments.py`, `augmentations.py` |
| curl | `ext/baseline_resources/05_curl/paper_2004.04136.pdf`, pp. 13–14, Table 3 and the crop/evaluation text | `ext/curl/curl_sac.py`, `train.py`, `encoder.py`, `config.yaml` |
| rad | `ext/baseline_resources/06_rad/paper_2004.14990.pdf`, pp. 16–17, Table 4 and Procgen appendix | `ext/rad/curl_sac.py`, `train.py`, `data_augs.py`, plus the active `runnable/dmc_gb` source |
| soda | `ext/baseline_resources/07_soda/paper_2011.13389.pdf`, pp. 9–10, Table IV and SODA objective | `ext/dmcontrol-generalization-benchmark/src/algorithms/soda.py`, `modules.py`, `arguments.py`, `train.py` |
| alda | `ext/baseline_resources/08_alda/paper_2410.07441.pdf`, pp. 4–6, 19–20, Table 1 and Eq. 7 | `ext/ALDA_Official/trainers/alda_trainer.py`, `autoencoders/`, `specs/`, active `runnable/alda` copy |
| idaac | `ext/baseline_resources/09_idaac/paper_2102.10330.pdf`, pp. 14–15, 21 and `raileanu21a-supp.pdf` §E | `ext/idaac/train.py`, `ppo_daac_idaac/{arguments,model,storage,algo}/`, active `runnable/idaac` port |
| ppg | `ext/baseline_resources/10_ppg/paper_2009.04416.pdf`, pp. 3–4, 14 (Algorithm 1 and Procgen hyperparameters) | `ext/phasic-policy-gradient/phasic_policy_gradient/`, active `runnable/ppg` copy and launch path |
| ibac_sni | `ext/papers-sorted/IBAC-SNI/IBAC-SNI_paper_neurips2019.pdf` (Igl et al., NeurIPS 2019, arXiv:1910.12911), plus the authors' `ext/IBAC-SNI` release. `ext/baseline_resources/11_ibac_sni/paper_1901.10902.pdf` is **InfoBot**, an unrelated paper retained read-only but excluded as IBAC-SNI evidence. | `ext/IBAC-SNI/torch_rl/`, `ext/IBAC-SNI/coinrun/coinrun/policies.py`, active `runnable/ibac_sni` port |
| ctrl | `ext/baseline_resources/12_ctrl/paper_2106.02193v2.pdf`, pp. 4–6, 13–14, Table 2 and pseudocode; the supplied supplement was checked for implementation detail | `ext/ctrl_public/{train_ppo,algo,models,buffer,vec_env}.py`, active `runnable/ctrl` port |

The file `ext/rl_vigen` and the active `RL-ViGen-upstream` checkout were also checked against
`ext/baseline_resources`'s RL-ViGen material.  The extracted `ext/rl_vigen_2304.08479.pdf` is a
different vision paper and is not used as the RL-ViGen benchmark source.  The active benchmark
source is `ext/baseline_resources/rl-vigen_v3_2307.10224.pdf` plus
`ext/baseline_resources/rlvigen_neurips_supplementary.pdf`.

## 3. Shared Door and measurement protocol

This section is deliberately separate from the per-method source comparison.  These values are
the current project protocol, not claims that the original papers used Door.

| Axis | Current effective value and evidence | Source interpretation / classification |
|---|---|---|
| Task | RL-ViGen robosuite `Door`, Panda, `OSC_POSE`, `agentview`, RGB only, control frequency 20, horizon 500, `ignore_done: false`: `RL-ViGen-upstream/envs/robosuiteVGB/cfg/robo_config.yaml:1-27` | **EXACT SOURCE MATCH** for the RL-ViGen Door task definition, not for the original DMC/Procgen papers. |
| Training/evaluation regimes | `train`, `eval-easy`, `eval-medium`, `eval-hard`; the wrapper explicitly maps modes and keeps dynamics randomization false: `RL-ViGen-upstream/.../robosuitevgb/utils.py:67-106` | **EXACT SOURCE MATCH** to the current RL-ViGen integration after P1/P3. The original method papers generally do not define these Door modes. |
| Scene sweep | Offline grid uses scenes 0–9; the RL-ViGen five and non-RL-ViGen families are evaluated by the shared grid through family-specific adapters. Descriptor values: `datasphere/native/families.json:100-243,341-479,587-949`. | **SOURCE VARIANT WITH CONTEXT**: original Procgen/DMC test-level protocols are not the same as ten Door scene IDs. This is a shared Door estimand, not original-source evaluation. |
| Randomization | Train has no color/camera randomization; easy/medium/hard progressively add color/light, robot/lighting/background conditions while dynamics remain false: `utils.py:67-106`. | **SOURCE VARIANT WITH CONTEXT**. This is benchmark protocol, not a method parameter. Do not call it “the authors' Procgen/DMC test split.” |
| Render resolution | Native RL-ViGen path: 84×84 (`robo_config.yaml:1-3`). RAD/SODA launcher requests 100×100 (`runnable/_launch/dmc_gb.sh:21-27`) and their source crops to 84. IDAAC, ALDA, PPG, IBAC-SNI, CTRL launch at 64 (`idaac.sh:9-11`, `alda.sh:14-16`, `ppg.sh:15-17`, `ibac_sni.sh:12-16`, `ctrl.sh:12-14`). | **SOURCE VARIANT WITH CONTEXT** for the multi-resolution protocol. The source backbones are resolution-coupled; forcing one common size would silently change or break some methods. The field-of-view difference between native 84 and 100→84 remains a comparability limitation. |
| Channels and stack | RL-ViGen, ALDA, RAD/SODA and the selected IDAAC/PPG continuous-control profiles use RGB with three-frame stacks (9 channels). IBAC-SNI and CTRL retain released one-frame geometry. PPG/IDAAC adapters accept explicit `frame_stack=1` for historical C1. | **SOURCE VARIANT WITH CONTEXT**. IDAAC’s DMC supplement explicitly uses 3 stacked frames. PPG uses that same IDAAC-authors' DMC comparator because OpenAI PPG has no primary DMC configuration; this is not called canonical PPG. |
| Action space | Door exposes continuous `Box(-1,1,(7,))`. The PPG/IDAAC/IBAC-SNI/CTRL ports add or select diagonal-Gaussian continuous heads: `idaac/model.py:311-385`, `runnable/ppg/phasic_policy_gradient/distr_builder.py:1-54`, `ibac_sni/model.py:190-201,278-281`, `ctrl/models.py:110-179`. | **UNSUPPORTED/NECESSARY ADAPTATION** for PPG, IDAAC, IBAC-SNI, and CTRL: their primary experiments/source paths are discrete Procgen or non-Door domains. It is not a source match merely because the head runs. |
| Action transform | SAC-derived families use the source tanh-squashed Gaussian path; PPO-family ports use the added Gaussian path and the environment’s Box limits. Current source locations: `runnable/dmc_gb/src/algorithms/modules.py:182-217`, `runnable/ppg/.../distr_builder.py`, `idaac/.../distributions.py`, `ibac_sni/model.py:278-281`, `ctrl/models.py:179-184`. | **SOURCE VARIANT WITH CONTEXT** for off-policy SAC variants; **UNSUPPORTED/NECESSARY ADAPTATION** for continuous ports. The exact raw-versus-clipped action convention must remain an explicit report field. |
| Training budget | Production planning defaults to 600,000 counted frames and seeds 101,102,103: `datasphere/native/plan_production.py:372-386`; the protocol says frame count is the executed environment-frame axis, with family-specific rollout quantum recorded rather than hidden. | **SOURCE VARIANT WITH CONTEXT**. RL-ViGen’s Door table specifies 600k; original method sources use 500k DMC, 25M/100M Procgen, or other domains. A common 600k Door budget is a declared cross-method comparison, not original training length. |
| Seed/reporting | Current protocol proposes three fixed training seeds, a shared evaluation placement seed, 20 full endpoint episodes per regime/scene and 3 episodes for intermediate curve points: `docs/EVAL-PROTOCOL.md:17-29,229-235,461-466`; `families.json` production fields. | **SOURCE VARIANT WITH CONTEXT**. RL-ViGen itself reports five seeds/95% CI in its paper (`rl-vigen_v3_2307.10224`, p. 6/§4), while this project’s three-seed plan is a budgeted operational decision. It cannot be presented as source-faithful seed replication. |
| Episode/reward reporting | Offline evaluator is authoritative for endpoint/curve records; native train-time logs remain family-specific. `docs/EVAL-PROTOCOL.md:133-147` and `scripts/eval_grid.py`. | **SOURCE VARIANT WITH CONTEXT**. Some sources report episode return, some train/test curves, and none defines this exact common Door grid. |
| Checkpoints | Every family has a terminal checkpoint and a retained 50k grid in the descriptor, but the production report’s common number is the endpoint unless a curve is explicitly requested: `families.json` checkpoint/intermediate fields; `docs/EVAL-PROTOCOL.md:413-466`. | **SOURCE VARIANT WITH CONTEXT**. Retention is project measurement infrastructure, not a method change. It must not be used to imply that the original training paper evaluated these checkpoint points. |

### Important x-axis confound

At 600k counted frames, the five RL-ViGen off-policy agents, RAD/SODA, ALDA, and the PPO-family
ports do not perform the same number of optimizer updates. The current decision surface explicitly
records this: `notes/DECISION-SHEET.md:1067-1076`. This is not automatically a bug: a common frame
budget is the benchmark’s declared resource axis, while update-to-data ratio is a method property.
It is a real interpretive confound and must be reported beside any ranking. In particular, the
source Procgen budgets of PPG/IDAAC/CTRL/IBAC-SNI are not reproduced by 600k Door frames.

## 4. Current effective family map

The family descriptor is the current production control surface, but it is not itself an original
paper. Its line ranges are included so that a future effective-command snapshot can replace prose.

| Family / baselines | Current effective training settings visible in descriptor | Current evaluation/checkpoint settings | Material caveat |
|---|---|---|---|
| `rlvigen` / drqv2, svea, drq, sgqn, curl | `families.json:22-142`; RL-ViGen config defaults `RL-ViGen-upstream/cfgs/config.yaml:9-52`; agent-specific configs `cfgs/*_config.yaml`. Common frame stack 3, gamma .99, batch 256, feature 50, hidden 1024, lr 1e-4, update every 2, target tau .01; DrQ n-step 1; the other four n-step 3. Launcher forces action repeat 1 and 84×84: `runnable/_launch/rlvigen.sh:18-20,61-78`. | Replay cap 300k, production save/retention 50k in descriptor, offline four regimes × scenes 0–9, endpoint 20 episodes, curve 3: `families.json:100-141`. | The descriptor’s common settings are RL-ViGen’s Door recipe, not each method paper’s original DMC settings. SGQN quantile/auxiliary values require checking the final composed argv against config and descriptor; do not cite a stale YAML default as the executed value. |
| `dmc_gb` / rad, soda | `families.json:142-243`; `runnable/dmc_gb/src/arguments.py:9-71` gives stack 3, default repeat 4, episode 1000, discount .99, init 1000, batch128, hidden1024, actor/critic lr1e-3, tau .01, target frequency2, 11-layer/32-filter CNN, adaptive entropy; SVEA .5/.5, SODA auxiliary batch256/tau .005. Launcher requests 100 render and passes `--action_repeat 1`, but the robosuite branch returns before consuming that flag: `runnable/_launch/dmc_gb.sh:21-27,49-55`; `src/env/wrappers.py:17-64`. | Production options set 600k, eval/save 50k, eval-easy training test mode, 20 train/test episodes, 20 offline episodes, three curve episodes: descriptor `:150-243`; `src/train.py:139-171`. | Native source’s default DMC action repeat is 4, but Door path does not use it. The 100→84 crop is necessary for RAD/SODA semantics: `src/algorithms/modules.py:67-81,130-145`, `soda.py:49-65`; at native 84 SODA asserts/fails and RAD’s crop degenerates. The remaining field-of-view difference is real. |
| `idaac` / idaac | `families.json:244-373`; current C2 constants 1 process × 2048 steps, 32 minibatches, log interval12, PPO epochs10, lr3e-4, gamma .99, entropy0, frame stack3; launcher 64×64 and eval-easy: `runnable/_launch/idaac.sh:9-46`; arguments and current Box support `runnable/idaac/ppo_daac_idaac/arguments.py:1-142`, `model.py:311-385`. | Descriptor `:282-373`: floor to 2048-frame rollout quantum, offline four regimes × ten scenes, endpoint-only native evaluation but retained 50k checkpoint copies. The source train loop saves only at terminal by default and logs/evaluates at `log_interval`: `ext/idaac/train.py:145-229`; the port adds retention. | Original Procgen recipe is 64 envs/worker, 256 rollout, gamma .999, lambda .95, 8 minibatches, entropy .01, lr5e-4, total25M, no frame stack (`paper_2102.10330`, p.15). The authors’ DMC supplement §E instead uses 3 stacked frames, one process, 2048 steps, 32 minibatches, PPO epochs10, entropy0, lr3e-4, and IDAAC coefficients αa=.1, αi=.1. Current C2 follows that continuous-control update/geometry profile while remaining a Door/action/evaluation adaptation; full-length competence/resource validation is still open. The former C1 one-stack/4×256 port remains historical. |
| `alda` / alda | `families.json:374-480`; `runnable/alda/specs/train_alda_robosuite_door.yaml:4-41`; source defaults in `runnable/alda/trainers/alda_trainer.py:37-79,229-308`. Batch128, 12 latents × 12 values, softmax beta100, 500k, 50k checkpoint, 10k eval, actor/critic/encoder lr1e-3, alpha lr1e-4, actor/critic update 2, frame stack3. | Descriptor `:382-480` sets exact 500k for current spec, 50k saves, 20 offline episodes / 3 curve episodes. Trainer evaluates train/eval-easy/eval-hard and saves all stamps: `alda_trainer.py:610-751`. | ALDA paper Table 1 p.20: 500k, replay1e6, batch128, 12/12, beta100, stack3, action repeat 2 (finger) otherwise4, episode100, 9×64×64 observation. Door uses a necessary domain integration and action repeat1 (dead knob on robosuite branch; spec `:34-39`), with horizon500. Algorithmic hyperparameters are close to source; domain, episode/repeat and augmentation/task are not source matches. |
| `ppg` / ppg | `families.json:481-618`; launcher 64×64: `runnable/_launch/ppg.sh:15-42`; current PPG defaults `runnable/ppg/phasic_policy_gradient/train.py:27-44,136-185`, `ppo.py:162-171`. Effective descriptor forces 8 envs × 256 steps, while upstream defaults expose 64 envs. Continuous Gaussian head is project code in `distr_builder.py:1-54`; log-std clamp/diagnostics are in `ppo.py:73-94`. | Descriptor `:513-618`: ceil to 2048 frames, no train-time evaluation, 50k saved copies and terminal `model_terminal.jd`; the source PPG train loop has no Door eval loop. | PPG paper p.14 uses Procgen: gamma .999, lambda .95, rollout256, minibatches8, entropy .01, clip .2, reward norm, lr5e-4, workers4 × 64 envs, total100M, nπ32, Eπ1, EV1, Eaux6, βclone1. Current nπ/aux settings are retained, but 8 envs and a continuous 7-D Gaussian are adaptations. Entropy .01 is sourced for discrete Procgen and is not source-validated for this continuous head; the current log-std clamp makes this a source variant, not a literal paper reproduction. |
| `ibac_sni` / ibac_sni | `families.json:619-749`; launcher `runnable/_launch/ibac_sni.sh:12-16,43-134`; effective model `--model_type impala --use_bottleneck --sni_type vib --entropy-coef 0.0 --beta 1e-4`, 64×64. Descriptor currently records one process × 128 frames/update and three cells: `:629-749`. | Separate evaluation by design; 50k stamped copies plus terminal `model.pt`, offline four regimes × ten scenes, 20/3 episodes: descriptor `:654-749`. | The source has two materially different branches. `ext/IBAC-SNI/torch_rl/scripts/train.py:31-111` is MiniGrid/PyTorch, defaults to 16 processes, 128 frames/process, PPO, entropy .01, beta1, and a default MiniGrid trunk; `ext/IBAC-SNI/coinrun/coinrun/policies.py:10-114` is the pixel/CoinRun Impala trunk with 64-ish pixel architecture, latent256 and `--nr-samples 12` in the README. Current `model_type=impala` is a source-backed architecture repair (`model.py:147-181`) and continuous Box head is an adaptation (`:190-201`). Current beta1e-4 follows CoinRun’s documented value, but no torch_rl equivalent for `nr-samples12` exists and the latent width remains 64. Entropy0.0 is an empirical declared deviation from the source default .01. One process is a resource profile, not an upstream fidelity claim; the measured 16-process OOM evidence does not prove one is the correct method setting. |
| `ctrl` / ctrl | `families.json:750-949`; launcher 64×64 and continuous Door path `runnable/_launch/ctrl.sh:12-20,30-50`; current descriptor constants include 16 envs, 256 steps, 8/8 minibatches, cluster_len10, 200 clusters, lr5e-4, CTRL lr1e-4: `families.json:754-821`; source defaults/constructors `runnable/ctrl/train_ppo.py:92-118,154-228`. | Descriptor `:804-949`: floor to 16-env quantum, checkpoint every 50k, no periodic native eval, continuous ID/OOD logging inside training; offline grid supplies the common eval. | CTRL paper Table 2 p.14 reports Procgen PPO/CTRL with gamma .999, lambda .95, rollout256, 1 PPO epoch, 8192 samples, entropy .01, clip .2, lr5e-4, 32 envs, CTRL clusters200, k3, T2, beta.3. Current Door uses 16 envs and `cluster_len=10`, and the action/likelihood path is an authored continuous Gaussian adaptation (`runnable/ctrl/models.py:110-179`). The paper’s discrete action embedding and Procgen observation semantics therefore do not transfer exactly. The current raw/clipped action and continuous loss decisions require a focused source/effect trace before being called faithful. |

## 5. Baseline-by-baseline source reconciliation

### 5.1 DrQ-v2

| Axis | Original source evidence | Current effective evidence | Classification / consequence |
|---|---|---|---|
| Method and objective | DrQ-v2 paper pp. 4–5, Algorithm 1: DDPG-style actor/critic, clipped double Q, n-step return, random-shift augmentation, no SAC entropy term. `ext/drqv2/drqv2.py:124-238` implements the actor/critic/update structure and clipped sampling. | RL-ViGen’s `algos/drqv2.py` is selected by `cfgs/config.yaml:39-52`; launcher runs the repository’s own `train.py`: `runnable/_launch/rlvigen.sh:8-16,77-78`. | **EXACT SOURCE MATCH** for the method mechanism, with RL-ViGen integration. |
| Image/augmentation | Paper p.4 and p.18/Table 2: 84×84, 3 RGB frames, pad 4 then random crop; DMC implementation’s `RandomShiftsAug` is in `ext/drqv2/drqv2.py:14-46`. | RL-ViGen Door is 84×84 and frame stack3 (`robo_config.yaml:1-3`, `config.yaml:9`), and the same family patch uses the RL-ViGen implementation. | **EXACT SOURCE MATCH** at the selected RL-ViGen/DMC point; the Door camera is necessarily different from DMC. |
| Update/budget | Paper Table 2: batch256, Adam lr1e-4, update frequency2, n-step3, tau.01, feature50, hidden1024, replay1e6, seed frames4k, exploration2k; p.6 uses action repeat2 and 10 seeds for DMC. | Current config `config.yaml:11-23,33-52` matches these algorithm settings except production replay is 300k and launcher forces action_repeat1 (`rlvigen.sh:61-67`, descriptor `families.json:100-141`). | **SOURCE VARIANT WITH CONTEXT**: replay cap is a documented host-memory adaptation; action repeat1 is RL-ViGen’s Robosuite Table 2 value, not DMC’s repeat2. The source paper’s 10-seed DMC result is not reproduced by the three-seed Door plan. |
| Exploration/eval | Paper p.5–6: clipped Gaussian noise with linear schedule; periodic DMC evaluation over 10 episodes. | `config.yaml:48-52` carries 2k exploration and .3 clip; production disables online eval and uses offline grid, descriptor `:106-125`. | **SOURCE VARIANT WITH CONTEXT**, not an algorithm change. Endpoint/offline reporting is project-owned. |

**Finding:** DrQ-v2 is the cleanest source match among the twelve, but “clean” does not mean its
source DMC result is directly comparable to Door. The real unresolved question is the effect of the
300k replay cap versus the paper’s 1M; it is documented as necessary by the current memory model,
not empirically shown to be behaviorally neutral at 600k.

### 5.2 SVEA

| Axis | Original source evidence | Current effective evidence | Classification / consequence |
|---|---|---|---|
| Core method | SVEA paper pp. 21–23: SAC with 11-layer CNN, jointly trains Q on augmented and unaugmented states; the encoder/policy are not naively trained on the strong augmentation. Source `ext/dmcontrol-generalization-benchmark/src/algorithms/svea.py:18-54`. | RL-ViGen selects `algos.svea.SVEAAgent` via `cfgs/svea_config.yaml:39-52`; RL-ViGen’s agent implementation is the active runtime closure. | **EXACT SOURCE MATCH** for the SVEA *update* mechanism (joint loss on augmented/unaugmented Q targets) only — see the Augmentation row below for the *which augmentation* axis, which is not a match. |
| Augmentation | [Added 2026-09-07, closing a real gap review 18 flagged: this row was entirely absent from this table, which let the "EXACT SOURCE MATCH" verdict above read as covering augmentation too.] SVEA paper's own augmentation is `random_conv` (a random convolutional filter), not an overlay. | `RL-ViGen-upstream/algos/svea.py:12,299` imports and calls `random_overlay` from `RL-ViGen-upstream/utils.py:227-241` — a Places365 alpha-blend overlay (`(1-.5)*x/255 + .5*places_img`), which is SODA's/SGQN's augmentation family, not SVEA's. Confirmed no `random_conv`/`random_convolution` function exists anywhere in `RL-ViGen-upstream/`. Matches `notes/CLAIMS-LEDGER.md`'s pre-existing `svea` row. | **SOURCE CONFLICT**, not a variant: the augmentation *class* is swapped, not merely re-parameterized. Report SVEA as "SVEA loss structure, SODA-family augmentation," never as an augmentation-faithful SVEA run. |
| Architecture/inputs | Paper p.21/Table 5: 84 render, 3 stack, 32 filters, first stride2 then 10 stride1 layers, 32×21×21 feature, 1024 actor/critic heads. | Current RL-ViGen cfg `svea_config.yaml:8-22,32-52` uses stack3, feature50, hidden1024 and 84 native input; the family source implements its own network. | **SOURCE VARIANT WITH CONTEXT**: feature50 is RL-ViGen common recipe rather than the paper’s stated intermediate size; verify the actual output shape from the runtime rather than infer from a config label. |
| Loss coefficients/optimization | Paper Table 5: α=.5, β=.5, Adam critic β1=.9, lr1e-3, batch128, target/encoder EMA values; current `arguments.py:25-60` carries those defaults, but RL-ViGen descriptor/config uses batch256/lr1e-4 where the common Door recipe overrides. | Current family descriptor and cfg have batch256 and lr1e-4: `families.json:22-141`, `svea_config.yaml:19-52`. | **SOURCE VARIANT WITH CONTEXT**, material and must be reported; it is not a literal SVEA Table 5 run. |
| Action/repeat/eval | Paper DMC action-repeat is task-dependent (Table 5); RL-ViGen Door launcher forces 1 and uses common offline grid. | `rlvigen.sh:61-78`, `EVAL-PROTOCOL.md`. | **SOURCE VARIANT WITH CONTEXT**: correct for the RL-ViGen Door protocol, not original DMC. |

### 5.3 DrQ

| Axis | Original source evidence | Current effective evidence | Classification / consequence |
|---|---|---|---|
| Core objective | DrQ paper pp. 4–5 and `ext/drq/drq.py:164-239`: SAC with data augmentation, automatic temperature/target entropy, augmented critic targets and actor path. | RL-ViGen config selects `algos.drq.DrQAgent`, `cfgs/drq_config.yaml:39-54`; source actor clamps log std and target entropy is `-|A|` (`ext/drq/drq.py:80-105,190-217`). | **EXACT SOURCE MATCH** for the algorithmic path. |
| Encoder/crop | Paper describes four 32-filter conv layers and random shift/crop, with a 100→84 render convention in its hyperparameter table. `ext/drq/drq.py:12-32`, `ext/drq/train.py:38-48`. | Current RL-ViGen path is native 84 and the common RL-ViGen config: stack3, batch256, feature50, n-step1; `cfgs/drq_config.yaml:8-22`; launcher 84/no P6. | **SOURCE VARIANT WITH CONTEXT**. Native 84 is the RL-ViGen Door implementation and differs from the original DMC render/crop convention. |
| Optimization/replay | Original paper’s table uses batch512, lr1e-3 for most SAC components, replay100k, target frequency2 and tau.01; current cfg `:18-22,32,45-54` uses replay capacity via descriptor 300k, batch256, lr1e-4, n-step1. | `families.json:100-141`, `cfgs/drq_config.yaml`. | **SOURCE CONFLICT** if the comparison is claimed as original DrQ hyperparameters; **SOURCE VARIANT WITH CONTEXT** if accurately labeled as RL-ViGen’s Door recipe. The report must use the latter wording. |
| Entropy/action | Source uses SAC automatic alpha and log-std bounds [-10,2]; current cfg `:53-54` preserves this. Door action is continuous Box. | **EXACT SOURCE MATCH** for the SAC continuous-action mechanism. |

### 5.4 SGQN

| Axis | Original source evidence | Current effective evidence | Classification / consequence |
|---|---|---|---|
| Core mechanism | SGQN paper pp. 15–16: SAC baseline plus attribution/quantile-guided overlay; Table 3 quantile .95 for most listed tasks, overlay and auxiliary update; official implementation `ext/SGQN/robot_env/src/algorithms/` and `augmentations.py:119-160`. | RL-ViGen selects `algos.sgqn.SGQNAgent` and common RL-ViGen agent config `sgqn_config.yaml:40-56`; Places365 overlay is an RL-ViGen family asset. | **SOURCE VARIANT WITH CONTEXT**: the mechanism is source-backed, but Door task integration and current common hyperparameters are RL-ViGen-specific. |
| Image/stack/augmentation | Paper Table 3: 84×84×3 render, stack3; quantile .95 in the source table and overlay/attribution. | Current RL-ViGen path is 84/stack3; `ext/SGQN/robot_env/src/augmentations.py:63-74,119-160`; descriptor requires Places365. | **EXACT SOURCE MATCH** for geometry/augmentation class, but the current configured quantile/aux values must be taken from the composed effective config, not just `cfgs/sgqn_config.yaml:54-56` (which says aux lr1e-4 and quantile .93). The descriptor/faithfulness table has historically recorded Door-specific values. This is **NOT SPECIFIED** until an effective-argv snapshot is retained. |
| Optimization | Paper Table 3: batch128, critic lr1e-3, SSL lr3e-4, alpha lr1e-4, target frequency2, encoder momentum .05/critic .01; current common RL-ViGen config uses batch256/lr1e-4 and descriptor records a Door auxiliary setting. | `sgqn_config.yaml:19-22,31-56`; `families.json:22-141`. | **SOURCE VARIANT WITH CONTEXT**; the difference is material. Do not report “SGQN original hyperparameters” for this row. |
| Action/eval | SAC continuous Box is source-compatible; RL-ViGen Door launcher action_repeat1 and offline grid are project choices. | `rlvigen.sh:61-78`, `docs/EVAL-PROTOCOL.md`. | **SOURCE VARIANT WITH CONTEXT**. |

### 5.5 CURL

| Axis | Original source evidence | Current effective evidence | Classification / consequence |
|---|---|---|---|
| Core method | CURL paper p.14: SAC plus contrastive online encoder, random crop, same crop across frame stack; source `ext/curl/curl_sac.py:185-229` and encoder. | RL-ViGen selects `algos.curl.CURLAgent`, `cfgs/curl_config.yaml:39-54`; active family source is the RL-ViGen implementation. | [Corrected 2026-09-07: this verdict was overbroad, exactly the failure review 18 named. Verified directly: `RL-ViGen-upstream/algos/curl.py:54` — `class CURLAgent(DrQV2Agent):`, `super().__init__(**kwargs)`. RL-ViGen's CURL backbone is DrQ-v2 (deterministic actor-critic, clipped-noise exploration, n-step returns, no entropy term) with a CURL contrastive head bolted on, not CURL's own SAC backbone. This is a mechanism-level difference, not a hyperparameter variant, and matches `notes/CLAIMS-LEDGER.md`'s pre-existing "DrQ-v2-based, not SAC" row for `curl`.] **SOURCE CONFLICT** for the backbone (DrQ-v2, not SAC); the contrastive-representation *idea* is present, but "EXACT SOURCE MATCH for the mechanism" is not an accurate verdict for this row. |
| Geometry/augmentation | Paper Table 3/p.14: 100×100 render, crop to84, stack3, center crop at evaluation; random crop applied consistently across stack. | Current RL-ViGen Door renders native84 and uses its own wrapper; `curl_config.yaml:8-22`; launcher leaves image size default84. | **SOURCE VARIANT WITH CONTEXT**. The original crop has no nontrivial 100→84 source geometry here; this is a real field-of-view/augmentation difference, though not the same fatal size dependency as SODA. |
| Optimization | Paper Table 3: replay100k, batch512, actor/critic lr task-dependent, alpha lr1e-4, tau.01, target freq2, latent50; current Door recipe uses replay300k, batch256, lr1e-4, n-step3, feature50: `cfgs/curl_config.yaml:8-53`, `families.json:100-141`. | **SOURCE VARIANT WITH CONTEXT**; common RL-ViGen settings override important original DMC values. |
| Evaluation | Paper reports DMC/Atari tasks with 10-episode evaluation; current report uses full Door offline grid. | **SOURCE VARIANT WITH CONTEXT**. |

### 5.6 RAD

| Axis | Original source evidence | Current effective evidence | Classification / consequence |
|---|---|---|---|
| Core method | RAD paper pp. 16–17/Table 4: SAC plus a selectable augmentation module; for DMC, crop/translate choices, automatic entropy, standard SAC actor/critic. `ext/rad/curl_sac.py`, `data_augs.py`, `train.py`. | Active code is the DMC-GB family source `runnable/dmc_gb/src/algorithms/rad.py` plus shared `modules.py`; descriptor maps rad to that family `families.json:142-243`. | **EXACT SOURCE MATCH** for using the official modular RAD/SAC mechanism, subject to task adaptation. |
| Render/crop | RAD Table 4 uses render100 and crop/translate to 84. Active launcher sets `RLVIGEN_IMAGE_SIZE=100`; the shared source crop is a 100→84 center/random path: `dmc_gb.sh:21-27`, `modules.py:67-81,130-145`. | **EXACT SOURCE MATCH** for the resolution-dependent source contract; Door camera itself is adapted. At 84, source RAD crop becomes identity and the algorithm degenerates toward SAC, so native 84 would be a source conflict. |
| Optimization | RAD Table 4: replay100k, init1000, stack3, batch512, hidden1024, actor/critic lr2e-4 for cheetah otherwise1e-3, alpha1e-4, tau.01, target2, gamma.99. Active defaults: `arguments.py:17-35` batch128, lr1e-3, tau.01; production descriptor leaves replay uncapped and passes budget/save/eval knobs. | **SOURCE VARIANT WITH CONTEXT**: active DMC-GB source defaults and RL-ViGen budget do not equal every RAD Table 4 value. The `rad` identifier is not license to claim the DMC paper’s exact hyperparameters. |
| Action/repeat/eval | Original DMC action repeat is task-dependent; Door branch does not consume `--action_repeat` (`dmc_gb.sh:49-54`, `wrappers.py:35-64`). | **UNSUPPORTED/NECESSARY ADAPTATION** for Door action/task; **SOURCE VARIANT WITH CONTEXT** for the preserved augmentation mechanism. |

### 5.7 SODA

| Axis | Original source evidence | Current effective evidence | Classification / consequence |
|---|---|---|---|
| Core method | SODA paper pp. 9–10: SAC plus a soft augmentation target/predictor; auxiliary update frequency2, SODA batch256, target momentum .005. `ext/dmcontrol-generalization-benchmark/src/algorithms/soda.py:13-85`, `modules.py:114-128`. | Active source `runnable/dmc_gb/src/algorithms/soda.py:13-85`; same family descriptor as RAD. | **EXACT SOURCE MATCH** for the SODA mechanism. |
| Resolution/augmentation | Paper Table IV p.9: render100, crop84, stack3, overlay α=.5; source asserts 100 in `soda.py:49-65` and uses crop in `modules.py`. | Launcher deliberately sets render100: `dmc_gb.sh:21-27`; a native84 default would fail the source assertion. | **EXACT SOURCE MATCH** for the source-dependent size path; **SOURCE VARIANT WITH CONTEXT** for Door rendering/camera. |
| Optimization | Paper Table IV: batch RL128/SODA256, SAC lr1e-3, alpha1e-4, SODA3e-4, actor freq2, critic1, auxiliary2, tau.005, gamma.99. Active arguments `:17-55` still default `aux_lr=1e-3`, but the official `runnable/dmc_gb/scripts/soda.sh:1-5` explicitly passes `--aux_lr 3e-4`; the production launcher now preserves that effective source value. Production still uses common `train_steps=600k`, uncapped buffer, and project evaluation. | **SOURCE VARIANT WITH CONTEXT**. SODA's mechanism and effective auxiliary LR now follow the DMC-GB source; budget, replay retention, Door adaptation, Places split, and project evaluation remain declared deviations. |
| Replay/action/update accounting | `SODA.update()` first calls inherited SAC critic/actor/target updates from `replay_buffer.sample()`; that generic sample applies random crop to `obs` and `next_obs`. On every second RL step, `sample_soda(256)` reads only stored observations, then SODA crop/overlay views train the predictor and EMA target. `train.py` collects one action and one transition per loop iteration; its Door branch does not consume `--action_repeat`. | `soda.py:49-84`, `utils.py:152-192`, `train.py:183-204`, `dmc_gb.sh:49-55`. | **SOURCE MATCH** for the two-stream update structure; executed transition endpoint is `train_steps+1` because the loop is inclusive, and action repeat is a Door adaptation. |
| Auxiliary optimizer | Paper specifies Adam β1=.9, β2=.999 for RL/auxiliary optimizers. `SODA.__init__` uses Adam on predictor parameters with `lr=args.aux_lr`, `betas=(args.aux_beta,.999)`; active parser default `aux_beta=.9`, launcher now supplies source `aux_lr=3e-4`. | `soda.py:30-32`, `arguments.py:49-52`, `scripts/soda.sh:1-5`, `_launch/dmc_gb.sh` final argument construction. | **SOURCE MATCH** for active optimizer values; the generic `arguments.py` `aux_lr=1e-3` is a non-effective fallback for the production SODA path. |
| Test-time behavior | Paper p.9/algorithm says only the learned encoder/policy is used at test. Current offline evaluator loads the checkpoint without the training auxiliary update. The inherited source `SODA.train()` guard checks `soda_predictor`, but the live module is named `predictor`; this leaves its BatchNorm predictor in train mode when the whole agent is put in eval mode. The predictor is not used by the policy action path, so this is a latent inherited defect, not a changed production metric. | **SOURCE MATCH** for the auxiliary update being absent from evaluation, with a documented inherited train-mode defect; common Door grid is project-owned. |

### 5.8 ALDA

| Axis | Original source evidence | Current effective evidence | Classification / consequence |
|---|---|---|---|
| Representation/objective | ALDA paper pp. 5–6: disentangled latent variables, softmax relaxation temperature β=100, 12 latent variables with 12 values, reconstruction/commit objective Eq.7, weight decay .1; source `ext/ALDA_Official/autoencoders/` and `trainers/alda_trainer.py:229-308`. | Active trainer preserves these values: `runnable/alda/trainers/alda_trainer.py:229-308`; spec `:9-14`. | **EXACT SOURCE MATCH** for the ALDA algorithmic design and principal coefficients. |
| Architecture | Paper p.19: three-layer 1024 GeLU actor/critic; source defaults/active trainer construct the SAC actor/critic and encoders: `alda_trainer.py:37-78,229-308`. | Door Box(7) is passed into the source SAC path. | **SOURCE VARIANT WITH CONTEXT**: actor/environment integration is a new domain branch, while the SAC/ALDA components are source-backed. |
| Input/frame/action | Paper Table 1 p.20: observation 9×64×64, frame stack3, action repeats2/4 by DMC task, episode100. Current Door spec is 64×64, frame stack3, action_repeat1 dead on robosuite path, horizon500: `runnable/alda/specs/train_alda_robosuite_door.yaml:31-41`; trainer `:134-215`. | **UNSUPPORTED/NECESSARY ADAPTATION** for Door task/horizon/action repeat; the 64/stack3 geometry is source-consistent. The dead `action_repeat` field must not be described as an effective override. |
| Training/eval/checkpoint | Paper uses DMC-GB, 500k and periodic evaluations; current trainer runs 500k, evaluates train/easy/hard, and saves at 50k: `alda_trainer.py:610-751`; descriptor `families.json:448-480`. | **SOURCE VARIANT WITH CONTEXT**: the three-regime Door extension is project behavior; it is nevertheless closer to the paper’s train/test generalization structure than the other ports. |

### 5.9 IDAAC — C2 follows the DMC-informed continuous-control design point

| Axis | Original source evidence | Current effective evidence | Classification / consequence |
|---|---|---|---|
| Algorithm | IDAAC paper pp. 14–15: PPO plus invariance discriminator/order-prediction mechanism, alternating policy/value updates; official source `ext/idaac/ppo_daac_idaac/algo/idaac.py`, `train.py:85-199`. | Active port retains IDAAC/DAAC/PPO branches and adds Box-compatible `DiagGaussian`: `runnable/idaac/ppo_daac_idaac/model.py:311-385`; launcher uses the repository’s own `train.py` (`idaac.sh:42-46`). | **SOURCE VARIANT WITH CONTEXT** for the algorithm; continuous Door action head is an **UNSUPPORTED/NECESSARY ADAPTATION**. |
| Procgen recipe | Paper p.15: gamma .999, λ .95, rollout256, 3 PPO epochs, 8 minibatches, entropy .01, lr5e-4, workers1/envs64, no frame stack, 25M frames. | Superseded C1 used 4 processes × 256 steps; current descriptor uses separate C2 design point: `families.json:247-308`. | **HISTORICAL SOURCE VARIANT**: retained for interpreting old C1 evidence, not current production configuration. |
| DMC continuous recipe | The authors’ supplementary `ext/idaac/raileanu21a-supp.pdf`, §E: 3 stacked frames, one process, 2048 steps, 32 minibatches, PPO epochs10, entropy0, lr3e-4, linear decay, and IDAAC αa=.1/αi=.1. | Current C2 applies these values through `families.json:247-373` and launcher options; Door action, scene/evaluation, horizon and resource behavior remain project adaptations. | **SOURCE-ALIGNED DESIGN POINT WITH CONTEXT**, not exact DMC reproduction. Full-length training/resource validation remains open. |
| Normalization/termination | Procgen source uses reward normalization and level-based test distribution; current RL-ViGen adapter uses VecMonitor/VecNormalize around a fixed Door scene: `runnable/idaac/ppo_daac_idaac/envs.py:100-179`. | **SOURCE VARIANT WITH CONTEXT**: wrapper behavior is preserved where possible, but the held-out-level semantics are not available when the in-loop scene is fixed at scene0. |
| Eval/checkpoint | Original evaluates a Procgen full distribution; current training evaluation is one scene and offline grid sweeps scenes. Current descriptor calls this split vacuous and saves 50k copies. | **SOURCE VARIANT WITH CONTEXT**; report the offline grid as the project’s estimand, not the source evaluate() quantity. |

**Required disposition:** label old C1 records separately. Current production target is IDAAC-C2,
the DMC-informed continuous-control design point with explicit Door adaptations. Do not reuse C1
competence or resource evidence as C2 validation; full-length C2 evidence remains required.

### 5.10 PPG — the one-stack/continuous adaptation and phasic cadence

| Axis | Original source evidence | Current effective evidence | Classification / consequence |
|---|---|---|---|
| Phasic method | PPG paper pp. 3–4: disjoint policy/value networks, policy phase, value phase, infrequent auxiliary phase, behavioral-cloning term; `ext/phasic-policy-gradient/phasic_policy_gradient/ppg.py`, `train.py`. | Active PPG preserves `n_pi=32`, policy/value epoch1, auxiliary epochs6, βclone1: `runnable/ppg/phasic_policy_gradient/train.py:27-44,79-115`. | **EXACT SOURCE MATCH** for the phasic update mechanism and these principal settings. |
| Procgen recipe | Paper p.14: gamma .999, λ .95, rollout256, minibatches8, entropy .01, clip .2, reward norm, lr5e-4, workers4/envs64, total100M, no frame stack. | Historical C1 used those defaults. Current production descriptor passes 8 envs × 256, `gamma=.99`, `lr=3e-4`, `aux_lr=3e-4`, `nminibatch=32`, `entcoef=0`, `frame_stack=3`, `interacts_total=600k`: `families.json:481-618`; train CLI receives them through `ppg.sh`. | **SOURCE VARIANT WITH CONTEXT**: DMC comparator values are source-backed adaptation from the IDAAC-authors' supplement, not OpenAI PPG's own Procgen recipe; 8 envs and 600k are Door resource/domain adaptations. |
| Action head | PPG source uses Procgen’s discrete categorical action head. Current `distr_builder.py:1-54` and `ppo.py` support RL-ViGen `Box(7,)`; current source logs and clamps continuous log std. | **UNSUPPORTED/NECESSARY ADAPTATION**. The discrete entropy coefficient .01 is not thereby validated for a 7-D Gaussian. It is a declared design point with health diagnostics, not an exact source setting. |
| Observation geometry | Procgen source is 64×64 RGB with no frame stack; the selected Door PPG profile explicitly passes `frame_stack=3`: `families.json:536-580`, `train.py`, and adapter `FrameStack` path `envs.py`. `frame_stack=1` remains explicit for C1. | **SOURCE VARIANT WITH CONTEXT**: production uses the three-frame geometry selected for the Door run. This adopts comparator geometry only, not the IDAAC DMC optimizer/rollout recipe and not a canonical PPG DMC claim. |
| Checkpoint/report | PPG paper reports policy performance after its phasic schedule, not this project’s 50k all-checkpoint curve. Current descriptor passes `--save_mode all --ic_per_save 50000`, terminal `model_terminal.jd`: `families.json:513-542`; source save plumbing was exposed without changing defaults. | **SOURCE VARIANT WITH CONTEXT**: retention/reporting is project-owned and does not alter learning, but a 600k run has only 18 full auxiliary phases if nπ is interpreted literally; the current `n_pi`/budget decision remains visible in `notes/DECISION-SHEET.md:464-488`. |

### 5.11 IBAC-SNI — branch identity, 64×64 Impala, continuous head, and process count

| Axis | Original source evidence | Current effective evidence | Classification / consequence |
|---|---|---|---|
| Method identity | IBAC-SNI paper pp. 13–15 defines the variational information bottleneck and SNI; continuous-control experiments use MuJoCo/PPO and goal-conditioned information, while pixel CoinRun uses a separate visual branch. | Current launcher selects PPO + VIB SNI: `ibac_sni.sh:43-60,133-134`; current `bottleneck.py`/algorithm preserve the bottleneck path. | **SOURCE VARIANT WITH CONTEXT**: method core is retained, but no primary source defines this exact Door combination. |
| Architecture | Official CoinRun `ext/IBAC-SNI/coinrun/coinrun/policies.py:10-114` has the Impala CNN (16,32,32; three pooling stages) and a 256-dimensional latent in the pixel branch. Official PyTorch `torch_rl/model.py` is MiniGrid-oriented and has a one-downsample trunk. | Current `runnable/ibac_sni/torch_rl/model.py:147-181` adds an explicit Impala branch; launcher selects `--model_type impala`, 64×64: `ibac_sni.sh:12-16,46-60`. | **SOURCE VARIANT WITH CONTEXT / NECESSARY ADAPTATION**: this is the correct source-backed pairing for a 64×64 pixel input, not the old 64×64 + MiniGrid-trunk hybrid. It still is not the authors’ TensorFlow CoinRun implementation. |
| Observation/action | CoinRun is pixel/discrete Procgen-like; torch_rl source is MiniGrid/discrete. Current Door is RGB64 and Box(7), with a Gaussian head: `model.py:190-201,278-281`. | **UNSUPPORTED/NECESSARY ADAPTATION**. The continuous head is not present in the original torch_rl branch and the CoinRun command does not define a continuous Door action. |
| Bottleneck strength | Official README command uses `--beta 0.0001 --nr-samples 12 --sni` for CoinRun; official torch parser defaults beta1, entropy .01 and epochs4/batch256: `ext/IBAC-SNI/torch_rl/scripts/train.py:31-111`; current launcher passes beta1e-4, but no torch_rl equivalent of `nr-samples12` exists. | **SOURCE VARIANT WITH CONTEXT** for beta; **NOT SPECIFIED/UNSUPPORTED** for the missing sample-count correspondence. This must be reported, not implied to be exact. |
| Entropy | Torch source default is .01 (`ext/.../scripts/train.py:49-50`), tuned in a discrete context. Current Door launcher passes 0.0 after a measured divergence comparison: `ibac_sni.sh:65-107`. | **SOURCE CONFLICT** against the literal torch default; **SOURCE VARIANT WITH CONTEXT** as an explicitly measured continuous-control workaround. It remains an owner-facing design choice; the earlier .01 run is not evidence for the current Impala/beta configuration. |
| Parallelism | Official parser default is 16 processes, 128 frames/process (`ext/.../scripts/train.py:31-42`). Current descriptor defaults to one process ×128 and says 16 workers OOM the gt4.1 resource: `families.json:619-749`; launcher passes caller process count. | **SOURCE VARIANT WITH CONTEXT**, not “source exact” and not a settled supersession of 16. One process is an operational profile selected under memory constraints. A production run should either use a tier that can execute the source-like process count or ratify the one-process profile; a local fork/spawn workaround is not automatically equivalent because renderer/process/RNG behavior is part of the effective experiment. |
| Eval/checkpoint | Official source separates training and evaluation; current grid evaluates saved checkpoints and retains stamped copies. | **SOURCE VARIANT WITH CONTEXT**, with no learning change. |

### 5.12 CTRL — cross-trajectory objective versus Door continuous adaptation

| Axis | Original source evidence | Current effective evidence | Classification / consequence |
|---|---|---|---|
| Core method | CTRL paper pp. 4–6 and p.13 pseudocode: trajectory-window views, online clustering/Sinkhorn-like prototypes, MYOW cross-cluster prediction, RL policy/value loss; `ext/ctrl_public/algo.py:170-243,479-527`, `models.py:103-199`. | Current port retains the CTRL cluster update and PPO path in `runnable/ctrl/algo.py`, `models.py`, `train_ppo.py`; family closure excludes training-only files from evaluator identity. | **SOURCE VARIANT WITH CONTEXT** for core mechanism. |
| PPO/CTRL hyperparameters | Paper Table 2 p.14: gamma .999, λ .95, rollout256, PPO epoch1, samples8192, entropy .01, clip .2, lr5e-4, 32 envs, clusters200, k3, trajectory length T2, beta .3. | Current descriptor: 16 envs, n_steps256, n_minibatch8, cluster_len10, n_minibatch_ctrl8, clusters200, lr5e-4/1e-4, max grad norm.5: `families.json:754-821`; source defaults `train_ppo.py:92-118`. | **SOURCE VARIANT WITH CONTEXT** for the common PPO settings; **SOURCE CONFLICT** for `cluster_len=10` versus Table 2 T2 if “exact CTRL” is claimed. The change may be necessary for a Door window or simply a port drift; it needs an explicit rationale/sensitivity. |
| Observation/action | Paper is Procgen and uses 64×64 images; model source `ext/ctrl_public/models.py:52-84` is Impala-like. Current launcher uses 64×64 and source has a continuous Gaussian head `runnable/ctrl/models.py:110-179`; `train_ppo.py:168-209` detects Box and initializes accordingly. | **SOURCE VARIANT WITH CONTEXT / NECESSARY ADAPTATION**: 64 geometry follows the source, but Box(7) and action embedding are not paper-exact. |
| Action semantics | Source paper’s primary experiments are discrete Procgen; current code’s continuous `MultivariateNormalDiag` and action conditioning are authored for Door. The exact raw/clipped path must be traced through `vec_env.py`, `algo.py`, and the RL-ViGen wrapper before final reporting. | **NOT SPECIFIED** until that trace is independently checked. It is not enough that the code compiles or that the endpoint evaluator runs. |
| Evaluation/processes | Paper uses 32 Procgen environments and reports ID/OOD behavior; current Door descriptor uses 16 envs and training loop continuously steps train/ID and eval/OOD environments, with offline evaluator used for common report: `train_ppo.py:85-105,189-209,313-374`. | **SOURCE VARIANT WITH CONTEXT**. The two continuous in-loop streams are useful health signals but differ from a periodic checkpoint evaluator; the offline grid is the common estimand. |

## 6. Focused cross-baseline conclusions

### 6.1 Sizing is not a single “preserve one input size” rule

The live code and source make three different cases:

1. **RL-ViGen-native five:** 84×84 is the benchmark’s own Door input and all five use the
   RL-ViGen source/config path. The original method papers’ DMC render conventions still differ,
   especially for DrQ/DrQ-v2/CURL/SVEA/SGQN.
2. **RAD/SODA:** their author code is explicitly size-dependent. The paper/source path renders
   100 and crops to 84. Current `dmc_gb.sh` sets 100 and `modules.py`/`soda.py` enforce the crop.
   Calling this “just an augmentation” is wrong: at native84 SODA fails and RAD’s crop may become
   an identity. The 100 render is therefore the best fidelity default, with an explicit camera/FOV
   comparability limitation.
3. **IDAAC/ALDA/PPG/IBAC-SNI/CTRL:** these are independent source trees whose visual trunks are
   Procgen/MiniGrid/ALDA-sized. Current 64×64 launch choices preserve the source-compatible
   architecture shape where possible. They do not make the resulting continuous Door methods
   source-exact. For IDAAC especially, the input *resolution* and the *frame stack* are separate:
   current 64×64 one-RGB-frame is not the authors’ DMC 3-stack recipe.

Thus “preserve original input size” is a correct operational rule only when paired with the
original source branch: 100 means render-before-crop for RAD/SODA; 64 means a source-sized visual
trunk for the independent Procgen-shaped ports; 84 means RL-ViGen’s native Door path. A universal
84 resize would make some methods different or broken, and a universal 64 resize would alter the
RL-ViGen backbones. The table must expose the resolution and preprocessing, not collapse them.

### 6.2 PPG and IDAAC are not interchangeable continuous-control evidence

Both methods share a Procgen PPO lineage, but their source records are different:

* PPG’s paper supplies the phasic schedule (nπ32, Eπ1, EV1, Eaux6, βclone1) and discrete
  categorical Procgen setup. Current PPG retains the phasic schedule but adds a continuous Gaussian
  head and uses 8 rather than 64 environments.
* IDAAC’s main Procgen recipe is not the authors’ continuous-control recipe. The supplement’s DMC
  §E explicitly changes the rollout/update geometry and uses 3 stacked frames, one process,
  2048 steps, 32 minibatches, 10 PPO epochs, entropy0 and lr3e-4, plus IDAAC coefficients. The
  historical Door pilot was 4×256/8 and one RGB frame; current production uses the implemented
  C2 profile. Full-length C2 competence/resource validation remains open, not the C2
  implementation itself.

The historical one-stack IDAAC pilot establishes importability, checkpointing, and that the port
runs. It cannot license the claim “we reproduced continuous-control IDAAC.” Current production
uses the implemented C2 three-stack arm; final production claims still need full-length evidence
and explicit owner ratification of remaining Door adaptations.

### 6.3 IBAC-SNI’s “proper” architecture is improved but not source-identical

The old 64×64 MiniGrid trunk was a hybrid that no source used. Selecting the Impala branch is the
best current default because it follows the authors’ own pixel branch and restores the expected
three-pool 64→8 geometry. That closes an architectural error, not the whole fidelity question:
the live run still uses the PyTorch MiniGrid training/evaluation stack, a continuous Gaussian
head, one VIB sample rather than CoinRun’s `nr-samples=12`, latent64 rather than the CoinRun
latent256, and entropy0 rather than the torch default .01. These are all reportable adaptations.

The process count must not be silently “fixed” to one as if one were source-faithful. The current
evidence says 16 workers were attempted and OOM-killed on gt4.1, while 1 is the measured safe
profile. The conservative production decision is either a tier/profile that can run 16, or an
explicitly labelled one-process profile; changing multiprocessing start method alone does not
prove semantic equivalence because MuJoCo/EGL ownership and RNG inheritance can change.

### 6.4 CTRL’s common algorithm is source-backed; its Door action/window choices need review

The live CTRL code retains the original clustering and auxiliary objective, and its 64×64 input is
source-shaped. However, the current `cluster_len=10` differs from Table 2’s T=2, and the continuous
Gaussian/Box action path is project-authored. The fact that CTRL can run and produce an offline
checkpoint evaluation proves integration, not that raw/clipped action semantics, action embedding,
and clustering windows are the paper’s method. A small local source trace plus a controlled
sensitivity/diagnostic is the correct next closure; do not repair this speculatively by changing
the action path before that trace.

## 7. Final classification matrix

This matrix records the strongest material status, not a binary quality score.

| Baseline | Strongest exact area | Strongest source variant/adaptation | Strongest conflict or unresolved item | Production wording safe now |
|---|---|---|---|---|
| drqv2 | DrQ-v2 actor/critic/augmentation and RL-ViGen geometry | replay cap, Door action repeat, 3-seed/offline protocol | cap neutrality at 600k not empirically demonstrated | “DrQ-v2 implementation on RL-ViGen Door with documented replay/protocol adaptation” |
| svea | SVEA loss/augmentation mechanism | RL-ViGen common lr/batch/replay and Door task | effective composed SGQN/SVEA config should be snapshotted, not inferred | “SVEA source mechanism, RL-ViGen Door configuration” |
| drq | SAC/DrQ mechanism and automatic entropy | RL-ViGen batch/lr/replay/native84 | original DMC hyperparameter table is not current effective run | “DrQ source implementation with RL-ViGen Door recipe” |
| sgqn | SGQN attribution/overlay mechanism | common RL-ViGen optimizer/geometry | quantile/aux values need final effective-argv proof | “SGQN source mechanism with explicit Door descriptor overrides” |
| curl | CURL contrastive mechanism | native84 versus source 100→84, common Door hyperparameters | crop/FOV difference | “CURL source mechanism on RL-ViGen Door; preprocessing variant declared” |
| rad | RAD modular augmentation and SAC | Door wrapper/action/reward/task | active batch/replay/budget differ from paper table | “RAD source augmentation/SAC on Door, not original DMC setting” |
| soda | SODA auxiliary target mechanism and 100→84 dependency | Door wrapper, uncapped budget, common eval | effective argv must be retained | “SODA source mechanism with source-required 100 render and Door adaptation” |
| alda | ALDA representation/objective and principal values | Door branch, horizon, action repeat1, three regimes | no completed CUDA production evidence yet; source does not define Door | “ALDA source algorithm with explicit robosuite Door branch” |
| idaac | IDAAC algorithm and current DMC-informed continuous-control profile | Box head and Door adapter; current production geometry is 3 frames, while historical C1 used one frame | full-length C2 competence/resource validation remains open; Door/action/evaluation remain adaptations | “IDAAC Door port using source-backed C2 geometry and update profile; full-length validation pending” |
| ppg | PPG phasic schedule and PPO coefficients; selected main path uses the IDAAC-authors' DMC comparator geometry | Box head, 3-frame C2 geometry, 8 envs, 600k, 64 Door | .01 entropy is discrete-source value; auxiliary phase count at 600k; comparator geometry is not canonical OpenAI PPG DMC evidence | “PPG phasic source algorithm with declared continuous Door adaptation and active C2 geometry” |
| ibac_sni | VIB/SNI core; Impala trunk now source-backed | torch MiniGrid stack, Box head, beta wiring, 64 input | missing nr-samples equivalence, latent width, entropy0, process count | “IBAC-SNI-derived Door port; pixel/continuous adaptations explicit” |
| ctrl | CTRL clustering/MYOW mechanism and 64 input | Box head, 16 envs, Door streams | `cluster_len=10` vs paper T2 and raw/clipped action trace | “CTRL source mechanism with declared continuous Door/window adaptation” |

## 8. Closure requirements before external/production claims

These are not new implementation instructions; they are the evidence required to move a row from
the classifications above to a defensible final report.

1. **Freeze effective commands/configs.** For each seed/family, retain the final argv, environment
   variables, resolved YAML/spec, package versions, host profile, frame quantum, executed frame
   count, and checkpoint hash. In particular, retain the composed SGQN values rather than citing
   its uncomposed YAML.
2. **Resolve IDAAC C1/C2.** Run or explicitly ratify the 3-stack DMC-informed design point before
   calling IDAAC continuous-control fidelity settled. Preserve the existing C1 as a labelled pilot;
   do not overwrite it or promote it by analogy.
3. **IBAC-SNI.** Treat Impala selection as the current best default, but make the missing CoinRun
   `nr-samples` correspondence, latent64-versus256, entropy coefficient, and process count visible
   in the result table. A competence run must use the current Impala + beta1e-4 configuration; old
   hybrid/.01/beta1 pilots are not evidence for it.
4. **CTRL.** Verify the full continuous action path from environment output through rollout buffer,
   distribution, loss, and evaluator, including whether any clipping occurs before storage or only
   at environment step. Compare the current cluster window to the source T2 before changing it.
5. **Off-policy sizing sensitivity.** The 100→84 RAD/SODA path is the source-faithful default. A
   native84 control is useful as a declared ablation, not as a replacement for the source path.
6. **Budget interpretation.** Report common 600k frames and the family-specific update quantum
   together. Do not substitute original 25M/100M Procgen or 500k DMC source budgets into the Door
   table without labelling that as a different experiment.
7. **Evaluation.** Keep endpoint as the headline metric if desired, but retain all 50k checkpoint
   artifacts and raw per-episode records so best-over-trajectory and post-hoc deeper evaluation
   remain reconstructible. The offline grid is the common measurement; native training curves are
   diagnostics and are not interchangeable quantities.
8. **Source/revision binding.** Rebuild evaluator payloads after any source-closure change and use
   the schema-2 evaluator identity/provenance rules. Do not reuse records whose evaluator identity
   predates a changed closure without revalidation.

## 9. Limits and uncertainty

* This audit read the cited primary pages and implementation closures; it did not claim that every
  line of every dependency is mathematically equivalent to the paper. Dynamic imports, generated
  configs, package versions, and runtime environment are why effective snapshots are required.
* For RL-ViGen five, some parameters are selected through Hydra composition and family overrides.
  A YAML default is not proof of the production argv. The SGQN quantile/auxiliary values are the
  clearest example; the final run manifest must settle them.
* A source paper’s DMC/Procgen result and a Door result share a method name but not an estimand.
  The classifications intentionally do not turn domain adaptation into “exact reproduction.”
* Local source inspection cannot establish CUDA renderer equivalence, throughput, memory under the
  final process count, or competence at 600k. Those require the bounded remote probes/production
  jobs, with their costs and failures retained.
* The project’s current tree is not clean: this note is a new evidence artifact, not a claim that
  all unrelated working-tree changes are integrated or frozen.
