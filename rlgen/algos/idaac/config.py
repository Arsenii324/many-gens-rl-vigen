"""Single source of truth for every constant.

Rule for this file: no number without a source tag. Sources are one of

  [E]     IDAAC paper, Appendix E (DeepMind Control, continuous) -- read from the PDF and
          quoted in FINDINGS.md. This is the continuous-control column and it is NOT the
          Procgen column; see the table below.
  [T3]    IDAAC paper, Table 3 (Procgen hyperparameters)
  [RLV]   RL-ViGen: a config file in this tree, or its NeurIPS'23 supplementary
  [IK]    ikostrikov/pytorch-a2c-ppo-acktr-gail, the base IDAAC forked
  [F:id]  a finding in FINDINGS.md
  [OURS]  not in any source; chosen here, with the reason stated

Procgen vs DMC, for the values that differ (all [E], all verified):
    lr            5e-4  -> 3e-4        entropy      0.01  -> 0.0
    minibatches      8  -> 32          gamma       0.999  -> 0.99
    rollout    64x256   -> 1x2048      E_V             9  -> 9
    N_pi             1  -> 32          alpha_a      0.25  -> 0.1
    alpha_i      0.001  -> 0.1   (100x more weight on the adversarial term)
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Config:
    # ---- task ---------------------------------------------------------------
    task: str = "Lift"                  # [F:I3] Lift is the scientific target; Door is the
                                        #        pipeline control -- Door-easy retains ~94%
                                        #        of training performance for every baseline,
                                        #        so there is no generalization gap to close.
    train_mode: str = "train"           # [RLV] robo_config.yaml: no randomization at all
    eval_mode: str = "eval-easy"        # [F:D1] what "Door-easy"/"Lift-easy" means
    seed: int = 0

    # ---- observation / environment ------------------------------------------
    frame_stack: int = 3                # [RLV] robo_config + supplementary
    image_size: int = 84                # [RLV] robo_config.yaml image_height/width
    action_repeat: int = 1              # [F:D5] robosuite uses 1; cfgs/config.yaml defaults
                                        #        to 2 and no task config overrides it, so this
                                        #        must always be passed explicitly.
    horizon: int = 500                  # [RLV] robo_config.yaml task_def.horizon
    gamma: float = 0.99                 # [E] and [RLV]; NOT Procgen's 0.999

    # ---- vectorization ------------------------------------------------------
    # CORRECTED 2026-08-13. `rlgen/trainer_onpolicy.py` runs ONE robosuite environment, always
    # (`RolloutStorage(num_steps, 1, ...)` -- the "1" is a literal, not `cfg.num_envs`; see that
    # file's own docstring: "This loop therefore runs num_envs=1 ... the seam is ready for that
    # and it is not done here"). `num_envs` below is inherited from the sibling gen-rebuttal
    # project, which DOES vectorize with `SubprocVecEnv` -- there it was live and load-bearing.
    # Here it is READ NOWHERE (`grep -rn cfg.num_envs rlgen/` finds only this file), so it drives
    # `rollout_size`/`minibatch_size`/`total_updates` below to values 8x the real ones -- cosmetic
    # only, since the code that actually splits a rollout into minibatches
    # (`storage.feed_forward_generator`, `storage.py:112`) computes its batch size from the REAL
    # stored tensor (`T * N` with N hardcoded to 1), not from these properties. Set to 1 so the
    # dataclass's own math matches what runs. If real vectorization is ever wired up, un-dead this.
    num_envs: int = 1
    num_steps: int = 2048               # [E] "1 process x 2048" (Appendix E's own continuous-
                                        # control config, PLAN.md sec.3.1). Previously 256 here
                                        # with configs/vigen.yaml's `idaac:` block overriding to
                                        # 2048 at every real launch -- so the dataclass default
                                        # never matched a real run. Corrected to match.
    total_frames: int = 1_000_000       # [OURS] placeholder -- see Q2. The three candidate
                                        # budgets (6e5/8e5, 1.1M/3.1M, 12.5M) are unresolved;
                                        # 1e6 matches the DeGuV reproduction we compare against.

    # ---- optimization -------------------------------------------------------
    lr: float = 3e-4                    # [E] DMC grid search winner
    linear_lr_decay: bool = True        # [E] linear decay over training
    gae_lambda: float = 0.95            # [E] and [T3]
    clip_param: float = 0.2             # [T3]
    max_grad_norm: float = 0.5          # [IK] default
    num_mini_batch: int = 32            # [E] 32 minibatches of a 2048 rollout = 64 samples each.
                                        # Our rollout is genuinely 2048 -- one environment run for
                                        # num_steps=2048 sequential steps, not num_envs x num_steps
                                        # (see the note above; num_envs is dead here) -- so this
                                        # matches Appendix E on both the count and the size with no
                                        # interpretation needed. Verified against the real storage
                                        # tensor, not the (now-corrected) cfg properties:
                                        # `storage.feed_forward_generator` computes its minibatch
                                        # size as `(T*N) // num_mini_batch` from the ACTUAL stored
                                        # T=2048, N=1, giving 64 -- matches Appendix E regardless
                                        # of whether the cfg properties above were ever wrong.
                                        # Was 8, whose comment claimed to "match the minibatch
                                        # size, not the count": at 8 minibatches the size is 256,
                                        # so it matched neither. The launch script had been
                                        # overriding to 32, which meant the DEFAULTS did not
                                        # reproduce our own runs (BUGHUNT Pass B).
    entropy_coef: float = 0.0           # [E] DMC winner. [F:R3] Procgen's 0.01 is wrong for a
                                        # 7-D Gaussian: entropy sums over dims and is unbounded
                                        # above, so maximizing it only inflates sigma.
    kl_early_stop: bool = True          # [OURS] [F:R16] stop the epoch loop once the policy has
                                        # left the trust region. Measured without it, at E_pi=10
                                        # and 32 minibatches (= 320 policy steps per rollout):
                                        # clipfrac climbed 0.12 -> 0.56 over 10 updates and
                                        # ratio_max hit 10.8, i.e. most samples contributed no
                                        # gradient and the update was far off-policy. Standard
                                        # PPO practice; set False to reproduce [E] literally.
    target_kl: float = 0.02             # [OURS, DERIVED] = clip_param**2 / 2, not a guess.
                                        # For small KL the chi-square divergence gives
                                        # E[(ratio-1)^2] ~ 2*KL, so RMS |ratio-1| ~ sqrt(2*KL).
                                        # Setting that equal to clip_param puts the typical
                                        # sample exactly at the clip boundary:
                                        #   KL = clip_param^2 / 2 = 0.2^2/2 = 0.02.
                                        # This ties the two hyperparameters together instead of
                                        # letting them contradict each other.
    value_loss_coef: float = 0.5        # [E]
    clip_value_loss: bool = True        # [IK] use_clipped_value_loss=True
    # ---- fixes that change LEARNING DYNAMICS ---------------------------------
    # fix_value_grad_scale defaults False so the defaults still reproduce the seed-0 runs exactly.
    fix_value_grad_scale: bool = False   # [F:R24] scale value grads AFTER backward, BEFORE the
                                        # clip, so the effective cap is max_grad_norm (0.5) rather
                                        # than max_grad_norm/value_loss_coef (1.0)
    stagger_episode_phase: bool = False  # [F:R18] INERT HERE, kept only so the cross-reference is
                                        # not lost. R18 is about MULTIPLE parallel workers all
                                        # resetting on the same step, which biases rollout
                                        # statistics with a period equal to their count. With
                                        # `num_envs` genuinely 1 (see above) there is only one
                                        # worker, so there is no cross-worker phase to align and
                                        # nothing for this flag to do -- confirmed unread by any
                                        # code in this package (`grep -rn stagger_episode_phase
                                        # rlgen/`). Flipping it changes nothing. If real
                                        # vectorization is ever wired up, this becomes live again.

    # ---- DAAC / IDAAC -------------------------------------------------------
    algo: str = "idaac"                 # "ppo" | "daac" | "idaac"
    epochs_policy: int = 10             # E_pi. [E] "10 ppo epochs ... used for all the
                                        # methods" on DMC. [F:Q3] the DAAC/IDAAC-specific
                                        # search reports only E_V/N_pi/alpha, so 1 (Procgen's
                                        # winner) is also defensible. Sweep, do not assume.
    epochs_value: int = 9               # E_V. [E] and [T3] agree on 9.
    value_update_every: int = 1         # N_pi. [E] DMC = 32, [T3] Procgen = 1.
                                        # [F:R9] we default to 1: the rollout buffer is
                                        # overwritten every update, so N_pi=32 means the value
                                        # net never sees 31 of every 32 rollouts. Sweep {1,8,32}.
    adv_loss_coef: float = 0.1          # alpha_a. [E] DMC (Procgen 0.25)
    inv_loss_coef: float = 0.1          # alpha_i. [E] DMC (Procgen 0.001 -- 100x smaller)
    disc_batch_size: int = 256          # [OURS] order-pair anchors per minibatch step
    disc_hidden: int = 0                # [IDAAC] 0 = LinearOrderClassifier, which is IDAAC's
                                        # DEFAULT: `--use_nonlinear_clf` is store_true and
                                        # defaults False (arguments.py:142-145), so train.py:80
                                        # builds `Linear(2*emb, 2) -> Softmax` -- no hidden layer.
                                        # >0 selects the opt-in nonlinear variant at that width;
                                        # IDAAC's `clf_hidden_size` default is 4. [F:R21] we had
                                        # 256, i.e. 64x the opt-in width plus a nonlinearity the
                                        # default lacks, which makes the adversary far stronger
                                        # than the one the paper's mechanism is posed against.

    # ---- model --------------------------------------------------------------
    hidden_dim: int = 256               # [T3] IMPALA-ResNet output width
    init_log_std: float = -1.0          # [OURS] DEVIATION from [IK], which uses AddBias(zeros)
                                        # -> sigma=1.0 unsquashed. [F:R2] robosuite actions live
                                        # in [-1,1]; sigma=1 puts most initial samples outside the
                                        # box, where the env clips them but the log-prob is
                                        # computed on the unclipped action. exp(-1)=0.37.
    mean_head_gain: float = 0.01        # [OURS] mirrors [IK]'s Categorical idiom so the initial
                                        # policy starts near zero action rather than saturated.

    # ---- reward normalization -----------------------------------------------
    normalize_reward: bool = True       # [T3] "reward normalization: yes"
    reward_clip: float = 10.0           # [IK] VecNormalize default
    # [F:R5] the normalizer must never touch the number reported as an episode return.

    # ---- diagnostics ---------------------------------------------------------
    # Tiered cadence. Cheap health detectors run every update -- they are microseconds on
    # tensors already in memory. The expensive ones run densely at the start, where wiring
    # bugs actually show, then sparsely. 0 disables.
    diag_every: int = 20                # [OURS] interval for corr(A,t) and per-module grad
                                        # norms after the warmup window below
    diag_dense_updates: int = 5         # [OURS] run them every update for this many first
    # corr(A,t) costs one forward pass over the whole rollout; grad norms walk every parameter
    # of five modules. Both are diagnostics, never load-bearing for learning.

    # ---- logging / checkpointing --------------------------------------------
    eval_frequency: int = 100_000       # frames between checkpoints. The supervisor's explicit
                                        # request: every checkpoint must be re-evaluable offline.
    eval_episodes: int = 10             # [RLV] cfgs/config.yaml num_eval_episodes
    log_every_updates: int = 1
    run_root: str = "runs"
    run_name: str = ""
    device: str = "cuda"
    use_wandb: bool = True
    wandb_project: str = "vigen-idaac"
    wandb_entity: str = "vaarsenii-hse-university"

    env_kwargs: dict = field(default_factory=dict)

    # -------------------------------------------------------------------------
    @property
    def rollout_size(self) -> int:
        return self.num_envs * self.num_steps

    @property
    def mini_batch_size(self) -> int:
        return self.rollout_size // self.num_mini_batch

    @property
    def num_updates(self) -> int:
        return self.total_frames // (self.rollout_size * self.action_repeat)

    def validate(self) -> None:
        assert self.algo in ("ppo", "daac", "idaac"), self.algo
        assert self.rollout_size % self.num_mini_batch == 0, (
            f"rollout {self.rollout_size} not divisible by {self.num_mini_batch} minibatches")
        assert self.num_updates >= 1, "total_frames too small for one update"
        assert 0.0 < self.gamma <= 1.0 and 0.0 <= self.gae_lambda <= 1.0
        # Deliberately absent: any floor on rollout_size. [F:R10] IDAAC's own continuous-control
        # runs used 2048x1, so a "rollout >= 8192" rule would reject the paper's configuration.
        if self.algo == "ppo":
            assert self.value_update_every == 1, "plain PPO has no separate value schedule"

    def to_dict(self) -> dict:
        return asdict(self)
