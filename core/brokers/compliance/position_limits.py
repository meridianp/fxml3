"""
Position Limit Monitoring for FXML4 Trading Platform.

This module provides position limit monitoring and enforcement
capabilities for regulatory compliance.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from .surveillance import AlertSeverity

logger = logging.getLogger(__name__)


class LimitType(Enum):
    """Types of position limits."""

    POSITION_LIMIT = "position_limit"
    CONCENTRATION_LIMIT = "concentration_limit"
    EXPOSURE_LIMIT = "exposure_limit"
    VAR_LIMIT = "var_limit"


@dataclass
class LimitViolation:
    """Position limit violation."""

    violation_id: str
    limit_type: LimitType
    current_exposure: Decimal
    limit_threshold: Decimal
    violation_amount: Decimal
    severity: AlertSeverity
    detected_at: datetime
    details: Dict[str, Any]


class PositionLimitMonitor:
    """Position limit monitoring and enforcement system."""

    def __init__(
        self,
        default_position_limit: Decimal = Decimal("10000000"),
        concentration_limit_pct: float = 0.25,
        var_limit: Decimal = Decimal("500000"),
    ):
        self.default_position_limit = default_position_limit
        self.concentration_limit_pct = concentration_limit_pct
        self.var_limit = var_limit

    async def check_position_limits(
        self, position: Any, db: AsyncSession
    ) -> Optional[LimitViolation]:
        """Check position against configured limits."""

        current_exposure = position.market_value

        if current_exposure > self.default_position_limit:
            violation_amount = current_exposure - self.default_position_limit

            return LimitViolation(
                violation_id=f"POS_LIMIT_{position.symbol}",
                limit_type=LimitType.POSITION_LIMIT,
                current_exposure=current_exposure,
                limit_threshold=self.default_position_limit,
                violation_amount=violation_amount,
                severity=AlertSeverity.HIGH,
                detected_at=datetime.now(timezone.utc),
                details={
                    "symbol": position.symbol,
                    "position_size": float(position.quantity),
                    "market_value": float(current_exposure),
                    "limit": float(self.default_position_limit),
                },
            )

        return None

    async def check_concentration_limits(
        self,
        portfolio: Dict[str, Decimal],
        total_portfolio_value: Decimal,
        db: AsyncSession,
    ) -> List[LimitViolation]:
        """Check portfolio concentration limits."""
        violations = []

        for symbol, position_value in portfolio.items():
            concentration_pct = float(position_value / total_portfolio_value)

            if concentration_pct > self.concentration_limit_pct:
                violation = LimitViolation(
                    violation_id=f"CONC_LIMIT_{symbol}",
                    limit_type=LimitType.CONCENTRATION_LIMIT,
                    current_exposure=position_value,
                    limit_threshold=Decimal(
                        str(self.concentration_limit_pct * float(total_portfolio_value))
                    ),
                    violation_amount=position_value
                    - Decimal(
                        str(self.concentration_limit_pct * float(total_portfolio_value))
                    ),
                    severity=AlertSeverity.MEDIUM,
                    detected_at=datetime.now(timezone.utc),
                    details={
                        "symbol": symbol,
                        "concentration_pct": concentration_pct * 100,
                        "limit_pct": self.concentration_limit_pct * 100,
                        "position_value": float(position_value),
                        "total_portfolio": float(total_portfolio_value),
                    },
                )
                violations.append(violation)

        return violations
