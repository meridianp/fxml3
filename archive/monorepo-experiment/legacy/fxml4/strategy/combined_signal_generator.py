"""Combined signal generator integrating ML, sentiment, and Elliott Wave analysis.

This module provides a signal generator that combines signals from machine learning,
sentiment analysis, and Elliott Wave pattern detection to create a unified trading approach.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from fxml4.config import get_config
from fxml4.strategy.integrated_strategy import Signal, SignalGenerator, SignalSource, SignalType
from fxml4.strategy.ml_signal_generator import MLSignalGenerator
from fxml4.strategy.sentiment_signal_generator import SentimentSignalGenerator
from fxml4.strategy.enhanced_wave_signal_generator import EnhancedWaveSignalGenerator

logger = logging.getLogger(__name__)


class CombinedSignalGenerator(SignalGenerator):
    """Signal generator combining ML, sentiment, and Elliott Wave analysis."""
    
    def __init__(
        self,
        ml_signal_generator: MLSignalGenerator,
        sentiment_signal_generator: SentimentSignalGenerator,
        wave_signal_generator: EnhancedWaveSignalGenerator,
        config: Optional[Dict[str, Any]] = None
    ):
        """Initialize the combined signal generator.
        
        Args:
            ml_signal_generator: Machine learning signal generator.
            sentiment_signal_generator: Sentiment signal generator.
            wave_signal_generator: Enhanced Elliott Wave signal generator.
            config: Configuration dictionary.
        """
        super().__init__(config)
        self.ml_signal_generator = ml_signal_generator
        self.sentiment_signal_generator = sentiment_signal_generator
        self.wave_signal_generator = wave_signal_generator
        
        # Configure signal combination method
        self.method = self.config.get("method", "weighted")
        
        # Configure weights for different signal sources
        self.weights = self.config.get("weights", {
            SignalSource.ML.value: 0.4,
            SignalSource.SENTIMENT.value: 0.2,
            SignalSource.WAVE.value: 0.4,
        })
        
        # Configure signal filtering
        self.min_confidence = self.config.get("min_confidence", 0.6)
        self.min_agreement = self.config.get("min_agreement", 2)  # Minimum number of signals that must agree
        
        # Configure consensus requirements
        self.require_consensus = self.config.get("require_consensus", True)
        
        # Configure adaptive weights based on market regimes
        self.use_adaptive_weights = self.config.get("use_adaptive_weights", False)
        self.market_regime_weights = self.config.get("market_regime_weights", {
            "trending": {
                SignalSource.ML.value: 0.4,
                SignalSource.SENTIMENT.value: 0.2,
                SignalSource.WAVE.value: 0.4,
            },
            "ranging": {
                SignalSource.ML.value: 0.3,
                SignalSource.SENTIMENT.value: 0.2,
                SignalSource.WAVE.value: 0.5,
            },
            "volatile": {
                SignalSource.ML.value: 0.5,
                SignalSource.SENTIMENT.value: 0.3,
                SignalSource.WAVE.value: 0.2,
            },
        })
        
        # Configure stop loss and take profit settings
        self.risk_reward_ratio = self.config.get("risk_reward_ratio", 2.0)
        self.stop_loss_pct = self.config.get("stop_loss_pct", 1.0)
        self.use_wave_stops = self.config.get("use_wave_stops", True)
        
        # Keep track of active signals for each source
        self.active_signals = {
            SignalSource.ML: None,
            SignalSource.SENTIMENT: None,
            SignalSource.WAVE: None,
        }
        
        logger.info("Initialized combined signal generator using %s method", self.method)
        
    def _detect_market_regime(self, data: pd.DataFrame) -> str:
        """Detect current market regime.
        
        Args:
            data: Market data.
            
        Returns:
            Market regime ("trending", "ranging", or "volatile").
        """
        # Use a simple heuristic based on ADX and volatility
        if 'adx' not in data.columns:
            # Calculate ADX if not present
            # This is a simplified calculation, not full ADX
            price_changes = data['close'].pct_change().abs()
            volatility = price_changes.rolling(14).std()
            trend_strength = price_changes.rolling(14).mean() / volatility
            
            if trend_strength.iloc[-1] > 0.5:
                return "trending"
            elif volatility.iloc[-1] > volatility.quantile(0.8):
                return "volatile"
            else:
                return "ranging"
        else:
            # Use existing ADX indicator
            adx = data['adx'].iloc[-1]
            volatility = data['close'].pct_change().rolling(14).std().iloc[-1]
            
            if adx > 25:
                return "trending"
            elif volatility > data['close'].pct_change().rolling(14).std().quantile(0.8).iloc[-1]:
                return "volatile"
            else:
                return "ranging"
            
    def _get_current_weights(self, data: pd.DataFrame) -> Dict[str, float]:
        """Get weights adjusted for current market regime.
        
        Args:
            data: Market data.
            
        Returns:
            Dictionary of signal weights.
        """
        if not self.use_adaptive_weights:
            return self.weights
            
        # Detect market regime
        regime = self._detect_market_regime(data)
        
        # Use regime-specific weights
        return self.market_regime_weights.get(regime, self.weights)
    
    def _combine_weighted(
        self, 
        signal_type: SignalType,
        ml_signals: List[Signal], 
        sentiment_signals: List[Signal],
        wave_signals: List[Signal],
        weights: Dict[str, float]
    ) -> Optional[Signal]:
        """Combine signals using weighted average.
        
        Args:
            signal_type: Signal type.
            ml_signals: Machine learning signals.
            sentiment_signals: Sentiment signals.
            wave_signals: Elliott Wave signals.
            weights: Signal weights.
            
        Returns:
            Combined signal or None if no strong signal is found.
        """
        # Filter signals by type
        ml_signal = next((s for s in ml_signals if s.signal_type == signal_type), None)
        sentiment_signal = next((s for s in sentiment_signals if s.signal_type == signal_type), None)
        wave_signal = next((s for s in wave_signals if s.signal_type == signal_type), None)
        
        # Count signals of this type
        signal_count = sum(1 for s in [ml_signal, sentiment_signal, wave_signal] if s is not None)
        
        # Check if we have enough signals
        if signal_count < self.min_agreement and self.require_consensus:
            return None
            
        # Calculate combined strength
        total_weight = 0
        weighted_strength = 0
        
        if ml_signal:
            ml_weight = weights.get(SignalSource.ML.value, 0.4)
            weighted_strength += ml_signal.strength * ml_weight
            total_weight += ml_weight
            
        if sentiment_signal:
            sentiment_weight = weights.get(SignalSource.SENTIMENT.value, 0.2)
            weighted_strength += sentiment_signal.strength * sentiment_weight
            total_weight += sentiment_weight
            
        if wave_signal:
            wave_weight = weights.get(SignalSource.WAVE.value, 0.4)
            weighted_strength += wave_signal.strength * wave_weight
            total_weight += wave_weight
            
        if total_weight == 0:
            return None
            
        strength = weighted_strength / total_weight
        
        # Check if strength meets minimum threshold
        if strength < self.min_confidence:
            return None
            
        # Determine timestamp (use the most recent)
        timestamps = []
        if ml_signal:
            timestamps.append(ml_signal.timestamp)
        if sentiment_signal:
            timestamps.append(sentiment_signal.timestamp)
        if wave_signal:
            timestamps.append(wave_signal.timestamp)
        
        timestamp = max(timestamps) if timestamps else pd.Timestamp.now()
        
        # Determine symbol and timeframe
        symbol = None
        timeframe = None
        for signal in [ml_signal, sentiment_signal, wave_signal]:
            if signal:
                symbol = signal.symbol
                timeframe = signal.timeframe
                break
                
        # Create combined metadata with info from all signals
        metadata = {
            "ml_signal": ml_signal.to_dict() if ml_signal else None,
            "sentiment_signal": sentiment_signal.to_dict() if sentiment_signal else None,
            "wave_signal": wave_signal.to_dict() if wave_signal else None,
            "signal_count": signal_count,
        }
        
        # Add risk management if we have a wave signal
        if wave_signal and "stop_loss" in wave_signal.metadata:
            metadata["stop_loss"] = wave_signal.metadata["stop_loss"]
            metadata["take_profit"] = wave_signal.metadata.get("take_profit")
        
        # Create combined signal
        combined_signal = Signal(
            signal_type=signal_type,
            strength=strength,
            source=SignalSource.ENSEMBLE,
            timestamp=timestamp,
            symbol=symbol,
            timeframe=timeframe,
            metadata=metadata,
        )
        
        return combined_signal
    
    def _calculate_risk_levels(
        self, 
        signal: Signal, 
        data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Calculate stop loss and take profit levels.
        
        Args:
            signal: Trading signal.
            data: Market data.
            
        Returns:
            Dictionary with risk levels.
        """
        current_price = data['close'].iloc[-1]
        
        # Check if signal has predefined risk levels from the wave generator
        if "stop_loss" in signal.metadata:
            stop_loss = signal.metadata["stop_loss"]
            
            # If take profit levels are also provided, use them
            if "take_profit" in signal.metadata:
                return {
                    "stop_loss": stop_loss,
                    "take_profit": signal.metadata["take_profit"]
                }
            
            # Otherwise calculate take profit based on risk-reward ratio
            risk = abs(current_price - stop_loss)
            take_profit_distance = risk * self.risk_reward_ratio
            
            if signal.signal_type == SignalType.ENTRY_LONG:
                take_profit = current_price + take_profit_distance
            else:  # Short
                take_profit = current_price - take_profit_distance
                
            return {
                "stop_loss": stop_loss,
                "take_profit": {
                    "target": take_profit
                }
            }
        
        # No predefined levels, calculate based on percentage
        if signal.signal_type == SignalType.ENTRY_LONG:
            stop_loss = current_price * (1 - self.stop_loss_pct / 100)
            take_profit = current_price * (1 + (self.stop_loss_pct * self.risk_reward_ratio) / 100)
        else:  # Short
            stop_loss = current_price * (1 + self.stop_loss_pct / 100)
            take_profit = current_price * (1 - (self.stop_loss_pct * self.risk_reward_ratio) / 100)
            
        return {
            "stop_loss": stop_loss,
            "take_profit": {
                "target": take_profit
            }
        }
    
    def generate_signals(
        self,
        data: pd.DataFrame,
        **kwargs: Any,
    ) -> List[Signal]:
        """Generate trading signals by combining ML, sentiment, and Elliott Wave signals.
        
        Args:
            data: Market data.
            **kwargs: Additional arguments.
            
        Returns:
            List of generated signals.
        """
        # Get news data if provided
        news_data = kwargs.get("news_data")
        
        # Generate signals from each source
        ml_signals = self.ml_signal_generator.generate_signals(data, **kwargs)
        sentiment_signals = self.sentiment_signal_generator.generate_signals(data, news_data=news_data, **kwargs)
        wave_signals = self.wave_signal_generator.generate_signals(data, news_data=news_data, **kwargs)
        
        # Update active signals
        for signal in ml_signals:
            self.active_signals[SignalSource.ML] = signal
        for signal in sentiment_signals:
            self.active_signals[SignalSource.SENTIMENT] = signal
        for signal in wave_signals:
            self.active_signals[SignalSource.WAVE] = signal
            
        # Get weights adjusted for current market regime
        weights = self._get_current_weights(data)
        
        # Combine signals by type
        combined_signals = []
        
        # Process entry long signals
        entry_long = self._combine_weighted(
            SignalType.ENTRY_LONG, 
            ml_signals, 
            sentiment_signals,
            wave_signals,
            weights
        )
        if entry_long:
            # Add risk management levels
            risk_levels = self._calculate_risk_levels(entry_long, data)
            entry_long.metadata.update(risk_levels)
            combined_signals.append(entry_long)
        
        # Process entry short signals
        entry_short = self._combine_weighted(
            SignalType.ENTRY_SHORT, 
            ml_signals, 
            sentiment_signals,
            wave_signals,
            weights
        )
        if entry_short:
            # Add risk management levels
            risk_levels = self._calculate_risk_levels(entry_short, data)
            entry_short.metadata.update(risk_levels)
            combined_signals.append(entry_short)
        
        # Process exit long signals
        exit_long = self._combine_weighted(
            SignalType.EXIT_LONG, 
            ml_signals, 
            sentiment_signals,
            wave_signals,
            weights
        )
        if exit_long:
            combined_signals.append(exit_long)
        
        # Process exit short signals
        exit_short = self._combine_weighted(
            SignalType.EXIT_SHORT, 
            ml_signals, 
            sentiment_signals,
            wave_signals,
            weights
        )
        if exit_short:
            combined_signals.append(exit_short)
        
        return combined_signals