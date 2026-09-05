# What every production episode row must carry

Written 2026-09-05 at the owner's direction: *"what should come from the runs is not only verdicts on
pre-set hypotheses, but the actual data — so that a hypothesis I had in mind but never committed to
the repo is still applicable without a full rerun. It is very unwise to leave the big production job
without explicit reporting."*

That is the correct principle and it inverts the usual instinct to record summaries.

## The asymmetry that decides everything here

**A row not recorded is unrecoverable without repeating the run.** One episode row is on the order of
a kilobyte. One production cell is hours of GPU and, at 6e5 × 3 × 12, the fleet is hundreds of
job-hours. The exchange rate between storage and recompute is so lopsided that **anything plausibly
interesting should be written**, and the burden of proof sits on *excluding* a field, not on
including one.

The corollary matters for pre-registration: freezing the analysis rules does **not** require freezing
what is measured. Record broadly, analyse under fixed rules, and a later question is a query rather
than a rerun.

## A correction to what I recommended earlier

I endorsed recording a **hash** of the realized initial placement (from the third external review).
That is right for its stated purpose — it makes pairing auditable and detects RNG-stream divergence.
**But a hash answers only "were these two episodes the same?".** It cannot answer *"does performance
depend on where the door was?"*, which is exactly the kind of unanticipated question the owner is
protecting against. A hash is a fingerprint; the parameters are data.

**Record the realized placement parameters themselves, and derive the hash from them.** Same
provenance guarantee, and the analysis stays possible.

## The shape this actually takes — reconciled with the emitter, 2026-09-05

External review 7 correctly observed that this document says "row per episode" while
`scripts/eval_grid.py` emits **one record per (regime, scene)** carrying index-aligned per-episode
ARRAYS: `returns`, `episode_success`, `placement_condition_seeds`, `placement_witnesses`,
`episode_diagnostics`, and now `eval_episode_ids`.

**The implementation is right and this document was describing an intention rather than a shape.**
Nothing episode-level is lost — every field below exists per episode, index-aligned — and the nested
form avoids repeating the identity and provenance block, which is identical for every episode in a
cell, twenty times over. What was genuinely missing was the episode IDENTIFIER, so a row could be
named rather than merely located; `eval_episode_ids` closes that.

So read every field list below as **"must be recoverable per episode from the record"**, not as
"must be a top-level key of its own JSON line". The gate checks the emitted key, not this prose:
`gate_placement_provenance` used to match the loop variable `episode_index` anywhere in the source
and therefore passed while no identifier reached a record at all.

## The row

**Identity and provenance** — so a row can be traced to the exact artefact that produced it:

    baseline, family, training_seed, regime, scene_id, episode_index, eval_episode_id
    checkpoint_frame, checkpoint_sha256, source_commit, container_digest, evaluator_revision
    effective_config (the resolved values actually used, not the template)

**Outcome** — the measured quantities, raw:

    episode_return              undiscounted, as the env emitted it
    success, time_to_success    the flag, and when it happened (None if never)
    episode_length, termination reason (time_limit | terminal)
    reward_sum, reward_mean, reward_min, reward_max

**Condition** — what the episode actually faced:

    initial_placement           the realized parameters, not only their hash
    placement_hash              derived from the above, for fast pairing checks
    mode/scene as APPLIED       read back from the env, not as requested

**Policy diagnostics** — because a finite policy can still be useless (σ ≈ 4.3 was finite):

    mean/min/max log_std        for stochastic policies
    action_clip_rate            per-coordinate AND vector-level (share of 7-D actions with any
                                coordinate clipped) -- the vector-level figure is the one the
                                environment experiences and it is ~93% at sigma=1
    ||a_raw - a_executed||      the actual transformation the env applied

**Conventions already carried** — keep: `eval_policy_mode`, `frame_stack`, `render_size`,
`time_limit_handling`.

## What is deliberately NOT recorded per step

Full per-step reward trajectories: 500 steps × 20 episodes × 10 scenes × 4 regimes × 12 baselines ×
3 seeds is on the order of 10^9 values. Per-episode reward summary statistics capture most of the
analysable signal at four numbers instead of five hundred. **If per-step traces are wanted, that is a
decision to take before the fleet, not after** — it is the one item on this page that genuinely costs
something.

## Why this is a gate and not a wish

Every other open item can be repaired after the fact by re-analysing. This one cannot: the moment
the fleet finishes, the set of answerable questions is fixed forever by what the rows contain. It is
therefore the cheapest possible insurance and the most expensive possible omission.

## Addendum, 2026-09-05 — record the reproducibility mode itself

`eval_grid.py` now enables `torch.use_deterministic_algorithms(True)`, with a `try/except` so that a
backend which cannot support it (JAX-only `ctrl`) still runs. That is right, but it means a row can
be produced under either regime and **the row does not say which**.

Add to every episode row:

    deterministic_algorithms: true | false

Door success is threshold-sensitive — this is why [C70](../docs/CONSTRUCTION.md#c70) enabled the
setting at all — so two rows produced under different regimes are not strictly comparable. Recording
the flag costs one boolean and turns "were these comparable?" from an assumption into a query. The
alternative is a future analyst inferring it from which family produced the row, which is exactly
the kind of reconstruction this spec exists to make unnecessary.
