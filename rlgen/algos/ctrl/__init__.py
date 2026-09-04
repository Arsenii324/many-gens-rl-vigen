"""CTRL (Mazoure et al., ICLR 2022, arXiv:2106.02193), hermetic per `porting-directive.md` §1.

NOT built on `idaac/algo.py`'s shared core. `onpolicy_ext.py::CTRLLearner` (still the live
registry path until this module is wired in, task #19) inherits IDAAC's PPO core, buffer, and
`set_lr` -- but CTRL's own reference is JAX (`ext/ctrl_public/`), sharing no code lineage with
IDAAC's PyTorch port at all. The JAX-vs-PyTorch framework decision was resolved separately
(`docs/REGISTER.md`, 2026-08-14, independently verified T1/T2 parity for a from-scratch PyTorch
port) before this module's construction began.

Reference fully read before writing anything here (`docs/REGISTER.md`, two dated entries,
2026-08-14): `algo.py` (618 lines), `models.py` (306 lines), `buffer.py` (86 lines),
`train_ppo.py` (289 lines), plus the load-bearing sections of `vec_env.py`. What that reading
surfaced, beyond what `onpolicy_ext.py::CTRLLearner`'s own docstring already recorded:

  * A `v`/`w` dual-embedding split (`cluster()` returns four embeddings, not one) that this
    project's prior construction never had.
  * The two known upstream JAX bugs (`scores_w_target`, `stop_gradient` commented out) break the
    ENTIRE MYOW neighbor-selection path, not only the stop-gradient -- the paper's intended
    neighbor-selection mechanism cannot be recovered from this file; DEPARTS(2)'s
    same-partition-sampling simplification is the only evidenced-runnable option, not merely a
    simplification of something that runs.
  * Three separate Optax optimizers confirmed by the executable `opt_idx` call sites, not only
    the pseudocode already cited for DEPARTS(3).
  * No learning-rate decay anywhere in the reference (grepped `schedule`/`decay`/`anneal` across
    all four core files, zero matches) -- a fourth real, previously-unflagged divergence from what
    this project's shared core currently applies via inheritance, the same shape of gap already
    found and fixed for PPG.
  * The reward-normalizer train/measurement split (`porting-directive.md` §2) is independently
    confirmed by the reference itself via two separate mechanisms: `evaluate_ppo.py`'s
    `normalize_rewards=False`, and `VecMonitor` wrapping inside `VecNormalize` so
    `info['episode']['r']` stays raw regardless of the flag.

Continuous action head: same declared adaptation as `ibac_sni`/`ppg`'s own modules -- CTRL's
reference is discrete Procgen (`Categorical`), so the diagonal-Gaussian head with
clip-outside/log-prob-inside treatment is the external, standard convention settling that branch
point, not invented here.
"""
