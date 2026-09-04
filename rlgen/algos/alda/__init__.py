"""ALDA, carried over from ../gen-rebuttal/vigen-idaac/vigen_alda/.

COPIED, NOT IMPORTED. The sibling project's own ALDA entry points fail at import in any other
tree because they say `from vigen_idaac.envs import ...` -- a package that exists only there. A
benchmark repo that depends on a sibling checkout is not cloneable, which is requirement R7. So
the three files that are pure algorithm -- `agent.py`, `nets.py`, `config.py` -- are copied and
the training/eval entry points are NOT: this repo has one trainer and one evaluator already.

WHY IT FITS. ALDA is SAC-based (critic target, log-alpha temperature, replay buffer), so it uses
the same off-policy loop as everything else here. It already exposes `act(obs, deterministic)`,
and `update_from_batch(obs, action, reward, next_obs, not_done, log)` takes a batch directly --
so no buffer-interface matching is needed.
"""
