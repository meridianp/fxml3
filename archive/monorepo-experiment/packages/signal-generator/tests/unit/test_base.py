"""Tests for base signal generation classes."""

import pytest
from datetime import datetime, timedelta
from typing import List
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch

from fxml4_signals.base import (
    Signal, SignalType, SignalSource, SignalGenerator
)


@pytest.fixture
def sample_signal_data():
    """Create sample signal data."""
    return {
        "timestamp": datetime.now(),
        "symbol": "EURUSD",
        "signal_type": SignalType.BUY,
        "source": "test_source",
        "confidence": 0.75,
        "price": 1.0850,
        "metadata": {"reason": "test signal", "indicators": ["rsi", "macd"]}
    }


@pytest.fixture
def sample_price_data():
    """Create sample price data DataFrame."""
    dates = pd.date_range(start='2024-01-15 00:00', periods=100, freq='5min')
    data = {
        'open': np.random.randn(100).cumsum() + 1.0850,
        'high': np.random.randn(100).cumsum() + 1.0860,
        'low': np.random.randn(100).cumsum() + 1.0840,
        'close': np.random.randn(100).cumsum() + 1.0855,
        'volume': np.random.randint(1000, 10000, 100)
    }
    df = pd.DataFrame(data, index=dates)
    
    # Ensure OHLC relationships
    df['high'] = df[['open', 'close', 'high']].max(axis=1)
    df['low'] = df[['open', 'close', 'low']].min(axis=1)
    
    return df


class ConcreteSignalSource(SignalSource):
    """Concrete implementation of SignalSource for testing."""
    
    def get_required_columns(self) -> List[str]:
        return ["close", "volume"]
    
    def generate_signals(self, data: pd.DataFrame, symbol: str) -> List[Signal]:
        """Generate dummy signals for testing."""
        signals = []
        
        # Generate a signal every 10 bars
        for i in range(9, len(data), 10):
            signal_type = SignalType.BUY if i % 20 == 9 else SignalType.SELL
            signal = Signal(
                timestamp=data.index[i],
                symbol=symbol,
                signal_type=signal_type,
                source=self.name,
                confidence=0.6 + (i % 10) * 0.04,  # 0.6 to 0.96
                price=data['close'].iloc[i],
                metadata={"bar_index": i}
            )
            signals.append(signal)
        
        return signals


class TestSignalType:
    """Test SignalType enum."""
    
    def test_signal_types(self):
        """Test all signal type values."""
        assert SignalType.BUY.value == "BUY"
        assert SignalType.SELL.value == "SELL"
        assert SignalType.HOLD.value == "HOLD"
        assert SignalType.CLOSE_LONG.value == "CLOSE_LONG"
        assert SignalType.CLOSE_SHORT.value == "CLOSE_SHORT"
    
    def test_signal_type_from_string(self):
        """Test creating signal type from string."""
        signal_type = SignalType("BUY")
        assert signal_type == SignalType.BUY


class TestSignal:
    """Test Signal dataclass."""
    
    def test_signal_creation(self, sample_signal_data):
        """Test creating a signal."""
        signal = Signal(**sample_signal_data)
        
        assert signal.timestamp == sample_signal_data["timestamp"]
        assert signal.symbol == "EURUSD"
        assert signal.signal_type == SignalType.BUY
        assert signal.source == "test_source"
        assert signal.confidence == 0.75
        assert signal.price == 1.0850
        assert signal.metadata["reason"] == "test signal"
    
    def test_signal_confidence_validation(self, sample_signal_data):
        """Test signal confidence validation."""
        # Valid confidence
        sample_signal_data["confidence"] = 0.0
        signal = Signal(**sample_signal_data)
        assert signal.confidence == 0.0
        
        sample_signal_data["confidence"] = 1.0
        signal = Signal(**sample_signal_data)
        assert signal.confidence == 1.0
        
        # Invalid confidence
        sample_signal_data["confidence"] = -0.1
        with pytest.raises(ValueError, match="Confidence must be between 0 and 1"):
            Signal(**sample_signal_data)
        
        sample_signal_data["confidence"] = 1.1
        with pytest.raises(ValueError, match="Confidence must be between 0 and 1"):
            Signal(**sample_signal_data)
    
    def test_signal_to_dict(self, sample_signal_data):
        """Test converting signal to dictionary."""
        signal = Signal(**sample_signal_data)
        signal_dict = signal.to_dict()
        
        assert signal_dict["timestamp"] == sample_signal_data["timestamp"].isoformat()
        assert signal_dict["symbol"] == "EURUSD"
        assert signal_dict["signal_type"] == "BUY"
        assert signal_dict["source"] == "test_source"
        assert signal_dict["confidence"] == 0.75
        assert signal_dict["price"] == 1.0850
        assert signal_dict["metadata"] == sample_signal_data["metadata"]
    
    def test_signal_immutability(self, sample_signal_data):
        """Test that signal fields are set correctly."""
        signal = Signal(**sample_signal_data)
        
        # Verify all fields are accessible
        assert hasattr(signal, 'timestamp')
        assert hasattr(signal, 'symbol')
        assert hasattr(signal, 'signal_type')
        assert hasattr(signal, 'source')
        assert hasattr(signal, 'confidence')
        assert hasattr(signal, 'price')
        assert hasattr(signal, 'metadata')


class TestSignalSource:
    """Test SignalSource abstract class."""
    
    def test_signal_source_initialization(self):
        """Test SignalSource initialization."""
        source = ConcreteSignalSource(name="test", weight=0.8)
        assert source.name == "test"
        assert source.weight == 0.8
    
    def test_signal_source_is_abstract(self):
        """Test that SignalSource cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            SignalSource("test")
    
    def test_validate_data_empty(self):
        """Test data validation with empty DataFrame."""
        source = ConcreteSignalSource("test")
        empty_df = pd.DataFrame()
        
        with patch('fxml4_signals.base.logger') as mock_logger:
            result = source.validate_data(empty_df)
            assert result is False
            mock_logger.warning.assert_called_once()
    
    def test_validate_data_missing_columns(self, sample_price_data):
        """Test data validation with missing columns."""
        source = ConcreteSignalSource("test")
        
        # Remove required column
        data = sample_price_data.drop(columns=['volume'])
        
        with patch('fxml4_signals.base.logger') as mock_logger:
            result = source.validate_data(data)
            assert result is False
            mock_logger.error.assert_called_once()
            
            # Check error message contains missing column
            error_call = mock_logger.error.call_args[0][0]
            assert "volume" in error_call
    
    def test_validate_data_success(self, sample_price_data):
        """Test successful data validation."""
        source = ConcreteSignalSource("test")
        result = source.validate_data(sample_price_data)
        assert result is True
    
    def test_generate_signals(self, sample_price_data):
        """Test signal generation."""
        source = ConcreteSignalSource("test")
        signals = source.generate_signals(sample_price_data, "EURUSD")
        
        # Should generate signals every 10 bars
        expected_count = len(sample_price_data) // 10
        assert len(signals) == expected_count
        
        # Check first signal
        assert signals[0].symbol == "EURUSD"
        assert signals[0].source == "test"
        assert signals[0].signal_type in [SignalType.BUY, SignalType.SELL]
        assert 0.6 <= signals[0].confidence <= 1.0


class TestSignalGenerator:
    """Test SignalGenerator class."""
    
    def test_initialization(self):
        """Test SignalGenerator initialization."""
        generator = SignalGenerator(min_confidence=0.6)
        assert generator.min_confidence == 0.6
        assert generator.sources == []
        assert generator.signal_history == []
    
    def test_add_source(self):
        """Test adding signal sources."""
        generator = SignalGenerator()
        source1 = ConcreteSignalSource("source1", weight=0.8)
        source2 = ConcreteSignalSource("source2", weight=1.2)
        
        with patch('fxml4_signals.base.logger') as mock_logger:
            generator.add_source(source1)
            generator.add_source(source2)
            
            assert len(generator.sources) == 2
            assert generator.sources[0] == source1
            assert generator.sources[1] == source2
            
            # Check logging
            assert mock_logger.info.call_count == 2
    
    def test_generate_signals(self, sample_price_data):
        """Test generating signals from sources."""
        generator = SignalGenerator(min_confidence=0.7)
        source = ConcreteSignalSource("test", weight=1.0)
        generator.add_source(source)
        
        result = generator.generate(sample_price_data, "EURUSD")
        
        # Check result is DataFrame
        assert isinstance(result, pd.DataFrame)
        assert not result.empty
        
        # Check signals were filtered by confidence
        assert all(result['confidence'] >= 0.7)
        
        # Check signal history was updated
        assert len(generator.signal_history) > 0
        assert all(s.confidence >= 0.7 for s in generator.signal_history)
    
    def test_generate_with_weighted_source(self, sample_price_data):
        """Test signal generation with weighted sources."""
        generator = SignalGenerator(min_confidence=0.5)
        source = ConcreteSignalSource("test", weight=0.5)
        generator.add_source(source)
        
        result = generator.generate(sample_price_data, "EURUSD")
        
        # All confidences should be halved due to weight
        raw_signals = source.generate_signals(sample_price_data, "EURUSD")
        expected_confidences = [s.confidence * 0.5 for s in raw_signals if s.confidence * 0.5 >= 0.5]
        
        assert len(result) == len(expected_confidences)
    
    def test_generate_with_multiple_sources(self, sample_price_data):
        """Test generating signals from multiple sources."""
        generator = SignalGenerator(min_confidence=0.5)
        
        source1 = ConcreteSignalSource("source1", weight=1.0)
        source2 = ConcreteSignalSource("source2", weight=0.8)
        
        generator.add_source(source1)
        generator.add_source(source2)
        
        result = generator.generate(sample_price_data, "EURUSD")
        
        # Should have signals from both sources
        assert not result.empty
        assert len(result) > 0
        
        # Check sources in result
        unique_sources = result['source'].unique()
        assert "source1" in unique_sources
        assert "source2" in unique_sources
    
    def test_generate_with_source_error(self, sample_price_data):
        """Test signal generation when source raises error."""
        generator = SignalGenerator()
        
        # Create a source that raises an error
        source = ConcreteSignalSource("error_source")
        source.generate_signals = Mock(side_effect=Exception("Test error"))
        
        generator.add_source(source)
        
        with patch('fxml4_signals.base.logger') as mock_logger:
            result = generator.generate(sample_price_data, "EURUSD")
            
            # Should return empty DataFrame
            assert result.empty
            
            # Error should be logged
            mock_logger.error.assert_called_once()
            error_msg = mock_logger.error.call_args[0][0]
            assert "error_source" in error_msg
            assert "Test error" in error_msg
    
    def test_generate_no_signals(self, sample_price_data):
        """Test generation when no signals meet confidence threshold."""
        generator = SignalGenerator(min_confidence=0.99)  # Very high threshold
        source = ConcreteSignalSource("test")
        generator.add_source(source)
        
        result = generator.generate(sample_price_data, "EURUSD")
        
        # Should return empty DataFrame
        assert result.empty
        assert len(generator.signal_history) == 0
    
    def test_aggregate_signals(self):
        """Test signal aggregation."""
        generator = SignalGenerator()
        
        # Create sample signals DataFrame
        timestamps = pd.date_range('2024-01-15 00:00', periods=20, freq='1min')
        signals_data = []
        
        for i, ts in enumerate(timestamps):
            signals_data.append({
                'timestamp': ts,
                'symbol': 'EURUSD',
                'signal_type': 'BUY' if i % 2 == 0 else 'SELL',
                'confidence': 0.7 + (i % 5) * 0.05,
                'price': 1.0850 + i * 0.0001
            })
        
        signals_df = pd.DataFrame(signals_data).set_index('timestamp')
        
        # Aggregate over 5-minute windows
        aggregated = generator.aggregate_signals(signals_df, window='5min')
        
        # Check aggregation results
        assert not aggregated.empty
        assert 'avg_confidence' in aggregated.columns
        assert 'max_confidence' in aggregated.columns
        assert 'signal_count' in aggregated.columns
        assert 'avg_price' in aggregated.columns
        
        # Should have fewer rows after aggregation
        assert len(aggregated) < len(signals_df)
    
    def test_aggregate_empty_signals(self):
        """Test aggregating empty signals."""
        generator = SignalGenerator()
        empty_df = pd.DataFrame()
        
        result = generator.aggregate_signals(empty_df)
        assert result.empty
    
    def test_get_latest_signals(self):
        """Test getting latest signals from history."""
        generator = SignalGenerator()
        
        # Create signals with different timestamps
        base_time = datetime.now()
        for i in range(20):
            signal = Signal(
                timestamp=base_time - timedelta(minutes=i),
                symbol="EURUSD" if i % 2 == 0 else "GBPUSD",
                signal_type=SignalType.BUY,
                source="test",
                confidence=0.8,
                price=1.0850,
                metadata={}
            )
            generator.signal_history.append(signal)
        
        # Get latest 10 signals
        latest = generator.get_latest_signals(n=10)
        assert len(latest) == 10
        
        # Should be sorted by timestamp descending
        for i in range(len(latest) - 1):
            assert latest[i].timestamp >= latest[i + 1].timestamp
        
        # Get latest for specific symbol
        eurusd_signals = generator.get_latest_signals(symbol="EURUSD", n=5)
        assert len(eurusd_signals) <= 5
        assert all(s.symbol == "EURUSD" for s in eurusd_signals)
    
    def test_get_latest_signals_empty_history(self):
        """Test getting latest signals with empty history."""
        generator = SignalGenerator()
        latest = generator.get_latest_signals()
        assert latest == []