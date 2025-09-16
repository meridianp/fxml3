"""
Tests for ML models.
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import tempfile

from fxml4_ml.models import (
    MLModel, RandomForestModel, XGBoostModel,
    LightGBMModel, LogisticRegressionModel, MLModelFactory
)


@pytest.fixture
def sample_data():
    """Create sample data for testing."""
    np.random.seed(42)
    n_samples = 1000
    n_features = 10
    
    # Create features
    X = pd.DataFrame(
        np.random.randn(n_samples, n_features),
        columns=[f"feature_{i}" for i in range(n_features)]
    )
    
    # Create target (3 classes)
    y = pd.Series(np.random.randint(0, 3, n_samples))
    
    return X, y


@pytest.fixture
def binary_data():
    """Create binary classification data."""
    np.random.seed(42)
    n_samples = 1000
    n_features = 10
    
    X = pd.DataFrame(
        np.random.randn(n_samples, n_features),
        columns=[f"feature_{i}" for i in range(n_features)]
    )
    
    y = pd.Series(np.random.randint(0, 2, n_samples))
    
    return X, y


class TestMLModels:
    """Test ML model implementations."""
    
    def test_random_forest_model(self, sample_data):
        """Test RandomForest model."""
        X, y = sample_data
        
        model = RandomForestModel(name="test_rf", n_estimators=10)
        assert model.model_type == "random_forest"
        assert not model.is_trained
        
        # Train model
        model.fit(X, y)
        assert model.is_trained
        assert model.feature_names == X.columns.tolist()
        
        # Make predictions
        predictions = model.predict(X)
        assert len(predictions) == len(y)
        assert all(pred in [0, 1, 2] for pred in predictions)
        
        # Get probabilities
        proba = model.predict_proba(X)
        assert proba.shape == (len(X), 3)
        assert np.allclose(proba.sum(axis=1), 1.0)
    
    def test_xgboost_model(self, sample_data):
        """Test XGBoost model."""
        X, y = sample_data
        
        model = XGBoostModel(name="test_xgb", n_estimators=10)
        assert model.model_type == "xgboost"
        
        model.fit(X, y)
        predictions = model.predict(X)
        assert len(predictions) == len(y)
    
    def test_lightgbm_model(self, sample_data):
        """Test LightGBM model."""
        X, y = sample_data
        
        model = LightGBMModel(name="test_lgb", n_estimators=10)
        assert model.model_type == "lightgbm"
        
        model.fit(X, y)
        predictions = model.predict(X)
        assert len(predictions) == len(y)
    
    def test_logistic_regression_model(self, sample_data):
        """Test Logistic Regression model."""
        X, y = sample_data
        
        model = LogisticRegressionModel(name="test_lr")
        assert model.model_type == "logistic_regression"
        
        model.fit(X, y)
        predictions = model.predict(X)
        assert len(predictions) == len(y)
    
    def test_model_save_load(self, sample_data):
        """Test model saving and loading."""
        X, y = sample_data
        
        # Train model
        model = RandomForestModel(name="test_save", n_estimators=10)
        model.fit(X, y)
        original_predictions = model.predict(X)
        
        # Save model
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "model.pkl"
            model.save(save_path)
            assert save_path.exists()
            
            # Load model
            loaded_model = RandomForestModel()
            loaded_model.load(save_path)
            
            assert loaded_model.is_trained
            assert loaded_model.metadata["name"] == "test_save"
            assert loaded_model.feature_names == model.feature_names
            
            # Check predictions are the same
            loaded_predictions = loaded_model.predict(X)
            np.testing.assert_array_equal(original_predictions, loaded_predictions)
    
    def test_model_factory(self):
        """Test MLModelFactory."""
        # Test creating models
        rf_model = MLModelFactory.create("random_forest", n_estimators=50)
        assert isinstance(rf_model, RandomForestModel)
        assert rf_model.model_params["n_estimators"] == 50
        
        xgb_model = MLModelFactory.create("xgboost", learning_rate=0.05)
        assert isinstance(xgb_model, XGBoostModel)
        assert xgb_model.model_params["learning_rate"] == 0.05
        
        # Test invalid model type
        with pytest.raises(ValueError, match="Unknown model type"):
            MLModelFactory.create("invalid_model")
    
    def test_binary_classification(self, binary_data):
        """Test binary classification."""
        X, y = binary_data
        
        model = XGBoostModel(name="test_binary", n_classes=2, n_estimators=10)
        model.fit(X, y)
        
        predictions = model.predict(X)
        assert all(pred in [0, 1] for pred in predictions)
        
        proba = model.predict_proba(X)
        assert proba.shape == (len(X), 2)
    
    def test_model_metadata(self, sample_data):
        """Test model metadata tracking."""
        X, y = sample_data
        
        model = RandomForestModel(name="test_metadata")
        assert "created_at" in model.metadata
        assert model.metadata["model_type"] == "random_forest"
        
        model.fit(X, y)
        assert "trained_at" in model.metadata
        assert model.metadata["n_samples"] == len(y)
    
    def test_predict_before_training(self):
        """Test prediction before training raises error."""
        model = RandomForestModel()
        X = pd.DataFrame(np.random.randn(10, 5))
        
        with pytest.raises(Exception, match="trained"):
            model.predict(X)
        
        with pytest.raises(Exception, match="trained"):
            model.predict_proba(X)