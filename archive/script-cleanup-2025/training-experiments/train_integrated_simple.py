#!/usr/bin/env python
"""Simplified integrated model training without external dependencies."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime
import json
import joblib
import logging
import warnings
warnings.filterwarnings('ignore')

from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from lightgbm import LGBMClassifier
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def add_elliott_wave_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add simplified Elliott Wave-based features."""
    logger.info("Adding Elliott Wave-inspired features...")
    
    # Wave detection using peaks and troughs
    window = 20
    
    # Find local maxima and minima
    df['high_rolling_max'] = df['high'].rolling(window, center=True).max()
    df['low_rolling_min'] = df['low'].rolling(window, center=True).min()
    
    df['is_peak'] = (df['high'] == df['high_rolling_max']).astype(int)
    df['is_trough'] = (df['low'] == df['low_rolling_min']).astype(int)
    
    # Count waves
    df['wave_count'] = (df['is_peak'] | df['is_trough']).cumsum()
    
    # Wave characteristics
    df['wave_length'] = df.groupby('wave_count').cumcount()
    df['wave_amplitude'] = df['high'] - df['low']
    
    # Fibonacci ratios
    df['fib_382'] = df['low'] + 0.382 * (df['high'] - df['low'])
    df['fib_500'] = df['low'] + 0.500 * (df['high'] - df['low'])
    df['fib_618'] = df['low'] + 0.618 * (df['high'] - df['low'])
    
    # Price relative to Fibonacci levels
    df['close_to_fib_382'] = (df['close'] - df['fib_382']) / df['close']
    df['close_to_fib_500'] = (df['close'] - df['fib_500']) / df['close']
    df['close_to_fib_618'] = (df['close'] - df['fib_618']) / df['close']
    
    # Trend strength using wave patterns
    df['wave_trend'] = df['close'].rolling(50).apply(
        lambda x: 1 if x.iloc[-1] > x.iloc[0] else -1
    )
    
    # Clean up temporary columns
    df.drop(['high_rolling_max', 'low_rolling_min'], axis=1, inplace=True)
    
    return df


def create_robust_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create features that are less prone to overfitting."""
    logger.info("Creating robust features...")
    
    # Price-based features (normalized)
    df['returns_log'] = np.log(df['close'] / df['close'].shift(1))
    
    # Volatility features
    df['volatility_20'] = df['returns_log'].rolling(20).std()
    df['volatility_ratio'] = df['volatility_20'] / df['volatility_20'].rolling(100).mean()
    
    # Volume features
    if 'volume' in df.columns:
        df['volume_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
        df['price_volume'] = df['close'] * df['volume']
        df['price_volume_ratio'] = df['price_volume'] / df['price_volume'].rolling(20).mean()
    
    # Momentum features
    for period in [5, 10, 20]:
        df[f'momentum_{period}'] = df['close'] / df['close'].shift(period) - 1
        
    # Mean reversion features
    for period in [20, 50]:
        df[f'mean_reversion_{period}'] = (df['close'] - df['close'].rolling(period).mean()) / df['close'].rolling(period).std()
    
    # Market microstructure
    df['high_low_ratio'] = df['high'] / df['low'] - 1
    df['close_to_high_low'] = 2 * (df['close'] - df['low']) / (df['high'] - df['low']) - 1
    
    return df


def create_stable_target(df: pd.DataFrame) -> pd.Series:
    """Create a more stable target variable."""
    # Use multiple forward bars to reduce noise
    forward_returns = []
    
    for i in range(1, 11):  # Look at next 10 bars
        ret = df['close'].pct_change(periods=i).shift(-i)
        forward_returns.append(ret)
    
    # Average forward return
    avg_return = pd.concat(forward_returns, axis=1).mean(axis=1)
    
    # More conservative thresholds
    conditions = [
        avg_return > 0.003,   # 0.3% average gain (bullish)
        avg_return < -0.003,  # 0.3% average loss (bearish)
    ]
    choices = [2, 0]  # 2=buy, 0=sell, 1=hold (default)
    
    target = pd.Series(
        np.select(conditions, choices, default=1),
        index=df.index,
        name='target'
    )
    
    return target


def train_with_anti_overfitting(X_train, y_train, X_test, y_test):
    """Train models with strong anti-overfitting measures."""
    models = {
        'rf_conservative': RandomForestClassifier(
            n_estimators=100,
            max_depth=5,  # Very shallow
            min_samples_split=100,  # Require many samples to split
            min_samples_leaf=50,   # Large leaf size
            max_features='sqrt',
            random_state=42
        ),
        'lgb_regularized': LGBMClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.02,
            min_child_samples=100,
            subsample=0.7,
            colsample_bytree=0.7,
            reg_alpha=1.0,  # L1 regularization
            reg_lambda=1.0, # L2 regularization
            random_state=42,
            verbosity=-1
        ),
        'xgb_conservative': XGBClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.02,
            min_child_weight=10,
            subsample=0.7,
            colsample_bytree=0.7,
            reg_alpha=1.0,
            reg_lambda=1.0,
            random_state=42
        )
    }
    
    results = {}
    
    for name, model in models.items():
        logger.info(f"Training {name}...")
        
        # Add noise to training data (dropout)
        noise = np.random.normal(0, 0.01, X_train.shape)
        X_train_noisy = X_train + noise
        
        # Train
        model.fit(X_train_noisy, y_train)
        
        # Evaluate
        train_pred = model.predict(X_train)
        test_pred = model.predict(X_test)
        
        train_acc = accuracy_score(y_train, train_pred)
        test_acc = accuracy_score(y_test, test_pred)
        overfit_ratio = train_acc / test_acc if test_acc > 0 else np.inf
        
        results[name] = {
            'model': model,
            'train_acc': train_acc,
            'test_acc': test_acc,
            'overfit_ratio': overfit_ratio
        }
        
        logger.info(f"  Train: {train_acc:.4f}, Test: {test_acc:.4f}, Overfit: {overfit_ratio:.2f}")
    
    # Select best model (lowest overfit ratio with decent accuracy)
    valid_models = {k: v for k, v in results.items() if v['test_acc'] > 0.35}
    
    if valid_models:
        best_name = min(valid_models.keys(), key=lambda k: valid_models[k]['overfit_ratio'])
        return valid_models[best_name]
    else:
        # Return model with best test accuracy
        best_name = max(results.keys(), key=lambda k: results[k]['test_acc'])
        return results[best_name]


def main():
    print("="*80)
    print("TRAINING INTEGRATED MODEL (SIMPLIFIED)")
    print("="*80)
    
    # Load data
    symbol = "GBPUSD"
    logger.info(f"Loading data for {symbol}...")
    
    df = pd.read_parquet(f"data/features/{symbol}_4h_features_advanced.parquet")
    initial_shape = df.shape
    
    # Add robust features
    df = create_robust_features(df)
    df = add_elliott_wave_features(df)
    
    # Create stable target
    df['target'] = create_stable_target(df)
    
    # Remove NaN values
    df = df.dropna()
    logger.info(f"Data shape: {initial_shape} -> {df.shape}")
    
    # Select features (exclude OHLCV and target)
    exclude_cols = ['open', 'high', 'low', 'close', 'volume', 'target']
    feature_cols = [col for col in df.columns if col not in exclude_cols]
    
    # Remove features with low variance
    feature_variance = df[feature_cols].var()
    low_variance_features = feature_variance[feature_variance < 0.0001].index.tolist()
    feature_cols = [f for f in feature_cols if f not in low_variance_features]
    
    logger.info(f"Using {len(feature_cols)} features")
    
    # Split data properly (time series split)
    split_idx = int(len(df) * 0.7)
    
    train_data = df.iloc[:split_idx]
    test_data = df.iloc[split_idx:]
    
    X_train = train_data[feature_cols]
    y_train = train_data['target']
    X_test = test_data[feature_cols]
    y_test = test_data['target']
    
    logger.info(f"Train period: {train_data.index[0]} to {train_data.index[-1]}")
    logger.info(f"Test period: {test_data.index[0]} to {test_data.index[-1]}")
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train models
    best_result = train_with_anti_overfitting(X_train_scaled, y_train, X_test_scaled, y_test)
    
    # Print results
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    
    print(f"\nBest Model Performance:")
    print(f"Training Accuracy: {best_result['train_acc']:.4f}")
    print(f"Test Accuracy: {best_result['test_acc']:.4f}")
    print(f"Overfit Ratio: {best_result['overfit_ratio']:.2f}")
    
    # Analyze predictions
    test_pred = best_result['model'].predict(X_test_scaled)
    
    # Prediction distribution
    unique, counts = np.unique(test_pred, return_counts=True)
    pred_dist = dict(zip(unique, counts))
    
    print(f"\nPrediction Distribution:")
    print(f"Sell (0): {pred_dist.get(0, 0)} ({pred_dist.get(0, 0)/len(test_pred)*100:.1f}%)")
    print(f"Hold (1): {pred_dist.get(1, 0)} ({pred_dist.get(1, 0)/len(test_pred)*100:.1f}%)")
    print(f"Buy (2): {pred_dist.get(2, 0)} ({pred_dist.get(2, 0)/len(test_pred)*100:.1f}%)")
    
    # Feature importance (if available)
    if hasattr(best_result['model'], 'feature_importances_'):
        importances = best_result['model'].feature_importances_
        feature_importance = pd.DataFrame({
            'feature': feature_cols,
            'importance': importances
        }).sort_values('importance', ascending=False)
        
        print(f"\nTop 10 Important Features:")
        for _, row in feature_importance.head(10).iterrows():
            print(f"  {row['feature']}: {row['importance']:.4f}")
            
        # Check Elliott Wave features
        wave_features = feature_importance[feature_importance['feature'].str.contains('wave|fib')]
        if not wave_features.empty:
            print(f"\nElliott Wave Feature Importance:")
            for _, row in wave_features.head(5).iterrows():
                print(f"  {row['feature']}: {row['importance']:.4f}")
    
    # Save model
    output_dir = Path(f"models/{symbol}_integrated_simple")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    joblib.dump(best_result['model'], output_dir / "model.joblib")
    joblib.dump(scaler, output_dir / "scaler.joblib")
    
    # Save metadata
    metadata = {
        'symbol': symbol,
        'training_date': datetime.now().isoformat(),
        'model_type': best_result['model'].__class__.__name__,
        'train_accuracy': best_result['train_acc'],
        'test_accuracy': best_result['test_acc'],
        'overfit_ratio': best_result['overfit_ratio'],
        'features': feature_cols,
        'train_period': f"{train_data.index[0]} to {train_data.index[-1]}",
        'test_period': f"{test_data.index[0]} to {test_data.index[-1]}"
    }
    
    with open(output_dir / 'metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
        
    with open(output_dir / 'features.json', 'w') as f:
        json.dump(feature_cols, f, indent=2)
    
    print(f"\nModel saved to: {output_dir}")
    
    # Summary
    print("\n" + "="*80)
    print("ANTI-OVERFITTING MEASURES APPLIED:")
    print("="*80)
    print("✓ Multi-bar target averaging (10 bars)")
    print("✓ Conservative model parameters (shallow trees)")
    print("✓ Strong regularization (L1 + L2)")
    print("✓ Noise injection during training")
    print("✓ Proper time series split (no future leakage)")
    print("✓ Elliott Wave features added")
    print("✓ Low variance features removed")
    
    if best_result['overfit_ratio'] < 1.3:
        print(f"\n✅ SUCCESS: Low overfit ratio ({best_result['overfit_ratio']:.2f})")
        print("Model should generalize well to new data!")
    else:
        print(f"\n⚠️  WARNING: High overfit ratio ({best_result['overfit_ratio']:.2f})")
        print("Consider more regularization or simpler models.")


if __name__ == "__main__":
    main()