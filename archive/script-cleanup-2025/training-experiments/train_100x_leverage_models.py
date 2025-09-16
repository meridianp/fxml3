#!/usr/bin/env python
"""Train ML models optimized for 100:1 leverage trading with micro lots."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import joblib
import json
import warnings
warnings.filterwarnings('ignore')

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_class_weight

class Leverage100XModelTrainer:
    """Train models specifically for 100:1 leverage trading."""
    
    def __init__(self):
        
        # Optimized for 100:1 leverage
        self.target_threshold = 0.0003  # 3 pips for micro lots (was 5 pips)
        self.min_holding_bars = 2       # Minimum 2 bars (8 hours)
        self.max_holding_bars = 6       # Maximum 6 bars (24 hours)
        
        # Feature selection for high-frequency trading
        self.selected_features = [
            # Price action
            'returns_1', 'returns_2', 'returns_4', 'returns_8',
            'log_returns_1', 'log_returns_2', 'log_returns_4',
            
            # Volatility (critical for position sizing)
            'volatility_8', 'volatility_12', 'volatility_24',
            'atr_10', 'atr_20',
            
            # Momentum
            'rsi_8', 'rsi_14', 'rsi_21',
            'macd_signal', 'macd_histogram',
            'stoch_k', 'stoch_d',
            
            # Trend
            'sma_8', 'sma_20', 'sma_50',
            'ema_8', 'ema_20',
            'adx_14', 'trend_strength_20',
            
            # Market structure  
            'bb_position', 'bb_width',
            'support_distance', 'resistance_distance',
            
            # Volume/Activity
            'volume_ratio', 'volume_trend',
            
            # Time features (for session trading)
            'hour', 'day_of_week',
            'is_london_session', 'is_ny_session', 'is_asian_session',
            
            # Microstructure
            'spread_ratio', 'high_low_ratio'
        ]
    
    def create_session_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add session-based features for optimal trading times."""
        df['hour'] = df.index.hour
        df['day_of_week'] = df.index.dayofweek
        
        # Trading sessions (UTC)
        df['is_asian_session'] = ((df['hour'] >= 23) | (df['hour'] < 8)).astype(int)
        df['is_london_session'] = ((df['hour'] >= 8) & (df['hour'] < 16)).astype(int)
        df['is_ny_session'] = ((df['hour'] >= 16) & (df['hour'] < 23)).astype(int)
        
        # Best hours from backtest (20:00, 08:00, 04:00)
        df['is_prime_hour'] = df['hour'].isin([20, 8, 4, 0, 16]).astype(int)
        
        return df
    
    def create_microstructure_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add microstructure features for micro lot trading."""
        # Spread approximation (high-low as proxy)
        df['spread_ratio'] = (df['high'] - df['low']) / df['close']
        
        # High-low ratio (volatility proxy)
        df['high_low_ratio'] = df['high'] / df['low'] - 1
        
        # Price precision (important for micro lots)
        df['price_precision'] = np.log10(df['close'])
        
        return df
    
    def create_advanced_labels(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """Create labels optimized for 100:1 leverage trading."""
        
        # Adjust threshold based on symbol
        if symbol == 'USDJPY':
            threshold = self.target_threshold * 100  # JPY pairs need adjustment
        else:
            threshold = self.target_threshold
        
        # Calculate forward returns for multiple horizons
        labels = pd.DataFrame(index=df.index)
        
        for bars in range(self.min_holding_bars, self.max_holding_bars + 1):
            # Future return
            future_return = df['close'].pct_change(bars).shift(-bars)
            
            # Create ternary labels
            labels[f'label_{bars}'] = 0  # Hold/No trade
            labels.loc[future_return > threshold, f'label_{bars}'] = 1   # Long
            labels.loc[future_return < -threshold, f'label_{bars}'] = -1  # Short
            
            # Quality score (how much beyond threshold)
            labels[f'quality_{bars}'] = abs(future_return) / threshold
            labels.loc[abs(future_return) <= threshold, f'quality_{bars}'] = 0
        
        # Ensemble label (majority vote)
        label_cols = [col for col in labels.columns if col.startswith('label_')]
        labels['ensemble_label'] = labels[label_cols].mode(axis=1)[0]
        
        # Average quality
        quality_cols = [col for col in labels.columns if col.startswith('quality_')]
        labels['avg_quality'] = labels[quality_cols].mean(axis=1)
        
        # Final label with quality threshold
        labels['label'] = labels['ensemble_label']
        labels.loc[labels['avg_quality'] < 1.5, 'label'] = 0  # Require 50% beyond threshold
        
        return labels
    
    def prepare_training_data(self, symbol: str, start_date: str, end_date: str):
        """Prepare data for training."""
        print(f"\nPreparing data for {symbol}...")
        
        # Load 4H data
        file_pattern = f'data/processed/4h/{symbol}_4H_features_*.parquet'
        import glob
        files = sorted(glob.glob(file_pattern))
        
        if not files:
            print(f"No 4H data found for {symbol}")
            return None, None, None
        
        # Load and concatenate
        dfs = []
        for file in files:
            df = pd.read_parquet(file)
            dfs.append(df)
        
        df = pd.concat(dfs, axis=0).sort_index()
        
        # Filter date range
        df = df[(df.index >= start_date) & (df.index <= end_date)]
        
        if len(df) < 500:
            print(f"Insufficient data for {symbol}: {len(df)} bars")
            return None, None, None
        
        # Add session features
        df = self.create_session_features(df)
        
        # Add microstructure features
        df = self.create_microstructure_features(df)
        
        # Create labels
        labels = self.create_advanced_labels(df, symbol)
        
        # Align data and labels
        common_idx = df.index.intersection(labels.index)
        df = df.loc[common_idx]
        labels = labels.loc[common_idx]
        
        # Select features
        available_features = [f for f in self.selected_features if f in df.columns]
        X = df[available_features]
        y = labels['label']
        
        # Remove NaN
        mask = ~(X.isna().any(axis=1) | y.isna())
        X = X[mask]
        y = y[mask]
        labels = labels[mask]
        
        print(f"  Data shape: {X.shape}")
        print(f"  Label distribution: {y.value_counts().to_dict()}")
        print(f"  Date range: {X.index[0]} to {X.index[-1]}")
        
        return X, y, labels
    
    def train_ensemble_model(self, X_train, y_train, X_val, y_val):
        """Train ensemble of models for robustness."""
        
        # Calculate class weights for imbalanced data
        classes = np.unique(y_train)
        class_weights = compute_class_weight('balanced', classes=classes, y=y_train)
        class_weight_dict = dict(zip(classes, class_weights))
        
        models = {
            'rf': RandomForestClassifier(
                n_estimators=200,
                max_depth=8,
                min_samples_split=50,
                min_samples_leaf=20,
                class_weight=class_weight_dict,
                random_state=42,
                n_jobs=-1
            ),
            'gb': GradientBoostingClassifier(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.05,
                subsample=0.8,
                random_state=42
            ),
            'lr': LogisticRegression(
                class_weight=class_weight_dict,
                C=0.1,
                max_iter=1000,
                random_state=42
            )
        }
        
        # Train models
        trained_models = {}
        predictions = {}
        
        for name, model in models.items():
            print(f"    Training {name}...")
            model.fit(X_train, y_train)
            trained_models[name] = model
            
            # Predictions
            pred = model.predict(X_val)
            predictions[name] = pred
            
            # Metrics
            acc = accuracy_score(y_val, pred)
            
            # Precision for each class
            if len(np.unique(y_val)) > 2:
                # Multiclass precision
                prec_per_class = precision_score(y_val, pred, average=None, zero_division=0)
                # Find precision for long (1) and short (-1)
                unique_classes = np.unique(y_val)
                long_prec = prec_per_class[np.where(unique_classes == 1)[0][0]] if 1 in unique_classes else 0
                short_prec = prec_per_class[np.where(unique_classes == -1)[0][0]] if -1 in unique_classes else 0
            else:
                # Binary precision
                if sum(y_val == 1) > 0:
                    long_mask = (y_val == 1) | (y_val == 0)
                    long_prec = precision_score(y_val[long_mask] == 1, pred[long_mask] == 1, zero_division=0)
                else:
                    long_prec = 0
                    
                if sum(y_val == -1) > 0:
                    short_mask = (y_val == -1) | (y_val == 0)
                    short_prec = precision_score(y_val[short_mask] == -1, pred[short_mask] == -1, zero_division=0)
                else:
                    short_prec = 0
            
            print(f"      Accuracy: {acc:.3f}, Long Prec: {long_prec:.3f}, Short Prec: {short_prec:.3f}")
        
        # Ensemble prediction (majority vote)
        ensemble_pred = np.zeros_like(predictions['rf'])
        for pred in predictions.values():
            ensemble_pred += pred
        ensemble_pred = np.sign(ensemble_pred)
        
        # Ensemble metrics
        ensemble_acc = accuracy_score(y_val, ensemble_pred)
        print(f"    Ensemble Accuracy: {ensemble_acc:.3f}")
        
        return trained_models, ensemble_acc
    
    def train_symbol(self, symbol: str):
        """Train models for a single symbol."""
        print(f"\n{'='*60}")
        print(f"Training {symbol} for 100:1 Leverage Trading")
        print(f"{'='*60}")
        
        # Date ranges
        train_start = '2024-01-01'
        train_end = '2024-06-30'
        val_start = '2024-07-01'
        val_end = '2024-08-31'
        
        # Prepare data
        X, y, labels = self.prepare_training_data(symbol, train_start, val_end)
        
        if X is None:
            print(f"Failed to prepare data for {symbol}")
            return None
        
        # Split data
        train_mask = X.index < val_start
        X_train = X[train_mask]
        y_train = y[train_mask]
        X_val = X[~train_mask]
        y_val = y[~train_mask]
        
        print(f"\nTraining set: {len(X_train)} samples")
        print(f"Validation set: {len(X_val)} samples")
        
        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_val_scaled = scaler.transform(X_val)
        
        # Train ensemble
        models, accuracy = self.train_ensemble_model(
            X_train_scaled, y_train, X_val_scaled, y_val
        )
        
        # Feature importance (from RF)
        rf_model = models['rf']
        importance = pd.DataFrame({
            'feature': X_train.columns,
            'importance': rf_model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        print("\nTop 10 Important Features:")
        print(importance.head(10))
        
        # Save models
        model_dir = Path(f'models/{symbol}_100x_leverage')
        model_dir.mkdir(parents=True, exist_ok=True)
        
        # Save ensemble models
        for name, model in models.items():
            joblib.dump(model, model_dir / f'{name}_model.pkl')
        
        # Save scaler
        joblib.dump(scaler, model_dir / 'scaler.pkl')
        
        # Save config
        config = {
            'symbol': symbol,
            'accuracy': float(accuracy),
            'features': list(X_train.columns),
            'train_samples': len(X_train),
            'val_samples': len(X_val),
            'train_period': f"{train_start} to {train_end}",
            'val_period': f"{val_start} to {val_end}",
            'target_threshold': self.target_threshold,
            'leverage': 100,
            'model_type': 'ensemble',
            'trained_at': datetime.now().isoformat()
        }
        
        with open(model_dir / 'config.json', 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"\n✅ Models saved to {model_dir}")
        
        return accuracy
    
    def analyze_predictions(self, symbol: str):
        """Analyze model predictions for insights."""
        print(f"\nAnalyzing predictions for {symbol}...")
        
        # Load test data
        test_start = '2024-09-01'
        test_end = '2024-12-31'
        
        X, y, labels = self.prepare_training_data(symbol, test_start, test_end)
        if X is None:
            return
        
        # Load models
        model_dir = Path(f'models/{symbol}_100x_leverage')
        if not model_dir.exists():
            print(f"No models found for {symbol}")
            return
        
        scaler = joblib.load(model_dir / 'scaler.pkl')
        rf_model = joblib.load(model_dir / 'rf_model.pkl')
        
        # Scale and predict
        X_scaled = scaler.transform(X)
        predictions = rf_model.predict(X_scaled)
        probabilities = rf_model.predict_proba(X_scaled)
        
        # Analysis by session
        results = pd.DataFrame({
            'hour': X.index.hour,
            'prediction': predictions,
            'actual': y,
            'correct': predictions == y
        })
        
        print("\nAccuracy by Trading Session:")
        print(f"Asian (23-8 UTC): {results[results['hour'].isin(range(23,24)) | results['hour'].isin(range(0,8))]['correct'].mean():.3f}")
        print(f"London (8-16 UTC): {results[results['hour'].isin(range(8,16))]['correct'].mean():.3f}")
        print(f"NY (16-23 UTC): {results[results['hour'].isin(range(16,23))]['correct'].mean():.3f}")
        
        # Signal distribution
        print(f"\nSignal Distribution:")
        print(f"Long signals: {sum(predictions == 1)} ({sum(predictions == 1)/len(predictions)*100:.1f}%)")
        print(f"Short signals: {sum(predictions == -1)} ({sum(predictions == -1)/len(predictions)*100:.1f}%)")
        print(f"No trade: {sum(predictions == 0)} ({sum(predictions == 0)/len(predictions)*100:.1f}%)")


def main():
    """Train models for all symbols."""
    
    symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF']
    trainer = Leverage100XModelTrainer()
    
    results = {}
    
    for symbol in symbols:
        accuracy = trainer.train_symbol(symbol)
        if accuracy:
            results[symbol] = accuracy
            trainer.analyze_predictions(symbol)
    
    # Summary
    print("\n" + "="*60)
    print("TRAINING SUMMARY")
    print("="*60)
    for symbol, acc in results.items():
        print(f"{symbol}: {acc:.3f}")
    
    print(f"\nAverage Accuracy: {np.mean(list(results.values())):.3f}")
    
    # Save summary
    with open('models/100x_leverage_training_summary.json', 'w') as f:
        json.dump({
            'results': results,
            'average_accuracy': float(np.mean(list(results.values()))),
            'trained_at': datetime.now().isoformat(),
            'leverage': 100,
            'target_pips': 3
        }, f, indent=2)

if __name__ == "__main__":
    main()