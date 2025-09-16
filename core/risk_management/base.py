"""Unified Risk Management Base Interface.

This module provides the base interface and common functionality for all risk management
implementations across the FXML4 system. It consolidates the various risk manager classes
into a unified hierarchy.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd


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
    DRAWDOWN_LIMIT = "drawdown_limit"
    CORRELATION_LIMIT = "correlation_limit"
    LEVERAGE_LIMIT = "leverage_limit"
    RISK_REWARD_RATIO = "risk_reward_ratio"


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
    severity: str = "medium"
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RiskLimits:
    """Universal risk limits configuration."""

    # Position limits
    max_position_size: float = 0.1  # 10% of capital
    max_portfolio_risk: float = 0.06  # 6% total portfolio risk
    max_correlation: float = 0.7  # Maximum correlation between positions
    max_leverage: float = 1.0  # Maximum leverage

    # Loss limits
    max_daily_loss: float = 0.03  # 3% daily loss limit
    max_drawdown: float = 0.15  # 15% maximum drawdown

    # Order limits
    max_order_size: float = 0.05  # 5% of capital per order
    min_risk_reward: float = 1.5  # Minimum risk/reward ratio

    # Price limits
    max_price_deviation: float = 0.05  # 5% price deviation from market

    # Stop loss settings
    use_trailing_stop: bool = True
    trailing_stop_distance: float = 0.02  # 2% trailing stop

    # Position sizing
    position_sizing_method: str = "fixed_risk"  # 'fixed_risk', 'kelly', 'volatility'


@dataclass
class Position:
    """Universal position representation."""

    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float = 0.0
    entry_time: datetime = field(default_factory=datetime.utcnow)
    last_update: datetime = field(default_factory=datetime.utcnow)

    @property
    def notional_value(self) -> float:
        """Calculate notional value of position."""
        return abs(self.quantity * self.current_price)

    @property
    def market_value(self) -> float:
        """Calculate current market value."""
        return self.quantity * self.current_price


@dataclass
class RiskMetrics:
    """Portfolio risk metrics."""

    total_exposure: float = 0.0
    daily_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    portfolio_value: float = 0.0
    var_95: float = 0.0  # 95% Value at Risk
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    risk_reward_ratio: float = 0.0
    correlation_matrix: Optional[pd.DataFrame] = None


class BaseRiskManager(ABC):
    """Base interface for all risk management implementations."""

    def __init__(self, limits: Optional[RiskLimits] = None):
        """Initialize base risk manager.

        Args:
            limits: Risk limits configuration.
        """
        self.limits = limits or RiskLimits()
        self.positions: Dict[str, Position] = {}
        self.daily_pnl: List[float] = []
        self.peak_portfolio_value = 0.0
        self.current_portfolio_value = 0.0
        self.violations: List[RiskViolation] = []

    @abstractmethod
    def validate_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        account_balance: float,
        current_positions: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, List[RiskViolation]]:
        """Validate an order against risk rules.

        Args:
            symbol: Trading symbol.
            side: Order side ('buy' or 'sell').
            quantity: Order quantity.
            price: Order price.
            account_balance: Current account balance.
            current_positions: Current positions dictionary.

        Returns:
            Tuple of (is_valid, violations).
        """
        pass

    @abstractmethod
    def update_position(self, position: Position) -> None:
        """Update position in risk manager.

        Args:
            position: Position to update.
        """
        pass

    @abstractmethod
    def calculate_risk_metrics(self) -> RiskMetrics:
        """Calculate current portfolio risk metrics.

        Returns:
            Risk metrics object.
        """
        pass

    def get_position_size_limit(self, symbol: str, account_balance: float) -> float:
        """Get maximum position size for a symbol.

        Args:
            symbol: Trading symbol.
            account_balance: Current account balance.

        Returns:
            Maximum position size.
        """
        return account_balance * self.limits.max_position_size

    def check_drawdown_limit(self, current_value: float) -> Optional[RiskViolation]:
        """Check if current drawdown exceeds limits.

        Args:
            current_value: Current portfolio value.

        Returns:
            RiskViolation if limit exceeded, None otherwise.
        """
        if self.peak_portfolio_value == 0:
            self.peak_portfolio_value = current_value
            return None

        # Update peak if current value is higher
        if current_value > self.peak_portfolio_value:
            self.peak_portfolio_value = current_value
            return None

        # Calculate current drawdown
        current_drawdown = (
            self.peak_portfolio_value - current_value
        ) / self.peak_portfolio_value

        if current_drawdown > self.limits.max_drawdown:
            return RiskViolation(
                check_type=RiskCheckType.DRAWDOWN_LIMIT,
                result=RiskCheckResult.FAIL,
                message=f"Drawdown limit exceeded: {current_drawdown:.2%} > {self.limits.max_drawdown:.2%}",
                current_value=current_drawdown,
                limit_value=self.limits.max_drawdown,
                severity="high",
            )

        return None

    def check_correlation_limit(
        self, symbol: str, side: str
    ) -> Optional[RiskViolation]:
        """Check if adding position would exceed correlation limits.

        Args:
            symbol: Trading symbol.
            side: Position side.

        Returns:
            RiskViolation if limit exceeded, None otherwise.
        """
        # Simplified correlation check - would need historical data for full implementation
        # For now, just check if we already have positions in same currency pair
        base_currency = symbol[:3]
        quote_currency = symbol[3:]

        similar_positions = [
            pos
            for pos in self.positions.values()
            if pos.symbol.startswith(base_currency)
            or pos.symbol.endswith(quote_currency)
        ]

        if len(similar_positions) >= 3:  # Simple rule: max 3 positions in same currency
            return RiskViolation(
                check_type=RiskCheckType.CORRELATION_LIMIT,
                result=RiskCheckResult.WARN,
                message=f"High correlation risk: {len(similar_positions)} positions in {base_currency}/{quote_currency}",
                current_value=len(similar_positions),
                limit_value=3,
                severity="medium",
            )

        return None

    def add_violation(self, violation: RiskViolation) -> None:
        """Add a risk violation to the log.

        Args:
            violation: Risk violation to add.
        """
        self.violations.append(violation)

        # Keep only last 1000 violations to prevent memory issues
        if len(self.violations) > 1000:
            self.violations = self.violations[-1000:]
