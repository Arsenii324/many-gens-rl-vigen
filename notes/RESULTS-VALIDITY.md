# Which existing measurements still stand

**A question five external reviews did not ask, and neither did I until now:** the evaluator has been
changed in four measurement-affecting ways since every retained number was produced. So which of the
numbers this project keeps citing are still comparable with anything we measure next?

    results/records/*.jsonl     written  04 Sep 16:55
    scripts/eval_grid.py        modified 05 Sep 01:25

**Every retained record predates the evaluator's current form.**

---

## The four changes, and what each does to a number

| change | effect on a measurement |
|---|---|
| **Per-episode condition seeding** (`placement_condition_seed`) | Episodes now face a *different sequence of door placements* than before. Old and new numbers are not the same episodes |
| **`use_deterministic_algorithms(True)` in `eval_grid`** | Old numbers used backend-selected kernels. Door success is threshold-sensitive — this is why [C70](../docs/CONSTRUCTION.md#c70) exists |
| **Strict regime verification** | Old cells could emit a row with the regime *unverified*. Job `bt1sgcg49j6d6jk84vuj` abstained **16 times** |
| **`run_scene_idaac` device** | idaac evaluation was hardcoded to CPU. `ibac_sni` still is (`agent.py:15` sets `self.device` and never uses it) |

## The load-bearing numbers, and their status

| number | used for | status |
|---|---|---|
| `idaac` **9.023** sd 6.488 N=20 vs native 5.347 N=10 → CONSISTENT | **one of only 2 of 12 evaluator burdens discharged** | **Suspect.** Computed pre-fix *and* on CPU. It is load-bearing for R6 and for every "the shared evaluator is validated" claim |
| `drqv2` **train 480.6 / eval-easy 1.44** at 100k | the C95 renderer probe, the anchor comparison, "first competent policy" | **Suspect as a comparison baseline.** Still fine as evidence that a policy *learned*; not fine as a value to compare a post-fix number against |
| `ctrl` **36.699** | first ctrl offline evaluation | Pre-fix |
| `ibac_sni` floor numbers, `ppg`/`alda` records | plumbing validation | Pre-fix, but they were only ever plumbing evidence |

## The consequence I would not have noticed without asking

**The migration plan says: verify the V100's renderer by reproducing `drqv2` 100k ≈ 480.6.** That
comparison would put a *post-fix, post-determinism, post-seeding* number against a *pre-fix*
baseline — so a mismatch would not isolate the renderer, which is the entire purpose of the probe.

**Fix: re-measure the probe baseline on the current evaluator before migrating**, or pick a baseline
produced after 05 Sep 01:25. It is one cheap cell and it makes the renderer check mean what it says.

## What this does and does not invalidate

**Does not invalidate:** that the twelve run end-to-end; that checkpoints stamp and retain; that
`run_scene_*` executes for all seven families; that `ibac_sni`'s σ ran away at 0.01 and stayed flat
at 0.0 — that finding is a *within-run trajectory comparison*, and both runs share an evaluator.

**Does invalidate, or at least suspend:** any *cross-run numeric comparison* that straddles
05 Sep 01:25, and specifically the **idaac evaluator discharge**, which should be recomputed before
"2 of 12 discharged" is quoted again.

**[Corrected 2026-09-05: the honest count is ZERO, not one.** This page suspended idaac and left drqv2 standing, but three of the four reasons for suspending idaac -- placement seeding, deterministic kernels, strict regime verification -- are family-agnostic, and this page's own finding is that EVERY retained record predates them. Only the CUDA device fix was idaac-specific. drqv2 was exempted by inattention.]

## Rule going forward

Every record already carries `checkpoint_sha256`. It should also carry an **evaluator revision** —
`record-completeness-spec.md` lists it, and this page is the argument for why. Without it, "is this
number comparable to that one" is answered by file timestamps, which is how I answered it here and
is not good enough for a result anyone will cite.

---

## Update 2026-09-05 (later) — the evaluator moved again, and by more than before

Six measurement-path changes landed today, after `payload-v100.tgz` was built and after job
`bt14het9mvpvvu8vatgo` was submitted:

| change | affects |
|---|---|
| `ctrl` evaluated with `normalize_rewards=False` | **ctrl's returns change units.** Every previous ctrl evaluation number is void, not merely incomparable |
| `run_scene_ppg` collects witnesses after the rollout and diagnostics before teardown | **ppg cells could not have completed at all**; there is no prior ppg grid result to invalidate |
| `eval_grid`'s duplicate diagnostics helper deleted in favour of `eval_provenance`'s | adds required-field validation to the production path; a malformed row now raises where it was recorded |
| `eval_episode_ids` added to every offline record | additive |
| determinism stamp made backend-specific | additive; corrects a Torch flag previously stamped on JAX measurements |
| `datasphere/native/families.json` added to `REVISION_MEMBERS` | changes `EVALUATOR_REVISION` for everything |

### What this means for the job now in flight

`bt14het9mvpvvu8vatgo` (idaac revalidation) runs the evaluator as it stood **before** those six.
None of them touches idaac's measurement path — the ctrl and ppg fixes are family-specific, and the
other four are metadata or hashing. But the entire point of a revision stamp is to stop us from
resting on exactly that kind of argument.

**So the honest reading of that job is narrower than the one it was submitted for.** Treat it as a
*functional* validation — does the shared evaluator run idaac end-to-end on CUDA, under strict regime
verification, and return complete records — and **not** as the final discharge number. The discharge
comparison has to be made under the revision the fleet will actually run, and that revision is not
frozen yet, because the owner decisions that would freeze it are still open.

Re-running it now would buy a number that the next evaluator change invalidates again. The right
sequence is the one reviews 7 and 8 both give: **freeze the configuration first, then revalidate
every evaluator family once, under one revision.**

### The floor

Re-measured today under the current scheme and, more usefully, **paired**: `scripts/probe_floor.py`
now seeds each episode with the same `placement_condition_seed(seed, scene, i)` the fleet uses, so
floor episode *i* runs the identical physical placement as baseline episode *i*. The marginal
placement distribution is unchanged by that switch, so this is a confirmation rather than a
correction — see the result recorded beside C55.
