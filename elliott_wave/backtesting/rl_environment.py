"""Reinforcement learning environment for forex trading."""

from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

try:
    import gymnasium as gym
except ImportError:
    try:
        import gym
    except ImportError:
        raise ImportError(
            "Neither gymnasium nor gym is installed. "
            "Please install one with: pip install gymnasium"
        )


class ForexTradingEnv(gym.Env):
    """Forex trading environment for reinforcement learning.

    This environment simulates a forex trading environment where an agent
    can take actions (buy, sell, hold) based on Elliott Wave patterns and
    other market features. It tracks account balance, positions, and
    calculates rewards based on trading performance.
    """

    def __init__(
        self,
        data: pd.DataFrame,
        wave_patterns: Optional[List[Dict]] = None,
        sentiment_data: Optional[pd.DataFrame] = None,
        window_size: int = 50,
        initial_balance: float = 10000.0,
        commission: float = 0.0001,  # 1 pip (0.01%)
        max_position: float = 1.0,
        reward_function: str = "sharpe",
        episode_length: Optional[int] = None,
        random_start: bool = True,
    ):
        """Initialize the forex trading environment.

        Args:
            data: DataFrame with OHLCV data for a forex pair
            wave_patterns: Optional list of detected Elliott Wave patterns
            sentiment_data: Optional DataFrame with sentiment data
            window_size: Number of lookback periods for the state
            initial_balance: Starting account balance
            commission: Trading commission (as a fraction)
            max_position: Maximum position size (as a fraction of balance)
            reward_function: Type of reward function to use
            episode_length: Length of each episode (if None, use full data)
            random_start: Whether to start at a random position in the data
        """
        # Store parameters
        self.data = data
        self.wave_patterns = wave_patterns or []
        self.sentiment_data = sentiment_data
        self.window_size = window_size
        self.initial_balance = initial_balance
        self.commission = commission
        self.max_position = max_position
        self.reward_function = reward_function
        self.random_start = random_start

        # Set episode length
        if episode_length is None:
            self.episode_length = len(data) - window_size
        else:
            self.episode_length = min(episode_length, len(data) - window_size)

        # Set up action and observation spaces
        self.action_space = gym.spaces.Box(
            low=np.array([-1.0]),  # -1 = full sell
            high=np.array([1.0]),  # +1 = full buy
            dtype=np.float32,
        )

        # The observation space will be defined based on the features
        self.observation_space = self._define_observation_space()

        # Initialize state variables (will be set in reset())
        self.current_step = 0
        self.current_position = 0.0
        self.current_balance = initial_balance
        self.starting_point = 0
        self.returns_history = []
        self.positions_history = []
        self.balance_history = []

    def _define_observation_space(self) -> gym.spaces.Box:
        """Define the observation space for the environment.

        Returns:
            Box space defining the observation dimensions
        """
        # 1. Price data features (normalized OHLCV)
        price_features = 5

        # 2. Technical indicators
        # Example indicators: RSI, MACD, Bollinger Bands
        tech_features = 10

        # 3. Wave patterns features
        # Current wave, confidence level, pattern type, etc.
        wave_features = 8

        # 4. Sentiment features
        sentiment_features = 3

        # 5. Position and account features
        account_features = 3  # balance, position, unrealized PnL

        # Total features
        total_features = (
            price_features
            + tech_features
            + wave_features
            + sentiment_features
            + account_features
        )

        return gym.spaces.Box(
            low=-np.inf, high=np.inf, shape=(total_features,), dtype=np.float32
        )

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[Dict] = None,
    ) -> Tuple[np.ndarray, Dict]:
        """Reset the environment to an initial state.

        Args:
            seed: Random seed for reproducibility
            options: Additional options for resetting the environment

        Returns:
            Tuple of (initial observation, info dict)
        """
        # Seed the random number generator
        if seed is not None:
            np.random.seed(seed)

        # Reset account and position
        self.current_balance = self.initial_balance
        self.current_position = 0.0

        # Choose a starting point (either random or beginning)
        if self.random_start:
            self.starting_point = np.random.randint(
                self.window_size, len(self.data) - self.episode_length
            )
        else:
            self.starting_point = self.window_size

        # Reset current step relative to starting point
        self.current_step = 0

        # Reset tracking variables
        self.returns_history = []
        self.positions_history = []
        self.balance_history = [self.current_balance]

        # Get initial observation
        observation = self._get_observation()

        # Compatibility with different gym versions
        try:
            # For gymnasium
            return observation, {}
        except ValueError:
            # For older gym versions
            return observation

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, Dict]:
        """Take a step in the environment by executing an action.

        Args:
            action: Action to take (-1 to 1, representing sell to buy)

        Returns:
            Tuple of (new observation, reward, done, info)
        """
        # Get action value (ensure it's a scalar)
        action_value = float(action[0])

        # Calculate the target position (scaled by max_position)
        target_position = action_value * self.max_position

        # Calculate position change
        position_delta = target_position - self.current_position

        # Get current price data
        current_idx = self.starting_point + self.current_step
        current_price = self.data.iloc[current_idx]

        # Use close price for trading
        execution_price = current_price["close"]

        # Calculate trading costs
        trading_cost = abs(position_delta) * execution_price * self.commission

        # Execute the trade
        old_balance = self.current_balance

        # Update position
        self.current_position = target_position

        # Update balance (subtract trading cost)
        self.current_balance -= trading_cost

        # Track position
        self.positions_history.append(self.current_position)

        # Advance to the next time step
        self.current_step += 1

        # Get the next price data
        next_idx = self.starting_point + self.current_step
        next_price = self.data.iloc[next_idx]

        # Calculate market return
        market_return = (next_price["close"] / execution_price) - 1

        # Calculate position return (based on position direction)
        position_return = market_return * self.current_position

        # Update balance based on position return
        position_value = abs(self.current_position) * self.current_balance
        return_value = position_value * position_return
        self.current_balance += return_value

        # Track returns and balance
        self.returns_history.append(position_return)
        self.balance_history.append(self.current_balance)

        # Calculate reward based on specified reward function
        reward = self._calculate_reward(
            old_balance=old_balance,
            new_balance=self.current_balance,
            position_changed=(position_delta != 0),
            action=action_value,
        )

        # Check if episode is done
        done = self.current_step >= self.episode_length or self.current_balance <= 0

        # Get new observation
        observation = self._get_observation()

        # Prepare info dictionary
        info = {
            "balance": self.current_balance,
            "position": self.current_position,
            "return": position_return,
            "step": self.current_step,
        }

        # Compatibility with different gym versions
        try:
            # For gymnasium
            terminated = done
            truncated = False
            return observation, reward, terminated, truncated, info
        except ValueError:
            # For older gym versions
            return observation, reward, done, info

    def _get_observation(self) -> np.ndarray:
        """Construct the observation vector from current state.

        Returns:
            Numpy array with the observation features
        """
        # Get current index in the data
        idx = self.starting_point + self.current_step

        # 1. Price data features (last window_size periods)
        # Normalize price data to avoid large values
        window_data = self.data.iloc[idx - self.window_size : idx]

        # Extract OHLCV data
        ohlcv = window_data[["open", "high", "low", "close", "volume"]].values

        # Normalize by the first close price in the window
        first_close = ohlcv[0, 3]
        normalized_ohlcv = ohlcv / first_close - 1

        # Extract the last row for the current state
        price_features = normalized_ohlcv[-1]

        # 2. Technical indicators
        # Calculate indicators or use precomputed ones
        tech_indicators = self._compute_technical_indicators(window_data)

        # 3. Wave pattern features
        wave_features = self._extract_wave_features(idx)

        # 4. Sentiment features
        sentiment_features = self._extract_sentiment_features(idx)

        # 5. Account state features
        account_features = np.array(
            [
                self.current_balance / self.initial_balance - 1,  # Normalized balance
                self.current_position,  # Current position
                (
                    sum(self.returns_history[-10:])
                    if len(self.returns_history) >= 10
                    else 0
                ),  # Recent returns
            ]
        )

        # Combine all features
        observation = np.concatenate(
            [
                price_features,
                tech_indicators,
                wave_features,
                sentiment_features,
                account_features,
            ]
        )

        return observation.astype(np.float32)

    def _compute_technical_indicators(self, data: pd.DataFrame) -> np.ndarray:
        """Compute technical indicators for the given data window.

        Args:
            data: DataFrame with price data for the window

        Returns:
            Numpy array with technical indicators
        """
        # For a real implementation, compute indicators here
        # Placeholder implementation with random values
        return np.random.randn(10).astype(np.float32)

    def _extract_wave_features(self, idx: int) -> np.ndarray:
        """Extract Elliott Wave pattern features for the current index.

        Args:
            idx: Current index in the data

        Returns:
            Numpy array with wave pattern features
        """
        # Find the most recent wave pattern that includes this index
        relevant_pattern = None
        for pattern in self.wave_patterns:
            # Check if pattern covers the current index
            start_idx = pattern.get("start_idx", 0)
            end_idx = pattern.get("end_idx", 0)

            if start_idx <= idx <= end_idx:
                relevant_pattern = pattern
                break

        # If no pattern found, return zero features
        if relevant_pattern is None:
            return np.zeros(8, dtype=np.float32)

        # Extract features from the pattern
        features = []

        # 1. Pattern type (0 for corrective, 1 for impulse)
        if relevant_pattern.get("type") == "impulse":
            features.append(1.0)
        else:
            features.append(0.0)

        # 2. Wave count (normalized)
        wave_count = relevant_pattern.get("wave_count", 0)
        features.append(wave_count / 5.0)

        # 3. Pattern confidence
        features.append(relevant_pattern.get("confidence", 0.0))

        # 4. Completion percentage
        current_point = idx - relevant_pattern.get("start_idx", 0)
        total_length = relevant_pattern.get("end_idx", 0) - relevant_pattern.get(
            "start_idx", 0
        )
        completion = current_point / total_length if total_length > 0 else 1.0
        features.append(min(1.0, max(0.0, completion)))

        # 5. Current wave direction (1 for up, -1 for down)
        wave_direction = relevant_pattern.get("direction", "up")
        features.append(1.0 if wave_direction == "up" else -1.0)

        # Fill remaining features with zeros
        while len(features) < 8:
            features.append(0.0)

        return np.array(features, dtype=np.float32)

    def _extract_sentiment_features(self, idx: int) -> np.ndarray:
        """Extract sentiment features for the current index.

        Args:
            idx: Current index in the data

        Returns:
            Numpy array with sentiment features
        """
        # If no sentiment data available, return zeros
        if self.sentiment_data is None:
            return np.zeros(3, dtype=np.float32)

        # Get timestamp for current index
        timestamp = self.data.index[idx]

        # Find the closest sentiment data
        closest_idx = self.sentiment_data.index.get_indexer(
            [timestamp], method="nearest"
        )[0]

        if closest_idx < 0 or closest_idx >= len(self.sentiment_data):
            return np.zeros(3, dtype=np.float32)

        sentiment_row = self.sentiment_data.iloc[closest_idx]

        # Extract sentiment features
        # 1. Overall sentiment (-1 to 1)
        overall = sentiment_row.get("weighted_sentiment", 0.0)

        # 2. Sentiment momentum
        momentum = sentiment_row.get("sentiment_momentum", 0.0)

        # 3. Sentiment volatility
        volatility = sentiment_row.get("sentiment_volatility", 0.0)

        return np.array([overall, momentum, volatility], dtype=np.float32)

    def _calculate_reward(
        self,
        old_balance: float,
        new_balance: float,
        position_changed: bool,
        action: float,
    ) -> float:
        """Calculate the reward based on the action and outcome.

        Args:
            old_balance: Balance before the action
            new_balance: Balance after the action
            position_changed: Whether the position changed
            action: The action taken

        Returns:
            Calculated reward value
        """
        # Choose reward function based on configuration
        if self.reward_function == "simple":
            # Simple reward: change in balance
            return new_balance - old_balance

        elif self.reward_function == "sharpe":
            # Sharpe-like reward: balance change adjusted for risk
            return self._calculate_sharpe_reward(new_balance, old_balance)

        elif self.reward_function == "consistency":
            # Consistency reward: encourage following wave patterns
            return self._calculate_consistency_reward(action, new_balance, old_balance)

        else:
            # Default to simple reward
            return new_balance - old_balance

    def _calculate_sharpe_reward(self, new_balance: float, old_balance: float) -> float:
        """Calculate a Sharpe ratio based reward.

        Args:
            new_balance: Balance after the action
            old_balance: Balance before the action

        Returns:
            Sharpe-like reward
        """
        # Calculate return
        returns = (new_balance - old_balance) / old_balance

        # Add to returns history
        self.returns_history.append(returns)

        # Need at least a few returns to calculate Sharpe ratio
        if len(self.returns_history) < 5:
            return returns * 100  # Scale up for initial returns

        # Calculate Sharpe ratio (with simplified assumptions)
        recent_returns = self.returns_history[-30:]  # Consider last 30 steps
        mean_return = np.mean(recent_returns)
        std_return = np.std(recent_returns) + 1e-6  # Avoid division by zero

        sharpe = mean_return / std_return * np.sqrt(252)  # Annualized

        # Scale the reward
        return returns * 100 + sharpe * 10

    def _calculate_consistency_reward(
        self,
        action: float,
        new_balance: float,
        old_balance: float,
    ) -> float:
        """Calculate a reward that encourages consistency with wave patterns.

        Args:
            action: The action taken
            new_balance: Balance after the action
            old_balance: Balance before the action

        Returns:
            Consistency reward
        """
        # Base reward is the balance change
        base_reward = (new_balance - old_balance) / old_balance * 100

        # Get current index
        idx = self.starting_point + self.current_step

        # Extract wave features
        wave_features = self._extract_wave_features(idx)

        # Check if we have valid wave features
        if np.all(wave_features == 0):
            return base_reward

        # Get pattern type and wave count
        pattern_type = wave_features[0]  # 1 for impulse, 0 for corrective
        wave_count = wave_features[1] * 5.0  # Denormalize
        direction = wave_features[4]  # 1 for up, -1 for down

        # Determine expected action based on wave patterns
        expected_action = 0.0

        if pattern_type == 1.0:  # Impulse
            # In impulse waves 1, 3, 5, we expect buying; in 2, 4, selling
            if wave_count in [1, 3, 5]:
                expected_action = 1.0  # Buy in bullish waves
            else:
                expected_action = -1.0  # Sell in bearish waves

            # Adjust for wave direction
            expected_action *= direction

        else:  # Corrective
            # In corrective waves A, C we expect selling; in B buying
            if wave_count in [1, 3]:  # A, C
                expected_action = -1.0  # Sell
            else:  # B
                expected_action = 1.0  # Buy

            # Adjust for wave direction
            expected_action *= direction

        # Calculate consistency bonus
        action_consistency = 1.0 - abs(action - expected_action) / 2.0
        consistency_bonus = action_consistency * 10.0

        # Combine base reward with consistency bonus
        return base_reward + consistency_bonus

    def render(self, mode: str = "human") -> Optional[np.ndarray]:
        """Render the environment's current state.

        Args:
            mode: Rendering mode

        Returns:
            Rendered frame (if mode is 'rgb_array')
        """
        # For now, just print the current state
        current_idx = self.starting_point + self.current_step
        current_price = self.data.iloc[current_idx]["close"]

        print(f"Step: {self.current_step}")
        print(f"Price: {current_price:.5f}")
        print(f"Position: {self.current_position:.2f}")
        print(f"Balance: {self.current_balance:.2f}")
        print("---")

        # Return None for 'human' mode
        return None
