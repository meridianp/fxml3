"""Tests for ML ensemble models and model registry."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest


class MockEnsembleModel:
    """Mock ensemble model for testing."""

    def __init__(self, name=None, models=None, voting="soft"):
        self.name = name or f"ensemble_{id(self)}"
        self.models = models or []
        self.voting = voting
        self.is_fitted = False

    def add_model(self, model):
        """Add model to ensemble."""
        self.models.append(model)

    def fit(self, X, y):
        """Fit all models in ensemble."""
        for model in self.models:
            model.fit(X, y)
        self.is_fitted = True
        return self

    def predict(self, X):
        """Ensemble prediction."""
        if not self.is_fitted:
            raise ValueError("Ensemble must be fitted")

        if not self.models:
            raise ValueError("No models in ensemble")

        # Get predictions from all models
        predictions = []
        for model in self.models:
            pred = model.predict(X)
            predictions.append(pred)

        predictions = np.array(predictions)

        # Majority voting
        n_samples = predictions.shape[1]
        ensemble_pred = np.zeros(n_samples, dtype=int)

        for i in range(n_samples):
            votes = predictions[:, i]
            ensemble_pred[i] = np.bincount(votes).argmax()

        return ensemble_pred

    def predict_proba(self, X):
        """Ensemble probability prediction."""
        if not self.is_fitted:
            raise ValueError("Ensemble must be fitted")

        if not self.models:
            raise ValueError("No models in ensemble")

        # Average probabilities
        all_proba = []
        for model in self.models:
            proba = model.predict_proba(X)
            all_proba.append(proba)

        return np.mean(all_proba, axis=0)


class MockModelRegistry:
    """Mock model registry for testing."""

    def __init__(self):
        self.models = {}
        self.metadata = {}

    def register_model(self, name, model, metadata=None):
        """Register a model."""
        self.models[name] = model
        self.metadata[name] = metadata or {}

    def get_model(self, name):
        """Get registered model."""
        if name not in self.models:
            raise KeyError(f"Model {name} not found")
        return self.models[name]

    def list_models(self):
        """List registered models."""
        return list(self.models.keys())

    def get_metadata(self, name):
        """Get model metadata."""
        if name not in self.metadata:
            raise KeyError(f"Model {name} not found")
        return self.metadata[name]


class TestEnsembleModels:
    """Test ensemble model functionality."""

    @pytest.fixture
    def mock_models(self):
        """Create mock models for ensemble."""
        from tests.unit.ml.test_models import MockMLModel

        models = []
        for i in range(3):
            model = MockMLModel(name=f"model_{i}", n_classes=3)
            models.append(model)
        return models

    @pytest.fixture
    def sample_data(self):
        """Create sample data."""
        np.random.seed(42)
        X = np.random.randn(100, 10)
        y = np.random.randint(0, 3, 100)
        return X, y

    def test_ensemble_initialization(self):
        """Test ensemble model initialization."""
        ensemble = MockEnsembleModel(name="test_ensemble")

        assert ensemble.name == "test_ensemble"
        assert ensemble.models == []
        assert ensemble.voting == "soft"
        assert ensemble.is_fitted is False

    def test_add_models_to_ensemble(self, mock_models):
        """Test adding models to ensemble."""
        ensemble = MockEnsembleModel()

        for model in mock_models:
            ensemble.add_model(model)

        assert len(ensemble.models) == 3
        assert all(model in ensemble.models for model in mock_models)

    def test_ensemble_fitting(self, mock_models, sample_data):
        """Test ensemble fitting."""
        X, y = sample_data
        ensemble = MockEnsembleModel(models=mock_models)

        assert ensemble.is_fitted is False
        ensemble.fit(X, y)

        assert ensemble.is_fitted is True
        # All individual models should be fitted
        assert all(model.is_fitted for model in ensemble.models)

    def test_ensemble_prediction(self, mock_models, sample_data):
        """Test ensemble prediction."""
        X, y = sample_data
        ensemble = MockEnsembleModel(models=mock_models)

        # Should raise error if not fitted
        with pytest.raises(ValueError, match="must be fitted"):
            ensemble.predict(X)

        # Fit and predict
        ensemble.fit(X, y)
        predictions = ensemble.predict(X)

        assert len(predictions) == 100
        assert all(0 <= pred < 3 for pred in predictions)

    def test_ensemble_predict_proba(self, mock_models, sample_data):
        """Test ensemble probability prediction."""
        X, y = sample_data
        ensemble = MockEnsembleModel(models=mock_models)

        # Should raise error if not fitted
        with pytest.raises(ValueError, match="must be fitted"):
            ensemble.predict_proba(X)

        # Fit and predict
        ensemble.fit(X, y)
        probabilities = ensemble.predict_proba(X)

        assert probabilities.shape == (100, 3)

        # Probabilities should sum to 1
        prob_sums = probabilities.sum(axis=1)
        assert np.allclose(prob_sums, 1.0)

    def test_empty_ensemble_error(self, sample_data):
        """Test error handling for empty ensemble."""
        X, y = sample_data
        ensemble = MockEnsembleModel()
        ensemble.is_fitted = True  # Simulate fitted state

        with pytest.raises(ValueError, match="No models in ensemble"):
            ensemble.predict(X)

        with pytest.raises(ValueError, match="No models in ensemble"):
            ensemble.predict_proba(X)


class TestModelRegistry:
    """Test model registry functionality."""

    @pytest.fixture
    def registry(self):
        """Create model registry."""
        return MockModelRegistry()

    @pytest.fixture
    def sample_model(self):
        """Create sample model."""
        from tests.unit.ml.test_models import MockMLModel

        return MockMLModel(name="sample_model")

    def test_registry_initialization(self, registry):
        """Test registry initialization."""
        assert registry.models == {}
        assert registry.metadata == {}

    def test_register_model(self, registry, sample_model):
        """Test model registration."""
        metadata = {"version": "1.0", "accuracy": 0.85}

        registry.register_model("test_model", sample_model, metadata)

        assert "test_model" in registry.models
        assert registry.models["test_model"] is sample_model
        assert registry.metadata["test_model"] == metadata

    def test_get_model(self, registry, sample_model):
        """Test getting registered model."""
        registry.register_model("test_model", sample_model)

        retrieved_model = registry.get_model("test_model")
        assert retrieved_model is sample_model

        # Test error for non-existent model
        with pytest.raises(KeyError, match="Model nonexistent not found"):
            registry.get_model("nonexistent")

    def test_list_models(self, registry, sample_model):
        """Test listing registered models."""
        assert registry.list_models() == []

        registry.register_model("model1", sample_model)
        registry.register_model("model2", sample_model)

        models = registry.list_models()
        assert len(models) == 2
        assert "model1" in models
        assert "model2" in models

    def test_get_metadata(self, registry, sample_model):
        """Test getting model metadata."""
        metadata = {"created": "2023-01-01", "type": "classifier"}
        registry.register_model("test_model", sample_model, metadata)

        retrieved_metadata = registry.get_metadata("test_model")
        assert retrieved_metadata == metadata

        # Test error for non-existent model
        with pytest.raises(KeyError, match="Model nonexistent not found"):
            registry.get_metadata("nonexistent")


@pytest.mark.unit
class TestEnsembleAndRegistryIntegration:
    """Integration tests for ensemble models and registry."""

    def test_ensemble_with_registry(self):
        """Test ensemble model with registry."""
        from tests.unit.ml.test_models import MockMLModel

        # Create models
        models = [MockMLModel(name=f"model_{i}") for i in range(3)]

        # Create registry and register models
        registry = MockModelRegistry()
        for i, model in enumerate(models):
            metadata = {"type": "classifier", "accuracy": 0.8 + i * 0.05}
            registry.register_model(f"model_{i}", model, metadata)

        # Create ensemble from registered models
        ensemble = MockEnsembleModel(name="registered_ensemble")
        for model_name in registry.list_models():
            model = registry.get_model(model_name)
            ensemble.add_model(model)

        # Test ensemble functionality
        np.random.seed(42)
        X = np.random.randn(50, 8)
        y = np.random.randint(0, 3, 50)

        ensemble.fit(X, y)
        predictions = ensemble.predict(X)
        probabilities = ensemble.predict_proba(X)

        assert len(predictions) == 50
        assert probabilities.shape == (50, 3)
        assert len(ensemble.models) == 3

    def test_model_versioning(self):
        """Test model versioning in registry."""
        from tests.unit.ml.test_models import MockMLModel

        registry = MockModelRegistry()

        # Register different versions of same model
        for version in ["1.0", "1.1", "2.0"]:
            model = MockMLModel(name=f"model_v{version}")
            metadata = {
                "version": version,
                "improvements": f"version_{version}_improvements",
            }
            registry.register_model(f"trading_model_v{version}", model, metadata)

        # Test that all versions are registered
        models = registry.list_models()
        assert len(models) == 3

        # Test metadata retrieval
        v2_metadata = registry.get_metadata("trading_model_v2.0")
        assert v2_metadata["version"] == "2.0"

    def test_ensemble_performance_comparison(self):
        """Test ensemble vs individual model performance."""
        from tests.unit.ml.test_models import MockMLModel

        np.random.seed(42)
        X = np.random.randn(200, 12)
        y = np.random.randint(0, 3, 200)

        # Create individual models
        individual_models = [MockMLModel(name=f"individual_{i}") for i in range(3)]

        # Create ensemble
        ensemble = MockEnsembleModel(
            name="performance_ensemble", models=individual_models.copy()
        )

        # Fit all models
        for model in individual_models:
            model.fit(X, y)
        ensemble.fit(X, y)

        # Get predictions
        individual_predictions = [model.predict(X) for model in individual_models]
        ensemble_predictions = ensemble.predict(X)

        # Validate predictions
        assert len(ensemble_predictions) == 200
        assert all(len(pred) == 200 for pred in individual_predictions)

        # Ensemble predictions should be different from any single model
        # (due to voting mechanism)
        assert not np.array_equal(ensemble_predictions, individual_predictions[0])


@pytest.mark.performance
def test_ensemble_performance():
    """Test ensemble model performance."""
    import time

    from tests.unit.ml.test_models import MockMLModel

    # Create large dataset
    np.random.seed(42)
    X = np.random.randn(5000, 20)
    y = np.random.randint(0, 3, 5000)

    # Create ensemble with multiple models
    models = [MockMLModel(name=f"perf_model_{i}") for i in range(5)]
    ensemble = MockEnsembleModel(name="performance_ensemble", models=models)

    # Test fitting time
    start_time = time.time()
    ensemble.fit(X, y)
    fit_time = time.time() - start_time

    # Test prediction time
    start_time = time.time()
    predictions = ensemble.predict(X)
    predict_time = time.time() - start_time

    # Performance checks
    assert fit_time < 2.0  # Should be reasonable for mock models
    assert predict_time < 1.0
    assert len(predictions) == 5000
