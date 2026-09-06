# Review 17 — item by item

Source: `notes/ai-review-17-external.md`. Section numbers match the review's own headings.

## Overview table and top-line conclusion

**Claim**: RAD/SODA/ALDA/DrQ-v2 are "already in reasonably strong shape"; the major problems are
IDAAC/PPG/CTRL/IBAC-SNI and the RL-ViGen-variant identity of CURL/SVEA/SGQN; IDAAC and CTRL have
"the clearest source-backed hyperparameter corrections"; SGQN has "a concrete mismatch against
RL-ViGen's own published Door table."

**What I did**: Accepted this triage as the priority ordering for my own work this session —
IDAAC got the deepest, most complete treatment (full implementation, not just documentation);
CTRL got a register entry naming the conflict; SGQN's specific mismatch was cross-checked against
this project's own pre-existing analysis (`C64`, see below) and found to already be tracked in
more depth than the review states. **CORROBORATED, NOT PRIMARY-VERIFIED** for RAD/SODA/ALDA/DrQ-v2
specifically — I did not re-derive their "high fidelity" status from their own source this
session; I inherited the project's existing `CLAIMS-LEDGER.md`/`FAITHFULNESS.md` claims about them,
which predate this review cycle. See `04-blind-spots-and-unverified-claims.md`.

**The naming proposal** (`drqv2-rlvigen`, `curl-rlvigen`, etc.): **NOT YET ADDRESSED** as an actual
renaming across the codebase. I applied the *labeling logic* to individual CLAIMS-LEDGER rows I
touched (idaac, and implicitly ctrl/sgqn via the entries below) but did not rename result files,
job configs, or the `baselines` list in `families.json`. This is a real, still-open piece of both
reviews' advice that nothing in this session executed as a rename.

---

## 1. IDAAC

**Claim**: production should move from Procgen-parser defaults to the published DMC
continuous-control recipe; the exact table given (processes=1, steps=2048, minibatches=32,
ppo_epoch=10, lr=3e-4, γ=.99, entropy=0, value_freq=32, α_a=α_i=.1, frame_stack=3, linear LR decay
over 1M steps) plus a separate concern about what `level_seed`/"instance identity" means on Door.

**VERIFIED, independently, before this review arrived.** This exact table was already re-derived
directly from `ext/idaac/raileanu21a-supp.pdf` §E earlier in this session (DECISION-SHEET A35),
triggered by an unrelated external note contradicting my own then-current (wrong) reasoning that
frame-stacking was theoretically incoherent for IDAAC. Every number in review 17's table matches
what I independently read from the PDF. This is the one row in this entire response where I can
say with full confidence that the review and my own primary-source read agree, because I did the
primary-source read first and the review corroborated it after the fact, not the other way round.

**What I did about it, in full**:
- Implemented the frame-stack machinery that did not previously exist at all in `runnable/idaac`
  (a `FrameStack` wrapper in `make_rlvigen_venv`, a channel-count-aware `VecPyTorchProcgen`, a real
  `update_linear_schedule` for the LR decay) — see `03-changes-made.md` commit `93ae962`.
- Made the full table `families.json`'s actual idaac production config, replacing the P defaults
  entirely, per the owner's later explicit direction to complete this rather than leave it as a
  documented-but-unreached target (`15b4e73`).
- **Retained the literal 1,000,000-step LR-decay horizon**, not rescaled to the project's 600k
  budget, exactly as the review recommends — the decay therefore never fully reaches zero within
  any run this project makes. Verified the scheduler's arithmetic in isolation before wiring it in.
- **Removed** a v100-specific `num_processes=16` host-profile override that predated this review:
  once `num_processes` is fixed at 1 by the paper's own design, it is no longer a per-host
  throughput knob a profile should be allowed to move.

**The `level_seed`/"instance identity" point**: **TAKEN ON TRUST, not acted on beyond a documented
caveat.** I did not attempt any code change here — this project's existing `CLAIMS-LEDGER.md` row
for idaac already carried a version of this caveat before the review (`level_seed is now
episode-scoped ... an episode is not a Procgen level`), and I only lightly updated the wording of
that row when I rewrote it for the C2 transition. I did not evaluate whether "if you have a real
persistent visual-domain/background/randomization identity available, that is the preferable
label" is actually achievable in this project's setup (Door has one training visual scene per the
current protocol) — this is a real, unresolved question the review raises that I have not engaged
with substantively.

**Confidence**: VERIFIED for the hyperparameter table and its implementation. **Not validated by a
full-length training run** — see `04-blind-spots-and-unverified-claims.md` for exactly what that
means and does not mean. TAKEN ON TRUST / NOT YET ADDRESSED for the level-identity relabeling.

---

## 2. PPG

**Claim**: the project's existing "8×256 matches 1×2048 in sample count and auxiliary cadence,
therefore it's fine" reasoning is true but insufficient — rollout *geometry* (GAE over one long
trajectory vs. eight short fragments, minibatch size 256 vs 64) still differs. Gives a corrected
target config; flags one genuine uncertainty (whether `aux_lr` should also become 3e-4, since
OpenAI PPG has separate primary/auxiliary rates and the continuous-control source may not specify
both).

**CORROBORATED, NOT PRIMARY-VERIFIED, and NOT YET IMPLEMENTED.** This project's own A26 already
reached almost exactly review 17's point independently (the "8×256 matches 2048=2048" language it
critiques is this project's own A26/CORRECTIONS #58) — I corrected A26's wording this session to
say "matches sample count and auxiliary-phase interaction count, not rollout geometry," matching
the review's own phrasing closely, but **I did not implement PPG's frame-stack wrapper or the
`1×2048/32-minibatch` rollout geometry change**. Per Codex's Q54, PPG's continuous-control
implementation is explicitly their task, not mine, and I confirmed in the mailbox (`A62`) that I
am not touching PPG code. The `aux_lr` uncertainty the review names is, as far as I know,
**still completely open** — I have not seen it addressed by either agent as of this writing.

**Confidence**: CORROBORATED for the geometry-vs-cadence distinction (I independently re-derived
the arithmetic myself when fixing A26's wording, not just trusted the review). NOT YET ADDRESSED
for the actual implementation, which is explicitly someone else's open task.

---

## 3. CTRL

**Claim**: production currently runs the official code's own parser defaults (num_envs=64 on
V100, ppo_epoch=3, lr_ctrl=1e-4, cluster_len=10, temp=0.1, nearest-clusters=1); the paper's LaTeX
appendix gives a different, internally consistent table (num_envs=32, ppo/RL epochs=1,
representation epochs=1, lr_repr=5e-4, cluster_len=2, nearest_clusters=3, temperature=.3); the
review recommends switching to the paper's table, and names one implementation trap (the paper's
"nearest clusters" `k=3` is this codebase's `myow_k`, not the separate Sinkhorn `k`).

**VERIFIED against the live tree, and the review's "currently inherits" claim is accurate.**
I independently re-read `runnable/ctrl/train_ppo.py`'s own `absl` flag defaults (lines 94-119) and
`datasphere/native/families.json`'s `ctrl` entry, including its `v100` host-profile override, and
confirmed the review's description of what's currently running is exactly right, down to the
`myow_k`-not-`k` naming trap it names (I found the same distinction independently by reading the
flags myself, then confirmed the review named it too).

**Where I diverge from review 17's own recommendation**: review 17 says "I would use those
[paper] values." Review 18, reading the identical evidence, says the opposite — "do not 'fix'
cluster_len 10→2 yet... current T=10 is no less source-backed than T=2" — and calls it an
unresolved paper-vs-official-code conflict rather than a decided fix. **I sided with review 18's
framing.** My reasoning, in full: (a) this project's own established convention for exactly this
shape of disagreement (see `C64` on SGQN, discussed below) is to declare a conflict and pick the
side already running unless there's a forcing reason to move; (b) this project already has a
documented precedent of deliberately choosing "move toward the released configuration" for CTRL
specifically (`families.json`'s own 2026-09-03 note on the `num_processes` 4→16 change); (c)
switching CTRL's live parameters this late in the session would have been exactly the kind of
reactive mid-freeze change this project's own governing rule (mailbox Q47) exists to prevent. I
filed this as register item `C97` (`docs/CONSTRUCTION.md#c97`): the released-code profile is the
declared operational default, the paper-vs-code conflict is recorded, and a paper-profile variant
config was built and verified runnable (then retired once the campaign's scope narrowed to one
predeclared run per algorithm, per a later owner instruction — see `03-changes-made.md`).

**Confidence on the numbers themselves**: **UPDATE — now VERIFIED, independently, against the
primary source.** This was originally written as this response set's single most important
unverified claim (`04-blind-spots-and-unverified-claims.md` named it explicitly). I subsequently
read `ext/papers-sorted/CTRL-Cross-Trajectory-Representation-Learning/latex-source/appendix.tex`
directly — the actual LaTeX appendix, not either review's extraction of it — and every number both
reviews cite is exactly correct (γ=.999, λ=.95, 256 timesteps/rollout, 1 epoch, 8192 samples,
entropy=.01, clip=.2, 32 envs, frame_stack=1, 200 clusters, k=3, T=2, β=.3). **One real correction
to how both reviews phrase it**: the paper's table has a single row, "Learning rate — Learning
rate for RL and representation learning — 5e-4," not two independently-specified parameters
(`lr_rl`, `lr_repr`) that happen to coincide — confirmed by grepping the same source for a second,
representation-specific rate, which does not exist. This doesn't change the recommendation (both
this project's `lr` and `lr_ctrl` would need to be 5e-4 to match the paper) but it is a real,
citable difference from how both reviews describe the table. See `docs/CONSTRUCTION.md#c97` for
the full citation, and `04-blind-spots-and-unverified-claims.md` for how this gap was found and
closed.

**The JAX/Flax/Optax version claim** ("authors' approximately JAX 0.2.17 / Flax 0.3.4 / Optax
0.0.9 environment" vs. this project's 0.4.35/0.10.2/0.2.3): **TAKEN ON TRUST.** I did not verify
the authors' claimed original versions against anything (their repo's own `requirements.txt`, a
release date, etc.) this session. This project's own `runnable/_launch/ctrl.sh` independently
documents a version gap for a related reason (`tensorflow_probability` compatibility forcing
`jax<0.5`), which is consistent with *some* version tension existing, but I did not check whether
the specific numbers review 17 names for the authors' environment are correct.

---

## 4. IBAC-SNI

**Claim**: the project already fixed two serious problems (Impala trunk instead of MiniGrid
network; β=1e-4). Remaining gaps: VIB latent 64 vs CoinRun's 256; single VIB sample vs CoinRun's
12; posterior scale unshifted `softplus(ρ)` vs CoinRun's shifted `softplus(ρ-5)`; L2 absent vs
CoinRun's 1e-4; the authors' `-uda` flag absent (should be checked, not assumed to mean
DrQ-style random shift); the `entropy_coef=0` decision is a defensible adaptation, not a fidelity
repair, provided the underlying `.01`-causes-runaway finding reproduces.

**NOT INDEPENDENTLY VERIFIED, NOT ACTED ON beyond one factual correction (below).** I did not read
IBAC-SNI's own CoinRun source (`ext/IBAC-SNI`) to confirm the 256-d latent, 12-sample, or
`rho - 5` claims myself this session. I have no reason to doubt them — they are specific and
plausible, and the project's own prior audit work (A17, A37, referenced in DECISION-SHEET)
independently arrived at the CoinRun-lineage commitment the review agrees with — but "specific and
plausible, and someone else's prior audit agrees" is not the same as reading the code, and I want
that stated plainly rather than implied. Per Q54/A62 I am also not touching IBAC-SNI's own
implementation code this session (Codex's territory), so none of the concrete fixes (L2, sample
count, posterior scale, `-uda`) have been attempted by me.

**The one thing I did do**: independently read `ext/baseline_resources/11_ibac_sni/paper_
1901.10902.pdf` directly with `pdftotext` and confirmed it is a *different paper entirely*
("InfoBot: Transfer and Exploration via the Information Bottleneck," Goyal et al., ICLR 2019), not
IBAC-SNI — a provenance bug neither review's own text flags for this specific file (review 18
separately catches the arXiv-ID-string mismatch, 1901.10902 vs 1910.12911, but frames it as a
labeling error; I found the underlying file itself is the wrong document, a more severe version of
the same finding). See `02-review-18-item-by-item.md` and `03-changes-made.md` — this was Luna's
to fix in the source index (`ext/` is read-only to me), and it has since been fixed.

**Confidence**: TAKEN ON TRUST for every architecture-gap claim in the review's own table.
VERIFIED for the wrong-PDF finding, by direct read.

---

## 5. SGQN

**Claim**: RL-ViGen's own Door/Lift Table 6 specifies quantile=.90, consistency weight=.7,
aux_lr=8e-5; the currently-running released code instead uses .93/.9(hardcoded)/1e-4; recommends
switching production to the Table 6 values and exposing the hardcoded consistency coefficient.

**VERIFIED, REVIEW'S NUMBERS MATCH, BUT ITS RECOMMENDATION WAS NOT ADOPTED — because this project
had already reasoned through this exact question in more depth, before either review arrived.**
This project's own register item `C64` (surfaced 2026-08-24, well before this review cycle)
already documents the identical paper-vs-code gap with the identical numbers, plus a deeper finding
review 17 does not mention: this project's `action_repeat` field *already* follows the paper over
the shipped code for a different SGQN-adjacent value, while `feature_dim`/`aux_lr` follow the
shipped code — an internal inconsistency in *which side wins on disagreement*, with no stated rule
prior to `C64`. `C64`'s own resolution (2026-09-03, well before this review cycle): **keep the
shipped code's values**, on reproducibility grounds ("the shipped defaults are the only complete,
reproducible, self-consistent configuration upstream actually distributes... no run of the
shipped repository is comparable to their published curve, because the published curve was
produced by a configuration the repository does not contain"). I confirmed this is genuinely
already-running production behavior (not a stale doc) via `test_executed_hyperparameters_audit.py`
and a direct read of the composed Hydra config, and left it as-is — see `A64` in
`notes/claude-answers.md` and `02-review-18-item-by-item.md`'s SGQN entry, since review 18 reaches
the same "keep the released profile, declare the conflict" conclusion C64 already had.

**What I have not checked**: the review's claim that the consistency-weight literal is "buried
inside `sgqn.py`" at a specific hardcoded `0.9`. I attempted to locate this exact line
(`grep -rn "consistency_weight\|consistency_coef"`) and found nothing by that name in the live
tree. Codex's own added test (`test_sgqn_released_profile_is_traceable_from_hydra_config_to_loss`)
pins a related literal (`critic_loss += 0.9 * ...` in `RL-ViGen-upstream/algos/sgqn.py`) which is
almost certainly the same value under a different description, but I have not confirmed this
myself by reading that exact source line in context. **This is a named gap in
`04-blind-spots-and-unverified-claims.md`.**

**Confidence**: VERIFIED for the three headline numbers (matches this project's own prior,
deeper, independent analysis). NOT VERIFIED for the exact code location of the hardcoded
consistency literal.

---

## 6. CURL

**Claim**: RL-ViGen's own supplement states it replaces CURL's online/target dual-encoder with a
single encoder; the project's implementation follows RL-ViGen's choice; call it `CURL-RLViGen` in
any manifest, and if an original-CURL sensitivity check is wanted, run a second variant via DMCGB.

**CORROBORATED, NOT PRIMARY-VERIFIED, RENAME NOT DONE.** I independently confirmed the *code-level*
fact this claim rests on — `RL-ViGen-upstream/algos/curl.py::CURLAgent(DrQV2Agent)`, i.e. CURL's
RL-ViGen implementation literally inherits the DrQ-v2 agent class, confirming both "single encoder,
not online/target" (DrQ-v2-lineage agents don't have that structure at all) and, as a side effect,
that CURL is DDPG-style rather than SAC — a fact I used in a different, unrelated fix this session
(A25's mechanism-taxonomy correction, see `03-changes-made.md`). I did **not** independently read
RL-ViGen's own supplementary PDF to confirm it states this design choice explicitly in those words
— I am relying on the code's structure as sufficient evidence for my own purposes, which is not
quite the same claim as "the paper says so." The renaming to `CURL-RLViGen` in result labels,
job configs, or `families.json` — **not done**, same as the general naming recommendation above.

---

## 7. SVEA

**Claim**: RL-ViGen's SVEA preserves the augmentation/critic-regularization idea but its learner
is DrQ-v2-lineage, not canonical SVEA's SAC-based DMCGB implementation; keep it for RL-ViGen
results, rename for clarity, don't rewrite.

**VERIFIED, independently, this session, as a side effect of a different fix.** I read
`RL-ViGen-upstream/algos/svea.py::SVEAAgent` directly and confirmed it uses `stddev_schedule` (a
scheduled deterministic-actor exploration noise) with no `log_alpha`/entropy term anywhere in the
class — definitively DDPG-style, not SAC, independent of and prior to reading this claim in either
review. This is also independently corroborated by this project's own pre-existing
`CLAIMS-LEDGER.md` row for svea (`Uses SODA's random_overlay, not SVEA's random convolution`),
which names a *different* fidelity gap in the same augmentation but was already on record before
this review cycle. Rename to `SVEA-RLViGen` — **not done**.

---

## 8. DrQ

**Claim**: current implementation is better understood as "RL-ViGen DrQ" than a reproduction of
canonical Kostrikov et al. DrQ; no severe Door-specific hyperparameter contradiction found (unlike
SGQN).

**VERIFIED, as a side effect of the same code read used for item 6/7 above.**
`RL-ViGen-upstream/algos/drq.py::DrQAgent` has a genuine `log_alpha`, `self.alpha.detach() *
log_prob` in both actor and critic losses — real SAC, unlike drqv2/svea/curl/sgqn. This makes DrQ
the *one* genuinely SAC-backboned member of the "RL-ViGen five," a fact I used directly to correct
this project's own A25 mechanism-taxonomy entry (see `03-changes-made.md`). I did not separately
check for an RL-ViGen-published Door-specific DrQ hyperparameter table the way I did for SGQN — I
have no positive evidence contradicting the review's "did not find one" claim, but I also did not
independently go looking for one myself.

---

## 9. DrQ-v2

**Claim**: strongest of the RL-ViGen-native group; action_repeat correctly overridden to 1
(matching RL-ViGen's own protocol over the released config's generic 2); the ~620k V100 replay
capacity is smaller than various 1M/10M source numbers but is *effectively* non-evicting for a
600k run, and that is the right frame for the claim rather than "matches the literal integer."

**PARTIALLY VERIFIED, one piece TAKEN ON TRUST.** The `action_repeat=1` override and its
reasoning are independently confirmed by this project's own `rlgen/protocol.py`
(`DEFAULT_ACTION_REPEAT` constant, with a comment tracing the exact same paper-vs-code
contradiction the review implies: "Supplementary Table 2... NOT a robo_config.yaml key... a stock
RL-ViGen robosuite run is off its own table by 2x"). This predates the review and I did not
re-derive it this session, but I did read the comment and confirm it says what I am representing
it as saying. The "~620k, effectively non-evicting" replay-capacity claim: **TAKEN ON TRUST** — I
did not independently verify the 620k figure or redo the non-eviction arithmetic myself this
session; it is consistent with this project's own `CLAIMS-LEDGER.md` entry for drqv2 and with
review 18's identical reasoning (see that file's DrQ-v2 row), but I have not personally checked it
against a running job's actual configuration this session.

---

## 10. RAD

**Claim**: production runs DMCGB's own RAD implementation, genuinely renders 100×100 and crops to
84×84 (older internal notes describing a different, superseded local port no longer apply); the
100→84 vs native-84 comparability gap is real but should not be "fixed" by forcing native 84,
since that would make RAD's own random crop degenerate.

**TAKEN ON TRUST, ENTIRELY.** I did not read `runnable/dmc_gb`'s RAD code, the launcher, or any
config this session to confirm the 100→84 render/crop claim, the "based on the official
implementation" provenance claim, or that "older internal descriptions" are genuinely superseded
rather than still partially accurate. This project's `CLAIMS-LEDGER.md` independently states RAD
uses `random_shift, not the paper's crop/translate; n-step 3 vs 1` — which is not obviously the
same claim as the review's "renders 100, crops to 84" framing, and I did not reconcile the two.
This is one of the more significant gaps in this response — RAD is one of the four baselines this
session did the least independent checking on, precisely because both reviews rate it "already in
reasonably strong shape" and I allocated my attention to the baselines flagged as urgent instead.

---

## 11. SODA

**Claim**: DMCGB's SODA is the official implementation and the source of Places365; production
preserves the right structure (100→84, SAC base, SODA auxiliary objective, Places365 overlay,
EMA/target representation); there is a paper-vs-code ambiguity in the auxiliary LR that should be
made explicit (declare a `SODA-code` and a `SODA-paper` profile, default to code).

**TAKEN ON TRUST, ENTIRELY.** Same situation as RAD: no independent check of DMCGB's SODA source,
the auxiliary-LR ambiguity, or the Places365 overlay mechanics this session. This project's
`CLAIMS-LEDGER.md` independently names `aux lr follows code not paper` and the Places-validation-
split issue (A22, a genuinely separate, already-decided question — see `02-review-18-item-by-
item.md`), which is broadly consistent with the review, but again I did not reconcile the two
myself or verify either against SODA's own source.

---

## 12. ALDA

**Claim**: official ALDA repository's own `specs/` directory documents the shipped Door-adjacent
config values (batch_size=128, num_latents=12, values_per_latent=12, beta=100, frame_stack=3,
64×64) as the paper-result configuration; the project preserves the source update structure
(no artificial UTD compensation for Door's action-repeat difference); ALDA never had a Door
experiment so there's no unique source-backed answer for some task-specific settings; overall
favorable ("official-implementation-preserving Door adaptation").

**PARTIALLY VERIFIED, one real correction made independent of this review.** I did not
re-derive `batch_size`/`num_latents`/`values_per_latent`/`beta`/`frame_stack` against ALDA's own
`specs/` directory myself this session — these values are already present, unchanged, in this
project's own `runnable/alda/specs/train_alda_robosuite_door.yaml`, and I take the review's word
that they match the official repository's own documented defaults. What I *did* independently
find and fix, unprompted by either review: `n_train_steps` was hardcoded at ALDA's own source
value (500,000) while every other baseline in this project targets a common 600,000-frame
production budget — a genuine, previously undiagnosed ambiguity (review 18 separately raises
this exact point, see that file) that I confirmed was real (not a stale doc) via
`scripts/audit_executed_hyperparameters.py`'s own `EXCLUDED_CLAIMS` entry, then changed to 600,000
with both the 500k source-horizon checkpoint and the 600k common-budget endpoint predeclared as
reportable. Also independently confirmed, as a side effect of the SVEA/CURL/DrQ code reads above,
that ALDA's own trainer genuinely has a `log_alpha` (real SAC), consistent with the review's
"preserves the source update structure" framing.

**Confidence**: TAKEN ON TRUST for the specs/-vs-paper match on the five named hyperparameters.
VERIFIED for the 500k/600k budget question, independently resolved (this session's own finding,
not the review's).

---

## Three project-wide issues

### Observation geometry

**Claim**: source-faithful geometry (varying per baseline) should be the primary protocol, with a
separate standardized-observation ablation if identical sensory bandwidth is ever wanted. Names
IDAAC and continuous-control PPG specifically as needing 3-frame stacking now.

**Acted on for IDAAC** (see item 1). **Not acted on for the general "add a standardized-observation
ablation" recommendation** — no such ablation config exists as of this writing. The underlying
project machinery this claim depends on (`rlgen/protocol.py::OBSERVATION_GEOMETRY`, and the tests
pinning it against each launcher) already existed before this review and is exactly the mechanism
I used to make IDAAC's geometry change consistent project-wide (see `03-changes-made.md`) — the
review's framing here matches this project's own pre-existing design, not something it introduced.

### Online evaluation and RNG isolation

**Claim**: RL-ViGen's process-global RNG seeding means online evaluation can silently perturb
future training placements; disabling/isolating it is sound hygiene; the offline common evaluator
should be the primary comparison regardless.

**Already fully implemented before this review**, and confirmed still correctly configured. This
is one of this project's own earlier, pre-review findings (`online_eval_rng_isolated: true` is
already present in every family's `families.json` production block, including idaac's, unchanged
by this session's edits). I did not need to act on this — I only confirmed, while editing idaac's
`families.json` entry for the C2 transition, that this flag was still present and untouched.

### Continuous-action clipping instrumentation

**Claim**: instrument raw-sampled vs. executed/clipped action, fraction clipped, mean distance —
across every Gaussian-policy continuous-action adaptation (PPG, IBAC-SNI, CTRL).

**UPDATE — VERIFIED: this instrumentation already substantially exists.** Read
`scripts/eval_provenance.py::ActionDiagnosticsAccumulator` directly. It tracks, per evaluated
scene: `action_clip_rate_coordinate` (fraction of action *components* clipped — matches the
review's "fraction of action components clipped"), `action_clip_rate_vector` (fraction of
*actions* with at least one clipped component — matches "fraction of transitions with ≥1 clipped
component"), and `action_raw_executed_l1` (an accumulated L1 distance between raw and executed
action, retained as a raw sum alongside `actions_observed`/`coordinates_observed` rather than
pre-divided — consistent with this project's general "report richly, aggregate post-hoc"
convention, not a missing mean). It also honestly declares its own scope limit
(`controller_clipping_observed: False`, `execution_boundary: "declared_action_space_before_
controller"`) — it measures clipping at the declared action-space boundary, not any further
downstream clipping robosuite's own controller might apply to derived torques, exactly the
distinction review 17's own text draws. Confirmed wired into all six of `eval_grid.py`'s
per-family scene-runner functions (`grep -n "_new_action_probe" scripts/eval_grid.py` — six call
sites), not just idaac. **What it does not do**: retain the raw per-step action *values*
themselves (only the aggregate statistics above), so "raw sampled action" and "executed/clipped
action" as literal retained traces — as opposed to derived clip-rate/distance statistics — are not
available post-hoc the way, say, per-episode returns are elsewhere in this project. That is a real,
if narrower, gap than I originally reported this section as being.

---

## "What I would change before final production" (ranked list)

Items 1 (IDAAC) and 2 (SGQN, resolved as "already correctly declared, no change") are covered
above. Item 3 (CTRL) is covered above (disagreed with, in favor of review 18's framing, filed as
`C97`). Item 4 (PPG) is explicitly deferred to Codex. Item 5 (IBAC-SNI) is untouched by me this
session. Item 6 (rename RL-ViGen variants) is **not done**. Item 7 (freeze one executed-config
manifest, "several project documents... have subsequently become stale") — this project already
has extensive machinery for exactly this problem (the whole `docs/CONSTRUCTION.md` register, the
`test_docs_not_stale.py` family of tests, `scripts/audit_executed_hyperparameters.py`), predating
this review; I used and extended that machinery repeatedly this session (see `03-changes-made.md`
for the specific stale-anchor fixes it caught) rather than building the review's proposed
`CURRENT_EXECUTED_CONFIGURATION.md`/`CURRENT_FIDELITY_DELTAS.md`/`historical/` split, which remains
a genuinely different, not-yet-adopted documentation architecture. Item 8 (record action/
observation semantics as contracts) — **partially exists** (`rlgen/protocol.py`'s
`OBSERVATION_GEOMETRY`, the `evaluator_scope` mechanism just fixed in `C98`) but not as a single
consolidated startup-time emission the way the review describes; I did not build this. Item 9
(offline evaluator as primary) — already this project's design, confirmed unchanged. Item 10
(strengthen source provenance with SHA256 chains) — **not done by me**; this project already
records some provenance (`source-lock.json`, mentioned throughout `docs/CONSTRUCTION.md`) but I
did not audit it against this specific recommendation this session.

## Documentation correction ("historical findings survive after supersession")

**Directly experienced, not just read about.** This exact failure mode is what several of this
session's own fixes were: `docs/RUNNABLE-ORIGINALS.md`'s diff-stat figures went stale *twice*
during this session's own edits (PPG, then ALDA, then IDAAC) purely from patch regeneration, each
caught only by `tests/test_docs_not_stale.py` actually running — I did not anticipate any of the
three staleness events before the test caught them. This is strong first-hand evidence for the
review's point, not a claim I am relaying secondhand. The review's proposed *document
restructuring* (`CURRENT_EXECUTED_CONFIGURATION.md` etc.) — not adopted; see item 7 above.

## Sources the review says it did and did not use

Not independently checkable by me — this describes the reviewer's own process, not a claim about
this project. I have no way to confirm or deny what a different reviewing process actually
consulted. Noted here only so its absence from this document isn't read as an oversight.
