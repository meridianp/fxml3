"""
Integration tests for FRED data feed.

These tests validate the functionality of the FRED API client and its integration
with TimescaleDB for storing economic indicators.
"""

import os
from datetime import datetime, timedelta

import pandas as pd
import pytest

from fxml4.data_engineering.data_feeds.fred_feed import COMMON_INDICATORS, FREDDataFeed
from fxml4.data_engineering.timescaledb import TimescaleDBClient

# Skip tests if FRED_API_KEY is not available
skip_if_no_api_key = pytest.mark.skipif(
    os.environ.get("FRED_API_KEY") is None,
    reason="FRED_API_KEY environment variable not set",
)

# Skip tests if TimescaleDB is not available
skip_if_no_timescaledb = pytest.mark.skipif(
    not (os.environ.get("TIMESCALEDB_HOST") and os.environ.get("TIMESCALEDB_PORT")),
    reason="TimescaleDB connection details not available",
)


@pytest.fixture
def fred_client():
    """Create a FRED data feed client for testing."""
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        pytest.skip("FRED_API_KEY environment variable not set")

    return FREDDataFeed(config={"api_key": api_key, "use_cache": True})


@pytest.fixture
def db_client():
    """Create a TimescaleDB client for testing."""
    host = os.environ.get("TIMESCALEDB_HOST", "localhost")
    port = int(os.environ.get("TIMESCALEDB_PORT", "5432"))
    dbname = os.environ.get("TIMESCALEDB_DATABASE", "fxml4")
    user = os.environ.get("TIMESCALEDB_USER", "postgres")
    password = os.environ.get("TIMESCALEDB_PASSWORD", "postgres")

    try:
        client = TimescaleDBClient(
            host=host, port=port, dbname=dbname, user=user, password=password
        )

        # Test connection
        with client.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1

        return client
    except Exception as e:
        pytest.skip(f"TimescaleDB connection failed: {e}")


@skip_if_no_api_key
class TestFREDDataFeed:
    """Test cases for the FRED data feed."""

    def test_initialization(self, fred_client):
        """Test that the FRED client initializes properly."""
        assert fred_client is not None
        assert fred_client.api_key is not None

    def test_available_series(self, fred_client):
        """Test retrieving the list of available series."""
        series_list = fred_client.get_available_series()

        # Check that we got series data
        assert series_list is not None
        assert len(series_list) > 0

        # Check the structure of a series item
        first_series = series_list[0]
        assert "name" in first_series
        assert "series_id" in first_series
        assert "title" in first_series

    def test_get_single_series(self, fred_client):
        """Test retrieving a single economic series."""
        # Test with unemployment rate (UNRATE)
        df = fred_client.get_series(
            series_id="UNRATE",
            start_date=datetime.now() - timedelta(days=365 * 2),  # 2 years ago
        )

        # Check that we got data
        assert not df.empty
        assert "value" in df.columns

        # Check that the data has proper attributes
        assert hasattr(df, "attrs")
        assert "series_id" in df.attrs
        assert df.attrs["series_id"] == "UNRATE"

        # Check that the index is a DatetimeIndex
        assert isinstance(df.index, pd.DatetimeIndex)

    def test_get_multiple_series(self, fred_client):
        """Test retrieving multiple economic series at once."""
        # Test with multiple indicators
        series_dict = fred_client.get_multiple_series(
            series_ids=["UNRATE", "CPIAUCSL", "GDP", "FEDFUNDS"],
            start_date=datetime.now() - timedelta(days=365 * 3),  # 3 years ago
        )

        # Check that we got data for each series
        assert len(series_dict) == 4
        assert "UNRATE" in series_dict
        assert "CPIAUCSL" in series_dict
        assert "GDP" in series_dict
        assert "FEDFUNDS" in series_dict

        # Check that each DataFrame has data
        for series_id, df in series_dict.items():
            assert not df.empty, f"No data for {series_id}"
            assert "value" in df.columns

    def test_get_consolidated_series(self, fred_client):
        """Test retrieving and consolidating multiple series into one DataFrame."""
        # Test with multiple indicators
        df = fred_client.get_consolidated_series(
            series_ids=["UNRATE", "CPIAUCSL", "FEDFUNDS"],
            start_date=datetime.now() - timedelta(days=365 * 2),  # 2 years ago
        )

        # Check that we got a consolidated DataFrame
        assert not df.empty
        assert "UNRATE" in df.columns
        assert "CPIAUCSL" in df.columns
        assert "FEDFUNDS" in df.columns

        # Check that the index is a DatetimeIndex
        assert isinstance(df.index, pd.DatetimeIndex)

    def test_get_indicator_by_name(self, fred_client):
        """Test retrieving an indicator by its common name."""
        # Test with unemployment indicator
        df = fred_client.get_indicator_by_name(
            indicator_name="UNEMPLOYMENT",
            start_date=datetime.now() - timedelta(days=365),  # 1 year ago
        )

        # Check that we got data
        assert not df.empty
        assert "value" in df.columns

        # Verify that it's the correct series
        assert df.attrs["series_id"] == COMMON_INDICATORS["UNEMPLOYMENT"]

    def test_get_economic_calendar(self, fred_client):
        """Test retrieving the economic release calendar."""
        # Test getting upcoming releases
        calendar = fred_client.get_economic_calendar()

        # Check that we got a DataFrame (might be empty if no upcoming releases)
        assert isinstance(calendar, pd.DataFrame)

        # If we have data, check its structure
        if not calendar.empty:
            assert "name" in calendar.columns
            assert "release_date" in calendar.columns


@skip_if_no_api_key
@skip_if_no_timescaledb
class TestFREDTimescaleDBIntegration:
    """Test cases for FRED integration with TimescaleDB."""

    def test_store_series_in_timescaledb(self, fred_client, db_client):
        """Test storing FRED data in TimescaleDB."""
        # Store unemployment data
        records = fred_client.store_series_in_timescaledb(
            series_id="UNRATE",
            db_client=db_client,
            start_date=datetime.now() - timedelta(days=365 * 2),  # 2 years ago
        )

        # Check that some records were stored
        assert records > 0

        # Verify the data in the database
        with db_client.get_connection() as conn:
            cursor = conn.cursor()

            # Check if the exogenous_data table exists
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'exogenous_data'
                );
            """
            )

            table_exists = cursor.fetchone()[0]
            assert table_exists, "exogenous_data table does not exist"

            # Check if our data is in the table
            cursor.execute(
                """
                SELECT COUNT(*) FROM exogenous_data
                WHERE source = 'fred' AND indicator_name = 'UNRATE';
            """
            )

            count = cursor.fetchone()[0]
            assert count > 0, "No UNRATE data found in the database"

            # Check the structure of the stored data
            cursor.execute(
                """
                SELECT time, indicator_name, value, frequency, metadata
                FROM exogenous_data
                WHERE source = 'fred' AND indicator_name = 'UNRATE'
                ORDER BY time DESC
                LIMIT 1;
            """
            )

            row = cursor.fetchone()
            assert row is not None
            assert row[0] is not None  # time
            assert row[1] == "UNRATE"  # indicator_name
            assert row[2] is not None  # value
            assert row[3] is not None  # frequency
            assert row[4] is not None  # metadata

    def test_multi_indicator_storage(self, fred_client, db_client):
        """Test storing multiple indicators in TimescaleDB."""
        # Store multiple key indicators
        indicators = ["CPIAUCSL", "GDP", "FEDFUNDS"]  # CPI  # GDP  # Federal Funds Rate

        total_records = 0
        for series_id in indicators:
            records = fred_client.store_series_in_timescaledb(
                series_id=series_id,
                db_client=db_client,
                start_date=datetime.now() - timedelta(days=365),  # 1 year ago
            )
            total_records += records

        # Check that records were stored
        assert total_records > 0

        # Verify the data for each indicator
        with db_client.get_connection() as conn:
            cursor = conn.cursor()

            for series_id in indicators:
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM exogenous_data
                    WHERE source = 'fred' AND indicator_name = %s;
                """,
                    (series_id,),
                )

                count = cursor.fetchone()[0]
                assert count > 0, f"No {series_id} data found in the database"
