"""
FXML4 Live Performance Tracker
Real-time calculation and tracking of trading performance metrics

This module provides comprehensive performance tracking for live paper trading validation:
- Real-time P&L calculation and NAV tracking
- Maximum drawdown monitoring with breach detection
- Risk-adjusted performance metrics (Sharpe, Sortino, Calmar ratios)
- Statistical significance testing and confidence intervals
- Benchmark comparison and relative performance analysis

Key Requirements:
- Track progress toward >15% annual return target
- Monitor drawdown levels vs <10% maximum limit
- Provide early warning for performance deviations
- Generate institutional-quality performance reports
"""

import asyncio
import json
import logging
import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..core.exceptions import PerformanceError, ValidationError


class PerformanceStatus(Enum):
    """Performance tracking status"""

    ON_TARGET = "on_target"
    UNDERPERFORMING = "underperforming"
    OUTPERFORMING = "outperforming"
    DRAWDOWN_WARNING = "drawdown_warning"
    DRAWDOWN_BREACH = "drawdown_breach"
    TARGET_ACHIEVED = "target_achieved"
    TARGET_FAILED = "target_failed"


class BenchmarkType(Enum):
    """Benchmark comparison types"""

    BUY_AND_HOLD = "buy_and_hold"
    RISK_FREE_RATE = "risk_free_rate"
    MARKET_INDEX = "market_index"
    FOREX_INDEX = "forex_index"


@dataclass
class PerformanceSnapshot:
    """Point-in-time performance snapshot"""

    timestamp: datetime
    account_value: float
    daily_return: float
    cumulative_return: float
    annualized_return: float
    max_drawdown: float
    current_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    win_rate: float
    profit_factor: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    average_win: float
    average_loss: float
    largest_win: float
    largest_loss: float
    consecutive_wins: int
    consecutive_losses: int
    days_trading: int
    volatility: float

    @property
    def is_drawdown_breach(self) -> bool:
        return self.max_drawdown > 10.0  # 10% maximum drawdown limit

    @property
    def is_return_target_met(self) -> bool:
        return self.annualized_return >= 15.0  # 15% annual return target

    @property
    def performance_status(self) -> PerformanceStatus:
        if self.is_drawdown_breach:
            return PerformanceStatus.DRAWDOWN_BREACH
        elif self.current_drawdown > 8.0:  # Warning at 8%
            return PerformanceStatus.DRAWDOWN_WARNING
        elif self.days_trading >= 30 and self.is_return_target_met:
            return PerformanceStatus.TARGET_ACHIEVED
        elif self.days_trading >= 30 and not self.is_return_target_met:
            return PerformanceStatus.TARGET_FAILED
        elif self.annualized_return >= 20.0:  # Outperforming
            return PerformanceStatus.OUTPERFORMING
        elif self.annualized_return < 10.0:  # Underperforming
            return PerformanceStatus.UNDERPERFORMING
        else:
            return PerformanceStatus.ON_TARGET


@dataclass
class TradeRecord:
    """Individual trade record for performance calculation"""

    trade_id: str
    symbol: str
    side: str  # BUY or SELL
    quantity: float
    entry_price: float
    exit_price: Optional[float] = None
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    pnl: float = 0.0
    commission: float = 0.0
    is_winner: bool = False
    hold_time_hours: float = 0.0

    @property
    def is_closed(self) -> bool:
        return self.exit_price is not None and self.exit_time is not None

    @property
    def net_pnl(self) -> float:
        return self.pnl - self.commission


@dataclass
class PeriodPerformance:
    """Performance statistics for a specific period"""

    start_date: datetime
    end_date: datetime
    period_name: str
    total_return: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    best_trade: float
    worst_trade: float

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days


class LivePerformanceTracker:
    """
    Live Performance Tracker for Trading System Validation

    Provides real-time calculation and tracking of comprehensive performance metrics
    for validating profitable trading performance over specified periods.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # Performance tracking configuration
        self.initial_capital = self.config.get("initial_capital", 100000.0)
        self.target_annual_return = self.config.get("target_annual_return", 15.0)  # 15%
        self.max_drawdown_limit = self.config.get("max_drawdown_limit", 10.0)  # 10%
        self.risk_free_rate = self.config.get("risk_free_rate", 2.0)  # 2% annual

        # Performance data storage
        self.account_values: List[Tuple[datetime, float]] = []
        self.daily_returns: List[float] = []
        self.trade_records: List[TradeRecord] = []
        self.performance_snapshots: List[PerformanceSnapshot] = []

        # Current performance state
        self.current_account_value = self.initial_capital
        self.peak_account_value = self.initial_capital
        self.current_drawdown = 0.0
        self.max_drawdown_reached = 0.0
        self.start_date: Optional[datetime] = None

        # Performance calculations cache
        self._performance_cache = {}
        self._cache_timestamp: Optional[datetime] = None

        # File storage
        self.data_file = Path("live_performance_data.json")
        self.reports_dir = Path("performance_reports")
        self.reports_dir.mkdir(exist_ok=True)

    async def initialize(self, initial_capital: Optional[float] = None) -> None:
        """Initialize performance tracker"""
        try:
            self.logger.info("Initializing live performance tracker...")

            if initial_capital:
                self.initial_capital = initial_capital
                self.current_account_value = initial_capital
                self.peak_account_value = initial_capital

            # Load historical data if available
            await self._load_historical_data()

            # Set start date if not already set
            if not self.start_date:
                self.start_date = datetime.utcnow()
                self.logger.info(
                    f"Starting performance tracking from: {self.start_date.isoformat()}"
                )

            self.logger.info("✅ Live performance tracker initialized successfully")

        except Exception as e:
            self.logger.error(f"❌ Failed to initialize performance tracker: {e}")
            raise ValidationError(f"Performance tracker initialization failed: {e}")

    async def update_account_value(
        self, new_value: float, timestamp: Optional[datetime] = None
    ) -> PerformanceSnapshot:
        """
        Update account value and calculate performance metrics

        Args:
            new_value: New account value
            timestamp: Timestamp for the update (defaults to now)

        Returns:
            PerformanceSnapshot with updated metrics
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        try:
            # Store account value
            self.account_values.append((timestamp, new_value))

            # Calculate daily return if we have previous value
            daily_return = 0.0
            if len(self.account_values) > 1:
                previous_value = self.account_values[-2][1]
                daily_return = (new_value - previous_value) / previous_value * 100
                self.daily_returns.append(daily_return)

            # Update current values
            self.current_account_value = new_value

            # Update peak and drawdown
            if new_value > self.peak_account_value:
                self.peak_account_value = new_value
                self.current_drawdown = 0.0
            else:
                self.current_drawdown = (
                    (self.peak_account_value - new_value)
                    / self.peak_account_value
                    * 100
                )
                self.max_drawdown_reached = max(
                    self.max_drawdown_reached, self.current_drawdown
                )

            # Calculate comprehensive performance metrics
            snapshot = await self._calculate_performance_snapshot(timestamp)
            self.performance_snapshots.append(snapshot)

            # Clear cache
            self._performance_cache.clear()

            # Save data periodically
            if len(self.account_values) % 10 == 0:  # Every 10 updates
                await self._save_performance_data()

            # Log significant events
            if snapshot.is_drawdown_breach:
                self.logger.error(
                    f"🚨 DRAWDOWN BREACH: {self.current_drawdown:.2f}% > {self.max_drawdown_limit}%"
                )
            elif snapshot.performance_status == PerformanceStatus.TARGET_ACHIEVED:
                self.logger.info(
                    f"🎉 PERFORMANCE TARGET ACHIEVED: {snapshot.annualized_return:.2f}% annual return"
                )

            return snapshot

        except Exception as e:
            self.logger.error(f"Error updating account value: {e}")
            raise PerformanceError(f"Account value update failed: {e}")

    async def record_trade(self, trade: TradeRecord) -> None:
        """Record a completed trade for performance analysis"""
        try:
            # Calculate trade P&L if not already set
            if trade.is_closed and trade.pnl == 0.0:
                if trade.side.upper() == "BUY":
                    trade.pnl = (trade.exit_price - trade.entry_price) * trade.quantity
                else:  # SELL
                    trade.pnl = (trade.entry_price - trade.exit_price) * trade.quantity

            # Calculate hold time
            if trade.entry_time and trade.exit_time:
                trade.hold_time_hours = (
                    trade.exit_time - trade.entry_time
                ).total_seconds() / 3600

            # Determine if winner
            trade.is_winner = trade.net_pnl > 0

            # Store trade record
            self.trade_records.append(trade)

            self.logger.info(
                f"📊 Trade recorded: {trade.symbol} {trade.side} "
                f"P&L: ${trade.net_pnl:.2f} ({'WIN' if trade.is_winner else 'LOSS'})"
            )

        except Exception as e:
            self.logger.error(f"Error recording trade: {e}")

    async def _calculate_performance_snapshot(
        self, timestamp: datetime
    ) -> PerformanceSnapshot:
        """Calculate comprehensive performance snapshot"""

        # Basic calculations
        cumulative_return = (
            (self.current_account_value - self.initial_capital)
            / self.initial_capital
            * 100
        )

        # Calculate annualized return
        days_trading = (timestamp - self.start_date).days
        if days_trading > 0:
            annualized_return = (
                (self.current_account_value / self.initial_capital)
                ** (365 / days_trading)
                - 1
            ) * 100
        else:
            annualized_return = 0.0

        # Calculate volatility (annualized)
        volatility = 0.0
        if len(self.daily_returns) > 1:
            daily_vol = statistics.stdev(self.daily_returns)
            volatility = daily_vol * math.sqrt(
                252
            )  # Annualize assuming 252 trading days

        # Calculate Sharpe ratio
        sharpe_ratio = 0.0
        if volatility > 0:
            excess_return = annualized_return - self.risk_free_rate
            sharpe_ratio = excess_return / volatility

        # Calculate Sortino ratio (using downside deviation)
        sortino_ratio = 0.0
        if len(self.daily_returns) > 1:
            downside_returns = [r for r in self.daily_returns if r < 0]
            if downside_returns:
                downside_deviation = statistics.stdev(downside_returns) * math.sqrt(252)
                if downside_deviation > 0:
                    excess_return = annualized_return - self.risk_free_rate
                    sortino_ratio = excess_return / downside_deviation

        # Trade statistics
        total_trades = len([t for t in self.trade_records if t.is_closed])
        winning_trades = len(
            [t for t in self.trade_records if t.is_closed and t.is_winner]
        )
        losing_trades = total_trades - winning_trades

        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

        # Calculate average win/loss
        wins = [t.net_pnl for t in self.trade_records if t.is_closed and t.is_winner]
        losses = [
            abs(t.net_pnl)
            for t in self.trade_records
            if t.is_closed and not t.is_winner
        ]

        average_win = statistics.mean(wins) if wins else 0.0
        average_loss = statistics.mean(losses) if losses else 0.0

        # Profit factor
        total_wins = sum(wins) if wins else 0.0
        total_losses = sum(losses) if losses else 1.0  # Avoid division by zero
        profit_factor = total_wins / total_losses if total_losses > 0 else 0.0

        # Largest win/loss
        largest_win = max(wins) if wins else 0.0
        largest_loss = max(losses) if losses else 0.0

        # Consecutive wins/losses (simplified calculation)
        consecutive_wins = 0
        consecutive_losses = 0
        current_consecutive_wins = 0
        current_consecutive_losses = 0

        for trade in self.trade_records:
            if trade.is_closed:
                if trade.is_winner:
                    current_consecutive_wins += 1
                    current_consecutive_losses = 0
                    consecutive_wins = max(consecutive_wins, current_consecutive_wins)
                else:
                    current_consecutive_losses += 1
                    current_consecutive_wins = 0
                    consecutive_losses = max(
                        consecutive_losses, current_consecutive_losses
                    )

        # Get daily return for snapshot
        daily_return = self.daily_returns[-1] if self.daily_returns else 0.0

        return PerformanceSnapshot(
            timestamp=timestamp,
            account_value=self.current_account_value,
            daily_return=daily_return,
            cumulative_return=cumulative_return,
            annualized_return=annualized_return,
            max_drawdown=self.max_drawdown_reached,
            current_drawdown=self.current_drawdown,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            average_win=average_win,
            average_loss=average_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            consecutive_wins=consecutive_wins,
            consecutive_losses=consecutive_losses,
            days_trading=days_trading,
            volatility=volatility,
        )

    def get_current_performance(self) -> Optional[PerformanceSnapshot]:
        """Get the most recent performance snapshot"""
        return self.performance_snapshots[-1] if self.performance_snapshots else None

    async def calculate_period_performance(
        self, start_date: datetime, end_date: datetime, period_name: str = ""
    ) -> PeriodPerformance:
        """Calculate performance statistics for a specific period"""

        # Filter data for the specified period
        period_values = [
            (ts, val) for ts, val in self.account_values if start_date <= ts <= end_date
        ]
        period_returns = []

        if len(period_values) < 2:
            raise ValueError("Insufficient data for period performance calculation")

        # Calculate period returns
        for i in range(1, len(period_values)):
            prev_val = period_values[i - 1][1]
            curr_val = period_values[i][1]
            period_returns.append((curr_val - prev_val) / prev_val * 100)

        # Calculate period statistics
        start_value = period_values[0][1]
        end_value = period_values[-1][1]
        total_return = (end_value - start_value) / start_value * 100

        # Annualize return
        days = (end_date - start_date).days
        annualized_return = (
            ((end_value / start_value) ** (365 / days) - 1) * 100 if days > 0 else 0.0
        )

        # Calculate volatility
        volatility = (
            statistics.stdev(period_returns) * math.sqrt(252)
            if len(period_returns) > 1
            else 0.0
        )

        # Calculate Sharpe ratio
        sharpe_ratio = 0.0
        if volatility > 0:
            excess_return = annualized_return - self.risk_free_rate
            sharpe_ratio = excess_return / volatility

        # Calculate Sortino ratio
        downside_returns = [r for r in period_returns if r < 0]
        sortino_ratio = 0.0
        if downside_returns and len(downside_returns) > 1:
            downside_deviation = statistics.stdev(downside_returns) * math.sqrt(252)
            if downside_deviation > 0:
                excess_return = annualized_return - self.risk_free_rate
                sortino_ratio = excess_return / downside_deviation

        # Calculate maximum drawdown for period
        period_peak = start_value
        max_dd = 0.0
        for _, value in period_values:
            if value > period_peak:
                period_peak = value
            else:
                dd = (period_peak - value) / period_peak * 100
                max_dd = max(max_dd, dd)

        # Trade statistics for period
        period_trades = [
            t
            for t in self.trade_records
            if t.is_closed and start_date <= t.exit_time <= end_date
        ]

        winning_trades = [t for t in period_trades if t.is_winner]
        win_rate = (
            len(winning_trades) / len(period_trades) * 100 if period_trades else 0.0
        )

        # Profit factor
        total_wins = sum(t.net_pnl for t in winning_trades)
        total_losses = sum(abs(t.net_pnl) for t in period_trades if not t.is_winner)
        profit_factor = total_wins / total_losses if total_losses > 0 else 0.0

        # Best and worst trades
        trade_pnls = [t.net_pnl for t in period_trades]
        best_trade = max(trade_pnls) if trade_pnls else 0.0
        worst_trade = min(trade_pnls) if trade_pnls else 0.0

        return PeriodPerformance(
            start_date=start_date,
            end_date=end_date,
            period_name=period_name,
            total_return=total_return,
            annualized_return=annualized_return,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_dd,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=len(period_trades),
            best_trade=best_trade,
            worst_trade=worst_trade,
        )

    async def generate_performance_report(
        self, report_type: str = "comprehensive"
    ) -> str:
        """Generate comprehensive performance report"""

        current_perf = self.get_current_performance()
        if not current_perf:
            return "No performance data available"

        report_lines = [
            "=" * 80,
            "FXML4 LIVE TRADING PERFORMANCE REPORT",
            "=" * 80,
            f"Generated: {datetime.utcnow().isoformat()}",
            f"Trading Period: {self.start_date.strftime('%Y-%m-%d')} to {current_perf.timestamp.strftime('%Y-%m-%d')}",
            f"Days Trading: {current_perf.days_trading}",
            "",
        ]

        # Performance Status
        status_emoji = {
            PerformanceStatus.TARGET_ACHIEVED: "🎉",
            PerformanceStatus.ON_TARGET: "✅",
            PerformanceStatus.OUTPERFORMING: "🚀",
            PerformanceStatus.UNDERPERFORMING: "⚠️",
            PerformanceStatus.DRAWDOWN_WARNING: "⚠️",
            PerformanceStatus.DRAWDOWN_BREACH: "🚨",
            PerformanceStatus.TARGET_FAILED: "❌",
        }.get(current_perf.performance_status, "📊")

        report_lines.extend(
            [
                f"PERFORMANCE STATUS: {status_emoji} {current_perf.performance_status.value.upper()}",
                "",
            ]
        )

        # Key Metrics
        report_lines.extend(
            [
                "KEY PERFORMANCE METRICS:",
                f"  Account Value: ${current_perf.account_value:,.2f}",
                f"  Initial Capital: ${self.initial_capital:,.2f}",
                f"  Total Return: {current_perf.cumulative_return:.2f}%",
                f"  Annualized Return: {current_perf.annualized_return:.2f}% (Target: ≥{self.target_annual_return}%)",
                f"  Maximum Drawdown: {current_perf.max_drawdown:.2f}% (Limit: ≤{self.max_drawdown_limit}%)",
                f"  Current Drawdown: {current_perf.current_drawdown:.2f}%",
                f"  Sharpe Ratio: {current_perf.sharpe_ratio:.2f}",
                f"  Sortino Ratio: {current_perf.sortino_ratio:.2f}",
                f"  Volatility: {current_perf.volatility:.2f}%",
                "",
            ]
        )

        # Trade Statistics
        report_lines.extend(
            [
                "TRADING STATISTICS:",
                f"  Total Trades: {current_perf.total_trades}",
                f"  Winning Trades: {current_perf.winning_trades}",
                f"  Losing Trades: {current_perf.losing_trades}",
                f"  Win Rate: {current_perf.win_rate:.1f}%",
                f"  Profit Factor: {current_perf.profit_factor:.2f}",
                f"  Average Win: ${current_perf.average_win:.2f}",
                f"  Average Loss: ${current_perf.average_loss:.2f}",
                f"  Largest Win: ${current_perf.largest_win:.2f}",
                f"  Largest Loss: ${current_perf.largest_loss:.2f}",
                f"  Consecutive Wins: {current_perf.consecutive_wins}",
                f"  Consecutive Losses: {current_perf.consecutive_losses}",
                "",
            ]
        )

        # Target Achievement Analysis
        days_remaining = max(0, 30 - current_perf.days_trading)
        report_lines.extend(
            [
                "TARGET ACHIEVEMENT ANALYSIS:",
                f"  Days Remaining: {days_remaining}",
                f"  Return Target: {'✅ MET' if current_perf.is_return_target_met else '❌ NOT MET'}",
                f"  Drawdown Compliance: {'✅ COMPLIANT' if not current_perf.is_drawdown_breach else '❌ BREACH'}",
                "",
            ]
        )

        # Recent Performance (last 7 days)
        if len(self.daily_returns) >= 7:
            recent_returns = self.daily_returns[-7:]
            report_lines.extend(
                [
                    "RECENT PERFORMANCE (Last 7 Days):",
                    f"  Average Daily Return: {statistics.mean(recent_returns):.3f}%",
                    f"  Best Day: {max(recent_returns):.3f}%",
                    f"  Worst Day: {min(recent_returns):.3f}%",
                    f"  Volatility: {statistics.stdev(recent_returns):.3f}%",
                    "",
                ]
            )

        report_lines.extend(["=" * 80])

        return "\n".join(report_lines)

    async def _save_performance_data(self) -> None:
        """Save performance data to file"""
        try:
            data = {
                "last_updated": datetime.utcnow().isoformat(),
                "initial_capital": self.initial_capital,
                "start_date": self.start_date.isoformat() if self.start_date else None,
                "account_values": [
                    (ts.isoformat(), val) for ts, val in self.account_values
                ],
                "daily_returns": self.daily_returns,
                "trade_records": [
                    {
                        "trade_id": t.trade_id,
                        "symbol": t.symbol,
                        "side": t.side,
                        "quantity": t.quantity,
                        "entry_price": t.entry_price,
                        "exit_price": t.exit_price,
                        "entry_time": (
                            t.entry_time.isoformat() if t.entry_time else None
                        ),
                        "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                        "pnl": t.pnl,
                        "commission": t.commission,
                        "is_winner": t.is_winner,
                        "hold_time_hours": t.hold_time_hours,
                    }
                    for t in self.trade_records
                ],
            }

            with open(self.data_file, "w") as f:
                json.dump(data, f, indent=2, default=str)

            self.logger.debug(
                f"💾 Performance data saved: {len(self.account_values)} values, {len(self.trade_records)} trades"
            )

        except Exception as e:
            self.logger.error(f"Failed to save performance data: {e}")

    async def _load_historical_data(self) -> None:
        """Load historical performance data"""
        try:
            if not self.data_file.exists():
                self.logger.info("No historical performance data found")
                return

            with open(self.data_file, "r") as f:
                data = json.load(f)

            # Restore basic data
            self.initial_capital = data.get("initial_capital", self.initial_capital)
            if data.get("start_date"):
                self.start_date = datetime.fromisoformat(data["start_date"])

            # Restore account values
            self.account_values = [
                (datetime.fromisoformat(ts), val)
                for ts, val in data.get("account_values", [])
            ]

            # Restore daily returns
            self.daily_returns = data.get("daily_returns", [])

            # Restore trade records
            for trade_data in data.get("trade_records", []):
                trade = TradeRecord(
                    trade_id=trade_data["trade_id"],
                    symbol=trade_data["symbol"],
                    side=trade_data["side"],
                    quantity=trade_data["quantity"],
                    entry_price=trade_data["entry_price"],
                    exit_price=trade_data.get("exit_price"),
                    entry_time=(
                        datetime.fromisoformat(trade_data["entry_time"])
                        if trade_data.get("entry_time")
                        else None
                    ),
                    exit_time=(
                        datetime.fromisoformat(trade_data["exit_time"])
                        if trade_data.get("exit_time")
                        else None
                    ),
                    pnl=trade_data.get("pnl", 0.0),
                    commission=trade_data.get("commission", 0.0),
                    is_winner=trade_data.get("is_winner", False),
                    hold_time_hours=trade_data.get("hold_time_hours", 0.0),
                )
                self.trade_records.append(trade)

            # Update current state
            if self.account_values:
                self.current_account_value = self.account_values[-1][1]
                self.peak_account_value = max(val for _, val in self.account_values)

                # Recalculate drawdown
                current_dd = (
                    (self.peak_account_value - self.current_account_value)
                    / self.peak_account_value
                    * 100
                )
                self.current_drawdown = max(0, current_dd)

                # Find maximum drawdown
                peak = self.initial_capital
                max_dd = 0.0
                for _, value in self.account_values:
                    if value > peak:
                        peak = value
                    else:
                        dd = (peak - value) / peak * 100
                        max_dd = max(max_dd, dd)
                self.max_drawdown_reached = max_dd

            self.logger.info(
                f"📁 Loaded historical performance data: {len(self.account_values)} values, {len(self.trade_records)} trades"
            )

        except Exception as e:
            self.logger.warning(f"Could not load historical performance data: {e}")


# Performance Tracker Runner for Direct Execution
async def main():
    """Main performance tracker runner for testing"""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    config = {
        "initial_capital": 100000.0,
        "target_annual_return": 15.0,
        "max_drawdown_limit": 10.0,
        "risk_free_rate": 2.0,
    }

    tracker = LivePerformanceTracker(config)

    try:
        # Initialize tracker
        await tracker.initialize()

        # Simulate some performance data
        logger.info("🔄 Simulating performance tracking...")

        # Simulate 10 days of trading with varying performance
        base_value = tracker.initial_capital
        for day in range(10):
            # Simulate daily return (random walk with slight positive bias)
            import random

            daily_change = random.normalvariate(0.001, 0.02)  # 0.1% mean, 2% std dev
            new_value = base_value * (1 + daily_change)

            timestamp = datetime.utcnow() - timedelta(days=10 - day)
            snapshot = await tracker.update_account_value(new_value, timestamp)

            logger.info(
                f"Day {day+1}: ${new_value:,.2f} "
                f"({snapshot.daily_return:+.2f}% daily, {snapshot.annualized_return:.1f}% annual, "
                f"{snapshot.current_drawdown:.1f}% DD)"
            )

            base_value = new_value

        # Generate performance report
        report = await tracker.generate_performance_report()
        logger.info("Performance Report:")
        logger.info(report)

        # Check performance status
        current_perf = tracker.get_current_performance()
        if current_perf:
            logger.info(f"📊 Current Status: {current_perf.performance_status.value}")

            if current_perf.is_return_target_met:
                logger.info("✅ Return target achieved!")
            if not current_perf.is_drawdown_breach:
                logger.info("✅ Drawdown within limits!")

    except Exception as e:
        logger.error(f"Performance tracking test failed: {e}")
        raise
    finally:
        # Save final data
        await tracker._save_performance_data()
        logger.info("🏁 Performance tracking test completed")


if __name__ == "__main__":
    asyncio.run(main())
