"""Backtesting Risk Manager Implementation.

This module provides risk management specifically designed for backtesting environments.
It focuses on portfolio-level risk management without real-time constraints.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..backtesting.event import OrderEvent, SignalEvent
from .base import (
    BaseRiskManager,
    Position,
    RiskCheckResult,
    RiskCheckType,
    RiskLimits,
    RiskMetrics,
    RiskViolation,
)

logger = logging.getLogger(__name__)


class BacktestRiskManager(BaseRiskManager):
    """Risk manager optimized for backtesting environments."""

    def __init__(self, limits: Optional[RiskLimits] = None):
        """Initialize backtest risk manager.

        Args:
            limits: Risk limits configuration.
        """
        super().__init__(limits)
        self.trade_history: List[Dict[str, Any]] = []
        self.equity_curve: List[float] = []

    def validate_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        account_balance: float,
        current_positions: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, List[RiskViolation]]:
        """Validate an order for backtesting.

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
        violations = []

        # Check position size limit
        position_value = abs(quantity * price)
        max_position_size = self.get_position_size_limit(symbol, account_balance)

        if position_value > max_position_size:
            violations.append(
                RiskViolation(
                    check_type=RiskCheckType.POSITION_LIMIT,
                    result=RiskCheckResult.FAIL,
                    message=f"Position size {position_value:.2f} exceeds limit {max_position_size:.2f}",
                    current_value=position_value,
                    limit_value=max_position_size,
                    severity="high",
                )
            )

        # Check daily loss limit
        daily_loss = sum(self.daily_pnl[-1:]) if self.daily_pnl else 0.0
        max_daily_loss = account_balance * self.limits.max_daily_loss

        if daily_loss < -max_daily_loss:
            violations.append(
                RiskViolation(
                    check_type=RiskCheckType.DAILY_LOSS_LIMIT,
                    result=RiskCheckResult.FAIL,
                    message=f"Daily loss {daily_loss:.2f} exceeds limit {max_daily_loss:.2f}",
                    current_value=abs(daily_loss),
                    limit_value=max_daily_loss,
                    severity="high",
                )
            )

        # Check drawdown limit
        drawdown_violation = self.check_drawdown_limit(account_balance)
        if drawdown_violation:
            violations.append(drawdown_violation)

        # Check correlation limit
        correlation_violation = self.check_correlation_limit(symbol, side)
        if correlation_violation:
            violations.append(correlation_violation)

        # Check if we have sufficient balance
        if side == "buy" and position_value > account_balance:
            violations.append(
                RiskViolation(
                    check_type=RiskCheckType.MARGIN_REQUIREMENT,
                    result=RiskCheckResult.FAIL,
                    message=f"Insufficient balance: {account_balance:.2f} < {position_value:.2f}",
                    current_value=account_balance,
                    limit_value=position_value,
                    severity="high",
                )
            )

        # Log violations
        for violation in violations:
            self.add_violation(violation)
            if violation.result == RiskCheckResult.FAIL:
                logger.warning(f"Risk violation: {violation.message}")

        # Order is valid if no FAIL violations
        is_valid = not any(v.result == RiskCheckResult.FAIL for v in violations)

        return is_valid, violations

    def update_position(self, position: Position) -> None:
        """Update position in backtesting risk manager.

        Args:
            position: Position to update.
        """
        self.positions[position.symbol] = position

        # Update equity curve
        total_value = sum(pos.market_value for pos in self.positions.values())
        self.equity_curve.append(total_value)

        # Update peak portfolio value
        if total_value > self.peak_portfolio_value:
            self.peak_portfolio_value = total_value

        self.current_portfolio_value = total_value

    def calculate_risk_metrics(self) -> RiskMetrics:
        """Calculate comprehensive risk metrics for backtesting.

        Returns:
            Risk metrics object.
        """
        positions = list(self.positions.values())

        if not positions:
            return RiskMetrics()

        # Calculate basic metrics
        total_exposure = sum(pos.notional_value for pos in positions)
        unrealized_pnl = sum(pos.unrealized_pnl for pos in positions)
        realized_pnl = sum(pos.realized_pnl for pos in positions)

        # Calculate drawdown
        if self.equity_curve:
            equity_series = pd.Series(self.equity_curve)
            running_max = equity_series.expanding().max()
            drawdown_series = (equity_series - running_max) / running_max
            max_drawdown = drawdown_series.min()
            current_drawdown = (
                drawdown_series.iloc[-1] if len(drawdown_series) > 0 else 0.0
            )
        else:
            max_drawdown = 0.0
            current_drawdown = 0.0

        # Calculate Sharpe ratio (simplified)
        if len(self.equity_curve) > 1:
            returns = pd.Series(self.equity_curve).pct_change().dropna()
            if len(returns) > 0 and returns.std() > 0:
                sharpe_ratio = (
                    returns.mean() / returns.std() * np.sqrt(252)
                )  # Annualized
            else:
                sharpe_ratio = 0.0
        else:
            sharpe_ratio = 0.0

        # Calculate win rate
        if self.trade_history:
            winning_trades = [t for t in self.trade_history if t.get("pnl", 0) > 0]
            win_rate = len(winning_trades) / len(self.trade_history)
        else:
            win_rate = 0.0

        # Calculate risk-reward ratio
        if self.trade_history:
            winning_trades = [
                t["pnl"] for t in self.trade_history if t.get("pnl", 0) > 0
            ]
            losing_trades = [
                t["pnl"] for t in self.trade_history if t.get("pnl", 0) < 0
            ]

            if winning_trades and losing_trades:
                avg_win = np.mean(winning_trades)
                avg_loss = np.mean(losing_trades)
                risk_reward_ratio = avg_win / abs(avg_loss)
            else:
                risk_reward_ratio = 0.0
        else:
            risk_reward_ratio = 0.0

        return RiskMetrics(
            total_exposure=total_exposure,
            daily_pnl=sum(self.daily_pnl[-1:]) if self.daily_pnl else 0.0,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=realized_pnl,
            max_drawdown=max_drawdown,
            current_drawdown=current_drawdown,
            portfolio_value=self.current_portfolio_value,
            sharpe_ratio=sharpe_ratio,
            win_rate=win_rate,
            risk_reward_ratio=risk_reward_ratio,
        )

    def validate_signal(
        self,
        signal: SignalEvent,
        portfolio_value: float,
        current_positions: Dict[str, Any],
    ) -> Tuple[bool, List[RiskViolation]]:
        """Validate a trading signal for backtesting.

        Args:
            signal: Signal event to validate.
            portfolio_value: Current portfolio value.
            current_positions: Current positions.

        Returns:
            Tuple of (is_valid, violations).
        """
        violations = []

        # Extract signal data
        symbol = signal.symbol
        direction = signal.direction
        confidence = signal.confidence

        # Check if signal confidence meets minimum threshold
        min_confidence = 0.6  # Configurable threshold
        if confidence < min_confidence:
            violations.append(
                RiskViolation(
                    check_type=RiskCheckType.RISK_REWARD_RATIO,
                    result=RiskCheckResult.WARN,
                    message=f"Signal confidence {confidence:.2f} below threshold {min_confidence:.2f}",
                    current_value=confidence,
                    limit_value=min_confidence,
                    severity="low",
                )
            )

        # Check if we already have a position in this symbol
        existing_position = current_positions.get(symbol)
        if existing_position:
            # Check if signal is trying to add to existing position
            existing_side = existing_position.get("side", "unknown")
            signal_side = "buy" if direction > 0 else "sell"

            if existing_side == signal_side:
                violations.append(
                    RiskViolation(
                        check_type=RiskCheckType.POSITION_LIMIT,
                        result=RiskCheckResult.WARN,
                        message=f"Signal would add to existing {existing_side} position in {symbol}",
                        current_value=existing_position.get("size", 0),
                        limit_value=self.limits.max_position_size,
                        severity="medium",
                    )
                )

        # Check correlation with existing positions
        correlation_violation = self.check_correlation_limit(
            symbol, "buy" if direction > 0 else "sell"
        )
        if correlation_violation:
            violations.append(correlation_violation)

        # Log violations
        for violation in violations:
            self.add_violation(violation)

        # Signal is valid if no FAIL violations
        is_valid = not any(v.result == RiskCheckResult.FAIL for v in violations)

        return is_valid, violations

    def record_trade(self, trade_data: Dict[str, Any]) -> None:
        """Record a completed trade for analysis.

        Args:
            trade_data: Trade data dictionary.
        """
        self.trade_history.append(trade_data)

        # Keep only last 10000 trades to prevent memory issues
        if len(self.trade_history) > 10000:
            self.trade_history = self.trade_history[-10000:]

    def reset_daily_metrics(self) -> None:
        """Reset daily metrics for new trading day."""
        if self.daily_pnl:
            # Archive the daily P&L
            self.daily_pnl.append(0.0)
        else:
            self.daily_pnl = [0.0]

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary.

        Returns:
            Performance summary dictionary.
        """
        metrics = self.calculate_risk_metrics()

        return {
            "total_trades": len(self.trade_history),
            "win_rate": metrics.win_rate,
            "sharpe_ratio": metrics.sharpe_ratio,
            "max_drawdown": metrics.max_drawdown,
            "current_drawdown": metrics.current_drawdown,
            "risk_reward_ratio": metrics.risk_reward_ratio,
            "total_pnl": metrics.realized_pnl + metrics.unrealized_pnl,
            "total_exposure": metrics.total_exposure,
            "portfolio_value": metrics.portfolio_value,
            "violations_count": len(self.violations),
            "high_severity_violations": len(
                [v for v in self.violations if v.severity == "high"]
            ),
        }
