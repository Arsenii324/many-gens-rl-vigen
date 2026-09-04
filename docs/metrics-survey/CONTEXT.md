# Why this survey exists

A sibling project, `~/build-projs/ccm-intro/projects/many-gens-rl-vigen`, runs twelve visual
generalization RL baselines on the RL-ViGen robosuite benchmark. It currently reports only two
quantities per baseline: episode return, and a task-defined binary success rate. That is thin.

The other projects in this workspace have, over time, built much richer metric suites. The goal
is to recover ALL of them so the RL-ViGen project can decide which to adopt — including metrics
that only make sense for a family of algorithms (on-policy vs off-policy, PPO-specific
diagnostics like approx-KL / clip fraction / explained variance, representation-quality probes,
generalization-gap constructions, evaluation-protocol statistics such as confidence intervals or
seed aggregation).

# What matters in the answer

- The metric's NAME as used in the code.
- Its DEFINITION: the formula or the actual computing expression, not a paraphrase.
- WHERE it is computed: file path and line number.
- WHAT IT IS FOR: what question it answers, and for which algorithm family it is meaningful.
- Any CAVEAT the code or its comments state — a metric that is documented as misleading, biased,
  or only valid under some condition is the most valuable kind of finding here.

Report metrics that are computed but never logged, and metrics that are logged but never used,
separately and explicitly — both are real findings.
