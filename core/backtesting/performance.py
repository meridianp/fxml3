"""Performance calculation module for backtesting.

This module provides performance metric calculation functionality required by the
backtesting test suite, implementing comprehensive trade and portfolio analysis.
"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class PerformanceCalculator:
    """Calculate comprehensive performance metrics from backtest results.

    This class implements the interface expected by the backtesting test suite,
    providing detailed analysis of trading performance, risk metrics, and
    statistical measures.
    """

    def __init__(self):
        """Initialize the performance calculator."""
        logger.info("PerformanceCalculator initialized")

    def calculate_metrics(
        self,
        trades: List[Dict[str, Any]],
        equity_curve: List[float],
        initial_capital: float,
        risk_free_rate: float = 0.02,
    ) -> Dict[str, Any]:
        """Calculate comprehensive performance metrics.

        Args:
            trades: List of trade dictionaries with 'pnl' and other trade data
            equity_curve: List of equity values over time
            initial_capital: Starting capital amount
            risk_free_rate: Risk-free rate for Sharpe ratio calculation
                           (default 2%)

        Returns:
            Dictionary containing comprehensive performance metrics
        """
        try:
            if not trades and not equity_curve:
                return self._empty_metrics()

            # Basic trade statistics
            total_trades = len(trades)
            winning_trades = [t for t in trades if t.get("pnl", 0) > 0]
            losing_trades = [t for t in trades if t.get("pnl", 0) < 0]

            num_winning_trades = len(winning_trades)
            num_losing_trades = len(losing_trades)

            # Win rate
            win_rate = num_winning_trades / total_trades if total_trades > 0 else 0

            # P&L statistics
            total_pnl = sum(t.get("pnl", 0) for t in trades)
            gross_profit = sum(t.get("pnl", 0) for t in winning_trades)
            gross_loss = sum(abs(t.get("pnl", 0)) for t in losing_trades)

            # Average win/loss
            average_win = (
                gross_profit / num_winning_trades if num_winning_trades > 0 else 0
            )
            average_loss = (
                gross_loss / num_losing_trades if num_losing_trades > 0 else 0
            )

            # Profit factor
            profit_factor = (
                gross_profit / gross_loss
                if gross_loss > 0
                else float("inf") if gross_profit > 0 else 0
            )

            # Return metrics
            if len(equity_curve) > 1:
                final_capital = equity_curve[-1]
                total_return = (final_capital - initial_capital) / initial_capital
                total_return_pct = total_return * 100
            else:
                final_capital = initial_capital + total_pnl
                total_return = total_pnl / initial_capital
                total_return_pct = total_return * 100

            # Calculate additional metrics from equity curve
            risk_metrics = self._calculate_risk_metrics(
                equity_curve, initial_capital, risk_free_rate
            )

            # Trade timing metrics
            timing_metrics = self._calculate_timing_metrics(trades)

            # Combine all metrics
            metrics = {
                # Basic trade statistics
                "total_trades": total_trades,
                "winning_trades": num_winning_trades,
                "losing_trades": num_losing_trades,
                "win_rate": win_rate,
                # P&L metrics
                "total_pnl": total_pnl,
                "gross_profit": gross_profit,
                "gross_loss": gross_loss,
                "average_win": average_win,
                "average_loss": average_loss,
                "profit_factor": profit_factor,
                # Return metrics
                "total_return": total_return,
                "total_return_pct": total_return_pct,
                "final_capital": final_capital,
                # Risk metrics (from equity curve analysis)
                **risk_metrics,
                # Timing metrics
                **timing_metrics,
            }

            logger.debug(
                f"Calculated {len(metrics)} performance metrics "
                f"for {total_trades} trades"
            )
            return metrics

        except Exception as e:
            logger.error(f"Error calculating performance metrics: {str(e)}")
            return self._empty_metrics()

    def _calculate_risk_metrics(
        self, equity_curve: List[float], initial_capital: float, risk_free_rate: float
    ) -> Dict[str, Any]:
        """Calculate risk-based performance metrics from equity curve."""

        if len(equity_curve) < 2:
            return {
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "max_drawdown": 0.0,
                "max_drawdown_pct": 0.0,
                "volatility": 0.0,
                "var_95": 0.0,
                "cvar_95": 0.0,
            }

        try:
            # Convert to pandas series for easier calculation
            equity_series = pd.Series(equity_curve)

            # Calculate returns
            returns = equity_series.pct_change().dropna()

            if len(returns) == 0:
                return self._empty_risk_metrics()

            # Annualize returns (assuming daily data, adjust if needed)
            periods_per_year = 252  # Trading days

            # Mean return
            mean_return = returns.mean()
            annualized_return = mean_return * periods_per_year

            # Volatility
            volatility = returns.std()
            annualized_volatility = volatility * np.sqrt(periods_per_year)

            # Sharpe ratio
            excess_return = annualized_return - risk_free_rate
            sharpe_ratio = (
                excess_return / annualized_volatility
                if annualized_volatility > 0
                else 0
            )

            # Sortino ratio (downside deviation)
            negative_returns = returns[returns < 0]
            downside_deviation = (
                negative_returns.std() if len(negative_returns) > 0 else 0
            )
            annualized_downside_deviation = downside_deviation * np.sqrt(
                periods_per_year
            )
            sortino_ratio = (
                excess_return / annualized_downside_deviation
                if annualized_downside_deviation > 0
                else 0
            )

            # Maximum drawdown
            peak = equity_series.expanding().max()
            drawdown = (equity_series - peak) / peak
            max_drawdown_pct = drawdown.min()
            max_drawdown = abs(max_drawdown_pct * initial_capital)

            # Value at Risk (95% confidence)
            var_95 = returns.quantile(0.05)

            # Conditional VaR (Expected Shortfall)
            cvar_95 = (
                returns[returns <= var_95].mean()
                if len(returns[returns <= var_95]) > 0
                else 0
            )

            return {
                "sharpe_ratio": sharpe_ratio,
                "sortino_ratio": sortino_ratio,
                "max_drawdown": max_drawdown,
                "max_drawdown_pct": (max_drawdown_pct * 100),  # Convert to percentage
                "volatility": annualized_volatility,
                "annualized_return": annualized_return,
                "var_95": var_95,
                "cvar_95": cvar_95,
            }

        except Exception as e:
            logger.error(f"Error calculating risk metrics: {str(e)}")
            return self._empty_risk_metrics()

    def _calculate_timing_metrics(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate timing-related metrics from trades."""

        try:
            if not trades:
                return {
                    "average_trade_duration": 0,
                    "max_consecutive_wins": 0,
                    "max_consecutive_losses": 0,
                }

            # Calculate trade durations
            durations = []
            for trade in trades:
                entry_time = trade.get("entry_time")
                exit_time = trade.get("exit_time")

                if entry_time and exit_time:
                    if isinstance(entry_time, str):
                        entry_time = pd.to_datetime(entry_time)
                    if isinstance(exit_time, str):
                        exit_time = pd.to_datetime(exit_time)

                    # Convert to hours
                    duration = (exit_time - entry_time).total_seconds() / 3600
                    durations.append(duration)

            avg_duration = np.mean(durations) if durations else 0

            # Calculate consecutive wins/losses
            max_consecutive_wins = 0
            max_consecutive_losses = 0
            current_win_streak = 0
            current_loss_streak = 0

            for trade in trades:
                pnl = trade.get("pnl", 0)

                if pnl > 0:  # Winning trade
                    current_win_streak += 1
                    current_loss_streak = 0
                    max_consecutive_wins = max(max_consecutive_wins, current_win_streak)
                elif pnl < 0:  # Losing trade
                    current_loss_streak += 1
                    current_win_streak = 0
                    max_consecutive_losses = max(
                        max_consecutive_losses, current_loss_streak
                    )

            return {
                "average_trade_duration": avg_duration,
                "max_consecutive_wins": max_consecutive_wins,
                "max_consecutive_losses": max_consecutive_losses,
            }

        except Exception as e:
            logger.error(f"Error calculating timing metrics: {str(e)}")
            return {
                "average_trade_duration": 0,
                "max_consecutive_wins": 0,
                "max_consecutive_losses": 0,
            }

    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty/default metrics when no data is available."""
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "total_pnl": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "average_win": 0.0,
            "average_loss": 0.0,
            "profit_factor": 0.0,
            "total_return": 0.0,
            "total_return_pct": 0.0,
            "final_capital": 0.0,
            **self._empty_risk_metrics(),
            "average_trade_duration": 0.0,
            "max_consecutive_wins": 0,
            "max_consecutive_losses": 0,
        }

    def _empty_risk_metrics(self) -> Dict[str, Any]:
        """Return empty risk metrics."""
        return {
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "max_drawdown": 0.0,
            "max_drawdown_pct": 0.0,
            "volatility": 0.0,
            "annualized_return": 0.0,
            "var_95": 0.0,
            "cvar_95": 0.0,
        }

    def calculate_rolling_metrics(
        self, equity_curve: List[float], window: int = 30
    ) -> Dict[str, List[float]]:
        """Calculate rolling performance metrics.

        Args:
            equity_curve: List of equity values over time
            window: Rolling window size (default 30 periods)

        Returns:
            Dictionary with rolling metrics as lists
        """
        if len(equity_curve) < window:
            return {
                "rolling_sharpe": [],
                "rolling_volatility": [],
                "rolling_return": [],
            }

        try:
            equity_series = pd.Series(equity_curve)
            returns = equity_series.pct_change().dropna()

            # Rolling Sharpe ratio (simplified, using rolling std)
            rolling_return = returns.rolling(window).mean()
            rolling_volatility = returns.rolling(window).std()
            # Annualized
            rolling_sharpe = rolling_return / rolling_volatility * np.sqrt(252)

            return {
                "rolling_sharpe": rolling_sharpe.dropna().tolist(),
                "rolling_volatility": (rolling_volatility * np.sqrt(252))
                .dropna()
                .tolist(),  # Annualized
                "rolling_return": (rolling_return * 252)
                .dropna()
                .tolist(),  # Annualized
            }

        except Exception as e:
            logger.error(f"Error calculating rolling metrics: {str(e)}")
            return {
                "rolling_sharpe": [],
                "rolling_volatility": [],
                "rolling_return": [],
            }

    def benchmark_comparison(
        self,
        equity_curve: List[float],
        benchmark_curve: List[float],
        initial_capital: float,
    ) -> Dict[str, Any]:
        """Compare performance against a benchmark.

        Args:
            equity_curve: Portfolio equity curve
            benchmark_curve: Benchmark equity curve
            initial_capital: Starting capital

        Returns:
            Dictionary with comparison metrics
        """
        try:
            if len(equity_curve) != len(benchmark_curve):
                logger.warning(
                    "Equity curve and benchmark curve have different lengths"
                )
                return {"alpha": 0.0, "beta": 0.0, "information_ratio": 0.0}

            portfolio_returns = pd.Series(equity_curve).pct_change().dropna()
            benchmark_returns = pd.Series(benchmark_curve).pct_change().dropna()

            if len(portfolio_returns) == 0 or len(benchmark_returns) == 0:
                return {"alpha": 0.0, "beta": 0.0, "information_ratio": 0.0}

            # Calculate beta (sensitivity to benchmark)
            covariance = np.cov(portfolio_returns, benchmark_returns)[0, 1]
            benchmark_variance = np.var(benchmark_returns)
            beta = covariance / benchmark_variance if benchmark_variance > 0 else 0

            # Calculate alpha (excess return)
            portfolio_mean = portfolio_returns.mean() * 252  # Annualized
            benchmark_mean = benchmark_returns.mean() * 252  # Annualized
            alpha = portfolio_mean - (beta * benchmark_mean)

            # Information ratio (active return / tracking error)
            active_returns = portfolio_returns - benchmark_returns
            tracking_error = active_returns.std() * np.sqrt(252)  # Annualized
            information_ratio = (
                active_returns.mean() * 252 / tracking_error
                if tracking_error > 0
                else 0
            )

            return {
                "alpha": alpha,
                "beta": beta,
                "information_ratio": information_ratio,
                "tracking_error": tracking_error,
            }

        except Exception as e:
            logger.error(f"Error calculating benchmark comparison: {str(e)}")
            return {
                "alpha": 0.0,
                "beta": 0.0,
                "information_ratio": 0.0,
                "tracking_error": 0.0,
            }
