"""Tests for EnhancedWaveSignalGenerator.

This module tests the enhanced Elliott Wave signal generator that uses
sentiment-enhanced pattern validation for signal generation.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

# Avoid importing SentimentWaveValidator which has external dependencies
# from fxml4.wave_analysis.sentiment_wave_validator import SentimentWaveValidator
from fxml4.strategy.enhanced_wave_signal_generator import EnhancedWaveSignalGenerator
from fxml4.strategy.integrated_strategy import SignalSource, SignalType
from fxml4.wave_analysis.elliott_wave import (
    ElliottWaveAnalyzer,
    ElliottWavePattern,
    WavePosition,
    WaveType,
)


class MockSentimentWaveValidator:
    """Mock SentimentWaveValidator for testing."""

    def __init__(self):
        self.wave_analyzer = MagicMock()

    def analyze_with_sentiment(self, price_data, news_data=None):
        """Return mock analysis results."""
        # Create a pattern similar to what would be returned by the real validator
        impulse_pattern = {
            "wave_type": "IMPULSE",
            "start_idx": 0,
            "end_idx": 90,
            "confidence": 0.75,
            "position": "END",
            "subwaves": [
                {
                    "wave_type": "IMPULSE",
                    "start_idx": 0,
                    "end_idx": 20,
                    "confidence": 0.8,
                    "position": "END",
                },
                {
                    "wave_type": "CORRECTION",
                    "start_idx": 20,
                    "end_idx": 30,
                    "confidence": 0.8,
                    "position": "END",
                },
                {
                    "wave_type": "IMPULSE",
                    "start_idx": 30,
                    "end_idx": 60,
                    "confidence": 0.8,
                    "position": "END",
                },
                {
                    "wave_type": "CORRECTION",
                    "start_idx": 60,
                    "end_idx": 70,
                    "confidence": 0.8,
                    "position": "END",
                },
                {
                    "wave_type": "IMPULSE",
                    "start_idx": 70,
                    "end_idx": 90,
                    "confidence": 0.8,
                    "position": "END",
                },
            ],
        }

        correction_pattern = {
            "wave_type": "CORRECTION",
            "start_idx": 90,
            "end_idx": 150,
            "confidence": 0.7,
            "position": "END",
            "subwaves": [
                {
                    "wave_type": "ZIGZAG",
                    "start_idx": 90,
                    "end_idx": 110,
                    "confidence": 0.8,
                    "position": "END",
                },
                {
                    "wave_type": "CORRECTION",
                    "start_idx": 110,
                    "end_idx": 130,
                    "confidence": 0.75,
                    "position": "END",
                },
                {
                    "wave_type": "ZIGZAG",
                    "start_idx": 130,
                    "end_idx": 150,
                    "confidence": 0.8,
                    "position": "END",
                },
            ],
        }

        # Define validation results
        validation_impulse = {
            "pattern": impulse_pattern,
            "is_valid": True,
            "confidence": 0.8,
            "details": {
                "wave_confidence": 0.75,
                "sentiment_confidence": 0.8,
                "rag_confidence": 0.85,
                "sentiment_score": 0.6,
            },
        }

        validation_correction = {
            "pattern": correction_pattern,
            "is_valid": True,
            "confidence": 0.75,
            "details": {
                "wave_confidence": 0.7,
                "sentiment_confidence": 0.7,
                "rag_confidence": 0.8,
                "sentiment_score": -0.3,
            },
        }

        return {
            "patterns": [impulse_pattern, correction_pattern],
            "validation": [validation_impulse, validation_correction],
            "combined_score": 0.775,
            "sentiment_score": 0.3,
        }


@pytest.fixture
def wave_validator():
    """Create mock wave validator."""
    return MockSentimentWaveValidator()


@pytest.fixture
def signal_generator(wave_validator):
    """Create enhanced wave signal generator."""
    return EnhancedWaveSignalGenerator(
        wave_validator=wave_validator,
        config={"threshold": 0.6, "min_confidence": 0.6, "max_stop_loss_pct": 2.0},
    )


@pytest.fixture
def price_data():
    """Create sample price data."""
    dates = pd.date_range(start="2025-01-01", periods=200, freq="H")
    data = pd.DataFrame(
        {
            "open": np.zeros(200),
            "high": np.zeros(200),
            "low": np.zeros(200),
            "close": np.linspace(100, 130, 200),
            "volume": np.random.randint(100, 1000, 200),
        },
        index=dates,
    )

    # Add highs and lows
    data["high"] = data["close"] + 0.5
    data["low"] = data["close"] - 0.5

    return data


class TestEnhancedWaveSignalGenerator:
    """Test cases for EnhancedWaveSignalGenerator."""

    def test_get_position_type(self, signal_generator):
        """Test position type detection."""
        # Create test pattern
        pattern = ElliottWavePattern(
            wave_type=WaveType.IMPULSE,
            start_idx=0,
            end_idx=100,
            confidence=0.8,
            position=WavePosition.END,
            subwaves=[
                ElliottWavePattern(WaveType.IMPULSE, 0, 20, 0.8),
                ElliottWavePattern(WaveType.CORRECTION, 20, 30, 0.8),
                ElliottWavePattern(WaveType.IMPULSE, 30, 60, 0.8),
                ElliottWavePattern(WaveType.CORRECTION, 60, 70, 0.8),
                ElliottWavePattern(WaveType.IMPULSE, 70, 100, 0.8),
            ],
        )

        # Test position type detection
        position_type = signal_generator._get_position_type(pattern)
        assert position_type == "impulse_end_5"

        # Test with correction pattern
        pattern = ElliottWavePattern(
            wave_type=WaveType.CORRECTION,
            start_idx=0,
            end_idx=100,
            confidence=0.8,
            position=WavePosition.END,
            subwaves=[
                ElliottWavePattern(WaveType.ZIGZAG, 0, 30, 0.8),
                ElliottWavePattern(WaveType.CORRECTION, 30, 60, 0.8),
                ElliottWavePattern(WaveType.ZIGZAG, 60, 100, 0.8),
            ],
        )

        # Test position type detection
        position_type = signal_generator._get_position_type(pattern)
        assert position_type == "correction_end_c"

    def test_calculate_stop_loss_level(self, signal_generator, price_data):
        """Test stop loss calculation."""
        # Create test pattern
        pattern = ElliottWavePattern(
            wave_type=WaveType.CORRECTION,
            start_idx=90,
            end_idx=150,
            confidence=0.7,
            position=WavePosition.END,
            subwaves=[
                ElliottWavePattern(WaveType.ZIGZAG, 90, 110, 0.8),
                ElliottWavePattern(WaveType.CORRECTION, 110, 130, 0.8),
                ElliottWavePattern(WaveType.ZIGZAG, 130, 150, 0.8),
            ],
        )

        # Test long entry stop loss
        stop_loss = signal_generator._calculate_stop_loss_level(
            pattern=pattern,
            price_data=price_data,
            combined_confidence=0.75,
            signal_type=SignalType.ENTRY_LONG,
        )

        # Verify stop loss is below current price
        current_price = price_data["close"].iloc[-1]
        assert stop_loss < current_price

        # Test short entry stop loss
        stop_loss = signal_generator._calculate_stop_loss_level(
            pattern=pattern,
            price_data=price_data,
            combined_confidence=0.75,
            signal_type=SignalType.ENTRY_SHORT,
        )

        # Verify stop loss is above current price
        assert stop_loss > current_price

    @pytest.mark.parametrize(
        "entry_price,stop_loss,signal_type,expected_risk,expected_conservative,expected_moderate,expected_aggressive",
        [
            (100.0, 98.0, SignalType.ENTRY_LONG, 2.0, 103.0, 104.0, 106.0),
            (100.0, 102.0, SignalType.ENTRY_SHORT, 2.0, 97.0, 96.0, 94.0),
        ],
    )
    def test_calculate_take_profit_levels(
        self,
        signal_generator,
        entry_price,
        stop_loss,
        signal_type,
        expected_risk,
        expected_conservative,
        expected_moderate,
        expected_aggressive,
    ):
        """Test take profit calculation."""
        take_profit_levels = signal_generator._calculate_take_profit_levels(
            entry_price=entry_price, stop_loss=stop_loss, signal_type=signal_type
        )

        # Verify take profit levels
        assert len(take_profit_levels) == 3  # conservative, moderate, aggressive

        assert take_profit_levels["conservative"] == expected_conservative
        assert take_profit_levels["moderate"] == expected_moderate
        assert take_profit_levels["aggressive"] == expected_aggressive

    def test_generate_signals(self, signal_generator, price_data):
        """Test signal generation."""
        # Generate signals
        signals = signal_generator.generate_signals(
            data=price_data, symbol="GBPUSD", timeframe="1H"
        )

        # Verify signals were generated
        assert len(signals) > 0

        # Check for correct signal types
        signal_types = [signal.signal_type for signal in signals]

        # We expect signals from both the impulse and correction patterns
        assert SignalType.ENTRY_SHORT in signal_types
        assert SignalType.EXIT_LONG in signal_types

        # Verify signal properties
        for signal in signals:
            # Check source
            assert signal.source == SignalSource.WAVE

            # Check metadata
            assert "wave_pattern" in signal.metadata
            assert "pattern_confidence" in signal.metadata
            assert "sentiment_score" in signal.metadata

            # For entry signals, we should have stop loss and take profit
            if signal.signal_type in [SignalType.ENTRY_LONG, SignalType.ENTRY_SHORT]:
                assert "stop_loss" in signal.metadata
                assert "take_profit" in signal.metadata

                # Verify take profit levels
                take_profit = signal.metadata["take_profit"]
                assert "conservative" in take_profit
                assert "moderate" in take_profit
                assert "aggressive" in take_profit

                # Check that stop loss is correctly positioned
                if signal.signal_type == SignalType.ENTRY_LONG:
                    assert signal.metadata["stop_loss"] < price_data["close"].iloc[-1]
                else:  # SHORT
                    assert signal.metadata["stop_loss"] > price_data["close"].iloc[-1]

    def test_generate_signals_with_news(self, signal_generator, price_data):
        """Test signal generation with news data."""
        # Create sample news data
        news_data = pd.DataFrame(
            {
                "date": pd.date_range(start="2025-01-01", periods=5),
                "headline": ["Positive news"] * 5,
                "content": ["Bullish market outlook"] * 5,
            }
        )

        # Generate signals with news data
        signals = signal_generator.generate_signals(
            data=price_data, news_data=news_data, symbol="GBPUSD", timeframe="1H"
        )

        # Verify signals were generated
        assert len(signals) > 0
