"""
Test utilities and helpers for FXML4 testing.

This module provides common utilities including:
- Mock data generators
- Assertion helpers
- Test data factories
- Common test patterns
- Database test utilities
"""

import json
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pandas as pd
import pytest
import yaml


class MockDataGenerator:
    """Generator for realistic mock data."""

    @staticmethod
    def generate_ohlcv_data(
        symbol: str = "EURUSD",
        start_time: Optional[datetime] = None,
        periods: int = 1000,
        timeframe: str = "1H",
        base_price: float = 1.1000,
        volatility: float = 0.01,
        trend: float = 0.0,
    ) -> pd.DataFrame:
        """Generate realistic OHLCV market data.

        Args:
            symbol: Trading symbol
            start_time: Start timestamp
            periods: Number of periods to generate
            timeframe: Timeframe (e.g., '1H', '4H', '1D')
            base_price: Starting price
            volatility: Price volatility (standard deviation of returns)
            trend: Daily trend (positive for uptrend, negative for downtrend)

        Returns:
            DataFrame with OHLCV data
        """
        if start_time is None:
            start_time = datetime(2024, 1, 1, tzinfo=timezone.utc)

        # Generate timestamps
        timestamps = pd.date_range(start=start_time, periods=periods, freq=timeframe)

        # Generate price series using geometric Brownian motion
        dt = 1.0  # time step
        returns = np.random.normal(trend * dt, volatility * np.sqrt(dt), periods)
        log_prices = np.cumsum(returns)
        prices = base_price * np.exp(log_prices)

        # Generate OHLCV data
        data = []
        for i, (timestamp, close_price) in enumerate(zip(timestamps, prices)):
            # Open price (previous close for first bar)
            open_price = prices[i - 1] if i > 0 else close_price

            # Add intrabar volatility
            intrabar_range = abs(np.random.normal(0, volatility * 0.5))
            high_price = max(
                open_price, close_price
            ) + intrabar_range * np.random.uniform(0.2, 1.0)
            low_price = min(
                open_price, close_price
            ) - intrabar_range * np.random.uniform(0.2, 1.0)

            # Generate volume (log-normal distribution)
            volume = int(np.random.lognormal(mean=9, sigma=0.5))  # ~8000 mean volume

            data.append(
                {
                    "time": timestamp,
                    "symbol": symbol,
                    "open": round(open_price, 5),
                    "high": round(high_price, 5),
                    "low": round(low_price, 5),
                    "close": round(close_price, 5),
                    "volume": volume,
                }
            )

        return pd.DataFrame(data)

    @staticmethod
    def generate_tick_data(
        symbol: str = "EURUSD",
        start_time: Optional[datetime] = None,
        count: int = 1000,
        base_price: float = 1.1000,
        spread: float = 0.0001,
    ) -> List[Dict[str, Any]]:
        """Generate realistic tick data.

        Args:
            symbol: Trading symbol
            start_time: Start timestamp
            count: Number of ticks to generate
            base_price: Base price around which ticks fluctuate
            spread: Bid-ask spread

        Returns:
            List of tick dictionaries
        """
        if start_time is None:
            start_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        ticks = []
        current_price = base_price

        for i in range(count):
            # Increment timestamp by random intervals (1-10 seconds)
            tick_time = start_time + timedelta(seconds=i + np.random.randint(1, 10))

            # Random walk for price
            price_change = np.random.normal(0, 0.0001)
            current_price += price_change

            # Generate bid/ask
            bid_price = current_price - spread / 2
            ask_price = current_price + spread / 2

            # Random size
            size = np.random.randint(100, 2000)

            # Alternate between bid and ask ticks
            tick_type = "bid" if i % 2 == 0 else "ask"
            price = bid_price if tick_type == "bid" else ask_price

            ticks.append(
                {
                    "symbol": symbol,
                    "timestamp": tick_time,
                    "price": round(price, 5),
                    "size": size,
                    "tick_type": tick_type,
                    "source": "mock",
                }
            )

        return ticks

    @staticmethod
    def generate_features_dataframe(
        n_samples: int = 1000,
        n_features: int = 20,
        start_time: Optional[datetime] = None,
        symbol: str = "EURUSD",
    ) -> pd.DataFrame:
        """Generate realistic feature data for ML models.

        Args:
            n_samples: Number of samples
            n_features: Number of features
            start_time: Start timestamp
            symbol: Trading symbol

        Returns:
            DataFrame with feature data
        """
        if start_time is None:
            start_time = datetime(2024, 1, 1, tzinfo=timezone.utc)

        # Generate timestamps
        timestamps = pd.date_range(start=start_time, periods=n_samples, freq="1H")

        # Generate feature data with some realistic relationships
        np.random.seed(42)  # For reproducible test data

        data = {"timestamp": timestamps, "symbol": [symbol] * n_samples}

        # Price-based features
        base_price = 1.1000
        price_changes = np.random.normal(0, 0.001, n_samples)
        prices = base_price + np.cumsum(price_changes)

        # Technical indicators (simplified)
        data["price"] = prices
        data["sma_10"] = pd.Series(prices).rolling(10).mean().fillna(prices[0])
        data["sma_20"] = pd.Series(prices).rolling(20).mean().fillna(prices[0])
        data["rsi_14"] = np.random.uniform(20, 80, n_samples)  # Simplified RSI
        data["macd"] = np.random.normal(0, 0.001, n_samples)
        data["bollinger_upper"] = data["sma_20"] + 2 * pd.Series(prices).rolling(
            20
        ).std().fillna(0.01)
        data["bollinger_lower"] = data["sma_20"] - 2 * pd.Series(prices).rolling(
            20
        ).std().fillna(0.01)

        # Volume features
        data["volume"] = np.random.lognormal(9, 0.5, n_samples).astype(int)
        data["volume_sma"] = (
            pd.Series(data["volume"]).rolling(10).mean().fillna(data["volume"][0])
        )

        # Market microstructure features
        data["spread"] = np.random.uniform(0.0001, 0.0005, n_samples)
        data["tick_count"] = np.random.randint(100, 500, n_samples)

        # Session features
        hours = [ts.hour for ts in timestamps]
        data["london_session"] = [(8 <= h < 17) for h in hours]
        data["ny_session"] = [(13 <= h < 22) for h in hours]
        data["asian_session"] = [(h < 8 or h >= 22) for h in hours]

        # Add additional random features if needed
        for i in range(len(data), n_features + 2):  # +2 for timestamp and symbol
            data[f"feature_{i}"] = np.random.randn(n_samples)

        df = pd.DataFrame(data)
        return df.set_index("timestamp")

    @staticmethod
    def generate_trading_signals(
        count: int = 50, start_time: Optional[datetime] = None, symbol: str = "EURUSD"
    ) -> List[Dict[str, Any]]:
        """Generate realistic trading signals.

        Args:
            count: Number of signals to generate
            start_time: Start timestamp
            symbol: Trading symbol

        Returns:
            List of signal dictionaries
        """
        if start_time is None:
            start_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        signals = []
        signal_types = ["ENTRY_LONG", "ENTRY_SHORT", "EXIT_LONG", "EXIT_SHORT"]
        sources = ["ML", "WAVE", "TECHNICAL", "FUNDAMENTAL"]

        for i in range(count):
            signal_time = start_time + timedelta(hours=i * np.random.randint(1, 6))

            signal = {
                "timestamp": signal_time,
                "symbol": symbol,
                "signal_type": np.random.choice(signal_types),
                "strength": np.random.uniform(0.6, 0.95),
                "source": np.random.choice(sources),
                "timeframe": np.random.choice(["1h", "4h", "1d"]),
                "metadata": {
                    "confidence": np.random.uniform(0.7, 0.9),
                    "features_used": np.random.choice(
                        ["sma", "rsi", "macd", "bollinger"],
                        size=np.random.randint(2, 4),
                    ).tolist(),
                    "model_version": f"v{np.random.randint(1, 5)}.{np.random.randint(0, 10)}",
                },
            }

            signals.append(signal)

        return signals

    @staticmethod
    def generate_backtest_results(
        num_trades: int = 100,
        win_rate: float = 0.6,
        avg_win: float = 0.02,
        avg_loss: float = -0.01,
    ) -> Dict[str, Any]:
        """Generate realistic backtest results.

        Args:
            num_trades: Number of trades
            win_rate: Win rate (0-1)
            avg_win: Average winning trade return
            avg_loss: Average losing trade return

        Returns:
            Dictionary with backtest metrics
        """
        # Generate trade returns
        num_wins = int(num_trades * win_rate)
        num_losses = num_trades - num_wins

        winning_trades = np.random.normal(avg_win, avg_win * 0.3, num_wins)
        losing_trades = np.random.normal(avg_loss, abs(avg_loss) * 0.3, num_losses)

        all_returns = np.concatenate([winning_trades, losing_trades])
        np.random.shuffle(all_returns)

        # Calculate metrics
        total_return = np.sum(all_returns)
        cumulative_returns = np.cumsum(all_returns)
        peak_returns = np.maximum.accumulate(cumulative_returns)
        drawdowns = peak_returns - cumulative_returns
        max_drawdown = np.max(drawdowns)

        # Calculate Sharpe ratio (simplified)
        sharpe_ratio = (
            np.mean(all_returns) / np.std(all_returns) * np.sqrt(252)
            if np.std(all_returns) > 0
            else 0
        )

        # Profit factor
        gross_profit = np.sum(winning_trades)
        gross_loss = abs(np.sum(losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        return {
            "total_return": total_return,
            "total_return_pct": total_return * 100,
            "annual_return": total_return * 2,  # Simplified annualized return
            "max_drawdown": max_drawdown,
            "max_drawdown_pct": max_drawdown * 100,
            "sharpe_ratio": sharpe_ratio,
            "profit_factor": profit_factor,
            "win_rate": win_rate,
            "total_trades": num_trades,
            "winning_trades": num_wins,
            "losing_trades": num_losses,
            "avg_trade": np.mean(all_returns),
            "avg_win": np.mean(winning_trades),
            "avg_loss": np.mean(losing_trades),
            "largest_win": np.max(winning_trades),
            "largest_loss": np.min(losing_trades),
            "trades": all_returns.tolist(),
            "cumulative_returns": cumulative_returns.tolist(),
        }


class TestAssertions:
    """Enhanced assertion helpers for testing."""

    @staticmethod
    def assert_valid_ohlcv(df: pd.DataFrame, strict: bool = True):
        """Assert that OHLCV data is valid.

        Args:
            df: DataFrame with OHLCV data
            strict: Whether to perform strict validation
        """
        assert not df.empty, "OHLCV data should not be empty"

        required_cols = ["open", "high", "low", "close"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        assert not missing_cols, f"Missing required columns: {missing_cols}"

        if strict:
            # Validate OHLC relationships
            assert (df["high"] >= df["open"]).all(), "High should be >= open"
            assert (df["high"] >= df["close"]).all(), "High should be >= close"
            assert (df["low"] <= df["open"]).all(), "Low should be <= open"
            assert (df["low"] <= df["close"]).all(), "Low should be <= close"

            # No negative prices
            for col in required_cols:
                assert (df[col] > 0).all(), f"All {col} prices should be positive"

            # Volume should be non-negative if present
            if "volume" in df.columns:
                assert (df["volume"] >= 0).all(), "Volume should be non-negative"

    @staticmethod
    def assert_performance_within_limits(
        elapsed_time: float,
        max_time: float,
        memory_delta_mb: Optional[float] = None,
        max_memory_mb: Optional[float] = None,
    ):
        """Assert that performance is within acceptable limits.

        Args:
            elapsed_time: Actual elapsed time in seconds
            max_time: Maximum acceptable time in seconds
            memory_delta_mb: Memory usage increase in MB
            max_memory_mb: Maximum acceptable memory increase in MB
        """
        assert (
            elapsed_time <= max_time
        ), f"Operation took {elapsed_time:.3f}s, expected <= {max_time}s"

        if memory_delta_mb is not None and max_memory_mb is not None:
            assert (
                memory_delta_mb <= max_memory_mb
            ), f"Memory increased by {memory_delta_mb:.1f}MB, expected <= {max_memory_mb}MB"

    @staticmethod
    def assert_api_response_valid(
        response,
        expected_status: int = 200,
        required_fields: Optional[List[str]] = None,
        forbidden_fields: Optional[List[str]] = None,
        response_time_limit: Optional[float] = None,
    ):
        """Assert that API response is valid.

        Args:
            response: HTTP response object
            expected_status: Expected status code
            required_fields: Fields that must be present in response
            forbidden_fields: Fields that must not be present in response
            response_time_limit: Maximum response time in seconds
        """
        assert (
            response.status_code == expected_status
        ), f"Expected status {expected_status}, got {response.status_code}: {response.text}"

        if expected_status == 200 and required_fields:
            try:
                data = response.json()
                for field in required_fields:
                    assert (
                        field in data
                    ), f"Required field '{field}' missing from response"

                if forbidden_fields:
                    for field in forbidden_fields:
                        assert (
                            field not in data
                        ), f"Forbidden field '{field}' present in response"
            except json.JSONDecodeError:
                pytest.fail("Response is not valid JSON")

        if response_time_limit and hasattr(response, "elapsed"):
            elapsed = response.elapsed.total_seconds()
            assert (
                elapsed <= response_time_limit
            ), f"Response took {elapsed:.3f}s, expected <= {response_time_limit}s"

    @staticmethod
    def assert_dataframe_schema(
        df: pd.DataFrame,
        expected_columns: List[str],
        expected_types: Optional[Dict[str, str]] = None,
        min_rows: int = 1,
        max_rows: Optional[int] = None,
    ):
        """Assert that DataFrame has expected schema.

        Args:
            df: DataFrame to validate
            expected_columns: List of expected column names
            expected_types: Dict mapping column names to expected data types
            min_rows: Minimum number of rows
            max_rows: Maximum number of rows
        """
        assert not df.empty or min_rows == 0, "DataFrame should not be empty"
        assert (
            len(df) >= min_rows
        ), f"DataFrame has {len(df)} rows, expected >= {min_rows}"

        if max_rows is not None:
            assert (
                len(df) <= max_rows
            ), f"DataFrame has {len(df)} rows, expected <= {max_rows}"

        missing_columns = set(expected_columns) - set(df.columns)
        assert not missing_columns, f"Missing columns: {missing_columns}"

        if expected_types:
            for column, expected_type in expected_types.items():
                if column in df.columns:
                    actual_type = str(df[column].dtype)
                    assert (
                        expected_type in actual_type
                    ), f"Column '{column}' has type {actual_type}, expected {expected_type}"

    @staticmethod
    def assert_no_data_leakage(
        train_data: pd.DataFrame,
        test_data: pd.DataFrame,
        time_column: str = "timestamp",
    ):
        """Assert that there is no data leakage between train and test sets.

        Args:
            train_data: Training data
            test_data: Test data
            time_column: Name of timestamp column
        """
        if time_column in train_data.columns and time_column in test_data.columns:
            max_train_time = train_data[time_column].max()
            min_test_time = test_data[time_column].min()

            assert (
                max_train_time < min_test_time
            ), f"Data leakage detected: training data ends at {max_train_time}, test data starts at {min_test_time}"

        # Check for duplicate indices
        train_indices = set(train_data.index)
        test_indices = set(test_data.index)
        overlap = train_indices.intersection(test_indices)

        assert (
            not overlap
        ), f"Index overlap detected between train and test sets: {len(overlap)} duplicates"


class MockFactories:
    """Factories for creating mock objects."""

    @staticmethod
    def create_mock_database_client():
        """Create a mock database client."""
        mock_client = Mock()

        # Mock connection methods
        mock_client.get_connection.return_value = Mock()
        mock_client.store_tick.return_value = True
        mock_client.store_ticks.return_value = 100
        mock_client.store_candle.return_value = True
        mock_client.store_candles.return_value = 50
        mock_client.get_tick_count.return_value = 1000
        mock_client.get_candle_count.return_value = 100
        mock_client.get_latest_tick.return_value = {
            "time": datetime.now(timezone.utc),
            "symbol": "EURUSD",
            "price": 1.1000,
            "size": 1000,
            "tick_type": "trade",
            "source": "mock",
        }

        # Mock OHLCV data
        sample_data = MockDataGenerator.generate_ohlcv_data(periods=100)
        mock_client.get_ohlcv_data.return_value = sample_data

        return mock_client

    @staticmethod
    def create_mock_ml_model():
        """Create a mock ML model."""
        mock_model = Mock()

        # Mock training methods
        mock_model.fit.return_value = mock_model
        mock_model.train.return_value = mock_model

        # Mock prediction methods
        mock_model.predict.return_value = np.array([0.7])
        mock_model.predict_proba.return_value = np.array([[0.3, 0.7]])
        mock_model.score.return_value = 0.85

        # Mock model properties
        mock_model.feature_importances_ = np.random.rand(10)
        mock_model.is_trained = True
        mock_model.model_type = "random_forest"

        return mock_model

    @staticmethod
    def create_mock_broker_adapter():
        """Create a mock broker adapter."""
        mock_adapter = Mock()

        # Connection methods
        mock_adapter.connect.return_value = True
        mock_adapter.disconnect.return_value = True
        mock_adapter.is_connected.return_value = True

        # Market data methods
        mock_adapter.request_market_data.return_value = True
        mock_adapter.cancel_market_data.return_value = True

        # Trading methods
        mock_adapter.place_order.return_value = {
            "order_id": 12345,
            "status": "Submitted",
            "filled_quantity": 0,
            "avg_fill_price": 0.0,
        }
        mock_adapter.cancel_order.return_value = True
        mock_adapter.get_positions.return_value = []
        mock_adapter.get_account_info.return_value = {
            "total_cash": 10000.0,
            "available_funds": 9500.0,
            "buying_power": 19000.0,
        }

        return mock_adapter

    @staticmethod
    def create_mock_config():
        """Create a mock configuration object."""
        mock_config = Mock()

        # Default configuration values
        config_values = {
            "database.host": "localhost",
            "database.port": 5432,
            "database.name": "fxml4_test",
            "api.host": "0.0.0.0",
            "api.port": 8000,
            "api.debug": True,
            "ml.models_dir": "/tmp/test_models",
            "backtesting.initial_capital": 10000.0,
            "interactive_brokers.host": "127.0.0.1",
            "interactive_brokers.port": 7497,
        }

        mock_config.get.side_effect = lambda key, default=None: config_values.get(
            key, default
        )
        mock_config.get_database_url.return_value = (
            "postgresql://test:test@localhost:5432/fxml4_test"
        )
        mock_config.to_dict.return_value = config_values

        return mock_config


class FileTestHelpers:
    """Helpers for file-based testing."""

    @staticmethod
    @contextmanager
    def temporary_config_file(config_data: Dict[str, Any], file_format: str = "yaml"):
        """Create a temporary configuration file.

        Args:
            config_data: Configuration data to write
            file_format: File format ('yaml' or 'json')

        Yields:
            Path to temporary config file
        """
        suffix = f".{file_format}"

        with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as f:
            if file_format == "yaml":
                yaml.dump(config_data, f)
            elif file_format == "json":
                json.dump(config_data, f)
            else:
                raise ValueError(f"Unsupported format: {file_format}")

            temp_path = f.name

        try:
            yield temp_path
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @staticmethod
    @contextmanager
    def temporary_csv_file(df: pd.DataFrame):
        """Create a temporary CSV file from DataFrame.

        Args:
            df: DataFrame to save

        Yields:
            Path to temporary CSV file
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            temp_path = f.name

        try:
            yield temp_path
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @staticmethod
    @contextmanager
    def temporary_directory():
        """Create a temporary directory.

        Yields:
            Path to temporary directory
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)


# Convenience functions for common test patterns
def skip_if_not_available(module_name: str, reason: str = None):
    """Decorator to skip test if module is not available."""

    def decorator(test_func):
        try:
            __import__(module_name)
            return test_func
        except ImportError:
            return pytest.mark.skip(reason=reason or f"{module_name} not available")(
                test_func
            )

    return decorator


def parametrize_symbols(symbols: List[str] = None):
    """Decorator to parametrize tests with different trading symbols."""
    if symbols is None:
        symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]

    return pytest.mark.parametrize("symbol", symbols)


def parametrize_timeframes(timeframes: List[str] = None):
    """Decorator to parametrize tests with different timeframes."""
    if timeframes is None:
        timeframes = ["1m", "5m", "15m", "1h", "4h", "1d"]

    return pytest.mark.parametrize("timeframe", timeframes)


# Export commonly used classes and functions
__all__ = [
    "MockDataGenerator",
    "TestAssertions",
    "MockFactories",
    "FileTestHelpers",
    "skip_if_not_available",
    "parametrize_symbols",
    "parametrize_timeframes",
]
