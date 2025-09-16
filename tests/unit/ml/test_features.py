"""Tests for ML feature engineering functionality."""

import warnings
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from fxml4.ml.features import create_basic_technical_features


class TestFeatureEngineering:
    """Test feature engineering functions."""

    @pytest.fixture
    def sample_ohlc_data(self):
        """Create sample OHLC market data."""
        np.random.seed(42)
        dates = pd.date_range(start="2023-01-01", periods=200, freq="H")

        # Generate realistic price data
        base_price = 1.1000
        price_changes = np.random.normal(0, 0.001, len(dates))
        prices = base_price + np.cumsum(price_changes)

        # Create OHLC data
        data = []
        for i, (date, price) in enumerate(zip(dates, prices)):
            noise = np.random.normal(0, 0.0005, 4)
            open_price = price + noise[0]
            high_price = max(price + abs(noise[1]), open_price)
            low_price = min(price - abs(noise[2]), open_price)
            close_price = price + noise[3]

            # Ensure realistic OHLC relationships
            high_price = max(high_price, open_price, close_price)
            low_price = min(low_price, open_price, close_price)

            data.append(
                {
                    "timestamp": date,
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "volume": np.random.randint(1000, 10000),
                }
            )

        df = pd.DataFrame(data)
        df.set_index("timestamp", inplace=True)
        return df

    def test_create_basic_technical_features_default(self, sample_ohlc_data):
        """Test basic technical features with default parameters."""
        result = create_basic_technical_features(sample_ohlc_data)

        # Should contain original columns
        assert "open" in result.columns
        assert "high" in result.columns
        assert "low" in result.columns
        assert "close" in result.columns

        # Check data integrity
        assert len(result) == len(sample_ohlc_data)

    def test_missing_columns_handling(self):
        """Test handling of missing required columns."""
        # Data missing 'close' column
        incomplete_data = pd.DataFrame(
            {
                "open": [1.1000, 1.1010],
                "high": [1.1005, 1.1015],
                "low": [1.0995, 1.1005],
                # Missing 'close'
            }
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = create_basic_technical_features(incomplete_data)

        # Should return original data without modifications
        assert list(result.columns) == list(incomplete_data.columns)

    def test_empty_dataframe_handling(self):
        """Test handling of empty dataframes."""
        empty_df = pd.DataFrame()

        result = create_basic_technical_features(empty_df)

        # Should return empty dataframe
        assert len(result) == 0


@pytest.mark.unit
class TestFeatureEngineeringIntegration:
    """Integration tests for feature engineering."""

    def test_complete_feature_engineering_pipeline(self):
        """Test complete feature engineering pipeline."""
        # Create realistic market data
        np.random.seed(42)
        dates = pd.date_range(start="2023-01-01", periods=100, freq="4H")

        # Generate correlated OHLC data
        returns = np.random.normal(0, 0.002, len(dates))
        prices = 1.1000 + np.cumsum(returns)

        data = []
        for i, (date, close) in enumerate(zip(dates, prices)):
            open_price = prices[i - 1] if i > 0 else close
            high = max(open_price, close) + abs(np.random.normal(0, 0.0003))
            low = min(open_price, close) - abs(np.random.normal(0, 0.0003))
            volume = np.random.randint(5000, 50000)

            data.append(
                {
                    "timestamp": date,
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                }
            )

        df = pd.DataFrame(data).set_index("timestamp")

        # Apply feature engineering
        features = create_basic_technical_features(
            df, indicators=["sma"], ma_periods=[5, 10], fillna=True
        )

        # Validate results
        assert len(features) == len(df)
        assert isinstance(features, pd.DataFrame)
