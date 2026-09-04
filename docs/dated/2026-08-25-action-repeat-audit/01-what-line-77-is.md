# 01 — What `rlvigen.sh:77` is, and where it came from

**Written 2026-08-25. Dated snapshot, not a living document.** Every claim below was verified
against the working tree, git history, or the vendored PDF on that date.

## The artifact

`runnable/_launch/rlvigen.sh` lines 77–78 are the launcher's `exec` into upstream's entry point:

```bash
exec "$PY" train.py --config-name "$CFG" env=robosuite "task@_global_=$TASK" \
  action_repeat=1 use_wandb=False use_tb=True save_video=False "${EXTRA_OVERRIDES[@]}" "$@"
```

`action_repeat=1` is a **hydra override on the command line**, not a config edit. Upstream's files
are untouched; the value is supplied at launch.

## The file is ours. Upstream ships nothing like it.

- Created **2026-08-17** in commit `849c5b15` ("Part 1 continued: ppg, idaac, ibac_sni, ctrl and
  RL-ViGen's own five now run too").
- `find RL-ViGen-upstream -name rlvigen.sh` returns nothing. It lives in `runnable/_launch/`
  alongside our other eight launchers (`alda.sh`, `ctrl.sh`, `dmc_gb.sh`, `ibac_sni.sh`,
  `idaac.sh`, `ppg.sh`, `ppg_eval.py`, `smoke_all.sh`).
- It is a **wrapper, not a fork**: it sets `sys.path` and `cd`s into the upstream tree, then calls
  upstream's own `train.py`. Its line 28 documents why the path work is needed — `algos/sgqn.py`
  does a bare `import drqv2`, so `$RLV/algos` must be on the path or hydra fails with
  "Error locating target `algos.sgqn.SGQNAgent`".

## Line 77 does **not** share the file's origin. It has three.

This is the part that a glance at the file would miss. The single line carries three separate
provenances:

| token | origin | when |
|---|---|---|
| `env=robosuite`, `task@_global_=$TASK`, `use_wandb=False`, `save_video=False` | original to the file | `849c5b15`, 2026-08-17 |
| **`action_repeat=1`** | **added later the same day** | `6f9ba507`, 2026-08-17 |
| `use_tb=True` (was `False`) | changed three days later | `1cdebae1`, 2026-08-20 |

Verified by `git show 849c5b15:runnable/_launch/rlvigen.sh`, whose exec line at line 51 carries
**no `action_repeat` override at all**. The commit that introduced it, `6f9ba507`, is titled
*"Part 2 opened: emission inventory. Two comparability defects found, one fixed."* — so
`action_repeat=1` entered as a **comparability fix**, discovered while inventorying what each
baseline emits, not as part of the launcher's original design.

The `use_tb` flip is separately notable because it has known fallout: it broke `drq`
(`algos/drq.py:328` calls `dist.entropy()` on a `SquashedNormal` guarded by `if self.use_tb:`).

## The system it drives

**`gemcollector/RL-ViGen`** — its `train.py`, `cfgs/*.yaml`, `algos/*.py`, vendored under
`RL-ViGen-upstream/`. Line 6 of the launcher names the five agents it serves:
`svea | drq | sgqn | curl | drqv2`.

The other seven baselines never touch this file. They have their own launchers and their own
upstream repositories, so "the system that uses the file" covers five of twelve, not all.

## Why the override exists at all

The launcher documents its own reasoning at lines 60–66, and the reasoning checks out (see
[02](02-paper-vs-shipped.md)): upstream's shipped configs set `action_repeat: 2`, upstream's own
paper specifies `1` for Robosuite, and `robo_wrapper` really does apply the value — so a stock run
is off the benchmark's own published table by 2× on every budget.

What the comment does **not** say, and what [03](03-the-twelve-audit.md) establishes, is that this
override is the only place in the whole twelve-baseline set where anyone actually decides the value.
