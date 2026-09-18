# What a production cell actually costs in wall-clock — eval, not training, dominates

**2026-09-18.** Written after giving the owner a wrong number with false confidence (**"the
endpoint grid is 96s end to end"**) and being pushed to check it. The retraction and the real
numbers are both worth keeping, because the wrong number came from citing a comment out of its
context rather than checking what it actually measured — exactly the failure mode this project's
own register exists to catch, and it got past me once before it got caught here.

## The retraction

`run_probe.sh`'s stall-watchdog comment says the endpoint eval grid is 96s, citing job
`bt1utl06n6mqffrt2jdn`. That job's config (`cfg-rlvigen-attest-v205.yaml`) is an **attestation-scale**
cell: `ENDPOINT_EVAL_REGIMES=train,eval-easy` (2 regimes), `ENDPOINT_EVAL_SCENES=0` (1 scene),
`ENDPOINT_EVAL_EPISODES=5` — **10 episodes total**. Production runs 4 regimes × 10 scenes × 20
episodes = **800 episodes**, 80x more. The 96s figure is real, for what it measured; it is not
"the endpoint grid" at production scale, and citing it as such without checking the config behind
the job ID was the actual mistake.

## The real numbers, from a real completed production cell

`idaac` s102 (`card1-20260916-213222`), read directly from `native-out/job.log`'s own printed
markers and file mtimes — nothing here is an estimate except where marked:

| phase | measurement | source |
|---|---|---|
| Training, full 600k | **≈7.46 h** (extrapolated: 6.21h measured across checkpoints at frames 51,200→550,912, scaled to 600k) | checkpoint file mtimes |
| Curve eval, 11 stamps | **≈6.76 h** | training-end mtime to first `NATIVE_ENDPOINT_EVAL_BEGIN` epoch |
| Endpoint eval, native mode | **12,881 s = 3.58 h** | `NATIVE_ENDPOINT_EVAL_SECONDS 12881 policy_mode=native` |
| Endpoint eval, mode-mode | **11,788 s = 3.27 h** | `NATIVE_ENDPOINT_EVAL_SECONDS 11788 policy_mode=mode` |
| **Eval total (curve + both endpoint passes)** | **≈13.6 h** | sum of the three measured lines above |

**Evaluation costs roughly double the training time on this cell** (13.6h eval vs ~7.46h training).
This is not a marginal overhead; for scheduling and windowing purposes, a "training run" on this
host actually means training-plus-eval, and the eval half is the larger half. `run_probe.sh`'s own
watch-budget arithmetic already accounts for an eval allowance separately from the training
timeout — this note is the measured number behind that allowance, not a new requirement.

**What this does not show:** these numbers are from one `idaac` cell. `ibac_sni` and `ppg` have
different episode/regime counts per policy mode (`ibac_sni` has no `mode` estimand split; `ppg`'s
`ENDPOINT_EVAL_POLICY_MODES=native` only, per `family.py production-env`), so their eval cost is
not directly this number — re-derive per family from its own `job.log` before relying on it.

## The ppg checkpoint-cadence correction, same session

Separately corrected after being pushed on the same kind of claim: ppg's real save cadence is
**not** the `ic_per_save=100_000` default I first cited, and not a clean 50k either. The actual
mechanism, found at `runnable/ppg/phasic_policy_gradient/ppo.py:188`:

    ic_per_step = venv.num * comm.size * nstep

This product (empirically 25 × 2048 = 51,200 in the production run) is what
`LogSaveHelper.__call__` adds to its running total every logging step; `rcm()` then checks whether
that step's window crossed a multiple of the **separate** `ic_per_save` threshold (100,000). Two
uncoordinated numbers combine via modular arithmetic to produce the observed cadence: real saves
from the actual production `ppg` run land at `IC=0, 51200, 100352, 151552, 200704, 251904...` —
essentially every rollout, not every 100k and not a configured 50k. **Why a keyword search for
"save"/"cadence"/`SAVE_EVERY_FRAMES` never finds this:** the controlling line (`ppo.py:188`) is
about interaction-count bookkeeping, not saving, on its face — it only gates a save two calls
later, in a different file, via `rcm()`'s boundary check. This is left as-is; the owner asked
explicitly not to change ppg's rollout quantum.
