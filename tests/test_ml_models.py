"""
Tests for the ML models module in FXML4.

This module verifies the correct functioning of:
- ClassicMLModel (Random Forest, XGBoost, Logistic Regression)
- EnsembleModel
- Hardware acceleration detection and optimization
- Model evaluation metrics
"""

import logging
import os
import shutil
import tempfile

import numpy as np
import pandas as pd
import pytest
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split

from fxml4.ml.models import (
    ClassicMLModel,
    EnsembleModel,
    compare_models,
    create_simple_ensemble,
    detect_platform,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.fixture
def ml_test_data():
    """Create test data for ML models."""
    # Create synthetic data for classification
    X, y = make_classification(
        n_samples=1000,
        n_features=20,
        n_informative=10,
        n_redundant=5,
        n_classes=3,
        random_state=42,
    )

    # Convert to DataFrame with feature names
    X_df = pd.DataFrame(X, columns=[f"feature_{i}" for i in range(X.shape[1])])
    y_series = pd.Series(y)

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X_df, y_series, test_size=0.3, random_state=42
    )

    # Generate mock returns for testing trading metrics
    returns = np.random.normal(0.0001, 0.001, size=len(y_test))

    return {
        "X": X_df,
        "y": y_series,
        "X_train": X_train,
        "X_test": X_test,
        "y_train": y_train,
        "y_test": y_test,
        "returns": returns,
    }


@pytest.fixture
def temp_dir():
    """Create temporary directory for model saving/loading tests."""
    temp_directory = tempfile.mkdtemp()
    yield temp_directory
    # Cleanup
    shutil.rmtree(temp_directory)


@pytest.fixture
def platform_info():
    """Get platform information for hardware acceleration tests."""
    info = detect_platform()
    logger.info(f"Testing on platform: {info}")
    return info


class TestMLModels:
    """Test cases for ML models."""

    def test_random_forest_model(self, ml_test_data, temp_dir):
        """Test Random Forest model."""
        # Create and train model
        rf_model = ClassicMLModel(
            model_type="random_forest", name="test_rf", n_classes=3, random_state=42
        )

        rf_model.train(ml_test_data["X_train"], ml_test_data["y_train"])

        # Check predictions
        y_pred = rf_model.predict(ml_test_data["X_test"])
        assert len(y_pred) == len(ml_test_data["y_test"])

        # Check evaluation
        metrics = rf_model.evaluate(
            ml_test_data["X_test"],
            ml_test_data["y_test"],
            returns=ml_test_data["returns"],
        )
        assert metrics["accuracy"] > 0.5  # Should be better than random

        # Check feature importance
        assert rf_model.feature_importance is not None
        assert len(rf_model.feature_importance) == ml_test_data["X"].shape[1]

        # Check save/load
        rf_model.save(temp_dir)
        loaded_model = ClassicMLModel.load("test_rf", temp_dir)

        # Verify loaded model works
        y_pred_loaded = loaded_model.predict(ml_test_data["X_test"])
        np.testing.assert_array_equal(y_pred, y_pred_loaded)

    def test_xgboost_model(self, ml_test_data, temp_dir):
        """Test XGBoost model."""
        # Create and train model
        xgb_model = ClassicMLModel(
            model_type="xgboost", name="test_xgb", n_classes=3, random_state=42
        )

        xgb_model.train(ml_test_data["X_train"], ml_test_data["y_train"])

        # Check predictions
        y_pred = xgb_model.predict(ml_test_data["X_test"])
        assert len(y_pred) == len(ml_test_data["y_test"])

        # Check evaluation
        metrics = xgb_model.evaluate(
            ml_test_data["X_test"],
            ml_test_data["y_test"],
            returns=ml_test_data["returns"],
        )
        assert metrics["accuracy"] > 0.5  # Should be better than random

        # Check feature importance
        assert xgb_model.feature_importance is not None
        assert len(xgb_model.feature_importance) == ml_test_data["X"].shape[1]

        # Check save/load
        xgb_model.save(temp_dir)
        loaded_model = ClassicMLModel.load("test_xgb", temp_dir)

        # Verify loaded model works
        y_pred_loaded = loaded_model.predict(ml_test_data["X_test"])
        np.testing.assert_array_equal(y_pred, y_pred_loaded)

    def test_logistic_model(self, ml_test_data, temp_dir):
        """Test Logistic Regression model."""
        # Create and train model
        lr_model = ClassicMLModel(
            model_type="logistic", name="test_lr", n_classes=3, random_state=42
        )

        lr_model.train(ml_test_data["X_train"], ml_test_data["y_train"])

        # Check predictions
        y_pred = lr_model.predict(ml_test_data["X_test"])
        assert len(y_pred) == len(ml_test_data["y_test"])

        # Check evaluation
        metrics = lr_model.evaluate(
            ml_test_data["X_test"],
            ml_test_data["y_test"],
            returns=ml_test_data["returns"],
        )
        assert metrics["accuracy"] > 0.5  # Should be better than random

        # Check feature importance
        assert lr_model.feature_importance is not None
        assert len(lr_model.feature_importance) == ml_test_data["X"].shape[1]

        # Check save/load
        lr_model.save(temp_dir)
        loaded_model = ClassicMLModel.load("test_lr", temp_dir)

        # Verify loaded model works
        y_pred_loaded = loaded_model.predict(ml_test_data["X_test"])
        np.testing.assert_array_equal(y_pred, y_pred_loaded)

    def test_ensemble_model(self, ml_test_data, temp_dir):
        """Test Ensemble model."""
        # Create base models
        rf_model = ClassicMLModel(
            model_type="random_forest",
            name="rf_for_ensemble",
            n_classes=3,
            random_state=42,
        )

        xgb_model = ClassicMLModel(
            model_type="xgboost", name="xgb_for_ensemble", n_classes=3, random_state=42
        )

        # Train models
        rf_model.train(ml_test_data["X_train"], ml_test_data["y_train"])
        xgb_model.train(ml_test_data["X_train"], ml_test_data["y_train"])

        # Save models
        rf_model.save(temp_dir)
        xgb_model.save(temp_dir)

        # Create ensemble
        ensemble = EnsembleModel(
            models=[rf_model, xgb_model],
            name="test_ensemble",
            ensemble_method="weighted",
            weights=[0.6, 0.4],
        )

        # Check predictions
        y_pred = ensemble.predict(ml_test_data["X_test"])
        assert len(y_pred) == len(ml_test_data["y_test"])

        # Check evaluation
        metrics = ensemble.evaluate(
            ml_test_data["X_test"],
            ml_test_data["y_test"],
            returns=ml_test_data["returns"],
        )
        assert metrics["accuracy"] > 0.5  # Should be better than random

        # Check save/load
        ensemble.save(temp_dir)
        loaded_ensemble = EnsembleModel.load(
            "test_ensemble",
            temp_dir,
            models_dict={"rf_for_ensemble": rf_model, "xgb_for_ensemble": xgb_model},
        )

        # Verify loaded model works
        y_pred_loaded = loaded_ensemble.predict(ml_test_data["X_test"])
        np.testing.assert_array_equal(y_pred, y_pred_loaded)

    def test_trading_metrics(self, ml_test_data):
        """Test trading-specific metrics."""
        # Create a simple model
        model = ClassicMLModel(
            model_type="random_forest",
            name="metrics_test",
            n_classes=3,
            random_state=42,
        )

        model.train(ml_test_data["X_train"], ml_test_data["y_train"])

        # Generate predictions
        y_pred = model.predict(ml_test_data["X_test"])

        # Calculate trading metrics manually
        # First, create returns based on predictions
        position_returns = np.zeros_like(ml_test_data["returns"])
        position_returns[y_pred == 1] = ml_test_data["returns"][y_pred == 1]  # Long
        position_returns[y_pred == -1] = -ml_test_data["returns"][y_pred == -1]  # Short

        # Apply transaction costs
        transaction_cost = 0.0001
        position_returns[y_pred != 0] -= transaction_cost

        # Calculate metrics
        profits = position_returns[position_returns > 0]
        losses = position_returns[position_returns < 0]

        if len(losses) > 0:
            expected_profit_factor = np.sum(profits) / np.abs(np.sum(losses))
        else:
            expected_profit_factor = float("inf") if len(profits) > 0 else 0.0

        expected_win_rate = (
            np.sum(position_returns > 0) / np.sum(y_pred != 0)
            if np.sum(y_pred != 0) > 0
            else 0.0
        )

        # Get metrics from model
        metrics = model._calculate_trading_metrics(
            ml_test_data["y_test"], y_pred, ml_test_data["returns"]
        )

        # Verify metrics
        assert abs(metrics["profit_factor"] - expected_profit_factor) < 1e-5
        assert abs(metrics["win_rate"] - expected_win_rate) < 1e-5

        # Additional metrics should exist
        assert "max_drawdown" in metrics
        assert "calmar_ratio" in metrics
        assert "sharpe_ratio" in metrics

    def test_sample_weights(self, ml_test_data):
        """Test training with sample weights."""
        # Create class imbalance in the data
        sample_weights = np.ones(len(ml_test_data["y_train"]))
        sample_weights[ml_test_data["y_train"] == 0] = (
            2.0  # Weight class 0 more heavily
        )

        # Create model with and without weights
        model_with_weights = ClassicMLModel(
            model_type="random_forest",
            name="with_weights",
            n_classes=3,
            random_state=42,
        )

        model_without_weights = ClassicMLModel(
            model_type="random_forest",
            name="without_weights",
            n_classes=3,
            random_state=42,
        )

        # Train models
        model_with_weights.train(
            ml_test_data["X_train"],
            ml_test_data["y_train"],
            sample_weights=sample_weights,
        )
        model_without_weights.train(ml_test_data["X_train"], ml_test_data["y_train"])

        # Get predictions
        y_pred_with = model_with_weights.predict(ml_test_data["X_test"])
        y_pred_without = model_without_weights.predict(ml_test_data["X_test"])

        # Make sure predictions are different (weights had an effect)
        assert np.any(y_pred_with != y_pred_without)

    def test_cross_validation(self, ml_test_data):
        """Test cross-validation functionality."""
        # Create model
        model = ClassicMLModel(
            model_type="random_forest", name="cv_test", n_classes=3, random_state=42
        )

        # Train model
        model.train(ml_test_data["X_train"], ml_test_data["y_train"])

        # Run cross-validation
        cv_results = model.cross_validate(
            ml_test_data["X"], ml_test_data["y"], n_splits=3, time_series=False
        )

        # Check results
        assert "accuracy_mean" in cv_results
        assert "precision_mean" in cv_results
        assert "recall_mean" in cv_results
        assert "f1_mean" in cv_results

        # Mean values should be between 0 and 1
        assert cv_results["accuracy_mean"] > 0
        assert cv_results["accuracy_mean"] < 1

    def test_hyperparameter_tuning(self, ml_test_data):
        """Test hyperparameter tuning functionality."""
        # Create model
        model = ClassicMLModel(
            model_type="random_forest", name="tuning_test", n_classes=3, random_state=42
        )

        # Define parameter grid
        param_grid = {"n_estimators": [10, 20], "max_depth": [5, 10]}

        # Train model
        model.train(ml_test_data["X_train"], ml_test_data["y_train"])

        # Run hyperparameter tuning
        tuning_results = model.tune_hyperparameters(
            ml_test_data["X"],
            ml_test_data["y"],
            param_grid=param_grid,
            n_splits=2,  # Use small number for testing
            n_jobs=1,  # Single job for testing
        )

        # Check results
        assert "best_params" in tuning_results
        assert "best_score" in tuning_results

        # Best params should be one of the combinations
        possible_params = [
            {"n_estimators": 10, "max_depth": 5},
            {"n_estimators": 10, "max_depth": 10},
            {"n_estimators": 20, "max_depth": 5},
            {"n_estimators": 20, "max_depth": 10},
        ]

        # Check if best_params matches one of the possible combinations
        found = False
        for params in possible_params:
            if all(
                tuning_results["best_params"].get(k) == v for k, v in params.items()
            ):
                found = True
                break

        assert (
            found
        ), f"Best params {tuning_results['best_params']} not in possible combinations"

    def test_hardware_acceleration(self, platform_info):
        """Test hardware acceleration detection."""
        # Test with hardware acceleration enabled (default)
        model_with_accel = ClassicMLModel(
            model_type="xgboost", hardware_acceleration=True
        )

        # Test with hardware acceleration disabled
        model_without_accel = ClassicMLModel(
            model_type="xgboost", hardware_acceleration=False
        )

        # Check if Apple Silicon is used correctly if available
        if platform_info["is_apple_silicon"]:
            tree_method = model_with_accel.model_params.get("tree_method")
            assert tree_method in [
                "hist",
                "gpu_hist",
            ], f"Expected 'hist' or 'gpu_hist' on Apple Silicon, got {tree_method}"

            # The non-accelerated model should not use GPU
            assert model_without_accel.model_params.get("tree_method") != "gpu_hist"

        # Check if CUDA is used correctly if available
        if platform_info["has_cuda"]:
            tree_method = model_with_accel.model_params.get("tree_method")
            assert (
                tree_method == "gpu_hist"
            ), f"Expected 'gpu_hist' on CUDA platform, got {tree_method}"

            # The non-accelerated model should not use GPU
            assert model_without_accel.model_params.get("tree_method") != "gpu_hist"

    def test_helper_functions(self, ml_test_data):
        """Test helper functions."""
        # Test create_simple_ensemble
        ensemble = create_simple_ensemble(
            ml_test_data["X_train"],
            ml_test_data["y_train"],
            weights={"random_forest": 0.5, "xgboost": 0.3, "logistic": 0.2},
        )

        # Check ensemble properties
        assert len(ensemble.models) == 3
        assert ensemble.ensemble_method == "weighted"
        assert abs(ensemble.weights[0] - 0.5) < 1e-10
        assert abs(ensemble.weights[1] - 0.3) < 1e-10
        assert abs(ensemble.weights[2] - 0.2) < 1e-10

        # Test predictions
        y_pred = ensemble.predict(ml_test_data["X_test"])
        assert len(y_pred) == len(ml_test_data["y_test"])

        # Test compare_models
        # Create models to compare
        models = [
            ClassicMLModel("random_forest", name="rf_compare"),
            ClassicMLModel("xgboost", name="xgb_compare"),
            ensemble,
        ]

        # Train models
        for model in models[:2]:  # Skip ensemble, already trained
            model.train(ml_test_data["X_train"], ml_test_data["y_train"])

        # Compare models
        comparison = compare_models(
            models,
            ml_test_data["X_test"],
            ml_test_data["y_test"],
            returns=ml_test_data["returns"],
        )

        # Check comparison results
        assert len(comparison) == 3
        assert "model_name" in comparison.columns
        assert "accuracy" in comparison.columns
        assert "profit_factor" in comparison.columns


# Pytest markers for test categorization
pytestmark = [pytest.mark.unit, pytest.mark.ml, pytest.mark.slow]
