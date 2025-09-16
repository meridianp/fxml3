"""Unit tests for BaseService class."""

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, call, patch

import aio_pika
import pytest
from shared.utils.base_service import BaseService, ServiceConfig


class TestBaseService:
    """Test BaseService functionality."""

    @pytest.fixture
    def test_service_class(self):
        """Create a test service class."""

        class TestService(BaseService):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.setup_called = False
                self.teardown_called = False
                self.run_iterations = 0

            async def service_setup(self):
                self.setup_called = True

            async def service_teardown(self):
                self.teardown_called = True

            async def service_run(self):
                while self.running and self.run_iterations < 3:
                    self.run_iterations += 1
                    await asyncio.sleep(0.01)
                self.running = False

        return TestService

    def test_initialization(self, test_service_class, test_config):
        """Test service initialization."""
        service = test_service_class("test-service", test_config)

        assert service.service_name == "test-service"
        assert service.config == test_config
        assert service.db_pool is None
        assert service.rabbitmq_connection is None
        assert service.rabbitmq_channel is None
        assert service.redis_client is None
        assert service.running is False
        assert service.tasks == []

    def test_logging_setup(self, test_service_class, test_config):
        """Test logging is properly configured."""
        service = test_service_class("test-service", test_config)

        assert service.logger is not None
        assert service.logger.name == "test-service"

    @pytest.mark.asyncio
    async def test_connect_db_success(
        self, test_service_class, test_config, mock_db_pool
    ):
        """Test successful database connection."""
        service = test_service_class("test-service", test_config)

        with patch("asyncpg.create_pool", return_value=mock_db_pool):
            await service.connect_db()

        assert service.db_pool is not None

    @pytest.mark.asyncio
    async def test_connect_db_failure(self, test_service_class, test_config):
        """Test database connection failure."""
        service = test_service_class("test-service", test_config)

        with patch("asyncpg.create_pool", side_effect=Exception("Connection failed")):
            with pytest.raises(Exception) as exc_info:
                await service.connect_db()

        assert "Connection failed" in str(exc_info.value)
        assert service.db_pool is None

    @pytest.mark.asyncio
    async def test_connect_rabbitmq_success(self, test_service_class, test_config):
        """Test successful RabbitMQ connection."""
        service = test_service_class("test-service", test_config)

        mock_connection = AsyncMock()
        mock_channel = AsyncMock()
        mock_connection.channel.return_value = mock_channel

        with patch("aio_pika.connect_robust", return_value=mock_connection):
            await service.connect_rabbitmq()

        assert service.rabbitmq_connection is not None
        assert service.rabbitmq_channel is not None
        mock_channel.set_qos.assert_called_once_with(prefetch_count=10)

    @pytest.mark.asyncio
    async def test_connect_redis_success(self, test_service_class, test_config):
        """Test successful Redis connection."""
        service = test_service_class("test-service", test_config)

        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True

        with patch("redis.asyncio.from_url", return_value=mock_redis):
            await service.connect_redis()

        assert service.redis_client is not None
        mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_message(
        self, test_service_class, test_config, mock_rabbitmq_connection
    ):
        """Test publishing message to RabbitMQ."""
        service = test_service_class("test-service", test_config)
        service.rabbitmq_connection, service.rabbitmq_channel = mock_rabbitmq_connection

        # Mock exchange
        mock_exchange = AsyncMock()
        service.rabbitmq_channel.get_exchange.return_value = mock_exchange

        # Publish message
        test_message = {"data": "test", "value": 123}
        await service.publish_message("test.exchange", "test.key", test_message)

        # Verify
        service.rabbitmq_channel.get_exchange.assert_called_once_with("test.exchange")
        mock_exchange.publish.assert_called_once()

        # Check message content
        call_args = mock_exchange.publish.call_args[0][0]
        body = json.loads(call_args.body.decode())
        assert body["data"] == "test"
        assert body["value"] == 123
        assert body["service"] == "test-service"
        assert "timestamp" in body

    @pytest.mark.asyncio
    async def test_publish_message_no_channel(self, test_service_class, test_config):
        """Test publishing message without channel raises error."""
        service = test_service_class("test-service", test_config)

        with pytest.raises(RuntimeError) as exc_info:
            await service.publish_message("test.exchange", "test.key", {})

        assert "RabbitMQ channel not initialized" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_consume_messages(
        self, test_service_class, test_config, mock_rabbitmq_connection
    ):
        """Test consuming messages from RabbitMQ."""
        service = test_service_class("test-service", test_config)
        service.rabbitmq_connection, service.rabbitmq_channel = mock_rabbitmq_connection

        # Mock queue and iterator
        mock_queue = AsyncMock()
        mock_iterator = AsyncMock()
        mock_queue.iterator.return_value.__aenter__.return_value = mock_iterator

        # Mock messages
        messages_processed = []

        async def mock_callback(data):
            messages_processed.append(data)

        # Create mock message
        mock_message = MagicMock()
        mock_message.body = json.dumps({"test": "data"}).encode()
        mock_message.process.return_value.__aenter__.return_value = None
        mock_message.process.return_value.__aexit__.return_value = None

        # Set up iterator to return one message then stop
        mock_iterator.__aiter__.return_value = iter([mock_message])

        service.rabbitmq_channel.get_queue.return_value = mock_queue

        # Start consuming (will process one message)
        task = asyncio.create_task(
            service.consume_messages("test.queue", mock_callback)
        )

        # Give it time to process
        await asyncio.sleep(0.1)
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify
        assert len(messages_processed) == 1
        assert messages_processed[0] == {"test": "data"}

    @pytest.mark.asyncio
    async def test_cache_operations(
        self, test_service_class, test_config, mock_redis_client
    ):
        """Test Redis cache operations."""
        service = test_service_class("test-service", test_config)
        service.redis_client = mock_redis_client

        # Test set/get
        await service.cache_set("test_key", "test_value", ttl=60)
        value = await service.cache_get("test_key")
        assert value == "test_value"

        # Test JSON set/get
        test_data = {"key": "value", "number": 42}
        await service.cache_json_set("json_key", test_data, ttl=60)
        retrieved = await service.cache_json_get("json_key")
        assert retrieved == test_data

        # Test missing key
        missing = await service.cache_get("missing_key")
        assert missing is None

        missing_json = await service.cache_json_get("missing_key")
        assert missing_json is None

    @pytest.mark.asyncio
    async def test_db_transaction_context(
        self, test_service_class, test_config, mock_db_pool
    ):
        """Test database transaction context manager."""
        service = test_service_class("test-service", test_config)
        service.db_pool = mock_db_pool

        # Use transaction
        async with service.db_transaction() as conn:
            assert conn is not None

        # Verify acquire was called
        mock_db_pool.acquire.assert_called()

    @pytest.mark.asyncio
    async def test_log_event(self, test_service_class, test_config, mock_db_pool):
        """Test logging events to database."""
        service = test_service_class("test-service", test_config)
        service.db_pool = mock_db_pool

        # Log event
        await service.log_event("test_event", "Test message", {"extra": "data"})

        # Verify insert was called
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.execute.assert_called_once()

        # Check SQL and parameters
        call_args = conn.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1:]

        assert "INSERT INTO trading.system_events" in sql
        assert params[1] == "test-service"
        assert params[2] == "test_event"
        assert params[3] == "info"
        assert params[4] == "Test message"
        assert json.loads(params[5]) == {"extra": "data"}

    @pytest.mark.asyncio
    async def test_log_error(self, test_service_class, test_config, mock_db_pool):
        """Test logging errors to database."""
        service = test_service_class("test-service", test_config)
        service.db_pool = mock_db_pool

        # Create and log error
        try:
            raise ValueError("Test error")
        except ValueError as e:
            await service.log_error(e, {"context": "test"})

        # Verify insert was called
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.execute.assert_called_once()

        # Check parameters
        call_args = conn.execute.call_args
        params = call_args[0][1:]

        assert params[1] == "test-service"
        assert params[2] == "error"
        assert params[3] == "error"
        assert params[4] == "Test error"

        details = json.loads(params[5])
        assert details["error_type"] == "ValueError"
        assert details["error_message"] == "Test error"
        assert details["context"] == {"context": "test"}
        assert "traceback" in details

    @pytest.mark.asyncio
    async def test_health_check_all_healthy(
        self,
        test_service_class,
        test_config,
        mock_db_pool,
        mock_rabbitmq_connection,
        mock_redis_client,
    ):
        """Test health check when all services are healthy."""
        service = test_service_class("test-service", test_config)
        service.db_pool = mock_db_pool
        service.rabbitmq_connection, service.rabbitmq_channel = mock_rabbitmq_connection
        service.redis_client = mock_redis_client

        # Mock healthy responses
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetchval.return_value = (
            1
        )
        service.rabbitmq_connection.is_closed = False

        health = await service.health_check()

        assert health["service"] == "test-service"
        assert health["status"] == "healthy"
        assert health["checks"]["database"] == "ok"
        assert health["checks"]["rabbitmq"] == "ok"
        assert health["checks"]["redis"] == "ok"
        assert "timestamp" in health

    @pytest.mark.asyncio
    async def test_health_check_db_unhealthy(
        self,
        test_service_class,
        test_config,
        mock_db_pool,
        mock_rabbitmq_connection,
        mock_redis_client,
    ):
        """Test health check with unhealthy database."""
        service = test_service_class("test-service", test_config)
        service.db_pool = mock_db_pool
        service.rabbitmq_connection, service.rabbitmq_channel = mock_rabbitmq_connection
        service.redis_client = mock_redis_client

        # Mock database error
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetchval.side_effect = Exception(
            "DB Error"
        )
        service.rabbitmq_connection.is_closed = False

        health = await service.health_check()

        assert health["status"] == "unhealthy"
        assert "error: DB Error" in health["checks"]["database"]
        assert health["checks"]["rabbitmq"] == "ok"
        assert health["checks"]["redis"] == "ok"

    @pytest.mark.asyncio
    async def test_setup_and_teardown(self, test_service_class, test_config):
        """Test service setup and teardown."""
        service = test_service_class("test-service", test_config)

        # Mock all connections
        with patch.multiple(
            service,
            connect_db=AsyncMock(),
            connect_rabbitmq=AsyncMock(),
            connect_redis=AsyncMock(),
            log_event=AsyncMock(),
        ):

            # Setup
            await service.setup()

            assert service.setup_called
            service.connect_db.assert_called_once()
            service.connect_rabbitmq.assert_called_once()
            service.connect_redis.assert_called_once()
            service.log_event.assert_called_with(
                "startup", "test-service started successfully"
            )

            # Add some tasks
            task1 = service.add_task(asyncio.sleep(10))
            task2 = service.add_task(asyncio.sleep(10))

            assert len(service.tasks) == 2

            # Teardown
            service.rabbitmq_connection = AsyncMock()
            service.redis_client = AsyncMock()
            service.db_pool = AsyncMock()

            await service.teardown()

            assert service.teardown_called
            assert task1.cancelled()
            assert task2.cancelled()

    @pytest.mark.asyncio
    async def test_run_complete_lifecycle(self, test_service_class, test_config):
        """Test complete service lifecycle."""
        service = test_service_class("test-service", test_config)

        # Mock all external connections
        with patch.multiple(
            service,
            connect_db=AsyncMock(),
            connect_rabbitmq=AsyncMock(),
            connect_redis=AsyncMock(),
            log_event=AsyncMock(),
            log_error=AsyncMock(),
        ):

            # Mock cleanup methods
            service.db_pool = AsyncMock()
            service.rabbitmq_connection = AsyncMock()
            service.redis_client = AsyncMock()

            # Run service
            await service.run()

            # Verify lifecycle
            assert service.setup_called
            assert service.run_iterations >= 3
            assert service.teardown_called
            assert not service.running

    @pytest.mark.asyncio
    async def test_run_with_error(self, test_service_class, test_config):
        """Test service run with error in service_run."""

        class ErrorService(test_service_class):
            async def service_run(self):
                raise RuntimeError("Service error")

        service = ErrorService("error-service", test_config)

        with patch.multiple(
            service,
            connect_db=AsyncMock(),
            connect_rabbitmq=AsyncMock(),
            connect_redis=AsyncMock(),
            log_event=AsyncMock(),
            log_error=AsyncMock(),
        ):

            # Mock cleanup methods
            service.db_pool = AsyncMock()
            service.rabbitmq_connection = AsyncMock()
            service.redis_client = AsyncMock()

            # Run should handle error gracefully
            await service.run()

            # Verify error was logged
            service.log_error.assert_called_once()
            error_arg = service.log_error.call_args[0][0]
            assert isinstance(error_arg, RuntimeError)
            assert str(error_arg) == "Service error"

    @pytest.mark.asyncio
    async def test_shutdown_signal(self, test_service_class, test_config):
        """Test graceful shutdown via signal."""
        service = test_service_class("test-service", test_config)

        assert service.running is False

        # Simulate shutdown
        await service.shutdown()

        assert service.running is False  # Should remain False

        # Set running and test again
        service.running = True
        await service.shutdown()

        assert service.running is False

    def test_service_config_from_env(self):
        """Test loading configuration from environment."""
        import os

        # Set test environment variables
        test_env = {
            "DB_HOST": "test-db-host",
            "DB_PORT": "5433",
            "RABBITMQ_HOST": "test-rabbit",
            "REDIS_PORT": "6380",
        }

        with patch.dict(os.environ, test_env):
            config = ServiceConfig.from_env()

        assert config["db_host"] == "test-db-host"
        assert config["db_port"] == 5433
        assert config["rabbitmq_host"] == "test-rabbit"
        assert config["redis_port"] == 6380

    @pytest.mark.asyncio
    async def test_add_task(self, test_service_class, test_config):
        """Test adding tasks to service."""
        service = test_service_class("test-service", test_config)

        # Add tasks
        async def test_coro():
            await asyncio.sleep(0.01)
            return "done"

        task1 = service.add_task(test_coro())
        task2 = service.add_task(test_coro())

        assert len(service.tasks) == 2
        assert task1 in service.tasks
        assert task2 in service.tasks

        # Wait for completion
        result1 = await task1
        result2 = await task2

        assert result1 == "done"
        assert result2 == "done"


class TestServiceIntegration:
    """Integration tests for BaseService with real async operations."""

    @pytest.mark.asyncio
    async def test_concurrent_operations(
        self,
        test_service_class,
        test_config,
        mock_db_pool,
        mock_rabbitmq_connection,
        mock_redis_client,
    ):
        """Test service handling concurrent operations."""
        service = test_service_class("test-service", test_config)
        service.db_pool = mock_db_pool
        service.rabbitmq_connection, service.rabbitmq_channel = mock_rabbitmq_connection
        service.redis_client = mock_redis_client

        # Create concurrent operations
        operations = []

        for i in range(10):
            operations.extend(
                [
                    service.cache_set(f"key_{i}", f"value_{i}"),
                    service.log_event("test", f"Message {i}"),
                    service.health_check(),
                ]
            )

        # Run all operations concurrently
        results = await asyncio.gather(*operations, return_exceptions=True)

        # Verify no exceptions
        for result in results:
            assert not isinstance(result, Exception)

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_message_throughput(
        self,
        test_service_class,
        test_config,
        mock_rabbitmq_connection,
        performance_benchmark,
    ):
        """Benchmark message publishing throughput."""
        service = test_service_class("test-service", test_config)
        service.rabbitmq_connection, service.rabbitmq_channel = mock_rabbitmq_connection

        # Mock exchange
        mock_exchange = AsyncMock()
        service.rabbitmq_channel.get_exchange.return_value = mock_exchange

        # Benchmark
        num_messages = 1000
        performance_benchmark.start("message_publish")

        for i in range(num_messages):
            await service.publish_message(
                "test.exchange", f"test.key.{i}", {"index": i, "data": "x" * 100}
            )

        performance_benchmark.stop("message_publish")

        # Verify
        assert mock_exchange.publish.call_count == num_messages

        # Check performance (should handle 1000 messages in < 1 second)
        duration = performance_benchmark.get_duration("message_publish")
        assert (
            duration < 1.0
        ), f"Publishing {num_messages} messages took {duration:.2f}s"
