"""
Backtesting engines for FXML4.

This module provides backtesting engine implementations required by the test suite,
including event-driven backtesting for realistic trading simulation.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class SimpleBacktestEngine:
    """Simple backtesting engine with basic strategy support."""

    def __init__(self, initial_capital: float = 10000.0, commission: float = 0.0001):
        self.initial_capital = initial_capital
        self.commission = commission
        self.results = []

    def run_backtest(
        self,
        data: pd.DataFrame,
        strategy_func: Callable[[pd.DataFrame], pd.Series],
        symbol: str = "UNKNOWN",
    ) -> Dict[str, Any]:
        """Run a simple backtest on the provided data.

        Args:
            data: OHLCV data with datetime index
            strategy_func: Function that returns signals (-1, 0, 1)
            symbol: Trading symbol

        Returns:
            Dictionary with backtest results
        """
        try:
            # Generate trading signals
            signals = strategy_func(data)

            # Calculate returns
            data = data.copy()
            data["signal"] = signals
            data["returns"] = data["close"].pct_change()
            data["strategy_returns"] = data["signal"].shift(1) * data["returns"]

            # Calculate cumulative returns
            data["cumulative_returns"] = (1 + data["returns"]).cumprod()
            data["cumulative_strategy_returns"] = (
                1 + data["strategy_returns"]
            ).cumprod()

            # Calculate metrics
            total_return = data["cumulative_strategy_returns"].iloc[-1] - 1
            total_return_pct = total_return * 100

            # Calculate max drawdown
            running_max = data["cumulative_strategy_returns"].expanding().max()
            drawdown = (data["cumulative_strategy_returns"] - running_max) / running_max
            max_drawdown = drawdown.min()
            max_drawdown_pct = max_drawdown * 100

            # Calculate Sharpe ratio (simplified)
            if data["strategy_returns"].std() > 0:
                sharpe_ratio = (
                    data["strategy_returns"].mean()
                    / data["strategy_returns"].std()
                    * np.sqrt(252)
                )
            else:
                sharpe_ratio = 0

            # Calculate win rate
            winning_trades = (data["strategy_returns"] > 0).sum()
            total_trades = (data["strategy_returns"] != 0).sum()
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

            # Final portfolio value
            final_value = self.initial_capital * (1 + total_return)

            return {
                "backtest_id": f"BT-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                "symbol": symbol,
                "start_date": data.index[0].isoformat(),
                "end_date": data.index[-1].isoformat(),
                "initial_capital": self.initial_capital,
                "final_value": final_value,
                "total_return": total_return,
                "total_return_pct": total_return_pct,
                "max_drawdown": max_drawdown,
                "max_drawdown_pct": max_drawdown_pct,
                "sharpe_ratio": sharpe_ratio,
                "win_rate": win_rate,
                "total_trades": int(total_trades),
                "winning_trades": int(winning_trades),
                "data_points": len(data),
                "success": True,
            }

        except Exception as e:
            logger.error(f"Backtest error: {e}")
            return {
                "backtest_id": f"BT-ERROR-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                "symbol": symbol,
                "error": str(e),
                "success": False,
            }


def simple_ma_crossover_strategy(
    data: pd.DataFrame, fast_period: int = 20, slow_period: int = 50
) -> pd.Series:
    """Simple moving average crossover strategy.

    Args:
        data: OHLCV DataFrame
        fast_period: Fast MA period
        slow_period: Slow MA period

    Returns:
        Series of signals (-1, 0, 1)
    """
    # Calculate moving averages
    fast_ma = data["close"].rolling(window=fast_period).mean()
    slow_ma = data["close"].rolling(window=slow_period).mean()

    # Generate signals
    signals = pd.Series(0, index=data.index)
    signals[fast_ma > slow_ma] = 1  # Buy signal
    signals[fast_ma < slow_ma] = -1  # Sell signal

    return signals


def rsi_strategy(
    data: pd.DataFrame, period: int = 14, oversold: float = 30, overbought: float = 70
) -> pd.Series:
    """Simple RSI strategy.

    Args:
        data: OHLCV DataFrame
        period: RSI period
        oversold: Oversold threshold
        overbought: Overbought threshold

    Returns:
        Series of signals (-1, 0, 1)
    """
    # Calculate RSI
    delta = data["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    # Generate signals
    signals = pd.Series(0, index=data.index)
    signals[rsi < oversold] = 1  # Buy on oversold
    signals[rsi > overbought] = -1  # Sell on overbought

    return signals


class BacktestEngine:
    """Event-driven backtesting engine for realistic trading simulation.

    This class implements the interface expected by the backtesting test suite,
    supporting async operation with pluggable data handlers, execution handlers,
    portfolios, strategies, and risk managers.
    """

    def __init__(
        self,
        initial_capital: float,
        data_handler: Any,
        execution_handler: Any,
        portfolio: Any,
        strategy: Any,
        risk_manager: Any,
    ):
        """Initialize the backtesting engine.

        Args:
            initial_capital: Starting capital for the backtest
            data_handler: Historical data handler
            execution_handler: Execution handler for order processing
            portfolio: Portfolio manager
            strategy: Trading strategy
            risk_manager: Risk management system
        """
        self.initial_capital = initial_capital
        self.data_handler = data_handler
        self.execution_handler = execution_handler
        self.portfolio = portfolio
        self.strategy = strategy
        self.risk_manager = risk_manager

        # Backtest state
        self.current_time = None
        self.events = []
        self.running = False

        logger.info(f"Initialized BacktestEngine with capital: {initial_capital}")

    async def run_backtest(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Run the complete backtesting simulation.

        Args:
            start_date: Start date for the backtest
            end_date: End date for the backtest

        Returns:
            Dictionary containing backtest results including trades, performance, and equity curve
        """
        logger.info(f"Starting backtest from {start_date} to {end_date}")

        # Initialize components
        self.data_handler.reset()
        if hasattr(self.portfolio, "reset"):
            self.portfolio.reset()

        # Track backtest results
        trades = []
        equity_curve = [self.initial_capital]
        events_processed = 0

        self.running = True

        try:
            # Main event loop
            while self.running and self.data_handler.has_more_data():
                # Get current market data
                market_data = self.data_handler.get_latest_bars()

                if not market_data or all(
                    data is None for data in market_data.values()
                ):
                    # No more data available
                    break

                # Update current time
                for symbol, bar_data in market_data.items():
                    if bar_data is not None:
                        self.current_time = bar_data.name
                        break

                # Check if we're in the date range
                if self.current_time < start_date:
                    self.data_handler.update_bars()
                    continue

                if self.current_time > end_date:
                    break

                # Update portfolio with current prices
                current_prices = {}
                for symbol, bar_data in market_data.items():
                    if bar_data is not None:
                        current_prices[symbol] = bar_data["close"]

                if current_prices and hasattr(self.portfolio, "update_prices"):
                    self.portfolio.update_prices(current_prices)

                # Process each symbol's market data through strategy
                for symbol, bar_data in market_data.items():
                    if bar_data is not None:
                        # Create market event (mock event class for compatibility)
                        market_event = type(
                            "MarketEvent",
                            (),
                            {
                                "timestamp": self.current_time,
                                "symbol": symbol,
                                "data": bar_data,
                            },
                        )()

                        # Get signal from strategy
                        signal_event = await self._safe_strategy_call(market_event)

                        if signal_event:
                            # Process signal through risk management
                            if self.risk_manager and hasattr(
                                self.risk_manager, "check_signal"
                            ):
                                approved = self.risk_manager.check_signal(signal_event)
                                if not approved:
                                    continue

                            # Create order from signal
                            order = self._create_order_from_signal(signal_event)

                            if order:
                                # Execute order
                                fill = self._execute_order(order, bar_data)

                                if fill:
                                    # Update portfolio
                                    self.portfolio.update_fill(fill)

                                    # Record trade
                                    trade = self._create_trade_record(fill)
                                    trades.append(trade)

                # Update equity curve
                total_equity = self._calculate_total_equity()
                equity_curve.append(total_equity)

                # Move to next time step
                self.data_handler.update_bars()
                events_processed += 1

                # Safety check for infinite loops
                if events_processed > 100000:
                    logger.warning("Breaking backtest due to excessive iterations")
                    break

                # Small delay for async compatibility
                if events_processed % 100 == 0:
                    await asyncio.sleep(0.001)

        except Exception as e:
            logger.error(f"Error during backtesting: {str(e)}")
            raise

        finally:
            self.running = False

        # Calculate performance metrics
        performance_metrics = self._calculate_performance_metrics(trades, equity_curve)

        results = {
            "trades": trades,
            "performance": performance_metrics,
            "equity_curve": equity_curve,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "initial_capital": self.initial_capital,
            "final_capital": equity_curve[-1] if equity_curve else self.initial_capital,
            "events_processed": events_processed,
        }

        logger.info(
            f"Backtest completed. Processed {events_processed} events, {len(trades)} trades"
        )
        return results

    async def _safe_strategy_call(self, market_event):
        """Safely call strategy with error handling."""
        try:
            if hasattr(self.strategy, "calculate_signals"):
                if asyncio.iscoroutinefunction(self.strategy.calculate_signals):
                    return await self.strategy.calculate_signals(market_event)
                else:
                    return self.strategy.calculate_signals(market_event)
            return None
        except Exception as e:
            logger.error(f"Error in strategy calculation: {str(e)}")
            return None

    def _create_order_from_signal(self, signal_event) -> Optional[Dict[str, Any]]:
        """Create order from signal event."""
        if not signal_event:
            return None

        try:
            # Default position sizing (1% of capital)
            position_size = self.initial_capital * 0.01

            # Determine quantity (simplified for FX)
            if hasattr(signal_event, "symbol") and "/" in signal_event.symbol:
                # For FX pairs, use standard lot size
                quantity = 100000  # Standard lot
            else:
                quantity = int(position_size)  # For other assets

            order = {
                "timestamp": getattr(signal_event, "timestamp", self.current_time),
                "symbol": getattr(signal_event, "symbol", "UNKNOWN"),
                "order_type": "MARKET",
                "quantity": quantity,
                "direction": getattr(signal_event, "signal_type", "BUY"),
            }

            return order

        except Exception as e:
            logger.error(f"Error creating order from signal: {str(e)}")
            return None

    def _execute_order(
        self, order: Dict[str, Any], bar_data: Any
    ) -> Optional[Dict[str, Any]]:
        """Execute order and return fill event."""
        try:
            # Use execution handler if available
            if hasattr(self.execution_handler, "execute_order"):
                # Mock current price and spread for execution handler
                current_price = float(bar_data["close"])
                spread = 0.0002  # 2 pips default spread
                return self.execution_handler.execute_order(
                    order, current_price=current_price, spread=spread
                )

            # Simple fill simulation
            fill_price = float(bar_data["close"])
            commission = fill_price * order["quantity"] * 0.0002  # 0.02% commission

            fill = {
                "timestamp": order["timestamp"],
                "symbol": order["symbol"],
                "exchange": "SIMULATED",
                "quantity": order["quantity"],
                "direction": order["direction"],
                "fill_cost": fill_price * order["quantity"],
                "commission": commission,
                "fill_price": fill_price,
            }

            return fill

        except Exception as e:
            logger.error(f"Error executing order: {str(e)}")
            return None

    def _create_trade_record(self, fill: Dict[str, Any]) -> Dict[str, Any]:
        """Create trade record from fill event."""
        return {
            "entry_time": fill["timestamp"],
            "exit_time": None,  # Will be updated when position is closed
            "symbol": fill["symbol"],
            "direction": fill["direction"],
            "entry_price": fill["fill_price"],
            "exit_price": None,
            "size": fill["quantity"],
            "pnl": 0,  # Will be calculated when position is closed
            "commission": fill["commission"],
            "status": "open",
        }

    def _calculate_total_equity(self) -> float:
        """Calculate total equity including unrealized P&L."""
        try:
            if hasattr(self.portfolio, "get_total_equity"):
                return self.portfolio.get_total_equity()
            elif hasattr(self.portfolio, "total_equity"):
                return self.portfolio.total_equity
            else:
                # Fallback to initial capital
                return self.initial_capital
        except Exception:
            return self.initial_capital

    def _calculate_performance_metrics(
        self, trades: List[Dict[str, Any]], equity_curve: List[float]
    ) -> Dict[str, Any]:
        """Calculate performance metrics from trades and equity curve."""
        try:
            if len(equity_curve) < 2:
                return self._default_performance_metrics()

            # Basic metrics
            initial_capital = equity_curve[0]
            final_capital = equity_curve[-1]
            total_return = (final_capital - initial_capital) / initial_capital

            # Trade statistics
            completed_trades = [
                t for t in trades if t.get("status") == "closed" or t.get("pnl", 0) != 0
            ]
            winning_trades = [t for t in completed_trades if t.get("pnl", 0) > 0]
            losing_trades = [t for t in completed_trades if t.get("pnl", 0) < 0]

            win_rate = (
                len(winning_trades) / len(completed_trades) if completed_trades else 0
            )

            # Calculate returns series for risk metrics
            returns = []
            for i in range(1, len(equity_curve)):
                ret = (equity_curve[i] - equity_curve[i - 1]) / equity_curve[i - 1]
                returns.append(ret)

            # Risk metrics
            if returns:
                returns_array = np.array(returns)
                sharpe_ratio = (
                    np.mean(returns_array) / np.std(returns_array) * np.sqrt(252)
                    if np.std(returns_array) > 0
                    else 0
                )

                # Max drawdown
                peak = equity_curve[0]
                max_drawdown = 0
                for value in equity_curve:
                    if value > peak:
                        peak = value
                    drawdown = (peak - value) / peak
                    max_drawdown = max(max_drawdown, drawdown)

                # Sortino ratio
                negative_returns = returns_array[returns_array < 0]
                downside_std = (
                    np.std(negative_returns) if len(negative_returns) > 0 else 0
                )
                sortino_ratio = (
                    np.mean(returns_array) / downside_std * np.sqrt(252)
                    if downside_std > 0
                    else 0
                )
            else:
                sharpe_ratio = 0
                max_drawdown = 0
                sortino_ratio = 0

            # Profit factor
            gross_profit = sum(t.get("pnl", 0) for t in winning_trades)
            gross_loss = abs(sum(t.get("pnl", 0) for t in losing_trades))
            profit_factor = (
                gross_profit / gross_loss
                if gross_loss > 0
                else float("inf") if gross_profit > 0 else 0
            )

            return {
                "total_return": total_return,
                "annualized_return": (
                    (1 + total_return) ** (252 / len(equity_curve)) - 1
                    if len(equity_curve) > 1
                    else 0
                ),
                "volatility": np.std(returns) * np.sqrt(252) if returns else 0,
                "sharpe_ratio": sharpe_ratio,
                "sortino_ratio": sortino_ratio,
                "max_drawdown": -max_drawdown,  # Negative value
                "win_rate": win_rate,
                "profit_factor": profit_factor,
                "total_trades": len(trades),
                "winning_trades": len(winning_trades),
                "losing_trades": len(losing_trades),
                "avg_trade_pnl": (
                    np.mean([t.get("pnl", 0) for t in completed_trades])
                    if completed_trades
                    else 0
                ),
            }

        except Exception as e:
            logger.error(f"Error calculating performance metrics: {str(e)}")
            return self._default_performance_metrics()

    def _default_performance_metrics(self) -> Dict[str, Any]:
        """Return default performance metrics when calculation fails."""
        return {
            "total_return": 0.0,
            "annualized_return": 0.0,
            "volatility": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "profit_factor": 1.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "avg_trade_pnl": 0.0,
        }
