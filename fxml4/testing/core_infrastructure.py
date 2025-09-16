"""Core test infrastructure components for advanced fixture patterns."""

import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional
from unittest.mock import Mock

logger = logging.getLogger(__name__)


class DatabaseTestManager:
    """Manages isolated database instances for testing."""

    def __init__(self):
        self.databases = {}
        self._connection_counter = 0

    def create_isolated_database(self) -> Mock:
        """Create an isolated database instance for testing."""
        self._connection_counter += 1
        connection_id = f"test_conn_{self._connection_counter}"
        schema_name = f"test_schema_{uuid.uuid4().hex[:8]}"

        db_instance = Mock()
        db_instance.connection_id = connection_id
        db_instance.schema_name = schema_name

        self.databases[connection_id] = db_instance
        logger.info(f"Created isolated database: {connection_id}")

        return db_instance

    def cleanup_databases(self):
        """Clean up all test databases."""
        for conn_id, db in self.databases.items():
            logger.info(f"Cleaning up database: {conn_id}")
            # Mock cleanup
        self.databases.clear()


class AsyncFixtureManager:
    """Manages async fixture lifecycle and cleanup."""

    def __init__(self):
        self.async_cleanup_queue = []
        self.active_resources = {}

    async def create_async_resource(self, factory_func):
        """Create an async resource using the provided factory."""
        resource = await factory_func()
        resource_id = str(uuid.uuid4())
        self.active_resources[resource_id] = resource
        return resource

    def register_async_cleanup(self, cleanup_coro):
        """Register an async cleanup coroutine."""
        self.async_cleanup_queue.append(cleanup_coro)

    async def cleanup_all(self):
        """Clean up all async resources."""
        for cleanup_coro in reversed(self.async_cleanup_queue):
            try:
                await cleanup_coro
            except Exception as e:
                logger.warning(f"Async cleanup failed: {e}")
        self.async_cleanup_queue.clear()
        self.active_resources.clear()


class ContextualFixture:
    """Provides context-aware fixtures that adapt to test environment."""

    def __init__(self):
        self.contexts = {
            "performance": {
                "database": {
                    "pool_size": 10,
                    "enable_metrics": True,
                    "connection_timeout": 30,
                }
            },
            "unit": {
                "database": {
                    "pool_size": 1,
                    "enable_metrics": False,
                    "connection_timeout": 5,
                }
            },
            "integration": {
                "database": {
                    "pool_size": 5,
                    "enable_metrics": True,
                    "connection_timeout": 15,
                }
            },
        }

    def get_database(self, context: str = "unit"):
        """Get database fixture configured for the specified context."""
        config = self.contexts.get(context, self.contexts["unit"])

        db_mock = Mock()
        db_mock.config = config["database"]

        return db_mock
