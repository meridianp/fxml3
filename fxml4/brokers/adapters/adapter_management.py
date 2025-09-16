"""
Unified Broker Adapter Management System.

This module provides both adapter registration and management functionality,
including dynamic registration, routing, statistics, and unified interfaces
for broker operations.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import Lock
from typing import Any, Callable, Dict, List, Optional, Set, Type

from ...fix.messages.base import FIXMessage
from ...fix.messages.orders import ExecutionReport, NewOrderSingle, OrderCancelRequest
from ..messaging.consumer import BrokerMessageConsumer, MessageHandler
from ..messaging.publisher import BrokerMessagePublisher
from ..messaging.router import MessageRouter, RoutingStrategy
from .base import (
    AdapterConfig,
    BrokerAdapter,
    BrokerConnection,
    ConnectionStatus,
    OrderInfo,
)

logger = logging.getLogger(__name__)


# FIX Broker Profiles
@dataclass
class FIXBrokerProfile:
    """Profile for a FIX broker configuration."""

    name: str
    host: str
    port: int
    sender_comp_id: str
    target_comp_id: str
    fix_version: str = "FIX.4.2"
    use_ssl: bool = False
    heartbeat_interval: int = 30
    features: Dict[str, Any] = None

    def to_adapter_config(self, adapter_id: str) -> AdapterConfig:
        """Convert profile to adapter configuration."""
        return AdapterConfig(
            adapter_id=adapter_id,
            broker_type="fix",
            broker_name=self.name,
            connection_params={
                "host": self.host,
                "port": self.port,
                "use_ssl": self.use_ssl,
                "session": {
                    "sender_comp_id": self.sender_comp_id,
                    "target_comp_id": self.target_comp_id,
                    "fix_version": self.fix_version,
                    "heartbeat_interval": self.heartbeat_interval,
                },
            },
            features=self.features or {},
            enabled=True,
        )


# Pre-configured FIX broker profiles
FIX_BROKER_PROFILES = {
    "currenex": FIXBrokerProfile(
        name="Currenex",
        host="fix.currenex.com",
        port=9876,
        sender_comp_id="FXML4",
        target_comp_id="CURRENEX",
        fix_version="FIX.4.4",
        use_ssl=True,
        features={
            "supports_market_data": True,
            "supports_trading": True,
            "supports_allocations": False,
        },
    ),
    "hotspot": FIXBrokerProfile(
        name="Hotspot FX",
        host="fix.hotspotfx.com",
        port=9000,
        sender_comp_id="FXML4",
        target_comp_id="HOTSPOT",
        fix_version="FIX.4.2",
        use_ssl=True,
        features={
            "supports_market_data": True,
            "supports_trading": True,
            "supports_rfq": True,
        },
    ),
    "integral": FIXBrokerProfile(
        name="Integral",
        host="fix.integral.com",
        port=443,
        sender_comp_id="FXML4",
        target_comp_id="INTEGRAL",
        fix_version="FIX.4.4",
        use_ssl=True,
        heartbeat_interval=20,
        features={
            "supports_market_data": True,
            "supports_trading": True,
            "supports_algo_orders": True,
        },
    ),
    "lmax": FIXBrokerProfile(
        name="LMAX",
        host="fix.lmax.com",
        port=443,
        sender_comp_id="FXML4",
        target_comp_id="LMAX",
        fix_version="FIX.4.4",
        use_ssl=True,
        features={
            "supports_market_data": True,
            "supports_trading": True,
            "supports_market_orders_only": False,
        },
    ),
    "mock": FIXBrokerProfile(
        name="Mock FIX Broker",
        host="localhost",
        port=9876,
        sender_comp_id="FXML4_TEST",
        target_comp_id="MOCK_BROKER",
        fix_version="FIX.4.2",
        use_ssl=False,
        features={
            "mock": True,
            "simulate_fills": True,
            "simulate_rejects": False,
            "fill_delay_ms": 1000,
        },
    ),
}


@dataclass
class AdapterRegistration:
    """Registration information for a broker adapter."""

    adapter_type: str
    adapter_class: Type[BrokerAdapter]
    description: str
    version: str
    supported_features: List[str]
    required_config: List[str]
    optional_config: List[str]

    def validate_config(self, config: AdapterConfig) -> List[str]:
        """Validate configuration for this adapter."""
        errors = []

        # Check adapter type matches
        if config.adapter_type != self.adapter_type:
            errors.append(
                f"Config adapter_type '{config.adapter_type}' does not match registration '{self.adapter_type}'"
            )

        # Check required configuration keys
        for required_key in self.required_config:
            if (
                required_key not in config.connection_params
                and required_key not in config.authentication
            ):
                errors.append(f"Missing required configuration: {required_key}")

        return errors


@dataclass
class AdapterStats:
    """Statistics for broker adapter."""

    adapter_type: str
    orders_submitted: int = 0
    orders_filled: int = 0
    orders_rejected: int = 0
    orders_cancelled: int = 0
    total_volume: float = 0.0
    avg_latency_ms: float = 0.0
    last_order_time: Optional[datetime] = None
    error_count: int = 0
    uptime_seconds: float = 0.0


class BrokerAdapterRegistry:
    """Registry for broker adapter classes."""

    def __init__(self):
        """Initialize the adapter registry."""
        self._adapters: Dict[str, AdapterRegistration] = {}
        self._aliases: Dict[str, str] = {}  # alias -> adapter_type
        self._lock = Lock()

        logger.info("Initialized broker adapter registry")

    def register(
        self,
        adapter_type: str,
        adapter_class: Type[BrokerAdapter],
        description: str = "",
        version: str = "1.0.0",
        supported_features: Optional[List[str]] = None,
        required_config: Optional[List[str]] = None,
        optional_config: Optional[List[str]] = None,
        aliases: Optional[List[str]] = None,
    ) -> None:
        """Register a broker adapter class."""
        with self._lock:
            if adapter_type in self._adapters:
                logger.warning(
                    "Overriding existing adapter registration: %s", adapter_type
                )

            # Validate adapter class
            if not issubclass(adapter_class, BrokerAdapter):
                raise ValueError(
                    f"Adapter class must inherit from BrokerAdapter: {adapter_class}"
                )

            # Create registration
            registration = AdapterRegistration(
                adapter_type=adapter_type,
                adapter_class=adapter_class,
                description=description or f"{adapter_type} broker adapter",
                version=version,
                supported_features=supported_features or [],
                required_config=required_config or [],
                optional_config=optional_config or [],
            )

            self._adapters[adapter_type] = registration

            # Register aliases
            if aliases:
                for alias in aliases:
                    if alias in self._aliases:
                        logger.warning("Overriding existing alias: %s", alias)
                    self._aliases[alias] = adapter_type

            logger.info(
                "Registered adapter: %s (%s) v%s", adapter_type, description, version
            )

    def get_adapter_class(self, adapter_type: str) -> Optional[Type[BrokerAdapter]]:
        """Get adapter class by type."""
        with self._lock:
            # Check direct registration
            registration = self._adapters.get(adapter_type)
            if registration:
                return registration.adapter_class

            # Check aliases
            actual_type = self._aliases.get(adapter_type)
            if actual_type:
                registration = self._adapters.get(actual_type)
                if registration:
                    return registration.adapter_class

            return None

    def create_adapter(
        self, adapter_type: str, config: AdapterConfig
    ) -> Optional[BrokerAdapter]:
        """Create adapter instance from configuration."""
        registration = self.get_registration(adapter_type)
        if not registration:
            logger.error("Adapter type not registered: %s", adapter_type)
            return None

        # Validate configuration
        errors = registration.validate_config(config)
        if errors:
            logger.error(
                "Configuration validation failed for %s: %s", adapter_type, errors
            )
            return None

        try:
            # Create adapter instance
            adapter = registration.adapter_class(config)
            logger.info("Created adapter instance: %s", adapter_type)
            return adapter

        except Exception as e:
            logger.error("Failed to create adapter %s: %s", adapter_type, e)
            return None

    def get_registration(self, adapter_type: str) -> Optional[AdapterRegistration]:
        """Get registration information for adapter."""
        with self._lock:
            # Check direct registration
            registration = self._adapters.get(adapter_type)
            if registration:
                return registration

            # Check aliases
            actual_type = self._aliases.get(adapter_type)
            if actual_type:
                return self._adapters.get(actual_type)

            return None

    def list_adapters(self) -> List[str]:
        """Get list of registered adapter types."""
        with self._lock:
            return list(self._adapters.keys())

    def register_standard_adapters(self) -> None:
        """Register standard adapter types with default configurations."""
        # Import adapter classes here to avoid circular imports
        try:
            from .fix_rabbitmq_adapter import FixRabbitMQAdapter
            from .fxcm_rabbitmq_adapter import FXCMRabbitMQAdapter
            from .ib_rabbitmq_adapter import IBRabbitMQAdapter
            from .manual_rabbitmq_adapter import ManualRabbitMQAdapter
        except ImportError as e:
            logger.warning(f"Some adapter classes not available: {e}")
            return

        # Register IB adapter
        self.register(
            adapter_type="ib",
            adapter_class=IBRabbitMQAdapter,
            description="Interactive Brokers TWS/Gateway adapter with FIX protocol support",
            version="1.0.0",
            supported_features=[
                "order_management",
                "market_data",
                "portfolio_queries",
                "real_time_execution",
                "order_modification",
                "historical_data",
                "account_management",
            ],
            required_config=["host", "port", "client_id"],
            optional_config=["account_id", "rabbitmq", "timeout", "reconnect_attempts"],
            aliases=["interactive_brokers", "ibkr", "tws"],
        )

        # Register FXCM adapter
        self.register(
            adapter_type="fxcm",
            adapter_class=FXCMRabbitMQAdapter,
            description="FXCM ForexConnect adapter with Docker isolation",
            version="1.0.0",
            supported_features=[
                "order_management",
                "market_data",
                "fx_instruments",
                "docker_isolation",
                "bridge_architecture",
            ],
            required_config=["bridge_url"],
            optional_config=["api_key", "rabbitmq", "timeout", "reconnect_attempts"],
            aliases=["forexconnect", "forex_connect"],
        )

        # Register Manual adapter
        self.register(
            adapter_type="manual",
            adapter_class=ManualRabbitMQAdapter,
            description="Manual execution adapter with RabbitMQ message queue integration",
            version="1.0.0",
            supported_features=[
                "order_management",
                "manual_review",
                "compliance_override",
                "human_in_the_loop",
                "message_queue",
            ],
            required_config=["review_interface"],
            optional_config=["auto_approve_limit", "notification_email", "rabbitmq"],
            aliases=["manual_rabbitmq", "human_approval"],
        )

        # Register FIX adapter
        self.register(
            adapter_type="fix",
            adapter_class=FixRabbitMQAdapter,
            description="Native FIX protocol adapter with message queue support",
            version="1.0.0",
            supported_features=[
                "order_management",
                "market_data",
                "fix_protocol",
                "low_latency",
                "institutional_grade",
                "message_queue",
            ],
            required_config=["host", "port", "sender_comp_id", "target_comp_id"],
            optional_config=[
                "fix_version",
                "use_ssl",
                "heartbeat_interval",
                "rabbitmq",
            ],
            aliases=["fix_rabbitmq", "native_fix"],
        )


class BrokerAdapterManager(MessageHandler):
    """Manager for multiple broker adapters.

    This class provides a unified interface for managing multiple
    broker adapters, routing orders, and handling responses.
    """

    def __init__(
        self,
        message_router: MessageRouter,
        publisher: Optional[BrokerMessagePublisher] = None,
        consumer: Optional[BrokerMessageConsumer] = None,
        registry: Optional[BrokerAdapterRegistry] = None,
    ):
        """Initialize the adapter manager.

        Args:
            message_router: Message routing system
            publisher: Message publisher for outbound messages
            consumer: Message consumer for inbound messages
            registry: Adapter registry (creates new if None)
        """
        self.message_router = message_router
        self.publisher = publisher
        self.consumer = consumer
        self.registry = registry or BrokerAdapterRegistry()

        # Active adapters
        self.adapters: Dict[str, BrokerAdapter] = {}
        self.adapter_stats: Dict[str, AdapterStats] = {}

        # Connection tracking
        self.connections: Dict[str, BrokerConnection] = {}

        # Order tracking
        self.pending_orders: Dict[str, OrderInfo] = {}
        self.order_history: List[OrderInfo] = []

        # Event callbacks
        self.order_callbacks: Dict[str, Callable] = {}

        # Health monitoring
        self.health_check_interval = 30  # seconds
        self.last_health_check = datetime.now()

        # Lock for thread safety
        self._lock = Lock()

        logger.info("Initialized broker adapter manager")

    async def start(self):
        """Start the adapter manager."""
        logger.info("Starting broker adapter manager")

        # Register standard adapters
        self.registry.register_standard_adapters()

        # Start message consumer if available
        if self.consumer:
            await self.consumer.start()
            self.consumer.register_handler(self)

        # Start health monitoring
        asyncio.create_task(self._health_monitor())

        logger.info("Broker adapter manager started")

    async def stop(self):
        """Stop the adapter manager."""
        logger.info("Stopping broker adapter manager")

        # Stop all adapters
        for adapter in self.adapters.values():
            try:
                await adapter.disconnect()
            except Exception as e:
                logger.error(f"Error stopping adapter: {e}")

        # Stop message consumer
        if self.consumer:
            await self.consumer.stop()

        logger.info("Broker adapter manager stopped")

    async def add_adapter(self, adapter_id: str, config: AdapterConfig) -> bool:
        """Add a new adapter."""
        with self._lock:
            if adapter_id in self.adapters:
                logger.warning(f"Adapter {adapter_id} already exists")
                return False

            # Create adapter instance
            adapter = self.registry.create_adapter(config.adapter_type, config)
            if not adapter:
                logger.error(f"Failed to create adapter for {adapter_id}")
                return False

            # Add to active adapters
            self.adapters[adapter_id] = adapter
            self.adapter_stats[adapter_id] = AdapterStats(
                adapter_type=config.adapter_type
            )

            logger.info(f"Added adapter: {adapter_id} ({config.adapter_type})")
            return True

    async def remove_adapter(self, adapter_id: str) -> bool:
        """Remove an adapter."""
        with self._lock:
            if adapter_id not in self.adapters:
                logger.warning(f"Adapter {adapter_id} not found")
                return False

            # Disconnect adapter
            adapter = self.adapters[adapter_id]
            try:
                await adapter.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting adapter {adapter_id}: {e}")

            # Remove from tracking
            del self.adapters[adapter_id]
            del self.adapter_stats[adapter_id]

            logger.info(f"Removed adapter: {adapter_id}")
            return True

    async def submit_order(
        self, order: NewOrderSingle, adapter_id: Optional[str] = None
    ) -> str:
        """Submit an order through the appropriate adapter."""
        # Select adapter using routing strategy
        if not adapter_id:
            adapter_id = self.message_router.route_message(order)

        if not adapter_id or adapter_id not in self.adapters:
            raise ValueError(f"No suitable adapter found for order: {adapter_id}")

        adapter = self.adapters[adapter_id]

        # Create order info
        order_info = OrderInfo(
            order_id=order.cl_ord_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.order_qty,
            order_type=order.ord_type,
            price=getattr(order, "price", None),
            status="PENDING",
            adapter_id=adapter_id,
            timestamp=datetime.now(),
        )

        # Track order
        with self._lock:
            self.pending_orders[order.cl_ord_id] = order_info

            # Update stats
            stats = self.adapter_stats[adapter_id]
            stats.orders_submitted += 1
            stats.last_order_time = datetime.now()

        try:
            # Submit to adapter
            result = await adapter.submit_order(order)

            # Publish order event if publisher available
            if self.publisher:
                await self.publisher.publish_order_event(order_info)

            return result

        except Exception as e:
            logger.error(f"Order submission failed: {e}")

            # Update order status
            with self._lock:
                order_info.status = "REJECTED"
                order_info.error_message = str(e)

                # Update stats
                stats = self.adapter_stats[adapter_id]
                stats.orders_rejected += 1
                stats.error_count += 1

            raise

    async def cancel_order(
        self, order_id: str, adapter_id: Optional[str] = None
    ) -> bool:
        """Cancel an order."""
        # Find order if adapter not specified
        if not adapter_id:
            order_info = self.pending_orders.get(order_id)
            if order_info:
                adapter_id = order_info.adapter_id

        if not adapter_id or adapter_id not in self.adapters:
            logger.error(f"Cannot find adapter for order cancellation: {order_id}")
            return False

        adapter = self.adapters[adapter_id]

        try:
            # Create cancel request
            cancel_request = OrderCancelRequest(
                orig_cl_ord_id=order_id,
                cl_ord_id=f"CANCEL_{order_id}",
                symbol=self.pending_orders[order_id].symbol,
                side=self.pending_orders[order_id].side,
                transact_time=datetime.now(),
            )

            result = await adapter.cancel_order(cancel_request)

            # Update stats
            with self._lock:
                stats = self.adapter_stats[adapter_id]
                stats.orders_cancelled += 1

            return result

        except Exception as e:
            logger.error(f"Order cancellation failed: {e}")

            # Update stats
            with self._lock:
                stats = self.adapter_stats[adapter_id]
                stats.error_count += 1

            return False

    async def handle_message(self, message: Any) -> None:
        """Handle incoming messages."""
        if isinstance(message, ExecutionReport):
            await self._handle_execution_report(message)
        elif isinstance(message, FIXMessage):
            await self._handle_fix_message(message)
        else:
            logger.warning(f"Unhandled message type: {type(message)}")

    async def _handle_execution_report(self, execution_report: ExecutionReport):
        """Handle execution report from adapter."""
        order_id = execution_report.cl_ord_id

        with self._lock:
            if order_id in self.pending_orders:
                order_info = self.pending_orders[order_id]

                # Update order status
                order_info.status = execution_report.ord_status
                order_info.filled_quantity = execution_report.cum_qty
                order_info.avg_price = execution_report.avg_px
                order_info.last_update = datetime.now()

                # Update stats
                adapter_id = order_info.adapter_id
                stats = self.adapter_stats[adapter_id]

                if execution_report.ord_status == "FILLED":
                    stats.orders_filled += 1
                    stats.total_volume += execution_report.last_qty

                    # Move to history
                    self.order_history.append(order_info)
                    del self.pending_orders[order_id]

                elif execution_report.ord_status == "REJECTED":
                    stats.orders_rejected += 1

                    # Move to history
                    self.order_history.append(order_info)
                    del self.pending_orders[order_id]

        # Publish execution event
        if self.publisher:
            await self.publisher.publish_execution_event(execution_report)

        # Call registered callbacks
        callback = self.order_callbacks.get(order_id)
        if callback:
            await callback(execution_report)

    async def _handle_fix_message(self, message: FIXMessage):
        """Handle general FIX messages."""
        # Route to appropriate adapter
        adapter_id = self.message_router.route_message(message)

        if adapter_id and adapter_id in self.adapters:
            adapter = self.adapters[adapter_id]
            await adapter.handle_message(message)

    def get_adapter_stats(
        self, adapter_id: Optional[str] = None
    ) -> Dict[str, AdapterStats]:
        """Get adapter statistics."""
        with self._lock:
            if adapter_id:
                return (
                    {adapter_id: self.adapter_stats.get(adapter_id)}
                    if adapter_id in self.adapter_stats
                    else {}
                )
            return self.adapter_stats.copy()

    def get_order_status(self, order_id: str) -> Optional[OrderInfo]:
        """Get order status."""
        with self._lock:
            # Check pending orders
            if order_id in self.pending_orders:
                return self.pending_orders[order_id]

            # Check history
            for order_info in self.order_history:
                if order_info.order_id == order_id:
                    return order_info

            return None

    def register_order_callback(self, order_id: str, callback: Callable):
        """Register callback for order updates."""
        self.order_callbacks[order_id] = callback

    async def _health_monitor(self):
        """Monitor adapter health."""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)

                current_time = datetime.now()

                with self._lock:
                    for adapter_id, adapter in self.adapters.items():
                        try:
                            # Check adapter health
                            is_healthy = await adapter.health_check()

                            if not is_healthy:
                                logger.warning(
                                    f"Adapter {adapter_id} health check failed"
                                )

                                # Update stats
                                stats = self.adapter_stats[adapter_id]
                                stats.error_count += 1

                        except Exception as e:
                            logger.error(f"Health check error for {adapter_id}: {e}")

                self.last_health_check = current_time

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitor error: {e}")


# Global registry instance
_global_registry = BrokerAdapterRegistry()


def get_global_registry() -> BrokerAdapterRegistry:
    """Get the global adapter registry instance."""
    return _global_registry


def register_adapter(
    adapter_type: str, adapter_class: Type[BrokerAdapter], **kwargs
) -> None:
    """Register adapter in global registry."""
    _global_registry.register(adapter_type, adapter_class, **kwargs)


def create_adapter(adapter_type: str, config: AdapterConfig) -> Optional[BrokerAdapter]:
    """Create adapter using global registry."""
    return _global_registry.create_adapter(adapter_type, config)


def get_fix_broker_profile(broker_name: str) -> Optional[FIXBrokerProfile]:
    """Get pre-configured FIX broker profile."""
    return FIX_BROKER_PROFILES.get(broker_name.lower())


def create_fix_adapter_config(
    adapter_id: str,
    broker_name: str,
    custom_params: Optional[Dict[str, Any]] = None,
    rabbitmq_config: Optional[Dict[str, Any]] = None,
) -> AdapterConfig:
    """Create FIX adapter configuration."""
    # Check for pre-configured profile
    profile = get_fix_broker_profile(broker_name)

    if profile:
        config = profile.to_adapter_config(adapter_id)

        # Apply custom parameters
        if custom_params:
            config.connection_params.update(custom_params)

        # Add RabbitMQ config if provided
        if rabbitmq_config:
            config.connection_params["rabbitmq"] = rabbitmq_config

        return config

    else:
        # Create custom configuration
        if not custom_params:
            raise ValueError(
                f"Unknown broker profile '{broker_name}' and no custom parameters provided"
            )

        return AdapterConfig(
            adapter_id=adapter_id,
            broker_type="fix",
            broker_name=broker_name,
            connection_params=(
                {**custom_params, "rabbitmq": rabbitmq_config}
                if rabbitmq_config
                else custom_params
            ),
            features={},
            enabled=True,
        )


def list_fix_broker_profiles() -> Dict[str, str]:
    """List available FIX broker profiles."""
    return {
        name: f"{profile.name} ({profile.fix_version})"
        for name, profile in FIX_BROKER_PROFILES.items()
    }


# Export main classes
__all__ = [
    "BrokerAdapterManager",
    "BrokerAdapterRegistry",
    "AdapterRegistration",
    "AdapterStats",
    "FIXBrokerProfile",
    "FIX_BROKER_PROFILES",
    "get_global_registry",
    "register_adapter",
    "create_adapter",
    "get_fix_broker_profile",
    "create_fix_adapter_config",
    "list_fix_broker_profiles",
]
