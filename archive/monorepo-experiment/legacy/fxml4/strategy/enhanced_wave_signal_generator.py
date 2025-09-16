"""Enhanced Elliott Wave signal generator with sentiment integration.

This module provides a signal generator that uses sentiment-enhanced Elliott Wave
patterns to generate trading signals.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from fxml4.config import get_config
from fxml4.strategy.integrated_strategy import Signal, SignalGenerator, SignalSource, SignalType
from fxml4.wave_analysis.elliott_wave import (
    ElliottWavePattern, ElliottWaveCount, WavePosition, WaveDegree, WaveType
)
from fxml4.wave_analysis.sentiment_wave_validator import SentimentWaveValidator

logger = logging.getLogger(__name__)


class EnhancedWaveSignalGenerator(SignalGenerator):
    """Signal generator using sentiment-enhanced Elliott Wave patterns."""
    
    def __init__(
        self,
        wave_validator: SentimentWaveValidator,
        config: Optional[Dict[str, Any]] = None
    ):
        """Initialize the enhanced Elliott Wave signal generator.
        
        Args:
            wave_validator: Sentiment-enhanced Elliott Wave validator.
            config: Configuration dictionary.
        """
        super().__init__(config)
        self.wave_validator = wave_validator
        
        # Signal configuration
        self.threshold = self.config.get("threshold", 0.65)
        self.position_weights = self.config.get("position_weights", {
            "impulse_end_5": 0.9,    # End of impulse wave 5
            "correction_end_c": 0.8,  # End of correction wave C
            "impulse_end_3": 0.7,    # End of impulse wave 3
            "correction_end_b": 0.5,  # End of correction wave B
            "diagonal_end": 0.7,     # End of diagonal pattern
            "triangle_end": 0.6,     # End of triangle pattern
            "correction_end_a": 0.4,  # End of correction wave A
            "impulse_end_1": 0.3,    # End of impulse wave 1
        })
        
        # Minimum confidence for signal generation
        self.min_confidence = self.config.get("min_confidence", 0.6)
        
        # Maximum stop loss as percentage of price
        self.max_stop_loss_pct = self.config.get("max_stop_loss_pct", 2.0)
        
        # Configure stop loss sizing based on pattern confidence
        self.stop_loss_confidence_scaling = self.config.get("stop_loss_confidence_scaling", True)
        
        # Configure take profit level multipliers
        self.take_profit_levels = self.config.get("take_profit_levels", {
            "conservative": 1.5,  # Risk-reward ratio for conservative target
            "moderate": 2.0,      # Risk-reward ratio for moderate target
            "aggressive": 3.0     # Risk-reward ratio for aggressive target
        })
        
        # Configure whether to use news sentiment
        self.use_news_sentiment = self.config.get("use_news_sentiment", True)
        
        logger.info("Initialized Enhanced Elliott Wave Signal Generator")
        
    def _get_position_type(self, wave: ElliottWavePattern) -> str:
        """Get position type string based on wave pattern.
        
        Args:
            wave: Elliott Wave pattern.
            
        Returns:
            Position type string.
        """
        if not wave:
            return "unknown"
        
        wave_type = wave.wave_type
        position = wave.position
        
        # Determine position type based on wave type and position
        if wave_type == WaveType.IMPULSE:
            if position == WavePosition.END:
                if wave.subwaves and len(wave.subwaves) >= 5:
                    return "impulse_end_5"
                elif wave.subwaves and len(wave.subwaves) >= 3:
                    return "impulse_end_3"
                elif wave.subwaves and len(wave.subwaves) >= 1:
                    return "impulse_end_1"
            return "impulse_middle"
        
        elif wave_type == WaveType.CORRECTION:
            if position == WavePosition.END:
                if wave.subwaves and len(wave.subwaves) >= 3:
                    return "correction_end_c"
                elif wave.subwaves and len(wave.subwaves) >= 2:
                    return "correction_end_b"
                elif wave.subwaves and len(wave.subwaves) >= 1:
                    return "correction_end_a"
            return "correction_middle"
        
        elif wave_type == WaveType.DIAGONAL:
            if position == WavePosition.END:
                return "diagonal_end"
            return "diagonal_middle"
        
        elif wave_type == WaveType.TRIANGLE:
            if position == WavePosition.END:
                return "triangle_end"
            return "triangle_middle"
            
        return "unknown"
    
    def _calculate_stop_loss_level(
        self, 
        pattern: ElliottWavePattern,
        price_data: pd.DataFrame,
        combined_confidence: float,
        signal_type: SignalType
    ) -> float:
        """Calculate stop loss level based on pattern and confidence.
        
        Args:
            pattern: Elliott Wave pattern.
            price_data: Price data.
            combined_confidence: Combined confidence score.
            signal_type: Type of trading signal.
            
        Returns:
            Stop loss price level.
        """
        # Get current price
        current_price = price_data['close'].iloc[-1]
        
        # Base stop distance as percentage (smaller for higher confidence)
        if self.stop_loss_confidence_scaling:
            # Adjust stop distance based on confidence (higher confidence = tighter stop)
            base_stop_pct = self.max_stop_loss_pct * (1 - 0.5 * combined_confidence)
        else:
            base_stop_pct = self.max_stop_loss_pct
        
        # For long entries, stop loss is below current price
        if signal_type == SignalType.ENTRY_LONG:
            # Look for recent low as potential stop reference
            if pattern.subwaves and len(pattern.subwaves) > 0:
                # Try to find swing low from wave structure
                last_correction = None
                for subwave in pattern.subwaves:
                    if subwave.wave_type in [WaveType.CORRECTION, WaveType.ZIGZAG]:
                        last_correction = subwave
                
                if last_correction and 0 <= last_correction.end_idx < len(price_data):
                    # Use correction end as stop reference with buffer
                    stop_price = price_data['low'].iloc[last_correction.end_idx] * 0.995
                    
                    # Ensure stop doesn't exceed maximum allowed distance
                    max_stop = current_price * (1 - base_stop_pct / 100)
                    return max(stop_price, max_stop)
            
            # If no structure available, use percentage-based stop
            return current_price * (1 - base_stop_pct / 100)
        
        # For short entries, stop loss is above current price
        elif signal_type == SignalType.ENTRY_SHORT:
            # Look for recent high as potential stop reference
            if pattern.subwaves and len(pattern.subwaves) > 0:
                # Try to find swing high from wave structure
                last_impulse = None
                for subwave in pattern.subwaves:
                    if subwave.wave_type == WaveType.IMPULSE:
                        last_impulse = subwave
                
                if last_impulse and 0 <= last_impulse.end_idx < len(price_data):
                    # Use impulse end as stop reference with buffer
                    stop_price = price_data['high'].iloc[last_impulse.end_idx] * 1.005
                    
                    # Ensure stop doesn't exceed maximum allowed distance
                    max_stop = current_price * (1 + base_stop_pct / 100)
                    return min(stop_price, max_stop)
            
            # If no structure available, use percentage-based stop
            return current_price * (1 + base_stop_pct / 100)
        
        # Default case
        return current_price * (1 - base_stop_pct / 100) if signal_type == SignalType.ENTRY_LONG else current_price * (1 + base_stop_pct / 100)
    
    def _calculate_take_profit_levels(
        self,
        entry_price: float,
        stop_loss: float,
        signal_type: SignalType
    ) -> Dict[str, float]:
        """Calculate take profit levels based on risk-reward ratios.
        
        Args:
            entry_price: Entry price.
            stop_loss: Stop loss price.
            signal_type: Type of trading signal.
            
        Returns:
            Dictionary of take profit levels.
        """
        # Calculate risk (absolute difference between entry and stop)
        risk = abs(entry_price - stop_loss)
        
        take_profit_prices = {}
        
        for level, rr_ratio in self.take_profit_levels.items():
            # Calculate reward as risk * ratio
            reward = risk * rr_ratio
            
            # For long entries, take profit is above entry
            if signal_type == SignalType.ENTRY_LONG:
                take_profit_prices[level] = entry_price + reward
            # For short entries, take profit is below entry
            else:  # SignalType.ENTRY_SHORT
                take_profit_prices[level] = entry_price - reward
                
        return take_profit_prices
    
    def generate_signals(
        self,
        data: pd.DataFrame,
        news_data: Optional[pd.DataFrame] = None,
        **kwargs: Any
    ) -> List[Signal]:
        """Generate trading signals using sentiment-enhanced Elliott Wave patterns.
        
        Args:
            data: Market data.
            news_data: Optional news data for sentiment analysis.
            **kwargs: Additional arguments.
            
        Returns:
            List of generated signals.
        """
        signals = []
        
        # Extract metadata
        symbol = kwargs.get("symbol", data.get("symbol", ["unknown"])[0] 
                             if "symbol" in data.columns else "unknown")
        timeframe = kwargs.get("timeframe", data.get("timeframe", ["unknown"])[0] 
                               if "timeframe" in data.columns else "unknown")
        
        # Get the latest timestamp
        latest_timestamp = data.index[-1] if isinstance(data.index, pd.DatetimeIndex) else pd.Timestamp.now()
        
        try:
            # Check if we should use news data
            use_news = news_data is not None and self.use_news_sentiment
            
            # Use SentimentWaveValidator to analyze price data with sentiment
            analysis_results = self.wave_validator.analyze_with_sentiment(
                price_data=data,
                news_data=news_data if use_news else None
            )
            
            # Extract results
            sentiment_score = analysis_results.get("sentiment_score", 0)
            validated_patterns = analysis_results.get("validation", [])
            
            if not validated_patterns:
                logger.debug("No validated patterns found")
                return signals
            
            # Get current price
            current_price = data['close'].iloc[-1]
            
            # Process each validated pattern
            for pattern_result in validated_patterns:
                # Skip invalid patterns
                if not pattern_result.get("is_valid", False):
                    continue
                
                # Get pattern details and confidence
                pattern_dict = pattern_result.get("pattern", {})
                confidence = pattern_result.get("confidence", 0)
                details = pattern_result.get("details", {})
                
                # Skip low confidence patterns
                if confidence < self.min_confidence:
                    continue
                
                # Convert pattern dict back to ElliottWavePattern
                pattern = ElliottWavePattern.from_dict(pattern_dict)
                
                # Get position type and strength
                position_type = self._get_position_type(pattern)
                position_strength = self.position_weights.get(position_type, 0.5)
                
                # Calculate signal strength
                signal_strength = confidence * position_strength
                
                # Determine signal type based on pattern and position
                if pattern.wave_type == WaveType.IMPULSE:
                    if position_type == "impulse_end_5":
                        # End of impulse wave 5 - expect correction
                        signal_type = SignalType.ENTRY_SHORT
                        # Also exit any existing long positions
                        exit_signal_type = SignalType.EXIT_LONG
                    elif position_type == "impulse_end_3":
                        # End of impulse wave 3 - expect wave 4 correction
                        signal_type = SignalType.ENTRY_SHORT
                    else:
                        # Default to no signal
                        continue
                
                elif pattern.wave_type == WaveType.CORRECTION:
                    if position_type == "correction_end_c":
                        # End of correction wave C - expect new impulse
                        signal_type = SignalType.ENTRY_LONG
                        # Also exit any existing short positions
                        exit_signal_type = SignalType.EXIT_SHORT
                    elif position_type == "correction_end_a":
                        # End of correction wave A - expect wave B bounce
                        signal_type = SignalType.ENTRY_LONG
                    else:
                        # Default to no signal
                        continue
                
                elif pattern.wave_type == WaveType.DIAGONAL:
                    if position_type == "diagonal_end":
                        # End of diagonal - typically a reversal pattern
                        # If in uptrend, expect downtrend
                        if sentiment_score > 0:
                            signal_type = SignalType.ENTRY_SHORT
                        # If in downtrend, expect uptrend
                        else:
                            signal_type = SignalType.ENTRY_LONG
                    else:
                        # Default to no signal
                        continue
                
                elif pattern.wave_type == WaveType.TRIANGLE:
                    if position_type == "triangle_end":
                        # End of triangle - typically followed by strong move
                        # Direction depends on sentiment and preceding trend
                        if sentiment_score > 0:
                            signal_type = SignalType.ENTRY_LONG
                        else:
                            signal_type = SignalType.ENTRY_SHORT
                    else:
                        # Default to no signal
                        continue
                
                else:
                    # Unknown pattern type, skip
                    continue
                
                # Calculate stop loss level
                stop_loss = self._calculate_stop_loss_level(
                    pattern=pattern,
                    price_data=data,
                    combined_confidence=confidence,
                    signal_type=signal_type
                )
                
                # Calculate take profit levels
                take_profit_levels = self._calculate_take_profit_levels(
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    signal_type=signal_type
                )
                
                # Create entry signal
                entry_signal = Signal(
                    signal_type=signal_type,
                    strength=signal_strength,
                    source=SignalSource.WAVE,
                    timestamp=latest_timestamp,
                    symbol=symbol,
                    timeframe=timeframe,
                    metadata={
                        "wave_pattern": pattern.wave_type.value,
                        "wave_position": position_type,
                        "pattern_confidence": confidence,
                        "sentiment_score": sentiment_score,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit_levels,
                        "wave_details": pattern_dict,
                        "validation_details": details,
                    },
                )
                signals.append(entry_signal)
                
                # Add exit signal if applicable
                if position_type in ["impulse_end_5", "correction_end_c"] and signal_strength >= self.threshold:
                    exit_signal = Signal(
                        signal_type=exit_signal_type,
                        strength=signal_strength,
                        source=SignalSource.WAVE,
                        timestamp=latest_timestamp,
                        symbol=symbol,
                        timeframe=timeframe,
                        metadata={
                            "wave_pattern": pattern.wave_type.value,
                            "wave_position": position_type,
                            "pattern_confidence": confidence,
                            "sentiment_score": sentiment_score,
                            "wave_details": pattern_dict,
                            "validation_details": details,
                        },
                    )
                    signals.append(exit_signal)
                
        except Exception as e:
            logger.exception(f"Error generating enhanced wave signals: {e}")
        
        return signals