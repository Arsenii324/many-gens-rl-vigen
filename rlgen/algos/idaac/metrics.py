"""Detectors. One function per RUNBOOK §2 row, each with a known answer under fault injection.

Design rule: a detector is a pure function of tensors, so it can be tested without an
environment, a GPU, or a training run. `tests/test_metrics.py` feeds each one the broken input
it exists to catch and asserts that it alarms -- a detector that has never fired is
indistinguishable from a healthy run.

`ALARMS` at the bottom is the single place thresholds live, and `check_alarms` is what the
trainer calls each update. Adding a metric without a threshold is allowed; adding a threshold
without a test is not.
"""
from __future__ import annotations

import math

import torch


# ---- environment ---------------------------------------------------------- #
def obs_health(obs_u8: torch.Tensor) -> dict:
    """E2 black/degenerate renders, E3 stale frame stack.

    `interframe_absdiff` is the mean |difference| between consecutive stacked frames. A frame
    stack that was refilled with one frame (or never advanced) gives ~0.
    """
    o = obs_u8.float()
    out = {"obs/mean": float(o.mean()), "obs/std": float(o.std()),
           "obs/frac_zero": float((obs_u8 == 0).float().mean())}
    C = obs_u8.shape[1]
    if C % 3 == 0 and C >= 6:
        frames = o.view(o.shape[0], C // 3, 3, *o.shape[2:])
        out["obs/interframe_absdiff"] = float((frames[:, 1:] - frames[:, :-1]).abs().mean())
    return out


def action_health(actions: torch.Tensor) -> dict:
    """E4 actions never reaching the env in range; S1 degenerate constant policy."""
    a = actions.float()
    return {"act/abs_mean": float(a.abs().mean()),
            "act/saturation_frac": float((a.abs() > 0.99).float().mean()),
            "act/std_across_batch": float(a.std(dim=0).mean())}


def worker_health(steps_delta, episodes_delta, episodes_cum=None) -> dict:
    """E6. What a lock-step vec env can and cannot tell you about a sick worker.

    This detector used to report `env/worker_imbalance` from STEP counts and was structurally
    incapable of firing: `_RewardBookkeeping.observe` increments `steps_per_worker` for the whole
    array at once, because the vec env is lock-step -- every worker steps exactly once per
    `SubprocVecEnv.step`, or the pipe protocol has already raised. Measured across 1019 and 1023
    logged rows of two real runs, the metric had exactly one distinct value: 0.0. `analyze.py`
    then reported E6 as "ok", which is the precise failure its own docstring says it exists to
    prevent -- a direction with no data reported as a direction that was ruled out.

    What actually covers a dying worker: `SubprocVecEnv.step`/`reset` raise with the worker's own
    traceback (the pipe error path). That is a loud failure, not a silent one, and it needs no
    threshold. So the honest reporting is:

      * `env/steps_per_worker_min`   -- kept, informational, NOT a detector
      * `env/episodes_per_worker_min`-- kept, informational
      * `env/episode_imbalance`      -- the one that can genuinely vary, and is thresholded

    Episode imbalance is real but weak here while workers stay phase-locked (R18): they reset
    together, so they also finish episodes together. It is reported rather than trusted, and
    `analyze.py` marks E6 `covered-by-construction` instead of `ok`.
    """
    s = torch.as_tensor(steps_delta).float()
    e = torch.as_tensor(episodes_delta).float()
    out = {
        "env/steps_per_worker_min": float(s.min()) if s.numel() else 0.0,
        "env/episodes_per_worker_min": float(e.min()) if e.numel() else 0.0,
    }
    if e.numel() and float(e.max()) > 0:
        # INFORMATIONAL ONLY -- no longer the E6 detector. On per-rollout deltas this saturates
        # the moment workers are staggered (R18): in any rollout some workers finish an episode
        # and others do not, so max=1, min=0, and the ratio is a constant 1.0. Measured: exactly
        # 1.0 in all 128-132 logged rows of all four box-2 runs, never any other value. A DEAD
        # worker produces the same 1.0, so the metric had no discriminating power left -- it was
        # firing WARN on healthy runs while being unable to detect the thing it named.
        out["env/episode_imbalance"] = float((e.max() - e.min()) / e.max())
    if episodes_cum is not None:
        c = torch.as_tensor(episodes_cum).float()
        if c.numel():
            # E6, derived rather than tuned. Worker i has completed floor((T + offset_i) / L)
            # episodes after T steps, so for any two workers the CUMULATIVE counts differ by at
            # most 1 -- whether or not they are staggered. A stalled worker's count stops growing
            # while the others keep ticking, so its spread grows without bound. That gives a
            # bound which is a theorem for healthy operation and unbounded for the failure.
            out["env/episode_spread_cum"] = float(c.max() - c.min())
    return out


def seed_collision(init_obs_hashes) -> dict:
    """E7. Identical initial observations across workers mean a shared seed, which silently
    reduces N parallel environments to one while every other metric looks healthy."""
    n = len(init_obs_hashes)
    return {"env/distinct_init_obs_frac": (len(set(init_obs_hashes)) / n) if n else 1.0}


# ---- optimisation --------------------------------------------------------- #
def explained_variance(returns: torch.Tensor, values: torch.Tensor) -> float:
    """O3. 1.0 for a perfect predictor, 0.0 for a constant one, negative for worse-than-mean."""
    r, v = returns.flatten().float(), values.flatten().float()
    var = r.var()
    if float(var) < 1e-12:
        return 0.0
    return float(1.0 - (r - v).var() / var)


def ppo_health(ratio: torch.Tensor, logratio: torch.Tensor, clip_param: float) -> dict:
    """O2. approx_kl is Schulman's low-variance estimator, which is what CleanRL/SB3 report."""
    with torch.no_grad():
        return {"pi/approx_kl": float(((ratio - 1) - logratio).mean()),
                "pi/clipfrac": float(((ratio - 1).abs() > clip_param).float().mean()),
                "pi/ratio_max": float(ratio.max())}


def grad_norms(named_modules: dict) -> dict:
    """O4. Per-module, because one exploding head is invisible in a global norm."""
    out = {}
    for name, mod in named_modules.items():
        if mod is None:
            continue
        tot = 0.0
        for p in mod.parameters():
            if p.grad is not None:
                tot += float(p.grad.detach().pow(2).sum())
        out[f"grad_norm/{name}"] = math.sqrt(tot)
    return out


def magnitude_health(**named) -> dict:
    """O9. NaN/Inf is the LAST stop on the way to a broken run, not the first.

    A value function can diverge through 19 orders of magnitude while staying perfectly
    finite -- which is exactly what happened: v/loss went 0.27 -> 5.3e18 over 69 updates and
    `health/nonfinite` stayed 0 the whole way. Absolute magnitude is the detector that would
    have caught it at update ~5 instead of never.
    """
    return {f"mag/{k}": float(abs(v)) for k, v in named.items()}


def nonfinite_count(*tensors) -> int:
    """O5. Checked on every loss before .backward(); a non-zero value aborts the run."""
    n = 0
    for t in tensors:
        if t is not None and torch.is_tensor(t):
            n += int((~torch.isfinite(t)).sum())
    return n


def adversary_health(disc_logit: torch.Tensor, label: torch.Tensor,
                     enc_loss: float) -> dict:
    """O7, IDAAC-specific. Two ways the adversarial game degenerates:
    the discriminator wins outright (acc -> 1, the encoder never catches up), or there is
    nothing to learn and enc_loss sits at log 2 = 0.6931 from step 0."""
    with torch.no_grad():
        pred = (disc_logit > 0).float()
        return {"disc/acc": float((pred == label).float().mean()),
                "disc/logit_abs_mean": float(disc_logit.abs().mean()),
                "disc/enc_loss": float(enc_loss),
                "disc/enc_loss_minus_log2": float(enc_loss - math.log(2.0))}


def advantage_head_tracking(pred: torch.Tensor, target: torch.Tensor) -> dict:
    """O8. If the advantage head is wired wrong (action at the wrong scale, one-hot path left
    in) the loss can still fall while the correlation stays at zero."""
    p, t = pred.flatten().float(), target.flatten().float()
    p = p - p.mean()
    t = t - t.mean()
    d = p.norm() * t.norm()
    return {"adv_head/corr": float((p @ t) / d) if float(d) > 0 else 0.0}


# ---- cross-field invariants ----------------------------------------------- #
def consistency(row: dict) -> dict:
    """Relationships between logged fields, which no single-metric threshold can see.

    The bug that invalidated two training runs was visible only here: `ep/truncated` read
    1024 per rollout (4 envs x 256 steps -- the flag was true on EVERY step) while only ~2
    episodes actually ended. A 500x violation, present in every row, next to a metric I read
    as confirmation because the *other* half of it, ep/terminated == 0, was correct.

    Univariate detectors are blind to this by construction. Ratios are the fix.
    """
    out = {}
    tr, ends = row.get("ep/truncated"), row.get("ep/ends_this_rollout")
    if tr is not None and ends is not None:
        # every truncation must correspond to an episode end; equality is the healthy case
        out["consistency/trunc_per_end"] = float(tr) / max(float(ends), 1.0)
    steps, ep_len = row.get("rollout/frames"), row.get("ep/length")
    if steps and ep_len and float(ep_len) > 0:
        out["consistency/expected_ends"] = float(steps) / float(ep_len)

    # An exact IDENTITY, not a heuristic. Explained variance is defined as
    #     ev = 1 - Var[R - V] / Var[R]
    # and the pre-normalisation advantage is exactly R - V, so
    #     adv_std_prenorm == return_std * sqrt(1 - ev)
    # must hold to floating-point precision. Verified across 839 logged rows of two live runs:
    # median relative error 1e-7, max 1.7e-6.
    #
    # It ties three separately-computed fields together, so it catches a family nothing else
    # does: advantages built from stale values, `ev` computed over a different slice than the
    # advantages, or a value network swapped between the two call sites. Each of those leaves
    # every individual metric looking entirely reasonable.
    a, rs, ev = row.get("adv/std_prenorm"), row.get("v/return_std"), row.get("v/explained_variance")
    if a is not None and rs is not None and ev is not None:
        rs, ev = float(rs), float(ev)
        if rs > 1e-9 and ev < 0.999:          # guard: ev -> 1 makes the prediction vanish
            pred = rs * math.sqrt(max(0.0, 1.0 - ev))
            if pred > 1e-9:
                out["consistency/adv_identity_relerr"] = abs(float(a) - pred) / pred
    return out


# ---- thresholds ----------------------------------------------------------- #
# (metric, comparison, threshold, severity). "abort" stops the run; "warn" is logged loudly.
ALARMS = [
    ("obs/std", "<", 1.0, "abort"),            # E2 black render
    ("obs/frac_zero", ">", 0.95, "abort"),     # E2
    ("obs/interframe_absdiff", "<", 1e-6, "warn"),   # E3 stale stack
    ("act/saturation_frac", ">", 0.5, "warn"),       # E4 / S1
    ("adv/std_prenorm", "<", 1e-6, "abort"),   # D3 degenerate advantages
    ("disc/pair_purity", "<", 1.0, "abort"),   # D4 pairs crossed an episode
    ("health/nonfinite", ">", 0.0, "abort"),   # O5
    # O9 magnitude. Thresholds are deliberately loose -- they exist to catch divergence,
    # not to police tuning. Normalised returns live at |r| <= reward_clip * num_steps, and a
    # healthy value loss on that scale is O(1e2) at most.
    ("mag/v_loss", ">", 1e6, "abort"),
    ("mag/adv_std_prenorm", ">", 1e4, "abort"),
    ("mag/ep_return_norm", ">", 1e5, "abort"),
    ("mag/value_pred", ">", 1e5, "abort"),
    # cross-field: more truncations than episode ends means the truncation flag is wrong
    ("consistency/trunc_per_end", ">", 1.5, "abort"),
    # An identity, so any real violation is a bug rather than bad luck. 1e-3 is ~600x the worst
    # float error measured over 839 real rows (1.7e-6), which leaves ample headroom while still
    # catching a genuine mismatch by orders of magnitude.
    ("consistency/adv_identity_relerr", ">", 1e-3, "abort"),
    ("pi/approx_kl", ">", 0.05, "warn"),       # O2
    ("pi/log_std_mean", "<", -3.0, "warn"),    # O1 collapse
    ("pi/log_std_mean", ">", 1.0, "warn"),     # O1 blow-up
    ("disc/acc", ">", 0.9, "warn"),            # O7 discriminator wins
    # E6: step imbalance was unfireable by construction; episode imbalance can vary
    ("env/episode_imbalance", ">", 0.5, "warn"),
    ("env/distinct_init_obs_frac", "<", 1.0, "warn"),  # E7 shared seed
]


def check_alarms(row: dict, warmup: bool = False) -> list[tuple[str, str, float]]:
    """Returns [(severity, metric, value)] for every threshold currently violated.

    `warmup` downgrades aborts to warnings for the first few updates, where explained
    variance and KL are legitimately wild. It never downgrades E2/O5 -- a black render or a
    NaN is never acceptable, at any point in the run.
    """
    never_downgraded = {"obs/std", "obs/frac_zero", "health/nonfinite",
                        "mag/v_loss", "mag/adv_std_prenorm", "mag/ep_return_norm",
                        "mag/value_pred", "consistency/trunc_per_end",
                        "consistency/adv_identity_relerr"}
    fired = []
    for key, op, thr, sev in ALARMS:
        if key not in row or row[key] is None:
            continue
        v = float(row[key])
        if (op == "<" and v < thr) or (op == ">" and v > thr):
            if warmup and sev == "abort" and key not in never_downgraded:
                sev = "warn"
            fired.append((sev, key, v))
    return fired


EXPECTED_KEYS = {
    "obs/mean", "obs/std", "obs/frac_zero", "obs/interframe_absdiff",
    "act/abs_mean", "act/saturation_frac",
    "env/steps_per_worker_min", "env/episodes_per_worker_min",
    "env/distinct_init_obs_frac", "diag/corr_A_t",
    "ep/return_raw", "rollout/reward_norm_sum", "ep/length", "ep/truncated",
    "ep/terminated", "v/return_std",
    "rew/raw_mean", "adv/std_prenorm",
    "pi/pg_loss", "pi/entropy", "pi/log_std_mean", "pi/approx_kl", "pi/clipfrac",
    "pi/epochs_ran", "pi/kl_early_stopped",
    "v/loss", "v/explained_variance",
    "health/nonfinite", "opt/lr", "time/fps", "time/collect_fps",
    "time/update_s", "time/learner_frac", "update_idx", "frames",
    "mag/v_loss", "mag/adv_std_prenorm", "mag/ep_return_norm", "mag/value_pred",
    "consistency/trunc_per_end", "consistency/adv_identity_relerr",
    "diag/corr_V_t",
}
"""RUNBOOK gate G3: the toy slice asserts this set is present in a logged row. Catches the
most common real failure -- a metric quietly dropped in a refactor."""
