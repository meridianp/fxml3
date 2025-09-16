"""Reinforcement learning agent for forex trading."""

import os
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

try:
    import tensorflow as tf
    import tensorflow_probability as tfp
except ImportError:
    raise ImportError(
        "TensorFlow is not installed. "
        "Please install it with: pip install tensorflow tensorflow-probability"
    )


class ReplayBuffer:
    """Experience replay buffer for storing and sampling transitions.

    Stores agent's experiences and allows for random sampling to break
    correlation between sequential observations and improve learning stability.
    """

    def __init__(self, capacity: int = 10000):
        """Initialize the replay buffer.

        Args:
            capacity: Maximum number of transitions to store
        """
        self.capacity = capacity
        self.buffer = []
        self.position = 0

    def push(
        self,
        state: np.ndarray,
        action: np.ndarray,
        reward: float,
        next_state: np.ndarray,
        done: bool,
    ) -> None:
        """Add a transition to the buffer.

        Args:
            state: Current state
            action: Action taken
            reward: Reward received
            next_state: Next state
            done: Whether episode is done
        """
        if len(self.buffer) < self.capacity:
            self.buffer.append(None)
        self.buffer[self.position] = (state, action, reward, next_state, done)
        self.position = (self.position + 1) % self.capacity

    def sample(self, batch_size: int) -> Tuple:
        """Sample a random batch of transitions.

        Args:
            batch_size: Number of transitions to sample

        Returns:
            Tuple of (states, actions, rewards, next_states, dones)
        """
        # Make sure buffer has enough samples
        batch_size = min(batch_size, len(self.buffer))

        # Sample indices without replacement
        indices = np.random.choice(len(self.buffer), batch_size, replace=False)

        # Get samples
        states, actions, rewards, next_states, dones = zip(
            *[self.buffer[i] for i in indices]
        )

        # Convert to arrays
        states = np.array(states)
        actions = np.array(actions)
        rewards = np.array(rewards, dtype=np.float32)
        next_states = np.array(next_states)
        dones = np.array(dones, dtype=np.float32)

        return states, actions, rewards, next_states, dones

    def __len__(self) -> int:
        """Get the current size of the buffer.

        Returns:
            Number of transitions in buffer
        """
        return len(self.buffer)


class WaveTradingAgent:
    """Trading agent using PPO for forex markets based on Elliott Wave patterns.

    Implements the Proximal Policy Optimization (PPO) algorithm for learning
    optimal trading policies. The agent uses actor-critic architecture with
    separate policy (actor) and value (critic) networks.
    """

    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        hidden_dim: int = 128,
        learning_rate: float = 0.0003,
        gamma: float = 0.99,
        clip_ratio: float = 0.2,
        entropy_coef: float = 0.01,
        value_coef: float = 0.5,
        max_grad_norm: float = 0.5,
        update_epochs: int = 4,
        batch_size: int = 64,
        model_dir: Optional[str] = None,
    ):
        """Initialize the trading agent.

        Args:
            state_dim: Dimension of the state space
            action_dim: Dimension of the action space
            hidden_dim: Hidden dimension of neural networks
            learning_rate: Learning rate for optimizers
            gamma: Discount factor for future rewards
            clip_ratio: PPO clipping parameter
            entropy_coef: Entropy coefficient for exploration
            value_coef: Value loss coefficient
            max_grad_norm: Maximum norm for gradient clipping
            update_epochs: Number of epochs to update on each batch
            batch_size: Batch size for updates
            model_dir: Directory to save models
        """
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.hidden_dim = hidden_dim
        self.learning_rate = learning_rate
        self.gamma = gamma
        self.clip_ratio = clip_ratio
        self.entropy_coef = entropy_coef
        self.value_coef = value_coef
        self.max_grad_norm = max_grad_norm
        self.update_epochs = update_epochs
        self.batch_size = batch_size
        self.model_dir = model_dir

        # Create directories if needed
        if model_dir and not os.path.exists(model_dir):
            os.makedirs(model_dir)

        # Build actor and critic networks
        self.actor = self._build_actor()
        self.critic = self._build_critic()

        # Initialize optimizers
        self.actor_optimizer = tf.keras.optimizers.Adam(learning_rate=learning_rate)
        self.critic_optimizer = tf.keras.optimizers.Adam(learning_rate=learning_rate)

        # Initialize replay buffer
        self.replay_buffer = ReplayBuffer(capacity=10000)

        # Track training metrics
        self.train_step = 0
        self.train_summary_writer = None

        # Initialize TensorBoard logging if model_dir is provided
        if model_dir:
            log_dir = os.path.join(model_dir, "logs", str(int(time.time())))
            self.train_summary_writer = tf.summary.create_file_writer(log_dir)

    def _build_actor(self) -> tf.keras.Model:
        """Build policy network (actor).

        Returns:
            Actor model that outputs action mean and log standard deviation
        """
        inputs = tf.keras.layers.Input(shape=(self.state_dim,))

        # Hidden layers with ELU activation
        x = tf.keras.layers.Dense(self.hidden_dim, activation="elu")(inputs)
        x = tf.keras.layers.Dense(self.hidden_dim, activation="elu")(x)

        # Output mean with tanh activation (scaled to [-1, 1])
        mean = tf.keras.layers.Dense(self.action_dim, activation="tanh")(x)

        # Output log standard deviation with custom activation
        log_std = tf.keras.layers.Dense(self.action_dim)(x)
        log_std = tf.keras.layers.Lambda(lambda x: tf.clip_by_value(x, -5, 0))(
            log_std
        )  # Clip log_std for numerical stability

        return tf.keras.Model(inputs=inputs, outputs=[mean, log_std])

    def _build_critic(self) -> tf.keras.Model:
        """Build value network (critic).

        Returns:
            Critic model that outputs state value
        """
        inputs = tf.keras.layers.Input(shape=(self.state_dim,))

        # Hidden layers with ELU activation
        x = tf.keras.layers.Dense(self.hidden_dim, activation="elu")(inputs)
        x = tf.keras.layers.Dense(self.hidden_dim, activation="elu")(x)

        # Output value (no activation)
        value = tf.keras.layers.Dense(1)(x)

        return tf.keras.Model(inputs=inputs, outputs=value)

    def act(
        self,
        state: np.ndarray,
        deterministic: bool = False,
    ) -> np.ndarray:
        """Select an action based on the current policy.

        Args:
            state: Current state
            deterministic: Whether to select deterministic action (mean)

        Returns:
            Selected action
        """
        # Convert state to tensor and ensure correct shape
        if len(state.shape) == 1:
            state = np.expand_dims(state, axis=0)
        state = tf.convert_to_tensor(state, dtype=tf.float32)

        # Get action mean and log_std from policy network
        mean, log_std = self.actor(state)

        if deterministic:
            # Return mean action
            return mean.numpy()[0]
        else:
            # Sample from normal distribution
            std = tf.exp(log_std)
            distribution = tfp.distributions.Normal(mean, std)
            action = distribution.sample()

            # Clip action to valid range
            action = tf.clip_by_value(action, -1.0, 1.0)

            return action.numpy()[0]

    def get_value(self, state: np.ndarray) -> float:
        """Get value estimate for a state.

        Args:
            state: State to evaluate

        Returns:
            Estimated value of the state
        """
        # Convert state to tensor and ensure correct shape
        if len(state.shape) == 1:
            state = np.expand_dims(state, axis=0)
        state = tf.convert_to_tensor(state, dtype=tf.float32)

        # Get value from critic network
        value = self.critic(state)

        return value.numpy()[0, 0]

    def store_transition(
        self,
        state: np.ndarray,
        action: np.ndarray,
        reward: float,
        next_state: np.ndarray,
        done: bool,
    ) -> None:
        """Store a transition in the replay buffer.

        Args:
            state: Current state
            action: Action taken
            reward: Reward received
            next_state: Next state
            done: Whether episode is done
        """
        self.replay_buffer.push(state, action, reward, next_state, done)

    def compute_advantages(
        self,
        rewards: np.ndarray,
        values: np.ndarray,
        dones: np.ndarray,
        next_values: np.ndarray,
    ) -> np.ndarray:
        """Compute advantages using Generalized Advantage Estimation (GAE).

        Args:
            rewards: Array of rewards
            values: Array of value estimates
            dones: Array of episode terminations
            next_values: Array of next state value estimates

        Returns:
            Array of advantage estimates
        """
        # Initialize advantage array
        advantages = np.zeros_like(rewards)

        # Calculate advantage estimates
        for t in reversed(range(len(rewards))):
            # Calculate TD error
            if t == len(rewards) - 1:
                next_value = next_values[t]
            else:
                next_value = values[t + 1]

            # Calculate TD target
            delta = rewards[t] + self.gamma * next_value * (1 - dones[t]) - values[t]

            # Calculate advantage
            advantages[t] = delta

            # Add discounted advantage from next step if not done
            if t < len(rewards) - 1 and not dones[t]:
                advantages[t] += self.gamma * advantages[t + 1]

        return advantages

    def learn(self) -> Dict:
        """Update policy and value networks from replay buffer.

        Returns:
            Dictionary of training metrics
        """
        # Check if buffer has enough samples
        if len(self.replay_buffer) < self.batch_size:
            return {"actor_loss": 0.0, "critic_loss": 0.0, "entropy": 0.0}

        # Sample from replay buffer
        states, actions, rewards, next_states, dones = self.replay_buffer.sample(
            self.batch_size
        )

        # Get values for states and next states
        values = self.critic(states).numpy().flatten()
        next_values = self.critic(next_states).numpy().flatten()

        # Compute advantages
        advantages = self.compute_advantages(rewards, values, dones, next_values)

        # Normalize advantages
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        # Compute returns
        returns = advantages + values

        # Convert to tensors
        states_tensor = tf.convert_to_tensor(states, dtype=tf.float32)
        actions_tensor = tf.convert_to_tensor(actions, dtype=tf.float32)
        advantages_tensor = tf.convert_to_tensor(advantages, dtype=tf.float32)
        returns_tensor = tf.convert_to_tensor(returns, dtype=tf.float32)

        # Get old policy distribution parameters
        old_means, old_log_stds = self.actor(states_tensor)
        old_stds = tf.exp(old_log_stds)
        old_dist = tfp.distributions.Normal(old_means, old_stds)
        old_log_probs = old_dist.log_prob(actions_tensor)
        old_log_probs = tf.reduce_sum(old_log_probs, axis=1)

        # Prepare arrays for tracking metrics
        actor_losses = []
        critic_losses = []
        entropy_values = []

        # Update networks for multiple epochs
        for epoch in range(self.update_epochs):
            # Update actor network
            with tf.GradientTape() as tape:
                # Get current policy distribution parameters
                means, log_stds = self.actor(states_tensor)
                stds = tf.exp(log_stds)
                dist = tfp.distributions.Normal(means, stds)

                # Calculate log probabilities
                log_probs = dist.log_prob(actions_tensor)
                log_probs = tf.reduce_sum(log_probs, axis=1)

                # Calculate ratio for importance sampling
                ratio = tf.exp(log_probs - old_log_probs)

                # Calculate surrogate objectives
                surrogate1 = ratio * advantages_tensor
                surrogate2 = (
                    tf.clip_by_value(
                        ratio, 1.0 - self.clip_ratio, 1.0 + self.clip_ratio
                    )
                    * advantages_tensor
                )

                # Calculate entropy
                entropy = tf.reduce_mean(dist.entropy())

                # Calculate actor loss (negative because we want to maximize)
                actor_loss = -tf.reduce_mean(tf.minimum(surrogate1, surrogate2))

                # Add entropy bonus to encourage exploration
                actor_loss -= self.entropy_coef * entropy

            # Calculate and apply actor gradients
            actor_grads = tape.gradient(actor_loss, self.actor.trainable_variables)
            actor_grads, _ = tf.clip_by_global_norm(actor_grads, self.max_grad_norm)
            self.actor_optimizer.apply_gradients(
                zip(actor_grads, self.actor.trainable_variables)
            )

            # Update critic network
            with tf.GradientTape() as tape:
                # Get current value estimates
                values = self.critic(states_tensor)
                values = tf.squeeze(values, axis=1)

                # Calculate value loss (MSE)
                critic_loss = (
                    tf.reduce_mean(tf.square(values - returns_tensor)) * self.value_coef
                )

            # Calculate and apply critic gradients
            critic_grads = tape.gradient(critic_loss, self.critic.trainable_variables)
            critic_grads, _ = tf.clip_by_global_norm(critic_grads, self.max_grad_norm)
            self.critic_optimizer.apply_gradients(
                zip(critic_grads, self.critic.trainable_variables)
            )

            # Store metrics
            actor_losses.append(actor_loss.numpy())
            critic_losses.append(critic_loss.numpy())
            entropy_values.append(entropy.numpy())

        # Increment training step
        self.train_step += 1

        # Log metrics
        metrics = {
            "actor_loss": np.mean(actor_losses),
            "critic_loss": np.mean(critic_losses),
            "entropy": np.mean(entropy_values),
        }

        # Write to TensorBoard if available
        if self.train_summary_writer:
            with self.train_summary_writer.as_default():
                for name, value in metrics.items():
                    tf.summary.scalar(name, value, step=self.train_step)

        return metrics

    def save_models(self, prefix: str = "model") -> None:
        """Save actor and critic models.

        Args:
            prefix: Prefix for model files
        """
        if not self.model_dir:
            return

        actor_path = os.path.join(self.model_dir, f"{prefix}_actor")
        critic_path = os.path.join(self.model_dir, f"{prefix}_critic")

        self.actor.save(actor_path)
        self.critic.save(critic_path)

        print(f"Models saved to {self.model_dir}")

    def load_models(self, prefix: str = "model") -> None:
        """Load actor and critic models.

        Args:
            prefix: Prefix for model files
        """
        if not self.model_dir:
            return

        actor_path = os.path.join(self.model_dir, f"{prefix}_actor")
        critic_path = os.path.join(self.model_dir, f"{prefix}_critic")

        if os.path.exists(actor_path) and os.path.exists(critic_path):
            self.actor = tf.keras.models.load_model(actor_path)
            self.critic = tf.keras.models.load_model(critic_path)
            print(f"Models loaded from {self.model_dir}")
        else:
            print(f"No saved models found in {self.model_dir}")


class SimpleTradingAgent:
    """Simple trading agent for baseline comparison.

    This agent uses predefined rules based on Elliott Wave patterns
    without learning, providing a baseline for RL performance comparison.
    """

    def __init__(self, action_dim: int = 1):
        """Initialize the simple trading agent.

        Args:
            action_dim: Dimension of the action space
        """
        self.action_dim = action_dim

    def act(self, state: np.ndarray) -> np.ndarray:
        """Select an action based on simple rules.

        Args:
            state: Current state including wave pattern features

        Returns:
            Selected action
        """
        # Extract wave pattern features from state
        # Assuming state structure from ForexTradingEnv:
        # - price_features (5)
        # - tech_indicators (10)
        # - wave_features (8) <- We're interested in these
        #   - [0]: pattern_type (1 for impulse, 0 for corrective)
        #   - [1]: wave_count (normalized 0-1, multiply by 5 to get actual count)
        #   - [4]: direction (1 for up, -1 for down)
        # - sentiment_features (3)
        # - account_features (3)

        # Extract wave features
        pattern_type = state[15]  # 1 for impulse, 0 for corrective
        wave_count = state[16] * 5.0  # Denormalize
        direction = state[19]  # 1 for up, -1 for down

        # Default action: hold
        action = np.zeros(self.action_dim)

        # Simple Elliott Wave trading rules
        if pattern_type == 1.0:  # Impulse wave
            # Buy in waves 1, 3, 5; sell in waves 2, 4
            if wave_count in [1, 3, 5]:
                action[0] = 0.8 * direction  # Buy (or sell if downward impulse)
            else:  # waves 2, 4
                action[0] = -0.4 * direction  # Sell (or buy if downward impulse)

        else:  # Corrective wave
            # Sell in waves A, C; buy in wave B
            if wave_count in [1, 3]:  # A, C
                action[0] = -0.5 * direction  # Sell (or buy if downward correction)
            else:  # wave B
                action[0] = 0.3 * direction  # Buy (or sell if downward correction)

        return action
