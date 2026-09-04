# Independent audit, 2026-08-17 — past findings re-checked against the current tree

## What this is and how to read it

A subagent was asked to recover the categories of finding this project has recorded across its
own history (`docs/FAITHFULNESS.md`, `PREMISES.md`, `REGISTER.md`, `RIGOR.md`, `REVIEW.md`,
`STEP-ZERO.md`) and check, for each category, whether an instance of it is present in the
current clone-based tree.

**It was run blind.** It did not read `docs/AUDIT-2026-08-17.html`, the report it was in effect
checking. That was the point: a reviewer who has read the report tends to confirm it. Its own
opening line records this: *"I did not open `docs/AUDIT-2026-08-17.html` at any point.
Conclusions below are independent."*

**Its verbatim output is preserved below, unedited, under "Report as received".** Everything
above that heading is my own verification of its claims, done afterwards by reading the cited
files. The two are kept apart on purpose — an audit whose corrections are folded silently into
its own text stops being evidence of anything.

**A blind auditor is not an oracle.** Earlier in the same session a differently-scoped blind run
asserted that an `idaac` change lived in `PolicyResNetBase.evaluate_actions_with_adv`; no such
method exists (the code is `forward`, `runnable/idaac/ppo_daac_idaac/model.py:211`). It also
claimed an ALDA "autoencoder lr 3e-4" that appears nowhere in ALDA's trainers or specs. So every
claim below was re-derived before being acted on, and where it turned out wrong that is recorded
rather than quietly dropped.

## Verification of the live findings (D1–D7)

| # | Claim | My verdict | Evidence I read myself |
|---|---|---|---|
| **D1** | `Protocol.time_limit_handling = "truncate_with_bootstrap"` is hashed, but the runs truncate-as-terminal | **PARTLY CONFIRMED — the blanket is wrong** | See below |
| **D2** | `tests/test_success_metric.py` turns any probe fault into a skip that reads as a pass | **CONFIRMED** | `:82`, `:136` — both were `if line is None: pytest.skip(...)` |
| **D3** | `_shim/sitecustomize.py` swallows a partial shim silently | **CONFIRMED** | `:166-167` was `except Exception: pass` |
| **D4** | float64/float32 alpha dtype differs between `drq` and `dmc_gb` on CUDA | **CONFIRMED as a code fact** | `RL-ViGen-upstream/algos/drq.py:213` carries P5's `np.float32` cast; `runnable/dmc_gb/src/algorithms/sac.py:35` does not |
| **D5** | `ppg/vec_monitor2.py` folds post-reset info into the ending episode, contradicting its own comment | **CONFIRMED, benign in magnitude** | reset is never a success, so the OR never flips a real value |
| **D6** | `action_repeat` is declared but unread in two seams | **CONFIRMED, currently harmless** | both launchers pass 1, which is the value the dead knob would have set |
| **D7a** | patch registry is P1–P13 but prose says P11/P12 | **CONFIRMED — and fixed** | four documents disagreed with the code *and each other*; see below |
| **D7b** | `runnable/ctrl/vec_env.py:613` invents `_max_episode_steps = 10_000` vs a real horizon of 500 | **CONFIRMED, dead code** | never read on this path |
| **D7c** | `ibac_sni/scripts/evaluate.py` reports return only, no success rate | **CONFIRMED** | its own `train.py` does report SR, so ibac_sni's held-out number is not the quantity the other eleven report |

### D1 — the blanket claim is wrong, and the correction matters

The auditor wrote *"Every current clone zeroes the bootstrap at the 500-step horizon."* That is
**not true of `dmc_gb`**, which covers `rad` and `soda`. Reading the file:

```python
# runnable/dmc_gb/src/train.py:149
done_bool = 0 if episode_step + 1 == env._max_episode_steps else float(done)
```

That is the standard, *correct* time-limit handling: at the horizon the transition is stored as
non-terminal, so the critic bootstraps through it. `rad` and `soda` do the right thing.

The other families do zero it, and I verified each rather than taking the list on trust:

| clone | what I read | bootstraps at the horizon? |
|---|---|---|
| `dmc_gb` (rad, soda) | `train.py:149` `done_bool = 0 if episode_step + 1 == env._max_episode_steps` | **yes — correct** |
| RL-ViGen five | `wrappers/robo_wrapper.py:42` `discount = 0.0` on any `done` | no |
| `ctrl` | `buffer.py:16,18` `(1 - done[t])` in the GAE recursion | no |
| `idaac` | `storage.py:58-62` GAE masked by `self.masks[step+1]` | no |
| `ppg` | `ppo.py:38` `notlast = 1.0 - first[:, t+1]` | no |
| `alda` | `trainers/alda_trainer.py:655`, the identical idiom | **yes — correct** |

So the finding survives — a hashed protocol field asserts a property most of the runs do not
have — but it is **not uniform**, and the non-uniformity is itself the more interesting fact:
`rad`, `soda` and `alda` handle the horizon correctly while nine others do not — a **3 / 9**
split in what the value target *means*, sitting underneath every number.

This is the same shape as the frame-stack split, and it is not currently declared anywhere.

### D7a — the one the test suite could not see

`setup/apply_patches.py` declares **P1–P13** (21 hunks; `--check` reports "21 already present").
The prose said:

- `docs/INTEGRATION-DELTA.md:221` — "now P1–P11"
- `docs/STEP-ZERO.md:13` — "P1–P11"
- `README.md:19,31` — "P1-P12"
- `docs/RUNNABLE-ORIGINALS.md:42,43,44` — "P1–P12 only"
- `docs/RUNNABLE-ORIGINALS.md:254` — heading "P6–P12", while its own body documents **P6 through P13**

Three different answers across four files. The registry's *content* was never at risk —
`Protocol.env_patches` hashes it and `tests/test_contract.py:554` pins the hash — but nothing
checked the number a person reads, so the one uncovered restatement is the one that rotted.

Fixed, and the gap closed: `tests/test_docs_not_stale.py::test_quoted_patch_range_matches_the_registry`
now asserts on the highest patch id each document mentions, red-green verified per document.

## What the auditor got right that the report had missed

Both D2 and D3 are **re-instances of defects this project had already found, named, and removed
by name** — `docs/REGISTER.md:104` and `:106`. That is the finding above the findings: the
register records the lesson but does not prevent its recurrence, because nothing executes it.
Both are now fixed with red-green verification (commit `1b1db3be`).

## Acted on since

- **D1** — annotated, not re-valued, and the survey behind it completed. The blanket claim was
  wrong in a second way too: **`alda` also bootstraps correctly**
  (`trainers/alda_trainer.py:655`, the same idiom as `dmc_gb`). So the split is **3 / 9**, not
  2 / 10 and certainly not 0 / 12. See `rlgen/protocol.py` for the per-clone table. The value is
  hashed, so re-valuing it invalidates every recorded protocol hash — a decision with
  consequences for existing results, not a docs fix. **OPEN**, with the consistent option being
  to split it per-baseline the way `OBSERVATION_GEOMETRY` splits frame stacking.
- **D2, D3** — fixed, red-green verified (commit `1b1db3be`).
- **D7a** — fixed, plus the missing test (commit `a44f514c`).
- **D7c** — fixed (commit `9b71840b`). `ibac_sni/torch_rl/scripts/evaluate.py` discarded `info`
  and reported return only, while its own `train.py:203` reports `success_rate`. So the one
  baseline with a real held-out eval script produced a number that **was not the quantity the
  other eleven report**, and the comparison table was silently comparing two different things —
  which is exactly the defect Part 2 exists to remove. Now accumulates success with the same
  idiom as `torch_rl/algos/base.py:99-171` and prints `SR`.

## Still open, with the evidence now in hand

> **Status lives in [`CONSTRUCTION.md`](CONSTRUCTION.md), not here.** That register is the single
> authority for what is open, decided, or resolved, and it carries the options and effects this
> document does not. Where the two disagree, it wins.


### D4 — the dtype asymmetry, verified line by line

| | |
|---|---|
| `RL-ViGen-upstream/algos/drq.py:213` | `torch.tensor(np.float32(np.log(init_temperature))).to(device)` — **float32, unconditional** (this is P5) |
| `runnable/dmc_gb/src/algorithms/sac.py:35` | `torch.tensor(np.log(args.init_temperature)).cuda()` — **float64 on CUDA** |

`drq` is the only RL-ViGen algorithm with a temperature at all (the other four are the
DrQv2 family, deterministic policy, no `alpha`), so the comparison is exactly `drq` against
`rad`/`soda`. Two consequences, and the second is the one that matters:

1. On the authoritative CUDA runs, `drq`'s `log_alpha` is float32 and `rad`/`soda`'s is float64.
2. **`dmc_gb`'s local run is not the same numerical configuration as its CUDA run.** The MPS shim
   downcasts float64 (MPS has none), so locally both are float32. `drq` is float32 on both. So a
   green local `rad`/`soda` result does not evidence the CUDA arithmetic — which is precisely the
   thing the shim's own docstring warns about, now with a named instance.

`docs/REGISTER.md:130` accepted P5's unconditional cast *specifically to avoid machine-dependent
results*. The tree now has that cast in one clone and not the other, and the asymmetry is
declared nowhere. Fixing it is one line in `dmc_gb` — cheap, recorded by the ledger, and it
changes `rad`/`soda` CUDA arithmetic, so it is the owner's call, not mine.

### D5, D6, D7b — confirmed, currently harmless, left in place

- **D5** `ppg/vec_monitor2.py` folds post-reset info into the ending episode, contradicting its
  own comment three lines above. Benign only because a reset is never a success.
- **D6** `action_repeat` is declared but unread in two seams; both launchers happen to pass `1`,
  which is what the dead knob would have set. Inert, and would bite the moment anyone changes it.
- **D7b** `runnable/ctrl/vec_env.py:613` invents `_max_episode_steps = 10_000` against a real
  horizon of 500. Dead on this path; wrong if ever read.

---

# Report as received

*Verbatim, unedited. Its D1 blanket claim is corrected above; nothing here has been altered to
match.*

## PART 0 — LIVE NOW (category (d)), highest value first

**D1. A protocol field certifies a behaviour no run has — truncation.**
`rlgen/protocol.py:242` declares `time_limit_handling: str = "truncate_with_bootstrap"`, and it is inside the hash (`protocol.py:328`, `block("episode", [...])`). Every current clone zeroes the bootstrap at the 500-step horizon: `RL-ViGen-upstream/wrappers/robo_wrapper.py` `Gym2DMC.step` → `if done: discount = 0.0` (unpatched; P11 was inserted immediately above that line); `runnable/ctrl/buffer.py:16,18` `(1 - done[t])`; `runnable/idaac/ppo_daac_idaac/storage.py:59,61` `masks`; `runnable/ibac_sni/.../algos/base.py` `self.mask = 1 - done` feeding GAE. Door/Lift only ever end by time limit, so it fires every episode. This is the exact defect the project recorded (`docs/PREMISES.md:117-142`, `docs/REGISTER.md:82`) and fixed in `rlgen/replay.py` — re-introduced by the clone approach, which is defensible, but the protocol field was not updated and now asserts the opposite. Same shape as `DEFAULT_FRAME_STACK`, which *was* annotated (`protocol.py:46-48`); this one was not.

**D2. A blanket skip turns a red probe green — the same defect the project removed by name.**
`tests/test_success_metric.py:82` and `:136`: `if line is None: pytest.skip("robosuite env could not be built here")`. Any failure inside the probe (including one caused by the patches under test) is reported as a skip, and `s` reads as a pass. `docs/REGISTER.md:104` records this precise defect ("a blanket `except Exception: pytest.skip(...)` … turned a real import failure into a silent pass … **Removed the guard entirely: if the base cannot be loaded, the file has no meaning and must say so loudly**"). It is back, in the file that is the *only* thing establishing the success metric is live.

**D3. Same family, unguarded, in production code.**
`runnable/_shim/sitecustomize.py:166-167`: `except Exception: pass  # never break a run by shimming`. A partially-applied shim proceeds silently. `docs/REGISTER.md:106` names this instinct explicitly ("making the harness *cope* with an awkward dependency instead of making the awkwardness visible"). `tests/test_mps_shim.py` tests three positive behaviours and nothing about partial application.

**D4. The float64/float32 divergence is now asymmetric across baselines, on the CUDA path.**
RL-ViGen's `algos/drq.py:213` carries P5 (`np.float32(np.log(init_temperature))`), unconditional — so `drq` runs float32 alpha on CUDA. `runnable/dmc_gb/src/algorithms/sac.py:35` still reads `torch.tensor(np.log(args.init_temperature)).cuda()` → float64 on CUDA, float32 locally via the shim's downcast. So `rad`/`soda` and `drq` differ in temperature dtype on the authoritative runs. The historical finding (`docs/REGISTER.md:130`) accepted one unconditional cast *precisely to avoid machine-dependent results*; the current tree has the cast in one clone and not the other, undeclared anywhere in `RUNNABLE-ORIGINALS.md` / `PART2-METRIC-INVENTORY.md`.

**D5. Comment asserts a boundary guarantee the code does not implement.**
`runnable/ppg/phasic_policy_gradient/vec_monitor2.py` `process()`: the success flag is OR'd from `infos[i]` *before* the `if firsts[i]` branch, so the post-reset info is folded into the *ending* episode — the very thing the comment three lines above says it avoids ("that info is sampled when `first` is set — i.e. AFTER the reset"). Benign in magnitude (reset is never a success), wrong as written.

**D6. `action_repeat` is a declared-but-unread field in two seams.** `runnable/dmc_gb/src/env/wrappers.py` robosuite branch returns before the `dmc2gym.make(frame_skip=action_repeat)` call; `alda_trainer.initialize_env_dmc` likewise returns before `frame_skip=env_config['action_repeat']` (lines 159/182/200). `dmc_gb.sh` passes `--action_repeat 1` and `specs/train_alda_robosuite_door.yaml` sets `action_repeat: 1`, so the value happens to match — but the knob is inert and the omission is undeclared in either patch. Historical class: `docs/FAITHFULNESS.md:585-613`, `docs/PREMISES.md:211-229`.

**D7. Minor live instances.** `runnable/ctrl/vec_env.py:613` invents `_max_episode_steps = 10_000` against a real horizon of 500 (dead, but wrong if ever read). `docs/INTEGRATION-DELTA.md:222` says the registry is "now P1–P11"; `setup/apply_patches.py` has P1–P13 (the hash itself *is* pinned, by `tests/test_contract.py:554`). `runnable/ibac_sni/torch_rl/scripts/evaluate.py` reports return only — no success rate — while its own `train.py` does, so ibac_sni's held-out number is not the quantity the other eleven report.

---

## PART 1 + 2 — categories and their current status

(a) structurally impossible · (b) guarded · (c) possible, unguarded · (d) live

| # | Category | Historical instance(s) | Now |
|---|---|---|---|
|1|Value transcribed from a secondary source, not the authors' code|`FAITHFULNESS.md:47-51`; `REGISTER.md:29`|(a) — clone *is* the source|
|2|Paper vs authors' own code disagree|CURL 5 knobs `FAITHFULNESS.md:378-380`; SODA aux lr `:448`|(a) for algo code; (c) for launcher flags|
|3|Benchmark's paper vs its shipped code|`action_repeat` 1 vs 2, `FAITHFULNESS.md:67,81-85`|(b) — `protocol.py:82-89`, `rlvigen.sh:61-66`|
|4|Mislabelled citation artifact / acronym collision|`FAITHFULNESS.md:59-63,479-484`|(b) — `scripts/check_citations.py`|
|5|Base term asserted, working tree never opened|`REGISTER.md:92,94`|(b) — `PRISTINE:` commit + `deviations.py:127-138` re-derives|
|6|Third-party port used as reference where authors' release exists|`STEP-ZERO.md:80-87`|(b) — `SOURCE_OF` in `deviations.py:80-87`|
|7|Dead constructor default hit by bypassing the reference's launcher|SGQN `aux_lr=0.3`, `FAITHFULNESS.md:254-284`|(a) for 11; (c) for `ppg_eval.py`|
|8|Config key that cannot reach the knob|`FAITHFULNESS.md:276-281`|(a) — no registry layer|
|9|Hyperparameter inherited from a shared trainer key|drq `nstep=3`, `FAITHFULNESS.md:86-88,410-419`; `PREMISES.md:211-229`|(a) — no shared trainer|
|10|**Declared-but-unread config field**|`normalize_reward` `FAITHFULNESS.md:585-613`|**(d) — D6**|
|11|Guard on an attribute that never exists|`soda.train()` `hasattr` `FAITHFULNESS.md:464-475`|(c) — inherited as-is in `dmc_gb`|
|12|Count passed where a size is expected|`REGISTER.md:57`|(a) — each clone's own call sites|
|13|Schedule from the wrong tier / budget|`stddev_schedule` `FAITHFULNESS.md:94-103`|(c) — launchers set no schedule|
|14|**Unit-axis confusion (frames/steps/repeat)**|`PREMISES.md:158-164`; `RIGOR.md:320`|(b) `protocol.py:210`; **(d) latent, D6**|
|15|Wrong augmentation / defining operator substituted|SVEA overlay-for-convolution `FAITHFULNESS.md:220-225`|(c) — inherited from RL-ViGen, undeclared in clone docs|
|16|Class under another class's lineage|`CTRLAgent(CURLAgent)` `FAITHFULNESS.md:789-792`; `REVIEW.md:147-163`|(a)|
|17|The named mechanism removed/collapsed|PPG single value head `FAITHFULNESS.md:667-684`|(a) for clones; (c) for RL-ViGen's CURL|
|18|Optimizer scoping / parameter-ownership error|SGQN `FAITHFULNESS.md:286-317`; CTRL `:819-823`|(a)|
|19|Invented coefficient|`ctrl_coef`, `REGISTER.md:16`|(a)|
|20|Minibatch shuffle-protocol divergence|`FAITHFULNESS.md:686-701`|(a)|
|21|**Episode-boundary / truncation-as-termination**|`PREMISES.md:117-142`; `REGISTER.md:82`|**(d) — D1**|
|22|Windowing splices across episodes|`REGISTER.md:20`|(a) — reference behaviour is the null|
|23|Train/eval leak (noise/aug reaching eval)|IBAC-SNI value head `FAITHFULNESS.md:744-764`|(c) — no `assert_respects_deterministic` equivalent|
|24|Requested eval regime silently not applied|`PREMISES.md:46-52`; `PART2-METRIC-INVENTORY.md:214-230`|(b) — P1/P3/P12 + `RLVIGEN_EVAL_MODE`|
|25|Metric column that is a placeholder reading as a measurement|`SR: 0.0000`, `test_success_metric.py:1-11`|(b), but see **D2**|
|26|**Comparability split across arms** (obs geometry)|`PART2-METRIC-INVENTORY.md:242-272`|(b/open) `test_observation_geometry.py`; `Protocol.frame_stack=3` still false for 4 of 12|
|27|Asymmetric eval protocol between arms|`PREMISES.md:100-104`; `REVIEW.md:136-140`|**(d)-lite — D7** (ibac_sni SR gap; ppg train-only SR)|
|28|**dtype divergence visible on one accelerator only**|`REGISTER.md:130`; `PREMISES.md:60-62`|**(d) — D4**|
|29|Device workaround that changes CUDA arithmetic|same|(b) declared for P5; (c) for the shim's `DoubleTensor→float32`|
|30|**Blanket `except`/`skip` converting red to green**|`REGISTER.md:104`|**(d) — D2, D3**|
|31|Test mutating global interpreter state|`REGISTER.md:106`|(b) — subprocess isolation, `test_mps_shim.py:13-17`|
|32|Verification method structurally blind (T1 vs init)|`REGISTER.md:104`; `STEP-ZERO.md:120-128`|(a) — no re-implementation to transplant into|
|33|Fixture shape production never emits|`RIGOR.md:193-196`|(b) — probes build the real env|
|34|Checker that passes on empty input|`RIGOR.md:188-191`; `REVIEW.md:124-126`|(b) `collect_metrics.py --self-test`; (c) `deviations.py` on absent clones|
|35|Mutation applied to the test, not the code|`RIGOR.md:262-282`|(c) — `mutants/` not re-pointed at `runnable/`|
|36|Untrained weights presented as a result|`RIGOR.md:201-207`; `REVIEW.md:112-118`|(b) — `smoke_all.sh:59-76` judges on evidence of training, not exit code|
|37|Verification result scoped to a tree an edit has voided|`REGISTER.md:98`|(c) — `.greenmark`/`scripts/greenmark.py` partially|
|38|Docstring/comment asserting a property the code lacks|`REGISTER.md:108,116`; `REVIEW.md:354-356`|**(d) — D5**|
|39|Number quoted in prose drifting from its tool|`REGISTER.md:44`|(b) — `test_docs_not_stale.py`; **(d)-lite D7** (patch count uncovered)|
|40|Claim about own edits asserted, never measured|`STEP-ZERO.md:880-888`; `REGISTER.md:114,126`|(b) — `git diff` against `PRISTINE:` is the statement|
|41|Two instruments reporting different quantities under one word|`REGISTER.md:128`|(b) — `+` vs `code+`, `deviations.py:168`|
|42|Decision held only in working state, lost|`REGISTER.md:122`|(c) — `INTEGRATION-DELTA.md` appends, but nothing enforces it|
|43|Illegitimate shared abstraction among baselines|`STEP-ZERO.md:328-333`; `REGISTER.md:57,124`|(a) — the point of the clone approach|
|44|Shared code, different effective contract per caller|`STEP-ZERO.md:471-480`|(a)|
|45|Re-derivation where a copy was on disk|`STEP-ZERO.md:190-195`; `REGISTER.md:120`|(a), except the four authored continuous heads (`INTEGRATION-DELTA.md:236-247`), which have no reference — (c) by construction|
|46|Uniform-vs-selective application of an authored choice|`STEP-ZERO.md:208-211`; `M4`|(b) — all four heads use state-independent log-std init 0.0, entropy 9.933 checked|
|47|Overly-loose matcher in a checker|—|(c) — `deviations.py:71-77` `seg.endswith(key)` would swallow `latent_models/`, `metadata/`; mitigated only by printing|
|48|Negative control / floor assumed not measured|`RIGOR.md:106-111`|(c) — zero training runs exist yet; nothing measures a random-policy floor for Door SR|
|49|Ratio over a near-zero denominator|`RIGOR.md:113-117`; `PREMISES.md:110-116`|(b) — `collect_metrics.py` reports absolute difference + Wilson CI|
|50|Secret committed / echoed|`REGISTER.md:68` (upstream W&B key)|(c) — `runnable/ctrl/train_ppo.py` still carries the authors' plaintext key; inert (`--wandb_mode=disabled`)|

**Overall:** the clone approach genuinely eliminates most of the port-era classes (rows 1, 7–9, 12, 16–20, 22, 32, 43–45) — those are structurally impossible, not merely untested. What it does **not** eliminate is the *harness* half: metric plumbing, protocol declarations, device shims, and test guards. Every live finding above (D1–D7) sits in exactly that half, and D1 and D2 are re-instances of failures this project had already found, named, and fixed once.
