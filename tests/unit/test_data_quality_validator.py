#!/usr/bin/env python3
"""
Test suite for data quality validation system.
Retrospective tests for existing production data quality validation infrastructure.
"""

import asyncio
import json

# Import the module under test
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Tuple
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pandas as pd
import pytest

sys.path.append(str(Path(__file__).parent.parent.parent / "scripts"))
from data_quality_validator import (
    DataGap,
    DataQualityValidator,
    PriceAnomaly,
    QualityMetrics,
)


class TestDataGapDataClass:
    """Test DataGap dataclass behavior."""

    def test_data_gap_creation(self):
        """Test DataGap creation with all fields."""
        # Given: Valid gap data
        start_date = date(2023, 1, 1)
        end_date = date(2023, 1, 5)
        gap = DataGap(
            symbol="EURUSD",
            start_date=start_date,
            end_date=end_date,
            duration_days=5,
            severity="major",
        )

        # When: Accessing fields
        # Then: All fields are correctly stored
        assert gap.symbol == "EURUSD"
        assert gap.start_date == start_date
        assert gap.end_date == end_date
        assert gap.duration_days == 5
        assert gap.severity == "major"


class TestPriceAnomalyDataClass:
    """Test PriceAnomaly dataclass behavior."""

    def test_price_anomaly_creation(self):
        """Test PriceAnomaly creation with details."""
        # Given: Valid anomaly data
        timestamp = datetime(2023, 1, 1, 12, 0, 0)
        details = {"return": 0.05, "threshold": 0.01, "price": 1.1000}

        anomaly = PriceAnomaly(
            symbol="GBPUSD",
            timestamp=timestamp,
            anomaly_type="price_spike",
            severity="major",
            details=details,
        )

        # When: Accessing fields
        # Then: All fields are correctly stored
        assert anomaly.symbol == "GBPUSD"
        assert anomaly.timestamp == timestamp
        assert anomaly.anomaly_type == "price_spike"
        assert anomaly.severity == "major"
        assert anomaly.details == details


class TestQualityMetricsDataClass:
    """Test QualityMetrics dataclass behavior."""

    def test_quality_metrics_creation(self):
        """Test QualityMetrics creation with comprehensive data."""
        # Given: Complete quality metrics data
        date_range = (date(2023, 1, 1), date(2023, 1, 31))
        gaps = [DataGap("EURUSD", date(2023, 1, 5), date(2023, 1, 6), 2, "minor")]
        anomalies = [PriceAnomaly("EURUSD", datetime.now(), "price_spike", "major", {})]

        metrics = QualityMetrics(
            symbol="EURUSD",
            total_records=1000,
            date_range=date_range,
            completeness_score=0.95,
            accuracy_score=0.88,
            consistency_score=0.92,
            freshness_score=0.85,
            overall_quality=0.90,
            gaps=gaps,
            anomalies=anomalies,
        )

        # When: Accessing fields
        # Then: All metrics are correctly stored
        assert metrics.symbol == "EURUSD"
        assert metrics.total_records == 1000
        assert metrics.date_range == date_range
        assert metrics.completeness_score == 0.95
        assert metrics.accuracy_score == 0.88
        assert metrics.consistency_score == 0.92
        assert metrics.freshness_score == 0.85
        assert metrics.overall_quality == 0.90
        assert len(metrics.gaps) == 1
        assert len(metrics.anomalies) == 1


class TestDataQualityValidatorInitialization:
    """Test validator initialization and configuration."""

    def test_initialization_default_path(self):
        """Test validator initialization with default data path."""
        # Given: No custom path
        # When: Creating validator
        validator = DataQualityValidator()

        # Then: Default configuration is applied
        assert validator.data_path == Path("/polygon/processed")
        assert validator.major_pairs == [
            "EURUSD",
            "GBPUSD",
            "USDJPY",
            "AUDUSD",
            "USDCHF",
            "USDCAD",
        ]
        assert validator.thresholds["price_spike_factor"] == 0.01
        assert validator.thresholds["missing_data_minor"] == 0.05
        assert validator.thresholds["freshness_hours_good"] == 24

    def test_initialization_custom_path(self):
        """Test validator initialization with custom data path."""
        # Given: Custom data path
        custom_path = "/custom/data/path"

        # When: Creating validator
        validator = DataQualityValidator(data_path=custom_path)

        # Then: Custom path is used
        assert validator.data_path == Path(custom_path)
        assert validator.major_pairs == [
            "EURUSD",
            "GBPUSD",
            "USDJPY",
            "AUDUSD",
            "USDCHF",
            "USDCAD",
        ]


class TestDataGapDetection:
    """Test data gap detection functionality."""

    def test_detect_data_gaps_no_data(self, tmp_path):
        """Test gap detection when no data directory exists."""
        # Given: Validator with non-existent data path
        validator = DataQualityValidator(data_path=str(tmp_path))
        start_date = date(2023, 1, 1)
        end_date = date(2023, 1, 10)

        # When: Detecting gaps
        gaps = validator.detect_data_gaps("EURUSD", start_date, end_date)

        # Then: One critical gap covering entire period
        assert len(gaps) == 1
        assert gaps[0].symbol == "EURUSD"
        assert gaps[0].start_date == start_date
        assert gaps[0].end_date == end_date
        assert gaps[0].severity == "critical"
        assert gaps[0].duration_days == 9

    def test_detect_data_gaps_with_files(self, tmp_path):
        """Test gap detection with some existing data files."""
        # Given: Directory with some data files
        symbol_path = tmp_path / "C_EURUSD"
        symbol_path.mkdir(parents=True)

        start_date = date(2023, 1, 1)
        end_date = date(2023, 1, 10)

        # Create files for days 1, 2, 3, 7, 8, 9, 10 (missing days 4, 5, 6)
        for day in [1, 2, 3, 7, 8, 9, 10]:
            test_date = date(2023, 1, day)
            day_path = (
                symbol_path
                / f"year={test_date.year}"
                / f"month={test_date.month}"
                / f"day={test_date.day}"
            )
            day_path.mkdir(parents=True, exist_ok=True)

            # Create mock parquet file with data
            data_file = day_path / "data.parquet.gz"
            data_file.touch()

        # Mock pyarrow to return data for existing files
        with patch("pyarrow.parquet.read_table") as mock_read_table:
            mock_table = Mock()
            mock_table.__len__ = Mock(return_value=100)  # Non-empty table
            mock_read_table.return_value = mock_table

            validator = DataQualityValidator(data_path=str(tmp_path))

            # When: Detecting gaps
            gaps = validator.detect_data_gaps("EURUSD", start_date, end_date)

            # Then: One gap for days 4, 5, 6
            assert len(gaps) == 1
            assert gaps[0].start_date == date(2023, 1, 4)
            assert gaps[0].end_date == date(2023, 1, 6)
            assert gaps[0].duration_days == 3
            assert gaps[0].severity == "minor"  # <= 1 day = minor, <= 7 days = major

    def test_classify_gap_severity(self):
        """Test gap severity classification."""
        # Given: Validator instance
        validator = DataQualityValidator()

        # When/Then: Testing different durations
        assert validator._classify_gap_severity(1) == "minor"
        assert validator._classify_gap_severity(3) == "major"
        assert validator._classify_gap_severity(7) == "major"
        assert validator._classify_gap_severity(10) == "critical"
        assert validator._classify_gap_severity(30) == "critical"


class TestPriceDataAnalysis:
    """Test price data anomaly detection."""

    def test_analyze_empty_data(self):
        """Test price analysis with empty DataFrame."""
        # Given: Validator and empty DataFrame
        validator = DataQualityValidator()
        empty_df = pd.DataFrame()

        # When: Analyzing price data
        anomalies = validator.analyze_price_data(empty_df, "EURUSD")

        # Then: No anomalies found
        assert anomalies == []

    def test_analyze_missing_columns(self):
        """Test price analysis with missing required columns."""
        # Given: DataFrame without required OHLC columns
        validator = DataQualityValidator()
        df = pd.DataFrame(
            {"price": [1.1000, 1.1010, 1.1020], "volume": [1000, 1500, 1200]}
        )

        # When: Analyzing price data
        anomalies = validator.analyze_price_data(df, "EURUSD")

        # Then: No anomalies due to missing columns
        assert anomalies == []

    def test_analyze_invalid_ohlc(self):
        """Test detection of invalid OHLC relationships."""
        # Given: DataFrame with invalid OHLC data
        validator = DataQualityValidator()
        df = pd.DataFrame(
            {
                "open": [1.1000, 1.1010, 1.1020],
                "high": [1.0990, 1.1020, 1.1030],  # First high < open (invalid)
                "low": [1.0980, 1.1005, 1.1015],
                "close": [1.1005, 1.1015, 1.1025],
            },
            index=pd.date_range("2023-01-01", periods=3, freq="1H"),
        )

        # When: Analyzing price data
        anomalies = validator.analyze_price_data(df, "EURUSD")

        # Then: Invalid OHLC anomaly detected
        invalid_ohlc_anomalies = [
            a for a in anomalies if a.anomaly_type == "invalid_ohlc"
        ]
        assert len(invalid_ohlc_anomalies) == 1
        assert invalid_ohlc_anomalies[0].severity == "major"
        assert invalid_ohlc_anomalies[0].details["high"] == 1.0990
        assert invalid_ohlc_anomalies[0].details["open"] == 1.1000

    def test_analyze_price_spikes(self):
        """Test detection of price spikes."""
        # Given: DataFrame with price spike
        validator = DataQualityValidator()
        df = pd.DataFrame(
            {
                "open": [1.1000, 1.1010, 1.1500, 1.1020],  # Large jump in 3rd row
                "high": [1.1005, 1.1015, 1.1510, 1.1025],
                "low": [1.0995, 1.1005, 1.1490, 1.1015],
                "close": [1.1002, 1.1012, 1.1502, 1.1022],  # ~45% spike
            },
            index=pd.date_range("2023-01-01", periods=4, freq="1H"),
        )

        # When: Analyzing price data
        anomalies = validator.analyze_price_data(df, "EURUSD")

        # Then: Price spike anomaly detected
        spike_anomalies = [a for a in anomalies if a.anomaly_type == "price_spike"]
        assert len(spike_anomalies) >= 1
        # Should detect significant return changes
        major_spikes = [a for a in spike_anomalies if a.severity == "major"]
        assert len(major_spikes) >= 1

    def test_analyze_volume_anomalies(self):
        """Test detection of volume anomalies."""
        # Given: DataFrame with volume spike
        validator = DataQualityValidator()
        df = pd.DataFrame(
            {
                "open": [1.1000, 1.1010, 1.1020, 1.1030],
                "high": [1.1005, 1.1015, 1.1025, 1.1035],
                "low": [1.0995, 1.1005, 1.1015, 1.1025],
                "close": [1.1002, 1.1012, 1.1022, 1.1032],
                "volume": [1000, 1200, 15000, 1100],  # 3rd row has ~12x normal volume
            },
            index=pd.date_range("2023-01-01", periods=4, freq="1H"),
        )

        # When: Analyzing price data
        anomalies = validator.analyze_price_data(df, "EURUSD")

        # Then: Volume anomaly detected
        volume_anomalies = [a for a in anomalies if a.anomaly_type == "volume_spike"]
        assert len(volume_anomalies) >= 1
        assert volume_anomalies[0].severity == "minor"
        assert volume_anomalies[0].details["volume"] == 15000


class TestQualityScoreCalculation:
    """Test quality score calculation methods."""

    def test_calculate_quality_scores_perfect_data(self):
        """Test quality scores for perfect data."""
        # Given: Validator and perfect data scenario
        validator = DataQualityValidator()
        start_date = date(2023, 1, 1)
        end_date = date(2023, 1, 10)
        date_range = (start_date, end_date)
        gaps = []  # No gaps
        anomalies = []  # No anomalies
        total_records = 1000

        # When: Calculating quality scores
        scores = validator.calculate_quality_scores(
            "EURUSD", total_records, date_range, gaps, anomalies
        )

        # Then: All scores should be high
        assert scores["completeness_score"] == 1.0  # No gaps
        assert scores["accuracy_score"] == 1.0  # No anomalies
        assert scores["consistency_score"] == 1.0  # No critical issues
        assert (
            scores["freshness_score"] == 1.0
        )  # Latest date is today (from date_range[1])
        assert scores["overall_quality"] == 1.0  # Perfect overall

    def test_calculate_quality_scores_with_issues(self):
        """Test quality scores with various data issues."""
        # Given: Data with gaps and anomalies
        validator = DataQualityValidator()
        start_date = date(2023, 1, 1)
        end_date = date(2023, 1, 10)  # 10 days total
        date_range = (start_date, date(2023, 1, 8))  # Data ends 2 days ago (not fresh)

        # 2 days of gaps out of 10 = 20% missing
        gaps = [
            DataGap("EURUSD", date(2023, 1, 3), date(2023, 1, 4), 2, "minor"),
        ]

        # Some anomalies
        anomalies = [
            PriceAnomaly("EURUSD", datetime.now(), "price_spike", "major", {}),
            PriceAnomaly("EURUSD", datetime.now(), "volume_spike", "minor", {}),
        ]
        total_records = 800

        # When: Calculating quality scores
        scores = validator.calculate_quality_scores(
            "EURUSD", total_records, date_range, gaps, anomalies
        )

        # Then: Scores reflect issues
        assert scores["completeness_score"] < 1.0  # Due to gaps
        assert scores["accuracy_score"] < 1.0  # Due to anomalies
        assert scores["consistency_score"] == 1.0  # No critical issues
        assert scores["freshness_score"] < 1.0  # Data ends 2 days ago
        assert scores["overall_quality"] < 1.0  # Overall quality reduced

    def test_calculate_quality_scores_critical_issues(self):
        """Test quality scores with critical issues."""
        # Given: Data with critical gaps and anomalies
        validator = DataQualityValidator()
        start_date = date(2023, 1, 1)
        end_date = date(2023, 1, 10)
        date_range = (start_date, end_date)

        gaps = [
            DataGap("EURUSD", date(2023, 1, 1), date(2023, 1, 10), 10, "critical"),
        ]
        anomalies = [
            PriceAnomaly("EURUSD", datetime.now(), "invalid_ohlc", "critical", {})
        ]
        total_records = 100

        # When: Calculating quality scores
        scores = validator.calculate_quality_scores(
            "EURUSD", total_records, date_range, gaps, anomalies
        )

        # Then: Scores are significantly reduced
        assert scores["completeness_score"] == 0.0  # 100% missing
        assert scores["accuracy_score"] < 0.5  # Critical anomalies heavily penalized
        assert scores["consistency_score"] <= 0.8  # Critical issues reduce by 20%
        assert scores["overall_quality"] < 0.5  # Very poor overall quality


class TestSymbolValidation:
    """Test single symbol validation."""

    @pytest.mark.asyncio
    async def test_validate_symbol_no_data(self, tmp_path):
        """Test symbol validation when no data exists."""
        # Given: Validator with empty data directory
        validator = DataQualityValidator(data_path=str(tmp_path))

        # When: Validating symbol
        metrics = await validator.validate_symbol("EURUSD", days_back=30)

        # Then: Metrics reflect no data
        assert metrics.symbol == "EURUSD"
        assert metrics.total_records == 0
        assert (
            len(metrics.gaps) >= 1
        )  # Should have at least one gap covering the period
        assert metrics.completeness_score == 0.0
        assert metrics.overall_quality == 0.0

    @pytest.mark.asyncio
    async def test_validate_symbol_with_data(self, tmp_path):
        """Test symbol validation with existing data."""
        # Given: Data directory with some files
        symbol_path = tmp_path / "C_EURUSD"
        symbol_path.mkdir(parents=True)

        # Create a few days of data files
        for day in range(1, 4):  # 3 days of data
            test_date = date.today() - timedelta(days=day)
            day_path = (
                symbol_path
                / f"year={test_date.year}"
                / f"month={test_date.month}"
                / f"day={test_date.day}"
            )
            day_path.mkdir(parents=True, exist_ok=True)
            (day_path / "data.parquet.gz").touch()

        # Mock pandas and pyarrow for data loading
        with patch("pyarrow.parquet.read_table") as mock_read_table:
            # Mock table with realistic forex data
            mock_table = Mock()
            sample_df = pd.DataFrame(
                {
                    "open": [1.1000, 1.1010, 1.1020],
                    "high": [1.1005, 1.1015, 1.1025],
                    "low": [1.0995, 1.1005, 1.1015],
                    "close": [1.1002, 1.1012, 1.1022],
                    "volume": [1000, 1200, 1100],
                    "timestamp": pd.date_range("2023-01-01", periods=3, freq="5T"),
                }
            )
            mock_table.to_pandas.return_value = sample_df
            mock_table.__len__ = Mock(return_value=3)
            mock_read_table.return_value = mock_table

            validator = DataQualityValidator(data_path=str(tmp_path))

            # When: Validating symbol
            metrics = await validator.validate_symbol("EURUSD", days_back=30)

            # Then: Metrics reflect the data
            assert metrics.symbol == "EURUSD"
            assert metrics.total_records > 0
            assert 0 <= metrics.overall_quality <= 1
            assert isinstance(metrics.gaps, list)
            assert isinstance(metrics.anomalies, list)


class TestComprehensiveValidation:
    """Test comprehensive validation for multiple symbols."""

    @pytest.mark.asyncio
    async def test_comprehensive_validation_default_symbols(self):
        """Test comprehensive validation with default major pairs."""
        # Given: Validator instance
        validator = DataQualityValidator()

        # Mock validate_symbol to return consistent results
        mock_metrics = QualityMetrics(
            symbol="TEST",
            total_records=1000,
            date_range=(date.today() - timedelta(days=30), date.today()),
            completeness_score=0.9,
            accuracy_score=0.85,
            consistency_score=0.88,
            freshness_score=0.95,
            overall_quality=0.89,
            gaps=[],
            anomalies=[],
        )

        with patch.object(
            validator, "validate_symbol", return_value=mock_metrics
        ) as mock_validate:
            # When: Running comprehensive validation
            report = await validator.run_comprehensive_validation()

            # Then: All major pairs are validated
            assert report["symbols_analyzed"] == 6  # Major pairs
            assert len(report["symbol_metrics"]) == 6
            assert mock_validate.call_count == 6

            # Check report structure
            assert "timestamp" in report
            assert "summary" in report
            assert "recommendations" in report
            assert report["summary"]["average_quality_score"] == 0.89

    @pytest.mark.asyncio
    async def test_comprehensive_validation_custom_symbols(self):
        """Test comprehensive validation with custom symbol list."""
        # Given: Validator and custom symbols
        validator = DataQualityValidator()
        custom_symbols = ["EURUSD", "GBPUSD"]

        # Mock validate_symbol
        def mock_validate_symbol(symbol):
            return QualityMetrics(
                symbol=symbol,
                total_records=500,
                date_range=(date.today() - timedelta(days=10), date.today()),
                completeness_score=0.8,
                accuracy_score=0.75,
                consistency_score=0.82,
                freshness_score=0.9,
                overall_quality=0.82,
                gaps=[],
                anomalies=[],
            )

        with patch.object(
            validator, "validate_symbol", side_effect=mock_validate_symbol
        ):
            # When: Running validation with custom symbols
            report = await validator.run_comprehensive_validation(
                symbols=custom_symbols
            )

            # Then: Only custom symbols are validated
            assert report["symbols_analyzed"] == 2
            assert set(report["symbol_metrics"].keys()) == set(custom_symbols)

    @pytest.mark.asyncio
    async def test_comprehensive_validation_quality_classification(self):
        """Test quality classification in comprehensive validation."""
        # Given: Validator with mixed quality results
        validator = DataQualityValidator()

        def mock_validate_symbol(symbol):
            # Return different quality levels for different symbols
            quality_map = {
                "EURUSD": 0.9,  # High quality
                "GBPUSD": 0.7,  # Medium quality
                "USDJPY": 0.4,  # Low quality
            }
            return QualityMetrics(
                symbol=symbol,
                total_records=1000,
                date_range=(date.today() - timedelta(days=30), date.today()),
                completeness_score=quality_map[symbol],
                accuracy_score=quality_map[symbol],
                consistency_score=quality_map[symbol],
                freshness_score=quality_map[symbol],
                overall_quality=quality_map[symbol],
                gaps=[],
                anomalies=[],
            )

        with patch.object(
            validator, "validate_symbol", side_effect=mock_validate_symbol
        ):
            # When: Running validation
            report = await validator.run_comprehensive_validation(
                ["EURUSD", "GBPUSD", "USDJPY"]
            )

            # Then: Quality classification is correct
            assert "EURUSD" in report["summary"]["high_quality_symbols"]  # >= 0.8
            assert "GBPUSD" in report["summary"]["medium_quality_symbols"]  # 0.5-0.8
            assert "USDJPY" in report["summary"]["low_quality_symbols"]  # < 0.5


class TestRecommendationGeneration:
    """Test recommendation generation."""

    def test_generate_recommendations_good_data(self):
        """Test recommendations for good quality data."""
        # Given: Validator and high-quality metrics
        validator = DataQualityValidator()
        metrics = QualityMetrics(
            symbol="EURUSD",
            total_records=1000,
            date_range=(date.today() - timedelta(days=30), date.today()),
            completeness_score=0.95,
            accuracy_score=0.92,
            consistency_score=0.94,
            freshness_score=0.98,
            overall_quality=0.95,
            gaps=[],
            anomalies=[],
        )

        # When: Generating recommendations
        recommendations = validator._generate_recommendations({"EURUSD": metrics})

        # Then: Minimal or no recommendations
        assert len(recommendations) <= 1  # Maybe global recommendation or none

    def test_generate_recommendations_poor_data(self):
        """Test recommendations for poor quality data."""
        # Given: Validator and poor-quality metrics
        validator = DataQualityValidator()

        # Create poor quality metrics
        critical_gap = DataGap(
            "EURUSD",
            date.today() - timedelta(days=10),
            date.today() - timedelta(days=5),
            5,
            "critical",
        )
        major_anomalies = [
            PriceAnomaly("EURUSD", datetime.now(), "price_spike", "major", {})
            for _ in range(15)  # More than 10 major anomalies
        ]

        metrics = QualityMetrics(
            symbol="EURUSD",
            total_records=500,
            date_range=(
                date.today() - timedelta(days=30),
                date.today() - timedelta(days=10),
            ),
            completeness_score=0.3,
            accuracy_score=0.4,
            consistency_score=0.2,
            freshness_score=0.2,  # Stale data
            overall_quality=0.3,  # Poor quality
            gaps=[critical_gap],
            anomalies=major_anomalies,
        )

        # When: Generating recommendations
        recommendations = validator._generate_recommendations({"EURUSD": metrics})

        # Then: Multiple recommendations generated
        assert len(recommendations) >= 3

        # Check specific recommendation types
        recommendation_text = " ".join(recommendations)
        assert "stale" in recommendation_text or "Update data" in recommendation_text
        assert "critical data gaps" in recommendation_text
        assert "quality issues" in recommendation_text
        assert "anomalies" in recommendation_text


class TestProductionBehaviorValidation:
    """Test against known production behavior patterns."""

    @pytest.mark.integration
    def test_validator_handles_major_currency_pairs(self):
        """Test validator works with all major currency pairs."""
        # Given: Validator with production major pairs
        validator = DataQualityValidator()

        # When: Checking major pairs configuration
        # Then: All expected pairs are present
        expected_pairs = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD"]
        assert validator.major_pairs == expected_pairs

    def test_validator_thresholds_realistic(self):
        """Test validator thresholds are realistic for forex data."""
        # Given: Validator instance
        validator = DataQualityValidator()

        # When: Checking thresholds
        thresholds = validator.thresholds

        # Then: Thresholds are realistic for forex
        assert (
            0.005 <= thresholds["price_spike_factor"] <= 0.02
        )  # 0.5-2% spike detection
        assert 5 <= thresholds["volume_anomaly_factor"] <= 20  # 5-20x volume spike
        assert 0.01 <= thresholds["missing_data_minor"] <= 0.1  # 1-10% missing = minor
        assert thresholds["freshness_hours_good"] == 24  # Daily data freshness

    @pytest.mark.asyncio
    async def test_comprehensive_validation_performance(self):
        """Test comprehensive validation completes in reasonable time."""
        # Given: Validator with performance monitoring
        validator = DataQualityValidator()

        # Mock fast validation results
        fast_metrics = QualityMetrics(
            symbol="TEST",
            total_records=100,
            date_range=(date.today(), date.today()),
            completeness_score=1.0,
            accuracy_score=1.0,
            consistency_score=1.0,
            freshness_score=1.0,
            overall_quality=1.0,
            gaps=[],
            anomalies=[],
        )

        with patch.object(validator, "validate_symbol", return_value=fast_metrics):
            # When: Running comprehensive validation
            start_time = datetime.now()
            await validator.run_comprehensive_validation(["EURUSD", "GBPUSD"])
            elapsed = (datetime.now() - start_time).total_seconds()

            # Then: Completes within reasonable time
            assert elapsed < 10.0  # Should complete in under 10 seconds


@pytest.mark.slow
class TestPerformanceBehavior:
    """Test performance characteristics of validation system."""

    def test_price_analysis_large_dataset_sampling(self):
        """Test that large datasets are properly sampled for analysis."""
        # Given: Validator and large DataFrame
        validator = DataQualityValidator()

        # Create large DataFrame (> 10,000 rows)
        large_df = pd.DataFrame(
            {
                "open": np.random.normal(1.1000, 0.01, 15000),
                "high": np.random.normal(1.1005, 0.01, 15000),
                "low": np.random.normal(1.0995, 0.01, 15000),
                "close": np.random.normal(1.1000, 0.01, 15000),
                "volume": np.random.normal(1000, 200, 15000),
            },
            index=pd.date_range("2023-01-01", periods=15000, freq="1T"),
        )

        # When: Analyzing large dataset
        start_time = datetime.now()
        anomalies = validator.analyze_price_data(large_df, "EURUSD")
        elapsed = (datetime.now() - start_time).total_seconds()

        # Then: Analysis completes in reasonable time due to sampling
        assert elapsed < 30.0  # Should complete within 30 seconds
        assert isinstance(anomalies, list)  # Should return results


class TestErrorHandling:
    """Test error handling in validation system."""

    def test_analyze_price_data_with_nans(self):
        """Test price analysis handles NaN values gracefully."""
        # Given: DataFrame with NaN values
        validator = DataQualityValidator()
        df = pd.DataFrame(
            {
                "open": [1.1000, np.nan, 1.1020],
                "high": [1.1005, 1.1015, np.nan],
                "low": [1.0995, 1.1005, 1.1015],
                "close": [1.1002, 1.1012, 1.1022],
            },
            index=pd.date_range("2023-01-01", periods=3, freq="1H"),
        )

        # When: Analyzing data with NaNs
        # Then: Should not raise exception
        anomalies = validator.analyze_price_data(df, "EURUSD")
        assert isinstance(anomalies, list)

    @pytest.mark.asyncio
    async def test_validate_symbol_file_read_errors(self, tmp_path):
        """Test symbol validation handles file read errors gracefully."""
        # Given: Validator and corrupted data file
        symbol_path = tmp_path / "C_EURUSD"
        symbol_path.mkdir(parents=True)

        # Create a file that will cause read error
        test_date = date.today()
        day_path = (
            symbol_path
            / f"year={test_date.year}"
            / f"month={test_date.month}"
            / f"day={test_date.day}"
        )
        day_path.mkdir(parents=True, exist_ok=True)
        (day_path / "data.parquet.gz").write_text("corrupted data")

        # Mock pyarrow to raise exception
        with patch(
            "pyarrow.parquet.read_table", side_effect=Exception("Corrupted file")
        ):
            validator = DataQualityValidator(data_path=str(tmp_path))

            # When: Validating symbol with corrupted file
            # Then: Should not raise exception, return valid metrics
            metrics = await validator.validate_symbol("EURUSD", days_back=1)
            assert isinstance(metrics, QualityMetrics)
            assert metrics.symbol == "EURUSD"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
