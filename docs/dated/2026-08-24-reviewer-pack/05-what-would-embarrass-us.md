# The things we would least like you to find

**Written 2026-08-24. Dated snapshot, not a living document.**

Stated first, in rough order of how much they threaten the work. Nothing here is hedged; where we
have a defence it is given, and where we do not, that is said.

## 1. The same checkpoint evaluated twice disagrees by 47%

**MEASURED, 2026-08-24, and not previously known to the project.** `snapshot.pt` and
`snapshot_100k_frames.pt` are byte-identical (md5 `ec21f9a30da07ca94d0511cc85be5baf`). Both were
evaluated at `seed: 0`, 20 episodes/scene, 10 scenes, identical recorded protocol. Results:
**19/200 vs 28/200 successes** in the training regime; 144.72 vs 131.05 pooled return on
`eval-easy`; scene 4 alone gives 9 vs 16 successes.

**Why it is the worst item here.** It bounds the resolution of every comparison in the project, and
it was invisible: the two grids sat in the results directory under different names, and nothing
noticed they were a replicate. The recorded metadata is *insufficient to distinguish a replicate
from a new measurement*, which means the project cannot currently tell how many of its other numbers
are separated by more than noise.

**Defence:** none yet. It is one replicate pair, so the magnitude is itself n=1 and should be
repeated before being quoted as a resolution limit. But "we have not measured our noise" and "our
one accidental noise measurement is large" are both bad positions.

## 2. The only trained checkpoints we had were not trained on the distribution their config declares

**C54, OPEN, no mechanism found.** Per-pixel comparison of the archived run's own stored training
frame against freshly rendered frames across all twenty regime×scene combinations puts
**`eval-easy`/scene 0 nearest (7.60)** and the **declared `train`/scene 0 nearly furthest (39.92)**.
Behaviourally, the 100k checkpoint scores 1.30 (SR 0.00) on `train`/scene 0 — chance, against a
measured floor of 1.82 — and 420.02 (SR 0.80) on `eval-easy`/scene 0.

What has been ruled out, each checked: the launch command carries no `mode` override and `env_set`
is empty; `train.py` assigns `train_env` once and never reassigns; `eval()` never writes to replay
storage; the config's mtime predates the run by eleven days; rendering is not
working-directory-dependent; and a 5000-frame reproduction did **not** reproduce it.

**The remaining hypothesis is run length**, because `replay_buffer.py:117` unlinks each episode file
as soon as the loader consumes it, so a run's buffer holds only its ending and cannot testify about
its middle. That is why the witness tooling (`watch_training_frames.py`) exists at all.

**Two register entries depend on those checkpoints.** C65 (the contamination screen) and C63 both
lean on them, though C65 is corroboration *of* C54 rather than a dependant.

## 3. Perfect collinearity: no difference is attributable to the algorithm

**r = 1** between method identity and seven configuration choices — learning rate, replay capacity,
augmentation, n-step, network sizes, rollout length, backbone lineage. Recorded in
`../../RESEARCH-FRAME.md`.

This is a *design property*, not a defect that crept in: each baseline is faithful to its own origin,
which is the whole point of the hermetic clone stance. But it means the study cannot make a causal
claim about mechanisms, and a reviewer is entitled to ask why it is being finished. See
[09](09-open-questions.md) Q2, where we ask that back.

## 4. n = 1 everywhere, against run-to-run variation we have already seen swamp the effects

`drqv2` seed 6 solves **59/200**. Seed 7 solves **0/200**. Same code, same 50k budget, same task.
C41 independently puts run-to-run variation near **49% by 40k frames**.

Every cell in the project is a single seed. **Nobody has computed what seed count this design would
need to resolve the effects it reports.** That calculation is cheap, obvious, and has not been done
— which is itself a finding about the process, not just about the statistics.

## 5. Return is not learning, and we believed otherwise for a while

At 50k frames on Door, **three of four runs reach a stable return of 79–115 while never opening the
door.** The mechanism is the reward's `if/elif` structure: shaping alone can pay up to **250** over
the horizon (C62). A shaping-optimising policy sits exactly in that band, stably, so its curve looks
healthy.

This retroactively distrusts every return-based statement made in this project before the success
counts existed. We do not have a clean audit of which statements those were.

## 6. Nothing has ever reproduced a published RL-ViGen number

**C48.** Zero published numbers reproduced, so **the entire external comparison rests on an assumed
protocol equivalence that has never been checked.** And [03](03-what-was-measured.md) §3 shows the
estimand moves **10×** (0.003 vs 0.030) depending on scene selection — so "our protocol matches
theirs" is not a small assumption, it is the load-bearing one.

Compounding it: their published `DrQ-v2` on Door Easy is **3.6**, which is **1.4% of the shaping
ceiling** — i.e. an agent that essentially never approached the handle. Our `drqv2` reads 3.49 at
50k (on their number) and 131.05 by 100k, at one twelfth of their budget. **We cannot explain why
their runs stayed at the floor with 12× more compute**, and until we can, either that number or ours
is measuring something we do not understand.

## 7. Lift has never been run, and nine of twelve baselines have no cell

Every finding in this pack is **Door-only**, and Door's specific reward structure drives item 5. Nine
baselines — `alda`, `ctrl`, `curl`, `ibac_sni`, `idaac`, `ppg`, `rad`, `sgqn`, `soda` — have no
retention grid at all. The intended deliverable is a twelve-row table; three rows have evidence.

Our own documents got this wrong too, saying "eight of twelve" — see
[04](04-the-twelve-baselines.md).

## 8. A document certifies a fix that cannot reach a run

**C64, found 2026-08-24.** `FAITHFULNESS.md` records SGQN's catastrophic `aux_lr = 0.3` (1000× off,
on the shared encoder) as "**FIXED 2026-08-10**". The fix is real and sits at `configs/vigen.yaml:82`
— which configures the **`rlgen/` port retired on 2026-08-17**. The clone runs upstream's hydra
config and uses **1e-4 / 0.93**.

Operationally this is benign — SGQN is not running at 0.3. Epistemically it is not: the document a
reader is routed to *"before quoting any baseline's result as that method's result"* states a
configuration that no run uses. Every individual sentence in it is true of the system it was written
about. **This is the project's signature failure shape and we keep producing it** — see
[06](06-unknown-knowns.md) §1.

## 9. Three baselines are partly our own invention, with nothing to check them against

`ppg`, `ibac_sni`, and `ctrl` needed continuous-action heads that do not exist in any reference. A
survey of fifteen RL libraries found no prior art — the PPG upstream's only Gaussian is unreachable
dead code at fixed σ=1. `ctrl` additionally **omits `L_clust` entirely** and draws positives from the
wrong partition, which makes it a different algorithm rather than a differently-tuned one.

For a quarter of the comparison, "the method's result" is partly "our construction's result", and
nothing external can adjudicate.
