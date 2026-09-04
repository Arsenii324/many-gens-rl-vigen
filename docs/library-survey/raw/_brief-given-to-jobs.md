# Context for the library-implementation sweep

## What the project is

`~/build-projs/ccm-intro/projects/many-gens-rl-vigen` compares **twelve** visual-RL baselines on
**robosuite** manipulation tasks (Door, Lift) through the **RL-ViGen** generalization benchmark,
measuring generalization to held-out visual scenes.

The twelve, with their action-distribution family:

| baseline | family | origin |
|---|---|---|
| drqv2, svea, sgqn, curl, drq | DrQv2 tanh-mean + TruncatedNormal | RL-ViGen's own tree |
| rad, soda | SAC squashed Gaussian | nicklashansen/dmcontrol-generalization-benchmark |
| alda | SAC squashed Gaussian | ALDA |
| ppg | unsquashed Gaussian + env clip | openai/phasic-policy-gradient |
| idaac | unsquashed Gaussian + env clip | rraileanu/idaac |
| ibac_sni | unsquashed Gaussian + env clip | IBAC-SNI |
| ctrl | unsquashed Gaussian + env clip (JAX/tfp MVNDiag) | CTRL |

Four of these (ppg, idaac, ibac_sni, ctrl) are **Procgen** algorithms, i.e. natively DISCRETE.
Running them on robosuite required authoring a continuous head, because their upstreams have
none. This project cares a lot about which parts are the authors' and which are ours.

## The methodological stance (this is the thing to compare against)

- **The null is the original repository, cloned, running its own `train.py`.** Six separate
  clones, each with its own venv-visible path, its own entry point.
- **Duplication across baselines is free. Any JOIN is work that carries a burden of proof** —
  merging two baselines' training loops, or sharing a replay buffer, or a common trainer, must
  be justified because it can silently change whose numbers you are reporting.
- Changes to clones are minimal and are stated exhaustively by `git diff` against a `PRISTINE:`
  first commit.

## What we want from you

We want to know **what the established PyTorch/JAX RL libraries do**, so we can (a) borrow
anything genuinely useful, (b) know where our practice differs from the field's, and (c) cite
prior art for the design decisions we had to make alone.

Bias toward INCLUDING information. The requester's words: *"They rather add extra information
than miss some."* A relevant-but-tangential fact is worth reporting; a missed one is not.

## Rules that make the answer usable

1. **Cite where you looked.** File path in the repo, doc URL, or issue number. A claim with no
   locator is worth much less to us than one with.
2. **If you could not verify something, write `UNVERIFIED` and say what you tried.** Do not fill
   a gap with a plausible guess. We would rather have a hole we know about.
3. Distinguish **what the library implements** from **what it documents** from **what it
   benchmarks with published numbers**. These three diverge constantly and the divergence is
   itself informative.
4. Quote exact hyperparameters, exact function/class names, exact default values where you can.
