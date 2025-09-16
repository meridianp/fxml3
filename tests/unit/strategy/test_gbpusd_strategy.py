"""
Comprehensive unit tests for GBP/USD trading strategy.

Following TDD methodology to increase test coverage from 60% to 85%.
Tests cover signal generation, risk management, market regime detection,
and integrated trading logic.
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import pandas as pd
import pytest

from fxml4.core.types import MarketRegime, SignalStrength, Symbol, Timeframe
from fxml4.strategy.gbpusd_strategy import (
    GBPUSDStrategy,
    MarketConditions,
    RiskParameters,
    SignalMetadata,
    StrategyMetrics,
    TradingSignal,
)


@pytest.fixture
def mock_data_pipeline():
    """Mock unified data pipeline."""
    mock = AsyncMock()
    mock.get_latest_features.return_value = {
        "sma_10": 1.2650,
        "sma_20": 1.2645,
        "rsi_14": 65.5,
        "macd": 0.0012,
        "bollinger_upper": 1.2680,
        "bollinger_lower": 1.2620,
        "volume_sma": 12500,
        "volatility_1h": 0.0015,
    }
    return mock


@pytest.fixture
def mock_ml_ensemble():
    """Mock ML ensemble predictor."""
    mock = AsyncMock()
    mock.predict.return_value = {
        "signal": 1,  # Bullish
        "confidence": 0.75,
        "probabilities": [0.25, 0.75],
        "feature_importance": {"sma_10": 0.3, "rsi_14": 0.25},
    }
    return mock


@pytest.fixture
def mock_wave_analyzer():
    """Mock Elliott Wave analyzer."""
    mock = AsyncMock()
    mock.analyze_current_wave.return_value = {
        "wave_pattern": "impulse_wave_5",
        "confidence": 0.8,
        "direction": 1,
        "completion_probability": 0.65,
    }
    return mock


@pytest.fixture
def mock_regime_classifier():
    """Mock market regime classifier."""
    mock = Mock()
    mock.classify_regime.return_value = MarketRegime.TRENDING
    mock.get_regime_confidence.return_value = 0.85
    return mock


@pytest.fixture
def mock_drawdown_controller():
    """Mock drawdown controller."""
    mock = Mock()
    mock.calculate_position_size.return_value = 0.02
    mock.check_risk_limits.return_value = True
    mock.current_drawdown = 0.03
    return mock


@pytest.fixture
def sample_market_data():
    """Generate sample OHLC market data."""
    dates = pd.date_range(start="2024-01-01", periods=100, freq="1H")
    np.random.seed(42)

    # Generate realistic GBP/USD price data
    base_price = 1.2650
    returns = np.random.normal(0, 0.001, 100)
    prices = base_price + np.cumsum(returns)

    data = []
    for i, (date, close) in enumerate(zip(dates, prices)):
        open_price = prices[i - 1] if i > 0 else close
        high = max(open_price, close) + np.random.uniform(0, 0.002)
        low = min(open_price, close) - np.random.uniform(0, 0.002)
        volume = np.random.randint(8000, 15000)

        data.append(
            {
                "timestamp": date,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )

    return pd.DataFrame(data)


@pytest.fixture
def strategy_config():
    """Default strategy configuration."""
    return {
        "symbol": "GBPUSD",
        "primary_timeframe": "1H",
        "execution_timeframe": "5M",
        "risk_per_trade": 0.02,
        "max_portfolio_risk": 0.06,
        "min_signal_confidence": 0.6,
        "stop_loss_pips": 50,
        "take_profit_pips": 100,
        "trailing_stop": True,
        "max_drawdown": 0.15,
    }


@pytest.fixture
async def gbpusd_strategy(
    strategy_config,
    mock_data_pipeline,
    mock_ml_ensemble,
    mock_wave_analyzer,
    mock_regime_classifier,
    mock_drawdown_controller,
):
    """Create GBP/USD strategy instance with mocked dependencies."""
    strategy = GBPUSDStrategy(strategy_config)

    # Inject mocked dependencies
    strategy.data_pipeline = mock_data_pipeline
    strategy.ml_ensemble = mock_ml_ensemble
    strategy.wave_analyzer = mock_wave_analyzer
    strategy.regime_classifier = mock_regime_classifier
    strategy.drawdown_controller = mock_drawdown_controller

    await strategy.initialize()
    return strategy


class TestGBPUSDStrategyInitialization:
    """Test strategy initialization and configuration."""

    def test_strategy_creation_with_valid_config(self, strategy_config):
        """Test strategy can be created with valid configuration."""
        strategy = GBPUSDStrategy(strategy_config)

        assert strategy.symbol == "GBPUSD"
        assert strategy.primary_timeframe == "1H"
        assert strategy.risk_per_trade == 0.02
        assert strategy.max_portfolio_risk == 0.06

    def test_strategy_creation_with_invalid_symbol(self, strategy_config):
        """Test strategy rejects invalid symbol."""
        strategy_config["symbol"] = "INVALID"

        with pytest.raises(ValueError, match="Invalid symbol"):
            GBPUSDStrategy(strategy_config)

    def test_strategy_creation_with_invalid_risk_params(self, strategy_config):
        """Test strategy validates risk parameters."""
        strategy_config["risk_per_trade"] = 0.5  # 50% risk per trade - too high

        with pytest.raises(ValueError, match="Risk per trade too high"):
            GBPUSDStrategy(strategy_config)

    @pytest.mark.asyncio
    async def test_strategy_initialization_success(self, gbpusd_strategy):
        """Test successful strategy initialization."""
        assert gbpusd_strategy.is_initialized
        assert gbpusd_strategy.ml_ensemble is not None
        assert gbpusd_strategy.wave_analyzer is not None


class TestSignalGeneration:
    """Test trading signal generation logic."""

    @pytest.mark.asyncio
    async def test_generate_bullish_signal(
        self, gbpusd_strategy, sample_market_data, mock_ml_ensemble, mock_wave_analyzer
    ):
        """Test generation of bullish trading signal."""
        # Setup ML prediction for bullish signal
        mock_ml_ensemble.predict.return_value = {
            "signal": 1,
            "confidence": 0.85,
            "probabilities": [0.15, 0.85],
        }

        # Setup Elliott Wave for bullish pattern
        mock_wave_analyzer.analyze_current_wave.return_value = {
            "wave_pattern": "impulse_wave_3",
            "confidence": 0.9,
            "direction": 1,
        }

        signal = await gbpusd_strategy.generate_signal(sample_market_data)

        assert signal.signal_type == TradingSignal.ENTRY_LONG
        assert signal.confidence >= 0.6
        assert signal.symbol == "GBPUSD"
        assert signal.metadata.ml_confidence >= 0.8
        assert signal.metadata.wave_pattern == "impulse_wave_3"

    @pytest.mark.asyncio
    async def test_generate_bearish_signal(
        self, gbpusd_strategy, sample_market_data, mock_ml_ensemble, mock_wave_analyzer
    ):
        """Test generation of bearish trading signal."""
        # Setup ML prediction for bearish signal
        mock_ml_ensemble.predict.return_value = {
            "signal": -1,
            "confidence": 0.78,
            "probabilities": [0.78, 0.22],
        }

        # Setup Elliott Wave for bearish pattern
        mock_wave_analyzer.analyze_current_wave.return_value = {
            "wave_pattern": "corrective_wave_abc",
            "confidence": 0.82,
            "direction": -1,
        }

        signal = await gbpusd_strategy.generate_signal(sample_market_data)

        assert signal.signal_type == TradingSignal.ENTRY_SHORT
        assert signal.confidence >= 0.6
        assert signal.metadata.wave_pattern == "corrective_wave_abc"

    @pytest.mark.asyncio
    async def test_no_signal_low_confidence(
        self, gbpusd_strategy, sample_market_data, mock_ml_ensemble
    ):
        """Test no signal generated when confidence is too low."""
        # Setup low confidence prediction
        mock_ml_ensemble.predict.return_value = {
            "signal": 1,
            "confidence": 0.45,  # Below minimum threshold
            "probabilities": [0.55, 0.45],
        }

        signal = await gbpusd_strategy.generate_signal(sample_market_data)

        assert signal.signal_type == TradingSignal.NO_SIGNAL
        assert signal.confidence < 0.6


class TestRiskManagement:
    """Test risk management functionality."""

    @pytest.mark.asyncio
    async def test_position_sizing_calculation(self, gbpusd_strategy):
        """Test position size calculation based on risk parameters."""
        account_balance = 10000.0
        signal_confidence = 0.8
        volatility = 0.0015

        position_size = await gbpusd_strategy.calculate_position_size(
            account_balance, signal_confidence, volatility
        )

        # Position size should respect risk per trade limit
        max_position_value = account_balance * gbpusd_strategy.risk_per_trade
        assert position_size <= max_position_value / gbpusd_strategy.current_price

    @pytest.mark.asyncio
    async def test_stop_loss_calculation(self, gbpusd_strategy):
        """Test stop loss level calculation."""
        entry_price = 1.2650
        signal_type = TradingSignal.ENTRY_LONG
        volatility = 0.0015

        stop_loss = await gbpusd_strategy.calculate_stop_loss(
            entry_price, signal_type, volatility
        )

        # Stop loss should be below entry for long positions
        assert stop_loss < entry_price

        # Stop loss distance should be reasonable
        stop_distance = abs(entry_price - stop_loss)
        assert 0.003 <= stop_distance <= 0.008  # 30-80 pips

    @pytest.mark.asyncio
    async def test_risk_limit_enforcement(
        self, gbpusd_strategy, mock_drawdown_controller
    ):
        """Test risk limits are properly enforced."""
        # Setup high current risk scenario
        mock_drawdown_controller.current_drawdown = 0.12
        mock_drawdown_controller.check_risk_limits.return_value = False

        signal = Mock()
        signal.confidence = 0.85

        can_trade = await gbpusd_strategy.can_execute_trade(signal)

        assert not can_trade


class TestMarketRegimeAdaptation:
    """Test market regime detection and strategy adaptation."""

    @pytest.mark.asyncio
    async def test_trending_market_adaptation(
        self, gbpusd_strategy, mock_regime_classifier
    ):
        """Test strategy adapts to trending market conditions."""
        mock_regime_classifier.classify_regime.return_value = MarketRegime.TRENDING

        await gbpusd_strategy.adapt_to_market_regime()

        # In trending markets, strategy should be more aggressive
        assert gbpusd_strategy.current_min_confidence <= 0.65
        assert gbpusd_strategy.position_size_multiplier >= 1.0

    @pytest.mark.asyncio
    async def test_ranging_market_adaptation(
        self, gbpusd_strategy, mock_regime_classifier
    ):
        """Test strategy adapts to ranging market conditions."""
        mock_regime_classifier.classify_regime.return_value = MarketRegime.RANGING

        await gbpusd_strategy.adapt_to_market_regime()

        # In ranging markets, strategy should be more conservative
        assert gbpusd_strategy.current_min_confidence >= 0.7
        assert gbpusd_strategy.position_size_multiplier <= 0.8

    @pytest.mark.asyncio
    async def test_volatile_market_adaptation(
        self, gbpusd_strategy, mock_regime_classifier
    ):
        """Test strategy adapts to volatile market conditions."""
        mock_regime_classifier.classify_regime.return_value = MarketRegime.VOLATILE

        await gbpusd_strategy.adapt_to_market_regime()

        # In volatile markets, reduce position sizes and increase confidence requirements
        assert gbpusd_strategy.position_size_multiplier <= 0.6
        assert gbpusd_strategy.current_min_confidence >= 0.75


class TestPerformanceMetrics:
    """Test strategy performance tracking and metrics."""

    @pytest.mark.asyncio
    async def test_trade_execution_tracking(self, gbpusd_strategy):
        """Test trade execution is properly tracked."""
        initial_trades = gbpusd_strategy.metrics.total_trades

        # Simulate trade execution
        trade_result = {
            "entry_time": datetime.now(),
            "entry_price": 1.2650,
            "exit_time": datetime.now() + timedelta(hours=2),
            "exit_price": 1.2680,
            "pnl": 0.003,
            "signal_confidence": 0.85,
        }

        await gbpusd_strategy.record_trade(trade_result)

        assert gbpusd_strategy.metrics.total_trades == initial_trades + 1
        assert gbpusd_strategy.metrics.total_pnl == 0.003

    @pytest.mark.asyncio
    async def test_drawdown_calculation(self, gbpusd_strategy):
        """Test maximum drawdown calculation."""
        # Simulate series of trades with losses
        trades = [
            {"pnl": 0.002},
            {"pnl": -0.005},
            {"pnl": -0.003},
            {"pnl": 0.001},
            {"pnl": -0.004},
        ]

        for trade in trades:
            await gbpusd_strategy.record_trade(trade)

        max_drawdown = gbpusd_strategy.calculate_max_drawdown()
        assert max_drawdown > 0  # Should show some drawdown from losses

    @pytest.mark.asyncio
    async def test_sharpe_ratio_calculation(self, gbpusd_strategy):
        """Test Sharpe ratio calculation for strategy performance."""
        # Simulate profitable trading period
        for i in range(20):
            pnl = np.random.normal(0.001, 0.002)  # Positive expected return
            await gbpusd_strategy.record_trade({"pnl": pnl})

        sharpe_ratio = gbpusd_strategy.calculate_sharpe_ratio()
        assert isinstance(sharpe_ratio, float)
        assert not np.isnan(sharpe_ratio)


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_data_unavailable_handling(self, gbpusd_strategy, mock_data_pipeline):
        """Test strategy handles data unavailability gracefully."""
        mock_data_pipeline.get_latest_features.side_effect = Exception(
            "Data unavailable"
        )

        signal = await gbpusd_strategy.generate_signal(pd.DataFrame())

        assert signal.signal_type == TradingSignal.NO_SIGNAL
        assert "data_error" in signal.metadata.error_info

    @pytest.mark.asyncio
    async def test_ml_model_failure_handling(self, gbpusd_strategy, mock_ml_ensemble):
        """Test strategy handles ML model failures gracefully."""
        mock_ml_ensemble.predict.side_effect = Exception("Model prediction failed")

        # Strategy should fall back to technical/wave analysis only
        signal = await gbpusd_strategy.generate_signal(Mock())

        # Should still generate signal but with lower confidence
        assert signal is not None
        assert signal.metadata.ml_confidence == 0.0

    @pytest.mark.asyncio
    async def test_invalid_market_data_handling(self, gbpusd_strategy):
        """Test strategy handles invalid market data."""
        # Create DataFrame with missing required columns
        invalid_data = pd.DataFrame({"price": [1.265, 1.267]})

        signal = await gbpusd_strategy.generate_signal(invalid_data)

        assert signal.signal_type == TradingSignal.NO_SIGNAL
        assert "invalid_data" in signal.metadata.error_info


class TestIntegrationScenarios:
    """Test integrated scenarios combining multiple components."""

    @pytest.mark.asyncio
    async def test_full_trading_cycle(
        self, gbpusd_strategy, sample_market_data, mock_ml_ensemble, mock_wave_analyzer
    ):
        """Test complete trading cycle from signal to execution."""
        # Setup bullish scenario
        mock_ml_ensemble.predict.return_value = {
            "signal": 1,
            "confidence": 0.85,
            "probabilities": [0.15, 0.85],
        }
        mock_wave_analyzer.analyze_current_wave.return_value = {
            "wave_pattern": "impulse_wave_5",
            "confidence": 0.88,
            "direction": 1,
        }

        # Generate signal
        signal = await gbpusd_strategy.generate_signal(sample_market_data)
        assert signal.signal_type == TradingSignal.ENTRY_LONG

        # Check if trade can be executed
        can_execute = await gbpusd_strategy.can_execute_trade(signal)
        assert can_execute

        # Calculate position parameters
        position_size = await gbpusd_strategy.calculate_position_size(
            10000.0, signal.confidence, 0.0015
        )
        stop_loss = await gbpusd_strategy.calculate_stop_loss(
            1.2650, signal.signal_type, 0.0015
        )
        take_profit = await gbpusd_strategy.calculate_take_profit(
            1.2650, signal.signal_type, signal.confidence
        )

        assert position_size > 0
        assert stop_loss < 1.2650
        assert take_profit > 1.2650

    @pytest.mark.asyncio
    async def test_risk_limit_override(self, gbpusd_strategy, mock_drawdown_controller):
        """Test risk limits override trading signals."""
        # Setup scenario where drawdown is too high
        mock_drawdown_controller.current_drawdown = 0.18  # Above 15% limit
        mock_drawdown_controller.check_risk_limits.return_value = False

        # Even with strong signal, should not trade
        strong_signal = Mock()
        strong_signal.confidence = 0.95
        strong_signal.signal_type = TradingSignal.ENTRY_LONG

        can_execute = await gbpusd_strategy.can_execute_trade(strong_signal)
        assert not can_execute

    @pytest.mark.asyncio
    async def test_regime_specific_signal_filtering(
        self, gbpusd_strategy, mock_regime_classifier, sample_market_data
    ):
        """Test signals are filtered based on market regime."""
        # Setup ranging market
        mock_regime_classifier.classify_regime.return_value = MarketRegime.RANGING
        await gbpusd_strategy.adapt_to_market_regime()

        # Weak signal that would be rejected in ranging market
        gbpusd_strategy.ml_ensemble.predict.return_value = {
            "signal": 1,
            "confidence": 0.65,
            "probabilities": [0.35, 0.65],
        }

        signal = await gbpusd_strategy.generate_signal(sample_market_data)

        # Should be rejected due to increased confidence threshold in ranging market
        assert signal.signal_type == TradingSignal.NO_SIGNAL


@pytest.mark.performance
class TestPerformanceRequirements:
    """Test performance requirements are met."""

    @pytest.mark.asyncio
    async def test_signal_generation_speed(self, gbpusd_strategy, sample_market_data):
        """Test signal generation completes within 2 seconds."""
        import time

        start_time = time.time()
        signal = await gbpusd_strategy.generate_signal(sample_market_data)
        end_time = time.time()

        execution_time = end_time - start_time
        assert execution_time < 2.0, f"Signal generation took {execution_time:.2f}s"

    @pytest.mark.asyncio
    async def test_risk_calculation_speed(self, gbpusd_strategy):
        """Test risk calculations complete within 200ms."""
        import time

        start_time = time.time()
        position_size = await gbpusd_strategy.calculate_position_size(
            10000.0, 0.8, 0.0015
        )
        stop_loss = await gbpusd_strategy.calculate_stop_loss(
            1.2650, TradingSignal.ENTRY_LONG, 0.0015
        )
        end_time = time.time()

        execution_time = end_time - start_time
        assert execution_time < 0.2, f"Risk calculations took {execution_time:.3f}s"
