"""Pytest configuration and shared fixtures for FXML4 tests."""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import aio_pika
import asyncpg
import redis.asyncio as redis


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_config() -> Dict[str, Any]:
    """Test configuration."""
    return {
        "db_host": "localhost",
        "db_port": 5432,
        "db_user": "postgres",
        "db_password": "postgres",
        "db_name": "fxml4_test",
        "rabbitmq_host": "localhost",
        "rabbitmq_user": "guest",
        "rabbitmq_pass": "guest",
        "redis_host": "localhost",
        "redis_port": 6379,
        "ib_gateway_host": "127.0.0.1",
        "ib_gateway_port": 7497,
        "ib_client_id": 999,  # Test client ID
    }


@pytest_asyncio.fixture
async def mock_db_pool():
    """Mock database pool."""
    pool = AsyncMock(spec=asyncpg.Pool)

    # Mock connection
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__.return_value = conn

    # Mock transaction
    conn.transaction.return_value.__aenter__.return_value = None
    conn.transaction.return_value.__aexit__.return_value = None

    # Default return values
    conn.execute.return_value = None
    conn.executemany.return_value = None
    conn.fetch.return_value = []
    conn.fetchrow.return_value = None
    conn.fetchval.return_value = None

    yield pool

    # Cleanup
    await pool.close()


@pytest_asyncio.fixture
async def mock_rabbitmq_connection():
    """Mock RabbitMQ connection and channel."""
    connection = AsyncMock(spec=aio_pika.Connection)
    channel = AsyncMock(spec=aio_pika.Channel)

    # Set up connection
    connection.is_closed = False
    connection.channel.return_value = channel

    # Set up channel
    channel.is_closed = False
    channel.set_qos = AsyncMock()

    # Mock exchange
    exchange = AsyncMock()
    exchange.publish = AsyncMock()
    channel.get_exchange.return_value = exchange
    channel.declare_exchange.return_value = exchange

    # Mock queue
    queue = AsyncMock()
    queue.bind = AsyncMock()
    queue.consume = AsyncMock()
    channel.get_queue.return_value = queue
    channel.declare_queue.return_value = queue

    yield connection, channel

    # Cleanup
    await connection.close()


@pytest_asyncio.fixture
async def mock_redis_client():
    """Mock Redis client."""
    client = AsyncMock(spec=redis.Redis)

    # Storage for mock Redis
    storage = {}

    # Mock get
    async def mock_get(key):
        return storage.get(key)

    # Mock set
    async def mock_set(key, value):
        storage[key] = value
        return True

    # Mock setex
    async def mock_setex(key, ttl, value):
        storage[key] = value
        return True

    # Mock delete
    async def mock_delete(key):
        if key in storage:
            del storage[key]
            return 1
        return 0

    client.get = mock_get
    client.set = mock_set
    client.setex = mock_setex
    client.delete = mock_delete
    client.ping = AsyncMock(return_value=True)
    client.close = AsyncMock()

    yield client

    # Cleanup
    await client.close()


@pytest.fixture
def mock_ib_gateway_client():
    """Mock IB Gateway client."""
    client = AsyncMock()

    # Connection methods
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.is_connected = MagicMock(return_value=True)

    # Market data methods
    client.subscribe_market_data = AsyncMock()
    client.unsubscribe_market_data = AsyncMock()
    client.get_market_data = AsyncMock()
    client.get_tick_data = AsyncMock()
    client.get_next_tick = AsyncMock(return_value=None)

    # Order methods
    client.place_order = AsyncMock()
    client.cancel_order = AsyncMock()
    client.get_order_status = AsyncMock()

    # Account methods
    client.get_account_summary = AsyncMock()
    client.get_positions = AsyncMock()

    return client


@pytest.fixture
def sample_market_data() -> Dict[str, Any]:
    """Sample market data for testing."""
    return {
        "time": datetime.utcnow(),
        "open": Decimal("1.0850"),
        "high": Decimal("1.0855"),
        "low": Decimal("1.0845"),
        "close": Decimal("1.0852"),
        "volume": 1000,
        "spread": Decimal("0.0001"),
        "bid": Decimal("1.0851"),
        "ask": Decimal("1.0852"),
    }


@pytest.fixture
def sample_tick_data() -> List[Dict[str, Any]]:
    """Sample tick data for testing."""
    base_time = datetime.utcnow()
    return [
        {
            "symbol": "EURUSD",
            "time": base_time,
            "price": Decimal("1.0850"),
            "size": 100,
            "type": "trade",
        },
        {
            "symbol": "EURUSD",
            "time": base_time + timedelta(seconds=1),
            "price": Decimal("1.0851"),
            "size": 200,
            "type": "trade",
        },
        {
            "symbol": "EURUSD",
            "time": base_time + timedelta(seconds=2),
            "price": Decimal("1.0852"),
            "size": 150,
            "type": "trade",
        },
    ]


@pytest.fixture
def sample_indicators() -> Dict[str, float]:
    """Sample technical indicators for testing."""
    return {
        "rsi_14": 55.5,
        "atr_14": 0.0012,
        "sma_20": 1.0848,
        "sma_50": 1.0845,
        "sma_200": 1.0840,
        "ema_9": 1.0849,
        "ema_21": 1.0847,
        "bb_upper": 1.0860,
        "bb_middle": 1.0848,
        "bb_lower": 1.0836,
        "macd": 0.0002,
        "macd_signal": 0.0001,
        "macd_histogram": 0.0001,
        "adx": 25.5,
        "plus_di": 22.3,
        "minus_di": 18.7,
        "stoch_k": 65.2,
        "stoch_d": 62.8,
    }


@pytest.fixture
def sample_signal() -> Dict[str, Any]:
    """Sample trading signal for testing."""
    return {
        "symbol": "EURUSD",
        "direction": "BUY",
        "entry_price": Decimal("1.0850"),
        "stop_loss": Decimal("1.0820"),
        "take_profit": Decimal("1.0880"),
        "confidence": 0.75,
        "timeframe": "4H",
        "signal_time": datetime.utcnow(),
        "source": "ml_model",
        "metadata": {"model_version": "1.0", "features_used": ["rsi", "macd", "bb"]},
    }


@pytest.fixture
def sample_trade() -> Dict[str, Any]:
    """Sample trade for testing."""
    return {
        "trade_id": "TEST-001",
        "symbol": "EURUSD",
        "direction": "BUY",
        "entry_price": Decimal("1.0850"),
        "entry_time": datetime.utcnow(),
        "position_size": Decimal("10000"),
        "stop_loss": Decimal("1.0820"),
        "take_profit": Decimal("1.0880"),
        "status": "open",
        "pnl": Decimal("0"),
        "commission": Decimal("2.50"),
    }


@pytest_asyncio.fixture
async def mock_base_service(
    test_config, mock_db_pool, mock_rabbitmq_connection, mock_redis_client
):
    """Create a mock base service for testing."""
    from shared.utils.base_service import BaseService

    class TestService(BaseService):
        async def service_setup(self):
            pass

        async def service_teardown(self):
            pass

        async def service_run(self):
            while self.running:
                await asyncio.sleep(0.1)

    # Create service
    service = TestService("test-service", test_config)

    # Inject mocks
    service.db_pool = mock_db_pool
    service.rabbitmq_connection, service.rabbitmq_channel = mock_rabbitmq_connection
    service.redis_client = mock_redis_client

    yield service

    # Cleanup
    service.running = False
    await service.teardown()


@pytest.fixture
def performance_benchmark():
    """Performance benchmarking fixture."""
    import time

    class Benchmark:
        def __init__(self):
            self.measurements = {}

        def start(self, name: str):
            self.measurements[name] = {"start": time.perf_counter()}

        def stop(self, name: str):
            if name in self.measurements:
                self.measurements[name]["end"] = time.perf_counter()
                self.measurements[name]["duration"] = (
                    self.measurements[name]["end"] - self.measurements[name]["start"]
                )

        def get_duration(self, name: str) -> float:
            return self.measurements.get(name, {}).get("duration", 0)

        def report(self):
            for name, data in self.measurements.items():
                if "duration" in data:
                    print(f"{name}: {data['duration']:.4f}s")

    return Benchmark()


# Async context managers for testing
@pytest.fixture
def async_context_manager():
    """Helper to create async context managers for testing."""

    class AsyncContextManager:
        def __init__(self, return_value=None):
            self.return_value = return_value
            self.entered = False
            self.exited = False

        async def __aenter__(self):
            self.entered = True
            return self.return_value

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            self.exited = True
            return False

    return AsyncContextManager


# Test database setup/teardown
@pytest_asyncio.fixture
async def test_db():
    """Create test database for integration tests."""
    if os.getenv("TESTING") != "true":
        pytest.skip("Integration test requires TESTING=true")

    # Connection parameters
    params = {
        "host": "localhost",
        "port": 5432,
        "user": "postgres",
        "password": "postgres",
        "database": "postgres",  # Connect to default db first
    }

    # Create test database
    conn = await asyncpg.connect(**params)
    try:
        await conn.execute("DROP DATABASE IF EXISTS fxml4_test")
        await conn.execute("CREATE DATABASE fxml4_test")
    finally:
        await conn.close()

    # Connect to test database
    params["database"] = "fxml4_test"
    pool = await asyncpg.create_pool(**params, min_size=1, max_size=5)

    # Run schema migrations (simplified for testing)
    async with pool.acquire() as conn:
        # Create schema
        await conn.execute("CREATE SCHEMA IF NOT EXISTS trading")

        # Create tables (simplified versions)
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trading.symbols (
                symbol VARCHAR(20) PRIMARY KEY,
                pip_size DECIMAL(10,6),
                min_tick_size DECIMAL(10,6),
                active BOOLEAN DEFAULT true
            )
        """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trading.market_data (
                time TIMESTAMPTZ NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                open DECIMAL(20,10),
                high DECIMAL(20,10),
                low DECIMAL(20,10),
                close DECIMAL(20,10),
                volume BIGINT,
                spread DECIMAL(20,10),
                tick_count INTEGER,
                PRIMARY KEY (time, symbol)
            )
        """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trading.system_events (
                event_time TIMESTAMPTZ NOT NULL,
                service_name VARCHAR(50),
                event_type VARCHAR(50),
                severity VARCHAR(20),
                message TEXT,
                details JSONB
            )
        """
        )

        # Insert test data
        await conn.execute(
            """
            INSERT INTO trading.symbols (symbol, pip_size, min_tick_size)
            VALUES
                ('EURUSD', 0.0001, 0.00001),
                ('GBPUSD', 0.0001, 0.00001),
                ('USDJPY', 0.01, 0.001)
        """
        )

    yield pool

    # Cleanup
    await pool.close()

    # Drop test database
    conn = await asyncpg.connect(**params)
    conn = await asyncpg.connect(
        host="localhost",
        port=5432,
        user="postgres",
        password="postgres",
        database="postgres",
    )
    try:
        await conn.execute("DROP DATABASE IF EXISTS fxml4_test")
    finally:
        await conn.close()


# Mock external API responses
@pytest.fixture
def mock_llm_response():
    """Mock LLM API response."""
    return {
        "analysis": "Bullish trend detected",
        "confidence": 0.85,
        "reasoning": "Strong upward momentum with breakout above resistance",
        "key_levels": {"support": [1.0820, 1.0800], "resistance": [1.0880, 1.0900]},
    }


# Utility functions for testing
@pytest.fixture
def assert_async():
    """Async assertion helper."""

    async def _assert(coro, expected=None, timeout=5):
        try:
            result = await asyncio.wait_for(coro, timeout=timeout)
            if expected is not None:
                assert result == expected
            return result
        except asyncio.TimeoutError:
            pytest.fail(f"Async operation timed out after {timeout}s")

    return _assert
