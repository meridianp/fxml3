"""Account Monitoring Bridge Components.

Implements account state synchronization, position tracking, margin monitoring,
and reconciliation between FXML4 and ForexConnect systems following TDD methodology.
Minimal implementation to pass the comprehensive tests.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set


def get_logger(name: str) -> logging.Logger:
    """Get logger for module."""
    return logging.getLogger(name)


logger = get_logger(__name__)


class AlertType(Enum):
    """Alert type enumeration."""

    LOW_BALANCE = "low_balance"
    HIGH_MARGIN_USAGE = "high_margin_usage"
    MARGIN_WARNING = "margin_warning"
    MARGIN_CALL = "margin_call"
    POSITION_LOSS = "position_loss"
    RECONCILIATION_FAILURE = "reconciliation_failure"


@dataclass
class AccountSnapshot:
    """Account state snapshot."""

    account_id: str
    balance: float
    equity: float
    margin_used: float
    margin_available: float
    unrealized_pl: float
    currency: str
    timestamp: datetime
    margin_level: float = field(init=False)
    free_margin: float = field(init=False)
    pl_percentage: float = field(init=False)

    def __post_init__(self):
        """Calculate derived fields."""
        self.margin_level = (
            (self.equity / self.margin_used) * 100 if self.margin_used > 0 else 0
        )
        self.free_margin = self.margin_available
        self.pl_percentage = (
            self.unrealized_pl / self.balance if self.balance > 0 else 0
        )


@dataclass
class PositionData:
    """Position data representation."""

    position_id: str
    symbol: str
    side: str
    quantity: int
    open_price: float
    current_price: float
    unrealized_pl: float
    timestamp: datetime
    close_price: Optional[float] = None
    realized_pl: Optional[float] = None
    is_closed: bool = False


@dataclass
class MarginData:
    """Margin data representation."""

    account_id: str
    equity: float
    margin_used: float
    margin_available: float
    margin_level: float
    status: str
    timestamp: datetime


@dataclass
class AccountAlert:
    """Account alert representation."""

    alert_type: AlertType
    account_id: str
    message: str
    severity: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReconciliationResult:
    """Reconciliation result representation."""

    account_id: str
    is_balanced: bool
    balance_difference: float
    equity_difference: float
    timestamp: datetime
    discrepancies: List[Any] = field(default_factory=list)
    within_tolerance: bool = False


@dataclass
class PositionReconciliationResult:
    """Position reconciliation result."""

    positions_match: bool
    missing_in_fxml4: List[Dict[str, Any]] = field(default_factory=list)
    missing_in_forex: List[Dict[str, Any]] = field(default_factory=list)
    quantity_differences: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Discrepancy:
    """Discrepancy representation."""

    field: str
    fxml4_value: Any
    forex_value: Any
    difference: float


@dataclass
class MarginTrendAnalysis:
    """Margin trend analysis result."""

    direction: str
    rate_of_change: float
    periods_analyzed: int


class AccountStateManager:
    """Manages account state synchronization with ForexConnect."""

    def __init__(self):
        """Initialize account state manager."""
        self.current_snapshot: Optional[AccountSnapshot] = None
        self.balance_history: List[AccountSnapshot] = []
        self.last_update: Optional[datetime] = None

        logger.info("Account state manager initialized")

    async def process_forex_account_update(
        self, account_data: Dict[str, Any]
    ) -> AccountSnapshot:
        """Process ForexConnect account update and create snapshot."""
        # Parse timestamp
        timestamp_str = account_data.get("timestamp")
        if isinstance(timestamp_str, str):
            # Try parsing ISO format
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except ValueError:
                timestamp = datetime.utcnow()
        else:
            timestamp = datetime.utcnow()

        # Create snapshot
        snapshot = AccountSnapshot(
            account_id=account_data["account_id"],
            balance=float(account_data["balance"]),
            equity=float(account_data["equity"]),
            margin_used=float(account_data.get("margin_used", 0)),
            margin_available=float(account_data.get("margin_available", 0)),
            unrealized_pl=float(
                account_data.get("pl", account_data.get("unrealized_pl", 0))
            ),
            currency=account_data.get("currency", "USD"),
            timestamp=timestamp,
        )

        # Update state
        self.current_snapshot = snapshot
        self.balance_history.append(snapshot)
        self.last_update = datetime.utcnow()

        logger.debug(f"Processed account update for {account_data['account_id']}")

        return snapshot

    def get_balance_change(self) -> float:
        """Get balance change from previous snapshot."""
        if len(self.balance_history) < 2:
            return 0.0

        current = self.balance_history[-1].balance
        previous = self.balance_history[-2].balance
        return current - previous

    def get_equity_change(self) -> float:
        """Get equity change from previous snapshot."""
        if len(self.balance_history) < 2:
            return 0.0

        current = self.balance_history[-1].equity
        previous = self.balance_history[-2].equity
        return current - previous

    async def generate_alerts(self, snapshot: AccountSnapshot) -> List[AccountAlert]:
        """Generate alerts based on account snapshot."""
        alerts = []

        # Low balance alert (less than $2000)
        if snapshot.balance < 2000:
            alerts.append(
                AccountAlert(
                    alert_type=AlertType.LOW_BALANCE,
                    account_id=snapshot.account_id,
                    message=f"Low balance: ${snapshot.balance:.2f}",
                    severity="warning",
                    timestamp=datetime.utcnow(),
                )
            )

        # High margin usage (over 80%)
        if (
            snapshot.margin_level < 125 and snapshot.margin_used > 0
        ):  # Less than 125% margin level
            alerts.append(
                AccountAlert(
                    alert_type=AlertType.HIGH_MARGIN_USAGE,
                    account_id=snapshot.account_id,
                    message=f"High margin usage: {snapshot.margin_level:.1f}%",
                    severity="critical",
                    timestamp=datetime.utcnow(),
                )
            )

        return alerts

    def get_account_summary(self) -> Dict[str, Any]:
        """Get account summary."""
        if not self.current_snapshot:
            return {}

        snapshot = self.current_snapshot
        account_age = (
            (datetime.utcnow() - self.last_update).total_seconds() / 60
            if self.last_update
            else 0
        )

        return {
            "account_id": snapshot.account_id,
            "current_balance": snapshot.balance,
            "current_equity": snapshot.equity,
            "margin_level": snapshot.margin_level,
            "unrealized_pl": snapshot.unrealized_pl,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "account_age_minutes": account_age,
        }


class PositionTracker:
    """Tracks positions and calculates P&L."""

    def __init__(self):
        """Initialize position tracker."""
        self.active_positions: Dict[str, PositionData] = {}
        self.closed_positions: List[PositionData] = []
        self.total_unrealized_pl: float = 0.0

        logger.info("Position tracker initialized")

    async def process_forex_position_update(
        self, position_data: Dict[str, Any]
    ) -> PositionData:
        """Process ForexConnect position update."""
        # Parse timestamp
        timestamp_str = position_data.get("timestamp")
        if isinstance(timestamp_str, str):
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except ValueError:
                timestamp = datetime.utcnow()
        else:
            timestamp = datetime.utcnow()

        # Calculate P&L if not provided
        unrealized_pl = position_data.get("unrealized_pl")
        if unrealized_pl is None:
            open_price = float(position_data["open_price"])
            current_price = float(position_data["current_price"])
            quantity = int(position_data["quantity"])
            side = position_data["side"]

            if side == "long":
                unrealized_pl = (current_price - open_price) * abs(quantity)
            else:  # short
                unrealized_pl = (open_price - current_price) * abs(quantity)
        else:
            unrealized_pl = float(unrealized_pl)

        # Create or update position
        position = PositionData(
            position_id=position_data["position_id"],
            symbol=position_data["symbol"],
            side=position_data["side"],
            quantity=int(position_data["quantity"]),
            open_price=float(position_data["open_price"]),
            current_price=float(position_data["current_price"]),
            unrealized_pl=unrealized_pl,
            timestamp=timestamp,
        )

        # Store position
        self.active_positions[position.position_id] = position

        # Update total P&L
        self.total_unrealized_pl = self.calculate_total_unrealized_pl()

        logger.debug(f"Processed position update for {position.position_id}")

        return position

    def calculate_total_unrealized_pl(self) -> float:
        """Calculate total unrealized P&L across all positions."""
        return sum(pos.unrealized_pl for pos in self.active_positions.values())

    async def close_position(
        self, position_id: str, close_price: float, realized_pl: float
    ) -> PositionData:
        """Close a position."""
        if position_id not in self.active_positions:
            raise ValueError(f"Position {position_id} not found")

        position = self.active_positions[position_id]

        # Update position with closure data
        position.close_price = close_price
        position.realized_pl = realized_pl
        position.is_closed = True

        # Move to closed positions
        del self.active_positions[position_id]
        self.closed_positions.append(position)

        # Update total P&L
        self.total_unrealized_pl = self.calculate_total_unrealized_pl()

        logger.debug(f"Closed position {position_id}")

        return position

    def get_positions_by_symbol(self, symbol: str) -> List[PositionData]:
        """Get positions for specific symbol."""
        return [pos for pos in self.active_positions.values() if pos.symbol == symbol]

    def get_position_statistics(self) -> Dict[str, Any]:
        """Get position statistics."""
        long_positions = sum(
            1 for pos in self.active_positions.values() if pos.side == "long"
        )
        short_positions = sum(
            1 for pos in self.active_positions.values() if pos.side == "short"
        )
        profitable_positions = sum(
            1 for pos in self.active_positions.values() if pos.unrealized_pl > 0
        )
        losing_positions = sum(
            1 for pos in self.active_positions.values() if pos.unrealized_pl < 0
        )

        return {
            "total_positions": len(self.active_positions),
            "long_positions": long_positions,
            "short_positions": short_positions,
            "total_unrealized_pl": self.total_unrealized_pl,
            "profitable_positions": profitable_positions,
            "losing_positions": losing_positions,
        }


class MarginMonitor:
    """Monitors margin levels and generates alerts."""

    def __init__(self):
        """Initialize margin monitor."""
        self.margin_alert_threshold = 100.0  # Default 100%
        self.margin_call_threshold = 50.0  # Default 50%
        self.margin_history: List[MarginData] = []

        logger.info("Margin monitor initialized")

    async def process_margin_update(self, margin_data: Dict[str, Any]) -> MarginData:
        """Process margin data update."""
        # Parse timestamp
        timestamp_str = margin_data.get("timestamp")
        if isinstance(timestamp_str, str):
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except ValueError:
                timestamp = datetime.utcnow()
        else:
            timestamp = datetime.utcnow()

        # Calculate margin level
        equity = float(margin_data["equity"])
        margin_used = float(margin_data["margin_used"])
        margin_level = (equity / margin_used) * 100 if margin_used > 0 else 0

        # Determine status
        if margin_level <= self.margin_call_threshold:
            status = "margin_call"
        elif margin_level <= self.margin_alert_threshold:
            status = "warning"
        else:
            status = "healthy"

        # Create margin data
        data = MarginData(
            account_id=margin_data["account_id"],
            equity=equity,
            margin_used=margin_used,
            margin_available=float(margin_data.get("margin_available", 0)),
            margin_level=margin_level,
            status=status,
            timestamp=timestamp,
        )

        # Store in history
        self.margin_history.append(data)

        logger.debug(f"Processed margin update for {data.account_id}")

        return data

    async def set_margin_thresholds(
        self, alert_threshold: float, call_threshold: float
    ) -> None:
        """Set margin alert thresholds."""
        self.margin_alert_threshold = alert_threshold
        self.margin_call_threshold = call_threshold

        logger.debug(
            f"Updated margin thresholds: alert={alert_threshold}%, call={call_threshold}%"
        )

    async def check_margin_alerts(self, margin_data: MarginData) -> List[AccountAlert]:
        """Check for margin-related alerts."""
        alerts = []

        if margin_data.margin_level <= self.margin_call_threshold:
            alerts.append(
                AccountAlert(
                    alert_type=AlertType.MARGIN_CALL,
                    account_id=margin_data.account_id,
                    message=f"Margin call: {margin_data.margin_level:.1f}%",
                    severity="critical",
                    timestamp=datetime.utcnow(),
                )
            )
        elif margin_data.margin_level <= self.margin_alert_threshold:
            alerts.append(
                AccountAlert(
                    alert_type=AlertType.MARGIN_WARNING,
                    account_id=margin_data.account_id,
                    message=f"Low margin: {margin_data.margin_level:.1f}%",
                    severity="warning",
                    timestamp=datetime.utcnow(),
                )
            )

        return alerts

    def analyze_margin_trend(self, lookback_periods: int = 5) -> Dict[str, Any]:
        """Analyze margin trend over recent periods."""
        if len(self.margin_history) < lookback_periods:
            return {
                "direction": "insufficient_data",
                "rate_of_change": 0.0,
                "periods_analyzed": len(self.margin_history),
            }

        recent_history = self.margin_history[-lookback_periods:]
        margin_levels = [data.margin_level for data in recent_history]

        # Simple linear trend calculation
        first_level = margin_levels[0]
        last_level = margin_levels[-1]
        rate_of_change = (last_level - first_level) / lookback_periods

        direction = (
            "declining"
            if rate_of_change < 0
            else "improving" if rate_of_change > 0 else "stable"
        )

        return {
            "direction": direction,
            "rate_of_change": rate_of_change,
            "periods_analyzed": lookback_periods,
        }

    def get_margin_summary(self) -> Dict[str, Any]:
        """Get margin summary."""
        if not self.margin_history:
            return {}

        latest = self.margin_history[-1]
        distance_to_call = latest.margin_level - self.margin_call_threshold

        return {
            "current_margin_level": latest.margin_level,
            "margin_status": latest.status,
            "margin_used": latest.margin_used,
            "margin_available": latest.margin_available,
            "distance_to_margin_call": distance_to_call,
            "last_update": latest.timestamp.isoformat(),
        }


class AccountReconciler:
    """Reconciles account data between FXML4 and ForexConnect systems."""

    def __init__(self):
        """Initialize account reconciler."""
        self.reconciliation_history: List[ReconciliationResult] = []
        self.last_reconciliation: Optional[ReconciliationResult] = None
        self.balance_tolerance: float = 0.0
        self.pl_tolerance: float = 0.0

        logger.info("Account reconciler initialized")

    async def reconcile_account_balance(
        self,
        fxml4_state: Dict[str, Any],
        forex_state: Dict[str, Any],
        apply_tolerance: bool = False,
    ) -> ReconciliationResult:
        """Reconcile account balances between systems."""
        # Calculate differences
        balance_diff = fxml4_state["balance"] - forex_state["balance"]
        equity_diff = fxml4_state["equity"] - forex_state["equity"]

        # Check for discrepancies
        discrepancies = []

        # Balance discrepancy
        if abs(balance_diff) > (self.balance_tolerance if apply_tolerance else 0):
            discrepancies.append(
                Discrepancy(
                    field="balance",
                    fxml4_value=fxml4_state["balance"],
                    forex_value=forex_state["balance"],
                    difference=balance_diff,
                )
            )

        # Equity discrepancy
        if abs(equity_diff) > (self.balance_tolerance if apply_tolerance else 0):
            discrepancies.append(
                Discrepancy(
                    field="equity",
                    fxml4_value=fxml4_state["equity"],
                    forex_value=forex_state["equity"],
                    difference=equity_diff,
                )
            )

        # P&L discrepancy
        fxml4_pl = fxml4_state.get("unrealized_pl", 0)
        forex_pl = forex_state.get("pl", 0)
        pl_diff = fxml4_pl - forex_pl

        if abs(pl_diff) > (self.pl_tolerance if apply_tolerance else 0):
            discrepancies.append(
                Discrepancy(
                    field="unrealized_pl",
                    fxml4_value=fxml4_pl,
                    forex_value=forex_pl,
                    difference=pl_diff,
                )
            )

        # Determine if balanced
        is_balanced = len(discrepancies) == 0
        within_tolerance = apply_tolerance and is_balanced

        # Create result
        result = ReconciliationResult(
            account_id=fxml4_state["account_id"],
            is_balanced=is_balanced,
            balance_difference=balance_diff,
            equity_difference=equity_diff,
            timestamp=datetime.utcnow(),
            discrepancies=discrepancies,
            within_tolerance=within_tolerance,
        )

        # Store result
        self.reconciliation_history.append(result)
        self.last_reconciliation = result

        logger.debug(f"Reconciled account {result.account_id}: balanced={is_balanced}")

        return result

    async def reconcile_positions(
        self,
        fxml4_positions: List[Dict[str, Any]],
        forex_positions: List[Dict[str, Any]],
    ) -> PositionReconciliationResult:
        """Reconcile positions between systems."""
        # Create position maps
        fxml4_map = {pos["position_id"]: pos for pos in fxml4_positions}
        forex_map = {pos["position_id"]: pos for pos in forex_positions}

        # Find missing positions
        missing_in_fxml4 = [
            pos for pos in forex_positions if pos["position_id"] not in fxml4_map
        ]
        missing_in_forex = [
            pos for pos in fxml4_positions if pos["position_id"] not in forex_map
        ]

        # Find quantity differences
        quantity_differences = []
        common_positions = set(fxml4_map.keys()) & set(forex_map.keys())

        for pos_id in common_positions:
            fxml4_pos = fxml4_map[pos_id]
            forex_pos = forex_map[pos_id]

            if fxml4_pos["quantity"] != forex_pos["quantity"]:
                quantity_differences.append(
                    {
                        "position_id": pos_id,
                        "fxml4_quantity": fxml4_pos["quantity"],
                        "forex_quantity": forex_pos["quantity"],
                        "difference": fxml4_pos["quantity"] - forex_pos["quantity"],
                    }
                )

        # Determine if positions match
        positions_match = (
            len(missing_in_fxml4) == 0
            and len(missing_in_forex) == 0
            and len(quantity_differences) == 0
        )

        result = PositionReconciliationResult(
            positions_match=positions_match,
            missing_in_fxml4=missing_in_fxml4,
            missing_in_forex=missing_in_forex,
            quantity_differences=quantity_differences,
        )

        logger.debug(f"Reconciled positions: match={positions_match}")

        return result

    async def set_reconciliation_tolerance(
        self, balance_tolerance: float, pl_tolerance: float
    ) -> None:
        """Set reconciliation tolerances."""
        self.balance_tolerance = balance_tolerance
        self.pl_tolerance = pl_tolerance

        logger.debug(
            f"Updated tolerances: balance=${balance_tolerance}, pl=${pl_tolerance}"
        )

    def get_reconciliation_report(self) -> Dict[str, Any]:
        """Generate reconciliation report."""
        if not self.reconciliation_history:
            return {
                "total_reconciliations": 0,
                "successful_reconciliations": 0,
                "failed_reconciliations": 0,
                "success_rate": 0.0,
                "last_reconciliation": None,
                "common_discrepancy_types": [],
            }

        total = len(self.reconciliation_history)
        successful = sum(1 for r in self.reconciliation_history if r.is_balanced)
        failed = total - successful
        success_rate = successful / total if total > 0 else 0.0

        # Count discrepancy types
        discrepancy_counts = {}
        for result in self.reconciliation_history:
            for discrepancy in result.discrepancies:
                field = discrepancy.field
                discrepancy_counts[field] = discrepancy_counts.get(field, 0) + 1

        common_discrepancies = sorted(
            discrepancy_counts.items(), key=lambda x: x[1], reverse=True
        )

        return {
            "total_reconciliations": total,
            "successful_reconciliations": successful,
            "failed_reconciliations": failed,
            "success_rate": success_rate,
            "last_reconciliation": (
                self.last_reconciliation.timestamp.isoformat()
                if self.last_reconciliation
                else None
            ),
            "common_discrepancy_types": common_discrepancies,
        }


# Module exports
__all__ = [
    "AccountStateManager",
    "PositionTracker",
    "MarginMonitor",
    "AccountReconciler",
    "AccountSnapshot",
    "PositionData",
    "MarginData",
    "AccountAlert",
    "AlertType",
    "ReconciliationResult",
    "PositionReconciliationResult",
    "Discrepancy",
    "MarginTrendAnalysis",
]
