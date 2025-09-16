"""
TDD Tests for Ensemble ML Models

Comprehensive test suite for machine learning ensemble models
used in forex trading signal generation.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import accuracy_score, precision_recall_fscore_support


@pytest.mark.tdd
@pytest.mark.ml
class TestEnsembleSignalGenerator:
    """
    Test suite for ensemble ML signal generation.

    Tests the complete ML pipeline from feature engineering
    through model training to signal generation.
    """

    @pytest.fixture
    def sample_market_data(self):
        """Generate sample market data for testing."""
        dates = pd.date_range(start="2024-01-01", periods=1000, freq="1H")
        np.random.seed(42)

        return pd.DataFrame(
            {
                "timestamp": dates,
                "open": 1.0850 + np.random.randn(1000) * 0.001,
                "high": 1.0860 + np.random.randn(1000) * 0.001,
                "low": 1.0840 + np.random.randn(1000) * 0.001,
                "close": 1.0851 + np.random.randn(1000) * 0.001,
                "volume": np.random.randint(100000, 1000000, 1000),
                "symbol": "EUR/USD",
            }
        )

    @pytest.fixture
    def feature_matrix(self, sample_market_data):
        """Generate feature matrix from market data."""
        from core.ml.features import FeatureEngineer

        engineer = FeatureEngineer()
        features = engineer.create_features(sample_market_data)
        return features

    @pytest.fixture
    def ensemble_model(self):
        """Create ensemble model instance."""
        from core.ml.ensemble_signal_generator import EnsembleSignalGenerator

        return EnsembleSignalGenerator(
            models=["random_forest", "xgboost", "lstm"],
            voting="soft",
            weights=[0.4, 0.4, 0.2],
        )

    # -------------------------------------------------------------------------
    # Feature Engineering Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    def test_technical_indicator_features(self, sample_market_data):
        """RED: Test technical indicator feature generation."""
        from core.ml.features import TechnicalFeatures

        tech_features = TechnicalFeatures()
        features = tech_features.generate(sample_market_data)

        # Check required indicators
        expected_indicators = [
            "rsi_14",
            "rsi_28",
            "macd",
            "macd_signal",
            "macd_hist",
            "bb_upper",
            "bb_middle",
            "bb_lower",
            "sma_20",
            "sma_50",
            "sma_200",
            "ema_12",
            "ema_26",
            "atr_14",
            "stoch_k",
            "stoch_d",
            "adx",
            "obv",
        ]

        for indicator in expected_indicators:
            assert indicator in features.columns, f"Missing {indicator}"

        # Validate indicator ranges
        assert features["rsi_14"].min() >= 0
        assert features["rsi_14"].max() <= 100
        assert not features["macd"].isnull().all()

    @pytest.mark.red
    def test_price_action_features(self, sample_market_data):
        """RED: Test price action pattern features."""
        from core.ml.features import PriceActionFeatures

        pa_features = PriceActionFeatures()
        features = pa_features.generate(sample_market_data)

        # Check pattern features
        expected_patterns = [
            "candlestick_pattern",
            "support_level",
            "resistance_level",
            "trend_strength",
            "trend_direction",
            "price_momentum",
            "volatility_regime",
        ]

        for pattern in expected_patterns:
            assert pattern in features.columns

        # Validate pattern values
        assert features["trend_direction"].isin([-1, 0, 1]).all()
        assert features["volatility_regime"].isin(["low", "medium", "high"]).all()

    @pytest.mark.red
    def test_market_microstructure_features(self, sample_market_data):
        """RED: Test market microstructure features."""
        from core.ml.features import MicrostructureFeatures

        micro_features = MicrostructureFeatures()
        features = micro_features.generate(sample_market_data)

        # Check microstructure metrics
        assert "bid_ask_spread" in features.columns
        assert "order_flow_imbalance" in features.columns
        assert "volume_weighted_price" in features.columns
        assert "tick_rule" in features.columns

        # Validate values
        assert (features["bid_ask_spread"] >= 0).all()
        assert features["tick_rule"].isin([-1, 0, 1]).all()

    # -------------------------------------------------------------------------
    # Model Training Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    def test_ensemble_model_training(self, ensemble_model, feature_matrix):
        """RED: Test ensemble model training process."""
        # Generate labels (buy/sell/hold signals)
        np.random.seed(42)
        labels = np.random.choice([0, 1, 2], size=len(feature_matrix))

        # Split data
        train_size = int(0.8 * len(feature_matrix))
        X_train = feature_matrix[:train_size]
        y_train = labels[:train_size]
        X_test = feature_matrix[train_size:]
        y_test = labels[train_size:]

        # Train model
        ensemble_model.fit(X_train, y_train, validation_split=0.2)

        # Evaluate
        predictions = ensemble_model.predict(X_test)
        accuracy = accuracy_score(y_test, predictions)

        assert accuracy > 0.4  # Better than random (33% for 3 classes)
        assert len(np.unique(predictions)) == 3  # All classes predicted

    @pytest.mark.red
    def test_individual_model_contributions(self, ensemble_model, feature_matrix):
        """RED: Test individual model contributions to ensemble."""
        labels = np.random.choice([0, 1, 2], size=len(feature_matrix))
        ensemble_model.fit(feature_matrix, labels)

        # Get individual model predictions
        individual_predictions = ensemble_model.get_individual_predictions(
            feature_matrix[:10]
        )

        assert "random_forest" in individual_predictions
        assert "xgboost" in individual_predictions
        assert "lstm" in individual_predictions

        # Check weighted voting
        ensemble_pred = ensemble_model.predict(feature_matrix[:10])
        weighted_sum = sum(
            pred * weight
            for pred, weight in zip(
                individual_predictions.values(), ensemble_model.weights
            )
        )
        # Ensemble should approximately match weighted voting
        assert np.allclose(ensemble_pred, np.argmax(weighted_sum, axis=1), atol=1)

    @pytest.mark.red
    def test_model_confidence_scores(self, ensemble_model, feature_matrix):
        """RED: Test model confidence score generation."""
        labels = np.random.choice([0, 1, 2], size=len(feature_matrix))
        ensemble_model.fit(feature_matrix, labels)

        # Get predictions with confidence
        predictions, confidence = ensemble_model.predict_with_confidence(
            feature_matrix[:100]
        )

        assert len(predictions) == 100
        assert len(confidence) == 100
        assert all(0 <= c <= 1 for c in confidence)

        # High confidence should correlate with agreement
        high_conf_idx = np.where(confidence > 0.8)[0]
        if len(high_conf_idx) > 0:
            # Check individual models agree when confidence is high
            individual = ensemble_model.get_individual_predictions(
                feature_matrix[high_conf_idx]
            )
            agreement = np.std([pred for pred in individual.values()], axis=0).mean()
            assert agreement < 0.5  # Low standard deviation = high agreement

    # -------------------------------------------------------------------------
    # Signal Generation Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    def test_trading_signal_generation(self, ensemble_model, sample_market_data):
        """RED: Test trading signal generation from predictions."""
        from core.ml.features import FeatureEngineer

        # Prepare features
        engineer = FeatureEngineer()
        features = engineer.create_features(sample_market_data)

        # Train model (mock for speed)
        with patch.object(ensemble_model, "fit"):
            ensemble_model.is_fitted = True

        # Generate signals
        signals = ensemble_model.generate_signals(
            features, confidence_threshold=0.6, position_sizing=True
        )

        assert "signal" in signals.columns
        assert "confidence" in signals.columns
        assert "position_size" in signals.columns

        # Validate signal values
        assert signals["signal"].isin(["BUY", "SELL", "HOLD"]).all()
        assert (signals["position_size"] >= 0).all()
        assert (signals["position_size"] <= 1).all()

    @pytest.mark.red
    def test_signal_filtering_and_smoothing(self, ensemble_model, feature_matrix):
        """RED: Test signal filtering and smoothing logic."""
        # Generate raw signals
        raw_signals = np.random.choice([0, 1, 2], size=100)

        # Apply filtering
        filtered_signals = ensemble_model.filter_signals(
            raw_signals, min_holding_period=3, signal_smoothing_window=5
        )

        # Check holding period constraint
        signal_changes = np.diff(filtered_signals)
        change_indices = np.where(signal_changes != 0)[0]

        if len(change_indices) > 1:
            periods = np.diff(change_indices)
            assert all(p >= 3 for p in periods)  # Minimum holding period

    @pytest.mark.red
    def test_risk_adjusted_signals(self, ensemble_model, sample_market_data):
        """RED: Test risk-adjusted signal generation."""
        from core.ml.features import FeatureEngineer

        engineer = FeatureEngineer()
        features = engineer.create_features(sample_market_data)

        # Add volatility for risk adjustment
        features["volatility"] = features["close"].pct_change().rolling(20).std()

        signals = ensemble_model.generate_risk_adjusted_signals(
            features, risk_factor="volatility", max_risk=0.02
        )

        # Check risk adjustment
        high_vol_periods = features["volatility"] > 0.02
        if high_vol_periods.any():
            # Position sizes should be reduced in high volatility
            high_vol_positions = signals.loc[high_vol_periods, "position_size"]
            normal_vol_positions = signals.loc[~high_vol_periods, "position_size"]

            if len(high_vol_positions) > 0 and len(normal_vol_positions) > 0:
                assert high_vol_positions.mean() < normal_vol_positions.mean()

    # -------------------------------------------------------------------------
    # Model Validation Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    def test_walk_forward_validation(self, ensemble_model, sample_market_data):
        """RED: Test walk-forward validation methodology."""
        from core.ml.validation import WalkForwardValidator

        validator = WalkForwardValidator(
            train_period=500, test_period=100, step_size=50
        )

        results = validator.validate(
            ensemble_model, sample_market_data, target_column="signal"
        )

        assert "sharpe_ratio" in results
        assert "max_drawdown" in results
        assert "win_rate" in results
        assert "profit_factor" in results

        # Basic performance checks
        assert results["win_rate"] > 0.3
        assert results["sharpe_ratio"] > -1

    @pytest.mark.red
    def test_cross_validation_stability(self, ensemble_model, feature_matrix):
        """RED: Test model stability across cross-validation folds."""
        from sklearn.model_selection import TimeSeriesSplit

        labels = np.random.choice([0, 1, 2], size=len(feature_matrix))
        tscv = TimeSeriesSplit(n_splits=5)

        scores = []
        for train_idx, test_idx in tscv.split(feature_matrix):
            X_train, X_test = (
                feature_matrix.iloc[train_idx],
                feature_matrix.iloc[test_idx],
            )
            y_train, y_test = labels[train_idx], labels[test_idx]

            ensemble_model.fit(X_train, y_train)
            score = ensemble_model.score(X_test, y_test)
            scores.append(score)

        # Check consistency across folds
        assert np.std(scores) < 0.15  # Standard deviation < 15%
        assert min(scores) > 0.3  # No catastrophic failures

    # -------------------------------------------------------------------------
    # Model Interpretability Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    def test_feature_importance_extraction(self, ensemble_model, feature_matrix):
        """RED: Test feature importance extraction from ensemble."""
        labels = np.random.choice([0, 1, 2], size=len(feature_matrix))
        ensemble_model.fit(feature_matrix, labels)

        importance = ensemble_model.get_feature_importance()

        assert len(importance) == feature_matrix.shape[1]
        assert all(imp >= 0 for imp in importance.values())
        assert sum(importance.values()) > 0

        # Top features should have meaningful importance
        top_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:10]
        assert all(imp > 0.01 for _, imp in top_features)

    @pytest.mark.red
    def test_shap_explanations(self, ensemble_model, feature_matrix):
        """RED: Test SHAP value generation for interpretability."""
        labels = np.random.choice([0, 1, 2], size=len(feature_matrix))
        ensemble_model.fit(feature_matrix, labels)

        # Get SHAP values for sample
        sample = feature_matrix[:10]
        shap_values = ensemble_model.explain_predictions(sample)

        assert shap_values.shape == (
            10,
            feature_matrix.shape[1],
            3,
        )  # samples x features x classes

        # SHAP values should sum to prediction difference from base
        base_value = ensemble_model.get_base_prediction()
        predictions = ensemble_model.predict_proba(sample)

        for i in range(10):
            shap_sum = shap_values[i].sum(axis=0)
            pred_diff = predictions[i] - base_value
            assert np.allclose(shap_sum, pred_diff, atol=0.1)

    # -------------------------------------------------------------------------
    # Model Persistence Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    def test_model_serialization_and_loading(
        self, ensemble_model, feature_matrix, tmp_path
    ):
        """RED: Test model save and load functionality."""
        labels = np.random.choice([0, 1, 2], size=len(feature_matrix))
        ensemble_model.fit(feature_matrix, labels)

        # Get predictions before saving
        original_predictions = ensemble_model.predict(feature_matrix[:50])

        # Save model
        model_path = tmp_path / "ensemble_model.pkl"
        ensemble_model.save(model_path)

        # Load model
        from core.ml.ensemble_signal_generator import EnsembleSignalGenerator

        loaded_model = EnsembleSignalGenerator.load(model_path)

        # Compare predictions
        loaded_predictions = loaded_model.predict(feature_matrix[:50])
        np.testing.assert_array_equal(original_predictions, loaded_predictions)

        # Check model metadata
        assert loaded_model.version == ensemble_model.version
        assert loaded_model.training_date == ensemble_model.training_date

    # -------------------------------------------------------------------------
    # Performance and Optimization Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    def test_prediction_latency(
        self, ensemble_model, feature_matrix, performance_timer
    ):
        """RED: Test prediction latency for real-time trading."""
        labels = np.random.choice([0, 1, 2], size=len(feature_matrix))
        ensemble_model.fit(feature_matrix, labels)

        # Test single prediction latency
        performance_timer.start()
        _ = ensemble_model.predict(feature_matrix[:1])
        single_latency = performance_timer.stop()

        assert single_latency < 0.01  # Less than 10ms

        # Test batch prediction latency
        performance_timer.start()
        _ = ensemble_model.predict(feature_matrix[:100])
        batch_latency = performance_timer.stop()

        assert batch_latency < 0.1  # Less than 100ms for 100 samples

    @pytest.mark.red
    def test_hyperparameter_optimization(self, ensemble_model, feature_matrix):
        """RED: Test hyperparameter optimization process."""
        from core.ml.optimization import HyperparameterOptimizer

        labels = np.random.choice([0, 1, 2], size=len(feature_matrix))

        optimizer = HyperparameterOptimizer(
            model=ensemble_model,
            param_space={
                "n_estimators": [100, 200],
                "max_depth": [5, 10],
                "learning_rate": [0.01, 0.1],
            },
            n_trials=10,
        )

        best_params = optimizer.optimize(feature_matrix, labels)

        assert "n_estimators" in best_params
        assert "max_depth" in best_params
        assert "learning_rate" in best_params

        # Model with optimized params should perform better
        optimized_model = ensemble_model.set_params(**best_params)
        optimized_model.fit(feature_matrix[:800], labels[:800])
        optimized_score = optimized_model.score(feature_matrix[800:], labels[800:])

        assert optimized_score > 0.4  # Better than random
