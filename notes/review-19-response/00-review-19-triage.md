# Review 19: independent triage

Date: 2026-09-07. Review source: `notes/ai-review-19-external.md`.

This response checks review claims against the current tree. It does not treat the review
artifact's snapshot as current state. No remote job was launched. PPG/IDAAC C2 source files,
the artifact builder, mailbox, and `ext/` were not edited.

## Accepted and already closed

- **SODA auxiliary learning rate:** review 19 is correct. The generic parser default is `1e-3`,
  but the authors' `runnable/dmc_gb/scripts/soda.sh` passes `--aux_lr 3e-4`. The active
  `runnable/_launch/dmc_gb.sh` now passes that value for SODA. `docs/FAITHFULNESS.md`,
  `notes/CLAIMS-LEDGER.md`, and `notes/PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md` state the
  effective value. `tests/test_soda_source_contract.py` pins this source/launcher contract.
- **SODA mechanics:** source inspection supports the review's SAC base, 100-pixel render,
  84-pixel crop, Places overlay, predictor/EMA target, auxiliary frequency 2, batch 256, and
  target coefficient .005. Remaining SODA issue is empirical: no production-length CUDA
  competence/throughput/peak-memory result yet.
- **SGQN/SVEA publication-versus-release feature width:** review 19 found a real omission in
  the claims ledger. RL-ViGen publication common settings say `feature_dim=256` for methods other
  than DrQ(v2)/CURL; shipped SVEA/SGQN configs use `50` (`docs/FAITHFULNESS.md:141`,
  `RL-ViGen-upstream/cfgs/{svea,sgqn}_config.yaml:33-34`). Ledger rows now state this conflict.
  Execution remains the predeclared released-code profile; no silent switch to 256.
- **Host-qualified replay wording:** review's distinction is correct. Claims now remain scoped:
  a V100 600k profile can be non-evicting, while the base profile's approximately 300k cap is a
  recency ring. This is not a global claim that the RL-ViGen replay capacity is equivalent to 1M.

## Current-tree corrections to review 19

- **PPG snapshot was stale.** Review 19 correctly says `1×2048/32 minibatches` is the IDAAC
  authors' DMC comparator, not an OpenAI PPG paper setting. It incorrectly treats the supplied
  artifact's old PPG state as current. Production descriptor now passes `frame_stack=3` and keeps
  the explicit PPG-shaped `8×256`, `nminibatch=8`, `n_pi=32` adaptation
  (`datasphere/native/families.json:536-580`). This remains a continuous-action Door port, not
  published PPG or the IDAAC DMC comparator. No PPG C2 source was changed here.
- **IDAAC snapshot was stale.** Current descriptor is IDAAC-C2: one process, 2048 steps, 32
  minibatches, 10 PPO epochs, lr `3e-4`, gamma `.99`, entropy `0`, frame stack 3, linear decay
  (`families.json:247-373`). The primary-source reconciliation was corrected from the obsolete
  C1 description. Full-length C2 competence, resource, and remote validation remain open; C1
  evidence must not be reused as C2 evidence. No IDAAC C2 source was changed here.
- **Canonical comparator arms are not production prerequisites.** Review 19's RAD/SVEA/CURL/
  SGQN canonical-arm suggestions are useful sensitivity studies, not requirements for one
  predeclared RL-ViGen Door run. Current result names and caveats must identify RL-ViGen variants.

## Material unresolved findings retained

- **IBAC-SNI remains a hybrid adaptation.** Current production launcher selects the source-backed
  Impala trunk, `beta=1e-4`, and entropy `0`; current code still has a 64-dimensional, single-sample
  bottleneck and lacks CoinRun's 256-dimensional shifted-scale, 12-sample mixture-policy,
  weight-decay, and rectangle-UDA semantics (`runnable/_launch/ibac_sni.sh:113-134`,
  `torch_rl/bottleneck.py:33-40`, `model.py:147-181,264-275`). Review 19 is right that these
  are mechanism-level gaps, not harmless flags. Implementing them requires a separately designed
  continuous-action likelihood/augmentation port; no speculative change made here. Current name
  and result qualification must remain “continuous-action adaptation/hybrid,” not exact CoinRun
  IBAC-SNI. One process is an operational resource profile, not an upstream fidelity claim.
- **CTRL paper/release conflict remains correctly open** (C97). Keep released-code profile as
  operational default unless owner ratifies another profile.
- **Evaluator geometry certification:** review's recommendation is valid. Declared geometry is
  not fully independent runtime/model-shape certification for every family. Treat as a production
  hardening item, not evidence that current recorded rows are validly reinterpreted.
- **Source precedence and manifest labels:** current docs record provenance and variant names, but
  result metadata still needs explicit source-target labels across all rows (canonical paper,
  authors' release, RL-ViGen paper, or RL-ViGen release). Do before production freeze.
- **IDAAC resource certification:** C2 changed compute shape; old throughput/memory estimates are
  not C2 certification. Measure before scheduling production.
- **Statistics:** report all algorithms and predeclared contrasts; treat “best in group” as
  descriptive unless selection-aware inference is added.

## Rejected or narrowed claims

- “SODA is still using `1e-3`” is rejected as stale after source and launcher verification.
- “PPG is still one-frame in the production path” is rejected; direct source default is one frame,
  but production descriptor explicitly passes three.
- “IDAAC C2 has not been built” is rejected; “IDAAC C2 has not had a full-length validation run”
  remains true.
- “One process proves IBAC-SNI is the faithful setting” is rejected. It is currently the measured
  runnable resource profile; upstream torch_rl default is 16, and 16-process Linux/EGL failure is
  an operational fact, not a method-fidelity proof.

## Verification

- `python -m pytest -q tests/test_docs_not_stale.py` — passed (`sss..........`).
- `python -m pytest -q tests/test_soda_source_contract.py tests/test_docs_not_stale.py` — passed
  after this response's documentation edits (`sss..............`).
- `git diff --check` — passed.
