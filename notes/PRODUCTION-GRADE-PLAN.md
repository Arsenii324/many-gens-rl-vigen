# Getting to a reportable battery in the fewest runs

**2026-09-09.** Every number here is measured on `card0-20260909-035152` or read from a vendored
source. The goal it serves: **spend as few runs as possible before every remaining run is production
grade.**

## The blocking constraint nobody had costed: seeds

RL-ViGen's own reporting standard, from the main paper (§ Provision of Raw Scores):

> To record the **stratified bootstrapped confidence interval** for each algorithm, it is vital to
> provide the **raw scores for each seed** instead of simply offering aggregated scores.

**We have one seed per baseline.** A single seed cannot produce a seed-level interval, so no amount
of additional evaluation on the runs we have makes them reportable to that standard. This is the one
gap that *requires* GPU time rather than analysis.

## What a seeded battery costs, from measured components

Components: **train 4.95 h**, **curve 4.60 h**, **endpoint 2.76 h per policy mode**. Three families
(`idaac`, `ppg`, `ibac_sni`) take a second endpoint pass; nine take one.

| plan | GPU-hours | days on one card | cells |
|---|---:|---:|---:|
| 1 seed, exactly as run today | 156 | 6.5 | 12 |
| 3 seeds, as run today | 468 | 19.5 | 36 |
| 3 seeds, lean curve | 402 | 16.7 | 36 |
| **3 seeds, lean curve, curve on seed 1 only** | **336** | **14.0** | **36** |
| 5 seeds, same shape | 537 | 22.4 | 60 |

Two savings, both already justified elsewhere:

- **Lean curve** (`production-host/28`): `train` + `eval-easy` at four scene sets, ten episodes,
  same eleven stamps — **cheaper AND more readable** than the current four regimes x ten scenes x
  three episodes, whose points are too thin to read individually.
- **Curve on seed 1 only.** The curve exists to show training dynamics; the confidence interval needs
  endpoints. Seeds 2 and 3 need train + endpoint, not a second and third trajectory.

**Recommendation: 3 seeds, lean curve on seed 1 only — 336 h.** Five seeds buys a tighter interval
for another 200 h, and 14 days of a shared booked card is already at the edge. The formal choice is
the owner's; this is the plan I would run.

## The ordering that makes it "fewest runs"

**Everything below must land before cell 1 of the battery**, or the battery inherits a defect and
some of its 36 cells have to be repeated. As of tonight a `ppg` re-run is already owed for exactly
this reason.

### Step 1 — `ppg` finished; both cells carry a complete primary result — **done 2026-09-10**

`ppg-s1` ended `NATIVE_CELL_FAILED` and **its native endpoint grid is complete**: 44/44 rows, as is
`idaac-s101`'s. Only the supplementary `mode` pass was lost (ppg 0/44, idaac 41/44). Numbers,
validity and the floor comparison are in
[`two-endpoint-grids-and-the-unit-of-variation.md`](two-endpoint-grids-and-the-unit-of-variation.md)
and [`both-endpoint-grids-against-the-random-floor.md`](both-endpoint-grids-against-the-random-floor.md).
`sha256(snapshot.pt)` equals the `checkpoint_sha256` on every one of those rows for both cells, so
any later evaluation of those bytes is commensurable with them by construction.

**Not yet installed into `results/records/`.** ppg's `records_delivery.jsonl` is 1.27 GB for 964
rows (see below); installing it as-is would import the defect. Options are to regenerate the bundle
on the host under the fixed runner, or to install from sources with an explicit provenance marker.
**Left as a decision rather than guessed at**, because a mislabelled bundle is worse than a
missing one.

### Step 2 — one revision bump, now carrying five changes
Landing these separately costs five re-attestations of seven families; together, one. Three were
implemented on 2026-09-10 and are **in the working tree awaiting the bump**; two remain.

| change | defect it closes | member | state |
|---|---|---|---|
| `ppg` mode eval under `no_grad` | killed a 3.6 h cell; bypassed `PpoModel.act`'s `@tu.no_grad` | `scripts/eval_grid.py` (CODE) | **done** |
| row states the action rule it *used* | 41 rows labelled `sample` were `mode`; the closure audit read the wrong field | `datasphere/native/normalize_curves.py` (CODE) | **done** |
| episode id gains `eval_scope` + `eval_policy_mode` | 760 of 2,120 ids collide, all reporting different returns | `scripts/eval_grid.py` (CODE) | **OPEN — my earlier "subsumed" was wrong.** Verified 2026-09-10 on `card0-20260909-035152`: **all 760** mode-pass ids collide with sampled ones, e.g. `idaac-s101-f598016-eval-easy-sc0-e0` names two episodes with different returns. The conventions fix made the ROW distinguishable; the ID still names two measurements |
| `runtime_import_manifest` → digest per row, manifest to a sidecar | 74 % of a 19.7 MB bundle; 2 distinct values over 569 rows; nothing reads it | `scripts/eval_grid.py` (CODE) | open |
| `ppg` `nminibatch` — assert like `idaac` does | executed config was not the declared one, silently | `runnable/ppg/…` (FAMILY_RUNTIME) | open |
| write a frame-0 checkpoint | no family has a measured **initialised-network** floor | family runtimes | open — but see below |
| `eval_grid.py:734` docstring says `general.py` reads `RLVIGEN_MODE`/`RLVIGEN_SCENE_ID` | it moved to `ibac_sni_runtime.py:65,77`; the BEHAVIOUR is intact, the pointer is stale | `scripts/eval_grid.py` (CODE) | open — docstring-only, but it moves every family's revision, so it waits for the bump |
| `tests/test_eval_identity.py` fails only in a full run | `ModuleNotFoundError: No module named 'models.sac'` — an earlier test puts a `models` package on `sys.path` that shadows ibac_sni's. Passes alone. **The suite's result is order-dependent**, so "green" means "green in this order" | tests only, no member | open — instrument hygiene, not a product defect |
| pin `jaxlib==0.4.35` beside `jax[cuda12]==0.4.35` | jax 0.4.35 against jaxlib 0.4.34 makes every cuDNN engine reject `ctrl`'s first conv; **ctrl has never completed on this host** | `datasphere/native/families.json` (CONFIG) | open — blocks 3 of 36 battery cells |

**The frame-0 item is no longer blocking interpretation.** C55's random-**action** floor (1.842,
`rlvigen_reference.py:87`) applies to these grids and survives the closure change, because
`probe_floor.py` never reads the observation and so is invariant to every axis that moved the
revision. Both cells are 6.2×–18.3× it. What frame-0 would add is the *initialised network's* floor,
a different question. It needs a per-family trainer change, since `eval_grid.py` unpickles agents
and cannot construct one.

### Step 2b — the ordering constraint found on 2026-09-10, and it inverts the plan

**7/7 is not reachable before the bump, because one of the bump's own items is what unblocks the
seventh family.** `ctrl` fails on this host with jax 0.4.35 against jaxlib 0.4.34 (every cuDNN engine
rejects its first convolution). The fix is a `jaxlib` pin in `families.json` — a `CONFIG_MEMBER` —
so applying it moves every family's evaluator revision and voids any attestation standing at the
time.

Attesting first and fixing second therefore costs two waves of seven. **Land every pending member
change, freeze, then attest once.** That is Q47's rule — accumulate fixes, validate once against the
final frozen tree — and it was learned again the hard way here.

The four families attested on 2026-09-10 (`idaac`, `ppg`, `alda`, `ibac_sni`) are **provisional**:
they will be superseded by the bump. Their value was not the ledger entry. They were the first
end-to-end runs of this pipeline on the V100 and they found two defects nothing static would have:

- `ctrl`'s jax/jaxlib split, and that **ctrl has never completed on this host**;
- `launch-card-cell.sh` silently dropping both asset archives, which made `svea`, `sgqn` and `soda`
  unrunnable through it — 9 of the 36 battery cells.

### Step 3 — re-attest, then verify on one short cell
`production_gates.py` back to 7/7, then a single short cell checked with
`scripts/audit_eval_validity.py --strict`: ids unique, summaries self-consistent, placement paired.
**One cheap cell, not a battery, is what proves the fixes.**

### Step 4 — the `drqv2` validity check, still first
Hard criterion, unchanged: Door's reward is 1.0 on success and at most 0.25+0.25 otherwise, so over
500 steps **a policy that never opens the door cannot exceed 250, and above 250 proves a success
step**. If `drqv2` lands near 34 with SR 0.000 beside `idaac`, the ceiling is the harness or the task
configuration, not either algorithm — and that changes what the whole battery is worth running for.

### Step 5 — the battery, 36 cells
With `record_host_run.py` at launch and `collect-host-run.sh` at the end, both now refusing to
overwrite.

## What is already fixed and needs no run to prove

`run_probe.sh` is in no evaluator member set, so the terminal-checkpoint stamp
(`snapshot_<frame>.pt`) is live now: endpoint frame provenance goes from **0 corroborated to all of
them**, verified on the real records by adding the alias and re-auditing.

## What no amount of running fixes, and must be reported as a limitation

`eval-medium` and `eval-hard` **resample their visual perturbation between passes** — 62 % and
**13 %** of slots respectively, against 0 % for `train` and `eval-easy`.

> **Denominator corrected 2026-09-10.** `eval-hard` was stated as 10 %, which divided 21 varying
> slots by all 200 rather than by the **166 that were actually observed more than once**. A slot
> seen once is evidence of nothing. `audit_eval_validity.py` now counts observations per slot and
> prints `NOT COMPARED` where there are none — it previously reported "0 % vary" for a single-pass
> file across 800 slots it had never compared. That is RL-ViGen's design, not a bug,
but it means **no paired claim is available for those regimes**, and their numbers carry perturbation
variance on top of episode variance. Seeds do not fix it; only more episodes narrow it.
