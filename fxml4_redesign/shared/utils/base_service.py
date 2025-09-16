"""Base service class for all FXML4 microservices."""

import asyncio
import json
import logging
import os
import signal
import sys
import traceback
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Callable, Dict, Optional

import aio_pika
import asyncpg
import redis.asyncio as redis


class BaseService(ABC):
    """Base class for all FXML4 microservices."""

    def __init__(self, service_name: str, config: Dict[str, Any]):
        """Initialize base service.

        Args:
            service_name: Name of the service
            config: Service configuration
        """
        self.service_name = service_name
        self.config = config
        self.logger = self._setup_logging()

        # Connections
        self.db_pool: Optional[asyncpg.Pool] = None
        self.rabbitmq_connection: Optional[aio_pika.Connection] = None
        self.rabbitmq_channel: Optional[aio_pika.Channel] = None
        self.redis_client: Optional[redis.Redis] = None

        # Control
        self.running = False
        self.tasks: list[asyncio.Task] = []

    def _setup_logging(self) -> logging.Logger:
        """Set up service logging."""
        logger = logging.getLogger(self.service_name)
        logger.setLevel(logging.INFO)

        # Console handler
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            f"%(asctime)s - {self.service_name} - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        return logger

    async def connect_db(self):
        """Connect to TimescaleDB."""
        try:
            self.db_pool = await asyncpg.create_pool(
                host=self.config.get("db_host", "localhost"),
                port=self.config.get("db_port", 5432),
                user=self.config.get("db_user", "postgres"),
                password=self.config.get("db_password", "postgres"),
                database=self.config.get("db_name", "fxml4_trading"),
                min_size=5,
                max_size=20,
                command_timeout=60,
                pool_recycle=3600,
            )
            self.logger.info("Connected to TimescaleDB")
        except Exception as e:
            self.logger.error(f"Failed to connect to database: {e}")
            raise

    async def connect_rabbitmq(self):
        """Connect to RabbitMQ."""
        try:
            self.rabbitmq_connection = await aio_pika.connect_robust(
                f"amqp://{self.config.get('rabbitmq_user', 'admin')}:"
                f"{self.config.get('rabbitmq_pass', 'admin123')}@"
                f"{self.config.get('rabbitmq_host', 'localhost')}/"
            )
            self.rabbitmq_channel = await self.rabbitmq_connection.channel()
            await self.rabbitmq_channel.set_qos(prefetch_count=10)
            self.logger.info("Connected to RabbitMQ")
        except Exception as e:
            self.logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    async def connect_redis(self):
        """Connect to Redis."""
        try:
            self.redis_client = await redis.from_url(
                f"redis://{self.config.get('redis_host', 'localhost')}:"
                f"{self.config.get('redis_port', 6379)}",
                decode_responses=True,
            )
            await self.redis_client.ping()
            self.logger.info("Connected to Redis")
        except Exception as e:
            self.logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def publish_message(
        self, exchange: str, routing_key: str, message: Dict[str, Any]
    ):
        """Publish message to RabbitMQ.

        Args:
            exchange: Exchange name
            routing_key: Routing key
            message: Message to publish
        """
        if not self.rabbitmq_channel:
            raise RuntimeError("RabbitMQ channel not initialized")

        # Add metadata
        message["timestamp"] = datetime.utcnow().isoformat()
        message["service"] = self.service_name

        # Get exchange
        exchange_obj = await self.rabbitmq_channel.get_exchange(exchange)

        # Publish
        await exchange_obj.publish(
            aio_pika.Message(
                body=json.dumps(message).encode(),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=routing_key,
        )

    async def consume_messages(self, queue_name: str, callback: Callable):
        """Consume messages from RabbitMQ queue.

        Args:
            queue_name: Queue to consume from
            callback: Async callback function to process messages
        """
        if not self.rabbitmq_channel:
            raise RuntimeError("RabbitMQ channel not initialized")

        # Get queue
        queue = await self.rabbitmq_channel.get_queue(queue_name)

        # Start consuming
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    try:
                        # Parse message
                        data = json.loads(message.body.decode())

                        # Process with callback
                        await callback(data)

                    except Exception as e:
                        self.logger.error(f"Error processing message: {e}")
                        await self.log_error(
                            e, {"queue": queue_name, "message": str(message.body)}
                        )

    async def cache_get(self, key: str) -> Optional[str]:
        """Get value from Redis cache."""
        if not self.redis_client:
            return None
        return await self.redis_client.get(key)

    async def cache_set(self, key: str, value: str, ttl: int = 3600):
        """Set value in Redis cache with TTL."""
        if not self.redis_client:
            return
        await self.redis_client.setex(key, ttl, value)

    async def cache_json_get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get JSON value from Redis cache."""
        value = await self.cache_get(key)
        if value:
            return json.loads(value)
        return None

    async def cache_json_set(self, key: str, value: Dict[str, Any], ttl: int = 3600):
        """Set JSON value in Redis cache."""
        await self.cache_set(key, json.dumps(value), ttl)

    @asynccontextmanager
    async def db_transaction(self):
        """Database transaction context manager."""
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                yield conn

    async def log_event(
        self, event_type: str, message: str, details: Optional[Dict] = None
    ):
        """Log system event to database."""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO trading.system_events
                (event_time, service_name, event_type, severity, message, details)
                VALUES ($1, $2, $3, $4, $5, $6)
            """,
                datetime.utcnow(),
                self.service_name,
                event_type,
                "info",
                message,
                json.dumps(details) if details else None,
            )

    async def log_error(self, error: Exception, context: Optional[Dict] = None):
        """Log error to database."""
        details = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "context": context,
        }

        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO trading.system_events
                (event_time, service_name, event_type, severity, message, details)
                VALUES ($1, $2, $3, $4, $5, $6)
            """,
                datetime.utcnow(),
                self.service_name,
                "error",
                "error",
                str(error),
                json.dumps(details),
            )

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        health = {
            "service": self.service_name,
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {},
        }

        # Check database
        try:
            async with self.db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            health["checks"]["database"] = "ok"
        except Exception as e:
            health["checks"]["database"] = f"error: {e}"
            health["status"] = "unhealthy"

        # Check RabbitMQ
        try:
            if self.rabbitmq_connection and not self.rabbitmq_connection.is_closed:
                health["checks"]["rabbitmq"] = "ok"
            else:
                health["checks"]["rabbitmq"] = "disconnected"
                health["status"] = "unhealthy"
        except Exception as e:
            health["checks"]["rabbitmq"] = f"error: {e}"
            health["status"] = "unhealthy"

        # Check Redis
        try:
            await self.redis_client.ping()
            health["checks"]["redis"] = "ok"
        except Exception as e:
            health["checks"]["redis"] = f"error: {e}"
            health["status"] = "unhealthy"

        return health

    async def setup(self):
        """Set up service connections and resources."""
        self.logger.info(f"Setting up {self.service_name}")

        # Connect to services
        await self.connect_db()
        await self.connect_rabbitmq()
        await self.connect_redis()

        # Service-specific setup
        await self.service_setup()

        # Log startup event
        await self.log_event("startup", f"{self.service_name} started successfully")

    async def teardown(self):
        """Clean up service resources."""
        self.logger.info(f"Shutting down {self.service_name}")

        # Service-specific teardown
        await self.service_teardown()

        # Cancel all tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()

        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)

        # Close connections
        if self.rabbitmq_connection:
            await self.rabbitmq_connection.close()

        if self.redis_client:
            await self.redis_client.close()

        if self.db_pool:
            await self.db_pool.close()

        # Log shutdown event
        try:
            await self.log_event("shutdown", f"{self.service_name} stopped")
        except:
            pass

    def add_task(self, coro):
        """Add a task to be managed by the service."""
        task = asyncio.create_task(coro)
        self.tasks.append(task)
        return task

    async def run(self):
        """Run the service."""
        # Set up signal handlers
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda s, f: asyncio.create_task(self.shutdown()))

        try:
            # Setup
            await self.setup()

            # Start service
            self.running = True
            self.logger.info(f"{self.service_name} is running")

            # Run service
            await self.service_run()

        except Exception as e:
            self.logger.error(f"Service error: {e}")
            await self.log_error(e)
        finally:
            await self.teardown()

    async def shutdown(self):
        """Graceful shutdown."""
        self.logger.info("Shutdown signal received")
        self.running = False

    @abstractmethod
    async def service_setup(self):
        """Service-specific setup. Override in subclass."""
        pass

    @abstractmethod
    async def service_teardown(self):
        """Service-specific teardown. Override in subclass."""
        pass

    @abstractmethod
    async def service_run(self):
        """Service main run loop. Override in subclass."""
        pass


class ServiceConfig:
    """Helper class to load service configuration."""

    @staticmethod
    def from_env() -> Dict[str, Any]:
        """Load configuration from environment variables."""
        return {
            # Database
            "db_host": os.getenv("DB_HOST", "localhost"),
            "db_port": int(os.getenv("DB_PORT", 5432)),
            "db_user": os.getenv("DB_USER", "postgres"),
            "db_password": os.getenv("DB_PASSWORD", "postgres"),
            "db_name": os.getenv("DB_NAME", "fxml4_trading"),
            # RabbitMQ
            "rabbitmq_host": os.getenv("RABBITMQ_HOST", "localhost"),
            "rabbitmq_user": os.getenv("RABBITMQ_USER", "admin"),
            "rabbitmq_pass": os.getenv("RABBITMQ_PASS", "admin123"),
            # Redis
            "redis_host": os.getenv("REDIS_HOST", "localhost"),
            "redis_port": int(os.getenv("REDIS_PORT", 6379)),
            # IB Gateway
            "ib_gateway_host": os.getenv("IB_GATEWAY_HOST", "127.0.0.1"),
            "ib_gateway_port": int(os.getenv("IB_GATEWAY_PORT", 7497)),
            "ib_client_id": int(os.getenv("IB_CLIENT_ID", 1)),
        }


if __name__ == "__main__":
    # Example usage
    class ExampleService(BaseService):
        async def service_setup(self):
            self.logger.info("Example service setup")

        async def service_teardown(self):
            self.logger.info("Example service teardown")

        async def service_run(self):
            while self.running:
                health = await self.health_check()
                self.logger.info(f"Health: {health}")
                await asyncio.sleep(10)

    # Run example
    config = ServiceConfig.from_env()
    service = ExampleService("example-service", config)
    asyncio.run(service.run())
