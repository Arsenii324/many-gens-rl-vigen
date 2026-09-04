"""The only place logging key strings exist.

WHY A WHOLE MODULE FOR SOME STRINGS. The supervisor's brief requires that every baseline log
"под одинаковыми ключами" -- under identical keys. A convention cannot deliver that: the group's
own reference repo (`~/Downloads/IBAC_SNI_torch`) states in a shell comment that its eval logging
is "identical to LSP", and then implements the eval loop inside `agents/ppo_ibac.py` with the tag
strings written as literals at the call site, while `agents/ppo.py` logs no eval at all. Two
baselines, one convention, one implementation.

Making the strings importable constants means a baseline cannot invent a tag without adding it
here, and `tests/test_eval_identity.py` fails the build if a tag literal appears anywhere else.

Changing a string here changes it for every baseline at once, which is the point. It also breaks
comparability with previously logged runs, so treat this file as a versioned schema:
bump SCHEMA_VERSION and say so in the run's protocol card.
"""
from __future__ import annotations

SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------------------------
# Evaluation. These are the curves the shared plotter draws and the only ones compared across
# baselines. `return` is the RAW undiscounted episodic sum -- never a normalised or shaped
# variant, because a normaliser in one baseline and not another is exactly the silent divergence
# this project exists to prevent.
# ---------------------------------------------------------------------------------------------
EVAL_RETURN_MEAN = "eval/return_mean"
EVAL_RETURN_STD = "eval/return_std"
EVAL_RETURN_MEDIAN = "eval/return_median"
EVAL_SUCCESS_RATE = "eval/success_rate"
EVAL_EPISODE_LEN_MEAN = "eval/episode_len_mean"
EVAL_EPISODES = "eval/n_episodes"

# The same statistics on the training distribution, logged by the same evaluator with a different
# protocol. Kept distinct so that no plot can silently mix a train-distribution number into a
# generalisation curve.
TRAIN_EVAL_RETURN_MEAN = "train_eval/return_mean"
TRAIN_EVAL_RETURN_STD = "train_eval/return_std"
TRAIN_EVAL_SUCCESS_RATE = "train_eval/success_rate"

# The generalisation gap, computed once, centrally, from the two above. Baselines never compute it.
GAP_ABSOLUTE = "gap/absolute"

# ---------------------------------------------------------------------------------------------
# Training progress. Not compared across baselines -- an on-policy and an off-policy method spend
# frames differently by construction -- but recorded so a curve can be read against wall-clock and
# update count when a difference needs explaining.
# ---------------------------------------------------------------------------------------------
TRAIN_RETURN_MEAN = "train/return_mean"
TRAIN_FPS = "train/fps"
TRAIN_UPDATES = "train/n_updates"
TRAIN_WALLCLOCK = "train/wallclock_s"

# ---------------------------------------------------------------------------------------------
# Mechanism diagnostics. Cheap at eval time and decisive when a baseline underperforms: they turn
# "it scores badly" into "its entropy term collapsed". docs/RIGOR.md section 3.2 records the case
# where these five numbers changed the conclusion of an entire study.
# Optional -- a baseline that cannot produce one omits it rather than logging a placeholder.
# ---------------------------------------------------------------------------------------------
DIAG_POLICY_ENTROPY = "diag/policy_entropy"
DIAG_ACTION_STD_MEAN = "diag/action_std_mean"
DIAG_ACTION_SAT_FRAC = "diag/action_saturated_frac"
DIAG_CRITIC_Q_MEAN = "diag/critic_q_mean"
DIAG_DET_STOCH_RATIO = "diag/deterministic_over_stochastic"

# ---------------------------------------------------------------------------------------------
EVAL_TAGS = (EVAL_RETURN_MEAN, EVAL_RETURN_STD, EVAL_RETURN_MEDIAN, EVAL_SUCCESS_RATE,
             EVAL_EPISODE_LEN_MEAN, EVAL_EPISODES)
TRAIN_EVAL_TAGS = (TRAIN_EVAL_RETURN_MEAN, TRAIN_EVAL_RETURN_STD, TRAIN_EVAL_SUCCESS_RATE)
DIAG_TAGS = (DIAG_POLICY_ENTROPY, DIAG_ACTION_STD_MEAN, DIAG_ACTION_SAT_FRAC,
             DIAG_CRITIC_Q_MEAN, DIAG_DET_STOCH_RATIO)
TRAIN_TAGS = (TRAIN_RETURN_MEAN, TRAIN_FPS, TRAIN_UPDATES, TRAIN_WALLCLOCK)

#: Tags every baseline MUST emit. `tests/test_eval_identity.py` asserts the set is identical
#: across baselines, so a missing one is a build failure rather than a hole in a plot.
REQUIRED_TAGS = frozenset(EVAL_TAGS) | frozenset(TRAIN_EVAL_TAGS) | {GAP_ABSOLUTE}

ALL_TAGS = frozenset(EVAL_TAGS) | frozenset(TRAIN_EVAL_TAGS) | frozenset(DIAG_TAGS) \
    | frozenset(TRAIN_TAGS) | {GAP_ABSOLUTE}

#: Column order for the per-episode record file. This is the artifact the whole post-hoc
#: programme depends on: with per-episode rows, any aggregation statistic, episode count or scene
#: subset can be recomputed later at zero cost; with only means, none of it can.
#: `frames` is the TRAINING frame count at which the checkpoint was taken -- not the episode's
#: length, which is `episode_len`. The previous implementation wrote episode length into the
#: column its own schema documented as the training step (docs/REVIEW.md F14).
EPISODE_COLUMNS = (
    "baseline", "backbone", "task", "mode", "scene_id", "seed", "frames", "checkpoint",
    "episode_idx", "return_raw", "episode_len", "terminated", "truncated", "success",
    "policy_mode", "protocol_hash", "weights_source", "code_commit",
)
