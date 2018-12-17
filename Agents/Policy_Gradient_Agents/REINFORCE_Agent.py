import numpy as np
import torch
from torch.distributions import Categorical
import torch.optim as optim
from Base_Agent import Base_Agent
from Model import Model


class REINFORCE_Agent(Base_Agent):
    agent_name = "REINFORCE"

    def __init__(self, config, agent_name):

        Base_Agent.__init__(self, config, agent_name)

        self.policy = Model(self.state_size, self.action_size, config.seed, self.hyperparameters).to(self.device)
        self.optimizer = optim.Adam(self.policy.parameters(), lr=self.hyperparameters["learning_rate"])

        self.episode_rewards = []
        self.episode_log_probabilities = []

    def reset_game(self):
        """Resets the game information so we are ready to play a new episode"""
        self.environment.reset_environment()
        self.state = self.environment.get_state()
        self.next_state = None
        self.action = None
        self.reward = None
        self.done = False
        self.total_episode_score_so_far = 0
        self.episode_rewards = []
        self.episode_log_probabilities = []
        self.episode_step_number = 0

    def step(self):
        """Runs a step within a game including a learning step if required"""
        self.pick_and_conduct_action_and_save_log_probabilities()

        self.update_next_state_reward_done_and_score()
        self.store_reward()

        if self.time_to_learn():
            self.critic_learn()

        self.state = self.next_state #this is to set the state for the next iteration

    def pick_and_conduct_action_and_save_log_probabilities(self):
        action, log_probabilities = self.pick_action_and_get_log_probabilities()
        self.store_log_probabilities(log_probabilities)
        self.store_action(action)
        self.conduct_action()

    def pick_action_and_get_log_probabilities(self):

        # PyTorch only accepts mini-batches and not individual observations so we have to add
        # a "fake" dimension to our observation using unsqueeze
        state = torch.from_numpy(self.state).float().unsqueeze(0).to(self.device)

        action_probabilities = self.policy.forward(state).cpu()
        action_distribution = Categorical(action_probabilities) # this creates a distribution to sample from
        action = action_distribution.sample()

        return action.item(), action_distribution.log_prob(action)

    def store_log_probabilities(self, log_probabilities):
        self.episode_log_probabilities.append(log_probabilities)

    def store_action(self, action):
        self.action = action

    def store_reward(self):
        self.episode_rewards.append(self.reward)


    def policy_learn(self):
        total_discounted_reward = self.calculate_episode_discounted_reward()
        policy_loss = self.calculate_policy_loss_on_episode(total_discounted_reward)
        self.optimizer.zero_grad()
        policy_loss.backward()
        self.optimizer.step()

    def calculate_episode_discounted_reward(self):
        discounts = self.hyperparameters["discount_rate"] ** np.arange(len(self.episode_rewards))
        total_discounted_reward = np.dot(discounts, self.episode_rewards)

        return total_discounted_reward

    def calculate_policy_loss_on_episode(self, total_discounted_reward):
        policy_loss = []
        for log_prob in self.episode_log_probabilities:
            policy_loss.append(-log_prob * total_discounted_reward)
        policy_loss = torch.cat(policy_loss).sum() # We need to add up the losses across the mini-batch to get 1 overall loss
        # policy_loss = Variable(policy_loss, requires_grad = True)
        return policy_loss

    def time_to_learn(self):
        """Tells us whether it is time for the algorithm to learn. With REINFORCE we only learn at the end of every
        episode so this just returns whether the episode is over"""
        return self.done
