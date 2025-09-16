"""Real-time signal generation module for live trading.

This module provides real-time trading signal generation capabilities required by the
integration test suite, implementing low-latency signal processing and multi-strategy
coordination for production trading environments.
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set

import numpy as np

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Trading signal types."""

    BUY = "BUY"
    SELL = "SELL"
    EXIT = "EXIT"
    HOLD = "HOLD"


class SignalStrength(Enum):
    """Signal strength levels."""

    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"
    VERY_STRONG = "VERY_STRONG"


@dataclass
class TradingSignal:
    """Trading signal data structure."""

    symbol: str
    signal_type: SignalType
    strength: SignalStrength
    confidence: float
    price: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = "realtime"
    metadata: Dict[str, Any] = field(default_factory=dict)
    expiry_time: Optional[datetime] = None
    risk_score: float = 0.5
    position_size: float = 1.0

    def is_expired(self) -> bool:
        """Check if signal has expired."""
        if self.expiry_time is None:
            return False
        return datetime.utcnow() > self.expiry_time

    def age_seconds(self) -> float:
        """Get signal age in seconds."""
        return (datetime.utcnow() - self.timestamp).total_seconds()


class RealTimeSignalGenerator:
    """Real-time trading signal generator for live trading.

    This class implements the interface expected by the integration test suite,
    providing low-latency signal generation and efficient signal management for
    real-time trading operations.
    """

    def __init__(
        self,
        signal_buffer_size: int = 1000,
        signal_expiry_seconds: int = 300,
        min_confidence_threshold: float = 0.6,
        max_signals_per_symbol: int = 5,
    ):
        """Initialize the real-time signal generator.

        Args:
            signal_buffer_size: Maximum number of signals to keep in memory
            signal_expiry_seconds: Default signal expiry time in seconds
            min_confidence_threshold: Minimum confidence to generate signals
            max_signals_per_symbol: Maximum active signals per symbol
        """
        self.signal_buffer_size = signal_buffer_size
        self.signal_expiry_seconds = signal_expiry_seconds
        self.min_confidence_threshold = min_confidence_threshold
        self.max_signals_per_symbol = max_signals_per_symbol

        # Signal storage
        self.active_signals: Dict[str, List[TradingSignal]] = {}
        self.signal_history: List[TradingSignal] = []
        self.last_signal_time: Dict[str, datetime] = {}

        # Strategy components
        self.strategy_weights: Dict[str, float] = {
            "technical": 0.4,
            "ml_model": 0.3,
            "momentum": 0.2,
            "mean_reversion": 0.1,
        }

        # Performance tracking
        self.signals_generated = 0
        self.signals_expired = 0
        self.processing_time_total = 0.0

        # Threading for concurrent processing
        self._signal_lock = threading.RLock()
        self._cleanup_lock = threading.Lock()

        logger.info(
            "RealTimeSignalGenerator initialized: buffer_size=%d, expiry=%ds",
            signal_buffer_size,
            signal_expiry_seconds,
        )

    async def process_live_signal(
        self,
        symbol: str,
        features: Dict[str, Any],
        market_data: Dict[str, Any],
        strategy_hints: Optional[Dict[str, Any]] = None,
    ) -> Optional[TradingSignal]:
        """Process real-time data and generate trading signals.

        Args:
            symbol: Trading symbol (e.g., 'EURUSD')
            features: Real-time computed features
            market_data: Current market data
            strategy_hints: Additional strategy parameters

        Returns:
            Generated trading signal or None if no signal
        """
        start_time = time.time()

        try:
            # Validate inputs
            if not features or not market_data:
                return None

            current_price = market_data.get("price", 0.0)
            if current_price <= 0:
                logger.warning(f"Invalid price for {symbol}: {current_price}")
                return None

            # Clean up expired signals
            await self._cleanup_expired_signals(symbol)

            # Check if we already have too many active signals
            if len(self.active_signals.get(symbol, [])) >= self.max_signals_per_symbol:
                logger.debug(f"Max signals reached for {symbol}")
                return None

            # Generate signal using multi-strategy approach
            signal = await self._generate_composite_signal(
                symbol, features, market_data, strategy_hints
            )

            # Validate signal quality
            if signal and signal.confidence >= self.min_confidence_threshold:
                # Store signal
                with self._signal_lock:
                    if symbol not in self.active_signals:
                        self.active_signals[symbol] = []

                    self.active_signals[symbol].append(signal)
                    self.signal_history.append(signal)
                    self.last_signal_time[symbol] = datetime.utcnow()
                    self.signals_generated += 1

                    # Maintain buffer size
                    if len(self.signal_history) > self.signal_buffer_size:
                        self.signal_history.pop(0)

                processing_time = time.time() - start_time
                self.processing_time_total += processing_time

                logger.info(
                    f"Signal generated for {symbol}: {signal.signal_type.value} "
                    f"(confidence: {signal.confidence:.3f}, time: {processing_time*1000:.1f}ms)"
                )

                return signal

            return None

        except Exception as e:
            logger.error(f"Error processing live signal for {symbol}: {str(e)}")
            return None

    async def get_active_signals(
        self,
        symbol: Optional[str] = None,
        signal_types: Optional[List[SignalType]] = None,
        min_confidence: Optional[float] = None,
    ) -> List[TradingSignal]:
        """Get currently active trading signals.

        Args:
            symbol: Specific symbol to filter by (optional)
            signal_types: Specific signal types to include (optional)
            min_confidence: Minimum confidence threshold (optional)

        Returns:
            List of active trading signals
        """
        with self._signal_lock:
            signals = []

            # Collect signals from all or specific symbol
            if symbol:
                signals.extend(self.active_signals.get(symbol, []))
            else:
                for symbol_signals in self.active_signals.values():
                    signals.extend(symbol_signals)

            # Apply filters
            filtered_signals = []
            for signal in signals:
                # Check if signal is expired
                if signal.is_expired():
                    continue

                # Filter by signal type
                if signal_types and signal.signal_type not in signal_types:
                    continue

                # Filter by minimum confidence
                if min_confidence and signal.confidence < min_confidence:
                    continue

                filtered_signals.append(signal)

            # Sort by confidence (descending)
            filtered_signals.sort(key=lambda s: s.confidence, reverse=True)

            return filtered_signals

    async def cancel_signals(
        self, symbol: str, signal_types: Optional[List[SignalType]] = None
    ) -> int:
        """Cancel active signals for a symbol.

        Args:
            symbol: Symbol to cancel signals for
            signal_types: Specific signal types to cancel (optional)

        Returns:
            Number of signals cancelled
        """
        cancelled_count = 0

        with self._signal_lock:
            if symbol not in self.active_signals:
                return 0

            remaining_signals = []
            for signal in self.active_signals[symbol]:
                if signal_types and signal.signal_type not in signal_types:
                    remaining_signals.append(signal)
                else:
                    cancelled_count += 1

            self.active_signals[symbol] = remaining_signals

            if not remaining_signals:
                del self.active_signals[symbol]

        logger.info(f"Cancelled {cancelled_count} signals for {symbol}")
        return cancelled_count

    async def get_signal_stats(self) -> Dict[str, Any]:
        """Get signal generation statistics.

        Returns:
            Dictionary containing performance metrics
        """
        with self._signal_lock:
            total_active = sum(len(signals) for signals in self.active_signals.values())

            avg_processing_time = (
                self.processing_time_total / self.signals_generated
                if self.signals_generated > 0
                else 0.0
            )

            # Calculate signal distribution
            signal_type_counts = {}
            for signals in self.active_signals.values():
                for signal in signals:
                    signal_type = signal.signal_type.value
                    signal_type_counts[signal_type] = (
                        signal_type_counts.get(signal_type, 0) + 1
                    )

            return {
                "total_generated": self.signals_generated,
                "active_signals": total_active,
                "expired_signals": self.signals_expired,
                "symbols_tracked": len(self.active_signals),
                "avg_processing_time_ms": avg_processing_time * 1000,
                "signal_distribution": signal_type_counts,
                "strategy_weights": self.strategy_weights.copy(),
            }

    # Private signal generation methods

    async def _generate_composite_signal(
        self,
        symbol: str,
        features: Dict[str, Any],
        market_data: Dict[str, Any],
        strategy_hints: Optional[Dict[str, Any]],
    ) -> Optional[TradingSignal]:
        """Generate signal using composite strategy approach."""

        # Get individual strategy signals
        technical_signal = self._generate_technical_signal(
            symbol, features, market_data
        )
        ml_signal = self._generate_ml_signal(symbol, features, market_data)
        momentum_signal = self._generate_momentum_signal(symbol, features)
        mean_reversion_signal = self._generate_mean_reversion_signal(symbol, features)

        # Combine signals using weighted voting
        signal_votes = {}
        confidence_sum = 0.0

        if technical_signal:
            weight = self.strategy_weights["technical"]
            signal_votes[technical_signal.signal_type] = (
                signal_votes.get(technical_signal.signal_type, 0) + weight
            )
            confidence_sum += technical_signal.confidence * weight

        if ml_signal:
            weight = self.strategy_weights["ml_model"]
            signal_votes[ml_signal.signal_type] = (
                signal_votes.get(ml_signal.signal_type, 0) + weight
            )
            confidence_sum += ml_signal.confidence * weight

        if momentum_signal:
            weight = self.strategy_weights["momentum"]
            signal_votes[momentum_signal.signal_type] = (
                signal_votes.get(momentum_signal.signal_type, 0) + weight
            )
            confidence_sum += momentum_signal.confidence * weight

        if mean_reversion_signal:
            weight = self.strategy_weights["mean_reversion"]
            signal_votes[mean_reversion_signal.signal_type] = (
                signal_votes.get(mean_reversion_signal.signal_type, 0) + weight
            )
            confidence_sum += mean_reversion_signal.confidence * weight

        # Determine winning signal type
        if not signal_votes:
            return None

        winning_signal_type = max(signal_votes.keys(), key=lambda k: signal_votes[k])
        winning_weight = signal_votes[winning_signal_type]

        # Only generate signal if it has sufficient support
        if winning_weight < 0.3:  # Minimum 30% support
            return None

        # Calculate composite confidence
        composite_confidence = min(0.95, confidence_sum)

        # Determine signal strength based on confidence and support
        if composite_confidence >= 0.8 and winning_weight >= 0.7:
            strength = SignalStrength.VERY_STRONG
        elif composite_confidence >= 0.7 and winning_weight >= 0.5:
            strength = SignalStrength.STRONG
        elif composite_confidence >= 0.6:
            strength = SignalStrength.MODERATE
        else:
            strength = SignalStrength.WEAK

        # Create composite signal
        current_price = market_data.get("price", 0.0)
        expiry_time = datetime.utcnow() + timedelta(seconds=self.signal_expiry_seconds)

        signal = TradingSignal(
            symbol=symbol,
            signal_type=winning_signal_type,
            strength=strength,
            confidence=composite_confidence,
            price=current_price,
            expiry_time=expiry_time,
            source="realtime_composite",
            metadata={
                "strategy_votes": signal_votes,
                "winning_weight": winning_weight,
                "features_used": list(features.keys()),
                "strategy_hints": strategy_hints or {},
            },
            risk_score=self._calculate_risk_score(features, winning_signal_type),
            position_size=self._calculate_position_size(composite_confidence, strength),
        )

        return signal

    def _generate_technical_signal(
        self, symbol: str, features: Dict[str, Any], market_data: Dict[str, Any]
    ) -> Optional[TradingSignal]:
        """Generate signal based on technical indicators."""
        try:
            # RSI-based signals
            rsi = features.get("rsi", 50.0)
            bb_position = features.get("bb_position", 0.5)
            macd = features.get("macd", 0.0)

            signal_score = 0.0
            signal_type = SignalType.HOLD

            # RSI signals
            if rsi < 30:  # Oversold
                signal_score += 0.4
                signal_type = SignalType.BUY
            elif rsi > 70:  # Overbought
                signal_score += 0.4
                signal_type = SignalType.SELL

            # Bollinger Bands signals
            if bb_position < 0.2:  # Near lower band
                signal_score += 0.3 if signal_type == SignalType.BUY else -0.2
            elif bb_position > 0.8:  # Near upper band
                signal_score += 0.3 if signal_type == SignalType.SELL else -0.2

            # MACD signals
            if macd > 0.001:  # Bullish MACD
                signal_score += 0.2 if signal_type == SignalType.BUY else -0.1
            elif macd < -0.001:  # Bearish MACD
                signal_score += 0.2 if signal_type == SignalType.SELL else -0.1

            if abs(signal_score) > 0.4:
                confidence = min(0.9, abs(signal_score))
                return TradingSignal(
                    symbol=symbol,
                    signal_type=signal_type,
                    strength=SignalStrength.MODERATE,
                    confidence=confidence,
                    price=market_data.get("price", 0.0),
                    source="technical",
                )

            return None

        except Exception as e:
            logger.debug(f"Technical signal generation error: {e}")
            return None

    def _generate_ml_signal(
        self, symbol: str, features: Dict[str, Any], market_data: Dict[str, Any]
    ) -> Optional[TradingSignal]:
        """Generate signal based on ML model predictions."""
        try:
            # Simulate ML model prediction based on features
            feature_sum = sum(
                float(v) for v in features.values() if isinstance(v, (int, float))
            )
            normalized_score = np.tanh(feature_sum / len(features)) if features else 0.0

            if abs(normalized_score) > 0.3:
                signal_type = (
                    SignalType.BUY if normalized_score > 0 else SignalType.SELL
                )
                confidence = min(0.9, abs(normalized_score) + 0.4)

                return TradingSignal(
                    symbol=symbol,
                    signal_type=signal_type,
                    strength=SignalStrength.MODERATE,
                    confidence=confidence,
                    price=market_data.get("price", 0.0),
                    source="ml_model",
                )

            return None

        except Exception as e:
            logger.debug(f"ML signal generation error: {e}")
            return None

    def _generate_momentum_signal(
        self, symbol: str, features: Dict[str, Any]
    ) -> Optional[TradingSignal]:
        """Generate momentum-based signals."""
        try:
            momentum = features.get("momentum", 0.0)
            price_change = features.get("return", 0.0)
            volatility = features.get("volatility", 0.0)

            if (
                abs(momentum) > 0.02 and volatility < 0.05
            ):  # Strong momentum, low volatility
                signal_type = SignalType.BUY if momentum > 0 else SignalType.SELL
                confidence = min(0.8, abs(momentum) * 10)

                return TradingSignal(
                    symbol=symbol,
                    signal_type=signal_type,
                    strength=SignalStrength.MODERATE,
                    confidence=confidence,
                    price=features.get("price", 0.0),
                    source="momentum",
                )

            return None

        except Exception as e:
            logger.debug(f"Momentum signal generation error: {e}")
            return None

    def _generate_mean_reversion_signal(
        self, symbol: str, features: Dict[str, Any]
    ) -> Optional[TradingSignal]:
        """Generate mean reversion signals."""
        try:
            bb_position = features.get("bb_position", 0.5)
            volatility = features.get("volatility", 0.0)

            # Mean reversion when price is at extremes with high volatility
            if volatility > 0.02:
                if bb_position < 0.1:  # Very low in BB
                    return TradingSignal(
                        symbol=symbol,
                        signal_type=SignalType.BUY,
                        strength=SignalStrength.WEAK,
                        confidence=0.6,
                        price=features.get("price", 0.0),
                        source="mean_reversion",
                    )
                elif bb_position > 0.9:  # Very high in BB
                    return TradingSignal(
                        symbol=symbol,
                        signal_type=SignalType.SELL,
                        strength=SignalStrength.WEAK,
                        confidence=0.6,
                        price=features.get("price", 0.0),
                        source="mean_reversion",
                    )

            return None

        except Exception as e:
            logger.debug(f"Mean reversion signal generation error: {e}")
            return None

    def _calculate_risk_score(
        self, features: Dict[str, Any], signal_type: SignalType
    ) -> float:
        """Calculate risk score for the signal."""
        try:
            volatility = features.get("volatility", 0.02)
            volume = features.get("volume", 1000.0)

            # Base risk from volatility
            risk_score = min(0.9, volatility * 20)  # Scale volatility to 0-1

            # Adjust for volume (lower volume = higher risk)
            if volume < 500:
                risk_score += 0.2

            return max(0.1, min(0.9, risk_score))

        except Exception:
            return 0.5  # Default moderate risk

    def _calculate_position_size(
        self, confidence: float, strength: SignalStrength
    ) -> float:
        """Calculate recommended position size."""
        try:
            base_size = confidence * 0.8  # Base on confidence

            # Adjust for signal strength
            strength_multiplier = {
                SignalStrength.WEAK: 0.5,
                SignalStrength.MODERATE: 0.8,
                SignalStrength.STRONG: 1.0,
                SignalStrength.VERY_STRONG: 1.2,
            }.get(strength, 0.8)

            return max(0.1, min(2.0, base_size * strength_multiplier))

        except Exception:
            return 1.0  # Default position size

    async def _cleanup_expired_signals(self, symbol: Optional[str] = None) -> int:
        """Remove expired signals from active signals."""
        removed_count = 0

        with self._signal_lock:
            symbols_to_check = [symbol] if symbol else list(self.active_signals.keys())

            for sym in symbols_to_check:
                if sym not in self.active_signals:
                    continue

                active_signals = []
                for signal in self.active_signals[sym]:
                    if signal.is_expired():
                        removed_count += 1
                        self.signals_expired += 1
                    else:
                        active_signals.append(signal)

                if active_signals:
                    self.active_signals[sym] = active_signals
                else:
                    del self.active_signals[sym]

        if removed_count > 0:
            logger.debug(f"Cleaned up {removed_count} expired signals")

        return removed_count
