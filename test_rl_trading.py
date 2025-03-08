#!/usr/bin/env python3
"""Test script for reinforcement learning with Elliott Wave trading."""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from typing import Dict, List

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fxml3.backtesting.rl_environment import ForexTradingEnv
from fxml3.backtesting.rl_agent import WaveTradingAgent, SimpleTradingAgent
from fxml3.backtesting.rl_training import (
    train_agent, evaluate_agent, compare_agents,
    plot_training_results, plot_evaluation_results
)
from fxml3.wave_analysis.elliott_wave import detect_elliott_waves
from fxml3.data_engineering.data_feeds.yahoo_feed import YahooFeed


def prepare_data():
    """Prepare data for the RL environment."""
    print("Loading forex data...")
    
    # Create data directory if it doesn't exist
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        
    # Load data using Yahoo feed
    data_feed = YahooFeed()
    
    # Get EURUSD data for the last 3 years
    symbol = "EURUSD=X"
    start_date = "2022-01-01"
    end_date = datetime.today().strftime("%Y-%m-%d")
    
    # Load data
    try:
        data = data_feed.fetch_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval="1d",  # Daily data
        )
        
        if data is None or len(data) == 0:
            print("Failed to load data from Yahoo Finance")
            print("Using sample data for testing...")
            # Generate sample data
            data = generate_sample_data()
        else:
            print(f"Loaded {len(data)} data points for {symbol}")
    except Exception as e:
        print(f"Error loading data: {str(e)}")
        print("Using sample data for testing...")
        # Generate sample data
        data = generate_sample_data()
    
    return data


def generate_sample_data(n_samples=500):
    """Generate sample data for testing."""
    # Generate timestamps
    timestamps = pd.date_range(
        start="2022-01-01",
        periods=n_samples,
        freq="D"
    )
    
    # Generate price data
    def generate_wave(amplitude, frequency, phase, n):
        return amplitude * np.sin(frequency * np.linspace(0, 2 * np.pi, n) + phase)
    
    # Generate basic trend (random walk with drift)
    trend = np.cumsum(np.random.normal(0.0001, 0.002, n_samples))
    
    # Add waves of different frequencies
    wave1 = generate_wave(0.01, 5, 0, n_samples)  # Short cycle
    wave2 = generate_wave(0.02, 2, 1, n_samples)  # Medium cycle
    wave3 = generate_wave(0.03, 1, 2, n_samples)  # Long cycle
    
    # Combine waves
    price = 1.1 + trend + wave1 + wave2 + wave3
    
    # Generate OHLCV data
    open_price = price
    high_price = price * (1 + np.abs(np.random.normal(0, 0.002, n_samples)))
    low_price = price * (1 - np.abs(np.random.normal(0, 0.002, n_samples)))
    close_price = price * (1 + np.random.normal(0, 0.001, n_samples))
    volume = np.random.randint(1000, 10000, n_samples)
    
    # Create DataFrame
    data = pd.DataFrame({
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
        "volume": volume,
    }, index=timestamps)
    
    return data


def detect_waves(data):
    """Detect Elliott Wave patterns in the data."""
    print("Detecting Elliott Wave patterns...")
    
    # Convert data for wave detection
    wave_data = data.copy()
    
    # Detect waves
    try:
        wave_patterns = detect_elliott_waves(wave_data)
        print(f"Detected {len(wave_patterns)} wave patterns")
    except Exception as e:
        print(f"Error detecting waves: {str(e)}")
        # Generate placeholder wave data
        wave_patterns = generate_placeholder_waves(data)
        print(f"Generated {len(wave_patterns)} placeholder wave patterns")
    
    return wave_patterns


def generate_placeholder_waves(data, n_patterns=10):
    """Generate placeholder wave patterns for testing."""
    # Generate random wave patterns
    wave_patterns = []
    
    # Get data index
    idx = data.index
    data_len = len(data)
    
    # Generate patterns
    for i in range(n_patterns):
        # Random pattern length (5-30% of data)
        pattern_length = np.random.randint(
            int(data_len * 0.05),
            int(data_len * 0.3)
        )
        
        # Random start position
        start_pos = np.random.randint(0, data_len - pattern_length)
        end_pos = start_pos + pattern_length
        
        # Pattern type (70% impulse, 30% corrective)
        if np.random.random() < 0.7:
            pattern_type = "impulse"
            wave_count = np.random.randint(1, 6)  # Wave 1-5
        else:
            pattern_type = "corrective"
            wave_count = np.random.randint(1, 4)  # Wave A-C
        
        # Pattern direction (60% up, 40% down)
        direction = "up" if np.random.random() < 0.6 else "down"
        
        # Create pattern
        pattern = {
            "type": pattern_type,
            "wave_count": wave_count,
            "direction": direction,
            "start_idx": start_pos,
            "end_idx": end_pos,
            "confidence": np.random.uniform(0.5, 0.9),
            "completion_pct": np.random.uniform(0.7, 1.0),
        }
        
        wave_patterns.append(pattern)
    
    return wave_patterns


def test_environment(data, wave_patterns):
    """Test the ForexTradingEnv environment."""
    print("\nTesting trading environment...")
    
    # Create environment
    env = ForexTradingEnv(
        data=data,
        wave_patterns=wave_patterns,
        window_size=20,
        initial_balance=10000.0,
        episode_length=200,
        random_start=True,
    )
    
    # Test reset
    print("Testing environment reset...")
    state, info = env.reset()
    print(f"Initial state shape: {state.shape}")
    
    # Test step with random actions
    print("Testing environment step with random actions...")
    total_reward = 0
    for i in range(10):
        action = np.random.uniform(-1, 1, size=(env.action_space.shape[0],))
        state, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        print(f"Step {i+1}: Action = {action[0]:.4f}, Reward = {reward:.4f}, Balance = {info['balance']:.2f}")
    
    print(f"Total reward after 10 steps: {total_reward:.4f}")
    
    return env


def test_agent(env):
    """Test the WaveTradingAgent."""
    print("\nTesting trading agent...")
    
    # Create agent
    agent = WaveTradingAgent(
        state_dim=env.observation_space.shape[0],
        action_dim=env.action_space.shape[0],
        hidden_dim=64,
        learning_rate=0.0003,
        model_dir="./models",
    )
    
    # Test agent act
    print("Testing agent action selection...")
    state, _ = env.reset()
    action = agent.act(state, deterministic=False)
    print(f"Agent action: {action}")
    
    # Test agent learn
    print("Testing agent learning...")
    
    # Collect some samples
    for i in range(100):
        action = agent.act(state, deterministic=False)
        next_state, reward, terminated, truncated, info = env.step(action)
        done = terminated or truncated
        agent.store_transition(state, action, reward, next_state, done)
        state = next_state
        if done:
            state, _ = env.reset()
    
    # Learn from samples
    metrics = agent.learn()
    print(f"Learning metrics: {metrics}")
    
    return agent


def main():
    """Run the test script."""
    print("Elliott Wave RL Trading Test")
    print("===========================")
    
    # Create models directory if it doesn't exist
    models_dir = os.path.join(os.path.dirname(__file__), "models")
    if not os.path.exists(models_dir):
        os.makedirs(models_dir)
    
    # Prepare data
    data = prepare_data()
    
    # Detect wave patterns
    wave_patterns = detect_waves(data)
    
    # Test environment
    env = test_environment(data, wave_patterns)
    
    # Test agent
    agent = test_agent(env)
    
    # Ask user if they want to run training
    train_model = input("\nRun training? (y/n): ").lower() == 'y'
    
    if train_model:
        # Set up environment for training
        train_env = ForexTradingEnv(
            data=data,
            wave_patterns=wave_patterns,
            window_size=20,
            initial_balance=10000.0,
            episode_length=200,
            random_start=True,
        )
        
        # Train agent
        rewards, metrics = train_agent(
            env=train_env,
            agent=agent,
            num_episodes=30,
            max_steps_per_episode=200,
            log_frequency=1,
            save_frequency=10,
        )
        
        # Plot training results
        plot_training_results(
            rewards=rewards,
            metrics=metrics,
            save_path=os.path.join(models_dir, "training_results.png"),
        )
        
        # Evaluate trained agent
        eval_env = ForexTradingEnv(
            data=data,
            wave_patterns=wave_patterns,
            window_size=20,
            initial_balance=10000.0,
            episode_length=100,
            random_start=False,
        )
        
        mean_reward, rewards, eval_metrics = evaluate_agent(
            env=eval_env,
            agent=agent,
            num_episodes=5,
        )
        
        # Plot evaluation results
        plot_evaluation_results(
            metrics=eval_metrics,
            save_path=os.path.join(models_dir, "evaluation_results.png"),
        )
        
        # Compare with baseline agent
        baseline_agent = SimpleTradingAgent(
            action_dim=env.action_space.shape[0],
        )
        
        comp_env = ForexTradingEnv(
            data=data,
            wave_patterns=wave_patterns,
            window_size=20,
            initial_balance=10000.0,
            episode_length=100,
            random_start=False,
        )
        
        comparison_results = compare_agents(
            env=comp_env,
            agents={
                "PPO Agent": agent,
                "Baseline": baseline_agent,
            },
            num_episodes=3,
        )
    
    print("\nTest completed successfully!")


if __name__ == "__main__":
    main()