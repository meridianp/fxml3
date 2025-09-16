#!/usr/bin/env python
"""Train integrated system using daily aggregated data for better alignment with economic indicators."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import joblib
import warnings
warnings.filterwarnings('ignore')

from scripts.train_integrated_system import IntegratedSystemTrainer
from scripts.load_polygon_data import load_aggregated_data

class DailyIntegratedTrainer(IntegratedSystemTrainer):
    """Modified trainer that aggregates to daily data."""
    
    def load_all_data(self, start_date: str, end_date: str):
        """Load data for all symbols and aggregate to daily."""
        print("Loading forex data and aggregating to daily...")
        
        forex_data = {}
        for symbol in self.symbols:
            try:
                # Load minute data
                df = load_aggregated_data(f"C_{symbol}", start_date, end_date)
                
                if df is not None and len(df) > 252:
                    # Aggregate to daily
                    daily_df = df.resample('D').agg({
                        'open': 'first',
                        'high': 'max',
                        'low': 'min',
                        'close': 'last',
                        'volume': 'sum'
                    }).dropna()
                    
                    # Only keep business days
                    daily_df = daily_df[daily_df.index.dayofweek < 5]
                    
                    forex_data[symbol] = daily_df
                    print(f"  ✅ {symbol}: {len(df)} minute bars -> {len(daily_df)} daily bars")
                else:
                    print(f"  ❌ {symbol}: Insufficient data")
            except Exception as e:
                print(f"  ❌ {symbol}: Error loading data - {e}")
        
        return forex_data
    
    def prepare_enhanced_features(self, symbol: str, forex_data: dict, economic_data: dict):
        """Prepare features with better alignment for daily data."""
        print(f"\nPreparing enhanced features for {symbol}...")
        
        # Get target data
        target_df = forex_data[symbol]
        
        # Create a common date range
        start_date = target_df.index[0]
        end_date = target_df.index[-1]
        
        # Create base features from target
        features = pd.DataFrame(index=target_df.index)
        
        # Add technical indicators
        features = self._add_technical_indicators(features, target_df, symbol)
        
        # Add other forex pairs
        for other_symbol, other_df in forex_data.items():
            if other_symbol != symbol:
                # Align data
                aligned_data = other_df.reindex(features.index, method='ffill')
                features[f'{other_symbol}_close'] = aligned_data['close']
                features[f'{other_symbol}_return'] = aligned_data['close'].pct_change()
                features[f'{other_symbol}_return_lag1'] = features[f'{other_symbol}_return'].shift(1)
                features[f'{other_symbol}_return_lag5'] = features[f'{other_symbol}_return'].shift(5)
        
        # Add economic indicators
        for name, series in economic_data.items():
            if isinstance(series, pd.Series) and len(series) > 0:
                # Align to daily frequency
                aligned_series = series.reindex(features.index, method='ffill')
                features[name] = aligned_series
                features[f'{name}_change'] = aligned_series.pct_change()
                features[f'{name}_lag1'] = aligned_series.shift(1)
        
        # Add derived features
        if 'US_10Y' in features.columns and 'US_2Y' in features.columns:
            features['yield_curve'] = features['US_10Y'] - features['US_2Y']
        
        if 'DXY' in features.columns:
            features['DXY_ma20'] = features['DXY'].rolling(20).mean()
            features['DXY_trend'] = features['DXY'] / features['DXY_ma20'] - 1
        
        # Replace infinities with NaN
        features = features.replace([np.inf, -np.inf], np.nan)
        
        # Drop columns with too many NaNs (>50%)
        features = features.dropna(thresh=len(features) * 0.5, axis=1)
        
        return features
    
    def _add_technical_indicators(self, features: pd.DataFrame, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """Add technical indicators for daily data."""
        
        # Price features
        features[f'{symbol}_return'] = df['close'].pct_change()
        features[f'{symbol}_log_return'] = np.log(df['close']).diff()
        
        # Moving averages
        for period in [5, 10, 20, 50, 100, 200]:
            features[f'{symbol}_sma_{period}'] = df['close'].rolling(period).mean()
            features[f'{symbol}_price_to_sma_{period}'] = df['close'] / features[f'{symbol}_sma_{period}']
        
        # RSI
        for period in [7, 14, 21]:
            features[f'{symbol}_rsi_{period}'] = self.calculate_rsi(df['close'], period)
        
        # Bollinger Bands
        for period in [20, 50]:
            sma = df['close'].rolling(period).mean()
            std = df['close'].rolling(period).std()
            features[f'{symbol}_bb_upper_{period}'] = sma + (2 * std)
            features[f'{symbol}_bb_lower_{period}'] = sma - (2 * std)
            features[f'{symbol}_bb_width_{period}'] = features[f'{symbol}_bb_upper_{period}'] - features[f'{symbol}_bb_lower_{period}']
            features[f'{symbol}_bb_position_{period}'] = (df['close'] - features[f'{symbol}_bb_lower_{period}']) / features[f'{symbol}_bb_width_{period}']
        
        # ATR
        tr = pd.DataFrame(index=df.index)
        tr['hl'] = df['high'] - df['low']
        tr['hc'] = abs(df['high'] - df['close'].shift(1))
        tr['lc'] = abs(df['low'] - df['close'].shift(1))
        true_range = tr.max(axis=1)
        
        for period in [7, 14, 21]:
            features[f'{symbol}_atr_{period}'] = true_range.rolling(period).mean()
            features[f'{symbol}_atr_ratio_{period}'] = features[f'{symbol}_atr_{period}'] / df['close']
        
        # Volatility
        for period in [5, 10, 20]:
            features[f'{symbol}_volatility_{period}'] = df['close'].pct_change().rolling(period).std()
        
        # Price patterns
        features[f'{symbol}_higher_high'] = ((df['high'] > df['high'].shift(1)) & 
                                           (df['high'].shift(1) > df['high'].shift(2))).astype(int)
        features[f'{symbol}_lower_low'] = ((df['low'] < df['low'].shift(1)) & 
                                          (df['low'].shift(1) < df['low'].shift(2))).astype(int)
        
        # Support/Resistance
        for period in [20, 50]:
            features[f'{symbol}_resistance_{period}'] = df['high'].rolling(period).max()
            features[f'{symbol}_support_{period}'] = df['low'].rolling(period).min()
            sr_range = features[f'{symbol}_resistance_{period}'] - features[f'{symbol}_support_{period}']
            features[f'{symbol}_sr_position_{period}'] = np.where(
                sr_range > 0,
                (df['close'] - features[f'{symbol}_support_{period}']) / sr_range,
                0.5  # Default to middle if no range
            )
        
        # Lagged returns
        for lag in [1, 2, 3, 5, 10, 20]:
            features[f'{symbol}_return_lag{lag}'] = features[f'{symbol}_return'].shift(lag)
        
        return features


def main():
    """Run daily integrated system training."""
    # Configuration
    symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF']
    
    # Use last 5 years for training (daily data needs more history)
    end_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=365*5)).strftime('%Y-%m-%d')
    
    print("="*80)
    print("DAILY INTEGRATED FOREX SYSTEM TRAINING")
    print("="*80)
    print("This version aggregates minute data to daily for better alignment")
    print("with economic indicators and more stable training.")
    print("="*80)
    
    # Initialize trainer
    trainer = DailyIntegratedTrainer(symbols)
    
    # Override models directory
    trainer.models_dir = Path("models/integrated_daily")
    trainer.models_dir.mkdir(exist_ok=True, parents=True)
    
    # Train all symbols
    trainer.train_all_symbols(start_date, end_date)
    
    print("\n💡 Next steps:")
    print("1. Run daily backtest: python scripts/backtest_integrated_daily.py")
    print("2. Compare with minute-level system")
    print("3. Consider ensemble of both approaches")


if __name__ == "__main__":
    main()