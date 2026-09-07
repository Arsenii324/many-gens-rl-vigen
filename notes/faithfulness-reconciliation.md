# Reconciling `FAITHFULNESS.md`'s divergence table against the clones

Written 2026-09-05. The table is the project's answer to "are the hyperparameters right", and its
summary is tagged **`[MIXED]`** by its own header — so citing it as current (which I did) needed
checking first. This is that check, for the rows rated **high**.

Method: compare the table's claim against (a) the clone's own declared default and (b) what we
**actually execute**, taken from logged `Namespace` lines in real jobs. The project's own rule is
that executed args outrank source defaults, which outrank prose.

---

## The rollout rows: same trajectory length, different effective-batch gaps

| | table says | upstream default | we execute | real divergence |
|---|---|---|---|---|
| **`ppg`** | "rollout **256** vs **65,536**" | 4 MPI × `num_envs=64` × `nstep=256` → **65,536**/global update | 1 × `8 × 256` → **2,048**/global update | **32× smaller effective batch** |
| **`idaac`** | "rollout **256** vs **2048** continuous" | `num_processes=64`, `num_steps=256` → **16,384**/iter | `4 × 256` → **1,024**/iter | **16× fewer parallel envs** |

**In both cases the per-environment rollout length is 256 — exactly upstream's value.** Nothing was
shortened. What differs is the global update: `ppg` runs one MPI worker with 8 environments instead
of four workers with 64 each, while `idaac` runs 4 environments instead of 64.

For **IDAAC**, comparing our per-env rollout to its total batch is a category error: the relevant
gap is 16×, not "256 vs 2048". For **PPG**, 65,536 is the released global batch: the README's
`mpiexec -np 4` combines with `train.py`'s 64 environments and 256 steps. The initial 8× reading
omitted those three MPI workers; its correct effective-batch gap is 32×.

**This changes what the deviation means.** A shortened rollout would alter the credit-assignment
horizon — a real algorithmic change. Fewer workers/environments alters batch diversity and gradient
noise while leaving trajectory length untouched. It is a memory/compute accommodation, but PPG's
32× gap is substantially larger than the initial reading made it appear.

**It may also be closable, which nobody has asked.** Matching PPG exactly requires **four MPI
workers × 64 environments**, while IDAAC requires 64 environments; both are host-capacity questions,
not code changes. The memory figures needed to answer that are already in
`plan_production.ENVELOPE`. **Worth checking before the fleet, because it is far cheaper than
declaring the deviation and defending it.**

## Rows verified as current

- **`svea` — high, CONFIRMED.** `RL-ViGen-upstream/algos/svea.py:12` imports `random_overlay` and
  `:298` applies it as the strong augmentation, where canonical SVEA uses random convolution. Note
  this does *not* affect the anchor: we run their code, so their published 268.8 measures this same
  implementation. It constrains the label only — **"RL-ViGen's SVEA"**.

## Rows that appear superseded

- **`ctrl` — "`L_clust` absent"** looks stale. `loss_cluster` is defined (`algo.py:173`) and its
  gradient is applied (`:558`), after this project restored two lines the authors had commented out —
  as released, `loss_cluster` raised `NameError` on first call and `ctrl_public @ 7a118c8` could not
  run its own algorithm at all. **The second half of that row — positives drawn from the same
  partition rather than a neighbouring one — is UNVERIFIED and may well stand.**

## Executed values recovered, for the record

    idaac      lr 5e-4   gamma 0.999   entropy_coef 0.01   num_processes 4    num_steps 256
    ibac_sni   lr 7e-4   discount 0.99 entropy_coef 0.01   procs 1            frames_per_proc 128

`ibac_sni` at `procs=1, frames_per_proc=128` is **128 transitions per iteration**, which is the
smallest batch in the fleet by a wide margin and is worth its own look — it is the same *class* of
deviation as the two above, and its row is currently rated only **medium**.

## What this says about the table as a whole

Two of five `high` rows are mischaracterised, one is superseded in half, and one is confirmed. The
table is **useful and not reliable** — it points at the right places and its numbers need checking
before being quoted. Any statement that "the parameters are fine" should rest on this reconciliation
rather than on the table, and the reconciliation is not finished: the `medium` and `low` rows have
not been checked.

## Is matching upstream's parallelism affordable? Probably — and the binding constraint is CPU, not GPU

Measured footprints: `ppg` 4.2 GiB RSS / 1588 MiB VRAM; `idaac` 2.9 GiB / 1204 MiB. **VRAM is
irrelevant here** — these models are tiny and 64 environments would not move it much. The cost of
parallel envs is **host RAM and CPU cores**, because robosuite stepping is CPU-bound.

That is very likely why the deviation exists: the DataSphere tiers we developed on have **4 cores
(`gt4.1`) and 8 (`gt4i.1`)**. Running 64 parallel robosuite environments on 4 cores would thrash,
so 8 and 4 were reasonable accommodations *to that hardware*. **Production is different hardware
whose core count we do not know**, which is exactly why this is worth asking rather than assuming.

Two consequences if the production box has the cores:

- **Fidelity**: matching PPG's four-worker × 64-env shape and IDAAC's 64-env shape would remove
  two declared learning-dynamics adaptations rather than leaving them for the write-up.
- **Throughput, possibly**: more parallel envs collect frames faster in wall-clock terms if CPU
  allows, so the fix could *reduce* campaign time rather than add to it. That is speculative until
  measured, and it interacts with the packing analysis in `DECISION-SHEET.md` A13.

**Concretely: establish the production host's core count and RAM.** If it is many-core, first probe
IDAAC at `num_processes=64`; separately probe the released PPG shape of four MPI workers × 64 envs.
Those probes answer the fidelity, throughput and memory questions without silently changing the
production descriptor.

## Second pass — the rows marked FIXED, and `curl`

**`sgqn` — "aux_lr 0.3 vs canonical 3e-4, 1000× on the SHARED ENCODER — FIXED".** Confirmed no
longer catastrophic: `cfgs/sgqn_config.yaml` now reads `aux_lr: 1e-4`. **But "FIXED" is doing more
work than it should** — 1e-4 is RL-ViGen's *global* `lr`, not SGQN's canonical **3e-4**. A **3×
divergence remains**, on the shared encoder, under a label that reads as resolved. It is no longer
critical and it is not gone.

**`curl` — high, CONFIRMED current.** `cfgs/curl_config.yaml`: `lr: 1e-4`, `aux_lr: 1e-4`, against a
canonical **1e-3** — a **10×** divergence on the main learning rate, still live.

**`drqv2` — "stddev schedule from the wrong tier — FIXED".** The old note below records a
historical short/determinism job and must not define production. Fresh Hydra composition of each
active RL-ViGen config with `task@_global_=Door` and the launcher override resolves production to
`stddev_schedule: linear(1.0,0.1,100000)` and `num_seed_frames: 4000`; the value reaches
`agent.stddev_schedule`. The easy preset supplies 100000; the medium preset's 500000 remains a
valid value for a different task tier.

## Standing conclusion after both passes

Of five `high` rows: **two mischaracterised** (`ppg`, `idaac` — parallelism, not rollout length),
**one confirmed** (`svea`), **one confirmed** (`curl`, 10× lr), **one superseded in half** (`ctrl`).
Of the two marked FIXED: **one is fixed but still 3× off canonical** (`sgqn`), **one unverifiable
from static files** (`drqv2`).

**The pattern worth naming: "FIXED" in this table means "no longer catastrophic", not "matches the
reference".** Anyone reading the table for whether we match canonical settings will over-read it.
That is a documentation defect rather than a code one, but it is the kind that produces a confident
wrong claim in a write-up.

## `ctrl`'s `high` row is refuted on BOTH halves

**Half 1 — "`L_clust` absent": false.** `loss_cluster` is defined (`algo.py:173`) and its gradient
applied (`:558`). It was unreachable *as released* — two lines commented out while their result was
still used, so it raised `NameError` on first call — and this project restored the authors' own
lines. Present and wired.

**Half 2 — "positives drawn from the same partition, not a neighbouring one": false.** Traced
through `algo.py:218-252`:

    indx        = top_k(-dist, myow_k+1)   over the PROTOTYPE distance matrix
    indx[:, 0]  = self  (distance 0)
    indx[:, 0+1]= the nearest OTHER prototype        <- skips self by construction
    nearby_cluster_idx = take_along_axis(indx[:, 0+1], cluster_idx)
    nearby_vec_idx     = a random MEMBER of that neighbouring cluster

So a positive is a random member of the **nearest neighbouring cluster**. That is the MYOW
construction, and it is what the row says is missing.

**What is genuinely odd there is upstream's, not ours.** The loop `for k_idx in range(myow_k)` uses
`indx[:, 0 + 1]` — a constant — rather than `indx[:, k_idx + 1]`, so it draws from the **single
nearest** neighbouring cluster `myow_k` times instead of iterating the k nearest. The written form
`0 + 1` rather than `1` suggests a loop variable was intended. **`ext/ctrl_public/algo.py:222`
contains the identical line**, so we reproduce upstream faithfully; the diversity of the MYOW term
is lower than the k-neighbour formulation implies, and that is CTRL's own behaviour.

**Consequence: `ctrl`'s `high` rating rests on two claims that are both false against the current
code.** Its real, recordable deviations are elsewhere — the restored lines (a repair, without which
the algorithm cannot run at all) and this upstream neighbour-index quirk (faithfully preserved).

## Historical diagnostic composition — superseded by active Door composition

`det3/drqv2_a/.hydra/config.yaml` (an actual run, so this outranks the template):

    stddev_schedule: linear(1.0, 0.1, 100000)      nstep: 3    lr: 1e-4    batch_size: 256
    num_seed_frames: 600        <- explicit short/determinism probe override

This diagnostic proves only that an explicit short job can compose 600; it does not override the
active production launcher. The active Door composition independently proves the production values
above. Preserve this block as historical evidence, but do not cite it as a production uncertainty.

---

# CORRECTION from the fourth external review — my `ppg` figure was wrong, and the synthesis is bigger

## I said 8×. It is 32×, and I missed the reason

I wrote that `ppg`'s "65,536" was unsourceable and the real divergence was **8×** (8 envs vs 64).
**Wrong — I missed the MPI dimension entirely.** `ppg/train.py:2` and `ppg.py:10,252` use
`mpi4py`, `comm = MPI.COMM_WORLD`; upstream's documented invocation is **4 MPI processes × 64 envs
× 256 steps = 65,536** global interactions per update. Ours is `1 × 8 × 256 = 2,048`. **32×**, and
`FAITHFULNESS.md`'s figure was right all along.

**And the consequence reframes a finding I presented as reassuring.** `n_pi=32` was not rescaled, so
the auxiliary phase now fires every `32 × 2,048 = 65,536` frames instead of upstream's
`32 × 65,536 ≈ 2.1M`. My earlier "PPG gets nine auxiliary phases at 6e5, so 6e5 is enough" is
therefore **not evidence of fidelity — it is a symptom of the rescaling**. The auxiliary phase is
~32× more frequent in sample terms than the source configuration implies.

## A second learning-affecting adaptation, across five baselines at once

**[UPDATED 2026-09-05: 300,000 remains the DataSphere-safe base, but the `v100` host profile
now resolves replay to **620,000**, which is non-evicting at a 600k budget and therefore
removes this deviation entirely on the production host. The row below describes the
DataSphere configuration.]**

`families.json:90` caps replay at **300,000** against a source ~1,000,000, with the reason recorded
honestly: uncapped is 38.8 GiB of worker-resident replay at 600k and **no allowed tier holds it**
(`gt4i.1` gives ~27 GiB); at 300k a cell is 21.0 GiB. In a **600k** experiment a 1M buffer retains
the whole run while 300k **evicts the first half** — a different sampling distribution for `drqv2`,
`drq`, `svea`, `sgqn` and `curl`.

**And a third instrument is wrong about it.** `audit_comparability_seam.py:654-655` emits
`"uniform over the whole run | {cap} nominal, disk-backed, exceeds 6e5"` whenever a capacity is
present — **without comparing it to 6e5**. At the production cap of 300,000 both clauses are false:
it is neither uniform over the run nor in excess of the budget.

## The synthesis, and it is the actionable part

**Three of the project's most consequential fidelity deviations exist because of DataSphere's tier
limits, and production is no longer on DataSphere.**

| deviation | forced by | source value | might be closable? |
|---|---|---|---|
| `ppg` 8 envs, 1 process | 4–8 cores | 4 MPI × 64 envs | **if the box is many-core** |
| `idaac` 4 processes | 4–8 cores | 64 processes | **if the box is many-core** |
| rlvigen five: 300k replay | 27 GiB RAM ceiling | ~1M (38.8 GiB) | **if the box has ~40+ GiB** |

The owner has said production is **another V100 with Docker and a Linux environment of our choice**.
So all three may simply dissolve — deleting two `high` fidelity ratings and one learning-affecting
adaptation that touches five baselines, at the cost of asking two questions about the host.

**What to ask for, concretely: core count and RAM.** With ~40 GiB and many cores, the production
configuration can be materially *more* faithful than anything measured so far, and several of the
write-up's limitations disappear rather than needing defending. This is the highest-leverage
unanswered question in the project, and it is a question, not an experiment.

## VERIFIED: all four on-policy imports run at reduced parallelism, and five more carry a replay cap

Checked against each clone's own declared default (fourth review, section B — I verified each):

| baseline | source default | production | reduction | evidence |
|---|---|---|---:|---|
| `ppg` | 4 MPI × 64 envs × 256 | 1 × 8 × 256 | **32×** | `README.md:34` (`mpiexec -np 4`), `train.py:27,131` |
| `idaac` | 64 processes × 256 | 4 × 256 | **16×** | `arguments.py:62-67` defaults |
| `ibac_sni` | 16 procs × 128 | 1 × 128 | **16×** | `scripts/train.py:41` (`--procs` default 16) |
| `ctrl` | 64 envs | 16 envs | **4×** | `train_ppo.py:86` (`num_envs` default 64) |

Plus the RL-ViGen five at a **300k replay cap against ~1M source**.

**So nine of twelve baselines carry a resource-forced learning-dynamics adaptation**, and every one
of them was forced by DataSphere's 4–8 cores and 27 GiB ceiling. For synchronous on-policy methods
the environment count is not a throughput knob: it sets the on-policy batch distribution and the
update cadence per collected frame.

**This makes the production-host question the single highest-leverage item in the project.** With
many cores and ~40+ GiB, most of this table could simply close — turning nine declared
learning-affecting adaptations into a configuration that matches the sources. It is one question
about the box, and it is worth asking before anything else is scheduled.

## A third wrong row — and I nearly retracted a valid result on the strength of it

`FAITHFULNESS.md:145` records **reward shaping** as:

> never stated [in the paper] … `True` … **CONFIRMED ABSENT from the paper** … Ours is `[OURS]`,
> inherited from robosuite's default via the SECANT lineage, and it is what makes a random arm score
> ~7.5 on `Lift`.

**`[OURS]` is wrong.** RL-ViGen's own `envs/robosuiteVGB/cfg/robo_config.yaml` contains
`reward_shaping: true`. It is *their* setting; we match it. "Absent from the paper" is true and
separate — the paper not stating it does not make the code ours.

**Why this mattered more than a mis-tag.** Reading that row, I concluded our Door returns might be
on a shaped scale while RL-ViGen's published numbers were not — which would have meant the T3 anchor
compares different quantities, exactly the C45/C47 failure, and I was about to withdraw the anchor
recommendation. Checking their config instead of trusting the row reversed that: **the scales agree
and the anchor stands.**

The supporting evidence for the anomaly that started this — their published `lift` values of 0–3
against our ~7.5 random floor — remains **unexplained**, but Lift is not the scoped task. Recorded in
`OPEN-QUESTIONS.md` rather than resolved.

**Running tally for this table: three `high` rows mischaracterised or wrong (`ppg`, `idaac`,
reward-shaping's provenance tag), one superseded in half (`ctrl`), two confirmed (`svea`, `curl`),
one "FIXED" that is still 3× off canonical (`sgqn`), one unverifiable statically (`drqv2`).** It
points at the right places and its specifics need checking before any of them is quoted.
