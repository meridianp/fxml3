#!/usr/bin/env python
"""Unit tests for enhanced Elliott Wave signal generator."""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pandas as pd
import pytest

sys.path.append(str(Path(__file__).parent.parent.parent))

from scripts.enhanced_elliott_wave_signals import (
    ElliottWaveSignal,
    EnhancedElliottWaveSignalGenerator,
)


@pytest.fixture
def wave_generator():
    """Create enhanced Elliott Wave signal generator."""
    return EnhancedElliottWaveSignalGenerator(
        min_wave_size=0.003,
        confidence_threshold=0.5,
        use_trend_filter=True,
        use_volume_confirmation=True,
    )


@pytest.fixture
def sample_wave_data():
    """Create sample OHLCV data."""
    bars = 200
    dates = pd.date_range(end=datetime.now(), periods=bars, freq="4h")

    # Generate trending data
    base_price = 1.1000
    trend = np.linspace(0, 0.05, bars)  # 5% uptrend
    noise = np.random.normal(0, 0.001, bars)

    close_prices = base_price + trend + noise

    data = pd.DataFrame(
        {
            "open": close_prices + np.random.uniform(-0.0002, 0.0002, bars),
            "high": close_prices + np.abs(np.random.uniform(0, 0.0005, bars)),
            "low": close_prices - np.abs(np.random.uniform(0, 0.0005, bars)),
            "close": close_prices,
            "volume": np.random.uniform(900000, 1100000, bars),
            "rsi_14": 50 + 20 * np.sin(np.linspace(0, 4 * np.pi, bars)),
            "atr_14": np.full(bars, 0.0015),
        },
        index=dates,
    )

    return data


class TestEnhancedElliottWaveSignalGenerator:
    """Test cases for Enhanced Elliott Wave Signal Generator."""

    def test_initialization(self, wave_generator):
        """Test generator initialization."""
        assert wave_generator.min_wave_size == 0.003
        assert wave_generator.confidence_threshold == 0.5
        assert wave_generator.use_trend_filter is True
        assert wave_generator.use_volume_confirmation is True
        assert wave_generator.analyzer is not None

    def test_generate_signals_insufficient_data(self, wave_generator, sample_wave_data):
        """Test signal generation with insufficient data."""
        small_data = sample_wave_data.head(50)
        signal = wave_generator.generate_signals(small_data, lookback=100)
        assert signal is None

    @patch("scripts.enhanced_elliott_wave_signals.ElliottWaveAnalyzer")
    def test_generate_signals_no_patterns(self, mock_analyzer_class, sample_wave_data):
        """Test signal generation when no patterns found."""
        # Mock analyzer to return no patterns
        mock_analyzer = Mock()
        mock_analyzer.analyze.return_value = Mock(waves=[])
        mock_analyzer_class.return_value = mock_analyzer

        generator = EnhancedElliottWaveSignalGenerator()
        signal = generator.generate_signals(sample_wave_data)

        assert signal is None

    def test_determine_trend(self, wave_generator, sample_wave_data):
        """Test trend determination."""
        # Uptrend data
        uptrend_data = sample_wave_data.copy()
        trend = wave_generator._determine_trend(uptrend_data)
        assert trend == "UP"

        # Downtrend data
        downtrend_data = sample_wave_data.copy()
        downtrend_data["close"] = downtrend_data["close"][
            ::-1
        ].values  # Reverse for downtrend
        trend = wave_generator._determine_trend(downtrend_data)
        assert trend == "DOWN"

        # Neutral trend - create data with price between MAs
        neutral_data = sample_wave_data.copy()
        # Set all prices to create specific MA values
        neutral_data["close"] = 1.10

        # Calculate what the MAs will be
        sma_20 = 1.10
        sma_50 = 1.10

        # Now adjust to create neutral condition: current between MAs
        # Set older data lower so SMA50 < current
        neutral_data.iloc[:100, neutral_data.columns.get_loc("close")] = 1.095
        # Set recent data higher so SMA20 > current
        neutral_data.iloc[-20:, neutral_data.columns.get_loc("close")] = 1.105
        # Set current price between them
        neutral_data.iloc[-1, neutral_data.columns.get_loc("close")] = 1.10

        trend = wave_generator._determine_trend(neutral_data)
        assert trend == "NEUTRAL"

    def test_calculate_atr(self, wave_generator, sample_wave_data):
        """Test ATR calculation."""
        # With atr_14 column
        atr = wave_generator._calculate_atr(sample_wave_data)
        assert abs(atr - 0.0015) < 0.0001

        # Without atr_14 column - manual calculation
        data_no_atr = sample_wave_data.drop("atr_14", axis=1)
        atr_manual = wave_generator._calculate_atr(data_no_atr)
        assert atr_manual > 0
        assert atr_manual < 0.01  # Reasonable range for forex

    def test_check_divergence(self, wave_generator, sample_wave_data):
        """Test divergence checking."""
        # Create mock pattern with waves
        mock_pattern = Mock()
        mock_pattern.direction = "UP"
        mock_pattern.waves = [
            {"end_idx": 10},
            {"end_idx": 20},
            {"end_idx": 30},  # Wave 3
            {"end_idx": 40},
            {"end_idx": 50},  # Wave 5
        ]

        # Create data with bearish divergence
        data = sample_wave_data.copy()
        data.loc[data.index[30], "high"] = 1.12
        data.loc[data.index[50], "high"] = 1.13  # Higher high
        data.loc[data.index[30], "rsi_14"] = 70
        data.loc[data.index[50], "rsi_14"] = 65  # Lower RSI

        has_divergence = wave_generator._check_divergence(data, mock_pattern)
        assert has_divergence is True

    @pytest.mark.parametrize(
        "waves,expected",
        [
            # Pattern with equal waves (C = A)
            (
                [
                    {"start_price": 1.10, "end_price": 1.11},  # Wave A: 0.01
                    {"start_price": 1.11, "end_price": 1.105},  # Wave B
                    {"start_price": 1.105, "end_price": 1.115},  # Wave C: 0.01
                ],
                True,
            ),
            # Pattern with 1.618 relationship
            (
                [
                    {"start_price": 1.10, "end_price": 1.11},  # Wave A: 0.01
                    {"start_price": 1.11, "end_price": 1.105},  # Wave B
                    {
                        "start_price": 1.105,
                        "end_price": 1.1212,
                    },  # Wave C: 0.0162 (1.618x)
                ],
                True,
            ),
        ],
    )
    def test_check_abc_completion(
        self, wave_generator, sample_wave_data, waves, expected
    ):
        """Test ABC pattern completion check."""
        pattern = Mock()
        pattern.waves = waves

        is_complete = wave_generator._check_abc_completion(pattern, sample_wave_data)
        assert is_complete == expected

    @patch("scripts.enhanced_elliott_wave_signals.ElliottWaveAnalyzer")
    def test_generate_impulse_signal_wave2(
        self, mock_analyzer_class, wave_generator, sample_wave_data
    ):
        """Test impulse wave 2 signal generation."""
        # Create mock pattern
        mock_pattern = Mock()
        mock_pattern.pattern_type = "impulse"
        mock_pattern.current_wave = 2
        mock_pattern.confidence = 0.7
        mock_pattern.waves = [
            {"start_price": 1.10, "end_price": 1.11},  # Wave 1
            {"start_price": 1.11, "end_price": 1.105},  # Wave 2
        ]

        signal = wave_generator._generate_impulse_signal(
            mock_pattern,
            sample_wave_data,
            1.105,  # Current price at wave 2 low
            "UP",
            2,
            0.7,
        )

        assert signal is not None
        assert signal.action == "LONG"
        assert signal.confidence > 0.7  # Boosted for wave 3
        assert signal.wave_position == "Wave 2 -> 3"
        assert isinstance(signal.targets, list)
        assert len(signal.targets) > 0

    def test_generate_corrective_signal_wave_c(self, wave_generator, sample_wave_data):
        """Test corrective wave C signal generation."""
        mock_pattern = Mock()
        mock_pattern.pattern_type = "corrective"
        mock_pattern.current_wave = "C"
        mock_pattern.direction = "DOWN"
        mock_pattern.waves = [
            {"start_price": 1.11, "end_price": 1.10, "start_idx": 0},  # Wave A
            {"start_price": 1.10, "end_price": 1.105, "start_idx": 10},  # Wave B
            {"start_price": 1.105, "end_price": 1.095, "end_idx": 20},  # Wave C
        ]

        # Mock ABC completion check
        with patch.object(wave_generator, "_check_abc_completion", return_value=True):
            signal = wave_generator._generate_corrective_signal(
                mock_pattern, sample_wave_data, 1.095, "DOWN", "C", 0.6
            )

        assert signal is not None
        assert signal.action == "LONG"  # Reversal after down correction
        assert signal.wave_position == "Wave C completion"
        assert signal.confidence > 0.6

    def test_generate_diagonal_signal(self, wave_generator, sample_wave_data):
        """Test diagonal pattern signal generation."""
        mock_pattern = Mock()
        mock_pattern.pattern_type = "diagonal"
        mock_pattern.subtype = "ending"
        mock_pattern.direction = "UP"
        mock_pattern.waves = [
            {"start_price": 1.10, "end_price": 1.105},
            {"start_price": 1.105, "end_price": 1.103},
            {"start_price": 1.103, "end_price": 1.108},
            {"start_price": 1.108, "end_price": 1.106},
            {"start_price": 1.106, "end_price": 1.11},
        ]

        signal = wave_generator._generate_diagonal_signal(
            mock_pattern, sample_wave_data, 1.11, "UP", 0.65
        )

        assert signal is not None
        assert signal.action == "SHORT"  # Reversal after ending diagonal
        assert signal.wave_position == "Ending Diagonal completion"
        assert signal.pattern_type == "Diagonal"

    def test_signal_dataclass(self):
        """Test ElliottWaveSignal dataclass."""
        signal = ElliottWaveSignal(
            action="LONG",
            confidence=0.75,
            entry=1.1050,
            stop_loss=1.1000,
            targets=[1.1100, 1.1150, 1.1200],
            wave_position="Wave 2 -> 3",
            pattern_type="Impulse",
            reasoning="Test signal",
        )

        assert signal.action == "LONG"
        assert signal.confidence == 0.75
        assert signal.entry == 1.1050
        assert signal.stop_loss == 1.1000
        assert len(signal.targets) == 3
        assert signal.wave_position == "Wave 2 -> 3"
        assert signal.pattern_type == "Impulse"
        assert signal.reasoning == "Test signal"
