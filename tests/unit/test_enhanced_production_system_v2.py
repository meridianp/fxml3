#!/usr/bin/env python
"""Unit tests for Enhanced Production System V2."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pandas as pd
import pytest

from scripts.enhanced_production_system_v2 import (
    AlphaVantageEnhancement,
    EnhancedProductionConfigV2,
    EnhancedProductionSystemV2,
)


class TestAlphaVantageEnhancement:
    """Test cases for AlphaVantageEnhancement class."""

    def test_init_without_api_key(self):
        """Test initialization without API key."""
        with patch.dict("os.environ", {}, clear=True):
            av_enhancement = AlphaVantageEnhancement()
            assert av_enhancement.enabled is False
            assert av_enhancement.api_key is None

    def test_init_with_api_key(self):
        """Test initialization with API key."""
        with patch.dict("os.environ", {"ALPHA_VANTAGE_API_KEY": "test_key"}):
            av_enhancement = AlphaVantageEnhancement()
            assert av_enhancement.enabled is True
            assert av_enhancement.api_key == "test_key"

    def test_get_economic_context_disabled(self):
        """Test economic context when disabled."""
        av_enhancement = AlphaVantageEnhancement()
        av_enhancement.enabled = False

        context = av_enhancement.get_economic_context(pd.Timestamp.now())
        assert context == {}

    def test_get_economic_context_enabled(self):
        """Test economic context when enabled."""
        av_enhancement = AlphaVantageEnhancement(api_key="test_key")
        timestamp = pd.Timestamp("2024-01-15")

        context = av_enhancement.get_economic_context(timestamp)

        assert "fed_rate" in context
        assert "unemployment" in context
        assert "cpi" in context
        assert "gdp_growth" in context
        assert "vix" in context
        assert "dxy" in context
        assert "economic_sentiment" in context

        # Check mock values
        assert context["fed_rate"] == 5.25
        assert context["unemployment"] == 3.7
        assert context["cpi"] == 3.2

    def test_get_economic_context_caching(self):
        """Test economic context caching."""
        av_enhancement = AlphaVantageEnhancement(api_key="test_key")
        timestamp = pd.Timestamp("2024-01-15")

        # First call
        context1 = av_enhancement.get_economic_context(timestamp)

        # Second call (should use cache)
        context2 = av_enhancement.get_economic_context(timestamp)

        assert context1 == context2
        assert "2024-01-15" in av_enhancement.economic_cache

    def test_get_news_sentiment_disabled(self):
        """Test news sentiment when disabled."""
        av_enhancement = AlphaVantageEnhancement()
        av_enhancement.enabled = False

        sentiment = av_enhancement.get_news_sentiment("EURUSD", pd.Timestamp.now())
        assert sentiment["sentiment"] == 0.0
        assert sentiment["relevance"] == 0.0

    def test_get_news_sentiment_enabled(self):
        """Test news sentiment when enabled."""
        av_enhancement = AlphaVantageEnhancement(api_key="test_key")

        sentiment = av_enhancement.get_news_sentiment("EURUSD", pd.Timestamp.now())

        assert "overall_sentiment" in sentiment
        assert "relevance_score" in sentiment
        assert sentiment["overall_sentiment"] == 0.0  # Mock value
        assert sentiment["relevance_score"] == 0.5  # Mock value

    def test_calculate_economic_sentiment(self):
        """Test economic sentiment calculation."""
        av_enhancement = AlphaVantageEnhancement(api_key="test_key")

        # Test bearish sentiment (high rates, high unemployment)
        context = {"fed_rate": 5.5, "unemployment": 5.5, "gdp_growth": 0.5, "vix": 30}
        sentiment = av_enhancement._calculate_economic_sentiment(context)
        assert sentiment < 0  # Should be bearish

        # Test bullish sentiment (low rates, low unemployment)
        context = {"fed_rate": 1.5, "unemployment": 3.5, "gdp_growth": 3.0, "vix": 12}
        sentiment = av_enhancement._calculate_economic_sentiment(context)
        assert sentiment > 0  # Should be bullish


class TestEnhancedProductionConfigV2:
    """Test cases for EnhancedProductionConfigV2."""

    def test_default_config(self):
        """Test default configuration values."""
        config = EnhancedProductionConfigV2()

        # Test adjusted values
        assert config.min_confluences == 1  # Lowered from 2
        assert config.min_signal_confidence == 0.6  # Reduced from 0.7
        assert config.single_source_position_reduction == 0.5
        assert config.max_bars_in_trade == 120
        assert config.use_adaptive_thresholds is True
        assert config.use_news_filter is True
        assert config.use_economic_data is True

        # Test other values
        assert config.initial_capital == 10000
        assert config.max_risk_per_trade == 0.015
        assert config.max_trades_per_week == 5  # Increased from 3


class TestEnhancedProductionSystemV2:
    """Test cases for EnhancedProductionSystemV2."""

    @pytest.fixture
    def sample_data(self):
        """Create sample market data."""
        dates = pd.date_range(start="2024-01-01", periods=200, freq="4h")
        data = pd.DataFrame(
            {
                "open": 1.1000 + np.random.randn(200) * 0.001,
                "high": 1.1050 + np.random.randn(200) * 0.001,
                "low": 1.0950 + np.random.randn(200) * 0.001,
                "close": 1.1000 + np.random.randn(200) * 0.001,
                "volume": np.random.randint(1000, 5000, 200),
                "atr_14": np.full(200, 0.0010),
            },
            index=dates,
        )

        # Ensure high > low
        data["high"] = data[["open", "close"]].max(axis=1) + 0.0005
        data["low"] = data[["open", "close"]].min(axis=1) - 0.0005

        return data

    @pytest.fixture
    def mock_ml_model(self):
        """Create mock ML model."""
        model = Mock()
        model.predict = Mock(return_value=np.array([0.7]))  # Bullish prediction
        return model

    def test_system_initialization(self):
        """Test system initialization."""
        config = EnhancedProductionConfigV2()
        system = EnhancedProductionSystemV2(config)

        assert system.capital == config.initial_capital
        assert len(system.positions) == 0
        assert len(system.trades) == 0
        assert system.ml_model is None
        assert system.av_enhancement is not None

        # Check performance stats initialization
        assert system.performance_stats["total_signals"] == 0
        assert system.performance_stats["ml_signals"] == 0
        assert system.performance_stats["single_source_trades"] == 0
        assert system.performance_stats["time_exits"] == 0

    def test_system_with_ml_model(self, mock_ml_model):
        """Test system initialization with ML model."""
        config = EnhancedProductionConfigV2()
        system = EnhancedProductionSystemV2(config, ml_model=mock_ml_model)

        assert system.ml_model == mock_ml_model
        assert system.ml_generator.model == mock_ml_model

    def test_update_adaptive_thresholds_high_volatility(self, sample_data):
        """Test adaptive threshold updates in high volatility."""
        config = EnhancedProductionConfigV2()
        system = EnhancedProductionSystemV2(config)

        # Create high volatility data
        high_vol_data = sample_data.copy()
        high_vol_data["close"] = (
            high_vol_data["close"] + np.random.randn(len(high_vol_data)) * 0.005
        )

        system._update_adaptive_thresholds(high_vol_data)

        # Check volatility percentile is high
        assert system.market_conditions["volatility_percentile"] > 75

        # Check thresholds were adjusted upward
        assert system.ml_generator.min_confidence > config.min_signal_confidence
        assert system.performance_stats["adaptive_adjustments"] == 1

    def test_update_adaptive_thresholds_low_volatility(self, sample_data):
        """Test adaptive threshold updates in low volatility."""
        config = EnhancedProductionConfigV2()
        system = EnhancedProductionSystemV2(config)

        # Create low volatility data
        low_vol_data = sample_data.copy()
        low_vol_data["close"] = (
            low_vol_data["close"] + np.random.randn(len(low_vol_data)) * 0.0001
        )

        system._update_adaptive_thresholds(low_vol_data)

        # Check volatility percentile is low
        assert system.market_conditions["volatility_percentile"] < 25

        # Check thresholds were adjusted downward
        assert system.ml_generator.min_confidence < config.min_signal_confidence
        assert system.performance_stats["adaptive_adjustments"] == 1

    def test_generate_combined_signal_no_signals(self, sample_data):
        """Test signal generation with no signals."""
        config = EnhancedProductionConfigV2()
        system = EnhancedProductionSystemV2(config)

        # Mock generators to return no signals
        system.ml_generator.generate_signal = Mock(return_value=None)
        system.ew_generator.generate_signals = Mock(return_value=None)
        system.ta_analyzer.analyze_market = Mock(return_value=None)

        signal = system.generate_combined_signal(
            sample_data, "EURUSD", pd.Timestamp.now()
        )

        assert signal is None
        assert system.performance_stats["total_signals"] == 1

    def test_generate_combined_signal_single_source(self, sample_data, mock_ml_model):
        """Test signal generation with single source."""
        config = EnhancedProductionConfigV2()
        system = EnhancedProductionSystemV2(config, ml_model=mock_ml_model)

        # Create ML signal only
        from scripts.enhanced_ml_signal_generator import MLSignal

        ml_signal = MLSignal(
            action="LONG",
            confidence=0.7,
            predicted_return=0.002,
            features_used=["sma_20", "rsi_14"],
            market_regime="trending",
        )

        # Mock generators
        system.ml_generator.generate_signal = Mock(return_value=ml_signal)
        system.ew_generator.generate_signals = Mock(return_value=None)
        system.ta_analyzer.analyze_market = Mock(return_value=None)

        signal = system.generate_combined_signal(
            sample_data, "EURUSD", pd.Timestamp.now()
        )

        assert signal is not None
        assert signal["action"] == "LONG"
        assert signal["signal_count"] == 1
        assert signal["position_size_multiplier"] == 0.5  # Single source reduction
        assert system.performance_stats["single_source_trades"] == 1
        assert system.performance_stats["ml_signals"] == 1

    def test_generate_combined_signal_multi_confluence(
        self, sample_data, mock_ml_model
    ):
        """Test signal generation with multiple confluences."""
        config = EnhancedProductionConfigV2()
        system = EnhancedProductionSystemV2(config, ml_model=mock_ml_model)

        # Create signals from multiple sources
        from scripts.enhanced_elliott_wave_signals import ElliottWaveSignal
        from scripts.enhanced_ml_signal_generator import MLSignal
        from scripts.general_technical_analysis_llm import TechnicalAnalysisSignal

        ml_signal = MLSignal(
            action="LONG",
            confidence=0.7,
            predicted_return=0.002,
            features_used=["sma_20", "rsi_14"],
            market_regime="trending",
        )

        ew_signal = ElliottWaveSignal(
            action="LONG",
            confidence=0.65,
            wave_position="Wave 2 -> 3",
            entry=1.1000,
            stop_loss=1.0950,
            targets=[1.1050, 1.1100, 1.1150],
            reasoning="Entering Wave 3",
        )

        ta_signal = TechnicalAnalysisSignal(
            bias="LONG",
            confidence=0.8,
            entry_zones=[1.0995, 1.1005],
            stop_loss=1.0950,
            targets=[1.1050, 1.1100],
            key_levels={"support": [1.0950], "resistance": [1.1050]},
            technical_confluences=["MA crossover", "RSI divergence"],
            market_structure="trending_up",
            risk_reward=2.5,
            time_horizon="swing",
        )

        # Mock generators
        system.ml_generator.generate_signal = Mock(return_value=ml_signal)
        system.ew_generator.generate_signals = Mock(return_value=ew_signal)
        system.ta_analyzer.analyze_market = Mock(return_value=ta_signal)

        signal = system.generate_combined_signal(
            sample_data, "EURUSD", pd.Timestamp.now()
        )

        assert signal is not None
        assert signal["action"] == "LONG"
        assert signal["signal_count"] == 3
        assert (
            signal["position_size_multiplier"] == 1.0
        )  # Full size for multi-confluence
        assert system.performance_stats["multi_confluence"] == 1
        assert len(signal["confluences"]) == 3

    def test_apply_final_filters_v2_risk_reward(self, sample_data):
        """Test final filters - risk/reward filter."""
        config = EnhancedProductionConfigV2()
        system = EnhancedProductionSystemV2(config)

        # Test signal with poor risk/reward
        signal = {
            "risk_reward": 1.2,  # Below 1.5 threshold
            "confidence": 0.7,
            "action": "LONG",
        }

        result = system._apply_final_filters_v2(
            signal, sample_data, pd.Timestamp.now(), {}
        )

        assert result is False

    def test_apply_final_filters_v2_news_sentiment(self, sample_data):
        """Test final filters - news sentiment filter."""
        config = EnhancedProductionConfigV2()
        config.use_news_filter = True
        system = EnhancedProductionSystemV2(config)

        # Test signal against strong negative sentiment
        signal = {"risk_reward": 2.0, "confidence": 0.7, "action": "LONG"}

        news_sentiment = {"overall_sentiment": -0.6}  # Strong bearish sentiment

        result = system._apply_final_filters_v2(
            signal, sample_data, pd.Timestamp.now(), news_sentiment
        )

        assert result is False  # Should block LONG against bearish news

    def test_execute_trade(self, sample_data):
        """Test trade execution."""
        config = EnhancedProductionConfigV2()
        system = EnhancedProductionSystemV2(config)

        signal = {
            "action": "LONG",
            "confidence": 0.7,
            "entry": 1.1000,
            "stop_loss": 1.0950,
            "targets": [1.1050, 1.1100],
            "source": "ML",
            "confluences": ["ML"],
            "position_size_multiplier": 1.0,
        }

        current_bar = sample_data.iloc[-1]
        system.execute_trade(signal, current_bar, pd.Timestamp.now(), "EURUSD")

        assert len(system.positions) == 1
        position_id = list(system.positions.keys())[0]
        position = system.positions[position_id]

        assert position["direction"] == "LONG"
        assert position["stop_loss"] == 1.0950
        assert position["bars_held"] == 0
        assert system.performance_stats["trades_executed"] == 1

    def test_update_positions_time_exit(self, sample_data):
        """Test position update with time-based exit."""
        config = EnhancedProductionConfigV2()
        config.time_based_exit_enabled = True
        config.max_bars_in_trade = 120
        system = EnhancedProductionSystemV2(config)

        # Create a position that has been held for max bars
        position_id = "EURUSD_2024-01-01"
        system.positions[position_id] = {
            "symbol": "EURUSD",
            "direction": "LONG",
            "entry_time": pd.Timestamp("2024-01-01"),
            "entry_price": 1.1000,
            "position_size": 10000,
            "stop_loss": 1.0950,
            "initial_stop": 1.0950,
            "targets": [1.1050],
            "targets_hit": [],
            "signal_confidence": 0.7,
            "signal_source": "ML",
            "confluences": ["ML"],
            "trailing_stop_active": False,
            "partial_exits": [],
            "bars_held": 119,  # One bar away from max
        }

        current_bar = pd.Series(
            {"open": 1.1020, "high": 1.1030, "low": 1.1010, "close": 1.1025}
        )

        system.update_positions("EURUSD", current_bar, pd.Timestamp.now())

        # Position should be closed due to time exit
        assert len(system.positions) == 0
        assert len(system.trades) == 1
        assert system.trades[0]["exit_reason"] == "Time Exit"
        assert system.performance_stats["time_exits"] == 1

    def test_check_recent_losses(self):
        """Test recent losses check."""
        config = EnhancedProductionConfigV2()
        system = EnhancedProductionSystemV2(config)

        # Add losing trades
        system.trades = [{"pnl": -100}, {"pnl": -50}, {"pnl": 75}]

        assert system._check_recent_losses() is True  # 2 losses in last 3

        # Add winning trade
        system.trades.append({"pnl": 100})
        assert system._check_recent_losses() is False  # Only 1 loss in last 3

    def test_calculate_atr(self, sample_data):
        """Test ATR calculation."""
        config = EnhancedProductionConfigV2()
        system = EnhancedProductionSystemV2(config)

        # Test with atr_14 column
        atr = system._calculate_atr(sample_data)
        assert atr == 0.0010

        # Test without atr_14 column
        data_no_atr = sample_data.drop("atr_14", axis=1)
        atr = system._calculate_atr(data_no_atr)
        assert atr > 0
        assert isinstance(atr, float)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
