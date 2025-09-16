"""End-to-End Functional Tests for Feature Engineering Pipeline.

This module tests the complete feature engineering process including technical
indicators, market microstructure features, and data preprocessing.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from fxml4.features.feature_engineering import FeatureEngineer
from fxml4.features.feature_selector import FeatureSelector
from fxml4.features.market_microstructure import MarketMicrostructure
from fxml4.features.session_features import SessionFeatures
from fxml4.features.technical_indicators import TechnicalIndicators
from fxml4.ml.data_preprocessing import DataPreprocessor


class TestFeatureEngineeringE2E:
    """End-to-end tests for feature engineering pipeline."""

    @pytest.fixture
    def sample_ohlcv_data(self):
        """Create sample OHLCV data for testing."""
        dates = pd.date_range(start="2024-01-01", periods=1000, freq="1h", tz="UTC")

        # Generate realistic price data
        np.random.seed(42)
        close_prices = 1.0850
        prices = [close_prices]

        for _ in range(len(dates) - 1):
            change = np.random.normal(0, 0.0005)
            close_prices = max(close_prices * (1 + change), 0.0001)
            prices.append(close_prices)

        df = pd.DataFrame(
            {
                "timestamp": dates,
                "open": [p * (1 + np.random.uniform(-0.0002, 0.0002)) for p in prices],
                "high": [p * (1 + np.random.uniform(0, 0.0003)) for p in prices],
                "low": [p * (1 - np.random.uniform(0, 0.0003)) for p in prices],
                "close": prices,
                "volume": np.random.randint(10000, 100000, len(dates)),
            }
        )

        # Ensure OHLC consistency
        df["high"] = df[["open", "high", "close"]].max(axis=1)
        df["low"] = df[["open", "low", "close"]].min(axis=1)

        return df.set_index("timestamp")

    @pytest.fixture
    def feature_config(self):
        """Feature engineering configuration."""
        return {
            "technical_indicators": {
                "sma_periods": [20, 50, 200],
                "ema_periods": [12, 26],
                "rsi_period": 14,
                "macd_params": (12, 26, 9),
                "bollinger_params": (20, 2),
                "atr_period": 14,
            },
            "microstructure": {
                "spread_enabled": True,
                "volume_profile_bins": 10,
                "order_flow_imbalance": True,
            },
            "session_features": {
                "sessions": ["asian", "european", "american"],
                "session_volatility": True,
                "session_momentum": True,
            },
            "lag_features": {"price_lags": [1, 2, 3, 5, 10], "volume_lags": [1, 2, 3]},
        }

    @pytest.mark.asyncio
    async def test_complete_feature_generation(self, sample_ohlcv_data, feature_config):
        """Test complete feature generation pipeline."""
        feature_engineer = FeatureEngineer(feature_config)

        # Generate all features
        features_df = await feature_engineer.generate_features(sample_ohlcv_data)

        # Verify feature generation
        assert len(features_df) == len(sample_ohlcv_data)

        # Check technical indicators
        assert "sma_20" in features_df.columns
        assert "sma_50" in features_df.columns
        assert "sma_200" in features_df.columns
        assert "ema_12" in features_df.columns
        assert "ema_26" in features_df.columns
        assert "rsi" in features_df.columns
        assert "macd" in features_df.columns
        assert "macd_signal" in features_df.columns
        assert "macd_histogram" in features_df.columns
        assert "bb_upper" in features_df.columns
        assert "bb_lower" in features_df.columns
        assert "bb_middle" in features_df.columns
        assert "atr" in features_df.columns

        # Check no NaN values after warm-up period
        warmup_period = 200  # Max of indicator periods
        features_clean = features_df.iloc[warmup_period:]
        assert not features_clean.isnull().any().any()

    @pytest.mark.asyncio
    async def test_technical_indicators_accuracy(self, sample_ohlcv_data):
        """Test accuracy of technical indicator calculations."""
        tech_indicators = TechnicalIndicators()

        # Calculate indicators
        df = sample_ohlcv_data.copy()

        # SMA calculation verification
        sma_20 = df["close"].rolling(window=20).mean()
        df["sma_20"] = tech_indicators.sma(df["close"], 20)
        assert np.allclose(df["sma_20"].dropna(), sma_20.dropna(), rtol=1e-5)

        # RSI calculation verification
        df["rsi"] = tech_indicators.rsi(df["close"], 14)
        assert df["rsi"].dropna().between(0, 100).all()

        # MACD calculation verification
        df["macd"], df["signal"], df["histogram"] = tech_indicators.macd(df["close"])
        assert len(df["macd"].dropna()) > 0
        assert len(df["signal"].dropna()) > 0

        # Bollinger Bands verification
        df["bb_upper"], df["bb_middle"], df["bb_lower"] = (
            tech_indicators.bollinger_bands(df["close"])
        )
        assert (df["bb_upper"] > df["bb_middle"]).all()
        assert (df["bb_middle"] > df["bb_lower"]).all()

    @pytest.mark.asyncio
    async def test_market_microstructure_features(self, sample_ohlcv_data):
        """Test market microstructure feature generation."""
        microstructure = MarketMicrostructure()

        # Add bid/ask data
        df = sample_ohlcv_data.copy()
        df["bid"] = df["close"] - 0.0001
        df["ask"] = df["close"] + 0.0001

        # Generate microstructure features
        features = microstructure.generate_features(df)

        # Verify spread calculation
        assert "spread" in features.columns
        assert "spread_pct" in features.columns
        assert (features["spread"] >= 0).all()

        # Verify volume features
        assert "volume_ma" in features.columns
        assert "volume_ratio" in features.columns
        assert "volume_momentum" in features.columns

        # Verify price momentum
        assert "price_momentum" in features.columns
        assert "price_acceleration" in features.columns

    @pytest.mark.asyncio
    async def test_session_based_features(self, sample_ohlcv_data):
        """Test trading session-based feature generation."""
        session_features = SessionFeatures()

        # Generate session features
        features = session_features.generate_features(sample_ohlcv_data)

        # Verify session indicators
        assert "is_asian_session" in features.columns
        assert "is_european_session" in features.columns
        assert "is_american_session" in features.columns

        # Verify session volatility
        assert "asian_volatility" in features.columns
        assert "european_volatility" in features.columns
        assert "american_volatility" in features.columns

        # Check session overlap features
        assert "session_overlap" in features.columns

        # Verify boolean session flags
        assert features["is_asian_session"].dtype == bool
        assert features["is_european_session"].dtype == bool
        assert features["is_american_session"].dtype == bool

    @pytest.mark.asyncio
    async def test_feature_lag_creation(self, sample_ohlcv_data, feature_config):
        """Test creation of lagged features."""
        feature_engineer = FeatureEngineer(feature_config)

        # Create base features
        df = sample_ohlcv_data.copy()
        df["returns"] = df["close"].pct_change()

        # Generate lag features
        lag_features = feature_engineer.create_lag_features(
            df[["returns", "volume"]], feature_config["lag_features"]
        )

        # Verify lag features
        for lag in feature_config["lag_features"]["price_lags"]:
            assert f"returns_lag_{lag}" in lag_features.columns

        for lag in feature_config["lag_features"]["volume_lags"]:
            assert f"volume_lag_{lag}" in lag_features.columns

        # Check lag values
        assert np.allclose(
            lag_features["returns_lag_1"].iloc[1:],
            df["returns"].iloc[:-1],
            equal_nan=True,
        )

    @pytest.mark.asyncio
    async def test_feature_normalization(self, sample_ohlcv_data, feature_config):
        """Test feature normalization and scaling."""
        feature_engineer = FeatureEngineer(feature_config)
        preprocessor = DataPreprocessor()

        # Generate features
        features_df = await feature_engineer.generate_features(sample_ohlcv_data)

        # Split features for training
        train_size = int(len(features_df) * 0.8)
        train_features = features_df.iloc[:train_size]
        test_features = features_df.iloc[train_size:]

        # Fit preprocessor on training data
        preprocessor.fit(train_features)

        # Transform both sets
        train_normalized = preprocessor.transform(train_features)
        test_normalized = preprocessor.transform(test_features)

        # Verify normalization
        # Most features should be roughly in [-3, 3] range for StandardScaler
        assert np.abs(train_normalized).max().max() < 10
        assert np.abs(test_normalized).max().max() < 10

        # Verify shape preservation
        assert train_normalized.shape == train_features.shape
        assert test_normalized.shape == test_features.shape

    @pytest.mark.asyncio
    async def test_feature_selection(self, sample_ohlcv_data, feature_config):
        """Test feature selection based on importance."""
        feature_engineer = FeatureEngineer(feature_config)
        feature_selector = FeatureSelector()

        # Generate features
        features_df = await feature_engineer.generate_features(sample_ohlcv_data)

        # Create target variable (next period return)
        target = sample_ohlcv_data["close"].pct_change().shift(-1)

        # Align features and target
        features_df = features_df.iloc[:-1]  # Remove last row
        target = target.iloc[:-1]

        # Remove NaN values
        valid_idx = ~(features_df.isnull().any(axis=1) | target.isnull())
        features_clean = features_df[valid_idx]
        target_clean = target[valid_idx]

        # Select features
        selected_features = feature_selector.select_features(
            features_clean, target_clean, method="mutual_info", n_features=20
        )

        # Verify selection
        assert len(selected_features) == 20
        assert all(feat in features_df.columns for feat in selected_features)

    @pytest.mark.asyncio
    async def test_no_look_ahead_bias(self, sample_ohlcv_data, feature_config):
        """Test that feature engineering has no look-ahead bias."""
        feature_engineer = FeatureEngineer(feature_config)

        # Generate features for full dataset
        features_full = await feature_engineer.generate_features(sample_ohlcv_data)

        # Generate features for partial dataset
        partial_data = sample_ohlcv_data.iloc[:-10]
        features_partial = await feature_engineer.generate_features(partial_data)

        # Compare overlapping period
        overlap_end = len(features_partial)

        # Features should be identical in overlapping period
        # (allowing for minor floating point differences)
        for col in features_partial.columns:
            if col in features_full.columns:
                full_values = features_full[col].iloc[:overlap_end]
                partial_values = features_partial[col]

                # Compare non-NaN values
                mask = ~(full_values.isnull() | partial_values.isnull())
                if mask.any():
                    assert np.allclose(
                        full_values[mask], partial_values[mask], rtol=1e-5, atol=1e-8
                    ), f"Look-ahead bias detected in feature: {col}"

    @pytest.mark.asyncio
    async def test_multi_timeframe_features(self, sample_ohlcv_data):
        """Test feature generation across multiple timeframes."""
        # Create multiple timeframe data
        timeframes = {
            "1h": sample_ohlcv_data,
            "4h": sample_ohlcv_data.resample("4h")
            .agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            )
            .dropna(),
            "1d": sample_ohlcv_data.resample("1D")
            .agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            )
            .dropna(),
        }

        # Generate features for each timeframe
        all_features = {}
        for tf, data in timeframes.items():
            feature_engineer = FeatureEngineer(
                {"technical_indicators": {"sma_periods": [10, 20], "rsi_period": 14}}
            )
            all_features[tf] = await feature_engineer.generate_features(data)

        # Verify features generated for all timeframes
        assert len(all_features) == 3
        assert all(len(features) > 0 for features in all_features.values())

        # Check feature consistency across timeframes
        for tf, features in all_features.items():
            assert "sma_10" in features.columns
            assert "sma_20" in features.columns
            assert "rsi" in features.columns

    @pytest.mark.asyncio
    async def test_feature_persistence_and_recovery(
        self, sample_ohlcv_data, feature_config, tmp_path
    ):
        """Test saving and loading of engineered features."""
        feature_engineer = FeatureEngineer(feature_config)

        # Generate features
        features_df = await feature_engineer.generate_features(sample_ohlcv_data)

        # Save features
        features_file = tmp_path / "features.parquet"
        features_df.to_parquet(features_file)

        # Save feature metadata
        metadata = {
            "feature_names": features_df.columns.tolist(),
            "feature_config": feature_config,
            "generation_timestamp": datetime.now(timezone.utc).isoformat(),
            "data_range": {
                "start": features_df.index[0].isoformat(),
                "end": features_df.index[-1].isoformat(),
            },
        }

        import json

        metadata_file = tmp_path / "feature_metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

        # Load features and verify
        loaded_features = pd.read_parquet(features_file)
        with open(metadata_file, "r") as f:
            loaded_metadata = json.load(f)

        # Verify loaded data
        assert loaded_features.equals(features_df)
        assert loaded_metadata["feature_names"] == features_df.columns.tolist()
        assert loaded_metadata["feature_config"] == feature_config


class TestFeatureEngineeringEdgeCases:
    """Test edge cases and error handling in feature engineering."""

    @pytest.mark.asyncio
    async def test_insufficient_data_handling(self, feature_config):
        """Test handling of insufficient data for feature calculation."""
        # Create minimal data (less than required for some indicators)
        dates = pd.date_range(start="2024-01-01", periods=10, freq="1h", tz="UTC")
        small_df = pd.DataFrame(
            {
                "timestamp": dates,
                "open": [1.08] * 10,
                "high": [1.085] * 10,
                "low": [1.075] * 10,
                "close": [1.08] * 10,
                "volume": [1000] * 10,
            }
        ).set_index("timestamp")

        feature_engineer = FeatureEngineer(feature_config)

        # Should handle gracefully with NaN for indicators requiring more data
        features = await feature_engineer.generate_features(small_df)

        # Verify shape
        assert len(features) == len(small_df)

        # Check that some features are NaN due to insufficient data
        assert features["sma_200"].isnull().all()  # Needs 200 periods
        assert features["sma_20"].isnull().sum() >= 19  # First 19 should be NaN

    @pytest.mark.asyncio
    async def test_missing_data_handling(self, sample_ohlcv_data, feature_config):
        """Test handling of missing data in input."""
        # Introduce missing values
        df_with_gaps = sample_ohlcv_data.copy()
        df_with_gaps.loc[df_with_gaps.index[10:15], "close"] = np.nan
        df_with_gaps.loc[df_with_gaps.index[50:52], "volume"] = np.nan

        feature_engineer = FeatureEngineer(feature_config)

        # Should handle missing data appropriately
        features = await feature_engineer.generate_features(df_with_gaps)

        # Verify features were generated
        assert len(features) == len(df_with_gaps)

        # Check that NaN propagation is handled correctly
        # Features dependent on close price should have NaN in affected periods
        assert features.loc[df_with_gaps.index[10:15], "sma_20"].isnull().any()

    @pytest.mark.asyncio
    async def test_extreme_value_handling(self, sample_ohlcv_data, feature_config):
        """Test handling of extreme values in data."""
        # Introduce extreme values
        df_extreme = sample_ohlcv_data.copy()
        df_extreme.loc[df_extreme.index[100], "close"] = df_extreme["close"].mean() * 10
        df_extreme.loc[df_extreme.index[200], "volume"] = (
            df_extreme["volume"].mean() * 100
        )

        feature_engineer = FeatureEngineer(feature_config)

        # Generate features with extreme values
        features = await feature_engineer.generate_features(df_extreme)

        # Verify features are generated without errors
        assert len(features) == len(df_extreme)

        # Check that extreme values are handled (e.g., RSI still bounded)
        assert features["rsi"].between(0, 100).all() | features["rsi"].isnull()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
