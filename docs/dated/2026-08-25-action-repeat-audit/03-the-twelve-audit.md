# 03 — Which originals intended action repeat, and a correction to our own audit

**Written 2026-08-25. Dated snapshot, not a living document.** Verified by reading the vendored
trees on that date, not from recollection.

## Correction first: `INTEGRATION-DELTA.md` credits `dmc_gb.sh` with a decision it does not make

[`INTEGRATION-DELTA.md`](../../INTEGRATION-DELTA.md):489 records:

> | `rad` `soda` | 1 | `_launch/dmc_gb.sh` passes `--action_repeat 1` **explicitly** |

The flag is passed — `runnable/_launch/dmc_gb.sh:49` really does carry `--action_repeat 1`. **But it
never reaches an environment on the robosuite path.**

`runnable/dmc_gb/src/env/wrappers.py`, `make_env()`:

```python
def make_env(..., episode_length=1000, frame_stack=3, action_repeat=4, ...):   # line 13-19
    if domain_name == 'robosuite':                                              # line 26
        ...
        env = _robo_make_env(task_name=..., seed=..., scene_id=..., mode=...)   # line 33
        env = _RGBOnly(env, episode_length)                                     # line 35
        return FrameStack(env, frame_stack)                                     # line 36  <-- returns
    ...
    env = dmc2gym.make(..., frame_skip=action_repeat, ...)                      # line 57
```

`frame_skip=action_repeat` appears **only at line 57**, on the DMC branch, which the robosuite branch
returns before reaching (line 36). Confirmed by grep: `frame_skip` occurs exactly once in the file.
`FrameStack`'s `for _ in range(self._k)` is observation stacking in `reset`, not action repeat; and
`_RGBOnly` is an observation unwrapper.

**So `rad` and `soda` reach `action_repeat = 1` by absence of a mechanism, exactly like `alda`** —
whose `specs/train_alda_robosuite_door.yaml:19` carries `action_repeat: 1` that
`trainers/alda_trainer.py` likewise never reads on its robosuite branch (it returns at line 152,
before the `dmc2gym.make(..., frame_skip=env_config['action_repeat'])` at line 159).

Two trees, same structural pattern, same consequence: **a robosuite branch bolted onto a DMC
codebase, returning early and skipping the line that consumes the knob.**

## The corrected picture

| group | baselines | how it reaches 1 | is it a decision? |
|---|---|---|---|
| RL-ViGen natives | `drqv2` `drq` `svea` `sgqn` `curl` | `rlvigen.sh:77` overrides a shipped default of **2** | **yes** |
| DMC-GB lineage | `rad` `soda` | flag passed, **never read** (`wrappers.py:36` returns first) | no |
| DMC-GB lineage | `alda` | spec key set to 1, **never read** (`alda_trainer.py:152` returns first) | no |
| Procgen-native | `idaac` `ctrl` `ibac_sni` `ppg` | **no action-repeat mechanism exists in their trees** | no |

**Five of twelve by decision, not seven.** `INTEGRATION-DELTA.md`'s summary sentence — *"only seven
of twelve agree by anyone's decision"* — should read **five**, and `rad`/`soda` move from the
"explicit" row into the "absent mechanism" row alongside `alda`.

This makes the entry's own conclusion *stronger*, not weaker: it already warns that "no mechanism
would notice if a clone's default changed." Seven of twelve pass no effective value; it is nine.

## Which originals genuinely intended action repeat, and what they intended

Verified defaults, from the vendored code:

- **`runnable/dmc_gb/src/arguments.py:12`** — `--action_repeat` default **4**. This is the tree that
  hosts both `rad` and `soda`.
- **`runnable/alda/dmcontrol_generalization_benchmark/src/arguments.py:12`** — `--action_repeat`
  default **4**. Same DMC-GB lineage, vendored inside alda.
- **RL-ViGen's own configs** — **2** everywhere (see [02](02-paper-vs-shipped.md)).
- **`idaac`, `ctrl`, `ibac_sni`, `ppg`** — zero occurrences of `action_repeat` or `frame_skip`
  anywhere in their trees. Procgen has no such convention.

So three baselines (`rad`, `soda`, `alda`) descend from a lineage whose default is **4**, and five
from one whose default is **2**.

## Why "giving it back" would be wrong

The 4 and the 2 are **domain constants, not method properties**, and this is the whole argument:

1. **They are per-domain, tuned elsewhere.** DMC-GB's 4 is the DeepMind Control convention, chosen
   for DMC's control frequency. RL-ViGen's own 2 is its "otherwise" value — and its paper *already
   overrides itself to 1 for Robosuite* (Table 2). The benchmark's authors treated the value as a
   function of the domain and set it to 1 for exactly the domain we run.
2. **No paper claims action repeat as a contribution.** There is no "DrQ-v2's action repeat" the way
   there is "IDAAC's advantage head." Nothing in any of the twelve methods depends on the value
   structurally; it is a wrapper outside the algorithm.
3. **Four of twelve cannot receive it at all.** `idaac`, `ctrl`, `ibac_sni` and `ppg` have no
   mechanism. Restoring 2 or 4 to the other eight would put them on a *different x-axis* from these
   four — which is the launcher's own stated reason (line 64) for forcing 1 in the first place.
4. **Robosuite is already at the control rate DMC's frame-skipping was reaching for.** OSC_POSE at
   robosuite's control frequency does not need decimation the way raw DMC physics does.

**The honest statement is therefore not "all twelve agree at 1."** It is: *one value is enforced for
five baselines by our launcher, and holds for the other seven because nothing in their robosuite
paths can express any other value.* Those are different facts, and only the first would survive
someone changing a config.

## What is not established here

Whether the original RAD/SODA/SVEA/CURL **papers** report DMC results at 4 (as opposed to the
DMC-GB harness defaulting to it) was not checked — it would need the papers themselves, and it does
not change the conclusion, since none of them ran robosuite at all.
