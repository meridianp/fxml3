"""
FXCM Broker Adapter with Enhanced Containerized forex-connect Integration

This module extends the existing FXCM adapter with enhanced containerized deployment
capabilities for better isolation, reliability, and control over the forex-connect
integration. Designed specifically for the FXML4 Phase 3 requirements.
"""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

import aiohttp

import docker
from fxml4.messaging import ExecutionMessage, OrderMessage
from fxml4.messaging.messages import OrderSide, OrderStatus, OrderType

logger = logging.getLogger(__name__)


class FXCMConnectionError(Exception):
    """Raised when FXCM connection fails."""

    pass


class FXCMAPIError(Exception):
    """Raised when FXCM API returns an error."""

    pass


class FXCMContainerManager:
    """
    Enhanced Docker container manager for FXCM forex-connect integration.

    Provides complete lifecycle management with health monitoring, automatic
    restart capabilities, and performance optimization for trading applications.
    """

    def __init__(
        self,
        image_name: str = "fxml4/fxcm-forex-connect:latest",
        container_name: str = "fxcm_bridge",
        api_port: int = 8080,
        data_port: int = 8081,
        health_check_interval: int = 30,
    ):
        self.image_name = image_name
        self.container_name = container_name
        self.api_port = api_port
        self.data_port = data_port
        self.health_check_interval = health_check_interval

        self.docker_client = None
        self.container = None
        self.is_running = False

        # Health monitoring
        self.last_health_check = None
        self.health_check_failures = 0
        self.max_health_failures = 3

    async def start_container(self) -> None:
        """Start FXCM forex-connect container with full configuration."""
        try:
            self.docker_client = docker.from_env()

            # Check if container already exists and is running
            try:
                existing = self.docker_client.containers.get(self.container_name)
                if existing.status == "running":
                    logger.info(f"Container {self.container_name} already running")
                    self.container = existing
                    self.is_running = True
                    return
                else:
                    # Remove stopped container
                    existing.remove()
                    logger.info(
                        f"Removed existing stopped container {self.container_name}"
                    )
            except docker.errors.NotFound:
                pass

            # Start new container with optimized configuration
            self.container = self.docker_client.containers.run(
                image=self.image_name,
                name=self.container_name,
                ports={"8080/tcp": self.api_port, "8081/tcp": self.data_port},
                detach=True,
                restart_policy={"Name": "unless-stopped"},
                environment={
                    "FXCM_API_PORT": str(self.api_port),
                    "FXCM_DATA_PORT": str(self.data_port),
                    "LOG_LEVEL": "INFO",
                    "PYTHONUNBUFFERED": "1",
                },
                # Resource limits for stability
                mem_limit="1g",
                cpu_count=1,
                # Health check
                healthcheck={
                    "test": f"curl -f http://localhost:{self.api_port}/health || exit 1",
                    "interval": 30000000000,  # 30 seconds in nanoseconds
                    "timeout": 10000000000,  # 10 seconds
                    "retries": 3,
                    "start_period": 30000000000,  # 30 seconds
                },
            )

            # Wait for container to be ready
            await self._wait_for_container_ready()

            self.is_running = True
            logger.info(
                f"FXCM container {self.container_name} started successfully on ports {self.api_port}/{self.data_port}"
            )

        except Exception as e:
            self.is_running = False
            logger.error(f"Failed to start FXCM container: {e}")
            raise FXCMConnectionError(f"Container startup failed: {e}")

    async def _wait_for_container_ready(self, timeout: int = 90) -> None:
        """Wait for container to be ready and responsive with extended timeout."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                self.container.reload()
                if self.container.status == "running":
                    # Test API endpoint with retry logic
                    for attempt in range(3):
                        try:
                            async with aiohttp.ClientSession() as session:
                                async with session.get(
                                    f"http://localhost:{self.api_port}/health",
                                    timeout=aiohttp.ClientTimeout(total=5),
                                ) as response:
                                    if response.status == 200:
                                        health_data = await response.json()
                                        if health_data.get("status") == "ready":
                                            logger.info(
                                                "FXCM container is ready and responsive"
                                            )
                                            return
                        except Exception as e:
                            logger.debug(
                                f"Health check attempt {attempt + 1} failed: {e}"
                            )
                            await asyncio.sleep(2)
            except Exception as e:
                logger.debug(f"Container status check failed: {e}")

            await asyncio.sleep(3)

        raise FXCMConnectionError("Container failed to become ready within timeout")

    async def stop_container(self) -> None:
        """Gracefully stop and remove FXCM container."""
        try:
            if self.container:
                logger.info(f"Stopping FXCM container {self.container_name}")
                self.container.stop(timeout=15)  # Graceful shutdown
                self.container.remove()
                logger.info(f"FXCM container {self.container_name} stopped and removed")

            if self.docker_client:
                self.docker_client.close()

            self.container = None
            self.docker_client = None
            self.is_running = False

        except Exception as e:
            logger.error(f"Error stopping FXCM container: {e}")
            # Force cleanup even if stop fails
            self.container = None
            self.docker_client = None
            self.is_running = False

    async def check_health(self) -> bool:
        """Comprehensive container health check."""
        try:
            if not self.container:
                logger.warning("No container instance available for health check")
                return False

            self.container.reload()

            # Check container status
            if self.container.status != "running":
                logger.warning(
                    f"Container status is {self.container.status}, not running"
                )
                self.is_running = False
                self.health_check_failures += 1
                return False

            # Test API endpoint
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"http://localhost:{self.api_port}/health",
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as response:
                        if response.status == 200:
                            health_data = await response.json()
                            is_healthy = health_data.get("status") == "ready"

                            if is_healthy:
                                self.health_check_failures = 0
                                self.last_health_check = datetime.utcnow()
                                return True
                            else:
                                logger.warning(f"Container not ready: {health_data}")

            except Exception as e:
                logger.warning(f"Container API health check failed: {e}")

            self.health_check_failures += 1
            return False

        except Exception as e:
            logger.error(f"Container health check failed: {e}")
            self.health_check_failures += 1
            return False

    async def restart_if_unhealthy(self) -> bool:
        """Restart container if consistently unhealthy."""
        if self.health_check_failures >= self.max_health_failures:
            logger.warning(
                f"Container unhealthy ({self.health_check_failures} failures), attempting restart"
            )
            try:
                await self.stop_container()
                await asyncio.sleep(5)  # Brief pause
                await self.start_container()
                logger.info("Container restart successful")
                return True
            except Exception as e:
                logger.error(f"Container restart failed: {e}")
                return False
        return False

    def get_container_stats(self) -> Dict[str, Any]:
        """Get container resource usage statistics."""
        if not self.container or not self.is_running:
            return {}

        try:
            stats = self.container.stats(stream=False)
            return {
                "cpu_percent": self._calculate_cpu_percent(stats),
                "memory_usage_mb": stats["memory"]["usage"] / 1024 / 1024,
                "memory_limit_mb": stats["memory"]["limit"] / 1024 / 1024,
                "network_rx_bytes": stats["networks"]["eth0"]["rx_bytes"],
                "network_tx_bytes": stats["networks"]["eth0"]["tx_bytes"],
                "status": self.container.status,
            }
        except Exception as e:
            logger.warning(f"Failed to get container stats: {e}")
            return {}

    def _calculate_cpu_percent(self, stats: Dict) -> float:
        """Calculate CPU usage percentage from Docker stats."""
        try:
            cpu_delta = (
                stats["cpu_stats"]["cpu_usage"]["total_usage"]
                - stats["precpu_stats"]["cpu_usage"]["total_usage"]
            )
            system_delta = (
                stats["cpu_stats"]["system_cpu_usage"]
                - stats["precpu_stats"]["system_cpu_usage"]
            )

            if system_delta > 0:
                return (
                    (cpu_delta / system_delta)
                    * len(stats["cpu_stats"]["cpu_usage"]["percpu_usage"])
                    * 100
                )
            return 0.0
        except (KeyError, ZeroDivisionError):
            return 0.0


class FXCMOrderManager:
    """
    Enhanced order management with comprehensive tracking and performance optimization.
    """

    def __init__(
        self,
        api_url: str = "http://localhost:8080",
        account_id: str = "",
        session_id: str = "",
        timeout_seconds: int = 10,
    ):
        self.api_url = api_url
        self.account_id = account_id
        self.session_id = session_id
        self.timeout_seconds = timeout_seconds

        # Enhanced order tracking
        self.active_orders: Dict[str, Dict] = {}
        self.order_history: Dict[str, Dict] = {}
        self.order_performance: Dict[str, float] = {}

        # Performance metrics
        self.order_count = 0
        self.total_latency_ms = 0
        self.last_order_time: Optional[datetime] = None
        self.successful_orders = 0
        self.failed_orders = 0

    async def place_order(self, order_msg: OrderMessage) -> Dict[str, Any]:
        """Enhanced order placement with detailed performance tracking."""
        start_time = time.time()

        try:
            # Prepare comprehensive order request
            order_request = {
                "account_id": self.account_id,
                "session_id": self.session_id,
                "order_id": order_msg.order_id,
                "client_order_id": order_msg.client_order_id,
                "symbol": order_msg.symbol,
                "side": order_msg.side.value,
                "order_type": order_msg.order_type.value,
                "quantity": str(order_msg.quantity),
                "time_in_force": order_msg.time_in_force,
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Add optional fields
            if order_msg.price:
                order_request["price"] = str(order_msg.price)
            if order_msg.stop_price:
                order_request["stop_price"] = str(order_msg.stop_price)
            if order_msg.strategy_id:
                order_request["strategy_id"] = order_msg.strategy_id

            # Send order with retry logic
            result = await self._send_order_request(order_request)

            # Track successful order
            self.successful_orders += 1
            latency_ms = (time.time() - start_time) * 1000
            self._update_performance_metrics(latency_ms)
            self.order_performance[order_msg.order_id] = latency_ms

            # Store in active orders
            self.active_orders[order_msg.order_id] = {
                **result,
                "client_order_id": order_msg.client_order_id,
                "symbol": order_msg.symbol,
                "submitted_time": datetime.utcnow(),
                "latency_ms": latency_ms,
            }

            result["ack_time_ms"] = round(latency_ms, 2)
            logger.info(
                f"FXCM order {order_msg.order_id} placed successfully in {latency_ms:.2f}ms"
            )

            return result

        except Exception as e:
            self.failed_orders += 1
            logger.error(f"Failed to place FXCM order {order_msg.order_id}: {e}")
            if isinstance(e, FXCMAPIError):
                raise
            raise FXCMConnectionError(f"Order placement failed: {e}")

    async def _send_order_request(
        self, order_request: Dict[str, Any], max_retries: int = 2
    ) -> Dict[str, Any]:
        """Send order request with retry logic."""
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.api_url}/orders",
                        json=order_request,
                        timeout=aiohttp.ClientTimeout(total=self.timeout_seconds),
                    ) as response:

                        result = await response.json()

                        if response.status == 200:
                            return result
                        elif response.status >= 500 and attempt < max_retries:
                            # Retry on server errors
                            logger.warning(
                                f"Server error on attempt {attempt + 1}, retrying..."
                            )
                            await asyncio.sleep(0.5 * (attempt + 1))
                            continue
                        else:
                            raise FXCMAPIError(
                                f"Order placement failed: {result.get('message', 'Unknown error')}"
                            )

            except asyncio.TimeoutError as e:
                last_exception = e
                if attempt < max_retries:
                    logger.warning(f"Timeout on attempt {attempt + 1}, retrying...")
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
            except Exception as e:
                if attempt < max_retries and not isinstance(e, FXCMAPIError):
                    logger.warning(
                        f"Request failed on attempt {attempt + 1}, retrying: {e}"
                    )
                    last_exception = e
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                raise

        # All retries exhausted
        if last_exception:
            raise last_exception
        raise FXCMConnectionError("All retry attempts failed")

    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Enhanced order cancellation with tracking."""
        try:
            if order_id not in self.active_orders:
                raise FXCMAPIError(f"Order {order_id} not found in active orders")

            cancel_request = {
                "account_id": self.account_id,
                "session_id": self.session_id,
                "order_id": order_id,
                "timestamp": datetime.utcnow().isoformat(),
            }

            async with aiohttp.ClientSession() as session:
                async with session.delete(
                    f"{self.api_url}/orders/{order_id}",
                    json=cancel_request,
                    timeout=aiohttp.ClientTimeout(total=self.timeout_seconds),
                ) as response:

                    result = await response.json()

                    if response.status != 200:
                        raise FXCMAPIError(
                            f"Order cancellation failed: {result.get('message', 'Unknown error')}"
                        )

                    # Move to history
                    if order_id in self.active_orders:
                        order_data = self.active_orders.pop(order_id)
                        order_data.update(result)
                        order_data["cancelled_time"] = datetime.utcnow()
                        self.order_history[order_id] = order_data

                    logger.info(f"FXCM order {order_id} cancelled successfully")
                    return result

        except Exception as e:
            logger.error(f"Failed to cancel FXCM order {order_id}: {e}")
            raise

    async def process_order_update(self, update_data: Dict[str, Any]) -> None:
        """Enhanced order update processing with history management."""
        order_id = update_data.get("order_id")
        if not order_id:
            logger.warning("Received order update without order_id")
            return

        status = update_data.get("status", "").upper()
        update_time = datetime.utcnow()

        # Add processing timestamp
        update_data["processed_time"] = update_time.isoformat()

        if order_id in self.active_orders:
            self.active_orders[order_id].update(update_data)

            # Move terminal status orders to history
            if status in ["FILLED", "CANCELLED", "REJECTED", "EXPIRED"]:
                order_data = self.active_orders.pop(order_id)
                order_data["final_status_time"] = update_time
                self.order_history[order_id] = order_data
                logger.info(
                    f"FXCM order {order_id} moved to history with status {status}"
                )
        else:
            # Handle updates for orders not in active tracking
            logger.warning(f"Received update for unknown order {order_id}")
            self.order_history[order_id] = {
                **update_data,
                "processed_time": update_time.isoformat(),
            }

    def _update_performance_metrics(self, latency_ms: float) -> None:
        """Update comprehensive performance metrics."""
        self.order_count += 1
        self.total_latency_ms += latency_ms
        self.last_order_time = datetime.utcnow()

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance metrics."""
        if self.order_count == 0:
            return {
                "total_orders": 0,
                "successful_orders": 0,
                "failed_orders": 0,
                "success_rate": 0.0,
                "average_latency_ms": 0.0,
            }

        return {
            "total_orders": self.order_count,
            "successful_orders": self.successful_orders,
            "failed_orders": self.failed_orders,
            "success_rate": self.successful_orders / self.order_count,
            "average_latency_ms": self.total_latency_ms / self.order_count,
            "active_orders_count": len(self.active_orders),
            "historical_orders_count": len(self.order_history),
            "last_order_time": (
                self.last_order_time.isoformat() if self.last_order_time else None
            ),
        }

    def get_average_latency_ms(self) -> float:
        """Get average order latency."""
        return self.total_latency_ms / max(self.order_count, 1)


class FXCMDataStreamer:
    """Enhanced real-time market data streaming with reliability improvements."""

    def __init__(
        self,
        data_url: str = "ws://localhost:8081/market_data",
        symbols: List[str] = None,
        update_interval_ms: int = 100,
        reconnect_interval: int = 5,
    ):
        self.data_url = data_url
        self.symbols = symbols or ["EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF"]
        self.update_interval_ms = update_interval_ms
        self.reconnect_interval = reconnect_interval

        # Connection state
        self.websocket = None
        self.is_connected = False
        self.connection_attempts = 0
        self.max_connection_attempts = 5

        # Market data storage with timestamps
        self.market_data: Dict[str, Dict] = {}
        self.last_update_time: Dict[str, datetime] = {}
        self.data_quality_metrics: Dict[str, Dict] = {}

        # Callback management
        self.update_callbacks: List[Callable] = []

        # Performance tracking
        self.updates_received = 0
        self.updates_processed = 0
        self.connection_start_time: Optional[datetime] = None

    async def connect(self) -> None:
        """Enhanced WebSocket connection with retry logic."""
        for attempt in range(self.max_connection_attempts):
            try:
                logger.info(f"Connecting to FXCM data stream (attempt {attempt + 1})")

                import websockets

                self.websocket = await websockets.connect(
                    self.data_url, ping_interval=20, ping_timeout=10, close_timeout=10
                )

                self.is_connected = True
                self.connection_attempts = 0
                self.connection_start_time = datetime.utcnow()

                logger.info(f"Connected to FXCM market data stream at {self.data_url}")

                # Subscribe to symbols
                await self._subscribe_to_symbols()
                return

            except Exception as e:
                self.connection_attempts += 1
                logger.warning(f"Connection attempt {attempt + 1} failed: {e}")

                if attempt < self.max_connection_attempts - 1:
                    await asyncio.sleep(self.reconnect_interval * (attempt + 1))

        self.is_connected = False
        raise FXCMConnectionError(
            "Failed to connect to data stream after maximum attempts"
        )

    async def disconnect(self) -> None:
        """Graceful disconnect from market data stream."""
        try:
            if self.websocket:
                await self.websocket.close()
            self.is_connected = False
            self.connection_start_time = None
            logger.info("Disconnected from FXCM market data stream")
        except Exception as e:
            logger.error(f"Error disconnecting from data stream: {e}")
            self.is_connected = False

    async def _subscribe_to_symbols(self) -> None:
        """Subscribe to market data with enhanced configuration."""
        subscription_batch = []

        for symbol in self.symbols:
            subscribe_msg = {
                "action": "subscribe",
                "symbol": symbol,
                "update_interval_ms": self.update_interval_ms,
                "include_volume": True,
                "include_timestamp": True,
            }
            subscription_batch.append(subscribe_msg)

        # Send batch subscription
        batch_msg = {"action": "batch_subscribe", "subscriptions": subscription_batch}

        await self.websocket.send(json.dumps(batch_msg))
        logger.info(f"Subscribed to market data for {len(self.symbols)} symbols")

    async def process_market_update(self, update_data: Dict[str, Any]) -> None:
        """Enhanced market data processing with quality metrics."""
        self.updates_received += 1
        symbol = update_data.get("symbol")

        if not symbol:
            logger.warning("Received market update without symbol")
            return

        try:
            # Process and validate data
            processed_data = {
                "bid": float(update_data.get("bid", 0)),
                "ask": float(update_data.get("ask", 0)),
                "spread": float(update_data.get("spread", 0)),
                "timestamp": update_data.get(
                    "timestamp", datetime.utcnow().isoformat()
                ),
                "volume": float(update_data.get("volume", 0)),
                "processed_at": datetime.utcnow().isoformat(),
            }

            # Data quality validation
            if processed_data["bid"] <= 0 or processed_data["ask"] <= 0:
                logger.warning(f"Invalid price data for {symbol}: {processed_data}")
                return

            if processed_data["ask"] <= processed_data["bid"]:
                logger.warning(f"Invalid spread for {symbol}: ask <= bid")
                return

            # Store data and update metrics
            self.market_data[symbol] = processed_data
            self.last_update_time[symbol] = datetime.utcnow()

            # Track data quality
            if symbol not in self.data_quality_metrics:
                self.data_quality_metrics[symbol] = {
                    "total_updates": 0,
                    "valid_updates": 0,
                    "last_valid_update": None,
                }

            self.data_quality_metrics[symbol]["total_updates"] += 1
            self.data_quality_metrics[symbol]["valid_updates"] += 1
            self.data_quality_metrics[symbol][
                "last_valid_update"
            ] = datetime.utcnow().isoformat()

            self.updates_processed += 1

            # Notify callbacks
            await self._notify_callbacks(symbol, processed_data)

        except Exception as e:
            logger.error(f"Error processing market update for {symbol}: {e}")

    async def _notify_callbacks(self, symbol: str, data: Dict[str, Any]) -> None:
        """Notify all registered callbacks of market data updates."""
        for callback in self.update_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(symbol, data)
                else:
                    callback(symbol, data)
            except Exception as e:
                logger.error(f"Error in market data callback: {e}")

    def add_update_callback(self, callback: Callable) -> None:
        """Add callback for market data updates."""
        self.update_callbacks.append(callback)

    def remove_update_callback(self, callback: Callable) -> None:
        """Remove callback for market data updates."""
        if callback in self.update_callbacks:
            self.update_callbacks.remove(callback)

    def get_current_price(self, symbol: str) -> Optional[Dict[str, float]]:
        """Get current bid/ask prices for symbol."""
        return self.market_data.get(symbol)

    def get_spread(self, symbol: str) -> Optional[float]:
        """Get current spread for symbol."""
        data = self.market_data.get(symbol)
        return data.get("spread") if data else None

    def get_data_quality_report(self) -> Dict[str, Any]:
        """Get comprehensive data quality report."""
        return {
            "total_updates_received": self.updates_received,
            "total_updates_processed": self.updates_processed,
            "processing_success_rate": self.updates_processed
            / max(self.updates_received, 1),
            "symbols_tracked": len(self.symbols),
            "symbols_with_data": len(self.market_data),
            "connection_uptime_seconds": (
                (datetime.utcnow() - self.connection_start_time).total_seconds()
                if self.connection_start_time
                else 0
            ),
            "symbol_metrics": self.data_quality_metrics,
        }


class FXCMBrokerAdapter:
    """
    Enhanced FXCM broker adapter with comprehensive containerized integration.

    This is the main coordination class that brings together container management,
    order execution, and market data streaming for a complete FXCM integration
    suitable for high-frequency trading requirements.
    """

    def __init__(
        self,
        username: str = "",
        password: str = "",
        server: str = "Demo",
        account_id: str = "",
        container_config: Optional[Dict[str, Any]] = None,
    ):
        self.username = username
        self.password = password
        self.server = server
        self.account_id = account_id

        # Connection state
        self.is_connected = False
        self.session_id: Optional[str] = None
        self.login_time: Optional[datetime] = None
        self.connection_retries = 0
        self.max_connection_retries = 3

        # Enhanced component initialization
        container_cfg = container_config or {}
        self.container_manager = FXCMContainerManager(
            image_name=container_cfg.get("image", "fxml4/fxcm-connect:latest"),
            api_port=container_cfg.get("api_port", 8080),
            data_port=container_cfg.get("data_port", 8081),
            health_check_interval=container_cfg.get("health_check_interval", 30),
        )

        self.order_manager = FXCMOrderManager(
            api_url=f"http://localhost:{self.container_manager.api_port}",
            account_id=self.account_id,
            timeout_seconds=container_cfg.get("timeout_seconds", 10),
        )

        self.data_streamer = FXCMDataStreamer(
            data_url=f"ws://localhost:{self.container_manager.data_port}/market_data",
            symbols=container_cfg.get(
                "symbols", ["EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF"]
            ),
            update_interval_ms=container_cfg.get("update_interval_ms", 100),
        )

        # Performance and monitoring
        self.connection_count = 0
        self.last_connection_time: Optional[datetime] = None
        self.health_monitor_task: Optional[asyncio.Task] = None

        logger.info(f"Enhanced FXCM adapter initialized for account {account_id}")

    async def connect(self) -> None:
        """Comprehensive connection workflow with full error handling."""
        try:
            logger.info("Starting FXCM adapter connection workflow...")

            # Step 1: Start container infrastructure
            if not self.container_manager.is_running:
                logger.info("Starting FXCM container...")
                await self.container_manager.start_container()
                await asyncio.sleep(5)  # Allow container to fully initialize

            # Step 2: Verify container health
            if not await self.container_manager.check_health():
                raise FXCMConnectionError("Container failed health check after startup")

            # Step 3: Authenticate with FXCM
            logger.info("Authenticating with FXCM...")
            auth_result = await self._authenticate()

            self.session_id = auth_result["session_id"]
            self.order_manager.session_id = self.session_id

            # Step 4: Connect data streamer
            logger.info("Connecting market data stream...")
            await self.data_streamer.connect()

            # Step 5: Start health monitoring
            self.health_monitor_task = asyncio.create_task(self._health_monitor_loop())

            # Update connection state
            self.is_connected = True
            self.login_time = datetime.utcnow()
            self.connection_count += 1
            self.last_connection_time = self.login_time
            self.connection_retries = 0

            logger.info(
                f"FXCM adapter connected successfully (session: {self.session_id})"
            )

        except Exception as e:
            self.is_connected = False
            logger.error(f"FXCM connection failed: {e}")

            # Cleanup on failure
            await self._cleanup_on_failure()
            raise

    async def _authenticate(self, max_retries: int = 3) -> Dict[str, Any]:
        """Enhanced authentication with retry logic."""
        auth_request = {
            "username": self.username,
            "password": self.password,
            "server": self.server,
            "account_id": self.account_id,
            "client_info": {
                "application": "FXML4",
                "version": "1.0",
                "timestamp": datetime.utcnow().isoformat(),
            },
        }

        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"http://localhost:{self.container_manager.api_port}/login",
                        json=auth_request,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as response:

                        result = await response.json()

                        if response.status == 200:
                            logger.info("FXCM authentication successful")
                            return result
                        elif response.status >= 500 and attempt < max_retries - 1:
                            # Retry on server errors
                            logger.warning(
                                f"Server error during authentication, retrying..."
                            )
                            await asyncio.sleep(2 * (attempt + 1))
                            continue
                        else:
                            raise FXCMConnectionError(
                                f"Login failed: {result.get('message', 'Unknown error')}"
                            )

            except asyncio.TimeoutError:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Authentication timeout, retrying attempt {attempt + 2}"
                    )
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
                raise FXCMConnectionError("Authentication timed out")

        raise FXCMConnectionError("Authentication failed after all retries")

    async def _health_monitor_loop(self) -> None:
        """Background health monitoring with automatic recovery."""
        while self.is_connected:
            try:
                # Check container health
                container_healthy = await self.container_manager.check_health()

                if not container_healthy:
                    logger.warning("Container health check failed")

                    # Attempt container restart
                    if await self.container_manager.restart_if_unhealthy():
                        # Give time for restart
                        await asyncio.sleep(10)

                        # Re-authenticate after restart
                        try:
                            auth_result = await self._authenticate()
                            self.session_id = auth_result["session_id"]
                            self.order_manager.session_id = self.session_id
                            logger.info("Re-authenticated after container restart")
                        except Exception as e:
                            logger.error(f"Re-authentication failed: {e}")

                # Check data stream health
                if not self.data_streamer.is_connected:
                    logger.warning("Data stream disconnected, attempting reconnection")
                    try:
                        await self.data_streamer.connect()
                        logger.info("Data stream reconnected successfully")
                    except Exception as e:
                        logger.error(f"Data stream reconnection failed: {e}")

                await asyncio.sleep(self.container_manager.health_check_interval)

            except asyncio.CancelledError:
                logger.info("Health monitor task cancelled")
                break
            except Exception as e:
                logger.error(f"Health monitor error: {e}")
                await asyncio.sleep(30)  # Brief pause before retry

    async def disconnect(self) -> None:
        """Comprehensive disconnect with cleanup."""
        logger.info("Disconnecting FXCM adapter...")

        try:
            # Stop health monitoring
            if self.health_monitor_task and not self.health_monitor_task.done():
                self.health_monitor_task.cancel()
                try:
                    await self.health_monitor_task
                except asyncio.CancelledError:
                    pass

            # Disconnect data streamer
            await self.data_streamer.disconnect()

            # Logout from FXCM
            await self._logout()

            # Stop container
            await self.container_manager.stop_container()

            self.is_connected = False
            self.session_id = None

            logger.info("FXCM adapter disconnected successfully")

        except Exception as e:
            logger.error(f"Error during FXCM disconnect: {e}")
            # Force cleanup
            self.is_connected = False
            self.session_id = None

    async def _logout(self) -> None:
        """Logout from FXCM session."""
        if self.session_id:
            try:
                async with aiohttp.ClientSession() as session:
                    await session.post(
                        f"http://localhost:{self.container_manager.api_port}/logout",
                        json={"session_id": self.session_id},
                        timeout=aiohttp.ClientTimeout(total=10),
                    )
                logger.info("FXCM logout successful")
            except Exception as e:
                logger.warning(f"Logout request failed: {e}")

    async def _cleanup_on_failure(self) -> None:
        """Cleanup resources on connection failure."""
        try:
            if self.health_monitor_task and not self.health_monitor_task.done():
                self.health_monitor_task.cancel()

            await self.data_streamer.disconnect()
            await self.container_manager.stop_container()
        except Exception as e:
            logger.error(f"Cleanup on failure error: {e}")

    async def execute_order(self, order_msg: OrderMessage) -> Dict[str, Any]:
        """Execute order with comprehensive validation."""
        if not self.is_connected:
            raise FXCMConnectionError("Not connected to FXCM")

        if not self.session_id:
            raise FXCMConnectionError("No active FXCM session")

        logger.info(f"Executing FXCM order {order_msg.order_id} for {order_msg.symbol}")
        return await self.order_manager.place_order(order_msg)

    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel order with validation."""
        if not self.is_connected:
            raise FXCMConnectionError("Not connected to FXCM")

        return await self.order_manager.cancel_order(order_id)

    async def get_positions(self) -> List[Dict[str, Any]]:
        """Retrieve current positions with enhanced error handling."""
        if not self.is_connected:
            raise FXCMConnectionError("Not connected to FXCM")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://localhost:{self.container_manager.api_port}/positions",
                    params={
                        "session_id": self.session_id,
                        "account_id": self.account_id,
                    },
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as response:

                    if response.status != 200:
                        result = await response.json()
                        raise FXCMAPIError(
                            f"Failed to get positions: {result.get('message', 'Unknown error')}"
                        )

                    positions = await response.json()
                    logger.debug(f"Retrieved {len(positions)} positions from FXCM")
                    return positions

        except Exception as e:
            logger.error(f"Failed to retrieve FXCM positions: {e}")
            if isinstance(e, FXCMAPIError):
                raise
            raise FXCMConnectionError(f"Position retrieval failed: {e}")

    async def get_account_info(self) -> Dict[str, Any]:
        """Get comprehensive account information."""
        if not self.is_connected:
            raise FXCMConnectionError("Not connected to FXCM")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://localhost:{self.container_manager.api_port}/account",
                    params={
                        "session_id": self.session_id,
                        "account_id": self.account_id,
                        "include_details": "true",
                    },
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as response:

                    if response.status != 200:
                        result = await response.json()
                        raise FXCMAPIError(
                            f"Failed to get account info: {result.get('message', 'Unknown error')}"
                        )

                    return await response.json()

        except Exception as e:
            logger.error(f"Failed to get FXCM account info: {e}")
            raise FXCMConnectionError(f"Account info retrieval failed: {e}")

    def get_current_price(self, symbol: str) -> Optional[Dict[str, float]]:
        """Get current market price for symbol."""
        return self.data_streamer.get_current_price(symbol)

    def add_market_data_callback(self, callback: Callable) -> None:
        """Add callback for real-time market data updates."""
        self.data_streamer.add_update_callback(callback)

    def remove_market_data_callback(self, callback: Callable) -> None:
        """Remove callback for real-time market data updates."""
        self.data_streamer.remove_update_callback(callback)

    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check report."""
        container_health = await self.container_manager.check_health()
        container_stats = self.container_manager.get_container_stats()
        order_performance = self.order_manager.get_performance_summary()
        data_quality = self.data_streamer.get_data_quality_report()

        return {
            "adapter": {
                "is_connected": self.is_connected,
                "session_id": self.session_id,
                "account_id": self.account_id,
                "connection_count": self.connection_count,
                "connection_uptime_seconds": (
                    (datetime.utcnow() - self.login_time).total_seconds()
                    if self.login_time
                    else 0
                ),
            },
            "container": {
                "is_running": self.container_manager.is_running,
                "health_status": container_health,
                "health_failures": self.container_manager.health_check_failures,
                "stats": container_stats,
            },
            "order_management": order_performance,
            "data_streaming": {
                "is_connected": self.data_streamer.is_connected,
                "quality_report": data_quality,
            },
        }

    @asynccontextmanager
    async def connection_context(self):
        """Context manager for FXCM connection lifecycle."""
        await self.connect()
        try:
            yield self
        finally:
            await self.disconnect()

    def __repr__(self) -> str:
        return f"FXCMBrokerAdapter(connected={self.is_connected}, session={self.session_id}, account={self.account_id})"
