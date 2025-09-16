"""Backtesting engine for FXML4.

This module provides the core backtesting engine for evaluating trading strategies.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from fxml4.config import get_config

logger = logging.getLogger(__name__)


class OrderType(Enum):
    """Order type enumeration."""
    
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(Enum):
    """Order side enumeration."""
    
    BUY = "buy"
    SELL = "sell"


class PositionStatus(Enum):
    """Position status enumeration."""
    
    OPEN = "open"
    CLOSED = "closed"


@dataclass
class Order:
    """Order data structure."""
    
    order_id: str
    symbol: str
    order_type: OrderType
    side: OrderSide
    quantity: float
    price: Optional[float]
    stop_price: Optional[float]
    timestamp: datetime
    status: str
    filled_price: Optional[float] = None
    filled_timestamp: Optional[datetime] = None
    

@dataclass
class Position:
    """Position data structure."""
    
    position_id: str
    symbol: str
    side: OrderSide
    entry_price: float
    entry_timestamp: datetime
    quantity: float
    status: PositionStatus
    exit_price: Optional[float] = None
    exit_timestamp: Optional[datetime] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    

@dataclass
class BacktestResult:
    """Backtesting result data structure."""
    
    strategy_name: str
    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    total_return: float
    total_return_pct: float
    annualized_return: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    win_rate: float
    profit_factor: float
    avg_profit_per_trade: float
    avg_loss_per_trade: float
    trades: List[Position]
    equity_curve: pd.DataFrame
    
    # Added fields for extended metrics
    performance_metrics: Optional[Dict[str, Any]] = None
    drawdown_analysis: Optional[pd.DataFrame] = None
    risk_analysis: Optional[Dict[str, pd.DataFrame]] = None
    monte_carlo_results: Optional[Dict[str, Any]] = None
    
    def get_performance_metrics(self):
        """Get performance metrics.
        
        Returns:
            Dictionary of performance metrics or metrics object if available.
        """
        return self.performance_metrics
    
    def get_summary(self) -> str:
        """Get a summary of key backtest results.
        
        Returns:
            Summary string.
        """
        summary_lines = [
            f"Strategy: {self.strategy_name}",
            f"Symbol: {self.symbol}",
            f"Period: {self.start_date} to {self.end_date}",
            f"Initial Capital: ${self.initial_capital:.2f}",
            f"Final Capital: ${self.final_capital:.2f}",
            f"Total Return: ${self.total_return:.2f} ({self.total_return_pct:.2f}%)",
            f"Annualized Return: {self.annualized_return:.2f}%",
            f"Max Drawdown: {self.max_drawdown_pct:.2f}%",
            f"Sharpe Ratio: {self.sharpe_ratio:.2f}",
            f"Sortino Ratio: {self.sortino_ratio:.2f}",
            f"Win Rate: {self.win_rate * 100:.2f}%",
            f"Profit Factor: {self.profit_factor:.2f}",
            f"Avg Profit per Trade: ${self.avg_profit_per_trade:.2f}",
            f"Avg Loss per Trade: ${self.avg_loss_per_trade:.2f}",
            f"Total Trades: {len(self.trades)}",
        ]
        
        return "\n".join(summary_lines)
    
    def generate_report(
        self,
        output_dir: str = "output/reports",
        include_figures: bool = True,
        export_pdf: bool = False,
    ) -> str:
        """Generate a performance report.
        
        Args:
            output_dir: Directory to save the report.
            include_figures: Whether to include figures in the report.
            export_pdf: Whether to export the report as PDF.
            
        Returns:
            Path to the generated report file.
        """
        try:
            from fxml4.visualization.performance_charts import create_performance_dashboard
            from fxml4.visualization.report_generator import create_performance_report, export_to_pdf
            
            # Create figures if requested
            figures = []
            if include_figures:
                figures = create_performance_dashboard(
                    equity_curve=self.equity_curve,
                    trades=self.trades,
                    risk_analysis=self.risk_analysis,
                    monthly_returns=self.performance_metrics.get("monthly_returns") if self.performance_metrics else None,
                )
            
            # Additional data for the report
            additional_data = {}
            
            # Add Monte Carlo results if available
            if self.monte_carlo_results:
                additional_data["Monte Carlo Simulation"] = {
                    "Probability of Profit": f"{self.monte_carlo_results.get('probability_of_profit', 0):.2%}",
                    "Probability of >10% Drawdown": f"{self.monte_carlo_results.get('probability_of_10pct_drawdown', 0):.2%}",
                    "95th Percentile Final Equity": f"${self.monte_carlo_results.get('final_equity_percentiles', {}).get(95, 0):,.2f}",
                    "5th Percentile Final Equity": f"${self.monte_carlo_results.get('final_equity_percentiles', {}).get(5, 0):,.2f}",
                }
            
            # Generate report
            report_path = create_performance_report(
                strategy_name=self.strategy_name,
                metrics=self.performance_metrics,
                equity_curve=self.equity_curve,
                trades=self.trades,
                figures=figures,
                additional_data=additional_data,
                output_dir=output_dir
            )
            
            # Export to PDF if requested
            if export_pdf:
                pdf_path = export_to_pdf(report_path)
                return pdf_path
            
            return report_path
            
        except ImportError:
            logger.error("Unable to generate report: Required visualization modules not available")
            return ""
    

class BacktestEngine:
    """Backtesting engine for trading strategies."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the backtesting engine.
        
        Args:
            config: Backtesting configuration.
        """
        self.config = config or {}
        
        # Set default configuration values
        self.initial_capital = self.config.get(
            "initial_capital", 
            get_config("backtesting.initial_capital", 10000)
        )
        self.commission = self.config.get(
            "commission", 
            get_config("backtesting.commission", 0.0002)
        )
        self.slippage = self.config.get(
            "slippage", 
            get_config("backtesting.slippage", 0.0001)
        )
        
        # Initialize backtesting state
        self.reset()
        
        logger.info("Initialized backtesting engine")
    
    def reset(self) -> None:
        """Reset the backtesting engine state."""
        self.capital = self.initial_capital
        self.equity = self.initial_capital
        self.orders: List[Order] = []
        self.positions: List[Position] = []
        self.open_positions: Dict[str, Position] = {}
        self.equity_curve: List[Dict[str, Any]] = []
        self.current_timestamp: Optional[datetime] = None
        
        logger.debug("Reset backtesting engine state")
    
    def run(
        self,
        strategy: Callable[[pd.DataFrame, int, Dict[str, Any]], Dict[str, Any]],
        data: pd.DataFrame,
        strategy_params: Optional[Dict[str, Any]] = None,
    ) -> BacktestResult:
        """Run a backtest for a trading strategy.
        
        Args:
            strategy: Strategy function that generates signals.
            data: Market data for backtesting.
            strategy_params: Parameters for the strategy.
            
        Returns:
            Backtest results.
        """
        self.reset()
        strategy_params = strategy_params or {}
        
        # Ensure data is sorted by time
        if "time" in data.columns:
            data = data.sort_values("time")
        
        # Extract required data
        start_date = data.iloc[0]["time"] if "time" in data.columns else None
        end_date = data.iloc[-1]["time"] if "time" in data.columns else None
        symbol = strategy_params.get("symbol", "UNKNOWN")
        timeframe = strategy_params.get("timeframe", "UNKNOWN")
        strategy_name = strategy.__name__
        
        # Run the backtest
        logger.info(
            "Starting backtest: %s on %s (%s) from %s to %s",
            strategy_name,
            symbol,
            timeframe,
            start_date,
            end_date,
        )
        
        # Iterate through each bar
        for i in range(len(data)):
            bar = data.iloc[i]
            self.current_timestamp = bar["time"] if "time" in data.columns else datetime.now()
            
            # Process any pending orders
            self._process_orders(bar)
            
            # Calculate current equity
            self._calculate_equity(bar)
            
            # Generate signals for current bar
            signals = strategy(data.iloc[:i+1], i, strategy_params)
            
            # Process signals
            self._process_signals(signals, bar)
            
            # Save equity curve point
            self.equity_curve.append({
                "timestamp": self.current_timestamp,
                "equity": self.equity,
                "capital": self.capital,
            })
        
        # Close any remaining positions
        for symbol, position in list(self.open_positions.items()):
            self._close_position(symbol, data.iloc[-1])
        
        # Calculate performance metrics
        result = self._calculate_performance(strategy_name, symbol, timeframe, start_date, end_date)
        
        logger.info("Backtest completed: Final equity = %.2f", self.equity)
        
        # Auto-generate performance report if enabled in configuration
        auto_generate = get_config("backtesting.reporting.auto_generate", False)
        if auto_generate:
            try:
                include_figures = get_config("backtesting.reporting.include_figures", True)
                export_pdf = get_config("backtesting.reporting.export_pdf", False)
                output_dir = get_config("backtesting.reporting.output_dir", "output/reports")
                
                report_path = result.generate_report(
                    output_dir=output_dir,
                    include_figures=include_figures,
                    export_pdf=export_pdf
                )
                
                if report_path:
                    logger.info("Performance report auto-generated: %s", report_path)
                else:
                    logger.warning("Failed to auto-generate performance report")
            except Exception as e:
                logger.error("Error generating performance report: %s", str(e))
        
        return result
    
    def _process_orders(self, bar: pd.Series) -> None:
        """Process pending orders.
        
        Args:
            bar: Current price bar.
        """
        # TODO: Implement order processing logic
        pass
    
    def _process_signals(self, signals: Dict[str, Any], bar: pd.Series) -> None:
        """Process trading signals.
        
        Args:
            signals: Trading signals from strategy.
            bar: Current price bar.
        """
        # Check for entry signals
        if "entry" in signals and signals["entry"]:
            side = OrderSide.BUY if signals.get("direction", "buy") == "buy" else OrderSide.SELL
            symbol = signals.get("symbol", bar.get("symbol", "UNKNOWN"))
            
            # Check if we already have an open position
            if symbol not in self.open_positions:
                quantity = self._calculate_position_size(signals, bar)
                price = bar["close"]
                
                # Apply slippage
                if side == OrderSide.BUY:
                    price *= (1 + self.slippage)
                else:
                    price *= (1 - self.slippage)
                
                # Create position
                position_id = f"POS-{len(self.positions) + 1}"
                position = Position(
                    position_id=position_id,
                    symbol=symbol,
                    side=side,
                    entry_price=price,
                    entry_timestamp=self.current_timestamp,
                    quantity=quantity,
                    status=PositionStatus.OPEN,
                )
                
                # Update capital
                self.capital -= price * quantity
                
                # Add to positions
                self.positions.append(position)
                self.open_positions[symbol] = position
                
                logger.debug(
                    "Opened %s position: %s @ %.5f, quantity: %.2f",
                    side.value,
                    symbol,
                    price,
                    quantity,
                )
        
        # Check for exit signals
        if "exit" in signals and signals["exit"]:
            symbol = signals.get("symbol", bar.get("symbol", "UNKNOWN"))
            
            # Check if we have an open position to close
            if symbol in self.open_positions:
                self._close_position(symbol, bar)
    
    def _close_position(self, symbol: str, bar: pd.Series) -> None:
        """Close an open position.
        
        Args:
            symbol: Symbol of the position to close.
            bar: Current price bar.
        """
        position = self.open_positions[symbol]
        price = bar["close"]
        
        # Apply slippage
        if position.side == OrderSide.BUY:
            price *= (1 - self.slippage)
        else:
            price *= (1 + self.slippage)
        
        # Calculate P&L
        if position.side == OrderSide.BUY:
            pnl = (price - position.entry_price) * position.quantity
        else:
            pnl = (position.entry_price - price) * position.quantity
        
        # Apply commission
        commission = price * position.quantity * self.commission
        pnl -= commission
        
        # Update position
        position.exit_price = price
        position.exit_timestamp = self.current_timestamp
        position.status = PositionStatus.CLOSED
        position.pnl = pnl
        position.pnl_pct = pnl / (position.entry_price * position.quantity) * 100
        
        # Update capital with exit proceeds minus commission already accounted
        # for in the P&L calculation. When the position was opened, the entry
        # value was subtracted from ``self.capital``. Closing the position should
        # therefore only credit the exit proceeds (less commission), not the
        # profit again. Adding ``pnl`` here would double count the gain or loss.
        self.capital += price * position.quantity - commission
        
        # Remove from open positions
        del self.open_positions[symbol]
        
        logger.debug(
            "Closed %s position: %s @ %.5f, P&L: %.2f (%.2f%%)",
            position.side.value,
            symbol,
            price,
            pnl,
            position.pnl_pct,
        )
    
    def _calculate_position_size(self, signals: Dict[str, Any], bar: pd.Series) -> float:
        """Calculate position size based on strategy signals.
        
        Args:
            signals: Trading signals from strategy.
            bar: Current price bar.
            
        Returns:
            Position size (quantity).
        """
        # Use fixed percentage of capital by default
        risk_pct = signals.get("risk_pct", 0.02)
        
        # If risk per pip is specified, calculate based on stop loss
        if "stop_loss" in signals:
            stop_loss = signals["stop_loss"]
            price = bar["close"]
            risk_amount = self.capital * risk_pct
            pip_value = 0.0001 if price < 10 else 0.01  # Assume forex/crypto
            pip_risk = abs(price - stop_loss) / pip_value
            return risk_amount / (pip_risk * pip_value)
        
        # Otherwise, use fixed percentage of capital
        return (self.capital * risk_pct) / bar["close"]
    
    def _calculate_equity(self, bar: pd.Series) -> None:
        """Calculate current equity based on open positions.
        
        Args:
            bar: Current price bar.
        """
        unrealized_pnl = 0
        
        for symbol, position in self.open_positions.items():
            price = bar["close"]
            
            # Calculate unrealized P&L
            if position.side == OrderSide.BUY:
                unrealized_pnl += (price - position.entry_price) * position.quantity
            else:
                unrealized_pnl += (position.entry_price - price) * position.quantity
        
        self.equity = self.capital + unrealized_pnl
    
    def _calculate_performance(
        self, 
        strategy_name: str, 
        symbol: str, 
        timeframe: str,
        start_date: Optional[datetime], 
        end_date: Optional[datetime],
    ) -> BacktestResult:
        """Calculate performance metrics for the backtest.
        
        Args:
            strategy_name: Name of the strategy.
            symbol: Symbol that was traded.
            timeframe: Timeframe that was used.
            start_date: Start date of the backtest.
            end_date: End date of the backtest.
            
        Returns:
            Backtest results.
        """
        # Convert equity curve to DataFrame
        equity_df = pd.DataFrame(self.equity_curve)
        
        # Extract closed positions
        closed_positions = [p for p in self.positions if p.status == PositionStatus.CLOSED]
        
        # Convert Position objects to trade dictionaries for performance analysis
        trades = []
        for p in closed_positions:
            trades.append({
                'entry_time': p.entry_timestamp,
                'exit_time': p.exit_timestamp,
                'symbol': p.symbol,
                'side': p.side.value,
                'entry_price': p.entry_price,
                'exit_price': p.exit_price,
                'quantity': p.quantity,
                'pnl': p.pnl,
                'pnl_pct': p.pnl_pct,
            })
        
        # Basic metrics calculation (initial approach kept for backward compatibility)
        if len(equity_df) > 0:
            equity_df["return"] = equity_df["equity"].pct_change()
            
            # Calculate drawdown
            equity_df["peak"] = equity_df["equity"].cummax()
            equity_df["drawdown"] = (equity_df["equity"] - equity_df["peak"]) / equity_df["peak"]
            
            max_drawdown = equity_df["drawdown"].min()
            max_drawdown_pct = max_drawdown * 100
        else:
            max_drawdown = 0
            max_drawdown_pct = 0
        
        # Calculate trade statistics
        win_count = sum(1 for p in closed_positions if p.pnl > 0)
        loss_count = sum(1 for p in closed_positions if p.pnl <= 0)
        win_rate = win_count / len(closed_positions) if closed_positions else 0
        
        # Calculate profit and loss metrics
        total_profit = sum(p.pnl for p in closed_positions if p.pnl > 0)
        total_loss = sum(p.pnl for p in closed_positions if p.pnl <= 0)
        profit_factor = abs(total_profit / total_loss) if total_loss != 0 else float("inf")
        
        avg_profit = total_profit / win_count if win_count > 0 else 0
        avg_loss = total_loss / loss_count if loss_count > 0 else 0
        
        # Calculate return metrics
        total_return = self.equity - self.initial_capital
        total_return_pct = (total_return / self.initial_capital) * 100
        
        # Calculate Sharpe ratio (if we have daily returns)
        if len(equity_df) > 0:
            returns = equity_df["return"].dropna()
            sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0
            
            # Calculate Sortino ratio
            downside_returns = returns[returns < 0]
            sortino_ratio = (returns.mean() / downside_returns.std()) * np.sqrt(252) if len(downside_returns) > 0 and downside_returns.std() > 0 else 0
        else:
            sharpe_ratio = 0
            sortino_ratio = 0
        
        # Calculate annualized return
        if start_date and end_date:
            years = (end_date - start_date).days / 365
            annualized_return = ((1 + total_return_pct / 100) ** (1 / years) - 1) * 100 if years > 0 else 0
        else:
            annualized_return = 0
            
        # Advanced metrics calculation using PerformanceAnalyzer if available
        advanced_metrics = None
        drawdown_analysis = None
        risk_analysis = None
        monte_carlo_results = None
        
        try:
            from fxml4.backtesting.performance_metrics import PerformanceAnalyzer
            
            # Initialize performance analyzer
            analyzer = PerformanceAnalyzer(
                risk_free_rate=0.02,  # Default to 2% risk-free rate
                annualization_factor=252,  # Default to 252 trading days per year
            )
            
            # Calculate comprehensive metrics
            metrics_obj = analyzer.calculate_metrics(
                equity_curve=equity_df,
                trades=trades,
                include_benchmark=False,  # No benchmark data by default
            )
            
            # Store the metrics object for later use
            advanced_metrics = metrics_obj
            
            # Analyze drawdowns
            drawdown_analysis = analyzer.analyze_drawdowns(
                equity_df,
                min_drawdown_pct=0.01,  # Include drawdowns of 1% or more
                top_n=5,  # Return top 5 drawdowns
            )
            
            # Analyze risk contribution by factors
            risk_analysis = analyzer.risk_contribution_analysis(trades)
            
            # Run Monte Carlo simulation for robustness testing
            if len(trades) >= 20:  # Only run if we have enough trades for statistical significance
                monte_carlo_results = analyzer.create_monte_carlo_simulation(
                    trades=trades,
                    initial_capital=self.initial_capital,
                    num_simulations=500,  # Default to 500 simulations
                )
                
            # Use more accurate metrics from advanced analysis if available
            if hasattr(metrics_obj, 'sharpe_ratio'):
                sharpe_ratio = metrics_obj.sharpe_ratio
            if hasattr(metrics_obj, 'sortino_ratio'):
                sortino_ratio = metrics_obj.sortino_ratio
            if hasattr(metrics_obj, 'max_drawdown_pct'):
                max_drawdown_pct = metrics_obj.max_drawdown_pct
            if hasattr(metrics_obj, 'win_rate'):
                win_rate = metrics_obj.win_rate
            if hasattr(metrics_obj, 'profit_factor'):
                profit_factor = metrics_obj.profit_factor
            if hasattr(metrics_obj, 'annualized_return'):
                annualized_return = metrics_obj.annualized_return
                
        except ImportError:
            logger.debug("PerformanceAnalyzer not available, using basic metrics only")
        
        # Create result object
        result = BacktestResult(
            strategy_name=strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date or datetime.now(),
            end_date=end_date or datetime.now(),
            initial_capital=self.initial_capital,
            final_capital=self.equity,
            total_return=total_return,
            total_return_pct=total_return_pct,
            annualized_return=annualized_return,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_profit_per_trade=avg_profit,
            avg_loss_per_trade=avg_loss,
            trades=closed_positions,
            equity_curve=equity_df,
            performance_metrics=advanced_metrics,
            drawdown_analysis=drawdown_analysis,
            risk_analysis=risk_analysis,
            monte_carlo_results=monte_carlo_results,
        )
        
        return result


def run_backtest(
    strategy: Callable[[pd.DataFrame, int, Dict[str, Any]], Dict[str, Any]],
    data: pd.DataFrame,
    strategy_params: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> BacktestResult:
    """Run a backtest for a trading strategy.
    
    Args:
        strategy: Strategy function that generates signals.
        data: Market data for backtesting.
        strategy_params: Parameters for the strategy.
        config: Backtesting configuration.
        
    Returns:
        Backtest results.
    """
    engine = BacktestEngine(config)
    return engine.run(strategy, data, strategy_params)