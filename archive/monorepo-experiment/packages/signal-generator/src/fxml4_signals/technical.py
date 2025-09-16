"""
Technical indicator-based signal generation.
"""

from typing import List, Dict, Any
import pandas as pd
import numpy as np
from datetime import datetime
import ta

from fxml4_core.logging import get_logger
from fxml4_signals.base import Signal, SignalType, SignalSource

logger = get_logger(__name__)


class TechnicalSignals(SignalSource):
    """Generate signals from technical indicators."""
    
    def __init__(
        self,
        name: str = "technical",
        weight: float = 1.0,
        rsi_oversold: float = 30,
        rsi_overbought: float = 70,
        bb_std: float = 2.0
    ):
        super().__init__(name, weight)
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.bb_std = bb_std
    
    def get_required_columns(self) -> List[str]:
        """Get required columns."""
        return ["open", "high", "low", "close", "volume"]
    
    def generate_signals(self, data: pd.DataFrame, symbol: str) -> List[Signal]:
        """Generate technical indicator signals."""
        signals = []
        
        # Calculate indicators
        indicators = self._calculate_indicators(data)
        
        # Generate signals from each indicator
        signals.extend(self._ma_crossover_signals(indicators, symbol))
        signals.extend(self._rsi_signals(indicators, symbol))
        signals.extend(self._macd_signals(indicators, symbol))
        signals.extend(self._bollinger_signals(indicators, symbol))
        
        return signals
    
    def _calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators."""
        df = data.copy()
        
        # Check if we have enough data for calculations
        if len(df) < 14:
            logger.warning(f"Insufficient data for indicators: {len(df)} rows (minimum 14 required)")
            # Initialize columns with NaN
            for col in ['sma_20', 'sma_50', 'ema_12', 'ema_26', 'rsi', 'macd', 'macd_signal', 'macd_diff', 'bb_upper', 'bb_middle', 'bb_lower', 'atr']:
                df[col] = np.nan
            return df
        
        # Moving averages
        if len(df) >= 20:
            df['sma_20'] = ta.trend.sma_indicator(df['close'], window=20)
            df['bb_upper'] = ta.volatility.BollingerBands(df['close'], window=20, window_dev=self.bb_std).bollinger_hband()
            df['bb_middle'] = ta.volatility.BollingerBands(df['close'], window=20, window_dev=self.bb_std).bollinger_mavg()
            df['bb_lower'] = ta.volatility.BollingerBands(df['close'], window=20, window_dev=self.bb_std).bollinger_lband()
        else:
            df['sma_20'] = np.nan
            df['bb_upper'] = np.nan
            df['bb_middle'] = np.nan
            df['bb_lower'] = np.nan
            
        if len(df) >= 50:
            df['sma_50'] = ta.trend.sma_indicator(df['close'], window=50)
        else:
            df['sma_50'] = np.nan
            
        df['ema_12'] = ta.trend.ema_indicator(df['close'], window=12)
        df['ema_26'] = ta.trend.ema_indicator(df['close'], window=26)
        
        # RSI
        df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
        
        # MACD
        macd = ta.trend.MACD(df['close'])
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_diff'] = macd.macd_diff()
        
        # ATR for stop loss (needs at least 14 periods)
        if len(df) >= 14:
            df['atr'] = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close']).average_true_range()
        else:
            df['atr'] = np.nan
        
        return df
    
    def _ma_crossover_signals(self, data: pd.DataFrame, symbol: str) -> List[Signal]:
        """Generate moving average crossover signals."""
        signals = []
        
        # Golden cross (SMA 20 crosses above SMA 50)
        golden_cross = (
            (data['sma_20'] > data['sma_50']) & 
            (data['sma_20'].shift(1) <= data['sma_50'].shift(1))
        )
        
        # Death cross (SMA 20 crosses below SMA 50)
        death_cross = (
            (data['sma_20'] < data['sma_50']) & 
            (data['sma_20'].shift(1) >= data['sma_50'].shift(1))
        )
        
        for idx in data[golden_cross].index:
            signal = Signal(
                timestamp=idx,
                symbol=symbol,
                signal_type=SignalType.BUY,
                source=f"{self.name}_ma_crossover",
                confidence=0.7,
                price=data.loc[idx, 'close'],
                metadata={
                    "indicator": "ma_crossover",
                    "pattern": "golden_cross",
                    "sma_20": data.loc[idx, 'sma_20'],
                    "sma_50": data.loc[idx, 'sma_50']
                }
            )
            signals.append(signal)
        
        for idx in data[death_cross].index:
            signal = Signal(
                timestamp=idx,
                symbol=symbol,
                signal_type=SignalType.SELL,
                source=f"{self.name}_ma_crossover",
                confidence=0.7,
                price=data.loc[idx, 'close'],
                metadata={
                    "indicator": "ma_crossover",
                    "pattern": "death_cross",
                    "sma_20": data.loc[idx, 'sma_20'],
                    "sma_50": data.loc[idx, 'sma_50']
                }
            )
            signals.append(signal)
        
        return signals
    
    def _rsi_signals(self, data: pd.DataFrame, symbol: str) -> List[Signal]:
        """Generate RSI-based signals."""
        signals = []
        
        # Oversold condition
        oversold = (
            (data['rsi'] < self.rsi_oversold) & 
            (data['rsi'].shift(1) >= self.rsi_oversold)
        )
        
        # Overbought condition
        overbought = (
            (data['rsi'] > self.rsi_overbought) & 
            (data['rsi'].shift(1) <= self.rsi_overbought)
        )
        
        for idx in data[oversold].index:
            signal = Signal(
                timestamp=idx,
                symbol=symbol,
                signal_type=SignalType.BUY,
                source=f"{self.name}_rsi",
                confidence=0.6,
                price=data.loc[idx, 'close'],
                metadata={
                    "indicator": "rsi",
                    "rsi_value": data.loc[idx, 'rsi'],
                    "condition": "oversold"
                }
            )
            signals.append(signal)
        
        for idx in data[overbought].index:
            signal = Signal(
                timestamp=idx,
                symbol=symbol,
                signal_type=SignalType.SELL,
                source=f"{self.name}_rsi",
                confidence=0.6,
                price=data.loc[idx, 'close'],
                metadata={
                    "indicator": "rsi",
                    "rsi_value": data.loc[idx, 'rsi'],
                    "condition": "overbought"
                }
            )
            signals.append(signal)
        
        return signals
    
    def _macd_signals(self, data: pd.DataFrame, symbol: str) -> List[Signal]:
        """Generate MACD-based signals."""
        signals = []
        
        # MACD crosses above signal line
        macd_buy = (
            (data['macd'] > data['macd_signal']) & 
            (data['macd'].shift(1) <= data['macd_signal'].shift(1))
        )
        
        # MACD crosses below signal line
        macd_sell = (
            (data['macd'] < data['macd_signal']) & 
            (data['macd'].shift(1) >= data['macd_signal'].shift(1))
        )
        
        for idx in data[macd_buy].index:
            # Higher confidence if MACD is below zero (potential trend reversal)
            confidence = 0.8 if data.loc[idx, 'macd'] < 0 else 0.6
            
            signal = Signal(
                timestamp=idx,
                symbol=symbol,
                signal_type=SignalType.BUY,
                source=f"{self.name}_macd",
                confidence=confidence,
                price=data.loc[idx, 'close'],
                metadata={
                    "indicator": "macd",
                    "reason": "macd_bullish_crossover",
                    "macd": data.loc[idx, 'macd'],
                    "macd_signal": data.loc[idx, 'macd_signal'],
                    "histogram": data.loc[idx, 'macd_diff']
                }
            )
            signals.append(signal)
        
        for idx in data[macd_sell].index:
            # Higher confidence if MACD is above zero (potential trend reversal)
            confidence = 0.8 if data.loc[idx, 'macd'] > 0 else 0.6
            
            signal = Signal(
                timestamp=idx,
                symbol=symbol,
                signal_type=SignalType.SELL,
                source=f"{self.name}_macd",
                confidence=confidence,
                price=data.loc[idx, 'close'],
                metadata={
                    "indicator": "macd",
                    "reason": "macd_bearish_crossover",
                    "macd": data.loc[idx, 'macd'],
                    "macd_signal": data.loc[idx, 'macd_signal'],
                    "histogram": data.loc[idx, 'macd_diff']
                }
            )
            signals.append(signal)
        
        return signals
    
    def _bollinger_signals(self, data: pd.DataFrame, symbol: str) -> List[Signal]:
        """Generate Bollinger Band signals."""
        signals = []
        
        # Price touches lower band (potential bounce)
        bb_buy = (
            (data['close'] <= data['bb_lower']) & 
            (data['close'].shift(1) > data['bb_lower'].shift(1))
        )
        
        # Price touches upper band (potential reversal)
        bb_sell = (
            (data['close'] >= data['bb_upper']) & 
            (data['close'].shift(1) < data['bb_upper'].shift(1))
        )
        
        for idx in data[bb_buy].index:
            signal = Signal(
                timestamp=idx,
                symbol=symbol,
                signal_type=SignalType.BUY,
                source=f"{self.name}_bollinger",
                confidence=0.65,
                price=data.loc[idx, 'close'],
                metadata={
                    "indicator": "bollinger_bands",
                    "bb_upper": data.loc[idx, 'bb_upper'],
                    "bb_middle": data.loc[idx, 'bb_middle'],
                    "bb_lower": data.loc[idx, 'bb_lower'],
                    "condition": "touch_lower"
                }
            )
            signals.append(signal)
        
        for idx in data[bb_sell].index:
            signal = Signal(
                timestamp=idx,
                symbol=symbol,
                signal_type=SignalType.SELL,
                source=f"{self.name}_bollinger",
                confidence=0.65,
                price=data.loc[idx, 'close'],
                metadata={
                    "indicator": "bollinger_bands",
                    "bb_upper": data.loc[idx, 'bb_upper'],
                    "bb_middle": data.loc[idx, 'bb_middle'],
                    "bb_lower": data.loc[idx, 'bb_lower'],
                    "condition": "touch_upper"
                }
            )
            signals.append(signal)
        
        return signals