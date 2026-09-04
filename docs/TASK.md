# many-gens-rl-vigen — task of record

> **Status of this document.** This is the *contract*, not a plan and not a report. It records
> what was asked, by whom, in their words, and turns it into criteria that can be checked
> mechanically. Everything downstream — the repo layout, the review, the experiment log — is
> answerable to this file. If the repo and this file disagree, one of them is wrong and the
> disagreement is itself a finding.
>
> Working standard for *how* the work is done: [`RIGOR.md`](RIGOR.md).
> State of the code against this contract: **`python scripts/requirements.py`**, which
> recomputes R1-R7 and refuses to grade the three that are not mechanically decidable.
> [`REVIEW.md`](REVIEW.md) is the standing judgement behind them and is a **dated
> snapshot** (2026-08-09, at a different repository path) — read it for reasoning, not for
> current status. *Amended 2026-08-19: this line pointed only at the snapshot, so the
> first question a reader asks had a ten-day-old answer. R1 reads "not met" there and
> thirteen `train.sh` files now exist.*

| | |
|---|---|
| Recorded | 2026-08-09 |
| Source | supervisor ("DZ") group message, forwarded verbatim by the repo owner |
| Code under contract | `/Users/a2mogus/build-projs/many-gens-rl-vigen` (a second agent was still finishing it when this was written) |
| Sibling project | `../gen-rebuttal/vigen-idaac` — IDAAC + ALDA on RL-ViGen robosuite; shares the ALDA/IDAAC ports and the eval-discipline lessons |

---

## 0. Why this document exists

The brief arrived as a chat message: a list of links, a list of baselines, and one paragraph of
repository principles. A chat message is not a specification. Three things in it are load-bearing
and easy to lose:

1. **"код эвалюэйшена должен быть ИДЕНТИЧЕН у всех бейзлайнов"** — evaluation identity is the
   *point* of the repo, not a nicety. Every other requirement serves it.
2. **The use-case sentence** — clone → install one baseline's deps → run one `sh` script. That
   sentence is the acceptance test for the whole repo, and it is checkable.
3. **A known defect exists in the supervisor's own reference eval**, reported by a group member
   and not yet shared. Building on an eval with an unshared defect is the single most expensive
   mistake available here.

None of the three survives being remembered rather than written down.

---

## 1. The brief, verbatim

Reproduced without edit, including its original numbering (which skips `9` and repeats `2`).

> 📎 Бенчмарки:
>
> 1) RL-vigen https://github.com/gemcollector/RL-ViGen/tree/master
> 2) procgen(torch version) https://github.com/joonleesky/train-procgen-pytorch
> 2) KAGE https://github.com/CognitiveAISystems/kage-bench
>
> Бейзлайны:
>
> 1) PhasicPolicyGradient PPG https://docs.cleanrl.dev/rl-algorithms/ppg/#overview
> 2) RAD https://arxiv.org/pdf/2004.14990
> 3) IBAC-SNI (torch версию прикрепил к сообщению) https://github.com/microsoft/IBAC-SNI
> 4) DrQ
> 5) DrQ_V2
> 6) CURL - https://arxiv.org/pdf/2004.04136
> 7) IDAAC - https://arxiv.org/abs/2102.10330
> 8) ALDA - https://arxiv.org/abs/2001.01046
> 10) SVEA - https://arxiv.org/abs/2107.00644
> 11) CTRL -https://arxiv.org/abs/2106.02193
> 12) SGQN - https://arxiv.org/pdf/2209.09203 (код https://github.com/SuReLI/SGQN)
> 13) SODA - https://arxiv.org/pdf/2011.13389 (код https://www.nicklashansen.com/SODA/)
>
> Просто полезные репо:
> https://github.com/nicklashansen/dmcontrol-generalization-benchmark
>
> ;;; Для Арсения: Обсудить eval на RL Vigen + дать эталонный код ;;;
>
> Для Арсения @Arsenii629570 : у тебя репозиторий RL-Vigen есть, эталонный evaluation тоже, но
> ты, кажется, говорил, что нашел в моём эвале какой то косяк — продублируй его в личку
> пожалуйста.
>
> Для всех как и обещал, общие принципы построения репозитория (можно использовать как правило
> для клода при обустройстве репо):
>
> Репозиторий с бенчамарком должен содержать папку с бейзлайнами для того, что бы можно было
> удобно запускать любой бейзлайн путём запуска sh скрипта с обучением. Все бейзлайны должны
> быть структурированно разложены в репо, не перемешаны в кучу, репозиторий должен оставаться
> читаемым. Для запуска каждого бейзлайна может потребоваться своё окружение — об этом надо
> писать в readme (инструкция) в папке каждого бейзлайна.
>
> Сценарий использования репозитория такой: человек с запросом провести эксперимент на этом
> бенчмарке для бейзлайна 'X' делает гит клон, ставит сперва зависимости требуемые для запуска
> обучения 'X' на бенчмарке, а затем просто sh скриптом запускает 'X' или любой другой бейзлайн
> если захочет.
>
> !ВАЖНО! код эвалюэйшена должен быть ИДЕНТИЧЕН у всех бейзлайнов для обеспечения ЧЕСТНОГО
> сравнения, то есть мы одинаковым образом бегаем по среде, одинаково часто, одинаковое
> количество эпизодов, одинаково собираем ревард и одинаково его усредняем и одинаково логгируем
> под одинаковыми ключами. Длина обучения тоже в идеале должна быть одинаковая, если это не
> противоречит каким то особенностям обучения алгоритма.
>
> Что бы код отрисовки бейзлайнов был также одинаковый, скачали лог тензорборда, и одним
> алгоритмом отрисовки на всех отрисовали эвал кривую.

---

## 2. Faithful rendering

**Benchmarks.** Three: RL-ViGen; Procgen via the PyTorch port `joonleesky/train-procgen-pytorch`;
KAGE-Bench (the lab's own).

**Baselines.** Twelve: PPG, RAD, IBAC-SNI, DrQ, DrQ-v2, CURL, IDAAC, ALDA, SVEA, CTRL, SGQN, SODA.

**Also useful.** `nicklashansen/dmcontrol-generalization-benchmark`.

**Repository principles.**

- The benchmark repo contains a **baselines folder**, so that any baseline can be launched
  conveniently *by running one `sh` training script*.
- Baselines are **laid out structurally, not mixed into a heap**; the repo must stay readable.
- Each baseline may need **its own environment**; that goes in a **README inside that baseline's
  own folder**.
- **The use case:** someone who wants to run an experiment for baseline `X` on this benchmark
  does `git clone`, installs the dependencies needed to *train* `X` on the benchmark, and then
  simply launches `X` — or any other baseline they fancy — with an `sh` script.
- **!IMPORTANT!** The evaluation code must be **IDENTICAL** across all baselines, to guarantee a
  **FAIR** comparison. Concretely, identical in all six of: how we step through the environment;
  how often; how many episodes; how we collect reward; how we average it; how we log it and under
  which keys.
- Training length should ideally be identical too, unless some property of an algorithm's
  training forbids it.
- So that the plotting is also identical: download the tensorboard logs and render every
  baseline's eval curve with **one** plotting routine.

**Side thread.** Arsenii holds an RL-ViGen checkout and a reference evaluation, and reported to DZ
that he had found a defect ("косяк") in DZ's eval. DZ asked him to forward it privately. We do not
have it.

---

## 3. Derived requirements, as acceptance criteria

Each requirement is written so that a script can decide whether it is met. "Looks fine" is not an
outcome. Where a criterion is *structural* — it makes the failure impossible rather than merely
absent — that is noted, because structural criteria are the ones that survive six months of edits.

### R1 — One `sh` script trains any baseline

> `baselines/<X>/train.sh` exists for every `X` in §2 and starts training.

**Check.** From a clean clone, after following only `baselines/<X>/README.md`:
`bash baselines/<X>/train.sh --smoke` returns exit code 0, and afterwards there exists at least
one checkpoint file and at least one log row. The `--smoke` path must run the *same code* as a
real run with a tiny step budget — a separate smoke code path proves nothing about the real one.

**Anti-criterion.** A script that requires the caller to already know a `PYTHONPATH`, a conda env
name, or an undocumented flag does not satisfy R1. The knowledge has to be *in* the script or *in*
that baseline's README.

### R2 — Structural separation, per-baseline README

> One directory per baseline; a `README.md` in each naming its environment and dependencies.

**Check.** `ls baselines/` enumerates exactly the baseline set. Each contains a `README.md` that
names: the Python version, the dependency manifest to install, any system dependency (MuJoCo,
EGL, CARLA), and the exact command to install it. Mechanically: assert the README contains a
fenced install block and that the block's first command is runnable.

**Anti-criterion.** A baseline whose code is reachable only through a path in another baseline's
directory is not separated.

### R3 — Evaluation comparability (relaxed from identity, owner, 2026-08-26)

> ~~Identical across baselines in all six respects: stepping, frequency, episode count, reward
> collection, averaging, logging keys.~~
>
> **Evaluation code should produce metrics that are fully on the same axes and directly
> comparable.**

> **This is a deliberate relaxation of a verbatim supervisor requirement, and it needs DZ's
> agreement rather than being absorbed quietly.** The brief says *"код эвалюэйшена должен быть
> ИДЕНТИЧЕН у всех бейзлайнов"* — the evaluation **code** identical. The owner's decision, taken
> 2026-08-26, relaxes the demand from **code identity** to **metric comparability**: the numbers
> must sit on the same axes and be directly comparable; the code producing them need not be one
> function.
>
> **Why the relaxation, and why it is not a weakening.** Code identity and the hermetic null are in
> direct conflict — [C53](CONSTRUCTION.md#c53) records that conflict rather than resolving it, and
> [C72](CONSTRUCTION.md#c72) is what it costs concretely: a single evaluator can only read the five
> baselines that share RL-ViGen's agent interface, so *enforcing* code identity would mean either
> abandoning seven baselines or building the shared adapter this project exists to refuse. The
> relaxed form keeps what the requirement was **for** — a fair comparison — and drops the
> implementation constraint that made it unreachable. The brief's own justification is
> *"для обеспечения ЧЕСТНОГО сравнения"*: fairness is the requirement, identity was the proposed
> mechanism.
>
> **What now carries the burden — corrected later the same day.** This first said
> [`COMPARABILITY_CONTRACT.md`](COMPARABILITY_CONTRACT.md), *"under the new R3 that document **is**
> R3"*. **Half of it cannot be.** Its §1–§10 audit the **retired `rlgen/` port** — 31 references —
> and its argument rests on *"every baseline's environment interaction … goes through
> `rlgen/envs.py`'s construction path"* plus four shared adapter classes. The null became the clone
> on 2026-08-17; there is no shared construction path and there are no adapters, so that evidence
> does not transfer ([C30](CONSTRUCTION.md#c30)). R3's burden had been assigned to a document about
> a system that no longer runs.
>
> The burden now sits on **[`PART2-METRIC-INVENTORY.md`](PART2-METRIC-INVENTORY.md)** — the
> reasoning of record for what each emitted quantity *is*, derived from the emitting code — and on
> **`scripts/audit_comparability_seam.py`**, its re-derivable regression check on the architecture
> that actually runs. [C76](CONSTRUCTION.md#c76) holds the result.
>
> **Grading, 2026-08-26: R3 is NOT MET, and now for a checkable reason — one that is the owner's
> to close.** The relaxation changed the wording, not the state; but the old predicate graded the
> *withdrawn* requirement, counting `collect_metrics.py`'s per-baseline parsers, which under the
> relaxed R3 are not a violation at all but the hermetic null working as designed.
> `scripts/requirements.py`'s R3 now grades the axes instead, across eleven of them:
>
> **Ten axes agree or split only in ways the claim already declares. One does not: the
> `evaluation scene set`.** `scripts/eval_across_scenes.py` sweeps ten scenes, nine held out, while
> **all seven** non-native evaluators build their env with `scene_id=0` and vary only the visual
> regime. So the five natives report *mean return over ten scenes* and the other seven report
> *mean return at scene 0*. That is a **UNITS** split — different estimands, not one estimand at
> different precision — and unlike the CONDITIONS splits (resolution, frame stack, truncation,
> action distribution, observation layout) it cannot be repaired by declaring and quantifying it.
> It is [C72](CONSTRUCTION.md#c72) restated as the axis it always was.
>
> **The decision this hands over.** Either the seven evaluators gain a scene sweep — real work in
> seven places, and a deviation in each clone — or the endpoint is redefined to what all twelve can
> already produce. Both are live; neither is a conversion anyone can apply to existing numbers. See
> [`PREMISES.md`](PREMISES.md) P4, which holds the evaluation-protocol choice this sits under.
>
> **And the predicate cannot ever grade it MET**, by construction and with a test that breaks it:
> driven to its most favourable input — every axis uniform, nothing underived — it stops at
> **NEEDS JUDGEMENT**. Whether the axis enumeration is *complete* is a judgement about unknown
> unknowns, and the null is that two baselines' numbers are not the same quantity until shown to
> be. Owner, 2026-08-26: *"the reasonable absence of unknown unknowns should be established before
> they're concluded same."* A script may narrow that gap; it may not close it.
>
> **What this does not relax.** The six respects the brief enumerates are still the axes on which
> comparability must be *shown* — stepping, frequency, episode count, reward collection, averaging,
> logging keys. The change is that showing two baselines agree on them is now sufficient, where
> before only one shared function was.

**Structural check (preferred).** There is **exactly one** function in the repo that steps an
environment for evaluation, and it receives the algorithm only as an opaque callable:

```python
def evaluate(env_factory, policy: Callable[[Obs], Action], protocol: Protocol) -> list[EpisodeRecord]
```

If the evaluator cannot see *which* algorithm it is running, it cannot treat two algorithms
differently. That is worth more than any amount of review discipline. Mechanically: a test asserts
that the count of eval-stepping loops in the tree is 1, and that `evaluate` has no parameter, and
closes over no global, that could carry an algorithm identity.

**Data check.** Every eval record carries the protocol hash that produced it. Two records with the
same protocol hash but different `n_episodes`, different `deterministic` flag, or different
aggregation are a contradiction and must fail a CI check rather than be averaged.

**Anti-criterion.** Any per-algorithm `evaluate.py`, any `eval_<person>.py`, any `if algo ==` in
an eval path. Each is a direct violation regardless of whether its numbers happen to agree today.

### R4 — Equal training length, or a stated reason

> Same budget across baselines unless the algorithm forbids it.

**Check.** One declared budget in the shared protocol, expressed in **environment frames** with
`action_repeat` folded in explicitly (frames, not "steps" — "steps" means agent steps in some
codebases and simulator steps in others, and that ambiguity has already cost this group real
time in `../gen-rebuttal/vigen-idaac`). Every run's final frame count is within a stated tolerance
of the budget, or the run carries a machine-readable `budget_exception` naming the algorithmic
reason. No exception without a reason string.

**Note.** On-policy (PPG, IDAAC, IBAC-SNI) and off-policy (DrQ, DrQ-v2, CURL, RAD, SODA, SVEA,
SGQN, CTRL, ALDA) methods consume frames very differently per gradient step. Equal *frames* is the
right invariant; equal *updates* is not, and equal *wall-clock* is not. Say which one a table
holds fixed, every time.

### R5 — One plotting routine over tensorboard logs

> **Deferral LIFTED, owner 2026-08-28.** *"I don't have a 'final results table' in mind; you can
> build metrics however you see … and the final presentation-ready table, or anything, I'll decide
> when you have your best results."* So the shape is no longer a precondition — it is delegated,
> and the owner's decision moves to **approving the result** rather than specifying the table. The
> tiered model below still governs what may share a column.
>
> *(Superseded: "Deferred, owner 2026-08-26 — decide once the results table's shape is settled. R5
> is not blocking and its answer depends on what the table contains.")*
>
> **But one assumption in the criterion below is wrong and should not survive the deferral.** It is
> written as though there were a single common metric set every baseline emits. The owner's model is
> the opposite: **each algorithm has a wide set, of which only part is shared.** Three tiers, not
> one —
>
> | tier | example | comparable across |
> |---|---|---|
> | **common** | episode return, success rate | all twelve |
> | **family** | `explained_variance`, `clip_fraction` (on-policy); contrastive loss; continuous-head entropy | within a family only |
> | **individual** | a method's own auxiliary term | that baseline alone |
>
> This is **not new** — it is [C28](CONSTRUCTION.md#c28) and
> [`PART2-METRIC-INVENTORY.md`](PART2-METRIC-INVENTORY.md) §6, *"the family-tier diagnostics:
> coverage declared before wiring"*, with the functions already in `scripts/metrics.py`. What the
> owner's answer settles is that the tiering is the **intended** model rather than a concession, so
> R5's "identical tag names" must mean *identical within a tier*, and a plotting routine has to know
> which tier it is drawing. A test asserting one global canonical tag set would encode the wrong
> model.

> Download tensorboard logs; render every baseline's eval curve with one algorithm.

**Check.** Every baseline writes eval scalars to tensorboard under **identical tag names**
(a single constants module owns the tag strings; no string literals at call sites). One script
consumes a directory of event files and emits the figure set, with no per-algorithm branch. A test
asserts the tag set emitted by each baseline is equal to the canonical set.

### R6 — Baseline coverage

> All twelve present as genuine implementations.

**Check.** For each baseline, a written statement of what makes it that method rather than its
backbone: which loss terms, which auxiliary heads, which augmentation. A baseline that reduces to
`class X(Y): pass` at both train and eval time is an **alias**, and must be reported as an alias
in the results table rather than as an independent row. Aliases are not forbidden — undeclared
aliases are.

### R7 — The clone-to-curve path works

> The use-case sentence, executed.

**Check.** A single documented sequence, run on a clean machine by someone who has not seen the
repo, that goes: clone → install baseline `X` → `sh` script → tensorboard log → shared plotter →
eval curve. Timed and recorded. This is the acceptance test for the repo as a deliverable, and it
is the one that will actually be attempted by the supervisor.

---

## 4. Scope decisions we have taken (not DZ's)

These are ours and can be revised; they are recorded so the revision is deliberate.

| # | Decision | Reason |
|---|---|---|
| S1 | **Cross-benchmark compatibility is dropped "to a strong extent."** The eval contract binds baselines *within* RL-ViGen; it is not engineered to also fit Procgen and KAGE unchanged. | Owner's call. The three benchmarks differ in action space, episode structure and observation semantics; a contract general enough for all three is general enough to be vacuous. Revisit only if a cross-benchmark table is actually wanted. **Note:** this drops the *contract*, not the *layout* — §5's reference repo is Procgen-based and its directory structure, config mechanism and logging tree are benchmark-agnostic and should be copied. |
| S2 | **RL-ViGen first.** | It is the benchmark the group already has running (`../gen-rebuttal/vigen-idaac`), so the ALDA and IDAAC ports and the eval lessons transfer directly. |
| S3 | The repo's earlier framing as a *protocol-audit paper kit* (`01_paper_outline.md`, `02_experiment_plan.md`, `03_protocol_card.md`, `audit.yaml`) is **subordinate** to the benchmark-repo brief. | The audit is useful as a *config source* for `--protocol paper:X`, which is exactly what `05_repo_architecture.md` already concluded. It is not the deliverable DZ asked for. |
| S4 | Local compute is **M2 Pro, MPS, never CUDA**. Anything needing millions of frames, JAX-CUDA, or Procgen goes remote. | `../../docs/local-envs.md`. This constrains what "training length identical" can mean in a local smoke test. |

---

## 5. The reference implementation — read this before designing anything

The two folders in `~/Downloads` are **two forks of one upstream**,
`joonleesky/train-procgen-pytorch`. `IBAC_SNI_torch/` carries an added IBAC-SNI baseline;
`train-procgen-pytorch_example/` carries unrelated local work (a `find_principal_component`
method, a `noise_amplitude` parameter, an `experiments/<algo>/<env>.sh` layout). They are **not** a
clean before/after pair, so the diff between them is not a measure of what adding a baseline
costs — every claim below was checked against the IBAC copy directly. Together they are still the
closest thing to a **worked example of this brief**, and DZ's own words —
*"можно использовать как правило для клода при обустройстве репо"* — point here.

### 5.1 The layout to copy (answers R1, R2, R5)

```
agents/          base_agent.py, ppo.py, ppo_ibac.py     <- one file per baseline, side by side
common/          logger.py, storage.py, model.py, policy.py, policy_ibac.py, env/
hyperparams/procgen/config.yml                          <- every hyperparameter set, one file
<env>.sh   (bigfish, heist, jumper, dodgeball, plunder) <- the launch scripts
   or experiments/<algo>/<env>.sh                       <- the reorganised form
logs/procgen/<env>/<algo>/<run-name>/                   <- events.out.tfevents.* + log.csv
train.py                                                <- one entry point for every baseline
```

**The IBAC baseline is contained in two new files** — `agents/ppo_ibac.py` (203 lines vs
`ppo.py`'s 150) and `common/policy_ibac.py` (78 vs 37) — plus one config entry, the per-env `.sh`
scripts, and a dispatch branch in `train.py`. `logger.py`, `storage.py`, `model.py` and
`train.py`'s env construction are shared and unchanged. That containment *is* the readability
requirement (R2), implemented rather than asserted.

### 5.2 How a baseline is selected (answers R4)

The `.sh` script does not name an algorithm. It names a **hyperparameter set**:

```bash
python train.py --env_name bigfish --distribution_mode easy \
  --param_name easy-200-ibac --exp_name ibac_sni \
  --seed ${SEED} --num_levels 200 --num_timesteps 25000000
```

`train.py` then reads `algo = hyperparameters.get('algo', 'ppo')` and dispatches. And the config
entry for a new baseline is **the base entry plus only its method-specific keys**:

> `easy-200-ibac` = `easy-200` + `beta: 1e-4`, `sni: True`, `sni_lambda: 0.5`. Of the eighteen
> shared keys — `n_envs`, `n_steps`, `epoch`, `gamma`, `learning_rate`, `architecture: impala`, … —
> **seventeen are byte-identical**; the eighteenth is `algo`, which is the selector `train.py`
> dispatches on rather than a hyperparameter.

**This is the mechanism R4 should adopt.** Equal training conditions become the default that a
baseline must explicitly opt out of, key by key, in a diffable file — rather than a convention
someone has to remember. Training length (`--num_timesteps 25000000`) and seeds (`1 2 3`) sit on
the command line, identical across scripts.

### 5.3 The anti-pattern to *not* copy — and it is the one DZ's `!ВАЖНО!` paragraph forbids

The `bigfish.sh` header states the intended convention:

> `# Eval и логирование идентичны LSP (Eval/avg_reward, Eval/std_reward каждый 5-й rollout).`

The code does not implement it as a shared convention. Verified:

- **The eval loop lives inside `agents/ppo_ibac.py:160-203`** — `evaluate(num_episodes=128,
  start_level=0, num_levels=0)`, triggered by `if eval_cnt % eval_freq == 0`, logging
  `Eval/avg_reward`, `Eval/std_reward`, `Eval/start_level`, `Eval/num_levels`.
- **`agents/ppo.py` contains zero eval-related lines.** The baseline IBAC-SNI is compared against
  does not evaluate at all.
- **`common/logger.py` records only training statistics.** Its CSV header is
  `timesteps, wall_time, num_episodes, max/mean/min_episode_rewards, max/mean/min_episode_len` —
  the shipped `logs/` contain no eval curve.
- The eval env is rebuilt inside the agent with `VecNormalize(eval_env, ob=False)`, so **reported
  eval reward is normalised**, not raw episodic return — a protocol axis set invisibly in the
  agent file.
- `num_levels=0` in Procgen means the **full** level distribution including training levels — the
  held-out-vs-full axis the audit database records as varying across papers. Also set in the agent.

So the eval protocol lives in the baseline that was added, and was hand-matched to a *different
repo* ("LSP") by copying. Add a third baseline the same way and you get a third eval convention.
This is the failure DZ is legislating against, present in the example — which makes it a very good
thing to have seen, and the strongest possible argument for the structural criterion in R3: the
evaluator must not be able to see which algorithm it is running.

*(Minor corroboration that these are hand-copied: `heist.sh`'s comment header still says
"на bigfish".)*

### 5.4 Everything else on this machine

| What | Where | Note |
|---|---|---|
| RL-ViGen upstream | `many-gens-rl-vigen/RL-ViGen-upstream/` | vendored |
| Prior RL-ViGen work: ALDA + IDAAC on robosuite, eval discipline, random-policy floors | `../gen-rebuttal/vigen-idaac/` — see its `AXES.md` and `instruction.md` | The most directly reusable asset we own |
| AI-written handover docs for the current code | `~/.gemini/antigravity-cli/brain/1b31deef-.../architectural_review.md`, `.../uncertainty_register.md` | Written by the agent that wrote the code. Useful, and **not** independent evidence — see `RIGOR.md` §7 |

---

## 6. Open questions for DZ — ask before building on the answers

Ordered by how much work the answer changes.

1. **The reference eval itself, and the defect.** We have **neither**. `ext/alda/Nd_ln.py` runs on
   RL-ViGen robosuite and is group-authored, but it is explicitly *not* offered as a good-eval
   example, so nothing in our possession is the group's reference protocol. Separately, Arsenii
   reported a "косяк" in DZ's evaluation and was asked to forward it
   privately. We have neither the defect nor the reference eval. Building our shared evaluator
   before seeing both risks reproducing exactly the bug the group already knows about. *This is
   the highest-value question in the list and it costs one message.*
2. ~~**Which ALDA?**~~ **RESOLVED 2026-08-10 — this is now a correction to report, not a question
   to ask.** `arXiv:2001.01046` is *Adversarial-Learned Loss for Domain Adaptation* (Chen et al.,
   **AAAI 2020**): unsupervised domain adaptation for **image classification**, with no agents, no
   environments and no RL of any kind. `arXiv:2410.07441` is *Associative Latent DisentAnglement*
   (Batra & Sukhatme, **ICML 2025**), a genuine visual-RL generalization method — SAC-based, on
   DMControl-GB. They are unrelated papers in unrelated fields that share an acronym.
   Only one of the two is an RL method at all, so **the existing port is right and the brief's
   citation is an error**. Evidence and canonical hyperparameters: [`FAITHFULNESS.md`](FAITHFULNESS.md) §3.
3. **Which benchmark is the target for the first complete matrix?** The brief lists three; S2 picks
   RL-ViGen. Confirm, because KAGE's throughput makes it a far cheaper place to fill a full
   baseline column, and that is a real argument against S2.
4. **Which RL-ViGen environments?** RL-ViGen spans robosuite, Habitat, CARLA, DMC and Adroit with
   very different install costs (CARLA and Habitat are the heavy ones). "All baselines on all
   simulators" is not affordable. Name the subset.
5. **Eval frequency and episode count.** R3 demands these be identical; it does not say what they
   are. Our prior work says the answer matters more than it looks: on RL-ViGen `eval-easy` the
   return distribution is bimodal (**note**: this was later shown NOT to be an argument against
   IQM — IQM aggregates over runs, not episodes; see `instruction.md` D5), and a 2-episode
   probe misread a random-policy floor by 16× (`../gen-rebuttal/vigen-idaac/CLAIMS.md` §E). Propose
   ≥10 episodes × all eval scenes, mean not IQM, and get it confirmed.
6. **Aliases (R6).** CTRL-as-CURL and RAD-as-SAC are architecturally near-identical to their
   parents at inference. Does DZ want them as separate table rows anyway?
7. **Seeds.** Not mentioned in the brief. Comparability across baselines is bounded by seed count;
   two seeds cannot separate methods whose published margins are within one standard deviation.
   The reference example uses **3** (`for SEED in 1 2 3`); our sibling project found two
   insufficient. Propose 5 and get it confirmed.
8. **What is "LSP", and is it the naming authority?** `bigfish.sh` says the eval and logging are
   *"идентичны LSP (`Eval/avg_reward`, `Eval/std_reward` каждый 5-й rollout)"*. If LSP is the
   group's reference baseline, then **its** logging keys are the standard R3/R5 must adopt, and we
   should be given that repo rather than re-deriving the convention from a comment. Ask for it —
   this is the concrete form of question 1.
9. **Eval on held-out levels or the full distribution?** The reference example evaluates with
   `num_levels=0` (Procgen: *all* levels, training levels included) while training on 200. The
   audit database records this as an axis papers genuinely disagree on, and at least one paper
   deviates deliberately and then compares against one that did not. Whichever we pick, it must be
   the same for all twelve and it must be written into the emitted protocol card.
10. **Is eval reward normalised or raw?** The reference example wraps its eval env in
    `VecNormalize(..., ob=False)`, so the logged `Eval/avg_reward` is a normalised return, not a
    raw episodic one. Cross-baseline comparison requires one answer, stated.

---

## 7. Where the code stands

Assessed against R1–R7 in [`REVIEW.md`](REVIEW.md), stamped to the exact tree state reviewed.
**That review describes the code as found, at commit `07c3f12`. It has since been replaced.** Its
verdict then: R1, R2, R4, R5 had no implementation; R3 was violated by multiple independent eval
paths; R6 partly met; R7 did not run.

Status after the rebuild (`instruction.md` §0, verified in `docs/VALIDATION.md`):

| | verdict | how |
|---|---|---|
| **R1** one `sh` script trains any baseline | **met** | `baselines/<x>/train.sh`, generated from the registry; 11 of 12 have completed real-simulator runs through it |
| **R2** per-baseline dir + README naming its environment | **met** | generated from the registry and config, with a freshness test; `requirements.txt` + `setup/install.sh` |
| **R3** evaluation identical across baselines | **met, structurally** | one `evaluate()` taking an opaque policy; enforced by `test_exactly_one_eval_stepping_loop`, `test_evaluate_cannot_see_the_algorithm` and — across two trainers — `test_on_policy_and_off_policy_runs_are_comparable` |
| **R4** equal training length | **met** | budget in frames, in the protocol and its hash; the on-policy loop stops on the budget, not on a rollout boundary |
| **R5** one plotting routine over tensorboard logs | **met** | `plot.py`, no per-baseline branch; jsonl and tfevents paths asserted to agree |
| **R6** twelve genuine baselines | **met** | all 12 implemented, none an alias. *Not* claimed: that PPG/IBAC-SNI/CTRL reproduce published returns — see `rlgen/algos/onpolicy_ext.py` |
| **R7** clone → install → sh → curve | **met at smoke scale** | verified end to end; no run at meaningful scale yet (`HANDOFF.md`) |

---

## 8. Change log

| Date | Change |
|---|---|
| 2026-08-09 | Created. Brief recorded verbatim; R1–R7 derived; S1–S4 recorded; seven open questions raised. |
