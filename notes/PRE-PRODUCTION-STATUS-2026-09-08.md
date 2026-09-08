# Pre-production status, 2026-09-08

Successor to `PRE-PRODUCTION-STATUS-2026-09-07-EVENING.md`. What changed today, what it cost, and
what is left.

## The day's shape

The v196 attestation canary failed, and reading its log rather than its status produced everything
below. One job, one budget overrun, four defects and five measurements.

## 1. The canary (A42)

`bt1f8b5gb39jgadqngke`, `dmc_gb`/`soda`, is the **first cell in this project's history to execute
the A22 production Places365 path**. It reported ERROR at `S: 8000` of 10,000, killed by its own
`timeout 3600s` — the raise to 9000s landed after submission. The Places365 train path itself
completed: `Loaded dataset from /tmp/native-work/places365-root`.

**Measured, and now carried in the instruments:**

| quantity | value | how |
|---|---|---|
| `soda` throughput | 2.92 fps | 13 steady episodes at 171.1s per 500 frames |
| container bootstrap | 606.2s | 3600s wall − 2993.8s of in-cell log |
| Places365 first-load | 561.8s | episode 3's 732.9s against the 171.1s steady state |
| `drqv2` throughput | 27.19 fps | `results/logs/bt15e9v1k2ngmb71hnjn…train.csv`, 99,500 frames / 3659.8s |

The Places365 surcharge is **constant in dataset size, not linear** — established, not assumed: the
fixture's train split is 1,000 images and `ImageFolder`'s scan measures ~2 µs/image locally, so the
cost is DataLoader worker startup plus the first decoded batch. Had it been per-image, the ~1.8M
production split would have extrapolated to ~7.7 hours per cell and every `svea`/`sgqn`/`soda`
budget in the fleet would have been unrunnable.

## 2. Defects found and fixed

**The Places365 integrity check certified a split the run never opened.** `check-asset` validated
`val/images` unconditionally, including under `NATIVE_PLACES365_SPLIT=train`. So the canary verified
36,500 val images while training on 1,000 train ones — the split that *is* the augmentation
mechanism was the only one never checked. Worse at production scale: the canonical
`places365standard_easyformat.tar` has no flat `val/images`, so the first real cell would have died
at the guard *after* its 21 GB upload. This is the same defect external review 24 found twelve lines
below, in the loader assertion, and fixed there.

**`audit_job_budgets.py` certified the job that then died** — four separate errors: no Places365
term at all; `BOOTSTRAP_SECONDS = 200` against a measured 606 (its own docstring simultaneously
claimed 700, and the prose number is the one that gets quoted); `CELLS=([A-Za-z_]+)` excluding
digits, so `drqv2` parsed as `drqv` and fell to the pessimistic floor; and consequently a **false
FAIL** on four configs that had already run to completion — the error class the file's own docstring
names as its reason to exist.

Both fixes are covered by tests that **execute** the shipped code rather than restating it, which
also disproved an older test module's stated premise that the Places365 block "runs only inside the
container" and could only be read.

## 3. Configuration changes, all landed before the wave

No wave was in flight, so the config freeze did not bind and these cost one wave instead of two.

- **`ctrl` and `ibac_sni` to `frame_stack=3`** (A40 REVISED-2). The cost estimate was wrong three
  times; tracing the path gave the answer: **neither baseline had any stacking mechanism at all**
  on the Door path. Both stacks are authored, with `baselines`' semantics. On-policy primary
  comparison pairs go **1 → 3**.
- **`ibac_sni` `lr` 7e-4 → 5e-4** (A43). The port runs CoinRun's IMPALA trunk at MiniGrid's
  learning rate — a pairing nobody chose. The rate moves to the architecture's lineage; the decay
  does not, because `torch_rl` has no scheduler and authoring one is a second unvalidated change.
- **`ppg` `aux_lr` 3e-4 → 5e-4** (A44). The supplement searched "the learning rate", singular;
  OpenAI ships `--lr` and `--aux_lr` as separate flags at the same default, so the authors' own
  recipe leaves the auxiliary optimizer alone. Our 3e-4 applied A41's paper exception to a value the
  paper does not contain.

## 4. Primary sources read, and three reviews corrected

A41 EXTENDED, A45 and A46 came from opening PDFs instead of trusting the review corpus.

- **SGQN**: reviews 17/19/20 all report the paper's quantile as **0.90**. Table 3 says **0.95**
  (Walker walk/stand, Finger spin) and **0.98** (Cartpole, Ball in cup), and it is explicitly
  per-task, chosen by inspecting each environment's foreground/background pixel ratio. Reviews
  17/18/20 report a consistency weight of **0.70**; the paper defines it only symbolically as λ in
  `L_Q + λ L_C` and **never assigns it a value**. Values unchanged, disclosure corrected: not "we
  deviate from 0.90/0.70" but "this is a per-task parameter nobody has tuned for Door".
- **CTRL** (A45): review 17's disputed list is confirmed **verbatim** against Table 2 — and reviews
  19/20/21 were still right to keep the released code, since Table 2 is a Procgen table. Every
  deviation is now enumerated in the provenance string, including one nobody had named: the paper
  gives a *single* learning rate covering representation learning, so the released `lr_ctrl=1e-4`
  contradicts its own paper by 5× on CTRL's defining objective.
- **IDAAC**: the project's highest-stakes paper claim, `order_loss_coef=0.1`, **verified**. The
  supplement's sentence names four values and `families.json` sets three, which looked like a gap —
  `--value_epoch` already defaults to the paper's 9, as do `--gae_lambda` and `--value_loss_coef`.
  The C2 recipe is complete.

**The general lesson, recorded because it outlives these parameters:** three reviews stated a
paper's hyperparameter, agreed with each other, and were wrong. Agreement between reviews is not
evidence about a paper.

## 5. Two things nobody had enumerated

- **Reward normalisation is a fourth comparability axis** (`rlgen/protocol.py::REWARD_NORMALIZATION`),
  splitting 3/9 — `idaac`, `ppg`, `ctrl` optimise a normalised reward — over a set **disjoint** from
  time-limit handling's 3/9. Declared, not equalised, with the argument stated: equalising is less
  faithful in both directions, the transplanted convention's condition is not violated on Door (a
  running normaliser is scale-adaptive, unlike a frame stack), and every evaluator reports the raw
  return, so it is a training-objective axis rather than a units one.
- **The common 600k budget lands between 0.375% and 120% of each method's own source horizon**
  (A46) — 500k for `rad`/`soda`/`alda`/SGQN, 1.1M for the RL-ViGen natives, 1M for `idaac`/`ppg`,
  8M for CTRL, 160M for IBAC-SNI. One concrete consequence: `idaac` and `ppg` decay linearly to zero
  over the literal 1M steps and stop at 600k, so both finish at **40% of their initial learning
  rate**, never annealed.

## 6. State

`production_gates.py`: **34 pass, 1 fail, 9 owner** — the one failure is `source tree frozen`,
i.e. this work is uncommitted as this is written. Seven `v197` payloads built and each verified to
bind to the live tree with `--require-evaluator-identity`. `verify_sources.py` passes;
`refresh_clone_patches.py --check` passes; every job config fits its own budget.

`ctrl` and `ibac_sni` attest budgets are raised to 5400s, because their measured throughput was
taken at `frame_stack=1` and no measurement of the stacked rate exists — that cell *is* the
measurement.

## 7. What is left, in order

1. **Commit**, and re-run the full suite against the committed tree.
2. **The v197 attestation wave**, seven cells. Five fit 3600s; the two Places365 cells need the
   raised 9000s.
3. **Pilot `ctrl` and `ibac_sni`** before three production seeds each. Read for non-degenerate
   learning, not a score. A43 fixes the disambiguation in advance: `ibac_sni` changed twice, so
   revert its `lr` first if the pilot fails.
4. ~~Phase 3 gaps~~ — **all three closed today**, and each found something:

   - **Git identity in the payload manifest.** `contract.py build-payload` now stamps
     `source_commit` and `source_dirty`, so every record carries the tree that produced it
     transitively. `source_dirty` is recorded, not refused: that judgement already lives in
     `gate_source_tree_frozen` and two copies of a rule can disagree.
   - **A durable second result location.** The gap was smaller than the plan assumed —
     `/tmp/native-out` *and* `/tmp/native-work` are both already host-mounted, so checkpoints have
     been durable as written since 2026-09-07. What was missing was a second *device*, and
     requiring one is only worth anything if it is verified: production scale now refuses without
     `NATIVE_RESULT_MIRROR`, **compares the filesystem ids**, and refuses a mirror on the same
     volume — or an id it cannot read — rather than accepting it with a warning.
   - **The attempt ledger's outcome half.** `scripts/audit_attempt_ledger.py` derives each
     attempt's state from artifacts that already exist (the records filename carries the job id;
     `evaluator_revision`, `record_delivery` and `execution_kind` carry the rest). Nothing new is
     written, because a ledger the runner must remember to update is a ledger that will be wrong
     in the direction of looking complete. It reports `NO-OUTCOME` rather than guessing between
     RUNNING and FAILED, which are indistinguishable from disk. Wired into `production_gates.py`
     with `--strict`, which fails only on the precise shape of the problem: a config submitted
     twice with a predecessor whose outcome cannot be read.

   **It found a real defect on its first run.** `results/submissions.jsonl` held 32 rows and
   *every one was a fixture* — three test modules (five, once the check was derived rather than
   listed) stub the DataSphere CLI, run `job.sh submit`, and `job.sh` appended to the repo path
   because `SUBMISSION_LEDGER` defaults to it. Nothing failed; the production attempt record simply
   became unusable while continuing to look like a record. Fixed at the source, with
   `tests/test_the_attempt_ledger_is_not_written_by_tests.py` deriving the rule so a sixth module
   cannot reintroduce it.
5. Still genuinely open and correctly so: `ibac_sni`'s VIB parity (64-d vs 256-d, 1 sample vs 12 —
   an engineering gap no configuration closes), CTRL's raw-vs-executed action in the clustering
   objective (diagnostic wired, comparison never run), and the nine OWNER gates.


---

## Addendum — four more, found after the first pass

**A47. IBAC-SNI's VIB latent was a literal, not the unreachable gap four reviews called it.**
Reviews 17-20 and A37 all record "64-d against CoinRun's 256-d" as part of a gap no configuration
closes. It is `model.py:212`, a constant — and the constant means opposite things on the two
branches this port hybridises: in `torch_rl`'s MiniGrid setting the embedding **is** 64, so it
imposes no dimensional squeeze at all; on CoinRun's 2048-d trunk (which A37 adopted) it became a
**32x** squeeze against CoinRun's own **8x**. Now 256 on the impala trunk, 64 kept where it is
correct. The 12-sample half of the reviews' finding stands and is real new code. The two had been
filed together for weeks and one of them was a one-line change hiding behind the one that is not.

**The reward-normalisation axis, checked on every surface.** It was recorded as
training-objective-not-units on the strength of the endpoint evaluator, which was already known to
read raw returns. The training *curve* was unchecked for all three families and is also reported.
All three are raw: idaac and ctrl read `info['episode']['r']` from a VecMonitor that sits inside
the normaliser; ppg gathers roller stats at `ppo.py:272`, **before** the normaliser touches
`seg["reward"]` at `:274`.

**A blocking axis that was correct by coincidence.** `comparison_blocks.py` excluded render size on
the reasoning that "crop policy already equalises what the network sees at 84" — true of
`rad`/`soda`, false of the 64-render group, as its own comment admitted. Now blocks on the
**network input**. It changes no pair, because each mechanism group happens to be internally
uniform in input size, which is exactly why it is worth adding: the reported set is now correct by
construction rather than by luck, and a test fails if the axis ever stops being free.

**Two stale prose numbers behind an owner ruling.** `family.py`'s comment said "four sampling
families … ~29 GPU-h" and `SAME-AXES-VERDICT.md` carried "28.7 GPU-h … about 3%" into the "no
secondaries" ruling. The code was always right — it derives the set from `FAMILY_EVAL_POLICY_MODE`,
so review 24 moving `ctrl` to `mode` correctly made it three. Actual cost **~21.6 GPU-h, ~2.4%**, a
quarter less. And it now buys more: with the frame-stack axis closed, policy mode is the **only**
confound left in the on-policy group, so that pass would take it from 3 primary pairs to all 6 —
and it is the only thing standing between `ctrl` and any primary comparison at all. The ruling is
the owner's and is not overturned; both of its inputs have moved since it was made, in the same
direction, and neither movement was written down.

This is the same defect shape as the morning's `BOOTSTRAP_SECONDS` (docstring 700, code 200) and
as SGQN's misquoted 0.90: **prose that disagrees with the thing it describes, where the prose is
what gets quoted.** Three instances in one day is a pattern, not a coincidence.

---

## Addendum — the wave, priced and pre-flighted

Seven `cfg-*-attest-v197.yaml`, each bound to a `payload-v197-*` verified against the live tree
with `--require-evaluator-identity`, all recording `source_commit cb98337e` and
`source_dirty False`.

| cell | budget | audit says it needs |
|---|---|---|
| idaac | 3600s | 1183s |
| ppg | 3600s | 1268s |
| alda | 3600s | 2146s |
| ctrl | **5400s** | 1811s |
| ibac_sni | **5400s** | 2312s |
| rlvigen (svea) | **9000s** | 5905s |
| dmc_gb (soda) | **9000s** | 5905s |

**~5.7 GPU-hours in total**, ~1.6h wall clock if run concurrently — against a production campaign
near 893 GPU-hours, so about 0.6%. `ctrl` and `ibac_sni` carry the raised budget because their
measured throughput was taken at `frame_stack=1` and no measurement of the stacked rate exists;
this cell is that measurement. Budgets are ceilings, not consumption: a job exits when it finishes.

**Pre-flighted before spending any of it:**

- `check-asset` run locally with the config's declared values against the real
  `places365-train-attest.tgz` — exit 0. The declared count and digest are the **train** tree's
  (1000, `c08327c5…`), which is the split these cells actually consume; the old config declared
  the val tree's and would have certified 36,500 images nobody opened.
- `verify_runtime_observation_geometry` accepts the exact tensors both authored stacks emit
  (`ctrl` NHWC `(1,64,64,9)`, `ibac_sni` HWC `(64,64,9)`) and **refuses** the pre-change
  single-frame shapes. So the wave is self-checking on precisely the new code: if the stack failed
  to reach the evaluator, the cell dies loudly instead of reporting a number measured on a
  one-frame policy.
- Every input file present; `audit_submission_configs.py` clean; `audit_job_budgets.py` clean.

**Deliberately not bundled:** five baselines (`drqv2`, `drq`, `curl`, `sgqn`, `rad`) will still
have no record under the live closure after this wave, so the runtime geometry assertion will
never have run for them. That is bounded rather than unsafe — a mismatch fails the cell, it does
not produce a wrong number, and the gate says so in its own PASS text. Closing it costs roughly
five short cells (~2.8 GPU-hours). It is the obvious next candidate, and it is worth deciding with
the wave's real throughput in hand rather than before it.
