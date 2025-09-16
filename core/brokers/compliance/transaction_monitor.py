"""Transaction Monitoring for Anti-Money Laundering and Suspicious Activity Detection.

This module implements real-time transaction monitoring to detect suspicious
trading patterns and potential money laundering activities.
"""

import asyncio
import json
import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from .audit_logger import AuditEvent, AuditLogger, AuditSeverity

logger = logging.getLogger(__name__)


class SuspiciousActivityType(Enum):
    """Types of suspicious activities."""

    UNUSUAL_VOLUME = "UNUSUAL_VOLUME"
    RAPID_TRADING = "RAPID_TRADING"
    ROUND_TRIP_TRADING = "ROUND_TRIP_TRADING"
    STRUCTURING = "STRUCTURING"
    LAYERING = "LAYERING"
    WASH_TRADING = "WASH_TRADING"
    FRONT_RUNNING = "FRONT_RUNNING"
    PUMP_AND_DUMP = "PUMP_AND_DUMP"
    SPOOFING = "SPOOFING"
    PRICE_MANIPULATION = "PRICE_MANIPULATION"
    INSIDER_TRADING = "INSIDER_TRADING"
    SMURFING = "SMURFING"
    VELOCITY_CHECK = "VELOCITY_CHECK"


class RiskLevel(Enum):
    """Risk levels for suspicious activities."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class TradingPattern:
    """Trading pattern analysis data."""

    client_id: str
    symbol: str
    time_window: timedelta

    # Volume metrics
    total_volume: float = 0
    total_trades: int = 0
    avg_trade_size: float = 0

    # Timing metrics
    trades_per_hour: float = 0
    fastest_interval: Optional[timedelta] = None
    avg_interval: Optional[timedelta] = None

    # Price metrics
    price_impact: float = 0
    volatility: float = 0

    # Behavioral metrics
    round_trips: int = 0
    same_size_trades: int = 0
    structured_amounts: int = 0


@dataclass
class SuspiciousActivity:
    """Suspicious activity alert."""

    activity_id: str
    activity_type: SuspiciousActivityType
    risk_level: RiskLevel
    confidence_score: float  # 0.0 to 1.0

    # Context
    client_id: str
    description: str
    details: Dict[str, Any] = field(default_factory=dict)

    # Related data
    related_orders: List[str] = field(default_factory=list)
    related_symbols: List[str] = field(default_factory=list)
    time_period: Tuple[datetime, datetime] = field(
        default_factory=lambda: (datetime.now(timezone.utc), datetime.now(timezone.utc))
    )

    # Investigation
    status: str = "NEW"  # NEW, INVESTIGATING, CLOSED, ESCALATED
    assigned_to: Optional[str] = None
    investigation_notes: List[str] = field(default_factory=list)

    # Timestamps
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "activity_id": self.activity_id,
            "activity_type": self.activity_type.value,
            "risk_level": self.risk_level.value,
            "confidence_score": self.confidence_score,
            "client_id": self.client_id,
            "description": self.description,
            "details": self.details,
            "related_orders": self.related_orders,
            "related_symbols": self.related_symbols,
            "time_period": [
                self.time_period[0].isoformat(),
                self.time_period[1].isoformat(),
            ],
            "status": self.status,
            "assigned_to": self.assigned_to,
            "investigation_notes": self.investigation_notes,
            "detected_at": self.detected_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class TransactionMonitor:
    """Real-time transaction monitoring system."""

    def __init__(
        self,
        audit_logger: Optional[AuditLogger] = None,
        monitoring_window: timedelta = timedelta(hours=24),
        alert_threshold: float = 0.7,
    ):
        """Initialize transaction monitor.

        Args:
            audit_logger: Audit logger instance.
            monitoring_window: Time window for pattern analysis.
            alert_threshold: Confidence threshold for generating alerts.
        """
        self.audit_logger = audit_logger
        self.monitoring_window = monitoring_window
        self.alert_threshold = alert_threshold

        # Transaction history
        self.transaction_history: List[Dict[str, Any]] = []
        self.client_patterns: Dict[str, TradingPattern] = {}

        # Active alerts
        self.active_alerts: Dict[str, SuspiciousActivity] = {}
        self.alert_history: List[SuspiciousActivity] = []

        # Configuration
        self.thresholds = self._initialize_thresholds()

        # Statistics
        self.total_transactions_monitored = 0
        self.alerts_generated = 0
        self.false_positives = 0

        logger.info("Transaction monitor initialized")

    def _initialize_thresholds(self) -> Dict[str, Any]:
        """Initialize monitoring thresholds."""
        return {
            # Volume thresholds
            "unusual_volume_multiplier": 5.0,  # 5x normal volume
            "large_transaction_threshold": 1_000_000,  # $1M
            # Velocity thresholds
            "rapid_trading_interval": 60,  # seconds
            "max_trades_per_hour": 100,
            # Pattern thresholds
            "round_trip_time_window": 3600,  # 1 hour
            "structuring_threshold": 10_000,  # $10K
            "structuring_variance": 0.1,  # 10% variance
            # Behavioral thresholds
            "wash_trading_price_tolerance": 0.001,  # 0.1%
            "layering_depth": 5,  # minimum layers
            "spoofing_cancel_ratio": 0.8,  # 80% cancellation rate
        }

    async def monitor_transaction(
        self, transaction: Dict[str, Any]
    ) -> List[SuspiciousActivity]:
        """Monitor a transaction for suspicious activity.

        Args:
            transaction: Transaction data.

        Returns:
            List of suspicious activities detected.
        """
        self.total_transactions_monitored += 1

        # Add to history
        transaction["timestamp"] = datetime.now(timezone.utc)
        self.transaction_history.append(transaction)

        # Clean old transactions
        cutoff_time = datetime.now(timezone.utc) - self.monitoring_window
        self.transaction_history = [
            t for t in self.transaction_history if t["timestamp"] > cutoff_time
        ]

        # Analyze patterns
        alerts = []
        client_id = transaction.get("client_id")

        if client_id:
            # Update client pattern
            await self._update_client_pattern(client_id, transaction)

            # Run detection algorithms
            alerts.extend(await self._detect_unusual_volume(client_id, transaction))
            alerts.extend(await self._detect_rapid_trading(client_id, transaction))
            alerts.extend(await self._detect_round_trip_trading(client_id, transaction))
            alerts.extend(await self._detect_structuring(client_id, transaction))
            alerts.extend(await self._detect_wash_trading(client_id, transaction))
            alerts.extend(await self._detect_layering(client_id, transaction))
            alerts.extend(await self._detect_spoofing(client_id, transaction))

        # Process alerts
        for alert in alerts:
            await self._process_alert(alert)

        return alerts

    async def _update_client_pattern(self, client_id: str, transaction: Dict[str, Any]):
        """Update trading pattern for a client."""
        symbol = transaction.get("symbol", "UNKNOWN")
        pattern_key = f"{client_id}_{symbol}"

        if pattern_key not in self.client_patterns:
            self.client_patterns[pattern_key] = TradingPattern(
                client_id=client_id, symbol=symbol, time_window=self.monitoring_window
            )

        pattern = self.client_patterns[pattern_key]

        # Update volume metrics
        trade_size = transaction.get("quantity", 0) * transaction.get("price", 0)
        pattern.total_volume += trade_size
        pattern.total_trades += 1

        if pattern.total_trades > 0:
            pattern.avg_trade_size = pattern.total_volume / pattern.total_trades

            # Calculate trades per hour
            recent_trades = [
                t
                for t in self.transaction_history
                if (
                    t.get("client_id") == client_id
                    and t.get("symbol") == symbol
                    and t["timestamp"] > datetime.now(timezone.utc) - timedelta(hours=1)
                )
            ]
            pattern.trades_per_hour = len(recent_trades)

    async def _detect_unusual_volume(
        self, client_id: str, transaction: Dict[str, Any]
    ) -> List[SuspiciousActivity]:
        """Detect unusual trading volume."""
        alerts = []
        symbol = transaction.get("symbol", "UNKNOWN")
        trade_size = transaction.get("quantity", 0) * transaction.get("price", 0)

        # Get historical average
        client_transactions = [
            t
            for t in self.transaction_history[-100:]  # Last 100 transactions
            if (t.get("client_id") == client_id and t.get("symbol") == symbol)
        ]

        if len(client_transactions) >= 10:  # Need sufficient history
            avg_size = statistics.mean(
                [t.get("quantity", 0) * t.get("price", 0) for t in client_transactions]
            )

            if trade_size > avg_size * self.thresholds["unusual_volume_multiplier"]:
                confidence = min(
                    0.9,
                    trade_size
                    / (avg_size * self.thresholds["unusual_volume_multiplier"]),
                )

                if confidence >= self.alert_threshold:
                    alert = SuspiciousActivity(
                        activity_id=f"UV_{client_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                        activity_type=SuspiciousActivityType.UNUSUAL_VOLUME,
                        risk_level=(
                            RiskLevel.MEDIUM if confidence < 0.8 else RiskLevel.HIGH
                        ),
                        confidence_score=confidence,
                        client_id=client_id,
                        description=f"Unusual trading volume detected for {symbol}",
                        details={
                            "trade_size": trade_size,
                            "average_size": avg_size,
                            "multiplier": trade_size / avg_size,
                            "symbol": symbol,
                        },
                        related_orders=[transaction.get("order_id", "")],
                        related_symbols=[symbol],
                    )
                    alerts.append(alert)

        return alerts

    async def _detect_rapid_trading(
        self, client_id: str, transaction: Dict[str, Any]
    ) -> List[SuspiciousActivity]:
        """Detect rapid trading patterns."""
        alerts = []

        # Get recent transactions
        recent_window = datetime.now(timezone.utc) - timedelta(
            seconds=self.thresholds["rapid_trading_interval"]
        )
        recent_trades = [
            t
            for t in self.transaction_history
            if (t.get("client_id") == client_id and t["timestamp"] > recent_window)
        ]

        if len(recent_trades) >= 5:  # 5+ trades in rapid succession
            confidence = min(0.9, len(recent_trades) / 10)  # Max at 10 trades

            if confidence >= self.alert_threshold:
                alert = SuspiciousActivity(
                    activity_id=f"RT_{client_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                    activity_type=SuspiciousActivityType.RAPID_TRADING,
                    risk_level=RiskLevel.MEDIUM,
                    confidence_score=confidence,
                    client_id=client_id,
                    description=f"Rapid trading pattern detected",
                    details={
                        "trades_count": len(recent_trades),
                        "time_window_seconds": self.thresholds[
                            "rapid_trading_interval"
                        ],
                        "symbols": list(set(t.get("symbol") for t in recent_trades)),
                    },
                    related_orders=[t.get("order_id", "") for t in recent_trades],
                    time_period=(recent_window, datetime.now(timezone.utc)),
                )
                alerts.append(alert)

        return alerts

    async def _detect_round_trip_trading(
        self, client_id: str, transaction: Dict[str, Any]
    ) -> List[SuspiciousActivity]:
        """Detect round-trip trading patterns."""
        alerts = []
        symbol = transaction.get("symbol")
        side = transaction.get("side")
        quantity = transaction.get("quantity", 0)

        # Look for opposite trades within time window
        recent_window = datetime.now(timezone.utc) - timedelta(
            seconds=self.thresholds["round_trip_time_window"]
        )
        opposite_trades = [
            t
            for t in self.transaction_history
            if (
                t.get("client_id") == client_id
                and t.get("symbol") == symbol
                and t.get("side") != side  # Opposite side
                and abs(t.get("quantity", 0) - quantity)
                <= quantity * 0.1  # Similar quantity
                and t["timestamp"] > recent_window
            )
        ]

        if opposite_trades:
            confidence = min(0.8, len(opposite_trades) / 3)  # Max at 3 round trips

            if confidence >= self.alert_threshold:
                alert = SuspiciousActivity(
                    activity_id=f"RTT_{client_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                    activity_type=SuspiciousActivityType.ROUND_TRIP_TRADING,
                    risk_level=RiskLevel.MEDIUM,
                    confidence_score=confidence,
                    client_id=client_id,
                    description=f"Round-trip trading pattern detected for {symbol}",
                    details={
                        "round_trips": len(opposite_trades),
                        "symbol": symbol,
                        "quantity": quantity,
                        "time_window_hours": self.thresholds["round_trip_time_window"]
                        / 3600,
                    },
                    related_symbols=[symbol],
                )
                alerts.append(alert)

        return alerts

    async def _detect_structuring(
        self, client_id: str, transaction: Dict[str, Any]
    ) -> List[SuspiciousActivity]:
        """Detect structuring (breaking large amounts into smaller amounts)."""
        alerts = []
        trade_amount = transaction.get("quantity", 0) * transaction.get("price", 0)
        threshold = self.thresholds["structuring_threshold"]

        # Look for multiple trades just under the threshold
        if trade_amount < threshold and trade_amount > threshold * 0.8:
            recent_window = datetime.now(timezone.utc) - timedelta(hours=24)
            similar_trades = [
                t
                for t in self.transaction_history
                if (t.get("client_id") == client_id and t["timestamp"] > recent_window)
            ]

            # Check for similar amounts
            similar_amounts = [
                t
                for t in similar_trades
                if abs((t.get("quantity", 0) * t.get("price", 0)) - trade_amount)
                <= trade_amount * self.thresholds["structuring_variance"]
            ]

            if len(similar_amounts) >= 3:  # 3+ similar amounts
                total_amount = sum(
                    t.get("quantity", 0) * t.get("price", 0) for t in similar_amounts
                )
                confidence = min(0.9, len(similar_amounts) / 5)

                if confidence >= self.alert_threshold:
                    alert = SuspiciousActivity(
                        activity_id=f"STR_{client_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                        activity_type=SuspiciousActivityType.STRUCTURING,
                        risk_level=RiskLevel.HIGH,
                        confidence_score=confidence,
                        client_id=client_id,
                        description="Potential structuring pattern detected",
                        details={
                            "similar_trades": len(similar_amounts),
                            "individual_amount": trade_amount,
                            "total_amount": total_amount,
                            "threshold": threshold,
                        },
                        related_orders=[t.get("order_id", "") for t in similar_amounts],
                    )
                    alerts.append(alert)

        return alerts

    async def _detect_wash_trading(
        self, client_id: str, transaction: Dict[str, Any]
    ) -> List[SuspiciousActivity]:
        """Detect wash trading (trading with oneself)."""
        alerts = []
        symbol = transaction.get("symbol")
        price = transaction.get("price", 0)

        # Look for trades at same/similar prices
        recent_window = datetime.now(timezone.utc) - timedelta(hours=1)
        similar_price_trades = [
            t
            for t in self.transaction_history
            if (
                t.get("client_id") == client_id
                and t.get("symbol") == symbol
                and abs(t.get("price", 0) - price)
                <= price * self.thresholds["wash_trading_price_tolerance"]
                and t["timestamp"] > recent_window
            )
        ]

        if len(similar_price_trades) >= 4:  # Multiple trades at same price
            confidence = min(0.8, len(similar_price_trades) / 10)

            if confidence >= self.alert_threshold:
                alert = SuspiciousActivity(
                    activity_id=f"WT_{client_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                    activity_type=SuspiciousActivityType.WASH_TRADING,
                    risk_level=RiskLevel.HIGH,
                    confidence_score=confidence,
                    client_id=client_id,
                    description=f"Potential wash trading detected for {symbol}",
                    details={
                        "similar_price_trades": len(similar_price_trades),
                        "price": price,
                        "symbol": symbol,
                    },
                    related_symbols=[symbol],
                )
                alerts.append(alert)

        return alerts

    async def _detect_layering(
        self, client_id: str, transaction: Dict[str, Any]
    ) -> List[SuspiciousActivity]:
        """Detect layering (placing multiple orders to create false impression)."""
        alerts = []

        # Get recent orders (including cancellations)
        recent_window = datetime.now(timezone.utc) - timedelta(minutes=30)
        recent_orders = [
            t
            for t in self.transaction_history
            if (t.get("client_id") == client_id and t["timestamp"] > recent_window)
        ]

        # Look for multiple orders at different price levels
        symbols = set(t.get("symbol") for t in recent_orders)

        for symbol in symbols:
            symbol_orders = [t for t in recent_orders if t.get("symbol") == symbol]
            price_levels = set(t.get("price") for t in symbol_orders if t.get("price"))

            if len(price_levels) >= self.thresholds["layering_depth"]:
                confidence = min(0.9, len(price_levels) / 10)

                if confidence >= self.alert_threshold:
                    alert = SuspiciousActivity(
                        activity_id=f"LAY_{client_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                        activity_type=SuspiciousActivityType.LAYERING,
                        risk_level=RiskLevel.HIGH,
                        confidence_score=confidence,
                        client_id=client_id,
                        description=f"Potential layering detected for {symbol}",
                        details={
                            "price_levels": len(price_levels),
                            "orders_count": len(symbol_orders),
                            "symbol": symbol,
                        },
                        related_symbols=[symbol],
                    )
                    alerts.append(alert)

        return alerts

    async def _detect_spoofing(
        self, client_id: str, transaction: Dict[str, Any]
    ) -> List[SuspiciousActivity]:
        """Detect spoofing (placing orders with intent to cancel)."""
        alerts = []

        # Get order cancellation data
        recent_window = datetime.now(timezone.utc) - timedelta(hours=1)
        recent_activity = [
            t
            for t in self.transaction_history
            if (t.get("client_id") == client_id and t["timestamp"] > recent_window)
        ]

        # Count cancellations vs executions
        cancellations = len(
            [t for t in recent_activity if t.get("status") == "CANCELLED"]
        )
        executions = len([t for t in recent_activity if t.get("status") == "FILLED"])
        total_orders = cancellations + executions

        if total_orders >= 10:  # Sufficient sample size
            cancel_ratio = cancellations / total_orders

            if cancel_ratio >= self.thresholds["spoofing_cancel_ratio"]:
                confidence = min(0.9, cancel_ratio)

                if confidence >= self.alert_threshold:
                    alert = SuspiciousActivity(
                        activity_id=f"SPF_{client_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                        activity_type=SuspiciousActivityType.SPOOFING,
                        risk_level=RiskLevel.HIGH,
                        confidence_score=confidence,
                        client_id=client_id,
                        description="Potential spoofing pattern detected",
                        details={
                            "cancellation_ratio": cancel_ratio,
                            "total_orders": total_orders,
                            "cancellations": cancellations,
                            "executions": executions,
                        },
                    )
                    alerts.append(alert)

        return alerts

    async def _process_alert(self, alert: SuspiciousActivity):
        """Process a suspicious activity alert."""
        self.alerts_generated += 1

        # Add to active alerts
        self.active_alerts[alert.activity_id] = alert

        # Log to audit system
        if self.audit_logger:
            await self.audit_logger.log_compliance_event(
                event_type="SUSPICIOUS_ACTIVITY_DETECTED",
                message=f"Suspicious activity detected: {alert.description}",
                compliance_flags=[alert.activity_type.value],
                details=alert.to_dict(),
                severity=AuditSeverity.COMPLIANCE,
            )

        logger.warning(
            f"Suspicious activity detected: {alert.activity_type.value} "
            f"for client {alert.client_id} (confidence: {alert.confidence_score:.2f})"
        )

    def get_active_alerts(
        self, risk_level: Optional[RiskLevel] = None
    ) -> List[SuspiciousActivity]:
        """Get active alerts, optionally filtered by risk level."""
        alerts = list(self.active_alerts.values())

        if risk_level:
            alerts = [a for a in alerts if a.risk_level == risk_level]

        return sorted(alerts, key=lambda x: x.detected_at, reverse=True)

    def get_client_alerts(self, client_id: str) -> List[SuspiciousActivity]:
        """Get alerts for a specific client."""
        return [
            alert
            for alert in self.active_alerts.values()
            if alert.client_id == client_id
        ]

    def update_alert_status(
        self,
        activity_id: str,
        status: str,
        assigned_to: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> bool:
        """Update alert status."""
        if activity_id in self.active_alerts:
            alert = self.active_alerts[activity_id]
            alert.status = status
            alert.updated_at = datetime.now(timezone.utc)

            if assigned_to:
                alert.assigned_to = assigned_to

            if notes:
                alert.investigation_notes.append(
                    f"{datetime.now(timezone.utc).isoformat()}: {notes}"
                )

            # Move to history if closed
            if status in ["CLOSED", "FALSE_POSITIVE"]:
                self.alert_history.append(alert)
                del self.active_alerts[activity_id]

                if status == "FALSE_POSITIVE":
                    self.false_positives += 1

            return True

        return False

    def get_monitoring_stats(self) -> Dict[str, Any]:
        """Get transaction monitoring statistics."""
        return {
            "total_transactions_monitored": self.total_transactions_monitored,
            "alerts_generated": self.alerts_generated,
            "active_alerts": len(self.active_alerts),
            "false_positives": self.false_positives,
            "false_positive_rate": (
                self.false_positives / self.alerts_generated * 100
                if self.alerts_generated > 0
                else 0
            ),
            "alert_types": {
                activity_type.value: len(
                    [
                        a
                        for a in self.active_alerts.values()
                        if a.activity_type == activity_type
                    ]
                )
                for activity_type in SuspiciousActivityType
            },
            "risk_levels": {
                risk_level.value: len(
                    [
                        a
                        for a in self.active_alerts.values()
                        if a.risk_level == risk_level
                    ]
                )
                for risk_level in RiskLevel
            },
        }
