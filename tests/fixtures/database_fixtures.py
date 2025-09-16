"""Database fixtures for testing.

This module provides reusable database fixtures for testing,
including setup, teardown, and data management.
"""

import asyncio
import sqlite3
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, Generator
from unittest.mock import AsyncMock, Mock

import pytest

# Use centralized event loop fixture
from tests.fixtures.event_loop_fixtures import event_loop

# Database imports
try:
    import asyncpg
    import psycopg2
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    ASYNC_DB_AVAILABLE = True
except ImportError:
    ASYNC_DB_AVAILABLE = False


def event_loop():
    """Create an instance of the default event loop for the test session."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sqlite_test_db():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Create connection and basic tables
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create test tables
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS test_market_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            open_price REAL NOT NULL,
            high_price REAL NOT NULL,
            low_price REAL NOT NULL,
            close_price REAL NOT NULL,
            volume INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS test_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            strength REAL NOT NULL,
            source TEXT NOT NULL,
            metadata TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS test_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            quantity REAL NOT NULL,
            price REAL NOT NULL,
            commission REAL DEFAULT 0.0,
            timestamp TEXT NOT NULL,
            order_id TEXT,
            execution_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS test_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            quantity REAL NOT NULL,
            avg_price REAL NOT NULL,
            current_price REAL,
            unrealized_pnl REAL DEFAULT 0.0,
            timestamp TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    conn.commit()

    yield {"path": db_path, "connection": conn, "cursor": cursor}

    # Cleanup
    conn.close()
    import os

    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def mock_database_connection():
    """Mock database connection for testing."""
    mock_conn = Mock()
    mock_cursor = Mock()

    # Setup connection methods
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.commit = Mock()
    mock_conn.rollback = Mock()
    mock_conn.close = Mock()
    mock_conn.execute = Mock()
    mock_conn.fetchone = Mock()
    mock_conn.fetchall = Mock()
    mock_conn.fetchmany = Mock()

    # Setup cursor methods
    mock_cursor.execute = Mock()
    mock_cursor.fetchone = Mock()
    mock_cursor.fetchall = Mock()
    mock_cursor.fetchmany = Mock()
    mock_cursor.close = Mock()
    mock_cursor.rowcount = 0
    mock_cursor.description = []

    return mock_conn


@pytest.fixture
async def mock_async_database():
    """Mock async database connection for testing."""
    mock_pool = AsyncMock()
    mock_conn = AsyncMock()

    # Pool methods
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_pool.acquire.return_value.__aexit__.return_value = None
    mock_pool.execute = AsyncMock()
    mock_pool.fetch = AsyncMock()
    mock_pool.fetchrow = AsyncMock()
    mock_pool.fetchval = AsyncMock()
    mock_pool.copy_records_to_table = AsyncMock()
    mock_pool.transaction = AsyncMock()

    # Connection methods
    mock_conn.execute = AsyncMock()
    mock_conn.fetch = AsyncMock()
    mock_conn.fetchrow = AsyncMock()
    mock_conn.fetchval = AsyncMock()
    mock_conn.copy_records_to_table = AsyncMock()
    mock_conn.transaction = AsyncMock()

    return mock_pool


@pytest.fixture
def database_test_data():
    """Sample test data for database operations."""
    return {
        "market_data": [
            {
                "symbol": "EURUSD",
                "timestamp": "2024-01-01T10:00:00Z",
                "open_price": 1.1000,
                "high_price": 1.1010,
                "low_price": 1.0990,
                "close_price": 1.1005,
                "volume": 1000000,
            },
            {
                "symbol": "GBPUSD",
                "timestamp": "2024-01-01T10:00:00Z",
                "open_price": 1.2500,
                "high_price": 1.2515,
                "low_price": 1.2485,
                "close_price": 1.2505,
                "volume": 750000,
            },
        ],
        "signals": [
            {
                "symbol": "EURUSD",
                "timestamp": "2024-01-01T10:00:00Z",
                "signal_type": "ENTRY_LONG",
                "strength": 0.8,
                "source": "ML",
                "metadata": '{"confidence": 0.85, "model": "random_forest"}',
            },
            {
                "symbol": "GBPUSD",
                "timestamp": "2024-01-01T10:05:00Z",
                "signal_type": "ENTRY_SHORT",
                "strength": 0.7,
                "source": "WAVE",
                "metadata": '{"pattern": "impulse_wave_5"}',
            },
        ],
        "trades": [
            {
                "symbol": "EURUSD",
                "side": "BUY",
                "quantity": 100000,
                "price": 1.1005,
                "commission": 2.50,
                "timestamp": "2024-01-01T10:01:00Z",
                "order_id": "ORDER_001",
                "execution_id": "EXEC_001",
            }
        ],
        "positions": [
            {
                "symbol": "EURUSD",
                "side": "LONG",
                "quantity": 100000,
                "avg_price": 1.1005,
                "current_price": 1.1010,
                "unrealized_pnl": 50.0,
                "timestamp": "2024-01-01T10:01:00Z",
            }
        ],
    }


@pytest.fixture
def populate_test_database(sqlite_test_db, database_test_data):
    """Populate test database with sample data."""
    conn = sqlite_test_db["connection"]
    cursor = sqlite_test_db["cursor"]

    # Insert market data
    for data in database_test_data["market_data"]:
        cursor.execute(
            """
            INSERT INTO test_market_data
            (symbol, timestamp, open_price, high_price, low_price, close_price, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                data["symbol"],
                data["timestamp"],
                data["open_price"],
                data["high_price"],
                data["low_price"],
                data["close_price"],
                data["volume"],
            ),
        )

    # Insert signals
    for data in database_test_data["signals"]:
        cursor.execute(
            """
            INSERT INTO test_signals
            (symbol, timestamp, signal_type, strength, source, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                data["symbol"],
                data["timestamp"],
                data["signal_type"],
                data["strength"],
                data["source"],
                data["metadata"],
            ),
        )

    # Insert trades
    for data in database_test_data["trades"]:
        cursor.execute(
            """
            INSERT INTO test_trades
            (symbol, side, quantity, price, commission, timestamp, order_id, execution_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                data["symbol"],
                data["side"],
                data["quantity"],
                data["price"],
                data["commission"],
                data["timestamp"],
                data["order_id"],
                data["execution_id"],
            ),
        )

    # Insert positions
    for data in database_test_data["positions"]:
        cursor.execute(
            """
            INSERT INTO test_positions
            (symbol, side, quantity, avg_price, current_price, unrealized_pnl, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                data["symbol"],
                data["side"],
                data["quantity"],
                data["avg_price"],
                data["current_price"],
                data["unrealized_pnl"],
                data["timestamp"],
            ),
        )

    conn.commit()

    return sqlite_test_db


# TimescaleDB-specific fixtures (if available)
if ASYNC_DB_AVAILABLE:

    @pytest.fixture
    async def mock_timescaledb_client():
        """Mock TimescaleDB client for testing."""
        from fxml4.data_engineering.async_timescaledb import AsyncTimescaleDBClient

        mock_client = Mock(spec=AsyncTimescaleDBClient)

        # Mock async methods
        mock_client.store_tick = AsyncMock(return_value=True)
        mock_client.store_ticks = AsyncMock(return_value=100)
        mock_client.store_candle = AsyncMock(return_value=True)
        mock_client.store_candles = AsyncMock(return_value=50)
        mock_client.get_latest_tick = AsyncMock(
            return_value={
                "time": datetime.now(timezone.utc),
                "symbol": "EURUSD",
                "price": 1.1000,
                "size": 1000,
                "tick_type": "trade",
                "source": "ib",
            }
        )
        mock_client.get_latest_candle = AsyncMock(
            return_value={
                "time": datetime.now(timezone.utc),
                "symbol": "EURUSD",
                "open": 1.1000,
                "high": 1.1010,
                "low": 1.0990,
                "close": 1.1005,
                "volume": 1000000,
            }
        )
        mock_client.get_tick_count = AsyncMock(return_value=1000)
        mock_client.get_candle_count = AsyncMock(return_value=100)
        mock_client.execute_query = AsyncMock()
        mock_client.fetch_query = AsyncMock(return_value=[])
        mock_client.fetchrow_query = AsyncMock(return_value=None)
        mock_client.fetchval_query = AsyncMock(return_value=None)

        return mock_client


@pytest.fixture
def database_cleaner():
    """Database cleanup utility for tests."""
    cleanup_tables = []

    def register_table(table_name: str):
        """Register a table for cleanup."""
        cleanup_tables.append(table_name)

    def cleanup_all(connection):
        """Clean up all registered tables."""
        cursor = connection.cursor()
        for table in cleanup_tables:
            try:
                cursor.execute(f"DELETE FROM {table}")
                connection.commit()
            except Exception as e:
                print(f"Warning: Failed to cleanup table {table}: {e}")

    # Return the register function
    register_table.cleanup_all = cleanup_all
    return register_table


@pytest.fixture
def database_transaction():
    """Database transaction context for test isolation."""

    @asynccontextmanager
    async def transaction_context(connection):
        """Provide a transaction context that can be rolled back."""
        if hasattr(connection, "begin"):
            # SQLAlchemy async connection
            async with connection.begin() as trans:
                try:
                    yield connection
                except Exception:
                    await trans.rollback()
                    raise
                else:
                    await trans.rollback()  # Always rollback in tests
        else:
            # Regular connection
            try:
                yield connection
            finally:
                if hasattr(connection, "rollback"):
                    connection.rollback()

    return transaction_context


@pytest.fixture
def sample_time_series_data():
    """Generate sample time series data for testing."""
    import numpy as np
    import pandas as pd

    np.random.seed(42)

    # Generate 24 hours of minute data
    timestamps = pd.date_range(
        start="2024-01-01 00:00:00", end="2024-01-01 23:59:00", freq="1min", tz="UTC"
    )

    # Generate realistic price data
    base_price = 1.1000
    price_changes = np.random.normal(0, 0.0001, len(timestamps))
    prices = base_price + np.cumsum(price_changes)

    data = []
    for i, (ts, close) in enumerate(zip(timestamps, prices)):
        # Generate OHLC for the minute
        open_price = prices[i - 1] if i > 0 else close
        high_price = max(open_price, close) + abs(np.random.normal(0, 0.00005))
        low_price = min(open_price, close) - abs(np.random.normal(0, 0.00005))
        volume = np.random.randint(1000, 10000)

        data.append(
            {
                "timestamp": ts.isoformat(),
                "symbol": "EURUSD",
                "open": round(open_price, 5),
                "high": round(high_price, 5),
                "low": round(low_price, 5),
                "close": round(close, 5),
                "volume": volume,
            }
        )

    return data


@pytest.fixture
def database_performance_monitor():
    """Monitor database performance during tests."""
    import time

    class PerformanceMonitor:
        def __init__(self):
            self.query_times = []
            self.connection_times = []

        def time_query(self, query_func):
            """Time a database query."""

            async def wrapper(*args, **kwargs):
                start = time.perf_counter()
                try:
                    result = await query_func(*args, **kwargs)
                    return result
                finally:
                    elapsed = time.perf_counter() - start
                    self.query_times.append(elapsed)

            return wrapper

        def get_stats(self):
            """Get performance statistics."""
            if not self.query_times:
                return {"avg_query_time": 0, "max_query_time": 0, "total_queries": 0}

            return {
                "avg_query_time": sum(self.query_times) / len(self.query_times),
                "max_query_time": max(self.query_times),
                "total_queries": len(self.query_times),
                "total_time": sum(self.query_times),
            }

    return PerformanceMonitor()
