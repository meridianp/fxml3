"""
Interactive Brokers Adapter - TDD Implementation (REFACTOR Phase)
Improved design with better separation of concerns and cleaner architecture
"""

import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    """Order status enumeration."""

    PENDING = "PENDING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class MarketStatus(Enum):
    """Market status enumeration."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"
    PRE_MARKET = "PRE_MARKET"
    AFTER_HOURS = "AFTER_HOURS"


class RiskViolation(Exception):
    """Exception raised when risk limits are violated."""

    pass


class PositionLimitExceeded(RiskViolation):
    """Position size exceeds maximum allowed."""

    pass


class DailyLossLimitExceeded(RiskViolation):
    """Daily loss exceeds maximum allowed."""

    pass


class CircuitBreakerTriggered(RiskViolation):
    """Circuit breaker has been triggered."""

    pass


class MarketClosedError(ValueError):
    """Market is closed for trading."""

    pass


class ConnectionManager:
    """Manages connection state and reconnection logic."""

    def __init__(self, auto_reconnect: bool = False):
        self.auto_reconnect = auto_reconnect
        self.connected = True
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 3

    def is_connected(self) -> bool:
        """Check if connection is active."""
        return self.connected

    def disconnect(self):
        """Disconnect from gateway."""
        self.connected = False
        self._reconnect_attempts = 0

    async def ensure_connection(self) -> None:
        """Ensure connection is active, reconnecting if necessary."""
        if self.connected:
            return

        if not self.auto_reconnect:
            raise ConnectionError("Not connected and auto-reconnect is disabled")

        await self._reconnect_with_backoff()

    async def _reconnect_with_backoff(self) -> None:
        """Attempt reconnection with exponential backoff."""
        for attempt in range(self._max_reconnect_attempts):
            success = await self._attempt_connection()
            if success:
                self.connected = True
                self._reconnect_attempts = 0
                logger.info("Successfully reconnected to IB Gateway")
                return

            # Exponential backoff between attempts
            if attempt < self._max_reconnect_attempts - 1:
                wait_time = 2**attempt
                logger.warning(
                    f"Reconnection attempt {attempt + 1} failed, waiting {wait_time}s"
                )
                await asyncio.sleep(wait_time)

        raise ConnectionError(
            f"Failed to reconnect after {self._max_reconnect_attempts} attempts"
        )

    async def _attempt_connection(self) -> bool:
        """Attempt to establish connection to IB Gateway."""
        # This would contain actual connection logic
        # For testing, this method will be mocked
        return False


class RiskManager:
    """Manages risk limits and circuit breakers."""

    def __init__(
        self,
        max_position_size: Optional[float] = None,
        daily_loss_limit: Optional[float] = None,
        max_consecutive_losses: Optional[int] = None,
    ):
        self.max_position_size = max_position_size
        self.daily_loss_limit = daily_loss_limit
        self.max_consecutive_losses = max_consecutive_losses

        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        self.trade_results: List[float] = []

    def validate_order(self, order: Dict[str, Any]) -> None:
        """Validate order against risk limits."""
        self._check_position_limit(order.get("quantity", 0))
        self._check_circuit_breaker()
        self._check_daily_loss_limit()

    def _check_position_limit(self, quantity: float) -> None:
        """Check if position size is within limits."""
        if self.max_position_size and quantity > self.max_position_size:
            raise PositionLimitExceeded(
                f"Position size {quantity} exceeds maximum {self.max_position_size}"
            )

    def _check_circuit_breaker(self) -> None:
        """Check if circuit breaker is triggered."""
        if (
            self.max_consecutive_losses
            and self.consecutive_losses >= self.max_consecutive_losses
        ):
            raise CircuitBreakerTriggered(
                f"Circuit breaker triggered: {self.consecutive_losses} consecutive losses"
            )

    def _check_daily_loss_limit(self) -> None:
        """Check if daily loss limit is exceeded."""
        if self.daily_loss_limit and abs(self.daily_pnl) > self.daily_loss_limit:
            raise DailyLossLimitExceeded(
                f"Daily loss ${abs(self.daily_pnl):.2f} exceeds limit ${self.daily_loss_limit}"
            )

    def record_trade_result(self, profit: float) -> None:
        """Record a trade result and update risk metrics."""
        self.trade_results.append(profit)
        self.daily_pnl += profit

        if profit < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

        logger.info(
            f"Trade result recorded: ${profit:.2f}, Daily P&L: ${self.daily_pnl:.2f}"
        )

    def reset_daily_stats(self) -> None:
        """Reset daily statistics at start of trading day."""
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        self.trade_results.clear()
        logger.info("Daily risk statistics reset")


class MarketHoursValidator:
    """Validates trading hours for different markets."""

    def __init__(self, check_trading_hours: bool = False):
        self.check_trading_hours = check_trading_hours

    def validate_market_hours(self) -> None:
        """Check if market is open for trading."""
        if not self.check_trading_hours:
            return

        if not self._is_market_open():
            raise MarketClosedError("Market is closed")

    def _is_market_open(self) -> bool:
        """Check if forex market is currently open."""
        now = datetime.now()
        weekday = now.weekday()

        # Forex market hours (simplified)
        # Closed: Friday 5pm EST to Sunday 5pm EST

        # Saturday - always closed
        if weekday == 5:
            return False

        # Sunday - closed until 5pm EST
        if weekday == 6 and now.hour < 17:
            return False

        # Friday - closed after 5pm EST
        if weekday == 4 and now.hour >= 17:
            return False

        return True

    def get_market_status(self) -> MarketStatus:
        """Get current market status."""
        if self._is_market_open():
            return MarketStatus.OPEN
        return MarketStatus.CLOSED


class OrderManager:
    """Manages order lifecycle and tracking."""

    def __init__(self):
        self.orders: Dict[int, Dict[str, Any]] = {}
        self.next_order_id = 1

    def create_order(self, order_data: Dict[str, Any]) -> int:
        """Create a new order and return its ID."""
        order_id = self.next_order_id
        self.next_order_id += 1

        self.orders[order_id] = {
            **order_data,
            "order_id": order_id,
            "status": OrderStatus.PENDING.value,
            "filled_quantity": 0,
            "remaining_quantity": order_data.get("quantity", 0),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        logger.info(f"Created order {order_id}: {order_data}")
        return order_id

    def process_fill(self, fill_data: Dict[str, Any]) -> None:
        """Process fill notification for an order."""
        order_id = fill_data.get("orderId")
        if order_id not in self.orders:
            raise ValueError(f"Unknown order ID: {order_id}")

        order = self.orders[order_id]
        order["filled_quantity"] = fill_data.get("filled", 0)
        order["remaining_quantity"] = fill_data.get("remaining", 0)
        order["avgFillPrice"] = fill_data.get("avgFillPrice")
        order["updated_at"] = datetime.now().isoformat()

        # Update status based on fill
        if order["remaining_quantity"] == 0:
            order["status"] = OrderStatus.FILLED.value
        elif order["filled_quantity"] > 0:
            order["status"] = OrderStatus.PARTIALLY_FILLED.value

        logger.info(f"Processed fill for order {order_id}: {fill_data}")

    def get_order_status(self, order_id: int) -> Dict[str, Any]:
        """Get current status of an order."""
        if order_id not in self.orders:
            raise ValueError(f"Unknown order ID: {order_id}")

        order = self.orders[order_id]
        return {
            "order_id": order_id,
            "status": order["status"],
            "filled_quantity": order["filled_quantity"],
            "remaining_quantity": order["remaining_quantity"],
            "avg_fill_price": order.get("avgFillPrice"),
            "created_at": order["created_at"],
            "updated_at": order["updated_at"],
        }

    def get_active_orders(self) -> List[Dict[str, Any]]:
        """Get list of active orders."""
        active_statuses = [
            OrderStatus.PENDING.value,
            OrderStatus.PARTIALLY_FILLED.value,
        ]
        return [
            order
            for order in self.orders.values()
            if order["status"] in active_statuses
        ]


class IBAdapter:
    """
    Interactive Brokers trading adapter with risk management and safety features.
    REFACTOR phase: Improved design with better separation of concerns.
    """

    def __init__(
        self,
        max_position_size: Optional[float] = None,
        leverage: int = 50,
        auto_reconnect: bool = False,
        check_trading_hours: bool = False,
        max_consecutive_losses: Optional[int] = None,
        daily_loss_limit: Optional[float] = None,
    ):
        """Initialize IB adapter with configuration."""
        self.leverage = leverage

        # Initialize component managers
        self.connection_manager = ConnectionManager(auto_reconnect)
        self.risk_manager = RiskManager(
            max_position_size, daily_loss_limit, max_consecutive_losses
        )
        self.market_hours_validator = MarketHoursValidator(check_trading_hours)
        self.order_manager = OrderManager()

        logger.info("IB Adapter initialized with enhanced architecture")

    def place_order(self, order: Dict[str, Any]) -> int:
        """Place an order with comprehensive validation."""
        # Validate connection
        if not self.connection_manager.is_connected():
            raise ConnectionError("Not connected to IB Gateway")

        # Validate market hours
        self.market_hours_validator.validate_market_hours()

        # Validate risk limits
        try:
            self.risk_manager.validate_order(order)
        except PositionLimitExceeded:
            raise ValueError(
                f"Position size exceeds maximum: {self.risk_manager.max_position_size}"
            )
        except CircuitBreakerTriggered as e:
            raise RuntimeError(str(e))
        except DailyLossLimitExceeded:
            raise RuntimeError(
                f"Daily loss limit exceeded: ${abs(self.risk_manager.daily_pnl):.2f}"
            )

        # Create and return order
        return self.order_manager.create_order(order)

    def calculate_margin(self, symbol: str, quantity: float, price: float) -> float:
        """Calculate required margin for a position."""
        position_value = quantity * price
        required_margin = position_value / self.leverage
        logger.debug(
            f"Margin for {quantity} {symbol} @ {price}: ${required_margin:.2f}"
        )
        return required_margin

    def process_fill(self, fill_data: Dict[str, Any]) -> None:
        """Process a fill notification for an order."""
        self.order_manager.process_fill(fill_data)

    def get_order_status(self, order_id: int) -> Dict[str, Any]:
        """Get the current status of an order."""
        return self.order_manager.get_order_status(order_id)

    def record_trade_result(self, profit: float) -> None:
        """Record a trade result for risk management."""
        self.risk_manager.record_trade_result(profit)

    async def ensure_connection(self) -> None:
        """Ensure connection to IB Gateway with auto-reconnect."""
        await self.connection_manager.ensure_connection()

    def reset_daily_stats(self) -> None:
        """Reset daily statistics (called at start of trading day)."""
        self.risk_manager.reset_daily_stats()

    def get_account_summary(self) -> Dict[str, Any]:
        """Get comprehensive account summary."""
        active_orders = self.order_manager.get_active_orders()
        return {
            "connected": self.connection_manager.is_connected(),
            "daily_pnl": self.risk_manager.daily_pnl,
            "consecutive_losses": self.risk_manager.consecutive_losses,
            "active_orders": len(active_orders),
            "total_orders": len(self.order_manager.orders),
            "market_status": self.market_hours_validator.get_market_status().value,
            "leverage": self.leverage,
            "risk_limits": {
                "max_position_size": self.risk_manager.max_position_size,
                "daily_loss_limit": self.risk_manager.daily_loss_limit,
                "max_consecutive_losses": self.risk_manager.max_consecutive_losses,
            },
        }

    # Maintain backward compatibility
    @property
    def connected(self) -> bool:
        """Backward compatibility for connected property."""
        return self.connection_manager.is_connected()

    @connected.setter
    def connected(self, value: bool):
        """Backward compatibility for connected property."""
        self.connection_manager.connected = value

    @property
    def daily_pnl(self) -> float:
        """Backward compatibility for daily_pnl property."""
        return self.risk_manager.daily_pnl

    @property
    def consecutive_losses(self) -> int:
        """Backward compatibility for consecutive_losses property."""
        return self.risk_manager.consecutive_losses

    @property
    def orders(self) -> Dict[int, Dict[str, Any]]:
        """Backward compatibility for orders property."""
        return self.order_manager.orders

    @property
    def max_position_size(self) -> Optional[float]:
        """Backward compatibility for max_position_size property."""
        return self.risk_manager.max_position_size

    @property
    def daily_loss_limit(self) -> Optional[float]:
        """Backward compatibility for daily_loss_limit property."""
        return self.risk_manager.daily_loss_limit

    @property
    def max_consecutive_losses(self) -> Optional[int]:
        """Backward compatibility for max_consecutive_losses property."""
        return self.risk_manager.max_consecutive_losses

    @property
    def check_trading_hours(self) -> bool:
        """Backward compatibility for check_trading_hours property."""
        return self.market_hours_validator.check_trading_hours

    async def _connect_to_gateway(self) -> bool:
        """Backward compatibility for connection method."""
        return await self.connection_manager._attempt_connection()
