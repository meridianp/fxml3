"""
Interactive Brokers Adapter - TDD Implementation (GREEN Phase)
Minimal implementation to make tests pass
"""

import asyncio
import time
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional


class IBAdapter:
    """
    Interactive Brokers trading adapter with risk management and safety features.
    This is the minimal GREEN phase implementation to make tests pass.
    """

    def __init__(
        self,
        max_position_size: Optional[float] = None,
        leverage: int = 50,
        auto_reconnect: bool = False,
        check_trading_hours: bool = False,
        max_consecutive_losses: int = None,
        daily_loss_limit: float = None,
    ):
        """Initialize IB adapter with configuration."""
        self.max_position_size = max_position_size
        self.leverage = leverage
        self.auto_reconnect = auto_reconnect
        self.check_trading_hours = check_trading_hours
        self.max_consecutive_losses = max_consecutive_losses
        self.daily_loss_limit = daily_loss_limit

        # Connection state
        self.connected = True  # Default to connected for simple cases

        # Order tracking
        self.orders = {}
        self.next_order_id = 1

        # Risk tracking
        self.consecutive_losses = 0
        self.daily_pnl = 0.0
        self.trade_results = []

    def place_order(self, order: Dict[str, Any]) -> int:
        """Place an order with validation and risk checks."""
        # Check connection
        if not self.connected:
            raise ConnectionError("Not connected to IB Gateway")

        # Check position limits
        if self.max_position_size and order.get("quantity", 0) > self.max_position_size:
            raise ValueError(f"Position size exceeds maximum: {self.max_position_size}")

        # Check circuit breaker
        if (
            self.max_consecutive_losses
            and self.consecutive_losses >= self.max_consecutive_losses
        ):
            raise RuntimeError(
                f"Circuit breaker triggered: {self.consecutive_losses} consecutive losses"
            )

        # Check daily loss limit
        if self.daily_loss_limit and abs(self.daily_pnl) > self.daily_loss_limit:
            raise RuntimeError(f"Daily loss limit exceeded: ${abs(self.daily_pnl):.2f}")

        # Check trading hours
        if self.check_trading_hours and not self._is_market_open():
            raise ValueError("Market is closed")

        # Generate order ID and store order
        order_id = self.next_order_id
        self.next_order_id += 1

        # Initialize order status
        self.orders[order_id] = {
            **order,
            "order_id": order_id,
            "status": "PENDING",
            "filled_quantity": 0,
            "remaining_quantity": order.get("quantity", 0),
            "created_at": datetime.now().isoformat(),
        }

        return order_id

    def calculate_margin(self, symbol: str, quantity: float, price: float) -> float:
        """Calculate required margin for a position."""
        position_value = quantity * price
        required_margin = position_value / self.leverage
        return required_margin

    def process_fill(self, fill_data: Dict[str, Any]) -> None:
        """Process a fill notification for an order."""
        order_id = fill_data.get("orderId")
        if order_id not in self.orders:
            raise ValueError(f"Unknown order ID: {order_id}")

        # Update order status
        order = self.orders[order_id]
        order["filled_quantity"] = fill_data.get("filled", 0)
        order["remaining_quantity"] = fill_data.get("remaining", 0)
        order["avgFillPrice"] = fill_data.get("avgFillPrice")

        # Update status based on fill
        if order["remaining_quantity"] == 0:
            order["status"] = "FILLED"
        elif order["filled_quantity"] > 0:
            order["status"] = "PARTIALLY_FILLED"

    def get_order_status(self, order_id: int) -> Dict[str, Any]:
        """Get the current status of an order."""
        if order_id not in self.orders:
            raise ValueError(f"Unknown order ID: {order_id}")

        order = self.orders[order_id]
        return {
            "order_id": order_id,
            "status": order["status"],
            "filled_quantity": order["filled_quantity"],
            "remaining_quantity": order["remaining_quantity"],
            "avg_fill_price": order.get("avgFillPrice"),
        }

    def record_trade_result(self, profit: float) -> None:
        """Record a trade result for risk management."""
        self.trade_results.append(profit)
        self.daily_pnl += profit

        # Track consecutive losses
        if profit < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

    async def ensure_connection(self) -> None:
        """Ensure connection to IB Gateway with auto-reconnect."""
        if self.connected:
            return

        if not self.auto_reconnect:
            raise ConnectionError("Not connected and auto-reconnect is disabled")

        # Attempt reconnection with exponential backoff
        max_attempts = 3
        for attempt in range(max_attempts):
            success = await self._connect_to_gateway()
            if success:
                self.connected = True
                return

            # Exponential backoff
            if attempt < max_attempts - 1:
                await asyncio.sleep(2**attempt)

        raise ConnectionError("Failed to reconnect after multiple attempts")

    async def _connect_to_gateway(self) -> bool:
        """Attempt to connect to IB Gateway (mocked for testing)."""
        # This would contain actual connection logic
        # For testing, this method will be mocked
        return False

    def _is_market_open(self) -> bool:
        """Check if forex market is open."""
        now = datetime.now()
        weekday = now.weekday()

        # Forex market is closed from Friday 5pm EST to Sunday 5pm EST
        # For simplicity, we'll say market is closed on Saturday (5)
        if weekday == 5:  # Saturday
            return False

        # Sunday: market opens at 5pm EST
        if weekday == 6:  # Sunday
            # This is a simplified check
            if now.hour < 17:  # Before 5pm
                return False

        # Friday: market closes at 5pm EST
        if weekday == 4:  # Friday
            if now.hour >= 17:  # After 5pm
                return False

        return True

    def reset_daily_stats(self) -> None:
        """Reset daily statistics (called at start of trading day)."""
        self.daily_pnl = 0.0
        self.consecutive_losses = 0

    def get_account_summary(self) -> Dict[str, Any]:
        """Get account summary information."""
        return {
            "connected": self.connected,
            "daily_pnl": self.daily_pnl,
            "consecutive_losses": self.consecutive_losses,
            "active_orders": len(
                [
                    o
                    for o in self.orders.values()
                    if o["status"] in ["PENDING", "PARTIALLY_FILLED"]
                ]
            ),
            "total_orders": len(self.orders),
        }
