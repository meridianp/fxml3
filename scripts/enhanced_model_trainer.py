#!/usr/bin/env python
"""Enhanced model trainer class for integrated system."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import json
import warnings
from datetime import datetime

import joblib
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

import lightgbm as lgb
import xgboost as xgb

# Model imports
from sklearn.ensemble import RandomForestRegressor, VotingRegressor
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler


class EnhancedModelTrainer:
    """Train enhanced ML models for forex prediction."""

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.models = {}
        self.scalers = {}
        self.best_model = None
        self.feature_columns = None

    def train_random_forest(self, X_train, y_train, X_test, y_test):
        """Train Random Forest model."""
        print("  Training Random Forest...")

        model = RandomForestRegressor(
            n_estimators=200,
            max_depth=20,
            min_samples_split=50,
            min_samples_leaf=20,
            max_features="sqrt",
            n_jobs=-1,
            random_state=42,
        )

        model.fit(X_train, y_train)

        # Predictions
        y_pred_train = model.predict(X_train)
        y_pred_test = model.predict(X_test)

        # Metrics
        train_r2 = r2_score(y_train, y_pred_train)
        test_r2 = r2_score(y_test, y_pred_test)

        # Direction accuracy
        train_dir_acc = np.mean(np.sign(y_pred_train) == np.sign(y_train))
        test_dir_acc = np.mean(np.sign(y_pred_test) == np.sign(y_test))

        self.models["random_forest"] = model

        return {
            "train_r2": train_r2,
            "test_r2": test_r2,
            "train_direction_accuracy": train_dir_acc,
            "test_direction_accuracy": test_dir_acc,
        }

    def train_xgboost(self, X_train, y_train, X_test, y_test):
        """Train XGBoost model."""
        print("  Training XGBoost...")

        # Convert to DMatrix for XGBoost
        dtrain = xgb.DMatrix(X_train, label=y_train)
        dtest = xgb.DMatrix(X_test, label=y_test)

        params = {
            "objective": "reg:squarederror",
            "max_depth": 10,
            "learning_rate": 0.01,
            "n_estimators": 1000,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "min_child_weight": 5,
            "gamma": 0.1,
            "reg_alpha": 0.1,
            "reg_lambda": 1.0,
            "random_state": 42,
        }

        # Train with early stopping
        evals = [(dtrain, "train"), (dtest, "eval")]
        model = xgb.train(
            params,
            dtrain,
            num_boost_round=1000,
            evals=evals,
            early_stopping_rounds=50,
            verbose_eval=False,
        )

        # Predictions
        y_pred_train = model.predict(dtrain)
        y_pred_test = model.predict(dtest)

        # Metrics
        train_r2 = r2_score(y_train, y_pred_train)
        test_r2 = r2_score(y_test, y_pred_test)

        # Direction accuracy
        train_dir_acc = np.mean(np.sign(y_pred_train) == np.sign(y_train))
        test_dir_acc = np.mean(np.sign(y_pred_test) == np.sign(y_test))

        self.models["xgboost"] = model

        return {
            "train_r2": train_r2,
            "test_r2": test_r2,
            "train_direction_accuracy": train_dir_acc,
            "test_direction_accuracy": test_dir_acc,
            "best_iteration": model.best_iteration,
        }

    def train_lightgbm(self, X_train, y_train, X_test, y_test):
        """Train LightGBM model."""
        print("  Training LightGBM...")

        # Create datasets
        train_data = lgb.Dataset(X_train, label=y_train)
        valid_data = lgb.Dataset(X_test, label=y_test, reference=train_data)

        params = {
            "objective": "regression",
            "metric": "rmse",
            "boosting_type": "gbdt",
            "num_leaves": 31,
            "learning_rate": 0.01,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "min_data_in_leaf": 50,
            "lambda_l1": 0.1,
            "lambda_l2": 1.0,
            "verbose": -1,
            "random_state": 42,
        }

        # Train
        model = lgb.train(
            params,
            train_data,
            valid_sets=[valid_data],
            num_boost_round=1000,
            callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)],
        )

        # Predictions
        y_pred_train = model.predict(X_train, num_iteration=model.best_iteration)
        y_pred_test = model.predict(X_test, num_iteration=model.best_iteration)

        # Metrics
        train_r2 = r2_score(y_train, y_pred_train)
        test_r2 = r2_score(y_test, y_pred_test)

        # Direction accuracy
        train_dir_acc = np.mean(np.sign(y_pred_train) == np.sign(y_train))
        test_dir_acc = np.mean(np.sign(y_pred_test) == np.sign(y_test))

        self.models["lightgbm"] = model

        return {
            "train_r2": train_r2,
            "test_r2": test_r2,
            "train_direction_accuracy": train_dir_acc,
            "test_direction_accuracy": test_dir_acc,
            "best_iteration": model.best_iteration,
        }

    def train_neural_network(self, X_train, y_train, X_test, y_test):
        """Train Neural Network model."""
        print("  Training Neural Network...")

        # Scale data for neural network
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        self.scalers["neural_network"] = scaler

        model = MLPRegressor(
            hidden_layer_sizes=(100, 50, 25),
            activation="relu",
            solver="adam",
            alpha=0.01,
            learning_rate="adaptive",
            learning_rate_init=0.001,
            max_iter=500,
            early_stopping=True,
            validation_fraction=0.2,
            n_iter_no_change=20,
            random_state=42,
        )

        model.fit(X_train_scaled, y_train)

        # Predictions
        y_pred_train = model.predict(X_train_scaled)
        y_pred_test = model.predict(X_test_scaled)

        # Metrics
        train_r2 = r2_score(y_train, y_pred_train)
        test_r2 = r2_score(y_test, y_pred_test)

        # Direction accuracy
        train_dir_acc = np.mean(np.sign(y_pred_train) == np.sign(y_train))
        test_dir_acc = np.mean(np.sign(y_pred_test) == np.sign(y_test))

        self.models["neural_network"] = model

        return {
            "train_r2": train_r2,
            "test_r2": test_r2,
            "train_direction_accuracy": train_dir_acc,
            "test_direction_accuracy": test_dir_acc,
            "n_iter": model.n_iter_,
        }

    def create_ensemble(self, X_train, y_train, X_test, y_test):
        """Create ensemble of all models."""
        print("  Creating Ensemble...")

        # For ensemble, we need sklearn-compatible models
        # Create wrapper for XGBoost
        class XGBWrapper:
            def __init__(self, model):
                self.model = model

            def predict(self, X):
                return self.model.predict(xgb.DMatrix(X))

            def fit(self, X, y):
                return self

        # Create wrapper for LightGBM
        class LGBWrapper:
            def __init__(self, model):
                self.model = model

            def predict(self, X):
                return self.model.predict(X, num_iteration=self.model.best_iteration)

            def fit(self, X, y):
                return self

        # Scale data for neural network in ensemble
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        self.scalers["ensemble"] = scaler

        # Create scaled NN wrapper
        class ScaledNNWrapper:
            def __init__(self, model, scaler):
                self.model = model
                self.scaler = scaler

            def predict(self, X):
                X_scaled = self.scaler.transform(X)
                return self.model.predict(X_scaled)

            def fit(self, X, y):
                return self

        # Create ensemble
        estimators = []

        if "random_forest" in self.models:
            estimators.append(("rf", self.models["random_forest"]))

        if "xgboost" in self.models:
            estimators.append(("xgb", XGBWrapper(self.models["xgboost"])))

        if "lightgbm" in self.models:
            estimators.append(("lgb", LGBWrapper(self.models["lightgbm"])))

        if "neural_network" in self.models:
            estimators.append(
                ("nn", ScaledNNWrapper(self.models["neural_network"], scaler))
            )

        # Voting regressor
        ensemble = VotingRegressor(estimators=estimators)
        ensemble.fit(X_train, y_train)  # This is just for compatibility

        # Predictions
        y_pred_train = ensemble.predict(X_train)
        y_pred_test = ensemble.predict(X_test)

        # Metrics
        train_r2 = r2_score(y_train, y_pred_train)
        test_r2 = r2_score(y_test, y_pred_test)

        # Direction accuracy
        train_dir_acc = np.mean(np.sign(y_pred_train) == np.sign(y_train))
        test_dir_acc = np.mean(np.sign(y_pred_test) == np.sign(y_test))

        # Calculate Sharpe ratio
        returns_pred = pd.Series(y_pred_test)
        sharpe = (
            np.sqrt(252) * returns_pred.mean() / returns_pred.std()
            if returns_pred.std() > 0
            else 0
        )

        self.models["ensemble"] = ensemble

        return {
            "train_r2": train_r2,
            "test_r2": test_r2,
            "train_direction_accuracy": train_dir_acc,
            "test_direction_accuracy": test_dir_acc,
            "sharpe_ratio": sharpe,
        }

    def optimize_threshold(self, X_test, y_test, model_name="ensemble"):
        """Optimize prediction threshold for better signal generation."""
        print(f"  Optimizing threshold for {model_name}...")

        model = self.models.get(model_name)
        if not model:
            return None

        # Get predictions
        if model_name == "neural_network" and model_name in self.scalers:
            X_test_scaled = self.scalers[model_name].transform(X_test)
            y_pred = model.predict(X_test_scaled)
        else:
            y_pred = model.predict(X_test)

        # Test different thresholds
        best_sharpe = -np.inf
        best_threshold = 0.001

        for threshold in np.linspace(0.0005, 0.002, 20):
            # Generate signals
            signals = np.where(
                y_pred > threshold, 1, np.where(y_pred < -threshold, -1, 0)
            )

            # Calculate returns
            returns = signals[:-1] * y_test.values[1:]  # Shift for next period return

            if len(returns[returns != 0]) > 10:  # Need minimum trades
                sharpe = (
                    np.sqrt(252) * returns.mean() / returns.std()
                    if returns.std() > 0
                    else 0
                )

                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_threshold = threshold

        # Calculate metrics with best threshold
        signals = np.where(
            y_pred > best_threshold, 1, np.where(y_pred < -best_threshold, -1, 0)
        )

        signal_rate = np.mean(signals != 0)

        return {
            "optimal_threshold": best_threshold,
            "sharpe_ratio": best_sharpe,
            "signal_rate": signal_rate,
        }

    def train_all_models(
        self, X_train, y_train, X_test, y_test, optimize_threshold=True
    ):
        """Train all models and create ensemble."""
        results = {}

        # Train individual models
        try:
            results["random_forest"] = self.train_random_forest(
                X_train, y_train, X_test, y_test
            )
        except Exception as e:
            print(f"  ⚠️ Random Forest failed: {e}")

        try:
            results["xgboost"] = self.train_xgboost(X_train, y_train, X_test, y_test)
        except Exception as e:
            print(f"  ⚠️ XGBoost failed: {e}")

        try:
            results["lightgbm"] = self.train_lightgbm(X_train, y_train, X_test, y_test)
        except Exception as e:
            print(f"  ⚠️ LightGBM failed: {e}")

        try:
            results["neural_network"] = self.train_neural_network(
                X_train, y_train, X_test, y_test
            )
        except Exception as e:
            print(f"  ⚠️ Neural Network failed: {e}")

        # Create ensemble if we have at least 2 models
        if len(self.models) >= 2:
            try:
                results["ensemble"] = self.create_ensemble(
                    X_train, y_train, X_test, y_test
                )

                # Optimize threshold
                if optimize_threshold:
                    threshold_results = self.optimize_threshold(
                        X_test, y_test, "ensemble"
                    )
                    if threshold_results:
                        results["ensemble"].update(threshold_results)

            except Exception as e:
                print(f"  ⚠️ Ensemble failed: {e}")

        # Find best model
        best_model_name = None
        best_accuracy = 0

        for name, metrics in results.items():
            if (
                "test_direction_accuracy" in metrics
                and metrics["test_direction_accuracy"] > best_accuracy
            ):
                best_accuracy = metrics["test_direction_accuracy"]
                best_model_name = name

        self.best_model = best_model_name

        return results
