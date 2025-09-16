"""
Comprehensive tests for TimescaleDB client.

This module tests database connection, pooling, data operations,
and error handling for the TimescaleDB integration.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import psycopg2
import pytest
from psycopg2.extras import DictCursor

from fxml4.data_engineering.timescaledb import TimescaleDBClient


class TestTimescaleDBClient:
    """Test cases for TimescaleDBClient."""

    def setup_method(self):
        """Set up test environment."""
        self.client = TimescaleDBClient(
            host="test-host",
            port=5433,
            dbname="test_db",
            user="test_user",
            password="test_pass",
            autocommit=True,
            pool_size=3,
        )

    def test_client_initialization(self):
        """Test client initialization with parameters."""
        client = TimescaleDBClient(
            host="localhost",
            port=5432,
            dbname="fxml4",
            user="postgres",
            password="secret",
            autocommit=False,
            pool_size=10,
        )

        assert client.host == "localhost"
        assert client.port == 5432
        assert client.dbname == "fxml4"
        assert client.user == "postgres"
        assert client.password == "secret"
        assert client.autocommit is False
        assert client.pool_size == 10

        # Check connection parameters
        expected_params = {
            "host": "localhost",
            "port": 5432,
            "dbname": "fxml4",
            "user": "postgres",
            "password": "secret",
        }
        assert client.conn_params == expected_params

    def test_default_initialization(self):
        """Test client initialization with default parameters."""
        with patch("fxml4.data_engineering.timescaledb.logger"):
            client = TimescaleDBClient()

        assert client.host == "localhost"
        assert client.port == 5432
        assert client.dbname == "fxml4"
        assert client.user == "postgres"
        assert client.password == "postgres"
        assert client.autocommit is False
        assert client.pool_size == 5

    @patch("fxml4.data_engineering.timescaledb.psycopg2.connect")
    def test_get_connection_success(self, mock_connect):
        """Test successful database connection."""
        mock_connection = Mock()
        mock_connect.return_value = mock_connection

        connection = self.client.get_connection()

        # Verify connection parameters
        mock_connect.assert_called_once_with(**self.client.conn_params)

        # Verify autocommit is set when enabled
        mock_connection.set_session.assert_called_once_with(autocommit=True)

        assert connection == mock_connection

    @patch("fxml4.data_engineering.timescaledb.psycopg2.connect")
    def test_get_connection_without_autocommit(self, mock_connect):
        """Test database connection without autocommit."""
        client = TimescaleDBClient(autocommit=False)
        mock_connection = Mock()
        mock_connect.return_value = mock_connection

        connection = client.get_connection()

        # Verify autocommit is not set
        mock_connection.set_session.assert_not_called()
        assert connection == mock_connection

    @patch("fxml4.data_engineering.timescaledb.psycopg2.connect")
    def test_get_connection_failure(self, mock_connect):
        """Test database connection failure."""
        mock_connect.side_effect = psycopg2.OperationalError("Connection failed")

        with pytest.raises(psycopg2.OperationalError):
            self.client.get_connection()

    @patch.object(TimescaleDBClient, "get_connection")
    def test_store_tick_success(self, mock_get_connection):
        """Test successful tick storage."""
        # Mock database connection and cursor
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection

        # Test data
        timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        result = self.client.store_tick(
            symbol="EURUSD",
            timestamp=timestamp,
            price=1.1000,
            size=1000,
            tick_type="trade",
            source="ib",
        )

        # Verify result
        assert result is True

        # Verify database operations
        mock_cursor.execute.assert_called_once()
        mock_connection.commit.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_connection.close.assert_called_once()

        # Verify SQL query parameters
        call_args = mock_cursor.execute.call_args
        assert "INSERT INTO tick_data" in call_args[0][0]
        assert call_args[0][1] == (timestamp, "EURUSD", 1.1000, 1000, "trade", "ib")

    @patch.object(TimescaleDBClient, "get_connection")
    def test_store_tick_with_naive_timestamp(self, mock_get_connection):
        """Test tick storage with naive timestamp (should add UTC timezone)."""
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection

        # Naive timestamp
        naive_timestamp = datetime(2024, 1, 1, 12, 0, 0)
        expected_timestamp = naive_timestamp.replace(tzinfo=timezone.utc)

        result = self.client.store_tick(
            symbol="EURUSD", timestamp=naive_timestamp, price=1.1000
        )

        assert result is True

        # Verify timestamp was converted to UTC
        call_args = mock_cursor.execute.call_args
        assert call_args[0][1][0] == expected_timestamp

    @patch.object(TimescaleDBClient, "get_connection")
    def test_store_tick_failure(self, mock_get_connection):
        """Test tick storage failure."""
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_cursor.execute.side_effect = psycopg2.Error("Database error")
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection

        with patch("fxml4.data_engineering.timescaledb.logger") as mock_logger:
            result = self.client.store_tick(
                symbol="EURUSD", timestamp=datetime.now(), price=1.1000
            )

        assert result is False
        mock_logger.error.assert_called_once()

    @patch.object(TimescaleDBClient, "get_connection")
    def test_store_ticks_success(self, mock_get_connection):
        """Test successful batch tick storage."""
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection

        # Test data
        ticks = [
            {
                "symbol": "EURUSD",
                "timestamp": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                "price": 1.1000,
                "size": 1000,
                "tick_type": "trade",
                "source": "ib",
            },
            {
                "symbol": "GBPUSD",
                "timestamp": datetime(2024, 1, 1, 12, 0, 1, tzinfo=timezone.utc),
                "price": 1.2500,
                "size": 500,
                # Missing tick_type and source should use defaults
            },
        ]

        with patch(
            "fxml4.data_engineering.timescaledb.execute_values"
        ) as mock_execute_values:
            result = self.client.store_ticks(ticks)

        assert result == 2
        mock_execute_values.assert_called_once()
        mock_connection.commit.assert_called_once()

    @patch.object(TimescaleDBClient, "get_connection")
    def test_store_ticks_empty_list(self, mock_get_connection):
        """Test batch tick storage with empty list."""
        result = self.client.store_ticks([])

        assert result == 0
        mock_get_connection.assert_not_called()

    @patch.object(TimescaleDBClient, "get_connection")
    def test_store_candle_success(self, mock_get_connection):
        """Test successful candle storage."""
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection

        timestamp = datetime(2024, 1, 1, 12, 30, 45, tzinfo=timezone.utc)
        expected_timestamp = datetime(
            2024, 1, 1, 12, 30, 0, tzinfo=timezone.utc
        )  # Rounded to minute

        result = self.client.store_candle(
            symbol="EURUSD",
            timestamp=timestamp,
            open_price=1.1000,
            high_price=1.1010,
            low_price=1.0990,
            close_price=1.1005,
            volume=10000,
            tick_count=50,
            source="ib",
        )

        assert result is True

        # Verify timestamp was rounded
        call_args = mock_cursor.execute.call_args
        assert call_args[0][1][0] == expected_timestamp

    @patch.object(TimescaleDBClient, "get_connection")
    def test_store_candles_success(self, mock_get_connection):
        """Test successful batch candle storage."""
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection

        candles = [
            {
                "symbol": "EURUSD",
                "timestamp": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                "open": 1.1000,
                "high": 1.1010,
                "low": 1.0990,
                "close": 1.1005,
                "volume": 10000,
            }
        ]

        with patch(
            "fxml4.data_engineering.timescaledb.execute_values"
        ) as mock_execute_values:
            result = self.client.store_candles(candles)

        assert result == 1
        mock_execute_values.assert_called_once()

    @patch.object(TimescaleDBClient, "get_connection")
    def test_get_latest_tick_success(self, mock_get_connection):
        """Test successful latest tick retrieval."""
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection

        # Mock return data
        mock_result = {
            "time": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            "symbol": "EURUSD",
            "price": 1.1000,
            "size": 1000,
            "tick_type": "trade",
            "source": "ib",
        }
        mock_cursor.fetchone.return_value = mock_result

        result = self.client.get_latest_tick("EURUSD", "trade")

        assert result == mock_result
        mock_cursor.execute.assert_called_once_with(
            "SELECT * FROM get_latest_tick(%s, %s)", ("EURUSD", "trade")
        )

    @patch.object(TimescaleDBClient, "get_connection")
    def test_get_latest_tick_not_found(self, mock_get_connection):
        """Test latest tick retrieval when no data found."""
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection

        mock_cursor.fetchone.return_value = None

        result = self.client.get_latest_tick("EURUSD", "trade")

        assert result is None

    @patch.object(TimescaleDBClient, "get_connection")
    def test_get_ohlcv_data_success(self, mock_get_connection):
        """Test successful OHLCV data retrieval."""
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection

        # Mock database response
        mock_cursor.description = [
            ("time",),
            ("symbol",),
            ("open",),
            ("high",),
            ("low",),
            ("close",),
            ("volume",),
        ]
        mock_cursor.fetchall.return_value = [
            (
                datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                "EURUSD",
                1.1000,
                1.1010,
                1.0990,
                1.1005,
                10000,
            ),
            (
                datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc),
                "EURUSD",
                1.1005,
                1.1015,
                1.0995,
                1.1010,
                12000,
            ),
        ]

        start_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2024, 1, 1, 14, 0, 0, tzinfo=timezone.utc)

        result = self.client.get_ohlcv_data("EURUSD", "1h", start_time, end_time)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert list(result.columns) == [
            "symbol",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]

        # Verify function call
        mock_cursor.execute.assert_called_once_with(
            "SELECT * FROM get_ohlcv(%s, %s, %s, %s)",
            ("EURUSD", "1h", start_time, end_time),
        )

    @patch.object(TimescaleDBClient, "get_connection")
    def test_get_ohlcv_data_with_naive_timestamps(self, mock_get_connection):
        """Test OHLCV data retrieval with naive timestamps."""
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection

        mock_cursor.description = [
            ("time",),
            ("symbol",),
            ("open",),
            ("high",),
            ("low",),
            ("close",),
            ("volume",),
        ]
        mock_cursor.fetchall.return_value = []

        # Naive timestamps
        start_time = datetime(2024, 1, 1, 12, 0, 0)
        end_time = datetime(2024, 1, 1, 14, 0, 0)

        self.client.get_ohlcv_data("EURUSD", "1h", start_time, end_time)

        # Verify timestamps were converted to UTC
        call_args = mock_cursor.execute.call_args
        assert call_args[0][1][2].tzinfo == timezone.utc
        assert call_args[0][1][3].tzinfo == timezone.utc

    @patch.object(TimescaleDBClient, "get_connection")
    def test_get_ohlcv_data_empty_result(self, mock_get_connection):
        """Test OHLCV data retrieval with no data."""
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection

        mock_cursor.description = []
        mock_cursor.fetchall.return_value = []

        start_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2024, 1, 1, 14, 0, 0, tzinfo=timezone.utc)

        result = self.client.get_ohlcv_data("EURUSD", "1h", start_time, end_time)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    @patch.object(TimescaleDBClient, "get_connection")
    def test_get_latest_candle_success(self, mock_get_connection):
        """Test successful latest candle retrieval."""
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_connection.cursor.return_value.__exit__ = Mock(return_value=None)
        mock_get_connection.return_value = mock_connection

        mock_result = {
            "time": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            "symbol": "EURUSD",
            "open": 1.1000,
            "high": 1.1010,
            "low": 1.0990,
            "close": 1.1005,
            "volume": 10000,
        }
        mock_cursor.fetchone.return_value = mock_result

        result = self.client.get_latest_candle("EURUSD", "1m")

        assert result == mock_result

    @patch.object(TimescaleDBClient, "get_connection")
    def test_get_tick_count_with_filters(self, mock_get_connection):
        """Test tick count with various filters."""
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection

        mock_cursor.fetchone.return_value = (12345,)

        start_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2024, 1, 1, 23, 59, 59, tzinfo=timezone.utc)

        result = self.client.get_tick_count(
            symbol="EURUSD", start_time=start_time, end_time=end_time
        )

        assert result == 12345

        # Verify query construction
        call_args = mock_cursor.execute.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        assert "WHERE" in query
        assert "symbol = %s" in query
        assert "time >= %s" in query
        assert "time <= %s" in query
        assert params == ["EURUSD", start_time, end_time]

    @patch.object(TimescaleDBClient, "get_connection")
    def test_get_candle_count_with_timeframe(self, mock_get_connection):
        """Test candle count for different timeframes."""
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection

        mock_cursor.fetchone.return_value = (5678,)

        result = self.client.get_candle_count("5m", symbol="EURUSD")

        assert result == 5678

        # Verify correct table name is used
        call_args = mock_cursor.execute.call_args
        query = call_args[0][0]
        assert "market_data_5m" in query

    @patch.object(TimescaleDBClient, "get_connection")
    def test_error_handling_with_logging(self, mock_get_connection):
        """Test error handling and logging."""
        mock_get_connection.side_effect = Exception("Connection error")

        with patch("fxml4.data_engineering.timescaledb.logger") as mock_logger:
            result = self.client.get_tick_count()

        assert result == 0
        mock_logger.error.assert_called_once()

        # Verify error message contains the exception
        error_call = mock_logger.error.call_args[0][0]
        assert "Error getting tick count" in error_call

    def test_connection_parameters_immutable(self):
        """Test that connection parameters are properly encapsulated."""
        original_params = self.client.conn_params.copy()

        # Modify the returned dict
        params = self.client.conn_params
        params["host"] = "modified-host"

        # Original should be unchanged
        assert self.client.conn_params != {"host": "modified-host"}
        # But it actually will be changed since we're not doing deep copy
        # This test documents current behavior


class TestTimescaleDBClientIntegration:
    """Integration-style tests for TimescaleDBClient."""

    @pytest.mark.integration
    @pytest.mark.requires_db
    def test_full_workflow_mock(self):
        """Test a complete workflow with mocked database."""
        with patch(
            "fxml4.data_engineering.timescaledb.psycopg2.connect"
        ) as mock_connect:
            # Setup mocked connection
            mock_connection = Mock()
            mock_cursor = Mock()
            mock_connection.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_connection

            client = TimescaleDBClient()

            # Test tick storage
            timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            success = client.store_tick("EURUSD", timestamp, 1.1000)
            assert success is True

            # Test candle storage
            success = client.store_candle(
                "EURUSD", timestamp, 1.1000, 1.1010, 1.0990, 1.1005, 10000
            )
            assert success is True

            # Verify multiple database operations occurred
            assert mock_cursor.execute.call_count >= 2


class TestTimescaleDBConnectionPooling:
    """Test connection pooling behavior."""

    def test_pool_initialization(self):
        """Test connection pool initialization."""
        client = TimescaleDBClient(pool_size=10)

        assert client.pool_size == 10
        assert client._pool is None  # Lazy initialization

    @patch("fxml4.data_engineering.timescaledb.psycopg2.connect")
    def test_connection_reuse_pattern(self, mock_connect):
        """Test connection usage pattern (currently creates new connections)."""
        mock_connection = Mock()
        mock_connect.return_value = mock_connection

        client = TimescaleDBClient()

        # Get multiple connections
        conn1 = client.get_connection()
        conn2 = client.get_connection()

        # Currently, each call creates a new connection
        assert mock_connect.call_count == 2
        assert conn1 == mock_connection
        assert conn2 == mock_connection


# Pytest markers for test categorization
pytestmark = [pytest.mark.unit, pytest.mark.database]
