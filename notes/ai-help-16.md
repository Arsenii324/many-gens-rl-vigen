For the standard RL-ViGen Robosuite Door task, use frame_stack = 3 for both IDAAC and PPG. I would make 3-frame stacking the primary setting in your reported experiments, not an optional tweak.

The evidence is unusually consistent once the environment is given priority over the algorithms’ original Procgen settings:

Evidence	Frame stack	Relevance to your experiment
Original IDAAC on Procgen	1 frame / no stacking	Low–medium
Original PPG on Procgen	1 frame / no stacking	Low–medium
IDAAC paper’s continuous-control experiments with visual distractors, including PPG baseline	3	High
RL-ViGen benchmark common configuration	3	Highest
RL-ViGen Robosuite implementation	3 by default	Highest

RL-ViGen’s own supplementary hyperparameter table explicitly specifies frame stack = 3, 84×84 inputs, and, specifically for Robosuite, action repeat = 1.   This should normally take precedence because frame stacking is substantially an environment/observation-design choice, rather than an intrinsic defining property of IDAAC or PPG.

There is also a particularly strong piece of evidence from the IDAAC authors themselves. For their pixel-based DeepMind Control experiments with natural and synthetic distractors—a much closer analogue to visual robotic manipulation than Procgen—they state that they use 3 stacked frames. Importantly, those experiments include both IDAAC and PPG, and the authors tune PPG and IDAAC in that common setup. raileanu21a-supp.pdf That is probably the single most useful precedent for your exact question.

This is more relevant than the fact that both algorithms originally used no frame stacking on Procgen. IDAAC’s Procgen hyperparameter table says both LSTM and frame stacking were disabled. raileanu21a-supp.pdf PPG likewise reports no LSTM and no frame stack for its original Procgen experiments. cobbe21a-supp.pdf Those settings establish what the algorithms used on Procgen, not that frame stacking should universally be disabled.

There is a task-specific reason that 3 frames make more sense for Door. RL-ViGen’s Robosuite wrapper extracts the RGB observation for the agent, rather than supplying the full simulator state.  From one RGB frame, a feed-forward policy cannot directly tell quantities such as gripper/hand velocity, door motion direction, whether contact has just occurred, or whether the handle is moving. A short visual history provides some of that dynamic information. Neither the standard IDAAC configuration nor the standard feed-forward PPG configuration gives you recurrent memory to recover it otherwise.

RL-ViGen’s implementation also actually concatenates the stored frames along the observation’s channel dimension.  Thus, for ordinary RGB observations, frame_stack=3 means that your CNN should effectively accept 9 channels, e.g. [RGB(t−2), RGB(t−1), RGB(t)], rather than 3 channels. The repository’s common configuration itself sets frame_stack: 3, and the Robosuite wrapper’s constructor defaults to 3.

So I would configure the experiment approximately as:

Environment:       RL-ViGen Robosuite Door
observation:       84 × 84 RGB
frame_stack:       3
effective channels: 9
action_repeat:     1   # RL-ViGen Robosuite benchmark setting
IDAAC:
    policy/advantage network receives same 3-frame stack
    separate value network receives same 3-frame stack
    no LSTM required
PPG:
    policy network receives same 3-frame stack
    value network receives same 3-frame stack
    auxiliary-value path receives same 3-frame stack
    no LSTM required

I would not use different stack sizes for IDAAC and PPG. Doing so changes the information available to each agent and makes the comparison less clean. Give both exactly the same 3-frame observation.

I also would not start with 4 frames. Three is supported directly by both RL-ViGen and the closest IDAAC/PPG continuous-control experiment; a fourth frame increases input bandwidth and CNN cost by another 33% while giving you no source-backed reason to expect an improvement. In visual-generalization experiments, additional frames can also reproduce more nuisance information from moving lights/video backgrounds. Three is a reasonable balance between dynamics information and nuisance/compute.

I would, however, run frame_stack ∈ {1, 3} as one controlled ablation if your compute budget permits it. Make 3 the preregistered/default result and 1 the ablation. That ablation answers a useful scientific question: whether temporal information is actually needed on Door, or whether the extra stacked visual history primarily adds distractor information. I would not tune 1/2/3/4 independently for IDAAC and PPG unless frame stacking itself is part of the study.

One implementation warning for PPG: CleanRL’s provided PPG implementation is a Procgen implementation for 64×64 RGB observations and a discrete action space.   RL-ViGen Robosuite Door has continuous actions, so that implementation is not a direct drop-in—you will need the appropriate continuous policy distribution/head and must ensure your CNN handles the 9-channel stacked observation. This does not change the recommendation of 3 frames.

There is one ambiguity worth flagging. RL-ViGen contains both manipulation and dexterous-manipulation domains, and the repository puts the Adroit configuration on its separate ViGen-adroit branch.   If by “Door” you specifically mean Adroit/dexterous-hand Door rather than Robosuite Door, the answer is slightly less absolute: 3 is still the canonical/reproducible starting point, but a 1-frame efficiency ablation becomes more compelling. For the normal main-branch Robosuite Door, my recommendation is unambiguous:

IDAAC: frame_stack = 3
PPG: frame_stack = 3
Primary comparison: same stack for both.
Optional ablation: 1 vs. 3; do not replace 3 with 1 for the main benchmark result.
