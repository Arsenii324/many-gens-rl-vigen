# IDAAC's "2048 steps, 1 process" was chosen under action repeat 4-8; Door runs action repeat 1

**2026-09-09.** A35/Q55 fixed IDAAC-C2's constants directly from `ext/idaac/raileanu21a-supp.pdf`
§E, which is the right method and produced the right numbers. This note records a **condition**
attached to those numbers that the transfer does not carry, found by reading the surrounding
paragraph rather than the quoted sentence.

## What the source actually says

> "**In line with standard practice for this benchmark**, we use **8 action repeats for Cartpole
> Swingup and 4 for Cartpole Balance and Ball In Cup**. We also use 3 stacked frames as
> observations. To find the best hyperparameters, we ran a grid search over the learning rate in
> [0.0001, 0.0003, 0.0007, 0.001], the number of minibatches in [32, 8, 16, 64], the entropy
> coefficient in [0.0, 0.01, 0.001, 0.0001], and the number of PPO epochs per update in
> [3, 5, 10, 20]. We found 10 ppo epochs, 0.0 entropy coefficient, 0.0003 learning rate, and 32
> minibatches to work best across these environments. We use γ = 0.99, λ = 0.95 ..., **2048 steps,
> 1 process**, value loss coefficient 0.5, and **linear rate decay over 1 million environment
> steps**."

Two things this settles, and one it opens.

**Settled: `1 process` was never tuned.** The grid searched learning rate, minibatches, entropy and
epochs. `2048 steps, 1 process` is listed beside γ and λ as a fixed convention — and it is the
canonical PPO-for-MuJoCo setting (2048-timestep batches, a single actor) from the original PPO
paper. Procgen needed 64 environments because it is a fast vectorised C++ environment with
procedural level diversity; single-environment is the historical continuous-control convention.
So the answer to "why 1 process on a physical environment" is **inherited practice, not a measured
optimum for physics**.

**Settled: adopting it is still correct as fidelity.** The alternative is inventing a value the
authors did not use, which A35 explicitly declined to do.

## The condition that does not transfer

Their DMC tasks ran at **action repeat 4-8**. Our Door runs at **action repeat 1**
(`datasphere/native/families.json:52`, "At the declared 600k-frame, **action_repeat=1** budget").

| | authors' DMC | our Door |
|---|---|---|
| agent steps per update | 2048 | 2048 |
| action repeat | 4-8 | **1** |
| simulator ticks per update | 8192-16384 | **2048** |
| renders per update | 2048 | 2048 |
| total budget | 1M agent steps (= 4-8M ticks) | 600k agent steps (= 600k ticks) |

**A rollout covers 4-8x less simulated time than theirs did**, at the same nominal 2048 steps. The
LR decay horizon inherits the same distortion: "linear rate decay over 1 million environment steps"
meant 4-8M ticks for them.

**It does NOT change wall clock much.** Rendering dominates our cost and a render happens once per
*agent* step, so 2048 steps is 2048 EGL renders either way; only the cheap physics ticks differ.
This is a question about what an update *represents*, not about throughput.

## What is not claimed here

That anything should change. Door is a manipulation task with a different horizon and reward
structure from Cartpole, and whether action repeat should match is a substantive question about the
task, not a transcription error — RL-ViGen's own Door configuration is the other authority in play.
The point is narrower: **the number 2048 was measured under a condition, that condition is 4-8x
different here, and nothing in the decision record notes it.** Now something does.

Compare `notes/DECISION-SHEET.md` A40 (frame stack) and the render-size item in the plan's Phase 5:
same shape of question — *under what condition did the authors choose this, and does that condition
hold on Door?* — which is the only method that has repeatedly found real defects in this project.
