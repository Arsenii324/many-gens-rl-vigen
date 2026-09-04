# Working standard: rigor, observability, verification

> The standard this project holds itself to. It is written to be **enforceable** — most items
> below name a command or a mechanical check, because a standard that can only be honoured by
> remembering it will not be honoured.
>
> It is a strengthened version of the discipline in `../../docs/rl-experiment-runbook.md` and of
> what was learned the hard way in `../gen-rebuttal/vigen-idaac`. Where a rule exists because
> something specific went wrong, the incident is named. Rules without incidents are the weakest
> rules here; treat the named ones as non-negotiable.

**Task of record:** [`TASK.md`](TASK.md). **Current code assessment:** [`REVIEW.md`](REVIEW.md).

---

## 0. The one rule

> **A claim needs evidence produced by a procedure that could have produced the opposite claim.**

Almost every wrong empirical result in this group's history was not a bug. The code was correct;
the *design* could not have returned "no". A check that cannot fail, a control that was assumed
rather than measured, a comparison against nothing — these produce clean green output and false
conclusions, and they are invisible from the results. They are only visible from the design.

So the question is never "did it pass". It is **"what would this have done if the thing were
broken?"** Ask it before running, not after.

---

## 1. Understand before acting

**Read the spine yourself.** Before delegating any review or search, read the entry point, the
shared contract, and one representative leaf. Delegated readers without your context re-derive
what you already know and miss what only a whole-system view shows. In this repo the spine is:
the eval runner, the protocol object, the env wrapper, the agent factory. Four files.

**Follow the import graph, not the directory listing.** A file's presence says nothing about
whether it runs. In this repo, five algorithm files under `rlgen-vigen/rlgen_vigen/algos/` are
never imported by anything — `agent_loader` resolves `from algos.X` to the *upstream* copies via
`sys.path`. Four are byte-identical duplicates; one (`drq.py:211`) does not even parse. A reader
who trusted the listing would have reviewed dead code and missed that the live code is elsewhere.

**Trace one datum end to end.** Pick a single number that will appear in a results table and walk
it backwards: figure → aggregation → log row → the line that wrote it → the env step that produced
it. Every hop is a place a definition can silently change. This costs an hour and is the single
highest-yield hour available.

**Provenance beats prose, in a fixed order.** When artifacts disagree: the **saved config /
checkpoint args** outrank the **README**, which outranks **prose or a handover doc**. Every
disagreement between them is itself a finding worth writing down — it means someone's mental model
diverged from the code, and that divergence is still in the repo somewhere.

---

## 2. Plan so that a null result is a decision

Write the decision gates *before* running anything, in the form: *"if X comes back below Y, we
stop / pivot to Z."* A gate written afterwards is a rationalisation. `02_experiment_plan.md` in
the code repo already does this well and it is the best thing in that document — keep the habit.

Before any measurement, answer three questions in writing:

1. **Is this the quantity someone would act on?** Final-checkpoint return and
   frames-to-reach-threshold are different quantities and can rank methods differently. Measure
   the operational one. If you measure the convenient one instead, say so *in the claim*.
2. **What is the positive control?** Name an arm that *must* move if the instrument works. Without
   one, a flat result is uninterpretable — it cannot be distinguished from a broken measurement.
   This is the item most often skipped, because when you expect an effect you do not think to
   check that you could have seen one.
3. **Which axes will the claim generalise over?** Seeds, tasks, scenes, budget, shift severity,
   checkpoint. Vary at least three points on any axis the claim quantifies over. A number measured
   at one point on an axis is a claim about that point and must be worded that way.

---

## 3. Observability

### 3.1 Log per-episode, always

The single irreversible logging decision. Store `(algorithm, backbone, task, setting, scene_id,
seed, frames, checkpoint, episode_idx, return, length, terminated, truncated, success)` per
**episode**. Means are recoverable from episodes; episodes are not recoverable from means.

Every post-hoc question — different aggregation statistic, different episode count, different
scene subset, bootstrap intervals, per-scene breakdown — becomes free if the episodes exist and
impossible if they do not. In `../gen-rebuttal/vigen-idaac` this one property was worth several
GPU-days of re-runs that did not have to happen.

### 3.2 Instrument the mechanism, not only the score

A score tells you *that* something failed. Diagnostics tell you *why*, and they are nearly free to
record at eval time. For actor-critic pixel RL, log at every checkpoint: policy entropy /
`neg_log_pi` against its target, action-distribution `std` (and whether it is pinned to its
configured floor), saturated-action fraction, critic Q against the realised return, and the ratio
of deterministic to stochastic return.

This is not hypothetical: in the sibling project these five numbers turned "ALDA underperforms"
into "SAC's entropy term has collapsed — `neg_log_pi` −14.5 against a −7 target, `std` pinned at
the `exp(−10)` floor, critic Q 71.7 against a true return of 0.47." One is a mystery, the other is
a mechanism. Same runs, same cost.

### 3.3 Measure the floor; never assume it

**A negative control is measured or it does not exist.** Run the random policy for a real number
of episodes and store the distribution, not just the mean.

Why this is not pedantry: on RL-ViGen `Lift`, the shaped reward pays `1 − tanh(10·d)` at *every*
one of 500 steps, so a random arm collects up to 60.06 return without ever lifting the block. A
2-episode probe put the floor at 0.47; 100 episodes put it at 7.80 ± 11.38. Any "retention" or
"improvement" ratio computed against the 2-episode number was off by a factor of sixteen — and
looked entirely reasonable.

Then **gate on the sampling distribution, not the mean**: a run counts as having learned only if
its train score exceeds the 97.5th percentile of the mean of `n` random episodes, for the same `n`
you actually ran. Ratios whose denominator fails the gate are reported as `undefined`, never as a
number. Nine published percentages in the sibling project were retracted this way, including a
"131.3% retention" whose denominator was 0.11.

### 3.4 Monitoring long and remote jobs

- **Pack incrementally under `trap … EXIT`.** A job that is stopped or killed must still return
  its partial results. A job that archives only at the end returns an empty archive when it
  matters most.
- **Exit codes do not survive a pipe.** `cmd | tail` reports `tail`'s status. Measuring exit codes
  through a pipe once made every failure in a batch read as success. Use `PIPESTATUS`, or do not
  pipe.
- **A guard must be scoped to the work that was requested.** A resume-job guard that walked every
  run directory failed jobs for work they had not been asked to do.
- **Write the shell you are running.** A monitor using bash associative arrays under `zsh` dies
  silently. Invoke the interpreter explicitly.
- **Never echo a secret.** Install keys via piped `printf` to a `chmod 600` file. The W&B key at
  `ccm-intro/secrets/wandb_key.txt` is never printed and never committed.

---

## 4. Debugging

**Reproduce before theorising.** A minimal deterministic repro, then a hypothesis. Not the reverse.

**Bisect the *stack*, not just the history.** For an RL defect, the layers are: env → wrapper →
observation pipeline → replay/rollout storage → network → loss → optimiser → logging. Assert an
invariant at each seam and find the first one that fails. Most "algorithm" bugs are wrapper or
storage bugs.

**Fix the class, not the instance.** When you find a defect, ask what else in the repo has the
same shape. Two of the most damaging problems in the sibling project were third and fourth copies
of a claim that had already been corrected once — the correction had been applied to one file.

**Verify at the seam.** When two processes or two configs must agree, assert the agreement at
runtime where they meet, not by reading both. Verify the env mode *inside* the worker, not in the
launcher that was supposed to have set it.

---

## 5. Verification: the iron law

> **No completion claim without fresh verification evidence produced in this session.**

Before writing any sentence that asserts something works:

1. **Identify** the command that would prove it.
2. **Run** it fully — not a subset, not a cached run.
3. **Read** the whole output, the exit code, and the failure count.
4. **State** the claim *with* the evidence, or state the actual status.

| Claim | Requires | Not sufficient |
|---|---|---|
| tests pass | the test command's output, 0 failures | a previous run, "should pass" |
| build works | exit 0 from the build | linter clean |
| bug fixed | the original symptom, retested | the code changed |
| regression test works | red→green cycle demonstrated | it passed once |
| an agent finished | the diff | the agent's report |
| requirement met | line-by-line against `TASK.md` §3 | tests pass |

Red flags that mean stop: "should", "probably", "seems to"; satisfaction expressed before running
anything; a claim phrased differently to dodge the rule. Spirit over letter.

**Correcting yourself counts too.** Verify a claim before repeating it — including your own from
earlier in the same session. Several of the worst errors in the sibling project were confident
restatements of an earlier unverified sentence.

---

## 6. Tests: the failure modes that matter

An RL repo's tests fail in characteristic ways. All four below produce green output.

**6.1 The check that cannot fail.** A cross-check that parsed zero rows from its input reported
success — it compared nothing, and "0 disagreements" read as agreement. **Rule: every checker
asserts its input is non-empty and fails loudly if it is not.** A verifier that verifies nothing
must exit non-zero.

**6.2 The fixture that production never produces.** A test harness whose `DummyEnv` declares
`obs_shape = (3, 84, 84)` while the real wrapper emits `(9, 84, 84)` (3 RGB frames × 3 stack)
exercises a shape the pipeline never sees. **Rule: fixtures are derived from the real
factory — `env = make_env(...); shape = env.observation_space.shape` — never re-declared by hand.**

**6.3 The assertion co-located with the defect.** See §7. If the same function both introduces the
fault and asserts it is present, the test measures Python, not your system.

**6.4 The untrained agent that looks like a result.** `load_or_instantiate_agent()` returns a
randomly-initialised network when no checkpoint is given, and the runner writes a full results CSV
and protocol card from it with no marker. Everything currently in `results/` was produced this
way. **Rule: a results artifact must record the provenance of the weights that produced it —
`checkpoint_path` and its hash, or an explicit `weights: random_init` field. A run that cannot say
where its weights came from is not admissible.** Prefer failing closed: evaluation without a
checkpoint requires an explicit `--allow-untrained` flag, and that flag is stamped into the output.

**6.5 Red-green every regression test.** Write the test, watch it pass, **revert the fix, watch it
fail**, restore the fix, watch it pass. A regression test that has never been seen to fail is an
assertion about nothing. "I've written a regression test" is not a claim you may make without
having run this cycle.

**6.6 Truthiness where a count belongs.** `assert runs` is true for *any* number of discovered
items, so a test that meant "the one run I just wrote" stayed green while silently comparing
against several. `assert len(runs) == 1` fails the moment contamination appears. **Rule: when you
know how many things should be there, assert the number.** The two hermetic tests in this repo's
plotter suite pin `== 1` and `== 3`; the one that did not was the one that broke.

**6.7 The test that reads the machine.** A test computed its search root as
`dirname(dirname(logdir))`. Because `logdir` sat *one* level below the fixture's temp directory,
that expression resolved to the whole of `$TMPDIR` — so the test walked every temp directory on
the machine, picked up runs written by concurrent processes, and compared this run's numbers
against another run's. It passed alone and failed under load, which reads as flakiness rather than
as a bug.

**Rule: a test's inputs are the ones it created.** Derive paths forward from the fixture, never
backward with repeated `dirname`. And where production code takes a root to walk, make the
nonsensical roots — `$TMPDIR`, `/`, `$HOME` — a loud error rather than a slow, plausible answer;
a mistyped `--logs` deserves an exception, not a figure.

**6.8 A guard must test the proposition you care about.** Two from one session:
`tar czf … && echo packed` proved the *command ran*, not that the archive held what was promised —
so a job whose payload was never created packed three stray files, exited 0, and reported success.
And `dd bs=1m` (a BSD spelling GNU coreutils rejects) wrote nothing while the script sailed on.
**Rule: assert the postcondition — read the artifact back and check it contains what you said it
would.** "The command returned 0" is not the postcondition.

This is the same family as §6.1, and it recurs constantly: `str.replace` with a mistyped anchor,
a hyperparameter passed to a config that has no such field, an `apply()` whose write never landed.
**Operations that fail by doing nothing are the ones worth an explicit assertion.**

---

## 7. Mutation testing, done properly

This section is long because the repo currently contains something *called* mutation testing that
is not, and the distinction is the difference between measuring your tests and flattering them.

### 7.1 The definition

> **Mutate the production code. Re-run the existing test suite, unchanged. A mutant is *killed*
> if the suite fails.** The measured quantity is the fraction of mutants killed — that is the
> suite's sensitivity, and it is the only evidence that the suite would notice a real regression.

Three properties are all necessary:

1. **The mutation is applied to the system under test**, not to the test.
2. **The oracle is the pre-existing suite**, not an assertion written next to the mutation.
3. **The result is a rate over a catalogue**, not a per-mutant anecdote.

### 7.2 The worked negative example

`run_mutants.py` in the code repo reports "60/60 mutants killed, 100% kill rate." It satisfies
none of the three properties. Each "mutant" replaces `agent.act` with a hand-written function that
directly exhibits a defect, then asserts inline that the defect is present:

```python
def mutant_act(obs, step=0, eval_mode=True):
    return np.array([5.0] * act_dim)        # the "mutation"
agent.act = mutant_act
action = agent.act(obs, ...)
if np.any(action > env.action_space.high):  # the "oracle", 3 lines later
    return True, "Mutant Killed."
```

This asserts `5.0 > 1.0`. It tests NumPy. It would report 100% against an empty test suite, against
a deleted codebase, against any agent whatsoever — and `test_eval_invariants.py`, the actual suite,
is never run at all. The in-place mutant is killed by a NumPy casting rule; the PRNG mutant is
killed by `os.urandom` returning different bytes. **A kill rate that is invariant to the quality of
your tests is not a measurement.** The handover doc reports the 100% as a verification result; it
is the strongest single reason to treat that doc as testimony rather than evidence.

*(The repo's own `uncertainty_register.md` §E4 spots this for one of the five mutants. The
generalisation — that none of the five mutate production code — is the finding.)*

### 7.3 The mechanics

Mutants are applied as a **patch to a copy of the tree**, the suite runs against the copy, and the
tree is restored. Never mutate the working tree in place.

```
for m in catalogue:
    cp -r src build/mut          # or git worktree
    apply m to build/mut
    run the FULL suite against build/mut
    record: killed (suite exit != 0) | SURVIVED (suite exit == 0)
report kill rate; every survivor is a named gap in the suite
```

**Survivors are the output.** A 100% kill rate on a small catalogue means the catalogue is too
easy, not that the suite is perfect. Grow the catalogue until something survives, then decide
whether to write the missing test or to record the gap as accepted.

**The catalogue is committed and reviewed.** Mutants chosen after seeing which ones die is
p-hacking for tests.

### 7.4 The catalogue that matters for *this* repo

Generic mutation tools (`mutmut`, `cosmic-ray`) flip operators and are largely useless for RL —
they perturb arithmetic that no test constrains. The mutants worth writing here are the ones that
correspond to a **fair-comparison failure**: a change that alters a reported number without
crashing. Each entry below should be a real patch, and the suite should die on it.

| # | Mutation to production code | What must catch it |
|---|---|---|
| M1 | `n_eval_episodes` 10 → 9 for one algorithm only | protocol-hash equality across records |
| M2 | flip `deterministic=True` → `False` in one agent's eval path | eval records carry `policy_mode`; a test asserts it is constant across baselines |
| M3 | accumulate reward one step past `done` | episode-length invariant vs the env's known horizon |
| M4 | `action_repeat` 2 → 4 in the env factory | frames-vs-agent-steps accounting test; budget in frames |
| M5 | swap normalisation convention (`obs/255 − 0.5` ↔ `obs/255`) for one family | a checkpoint↔convention compatibility assertion (**currently nothing would catch this**) |
| M6 | reuse the same env seed for every eval episode | across-episode variance test — variance collapses to ~0 |
| M7 | evaluate on the training scene while labelling it `eval` | scene-id recorded per episode and asserted disjoint from train |
| M8 | drop one frame from the stack (9 → 8 channels) | shape assertion derived from the env, not hand-declared (see §6.2) |
| M9 | change the aggregation from mean to IQM in one place | the statistic is named in the artifact and asserted equal across rows |
| M10 | return a randomly-initialised agent when the checkpoint path is wrong | weights-provenance field (§6.4) |

M5, M7 and M10 are the ones that would silently produce a *publishable-looking wrong table*. Write
those first.

### 7.5 A curated catalogue is not enough — measure with one you did not design

This is the most important thing learned while building this repo, and it was learned the
expensive way.

The curated catalogue in §7.4 scored **14/14**. The same suite, measured by a **random operator
sweep** over the AST of the same production code — comparison-boundary flips, arithmetic swaps,
boolean-connective swaps, small-integer perturbation, dropped negations, sites chosen uniformly
at random with no regard for coverage — scored **12/40, 30%**.

Both numbers are correct. They measure different things:

> A catalogue where one person writes the mutants **and** the tests that kill them measures that
> person's imagination. It cannot discover a module they never thought about.

And it did not. The sweep found `trainer.py` with no tests at all, `replay.py`'s index arithmetic
unconstrained, `bootstrap_ci` unconstrained — and, sharpest of all, that mutating the truncation
comparison in the **real** environment survived while the identical mutation in the **synthetic**
one was killed, because every test ran on the synthetic backend and the real class was never
executed. A stand-in backend that lets the real one go untested is this document's §6.2 all over
again, in a place nobody was looking.

**So: run both.** The catalogue documents which specific failures you are defended against, which
is genuinely useful. The sweep tells you what your suite is actually worth.

Two rules that make the sweep number honest:

- **Report an out-of-sample seed.** Once you fix the survivors a seed found, re-running that seed
  is an in-sample score and flatters you exactly the way a perfect curated score does. Run a fresh seed
  whose survivors you have never looked at, and report *that*.
- **Print every survivor with its diff, and triage by hand.** Some mutants are semantically
  equivalent to the original — a perturbed constant inside an error message, a bound that is never
  reached — and no suite can kill them. Counting them as failures understates sensitivity, but
  letting a script decide which is which reintroduces the problem. A survivor is either a real gap
  or a demonstrably equivalent mutant, and saying which is a judgement.

Also: exclude nothing quietly. If a module in the production package is really test
instrumentation (this repo's `SyntheticEnv` lives in `rlgen/envs.py` and is exactly that), say so
next to the number rather than filtering it out of the sample.

### 7.6 The suite is the instrument — three ways the number lies

All three were found here, and none of them is visible from the score.

**7.6.1 A flaky test in the oracle biases the measurement upward.** `pytest tests` *is* the
oracle, so a test that can fail for reasons unrelated to the mutation records a spurious KILL.
This is not the ordinary annoyance of flakiness: it inflates the very number you are quoting as
evidence of sensitivity.

Caught in the act here: a mutation to `rlgen/replay.py` was recorded killed by *the plotter test*
— a test that compares one run against itself and cannot legitimately notice a replay change. On
the hermetic tree, same seed and same mutation, it **survives**.

**Rule: before quoting a mutation score, confirm the oracle is deterministic under load.** Run the
unmutated suite concurrently with itself. The sanity mutant (§7.3) checks that the suite passes;
it does not check that it passes *reliably*, and those are different claims. Treat a kill
attributed to a test with no plausible causal path to the mutated code as a bug report about the
suite.

**7.6.2 A hand-written coverage list silently shrinks.** The operator sweep's `TARGETS` was a
literal list of module names. A module added later never joined it, so 34 of 465 mutable sites —
7.3% of the pool, including the entire on-policy trainer — were unreachable from the day that file
was written, while the number was reported as a sweep over the whole package. **The figure was not
wrong; its stated scope was, which is worse**, because nothing about the output looks incomplete.

**Rule: derive coverage from the package, and make a missing target fatal.** `if not
os.path.exists(path): continue` turns a renamed module into a silent gap.

**7.6.3 A score that moves with ambient machine state is not a measurement.** Two mutants here are
observable only when an optional dataset is *absent*, and the test guarding them skips (correctly)
when it is present. So the catalogue scored one value before that dataset was downloaded and a
lower one after — **with no code change in between**.

§7.2 already forbids a skip guard derived from the system under test. This is the subtler cousin:
the guard was derived from the filesystem, which is *right*, and the hole remained anyway, because
one environment had no test at all.

**Rule: when a mutant is only observable in one environment, write the complementary test for the
other**, so that whichever machine you are on, something is watching. Here: dataset present → a
no-false-positive test; dataset absent → the refusal test; either way → a trainer test that
simulates the report instead of depending on a real absence. **And when a score moves, suspect the
environment before the code.**

### 7.7 Report honestly

Report `killed / total`, list every survivor by name, and state what the catalogue does **not**
cover. "100%" without a survivor list is a warning sign, not a result.

State the environment the score was measured in, since §7.6.3 shows it is part of the result.

And triage survivors rather than reflexively killing them. One survivor here was a boundary
constant in a ring buffer; diffing the valid-index sets across five buffer configurations showed
the mutation admits a few extra transitions whose frame stacks are clamped-degenerate rather than
corrupt. An attempt to kill it with a content invariant *failed*, and that failure is the
evidence — it is conservatism, not a defect. **Writing a test that pins the literal would have
raised the score and taught nobody anything.** The invariant was kept because it asserts something
real; the mutant is recorded as equivalent.

---

## 8. Claims and evidence

**Name the statistic completely.** Not "return" but *"mean over 10 episodes × 10 eval scenes, at
the 500k-frame checkpoint, deterministic policy."* Two mislabelled numbers in the sibling
project — a scene-0 value described as the 10-scene headline — survived review twice. A mislabelled
statistic is how a wrong number reaches a reviewer with everyone's arithmetic correct.

**A null needs a minimum detectable effect.** "No difference between A and B" is meaningless
without "this design resolves effects down to X". Get X from the positive control: how large was
the effect it *did* register, at what precision? No control, no null — only an unfinished
measurement.

**Check collinearity before reading any attribution.** A near-zero coefficient against a
0.9-collinear partner is *unidentifiable*, not null. Print the predictor correlation matrix next
to any ablation or regression table, and if two factors are entangled, say the design cannot
separate them.

**Censoring is an aggregation problem.** Runs that hit a step cap, timed out, or diverged did not
take "budget" long — they did not finish. Record them as censored and make the *aggregation*
respect it. Averaging a cap in as if it were an observation produces flat curves that read as real
scaling. Always report how many runs were censored.

**Tune each arm independently.** A grid centred on one method's optimum handicaps the others. If a
winner sits on a grid boundary, the optimum is probably outside the grid and the comparison is an
artifact of where you stopped looking — say so.

**Normalise before comparing.** Two curves sampled on different grids are not comparable raw. Per
100k frames, or per update — state which. Comparing a 50k-spaced grid against a 400k-spaced grid
without normalising understated a volatility gap by more than an order of magnitude (1.7× reported
where the normalised figure was 40×).

**State the scope the evidence supports**, not the scope you want: the axes and ranges measured,
what the control registered, the effect size the design could resolve. A missing one of those is
the next finding, not a footnote.

---

## 9. Provenance

- **Every artifact stamps the code that produced it.** Commit SHA into the run directory and into
  the deployed archive; the packer *fails* if the stamp is missing. In the sibling project the
  final runs had no recorded code version and the gap had to be closed after the fact by hashing
  eleven files against a candidate commit. Cheap before, expensive after.
- **`ext/` and vendored upstream are read-only.** Copy out, edit the copy.
- **Record the exact tree state a review covers.** A review of a moving target is worthless unless
  it says which state it read. Use commit SHA + a content hash of the first-party source set, so
  the review can be re-run and diffed when the tree settles.
- **Private by default** for anything uploaded — Kaggle kernels and datasets included. This is
  unpublished lab work.

---

## 10. Documents written by an AI (including by me)

Treat a handover document produced by the agent that wrote the code as **testimony by an
interested party**: a useful index of where to look, not evidence about what is there.

The two AI docs for this repo are unusually good — `uncertainty_register.md` is honest, specific,
and catches real problems its own author's code has. That is exactly why the failure mode is
subtle: high average quality lends unearned credibility to the wrong lines. Concretely, they
report a "100% mutation kill rate" as verification (§7.2), and they say nothing about the five
requirements the repo was actually commissioned to satisfy.

**Rule:** for every claim in such a document that you intend to rely on, open the cited lines. A
claim stated with more confidence than the code supports is itself a reportable finding, and it
should be recorded in the review next to the code findings — because the next reader will meet the
document before they meet the code.

---

## 11. Delegation

Parallel agents are for genuine fan-out — many independent files, several angles to verify at
once. They are not a substitute for understanding.

- **Read the spine first** (§1) and hand agents that context, or they duplicate each other's work
  and miss what only the whole view shows.
- **Prefer Sonnet** for reading slices; reserve the larger model for synthesis and adversarial
  passes.
- **Disjoint slices, structured returns**, each finding carrying `path:line` and a concrete failure
  scenario. A finding with no line is a suspicion and must be labelled one.
- **Adversarially check before reporting.** Default the checker to skepticism: a finding whose
  failure scenario does not follow from the quoted code is killed, not softened.
- **Never trust an agent's success report.** Check the diff, or the artifact, yourself (§5).
- **Read-only means read-only.** When another agent is working in a tree, reviewers get explicit
  no-write instructions and a scratch directory outside it.

---

## 12. Pre-claim checklist

Run down this list before saying a piece of work is done.

- [ ] The verification command was run **in this session**, in full, and its output read.
- [ ] Every number in the write-up is re-derivable from a stored artifact by a script, not by hand.
- [ ] Each statistic is named completely: reduction, over what, at which checkpoint, which scenes.
- [ ] A **measured** negative control exists, and ratios against a denominator below it read
      `undefined`.
- [ ] A **positive control** was run, and any null states the effect size the design could resolve.
- [ ] Every new regression test has been through red→green.
- [ ] The mutation catalogue ran against **production** code with the **existing** suite, and
      survivors are listed by name.
- [ ] No checker in the pipeline can pass on empty input.
- [ ] Artifacts carry the commit SHA and the provenance of the weights.
- [ ] Claims taken from a handover document were checked against the cited lines.
- [ ] What was *not* done is stated as plainly as what was.
