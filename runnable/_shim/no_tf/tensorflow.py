"""A TensorFlow that exists but does nothing -- and says so loudly the moment it is touched.

## Why this exists

`idaac` imports `baselines.common.vec_env.{VecMonitor, VecNormalize}`. `VecNormalize.__init__`
branches on `use_tf`, and with `use_tf=False` -- which is the default, and what idaac's own
`VecNormalize(venv=venv, ob=False)` call gets -- it uses `RunningMeanStd`, a **pure numpy** class:
`np.zeros`, `np.mean`, `np.var`, and Chan's parallel-variance update. No tensor ever exists.

But `baselines/common/running_mean_std.py` opens with a module-level `import tensorflow as tf`,
for the sibling class `TfRunningMeanStd` that nothing on this path constructs. So a hard TF
dependency is imposed by an import statement rather than by any code that runs.

## Why a stub rather than installing TensorFlow

Installing TF to satisfy an import whose only consumer is unreachable adds a multi-gigabyte
dependency to every environment this baseline ever runs in -- Kaggle and DataSphere included --
and buys nothing. This file is on `PYTHONPATH` only for the idaac launcher, changes zero lines in
any repo, and is visible in `runnable/_launch/idaac.sh`.

## Why it raises instead of no-opping

A silent stub would let a genuine TF code path run on garbage and report a number. This one
imports cleanly and raises `NotImplementedError` on **any** attribute access, so the claim
"nothing on our path uses TensorFlow" is enforced at runtime rather than asserted. If this ever
raises, the assumption was wrong and the run stops -- which is the point.

If real TensorFlow is ever installed, drop `runnable/_shim/no_tf` from PYTHONPATH: a PYTHONPATH
entry precedes site-packages and this file would shadow the real package.


## The one allowance, and how it was bounded

The import chain does not stop at `running_mean_std`: that module also does
`from baselines.common.tf_util import get_session`, and `tf_util` evaluates `tf.float32` while
being imported. An AST pass over `tf_util.py` -- module-level statements plus every function
signature, since default arguments are evaluated at def time -- reports the complete set of
`tf.*` names touched at import as exactly:

    ['float32']

and it appears only as `def conv2d(..., dtype=tf.float32, ...)`, a default for a function
nothing on this path calls. So `float32` is a sentinel object below, and every other name still
raises. That is a bounded claim about one name, not a general "TF is unused" hand-wave.
"""


class _Unusable:
    """Identity-only. Anything that tries to compute with it fails."""

    def __repr__(self):
        return "<stubbed tensorflow.float32 -- never used on this path>"


float32 = _Unusable()


def __getattr__(name):
    raise NotImplementedError(
        f"tensorflow.{name} was accessed, but TensorFlow is stubbed here "
        "(runnable/_shim/no_tf/tensorflow.py). Only baselines' numpy-only RunningMeanStd and "
        "the unused tf.float32 default in tf_util.conv2d are supposed to be reachable on this "
        "path -- something now genuinely needs TF. Re-run the AST check in this file's "
        "docstring before widening the allowance."
    )
