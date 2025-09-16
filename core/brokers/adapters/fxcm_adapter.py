"""FXCM Broker Adapter.

This adapter integrates with FXCM through a Docker-based bridge service
that handles the ForexConnect API communication.
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import aiohttp

from ...fix.messages.base import FIXMessage, OrdStatus
from ...fix.messages.orders import ExecutionReport, NewOrderSingle, OrderCancelRequest

# Use fast FIX implementations for better performance
from ...fix.utils.fast_builder import FastFIXBuilder, fast_build_fix
from ...fix.utils.fast_parser import FastFIXParser, fast_parse_fix

# Performance monitoring
from ...monitoring.metrics import (
    performance_timer,
    track_broker_adapter,
    track_fix_message,
)
from .base import AdapterConfig, AdapterMetrics, BrokerAdapter, ConnectionStatus

logger = logging.getLogger(__name__)


class FXCMBrokerAdapter(BrokerAdapter):
    """FXCM broker adapter implementation.

    This adapter communicates with FXCM via a Docker-based bridge service
    that runs ForexConnect API in an isolated Python 3.7 environment.
    """

    def __init__(self, config: AdapterConfig):
        """Initialize FXCM adapter.

        Args:
            config: Adapter configuration including bridge service URL.
        """
        super().__init__(config)

        # Bridge service configuration
        self.bridge_url = config.connection_params.get(
            "bridge_url", "http://fxcm-bridge:9090"
        )
        self.api_key = config.connection_params.get("api_key")

        # HTTP session for bridge communication
        self.session: Optional[aiohttp.ClientSession] = None

        # FIX message handling - use fast implementations for performance
        self.fix_builder = FastFIXBuilder()
        self.fix_parser = FastFIXParser()

        # Order tracking
        self.active_orders: Dict[str, Dict[str, Any]] = {}
        self.order_map: Dict[str, str] = {}  # cl_ord_id -> bridge_order_id

        # Status monitoring
        self.bridge_connected = False
        self.last_heartbeat = datetime.utcnow()
        self._monitor_task: Optional[asyncio.Task] = None

        logger.info(f"Initialized FXCM adapter with bridge URL: {self.bridge_url}")

    async def connect(self) -> bool:
        """Connect to FXCM via bridge service.

        Returns:
            True if connection successful, False otherwise.
        """
        start_time = time.time()
        try:
            logger.info("Connecting to FXCM bridge service...")

            # Create HTTP session
            headers = {}
            if self.api_key:
                headers["X-API-Key"] = self.api_key

            self.session = aiohttp.ClientSession(
                headers=headers, timeout=aiohttp.ClientTimeout(total=30)
            )

            # Check bridge health
            health_url = urljoin(self.bridge_url, "/health")
            async with self.session.get(health_url) as response:
                if response.status != 200:
                    raise Exception(f"Bridge health check failed: {response.status}")

                health_data = await response.json()
                self.bridge_connected = health_data.get("connected", False)

            if not self.bridge_connected:
                logger.warning("Bridge is not connected to FXCM")

            # Get bridge status
            status_url = urljoin(self.bridge_url, "/status")
            async with self.session.get(status_url) as response:
                if response.status == 200:
                    status_data = await response.json()
                    self.account_id = status_data.get("account_id")
                    logger.info(f"Connected to FXCM account: {self.account_id}")

            # Update connection status
            self.connection.status = ConnectionStatus.READY
            self.connection._connected = True
            self.connection._authenticated = True

            # Start monitoring task
            self._monitor_task = asyncio.create_task(self._monitor_bridge())

            # Update metrics
            self.metrics.last_connect_time = datetime.utcnow()

            logger.info("Successfully connected to FXCM bridge service")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to FXCM bridge: {e}")
            self.connection.status = ConnectionStatus.ERROR
            self.connection.error = str(e)

            if self.session:
                await self.session.close()
                self.session = None

            # Track failed connection
            track_broker_adapter("fxcm", "connect", False, time.time() - start_time)
            return False

        finally:
            # Track successful connection
            if (
                hasattr(self, "connection")
                and self.connection.status == ConnectionStatus.CONNECTED
            ):
                track_broker_adapter("fxcm", "connect", True, time.time() - start_time)

    async def disconnect(self) -> None:
        """Disconnect from FXCM bridge service."""
        try:
            logger.info("Disconnecting from FXCM bridge service...")

            # Cancel monitoring task
            if self._monitor_task:
                self._monitor_task.cancel()
                try:
                    await self._monitor_task
                except asyncio.CancelledError:
                    pass

            # Close HTTP session
            if self.session:
                await self.session.close()
                self.session = None

            # Clear state
            self.active_orders.clear()
            self.order_map.clear()
            self.bridge_connected = False

            # Update connection status
            self.connection.status = ConnectionStatus.DISCONNECTED
            self.connection._connected = False
            self.connection._authenticated = False

            # Update metrics
            self.metrics.last_disconnect_time = datetime.utcnow()

            logger.info("Disconnected from FXCM bridge service")

        except Exception as e:
            logger.error(f"Error during disconnect: {e}")

    async def submit_order(self, order: NewOrderSingle) -> str:
        """Submit order to FXCM.

        Args:
            order: FIX NewOrderSingle message.

        Returns:
            Order ID from broker.

        Raises:
            Exception: If order submission fails.
        """
        if not self.session:
            raise Exception("Not connected to bridge service")

        try:
            # Build FIX message
            fix_message = self.fix_builder.build(order)

            # Submit to bridge
            submit_url = urljoin(self.bridge_url, "/orders")
            payload = {"fix_message": fix_message, "correlation_id": order.cl_ord_id}

            async with self.session.post(submit_url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Order submission failed: {error_text}")

                result = await response.json()

                if not result.get("success"):
                    raise Exception(result.get("message", "Unknown error"))

                # Get order ID from bridge
                bridge_order_id = result.get("order_id")
                if not bridge_order_id:
                    raise Exception("No order ID returned from bridge")

                # Track order
                self.active_orders[order.cl_ord_id] = {
                    "bridge_order_id": bridge_order_id,
                    "order": order,
                    "status": "Submitted",
                    "timestamp": datetime.utcnow(),
                }
                self.order_map[order.cl_ord_id] = bridge_order_id

                # Process initial execution report if provided
                if result.get("execution_report"):
                    await self._process_execution_report(result["execution_report"])

                # Update metrics
                self.metrics.total_orders += 1

                logger.info(
                    f"Order submitted successfully: {order.cl_ord_id} -> {bridge_order_id}"
                )
                return bridge_order_id

        except Exception as e:
            logger.error(f"Error submitting order: {e}")
            self.metrics.failed_orders += 1
            raise

    async def cancel_order(self, cancel_request: OrderCancelRequest) -> bool:
        """Cancel order on FXCM.

        Args:
            cancel_request: FIX OrderCancelRequest message.

        Returns:
            True if cancellation successful.
        """
        if not self.session:
            logger.error("Not connected to bridge service")
            return False

        try:
            # Get bridge order ID
            orig_cl_ord_id = cancel_request.orig_cl_ord_id
            bridge_order_id = self.order_map.get(orig_cl_ord_id)

            if not bridge_order_id:
                logger.warning(f"Order not found for cancellation: {orig_cl_ord_id}")
                return False

            # Cancel via bridge
            cancel_url = urljoin(self.bridge_url, f"/orders/{bridge_order_id}")

            async with self.session.delete(cancel_url) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Order cancellation failed: {error_text}")
                    return False

                result = await response.json()

                if result.get("success"):
                    # Update order status
                    if orig_cl_ord_id in self.active_orders:
                        self.active_orders[orig_cl_ord_id]["status"] = "Cancelled"

                    self.metrics.cancelled_orders += 1
                    logger.info(f"Order cancelled successfully: {orig_cl_ord_id}")
                    return True
                else:
                    logger.error(f"Order cancellation failed: {result.get('message')}")
                    return False

        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False

    async def modify_order(self, modify_request: FIXMessage) -> bool:
        """Modify order on FXCM.

        Note: FXCM may have limitations on order modifications.

        Args:
            modify_request: Order modification request.

        Returns:
            True if modification successful.
        """
        logger.warning("Order modification not fully implemented for FXCM")
        return False

    async def get_order_status(self, cl_ord_id: str) -> Optional[ExecutionReport]:
        """Get current order status.

        Args:
            cl_ord_id: Client order ID.

        Returns:
            ExecutionReport with current status, or None if not found.
        """
        if not self.session:
            return None

        try:
            # Get bridge order ID
            bridge_order_id = self.order_map.get(cl_ord_id)
            if not bridge_order_id:
                return None

            # Query bridge
            status_url = urljoin(self.bridge_url, f"/orders/{bridge_order_id}")

            async with self.session.get(status_url) as response:
                if response.status == 404:
                    return None
                elif response.status != 200:
                    logger.error(f"Failed to get order status: {response.status}")
                    return None

                order_data = await response.json()

                # Create execution report
                # Note: This is simplified - actual implementation would parse
                # more detailed status from bridge
                order_info = self.active_orders.get(cl_ord_id, {})
                original_order = order_info.get("order")

                if original_order:
                    # Create basic execution report
                    exec_report = ExecutionReport(
                        order_id=bridge_order_id,
                        cl_ord_id=cl_ord_id,
                        exec_id=f"STATUS_{bridge_order_id}_{int(datetime.utcnow().timestamp())}",
                        exec_type=ExecType.ORDER_STATUS,
                        ord_status=self._map_order_status(
                            order_data.get("status", "Unknown")
                        ),
                        symbol=original_order.symbol,
                        side=original_order.side,
                        order_qty=original_order.order_qty,
                        transact_time=datetime.utcnow(),
                    )

                    return exec_report

        except Exception as e:
            logger.error(f"Error getting order status: {e}")

        return None

    async def subscribe_market_data(self, symbols: List[str]) -> bool:
        """Subscribe to market data for symbols.

        Args:
            symbols: List of symbols to subscribe to.

        Returns:
            True if subscription successful.
        """
        if not self.session:
            return False

        try:
            # Subscribe via bridge
            subscribe_url = urljoin(self.bridge_url, "/market-data/subscribe")
            payload = {"symbols": symbols, "subscribe": True}

            async with self.session.post(subscribe_url, json=payload) as response:
                if response.status != 200:
                    logger.error(f"Market data subscription failed: {response.status}")
                    return False

                result = await response.json()

                if result.get("success"):
                    logger.info(f"Subscribed to market data for: {symbols}")
                    return True
                else:
                    logger.error(
                        f"Market data subscription failed: {result.get('message')}"
                    )
                    return False

        except Exception as e:
            logger.error(f"Error subscribing to market data: {e}")
            return False

    async def unsubscribe_market_data(self, symbols: List[str]) -> bool:
        """Unsubscribe from market data.

        Args:
            symbols: List of symbols to unsubscribe from.

        Returns:
            True if unsubscription successful.
        """
        if not self.session:
            return False

        try:
            # Unsubscribe via bridge
            subscribe_url = urljoin(self.bridge_url, "/market-data/subscribe")
            payload = {"symbols": symbols, "subscribe": False}

            async with self.session.post(subscribe_url, json=payload) as response:
                if response.status != 200:
                    logger.error(
                        f"Market data unsubscription failed: {response.status}"
                    )
                    return False

                logger.info(f"Unsubscribed from market data for: {symbols}")
                return True

        except Exception as e:
            logger.error(f"Error unsubscribing from market data: {e}")
            return False

    async def _monitor_bridge(self) -> None:
        """Monitor bridge connection and poll for updates."""
        poll_interval = 5  # seconds

        while True:
            try:
                # Check bridge status
                status_url = urljoin(self.bridge_url, "/status")

                async with self.session.get(status_url) as response:
                    if response.status == 200:
                        status_data = await response.json()
                        self.bridge_connected = status_data.get("connected", False)
                        self.last_heartbeat = datetime.utcnow()

                        # Update connection status
                        if self.bridge_connected:
                            if self.connection.status != ConnectionStatus.READY:
                                self.connection.status = ConnectionStatus.READY
                                logger.info("Bridge connection restored")
                        else:
                            if self.connection.status == ConnectionStatus.READY:
                                self.connection.status = ConnectionStatus.CONNECTED
                                logger.warning("Bridge lost connection to FXCM")
                    else:
                        logger.warning(f"Bridge status check failed: {response.status}")

                # Poll for order updates
                # In a production system, this would be replaced with
                # WebSocket or Server-Sent Events for real-time updates
                for cl_ord_id, order_info in self.active_orders.items():
                    if order_info["status"] not in ["Filled", "Cancelled", "Rejected"]:
                        status = await self.get_order_status(cl_ord_id)
                        if status:
                            # Process any status changes
                            pass

                await asyncio.sleep(poll_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in bridge monitor: {e}")
                await asyncio.sleep(poll_interval)

    async def _process_execution_report(self, fix_message: str) -> None:
        """Process execution report from bridge.

        Args:
            fix_message: FIX format execution report.
        """
        try:
            # Parse FIX message
            exec_report = self.fix_parser.parse(fix_message)

            if isinstance(exec_report, ExecutionReport):
                # Update order tracking
                cl_ord_id = exec_report.cl_ord_id
                if cl_ord_id in self.active_orders:
                    self.active_orders[cl_ord_id][
                        "status"
                    ] = exec_report.ord_status.name

                # TODO: Forward to message queue or callback
                logger.info(f"Processed execution report for order: {cl_ord_id}")

        except Exception as e:
            logger.error(f"Error processing execution report: {e}")

    def _map_order_status(self, bridge_status: str) -> OrdStatus:
        """Map bridge order status to FIX OrdStatus.

        Args:
            bridge_status: Status from bridge service.

        Returns:
            FIX order status.
        """
        from ...fix.messages.base import OrdStatus

        status_map = {
            "Executing": OrdStatus.NEW,
            "Executed": OrdStatus.FILLED,
            "Cancelled": OrdStatus.CANCELED,
            "Rejected": OrdStatus.REJECTED,
            "Expired": OrdStatus.EXPIRED,
            "PartiallyFilled": OrdStatus.PARTIALLY_FILLED,
        }

        return status_map.get(bridge_status, OrdStatus.NEW)
