"""
Real-Time Trade Monitoring and Surveillance System for FXML4.

This module provides comprehensive trade surveillance capabilities including:
- Real-time monitoring of all trading activities
- Pattern detection for suspicious activities
- Regulatory compliance checking
- Automated alert generation
- Surveillance reporting and analytics
"""

import asyncio
import json
import logging
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from fxml4.api.auth.trading_audit_logger import (
    TradingEventType,
    get_trading_audit_logger,
)
from fxml4.brokers.compliance.audit_logger import (
    AuditCategory,
    AuditEvent,
    AuditSeverity,
    get_audit_logger,
)
from fxml4.config import get_config
from fxml4.fix.messages.orders import ExecutionReport, NewOrderSingle

logger = logging.getLogger(__name__)


class SurveillanceAlertType(Enum):
    """Types of surveillance alerts."""

    # Market Manipulation
    WASH_TRADING = "wash_trading"
    LAYERING = "layering"
    SPOOFING = "spoofing"
    RAMPING = "ramping"
    CROSS_TRADING = "cross_trading"

    # Insider Trading
    SUSPICIOUS_TIMING = "suspicious_timing"
    UNUSUAL_PROFIT_PATTERN = "unusual_profit_pattern"
    PRE_ANNOUNCEMENT_TRADING = "pre_announcement_trading"

    # Risk Management
    POSITION_LIMIT_BREACH = "position_limit_breach"
    CONCENTRATION_RISK = "concentration_risk"
    LEVERAGE_EXCESSIVE = "leverage_excessive"
    DRAWDOWN_EXCESSIVE = "drawdown_excessive"

    # Operational
    HIGH_FREQUENCY_PATTERN = "high_frequency_pattern"
    UNUSUAL_ORDER_SIZE = "unusual_order_size"
    AFTER_HOURS_ACTIVITY = "after_hours_activity"
    CROSS_BORDER_ACTIVITY = "cross_border_activity"

    # Regulatory
    BEST_EXECUTION_VIOLATION = "best_execution_violation"
    CLIENT_MONEY_SEGREGATION = "client_money_segregation"
    REPORTING_FAILURE = "reporting_failure"
    POSITION_REPORTING_BREACH = "position_reporting_breach"


class SurveillanceAlertSeverity(Enum):
    """Alert severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TradingPattern:
    """Trading pattern data structure."""

    symbol: str
    user_id: str
    account_id: Optional[str]

    # Pattern metrics
    trade_count: int = 0
    total_volume: float = 0.0
    avg_trade_size: float = 0.0
    price_impact: float = 0.0

    # Timing patterns
    trade_times: List[datetime] = field(default_factory=list)
    avg_time_between_trades: float = 0.0

    # Price patterns
    execution_prices: List[float] = field(default_factory=list)
    price_volatility: float = 0.0

    # Profit patterns
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    win_rate: float = 0.0

    # Risk metrics
    max_position: float = 0.0
    current_position: float = 0.0
    max_drawdown: float = 0.0


@dataclass
class SurveillanceAlert:
    """Surveillance alert data structure."""

    alert_id: str
    alert_type: SurveillanceAlertType
    severity: SurveillanceAlertSeverity
    timestamp: datetime

    # Trade details
    symbol: str
    user_id: str
    account_id: Optional[str]

    # Alert specifics
    description: str
    details: Dict[str, Any]
    pattern_data: Optional[TradingPattern] = None

    # Status tracking
    status: str = "open"  # open, investigating, resolved, false_positive
    assigned_to: Optional[str] = None
    resolution_notes: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Regulatory context
    regulatory_framework: List[str] = field(default_factory=list)
    potential_violations: List[str] = field(default_factory=list)


class TradeSurveillanceEngine:
    """Real-time trade monitoring and surveillance engine."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize surveillance engine."""
        self.config = config or get_config()

        # Core components
        self.audit_logger = get_audit_logger()
        self.trading_audit_logger = get_trading_audit_logger()

        # Pattern tracking
        self.trading_patterns: Dict[str, TradingPattern] = (
            {}
        )  # key: f"{user_id}:{symbol}"
        self.user_daily_stats: Dict[str, Dict[str, Any]] = {}  # key: user_id
        self.symbol_stats: Dict[str, Dict[str, Any]] = {}  # key: symbol

        # Alert management
        self.active_alerts: Dict[str, SurveillanceAlert] = {}
        self.alert_history: List[SurveillanceAlert] = []

        # Configuration
        self.monitoring_enabled = self.config.get(
            "compliance.surveillance.enabled", True
        )
        self.alert_thresholds = self._load_alert_thresholds()
        self.surveillance_hours = self.config.get(
            "compliance.surveillance.hours", "24/7"
        )

        # Performance tracking
        self.processed_trades_count = 0
        self.alerts_generated_count = 0

        # Background tasks
        self.monitoring_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None

        logger.info("Trade surveillance engine initialized")

    def _load_alert_thresholds(self) -> Dict[str, Any]:
        """Load surveillance alert thresholds from configuration."""
        return {
            # Wash trading detection
            "wash_trading": {
                "min_round_trips": 3,
                "time_window_minutes": 30,
                "price_tolerance": 0.0001,  # 1 pip for forex
            },
            # Layering detection
            "layering": {
                "min_orders": 5,
                "time_window_minutes": 10,
                "price_levels": 3,
                "cancellation_rate": 0.8,  # 80% cancellation rate
            },
            # High frequency patterns
            "high_frequency": {
                "trades_per_minute": 10,
                "orders_per_minute": 50,
                "time_window_minutes": 5,
            },
            # Position limits
            "position_limits": {
                "max_position_size": 10000000,  # $10M
                "max_daily_volume": 100000000,  # $100M
                "concentration_limit": 0.25,  # 25% of daily volume
            },
            # Unusual patterns
            "unusual_activity": {
                "size_multiplier": 10,  # 10x normal size
                "frequency_multiplier": 5,  # 5x normal frequency
                "profit_threshold": 0.1,  # 10% profit in short time
            },
        }

    async def start_monitoring(self):
        """Start the surveillance monitoring system."""
        if not self.monitoring_enabled:
            logger.info("Trade surveillance monitoring is disabled")
            return

        logger.info("Starting trade surveillance monitoring")

        # Start background monitoring tasks
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())

        # Log system startup
        await self.audit_logger.log_system_event(
            "surveillance_start",
            "Trade surveillance monitoring started",
            "surveillance_engine",
            details={
                "monitoring_enabled": self.monitoring_enabled,
                "surveillance_hours": self.surveillance_hours,
                "alert_thresholds": self.alert_thresholds,
            },
        )

    async def stop_monitoring(self):
        """Stop the surveillance monitoring system."""
        logger.info("Stopping trade surveillance monitoring")

        # Cancel background tasks
        if self.monitoring_task:
            self.monitoring_task.cancel()
        if self.cleanup_task:
            self.cleanup_task.cancel()

        # Wait for tasks to complete
        tasks = [
            t for t in [self.monitoring_task, self.cleanup_task] if t and not t.done()
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # Log system shutdown
        await self.audit_logger.log_system_event(
            "surveillance_stop",
            "Trade surveillance monitoring stopped",
            "surveillance_engine",
            details={
                "processed_trades": self.processed_trades_count,
                "alerts_generated": self.alerts_generated_count,
                "active_alerts": len(self.active_alerts),
            },
        )

    async def process_trade(
        self, execution_report: ExecutionReport, order: NewOrderSingle
    ):
        """Process a trade for surveillance monitoring."""
        try:
            if not self.monitoring_enabled:
                return

            self.processed_trades_count += 1

            # Extract trade details
            user_id = getattr(order, "user_id", "unknown")
            account_id = getattr(order, "account_id", None)
            symbol = execution_report.symbol

            # Update trading patterns
            pattern_key = f"{user_id}:{symbol}"
            await self._update_trading_pattern(pattern_key, execution_report, order)

            # Run surveillance checks
            await self._run_surveillance_checks(execution_report, order)

            # Update statistics
            await self._update_statistics(execution_report, order)

        except Exception as e:
            logger.error(f"Error processing trade for surveillance: {e}")

    async def _update_trading_pattern(
        self, pattern_key: str, execution_report: ExecutionReport, order: NewOrderSingle
    ):
        """Update trading pattern for user/symbol combination."""
        try:
            # Get or create pattern
            if pattern_key not in self.trading_patterns:
                user_id, symbol = pattern_key.split(":", 1)
                self.trading_patterns[pattern_key] = TradingPattern(
                    symbol=symbol,
                    user_id=user_id,
                    account_id=getattr(order, "account_id", None),
                )

            pattern = self.trading_patterns[pattern_key]

            # Update pattern metrics
            pattern.trade_count += 1
            pattern.total_volume += execution_report.last_qty
            pattern.avg_trade_size = pattern.total_volume / pattern.trade_count

            # Update timing patterns
            trade_time = datetime.now(timezone.utc)
            pattern.trade_times.append(trade_time)

            if len(pattern.trade_times) > 1:
                time_diffs = [
                    (
                        pattern.trade_times[i] - pattern.trade_times[i - 1]
                    ).total_seconds()
                    for i in range(1, len(pattern.trade_times))
                ]
                pattern.avg_time_between_trades = statistics.mean(time_diffs)

            # Update price patterns
            if execution_report.last_px:
                pattern.execution_prices.append(execution_report.last_px)
                if len(pattern.execution_prices) > 1:
                    pattern.price_volatility = statistics.stdev(
                        pattern.execution_prices
                    )

            # Keep only recent data (last 24 hours)
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
            pattern.trade_times = [t for t in pattern.trade_times if t > cutoff_time]
            if len(pattern.execution_prices) > 100:
                pattern.execution_prices = pattern.execution_prices[-100:]

        except Exception as e:
            logger.error(f"Error updating trading pattern: {e}")

    async def _run_surveillance_checks(
        self, execution_report: ExecutionReport, order: NewOrderSingle
    ):
        """Run all surveillance checks on the trade."""
        try:
            user_id = getattr(order, "user_id", "unknown")
            symbol = execution_report.symbol
            pattern_key = f"{user_id}:{symbol}"

            if pattern_key in self.trading_patterns:
                pattern = self.trading_patterns[pattern_key]

                # Run individual checks
                await self._check_wash_trading(pattern)
                await self._check_layering_pattern(pattern)
                await self._check_high_frequency_trading(pattern)
                await self._check_unusual_order_size(execution_report, order)
                await self._check_position_limits(pattern)
                await self._check_timing_patterns(pattern)

        except Exception as e:
            logger.error(f"Error running surveillance checks: {e}")

    async def _check_wash_trading(self, pattern: TradingPattern):
        """Check for potential wash trading patterns."""
        try:
            thresholds = self.alert_thresholds["wash_trading"]

            # Look for round-trip trades at similar prices within time window
            if len(pattern.execution_prices) < thresholds["min_round_trips"] * 2:
                return

            recent_trades = pattern.trade_times[-thresholds["min_round_trips"] * 2 :]
            recent_prices = pattern.execution_prices[
                -thresholds["min_round_trips"] * 2 :
            ]

            if not recent_trades:
                return

            # Check if trades occurred within time window
            time_span = (recent_trades[-1] - recent_trades[0]).total_seconds() / 60
            if time_span > thresholds["time_window_minutes"]:
                return

            # Check for price similarity (potential wash trading)
            price_range = max(recent_prices) - min(recent_prices)
            avg_price = statistics.mean(recent_prices)
            price_tolerance = avg_price * thresholds["price_tolerance"]

            if price_range <= price_tolerance:
                # Potential wash trading detected
                await self._generate_alert(
                    SurveillanceAlertType.WASH_TRADING,
                    SurveillanceAlertSeverity.HIGH,
                    pattern.symbol,
                    pattern.user_id,
                    pattern.account_id,
                    "Potential wash trading detected: multiple trades at similar prices",
                    {
                        "trade_count": len(recent_trades),
                        "time_window_minutes": time_span,
                        "price_range": price_range,
                        "avg_price": avg_price,
                        "trades": list(zip(recent_trades, recent_prices)),
                    },
                    pattern,
                )

        except Exception as e:
            logger.error(f"Error checking wash trading: {e}")

    async def _check_layering_pattern(self, pattern: TradingPattern):
        """Check for layering/spoofing patterns."""
        try:
            thresholds = self.alert_thresholds["layering"]

            # This would require order book data and cancel/fill ratios
            # For now, check for high order-to-trade ratio
            if pattern.trade_count > 0:
                # Simplified check - would need more sophisticated order tracking
                recent_trade_frequency = len(pattern.trade_times) / max(
                    1, len(pattern.trade_times)
                )

                if recent_trade_frequency > thresholds["min_orders"]:
                    await self._generate_alert(
                        SurveillanceAlertType.LAYERING,
                        SurveillanceAlertSeverity.MEDIUM,
                        pattern.symbol,
                        pattern.user_id,
                        pattern.account_id,
                        "Potential layering pattern detected: high order activity",
                        {
                            "trade_count": pattern.trade_count,
                            "recent_frequency": recent_trade_frequency,
                        },
                        pattern,
                    )

        except Exception as e:
            logger.error(f"Error checking layering pattern: {e}")

    async def _check_high_frequency_trading(self, pattern: TradingPattern):
        """Check for excessive high-frequency trading."""
        try:
            thresholds = self.alert_thresholds["high_frequency"]

            # Check recent trading frequency
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(minutes=thresholds["time_window_minutes"])

            recent_trades = [t for t in pattern.trade_times if t > cutoff]
            trades_per_minute = len(recent_trades) / thresholds["time_window_minutes"]

            if trades_per_minute > thresholds["trades_per_minute"]:
                await self._generate_alert(
                    SurveillanceAlertType.HIGH_FREQUENCY_PATTERN,
                    SurveillanceAlertSeverity.MEDIUM,
                    pattern.symbol,
                    pattern.user_id,
                    pattern.account_id,
                    "High frequency trading pattern detected",
                    {
                        "trades_per_minute": trades_per_minute,
                        "time_window": thresholds["time_window_minutes"],
                        "threshold": thresholds["trades_per_minute"],
                    },
                    pattern,
                )

        except Exception as e:
            logger.error(f"Error checking high frequency trading: {e}")

    async def _check_unusual_order_size(
        self, execution_report: ExecutionReport, order: NewOrderSingle
    ):
        """Check for unusual order sizes."""
        try:
            symbol = execution_report.symbol
            order_size = execution_report.last_qty

            # Get historical average for this symbol
            if symbol in self.symbol_stats:
                avg_size = self.symbol_stats[symbol].get("avg_order_size", order_size)
                threshold = self.alert_thresholds["unusual_activity"]["size_multiplier"]

                if order_size > avg_size * threshold:
                    await self._generate_alert(
                        SurveillanceAlertType.UNUSUAL_ORDER_SIZE,
                        SurveillanceAlertSeverity.MEDIUM,
                        symbol,
                        getattr(order, "user_id", "unknown"),
                        getattr(order, "account_id", None),
                        "Unusual order size detected",
                        {
                            "order_size": order_size,
                            "average_size": avg_size,
                            "multiplier": order_size / avg_size,
                            "threshold": threshold,
                        },
                    )

        except Exception as e:
            logger.error(f"Error checking unusual order size: {e}")

    async def _check_position_limits(self, pattern: TradingPattern):
        """Check for position limit violations."""
        try:
            limits = self.alert_thresholds["position_limits"]

            # Check current position against limits
            if abs(pattern.current_position) > limits["max_position_size"]:
                await self._generate_alert(
                    SurveillanceAlertType.POSITION_LIMIT_BREACH,
                    SurveillanceAlertSeverity.HIGH,
                    pattern.symbol,
                    pattern.user_id,
                    pattern.account_id,
                    "Position limit exceeded",
                    {
                        "current_position": pattern.current_position,
                        "limit": limits["max_position_size"],
                        "breach_amount": abs(pattern.current_position)
                        - limits["max_position_size"],
                    },
                    pattern,
                )

            # Check daily volume limits
            if pattern.total_volume > limits["max_daily_volume"]:
                await self._generate_alert(
                    SurveillanceAlertType.CONCENTRATION_RISK,
                    SurveillanceAlertSeverity.MEDIUM,
                    pattern.symbol,
                    pattern.user_id,
                    pattern.account_id,
                    "Daily volume limit exceeded",
                    {
                        "daily_volume": pattern.total_volume,
                        "limit": limits["max_daily_volume"],
                        "breach_amount": pattern.total_volume
                        - limits["max_daily_volume"],
                    },
                    pattern,
                )

        except Exception as e:
            logger.error(f"Error checking position limits: {e}")

    async def _check_timing_patterns(self, pattern: TradingPattern):
        """Check for suspicious timing patterns."""
        try:
            # Check for after-hours trading
            now = datetime.now(timezone.utc)
            current_hour = now.hour

            # Define market hours (example: 8 AM to 5 PM UTC)
            if current_hour < 8 or current_hour > 17:
                recent_trades = [
                    t for t in pattern.trade_times if (now - t).total_seconds() < 3600
                ]  # Last hour

                if len(recent_trades) > 5:  # Threshold for after-hours activity
                    await self._generate_alert(
                        SurveillanceAlertType.AFTER_HOURS_ACTIVITY,
                        SurveillanceAlertSeverity.LOW,
                        pattern.symbol,
                        pattern.user_id,
                        pattern.account_id,
                        "Unusual after-hours trading activity",
                        {
                            "current_hour": current_hour,
                            "recent_trades": len(recent_trades),
                            "time_window": "1 hour",
                        },
                        pattern,
                    )

        except Exception as e:
            logger.error(f"Error checking timing patterns: {e}")

    async def _generate_alert(
        self,
        alert_type: SurveillanceAlertType,
        severity: SurveillanceAlertSeverity,
        symbol: str,
        user_id: str,
        account_id: Optional[str],
        description: str,
        details: Dict[str, Any],
        pattern: Optional[TradingPattern] = None,
    ):
        """Generate a surveillance alert."""
        try:
            alert_id = f"{alert_type.value}_{user_id}_{symbol}_{int(datetime.now().timestamp())}"

            alert = SurveillanceAlert(
                alert_id=alert_id,
                alert_type=alert_type,
                severity=severity,
                timestamp=datetime.now(timezone.utc),
                symbol=symbol,
                user_id=user_id,
                account_id=account_id,
                description=description,
                details=details,
                pattern_data=pattern,
                regulatory_framework=["MiFID II", "ESMA", "FCA"],
                potential_violations=self._get_potential_violations(alert_type),
            )

            # Store alert
            self.active_alerts[alert_id] = alert
            self.alert_history.append(alert)
            self.alerts_generated_count += 1

            # Log alert to audit system
            await self.audit_logger.log_compliance_event(
                alert_type.value,
                f"Surveillance alert generated: {description}",
                [alert_type.value],
                details={
                    "alert_id": alert_id,
                    "severity": severity.value,
                    "symbol": symbol,
                    "user_id": user_id,
                    "account_id": account_id,
                    "alert_details": details,
                },
            )

            # Send to trading audit logger as well
            await self.trading_audit_logger.log_compliance_event(
                TradingEventType.COMPLIANCE_CHECK_FAILED,
                [alert_type.value],
                {
                    "alert_id": alert_id,
                    "severity": severity.value,
                    "description": description,
                    **details,
                },
                symbol=symbol,
            )

            logger.warning(f"Surveillance alert generated: {alert_id} - {description}")

        except Exception as e:
            logger.error(f"Error generating surveillance alert: {e}")

    def _get_potential_violations(self, alert_type: SurveillanceAlertType) -> List[str]:
        """Get potential regulatory violations for alert type."""
        violation_mapping = {
            SurveillanceAlertType.WASH_TRADING: [
                "Market Manipulation",
                "MAR Article 15",
            ],
            SurveillanceAlertType.LAYERING: [
                "Market Manipulation",
                "Spoofing",
                "MAR Article 15",
            ],
            SurveillanceAlertType.SPOOFING: ["Market Manipulation", "MAR Article 15"],
            SurveillanceAlertType.RAMPING: ["Market Manipulation", "MAR Article 15"],
            SurveillanceAlertType.SUSPICIOUS_TIMING: [
                "Insider Trading",
                "MAR Article 14",
            ],
            SurveillanceAlertType.POSITION_LIMIT_BREACH: [
                "Position Limit Violation",
                "MiFID II",
            ],
            SurveillanceAlertType.BEST_EXECUTION_VIOLATION: [
                "Best Execution",
                "MiFID II Article 27",
            ],
            SurveillanceAlertType.REPORTING_FAILURE: [
                "Transaction Reporting",
                "MiFID II Article 26",
            ],
        }

        return violation_mapping.get(alert_type, ["Compliance Violation"])

    async def _update_statistics(
        self, execution_report: ExecutionReport, order: NewOrderSingle
    ):
        """Update trading statistics for surveillance analysis."""
        try:
            symbol = execution_report.symbol
            user_id = getattr(order, "user_id", "unknown")

            # Update symbol statistics
            if symbol not in self.symbol_stats:
                self.symbol_stats[symbol] = {
                    "total_volume": 0.0,
                    "trade_count": 0,
                    "avg_order_size": 0.0,
                    "price_history": deque(maxlen=1000),
                }

            symbol_stats = self.symbol_stats[symbol]
            symbol_stats["total_volume"] += execution_report.last_qty
            symbol_stats["trade_count"] += 1
            symbol_stats["avg_order_size"] = (
                symbol_stats["total_volume"] / symbol_stats["trade_count"]
            )

            if execution_report.last_px:
                symbol_stats["price_history"].append(execution_report.last_px)

            # Update user statistics
            if user_id not in self.user_daily_stats:
                self.user_daily_stats[user_id] = {
                    "daily_volume": 0.0,
                    "daily_trades": 0,
                    "symbols_traded": set(),
                    "last_reset": datetime.now(timezone.utc).date(),
                }

            user_stats = self.user_daily_stats[user_id]

            # Reset daily stats if new day
            current_date = datetime.now(timezone.utc).date()
            if user_stats["last_reset"] != current_date:
                user_stats["daily_volume"] = 0.0
                user_stats["daily_trades"] = 0
                user_stats["symbols_traded"] = set()
                user_stats["last_reset"] = current_date

            user_stats["daily_volume"] += execution_report.last_qty
            user_stats["daily_trades"] += 1
            user_stats["symbols_traded"].add(symbol)

        except Exception as e:
            logger.error(f"Error updating surveillance statistics: {e}")

    async def _monitoring_loop(self):
        """Background monitoring loop for surveillance."""
        while True:
            try:
                # Perform periodic surveillance tasks
                await self._analyze_patterns()
                await self._check_alert_escalation()
                await self._generate_surveillance_reports()

                # Sleep for monitoring interval
                await asyncio.sleep(60)  # Check every minute

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in surveillance monitoring loop: {e}")
                await asyncio.sleep(60)

    async def _cleanup_loop(self):
        """Background cleanup loop for surveillance data."""
        while True:
            try:
                # Clean up old data
                await self._cleanup_old_patterns()
                await self._cleanup_old_alerts()

                # Sleep for cleanup interval
                await asyncio.sleep(3600)  # Clean up every hour

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in surveillance cleanup loop: {e}")
                await asyncio.sleep(3600)

    async def _analyze_patterns(self):
        """Analyze accumulated trading patterns."""
        try:
            # Perform cross-pattern analysis
            for pattern_key, pattern in self.trading_patterns.items():
                # Check for complex patterns that require multiple data points
                await self._check_cross_symbol_patterns(pattern)
                await self._check_velocity_patterns(pattern)

        except Exception as e:
            logger.error(f"Error analyzing patterns: {e}")

    async def _check_cross_symbol_patterns(self, pattern: TradingPattern):
        """Check for patterns across multiple symbols."""
        try:
            user_patterns = [
                p
                for p in self.trading_patterns.values()
                if p.user_id == pattern.user_id
            ]

            if len(user_patterns) > 5:  # Trading many symbols
                total_volume = sum(p.total_volume for p in user_patterns)
                if (
                    total_volume
                    > self.alert_thresholds["position_limits"]["max_daily_volume"]
                ):
                    await self._generate_alert(
                        SurveillanceAlertType.CONCENTRATION_RISK,
                        SurveillanceAlertSeverity.MEDIUM,
                        "MULTI",
                        pattern.user_id,
                        pattern.account_id,
                        "Cross-symbol concentration risk detected",
                        {
                            "symbols_count": len(user_patterns),
                            "total_volume": total_volume,
                            "symbols": [p.symbol for p in user_patterns],
                        },
                    )

        except Exception as e:
            logger.error(f"Error checking cross-symbol patterns: {e}")

    async def _check_velocity_patterns(self, pattern: TradingPattern):
        """Check for velocity-based suspicious patterns."""
        try:
            if len(pattern.trade_times) >= 10:
                # Calculate trading velocity acceleration
                recent_times = pattern.trade_times[-10:]
                time_diffs = [
                    (recent_times[i] - recent_times[i - 1]).total_seconds()
                    for i in range(1, len(recent_times))
                ]

                if time_diffs:
                    avg_interval = statistics.mean(time_diffs)
                    if avg_interval < 60:  # Less than 1 minute average
                        await self._generate_alert(
                            SurveillanceAlertType.HIGH_FREQUENCY_PATTERN,
                            SurveillanceAlertSeverity.HIGH,
                            pattern.symbol,
                            pattern.user_id,
                            pattern.account_id,
                            "Extreme trading velocity detected",
                            {
                                "avg_interval_seconds": avg_interval,
                                "recent_trades": len(recent_times),
                                "velocity_threshold": 60,
                            },
                            pattern,
                        )

        except Exception as e:
            logger.error(f"Error checking velocity patterns: {e}")

    async def _check_alert_escalation(self):
        """Check if alerts need escalation."""
        try:
            current_time = datetime.now(timezone.utc)

            for alert in self.active_alerts.values():
                if alert.status == "open":
                    age_minutes = (current_time - alert.timestamp).total_seconds() / 60

                    # Escalate high severity alerts after 15 minutes
                    if (
                        alert.severity == SurveillanceAlertSeverity.HIGH
                        and age_minutes > 15
                    ):
                        await self._escalate_alert(alert)

                    # Escalate critical alerts after 5 minutes
                    elif (
                        alert.severity == SurveillanceAlertSeverity.CRITICAL
                        and age_minutes > 5
                    ):
                        await self._escalate_alert(alert)

        except Exception as e:
            logger.error(f"Error checking alert escalation: {e}")

    async def _escalate_alert(self, alert: SurveillanceAlert):
        """Escalate a surveillance alert."""
        try:
            # Log escalation
            await self.audit_logger.log_compliance_event(
                "alert_escalation",
                f"Surveillance alert escalated: {alert.alert_id}",
                ["ESCALATION"],
                details={
                    "alert_id": alert.alert_id,
                    "original_severity": alert.severity.value,
                    "escalation_reason": "Time threshold exceeded",
                    "age_minutes": (
                        datetime.now(timezone.utc) - alert.timestamp
                    ).total_seconds()
                    / 60,
                },
            )

            # In a real system, this would:
            # - Send notifications to compliance officers
            # - Create tickets in compliance management system
            # - Trigger automated responses if configured

            logger.critical(
                f"Surveillance alert escalated: {alert.alert_id} - {alert.description}"
            )

        except Exception as e:
            logger.error(f"Error escalating alert: {e}")

    async def _generate_surveillance_reports(self):
        """Generate periodic surveillance reports."""
        try:
            # Generate hourly summary report
            current_hour = datetime.now(timezone.utc).hour
            if current_hour != getattr(self, "_last_report_hour", -1):
                await self._generate_hourly_report()
                self._last_report_hour = current_hour

        except Exception as e:
            logger.error(f"Error generating surveillance reports: {e}")

    async def _generate_hourly_report(self):
        """Generate hourly surveillance summary report."""
        try:
            current_time = datetime.now(timezone.utc)
            hour_start = current_time.replace(minute=0, second=0, microsecond=0)

            # Count alerts by type and severity
            recent_alerts = [
                alert for alert in self.alert_history if alert.timestamp >= hour_start
            ]

            alert_summary = {
                "total_alerts": len(recent_alerts),
                "by_severity": {},
                "by_type": {},
                "active_investigations": len(
                    [
                        a
                        for a in self.active_alerts.values()
                        if a.status == "investigating"
                    ]
                ),
            }

            for alert in recent_alerts:
                # Count by severity
                severity = alert.severity.value
                alert_summary["by_severity"][severity] = (
                    alert_summary["by_severity"].get(severity, 0) + 1
                )

                # Count by type
                alert_type = alert.alert_type.value
                alert_summary["by_type"][alert_type] = (
                    alert_summary["by_type"].get(alert_type, 0) + 1
                )

            # Log report
            await self.audit_logger.log_compliance_event(
                "surveillance_report",
                f"Hourly surveillance report generated",
                ["REPORTING"],
                details={
                    "report_period": f"{hour_start.isoformat()} - {current_time.isoformat()}",
                    "processed_trades": self.processed_trades_count,
                    "alert_summary": alert_summary,
                    "monitoring_patterns": len(self.trading_patterns),
                },
            )

        except Exception as e:
            logger.error(f"Error generating hourly report: {e}")

    async def _cleanup_old_patterns(self):
        """Clean up old trading patterns."""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=1)

            patterns_to_remove = []
            for pattern_key, pattern in self.trading_patterns.items():
                if pattern.trade_times and pattern.trade_times[-1] < cutoff_time:
                    patterns_to_remove.append(pattern_key)

            for pattern_key in patterns_to_remove:
                del self.trading_patterns[pattern_key]

            if patterns_to_remove:
                logger.info(
                    f"Cleaned up {len(patterns_to_remove)} old trading patterns"
                )

        except Exception as e:
            logger.error(f"Error cleaning up old patterns: {e}")

    async def _cleanup_old_alerts(self):
        """Clean up old resolved alerts."""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=30)

            # Remove old alerts from active list if resolved
            alerts_to_remove = []
            for alert_id, alert in self.active_alerts.items():
                if (
                    alert.status in ["resolved", "false_positive"]
                    and alert.updated_at < cutoff_time
                ):
                    alerts_to_remove.append(alert_id)

            for alert_id in alerts_to_remove:
                del self.active_alerts[alert_id]

            if alerts_to_remove:
                logger.info(f"Cleaned up {len(alerts_to_remove)} old resolved alerts")

        except Exception as e:
            logger.error(f"Error cleaning up old alerts: {e}")

    # Public API methods for alert management

    def get_active_alerts(self) -> List[SurveillanceAlert]:
        """Get all active surveillance alerts."""
        return list(self.active_alerts.values())

    def get_alert_by_id(self, alert_id: str) -> Optional[SurveillanceAlert]:
        """Get specific alert by ID."""
        return self.active_alerts.get(alert_id)

    async def update_alert_status(
        self,
        alert_id: str,
        status: str,
        assigned_to: Optional[str] = None,
        resolution_notes: Optional[str] = None,
    ) -> bool:
        """Update alert status and assignment."""
        try:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.status = status
                alert.updated_at = datetime.now(timezone.utc)

                if assigned_to:
                    alert.assigned_to = assigned_to
                if resolution_notes:
                    alert.resolution_notes = resolution_notes

                # Log status update
                await self.audit_logger.log_compliance_event(
                    "alert_status_update",
                    f"Surveillance alert status updated: {alert_id}",
                    ["STATUS_UPDATE"],
                    details={
                        "alert_id": alert_id,
                        "new_status": status,
                        "assigned_to": assigned_to,
                        "resolution_notes": resolution_notes,
                    },
                )

                return True

            return False

        except Exception as e:
            logger.error(f"Error updating alert status: {e}")
            return False

    def get_surveillance_statistics(self) -> Dict[str, Any]:
        """Get surveillance engine statistics."""
        return {
            "processed_trades": self.processed_trades_count,
            "alerts_generated": self.alerts_generated_count,
            "active_alerts": len(self.active_alerts),
            "monitoring_patterns": len(self.trading_patterns),
            "symbols_monitored": len(self.symbol_stats),
            "users_monitored": len(self.user_daily_stats),
            "monitoring_enabled": self.monitoring_enabled,
        }


# Global surveillance engine instance
_surveillance_engine: Optional[TradeSurveillanceEngine] = None


def get_surveillance_engine(
    config: Optional[Dict[str, Any]] = None
) -> TradeSurveillanceEngine:
    """Get global surveillance engine instance."""
    global _surveillance_engine
    if _surveillance_engine is None:
        _surveillance_engine = TradeSurveillanceEngine(config)
    return _surveillance_engine


async def initialize_surveillance_engine(
    config: Optional[Dict[str, Any]] = None
) -> TradeSurveillanceEngine:
    """Initialize and start the surveillance engine."""
    engine = get_surveillance_engine(config)
    await engine.start_monitoring()
    return engine


async def shutdown_surveillance_engine():
    """Shutdown the surveillance engine."""
    global _surveillance_engine
    if _surveillance_engine:
        await _surveillance_engine.stop_monitoring()
        _surveillance_engine = None
