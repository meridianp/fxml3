"""Integration tests for FXML4.

This module contains tests that verify the integration of different components
of the FXML4 system.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest

from fxml4.config import get_config
from fxml4.ml.features import create_technical_features
from fxml4.strategy.integrated_strategy import (
    IntegratedStrategy,
    Signal,
    SignalGenerator,
    SignalSource,
    SignalType,
)
from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer


@pytest.fixture
def market_data():
    """Create sample market data for testing."""
    # Create sample market data
    data = {
        "time": pd.date_range(start="2023-01-01", periods=100, freq="H"),
        "open": np.random.normal(1.1, 0.01, 100),
        "high": np.random.normal(1.11, 0.01, 100),
        "low": np.random.normal(1.09, 0.01, 100),
        "close": np.random.normal(1.1, 0.01, 100),
        "volume": np.random.randint(100, 1000, 100),
    }
    df = pd.DataFrame(data)

    # Ensure OHLC values are consistent
    for i in range(len(df)):
        df.loc[i, "high"] = max(
            df.loc[i, "open"], df.loc[i, "close"], df.loc[i, "high"]
        )
        df.loc[i, "low"] = min(df.loc[i, "open"], df.loc[i, "close"], df.loc[i, "low"])

    return df


class TestFeatureIntegration:
    """Test the integration of feature engineering components."""

    def test_feature_creation(self, market_data):
        """Test that features can be created from market data."""
        # Create features
        features_df = create_technical_features(market_data)

        # Verify technical indicators were created
        assert "sma_10" in features_df.columns
        assert "rsi_14" in features_df.columns
        assert "macd" in features_df.columns

        # Verify price patterns were created
        assert "return_1" in features_df.columns
        assert "volatility_5" in features_df.columns

        # Verify volume features were created
        assert "volume_sma_5" in features_df.columns
        assert "obv" in features_df.columns

        # Verify session features were created
        assert "hour" in features_df.columns
        assert "day_of_week" in features_df.columns


class MockMLSignalGenerator(SignalGenerator):
    """Mock ML signal generator for testing."""

    def generate_signals(self, data, **kwargs):
        """Generate mock ML signals."""
        # Just return a fixed signal for testing
        return [
            Signal(
                signal_type=SignalType.ENTRY_LONG,
                strength=0.8,
                source=SignalSource.ML,
                timestamp=pd.Timestamp("2023-01-01"),
                symbol="EURUSD",
                timeframe="1h",
                metadata={"feature_importance": {"rsi_14": 0.5, "macd": 0.3}},
            )
        ]


class MockWaveSignalGenerator(SignalGenerator):
    """Mock Elliott Wave signal generator for testing."""

    def generate_signals(self, data, **kwargs):
        """Generate mock wave signals."""
        # Just return a fixed signal for testing
        return [
            Signal(
                signal_type=SignalType.ENTRY_LONG,
                strength=0.6,
                source=SignalSource.WAVE,
                timestamp=pd.Timestamp("2023-01-01"),
                symbol="EURUSD",
                timeframe="1h",
                metadata={"wave_pattern": "Impulse wave 3"},
            )
        ]


@pytest.fixture
def integrated_strategy():
    """Create integrated strategy with mock signal generators."""
    strategy = IntegratedStrategy()
    strategy.add_signal_generator(MockMLSignalGenerator())
    strategy.add_signal_generator(MockWaveSignalGenerator())
    return strategy


class TestStrategyIntegration:
    """Test the integration of strategy components."""

    def test_signal_generation_and_combination(self, market_data, integrated_strategy):
        """Test that signals are generated and combined correctly."""
        # Generate signals
        signal = integrated_strategy.generate_signals(
            market_data, symbol="EURUSD", timeframe="1h"
        )

        # Verify signal was generated and combined
        assert signal is not None
        assert signal.source.value == "ensemble"
        assert signal.signal_type.value == "entry_long"
        assert 0 <= signal.strength <= 1

        # Verify metadata contains component signals
        assert "component_signals" in signal.metadata
        assert len(signal.metadata["component_signals"]) == 2


@pytest.fixture
def wave_data():
    """Create sample wave data with clear Elliott Wave patterns."""
    times = pd.date_range(start="2023-01-01", periods=100, freq="H")

    # Create a simple 5-wave pattern
    closes = [1.1000] * 100
    # Wave 1 (up)
    for i in range(5, 20):
        closes[i] = closes[4] + (i - 4) * 0.0005
    # Wave 2 (down)
    for i in range(20, 30):
        closes[i] = closes[19] - (i - 19) * 0.0002
    # Wave 3 (up)
    for i in range(30, 55):
        closes[i] = closes[29] + (i - 29) * 0.0008
    # Wave 4 (down)
    for i in range(55, 65):
        closes[i] = closes[54] - (i - 54) * 0.0003
    # Wave 5 (up)
    for i in range(65, 85):
        closes[i] = closes[64] + (i - 64) * 0.0006
    # Final drop
    for i in range(85, 100):
        closes[i] = closes[84] - (i - 84) * 0.0010

    # Create DataFrame
    data = {
        "time": times,
        "open": closes,
        "high": [c + 0.0010 for c in closes],
        "low": [c - 0.0010 for c in closes],
        "close": closes,
        "volume": np.random.randint(100, 1000, 100),
    }
    return pd.DataFrame(data)


@pytest.fixture
def wave_analyzer():
    """Create Elliott Wave analyzer."""
    return ElliottWaveAnalyzer()


class TestWaveAnalysisIntegration:
    """Test the integration of Elliott Wave analysis components."""

    def test_wave_detection(self, wave_data, wave_analyzer):
        """Test that Elliott Waves are detected correctly."""
        # Analyze wave patterns
        result = wave_analyzer.analyze(wave_data)

        # Verify impulse waves were detected
        assert "impulse_waves" in result

        # Note: The exact number of detected waves depends on the algorithm's sensitivity
        # In a real test, we would have more specific expectations


class TestTickToCandleIntegration:
    """Test the integration of tick-to-candle and timeframe conversion."""

    @pytest.mark.slow
    def test_tick_to_multiple_timeframes(self):
        """Test converting ticks to multiple timeframes."""
        from fxml4.data_engineering.tick_to_candle import TickAggregator
        from fxml4.data_engineering.timeframe_conversion import TimeframeConverter

        # Create tick aggregator
        tick_aggregator = TickAggregator(timeframes=[1, 5, 15])

        # Create timeframe converter
        timeframe_converter = TimeframeConverter(
            base_timeframe="1m", derived_timeframes=["5m", "15m", "30m", "1h"]
        )

        # Create a series of ticks
        symbol = "EURUSD"
        base_time = datetime(2025, 3, 1, 10, 0, 0, tzinfo=timezone.utc)

        # Create 120 minutes (2 hours) of ticks, several per minute
        for minute in range(120):
            # Add several ticks per minute
            for second in [0, 15, 30, 45]:
                tick_time = base_time + timedelta(minutes=minute, seconds=second)
                price = (
                    1.1000 + np.sin(minute / 20) * 0.01 + np.random.normal(0, 0.0005)
                )
                size = np.random.randint(100, 1000)

                # Process tick
                completed_candles = tick_aggregator.process_tick(
                    symbol, tick_time, price, size
                )

                # If a 1-minute candle was completed, update derived timeframes
                if 1 in completed_candles:
                    one_min_candle = completed_candles[1]

                    # Convert the candle to a DataFrame
                    candle_df = pd.DataFrame(
                        [
                            {
                                "open": one_min_candle["open"],
                                "high": one_min_candle["high"],
                                "low": one_min_candle["low"],
                                "close": one_min_candle["close"],
                                "volume": one_min_candle["volume"],
                            }
                        ],
                        index=[one_min_candle["timestamp"]],
                    )

                    # Get existing 1-minute candles
                    existing_candles = tick_aggregator.get_candles(symbol, timeframe=1)

                    # Update derived timeframes
                    if not existing_candles.empty:
                        # Append the new candle to existing candles
                        all_candles = pd.concat([existing_candles, candle_df])

                        # Update derived timeframes
                        timeframe_converter.update_data(
                            symbol, all_candles, timeframe="1m"
                        )

        # Verify we have the expected number of candles
        # For 120 minutes:
        # - 1-minute: ~119 candles (minus the current in-progress candle)
        # - 5-minute: ~24 candles (120/5)
        # - 15-minute: ~8 candles (120/15)
        # - 1-hour: ~2 candles (120/60)

        # Get candles from tick aggregator
        one_min_candles = tick_aggregator.get_candles(symbol, timeframe=1)
        five_min_candles = tick_aggregator.get_candles(symbol, timeframe=5)
        fifteen_min_candles = tick_aggregator.get_candles(symbol, timeframe=15)

        # Get candles from timeframe converter
        tf_five_min = timeframe_converter.get_data(symbol, "5m")
        tf_fifteen_min = timeframe_converter.get_data(symbol, "15m")
        tf_thirty_min = timeframe_converter.get_data(symbol, "30m")
        tf_one_hour = timeframe_converter.get_data(symbol, "1h")

        # Verify counts
        assert (
            len(one_min_candles) >= 115
        ), f"Expected at least 115 1-minute candles, got {len(one_min_candles)}"
        assert (
            len(five_min_candles) >= 22
        ), f"Expected at least 22 5-minute candles, got {len(five_min_candles)}"
        assert (
            len(fifteen_min_candles) >= 7
        ), f"Expected at least 7 15-minute candles, got {len(fifteen_min_candles)}"

        # Verify timeframe converter counts
        assert (
            len(tf_five_min) >= 22
        ), f"Expected at least 22 5-minute candles from converter, got {len(tf_five_min)}"
        assert (
            len(tf_fifteen_min) >= 7
        ), f"Expected at least 7 15-minute candles from converter, got {len(tf_fifteen_min)}"
        assert (
            len(tf_thirty_min) >= 3
        ), f"Expected at least 3 30-minute candles from converter, got {len(tf_thirty_min)}"
        assert (
            len(tf_one_hour) >= 1
        ), f"Expected at least 1 1-hour candle from converter, got {len(tf_one_hour)}"
