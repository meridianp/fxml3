"""
Unit tests for Machine Learning Pipeline.

Tests comprehensive ML pipeline functionality including:
- Feature engineering and preprocessing
- Model training and validation
- Hyperparameter optimization
- Model selection and ensemble methods
- Real-time predictions
- Model versioning and deployment
- Performance monitoring
- Feature importance analysis
- Cross-validation strategies
- Model interpretability
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from freezegun import freeze_time
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from core.ml.ml_pipeline import (
    FeatureEngineer,
    MLPipeline,
    ModelEvaluator,
    ModelTrainer,
    ModelType,
    PredictionService,
)


class TestMLPipeline:
    """Test suite for machine learning pipeline."""

    @pytest.fixture
    def pipeline_config(self):
        """Configuration for ML pipeline."""
        return {
            "models": ["random_forest", "xgboost", "lstm", "ensemble"],
            "feature_engineering": {
                "technical_indicators": True,
                "elliott_wave_features": True,
                "market_microstructure": True,
                "sentiment_features": True,
                "lag_features": [1, 5, 10, 20],
                "rolling_windows": [5, 10, 20, 50],
            },
            "training": {
                "train_test_split": 0.8,
                "validation_split": 0.2,
                "cross_validation_folds": 5,
                "early_stopping_rounds": 10,
                "max_epochs": 100,
                "batch_size": 32,
            },
            "hyperparameter_tuning": {
                "method": "bayesian",
                "n_trials": 50,
                "timeout_seconds": 3600,
            },
            "ensemble": {
                "voting_type": "soft",
                "weights": "optimized",
                "meta_learner": "linear",
            },
            "monitoring": {
                "track_metrics": True,
                "alert_threshold": 0.1,
                "retraining_trigger": "performance_degradation",
            },
        }

    @pytest.fixture
    def sample_market_data(self):
        """Generate sample market data for ML training."""
        dates = pd.date_range(start="2024-01-01", periods=1000, freq="h")

        # Generate synthetic price data with patterns
        np.random.seed(42)
        trend = np.linspace(1.0500, 1.1000, 1000)
        seasonality = 0.005 * np.sin(np.linspace(0, 8 * np.pi, 1000))
        noise = np.random.normal(0, 0.001, 1000)

        prices = trend + seasonality + noise

        df = pd.DataFrame(
            {
                "timestamp": dates,
                "open": prices + np.random.uniform(-0.0005, 0.0005, 1000),
                "high": prices + np.abs(np.random.uniform(0, 0.001, 1000)),
                "low": prices - np.abs(np.random.uniform(0, 0.001, 1000)),
                "close": prices,
                "volume": np.random.randint(100000, 1000000, 1000),
                "bid": prices - 0.0001,
                "ask": prices + 0.0001,
                "spread": 0.0002,
            }
        )

        # Add target variable (next price movement)
        df["target"] = df["close"].shift(-1) - df["close"]

        return df.dropna()

    @pytest.fixture
    def ml_pipeline(self, pipeline_config):
        """Create ML pipeline for testing."""
        return MLPipeline(config=pipeline_config)

    @pytest.mark.asyncio
    async def test_feature_engineering(self, ml_pipeline, sample_market_data):
        """Test feature engineering and preprocessing."""
        features = await ml_pipeline.engineer_features(sample_market_data)

        assert "features" in features
        assert "feature_names" in features
        assert len(features["feature_names"]) > 20  # Should have many features

        # Check for specific feature categories
        feature_names = features["feature_names"]
        assert any("sma" in name for name in feature_names)  # Technical indicators
        assert any("rsi" in name for name in feature_names)
        assert any("lag" in name for name in feature_names)  # Lag features
        assert any("rolling" in name for name in feature_names)  # Rolling features

        # Check data shape
        assert features["features"].shape[0] == len(sample_market_data) - max(
            ml_pipeline.config["feature_engineering"]["lag_features"]
        )

    @pytest.mark.asyncio
    async def test_trains_random_forest_model(self, ml_pipeline, sample_market_data):
        """Test training Random Forest model."""
        result = await ml_pipeline.train_model(
            data=sample_market_data, model_type=ModelType.RANDOM_FOREST
        )

        assert result["status"] == "trained"
        assert "model" in result
        assert "metrics" in result
        assert "feature_importance" in result
        assert result["metrics"]["training_score"] > 0
        assert "mse" in result["metrics"]
        assert "mae" in result["metrics"]

    @pytest.mark.asyncio
    async def test_trains_xgboost_model(self, ml_pipeline, sample_market_data):
        """Test training XGBoost model."""
        result = await ml_pipeline.train_model(
            data=sample_market_data, model_type=ModelType.XGBOOST
        )

        assert result["status"] == "trained"
        assert result["model_type"] == ModelType.XGBOOST
        assert "validation_score" in result["metrics"]
        assert result["metrics"]["validation_score"] > 0

    @pytest.mark.asyncio
    async def test_trains_lstm_model(self, ml_pipeline, sample_market_data):
        """Test training LSTM neural network model."""
        result = await ml_pipeline.train_model(
            data=sample_market_data, model_type=ModelType.LSTM
        )

        assert result["status"] == "trained"
        assert result["model_type"] == ModelType.LSTM
        assert "epochs_trained" in result
        assert "loss_history" in result
        assert result["architecture"]["type"] == "LSTM"

    @pytest.mark.asyncio
    async def test_hyperparameter_optimization(self, ml_pipeline, sample_market_data):
        """Test Bayesian hyperparameter optimization."""
        result = await ml_pipeline.optimize_hyperparameters(
            data=sample_market_data,
            model_type=ModelType.RANDOM_FOREST,
            n_trials=10,  # Reduced for testing
        )

        assert "best_params" in result
        assert "best_score" in result
        assert "optimization_history" in result
        assert len(result["optimization_history"]) == 10
        assert result["best_score"] > 0

        # Check parameter ranges were explored
        assert "n_estimators" in result["best_params"]
        assert "max_depth" in result["best_params"]

    @pytest.mark.asyncio
    async def test_cross_validation(self, ml_pipeline, sample_market_data):
        """Test k-fold cross-validation."""
        result = await ml_pipeline.cross_validate(
            data=sample_market_data,
            model_type=ModelType.RANDOM_FOREST,
            n_folds=3,  # Reduced for testing
        )

        assert "cv_scores" in result
        assert len(result["cv_scores"]) == 3
        assert "mean_score" in result
        assert "std_score" in result
        assert result["mean_score"] > 0
        assert result["std_score"] >= 0

    @pytest.mark.asyncio
    async def test_ensemble_model_creation(self, ml_pipeline, sample_market_data):
        """Test ensemble model combining multiple algorithms."""
        result = await ml_pipeline.create_ensemble(
            data=sample_market_data, base_models=["random_forest", "xgboost"]
        )

        assert result["status"] == "ensemble_created"
        assert "ensemble_model" in result
        assert "base_model_weights" in result
        assert len(result["base_model_weights"]) == 2
        assert sum(result["base_model_weights"].values()) == pytest.approx(1.0)
        assert "ensemble_score" in result

    @pytest.mark.asyncio
    async def test_real_time_prediction(self, ml_pipeline, sample_market_data):
        """Test real-time prediction serving."""
        # Train model first
        await ml_pipeline.train_model(sample_market_data, ModelType.RANDOM_FOREST)

        # Make prediction
        latest_data = sample_market_data.iloc[-1:].drop("target", axis=1)
        prediction = await ml_pipeline.predict(latest_data)

        assert "prediction" in prediction
        assert "confidence" in prediction
        assert "timestamp" in prediction
        assert "model_version" in prediction
        assert isinstance(prediction["prediction"], (float, np.float64))
        assert 0 <= prediction["confidence"] <= 1

    @pytest.mark.asyncio
    async def test_batch_predictions(self, ml_pipeline, sample_market_data):
        """Test batch prediction processing."""
        # Train model first
        await ml_pipeline.train_model(sample_market_data, ModelType.RANDOM_FOREST)

        # Make batch predictions
        batch_data = sample_market_data.iloc[-10:].drop("target", axis=1)
        predictions = await ml_pipeline.predict_batch(batch_data)

        assert "predictions" in predictions
        assert len(predictions["predictions"]) == 10
        assert "processing_time_ms" in predictions
        assert all("prediction" in p for p in predictions["predictions"])

    @pytest.mark.asyncio
    async def test_feature_importance_analysis(self, ml_pipeline, sample_market_data):
        """Test feature importance extraction and ranking."""
        # Train model first
        result = await ml_pipeline.train_model(
            sample_market_data, ModelType.RANDOM_FOREST
        )

        importance = await ml_pipeline.get_feature_importance()

        assert "features" in importance
        assert len(importance["features"]) > 0
        assert all("name" in f and "importance" in f for f in importance["features"])

        # Check features are sorted by importance
        importances = [f["importance"] for f in importance["features"]]
        assert importances == sorted(importances, reverse=True)

    @pytest.mark.asyncio
    async def test_model_versioning(self, ml_pipeline, sample_market_data):
        """Test model versioning and management."""
        # Train multiple versions
        v1 = await ml_pipeline.train_model(sample_market_data, ModelType.RANDOM_FOREST)
        v2 = await ml_pipeline.train_model(sample_market_data, ModelType.XGBOOST)

        versions = await ml_pipeline.list_model_versions()

        assert len(versions) >= 2
        assert all("version" in v for v in versions)
        assert all("timestamp" in v for v in versions)
        assert all("model_type" in v for v in versions)
        assert all("metrics" in v for v in versions)

    @pytest.mark.asyncio
    async def test_model_deployment(self, ml_pipeline, sample_market_data):
        """Test model deployment and activation."""
        # Train and deploy model
        training_result = await ml_pipeline.train_model(
            sample_market_data, ModelType.RANDOM_FOREST
        )

        deployment = await ml_pipeline.deploy_model(
            model_version=training_result["version"], environment="production"
        )

        assert deployment["status"] == "deployed"
        assert deployment["environment"] == "production"
        assert "deployment_id" in deployment
        assert "health_check" in deployment
        assert deployment["health_check"] == "healthy"

    @pytest.mark.asyncio
    async def test_performance_monitoring(self, ml_pipeline, sample_market_data):
        """Test model performance monitoring and alerting."""
        # Train and deploy model
        await ml_pipeline.train_model(sample_market_data, ModelType.RANDOM_FOREST)

        # Monitor performance
        monitoring = await ml_pipeline.monitor_performance(
            time_window="1h", metrics=["mse", "mae", "directional_accuracy"]
        )

        assert "metrics" in monitoring
        assert "mse" in monitoring["metrics"]
        assert "mae" in monitoring["metrics"]
        assert "alerts" in monitoring
        assert "drift_detected" in monitoring

    @pytest.mark.asyncio
    async def test_automatic_retraining(self, ml_pipeline, sample_market_data):
        """Test automatic model retraining on performance degradation."""
        # Train initial model
        initial = await ml_pipeline.train_model(
            sample_market_data, ModelType.RANDOM_FOREST
        )

        # Simulate performance degradation
        ml_pipeline._simulate_degradation = True

        # Trigger retraining check
        retraining = await ml_pipeline.check_retraining_needed()

        assert retraining["needs_retraining"] is True
        assert "reason" in retraining
        assert "degradation_score" in retraining

        # Perform retraining
        new_model = await ml_pipeline.retrain_model(sample_market_data)

        assert new_model["status"] == "retrained"
        assert new_model["version"] != initial["version"]

    @pytest.mark.asyncio
    async def test_model_interpretability(self, ml_pipeline, sample_market_data):
        """Test model interpretability features (SHAP values)."""
        # Train model
        await ml_pipeline.train_model(sample_market_data, ModelType.RANDOM_FOREST)

        # Get interpretability analysis
        interpretation = await ml_pipeline.explain_prediction(
            data=sample_market_data.iloc[-1:].drop("target", axis=1)
        )

        assert "shap_values" in interpretation
        assert "feature_contributions" in interpretation
        assert "baseline_value" in interpretation
        assert len(interpretation["feature_contributions"]) > 0

    @pytest.mark.asyncio
    async def test_online_learning(self, ml_pipeline):
        """Test online learning with streaming data."""
        # Initialize online learner
        online_model = await ml_pipeline.initialize_online_learner(
            model_type=ModelType.SGD_REGRESSOR
        )

        assert online_model["status"] == "initialized"

        # Stream data points
        for i in range(10):
            data_point = {"features": np.random.randn(10), "target": np.random.randn()}

            update = await ml_pipeline.update_online_model(data_point)
            assert update["status"] == "updated"
            assert "samples_seen" in update
            assert update["samples_seen"] == i + 1

    @pytest.mark.asyncio
    async def test_multi_target_prediction(self, ml_pipeline, sample_market_data):
        """Test prediction of multiple targets simultaneously."""
        # Add multiple targets
        sample_market_data["target_1h"] = sample_market_data["close"].shift(-1)
        sample_market_data["target_4h"] = sample_market_data["close"].shift(-4)
        sample_market_data["target_1d"] = sample_market_data["close"].shift(-24)

        result = await ml_pipeline.train_multi_target_model(
            data=sample_market_data, targets=["target_1h", "target_4h", "target_1d"]
        )

        assert result["status"] == "trained"
        assert "models" in result
        assert len(result["models"]) == 3
        assert all(f"target_{t}" in result["metrics"] for t in ["1h", "4h", "1d"])

    @pytest.mark.asyncio
    async def test_handles_missing_data(self, ml_pipeline):
        """Test handling of missing data in pipeline."""
        # Create data with missing values
        data = pd.DataFrame(
            {
                "feature1": [1, 2, np.nan, 4, 5],
                "feature2": [np.nan, 2, 3, 4, 5],
                "feature3": [1, 2, 3, np.nan, np.nan],
                "target": [0.1, 0.2, 0.3, 0.4, 0.5],
            }
        )

        result = await ml_pipeline.handle_missing_data(data=data, strategy="impute")

        assert result["missing_handled"] is True
        assert "imputation_methods" in result
        assert not result["processed_data"].isnull().any().any()

    @pytest.mark.asyncio
    async def test_feature_selection(self, ml_pipeline, sample_market_data):
        """Test automatic feature selection."""
        result = await ml_pipeline.select_features(
            data=sample_market_data, method="mutual_information", n_features=10
        )

        assert "selected_features" in result
        assert len(result["selected_features"]) == 10
        assert "feature_scores" in result
        assert all(f in result["feature_scores"] for f in result["selected_features"])

    @pytest.mark.asyncio
    async def test_model_compression(self, ml_pipeline, sample_market_data):
        """Test model compression for deployment."""
        # Train large model
        result = await ml_pipeline.train_model(
            sample_market_data, ModelType.RANDOM_FOREST, n_estimators=100
        )

        # Compress model
        compressed = await ml_pipeline.compress_model(
            model_version=result["version"], compression_method="pruning"
        )

        assert compressed["status"] == "compressed"
        assert compressed["size_reduction_percent"] > 0
        assert compressed["performance_impact"] < 0.05  # Less than 5% degradation

    @pytest.mark.asyncio
    async def test_distributed_training(self, ml_pipeline, sample_market_data):
        """Test distributed model training across multiple workers."""
        result = await ml_pipeline.train_distributed(
            data=sample_market_data, model_type=ModelType.XGBOOST, n_workers=2
        )

        assert result["status"] == "trained"
        assert result["training_mode"] == "distributed"
        assert "workers_used" in result
        assert result["workers_used"] == 2
        assert "speedup_factor" in result
