"""
Policy optimization module for RL-based trading strategies.

This module provides tools for optimizing and fine-tuning RL agents
for trading forex markets based on Elliott Wave patterns.
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import tensorflow as tf
from ray import tune
from ray.tune import CLIReporter
from ray.tune.integration.tensorflow import TensorboardCallback
from ray.tune.schedulers import ASHAScheduler, PopulationBasedTraining

from fxml3.backtesting.rl_agent import SimpleTradingAgent, WaveTradingAgent
from fxml3.backtesting.rl_environment import ForexTradingEnv
from fxml3.backtesting.rl_training import evaluate_agent, train_agent


@dataclass
class PolicyNetworkConfig:
    """Configuration for policy network architecture."""

    hidden_layers: List[int] = None
    activation: str = "tanh"
    learning_rate: float = 3e-4
    layer_normalization: bool = True
    dropout_rate: Optional[float] = None
    use_lstm: bool = False
    lstm_units: int = 64


@dataclass
class PPOConfig:
    """Configuration for PPO algorithm."""

    clip_ratio: float = 0.2
    value_coeff: float = 0.5
    entropy_coeff: float = 0.01
    target_kl: float = 0.01
    gae_lambda: float = 0.95
    gamma: float = 0.99
    update_epochs: int = 4
    normalize_advantages: bool = True


class PolicyOptimizer:
    """Handles optimization of RL policy networks for trading."""

    def __init__(
        self,
        env_config: Dict[str, Any],
        base_agent_config: Dict[str, Any],
        optimization_metric: str = "sharpe_ratio",
        max_trials: int = 10,
        resources_per_trial: Dict[str, Any] = None,
    ):
        """
        Initialize the policy optimizer.

        Args:
            env_config: Configuration for the trading environment
            base_agent_config: Base configuration for the agent
            optimization_metric: Metric to optimize ('sharpe_ratio', 'total_return', etc.)
            max_trials: Maximum number of optimization trials
            resources_per_trial: CPU/GPU resources per trial
        """
        self.env_config = env_config
        self.base_agent_config = base_agent_config
        self.optimization_metric = optimization_metric
        self.max_trials = max_trials
        self.resources_per_trial = resources_per_trial or {"cpu": 2, "gpu": 0.25}
        self.results = None

    def _create_agent_with_config(self, config: Dict[str, Any]) -> WaveTradingAgent:
        """Create an agent with the given configuration."""
        # Merge base config with trial config
        merged_config = {**self.base_agent_config, **config}

        # Create environment
        env = ForexTradingEnv(**self.env_config)

        # Create policy network configuration
        network_config = PolicyNetworkConfig(
            hidden_layers=config.get("hidden_layers", [64, 64]),
            activation=config.get("activation", "tanh"),
            learning_rate=config.get("learning_rate", 3e-4),
            layer_normalization=config.get("layer_normalization", True),
            dropout_rate=config.get("dropout_rate", None),
            use_lstm=config.get("use_lstm", False),
            lstm_units=config.get("lstm_units", 64),
        )

        # Create PPO configuration
        ppo_config = PPOConfig(
            clip_ratio=config.get("clip_ratio", 0.2),
            value_coeff=config.get("value_coeff", 0.5),
            entropy_coeff=config.get("entropy_coeff", 0.01),
            target_kl=config.get("target_kl", 0.01),
            gae_lambda=config.get("gae_lambda", 0.95),
            gamma=config.get("gamma", 0.99),
            update_epochs=config.get("update_epochs", 4),
            normalize_advantages=config.get("normalize_advantages", True),
        )

        # Create agent
        agent = WaveTradingAgent(
            env=env,
            policy_network_config=network_config,
            ppo_config=ppo_config,
            **merged_config,
        )

        return agent, env

    def _train_and_evaluate(self, config: Dict[str, Any]) -> Dict[str, float]:
        """Train and evaluate an agent with the given configuration."""
        agent, env = self._create_agent_with_config(config)

        # Train agent
        train_metrics = train_agent(
            agent=agent,
            env=env,
            epochs=config.get("epochs", 100),
            batch_size=config.get("batch_size", 64),
            log_interval=config.get("log_interval", 10),
            checkpoint_dir=os.path.join(
                config.get("checkpoint_dir", "./checkpoints"), str(tune.get_trial_id())
            ),
            early_stopping_patience=config.get("early_stopping_patience", 20),
            tensorboard_dir=os.path.join(
                config.get("tensorboard_dir", "./logs"), str(tune.get_trial_id())
            ),
        )

        # Evaluate agent
        eval_metrics = evaluate_agent(
            agent=agent,
            env=env,
            num_episodes=config.get("eval_episodes", 100),
            render=False,
        )

        # Combine metrics
        metrics = {**train_metrics, **eval_metrics}

        # Report metrics for Ray Tune
        tune.report(**metrics)

        return metrics

    def _get_search_space(self) -> Dict[str, Any]:
        """Define the hyperparameter search space."""
        return {
            # Network architecture
            "hidden_layers": tune.choice(
                [[32, 32], [64, 64], [128, 64], [64, 64, 32], [128, 64, 32]]
            ),
            "activation": tune.choice(["relu", "tanh", "selu"]),
            "learning_rate": tune.loguniform(1e-5, 1e-3),
            "layer_normalization": tune.choice([True, False]),
            "dropout_rate": tune.choice([None, 0.1, 0.2, 0.3]),
            "use_lstm": tune.choice([True, False]),
            "lstm_units": tune.choice([32, 64, 128]),
            # PPO parameters
            "clip_ratio": tune.uniform(0.1, 0.3),
            "value_coeff": tune.uniform(0.3, 0.7),
            "entropy_coeff": tune.loguniform(1e-4, 1e-2),
            "target_kl": tune.uniform(0.005, 0.02),
            "gae_lambda": tune.uniform(0.9, 0.99),
            "gamma": tune.uniform(0.95, 0.995),
            "update_epochs": tune.choice([2, 4, 6, 8]),
            # Training parameters
            "batch_size": tune.choice([32, 64, 128, 256]),
            "epochs": 100,  # Fixed to save time
            "eval_episodes": 50,  # Fixed to save time
        }

    def run_grid_search(
        self, experiment_name: str = "ppo_grid_search"
    ) -> Dict[str, Any]:
        """Run grid search for hyperparameter optimization."""
        search_space = self._get_search_space()

        scheduler = ASHAScheduler(
            metric=self.optimization_metric,
            mode="max",
            max_t=100,
            grace_period=10,
            reduction_factor=2,
        )

        reporter = CLIReporter(
            metric_columns=[
                self.optimization_metric,
                "episode_reward_mean",
                "training_loss",
            ],
            parameter_columns=["hidden_layers", "learning_rate", "batch_size"],
        )

        result = tune.run(
            self._train_and_evaluate,
            config=search_space,
            num_samples=self.max_trials,
            scheduler=scheduler,
            progress_reporter=reporter,
            resources_per_trial=self.resources_per_trial,
            name=experiment_name,
            callbacks=[TensorboardCallback()],
        )

        self.results = result

        best_trial = result.get_best_trial(self.optimization_metric, "max", "last")
        print(f"Best trial config: {best_trial.config}")
        print(
            f"Best trial final {self.optimization_metric}: {best_trial.last_result[self.optimization_metric]}"
        )

        # Save best configuration
        best_config = best_trial.config
        os.makedirs("./optimization_results", exist_ok=True)
        with open(
            f"./optimization_results/{experiment_name}_best_config.json", "w"
        ) as f:
            json.dump(best_config, f, indent=2)

        return best_config

    def run_pbt(self, experiment_name: str = "ppo_pbt") -> Dict[str, Any]:
        """Run Population Based Training for dynamic hyperparameter optimization."""
        search_space = self._get_search_space()

        # Define hyperparameters that PBT can change during training
        hyperparam_mutations = {
            "learning_rate": tune.loguniform(1e-5, 1e-3),
            "batch_size": [32, 64, 128, 256],
            "clip_ratio": tune.uniform(0.1, 0.3),
            "value_coeff": tune.uniform(0.3, 0.7),
            "entropy_coeff": tune.loguniform(1e-4, 1e-2),
        }

        scheduler = PopulationBasedTraining(
            time_attr="training_iteration",
            metric=self.optimization_metric,
            mode="max",
            perturbation_interval=5,
            hyperparam_mutations=hyperparam_mutations,
        )

        reporter = CLIReporter(
            metric_columns=[
                self.optimization_metric,
                "episode_reward_mean",
                "training_loss",
            ],
            parameter_columns=["learning_rate", "batch_size", "entropy_coeff"],
        )

        result = tune.run(
            self._train_and_evaluate,
            config=search_space,
            num_samples=10,  # Population size
            scheduler=scheduler,
            progress_reporter=reporter,
            resources_per_trial=self.resources_per_trial,
            name=experiment_name,
            callbacks=[TensorboardCallback()],
        )

        self.results = result

        best_trial = result.get_best_trial(self.optimization_metric, "max", "last")
        print(f"Best trial config: {best_trial.config}")
        print(
            f"Best trial final {self.optimization_metric}: {best_trial.last_result[self.optimization_metric]}"
        )

        # Save best configuration
        best_config = best_trial.config
        os.makedirs("./optimization_results", exist_ok=True)
        with open(
            f"./optimization_results/{experiment_name}_best_config.json", "w"
        ) as f:
            json.dump(best_config, f, indent=2)

        return best_config

    def visualize_optimization_results(
        self, top_n: int = 5, save_path: Optional[str] = None
    ):
        """Visualize the results of hyperparameter optimization."""
        if self.results is None:
            print("No optimization results available. Run optimization first.")
            return

        # Get dataframe of results
        df = self.results.dataframe()

        # Sort by optimization metric
        df = df.sort_values(by=self.optimization_metric, ascending=False)

        # Select top N trials
        top_trials = df.head(top_n)

        # Plot key metrics
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))

        # Plot optimization metric
        axes[0, 0].bar(range(len(top_trials)), top_trials[self.optimization_metric])
        axes[0, 0].set_title(f"Top {top_n} Trials by {self.optimization_metric}")
        axes[0, 0].set_xticks(range(len(top_trials)))
        axes[0, 0].set_xticklabels([f"Trial {i}" for i in range(len(top_trials))])

        # Plot learning rates
        axes[0, 1].bar(range(len(top_trials)), top_trials["config/learning_rate"])
        axes[0, 1].set_title("Learning Rates")
        axes[0, 1].set_xticks(range(len(top_trials)))
        axes[0, 1].set_xticklabels([f"Trial {i}" for i in range(len(top_trials))])

        # Plot batch sizes
        axes[1, 0].bar(range(len(top_trials)), top_trials["config/batch_size"])
        axes[1, 0].set_title("Batch Sizes")
        axes[1, 0].set_xticks(range(len(top_trials)))
        axes[1, 0].set_xticklabels([f"Trial {i}" for i in range(len(top_trials))])

        # Plot entropy coefficients
        axes[1, 1].bar(range(len(top_trials)), top_trials["config/entropy_coeff"])
        axes[1, 1].set_title("Entropy Coefficients")
        axes[1, 1].set_xticks(range(len(top_trials)))
        axes[1, 1].set_xticklabels([f"Trial {i}" for i in range(len(top_trials))])

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path)

        plt.show()

        # Print summary of top configurations
        print(f"\nTop {top_n} Configurations:")
        for i, (idx, row) in enumerate(top_trials.iterrows()):
            print(f"\nRank {i+1} (Trial {idx}):")
            print(f"  {self.optimization_metric}: {row[self.optimization_metric]:.4f}")
            print(
                f"  Network: {row['config/hidden_layers']}, {row['config/activation']}"
            )
            print(f"  Learning rate: {row['config/learning_rate']:.6f}")
            print(f"  Batch size: {row['config/batch_size']}")


class AdvancedPolicyNetworks:
    """Implements advanced policy network architectures for RL trading."""

    @staticmethod
    def create_mlp(
        input_shape: Tuple[int],
        output_dim: int,
        hidden_layers: List[int],
        activation: str = "tanh",
        dropout_rate: Optional[float] = None,
        layer_norm: bool = True,
        output_activation: Optional[str] = None,
    ) -> tf.keras.Model:
        """Create a multi-layer perceptron policy network."""
        inputs = tf.keras.Input(shape=input_shape)
        x = inputs

        # Hidden layers
        for units in hidden_layers:
            x = tf.keras.layers.Dense(units)(x)
            if layer_norm:
                x = tf.keras.layers.LayerNormalization()(x)
            x = tf.keras.layers.Activation(activation)(x)
            if dropout_rate is not None:
                x = tf.keras.layers.Dropout(dropout_rate)(x)

        # Output layer
        if output_activation:
            outputs = tf.keras.layers.Dense(output_dim, activation=output_activation)(x)
        else:
            outputs = tf.keras.layers.Dense(output_dim)(x)

        model = tf.keras.Model(inputs=inputs, outputs=outputs)
        return model

    @staticmethod
    def create_lstm_policy(
        input_shape: Tuple[int],
        output_dim: int,
        lstm_units: int = 64,
        hidden_layers: List[int] = None,
        dropout_rate: Optional[float] = None,
        layer_norm: bool = True,
        output_activation: Optional[str] = None,
    ) -> tf.keras.Model:
        """Create an LSTM-based policy network for time series data."""
        hidden_layers = hidden_layers or [32]

        # Reshape input if needed
        inputs = tf.keras.Input(shape=input_shape)

        # If input is not 3D (batch, time, features), reshape it
        if len(input_shape) < 2:
            # Assume last 10 steps for time dimension
            time_steps = 10
            x = tf.keras.layers.Reshape((-1, time_steps))(inputs)
        else:
            x = inputs

        # LSTM layer
        x = tf.keras.layers.LSTM(lstm_units, return_sequences=False)(x)
        if dropout_rate is not None:
            x = tf.keras.layers.Dropout(dropout_rate)(x)

        # Additional dense layers
        for units in hidden_layers:
            x = tf.keras.layers.Dense(units)(x)
            if layer_norm:
                x = tf.keras.layers.LayerNormalization()(x)
            x = tf.keras.layers.Activation("tanh")(x)
            if dropout_rate is not None:
                x = tf.keras.layers.Dropout(dropout_rate)(x)

        # Output layer
        if output_activation:
            outputs = tf.keras.layers.Dense(output_dim, activation=output_activation)(x)
        else:
            outputs = tf.keras.layers.Dense(output_dim)(x)

        model = tf.keras.Model(inputs=inputs, outputs=outputs)
        return model

    @staticmethod
    def create_attention_policy(
        input_shape: Tuple[int],
        output_dim: int,
        num_heads: int = 4,
        key_dim: int = 32,
        ff_dim: int = 64,
        dropout_rate: Optional[float] = 0.1,
        output_activation: Optional[str] = None,
    ) -> tf.keras.Model:
        """Create a transformer-based policy network with attention mechanism."""
        inputs = tf.keras.Input(shape=input_shape)

        # Reshape input if needed for attention (needs 3D input)
        if len(input_shape) < 2:
            # Assume each feature is a token and reshape to (batch, tokens, features)
            x = tf.keras.layers.Reshape((input_shape[0], 1))(inputs)
        else:
            x = inputs

        # Add positional encoding
        x = tf.keras.layers.LayerNormalization(epsilon=1e-6)(x)

        # Multi-head attention block
        attn_output = tf.keras.layers.MultiHeadAttention(
            num_heads=num_heads, key_dim=key_dim
        )(x, x)
        attn_output = tf.keras.layers.Dropout(dropout_rate)(attn_output)
        x = tf.keras.layers.LayerNormalization(epsilon=1e-6)(x + attn_output)

        # Feed Forward network
        ffn_output = tf.keras.layers.Dense(ff_dim, activation="relu")(x)
        ffn_output = tf.keras.layers.Dense(x.shape[-1])(ffn_output)
        ffn_output = tf.keras.layers.Dropout(dropout_rate)(ffn_output)
        x = tf.keras.layers.LayerNormalization(epsilon=1e-6)(x + ffn_output)

        # Global pooling to get a fixed-length representation
        x = tf.keras.layers.GlobalAveragePooling1D()(x)

        # Final output layer
        if output_activation:
            outputs = tf.keras.layers.Dense(output_dim, activation=output_activation)(x)
        else:
            outputs = tf.keras.layers.Dense(output_dim)(x)

        model = tf.keras.Model(inputs=inputs, outputs=outputs)
        return model


class MarketRegimePolicySelector:
    """
    Policy selector that chooses between different policies based on
    detected market regime (trending, ranging, volatile).
    """

    def __init__(
        self,
        env: ForexTradingEnv,
        policies: Dict[str, WaveTradingAgent],
        regime_detector: Callable[[np.ndarray], str],
    ):
        """
        Initialize the market regime policy selector.

        Args:
            env: The trading environment
            policies: Dict mapping regime names to policy agents
            regime_detector: Function that takes environment state and returns regime name
        """
        self.env = env
        self.policies = policies
        self.regime_detector = regime_detector
        self.current_policy = None
        self.current_regime = None
        self.regime_history = []

    def select_policy(self, state: np.ndarray) -> WaveTradingAgent:
        """Select the appropriate policy based on the current market regime."""
        regime = self.regime_detector(state)

        if regime != self.current_regime:
            print(f"Market regime changed from {self.current_regime} to {regime}")
            self.current_regime = regime
            self.current_policy = self.policies[regime]
            self.regime_history.append((len(self.regime_history), regime))

        return self.current_policy

    def act(self, state: np.ndarray) -> Tuple[int, Dict[str, Any]]:
        """Select action using the appropriate policy for the current market regime."""
        policy = self.select_policy(state)
        action, info = policy.act(state)
        info["regime"] = self.current_regime
        return action, info

    def train(self, epochs: int = 100, batch_size: int = 64) -> Dict[str, List[float]]:
        """Train all policies on their respective market regimes."""
        all_metrics = {}

        for regime, policy in self.policies.items():
            print(f"Training policy for {regime} market regime...")
            # Filter training data for this regime
            # This would require modification to the environment to support filtering
            # by market regime, which is not implemented in this example
            metrics = train_agent(
                agent=policy,
                env=self.env,  # Ideally, we'd use a filtered version of the env
                epochs=epochs,
                batch_size=batch_size,
            )
            all_metrics[regime] = metrics

        return all_metrics

    def plot_regime_transitions(self, save_path: Optional[str] = None):
        """Plot the history of regime transitions."""
        regimes = [r for _, r in self.regime_history]
        indices = [i for i, _ in self.regime_history]

        if not regimes:
            print("No regime transitions recorded.")
            return

        plt.figure(figsize=(12, 6))
        # Convert regimes to numeric values for plotting
        regime_types = list(set(regimes))
        regime_values = [regime_types.index(r) for r in regimes]

        plt.plot(indices, regime_values, "b-", marker="o")
        plt.yticks(range(len(regime_types)), regime_types)
        plt.xlabel("Time Steps")
        plt.ylabel("Market Regime")
        plt.title("Market Regime Transitions")
        plt.grid(True)

        if save_path:
            plt.savefig(save_path)

        plt.show()


def detect_market_regime(
    state: np.ndarray, volatility_threshold: float = 1.5, trend_threshold: float = 0.6
) -> str:
    """
    Detect the current market regime based on state features.

    Args:
        state: Environment state including price and indicators
        volatility_threshold: Threshold for detecting volatile regime
        trend_threshold: Threshold for detecting trending regime

    Returns:
        String indicating the detected regime: 'trending', 'ranging', or 'volatile'
    """
    # Extract relevant features from state
    # This is a simplified example - in practice, you would use more sophisticated
    # features from the state and might include indicators like ADX, ATR, etc.

    # For illustration, let's assume state contains:
    # - Recent price changes at index 0
    # - Volatility measure (e.g., ATR) at index 1
    # - Trend strength (e.g., ADX) at index 2

    # In a real implementation, you would adapt this to the actual state representation
    try:
        recent_volatility = np.abs(state[1])
        trend_strength = np.abs(state[2])

        if recent_volatility > volatility_threshold:
            return "volatile"
        elif trend_strength > trend_threshold:
            return "trending"
        else:
            return "ranging"
    except (IndexError, TypeError):
        # Fallback if state doesn't have the expected structure
        return "ranging"  # Default to ranging regime


# Example usage
if __name__ == "__main__":
    # Example configuration
    env_config = {
        "data_path": "path/to/forex_data.csv",
        "window_size": 60,
        "features": ["close", "volume", "rsi", "macd"],
        "reward_type": "sharpe",
    }

    base_agent_config = {
        "learning_rate": 3e-4,
        "hidden_layers": [64, 64],
        "batch_size": 64,
    }

    # Create optimizer
    optimizer = PolicyOptimizer(
        env_config=env_config,
        base_agent_config=base_agent_config,
        optimization_metric="sharpe_ratio",
        max_trials=20,
    )

    # Run grid search
    best_config = optimizer.run_grid_search(experiment_name="ppo_forex_optimization")

    # Visualize results
    optimizer.visualize_optimization_results(
        top_n=5, save_path="./optimization_results/top_configs.png"
    )
