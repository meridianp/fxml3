"""Risk Monitor - Real-time risk monitoring and enforcement."""

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Risk severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskType(str, Enum):
    """Types of risk violations."""

    POSITION_SIZE = "position_size"
    DAILY_LOSS = "daily_loss"
    DRAWDOWN = "drawdown"
    EXPOSURE = "exposure"
    CORRELATION = "correlation"
    MARGIN = "margin"
    VOLATILITY = "volatility"
    CONCENTRATION = "concentration"


class RiskAlert:
    """Risk alert object."""

    def __init__(self, alert_data: Dict[str, Any]):
        self.alert_id = alert_data["alert_id"]
        self.risk_type = RiskType(alert_data["risk_type"])
        self.risk_level = RiskLevel(alert_data["risk_level"])
        self.message = alert_data["message"]
        self.details = alert_data.get("details", {})
        self.created_at = alert_data.get("created_at", datetime.utcnow())
        self.resolved_at = alert_data.get("resolved_at")
        self.position_ids = alert_data.get("position_ids", [])
        self.action_required = alert_data.get("action_required", False)
        self.auto_resolved = alert_data.get("auto_resolved", False)


class RiskLimits:
    """Risk limit configuration."""

    def __init__(self, config: Dict[str, Any]):
        # Position limits
        self.max_position_size = Decimal(str(config.get("max_position_size", 100000)))
        self.max_positions = config.get("max_positions", 10)
        self.max_positions_per_symbol = config.get("max_positions_per_symbol", 3)

        # Loss limits
        self.daily_loss_limit = Decimal(str(config.get("daily_loss_limit", 0.02)))  # 2%
        self.weekly_loss_limit = Decimal(
            str(config.get("weekly_loss_limit", 0.05))
        )  # 5%
        self.monthly_loss_limit = Decimal(
            str(config.get("monthly_loss_limit", 0.10))
        )  # 10%
        self.max_drawdown = Decimal(str(config.get("max_drawdown", 0.15)))  # 15%

        # Exposure limits
        self.max_exposure = Decimal(
            str(config.get("max_exposure", 0.30))
        )  # 30% of account
        self.max_correlated_exposure = Decimal(
            str(config.get("max_correlated_exposure", 0.20))
        )  # 20%
        self.max_sector_exposure = Decimal(
            str(config.get("max_sector_exposure", 0.25))
        )  # 25%

        # Risk per trade
        self.max_risk_per_trade = Decimal(
            str(config.get("max_risk_per_trade", 0.02))
        )  # 2%
        self.max_risk_reward_ratio = Decimal(
            str(config.get("max_risk_reward_ratio", 0.33))
        )  # 1:3

        # Volatility limits
        self.max_volatility_exposure = Decimal(
            str(config.get("max_volatility_exposure", 2.0))
        )
        self.volatility_adjustment_enabled = config.get(
            "volatility_adjustment_enabled", True
        )

        # Time restrictions
        self.trading_hours = config.get("trading_hours", {})  # Symbol-specific hours
        self.news_blackout_minutes = config.get("news_blackout_minutes", 30)
        self.weekend_close_enabled = config.get("weekend_close_enabled", True)


class RiskMonitor:
    """Monitors and enforces risk limits in real-time."""

    def __init__(self):
        self.risk_limits = RiskLimits({})
        self.active_alerts: Dict[str, RiskAlert] = {}
        self.alert_history: List[RiskAlert] = []
        self.risk_metrics: Dict[str, Any] = {}
        self.position_risks: Dict[str, Dict[str, Any]] = {}
        self.daily_pnl: Dict[str, Decimal] = defaultdict(Decimal)
        self.correlation_matrix: Dict[Tuple[str, str], float] = {}
        self._lock = asyncio.Lock()

    async def initialize(self, config: Optional[Dict[str, Any]] = None):
        """Initialize risk monitor with configuration."""
        if config:
            self.risk_limits = RiskLimits(config)

        # Initialize correlation matrix
        await self._load_correlation_matrix()

        logger.info("Risk Monitor initialized")

    async def check_pre_trade_risk(
        self,
        trade_request: Dict[str, Any],
        account_data: Dict[str, Any],
        positions: List[Dict[str, Any]],
    ) -> Tuple[bool, List[str]]:
        """Check if a trade is allowed based on risk limits."""
        violations = []

        # Extract trade details
        symbol = trade_request["symbol"]
        side = trade_request["side"]
        quantity = Decimal(str(trade_request["quantity"]))
        entry_price = Decimal(str(trade_request.get("price", 0)))
        stop_loss = Decimal(str(trade_request.get("stop_loss", 0)))

        # Check position size limit
        position_value = quantity * entry_price
        if position_value > self.risk_limits.max_position_size:
            violations.append(
                f"Position size ${position_value} exceeds limit ${self.risk_limits.max_position_size}"
            )

        # Check max positions
        if len(positions) >= self.risk_limits.max_positions:
            violations.append(
                f"Maximum positions ({self.risk_limits.max_positions}) reached"
            )

        # Check positions per symbol
        symbol_positions = [p for p in positions if p["symbol"] == symbol]
        if len(symbol_positions) >= self.risk_limits.max_positions_per_symbol:
            violations.append(
                f"Maximum positions for {symbol} ({self.risk_limits.max_positions_per_symbol}) reached"
            )

        # Check risk per trade
        if stop_loss > 0:
            risk_amount = await self._calculate_trade_risk(
                trade_request, account_data["balance"]
            )
            risk_percent = risk_amount / account_data["balance"]
            if risk_percent > self.risk_limits.max_risk_per_trade:
                violations.append(
                    f"Trade risk {risk_percent:.1%} exceeds limit {self.risk_limits.max_risk_per_trade:.1%}"
                )

        # Check daily loss limit
        daily_loss = abs(self.daily_pnl.get(datetime.utcnow().date(), Decimal("0")))
        daily_loss_percent = daily_loss / account_data["balance"]
        if daily_loss_percent >= self.risk_limits.daily_loss_limit:
            violations.append(
                f"Daily loss limit ({self.risk_limits.daily_loss_limit:.1%}) reached"
            )

        # Check total exposure
        total_exposure = await self._calculate_total_exposure(
            positions, account_data["balance"]
        )
        new_exposure = total_exposure + (position_value / account_data["balance"])
        if new_exposure > self.risk_limits.max_exposure:
            violations.append(
                f"Total exposure {new_exposure:.1%} would exceed limit {self.risk_limits.max_exposure:.1%}"
            )

        # Check correlated exposure
        correlated_exposure = await self._calculate_correlated_exposure(
            symbol, positions, account_data["balance"]
        )
        if correlated_exposure > self.risk_limits.max_correlated_exposure:
            violations.append(
                f"Correlated exposure {correlated_exposure:.1%} exceeds limit"
            )

        # Check trading hours
        if not await self._check_trading_hours(symbol):
            violations.append(f"Outside trading hours for {symbol}")

        # Check volatility limits
        volatility_risk = await self._check_volatility_risk(symbol, position_value)
        if volatility_risk > self.risk_limits.max_volatility_exposure:
            violations.append(f"Volatility risk {volatility_risk:.1f} exceeds limit")

        return len(violations) == 0, violations

    async def update_position_risk(
        self, position: Dict[str, Any], market_data: Dict[str, Any]
    ):
        """Update risk metrics for a position."""
        position_id = position["position_id"]

        # Calculate position risk metrics
        risk_metrics = {
            "position_id": position_id,
            "symbol": position["symbol"],
            "position_value": position["quantity"] * market_data["current_price"],
            "unrealized_pnl": position.get("unrealized_pnl", 0),
            "risk_amount": await self._calculate_position_risk(position),
            "volatility_exposure": await self._calculate_volatility_exposure(
                position, market_data
            ),
            "time_risk": await self._calculate_time_risk(position),
            "updated_at": datetime.utcnow(),
        }

        async with self._lock:
            self.position_risks[position_id] = risk_metrics

        # Check for risk violations
        await self._check_position_violations(position, risk_metrics)

    async def update_daily_pnl(self, pnl_update: Dict[str, Any]):
        """Update daily P&L tracking."""
        date = pnl_update.get("date", datetime.utcnow().date())
        amount = Decimal(str(pnl_update["amount"]))

        async with self._lock:
            self.daily_pnl[date] += amount

        # Check daily loss limit
        if self.daily_pnl[date] < 0:
            await self._check_daily_loss_limit(date)

    async def check_portfolio_risk(
        self, positions: List[Dict[str, Any]], account_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Comprehensive portfolio risk check."""
        metrics = {
            "timestamp": datetime.utcnow(),
            "account_balance": account_data["balance"],
            "total_positions": len(positions),
            "violations": [],
        }

        # Calculate portfolio metrics
        metrics["total_exposure"] = await self._calculate_total_exposure(
            positions, account_data["balance"]
        )
        metrics["portfolio_var"] = await self._calculate_portfolio_var(positions)
        metrics["max_drawdown"] = await self._calculate_max_drawdown(account_data)
        metrics["correlation_risk"] = await self._calculate_correlation_risk(positions)

        # Check for violations
        if metrics["total_exposure"] > self.risk_limits.max_exposure:
            metrics["violations"].append(
                {
                    "type": RiskType.EXPOSURE,
                    "level": RiskLevel.HIGH,
                    "message": f"Total exposure {metrics['total_exposure']:.1%} exceeds limit",
                }
            )

        if metrics["max_drawdown"] > self.risk_limits.max_drawdown:
            metrics["violations"].append(
                {
                    "type": RiskType.DRAWDOWN,
                    "level": RiskLevel.CRITICAL,
                    "message": f"Drawdown {metrics['max_drawdown']:.1%} exceeds limit",
                }
            )

        # Update risk metrics
        async with self._lock:
            self.risk_metrics = metrics

        return metrics

    async def create_alert(
        self,
        risk_type: RiskType,
        risk_level: RiskLevel,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        position_ids: Optional[List[str]] = None,
        action_required: bool = False,
    ) -> RiskAlert:
        """Create a new risk alert."""
        alert_data = {
            "alert_id": f"alert_{datetime.utcnow().timestamp()}",
            "risk_type": risk_type,
            "risk_level": risk_level,
            "message": message,
            "details": details or {},
            "position_ids": position_ids or [],
            "action_required": action_required,
            "created_at": datetime.utcnow(),
        }

        alert = RiskAlert(alert_data)

        async with self._lock:
            self.active_alerts[alert.alert_id] = alert
            self.alert_history.append(alert)

        logger.warning(f"Risk alert created: {risk_level.value.upper()} - {message}")

        return alert

    async def resolve_alert(self, alert_id: str, auto_resolved: bool = False):
        """Resolve a risk alert."""
        async with self._lock:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.resolved_at = datetime.utcnow()
                alert.auto_resolved = auto_resolved
                del self.active_alerts[alert_id]
                logger.info(f"Risk alert resolved: {alert_id}")

    async def get_risk_summary(self) -> Dict[str, Any]:
        """Get current risk summary."""
        return {
            "active_alerts": len(self.active_alerts),
            "risk_metrics": self.risk_metrics,
            "daily_pnl": float(self.daily_pnl.get(datetime.utcnow().date(), 0)),
            "position_risks": list(self.position_risks.values()),
            "limits": {
                "daily_loss": float(self.risk_limits.daily_loss_limit),
                "max_drawdown": float(self.risk_limits.max_drawdown),
                "max_exposure": float(self.risk_limits.max_exposure),
                "max_positions": self.risk_limits.max_positions,
            },
        }

    async def _calculate_trade_risk(
        self, trade_request: Dict[str, Any], account_balance: Decimal
    ) -> Decimal:
        """Calculate risk amount for a trade."""
        quantity = Decimal(str(trade_request["quantity"]))
        entry_price = Decimal(str(trade_request.get("price", 0)))
        stop_loss = Decimal(str(trade_request.get("stop_loss", 0)))

        if stop_loss == 0:
            # Use default risk
            return account_balance * self.risk_limits.max_risk_per_trade

        side = trade_request["side"]
        if side == "BUY":
            risk_per_unit = entry_price - stop_loss
        else:
            risk_per_unit = stop_loss - entry_price

        return abs(risk_per_unit * quantity)

    async def _calculate_position_risk(self, position: Dict[str, Any]) -> Decimal:
        """Calculate current risk for a position."""
        quantity = Decimal(str(position["quantity"]))
        entry_price = Decimal(str(position["avg_entry_price"]))
        stop_loss = Decimal(str(position.get("stop_loss", 0)))

        if stop_loss == 0:
            return Decimal("0")

        if position["side"] == "BUY":
            risk_per_unit = entry_price - stop_loss
        else:
            risk_per_unit = stop_loss - entry_price

        return abs(risk_per_unit * quantity)

    async def _calculate_total_exposure(
        self, positions: List[Dict[str, Any]], account_balance: Decimal
    ) -> Decimal:
        """Calculate total portfolio exposure."""
        total_value = Decimal("0")

        for position in positions:
            position_value = Decimal(str(position["quantity"])) * Decimal(
                str(position["current_price"])
            )
            total_value += position_value

        return total_value / account_balance if account_balance > 0 else Decimal("0")

    async def _calculate_correlated_exposure(
        self, symbol: str, positions: List[Dict[str, Any]], account_balance: Decimal
    ) -> Decimal:
        """Calculate exposure to correlated assets."""
        correlated_value = Decimal("0")

        for position in positions:
            correlation = self.correlation_matrix.get((symbol, position["symbol"]), 0)
            if abs(correlation) > 0.7:  # High correlation threshold
                position_value = Decimal(str(position["quantity"])) * Decimal(
                    str(position["current_price"])
                )
                correlated_value += position_value * Decimal(str(abs(correlation)))

        return (
            correlated_value / account_balance if account_balance > 0 else Decimal("0")
        )

    async def _calculate_portfolio_var(
        self, positions: List[Dict[str, Any]], confidence_level: float = 0.95
    ) -> Decimal:
        """Calculate portfolio Value at Risk."""
        # Simplified VaR calculation
        # In production, use historical simulation or Monte Carlo
        total_risk = Decimal("0")

        for position in positions:
            position_risk = await self._calculate_position_risk(position)
            total_risk += position_risk

        return total_risk * Decimal(str(1.645))  # 95% confidence

    async def _calculate_max_drawdown(self, account_data: Dict[str, Any]) -> Decimal:
        """Calculate maximum drawdown from peak."""
        peak_balance = Decimal(
            str(account_data.get("peak_balance", account_data["balance"]))
        )
        current_balance = Decimal(str(account_data["balance"]))

        if peak_balance == 0:
            return Decimal("0")

        drawdown = (peak_balance - current_balance) / peak_balance
        return max(drawdown, Decimal("0"))

    async def _calculate_correlation_risk(
        self, positions: List[Dict[str, Any]]
    ) -> float:
        """Calculate portfolio correlation risk."""
        if len(positions) < 2:
            return 0.0

        # Calculate average correlation
        total_correlation = 0.0
        count = 0

        for i, pos1 in enumerate(positions):
            for pos2 in positions[i + 1 :]:
                correlation = self.correlation_matrix.get(
                    (pos1["symbol"], pos2["symbol"]), 0
                )
                total_correlation += abs(correlation)
                count += 1

        return total_correlation / count if count > 0 else 0.0

    async def _calculate_volatility_exposure(
        self, position: Dict[str, Any], market_data: Dict[str, Any]
    ) -> Decimal:
        """Calculate position volatility exposure."""
        position_value = Decimal(str(position["quantity"])) * Decimal(
            str(position["current_price"])
        )
        volatility = Decimal(str(market_data.get("volatility", 0.01)))  # Default 1%

        return position_value * volatility

    async def _calculate_time_risk(self, position: Dict[str, Any]) -> float:
        """Calculate time-based risk for position."""
        if not position.get("opened_at"):
            return 0.0

        # Time decay risk increases with holding period
        hold_time = datetime.utcnow() - position["opened_at"]
        days_held = hold_time.total_seconds() / 86400

        # Risk increases exponentially with time
        return min(1.0, days_held / 30)  # Max risk at 30 days

    async def _check_trading_hours(self, symbol: str) -> bool:
        """Check if within trading hours for symbol."""
        now = datetime.utcnow()

        # Get symbol-specific hours or use defaults
        hours = self.risk_limits.trading_hours.get(
            symbol,
            {
                "start": 0,  # 00:00 UTC
                "end": 23,  # 23:00 UTC
                "days": [0, 1, 2, 3, 4],  # Monday to Friday
            },
        )

        # Check day of week
        if now.weekday() not in hours.get("days", [0, 1, 2, 3, 4]):
            return False

        # Check hour
        if now.hour < hours.get("start", 0) or now.hour >= hours.get("end", 23):
            return False

        return True

    async def _check_volatility_risk(
        self, symbol: str, position_value: Decimal
    ) -> Decimal:
        """Check volatility-based risk."""
        # Simplified - would fetch actual volatility data
        base_volatility = Decimal("0.01")  # 1% daily volatility

        # Adjust for symbol characteristics
        if "JPY" in symbol:
            base_volatility *= Decimal("0.8")
        elif any(currency in symbol for currency in ["GBP", "AUD", "NZD"]):
            base_volatility *= Decimal("1.2")

        return (
            position_value * base_volatility * Decimal("2.0")
        )  # 2 standard deviations

    async def _check_position_violations(
        self, position: Dict[str, Any], risk_metrics: Dict[str, Any]
    ):
        """Check for position-specific risk violations."""
        # Check individual position risk
        if risk_metrics["risk_amount"] > self.risk_limits.max_position_size:
            await self.create_alert(
                RiskType.POSITION_SIZE,
                RiskLevel.HIGH,
                f"Position {position['position_id']} exceeds size limit",
                details=risk_metrics,
                position_ids=[position["position_id"]],
                action_required=True,
            )

        # Check volatility exposure
        if (
            risk_metrics["volatility_exposure"]
            > self.risk_limits.max_volatility_exposure
        ):
            await self.create_alert(
                RiskType.VOLATILITY,
                RiskLevel.MEDIUM,
                f"High volatility exposure for {position['symbol']}",
                details=risk_metrics,
                position_ids=[position["position_id"]],
            )

    async def _check_daily_loss_limit(self, date):
        """Check if daily loss limit is breached."""
        daily_loss = abs(self.daily_pnl[date])

        # This would need account balance from somewhere
        # For now, using a placeholder
        account_balance = Decimal("100000")

        loss_percent = daily_loss / account_balance

        if loss_percent >= self.risk_limits.daily_loss_limit:
            await self.create_alert(
                RiskType.DAILY_LOSS,
                RiskLevel.CRITICAL,
                f"Daily loss limit breached: {loss_percent:.1%}",
                details={"date": str(date), "loss": float(daily_loss)},
                action_required=True,
            )

    async def _load_correlation_matrix(self):
        """Load correlation matrix for symbols."""
        # Simplified correlation matrix
        # In production, calculate from historical data

        # Major forex pairs correlations
        correlations = {
            ("EURUSD", "GBPUSD"): 0.75,
            ("EURUSD", "USDCHF"): -0.85,
            ("EURUSD", "USDJPY"): -0.30,
            ("GBPUSD", "USDCHF"): -0.70,
            ("GBPUSD", "USDJPY"): -0.25,
            ("USDCHF", "USDJPY"): 0.40,
            ("AUDUSD", "NZDUSD"): 0.85,
            ("EURUSD", "EURJPY"): 0.60,
            ("USDJPY", "EURJPY"): 0.70,
        }

        # Add reverse correlations
        for (sym1, sym2), corr in list(correlations.items()):
            correlations[(sym2, sym1)] = corr

        self.correlation_matrix = correlations
