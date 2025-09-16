"""Unified feature engineering module for ML model training and backtesting.

This module provides consistent feature generation that can be used by both
the training pipeline and the backtesting system to ensure feature alignment.
"""

import logging
from typing import Dict, List, Optional, Tuple, Union
import warnings

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class UnifiedFeatureEngineer:
    """Unified feature engineering for both training and backtesting."""
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize the feature engineer.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        
        # Feature configuration
        self.basic_indicators = self.config.get('basic_indicators', [
            'sma', 'ema', 'rsi', 'macd', 'bollinger', 'stoch', 'atr', 'adx'
        ])
        
        self.ma_periods = self.config.get('ma_periods', [5, 21, 55, 200])
        
        self.advanced_features = self.config.get('advanced_features', True)
        self.elliott_wave_features = self.config.get('elliott_wave_features', True)
        self.regime_features = self.config.get('regime_features', True)
        self.microstructure_features = self.config.get('microstructure_features', True)
        
    def generate_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate all features for the given data.
        
        Args:
            data: DataFrame with OHLCV data
            
        Returns:
            DataFrame with all features added
        """
        df = data.copy()
        
        # Check required columns
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")
        
        # 1. Basic technical indicators
        logger.info("Generating basic technical indicators...")
        df = self._add_basic_indicators(df)
        
        # 2. Advanced features
        if self.advanced_features:
            logger.info("Generating advanced features...")
            df = self._add_market_microstructure_features(df)
            df = self._add_pattern_features(df)
        
        # 3. Elliott Wave features
        if self.elliott_wave_features:
            logger.info("Generating Elliott Wave features...")
            df = self._add_elliott_wave_features(df)
        
        # 4. Market regime features
        if self.regime_features:
            logger.info("Generating market regime features...")
            df = self._add_regime_features(df)
        
        # 5. Additional derived features
        logger.info("Generating derived features...")
        df = self._add_derived_features(df)
        
        # Clean up
        df = self._clean_features(df)
        
        return df
    
    def _add_basic_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add basic technical indicators."""
        
        # Simple Moving Averages
        if 'sma' in self.basic_indicators:
            for period in self.ma_periods:
                df[f'sma_{period}'] = df['close'].rolling(window=period).mean()
        
        # Exponential Moving Averages
        if 'ema' in self.basic_indicators:
            for period in self.ma_periods:
                df[f'ema_{period}'] = df['close'].ewm(span=period, adjust=False).mean()
        
        # RSI
        if 'rsi' in self.basic_indicators:
            delta = df['close'].diff()
            gain = delta.clip(lower=0)
            loss = -delta.clip(upper=0)
            avg_gain = gain.rolling(window=14).mean()
            avg_loss = loss.rolling(window=14).mean()
            rs = avg_gain / (avg_loss + 1e-10)
            df['rsi_14'] = 100 - (100 / (1 + rs))
        
        # MACD
        if 'macd' in self.basic_indicators:
            ema_12 = df['close'].ewm(span=12, adjust=False).mean()
            ema_26 = df['close'].ewm(span=26, adjust=False).mean()
            df['macd'] = ema_12 - ema_26
            df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
            df['macd_hist'] = df['macd'] - df['macd_signal']
            
            # MACD crossover signals
            m = df['macd']
            s = df['macd_signal']
            df['macd_cross_up'] = ((m > s) & (m.shift(1) <= s.shift(1))).astype(int)
            df['macd_cross_down'] = ((m < s) & (m.shift(1) >= s.shift(1))).astype(int)
            df['macd_cross_strength'] = 0.0
            df.loc[df['macd_cross_up'] == 1, 'macd_cross_strength'] = df.loc[df['macd_cross_up'] == 1, 'macd_hist']
            df.loc[df['macd_cross_down'] == 1, 'macd_cross_strength'] = -df.loc[df['macd_cross_down'] == 1, 'macd_hist']
        
        # Bollinger Bands
        if 'bollinger' in self.basic_indicators:
            period = 20
            std_dev = 2
            df['bb_middle'] = df['close'].rolling(window=period).mean()
            df['bb_std'] = df['close'].rolling(window=period).std()
            df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * std_dev)
            df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * std_dev)
            df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / (df['bb_middle'] + 1e-10)
            
            # Bollinger Band Squeeze
            squeeze_window = 20
            squeeze_threshold = 0.05
            ratio = (df['bb_width'] / (df['bb_middle'] + 1e-10)).rolling(squeeze_window).mean()
            df['bb_squeeze'] = (ratio < squeeze_threshold).astype(int)
        
        # Stochastic Oscillator
        if 'stoch' in self.basic_indicators:
            k_period = 14
            d_period = 3
            low_min = df['low'].rolling(window=k_period).min()
            high_max = df['high'].rolling(window=k_period).max()
            df['stoch_k'] = 100 * ((df['close'] - low_min) / (high_max - low_min + 1e-10))
            df['stoch_d'] = df['stoch_k'].rolling(window=d_period).mean()
        
        # ATR
        if 'atr' in self.basic_indicators:
            high_low = df['high'] - df['low']
            high_close = (df['high'] - df['close'].shift()).abs()
            low_close = (df['low'] - df['close'].shift()).abs()
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = ranges.max(axis=1)
            df['atr_14'] = true_range.rolling(window=14).mean()
        
        # ADX
        if 'adx' in self.basic_indicators:
            # Simplified ADX calculation
            high_change = df['high'].diff()
            low_change = -df['low'].diff()
            
            plus_dm = ((high_change > low_change) & (high_change > 0)).astype(float) * high_change
            minus_dm = ((low_change > high_change) & (low_change > 0)).astype(float) * low_change
            
            atr = df.get('atr_14', true_range.rolling(window=14).mean())
            
            plus_di = 100 * plus_dm.rolling(window=14).mean() / (atr + 1e-10)
            minus_di = 100 * minus_dm.rolling(window=14).mean() / (atr + 1e-10)
            
            dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10).abs())
            df['adx_14'] = dx.rolling(window=14).mean()
            df['di_plus_14'] = plus_di
            df['di_minus_14'] = minus_di
        
        # Basic price features
        df['daily_return'] = df['close'].pct_change()
        df['volatility_14'] = df['close'].pct_change().rolling(window=14).std() * 100
        df['weekly_change'] = (df['close'] - df['close'].shift(5 * 24)) / (df['close'].shift(5 * 24) + 1e-10) * 100
        
        # Volume features
        if df['volume'].sum() > 0:
            df['volume_sma'] = df['volume'].rolling(20).mean()
        
        return df
    
    def _add_market_microstructure_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add market microstructure features."""
        if not self.microstructure_features:
            return df
        
        # Price efficiency metrics
        df['high_low_spread'] = (df['high'] - df['low']) / (df['close'] + 1e-10)
        df['close_to_high'] = (df['close'] - df['low']) / (df['high'] - df['low'] + 1e-10)
        
        # Volatility measures
        df['parkinson_vol'] = np.sqrt(
            (1 / (4 * np.log(2))) * np.log(df['high'] / (df['low'] + 1e-10)) ** 2
        ).rolling(window=20).mean()
        
        # Price momentum
        df['momentum_3'] = df['close'].pct_change(3)
        df['momentum_10'] = df['close'].pct_change(10)
        df['momentum_30'] = df['close'].pct_change(30)
        
        # Volume patterns (if available)
        if df['volume'].sum() > 0:
            df['volume_sma_20'] = df['volume'].rolling(window=20).mean()
            df['volume_ratio'] = df['volume'] / (df['volume_sma_20'] + 1e-10)
        else:
            df['volume_sma_20'] = 0
            df['volume_ratio'] = 1
        
        return df
    
    def _add_pattern_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add price pattern features."""
        # Support/Resistance levels
        df['resistance_20'] = df['high'].rolling(window=20).max()
        df['support_20'] = df['low'].rolling(window=20).min()
        df['price_to_resistance'] = df['close'] / (df['resistance_20'] + 1e-10)
        df['price_to_support'] = df['close'] / (df['support_20'] + 1e-10)
        
        # Channel indicators
        df['channel_position'] = (df['close'] - df['support_20']) / (df['resistance_20'] - df['support_20'] + 1e-10)
        
        # Trend strength (requires ATR)
        if 'atr_14' in df.columns:
            df['trend_strength'] = (df['close'] - df['close'].shift(20)) / (df['atr_14'].rolling(window=20).mean() + 1e-10)
        else:
            df['trend_strength'] = (df['close'] - df['close'].shift(20)) / (df['close'].shift(20) + 1e-10)
        
        return df
    
    def _add_elliott_wave_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add Elliott Wave features (simplified version)."""
        if not self.elliott_wave_features:
            return df
        
        # Initialize features
        window_size = 100
        df['wave_trend'] = 0.0
        df['fib_support'] = df['close']
        df['fib_resistance'] = df['close']
        
        # Simplified wave detection in rolling windows
        for i in range(window_size, len(df), 20):  # Step by 20 for efficiency
            if i >= len(df):
                break
                
            window_data = df.iloc[max(0, i-window_size):i]
            
            if len(window_data) < 10:  # Skip if window too small
                continue
            
            # Find high and low in window
            high_idx = window_data['high'].idxmax()
            low_idx = window_data['low'].idxmin()
            
            # Simple trend detection
            if pd.notna(high_idx) and pd.notna(low_idx):
                if high_idx > low_idx:  # Uptrend
                    df.loc[df.index[i-1], 'wave_trend'] = 1.0
                    # Calculate Fibonacci levels
                    swing_range = window_data.loc[high_idx, 'high'] - window_data.loc[low_idx, 'low']
                    df.loc[df.index[i-1], 'fib_support'] = window_data.loc[low_idx, 'low'] + 0.618 * swing_range
                    df.loc[df.index[i-1], 'fib_resistance'] = window_data.loc[low_idx, 'low'] + 1.618 * swing_range
                else:  # Downtrend
                    df.loc[df.index[i-1], 'wave_trend'] = -1.0
                    swing_range = window_data.loc[high_idx, 'high'] - window_data.loc[low_idx, 'low']
                    df.loc[df.index[i-1], 'fib_support'] = window_data.loc[high_idx, 'high'] - 1.618 * swing_range
                    df.loc[df.index[i-1], 'fib_resistance'] = window_data.loc[high_idx, 'high'] - 0.618 * swing_range
        
        # Forward fill the wave features
        df['wave_trend'] = df['wave_trend'].fillna(method='ffill').fillna(0)
        df['fib_support'] = df['fib_support'].fillna(method='ffill').fillna(df['close'])
        df['fib_resistance'] = df['fib_resistance'].fillna(method='ffill').fillna(df['close'])
        
        # Distance to Fibonacci levels
        df['dist_to_fib_support'] = (df['close'] - df['fib_support']) / (df['close'] + 1e-10)
        df['dist_to_fib_resistance'] = (df['fib_resistance'] - df['close']) / (df['close'] + 1e-10)
        
        return df
    
    def _add_regime_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add market regime features."""
        if not self.regime_features:
            return df
        
        # Volatility regime
        try:
            vol_rolling = df['atr_14'].rolling(window=100, min_periods=50).mean()
            df['vol_regime'] = pd.qcut(vol_rolling, q=3, labels=[0, 1, 2], duplicates='drop')
            df['vol_regime'] = pd.to_numeric(df['vol_regime'], errors='coerce').fillna(1)
        except:
            df['vol_regime'] = 1
        
        # Trend regime (using ADX)
        if 'adx_14' in df.columns:
            df['trend_regime'] = (df['adx_14'] > 25).astype(int)
        else:
            df['trend_regime'] = 0
        
        # Momentum regime
        try:
            rsi_rolling = df['rsi_14'].rolling(window=50, min_periods=25).mean()
            df['momentum_regime'] = pd.qcut(rsi_rolling, q=3, labels=[0, 1, 2], duplicates='drop')
            df['momentum_regime'] = pd.to_numeric(df['momentum_regime'], errors='coerce').fillna(1)
        except:
            df['momentum_regime'] = 1
        
        return df
    
    def _add_derived_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add additional derived features."""
        # Price position relative to moving averages
        for period in self.ma_periods:
            if f'sma_{period}' in df.columns:
                df[f'price_above_sma_{period}'] = (df['close'] > df[f'sma_{period}']).astype(int)
                df[f'price_to_sma_{period}'] = df['close'] / (df[f'sma_{period}'] + 1e-10)
        
        # Moving average crossovers
        if 'sma_50' in df.columns and 'sma_200' in df.columns:
            df['golden_cross'] = ((df['sma_50'] > df['sma_200']) & 
                                  (df['sma_50'].shift(1) <= df['sma_200'].shift(1))).astype(int)
            df['death_cross'] = ((df['sma_50'] < df['sma_200']) & 
                                 (df['sma_50'].shift(1) >= df['sma_200'].shift(1))).astype(int)
        
        # RSI extremes
        if 'rsi_14' in df.columns:
            df['rsi_oversold'] = (df['rsi_14'] < 30).astype(int)
            df['rsi_overbought'] = (df['rsi_14'] > 70).astype(int)
        
        return df
    
    def _clean_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean up features by handling NaN and inf values."""
        # Replace infinities
        df = df.replace([np.inf, -np.inf], np.nan)
        
        # Forward fill then backward fill
        df = df.fillna(method='ffill').fillna(method='bfill')
        
        # Fill any remaining NaN with 0
        df = df.fillna(0)
        
        return df
    
    def get_feature_names(self) -> List[str]:
        """Get list of all feature names that will be generated."""
        features = []
        
        # Basic indicators
        if 'sma' in self.basic_indicators:
            features.extend([f'sma_{p}' for p in self.ma_periods])
        if 'ema' in self.basic_indicators:
            features.extend([f'ema_{p}' for p in self.ma_periods])
        if 'rsi' in self.basic_indicators:
            features.append('rsi_14')
        if 'macd' in self.basic_indicators:
            features.extend(['macd', 'macd_signal', 'macd_hist', 'macd_cross_up', 
                            'macd_cross_down', 'macd_cross_strength'])
        if 'bollinger' in self.basic_indicators:
            features.extend(['bb_middle', 'bb_std', 'bb_upper', 'bb_lower', 
                            'bb_width', 'bb_squeeze'])
        if 'stoch' in self.basic_indicators:
            features.extend(['stoch_k', 'stoch_d'])
        if 'atr' in self.basic_indicators:
            features.append('atr_14')
        if 'adx' in self.basic_indicators:
            features.extend(['adx_14', 'di_plus_14', 'di_minus_14'])
        
        # Basic price features
        features.extend(['daily_return', 'volatility_14', 'weekly_change'])
        
        # Volume features
        features.extend(['volume_sma', 'volume_sma_20', 'volume_ratio'])
        
        # Microstructure features
        if self.microstructure_features:
            features.extend(['high_low_spread', 'close_to_high', 'parkinson_vol',
                            'momentum_3', 'momentum_10', 'momentum_30'])
        
        # Pattern features
        if self.advanced_features:
            features.extend(['resistance_20', 'support_20', 'price_to_resistance',
                            'price_to_support', 'channel_position', 'trend_strength'])
        
        # Elliott Wave features
        if self.elliott_wave_features:
            features.extend(['wave_trend', 'fib_support', 'fib_resistance',
                            'dist_to_fib_support', 'dist_to_fib_resistance'])
        
        # Regime features
        if self.regime_features:
            features.extend(['vol_regime', 'trend_regime', 'momentum_regime'])
        
        # Derived features
        for period in self.ma_periods:
            features.extend([f'price_above_sma_{period}', f'price_to_sma_{period}'])
        
        if 50 in self.ma_periods and 200 in self.ma_periods:
            features.extend(['golden_cross', 'death_cross'])
        
        features.extend(['rsi_oversold', 'rsi_overbought'])
        
        return features