#!/usr/bin/env python3
"""The metric definitions this project reports, in one place, with their conditions of validity.

    python scripts/metrics.py --self-test      # the numeric properties below, checked

Recovered rather than invented: the sibling projects in this workspace already built ~577
metrics between them (`docs/metrics-survey/`), and this file ports the four that answer questions
`docs/AUDIT-2026-08-17.html` could otherwise only argue about, plus the interval that a binary
success rate needs and did not have.

## Why each one is here

- `wilson_interval` — this project reports a SUCCESS RATE, which is a binomial proportion. The
  normal approximation `p ± z·sqrt(p(1-p)/n)` is wrong exactly where our numbers live: at p near
  0 or 1 it produces intervals that leave [0,1], and at p == 0 it produces width ZERO, which
  reads as certainty from a handful of episodes. Wilson does not. `unified-bench` documents the
  same failure for `sem` over 32 episodes ("pure Bernoulli noise").
- `iqm` + `bootstrap_ci` — the interquartile mean, robust to the outlier episodes that a dense
  manipulation reward produces. `unified-bench` also records its own caveat, kept below: on
  NEAR-BINARY reward distributions IQM truncates away the signal and can report a constant.
- `interframe_absdiff` — how much consecutive frames inside one stacked observation differ. This
  is the measurement behind the project's largest open question: four baselines see a single
  frame and eight see three, and a single frame on a manipulation task is velocity-blind. This
  turns that from an argument into a number.
- `action_saturation_frac` — the fraction of action components sitting on the box boundary. Four
  baselines emit an unsquashed Gaussian bounded only by robosuite's own `np.clip`, so the
  probability mass outside the box is folded onto the boundary while the policy's likelihood
  still treats it as interior. This measures how much.
- `diag_gaussian_entropy` — the closed form, so a head's initialisation can be ASSERTED rather
  than eyeballed in a log.

## What none of this can see

These are definitions, not measurements. They cannot tell you that the number handed to them was
computed over the right episodes, in the right regime, or by the right policy. A perfectly
correct Wilson interval around a success rate collected in the training regime is still a
train-distribution number. `scripts/collect_metrics.py` is where the regime is tracked.
"""
from __future__ import annotations

import math
import sys

import numpy as np


# -- proportions ------------------------------------------------------------------------------

def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion. Default z=1.96 is 95%.

    Chosen over the normal approximation because of how it behaves at the edges, which is where
    this project's success rates currently are:

        p=0, n=10   normal -> (0.000, 0.000)      <- width zero. Reads as certainty.
                    wilson -> (0.000, 0.278)      <- honest about ten episodes proving little.

    Returns (lo, hi), both clamped into [0, 1]. n == 0 returns (0.0, 1.0): no episodes is no
    information, and it should look like it.
    """
    if n <= 0:
        return (0.0, 1.0)
    if successes < 0 or successes > n:
        raise ValueError(f"successes={successes} outside [0, {n}]")
    p = successes / n
    d = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = (z / d) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, centre - half), min(1.0, centre + half))


# -- distributions over episode returns -------------------------------------------------------

def iqm(xs) -> float:
    """Interquartile mean: the mean of the middle 50%, discarding the top and bottom quartile.

    CAVEAT, ported with the metric and not to be dropped: on a NEAR-BINARY distribution -- which
    a sparse success signal is -- the truncation removes the informative tail and IQM can report
    a constant while the underlying rate moves. `unified-bench` documents this happening to it.
    Use it for dense returns; use `wilson_interval` for the success rate itself.

    WHY NOTHING IN THIS PROJECT CALLS IT, checked 2026-08-28 rather than left as dead code for
    someone to "fix". Every caller passes `stat=mean` explicitly, overriding this default, and that
    is correct for two reasons:

    1. **IQM's home is aggregation across RUNS**, which is what Agarwal et al. propose it for --
       robustness when a handful of seeds land badly. This project has **one seed per cell**, so
       there is nothing across which to aggregate. It becomes the right estimator the moment a cell
       has three or more seeds, and that is the trigger to switch.
    2. **Within a single run it is a different and worse statistic here.** Door's returns are
       bimodal -- below the 250 shaping ceiling (door never opened) or above it -- so discarding
       the bottom quartile discards failures and inflates the cell. Measured on `drqv2`@100k:
       scene 0 mean 439.75 against IQM 482.91, scene 9 mean 374.62 against IQM 465.43.

    The caveat above was ALSO checked on this data and does not bite: IQM erased the success mode
    on **0 of 10** scenes, because where successes exist they are the majority (18/20, 17/20,
    20/20) and the middle 50% keeps them. So the reason not to use it is (1), not the caveat --
    recorded because the plausible-sounding reason is the wrong one.
    """
    a = np.sort(np.asarray(list(xs), dtype=np.float64))
    if a.size == 0:
        return float("nan")
    lo, hi = int(np.floor(a.size * 0.25)), int(np.ceil(a.size * 0.75))
    mid = a[lo:hi] if hi > lo else a
    return float(mid.mean())


def bootstrap_ci(xs, stat=iqm, n_boot: int = 2000, alpha: float = 0.05,
                 seed: int = 0) -> tuple[float, float]:
    """Percentile bootstrap CI for any statistic. Deterministic given `seed`.

    This resamples EPISODES within one run. It therefore expresses within-run sampling
    uncertainty and says NOTHING about seed-to-seed variance, which for RL is usually the larger
    term -- `unified-bench` records single-seed point estimates as its most serious caveat, and
    RL-ViGen's own paper (§4) specifies 5 seeds with 95% CIs. Do not present this as if it
    covered that.
    """
    a = np.asarray(list(xs), dtype=np.float64)
    if a.size == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    draws = [stat(rng.choice(a, size=a.size, replace=True)) for _ in range(n_boot)]
    return (float(np.percentile(draws, 100 * alpha / 2)),
            float(np.percentile(draws, 100 * (1 - alpha / 2))))


# -- observation geometry ---------------------------------------------------------------------

def interframe_absdiff(obs, n_frames: int, channels_first: bool = True) -> float:
    """Mean |pixel difference| between consecutive frames of ONE stacked observation, in [0,1].

    Answers: does this observation carry motion at all? A frame stack exists so the agent can
    infer velocity; if consecutive frames are identical the stack is decoration, and if there is
    only one frame the quantity is undefined -- which is the finding, not a failure.

    Returns 0.0 for n_frames == 1, and the caller must not read that as "no motion": it means
    NOT MEASURABLE. `probe_observation.py` reports the frame count alongside so the two cannot be
    confused.

    Input is uint8 [0,255] or float [0,1]; both are normalised to [0,1] before differencing so
    the number is comparable across baselines that scale differently (see the audit, §4).
    """
    a = np.asarray(obs, dtype=np.float64)
    if n_frames <= 1:
        return 0.0
    if a.max() > 1.5:                     # uint8-valued, whatever the declared dtype
        a = a / 255.0
    if channels_first:                    # (F*C, H, W)
        f = a.reshape(n_frames, -1)
    else:                                 # (H, W, F*C)
        a = np.moveaxis(a, -1, 0)
        f = a.reshape(n_frames, -1)
    return float(np.abs(np.diff(f, axis=0)).mean())


def histogram_tv_distance(a, b, bins: int = 32, channels_first: bool = True) -> float:
    """Total-variation distance between the pixel-intensity distributions of two observation sets.

    In [0, 1]: 0 means the two sets are indistinguishable by intensity histogram, 1 means
    disjoint. Computed per channel and averaged, because a colour randomisation moves channels
    differently and collapsing to greyscale first would hide exactly that.

    **This exists to answer whether the eval regimes differ from train at all.** RL-ViGen's
    `eval-easy` randomises colour and lighting, `eval-hard` adds a video background — but "the
    code sets a flag" and "the observation distribution actually moved" are different claims, and
    only the second one makes a generalisation number mean anything.

    CONDITION OF VALIDITY, and it is the whole design: **a between-regime distance is
    uninterpretable without a within-regime one.** Two samples drawn from the *same* regime with
    different seeds still differ, because initial states and (in eval) per-episode randomisation
    differ. That within-regime number is the control. If between-regime is not clearly larger,
    the regimes are not separated no matter what the config says.

    Deliberately not a learned or perceptual distance: this must be cheap, deterministic, and
    explainable in one line, because it is used to decide whether to spend compute at all.
    """
    def hist(x):
        arr = np.asarray(x, dtype=np.float64)
        if arr.max() > 1.5:
            arr = arr / 255.0
        if arr.ndim == 3:                       # single observation -> add a sample axis
            arr = arr[None]
        # (N, C, H, W) or (N, H, W, C) -> (C, pixels)
        arr = arr.reshape(arr.shape[0], *arr.shape[1:])
        if channels_first:
            c = arr.shape[1]
            flat = arr.reshape(arr.shape[0], c, -1).transpose(1, 0, 2).reshape(c, -1)
        else:
            c = arr.shape[-1]
            flat = np.moveaxis(arr, -1, 1).reshape(arr.shape[0], c, -1).transpose(1, 0, 2)\
                     .reshape(c, -1)
        return np.stack([np.histogram(ch, bins=bins, range=(0.0, 1.0), density=False)[0]
                         / max(1, ch.size) for ch in flat])

    ha, hb = hist(a), hist(b)
    if ha.shape != hb.shape:
        raise ValueError(f"channel counts differ: {ha.shape[0]} vs {hb.shape[0]}")
    return float(np.abs(ha - hb).sum(axis=1).mean() / 2.0)


# -- action geometry --------------------------------------------------------------------------

def action_saturation_frac(actions, lo: float = -1.0, hi: float = 1.0,
                           eps: float = 1e-3) -> float:
    """Fraction of action COMPONENTS at or outside the box boundary.

    For a tanh-squashed policy this is ~0 by construction. For an unsquashed Gaussian clipped by
    the environment it is the share of the policy's mass that the env is folding onto the
    boundary while the policy's own log-prob still treats it as interior -- the defect named in
    the audit's Finding 6, quantified.

    Components, not actions: one saturated dimension out of seven is a seventh of a
    saturated action, and reporting it per-action would hide that.
    """
    a = np.asarray(actions, dtype=np.float64)
    if a.size == 0:
        return float("nan")
    return float(((a <= lo + eps) | (a >= hi - eps)).mean())


# -- on-policy family: the PPO/PPG/IDAAC/IBAC-SNI/CTRL eight ----------------------------------
#
# Names taken deliberately from TorchRL's `ClipPPOLoss.out_keys` rather than invented, so a
# reader who knows the field reads these without a glossary and a number here is comparable to a
# number there: `explained_variance`, `clip_fraction`, `kl_approx`, `ESS`. See
# `docs/library-survey/raw/torchrl.md` §5.2 for the source list, and note two gaps this file
# deliberately fills:
#
#   - TorchRL computes `kl_approx` as the k1 estimator ONLY. k1 is unbiased for the KL but has
#     high variance and can go NEGATIVE, which is embarrassing in a log and useless as a trigger.
#     `approx_kl` below offers k3, which is unbiased AND non-negative (Schulman, "Approximating
#     KL Divergence", 2020).
#   - `target_network_divergence` is measured NOWHERE in TorchRL (verified by grep for
#     `target.*diverg`, `param_distance`, `target_norm`). For the five DrQv2-family and three
#     SAC-family baselines it is the cheapest early warning that a target network has stopped
#     tracking, which is the classic silent failure in off-policy visual RL.

def explained_variance(y_true, y_pred) -> float:
    """1 - Var(y_true - y_pred) / Var(y_true). The critic's R^2 against the returns it predicts.

    Reads as: 1.0 the critic explains the returns perfectly, 0.0 it is no better than predicting
    the mean, NEGATIVE it is worse than the mean -- which is the value worth watching, because a
    critic below 0 makes every advantage it produces noise.

    Returns nan when the targets have no variance, because the quantity is undefined there rather
    than 0.0 -- and 0.0 would read as "explains nothing", which is a different claim. On a sparse
    manipulation reward the all-zero-return case is common, so this distinction is not academic.
    """
    yt = np.asarray(y_true, dtype=np.float64).ravel()
    yp = np.asarray(y_pred, dtype=np.float64).ravel()
    if yt.size == 0 or yt.size != yp.size:
        return float("nan")
    var = yt.var()
    return float("nan") if var == 0 else float(1.0 - (yt - yp).var() / var)


def clip_fraction(log_ratio, clip_eps: float = 0.2) -> float:
    """Fraction of samples whose importance ratio left [1-eps, 1+eps], i.e. that PPO clipped.

    Takes the LOG ratio, not the ratio, because that is what a policy actually produces
    (`logp_new - logp_old`) and exponentiating early loses precision exactly where the ratio is
    extreme -- which is the region this metric exists to count.

    Interpretation is one-sided in a useful way: near 0 means the updates are too small to bind,
    and a large value means the policy is moving far enough per step that most of the gradient is
    being thrown away. Neither is a failure on its own; a sudden change in it usually is.
    """
    lr = np.asarray(log_ratio, dtype=np.float64).ravel()
    if lr.size == 0:
        return float("nan")
    r = np.exp(lr)
    return float((np.abs(r - 1.0) > clip_eps).mean())


def approx_kl(log_ratio, estimator: str = "k3") -> float:
    """Approximate KL(old || new) from log_ratio = logp_new - logp_old. Schulman (2020).

        k1 = -log r            unbiased, high variance, CAN BE NEGATIVE
        k2 = 0.5 * (log r)^2   low variance, biased
        k3 = (r - 1) - log r   unbiased AND non-negative  <- the default, and the reason this
                               exists rather than deferring to TorchRL's `kl_approx`

    k3 is the default because a KL that can print a negative number is not usable as an
    early-stopping trigger, and a negative KL in a log invites someone to "fix" the sign.
    """
    lr = np.asarray(log_ratio, dtype=np.float64).ravel()
    if lr.size == 0:
        return float("nan")
    if estimator == "k1":
        return float(-lr.mean())
    if estimator == "k2":
        return float(0.5 * (lr ** 2).mean())
    if estimator == "k3":
        return float((np.exp(lr) - 1.0 - lr).mean())
    raise ValueError(f"unknown estimator {estimator!r}; use k1, k2 or k3")


def effective_sample_size(log_ratio) -> float:
    """Normalised ESS of the importance weights, in (0, 1]. 1.0 = every sample weighted equally.

    (sum w)^2 / (n * sum w^2). Reported normalised rather than as a raw count so it is comparable
    across baselines whose batch sizes differ -- which ours do, by a lot, since each clone brings
    its own. TorchRL reports `ESS` divided by batch for the same reason.

    Low ESS means the batch is effectively smaller than it looks: a handful of samples carry the
    update. For an off-policy-corrected on-policy method that is the quantity that decides whether
    the data still describes the current policy.
    """
    lr = np.asarray(log_ratio, dtype=np.float64).ravel()
    if lr.size == 0:
        return float("nan")
    lr = lr - lr.max()                    # stabilise; scale cancels in the ratio below
    w = np.exp(lr)
    denom = (w ** 2).sum()
    return float("nan") if denom == 0 else float(w.sum() ** 2 / (lr.size * denom))


# -- off-policy family: the DrQv2 five and SAC three -------------------------------------------

def target_network_divergence(online, target, eps: float = 1e-12) -> float:
    """Relative L2 distance between an online parameter set and its target: |t - o| / |o|.

    Measured nowhere in TorchRL, and it is the cheapest early warning that a target network has
    stopped tracking. Under Polyak averaging with coefficient tau this should sit at a small
    plateau proportional to how fast the online net moves; it drifting UP without bound means the
    online network is outrunning the target, and it collapsing to 0 means the update is copying
    rather than averaging.

    That last case is the shape of a real defect TorchRL shipped -- `DDPGLoss.delay_value=False`
    by default, so `SoftUpdate` copied the source onto itself (their issue #1181, PR #1183). With
    target == online this reads exactly 0.0 and would keep reading it. REASONED, NOT
    DEMONSTRATED: that follows from the definition, but it was never run against their code, and
    the claim is offered as motivation for the metric rather than as a reproduction.

    Accepts anything array-like or an iterable of arrays, so it works on a flat vector or on a
    list of per-layer tensors without the caller having to flatten first. Relative rather than
    absolute so the number is comparable across networks of different scale.
    """
    def flat(x):
        if hasattr(x, "detach"):
            x = x.detach().cpu().numpy()
        a = np.asarray(x, dtype=np.float64)
        return a.ravel() if a.dtype != object else np.concatenate([flat(i) for i in x])

    try:
        o = flat(online)
        t = flat(target)
    except (TypeError, ValueError):
        o = np.concatenate([flat(p) for p in online])
        t = np.concatenate([flat(p) for p in target])
    if o.size != t.size:
        raise ValueError(f"online has {o.size} params, target has {t.size}")
    if o.size == 0:
        return float("nan")
    return float(np.linalg.norm(t - o) / (np.linalg.norm(o) + eps))


def diag_gaussian_entropy(log_std, dim: int | None = None) -> float:
    """Closed-form differential entropy of a diagonal Gaussian: sum_i [ log s_i + 0.5*log(2*pi*e) ].

    Exists so a continuous head's initialisation is an assertion rather than a thing someone
    notices. All four authored heads in this project init log_std = 0, so a 7-dim action space
    must report 7 * 0.5*log(2*pi*e) = 9.9327 at step 0. Any other value means the head was built
    differently from what the audit claims.
    """
    ls = np.asarray(log_std, dtype=np.float64).ravel()
    if dim is not None and ls.size == 1:
        ls = np.repeat(ls, dim)
    return float((ls + 0.5 * math.log(2 * math.pi * math.e)).sum())


def gaussian_boundary_fraction(log_std) -> float:
    """Probability mass a zero-mean N(0, s) puts OUTSIDE the action box [-1, 1]: 2*(1 - Phi(1/s)).

    This is the diagnostic C61 actually needs, and it is not the entropy. For a categorical over n
    actions the entropy bonus is bounded by log n; for a diagonal Gaussian it is unbounded above,
    and the entropy term's gradient with respect to each log_std is a CONSTANT -- so an entropy
    coefficient tuned on Procgen applies a constant upward force on log_std here, opposed only by
    the policy gradient. Entropy rising is not by itself a failure; the failure is the policy
    becoming bang-bang noise against the action clip, and that is what this measures.

    At s = 1 it is 0.317, at s = 2 it is 0.617, at s = 5 it is 0.841. A head whose boundary
    fraction is climbing past ~0.6 is emitting mostly saturated actions whatever its mean says.

    Averaged over dimensions, because a single dimension running away is the interesting case and
    a sum would hide it behind six healthy ones -- the per-dimension values are returned too.
    """
    ls = np.asarray(log_std, dtype=np.float64).ravel()
    sigma = np.exp(ls)
    # 1 - Phi(x) = 0.5 * erfc(x / sqrt(2)); erfc is stable in the tail where a plain 1 - Phi is not
    per_dim = np.array([math.erfc(1.0 / (s * math.sqrt(2.0))) if s > 0 else 0.0 for s in sigma])
    return float(per_dim.mean())


def gaussian_policy_health(log_std, dim: int | None = None) -> dict:
    """The four numbers a continuous head needs logged, together, so C61 is observable.

    `entropy` is what the loss actually adds; `mean_log_std` is the quantity the entropy term
    pushes on directly and the one that moves first; `sigma_mean` is the human-readable form; and
    `boundary_fraction` is the consequence that decides whether the run is still doing control or
    has become saturated noise. Logging only the entropy would show a number rising with no way to
    tell whether that was healthy exploration or a policy dissolving.
    """
    ls = np.asarray(log_std, dtype=np.float64).ravel()
    if dim is not None and ls.size == 1:
        ls = np.repeat(ls, dim)
    return {
        "entropy": diag_gaussian_entropy(ls),
        "mean_log_std": float(ls.mean()),
        "sigma_mean": float(np.exp(ls).mean()),
        "boundary_fraction": gaussian_boundary_fraction(ls),
    }


# -- self-test --------------------------------------------------------------------------------

def _self_test() -> int:
    ok = True

    def check(name, cond, detail=""):
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{'' if cond else '  -- ' + detail}")
        ok = ok and cond

    print("wilson_interval")
    lo, hi = wilson_interval(0, 10)
    check("p=0,n=10 has NON-zero width (the normal approx gives 0)", hi > 0.2, f"hi={hi:.3f}")
    check("p=0 lower bound is 0", lo == 0.0)
    lo, hi = wilson_interval(10, 10)
    check("p=1,n=10 upper bound is 1", hi == 1.0)
    check("p=1 lower bound is well below 1", lo < 0.8, f"lo={lo:.3f}")
    l1, h1 = wilson_interval(5, 10)
    l2, h2 = wilson_interval(50, 100)
    check("more episodes -> narrower interval", (h2 - l2) < (h1 - l1))
    check("n=0 is total ignorance", wilson_interval(0, 0) == (0.0, 1.0))

    print("iqm / bootstrap_ci")
    check("iqm discards outliers", abs(iqm([0, 1, 1, 1, 1, 100]) - 1.0) < 1e-9,
          str(iqm([0, 1, 1, 1, 1, 100])))
    lo, hi = bootstrap_ci([1.0] * 20)
    check("bootstrap of a constant is that constant", abs(hi - 1.0) < 1e-9 and abs(lo - 1.0) < 1e-9)
    a, b = bootstrap_ci(list(range(20)), seed=1), bootstrap_ci(list(range(20)), seed=1)
    check("bootstrap is deterministic given a seed", a == b)

    print("interframe_absdiff")
    still = np.tile(np.full((3, 8, 8), 120, np.uint8), (3, 1, 1))
    check("identical frames -> 0", interframe_absdiff(still, 3) == 0.0)
    moving = np.concatenate([np.full((3, 8, 8), v, np.uint8) for v in (0, 128, 255)])
    check("differing frames -> >0", interframe_absdiff(moving, 3) > 0.4,
          f"{interframe_absdiff(moving, 3):.3f}")
    check("single frame -> 0.0 meaning NOT MEASURABLE",
          interframe_absdiff(np.zeros((3, 8, 8), np.uint8), 1) == 0.0)
    check("uint8 and float [0,1] agree",
          abs(interframe_absdiff(moving, 3) - interframe_absdiff(moving / 255.0, 3)) < 1e-9)

    print("action_saturation_frac")
    check("interior actions -> 0", action_saturation_frac([[0.0, 0.5, -0.5]]) == 0.0)
    check("all-saturated -> 1", action_saturation_frac([[1.0, -1.0]]) == 1.0)
    check("counts COMPONENTS not actions",
          abs(action_saturation_frac([[1.0, 0.0, 0.0, 0.0]]) - 0.25) < 1e-9)

    print("on-policy family (names from TorchRL's ClipPPOLoss.out_keys)")
    check("perfect critic -> explained_variance 1", abs(explained_variance([1, 2, 3], [1, 2, 3]) - 1) < 1e-12)
    check("critic worse than the mean -> NEGATIVE", explained_variance([1, 2, 3, 4], [4, 3, 2, 1]) < 0)
    check("constant returns -> nan, NOT 0 ('explains nothing' is a different claim)",
          math.isnan(explained_variance([2.0] * 4, [1.0, 2.0, 3.0, 2.0])))
    check("clip_fraction counts only what left the band",
          abs(clip_fraction([0.0, 0.0, 0.5, -0.5], 0.2) - 0.5) < 1e-12)
    _lr = np.array([0.3, 0.4, 0.5])
    check("k1 CAN go negative (why we default to k3)", approx_kl(_lr, "k1") < 0)
    check("k3 never does", approx_kl(_lr, "k3") > 0)
    check("all estimators vanish for an unmoved policy",
          all(abs(approx_kl(np.zeros(20), e)) < 1e-12 for e in ("k1", "k2", "k3")))
    check("equal weights -> ESS 1.0", abs(effective_sample_size(np.zeros(32)) - 1.0) < 1e-12)
    check("one dominant weight collapses ESS",
          effective_sample_size(np.concatenate([[20.0], np.zeros(99)])) < 0.02)

    print("off-policy family (target_network_divergence is measured nowhere in TorchRL)")
    _w = np.array([1.0, -2.0, 3.0])
    check("freshly copied target -> 0", target_network_divergence(_w, _w) == 0.0)
    check("relative, so it compares across network scales",
          abs(target_network_divergence(np.ones(2), np.ones(2) * 1.1)
              - target_network_divergence(np.ones(2) * 100, np.ones(2) * 110)) < 1e-9)

    print("diag_gaussian_entropy")
    e = diag_gaussian_entropy(np.zeros(7))
    check("7-dim unit Gaussian == 9.9327", abs(e - 9.93257) < 1e-4, f"{e:.5f}")
    check("larger sigma -> larger entropy", diag_gaussian_entropy(np.full(7, 0.5)) > e)

    print("\n" + ("ALL PASS" if ok else "FAILURES ABOVE"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_self_test() if "--self-test" in sys.argv else _self_test())
