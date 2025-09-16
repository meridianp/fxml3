#!/usr/bin/env python
"""Fast training of ML models on a single symbol."""

import argparse
import logging
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from typing import Dict, Tuple
import joblib
import json
from datetime import datetime

# Sklearn imports
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, accuracy_score
from sklearn.ensemble import RandomForestClassifier

# XGBoost and LightGBM
import xgboost as xgb
import lightgbm as lgb

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_labels(df: pd.DataFrame, threshold: float = 0.0001) -> pd.Series:
    """Create classification labels based on future returns."""
    # Calculate forward returns (next 4-hour bar)
    future_returns = df['close'].pct_change().shift(-1)
    
    # Create labels: -1 (sell), 0 (hold), 1 (buy)
    labels = pd.Series(index=df.index, dtype=int)
    labels[future_returns > threshold] = 1  # Buy signal
    labels[future_returns < -threshold] = -1  # Sell signal
    labels[(future_returns >= -threshold) & (future_returns <= threshold)] = 0  # Hold
    
    return labels


def prepare_data(symbol: str) -> Tuple[pd.DataFrame, pd.Series]:
    """Load and prepare data for training."""
    features_dir = Path(__file__).parent.parent / 'data' / 'features'
    features_file = features_dir / f'{symbol}_4h_features_advanced.parquet'
    
    logger.info(f"Loading features from {features_file}")
    df = pd.read_parquet(features_file)
    
    # Create labels
    labels = create_labels(df)
    
    # Remove last row (no future return)
    df = df[:-1]
    labels = labels[:-1]
    
    # Remove any remaining NaN values
    valid_idx = ~(df.isnull().any(axis=1) | labels.isnull())
    df = df[valid_idx]
    labels = labels[valid_idx]
    
    logger.info(f"Data shape: {df.shape}")
    logger.info(f"Label distribution: Buy={sum(labels==1)}, Hold={sum(labels==0)}, Sell={sum(labels==-1)}")
    
    return df, labels


def get_feature_columns(df: pd.DataFrame) -> list:
    """Get feature columns excluding price data."""
    exclude_cols = ['open', 'high', 'low', 'close', 'volume']
    return [col for col in df.columns if col not in exclude_cols]


def train_models(X_train, y_train, X_test, y_test) -> Dict:
    """Train all models with fixed parameters for speed."""
    results = {}
    
    # Random Forest
    logger.info("Training Random Forest...")
    rf = RandomForestClassifier(
        n_estimators=100,
        max_depth=20,
        min_samples_split=5,
        random_state=42,
        n_jobs=-1
    )
    rf.fit(X_train, y_train)
    y_pred_rf = rf.predict(X_test)
    
    results['random_forest'] = {
        'model': rf,
        'accuracy': accuracy_score(y_test, y_pred_rf),
        'classification_report': classification_report(y_test, y_pred_rf, output_dict=True),
        'predictions': y_pred_rf,
        'feature_importance': dict(zip(X_train.columns, rf.feature_importances_))
    }
    logger.info(f"Random Forest accuracy: {results['random_forest']['accuracy']:.4f}")
    
    # XGBoost
    logger.info("Training XGBoost...")
    xgb_model = xgb.XGBClassifier(
        max_depth=5,
        learning_rate=0.05,
        n_estimators=100,
        objective='multi:softprob',
        num_class=3,
        random_state=42,
        n_jobs=-1,
        use_label_encoder=False,
        eval_metric='mlogloss'
    )
    # Convert labels for XGBoost
    y_train_xgb = y_train + 1
    y_test_xgb = y_test + 1
    xgb_model.fit(X_train, y_train_xgb)
    y_pred_xgb = xgb_model.predict(X_test) - 1
    
    results['xgboost'] = {
        'model': xgb_model,
        'accuracy': accuracy_score(y_test, y_pred_xgb),
        'classification_report': classification_report(y_test, y_pred_xgb, output_dict=True),
        'predictions': y_pred_xgb,
        'feature_importance': xgb_model.get_booster().get_score(importance_type='gain')
    }
    logger.info(f"XGBoost accuracy: {results['xgboost']['accuracy']:.4f}")
    
    # LightGBM
    logger.info("Training LightGBM...")
    lgb_model = lgb.LGBMClassifier(
        num_leaves=31,
        learning_rate=0.05,
        n_estimators=100,
        objective='multiclass',
        num_class=3,
        random_state=42,
        n_jobs=-1,
        verbosity=-1
    )
    # Convert labels for LightGBM
    lgb_model.fit(X_train, y_train_xgb)
    y_pred_lgb = lgb_model.predict(X_test) - 1
    
    results['lightgbm'] = {
        'model': lgb_model,
        'accuracy': accuracy_score(y_test, y_pred_lgb),
        'classification_report': classification_report(y_test, y_pred_lgb, output_dict=True),
        'predictions': y_pred_lgb,
        'feature_importance': dict(zip(X_train.columns, lgb_model.feature_importances_))
    }
    logger.info(f"LightGBM accuracy: {results['lightgbm']['accuracy']:.4f}")
    
    return results


def evaluate_and_save(symbol: str, results: Dict, scaler: StandardScaler) -> None:
    """Evaluate models and save results."""
    logger.info("\n" + "="*60)
    logger.info("MODEL COMPARISON")
    logger.info("="*60)
    
    # Find best model
    best_model = max(results.items(), key=lambda x: x[1]['accuracy'])
    
    for model_name, result in results.items():
        is_best = model_name == best_model[0]
        logger.info(f"\n{model_name.upper()} {'[BEST]' if is_best else ''}")
        logger.info(f"Accuracy: {result['accuracy']:.4f}")
        
        # Classification report summary
        report = result['classification_report']
        logger.info(f"Macro avg F1-score: {report['macro avg']['f1-score']:.3f}")
        
        # Top 5 features
        if result['feature_importance']:
            logger.info("Top 5 features:")
            sorted_features = sorted(result['feature_importance'].items(), 
                                   key=lambda x: x[1], reverse=True)[:5]
            for i, (feat, imp) in enumerate(sorted_features, 1):
                logger.info(f"  {i}. {feat}: {imp:.4f}")
    
    # Save models
    output_dir = Path(__file__).parent.parent / 'models' / symbol
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save best model
    best_model_file = output_dir / f'best_model_{best_model[0]}.joblib'
    joblib.dump(best_model[1]['model'], best_model_file)
    logger.info(f"\nSaved best model to {best_model_file}")
    
    # Save scaler
    scaler_file = output_dir / 'scaler.joblib'
    joblib.dump(scaler, scaler_file)
    
    # Save metadata
    metadata = {
        'symbol': symbol,
        'training_date': datetime.now().isoformat(),
        'best_model': best_model[0],
        'best_accuracy': best_model[1]['accuracy'],
        'all_accuracies': {k: v['accuracy'] for k, v in results.items()}
    }
    
    metadata_file = output_dir / 'training_metadata.json'
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    logger.info(f"Training complete! Best model: {best_model[0]} ({best_model[1]['accuracy']:.4f})")


def main():
    parser = argparse.ArgumentParser(description='Fast ML training on single symbol')
    parser.add_argument('--symbol', type=str, default='GBPUSD', help='Trading symbol')
    parser.add_argument('--test-size', type=float, default=0.2, help='Test set size')
    args = parser.parse_args()
    
    # Load data
    df, labels = prepare_data(args.symbol)
    
    # Get feature columns
    feature_cols = get_feature_columns(df)
    X = df[feature_cols]
    y = labels
    
    # Train/test split (time-based)
    split_idx = int(len(X) * (1 - args.test_size))
    X_train = X[:split_idx]
    X_test = X[split_idx:]
    y_train = y[:split_idx]
    y_test = y[split_idx:]
    
    logger.info(f"Training set: {X_train.shape}")
    logger.info(f"Test set: {X_test.shape}")
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = pd.DataFrame(
        scaler.fit_transform(X_train),
        columns=X_train.columns,
        index=X_train.index
    )
    X_test_scaled = pd.DataFrame(
        scaler.transform(X_test),
        columns=X_test.columns,
        index=X_test.index
    )
    
    # Train models
    results = train_models(X_train_scaled, y_train, X_test_scaled, y_test)
    
    # Evaluate and save
    evaluate_and_save(args.symbol, results, scaler)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())