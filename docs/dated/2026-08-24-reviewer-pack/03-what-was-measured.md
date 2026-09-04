# What has actually been measured

**Written 2026-08-24. Dated snapshot, not a living document.** Every number here was re-derived from
`results/regime-retention/*.json` for this document rather than copied from prose. Where a figure
differs from what another project document states, that is flagged.

This is the file to attack. Everything else in the pack is context for it.

## 1. The complete inventory

Eight paired grids exist. That is all the evaluation evidence this project has. Every one is
**Door**, `action_repeat=1`, **20 episodes per scene across 10 scenes = 200 episodes per regime**,
episode seed 0, within-scene control seed 1.

| grid | baseline | frames | train mean | train succ | eval-easy mean | eval-easy succ | ratio |
|---|---|---|---|---|---|---|---|
| `cell55k` | `drqv2` seed 6 | 50k | 115.31 | **59/200** | 3.49 | 0/200 | 0.030 |
| `cell_drqv2_s7` | `drqv2` seed 7 | 50k | 85.01 | 0/200 | 15.00 | 1/200 | 0.176 |
| `cell_drq_s1` | `drq` seed 1 | 50k | 79.29 | 0/200 | 22.18 | 1/200 | 0.280 |
| `cell_svea_s1` | `svea` seed 1 | 50k | 97.50 | 6/200 | 85.51 | 3/200 | 0.877 |
| `random-floor` | *none — control* | 0 | 1.82 | 0/200 | 1.85 | 0/200 | 1.020 |
| `snapshot_50k_frames` | `drqv2` archived | 50k | 24.75 | 1/200 | 46.71 | 4/200 | 1.887 |
| `snapshot_100k_frames` | `drqv2` archived | 100k | 52.16 | 28/200 | 131.05 | 63/200 | 2.513 |
| `snapshot` | `drqv2` archived | 100k | 51.94 | 19/200 | 144.72 | 62/200 | 2.786 |

**MEASURED**, all of it. Three distinct baselines appear: `drqv2`, `drq`, `svea`. The bottom three
rows are three checkpoints of *one* archived run, not three runs.

## 2. The accidental replicate, and why it is the most important row here

**`snapshot` and `snapshot_100k_frames` are the same checkpoint.** Byte-identical:

```
md5  snapshot.pt              = ec21f9a30da07ca94d0511cc85be5baf
md5  snapshot_100k_frames.pt  = ec21f9a30da07ca94d0511cc85be5baf
```

Every protocol field in both JSON pairs is identical — `task: Door`, `trained_step: 100000`,
`action_repeat: 1`, `episodes: 20`, `seed: 0`, `control_seed: 1`, same ten scenes, same mode. The
two grids were run at different times under different filenames and **nobody realised they were a
replicate.** So the project has, without intending to, measured its own evaluation noise.

| | `snapshot` | `snapshot_100k_frames` | disagreement |
|---|---|---|---|
| train, pooled mean | 51.94 | 52.16 | 0.4% |
| train, successes | **19/200** | **28/200** | **47%** |
| eval-easy, pooled mean | 144.72 | 131.05 | **10%** |
| eval-easy, successes | 62/200 | 63/200 | 1.6% |

Per scene, train regime — the disagreement is not spread evenly:

| scene | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|---|
| `snapshot` succ | 0 | 0 | 2 | 3 | **9** | 2 | 0 | 0 | 1 | 2 |
| `snap_100k` succ | 0 | 0 | 4 | 2 | **16** | 3 | 0 | 1 | 0 | 2 |
| `snapshot` mean | 3.06 | 16.44 | 100.96 | 44.22 | 128.05 | 48.97 | **18.86** | 42.50 | 74.81 | 41.57 |
| `snap_100k` mean | 2.11 | 16.96 | 108.37 | 38.65 | 141.08 | 46.38 | **9.09** | 43.88 | 80.16 | 34.90 |

Scene 4 differs by 78% in success count (9 vs 16). Scene 6 differs by 2× in mean return.

**What this establishes (INFERRED, from a single replicate pair):** evaluation of a fixed policy at
a fixed seed is not reproducible at this protocol, and the irreproducibility is large — comparable
to, or larger than, most differences the project has been treating as findings. A 20-episode
per-scene grid does not resolve a success count to better than roughly ±50% at this success rate.

**What it does not establish:** the cause. It could be unseeded env stochasticity, unseeded action
sampling, MuJoCo/Metal nondeterminism, or a code change between the two runs that the JSON metadata
does not capture. **Nothing in the recorded metadata distinguishes these**, which is itself the
finding — the protocol fields that *are* recorded were insufficient to notice the runs were
replicates, let alone to explain why they differ.

**One replicate is one replicate.** This is n=1 on the noise estimate itself. It should be repeated
before the magnitude above is quoted as a resolution limit; it is currently the only direct evidence
of its size, which is why it is stated so prominently rather than despite that.

## 3. The one retention number that exists, and what it actually is

Only `cell55k` (`drqv2` seed 6, 50k frames, **one seed, one checkpoint**) has a denominator that
survives the guards in `scripts/regime_retention_report.py`. The headline is **0.003**.

Its own pooled inputs are 3.49 / 115.31 = **0.030** — ten times larger. Both are correct, and the
gap is a selection step that must not be skipped when reading it:

- The tool refuses any scene whose *denominator* fails to clear the measured random floor (1.82)
  **and** solve the task at least 25% of the time (`MIN_DENOM_SUCCESS = 0.25`, added after a policy
  scoring 1/20 on every scene produced a 0.947 "retention" that read as robustness).
- **4 of 10 scenes pass.** The 0.003 is pooled over those four only.
- This is **post-hoc scene selection on the denominator**. The tool prints its own warning that the
  estimand is not RL-ViGen's protocol, which averages all ten. A reviewer should go straight at this.

So the project's single headline generalization number rests on: one baseline, one seed, one
checkpoint, four of ten scenes, chosen after seeing which scenes the agent could do at all — and,
per §2 above, measured with an instrument whose reproducibility at fixed seed is roughly ±50% on
success counts.

## 4. The finding that survives all of that

Independent of any ratio, and the most robust thing in this file:

**At 50k frames on Door, three of four runs reach a stable return plateau of 79–115 while opening
the door zero times.** (`drqv2` s7: 0/200. `drq` s1: 0/200. `svea` s1: 6/200, never more than 1/20
on any scene. Only `drqv2` s6 solves: 59/200.)

The mechanism is not mysterious. Door's reward is `if/elif`: success pays exactly 1.0 with no
shaping; otherwise up to 0.25/step for gripper proximity plus 0.25/step for door rotation. Over a
500-step horizon **shaping alone can pay up to 250 without the door ever opening** (C62). A policy
that optimises shaping and never solves the task sits exactly in the 79–115 band, and sits there
*stably*, so its learning curve looks healthy.

**Consequence (INFERRED, and it reaches backwards):** return is not evidence of learning on this
task. Only the success count separates the two cases, and obtaining it costs a full evaluation grid.
Every return-based statement made anywhere in this project before the success counts existed should
be re-read with that in mind.

**This also re-reads RL-ViGen's own published numbers.** Their `DrQ-v2` on Door Easy is **3.6** over
5 seeds — **1.4% of the shaping ceiling.** That is not a weakly-trained agent; it is one whose
gripper essentially never approaches the handle. Same for their CURL (6.6) and DrQ (14.0). Our
`drqv2` reads **3.49** at 50k on the same regime — i.e. *on* their published value — and **131.05**
by 100k, at one twelfth of their budget (C37). We cannot explain why their runs, at 12× more
budget, stayed at the floor. **ASSUMED**: that our evaluation protocol matches theirs closely enough
for the comparison to mean anything. Nothing has ever verified this — see
[05](05-what-would-embarrass-us.md).

## 5. What is emphatically not measured

- **Lift.** Never run. Every finding in this pack is Door-only, and Door's specific `if/elif` reward
  structure drives the central result in §4. Whether any of it transfers is unknown.
- **Nine of twelve baselines.** No retention grid exists for `alda`, `ctrl`, `curl`, `ibac_sni`,
  `idaac`, `ppg`, `rad`, `sgqn`, `soda`. See [04](04-the-twelve-baselines.md).
- **`eval-hard`.** Only `train` and `eval-easy` grids exist. The benchmark also defines
  `cam-easy`/`cam-hard`, a camera axis nothing here has ever measured.
- **Any published RL-ViGen number, reproduced.** Zero. (C48.)
- **Seed count.** Every cell is n=1. `drqv2` s6 solves 59/200 and s7 solves 0/200 — same code, same
  budget, same task, different seed. Nobody has computed what seed count this design would need to
  resolve the effects it reports. **That calculation is cheap and has not been done.**
