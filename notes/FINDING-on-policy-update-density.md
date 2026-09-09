# The four on-policy families' regular-phase update density versus their Procgen source

> ## SUPERSEDED FOR `idaac`, 2026-09-06 — and the finding is VOID, not merely restated
>
> Every `idaac` row below is computed from `16 x 256 = 4096` with `1 x 8` epochs x minibatches.
> **That configuration no longer exists.** DECISION-SHEET **A35 / Q55** (commit `15b4e73`,
> 2026-09-06) replaced the Procgen-derived IDAAC-P recipe wholesale with the authors' own DMC
> continuous-control recipe, every constant confirmed directly against
> `ext/idaac/raileanu21a-supp.pdf` §E: `num_processes` **1**, `num_steps` **2048**,
> `num_mini_batch` **32**, `ppo_epoch` **10**, γ **0.99**, `entropy_coef` **0**, `lr` **3e-4**,
> `value_freq` **32**, `adv_loss_coef`/`order_loss_coef` **0.1**, frame stack **3**. The `v100`
> host-profile override that raised processes to 16 was **removed**.
>
> **Why the finding is void rather than re-derivable.** It measured a *divergence from upstream
> parallelism* — 4x the update density because we ran fewer environments than the Procgen
> reference's 64. Under C2 the reference is no longer Procgen: it is the authors' DMC recipe, whose
> own rollout is **1 process x 2048 steps**, which is exactly what we now run. Executed and
> reference update density are `10 x 32 / 2048 = 0.15625` grad steps per env frame in both cases.
> **The ratio is 1x.** There is no idaac parallelism divergence left to report.
>
> The rows for `ibac_sni` and `ctrl` are untouched by A35 and stand as written.
>
> ## ALSO SUPERSEDED FOR `ppg`, found 2026-09-09 — same shape, two days later
>
> The line above originally read "the rows for `ppg`, `ibac_sni` and the others … stand as written".
> **The `ppg` row does not.** It is computed from `8 x 256 = 2048` with `1 x 8` minibatches, which is
> the **pre-A36** configuration. **A36 (2026-09-07) changed `ppg` to `num_envs 1 x nstep 2048` with
> `nminibatch 32`**, adopting `raileanu21a-supp.pdf` §E for the same reason A35 changed `idaac` —
> two days after this note was written, and the note was not revisited.
>
> Recomputed under the declared A36 configuration: `1 x 32 = 32` grad steps over a 2048 rollout is
> **0.015625** steps per env frame, against PPG's released 1-rank **0.000488** — a **32x** ratio,
> not the 8x/32x recorded below, and arrived at by a different mechanism (minibatch count, not
> rollout size).
>
> **And the EXECUTED density is a third number again.** `minibatch_optimize` splits on the batch
> axis, so `num_envs=1` clamps `nminibatch` 32 → 1 (logged 291 times as
> `Warning: nminibatch > ntrain!! (32 > 1)`), giving **0.000488** steps per env frame — *exactly*
> PPG's released density, by accident. See
> [`ppg-took-256-gradient-steps-not-8192.md`](ppg-took-256-gradient-steps-not-8192.md).
>
> So this note's own method — grad steps per env frame, read from the executed entry point — is
> still right, and applying it to `ppg` today gives **declared 0.015625, executed 0.000488,
> upstream 0.000488**. Do not quote the `ppg` number below either.
>
> Left in place rather than deleted: the arithmetic is still the right method, and a note that
> quietly vanished would take its reasoning with it. But do not quote an `idaac` number from below.


Found 2026-09-05 in the full-project audit, extending the same question already asked of the
off-policy families (`FINDING-update-to-data-ratio.md`, A27, corrected after review 14): not "what
does one unit of the x-axis mean" but "how much learning happens per unit". PPG's AUXILIARY-phase
cadence was already found and fixed today (A26) — this is the separate, previously unexamined
question of the REGULAR PPO-phase update rate, for all four on-policy families.

## The mechanism

An on-policy update takes `epochs x minibatches` gradient steps per collected rollout of
`num_envs x num_steps` transitions. Holding `epochs` and `minibatches` fixed while `num_envs` shrinks
(because a single V100 cannot run Procgen's ~64 cheap procedurally-generated envs' worth of parallel
*robosuite/MuJoCo* environments) multiplies the update density by exactly the ratio of rollout sizes
— the identical shape as the off-policy `action_repeat` case, mechanism substituted.

## The measurement, verified against the executed entry point in each case

| family | production rollout (`num_envs x num_steps`) | epochs x minibatches | grad steps / env frame | upstream rollout | upstream grad steps / env frame | ratio |
|---|---:|---:|---:|---:|---:|---:|
| `idaac` (policy+aux head) | 16 x 256 = 4096 | 1 x 8 = 8 | 0.00195 | 64 x 256 = 16384 | 0.000488 | **4x** |
| `idaac` (value head, separate optimizer) | 4096 | 9 x 8 = 72 | 0.01758 | 16384 | 0.004395 | **4x** |
| `ppg` (regular PPO phase) | 8 x 256 = 2048 | 1 x 8 = 8 | 0.00391 | 16384 (1-rank) / 65536 (4-rank MPI) | 0.000488 / 0.000122 | **8x / 32x** |
| `ibac_sni` (target `procs=16` profile) | 16 x 128 = 2048 | 4 x 8 = 32 | 0.015625 | 16 x 128 = 2048 (both are upstream's own defaults) | 0.015625 | **1x — exact match** |
| `ctrl` (V100 profile, `num_envs=64`) | 64 x 256 = 16384 | 3 x 8 = 24 | 0.001465 | 64 x 256 = 16384 (upstream default) | 0.001465 | **1x — exact match** |

Every non-1x number above comes from an UNOVERRIDDEN upstream default colliding with a SMALLER
`num_envs` than Procgen's own default — none of `ppo_epoch`, `num_mini_batch`, `value_epoch`,
`n_epoch_pi`, `nminibatch` are touched by this project's launchers or descriptors. Evidence, all
read from the executed entry point, not a callee's own internal default (PPG's `nminibatch` needed
this distinction: `ppo.py`'s function signature defaults to 4, but `train.py:33` — the actual CLI
entry point our launcher calls — defaults to 8, and that is the value that executes):

- idaac: `ppo_daac_idaac/arguments.py:62-64,72-79,134-136`; `algo/idaac.py:60,76,94,132`;
  `families.json` idaac constants/host_profiles.v100 (`num_processes` 4 base / 16 v100, vs upstream **[SUPERSEDED 2026-09-06: `host_profiles.v100` no longer exists on idaac; `num_processes` is 1.]**
  default 64).
- ppg: `phasic_policy_gradient/train.py:27-38`; `ppo.py:168-170`; `families.json` ppg
  constants (`num_envs: 8`, A26-reverted) vs upstream default 64 (single rank) / 4-rank MPI.
- ibac_sni: `torch_rl/scripts/train.py:53,67,87-91` (`--procs` default **16**, `--frames-per-proc`
  default **128** for PPO, `--batch-size` default 256, `--epochs` default 4 — all four are upstream
  defaults, none overridden); `families.json` ibac_sni constants (`procs: 1` base is a DataSphere
  memory accommodation, not the target; `host_profiles.v100.constants.procs: 16` restores the
  upstream default exactly).
- ctrl: `train_ppo.py:94,101-104,118` (`num_envs` default 64, `n_steps` 256, `n_minibatch` 8,
  `epoch_ppo` 3); `families.json` ctrl constants (`num_envs: 16` base, DataSphere memory
  accommodation) and `host_profiles.v100.constants.num_envs: 64` — restoring the upstream default
  exactly, already fixed and gated (`gate_ctrl_v100_profile_restored`) earlier this session.

## Why two of four already match exactly, and it is not luck

`ibac_sni` and `ctrl` match upstream exactly on the V100 profile **because their V100 host profiles
were already built to restore the full upstream `num_envs`** — ctrl explicitly (measured 13.57 GiB
at 16 envs, 113 GiB host, restore 64), ibac_sni structurally (16 was always the upstream default;
`procs=1` is the DataSphere-memory accommodation, not a chosen production value, and is gated behind
a real smoke before it may launch). `idaac` and `ppg` have no such V100 restoration: idaac's V100
profile only raises `num_processes` to 16, still a quarter of Procgen's 64, and `ppg`'s A26 fix **[SUPERSEDED 2026-09-06: that profile was removed; idaac runs 1 process, which IS the DMC reference.]**
deliberately kept `num_envs` at 8 to preserve its AUXILIARY-phase cadence — which is the right call
for that axis, and this finding is what it costs on this one.

## What this means, and what I recommend

This is the same shape as A26/A27: real, verified, and **not obviously wrong** — a single V100
genuinely cannot run 64 parallel robosuite/MuJoCo environments the way Procgen's cheap 2D levels
allow, so *some* deviation from Procgen's parallelism is forced by hardware, exactly as *some*
retiming of PPG's auxiliary phase was forced by the 600k budget. The question is only whether it is
declared.

**It is not declared anywhere today.** `updates_per_env_frame()` in `audit_comparability_seam.py`
currently reports `"n/a on-policy"` for all four on-policy families — correct for the *replay-ratio*
sense that function was built for, but it means no comparability axis currently surfaces this
number at all.

**Recommended: extend `updates_per_env_frame()` with these real numbers rather than `n/a`,** and
raise idaac's and ppg's regular-phase density as a declared design-point limitation alongside their
already-declared Procgen-vs-continuous-control geometry limitation (review 11 §7/§8, T16/T17).
**Not recommended: compensating by raising `num_mini_batch`/`ppo_epoch` to force a 1x match** — that
would be inventing a new hyperparameter combination nobody validated, the same reasoning this
project already applied when it declined to equalise the off-policy ratio.

Filed as **A29** rather than applied silently, since it touches idaac and ppg's effective learning
rate per unit of collected experience — method-defining, not a bookkeeping fix.
