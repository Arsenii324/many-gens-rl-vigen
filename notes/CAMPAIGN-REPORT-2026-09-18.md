# Campaign report — what ran, what it says, and what failed

**2026-09-18, 07:40 MSK.** The task was: run the twelve baselines on RL-ViGen Door at three seeds,
get genuinely same-axes measurements, best effort, and say what succeeded and what failed. This is
that account. Every number is reproducible by the command named beside it; nothing here is recalled.

---

## 1. What exists

    python scripts/campaign_status.py        # 36 cells: 32 MISSING, 3 DONE, 1 PARTIAL

| baseline | seed 101 | seed 102 | seed 103 |
|---|---|---|---|
| `idaac` | **DONE** | **DONE** | MISSING (armed, waiting for a card) |
| `ibac_sni` | **DONE** | PARTIAL (7 salvaged stamps) | MISSING |
| `ppg` | banked at **seed 1**, off-schedule | MISSING | MISSING |
| `drqv2`, `svea`, `drq`, `sgqn`, `curl`, `rad`, `soda`, `alda`, `ctrl` | MISSING | MISSING | MISSING |

**Three of thirty-six cells are complete**, from three baselines, all on-policy. `ppg` seed 1 is a
complete cell that the counter reads as MISSING because the schedule names seeds {101, 102, 103};
that is a bookkeeping decision awaiting the owner, not a missing run.

Twelve production attempts are recorded (`results/host-runs.jsonl`): **3 complete, 7 failed,
1 yielded mid-run, 1 stopped by its watch budget**. Of the eight that did not finish, **seven were
stopped by the GPU memory floor when a co-tenant returned to the card**, and one by an EGL worker
dying 24 s in. None was an algorithmic failure, and none damaged another group's job.

The fleet holds **6,193 rows, 2,932 on the current evaluator closure** (`export_fleet.py`), across
all twelve baselines — but most of those are pre-production probes and attestations, not production
cells.

## 2. What the completed cells say

    python scripts/production_reading.py --retention

Aggregated as `docs/EVAL-PROTOCOL.md` §4c requires (episodes → ten scenes → seeds as the only
replicates), train regime, at the 600k endpoint:

| baseline | seed | estimand | train Ȳ | train success |
|---|---|---|---|---|
| `ibac_sni` | 101 | sample | 82.18 | 0.005 |
| `idaac` | 101 / 102 | sample | 39.24 / 20.51 | 0.000 / 0.005 |
| `ppg` | 1 | sample | 22.69 | 0.000 |

**The headline finding is negative, and it is the most important thing in this report.** Every
completed policy sits far above the 1.842 random floor on shaped return and **opens the door in at
most one episode in two hundred**. Across the full retained curve — twelve stamps for `ibac_sni`
s101 — shaped return climbs 15.15 → 79.36 while success stays at 0.000. These policies optimise the
reaching-and-grasping shaping term and do not solve the task.

Under the project's own competence gate (§3 of the protocol) a retention *ratio* may not be reported
for any of them, and the tool refuses to print one. That is correct: a method that never solves the
task has a gap of ~0 between regimes because there is nothing to lose, which would read as perfect
generalisation. Detail and the three candidate explanations:
[`production-host/36`](production-host/36-no-completed-cell-passes-the-competence-gate.md).

**So the campaign cannot yet answer its own question.** What it can say is: *these three on-policy
methods do not reach competence on Door at 600k frames*, which is a real result about this
benchmark at this budget, and one the reference does not cover — RL-ViGen never ran the on-policy
family on Door.

**For contrast, from the reference's own published table** (`notes/rlvigen-published-door-anchor.md`):
their DrQ-v2 scores 3.6 on Door eval-easy — also a failure — while **SVEA reaches 268.8 and SGQN
391.4**, above the 250 shaping ceiling, i.e. actually opening the door. The methods that solve this
task are the augmentation/saliency family, and none of them has run here yet.

## 3. What failed, and why

| failure | count | cause | consequence |
|---|---|---|---|
| Cell stopped by the memory floor | 7 | a co-tenant returned to the shared card mid-run | stamps kept from the last 50k boundary; the seed must be rerun from zero |
| EGL worker died 24 s in | 1 | rendering never initialised | nothing lost, relaunch |
| Cell reaped at its watch budget | 1 | the endpoint grid ran past the booking | every row already written was collected |
| Retention unanswerable | — | competence gate (§2 above) | returns published, ratios withheld |
| Nine baselines never run | 9 | card availability; Places365 for three of them; `ctrl` needs an empty card | — |

**The binding constraint all along was card availability, not throughput.** A cell needs 15–21
hours of uninterrupted card time; the co-tenant's absences were mostly 1–4 minute restarts. Over the
night of 17–18 Sep the card was free once, for twenty minutes, at 21:39 — and nothing launched,
because the watcher only reported. That is now fixed (`wait-and-train-v4.sh` launches under the
validated rule), but it cost a cell.

At measured rates the full 36-cell campaign needs **20–28 days of uninterrupted card time**
([`production-host/35`](production-host/35-what-the-campaign-costs-at-measured-rates.md)). It was
never going to finish in the window; what matters is that the subset chosen is defensible.

## 4. What is ready that was not

- **The operator path is executable end to end by someone else.**
  [`OPERATOR-GUIDE.md`](OPERATOR-GUIDE.md) maps every stage, every stop mechanism, every check, the
  per-family checkpoint/resume facts, and an out-of-reach catalogue with a target and an operation
  for each item. §11 separates what was executed from what was not, line by line.
- **The cold start is verified on Linux**: fresh tree → reconstruct → verify → payload build, verify
  and evaluator binding for all seven families, every exit code 0
  ([`results/evidence/linux-reconstruction-from-a-fresh-tree`](../results/evidence/linux-reconstruction-from-a-fresh-tree/CLAIM.md)).
- **Places365 is no longer blocked.** The 55 kB/s that stopped it was the *source*: the host pulls
  13.7 MB/s from GitHub and 623 B/s from `data.csail.mit.edu`. The validated 26 GB corpus is being
  shipped from the laptop; `svea`, `sgqn` and `soda` become launchable when it lands, with the
  wrapper path already dry-run proven.
- **The reading is a command, not a hand calculation.** `production_reading.py` aggregates per the
  protocol, prints every seed point, carries the success rate beside every return, refuses a ratio
  where competence fails, and says how many cells it skipped.

## 5. What I would do next, in order

1. **`idaac` s103** — armed and self-launching; completes the first baseline at n = 3.
2. **`svea` s101** once the corpus lands — the first test of a method the reference says solves
   Door, and the first use of the Places365 path.
3. **`drqv2` s101** — needs no corpus, its payload is already on the host, and it is the one
   baseline with a published number to check ourselves against (eval-easy within 1–7).
4. Only then more seeds of the on-policy trio.

This ordering follows from §2: more seeds of methods that never solve the task tighten the error
bars on a plateau, while one `svea` cell tests whether this port reproduces the behaviour that makes
Door interesting at all.

## 6. Honest limits of this report

- Three cells is not a result about generalisation, and nothing here should be read as a ranking.
  One `idaac` seed pair already changed the sign of its own train → eval-easy gap.
- `ppg`'s seed is off-schedule; `ibac_sni` s102 is a partial curve from a stopped run and is
  recorded as a separate trajectory, never pooled with a future rerun of that seed.
- No cell has yet consumed Places365, and no augmentation baseline has run, so the comparison the
  benchmark exists for has not been attempted.
- The renderer-parity probe (R_A/R_B) remains an OWNER gate: our returns and the published ones have
  not been shown to come from the same rendering path, only from the same axis.
