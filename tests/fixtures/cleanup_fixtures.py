"""
Automatic Cleanup Fixtures for WebSocket and RabbitMQ
======================================================

This module provides autouse fixtures that automatically clean up
WebSocket connections, RabbitMQ channels, and other resources after
each test to prevent connection leaks and test interference.

These fixtures are automatically applied to all tests when imported
in conftest.py, ensuring 100% resource cleanup.
"""

import asyncio
import logging
import weakref
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Dict, List, Optional, Set
from unittest.mock import AsyncMock, Mock

import pytest

logger = logging.getLogger(__name__)


# ============================================================================
# Global Resource Tracking
# ============================================================================


class ResourceTracker:
    """Track all resources created during tests for cleanup."""

    def __init__(self):
        self.websockets: Set[weakref.ref] = set()
        self.rabbitmq_channels: Set[weakref.ref] = set()
        self.rabbitmq_connections: Set[weakref.ref] = set()
        self.redis_connections: Set[weakref.ref] = set()
        self.db_connections: Set[weakref.ref] = set()
        self.temp_files: List[str] = []
        self.active_tasks: List[asyncio.Task] = []

    def track_websocket(self, ws):
        """Track a WebSocket connection."""
        self.websockets.add(weakref.ref(ws))
        logger.debug(f"Tracking WebSocket: {ws}")

    def track_rabbitmq_channel(self, channel):
        """Track a RabbitMQ channel."""
        self.rabbitmq_channels.add(weakref.ref(channel))
        logger.debug(f"Tracking RabbitMQ channel: {channel}")

    def track_rabbitmq_connection(self, connection):
        """Track a RabbitMQ connection."""
        self.rabbitmq_connections.add(weakref.ref(connection))
        logger.debug(f"Tracking RabbitMQ connection: {connection}")

    def track_redis_connection(self, connection):
        """Track a Redis connection."""
        self.redis_connections.add(weakref.ref(connection))
        logger.debug(f"Tracking Redis connection: {connection}")

    def track_db_connection(self, connection):
        """Track a database connection."""
        self.db_connections.add(weakref.ref(connection))
        logger.debug(f"Tracking DB connection: {connection}")

    def track_temp_file(self, filepath):
        """Track a temporary file."""
        self.temp_files.append(filepath)
        logger.debug(f"Tracking temp file: {filepath}")

    def track_task(self, task):
        """Track an asyncio task."""
        self.active_tasks.append(task)
        logger.debug(f"Tracking task: {task}")

    async def cleanup_all(self):
        """Clean up all tracked resources."""
        logger.info("Starting comprehensive resource cleanup")

        # Clean up WebSockets
        for ws_ref in self.websockets:
            ws = ws_ref()
            if ws:
                await self._cleanup_websocket(ws)
        self.websockets.clear()

        # Clean up RabbitMQ channels
        for channel_ref in self.rabbitmq_channels:
            channel = channel_ref()
            if channel:
                await self._cleanup_rabbitmq_channel(channel)
        self.rabbitmq_channels.clear()

        # Clean up RabbitMQ connections
        for conn_ref in self.rabbitmq_connections:
            conn = conn_ref()
            if conn:
                await self._cleanup_rabbitmq_connection(conn)
        self.rabbitmq_connections.clear()

        # Clean up Redis connections
        for redis_ref in self.redis_connections:
            redis = redis_ref()
            if redis:
                await self._cleanup_redis_connection(redis)
        self.redis_connections.clear()

        # Clean up database connections
        for db_ref in self.db_connections:
            db = db_ref()
            if db:
                await self._cleanup_db_connection(db)
        self.db_connections.clear()

        # Clean up temp files
        for filepath in self.temp_files:
            self._cleanup_temp_file(filepath)
        self.temp_files.clear()

        # Cancel active tasks
        for task in self.active_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self.active_tasks.clear()

        logger.info("Resource cleanup completed")

    async def _cleanup_websocket(self, ws):
        """Clean up a WebSocket connection."""
        try:
            if hasattr(ws, "close"):
                await ws.close()
                logger.debug(f"Closed WebSocket: {ws}")
            elif hasattr(ws, "disconnect"):
                await ws.disconnect()
                logger.debug(f"Disconnected WebSocket: {ws}")
        except Exception as e:
            logger.warning(f"Error closing WebSocket: {e}")

    async def _cleanup_rabbitmq_channel(self, channel):
        """Clean up a RabbitMQ channel."""
        try:
            if hasattr(channel, "close"):
                if asyncio.iscoroutinefunction(channel.close):
                    await channel.close()
                else:
                    channel.close()
                logger.debug(f"Closed RabbitMQ channel: {channel}")
        except Exception as e:
            logger.warning(f"Error closing RabbitMQ channel: {e}")

    async def _cleanup_rabbitmq_connection(self, connection):
        """Clean up a RabbitMQ connection."""
        try:
            if hasattr(connection, "close"):
                if asyncio.iscoroutinefunction(connection.close):
                    await connection.close()
                else:
                    connection.close()
                logger.debug(f"Closed RabbitMQ connection: {connection}")
        except Exception as e:
            logger.warning(f"Error closing RabbitMQ connection: {e}")

    async def _cleanup_redis_connection(self, connection):
        """Clean up a Redis connection."""
        try:
            if hasattr(connection, "close"):
                await connection.close()
                logger.debug(f"Closed Redis connection: {connection}")
            elif hasattr(connection, "disconnect"):
                connection.disconnect()
                logger.debug(f"Disconnected Redis: {connection}")
        except Exception as e:
            logger.warning(f"Error closing Redis connection: {e}")

    async def _cleanup_db_connection(self, connection):
        """Clean up a database connection."""
        try:
            if hasattr(connection, "close"):
                if asyncio.iscoroutinefunction(connection.close):
                    await connection.close()
                else:
                    connection.close()
                logger.debug(f"Closed DB connection: {connection}")
        except Exception as e:
            logger.warning(f"Error closing DB connection: {e}")

    def _cleanup_temp_file(self, filepath):
        """Clean up a temporary file."""
        import os

        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                logger.debug(f"Removed temp file: {filepath}")
        except Exception as e:
            logger.warning(f"Error removing temp file {filepath}: {e}")


# Global tracker instance
_resource_tracker = ResourceTracker()


# ============================================================================
# Autouse Cleanup Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
async def auto_cleanup_resources():
    """
    Automatically clean up all resources after each test.
    This fixture runs for every test automatically.
    """
    # Setup: Nothing to do
    yield

    # Teardown: Clean up everything
    await _resource_tracker.cleanup_all()


@pytest.fixture(autouse=True)
def monitor_websockets(monkeypatch):
    """
    Automatically monitor and track WebSocket connections.
    Patches WebSocket creation to track all instances.
    """
    original_websocket = None

    try:
        import websockets

        original_websocket = websockets.connect

        async def tracked_connect(*args, **kwargs):
            ws = await original_websocket(*args, **kwargs)
            _resource_tracker.track_websocket(ws)
            return ws

        monkeypatch.setattr(websockets, "connect", tracked_connect)
    except ImportError:
        pass  # websockets not installed

    try:
        from aiohttp import ClientSession

        original_ws_connect = ClientSession.ws_connect

        async def tracked_ws_connect(self, *args, **kwargs):
            ws = await original_ws_connect(self, *args, **kwargs)
            _resource_tracker.track_websocket(ws)
            return ws

        monkeypatch.setattr(ClientSession, "ws_connect", tracked_ws_connect)
    except ImportError:
        pass  # aiohttp not installed

    yield


@pytest.fixture(autouse=True)
def monitor_rabbitmq(monkeypatch):
    """
    Automatically monitor and track RabbitMQ connections and channels.
    """
    try:
        import pika

        # Track synchronous connections
        original_blocking = pika.BlockingConnection

        def tracked_blocking_connection(*args, **kwargs):
            conn = original_blocking(*args, **kwargs)
            _resource_tracker.track_rabbitmq_connection(conn)

            # Also track channels created from this connection
            original_channel = conn.channel

            def tracked_channel():
                ch = original_channel()
                _resource_tracker.track_rabbitmq_channel(ch)
                return ch

            conn.channel = tracked_channel
            return conn

        monkeypatch.setattr(pika, "BlockingConnection", tracked_blocking_connection)
    except ImportError:
        pass  # pika not installed

    try:
        import aio_pika

        # Track async connections
        original_connect = aio_pika.connect

        async def tracked_connect(*args, **kwargs):
            conn = await original_connect(*args, **kwargs)
            _resource_tracker.track_rabbitmq_connection(conn)

            # Track channels
            original_channel = conn.channel

            async def tracked_channel():
                ch = await original_channel()
                _resource_tracker.track_rabbitmq_channel(ch)
                return ch

            conn.channel = tracked_channel
            return conn

        monkeypatch.setattr(aio_pika, "connect", tracked_connect)
    except ImportError:
        pass  # aio_pika not installed

    yield


@pytest.fixture(autouse=True)
def monitor_redis(monkeypatch):
    """
    Automatically monitor and track Redis connections.
    """
    try:
        import redis

        original_redis = redis.Redis

        def tracked_redis(*args, **kwargs):
            r = original_redis(*args, **kwargs)
            _resource_tracker.track_redis_connection(r)
            return r

        monkeypatch.setattr(redis, "Redis", tracked_redis)
    except ImportError:
        pass  # redis not installed

    try:
        import aioredis

        original_create = aioredis.create_redis_pool

        async def tracked_create(*args, **kwargs):
            pool = await original_create(*args, **kwargs)
            _resource_tracker.track_redis_connection(pool)
            return pool

        monkeypatch.setattr(aioredis, "create_redis_pool", tracked_create)
    except ImportError:
        pass  # aioredis not installed

    yield


@pytest.fixture(autouse=True)
def monitor_asyncio_tasks():
    """
    Monitor and clean up asyncio tasks.
    """
    import asyncio

    original_create_task = asyncio.create_task

    def tracked_create_task(coro, **kwargs):
        task = original_create_task(coro, **kwargs)
        _resource_tracker.track_task(task)
        return task

    asyncio.create_task = tracked_create_task

    yield

    # Restore original
    asyncio.create_task = original_create_task


# ============================================================================
# Manual Cleanup Helpers
# ============================================================================


async def cleanup_websocket_manager():
    """Manually clean up WebSocket manager if needed."""
    try:
        from fxml4.api.websocket_manager import WebSocketManager

        manager = WebSocketManager()
        await manager.disconnect_all()
        logger.info("Cleaned up WebSocket manager")
    except ImportError:
        pass


async def cleanup_rabbitmq_client():
    """Manually clean up RabbitMQ client if needed."""
    try:
        from fxml4.brokers.rabbitmq_client import RabbitMQClient

        client = RabbitMQClient()
        await client.close_all_channels()
        await client.close_connection()
        logger.info("Cleaned up RabbitMQ client")
    except ImportError:
        pass


async def cleanup_redis_client():
    """Manually clean up Redis client if needed."""
    try:
        from fxml4.cache.redis_client import RedisClient

        client = RedisClient()
        await client.close_all_connections()
        logger.info("Cleaned up Redis client")
    except ImportError:
        pass


# ============================================================================
# Context Managers for Explicit Resource Management
# ============================================================================


@asynccontextmanager
async def managed_websocket(url: str, **kwargs):
    """Context manager for WebSocket connections with automatic cleanup."""
    import websockets

    ws = await websockets.connect(url, **kwargs)
    _resource_tracker.track_websocket(ws)

    try:
        yield ws
    finally:
        await ws.close()
        logger.debug(f"Closed managed WebSocket: {url}")


@asynccontextmanager
async def managed_rabbitmq_connection(url: str, **kwargs):
    """Context manager for RabbitMQ connections with automatic cleanup."""
    import aio_pika

    connection = await aio_pika.connect(url, **kwargs)
    _resource_tracker.track_rabbitmq_connection(connection)

    try:
        yield connection
    finally:
        await connection.close()
        logger.debug(f"Closed managed RabbitMQ connection: {url}")


@asynccontextmanager
async def managed_rabbitmq_channel(connection):
    """Context manager for RabbitMQ channels with automatic cleanup."""
    channel = await connection.channel()
    _resource_tracker.track_rabbitmq_channel(channel)

    try:
        yield channel
    finally:
        await channel.close()
        logger.debug("Closed managed RabbitMQ channel")


# ============================================================================
# Test Utilities
# ============================================================================


def get_resource_stats() -> Dict[str, int]:
    """Get current resource tracking statistics."""
    return {
        "websockets": len(
            [ws for ws in _resource_tracker.websockets if ws() is not None]
        ),
        "rabbitmq_channels": len(
            [ch for ch in _resource_tracker.rabbitmq_channels if ch() is not None]
        ),
        "rabbitmq_connections": len(
            [
                conn
                for conn in _resource_tracker.rabbitmq_connections
                if conn() is not None
            ]
        ),
        "redis_connections": len(
            [r for r in _resource_tracker.redis_connections if r() is not None]
        ),
        "db_connections": len(
            [db for db in _resource_tracker.db_connections if db() is not None]
        ),
        "temp_files": len(_resource_tracker.temp_files),
        "active_tasks": len(
            [t for t in _resource_tracker.active_tasks if not t.done()]
        ),
    }


def assert_no_resource_leaks():
    """Assert that no resources are leaked."""
    stats = get_resource_stats()

    for resource_type, count in stats.items():
        assert (
            count == 0
        ), f"Resource leak detected: {count} {resource_type} still active"


# ============================================================================
# Fixture Registration
# ============================================================================


def register_cleanup_fixtures():
    """
    Register all cleanup fixtures globally.
    Call this from conftest.py to enable automatic cleanup.
    """
    logger.info("Cleanup fixtures registered - automatic resource cleanup enabled")
    return {
        "auto_cleanup_resources": auto_cleanup_resources,
        "monitor_websockets": monitor_websockets,
        "monitor_rabbitmq": monitor_rabbitmq,
        "monitor_redis": monitor_redis,
        "monitor_asyncio_tasks": monitor_asyncio_tasks,
    }


# ============================================================================
# Testing the Cleanup Fixtures
# ============================================================================


@pytest.mark.asyncio
async def test_cleanup_fixtures_websocket():
    """Test that WebSocket cleanup works."""
    # Mock WebSocket
    ws = AsyncMock()
    ws.close = AsyncMock()

    # Track it
    _resource_tracker.track_websocket(ws)

    # Verify it's tracked
    assert get_resource_stats()["websockets"] == 1

    # Clean up
    await _resource_tracker.cleanup_all()

    # Verify it's cleaned
    ws.close.assert_called_once()
    assert get_resource_stats()["websockets"] == 0


@pytest.mark.asyncio
async def test_cleanup_fixtures_rabbitmq():
    """Test that RabbitMQ cleanup works."""
    # Mock RabbitMQ channel
    channel = AsyncMock()
    channel.close = AsyncMock()

    # Mock RabbitMQ connection
    connection = AsyncMock()
    connection.close = AsyncMock()

    # Track them
    _resource_tracker.track_rabbitmq_channel(channel)
    _resource_tracker.track_rabbitmq_connection(connection)

    # Verify they're tracked
    stats = get_resource_stats()
    assert stats["rabbitmq_channels"] == 1
    assert stats["rabbitmq_connections"] == 1

    # Clean up
    await _resource_tracker.cleanup_all()

    # Verify they're cleaned
    channel.close.assert_called_once()
    connection.close.assert_called_once()

    stats = get_resource_stats()
    assert stats["rabbitmq_channels"] == 0
    assert stats["rabbitmq_connections"] == 0
