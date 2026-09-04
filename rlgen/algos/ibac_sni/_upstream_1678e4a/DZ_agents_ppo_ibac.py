# PPO with Information Bottleneck (IBAC) and Selective Noise Injection (SNI).
# Igl et al., "Generalization in RL with Selective Noise Injection and Information Bottleneck", NeurIPS 2019.
#
# IB:  add beta * KL(z || N(0,I)) to the PPO loss, where z is a stochastic latent bottleneck.
# SNI: the policy-gradient objective is evaluated on the DETERMINISTIC pass (z=mu), avoiding the
#      variance that stochastic z injects into the PG estimator; the IB regularizer is evaluated on
#      the STOCHASTIC pass. sni_lambda in [0,1] mixes the two policy passes for the actor loss:
#        pi_used = lambda * pi_det + (1-lambda) * pi_stoch      (lambda=1.0 -> pure SNI actor)
# Rollout (predict) always uses the deterministic pass, consistent with SNI.
from .base_agent import BaseAgent
from common.misc_util import adjust_lr
import torch
import torch.optim as optim
import numpy as np
from procgen import ProcgenEnv
from common.env.procgen_wrappers import *


class PPO_IBAC(BaseAgent):
    def __init__(self, env, env_name, distribution_mode, policy, logger, storage, device, n_checkpoints,
                 n_steps=128, n_envs=8, epoch=3, mini_batch_per_epoch=8, mini_batch_size=32*8,
                 gamma=0.99, lmbda=0.95, learning_rate=2.5e-4, grad_clip_norm=0.5, eps_clip=0.2,
                 value_coef=0.5, entropy_coef=0.01, normalize_adv=True, normalize_rew=True,
                 use_gae=True, beta=1e-4, sni=True, sni_lambda=0.5, **kwargs):
        super(PPO_IBAC, self).__init__(env, policy, logger, storage, device, n_checkpoints)
        self.env_name = env_name
        self.distribution_mode = distribution_mode
        self.n_steps = n_steps; self.n_envs = n_envs; self.epoch = epoch
        self.mini_batch_per_epoch = mini_batch_per_epoch; self.mini_batch_size = mini_batch_size
        self.gamma = gamma; self.lmbda = lmbda; self.learning_rate = learning_rate
        self.optimizer = optim.Adam(self.policy.parameters(), lr=learning_rate, eps=1e-5)
        self.grad_clip_norm = grad_clip_norm; self.eps_clip = eps_clip
        self.value_coef = value_coef; self.entropy_coef = entropy_coef
        self.normalize_adv = normalize_adv; self.normalize_rew = normalize_rew; self.use_gae = use_gae
        # IBAC-SNI knobs
        self.beta = beta               # IB weight
        self.sni = sni                 # enable selective noise injection
        self.sni_lambda = sni_lambda   # mixing between deterministic and stochastic actor

    def predict(self, obs, hidden_state, done):
        with torch.no_grad():
            obs = torch.FloatTensor(obs).to(device=self.device)
            hidden_state = torch.FloatTensor(hidden_state).to(device=self.device)
            mask = torch.FloatTensor(1-done).to(device=self.device)
            # deterministic pass for rollout (SNI-consistent)
            dist, value, hidden_state = self.policy(obs, hidden_state, mask, sample=False)
            act = dist.sample()
            log_prob_act = dist.log_prob(act)
        return act.cpu().numpy(), log_prob_act.cpu().numpy(), value.cpu().numpy(), hidden_state.cpu().numpy()

    def _actor_terms(self, obs, hx, mask):
        """Return (log_prob fn inputs): a deterministic dist, a stochastic dist, value, ib_kl.
        Value/entropy taken from the pass(es) per SNI convention."""
        # stochastic pass provides the IB KL and the stochastic actor
        dist_s, value_s, _, ib_kl = self.policy(obs, hx, mask, sample=True, return_ib=True)
        if self.sni:
            dist_d, value_d, _ = self.policy(obs, hx, mask, sample=False)
            return dist_d, dist_s, value_d, value_s, ib_kl
        else:
            return None, dist_s, None, value_s, ib_kl

    def optimize(self):
        pi_loss_list, value_loss_list, entropy_loss_list, ib_loss_list = [], [], [], []
        batch_size = self.n_steps * self.n_envs // self.mini_batch_per_epoch
        if batch_size < self.mini_batch_size:
            self.mini_batch_size = batch_size
        grad_accumulation_steps = batch_size / self.mini_batch_size
        grad_accumulation_cnt = 1

        self.policy.train()
        for e in range(self.epoch):
            recurrent = self.policy.is_recurrent()
            generator = self.storage.fetch_train_generator(mini_batch_size=self.mini_batch_size,
                                                           recurrent=recurrent)
            for sample in generator:
                obs_batch, hidden_state_batch, act_batch, done_batch, \
                    old_log_prob_act_batch, old_value_batch, return_batch, adv_batch = sample
                mask_batch = (1-done_batch)

                dist_d, dist_s, value_d, value_s, ib_kl = self._actor_terms(obs_batch, hidden_state_batch, mask_batch)

                def ppo_pi_loss(dist):
                    lp = dist.log_prob(act_batch)
                    ratio = torch.exp(lp - old_log_prob_act_batch)
                    surr1 = ratio * adv_batch
                    surr2 = torch.clamp(ratio, 1.0 - self.eps_clip, 1.0 + self.eps_clip) * adv_batch
                    return -torch.min(surr1, surr2).mean()

                if self.sni:
                    # SNI: mix deterministic and stochastic actor objectives
                    pi_loss = self.sni_lambda * ppo_pi_loss(dist_d) + (1.0 - self.sni_lambda) * ppo_pi_loss(dist_s)
                    entropy_loss = (self.sni_lambda * dist_d.entropy().mean()
                                    + (1.0 - self.sni_lambda) * dist_s.entropy().mean())
                    value_batch = self.sni_lambda * value_d + (1.0 - self.sni_lambda) * value_s
                else:
                    pi_loss = ppo_pi_loss(dist_s)
                    entropy_loss = dist_s.entropy().mean()
                    value_batch = value_s

                # Clipped value loss
                clipped_value_batch = old_value_batch + (value_batch - old_value_batch).clamp(-self.eps_clip, self.eps_clip)
                v_surr1 = (value_batch - return_batch).pow(2)
                v_surr2 = (clipped_value_batch - return_batch).pow(2)
                value_loss = 0.5 * torch.max(v_surr1, v_surr2).mean()

                loss = (pi_loss + self.value_coef * value_loss
                        - self.entropy_coef * entropy_loss
                        + self.beta * ib_kl)
                loss.backward()

                if grad_accumulation_cnt % grad_accumulation_steps == 0:
                    torch.nn.utils.clip_grad_norm_(self.policy.parameters(), self.grad_clip_norm)
                    self.optimizer.step()
                    self.optimizer.zero_grad()
                grad_accumulation_cnt += 1
                pi_loss_list.append(pi_loss.item())
                value_loss_list.append(value_loss.item())
                entropy_loss_list.append(entropy_loss.item())
                ib_loss_list.append(ib_kl.item())

        return {'Loss/pi': np.mean(pi_loss_list), 'Loss/v': np.mean(value_loss_list),
                'Loss/entropy': np.mean(entropy_loss_list), 'Loss/ib_kl': np.mean(ib_loss_list)}

    def train(self, num_timesteps):
        save_every = num_timesteps // self.num_checkpoints
        checkpoint_cnt = 0
        obs = self.env.reset()
        hidden_state = np.zeros((self.n_envs, self.storage.hidden_state_size))
        done = np.zeros(self.n_envs)
        eval_cnt = 0
        eval_freq = 5
        while self.t < num_timesteps:
            eval_cnt += 1
            self.policy.eval()
            for _ in range(self.n_steps):
                act, log_prob_act, value, next_hidden_state = self.predict(obs, hidden_state, done)
                next_obs, rew, done, info = self.env.step(act)
                self.storage.store(obs, hidden_state, act, rew, done, info, log_prob_act, value)
                obs = next_obs; hidden_state = next_hidden_state
            _, _, last_val, hidden_state = self.predict(obs, hidden_state, done)
            self.storage.store_last(obs, hidden_state, last_val)
            self.storage.compute_estimates(self.gamma, self.lmbda, self.use_gae, self.normalize_adv)
            summary = self.optimize()
            self.t += self.n_steps * self.n_envs
            rew_batch, done_batch = self.storage.fetch_log_data()
            self.logger.feed(rew_batch, done_batch)
            self.logger.write_summary(summary)
            self.logger.dump()
            self.optimizer = adjust_lr(self.optimizer, self.learning_rate, self.t, num_timesteps)

            if eval_cnt % eval_freq == 0:
                self.evaluate(num_episodes=128, start_level=0, num_levels=0)

            if self.t > ((checkpoint_cnt+1) * save_every):
                torch.save({'state_dict': self.policy.state_dict()},
                           self.logger.logdir + '/model_' + str(self.t) + '.pth')
                checkpoint_cnt += 1
        self.env.close()

    def evaluate(self, num_episodes=128, start_level=0, num_levels=0):
        self.policy.eval()

        eval_env = ProcgenEnv(num_envs=self.n_envs,
                              env_name=self.env_name,
                              start_level=start_level,
                              num_levels=num_levels,
                              distribution_mode=self.distribution_mode)
        normalize_rew = True
        eval_env = VecExtractDictObs(eval_env, "rgb")
        if normalize_rew:
            eval_env = VecNormalize(eval_env, ob=False)  # normalize returns, not frames
        eval_env = TransposeFrame(eval_env)
        eval_env = ScaledFloatFrame(eval_env)

        obs = eval_env.reset()
        hidden_state = np.zeros((self.n_envs, self.storage.hidden_state_size))
        done = np.zeros(self.n_envs)
        episode_rewards = [0.0 for _ in range(self.n_envs)]
        results = []
        completed_episodes = 0

        while completed_episodes < num_episodes:
            act, _, _, hidden_state = self.predict(obs, hidden_state, done)
            next_obs, rew, done, infos = eval_env.step(act)
            for i, d in enumerate(done):
                episode_rewards[i] += rew[i]
                if d:
                    results.append(episode_rewards[i])
                    episode_rewards[i] = 0
                    completed_episodes += 1
            obs = next_obs

        avg_reward = np.mean(results)
        std_reward = np.std(results)
        print(f"[Eval] {num_episodes} episodes | avg_reward={avg_reward:.2f} \u00b1 {std_reward:.2f} | start_level={start_level}, num_levels={num_levels}")

        if self.logger is not None:
            self.logger.write_summary({
                'Eval/avg_reward': avg_reward,
                'Eval/std_reward': std_reward,
                'Eval/start_level': start_level,
                'Eval/num_levels': num_levels
            })
