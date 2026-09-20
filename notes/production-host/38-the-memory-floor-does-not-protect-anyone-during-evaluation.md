# 38 — The memory floor does not protect anyone during evaluation

Written 2026-09-20 by Claude, the evening it was observed. Status: **OBSERVED on the host and
CONFIRMED in the code; NOT FIXED.**

## What happened

`drqv2` s101 (`card0-20260920-094616`) finished training at about 15:15 MSK and went into its
evaluation grid on card 0. At 16:56 a labmate's job — a bare host process, in no container — took
about 26 GiB of that card. Free memory fell to **1,905 MiB, under the 4,000 MiB floor**.

The host-side observer did its part. `native-work/yield.sentinel`, written at 16:57:01:

    yielded at 1789912622: free memory 1905 MiB is below the 4000 MiB floor
    free_mib=1905 procs=2 util=100

**The cell did not yield.** It kept evaluating for 50 minutes, on a card it had been told to leave,
until I stopped it by hand at 17:46 for a different reason (the owner's wish to defer deferrable
evaluation). Its log contains no `NATIVE_CELL_YIELDED`. Nothing announced the failure; I found it
only because the observer's container was missing from `docker ps` and I asked why.

## Why

The sentinel is read by a poller that lives **inside `run_measured()`** in
`datasphere/native/run_probe.sh` and loops `while kill -0 "$training_pid"` — it exists only while
the TRAINING process does, and what it kills is the training process group. Curve and endpoint
evaluation run after `run_measured` returns, outside it. For the whole evaluation phase nothing
reads the sentinel.

The observer, for its part, writes the sentinel once and exits. It does not check that anything
happened, does not retry, and has no fallback (`neighbour-yield.sh`'s optional `docker stop` is
disarmed — `notes/model/STOP-MECHANISMS.md`).

Evaluation is the larger part of a cell's life: 10.1 h of 15.1 h for the measured `idaac` cell,
about 8 h after 5.2 h of training for `drqv2`.

## What this falsifies

- `notes/model/HARNESS-MODEL.md` §5: "**The memory floor is never waived.**" It is not waived; it
  is inert for most of the run, which is worse because it reads as protection.
- Every earlier firing of the floor yield that the docs cite as evidence it works
  (`ibac_sni` s102, twice) happened during TRAINING. No document records it firing during
  evaluation, and it cannot have.
- The vacancy arithmetic in `CURRENT-STATE-AND-RESPONSIBILITY.md` ("one cell survives the
  co-tenant's return with 6,647 MiB free") assumes a cell that gives way when it must. During
  evaluation it will not.

## The mitigating fact, stated so it is not mistaken for a defence

An evaluating cell holds little VRAM (841 MiB measured for `idaac`; `drqv2`'s evaluation left the
labmate's job its 26 GiB). Nobody was OOMed. The labmate arrived on a card that was nearly empty
and got what they asked for. The defect is that the mechanism we rely on to guarantee that did
nothing, and we did not know.

## Until it is fixed

Treat a cell in its evaluation phase as having NO automatic yield. If a co-tenant appears on its
card, stop it by hand, by exact container name (`OPERATOR-GUIDE.md` §6b) — its checkpoints are
already retained and the evaluation can be re-run from them.

## The fix (not made; belongs with the timeout redesign, `ACCOUNTABILITY.md` H3)

The sentinel poll has to cover the cell's whole life, not `run_measured`'s: one poller started when
the cell begins and stopped when it ends, which terminates whatever phase is running and prints
`NATIVE_CELL_YIELDED` with the phase named. `run_probe.sh` is outside the evaluator closure, so
this does not touch an attestation. It needs a test that writes the sentinel during a stubbed
evaluation phase and sees the cell stop — red against today's script.
