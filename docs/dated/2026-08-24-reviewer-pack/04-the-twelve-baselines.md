# The twelve baselines, one at a time

**Written 2026-08-24. Dated snapshot, not a living document.** Fidelity states are read from
`../../FAITHFULNESS.md` §0; cell status is re-derived from `results/regime-retention/` for this
document. Where the two disagree, the artifact wins and the disagreement is noted.

## The headline, stated per baseline rather than in aggregate

**Nine of the twelve have no measured cell.** The project's own documents say "eight"
(seed brief §5.5); re-deriving from `results/regime-retention/*__train.json` gives three baselines
with grids — `drqv2`, `drq`, `svea` — so nine without. **MEASURED.**

The confusion has a specific cause worth knowing: `results/cell-*` directories exist for eight
baselines and look like cells. They are not. Every one contains only `watcher.log` and
`frames/*.npy` — training-distribution witness captures — and **not one contains an `eval.csv`, a
snapshot, or a `train.csv`.** Several are empty or near-empty (`ctrl`, `ppg`, `rad` seed 0 hold a
log and nothing else; `rad` seed 1 holds zero files).

## The four with evaluation evidence

### `drqv2` — the reference method, and the only one with a usable retention number
- **Source:** RL-ViGen upstream.
- **Fidelity:** replay 1e5-vs-1e6 divergence *retracted*; stddev schedule was read from the wrong
  tier, **fixed 2026-08-10**. Severity was **high**, not low as first recorded.
- **Cells:** seed 6 (`cell55k`) and seed 7 (`cell_drqv2_s7`), both 50k frames, plus three grids of
  one archived run at 50k/100k.
- **What it shows:** seed 6 solves **59/200** in the training regime; seed 7 solves **0/200**. Same
  code, same budget, same task. This pair is the project's clearest evidence that n=1 is
  insufficient, and no seed-count calculation has been done.
- **Caveat:** the archived checkpoints are the ones C54 shows were not trained on their declared
  distribution, and two of the three archived grids are a byte-identical replicate (see
  [03](03-what-was-measured.md) §2).

### `svea` — the best retention, and the most suspicious fidelity state
- **Source:** RL-ViGen upstream.
- **Fidelity:** **high severity.** It **uses SODA's overlay augmentation, not SVEA's random
  convolution**, and is DrQ-v2-based rather than SAC-based. So "SVEA" here is a method the SVEA
  paper would not fully recognise.
- **Cell:** seed 1, 50k. train 97.50 (6/200), eval-easy 85.51 (3/200), ratio **0.877** — by far the
  highest of the four fresh cells.
- **Read with care.** 0.877 looks like excellent generalization. It is a ratio of two shaping
  plateaus: 6 successes out of 200 in the denominator, never more than 1/20 on any single scene.
  The tool refuses this denominator (`MIN_DENOM_SUCCESS = 0.25`) precisely because an earlier
  version did not, and produced a 0.947 that read as robustness.

### `drq`
- **Source:** RL-ViGen upstream. **Fidelity:** low-medium — lr 1e-4 vs 1e-3; n-step fixed 2026-08-10.
- **Cell:** seed 1, 50k. train 79.29 (**0/200**), eval-easy 22.18 (1/200). Yields no retention
  number: the denominator never solves the task.
- **Operational note:** enabling TensorBoard breaks this baseline — `algos/drq.py:328` calls
  `dist.entropy()` on a `SquashedNormal` under `if self.use_tb:`. It runs with `use_tb=False`.

### `random` — not a baseline, the control
- Measured floor: **1.82** (`train`), **1.85** (`eval-easy`), **0 successes in 400 episodes**.
- Its retention ratio is **1.02**, which is the anchor that makes C65's contamination screen
  readable: a policy with no training distribution to lose sits at 1.

## The nine with no cell

### `sgqn` — carries a live false certification (C64)
- **Fidelity as documented:** `aux_lr` 0.3 vs canonical 3e-4 — a 1000× error on the *shared
  encoder* — "**FIXED 2026-08-10**", severity **critical**.
- **What actually runs (MEASURED, 2026-08-24):** the fix was applied to `configs/vigen.yaml:82`,
  which configures the **retired `rlgen/` port**. The clone runs upstream's `train.py` through
  hydra, which reads `RL-ViGen-upstream/cfgs/sgqn_config.yaml:54,56` → **`aux_lr: 1e-4`,
  `sgqn_quantile: 0.93`**. `grep -n 'aux_lr\|quantile' runnable/_launch/rlvigen.sh scripts/run_cell.sh`
  returns nothing, so no override exists on the launch path.
- **So the doc's "ours" column is wrong in both directions**: not 0.3 (hydra is not bypassed, so the
  constructor trap is never reached) and not 8e-5 (that fix cannot reach a clone run).
- **The live question:** upstream's shipped 1e-4/0.93 disagrees with RL-ViGen's *own* paper Table 6
  (8e-5/0.9). Which should the clone run — the null, or the paper? Undecided. This is C64.
- **Cell:** none. `results/cell-sgqn-Door-seed1` holds a watcher log and one captured frame.

### `curl`
- **Fidelity: high.** DrQ-v2-based not SAC; lr 1e-4 vs 1e-3; paper and code disagree five ways.
- **Cell:** none. Two directories exist (seeds 1 and 2) with captured frames only.
- **Blocker:** fails on MPS with `scatter: index -1`. `smoke_all.sh:15,49` works around it with
  `device=cpu`, and CPU is ~60× slower for conv work here, so a 55k CURL cell is not feasible
  locally. This exact failure has been rediscovered **four** times; C52 records the error string
  verbatim.

### `rad`
- **Fidelity: medium.** Ours, on a recovered SAC. n-step 3 vs 1-step; `random_shift` rather than the
  paper's crop/translate.
- **Cell:** none — both directories are empty or hold a log only.
- **Note:** RAD is the one baseline verified to train end-to-end on a Kaggle T4 with real robosuite
  envs, so it is the cheapest candidate for the next remote cell.

### `soda`
- **Fidelity: low.** Recovered from history; aux lr follows code (1e-3) not paper (3e-4). **Cell:** none.

### `alda`
- **Fidelity: low** — faithful port, but its benchmark is extrapolated from DMControl-GB to
  robosuite, which is a different claim from "faithful to the paper on this task".
- **Cell:** none. Its checkpoint cadence is `checkpoint_n_steps = 50_000`; note that an earlier
  reading took the cadence from a config file its entry point does not execute.

### `idaac`
- **Fidelity: high.** Rollout 256 vs the paper's 2048 (continuous); 8-sample minibatches.
- **Cell:** none.
- **Three unresolved audit flags**, recorded in `INTEGRATION-DELTA.md` but never promoted to register
  entries: a `_LevelSeed` comment that C49 refutes with no corresponding tag in the code; an eval env
  that reuses training env #0's seed and a literal `scene_id=0`; and `model.py:379-383` forwarding
  `num_actions` with no assertion.
- Its instance-invariance loss is **inert in this setting** — a "handicap recorded, not removed",
  which is precisely the divergence class with no home in the document system.

### `ppg`, `ibac_sni`, `ctrl` — the three with no continuous ground truth anywhere
- **`ppg`: high.** Rollout 256 vs 65 536; lr 1e-4 vs 5e-4; **the continuous head has no reference
  implementation.**
- **`ibac_sni`: medium.** β and λ match the paper; **continuous head has no reference.** Separately,
  its model is **227× larger** than intended (C3) — another recorded-not-removed handicap.
- **`ctrl`: high, and structural.** `L_clust` is **absent**, and positives are drawn from the same
  partition rather than a neighbouring one. That is not a hyperparameter divergence; it is a
  different algorithm.
- **Cells:** none. `ctrl` and `ppg` exit 3 from `run_cell.sh` with a stated reason.
- **Why this trio matters most to a reviewer:** all three required us to *author* a continuous-action
  head, and a survey of fifteen RL libraries found no prior art to check against — the PPG upstream's
  only Gaussian is unreachable dead code at fixed σ=1. So for three of twelve baselines, the thing
  being measured is partly our own construction, with nothing external to validate it.

## What this table means for the comparison

The intended deliverable is a twelve-row table. **Three rows have any evidence; one has a retention
number that survives its own guards, and that one rests on four of ten scenes selected post hoc.**
Everything else is fidelity bookkeeping for runs that have not happened.
