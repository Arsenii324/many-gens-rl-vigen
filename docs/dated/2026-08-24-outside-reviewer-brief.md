# Full project brief for an outside reviewer

**Written 2026-08-24. Dated snapshot, not a living document** — it states the project as of that
date and is not maintained. Every claim below is checkable against the cited file; check before
relying on it. Where this brief and a live document disagree, the live document wins and the
disagreement is itself worth reporting back.

---

## 0. How to read this, and what is wanted from you

You are being asked to **find what is wrong with this project**, not to approve it. The brief is
therefore written against the grain of a normal write-up: it is not the best case and not the
easiest case, it is the complete one. Where something is half-finished, contaminated, or
embarrassing, it is here in the body rather than in a footnote — an omitted mess is exactly the
mess you cannot find the error in.

Three reading aids:

- **Every number is tagged** MEASURED (we ran it and the artifact is on disk), INFERRED (derived
  from something measured, with the derivation shown), or ASSUMED (believed, not established).
- **Sample sizes appear next to the number**, not in a footnote. Most numbers here come from
  *one seed* and *one checkpoint*; that is stated inline every time, because the single most
  likely way to misread this project is to treat a one-checkpoint number as a method-level result.
- **Contradictions between our own documents are surfaced, not smoothed.** They are evidence
  about the process, and the process is as much under review as the results.

A caution about this document's own reliability: it was written by the same system that produced
the work. Its standing rule is that *even our own earlier output is argument-shaped until
re-derived*, and while writing this I re-derived the numbers in §3 from the raw artifacts rather
than copying them from prose. Two things came out different from what the prose said; both are
recorded in §3.3 and §7.6.

---

## 1. The question, and who is asking

**Institution.** MIPT Centre for Cognitive Modelling, generalization-in-RL group. The immediate
consumer is a supervisor ("DZ") to whom progress is reported; the eventual consumer is a
comparison table in a paper or report.

**The question.** Twelve visual-RL baselines are run on the same manipulation tasks, and each is
measured on how much of its performance it *keeps* when the visuals change. The intended output is
a ranking, or at least a defensible statement, about which published methods generalize across
visual perturbation in a continuous-control manipulation setting.

**The benchmark.** RL-ViGen (Yuan et al.) is a visual-generalization benchmark spanning several
domains. This project uses only its **robosuite** domain: a simulated Franka Panda arm, MuJoCo
physics, 84×84 RGB observations, operational-space control (`OSC_POSE`). Two tasks:

- **Door** — rotate a handle and open a door. Episode horizon 500 steps, no early termination.
- **Lift** — pick up a block. Same horizon convention.

**Why it matters if it works.** Visual-generalization results in RL are overwhelmingly reported on
Procgen (discrete, 2D, procedurally generated) and DeepMind Control (continuous, but simple
locomotion). Whether the methods that win on those transfer to *manipulation* — contact-rich,
sparse-reward, continuous — is genuinely open. Eight of the twelve baselines here were never
published on a manipulation task at all.

**Why it matters if it fails.** A negative or unidentifiable result is still informative, and §5
argues the current design is closer to that than to a clean ranking.

---

## 2. Vocabulary

Defined here because every one of these is used in a project-specific way.

| Term | Meaning here |
|---|---|
| **Regime** | A visual condition the environment renders in. RL-ViGen defines `train`, `eval-easy`, `eval-medium`, `eval-hard` — increasing perturbation of texture, lighting and colour. A probe found the environment actually implements **six**, adding a `cam-easy`/`cam-hard` camera axis nobody here has measured (`SYSTEM.md`, instrument-audit section). |
| **Scene** | Within a regime, one of ten concrete visual instances (`scene_id` 0–9). Scene 0 is the training scene. |
| **Cell** | One (baseline × task × seed) training run that produced a usable checkpoint, plus the evaluation grid over it. The project's unit of result. |
| **Retention** | The endpoint. `eval-regime performance / train-regime performance` for the *same* checkpoint. Chosen so each method is its own control — see §4.3. |
| **Grid** | An evaluation sweep: 10 scenes × 20 episodes = 200 episodes, at one checkpoint in one regime. |
| **The register** | `docs/CONSTRUCTION.md`, the single authority for what is open/decided/resolved. 63 entries as of today. Entries are cited as C-numbers throughout. |
| **Register classes** | `INHERITED` (came from the original code/paper), `OURS` (we introduced it), `UNDECLARED` (real but written down nowhere), `FALSE-CERTIFICATION` (a check asserts something untrue), `DESIGN-GAP` (blocks results, not code). |
| **Register statuses** | `OPEN` (needs a judgement between alternatives, must carry an Options block), `READY`, `BLOCKED`, `MONITORED` (known, deliberately not acted on), `RESOLVED` (decision + attempt + *effect* recorded, naming its commit). |
| **INTRINSIC taxonomy** | For each thing we authored: is its correctness legible *at the edit*, against the original? `INTRINSIC` (yes), `INTRINSIC by delegation` (a trusted component guarantees it), `INTRINSIC by corroboration` (two independent sources agree), `NOT INTRINSIC` (a debt, whether or not a test passes), `CONSEQUENCE` (forced by an earlier choice). The NOT-INTRINSIC rows are the point of `docs/INTEGRATION-DELTA.md`. |
| **The null** | The original repository, cloned, running its own `train.py`. Not a reimplementation. |

---

## 3. What has actually been measured

This is the section to read first if you read only one.

### 3.1 The complete measurement inventory

Every evaluation grid that exists on disk, re-derived for this brief directly from
`results/regime-retention/*.json` rather than copied from any document. All MEASURED. All are
**Door**. All are 10 scenes × 20 episodes = **200 episodes** per cell. All are **single-seed**.

| artifact | regime | checkpoint | pooled return | successes |
|---|---|---|---|---|
| `random-floor__train` | train | untrained | **1.82** | 0/200 |
| `random-floor__eval-easy` | eval-easy | untrained | **1.85** | 0/200 |
| `cell55k__train` | train | drqv2 s6, 50k | 115.31 | **59/200** |
| `cell55k__eval-easy` | eval-easy | drqv2 s6, 50k | 3.49 | 0/200 |
| `cell_drqv2_s7__train` | train | drqv2 s7, 50k | 85.01 | 0/200 |
| `cell_drqv2_s7__eval-easy` | eval-easy | drqv2 s7, 50k | 15.00 | 1/200 |
| `cell_svea_s1__train` | train | svea s1, 50k | 97.50 | 6/200 |
| `cell_svea_s1__eval-easy` | eval-easy | svea s1, 50k | 85.51 | 3/200 |
| `cell_drq_s1__train` | train | drq s1, 50k | 79.29 | 0/200 |
| `cell_drq_s1__eval-easy` | eval-easy | drq s1, 50k | 22.18 | 1/200 |
| `snapshot_50k_frames__train` | train | archived drqv2, 50k | 24.75 | 1/200 |
| `snapshot_50k_frames__eval-easy` | eval-easy | archived drqv2, 50k | 46.71 | 4/200 |
| `snapshot_100k_frames__train` | train | archived drqv2, 100k | 52.16 | 28/200 |
| `snapshot_100k_frames__eval-easy` | eval-easy | archived drqv2, 100k | 131.05 | 63/200 |
| `snapshot__train` | train | archived drqv2, 100k | 51.94 | 19/200 |
| `snapshot__eval-easy` | eval-easy | archived drqv2, 100k | 144.72 | 62/200 |

**That is the entire empirical basis of this project.** Sixteen grids, one task, four distinct
trained runs plus one archived contaminated run, no seed replication of any cell, no Lift.

### 3.2 The one retention number that exists

Exactly one cell yields a retention figure: **drqv2 seed 6 at 50k frames, retention 0.003**
(95% CI [0.003, 0.004]). MEASURED.

Three things must be attached to it, and the instrument itself prints all three:

1. **It is computed over 4 of the 10 scenes**, not ten. Six were refused — two as at-chance, four
   as "above chance but never successful". The tool's own output says: *"pooled over the 4 usable
   scenes only — NOT RL-ViGen's protocol, which averages all ten. Dropping scenes changes the
   estimand; the number above answers 'on scenes where the agent had learned something'."*
   Verified by recomputation: the four qualifying scenes give
   (0.86+0.71+0.92+0.91)/(424.52+147.04+391.20+126.30) = **0.00312**.
2. **The naive pooled ratio is 0.030, ten times larger** (3.49/115.31), because it includes dead
   scenes in both numerator and denominator. Both numbers are defensible; they answer different
   questions. A reviewer should decide whether the selected-scene estimand is the right one — we
   think it is, but it is a selection step applied after seeing the data, which is exactly the
   shape of a garden-of-forking-paths problem.
3. **Success-rate retention does not exist for this checkpoint.** Train SR is 0/200 on the
   qualifying construction; the tool prints `SR retention undefined` rather than 0.

### 3.3 An observation made while writing this brief

Not previously recorded anywhere, offered as a finding rather than an established result.

The sixteen grids split cleanly into two families by the **sign** of the train→eval change:

- **The four freshly-trained cells** (drqv2 s6, drqv2 s7, svea s1, drq s1) all show
  `eval-easy < train`: 3.49<115.31, 15.00<85.01, 85.51<97.50, 22.18<79.29. Normal direction.
- **All three archived-checkpoint grids** show `eval-easy > train`: 46.71>24.75, 131.05>52.16,
  144.72>51.94 — the last two by a factor of ~2.5–2.8.

The archived run is the one C54 (§5.1) independently concludes was not trained on the distribution
its config declares. The sign of the regime gap separates the contaminated run from the clean ones
perfectly, across three checkpoints, with no exceptions. INFERRED, and it is a cheap corroboration
of C54 from a direction C54 did not use. It also suggests a **general screen**: retention above 1
should be treated as a contamination alarm rather than as a result, in any future cell.

### 3.4 What is emphatically not measured

- **Lift: never run.** Every finding in this project is Door-only.
- **`eval-medium` and `eval-hard`: never run.** All retention numbers are `train`→`eval-easy`,
  the mildest perturbation.
- **`cam-easy`/`cam-hard`: never run**, and were not known to exist until an instrument audit found
  the environment implements six regimes rather than four.
- **Seed replication: none.** No cell has been run at two seeds. The two drqv2 seeds (6 and 7) are
  different runs, not a replication — s6 solves 59/200 and s7 solves 0/200 at the same budget,
  which is itself the most alarming single fact in §5.2.
- **Eight of twelve baselines have produced no measured cell.** Directories exist under
  `results/cell-*` for ctrl, curl, ppg, rad, sgqn and others, but they contain only watcher frames
  and logs — zero result artifacts. Verified: `find results/cell-* -name '*.csv' -o -name '*.pt'
  -o -name '*.json'` returns nothing.

---

## 4. The design, and why each choice

### 4.1 Hermetic clones, not a framework

Each baseline lives as its own clone of the original authors' repository, running the original
`train.py`. No shared base classes, no shared runner, no adapter layer. The governing rule, from
`docs/porting-directive.md` §1, is:

> *Duplication is cheaper than a wrong abstraction.* — and its operational form: **duplication is
> free; any join carries burden of proof.**

**Why.** The failure mode this is built against is a shared component silently changing an
algorithm's numbers. That is not hypothetical: the library survey found TorchRL's issue tracker
documents ~20 such cases (`docs/library-survey/CONTEXT.md`). If twelve baselines share a replay
buffer and it subtly differs from one method's original, that method's published behaviour is
gone and nothing reports it.

**What it costs.** Twelve copies of nearly everything, and no ability to state "the only difference
between A and B is the algorithm" — because it isn't. See §4.4.

**A reviewer should challenge this.** It is the project's founding commitment and everything else
follows from it. The strongest counter-argument is that fidelity to twelve different original
codebases makes the twelve mutually incomparable, which §4.4 concedes is largely true.

### 4.2 The null is the original repo running its own `train.py`

Not a reimplementation, not a port. There *was* a port (under `rlgen/`); it is superseded, and much
of the test suite still points at it rather than at the twelve clones that produce reported
numbers — `SYSTEM.md` flags this as an instrument-aimed-at-the-wrong-artifact problem and declines
to state the exact share, on the grounds that any session that works on it invalidates the figure.

### 4.3 Retention as the endpoint

Retention divides each checkpoint by *itself* in a different regime. **Why:** it makes each method
its own control, so the seven-way confound in §4.4 cancels to first order — a method's frame stack,
learning rate and discount affect numerator and denominator alike.

**Where that breaks, stated in `RESEARCH-FRAME.md` before it was measured:** the confounds do not
cancel to *second* order. A confound can interact with the regime shift — a single-frame method may
degrade under visual perturbation differently from a three-frame one *for reasons about frames, not
about the algorithm*, and frame count is one of the confounds. So a retention ranking is evidence
about **published methods as shipped**, never about algorithmic ideas.

And the ratio has a denominator problem, predicted in advance and then confirmed: if train-regime
performance is near the random floor, the ratio is a ratio of noise that *looks* like a number. The
guard is `scripts/regime_retention_report.py`, which refuses to divide unless the denominator both
clears the measured floor and solves ≥25% of episodes, printing `AT-CHANCE`,
`UNSOLVED-DENOM` or `WEAK-DENOM(n/m)` instead. That guard's history is in §6.3 and is not
flattering.

### 4.4 The identification problem, which is the design's central weakness

From `docs/RESEARCH-FRAME.md`, and stated by the project itself rather than extracted by review:

> **Method identity is perfectly collinear with its entire configuration.** Not approximately — *by
> construction*, r = 1. Choosing `ppg` chooses a single frame, γ=0.999, lr 5e-4, an unsquashed
> Gaussian, 64×64 input, reward normalisation, and truncation-as-termination, all at once, with no
> independent variation anywhere in the design.

| Method group | frames | truncation | γ | lr | action dist. | render |
|---|---|---|---|---|---|---|
| `rad`, `soda` | 3 | **bootstraps** | 0.99 | 1e-3 | SAC squashed | 100→84 |
| `alda` | 3 | **bootstraps** | 0.99 | — | SAC squashed | 64 |
| `drqv2 svea sgqn curl drq` | 3 | zeroes | 0.99 | 1e-4 | DrQv2 trunc. | 84 |
| `ppg`, `idaac`, `ctrl` | **1** | zeroes | **0.999** | 5e-4 | unsquashed + clip | 64 |
| `ibac_sni` | **1** | zeroes | 0.99 | 7e-4 | unsquashed + clip | 64 |

The project's own conclusion, which we believe is correct and want challenged anyway:

> **No observed difference between two methods can be attributed to the algorithm**, because the
> algorithm never varies independently of seven other things. This is the standard
> unidentifiability of collinear predictors, and the honest statement is *"this design cannot
> separate them"* — not a smaller p-value.

What the design **can** support: within-method, across-regime comparison. That is a genuine
controlled contrast and it is the generalization question. What it cannot support: any per-method
ranking read as a claim about an algorithmic idea.

---

## 5. The things that would most embarrass us

### 5.1 The only trained checkpoints we had were not trained on the distribution their config declares

Register entry **C54**, class FALSE-CERTIFICATION, status OPEN. This is the worst one.

The archived `drqv2` run's config says `mode: train`, `scene_id: 0`, no randomisation. Evaluating
that checkpoint on exactly that condition gives **chance performance** — 1.30 return, 0.00 success —
while its own logged eval reported 436 with SR 1.00. The failure is specific to that one condition:
the same checkpoint is well above chance on other `train`-mode scenes (up to 80.67).

**The pixel evidence settles what it actually trained on.** The run stored one training episode.
Comparing its reset frame against freshly rendered frames across all twenty regime×scene
combinations: `eval-easy`/scene 0 matches at mean-abs-difference **7.60** (correlation 0.942),
while `train`/scene 0 — *the declared condition* — is at **39.92**, nearly the worst of the twenty.

**No mechanism has been found.** C54 lists what was ruled out: the launch command carries no `mode`
override; `train.py` never reassigns `train_env`; the config file predates the run by eleven days;
rendering is not working-directory dependent; and a 5000-frame reproduction did **not** reproduce
it. The honest status is a known-live, unexplained failure in a pipeline all twelve baselines share.

**Why it is worse than it looks.** Two register entries (C46, C47) rest on those checkpoints, and
several published-comparison claims chain off them.

### 5.2 The measurable window is narrower than the finite window

This is the project's binding constraint, measured on both sides.

- **Below ~50k frames**, most baselines have not learned enough for retention to be defined — the
  denominator fails the floor-and-success guard, and the answer is "no number", not "a small
  number".
- **Both 120k-frame runs diverged to NaN.**

So the band that yields a *measurable* cell is narrower than the band that yields a *finite*
checkpoint, and the project is operating inside it. This is a structural problem, not a tuning
problem, and it is the single biggest threat to ever producing a twelve-row table.

**And within that band, run-to-run variance swamps everything.** drqv2 seed 6 solves 59/200 at 50k;
drqv2 seed 7 solves **0/200** at the same budget with the same code. A separate probe put
run-to-run variation at ~49% by 40k frames (C41). With one seed per cell, the current design cannot
distinguish a method from a seed.

### 5.3 Three of four cells show learning that is not learning

At 50k on Door, three of four runs reach a stable return of 79–115 against a floor of 1.82 — and
open the door **zero times**. Door's reward is `if/elif`: success pays exactly 1.0 with no shaping;
otherwise up to 0.25/step for gripper proximity plus 0.25/step for door rotation. Over 500 steps
the shaping alone can pay **250** without the door ever opening (C62).

A policy that optimises shaping and never solves the task sits exactly there, *stably*, so its
return curve looks healthy. **Return is not evidence of learning on this task**; only the success
count separates the two, and that costs an evaluation grid.

This also re-reads the published numbers: RL-ViGen publish DrQ-v2 on Door Easy at **3.6**, which is
**1.4% of the shaping ceiling** — not a weakly-trained agent but one whose gripper is essentially
never near the handle (C37).

### 5.4 Nothing has ever reproduced a published RL-ViGen number

Register entry **C48**, class DESIGN-GAP, status OPEN. Every external comparison runs one direction:
we read their table and compare our numbers to it. **Nothing has run their evaluation path on a
policy and landed on one of their cells.** So the comparison rests on an assumed protocol
equivalence that has never been closed experimentally.

### 5.5 Lift has never been run, and eight of twelve baselines have no cell

Stated in §3.4 and repeated here because it is easy to lose: the "twelve-baseline comparison" has
measured results for four baselines on one task at one seed each.

### 5.6 Twelve baselines run at `action_repeat=1` for three different reasons

An audit found all twelve agree with the paper's Table 2 — but five get it explicitly from a
launcher, two from a different launcher, one (`alda`) carries specs saying 1, 2 **and** 4 with the
key *never read* on the robosuite path, and four (`idaac`, `ctrl`, `ibac_sni`, `ppg`) have **no
action-repeat mechanism at all**. They agree, but *only seven of twelve agree by anyone's decision*.
Recorded in `docs/INTEGRATION-DELTA.md`. This is the shape of a whole class of latent problems: an
invariant that currently holds by coincidence and would break silently.

### 5.7 The time-limit split, which biases nine baselines against three

**C1**, OPEN. Door and Lift have no early termination, so every episode ends by time limit. Three
baselines (`rad`, `soda`, `alda`) treat that as truncation and bootstrap through it; **nine treat it
as a terminal state and zero the bootstrap, on every episode throughout training.** Nine baselines'
value targets are biased downward relative to three.

The split is lineage, not accident: the three correct ones descend from Yarats' dmcontrol code; the
Procgen-native ones are wrong *here* only because the environment changed underneath them — in
Procgen every episode genuinely is a termination, so their authors were right for Procgen.

It is also a false certification: `rlgen/protocol.py` declared
`time_limit_handling = "truncate_with_bootstrap"` **inside `Protocol.hash()`**, a string true of
three baselines out of twelve.

---

## 6. Unknown knowns — things the project knows but has not acted on

### 6.1 Every defect found sits at a *join*, and every instrument checks an *artifact*

The project's own most important self-observation (`SYSTEM.md`). Not one defect it has found was a
wrong measurement. C54 is config ↔ what the env rendered. C55 is a measured floor ↔ the instrument
that needed it. C43/C45 is a protocol's certification ↔ the actual eval loop. C23 is "RESOLVED" ↔
"defect removed". C57 is "training ran" ↔ "a policy exists". **In each case both sides were
individually correct.**

The founding rule — *duplication is free; any join carries burden of proof* — was applied with real
discipline to **code** joins and never to **epistemic** ones. Hundreds of tests and 63 register
entries all point at artifacts: a file, a field, a number. **Nothing points at a seam.** The project
states it does not know whether that is fixable by a check or only by a habit.

*This is the single most useful thing a reviewer could push on.*

### 6.2 A whole class of divergence has no home in the document system

Divergences are filed by what licenses them: adaptations forced by the target go to
`INTEGRATION-DELTA.md`; deliberate divergences go to `FAITHFULNESS.md`; measurement defects go to
`CONSTRUCTION.md`. The fourth kind — **a handicap that was recorded but not removed** — has **no
home**, and the gap is structural rather than an oversight: a handicap leaves no trace in code, so
it produces no diff for a deviation-counter to find and no authored line for an
"is this ours?" rule to admit. A *non*-change is correctly attributed to the original authors.

Current members, all recorded somewhere and collected nowhere: the entropy coefficient (C61),
`ibac_sni`'s 227× model (C3), render resolution 100→84/84/64 (C5), IDAAC's referent-less instance
labels (C50), the 3/9 truncation split (C1), and same-named metrics meaning different things.

They are findable by **date** and invisible by **algorithm** — so a reader of `idaac`'s
FAITHFULNESS section currently learns nothing about its instance-invariance loss being inert here.

### 6.3 Instruments are not trustworthy on their first run, and this is documented in detail

The project has caught six defects in its own checkers, three written the same session. The pattern
it extracted: **not one was found by writing the instrument more carefully; every one was found by
running it and disbelieving a result.**

Two that bear directly on results in §3:

- The **citation resolver** ran, passed, and reported 0 defects across 677 citations while its
  predicate — "is the line number ≤ the file length" — could not fail for any realistic input.
- The **retention floor guard** — the thing standing between this project and a fabricated headline
  — got it wrong **twice**. First it keyed the guard to the returns' own spread (a chance-level
  denominator with tight spread passed). Then it keyed it to significance (20 episodes can separate
  2.02 from 1.82). The third version added a measured floor plus a ≥25% success requirement, after
  svea's 1/20 slipped through and produced a 0.947 retention headline.

The standing rule: *a green instrument is evidence only if something is known to make it red.*

### 6.4 A session that measures this system invalidates its own measurement by continuing to work

Recorded after three figures written one night were stale by morning — the document line count, the
register total, and the test counts — each invalidated by later work *in the same session that
wrote it*. The fix adopted: a count about this repository belongs in a command, not in prose.

Today this recurred: `PROJECT-INDEX.md` described the register as "26 items" (a port-era figure)
while it held 63.

### 6.5 The document set is growing faster than it is read

~23,000 lines of project markdown as of today against **602 code lines** of actual porting
deviation — roughly 29 lines written about the work per line of it. The system flags this as its
most likely failure mode: not a wrong document, but a set too large for the next session to reach
the right one. The bullet warning about growth has itself been updated three times by sessions it
was written to restrain.

---

## 7. Unknown unknowns — where we would look if we were you

**This section is speculation and is labelled as such.** It is our honest guess at blind spots, not
a list of known problems. It is included because a hostile expert will look here anyway.

### 7.1 The evaluation protocol may not match RL-ViGen's, and nothing would catch it

C48 says no published number has ever been reproduced. That means the *entire* external comparison
rests on protocol equivalence being assumed. If their `eval-easy` samples scenes differently,
averages differently, or uses a different episode count, every "ours vs theirs" statement in this
project is comparing different quantities — and §3.2 already shows the estimand is sensitive to
scene selection at the factor-of-ten level. **This is where we would attack first.**

### 7.2 The environment may not be deterministic in the way everything assumes

Every grid uses fixed episode seeds and a fixed control seed. If MuJoCo's contact solver or the
renderer carries state across `env.reset()` — and C54's unexplained mechanism is *consistent* with
some form of cross-episode state leakage — then "same seed, same scene" may not mean "same
episode". The project has a training-distribution witness for the *training* side and nothing
equivalent for the *evaluation* side.

### 7.3 The shaping ceiling may not be 250

C62's derivation assumes the two shaping terms are each bounded by 0.25/step and are additive over
500 steps. If either term can exceed its assumed bound, or if success and shaping can co-occur in a
step, the ceiling moves and the "return is not learning" reading in §5.3 weakens. The ceiling was
derived from reading the reward function, not measured by rolling out a shaping-maximising policy.

### 7.4 Success may be defined differently in three places

"Success" appears in the environment's `_check_success`, in our grid's `n_success` counter, and in
RL-ViGen's published SR. Whether all three mean "the door was open at any point" versus "at episode
end" has not, to our knowledge, been checked end to end. Given §5.3, this distinction is
load-bearing.

### 7.5 Single-seed variance may be larger than the effect being measured

Stated as a known in §5.2, listed again here because the *implication* may be unknown: if
seed-to-seed variation is ~49%, and retention differences between methods are smaller than that,
then the twelve-row table cannot be produced at any seed count this project can afford. Nobody has
computed what seed count would be needed. That calculation is cheap and has not been done.

### 7.6 Numbers in prose may have drifted from their artifacts more widely than the two found

Re-deriving §3 from raw JSON caught one stale index figure and required resolving an apparent
inconsistency in a headline number (§3.2 — it turned out correct, but only after recomputation).
Two checks, two surprises. That rate suggests more.

---

## 8. The methodology as an object of review

The practices are as reviewable as the results, and the project would rather have them attacked
than praised.

**The register.** Every finding gets an entry when *noticed*, before it is repaired or even
understood — because repairing first and recording after loses why it was found. Each carries a
class, a status, and a blast radius. A `RESOLVED` entry must record the *effect*, including "we did
it and nothing changed", and must name its commit. Structure is enforced by
`tests/test_construction_register.py`, which today rejected a new entry three times: for missing a
summary row, for a count line that disagreed with the table, and for being `OPEN` without an
Options block.

**The §4 four-field format.** Every decision records: the structural property of the original that
the mechanism depends on; the options considered; the choice; and **the result that would show the
choice wrong.** The fourth field is what stops a decision fossilising into an assumption.

**Falsifier discipline, and an honest note on it.** Entries state in advance what would refute them.
This works — one entry today stated a falsifier, the falsifier was run the same day, and it
confirmed rather than refuted, which is reported as such. But note the selection effect a reviewer
should press on: **falsifiers that are cheap to run get run.** There is no accounting of how many
stated falsifiers have never been executed, and the honest answer is that most have not.

**Pre-registration.** At least one measurement was pre-registered with three named readings written
before it ran, precisely so the interpretation could not be chosen after seeing the number. That is
good practice and there is exactly one instance of it.

**Where the discipline demonstrably slipped**, recorded because it is evidence:
- A finding was committed twice — the entry about testing against an unreal directory layout was
  written, and then the same mistake was made again in the same session.
- An overclaim ("the floor was never measured") was written into an entry when a prior entry had
  measured it eight days earlier.
- A claim that "our own launcher forces `action_repeat=1`" implied a shared launcher that does not
  exist; the twelve-baseline audit in §5.6 was the correction.
- A failure mode was rediscovered for the **fourth** time despite being documented verbatim in the
  register, with a workaround already in the code.

That last one is the most damning single fact about the document system: it is large enough that
its own contents get rediscovered rather than recalled.

---

## 9. Constraints that shaped the work

These are real and they explain choices that would otherwise look lazy.

- **Hardware: Apple M2 Pro, MPS, no CUDA, ever.** Conv-heavy work is ~60× faster on MPS than CPU,
  but anything needing millions of env steps, JAX-CUDA, or Procgen is necessarily a remote job.
- **Concurrency cap of two.** Wired GPU memory (not RSS) drives swap on this machine; more than two
  concurrent MuJoCo/Metal runs pushes it into swap. Swap hit 90% with 54M swapouts once before it
  was noticed.
- **Remote compute ceiling: T4.** Yandex DataSphere `gt4.1`/`gt4i.1` only; V100 and above are out
  of budget. A run did land on a V100 once against this ceiling, because a config comment said
  "one T4"; corrected.
- **Kaggle: ~3.9 GPU-hours remain this period, resetting 2026-08-29** (MEASURED today: 94,030s used
  of 108,000s allowed; the stock `kaggle quota` CLI cannot report this due to a parsing bug in the
  SDK's duration deserializer, so it was read via the API directly).
- **Kaggle's train regime works; its eval regimes are blocked.** A T4 kernel trained RAD end-to-end
  with real robosuite envs, so headless GL/EGL rendering is not the blocker. The blocker is narrow
  and version-specific: RL-ViGen's eval regimes need mujoco 2.x for `MjModel.tex_rgb` (removed in
  mujoco 3.0), mujoco 2.x has no Python-3.12 wheel, and Kaggle runs Python 3.12.
- **Everything uploaded is private by default.** Unpublished lab work.

---

## 10. What we most want challenged

Real questions, in the order we would most like them answered.

1. **Is the retention estimand defensible?** We drop scenes whose denominator fails a floor-and-
   success guard, which changes the estimand from RL-ViGen's ten-scene average and moves the
   headline by 10×. Is selecting scenes post hoc on a denominator criterion sound, or is the honest
   move to report the ten-scene number with its instability stated? Is there a standard estimator
   for "retention where the denominator is sometimes at chance" that we should be using instead?

2. **Given §4.4's perfect collinearity, is there any version of this study worth finishing?** We
   believe within-method across-regime is identified and cross-method is not. Is that too
   pessimistic — is there a design change (varying one confound within one method, say frame stack
   in drqv2) that would buy real identification for a cost proportional to one baseline rather than
   twelve?

3. **How would you find defects that live at a join?** §6.1 is our central methodological gap: every
   instrument checks an artifact, every real defect was a mismatch between two individually-correct
   artifacts. Is there a known technique for this, or is it irreducibly a habit rather than a check?

4. **What seed count would this need?** With ~49% run-to-run variation at 40k frames and one seed
   per cell, is a twelve-row retention table achievable at any budget we could plausibly get? We
   have not done this calculation and suspect the answer may be "no", which would be a decision-
   grade finding.

5. **Is C54 (§5.1) recoverable, or should those checkpoints be discarded outright?** No mechanism
   was found, a reproduction attempt failed to reproduce it, and two register entries depend on the
   affected checkpoints. Does the §3.3 sign-of-the-gap observation constitute sufficient grounds to
   quarantine them, or is there a diagnostic we have not thought of?

6. **Is "return is not learning" (§5.3) being applied consistently?** Given the shaping ceiling, we
   now distrust every return-based statement in the project. Should the endpoint move to success
   rate outright, accepting that SR retention is undefined for most current cells — i.e. accepting
   "no number" over "a misleading number"?

7. **Is the document system a net positive?** 29 lines written per line of code changed, a
   four-times-rediscovered finding, and growth flagged by the system as its own most likely failure
   mode. From outside, does this read as rigour or as displacement activity? We genuinely do not
   know, and from inside a session those are indistinguishable.
