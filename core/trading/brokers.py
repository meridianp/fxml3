"""
Broker Integration and Smart Order Routing for FXML4

TDD-driven implementation of broker adapters and smart routing.
Following Green phase - minimal implementation to pass tests.
"""

import asyncio
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from core.trading.orders import Order, OrderSide, OrderType


class BrokerStatus(str, Enum):
    """Broker connection status enumeration."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class BrokerAdapter(ABC):
    """Base class for broker adapters."""

    def __init__(
        self,
        broker_id: str,
        heartbeat_interval: int = 30,
    ):
        """Initialize broker adapter."""
        self.broker_id = broker_id
        self.status = BrokerStatus.DISCONNECTED
        self.heartbeat_interval = heartbeat_interval

        # Connection tracking
        self.connected_at: Optional[datetime] = None
        self.disconnected_at: Optional[datetime] = None
        self.last_heartbeat: Optional[datetime] = None
        self.last_error: Optional[str] = None

        # Heartbeat task
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def connect(self) -> Dict[str, Any]:
        """Connect to broker."""
        try:
            self.status = BrokerStatus.CONNECTING
            await self._connect()
            self.status = BrokerStatus.CONNECTED
            self.connected_at = datetime.now()
            self.last_heartbeat = datetime.now()

            # Start heartbeat monitoring
            if self.heartbeat_interval:
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            return {"status": "connected", "broker_id": self.broker_id}
        except Exception as e:
            self.status = BrokerStatus.ERROR
            self.last_error = str(e)
            return {"status": "error", "broker_id": self.broker_id, "error": str(e)}

    async def disconnect(self) -> Dict[str, Any]:
        """Disconnect from broker."""
        # Cancel heartbeat task
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

        await self._disconnect()
        self.status = BrokerStatus.DISCONNECTED
        self.disconnected_at = datetime.now()

        return {"status": "disconnected", "broker_id": self.broker_id}

    async def _heartbeat_loop(self):
        """Monitor connection with heartbeat."""
        while self.status == BrokerStatus.CONNECTED:
            await asyncio.sleep(self.heartbeat_interval)
            self.last_heartbeat = datetime.now()
            # Here we could add actual heartbeat check to broker

    async def _connect(self):
        """Broker-specific connection implementation."""
        # Default implementation (override in subclasses)
        pass

    async def _disconnect(self):
        """Broker-specific disconnection implementation."""
        # Default implementation (override in subclasses)
        pass

    async def submit_order(self, order: Order) -> Dict[str, Any]:
        """Submit order to broker."""
        if self.status != BrokerStatus.CONNECTED:
            raise Exception(f"Broker {self.broker_id} not connected")

        # Generate broker order ID
        broker_order_id = f"{self.broker_id}{order.order_id[:8]}"

        # Default implementation returns accepted
        return {
            "status": "accepted",
            "broker_order_id": broker_order_id,
            "timestamp": datetime.now().isoformat(),
        }

    async def cancel_order(self, broker_order_id: str) -> Dict[str, Any]:
        """Cancel order at broker."""
        if self.status != BrokerStatus.CONNECTED:
            raise Exception(f"Broker {self.broker_id} not connected")

        return {
            "status": "cancelled",
            "broker_order_id": broker_order_id,
            "timestamp": datetime.now().isoformat(),
        }

    async def get_order_status(self, broker_order_id: str) -> Dict[str, Any]:
        """Get order status from broker."""
        if self.status != BrokerStatus.CONNECTED:
            raise Exception(f"Broker {self.broker_id} not connected")

        # Default implementation
        return {
            "broker_order_id": broker_order_id,
            "state": "submitted",
            "filled_quantity": 0,
            "average_fill_price": None,
            "timestamp": datetime.now().isoformat(),
        }


class IBAdapter(BrokerAdapter):
    """Interactive Brokers adapter."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 1,
        **kwargs,
    ):
        """Initialize IB adapter."""
        super().__init__(broker_id="IB", **kwargs)
        self.host = host
        self.port = port
        self.client_id = client_id

    def create_contract(self, order: Order) -> Dict[str, Any]:
        """Create IB contract from order."""
        # Parse forex symbol
        symbol_parts = order.symbol.split("/")
        if len(symbol_parts) != 2:
            raise ValueError(f"Invalid forex symbol: {order.symbol}")

        base_currency = symbol_parts[0]
        quote_currency = symbol_parts[1]

        return {
            "symbol": base_currency,
            "currency": quote_currency,
            "sec_type": "CASH",
            "exchange": "IDEALPRO",
        }

    def create_ib_order(self, order: Order) -> Dict[str, Any]:
        """Create IB order from internal order."""
        # Map order side
        action = "BUY" if order.side == OrderSide.BUY else "SELL"

        # Map order type
        order_type_map = {
            OrderType.MARKET: "MKT",
            OrderType.LIMIT: "LMT",
            OrderType.STOP: "STP",
            OrderType.STOP_LIMIT: "STP LMT",
        }
        ib_order_type = order_type_map.get(order.order_type, "MKT")

        ib_order = {
            "action": action,
            "quantity": order.quantity,
            "order_type": ib_order_type,
        }

        # Add price fields
        if order.limit_price:
            ib_order["limit_price"] = float(order.limit_price)
        if order.stop_price:
            ib_order["stop_price"] = float(order.stop_price)

        return ib_order


@dataclass
class BrokerConfig:
    """Configuration for a broker in the router."""

    broker: BrokerAdapter
    priority: int = 1
    active: bool = True
    order_count: int = 0
    error_count: int = 0
    last_error: Optional[datetime] = None


class SmartOrderRouter:
    """Smart order router for broker selection and failover."""

    def __init__(
        self,
        load_balance: bool = False,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: int = 300,  # 5 minutes
    ):
        """Initialize smart order router."""
        self.brokers: Dict[str, BrokerConfig] = {}
        self.load_balance = load_balance
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout

        # Symbol preferences
        self.symbol_preferences: Dict[str, str] = {}

        # Circuit breaker state
        self.circuit_breaker_state: Dict[str, datetime] = {}

    async def add_broker(self, broker: BrokerAdapter, priority: int = 1):
        """Add a broker to the router."""
        config = BrokerConfig(broker=broker, priority=priority)
        self.brokers[broker.broker_id] = config

    def get_broker(self, broker_id: str) -> Optional[BrokerAdapter]:
        """Get broker by ID."""
        config = self.brokers.get(broker_id)
        return config.broker if config else None

    def set_symbol_preference(self, symbol: str, broker_id: str):
        """Set preferred broker for a symbol."""
        self.symbol_preferences[symbol] = broker_id

    def is_circuit_open(self, broker_id: str) -> bool:
        """Check if circuit breaker is open for a broker."""
        if broker_id not in self.circuit_breaker_state:
            return False

        opened_at = self.circuit_breaker_state[broker_id]
        elapsed = (datetime.now() - opened_at).total_seconds()

        if elapsed > self.circuit_breaker_timeout:
            # Circuit breaker timeout expired, close it
            del self.circuit_breaker_state[broker_id]
            return False

        return True

    def _open_circuit(self, broker_id: str):
        """Open circuit breaker for a broker."""
        self.circuit_breaker_state[broker_id] = datetime.now()

    async def route_order(self, order: Order) -> Dict[str, Any]:
        """Route order to appropriate broker."""
        # Check symbol preference
        if order.symbol in self.symbol_preferences:
            preferred_broker_id = self.symbol_preferences[order.symbol]
            config = self.brokers.get(preferred_broker_id)

            if config and config.broker.status == BrokerStatus.CONNECTED:
                if not self.is_circuit_open(preferred_broker_id):
                    try:
                        result = await config.broker.submit_order(order)
                        result["broker_id"] = preferred_broker_id
                        config.order_count += 1
                        return result
                    except Exception as e:
                        config.error_count += 1
                        config.last_error = datetime.now()

                        if config.error_count >= self.circuit_breaker_threshold:
                            self._open_circuit(preferred_broker_id)

        # Get available brokers
        available_brokers = [
            (broker_id, config)
            for broker_id, config in self.brokers.items()
            if config.active
            and config.broker.status == BrokerStatus.CONNECTED
            and not self.is_circuit_open(broker_id)
        ]

        if not available_brokers:
            raise Exception("No available brokers")

        # Sort by priority (lower number = higher priority)
        available_brokers.sort(key=lambda x: (x[1].priority, x[1].order_count))

        # Load balancing logic
        if self.load_balance and len(available_brokers) > 1:
            # Filter to same priority level
            top_priority = available_brokers[0][1].priority
            same_priority = [
                (bid, cfg)
                for bid, cfg in available_brokers
                if cfg.priority == top_priority
            ]

            if len(same_priority) > 1:
                # Select broker with least orders
                min_orders = min(cfg.order_count for _, cfg in same_priority)
                candidates = [
                    (bid, cfg)
                    for bid, cfg in same_priority
                    if cfg.order_count == min_orders
                ]
                # Random selection among candidates with same order count
                broker_id, config = random.choice(candidates)
            else:
                broker_id, config = same_priority[0]
        else:
            # Use highest priority broker
            broker_id, config = available_brokers[0]

        # Submit order
        try:
            result = await config.broker.submit_order(order)
            result["broker_id"] = broker_id
            config.order_count += 1
            config.error_count = 0  # Reset error count on success
            return result
        except Exception as e:
            config.error_count += 1
            config.last_error = datetime.now()

            if config.error_count >= self.circuit_breaker_threshold:
                self._open_circuit(broker_id)
                raise Exception(f"Circuit breaker open for {broker_id}: {str(e)}")
            raise