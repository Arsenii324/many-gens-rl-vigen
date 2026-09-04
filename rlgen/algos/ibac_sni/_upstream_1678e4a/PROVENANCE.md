# `ibac_sni`'s base term, vendored verbatim

**Nothing in this directory is edited, ever.** It exists so that the claim "the port's edits over
its base are minimal and scoped" is *mechanically checkable* — `diff` this against the module one
level up — rather than argument-shaped prose that has to be believed
(`porting-directive.md` §6, `docs/STEP-ZERO.md` gate 2).

## What each file is

| Vendored as | Origin | sha256 (first 16) |
|---|---|---|
| `common_model.py` | `common/model.py` | `b648f4d7b6cd6c4f` |
| `common_policy.py` | `common/policy.py` | `646806e1a5d32395` |
| `common_misc_util.py` | `common/misc_util.py` | `76c10f92e5f7fdbc` |
| `common_storage.py` | `common/storage.py` | `e72b0bb06e06ff80` |
| `agents_ppo.py` | `agents/ppo.py` | `1bcddc3a72d90ad1` |
| `agents_base_agent.py` | `agents/base_agent.py` | `1a545d22d1d1b58f` |
| `DZ_common_policy_ibac.py` | DZ's `common/policy_ibac.py` | `9274a9d54efeec58` |
| `DZ_agents_ppo_ibac.py` | DZ's `agents/ppo_ibac.py` | `c3e020574f30231a` |

## Where they came from — three sources, three different standings

**1. The PPO host — the base term proper.**
`joonleesky/train-procgen-pytorch` @ **`1678e4a9e2cb8ffc3772ecb3b589a3e0e06a2281`**
(2020-09-10, "Update Readme.md"), extracted with `git show 1678e4a:<path>` from the clone at
`~/Downloads/train-procgen-pytorch_example`.

**Extracted from the commit, deliberately not from that clone's working tree.** The working tree
is dirty — ` M agents/ppo.py`, ` M train.py`, untracked `experiments/` — carrying an unrelated
third party's noise-injection experiment (an SVD `find_principal_component`, a `noise_amplitude`
knob, Russian comments). Its `agents/ppo.py` **does not parse**: `ast.parse` raises
`SyntaxError` on `self.find_principal_component( self.storage.  )`. Until 2026-08-16 this
project's own docs recorded that tree as a *clean* base — the remote had been verified and that
was silently read as the working tree being clean. See `docs/REGISTER.md`, 2026-08-16.

**2. The IBAC-SNI semantics — NOT from this directory's DZ files.**
`ext/IBAC-SNI`, `microsoft/IBAC-SNI` @ `6b3a58bfc23a1e8e2bbb669a4e96e24dabc32d71`, the authors'
own release. It ships both the TF 1.x CoinRun path (`coinrun/coinrun/{policies,ppo2,config}.py`,
the paper's headline experiments) and **the authors' own PyTorch bottleneck**
(`torch_rl/bottleneck.py`, `torch_rl/model.py`). Not vendored here because it is already in-repo
under `ext/` and is cited per-edit at the point of use instead.

**3. DZ's PyTorch port — wiring only, and vendored precisely so it can be diffed against, not
inherited from.**
`~/Downloads/IBAC_SNI_torch/train-procgen-pytorch` (no `.git`). Its delta against the pristine
base above is **4 files** — `hyperparams/procgen/config.yml` and `train.py` modified,
`agents/ppo_ibac.py` and `common/policy_ibac.py` new (+ 5 non-code launch `.sh`). It is *not*
5 files: `agents/ppo.py` is byte-identical to upstream (`diff`, exit 0) and only appeared modified
because the earlier diff was taken against the dirty tree.

The two `DZ_*.py` files here are a **Construction** — a re-derivation from the paper, not a
transcription of the authors' code. Evidence: their headers cite the paper by title and venue and
describe the mechanism in prose; and `ppo_ibac.py::evaluate()` is a translated copy of the *dirty*
tree's `ppo.py::evaluate()`, so this port post-dates and partly derives from those local
modifications. The usual argument that would promote a third party's PyTorch version to reference
status — "it is the only PyTorch implementation available" — **is false here**, because the
authors released one themselves.

So DZ's files are authoritative about **how IBAC bolts into this specific PPO host** (constructor
signature, config keys, dispatch) and about **nothing else**. Every point where they diverge from
`ext/IBAC-SNI` is recorded as a finding, not silently adopted.

## What is deliberately absent

`common/logger.py`, `common/env/procgen_wrappers.py`, `train.py`, `hyperparams/` — the env,
logging and launcher layers. This project supplies its own harness (`rlgen/envs.py`,
`rlgen/trainer_onpolicy.py`), which is legitimately shared because a defect in it lands
*uniformly* on every baseline it serves and shows up as a systematic offset
(`docs/STEP-ZERO.md` gate 3). The reward normalizer is the exception and was already transcribed
per-baseline from `procgen_wrappers.py::VecNormalize` (`docs/REGISTER.md`, 2026-08-14), because
its failure would land *selectively*.
