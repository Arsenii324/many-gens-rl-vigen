# Handoff — EXPIRED, kept as evidence

> **Scope: the state as of 2026-08-10. Do not act on it.** Superseded 2026-08-16.
> The live working state is `docs/STEP-ZERO.md`'s handoff block plus `python scripts/state.py`.
>
> **Why this is marked rather than deleted.** It is the worked example behind `docs/SYSTEM.md`'s
> central rule. It did not decay — it was a true snapshot filed as if it were a fact, and six days
> later it reads as a status report. The table below still says "12/12 implemented" and
> "13 of 13 real runs", after `ibac_sni` was rebuilt from its base and `ppg`/`alda`/`idaac` were
> each measured at 0% descent from their own references. Nothing here was ever wrong; it simply
> carried no scope, so a reader has no way to reject it and will instead trust it slightly.
>
> `SYSTEM.md`'s open question stands: two working-state slots exist (this file and STEP-ZERO's
> block) with no rule for which is authoritative. They should collapse to one.

Written for the next session (mine after a compaction, or a person). Scratch file: delete once its
content has been absorbed into `instruction.md`. Everything below was committed and verifiable
**on 2026-08-10**.

## State, in one table

| | |
|---|---|
| repo | `ccm-intro/projects/many-gens-rl-vigen`, tree clean |
| baselines | **12/12 implemented**, none an alias, plus `random` as the negative control |
| real-simulator runs | **13 of 13** (12 baselines + `random`) under protocol hash `7e674231852bca46`, each with a checkpoint |
| tests | `pytest tests` — count and timing in `docs/VALIDATION.md` §0 |
| mutation | curated **19/19**; unbiased sweep seed 101 **13/25**, survivors triaged in `docs/VALIDATION.md` |
| remote | DataSphere `gt4.1` bring-up **verified end to end** — see [`datasphere/README.md`](datasphere/README.md) |
| env | robosuite via `barannikov-work/.venv`, `MUJOCO_GL=glfw`, mujoco **2.3.7** (3.x breaks every eval mode) |

Read [`instruction.md`](instruction.md) first — §0 status, §5a per-baseline verdict on the
historical code, §8/§8b known gaps. Then [`docs/VALIDATION.md`](docs/VALIDATION.md) for what is and
is not established.

## The things most likely to be got wrong again

1. **Unpatched RL-ViGen silently evaluates on the training distribution.** If
   `python setup/apply_patches.py --check` fails, no number from the tree means anything. Four
   patches: P1 mode, P2 video load, P3 regime export, P4 overlay device.
2. **`str.replace` with a mistyped anchor is a silent no-op.** It cost six missing config entries
   and two hours. Every edit script here asserts its anchor is present and unique; keep doing that.
3. **Passing a hyperparameter a config does not have is also a silent no-op.** `ppo_epoch` was
   ignored by IDAAC's `Config`, which is why two tests ran 10× longer than intended.
4. **A measurement can depend on ambient machine state.** The curated catalogue read 19/19 before
   Places365 was fetched and 17/19 after, with no code change — the two mutants it stopped killing
   are only observable when the dataset is *absent*, and the guarding test skips when it is
   present. Both environments are now covered. When a score moves, suspect the environment before
   the code.
5. **`pgrep -f "foo.py"` matches your own waiter shell**, whose command line contains that string.
   Several waits here returned instantly, or never, for that reason. Match on the interpreter path
   too.

## Next steps, in the order I would do them

*(Rewritten 2026-08-10 after the audit and four research passes. Three of the four items that used
to be here are done or refuted; see `docs/STATUS-AGAINST-THE-GOAL.md` for the full picture.)*

1. **Decide the four open protocol questions before spending compute** — headline metric (return
   vs success rate), `feature_dim` 50 vs 256, checkpoint selection, and seeds. All change the
   protocol hash, which is free now and invalidating later. `STATUS-AGAINST-THE-GOAL.md` §3b ranks
   the full list of sixteen by how much each distorts the comparison.
2. **Exercise the clone-to-curve path from a genuinely clean clone.** The reproducibility half is
   closed — a fresh `install.sh` now really does reproduce this tree, which it did not before P5 —
   but the end-to-end run has never been done. Note that RL-ViGen cannot be checked out cleanly on
   macOS at all (it tracks two paths differing only in letter case).
3. **A real training run at meaningful scale, on DataSphere.** Everything so far is 3k-frame smoke.
   ~78 env steps/s on a T4 → ~1.8 h of env stepping per 500k-frame run, CPU-bound on physics, so
   pack several runs per box.

**Removed from this list, with reasons:**
- ~~Re-run all 13 baselines cleanly at one commit~~ — done; and the protocol hash has since moved
  twice (P4, P5), so those runs are superseded anyway.
- ~~Validate PPG / IBAC-SNI / CTRL against Procgen~~ — **refuted as a plan.** It costs a second
  environment stack and validates the *discrete* method, not the continuous port, which is the
  thing actually in doubt. Diagnostic signatures plus unit tests on the Gaussian machinery are the
  cheaper and more relevant evidence.
- ~~`num_envs > 1` for the on-policy loop~~ — **not needed.** IDAAC's own continuous configuration
  is *"2048 steps, 1 process"*, so one environment is the authors' setting. Raising `num_steps` was
  the correct fix and is applied.

## Open questions for the supervisor

`docs/SUPERVISOR-BRIEFING.md` is the current version of this; `docs/TASK.md` §6 is the original
list. Both of the items that used to sit here are resolved:

- ~~**which ALDA**~~ — settled. The brief's `2001.01046` is an AAAI 2020 **image-classification**
  paper with no RL content; the RL one is `2410.07441`, which our port implements. A correction to
  report, not a question to ask.
- ~~**the reference eval**~~ — withdrawn as a blocker. Managing evaluation caveats is our job, not
  something to wait on. RL-ViGen's own `eval.py::robo_eval` is now readable here and our evaluator
  has been checked against it numerically (`VALIDATION.md` §0.05).
