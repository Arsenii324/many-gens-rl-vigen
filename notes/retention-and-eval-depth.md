# What the production run must emit — retention, eval depth, and the cross-scale problem

Written 2026-09-05 at the owner's direction: *don't commit to only derivative results; fine-grained
train metrics, fine-grained during-training eval results that are not over-aggregated, checkpoints
from across training that we can actually retrieve and evaluate, and eval runs that report richly so
any aggregation or hypothesis check can be post-hoc.*

The balance of eval frequency and depth was left to me. Here it is, with the arithmetic.

---

## 0. The reversal this forces, and why it is now correct

I previously recommended **evaluating the checkpoint grid in-container and discarding the weights.**
That was right for DataSphere, where the argument rested on [C95](../docs/CONSTRUCTION.md#c95) *and*
on archive cost. Production now runs on our own V100 with our own disk and no per-hour billing, so
half that argument is gone.

**Retain every checkpoint. It is the strongest possible form of the owner's requirement.**

A retained checkpoint makes re-answerable not just the questions we thought to record, but
**evaluations we never planned** — a scene set we did not certify yet, an episode count we did not
budget, a regime we have not defined, a diagnostic invented after the fact. No amount of pre-planned
logging matches that, because logging can only capture questions already asked.

**Corrected 2026-09-05 — the number originally here was never actually computed; see
CORRECTIONS #50.** It read "the whole fleet's grid is 35.5 GB", copied from
`claude-answers.md:1311`'s `600000 x 63504 = 35.5 GiB replay` — which is the in-memory replay
buffer size for **one off-policy cell**, not a fleet-wide checkpoint total. The real total, computed
from real per-baseline checkpoint sizes (8 of 12 measured directly from tonight's job output, 4
estimated by architectural analogy) at a 12-stamp, 3-seed, 12-baseline fleet:

    ~28.6 GiB total for the whole fleet's retained checkpoint curve

Smaller than the previously-stated figure, and for an unrelated reason — this project had confused
a per-cell replay-buffer size with a fleet-wide checkpoint total. The conclusion survives (checkpoint
retention is trivial against disk) but the number that supported it was wrong.

C95 still binds *where* evaluation runs: on the production box, or an image matched to it.

## 1. Eval depth and frequency — the recommendation, and the cost that justifies it

Computed for 6e5 × 3 seeds × 12 baselines, 4 regimes × 10 scenes, against 512 job-hours of training:

| stamp grid | episodes/stamp | stamps | eval job-hours | vs training |
|---:|---:|---:|---:|---:|
| 25k | 5 | 25 | 251 | +49% |
| **50k** | **5** | **13** | **130** | **+25%** ← recommended |
| 50k | 10 | 13 | 261 | +51% |
| 100k | 5 | 7 | 70 | +14% |
| 100k | 20 | 7 | 281 | +55% |

**Recommended: a 50k stamp grid, all four regimes, all ten scenes, 5 episodes per cell at
intermediate stamps, 20 at the endpoint. Every episode retained as its own row.**

Two points of reasoning, because the obvious reading of "don't over-aggregate" is the wrong lever:

- **"Not over-aggregated" is about reporting granularity, not episode count.** Five episodes written
  as five rows is richer than fifty written as one mean — the first supports any later aggregation,
  the second supports none. So the requirement is met by *never writing a mean as the primary
  record*, which costs nothing, rather than by buying more episodes.
- **Intermediate points carry shape; the endpoint carries the number.** Noise tolerable in a curve is
  not tolerable in a reported value, which is why depth is spent at the endpoint. And because the
  checkpoints are retained, **any intermediate point can be re-evaluated at greater depth later** —
  the 5-episode choice is reversible, which is exactly why it is the right place to economise.

If +51% is acceptable, 10 episodes at intermediate stamps is strictly better and needs no other change.

## 2. Train-side metrics

Whatever each family already logs, at its native cadence, retained in full — not resampled, not
truncated to the columns we currently plot. These are kilobytes. The families differ (some log per
update, some per episode, `ctrl` through a W&B sink) and that heterogeneity is itself data.

Add, for every family with a stochastic continuous policy, the diagnostics that a finiteness check
cannot catch: `log_std` mean/min/max, vector-level action clip rate, PPO approximate KL, clip
fraction, value explained variance, gradient norm. σ ≈ 4.3 was perfectly finite and useless.

## 3. The cross-scale problem — the owner's "random question", which is not a small one

**`ctrl`'s own default is 25,000,000 frames. Our 6e5 is 2.4% of it.** `idaac` and `ppg` are Procgen
algorithms with similarly long native schedules. So for those baselines a 50k stamp grid does not
sample "early, middle and late training" — **it samples the first 2.4% of the schedule the authors
intended**, thirteen times.

That is not a reason to abandon the grid, but it is a reason to record two axes and never conflate
them:

- **absolute frame stamp** — makes stamps comparable *across* baselines, which is what a common
  protocol needs;
- **fraction of that algorithm's native horizon** — makes a stamp interpretable *within* a baseline,
  which is what a learning-curve claim needs.

Report both per stamp. The same 300k stamp is 50% of `drqv2`'s native Door budget and 1.2% of
`ctrl`'s; a curve that shows them side by side without saying so invites a false reading.

**A concrete instance worth labelling per stamp:** PPG's auxiliary phase first fires at **65,536**
frames, so on a 50k grid the *first* stamp is pre-auxiliary — a PPO checkpoint — and every later one
is PPG. Two adjacent points on that curve are different algorithms. Mark it in the record rather
than leaving it to be rediscovered.

## 4. Retrieval and re-evaluation must be demonstrated, not assumed

The owner asks to be sure we can get checkpoints down and actually launch evaluations with them.
Status: the offline evaluator has been exercised on real checkpoints for **all seven families**
(`rlvigen`, `idaac`, `ctrl`, `ppg`, `ibac_sni`, `dmc_gb`, `alda`); the ALDA cadence probe
`bt1gio1ng14k4o94dpie` returned 15 records. The download path (`result.tgz` plus a separate records
output) is exercised routinely.

**What has not been demonstrated is the full loop at production scale**: train → stamp → retrieve →
*clean-process* reload → full grid → records. That is the canary, and it should be a real production
cell so that passing costs nothing.

Add one cheap universal gate before the fleet, per the third review: for every family, load a
checkpoint in a **fresh process** and confirm the policy's distribution parameters match the live
policy's on fixed observations — comparing distribution parameters, not sampled actions.

## Replay-buffer retention at the end of a run — costed, 2026-09-05

Raised as a question: instead of never saving the replay buffer (today's state, everywhere), save it
once at the terminal checkpoint only, so an interrupted off-policy run could resume as something
closer to an exact continuation, without paying the cost at every intermediate stamp.

**One family already has the code for this.** `alda_trainer.py:54,712` — `save_buffer: bool = False`,
and `if self.save_buffer: self.buffer.save(...)` inside `save_checkpoint()`. It defaults off and no
launch script turns it on. This is not a build task for alda; it is a **config flag**.

For the other six off-policy families (rlvigen's five, dmc_gb's rad/soda) no equivalent exists in the
clones; adding it would mean writing new save/load code against each buffer implementation, not
flipping a flag.

**The cost, using the same per-transition size already measured elsewhere in this project**
(84x84x9 uint8 = 63,504 B/transition, `families.json:102`), at the V100 production replay caps:

| baseline group | cap/baseline | GiB/cell | baselines | x3 seeds |
|---|---:|---:|---:|---:|
| rlvigen five (620k, non-evicting) | 620,000 | 36.66 | 5 | 549.9 GiB |
| dmc_gb two (600k, uncapped) | 600,000 | 35.48 | 2 | 212.9 GiB |
| **total** | | | | **~762.8 GiB** |

That is **~27x the entire checkpoint curve's ~28.6 GiB**, for buffers that would only ever be read
back if a run is actually interrupted mid-training — which is not the expected case (DataSphere jobs
run to completion or timeout; nothing here uses preemptible/spot instances, so there is no routine
eviction to plan around).

**Recommendation: not worth it as a blanket policy.** The production host's disk capacity was never
measured (no `df -h` in `notes/remote-infra.txt`), so 763 GiB is currently uncosted against what is
actually available — that alone is reason enough to not commit to it by default. If the owner wants
insurance against a genuine mid-run failure for a SPECIFIC expensive cell (soda's ~45h projected run
is the obvious candidate — the most to lose from an uncheckpointed interruption), alda's existing
flag is proof the mechanism is cheap where it exists; the other six would need new code, which is
real engineering effort against a risk that has not materialized (no preemption model here) rather
than pre-production hardening.

## Section 2's diagnostics recommendation — checked against real logs, 2026-09-05, corrected once

§2 above recommends, "for every family with a stochastic continuous policy": log_std mean/min/max,
vector-level action clip rate, PPO approximate KL, clip fraction, value explained variance, gradient
norm.

**First pass was wrong about `idaac`, and it is worth recording exactly how.** It checked tonight's
own 10k-frame validation run's CSV, found 4 columns, and concluded idaac was "thin — none of the
recommended diagnostics", parallel to `ctrl`. That conclusion did not survive `docs/PART2-METRIC-
INVENTORY.md` (the project's own metric inventory, which the user recalled existed and asked to be
checked): `idaac` has emitted `train/clip_fraction` and `train/approx_kl_k3` since **2026-08-19**,
"verified against a real run" — `runnable/idaac/train.py:350-352`, guarded by
`getattr(agent, "last_clip_fraction", None) is not None`. The CSV I checked had exactly **one row**,
produced by the terminal-only evaluation path (`finalize_run`), which never includes this block. The
PERIODIC block that does is gated on `log_interval=25` **updates**; a 10k-frame probe with
`num_processes=4, num_steps=256` produces only ~9 updates total, so it never fires. At production
scale (600k frames, ~586 updates) it fires roughly 23 times. **The columns are real; my test
condition just could not have shown them.** Re-checked before writing this correction: `ppg` (6 rows
at this same short scale) and `ibac_sni` (80 rows) both show their rich columns even in the short
probe, confirming their richness was not a similar artifact.

| family | verdict, now properly checked |
|---|---|
| `ppg` | **rich**, confirmed at both short and production scale — PPG's own upstream logger |
| `ibac_sni` | **rich**, confirmed at both short and production scale — upstream's native logger |
| `idaac` | **rich at production scale** (`clip_fraction`, `approx_kl_k3`, wired 2026-08-19); genuinely absent from a short probe for a reason unrelated to whether it is wired |
| `ctrl` | **thin — genuinely, independently confirmed** by `PART2-METRIC-INVENTORY.md`'s own §6: "ctrl is not wired, and this one is structural... its loss is a jitted JAX function, so metrics have to be threaded out of it... should be a decision rather than a default" |

**So the real, remaining gap is `ctrl` alone**, already named and already correctly scoped by this
project's own prior work — not a new finding, and not something needing a new decision surface;
`PART2-METRIC-INVENTORY.md` §6 already states the decision this is waiting on (thread metrics out of
the jitted JAX loss, a real design choice, not a default). Left as a to-do rather than attempted
inline — smaller in scope than first thought (one training loop, not two), but still real work.
