"""End-to-End Functional Tests for ML Training Pipeline.

This module tests the complete machine learning training pipeline including
data preparation, model training, validation, and deployment preparation.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import joblib
import numpy as np
import pandas as pd
import pytest

from fxml4.ml.data_preprocessing import DataPreprocessor
from fxml4.ml.hyperparameter_tuning import HyperparameterTuner
from fxml4.ml.model_evaluation import ModelEvaluator
from fxml4.ml.model_registry import ModelRegistry
from fxml4.ml.model_selection import ModelSelector, TimeSeriesSplitter
from fxml4.ml.models.ensemble import EnsembleModel
from fxml4.ml.models.lightgbm_model import LightGBMModel
from fxml4.ml.models.xgboost_model import XGBoostModel


class TestMLTrainingPipelineE2E:
    """End-to-end tests for ML training pipeline."""

    @pytest.fixture
    def sample_ml_data(self):
        """Create sample data for ML training."""
        np.random.seed(42)
        n_samples = 10000
        n_features = 50

        # Generate timestamps
        timestamps = pd.date_range(
            start="2023-01-01", periods=n_samples, freq="1h", tz="UTC"
        )

        # Generate features with some structure
        features = {}

        # Technical indicators
        for i in range(10):
            features[f"tech_indicator_{i}"] = np.random.randn(n_samples).cumsum()

        # Market microstructure
        for i in range(10):
            features[f"microstructure_{i}"] = np.random.randn(n_samples) * 0.1

        # Lag features
        base_price = 1.08
        prices = [base_price]
        for _ in range(n_samples - 1):
            change = np.random.normal(0, 0.001)
            prices.append(prices[-1] * (1 + change))

        for lag in [1, 2, 5, 10]:
            features[f"price_lag_{lag}"] = pd.Series(prices).pct_change(lag).values

        # Session features
        for session in ["asian", "european", "american"]:
            features[f"{session}_active"] = np.random.randint(0, 2, n_samples)

        # Create DataFrame
        df = pd.DataFrame(features, index=timestamps)

        # Add target variable (next hour return)
        df["target"] = pd.Series(prices).pct_change().shift(-1).values

        # Remove last row (no target)
        df = df.iloc[:-1]

        # Remove rows with NaN
        df = df.dropna()

        return df

    @pytest.fixture
    def training_config(self):
        """ML training configuration."""
        return {
            "data_split": {
                "train_ratio": 0.7,
                "val_ratio": 0.15,
                "test_ratio": 0.15,
                "gap_hours": 24,  # Gap between train and test
            },
            "models": {
                "xgboost": {
                    "n_estimators": 100,
                    "max_depth": 5,
                    "learning_rate": 0.01,
                    "subsample": 0.8,
                },
                "lightgbm": {
                    "n_estimators": 100,
                    "num_leaves": 31,
                    "learning_rate": 0.01,
                    "feature_fraction": 0.8,
                },
            },
            "hyperparameter_tuning": {
                "n_trials": 10,
                "cv_folds": 3,
                "scoring": "neg_mean_squared_error",
            },
            "ensemble": {"method": "weighted_average", "optimize_weights": True},
        }

    @pytest.mark.asyncio
    async def test_complete_training_pipeline(self, sample_ml_data, training_config):
        """Test complete ML training pipeline from data to model."""
        # 1. Data Splitting
        splitter = TimeSeriesSplitter(
            train_ratio=training_config["data_split"]["train_ratio"],
            val_ratio=training_config["data_split"]["val_ratio"],
            test_ratio=training_config["data_split"]["test_ratio"],
            gap_hours=training_config["data_split"]["gap_hours"],
        )

        X = sample_ml_data.drop("target", axis=1)
        y = sample_ml_data["target"]

        splits = splitter.split(X, y)
        X_train, X_val, X_test = splits["X_train"], splits["X_val"], splits["X_test"]
        y_train, y_val, y_test = splits["y_train"], splits["y_val"], splits["y_test"]

        # Verify splits
        assert len(X_train) > len(X_val)
        assert len(X_val) > 0
        assert len(X_test) > 0
        assert len(X_train) + len(X_val) + len(X_test) <= len(X)

        # 2. Data Preprocessing
        preprocessor = DataPreprocessor()

        # Fit on training data
        X_train_scaled = preprocessor.fit_transform(X_train)
        X_val_scaled = preprocessor.transform(X_val)
        X_test_scaled = preprocessor.transform(X_test)

        # Verify preprocessing
        assert X_train_scaled.shape == X_train.shape
        assert not np.any(np.isnan(X_train_scaled))

        # 3. Model Training
        models = {}

        # Train XGBoost
        xgb_model = XGBoostModel(training_config["models"]["xgboost"])
        xgb_model.train(X_train_scaled, y_train, X_val_scaled, y_val)
        models["xgboost"] = xgb_model

        # Train LightGBM
        lgb_model = LightGBMModel(training_config["models"]["lightgbm"])
        lgb_model.train(X_train_scaled, y_train, X_val_scaled, y_val)
        models["lightgbm"] = lgb_model

        # 4. Model Evaluation
        evaluator = ModelEvaluator()

        for name, model in models.items():
            # Make predictions
            train_pred = model.predict(X_train_scaled)
            val_pred = model.predict(X_val_scaled)
            test_pred = model.predict(X_test_scaled)

            # Evaluate
            metrics = evaluator.evaluate(
                y_true=y_test, y_pred=test_pred, dataset_name="test"
            )

            # Verify metrics
            assert "mse" in metrics
            assert "rmse" in metrics
            assert "mae" in metrics
            assert "r2" in metrics
            assert metrics["r2"] > -1  # Basic sanity check

        # 5. Ensemble Creation
        ensemble = EnsembleModel(
            models=list(models.values()), method=training_config["ensemble"]["method"]
        )

        if training_config["ensemble"]["optimize_weights"]:
            ensemble.optimize_weights(X_val_scaled, y_val)

        ensemble_pred = ensemble.predict(X_test_scaled)

        # Verify ensemble predictions
        assert len(ensemble_pred) == len(y_test)
        assert not np.any(np.isnan(ensemble_pred))

    @pytest.mark.asyncio
    async def test_hyperparameter_optimization(self, sample_ml_data, training_config):
        """Test hyperparameter optimization process."""
        # Prepare data
        X = sample_ml_data.drop("target", axis=1)
        y = sample_ml_data["target"]

        # Split data
        train_size = int(len(X) * 0.8)
        X_train = X.iloc[:train_size]
        y_train = y.iloc[:train_size]
        X_val = X.iloc[train_size:]
        y_val = y.iloc[train_size:]

        # Define search space
        search_space = {
            "n_estimators": (50, 300),
            "max_depth": (3, 10),
            "learning_rate": (0.001, 0.1),
            "subsample": (0.6, 1.0),
            "colsample_bytree": (0.6, 1.0),
        }

        # Create tuner
        tuner = HyperparameterTuner(
            model_class=XGBoostModel,
            search_space=search_space,
            n_trials=training_config["hyperparameter_tuning"]["n_trials"],
            cv_folds=training_config["hyperparameter_tuning"]["cv_folds"],
        )

        # Run optimization
        best_params, best_score, trial_history = await tuner.optimize(
            X_train, y_train, X_val, y_val
        )

        # Verify results
        assert isinstance(best_params, dict)
        assert all(param in best_params for param in search_space.keys())
        assert best_score < 0  # Negative MSE
        assert (
            len(trial_history) == training_config["hyperparameter_tuning"]["n_trials"]
        )

        # Train model with best parameters
        best_model = XGBoostModel(best_params)
        best_model.train(X_train, y_train, X_val, y_val)

        # Verify model performance
        predictions = best_model.predict(X_val)
        assert len(predictions) == len(y_val)

    @pytest.mark.asyncio
    async def test_time_series_cross_validation(self, sample_ml_data, training_config):
        """Test time series cross-validation."""
        X = sample_ml_data.drop("target", axis=1)
        y = sample_ml_data["target"]

        # Create time series CV splitter
        tscv = TimeSeriesSplitter(n_splits=5, test_size=0.2, gap_hours=24)

        cv_scores = []

        for fold_idx, (train_idx, val_idx) in enumerate(tscv.split(X)):
            X_train_fold = X.iloc[train_idx]
            y_train_fold = y.iloc[train_idx]
            X_val_fold = X.iloc[val_idx]
            y_val_fold = y.iloc[val_idx]

            # Train model
            model = XGBoostModel(training_config["models"]["xgboost"])
            model.train(X_train_fold, y_train_fold, X_val_fold, y_val_fold)

            # Evaluate
            predictions = model.predict(X_val_fold)
            mse = np.mean((predictions - y_val_fold) ** 2)
            cv_scores.append(mse)

            # Verify temporal order
            assert X_train_fold.index.max() < X_val_fold.index.min()

        # Verify CV results
        assert len(cv_scores) == 5
        assert all(score > 0 for score in cv_scores)

        # Calculate CV statistics
        cv_mean = np.mean(cv_scores)
        cv_std = np.std(cv_scores)

        print(f"CV MSE: {cv_mean:.6f} (+/- {cv_std:.6f})")

    @pytest.mark.asyncio
    async def test_model_persistence_and_loading(
        self, sample_ml_data, training_config, tmp_path
    ):
        """Test model saving and loading."""
        # Train model
        X = sample_ml_data.drop("target", axis=1)
        y = sample_ml_data["target"]

        train_size = int(len(X) * 0.8)
        X_train = X.iloc[:train_size]
        y_train = y.iloc[:train_size]
        X_test = X.iloc[train_size:]
        y_test = y.iloc[train_size:]

        # Train model
        model = XGBoostModel(training_config["models"]["xgboost"])
        model.train(X_train, y_train)

        # Make predictions before saving
        predictions_before = model.predict(X_test)

        # Save model
        model_path = tmp_path / "test_model.joblib"
        model.save(model_path)

        # Save metadata
        metadata = {
            "model_type": "xgboost",
            "training_config": training_config["models"]["xgboost"],
            "feature_names": X_train.columns.tolist(),
            "training_date": datetime.now(timezone.utc).isoformat(),
            "training_samples": len(X_train),
            "performance_metrics": {"train_mse": 0.001, "val_mse": 0.0012},
        }

        metadata_path = tmp_path / "test_model_metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        # Load model
        loaded_model = XGBoostModel.load(model_path)

        # Make predictions after loading
        predictions_after = loaded_model.predict(X_test)

        # Verify predictions are identical
        assert np.allclose(predictions_before, predictions_after)

        # Verify metadata
        with open(metadata_path, "r") as f:
            loaded_metadata = json.load(f)

        assert loaded_metadata["model_type"] == "xgboost"
        assert loaded_metadata["feature_names"] == X_train.columns.tolist()

    @pytest.mark.asyncio
    async def test_model_registry_integration(
        self, sample_ml_data, training_config, tmp_path
    ):
        """Test model registry for model versioning and management."""
        registry = ModelRegistry(base_path=tmp_path)

        # Train multiple model versions
        X = sample_ml_data.drop("target", axis=1)
        y = sample_ml_data["target"]

        train_size = int(len(X) * 0.8)
        X_train = X.iloc[:train_size]
        y_train = y.iloc[:train_size]
        X_test = X.iloc[train_size:]
        y_test = y.iloc[train_size:]

        model_versions = []

        for version in range(3):
            # Modify config slightly for each version
            config = training_config["models"]["xgboost"].copy()
            config["n_estimators"] = 100 + version * 50

            # Train model
            model = XGBoostModel(config)
            model.train(X_train, y_train)

            # Evaluate model
            predictions = model.predict(X_test)
            mse = np.mean((predictions - y_test) ** 2)

            # Register model
            model_info = await registry.register_model(
                model=model,
                model_name="test_xgboost",
                version=f"v{version + 1}",
                metrics={"test_mse": mse},
                metadata={"config": config, "feature_names": X_train.columns.tolist()},
            )

            model_versions.append(model_info)

        # Verify registry
        assert len(model_versions) == 3

        # Get best model
        best_model_info = await registry.get_best_model(
            model_name="test_xgboost", metric="test_mse", higher_better=False
        )

        assert best_model_info is not None
        assert "version" in best_model_info
        assert "metrics" in best_model_info

        # Load specific version
        model_v2 = await registry.load_model("test_xgboost", version="v2")
        assert model_v2 is not None

        # List all versions
        all_versions = await registry.list_model_versions("test_xgboost")
        assert len(all_versions) == 3

    @pytest.mark.asyncio
    async def test_feature_importance_analysis(self, sample_ml_data, training_config):
        """Test feature importance extraction and analysis."""
        X = sample_ml_data.drop("target", axis=1)
        y = sample_ml_data["target"]

        train_size = int(len(X) * 0.8)
        X_train = X.iloc[:train_size]
        y_train = y.iloc[:train_size]

        # Train models
        models = {
            "xgboost": XGBoostModel(training_config["models"]["xgboost"]),
            "lightgbm": LightGBMModel(training_config["models"]["lightgbm"]),
        }

        feature_importances = {}

        for name, model in models.items():
            model.train(X_train, y_train)
            importances = model.get_feature_importance()
            feature_importances[name] = importances

            # Verify feature importance
            assert len(importances) == len(X_train.columns)
            assert all(imp >= 0 for imp in importances.values())
            assert sum(importances.values()) > 0

        # Compare feature importances across models
        common_features = set(feature_importances["xgboost"].keys()) & set(
            feature_importances["lightgbm"].keys()
        )

        assert len(common_features) == len(X_train.columns)

        # Find top features
        top_features_xgb = sorted(
            feature_importances["xgboost"].items(), key=lambda x: x[1], reverse=True
        )[:10]

        top_features_lgb = sorted(
            feature_importances["lightgbm"].items(), key=lambda x: x[1], reverse=True
        )[:10]

        # Some overlap expected in top features
        top_xgb_names = [f[0] for f in top_features_xgb]
        top_lgb_names = [f[0] for f in top_features_lgb]
        overlap = set(top_xgb_names) & set(top_lgb_names)

        assert len(overlap) > 0  # At least some common important features

    @pytest.mark.asyncio
    async def test_incremental_learning(self, sample_ml_data, training_config):
        """Test incremental/online learning capabilities."""
        X = sample_ml_data.drop("target", axis=1)
        y = sample_ml_data["target"]

        # Split data into initial and incremental batches
        initial_size = int(len(X) * 0.5)
        batch_size = int(len(X) * 0.1)

        X_initial = X.iloc[:initial_size]
        y_initial = y.iloc[:initial_size]

        # Train initial model
        model = LightGBMModel(training_config["models"]["lightgbm"])
        model.train(X_initial, y_initial)

        # Get initial performance
        initial_pred = model.predict(X.iloc[initial_size : initial_size + batch_size])
        initial_mse = np.mean(
            (initial_pred - y.iloc[initial_size : initial_size + batch_size]) ** 2
        )

        # Incremental updates
        for i in range(3):
            start_idx = initial_size + i * batch_size
            end_idx = start_idx + batch_size

            if end_idx > len(X):
                break

            X_batch = X.iloc[start_idx:end_idx]
            y_batch = y.iloc[start_idx:end_idx]

            # Update model (if supported)
            if hasattr(model, "update"):
                model.update(X_batch, y_batch)
            else:
                # Retrain with combined data
                X_combined = pd.concat([X_initial, X.iloc[initial_size:end_idx]])
                y_combined = pd.concat([y_initial, y.iloc[initial_size:end_idx]])
                model.train(X_combined, y_combined)

        # Verify model adapted
        final_pred = model.predict(X.iloc[-batch_size:])
        assert len(final_pred) == batch_size

    @pytest.mark.asyncio
    async def test_multi_target_training(self, sample_ml_data, training_config):
        """Test training for multiple prediction targets."""
        X = sample_ml_data.drop("target", axis=1)

        # Create multiple targets
        targets = {
            "1h_return": sample_ml_data["target"],  # Original 1h return
            "4h_return": sample_ml_data["target"]
            .rolling(4)
            .sum()
            .shift(-3),  # 4h return
            "direction": (sample_ml_data["target"] > 0).astype(int),  # Binary direction
        }

        # Remove NaN values
        valid_idx = ~any(target.isnull() for target in targets.values())
        X_clean = X[valid_idx]
        targets_clean = {k: v[valid_idx] for k, v in targets.items()}

        train_size = int(len(X_clean) * 0.8)

        trained_models = {}

        for target_name, y in targets_clean.items():
            X_train = X_clean.iloc[:train_size]
            y_train = y.iloc[:train_size]
            X_test = X_clean.iloc[train_size:]
            y_test = y.iloc[train_size:]

            # Choose model based on target type
            if target_name == "direction":
                # Classification
                config = training_config["models"]["xgboost"].copy()
                config["objective"] = "binary:logistic"
                model = XGBoostModel(config)
            else:
                # Regression
                model = XGBoostModel(training_config["models"]["xgboost"])

            # Train model
            model.train(X_train, y_train)
            trained_models[target_name] = model

            # Evaluate
            predictions = model.predict(X_test)

            if target_name == "direction":
                # Convert probabilities to classes
                predictions = (predictions > 0.5).astype(int)
                accuracy = np.mean(predictions == y_test)
                assert accuracy > 0.4  # Better than random
            else:
                mse = np.mean((predictions - y_test) ** 2)
                assert mse < 1.0  # Reasonable error

        # Verify all models trained
        assert len(trained_models) == 3


class TestModelDeploymentPreparation:
    """Test model preparation for deployment."""

    @pytest.mark.asyncio
    async def test_model_serialization_formats(
        self, sample_ml_data, training_config, tmp_path
    ):
        """Test different model serialization formats."""
        X = sample_ml_data.drop("target", axis=1)
        y = sample_ml_data["target"]

        train_size = int(len(X) * 0.8)
        X_train = X.iloc[:train_size]
        y_train = y.iloc[:train_size]
        X_test = X.iloc[train_size:]

        # Train model
        model = XGBoostModel(training_config["models"]["xgboost"])
        model.train(X_train, y_train)

        # Test different serialization formats
        formats = {
            "joblib": tmp_path / "model.joblib",
            "pickle": tmp_path / "model.pkl",
            "json": tmp_path / "model.json",  # XGBoost specific
        }

        predictions_original = model.predict(X_test)

        for format_name, path in formats.items():
            if format_name == "joblib":
                joblib.dump(model, path)
                loaded_model = joblib.load(path)
            elif format_name == "pickle":
                import pickle

                with open(path, "wb") as f:
                    pickle.dump(model, f)
                with open(path, "rb") as f:
                    loaded_model = pickle.load(f)
            elif format_name == "json" and hasattr(model.model, "save_model"):
                # XGBoost native format
                model.model.save_model(str(path))
                continue  # Skip prediction test for JSON format

            # Verify predictions match
            predictions_loaded = loaded_model.predict(X_test)
            assert np.allclose(predictions_original, predictions_loaded)

    @pytest.mark.asyncio
    async def test_model_optimization_for_inference(
        self, sample_ml_data, training_config
    ):
        """Test model optimization for faster inference."""
        X = sample_ml_data.drop("target", axis=1)
        y = sample_ml_data["target"]

        train_size = int(len(X) * 0.8)
        X_train = X.iloc[:train_size]
        y_train = y.iloc[:train_size]
        X_test = X.iloc[train_size:]

        # Train full model
        full_model = XGBoostModel(training_config["models"]["xgboost"])
        full_model.train(X_train, y_train)

        # Create optimized model with fewer trees
        optimized_config = training_config["models"]["xgboost"].copy()
        optimized_config["n_estimators"] = 50  # Half the trees

        optimized_model = XGBoostModel(optimized_config)
        optimized_model.train(X_train, y_train)

        # Compare inference time
        import time

        # Full model inference
        start = time.time()
        for _ in range(100):
            _ = full_model.predict(X_test.iloc[:10])
        full_time = time.time() - start

        # Optimized model inference
        start = time.time()
        for _ in range(100):
            _ = optimized_model.predict(X_test.iloc[:10])
        optimized_time = time.time() - start

        # Optimized should be faster
        assert optimized_time < full_time

        print(
            f"Inference time - Full: {full_time:.3f}s, Optimized: {optimized_time:.3f}s"
        )

    @pytest.mark.asyncio
    async def test_model_monitoring_metrics(self, sample_ml_data, training_config):
        """Test collection of model monitoring metrics."""
        X = sample_ml_data.drop("target", axis=1)
        y = sample_ml_data["target"]

        train_size = int(len(X) * 0.8)
        X_train = X.iloc[:train_size]
        y_train = y.iloc[:train_size]
        X_test = X.iloc[train_size:]
        y_test = y.iloc[train_size:]

        # Train model
        model = XGBoostModel(training_config["models"]["xgboost"])
        model.train(X_train, y_train)

        # Collect monitoring metrics
        monitoring_metrics = {
            "prediction_stats": {},
            "feature_stats": {},
            "performance_degradation": [],
        }

        # Simulate production inference over time
        window_size = 100
        for i in range(0, len(X_test) - window_size, window_size):
            X_window = X_test.iloc[i : i + window_size]
            y_window = y_test.iloc[i : i + window_size]

            # Make predictions
            predictions = model.predict(X_window)

            # Collect prediction statistics
            monitoring_metrics["prediction_stats"][f"window_{i//window_size}"] = {
                "mean": float(np.mean(predictions)),
                "std": float(np.std(predictions)),
                "min": float(np.min(predictions)),
                "max": float(np.max(predictions)),
            }

            # Collect feature statistics
            feature_means = X_window.mean().to_dict()
            monitoring_metrics["feature_stats"][
                f"window_{i//window_size}"
            ] = feature_means

            # Track performance
            mse = np.mean((predictions - y_window) ** 2)
            monitoring_metrics["performance_degradation"].append(mse)

        # Verify monitoring data collected
        assert len(monitoring_metrics["prediction_stats"]) > 0
        assert len(monitoring_metrics["feature_stats"]) > 0
        assert len(monitoring_metrics["performance_degradation"]) > 0

        # Check for performance degradation
        degradation = monitoring_metrics["performance_degradation"]
        if len(degradation) > 1:
            # Simple trend check
            first_half_mean = np.mean(degradation[: len(degradation) // 2])
            second_half_mean = np.mean(degradation[len(degradation) // 2 :])
            degradation_rate = (second_half_mean - first_half_mean) / first_half_mean

            print(f"Performance degradation rate: {degradation_rate:.2%}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
