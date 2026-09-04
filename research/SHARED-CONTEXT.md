# Shared context for the research briefs

Give this to **every** agent, alongside its own brief and `PREMISES.md` / `FAITHFULNESS.md`.

---

## 1. What the project is

A **multi-baseline generalization benchmark** for the MIPT Centre for Cognitive Modelling. Twelve
visual-RL algorithms are trained under one protocol on one environment, and the quantity of
interest is the **generalization gap**: performance on the training visual regime minus performance
on a held-out regime.

The point of the repo is *comparability*, not any single algorithm's score. So the evaluator is
shared by construction — it takes an opaque `policy: Callable[[obs], action]` and cannot see which
algorithm produced it — and the protocol is hashed so two runs either pool or visibly do not.

**Environment**: RL-ViGen (NeurIPS 2023 Datasets & Benchmarks), robosuite backend, tasks `Door` and
`Lift`, Panda arm, `OSC_POSE` controller. Pixel observations `(9, 84, 84)` uint8 = 3 stacked RGB
frames. Continuous action `(7,)`. Horizon 500, no early termination, so every episode end is a time
limit. Visual regimes: `train`, `eval-easy`, `eval-hard`. Ten scene ids; we train on scene 0 and
evaluate on 0–9.

**The twelve**: DrQ, DrQ-v2, CURL, RAD, SVEA, SODA, SGQN, ALDA (off-policy) and IDAAC, PPG,
IBAC-SNI, CTRL (on-policy PPO family), plus a uniform-random negative control.

## 2. Where the implementations come from

This matters because "is our X faithful?" has a different answer depending on the row.

| baselines | source |
|---|---|
| `drqv2`, `svea`, `sgqn`, `curl`, `drq` | **RL-ViGen's own implementations**, loaded by file path from the vendored upstream. We did not write them. |
| `idaac`, `alda` | ported from a sibling project (`gen-rebuttal/vigen-idaac`) that ran them on this same benchmark |
| `rad`, `soda` | a SAC stack recovered from this repo's own history, with the method written on top |
| `ppg`, `ibac_sni`, `ctrl` | **written here**, on a shared PPO core, because no usable implementation existed |

## 3. The state of the audit, and what is still soft

An audit was completed on 2026-08-10 (`PREMISES.md`, `FAITHFULNESS.md`). Its findings split
cleanly by how they were established, and **the briefs are aimed at the second category**.

**Established by measurement on the machine — treat as fact:**
- 173 distinct declared knobs across `Protocol` / `TrainConfig` / `SAC_DEFAULTS` /
  `idaac.Config` / `AldaConfig`; only 44 appear anywhere in `configs/vigen.yaml`.
- A 10× learning-rate split across arms, caused by `lr` being silently dropped for baselines whose
  builder does not recognise the key. Verified by constructing every agent and reading its
  optimizers.
- ~~The PPO family updates on 8-sample minibatches~~ — **FIXED 2026-08-10.** `num_steps` is now
  2048, giving 64 samples per minibatch, which matches IDAAC's own continuous configuration
  (Appendix E, "2048 steps, 1 process") exactly. `num_envs > 1` turned out not to be needed.
- ~~`nstep=3` applied to seven 1-step-canonical baselines~~ — **partly fixed.** RL-ViGen's own
  Table 2 says "N-step return — DrQ: 1, otherwise: 3", so n=3 is the benchmark's documented choice
  for robosuite and only DrQ was wrong. DrQ is now 1.
- ~~`Protocol.env_patches` stale; 13 modified files where four are declared~~ — **FIXED.**
  `env_patches` is corrected and pinned by a test; `--check` now diffs the whole vendored tree in
  both directions; the one load-bearing orphan (`algos/drq.py`) became patch P5.

**Established by a single research pass — verify before relying on it:**
- Canonical hyperparameters quoted in `FAITHFULNESS.md` for the *algorithms*. **RL-ViGen's own
  Tables 2 and 6 are no longer in this category** — they have since been read directly from the
  NeurIPS supplementary and every cell this project acted on is verified verbatim.
- Canonical hyperparameters for the individual algorithms, where they rest on a single reading.

**RESOLVED since this document was written** — do not spend effort re-deriving these:

- ~~SGQN `aux_lr = 0.3` vs canonical `3e-4`; is it a defect or a re-tune?~~ **Neither.** RL-ViGen's
  Table 6 specifies **8e-5**, and 8e-5 appears in all five of its benchmark tables. Their own
  `cfgs/sgqn_config.yaml` supplies 1e-4 via hydra, so upstream never runs at 0.3 — we hit the
  constructor default only because we bypass hydra. **Applied: 8e-5, quantile 0.9.**
- ~~SVEA's augmentation substitution~~ — **verified from source**: canonical
  `dmcontrol-generalization-benchmark/svea.py` uses `random_conv`; RL-ViGen uses `random_overlay`.
- ~~"No continuous adaptation of PPG / IBAC-SNI / CTRL exists"~~ — **refuted for PPG** (XuanCe ships
  `Gaussian_PPG`, itself unvalidated on continuous control) and IDAAC's Appendix E publishes
  continuous PPG hyperparameters. The claim stands for IBAC-SNI and CTRL.
- ~~RL-ViGen's own paper and supplementary were never audited~~ — **done.** Every Table 2 and
  Table 6 cell this project acted on is verified verbatim against the NeurIPS supplementary.
  Notable: reward shaping for robosuite is **never characterised anywhere**, and batch size, target
  tau and the exploration schedule are **absent for robosuite** — decide-and-record, not look-it-up.

**Still genuinely open** and worth an outside view: whether the four PPO-family arms are
scientifically reportable at all (IDAAC's own §6 names *"episode length variations"* as a condition
for expected gains, and we have a fixed 500-step horizon), and every item in
`docs/STATUS-AGAINST-THE-GOAL.md` §3b.

## 4. Constraints that shape what advice is useful

- **Hardware**: Apple M2 Pro (MPS, no CUDA) for development; Yandex DataSphere `gt4.1` (1× Tesla
  T4, 4 vCPU, 31 GB RAM) for real runs, verified working end to end.
- **Measured throughput**: ~78 environment steps/s on the T4. Rendering is ~12% of a step, physics
  ~88%, both CPU-bound — so the lever is packing runs per box, not a larger GPU. **500k frames is
  ~1.8 h of pure environment stepping per run.**
- **`num_envs = 1`** for the on-policy loop: RL-ViGen's robosuite calls `GlobalHydra.clear()` on
  every construction and needs its GL backend chosen before mujoco is imported, so environments
  cannot be built concurrently in one interpreter. **This turned out not to be a limitation worth
  engineering around** — IDAAC's own continuous configuration is *"2048 steps, 1 process"*, so one
  environment is the authors' setting. The fix was to raise `num_steps`, which is applied.
- Compute is real but finite. Advice of the form "tune each arm with a 50-run sweep" is not
  actionable; advice of the form "these three knobs matter and here is the published value or the
  cheapest defensible rule" is.
- **`action_repeat = 1`**, stated deliberately rather than inherited (RL-ViGen's config defaults to
  2 and no task config overrides it). Budgets are counted in environment frames with action repeat
  folded in.

## 5. What a useful answer looks like

- **Primary sources, quoted.** A config file line, a paper table cell, a specific commit. Not "it
  is generally accepted that".
- **Explicit uncertainty.** "UNVERIFIED" or "I could not confirm this" is more valuable than a
  plausible number. A wrong hyperparameter that looks right costs more here than an admitted gap —
  the whole audit exists because plausible-looking values turned out to be silently wrong.
- **Distinguish absence-of-evidence from evidence-of-absence.** If you searched for something and
  did not find it, say which searches you ran.
- **Say what would change our decision.** Each brief ends with a decision it feeds. Answer that
  decision, not just the literature.
- **Disagreement with the audit is welcome and useful.** `PREMISES.md` and `FAITHFULNESS.md` are
  provisional in exactly the places §3 marks as soft. If a claim there is wrong, say so plainly and
  show the source.
