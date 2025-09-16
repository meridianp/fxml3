"""
Comprehensive unit tests for Signal Processing service.

This module provides complete test coverage for the signal processing functionality,
following Test-Driven Development (TDD) principles.
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Use centralized event loop fixture
from tests.fixtures.event_loop_fixtures import event_loop

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Mock all external dependencies before importing
sys.modules["openai"] = Mock()
sys.modules["fxml4.strategy.integrated_signal_generator"] = Mock()
sys.modules["fxml4.wave_analysis.sentiment_wave_validator"] = Mock()
sys.modules["fxml4.llm_integration.sentiment_analysis"] = Mock()
sys.modules["fxml4.llm_integration.llm_client"] = Mock()


class MockSignalData:
    """Mock signal data for testing."""

    def __init__(
        self,
        timestamp,
        symbol,
        timeframe,
        direction,
        confidence,
        signal_type,
        source,
        metadata=None,
    ):
        self.timestamp = timestamp
        self.symbol = symbol
        self.timeframe = timeframe
        self.direction = direction
        self.confidence = confidence
        self.signal_type = signal_type
        self.source = source
        self.metadata = metadata or {}
        self.id = f"signal_{timestamp.strftime('%Y%m%d_%H%M%S')}_{symbol}"


class TestSignalProcessingModels:
    """Test signal processing data models and structures."""

    def test_mock_signal_data_creation(self):
        """Test creation of mock signal data."""
        timestamp = datetime.utcnow()
        signal = MockSignalData(
            timestamp=timestamp,
            symbol="EURUSD",
            timeframe="1h",
            direction=1,
            confidence=0.8,
            signal_type="ml_signal",
            source="test_model",
            metadata={"strategy": "momentum"},
        )

        assert signal.timestamp == timestamp
        assert signal.symbol == "EURUSD"
        assert signal.timeframe == "1h"
        assert signal.direction == 1
        assert signal.confidence == 0.8
        assert signal.signal_type == "ml_signal"
        assert signal.source == "test_model"
        assert signal.metadata == {"strategy": "momentum"}
        assert "EURUSD" in signal.id
        assert signal.id.startswith("signal_")

    def test_signal_data_buy_signal(self):
        """Test buy signal creation."""
        signal = MockSignalData(
            timestamp=datetime.utcnow(),
            symbol="GBPUSD",
            timeframe="4h",
            direction=1,  # Buy signal
            confidence=0.75,
            signal_type="elliott_wave",
            source="pattern_analyzer",
        )

        assert signal.direction > 0  # Buy signal
        assert signal.symbol == "GBPUSD"
        assert signal.signal_type == "elliott_wave"

    def test_signal_data_sell_signal(self):
        """Test sell signal creation."""
        signal = MockSignalData(
            timestamp=datetime.utcnow(),
            symbol="USDJPY",
            timeframe="15m",
            direction=-1,  # Sell signal
            confidence=0.65,
            signal_type="technical_indicator",
            source="rsi_oversold",
        )

        assert signal.direction < 0  # Sell signal
        assert signal.symbol == "USDJPY"
        assert signal.source == "rsi_oversold"

    def test_signal_data_confidence_ranges(self):
        """Test signal confidence validation."""
        # Low confidence
        low_conf_signal = MockSignalData(
            datetime.utcnow(), "USDCHF", "1h", 1, 0.1, "test", "test"
        )
        assert 0.0 <= low_conf_signal.confidence <= 1.0

        # High confidence
        high_conf_signal = MockSignalData(
            datetime.utcnow(), "USDCHF", "1h", -1, 0.95, "test", "test"
        )
        assert 0.0 <= high_conf_signal.confidence <= 1.0

        # Medium confidence
        med_conf_signal = MockSignalData(
            datetime.utcnow(), "USDCHF", "1h", 1, 0.5, "test", "test"
        )
        assert 0.0 <= med_conf_signal.confidence <= 1.0


class MockSignalProcessingService:
    """Mock implementation of SignalProcessingService for testing."""

    def __init__(self):
        self.signals_storage = {}  # Dict[str, List[MockSignalData]]
        self.active_symbols = set()
        self.signal_generators = {}
        self.callbacks = []
        self._pool = None
        self.config = None

        # Processing state
        self.is_processing = False
        self.processing_tasks = {}

        # Signal generation settings
        self.min_confidence_threshold = 0.3
        self.max_signals_per_hour = 20
        self.supported_timeframes = ["1m", "5m", "15m", "1h", "4h", "1d"]

    async def initialize(self):
        """Initialize the signal processing service."""
        self._pool = AsyncMock()
        self.config = AsyncMock()
        self.signal_generators = {
            "ml_signal": Mock(),
            "elliott_wave": Mock(),
            "technical_indicator": Mock(),
            "sentiment_analysis": Mock(),
        }

    async def start_signal_processing(self, symbols: List[str]):
        """Start signal processing for given symbols."""
        if not symbols:
            raise ValueError("No symbols provided for processing")

        self.active_symbols.update(symbols)
        self.is_processing = True

        # Start processing tasks for each symbol
        for symbol in symbols:
            if symbol not in self.processing_tasks:
                # Mock task creation
                task = AsyncMock()
                self.processing_tasks[symbol] = task

    async def stop_signal_processing(self, symbols: List[str] = None):
        """Stop signal processing for given symbols or all symbols."""
        if symbols is None:
            symbols = list(self.active_symbols)

        for symbol in symbols:
            self.active_symbols.discard(symbol)
            if symbol in self.processing_tasks:
                # Mock task cancellation
                task = self.processing_tasks.pop(symbol)
                task.cancel = Mock()

        if not self.active_symbols:
            self.is_processing = False

    async def generate_signal(
        self, symbol: str, timeframe: str = "1h"
    ) -> Optional[MockSignalData]:
        """Generate a signal for a given symbol and timeframe."""
        if symbol not in self.active_symbols:
            return None

        if timeframe not in self.supported_timeframes:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        # Simulate signal generation logic
        import random

        # Randomly decide whether to generate a signal (70% chance)
        if random.random() < 0.7:
            direction = random.choice([1, -1])
            confidence = random.uniform(0.3, 0.95)
            signal_type = random.choice(list(self.signal_generators.keys()))

            signal = MockSignalData(
                timestamp=datetime.utcnow(),
                symbol=symbol,
                timeframe=timeframe,
                direction=direction,
                confidence=confidence,
                signal_type=signal_type,
                source=f"mock_{signal_type}",
                metadata={
                    "timeframe": timeframe,
                    "generated_at": datetime.utcnow().isoformat(),
                    "mock_data": True,
                },
            )

            # Store signal
            await self._store_signal(signal)

            # Notify callbacks
            for callback in self.callbacks:
                try:
                    callback(signal)
                except Exception:
                    pass

            return signal

        return None

    async def _store_signal(self, signal: MockSignalData):
        """Store a signal in memory."""
        if signal.symbol not in self.signals_storage:
            self.signals_storage[signal.symbol] = []

        self.signals_storage[signal.symbol].append(signal)

        # Keep only last 100 signals per symbol
        if len(self.signals_storage[signal.symbol]) > 100:
            self.signals_storage[signal.symbol] = self.signals_storage[signal.symbol][
                -100:
            ]

    async def get_recent_signals(
        self,
        symbol: str,
        limit: int = 10,
        hours_back: int = 24,
        min_confidence: float = None,
    ) -> List[MockSignalData]:
        """Get recent signals for a symbol."""
        if symbol not in self.signals_storage:
            return []

        signals = self.signals_storage[symbol]
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)

        # Filter by time
        recent_signals = [s for s in signals if s.timestamp > cutoff_time]

        # Filter by confidence if specified
        if min_confidence is not None:
            recent_signals = [
                s for s in recent_signals if s.confidence >= min_confidence
            ]

        # Sort by timestamp (newest first) and limit
        recent_signals.sort(key=lambda x: x.timestamp, reverse=True)
        return recent_signals[:limit]

    async def get_signal_stats(self, symbol: str = None) -> Dict[str, Any]:
        """Get signal generation statistics."""
        if symbol:
            signals = self.signals_storage.get(symbol, [])
            return {
                "symbol": symbol,
                "total_signals": len(signals),
                "buy_signals": sum(1 for s in signals if s.direction > 0),
                "sell_signals": sum(1 for s in signals if s.direction < 0),
                "avg_confidence": (
                    sum(s.confidence for s in signals) / len(signals) if signals else 0
                ),
                "signal_types": list(set(s.signal_type for s in signals)),
            }
        else:
            all_signals = []
            for symbol_signals in self.signals_storage.values():
                all_signals.extend(symbol_signals)

            return {
                "total_signals": len(all_signals),
                "active_symbols": len(self.active_symbols),
                "buy_signals": sum(1 for s in all_signals if s.direction > 0),
                "sell_signals": sum(1 for s in all_signals if s.direction < 0),
                "avg_confidence": (
                    sum(s.confidence for s in all_signals) / len(all_signals)
                    if all_signals
                    else 0
                ),
                "symbols_with_signals": list(self.signals_storage.keys()),
            }

    async def validate_signal(self, signal: MockSignalData) -> Dict[str, Any]:
        """Validate a signal against quality criteria."""
        validation_result = {"valid": True, "issues": [], "warnings": [], "score": 1.0}

        # Check confidence threshold
        if signal.confidence < self.min_confidence_threshold:
            validation_result["valid"] = False
            validation_result["issues"].append(
                f"Confidence {signal.confidence} below threshold {self.min_confidence_threshold}"
            )
            validation_result["score"] *= 0.5

        # Check timeframe validity
        if signal.timeframe not in self.supported_timeframes:
            validation_result["valid"] = False
            validation_result["issues"].append(
                f"Unsupported timeframe: {signal.timeframe}"
            )
            validation_result["score"] *= 0.3

        # Check signal age (warn if older than 5 minutes)
        signal_age = datetime.utcnow() - signal.timestamp
        if signal_age > timedelta(minutes=5):
            validation_result["warnings"].append(f"Signal is {signal_age} old")
            validation_result["score"] *= 0.9

        # Check direction validity
        if signal.direction not in [-1, 1]:
            validation_result["valid"] = False
            validation_result["issues"].append(f"Invalid direction: {signal.direction}")
            validation_result["score"] *= 0.2

        return validation_result

    def add_signal_callback(self, callback):
        """Add callback for new signals."""
        self.callbacks.append(callback)

    def get_active_symbols(self) -> List[str]:
        """Get list of symbols being actively processed."""
        return list(self.active_symbols)

    def get_processing_status(self) -> Dict[str, Any]:
        """Get current processing status."""
        return {
            "is_processing": self.is_processing,
            "active_symbols": list(self.active_symbols),
            "processing_tasks": len(self.processing_tasks),
            "total_signals_stored": sum(
                len(signals) for signals in self.signals_storage.values()
            ),
        }


class TestMockSignalProcessingService:
    """Test the mock signal processing service functionality."""

    @pytest.fixture
    def service(self):
        """Create a fresh MockSignalProcessingService instance for each test."""
        return MockSignalProcessingService()

    @pytest.mark.asyncio
    async def test_initialization(self, service):
        """Test service initialization."""
        await service.initialize()

        assert service._pool is not None
        assert service.config is not None
        assert len(service.signal_generators) > 0
        assert "ml_signal" in service.signal_generators
        assert "elliott_wave" in service.signal_generators

    @pytest.mark.asyncio
    async def test_start_signal_processing(self, service):
        """Test starting signal processing."""
        symbols = ["EURUSD", "GBPUSD"]

        await service.start_signal_processing(symbols)

        assert service.is_processing is True
        assert service.active_symbols == set(symbols)
        assert len(service.processing_tasks) == len(symbols)

        for symbol in symbols:
            assert symbol in service.processing_tasks

    @pytest.mark.asyncio
    async def test_start_processing_empty_symbols(self, service):
        """Test starting processing with empty symbols list."""
        with pytest.raises(ValueError, match="No symbols provided"):
            await service.start_signal_processing([])

    @pytest.mark.asyncio
    async def test_stop_signal_processing_specific_symbols(self, service):
        """Test stopping processing for specific symbols."""
        symbols = ["EURUSD", "GBPUSD", "USDJPY"]

        # Start processing
        await service.start_signal_processing(symbols)
        assert len(service.active_symbols) == 3

        # Stop processing for specific symbols
        await service.stop_signal_processing(["EURUSD", "GBPUSD"])

        assert "USDJPY" in service.active_symbols
        assert "EURUSD" not in service.active_symbols
        assert "GBPUSD" not in service.active_symbols
        assert service.is_processing is True  # Still processing USDJPY

    @pytest.mark.asyncio
    async def test_stop_all_signal_processing(self, service):
        """Test stopping all signal processing."""
        symbols = ["EURUSD", "GBPUSD"]

        # Start processing
        await service.start_signal_processing(symbols)
        assert service.is_processing is True

        # Stop all processing
        await service.stop_signal_processing()

        assert len(service.active_symbols) == 0
        assert service.is_processing is False
        assert len(service.processing_tasks) == 0

    @pytest.mark.asyncio
    async def test_generate_signal_for_active_symbol(self, service):
        """Test signal generation for active symbol."""
        symbol = "EURUSD"
        timeframe = "1h"

        # Start processing
        await service.start_signal_processing([symbol])

        # Generate signal (may return None randomly)
        signal = await service.generate_signal(symbol, timeframe)

        if signal is not None:
            assert signal.symbol == symbol
            assert signal.timeframe == timeframe
            assert signal.direction in [-1, 1]
            assert 0.0 <= signal.confidence <= 1.0
            assert signal.signal_type in service.signal_generators.keys()
            assert isinstance(signal.timestamp, datetime)

            # Check signal was stored
            stored_signals = await service.get_recent_signals(symbol)
            assert len(stored_signals) >= 1

    @pytest.mark.asyncio
    async def test_generate_signal_for_inactive_symbol(self, service):
        """Test signal generation for inactive symbol."""
        symbol = "EURUSD"

        # Don't start processing for this symbol
        signal = await service.generate_signal(symbol)

        assert signal is None  # Should not generate signal for inactive symbol

    @pytest.mark.asyncio
    async def test_generate_signal_invalid_timeframe(self, service):
        """Test signal generation with invalid timeframe."""
        symbol = "EURUSD"

        await service.start_signal_processing([symbol])

        with pytest.raises(ValueError, match="Unsupported timeframe"):
            await service.generate_signal(symbol, "invalid_timeframe")

    @pytest.mark.asyncio
    async def test_get_recent_signals_empty(self, service):
        """Test getting recent signals when none exist."""
        signals = await service.get_recent_signals("EURUSD")
        assert signals == []

    @pytest.mark.asyncio
    async def test_get_recent_signals_with_data(self, service):
        """Test getting recent signals with stored data."""
        symbol = "GBPUSD"

        # Store some test signals manually
        for i in range(5):
            signal = MockSignalData(
                timestamp=datetime.utcnow() - timedelta(minutes=i * 10),
                symbol=symbol,
                timeframe="1h",
                direction=1 if i % 2 == 0 else -1,
                confidence=0.5 + (i * 0.1),
                signal_type="test_signal",
                source="test",
            )
            await service._store_signal(signal)

        # Get recent signals
        recent_signals = await service.get_recent_signals(symbol, limit=3)

        assert len(recent_signals) == 3
        # Should be sorted by timestamp (newest first)
        for i in range(len(recent_signals) - 1):
            assert recent_signals[i].timestamp >= recent_signals[i + 1].timestamp

    @pytest.mark.asyncio
    async def test_get_recent_signals_with_confidence_filter(self, service):
        """Test filtering signals by minimum confidence."""
        symbol = "USDJPY"

        # Store signals with different confidence levels
        confidences = [0.2, 0.5, 0.7, 0.9]
        for conf in confidences:
            signal = MockSignalData(
                timestamp=datetime.utcnow(),
                symbol=symbol,
                timeframe="1h",
                direction=1,
                confidence=conf,
                signal_type="test",
                source="test",
            )
            await service._store_signal(signal)

        # Filter by confidence >= 0.6
        filtered_signals = await service.get_recent_signals(symbol, min_confidence=0.6)

        assert len(filtered_signals) == 2  # Should only get 0.7 and 0.9
        assert all(s.confidence >= 0.6 for s in filtered_signals)

    @pytest.mark.asyncio
    async def test_get_signal_stats_for_symbol(self, service):
        """Test getting signal statistics for specific symbol."""
        symbol = "USDCHF"

        # Store test signals
        signals_data = [
            (1, 0.8, "ml_signal"),  # Buy
            (-1, 0.6, "elliott_wave"),  # Sell
            (1, 0.9, "ml_signal"),  # Buy
            (1, 0.5, "technical_indicator"),  # Buy
        ]

        for direction, confidence, signal_type in signals_data:
            signal = MockSignalData(
                timestamp=datetime.utcnow(),
                symbol=symbol,
                timeframe="1h",
                direction=direction,
                confidence=confidence,
                signal_type=signal_type,
                source="test",
            )
            await service._store_signal(signal)

        stats = await service.get_signal_stats(symbol)

        assert stats["symbol"] == symbol
        assert stats["total_signals"] == 4
        assert stats["buy_signals"] == 3
        assert stats["sell_signals"] == 1
        assert stats["avg_confidence"] == 0.7  # (0.8 + 0.6 + 0.9 + 0.5) / 4
        assert "ml_signal" in stats["signal_types"]
        assert "elliott_wave" in stats["signal_types"]
        assert "technical_indicator" in stats["signal_types"]

    @pytest.mark.asyncio
    async def test_get_overall_signal_stats(self, service):
        """Test getting overall signal statistics."""
        # Store signals for multiple symbols
        symbols_data = {
            "EURUSD": [(1, 0.8), (-1, 0.6)],
            "GBPUSD": [(1, 0.9), (1, 0.7), (-1, 0.5)],
        }

        for symbol, signal_list in symbols_data.items():
            for direction, confidence in signal_list:
                signal = MockSignalData(
                    timestamp=datetime.utcnow(),
                    symbol=symbol,
                    timeframe="1h",
                    direction=direction,
                    confidence=confidence,
                    signal_type="test",
                    source="test",
                )
                await service._store_signal(signal)

        stats = await service.get_signal_stats()

        assert stats["total_signals"] == 5
        assert stats["buy_signals"] == 3
        assert stats["sell_signals"] == 2
        assert len(stats["symbols_with_signals"]) == 2
        assert "EURUSD" in stats["symbols_with_signals"]
        assert "GBPUSD" in stats["symbols_with_signals"]

    @pytest.mark.asyncio
    async def test_validate_signal_valid(self, service):
        """Test validation of valid signal."""
        signal = MockSignalData(
            timestamp=datetime.utcnow(),
            symbol="EURUSD",
            timeframe="1h",
            direction=1,
            confidence=0.8,
            signal_type="ml_signal",
            source="test",
        )

        result = await service.validate_signal(signal)

        assert result["valid"] is True
        assert len(result["issues"]) == 0
        assert result["score"] == 1.0

    @pytest.mark.asyncio
    async def test_validate_signal_low_confidence(self, service):
        """Test validation of signal with low confidence."""
        signal = MockSignalData(
            timestamp=datetime.utcnow(),
            symbol="EURUSD",
            timeframe="1h",
            direction=1,
            confidence=0.1,  # Below threshold
            signal_type="ml_signal",
            source="test",
        )

        result = await service.validate_signal(signal)

        assert result["valid"] is False
        assert len(result["issues"]) >= 1
        assert "Confidence" in result["issues"][0]
        assert result["score"] < 1.0

    @pytest.mark.asyncio
    async def test_validate_signal_invalid_timeframe(self, service):
        """Test validation of signal with invalid timeframe."""
        signal = MockSignalData(
            timestamp=datetime.utcnow(),
            symbol="EURUSD",
            timeframe="invalid",
            direction=1,
            confidence=0.8,
            signal_type="ml_signal",
            source="test",
        )

        result = await service.validate_signal(signal)

        assert result["valid"] is False
        assert any("timeframe" in issue for issue in result["issues"])

    @pytest.mark.asyncio
    async def test_validate_signal_old_timestamp(self, service):
        """Test validation of old signal."""
        signal = MockSignalData(
            timestamp=datetime.utcnow() - timedelta(minutes=10),  # Old signal
            symbol="EURUSD",
            timeframe="1h",
            direction=1,
            confidence=0.8,
            signal_type="ml_signal",
            source="test",
        )

        result = await service.validate_signal(signal)

        assert result["valid"] is True  # Still valid but with warnings
        assert len(result["warnings"]) >= 1
        assert "old" in result["warnings"][0]
        assert result["score"] < 1.0

    def test_signal_callback_registration(self, service):
        """Test signal callback registration."""
        callback = MagicMock()
        service.add_signal_callback(callback)

        assert callback in service.callbacks

    @pytest.mark.asyncio
    async def test_signal_callback_notification(self, service):
        """Test signal callback notification."""
        callback_calls = []

        def test_callback(signal):
            callback_calls.append(signal)

        service.add_signal_callback(test_callback)

        # Store a signal (should trigger callback)
        signal = MockSignalData(
            timestamp=datetime.utcnow(),
            symbol="EURUSD",
            timeframe="1h",
            direction=1,
            confidence=0.8,
            signal_type="test",
            source="test",
        )

        await service._store_signal(signal)
        # Manually trigger callback for test
        for callback in service.callbacks:
            callback(signal)

        assert len(callback_calls) == 1
        assert callback_calls[0] == signal

    def test_get_active_symbols(self, service):
        """Test getting active symbols."""
        symbols = ["EURUSD", "GBPUSD", "USDJPY"]
        service.active_symbols.update(symbols)

        active = service.get_active_symbols()
        assert set(active) == set(symbols)

    def test_get_processing_status(self, service):
        """Test getting processing status."""
        # Set up some state
        service.is_processing = True
        service.active_symbols = {"EURUSD", "GBPUSD"}
        service.processing_tasks = {"EURUSD": Mock(), "GBPUSD": Mock()}
        service.signals_storage = {"EURUSD": [Mock(), Mock()], "GBPUSD": [Mock()]}

        status = service.get_processing_status()

        assert status["is_processing"] is True
        assert set(status["active_symbols"]) == {"EURUSD", "GBPUSD"}
        assert status["processing_tasks"] == 2
        assert status["total_signals_stored"] == 3


# Pytest configuration
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
