"""Unit tests for the integrated strategy framework."""

from datetime import datetime
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest

from fxml4.strategy.integrated_strategy import (
    IntegratedStrategy,
    Signal,
    SignalCombiner,
    SignalGenerator,
    SignalSource,
    SignalStrength,
    SignalType,
    simple_strategy,
)


class TestEnums:
    """Test the enum classes."""

    def test_signal_type_enum(self):
        """Test SignalType enum."""
        assert SignalType.ENTRY_LONG.value == "entry_long"
        assert SignalType.ENTRY_SHORT.value == "entry_short"
        assert SignalType.EXIT_LONG.value == "exit_long"
        assert SignalType.EXIT_SHORT.value == "exit_short"
        assert SignalType.UNKNOWN.value == "unknown"

    def test_signal_strength_enum(self):
        """Test SignalStrength enum."""
        assert SignalStrength.STRONG.value == "strong"
        assert SignalStrength.MODERATE.value == "moderate"
        assert SignalStrength.WEAK.value == "weak"
        assert SignalStrength.NEUTRAL.value == "neutral"

    def test_signal_source_enum(self):
        """Test SignalSource enum."""
        assert SignalSource.ML.value == "ml"
        assert SignalSource.WAVE.value == "wave"
        assert SignalSource.TECHNICAL.value == "technical"
        assert SignalSource.SENTIMENT.value == "sentiment"
        assert SignalSource.ENSEMBLE.value == "ensemble"


class TestSignal:
    """Test the Signal class."""

    def test_signal_creation(self):
        """Test Signal creation with valid parameters."""
        signal = Signal(
            signal_type=SignalType.ENTRY_LONG,
            strength=0.8,
            source=SignalSource.ML,
            timestamp=pd.Timestamp("2024-01-01 10:00:00"),
            symbol="EURUSD",
            timeframe="1h",
            metadata={"model": "random_forest"},
        )

        assert signal.signal_type == SignalType.ENTRY_LONG
        assert signal.strength == 0.8
        assert signal.source == SignalSource.ML
        assert signal.symbol == "EURUSD"
        assert signal.timeframe == "1h"
        assert signal.metadata["model"] == "random_forest"

    def test_signal_strength_validation(self):
        """Test signal strength validation and clamping."""
        # Test strength above 1.0
        signal = Signal(
            signal_type=SignalType.ENTRY_LONG,
            strength=1.5,
            source=SignalSource.ML,
            timestamp=pd.Timestamp("2024-01-01"),
            symbol="EURUSD",
            timeframe="1h",
        )
        assert signal.strength == 1.0

        # Test strength below 0.0
        signal = Signal(
            signal_type=SignalType.ENTRY_LONG,
            strength=-0.5,
            source=SignalSource.ML,
            timestamp=pd.Timestamp("2024-01-01"),
            symbol="EURUSD",
            timeframe="1h",
        )
        assert signal.strength == 0.0

    def test_strength_category_property(self):
        """Test strength category property."""
        # Strong signal
        signal = Signal(
            SignalType.ENTRY_LONG,
            0.8,
            SignalSource.ML,
            pd.Timestamp("2024-01-01"),
            "EURUSD",
            "1h",
        )
        assert signal.strength_category == SignalStrength.STRONG

        # Moderate signal
        signal.strength = 0.6
        assert signal.strength_category == SignalStrength.MODERATE

        # Weak signal
        signal.strength = 0.4
        assert signal.strength_category == SignalStrength.WEAK

        # Neutral signal
        signal.strength = 0.2
        assert signal.strength_category == SignalStrength.NEUTRAL

    def test_to_dict(self):
        """Test signal to_dict conversion."""
        signal = Signal(
            SignalType.ENTRY_LONG,
            0.75,
            SignalSource.WAVE,
            pd.Timestamp("2024-01-01 10:00:00"),
            "GBPUSD",
            "4h",
            metadata={"pattern": "wave_5"},
        )

        signal_dict = signal.to_dict()

        assert signal_dict["signal_type"] == "entry_long"
        assert signal_dict["strength"] == 0.75
        assert signal_dict["source"] == "wave"
        assert signal_dict["symbol"] == "GBPUSD"
        assert signal_dict["timeframe"] == "4h"
        assert signal_dict["strength_category"] == "strong"
        assert signal_dict["metadata"]["pattern"] == "wave_5"

    def test_string_representation(self):
        """Test signal string representation."""
        signal = Signal(
            SignalType.ENTRY_SHORT,
            0.9,
            SignalSource.TECHNICAL,
            pd.Timestamp("2024-01-01 15:30:00"),
            "USDCHF",
            "1d",
        )

        str_repr = str(signal)
        assert "technical" in str_repr
        assert "entry_short" in str_repr
        assert "strong" in str_repr
        assert "USDCHF" in str_repr
        assert "1d" in str_repr


class TestSignalCombiner:
    """Test the SignalCombiner class."""

    def test_init_default_config(self):
        """Test SignalCombiner initialization with default config."""
        combiner = SignalCombiner()
        assert combiner.method in ["weighted", "voting", "priority"]
        assert isinstance(combiner.weights, dict)
        assert combiner.min_confidence >= 0

    def test_init_custom_config(self):
        """Test SignalCombiner initialization with custom config."""
        config = {
            "method": "voting",
            "weights": {"ml": 0.7, "wave": 0.3},
            "min_confidence": 0.8,
        }
        combiner = SignalCombiner(config)
        assert combiner.method == "voting"
        assert combiner.weights["ml"] == 0.7
        assert combiner.min_confidence == 0.8

    def test_combine_signals_empty_list(self):
        """Test combining empty signal list."""
        combiner = SignalCombiner()
        result = combiner.combine_signals([])
        assert result is None

    def test_combine_signals_weighted(self, sample_signals):
        """Test weighted signal combination."""
        combiner = SignalCombiner(
            {
                "method": "weighted",
                "weights": {"ml": 0.6, "wave": 0.4},
                "min_confidence": 0.5,
            }
        )

        # Use only entry signals
        entry_signals = [
            s for s in sample_signals if s.signal_type == SignalType.ENTRY_LONG
        ]
        result = combiner.combine_signals(entry_signals)

        assert result is not None
        assert result.source == SignalSource.ENSEMBLE
        assert result.signal_type == SignalType.ENTRY_LONG
        assert 0 <= result.strength <= 1

    def test_combine_signals_voting(self, sample_signals):
        """Test voting signal combination."""
        combiner = SignalCombiner(
            {
                "method": "voting",
                "weights": {"ml": 0.5, "wave": 0.5},
                "min_confidence": 0.5,
            }
        )

        entry_signals = [
            s for s in sample_signals if s.signal_type == SignalType.ENTRY_LONG
        ]
        result = combiner.combine_signals(entry_signals)

        assert result is not None
        assert result.source == SignalSource.ENSEMBLE
        assert "yes_votes" in result.metadata
        assert "total_votes" in result.metadata

    def test_combine_signals_priority(self, sample_signals):
        """Test priority signal combination."""
        combiner = SignalCombiner(
            {
                "method": "priority",
                "weights": {"ml": 0.8, "wave": 0.2},  # ML has higher priority
                "min_confidence": 0.5,
            }
        )

        entry_signals = [
            s for s in sample_signals if s.signal_type == SignalType.ENTRY_LONG
        ]
        result = combiner.combine_signals(entry_signals)

        assert result is not None
        assert result.source == SignalSource.ENSEMBLE
        assert "selected_source" in result.metadata
        assert "priority_order" in result.metadata

    def test_combine_signals_below_confidence(self, sample_signals):
        """Test signal combination below confidence threshold."""
        combiner = SignalCombiner(
            {"method": "weighted", "min_confidence": 0.95}  # Very high threshold
        )

        result = combiner.combine_signals(sample_signals)
        assert result is None  # Should be filtered out


class TestSignalGenerator:
    """Test the SignalGenerator abstract base class."""

    def test_signal_generator_interface(self):
        """Test that SignalGenerator defines the correct interface."""

        # Create a concrete implementation
        class TestGenerator(SignalGenerator):
            def generate_signals(self, data, **kwargs):
                return []

        generator = TestGenerator()
        assert hasattr(generator, "generate_signals")
        assert generator.name == "TestGenerator"

        # Test that abstract class cannot be instantiated
        with pytest.raises(TypeError):
            SignalGenerator()


class TestIntegratedStrategy:
    """Test the IntegratedStrategy class."""

    def test_init_default_config(self):
        """Test IntegratedStrategy initialization."""
        strategy = IntegratedStrategy()
        assert strategy.name == "IntegratedStrategy"
        assert len(strategy.signal_generators) == 0
        assert isinstance(strategy.signal_combiner, SignalCombiner)

    def test_init_custom_config(self):
        """Test IntegratedStrategy initialization with custom config."""
        config = {
            "name": "CustomStrategy",
            "signal_combiner": {"method": "voting", "min_confidence": 0.7},
        }
        strategy = IntegratedStrategy(config)
        assert strategy.name == "CustomStrategy"
        assert strategy.signal_combiner.method == "voting"
        assert strategy.signal_combiner.min_confidence == 0.7

    def test_add_signal_generator(self):
        """Test adding signal generators."""
        strategy = IntegratedStrategy()

        # Create mock generators
        generator1 = Mock(spec=SignalGenerator)
        generator1.name = "Generator1"
        generator2 = Mock(spec=SignalGenerator)
        generator2.name = "Generator2"

        strategy.add_signal_generator(generator1)
        strategy.add_signal_generator(generator2)

        assert len(strategy.signal_generators) == 2
        assert generator1 in strategy.signal_generators
        assert generator2 in strategy.signal_generators

    def test_generate_signals_no_generators(self, sample_ohlc_data):
        """Test signal generation with no generators."""
        strategy = IntegratedStrategy()
        result = strategy.generate_signals(sample_ohlc_data)
        assert result is None

    def test_generate_signals_with_generators(self, sample_ohlc_data, sample_signals):
        """Test signal generation with mock generators."""
        strategy = IntegratedStrategy()

        # Create mock generators that return signals
        generator1 = Mock(spec=SignalGenerator)
        generator1.name = "Generator1"
        generator1.generate_signals.return_value = sample_signals[:1]

        generator2 = Mock(spec=SignalGenerator)
        generator2.name = "Generator2"
        generator2.generate_signals.return_value = sample_signals[1:2]

        strategy.add_signal_generator(generator1)
        strategy.add_signal_generator(generator2)

        result = strategy.generate_signals(sample_ohlc_data)

        # Verify generators were called
        generator1.generate_signals.assert_called_once()
        generator2.generate_signals.assert_called_once()

        # Result should be combined signal or None depending on combiner settings
        assert result is None or isinstance(result, Signal)

    def test_generate_signals_with_failing_generator(self, sample_ohlc_data):
        """Test signal generation when one generator fails."""
        strategy = IntegratedStrategy()

        # Create generators - one fails, one succeeds
        failing_generator = Mock(spec=SignalGenerator)
        failing_generator.name = "FailingGenerator"
        failing_generator.generate_signals.side_effect = Exception("Generator failed")

        working_generator = Mock(spec=SignalGenerator)
        working_generator.name = "WorkingGenerator"
        working_generator.generate_signals.return_value = []

        strategy.add_signal_generator(failing_generator)
        strategy.add_signal_generator(working_generator)

        # Should not raise exception, should continue with working generator
        result = strategy.generate_signals(sample_ohlc_data)

        # Both generators should have been called
        failing_generator.generate_signals.assert_called_once()
        working_generator.generate_signals.assert_called_once()


class TestSimpleStrategy:
    """Test the simple_strategy function."""

    def test_simple_strategy_insufficient_data(self, sample_ohlc_data):
        """Test simple strategy with insufficient data."""
        # Test with index less than 20
        result = simple_strategy(sample_ohlc_data, 10, {})
        assert result == {}

    def test_simple_strategy_missing_indicators(self, sample_ohlc_data):
        """Test simple strategy with missing technical indicators."""
        # Data without SMA columns
        result = simple_strategy(sample_ohlc_data, 25, {})
        assert result == {}

    def test_simple_strategy_with_indicators(self, sample_ohlc_data):
        """Test simple strategy with proper technical indicators."""
        # Add simple moving averages to data
        data = sample_ohlc_data.copy()
        data["sma_10"] = data["close"].rolling(10).mean()
        data["sma_20"] = data["close"].rolling(20).mean()

        # Test at index where we have enough data
        result = simple_strategy(data, 25, {"risk_pct": 0.02})

        # Should return empty dict or trading signals
        assert isinstance(result, dict)

        # If signals are generated, they should have expected keys
        if "entry" in result:
            assert "direction" in result
            assert "risk_pct" in result
            assert result["risk_pct"] == 0.02

        if "exit" in result:
            assert result["exit"] is True
