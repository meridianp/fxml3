"""
Performance analysis for backtesting results.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Union
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

from fxml4_core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PerformanceMetrics:
    """Container for performance metrics."""
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    max_drawdown_duration: int
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_trade_duration: float
    calmar_ratio: float
    recovery_factor: float
    expectancy: float
    var_95: float
    cvar_95: float


class PerformanceAnalyzer:
    """Analyze backtest performance."""
    
    def __init__(self, risk_free_rate: float = 0.02):
        self.risk_free_rate = risk_free_rate
        self.metrics = None
        self.equity_curve = None
        self.trades = None
    
    def calculate_metrics(
        self,
        equity_curve: pd.DataFrame,
        trades: pd.DataFrame,
        initial_capital: float
    ) -> PerformanceMetrics:
        """Calculate all performance metrics."""
        self.equity_curve = equity_curve
        self.trades = trades
        
        # Basic returns
        total_return = self._calculate_total_return(equity_curve, initial_capital)
        annualized_return = self._calculate_annualized_return(equity_curve)
        
        # Risk metrics
        sharpe_ratio = self._calculate_sharpe_ratio(equity_curve)
        sortino_ratio = self._calculate_sortino_ratio(equity_curve)
        max_dd, max_dd_duration = self._calculate_max_drawdown(equity_curve)
        
        # Trade statistics
        trade_stats = self._calculate_trade_statistics(trades)
        
        # Advanced metrics
        calmar_ratio = annualized_return / abs(max_dd) if max_dd != 0 else 0
        recovery_factor = total_return / abs(max_dd) if max_dd != 0 else 0
        var_95, cvar_95 = self._calculate_var_cvar(equity_curve)
        
        self.metrics = PerformanceMetrics(
            total_return=total_return,
            annualized_return=annualized_return,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_dd,
            max_drawdown_duration=max_dd_duration,
            win_rate=trade_stats['win_rate'],
            profit_factor=trade_stats['profit_factor'],
            avg_win=trade_stats['avg_win'],
            avg_loss=trade_stats['avg_loss'],
            total_trades=trade_stats['total_trades'],
            winning_trades=trade_stats['winning_trades'],
            losing_trades=trade_stats['losing_trades'],
            avg_trade_duration=trade_stats['avg_duration'],
            calmar_ratio=calmar_ratio,
            recovery_factor=recovery_factor,
            expectancy=trade_stats['expectancy'],
            var_95=var_95,
            cvar_95=cvar_95
        )
        
        logger.info(
            "Performance metrics calculated - Return: %.2f%%, Sharpe: %.2f",
            total_return * 100,
            sharpe_ratio
        )
        
        return self.metrics
    
    def _calculate_total_return(
        self,
        equity_curve: pd.DataFrame,
        initial_capital: float
    ) -> float:
        """Calculate total return."""
        if equity_curve.empty:
            return 0.0
        
        final_equity = equity_curve['equity'].iloc[-1]
        return (final_equity - initial_capital) / initial_capital
    
    def _calculate_annualized_return(self, equity_curve: pd.DataFrame) -> float:
        """Calculate annualized return."""
        if equity_curve.empty or len(equity_curve) < 2:
            return 0.0
        
        # Calculate time period
        start_date = pd.to_datetime(equity_curve['timestamp'].iloc[0])
        end_date = pd.to_datetime(equity_curve['timestamp'].iloc[-1])
        years = (end_date - start_date).days / 365.25
        
        if years <= 0:
            return 0.0
        
        # Calculate annualized return
        total_return = equity_curve['equity'].iloc[-1] / equity_curve['equity'].iloc[0] - 1
        annualized_return = (1 + total_return) ** (1 / years) - 1
        
        return annualized_return
    
    def _calculate_sharpe_ratio(self, equity_curve: pd.DataFrame) -> float:
        """Calculate Sharpe ratio."""
        if 'returns' not in equity_curve or equity_curve['returns'].std() == 0:
            return 0.0
        
        returns = equity_curve['returns'].dropna()
        if len(returns) < 2:
            return 0.0
        
        # Annualized Sharpe ratio
        mean_return = returns.mean() * 252  # Daily to annual
        std_return = returns.std() * np.sqrt(252)
        
        if std_return == 0:
            return 0.0
        
        return (mean_return - self.risk_free_rate) / std_return
    
    def _calculate_sortino_ratio(self, equity_curve: pd.DataFrame) -> float:
        """Calculate Sortino ratio."""
        if 'returns' not in equity_curve:
            return 0.0
        
        returns = equity_curve['returns'].dropna()
        if len(returns) < 2:
            return 0.0
        
        # Downside deviation
        negative_returns = returns[returns < 0]
        if len(negative_returns) == 0:
            return float('inf')
        
        downside_std = negative_returns.std() * np.sqrt(252)
        if downside_std == 0:
            return 0.0
        
        mean_return = returns.mean() * 252
        return (mean_return - self.risk_free_rate) / downside_std
    
    def _calculate_max_drawdown(
        self,
        equity_curve: pd.DataFrame
    ) -> tuple[float, int]:
        """Calculate maximum drawdown and duration."""
        if equity_curve.empty:
            return 0.0, 0
        
        equity = equity_curve['equity'].values
        
        # Calculate running maximum
        running_max = np.maximum.accumulate(equity)
        
        # Calculate drawdown
        drawdown = (equity - running_max) / running_max
        
        # Find maximum drawdown
        max_drawdown = drawdown.min()
        
        # Calculate drawdown duration
        drawdown_start = None
        max_duration = 0
        current_duration = 0
        
        for i, dd in enumerate(drawdown):
            if dd < 0:
                if drawdown_start is None:
                    drawdown_start = i
                current_duration = i - drawdown_start
            else:
                if drawdown_start is not None:
                    max_duration = max(max_duration, current_duration)
                    drawdown_start = None
                    current_duration = 0
        
        # Check if still in drawdown
        if drawdown_start is not None:
            max_duration = max(max_duration, len(drawdown) - drawdown_start)
        
        return max_drawdown, max_duration
    
    def _calculate_trade_statistics(self, trades: pd.DataFrame) -> Dict[str, float]:
        """Calculate trade statistics."""
        stats = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'expectancy': 0.0,
            'avg_duration': 0.0
        }
        
        if trades.empty:
            return stats
        
        # Calculate P&L for each trade
        if 'realized_pnl' in trades.columns:
            pnl = trades['realized_pnl']
        else:
            # Calculate from entry/exit prices
            pnl = (trades['exit_price'] - trades['entry_price']) * trades['quantity']
            if 'commission' in trades.columns:
                pnl -= trades['commission']
        
        # Basic statistics
        stats['total_trades'] = len(trades)
        winning_trades = pnl > 0
        losing_trades = pnl < 0
        
        stats['winning_trades'] = winning_trades.sum()
        stats['losing_trades'] = losing_trades.sum()
        stats['win_rate'] = stats['winning_trades'] / stats['total_trades'] if stats['total_trades'] > 0 else 0
        
        # Average win/loss
        if stats['winning_trades'] > 0:
            stats['avg_win'] = pnl[winning_trades].mean()
        
        if stats['losing_trades'] > 0:
            stats['avg_loss'] = abs(pnl[losing_trades].mean())
        
        # Profit factor
        gross_profit = pnl[winning_trades].sum() if stats['winning_trades'] > 0 else 0
        gross_loss = abs(pnl[losing_trades].sum()) if stats['losing_trades'] > 0 else 1
        stats['profit_factor'] = gross_profit / gross_loss if gross_loss != 0 else 0
        
        # Expectancy
        stats['expectancy'] = pnl.mean()
        
        # Average duration
        if 'opened_at' in trades.columns and 'closed_at' in trades.columns:
            durations = pd.to_datetime(trades['closed_at']) - pd.to_datetime(trades['opened_at'])
            stats['avg_duration'] = durations.mean().total_seconds() / 3600  # Hours
        
        return stats
    
    def _calculate_var_cvar(
        self,
        equity_curve: pd.DataFrame,
        confidence: float = 0.95
    ) -> tuple[float, float]:
        """Calculate Value at Risk and Conditional Value at Risk."""
        if 'returns' not in equity_curve:
            return 0.0, 0.0
        
        returns = equity_curve['returns'].dropna()
        if len(returns) < 20:
            return 0.0, 0.0
        
        # Calculate VaR
        var_percentile = (1 - confidence) * 100
        var = np.percentile(returns, var_percentile)
        
        # Calculate CVaR (expected shortfall)
        cvar = returns[returns <= var].mean()
        
        return var, cvar
    
    def plot_performance(
        self,
        save_path: Optional[str] = None,
        show: bool = True
    ) -> None:
        """Plot performance charts."""
        if self.equity_curve is None:
            logger.warning("No equity curve to plot")
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Backtest Performance Analysis', fontsize=16)
        
        # Plot 1: Equity curve
        ax = axes[0, 0]
        equity_curve = pd.DataFrame(self.equity_curve)
        equity_curve['timestamp'] = pd.to_datetime(equity_curve['timestamp'])
        ax.plot(equity_curve['timestamp'], equity_curve['equity'], 'b-', linewidth=2)
        ax.set_title('Equity Curve')
        ax.set_xlabel('Date')
        ax.set_ylabel('Equity ($)')
        ax.grid(True, alpha=0.3)
        
        # Plot 2: Drawdown
        ax = axes[0, 1]
        equity = equity_curve['equity'].values
        running_max = np.maximum.accumulate(equity)
        drawdown = (equity - running_max) / running_max * 100
        ax.fill_between(equity_curve['timestamp'], 0, drawdown, color='red', alpha=0.3)
        ax.plot(equity_curve['timestamp'], drawdown, 'r-', linewidth=1)
        ax.set_title('Drawdown')
        ax.set_xlabel('Date')
        ax.set_ylabel('Drawdown (%)')
        ax.grid(True, alpha=0.3)
        
        # Plot 3: Returns distribution
        ax = axes[1, 0]
        if 'returns' in equity_curve.columns:
            returns = equity_curve['returns'].dropna() * 100
            ax.hist(returns, bins=50, alpha=0.7, color='blue', edgecolor='black')
            ax.axvline(returns.mean(), color='red', linestyle='--', label=f'Mean: {returns.mean():.2f}%')
            ax.set_title('Returns Distribution')
            ax.set_xlabel('Daily Returns (%)')
            ax.set_ylabel('Frequency')
            ax.legend()
            ax.grid(True, alpha=0.3)
        
        # Plot 4: Trade analysis
        ax = axes[1, 1]
        if self.trades is not None and not self.trades.empty:
            # P&L distribution
            if 'realized_pnl' in self.trades.columns:
                pnl = self.trades['realized_pnl']
                wins = pnl[pnl > 0]
                losses = pnl[pnl < 0]
                
                ax.hist(wins, bins=20, alpha=0.7, color='green', label=f'Wins ({len(wins)})')
                ax.hist(losses, bins=20, alpha=0.7, color='red', label=f'Losses ({len(losses)})')
                ax.set_title('Trade P&L Distribution')
                ax.set_xlabel('P&L ($)')
                ax.set_ylabel('Frequency')
                ax.legend()
                ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Performance plot saved to {save_path}")
        
        if show:
            plt.show()
        else:
            plt.close()
    
    def generate_report(self) -> str:
        """Generate text performance report."""
        if self.metrics is None:
            return "No metrics calculated yet."
        
        report = f"""
BACKTEST PERFORMANCE REPORT
{'=' * 50}

RETURNS
-------
Total Return: {self.metrics.total_return * 100:.2f}%
Annualized Return: {self.metrics.annualized_return * 100:.2f}%

RISK METRICS
------------
Sharpe Ratio: {self.metrics.sharpe_ratio:.2f}
Sortino Ratio: {self.metrics.sortino_ratio:.2f}
Max Drawdown: {self.metrics.max_drawdown * 100:.2f}%
Max DD Duration: {self.metrics.max_drawdown_duration} periods
VaR (95%): {self.metrics.var_95 * 100:.2f}%
CVaR (95%): {self.metrics.cvar_95 * 100:.2f}%

TRADE STATISTICS
----------------
Total Trades: {self.metrics.total_trades}
Win Rate: {self.metrics.win_rate * 100:.2f}%
Profit Factor: {self.metrics.profit_factor:.2f}
Average Win: ${self.metrics.avg_win:.2f}
Average Loss: ${self.metrics.avg_loss:.2f}
Expectancy: ${self.metrics.expectancy:.2f}
Avg Duration: {self.metrics.avg_trade_duration:.1f} hours

ADVANCED METRICS
----------------
Calmar Ratio: {self.metrics.calmar_ratio:.2f}
Recovery Factor: {self.metrics.recovery_factor:.2f}
"""
        
        return report