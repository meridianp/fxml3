"""
Best Execution Monitor for FXML4 Trading Platform.

This module provides best execution monitoring and validation
capabilities for regulatory compliance.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class ExecutionQuality:
    """Execution quality metrics."""

    achieved_best_execution: bool
    price_improvement: Optional[Decimal]
    execution_venue: str
    market_impact: Optional[Decimal]
    total_transaction_cost: Optional[Decimal]
    analysis_timestamp: datetime


@dataclass
class PriceImprovement:
    """Price improvement analysis."""

    improvement_amount: Decimal
    improvement_basis_points: Decimal
    benchmark_price: Decimal
    execution_price: Decimal


@dataclass
class ExecutionQualityReport:
    """Comprehensive execution quality report."""

    fill_rate: Decimal
    execution_latency_ms: int
    total_transaction_cost: Decimal
    meets_best_execution_standard: bool
    price_improvement: Optional[PriceImprovement]


class BestExecutionMonitor:
    """Best execution monitoring and validation system."""

    def __init__(
        self,
        price_improvement_threshold: Decimal = Decimal("0.0001"),
        execution_venues: List[str] = None,
        latency_threshold_ms: int = 100,
    ):
        self.price_improvement_threshold = price_improvement_threshold
        self.execution_venues = execution_venues or [
            "IDEALPRO",
            "EBS",
            "REUTERS",
            "FXCM",
        ]
        self.latency_threshold_ms = latency_threshold_ms

    async def calculate_execution_quality(
        self, trade: Any, market_data: Dict[str, Any], db: AsyncSession
    ) -> ExecutionQuality:
        """Calculate execution quality for a trade."""

        symbol_data = market_data.get(trade.symbol, {})
        best_bid = symbol_data.get("best_bid", trade.price)
        best_ask = symbol_data.get("best_ask", trade.price)

        # Determine benchmark price
        if trade.side.lower() == "buy":
            benchmark_price = best_ask
            price_improvement = (
                benchmark_price - trade.price
                if trade.price < benchmark_price
                else Decimal("0")
            )
        else:  # sell
            benchmark_price = best_bid
            price_improvement = (
                trade.price - benchmark_price
                if trade.price > benchmark_price
                else Decimal("0")
            )

        # Check if execution venue is in our list
        execution_venue = getattr(trade, "venue", "IDEALPRO")
        venue_acceptable = execution_venue in self.execution_venues

        achieved_best_execution = price_improvement >= Decimal("0") and venue_acceptable

        return ExecutionQuality(
            achieved_best_execution=achieved_best_execution,
            price_improvement=price_improvement,
            execution_venue=execution_venue,
            market_impact=None,  # Would calculate with more detailed market data
            total_transaction_cost=None,
            analysis_timestamp=datetime.now(timezone.utc),
        )

    async def generate_execution_quality_report(
        self, trade: Any, execution_details: Dict[str, Any], db: AsyncSession
    ) -> ExecutionQualityReport:
        """Generate comprehensive execution quality report."""

        # Calculate fill rate
        requested_quantity = execution_details.get("requested_quantity", trade.quantity)
        executed_quantity = execution_details.get("executed_quantity", trade.quantity)
        fill_rate = (
            executed_quantity / requested_quantity
            if requested_quantity > 0
            else Decimal("0")
        )

        # Calculate execution latency
        order_timestamp = execution_details.get("order_timestamp", trade.timestamp)
        execution_timestamp = execution_details.get(
            "execution_timestamp", trade.timestamp
        )
        latency_ms = int((execution_timestamp - order_timestamp).total_seconds() * 1000)

        # Calculate total transaction cost
        commission = execution_details.get("total_commission", Decimal("0"))
        total_cost = (
            commission  # Simplified - would include spread, market impact, etc.
        )

        # Determine if meets best execution standard
        meets_standard = (
            fill_rate >= Decimal("1.0")  # Fully filled
            and latency_ms <= self.latency_threshold_ms  # Within latency threshold
            and total_cost
            <= trade.quantity * trade.price * Decimal("0.001")  # Cost < 10 bps
        )

        # Calculate price improvement if available
        price_improvement = None
        if execution_details.get("benchmark_price"):
            benchmark = Decimal(str(execution_details["benchmark_price"]))
            improvement_amount = abs(trade.price - benchmark)
            improvement_bps = (improvement_amount / benchmark) * 10000  # basis points

            price_improvement = PriceImprovement(
                improvement_amount=improvement_amount,
                improvement_basis_points=improvement_bps,
                benchmark_price=benchmark,
                execution_price=trade.price,
            )

        return ExecutionQualityReport(
            fill_rate=fill_rate,
            execution_latency_ms=latency_ms,
            total_transaction_cost=total_cost,
            meets_best_execution_standard=meets_standard,
            price_improvement=price_improvement,
        )
