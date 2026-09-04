# Vocabulary

**Written 2026-08-24. Dated snapshot, not a living document.**

Assumes no familiarity with RL-ViGen, robosuite, or this project. Terms are defined in the sense
this project uses them, which is not always the field's sense — where it differs, that is flagged,
because those are exactly the places a reader silently substitutes their own definition.

## The environment

**robosuite** — a MuJoCo-based robot manipulation simulator. Here: a Panda 7-DoF arm, OSC_POSE
control, 84×84 RGB pixel observations, 500-step episode horizon, `action_repeat = 1`.

**RL-ViGen** — a benchmark for *visual generalization* in RL, wrapping robosuite (and other
domains) with a set of visual **regimes** and publishing baseline numbers for twelve methods. The
project's null is this repository, cloned and run through its own `train.py`.

**Door** — the task all measurements here use. The arm must grasp a handle and rotate it. Its reward
is an `if/elif`, and the structure matters more than it looks:

- **success** pays exactly **1.0** for that step, with **no** shaping added;
- **otherwise**, up to **0.25/step** for gripper-to-handle proximity plus **0.25/step** for door
  rotation.

Over a 500-step horizon, **shaping alone can therefore pay up to 250 without the door ever
opening.** This single fact drives the central result in [03](03-what-was-measured.md).

**Lift** — the second intended task. **Never run.** Every finding here is Door-only.

## The axes

**Regime** — a visual condition. `train` fixes textures and lighting; `eval-easy` randomises them;
`eval-hard` randomises harder. There is also a camera axis (`cam-easy`, `cam-hard`). **Only `train`
and `eval-easy` have ever been measured in this project.**

**Scene** — one of ten concrete instantiations within a regime (`scene_id` 0–9). Scene 0 is the
training scene. Note that *scene* and *regime* are separate axes and the project measures both;
conflating them is a live source of confusion, and one register entry (C46) exists because the two
were compared as though they were the same axis.

**Cell** — one baseline × one task × one seed, evaluated across all ten scenes in both regimes:
20 episodes per scene per regime, so **200 episodes per regime, 400 per cell.** A cell is the unit
that yields a retention number.

> **Careful:** the directories named `results/cell-*` are **not** cells in this sense. They contain
> only `watcher.log` and captured `frames/*.npy` — training-distribution witness data. The actual
> cells live in `results/regime-retention/*.json`. This naming has already misled the project's own
> documents about how many baselines have been measured.

## The endpoint

**Retention** — held-out-regime performance divided by training-regime performance, for one method:

```
retention = mean_return(eval-easy) / mean_return(train)
```

Reported per method, so each method is its own control. Read [01](01-question-and-design.md) §3–4
for why the endpoint is a ratio.

**Success rate retention** — the same ratio computed on success counts rather than returns. **These
two are reported separately and never averaged.** They share a name and a lineage; that is not
evidence they are the same quantity, and on this task they diverge sharply (see the replicate in
[03](03-what-was-measured.md) §2, where pooled means agree to 0.4% while success counts disagree by
47%).

**Random floor** — the return a uniform random policy achieves, measured rather than assumed: **1.82
in `train`, 1.85 in `eval-easy`, 0 successes in 400 episodes.** Any denominator that does not clear
this is refused, because a ratio of two chance-level numbers carries no information about retention.

**Shaping plateau** — a stable return in roughly the 79–115 band produced by optimising shaping while
never solving the task. It looks like successful learning on a return curve. Only the success count
distinguishes it.

## The findings register

`../../CONSTRUCTION.md` is the single authority for what is open, decided, or resolved. Entries are
cited as **C*n***. Each carries a **class**:

| class | means |
|---|---|
| **INHERITED** | a property of upstream's code or the benchmark, not ours |
| **OURS** | something this project did, decided, or got wrong |
| **UNDECLARED** | a divergence that existed without being written down |
| **FALSE-CERTIFICATION** | a document asserts something is verified when it is not — C64 is a live example |
| **DESIGN-GAP** | a structural hole that blocks results rather than code |

and a **status**: `OPEN` (needs a judgement between stated alternatives), `READY`, `BLOCKED`,
`MONITORED` (known, deliberately not acted on), `RESOLVED` (decision, attempt, **and effect** all
recorded, naming a commit).

## The INTRINSIC taxonomy

Applied in `../../INTEGRATION-DELTA.md` to every element of code that is ours rather than the
original authors'. It answers *how do we know this is right?*

| tag | meaning |
|---|---|
| **INTRINSIC** | correctness is legible at the edit itself, against the original |
| **INTRINSIC by delegation** | correct because a component with its own guarantee does the work |
| **INTRINSIC by corroboration** | correct because an independent source agrees |
| **NOT INTRINSIC** | a debt — whether or not a test currently passes |
| **CONSEQUENCE** | forced by another decision, not an independent choice |

**The NOT INTRINSIC rows are the point of that file.** A reviewer looking for where unverified
authorship is load-bearing should start there.

## Four kinds of divergence

The project distinguishes them by **what licenses the change**, which is the question a reviewer
asks:

| kind | licensed by | where it lives |
|---|---|---|
| adaptation as construction | the target forces it | `INTEGRATION-DELTA.md` |
| divergence left deliberately | a choice, original's value known | `FAITHFULNESS.md` |
| **handicap: recorded, not removed** | nothing — it is a *non*-change with a consequence | **no home** |
| measurement defect in our own instruments | ours entirely | `CONSTRUCTION.md` |

The third row has no home in the document system, structurally rather than by oversight — a
non-change produces no diff to count and no authored line to attribute. See
[06](06-unknown-knowns.md).
