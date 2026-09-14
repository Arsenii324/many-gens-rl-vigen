# What we actually have, 2026-09-14 — a full artifact audit

Every number here was read off the host or out of `results/` during this audit, not recalled.
Where I got something wrong earlier in the session, the correction is stated rather than quietly
replaced.

## 0. The correction that reframes the rest

**Intermediate checkpoints were NOT dropped.** I reported they were, twice. I had surveyed
retention with `find -name "*.pt"`, and checkpoint extensions are per-family:

| family | `intermediate_checkpoints` glob |
|---|---|
| alda | `checkpoints/sac_*_step_*.pt` |
| ctrl | `models/robosuite:{task}/checkpoint_*.msgpack` |
| dmc_gb | `model/*.pt` |
| ibac_sni | `model_[0-9]*.pt` |
| idaac | `models/agent-robosuite:{task}-{baseline}-s{seed}_*.pt` |
| ppg | `model[0-9]*.jd` |
| rlvigen | `snapshot_*.pt` |

`ppg` writes `.jd` and `ctrl` writes `.msgpack`, so a `.pt` search undercounts exactly the families
whose runs matter most here. Re-surveyed with all three extensions, `card0-20260909-115331` holds
**14** checkpoints (13 `model*.jd` intermediates + `snapshot.pt`), not 1.

This matters beyond bookkeeping: the register row `curve-depth-vs-endpoint-depth` justifies
3-episode curve points by "because every checkpoint is retained, any intermediate point can be
re-evaluated at greater depth later", and its falsifier is "if checkpoints stop being retained,
curve depth stops being reversible". On my wrong reading that falsifier had fired. It has not.
The row stands.

## 1. Artifact types a cell leaves behind

Per run directory, under `native-out/`:

| artifact | what it is | first-hand? |
|---|---|---|
| `records_delivery.jsonl` | the measurement bundle: train curve + eval + every offline-eval row, each carrying `_run_provenance` | **yes, this is the product** |
| `records.jsonl` | curve rows only, no offline-eval | partial subset, never the bundle |
| `cells/<cell>/offline_eval_*.jsonl` | per-stamp grid output, merged into the bundle by `collect_record_delivery` | yes, input to the bundle |
| `cells/<cell>/snapshot.pt` | terminal policy, normalised name by `family.py:821` | yes |
| `cells/<cell>/checkpoints/*` | intermediate policies, per the glob above | yes |
| `train.csv`, `*.log` | trainer logs | yes, diagnostic |
| `effective_config.json`, `resolved_packages.json` | executed configuration and pip resolution | yes, provenance |

`native-work/` (1.9 GB in a typical run) is the vendored source tree and build state —
regenerable, not an artifact.

## 2. What "collected" means

No compute, no device, no re-evaluation. The numbers are produced on the GPU during the run.
Collection is: copy `records_delivery.jsonl` into `results/records/<job>__records.jsonl`, then
`populate_evaluator_ledger.py <family> <job>`, which **refuses** the record if its
`evaluator_revision` is not the live one and otherwise writes
`validated_evaluator_families.json`. That is why soda and ctrl could be collected days later
without any loss of validity.

## 3. The three phases, and which is an evaluation

- `train` — training-time logging, return per update. Not an evaluation.
- `eval` — online evaluation inside the training loop, `EVAL_EPISODES` deep. In every attestation
  wave `EVAL_EVERY_FRAMES=2147483647`, i.e. deliberately disabled, leaving one endpoint row.
- `offline-eval` — the grid: checkpoint x regime x scene_set x episode depth, run from a saved
  checkpoint outside training. **This is where the reported numbers come from.**

## 4. Stamp cadence actually used, against the paradigm

`production-schedule-v100.json` declares `save_every_frames=50000`, `curve_eval_episodes=3`,
`endpoint_eval_episodes=20`. The 600k ppg run actually graded 13 stamps:

```
0, 51,200, 100,352, 151,552, 200,704, 251,904, 301,056,
350,208, 401,408, 450,560, 501,760, 550,912, 600,064
```

Deltas are 49,152 and 51,200, not 50,000: stamps are quantised by the rollout size, so the
cadence is the nearest achievable multiple rather than the declared round number. Episode depths
observed: 3 (520 rows), 20 (40), 30 (52), 200 (4) — consistent with 3 on the curve and deeper at
the endpoint.

## 5. The fleet, as `export_fleet.py` reports it

**2969 rows, 28 on the CURRENT closure, 2941 superseded.** The 28 are 4 offline-eval rows from
each of the seven attestation families.

| baseline | rows | current | max frame | seeds |
|---|---|---|---|---|
| ibac_sni | 1397 | 4 | 100,096 | 1 |
| idaac | 657 | 4 | 598,016 | 1, 101 |
| drqv2 | 323 | 0 | 100,000 | 1, 2 |
| rad | 147 | 0 | 10,000 | 1 |
| soda | 112 | 4 | 10,000 | 1 |
| ppg | 99 | 4 | **10,240** | 1 |
| ctrl | 66 | 4 | 10,000 | 1 |
| alda | 58 | 4 | 10,000 | 1 |
| svea | 53 | 4 | 10,000 | 1 |
| curl / drq / sgqn | 19 each | 0 | 10,000 | 1 |

`execution_kind` across all records: **1174 exploratory, 1751 with no field (predating it), 44
eval_only_validation, and ZERO production.** Nothing in the fleet is a production measurement yet.

`audit_row_closure.py`: no PRODUCTION row mixes closures; 4 mixed-closure groups are exploratory
and expected; 1 group carries no `execution_kind` and cannot be classified.

## 6. The two long runs, and why they are the valuable thing

`ppg` reads max frame 10,240 in the table above **because its 600k run was never collected.**

| run | baseline | rows | frames | checkpoints | closure |
|---|---|---|---|---|---|
| `card0-20260909-115331` | ppg, seed 1 | 964 (347 train, 1 eval, 616 offline-eval) | to 600,064 | 14 | `16e960b1f446` |
| `card0-20260909-035152` | idaac, seed 101 | 569 (all offline-eval) | 51,200 to 598,016 | 12 | `16e960b1f446` |

Both are full-length, production-shaped runs: 4 regimes x 11 scene sets (scenes 0-9 plus the
pooled set) across 12-13 stamps. Both are superseded — current closures are `248751f7caca` (ppg)
and `1b092f978fdc` (idaac).

**Superseded here means re-hashed, not refuted.** The three commits that moved the revision after
these ran are `84d3b85` (ppg mode eval under `no_grad` — execution and memory, not forward-pass
values), `31f8f80` (rows record the action rule — metadata) and `0d4b0e1` (episode ids, a
docstring, the reverted jaxlib pin — identifiers). The estimand is unchanged: all 616 offline-eval
rows carry `eval_policy_mode=sample`, and `family_eval_policy_mode('ppg')` is still `sample`.

That is a reading of three diffs, not a measurement. The repo's rule blocks pooling on revision
mismatch precisely because "the diffs look harmless" is the failure it guards against. So: strong
evidence they are scientifically intact, formally inadmissible until re-measured or ratified.

**And because the checkpoints are retained, re-measuring costs no training.** Re-running the grid
on the 14 retained ppg policies reproduces an admissible 600k curve and endpoint without the ~4-10
GPU-hours of training. That is the single most valuable recoverable asset on the host.

## 7. RETRACTED — the ctrl checkpoint "gap" was my error, not a defect

An earlier version of this note flagged that `ctrl` declares
`models/robosuite:{task}/checkpoint_*.msgpack` while its completed run left only `snapshot.pt`,
and suggested its curve might be non-re-evaluable. **That is wrong and the repo already handles
it.**

`family.py:1147` dispatches on **content, not filename**, and says why: the runner copies every
family's checkpoint to `snapshot.pt` whatever it was called, so ctrl's flax msgpack arrives as a
`.pt`. Verified on the artifact itself — ctrl's `snapshot.pt` is 39,852,774 bytes beginning
`83 a4 73 74 65 70`, a msgpack map whose first key is `step`. It is the msgpack, renamed.
`snapshot_10000.pt` is its retained intermediate.

The comment at that line also records that this project made the inverse mistake before — an alda
terminal save "verified" by its filename rather than its bytes — which is exactly the error I then
repeated in the opposite direction. Checking the repo first would have cost one grep.

## 7b. What cross-checking the report against the rest of the project turned up

Verified each claim against the docs, descriptors, decision records and operator guide rather than
only against the host. Two real defects, both now fixed, plus one confirmation:

**The register cited a superseded note.** `curve-depth-vs-endpoint-depth` cited only
`notes/retention-and-eval-depth.md`, whose section 1 recommends **five** episodes per intermediate
stamp. The shipped value is **three** — A20, 2026-09-05, recorded in every family's
`curve_eval_episodes_reason` and in `docs/EVAL-PROTOCOL.md:490`. The decision was correct and
recorded; the note simply carried no supersession stamp, so a reader opening it directly saw the
five-episode recommendation as current. EVAL-PROTOCOL.md:490 warns about this exact pattern in its
own words. The note now carries a stamp at its head, and the row cites the authority first.

**A citation that resolved but pointed at the wrong line.** My corrected row cited
`families.json:1083` for the curve-depth decision. That line resolves — the file is long enough —
but holds `save_every_reason` for ctrl; the text meant is at `:166`.
`verify_resolved_register.py` passed it, because it checked only that a citation RESOLVES.
Rows may now declare `evidence_expect`, mapping a citation to a substring the cited line must
actually contain, and the verifier fails when it does not. Falsified before use: pointing an
anchor at the wrong content makes it exit 1 with the citation named.

**Confirmed rather than corrected:** `campaign_status.py` independently reports
`36 cells: 35 MISSING, 1 SUPERSEDED`, naming `idaac:101` at frame 598016 on a stale closure. That
agrees with this audit, and its silence about the 600k ppg run is consistent too — that run was
never collected, so the campaign tracker cannot see it.

## 8. Storage, and what is where

- `results/records/*.jsonl` — 82 collected bundles. The admissible surface.
- `results/superseded-runs/` — 84 MB: the three uncollected superseded bundles (986 rows), plus
  `checkpoints/` holding ppg's 600k terminal policy (sha-verified `a328e63e...`) and idaac's 12
  intermediates. Nothing in the reporting path reads this directory; its README says why.
- Host `~/rlvigen-runs` — 44 GB across ~36 run dirs. Per-run: ~1.9 GB regenerable `native-work`,
  plus `native-out`. `records_delivery.jsonl` alone is 1.37 GB in the 600k ppg run, because
  `_run_provenance` repeats at ~231 KB per row; stripped to one copy it is 22 MB.
- Host `~/rlvigen-assets` — 790 MB: the rlvigen archive and a 21-class, 37,500-image Places365
  subset. The full 365-class train corpus is deliberately absent under the disk bound.

## 9. Disk

Host: 262 GB free on a 20 TB filesystem at 99 % used; ours is ~46.7 GB of that. Local: 34 GB free.
No deletion has been performed and none is proposed in this note.
