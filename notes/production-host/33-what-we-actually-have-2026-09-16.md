# What we actually have, 2026-09-16 — the re-evaluation landed, and three numbers were wrong

Successor to [`32-what-we-actually-have-2026-09-14.md`](32-what-we-actually-have-2026-09-14.md).
Same rule: every number read off the host or out of `results/` during this session, not recalled.
Where I got something wrong, the correction is stated rather than quietly replaced — and this time
there are three, all of the same shape.

## 0. The headline: the fleet has admissible production rows now

`32` §5 recorded **2969 rows, 28 on the current closure**, and `execution_kind` showing *"ZERO
production"*. Today:

```
3673 rows, 732 on the CURRENT closure, 2941 superseded
```

The 704 new rows are the re-evaluation `32` §6 argued for — *"because the checkpoints are retained,
re-measuring costs no training... the single most valuable recoverable asset on the host"*. It was
done, and it cost no training:

| bundle | rows | what it is |
|---|---|---|
| `reeval-v214-ppg-endpoint` | 88 | ppg seed 1 @ 600,064, 11 scene sets x 4 regimes x 2 policy modes |
| `reeval-v214-ppg-curve` | 528 | ppg seed 1, 12 stamps from 51,200 to 600,064 |
| `reeval-v214-idaac-endpoint` | 88 | idaac seed 101 @ 598,016 |

So `32`'s "strong evidence they are scientifically intact, formally inadmissible until re-measured"
is resolved the honest way — by re-measuring, not by ratifying the diff-reading.

## 1. But the campaign counts ONE cell, not two, and the reason is the seed

`campaign_status.py` reports **36 cells: 35 MISSING, 1 DONE**. Only `idaac:101` counts.

`production-schedule-v100.json` names seeds `[101, 102, 103]`. **ppg is banked at seed 1**, which is
not in that set, so every ppg column reads MISSING however good the rows are. The rows are valid —
the seed was fixed in advance and not chosen by outcome, which is what the n=3 policy in
`docs/EVAL-PROTOCOL.md` §4b actually requires — but any join from records to the schedule misses
them, and the campaign tracker is such a join.

This is a decision someone must make explicitly rather than let the tracker make by omission:
either ppg's seed set is recorded as `{1, 102, 103}`, or ppg is re-run at 101 and eight GPU-hours
buy a number we already have. Implemented default, pending ratification: **keep the run, record the
set as `{1, 102, 103}`**.

## 2. VRAM is measured for six of seven families — and README.md still says it is measured for none

`README.md` states *"We do not currently satisfy this for VRAM: six of seven families have no VRAM
measurement at all. That blocks the first shared-GPU cell until it is closed."* That is now
inverted. From `datasphere/native/measured-vram-bounds.json`:

| family | peak (ours) | | family | peak (ours) |
|---|---|---|---|---|
| `ctrl` | 32,435 MiB | | `dmc_gb` | 2,529 MiB |
| `ppg` | 7,146 MiB | | `alda` | 2,397 MiB |
| `rlvigen` | 4,549 MiB | | one eval cell | 841 MiB |
| `idaac` | 2,638 MiB | | **`ibac_sni`** | **still unmeasured** |

`ctrl` at 32,435 MiB exceeds a 32,494 MiB card once the 4,000 MiB floor is added, so ctrl cannot
satisfy floor-plus-peak at all: it needs an empty card **and** an explicit floor decision. That is
a harder constraint than "needs a big card" and it was not previously stated anywhere.

## 3. The three wrong numbers, because the shape is the lesson

`ibac_sni`'s VRAM at `procs=16` was quoted three times today and every figure was wrong:

| figure | where it came from | why it is wrong |
|---|---|---|
| ~15 GiB | a **comment** in `reeval-cell.sh`, quoted back as a measurement by two agents | never measured |
| 2,199 MiB | a real measurement of a **3-process** cell | under-counts: the same cell's card delta is 6,804 MiB, and the ~4.6 GiB gap is EGL render contexts, which are not compute apps |
| 22,675 MiB | reported by me as measured | **21,300 MiB of it was a colleague's two processes** |

The third was an instrument defect and the most instructive. `measure_vram_bounds.py` summed every
compute process on the card while its own docstring claimed it filtered to this cell's process tree.
No such filter existed, and none can be added: the cell's pids are container-namespace and
`gpu_compute_processes` carries host pids. The field is now `all_procs_peak_mib`, rows carry
`shared_card` and `steady_state`, and the per-family aggregation **refuses** a shared or
still-ramping row.

Only a lower bound survives for ibac_sni: **~6.6 GiB**, the card delta at the moment the floor stood
a cell down 42.4 s in, with its process count still climbing 2 → 20.

**The operating rule this produces:** before a number decides anything, find where it was produced.
A number in a comment is not a measurement, and this directory's `10-resource-upper-bound-rule.md`
is unenforceable without that habit.

## 4. ibac_sni has never completed a 600k cell — five attempts, and what stopped each

| run | stopped by | reached |
|---|---|---|
| `card0-20260916-005601` | memory floor, free 3,705 MiB | no checkpoints |
| `card0-20260916-010515` | `NATIVE_CELL_FAILED` | no checkpoints |
| `card1-20260916-115450` | memory floor, free 125 MiB | **F 100352** — the furthest any ibac_sni cell has trained |
| `card1-20260916-121400` | preflight refusal, free 150 MiB < 4,000 | never started |
| `card1-20260916-141636` | memory floor, free 3,063 MiB | started training |

Four of five are the memory floor doing its job on a card a colleague was holding. This is not an
ibac_sni defect; it is a scheduling fact. It needs a card with roughly 11 GiB free that **stays**
free, which on this host means waiting for a real window rather than a momentary one (§5).

## 5. The co-tenants, and the arithmetic that actually decides a launch

Observed on both cards, by container name:

| container | hold | behaviour |
|---|---|---|
| `rlvigen_kalugin_df` | **two processes, ~10,650 MiB each = ~21.3 GiB** | releases the whole block and reclaims it within tens of minutes |
| `rl4vla_cudagl` | ~14,700 MiB | long-lived |
| `sg_sam2` | ~3,800 MiB | long-lived |

**A card that just became free is not a free card.** A 600k cell was launched into a five-minute
vacancy on card 1 and the co-tenant returned within minutes.

The arithmetic that follows is the useful part, and it is not the obvious one. **Size a launch
against the co-tenant's RETURN, not against current free.** Worked example, card 1 at 15:16 today
with 28,858 MiB free and our idaac s102 (2,635 MiB) resident:

- Add ppg (7,146): free becomes 21,712. The colleague reclaims 21,298 → **414 MiB free, under the
  4,000 floor, and BOTH our cells yield.**
- Add nothing: the colleague's return still leaves 7,560 MiB → **idaac s102 survives.**

So the second cell does not cost a coin-flip on itself; it costs the cell already running. Declining
to launch was the higher-value action, and that is the opposite of what "use the free card" suggests.

## 6. Two published claims of mine, retracted in place

Both were wrong in the direction that flatters the writer, which is why they are recorded here
rather than edited away.

**"The memory floor is enforced only at preflight."** Written into
[`../model/STOP-MECHANISMS.md`](../model/STOP-MECHANISMS.md) after reading
`watch_gpu_headroom.py`'s `watch()` and finding it enforces nothing. `watch()` really is only a
recorder — but it is not the enforcer. `yield_gpu_to_neighbour.py`, armed at STEP 2 of every launch,
polls the floor for the life of the cell and writes the sentinel. It was demonstrated an hour later
by the s101 cell standing itself down at `free memory 3063 MiB is below the 4000 MiB floor`. The
reasoning error: I read one function, found it did not enforce, and concluded nothing did.
`yield.sentinel` has three writers and I checked one.

**"The nine mode baselines are unaffected by evaluator nondeterminism."** Pairing all 88 endpoint
rows across two completed runs of the same invocation: **mode rows reproduce 282/800 episodes,
sample rows 264/800.** Near-identical, so action sampling is not the driver and all twelve
baselines are exposed. `eval-medium` and `eval-hard` reproduce **0/200** in both modes while `train`
and `eval-easy` reproduce 132–150/200, and placements are identical 40/40. The mechanism is
recorded as **open** — `VGBWrapper`'s `random_state` drives texture/colour/lighting and is never
re-seeded per episode, but a once-seeded generator consumed identically still yields identical
sequences, so something must first perturb the draw count. See
[`../endgame/RESOLVED-ppg-reeval-is-within-evaluator-noise.md`](../endgame/RESOLVED-ppg-reeval-is-within-evaluator-noise.md).

## 7. Storage

| where | size | note |
|---|---|---|
| host `~/rlvigen-runs` | **59 GB** (was 44 GB on 09-14) | ~41 run dirs from today alone |
| host `~/rlvigen-assets` | 790 MB | rlvigen archive + a 21-class Places365 subset; the full 365-class train corpus is deliberately absent |
| host free | **99 GiB** | fell 137 → 99 GiB during today's bootstraps; the sweep refuses new cells below `MIN_FREE_GIB=100` |

No deletion has been performed and none is proposed.

## 8. Running as of this writing

- `idaac` seed 102, 600k training on card 1 since 14:32 MSK, under `self-vram-cap.sh` at 5,000 MiB.
  This is the second idaac seed, giving `{101, 102}` against the schedule's `[101, 102, 103]`.
- `idaac` seed 101 curve sweep on card 0, **7 of 11 stamps** banked, 4 cells in flight. Completing
  it gives idaac a full curve to match ppg's.

## 9. What this leaves open

- **`ibac_sni` has no completed 600k cell and no VRAM measurement.** Both are the same blocker.
- **`ctrl` cannot fit floor-plus-peak on a 32,494 MiB card** and has never run at 600k.
- **Nine of twelve baselines have no production record at all.**
- **The evaluator-nondeterminism mechanism is unexplained**, and it affects every baseline rather
  than the three sampling ones.
- **`svea`, `sgqn` and `soda` are blocked on Places365 and nobody had written that down.** The host
  holds `~/rlvigen-assets/places365` at 563 MB, whose `train/` is **20 class directories and 1,000
  files** — the attestation fixture, not the corpus. The operator guide's §2b told an operator to
  fetch to `/data/places365`, a path that does not exist on this host on a `/data` that is not
  writable. The real corpus is ~24 GB against 97 GiB free.

  The part worth pausing on: **nothing mechanical would have caught a cell trained against the
  fixture.** `run_probe.sh` verifies `PLACES365_EXPECTED_COUNT`/`_SHA256` against what the operator
  DECLARED, no gate ties a production run to the production dataset, and `family.py
  needs-places365` only answers whether a cell needs one. The augmentation corpus is a
  learning-affecting input, so such a cell is not a wrong-looking cell — it is a wrong cell that
  looks right, for a quarter of the fleet.
