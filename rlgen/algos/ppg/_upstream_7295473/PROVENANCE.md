# `ppg`'s base term, vendored verbatim

**Nothing in this directory is edited, ever.** It exists so "the port's edits over its base are
minimal and scoped" is checkable with `diff` rather than believed from prose
(`docs/STEP-ZERO.md` gate 2).

## Provenance

`openai/phasic-policy-gradient` @ **`7295473f0185c82f9eb9c1e17a373135edd8aacc`** (2020-12-11),
copied from `ext/phasic-policy-gradient/phasic_policy_gradient/`.

**Reconnaissance before the base term was stated as fact** (`STEP-ZERO.md` gate 0 — the step whose
absence produced `ibac_sni`'s wrong base term): `git status --porcelain` reports **0 dirty tracked
files and 0 untracked**; all **19** `.py` files parse under `ast.parse`; the package is
**PyTorch** (`import torch as th`, `torch_util`, `torch.distributions`). Unlike `ibac_sni`'s base
this one is exactly what the record said it was.

| Vendored | sha256 (first 16) |
|---|---|
| `ppg.py` | `ff94cfe2f61375b6` |
| `ppo.py` | `640185fd4604e686` |
| `impala_cnn.py` | `029ab63688264b27` |
| `reward_normalizer.py` | `e1052fcc12430de1` |
| `roller.py` | `1a87c55a7b112e9a` |
| `distr_builder.py` | `3de4655f99b792d5` |
| `torch_util.py` | `5687b6171bffabbc` |
| `minibatch_optimize.py` | `239322b6a2a059c6` |
| `tree_util.py` | `ba2f835a26245781` |

## What this base can and cannot settle

**Can:** the encoder (`impala_cnn.py` — note `tu.NormedConv2d` with an explicit `scale`, a
different initialisation scheme from `train-procgen-pytorch`'s xavier, so nothing transfers from
`ibac_sni`'s base by analogy), the PPO phase (`ppo.py`), the auxiliary phase and its
`beta_clone` distillation (`ppg.py`), the rollout container (`roller.py`), and the reward
normalizer (`reward_normalizer.py`, already transcribed and verified 2026-08-14 by running it).

**Cannot: the continuous policy head — the reference is discrete-only as shipped.**
`distr_builder.py::tensor_distr_builder` routes `Discrete(2)` to Bernoulli and `Discrete` to
Categorical, and **raises `ValueError` on anything else**. There is a `_make_normal`
(`distr_builder.py:11-14`), and it is **dead code**: grepped the whole package, it has no caller,
and `Real` is imported only for the *observation* type (`impala_cnn.py:9`).

This is a trap worth naming, because the dead function is exactly what a hurried reading would
seize on as "PPG's own continuous head". Had it been wired it would still be wrong for this
project: it fixes `scale=1.0` with no learnable log-std, and the authors flagged that themselves
with `warnings.warn("Using stdev=1")`.

So PPG joins `idaac` and `ibac_sni`: **no continuous version exists in the authors' release**, and
the head is an authored adaptation (`porting-directive.md` §4) with no first-party reference to be
faithful to. It is recorded as such rather than allowed to borrow credibility from the base around
it.

## Deliberately absent

`train.py`, `logger.py`, `log_save_helper.py`, `envs.py`, `graph*.py`, `vec_monitor2.py` — the
launcher, logging and env layers. This project supplies its own harness, which is legitimately
shared because a defect in it lands *uniformly* on every baseline (`STEP-ZERO.md` gate 3). Note
`ppg.py`, `ppo.py`, `torch_util.py` and `minibatch_optimize.py` all import `mpi4py`; the algorithm
math is reachable without it, and any dependency-free extraction needed for a parity test is done
in the test, never by editing this directory.
