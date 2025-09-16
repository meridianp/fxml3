#!/usr/bin/env python
"""Simplified training script for 100:1 leverage models."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime
import joblib
import json
import warnings
warnings.filterwarnings('ignore')

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import StandardScaler

def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add essential features for trading."""
    
    # Price returns
    for period in [1, 2, 4, 8, 12]:
        df[f'returns_{period}'] = df['close'].pct_change(period)
    
    # Moving averages
    for period in [8, 20, 50]:
        df[f'sma_{period}'] = df['close'].rolling(period).mean()
        df[f'sma_{period}_slope'] = df[f'sma_{period}'].pct_change(4)
    
    # RSI
    def calculate_rsi(data, period=14):
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    df['rsi_14'] = calculate_rsi(df['close'])
    
    # Volatility
    df['volatility'] = df['returns_1'].rolling(20).std()
    df['atr'] = (df['high'] - df['low']).rolling(14).mean()
    
    # Time features
    df['hour'] = df.index.hour
    df['day_of_week'] = df.index.dayofweek
    
    # Trading sessions
    df['is_london'] = ((df['hour'] >= 8) & (df['hour'] < 16)).astype(int)
    df['is_ny'] = ((df['hour'] >= 13) & (df['hour'] < 22)).astype(int)
    df['is_asian'] = ((df['hour'] >= 23) | (df['hour'] < 8)).astype(int)
    
    return df

def create_labels(df: pd.DataFrame, symbol: str, threshold_pips: float = 3) -> pd.Series:
    """Create trading labels based on future price movement."""
    
    # Adjust threshold for JPY pairs
    if 'JPY' in symbol:
        threshold = threshold_pips / 100  # JPY pairs have different decimal places
    else:
        threshold = threshold_pips / 10000  # Standard pairs
    
    # Look ahead 2-6 bars (8-24 hours)
    future_returns = []
    for h in range(2, 7):
        future_returns.append(df['close'].pct_change(h).shift(-h))
    
    # Average future return
    df['future_return'] = pd.concat(future_returns, axis=1).mean(axis=1)
    
    # Create labels
    df['label'] = 0  # Default: no trade
    df.loc[df['future_return'] > threshold, 'label'] = 1   # Long
    df.loc[df['future_return'] < -threshold, 'label'] = -1  # Short
    
    return df['label']

def train_model(symbol: str):
    """Train a model for a single symbol."""
    print(f"\n{'='*60}")
    print(f"Training {symbol}")
    print(f"{'='*60}")
    
    # Load data
    data_file = f'data/processed/4h/{symbol}_4H_features_complete.parquet'
    if not Path(data_file).exists():
        print(f"❌ No data file found: {data_file}")
        return None
    
    df = pd.read_parquet(data_file)
    print(f"Loaded {len(df)} bars")
    
    # Filter to 2024 data only
    df = df[df.index >= '2024-01-01']
    print(f"Using {len(df)} bars from 2024")
    
    # Add features
    df = prepare_features(df)
    
    # Create labels
    df['label'] = create_labels(df, symbol)
    
    # Select features
    feature_columns = [
        'returns_1', 'returns_2', 'returns_4', 'returns_8',
        'sma_8_slope', 'sma_20_slope', 'sma_50_slope',
        'rsi_14', 'volatility', 'atr',
        'hour', 'day_of_week',
        'is_london', 'is_ny', 'is_asian'
    ]
    
    # Remove NaN
    df = df.dropna(subset=feature_columns + ['label'])
    
    # Check label distribution
    print(f"\nLabel distribution:")
    print(df['label'].value_counts().sort_index())
    
    if len(df['label'].unique()) < 2:
        print("❌ Not enough label diversity")
        return None
    
    # Prepare data
    X = df[feature_columns]
    y = df['label']
    
    # Split data (70/30)
    split_date = '2024-09-01'
    X_train = X[X.index < split_date]
    y_train = y[y.index < split_date]
    X_test = X[X.index >= split_date]
    y_test = y[y.index >= split_date]
    
    print(f"\nTrain: {len(X_train)}, Test: {len(X_test)}")
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train model
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=6,
        min_samples_split=20,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )
    
    print("\nTraining Random Forest...")
    model.fit(X_train_scaled, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test_scaled)
    accuracy = accuracy_score(y_test, y_pred)
    
    print(f"\nTest Accuracy: {accuracy:.3f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=['Short', 'Hold', 'Long']))
    
    # Feature importance
    importance = pd.DataFrame({
        'feature': feature_columns,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print("\nTop Features:")
    print(importance.head())
    
    # Save model
    model_dir = Path(f'models/{symbol}_100x_simple')
    model_dir.mkdir(parents=True, exist_ok=True)
    
    joblib.dump(model, model_dir / 'model.pkl')
    joblib.dump(scaler, model_dir / 'scaler.pkl')
    
    # Save config
    config = {
        'symbol': symbol,
        'accuracy': float(accuracy),
        'features': feature_columns,
        'train_samples': len(X_train),
        'test_samples': len(X_test),
        'threshold_pips': 3,
        'trained_at': datetime.now().isoformat()
    }
    
    with open(model_dir / 'config.json', 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"\n✅ Model saved to {model_dir}")
    
    return accuracy

def main():
    """Train models for all symbols."""
    symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF']
    
    results = {}
    for symbol in symbols:
        try:
            accuracy = train_model(symbol)
            if accuracy:
                results[symbol] = accuracy
        except Exception as e:
            print(f"❌ Error training {symbol}: {e}")
    
    print("\n" + "="*60)
    print("TRAINING COMPLETE")
    print("="*60)
    
    for symbol, acc in results.items():
        print(f"{symbol}: {acc:.3f}")
    
    if results:
        print(f"\nAverage: {np.mean(list(results.values())):.3f}")

if __name__ == "__main__":
    main()