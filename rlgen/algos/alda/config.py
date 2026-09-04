"""Single source of truth for every ALDA constant.

Same rule as `vigen_idaac/config.py`: no number without a source tag.

  [A]     ALDA paper, arXiv 2410.07441v2 == the ICML'25 camera-ready (verified in the ext/
          traces: normalised similarity 0.9997 against the OpenReview PDF, difference is
          running heads). Appendix A.7.3 Table 1 unless another section is named.
  [AC]    ALDA_Official, github.com/SumeetBatra/ALDA_Official -- the single squashed commit of
          2025-05-27, MIT. THE REFERENCE IMPLEMENTATION. Where it disagrees with [A] we follow
          [AC] and say so, because [AC] is what produced the published numbers.
  [RLV]   RL-ViGen: a config file in this tree, or its NeurIPS'23 supplementary.
  [F:id]  a finding in FINDINGS.md (IDAAC port) or ALDA.md (this port).
  [OURS]  not in any source; chosen here, with the reason stated.

WHERE [A] AND [AC] DISAGREE -- read ALDA.md §4 before changing any of these:

  loss weights      [A] writes the objective as L_commit + L_reconstruct with no coefficients.
                    [AC] applies commitment 0.01 and BCE 1.0. We follow [AC].
  reconstruction    [A] writes `log g_phi(o|z_d)`. [AC] uses binary cross-entropy with logits
                    against the [0,1]-scaled image. We follow [AC].
  which frames      [A] "fold k into the batch dimension and encode/decode batches of single
                    images". [AC]'s autoencoder update uses `obs[:, -3:]` -- the NEWEST frame
                    only. All k frames are folded only on the RL path. We follow [AC].
  codebook          [A] calls the codebook "a set of task-optimized memories". [AC] never
                    applies a gradient to it -- see `train_codebook` below. We follow [AC].
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class AldaConfig:
    # ---- task ---------------------------------------------------------------
    task: str = "Door"
    train_mode: str = "train"           # [RLV] robo_config.yaml: no randomisation at all
    eval_mode: str = "eval-easy"        # [F:D1] what "Door-easy"/"Lift-easy" means
    seed: int = 0

    # ---- observation / environment ------------------------------------------
    # These MUST match the IDAAC runs exactly or the comparison is not frame-matched and not
    # protocol-matched. Every one of them is [RLV], i.e. the benchmark's, not either paper's.
    frame_stack: int = 3                # [A] and [RLV] agree on 3
    image_size: int = 84                # [RLV] robo_config.yaml image_height/width.
                                        # DEVIATION from [A]'s 64x64. Not negotiable: robo_make
                                        # takes no size argument, so 84 is what the benchmark
                                        # renders. nets.py mirrors the decoder to whatever the
                                        # encoder produced, and at 64 it degenerates to [AC]'s
                                        # exact architecture -- pinned by a test.
    action_repeat: int = 1              # [F:D5] robosuite uses 1. [A] uses 4 (2 for finger spin)
                                        # on DMC. Held at 1 so an ALDA frame and an IDAAC frame
                                        # are the same unit of environment interaction.
    horizon: int = 500                  # [RLV] robo_config.yaml task_def.horizon
    discount: float = 0.99              # [A] and [RLV]

    # Reward normalisation is OFF, unlike the IDAAC port.
    # [AC] trains on raw environment rewards, and SAC's temperature is auto-tuned against the
    # reward scale -- normalising by a running return std would move the target entropy's
    # effective weight under the agent during training. IDAAC normalises because [T3] says to.
    normalize_reward: bool = False      # [AC]
    reward_clip: float = 10.0           # [OURS] no source: neither [A] nor [RLV] clips reward.
                                        # Inert while normalize_reward is False (which is [AC]'s
                                        # setting and ours), and train.py asserts rew == raw every
                                        # step, so it cannot silently take effect.
    stagger_episode_phase: bool = False # [OURS] an on-policy device (IDAAC F:R18). Off-policy
                                        # sampling is uniform over a replay buffer, so rollout
                                        # phase alignment cannot bias anything here.

    # ---- collection ---------------------------------------------------------
    num_envs: int = 4                   # [OURS] DEVIATION from [AC]'s single env. Pure wall-clock:
                                        # updates outnumber env steps 1:1 and cost ~10x more, so
                                        # 4 workers hide collection behind the learner without
                                        # changing the update-to-data ratio. See `utd`.
    utd: float = 0.25                   # [F:gen-rebuttal D1] FIXED 2026-08-13. The naive reading
                                        # is "one update per environment step" -- but ALDA does 1
                                        # update per AGENT step (alda_trainer.py:610, `num_updates
                                        # = ... else 1`), and one agent step is `action_repeat` ENV
                                        # FRAMES -- 4 on DMC (paper Table, "Action repeat: 2 for
                                        # finger spin otherwise 4"). So ALDA's true replay ratio is
                                        # 0.25 updates per env frame. RL-ViGen mandates
                                        # action_repeat=1 for robosuite (D5), so a naive utd=1.0
                                        # here runs at 4x ALDA's replay ratio -- an unintended
                                        # consequence of changing action_repeat, not a choice
                                        # anyone made. This was live as the default here: nothing
                                        # in configs/vigen.yaml's `alda:` block overrode it, so
                                        # every launch ran the wrong ratio. High replay ratio is a
                                        # known cause of critic divergence (REDQ / DroQ /
                                        # primacy-bias line of work), and CONFIRMED empirically in
                                        # the sibling gen-rebuttal project (STATE.md D1): utd=1.0
                                        # diverged 3 Lift runs across 2 seeds by ~141k frames
                                        # (critic/loss > 1e8, Q above the reward ceiling, policy
                                        # entropy collapsing); utd=0.25 cleared 220k on both seeds
                                        # with critic/loss in [0.46, 0.68]. See PROTOCOL-DIFF.md
                                        # in that project for the full derivation.
    allow_oom_risk: bool = False    # [OURS] see train.py: safe only when the caller
                                    # packs results even if the trainer is killed
    abort_on_diverge: bool = True   # [OURS] --no-abort disables the SystemExit,
                                    # keeping the checkpoint + the log line
    init_steps: int = 4000              # [RLV] num_seed_frames. [AC] uses 1000 -- but its episode
                                        # is 100 steps at action_repeat 4, so 1000 steps is ~10
                                        # episodes. Ours is 500 steps at action_repeat 1, so 4000
                                        # is 8 episodes: closer to [AC] in the unit that matters
                                        # (episodes of experience) than 1000 would be, AND equal
                                        # to the benchmark's own seed-frame count.
    total_frames: int = 1_100_000       # [RLV] cfgs/task/easy.yaml num_train_frames -- the
                                        # benchmark's own budget for Door, and what produced the
                                        # DrQ-v2/SVEA numbers in results/evaluation_score.xlsx.
                                        # Lift's [RLV] budget is 3.1M (cfgs/task/medium.yaml);
                                        # launch it at 1.1M first and extend by resume, so the
                                        # two tasks are frame-matched at 1.1M whatever happens.

    # ---- replay buffer ------------------------------------------------------
    buffer_capacity: int = 1_100_000    # [AC] uses 1e6 and never fills it (500k train steps).
                                        # Sized here to hold the WHOLE run so nothing is ever
                                        # evicted -- eviction would make the data distribution
                                        # depend on wall-clock position, which is a confound we
                                        # can simply pay RAM to avoid. buffer.py stores single
                                        # frames, not stacks: 3*84*84 = 21.2 kB/step, so 1.1M
                                        # steps is 23.3 GB against 70 GB for stacked obs.
    batch_size: int = 128               # [A]

    # ---- ALDA representation ------------------------------------------------
    num_latents: int = 12               # [A] |z_d|. [A] section 4: "within the ballpark of the
                                        # size of the observation space for the proprioceptive,
                                        # state-based version of the task". Door/Lift: 7 arm
                                        # joints + gripper + object pose ~= 10-12, so the paper's
                                        # own heuristic lands on 12 here too -- see ALDA.md 5.
    values_per_latent: int = 12         # [A]
    beta: float = 100.0                 # [A] Hopfield softmax temperature
    embedding_size: int = 256           # [AC]
    latent_model: str = "associative"   # "associative" = ALDA. "clamp" replaces retrieval with a
                                        # plain clamp to [-1, 1] (ours -- see ALDA.md 8, it is
                                        # sharp because A1 makes the codebook a fixed grid).
                                        # "quantized" = SAC+QLAE (hard
                                        # argmin, [A] Fig. 4). "continuous" = SAC+AE, no
                                        # quantisation and no association ([A] Fig. 5 baseline).
                                        # The three share every other line of code, which is what
                                        # makes them an ablation rather than three programs.
    critic_grad_to_encoder: bool = False
    # [AC] cuts the RL path with `associate(x.detach())`, so no actor or critic gradient reaches
    # the encoder. That cut IS the method: [A] Appendix A.10 measures the variant that removes
    # it -- "ALDA (CG)" -- as worse on every environment, and the ICML rebuttal names the
    # routing as deliberate. False reproduces ALDA. True routes the RL path through the
    # straight-through `z_hat` instead, which is both A.10's ablation and the way SAC+AE
    # (Yarats et al. 2021, [A] Fig. 5's baseline) trains its encoder.
    #
    # Together with `latent_model`, `use_quant_loss` and `train_codebook` this reproduces five
    # named configurations from ONE code path, which is what makes them an ablation rather than
    # five programs:
    #
    #   ALDA                      associative  CG=False  quant=False  codebook=False   [A] main
    #   ALDA (CG)                 associative  CG=True   quant=False  codebook=False   [A] A.10
    #   SAC+QLAE                  quantized    CG=False  quant=True   codebook=True    [A] Fig. 4
    #   SAC+AE                    continuous   CG=True   quant=False  --               [A] Fig. 5
    #   ALDA minus association    continuous   CG=False  quant=False  --               ours

    use_quant_loss: bool = False        # [AC] `use_quant_loss: bool = False`, and [A] section 4
                                        # states the omission explicitly ("we omit L_quantize")
    train_codebook: bool = False        # [F:A1] FAITHFUL TO [AC] AND SURPRISING. In [AC] the
                                        # codebook receives a real gradient from the critic loss
                                        # (measured norm 0.86 on a toy replay of the update
                                        # order) -- and `latent_optimizer.zero_grad()` in
                                        # update_alda discards it before ALDA's own loss, which
                                        # produces NO codebook gradient at all (commitment
                                        # detaches z_q; the straight-through z_hat detaches the
                                        # codebook term; L_quantize is off). Net effect: the
                                        # codebook is FROZEN at linspace(-1, 1, 12) for the whole
                                        # run, despite [A] calling it "task-optimized memories".
                                        # False reproduces [AC]. True lets the critic gradient
                                        # through, which is what [A]'s wording describes.

    # ---- losses -------------------------------------------------------------
    commitment_coef: float = 0.01       # [AC] lambdas['commitment']; [A] implies 1.0
    quantization_coef: float = 0.01     # [AC] lambdas['quantization'] (inert while use_quant_loss)
    recon_coef: float = 1.0             # [AC] lambdas['binary_cross_entropy']
    ae_weight_decay: float = 0.1        # [A] lambda_theta = lambda_phi = 0.1, via AdamW [AC]

    # ---- SAC ----------------------------------------------------------------
    hidden_dim: int = 1024              # [A] 3-layer MLP, 1024 units, GELU
    actor_lr: float = 1e-3              # [A]
    critic_lr: float = 1e-3             # [A]
    encoder_lr: float = 1e-3            # [A] encoder/decoder/latent-model lr
    alpha_lr: float = 1e-4              # [A] "Temperature learning rate"
    actor_beta: float = 0.9             # [AC] Adam beta1 for the actor
    critic_beta: float = 0.9            # [AC]
    alpha_beta: float = 0.5             # [AC]
    init_temperature: float = 0.1       # [AC]
    actor_log_std_min: float = -10.0    # [AC]
    actor_log_std_max: float = 2.0      # [AC]
    actor_update_freq: int = 2          # [A] "Actor update frequency 2"
    critic_target_update_freq: int = 2  # [A] "Critic update frequency 2"
    critic_tau: float = 0.01            # [AC]
    encoder_tau: float = 0.05           # [AC] -- 5x the critic's, and it also drives the latent
                                        # target. Note this is only meaningful while
                                        # train_codebook is True; with a frozen codebook the
                                        # latent target is a copy of a constant.

    # ---- diagnostics ---------------------------------------------------------
    # Tiered like the IDAAC port: cheap detectors every log interval, expensive ones densely at
    # the start where wiring bugs show, then sparsely. 0 disables.
    diag_every: int = 50                # [OURS] updates between the expensive detector pass
    diag_dense_updates: int = 20        # [OURS] run every update for this many first

    # ---- logging / checkpointing --------------------------------------------
    eval_frequency: int = 50_000        # [OURS] frames between checkpoints. Finer than the IDAAC
                                        # port's 100k: SAC moves far faster early, and a
                                        # retention curve needs resolution where the policy is
                                        # actually changing. The supervisor's standing request is
                                        # that every checkpoint be re-evaluable offline.
    log_every_updates: int = 200        # [OURS] one CSV row per this many updates
    eval_episodes: int = 10             # [RLV] cfgs/config.yaml num_eval_episodes (in-loop only;
                                        # the REPORTED protocol is evaluate.py's 100 episodes)
    run_root: str = "runs"
    run_name: str = ""
    device: str = "cuda"
    use_wandb: bool = True
    wandb_project: str = "vigen-idaac"
    wandb_entity: str = "vaarsenii-hse-university"

    env_kwargs: dict = field(default_factory=dict)

    # -------------------------------------------------------------------------
    @property
    def gamma(self) -> float:
        """Alias. `vigen_idaac/envs.py` reads `cfg.gamma` for its return normaliser; ALDA's own
        vocabulary (and [A] Table 1) says "discount". One number, two names, never two values."""
        return self.discount

    @property
    def steps_per_episode(self) -> int:
        return max(1, self.horizon // max(1, self.action_repeat))

    @property
    def total_updates(self) -> int:
        """Gradient updates over the run, excluding the init burst."""
        return int((self.total_frames - self.init_steps) * self.utd)

    def validate(self) -> None:
        assert self.latent_model in ("associative", "quantized", "continuous", "clamp"), \
            self.latent_model
        assert self.image_size % 16 == 0 or self.image_size >= 32, self.image_size
        assert self.total_frames > self.init_steps, "nothing to train on"
        # utd became load-bearing once it was used to set the replay ratio. A non-positive value
        # yields a run that collects data and NEVER updates: frames advance, fps looks normal,
        # every learning metric sits at its init value, and nothing errors. `--utd 0` is one
        # keystroke away from `--utd 0.25`.
        assert self.utd > 0, (
            f"utd must be > 0, got {self.utd}: the run would collect data and never learn")
        assert self.init_steps % self.num_envs == 0, (
            f"init_steps {self.init_steps} must be a multiple of num_envs {self.num_envs}; "
            f"otherwise the prefill boundary falls mid-iteration and the update burst is "
            f"off by up to num_envs-1 steps")
        assert self.buffer_capacity % self.num_envs == 0, (
            f"buffer_capacity {self.buffer_capacity} must divide by num_envs {self.num_envs}: "
            f"the buffer is per-env ring segments so that index i+1 is the SAME env's next step")
        assert 0.0 < self.discount <= 1.0
        assert self.frame_stack >= 1 and self.num_latents >= 1
        # Deliberately absent: any check that buffer_capacity >= total_frames. Evicting is a
        # legitimate configuration, it just has to be a CHOSEN one -- train.py logs which it is.

    def to_dict(self) -> dict:
        return asdict(self)
