# Reviews 6, 7 and 8 — triage against the tree

Written 2026-09-05. All three read in full. Review 6 is by a weaker model and says so; it is
nonetheless the one that found the fleet-wide payload outage first. Review 7 is the most complete
audit the project has received. Review 8 found the largest single fidelity defect in the tree.

**Everything below was re-derived from the code before being recorded here.** Where a review's
mechanism did not reproduce, that is stated as plainly as the confirmations.

---

## Confirmed, fixed in this session

### 1. The remote evaluator was broken fleet-wide (reviews 6 §1, 7 §1) — FIXED

`scripts/eval_provenance.evaluator_revision` hashes `rlgen/protocol.py` and raises when a member is
missing; `datasphere/native/contract.py`'s `BASE_ALLOWED` never carried it. Verified directly:
`payload-v95.tgz` (the archive my own running job was using) contained **zero** copies, and the job
`bt11qe3gunam3cnjml0u` duly ERRORed. Codex's `payload-v99.tgz` had the same hole, so the next
submission from either agent would have failed identically.

Review 7 established the scope I had not: **all seven families**, not just idaac.

Fixed by shipping the file (it is a hash INPUT, read with `read_bytes()`, never imported — so one
file suffices and no `rlgen/__init__.py` is needed) and, per both reviews' advice, by closing the
class rather than the instance: `tests/test_payload_contract_covers_provenance.py` asserts every
`REVISION_MEMBERS` entry is a declared payload member. The member tuple was hoisted to module scope
to make that checkable. **Verified the test fails on the real defect** by restoring it.

### 2. PPG's evaluator would have terminated every cell (review 7 §2) — FIXED

Two ordering errors in `run_scene_ppg`, both confirmed:

- `LAST_PLACEMENT_WITNESSES.extend(...)` ran **above** the rollout loop. `extend` copies what the
  list holds at that moment — the construction reset alone — and keeps no reference to the appends
  `roller.multi_step` then makes. `_run_grid`'s `len(witnesses) != len(returns)` check would fire
  with 1 witness against 20 returns.
- `completed_episode_diagnostics(venv, ...)` ran **below** the `finally` that closes the venv, so it
  interrogated a torn-down wrapper stack.

The other six families already collected before closing; ppg was the only inverted one, so the fix
aligns it rather than diverging. Pinned by `tests/test_eval_grid_collects_before_close.py`, which
walks every `run_scene*` function and compares collection line numbers against teardown line
numbers. **Verified failing on the pre-fix file.**

### 3. CTRL's evaluated return was not in Door units (review 8 §1) — FIXED

The largest measurement defect found. `RLViGenVecEnvCustom` — added by
`runnable/_patches/ctrl.patch:686`, **not** the `ProcgenVecEnvCustom` at `vec_env.py:17` — defaults
`normalize_rewards=True` and puts `VecNormalize(ret=True)` **outside** `VecMonitor`. The evaluator
sums the outermost `step()` reward, so ctrl's return was divided by a running return std and clipped
at ±10: the only one of twelve not in Door reward units.

This does **not** contradict `REGISTER.md:198`'s "all twelve report raw returns" — that finding is
about the monitor-recorded **training** return, a different quantity. That entry in fact anticipated
this repair: *"normalize_rewards is a live parameter … so the offline harness can construct a
raw-reward env deliberately rather than by luck."*

Fixed by passing `normalize_rewards=False`, which is CTRL's **own** evaluation convention
(`evaluate_ppo.py:38` uses False; `train_ppo.py:91,99,106` use True; byte-identical upstream). So the
fix increases fidelity rather than trading it. `tests/test_ctrl_eval_reward_units.py` drives CTRL's
real `VecNormalize` on a constant-reward stub to prove the flag is load-bearing, then asserts the
call site — a behavioural anchor under a static assertion, because a source-string test alone is the
thing these reviews keep faulting.

### 4. IBAC-SNI ran with a VIB coefficient 10,000x its own recorded value (review 8 §7) — FIXED

**The largest fidelity defect found in the whole review series.** `torch_rl/scripts/train.py:99`
defaults `--beta` to 1.0 and `algos/ppo.py:118` adds `self.beta * kl` directly to the objective, so
beta scales the bottleneck KL that *is* the IBAC mechanism. `runnable/_launch/ibac_sni.sh:113-114`
passed `--use_bottleneck --sni_type vib --model_type impala --entropy-coef 0.0` and **no `--beta`**.

Meanwhile `FAITHFULNESS.md:808` already recorded *"`vib_beta: 1e-4` matches CoinRun `[P]`"* and even
wrote down that beta is per-benchmark: 1e-3 toy, 1e-6 Multiroom, 1e-4 CoinRun. The authors' own
command is `README.md:109`: `--beta 0.0001 --nr-samples 12 --sni`.

So the value was researched, sourced, written down — and never wired to the process. Executed beta
was **10^4x the CoinRun value and 10^6x the Multiroom value.**

Fixed to `--beta 1e-4`, matching the CoinRun branch this configuration already follows (the trunk is
`--model_type impala`, ported from IBAC-SNI's own CoinRun branch per C3). Pinned by
`tests/test_ibac_beta_is_wired.py`, which also guards that the upstream default is still 1.0 so the
test cannot quietly stop guarding anything.

**This very likely bears on the open ibac_sni competence question.** A bottleneck penalty 10^4 too
strong is a mechanism for a policy that neither diverges nor learns — precisely the symptom the
`entropy_coef=0` pilots recorded (no runaway, zero success events). **The earlier pilots are not
evidence about the corrected configuration and must not be read as such.**

---

## Confirmed, and deliberately NOT "fixed"

### CTRL's online evaluation advances the training JAX key (reviews 6 §2, 7 §3, 8 §3)

The mechanism is real and I confirmed it: `select_action` rebinds `key` twice inside the eval block,
the `finally` restores only NumPy, and `update_ppo`/`update_cluster` then consume the advanced key.

**But all three reviews stop one step short of the fidelity question.** `ext/ctrl_public/train_ppo.py:193,202`
has the identical rebinding, and steps the same test envs in the same place in the loop. The key
advance is **upstream CTRL's own design**, and `families.json` records that ctrl's training-time eval
is *"CONTINUOUS, not periodic … There is no cadence and no episode count to set."* So the cadence
cannot drift, and splitting the key would be **our deviation introduced into a clone whose null is
running its own algorithm** — not a repair.

What was genuinely wrong was **my gate's claim**. It reported `PASS train/eval RNG isolation` on the
strength of a `np.random.get_state()` string search, which all three reviews correctly call a
textbook false pass. The gate now states what it actually verifies: the **placement** stream is
isolated, the JAX key advance is upstream's and is deliberately unpatched.

Worth noting against ourselves: the NumPy save/restore is **ours**, so we have already deviated from
upstream in the other direction. That is defensible but should be recorded as a deviation, not as an
isolation guarantee.

---

## Not reproduced

### Review 8 §2 — "CTRL's paired episode conditions are not actually paired"

The described mechanism needs a **running condition counter** that the explicit `env.reset()`
double-advances. CTRL has no such counter: the patched `RLViGenVecEnvCustom` swallows `condition_seed`
in `**_ignored`, and the evaluator instead calls `seed_episode_placement(seed, scene_id, episode_index)`
before every measured reset, which re-seeds `random` and `np.random` from a `SeedSequence` of
`(seed, scene, episode_index)`. A re-seed **overwrites** the stream, so a discarded auto-reset cannot
shift the measured placement. Episode *i*'s condition is a pure function of *i*.

`ppg` is the family that *does* keep an internal counter (`envs.py`, `self._episode_index`), and it
increments exactly once per reset while each reset begins exactly one episode — so it lands on index
*i* for episode *i* as well. The two schemes agree.

**The review's underlying recommendation still stands and is not answered by this**: the pairing test
should compare **realized placement hashes across families**, not seeding expressions. Nothing in the
tree does that yet.

---

## Confirmed and still open — carried to the decision surfaces

| finding | where it goes |
|---|---|
| Duplicate `completed_episode_diagnostics` in `eval_grid` (weak) and `eval_provenance` (validates required fields); production uses the weak one (review 7 §5) | real drift seam; `eval_grid` should import the tested helper |
| `evaluator_revision` omits `families.json`, which per-family eval configuration lives in — under-sensitive, the dangerous direction (review 7 §6) | see below |
| Offline eval rows carry no `_run_provenance`, unlike normalized training rows (review 7 §7) | records-completeness |
| Record spec promises one **episode row**; `eval_grid` emits a **scene aggregate** with nested arrays, and no `eval_episode_id` (review 7 §4) | spec-vs-code divergence |
| `diagnostics_available: False` is tolerated in production (review 7 §4) | Codex softened the collector to tolerate *unreachable* while still failing on *partial*, which resolves my A21b concern; whether the final fleet may record a cell with no diagnostics at all is an owner decision |
| IBAC's competence pilot ran at `procs=1`; production targets `procs=16`, which changes rollout size, minibatch count and update-per-frame ratio (review 7) | **A14 must be applied before A1's pilot** — and now also before the corrected beta is evaluated |
| PPG `n_pi=32` unrescaled: ~9 auxiliary phases at 8 envs, ~4 at 16, upstream would reach 0 at 600k (reviews 6 §3, 7, 8) | declare the choice; none of the three options is a canonical reproduction |
| `nr_samples=12` (CoinRun) has no equivalent in `torch_rl`; latent is 64-d not 256-d (review 8) | ibac_sni is an **authored hybrid** of the authors' two implementations — CLAIMS-LEDGER wording |
| Renderer gate recommends reproducing DrQ-v2 **480.6** while `RESULTS-VALIDITY.md` invalidates that number for the purpose (review 7 §10) | internal contradiction between two of our own surfaces |
| CTRL records Torch determinism for a JAX measurement (review 7) | `determinism_backend` should be backend-specific |
| "Terminal-at-horizon methods are systematically disadvantaged" is a directional judgement without a controlled ablation (review 7) | soften to "their learning targets differ near the horizon" |
| Random floor 1.82 should be re-measured under the final evaluator (reviews 7, 8) | cheap; pairs with the drqv2 renderer re-measurement |

---

## The Gemini pair — `THE-STRONGEST-REVIEW-REPORT.md` and `_archived_plan_strongest_review.md`

Assessed on request. **It reads real code — but its self-description as "the strongest adversarial
review" is not borne out against reviews 7 and 8, and one of its headline recommendations is a
choice this project already retracted.**

**Where it is genuinely right and genuinely reading the source:** its `_LevelSeed` derivation quotes
`self._level_seed_base + self._episode_index * self._level_stride` and that formula is really in
`runnable/idaac/ppo_daac_idaac/envs.py:108-109` (it cites :125, but the code is there). Its DEF-01
payload finding is real and is fixed above. Its entropy-runaway derivation is correct and matches
C61. Its A4 — **subtract the random floor before forming a retention ratio** — is a genuinely useful
concrete proposal, and it is the missing operational half of CORRECTIONS #5, which established that
retention is not invariant to reward offsets but stopped at demoting the metric.

**Where the confidence is not backed:**

- **A9 recommends anchoring on RL-ViGen's published DrQ-v2 Door score of ~3.6.** That is the exact
  anchor `CORRECTIONS.md` #3 **retracted**, and for a reason the report does not engage: against a
  1.82 floor, a broken evaluator, a floored policy and a correct reproduction all produce ~2, so 3.6
  discriminates nothing. The valid anchors are `sgqn` (391.4) and `svea` (268.8). Following A9 would
  re-adopt a retracted decision.
- **It attributes IBAC-SNI to ICLR 2020.** The paper is NeurIPS 2019 (arXiv:1910.12911), as
  `FAITHFULNESS.md:806` records.
- **Its DEF-02 remedy repeats the fidelity error**: it treats CTRL's JAX key advance as a defect to
  patch without checking `ext/ctrl_public`, where the same rebinding is present. See above.
- **Its A1 is now superseded** — it recommends the `entropy_coef=0.0` pilot without knowing about
  either the beta defect or the `procs=1 → 16` change, both of which invalidate that pilot as
  evidence about the production configuration.

**What it does not contain:** none of the three largest real defects found in this session — the
IBAC beta being 10^4 too large, CTRL's evaluated return being in normalized units, or PPG's witness
copy. Review 7 found the last of those; review 8 found the first two.

**Net:** worth keeping for A4 and as independent corroboration of DEF-01. Not a substitute for
review 7, and its A9 must not be actioned. The loud framing tracks confidence, not coverage.

---

## Verified while checking the above: the paired inference holds across all seven evaluators

Not asked by any review, but it is the assumption the project's primary contrast rests on, and two
families reach it by different routes.

- **Five families** (`dmc_gb`, `idaac`, `ibac_sni`, `alda`, `ctrl`) call the shared
  `seed_episode_placement(seed, scene_id, episode_index)` before every measured reset.
- **`ppg` does not.** It pairs through its wrapper's own counter in
  `runnable/ppg/phasic_policy_gradient/envs.py`, which computes
  `SeedSequence([condition_seed, scene_id, self._episode_index]).generate_state(1, dtype=np.uint32)[0]`.
  That is the **identical formula** to `placement_condition_seed`, and `condition_seed=seed` is what
  the evaluator passes, so episode *i* lands on the same physical placement either way.
- **One asymmetry, checked and harmless:** the shared helper also seeds Python's `random`; ppg's
  wrapper seeds only NumPy. `RL-ViGen-upstream/.../vgb_wrapper.py` imports `random` but its only
  use is `random.seed(seed)` at :449 — a seeding call, never a draw — and Door's placement comes
  from the global NumPy stream (C69). So nothing in the reset path consumes Python's `random`, and
  the two routes agree.
- **`dmc_gb`'s `seed + 42`** (`dmc_eval_seed`, matching dmc_gb's own `train.py`) applies to env
  *construction* only; the per-episode placement seed is derived from the unoffset `seed`. So the
  physical placements are paired and it is the **visual** condition that is not — exactly as
  `CLAIMS-LEDGER` already states, now confirmed rather than assumed.

---

## Measured, not argued: ppg's episode diagnostics ARE reachable and complete

Review 7 §4 warns that `diagnostics_available: false` is tolerated in production and that a wrapper
stack may therefore silently omit realized placement, reward statistics, clipping diagnostics and
termination reason. My own A21b argued the opposite risk — that a fail-closed collector would kill
the three families whose wrappers sit behind a vector boundary.

**Both were speculation. It is cheap to measure, so I measured it**, locally, on the real ppg venv:

    get_venv(num_envs=1, env_name="robosuite:Door", mode="train", seed=1, scene_id=0,
             condition_seed=1)  ->  ConcatEnv
    hoisted attrs: ['_vigen_regime', '_placement_witnesses']      # NOT episode_diagnostics
    ... step one full 500-step episode ...
    completed_episode_diagnostics(venv, 0.0, 1)
      diagnostics_available: True
      keys: action_clip_rate_coordinate, action_clip_rate_vector, action_raw_executed_l1,
            action_raw_max, action_raw_min, applied_mode, applied_scene_id, ...

**So the list is reached through the `envs` list into the inner wrappers, even though nobody hoisted
it.** ppg will record complete per-episode diagnostics; the omission review 7 feared does not occur
for this family, and the cells my A21b feared would die do not die.

Two things this also settles:

1. **The ppg ordering fix was load-bearing, not cosmetic.** The diagnostics call used to run after
   the `finally` that closes the venv; the traversal above only succeeds on a live wrapper stack.
2. **An empty list is not the same as an unreachable one, and the collector is right to
   distinguish them.** Before the episode completed, the traversal found a *present but empty*
   list and raised — which is the correct behaviour, and is why the earlier five red tests were a
   fixture artefact rather than the production hazard I took them for.

Still unmeasured: `idaac` and `ibac_sni`. They share the wrapper structure, so the same result is
likely, but likely is not measured — and the running revalidation job will show it directly for
idaac in its records' `diagnostics_available` field.

## Checked after fixing ctrl: no other family reports a transformed return

Having found one evaluator summing a normalized reward, the obvious question is whether any other
does. Audited all seven return-accumulation paths in `eval_grid.py`:

| family | how the return is formed | raw? |
|---|---|---|
| `idaac` | reads `info['episode']['r']` from **VecMonitor**, explicitly, with a comment saying why | yes |
| `ppg` | `roller.recent_eprets`, which PPG's `VecMonitor2` fills before `reward_normalizer` runs | yes |
| `ctrl` | summed `step()` — **the defect**, now `normalize_rewards=False` | yes, after the fix |
| `dmc_gb` (rad, soda) | sums `step()`; dmc_gb does not normalize | yes |
| `ibac_sni` | sums `step()`; no normalization in its stack | yes |
| `alda` | sums `step()`; no normalization in its stack | yes |
| RL-ViGen five | their own path; no normalization | yes |

So `ctrl` was the only one, and `REGISTER.md:198`'s conclusion — that the three normalizing
families (`ctrl`, `idaac`, `ppg`) all still *report* raw returns because the monitor sits inside the
normalizer — holds for every training loop. The common **evaluator** was the one place that reached
past the monitor, and only for ctrl.

---

## Found by running the job, not by reading: idaac could not be evaluated at all

`bt1p4ei1s64o50oka946` failed at `runnable/idaac/ppo_daac_idaac/envs.py:136`:

    RuntimeError: RL-ViGen adapter lost P3's applied regime read-back during construction

**The guard was checking for something nothing ever sets.** P3 attaches `_vigen_regime` inside
RL-ViGen's `robo_make`; this adapter calls `robosuitevgb.utils.make_env` directly (`envs.py:68`),
which P3 does **not** patch. And `venv.envs[0]` is a `_LevelSeed` wrapper that forwards no
attributes anyway. So the guard raised on **every** construction — idaac evaluation was totally
blocked, for the whole fleet, in every payload carrying that check.

Reproduced locally on a real env, which also showed what IS available:

    type(base): VGBWrapper
      base._mode        = 'train'
      base._scene_id    = 0
      base._vigen_regime = <absent>          # nowhere on the .env chain either

Fixed by deriving the regime from `_mode`/`_scene_id` on the base env and hoisting it in P3's
shape — **which is exactly what `ibac_sni` already did** (`torch_rl/utils/general.py:93-99`), so
this makes idaac consistent with its sibling rather than introducing a new pattern. `ppg` was
measured working earlier in the session. Verified both ways: the pre-fix file reproduces the remote
error locally, the fixed file returns
`{'mode': 'train', 'scene_id': 0, 'video_background': False}`.

**Why no test caught it.** The change that introduced the guard landed with a green suite of 89
tests, and none of them constructed an environment. `tests/test_family_regime_readback.py` now does
— an integration test, deliberately, because the defect is invisible to anything that does not
build the real wrapper stack. Verified non-vacuous: it fails on the pre-fix file and passes on the
fixed one.

**The lesson generalises past this bug.** A guard is code, and an unexercised guard is a claim about
code that nobody checked. This one asserted a postcondition that its own construction path could
never satisfy, and it read as extra safety.

## And a second family was equally blocked: ctrl

Having fixed idaac's regime read-back, the obvious question was whether any other family shared the
defect. Rather than reason about it, I constructed **every** family's evaluation env locally and ran
the real `verify_regime(..., strict=True)` against it:

| family | verdict |
|---|---|
| `idaac` | was **FAIL**, fixed |
| `ctrl` | was **FAIL** — `ctrl: regime 'train'/scene 0 is UNVERIFIED; refusing to emit a production evaluation record` |
| `ppg`, `dmc_gb`, `ibac_sni`, `alda` | pass |
| `rlvigen` | not applicable — the five natives use their own fail-closed read-back in `eval_across_scenes.py:189-195`, and that path is proven by completed production jobs |

**So two of the six families that use the shared guard could not evaluate at all**, and only one had
been noticed. `RLViGenVecEnvCustom` builds `_SyncVecEnv -> VecMonitor -> VecNormalize`, none of
which forwards attributes, so `_mode` on the base envs was unreachable from the handle the evaluator
holds. Fixed with the same hoist idaac and ibac_sni use, so all three now agree in shape.

**The general lesson, and it is the one that keeps repeating tonight:** a fail-closed guard is a
claim about code that nobody ran. Both of these read as extra safety while making their families
unrunnable, and both were introduced in a change that landed with a green suite — because no test
constructed an environment.

### A third defect, revealed only by fixing the first

With construction working, `bt16ikro8c3mu3id9p8n` reached the policy and died there:

    model.py:77 RuntimeError: Input type (torch.cuda.FloatTensor) and weight type
    (torch.FloatTensor) should be the same

The checkpoint loader moved `nn.Module` **attributes** of the agent, but idaac (like ppg) pickles an
`nn.Module` *directly*, whose children live in `_modules` — so the walk moved nothing and the weights
stayed on CPU. ppg had an explicit `if a.family == "ppg"` branch for exactly this shape; **idaac,
identical in shape, inherited the bug instead of the fix because the branch was keyed on a name.**
Now `place_agent_on_device` keys on `isinstance(agent, torch.nn.Module)`, extracted so it can be
unit-tested, with `tests/test_agent_device_placement.py`.

**Guards stack.** Each fix here revealed the next defect behind it, which is the strongest argument
against treating a green remote job as evidence that the ones before it were fine.

## The recovery path was broken and nobody could have noticed

`RECOVERY-HANDOFF.md:30` says the clones are "reproducible from `ext/` plus
`runnable/_patches/*.patch`". `setup/apply_patches.py` does **not** apply those files — it patches
the vendored RL-ViGen tree — so they are provenance snapshots that nothing re-derives. **Five of the
six had drifted**, including Codex's turn-64 ppg edit and tonight's fixes.

`scripts/refresh_clone_patches.py` now regenerates and `--check`s them, and it is a gate. Its own
construction is a cautionary tale worth keeping: the first version marked **all six** stale through a
doubled path prefix, and would have overwritten six provenance files had I not first compared its
output against a family I had never touched. `dmc_gb` reproducing byte-for-byte is what proved the
generator correct.

## Diagnostics reachability, now measured for two families rather than one

Review 7 §4 warned that `diagnostics_available: false` is tolerated in production, so a wrapper stack
could silently omit realized placement, reward statistics, clipping rates and termination reason —
the one class of loss that cannot be repaired after a fleet finishes.

Measured, not argued, for both families whose stepping interface is known:

| family | after one full 500-step episode |
|---|---|
| `ppg` | `diagnostics_available: True`, full field set |
| `ctrl` | `diagnostics_available: True`, full field set |
| `idaac` | `diagnostics_available: True`, full field set |

Both reach P20's list through the wrapper chain even though neither hoists it explicitly. This is
now `tests/test_family_env_smoke.py`, which runs in ~18 seconds with no checkpoint and no GPU, and
asserts the specific fields a record needs (`episode_length`, `termination_reason`, `reward_sum`,
`initial_placement`, `applied_mode`, `action_clip_rate_vector`).

**Note the test steps a FULL episode deliberately.** P20 appends at episode end, so a partial
episode finds a present-but-empty list — which the collector correctly treats as an error, not an
absence. That distinction is the reason the five red `test_eval_loop_measurement` failures earlier in
the session were a fixture artefact rather than the production hazard I first took them for.

`idaac` and `ibac_sni` are not yet covered here because their stepping interfaces differ; their
construction and strict regime verification are.
