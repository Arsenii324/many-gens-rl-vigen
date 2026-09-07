Yes. For the Door benchmark, I would use `frame_stack = 3` for all 12.

But the reason is slightly subtler than “none of the originals deliberately omit it.” Two originals—IBAC-SNI and CTRL—do deliberately use one frame. Crucially, both compensate by explicitly painting velocity information into that single image. On RGB-only Door, that compensation is absent. So I do not see a source-fidelity argument for preserving their one-frame setting on Door.

Here is the source-level picture:

| Baseline | Original/reference observation history | Source evidence | Door recommendation |
|---|---:|---|---:|
| PPG | 1 in original Procgen; **3 in published DMC adaptation** | OpenAI PPG simply extracts one RGB Procgen observation.  Raileanu/Fergus' published continuous-control PPG experiment explicitly uses 3 stacked frames.  | **3** |
| RAD | **3** | Official DMC reproduction command has `--frame_stack 3`.  | **3** |
| IBAC-SNI | **1 deliberately, because velocity is painted** | Authors: “No frame stack is necessary if `PAINT_VEL_INFO = 1`”; stack defaults 1, while standard CoinRun defaults velocity painting on.  | **3** |
| DrQ | **3** | Official config: `frame_stack: 3`.  | **3** |
| DrQ-v2 | **3** | Official config: `frame_stack: 3`.  | **3** |
| CURL | **3** | Official DMC command: `--frame_stack 3`.  | **3** |
| IDAAC | 1 in Procgen; **3 in authors' DMC experiment** | Original Procgen wrapper exposes `(3,64,64)`, i.e. one RGB frame.  Their published continuous-control experiments explicitly use 3 stacked frames.  | **3** |
| ALDA | **3** | Official paper-result spec: `frame_stack: 3`.  | **3** |
| SVEA | **3** | Official DMCGB uses `frame_stack=3`; DMCGB identifies SVEA as an official implementation.  | **3** |
| CTRL | **1 deliberately, with velocity painted** | Its environment passes `paint_vel_info=True` to Procgen and declares a single `(3,64,64)` RGB observation.  | **3** |
| SGQN | **3** | Official DMC implementation defaults `frame_stack=3`.  | **3** |
| SODA | **3** | Official DMCGB defaults to 3 and identifies SODA as an official implementation.  | **3** |

The key source evidence is IBAC-SNI. Its authors literally write:

> “No frame stack is necessary if `PAINT_VEL_INFO = 1`”

and configure standard CoinRun so `paint_vel_info` defaults on.  That is unusually strong evidence about intent. IBAC-SNI did not choose one frame because its algorithm requires static observations or because temporal history is undesirable. It chose one frame because the environment injected the missing dynamical information directly into the pixels. It also defaults its LSTM off, so recurrence is not providing that information instead. 

CTRL is almost the same story. Its custom Procgen wrapper explicitly constructs the environment with:

```python
paint_vel_info=True
```

while exposing only:

```python
Box(shape=(3, 64, 64), ...)
```

i.e. one image. 

So for both IBAC-SNI and CTRL, **one RGB Door frame is arguably less faithful to the original information set than three RGB Door frames are**.

### Why this matters on Door

A single rendered image tells you approximately configuration—door angle, gripper pose, arm pose—but generally does not uniquely determine velocities. The same image can occur while the arm or door is moving in different directions.

Three observations,

\[
(o_{t-2},o_{t-1},o_t),
\]

give the CNN enough information to infer finite-difference motion cues. They do not make pixels perfectly Markov, but they restore the kind of short-term dynamics information that DMC pixel-control methods conventionally obtain through stacking.

This is exactly why the IDAAC authors used three frames when they moved their Procgen algorithms—including **PPG and IDAAC themselves**—to continuous control. Their supplement says:

> “We also use 3 stacked frames as observations.”

and applies that DMC setup to PPO, PPG, UCB-DrAC, DAAC, and IDAAC. 

That is particularly persuasive for your adaptations. You are not inventing a new PPG/IDAAC convention; you are following their published continuous-control precedent.

### The PPG nuance

Canonical OpenAI PPG does use one Procgen RGB frame: its environment wrapper simply extracts `"rgb"` and returns it.  Modern Procgen itself defaults `paint_vel_info=False`. 

So PPG is the one case where you cannot say “the original single frame already contained explicit velocity.”

But you still have stronger task-domain precedent: the published DMC PPG comparator uses three frames. For a Door continuous-control adaptation, I would choose that over reproducing the Procgen observation convention.

### I see no algorithmic reason to preserve one frame

This is the decisive point.

I found no baseline among the twelve whose defining method:

- assumes observations must be single-frame;
- has an auxiliary objective whose intended semantics require one frame;
- deliberately removes history to enforce partial observability;
- or uses one frame because the authors concluded stacking harmed the method.

The single-frame cases arise from **environment conventions**, not methodological commitments.

Thus I would classify `frame_stack=3` as a common Door observation-interface decision, not as an algorithm-changing regularizer.

For IBAC-SNI and CTRL I would document the adaptation specifically as:

> Original Procgen implementation uses a single RGB frame with explicit velocity painted into the observation. Door does not provide the corresponding pixel velocity cue, so three consecutive RGB observations are stacked to provide short-horizon motion information.

That is a strong justification.

### One thing I would not do

Do not independently augment the three temporal frames with different random spatial transforms.

If an augmentation method sees a 9-channel stack, a spatial crop/shift should normally use the **same spatial transformation across all three constituent frames**. Otherwise you manufacture apparent motion:

\[
\text{real motion} + \text{independent augmentation jitter},
\]

which damages precisely the velocity information you introduced the stack to provide.

The standard pixel-control arrangement—stack first, then apply a common spatial transform to the stacked tensor—is the safer semantics.

Likewise, at episode reset the stack should be initialized by repeating the reset observation:

\[
(o_0,o_0,o_0),
\]

rather than including stale images from the previous episode.

### One remaining caveat

Three consecutive Door frames at `action_repeat=1` do not span the same physical time interval as three DMC frames when DMC uses action repeat 4 or 8. For example, DrQ-v2's official configuration uses frame stack 3 and action repeat 2,  while the IDAAC continuous-control experiments use task-dependent repeats of 4 or 8 alongside the three-frame stack. 

I would **not** compensate by inventing a temporal-stride stack. That introduces another nonstandard variable. Three consecutive Door observations is the clean common choice.

So my production recommendation is:

\[
\boxed{\texttt{frame\_stack = 3 for all twelve}}
\]

I would regard that as both a better same-axes benchmark and, for **IBAC-SNI/CTRL specifically**, arguably a better *information-fidelity* adaptation than their current one-frame Door versions. The only provenance note needed is that canonical Procgen PPG/IDAAC/IBAC-SNI/CTRL were single-frame, with IBAC-SNI and CTRL explicitly replacing temporal history with painted velocity.

---

Yes. A **3-frame-stack IMPALA-CNN is completely standard/valid**, including for RL. It is usually not considered a separate “IMPALA-CNN version”; you simply stack frames along the channel dimension before the encoder. For RGB:

`1 frame → [3, H, W]`  
`3 frames → [9, H, W]`

so the first IMPALA convolution takes `in_channels=9`; the rest of the architecture is unchanged. There are concrete RL implementations doing exactly this—for example, the 2026 ReFORM implementation runs visual RL with `--encoder impala_small --frame_stack 3`. 

IMPALA-CNN itself is very much an RL architecture. It was designed as a deeper residual image encoder for deep RL: the usual version has three convolutional sequences with pooling and residual blocks. It remains a strong visual-RL backbone, particularly when representation capacity/generalization matters. Recent work still describes it as outperforming older shallow CNN architectures, although newer variants such as Impoola-CNN improve it further by changing the final spatial aggregation. 

For a feed-forward agent, frame stacking is often useful because a single image does not tell you motion direction or velocity. Three frames let the CNN infer some short-term dynamics. But it is not universally better: it increases input/replay memory and some compute, and on slow robotic-control tasks there can be substantial redundancy.

For **RL-ViGen specifically**, the important answer is:

**RL-ViGen uses frame stack = 3, but it does not use IMPALA-CNN as its standard encoder.** The paper lists `84×84` observations and `Frame stack = 3` as common hyperparameters. The repository also sets `frame_stack: 3` globally. 

For the Robosuite environments, the implementation literally concatenates the frames along the channel dimension. Its wrapper changes the observation channel dimension to `C × num_frames` and calls `np.concatenate(..., axis=0)`. Thus Robosuite Door with RGB and stack 3 is effectively a **9×84×84 observation**. 

But the default RL-ViGen config instantiates:

`algos.drqv2.DrQV2Agent`

rather than an IMPALA agent/encoder.  The DrQ-v2-style encoder is much shallower than IMPALA: essentially four 3×3 conv layers rather than the IMPALA residual ConvSequence architecture. The corresponding VRL3 code explicitly calls its four-convolution `Stage3ShallowEncoder` “the encoder architecture used in DrQv2.” 

There is one subtlety with **“Door” in RL-ViGen**: there are actually two Door settings.

| RL-ViGen task | Base environment | Frames | Encoder/base |
|---|---|---:|---|
| Door | **Robosuite** table-top manipulation | 3 | DrQ-v2-style visual RL; **not IMPALA-CNN** |
| Door | **Adroit** dexterous hand manipulation | 3 in RL-ViGen/paper setup | VRL3, whose online stage is DrQ-v2-based; **not IMPALA-CNN** |

For Adroit Door specifically, RL-ViGen says Door/Hammer/Pen are run using **VRL3 as the base algorithm**, because plain DrQ/DrQ-v2 struggle on those tasks. It also says VRL3's update is based on DrQ-v2 and that RL-ViGen uses only VRL3's stage 3 for these comparisons. 

An interesting detail relevant to your first question: the VRL3 authors say that most experiments in their paper used **`frame_stack=3`**, but they later found they could reduce it to **1 with the same performance**, while saving memory and computation. So for Adroit Door in particular, three frames are demonstrably not essential in that implementation. 

So if your goal is **reproducing RL-ViGen Door**, I would use the shallow DrQ-v2/VRL3 encoder + stack 3, rather than IMPALA-CNN. If your goal is instead **building a stronger visual encoder for a Door-like RL task**, `IMPALA-CNN + frame_stack=3` is a sensible experiment and architecturally straightforward, but it is a different encoder from the RL-ViGen baseline. I would compare at least `DrQ-v2 CNN, stack=3` versus `IMPALA-small, stack=3`; for Adroit I would additionally test stack 1 because of the VRL3 result.
