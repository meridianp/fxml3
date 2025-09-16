"""
Advanced Drawdown Control System for FXML4

This module implements sophisticated drawdown monitoring and control mechanisms
that automatically adjust position sizing, implement circuit breakers, and manage
recovery protocols to protect capital during adverse market conditions.

Key Features:
- Real-time drawdown monitoring (portfolio and individual positions)
- Dynamic position scaling based on drawdown levels
- Automatic risk reduction with circuit breakers
- Adaptive risk parameter adjustment
- Gradual recovery protocols after drawdown periods
- Historical drawdown analysis and learning
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats


class DrawdownLevel(Enum):
    """Drawdown severity levels"""

    NORMAL = "normal"  # 0-5% drawdown
    WARNING = "warning"  # 5-10% drawdown
    CRITICAL = "critical"  # 10-15% drawdown
    SEVERE = "severe"  # 15-20% drawdown
    EMERGENCY = "emergency"  # 20%+ drawdown


class RiskAction(Enum):
    """Risk management actions"""

    MAINTAIN = "maintain"  # Continue normal operations
    REDUCE_SIZE = "reduce_size"  # Reduce position sizes
    HALT_NEW = "halt_new"  # Halt new positions, maintain existing
    CLOSE_RISKY = "close_risky"  # Close highest risk positions
    EMERGENCY_CLOSE = "emergency_close"  # Close all positions


@dataclass
class DrawdownMetrics:
    """Comprehensive drawdown metrics"""

    current_drawdown: float  # Current drawdown from peak (0.0 to 1.0)
    max_drawdown: float  # Maximum historical drawdown
    drawdown_duration: int  # Days in current drawdown
    max_drawdown_duration: int  # Longest historical drawdown duration
    recovery_factor: float  # How much recovery from current drawdown
    underwater_curve: List[float]  # Historical underwater curve
    peak_date: datetime  # Date of current peak
    trough_date: Optional[datetime]  # Date of current trough
    recovery_date: Optional[datetime]  # Expected recovery date
    var_95: float  # 95% Value at Risk
    cvar_95: float  # 95% Conditional Value at Risk
    calmar_ratio: float  # Return/Max Drawdown ratio
    sterling_ratio: float  # Risk-adjusted return metric
    pain_index: float  # Severity of drawdowns over time


@dataclass
class PositionRisk:
    """Individual position risk assessment"""

    position_id: str
    symbol: str
    unrealized_pnl: Decimal
    position_size: float
    risk_score: float  # 0.0 to 1.0
    contribution_to_drawdown: float  # Position's contribution to portfolio drawdown
    time_in_position: timedelta
    correlation_risk: float  # Correlation with other positions
    volatility_risk: float  # Position volatility risk
    liquidity_risk: float  # Market liquidity risk
    priority_for_closure: int  # 1 (highest) to 10 (lowest)


@dataclass
class RiskParameters:
    """Dynamic risk management parameters"""

    max_position_size: float  # Maximum position size (% of portfolio)
    max_portfolio_exposure: float  # Maximum total exposure
    max_correlation: float  # Maximum correlation between positions
    volatility_limit: float  # Maximum position volatility
    var_limit: float  # Value at Risk limit
    drawdown_threshold: float  # Drawdown threshold for action
    recovery_multiplier: float  # Position size recovery rate
    circuit_breaker_threshold: float  # Emergency stop threshold

    # Dynamic scaling factors
    scale_at_5pct: float = 0.8  # Scale to 80% at 5% drawdown
    scale_at_10pct: float = 0.5  # Scale to 50% at 10% drawdown
    scale_at_15pct: float = 0.2  # Scale to 20% at 15% drawdown
    halt_at_20pct: float = 0.0  # Halt all new positions at 20% drawdown


class AdvancedDrawdownController:
    """
    Advanced drawdown control system that monitors portfolio performance
    and implements sophisticated risk reduction mechanisms.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize drawdown controller with configuration"""
        self.config = config
        self.logger = logging.getLogger(f"fxml4.risk.{self.__class__.__name__}")

        # Initialize risk parameters
        self.risk_params = RiskParameters(
            max_position_size=config.get("max_position_size", 0.02),
            max_portfolio_exposure=config.get("max_portfolio_exposure", 0.06),
            max_correlation=config.get("max_correlation", 0.7),
            volatility_limit=config.get("volatility_limit", 0.25),
            var_limit=config.get("var_limit", 0.02),
            drawdown_threshold=config.get("drawdown_threshold", 0.05),
            recovery_multiplier=config.get("recovery_multiplier", 1.2),
            circuit_breaker_threshold=config.get("circuit_breaker_threshold", 0.20),
        )

        # Portfolio tracking
        self.portfolio_values: List[Tuple[datetime, float]] = []
        self.portfolio_peak = 0.0
        self.portfolio_trough = float("inf")
        self.current_drawdown = 0.0
        self.max_drawdown = 0.0
        self.drawdown_start_date: Optional[datetime] = None

        # Position tracking
        self.active_positions: Dict[str, PositionRisk] = {}
        self.closed_positions: List[Dict[str, Any]] = []

        # Risk state
        self.current_risk_level = DrawdownLevel.NORMAL
        self.risk_actions_taken: List[Tuple[datetime, RiskAction, str]] = []
        self.position_scale_factor = 1.0

        # Performance tracking
        self.daily_returns: List[float] = []
        self.rolling_volatility = 0.0
        self.rolling_sharpe = 0.0

        # Emergency controls
        self.emergency_mode = False
        self.halt_new_positions = False
        self.force_close_all = False

        self.logger.info(
            f"Advanced Drawdown Controller initialized with config: {config}"
        )

    async def update_portfolio_value(self, timestamp: datetime, portfolio_value: float):
        """Update portfolio value and calculate drawdown metrics"""
        try:
            # Store portfolio value
            self.portfolio_values.append((timestamp, portfolio_value))

            # Calculate returns
            if len(self.portfolio_values) > 1:
                prev_value = self.portfolio_values[-2][1]
                daily_return = (portfolio_value - prev_value) / prev_value
                self.daily_returns.append(daily_return)

                # Keep rolling window of returns
                if len(self.daily_returns) > 252:  # 1 year of daily returns
                    self.daily_returns = self.daily_returns[-252:]

            # Update peak and calculate drawdown
            if portfolio_value > self.portfolio_peak:
                self.portfolio_peak = portfolio_value
                self.portfolio_trough = float("inf")

                # Check if recovering from drawdown
                if self.current_drawdown > 0:
                    await self._handle_drawdown_recovery(timestamp)
            else:
                # Track trough
                if portfolio_value < self.portfolio_trough:
                    self.portfolio_trough = portfolio_value

                # Calculate current drawdown
                self.current_drawdown = (
                    self.portfolio_peak - portfolio_value
                ) / self.portfolio_peak

                # Update max drawdown
                if self.current_drawdown > self.max_drawdown:
                    self.max_drawdown = self.current_drawdown

                # Track drawdown start
                if (
                    self.drawdown_start_date is None and self.current_drawdown > 0.001
                ):  # 0.1%
                    self.drawdown_start_date = timestamp

            # Update risk metrics
            await self._update_risk_metrics()

            # Evaluate risk level and take action
            await self._evaluate_risk_level(timestamp)

        except Exception as e:
            self.logger.error(f"Error updating portfolio value: {e}")

    async def update_position(self, position: PositionRisk):
        """Update individual position risk assessment"""
        try:
            # Store position
            self.active_positions[position.position_id] = position

            # Calculate position's contribution to drawdown
            position_pnl = float(position.unrealized_pnl)
            if position_pnl < 0:
                total_portfolio_value = (
                    self.portfolio_values[-1][1] if self.portfolio_values else 1.0
                )
                position.contribution_to_drawdown = (
                    abs(position_pnl) / total_portfolio_value
                )
            else:
                position.contribution_to_drawdown = 0.0

            # Calculate correlation risk (simplified)
            position.correlation_risk = await self._calculate_correlation_risk(position)

            # Calculate priority for closure
            position.priority_for_closure = await self._calculate_closure_priority(
                position
            )

            self.logger.debug(
                f"Updated position {position.position_id}: risk_score={position.risk_score:.3f}, "
                f"drawdown_contribution={position.contribution_to_drawdown:.3f}"
            )

        except Exception as e:
            self.logger.error(f"Error updating position {position.position_id}: {e}")

    async def close_position(self, position_id: str, reason: str = "manual"):
        """Close a position and update tracking"""
        try:
            if position_id in self.active_positions:
                position = self.active_positions.pop(position_id)

                # Store closed position info
                self.closed_positions.append(
                    {
                        "position_id": position_id,
                        "symbol": position.symbol,
                        "close_time": datetime.utcnow(),
                        "final_pnl": float(position.unrealized_pnl),
                        "reason": reason,
                        "risk_score": position.risk_score,
                    }
                )

                self.logger.info(f"Closed position {position_id} due to: {reason}")
                return True

        except Exception as e:
            self.logger.error(f"Error closing position {position_id}: {e}")

        return False

    async def get_position_size_adjustment(
        self, base_size: float, symbol: str
    ) -> float:
        """Calculate adjusted position size based on current drawdown"""
        try:
            # Base adjustment from drawdown level
            adjustment = self.position_scale_factor

            # Additional symbol-specific adjustments
            symbol_risk = await self._get_symbol_risk_factor(symbol)
            adjustment *= 1.0 - symbol_risk * 0.5  # Reduce size for risky symbols

            # Portfolio correlation adjustment
            correlation_adjustment = await self._get_correlation_adjustment(symbol)
            adjustment *= correlation_adjustment

            # Volatility adjustment
            volatility_adjustment = await self._get_volatility_adjustment()
            adjustment *= volatility_adjustment

            # Apply final adjustment
            adjusted_size = base_size * adjustment
            adjusted_size = max(adjusted_size, base_size * 0.1)  # Minimum 10% of base
            adjusted_size = min(adjusted_size, self.risk_params.max_position_size)

            self.logger.debug(
                f"Position size adjustment for {symbol}: {base_size:.4f} -> {adjusted_size:.4f} "
                f"(factor: {adjustment:.3f})"
            )

            return adjusted_size

        except Exception as e:
            self.logger.error(f"Error calculating position size adjustment: {e}")
            return base_size * 0.5  # Conservative fallback

    async def should_halt_new_positions(self) -> bool:
        """Check if new positions should be halted"""
        return (
            self.halt_new_positions
            or self.emergency_mode
            or self.current_risk_level
            in [DrawdownLevel.SEVERE, DrawdownLevel.EMERGENCY]
        )

    async def get_positions_to_close(self, max_positions: int = 5) -> List[str]:
        """Get list of positions that should be closed based on risk"""
        try:
            positions_to_close = []

            # Sort positions by closure priority
            sorted_positions = sorted(
                self.active_positions.values(),
                key=lambda p: (p.priority_for_closure, -p.contribution_to_drawdown),
            )

            # Select positions to close based on risk level
            close_count = 0
            if self.current_risk_level == DrawdownLevel.CRITICAL:
                close_count = min(2, len(sorted_positions))
            elif self.current_risk_level == DrawdownLevel.SEVERE:
                close_count = min(3, len(sorted_positions))
            elif self.current_risk_level == DrawdownLevel.EMERGENCY:
                close_count = len(sorted_positions)  # Close all

            for i in range(min(close_count, max_positions)):
                positions_to_close.append(sorted_positions[i].position_id)

            return positions_to_close

        except Exception as e:
            self.logger.error(f"Error getting positions to close: {e}")
            return []

    async def get_drawdown_metrics(self) -> DrawdownMetrics:
        """Calculate comprehensive drawdown metrics"""
        try:
            # Calculate underwater curve
            underwater_curve = []
            if self.portfolio_values:
                peak = 0.0
                for timestamp, value in self.portfolio_values:
                    if value > peak:
                        peak = value
                    drawdown = (peak - value) / peak if peak > 0 else 0.0
                    underwater_curve.append(drawdown)

            # Calculate duration metrics
            drawdown_duration = 0
            max_drawdown_duration = 0
            if self.drawdown_start_date and self.current_drawdown > 0:
                drawdown_duration = (datetime.utcnow() - self.drawdown_start_date).days

            # Calculate risk metrics
            var_95, cvar_95 = await self._calculate_var_metrics()
            calmar_ratio = await self._calculate_calmar_ratio()
            sterling_ratio = await self._calculate_sterling_ratio()
            pain_index = await self._calculate_pain_index(underwater_curve)

            # Recovery factor
            recovery_factor = 0.0
            if self.current_drawdown > 0:
                recovery_factor = 1.0 - (self.current_drawdown / self.max_drawdown)

            return DrawdownMetrics(
                current_drawdown=self.current_drawdown,
                max_drawdown=self.max_drawdown,
                drawdown_duration=drawdown_duration,
                max_drawdown_duration=max_drawdown_duration,
                recovery_factor=recovery_factor,
                underwater_curve=underwater_curve,
                peak_date=(
                    self.portfolio_values[-1][0]
                    if self.portfolio_values
                    else datetime.utcnow()
                ),
                trough_date=None,  # TODO: Calculate trough date
                recovery_date=None,  # TODO: Estimate recovery date
                var_95=var_95,
                cvar_95=cvar_95,
                calmar_ratio=calmar_ratio,
                sterling_ratio=sterling_ratio,
                pain_index=pain_index,
            )

        except Exception as e:
            self.logger.error(f"Error calculating drawdown metrics: {e}")
            # Return basic metrics on error
            return DrawdownMetrics(
                current_drawdown=self.current_drawdown,
                max_drawdown=self.max_drawdown,
                drawdown_duration=0,
                max_drawdown_duration=0,
                recovery_factor=0.0,
                underwater_curve=[],
                peak_date=datetime.utcnow(),
                trough_date=None,
                recovery_date=None,
                var_95=0.0,
                cvar_95=0.0,
                calmar_ratio=0.0,
                sterling_ratio=0.0,
                pain_index=0.0,
            )

    async def _update_risk_metrics(self):
        """Update rolling risk metrics"""
        try:
            if len(self.daily_returns) >= 30:  # Need at least 30 days
                # Rolling volatility (30-day)
                recent_returns = self.daily_returns[-30:]
                self.rolling_volatility = np.std(recent_returns) * np.sqrt(252)

                # Rolling Sharpe ratio
                if self.rolling_volatility > 0:
                    self.rolling_sharpe = (
                        np.mean(recent_returns) * 252
                    ) / self.rolling_volatility

        except Exception as e:
            self.logger.error(f"Error updating risk metrics: {e}")

    async def _evaluate_risk_level(self, timestamp: datetime):
        """Evaluate current risk level and take appropriate action"""
        try:
            # Determine risk level
            previous_level = self.current_risk_level

            if self.current_drawdown >= 0.20:
                self.current_risk_level = DrawdownLevel.EMERGENCY
            elif self.current_drawdown >= 0.15:
                self.current_risk_level = DrawdownLevel.SEVERE
            elif self.current_drawdown >= 0.10:
                self.current_risk_level = DrawdownLevel.CRITICAL
            elif self.current_drawdown >= 0.05:
                self.current_risk_level = DrawdownLevel.WARNING
            else:
                self.current_risk_level = DrawdownLevel.NORMAL

            # Update position scale factor
            if self.current_drawdown >= 0.15:
                self.position_scale_factor = self.risk_params.scale_at_15pct
            elif self.current_drawdown >= 0.10:
                self.position_scale_factor = self.risk_params.scale_at_10pct
            elif self.current_drawdown >= 0.05:
                self.position_scale_factor = self.risk_params.scale_at_5pct
            else:
                self.position_scale_factor = 1.0

            # Take action if risk level changed
            if self.current_risk_level != previous_level:
                await self._execute_risk_action(timestamp, previous_level)

        except Exception as e:
            self.logger.error(f"Error evaluating risk level: {e}")

    async def _execute_risk_action(
        self, timestamp: datetime, previous_level: DrawdownLevel
    ):
        """Execute risk management action based on current level"""
        try:
            action_taken = False
            reason = f"Drawdown level changed from {previous_level.value} to {self.current_risk_level.value}"

            if self.current_risk_level == DrawdownLevel.EMERGENCY:
                # Emergency: Close all positions
                self.emergency_mode = True
                self.halt_new_positions = True
                action = RiskAction.EMERGENCY_CLOSE
                action_taken = True

                self.logger.critical(
                    f"EMERGENCY MODE ACTIVATED: {self.current_drawdown:.1%} drawdown"
                )

            elif self.current_risk_level == DrawdownLevel.SEVERE:
                # Severe: Close risky positions, halt new
                self.halt_new_positions = True
                action = RiskAction.CLOSE_RISKY
                action_taken = True

                # Close highest risk positions
                positions_to_close = await self.get_positions_to_close(max_positions=3)
                for position_id in positions_to_close:
                    await self.close_position(
                        position_id, "severe_drawdown_risk_reduction"
                    )

                self.logger.error(
                    f"SEVERE DRAWDOWN: {self.current_drawdown:.1%} - Closing {len(positions_to_close)} risky positions"
                )

            elif self.current_risk_level == DrawdownLevel.CRITICAL:
                # Critical: Halt new positions, reduce existing
                self.halt_new_positions = True
                action = RiskAction.HALT_NEW
                action_taken = True

                self.logger.warning(
                    f"CRITICAL DRAWDOWN: {self.current_drawdown:.1%} - Halting new positions"
                )

            elif self.current_risk_level == DrawdownLevel.WARNING:
                # Warning: Reduce position sizes
                action = RiskAction.REDUCE_SIZE
                action_taken = True

                self.logger.warning(
                    f"DRAWDOWN WARNING: {self.current_drawdown:.1%} - Reducing position sizes"
                )

            elif (
                self.current_risk_level == DrawdownLevel.NORMAL
                and previous_level != DrawdownLevel.NORMAL
            ):
                # Recovery: Gradually restore normal operations
                if self.halt_new_positions:
                    self.halt_new_positions = False
                if self.emergency_mode:
                    self.emergency_mode = False
                action = RiskAction.MAINTAIN
                action_taken = True

                self.logger.info(
                    f"DRAWDOWN RECOVERY: {self.current_drawdown:.1%} - Restoring normal operations"
                )

            # Record action
            if action_taken:
                self.risk_actions_taken.append((timestamp, action, reason))

                # Keep only recent actions (last 100)
                if len(self.risk_actions_taken) > 100:
                    self.risk_actions_taken = self.risk_actions_taken[-100:]

        except Exception as e:
            self.logger.error(f"Error executing risk action: {e}")

    async def _handle_drawdown_recovery(self, timestamp: datetime):
        """Handle recovery from drawdown period"""
        try:
            if self.drawdown_start_date:
                recovery_duration = (timestamp - self.drawdown_start_date).days

                self.logger.info(
                    f"Portfolio recovered to new peak after {recovery_duration} days of drawdown"
                )

                # Reset drawdown tracking
                self.current_drawdown = 0.0
                self.drawdown_start_date = None

                # Gradually restore position sizing
                if self.position_scale_factor < 1.0:
                    self.position_scale_factor = min(
                        1.0,
                        self.position_scale_factor
                        * self.risk_params.recovery_multiplier,
                    )

        except Exception as e:
            self.logger.error(f"Error handling drawdown recovery: {e}")

    # Helper methods for risk calculations

    async def _calculate_correlation_risk(self, position: PositionRisk) -> float:
        """Calculate correlation risk for a position"""
        # Simplified correlation risk calculation
        return 0.3  # Placeholder

    async def _calculate_closure_priority(self, position: PositionRisk) -> int:
        """Calculate priority for closing position (1 = highest priority)"""
        try:
            # Factors for closure priority:
            # - Negative PnL (higher weight)
            # - High risk score
            # - Long time in position
            # - High contribution to drawdown

            priority_score = 0.0

            # PnL factor (0-4 points)
            if float(position.unrealized_pnl) < 0:
                pnl_ratio = abs(float(position.unrealized_pnl)) / 1000  # Normalize
                priority_score += min(4.0, pnl_ratio * 2)

            # Risk score factor (0-3 points)
            priority_score += position.risk_score * 3

            # Time factor (0-2 points)
            days_in_position = position.time_in_position.days
            if days_in_position > 7:  # Over a week
                priority_score += min(2.0, days_in_position / 14)

            # Drawdown contribution (0-3 points)
            priority_score += position.contribution_to_drawdown * 3

            # Convert to priority (1-10, lower is higher priority)
            priority = max(1, min(10, int(11 - priority_score)))

            return priority

        except Exception as e:
            self.logger.error(f"Error calculating closure priority: {e}")
            return 5  # Medium priority

    async def _get_symbol_risk_factor(self, symbol: str) -> float:
        """Get risk factor for specific symbol"""
        # Simplified symbol risk (could be enhanced with historical volatility, etc.)
        risk_factors = {
            "GBPUSD": 0.2,  # Medium risk
            "EURUSD": 0.15,  # Lower risk
            "USDJPY": 0.25,  # Higher risk
        }
        return risk_factors.get(symbol, 0.3)  # Default higher risk for unknown symbols

    async def _get_correlation_adjustment(self, symbol: str) -> float:
        """Get position size adjustment based on portfolio correlation"""
        # Simplified correlation adjustment
        return 0.9  # Slightly reduce for correlation

    async def _get_volatility_adjustment(self) -> float:
        """Get adjustment based on current market volatility"""
        if self.rolling_volatility > 0.3:  # High volatility
            return 0.7
        elif self.rolling_volatility < 0.15:  # Low volatility
            return 1.1
        else:
            return 1.0

    async def _calculate_var_metrics(self) -> Tuple[float, float]:
        """Calculate Value at Risk metrics"""
        try:
            if len(self.daily_returns) < 30:
                return 0.0, 0.0

            returns = np.array(self.daily_returns)
            var_95 = np.percentile(returns, 5)  # 5th percentile

            # Conditional VaR (expected shortfall)
            cvar_95 = returns[returns <= var_95].mean()

            return abs(var_95), abs(cvar_95)

        except Exception as e:
            self.logger.error(f"Error calculating VaR metrics: {e}")
            return 0.0, 0.0

    async def _calculate_calmar_ratio(self) -> float:
        """Calculate Calmar ratio (annual return / max drawdown)"""
        try:
            if len(self.daily_returns) < 30 or self.max_drawdown == 0:
                return 0.0

            annual_return = np.mean(self.daily_returns) * 252
            return annual_return / self.max_drawdown

        except Exception as e:
            self.logger.error(f"Error calculating Calmar ratio: {e}")
            return 0.0

    async def _calculate_sterling_ratio(self) -> float:
        """Calculate Sterling ratio"""
        # Simplified Sterling ratio calculation
        return await self._calculate_calmar_ratio() * 0.8

    async def _calculate_pain_index(self, underwater_curve: List[float]) -> float:
        """Calculate pain index (severity of drawdowns over time)"""
        try:
            if not underwater_curve:
                return 0.0

            # Pain index is the average drawdown over time
            return np.mean(underwater_curve)

        except Exception as e:
            self.logger.error(f"Error calculating pain index: {e}")
            return 0.0

    async def get_risk_summary(self) -> Dict[str, Any]:
        """Get comprehensive risk summary"""
        try:
            metrics = await self.get_drawdown_metrics()

            return {
                "timestamp": datetime.utcnow().isoformat(),
                "risk_level": self.current_risk_level.value,
                "current_drawdown": self.current_drawdown,
                "max_drawdown": self.max_drawdown,
                "position_scale_factor": self.position_scale_factor,
                "active_positions": len(self.active_positions),
                "halt_new_positions": self.halt_new_positions,
                "emergency_mode": self.emergency_mode,
                "portfolio_peak": self.portfolio_peak,
                "rolling_volatility": self.rolling_volatility,
                "rolling_sharpe": self.rolling_sharpe,
                "var_95": metrics.var_95,
                "cvar_95": metrics.cvar_95,
                "calmar_ratio": metrics.calmar_ratio,
                "pain_index": metrics.pain_index,
                "recent_actions": len(self.risk_actions_taken),
                "drawdown_duration_days": metrics.drawdown_duration,
            }

        except Exception as e:
            self.logger.error(f"Error getting risk summary: {e}")
            return {"error": str(e)}

    async def cleanup(self):
        """Cleanup resources"""
        try:
            self.logger.info("Advanced Drawdown Controller cleanup completed")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
