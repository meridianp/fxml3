"""
Comprehensive retrospective test coverage for ML Training Pipeline.

This module provides comprehensive test coverage for the FXML4 ML training pipeline,
which handles model training, validation, evaluation, and hyperparameter optimization
for forex trading models.

Following TDD principles with retrospective testing approach:
- Testing existing production ML training functionality
- Ensuring comprehensive coverage of training workflows and evaluation
- Validating time series cross-validation and model performance metrics
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import ANY, AsyncMock, MagicMock, call, patch

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score
from sklearn.model_selection import TimeSeriesSplit

from fxml4.ml.models import ClassicMLModel, EnsembleModel
from fxml4.ml.training import (
    ModelTrainingPipeline,
    PerformanceMetrics,
    TrainingConfig,
    ValidationResults,
    create_time_series_splits,
    create_trading_metrics,
    evaluate_model_performance,
    hyperparameter_optimization,
    train_model_pipeline,
)


class TestMLTrainingTimeSeries:
    """Test time series cross-validation functionality."""

    def test_create_time_series_splits_default_params(self):
        """Test time series splits with default parameters."""
        # Create sample time series data
        dates = pd.date_range("2024-01-01", periods=1000, freq="1H")
        X = pd.DataFrame(
            {
                "feature_1": np.random.randn(1000),
                "feature_2": np.random.randn(1000),
                "timestamp": dates,
            }
        )
        y = pd.Series(np.random.randint(0, 3, 1000))

        splits = create_time_series_splits(X, y, n_splits=5)

        assert len(splits) == 5

        # Verify splits maintain temporal order
        for i, (train_idx, test_idx) in enumerate(splits):
            assert len(train_idx) > 0
            assert len(test_idx) > 0
            assert max(train_idx) < min(test_idx)  # No data leakage

    def test_create_time_series_splits_with_gap(self):
        """Test time series splits with gap between train and test."""
        X = pd.DataFrame(np.random.randn(500, 3))
        y = pd.Series(np.random.randint(0, 3, 500))

        gap = 10
        splits = create_time_series_splits(X, y, n_splits=3, gap=gap)

        for train_idx, test_idx in splits:
            # Verify gap is maintained
            assert min(test_idx) - max(train_idx) >= gap

    def test_create_time_series_splits_custom_train_pct(self):
        """Test time series splits with custom training percentage."""
        X = pd.DataFrame(np.random.randn(1000, 4))
        y = pd.Series(np.random.randint(0, 3, 1000))

        splits = create_time_series_splits(X, y, n_splits=3, train_pct=0.9)

        for train_idx, test_idx in splits:
            # Training set should be larger with higher train_pct
            assert len(train_idx) > len(test_idx)

    def test_time_series_splits_invalid_params(self):
        """Test time series splits with invalid parameters."""
        X = pd.DataFrame(np.random.randn(100, 2))
        y = pd.Series(np.random.randint(0, 3, 100))

        # Invalid n_splits
        with pytest.raises(ValueError):
            create_time_series_splits(X, y, n_splits=0)

        # Invalid train_pct
        with pytest.raises(ValueError):
            create_time_series_splits(X, y, train_pct=1.5)

    def test_time_series_splits_insufficient_data(self):
        """Test time series splits with insufficient data."""
        # Very small dataset
        X = pd.DataFrame(np.random.randn(10, 2))
        y = pd.Series(np.random.randint(0, 3, 10))

        # Should handle gracefully
        splits = create_time_series_splits(X, y, n_splits=2)
        assert len(splits) <= 2


class TestMLModelTrainingPipeline:
    """Test core model training pipeline functionality."""

    @pytest.fixture
    def sample_training_data(self):
        """Create sample training data for testing."""
        dates = pd.date_range("2024-01-01", periods=1000, freq="1H")
        X = pd.DataFrame(
            {
                "rsi": np.random.uniform(0, 100, 1000),
                "macd": np.random.randn(1000),
                "bollinger_ratio": np.random.uniform(-2, 2, 1000),
                "volume": np.random.exponential(1000, 1000),
                "returns": np.random.randn(1000) * 0.01,
                "timestamp": dates,
            }
        )
        # Create trading signals (0=Hold, 1=Buy, 2=Sell)
        y = pd.Series(np.random.choice([0, 1, 2], 1000, p=[0.6, 0.2, 0.2]))
        return X, y

    @pytest.fixture
    def training_config(self):
        """Create training configuration for testing."""
        return TrainingConfig(
            model_type="random_forest",
            n_splits=3,
            test_size=0.2,
            random_state=42,
            hyperparameters={
                "n_estimators": 100,
                "max_depth": 10,
                "min_samples_split": 5,
            },
            evaluation_metrics=["accuracy", "precision", "recall", "f1"],
            save_model=True,
        )

    def test_model_training_pipeline_initialization(self, training_config):
        """Test training pipeline initialization."""
        pipeline = ModelTrainingPipeline(training_config)

        assert pipeline.config == training_config
        assert pipeline.model is None
        assert pipeline.training_results is None
        assert pipeline.validation_results is None

    @patch("fxml4.ml.models.ClassicMLModel")
    def test_train_model_pipeline_success(
        self, mock_model_class, sample_training_data, training_config
    ):
        """Test successful model training pipeline execution."""
        X, y = sample_training_data

        # Mock model
        mock_model = MagicMock()
        mock_model.fit.return_value = mock_model
        mock_model.predict.return_value = np.random.randint(0, 3, len(X))
        mock_model.predict_proba.return_value = np.random.rand(len(X), 3)
        mock_model_class.return_value = mock_model

        pipeline = ModelTrainingPipeline(training_config)
        results = pipeline.train(X, y)

        assert results is not None
        assert "train_score" in results
        assert "validation_score" in results
        assert "model_path" in results
        mock_model.fit.assert_called()

    def test_model_training_with_time_series_cv(
        self, sample_training_data, training_config
    ):
        """Test model training with time series cross-validation."""
        X, y = sample_training_data
        training_config.cv_method = "time_series"

        with patch("fxml4.ml.training.create_time_series_splits") as mock_splits:
            mock_splits.return_value = [(np.arange(700), np.arange(700, 800))]

            with patch("sklearn.ensemble.RandomForestClassifier") as mock_rf:
                mock_model = MagicMock()
                mock_model.fit.return_value = mock_model
                mock_model.predict.return_value = np.ones(100)
                mock_rf.return_value = mock_model

                pipeline = ModelTrainingPipeline(training_config)
                results = pipeline.train(X, y)

                mock_splits.assert_called_once()
                assert results is not None

    def test_hyperparameter_optimization(self, sample_training_data):
        """Test hyperparameter optimization functionality."""
        X, y = sample_training_data

        param_grid = {
            "n_estimators": [50, 100],
            "max_depth": [5, 10],
            "min_samples_split": [2, 5],
        }

        with patch("sklearn.model_selection.TimeSeriesSplit") as mock_tscv:
            mock_tscv.return_value.split.return_value = [
                (np.arange(700), np.arange(700, 800))
            ]

            with patch("sklearn.ensemble.RandomForestClassifier") as mock_rf:
                mock_model = MagicMock()
                mock_model.fit.return_value = mock_model
                mock_model.predict.return_value = np.ones(100)
                mock_model.score.return_value = 0.85
                mock_rf.return_value = mock_model

                best_params, best_score = hyperparameter_optimization(
                    X, y, param_grid, cv_folds=3, scoring="accuracy"
                )

                assert best_params is not None
                assert isinstance(best_score, float)
                assert 0 <= best_score <= 1

    def test_model_training_error_handling(self, sample_training_data, training_config):
        """Test error handling in model training pipeline."""
        X, y = sample_training_data

        # Test with invalid model type
        training_config.model_type = "invalid_model"
        pipeline = ModelTrainingPipeline(training_config)

        with pytest.raises(ValueError, match="Unknown model type"):
            pipeline.train(X, y)

    def test_model_training_insufficient_data(self, training_config):
        """Test model training with insufficient data."""
        # Very small dataset
        X = pd.DataFrame(np.random.randn(10, 3))
        y = pd.Series(np.random.randint(0, 3, 10))

        pipeline = ModelTrainingPipeline(training_config)

        with pytest.raises(ValueError, match="Insufficient data"):
            pipeline.train(X, y)


class TestMLModelEvaluation:
    """Test model evaluation and performance metrics."""

    def test_evaluate_model_performance_classification(self):
        """Test model performance evaluation for classification."""
        # Mock predictions and ground truth
        y_true = np.array([0, 1, 2, 0, 1, 2, 0, 1, 2])
        y_pred = np.array([0, 1, 2, 0, 2, 1, 0, 1, 2])
        y_proba = np.random.rand(9, 3)
        y_proba = y_proba / y_proba.sum(axis=1, keepdims=True)  # Normalize

        metrics = evaluate_model_performance(
            y_true, y_pred, y_proba, task_type="classification"
        )

        assert "accuracy" in metrics
        assert "precision" in metrics
        assert "recall" in metrics
        assert "f1_score" in metrics
        assert "confusion_matrix" in metrics

        # Verify metric ranges
        assert 0 <= metrics["accuracy"] <= 1
        assert 0 <= metrics["precision"] <= 1
        assert 0 <= metrics["recall"] <= 1

    def test_create_trading_metrics(self):
        """Test creation of trading-specific performance metrics."""
        # Mock trading predictions and returns
        y_pred = np.array([0, 1, 2, 0, 1, 2, 1, 1, 0])  # 0=Hold, 1=Buy, 2=Sell
        returns = np.array(
            [0.01, -0.005, 0.02, -0.01, 0.015, -0.008, 0.012, 0.005, 0.003]
        )

        trading_metrics = create_trading_metrics(y_pred, returns)

        assert "total_return" in trading_metrics
        assert "sharpe_ratio" in trading_metrics
        assert "max_drawdown" in trading_metrics
        assert "win_rate" in trading_metrics
        assert "profit_factor" in trading_metrics

        # Verify return calculation
        buy_signals = y_pred == 1
        sell_signals = y_pred == 2
        expected_return = np.sum(returns[buy_signals]) - np.sum(returns[sell_signals])
        assert abs(trading_metrics["total_return"] - expected_return) < 0.001

    def test_trading_metrics_no_signals(self):
        """Test trading metrics with no buy/sell signals."""
        y_pred = np.zeros(100)  # All hold signals
        returns = np.random.randn(100) * 0.01

        trading_metrics = create_trading_metrics(y_pred, returns)

        assert trading_metrics["total_return"] == 0.0
        assert trading_metrics["win_rate"] == 0.0
        assert trading_metrics["profit_factor"] is None  # No trades

    def test_performance_metrics_with_probabilities(self):
        """Test performance evaluation with prediction probabilities."""
        y_true = np.random.randint(0, 3, 100)
        y_pred = np.random.randint(0, 3, 100)
        y_proba = np.random.rand(100, 3)
        y_proba = y_proba / y_proba.sum(axis=1, keepdims=True)

        metrics = evaluate_model_performance(
            y_true, y_pred, y_proba, task_type="classification"
        )

        assert "roc_auc" in metrics
        assert "log_loss" in metrics

        # Verify probability-based metrics
        assert 0 <= metrics["log_loss"]  # Log loss should be non-negative


class TestMLTrainingConfiguration:
    """Test training configuration and parameter validation."""

    def test_training_config_validation(self):
        """Test training configuration validation."""
        # Valid configuration
        config = TrainingConfig(
            model_type="random_forest", n_splits=5, test_size=0.2, random_state=42
        )

        assert config.model_type == "random_forest"
        assert config.n_splits == 5
        assert config.test_size == 0.2

    def test_training_config_invalid_params(self):
        """Test training configuration with invalid parameters."""
        # Invalid test_size
        with pytest.raises(ValueError):
            TrainingConfig(model_type="random_forest", test_size=1.5)

        # Invalid n_splits
        with pytest.raises(ValueError):
            TrainingConfig(model_type="random_forest", n_splits=0)

    def test_training_config_defaults(self):
        """Test training configuration default values."""
        config = TrainingConfig(model_type="random_forest")

        assert config.n_splits == 5  # Default value
        assert config.test_size == 0.2  # Default value
        assert config.random_state is not None

    def test_hyperparameter_validation(self):
        """Test hyperparameter validation in configuration."""
        # Valid hyperparameters for random forest
        config = TrainingConfig(
            model_type="random_forest",
            hyperparameters={
                "n_estimators": 100,
                "max_depth": 10,
                "min_samples_split": 2,
            },
        )

        assert config.hyperparameters["n_estimators"] == 100

    def test_evaluation_metrics_validation(self):
        """Test evaluation metrics validation."""
        # Valid metrics
        config = TrainingConfig(
            model_type="random_forest",
            evaluation_metrics=["accuracy", "precision", "recall", "f1"],
        )

        assert "accuracy" in config.evaluation_metrics

        # Invalid metric
        with pytest.raises(ValueError):
            TrainingConfig(
                model_type="random_forest", evaluation_metrics=["invalid_metric"]
            )


class TestMLTrainingIntegration:
    """Test integration scenarios and complete training workflows."""

    @pytest.fixture
    def forex_training_data(self):
        """Create realistic forex training data."""
        dates = pd.date_range("2024-01-01", periods=2000, freq="1H")

        # Create realistic technical indicators
        price_base = 1.1000 + np.cumsum(np.random.randn(2000) * 0.0001)

        X = pd.DataFrame(
            {
                "rsi": np.random.uniform(20, 80, 2000),
                "macd": np.random.randn(2000) * 0.0001,
                "macd_signal": np.random.randn(2000) * 0.0001,
                "bollinger_upper": price_base + np.random.uniform(0.001, 0.002, 2000),
                "bollinger_lower": price_base - np.random.uniform(0.001, 0.002, 2000),
                "atr": np.random.uniform(0.0005, 0.002, 2000),
                "volume": np.random.exponential(1000, 2000),
                "hour": [d.hour for d in dates],
                "day_of_week": [d.weekday() for d in dates],
                "returns_1": np.random.randn(2000) * 0.001,
                "returns_5": np.random.randn(2000) * 0.002,
                "volatility": np.random.uniform(0.0001, 0.001, 2000),
                "timestamp": dates,
            }
        )

        # Generate realistic trading signals based on indicators
        signals = []
        for i in range(2000):
            if X.loc[i, "rsi"] < 30 and X.loc[i, "macd"] > 0:
                signals.append(1)  # Buy
            elif X.loc[i, "rsi"] > 70 and X.loc[i, "macd"] < 0:
                signals.append(2)  # Sell
            else:
                signals.append(0)  # Hold

        y = pd.Series(signals)
        return X, y

    def test_complete_training_workflow(self, forex_training_data):
        """Test complete training workflow from data to deployed model."""
        X, y = forex_training_data

        config = TrainingConfig(
            model_type="random_forest",
            n_splits=3,
            hyperparameters={
                "n_estimators": 50,  # Smaller for testing
                "max_depth": 8,
                "min_samples_split": 5,
                "random_state": 42,
            },
            evaluation_metrics=["accuracy", "precision", "recall"],
            save_model=True,
        )

        with patch("joblib.dump") as mock_save:
            with patch("sklearn.ensemble.RandomForestClassifier") as mock_rf:
                mock_model = MagicMock()
                mock_model.fit.return_value = mock_model
                mock_model.predict.return_value = np.random.randint(0, 3, len(X))
                mock_model.predict_proba.return_value = np.random.rand(len(X), 3)
                mock_model.score.return_value = 0.75
                mock_rf.return_value = mock_model

                pipeline = ModelTrainingPipeline(config)
                results = pipeline.train(X, y)

                assert results["train_score"] > 0
                assert results["validation_score"] > 0
                assert "model_path" in results
                mock_save.assert_called()  # Model should be saved

    def test_multi_model_comparison(self, forex_training_data):
        """Test training and comparison of multiple models."""
        X, y = forex_training_data

        model_configs = [
            TrainingConfig(
                model_type="random_forest", hyperparameters={"n_estimators": 50}
            ),
            TrainingConfig(
                model_type="gradient_boosting", hyperparameters={"n_estimators": 50}
            ),
            TrainingConfig(model_type="svm", hyperparameters={"C": 1.0}),
        ]

        results = {}

        for i, config in enumerate(model_configs):
            with patch(f"sklearn.ensemble.RandomForestClassifier") as mock_model_class:
                mock_model = MagicMock()
                mock_model.fit.return_value = mock_model
                mock_model.predict.return_value = np.random.randint(0, 3, len(X))
                mock_model.score.return_value = 0.7 + i * 0.05  # Increasing scores
                mock_model_class.return_value = mock_model

                pipeline = ModelTrainingPipeline(config)
                result = pipeline.train(X, y)
                results[config.model_type] = result

        # Should have results for all models
        assert len(results) == 3
        assert all("validation_score" in result for result in results.values())

    def test_trading_performance_validation(self, forex_training_data):
        """Test validation of trading performance metrics."""
        X, y = forex_training_data

        # Add returns data for trading metrics
        X["future_returns"] = np.random.randn(len(X)) * 0.001

        config = TrainingConfig(
            model_type="random_forest",
            evaluation_metrics=["accuracy", "trading_return", "sharpe_ratio"],
            hyperparameters={"n_estimators": 50, "random_state": 42},
        )

        with patch("sklearn.ensemble.RandomForestClassifier") as mock_rf:
            mock_model = MagicMock()
            mock_model.fit.return_value = mock_model

            # Generate realistic predictions
            predictions = np.random.choice([0, 1, 2], size=len(X), p=[0.7, 0.15, 0.15])
            mock_model.predict.return_value = predictions
            mock_model.score.return_value = 0.65
            mock_rf.return_value = mock_model

            pipeline = ModelTrainingPipeline(config)
            results = pipeline.train(X, y)

            assert "validation_score" in results
            assert results["validation_score"] > 0

    def test_model_persistence_and_loading(self, forex_training_data):
        """Test model saving and loading functionality."""
        X, y = forex_training_data

        config = TrainingConfig(
            model_type="random_forest",
            save_model=True,
            model_name="test_forex_model",
            hyperparameters={"n_estimators": 50, "random_state": 42},
        )

        with (
            patch("joblib.dump") as mock_save,
            patch("joblib.load") as mock_load,
            patch("sklearn.ensemble.RandomForestClassifier") as mock_rf,
        ):

            mock_model = MagicMock()
            mock_model.fit.return_value = mock_model
            mock_model.predict.return_value = np.random.randint(0, 3, 100)
            mock_model.score.return_value = 0.75
            mock_rf.return_value = mock_model

            # Train model
            pipeline = ModelTrainingPipeline(config)
            results = pipeline.train(X, y)

            # Verify model was saved
            mock_save.assert_called()
            save_path = mock_save.call_args[0][1]
            assert "test_forex_model" in save_path

            # Test loading
            mock_load.return_value = mock_model
            loaded_model = pipeline.load_model(save_path)

            assert loaded_model is not None
            mock_load.assert_called_with(save_path)

    def test_cross_validation_robustness(self, forex_training_data):
        """Test robustness of cross-validation across different market conditions."""
        X, y = forex_training_data

        # Add market regime indicators
        X["volatility_regime"] = np.random.choice(["low", "medium", "high"], len(X))
        X["trend_regime"] = np.random.choice(["bull", "bear", "sideways"], len(X))

        config = TrainingConfig(
            model_type="random_forest",
            n_splits=5,
            cv_method="time_series",
            hyperparameters={"n_estimators": 50, "random_state": 42},
        )

        with patch("fxml4.ml.training.create_time_series_splits") as mock_splits:
            # Create splits that represent different market conditions
            splits = [
                (np.arange(400), np.arange(400, 500)),  # Low volatility period
                (np.arange(500), np.arange(500, 600)),  # Medium volatility
                (np.arange(600), np.arange(600, 700)),  # High volatility
                (np.arange(700), np.arange(700, 800)),  # Bull market
                (np.arange(800), np.arange(800, 900)),  # Bear market
            ]
            mock_splits.return_value = splits

            with patch("sklearn.ensemble.RandomForestClassifier") as mock_rf:
                mock_model = MagicMock()
                mock_model.fit.return_value = mock_model
                mock_model.predict.return_value = np.random.randint(0, 3, 100)
                # Varying performance across market conditions
                mock_model.score.side_effect = [0.65, 0.70, 0.60, 0.75, 0.58]
                mock_rf.return_value = mock_model

                pipeline = ModelTrainingPipeline(config)
                results = pipeline.train(X, y)

                # Should complete training across all market conditions
                assert results["validation_score"] > 0
                assert mock_model.fit.call_count == 5  # One for each split
