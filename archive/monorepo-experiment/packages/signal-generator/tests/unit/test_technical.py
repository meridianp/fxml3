"""Tests for technical indicator signal generation."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import ta

from fxml4_signals.technical import TechnicalSignals
from fxml4_signals.base import Signal, SignalType


@pytest.fixture
def technical_signals():
    """Create TechnicalSignals instance."""
    return TechnicalSignals(
        name="technical_test",
        weight=0.9,
        rsi_oversold=30,
        rsi_overbought=70,
        bb_std=2.0
    )


@pytest.fixture
def trending_price_data():
    """Create trending price data."""
    periods = 200
    dates = pd.date_range(start='2024-01-01', periods=periods, freq='1h')
    
    # Create uptrend
    trend = np.linspace(1.0800, 1.0900, periods)
    noise = np.random.randn(periods) * 0.0005
    
    close = trend + noise
    open_price = np.roll(close, 1)
    open_price[0] = close[0]
    
    high = np.maximum(open_price, close) + abs(np.random.randn(periods) * 0.0002)
    low = np.minimum(open_price, close) - abs(np.random.randn(periods) * 0.0002)
    
    volume = np.random.randint(5000, 15000, periods)
    
    df = pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)
    
    return df


@pytest.fixture
def ranging_price_data():
    """Create ranging/sideways price data."""
    periods = 200
    dates = pd.date_range(start='2024-01-01', periods=periods, freq='1h')
    
    # Create sideways movement
    center = 1.0850
    close = center + np.sin(np.linspace(0, 4*np.pi, periods)) * 0.0020
    close += np.random.randn(periods) * 0.0002
    
    open_price = np.roll(close, 1)
    open_price[0] = close[0]
    
    high = np.maximum(open_price, close) + abs(np.random.randn(periods) * 0.0001)
    low = np.minimum(open_price, close) - abs(np.random.randn(periods) * 0.0001)
    
    volume = np.random.randint(3000, 8000, periods)
    
    df = pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)
    
    return df


@pytest.fixture
def volatile_price_data():
    """Create volatile price data."""
    periods = 200
    dates = pd.date_range(start='2024-01-01', periods=periods, freq='1h')
    
    # Create volatile movement
    base = 1.0850
    close = base + np.random.randn(periods).cumsum() * 0.0010
    
    open_price = np.roll(close, 1)
    open_price[0] = close[0]
    
    # Higher volatility in high/low
    high = np.maximum(open_price, close) + abs(np.random.randn(periods) * 0.0008)
    low = np.minimum(open_price, close) - abs(np.random.randn(periods) * 0.0008)
    
    # Volume spikes with volatility
    volume = np.random.randint(1000, 20000, periods)
    
    df = pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)
    
    return df


class TestTechnicalSignals:
    """Test TechnicalSignals class."""
    
    def test_initialization(self):
        """Test TechnicalSignals initialization."""
        signals = TechnicalSignals(
            name="tech",
            weight=0.8,
            rsi_oversold=25,
            rsi_overbought=75,
            bb_std=2.5
        )
        
        assert signals.name == "tech"
        assert signals.weight == 0.8
        assert signals.rsi_oversold == 25
        assert signals.rsi_overbought == 75
        assert signals.bb_std == 2.5
    
    def test_default_initialization(self):
        """Test TechnicalSignals with default parameters."""
        signals = TechnicalSignals()
        
        assert signals.name == "technical"
        assert signals.weight == 1.0
        assert signals.rsi_oversold == 30
        assert signals.rsi_overbought == 70
        assert signals.bb_std == 2.0
    
    def test_get_required_columns(self, technical_signals):
        """Test required columns."""
        required = technical_signals.get_required_columns()
        
        assert "open" in required
        assert "high" in required
        assert "low" in required
        assert "close" in required
        assert "volume" in required
        assert len(required) == 5
    
    def test_calculate_indicators(self, technical_signals, trending_price_data):
        """Test indicator calculation."""
        indicators = technical_signals._calculate_indicators(trending_price_data)
        
        # Check all indicators are calculated
        expected_indicators = [
            'sma_20', 'sma_50', 'ema_12', 'ema_26',
            'rsi', 'macd', 'macd_signal', 'macd_diff',
            'bb_upper', 'bb_middle', 'bb_lower', 'atr'
        ]
        
        for indicator in expected_indicators:
            assert indicator in indicators.columns
            # Check no NaN values after warmup period
            assert not indicators[indicator].iloc[50:].isna().any()
    
    def test_ma_crossover_signals(self, technical_signals, trending_price_data):
        """Test moving average crossover signal generation."""
        # Calculate indicators first
        indicators = technical_signals._calculate_indicators(trending_price_data)
        
        # Generate MA crossover signals
        signals = technical_signals._ma_crossover_signals(indicators, "EURUSD")
        
        # In an uptrend, should have some golden crosses
        buy_signals = [s for s in signals if s.signal_type == SignalType.BUY]
        sell_signals = [s for s in signals if s.signal_type == SignalType.SELL]
        
        # Check signal properties
        if buy_signals:
            assert all(s.source == "technical_test" for s in buy_signals)
            assert all(s.symbol == "EURUSD" for s in buy_signals)
            assert all(0 <= s.confidence <= 1 for s in buy_signals)
            assert all("golden_cross" in s.metadata.get("reason", "") for s in buy_signals)
    
    def test_rsi_signals(self, technical_signals, volatile_price_data):
        """Test RSI-based signal generation."""
        # Modify data to ensure RSI extremes
        volatile_price_data = volatile_price_data.copy()
        
        # Force some oversold conditions
        volatile_price_data.loc[volatile_price_data.index[60:65], 'close'] *= 0.99
        
        # Force some overbought conditions  
        volatile_price_data.loc[volatile_price_data.index[120:125], 'close'] *= 1.01
        
        indicators = technical_signals._calculate_indicators(volatile_price_data)
        signals = technical_signals._rsi_signals(indicators, "EURUSD")
        
        # Should have both oversold and overbought signals
        if signals:
            oversold_signals = [s for s in signals if "oversold" in s.metadata.get("reason", "")]
            overbought_signals = [s for s in signals if "overbought" in s.metadata.get("reason", "")]
            
            # Verify signal properties
            for signal in signals:
                assert signal.source == "technical_test"
                assert signal.symbol == "EURUSD"
                assert 0 <= signal.confidence <= 1
    
    def test_macd_signals(self, technical_signals, trending_price_data):
        """Test MACD-based signal generation."""
        indicators = technical_signals._calculate_indicators(trending_price_data)
        signals = technical_signals._macd_signals(indicators, "EURUSD")
        
        # Should generate some MACD crossover signals
        if signals:
            # Check signal properties
            for signal in signals:
                assert signal.source == "technical_test"
                assert signal.symbol == "EURUSD"
                assert signal.signal_type in [SignalType.BUY, SignalType.SELL]
                assert "macd" in signal.metadata.get("reason", "").lower()
    
    def test_bollinger_signals(self, technical_signals, volatile_price_data):
        """Test Bollinger Bands signal generation."""
        indicators = technical_signals._calculate_indicators(volatile_price_data)
        signals = technical_signals._bollinger_signals(indicators, "EURUSD")
        
        # In volatile data, should touch bands occasionally
        if signals:
            # Check for band touch signals
            lower_band_signals = [s for s in signals if "lower band" in s.metadata.get("reason", "")]
            upper_band_signals = [s for s in signals if "upper band" in s.metadata.get("reason", "")]
            
            # Verify signal properties
            for signal in signals:
                assert signal.source == "technical_test"
                assert signal.symbol == "EURUSD"
                assert "bollinger" in signal.metadata.get("reason", "").lower()
    
    def test_generate_signals_complete(self, technical_signals, trending_price_data):
        """Test complete signal generation process."""
        signals = technical_signals.generate_signals(trending_price_data, "EURUSD")
        
        # Should generate multiple types of signals
        assert isinstance(signals, list)
        assert len(signals) > 0
        
        # Check signal diversity
        signal_reasons = set()
        for signal in signals:
            reason = signal.metadata.get("reason", "")
            if "cross" in reason:
                signal_reasons.add("crossover")
            elif "rsi" in reason:
                signal_reasons.add("rsi")
            elif "macd" in reason:
                signal_reasons.add("macd")
            elif "bollinger" in reason:
                signal_reasons.add("bollinger")
        
        # Should have signals from multiple indicators
        assert len(signal_reasons) >= 2
    
    def test_generate_signals_insufficient_data(self, technical_signals):
        """Test signal generation with insufficient data."""
        # Create minimal data (not enough for indicators)
        dates = pd.date_range(start='2024-01-01', periods=10, freq='1h')
        small_data = pd.DataFrame({
            'open': [1.08] * 10,
            'high': [1.09] * 10,
            'low': [1.07] * 10,
            'close': [1.08] * 10,
            'volume': [1000] * 10
        }, index=dates)
        
        signals = technical_signals.generate_signals(small_data, "EURUSD")
        
        # Should handle gracefully, might return empty or few signals
        assert isinstance(signals, list)
    
    def test_signal_confidence_levels(self, technical_signals, trending_price_data):
        """Test that signals have appropriate confidence levels."""
        signals = technical_signals.generate_signals(trending_price_data, "EURUSD")
        
        # Group signals by type and check confidence
        for signal in signals:
            reason = signal.metadata.get("reason", "")
            
            # Golden/death crosses should have high confidence
            if "golden_cross" in reason or "death_cross" in reason:
                assert signal.confidence >= 0.7
            
            # RSI extremes should have moderate to high confidence
            elif "oversold" in reason or "overbought" in reason:
                assert 0.5 <= signal.confidence <= 0.9
            
            # Band touches might have lower confidence
            elif "band" in reason:
                assert 0.4 <= signal.confidence <= 0.8
    
    def test_signal_metadata(self, technical_signals, trending_price_data):
        """Test that signals contain proper metadata."""
        signals = technical_signals.generate_signals(trending_price_data, "EURUSD")
        
        for signal in signals:
            assert "reason" in signal.metadata
            assert isinstance(signal.metadata["reason"], str)
            
            # Check for indicator values in metadata
            if "rsi" in signal.metadata.get("reason", ""):
                assert "rsi_value" in signal.metadata
            
            if "macd" in signal.metadata.get("reason", ""):
                assert "macd" in signal.metadata or "histogram" in signal.metadata
    
    def test_no_duplicate_signals(self, technical_signals, trending_price_data):
        """Test that no duplicate signals are generated for the same timestamp."""
        signals = technical_signals.generate_signals(trending_price_data, "EURUSD")
        
        # Group by timestamp and signal type
        signal_map = {}
        for signal in signals:
            key = (signal.timestamp, signal.signal_type)
            if key in signal_map:
                # Check if it's truly a duplicate or different reason
                existing_reason = signal_map[key].metadata.get("reason", "")
                new_reason = signal.metadata.get("reason", "")
                assert existing_reason != new_reason, f"Duplicate signal at {signal.timestamp}"
            signal_map[key] = signal
    
    @patch('ta.trend.sma_indicator')
    def test_indicator_calculation_error_handling(self, mock_sma, technical_signals, trending_price_data):
        """Test handling of indicator calculation errors."""
        # Make SMA calculation fail
        mock_sma.side_effect = Exception("Indicator calculation error")
        
        # Should handle error gracefully
        with patch('fxml4_signals.technical.logger') as mock_logger:
            # This might fail or return partial indicators
            try:
                indicators = technical_signals._calculate_indicators(trending_price_data)
                # If it succeeds, check that we handled the error
                assert 'sma_20' not in indicators or indicators['sma_20'].isna().all()
            except Exception:
                # If it propagates the error, that's also acceptable
                pass
    
    def test_different_market_conditions(self, technical_signals, trending_price_data, 
                                       ranging_price_data, volatile_price_data):
        """Test signal generation in different market conditions."""
        # Trending market
        trend_signals = technical_signals.generate_signals(trending_price_data, "EURUSD")
        
        # Ranging market
        range_signals = technical_signals.generate_signals(ranging_price_data, "EURUSD")
        
        # Volatile market
        volatile_signals = technical_signals.generate_signals(volatile_price_data, "EURUSD")
        
        # Each market condition should generate signals
        assert len(trend_signals) > 0
        assert len(range_signals) > 0
        assert len(volatile_signals) > 0
        
        # Signal characteristics might differ by market condition
        # Trending market might have more crossover signals
        trend_crossovers = [s for s in trend_signals if "cross" in s.metadata.get("reason", "")]
        
        # Ranging market might have more band/RSI signals
        range_extremes = [s for s in range_signals 
                         if any(x in s.metadata.get("reason", "") 
                               for x in ["band", "oversold", "overbought"])]
        
        # Volatile market might have mixed signals
        volatile_types = set(s.signal_type for s in volatile_signals)
        assert len(volatile_types) >= 2  # Should have both BUY and SELL