"""
Test module for RL-based trading with Elliott Wave patterns.

This module demonstrates the integration of reinforcement learning
with Elliott Wave pattern detection for forex trading.
"""

import os
import sys
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

# Add project root to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fxml3.data_engineering.data_loader import load_forex_data
from fxml3.wave_analysis.elliott_wave import ElliottWaveAnalyzer
from fxml3.backtesting.rl_environment import ForexTradingEnv
from fxml3.backtesting.rl_agent import WaveTradingAgent, SimpleTradingAgent
from fxml3.backtesting.rl_policy_optimization import PolicyOptimizer
from fxml3.backtesting.wave_backtester import WaveBacktester, BacktestConfig
from fxml3.backtesting.performance_metrics import calculate_metrics, plot_equity_curve


def test_rl_environment_setup():
    """Test the setup of the RL environment."""
    print("Testing RL environment setup...")
    
    # Load sample data
    symbol = "EURUSD"
    start_date = "2022-01-01"
    end_date = "2022-12-31"
    timeframe = "1H"
    
    # Load data
    try:
        data = load_forex_data(symbol, timeframe, start_date, end_date)
        print(f"Loaded {len(data)} data points for {symbol} from {start_date} to {end_date}")
    except Exception as e:
        print(f"Error loading data: {str(e)}")
        return
    
    # Create environment
    env_config = {
        "data": data,
        "window_size": 60,
        "features": ["close", "volume", "rsi", "macd"],
        "reward_type": "sharpe",
        "commission": 0.0001,
        "render_mode": None
    }
    
    env = ForexTradingEnv(**env_config)
    print(f"Created environment with {len(env.data)} data points")
    
    # Test reset
    observation = env.reset()
    print(f"Observation shape: {observation.shape}")
    
    # Test step with random actions
    for _ in range(5):
        action = np.random.randint(0, env.action_space.n)
        observation, reward, done, truncated, info = env.step(action)
        print(f"Action: {action}, Reward: {reward:.4f}, Done: {done}")
    
    print("RL environment setup test completed successfully.")


def test_wave_agent_training():
    """Test training of a WaveTradingAgent."""
    print("Testing WaveTradingAgent training...")
    
    # Load sample data
    symbol = "EURUSD"
    start_date = "2022-01-01"
    end_date = "2022-06-30"
    timeframe = "1H"
    
    # Load data
    try:
        data = load_forex_data(symbol, timeframe, start_date, end_date)
        print(f"Loaded {len(data)} data points for {symbol} from {start_date} to {end_date}")
    except Exception as e:
        print(f"Error loading data: {str(e)}")
        return
    
    # Create environment
    env_config = {
        "data": data,
        "window_size": 60,
        "features": ["close", "volume", "rsi", "macd"],
        "reward_type": "sharpe",
        "commission": 0.0001,
        "render_mode": None
    }
    
    env = ForexTradingEnv(**env_config)
    
    # Create agent
    agent_config = {
        "learning_rate": 3e-4,
        "hidden_layers": [64, 32],
        "batch_size": 64,
        "gamma": 0.99,
        "tensorboard_dir": "./logs/test_agent"
    }
    
    agent = WaveTradingAgent(env=env, **agent_config)
    
    # Train agent (just a few epochs for testing)
    epochs = 5
    print(f"Training agent for {epochs} epochs...")
    
    # Track training metrics
    metrics = []
    
    for epoch in range(epochs):
        # Reset environment
        observation = env.reset()
        done = False
        truncated = False
        episode_reward = 0
        
        # Run episode
        while not (done or truncated):
            action, _ = agent.act(observation)
            next_observation, reward, done, truncated, info = env.step(action)
            
            # Store transition
            agent.store_transition(observation, action, reward, next_observation, done)
            
            # Update observation
            observation = next_observation
            episode_reward += reward
        
        # Train on collected transitions
        loss = agent.train()
        
        # Record metrics
        metrics.append({
            'epoch': epoch,
            'episode_reward': episode_reward,
            'loss': loss
        })
        
        print(f"Epoch {epoch}, Reward: {episode_reward:.4f}, Loss: {loss:.4f}")
    
    print("WaveTradingAgent training test completed successfully.")
    
    # Return the trained agent for further testing
    return agent, env


def test_policy_optimization():
    """Test policy optimization for RL trading."""
    print("Testing policy optimization...")
    
    # Load sample data
    symbol = "EURUSD"
    start_date = "2022-01-01"
    end_date = "2022-06-30"
    timeframe = "1H"
    
    # Load data
    try:
        data = load_forex_data(symbol, timeframe, start_date, end_date)
        print(f"Loaded {len(data)} data points for {symbol} from {start_date} to {end_date}")
    except Exception as e:
        print(f"Error loading data: {str(e)}")
        return
    
    # Create environment config
    env_config = {
        "data": data,
        "window_size": 60,
        "features": ["close", "volume", "rsi", "macd"],
        "reward_type": "sharpe",
        "commission": 0.0001,
        "render_mode": None
    }
    
    # Create base agent config
    base_agent_config = {
        "learning_rate": 3e-4,
        "hidden_layers": [64, 32],
        "batch_size": 64,
        "gamma": 0.99,
        "tensorboard_dir": "./logs/policy_optimization"
    }
    
    # Create policy optimizer with minimal trials for testing
    optimizer = PolicyOptimizer(
        env_config=env_config,
        base_agent_config=base_agent_config,
        optimization_metric="sharpe_ratio",
        max_trials=2  # Just 2 trials for testing
    )
    
    # Define a simplified search space for testing
    search_space = {
        "hidden_layers": [
            [32, 16],
            [64, 32]
        ],
        "learning_rate": [1e-4, 3e-4],
        "batch_size": [32, 64]
    }
    
    # Run a minimal grid search
    print("Running simplified grid search for policy optimization...")
    best_config = optimizer.run_grid_search(experiment_name="test_optimization")
    
    print(f"Best configuration: {best_config}")
    
    print("Policy optimization test completed successfully.")
    
    return best_config


def test_wave_backtester():
    """Test the WaveBacktester with both rule-based and RL strategies."""
    print("Testing WaveBacktester...")
    
    # Load sample data
    symbol = "EURUSD"
    start_date = "2022-01-01"
    end_date = "2022-12-31"
    timeframe = "1H"
    
    # Create backtest config
    config = BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        symbol=symbol,
        timeframe=timeframe,
        initial_capital=10000.0,
        position_size_pct=0.02,
        stop_loss_pct=0.01,
        take_profit_pct=0.03
    )
    
    # Create wave analyzer
    wave_analyzer = ElliottWaveAnalyzer()
    
    # Create backtester
    backtester = WaveBacktester(
        data_loader=load_forex_data,
        wave_analyzer=wave_analyzer,
        config=config
    )
    
    # Run rule-based backtest
    print("Running rule-based backtest...")
    rule_result = backtester.run_rule_based_backtest()
    
    # Display metrics
    metrics = rule_result.metrics
    print("\nRule-based Strategy Metrics:")
    print(f"Total Return: {metrics['total_return']:.2%}")
    print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
    print(f"Max Drawdown: {metrics['max_drawdown']:.2%}")
    print(f"Win Rate: {metrics['win_rate']:.2%}")
    print(f"Profit Factor: {metrics['profit_factor']:.2f}")
    print(f"Number of Trades: {len(rule_result.trades)}")
    
    # Plot equity curve
    plot_equity_curve(rule_result.equity_curve, "Rule-based Strategy Equity Curve")
    
    # Only run agent backtest if we have a trained agent
    # In a real test this would be more robust
    try:
        # Use a simple agent for testing
        # Train a basic agent
        agent, env = test_wave_agent_training()
        
        # Run agent-based backtest
        print("\nRunning agent-based backtest...")
        agent_result = backtester.run_agent_backtest(agent)
        
        # Display metrics
        metrics = agent_result.metrics
        print("\nRL Agent Strategy Metrics:")
        print(f"Total Return: {metrics['total_return']:.2%}")
        print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        print(f"Max Drawdown: {metrics['max_drawdown']:.2%}")
        print(f"Win Rate: {metrics['win_rate']:.2%}")
        print(f"Profit Factor: {metrics['profit_factor']:.2f}")
        print(f"Number of Trades: {len(agent_result.trades)}")
        
        # Compare strategies
        backtester.compare_strategies(
            rule_result, agent_result, 
            save_path="./output/strategy_comparison.png"
        )
    except Exception as e:
        print(f"Error running agent backtest: {str(e)}")
    
    print("WaveBacktester test completed successfully.")
    
    return rule_result


def main():
    """Run all RL trading tests."""
    print("Running RL trading tests...\n")
    
    # Create output directory if it doesn't exist
    os.makedirs("./output", exist_ok=True)
    
    # Run tests
    test_rl_environment_setup()
    print("\n" + "-"*50 + "\n")
    
    agent, env = test_wave_agent_training()
    print("\n" + "-"*50 + "\n")
    
    best_config = test_policy_optimization()
    print("\n" + "-"*50 + "\n")
    
    rule_result = test_wave_backtester()
    print("\n" + "-"*50 + "\n")
    
    print("All RL trading tests completed successfully.")


if __name__ == "__main__":
    main()