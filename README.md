# many-gens-rl-vigen

Generalization baselines on **RL-ViGen robosuite** (Door, Lift).

> ## The approach changed on 2026-08-17. Read this before the rest of the file.
>
> **The null is the original repository, cloned, running its own `train.py`.** Duplication across
> baselines is free; any *join* is work and carries the burden of proof. Everything below the
> divider describes the earlier port-and-one-harness design — `rlgen/`, `configs/`, one
> `train.py`, one `plot.py` — which is **superseded**. It is kept because the reason the approach
> changed is only legible next to what it replaced, and because `rlgen/` still exists.
>
> Current entry points:
>
> ```bash
> bash runnable/_launch/smoke_all.sh        # all twelve baselines, one table   (12/12, 66 min)
> bash runnable/_launch/dmc_gb.sh rad Door  # one baseline, its OWN train.py
> python scripts/deviations.py              # every line this project changed in an original
> python setup/apply_patches.py --check     # the vendored RL-ViGen tree, P1-P21
> python scripts/collect_metrics.py <dir>   # all twelve baselines' metrics on one set of axes
> ```
>
> - **[`docs/RUN-THIS-PROJECT.md`](docs/RUN-THIS-PROJECT.md)** — **start here from a fresh clone.**
>   Reconstruct the pinned sources, build the environment, provision Places365, build and verify a
>   payload, submit a run. Each step states what proves it worked.
> - **[`notes/START-HERE.md`](notes/START-HERE.md)** — the index to every other surface: which
>   decisions are still the owner's to make, the host-migration order, and how to run the campaign.
>   Start there rather than here if the question is "what is still open" or "how do I run this on
>   the production host"; this README describes what the repo *is*, not what is left to do in it.
>   Running a cell on the production V100 box is
>   [`notes/RUNNING-ON-PRODUCTION-HOST.md`](notes/RUNNING-ON-PRODUCTION-HOST.md), with its
>   rationale and open decisions in
>   [`notes/PRODUCTION-HOST-RATIFICATION.md`](notes/PRODUCTION-HOST-RATIFICATION.md).
> - **[`docs/RUNNABLE-ORIGINALS.md`](docs/RUNNABLE-ORIGINALS.md)** — Part 1: what runs, what was
>   changed to make it run, and what the T4 has and has not proved.
> - **[`setup/SOURCE-BOOTSTRAP.md`](setup/SOURCE-BOOTSTRAP.md)** — reconstruct every ignored source
>   tree from public pinned repositories, apply tracked adaptations, and verify source closures.
> - **[`docs/PART2-METRIC-INVENTORY.md`](docs/PART2-METRIC-INVENTORY.md)** — Part 2: what each
>   baseline emits and against what, with seven findings. Two of them change what the benchmark
>   measures: RL-ViGen's own runner evaluated on the *training* distribution, and frame stacking
>   splits the twelve 10/2 in a way no rescaling repairs (`ctrl` and `ibac_sni` are the
>   single-frame two; the 8/4 this line used to quote predates IDAAC's frame-stack move).
>
> Twelve baselines currently train on RL-ViGen robosuite by running their own entry points, at
> **38 files, +1,568 / −146 (941 non-comment)** across six clones plus RL-ViGen patches P1–P21
> (no P16 — the ids are not contiguous). The file/line totals are the complete-tree count quoted
> by `docs/RUNNABLE-ORIGINALS.md`; the current checkout is intentionally slim, so
> `python scripts/deviations.py` reports per-clone PARTIAL counts and no total here.

---

---

## What this repo is for

Twelve visual-generalization baselines are supposed to be comparable to each other. They are
comparable only if the thing measuring them is *the same thing*. Almost all of the effort here
goes into making that structurally true rather than conventionally true:

| Requirement | How it is guaranteed |
|---|---|
| Identical evaluation | **One** `evaluate()`. It receives the policy as an opaque `Callable[[obs], action]` — no agent, no config, no name. It cannot branch on an algorithm it cannot see. |
| Identical logging keys | Every tag is a constant in [`rlgen/tags.py`](rlgen/tags.py). `RunLogger` raises on an unknown key, and a test fails the build if a tag literal appears anywhere else. |
| Identical training length | The budget is in **environment frames** with `action_repeat` folded in, and lives in the protocol. A launch script names a *config*, not an algorithm; a baseline's config is `base` plus only its own keys. |
| Comparable numbers | Every episode row and every run carries a **protocol hash**. Two numbers belong in one table iff the hashes match. `plot.py` refuses to overlay two protocols silently. |
| Honest baselines | Every baseline declares `implemented` / `alias` / `absent` in [`rlgen/registry.py`](rlgen/registry.py). A declared alias is labelled as one on every figure; an undeclared alias is what corrupts a table. |

## Layout

```
rlgen/          the contract. protocol, env seam, evaluator, logger, tags, registry, replay, trainer
baselines/<x>/  train.sh + README per baseline        (generated from the registry — see tools/)
configs/        one yaml: `base` plus per-baseline deltas
train.py        one entry point for every baseline
plot.py         one plotting routine; no per-baseline branch
tests/          the structural guarantees, as tests
mutants/        real mutation testing: mutate rlgen/, run `pytest tests`, report survivors
setup/          upstream clone, patches, install, verification
docs/           the brief, the working standard, the review of the previous code
instruction.md  what was taken from where, and every decision, with reasons
```

## Baselines

```bash
python train.py --list
```

**All twelve baselines from the brief are implemented**, plus `random` as the negative control.

| | |
|---|---|
| **off-policy** | `drqv2`, `svea`, `sgqn`, `curl`, `drq` (DrQ-v2 / SAC backbones) · `rad`, `soda`, `alda` (SAC) |
| **corrected** | `ctrl` is *Cross-Trajectory Representation Learning* (ICLR 2022) — **PPO**-based, not a CURL variant. The previous `class CTRLAgent(CURLAgent)` was a name-similarity mistake. |
| **on-policy** | `ppg`, `ibac_sni`, `idaac`, `ctrl` (IMPALA backbone) — driven by `rlgen/trainer_onpolicy.py`, which shares this repo's evaluator, logger, protocol and eval cadence with the off-policy loop |
| **data-gated** | `svea`, `sgqn`, `soda` need Places365 for their overlay augmentation *to train* (not to evaluate). `bash setup/fetch_overlay_dataset.sh` fetches the **train** split, ~24 GB — the production value, because the overlay distribution IS their mechanism (DECISION-SHEET A22). Pass `val` for a ~2 GB probe asset, which production refuses unless the deviation is stated explicitly. |

Not claimed: that `ppg`, `ibac_sni` or `ctrl` reproduce published returns. Nobody has published either on
RL-ViGen robosuite, so there is no number to reproduce — see `rlgen/algos/onpolicy_ext.py`.

`random` is not decoration. On Lift the shaped reward pays `1 − tanh(10·d)` at every one of 500
steps, so a random arm can collect a return of 60 without ever lifting the block. Any
"improvement" is a comparison against that floor, and the floor is measured, not assumed.

## Verifying before you trust a number

```bash
python setup/apply_patches.py --check   # the vendored upstream is in the state this repo expects
pytest tests -q                         # everything (slow: builds real envs, trains)
pytest tests -q -m "not slow"            # the inner loop
python mutants/run.py                   # 14 curated mutants, oracle = pytest tests
python mutants/sweep.py -n 40           # UNBIASED random operator sweep — the number that matters
```

Both mutation runs edit the **production** code and require the real test suite to notice — which
is what mutation testing is, and is not what the file this repo used to carry was doing.

The **sweep** is the one to trust. A curated catalogue where the same person wrote the mutants and
the tests measures that person's imagination; the sweep picks sites uniformly at random over the
AST. Its first run scored **12/40 (30%)** against a suite that had just passed the curated
catalogue 14/14 — and it localised the gaps exactly: `trainer.py` untested, the replay index
arithmetic untested, and the real environment's own truncation untested because every test ran on
the synthetic backend. Closing what it named took the suite to **60% out-of-sample**, and found
along the way a dataset dependency that failed only after writing artifacts, an operator-precedence
bug that disabled a guard, a first-episode measurement artifact affecting one episode in ten, a
test that passed with and without the fix it was written for, and a test that the defect it
catches would have silently *skipped*. Numbers, survivors and triage:
[`docs/VALIDATION.md`](docs/VALIDATION.md).

## Compute

Everything above runs on an M2 Pro (MPS, no CUDA) at 79–118 pixel-steps/s per environment. Full
runs (500k frames × 12 baselines × 2 tasks × seeds) are remote work — see
[`docs/compute.md`](docs/compute.md).

## Where the reasoning is

- [`instruction.md`](instruction.md) — **read this first if you are picking the repo up.** What
  was inherited from where, every decision and its reason, what was deleted and why.
- [`docs/TASK.md`](docs/TASK.md) — the supervisor's brief verbatim, and R1–R7 as checkable criteria.
- [`docs/RIGOR.md`](docs/RIGOR.md) — the working standard: observability, verification, and how
  mutation testing is done properly.
- [`docs/REVIEW.md`](docs/REVIEW.md) — the review of the code this replaced, stamped to commit
  `07c3f12`.
