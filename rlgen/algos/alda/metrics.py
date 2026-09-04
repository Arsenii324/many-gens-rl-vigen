"""Health detectors. Each answers one question and says what to do about the answer.

Severity is the whole point of the file:

  abort  the run is producing numbers that cannot be repaired by more training. Stop, because
         every further GPU-hour is wasted and, worse, produces a plausible-looking curve.
  warn   something is off but the run may still be worth its time. Say so on every log line
         until it clears, because the IDAAC port had an alarm go unread 368 times (FINDINGS
         R16) precisely by being printed once and buried.
  info   context a reader needs to interpret a number, not a problem.

Two detectors here are ALDA-specific and have no analogue in the IDAAC port, because they watch
the mechanism the paper's whole claim rests on:

  latent/usage_entropy      if a latent always retrieves the same codebook entry it carries
                            zero information, and the "12-dimensional disentangled
                            representation" is really fewer dimensions.
  latent/frac_outside_unit  the association step maps an input to the convex hull of [-1, 1].
                            Encoder outputs far outside that range all snap to an endpoint, so
                            the representation degenerates to 2 levels per latent. On TRAINING
                            data this means the commitment loss is losing; on eval data it is
                            the OOD signal working as designed. Same number, opposite readings
                            -- which is why it is logged separately per regime.
"""
from __future__ import annotations

import math

# key -> (severity, predicate on the value, message)
_ABORT_ABS = {
    "critic/q1": 1e5, "critic/q2": 1e5, "critic/target_q": 1e5,
    "critic/loss": 1e8, "alda/total_loss": 1e6,
}


def detect(row: dict, cfg, frames: int, expected_ep_len: int | None = None
           ) -> list[tuple[str, str]]:
    """Return [(severity, message), ...] for one logged row.

    `expected_ep_len` comes from the ENVIRONMENT, not from the config. They agree for the real
    robosuite envs, but the local gate runs a short synthetic horizon, and comparing against
    `cfg.horizon` there fired a warning on every row of a perfectly healthy gate run. An alarm
    that cries wolf on the gate is an alarm nobody reads on the box (FINDINGS R16).
    """
    out: list[tuple[str, str]] = []

    for k, v in row.items():
        if isinstance(v, float) and not math.isfinite(v):
            out.append(("abort", f"{k} is {v} -- a non-finite value has entered training"))
    if out:
        return out                                  # nothing else is meaningful after that

    for k, cap in _ABORT_ABS.items():
        if k in row and abs(row[k]) > cap:
            out.append(("abort", f"{k} = {row[k]:.3e} exceeds {cap:.0e}; the critic has "
                                 f"diverged and no amount of further training recovers it"))

    a = row.get("actor/alpha")
    if a is not None:
        if a > 50.0:
            out.append(("abort", f"alpha = {a:.2f}; the entropy term now dominates the return "
                                 f"and the policy is being trained to be random"))
        elif a < 1e-5:
            out.append(("warn", f"alpha = {a:.2e} has collapsed; the policy is effectively "
                                f"deterministic and will stop exploring"))

    # reconstruction: BCE must fall below its starting point, or the encoder is learning nothing
    b = row.get("alda/recon_bce")
    if b is not None and frames > 200_000 and b > 0.69:
        out.append(("warn", f"recon BCE {b:.4f} is still at the ln2 = 0.693 no-information "
                            f"level after {frames} frames; the autoencoder is not learning"))

    ue, uemax = row.get("latent/usage_entropy"), row.get("latent/usage_entropy_max")
    # `and uemax` was a truthiness test: a legitimate max-entropy of 0.0 (a single-value
    # codebook) skipped the collapse check entirely instead of being handled.
    if ue is not None and uemax is not None and uemax > 0:
        if ue < 0.05 * uemax:
            out.append(("warn", f"codebook usage entropy {ue:.3f} of a possible {uemax:.3f}: "
                                f"the latents have collapsed onto single codes, so the "
                                f"representation carries almost no information"))
    dc = row.get("latent/dead_codes_frac")
    if dc is not None and dc > 0.9:
        out.append(("warn", f"{dc:.0%} of codebook entries are never retrieved in a batch"))

    # Only meaningful when there IS a codebook. The `continuous` arm (SAC+AE) has no codebook
    # and no snapping -- its latent is unbounded by construction, so "92% outside [-1, 1]" is
    # the expected behaviour, not a fault. This fired on the SAC+AE control within its first
    # 5k frames and was false there; the arm-blind version of the message would have trained
    # the reader to ignore a detector that is genuinely important for ALDA.
    #
    # SECOND correction: "[-1, 1]" is only the codebook's range when the codebook is FIXED.
    # With `train_codebook=True` (the QLAE arm) the codes are learned and co-scale with the
    # encoder: measured on the final runs, `latent/codebook_absmax` reached **7.3-7.8** while
    # `z_abs_mean` reached 3.1-3.4. `frac_outside_unit` then reads 0.83 and means nothing except
    # "the whole latent space grew", which is not a fault.
    #
    # The scale-FREE evidence contradicted the message outright on those runs: dead_codes_frac
    # 0.000 (every code alive) and usage_entropy 2.42 of a 2.485 maximum (97% of uniform). A
    # latent carrying "~1 bit" cannot have near-uniform usage over 12 codes. So require the
    # scale-free symptom too, and quote it -- a saturation warning that cannot point at unused
    # codes is not evidence of saturation.
    fo = row.get("latent/frac_outside_unit")
    cb = row.get("latent/codebook_absmax")
    ent, ent_max = row.get("latent/usage_entropy"), row.get("latent/usage_entropy_max")
    dead = row.get("latent/dead_codes_frac")
    underused = ((ent is not None and ent_max not in (None, 0) and ent < 0.6 * ent_max)
                 or (dead is not None and dead > 0.25))
    codebook_is_unit = cb is None or cb <= 1.5      # fixed linspace(-1, 1, k)
    if (fo is not None and fo > 0.75 and underused and codebook_is_unit
            and getattr(cfg, "latent_model", "") != "continuous"):
        out.append(("warn", f"{fo:.0%} of encoder outputs fall outside the codebook range on "
                            f"TRAINING data AND the codebook is underused "
                            f"(usage entropy {ent:.2f}/{ent_max:.2f}, dead codes {dead:.0%}): "
                            f"values are snapping to endpoints and the latent is losing capacity"))

    # episode length: Door/Lift have a fixed horizon and no early termination
    want = cfg.steps_per_episode if expected_ep_len is None else expected_ep_len
    el = row.get("ep/length")
    if el is not None and el > 0 and abs(el - want) > 1:
        out.append(("warn", f"mean episode length {el:.1f} != the fixed horizon {want}; these "
                            f"tasks do not terminate early, so either the horizon or the "
                            f"truncation flag is wrong"))

    # "Is this run still worth its remaining hours?" -- the question a 20-hour run needs asked
    # for it. Deliberately LATE and loose: returns legitimately sit flat for a long time on a
    # sparse-ish manipulation task, so firing early would train the reader to ignore it. It only
    # speaks once half the budget is gone AND a third of the budget has passed with no new best.
    # A warn, never an abort: a plateau is a result, not a malfunction, and the decision to stop
    # is a human one.
    stale = row.get("ep/frames_since_best")
    if stale is not None and frames > 0.5 * cfg.total_frames and stale > 0.35 * cfg.total_frames:
        out.append(("warn", f"no new best episode return in {int(stale)} frames "
                            f"({stale / cfg.total_frames:.0%} of the budget); the policy has "
                            f"plateaued -- check the SAC+AE control before spending the rest"))

    # ENTROPY COLLAPSE. SAC's temperature is auto-tuned to hold the policy's entropy near
    # `target_entropy = -act_dim`; if the entropy runs far BELOW that and alpha is climbing in
    # response, the policy has gone nearly deterministic and the temperature controller is
    # losing. Caught on alda-lift-s0: entropy fell 4.75 -> -12.3 against a target of -7 while
    # alpha turned around and rose 0.0126 -> 0.0266, and the return fell 13.6 -> 4.9 over the
    # same window. Nothing in the previous detector set said a word.
    ent = row.get("actor/neg_log_pi")
    target_h = -7.0                       # -act_dim; robosuite OSC_POSE + gripper
    if ent is not None and ent < target_h - 4.0:
        out.append(("warn", f"policy entropy {ent:.1f} is far below the target {target_h:.0f}: "
                            f"the policy has collapsed toward deterministic and SAC's "
                            f"temperature controller is chasing it"))

    # VALUE OVERESTIMATION -- but only once it MEANS something. Q above the achieved return is
    # normal and expected while a policy is improving: Q estimates discounted future return, so
    # early in training a ratio of 10x simply says "the critic expects to get better". The first
    # version of this detector fired on every row of every healthy run for that reason, which
    # would have made it noise. It is pathological only when the return has STOPPED improving
    # and Q keeps climbing anyway, which is what alda-lift-s0 did: Q 23 -> 56 while the return
    # fell 13.6 -> 4.9. `ep/frames_since_best` is what distinguishes the two, so a run whose log
    # predates that column simply does not get this check.
    q1, ret = row.get("critic/q1"), row.get("ep/return_raw")
    stale_f = row.get("ep/frames_since_best")
    if (q1 is not None and ret is not None and stale_f is not None and ret > 0.5
            and stale_f > 0.10 * cfg.total_frames and q1 > 4.0 * ret):
        out.append(("warn", f"critic Q1 {q1:.1f} is {q1 / ret:.1f}x the achieved return "
                            f"{ret:.1f} and the return has not improved in {int(stale_f)} "
                            f"frames; the value function is overestimating"))

    # EXPLODING GRADIENTS. [AC] applies NO gradient clipping anywhere -- verified by grep over
    # its trainer and nets -- so nothing bounds the raw gradient; only Adam's second-moment
    # normalisation bounds the STEP, and that leaves the direction dominated by outliers.
    # Measured contrast: alda-door-s0 peaks at grad/critic 7.2e2 and grad/history 7.1e1, while
    # the diverging alda-lift-s0 reaches 2.6e5 and 3.1e6 -- three to four orders of magnitude.
    for k in ("grad/critic", "grad/history", "grad/actor", "grad/trunk", "grad/decoder"):
        g = row.get(k)
        if g is not None and g > 1e4:
            out.append(("warn", f"{k} = {g:.2e}; [AC] applies no gradient clipping, so only "
                                f"Adam's normalisation bounds the step and its direction is "
                                f"dominated by outliers"))

    q = row.get("critic/q_gap")
    if q is not None and q > 100.0:
        out.append(("warn", f"|Q1 - Q2| = {q:.1f}; the twin critics have decorrelated, which "
                            f"usually precedes divergence"))
    return out


def format_alarms(alarms: list[tuple[str, str]]) -> str:
    if not alarms:
        return ""
    order = {"abort": 0, "warn": 1, "info": 2}
    return "\n".join(f"[{s.upper()}] {m}" for s, m in
                     sorted(alarms, key=lambda x: order.get(x[0], 3)))
