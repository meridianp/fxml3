#!/usr/bin/env python3
"""
Broker Mock Fixtures
====================

Provides mock broker adapters and responses for testing trading systems
without requiring actual broker connections.
"""

import asyncio
import json
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

import numpy as np


class OrderStatus(Enum):
    """Order status enumeration."""

    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass
class MockOrderResponse:
    """Mock order response structure."""

    order_id: str
    status: OrderStatus
    filled_quantity: float = 0
    remaining_quantity: float = 0
    average_price: float = 0
    commission: float = 0
    timestamp: datetime = field(default_factory=datetime.now)
    rejection_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MockPosition:
    """Mock position structure."""

    symbol: str
    quantity: float
    side: str
    average_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    commission: float = 0
    open_time: datetime = field(default_factory=datetime.now)


class MockBrokerAdapter:
    """Base mock broker adapter for testing."""

    def __init__(
        self,
        broker_name: str = "MockBroker",
        latency_ms: int = 50,
        failure_rate: float = 0.0,
        partial_fill_probability: float = 0.2,
        slippage_pips: float = 0.5,
    ):
        """
        Initialize mock broker adapter.

        Args:
            broker_name: Name of the broker
            latency_ms: Simulated network latency in milliseconds
            failure_rate: Probability of order failure (0-1)
            partial_fill_probability: Probability of partial fills
            slippage_pips: Average slippage in pips
        """
        self.broker_name = broker_name
        self.latency_ms = latency_ms
        self.failure_rate = failure_rate
        self.partial_fill_probability = partial_fill_probability
        self.slippage_pips = slippage_pips

        # State tracking
        self.is_connected = True
        self.orders = {}
        self.positions = {}
        self.executions = []
        self.account_balance = 1000000.0
        self.account_equity = 1000000.0
        self.margin_used = 0.0
        self.margin_available = 1000000.0

        # Order ID counter
        self._order_counter = 1000

    async def connect(self) -> bool:
        """Simulate broker connection."""
        await self._simulate_latency()
        self.is_connected = True
        return True

    async def disconnect(self) -> bool:
        """Simulate broker disconnection."""
        self.is_connected = False
        return True

    async def submit_order(self, order: Dict[str, Any]) -> MockOrderResponse:
        """
        Simulate order submission.

        Args:
            order: Order details dictionary

        Returns:
            MockOrderResponse with submission details
        """
        await self._simulate_latency()

        # Check connection
        if not self.is_connected:
            raise ConnectionError(f"{self.broker_name} is not connected")

        # Simulate random failure
        if random.random() < self.failure_rate:
            return MockOrderResponse(
                order_id=self._generate_order_id(),
                status=OrderStatus.REJECTED,
                rejection_reason="Simulated order rejection for testing",
            )

        # Generate order ID
        order_id = self._generate_order_id()

        # Calculate fill price with slippage
        base_price = order.get("price", 1.0850)
        slippage = (random.random() - 0.5) * self.slippage_pips * 0.0001
        fill_price = base_price + slippage

        # Determine if partial fill
        quantity = order.get("quantity", 10000)
        if random.random() < self.partial_fill_probability:
            filled_quantity = quantity * random.uniform(0.3, 0.8)
            status = OrderStatus.PARTIALLY_FILLED
        else:
            filled_quantity = quantity
            status = OrderStatus.FILLED

        # Calculate commission
        commission = filled_quantity * 0.00002  # $2 per 100k

        # Store order
        response = MockOrderResponse(
            order_id=order_id,
            status=status,
            filled_quantity=filled_quantity,
            remaining_quantity=quantity - filled_quantity,
            average_price=fill_price,
            commission=commission,
        )

        self.orders[order_id] = response

        # Update position if filled
        if filled_quantity > 0:
            await self._update_position(order, filled_quantity, fill_price)

        return response

    async def cancel_order(self, order_id: str) -> MockOrderResponse:
        """Simulate order cancellation."""
        await self._simulate_latency()

        if order_id not in self.orders:
            raise ValueError(f"Order {order_id} not found")

        order = self.orders[order_id]

        if order.status in [
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
        ]:
            raise ValueError(f"Cannot cancel order in status {order.status}")

        order.status = OrderStatus.CANCELLED
        order.metadata["cancel_time"] = datetime.now()

        return order

    async def modify_order(
        self, order_id: str, modifications: Dict[str, Any]
    ) -> MockOrderResponse:
        """Simulate order modification."""
        await self._simulate_latency()

        if order_id not in self.orders:
            raise ValueError(f"Order {order_id} not found")

        order = self.orders[order_id]

        if order.status not in [OrderStatus.SUBMITTED, OrderStatus.ACKNOWLEDGED]:
            raise ValueError(f"Cannot modify order in status {order.status}")

        # Apply modifications
        for key, value in modifications.items():
            if key in ["price", "quantity", "stop_loss", "take_profit"]:
                order.metadata[f"modified_{key}"] = value

        order.metadata["modification_time"] = datetime.now()

        return order

    async def get_order_status(self, order_id: str) -> MockOrderResponse:
        """Get order status."""
        await self._simulate_latency()

        if order_id not in self.orders:
            raise ValueError(f"Order {order_id} not found")

        return self.orders[order_id]

    async def get_positions(self) -> List[MockPosition]:
        """Get current positions."""
        await self._simulate_latency()
        return list(self.positions.values())

    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information."""
        await self._simulate_latency()

        return {
            "broker": self.broker_name,
            "account_id": f"{self.broker_name}_TEST_123",
            "balance": self.account_balance,
            "equity": self.account_equity,
            "margin_used": self.margin_used,
            "margin_available": self.margin_available,
            "currency": "USD",
            "leverage": 50,
            "timestamp": datetime.now().isoformat(),
        }

    async def stream_prices(
        self, symbols: List[str], callback: Callable[[Dict[str, Any]], None]
    ) -> None:
        """
        Simulate streaming price data.

        Args:
            symbols: List of symbols to stream
            callback: Callback function for price updates
        """
        while self.is_connected:
            for symbol in symbols:
                # Generate random price
                base_price = 1.0850 if symbol == "EURUSD" else 1.2650
                bid = base_price + (random.random() - 0.5) * 0.001
                ask = bid + 0.0001

                price_data = {
                    "symbol": symbol,
                    "bid": bid,
                    "ask": ask,
                    "timestamp": datetime.now().isoformat(),
                }

                await callback(price_data)

            await asyncio.sleep(0.1)  # Stream every 100ms

    # Helper methods

    def _generate_order_id(self) -> str:
        """Generate unique order ID."""
        self._order_counter += 1
        return f"{self.broker_name}_{self._order_counter}"

    async def _simulate_latency(self) -> None:
        """Simulate network latency."""
        if self.latency_ms > 0:
            await asyncio.sleep(self.latency_ms / 1000.0)

    async def _update_position(
        self, order: Dict[str, Any], quantity: float, price: float
    ) -> None:
        """Update position after fill."""
        symbol = order.get("symbol", "EURUSD")
        side = order.get("side", "BUY")

        if symbol not in self.positions:
            # Create new position
            self.positions[symbol] = MockPosition(
                symbol=symbol,
                quantity=quantity if side == "BUY" else -quantity,
                side=side,
                average_price=price,
                current_price=price,
                unrealized_pnl=0,
                realized_pnl=0,
            )
        else:
            # Update existing position
            pos = self.positions[symbol]

            if (side == "BUY" and pos.quantity > 0) or (
                side == "SELL" and pos.quantity < 0
            ):
                # Adding to position
                total_cost = abs(pos.quantity) * pos.average_price + quantity * price
                pos.quantity += quantity if side == "BUY" else -quantity
                pos.average_price = (
                    total_cost / abs(pos.quantity) if pos.quantity != 0 else price
                )
            else:
                # Reducing or reversing position
                if abs(pos.quantity) >= quantity:
                    # Partial close
                    pnl = (
                        quantity
                        * (price - pos.average_price)
                        * (1 if pos.quantity > 0 else -1)
                    )
                    pos.realized_pnl += pnl
                    pos.quantity += quantity if side == "BUY" else -quantity
                else:
                    # Full close and reverse
                    pnl = (
                        abs(pos.quantity)
                        * (price - pos.average_price)
                        * (1 if pos.quantity > 0 else -1)
                    )
                    pos.realized_pnl += pnl

                    remaining = quantity - abs(pos.quantity)
                    pos.quantity = remaining if side == "BUY" else -remaining
                    pos.average_price = price
                    pos.side = side

            # Remove position if closed
            if abs(pos.quantity) < 0.01:
                del self.positions[symbol]


class MockIBAdapter(MockBrokerAdapter):
    """Mock Interactive Brokers adapter."""

    def __init__(self, **kwargs):
        super().__init__(
            broker_name="InteractiveBrokers", latency_ms=30, slippage_pips=0.3, **kwargs
        )

        # IB-specific features
        self.tws_connected = True
        self.market_data_subscriptions = set()
        self.historical_data_cache = {}

    async def connect_tws(self, client_id: int = 999) -> bool:
        """Simulate TWS connection."""
        await self._simulate_latency()
        self.tws_connected = True
        self.is_connected = True
        return True

    async def request_market_data(
        self, symbol: str, data_type: str = "REALTIME"
    ) -> Dict[str, Any]:
        """Simulate market data request."""
        await self._simulate_latency()

        self.market_data_subscriptions.add(symbol)

        return {
            "symbol": symbol,
            "bid": 1.0850 + random.uniform(-0.001, 0.001),
            "ask": 1.0851 + random.uniform(-0.001, 0.001),
            "last": 1.08505 + random.uniform(-0.001, 0.001),
            "volume": random.randint(1000000, 5000000),
            "timestamp": datetime.now().isoformat(),
        }

    async def request_historical_data(
        self, symbol: str, duration: str = "1 D", bar_size: str = "1 hour"
    ) -> List[Dict[str, Any]]:
        """Simulate historical data request."""
        await self._simulate_latency()

        # Generate mock historical data
        bars = []
        periods = 24 if "D" in duration else 100

        for i in range(periods):
            base_price = 1.0850 + i * 0.0001
            bars.append(
                {
                    "timestamp": (
                        datetime.now() - timedelta(hours=periods - i)
                    ).isoformat(),
                    "open": base_price + random.uniform(-0.0005, 0.0005),
                    "high": base_price + random.uniform(0, 0.001),
                    "low": base_price - random.uniform(0, 0.001),
                    "close": base_price + random.uniform(-0.0005, 0.0005),
                    "volume": random.randint(100000, 500000),
                }
            )

        return bars


class MockFXCMAdapter(MockBrokerAdapter):
    """Mock FXCM adapter."""

    def __init__(self, **kwargs):
        super().__init__(broker_name="FXCM", latency_ms=50, slippage_pips=0.5, **kwargs)

        # FXCM-specific features
        self.forex_connect_session = None
        self.trading_session_id = None

    async def login(
        self, username: str, password: str, connection: str = "Demo"
    ) -> bool:
        """Simulate FXCM login."""
        await self._simulate_latency()

        self.forex_connect_session = f"FXCM_SESSION_{random.randint(1000, 9999)}"
        self.trading_session_id = f"TS_{random.randint(10000, 99999)}"
        self.is_connected = True

        return True

    async def get_offers_table(self) -> List[Dict[str, Any]]:
        """Get available trading instruments."""
        await self._simulate_latency()

        offers = [
            {"symbol": "EUR/USD", "bid": 1.0850, "ask": 1.0851, "pip_cost": 1.0},
            {"symbol": "GBP/USD", "bid": 1.2650, "ask": 1.2652, "pip_cost": 1.0},
            {"symbol": "USD/JPY", "bid": 110.50, "ask": 110.52, "pip_cost": 0.91},
            {"symbol": "AUD/USD", "bid": 0.6850, "ask": 0.6852, "pip_cost": 1.0},
        ]

        return offers

    async def create_market_order(
        self, symbol: str, is_buy: bool, amount: int
    ) -> Dict[str, Any]:
        """Create market order FXCM style."""
        order = {
            "symbol": symbol,
            "side": "BUY" if is_buy else "SELL",
            "quantity": amount,
            "order_type": "MARKET",
        }

        response = await self.submit_order(order)

        return {
            "order_id": response.order_id,
            "status": response.status.value,
            "fill_price": response.average_price,
            "filled_amount": response.filled_quantity,
        }


class MockManualAdapter(MockBrokerAdapter):
    """Mock manual trading adapter for testing user interaction."""

    def __init__(self, **kwargs):
        super().__init__(
            broker_name="Manual",
            latency_ms=100,  # Slower for manual execution
            slippage_pips=1.0,  # Higher slippage for manual
            **kwargs,
        )

        # Manual trading specific
        self.pending_confirmations = {}
        self.auto_confirm = False  # For testing

    async def submit_order(self, order: Dict[str, Any]) -> MockOrderResponse:
        """Submit order for manual confirmation."""
        await self._simulate_latency()

        order_id = self._generate_order_id()

        # Add to pending confirmations
        self.pending_confirmations[order_id] = {
            "order": order,
            "status": "PENDING_CONFIRMATION",
            "created_at": datetime.now(),
        }

        if self.auto_confirm:
            # Auto-confirm for testing
            return await self.confirm_order(order_id)

        # Return pending status
        return MockOrderResponse(
            order_id=order_id,
            status=OrderStatus.PENDING,
            metadata={"requires_confirmation": True},
        )

    async def confirm_order(self, order_id: str) -> MockOrderResponse:
        """Confirm manual order execution."""
        if order_id not in self.pending_confirmations:
            raise ValueError(f"No pending order {order_id}")

        pending = self.pending_confirmations[order_id]
        order = pending["order"]

        # Execute order
        result = await super().submit_order(order)

        # Remove from pending
        del self.pending_confirmations[order_id]

        return result

    async def reject_order(
        self, order_id: str, reason: str = "Manual rejection"
    ) -> MockOrderResponse:
        """Reject manual order."""
        if order_id not in self.pending_confirmations:
            raise ValueError(f"No pending order {order_id}")

        # Remove from pending
        del self.pending_confirmations[order_id]

        return MockOrderResponse(
            order_id=order_id, status=OrderStatus.REJECTED, rejection_reason=reason
        )


class BrokerResponseSimulator:
    """Simulates realistic broker responses for various scenarios."""

    @staticmethod
    def simulate_partial_fills(
        quantity: float, num_fills: int = 3
    ) -> List[Dict[str, Any]]:
        """Generate partial fill sequence."""
        fills = []
        remaining = quantity

        for i in range(num_fills - 1):
            fill_size = remaining * random.uniform(0.2, 0.6)
            fills.append(
                {
                    "quantity": fill_size,
                    "price": 1.0850 + random.uniform(-0.0002, 0.0002),
                    "timestamp": datetime.now() + timedelta(seconds=i * 10),
                }
            )
            remaining -= fill_size

        # Final fill
        fills.append(
            {
                "quantity": remaining,
                "price": 1.0850 + random.uniform(-0.0002, 0.0002),
                "timestamp": datetime.now() + timedelta(seconds=num_fills * 10),
            }
        )

        return fills

    @staticmethod
    def simulate_rejection_reasons() -> List[str]:
        """Get list of possible rejection reasons."""
        return [
            "Insufficient margin",
            "Invalid symbol",
            "Market closed",
            "Position limit exceeded",
            "Invalid price",
            "Risk limit exceeded",
            "Account restricted",
            "Order size too small",
            "Order size too large",
            "Duplicate order",
        ]

    @staticmethod
    def simulate_connection_issues() -> List[Exception]:
        """Simulate various connection issues."""
        return [
            ConnectionError("Connection timeout"),
            ConnectionError("Connection refused"),
            TimeoutError("Request timeout"),
            OSError("Network unreachable"),
            Exception("Authentication failed"),
            Exception("Session expired"),
        ]

    @staticmethod
    def simulate_market_impact(
        order_size: float, average_daily_volume: float = 1000000000
    ) -> float:
        """Calculate simulated market impact in pips."""
        # Simple square-root market impact model
        participation_rate = order_size / average_daily_volume
        impact_pips = 10 * np.sqrt(participation_rate * 10000)
        return min(impact_pips, 5.0)  # Cap at 5 pips


def create_mock_broker_suite() -> Dict[str, MockBrokerAdapter]:
    """
    Create a suite of mock broker adapters for testing.

    Returns:
        Dictionary of broker name to adapter instance
    """
    return {
        "IB": MockIBAdapter(failure_rate=0.01),
        "FXCM": MockFXCMAdapter(failure_rate=0.02),
        "Manual": MockManualAdapter(auto_confirm=True),
        "Unreliable": MockBrokerAdapter(
            broker_name="Unreliable", failure_rate=0.3, latency_ms=200
        ),
        "HighSlippage": MockBrokerAdapter(
            broker_name="HighSlippage", slippage_pips=2.0
        ),
    }


if __name__ == "__main__":
    # Example usage
    async def test_mock_brokers():
        brokers = create_mock_broker_suite()

        # Test IB adapter
        ib = brokers["IB"]
        await ib.connect_tws()

        order = {
            "symbol": "EURUSD",
            "side": "BUY",
            "quantity": 10000,
            "order_type": "MARKET",
        }

        result = await ib.submit_order(order)
        print(f"IB Order: {result}")

        # Test market data
        market_data = await ib.request_market_data("EURUSD")
        print(f"Market Data: {market_data}")

    # Run test
    asyncio.run(test_mock_brokers())
