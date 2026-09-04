"""IBAC-SNI (Igl et al., NeurIPS 2019, arXiv:1901.10902), rebuilt base-first 2026-08-16.

## The formula for this baseline

    base (`joonleesky/train-procgen-pytorch` @ `1678e4a`, vendored verbatim at
          `_upstream_1678e4a/`, extracted with `git show` from the *commit*)
  + N  scoped edits, each cited inline and each visible as a `diff` against that directory
  + M  adaptations forced by the target (84x84x9 uint8, 7-DoF continuous, one env)
  + K  this project's on-policy learner contract
  = this module.

**Measured textual descent from the base, 2026-08-16** — `difflib.SequenceMatcher` over code
lines (blank lines, comments and the module docstring excluded), base lines surviving verbatim:

| File | Base | Descent | What that actually means |
|---|---|---|---|
| `misc_util.py` | `common/misc_util.py` | **100%** | byte-identical; imports and runs unmodified |
| `model.py` | `common/model.py` | **99%** | a genuine copy + 2 scoped edits (E1 input size, E2 uint8 scaling) |
| `policy.py` | `common/policy.py` | **44%** | partial descent — see below |
| `storage.py` | `common/storage.py` | **3%** | **not a copy** — see below |
| `algo.py` | `agents/ppo.py` | **7%** | **not a copy** — see below |
| `config.py` | `hyperparams/procgen/config.yml` | n/a | `.py` vs `.yml`; every value re-sourced instead |

**An earlier version of this docstring claimed "every file here started as a byte-copy." That was
false for three of five files, and was written before the diff was run** — an assertion where a
measurement was available, which is the specific failure this module exists to correct. Corrected by measuring.

Why the three are low, stated rather than excused:

- **`policy.py` (44%)** — the base contributes only 32 code lines (`CategoricalPolicy`: the head
  layout, the `orthogonal_init` gains, `is_recurrent`), and 14 survive. Everything else is the
  bottleneck and the sample-mixture, whose authority is **a different reference**
  (`ext/IBAC-SNI/coinrun/coinrun/policies.py`). A file implementing IBAC-SNI cannot textually
  descend from a PPO host that contains no IBAC-SNI. Two-reference descent, cited per line.
- **`algo.py` (7%)** — the base's `PPO` is an *agent* that owns the env, the rollout loop, the
  logger and checkpointing; this is a *learner* that owns only the update, because the loop is
  the shared harness. `optimize()`'s skeleton is followed statement for statement (epoch loop,
  generator, clipped value loss, accumulate-then-clip-then-step) but three methods are dropped and
  the loss body comes from `ppo2.py:76-153`. Structural fidelity is real; textual descent is not
  the measure of it here.
- **`storage.py` (3%)** — **the weakest claim in this module, and the one to distrust first.** It
  was *not* rebuilt from the base; a pre-existing buffer was kept and re-anchored, and its
  equivalence to the base's GAE is established **numerically, by running both**
  (`tests/test_ibac_sni_base_parity.py`), not by textual descent. That is a real check and it
  caught a real drift (the `1e-5`/`1e-8` epsilon). It is still equivalence-by-test rather than
  correctness-by-construction, which is a weaker thing — see `docs/INTEGRATION-DELTA.md` on why
  that distinction is not a grading nicety.

## What this replaced, and why it was discarded rather than patched

The previous module was a **Construction** — written from understanding while a copyable base sat
on disk. It was tested and it ran. It was discarded anyway, because a passing test on an artefact
with no settled provenance establishes that the artefact is self-consistent, not that it is
IBAC-SNI. Rebuilding surfaced defects the tests could not have:

1. **The value head was mixed under SNI.** The reference overwrites *both* value tensors to the
   deterministic `fc(h_vf, 'v', 1)` (`policies.py:161`) with the comment *"Use deterministic value
   function for both as VIB for regression seems like a bad idea."* The old module computed
   `sni_lambda*v_det + (1-sni_lambda)*v_stoch`, and `registry.py` advertised that as a feature.
2. **sigma was `exp(clamp(log_sigma, -10, 2))`.** Both first-party paths use `softplus`, neither
   clamps, and CoinRun offsets by -5.0 — so std starts at ~0.0067, not 1.0. ~150x different noise
   at initialisation, plus a zero-gradient plateau that softplus does not have.
3. **No L2 term at all.** Every headline run passes `--l2 0.0001` (`ppo2.py:153`).
4. **One sample instead of 12.** `--nr-samples 12` in every headline run; the policy is a mixture
   over those draws (`policies.py:141-147`).
5. **The KL was in nats, not bits.** `beta = 0.0001` is quoted from a codebase that divides by
   `log(2)` (`policies.py:64`), so the same numeral meant a ~1.44x different penalty.
6. **`sni_lambda` was a tunable knob.** The reference has no such flag — `Config.SNI` is a
   boolean and the weight is a hardcoded `/2.`. The knob invented a degree of freedom.

1 and 2 were found by hand and independently confirmed by an adversarial audit against the
reference; 3-6 came out of reading the reference's own headline run commands.

## Scope exclusions, declared

- **Non-recurrent.** `IBACPolicy` raises on `recurrent=True`. Every config block in the base's own
  `config.yml`, and both of DZ's IBAC blocks, set `recurrent: False`; this project's shared
  on-policy trainer threads no hidden state.
- **`entropy_coef = 0.0`**, uniform across all four on-policy baselines here, so **SNI's
  entropy-mixing half is inert** and only the policy-gradient mixing is live. See `config.py` and
  `docs/FAITHFULNESS.md`.
- **`sni=False` is untested.** The reference's plain branch aliases `pd_run` to `pd_train`
  (`policies.py:186-189`), which this module does not implement — it would be a second code path
  with no run behind it. `sni=True` is the configured and only supported setting.

## Tier

**T4 (structural accounting) for the algorithm**, with two exceptions that are real and bounded:
`storage.py`'s GAE has a numerical equivalence test against the base's own `Storage`, and
`normalize_reward` was verified 2026-08-14 by running the reference. No weight-transplant check
against the TF reference exists — crossing TF 1.x is not attempted here. Stated, not implied:
`docs/STEP-ZERO.md` gate 2.
"""
