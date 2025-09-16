"""Performance metrics module for backtesting.

This module provides comprehensive performance metrics for evaluating trading strategies,
including risk-adjusted returns, drawdown analysis, and multi-scenario comparison.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for backtesting results."""
    
    # Basic metrics
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
    drawdown_duration: timedelta
    recovery_factor: float
    calmar_ratio: float
    ulcer_index: float
    
    # Trade metrics
    num_trades: int
    win_rate: float
    profit_factor: float
    avg_profit_per_trade: float
    avg_loss_per_trade: float
    avg_trade_duration: timedelta
    max_consecutive_wins: int
    max_consecutive_losses: int
    
    # Value at Risk metrics
    var_95: float
    var_99: float
    cvar_95: float
    cvar_99: float
    
    # Benchmark comparison (if available)
    alpha: Optional[float] = None
    beta: Optional[float] = None
    correlation: Optional[float] = None
    information_ratio: Optional[float] = None
    treynor_ratio: Optional[float] = None
    up_capture: Optional[float] = None
    down_capture: Optional[float] = None
    
    # Exposure metrics
    avg_exposure: Optional[float] = None
    max_leverage: Optional[float] = None
    concentration: Optional[float] = None
    net_exposure: Optional[float] = None
    
    # Cost metrics
    total_fees: Optional[float] = None
    total_slippage: Optional[float] = None
    cost_per_trade: Optional[float] = None
    cost_as_pct_of_profit: Optional[float] = None
    
    # Additional metrics
    expectancy: Optional[float] = None
    kelly_percentage: Optional[float] = None
    r_squared: Optional[float] = None
    skewness: Optional[float] = None
    kurtosis: Optional[float] = None
    
    # Raw data
    equity_curve: Optional[pd.DataFrame] = None
    monthly_returns: Optional[pd.DataFrame] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary.
        
        Returns:
            Dictionary of metrics (excluding dataframes).
        """
        result = {}
        for field, value in self.__dict__.items():
            if not isinstance(value, pd.DataFrame):
                result[field] = value
        return result
    
    def summary(self) -> str:
        """Generate a summary of the most important metrics.
        
        Returns:
            String summary of key metrics.
        """
        summary_lines = [
            f"Total Return: {self.total_return_pct:.2f}%",
            f"Annualized Return: {self.annualized_return:.2f}%",
            f"Sharpe Ratio: {self.sharpe_ratio:.2f}",
            f"Max Drawdown: {self.max_drawdown_pct:.2f}%",
            f"Win Rate: {self.win_rate:.2%}",
            f"Profit Factor: {self.profit_factor:.2f}",
            f"Number of Trades: {self.num_trades}",
        ]
        
        if self.alpha is not None and self.beta is not None:
            summary_lines.extend([
                f"Alpha: {self.alpha:.4f}",
                f"Beta: {self.beta:.2f}",
            ])
            
        return "\n".join(summary_lines)


class PerformanceAnalyzer:
    """Analyzer for calculating performance metrics from backtest results."""
    
    def __init__(
        self,
        risk_free_rate: float = 0.0,
        annualization_factor: int = 252,
        benchmark_data: Optional[pd.DataFrame] = None,
        benchmark_col: str = "close",
    ):
        """Initialize the performance analyzer.
        
        Args:
            risk_free_rate: Annual risk-free rate (default: 0.0).
            annualization_factor: Number of periods in a year (default: 252 for daily).
            benchmark_data: Optional benchmark price data.
            benchmark_col: Column to use from benchmark data (default: "close").
        """
        self.risk_free_rate = risk_free_rate
        self.annualization_factor = annualization_factor
        self.benchmark_data = benchmark_data
        self.benchmark_col = benchmark_col
        
        # Calculate daily risk-free rate if needed
        self.daily_risk_free_rate = self.risk_free_rate / self.annualization_factor
    
    def calculate_metrics(
        self, 
        equity_curve: pd.DataFrame,
        trades: List[Dict[str, Any]],
        include_benchmark: bool = True,
    ) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics.
        
        Args:
            equity_curve: DataFrame with at least a column named 'equity'.
            trades: List of trade dictionaries.
            include_benchmark: Whether to calculate benchmark-relative metrics.
            
        Returns:
            PerformanceMetrics object with calculated metrics.
        """
        # Validate input data
        if "equity" not in equity_curve.columns:
            raise ValueError("equity_curve must contain an 'equity' column")
        
        # Make a copy to avoid modifying the original
        equity_df = equity_curve.copy()
        
        # Ensure index is datetime (if not already)
        if not isinstance(equity_df.index, pd.DatetimeIndex):
            if "timestamp" in equity_df.columns:
                equity_df.set_index("timestamp", inplace=True)
            elif "time" in equity_df.columns:
                equity_df.set_index("time", inplace=True)
            else:
                logger.warning("No timestamp column found in equity_curve, using integer index")
        
        # Calculate returns
        equity_df["return"] = equity_df["equity"].pct_change()
        
        # Calculate drawdown
        equity_df["peak"] = equity_df["equity"].cummax()
        equity_df["drawdown"] = (equity_df["equity"] - equity_df["peak"]) / equity_df["peak"]
        
        # Calculate benchmark returns if available
        benchmark_returns = None
        if include_benchmark and self.benchmark_data is not None:
            benchmark_df = self.benchmark_data.copy()
            if isinstance(benchmark_df, pd.Series):
                benchmark_returns = benchmark_df.pct_change().dropna()
            elif self.benchmark_col in benchmark_df.columns:
                benchmark_returns = benchmark_df[self.benchmark_col].pct_change().dropna()
                
            # Align benchmark returns with strategy returns
            if benchmark_returns is not None:
                benchmark_returns = benchmark_returns.reindex(equity_df.index, method="ffill")
        
        # Calculate basic return metrics
        total_return = equity_df["equity"].iloc[-1] - equity_df["equity"].iloc[0]
        total_return_pct = (total_return / equity_df["equity"].iloc[0]) * 100
        
        # Calculate time-weighted metrics
        start_date = equity_df.index[0]
        end_date = equity_df.index[-1]
        years = (end_date - start_date).days / 365.25
        
        # Calculate annualized return
        annualized_return = ((1 + total_return_pct / 100) ** (1 / years) - 1) * 100 if years > 0 else 0
        
        # Calculate volatility and risk-adjusted metrics
        returns = equity_df["return"].dropna()
        volatility = returns.std() * np.sqrt(self.annualization_factor)
        
        # Calculate Sharpe ratio
        excess_returns = returns - self.daily_risk_free_rate
        sharpe_ratio = excess_returns.mean() / returns.std() * np.sqrt(self.annualization_factor) if returns.std() > 0 else 0
        
        # Calculate Sortino ratio
        downside_returns = returns[returns < 0]
        sortino_ratio = excess_returns.mean() / downside_returns.std() * np.sqrt(self.annualization_factor) if len(downside_returns) > 0 and downside_returns.std() > 0 else 0
        
        # Calculate drawdown metrics
        max_drawdown = equity_df["drawdown"].min()
        max_drawdown_pct = max_drawdown * 100
        avg_drawdown = equity_df["drawdown"].mean()
        
        # Calculate drawdown duration
        in_drawdown = (equity_df["equity"] < equity_df["peak"])
        drawdown_duration = timedelta(0)
        if in_drawdown.any():
            # Find the start of the max drawdown
            max_dd_idx = equity_df["drawdown"].idxmin()
            # Find the last peak before max drawdown
            prev_peak_idx = equity_df.loc[:max_dd_idx]["equity"].idxmax()
            # Find the recovery point after max drawdown (or use end date if not recovered)
            recovered = False
            for i in range(equity_df.index.get_loc(max_dd_idx) + 1, len(equity_df)):
                if equity_df["equity"].iloc[i] >= equity_df["equity"].loc[prev_peak_idx]:
                    recovery_idx = equity_df.index[i]
                    recovered = True
                    break
            
            if recovered:
                drawdown_duration = recovery_idx - prev_peak_idx
            else:
                # If never recovered, calculate duration from peak to end
                drawdown_duration = equity_df.index[-1] - prev_peak_idx
        
        # Calculate recovery factor and Calmar ratio
        recovery_factor = abs(total_return / (max_drawdown * equity_df["equity"].iloc[0])) if max_drawdown != 0 else float('inf')
        calmar_ratio = annualized_return / abs(max_drawdown_pct) if max_drawdown_pct != 0 else float('inf')
        
        # Calculate Ulcer Index (root mean square of drawdowns)
        # Squaring drawdowns emphasizes larger drawdowns
        ulcer_index = np.sqrt(np.mean(equity_df["drawdown"] ** 2))
        
        # Calculate Value at Risk (VaR) and Conditional VaR (CVaR)
        var_95 = np.percentile(returns, 5) * 100  # 95% VaR (represented as a percentage)
        var_99 = np.percentile(returns, 1) * 100  # 99% VaR
        cvar_95 = returns[returns <= np.percentile(returns, 5)].mean() * 100  # 95% CVaR
        cvar_99 = returns[returns <= np.percentile(returns, 1)].mean() * 100  # 99% CVaR
        
        # Calculate trade metrics
        num_trades = len(trades)
        win_count = sum(1 for t in trades if t.get("pnl", 0) > 0)
        loss_count = sum(1 for t in trades if t.get("pnl", 0) <= 0)
        
        win_rate = win_count / num_trades if num_trades > 0 else 0
        
        # Calculate profit factor
        total_profit = sum(t.get("pnl", 0) for t in trades if t.get("pnl", 0) > 0)
        total_loss = abs(sum(t.get("pnl", 0) for t in trades if t.get("pnl", 0) < 0))
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        
        # Calculate average profit/loss per trade
        avg_profit_per_trade = total_profit / win_count if win_count > 0 else 0
        avg_loss_per_trade = total_loss / loss_count if loss_count > 0 else 0
        
        # Calculate trade durations
        trade_durations = []
        for trade in trades:
            if "entry_time" in trade and "exit_time" in trade:
                duration = trade["exit_time"] - trade["entry_time"]
                trade_durations.append(duration)
                
        avg_trade_duration = sum(trade_durations, timedelta(0)) / len(trade_durations) if trade_durations else timedelta(0)
        
        # Calculate consecutive wins/losses
        trade_results = [1 if t.get("pnl", 0) > 0 else 0 for t in trades]
        max_consecutive_wins = self._get_max_consecutive(trade_results, 1)
        max_consecutive_losses = self._get_max_consecutive(trade_results, 0)
        
        # Calculate benchmark comparison metrics
        alpha = None
        beta = None
        correlation = None
        information_ratio = None
        treynor_ratio = None
        up_capture = None
        down_capture = None
        r_squared = None
        
        if benchmark_returns is not None and len(benchmark_returns) > 0:
            # Align returns for comparison
            common_idx = returns.index.intersection(benchmark_returns.index)
            if len(common_idx) > 1:
                aligned_returns = returns.loc[common_idx]
                aligned_benchmark = benchmark_returns.loc[common_idx]
                
                # Calculate beta
                covariance = np.cov(aligned_returns, aligned_benchmark)[0, 1]
                variance = np.var(aligned_benchmark)
                beta = covariance / variance if variance > 0 else 0
                
                # Calculate alpha using CAPM
                alpha = (aligned_returns.mean() - self.daily_risk_free_rate) - beta * (aligned_benchmark.mean() - self.daily_risk_free_rate)
                alpha = alpha * self.annualization_factor  # Annualize alpha
                
                # Calculate correlation
                correlation = aligned_returns.corr(aligned_benchmark)
                
                # Calculate tracking error
                tracking_error = (aligned_returns - aligned_benchmark).std() * np.sqrt(self.annualization_factor)
                
                # Calculate information ratio
                excess_return = aligned_returns.mean() - aligned_benchmark.mean()
                information_ratio = excess_return / tracking_error * np.sqrt(self.annualization_factor) if tracking_error > 0 else 0
                
                # Calculate Treynor ratio
                treynor_ratio = excess_returns.mean() / beta * np.sqrt(self.annualization_factor) if beta > 0 else 0
                
                # Calculate up/down capture
                up_market = aligned_benchmark > 0
                down_market = aligned_benchmark < 0
                
                if up_market.any() and aligned_benchmark[up_market].mean() != 0:
                    up_capture = aligned_returns[up_market].mean() / aligned_benchmark[up_market].mean()
                
                if down_market.any() and aligned_benchmark[down_market].mean() != 0:
                    down_capture = aligned_returns[down_market].mean() / aligned_benchmark[down_market].mean()
                
                # Calculate R-squared (coefficient of determination)
                slope, intercept, r_value, p_value, std_err = stats.linregress(aligned_benchmark, aligned_returns)
                r_squared = r_value ** 2
        
        # Calculate additional statistical metrics
        skewness = returns.skew() if len(returns) > 2 else 0
        kurtosis = returns.kurtosis() if len(returns) > 3 else 0
        
        # Calculate expectancy and Kelly percentage
        expectancy = None
        kelly_percentage = None
        
        if win_rate > 0 and avg_loss_per_trade > 0:
            avg_win_loss_ratio = avg_profit_per_trade / avg_loss_per_trade
            expectancy = (win_rate * avg_win_loss_ratio) - (1 - win_rate)
            kelly_percentage = win_rate - ((1 - win_rate) / avg_win_loss_ratio)
            kelly_percentage = max(0, kelly_percentage) * 100  # Keep positive only, convert to percentage
        
        # Calculate monthly returns table
        monthly_returns = self._calculate_monthly_returns(equity_df)
        
        # Calculate cost metrics
        total_fees = sum(t.get("commission", 0) for t in trades)
        total_slippage = sum(t.get("slippage", 0) for t in trades)
        cost_per_trade = (total_fees + total_slippage) / num_trades if num_trades > 0 else 0
        cost_as_pct_of_profit = (total_fees + total_slippage) / total_profit * 100 if total_profit > 0 else 0
        
        # Create PerformanceMetrics object
        metrics = PerformanceMetrics(
            # Basic metrics
            total_return=total_return,
            total_return_pct=total_return_pct,
            annualized_return=annualized_return,
            volatility=volatility * 100,  # Convert to percentage
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            
            # Drawdown metrics
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            avg_drawdown=avg_drawdown,
            drawdown_duration=drawdown_duration,
            recovery_factor=recovery_factor,
            calmar_ratio=calmar_ratio,
            ulcer_index=ulcer_index,
            
            # Trade metrics
            num_trades=num_trades,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_profit_per_trade=avg_profit_per_trade,
            avg_loss_per_trade=avg_loss_per_trade,
            avg_trade_duration=avg_trade_duration,
            max_consecutive_wins=max_consecutive_wins,
            max_consecutive_losses=max_consecutive_losses,
            
            # Value at Risk metrics
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            
            # Benchmark comparison
            alpha=alpha,
            beta=beta,
            correlation=correlation,
            information_ratio=information_ratio,
            treynor_ratio=treynor_ratio,
            up_capture=up_capture,
            down_capture=down_capture,
            
            # Additional metrics
            expectancy=expectancy,
            kelly_percentage=kelly_percentage,
            r_squared=r_squared,
            skewness=skewness,
            kurtosis=kurtosis,
            
            # Cost metrics
            total_fees=total_fees,
            total_slippage=total_slippage,
            cost_per_trade=cost_per_trade,
            cost_as_pct_of_profit=cost_as_pct_of_profit,
            
            # Raw data
            equity_curve=equity_df,
            monthly_returns=monthly_returns,
        )
        
        return metrics
    
    def compare_strategies(
        self,
        strategy_results: Dict[str, Dict],
        key_metrics: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """Compare multiple strategy results.
        
        Args:
            strategy_results: Dict mapping strategy names to result dictionaries.
            key_metrics: Optional list of metrics to include in the comparison.
            
        Returns:
            DataFrame comparing strategy metrics.
        """
        if not strategy_results:
            return pd.DataFrame()
        
        # Default key metrics if not specified
        if key_metrics is None:
            key_metrics = [
                "total_return_pct", "annualized_return", "volatility",
                "sharpe_ratio", "sortino_ratio", "max_drawdown_pct",
                "win_rate", "profit_factor", "num_trades"
            ]
        
        # Initialize results dictionary
        comparison = {}
        
        # Calculate metrics for each strategy
        for strategy_name, result in strategy_results.items():
            if "equity_curve" not in result or "trades" not in result:
                logger.warning(f"Strategy {strategy_name} missing required data")
                continue
                
            metrics = self.calculate_metrics(
                equity_curve=result["equity_curve"],
                trades=result["trades"],
                include_benchmark=True,
            )
            
            # Convert to dict and extract requested metrics
            metrics_dict = metrics.to_dict()
            comparison[strategy_name] = {k: metrics_dict.get(k) for k in key_metrics}
        
        # Convert to DataFrame
        df = pd.DataFrame(comparison).T
        
        return df
    
    def analyze_drawdowns(
        self,
        equity_curve: pd.DataFrame,
        min_drawdown_pct: float = 0.02,  # 2%
        top_n: int = 5,
    ) -> pd.DataFrame:
        """Analyze major drawdown periods.
        
        Args:
            equity_curve: DataFrame with at least a column named 'equity'.
            min_drawdown_pct: Minimum drawdown percentage to include.
            top_n: Number of top drawdowns to return.
            
        Returns:
            DataFrame with drawdown analysis.
        """
        # Make a copy to avoid modifying the original
        equity_df = equity_curve.copy()
        
        # Ensure index is datetime
        if not isinstance(equity_df.index, pd.DatetimeIndex):
            if "timestamp" in equity_df.columns:
                equity_df.set_index("timestamp", inplace=True)
            elif "time" in equity_df.columns:
                equity_df.set_index("time", inplace=True)
        
        # Calculate drawdown
        equity_df["peak"] = equity_df["equity"].cummax()
        equity_df["drawdown"] = (equity_df["equity"] - equity_df["peak"]) / equity_df["peak"]
        
        # Initialize drawdown periods tracking
        drawdowns = []
        current_peak = equity_df.iloc[0]["equity"]
        peak_date = equity_df.index[0]
        in_drawdown = False
        
        # Scan through equity curve to find drawdown periods
        for idx, row in equity_df.iterrows():
            if row["equity"] >= current_peak:
                # New peak, reset tracking
                if in_drawdown:
                    # Calculate recovery time from previous drawdown
                    recovery_duration = idx - trough_date
                    
                    # Add to drawdowns if significant
                    if abs(max_drawdown) >= min_drawdown_pct:
                        drawdowns.append({
                            "start_date": peak_date,
                            "trough_date": trough_date,
                            "end_date": idx,
                            "duration": idx - peak_date,
                            "recovery_duration": recovery_duration,
                            "max_drawdown_pct": max_drawdown * 100,
                            "max_drawdown_amount": peak_value - trough_value,
                        })
                
                current_peak = row["equity"]
                peak_date = idx
                peak_value = row["equity"]
                in_drawdown = False
            elif row["equity"] < current_peak:
                # In drawdown period
                if not in_drawdown or row["equity"] < trough_value:
                    # Start of drawdown or new low
                    trough_date = idx
                    trough_value = row["equity"]
                    max_drawdown = (trough_value - current_peak) / current_peak
                
                in_drawdown = True
        
        # Handle final drawdown if still in progress
        if in_drawdown:
            # Calculate measures for current drawdown
            max_drawdown = (trough_value - current_peak) / current_peak
            
            # Add to drawdowns if significant
            if abs(max_drawdown) >= min_drawdown_pct:
                drawdowns.append({
                    "start_date": peak_date,
                    "trough_date": trough_date,
                    "end_date": equity_df.index[-1],
                    "duration": equity_df.index[-1] - peak_date,
                    "recovery_duration": timedelta(0),  # Not recovered yet
                    "max_drawdown_pct": max_drawdown * 100,
                    "max_drawdown_amount": peak_value - trough_value,
                    "recovered": False,
                })
        
        # Convert to DataFrame and sort by drawdown magnitude
        if not drawdowns:
            return pd.DataFrame()
            
        drawdown_df = pd.DataFrame(drawdowns)
        drawdown_df = drawdown_df.sort_values("max_drawdown_pct").iloc[:top_n]
        
        return drawdown_df
    
    def risk_contribution_analysis(
        self,
        trades: List[Dict[str, Any]],
    ) -> pd.DataFrame:
        """Analyze risk contribution from different factors.
        
        Args:
            trades: List of trade dictionaries.
            
        Returns:
            DataFrame with risk contribution analysis.
        """
        if not trades:
            return pd.DataFrame()
        
        # Group trades by symbol, market regime, etc.
        risk_groups = {}
        
        # Analyze by symbol
        symbols = set(t.get("symbol", "Unknown") for t in trades)
        symbol_pnl = {s: 0 for s in symbols}
        symbol_count = {s: 0 for s in symbols}
        symbol_win_count = {s: 0 for s in symbols}
        symbol_loss = {s: 0 for s in symbols}
        
        # Analyze by market regime if available
        regimes = set(
            t.get("metadata", {}).get("market_regime", "Unknown") 
            for t in trades 
            if "metadata" in t and "market_regime" in t.get("metadata", {})
        )
        regime_pnl = {r: 0 for r in regimes}
        regime_count = {r: 0 for r in regimes}
        regime_win_count = {r: 0 for r in regimes}
        
        # Analyze by time of day if available
        hours = set(t.get("entry_time").hour for t in trades if "entry_time" in t)
        hour_pnl = {h: 0 for h in hours}
        hour_count = {h: 0 for h in hours}
        hour_win_count = {h: 0 for h in hours}
        
        # Process each trade
        for trade in trades:
            symbol = trade.get("symbol", "Unknown")
            pnl = trade.get("pnl", 0)
            
            # Update symbol statistics
            symbol_pnl[symbol] += pnl
            symbol_count[symbol] += 1
            if pnl > 0:
                symbol_win_count[symbol] += 1
            else:
                symbol_loss[symbol] += abs(pnl)
            
            # Update regime statistics if available
            if "metadata" in trade and "market_regime" in trade.get("metadata", {}):
                regime = trade["metadata"]["market_regime"]
                regime_pnl[regime] += pnl
                regime_count[regime] += 1
                if pnl > 0:
                    regime_win_count[regime] += 1
            
            # Update time of day statistics if available
            if "entry_time" in trade:
                hour = trade["entry_time"].hour
                hour_pnl[hour] += pnl
                hour_count[hour] += 1
                if pnl > 0:
                    hour_win_count[hour] += 1
        
        # Create DataFrames for each analysis dimension
        
        # Symbol analysis
        symbol_data = []
        for symbol in symbols:
            win_rate = symbol_win_count[symbol] / symbol_count[symbol] if symbol_count[symbol] > 0 else 0
            avg_win = symbol_pnl[symbol] / symbol_win_count[symbol] if symbol_win_count[symbol] > 0 else 0
            avg_loss = symbol_loss[symbol] / (symbol_count[symbol] - symbol_win_count[symbol]) if (symbol_count[symbol] - symbol_win_count[symbol]) > 0 else 0
            
            symbol_data.append({
                "symbol": symbol,
                "count": symbol_count[symbol],
                "total_pnl": symbol_pnl[symbol],
                "win_rate": win_rate,
                "avg_win": avg_win,
                "avg_loss": avg_loss,
                "profit_factor": symbol_pnl[symbol] / symbol_loss[symbol] if symbol_loss[symbol] > 0 else float('inf'),
            })
        
        symbol_df = pd.DataFrame(symbol_data)
        
        # Regime analysis
        regime_data = []
        for regime in regimes:
            win_rate = regime_win_count[regime] / regime_count[regime] if regime_count[regime] > 0 else 0
            
            regime_data.append({
                "regime": regime,
                "count": regime_count[regime],
                "total_pnl": regime_pnl[regime],
                "win_rate": win_rate,
                "avg_pnl": regime_pnl[regime] / regime_count[regime] if regime_count[regime] > 0 else 0,
            })
        
        regime_df = pd.DataFrame(regime_data)
        
        # Time of day analysis
        hour_data = []
        for hour in hours:
            win_rate = hour_win_count[hour] / hour_count[hour] if hour_count[hour] > 0 else 0
            
            hour_data.append({
                "hour": hour,
                "count": hour_count[hour],
                "total_pnl": hour_pnl[hour],
                "win_rate": win_rate,
                "avg_pnl": hour_pnl[hour] / hour_count[hour] if hour_count[hour] > 0 else 0,
            })
        
        hour_df = pd.DataFrame(hour_data)
        
        # Combine into a dictionary of DataFrames
        return {
            "by_symbol": symbol_df.sort_values("total_pnl", ascending=False) if not symbol_df.empty else symbol_df,
            "by_regime": regime_df.sort_values("total_pnl", ascending=False) if not regime_df.empty else regime_df,
            "by_hour": hour_df.sort_values("hour") if not hour_df.empty else hour_df,
        }
    
    def create_monte_carlo_simulation(
        self,
        trades: List[Dict[str, Any]],
        initial_capital: float = 10000.0,
        num_simulations: int = 1000,
        percentiles: List[int] = [5, 25, 50, 75, 95],
    ) -> Dict[str, Any]:
        """Run Monte Carlo simulation by randomly reordering trades.
        
        Args:
            trades: List of trade dictionaries.
            initial_capital: Initial capital for simulations.
            num_simulations: Number of simulations to run.
            percentiles: Percentiles to calculate for the final results.
            
        Returns:
            Dictionary with simulation results.
        """
        if not trades:
            return {}
        
        # Extract P&L from trades
        pnls = [t.get("pnl", 0) for t in trades]
        
        # Initialize results arrays
        final_equities = np.zeros(num_simulations)
        max_drawdowns = np.zeros(num_simulations)
        
        # Run simulations
        for i in range(num_simulations):
            # Shuffle the P&Ls
            np.random.shuffle(pnls)
            
            # Calculate equity curve
            equity = initial_capital + np.cumsum(pnls)
            
            # Calculate drawdowns
            peak = np.maximum.accumulate(equity)
            drawdown = (equity - peak) / peak
            
            # Store results
            final_equities[i] = equity[-1]
            max_drawdowns[i] = drawdown.min()
        
        # Calculate percentiles
        equity_percentiles = {
            p: np.percentile(final_equities, p) for p in percentiles
        }
        
        drawdown_percentiles = {
            p: np.percentile(max_drawdowns, p) for p in percentiles
        }
        
        # Calculate probabilities
        prob_profit = np.mean(final_equities > initial_capital)
        prob_loss = 1 - prob_profit
        prob_drawdown_10 = np.mean(max_drawdowns < -0.1)  # Probability of >10% drawdown
        prob_drawdown_20 = np.mean(max_drawdowns < -0.2)  # Probability of >20% drawdown
        
        # Return results
        return {
            "final_equity_percentiles": equity_percentiles,
            "drawdown_percentiles": drawdown_percentiles,
            "probability_of_profit": prob_profit,
            "probability_of_loss": prob_loss,
            "probability_of_10pct_drawdown": prob_drawdown_10,
            "probability_of_20pct_drawdown": prob_drawdown_20,
            "final_equity_mean": np.mean(final_equities),
            "final_equity_std": np.std(final_equities),
            "max_drawdown_mean": np.mean(max_drawdowns),
            "max_drawdown_std": np.std(max_drawdowns),
        }
    
    def _calculate_monthly_returns(self, equity_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate monthly returns table.
        
        Args:
            equity_df: DataFrame with equity curve.
            
        Returns:
            DataFrame with monthly returns.
        """
        # Ensure we have datetime index
        if not isinstance(equity_df.index, pd.DatetimeIndex):
            return pd.DataFrame()
        
        # Resample to month-end (using 'ME' for month-end as 'M' is deprecated)
        monthly_equity = equity_df["equity"].resample("ME").last()
        
        # Calculate monthly returns
        monthly_returns = monthly_equity.pct_change().dropna() * 100
        
        # Create monthly returns table with year as rows and month as columns
        # First, create a Series with MultiIndex of (year, month)
        monthly_returns_series = pd.Series(
            monthly_returns.values,
            index=pd.MultiIndex.from_arrays([
                monthly_returns.index.year,
                monthly_returns.index.month
            ])
        )
        
        # Unstack to create the table
        returns_table = monthly_returns_series.unstack()
        
        # Calculate yearly totals
        returns_table["Annual"] = returns_table.sum(axis=1)
        
        # Calculate monthly averages
        monthly_means = returns_table.mean()
        returns_table.loc["Average"] = monthly_means
        
        return returns_table
    
    def _get_max_consecutive(self, results: List[int], value: int) -> int:
        """Calculate maximum consecutive occurrences of a value.
        
        Args:
            results: List of values (0 or 1).
            value: Value to count consecutive occurrences of.
            
        Returns:
            Maximum number of consecutive occurrences.
        """
        max_consecutive = 0
        current_consecutive = 0
        
        for result in results:
            if result == value:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
                
        return max_consecutive


class ScenarioAnalyzer:
    """Analyzer for comparing multiple trading scenarios."""
    
    def __init__(self, performance_analyzer: Optional[PerformanceAnalyzer] = None):
        """Initialize the scenario analyzer.
        
        Args:
            performance_analyzer: Optional PerformanceAnalyzer instance.
        """
        self.performance_analyzer = performance_analyzer or PerformanceAnalyzer()
        self.scenarios = {}
    
    def add_scenario(
        self,
        name: str,
        equity_curve: pd.DataFrame,
        trades: List[Dict[str, Any]],
        description: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a backtest scenario.
        
        Args:
            name: Scenario name.
            equity_curve: Equity curve DataFrame.
            trades: List of trade dictionaries.
            description: Optional scenario description.
            parameters: Optional dictionary of strategy parameters.
        """
        # Calculate metrics for this scenario
        metrics = self.performance_analyzer.calculate_metrics(equity_curve, trades)
        
        # Store the scenario
        self.scenarios[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "equity_curve": equity_curve,
            "trades": trades,
            "metrics": metrics,
        }
    
    def compare_scenarios(
        self,
        key_metrics: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """Compare all scenarios.
        
        Args:
            key_metrics: Optional list of metrics to include in the comparison.
            
        Returns:
            DataFrame comparing scenario metrics.
        """
        if not self.scenarios:
            return pd.DataFrame()
        
        # Default key metrics if not specified
        if key_metrics is None:
            key_metrics = [
                "total_return_pct", "annualized_return", "volatility",
                "sharpe_ratio", "sortino_ratio", "max_drawdown_pct",
                "win_rate", "profit_factor", "num_trades"
            ]
        
        # Create comparison DataFrame
        comparison = {}
        
        for name, scenario in self.scenarios.items():
            metrics_dict = scenario["metrics"].to_dict()
            comparison[name] = {k: metrics_dict.get(k) for k in key_metrics}
            
            # Add parameters if they exist
            if scenario["parameters"]:
                for param_name, param_value in scenario["parameters"].items():
                    comparison[name][f"param_{param_name}"] = param_value
        
        # Convert to DataFrame
        df = pd.DataFrame(comparison).T
        
        return df
    
    def compare_equity_curves(self) -> pd.DataFrame:
        """Compare equity curves across scenarios.
        
        Returns:
            DataFrame with aligned equity curves.
        """
        if not self.scenarios:
            return pd.DataFrame()
        
        # Extract and align equity curves
        equity_curves = {}
        
        for name, scenario in self.scenarios.items():
            equity_curves[name] = scenario["equity_curve"]["equity"]
        
        # Convert to DataFrame
        df = pd.DataFrame(equity_curves)
        
        return df
    
    def compare_drawdowns(
        self,
        min_drawdown_pct: float = 0.02,  # 2%
        top_n: int = 5,
    ) -> Dict[str, pd.DataFrame]:
        """Compare drawdown periods across scenarios.
        
        Args:
            min_drawdown_pct: Minimum drawdown percentage to include.
            top_n: Number of top drawdowns to return per scenario.
            
        Returns:
            Dictionary mapping scenario names to drawdown DataFrames.
        """
        if not self.scenarios:
            return {}
        
        # Analyze drawdowns for each scenario
        drawdowns = {}
        
        for name, scenario in self.scenarios.items():
            drawdown_df = self.performance_analyzer.analyze_drawdowns(
                scenario["equity_curve"],
                min_drawdown_pct,
                top_n,
            )
            drawdowns[name] = drawdown_df
        
        return drawdowns
    
    def analyze_parameter_sensitivity(
        self,
        parameter_name: str,
        metric_name: str = "sharpe_ratio",
    ) -> pd.DataFrame:
        """Analyze sensitivity of a metric to a specific parameter.
        
        Args:
            parameter_name: Name of the parameter to analyze.
            metric_name: Name of the metric to track.
            
        Returns:
            DataFrame with parameter values and corresponding metric values.
        """
        if not self.scenarios:
            return pd.DataFrame()
        
        # Extract parameter and metric values
        param_values = []
        metric_values = []
        scenario_names = []
        
        for name, scenario in self.scenarios.items():
            if not scenario["parameters"] or parameter_name not in scenario["parameters"]:
                continue
                
            param_value = scenario["parameters"][parameter_name]
            metric_value = scenario["metrics"].to_dict().get(metric_name)
            
            if metric_value is not None:
                param_values.append(param_value)
                metric_values.append(metric_value)
                scenario_names.append(name)
        
        if not param_values:
            return pd.DataFrame()
        
        # Create DataFrame
        sensitivity_df = pd.DataFrame({
            "scenario": scenario_names,
            "parameter": param_values,
            "metric": metric_values,
        })
        
        # Sort by parameter value
        sensitivity_df = sensitivity_df.sort_values("parameter")
        
        return sensitivity_df
    
    def find_optimal_scenario(self, metric_name: str = "sharpe_ratio") -> Tuple[str, Dict[str, Any]]:
        """Find the optimal scenario based on a specific metric.
        
        Args:
            metric_name: Name of the metric to optimize.
            
        Returns:
            Tuple of (scenario_name, scenario_data).
        """
        if not self.scenarios:
            return "", {}
        
        # Extract metric values
        metric_values = {}
        
        for name, scenario in self.scenarios.items():
            metric_value = scenario["metrics"].to_dict().get(metric_name)
            if metric_value is not None:
                metric_values[name] = metric_value
        
        if not metric_values:
            return "", {}
        
        # Find the optimal scenario
        optimal_name = max(metric_values.items(), key=lambda x: x[1])[0]
        
        return optimal_name, self.scenarios[optimal_name]