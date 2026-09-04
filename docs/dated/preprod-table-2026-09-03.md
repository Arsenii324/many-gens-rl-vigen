Written 2026-09-04 by `scripts/preprod_table.py`.

# Pre-production validation table

| baseline | frames | regime | eps | return | success | estimator | stack | render |
|---|---|---|---|---|---|---|---|---|
| `ctrl` ⚠ | 10000 | eval-easy | — | 1.326 ⌊ | 0.00 | SAMPLE | 1 | egl |
| `ibac_sni` | 10112 | eval-easy | 10 | 1.740 ⌊ | 0.00 | SAMPLE | 1 | egl |
| `idaac` | 9216 | eval-easy | 10 | 3.015 | 0.00 | SAMPLE | 1 | egl |
| `ppg` | 10240 | eval-easy | 10 | 0.772 ⌊ | 0.00 | SAMPLE | 1 | egl |
| `alda` | 10000 | eval-easy* | — | 0.867 ⌊ | 0.00 | mode | 3 | egl |
| `curl` | 10000 | eval-easy | — | 11.706 | 0.00 | mode | 3 | egl |
| `drq` | 10000 | eval-easy | — | 1.100 ⌊ | 0.00 | mode | 3 | egl |
| `drqv2` | 10000 | eval-easy | — | 21.884 | 0.00 | mode | 3 | egl |
| `rad` | 10000 | eval-easy | — | 9.664 | 0.00 | mode | 3 | egl |
| `sgqn` | 10000 | eval-easy | — | 2.348 | 0.00 | mode | 3 | egl |
| `soda` | 10000 | eval-easy | — | 1.034 ⌊ | 0.00 | mode | 3 | egl |
| `svea` | 10000 | eval-easy | — | 42.915 | 0.00 | mode | 3 | egl |

**12 of 12 baselines present**; all twelve present

**This table may not be sorted by return.** Three baselines report a SAMPLED return (`idaac`, `ibac_sni`, `ppg`) and nine report a mode return; the two are different quantities. Four receive a single frame and eight receive three, which on a manipulation task makes them velocity-blind — a different POMDP, not a weaker algorithm (C2). Rows are grouped by stack for that reason.

**Budgets are equal by intent, not exactly** (R4): `ppg` floors to a 2048 quantum and `ctrl` to a multiple of `num_envs`, so their frame counts differ from the requested budget by construction. The `frames` column is what actually executed.

**⌊ marks a return at or below the random-policy floor of 1.82** (C55: uniform random, 400 episodes, zero successes on Door). At this budget that is 6 of 12: `ctrl`, `ibac_sni`, `ppg`, `alda`, `drq`, `soda`. **No retention ratio may be computed from a floored row.** A ratio over a near-floor denominator is not a small number, it is an undefined one that looks like a number (C18, RIGOR.md). This is the expected result of a 10k budget and is why the pass validates the pipeline rather than measuring generalisation.

**`alda`'s regime is a MAPPING, marked `*`.** It reports dmcontrol-generalization-benchmark's own names — `color` and `distracting` — which `normalize_curves.read_alda` maps to the nearest RL-ViGen regime and explicitly labels *a mapping rather than an identity*; the original key survives in the record's `native` block. The mapping is reasonable (colour randomisation ≈ eval-easy, distracting background ≈ eval-hard) and it is still not the same generator, so an alda row and a native row under one regime label are close neighbours, not the same condition.

**`ctrl`'s row is NOT comparable with the others and is marked accordingly.** `audit_comparability_seam.py::reported_estimator` states that the estimator axis is uniform *conditional on only ever reading the evaluation number*, and warns that training-curve numbers are a different estimand which pooling would corrupt. `ctrl`'s cell reports `Eprew200`/`Eprew0` — training-curve numbers — because its fixed-policy evaluator is unbuilt: `evaluate_ppo.py` calls a discrete-only helper while `algo.select_action` already handles both action spaces. So this pass violates that condition for exactly one baseline. Until the evaluator is adapted, `ctrl` is a pipeline check only.

**A blank `eps` is the symptom of that, not a formatting gap.** `ctrl` never performs a terminal evaluation: `train_ppo.py` steps an ID and an OOD test env *inside* the training loop and reports `Eprew200`/`Eprew0`, a running mean over a trailing window. Every other baseline here reports a fixed-N evaluation of the final policy. A windowed running mean and a terminal N-episode mean are different estimators of different quantities: the first is smeared over the policies of the last N episodes, the second measures only the policy that was saved. Comparing them as if they were the same column overstates `ctrl` when it is improving and understates it when it has just diverged.

**`render` must be identical across rows to compare them at all** (C95): a container-trained policy evaluated under a different rasteriser reads 12–14x low. Any row showing `glfw` beside rows showing `egl` is not comparable.
