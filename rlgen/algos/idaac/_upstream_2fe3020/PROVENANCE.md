# `idaac`'s base term, vendored verbatim

**Nothing in this directory is edited, ever.** It exists so "the port's edits over its base are
minimal and scoped" is checkable with `diff` (`docs/STEP-ZERO.md` gate 2).

## Provenance

`rraileanu/idaac` @ **`2fe3020`**, the paper's own author, copied from `ext/idaac/`.

**Gate-0 reconnaissance, done before the base term was stated as fact:** `git status --porcelain`
reports **0 dirty tracked files**; the only 2 untracked entries are the paper PDFs
(`raileanu21a.pdf`, `raileanu21a-supp.pdf`, the source of Appendix E's continuous DMC
hyperparameters); every `.py` parses; **PyTorch throughout**.

Checked because the risk was raised explicitly: this is *not* a copy of `gen-rebuttal`'s
adaptation. `git remote -v` resolves to `https://github.com/rraileanu/idaac.git`.

| Vendored | Origin | sha256 (first 16) |
|---|---|---|
| `model.py` | `ppo_daac_idaac/model.py` | `8ab8ff3ad74ff9fa` |
| `storage.py` | `ppo_daac_idaac/storage.py` | `94ee5caa68a6a5e9` |
| `distributions.py` | `ppo_daac_idaac/distributions.py` | `945c4ede237642b8` |
| `utils.py` | `ppo_daac_idaac/utils.py` | `80ff234507c570e5` |
| `algo_idaac.py` | `ppo_daac_idaac/algo/idaac.py` | `9171fda7adce2159` |
| `algo_daac.py` | `ppo_daac_idaac/algo/daac.py` | `964206e55ce4f38a` |
| `algo_ppo.py` | `ppo_daac_idaac/algo/ppo.py` | `a4e68ba597861d77` |
| `hyperparams.py` | `hyperparams.py` | `661d85c7a12b4547` |

## What this base settles, and the one thing it cannot

**Settles**: the encoder (`ResNetBase`, `PolicyResNetBase`, `ValueResNet`), the rollout buffer
(`storage.py`), the DAAC/IDAAC losses including the order-pair discriminator, and the published
hyperparameter grid (`hyperparams.py`).

**Cannot settle the continuous policy head.** `distributions.py` defines only `FixedCategorical`
and `Categorical`; `model.py:313,360` wires `Categorical` unconditionally. There is no Gaussian
head anywhere in the release. So the head is an authored `porting-directive.md` §4 adaptation with
no first-party reference — the same position as `ppg` and `ibac_sni`, and it must be graded NOT
INTRINSIC rather than borrowing credibility from the faithful base around it.

Related, and worse than merely absent: `rlgen/algos/idaac/config.py:152` and `model.py:84` justify
the head's form as a `DEVIATION from [IK]` — Kostrikov's `pytorch-a2c-ppo-acktr`, which **is not
on this disk** and has never been read here (`docs/REGISTER.md`, 2026-08-16). That citation cannot
currently be checked by anything.

## Read before building — three details that do not survive being assumed

1. **`self.fc = init_relu_(nn.Linear(2048, hidden_size))`** (`model.py:145`) hardcodes `2048`
   = `32*8*8`, correct only for Procgen's 64x64. At this project's 84x84 the stack yields
   84 -> 42 -> 21 -> 11, i.e. `32*11*11 = 3872`. Same shape of edit as `ibac_sni`'s E1, and the
   opposite of `ppg`, whose reference derives its own width and needed no edit at all.
2. **`Conv2d_tf` implements TF "SAME" padding**, including the asymmetric one-sided pad when the
   total is odd (`F.pad(input, [0, cols_odd, 0, rows_odd])`). A plain `nn.Conv2d(padding=1)` is
   *not* equivalent at every input size. Note the wart: `BasicBlock` passes `padding=(1,1)`, a
   tuple, which only ever fails the `== "VALID"` test — so the value is ignored and SAME is
   computed regardless.
3. **Initialisation is `apply_init_`: `xavier_uniform_` on every `Conv2d`, zero bias**
   (`model.py:18-31`) — the same family as `ibac_sni`'s base and *not* `ppg`'s normalized-fan-in.
   Three baselines, three different init schemes; the T1 blind spot recorded in `STEP-ZERO.md`
   means a weight transplant will not notice if this is wrong, so it needs its own init-parity
   check.

## Deliberately absent

`train.py`, `test.py`, `envs.py`, `arguments.py` — launcher, env and CLI layers. This project
supplies its own harness, legitimately shared because a defect in it lands *uniformly* on every
baseline (`STEP-ZERO.md` gate 3).
