# What we actually have, 2026-09-16 — the re-evaluation landed, and three numbers were wrong

Successor to [`32-what-we-actually-have-2026-09-14.md`](32-what-we-actually-have-2026-09-14.md).
Same rule: every number read off the host or out of `results/` during this session, not recalled.
Where I got something wrong, the correction is stated rather than quietly replaced — and this time
there are three, all of the same shape.

## 0. The headline: the fleet has admissible production rows now

`32` §5 recorded **2969 rows, 28 on the current closure**, and `execution_kind` showing *"ZERO
production"*. Today:

```
4157 rows, 1216 on the CURRENT closure, 2941 superseded
```

The 1,188 new rows are the re-evaluation `32` §6 argued for — *"because the checkpoints are retained,
re-measuring costs no training... the single most valuable recoverable asset on the host"*. It was
done, and it cost no training:

| bundle | rows | what it is |
|---|---|---|
| `reeval-v214-ppg-endpoint` | 88 | ppg seed 1 @ 600,064, 11 scene sets x 4 regimes x 2 policy modes |
| `reeval-v214-ppg-curve` | 528 | ppg seed 1, 12 stamps from 51,200 to 600,064 |
| `reeval-v214-idaac-endpoint` | 88 | idaac seed 101 @ 598,016 |
| `reeval-v214-idaac-curve` | 484 | idaac seed 101, 11 stamps from 51,200 to 550,912 |

**idaac's curve completed and was collected at 16:00 MSK**, so idaac and ppg now both have a full
endpoint grid AND a full curve. It was collected with `scripts/collect_reeval_sweep.py`, written
the same afternoon because nothing merged a sweep's per-stamp archives — ppg's 528 rows had been
merged by hand — and the ledger accepted it: `paired=True`, `diagnostics_complete=True`.

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
| `idaac` | 2,638 MiB | | **`ibac_sni`** | **7,421 MiB** total — see 3b |

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

## 3b. Measured at last: 7,421 MiB, and why the number was always going to be 2,199 plus something

At 20:35 the waiter launched ibac_sni s101 into a card 1 that had emptied and held free for ten
polls, and for the first time the cell trained past its ramp. With no co-tenant on the card,
`card total − card free` is ibac's true footprint. Three consecutive 20-second samples, with
training advancing F 8,192 → 12,288:

```
ours=2199 MiB   card_used=7421 MiB   non-compute=5222 MiB
```

**So the 2,199 MiB in every failed attempt was never a ramp point.** It is the stable compute-app
part. The other 5,222 MiB is EGL render contexts, which `nvidia-smi` does not list as compute apps
and no per-process sum can see. Section 3 above correctly refused to call 2,199 a peak; the reason
was different from the one it gave.

**It explains every failure exactly.** ibac needs 7,421 + 4,000 floor = **11,421 MiB**. Card 1 with
its ~21.3 GiB co-tenant resident offers 32,494 − 21,300 − 4,000 = **7,194**. It was short by 4.2 GiB
every time the co-tenant returned — arithmetic, not luck.

**And it changes how to read every other figure in section 2.** Those are compute-app figures and
under-state total footprint by their own EGL share, which grows with the number of rendering
workers. `measured-vram-bounds.json` now says so first; `self-vram-cap.sh`, which also sums compute
apps only, read 2,199 while the cell held 7,421.

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

**A co-tenant can take 6.2 GiB in TWENTY SECONDS, which changes what monitoring can protect.**
Measured from our own cap watcher's samples on idaac s102, twenty seconds apart:

```
17:54:27  ours=2640MiB  peak=2640MiB  card_free=6422MiB
17:54:47  ours=2640MiB  peak=2640MiB  card_free=224MiB
```

The floor fired at `free memory 224 MiB is below the 4000 MiB floor` and stood our cell down at 41%
of 600k. Our own usage never moved — peak 2,640 MiB against a 5,000 cap — so we did not cause it.

The lesson is not "watch the card longer". **No poll can see a 6.2 GiB step that completes between
two samples**, and ours runs at 20 s. What protected the colleague was the sentinel check inside the
cell, which acts in-process at the moment of the breach. Monitoring tells the OPERATOR what
happened; only the floor acts in time. Sizing against the co-tenant's return (below) remains the
right planning rule, and it is a planning rule, not a defence.

**Nothing was lost that the protocol cares about.** Five checkpoints were retained (51,200 through
251,904) and each is separately evaluable, so the run is partial rather than void. idaac cannot
RESUME — `families.json`'s checkpoint semantics give it policy plus observation statistics, no
optimizer or RNG state — so the rerun policy applies: rerun from zero under the identical seed,
never resume.

**Confirmed by the event rather than left as a prediction.** At 16:05 the co-tenant returned to card
1 with 10,650 + 11,246 = 21,896 MiB, leaving **6,422 MiB free**. idaac s102 was at 21% and survived,
because 6,422 is above the 4,000 floor. Had the ppg cell been added an hour earlier, free would have
gone below zero and the floor would have stood **both** cells down — losing 1.5 h of training to gain
a cell that would also have died. The arithmetic was not conservative; it was correct.

## 5b. The scheduling model this host actually has: eval survives co-tenancy, training does not

Six ibac_sni attempts and one idaac attempt died the same way, and the pattern is now clear enough
to schedule against rather than to keep re-discovering.

**The two cards have different co-tenants and they behave differently.**

| card | co-tenants | behaviour | what we should put there |
|---|---|---|---|
| 0 | `sg_sam2` ~3.8 GiB, `rl4vla_cudagl` ~14.7-22.5 GiB | **long-lived and stable** | our work |
| 1 | `rlvigen_kalugin_df`, two processes ~21.3 GiB total | **cycles off and back within tens of minutes** | nothing we mind losing |

**And the size of our cell decides whether it survives.** An eval cell is 841 MiB and coexists with
a 21.7 GiB co-tenant; a training cell is 2.6 GiB or more and does not survive the spikes, because
the floor stands it down the moment free memory drops under 4,000 MiB. That is the floor working —
our cell dies, the colleague's does not — but it means:

> **On this host, under this co-tenant, EVALUATION work is viable and TRAINING work is not.**

The evidence, all from today:

- idaac s102: killed at 41% when free fell 6,422 → 224 MiB in **20 seconds**.
- ibac_sni s101: killed 8 minutes after launch, mid-ramp, when free fell 8,575 → 2,595 MiB.
- Meanwhile **eleven eval cells completed** on card 0 across the same afternoon, and the entire
  idaac curve was produced while co-tenants held 26 GiB of that card.

**A consequence for the ibac_sni measurement, and it is why the number keeps coming out the same.**
Our cap watcher recorded ibac's ramp at 308 → 616 → 1,375 → 2,199 MiB, and the floor fired at 2,199
with the process count still climbing. The earlier attempt also stopped near 2,199. That figure is
**where the floor catches ibac, not what ibac needs** — reporting it as a peak would repeat exactly
the error section 3 documents. Its footprint stays unmeasured, and it stays unmeasured for the same
reason it stays unrun. **[Superseded by 3b: measured at 7,421 MiB.]**

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
