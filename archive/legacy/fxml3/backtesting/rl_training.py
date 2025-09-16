"""Training utilities for reinforcement learning agents."""

import os
import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import Dict, List, Optional, Tuple, Union, Any

from fxml3.backtesting.rl_environment import ForexTradingEnv
from fxml3.backtesting.rl_agent import WaveTradingAgent, SimpleTradingAgent


def train_agent(
    env: ForexTradingEnv,
    agent: WaveTradingAgent,
    num_episodes: int = 100,
    max_steps_per_episode: int = 1000,
    exploration_fraction: float = 0.3,
    log_frequency: int = 10,
    save_frequency: int = 25,
    render: bool = False,
) -> Tuple[List[float], Dict[str, List[float]]]:
    """Train an RL agent on a trading environment.
    
    Args:
        env: Trading environment
        agent: RL agent to train
        num_episodes: Number of episodes to train for
        max_steps_per_episode: Maximum steps per episode
        exploration_fraction: Fraction of training to explore
        log_frequency: Episodes between logging
        save_frequency: Episodes between model saving
        render: Whether to render the environment
        
    Returns:
        Tuple of (episode rewards, training metrics)
    """
    # Initialize tracking variables
    episode_rewards = []
    metrics = {
        "actor_loss": [],
        "critic_loss": [],
        "entropy": [],
    }
    
    print(f"Starting training for {num_episodes} episodes...")
    
    # Track overall start time
    start_time = time.time()
    
    for episode in range(num_episodes):
        # Reset the environment and get initial state
        state, info = env.reset()
        
        # Track episode data
        episode_reward = 0
        steps = 0
        
        # Calculate exploration probability (linear decay)
        exploration_prob = max(
            0.05,  # Minimum exploration probability
            1.0 - episode / (num_episodes * exploration_fraction)
        )
        
        # Episode loop
        for step in range(max_steps_per_episode):
            # Choose action: explore or exploit
            if np.random.random() < exploration_prob:
                # Random action for exploration
                action = np.random.uniform(-1, 1, size=(env.action_space.shape[0],))
            else:
                # Use agent policy for exploitation
                action = agent.act(state, deterministic=False)
            
            # Take a step in the environment
            next_state, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated
            
            # Store the transition
            agent.store_transition(state, action, reward, next_state, done)
            
            # Track episode reward
            episode_reward += reward
            
            # Render if requested
            if render:
                env.render()
            
            # Move to the next state
            state = next_state
            steps += 1
            
            # Update agent periodically
            if step % 10 == 0:
                step_metrics = agent.learn()
                
                # Track metrics
                for key, value in step_metrics.items():
                    if key in metrics:
                        metrics[key].append(value)
            
            # Break if episode is done
            if done:
                break
        
        # Save the final episode reward
        episode_rewards.append(episode_reward)
        
        # Log progress
        if episode % log_frequency == 0 or episode == num_episodes - 1:
            # Calculate elapsed time
            elapsed_time = time.time() - start_time
            minutes, seconds = divmod(elapsed_time, 60)
            
            # Calculate moving averages for smoother metrics
            window_size = min(10, len(episode_rewards))
            avg_reward = np.mean(episode_rewards[-window_size:])
            
            print(f"Episode {episode+1}/{num_episodes} | " +
                  f"Steps: {steps} | " +
                  f"Reward: {episode_reward:.2f} | " +
                  f"Avg(10): {avg_reward:.2f} | " +
                  f"Exploration: {exploration_prob:.2f} | " +
                  f"Time: {int(minutes)}m {int(seconds)}s")
        
        # Save models periodically
        if episode % save_frequency == 0 and episode > 0:
            agent.save_models(prefix=f"ep{episode}")
    
    # Save final model
    agent.save_models(prefix="final")
    
    print(f"Training completed in {time.time() - start_time:.2f} seconds")
    
    return episode_rewards, metrics


def evaluate_agent(
    env: ForexTradingEnv,
    agent: Union[WaveTradingAgent, SimpleTradingAgent],
    num_episodes: int = 10,
    render: bool = False,
) -> Tuple[float, List[float], Dict[str, Any]]:
    """Evaluate an agent's performance on a trading environment.
    
    Args:
        env: Trading environment
        agent: Agent to evaluate
        num_episodes: Number of episodes to evaluate for
        render: Whether to render the environment
        
    Returns:
        Tuple of (mean reward, all rewards, metrics)
    """
    # Initialize tracking variables
    episode_rewards = []
    all_returns = []
    all_balances = []
    all_actions = []
    
    print(f"Evaluating agent for {num_episodes} episodes...")
    
    for episode in range(num_episodes):
        # Reset the environment
        state, info = env.reset()
        
        # Track episode data
        episode_reward = 0
        episode_returns = []
        episode_balances = []
        episode_actions = []
        
        # Episode loop
        done = False
        step = 0
        
        while not done:
            # Choose action (deterministic for evaluation)
            action = agent.act(state, deterministic=True)
            
            # Take a step in the environment
            next_state, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated
            
            # Track episode reward and info
            episode_reward += reward
            episode_returns.append(info.get("return", 0))
            episode_balances.append(info.get("balance", 0))
            episode_actions.append(action[0])  # Assuming 1D action
            
            # Render if requested
            if render:
                env.render()
            
            # Move to the next state
            state = next_state
            step += 1
        
        # Save the episode results
        episode_rewards.append(episode_reward)
        all_returns.append(episode_returns)
        all_balances.append(episode_balances)
        all_actions.append(episode_actions)
        
        print(f"Episode {episode+1}/{num_episodes} | " +
              f"Steps: {step} | " +
              f"Reward: {episode_reward:.2f} | " +
              f"Final Balance: {episode_balances[-1]:.2f}")
    
    # Calculate performance metrics
    mean_reward = np.mean(episode_rewards)
    final_balances = [balances[-1] for balances in all_balances]
    mean_final_balance = np.mean(final_balances)
    
    # Calculate return metrics
    all_episode_returns = [item for sublist in all_returns for item in sublist]
    if all_episode_returns:
        mean_return = np.mean(all_episode_returns)
        sharpe_ratio = np.mean(all_episode_returns) / (np.std(all_episode_returns) + 1e-8)
        max_drawdown = calculate_max_drawdown(all_balances)
    else:
        mean_return = 0
        sharpe_ratio = 0
        max_drawdown = 0
    
    # Prepare metrics dictionary
    metrics = {
        "mean_reward": mean_reward,
        "mean_final_balance": mean_final_balance,
        "mean_return": mean_return,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
        "all_returns": all_returns,
        "all_balances": all_balances,
        "all_actions": all_actions,
    }
    
    print(f"Evaluation results:")
    print(f"Mean Reward: {mean_reward:.2f}")
    print(f"Mean Final Balance: {mean_final_balance:.2f}")
    print(f"Mean Return: {mean_return:.6f}")
    print(f"Sharpe Ratio: {sharpe_ratio:.2f}")
    print(f"Max Drawdown: {max_drawdown:.2%}")
    
    return mean_reward, episode_rewards, metrics


def calculate_max_drawdown(balance_history: List[List[float]]) -> float:
    """Calculate maximum drawdown from balance history.
    
    Args:
        balance_history: List of balance histories per episode
        
    Returns:
        Maximum drawdown as a fraction
    """
    # Combine all balance histories
    all_balances = []
    for balances in balance_history:
        all_balances.extend(balances)
        
    # Calculate drawdowns
    max_so_far = all_balances[0]
    max_drawdown = 0.0
    
    for balance in all_balances:
        max_so_far = max(max_so_far, balance)
        drawdown = (max_so_far - balance) / max_so_far if max_so_far > 0 else 0
        max_drawdown = max(max_drawdown, drawdown)
        
    return max_drawdown


def plot_training_results(
    rewards: List[float],
    metrics: Dict[str, List[float]],
    window_size: int = 10,
    save_path: Optional[str] = None,
) -> None:
    """Plot training results.
    
    Args:
        rewards: List of episode rewards
        metrics: Dictionary of training metrics
        window_size: Window size for moving average
        save_path: Path to save the plot
    """
    # Create figure with subplots
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    
    # Plot rewards
    axes[0, 0].plot(rewards, alpha=0.6, label="Episode Reward")
    
    # Plot smoothed rewards
    if len(rewards) > window_size:
        smoothed_rewards = []
        for i in range(window_size, len(rewards)):
            smoothed_rewards.append(np.mean(rewards[i-window_size:i]))
        axes[0, 0].plot(
            range(window_size, len(rewards)),
            smoothed_rewards,
            label=f"Moving Avg ({window_size})",
            linewidth=2
        )
    
    axes[0, 0].set_title("Episode Rewards")
    axes[0, 0].set_xlabel("Episode")
    axes[0, 0].set_ylabel("Reward")
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)
    
    # Plot actor loss
    if "actor_loss" in metrics and metrics["actor_loss"]:
        axes[0, 1].plot(metrics["actor_loss"], label="Actor Loss", alpha=0.7)
        axes[0, 1].set_title("Actor Loss")
        axes[0, 1].set_xlabel("Update Step")
        axes[0, 1].set_ylabel("Loss")
        axes[0, 1].grid(True, alpha=0.3)
    
    # Plot critic loss
    if "critic_loss" in metrics and metrics["critic_loss"]:
        axes[1, 0].plot(metrics["critic_loss"], label="Critic Loss", alpha=0.7)
        axes[1, 0].set_title("Critic Loss")
        axes[1, 0].set_xlabel("Update Step")
        axes[1, 0].set_ylabel("Loss")
        axes[1, 0].grid(True, alpha=0.3)
    
    # Plot entropy
    if "entropy" in metrics and metrics["entropy"]:
        axes[1, 1].plot(metrics["entropy"], label="Entropy", alpha=0.7)
        axes[1, 1].set_title("Policy Entropy")
        axes[1, 1].set_xlabel("Update Step")
        axes[1, 1].set_ylabel("Entropy")
        axes[1, 1].grid(True, alpha=0.3)
    
    # Add timestamp and overall title
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    plt.suptitle(f"Training Results - {timestamp}", fontsize=16)
    
    plt.tight_layout()
    
    # Save if path provided
    if save_path:
        plt.savefig(save_path)
        print(f"Plot saved to {save_path}")
    
    plt.show()


def plot_evaluation_results(
    metrics: Dict[str, Any],
    save_path: Optional[str] = None,
) -> None:
    """Plot evaluation results.
    
    Args:
        metrics: Dictionary of evaluation metrics
        save_path: Path to save the plot
    """
    # Create figure with subplots
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    
    # Plot balance histories
    for i, balance_history in enumerate(metrics["all_balances"]):
        axes[0, 0].plot(balance_history, alpha=0.3, label=f"Episode {i+1}" if i < 5 else None)
    
    # Plot mean balance
    mean_balance = np.mean(np.array(metrics["all_balances"]), axis=0)
    axes[0, 0].plot(mean_balance, linewidth=2, color="black", label="Mean")
    
    axes[0, 0].set_title("Account Balance")
    axes[0, 0].set_xlabel("Step")
    axes[0, 0].set_ylabel("Balance")
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)
    
    # Plot return histograms
    all_returns = [item for sublist in metrics["all_returns"] for item in sublist]
    axes[0, 1].hist(all_returns, bins=50, alpha=0.7)
    axes[0, 1].set_title("Return Distribution")
    axes[0, 1].set_xlabel("Return")
    axes[0, 1].set_ylabel("Frequency")
    # Add mean and std as text
    if all_returns:
        mean_return = np.mean(all_returns)
        std_return = np.std(all_returns)
        axes[0, 1].axvline(mean_return, color="red", linestyle="dashed", linewidth=2)
        axes[0, 1].text(
            0.05, 0.95,
            f"Mean: {mean_return:.6f}\nStd: {std_return:.6f}",
            transform=axes[0, 1].transAxes,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.7)
        )
    axes[0, 1].grid(True, alpha=0.3)
    
    # Plot action distribution
    all_actions = [item for sublist in metrics["all_actions"] for item in sublist]
    axes[1, 0].hist(all_actions, bins=50, alpha=0.7)
    axes[1, 0].set_title("Action Distribution")
    axes[1, 0].set_xlabel("Action")
    axes[1, 0].set_ylabel("Frequency")
    axes[1, 0].grid(True, alpha=0.3)
    
    # Plot example episode
    if metrics["all_balances"]:
        # Find best episode by final balance
        best_episode = np.argmax([balances[-1] for balances in metrics["all_balances"]])
        
        # Plot balance, actions and returns for this episode
        ax4 = axes[1, 1]
        
        # Twin axis for actions
        ax4_twin = ax4.twinx()
        
        # Plot balance
        balance_line = ax4.plot(
            metrics["all_balances"][best_episode],
            color="blue",
            label="Balance",
            linewidth=2
        )
        
        # Plot actions
        action_line = ax4_twin.plot(
            metrics["all_actions"][best_episode],
            color="green",
            linestyle="--",
            label="Action",
            alpha=0.7
        )
        
        # Add labels and legend
        ax4.set_title(f"Best Episode (#{best_episode+1})")
        ax4.set_xlabel("Step")
        ax4.set_ylabel("Balance")
        ax4_twin.set_ylabel("Action")
        
        # Combine legends
        lines = balance_line + action_line
        labels = [line.get_label() for line in lines]
        ax4.legend(lines, labels, loc="upper left")
        
        ax4.grid(True, alpha=0.3)
    
    # Add overall title with metrics
    title = (
        f"Evaluation Results - "
        f"Mean Reward: {metrics['mean_reward']:.2f}, "
        f"Sharpe: {metrics['sharpe_ratio']:.2f}, "
        f"MDD: {metrics['max_drawdown']:.2%}"
    )
    plt.suptitle(title, fontsize=16)
    
    plt.tight_layout()
    
    # Save if path provided
    if save_path:
        plt.savefig(save_path)
        print(f"Plot saved to {save_path}")
    
    plt.show()


def compare_agents(
    env: ForexTradingEnv,
    agents: Dict[str, Union[WaveTradingAgent, SimpleTradingAgent]],
    num_episodes: int = 10,
) -> Dict[str, Dict[str, Any]]:
    """Compare multiple agents on the same environment.
    
    Args:
        env: Trading environment
        agents: Dictionary mapping agent names to agent instances
        num_episodes: Number of episodes to evaluate each agent
        
    Returns:
        Dictionary with evaluation metrics for each agent
    """
    # Initialize results dictionary
    results = {}
    
    # Evaluate each agent
    for agent_name, agent in agents.items():
        print(f"\nEvaluating agent: {agent_name}")
        
        # Run evaluation
        mean_reward, rewards, metrics = evaluate_agent(
            env=env,
            agent=agent,
            num_episodes=num_episodes,
            render=False
        )
        
        # Store results
        results[agent_name] = {
            "mean_reward": mean_reward,
            "rewards": rewards,
            "metrics": metrics,
        }
    
    # Print comparison summary
    print("\nAgent Comparison:")
    print(f"{'Agent':<20} {'Mean Reward':<15} {'Mean Final Balance':<20} {'Sharpe Ratio':<15} {'Max Drawdown':<15}")
    print("-" * 85)
    
    for agent_name, result in results.items():
        metrics = result["metrics"]
        print(
            f"{agent_name:<20} "
            f"{metrics['mean_reward']:15.2f} "
            f"{metrics['mean_final_balance']:20.2f} "
            f"{metrics['sharpe_ratio']:15.2f} "
            f"{metrics['max_drawdown']:15.2%}"
        )
    
    return results