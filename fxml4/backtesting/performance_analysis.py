"""Performance analysis for backtesting results.

This module provides comprehensive performance metrics for evaluating trading strategies,
including risk-adjusted returns, drawdown analysis, multi-scenario comparison, and visualization.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics for backtesting results."""

    # Basic return metrics
    total_return: float
    total_return_pct: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float

    # Drawdown metrics
    max_drawdown: float
    max_drawdown_pct: float
    avg_drawdown: float
    max_drawdown_duration: int
    drawdown_duration: timedelta
    recovery_factor: float
    calmar_ratio: float
    ulcer_index: float

    # Trade metrics
    num_trades: int
    total_trades: int
    win_rate: float
    profit_factor: float
    avg_profit_per_trade: float
    avg_loss_per_trade: float
    avg_win: float
    avg_loss: float
    avg_trade_duration: timedelta
    max_consecutive_wins: int
    max_consecutive_losses: int
    winning_trades: int
    losing_trades: int

    # Value at Risk metrics
    var_95: float
    cvar_95: float
    var_99: float
    cvar_99: float

    # Additional risk metrics
    expectancy: float
    kelly_criterion: float
    information_ratio: float
    treynor_ratio: float
    tracking_error: float

    # Monthly/yearly metrics
    monthly_returns: pd.Series
    yearly_returns: pd.Series
    best_month: float
    worst_month: float
    best_year: float
    worst_year: float

    # Statistical metrics
    skewness: float
    kurtosis: float
    downside_deviation: float
    up_capture_ratio: float
    down_capture_ratio: float


class PerformanceAnalyzer:
    """Analyze backtest performance with comprehensive metrics and visualization."""

    def __init__(
        self,
        risk_free_rate: float = 0.02,
        benchmark_returns: Optional[pd.Series] = None,
    ):
        """Initialize performance analyzer.

        Args:
            risk_free_rate: Risk-free rate for Sharpe ratio calculation
            benchmark_returns: Benchmark returns for comparison metrics
        """
        self.risk_free_rate = risk_free_rate
        self.benchmark_returns = benchmark_returns
        self.metrics = None
        self.equity_curve = None
        self.trades = None
        self.returns = None

    def analyze(
        self,
        equity_curve: pd.Series,
        trades: Optional[List[Dict[str, Any]]] = None,
        initial_capital: float = 10000.0,
    ) -> PerformanceMetrics:
        """Analyze backtest performance.

        Args:
            equity_curve: Time series of portfolio value
            trades: List of trade records
            initial_capital: Initial capital amount

        Returns:
            PerformanceMetrics object with comprehensive metrics
        """
        self.equity_curve = equity_curve
        self.trades = trades or []

        # Calculate returns
        self.returns = equity_curve.pct_change().dropna()

        # Calculate all metrics
        metrics = self._calculate_comprehensive_metrics(equity_curve, initial_capital)

        self.metrics = metrics
        return metrics

    def _calculate_comprehensive_metrics(
        self, equity_curve: pd.Series, initial_capital: float
    ) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics."""

        # Basic return metrics
        total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1
        total_return_pct = total_return * 100

        # Annualized return
        trading_days = 252
        years = len(equity_curve) / trading_days
        annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

        # Volatility
        volatility = self.returns.std() * np.sqrt(trading_days)

        # Sharpe ratio
        excess_returns = self.returns - self.risk_free_rate / trading_days
        sharpe_ratio = (
            excess_returns.mean() / excess_returns.std() * np.sqrt(trading_days)
            if excess_returns.std() > 0
            else 0
        )

        # Sortino ratio
        downside_returns = self.returns[self.returns < 0]
        downside_deviation = downside_returns.std() * np.sqrt(trading_days)
        sortino_ratio = (
            (annualized_return - self.risk_free_rate) / downside_deviation
            if downside_deviation > 0
            else 0
        )

        # Drawdown metrics
        drawdown_metrics = self._calculate_drawdown_metrics(equity_curve)

        # Trade metrics
        trade_metrics = self._calculate_trade_metrics()

        # Value at Risk metrics
        var_metrics = self._calculate_var_metrics()

        # Monthly and yearly returns
        monthly_returns = self._calculate_monthly_returns()
        yearly_returns = self._calculate_yearly_returns()

        # Additional risk metrics
        expectancy = self._calculate_expectancy()
        kelly_criterion = self._calculate_kelly_criterion()
        information_ratio = self._calculate_information_ratio()
        treynor_ratio = self._calculate_treynor_ratio()
        tracking_error = self._calculate_tracking_error()

        # Statistical metrics
        skewness = self.returns.skew()
        kurtosis = self.returns.kurtosis()

        # Capture ratios
        up_capture_ratio, down_capture_ratio = self._calculate_capture_ratios()

        return PerformanceMetrics(
            total_return=total_return,
            total_return_pct=total_return_pct,
            annualized_return=annualized_return,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=drawdown_metrics["max_drawdown"],
            max_drawdown_pct=drawdown_metrics["max_drawdown_pct"],
            avg_drawdown=drawdown_metrics["avg_drawdown"],
            max_drawdown_duration=drawdown_metrics["max_drawdown_duration"],
            drawdown_duration=drawdown_metrics["drawdown_duration"],
            recovery_factor=drawdown_metrics["recovery_factor"],
            calmar_ratio=drawdown_metrics["calmar_ratio"],
            ulcer_index=drawdown_metrics["ulcer_index"],
            num_trades=trade_metrics["num_trades"],
            total_trades=trade_metrics["total_trades"],
            win_rate=trade_metrics["win_rate"],
            profit_factor=trade_metrics["profit_factor"],
            avg_profit_per_trade=trade_metrics["avg_profit_per_trade"],
            avg_loss_per_trade=trade_metrics["avg_loss_per_trade"],
            avg_win=trade_metrics["avg_win"],
            avg_loss=trade_metrics["avg_loss"],
            avg_trade_duration=trade_metrics["avg_trade_duration"],
            max_consecutive_wins=trade_metrics["max_consecutive_wins"],
            max_consecutive_losses=trade_metrics["max_consecutive_losses"],
            winning_trades=trade_metrics["winning_trades"],
            losing_trades=trade_metrics["losing_trades"],
            var_95=var_metrics["var_95"],
            cvar_95=var_metrics["cvar_95"],
            var_99=var_metrics["var_99"],
            cvar_99=var_metrics["cvar_99"],
            expectancy=expectancy,
            kelly_criterion=kelly_criterion,
            information_ratio=information_ratio,
            treynor_ratio=treynor_ratio,
            tracking_error=tracking_error,
            monthly_returns=monthly_returns,
            yearly_returns=yearly_returns,
            best_month=monthly_returns.max() if not monthly_returns.empty else 0,
            worst_month=monthly_returns.min() if not monthly_returns.empty else 0,
            best_year=yearly_returns.max() if not yearly_returns.empty else 0,
            worst_year=yearly_returns.min() if not yearly_returns.empty else 0,
            skewness=skewness,
            kurtosis=kurtosis,
            downside_deviation=downside_deviation,
            up_capture_ratio=up_capture_ratio,
            down_capture_ratio=down_capture_ratio,
        )

    def _calculate_drawdown_metrics(self, equity_curve: pd.Series) -> Dict[str, Any]:
        """Calculate drawdown-related metrics."""
        # Rolling maximum
        rolling_max = equity_curve.expanding().max()

        # Drawdown
        drawdown = (equity_curve - rolling_max) / rolling_max

        # Max drawdown
        max_drawdown = drawdown.min()
        max_drawdown_pct = max_drawdown * 100

        # Average drawdown
        avg_drawdown = drawdown[drawdown < 0].mean() if (drawdown < 0).any() else 0

        # Max drawdown duration
        is_in_drawdown = drawdown < 0
        drawdown_periods = (
            is_in_drawdown.astype(int)
            .groupby((is_in_drawdown != is_in_drawdown.shift()).cumsum())
            .sum()
        )
        max_drawdown_duration = (
            drawdown_periods.max() if not drawdown_periods.empty else 0
        )

        # Recovery factor
        recovery_factor = (
            abs(self.returns.sum()) / abs(max_drawdown) if max_drawdown != 0 else 0
        )

        # Calmar ratio
        calmar_ratio = (
            (self.returns.mean() * 252) / abs(max_drawdown) if max_drawdown != 0 else 0
        )

        # Ulcer index
        ulcer_index = np.sqrt((drawdown**2).mean())

        return {
            "max_drawdown": max_drawdown,
            "max_drawdown_pct": max_drawdown_pct,
            "avg_drawdown": avg_drawdown,
            "max_drawdown_duration": max_drawdown_duration,
            "drawdown_duration": timedelta(days=max_drawdown_duration),
            "recovery_factor": recovery_factor,
            "calmar_ratio": calmar_ratio,
            "ulcer_index": ulcer_index,
        }

    def _calculate_trade_metrics(self) -> Dict[str, Any]:
        """Calculate trade-related metrics."""
        if not self.trades:
            return {
                "num_trades": 0,
                "total_trades": 0,
                "win_rate": 0,
                "profit_factor": 0,
                "avg_profit_per_trade": 0,
                "avg_loss_per_trade": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "avg_trade_duration": timedelta(0),
                "max_consecutive_wins": 0,
                "max_consecutive_losses": 0,
                "winning_trades": 0,
                "losing_trades": 0,
            }

        # Extract PnL from trades
        pnl_values = [trade.get("pnl", 0) for trade in self.trades]

        # Basic trade stats
        winning_trades = [pnl for pnl in pnl_values if pnl > 0]
        losing_trades = [pnl for pnl in pnl_values if pnl < 0]

        num_trades = len(self.trades)
        win_rate = len(winning_trades) / num_trades if num_trades > 0 else 0

        # Profit factor
        gross_profit = sum(winning_trades) if winning_trades else 0
        gross_loss = abs(sum(losing_trades)) if losing_trades else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        # Average profits/losses
        avg_win = np.mean(winning_trades) if winning_trades else 0
        avg_loss = np.mean(losing_trades) if losing_trades else 0
        avg_profit_per_trade = np.mean(pnl_values) if pnl_values else 0
        avg_loss_per_trade = (
            np.mean([pnl for pnl in pnl_values if pnl < 0]) if losing_trades else 0
        )

        # Consecutive wins/losses
        max_consecutive_wins = self._calculate_max_consecutive(
            pnl_values, lambda x: x > 0
        )
        max_consecutive_losses = self._calculate_max_consecutive(
            pnl_values, lambda x: x < 0
        )

        # Average trade duration
        avg_trade_duration = self._calculate_avg_trade_duration()

        return {
            "num_trades": num_trades,
            "total_trades": num_trades,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "avg_profit_per_trade": avg_profit_per_trade,
            "avg_loss_per_trade": avg_loss_per_trade,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "avg_trade_duration": avg_trade_duration,
            "max_consecutive_wins": max_consecutive_wins,
            "max_consecutive_losses": max_consecutive_losses,
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
        }

    def _calculate_max_consecutive(
        self, values: List[float], condition: callable
    ) -> int:
        """Calculate maximum consecutive occurrences of a condition."""
        if not values:
            return 0

        max_consecutive = 0
        current_consecutive = 0

        for value in values:
            if condition(value):
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0

        return max_consecutive

    def _calculate_avg_trade_duration(self) -> timedelta:
        """Calculate average trade duration."""
        if not self.trades:
            return timedelta(0)

        durations = []
        for trade in self.trades:
            if "entry_time" in trade and "exit_time" in trade:
                duration = trade["exit_time"] - trade["entry_time"]
                durations.append(duration)

        return (
            sum(durations, timedelta(0)) / len(durations) if durations else timedelta(0)
        )

    def _calculate_var_metrics(self) -> Dict[str, float]:
        """Calculate Value at Risk metrics."""
        if self.returns.empty:
            return {"var_95": 0, "cvar_95": 0, "var_99": 0, "cvar_99": 0}

        # VaR at 95% confidence
        var_95 = np.percentile(self.returns, 5)
        cvar_95 = self.returns[self.returns <= var_95].mean()

        # VaR at 99% confidence
        var_99 = np.percentile(self.returns, 1)
        cvar_99 = self.returns[self.returns <= var_99].mean()

        return {
            "var_95": var_95,
            "cvar_95": cvar_95,
            "var_99": var_99,
            "cvar_99": cvar_99,
        }

    def _calculate_monthly_returns(self) -> pd.Series:
        """Calculate monthly returns."""
        if self.equity_curve is None:
            return pd.Series()

        monthly_equity = self.equity_curve.resample("M").last()
        return monthly_equity.pct_change().dropna()

    def _calculate_yearly_returns(self) -> pd.Series:
        """Calculate yearly returns."""
        if self.equity_curve is None:
            return pd.Series()

        yearly_equity = self.equity_curve.resample("Y").last()
        return yearly_equity.pct_change().dropna()

    def _calculate_expectancy(self) -> float:
        """Calculate expectancy."""
        if not self.trades:
            return 0

        pnl_values = [trade.get("pnl", 0) for trade in self.trades]
        return np.mean(pnl_values) if pnl_values else 0

    def _calculate_kelly_criterion(self) -> float:
        """Calculate Kelly criterion."""
        if not self.trades:
            return 0

        pnl_values = [trade.get("pnl", 0) for trade in self.trades]
        winning_trades = [pnl for pnl in pnl_values if pnl > 0]
        losing_trades = [pnl for pnl in pnl_values if pnl < 0]

        if not winning_trades or not losing_trades:
            return 0

        win_rate = len(winning_trades) / len(pnl_values)
        avg_win = np.mean(winning_trades)
        avg_loss = abs(np.mean(losing_trades))

        kelly = (
            win_rate - ((1 - win_rate) / (avg_win / avg_loss)) if avg_loss > 0 else 0
        )
        return kelly

    def _calculate_information_ratio(self) -> float:
        """Calculate information ratio."""
        if self.benchmark_returns is None or self.returns.empty:
            return 0

        # Align returns with benchmark
        aligned_returns, aligned_benchmark = self.returns.align(
            self.benchmark_returns, join="inner"
        )

        if aligned_returns.empty or aligned_benchmark.empty:
            return 0

        excess_returns = aligned_returns - aligned_benchmark
        tracking_error = excess_returns.std() * np.sqrt(252)

        return excess_returns.mean() * 252 / tracking_error if tracking_error > 0 else 0

    def _calculate_treynor_ratio(self) -> float:
        """Calculate Treynor ratio."""
        if self.benchmark_returns is None or self.returns.empty:
            return 0

        # Align returns with benchmark
        aligned_returns, aligned_benchmark = self.returns.align(
            self.benchmark_returns, join="inner"
        )

        if aligned_returns.empty or aligned_benchmark.empty:
            return 0

        # Calculate beta
        covariance = np.cov(aligned_returns, aligned_benchmark)[0, 1]
        benchmark_variance = np.var(aligned_benchmark)
        beta = covariance / benchmark_variance if benchmark_variance > 0 else 0

        excess_return = aligned_returns.mean() * 252 - self.risk_free_rate
        return excess_return / beta if beta > 0 else 0

    def _calculate_tracking_error(self) -> float:
        """Calculate tracking error."""
        if self.benchmark_returns is None or self.returns.empty:
            return 0

        # Align returns with benchmark
        aligned_returns, aligned_benchmark = self.returns.align(
            self.benchmark_returns, join="inner"
        )

        if aligned_returns.empty or aligned_benchmark.empty:
            return 0

        excess_returns = aligned_returns - aligned_benchmark
        return excess_returns.std() * np.sqrt(252)

    def _calculate_capture_ratios(self) -> Tuple[float, float]:
        """Calculate up and down capture ratios."""
        if self.benchmark_returns is None or self.returns.empty:
            return 0, 0

        # Align returns with benchmark
        aligned_returns, aligned_benchmark = self.returns.align(
            self.benchmark_returns, join="inner"
        )

        if aligned_returns.empty or aligned_benchmark.empty:
            return 0, 0

        # Up capture ratio
        up_markets = aligned_benchmark > 0
        up_capture_ratio = (
            (aligned_returns[up_markets].mean() / aligned_benchmark[up_markets].mean())
            if up_markets.any()
            else 0
        )

        # Down capture ratio
        down_markets = aligned_benchmark < 0
        down_capture_ratio = (
            (
                aligned_returns[down_markets].mean()
                / aligned_benchmark[down_markets].mean()
            )
            if down_markets.any()
            else 0
        )

        return up_capture_ratio, down_capture_ratio

    def plot_performance(self, figsize: Tuple[int, int] = (15, 10)):
        """Generate comprehensive performance plots."""
        if self.equity_curve is None:
            logger.warning("No equity curve data available for plotting")
            return

        fig, axes = plt.subplots(2, 2, figsize=figsize)

        # Equity curve
        axes[0, 0].plot(self.equity_curve.index, self.equity_curve.values)
        axes[0, 0].set_title("Equity Curve")
        axes[0, 0].set_ylabel("Portfolio Value")
        axes[0, 0].grid(True)

        # Returns histogram
        axes[0, 1].hist(self.returns.dropna(), bins=50, alpha=0.7, edgecolor="black")
        axes[0, 1].set_title("Returns Distribution")
        axes[0, 1].set_xlabel("Daily Returns")
        axes[0, 1].set_ylabel("Frequency")
        axes[0, 1].grid(True)

        # Drawdown
        rolling_max = self.equity_curve.expanding().max()
        drawdown = (self.equity_curve - rolling_max) / rolling_max
        axes[1, 0].fill_between(
            drawdown.index, drawdown.values, 0, alpha=0.3, color="red"
        )
        axes[1, 0].set_title("Drawdown")
        axes[1, 0].set_ylabel("Drawdown")
        axes[1, 0].grid(True)

        # Rolling Sharpe ratio
        rolling_sharpe = (
            self.returns.rolling(window=252).mean()
            / self.returns.rolling(window=252).std()
            * np.sqrt(252)
        )
        axes[1, 1].plot(rolling_sharpe.index, rolling_sharpe.values)
        axes[1, 1].set_title("Rolling Sharpe Ratio (252 days)")
        axes[1, 1].set_ylabel("Sharpe Ratio")
        axes[1, 1].grid(True)

        plt.tight_layout()
        plt.show()

    def generate_report(self) -> str:
        """Generate a comprehensive text report."""
        if self.metrics is None:
            return "No performance metrics available. Run analyze() first."

        report = f"""
PERFORMANCE ANALYSIS REPORT
===========================

RETURN METRICS:
- Total Return: {self.metrics.total_return:.2%}
- Annualized Return: {self.metrics.annualized_return:.2%}
- Volatility: {self.metrics.volatility:.2%}
- Sharpe Ratio: {self.metrics.sharpe_ratio:.3f}
- Sortino Ratio: {self.metrics.sortino_ratio:.3f}

DRAWDOWN METRICS:
- Max Drawdown: {self.metrics.max_drawdown:.2%}
- Average Drawdown: {self.metrics.avg_drawdown:.2%}
- Max Drawdown Duration: {self.metrics.max_drawdown_duration} days
- Recovery Factor: {self.metrics.recovery_factor:.3f}
- Calmar Ratio: {self.metrics.calmar_ratio:.3f}

TRADE METRICS:
- Total Trades: {self.metrics.total_trades}
- Win Rate: {self.metrics.win_rate:.2%}
- Profit Factor: {self.metrics.profit_factor:.3f}
- Average Win: {self.metrics.avg_win:.2f}
- Average Loss: {self.metrics.avg_loss:.2f}
- Max Consecutive Wins: {self.metrics.max_consecutive_wins}
- Max Consecutive Losses: {self.metrics.max_consecutive_losses}

RISK METRICS:
- VaR (95%): {self.metrics.var_95:.2%}
- CVaR (95%): {self.metrics.cvar_95:.2%}
- VaR (99%): {self.metrics.var_99:.2%}
- CVaR (99%): {self.metrics.cvar_99:.2%}
- Skewness: {self.metrics.skewness:.3f}
- Kurtosis: {self.metrics.kurtosis:.3f}

ADDITIONAL METRICS:
- Expectancy: {self.metrics.expectancy:.2f}
- Kelly Criterion: {self.metrics.kelly_criterion:.2%}
- Information Ratio: {self.metrics.information_ratio:.3f}
- Tracking Error: {self.metrics.tracking_error:.2%}
        """

        return report.strip()


# Legacy compatibility
LegacyPerformanceAnalyzer = PerformanceAnalyzer  # For backward compatibility


# Export main classes
__all__ = [
    "PerformanceAnalyzer",
    "PerformanceMetrics",
    "LegacyPerformanceAnalyzer",  # For backward compatibility
]
