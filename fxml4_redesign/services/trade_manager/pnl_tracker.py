"""P&L Tracker - Tracks realized and unrealized P&L with detailed analytics."""

import asyncio
import json
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class PnLPeriod(str, Enum):
    """P&L calculation periods."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    ALL_TIME = "all_time"


class TradeOutcome(str, Enum):
    """Trade outcome classification."""

    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    OPEN = "open"


class PnLMetrics:
    """Comprehensive P&L metrics."""

    def __init__(self):
        self.realized_pnl = Decimal("0")
        self.unrealized_pnl = Decimal("0")
        self.gross_profit = Decimal("0")
        self.gross_loss = Decimal("0")
        self.commission_paid = Decimal("0")
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.breakeven_trades = 0
        self.largest_win = Decimal("0")
        self.largest_loss = Decimal("0")
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        self.max_consecutive_wins = 0
        self.max_consecutive_losses = 0
        self.average_win = Decimal("0")
        self.average_loss = Decimal("0")
        self.win_rate = 0.0
        self.profit_factor = 0.0
        self.expectancy = Decimal("0")
        self.sharpe_ratio = 0.0
        self.sortino_ratio = 0.0
        self.max_drawdown = Decimal("0")
        self.max_drawdown_duration = timedelta()
        self.current_drawdown = Decimal("0")
        self.peak_balance = Decimal("0")
        self.roi = 0.0
        self.trades_by_symbol: Dict[str, int] = defaultdict(int)
        self.pnl_by_symbol: Dict[str, Decimal] = defaultdict(Decimal)
        self.pnl_by_strategy: Dict[str, Decimal] = defaultdict(Decimal)
        self.daily_pnl: Dict[date, Decimal] = defaultdict(Decimal)
        self.hourly_pnl: Dict[int, Decimal] = defaultdict(Decimal)

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "realized_pnl": float(self.realized_pnl),
            "unrealized_pnl": float(self.unrealized_pnl),
            "total_pnl": float(self.realized_pnl + self.unrealized_pnl),
            "gross_profit": float(self.gross_profit),
            "gross_loss": float(self.gross_loss),
            "commission_paid": float(self.commission_paid),
            "net_profit": float(self.realized_pnl - self.commission_paid),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "breakeven_trades": self.breakeven_trades,
            "largest_win": float(self.largest_win),
            "largest_loss": float(self.largest_loss),
            "consecutive_wins": self.consecutive_wins,
            "consecutive_losses": self.consecutive_losses,
            "max_consecutive_wins": self.max_consecutive_wins,
            "max_consecutive_losses": self.max_consecutive_losses,
            "average_win": float(self.average_win),
            "average_loss": float(self.average_loss),
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "expectancy": float(self.expectancy),
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "max_drawdown": float(self.max_drawdown),
            "max_drawdown_duration_days": self.max_drawdown_duration.days,
            "current_drawdown": float(self.current_drawdown),
            "roi": self.roi,
            "trades_by_symbol": dict(self.trades_by_symbol),
            "pnl_by_symbol": {k: float(v) for k, v in self.pnl_by_symbol.items()},
            "pnl_by_strategy": {k: float(v) for k, v in self.pnl_by_strategy.items()},
        }


class PnLTracker:
    """Tracks and analyzes P&L across all trading activities."""

    def __init__(self):
        self.trades_history: List[Dict[str, Any]] = []
        self.open_positions: Dict[str, Dict[str, Any]] = {}
        self.daily_metrics: Dict[date, PnLMetrics] = {}
        self.period_metrics: Dict[PnLPeriod, PnLMetrics] = {
            period: PnLMetrics() for period in PnLPeriod
        }
        self.current_metrics = PnLMetrics()
        self.account_balance = Decimal("100000")  # Default starting balance
        self.peak_balance = Decimal("100000")
        self.equity_curve: List[Tuple[datetime, Decimal]] = []
        self.drawdown_periods: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()

    async def initialize(self, starting_balance: Optional[Decimal] = None):
        """Initialize P&L tracker with starting balance."""
        if starting_balance:
            self.account_balance = starting_balance
            self.peak_balance = starting_balance

        # Add initial equity curve point
        self.equity_curve.append((datetime.utcnow(), self.account_balance))

        logger.info(f"P&L Tracker initialized with balance: {self.account_balance}")

    async def record_trade_open(self, trade_data: Dict[str, Any]):
        """Record a new trade opening."""
        async with self._lock:
            position_id = trade_data["position_id"]

            # Store in open positions
            self.open_positions[position_id] = {
                "position_id": position_id,
                "symbol": trade_data["symbol"],
                "side": trade_data["side"],
                "quantity": Decimal(str(trade_data["quantity"])),
                "entry_price": Decimal(str(trade_data["entry_price"])),
                "entry_time": trade_data.get("entry_time", datetime.utcnow()),
                "strategy": trade_data.get("strategy", "unknown"),
                "stop_loss": Decimal(str(trade_data.get("stop_loss", 0))),
                "take_profit": Decimal(str(trade_data.get("take_profit", 0))),
                "commission": Decimal(str(trade_data.get("commission", 0))),
                "unrealized_pnl": Decimal("0"),
            }

            # Update commission paid
            self.current_metrics.commission_paid += self.open_positions[position_id][
                "commission"
            ]

    async def update_position_pnl(
        self,
        position_id: str,
        current_price: Decimal,
        partial_exit: Optional[Dict[str, Any]] = None,
    ):
        """Update P&L for an open position."""
        async with self._lock:
            if position_id not in self.open_positions:
                return

            position = self.open_positions[position_id]

            # Handle partial exit
            if partial_exit:
                exit_quantity = Decimal(str(partial_exit["quantity"]))
                exit_price = Decimal(str(partial_exit["price"]))
                commission = Decimal(str(partial_exit.get("commission", 0)))

                # Calculate realized P&L for partial exit
                if position["side"] == "BUY":
                    pnl = (exit_price - position["entry_price"]) * exit_quantity
                else:
                    pnl = (position["entry_price"] - exit_price) * exit_quantity

                # Update position
                position["quantity"] -= exit_quantity

                # Record partial close
                await self._record_trade_close(
                    position_id=f"{position_id}_partial_{datetime.utcnow().timestamp()}",
                    position_data=position,
                    exit_price=exit_price,
                    exit_quantity=exit_quantity,
                    commission=commission,
                    pnl=pnl,
                )

            # Update unrealized P&L for remaining position
            if position["quantity"] > 0:
                if position["side"] == "BUY":
                    position["unrealized_pnl"] = (
                        current_price - position["entry_price"]
                    ) * position["quantity"]
                else:
                    position["unrealized_pnl"] = (
                        position["entry_price"] - current_price
                    ) * position["quantity"]

                # Update current metrics
                await self._update_unrealized_totals()

    async def record_trade_close(
        self,
        position_id: str,
        exit_price: Decimal,
        exit_time: Optional[datetime] = None,
        commission: Decimal = Decimal("0"),
    ):
        """Record a trade closing."""
        async with self._lock:
            if position_id not in self.open_positions:
                logger.warning(f"Position {position_id} not found in open positions")
                return

            position = self.open_positions[position_id]

            # Calculate P&L
            if position["side"] == "BUY":
                pnl = (exit_price - position["entry_price"]) * position["quantity"]
            else:
                pnl = (position["entry_price"] - exit_price) * position["quantity"]

            # Record the close
            await self._record_trade_close(
                position_id=position_id,
                position_data=position,
                exit_price=exit_price,
                exit_quantity=position["quantity"],
                commission=commission,
                pnl=pnl,
                exit_time=exit_time,
            )

            # Remove from open positions
            del self.open_positions[position_id]

            # Update unrealized totals
            await self._update_unrealized_totals()

    async def _record_trade_close(
        self,
        position_id: str,
        position_data: Dict[str, Any],
        exit_price: Decimal,
        exit_quantity: Decimal,
        commission: Decimal,
        pnl: Decimal,
        exit_time: Optional[datetime] = None,
    ):
        """Internal method to record trade close."""
        exit_time = exit_time or datetime.utcnow()

        # Create trade record
        trade_record = {
            "position_id": position_id,
            "symbol": position_data["symbol"],
            "side": position_data["side"],
            "quantity": float(exit_quantity),
            "entry_price": float(position_data["entry_price"]),
            "exit_price": float(exit_price),
            "entry_time": position_data["entry_time"],
            "exit_time": exit_time,
            "duration": (exit_time - position_data["entry_time"]).total_seconds()
            / 60,  # minutes
            "gross_pnl": float(pnl),
            "commission": float(commission),
            "net_pnl": float(pnl - commission),
            "strategy": position_data["strategy"],
            "outcome": self._classify_outcome(pnl - commission),
        }

        # Add to history
        self.trades_history.append(trade_record)

        # Update metrics
        await self._update_metrics_for_trade(trade_record)

        # Update equity curve
        self.account_balance += pnl - commission
        self.equity_curve.append((exit_time, self.account_balance))

        # Check for new peak
        if self.account_balance > self.peak_balance:
            self.peak_balance = self.account_balance

        # Update drawdown
        await self._update_drawdown()

    async def _update_metrics_for_trade(self, trade_record: Dict[str, Any]):
        """Update all metrics for a completed trade."""
        pnl = Decimal(str(trade_record["net_pnl"]))
        symbol = trade_record["symbol"]
        strategy = trade_record["strategy"]
        outcome = trade_record["outcome"]
        trade_date = trade_record["exit_time"].date()
        trade_hour = trade_record["exit_time"].hour

        # Update current metrics
        self.current_metrics.realized_pnl += pnl
        self.current_metrics.commission_paid += Decimal(str(trade_record["commission"]))
        self.current_metrics.total_trades += 1

        # Update by outcome
        if outcome == TradeOutcome.WIN:
            self.current_metrics.winning_trades += 1
            self.current_metrics.gross_profit += pnl
            self.current_metrics.consecutive_wins += 1
            self.current_metrics.consecutive_losses = 0

            if pnl > self.current_metrics.largest_win:
                self.current_metrics.largest_win = pnl

            if (
                self.current_metrics.consecutive_wins
                > self.current_metrics.max_consecutive_wins
            ):
                self.current_metrics.max_consecutive_wins = (
                    self.current_metrics.consecutive_wins
                )

        elif outcome == TradeOutcome.LOSS:
            self.current_metrics.losing_trades += 1
            self.current_metrics.gross_loss += abs(pnl)
            self.current_metrics.consecutive_losses += 1
            self.current_metrics.consecutive_wins = 0

            if abs(pnl) > abs(self.current_metrics.largest_loss):
                self.current_metrics.largest_loss = pnl

            if (
                self.current_metrics.consecutive_losses
                > self.current_metrics.max_consecutive_losses
            ):
                self.current_metrics.max_consecutive_losses = (
                    self.current_metrics.consecutive_losses
                )

        else:  # Breakeven
            self.current_metrics.breakeven_trades += 1
            self.current_metrics.consecutive_wins = 0
            self.current_metrics.consecutive_losses = 0

        # Update symbol and strategy metrics
        self.current_metrics.trades_by_symbol[symbol] += 1
        self.current_metrics.pnl_by_symbol[symbol] += pnl
        self.current_metrics.pnl_by_strategy[strategy] += pnl
        self.current_metrics.daily_pnl[trade_date] += pnl
        self.current_metrics.hourly_pnl[trade_hour] += pnl

        # Update calculated metrics
        await self._update_calculated_metrics()

        # Update period metrics
        await self._update_period_metrics(trade_record)

    async def _update_calculated_metrics(self):
        """Update calculated metrics like win rate, profit factor, etc."""
        metrics = self.current_metrics

        # Win rate
        if metrics.total_trades > 0:
            metrics.win_rate = metrics.winning_trades / metrics.total_trades

        # Average win/loss
        if metrics.winning_trades > 0:
            metrics.average_win = metrics.gross_profit / metrics.winning_trades

        if metrics.losing_trades > 0:
            metrics.average_loss = metrics.gross_loss / metrics.losing_trades

        # Profit factor
        if metrics.gross_loss > 0:
            metrics.profit_factor = float(metrics.gross_profit / metrics.gross_loss)

        # Expectancy
        if metrics.total_trades > 0:
            win_expectancy = metrics.win_rate * metrics.average_win
            loss_expectancy = (1 - metrics.win_rate) * metrics.average_loss
            metrics.expectancy = win_expectancy - loss_expectancy

        # ROI
        if self.account_balance > 0:
            initial_balance = (
                self.equity_curve[0][1] if self.equity_curve else self.account_balance
            )
            metrics.roi = float(
                (self.account_balance - initial_balance) / initial_balance
            )

        # Sharpe ratio (simplified)
        await self._calculate_sharpe_ratio()

        # Sortino ratio (simplified)
        await self._calculate_sortino_ratio()

    async def _calculate_sharpe_ratio(self):
        """Calculate Sharpe ratio from returns."""
        if len(self.trades_history) < 2:
            return

        # Calculate returns
        returns = []
        for i in range(1, len(self.equity_curve)):
            prev_balance = self.equity_curve[i - 1][1]
            curr_balance = self.equity_curve[i][1]
            if prev_balance > 0:
                ret = float((curr_balance - prev_balance) / prev_balance)
                returns.append(ret)

        if not returns:
            return

        # Calculate Sharpe (assuming 0 risk-free rate)
        avg_return = sum(returns) / len(returns)

        if len(returns) > 1:
            variance = sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)
            std_dev = variance**0.5

            if std_dev > 0:
                # Annualized Sharpe (assuming 252 trading days)
                self.current_metrics.sharpe_ratio = (avg_return / std_dev) * (252**0.5)

    async def _calculate_sortino_ratio(self):
        """Calculate Sortino ratio (downside deviation)."""
        if len(self.trades_history) < 2:
            return

        # Calculate returns
        returns = []
        for i in range(1, len(self.equity_curve)):
            prev_balance = self.equity_curve[i - 1][1]
            curr_balance = self.equity_curve[i][1]
            if prev_balance > 0:
                ret = float((curr_balance - prev_balance) / prev_balance)
                returns.append(ret)

        if not returns:
            return

        # Calculate downside deviation
        avg_return = sum(returns) / len(returns)
        negative_returns = [r for r in returns if r < 0]

        if negative_returns:
            downside_variance = sum(r**2 for r in negative_returns) / len(
                negative_returns
            )
            downside_dev = downside_variance**0.5

            if downside_dev > 0:
                # Annualized Sortino
                self.current_metrics.sortino_ratio = (avg_return / downside_dev) * (
                    252**0.5
                )

    async def _update_unrealized_totals(self):
        """Update total unrealized P&L."""
        total_unrealized = Decimal("0")

        for position in self.open_positions.values():
            total_unrealized += position["unrealized_pnl"]

        self.current_metrics.unrealized_pnl = total_unrealized

    async def _update_drawdown(self):
        """Update drawdown metrics."""
        if self.peak_balance > 0:
            drawdown = (self.peak_balance - self.account_balance) / self.peak_balance
            self.current_metrics.current_drawdown = drawdown

            if drawdown > self.current_metrics.max_drawdown:
                self.current_metrics.max_drawdown = drawdown

            # Track drawdown periods
            if drawdown > 0:
                if not self.drawdown_periods or self.drawdown_periods[-1].get(
                    "end_time"
                ):
                    # Start new drawdown period
                    self.drawdown_periods.append(
                        {
                            "start_time": datetime.utcnow(),
                            "start_balance": self.peak_balance,
                            "peak_drawdown": drawdown,
                        }
                    )
                else:
                    # Update current drawdown period
                    current_period = self.drawdown_periods[-1]
                    if drawdown > current_period["peak_drawdown"]:
                        current_period["peak_drawdown"] = drawdown
            else:
                # End drawdown period
                if self.drawdown_periods and not self.drawdown_periods[-1].get(
                    "end_time"
                ):
                    self.drawdown_periods[-1]["end_time"] = datetime.utcnow()
                    duration = (
                        self.drawdown_periods[-1]["end_time"]
                        - self.drawdown_periods[-1]["start_time"]
                    )

                    if duration > self.current_metrics.max_drawdown_duration:
                        self.current_metrics.max_drawdown_duration = duration

    async def _update_period_metrics(self, trade_record: Dict[str, Any]):
        """Update period-specific metrics."""
        trade_time = trade_record["exit_time"]

        # Update daily metrics
        trade_date = trade_time.date()
        if trade_date not in self.daily_metrics:
            self.daily_metrics[trade_date] = PnLMetrics()

        # This would duplicate all the metric updates for the daily period
        # Simplified for brevity

        # Update other periods (weekly, monthly, etc.)
        # Also simplified for brevity

    def _classify_outcome(self, net_pnl: Decimal) -> TradeOutcome:
        """Classify trade outcome."""
        if net_pnl > Decimal("0.01"):  # Small threshold for breakeven
            return TradeOutcome.WIN
        elif net_pnl < Decimal("-0.01"):
            return TradeOutcome.LOSS
        else:
            return TradeOutcome.BREAKEVEN

    async def get_performance_summary(
        self,
        period: Optional[PnLPeriod] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        # Filter trades by date if specified
        if start_date or end_date:
            filtered_trades = []
            for trade in self.trades_history:
                trade_time = trade["exit_time"]
                if start_date and trade_time < start_date:
                    continue
                if end_date and trade_time > end_date:
                    continue
                filtered_trades.append(trade)

            # Calculate metrics for filtered period
            # (Implementation would recalculate all metrics for the period)

        # Get appropriate metrics
        if period and period in self.period_metrics:
            metrics = self.period_metrics[period]
        else:
            metrics = self.current_metrics

        summary = metrics.to_dict()

        # Add additional summary info
        summary["account_balance"] = float(self.account_balance)
        summary["peak_balance"] = float(self.peak_balance)
        summary["open_positions"] = len(self.open_positions)
        summary["total_positions_value"] = float(
            sum(p["quantity"] * p["entry_price"] for p in self.open_positions.values())
        )

        # Add best/worst performing symbols
        if metrics.pnl_by_symbol:
            sorted_symbols = sorted(
                metrics.pnl_by_symbol.items(), key=lambda x: x[1], reverse=True
            )
            summary["best_symbol"] = sorted_symbols[0] if sorted_symbols else None
            summary["worst_symbol"] = sorted_symbols[-1] if sorted_symbols else None

        # Add best/worst performing strategies
        if metrics.pnl_by_strategy:
            sorted_strategies = sorted(
                metrics.pnl_by_strategy.items(), key=lambda x: x[1], reverse=True
            )
            summary["best_strategy"] = (
                sorted_strategies[0] if sorted_strategies else None
            )
            summary["worst_strategy"] = (
                sorted_strategies[-1] if sorted_strategies else None
            )

        # Add time-based analysis
        if metrics.hourly_pnl:
            best_hour = max(metrics.hourly_pnl.items(), key=lambda x: x[1])
            worst_hour = min(metrics.hourly_pnl.items(), key=lambda x: x[1])
            summary["best_trading_hour"] = best_hour
            summary["worst_trading_hour"] = worst_hour

        return summary

    async def get_equity_curve(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get equity curve data."""
        curve_data = []

        for timestamp, balance in self.equity_curve:
            if start_date and timestamp < start_date:
                continue
            if end_date and timestamp > end_date:
                continue

            curve_data.append(
                {
                    "timestamp": timestamp.isoformat(),
                    "balance": float(balance),
                    "drawdown": float(
                        (self.peak_balance - balance) / self.peak_balance
                        if self.peak_balance > 0
                        else 0
                    ),
                }
            )

        return curve_data

    async def export_trades_history(
        self, format: str = "json", filepath: Optional[str] = None
    ) -> Optional[str]:
        """Export trades history to file."""
        if format == "json":
            # Convert datetime objects to strings
            export_data = []
            for trade in self.trades_history:
                trade_copy = trade.copy()
                trade_copy["entry_time"] = trade_copy["entry_time"].isoformat()
                trade_copy["exit_time"] = trade_copy["exit_time"].isoformat()
                export_data.append(trade_copy)

            if filepath:
                with open(filepath, "w") as f:
                    json.dump(export_data, f, indent=2)
                return filepath
            else:
                return json.dumps(export_data, indent=2)

        # Add CSV export if needed

        return None
