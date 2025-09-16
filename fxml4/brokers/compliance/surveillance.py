"""
Trade Surveillance Engine for FXML4 Trading Platform.

This module provides real-time trade surveillance capabilities including
unusual activity detection, pattern recognition, and alert generation.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SurveillanceAlert:
    """Trade surveillance alert."""

    alert_id: str
    alert_type: str
    severity: AlertSeverity
    detected_at: datetime
    description: str
    details: Dict[str, Any]
    confidence_score: float = 0.8


class TradeSurveillanceEngine:
    """Real-time trade surveillance and monitoring engine."""

    def __init__(
        self,
        volume_threshold_multiplier: float = 5.0,
        price_movement_threshold: float = 0.02,
        frequency_threshold: int = 10,
    ):
        self.volume_threshold_multiplier = volume_threshold_multiplier
        self.price_movement_threshold = price_movement_threshold
        self.frequency_threshold = frequency_threshold

    async def detect_unusual_volume(
        self, trades: List[Any], db: AsyncSession
    ) -> List[SurveillanceAlert]:
        """Detect unusual trading volumes."""
        alerts = []

        if not trades:
            return alerts

        # Calculate average volume
        volumes = [float(trade.quantity) for trade in trades]
        avg_volume = sum(volumes) / len(volumes)

        # Check for unusually large trades
        for trade in trades:
            if float(trade.quantity) > avg_volume * self.volume_threshold_multiplier:
                alert = SurveillanceAlert(
                    alert_id=f"VOL_{trade.trade_id}",
                    alert_type="UNUSUAL_VOLUME",
                    severity=AlertSeverity.HIGH,
                    detected_at=datetime.now(timezone.utc),
                    description=f"Unusually large trade volume detected",
                    details={
                        "trade_id": trade.trade_id,
                        "volume": float(trade.quantity),
                        "average_volume": avg_volume,
                        "multiplier": float(trade.quantity) / avg_volume,
                    },
                    confidence_score=0.9,
                )
                alerts.append(alert)

        return alerts

    async def detect_rapid_fire_trading(
        self, trades: List[Any], db: AsyncSession
    ) -> List[SurveillanceAlert]:
        """Detect rapid-fire trading patterns."""
        alerts = []

        if len(trades) <= self.frequency_threshold:
            return alerts

        # Check for trades within 1-minute window exceeding threshold
        recent_trades = []
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=1)

        for trade in trades:
            if trade.timestamp >= cutoff_time:
                recent_trades.append(trade)

        if len(recent_trades) > self.frequency_threshold:
            alert = SurveillanceAlert(
                alert_id=f"RF_{recent_trades[0].user_id}",
                alert_type="RAPID_FIRE_TRADING",
                severity=AlertSeverity.MEDIUM,
                detected_at=datetime.now(timezone.utc),
                description=f"Rapid-fire trading pattern detected",
                details={
                    "trade_count": len(recent_trades),
                    "threshold": self.frequency_threshold,
                    "time_window_minutes": 1,
                    "user_id": recent_trades[0].user_id,
                },
                confidence_score=0.8,
            )
            alerts.append(alert)

        return alerts

    async def analyze_price_manipulation_pattern(
        self, pattern: Dict[str, Any], db: AsyncSession
    ) -> Optional[SurveillanceAlert]:
        """Analyze potential price manipulation patterns."""

        trades = pattern.get("trades", [])
        if len(trades) < 3:
            return None

        # Simple heuristic: buy pressure followed by large sell
        buy_trades = [t for t in trades if t["side"] == "buy"]
        sell_trades = [t for t in trades if t["side"] == "sell"]

        if len(buy_trades) >= 2 and len(sell_trades) >= 1:
            total_buy_volume = sum(t["quantity"] for t in buy_trades)
            total_sell_volume = sum(t["quantity"] for t in sell_trades)

            if total_sell_volume > total_buy_volume:
                return SurveillanceAlert(
                    alert_id=f"PM_{pattern['symbol']}",
                    alert_type="POTENTIAL_MANIPULATION",
                    severity=AlertSeverity.HIGH,
                    detected_at=datetime.now(timezone.utc),
                    description="Potential price manipulation pattern detected",
                    details={
                        "symbol": pattern["symbol"],
                        "buy_volume": total_buy_volume,
                        "sell_volume": total_sell_volume,
                        "pattern_duration": pattern.get("time_window"),
                    },
                    confidence_score=0.75,
                )

        return None
