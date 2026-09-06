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
    checkpoint_frame, checkpoint_sha256, source_commit, container_digest
    evaluator_revision, evaluator_config_revision
    evaluator_scope, evaluator_scope_revision, evaluator_measurement_revision
    effective_config (the resolved values actually used, not the template)

`evaluator_revision` is the static family runtime-closure identity and
`evaluator_config_revision` is the static family configuration/payload identity. The resolved
`evaluator_scope` is hashed as `evaluator_scope_revision`; analysis and pooling must use
`evaluator_measurement_revision` (the static evaluator identity combined with that scope
revision), not the static revision alone.

The validation ledger may bind these fields to `validation_kind: functional_endpoint`,
`evaluation_records_path`, and `evaluation_records_sha256`. That artifact binding makes the ledger
claim mechanically comparable with its applicable offline rows; it remains a human-reviewed
artifact and does not itself prove source or job correctness.

**Delivery status is part of record interpretation.** The native runner writes `run_manifest.json`
before invoking `normalize_curves.py`, because the normalizer attaches that manifest's provenance to
rows. If normalization fails in a production endpoint cell, the runner preserves the native
archive, sets the manifest's `failure_marker` to `NATIVE_RECORDS_NORMALIZATION_FAILED ...`, clears
its top-level `final_evaluation_marker`, and exits nonzero only after the archive has been written.
Such an archive is evidence of a postprocess failure, not a successful normalized record delivery.
Exploratory/non-production normalization failure is tolerated only with an explicit
`NATIVE_RECORDS_NORMALIZATION_TOLERATED` marker. An earlier cell failure retains ownership of the
manifest failure marker and is never replaced by the later normalizer failure.

The manifest now carries `finalization_schema: 1` and an `execution_kind` chosen before
normalization: `preflight`, `eval_only_validation`, `training_production`, or `exploratory`.
`record_delivery` starts as `pending` and is finalized only after normalization and after the
optional `RECORDS_OUT` bundle has been assembled. Its only legal final values are:

    not_applicable     preflight, which intentionally emits no records
    complete           nonempty, valid JSON-object rows were delivered
    failed             required delivery is absent/empty/malformed, or execution already failed
    empty_tolerated    exploratory execution produced no rows; never a final result

Production and eval-only validation therefore require a `RECORDS_OUT` destination and at least one
valid JSONL row. Eval-only validation satisfies this with its raw offline-evaluation rows; it does
not need a training `records.jsonl`. Exploratory probes retain their historical empty-output
behavior, but the explicit `empty_tolerated` status prevents a report from treating them as a
successful final delivery. The manifest's `record_artifacts` records the input files and delivered
output's row count and SHA-256 (when present). A malformed row is never silently carried through.

Finalization also verifies preservation, not merely nonemptiness: it reads the declared source
sequence in runner order — `records.jsonl`, root `offline_eval_*.jsonl`, then cell
`offline_eval_*.jsonl`, each lexicographically within its group — and compares it with the delivered
JSONL sequence. Each row is canonicalized as a sorted-key compact JSON object; only the
runner-added `_run_provenance` and `_delivery_provenance` fields are removed because the collector
intentionally adds them to offline and completed-delivery rows.
The canonical byte sequence is ordered and hashed, so omission, duplication, reordering, or a
changed measurement field fails even when the remaining rows are valid. Raw-byte SHA-256 is kept
separately for the actual input/output files.

For exploratory runs, only a genuinely empty source/output set receives `empty_tolerated`. A
nonempty but partial or otherwise mismatching bundle is `failed`: tolerating it would preserve the
old false-success surface while making the status look explicit. Collector truncation/write errors
are caught before `set -e` can terminate the runner; the manifest records the failure and native
evidence is archived before the job returns nonzero. Before truncating `RECORDS_OUT`, the collector
also rejects a destination whose resolved path or existing file identity aliases any declared native
source (`records.jsonl`, root offline-evaluation files, or cell offline-evaluation files); this
preserves the source evidence for the finalizer and archive when a destination is misconfigured.

The finalizer updates the manifest before `result.tgz` is written. A required delivery failure
clears the completion marker and adds `NATIVE_RECORD_DELIVERY_FAILED` unless an earlier cell
failure already owns `failure_marker`; the runner then returns nonzero only after the archive has
been verified. `summarize_result.py` refuses production/eval-only artifacts without supported,
`complete` finalization by default. `--diagnostic` is the explicit escape hatch for inspecting old,
incomplete, or failed artifacts and must not be used as a production result view.

After — and only after — that full source/output comparison succeeds, the finalizer atomically
rewrites `RECORDS_OUT`. Every JSON object receives this small top-level `_delivery_provenance`:

    finalization_schema, execution_kind, record_delivery: "complete"
    source_row_count, source_canonical_sha256

It contains neither the full manifest nor a self-referential output hash. A records-only consumer
can therefore establish that the bundle reached completed finalization and identify the exact
canonical source sequence, without downloading `result.tgz`. The comparison ignores exactly the
two runner-added metadata fields `_run_provenance` and `_delivery_provenance`; ordinary measurement
fields remain part of the comparison. The output's raw and canonical hashes are computed again
after this rewrite and stored in the archived manifest. If stamping or its post-write verification
fails, delivery is `failed` and the archive-first rule still applies.

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

`action_raw_executed_l1` is a sum over the observed action vectors in its scope (the scene-level
policy diagnostic or an individual episode's P20 row), not a mean or a per-action value. It is
therefore an aggregate L1 total; `actions_observed` supplies the corresponding count if a later
analysis needs to derive a mean.

The scene-level native record also carries `policy_action_diagnostics`. This is the evaluator-side
measurement of the action value after each family's adapter conversion and immediately before its
environment call. It uses the declared numeric action-space bounds and reports the same coordinate
and vector clip rates, L1 difference, and raw range. The value is observed without replacing the
action, so trainer/loss semantics and returns are unchanged. PPG is observable at its `venv.act`
boundary after its existing tensor-to-NumPy conversion; all seven current evaluator families have
an adapter boundary at which this can be observed. `available: false` is reserved for a future
adapter that exposes neither a numeric bound nor an action at that boundary.

This is not a measurement of controller-internal clipping: robosuite controllers can clip derived
torques after the action-space boundary. Records state this with `controller_clipping_observed:
false`; the existing P20 per-episode fields remain the independent VGB-wrapper measurement of the
declared action-space boundary.

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
