#!/usr/bin/env python3
"""
REAL ENVIRONMENT TESTING
========================

Tests against actual deployed services - NOT mocked or local instances.
This ensures our CI/CD validates against real production infrastructure.

CRITICAL PREVENTION MEASURES:
- Tests against actual staging/production deployments
- Validates real database connections and external APIs
- Ensures no environment-specific issues reach production
- Confirms all external dependencies work in deployed state

Environments Tested:
1. Staging Environment - Full integration testing
2. Production Environment - Health checks and read-only operations
3. Database Connectivity - Real TimescaleDB instances
4. External APIs - Interactive Brokers, Polygon.io, etc.
5. Message Queues - RabbitMQ in deployed state
6. Cache Systems - Redis clusters
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import aiohttp
import pika
import psycopg2
import pytest
import redis

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class EnvironmentHealth:
    """Health status of environment components"""

    component: str
    status: str  # HEALTHY, DEGRADED, FAILED
    response_time_ms: float
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class RealEnvironmentTester:
    """Test against actual deployed services"""

    def __init__(self, environment: str):
        self.environment = environment.lower()
        self.config = self._get_environment_config()
        self.health_results: List[EnvironmentHealth] = []

    def _get_environment_config(self) -> Dict[str, str]:
        """Get configuration for environment"""
        configs = {
            "staging": {
                "api_url": os.getenv("STAGING_URL", "http://staging-api.fxml4.com"),
                "ui_url": os.getenv("STAGING_UI_URL", "http://staging-app.fxml4.com"),
                "db_url": os.getenv(
                    "STAGING_DB_URL",
                    "postgresql://fxml4:password@staging-db:5432/fxml4",  # pragma: allowlist secret
                ),
                "redis_url": os.getenv(
                    "STAGING_REDIS_URL", "redis://staging-redis:6379"
                ),
                "rabbitmq_url": os.getenv(
                    "STAGING_RABBITMQ_URL",
                    "amqp://guest:guest@staging-rabbitmq:5672/",  # pragma: allowlist secret
                ),
                "test_mode": "full",
            },
            "production": {
                "api_url": os.getenv("PRODUCTION_URL", "https://api.fxml4.com"),
                "ui_url": os.getenv("PRODUCTION_UI_URL", "https://app.fxml4.com"),
                "db_url": os.getenv(
                    "PRODUCTION_DB_URL",
                    "postgresql://fxml4:password@prod-db:5432/fxml4",  # pragma: allowlist secret
                ),
                "redis_url": os.getenv(
                    "PRODUCTION_REDIS_URL", "redis://prod-redis:6379"
                ),
                "rabbitmq_url": os.getenv(
                    "PRODUCTION_RABBITMQ_URL",
                    "amqp://guest:guest@prod-rabbitmq:5672/",  # pragma: allowlist secret
                ),
                "test_mode": "readonly",
            },
            "local": {
                "api_url": os.getenv("API_URL", "http://localhost:8001"),
                "ui_url": os.getenv("UI_URL", "http://localhost:3000"),
                "db_url": os.getenv(
                    "DATABASE_URL",
                    "postgresql://postgres:password@localhost:5433/fxml4",  # pragma: allowlist secret
                ),
                "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379"),
                "rabbitmq_url": os.getenv(
                    "RABBITMQ_URL",
                    "amqp://guest:guest@localhost:5672/",  # pragma: allowlist secret
                ),
                "test_mode": "full",
            },
        }

        return configs.get(self.environment, configs["local"])

    async def test_api_health(self) -> EnvironmentHealth:
        """Test API health against real deployment"""
        start_time = time.time()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.config['api_url']}/health",
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    response_time = (time.time() - start_time) * 1000

                    if response.status != 200:
                        return EnvironmentHealth(
                            component="API Health",
                            status="FAILED",
                            response_time_ms=response_time,
                            error_message=f"HTTP {response.status}",
                        )

                    health_data = await response.json()

                    # Validate health response structure
                    required_fields = ["status", "timestamp", "version"]
                    for field in required_fields:
                        if field not in health_data:
                            return EnvironmentHealth(
                                component="API Health",
                                status="DEGRADED",
                                response_time_ms=response_time,
                                error_message=f"Missing {field} in health response",
                            )

                    status = "HEALTHY" if response_time < 1000 else "DEGRADED"

                    return EnvironmentHealth(
                        component="API Health",
                        status=status,
                        response_time_ms=response_time,
                        metadata={
                            "version": health_data.get("version"),
                            "uptime": health_data.get("uptime"),
                            "environment": health_data.get("environment"),
                        },
                    )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return EnvironmentHealth(
                component="API Health",
                status="FAILED",
                response_time_ms=response_time,
                error_message=str(e),
            )

    async def test_database_connectivity(self) -> EnvironmentHealth:
        """Test real database connectivity"""
        start_time = time.time()

        try:
            # Test PostgreSQL/TimescaleDB connection
            conn = psycopg2.connect(self.config["db_url"])
            cursor = conn.cursor()

            # Test basic query
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]

            # Test TimescaleDB extension
            cursor.execute(
                "SELECT extname FROM pg_extension WHERE extname = 'timescaledb';"
            )
            timescale_result = cursor.fetchone()

            # Test FXML4 specific tables
            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN ('market_data', 'trades', 'signals', 'backtests')
            """
            )
            tables = [row[0] for row in cursor.fetchall()]

            # Test data availability (read-only)
            cursor.execute("SELECT COUNT(*) FROM market_data LIMIT 1;")
            data_count = cursor.fetchone()[0]

            cursor.close()
            conn.close()

            response_time = (time.time() - start_time) * 1000

            # Validate requirements
            issues = []
            if not timescale_result:
                issues.append("TimescaleDB extension not found")

            required_tables = {"market_data", "trades", "signals", "backtests"}
            missing_tables = required_tables - set(tables)
            if missing_tables:
                issues.append(f"Missing tables: {missing_tables}")

            status = "HEALTHY" if not issues and response_time < 2000 else "DEGRADED"
            if issues:
                status = "FAILED"

            return EnvironmentHealth(
                component="Database Connectivity",
                status=status,
                response_time_ms=response_time,
                error_message="; ".join(issues) if issues else None,
                metadata={
                    "postgres_version": version,
                    "timescaledb_enabled": bool(timescale_result),
                    "tables_found": tables,
                    "data_records": data_count,
                },
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return EnvironmentHealth(
                component="Database Connectivity",
                status="FAILED",
                response_time_ms=response_time,
                error_message=str(e),
            )

    async def test_redis_connectivity(self) -> EnvironmentHealth:
        """Test Redis cache connectivity"""
        start_time = time.time()

        try:
            # Parse Redis URL
            redis_client = redis.from_url(self.config["redis_url"])

            # Test basic connectivity
            pong = redis_client.ping()
            if not pong:
                raise Exception("Redis ping failed")

            # Test read/write operations (safe test keys)
            test_key = f"health_check_{int(time.time())}"
            test_value = "environment_test"

            redis_client.set(test_key, test_value, ex=60)  # 60 second expiry
            retrieved_value = redis_client.get(test_key).decode("utf-8")

            if retrieved_value != test_value:
                raise Exception("Redis read/write test failed")

            # Clean up test key
            redis_client.delete(test_key)

            # Get Redis info
            redis_info = redis_client.info()

            redis_client.close()

            response_time = (time.time() - start_time) * 1000
            status = "HEALTHY" if response_time < 500 else "DEGRADED"

            return EnvironmentHealth(
                component="Redis Connectivity",
                status=status,
                response_time_ms=response_time,
                metadata={
                    "redis_version": redis_info.get("redis_version"),
                    "connected_clients": redis_info.get("connected_clients"),
                    "used_memory_human": redis_info.get("used_memory_human"),
                },
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return EnvironmentHealth(
                component="Redis Connectivity",
                status="FAILED",
                response_time_ms=response_time,
                error_message=str(e),
            )

    async def test_rabbitmq_connectivity(self) -> EnvironmentHealth:
        """Test RabbitMQ message queue connectivity"""
        start_time = time.time()

        try:
            # Test RabbitMQ connection
            connection = pika.BlockingConnection(
                pika.URLParameters(self.config["rabbitmq_url"])
            )
            channel = connection.channel()

            # Test queue operations (declare test queue)
            test_queue = f"health_check_{int(time.time())}"
            channel.queue_declare(queue=test_queue, durable=False, auto_delete=True)

            # Test message publish/consume
            test_message = json.dumps(
                {"test": "environment_health", "timestamp": datetime.now().isoformat()}
            )
            channel.basic_publish(
                exchange="", routing_key=test_queue, body=test_message
            )

            # Get message
            method_frame, header_frame, body = channel.basic_get(queue=test_queue)
            if not method_frame:
                raise Exception("Failed to retrieve test message")

            # Acknowledge message
            channel.basic_ack(method_frame.delivery_tag)

            # Clean up test queue
            channel.queue_delete(queue=test_queue)

            connection.close()

            response_time = (time.time() - start_time) * 1000
            status = "HEALTHY" if response_time < 1000 else "DEGRADED"

            return EnvironmentHealth(
                component="RabbitMQ Connectivity",
                status=status,
                response_time_ms=response_time,
                metadata={
                    "connection_successful": True,
                    "publish_consume_test": "passed",
                },
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return EnvironmentHealth(
                component="RabbitMQ Connectivity",
                status="FAILED",
                response_time_ms=response_time,
                error_message=str(e),
            )

    async def test_external_apis(self) -> EnvironmentHealth:
        """Test external API connectivity (brokers, data providers)"""
        start_time = time.time()

        try:
            async with aiohttp.ClientSession() as session:
                # Test our API's external connections endpoint
                async with session.get(
                    f"{self.config['api_url']}/health/external",
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:

                    if response.status != 200:
                        return EnvironmentHealth(
                            component="External APIs",
                            status="FAILED",
                            response_time_ms=(time.time() - start_time) * 1000,
                            error_message=f"External health check endpoint failed: {response.status}",
                        )

                    external_health = await response.json()

                    # Analyze external service health
                    failed_services = []
                    degraded_services = []

                    for service, health in external_health.get("services", {}).items():
                        if health.get("status") == "failed":
                            failed_services.append(service)
                        elif health.get("status") == "degraded":
                            degraded_services.append(service)

                    response_time = (time.time() - start_time) * 1000

                    # Determine overall status
                    if failed_services:
                        status = "FAILED"
                        error_msg = f"Failed services: {failed_services}"
                    elif degraded_services:
                        status = "DEGRADED"
                        error_msg = f"Degraded services: {degraded_services}"
                    else:
                        status = "HEALTHY"
                        error_msg = None

                    return EnvironmentHealth(
                        component="External APIs",
                        status=status,
                        response_time_ms=response_time,
                        error_message=error_msg,
                        metadata={
                            "services_checked": list(
                                external_health.get("services", {}).keys()
                            ),
                            "failed_services": failed_services,
                            "degraded_services": degraded_services,
                        },
                    )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return EnvironmentHealth(
                component="External APIs",
                status="FAILED",
                response_time_ms=response_time,
                error_message=str(e),
            )

    async def test_ui_availability(self) -> EnvironmentHealth:
        """Test UI frontend availability"""
        start_time = time.time()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.config["ui_url"], timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    response_time = (time.time() - start_time) * 1000

                    if response.status != 200:
                        return EnvironmentHealth(
                            component="UI Availability",
                            status="FAILED",
                            response_time_ms=response_time,
                            error_message=f"UI returned HTTP {response.status}",
                        )

                    # Check for basic HTML structure
                    html_content = await response.text()

                    # Basic checks for React app
                    if "<!DOCTYPE html>" not in html_content:
                        return EnvironmentHealth(
                            component="UI Availability",
                            status="DEGRADED",
                            response_time_ms=response_time,
                            error_message="Invalid HTML structure",
                        )

                    # Check for app root element
                    if (
                        'id="root"' not in html_content
                        and 'id="__next"' not in html_content
                    ):
                        return EnvironmentHealth(
                            component="UI Availability",
                            status="DEGRADED",
                            response_time_ms=response_time,
                            error_message="React/Next.js root element not found",
                        )

                    status = "HEALTHY" if response_time < 3000 else "DEGRADED"

                    return EnvironmentHealth(
                        component="UI Availability",
                        status=status,
                        response_time_ms=response_time,
                        metadata={
                            "content_length": len(html_content),
                            "has_html_structure": True,
                        },
                    )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return EnvironmentHealth(
                component="UI Availability",
                status="FAILED",
                response_time_ms=response_time,
                error_message=str(e),
            )

    async def run_full_environment_test(self) -> List[EnvironmentHealth]:
        """Run complete environment health check"""
        logger.info(f"🌍 TESTING REAL ENVIRONMENT: {self.environment.upper()}")
        logger.info(f"API: {self.config['api_url']}")
        logger.info(f"UI: {self.config['ui_url']}")

        # Define test suite based on environment
        if self.config["test_mode"] == "readonly":
            # Production - limited testing
            tests = [
                self.test_api_health(),
                self.test_ui_availability(),
                self.test_external_apis(),
            ]
        else:
            # Staging/Local - full testing
            tests = [
                self.test_api_health(),
                self.test_database_connectivity(),
                self.test_redis_connectivity(),
                self.test_rabbitmq_connectivity(),
                self.test_external_apis(),
                self.test_ui_availability(),
            ]

        # Run all tests
        results = []
        for test_coro in tests:
            try:
                result = await test_coro
                results.append(result)
                self.health_results.append(result)

                # Log result
                status_emoji = {"HEALTHY": "✅", "DEGRADED": "⚠️", "FAILED": "❌"}[
                    result.status
                ]
                logger.info(
                    f"{status_emoji} {result.component}: {result.status} ({result.response_time_ms:.1f}ms)"
                )

                if result.error_message:
                    logger.warning(f"  Error: {result.error_message}")

            except Exception as e:
                logger.error(f"Test failed with exception: {e}")
                results.append(
                    EnvironmentHealth(
                        component="Unknown Test",
                        status="FAILED",
                        response_time_ms=0,
                        error_message=str(e),
                    )
                )

        # Analyze overall health
        failed = [r for r in results if r.status == "FAILED"]
        degraded = [r for r in results if r.status == "DEGRADED"]
        healthy = [r for r in results if r.status == "HEALTHY"]

        total_time = sum(r.response_time_ms for r in results)

        logger.info(f"📊 ENVIRONMENT HEALTH SUMMARY:")
        logger.info(f"  ✅ Healthy: {len(healthy)}")
        logger.info(f"  ⚠️  Degraded: {len(degraded)}")
        logger.info(f"  ❌ Failed: {len(failed)}")
        logger.info(f"  ⏱️  Total Time: {total_time:.1f}ms")

        # Fail if any critical components failed
        if failed:
            failed_components = [r.component for r in failed]
            raise AssertionError(
                f"Environment health check failed - Components: {failed_components}"
            )

        return results


# Pytest integration for CI/CD
@pytest.mark.critical
@pytest.mark.environment
@pytest.mark.slow
async def test_staging_environment_health():
    """Test staging environment health - full integration"""
    tester = RealEnvironmentTester("staging")
    results = await tester.run_full_environment_test()

    # Ensure no critical failures
    failed_results = [r for r in results if r.status == "FAILED"]
    assert (
        not failed_results
    ), f"Staging environment health check failed: {[r.component for r in failed_results]}"


@pytest.mark.critical
@pytest.mark.environment
@pytest.mark.production
async def test_production_environment_health():
    """Test production environment health - read-only checks"""
    tester = RealEnvironmentTester("production")
    results = await tester.run_full_environment_test()

    # Ensure no critical failures
    failed_results = [r for r in results if r.status == "FAILED"]
    assert (
        not failed_results
    ), f"Production environment health check failed: {[r.component for r in failed_results]}"


@pytest.mark.environment
@pytest.mark.integration
async def test_local_environment_health():
    """Test local development environment"""
    tester = RealEnvironmentTester("local")
    results = await tester.run_full_environment_test()

    # Allow some degradation in local environment
    failed_results = [r for r in results if r.status == "FAILED"]
    critical_failures = [
        r
        for r in failed_results
        if r.component in ["API Health", "Database Connectivity"]
    ]

    assert (
        not critical_failures
    ), f"Critical local environment failures: {[r.component for r in critical_failures]}"


if __name__ == "__main__":
    import sys

    # Command line execution
    environment = sys.argv[1] if len(sys.argv) > 1 else "local"

    async def main():
        try:
            tester = RealEnvironmentTester(environment)
            results = await tester.run_full_environment_test()

            print(f"✅ ENVIRONMENT HEALTH CHECK PASSED: {environment.upper()}")
            print(f"Components tested: {len(results)}")

            for result in results:
                status_emoji = {"HEALTHY": "✅", "DEGRADED": "⚠️", "FAILED": "❌"}[
                    result.status
                ]
                print(
                    f"  {status_emoji} {result.component}: {result.status} ({result.response_time_ms:.1f}ms)"
                )

            return 0

        except Exception as e:
            print(f"❌ ENVIRONMENT HEALTH CHECK FAILED: {e}")
            return 1

    exit_code = asyncio.run(main())
    sys.exit(exit_code)
