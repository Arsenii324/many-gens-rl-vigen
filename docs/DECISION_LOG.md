# Decision log

> **HISTORICAL.** These entries are from the superseded `rlgen` port era and record *why*
> things were done, not what is true now. The live register of open decisions is
> [`CONSTRUCTION.md`](CONSTRUCTION.md).

Every integration-significant decision made **while actually developing/integrating something
new** — not a retrospective of the existing, already-integrated codebase's history (that's
`FAITHFULNESS.md`/`VALIDATION.md`/git history's job). Scoped specifically to the narrow thing
those don't centralize: **every place a choice was made about what a value, argument, or
interface *means*, not just what type it has**, for code actually being built in the current
arc of work. Python lets a float be a float wherever one is expected; it says nothing about
whether that float is normalized or raw, a coefficient or a physical quantity, a count or an
index. Any time new/changed code assumes, changes, or fixes such a thing — normalized vs. raw
input, truncation vs. termination vs. done, a threshold's direction, what a counter counts, which
pass of a stochastic module a downstream consumer reads — it belongs here, explicitly, with its
effect actually seen (built, tested, verified — not merely proposed).

**Rule**: "left it at its existing default" is not a decision and does not get an entry. Neither
does a fix to pre-existing code made before this log started — that history lives in git log and
the topic-specific docs, not here. This file starts sparse and grows only as actual new
development happens; a short file early on is correct, not a gap.

**Format per entry**: date, one-line title, the decision, the semantic assumption it makes
explicit, why, and where (file:line or commit).

---

## 2026-08-13 — Choke-point instrumentation: what `step_calls`/`action_clip_events` actually measure

**Decision**: `rlgen/envs.py`'s new `step_calls` counts real `env.step()` calls — i.e., **agent
decisions**, not physical simulator ticks. `action_clip_events` counts a call as "clipped" when
any dimension of the *pre-clip* action's absolute value exceeds `1.0` (`mag = abs(raw).max()`,
strict `>`, per-dimension max rather than an L2/other norm).
**Assumption made explicit**: `action_repeat` is folded into ONE `env.step()` call internally (via
the wrapped `ActionRepeatWrapper` for `RoboEnv`, and directly for `SyntheticEnv`) — so
`step_calls x action_repeat` is the frame count, not `step_calls` alone. A reader cross-checking a
baseline's own reported "frames" against `step_calls` must apply that multiplication or the
numbers will disagree for any `action_repeat != 1`, which would look like a bug and isn't one.
The per-dimension-max choice for `action_clip_events` (rather than e.g. an L2 norm over the action
vector) means a single wildly-out-of-range dimension in an otherwise-fine action vector still
counts as one clip event — a deliberate choice to catch per-dimension miscalibration, not just
aggregate magnitude.
**Where**: `rlgen/envs.py:41-48` (module docstring point 5), `rlgen/envs.py:129-139` (`Env` base
class attribute docs). Built, red-green tested, committed both branches.

## 2026-08-13 — `_assert_action_contract`'s shape check is exact-match, not "at-least"

**Decision**: `_assert_action_contract` raises unless `action.shape == (act_dim,)` exactly —
rejects both too-few and too-many dimensions, and rejects any action that isn't rank-1.
**Assumption made explicit**: a caller handing in `(act_dim, 1)` or `(1, act_dim)` (an easy mistake
after a batch-dim squeeze goes wrong) is a bug to catch, not a shape numpy should be allowed to
broadcast past silently — mirrors the existing `_assert_contract`'s equally strict treatment of
`obs.shape`.
**Where**: `rlgen/envs.py:133-139`. Built, red-green tested, committed both branches.

---

## 2026-08-14 — Reward-normalizer placement: algorithm-side hook, per-baseline transcription, raw stays raw

**Decision**: reward normalization is part of an algorithm's own reference, not part of what the
harness measures (`porting-directive.md` §2). Implemented as a `normalize_reward(raw_reward,
done) -> float` method on each on-policy `Learner`, called by `trainer_onpolicy.py` between
`env.step()`'s raw reward and `storage.insert()`. `idaac/algo.py::Learner` now has a real
transcription (Welford variance of the discounted return, `reward / sqrt(var+1e-8)` clipped to
`±reward_clip`) sourced from `gen-rebuttal/vigen-idaac/vigen_idaac/envs.py::RunningReturnStd` —
the same lineage `idaac/config.py`'s `normalize_reward`/`reward_clip` fields already cited but
nothing previously read. `onpolicy_ext.py::CTRLLearner`, `ppg/algo.py::Learner`,
`ibac_sni/algo.py::Learner` get explicit, clearly-commented no-op overrides for now (tasks
#21/#22/#23) — not silently inherited defaults.

**Semantic assumption made explicit**: `RolloutStorage.rewards` (what GAE/`compute_returns`
reads) and `RolloutStorage.rewards_raw` (what the harness/evaluator would read, if anything ever
does) are different quantities from the moment they're written, not the same value duplicated —
`idaac/storage.py` already named them this way (`# normalized, + boot value` vs. `# never touched
by the normalizer`) but nothing enforced the difference until this change. `ep_ret` (episode
return, logged) is accumulated from the pre-normalization `reward` in `trainer_onpolicy.py`,
upstream of this call, so it was never affected either way.

**Why a per-Learner method, not a shared utility class**: `porting-directive.md` §1 — stateful
objects are never lifted into shared code across baselines, "identical code under different
parameters is a different object, not the same object differently configured." `ctrl`'s own
reference (`ext/ctrl_public/vec_env.py`) uses the same Welford-var-of-discounted-return-then-clip
shape as `idaac`'s gen-rebuttal lineage, but is a separately-sourced implementation belonging in
CTRL's own hermetic module, not borrowed via `CTRLLearner(Learner)`'s inheritance from
`idaac.algo.Learner` — inheritance would have applied it silently, which is exactly why the
no-op override on `CTRLLearner` exists as an explicit line, not an omission.

**Scope check across all 12 baselines, not just the on-policy family**: `alda` already correctly
declared `normalize_reward=False` with a cited reason (SAC's auto-tuned temperature targets
entropy against reward scale). `drqv2`, `svea`, `sgqn`, `curl`, `drq`, `rad`, `soda` checked
directly against their own reference/backbone files — zero mentions of reward
normalization/scaling in any of the seven. `NotApplicable` for all 8, not merely unaddressed.

**Where**: `rlgen/algos/idaac/algo.py` (`_RunningReturnStd`, `Learner.normalize_reward`);
`rlgen/algos/onpolicy_ext.py::CTRLLearner.normalize_reward`;
`rlgen/algos/{ppg,ibac_sni}/algo.py::Learner.normalize_reward`; `rlgen/trainer_onpolicy.py`
(call site). Built, red-green tested (`tests/test_reward_normalizer.py` — mutated the normalizer
to bypass itself, confirmed 3 of 5 tests fail, restored, confirmed green), full suite run clean
apart from one pre-existing, unrelated failure (`test_preflight_does_not_fire_for_a_baseline_with_no_data_needs`,
a local GLFW/OpenGL import gap, confirmed to fail identically with these changes stashed out).
Full details and the per-family checked-reference citations: `docs/REGISTER.md`, "reward-normalizer
placement decision" and the audit entry immediately above it. `ppg`/`ibac_sni`/`ctrl`'s own
normalizers remain open (tasks #21/#22/#23) — this entry covers the mechanism and `idaac` only.

---

*(The comparability-contract meta-plan's Stages 1-6 were verification/instrumentation confirming
the EXISTING pipeline already satisfies the interface contract, not integration work on any
baseline's internals — the entry above is the first real one once actual re-architecture/
integration work began.)*
