# Integration delta — everything in this code that is ours, not the original authors'

Started 2026-08-16, retrospective to the whole project. **A log, appended to, never rewritten.**

## What belongs here, and what does not

One rule: **if a reader would be wrong to attribute it to the paper's authors, it goes here.**

- *Not* an entry: "this module is based on repo X." A whole externally-provided implementation is
  a **base state**, not new information. `docs/ORIGINAL_LOCATIONS.md` records those.
- *Is* an entry: every change, addition, removal, substitution, or value choice made **relative to
  that base** — including **back-merges**, where reference behaviour is restored over a local
  version. A back-merge is authored information: someone decided the reference was right *here*
  and the local code wrong, and that decision can be wrong.

Branch-off and research work is not tracked live. **A decision is logged when it is reached.**

## Why this is not a second copy of `FAITHFULNESS.md`

They cover nearly the same set, and that is not an accident: **"code we authored" and "divergence
from the paper" are close to isomorphic.** Even "just run algorithm A on environment B" is both at
once — it is a script someone wrote, *and* it is a divergence the moment a scaling, a horizon, or
a hyperparameter departs from A's own setting. There is no third category of neutral glue.

So the two documents are one set under two keys, and this one adds the column the other lacks:

| Document | Keyed by | Answers |
|---|---|---|
| `FAITHFULNESS.md` | algorithm | "would this baseline's number be fair to call that method's result?" |
| `REGISTER.md` | finding | "what was discovered, when, and what was decided?" |
| `DECISION_LOG.md` | semantics | "what does this value/argument *mean*?" |
| **this file** | **authored element** | **"who wrote this, and how do we know it's right?"** |

**The correctness column is the point, and it is binary.**

The grading was first written with four tiers — built-in, verified-after, argued, unverified — as
if "we checked afterwards and it passed" were a respectable middle. **That was wrong, and it was
wrong in the specific way this whole standard exists to prevent.** An element whose correctness
can only be established *after* it is written has already cost what it was going to cost: the
abstraction was applied without its correctness being visible, and that produces the endless
patch-when-it-leaks cycle that no amount of downstream testing ends. The test tells you *this
instance* survived. It does not repair the process that produced it, and that process will leak
again somewhere a test does not happen to look.

So there are two categories:

- **INTRINSIC** — correctness is *visible at the point of the edit*, where the abstraction meets
  the original. The edit is derived from the reference (or provably reduces to it), so it could
  not have been silently wrong. A test still exists, but the test **confirms**; it does not
  **discover**.
- **NOT INTRINSIC** — correctness was, or would have to be, discovered afterwards. **A passing
  test does not promote an entry out of this category.** It only records that the leak has not
  been observed yet.

Everything in the second category is a debt, whether or not it is currently green. That is the
deliverable of this file; the first category is bookkeeping.

Two things this framing is deliberately *not* saying. It is not "never write anything you cannot
derive" — some elements have no reference to be derived from (see `I9`, `M4`), and refusing to
act would be worse than acting with the gap named. And it is not a claim that tests are
low-value; the tests here caught two real defects. It is a claim about **where in the process the
correctness argument has to live** — at the edit, against the original — and about not letting a
green suite stand in for having put it there.

---

# `ibac_sni` — rebuilt base-first, 2026-08-16

Base: `joonleesky/train-procgen-pytorch` @ `1678e4a`, vendored verbatim at
`rlgen/algos/ibac_sni/_upstream_1678e4a/`. Semantic authority for the IBAC-SNI mechanism:
`ext/IBAC-SNI` (`microsoft/IBAC-SNI` @ `6b3a58b`), the authors' own release.

### Back-merges from the authors' code over DZ's port

DZ's `agents/ppo_ibac.py` + `common/policy_ibac.py` are a third party's re-derivation from the
paper. Each row below is a place where the authors' own code was restored over it. **Each is
authored information — a judgement that the reference is right here.**

These are the strongest rows in the file: each is a value read directly out of the authors' code,
so correctness is visible at the edit and the tests only confirm it.

| # | What was restored | DZ's port had | Correctness | Evidence |
|---|---|---|---|---|
| I1 | Value head reads the **deterministic** latent only; no value mixing under SNI | `sni_lambda*v_det + (1-sni_lambda)*v_stoch` | **INTRINSIC** — the reference states it outright, *with its own reason*. Test confirms, red-green | `policies.py:161` + the authors' comment *"Use deterministic value function for both as VIB for regression seems like a bad idea"*; `ppo2.py:76-81` |
| I2 | sigma = `softplus(rho - 5.0)` | `exp(clamp(log_sigma, -10, 2))` | **INTRINSIC** — both first-party paths agree on softplus. Test confirms, red-green | `policies.py:58`; `torch_rl/bottleneck.py:33-34` |
| I3 | One `Linear(in, 2*out)` split in half | two separate `Linear`s | **INTRINSIC in form** — both references do exactly this. The *consequence* (correlated init) is not derived, only the form | `policies.py:56-57`; `bottleneck.py:26` |
| I4 | L2 term `sum_w \|\|w\|\|²/2 × 1e-4` over non-bias params | absent entirely | **INTRINSIC** — term and its parameter filter read from the loss line itself | `ppo2.py:116,128,153`; README headline runs pass `--l2 0.0001` |
| I5 | `nr_samples = 12`, policy is a mixture over the draws | one sample | **NOT INTRINSIC** — the count is read off the reference, but the reference's mixture is over **Categoricals**; a mixture over diagonal Normals is a different object whose equivalence is not derived. Nothing here establishes it is the right continuous analogue | README `--nr-samples 12`; `policies.py:141-147` |
| I6 | KL in **bits** (`/ln 2`) | nats | **INTRINSIC** — a unit conversion, derivable in one line, and required for the quoted `beta` to mean what it meant | `policies.py:64` |
| I7 | `sni_lambda` knob **removed**; the weight is a hardcoded `/2` | tunable `sni_lambda` | **INTRINSIC** — removing a degree of freedom the reference does not have cannot introduce an error | `ppo2.py:104,107`; `config.py` has no lambda flag |
| I8 | Post-bottleneck `relu` on **both** sample and mean | absent | **INTRINSIC** — read from the line that does it | `policies.py:104-105` |
| I9 | Policy-head `init_scale = 1.0` | `0.01` | **NOT INTRINSIC — and unresolvable.** The reference reaches 1.0 only through `tf.AUTO_REUSE` construction order. Whether that is design or accident **cannot be determined from the code, at all**. Fidelity to observed behaviour decided it; no test can settle it, so no test is claimed | `policies.py:140` vs `:164`; `ppo2.py:63`; `reuse=AUTO_REUSE` at `:133` |

### Edits over the base (N)

| # | File | What | Correctness | Evidence |
|---|---|---|---|---|
| E1 | `model.py` | `ImpalaModel` accepts a non-64 input; `_impala_flat_dim` replaces the hardcoded `32*8*8` | **INTRINSIC** — the formula *provably reduces to the base's own constant* at 64, asserted at import. Correctness is legible in the edit; the weight-transplant test confirms | `common/model.py:102` |
| E2 | `model.py` | `forward` accepts uint8 and scales by 255 | **INTRINSIC** — identical arithmetic, moved seam. Test shows uint8-to-ours equals prescaled-float-to-base | base scaled in `procgen_wrappers.py:365-377`, absent from this harness |
| E3 | `storage.py` | advantage-normaliser epsilon `1e-5` → `1e-8` | **The repair is INTRINSIC** (adopt the base's own constant) — **but its existence is evidence the original edit was not.** A drift of this kind is invisible to inspection and was found only because a parity test happened to exist. Logged as a defect in how the file was first written, not as a success | `common/storage.py:69` |
| E4 | `misc_util.py` | **nothing** — byte-identical copy | **INTRINSIC** — zero edits cannot be wrong; sha256 asserted | — |

### Adaptations forced by the target (M)

Adaptations are where intrinsic correctness is hardest, because the target differs from anything
the reference ran — there is, by construction, no original to derive from for some of them. Naming
which ones is the point.

| # | What | Correctness | Evidence |
|---|---|---|---|
| M1 | Discrete `Categorical` head → diagonal `Normal`, state-independent `logstd` | **INTRINSIC by delegation, one step weakened** — the reference does not hand-write a head, it calls `make_pdtype(ac_space)`, so the Box branch *is* the reference's own answer for continuous actions. Weakened because that branch was read from `openai/baselines` **over the network**, not from this disk | `policies.py:123`; baselines `distributions.py::DiagGaussianPdType.pdfromlatent` |
| M2 | `in_channels` 3 → 9 (3 stacked RGB frames) | **INTRINSIC** — the parameter already existed; zero edits | `common/model.py:96` |
| M3 | Truncation-bootstrap folded into the stored reward | **INTRINSIC by corroboration** — not derived from *this* base (which has no truncation concept at all), but ALDA's own reference implements the general form of which this is the Door/Lift special case. Test pins both that it fires and that it does not leak past the boundary | `docs/PREMISES.md` P4; `ALDA_Official/trainers/alda_trainer.py:616` |
| M4 | ~~`init_log_std = -1.0`, not baselines' `0.0`~~ **STALE — REFUTED 2026-09-03, see the note below the table** | **NOT INTRINSIC** — a deliberate departure with no reference behind it. The mitigation is *uniformity*, not correctness: all four on-policy baselines use it, so it lands as a systematic offset rather than selectively (`STEP-ZERO.md` gate 3). Uniformity makes an error **detectable**; it does not make it **absent** | `config.py`; checked across `idaac`/`ppg`/`ctrl` |
| M5 | Recurrent path **removed** (raises) | **INTRINSIC** — no config block in the base or DZ's blocks enables it; removing unreachable code cannot change behaviour | `hyperparams/procgen/config.yml` |
| M6 | `sni=False` **refused**, not silently run | **INTRINSIC** — the reference's plain branch aliases `pd_run` to `pd_train`, which this module does not do; refusing a configuration you have not implemented cannot produce a wrong number | `policies.py:186-189` |

**M4 is refuted, 2026-09-03, and three independent sources agree against it.** The row claims a
deliberate departure to `init_log_std = -1.0`. **Every constructed continuous head in this tree
initialises it to ZERO** — `ibac_sni/torch_rl/model.py:143` `nn.Parameter(torch.zeros(...))`,
`ctrl/models.py:129` and `:254` `nn.initializers.zeros`, `idaac/distributions.py:89`
`AddBias(torch.zeros(...))`. That is precisely "baselines' `0.0`", the thing M4 says we departed
from.

**Two corroborations that did not come from reading the same file again.** `ppg/train.py:104`
carries an unrelated comment recording that *"log_std = 0 gives exactly 9.932570"* nats of entropy;
and the pre-production `ibac_sni` cell logged **9.944** at its first update — one update of drift
from that figure. So the code, a sibling baseline's own arithmetic, and a live measurement agree,
and the ledger row does not.

**Most likely cause, stated as a hypothesis rather than a finding**: M4 describes the deleted shared
`onpolicy_ext.py` era, before these became hermetic clones. If so the row was true when written and
was never retired when the module it described was.

**Why it is corrected rather than deleted.** A faithfulness ledger that quietly drops a refuted row
teaches nothing; this one now records that *an adaptation table can outlive the code it describes*,
which is the same failure mode as a stale count and is why `tests/test_docs_not_stale.py` exists for
the register. **Recorded consequence**: M4 was the only entry claiming a non-zero log-std
initialisation, so [C61](CONSTRUCTION.md#c61)'s entropy analysis — which assumes sigma starts at 1.0
— is unaffected and in fact rests on the corrected value.

### Consequences we created, recorded because they are easy to miss

| # | What | Status |
|---|---|---|
| C1 | `entropy_coef = 0.0` (project-uniform) makes **SNI's entropy-mixing half inert** — only the policy-gradient mixing is live | **NOT INTRINSIC, and the clearest leak in this module.** A value chosen for *cross-baseline comparability* silently disabled half of *this algorithm's* mechanism. Neither decision was wrong locally; the interaction was invisible from either. Exactly the failure mode of a decision made without tracing what the abstraction under it is for. Found by writing the loss out and reading it, not by any test — and no test would have caught it, because the code is doing precisely what it says |
| C2 | The whole IBAC-SNI mechanism is **T4** — no weight-transplant check against the TF 1.x reference exists | **NOT INTRINSIC, capped by declaration.** The only numerical checks are against the *PPO host*, never against IBAC-SNI itself. Declaring the cap is honest; it does not narrow the gap |
| C3 | `storage.py` retains **3%** textual descent from the base (measured, `difflib`) — it was re-anchored, not rebuilt | **NOT INTRINSIC.** Its GAE equivalence is established by *running both*, which is the definition of correctness discovered afterwards. Real and it caught `E3` — and still the weakest structural claim in the module, flagged as the first thing to distrust |

---

# Shared harness — ours by definition

`RL-ViGen-upstream` supplies `robo_make`; everything else in `rlgen/envs.py`,
`trainer*.py`, `replay.py`, `agents.py`, `registry.py` is authored here.

| # | What | Kind | Correctness | Evidence |
|---|---|---|---|---|
| H1 | GLFW library-path resolution on macOS (`PYGLFW_LIBRARY` probing Homebrew paths) | our own invention | **verified** — real robosuite now constructs; first genuinely green suite | `rlgen/envs.py` |
| H2 | Eval passes `mode`/`scene_id` to `robo_make`; upstream's own `train.py` **never does**, silently building a `train`-regime env whatever scene was asked for | bugfix over reference | **verified** — `test_eval_modes_actually_look_different_from_train` | `PREMISES.md` P1 |
| H3 | Truncation-bootstrap: `discount` is **not** zeroed at a time limit; upstream's `Gym2DMC.step` sets `discount=0.0` unconditionally | bugfix over reference | **verified** for `ibac_sni` (M3); **argued** elsewhere | `robo_wrapper.py:35-40`; `REGISTER.md` 2026-08-15 |
| H4 | Reward-normalizer split: each baseline's own normalizer feeds *training*; `rewards_raw` feeds *measurement* | our own invention | **verified** — 3 of 4 normalizers checked by running the reference | `REGISTER.md` 2026-08-14 |
| H5 | Hard frame-budget stop; a rollout cut short is not used for an update | our own invention | **argued** — so all curves end at the same x | `trainer_onpolicy.py` |
| H6 | Each learner declares `storage_cls`; the trainer previously hardcoded IDAAC's buffer for *every* on-policy baseline | bugfix over our own earlier code | **verified** — the hermetic buffers were unreachable before this | `REGISTER.md` 2026-08-14 |
| H7 | Frame stacking to 9 channels | adaptation | **argued** | `envs.py` |

---

# Other baselines — retrospective, from 77 tagged sites plus the docs

**Coverage is honest, not complete.** The mechanical sweep below is a `grep` over the tags this
project already writes (`[OURS]`, `[CA]`, `[E]`, `[F:Rn]`, `DEVIATION`, `CHANGED`, `ADAPTATION`),
which is exhaustive *for tagged* content. **Untagged authored content is not yet swept for these
nine baselines** — see "What this file does not yet cover".

| Baseline | Authored elements (tagged) | Notable |
|---|---|---|
| `idaac` | 29 sites — the largest, because **no official continuous IDAAC exists anywhere**, so essentially the entire continuous surface is authored | `[OURS]` on: value-clip placeholder (Q2 open), KL-early-stop epoch cutoff `[F:R16]`, order-pair anchors per minibatch, `init_log_std=-1.0` (explicit `DEVIATION` from `[IK]`'s `AddBias(zeros)`), mean-head gain, diagnostics cadence |
| `alda` | 13 sites | `DEVIATION` from `[A]`'s 64×64 (forced by `robo_make`); reward clipping present where **neither** `[A]` nor `[RLV]` clips (`[OURS]`, no source); `DEVIATION` from single-env for wall-clock; `utd=0.25` baked in against the sibling's stale `1.0`; **no `buffer.py` at all** — uses the shared `replay.py`, so the sibling's `BufferVerifier` guard has no equivalent running here |
| `ppg` | 7 sites | `[OURS]` minibatch count (reference's `nminibatch=8` rejected for this project's batch scale); `aux_mbsize` likewise; `[CA]` entropy/log-std/width. **Still a Construction written from understanding while `ext/phasic-policy-gradient/` sat on disk — the next rebuild** |
| `ctrl` | 8 sites (+ model) | Every file authored (JAX→PyTorch). `protos` clean-forward-call instead of the identity-matrix trick; MYOW same-partition simplification; `action_mlp` fed the raw continuous vector; **two real bugfixes found by the T1 transplant** (flatten order, maxpool pad value = −inf) |
| `rad` | 1 | `DEVIATION, DECLARED` on `random_crop` render size |
| `soda` | 1 | `DEVIATION, DECLARED` |
| `drqv2`, `svea`, `sgqn`, `curl`, `drq` | 0 tagged in `rlgen/algos/` | They **import RL-ViGen-upstream's own agent files directly** — no algorithm code is authored, so the authored surface is entirely in the wiring (H1–H7) |
| `registry.py` | 2 | `DEVIATION`: the paper's categorical clone-KL becomes the closed-form Gaussian KL, because this benchmark's policy is Gaussian |

## Completeness against the current tree, as of 2026-08-16: **no**

Complete for `ibac_sni` and the shared harness; **for nothing else.** The other
nine baselines are covered only where a tag (`[OURS]`, `[CA]`, `DEVIATION`, …) already existed for
a `grep` to find — 77 sites. That is a search over one index, not an audit, and an authored edit
that nobody tagged is invisible to it. Untagged edits are also the ones most likely to have gone
in without a reason, which is precisely the population this file exists to surface. **Treat every
non-`ibac_sni` row below as a lower bound.**

Measured 2026-08-16 (`difflib.SequenceMatcher` over code lines, best match across each reference),
because "is this module actually descended from its reference" is a number, not an opinion:

| baseline | descent from its reference | reading |
|---|---|---|
| `sac.py` / `soda.py` | **93% / 85%** (`dmcontrol-generalization-benchmark`) | genuine transcriptions |
| `alda/*` | **100% from our own sibling** `gen-rebuttal/vigen-idaac/vigen_alda/`; **0% from `ext/ALDA_Official`** | **flag** — and `ALDA_Official` is PyTorch with a conventional layout, so no framework crossing excuses it. Both hops now measured; the second hop does not exist textually |
| `ppg/*` | **0%** from `ext/phasic-policy-gradient` | **flag** — the base is clean, PyTorch, 19/19 files parse |
| `idaac/*` | **0%** from `ext/idaac` (`rraileanu/idaac` @ `2fe3020`, the author's own repo) | **flag**, with a caveat: that repo has no continuous head at all (`distributions.py` defines only `Categorical`), so it can settle the encoder, storage and losses but not the policy head |
| `ctrl/*` | **0%** from `ext/ctrl_public` | **not a flag** — JAX/Flax only; the crossing is the reason and it is declared |
| `rad.py` | **0%** from `ext/rad` | **not a flag** — thin wrapper; the substance is `sac.py` above, and its one deviation is declared in its own docstring |
| `ibac_sni/*` | 100 / 99 / 44 / 3 / 7% | rebuilt 2026-08-16; see this file's own section |
| `drqv2`,`svea`,`sgqn`,`curl`,`drq` | n/a | import `RL-ViGen-upstream`'s agent files directly — no authored algorithm code, so the authored surface is entirely the harness (H1–H7) |

**0% is a flag, not a verdict.** Two rows above are legitimately 0%. The number says where to
look; a paired judgement about frameworks and wrappers decides what it means.

**One row is worse than "untagged":** `idaac/config.py:152` and `model.py:84` justify the
continuous head as a `DEVIATION from [IK]` — Kostrikov's `pytorch-a2c-ppo-acktr`, which **is not
on this disk** and was never read here. An argument-shaped citation to an absent artifact
(`docs/REGISTER.md`, 2026-08-16).

## What this file does not yet cover

Stated rather than left for a reader to discover:

1. **Untagged authored content in the nine baselines above.** The sweep is exhaustive for tagged
   sites only. An untagged edit is invisible to it — and an untagged edit is exactly the kind most
   likely to be unjustified.
2. **`alda`'s two-hop provenance** (`Nd_ln.py` → sibling `vigen_alda` → here) is unaudited, so its
   authored surface is not fully enumerated.
3. **`ppg`, `idaac`, `ctrl`-past-the-encoder have no numerical reference comparison at all**, so
   every row for them is at best **argued**, never **verified**.
4. **The K/contract layer is unverified for all 12.** Readiness there is *joint* and cannot be
   claimed per-baseline.
5. `I9` (`init_scale=1.0`) is the one row in `ibac_sni` where fidelity to the reference and
   confidence in the reference's intent point in different directions.

---

## 2026-08-17 — the approach changed, and this log continues under it

**The null became the original repository, cloned, running its own `train.py`.** Everything above
describes the port under `rlgen/`, which is now superseded. That entry is not retracted — this
file is appended to, never rewritten — but from here the accounting lives in two places:

- `python scripts/deviations.py` — the exhaustive per-clone change set, since every clone carries
  a `PRISTINE:` first commit and `git diff` against it *is* the statement. Currently
  **34 files, +917 / −125 (602 non-comment)** across six clones.
- `setup/apply_patches.py` — the RL-ViGen patch registry, now P1–P21 (no P16; ids are not
  contiguous), pinned by
  `Protocol.env_patches` and two contract tests.

**What was added to this project's own code, as opposed to a clone:**

| ours | why it is not in a clone |
|---|---|
| `runnable/_shim/sitecustomize.py` | device adaptation via `PYTHONPATH`; changes zero repo lines |
| `runnable/_shim/no_tf/tensorflow.py` | a TensorFlow that raises on use, so `baselines`' unreachable import resolves |
| `runnable/_launch/*.sh` | launch environment, recorded because a run needing undocumented environment is not reproducible |
| `runnable/_launch/ppg_eval.py` | `ppg` ships no evaluation entry point at all; this reuses its own `Roller`/`VecMonitor2` |
| `runnable/_launch/smoke_all.sh` | runs all twelve and judges on evidence of training, not exit codes |
| `scripts/deviations.py` | the ledger |
| `tests/test_{mps_shim,success_metric,observation_geometry,docs_not_stale}.py` | four properties that had each already broken silently once |

**The four continuous heads, by provenance** — because "we wrote a head" is not one kind of act:

| baseline | head | provenance |
|---|---|---|
| `idaac` | `FixedNormal` + `AddBias` + `DiagGaussian` | **copied verbatim** from `ikostrikov/pytorch-a2c-ppo-acktr-gail@41332b7`, the file's own upstream |
| `ppg` | `_make_normal` completed | authored; upstream's body was unreachable and hardcoded `scale=1.0` under its own warning |
| `ibac_sni` | `make_dist` → `Independent(Normal, 1)` | authored; `torch_rl` refuses anything but `Discrete` |
| `ctrl` | `make_pi` → `tfd.MultivariateNormalDiag` | authored |

All four put the log-stdev in a state-independent parameter, as PPO does. Evidence they are
right rather than merely running: logged entropy 9.9333 (`ppg`) and 9.935 (`ibac_sni`) against
7 × ½log(2πe) = 9.9326 for a 7-dim unit Gaussian; jax's MVNDiag reports 9.93257 for the same.

## 2026-08-19 — a branch point found by measuring, not by reading

The heads above are adaptations we *chose* and knew we were choosing. This one is different: it
was already in the code, justified by a sentence that turns out to be false. Recording it in §4's
four fields, because the point of §4 is the branch point, not its forced consequences.

**`idaac` — `info['level_seed']`** (register [C50](CONSTRUCTION.md#c50))

| §4 field | |
|---|---|
| **Structural property of the original the mechanism depends on** | IDAAC's adversarial order classifier uses temporal position as a proxy for level identity because Procgen levels have varying episode lengths; its paper names episode-length variation as the bridge from order information to level-specific information |
| **What the target actually offers** | Door has a fixed 500-step horizon. Adding scene IDs would create visual diversity but would not create the episode-length variation the objective relies on |
| **Options** | (1) keep the faithful objective and disclose that this target lacks the structure from which it is expected to gain; (2) add scenes only to IDAAC, making its training distribution incomparable without repairing episode-length variation; (3) change the benchmark for all twelve |
| **Choice** | **Option 1, settled default, 2026-09-04.** The objective remains active; the target-method mismatch is reported beside IDAAC's row |
| **What would show the choice was wrong** | A target variant with variable episode lengths would restore the paper's stated condition and require revisiting this disposition |

The pre-existing comment at `ppo_daac_idaac/envs.py:82` — *"the seed IS the level id"* — is the
false statement. It is left in place and contradicted here rather than quietly deleted, because
the disagreement between code comment and measurement is itself the finding.

**Footing of the numbers already produced.** `Protocol.env_patches` rides inside
`Protocol.hash()`, so any change to the patch set makes old and new numbers machine-distinguishable
rather than silently poolable. Two things follow, and both are easy to lose:

- `setup/apply_patches.py` now classifies every patch as PLATFORM / RESTORES / **ENABLES**, and
  the ENABLES set is `P6, P10, P11`. A number produced with those active is not a pure-fidelity
  number — success rate is not emitted by upstream at all, and the 84px render is fixed in their
  config. **No number this project has produced is a pure-fidelity number**, and that line was
  crossed by patches that looked like plumbing, not by any deliberate deviation.
- [C47](CONSTRUCTION.md#c47)'s retention (0.278 at 50k, 0.238 at 100k) was measured on the patch
  set as it stood. If a future patch changes *which distribution* is evaluated — the scoped-but-
  unimplemented P14 would be the first — the hash changes and a re-measurement is a **different
  measurement**. It must sit beside C47, not replace it.

## 2026-08-19 — P14, the evaluation axis (decided and applied)

Logged when reached, per this file's own rule. §4 form, because a change to *which distribution
is evaluated* is a branch point even though it is not a mechanism port.

**P14 — `train.py` evaluates the certified scenes, and both regimes** (register
[C45](CONSTRUCTION.md#c45) + [C43](CONSTRUCTION.md#c43))

| §4 field | |
|---|---|
| **Structural property of the original the mechanism depends on** | RL-ViGen's reported robosuite numbers come from `eval.py`, which sweeps ten scenes at ten episodes each (`eval.py:178-184`), matching its supplement's §D.1.1. That sweep *is* their evaluation protocol |
| **What the target actually offers** | `train.py` — the loop every number this project has produced came through — contains no occurrence of the string `scene`, so it evaluated `robo_make`'s default scene 0 forever, and built no train-regime env at all. `Protocol` meanwhile certified ten scenes inside its own hash, so the certification and the code disagreed and nothing noticed |
| **Options** | (1) sweep the ten scenes and add a train-regime denominator — one edit to one loop; (2) report one scene and change `Protocol` to certify one, which is honest but makes our numbers incomparable with RL-ViGen's own; (3) leave both and caveat the results, which [C47](CONSTRUCTION.md#c47) measures as ~4× optimistic on held-out scenes |
| **Choice** | **(1), decided by the owner 2026-08-19 and applied.** C43 and C45 are one patch, not two: both are edits to the same eval loop, and splitting them would produce a tree where the scene axis exists and the denominator does not |
| **What would show the choice was wrong** | A ten-scene evaluation costing enough per run to make the 5-seed budget unaffordable ([C18](CONSTRUCTION.md#c18) already prices seeds at ~53% resolution at the operational n=3 -- corrected 2026-09-05, A28, from a stale ~31%-at-five-seeds figure that used the wrong statistical approximation -- so eval cost trades directly against seed count); or scene-to-scene variance turning out smaller than the within-scene control, which would make the sweep expensive noise — [C46](CONSTRUCTION.md#c46) measured the opposite, and that measurement is the thing to re-check first |

**Defect found in this patch, 2026-08-20 — the denominator is one episode.** `train.py:152` sets
`per = max(1, num_eval_episodes // len(scenes))`, which is `max(1, 10 // 10) = 1` at the config's
`num_eval_episodes: 10`. The reported eval number is then ten episodes (one per scene), and the
train-regime denominator is `_eval_regime('train', scenes[:1], 1)` — **one scene, one episode**.
A ratio with a single-episode denominator is not a measurement, and `svea` showed it plainly:
train-regime **0.79** at 30k frames, below the [C55](CONSTRUCTION.md#c55) floor of 1.82, while
that run's training episodes over the same interval averaged 41.93.

The patch's own §4 above worried about eval *cost* against seed count and never about episodes
per point — so the trade was made in the right currency and priced against the wrong quantity.
Fixing it means either raising `num_eval_episodes` (cost scales with the ten scenes too) or
giving `den` its own episode count independent of `per` (cheap, and it makes the denominator's
sample size a stated number rather than an arithmetic accident). Either is a change to a patch
already applied, so it is a decision, not a slot.

**Verified before being recorded as done**, not argued: a `drqv2` run at `num_eval_episodes=10`
built **24** environments — two at startup, then two eval points of ten eval-easy scenes plus one
train-regime env — and `eval.csv` gained `train_regime_reward` 0.8525 beside a ten-scene
`episode_reward` of 0.8718. `tests/test_p14_eval_axis.py` holds the shape; it does not
re-establish it.

**Scope, corrected the same day it was written.** P14 patches `RL-ViGen-upstream/train.py`, which
serves **five** baselines — `drqv2`, `svea`, `sgqn`, `curl`, `drq`. The other seven have their own
training loops and are untouched: `idaac` and `ibac_sni` pass a literal `scene_id=0`, and `alda`,
`ctrl`, `ppg`, `rad`/`soda` thread a parameter nothing in their trees ever moves. C45 and C43 were
briefly marked RESOLVED on the strength of a verification that covered five, and are OPEN again.
`python scripts/audit_eval_axis.py` prints the state per baseline; extending the sweep to the
other seven is seven clone deviations, which is a decision rather than a slot.

**What it costs, stated because it is not free.** Evaluation is now ~11× the environments per eval
point. That is the trade [C18](CONSTRUCTION.md#c18) prices: eval cost and seed count come from the
same budget, and this decision spends on coverage rather than on seeds.

**Footing.** P14 is ENABLES — it changes *which distribution* is evaluated, so numbers produced
with it are ours. `Protocol.env_patches` carries it, so the hash separates pre- and post-P14
results. Every number this project has produced so far, [C47](CONSTRUCTION.md#c47)'s retention
included, is pre-P14 and is not superseded by anything measured after it.

## 2026-08-19 — a recorded decision overturned, and how it was nearly done silently

**P-C23 → superseded: re-value the per-baseline fields rather than annotate them** (register
[C23](CONSTRUCTION.md#c23), [C1](CONSTRUCTION.md#c1), [C2](CONSTRUCTION.md#c2))

| §4 field | |
|---|---|
| **Structural property of the original the mechanism depends on** | Not a port question. `Protocol.hash()` is this project's definition of "two numbers are comparable iff this matches", and per-baseline facts inside it — frame stack, render size, time-limit handling — were single project-wide values |
| **What the target actually offers** | Those values differ per baseline and the maps recording the truth (`OBSERVATION_GEOMETRY`, later `TIME_LIMIT_HANDLING`) sat beside the fields, unconsulted |
| **Options** | (1) annotate the field as insufficient and point at the map — **this was decided on 2026-08-17 as C23, explicitly "the precedent C1 should follow"**; (2) re-value per baseline so the hash separates them, rejected then because it invalidates every recorded protocol hash |
| **Choice** | **(2), 2026-08-19 — overturning (1).** The reason (1) was chosen was the re-stamp cost. P14 invalidated every recorded hash that same day for [C45](CONSTRUCTION.md#c45)+[C43](CONSTRUCTION.md#c43), so the cost (1) was avoiding had already been paid, and bundling was free. The annotation stays in place; what changed is that the field now also *is* correct rather than only *declaring itself* incorrect |
| **What would show the choice was wrong** | Recorded hashes turning out to be referenced somewhere that cannot be re-stamped — no result set exists yet, which is exactly why now was cheap and later would not be. Also: if per-baseline hashes make two baselines' numbers look incomparable in a way that is *only* bookkeeping, the separation is noise and the annotation was the better trade |

**This was nearly done silently, and that is the part worth keeping.** C1 and C2 were fixed as
though they were oversights. They were not: C23 had considered the same fix and rejected it, in
writing, and named itself the precedent. The supersession was noticed only while triaging which
RESOLVED entries lacked a §4 block — i.e. by the instrument built earlier the same day for a
different reason.

Had C23 been recorded as a §4 block rather than as prose inside a resolved entry,
`scripts/decisions.py`'s premise-drift check would have flagged it the moment P14 landed: a
decision whose stated cost had just been paid by something else. That is precisely the
"decisions build on later decisions" failure the ledger exists for, and it caught one on its
first day by accident rather than by design.

## 2026-08-20 — read runs where runs actually land

**P-C59: `collect_metrics.py --from-runs` walks the hydra tree and reads `eval.csv`** (register
[C59](CONSTRUCTION.md#c59))

| §4 field | |
|---|---|
| **Structural property this depends on** | RL-ViGen picks its agent by choosing a whole config file, so a run directory's name never says which baseline produced it — and only `cfgs/config.yaml` writes `exp_local/<date>/<run>/`; the other four interpolate `${name}` and land a level deeper |
| **What the target offers** | Every run writes `.hydra/hydra.yaml` with its `config_name`, and `eval.csv` with the metrics. Both are durable; the console output the existing parsers match is not written to disk by a real run |
| **Options** | (1) keep the flat `<baseline>.log` contract and have each launcher tee stdout into it — cheap, but it makes the record depend on how a run was invoked; (2) parse `train.log` — tried, and it yields nothing, because that is hydra's log and the metric lines go to stdout; (3) read `eval.csv` and take the baseline from the run's own saved config |
| **Choice** | **(3)**, with `rglob` rather than a fixed depth: depth is not part of the contract, having a `.hydra/hydra.yaml` is. The regime is not inferred — post-P14 runs carry `train_regime_reward`, and pre-P14 runs record nothing about `RLVIGEN_EVAL_MODE`, so those rows say `eval(unrecorded)` rather than being assumed `eval-easy` |
| **What would show the choice was wrong** | A baseline that writes no `eval.csv` — the seven clones do not use this loop at all, so `--from-runs` covers five of twelve and the other seven still need their own path; or upstream changing the CSV's columns, which would fail loudly rather than silently since the collector reports "PARSED NOTHING from an existing log" |

## 2026-08-20 — turn TensorBoard on, because the contract asks for it

**P-TB: `runnable/_launch/rlvigen.sh` passes `use_tb=True`** (register
[C57](CONSTRUCTION.md#c57), [TASK.md](TASK.md) R7)

| §4 field | |
|---|---|
| **Structural property this depends on** | `algos/drqv2.py` computes `metrics['critic_loss']` and `metrics['actor_loss']` on every update, and `logger.py` routes them to TensorBoard **only** — `_try_sw_log` is the sole outlet, and the CSV's field list is frozen at the first dump without them |
| **What the target offers** | `torch.utils.tensorboard` is installed, and P13 already made the import lazy so `use_tb=True` works without reinstating an unconditional import |
| **Options** | (1) leave it off, which is what all eight prior runs did; (2) add the loss keys to `COMMON_TRAIN_FORMAT` so they reach the CSV — a patch to upstream's logger, and it duplicates a facility that already exists; (3) pass `use_tb=True` from our own launcher |
| **Choice** | **(3).** Two independent reasons, and either alone would be enough. [TASK.md](TASK.md)'s **R7** — the acceptance test for the repo as a deliverable — is *"clone → install → `sh` script → tensorboard log → shared plotter → eval curve"*, and with tb off that sequence is not runnable, so the contract was unsatisfiable by our own launcher. And it is the only place a NaN in `critic_loss` would have appeared: [C57](CONSTRUCTION.md#c57)'s run discarded ~100,000 finiteness checks and stayed dead for 70,000 frames. Verified: a 6,000-frame run logs `train/critic_loss`, `train/actor_loss` and three critic-Q series at 373 points each |
| **What would show the choice was wrong** | TensorBoard writes costing measurable throughput on the long runs — untested, and cheap to test by timing one run each way; or the event files growing enough to matter on a machine already short on disk. `"$@"` comes last in the launcher, so any caller can still pass `use_tb=False` |

Changes no number and no algorithm — it adds an artifact that the contract already required and
that nothing was producing. This is a change to **our** launcher, not a patch to upstream, so it
carries no new deviation against the pinned tree.

**It broke `drq`, 2026-08-24 — the falsifier above was the wrong one.** That row worried about
throughput and disk. What actually happened is that turning TensorBoard on **executes code that
was never executed before**, and one baseline's tb-only path has a latent upstream bug:
`algos/drq.py:328` logs `dist.entropy()` inside `if self.use_tb:`, and `drq`'s `dist` is a
`SquashedNormal`, a torch `TransformedDistribution`, which does not implement `entropy()`. So
`drq` raises `NotImplementedError` on its **first actor update** — past the 4000 seed frames, which
is why a short smoke run exits 0 and a real one dies.

Blast radius is exactly one baseline, checked rather than assumed: of the five natives, only
`drq` has both an `.entropy()` call and a transformed distribution (`drqv2` and `svea` call
entropy on a TruncatedNormal and both completed 55k runs after the change; `sgqn` and `curl` never
call it).

`scripts/run_cell.sh` now runs `drq` with `use_tb=False` and says so. tb affects no number, so the
cost is the artifact — `drq` produces no tensorboard log and therefore cannot satisfy
[TASK.md](TASK.md) R7's sequence, which is a disclosed asymmetry rather than a hidden one. The
alternatives are all worse or are yours: reverting the default gives up R7 and C57 detection for
the other four, and patching `drq.py` to compute a transformed-distribution entropy is a deviation
on upstream's algorithm code.

**The general lesson, which is the part worth keeping:** "enable a logging flag" is not a no-op
change. It is *running code that has never run*, and a repository's tb-only branches are exactly
the least-tested lines in it.

## 2026-08-20 — a floor under every ratio

**P-C55: a retention report refuses a denominator that has not cleared chance** (register
[C55](CONSTRUCTION.md#c55), [C47](CONSTRUCTION.md#c47))

| §4 field | |
|---|---|
| **Structural property this depends on** | Retention is a ratio, and robosuite's rewards are shaped, so "does nothing" pays ~1.8 per episode rather than 0. A denominator can therefore look well-determined and carry no information about competence |
| **What the target offers** | `robo_make` accepts an action spec, so a uniform policy runs through the identical evaluator, scenes and episode counts. No new machinery, one flag |
| **Options** | (1) report ratios and caveat them in prose — the status quo, and the caveat is exactly what a reader skips; (2) guard on the denominator's own statistical precision — tried, and it *passed* a chance-level denominator, because 2.02 ± 0.8 is precise and still chance; (3) measure the floor and refuse below it; (4) refuse whenever the policy never solves the task, which would also mute rows that legitimately measure partial competence |
| **Choice** | (3), plus a distinct verdict for (4)'s case rather than collapsing them. A row that clears the floor but never solves the task is printed as `UNSOLVED-DENOMINATOR` and excluded from pooling: it measures retention of reward *shaping*, which is a real quantity and not the same one |
| **What would show the choice wrong** | A task whose floor is genuinely 0 — then the guard costs a rendering pass per baseline and buys nothing, and the honest response is to measure once per task and record it, not to keep re-measuring. Also: if `UNSOLVED-DENOMINATOR` rows turn out to track the pooled figure closely across many checkpoints, the separation is bookkeeping and the simpler report was right |

Logged here because `scripts/decisions.py` flagged C55 as RESOLVED with no §4 block on the day
after the ledger was built — the instrument catching its author, which is the only evidence so
far that it works on anything but the case it was written for. It also cost a second attempt:
the block was first written with an explanatory paragraph between the title and the table, and
the extractor requires them within three lines, so the ledger went on reporting the decision as
unlogged. A format that silently ignores a correct-looking entry is worth knowing about, and the
right fix was the block, not the regex — prose belongs under the table.

## 2026-08-24 — the completeness gap, measured for two clones

This file's own statement was *"complete for `ibac_sni` and the shared harness; for nothing
else"*, with the other nine covered only where a tag existed to `grep`. Audited properly for two
clones — not by grepping tags, but by `git diff <PRISTINE-sha> HEAD` in each clone, which is every
authored change whether tagged or not.

| clone | authored hunks | already tagged | missing from the tag index |
|---|---|---|---|
| `alda` | 7 | 0 | **100%** |
| `idaac` | 29 | 4 (all `[OURS]` C28) | **86%** |
| **both** | **36** | **4** | **89%** |

**The sharper finding is about this file's own bookkeeping.** Its per-baseline table credits
`alda` with 13 tagged sites and `idaac` with 29. Those tags live in `rlgen/algos/alda` and
`rlgen/algos/idaac` — the **superseded 2026-08-16 port**, not the clones, whose era began
2026-08-17. So the recorded counts contribute **zero** coverage of the trees that are the
deliverable, and the four tags actually present in the clones are not among the 77 this file
counted. The same defect hits `M4` (`init_log_std = -1.0`) in the adaptations table above: it
describes the superseded port only, and nothing said so. *(Clone-era check: `idaac`, `ibac_sni`
and `ctrl` all initialise `log_std` at **0.0**, so clone-era uniformity holds and M4 does not
apply to them.)*

In fairness to the machinery that does work: `scripts/deviations.py` enumerates all 36
mechanically and its counts are exact (`alda` 2 files +81/−1, `idaac` 6 files +223/−30, both
matching the diff), and `RUNNABLE-ORIGINALS.md` carries prose for both. What is missing is the
**classification**, and two whole surfaces appear in no index at all: the **success-rate metric**
(3 `alda` hunks + 8 `idaac`) and the **C28 diagnostics**.

### One new defect, verified

**`alda` emits a hard `0.0` success rate on the DMC path.** `trainers/alda_trainer.py:562-563`
logs `float(succeeded)` unconditionally, and on DMC `info` never carries `success` — so a DMC run
reports a measured-looking zero. `idaac/train.py:234-238` faces the identical choice and takes the
opposite one, in writing: *"nan rather than 0 when no episode finished: a zero here would be
indistinguishable from a measured failure."* **The same principle, applied in one clone and
inverted in the other, neither tagged.** Robosuite runs are unaffected; this is a DMC-path defect
and it is ours.

### Two flags that did not survive checking

Recorded because a rejected finding is worth as much as a kept one, and both would have been
plausible entries:

- **"Both clones bypass `robo_make`, so they miss `ActionRepeatWrapper` and run at a different
  control frequency."** Refuted — but the first refutation was sloppy and is worth correcting,
  because "our launcher forces it" implies a shared launcher that does not exist. Audited across
  all seven launchers and all twelve baselines:

  | baseline | action repeat | how |
  |---|---|---|
  | `drqv2` `svea` `sgqn` `curl` `drq` | 1 | `_launch/rlvigen.sh:77` passes `action_repeat=1` **explicitly**, documented at :60 as "this project's declared protocol" |
  | `rad` `soda` | 1 | ~~`_launch/dmc_gb.sh` passes `--action_repeat 1` **explicitly**~~ — **wrong, corrected 2026-08-25**: the flag is passed and **never read**. `runnable/dmc_gb/src/env/wrappers.py`'s robosuite branch builds through `_robo_make_env(...)` and `return`s at `FrameStack`, *before* the `dmc2gym.make(..., frame_skip=action_repeat)` that is the file's only consumer of it. Same structural pattern as `alda`'s. |
  | `alda` | 1 | its specs carry `action_repeat` at 1, 2 **and** 4 across tasks — but on the robosuite path the key is **never read** (only `dmc2gym.make` reads it, and the branch returns first) |
  | `idaac` `ctrl` `ibac_sni` `ppg` | 1 | **no action-repeat mechanism exists in their code at all** — Procgen-native trainers do not repeat actions |

  So all twelve do run at 1, matching `protocol.py:140`'s `DEFAULT_ACTION_REPEAT = 1` and the
  paper's Table 2 ("Action repeat — Robosuite: 1"). **But they agree for three different reasons,
  and only FIVE of twelve agree by anyone's decision** — the five natives, via `rlvigen.sh:77`.
  *(This read "seven" until 2026-08-25, counting `rad`/`soda` as explicit; they are not — see the
  correction in their row above. The revision moves them into the absent-mechanism group, which now
  holds six.)* Six agree because the mechanism is absent, and `alda` agrees because a key that looks
  configured is dead — it would read as configured to anyone auditing the spec, as would
  `dmc_gb.sh`'s flag.

  **And the direction of the deviation is the opposite of what "we override upstream" suggests.**
  The vendored supplement's **Table 2** states *"Action repeat — Robosuite: 1, otherwise: 2"*. Every
  shipped config says `2` and no task file overrides it. So `rlvigen.sh:77` makes us **faithful to
  their paper and unfaithful to their shipped code** — upstream's own repository contradicts
  upstream's own table, exactly as it does for `feature_dim` and SGQN's `aux_lr`
  ([C64](CONSTRUCTION.md#c64)).

  **That is worth stating plainly, because the project answers the same question two ways in the
  same file.** For `action_repeat` we follow the paper; for `feature_dim` and `aux_lr` we follow the
  shipped default. Both may be defensible individually, but the choice has never been made as a
  *rule* — and C64 is currently being argued on "the null is what upstream ships," a principle line
  77 has violated on every run since 2026-08-17. C64 should be decided as an instance of a stated
  rule rather than on its own merits.

  **Added 2026-08-24, and it is the half of this audit that carries risk: the value those five
  baselines are being overridden *from* is 2, not 1.** Every RL-ViGen config on disk ships
  `action_repeat: 2` — `config.yaml:10`, `drq_config.yaml:9`, `svea_config.yaml:9`,
  `sgqn_config.yaml:9`, `curl_config.yaml:9`, and the four `pieg`/`srm`/`svea_drq`/`sgqn_drq`
  variants — and **no task-level override exists for Door**: `cfgs/task/*.yaml` contains no
  `action_repeat` at all. So for those five, `1` is not a default that our launcher happens to
  restate. It is our launcher contradicting upstream's shipped value, every run, silently.

  The consequence is a live footgun rather than a debt: **launch any native baseline without
  `_launch/rlvigen.sh` — a bare `python train.py`, a notebook, a remote job someone assembles from
  the upstream README — and it runs at 2**, producing a number not comparable with anything else
  here. Nothing in the pipeline would flag it: `Protocol` hashes `DEFAULT_ACTION_REPEAT = 1` but is
  not consulted by the runners, and the grids record `action_repeat` from the run rather than
  checking it. Worse, **the logged `episode_length` reads `500.0` at either value**, so the one
  field that looks like it would catch this cannot.

  > **Corrected 2026-08-25 — what changes at `action_repeat=2` is not what this paragraph first
  > said.** It claimed the change "halves the environment steps behind each frame" and moves where
  > a 500-step episode ends. **Both are wrong.** `train.py:135` defines
  > `global_frame = global_step * action_repeat`, and `wrappers/dmc.py:44-52`'s
  > `ActionRepeatWrapper.step` loops `num_repeats` times *accumulating* reward. So a frame budget
  > buys the same number of environment steps either way, the episode still spans 500 env steps,
  > and **[C62](CONSTRUCTION.md#c62)'s 250 shaping ceiling is invariant**.
  >
  > What actually halves is **agent decisions per episode** (500 → 250) and **gradient updates per
  > frame budget**. That is a real and serious difference — it changes the policy's temporal
  > resolution and how much learning a budget buys — but it is a different claim, and the
  > ceiling-based arithmetic elsewhere in these documents is unaffected by it.

  **The hermetic question, which this audit had not asked, added 2026-08-25 on challenge.**
  Everything above establishes *what* the values are. It does not ask whether forcing one of them
  is consistent with the project's founding rule — *"hermetic per baseline: own file, own utilities,
  no shared base classes, runners, or adapters; duplication is cheaper than a wrong abstraction."*
  That question was skipped, and the recommendation to keep `1` was adopted on comparability
  grounds alone. Applying the rule properly gives a more uncomfortable answer than either.

  - **Strictly, §1 is not violated.** A launcher passing a CLI override is not a shared base class,
    runner, or adapter; each baseline still executes its own `train.py`. The join is at
    *configuration*, not at code.
  - **But `_launch/rlvigen.sh` is a shared launcher for five baselines**, and it imposes a value
    each of their own configs contradicts. That is the same shape as [C53](CONSTRUCTION.md#c53)
    (unified logging vs §1) — a place where a comparability requirement and hermeticism pull in
    opposite directions, and the project has resolved it silently rather than recording the
    tension. The strictly-hermetic reading is that each clone should run **its own** value, which
    would put the five natives at 2, `rad`/`soda`/`alda` at 4, and the four Procgen clones at 1 —
    and would make the x-axis mean three different things.
  - **The real leak is not the override; it is the invariant nobody enforces.**
    `rlgen/protocol.py:140` declares `DEFAULT_ACTION_REPEAT = 1` and hashes it into the
    comparability record, but **no runner consults it** ([C71](CONSTRUCTION.md#c71) #4). So the
    project has been relying on "the protocol guarantees a common x-axis" when the protocol
    guarantees nothing — the abstraction leaked completely, and it took an audit to notice. The
    only thing that now bites is
    `tests/test_x_axis_invariant.py::test_every_archived_grid_was_measured_at_action_repeat_1`,
    which reads the *grids* rather than the declaration.

  **So the decision stands and its justification changes.** Keeping `1` is right — it is the
  paper's value for this domain, four baselines can express nothing else, and the alternative is
  three incompatible x-axes. What is withdrawn is the *framing*: this is not "a project-wide
  protocol constant", it is **a deliberate, recorded, unenforced-until-2026-08-24 override on five
  baselines, coexisting with seven that hold the same value for unrelated reasons.** Stating it the
  short way is the leak; the long way is the fact.

  That is the same shape as [C1](CONSTRUCTION.md#c1)'s truncation split: a project-wide constant
  holding by coincidence across most of the set is not the same fact as one being enforced, and
  the difference only shows when something perturbs it. Nothing is broken today; what is missing
  is that **no mechanism would notice if a clone's default changed**, since seven of twelve never
  pass the value and `Protocol` hashes a number nobody checks against the runners.
- **"`idaac` does no frame stacking — 3 channels where others see 9."** True and **already
  recorded**: [C2](CONSTRUCTION.md#c2) and `rlgen/protocol.py`'s `OBSERVATION_GEOMETRY`, which
  pins `idaac: (64, 1)`.

Two of six flags were refuted or already known, which is the expected yield and the reason the
diff is checked against the record rather than reported from it.



---

## P-C69 / P-C70 — the evaluator's reproducibility preconditions

Authored element: `scripts/eval_across_scenes.py::run_scene`. Two lines, one claim — that a
recorded seed names a measurement. Findings and evidence in [C69](CONSTRUCTION.md#c69) and [C70](CONSTRUCTION.md#c70); the branch points are here,
because that is where a decision changing code is enumerable.

**Where to seed the placement RNG** — [C69](CONSTRUCTION.md#c69).

`scripts/decisions.py` was right that this had been written as prose rather than enumerated.

| §4 field | |
|---|---|
| **Structural property of the original the mechanism depends on** | `UniformRandomSampler` (`robosuite/utils/placement_samplers.py:167,183,196,198`) draws from the **global** numpy RNG and holds no `random_state`. Upstream seeds that stream **once per process**, before env construction (`train.py:47` → `utils.py:38`), and every later `reset()` advances it |
| **What the target actually offers** | Our evaluator builds one env **per scene**, sequentially, inside a single process — a structure upstream's training loop does not have. So "seed once at start" and "seed per scene" are different measurements here, and upstream's convention does not decide between them |
| **Options** | (1) **Seed once per run**, mirroring upstream — reproducible grid-to-grid, but each scene inherits wherever the previous scene left the stream, so scenes differ in *placement* as well as appearance and the comparison is confounded. (2) **Seed per scene from the base seed** — every scene sees an identical placement sequence, so scene identity is the only varying quantity. (3) **Seed per episode** — maximal control, but collapses the within-scene episode variation the bootstrap CIs are computed over |
| **Choice** | **(2).** The script's stated purpose is an intervention on scene identity with the regime held fixed; (1) silently makes it an observation instead, and (3) destroys the dispersion the error bars describe |
| **What would show the choice was wrong** | If the fixed placement sequence interacts with scene geometry — one scene systematically advantaged because the shared draw happens to suit its handle position — the between-scene signal would be biased rather than controlled. Detectable by re-deriving one grid under option (1) and checking whether the **scene ranking** moves; the ranking is what [C47](CONSTRUCTION.md#c47) reads, and it is the part [C67](CONSTRUCTION.md#c67) already shows is fragile. Not yet run |

**Whether to force deterministic torch kernels** — [C70](CONSTRUCTION.md#c70).

| §4 field | |
|---|---|
| **Structural property of the original the mechanism depends on** | Nothing in the reference — this is entirely ours. RL-ViGen's own evaluator never claims reproducibility, and the algorithms do not depend on it |
| **What the target actually offers** | A task whose success is a **threshold** (`hinge_qpos > 0.3`), which converts a ~1e-7 difference in one action into a binary outcome. On a continuous-reward task this defect would be invisible and arguably harmless |
| **Options** | (1) **`use_deterministic_algorithms(True)`** — exact reproducibility, at the risk that some op on this path has no deterministic implementation and raises. (2) **Accept nondeterminism and report bands** — no code change, but every number acquires a ±1-success-per-scene envelope that cannot be reduced by more episodes, only characterised. (3) **Pin threads** — measured and **rejected on evidence**: `set_num_threads(1)` still diverges, so it addresses the wrong mechanism |
| **Choice** | **(1).** Option 2 spends the project's remaining resolution on noise that a one-line change removes, and the whole point of the C69 work was that a recorded seed should name a measurement |
| **What would show the choice was wrong** | An op on the evaluation path with no deterministic implementation would raise `RuntimeError` and stop the evaluator outright — a loud failure, not a silent one. Fourteen grids have run under it without raising, so the risk is bounded by evidence rather than by argument. It would also be wrong if determinism were bought at a large throughput cost; not measured, and worth a timing comparison if a grid ever becomes the bottleneck |


**Which ratio the contamination screen reads** — [C65](CONSTRUCTION.md#c65),
`scripts/regime_retention_report.py`. Recorded after the fact: the first implementation chose
wrong and passed its own tests, which is the case §4 exists to make visible.

| §4 field | |
|---|---|
| **Structural property of the original the mechanism depends on** | None — RL-ViGen publishes pooled returns and has no notion of a provenance screen. This is entirely ours, which is why the estimand had to be chosen rather than inherited |
| **What the target actually offers** | Two defensible pooled ratios over the same grids: the **guarded** one (scenes whose denominator clears the floor and solves ≥25%) and the **all-scene** one. They are not close — on `snapshot_100k_frames` they read **0.010** and **2.513** — and they disagree in *sign* relative to 1 on exactly the checkpoints the screen exists to catch |
| **Options** | (1) **Guarded ratio** — consistent with the retention number printed beside it, one estimand for the reader to hold. (2) **All-scene ratio** — inconsistent with the printed retention, but it is the quantity that answers "which regime does this policy prefer". (3) **Both, side by side** — no information lost, at the cost of two numbers a reader must not confuse |
| **Choice** | **(2) for the alarm, printed alongside (1).** The guarded ratio answers *how much skill survives where the agent had skill*; only the all-scene ratio is evidence about provenance. Chosen after (1) was implemented, shipped, and found **silent on all three contaminated checkpoints while passing its own tests** |
| **What would show the choice was wrong** | A clean, correctly-provenanced checkpoint whose all-scene ratio sits significantly above 1 — that would make the screen a false-positive generator rather than a provenance signal. The random-policy control at **1.02** is the nearest case and does not trip it. The screen currently rests on four clean runs versus one contaminated one, so a second contaminated run scoring below 1 would also refute it |

---

## 2026-09-02 — RL-ViGen becomes an input, not a clone (a provenance change, forced)

**What changed.** `run_probe.sh` no longer begins every job with
`git clone https://github.com/gemcollector/RL-ViGen.git`. It prefers `RLVIGEN_ARCHIVE`, a job input
carrying a **pristine** tree at `90d8b8c40acb63af6f938c1f4cc79a0cfee7d7ec`, whose sha256 it checks
against `datasphere/native/rlvigen-source.json` before extracting. The clone survives as a fallback
and announces itself (`NATIVE_RLVIGEN_NO_INPUT`) when used.

**Why, and it is not an optimisation.** On 2026-09-02 two probes died at that clone with
`fatal: could not read Username for 'https://github.com'`, after three retries each. An anonymous
clone of a public repository never prompts for credentials. Checked from the laptop at the same
moment: the GitHub API returned **200** and `git ls-remote` returned exactly the pinned commit. So
upstream was fine and the container was not — and the same runner had cloned successfully for the
RL-ViGen five days earlier. `apt` and `pip` still worked in the failing jobs, which fits an egress
policy allowing the platform's mirrors and not the general internet. **Until this change, no
baseline could run at all.**

**Why pristine matters here.** The runner applies P1–P21 to whatever tree it is given. The vendored
working copy already has them applied — `git status` on it shows 15 modified files — so shipping
*that* would patch a patched tree and every FIND anchor would either miss or double-apply. The
archive is therefore built from a fresh clone, not from the tree we work in.

**What this costs in provenance, stated plainly.** Before, the tree came from GitHub at run time
and its identity was the commit hash. Now it comes from an archive **we** built, and its identity
is a sha256 of our tarball plus a claim about which commit it was made from. That is strictly
weaker: a reader can verify the hash matches what the runner extracted, but not that the tarball
corresponds to the commit, without re-cloning. Mitigations, in order of strength:

1. `rlvigen-source.json` records the commit, the sha256, the byte count, the entry count and the
   exact command that built it, so the archive is reproducible by anyone with network access;
2. the runner **verifies the hash before extracting**, so a swapped or truncated input fails at the
   input rather than several minutes later as an unexplained patch-anchor mismatch;
3. `setup/apply_patches.py --check` still runs afterwards and still certifies "the pinned commit
   plus exactly the declared differences", which would fail loudly on a tree that was not the one
   claimed;
4. the divergence that *does* exist is declared: a fresh clone on macOS cannot hold both
   `cfgs/task/TwoArmHandover.yaml` and `TwoArmHandOver.yaml`, so the archive is one file short of
   the commit. Neither is on the Door path.

**Class.** PLATFORM in effect — nothing measured changes, the same tree at the same commit reaches
the same patch set — but it is recorded here rather than in the patch registry because it changes
*where the tree comes from*, which is a provenance question and not a code one.

**Runner contract 8 → 9**, because the runner now requires a payload member (`rlvigen-source.json`)
that earlier payloads do not carry. Without the bump, a stale payload would leave the runner having
just stopped cloning, with no tree and no useful error.

### Correction, same day — the shipped archive is pristine *and* incomplete

The entry above says the archive is a pristine tree at `90d8b8c4`. It is pristine in the sense that
matters — no patches applied — but it is **not the whole commit**, and the first submission is why.

Uploading the full 667 MB was **reset by peer mid-transfer** before the job was created. The
archive was rebuilt without `envs/DMCVGB` (480 MB of mp4 distractor videos and colour tensors for
the DeepMind Control variant) and `img/`, bringing it to **310 MB** — inside the precedent set by
the 455 MB places365 asset, which uploads reliably.

The exclusion is argued, not assumed: `wrappers/__init__.py` is empty, `train.py` imports only
`wrappers.dmc` and — lazily, inside the robosuite branch — `wrappers.robo_wrapper`, and the single
`from dmcvgb…` import in the repository is `wrappers/loco_wrapper.py`, which this project never
reaches. `dmcvgb` is not on the container's `PYTHONPATH` either, so importing it would already have
failed. All 997 robosuite asset files and all 97 `robosuiteVGB` files are present.

**The consequence is a real boundary and is recorded as one: this archive cannot run the DMC or
locomotion domains.** It is a robosuite-Door artefact that happens to be built from the RL-ViGen
commit, not a general-purpose copy of it. `rlvigen-source.json` states the exclusions in the same
field that states the commit, so the two travel together.

## 2026-09-02 — C61 policy-health diagnostics in `ibac_sni` (logging only)

**What.** `runnable/ibac_sni/torch_rl/scripts/train.py` now logs `sigma_mean`, `mean_log_std` and
`boundary_fraction` beside the existing C28 diagnostics, from
`scripts/metrics.py::gaussian_policy_health`. Appended last, per that block's own standing note
that `data` is consumed positionally.

**Correctness: INTRINSIC.** The quantities are closed forms of the head's own `log_std` — entropy
is `sum_i(log s_i) + d/2*log(2*pi*e)`, and the boundary fraction is `erfc(1/(s*sqrt(2)))` averaged
over dimensions. Both are checked against hand values at s = 1, 2, 5 (0.3173, 0.6171, 0.8415) and
against the d = 7 initialisation entropy 9.93257 that `probe_heads` already pins. Nothing is
estimated and nothing is discovered afterwards.

**Why `ibac_sni` first, and why this is not arbitrary.** Of the four PPO-family baselines it is the
only one with **neither** reward normalisation **nor** advantage normalisation, and its `log_std`
is unclamped. The entropy term's gradient with respect to each `log_std` is a constant, so the
0.01 coefficient is a fixed upward force on σ; everywhere else that force is opposed by a
normalised policy gradient of order 1, and here it is opposed by whatever Door's raw shaped return
produces. Ranked risk, not a guess — see the register entry of the same date.

**Two defects introduced and fixed in the same edit, recorded because both were mine.** The first
replace was global and turned an unrelated `logger.info("Model successfully saved")` into an
assignment, silently removing that message. The second gated the new format placeholders on
`len(data) > 20`, which was already true before the fields were appended — the guard is now an
explicit flag set where the fields are added. The lesson is the one this file keeps recording: a
textual edit wide enough to be convenient is wide enough to hit something else.

**It changes nothing measured.** No loss, no gradient, no sampled action. It adds three columns to
a CSV and three fields to TensorBoard, and `scripts/audit_eval_cadence.py`'s anchor for this file
was re-pointed from line 196 to 206 because the import block shifted it — the audit caught that
itself on the next `--check`.

## 2026-09-03 — `datasphere/native/job.sh`, and the wasted job that motivated it

**What.** One entry point for the three things every DataSphere interaction here repeated by hand:
`submit <config>`, `status [ids]`, `diagnose <id>`.

**Why `submit` verifies before spending.** A config was repointed at a rebuilt payload with a `sed`
matching `v37 → v38` while the file still read `v36`. The substitution silently matched nothing,
the job went out against a payload predating the fix it existed to test, and **it failed in exactly
the way the fix was meant to prevent** — so the result read as "the fix did not work" rather than
"the fix was not present". `submit` now resolves every path named under `inputs:` and refuses if
any is absent, printing each with its size.

**Why `diagnose` exists.** Reading a failure meant `mkdir`, `download-files`, then four or five
greps for whichever marker mattered, over a 3,000-line log. It now prints the runner's markers in
the order they should appear — clone source, budget gate, dependency install, import gate,
production settings, cell begin/complete, finiteness — then the last non-boilerplate lines, then
the returned archive's cell contents. A missing marker is as informative as a failing one and this
makes the absence visible.

**Correctness: INTRINSIC for the guard, NOT INTRINSIC for the marker list.** The input check is a
file-existence test against the config's own declarations — it cannot be silently wrong. The
marker list is a curated set that will drift as the runner gains stages; a marker added to
`run_probe.sh` and not to `job.sh` degrades the summary without failing anything. Recorded as a
debt rather than defended with a test, because a test asserting "these greps match the runner's
echoes" would restate the list rather than check it.

**Not a change to anything measured.** It submits the same configs to the same project and reads
logs that already exist.

## 2026-09-03 — P19: the places365 loader's worker count becomes a dial

`setup/apply_patches.py`, patch P19, against `RL-ViGen-upstream/utils.py`.

**What it fixes.** `sgqn` was the only baseline of twelve that could not complete a pre-production
cell. Three jobs, none of them a retry, each changing one thing:

1. In the five-cell job it reached F: 5000 of 10,000 and died with `DataLoader worker killed by
   signal: Aborted` — at **3.77 GB RSS on a 32 GB tier**, so not OOM, which is the explanation a
   plain retry would have been testing.
2. Re-run with `replay_buffer_num_workers=0`. It failed *again*, but in-process, and the fault
   became legible: `malloc_consolidate(): unaligned fastbin chunk detected`, via
   `sgqn.py:242 update -> update_aux -> random_overlay -> utils.py:208 _get_places_batch`. **glibc
   heap corruption, and the aborting loader is the PLACES365 one** — a different DataLoader that
   the replay override never touched. The knob was wrong; the diagnostic still paid, because a
   `SIGABRT` in a child process arrives at the parent as a mute signal with no traceback.
3. The first version of P19 changed `_load_places`'s *signature*. The runner rejected it:
   `unexpected Places365 loader signature`. `datasphere/native/configure_places365_val.py` already
   rewrites that same line to select the val partition, and fails on any form it does not know.
   **Two pieces of our own machinery own that line, and I added a third without checking.**

**The cause.** `_load_places` hardcodes `num_workers=8` with `pin_memory=True`; the container
reports `logical_cpu_count: 4`. Eight JPEG-decoding workers on four CPUs.

**Why only `sgqn`, when `svea` and `soda` use the same loader and both passed.** `sgqn.update`
calls `random_overlay` an **extra** time inside `update_aux`, so it draws places batches at roughly
twice their rate. The margin the other two survive on is the whole difference.

**The patch, and where it sits.** The dial is read at the **DataLoader construction**, not in the
signature, so `configure_places365_val.py` keeps working:
`num_workers=int(os.environ.get("RLVIGEN_PLACES_WORKERS", num_workers))`. Unset preserves
upstream's 8 exactly, so no other baseline's behaviour moves.

**PLATFORM-class, and the reasoning matters.** Worker count changes *scheduling*, never which
images are drawn or in what order — `shuffle=True` draws from the same generator at any worker
count and the seeding is untouched. So P19 does **not** join `P6, P10, P11, P14, P15, P18`, the set
`apply_patches.py` names as making a number non-pure-fidelity. `--check` confirms the vendored tree
still equals its pinned commit plus exactly the declared differences.

**Result**: `sgqn` completes at **2.348** on eval-easy, and the pre-production pass is 12 of 12.

## 2026-09-03 — `ibac_sni` gains a scene axis (the piece that was actually blocking)

`runnable/ibac_sni/torch_rl/utils/general.py` built its RL-ViGen env with `scene_id=0`, hardcoded.
That is [C45](CONSTRUCTION.md#c45)'s shape for this family: the protocol and the benchmark both say
ten scenes and seven of the twelve baselines pin one. It now reads `RLVIGEN_SCENE_ID`, exactly as
it already read `RLVIGEN_MODE` for the regime — an environment variable rather than a parameter
because the callers are the clone's own scripts, and a new argument would mean editing them; this
keeps the deviation inside the seam that already exists. Default 0, so every existing caller is
unchanged. A non-integer value raises rather than falling back to 0, because a scene axis that
silently defaults would report a one-scene number as a ten-scene sweep — which is the error C45
exists to name.

**Deliberately stopped short of the `eval_grid` family.** Writing `run_scene_ibac_sni` without a
checkpoint to smoke it against would be untested code, and the `ppg` lesson was that a fixture makes
the difference; more to the point, the two running grid jobs decide whether the offline-grid path is
viable at all, and building on it first would be building on an unvalidated instrument.

**Noted while reading, because it belongs to the comparability analysis and to an open question the
owner raised.** `scripts/evaluate.py`'s `--argmax` defaults to **False**, so `ibac_sni`'s own
evaluation *samples* from the policy rather than taking the mode. That is the same estimator choice
`ppg` and `idaac` make and the opposite of the RL-ViGen family's `eval_mode=True`. It is a real
cross-baseline axis, not a detail: a sampled return and a mode return are different quantities, and
four of the twelve report the first.

## 2026-09-03 — the pre-production pass, and three defects it exposed

`scripts/preprod_table.py` (new), a guard fix in `run_probe.sh`, and an eval reader in
`normalize_curves.py`.

**The pass.** Twelve baselines, one seed, a common 10,000-frame budget, on CUDA, each through its
own repository's `train.py` — seven jobs because the families cannot share an environment. It is a
**pipeline result, not a science result**: 10k is far below what learns Door, and the numbers exist
to show the clone-to-curve chain closes (R7) at an equal budget (R4), not to rank anything.

**Defect 1 — a guard that refused without saying so.** `run_probe.sh` had a bare
`[[ -n "$asset_archive" ]]` inside the places365 branch. Under `set -e` that ends the job with **no
message at all**: two jobs (`rlvigen`, `dmc_gb`) produced byte-identical 2838-line logs that simply
stopped mid-import, status ERROR, no traceback. The cause was mine — those configs omitted the
places365 input that `svea`, `sgqn` and `soda` need — but the diagnosis cost far more than it should
have, because a silent `exit 1` is indistinguishable from a crash. It now names the missing input,
the cells that need it, and the two environment variables.

**Defect 2 — an R7 break that looks exactly like a bad score.** `ibac_sni` trained, evaluated, and
printed `R:μσmM 1.74 … SR 0.0000`, and **none of it reached the record set**: `read_ibac_sni` parsed
only `log.csv` and its evaluator prints a single line to stdout. The record set therefore held 79
training rows and zero eval rows. The table rendered that as "no eval number", which is the correct
rendering and the reason the table exists — *a break in the recording path and a baseline that
scored nothing are the same shape in a results column*. Added `IBAC_EVAL_LINE` and an eval branch.

**Defect 3 — an axis nobody had named.** `ctrl`'s eval record carries `episodes: None`, which is
**correct**: it never evaluates a saved policy, but reports `Eprew200`/`Eprew0`, a running mean over
a trailing window, from inside the training loop. Eleven baselines measure a checkpoint; `ctrl`
measures a trailing average of the run. Recorded as `COMPARABILITY_CONTRACT.md` §5d.

**Why the table generates itself.** Twelve rows across seven families, each with its own log format,
is exactly the hand-maintained artifact that goes stale — and this project's register already holds
several entries about counts that rotted. It prints the estimator, the frame stack and the render
backend *beside* each number, and refuses to sort by return, because the finding of §5b–§5d is that
a bare column invites a comparison the data does not support.

**The `frames` column is the R4 evidence.** A requested 10,000 executed as **9216** (`idaac`),
**10000** (`ctrl`), **10112** (`ibac_sni`) and **10240** (`ppg`) — four different quanta, none equal.
"Equal training length" is an intent here, not a fact, and the column says so.

## 2026-09-03 — `OFFLINE_EVAL`: the grid becomes runnable on the container

`datasphere/native/run_probe.sh` gains `run_offline_eval()` and a dispatch branch beside
`PREFLIGHT_ONLY`; `scripts/eval_grid.py` becomes a payload member.

**This is forced by a measurement, not a convenience.** The same 60k `drqv2` snapshot, on
eval-easy / scene 0 / twenty episodes, returns **41.66** and **50.73** inside the container (two
independent jobs, RL-ViGen's own `eval()`) and **3.41** on this laptop from RL-ViGen's own
`_eval_regime`, against **2.94** from `eval_grid.py`. Upstream's loop fails here exactly as mine
does, so the evaluator is exonerated and the *machine* is the variable. Every generalisation number
this project computed locally from a container-trained checkpoint is therefore suspect, and the
grid has to run where the policy was trained.

**One job answers the open question.** `OFFLINE_EVAL_DEVICES` takes a comma list and runs the same
grid once per device in one container, both under EGL, writing `offline_eval_<device>.jsonl` each.
CUDA and CPU agreeing near 41 indicts the renderer (`MUJOCO_GL=egl` against macOS `glfw`); a CPU
pass near 3 indicts the device. Running both in one job rather than two is the difference between
one answer and two half-answers at twice the cost.

**It reuses the whole bootstrap and changes no measurement path.** The payload extraction, the
RL-ViGen archive, the dependency install, the budget gate and the import gate all run exactly as
for a training cell; only the final dispatch differs. `PIPESTATUS[0]` rather than the pipeline's
status, because the grid's output is teed to the log and `tee` would otherwise mask a failure.

## 2026-09-03 — the finiteness probe stops trusting file names

`datasphere/native/family.py`, `FINITENESS_PROBE`.

It chose its loader with `path.endswith(".msgpack")`. The runner copies every family's checkpoint
to `snapshot.pt` whatever it was called, so `ctrl`'s flax msgpack reached the probe as a `.pt`,
took the torch branch, and returned `ModuleNotFoundError: No module named 'torch'` — `ctrl` is JAX
and excludes torch deliberately. **A gate of ours failed a cell whose training had already
succeeded and reached its endpoint** (`bt1f1kg6kiemsj7j8f6q`, exit status 0).

**This is a repeat, which is why it is written here and not only fixed.** The register already
records an alda terminal save "verified" by its filename rather than its bytes. Choosing a loader
by extension is the same error in a different place, and the probe's own docstring had *already*
named ctrl's msgpack — the knowledge was present and the code still keyed on the name.

Now it sniffs magic bytes (`PK\x03\x04` or a `0x80` pickle opcode means torch-shaped) and tries
torch, msgpack and numpy in the order that suggests, falling through on exception and reporting
which loader succeeded as `"loader"` in the JSON. A wrong guess costs an exception, never a failed
cell. Both directions are covered: a torch file named `.msgpack` loads via torch, a non-torch file
named `.pt` via numpy.

## 2026-09-03 — the W&B shim stops refusing and starts recording (runner contract 10)

`runnable/_shim/wandb.py`, rewritten. `datasphere/native/run_probe.sh` exports `RLGEN_WANDB_JSONL`
into the run directory. `RUNNER_CONTRACT` 9 → 10.

**Why the old design had to go, stated fairly.** [Codex 2026-09-01] built it fail-closed — every
attribute raised — to satisfy an unconditional upstream import while rejecting all tracking. That
is a good design against the threat it names. It is also unsatisfiable by `ctrl`, whose
`train_ppo.py:111` calls `wandb.init(...)` with no flag to disable, so a raising `init` means the
twelfth baseline cannot run at all. Attempt #10 (`bt1efc5ma3m0lohlnq2d`) died there.

**The property preserved is "no network", which was the point; "raise" was only the means.** The
shim opens no socket, imports no client, and the test asserts that at the source — `import
requests`, `import socket`, `urllib`, `http.client` and `wandb_sdk` must all be absent from the
file. `init` returns a run object; `log` appends one JSON object per call to `RLGEN_WANDB_JSONL`.

**Recording rather than no-op'ing, deliberately.** A silent no-op would let a baseline whose only
metric sink is W&B finish with empty curves and look successful — the exact failure shape this
project keeps finding elsewhere. Recording makes the metrics an artifact instead: `ctrl`'s
`wandb_offline.jsonl` is now one of its optional curves, so attempt #10's numbers would have
survived had this existed.

**Fail-closed is still reachable and is one variable away.** `RLGEN_WANDB_STRICT=1` restores the
original raising behaviour exactly, for any probe that wants to assert a baseline is silent. The
test exercises both directions.

**Two details that are load-bearing.** Values arrive as numpy scalars and arrays and W&B media
objects, none JSON-serialisable, so `_jsonable` unwraps `.item()`/`.tolist()` and falls back to
`repr`; and unknown attributes return a permissive object that is callable, subscriptable,
iterable and attribute-settable, because upstream code does all four to W&B objects and a shim
that breaks on any of them merely moves the crash.

**Contract 10 because the payload changed, not the runner alone.** The shim ships inside the
payload while `run_probe.sh` is a separate job input; an old payload against the new runner still
fails `ctrl`, and that is precisely the drift the contract number exists to catch.

## 2026-09-03 — `ppg` joins the offline grid (ninth family of twelve)

`scripts/eval_grid.py` gains `--family ppg`: `_ppg_setup()` and `run_scene_ppg()`.

**The gap was not the one the plan named.** The points-list carried "ppg needs an eval loop". It
does not — `runnable/_launch/ppg_eval.py` has been that loop since 2026-09-02, and
`ppg_cell.sh` already calls it with an `{eval_episodes}` positional. What ppg lacked was a place in
the *regimes × scenes* grid, which is a different instrument: `ppg_eval.py` measures one regime at
one scene at the end of a cell, and C43 needs two regimes measured against each other across the
scene sweep. Recorded because the plan item was wrong in a way worth remembering: a task named
after a missing artefact, when the artefact existed and something adjacent was missing.

**It reuses PPG's own machinery for everything that moves a number.** `get_venv` (which already
took `scene_id`, from the earlier robosuite adapter), `Roller`, `VecMonitor2`, and `PpoModel.act`.
The new code is the loop, the venv close, and the record.

**It samples rather than taking the mode**, restating `ppg_eval.py`'s own declaration: PPG ships no
deterministic-action path. The grid must report the estimator its launcher reports, so this is
consistency, not a preference — but a Gaussian mean would read higher, and that is why it is
written down here as well as there.

**Two settings are contract.** 64×64, because `ppg_cell.sh` exports `RLVIGEN_IMAGE_SIZE=64` before
training and ImpalaCNN's flattened width was fixed there — the identical failure mode idaac had at
84. And `runnable/ppg` on `sys.path` *before* `torch.load`, because `LogSaveHelper` pickles the
whole model and unpickling imports `phasic_policy_gradient` as a top-level package.

**Smoked on a fixture, not on a policy.** No ppg checkpoint exists locally, so the path was
exercised against an untrained `PhasicValueModel` built through ppg's own factory and pickled the
way `LogSaveHelper` does. Two regimes × one scene × two episodes ran clean in 37s and returned
3.14 (train) / 1.88 (eval-easy). **Those numbers are random-policy numbers and say nothing about
ppg**; what they establish is that the env builds, the roller counts closed episodes, the action
shape matches (`ac_space R[7]`, a fourth independent confirmation of Door's 7-DOF), and the records
carry their axes. The path is unverified against a *trained* ppg checkpoint, and that gap is real
until a production cell returns one.

## 2026-09-05 — P20: realized placement and episode diagnostics are retained

`setup/apply_patches.py`, patch P20, against `RL-ViGen-upstream/envs/robosuiteVGB/robosuitevgb/vgb_wrapper.py`.

The offline grid already paired episodes by condition seed and stored an observation fingerprint,
but that fingerprint could not answer whether performance depended on the actual Door placement.
P20 records the post-reset Door root-body position and quaternion, then derives a placement hash
from those values in `scripts/eval_provenance.py`. At the same common environment boundary it
retains raw reward summaries, time-to-success, applied mode/scene, and normalized-action clipping
diagnostics. The action path is unchanged; the records become richer and remain bounded rather
than storing per-step trajectories. `eval_grid.py` fails closed if a family does not expose one
complete diagnostic row per measured episode.
