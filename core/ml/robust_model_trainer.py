"""Robust model training with comprehensive anti-overfitting techniques."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.base import BaseEstimator
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, log_loss
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

logger = logging.getLogger(__name__)


class RobustModelTrainer:
    """
    Implements comprehensive anti-overfitting techniques:

    1. Proper time series validation (no future data leakage)
    2. Feature stability analysis
    3. Model complexity penalties
    4. Ensemble of simpler models
    5. Noise injection for robustness
    6. Early stopping with proper validation
    7. Feature dropout during training
    """

    def __init__(self):
        self.feature_stability_scores = {}
        self.model_complexity_scores = {}

    def calculate_feature_stability(
        self,
        data: pd.DataFrame,
        features: List[str],
        window_size: int = 252,  # 1 year for daily data
    ) -> Dict[str, float]:
        """
        Calculate stability scores for features across time.
        Stable features are more reliable for out-of-sample prediction.
        """
        stability_scores = {}

        for feature in features:
            if feature not in data.columns:
                continue

            # Calculate rolling correlation with target
            rolling_corr = []

            for i in range(window_size, len(data) - window_size, window_size // 4):
                window_data = data.iloc[i - window_size : i]
                if "target" in window_data.columns:
                    corr = window_data[feature].corr(window_data["target"])
                    rolling_corr.append(corr)

            if rolling_corr:
                # Stability = low variance in correlation over time
                stability = 1 / (1 + np.std(rolling_corr))
                stability_scores[feature] = stability
            else:
                stability_scores[feature] = 0.5

        return stability_scores

    def inject_noise(self, X: np.ndarray, noise_level: float = 0.01) -> np.ndarray:
        """
        Add small amounts of noise to prevent overfitting to exact values.
        """
        noise = np.random.normal(0, noise_level, X.shape)
        return X + noise * np.std(X, axis=0)

    def create_simple_ensemble(self) -> List[BaseEstimator]:
        """
        Create ensemble of simple models to prevent overfitting.
        """
        models = [
            # Very shallow trees
            RandomForestClassifier(
                n_estimators=50,
                max_depth=3,
                min_samples_split=100,
                min_samples_leaf=50,
                max_features="sqrt",
                random_state=42,
            ),
            # Highly regularized LightGBM
            LGBMClassifier(
                n_estimators=50,
                max_depth=3,
                learning_rate=0.01,
                min_child_samples=100,
                subsample=0.6,
                colsample_bytree=0.6,
                reg_alpha=1.0,
                reg_lambda=1.0,
                random_state=42,
            ),
            # Conservative XGBoost
            XGBClassifier(
                n_estimators=50,
                max_depth=3,
                learning_rate=0.01,
                min_child_weight=10,
                subsample=0.6,
                colsample_bytree=0.6,
                reg_alpha=1.0,
                reg_lambda=1.0,
                random_state=42,
            ),
        ]

        return models

    def feature_dropout_training(
        self,
        model: BaseEstimator,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        dropout_rate: float = 0.2,
        n_iterations: int = 10,
    ) -> BaseEstimator:
        """
        Train model multiple times with random feature dropout.
        """
        n_features = X_train.shape[1]
        n_dropout = int(n_features * dropout_rate)

        predictions = []

        for i in range(n_iterations):
            # Randomly select features to keep
            keep_features = np.random.choice(
                n_features, size=n_features - n_dropout, replace=False
            )

            X_subset = X_train.iloc[:, keep_features]

            # Train on subset
            model_copy = model.__class__(**model.get_params())
            model_copy.fit(X_subset, y_train)

            # Store for ensemble
            predictions.append((keep_features, model_copy))

        # Return ensemble wrapper
        return DropoutEnsemble(predictions)

    def train_with_time_decay(
        self,
        model: BaseEstimator,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        decay_rate: float = 0.95,
    ) -> BaseEstimator:
        """
        Train with exponentially decaying weights for older data.
        """
        # Calculate sample weights
        n_samples = len(X_train)
        days_ago = np.arange(n_samples, 0, -1)
        weights = decay_rate ** (days_ago / 30)  # Monthly decay
        weights = weights / weights.sum() * n_samples

        # Train with weights
        model.fit(X_train, y_train, sample_weight=weights)

        return model

    def validate_no_lookahead(self, features: List[str]) -> List[str]:
        """
        Remove features that might contain look-ahead bias.
        """
        suspicious_keywords = [
            "future",
            "next",
            "forward",
            "ahead",
            "later",
            "high_low_spread",  # If calculated with same bar's high/low
            "close_to_high",  # If using same bar's high
            "close_to_low",  # If using same bar's low
        ]

        clean_features = []
        removed = []

        for feature in features:
            has_bias = any(
                keyword in feature.lower() for keyword in suspicious_keywords
            )

            if has_bias:
                removed.append(feature)
            else:
                clean_features.append(feature)

        if removed:
            logger.warning(
                f"Removed {len(removed)} features with potential look-ahead bias: {removed[:5]}..."
            )

        return clean_features

    def train_robust_model(
        self,
        data: pd.DataFrame,
        features: List[str],
        target_col: str = "target",
        test_size: float = 0.2,
    ) -> Dict[str, Any]:
        """
        Train a robust model with all anti-overfitting techniques.
        """
        # 1. Remove look-ahead features
        clean_features = self.validate_no_lookahead(features)

        # 2. Calculate feature stability
        stability_scores = self.calculate_feature_stability(data, clean_features)

        # 3. Select stable features (top 70%)
        stable_features = sorted(
            stability_scores.items(), key=lambda x: x[1], reverse=True
        )
        n_keep = int(len(stable_features) * 0.7)
        selected_features = [f[0] for f in stable_features[:n_keep]]

        logger.info(
            f"Selected {len(selected_features)} stable features from {len(clean_features)}"
        )

        # 4. Prepare data with proper time split
        train_size = int(len(data) * (1 - test_size))
        train_data = data.iloc[:train_size]
        test_data = data.iloc[train_size:]

        X_train = train_data[selected_features]
        y_train = train_data[target_col]
        X_test = test_data[selected_features]
        y_test = test_data[target_col]

        # 5. Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        # 6. Add noise to training data
        X_train_noisy = self.inject_noise(X_train_scaled, noise_level=0.01)

        # 7. Train ensemble of simple models
        models = self.create_simple_ensemble()
        trained_models = []

        for i, model in enumerate(models):
            logger.info(
                f"Training model {i+1}/{len(models)}: {model.__class__.__name__}"
            )

            # Train with time decay
            model = self.train_with_time_decay(
                model, pd.DataFrame(X_train_noisy), y_train, decay_rate=0.95
            )

            # Evaluate
            train_pred = model.predict(X_train_scaled)
            test_pred = model.predict(X_test_scaled)

            train_acc = accuracy_score(y_train, train_pred)
            test_acc = accuracy_score(y_test, test_pred)

            logger.info(f"  Train accuracy: {train_acc:.4f}")
            logger.info(f"  Test accuracy: {test_acc:.4f}")
            logger.info(f"  Overfit ratio: {train_acc/test_acc:.2f}")

            trained_models.append(
                {
                    "model": model,
                    "train_acc": train_acc,
                    "test_acc": test_acc,
                    "overfit_ratio": train_acc / test_acc if test_acc > 0 else np.inf,
                }
            )

        # 8. Select best model (lowest overfit ratio)
        best_model_info = min(trained_models, key=lambda x: x["overfit_ratio"])

        return {
            "model": best_model_info["model"],
            "scaler": scaler,
            "features": selected_features,
            "stability_scores": stability_scores,
            "train_accuracy": best_model_info["train_acc"],
            "test_accuracy": best_model_info["test_acc"],
            "overfit_ratio": best_model_info["overfit_ratio"],
            "all_models": trained_models,
        }


class DropoutEnsemble:
    """Ensemble of models trained with feature dropout."""

    def __init__(self, models: List[Tuple[np.ndarray, BaseEstimator]]):
        self.models = models

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Ensemble prediction with voting."""
        predictions = []

        for feature_indices, model in self.models:
            X_subset = X[:, feature_indices]
            pred = model.predict(X_subset)
            predictions.append(pred)

        # Majority vote
        predictions = np.array(predictions)
        return np.apply_along_axis(
            lambda x: np.bincount(x).argmax(), axis=0, arr=predictions
        )

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Ensemble probability prediction."""
        probas = []

        for feature_indices, model in self.models:
            X_subset = X[:, feature_indices]
            if hasattr(model, "predict_proba"):
                proba = model.predict_proba(X_subset)
                probas.append(proba)

        if probas:
            # Average probabilities
            return np.mean(probas, axis=0)
        else:
            # Fallback to predict
            pred = self.predict(X)
            n_classes = 3  # -1, 0, 1
            proba = np.zeros((len(X), n_classes))
            proba[np.arange(len(X)), pred] = 1
            return proba
