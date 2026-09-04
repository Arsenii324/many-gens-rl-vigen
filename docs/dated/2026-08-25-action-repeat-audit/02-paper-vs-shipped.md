# 02 — Is upstream faithful to its own paper? No, and we silently took the paper's side

**Written 2026-08-25. Dated snapshot, not a living document.** The PDF extraction below was run on
that date against the vendored copy.

## The paper says 1. The code says 2.

Verified by extracting text directly from `ext/baseline_resources/benchmarks/rlvigen_neurips_supplementary.pdf`,
**page 3, Table 2 ("Common hyper-parameters in RL-ViGen")**:

```
Action repeat    Robosuite: 1, otherwise: 2
Feature dim      DrQ(v2), CURL: 50, otherwise: 256
Frame stack      3
```

Against every shipped config in `RL-ViGen-upstream/cfgs/`:

| file | line | value |
|---|---|---|
| `config.yaml` (drqv2) | 10 | `action_repeat: 2` |
| `drq_config.yaml` | 9 | `action_repeat: 2` |
| `svea_config.yaml` | 9 | `action_repeat: 2` |
| `sgqn_config.yaml` | 9 | `action_repeat: 2` |
| `curl_config.yaml` | 9 | `action_repeat: 2` |
| `pieg`/`srm`/`svea_drq`/`sgqn_drq` | 8–9 | `action_repeat: 2` |

And `cfgs/task/*.yaml` contains **no `action_repeat` key at all** — there is no Door-level override
that would rescue the shipped default.

**So RL-ViGen's repository contradicts RL-ViGen's paper**, and our `rlvigen.sh:77` resolves the
contradiction in the paper's favour, on every run, for all five native baselines.

## The shipped value is not inert — it would really take effect

Worth confirming, because "the config says 2" would be harmless if nothing read it.

- `wrappers/robo_wrapper.py:121` — `def robo_make(name, frame_stack=3, action_repeat=2, ...)`.
  Note the **function's own default is also 2**, so even a caller that omits the argument gets it.
- `wrappers/robo_wrapper.py:129` — `env = ActionRepeatWrapper(env, action_repeat)`.
- `wrappers/dmc.py:44-54` — `ActionRepeatWrapper.step()` loops `for i in range(self._num_repeats)`,
  stepping the inner env each time and **accumulating reward** (`reward += ...`), breaking early on
  `time_step.last()`.

So the mechanism is live and correctly implemented. It is not a vestigial key.

## The same paper-vs-code split is not confined to `action_repeat`

Table 2 also gives `Feature dim — DrQ(v2), CURL: 50, otherwise: 256`, while **every** shipped
config hard-codes `feature_dim: 50` (`config.yaml:34`, `svea_config.yaml:34`, `sgqn_config.yaml:33`,
`pieg_config.yaml:34`, `srm_config.yaml:34`, and the rest). Already recorded at
[`FAITHFULNESS.md`](../../FAITHFULNESS.md):71 and as open decision 2 in
[`STATUS-AGAINST-THE-GOAL.md`](../../STATUS-AGAINST-THE-GOAL.md):121.

Supplementary Table 6 adds a third instance for SGQN (`aux_lr` 8e-5 / `quantile` 0.9 in the paper
against 1e-4 / 0.93 shipped), which is [C64](../../CONSTRUCTION.md#c64).

## The inconsistency that matters, and that nobody appears to have decided

Three instances of one class of conflict — *paper says X, shipped code says Y* — resolved two
different ways, within the same five-baseline launcher:

| conflict | paper | shipped | what we run | which side we took |
|---|---|---|---|---|
| `action_repeat` (Robosuite) | **1** | 2 | **1** | **paper** |
| `feature_dim` (10 of 12 methods) | **256** | 50 | 50 | **shipped** |
| `sgqn aux_lr` / `quantile` | **8e-5 / 0.9** | 1e-4 / 0.93 | 1e-4 / 0.93 | **shipped** |

[C64](../../CONSTRUCTION.md#c64) argues its choice from the founding principle that the null is
"the original repository, running its own `train.py`" — that is, take the shipped value. **But
`rlvigen.sh:77` already violates that principle**, on every run, for all five natives, and has done
since 2026-08-17. C64's recommendation is therefore not the status quo it presents itself as; it is
the *opposite* of the resolution already in force one line away in the same launcher.

This does not make either choice wrong. It means the project has an **undeclared rule** for
resolving paper-vs-code conflicts, applied inconsistently, and C64 should be decided as one
instance of that rule rather than on its own.

**A caveat that cuts the other way**, from the external review and verified here: upstream ships
**no robosuite launch script** (`RL-ViGen-upstream/scripts/` has `train.sh` (DMC), `eval.sh`
(CARLA), `carlatrain.sh`, `habitrain.sh`, `locoeval.sh`, `locodmc_eval.sh`, and no `.sh` mentions
`env=robosuite`). So the configuration that produced the paper's Robosuite numbers is not in the
repository, and "run what upstream ships" does not identify a unique configuration either. Whichever
way the rule is written, it should be written down.
