# What all of it adds up to

Written 2026-09-05 from a session holding five external reviews (~2,900 lines), the project's own
registers, and my own nineteen corrections at once. This is the part that is not visible from any
one document: **~60 distinct findings reduce to three generative mechanisms, and one of them is
caused by the porting act itself.**

---

## Mechanism 1 — absence of a signal read as evidence of a state

An instrument that *cannot run* reports the same thing as one that ran and passed.

| instance | what happened |
|---|---|
| `gate_source_tree_frozen` | read `git status`'s stdout, ignored the exit code → a failing git read as **a clean tree** |
| `gate_scheduler_ram_invariant` | grepped the cost model, which does compare RAM → PASS while the **submission path** that failed went unchecked |
| `contract.py verify-payload` | contract failure and argparse's usage error both exited **2** → a mistyped command reported four present markers as missing |
| `SAVE_EVERY` vs `SAVE_EVERY_FRAMES` | the runner never read the knob → two jobs "validated" cadence and one reported **SUCCESS** |
| `audit_comparability_seam` replay | asserts "uniform over the whole run … exceeds 6e5" **without comparing the cap to the budget** |
| `git status` on the clones | `.gitignore: runnable/*/` → empty output meant *not tracked*, and I read it as *unmodified* |

**The rule:** every check must state what it reports when it cannot run, and that must never be the
pass value. Only `production_gates.py` now has tests against its own false passes — because it is the
only instrument that was audited twice.

## Mechanism 2 — two homes for one number

| instance | the two homes |
|---|---|
| production budget | `production-schedule.json` (500k) vs the protocol (600k) |
| ctrl config | `eval_grid.CTRL_DEFAULTS` vs `families.json` |
| replay capacity | top-level vs `production` block — **I created this one** |
| patch registry | `apply_patches.py` (P20) vs `protocol.env_patches` (to P19) |
| fidelity claims | `FAITHFULNESS.md` vs the clones — three rows wrong |
| **open decisions** | `open_decisions.py` vs `DECISION-SHEET.md` — **now reconciled** |
| throughput | `plan_production.MEASURED_FPS` vs the schedule's copy — **now synced** |

## Mechanism 3 — a constant transplanted across a scope change

**This is the one the project's own instincts get backwards, and it explains the most severe
findings.**

| constant | scope it was tuned in | scope it landed in | consequence |
|---|---|---|---|
| `entropy_coef=0.01` | 15-way categorical, bounded H | 7-D Gaussian, unbounded H | σ → 4.3, policy is noise |
| `kl_divergence(...).mean()` | scalar-per-sample KL | 7-D KL | clone constraint **7× weak** |
| `n_pi=32` | 65,536-sample rollout | 2,048-sample rollout | auxiliary phase **32× more frequent** |
| `level_seed` | Procgen persistent levels | Door episodes | order targets across unrelated episodes |
| `num_envs`, `procs`, replay cap | 4–8 core tiers, 27 GiB | 16 cores, 113 GB | nine baselines carry a resource adaptation |
| `stddev_schedule` | a DrQ-v2 difficulty tier | Door | unresolved (`OPEN-QUESTIONS` Q1) |

**The principle that falls out, and the project does not have it written down:**

> When a port changes a scope — action space, task horizon, hardware, benchmark — **a preserved
> literal is a changed meaning.** Fidelity requires re-deriving the constant's *role*, not copying
> its value.

Preserving `.mean()` because "it is the authors' line" made the port **less** faithful, not more.
The project applied that reasoning correctly to `ibac_sni` (twice) and incorrectly to `ppg`, and the
inconsistency went unnoticed until an external reviewer named it.

## The instrument-audit asymmetry, stated plainly

**Every instrument that was audited was found wrong.** `audit_implementations` (presence, not
wiring), `audit_comparability_seam` (replay claim; completeness relative to a hand-maintained list),
`production_gates` (two false passes), `open_decisions` (blind to an entire surface),
`verify-payload` (exit-code collision), `rlvigen_reference` (**points at a path that does not exist
in this tree — which is why RL-ViGen's published Door numbers went unread for the project's whole
life**).

**Seven for seven as of 2026-09-05**, with three more found the same day: `production_gates`
produced a **third** false pass (`placement provenance` matched the loop variable `episode_index`,
so it certified that records carried an episode id when none reached a record); `eval_grid` carried
a **duplicate, weaker** copy of `completed_episode_diagnostics` so the tests exercised the
validating helper while production ran the permissive one; and `deviations.py` reported **six**
baselines as having mislabelled provenance because `git -C <dir> log` walks UP when `<dir>` is not
itself a repository — `ext/` has no `.git`, so it was comparing every declared upstream commit
against ccm-intro's own HEAD. That last one is the mirror image of the others: a false ALARM rather
than a false pass, which is the safe direction and still wrong.

And the instrument written *this day to enforce this very rule* —
`audit_executed_hyperparameters.py` — swallowed real claims twice while exiting 0, once dropping a
whole baseline. See CORRECTIONS #24.

Seven for seven is not bad luck. Instruments here are written once, at the moment of understanding, and
then trusted. The fix is not more instruments; it is **re-auditing the ones that exist**, and asking
of each: what does it report when it cannot run, and what does it check that it does not claim?

## What is actually strong

The registers, the null discipline ("each repository running its own `train.py`"), and the
correction culture. Five reviews attacked this project and the thing that held up best was its
**record-keeping** — every finding above was *findable* because someone wrote down what they did and
why. The `[MIXED]` tag on `FAITHFULNESS`'s own summary is the project warning a reader about itself,
which is rarer than it sounds.

## The highest-risk thing remaining, which no gate covers

**The fleet would be launched from a configuration whose values were chosen for hardware it will not
run on.** Nine of twelve baselines carry a DataSphere-shaped adaptation; the host has 16 cores and
113 GB; and the failure mode of running the small configuration on the big machine is **silent** — it
produces valid-looking numbers of a 32×-rescaled PPG. Mechanism 1 and Mechanism 3 meeting at the
worst possible moment.

`MIGRATION-T4-TO-V100.md` exists to prevent exactly that, and it is a document, not a mechanism. The
mechanism — a host-profile dimension with the records stamping which profile ran — is unbuilt.

---

## Update 2026-09-05 — the closing section above is now STALE, and deliberately left in place

It read: *"the mechanism — a host-profile dimension with the records stamping which profile ran — is
unbuilt."* **It is built.** `family.py:host_profile()` resolves the selector and refuses a typo;
`resolved_descriptor()` applies the per-family overrides; `run_probe.sh` stamps `host_profile` into
both the record and the per-cell `effective_config.json`; `production_gates.py:628` validates the
declared overrides; `eval_provenance.py:91` checks the value against the known profiles.

Two things were nevertheless still wrong, and both are the mechanisms this document names:

- **Mechanism 2, two homes for one number.** The two stamp sites disagreed *in the default case* —
  `effective_config.json` wrote `null` where the record wrote `"datasphere"`. Every run made so far
  used that default, so every run produced two artifacts describing its host differently, and a
  reader could not distinguish that from a genuine mid-run change. Aligned; pinned by
  `tests/test_host_profile_gate_is_not_vacuous.py`.
- **Mechanism 1, and the silent direction.** Nothing refused to *infer* the host. A production-scale
  run with `NATIVE_HOST_PROFILE` unset would inherit `"datasphere"`, execute nine baselines'
  DataSphere-shaped values on a 16-core/113-GiB V100, and **succeed** — the failure mode this
  document calls out as the worst possible meeting of Mechanisms 1 and 3. The runner now refuses to
  start at `FRAMES >= 600000` without an explicit profile, and `gate_production_names_its_host`
  certifies the refusal. The gate is proven to FAIL when the guard is removed.

The stale paragraph stays because this file's own thesis is that documents describing state go
stale within hours, and a correction that erases its evidence teaches nothing.
