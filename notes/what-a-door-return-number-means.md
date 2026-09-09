# What a Door return number actually means — a hard ceiling, and why SR=0 caps it at 250

**2026-09-09**, read from the vendored source
(`RL-ViGen-upstream/third_party/robosuite/robosuite/environments/manipulation/door.py`) plus
RL-ViGen's own `envs/robosuiteVGB/cfg/robo_config.yaml`. Every number below is from those two files.

## The reward, exactly

```python
reward = 0.0
if self._check_success():                       # hinge_qpos > 0.3 rad  (~17 degrees)
    reward = 1.0
elif self.reward_shaping:
    dist = np.linalg.norm(self._gripper_to_handle)
    reward += 0.25 * (1 - np.tanh(10.0 * dist))                       # reaching,  <= 0.25
    if self.use_latch:
        reward += np.clip(0.25 * np.abs(handle_qpos / (0.5*np.pi)), -0.25, 0.25)  # latch, <= 0.25
reward *= self.reward_scale                                           # 1.0
```

With `reward_shaping: true` and `horizon: 500` from `robo_config.yaml`, and `use_latch=True`,
`reward_scale=1.0` as the task's defaults.

## The bound this gives, and it is hard

**Success and shaping are mutually exclusive per step** — the `elif`. So:

| state of a step | reward |
|---|---|
| door open (`hinge_qpos > 0.3`) | **1.0** |
| not open, best possible shaping | **0.50** (0.25 reaching + 0.25 latch) |

Over a 500-step episode:

- **A policy that never opens the door cannot exceed return 250.**
- **Return > 250 therefore PROVES at least one success step**, with no other evidence needed.
- **Return 500 means the door was open for the entire episode**, which is unreachable from a start
  state where it is closed. Figure 22's 0-500 axis is, in effect, *how much of the episode the door
  spent open*.

## What that says about our numbers

`idaac` at 598,016 frames, endpoint, 400 episodes per regime:

| | value |
|---|---|
| train return | **33.69** |
| per step | **0.067** |
| fraction of the 250 shaped ceiling | **13.5 %** |
| success rate | **0.000** over all 880 endpoint episodes |

Pure reaching saturates at **0.25/step** once the gripper is at the handle. An average of 0.067
means the gripper is near the handle only part of the time and **the latch component is
contributing almost nothing** — `handle_qpos` stays near zero, so the handle is not being turned.

**Coherent reading: the policy learned to approach the handle and never learned to turn it.** SR of
exactly 0.000 across 880 episodes says the hinge never once passed 0.3 rad. That is not a broken
success flag — the convention is pinned and tested (`tests/test_success_convention.py`, seven
accumulation sites across twelve baselines, any-step rather than final-step, `docs/REGISTER.md`
2026-08-18).

## Why this matters for the battery

**The remaining gap is discrete, not gradual.** Getting from 34 to competence is not a matter of
grinding the shaped reward upward; it requires crossing into a regime worth 1.0/step. A run improving
from 34 to, say, 60 has not got closer to opening the door in any meaningful sense — it has got
better at hovering near the handle.

**It gives `drqv2` a hard, checkable criterion I did not have before:**

- **Return > 250 is impossible without success.** If `drqv2` clears 250, the harness demonstrably
  supports competence on Door and the ceiling is the algorithms.
- **If `drqv2` also lands near 34 with SR 0.000**, then two baselines from different families both
  learned to reach and neither learned to turn — which points at the task configuration, the action
  space, or the observation, and not at either algorithm.

**And it reframes `success_rate` for reporting.** It is not the axis RL-ViGen judges Robosuite on, so
0.000 is not by itself a failure report. But `success_rate = 0` and `return <= 250` are the *same
statement* under this reward, so quoting the return already carries the success information — which
is worth knowing before anyone writes "SR was 0 but return was reasonable" as though those were two
independent observations.
