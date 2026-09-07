# External review — triage against the real tree

Written 2026-09-04. The review was performed on an **incomplete ZIP**; this checks each item against
the working tree instead. Read-only: nothing here was fixed by the triage itself, so ownership of
the fixes is still open (see `claude-answers.md`, QC1).

**Headline: I agree with the reviewer's no-go.** But two of its five P0s are upload artifacts, one
severe conditional P0 resolves in our favour, and the two items I would treat as most dangerous are
ones the review ranked P1.

---

## A. Upload artifacts — not project defects

| # | claim | finding |
|---|---|---|
| 1 | "not the production repository it describes" | **ARTIFACT.** In the tree: `.git`, `families.json`, `run_probe.sh`, `production-schedule.json`, `source-lock.json`, `requirements-native.txt`, the IBAC launcher all present; `runnable/ibac_sni/` has **76** `.py`, `rlgen/` has **72**. |
| 2 | "28 collection errors; gate broken" | **ARTIFACT.** Full suite in-tree today: **one** failure, the deliberate `test_internal_links_resolve[PROJECT-INDEX.md]` whose target resolves only in the canonical tree. |

These do not survive contact with the tree, and they inflate the review's severity. **#3 is
untouched by this and remains real**: there is still no immutable commit meaning "the code whose
results we report."

## B. Verified real — fix before any production row

| # | claim | evidence |
|---|---|---|
| **7** | result metadata contradicts the evaluator | **CONFIRMED, highest priority.** `normalize_curves.py` stamps `ppg:"none"`, `ibac_sni:"separate-script"`, `ctrl:"discrete-only"`; `eval_grid.py`'s own docstrings say **"It SAMPLES"** for those families. Silent, and it travels with every row. |
| **8** | provenance regression | **CONFIRMED.** `snapshot_md5` exists only in `eval_across_scenes.py:410`; the newer grid records none. Acute because ibac_sni's `model_type` **and** `entropy_coef` both changed on one day — two rows would be indistinguishable. |
| **17** | evaluators leak envs | **CONFIRMED.** Two `close()` calls in the whole file: ppg's guarded one (`:353`) and the output sink (`:704`). Five families never close. |
| **18** | temp dirs leak | **CONFIRMED.** `mkdtemp` at `:478` (alda) and `:824` (ibac_sni); no `rmtree`/`TemporaryDirectory` anywhere. |
| **23** | CPU default contradicts C95 | **CONFIRMED.** `ap.add_argument("--device", default="cpu")` (`:742`) on the production entry point. |
| **6** | audit instruments stale | **CONFIRMED.** `scripts/handicaps.py` still reports *"C3 `ibac_sni` at 64×64 is a 227× model"* as live, after the default became the 360,399-parameter impala head — which is C3's repair. |
| **24** | protocol stale on estimators | **CONFIRMED, and self-contradictory inside one file.** `EVAL-PROTOCOL.md:113` says three sample and "the other nine keep taking a mode"; `:436-437` records **"ctrl samples"**. Four samplers. |
| **40** | env reproducibility uncertified | **CONFIRMED.** `source-lock.json` holds `accepted_adaptations`, `places365_validation_asset`, `nested_repository_commits` — **no dependency versions, no container digest**. This is C29, unclosed. |
| **20/21** | verification fail-open; RNG asymmetry | **CONFIRMED EMPIRICALLY.** Job `bt1sgcg49j6d6jk84vuj` emitted the abstention **16 times**, so the regime is currently *unverified* in-container. And `eval_across_scenes.py:138-146` probes with `reset()+step()` (consuming C69's global stream) while `eval_grid` deliberately does not — so **identical seeds do not imply identical door placements across evaluator families**. That asymmetry is mine and it undercuts the paired-comparison claim. |
| **37** | post-selection bias in reporting | **CONFIRMED.** `results_table.py:171-175` pools numerator and denominator over performance-selected `usable` scenes, so different baselines average different scene sets. |
| **38** | no policy-scale gate | **CONFIRMED.** `check_checkpoint_finite.py` tests finiteness only. σ ≈ 4.3 is perfectly finite and useless — our own runaway is the proof that finiteness is insufficient. |

## C. Resolved in our favour

| # | claim | finding |
|---|---|---|
| **14** | raw-vs-clipped PPO likelihood seam (the review's most severe conditional P0) | **RAW-STORED-CORRECT.** `algos/base.py:137` `action = dist.sample()`; `:142` `env.step(action.cpu().numpy())`; `:150` stores the **raw** action; `:159` scores that same raw action; `algos/ppo.py:82` forms `ratio = exp(dist.log_prob(sb.action) - sb.log_prob)`. Raw against raw. Clipping never flows back into the stored action. **Residual:** `.cpu().numpy()` shares memory on a CPU device, so an in-place clip in a wrapper would corrupt the stored action — safe on CUDA, latent on CPU, which is another reason #23's default is wrong. |

## D. Softened

- **#19** — there *is* an `--append` flag (`:637`); `"w"` is only the default. No resume/skip-completed
  logic, so the substance stands, but "restart destroys the prefix" is conditional.
- **#13 / #39** — the arithmetic is right (1 − 0.6827⁷ = **93.1%** of 7-D action vectors have at
  least one coordinate outside [−1,1] at σ=1). But this is shared by most continuous PPO with σ=1
  init and clipped actions. It is a **measurement gap**, not a defect — and #39's actual ask (log
  the vector-level clip rate rather than the per-coordinate analytic proxy) is the right fix.

## E. Adopted — better than our own framing

- **#15.** If `log_std` is state-independent then `H[q(a|z)]` does not depend on `z`, so IBAC's
  conditional-entropy term is **already degenerate**. This *helps* us: `entropy_coef=0` removes far
  less of "IBAC" than it appears to. Better than the argument we had.
- **#26.** One frame vs three changes the **effective observability**, not merely encoder capacity —
  a single RGB frame does not expose velocity. Sharper than our C2 wording.

## F. Agreed, already recorded, correctly weighted

#3, #4, #9 (2/12 evaluator burdens discharged), #10, #11, #12, #25, #30, #31, #32, #33.
Two deserve elevation: **#9 and #30** are, with #7, why the fleet would currently produce rows
nobody could interpret. **#32 now has evidence rather than being a worry** — see below.

## G. Agreed, not independently verified

#5 (partially: `RECOVERY-HANDOFF.md` still contains "hold 0.01" alongside the later 0.0 decision),
#16, #22, #27, #34, #35, #36.

## H. Elevated above the review's own ranking — nothing in the project covers these

- **#28 (statistical inference).** Not specified anywhere. Episodes are clustered by training seed
  and by scene; treating 200 as IID understates uncertainty. Training seed must be the outer unit.
- **#29 (checkpoint-selection bias).** **Newly dangerous because of work done today.** Making all
  twelve emit trajectory stamps made "best over the trajectory" reachable for the first time. If the
  best checkpoint is selected on eval-easy/medium/hard and then reported on that same regime, the
  test set has silently become a validation set. Endpoint-as-headline avoids it; anything else must
  select on the **train** regime or a **held-out** one.

## I. One item the review could not have known

`bt1ptu2e6stuko76s6dd` (the `dmc_gb`+`alda` preflight) **failed on `signal 9` — SIGKILL**, with a
high-water of **11.0 GiB and climbing**, not on a missing dependency. `plan_production.py` already
carried `ALDA_FIXED_GIB = 15.3` against `gt4.1`'s `usable_ram_gib = 14.5`: **alda cannot fit that
tier by construction** and belongs on `gt4i.1`. The cost model predicted it and the job was
submitted to the wrong tier anyway — my error, not a code defect. This is a concrete instance of
review item **#32**, and at 6e5 it would fail later and far more expensively.

Also from that job: **`rad` completed** and `run_curve_eval` returned `stamps=3` with 28 records, so
`run_scene_dmc_gb` is exercised and works. **`alda` is now the only evaluator family never run.**

---

# Second external review — triage (2026-09-05)

Same method: checked against the working tree. This reviewer was **more careful about the archive
limitation** — it explicitly declines to count omitted-file failures as defects — so it has no
equivalent of review 1's #1/#2 artifacts. It is also **deeper on the algorithm ports**, and found
four material defects review 1 missed entirely. All four verified below.

## Verified real, and new

| # | claim | evidence in tree |
|---|---|---|
| **2-7** | PPG's auxiliary KL is scaled wrong for a continuous action space | **CONFIRMED.** `ppg.py:198` is `td.kl_divergence(mb["oldpd"], pd).mean()`. For a 7-D Normal that averages over the action dimension while the PPO losses **sum** over it, so the effective `beta_clone` is ~7× too small. **The project already documented this and declined to fix it** — `RUNNABLE-ORIGINALS.md` says verbatim *"Recorded, not fixed … The effective `beta_clone` is therefore 7×"*. |
| **2-8** | IDAAC's `level_seed` labels a worker slot, not an instance | **CONFIRMED structurally.** `envs.py:81-97` `_LevelSeed` supplies a constant per worker; `train.py:205` reads it; `train.py:218` resets `nsteps` on `done`. A 256-step rollout is shorter than the 500-step episode but is not synchronised to episode starts, so two observations sharing a "level" can straddle an episode boundary and the temporal-order target has **no referent** for that pair. |
| **2-12** | IDAAC's evaluator ignores the requested device | **CONFIRMED.** `run_scene_idaac` hardcodes `device = torch.device("cpu")`, so `--device cuda` is silently discarded for that family. |
| **2-24** | IDAAC's trainer never seeds NumPy | **CONFIRMED.** `train.py:80` sets `torch.manual_seed` only; no `np.random.seed` in `train.py`, `envs.py`, or `runnable/_shim/`. Under [C69](../docs/CONSTRUCTION.md#c69) door placement is drawn from the **global NumPy RNG**, so two idaac runs at the same `--seed` do not see the same task instances. |

## The finding I would act on first

**2-1 / 2-21 — the paired comparison is not paired, and this reviewer supplies the right fix.**
Review 1 raised the same asymmetry (its #21) and I owned it; this reviewer goes further and rejects
the obvious repair. Reseeding once after the verification probe is not enough, because any
difference in construction, probes, or reset counts between families reintroduces the skew. The
robust design is **per-episode condition seeding**: seed from `(eval_seed, scene, episode_index)`
immediately before each *measured* reset, after all construction and probes, and record the realized
initial placement as evidence. That makes pairing independent of everything upstream of it.

Consequence to state plainly: **existing common-grid numbers are not placement-paired across the
RL-ViGen / non-RL-ViGen boundary**, because `eval_across_scenes.py:136-149` probes and `eval_grid.py`
deliberately does not.

## The inconsistency in our own standard that 2-7 exposes

We argued — for `ibac_sni`'s entropy coefficient and again for its architecture — that **a constant
scoped to a different action space or input is not a tie worth preserving**, and we changed both.
`ppg.py:198` is the same situation: a reduction that was correct for a Categorical became wrong when
the adaptation changed the tensor's rank. We preserved the literal line there and called it fidelity.
**Both positions cannot be right.** Either literal preservation wins and `ibac_sni` should go back to
0.01, or semantic preservation wins and PPG's clone loss needs `sum` over the action dimension (or an
explicitly recalibrated coefficient). I think the reviewer is right that literal preservation is the
*less* faithful choice once rank changes — which means PPG, not ibac_sni, is the row that is
currently mislabelled.

## The striking inversion

`idaac` was one of only **two** baselines whose shared-evaluator burden was discharged, which made it
look like the best-validated row in the table. It now carries **three** verified defects — a
semantically incoherent order target (2-8), an evaluator that ignored the device (2-12), and unseeded
training placements (2-24). The apparently best-validated baseline is the worst-placed one.

## Second review — remaining sections, read in full (2026-09-05)

My first pass covered only §1/21, §7, §8, §12, §24. The rest, with verdicts:

### Newly verified real

| § | claim | evidence |
|---|---|---|
| **2-4** | **online evaluation alters the training experiment** | **CONFIRMED.** `RL-ViGen-upstream/train.py` calls `utils.set_seed_everywhere(cfg.seed)` once, and `eval()` (`:126`) calls `self.eval_env.reset()` (`:131`). Both envs draw the same global NumPy stream that [C69](../docs/CONSTRUCTION.md#c69) says sets door placement, so **every periodic evaluation consumes placement draws that would otherwise go to training**. Same algorithm + same seed + different eval schedule = different training run. **Our own P14 made this worse**, since it evaluates many scenes. The twelve have wildly different native eval cadences (5×2 for the RL-ViGen five, 0 for ppg/ibac_sni, continuous for ctrl), so this is a *cross-family* confound, not just noise. |
| **2-14** | Places365 partition silently changed | **CONFIRMED, and mis-classified.** `configure_places365_val.py:34-35` rewrites `use_val=False` → `use_val=True` and disables fallback. `source-lock.json` records the asset at **36,500 images** against Places365-Standard train's ~1.8M — roughly **50× less background diversity**, for three methods (`svea`, `sgqn`, `soda`) whose entire mechanism is background-overlay invariance. That is learning-affecting, not PLATFORM. |
| **2-11** | CTRL checkpoints do not bind their config | **CONFIRMED as a design defect, not yet manifesting.** `eval_grid.py:604` hardcodes `CTRL_DEFAULTS(num_clusters=200, n_att_heads=2, cluster_len=10, …)`, which today matches ctrl's own flag defaults (`train_ppo.py:104,107,108`). But `families.json` passes `--cluster_len={cluster_len}` as a **template**, so a descriptor change would silently desynchronise the evaluator's reconstruction target from the checkpoint. Second copy of production hyperparameters — the "one number, one home" failure again. |
| **2-16** | 600k is a small fraction of some native horizons | **CONFIRMED.** `train_ppo.py:87` — ctrl's own default is `train_steps = 25_000_000`. **6e5 is 2.4% of it.** |
| **2-30** | gamma differs materially | **CONFIRMED.** ctrl `gamma = 0.999` (`train_ppo.py`), idaac `gamma = 0.999` (its logged Namespace), ibac_sni `discount = 0.99`. At a 500-step horizon that is an effective planning horizon of ~1000 vs ~100 — a 10× difference sitting inside "algorithm identity". |

### Agreed, and better argued than our own version

- **2-19 — retention is not invariant to reward offset.** A constant shaping offset `c` changes
  `R_eval/R_train` without any behavioural change, and Door has dense shaped reward with a non-zero
  floor. The competence gate stops the *worst* pathology (two chance policies scoring 1.0) but does
  not fix dependence on the arbitrary reward origin. **Success rate is the cleaner headline**, with
  a floor-adjusted `(R_eval − R_floor)/(R_train − R_floor)` for the dense version. I had not
  considered this and it is correct.
- **2-20 — P-C76 is three different estimands**, not a bookkeeping choice: (A) appearance robustness
  on trained geometry, (B) within-scene appearance effect aggregated over scenes, (C) joint
  appearance+scene shift. A scene-0 denominator with a ten-scene numerator silently reports (C)
  while sounding like (A). **The grid already collects enough per-scene data to report all three**,
  which is the right answer and cheaper than choosing.
- **2-17 — adaptive seed allocation is outcome-dependent sampling.** This lands on a default *I*
  set: "one seed everywhere, then concentrate seeds where comparisons are live". A method with an
  unlucky first seed gets classified floor and never receives more trials. For final rows it must be
  a fixed minimum for everyone, or a predeclared stopping rule. **My default was wrong.**
- **2-37 — present the analysis hierarchically.** Tier 1 = the RL-ViGen five (common observation,
  frame stack, horizon, reward, evaluation structure) is a genuinely controlled comparison. Tier 2 =
  the twelve-way port-at-design-point table. Do not give Tier 2 Tier 1's causal language. This is
  the most constructive framing either review offers.

### Agreed, already known

2-3 (evaluator unvalidated, 2/12), 2-5 (observation confound = C2), 2-6 (time-limit = C1),
2-13 (estimators differ), 2-18 (three seeds thin), 2-22 (pin container digest + observation
fingerprint), 2-26/2-27/2-28 (implementation identity and labelling), 2-29 (reward normalisation),
2-31 (protocol not frozen), 2-32 (tree ambiguity = review-1 #3), 2-36 (families less audited than
the documents suggest).

### Not confirmed

- **2-33** — the claim that `eval_grid.py`'s module docstring still advertises a subset of families.
  Its opening lines do not restrict scope; this may already have been corrected.
- **2-15** — P19's worker-count change "unproven, not a bug". I agree it is unproven and did not
  attempt to prove it; the reviewer is appropriately cautious.

### Where I can upgrade the reviewer's own confidence

**2-24**: the reviewer says it "cannot label IDAAC definitively unseeded from this archive" and asks
for it as a verification item. **I verified it: there is no `np.random.seed` in `train.py`,
`ppo_daac_idaac/envs.py`, or `runnable/_shim/`.** Under C69 that means idaac's training door
placements are not controlled by its `--seed`. Confirmed, not merely suspected.

### Closing out the "agreed but unverified" list (2026-09-05)

- **#22 / 2-22 determinism asymmetry — CONFIRMED, and it undermines an instrument we rely on.**
  `torch.use_deterministic_algorithms(True)` appears **only** in `eval_across_scenes.py:110`; the
  seven-family `eval_grid.py` does not enforce it. So the *same checkpoint* can yield different
  success counts depending on which evaluator ran it — Door success is threshold-sensitive, which is
  why [C70](../docs/CONSTRUCTION.md#c70) added that call in the first place. **This is a confound
  inside `audit_shared_evaluator.py` itself**: that audit compares our number against the family's
  own, and part of any disagreement may be nondeterminism rather than a real difference. It is a
  plausible contributor to why 10 of 12 burdens remain undischarged, and it should be equalised
  before any further discharge attempt is trusted.
- **#27 / 2-6 time-limit split — CONFIRMED exactly.** The conventions table holds **3 `bootstrap`**
  and **9 `terminal`**. Matches C1 and the reviewers' claim without rounding.
- **#16 — partially confirmed.** `ibac_sni` runs `--beta` default **1.0** (upstream `torch_rl`
  value). The reviewer's point stands: β varies substantially across IBAC's original benchmarks and
  Door has no IBAC precedent, so it is a cross-domain inheritance to declare rather than a tie.

---

# STATUS AS OF 2026-09-05, LATE — much of the above is now FIXED

**This triage is a record of what was found, not of what is currently broken.** Several items marked
CONFIRMED have since been repaired, mostly by the concurrent session. Reading it as a live defect
list would now overstate the problem — which is exactly the staleness failure this project keeps
recording, so it is corrected here rather than left to be discovered.

**Do not read this file for current state. Run `python scripts/production_gates.py`,** which
recomputes from the tree.

Fixed since the triage was written (verified, not assumed):

| item | now |
|---|---|
| #7 result metadata (`eval_policy_mode` lie) | **FIXED** — all twelve pairs read correctly; `idaac`/`ppg`/`ibac_sni` say `sample` (`ctrl` said `sample` here too; corrected to `mode` 2026-09-07, see `notes/SAME-AXES-VERDICT.md`) |
| #8 checkpoint provenance | **FIXED** — SHA-256 stamped into records |
| #20 fail-open verification | **FIXED** — `strict=True` on production call sites |
| #21 / 2-1 pairing | **FIXED** — `placement_condition_seed(eval_seed, scene, episode_index)` per episode |
| 2-8 idaac `level_seed` | **FIXED** — episode-scoped (`_level_seed_base + _episode_index * _level_stride`) |
| 2-7 ppg auxiliary KL | **FIXED** — `kl.sum(-1).mean() if kl.ndim > 1 else kl.mean()` (`ppg.py:203`) |
| 2-12 idaac evaluator device | **FIXED** |
| 2-11 ctrl config binding | **FIXED** |
| #37 selected-scene pooling | **FIXED** — pools the full grid or none |
| #40 environment manifest | **FIXED** — `container_image`, `requirements_native_sha256` in source-lock |
| 2-4 train/eval RNG isolation | **FIXED** |
| #23 CPU evaluator default | **FIXED** |
| review-2 §1 placement witness | **FIXED** — records carry an episode id and placement witness |

Still open at the time of writing: the uncommitted tree (53 paths), and everything in
`notes/DECISION-SHEET.md` that needs the owner.

**One correction to my own method, recorded because it is the same class of error I was auditing
for.** In QC6 I told the concurrent session that `runnable/idaac` and `runnable/ppg` were "clean" on
the evidence that `git status` showed nothing under them. `.gitignore:35` is `runnable/*/` — the
parent repo does not track the clones at all, and each has its own `.git`. Empty output meant *not
tracked*, not *unmodified*. I read the absence of a signal as evidence of a state.
`python scripts/deviations.py` is the instrument that actually answers that question.
