"""The mutation catalogue: deliberate defects in PRODUCTION code, each a claim about the suite.

WHAT MUTATION TESTING IS, and what this repo used to do instead. Mutation testing means: change
the system under test, run the EXISTING test suite unchanged, and see whether it fails. The
measured quantity is the suite's sensitivity.

The previous `run_mutants.py` reported "100% kill rate, 60/60". It satisfied none of that. Each of
its five "mutants" replaced `agent.act` with a hand-written function that directly exhibited a
defect, then asserted inline, three lines later, that the defect was present:

    def mutant_act(...): return np.array([5.0] * act_dim)   # the "mutation"
    agent.act = mutant_act
    if np.any(action > env.action_space.high):              # the "oracle"
        return True, "Mutant Killed."

That asserts `5.0 > 1.0`. It tests NumPy. It would report 100% against an empty test suite, and
`test_eval_invariants.py` -- the actual suite -- was never run. A kill rate invariant to the
quality of your tests is not a measurement.

EVERY MUTANT BELOW IS A PATCH TO PRODUCTION CODE, and the default oracle is `pytest
tests`. This line used to say "a file under `rlgen/`"; it stopped being true at M24 and
was corrected on 2026-08-27, when M25-M31 added the clone-era instruments under
`scripts/`. `rlgen/` is the retired port -- a catalogue that only mutated it would be
measuring the suite's sensitivity to code that no longer runs.

The catalogue is committed and reviewed, because mutants chosen after seeing which ones die is
p-hacking for tests. Each entry names the real-world failure it stands for; the ones marked
CRITICAL are those that would produce a publishable-looking wrong table rather than a crash.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Mutant:
    id: str
    path: str
    find: str
    replace: str
    #: What breaks in the world if this defect ships.
    why: str
    critical: bool = False
    #: Which tests are claimed to catch it. Default is the whole suite, which is the honest
    #: default when the claim is "something catches this". Naming a file makes the claim
    #: SHARPER -- "test_metrics catches this" says more than "the suite does" -- and it keeps a
    #: mutant cheap enough to be run often. It is not a weaker check: a kill is a kill, and a
    #: scoped oracle that fails to kill is a survivor exactly as before.
    oracle: str = "tests"


CATALOGUE: list[Mutant] = [

    Mutant(
        id="M1-episode-count",
        path="rlgen/evaluate.py",
        find="            for ep in range(per_scene):",
        replace="            for ep in range(max(1, per_scene - 1)):",
        why="One baseline evaluated on fewer episodes than another. Nothing crashes; the "
            "confidence interval is simply wider for one row of the table and nobody can tell.",
        critical=True),

    Mutant(
        id="M2-ignore-deterministic",
        path="rlgen/agents.py",
        find="            a = self._agent.act(np.asarray(obs), self._step, eval_mode=bool(deterministic))",
        replace="            a = self._agent.act(np.asarray(obs), self._step, eval_mode=True)",
        why="The `deterministic` flag is silently ignored. The protocol card keeps claiming "
            "`policy_mode: deterministic` while a different quantity is measured.",
        critical=True),

    Mutant(
        id="M3-truncate-late",
        path="rlgen/envs.py",
        find="        truncated = self._t >= self.spec.steps_per_episode\n"
             "        info: dict[str, Any] = {\"scene_id\": self.spec.scene_id, \"mode\": self.spec.mode}\n"
             "        if truncated:",
        replace="        truncated = self._t > self.spec.steps_per_episode\n"
                "        info: dict[str, Any] = {\"scene_id\": self.spec.scene_id, \"mode\": self.spec.mode}\n"
                "        if truncated:",
        why="Reward accumulated one step past the horizon. Every return is inflated by one "
            "step's worth, consistently, so no curve looks wrong.",
        critical=True),

    Mutant(
        id="M4-action-repeat-ignored",
        path="rlgen/envs.py",
        find="    @property\n    def steps_per_episode(self) -> int:\n        return self.horizon // self.action_repeat",
        replace="    @property\n    def steps_per_episode(self) -> int:\n        return self.horizon",
        why="Frames and agent steps are conflated. With action_repeat=2 every episode runs twice "
            "as long as the protocol says and the budget means something different per baseline.",
        critical=True),

    Mutant(
        id="M5-contract-dtype-unchecked",
        path="rlgen/envs.py",
        find="    if obs.dtype != np.uint8:\n        raise ContractError(f\"obs dtype {obs.dtype}, expected uint8. Normalisation belongs in \"\n                            f\"the baseline, not here.\")",
        replace="    if False:\n        raise ContractError(\"unreachable\")",
        why="The observation dtype contract stops being enforced, so a float observation reaches "
            "an encoder that expects uint8 and is normalised twice -- a silent 1/255 input scale.",
        critical=True),

    Mutant(
        id="M6-constant-episode-seed",
        path="rlgen/evaluate.py",
        find='    key = f"{protocol_hash}|{mode}|{scene_id}|{seed}|{episode_idx}"',
        replace='    key = f"{protocol_hash}|{mode}|{scene_id}|{seed}|0"',
        why="Every episode runs from the same seed. Across-episode variance collapses to zero, "
            "the policy looks far more consistent than it is, and the CI is meaninglessly tight.",
        critical=True),

    Mutant(
        id="M7-evaluate-on-train-scene",
        path="rlgen/evaluate.py",
        find="    scenes = list(scene_ids if scene_ids is not None else protocol.eval_scene_ids)",
        replace="    scenes = [protocol.train_scene_ids[0]] * len(\n"
                "        list(scene_ids if scene_ids is not None else protocol.eval_scene_ids))",
        why="THE headline defect. Evaluation silently runs on the training scene while every "
            "artifact still says eval-easy. The number is a training-distribution number wearing "
            "a generalisation label -- exactly what unpatched RL-ViGen does.",
        critical=True),

    Mutant(
        id="M8-frame-stack-off-by-one",
        path="rlgen/envs.py",
        find="    @property\n    def obs_shape(self) -> tuple:\n        return (3 * self.frame_stack, self.image_size, self.image_size)",
        replace="    @property\n    def obs_shape(self) -> tuple:\n        return (3 * (self.frame_stack - 1), self.image_size, self.image_size)",
        why="One frame short. The agent sees less history than the protocol claims; a suite whose "
            "fixtures hand-declare the shape would never notice.",
        critical=False),

    Mutant(
        id="M9-aggregation-hardcoded",
        path="rlgen/evaluate.py",
        find="        out[T.EVAL_RETURN_MEAN] = _reduce(rets, protocol.aggregation)",
        replace="        out[T.EVAL_RETURN_MEAN] = _reduce(rets, \"iqm\")",
        why="The reported statistic stops being the declared one. On this benchmark's bimodal "
            "eval distribution IQM trims the successful tail, so it reads systematically lower.",
        critical=True),

    Mutant(
        id="M10-unknown-tags-accepted",
        path="rlgen/logging_.py",
        find="        unknown = set(scalars) - tags.ALL_TAGS\n        if unknown:",
        replace="        unknown = set()\n        if unknown:",
        why="A baseline can invent its own logging key. The shared plotter then has to guess, "
            "and a curve can be silently missing from one baseline's panel.",
        critical=False),

    Mutant(
        id="M11-protocol-hash-ignores-episodes",
        path="rlgen/protocol.py",
        find='    HASH_EXCLUDE = ("name", "seed", "weights_source", "code_commit")',
        replace='    HASH_EXCLUDE = ("name", "seed", "weights_source", "code_commit", '
                '"episodes_per_scene", "aggregation")',
        why="Two runs measured under different episode counts and different reductions compare "
            "as `comparable_to` each other, so the guard that keeps a table honest stops guarding.",
        critical=True),

    Mutant(
        id="M12-mix-protocols-in-one-log",
        path="rlgen/logging_.py",
        find="                if r.protocol_hash != self.protocol.hash():",
        replace="                if False:",
        why="Episodes from two protocols land in one episodes.csv, and every post-hoc "
            "aggregation over that file silently averages across incomparable settings.",
        critical=True),

    Mutant(
        id="M13-replay-splices-episodes",
        path="rlgen/replay.py",
        find="            if self._episode[prev] == ep and prev != newest:",
        replace="            if True:",
        why="Frame stacks splice across the ring-buffer wrap, so a training batch contains "
            "observations assembled from two unrelated trajectories. Training still 'works'.",
        critical=False),

    # M18-ibac-noise-at-eval RETIRED 2026-08-14 (docs/REGISTER.md): targeted
    # rlgen/algos/onpolicy_ext.py::IBACSNILearner, deleted along with that whole file once
    # ibac_sni's own hermetic module (rlgen/algos/ibac_sni/) fully replaced it. The property this
    # mutant protected -- no noise injection at eval -- is still covered, but no longer via a
    # `self.policy.training`-flag check: the hermetic module's `IBACSNIPolicy.forward` takes an
    # explicit `sample: bool` argument from its caller instead, and
    # tests/test_onpolicy.py::test_ibac_bottleneck_is_silent_at_eval_and_noisy_in_training checks
    # it directly against the live module. No equivalent mutant re-added for the new code path --
    # out of scope for a dead-code deletion pass; flagged here rather than silently dropped.

    Mutant(
        id="M19-onpolicy-agent-in-offpolicy-loop",
        path="rlgen/agents.py",
        find="        raise RuntimeError(\n"
             "            f\"{type(self.learner).__name__} is on-policy and must be driven by \"",
        replace="        return {}  # noqa\n        raise RuntimeError(\n"
                "            f\"{type(self.learner).__name__} is on-policy and must be driven by \"",
        why="An on-policy agent handed to the off-policy trainer silently does nothing: it "
            "collects frames, never learns, and emits a complete set of artifacts with a flat "
            "curve that reads as 'this method is bad on this benchmark'.",
        critical=True),

    Mutant(
        id="M17-invert-data-presence-check",
        path="rlgen/registry.py",
        find="        if not present():",
        replace="        if present():",
        why="The dataset-presence check is inverted, so a baseline whose data is missing reports "
            "no problem and trains until it dies at the first gradient step. Worth its own entry "
            "because of HOW it used to survive: the test guarding it skipped itself when "
            "`check_data_requirements` returned nothing -- i.e. the defect disabled the test that "
            "catches it, and pytest exited 0. A skip condition derived from the system under test "
            "is a vacuous check.",
        critical=True),

    Mutant(
        id="M15-data-preflight-disabled",
        path="rlgen/trainer.py",
        find="    problems = registry.check_data_requirements(baseline)\n    if problems:",
        replace="    problems = registry.check_data_requirements(baseline)\n    if False:",
        why="A baseline whose training dataset is absent starts anyway, evaluates at frame 0, "
            "writes a protocol card / episodes.csv / tensorboard file, and only then dies at the "
            "first gradient step. The leftover directory is indistinguishable from a real run's.",
        critical=True),

    Mutant(
        id="M16-no-warmup-reset",
        path="rlgen/envs.py",
        find="        # Pinned by `test_real_env.py::test_same_seed_reproduces_from_the_very_first_episode`.\n        self._env.reset()",
        replace="        # Pinned by `test_real_env.py::test_same_seed_reproduces_from_the_very_first_episode`.\n        pass",
        why="robosuite's first reset after construction draws from a different distribution than "
            "later ones (measured ~45% higher return with a zero policy). evaluate() builds one "
            "env per scene, so episode 0 of every scene would be systematically off -- a tenth of "
            "the data at the default episodes_per_scene, invisible in any curve.",
        critical=True),

    Mutant(
        id="M14-alias-hidden",
        path="rlgen/registry.py",
        find='        if self.status == "alias" and self.alias_of:\n            return f"{self.name} (= {self.alias_of})"',
        replace='        if False:\n            return ""',
        why="A declared alias stops being labelled, so CTRL appears in the legend as an "
            "independent baseline next to the CURL it is byte-identical to.",
        critical=False),
    # -- scripts/metrics.py ---------------------------------------------------------------
    # The metric definitions were added after the clone approach and were NOT covered by this
    # catalogue -- docs/CONSTRUCTION.md C22. 44 passing tests is an assertion about the tests;
    # these are the claim that they constrain the metrics. Each one undoes a specific documented
    # design decision, so a survivor names the decision that is unprotected.
    Mutant(
        id="M19-wilson-becomes-normal-approx",
        path="scripts/metrics.py",
        find="    half = (z / d) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))",
        replace="    half = z * math.sqrt(p * (1 - p) / n)",
        why="The normal approximation has width ZERO at p=0. Every success rate this project "
            "reports is 0.000, so the interval would claim to have proven the policies never "
            "succeed, from ten episodes. This is the exact reason Wilson was chosen.",
        oracle="tests/test_metrics.py",
    ),
    Mutant(
        id="M20-single-frame-treated-as-measurable",
        path="scripts/metrics.py",
        find="    if n_frames <= 1:",
        replace="    if n_frames <= 0:",
        why="A single frame carries no motion because the quantity is UNDEFINED, not because it "
            "is zero. Four baselines receive one frame; conflating the two readings is what the "
            "frame-stack finding rests on not doing.",
        oracle="tests/test_metrics.py",
    ),
    Mutant(
        id="M21-explained-variance-zero-not-nan",
        path="scripts/metrics.py",
        find='    return float("nan") if var == 0 else float(1.0 - (yt - yp).var() / var)',
        replace="    return 0.0 if var == 0 else float(1.0 - (yt - yp).var() / var)",
        why="0.0 reads as 'the critic explains nothing'; nan says the quantity is undefined. On "
            "a sparse manipulation reward an all-zero-return batch is routine, so this would "
            "silently report a real-looking value for a case that has none.",
        oracle="tests/test_metrics.py",
    ),
    Mutant(
        id="M22-tv-distance-unnormalised",
        path="scripts/metrics.py",
        find="    return float(np.abs(ha - hb).sum(axis=1).mean() / 2.0)",
        replace="    return float(np.abs(ha - hb).sum(axis=1).mean())",
        why="Total variation must be bounded in [0,1] for the regime-separation ratio to mean "
            "anything. Unnormalised it reaches 2, and 'separated 6x' would be read off a "
            "quantity with the wrong scale.",
        oracle="tests/test_metrics.py",
    ),
    Mutant(
        id="M23-saturation-misses-the-boundary",
        path="scripts/metrics.py",
        find="    return float(((a <= lo + eps) | (a >= hi - eps)).mean())",
        replace="    return float(((a < lo) | (a > hi)).mean())",
        why="Actions ON the boundary are exactly the clipped mass this measures. Counting only "
            "actions BEYOND it reports ~0 for the four unsquashed heads and erases Finding 6.",
        oracle="tests/test_metrics.py",
    ),
    Mutant(
        id="M24-approx-kl-defaults-to-k1",
        path="scripts/metrics.py",
        find='def approx_kl(log_ratio, estimator: str = "k3") -> float:',
        replace='def approx_kl(log_ratio, estimator: str = "k1") -> float:',
        why="k1 is unbiased but CAN GO NEGATIVE, which is unusable as an early-stopping trigger "
            "and invites someone to 'fix' the sign. k3 is the documented default and the reason "
            "this metric exists rather than deferring to TorchRL's k1-only value.",
        oracle="tests/test_metrics.py",
    ),

    # ------------------------------------------------------------------------------------------
    # M25-M31: the clone-era instruments, added 2026-08-27. Every one of these was run by hand as
    # a `cp`/patch/`pytest`/restore cycle on the working tree during the session that built them,
    # which is exactly what `docs/RIGOR.md` section 7.3 forbids -- "a mutation runner that edits
    # your source and restores it afterwards loses a race with any interruption", and that session
    # was interrupted twice. Nothing was left behind (checked), but the practice was wrong and the
    # fix is not a better restore: it is putting the mutants HERE, where they run against a copy,
    # are reviewed, and keep running after the session that thought of them has ended.
    # ------------------------------------------------------------------------------------------

    Mutant(
        id="M25-units-axis-splits-unnoticed",
        path="scripts/audit_comparability_seam.py",
        find='        out[b] = ("raw | learner: NORMALISED by running return std, clipped" if norm',
        replace='        out[b] = ("normalised | learner: NORMALISED by running return std, clipped" if norm',
        why="A UNITS axis -- what a reported number MEANS -- silently splits. idaac/ctrl/ppg's "
            "reported return is raw ONLY because each one's episode monitor sits inside its "
            "normaliser; move a wrapper and twelve numbers change units with nothing raised. "
            "R3 is graded off this axis, so an unnoticed split would be reported as comparable.",
        critical=True,
        oracle="tests/test_comparability_seam_audit.py",
    ),

    Mutant(
        id="M26-seam-audit-runs-on-a-missing-tree",
        path="scripts/audit_comparability_seam.py",
        find="    if empty:\n        raise EmptyInput(",
        replace="    if False:\n        raise EmptyInput(",
        why="Every negative finding in that audit is an ABSENCE: frame_stack reads 1 from no "
            "wrapper, reward_pipeline reads 'learner: raw' from no VecNormalize. A missing source "
            "tree therefore yields a confident, uniform, fictional result with no error -- and "
            "uniform is the answer that gets quoted. RIGOR 6.1's 'check that cannot fail'. Not "
            "hypothetical: this project retired the whole rlgen/ tree mid-flight.",
        critical=True,
        oracle="tests/test_comparability_seam_audit.py",
    ),

    Mutant(
        id="M27-open-decision-counted-as-settled",
        path="scripts/decisions.py",
        find='        d["settled"] = bool(ch) and not any(m in ch.lower() for m in UNDECIDED_MARKERS)',
        replace='        d["settled"] = bool(ch) and "not yet made" not in ch.lower()',
        why="C78: the ledger of open decisions silently closes one whenever a writer phrases "
            "'undecided' differently from the single hardcoded literal. It still prints a "
            "confident count, and the count is what gets trusted. The real block it swallowed "
            "was P-C76, the evaluation-protocol branch point R3 now fails on.",
        critical=True,
        oracle="tests/test_decisions_ledger.py",
    ),

    Mutant(
        id="M28-cell-budget-yields-no-checkpoint",
        path="scripts/run_cell.sh",
        find='      if [ $(( $2 % 50000 )) -eq 0 ]; then echo $(( $2 + 5000 )); else echo "$2"; fi ;;',
        replace='      echo "$2" ;;',
        why="C77: a native run launched at exactly N never saves at N -- the save sits inside "
            "`if time_step.last():` at the top of a `while step < until` loop, so the loop exits "
            "before it. Reverting the bump means every cell at a round budget trains for hours "
            "and writes no checkpoint, which is how this was found in the first place.",
        critical=True,
        oracle="tests/test_run_cell_budget.py",
    ),

    Mutant(
        id="M29-unwatchable-run-reported-healthy",
        path="scripts/watch_divergence.py",
        find="    if not present:\n        return BLIND, (",
        replace="    if not present:\n        return OK, (",
        why="C79: a run whose train.csv has no loss columns -- drq always, by its own tb "
            "regression -- cannot be checked for divergence. Reporting OK converts 'we could not "
            "look' into 'we looked and it was fine', and a NaN checkpoint then passes into the "
            "results as a policy.",
        critical=True,
        oracle="tests/test_divergence_watch.py",
    ),

    Mutant(
        id="M30-preserves-a-finished-run-as-a-live-one",
        path="scripts/preserve_intermediate_snapshot.py",
        find="            if d in seen_before or d in done:",
        replace="            if d in done:",
        why="The 50k preserver would copy a snapshot from a run that finished BEFORE it started, "
            "inventing a paired budget point no live run produced. The pairing is what turns "
            "C73's n=1 contaminated budget comparison into a within-run one, so a fabricated "
            "member is worse than a missing one.",
        oracle="tests/test_preserve_intermediate_snapshot.py",
    ),

    Mutant(
        id="M31-R3-grades-itself-met",
        path="scripts/requirements.py",
        find='    return "NEEDS JUDGEMENT", (\n        f"every derived UNITS axis is uniform, all {len(cond_split)} splits are CONDITIONS and "',
        replace='    return "MET", (\n        f"every derived UNITS axis is uniform, all {len(cond_split)} splits are CONDITIONS and "',
        why="The null is that two baselines' numbers are NOT the same quantity. A finite list of "
            "uniform axes removes the ways somebody thought to check and says nothing about the "
            "ways nobody enumerated, so completeness is a judgement and no script may be the "
            "thing that lifts the null. Owner, 2026-08-26.",
        critical=True,
        oracle="tests/test_requirements_status.py",
    ),
]


def by_id(mid: str) -> Mutant:
    for m in CATALOGUE:
        if m.id == mid:
            return m
    raise KeyError(f"unknown mutant {mid!r}; have {[m.id for m in CATALOGUE]}")
