#!/usr/bin/env python3
"""
Consolidated Training Suite for FXML4
Combines functionality from multiple training scripts into a single interface.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit, train_test_split
from sklearn.preprocessing import StandardScaler

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fxml4.data.data_loader import DataLoader
from fxml4.ml.cross_validation import CrossValidation
from fxml4.ml.features import FeatureEngineer
from fxml4.ml.models import ModelTrainer
from fxml4.ml.walk_forward_optimizer import WalkForwardOptimizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConsolidatedTrainingSuite:
    """Consolidated training suite with multiple training approaches."""

    def __init__(self):
        self.training_methods = {
            "4hour_models": self.train_4hour_models,
            "all_symbols": self.train_all_symbols,
            "visual_validation": self.train_and_test_visual_validation,
            "better_models": self.train_better_models,
            "enhanced_models": self.train_enhanced_models,
            "single_symbol": self.train_single_symbol,
            "with_real_data": self.train_with_real_data,
            "unified_features": self.train_with_unified_features,
            "walk_forward": self.train_with_walk_forward,
        }

        self.model_types = {
            "rf": RandomForestRegressor,
            "gb": GradientBoostingRegressor,
            "lr": LinearRegression,
        }

    def train_4hour_models(self, symbols=None, **kwargs):
        """Train models specifically for 4-hour timeframe."""
        logger.info("Training 4-hour models")

        if symbols is None:
            symbols = ["EURUSD", "GBPUSD", "USDCHF", "USDJPY"]

        results = {}

        for symbol in symbols:
            logger.info(f"Training 4-hour model for {symbol}")

            # Load 4-hour data
            data_loader = DataLoader()
            data = data_loader.load_data(symbol, timeframe="4h")

            # Engineer features for 4-hour timeframe
            feature_engineer = FeatureEngineer(timeframe="4h")
            features = feature_engineer.engineer_features(data)

            # Train model
            model_trainer = ModelTrainer(model_type="rf", timeframe="4h")
            model_result = model_trainer.train(features, target="future_return")

            # Save model
            model_path = Path("models") / f"{symbol}_4h"
            model_path.mkdir(parents=True, exist_ok=True)

            joblib.dump(model_result["model"], model_path / "model.joblib")
            joblib.dump(model_result["scaler"], model_path / "scaler.joblib")

            with open(model_path / "metadata.json", "w") as f:
                json.dump(model_result["metadata"], f, indent=2, default=str)

            results[symbol] = model_result

        return results

    def train_all_symbols(self, model_type="rf", **kwargs):
        """Train models for all supported symbols."""
        logger.info("Training models for all symbols")

        symbols = ["EURUSD", "GBPUSD", "USDCHF", "USDJPY", "AUDUSD", "NZDUSD", "USDCAD"]
        timeframes = kwargs.get("timeframes", ["1h", "4h", "daily"])

        results = {}

        for symbol in symbols:
            results[symbol] = {}

            for timeframe in timeframes:
                logger.info(f"Training {model_type} model for {symbol} on {timeframe}")

                try:
                    # Load data
                    data_loader = DataLoader()
                    data = data_loader.load_data(symbol, timeframe=timeframe)

                    # Engineer features
                    feature_engineer = FeatureEngineer(timeframe=timeframe)
                    features = feature_engineer.engineer_features(data)

                    # Train model
                    model_trainer = ModelTrainer(
                        model_type=model_type, timeframe=timeframe
                    )
                    model_result = model_trainer.train(features, target="future_return")

                    # Save model
                    model_path = Path("models") / f"{symbol}_{timeframe}"
                    model_path.mkdir(parents=True, exist_ok=True)

                    joblib.dump(
                        model_result["model"], model_path / f"{model_type}_model.joblib"
                    )
                    joblib.dump(
                        model_result["scaler"],
                        model_path / f"{model_type}_scaler.joblib",
                    )

                    with open(model_path / f"{model_type}_metadata.json", "w") as f:
                        json.dump(model_result["metadata"], f, indent=2, default=str)

                    results[symbol][timeframe] = model_result

                except Exception as e:
                    logger.error(f"Error training {symbol} {timeframe}: {e}")
                    results[symbol][timeframe] = {"error": str(e)}

        return results

    def train_and_test_visual_validation(self, symbol, **kwargs):
        """Train models with visual validation testing."""
        logger.info(f"Training with visual validation for {symbol}")

        # Load data
        data_loader = DataLoader()
        data = data_loader.load_data(symbol, timeframe="4h")

        # Engineer features
        feature_engineer = FeatureEngineer(timeframe="4h")
        features = feature_engineer.engineer_features(data)

        # Split data for visual validation
        split_date = pd.Timestamp("2023-01-01")
        train_data = features[features.index < split_date]
        test_data = features[features.index >= split_date]

        # Train model
        model_trainer = ModelTrainer(model_type="rf", timeframe="4h")
        model_result = model_trainer.train(train_data, target="future_return")

        # Test with visual validation
        predictions = model_result["model"].predict(
            model_result["scaler"].transform(test_data.drop("future_return", axis=1))
        )

        # Generate visual validation charts
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(2, 2, figsize=(15, 10))

        # Plot 1: Predictions vs Actuals
        axes[0, 0].scatter(test_data["future_return"], predictions, alpha=0.5)
        axes[0, 0].plot(
            [test_data["future_return"].min(), test_data["future_return"].max()],
            [test_data["future_return"].min(), test_data["future_return"].max()],
            "r--",
        )
        axes[0, 0].set_xlabel("Actual Returns")
        axes[0, 0].set_ylabel("Predicted Returns")
        axes[0, 0].set_title("Predictions vs Actuals")

        # Plot 2: Time series of predictions
        axes[0, 1].plot(
            test_data.index, test_data["future_return"], label="Actual", alpha=0.7
        )
        axes[0, 1].plot(test_data.index, predictions, label="Predicted", alpha=0.7)
        axes[0, 1].set_xlabel("Date")
        axes[0, 1].set_ylabel("Returns")
        axes[0, 1].set_title("Time Series Comparison")
        axes[0, 1].legend()

        # Plot 3: Residuals
        residuals = test_data["future_return"] - predictions
        axes[1, 0].scatter(predictions, residuals, alpha=0.5)
        axes[1, 0].axhline(y=0, color="r", linestyle="--")
        axes[1, 0].set_xlabel("Predicted Returns")
        axes[1, 0].set_ylabel("Residuals")
        axes[1, 0].set_title("Residual Plot")

        # Plot 4: Feature importance
        feature_importance = model_result["model"].feature_importances_
        feature_names = test_data.drop("future_return", axis=1).columns
        sorted_idx = feature_importance.argsort()[-10:]  # Top 10 features

        axes[1, 1].barh(range(len(sorted_idx)), feature_importance[sorted_idx])
        axes[1, 1].set_yticks(range(len(sorted_idx)))
        axes[1, 1].set_yticklabels([feature_names[i] for i in sorted_idx])
        axes[1, 1].set_xlabel("Importance")
        axes[1, 1].set_title("Top 10 Feature Importance")

        plt.tight_layout()

        # Save validation charts
        output_dir = Path("output") / "visual_validation"
        output_dir.mkdir(parents=True, exist_ok=True)
        plt.savefig(
            output_dir
            / f'{symbol}_validation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
        )
        plt.close()

        # Calculate metrics
        mse = mean_squared_error(test_data["future_return"], predictions)
        mae = mean_absolute_error(test_data["future_return"], predictions)
        r2 = r2_score(test_data["future_return"], predictions)

        model_result["validation_metrics"] = {"mse": mse, "mae": mae, "r2": r2}

        return model_result

    def train_better_models(self, symbols=None, **kwargs):
        """Train improved models with better hyperparameters."""
        logger.info("Training better models with optimized hyperparameters")

        if symbols is None:
            symbols = ["EURUSD", "GBPUSD"]

        results = {}

        # Improved hyperparameters
        hyperparams = {
            "rf": {
                "n_estimators": 200,
                "max_depth": 10,
                "min_samples_split": 5,
                "min_samples_leaf": 2,
                "random_state": 42,
            },
            "gb": {
                "n_estimators": 150,
                "learning_rate": 0.1,
                "max_depth": 6,
                "min_samples_split": 5,
                "random_state": 42,
            },
        }

        for symbol in symbols:
            results[symbol] = {}

            for model_type, params in hyperparams.items():
                logger.info(f"Training better {model_type} model for {symbol}")

                # Load data
                data_loader = DataLoader()
                data = data_loader.load_data(symbol, timeframe="4h")

                # Engineer features
                feature_engineer = FeatureEngineer(timeframe="4h")
                features = feature_engineer.engineer_features(data)

                # Train with better hyperparameters
                model_class = self.model_types[model_type]
                model = model_class(**params)

                X = features.drop("future_return", axis=1)
                y = features["future_return"]

                # Split data
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=0.2, random_state=42
                )

                # Scale features
                scaler = StandardScaler()
                X_train_scaled = scaler.fit_transform(X_train)
                X_test_scaled = scaler.transform(X_test)

                # Train model
                model.fit(X_train_scaled, y_train)

                # Evaluate
                train_score = model.score(X_train_scaled, y_train)
                test_score = model.score(X_test_scaled, y_test)

                results[symbol][model_type] = {
                    "model": model,
                    "scaler": scaler,
                    "train_score": train_score,
                    "test_score": test_score,
                    "hyperparams": params,
                }

        return results

    def train_enhanced_models(self, symbols=None, **kwargs):
        """Train enhanced models with additional features."""
        logger.info("Training enhanced models with additional features")

        if symbols is None:
            symbols = ["EURUSD", "GBPUSD"]

        results = {}

        for symbol in symbols:
            logger.info(f"Training enhanced model for {symbol}")

            # Load data
            data_loader = DataLoader()
            data = data_loader.load_data(symbol, timeframe="4h")

            # Engineer enhanced features
            feature_engineer = FeatureEngineer(timeframe="4h")
            features = feature_engineer.engineer_features(data)

            # Add additional features
            features = self._add_enhanced_features(features)

            # Train ensemble model
            model_trainer = ModelTrainer(model_type="ensemble", timeframe="4h")
            model_result = model_trainer.train(features, target="future_return")

            results[symbol] = model_result

        return results

    def train_single_symbol(self, symbol, model_type="rf", **kwargs):
        """Train a single symbol with comprehensive analysis."""
        logger.info(f"Training single symbol model for {symbol}")

        # Load data
        data_loader = DataLoader()
        data = data_loader.load_data(symbol, timeframe="4h")

        # Engineer features
        feature_engineer = FeatureEngineer(timeframe="4h")
        features = feature_engineer.engineer_features(data)

        # Comprehensive cross-validation
        cv = CrossValidation(n_splits=5, model_type=model_type)
        cv_results = cv.cross_validate(features, target="future_return")

        # Train final model on all data
        model_trainer = ModelTrainer(model_type=model_type, timeframe="4h")
        model_result = model_trainer.train(features, target="future_return")

        # Combine results
        model_result["cv_results"] = cv_results

        return model_result

    def train_with_real_data(self, symbols=None, **kwargs):
        """Train models with real market data considerations."""
        logger.info("Training with real market data")

        if symbols is None:
            symbols = ["EURUSD", "GBPUSD"]

        results = {}

        for symbol in symbols:
            logger.info(f"Training with real data for {symbol}")

            # Load real data with proper handling
            data_loader = DataLoader()
            data = data_loader.load_real_data(symbol, timeframe="4h")

            # Handle missing data and outliers
            data = self._clean_real_data(data)

            # Engineer features for real data
            feature_engineer = FeatureEngineer(timeframe="4h")
            features = feature_engineer.engineer_features(data)

            # Train with real data considerations
            model_trainer = ModelTrainer(model_type="rf", timeframe="4h")
            model_result = model_trainer.train(features, target="future_return")

            results[symbol] = model_result

        return results

    def train_with_unified_features(self, symbols=None, **kwargs):
        """Train models with unified feature set."""
        logger.info("Training with unified features")

        if symbols is None:
            symbols = ["EURUSD", "GBPUSD", "USDCHF", "USDJPY"]

        # Create unified feature set
        unified_features = self._create_unified_features(symbols)

        results = {}

        for symbol in symbols:
            logger.info(f"Training unified model for {symbol}")

            symbol_features = unified_features[symbol]

            # Train model
            model_trainer = ModelTrainer(model_type="rf", timeframe="4h")
            model_result = model_trainer.train(symbol_features, target="future_return")

            results[symbol] = model_result

        return results

    def train_with_walk_forward(self, symbol, **kwargs):
        """Train models with walk-forward optimization."""
        logger.info(f"Training with walk-forward optimization for {symbol}")

        # Load data
        data_loader = DataLoader()
        data = data_loader.load_data(symbol, timeframe="4h")

        # Engineer features
        feature_engineer = FeatureEngineer(timeframe="4h")
        features = feature_engineer.engineer_features(data)

        # Walk-forward optimization
        optimizer = WalkForwardOptimizer(
            model_type="rf",
            window_size=kwargs.get("window_size", 1000),
            step_size=kwargs.get("step_size", 100),
        )

        wf_results = optimizer.optimize(features, target="future_return")

        return wf_results

    def _add_enhanced_features(self, features):
        """Add enhanced features to the dataset."""
        # Add momentum features
        features["momentum_5"] = features["close"].pct_change(5)
        features["momentum_10"] = features["close"].pct_change(10)
        features["momentum_20"] = features["close"].pct_change(20)

        # Add volatility features
        features["volatility_5"] = features["close"].rolling(5).std()
        features["volatility_10"] = features["close"].rolling(10).std()
        features["volatility_20"] = features["close"].rolling(20).std()

        return features

    def _clean_real_data(self, data):
        """Clean real market data."""
        # Remove outliers
        Q1 = data["close"].quantile(0.25)
        Q3 = data["close"].quantile(0.75)
        IQR = Q3 - Q1

        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR

        data = data[(data["close"] >= lower_bound) & (data["close"] <= upper_bound)]

        # Fill missing values
        data = data.fillna(method="forward")

        return data

    def _create_unified_features(self, symbols):
        """Create unified feature set for all symbols."""
        unified_features = {}

        for symbol in symbols:
            data_loader = DataLoader()
            data = data_loader.load_data(symbol, timeframe="4h")

            feature_engineer = FeatureEngineer(timeframe="4h")
            features = feature_engineer.engineer_features(data)

            unified_features[symbol] = features

        return unified_features

    def run_training_method(self, method_name, **kwargs):
        """Run a specific training method."""
        if method_name not in self.training_methods:
            raise ValueError(f"Unknown training method: {method_name}")

        return self.training_methods[method_name](**kwargs)

    def list_training_methods(self):
        """List available training methods."""
        return list(self.training_methods.keys())


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(description="FXML4 Consolidated Training Suite")
    parser.add_argument("--method", required=True, help="Training method to run")
    parser.add_argument("--symbol", help="Single symbol to train")
    parser.add_argument("--symbols", nargs="+", help="Multiple symbols to train")
    parser.add_argument(
        "--model-type", default="rf", choices=["rf", "gb", "lr"], help="Model type"
    )
    parser.add_argument(
        "--list-methods", action="store_true", help="List available training methods"
    )

    args = parser.parse_args()

    suite = ConsolidatedTrainingSuite()

    if args.list_methods:
        print("Available training methods:")
        for method in suite.list_training_methods():
            print(f"  - {method}")
        return

    # Run training method
    kwargs = {
        "symbol": args.symbol,
        "symbols": args.symbols,
        "model_type": args.model_type,
    }

    logger.info(f"Running training method: {args.method}")
    result = suite.run_training_method(args.method, **kwargs)

    # Save results
    output_dir = Path("output") / "training" / args.method
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(
        output_dir / f'results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json', "w"
    ) as f:
        json.dump(result, f, indent=2, default=str)

    logger.info(f"Training completed. Results saved to {output_dir}")


if __name__ == "__main__":
    main()
