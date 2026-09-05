# Update/data accounting is an undeclared axis; do not confuse replay ratio with physics-step ratio

Found 2026-09-05 during the full-project audit, by asking a question none of the sixteen tracked
comparability axes asks: **not "what does one unit on the x-axis mean" but "how much learning
happens per unit".**

`scripts/audit_comparability_seam.py`'s `AXES` list tracks sixteen axes including `x-axis
accounting`, which correctly establishes that all twelve baselines count **environment
transitions** and that the unit is genuinely common. It does not ask how many gradient updates each
family performs per transition. Nothing else does either — searched `docs/` and `notes/` first, per
that file's own standing instruction after the crop-policy axis sat documented and unnoticed for
eighteen days.

## The measurement

Every number below is read from the executing tree, not from a document. Review 14 corrected the
important denominator error in the first version of this note: an action-repeat transition is one
replay item, even when it represents several low-level simulator substeps.

| family | learner updates per newly collected replay transition, OURS | source design point | separate physics-step context |
|---|---:|---:|---:|
| `drqv2 svea drq sgqn curl` | **0.5** — `update_every_steps: 2` (`cfgs/config.yaml:46`), Door `action_repeat=1` | about 1 update per new replay transition in the RL-ViGen source loop | source and Door both represent one simulator step per stored transition |
| `rad soda` | **1.0** — one `agent.update` per step (`dmc_gb/src/train.py:191-194`); Door path's effective repeat is 1 | about 1 update per new replay transition; source repeat 4 | source transition spans four simulator substeps; Door transition spans one |
| `alda` | **1.0** — one update after warmup (`alda_trainer.py:649`); Door path's effective repeat is 1 | about 1 update per new replay transition; source specs use repeat 4 | source transition spans four simulator substeps; Door transition spans one |

The four on-policy families (`idaac`, `ppg`, `ibac_sni`, `ctrl`) do not have a per-step replay
ratio; their analogue is epochs x minibatches per rollout and is a separate row, not filled here.

The protocol choice still creates a real *physics-time* condition difference: this project uses
`action_repeat=1` on Door, while RAD/SODA/ALDA source configurations use 4. That is appropriate
for the Door task and is disclosed as a design-point condition, but it is not a reason to divide
learner updates by four. The stored-data ratio and the simulator-substep ratio are different axes.

## Two consequences, of different severity

### 1. A cross-family confound at the common budget — undeclared

At the common 600k-frame budget the five RL-ViGen baselines take **~300k gradient updates** while
`rad`, `soda` and `alda` take **~600k**. A benchmark whose purpose is ranking algorithms at a
common budget is therefore holding the transition axis common while allowing a 2x difference in
learner updates between families. That is a legitimate faithful-source design choice, but it is
currently **undeclared**, and the report must expose it rather than imply equal optimization.

This belongs in `audit_comparability_seam.py` as a seventeenth axis and in the report's caveats.

### 2. `alda` still carries a stability risk, but the old evidence does not prove a faithful 0.25
setting

`docs/FAITHFULNESS.md:603-616` records, as measurement rather than argument:

> `utd=1.0` diverged 3 Lift runs across 2 seeds by ~141k frames (`critic/loss > 1e8`, Q above the
> reward ceiling, policy entropy collapsing negative); `utd=0.25` cleared 220k on both seeds with
> `critic/loss` in `[0.46, 0.68]`.

It was fixed to `0.25` and pinned by two red-green tests. **Both tests protect a code path
production does not run.** `tests/test_sweep_gaps.py:710,718` import `from rlgen import registry`
and assert on `AldaConfig().utd` — the **retired** `rlgen/algos/alda` port. Production launches
`runnable/alda` (`families.json:376-377`), which has **no `utd` field at all**: the update count is
the literal `1` on `alda_trainer.py:649`.

So the lesson was learned, written down, tested, and then not carried into the clone that will
actually run. This remains a stability risk, but it is not evidence that the production replay
ratio is four times the source ratio: the source transition and the Door transition are each one
replay item.

**Calibration, stated honestly.** What is *proven* for our exact setup: the current Door path
performs one learner update per newly collected replay transition. What is *not* proven: that
`runnable/alda` on Door will diverge.
The divergence evidence is from **Lift**, in a sibling project, through the **retired** port. It is
a strong prior on a different task, not a result for this one. But the divergence appeared at ~141k
frames, well inside our 600k budget, and the direction of risk is one-sided: the faithful value is
also the safe one.

## What I recommend, and what I did

**Recommended default for now: keep the current one update per newly collected Door transition,
and run a target-specific ALDA sensitivity probe at 1.0 versus 0.25 before the fleet.** If 0.25 is
needed for stability on Door, record it as a target-specific adaptation, not as restoration of
the source replay ratio. The old Lift/retired-port result is a strong stability prior, not a Door
fidelity proof.

**Not applied unilaterally.** Unlike the PPG cadence fix earlier today — where the base config was
already correct and only an unreasoned override had broken it — here there is no already-correct
base to restore, the change alters a training loop rather than reverting a profile, and it changes
`rad`/`soda`/`alda` results materially. It is a **method-defining value**, which this project's own
triage says closes "only after its default is researched, implemented, and still surfaced for owner
ratification". Raised as **A27**.

**The counter-argument, stated fairly.** The previous note treated simulator frames as if they
were replay samples and therefore called 1.0 a 4x source replay ratio. That was wrong. The remaining
argument for testing 0.25 is empirical stability on a different task/port, not source fidelity.

For reporting, retain both quantities: learner updates per newly collected replay transition, and
simulator substeps per transition. Do not collapse them into one UTD column.

## The class, not just the instance

The general failure is that **a fix can be pinned by a test that does not cover the code that
runs.** Both `utd` tests are real, both are red-green verified, and both are useless here. The
same shape could hide anywhere the project migrated from `rlgen/algos/*` to `runnable/*` and left
the old tests in place.

`scripts/audit_implementations.py` and `tests/test_inventory.py` exist; neither asks "does the test
that pins this value import the module production launches". That check is worth building, and is
filed in NEXT-ACTIONS rather than built inside this finding.
