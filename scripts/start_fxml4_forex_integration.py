#!/usr/bin/env python3
"""Startup script for FXML4-ForexConnect integrated trading system.

This script orchestrates the startup of all components in the correct order,
performs health checks, and provides monitoring and control capabilities.
"""

import asyncio
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
import yaml

import docker

# Import paths handled by PYTHONPATH wrapper
project_root = Path(__file__).parent.parent

from fxml4.core.logging import get_logger

logger = get_logger(__name__)


class ServiceHealth:
    """Service health status tracking."""

    def __init__(self, name: str, url: str, required: bool = True):
        self.name = name
        self.url = url
        self.required = required
        self.healthy = False
        self.last_check = None
        self.error = None


class IntegratedSystemManager:
    """Manager for FXML4-ForexConnect integrated system."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize system manager.

        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path or "config/fxcm_integration.yaml"
        self.docker_compose_file = "docker-compose.fxml4-forex.yml"

        # Load configuration
        self.config = self._load_config()

        # Docker client
        self.docker_client = docker.from_env()

        # Service definitions
        self.services = {
            "rabbitmq": ServiceHealth("RabbitMQ", "http://localhost:15672"),
            "db": ServiceHealth("TimescaleDB", "postgresql://localhost:5432/fxml4"),
            "redis": ServiceHealth("Redis", "redis://localhost:6379"),
            "forex-middleware": ServiceHealth(
                "ForexConnect Middleware", "http://localhost:8080/health"
            ),
            "api": ServiceHealth("FXML4 API", "http://localhost:8000/health"),
            "dashboard": ServiceHealth(
                "FXML4 Dashboard", "http://localhost:8501", required=False
            ),
            "fxcm-adapter": ServiceHealth(
                "FXCM Bridge Adapter",
                "http://localhost:8000/health/brokers",
                required=False,
            ),
        }

        # System state
        self.running = False
        self.startup_complete = False
        self.shutdown_requested = False

        logger.info("Integrated system manager initialized")

    def _load_config(self) -> Dict[str, Any]:
        """Load system configuration."""
        try:
            config_file = Path(self.config_path)
            if not config_file.exists():
                logger.warning(
                    f"Config file {self.config_path} not found, using defaults"
                )
                return {}

            with open(config_file, "r") as f:
                config = yaml.safe_load(f)

            logger.info(f"Loaded configuration from {self.config_path}")
            return config

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            return {}

    async def start_system(self) -> bool:
        """Start the integrated system.

        Returns:
            True if startup successful
        """
        logger.info("Starting FXML4-ForexConnect integrated system...")

        try:
            # Step 1: Pre-flight checks
            if not await self._preflight_checks():
                return False

            # Step 2: Start infrastructure services
            if not await self._start_infrastructure():
                return False

            # Step 3: Start application services
            if not await self._start_applications():
                return False

            # Step 4: Verify system health
            if not await self._verify_system_health():
                return False

            # Step 5: Initialize trading system
            if not await self._initialize_trading_system():
                return False

            self.running = True
            self.startup_complete = True

            logger.info("🚀 FXML4-ForexConnect integrated system started successfully!")
            self._print_system_status()

            return True

        except Exception as e:
            logger.error(f"System startup failed: {e}")
            await self.stop_system()
            return False

    async def _preflight_checks(self) -> bool:
        """Perform pre-flight system checks."""
        logger.info("Performing pre-flight checks...")

        # Check Docker is available
        try:
            self.docker_client.ping()
            logger.info("✓ Docker is available")
        except Exception as e:
            logger.error(f"✗ Docker not available: {e}")
            return False

        # Check docker-compose file exists
        compose_file = Path(self.docker_compose_file)
        if not compose_file.exists():
            logger.error(f"✗ Docker compose file not found: {self.docker_compose_file}")
            return False
        logger.info("✓ Docker compose file found")

        # Check environment variables
        required_env_vars = [
            "FOREX_USER_ID",
            "FOREX_PASSWORD",
            "POSTGRES_PASSWORD",
            "RABBITMQ_PASSWORD",
        ]

        missing_vars = []
        for var in required_env_vars:
            if not os.getenv(var):
                missing_vars.append(var)

        if missing_vars:
            logger.error(f"✗ Missing environment variables: {missing_vars}")
            logger.info("Please create .env file with required credentials")
            return False

        logger.info("✓ Environment variables configured")

        # Check ports are available
        ports_to_check = [5672, 15672, 5432, 6379, 8080, 8000, 8501]
        busy_ports = []

        for port in ports_to_check:
            if self._is_port_busy(port):
                busy_ports.append(port)

        if busy_ports:
            logger.warning(f"⚠ Ports already in use: {busy_ports}")
            logger.info("System will attempt to use existing services if compatible")

        logger.info("✓ Pre-flight checks completed")
        return True

    def _is_port_busy(self, port: int) -> bool:
        """Check if port is already in use."""
        import socket

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(("localhost", port))
                return result == 0
        except:
            return False

    async def _start_infrastructure(self) -> bool:
        """Start infrastructure services (databases, message queue)."""
        logger.info("Starting infrastructure services...")

        # Start core infrastructure with docker-compose
        infrastructure_services = ["rabbitmq", "db", "redis"]

        try:
            for service in infrastructure_services:
                logger.info(f"Starting {service}...")
                result = subprocess.run(
                    [
                        "docker-compose",
                        "-f",
                        self.docker_compose_file,
                        "up",
                        "-d",
                        service,
                    ],
                    capture_output=True,
                    text=True,
                )

                if result.returncode != 0:
                    logger.error(f"Failed to start {service}: {result.stderr}")
                    return False

                # Wait for service to be healthy
                max_wait = 60  # seconds
                wait_time = 0
                while wait_time < max_wait:
                    if await self._check_service_health(service):
                        logger.info(f"✓ {service} is healthy")
                        break
                    await asyncio.sleep(2)
                    wait_time += 2
                else:
                    logger.error(
                        f"✗ {service} failed to become healthy within {max_wait}s"
                    )
                    return False

            logger.info("✓ Infrastructure services started")
            return True

        except Exception as e:
            logger.error(f"Infrastructure startup failed: {e}")
            return False

    async def _start_applications(self) -> bool:
        """Start application services."""
        logger.info("Starting application services...")

        # Start ForexConnect middleware first
        try:
            logger.info("Starting ForexConnect middleware...")
            result = subprocess.run(
                [
                    "docker-compose",
                    "-f",
                    self.docker_compose_file,
                    "up",
                    "-d",
                    "forex-middleware",
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                logger.error(f"Failed to start forex-middleware: {result.stderr}")
                return False

            # Wait for ForexConnect to connect
            max_wait = 120  # 2 minutes for ForexConnect connection
            wait_time = 0
            while wait_time < max_wait:
                if await self._check_service_health("forex-middleware"):
                    logger.info("✓ ForexConnect middleware is healthy")
                    break
                await asyncio.sleep(5)
                wait_time += 5
            else:
                logger.error("✗ ForexConnect middleware failed to connect")
                return False

        except Exception as e:
            logger.error(f"ForexConnect middleware startup failed: {e}")
            return False

        # Start FXML4 services
        fxml4_services = ["api", "worker", "fxcm-adapter", "dashboard"]

        try:
            for service in fxml4_services:
                logger.info(f"Starting {service}...")
                result = subprocess.run(
                    [
                        "docker-compose",
                        "-f",
                        self.docker_compose_file,
                        "up",
                        "-d",
                        service,
                    ],
                    capture_output=True,
                    text=True,
                )

                if result.returncode != 0:
                    logger.error(f"Failed to start {service}: {result.stderr}")
                    if self.services[service].required:
                        return False
                    else:
                        logger.warning(f"Optional service {service} failed to start")
                        continue

                # Wait for service health
                max_wait = 60
                wait_time = 0
                while wait_time < max_wait:
                    if await self._check_service_health(service):
                        logger.info(f"✓ {service} is healthy")
                        break
                    await asyncio.sleep(2)
                    wait_time += 2
                else:
                    if self.services[service].required:
                        logger.error(f"✗ {service} failed to become healthy")
                        return False
                    else:
                        logger.warning(f"⚠ Optional service {service} not healthy")

            logger.info("✓ Application services started")
            return True

        except Exception as e:
            logger.error(f"Application startup failed: {e}")
            return False

    async def _check_service_health(self, service_name: str) -> bool:
        """Check health of a specific service."""
        service = self.services.get(service_name)
        if not service:
            return False

        try:
            if service_name == "db":
                # Check database connection
                result = subprocess.run(
                    [
                        "docker",
                        "exec",
                        "fxml4-forex-db",
                        "pg_isready",
                        "-U",
                        "postgres",
                    ],
                    capture_output=True,
                    text=True,
                )
                healthy = result.returncode == 0

            elif service_name == "redis":
                # Check Redis connection
                result = subprocess.run(
                    ["docker", "exec", "fxml4-forex-redis", "redis-cli", "ping"],
                    capture_output=True,
                    text=True,
                )
                healthy = "PONG" in result.stdout

            elif service_name == "rabbitmq":
                # Check RabbitMQ
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        "http://localhost:15672/api/overview",
                        auth=aiohttp.BasicAuth(
                            "fxml4", os.getenv("RABBITMQ_PASSWORD", "fxml4_pass")
                        ),
                    ) as response:
                        healthy = response.status == 200

            else:
                # HTTP health check
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        service.url, timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        healthy = response.status == 200

            service.healthy = healthy
            service.last_check = datetime.utcnow()

            if not healthy:
                service.error = "Health check failed"
            else:
                service.error = None

            return healthy

        except Exception as e:
            service.healthy = False
            service.error = str(e)
            service.last_check = datetime.utcnow()
            return False

    async def _verify_system_health(self) -> bool:
        """Verify overall system health."""
        logger.info("Verifying system health...")

        healthy_count = 0
        total_required = 0

        for name, service in self.services.items():
            is_healthy = await self._check_service_health(name)

            if service.required:
                total_required += 1
                if is_healthy:
                    healthy_count += 1
                    logger.info(f"✓ {service.name} is healthy")
                else:
                    logger.error(f"✗ {service.name} is unhealthy: {service.error}")
            else:
                if is_healthy:
                    logger.info(f"✓ {service.name} is healthy (optional)")
                else:
                    logger.warning(
                        f"⚠ {service.name} is unhealthy (optional): {service.error}"
                    )

        if healthy_count < total_required:
            logger.error(
                f"System health check failed: {healthy_count}/{total_required} required services healthy"
            )
            return False

        logger.info(
            f"✓ System health check passed: {healthy_count}/{total_required} required services healthy"
        )
        return True

    async def _initialize_trading_system(self) -> bool:
        """Initialize trading system components."""
        logger.info("Initializing trading system...")

        try:
            # Test FXML4 API connection
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:8000/health") as response:
                    if response.status != 200:
                        logger.error("FXML4 API not responding")
                        return False

                    health_data = await response.json()
                    logger.info(
                        f"FXML4 API Status: {health_data.get('status', 'unknown')}"
                    )

            # Test ForexConnect middleware connection
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:8080/health") as response:
                    if response.status != 200:
                        logger.error("ForexConnect middleware not responding")
                        return False

                    health_data = await response.json()
                    logger.info(
                        f"ForexConnect Status: {health_data.get('status', 'unknown')}"
                    )

                    if health_data.get("forex_connect_status") != "connected":
                        logger.error("ForexConnect API not connected")
                        return False

            # Test bridge adapter connection
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        "http://localhost:8000/health/brokers"
                    ) as response:
                        if response.status == 200:
                            broker_health = await response.json()
                            logger.info(
                                f"Bridge Adapter Status: {broker_health.get('fxcm_bridge', 'unknown')}"
                            )
            except:
                logger.warning("Bridge adapter health check not available (optional)")

            logger.info("✓ Trading system initialized")
            return True

        except Exception as e:
            logger.error(f"Trading system initialization failed: {e}")
            return False

    def _print_system_status(self):
        """Print current system status."""
        print("\n" + "=" * 60)
        print("🚀 FXML4-ForexConnect Integration System Status")
        print("=" * 60)

        print("\n📊 Services:")
        for name, service in self.services.items():
            status = "✅ Healthy" if service.healthy else "❌ Unhealthy"
            required = "(Required)" if service.required else "(Optional)"
            print(f"  {service.name:<25} {status} {required}")

        print(f"\n🌐 Web Interfaces:")
        print(f"  FXML4 API:          http://localhost:8000")
        print(f"  FXML4 Dashboard:    http://localhost:8501")
        print(f"  RabbitMQ Management: http://localhost:15672")
        print(f"  Grafana:            http://localhost:3000")
        print(f"  Prometheus:         http://localhost:9090")

        print(f"\n🔧 Management:")
        print(f"  Logs: docker-compose -f {self.docker_compose_file} logs -f")
        print(f"  Stop: python {__file__} --stop")
        print(f"  Status: python {__file__} --status")

        print("=" * 60)

    async def monitor_system(self, interval: int = 30):
        """Monitor system health continuously."""
        logger.info(f"Starting system monitoring (interval: {interval}s)")

        while self.running and not self.shutdown_requested:
            try:
                # Check all service health
                unhealthy_services = []
                for name, service in self.services.items():
                    if not await self._check_service_health(name):
                        if service.required:
                            unhealthy_services.append(name)

                # Log status
                if unhealthy_services:
                    logger.warning(f"Unhealthy services detected: {unhealthy_services}")
                else:
                    logger.debug("All required services healthy")

                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(interval)

    async def stop_system(self):
        """Stop the integrated system."""
        logger.info("Stopping FXML4-ForexConnect integrated system...")

        self.shutdown_requested = True
        self.running = False

        try:
            # Stop docker-compose services
            result = subprocess.run(
                ["docker-compose", "-f", self.docker_compose_file, "down"],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                logger.info("✓ All services stopped")
            else:
                logger.error(f"Error stopping services: {result.stderr}")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    async def get_system_status(self) -> Dict[str, Any]:
        """Get current system status."""
        status = {
            "running": self.running,
            "startup_complete": self.startup_complete,
            "timestamp": datetime.utcnow().isoformat(),
            "services": {},
        }

        for name, service in self.services.items():
            await self._check_service_health(name)
            status["services"][name] = {
                "healthy": service.healthy,
                "required": service.required,
                "last_check": (
                    service.last_check.isoformat() if service.last_check else None
                ),
                "error": service.error,
            }

        return status


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="FXML4-ForexConnect Integration System Manager"
    )
    parser.add_argument(
        "--start", action="store_true", help="Start the integrated system"
    )
    parser.add_argument(
        "--stop", action="store_true", help="Stop the integrated system"
    )
    parser.add_argument("--status", action="store_true", help="Show system status")
    parser.add_argument("--monitor", action="store_true", help="Monitor system health")
    parser.add_argument("--config", help="Configuration file path")

    args = parser.parse_args()

    # Create system manager
    manager = IntegratedSystemManager(config_path=args.config)

    # Handle shutdown signals
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating shutdown...")
        asyncio.create_task(manager.stop_system())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        if args.stop:
            await manager.stop_system()

        elif args.status:
            status = await manager.get_system_status()
            print(f"\nSystem Status: {'Running' if status['running'] else 'Stopped'}")
            print(f"Startup Complete: {status['startup_complete']}")
            print(f"Last Check: {status['timestamp']}")

            for name, service_status in status["services"].items():
                health = "✅" if service_status["healthy"] else "❌"
                req = "(Required)" if service_status["required"] else "(Optional)"
                print(f"  {name:<20} {health} {req}")
                if service_status["error"]:
                    print(f"    Error: {service_status['error']}")

        elif args.monitor:
            if not await manager.start_system():
                sys.exit(1)
            await manager.monitor_system()

        else:  # Default: start system
            if await manager.start_system():
                try:
                    # Run monitoring in background
                    monitor_task = asyncio.create_task(manager.monitor_system())

                    # Wait for shutdown signal
                    while manager.running:
                        await asyncio.sleep(1)

                    monitor_task.cancel()

                except KeyboardInterrupt:
                    logger.info("Shutdown requested by user")

                await manager.stop_system()
            else:
                logger.error("System startup failed")
                sys.exit(1)

    except Exception as e:
        logger.error(f"System manager error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
