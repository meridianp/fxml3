"""Multi-timeframe position sizing for comprehensive risk assessment.

This module provides position sizing that considers multiple timeframes
to better assess risk and optimize position sizes.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from fxml4.backtesting.event import SignalEvent
from fxml4.backtesting.risk_management import PositionSizer
from fxml4.config import get_config

logger = logging.getLogger(__name__)


class TimeframeData:
    """Container for timeframe-specific market data and metrics."""
    
    def __init__(self, timeframe: str, lookback_periods: int = 50):
        """Initialize timeframe data container.
        
        Args:
            timeframe: Timeframe identifier (e.g., '1m', '5m', '1h', '4h', '1d').
            lookback_periods: Number of periods to store.
        """
        self.timeframe = timeframe
        self.lookback_periods = lookback_periods
        self.data = pd.DataFrame()
        self.volatility = 0.0
        self.trend_strength = 0.0
        self.support_resistance = {}
        self.volume_profile = {}
    
    def update(self, new_data: pd.DataFrame) -> None:
        """Update timeframe data with new market data.
        
        Args:
            new_data: New market data to append.
        """
        self.data = pd.concat([self.data, new_data]).tail(self.lookback_periods)
        self._calculate_metrics()
    
    def _calculate_metrics(self) -> None:
        """Calculate timeframe-specific metrics."""
        if len(self.data) < 20:
            return
        
        # Calculate volatility
        returns = self.data['close'].pct_change().dropna()
        self.volatility = returns.std() * np.sqrt(self._get_annualization_factor())
        
        # Calculate trend strength (ADX-like)
        high = self.data['high']
        low = self.data['low']
        close = self.data['close']
        
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        
        # Directional movement
        up_move = high - high.shift()
        down_move = low.shift() - low
        
        pos_dm = up_move.where((up_move > down_move) & (up_move > 0), 0)
        neg_dm = down_move.where((down_move > up_move) & (down_move > 0), 0)
        
        pos_di = 100 * (pos_dm.rolling(14).mean() / atr)
        neg_di = 100 * (neg_dm.rolling(14).mean() / atr)
        
        dx = 100 * abs(pos_di - neg_di) / (pos_di + neg_di)
        adx = dx.rolling(14).mean()
        
        self.trend_strength = adx.iloc[-1] if not adx.empty else 0
        
        # Identify support/resistance levels
        self._identify_support_resistance()
        
        # Calculate volume profile
        self._calculate_volume_profile()
    
    def _get_annualization_factor(self) -> int:
        """Get annualization factor based on timeframe."""
        factors = {
            '1m': 525600,  # Minutes in a year
            '5m': 105120,
            '15m': 35040,
            '30m': 17520,
            '1h': 8760,
            '4h': 2190,
            '1d': 365,
            '1w': 52,
        }
        return factors.get(self.timeframe, 365)
    
    def _identify_support_resistance(self) -> None:
        """Identify key support and resistance levels."""
        if len(self.data) < 20:
            return
        
        highs = self.data['high']
        lows = self.data['low']
        
        # Simple peak/trough detection
        resistance_levels = []
        support_levels = []
        
        for i in range(2, len(highs) - 2):
            # Resistance (local highs)
            if (highs.iloc[i] > highs.iloc[i-1] and 
                highs.iloc[i] > highs.iloc[i-2] and
                highs.iloc[i] > highs.iloc[i+1] and 
                highs.iloc[i] > highs.iloc[i+2]):
                resistance_levels.append(highs.iloc[i])
            
            # Support (local lows)
            if (lows.iloc[i] < lows.iloc[i-1] and 
                lows.iloc[i] < lows.iloc[i-2] and
                lows.iloc[i] < lows.iloc[i+1] and 
                lows.iloc[i] < lows.iloc[i+2]):
                support_levels.append(lows.iloc[i])
        
        self.support_resistance = {
            'resistance': sorted(resistance_levels)[-3:] if resistance_levels else [],
            'support': sorted(support_levels)[:3] if support_levels else [],
        }
    
    def _calculate_volume_profile(self) -> None:
        """Calculate volume profile for price levels."""
        if len(self.data) < 10:
            return
        
        # Create price bins
        price_range = self.data['high'].max() - self.data['low'].min()
        num_bins = 20
        bin_size = price_range / num_bins
        
        volume_by_price = {}
        
        for _, row in self.data.iterrows():
            # Distribute volume across the bar's range
            low = row['low']
            high = row['high']
            volume = row['volume']
            
            # Find which bins this bar spans
            low_bin = int((low - self.data['low'].min()) / bin_size)
            high_bin = int((high - self.data['low'].min()) / bin_size)
            
            # Distribute volume equally across bins
            bins_spanned = high_bin - low_bin + 1
            volume_per_bin = volume / bins_spanned
            
            for bin_idx in range(low_bin, high_bin + 1):
                if bin_idx not in volume_by_price:
                    volume_by_price[bin_idx] = 0
                volume_by_price[bin_idx] += volume_per_bin
        
        self.volume_profile = volume_by_price


class MultiTimeframePositionSizer(PositionSizer):
    """Position sizer that considers multiple timeframes for comprehensive risk assessment."""
    
    def __init__(
        self,
        base_position_pct: float = 0.02,
        timeframes: List[str] = None,
        timeframe_weights: Dict[str, float] = None,
        use_trend_alignment: bool = True,
        use_volatility_scaling: bool = True,
        use_support_resistance: bool = True,
    ):
        """Initialize multi-timeframe position sizer.
        
        Args:
            base_position_pct: Base position size as percentage of equity.
            timeframes: List of timeframes to consider.
            timeframe_weights: Weights for each timeframe.
            use_trend_alignment: Scale based on trend alignment.
            use_volatility_scaling: Scale based on volatility across timeframes.
            use_support_resistance: Consider support/resistance levels.
        """
        self.base_position_pct = base_position_pct
        self.timeframes = timeframes or ['4h', '1d', '1w']
        
        # Default weights
        if timeframe_weights is None:
            self.timeframe_weights = {
                '1m': 0.05,
                '5m': 0.10,
                '15m': 0.15,
                '1h': 0.20,
                '4h': 0.30,
                '1d': 0.15,
                '1w': 0.05,
            }
        else:
            self.timeframe_weights = timeframe_weights
        
        self.use_trend_alignment = use_trend_alignment
        self.use_volatility_scaling = use_volatility_scaling
        self.use_support_resistance = use_support_resistance
        
        # Initialize timeframe data containers
        self.timeframe_data = {
            tf: TimeframeData(tf) for tf in self.timeframes
        }
    
    def update_timeframe_data(self, timeframe: str, data: pd.DataFrame) -> None:
        """Update data for a specific timeframe.
        
        Args:
            timeframe: Timeframe identifier.
            data: Market data for the timeframe.
        """
        if timeframe in self.timeframe_data:
            self.timeframe_data[timeframe].update(data)
    
    def calculate_position_size(
        self,
        signal: SignalEvent,
        portfolio: Any,
        current_price: float,
    ) -> float:
        """Calculate position size considering multiple timeframes.
        
        Args:
            signal: Signal event.
            portfolio: Portfolio instance.
            current_price: Current price.
            
        Returns:
            Position size (quantity).
        """
        # Start with base position size
        position_pct = self.base_position_pct
        
        # Collect adjustments from each timeframe
        adjustments = {
            'trend_alignment': 1.0,
            'volatility': 1.0,
            'support_resistance': 1.0,
        }
        
        # Analyze each timeframe
        timeframe_scores = {}
        
        for timeframe in self.timeframes:
            if timeframe not in self.timeframe_data:
                continue
            
            tf_data = self.timeframe_data[timeframe]
            if len(tf_data.data) < 20:
                continue
            
            tf_score = self._analyze_timeframe(tf_data, signal, current_price)
            timeframe_scores[timeframe] = tf_score
        
        # Calculate weighted adjustments
        if timeframe_scores:
            # Trend alignment adjustment
            if self.use_trend_alignment:
                trend_scores = [
                    score['trend_alignment'] * self.timeframe_weights.get(tf, 0.1)
                    for tf, score in timeframe_scores.items()
                ]
                adjustments['trend_alignment'] = sum(trend_scores) / sum(
                    self.timeframe_weights.get(tf, 0.1) 
                    for tf in timeframe_scores
                )
            
            # Volatility adjustment
            if self.use_volatility_scaling:
                vol_scores = [
                    score['volatility_score'] * self.timeframe_weights.get(tf, 0.1)
                    for tf, score in timeframe_scores.items()
                ]
                adjustments['volatility'] = sum(vol_scores) / sum(
                    self.timeframe_weights.get(tf, 0.1) 
                    for tf in timeframe_scores
                )
            
            # Support/resistance adjustment
            if self.use_support_resistance:
                sr_scores = [
                    score['sr_score'] * self.timeframe_weights.get(tf, 0.1)
                    for tf, score in timeframe_scores.items()
                ]
                adjustments['support_resistance'] = sum(sr_scores) / sum(
                    self.timeframe_weights.get(tf, 0.1) 
                    for tf in timeframe_scores
                )
        
        # Apply adjustments
        total_adjustment = (
            adjustments['trend_alignment'] * 0.4 +
            adjustments['volatility'] * 0.4 +
            adjustments['support_resistance'] * 0.2
        )
        
        # Limit adjustment range
        total_adjustment = max(0.5, min(1.5, total_adjustment))
        
        # Calculate final position size
        adjusted_position_pct = position_pct * total_adjustment
        position_value = portfolio.equity * adjusted_position_pct
        quantity = position_value / current_price if current_price > 0 else 0
        
        # Store metadata
        signal.signal_data["position_sizing"] = {
            "method": "multi_timeframe",
            "base_position_pct": position_pct,
            "adjustments": adjustments,
            "total_adjustment": total_adjustment,
            "final_position_pct": adjusted_position_pct,
            "timeframe_scores": timeframe_scores,
        }
        
        return quantity
    
    def _analyze_timeframe(
        self,
        tf_data: TimeframeData,
        signal: SignalEvent,
        current_price: float,
    ) -> Dict[str, float]:
        """Analyze a single timeframe for position sizing.
        
        Args:
            tf_data: Timeframe data container.
            signal: Signal event.
            current_price: Current price.
            
        Returns:
            Dictionary of scores for this timeframe.
        """
        scores = {
            'trend_alignment': 1.0,
            'volatility_score': 1.0,
            'sr_score': 1.0,
        }
        
        # Trend alignment score
        if self.use_trend_alignment and tf_data.trend_strength > 0:
            # Check if signal aligns with trend
            sma_20 = tf_data.data['close'].rolling(20).mean()
            sma_50 = tf_data.data['close'].rolling(50).mean()
            
            if len(sma_20) > 0 and len(sma_50) > 0:
                current_sma_20 = sma_20.iloc[-1]
                current_sma_50 = sma_50.iloc[-1]
                
                # Bullish trend
                if current_sma_20 > current_sma_50:
                    if signal.signal_type.value.startswith("ENTRY_LONG"):
                        scores['trend_alignment'] = 1.0 + (tf_data.trend_strength / 100) * 0.5
                    elif signal.signal_type.value.startswith("ENTRY_SHORT"):
                        scores['trend_alignment'] = 1.0 - (tf_data.trend_strength / 100) * 0.5
                
                # Bearish trend
                elif current_sma_20 < current_sma_50:
                    if signal.signal_type.value.startswith("ENTRY_SHORT"):
                        scores['trend_alignment'] = 1.0 + (tf_data.trend_strength / 100) * 0.5
                    elif signal.signal_type.value.startswith("ENTRY_LONG"):
                        scores['trend_alignment'] = 1.0 - (tf_data.trend_strength / 100) * 0.5
        
        # Volatility score
        if self.use_volatility_scaling and tf_data.volatility > 0:
            # Lower size in high volatility
            if tf_data.volatility > 0.3:  # High volatility (30% annualized)
                scores['volatility_score'] = 0.7
            elif tf_data.volatility > 0.2:  # Medium-high volatility
                scores['volatility_score'] = 0.85
            elif tf_data.volatility < 0.1:  # Low volatility
                scores['volatility_score'] = 1.2
            else:  # Normal volatility
                scores['volatility_score'] = 1.0
        
        # Support/resistance score
        if self.use_support_resistance and tf_data.support_resistance:
            resistance_levels = tf_data.support_resistance.get('resistance', [])
            support_levels = tf_data.support_resistance.get('support', [])
            
            # Check proximity to levels
            for resistance in resistance_levels:
                if abs(current_price - resistance) / current_price < 0.005:  # Within 0.5%
                    if signal.signal_type.value.startswith("ENTRY_LONG"):
                        scores['sr_score'] *= 0.8  # Reduce size near resistance
                    break
            
            for support in support_levels:
                if abs(current_price - support) / current_price < 0.005:  # Within 0.5%
                    if signal.signal_type.value.startswith("ENTRY_SHORT"):
                        scores['sr_score'] *= 0.8  # Reduce size near support
                    break
        
        return scores


class AdaptiveMultiTimeframeSizer(MultiTimeframePositionSizer):
    """Adaptive version that automatically adjusts timeframe weights based on performance."""
    
    def __init__(self, *args, **kwargs):
        """Initialize adaptive multi-timeframe sizer."""
        super().__init__(*args, **kwargs)
        self.timeframe_performance = {tf: [] for tf in self.timeframes}
        self.adaptation_rate = kwargs.get('adaptation_rate', 0.1)
    
    def update_performance(self, timeframe: str, signal_accuracy: float) -> None:
        """Update performance tracking for a timeframe.
        
        Args:
            timeframe: Timeframe identifier.
            signal_accuracy: Accuracy of signals from this timeframe.
        """
        if timeframe in self.timeframe_performance:
            self.timeframe_performance[timeframe].append(signal_accuracy)
            
            # Keep only recent performance
            if len(self.timeframe_performance[timeframe]) > 50:
                self.timeframe_performance[timeframe] = self.timeframe_performance[timeframe][-50:]
            
            # Adapt weights
            self._adapt_weights()
    
    def _adapt_weights(self) -> None:
        """Adapt timeframe weights based on performance."""
        # Calculate average performance for each timeframe
        avg_performance = {}
        
        for tf in self.timeframes:
            if tf in self.timeframe_performance and self.timeframe_performance[tf]:
                avg_performance[tf] = np.mean(self.timeframe_performance[tf])
            else:
                avg_performance[tf] = 0.5  # Neutral
        
        # Update weights based on performance
        for tf in self.timeframes:
            if tf in avg_performance:
                # Increase weight for better performing timeframes
                performance_multiplier = avg_performance[tf] * 2  # 0 to 2 range
                
                current_weight = self.timeframe_weights.get(tf, 0.1)
                new_weight = current_weight * (1 - self.adaptation_rate) + (
                    current_weight * performance_multiplier * self.adaptation_rate
                )
                
                self.timeframe_weights[tf] = new_weight
        
        # Normalize weights
        total_weight = sum(self.timeframe_weights.values())
        if total_weight > 0:
            self.timeframe_weights = {
                tf: w / total_weight 
                for tf, w in self.timeframe_weights.items()
            }