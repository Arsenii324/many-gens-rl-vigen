# The "train regime" aggregate is already a generalization number

Established 2026-09-08 from source, prompted by the seedvar job's scene breakdown.

## The chain, each link read rather than assumed

1. **A `scene` is a visual configuration, not a placement.**
   `secant/envs/robosuite/preset_customization.py:307` — `get_custom_reset_config(task, mode,
   scene_id)` builds texture, colour, camera and lighting from
   `TASK_RANDOM_SEED[task][mode][scene_id]` and `TASK_TEX_CANDIDATE[task][mode][scene_id]`.
   `robosuitevgb/utils.py:33` asserts `0 <= scene_id <= 9`.

2. **Placements are held CONSTANT across scenes**, so scene identity is the only intervention.
   `scripts/eval_across_scenes.py` seeds `utils.set_seed_everywhere(seed)` from the same base for
   every scene, and its own comment says why: *"each scene sees the SAME sequence of object
   placements. That is what makes the scene comparison an intervention."*

3. **The agent trains on scene 0 only.** `RL-ViGen-upstream/train.py:78`:

   ```python
   self.train_env = robo_make(name=..., action_repeat=..., frame_stack=..., seed=self.cfg.seed)
   ```

   No `scene_id` argument, so it takes `robo_make`'s default **`scene_id=0`**; `mode` unset, so it
   inherits `robo_config.yaml`'s `mode: train`. One fixed visual configuration for the whole run.

## What follows, and it changes how a table should be written

The endpoint grid sweeps `train` over scenes 0–9. That is **one seen scene and nine unseen visual
variants**. drqv2 at 100k, mode policy, 20 episodes per scene, three seeds:

| | return |
|---|---:|
| scene 0 — the configuration actually trained on | **354.18** |
| scenes 1–9 — unseen variants, still "train regime" | **35.89** |
| the 200-episode `train` aggregate that records report | **67.72** |
| `eval-easy` aggregate | 8.14 |

**The 9.9× drop happens before any eval regime is reached.** A report that presents 67.72 as the
in-distribution baseline and 8.14 as the generalization result would understate in-distribution
performance by more than 5× and would silently fold a generalization gap into its own control.

## What this does NOT settle

Whether scene 0 is *representative* of the train regime or an easy draw. Three seeds all score far
above the other nine on it, so it is not seed noise — but "the trained scene is easiest" and "the
trained scene is where competence lives" are the same observation from one measurement, and this
job cannot separate them. Training a second seed set on a different `scene_id` would.

**Nothing here is a defect.** `eval_grid.py`'s docstring already refuses to aggregate across
regimes and makes every row name its scene set, so the data needed to say all of this is on every
row. What is missing is the reporting convention, and that is an owner decision:

- report `train:scene 0` as the in-distribution headline and `train:1-9` as a first generalization
  step, or
- keep the 10-scene aggregate as the headline and say plainly that it is not in-distribution, or
- train across the whole train scene set, which changes the experiment rather than the report.

The third is not a documentation change and would invalidate every existing cell.
