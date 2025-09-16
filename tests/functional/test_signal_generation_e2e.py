"""End-to-End Functional Tests for Signal Generation.

This module tests the complete signal generation pipeline from trained models
to actionable trading signals with proper filtering and risk controls.
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from fxml4.features.feature_engineering import FeatureEngineer
from fxml4.ml.models.ensemble import EnsembleModel
from fxml4.signals.confidence_calculator import ConfidenceCalculator
from fxml4.signals.signal_aggregator import SignalAggregator
from fxml4.signals.signal_filters import SignalFilter
from fxml4.signals.signal_generator import SignalGenerator


class TestSignalGenerationE2E:
    """End-to-end tests for signal generation pipeline."""

    @pytest.fixture
    def mock_trained_models(self):
        """Create mock trained models for testing."""
        models = {}

        # Mock XGBoost model
        xgb_model = MagicMock()
        xgb_model.predict = MagicMock(
            side_effect=lambda X: np.random.normal(0.0001, 0.0005, len(X))
        )
        xgb_model.predict_proba = MagicMock(
            side_effect=lambda X: np.column_stack(
                [
                    np.random.uniform(0.3, 0.7, len(X)),
                    np.random.uniform(0.3, 0.7, len(X)),
                ]
            )
        )
        models["xgboost"] = xgb_model

        # Mock LightGBM model
        lgb_model = MagicMock()
        lgb_model.predict = MagicMock(
            side_effect=lambda X: np.random.normal(0.0001, 0.0005, len(X))
        )
        lgb_model.predict_proba = MagicMock(
            side_effect=lambda X: np.column_stack(
                [
                    np.random.uniform(0.3, 0.7, len(X)),
                    np.random.uniform(0.3, 0.7, len(X)),
                ]
            )
        )
        models["lightgbm"] = lgb_model

        # Mock ensemble
        ensemble = MagicMock(spec=EnsembleModel)
        ensemble.models = [xgb_model, lgb_model]
        ensemble.weights = [0.6, 0.4]
        ensemble.predict = MagicMock(
            side_effect=lambda X: 0.6 * xgb_model.predict(X)
            + 0.4 * lgb_model.predict(X)
        )
        models["ensemble"] = ensemble

        return models

    @pytest.fixture
    def sample_feature_data(self):
        """Create sample feature data for signal generation."""
        dates = pd.date_range(start="2024-01-01", periods=100, freq="1h", tz="UTC")

        # Create realistic features
        features = pd.DataFrame(
            {
                "sma_20": np.random.randn(100).cumsum() + 1.08,
                "sma_50": np.random.randn(100).cumsum() + 1.08,
                "rsi": np.random.uniform(30, 70, 100),
                "macd": np.random.normal(0, 0.001, 100),
                "bb_position": np.random.uniform(-1, 1, 100),
                "volume_ratio": np.random.uniform(0.5, 2.0, 100),
                "spread": np.random.uniform(0.0001, 0.0003, 100),
                "momentum": np.random.normal(0, 0.001, 100),
                "volatility": np.random.uniform(0.0001, 0.001, 100),
                "is_european_session": np.random.randint(0, 2, 100),
            },
            index=dates,
        )

        # Add current price
        features["current_price"] = 1.0850 + np.random.randn(100).cumsum() * 0.001

        return features

    @pytest.fixture
    def signal_config(self):
        """Signal generation configuration."""
        return {
            "thresholds": {
                "min_prediction": 0.0002,  # 2 pips minimum
                "max_prediction": 0.01,  # 100 pips maximum
                "min_confidence": 0.6,
                "min_model_agreement": 0.7,
            },
            "filters": {
                "spread_filter": {"max_spread": 0.0003, "enabled": True},  # 3 pips
                "volatility_filter": {
                    "min_volatility": 0.0001,
                    "max_volatility": 0.002,
                    "enabled": True,
                },
                "session_filter": {
                    "allowed_sessions": ["european", "american"],
                    "enabled": True,
                },
                "momentum_filter": {
                    "min_momentum": -0.002,
                    "max_momentum": 0.002,
                    "enabled": True,
                },
            },
            "risk_controls": {
                "max_daily_signals": 20,
                "min_time_between_signals": 300,  # 5 minutes
                "max_correlation": 0.7,
                "position_sizing": {
                    "method": "kelly",
                    "max_position_pct": 0.02,
                    "min_position_pct": 0.001,
                },
            },
        }

    @pytest.mark.asyncio
    async def test_complete_signal_generation_flow(
        self, mock_trained_models, sample_feature_data, signal_config
    ):
        """Test complete signal generation from features to filtered signals."""
        # Create signal generator
        signal_generator = SignalGenerator(
            models=mock_trained_models, config=signal_config
        )

        # Generate raw signals
        signals = []

        for idx, (timestamp, features) in enumerate(sample_feature_data.iterrows()):
            # Generate predictions from each model
            features_array = features.drop("current_price").values.reshape(1, -1)

            predictions = {}
            for model_name, model in mock_trained_models.items():
                if model_name != "ensemble":
                    predictions[model_name] = float(model.predict(features_array)[0])

            # Generate ensemble prediction
            ensemble_pred = float(
                mock_trained_models["ensemble"].predict(features_array)[0]
            )

            # Calculate confidence
            confidence = ConfidenceCalculator.calculate_confidence(
                predictions=list(predictions.values()),
                model_weights=mock_trained_models["ensemble"].weights,
                feature_importance={
                    "rsi": features["rsi"],
                    "volatility": features["volatility"],
                },
            )

            # Create signal if criteria met
            if abs(ensemble_pred) > signal_config["thresholds"]["min_prediction"]:
                signal = {
                    "timestamp": timestamp,
                    "symbol": "EUR/USD",
                    "direction": "BUY" if ensemble_pred > 0 else "SELL",
                    "predicted_return": ensemble_pred,
                    "confidence": confidence,
                    "current_price": features["current_price"],
                    "features": features.to_dict(),
                    "model_predictions": predictions,
                }
                signals.append(signal)

        # Verify signals generated
        assert len(signals) > 0
        assert all("timestamp" in s for s in signals)
        assert all("direction" in s for s in signals)
        assert all("confidence" in s for s in signals)

        # Apply filters
        signal_filter = SignalFilter(signal_config["filters"])
        filtered_signals = []

        for signal in signals:
            if signal_filter.apply_filters(signal):
                filtered_signals.append(signal)

        # Verify filtering
        assert len(filtered_signals) <= len(signals)
        print(f"Signals: {len(signals)} raw, {len(filtered_signals)} filtered")

    @pytest.mark.asyncio
    async def test_signal_filtering_logic(self, sample_feature_data, signal_config):
        """Test individual signal filters."""
        signal_filter = SignalFilter(signal_config["filters"])

        # Test spread filter
        signal_high_spread = {
            "features": {"spread": 0.0005},  # 5 pips - too high
            "direction": "BUY",
            "confidence": 0.8,
        }
        assert not signal_filter.apply_spread_filter(signal_high_spread)

        signal_low_spread = {
            "features": {"spread": 0.0002},  # 2 pips - acceptable
            "direction": "BUY",
            "confidence": 0.8,
        }
        assert signal_filter.apply_spread_filter(signal_low_spread)

        # Test volatility filter
        signal_high_vol = {
            "features": {"volatility": 0.003},  # Too high
            "direction": "BUY",
            "confidence": 0.8,
        }
        assert not signal_filter.apply_volatility_filter(signal_high_vol)

        signal_good_vol = {
            "features": {"volatility": 0.0005},  # Good range
            "direction": "BUY",
            "confidence": 0.8,
        }
        assert signal_filter.apply_volatility_filter(signal_good_vol)

        # Test session filter
        signal_asian = {
            "features": {"is_european_session": 0, "is_american_session": 0},
            "direction": "BUY",
            "confidence": 0.8,
        }
        assert not signal_filter.apply_session_filter(signal_asian)

        signal_european = {
            "features": {"is_european_session": 1, "is_american_session": 0},
            "direction": "BUY",
            "confidence": 0.8,
        }
        assert signal_filter.apply_session_filter(signal_european)

    @pytest.mark.asyncio
    async def test_confidence_calculation(self, mock_trained_models):
        """Test confidence score calculation for signals."""
        confidence_calc = ConfidenceCalculator()

        # Test with high model agreement
        predictions_agree = [0.001, 0.0012, 0.0011]  # All positive, similar magnitude
        confidence_high = confidence_calc.calculate_confidence(
            predictions=predictions_agree, model_weights=[0.4, 0.3, 0.3]
        )
        assert confidence_high > 0.7

        # Test with model disagreement
        predictions_disagree = [0.001, -0.0005, 0.0002]  # Mixed signals
        confidence_low = confidence_calc.calculate_confidence(
            predictions=predictions_disagree, model_weights=[0.4, 0.3, 0.3]
        )
        assert confidence_low < 0.5

        # Test with feature-based confidence
        feature_confidence = confidence_calc.calculate_feature_confidence(
            {
                "rsi": 50,  # Neutral
                "volatility": 0.0005,  # Normal
                "spread": 0.0002,  # Acceptable
            }
        )
        assert 0.4 < feature_confidence < 0.6

    @pytest.mark.asyncio
    async def test_signal_aggregation(self, mock_trained_models, sample_feature_data):
        """Test aggregation of signals from multiple models."""
        aggregator = SignalAggregator()

        # Generate signals from different models
        all_signals = []

        for model_name, model in mock_trained_models.items():
            if model_name == "ensemble":
                continue

            model_signals = []
            for idx, (timestamp, features) in enumerate(
                sample_feature_data.head(10).iterrows()
            ):
                features_array = features.drop("current_price").values.reshape(1, -1)
                prediction = float(model.predict(features_array)[0])

                if abs(prediction) > 0.0002:
                    signal = {
                        "timestamp": timestamp,
                        "model": model_name,
                        "symbol": "EUR/USD",
                        "direction": "BUY" if prediction > 0 else "SELL",
                        "predicted_return": prediction,
                        "confidence": np.random.uniform(0.5, 0.9),
                    }
                    model_signals.append(signal)

            all_signals.extend(model_signals)

        # Aggregate signals
        aggregated = aggregator.aggregate_signals(
            all_signals,
            method="weighted_vote",
            weights={"xgboost": 0.6, "lightgbm": 0.4},
        )

        # Verify aggregation
        assert len(aggregated) <= len(all_signals)

        # Check aggregated signal structure
        for agg_signal in aggregated:
            assert "timestamp" in agg_signal
            assert "direction" in agg_signal
            assert "aggregate_confidence" in agg_signal
            assert "contributing_models" in agg_signal
            assert len(agg_signal["contributing_models"]) >= 1

    @pytest.mark.asyncio
    async def test_signal_timing_controls(self, signal_config):
        """Test timing controls for signal generation."""
        timing_controller = SignalGenerator.TimingController(
            min_time_between_signals=signal_config["risk_controls"][
                "min_time_between_signals"
            ]
        )

        base_time = datetime.now(timezone.utc)

        # First signal should pass
        signal1 = {"timestamp": base_time, "symbol": "EUR/USD", "direction": "BUY"}
        assert timing_controller.can_generate_signal(signal1)
        timing_controller.record_signal(signal1)

        # Signal too soon after should fail
        signal2 = {
            "timestamp": base_time + timedelta(seconds=100),  # Only 100s later
            "symbol": "EUR/USD",
            "direction": "SELL",
        }
        assert not timing_controller.can_generate_signal(signal2)

        # Signal after minimum time should pass
        signal3 = {
            "timestamp": base_time + timedelta(seconds=400),  # 400s later
            "symbol": "EUR/USD",
            "direction": "SELL",
        }
        assert timing_controller.can_generate_signal(signal3)

    @pytest.mark.asyncio
    async def test_position_sizing_calculation(self, signal_config):
        """Test position sizing based on signal confidence and risk."""
        position_sizer = SignalGenerator.PositionSizer(
            signal_config["risk_controls"]["position_sizing"]
        )

        # High confidence signal
        signal_high_conf = {
            "confidence": 0.85,
            "predicted_return": 0.001,
            "volatility": 0.0005,
        }
        position_high = position_sizer.calculate_position_size(
            signal_high_conf, account_balance=100000, current_exposure=0.01
        )

        # Should be closer to max position
        assert position_high > 0.015
        assert (
            position_high
            <= signal_config["risk_controls"]["position_sizing"]["max_position_pct"]
        )

        # Low confidence signal
        signal_low_conf = {
            "confidence": 0.55,
            "predicted_return": 0.0003,
            "volatility": 0.001,
        }
        position_low = position_sizer.calculate_position_size(
            signal_low_conf, account_balance=100000, current_exposure=0.01
        )

        # Should be closer to min position
        assert position_low < position_high
        assert (
            position_low
            >= signal_config["risk_controls"]["position_sizing"]["min_position_pct"]
        )

    @pytest.mark.asyncio
    async def test_multi_symbol_signal_generation(
        self, mock_trained_models, sample_feature_data, signal_config
    ):
        """Test signal generation for multiple symbols."""
        symbols = ["EUR/USD", "GBP/USD", "USD/JPY"]

        all_signals = []

        for symbol in symbols:
            # Create symbol-specific features
            symbol_features = sample_feature_data.copy()

            # Adjust features slightly for each symbol
            if symbol == "GBP/USD":
                symbol_features["current_price"] = (
                    1.25 + np.random.randn(100).cumsum() * 0.001
                )
            elif symbol == "USD/JPY":
                symbol_features["current_price"] = (
                    110.0 + np.random.randn(100).cumsum() * 0.1
                )

            # Generate signals for symbol
            signal_generator = SignalGenerator(
                models=mock_trained_models, config=signal_config
            )

            symbol_signals = await signal_generator.generate_signals(
                symbol=symbol, features=symbol_features.head(20)
            )

            all_signals.extend(symbol_signals)

        # Verify multi-symbol generation
        generated_symbols = set(s["symbol"] for s in all_signals)
        assert len(generated_symbols) <= len(symbols)

        # Check signal distribution
        symbol_counts = {}
        for signal in all_signals:
            symbol_counts[signal["symbol"]] = symbol_counts.get(signal["symbol"], 0) + 1

        print(f"Signal distribution: {symbol_counts}")

    @pytest.mark.asyncio
    async def test_signal_correlation_filter(self, signal_config):
        """Test correlation-based signal filtering."""
        correlation_filter = SignalGenerator.CorrelationFilter(
            max_correlation=signal_config["risk_controls"]["max_correlation"]
        )

        # Create correlated signals
        base_time = datetime.now(timezone.utc)

        signal1 = {
            "timestamp": base_time,
            "symbol": "EUR/USD",
            "direction": "BUY",
            "features": {"momentum": 0.001, "rsi": 60},
        }

        # Highly correlated signal (same direction, similar features)
        signal2_corr = {
            "timestamp": base_time + timedelta(minutes=10),
            "symbol": "GBP/USD",
            "direction": "BUY",
            "features": {"momentum": 0.0012, "rsi": 62},
        }

        # Less correlated signal (opposite direction)
        signal3_uncorr = {
            "timestamp": base_time + timedelta(minutes=20),
            "symbol": "USD/JPY",
            "direction": "SELL",
            "features": {"momentum": -0.0008, "rsi": 35},
        }

        # Test correlation
        correlation_filter.add_signal(signal1)

        # Should reject highly correlated signal
        assert not correlation_filter.is_acceptable(signal2_corr)

        # Should accept uncorrelated signal
        assert correlation_filter.is_acceptable(signal3_uncorr)

    @pytest.mark.asyncio
    async def test_signal_persistence_and_tracking(self, tmp_path):
        """Test signal storage and tracking."""
        signal_store = SignalGenerator.SignalStore(base_path=tmp_path)

        # Create test signals
        signals = []
        base_time = datetime.now(timezone.utc)

        for i in range(50):
            signal = {
                "id": f"signal_{i:04d}",
                "timestamp": base_time + timedelta(minutes=i * 10),
                "symbol": ["EUR/USD", "GBP/USD", "USD/JPY"][i % 3],
                "direction": "BUY" if i % 2 == 0 else "SELL",
                "predicted_return": np.random.uniform(0.0002, 0.001),
                "confidence": np.random.uniform(0.6, 0.9),
                "status": "pending",
                "features": {
                    "rsi": np.random.uniform(30, 70),
                    "volatility": np.random.uniform(0.0001, 0.001),
                },
            }
            signals.append(signal)
            await signal_store.store_signal(signal)

        # Verify storage
        stored_count = await signal_store.get_signal_count(
            start_time=base_time, end_time=base_time + timedelta(hours=10)
        )
        assert stored_count == len(signals)

        # Query signals
        eur_signals = await signal_store.get_signals(
            symbol="EUR/USD",
            start_time=base_time,
            end_time=base_time + timedelta(hours=10),
        )
        assert len(eur_signals) > 0
        assert all(s["symbol"] == "EUR/USD" for s in eur_signals)

        # Update signal status
        first_signal = signals[0]
        await signal_store.update_signal_status(
            signal_id=first_signal["id"],
            status="executed",
            execution_price=1.0850,
            execution_time=datetime.now(timezone.utc),
        )

        # Verify update
        updated_signal = await signal_store.get_signal(first_signal["id"])
        assert updated_signal["status"] == "executed"
        assert "execution_price" in updated_signal

    @pytest.mark.asyncio
    async def test_signal_performance_tracking(self):
        """Test tracking of signal performance."""
        performance_tracker = SignalGenerator.PerformanceTracker()

        # Add executed signals with outcomes
        signals_with_outcomes = [
            {
                "id": "sig_001",
                "direction": "BUY",
                "predicted_return": 0.0005,
                "confidence": 0.75,
                "actual_return": 0.0003,  # Profitable but less than predicted
                "outcome": "win",
            },
            {
                "id": "sig_002",
                "direction": "SELL",
                "predicted_return": -0.0004,
                "confidence": 0.65,
                "actual_return": -0.0006,  # Profitable, more than predicted
                "outcome": "win",
            },
            {
                "id": "sig_003",
                "direction": "BUY",
                "predicted_return": 0.0003,
                "confidence": 0.60,
                "actual_return": -0.0002,  # Loss
                "outcome": "loss",
            },
        ]

        for signal in signals_with_outcomes:
            performance_tracker.add_signal_outcome(signal)

        # Calculate performance metrics
        metrics = performance_tracker.calculate_metrics()

        # Verify metrics
        assert metrics["total_signals"] == 3
        assert metrics["win_rate"] == 2 / 3
        assert "average_return" in metrics
        assert "sharpe_ratio" in metrics
        assert "prediction_accuracy" in metrics

        # Test performance by confidence level
        confidence_performance = performance_tracker.get_performance_by_confidence()
        assert len(confidence_performance) > 0

        # Higher confidence should generally have better performance
        high_conf_perf = confidence_performance.get("high", {})
        low_conf_perf = confidence_performance.get("low", {})

        if high_conf_perf and low_conf_perf:
            # This is a general expectation, may not always hold with small samples
            print(f"High confidence win rate: {high_conf_perf.get('win_rate', 0)}")
            print(f"Low confidence win rate: {low_conf_perf.get('win_rate', 0)}")


class TestSignalGenerationEdgeCases:
    """Test edge cases and error handling in signal generation."""

    @pytest.mark.asyncio
    async def test_no_model_predictions(self, signal_config):
        """Test handling when models fail to generate predictions."""
        # Mock models that fail
        failed_models = {
            "xgboost": MagicMock(
                predict=MagicMock(side_effect=Exception("Model error"))
            ),
            "lightgbm": MagicMock(predict=MagicMock(return_value=np.array([np.nan]))),
        }

        signal_generator = SignalGenerator(models=failed_models, config=signal_config)

        # Should handle gracefully
        features = pd.DataFrame({"feature1": [1], "feature2": [2]})
        signals = await signal_generator.generate_signals("EUR/USD", features)

        # No signals should be generated
        assert len(signals) == 0

    @pytest.mark.asyncio
    async def test_extreme_market_conditions(self, mock_trained_models, signal_config):
        """Test signal generation during extreme market conditions."""
        # Create extreme market data
        extreme_features = pd.DataFrame(
            {
                "volatility": [0.01],  # 10x normal
                "spread": [0.001],  # Very wide spread
                "momentum": [0.01],  # Extreme momentum
                "rsi": [95],  # Overbought
                "current_price": [1.10],
            },
            index=[datetime.now(timezone.utc)],
        )

        signal_generator = SignalGenerator(
            models=mock_trained_models, config=signal_config
        )

        # Should filter out signals in extreme conditions
        signals = await signal_generator.generate_signals("EUR/USD", extreme_features)

        # Signals should be filtered due to extreme conditions
        assert len(signals) == 0 or all(s["confidence"] < 0.5 for s in signals)

    @pytest.mark.asyncio
    async def test_signal_generation_with_missing_features(
        self, mock_trained_models, signal_config
    ):
        """Test handling of missing features in signal generation."""
        # Create features with missing values
        incomplete_features = pd.DataFrame(
            {
                "sma_20": [1.08, np.nan, 1.09],
                "rsi": [50, 55, np.nan],
                "volatility": [0.0005, 0.0006, 0.0007],
                "current_price": [1.0850, 1.0851, 1.0852],
            },
            index=pd.date_range("2024-01-01", periods=3, freq="1h", tz="UTC"),
        )

        signal_generator = SignalGenerator(
            models=mock_trained_models, config=signal_config
        )

        # Should skip rows with missing features
        signals = await signal_generator.generate_signals(
            "EUR/USD", incomplete_features
        )

        # Only complete rows should generate signals
        assert len(signals) <= 1  # Only first row has complete features


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
