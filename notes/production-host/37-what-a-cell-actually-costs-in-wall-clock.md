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

## The ppg checkpoint-cadence correction — retracted and redone twice, now checked against the real argv

This section was wrong **twice** before it was right, and both wrong versions are worth naming
because the failure mode was the same both times: reading code that describes a *default* or a
*historical* state, instead of reading the actual executed argv.

**First claim (wrong): "ppg saves every 100,000 interactions, the code default, never overridden."**
Sourced from `log_save_helper.py`'s `ic_per_save: ... = 100_000` default and from `grep`ing
`runnable/_launch/ppg*.sh` for `SAVE_EVERY_FRAMES`/`ic_per_save` and finding nothing. Both facts
were real; the conclusion was not, because the actual wiring happens somewhere neither of those
greps could see: `families.json`'s **templated options list** for `ppg`
(`"--ic_per_save", "{save_every}"`), substituted by `family.py` before `ppg_cell.sh` ever runs.
`families.json` itself even names this exact mistake as a *historical* fact, not a current one —
its own `save_every_reason` comment (dated 2026-09-04) reads: *"Previously: C60 records ppg as
never saving: ic_per_save is never set by any launcher"* — i.e. I re-asserted a defect that this
project's own commit history had already closed two weeks earlier, because I checked the shell
launchers and never checked the JSON template layer that actually substitutes into them.

**Second claim (also wrong, in the retraction above): "not every 100k and not a configured 50k
either — it's whatever the rollout quantum happens to produce."** Half right: the rollout quantum
*is* what produces the observed spacing. But **50,000 is explicitly configured** — confirmed by
reading the real executed argv from a completed production cell
(`card0-20260909-115331/native-out/cells/ppg-s1/effective_config.json`), which contains literally
`"--ic_per_save", "50000"`. It is not left at the code's 100,000 default; `family.py` sets it to
50,000 on purpose, to match the other families' ~50k cadence.

**The actual mechanism, now fully reconciled, both halves confirmed from the real run:**

    ic_per_step = venv.num * comm.size * nstep     # ppo.py:188 -- the MPI-rollout quantum
    ic_per_save = 50000                            # families.json's "{save_every}" template, confirmed in the real argv

`ic_per_step` is empirically **51,200** in production (an MPI rollout of `nstep=2048` across
`comm.size=25` workers — `25` is the `mpirun` worker count, not a Python argv value, which is why
grepping the JSON config for it found nothing either). Because the rollout quantum (51,200)
**exceeds** the configured save threshold (50,000), `rcm()`'s boundary check finds at least one
multiple of 50,000 inside every single logging window — so a save fires on **every rollout**, not
once every two as the raw ratio might suggest. That is why the real observed saves
(`IC=0, 51200, 100352, 151552, 200704, 251904...`) look like "every ~51k," even though the
configured number is 50,000: the configured threshold is real and intentional, and the *reason it
doesn't produce clean 50k-spaced saves* is that it is smaller than the step size that tests it.

**Why a keyword search for "save"/"cadence"/`SAVE_EVERY_FRAMES` misses all of this:** the value
lives in a JSON *template string* (`families.json`), not a shell variable; the quantity that
determines the *spacing* between saves (`ic_per_step`) lives in a completely different file
(`ppo.py:188`) under a name that has nothing to do with saving on its face; and the number that
looked authoritative from the source code (`100_000`, the class default) is simply not the value
in force. Three independent places have to agree before a claim like "ppg saves every N" is
checkable at all, and the fastest way to get it right is what closed it here: read the **real
executed argv** of a completed run, not the source, not a shell launcher, not a config template in
isolation. This is left as-is; the owner asked explicitly not to change ppg's rollout quantum.
