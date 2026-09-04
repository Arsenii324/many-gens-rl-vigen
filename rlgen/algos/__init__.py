"""Algorithm implementations this repo owns, as opposed to those it loads from RL-ViGen.

RL-ViGen ships DrQ-v2, SVEA, SGQN, CURL and DrQ; `rlgen/registry.py` loads those by file path.
It does NOT ship RAD or SODA, so their SAC backbone lives here. The files were recovered from
this repo's own history (`de879a0`) rather than rewritten -- `sac.py`, `modules.py`,
`augmentations.py` and `soda_utils.py` are the SAC stack, and `soda.py` is a genuine SODA
auxiliary (a BYOL-style predictor over augmented views).

BACKBONE IS PART OF THE MEASUREMENT. RAD and SODA are SAC-based; every other baseline here is
DrQ-v2-based. That is faithful to the papers and it is a confound, so the registry records
`backbone` separately from `method` and every figure legend carries it. RAD on a DrQ-v2 backbone
would be a near-alias of DrQ-v2, since DrQ-v2 already applies RandomShiftsAug -- which is exactly
the undeclared-alias trap this repo refuses.
"""
