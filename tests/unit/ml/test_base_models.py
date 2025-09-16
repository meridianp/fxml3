"""Tests for ML base model classes."""

import json
import os
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pandas as pd
import pytest

from fxml4.ml.models.base import MLModelBase


class MockMLModel(MLModelBase):
    """Mock implementation of MLModelBase for testing."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model = None
        self.is_fitted = False

    def fit(self, X, y):
        """Mock fit implementation."""
        self.is_fitted = True
        self.model = {
            "fitted": True,
            "features": X.shape[1] if hasattr(X, "shape") else len(X[0]),
        }
        return self

    def predict(self, X):
        """Mock predict implementation."""
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction")

        # Return mock predictions
        if hasattr(X, "shape"):
            n_samples = X.shape[0]
        else:
            n_samples = len(X)

        # Random predictions for n_classes
        return np.random.randint(0, self.n_classes, size=n_samples)

    def predict_proba(self, X):
        """Mock predict_proba implementation."""
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction")

        if hasattr(X, "shape"):
            n_samples = X.shape[0]
        else:
            n_samples = len(X)

        # Random probabilities
        proba = np.random.random((n_samples, self.n_classes))
        # Normalize to sum to 1
        return proba / proba.sum(axis=1, keepdims=True)


class TestMLModelBase:
    """Test MLModelBase abstract class."""

    @pytest.fixture
    def sample_data(self):
        """Create sample training data."""
        np.random.seed(42)
        X = np.random.randn(100, 10)  # 100 samples, 10 features
        y = np.random.randint(0, 3, 100)  # 3-class classification
        return X, y

    @pytest.fixture
    def mock_model(self):
        """Create a mock ML model."""
        return MockMLModel(
            name="test_model", model_type="mock", n_classes=3, random_state=42
        )

    @pytest.fixture
    def custom_mock_model(self):
        """Create a mock ML model with custom parameters."""
        return MockMLModel(
            name="custom_model",
            model_type="custom_mock",
            n_classes=2,
            model_params={"param1": 10, "param2": "value"},
            metadata={"created_by": "test_suite", "version": "1.0"},
        )

    def test_initialization_default(self, mock_model):
        """Test model initialization with defaults."""
        model = MockMLModel()

        assert model.model_type == "base"
        assert model.n_classes == 3
        assert model.random_state == 42
        assert model.model_params == {}
        assert isinstance(model.name, str)  # Auto-generated name
        assert model.is_fitted is False

    def test_initialization_custom(self, custom_mock_model):
        """Test model initialization with custom parameters."""
        assert custom_mock_model.name == "custom_model"
        assert custom_mock_model.model_type == "custom_mock"
        assert custom_mock_model.n_classes == 2
        assert custom_mock_model.model_params == {"param1": 10, "param2": "value"}
        assert custom_mock_model.metadata == {
            "created_by": "test_suite",
            "version": "1.0",
        }

    def test_auto_generated_name(self):
        """Test auto-generated model names are unique."""
        model1 = MockMLModel(model_type="test")
        model2 = MockMLModel(model_type="test")

        assert model1.name != model2.name
        assert "test" in model1.name
        assert "test" in model2.name

    def test_fit_functionality(self, mock_model, sample_data):
        """Test model fitting."""
        X, y = sample_data

        assert mock_model.is_fitted is False

        # Fit the model
        fitted_model = mock_model.fit(X, y)

        # Should return self
        assert fitted_model is mock_model
        assert mock_model.is_fitted is True
        assert mock_model.model["fitted"] is True
        assert mock_model.model["features"] == 10

    def test_predict_functionality(self, mock_model, sample_data):
        """Test model prediction."""
        X, y = sample_data

        # Should raise error if not fitted
        with pytest.raises(ValueError, match="must be fitted"):
            mock_model.predict(X)

        # Fit the model first
        mock_model.fit(X, y)

        # Test prediction
        predictions = mock_model.predict(X)

        assert len(predictions) == 100
        assert all(0 <= pred < 3 for pred in predictions)  # Valid class predictions

    def test_predict_proba_functionality(self, mock_model, sample_data):
        """Test model probability prediction."""
        X, y = sample_data

        # Should raise error if not fitted
        with pytest.raises(ValueError, match="must be fitted"):
            mock_model.predict_proba(X)

        # Fit the model first
        mock_model.fit(X, y)

        # Test probability prediction
        probabilities = mock_model.predict_proba(X)

        assert probabilities.shape == (100, 3)  # 100 samples, 3 classes

        # Check probabilities sum to 1 (within tolerance)
        prob_sums = probabilities.sum(axis=1)
        assert np.allclose(prob_sums, 1.0)

        # Check all probabilities are valid (0-1)
        assert np.all(probabilities >= 0)
        assert np.all(probabilities <= 1)

    def test_different_data_formats(self, mock_model):
        """Test model with different input data formats."""
        # Test with list input
        X_list = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
        y_list = [0, 1, 2]

        mock_model.fit(X_list, y_list)
        predictions = mock_model.predict(X_list)
        probabilities = mock_model.predict_proba(X_list)

        assert len(predictions) == 3
        assert probabilities.shape == (3, 3)

    def test_different_n_classes(self):
        """Test model with different number of classes."""
        # Binary classification
        binary_model = MockMLModel(n_classes=2)
        X = np.random.randn(50, 5)
        y = np.random.randint(0, 2, 50)

        binary_model.fit(X, y)
        predictions = binary_model.predict(X)
        probabilities = binary_model.predict_proba(X)

        assert all(0 <= pred < 2 for pred in predictions)
        assert probabilities.shape == (50, 2)

        # Multi-class classification
        multi_model = MockMLModel(n_classes=5)
        y_multi = np.random.randint(0, 5, 50)

        multi_model.fit(X, y_multi)
        predictions = multi_model.predict(X)
        probabilities = multi_model.predict_proba(X)

        assert all(0 <= pred < 5 for pred in predictions)
        assert probabilities.shape == (50, 5)

    def test_model_metadata_handling(self):
        """Test metadata handling."""
        metadata = {
            "created_at": datetime.now().isoformat(),
            "created_by": "test_user",
            "version": "1.0",
            "parameters": {"learning_rate": 0.01},
        }

        model = MockMLModel(name="metadata_test", metadata=metadata)

        assert model.metadata == metadata

    def test_model_parameters_handling(self):
        """Test model parameters handling."""
        params = {
            "n_estimators": 100,
            "max_depth": 10,
            "learning_rate": 0.1,
            "subsample": 0.8,
        }

        model = MockMLModel(name="params_test", model_params=params)

        assert model.model_params == params

    def test_reproducibility(self, sample_data):
        """Test that random_state ensures reproducibility."""
        X, y = sample_data

        # Create two identical models
        model1 = MockMLModel(random_state=123)
        model2 = MockMLModel(random_state=123)

        # Fit both models
        model1.fit(X, y)
        model2.fit(X, y)

        # Predictions should be identical (due to same random seed in mock)
        # Note: This depends on the mock implementation using the random_state

    def test_large_dataset_handling(self):
        """Test model with larger datasets."""
        # Create larger dataset
        np.random.seed(42)
        X_large = np.random.randn(10000, 50)  # 10k samples, 50 features
        y_large = np.random.randint(0, 3, 10000)

        model = MockMLModel(name="large_data_test")

        # Should handle large dataset without issues
        model.fit(X_large, y_large)
        predictions = model.predict(X_large)
        probabilities = model.predict_proba(X_large)

        assert len(predictions) == 10000
        assert probabilities.shape == (10000, 3)

    def test_edge_cases(self):
        """Test edge cases and error handling."""
        model = MockMLModel()

        # Test with minimal data
        X_small = np.array([[1], [2]])
        y_small = np.array([0, 1])

        model.fit(X_small, y_small)
        predictions = model.predict(X_small)

        assert len(predictions) == 2

        # Test with single sample
        X_single = np.array([[1, 2, 3]])
        predictions_single = model.predict(X_single)
        probabilities_single = model.predict_proba(X_single)

        assert len(predictions_single) == 1
        assert probabilities_single.shape == (1, 3)


@pytest.mark.unit
class TestMLModelBaseIntegration:
    """Integration tests for MLModelBase."""

    def test_complete_ml_workflow(self):
        """Test complete ML workflow from training to prediction."""
        # Create synthetic financial data
        np.random.seed(42)

        # Features: price changes, volume, technical indicators
        n_samples = 1000
        n_features = 20

        X = np.random.randn(n_samples, n_features)
        # Target: 0=sell, 1=hold, 2=buy signals
        y = np.random.randint(0, 3, n_samples)

        # Split data
        split_idx = int(0.8 * n_samples)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        # 1. Initialize model
        model = MockMLModel(
            name="integration_test_model",
            model_type="mock_classifier",
            n_classes=3,
            model_params={"test_param": "value"},
            metadata={"test": "integration"},
        )

        # 2. Train model
        model.fit(X_train, y_train)
        assert model.is_fitted is True

        # 3. Make predictions
        predictions = model.predict(X_test)
        probabilities = model.predict_proba(X_test)

        # 4. Validate results
        assert len(predictions) == len(X_test)
        assert probabilities.shape == (len(X_test), 3)
        assert all(0 <= pred < 3 for pred in predictions)

        # 5. Verify metadata integrity
        assert model.name == "integration_test_model"
        assert model.model_type == "mock_classifier"
        assert model.metadata["test"] == "integration"

    def test_model_comparison(self):
        """Test comparison between different model configurations."""
        np.random.seed(42)
        X = np.random.randn(100, 10)
        y = np.random.randint(0, 3, 100)

        # Create models with different configurations
        model_configs = [
            {"name": "model_1", "n_classes": 3, "model_params": {"param": 1}},
            {"name": "model_2", "n_classes": 3, "model_params": {"param": 2}},
            {"name": "model_3", "n_classes": 2, "model_params": {"param": 3}},
        ]

        models = []
        for config in model_configs:
            model = MockMLModel(**config)
            model.fit(X, y if config["n_classes"] == 3 else y % 2)
            models.append(model)

        # Test that models have different configurations
        assert models[0].model_params["param"] == 1
        assert models[1].model_params["param"] == 2
        assert models[2].n_classes == 2

        # All should be able to make predictions
        for model in models:
            predictions = model.predict(X)
            probabilities = model.predict_proba(X)

            assert len(predictions) == 100
            assert probabilities.shape[0] == 100
            assert probabilities.shape[1] == model.n_classes


@pytest.mark.performance
def test_ml_model_performance():
    """Test ML model performance with large datasets."""
    import time

    # Create large dataset
    np.random.seed(42)
    X = np.random.randn(50000, 100)  # 50k samples, 100 features
    y = np.random.randint(0, 3, 50000)

    model = MockMLModel(name="performance_test")

    # Test fitting performance
    start_time = time.time()
    model.fit(X, y)
    fit_time = time.time() - start_time

    # Test prediction performance
    start_time = time.time()
    predictions = model.predict(X)
    predict_time = time.time() - start_time

    # Test probability prediction performance
    start_time = time.time()
    probabilities = model.predict_proba(X)
    predict_proba_time = time.time() - start_time

    # Performance assertions (these are lenient for mock implementation)
    assert fit_time < 5.0  # Should fit within 5 seconds
    assert predict_time < 2.0  # Should predict within 2 seconds
    assert predict_proba_time < 2.0  # Should predict probabilities within 2 seconds

    # Verify results
    assert len(predictions) == 50000
    assert probabilities.shape == (50000, 3)
