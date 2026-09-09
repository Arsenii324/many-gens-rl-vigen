# The first complete endpoint grid: `idaac` on Door at 598,016 frames

**2026-09-09**, `card0-20260909-035152`, cell `idaac-s101`, seed 101. Pass 1 of 2
(`policy_mode=native`, which for `idaac` is **sample**) finished at 44 rows: 4 regimes x 11 scene
sets x 20 episodes = **880 episodes**. This is the first complete endpoint grid this project has
produced on any host.

| regime | return | sd | **SE** | success rate | episodes |
|---|---|---|---|---|---|
| train | **33.69** | 24.91 | 1.25 | 0.000 | 400 |
| eval-easy | **31.58** | 26.05 | 1.30 | 0.000 | 400 |
| eval-medium | **11.55** | 8.35 | 0.42 | 0.000 | 400 |
| eval-hard | **18.47** | 15.14 | 0.76 | 0.000 | 400 |

Standard errors of 0.4-1.3 on 400 episodes: every gap below is many SE wide and none of this is
noise.

## Retention

Against the train denominator, which `C43` exists to provide and which nothing before this project
built:

| regime | retention |
|---|---|
| eval-easy | **93.7 %** |
| eval-medium | **34.3 %** |
| eval-hard | **54.8 %** |

Visual perturbation costs `idaac` very little on `eval-easy` and roughly two thirds of its return on
`eval-medium`. **That is a real generalisation gap measured on a real grid**, and it is the kind of
number the whole benchmark exists to produce.

## `eval-hard` scores ABOVE `eval-medium`, and that is expected

18.47 against 11.55 is about 8 SE apart, and the same inversion appears at **every one of the eleven
curve stamps**, so it is systematic rather than a fluke of the endpoint.

**It is not a defect and not a mislabelling.** `rlgen/protocol.py:30-35` already says so, and said so
before this run:

> the eval modes differ in **WHICH** effects are switched on, not in the magnitude of any single
> effect — the magnitudes are shared constants upstream. So `easy < medium < hard` is a statement
> about the number of active nuisance factors, and it does **NOT** imply the returns are
> rank-ordered. In the sibling project only 3 of 12 checkpoints came out ordered
> `easy >= medium >= hard`.

Our run adds one data point in the same direction: **1 of 1 checkpoints not rank-ordered.**

*(I nearly filed this as a discovery. It is the third time today I have nearly written up as new
something the codebase already documented — the other two were the single-filesystem mirror
distinction, already argued in `run_on_production_host.sh:405-437`, and a claim about a plan item
that `families.json` already covered. Running `scripts/where_is_this_decided.py` before asserting an
absence costs seconds. **An agent writing from its own context cannot check breadth**, which is
exactly what `CONSOLIDATION-DESIGN-2026-09-09.md` D6 says and what I keep re-learning.)*

## Against the floor

A randomly initialised policy scores **≈ 2** on this axis (`ppg`'s frame-0 stamp, 60 episodes per
regime). `idaac`'s train 33.69 is therefore roughly **17x random**.

That comparison is caveated and deliberately not put in the table: the floor is `ppg`'s
initialisation, and **`idaac` has no frame-0 checkpoint at all** — its earliest retained checkpoint
is 51,200. `scripts/learning_over_random.py` reports `NO frame-0 row -- floor unknown` for this cell
rather than borrowing `ppg`'s number, which is the correct behaviour.

## What this grid does NOT establish

- **Nothing about RL-ViGen's own Door numbers.** They exist only inside Figures 22 and 19 and are
  not reported numerically anywhere in either vendored PDF. No "gap to the benchmark" claim is
  available from these documents.
- **Nothing comparable to the nine mode-policy families.** These rows are `sample`. Pass 2
  (`policy_mode=mode`) is what would be comparable, and it is the pass the reaper is expected to cut
  short at 18:37.
- **Nothing about IDAAC as an algorithm at its best.** This is IDAAC at faithful configuration, whose
  optimiser diagnostics show it updating far outside the trust region
  ([`idaac-on-door-is-a-trust-region-blowout.md`](idaac-on-door-is-a-trust-region-blowout.md)).

---

## Pass 2, and the two rows it will lose

Measured rather than projected: **pass 1 took 9,520 s (2.64 h)** for 880 episodes — **10.8 s per
episode**, which confirms the 12 s/episode constant used in `launch-card-cell.sh`'s new allowance
derivation is conservative in the right direction.

Pass 2 (`policy_mode=mode`) began **16:04 MSK** (`epoch=1788959041`). At the same rate it lands
**~18:43** against a reaper at **18:37**, so it completes roughly **42 of 44 rows** and then the cell
is stopped.

**What is lost is not the rows — it is the delivery.** `collect_record_delivery` runs after
evaluation, so a reaped cell writes every row and assembles none. Handled:

1. The rows are pulled locally every ten minutes. **This is a second copy, not a rescue** — the rows stay on the host's disk either way; what the stop costs is the ASSEMBLY step, not the measurements.
2. `scripts/assemble_reaped_delivery.py <fetched-run-dir> --out bundle.jsonl` rebuilds the bundle
   from the same sources the runner would have used, marking every row `_assembled_after_reaping`
   and printing coverage by `(frame, phase, policy mode)` so the missing cells are visible rather
   than inferred from a row count.
3. `collect-host-run.sh`'s refusal detects the per-cell rows and names that path.

**The two missing rows are recoverable, and recovering them is the experiment worth running anyway.**
`snapshot.pt` is retained, and `scripts/eval_grid.py` takes an arbitrary checkpoint:

```bash
python scripts/eval_grid.py \
  --snapshot <run>/native-out/cells/idaac-s101/snapshot.pt \
  --family idaac --baseline idaac --seed 101 --frame 598016 \
  --regimes <the regime that was cut> --scenes <the scene sets that were cut> \
  --episodes 20 --episode-seed 20260903 --policy-mode mode --eval-scope endpoint \
  --append --out <run>/native-out/cells/idaac-s101/offline_eval_endpoint.jsonl
```

This is exactly the **standalone evaluation from a previous cell's checkpoint** that
[`production-host/28-eval-is-sixty-percent-of-a-cell.md`](production-host/28-eval-is-sixty-percent-of-a-cell.md)
names as the one unproven piece of the train-then-evaluate-separately shape. Running it on two rows
we need anyway proves the wiring at negligible cost, and the check is direct: the recovered rows must
carry the same `evaluator_revision` as the 42 that preceded them.

---

# Rehearsal finding: the endpoint's frame label cannot be corroborated, and that is structural

Rehearsed the whole collection sequence on a pre-fetched copy at 18:10, before the cell was stopped.
It works end to end — assemble, collect under `NATIVE_ACCEPT_WATCH_STOP=1`, both audits — and it
found two things.

## 1. The auditor was double-counting, and only the totals were wrong

It reported **1,106 records for a 553-row bundle**. `records_delivery.jsonl` is by construction the
concatenation of `records.jsonl` and every `cells/*/offline_eval_*.jsonl`, and the auditor globbed
all of them, so each row was counted twice. **Every per-row verdict was right and every total was
doubled** — the worse way round, because a reader checks the totals. Fixed: when the bundle and its
own sources are both present the bundle is skipped, and a bundle alone is still audited. Two tests.

## 2. Every endpoint row is UNVERIFIABLE, and no amount of auditing fixes it

Corrected counts on the real cell:

| | rows | verdict |
|---|---:|---|
| curve | **484** | **corroborated** — each measured a frame-named checkpoint |
| endpoint, `native`/sample | 44 | **unverifiable** |
| endpoint, `mode` | 25 | **unverifiable** |

The endpoint evaluates **`snapshot.pt` at frame 598,016**. The retained frame-named checkpoints stop
at **550,912** — `agent-robosuite:Door-idaac-s101_51200.pt` … `_550912.pt`, eleven files. **There is
no `_598016.pt`**, so the alias mechanism that corroborates an unnamed file through a byte-identical
twin has no twin to find, and the frame on the project's *headline* measurement rests on a single
producer.

**This is not a defect in the audit; it is a gap in what the run retains.** And it applies to every
host run, not this one: the terminal checkpoint is always written as `snapshot.pt` and the frame-named
series always stops at the last periodic save.

### The fix, for the next run, and it is small

Retain the terminal checkpoint **under its frame name as well** — `..._598016.pt` beside
`snapshot.pt`, same bytes. Then the existing alias path corroborates all 88 endpoint rows for free,
and nothing else changes: the evaluator still loads `snapshot.pt`, the record still carries its
`checkpoint_sha256`, and `audit_record_frame_provenance.py` finds the twin and matches the name.

Cost: one extra 4.8 MB file per cell, against 53 MB of retained checkpoints already there.

**Until that lands, read the endpoint tables as measured-but-unlabelled**: the numbers are real and
the checkpoint hash is recorded, but *which frame produced them* is asserted by the runner rather
than corroborated by a second producer. The curve, which is 484 of the 553 rows, is fully
corroborated.
