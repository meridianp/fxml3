"""Risk Management Base Classes for Broker Abstraction.

This module defines the base classes and interfaces for risk management
in the FIX-based broker abstraction system.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ...fix.messages.base import OrdStatus, Side

# Note: Avoiding circular import - BrokerAdapter will be imported when needed
from ...fix.messages.orders import ExecutionReport, NewOrderSingle

logger = logging.getLogger(__name__)


class RiskCheckType(Enum):
    """Types of risk checks."""

    POSITION_LIMIT = "position_limit"
    NOTIONAL_LIMIT = "notional_limit"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    ORDER_SIZE_LIMIT = "order_size_limit"
    PRICE_DEVIATION = "price_deviation"
    SYMBOL_RESTRICTION = "symbol_restriction"
    TIME_RESTRICTION = "time_restriction"
    COUNTERPARTY_LIMIT = "counterparty_limit"
    MARGIN_REQUIREMENT = "margin_requirement"
    DUPLICATE_ORDER = "duplicate_order"


class RiskCheckResult(Enum):
    """Result of a risk check."""

    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    OVERRIDE = "override"


@dataclass
class RiskViolation:
    """Details of a risk check violation."""

    check_type: RiskCheckType
    result: RiskCheckResult
    message: str
    current_value: Any
    limit_value: Any
    timestamp: datetime = field(default_factory=datetime.utcnow)
    can_override: bool = False
    override_level: str = "risk_manager"  # risk_manager, senior_trader, compliance


@dataclass
class Position:
    """Current position for a symbol."""

    symbol: str
    quantity: float
    average_price: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float
    last_update: datetime = field(default_factory=datetime.utcnow)

    @property
    def notional_value(self) -> float:
        """Calculate notional value of position."""
        return abs(self.quantity * self.average_price)


@dataclass
class RiskLimits:
    """Risk limits configuration."""

    # Position limits
    max_position_size: Dict[str, float] = field(default_factory=dict)  # Per symbol
    max_portfolio_notional: float = 10_000_000  # Total portfolio
    max_single_position_notional: float = 1_000_000

    # Order limits
    max_order_size: Dict[str, float] = field(default_factory=dict)
    max_order_notional: float = 500_000
    min_order_size: float = 1000  # Minimum order size

    # Loss limits
    max_daily_loss: float = 50_000
    max_weekly_loss: float = 150_000
    max_monthly_loss: float = 500_000

    # Price limits
    max_price_deviation_pct: float = 2.0  # 2% from market

    # Time restrictions
    restricted_hours: List[Tuple[int, int]] = field(
        default_factory=list
    )  # [(start_hour, end_hour)]

    # Symbol restrictions
    allowed_symbols: Optional[List[str]] = None
    blocked_symbols: List[str] = field(default_factory=list)

    # Counterparty limits
    max_orders_per_broker: Dict[str, int] = field(default_factory=dict)
    max_notional_per_broker: Dict[str, float] = field(default_factory=dict)


@dataclass
class RiskMetrics:
    """Current risk metrics."""

    total_notional: float = 0
    daily_pnl: float = 0
    weekly_pnl: float = 0
    monthly_pnl: float = 0
    open_orders: int = 0
    open_order_notional: float = 0
    positions: Dict[str, Position] = field(default_factory=dict)
    broker_exposure: Dict[str, float] = field(default_factory=dict)
    last_update: datetime = field(default_factory=datetime.utcnow)


class RiskCheck(ABC):
    """Abstract base class for risk checks."""

    def __init__(self, check_type: RiskCheckType, enabled: bool = True):
        """Initialize risk check.

        Args:
            check_type: Type of risk check.
            enabled: Whether check is enabled.
        """
        self.check_type = check_type
        self.enabled = enabled

    @abstractmethod
    async def check(
        self, order: NewOrderSingle, limits: RiskLimits, metrics: RiskMetrics
    ) -> Optional[RiskViolation]:
        """Perform risk check on order.

        Args:
            order: Order to check.
            limits: Risk limits configuration.
            metrics: Current risk metrics.

        Returns:
            RiskViolation if check fails, None if passes.
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(type={self.check_type.value}, enabled={self.enabled})"


class RiskManager(ABC):
    """Abstract base class for risk management."""

    def __init__(self, limits: RiskLimits):
        """Initialize risk manager.

        Args:
            limits: Risk limits configuration.
        """
        self.limits = limits
        self.metrics = RiskMetrics()
        self.checks: List[RiskCheck] = []
        # CRITICAL FIX: Use proper asyncio locks instead of boolean flags
        self._position_locks: Dict[str, asyncio.Lock] = {}
        self._lock_creation_lock = asyncio.Lock()

    @abstractmethod
    async def check_order(
        self, order: NewOrderSingle, broker: Optional[str] = None
    ) -> Tuple[bool, List[RiskViolation]]:
        """Check if order passes risk controls.

        Args:
            order: Order to check.
            broker: Target broker for the order.

        Returns:
            Tuple of (passes_checks, list_of_violations).
        """
        pass

    @abstractmethod
    async def update_position(self, symbol: str, quantity: float, price: float) -> None:
        """Update position after trade.

        Args:
            symbol: Symbol traded.
            quantity: Quantity traded (positive for buy, negative for sell).
            price: Execution price.
        """
        pass

    @abstractmethod
    async def update_metrics(self) -> None:
        """Update risk metrics from current positions."""
        pass

    @abstractmethod
    async def handle_execution(self, execution: ExecutionReport) -> None:
        """Handle execution report for risk tracking.

        Args:
            execution: Execution report from broker.
        """
        pass

    async def lock_symbol(self, symbol: str) -> bool:
        """Acquire asyncio lock for symbol to prevent concurrent position updates.

        CRITICAL FIX: Uses proper asyncio locks with timeout to prevent deadlocks.

        Args:
            symbol: Symbol to lock.

        Returns:
            True if lock acquired, False if timeout or error.
        """
        try:
            # Thread-safe lock creation
            async with self._lock_creation_lock:
                if symbol not in self._position_locks:
                    self._position_locks[symbol] = asyncio.Lock()

            # Acquire symbol lock with timeout to prevent deadlocks
            symbol_lock = self._position_locks[symbol]

            # Try to acquire lock with 5-second timeout
            try:
                await asyncio.wait_for(symbol_lock.acquire(), timeout=5.0)
                return True
            except asyncio.TimeoutError:
                logger.warning(f"Timeout acquiring lock for symbol {symbol}")
                return False

        except Exception as e:
            logger.error(f"Error acquiring lock for symbol {symbol}: {e}")
            return False

    async def unlock_symbol(self, symbol: str) -> None:
        """Release asyncio lock for symbol after position update.

        Args:
            symbol: Symbol to unlock.
        """
        try:
            if symbol in self._position_locks:
                symbol_lock = self._position_locks[symbol]
                if symbol_lock.locked():
                    symbol_lock.release()
        except Exception as e:
            logger.error(f"Error releasing lock for symbol {symbol}: {e}")

    def add_check(self, check: RiskCheck) -> None:
        """Add risk check to manager.

        Args:
            check: Risk check to add.
        """
        self.checks.append(check)
        logger.info(f"Added risk check: {check}")

    def remove_check(self, check_type: RiskCheckType) -> None:
        """Remove risk check by type.

        Args:
            check_type: Type of check to remove.
        """
        self.checks = [c for c in self.checks if c.check_type != check_type]
        logger.info(f"Removed risk check: {check_type.value}")

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get current position for symbol.

        Args:
            symbol: Symbol to get position for.

        Returns:
            Position or None if no position.
        """
        return self.metrics.positions.get(symbol)

    def get_total_notional(self) -> float:
        """Get total portfolio notional value."""
        return sum(pos.notional_value for pos in self.metrics.positions.values())

    def get_daily_pnl(self) -> float:
        """Get total daily P&L."""
        return sum(
            pos.unrealized_pnl + pos.realized_pnl
            for pos in self.metrics.positions.values()
        )
