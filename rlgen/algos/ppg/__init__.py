"""PPG (Cobbe et al., ICML 2021, arXiv:2009.04416), hermetic per `porting-directive.md` §1.

NOT built on `idaac/model.py`/`algo.py`. The shared core gave PPG exactly one value head
(`cfg.algo="ppo"` forces `value_net` to stay `None`, `idaac/algo.py::Learner.__init__`) --
`arch="dual"` is confirmed as the reference's own actual default at BOTH the model level
(`ppg.py:72`) and the launch-script level (`train.py:11,89`), building a genuinely separate
value encoder. Sharing meant this project never had one. Re-deriving from the reference directly
(`ext/phasic-policy-gradient/phasic_policy_gradient/{ppg,ppo,train}.py`, all read in full
2026-08-14, `docs/REGISTER.md`) is what surfaced this and two more real divergences: PPG's own
launch config runs exactly ONE SGD epoch per policy-phase update
(`n_epoch_pi=1`/`n_epoch_vf=1`, confirmed at both the function-default and CLI-default level in
`train.py`), not the ten this project's shared core applies via IDAAC's own tuned value; and the
aux phase retrains the separate value network itself (`vf_true`, weighted by `vf_true_weight`),
not just the policy-encoder's auxiliary head -- a term the shared implementation never had at all
because it never had a separate value network to retrain.

Continuous action head: same declared adaptation as `ibac_sni`'s own module -- no continuous PPG
reference of any kind exists (checked exhaustively via two independent `agy` searches,
`docs/ORIGINAL_LOCATIONS.md` §ppg), so the diagonal-Gaussian head with clip-outside/
log-prob-inside treatment is the external, standard convention settling that branch point, not
invented here.
"""
