"""IDAAC and the shared PPO-family core, carried over from ../gen-rebuttal/vigen-idaac.

COPIED, NOT IMPORTED -- same rule as `rlgen/algos/alda/`: the sibling's entry points say
`from vigen_idaac.envs import ...` and fail in any other tree. These four files are pure
algorithm and import nothing from that package.

WHAT IS REUSED BEYOND IDAAC. `model.py` (ImpalaEncoder + DiagGaussianHead) and `storage.py` (a
rollout buffer with GAE and a minibatch generator) are the PPO-family substrate that PPG and
IBAC-SNI also need. They already solve the two hard adaptations for this benchmark -- discrete
Categorical -> continuous diagonal Gaussian, and 3-channel 64x64 Procgen frames -> 9-channel
84x84 frame-stacked robosuite -- and they carry the sibling project's marked deviations in their
own docstrings. Re-deriving that would be strictly worse.
"""
