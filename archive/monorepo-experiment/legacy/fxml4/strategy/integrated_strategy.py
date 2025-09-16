"""Integrated trading strategy framework.

This module provides a framework for combining multiple signal generators
into a unified trading strategy.
"""

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from fxml4.config import get_config

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Signal type enumeration."""
    
    ENTRY_LONG = "entry_long"
    ENTRY_SHORT = "entry_short"
    EXIT_LONG = "exit_long"
    EXIT_SHORT = "exit_short"
    UNKNOWN = "unknown"


class SignalStrength(Enum):
    """Signal strength enumeration."""
    
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NEUTRAL = "neutral"


class SignalSource(Enum):
    """Signal source enumeration."""
    
    ML = "ml"
    WAVE = "wave"
    TECHNICAL = "technical"
    SENTIMENT = "sentiment"
    ENSEMBLE = "ensemble"


class Signal:
    """Trading signal data structure."""
    
    def __init__(
        self,
        signal_type: SignalType,
        strength: float,
        source: SignalSource,
        timestamp: pd.Timestamp,
        symbol: str,
        timeframe: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Initialize a trading signal.
        
        Args:
            signal_type: Type of signal.
            strength: Signal strength between 0 and 1.
            source: Source of the signal.
            timestamp: Timestamp of the signal.
            symbol: Trading symbol for the signal.
            timeframe: Timeframe for the signal.
            metadata: Additional signal metadata.
        """
        self.signal_type = signal_type
        self.strength = strength
        self.source = source
        self.timestamp = timestamp
        self.symbol = symbol
        self.timeframe = timeframe
        self.metadata = metadata or {}
        
        # Validate signal strength
        if not 0 <= strength <= 1:
            logger.warning("Signal strength outside of [0, 1] range: %f", strength)
            self.strength = max(0, min(1, strength))
    
    @property
    def strength_category(self) -> SignalStrength:
        """Get the categorical strength of the signal.
        
        Returns:
            Signal strength category.
        """
        if self.strength >= 0.7:
            return SignalStrength.STRONG
        elif self.strength >= 0.5:
            return SignalStrength.MODERATE
        elif self.strength >= 0.3:
            return SignalStrength.WEAK
        else:
            return SignalStrength.NEUTRAL
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert signal to dictionary representation.
        
        Returns:
            Dictionary representation of the signal.
        """
        return {
            "signal_type": self.signal_type.value,
            "strength": self.strength,
            "source": self.source.value,
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "strength_category": self.strength_category.value,
            "metadata": self.metadata,
        }
    
    def __str__(self) -> str:
        """Get string representation of the signal.
        
        Returns:
            String representation.
        """
        return (
            f"{self.source.value} {self.signal_type.value} signal "
            f"({self.strength_category.value}, {self.strength:.2f}) "
            f"for {self.symbol} ({self.timeframe}) at {self.timestamp}"
        )


class SignalGenerator(ABC):
    """Abstract base class for signal generators."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the signal generator.
        
        Args:
            config: Configuration dictionary.
        """
        self.config = config or {}
        self.name = self.__class__.__name__
    
    @abstractmethod
    def generate_signals(
        self, 
        data: pd.DataFrame,
        **kwargs: Any,
    ) -> List[Signal]:
        """Generate trading signals from market data.
        
        Args:
            data: Market data.
            **kwargs: Additional arguments.
            
        Returns:
            List of generated signals.
        """
        pass


class SignalCombiner:
    """Combines signals from multiple sources into a unified signal."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the signal combiner.
        
        Args:
            config: Configuration dictionary.
        """
        self.config = config or {}
        
        # Configure signal combination method
        self.method = self.config.get(
            "method", 
            get_config("signals.combination.method", "weighted")
        )
        
        # Configure weights for different signal sources
        self.weights = self.config.get(
            "weights", 
            get_config("signals.combination.weights", {
                "ml": 0.5,
                "wave": 0.3,
                "technical": 0.1,
                "sentiment": 0.1,
            })
        )
        
        # Configure signal filters
        self.min_confidence = self.config.get(
            "min_confidence", 
            get_config("signals.filtering.min_confidence", 0.6)
        )
        
        logger.info("Initialized signal combiner using %s method", self.method)
    
    def combine_signals(
        self, 
        signals: List[Signal],
        **kwargs: Any,
    ) -> Optional[Signal]:
        """Combine signals from multiple sources.
        
        Args:
            signals: List of signals to combine.
            **kwargs: Additional arguments.
            
        Returns:
            Combined signal or None if no strong signal is found.
        """
        if not signals:
            return None
        
        # Group signals by type
        signals_by_type: Dict[SignalType, List[Signal]] = {}
        for signal in signals:
            if signal.signal_type not in signals_by_type:
                signals_by_type[signal.signal_type] = []
            signals_by_type[signal.signal_type].append(signal)
        
        # Combine signals for each type
        combined_signals = []
        for signal_type, type_signals in signals_by_type.items():
            if self.method == "weighted":
                combined_signal = self._combine_weighted(signal_type, type_signals)
            elif self.method == "voting":
                combined_signal = self._combine_voting(signal_type, type_signals)
            elif self.method == "priority":
                combined_signal = self._combine_priority(signal_type, type_signals)
            else:
                logger.warning("Unknown signal combination method: %s", self.method)
                combined_signal = self._combine_weighted(signal_type, type_signals)
            
            if combined_signal and combined_signal.strength >= self.min_confidence:
                combined_signals.append(combined_signal)
        
        # Return the strongest signal
        if combined_signals:
            return max(combined_signals, key=lambda s: s.strength)
        
        return None
    
    def _combine_weighted(
        self, 
        signal_type: SignalType, 
        signals: List[Signal],
    ) -> Optional[Signal]:
        """Combine signals using weighted average.
        
        Args:
            signal_type: Type of signals to combine.
            signals: List of signals to combine.
            
        Returns:
            Combined signal or None if no signals.
        """
        if not signals:
            return None
        
        # Get weights for each signal source
        signal_weights = []
        for signal in signals:
            source_key = signal.source.value
            weight = self.weights.get(source_key, 0.1)
            signal_weights.append(weight)
        
        # Normalize weights
        total_weight = sum(signal_weights)
        if total_weight > 0:
            normalized_weights = [w / total_weight for w in signal_weights]
        else:
            normalized_weights = [1.0 / len(signals) for _ in signals]
        
        # Calculate weighted average strength
        weighted_strength = sum(
            s.strength * w for s, w in zip(signals, normalized_weights)
        )
        
        # Create combined signal
        reference_signal = signals[0]
        return Signal(
            signal_type=signal_type,
            strength=weighted_strength,
            source=SignalSource.ENSEMBLE,
            timestamp=reference_signal.timestamp,
            symbol=reference_signal.symbol,
            timeframe=reference_signal.timeframe,
            metadata={
                "component_signals": [s.to_dict() for s in signals],
                "component_weights": normalized_weights,
            },
        )
    
    def _combine_voting(
        self, 
        signal_type: SignalType, 
        signals: List[Signal],
    ) -> Optional[Signal]:
        """Combine signals using voting mechanism.
        
        Args:
            signal_type: Type of signals to combine.
            signals: List of signals to combine.
            
        Returns:
            Combined signal or None if no signals.
        """
        if not signals:
            return None
        
        # Count votes (weighted by signal strength)
        total_votes = 0
        yes_votes = 0
        
        for signal in signals:
            source_key = signal.source.value
            weight = self.weights.get(source_key, 0.1)
            vote_strength = signal.strength * weight
            
            total_votes += weight
            yes_votes += vote_strength
        
        # Calculate voting result
        if total_votes > 0:
            vote_ratio = yes_votes / total_votes
        else:
            vote_ratio = 0
        
        # Create combined signal
        reference_signal = signals[0]
        return Signal(
            signal_type=signal_type,
            strength=vote_ratio,
            source=SignalSource.ENSEMBLE,
            timestamp=reference_signal.timestamp,
            symbol=reference_signal.symbol,
            timeframe=reference_signal.timeframe,
            metadata={
                "component_signals": [s.to_dict() for s in signals],
                "yes_votes": yes_votes,
                "total_votes": total_votes,
            },
        )
    
    def _combine_priority(
        self, 
        signal_type: SignalType, 
        signals: List[Signal],
    ) -> Optional[Signal]:
        """Combine signals using priority order.
        
        Args:
            signal_type: Type of signals to combine.
            signals: List of signals to combine.
            
        Returns:
            Combined signal or None if no signals.
        """
        if not signals:
            return None
        
        # Define priority order based on weights
        priority_order = sorted(
            self.weights.keys(),
            key=lambda k: self.weights.get(k, 0),
            reverse=True,
        )
        
        # Choose signal based on priority
        best_signal = None
        best_priority = float("inf")
        
        for signal in signals:
            source_key = signal.source.value
            if source_key in priority_order:
                priority = priority_order.index(source_key)
                if priority < best_priority:
                    best_signal = signal
                    best_priority = priority
        
        if best_signal:
            # Create combined signal based on the highest priority
            return Signal(
                signal_type=signal_type,
                strength=best_signal.strength,
                source=SignalSource.ENSEMBLE,
                timestamp=best_signal.timestamp,
                symbol=best_signal.symbol,
                timeframe=best_signal.timeframe,
                metadata={
                    "component_signals": [s.to_dict() for s in signals],
                    "selected_source": best_signal.source.value,
                    "priority_order": priority_order,
                },
            )
        
        return None


class IntegratedStrategy:
    """Integrated trading strategy combining multiple signal sources."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the integrated strategy.
        
        Args:
            config: Configuration dictionary.
        """
        self.config = config or {}
        self.name = self.config.get("name", "IntegratedStrategy")
        
        # Initialize signal generators
        self.signal_generators: List[SignalGenerator] = []
        
        # Initialize signal combiner
        combiner_config = self.config.get("signal_combiner", {})
        self.signal_combiner = SignalCombiner(combiner_config)
        
        logger.info("Initialized integrated strategy: %s", self.name)
    
    def add_signal_generator(self, generator: SignalGenerator) -> None:
        """Add a signal generator to the strategy.
        
        Args:
            generator: Signal generator to add.
        """
        self.signal_generators.append(generator)
        logger.info("Added signal generator: %s", generator.name)
    
    def generate_signals(
        self, 
        data: pd.DataFrame,
        **kwargs: Any,
    ) -> Optional[Signal]:
        """Generate trading signals from market data.
        
        Args:
            data: Market data.
            **kwargs: Additional arguments.
            
        Returns:
            Combined trading signal or None.
        """
        all_signals: List[Signal] = []
        
        # Generate signals from each generator
        for generator in self.signal_generators:
            try:
                signals = generator.generate_signals(data, **kwargs)
                if signals:
                    all_signals.extend(signals)
            except Exception as e:
                logger.exception("Error generating signals from %s: %s", generator.name, e)
        
        # Combine signals
        if all_signals:
            return self.signal_combiner.combine_signals(all_signals, **kwargs)
        
        return None


# Placeholder functions for a simple strategy
def simple_strategy(data: pd.DataFrame, current_idx: int, params: Dict[str, Any]) -> Dict[str, Any]:
    """Simple trading strategy for backtesting.
    
    Args:
        data: Market data.
        current_idx: Index of the current bar.
        params: Strategy parameters.
        
    Returns:
        Dictionary with strategy signals.
    """
    if current_idx < 20:
        return {}
    
    # Get current and previous data
    current = data.iloc[current_idx]
    
    # Simple moving average crossover
    if "sma_10" not in data.columns or "sma_20" not in data.columns:
        return {}
    
    sma_short = current["sma_10"]
    sma_long = current["sma_20"]
    
    previous_idx = current_idx - 1
    previous = data.iloc[previous_idx]
    prev_sma_short = previous["sma_10"]
    prev_sma_long = previous["sma_20"]
    
    signals = {}
    
    # Entry signal: short-term MA crosses above long-term MA
    if prev_sma_short <= prev_sma_long and sma_short > sma_long:
        signals["entry"] = True
        signals["direction"] = "buy"
        signals["risk_pct"] = params.get("risk_pct", 0.02)
    
    # Exit signal: short-term MA crosses below long-term MA
    elif prev_sma_short >= prev_sma_long and sma_short < sma_long:
        signals["exit"] = True
    
    return signals