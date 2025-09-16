#!/usr/bin/env python
"""Retrain EURUSD model with balanced predictions to fix the positive bias issue."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import json
import warnings
from datetime import datetime

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")


class BalancedEURUSDTrainer:
    """Retrain EURUSD with balanced target distribution."""

    def __init__(self):
        self.symbol = "EURUSD"
        self.models = {}
        self.scalers = {}
        self.features = []
        self.h4_data_dir = Path("data/h4_processed")
        self.model_dir = Path("models/h4_models")

    def load_and_analyze_data(self):
        """Load data and analyze target distribution."""
        data_file = self.h4_data_dir / f"{self.symbol}_h4_features.parquet"

        if not data_file.exists():
            raise FileNotFoundError(f"No 4-hour data found for {self.symbol}")

        # Load data
        df = pd.read_parquet(data_file)

        print(f"Loaded {len(df)} 4-hour bars for {self.symbol}")
        print(f"\nOriginal target distribution:")
        print(f"  Mean: {df['target'].mean():.6f}")
        print(f"  Std: {df['target'].std():.6f}")
        print(f"  Min: {df['target'].min():.6f}")
        print(f"  Max: {df['target'].max():.6f}")
        print(f"  Skewness: {df['target'].skew():.3f}")

        # Check for bias
        positive_pct = (df["target"] > 0).mean()
        print(f"\n  Positive targets: {positive_pct:.1%}")
        print(f"  Negative targets: {(df['target'] < 0).mean():.1%}")

        return df

    def create_balanced_target(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create a more balanced target variable."""
        # Instead of using raw returns, create a detrended target
        # This helps when there's a long-term trend causing bias

        # Calculate returns if not present
        if "returns" not in df.columns:
            df["returns"] = df["close"].pct_change()

        # Use a rolling mean to detrend
        window = 120  # 20 days for 4H bars
        df["returns_ma"] = df["returns"].rolling(window=window, min_periods=30).mean()
        df["returns_detrended"] = df["returns"] - df["returns_ma"]

        # Create balanced target - predict detrended returns
        df["target_balanced"] = df["returns_detrended"].shift(
            -1
        )  # Next bar's detrended return

        # Drop NaN values
        df = df.dropna(subset=["target_balanced"])

        print(f"\nBalanced target distribution:")
        print(f"  Mean: {df['target_balanced'].mean():.6f}")
        print(f"  Std: {df['target_balanced'].std():.6f}")
        print(f"  Min: {df['target_balanced'].min():.6f}")
        print(f"  Max: {df['target_balanced'].max():.6f}")
        print(f"  Skewness: {df['target_balanced'].skew():.3f}")

        positive_pct = (df["target_balanced"] > 0).mean()
        print(f"\n  Positive targets: {positive_pct:.1%}")
        print(f"  Negative targets: {(df['target_balanced'] < 0).mean():.1%}")

        return df

    def train_balanced_models(self, df: pd.DataFrame):
        """Train models with balanced target."""

        # Use balanced target
        df["target"] = df["target_balanced"]

        # Split data - 80/20 train/test
        split_idx = int(len(df) * 0.8)
        train_df = df.iloc[:split_idx]
        test_df = df.iloc[split_idx:]

        # Separate features and target
        feature_cols = [
            col
            for col in df.columns
            if col
            not in [
                "target",
                "target_balanced",
                "returns",
                "returns_ma",
                "returns_detrended",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ]
        ]
        self.features = feature_cols

        X_train = train_df[feature_cols]
        y_train = train_df["target"]
        X_test = test_df[feature_cols]
        y_test = test_df["target"]

        print(f"\nTraining balanced models for {self.symbol}...")
        print(f"  Train: {len(X_train)} samples")
        print(f"  Test: {len(X_test)} samples")
        print(f"  Features: {len(feature_cols)}")

        results = {}

        # 1. Random Forest
        print("\n1. Random Forest...")
        rf = RandomForestRegressor(
            n_estimators=300,
            max_depth=12,
            min_samples_split=50,
            min_samples_leaf=20,
            max_features="sqrt",
            random_state=42,
            n_jobs=-1,
        )
        rf.fit(X_train, y_train)
        self.models["random_forest"] = rf

        # Evaluate
        train_pred = rf.predict(X_train)
        test_pred = rf.predict(X_test)
        results["random_forest"] = self.evaluate_predictions(
            y_train, train_pred, y_test, test_pred
        )

        # 2. XGBoost
        print("\n2. XGBoost...")
        xgb_params = {
            "n_estimators": 2000,
            "max_depth": 6,
            "learning_rate": 0.01,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "gamma": 0.1,
            "random_state": 42,
            "n_jobs": -1,
            "early_stopping_rounds": 100,
            "eval_metric": "rmse",
        }

        xgb_model = xgb.XGBRegressor(**xgb_params)
        xgb_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
        self.models["xgboost"] = xgb_model

        # Evaluate
        train_pred = xgb_model.predict(X_train)
        test_pred = xgb_model.predict(X_test)
        results["xgboost"] = self.evaluate_predictions(
            y_train, train_pred, y_test, test_pred
        )

        # 3. LightGBM
        print("\n3. LightGBM...")
        lgb_params = {
            "n_estimators": 2000,
            "max_depth": 6,
            "learning_rate": 0.01,
            "num_leaves": 31,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
            "n_jobs": -1,
            "verbosity": -1,
        }

        lgb_model = lgb.LGBMRegressor(**lgb_params)
        lgb_model.fit(
            X_train,
            y_train,
            eval_set=[(X_test, y_test)],
            callbacks=[lgb.early_stopping(100), lgb.log_evaluation(0)],
        )
        self.models["lightgbm"] = lgb_model

        # Evaluate
        train_pred = lgb_model.predict(X_train)
        test_pred = lgb_model.predict(X_test)
        results["lightgbm"] = self.evaluate_predictions(
            y_train, train_pred, y_test, test_pred
        )

        # 4. Create ensemble based on test performance
        print("\n4. Creating ensemble...")
        best_model_name = max(
            results.keys(), key=lambda x: results[x]["test_direction_accuracy"]
        )
        best_model = self.models[best_model_name]

        print(f"  Best model: {best_model_name}")
        self.models["ensemble"] = best_model

        # No scaling needed for tree models
        self.scalers = {"ensemble": None}

        # Store results
        self.training_results = results

        return results

    def evaluate_predictions(self, y_train, train_pred, y_test, test_pred):
        """Evaluate model predictions with 4H-specific metrics."""

        # Check prediction distribution
        pred_positive_pct = (test_pred > 0).mean()

        # Direction accuracy
        train_direction = np.sign(y_train) == np.sign(train_pred)
        test_direction = np.sign(y_test) == np.sign(test_pred)

        # Signal accuracy with 4H threshold
        threshold = 0.00005  # 0.5 basis points
        train_signals = (np.abs(train_pred) > threshold).astype(int)
        test_signals = (np.abs(test_pred) > threshold).astype(int)

        train_signal_acc = (train_signals == (np.abs(y_train) > threshold)).mean()
        test_signal_acc = (test_signals == (np.abs(y_test) > threshold)).mean()

        results = {
            "train_r2": r2_score(y_train, train_pred),
            "test_r2": r2_score(y_test, test_pred),
            "train_mae": mean_absolute_error(y_train, train_pred),
            "test_mae": mean_absolute_error(y_test, test_pred),
            "train_direction_accuracy": train_direction.mean(),
            "test_direction_accuracy": test_direction.mean(),
            "train_signal_accuracy": train_signal_acc,
            "test_signal_accuracy": test_signal_acc,
            "test_pred_positive_pct": pred_positive_pct,
            "test_signals_per_day": (np.abs(test_pred) > threshold).mean() * 6,
        }

        print(f"  Test direction accuracy: {results['test_direction_accuracy']:.1%}")
        print(f"  Test signal accuracy: {results['test_signal_accuracy']:.1%}")
        print(f"  Test predictions positive: {pred_positive_pct:.1%}")
        print(f"  Test signals per day: {results['test_signals_per_day']:.1f}")

        return results

    def save_models(self):
        """Save the retrained models."""

        # Prepare model data
        model_data = {
            "models": self.models,
            "scalers": self.scalers,
            "selected_features": self.features,
            "training_results": self.training_results,
            "training_date": datetime.now().isoformat(),
            "timeframe": "4H",
            "balanced_training": True,
        }

        # Save models
        model_file = self.model_dir / f"{self.symbol}_h4_models.joblib"
        joblib.dump(model_data, model_file)
        print(f"\n✅ Saved balanced model to {model_file}")

        # Save features
        feature_file = self.model_dir / f"{self.symbol}_h4_features.json"
        with open(feature_file, "w") as f:
            json.dump(
                {
                    "features": self.features,
                    "n_features": len(self.features),
                    "training_date": datetime.now().isoformat(),
                },
                f,
                indent=2,
            )

        print(f"✅ Saved features to {feature_file}")


def main():
    """Retrain EURUSD with balanced predictions."""
    print("=" * 80)
    print("RETRAINING EURUSD WITH BALANCED PREDICTIONS")
    print("=" * 80)

    trainer = BalancedEURUSDTrainer()

    # Load and analyze data
    df = trainer.load_and_analyze_data()

    # Create balanced target
    df = trainer.create_balanced_target(df)

    # Train models
    results = trainer.train_balanced_models(df)

    # Save models
    trainer.save_models()

    print("\n" + "=" * 80)
    print("RETRAINING COMPLETE")
    print("=" * 80)

    # Summary
    print("\nModel Performance Summary:")
    for model_name, metrics in results.items():
        print(f"\n{model_name}:")
        print(f"  Direction accuracy: {metrics['test_direction_accuracy']:.1%}")
        print(f"  Signal accuracy: {metrics['test_signal_accuracy']:.1%}")
        print(
            f"  Predictions balanced: {abs(metrics['test_pred_positive_pct'] - 0.5) < 0.1}"
        )


if __name__ == "__main__":
    main()
