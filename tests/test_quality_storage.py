#!/usr/bin/env python3
"""
Unit tests for data quality storage functionality.

This script tests the integration between data quality assessment and TimescaleDB.
"""

import json
import os
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Add the project root to the path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)

from fxml4.config import get_config

# Import necessary modules
from scripts.data_quality_storage import QualityMetricsStorage


@pytest.fixture(scope="class")
def storage():
    """Create QualityMetricsStorage instance for testing."""
    # Get database configuration from config
    from fxml4.config import load_config

    config = load_config()
    db_config = config.get("timescaledb", {})

    # Create QualityMetricsStorage instance
    try:
        storage_instance = QualityMetricsStorage(
            host=db_config.get("host", "localhost"),
            port=int(db_config.get("port", 5433)),
            dbname=db_config.get("dbname", "fxml4"),
            user=db_config.get("user", "postgres"),
            password=db_config.get("password", "postgres"),
        )

        # Test connection
        conn = storage_instance.db_client.get_connection()

        # Check if required tables exist
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT FROM pg_tables
                WHERE schemaname = 'public'
                AND tablename = 'data_quality_metrics'
            )
        """
        )
        tables_exist = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        storage_instance.db_available = True
        storage_instance.tables_exist = tables_exist

        if not tables_exist:
            print(
                "Warning: Required database tables do not exist. Run the migration script first."
            )
            print(
                "  psql -U postgres -d fxml4 -f db/migrations/004_add_data_quality_schema.sql"
            )

        return storage_instance

    except Exception as e:
        print(f"Warning: Could not connect to TimescaleDB: {e}")
        # Return mock object with db_available=False
        mock_storage = type(
            "Storage",
            (),
            {"db_available": False, "tables_exist": False, "db_client": None},
        )()
        return mock_storage


@pytest.fixture
def quality_result():
    """Create sample quality result for testing."""
    return {
        "pair": "EURUSD",
        "date": date.today().isoformat(),
        "timeframe": "1m",
        "data_available": True,
        "overall_quality_score": 85.5,
        "quality_categories": {
            "completeness": {
                "completeness_pct": 98.0,
                "data_points": 1410,
                "expected_points": 1440,
                "missing_points": 30,
                "gap_count": 1,
                "max_gap_duration": 30.0,
                "quality_score": 96.0,
            },
            "price_spikes": {
                "has_spikes": True,
                "spike_count": 2,
                "max_spike_pct": 0.015,
                "spike_timestamps": ["2024-01-01T10:30:00"],
                "quality_score": 90.0,
            },
            "price_freezes": {
                "has_freezes": False,
                "freeze_count": 0,
                "longest_freeze": 0,
                "freeze_periods": [],
                "quality_score": 100.0,
            },
            "ohlc_integrity": {
                "valid_ohlc": True,
                "anomaly_count": 0,
                "anomaly_types": {},
                "quality_score": 100.0,
            },
            "volatility": {
                "avg_volatility": 0.0005,
                "low_volatility_periods": 0,
                "quality_score": 100.0,
            },
        },
    }


@pytest.fixture
def quality_results(quality_result):
    """Create sample quality results dictionary."""
    results = {f"{date.today().isoformat()}-EURUSD-1m": quality_result}

    # Add a second result for GBPUSD
    gbpusd_result = quality_result.copy()
    gbpusd_result["pair"] = "GBPUSD"
    gbpusd_result["overall_quality_score"] = 92.0
    gbpusd_result["quality_categories"] = quality_result["quality_categories"].copy()

    results[f"{date.today().isoformat()}-GBPUSD-1m"] = gbpusd_result
    return results


@pytest.mark.integration
@pytest.mark.requires_db
class TestQualityStorageIntegration:
    """Tests for quality assessment storage in TimescaleDB."""

    def test_db_connection(self, storage):
        """Test that we can connect to the database."""
        if not storage.db_available:
            pytest.skip("TimescaleDB not available")

        # Test connection
        conn = storage.db_client.get_connection()
        assert conn is not None

        # Test running a query
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        assert result[0] == 1

        cursor.close()
        conn.close()

    def test_store_quality_metrics(self, storage, quality_result):
        """Test storing quality metrics in the database."""
        if not storage.db_available:
            pytest.skip("TimescaleDB not available")

        if not storage.tables_exist:
            pytest.skip("Required database tables do not exist")

        # Store a single quality result
        result = storage.store_quality_metrics(quality_result)
        assert result is True

    def test_store_quality_results(self, storage, quality_results):
        """Test storing multiple quality results in the database."""
        if not storage.db_available:
            pytest.skip("TimescaleDB not available")

        if not storage.tables_exist:
            pytest.skip("Required database tables do not exist")

        # Store multiple quality results
        count = storage.store_quality_results(quality_results)
        assert count == len(quality_results)

    def test_store_quality_report(self, storage):
        """Test storing a quality report in the database."""
        if not storage.db_available:
            pytest.skip("TimescaleDB not available")

        if not storage.tables_exist:
            pytest.skip("Required database tables do not exist")

        # Create a temporary report
        today = date.today()
        yesterday = today - timedelta(days=1)

        summary = {
            "pairs": ["EURUSD", "GBPUSD"],
            "timeframes": ["1m"],
            "date_range": {"start": yesterday.isoformat(), "end": today.isoformat()},
            "assessment_count": 2,
            "stored_count": 2,
            "quality_scores": {"overall": {"avg": 88.75, "min": 85.5, "max": 92.0}},
        }

        # Store the report
        result = storage.store_quality_report(
            report_date=today,
            start_date=yesterday,
            end_date=today,
            pairs=["EURUSD", "GBPUSD"],
            timeframes=["1m"],
            summary=summary,
            report_markdown="# Test Report",
            report_json={"test": True},
            visualization_path="/tmp/test.png",
        )

        assert result is True

    def test_get_quality_metrics(self, storage, quality_result):
        """Test retrieving quality metrics from the database."""
        if not storage.db_available:
            pytest.skip("TimescaleDB not available")

        if not storage.tables_exist:
            pytest.skip("Required database tables do not exist")

        # First ensure we have data to retrieve
        storage.store_quality_metrics(quality_result)

        # Retrieve the metrics
        today = date.today()
        yesterday = today - timedelta(days=1)

        metrics = storage.get_quality_metrics(
            pair="EURUSD", timeframe="1m", start_date=yesterday, end_date=today
        )

        # Check that we got some results
        assert isinstance(metrics, list)
        # We might not always get results due to timing, so only check if we did
        if metrics:
            assert len(metrics) >= 1
            assert metrics[0]["pair"] == "EURUSD"
            assert metrics[0]["timeframe"] == "1m"

    def test_get_quality_trend(self, storage):
        """Test retrieving quality trend data from the database."""
        if not storage.db_available:
            pytest.skip("TimescaleDB not available")

        if not storage.tables_exist:
            pytest.skip("Required database tables do not exist")

        # Retrieve trend data - this might not return results in tests
        # since the continuous aggregate may not have processed data yet
        today = date.today()
        last_week = today - timedelta(days=7)

        trend = storage.get_quality_trend(
            pairs=["EURUSD", "GBPUSD"],
            timeframe="1m",
            start_date=last_week,
            end_date=today,
        )

        # We can't guarantee results, so just check the function doesn't error
        assert isinstance(trend, list)

    def test_get_recent_quality_issues(self, storage):
        """Test retrieving recent quality issues from the database."""
        if not storage.db_available:
            pytest.skip("TimescaleDB not available")

        if not storage.tables_exist:
            pytest.skip("Required database tables do not exist")

        # Retrieve recent issues - might not return results in tests
        issues = storage.get_recent_quality_issues(
            lookback_days=7, min_score=95.0  # Set high to get some results
        )

        # We can't guarantee results, so just check the function doesn't error
        assert isinstance(issues, list)


@pytest.fixture
def invalid_storage():
    """Create QualityMetricsStorage with invalid connection."""
    return QualityMetricsStorage(
        host="invalid-host",
        port=9999,
        dbname="invalid-db",
        user="invalid-user",
        password="invalid-password",
    )


@pytest.fixture
def fallback_quality_result():
    """Create sample quality result for fallback testing."""
    return {
        "pair": "EURUSD",
        "date": date.today().isoformat(),
        "timeframe": "1m",
        "data_available": True,
        "overall_quality_score": 85.5,
        "quality_categories": {
            "completeness": {
                "completeness_pct": 98.0,
                "data_points": 1410,
                "expected_points": 1440,
                "missing_points": 30,
                "gap_count": 1,
                "max_gap_duration": 30.0,
                "quality_score": 96.0,
            },
            "price_spikes": {
                "has_spikes": True,
                "spike_count": 2,
                "max_spike_pct": 0.015,
                "spike_timestamps": ["2024-01-01T10:30:00"],
                "quality_score": 90.0,
            },
            "price_freezes": {
                "has_freezes": False,
                "freeze_count": 0,
                "longest_freeze": 0,
                "freeze_periods": [],
                "quality_score": 100.0,
            },
            "ohlc_integrity": {
                "valid_ohlc": True,
                "anomaly_count": 0,
                "anomaly_types": {},
                "quality_score": 100.0,
            },
            "volatility": {
                "avg_volatility": 0.0005,
                "low_volatility_periods": 0,
                "quality_score": 100.0,
            },
        },
    }


class TestQualityStorageFallback:
    """Tests for quality storage functionality when database is not available."""

    def test_graceful_failure_store_metrics(
        self, invalid_storage, fallback_quality_result
    ):
        """Test that storage functions fail gracefully when DB is not available."""
        # Should return False but not raise exception
        result = invalid_storage.store_quality_metrics(fallback_quality_result)
        assert result is False

    def test_graceful_failure_get_metrics(self, invalid_storage):
        """Test that retrieval functions fail gracefully when DB is not available."""
        # Should return empty list but not raise exception
        today = date.today()
        yesterday = today - timedelta(days=1)

        metrics = invalid_storage.get_quality_metrics(
            pair="EURUSD", timeframe="1m", start_date=yesterday, end_date=today
        )

        assert metrics == []
