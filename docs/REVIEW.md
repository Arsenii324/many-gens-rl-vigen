# Code review — `many-gens-rl-vigen`

Assessed against the acceptance criteria in [`TASK.md`](TASK.md) §3, under the standard in
[`RIGOR.md`](RIGOR.md).

## State reviewed

| | |
|---|---|
| Date | 2026-08-09 |
| Path | `/Users/a2mogus/build-projs/many-gens-rl-vigen` |
| Git HEAD | `07c3f12355571d1f160e7d9d02f1563b827a8745` ("Initialize rlgen-core and rlgen-vigen with common protocol eval") |
| Working tree | **dirty — 24 paths**, including 3 deletions and most of the reviewed code as untracked |
| First-party source set | 79 files (`*.py`/`*.md`/`*.yaml`/`*.sh`, excluding `.git`, `third_party/`, `RL-ViGen-upstream/`, `__pycache__`) |
| Content hash of that set | `6e9027138dbbaf84ffbb2371bd98b6378aa00ecdc51bc88083e2ee9954a69584` |

Re-derive the hash before trusting this document against a changed tree:

```bash
cd /Users/a2mogus/build-projs/many-gens-rl-vigen
find . -type f \( -name '*.py' -o -name '*.md' -o -name '*.yaml' -o -name '*.sh' \) \
  -not -path './.git/*' -not -path './third_party/*' -not -path './RL-ViGen-upstream/*' \
  -not -path '*/__pycache__/*' | sort | xargs shasum -a 256 | shasum -a 256
```

**Note.** Most of the reviewed code is *untracked*, so it is not recoverable if lost and cannot be
diffed against any baseline. Committing it is the cheapest risk reduction available and should
happen before any edit.

## Method, and how much to trust each line

I read the spine myself (`eval.py`, `protocol.py`, `resolver.py`, `env.py`, `agent_loader.py`, the
five planning docs), then fanned out seven Sonnet reviewers over disjoint slices, then ran an
adversarial pass **myself** over their output rather than trusting it.

That pass mattered. The automated critic returned **zero kills**, which by `RIGOR.md` §0 is a
warning sign rather than a clean bill — an adversarial checker that never rejects anything is not
measurably adversarial. Re-reading the cited lines produced three corrections, recorded in §7.

Every finding below carries its verification provenance:

- **`[lead]`** — I opened the cited lines, or ran the cited command, in this session.
- **`[agent]`** — a slice reviewer cited them and I did not re-read. Treat as *probable*, not
  established.

---

## 0. The answer in one paragraph

The repo is a **carefully plumbed evaluation-smoke-test harness for twelve agent constructors**,
plus two complete training/eval pipelines lifted wholesale from the sibling `vigen-idaac` project.
It is real work and some of it is good. It is not the deliverable the brief describes. Of the seven
acceptance criteria, **R1, R2, R4, R5 and R7 have no implementation at all**; **R3 is violated at
the level of the task set, not merely the code** — the twelve baselines do not run on the same
benchmark; and **R6 is met for 9 of 12**. Everything currently in `results/` was produced by
randomly-initialised networks and is labelled as though it were not.

---

## 1. The headline: the twelve baselines are not on one benchmark

This is the largest finding and none of the seven reviewers stated it cleanly. It is not a code
bug; it is a structural fact that makes the requested comparison impossible as built.

- Ten baselines (`drqv2, svea, drq, curl, sgqn, ppg, ctrl, ibac_sni, rad, soda`) reach the
  environment through `rlgen-vigen/rlgen_vigen/env.py`, which accepts exactly four layer names —
  `['dcs', 'dmc_gb', 'dmc_gb2', 'rl_vigen_locomotion']` — and **raises `NotImplementedError` for
  anything else** (`env.py:32`, `env.py:65-66`). All four are DeepMind Control. Every stored result
  is `walker_walk`. **`[lead]`**
- Two baselines (`idaac`, `alda`) are copies of the sibling project's robosuite pipeline. Their
  own evaluator declares a different protocol outright: `EVAL_SCENES = tuple(range(10))`,
  `EPISODES_PER_SCENE = 10` → **100 episodes over 10 robosuite scenes, deterministic, reduced by
  IQM** (`algos/idaac/evaluate.py:24-26, :125, :193`). **`[lead]`** for the constants and the
  docstring; **`[agent]`** for the IQM line.
- That evaluator's docstring states the fork explicitly: *"We do not inherit `eval.py` for this —
  it raises NameError on exactly that scene switch (FINDINGS B2)."* **`[lead]`**

So the shared runner measures **DMC `walker_walk`, 3 episodes, raw mean, CSV**; the IDAAC/ALDA
path measures **robosuite Door/Lift, 100 episodes over 10 scenes, IQM, JSON**. These are not two
implementations of one protocol that happen to differ. They are two different benchmarks. No
amount of harmonising the eval *code* puts their numbers in one table.

**Provenance of the imported half.** `algos/alda/train.py:43-44` and `algos/alda/evaluate.py:31-32`
import `vigen_idaac.envs` / `vigen_idaac.logging_` / `vigen_idaac.evaluate` — the package name from
`../gen-rebuttal/vigen-idaac`, which does not exist in this tree under that name. **`[lead]`** The
directories were renamed (`rlgen_vigen/algos/idaac`, `.../alda`); the internal imports were not.
Both ALDA entry points therefore fail at import before a single env step.

This is fixable — it is a rename, not a rewrite — but it means the IDAAC/ALDA half has **never
been run inside this repo**, only in its parent.

---

## 2. Against the acceptance criteria

| | Requirement | Verdict | Evidence |
|---|---|---|---|
| **R1** | one `sh` script trains any baseline | **not met** | The repo's only non-vendor `.sh` is `submit_kaggle.sh`, and **both of its branches invoke `python -m rlgen_vigen.eval`** — it never trains anything. Ten of twelve baselines have no training code anywhere; `ppg.py` and `ibac_sni.py` define `act()` and no `update()`. **`[lead]`** |
| **R2** | per-baseline dir + README naming its environment | **not met** | Zero per-baseline READMEs. **Zero dependency manifests of any kind** — no `requirements.txt`, `pyproject.toml`, or `environment.yml` outside `third_party/`. **`[lead]`** |
| **R3** | evaluation identical across baselines | **violated** | §1 above, plus §3.1. Three incompatible eval paths, and the two halves are on different benchmarks. |
| **R4** | equal training length | **n/a — nothing trains** | No budget is declared anywhere; the two importable trainers (IDAAC, ALDA) carry the sibling project's own budgets. |
| **R5** | one plotting routine over tensorboard logs | **not met** | No plotting code. Tensorboard/W&B logging exists **only** inside the vendored `idaac/` and `alda/` packages and in the unused `cleanrl_ppg.py`; the shared `RunLogger` writes CSV and emits no tensorboard scalars at all. **`[lead]`** |
| **R6** | twelve genuine baselines | **9 of 12** | §3.2. `ctrl`, `rad`, `ppg` are not distinct algorithms as instantiated. |
| **R7** | clone → install → `sh` → curve | **does not run** | §5. |

---

## 3. Findings, by severity

### 3.1 Critical — results that look real and are not

**F1. Evaluation silently accepts an untrained network, and the artifact asserts otherwise.**
`load_or_instantiate_agent()` returns a freshly-initialised agent when `--model-path` is absent
(`agent_loader.py:16-21`), with no marker anywhere in the output. **There are no agent checkpoints
in the tree** — the only `.pt` files are DMCVGB colour data — so every one of the four data rows in
`results/` came from an untrained net. Meanwhile the co-emitted protocol card states
`checkpoint_selection: final`. That is not an omission; it is an artifact making a false claim
about weights that never existed. **`[lead]`**
*Scenario:* anyone runs `submit_kaggle.sh drqv2 walker_walk video_hard`, gets a clean CSV and a
protocol card, and has a number that is pure random-policy noise with a "final checkpoint" label.

**F2. `results/` is presented as results and is a smoke-test residue.** Six files, **four data
rows, two files empty (header only)**. The two empties — `drqv2_walker_walk_medium`,
`soda_walker_walk_video_hard` — are runs that produced zero episodes, i.e. failed, and nothing
flagged it. A run that emits an empty log and exits 0 is the failure `RIGOR.md` §6.1 is about.
**`[lead]`**

**F3. Five of twelve baselines cannot be constructed in any environment on this machine.**
`agent_loader` reaches `drqv2/svea/drq/curl/sgqn` via `from algos.X import ...`. That triggers
`RL-ViGen-upstream/algos/__init__.py`, which is one line — `from algos import pieg` — and
`pieg.py` imports `hydra` and `torchvision`. **`hydra` is installed in neither local venv**, and
the repo declares no dependencies. So importing *any* upstream algo eagerly drags in a
transitive dependency of an algorithm this repo never uses. Verified by executing the resolution
under `eval.py`'s exact `sys.path`. **`[lead]`**

**F4. Three incompatible evaluation harnesses.** `rlgen_vigen/eval.py` (3 episodes by default,
DMC only, raw summed reward, per-episode CSV) · `algos/idaac/evaluate.py` (100 episodes × 10
robosuite scenes, forced deterministic, IQM, JSON) · `algos/alda/evaluate.py` (imports the
sibling package; unimportable here). Episode count also disagrees *between entry points into the
same runner*: `eval.py` defaults to `--episodes 3`, `submit_kaggle.sh` passes `100`. **`[lead]`**

### 3.2 High — baselines that are not the algorithm they are named

None of these is hidden; each file says what it is. The defect is that `results/` would present
them as independent rows.

**F5. `ctrl` is a zero-override subclass of `CURL`.** The entire class body is
`super().__init__(**kwargs)` plus two comments (`algos/ctrl.py:8-12`). Its header states the intent
honestly — *"we wrap the baseline CURL network topology so it can load CTRL checkpoints"* — but
**no CTRL trainer exists**, so no CTRL checkpoint can be produced, and `--algo ctrl` today
evaluates literally CURL with a different RNG draw. **`[lead]`**
*(Downgraded from the automated critic's "critical". See §7.)*

**F6. `rad` adds nothing to SAC.** `class RAD(SAC)` with an `__init__` that calls `super()`, and
nothing else (`algos/rad.py:11-13`) — no random crop/translate, the transformation that *defines*
RAD. Because RAD's augmentation is a training-time operation on replay batches, an eval-only RAD
legitimately reduces to SAC; this is latent today and becomes a wrong number the moment R1 is
satisfied. **`[lead]`**

**F7. `ppg` is a DrQV2 actor under a PPG name, and the real PPG file is dead.** `algos/ppg.py` is
39 lines: a DrQV2 `Encoder`/`Actor`/`Critic`/`aux_critic` and an `act()`. No clipped surrogate, no
rollout storage, no phasic auxiliary phase, **no `update()` at all**. `cleanrl_ppg.py` (480 lines,
the actual algorithm) is **imported by nothing**. **`[lead]`**

### 3.3 High — dead and broken code that reads as live

**F8. Six duplicate algorithm files under `rlgen-vigen/rlgen_vigen/algos/` that nothing imports.**
`drqv2.py`, `svea.py`, `sgqn.py`, `curl.py` are byte-identical to the upstream copies; `drq.py`
diverges; `utils.py` (334 lines) has no upstream counterpart and is not reached under the
documented path setup. Every `from algos.X` in the repo resolves to `RL-ViGen-upstream/algos/`.
1,685 lines that a reader would reasonably edit to no effect. **`[lead]`**

**F9. One of those duplicates does not parse.** `rlgen-vigen/rlgen_vigen/algos/drq.py:211` has an
unclosed parenthesis — `torch.tensor(np.float32(np.log(init_temperature)).to(device)`. It is
**the only one of 63 first-party Python files that fails `ast.parse`**; the upstream copy has the
fix. Harmless only for as long as nobody "tidies" `agent_loader`'s bare imports into qualified
ones. **`[lead]`**

**F10. `resolve_setting.py` and `audit_tools.py` at repo root have never worked.** Both compute
`ROOT = Path(__file__).resolve().parent.parent`, which from the repo root resolves to
`/Users/a2mogus/build-projs/`, and look for `data/*.yaml` there. The yaml files live in
`rlgen-core/data/`, and no `data/` exists at either location. Running the exact command in each
script's own docstring raises `FileNotFoundError`. `resolve_setting.py` is additionally a
duplicate of the *working* `rlgen-core/rlgen_core/resolver.py`. **`[lead]`** for the path
computation and the yaml locations; **`[agent]`** for the byte-identity.

**F11. README's Quick Start cannot run.** It instructs `python src/audit_tools.py validate` and
four sibling commands. **`src/` does not exist.** This is the first page a supervisor reads.
**`[lead]`**

### 3.4 Medium

**F12. `--protocol paper:X` is a silent no-op.** `eval.py:29-31` builds `Protocol.canonical()` and
then only overwrites `.name`. A user asking for a published protocol gets the canonical one with a
different label written into the card. **`[lead]`**

**F13. The protocol card omits the fields that set the numbers.** `Protocol` has five fields;
`03_protocol_card.md` specifies roughly thirty-five. `action_repeat=2` and `frame_stack=3` are
hardcoded at `env.py:63`, episode count lives in argparse, and the commit is nowhere. For a
project whose thesis is that unreported protocol axes make numbers incomparable, this is
self-refuting — and `05_repo_architecture.md` predicted exactly this failure mode. It also
hardcodes `train_levels=200`, a Procgen concept, into every RL-ViGen card. **`[lead]`**

**F14. `RunLogger` violates its own declared schema.** `02_experiment_plan.md` defines `step` as
the training step / checkpoint index — the axis every post-hoc re-scoring in S1 groups by.
`eval.py:68` passes the *episode's step count*. The column that makes the whole re-scoring
programme possible holds episode length instead. **`[lead]`**

**F15. IDAAC checkpoints cannot be loaded through the shared harness.** `agent_loader.py:16-19`
returns `payload['agent']`; `idaac/train.py:34-52` writes `{"learner", "ret_rms", "config",
"update_idx", "frames", ...}` with no `agent` key. `KeyError` on the first real checkpoint.
**`[lead]`** for both key sets.

**F16. `audit_param_counts.py` reports `0` for exactly the algorithms it was written to handle.**
Its fallback branch iterates `target.__dict__` (the mock *wrapper*, whose only attribute is
`model`) rather than `target_model.__dict__`, and `isinstance(RAD_instance, nn.Module)` is False
because `SAC`/`AldaAgent` are plain objects. It prints `Total Parameters: 0` with no warning for
`rad`, `soda`, `alda`. **`[lead]`**

**F17. IDAAC training cannot use MPS on this machine.** `idaac/train.py:86-87`:
`torch.device(cfg.device if torch.cuda.is_available() or cfg.device == "cpu" else "cpu")` has no
MPS branch, so `--device mps` yields CPU. **This is not silent** — it prints a notice and rewrites
`cfg.device` so the checkpoint records the truth, with a comment explaining why. The defect is the
missing branch, not concealment. **`[lead]`** *(Corrected from the automated critic. See §7.)*

**F18. `05_repo_architecture.md` — the document `README.md` calls "the plan of record" —
contradicts the repo.** It defers `rlgen-vigen` to last ("only if there is time"), and its
algorithm × benchmark matrix lists PPO / PIE-G / UCB-DrAC / PLR — a set that does not overlap with
seven of the twelve baselines actually implemented. **`[agent]`**

---

## 4. Verification that cannot fail

Called out separately because green output from these is worse than no output: it is
*affirmative evidence of correctness where none exists*.

**F19. `run_mutants.py` is not mutation testing.** All five "mutants" replace `agent.act` with a
hand-written function that directly exhibits a defect, then assert inline, three lines later, that
the defect is present. Production code is never mutated; `test_eval_invariants.py` — the actual
suite — is never run. The bounds mutant asserts `5.0 > 1.0`; the in-place mutant is killed by a
NumPy casting rule; the PRNG mutant is killed by `os.urandom`. The reported **"100% kill rate,
60/60"** would be identical against an empty test suite. **`[lead]`**
The correct construction, and a ten-mutant catalogue specific to this repo, is
[`RIGOR.md`](RIGOR.md) §7.

**F20. `test_normalization.py` cannot fail.** Zero `assert` and zero `sys.exit` in the file; the
`__main__` block prints a tally and returns 0 whether 0/8 or 8/8 pass. It also silently omits
`rad`, `soda`, `idaac`, `alda` from its algorithm list. **`[lead]`**

**F21. `test_eval_invariants.py` tests a shape the pipeline never produces.** Its `DummyEnv`
hand-declares `shape = (3, 84, 84)` while the real wrapper is constructed with `frame_stack=3` on
RGB. Fixtures must be derived from the real factory, never re-declared (`RIGOR.md` §6.2).
**`[lead]`** for the hand-declaration; the exact real channel count is in §8.

---

## 5. Where the clone-to-curve path stops

Walking `TASK.md` R7 concretely, it stops in three different places depending on the baseline —
and in the worst case it does not stop at all, which is the dangerous one.

1. **`git clone`** — succeeds.
2. **install dependencies** — *no instruction and no manifest exists* (F14/R2). Guessing, you land
   on `hydra` missing, and `drqv2/svea/drq/curl/sgqn` cannot be imported (F3).
3. **run the `sh` script** — `submit_kaggle.sh` is the only one, and it evaluates rather than
   trains (F1/R1). For a baseline that *does* import, it **completes successfully** and writes a
   plausible CSV of untrained-network noise labelled `checkpoint_selection: final` (F1). This is
   the real hazard: the pipeline does not fail, it silently produces a wrong result.
4. **IDAAC / ALDA instead** — `env.py` raises `NotImplementedError` for robosuite (§1); their own
   trainers must be used; ALDA's cannot be imported at all (`vigen_idaac`); IDAAC's checkpoints
   cannot be read back by the shared loader (F15).
5. **tensorboard → shared plotter** — neither exists (R5).

---

## 6. What is good here, and worth keeping

A review that lists only defects will mislead the next reader about where the value is.

- **`rlgen-core/rlgen_core/resolver.py`** is the best code in the repo. Treating a setting name as
  a `(stack, layer, name)` path and **raising on ambiguity rather than guessing** is the right
  design, and its `check()` command cross-validates the machine-built index against the
  hand-written collision list in both directions. Keep it; it needs no rework.
- **The single shared episode loop in `eval.py`** is structurally correct even though its protocol
  is wrong: it takes the agent through one `act()` interface and does not branch on algorithm. That
  is the property R3 needs. Fix the protocol around it, not the loop.
- **The twelve-constructor adapter layer** is genuinely fiddly work — eight different constructor
  signatures unified behind one `act(obs, step, eval_mode)`. It is reusable once real checkpoints
  exist.
- **`algos/alda/eval_dz.py`** is a careful, auditable transcription of another script's eval
  protocol — good practice, though see §8 for what it is *not*.
- **`uncertainty_register.md`** is an unusually honest handover document. Most of its items are
  real, and several (A1 normalisation cross-loading, C3 the VIB bottleneck dimension, F3 replay
  dtype) are worth carrying forward verbatim.

---

## 7. Corrections I made to my own reviewers

Recorded because the corrections are as informative as the findings, and because a review that
does not say where its own process failed is asking to be trusted rather than checked.

| Claim as returned | Correction |
|---|---|
| `ctrl` alias is *"the worst case of requirement 3 being violated"*, **critical** | **Downgraded to high.** `ctrl.py`'s own header declares the aliasing and its purpose (loading CTRL checkpoints). It is a stated eval-only shim, not a disguise. The real defect is narrower: no CTRL trainer exists, so the shim's purpose is unrealisable. |
| `idaac/train.py` *"silently downgrades any 'mps' request to CPU"* | **Corrected.** The code prints a notice *and* rewrites `cfg.device` so the checkpoint records what actually ran, with a comment explaining that a previous run "silently demoted to CPU claimed cuda forever after". It is a deliberate anti-silence measure. The finding is the missing MPS branch (F17), not concealment. |
| `rad`/`ppg`/`ctrl` merged into one **critical** finding | **Split.** They fail for different reasons at different severities (F5, F6, F7). Merging them inflated two of the three. |
| architectural_review: *"`RL-ViGen-upstream/algos/utils.py` — imported as `import utils`"* | **False.** That file does not exist. `import utils` resolves to `RL-ViGen-upstream/utils.py` (repo root). Verified by resolving under `eval.py`'s exact `sys.path`. |
| The critic returned **zero kills** | Treated as a process failure, not a result — see *Method* above. |

Other corrections to the two AI handover docs (`architectural_review.md`,
`uncertainty_register.md`), each **`[agent]`** unless noted:

- CURL and CTRL are listed under the "SAC backbone / `modules.py`" family with unit-scale
  normalisation. The production `CURLAgent` subclasses `DrQV2Agent` with its own encoder using
  **zero-centred** `obs/255 − 0.5`, and never touches `modules.py` or `sac.py`. Only RAD and SODA
  run on that stack. This inverts the normalisation-parity table.
- `uncertainty_register.md` B2 states `sample_action` is **not** wrapped in `torch.no_grad()`.
  `sac.py:74-84` wraps both `select_action` and `sample_action`.
- `architectural_review.md` reports *"100% baseline pass, 100% mutant kill rate (60/60)"* as a
  verification result, with no caveat — while the same author's `uncertainty_register.md` E4 says
  one of those kills "is vacuous". See F19. **`[lead]`**
- Neither document mentions any of the five requirements the repo was commissioned to satisfy.
  Both are entirely about eval-path plumbing.

---

## 8. `eval_dz.py` — and why it is not what it says it is

`algos/alda/eval_dz.py` changes two of the open questions in `TASK.md` §6, and it was carried in
from the sibling project. Its docstring states: **`[lead]`**

> DZ's evaluation protocol, implemented exactly, for both the ALDA and IDAAC ports. […] Our own
> protocol (100 episodes over 10 scenes, IQM) is a superset of DZ's (**10 episodes on scene 0,
> mean**) […] DZ's source, `ext/alda/Nd_ln.py:593-665`, reproduced here so the correspondence is
> auditable.

Three consequences:

1. **CORRECTED — this is not the group's reference evaluation.** `Nd_ln.py` is group-authored
   (Russian comments) and does run on RL-ViGen robosuite, but the repo owner has confirmed it is
   *not* offered as an example of good RL-ViGen eval. So `eval_dz.py` faithfully transcribes *a*
   script's protocol, not a reference one. `TASK.md` §6 Q1 stands as written: we have neither the
   reference eval nor the reported defect.
2. **DZ's protocol is 10 episodes on scene 0, reduced by mean.** That answers §6 Q5's "what are
   the numbers" for the RL-ViGen half, and it is a much weaker protocol than the 100-episode
   10-scene one — worth proposing an upgrade, with the bimodality argument from
   `../gen-rebuttal/vigen-idaac/CLAIMS.md` §E as the reason.
3. The transcription flags a specific subtlety — *"terminal step IS counted: `not_done` is read
   BEFORE the update"* — exactly the class of off-by-one that Arsenii's "косяк" is likely to be.
   Worth raising directly.

**Caveat:** the file's docstring cites `tests/test_dz_eval_parity.py` as checking it against DZ's
actual source text. **That test does not exist in this repo** **`[agent]`** — it is in the sibling
project, or nowhere. Confirm before relying on the transcription.

---

## 9. What I did not verify

Stated plainly so nobody reads absence as clearance.

- **Nothing was executed.** No agent was constructed, no environment stepped, no training run. All
  findings are from reading, from `ast.parse`, and from import-resolution under `eval.py`'s exact
  `sys.path`. `hydra` being absent locally blocks constructing the five upstream-backed agents.
- **The real observation channel count** (`env.py` passes `frame_stack=3`, but
  `loco_wrapper.py:130`'s `FrameStackWrapper` is **commented out** and stacking is delegated to
  `make_env`). The AI doc claims `(9, 84, 84)`. Unconfirmed. F21 stands regardless — the defect is
  the hand-declared fixture, not the number.
- **Per-paper hyperparameter fidelity.** `uncertainty_register.md` §C is right that constructor
  values were never cross-checked against published tables. Still true. One checked point: the RAD
  and SODA `DummyArgs` blocks agree with each other on every shared key **`[agent]`**.
- **`fix_*.py`** (four one-shot source rewriters). Not run, by design. Whether they are idempotent
  and whether they have already been applied is open **`[agent]`**.
- **`protocol_variance.py`, `audit_architectures_deep.py`, `render_scenes.py`,
  `rlgen-core/data/*.yaml`** — reviewed by slice agent only.
- **`third_party/rl-iter/`** — not reviewed at all. Nothing in the first-party tree imports it.

---

## 10. Most of R1/R2/R4/R5 does not need designing — there is a template

Recorded late: I initially wrote off the two `~/Downloads` folders on the strength of their names.
They are **the same repository** — `IBAC_SNI_torch/train-procgen-pytorch` is
`train-procgen-pytorch_example` with one baseline added — and together they are a worked example of
this brief. Full analysis in [`TASK.md`](TASK.md) §5. The three things it settles:

1. **The layout** (`agents/<algo>.py` · shared `common/` · `hyperparams/<bench>/config.yml` ·
   `<env>.sh` · `logs/<bench>/<env>/<algo>/<run>/` · one `train.py`). Adding a baseline touched
   exactly two new files plus a config entry.
2. **The R4 mechanism.** A `.sh` script names a *hyperparameter set*, not an algorithm;
   `train.py` reads `algo` out of it. `easy-200-ibac` is `easy-200` plus only `beta`, `sni`,
   `sni_lambda` — all eighteen shared keys byte-identical. Equal training conditions become the
   default a baseline must explicitly opt out of, in a diffable file. Adopt this.
3. **A live demonstration of the anti-pattern**, which is the most useful part. `bigfish.sh`
   promises *"eval and logging identical to LSP (`Eval/avg_reward`, `Eval/std_reward` every 5th
   rollout)"*. In fact the eval loop lives **inside `agents/ppo_ibac.py:160-203`**;
   `agents/ppo.py` has **zero** eval-related lines; `common/logger.py` records only training
   statistics; and the eval env is rebuilt in the agent with `VecNormalize` and `num_levels=0`
   (full distribution). So the added baseline has an eval curve, the baseline it is compared
   against has none, and two protocol axes are set invisibly in an agent file. **`[lead]`**

That last point is the failure DZ's `!ВАЖНО!` paragraph legislates against, occurring inside the
group's own reference — and it is the strongest available argument for the *structural* form of
R3 (`TASK.md` §3): the evaluator must not be able to see which algorithm it is running.

It also raises three questions that must go to DZ before the shared evaluator is written — what
"LSP" is and whether its keys are the standard; held-out vs full-distribution eval; normalised vs
raw eval reward. Added as `TASK.md` §6 Q8–Q10.

## 11. Recommended order of work

Ordered by risk removed per hour, not by severity.

1. **Commit the tree.** 24 uncommitted paths hold most of the reviewed code. Nothing else is safe
   until this is done.
2. **Quarantine the false results.** Delete `results/`, or move it to `results/_smoke_untrained/`
   with a README saying what it is. It is the one artifact that can mislead a reader today.
3. **Make F1 impossible, not merely documented.** Evaluation without a checkpoint requires an
   explicit `--allow-untrained`, and the flag is stamped into the CSV and the card. This is
   mutant M10 in `RIGOR.md` §7.4 and it is ~20 lines.
4. **Delete the six dead duplicates** (F8/F9), removing the unparseable file with them.
5. **Decide the benchmark question (§1)** before writing any more code. Either the ten DMC
   baselines move to robosuite, or IDAAC/ALDA move to DMC, or the repo declares two benchmark
   tracks and stops claiming one table. This is a research decision, not an engineering one, and
   it should go to DZ with `TASK.md` §6 Q3/Q4 — alongside Q8–Q10 from §10 above.
6. **Then** R1/R2/R4/R5, against the §10 template rather than from scratch — but with the eval
   loop and the tensorboard tags in `common/`, never in an agent. This is the bulk of the
   remaining work and it is wasted if step 5 goes the other way.
