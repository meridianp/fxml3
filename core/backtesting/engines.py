"""
Unified backtesting engines for FXML4.

This module provides both abstract base classes and concrete implementations
for backtesting engines, including event-driven and vectorized approaches.
"""

import logging
import threading
import time
import uuid
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from queue import Empty, Queue
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import pandas as pd

# Conditional imports to avoid circular imports
if TYPE_CHECKING:
    from fxml4.backtesting.strategy import Strategy
    from fxml4.backtesting.performance_metrics import (
        PerformanceAnalyzer,
        PerformanceMetrics,
    )

from fxml4.backtesting.event import EventUnion
from fxml4.backtesting.events import (
    Event,
    EventType,
    FillEvent,
    MarketEvent,
    OrderEvent,
    SignalEvent,
)
from fxml4.backtesting.execution import ExecutionHandler, SlippageModel
from fxml4.backtesting.portfolio import Portfolio
from fxml4.config import get_config

logger = logging.getLogger(__name__)


# Compatibility enums and data structures
class OrderType(Enum):
    """Order types with lowercase values for compatibility."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(Enum):
    """Order sides with lowercase values for compatibility."""

    BUY = "buy"
    SELL = "sell"


class PositionStatus(Enum):
    """Position status enum."""

    OPEN = "open"
    CLOSED = "closed"


@dataclass
class Order:
    """Order data class for compatibility."""

    order_id: str
    symbol: str
    order_type: OrderType
    side: OrderSide
    quantity: float
    price: float
    timestamp: datetime
    status: str = "pending"
    filled_quantity: float = 0.0
    remaining_quantity: float = 0.0
    avg_fill_price: float = 0.0

    def __post_init__(self):
        self.remaining_quantity = self.quantity


@dataclass
class Position:
    """Position data class for compatibility."""

    symbol: str
    quantity: float
    avg_price: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float
    side: str
    status: PositionStatus = PositionStatus.OPEN
    open_time: Optional[datetime] = None
    close_time: Optional[datetime] = None


@dataclass
class BacktestResult:
    """Results of a backtest run."""

    initial_capital: float
    final_capital: float
    total_return: float
    annualized_return: float
    max_drawdown: float
    sharpe_ratio: float
    num_trades: int
    win_rate: float
    profit_factor: float
    start_date: datetime
    end_date: datetime
    equity_curve: pd.Series
    trades: List[Dict[str, Any]]
    metrics: Dict[str, Any]


class BacktestEngine(ABC):
    """Abstract base class for backtesting engines."""

    def __init__(
        self,
        initial_capital: float = 10000.0,
        commission: float = 0.001,
        slippage_model: str = "fixed",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage_model = slippage_model
        self.start_date = start_date
        self.end_date = end_date
        self.results = None

    @abstractmethod
    def run(self, strategy: "Strategy", data: pd.DataFrame) -> BacktestResult:
        """Run the backtest with the given strategy and data."""
        pass

    @abstractmethod
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for the backtest."""
        pass


class VectorizedEngine(BacktestEngine):
    """Vectorized backtesting engine for simple strategies."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.positions = {}
        self.trades = []
        self.equity_curve = None

    def run(self, strategy: "Strategy", data: pd.DataFrame) -> BacktestResult:
        """Run vectorized backtest."""
        # Filter data by date range
        if self.start_date:
            data = data[data.index >= self.start_date]
        if self.end_date:
            data = data[data.index <= self.end_date]

        # Generate signals
        signals = strategy.generate_signals(data)

        # Calculate returns
        returns = self._calculate_returns(data, signals)

        # Create equity curve
        self.equity_curve = (1 + returns).cumprod() * self.initial_capital

        # Calculate metrics
        metrics = self._calculate_metrics(returns)

        self.results = BacktestResult(
            initial_capital=self.initial_capital,
            final_capital=self.equity_curve.iloc[-1],
            total_return=metrics["total_return"],
            annualized_return=metrics["annualized_return"],
            max_drawdown=metrics["max_drawdown"],
            sharpe_ratio=metrics["sharpe_ratio"],
            num_trades=len(self.trades),
            win_rate=metrics["win_rate"],
            profit_factor=metrics["profit_factor"],
            start_date=data.index[0],
            end_date=data.index[-1],
            equity_curve=self.equity_curve,
            trades=self.trades,
            metrics=metrics,
        )

        return self.results

    def _calculate_returns(self, data: pd.DataFrame, signals: pd.Series) -> pd.Series:
        """Calculate returns from signals."""
        # Simple implementation - would be expanded based on strategy
        price_changes = data["close"].pct_change()
        returns = signals.shift(1) * price_changes
        return returns.fillna(0)

    def _calculate_metrics(self, returns: pd.Series) -> Dict[str, Any]:
        """Calculate performance metrics."""
        total_return = (1 + returns).prod() - 1
        annualized_return = (1 + total_return) ** (252 / len(returns)) - 1

        # Calculate drawdown
        cumulative = (1 + returns).cumprod()
        rolling_max = cumulative.expanding().max()
        drawdown = (cumulative - rolling_max) / rolling_max
        max_drawdown = drawdown.min()

        # Sharpe ratio
        sharpe_ratio = (
            returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        )

        # Trade statistics
        winning_trades = returns[returns > 0]
        losing_trades = returns[returns < 0]

        win_rate = (
            len(winning_trades) / len(returns[returns != 0])
            if len(returns[returns != 0]) > 0
            else 0
        )
        profit_factor = (
            winning_trades.sum() / abs(losing_trades.sum())
            if len(losing_trades) > 0
            else float("inf")
        )

        return {
            "total_return": total_return,
            "annualized_return": annualized_return,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "volatility": returns.std() * np.sqrt(252),
            "num_trades": len(returns[returns != 0]),
        }

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return self.results.metrics if self.results else {}


class EventDrivenEngine(BacktestEngine):
    """Event-driven backtesting engine for realistic trading simulation."""

    def __init__(
        self,
        initial_capital: float = 10000.0,
        commission: float = 0.001,
        slippage_model: str = "fixed",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        heartbeat: float = 0.0,
        max_iters: int = 1000000,
        fee_model: Optional[str] = None,
        risk_manager: Optional[Any] = None,
    ):
        super().__init__(
            initial_capital, commission, slippage_model, start_date, end_date
        )
        self.heartbeat = heartbeat
        self.max_iters = max_iters
        self.fee_model = fee_model
        self.risk_manager = risk_manager

        # Event handling
        self.events = Queue()
        self.continue_backtest = True
        self.iter_count = 0

        # Components
        self.data_handler = None
        self.strategy = None
        self.portfolio = None
        self.execution_handler = None

        # Performance tracking
        self.performance_analyzer = None
        self.equity_curve = []
        self.trades = []
        self.positions = {}

        # Threading
        self._stop_event = threading.Event()
        self._paused = False
        self._lock = threading.Lock()

    def setup_components(self, strategy: "Strategy", data: pd.DataFrame):
        """Set up the backtesting components."""
        # Data handler (simplified for this example)
        self.data_handler = data
        self.strategy = strategy

        # Portfolio
        self.portfolio = Portfolio(
            initial_capital=self.initial_capital,
            fee_model=self.fee_model,
            risk_manager=self.risk_manager,
        )

        # Execution handler
        self.execution_handler = ExecutionHandler(
            commission=self.commission, slippage_model=self.slippage_model
        )

    def run(self, strategy: "Strategy", data: pd.DataFrame) -> BacktestResult:
        """Run the event-driven backtest."""
        logger.info("Starting event-driven backtest")

        # Setup components
        self.setup_components(strategy, data)

        # Filter data by date range
        if self.start_date:
            data = data[data.index >= self.start_date]
        if self.end_date:
            data = data[data.index <= self.end_date]

        # Main event loop
        start_time = time.time()

        try:
            for i, (timestamp, row) in enumerate(data.iterrows()):
                if self._stop_event.is_set():
                    break

                if self.iter_count >= self.max_iters:
                    logger.warning(f"Max iterations ({self.max_iters}) reached")
                    break

                # Create market event
                market_event = MarketEvent(
                    timestamp=timestamp,
                    symbol=row.get("symbol", "DEFAULT"),
                    data={
                        "open": row.get("open", 0),
                        "high": row.get("high", 0),
                        "low": row.get("low", 0),
                        "close": row.get("close", 0),
                        "volume": row.get("volume", 0),
                    },
                )

                self.events.put(market_event)

                # Process all events in queue
                while not self.events.empty():
                    try:
                        event = self.events.get(timeout=1)
                        self._process_event(event)
                    except Empty:
                        continue

                # Track equity
                current_equity = self.portfolio.get_total_equity()
                self.equity_curve.append(
                    {"timestamp": timestamp, "equity": current_equity}
                )

                self.iter_count += 1

                # Heartbeat
                if self.heartbeat > 0:
                    time.sleep(self.heartbeat)

        except Exception as e:
            logger.error(f"Error in backtest loop: {e}")
            raise

        finally:
            end_time = time.time()
            logger.info(f"Backtest completed in {end_time - start_time:.2f} seconds")

        # Calculate final results
        return self._calculate_final_results(data)

    def _process_event(self, event: Event):
        """Process a single event."""
        if event.type == EventType.MARKET:
            # Update portfolio with new market data
            self.portfolio.update_market_data(event)

            # Generate signals
            signal = self.strategy.calculate_signals(event)
            if signal:
                self.events.put(signal)

        elif event.type == EventType.SIGNAL:
            # Generate orders from signals
            orders = self.portfolio.generate_orders(event)
            for order in orders:
                self.events.put(order)

        elif event.type == EventType.ORDER:
            # Execute orders
            fill_event = self.execution_handler.execute_order(event)
            if fill_event:
                self.events.put(fill_event)

        elif event.type == EventType.FILL:
            # Update portfolio with fills
            self.portfolio.update_fill(event)
            self.trades.append(self._create_trade_record(event))

    def _create_trade_record(self, fill_event: FillEvent) -> Dict[str, Any]:
        """Create a trade record from a fill event."""
        return {
            "timestamp": fill_event.timestamp,
            "symbol": fill_event.symbol,
            "quantity": fill_event.quantity,
            "price": fill_event.price,
            "side": fill_event.side,
            "commission": fill_event.commission,
            "order_id": fill_event.order_id,
        }

    def _calculate_final_results(self, data: pd.DataFrame) -> BacktestResult:
        """Calculate final backtest results."""
        # Convert equity curve to pandas Series
        equity_df = pd.DataFrame(self.equity_curve)
        if not equity_df.empty:
            equity_df.set_index("timestamp", inplace=True)
            equity_series = equity_df["equity"]
        else:
            equity_series = pd.Series([self.initial_capital], index=[data.index[0]])

        # Calculate metrics
        returns = equity_series.pct_change().dropna()

        final_capital = (
            equity_series.iloc[-1] if not equity_series.empty else self.initial_capital
        )
        total_return = (final_capital / self.initial_capital) - 1

        # Annualized return
        days = (data.index[-1] - data.index[0]).days
        annualized_return = ((1 + total_return) ** (365 / days)) - 1 if days > 0 else 0

        # Max drawdown
        rolling_max = equity_series.expanding().max()
        drawdown = (equity_series - rolling_max) / rolling_max
        max_drawdown = drawdown.min()

        # Sharpe ratio
        sharpe_ratio = (
            returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        )

        # Trade statistics
        winning_trades = [t for t in self.trades if t.get("pnl", 0) > 0]
        win_rate = len(winning_trades) / len(self.trades) if self.trades else 0

        total_profit = sum(t.get("pnl", 0) for t in winning_trades)
        total_loss = sum(t.get("pnl", 0) for t in self.trades if t.get("pnl", 0) < 0)
        profit_factor = (
            total_profit / abs(total_loss) if total_loss < 0 else float("inf")
        )

        metrics = {
            "total_return": total_return,
            "annualized_return": annualized_return,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "num_trades": len(self.trades),
            "volatility": returns.std() * np.sqrt(252) if not returns.empty else 0,
        }

        return BacktestResult(
            initial_capital=self.initial_capital,
            final_capital=final_capital,
            total_return=total_return,
            annualized_return=annualized_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            num_trades=len(self.trades),
            win_rate=win_rate,
            profit_factor=profit_factor,
            start_date=data.index[0],
            end_date=data.index[-1],
            equity_curve=equity_series,
            trades=self.trades,
            metrics=metrics,
        )

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return self.results.metrics if self.results else {}

    def stop(self):
        """Stop the backtest."""
        self._stop_event.set()
        self.continue_backtest = False

    def pause(self):
        """Pause the backtest."""
        self._paused = True

    def resume(self):
        """Resume the backtest."""
        self._paused = False


# Enhanced Portfolio class for event-driven engine
class EventDrivenPortfolio(Portfolio):
    """Enhanced portfolio for event-driven backtesting."""

    def __init__(
        self,
        initial_capital: float = 10000.0,
        fee_model: Optional[str] = None,
        risk_manager: Optional[Any] = None,
    ):
        super().__init__(initial_capital, fee_model, risk_manager)
        self.current_positions = {}
        self.closed_positions = []
        self.pending_orders = {}
        self.market_data = {}

    def update_market_data(self, market_event: MarketEvent):
        """Update market data for portfolio valuation."""
        self.market_data[market_event.symbol] = market_event.data

        # Update position values
        for symbol, position in self.current_positions.items():
            if symbol in self.market_data:
                current_price = self.market_data[symbol]["close"]
                position.market_value = position.quantity * current_price
                position.unrealized_pnl = position.market_value - (
                    position.quantity * position.avg_price
                )

    def generate_orders(self, signal_event: SignalEvent) -> List[OrderEvent]:
        """Generate orders from signal events."""
        orders = []

        # Simple order generation logic
        if signal_event.signal_type == "BUY":
            order = OrderEvent(
                symbol=signal_event.symbol,
                order_type="MKT",
                quantity=100,  # Fixed quantity for example
                direction="BUY",
                timestamp=signal_event.timestamp,
            )
            orders.append(order)
        elif signal_event.signal_type == "SELL":
            order = OrderEvent(
                symbol=signal_event.symbol,
                order_type="MKT",
                quantity=100,
                direction="SELL",
                timestamp=signal_event.timestamp,
            )
            orders.append(order)

        return orders

    def update_fill(self, fill_event: FillEvent):
        """Update portfolio with fill information."""
        symbol = fill_event.symbol

        if symbol not in self.current_positions:
            self.current_positions[symbol] = Position(
                symbol=symbol,
                quantity=0,
                avg_price=0,
                market_value=0,
                unrealized_pnl=0,
                realized_pnl=0,
                side="LONG",
                status=PositionStatus.OPEN,
            )

        position = self.current_positions[symbol]

        if fill_event.direction == "BUY":
            # Update position for buy
            total_cost = (
                position.quantity * position.avg_price
                + fill_event.quantity * fill_event.price
            )
            position.quantity += fill_event.quantity
            position.avg_price = (
                total_cost / position.quantity if position.quantity > 0 else 0
            )
        else:
            # Update position for sell
            position.quantity -= fill_event.quantity

            # If position is closed, move to closed positions
            if position.quantity == 0:
                position.status = PositionStatus.CLOSED
                self.closed_positions.append(position)
                del self.current_positions[symbol]

    def get_total_equity(self) -> float:
        """Get total portfolio equity."""
        cash = self.initial_capital

        # Add unrealized PnL from current positions
        for position in self.current_positions.values():
            cash += position.unrealized_pnl

        # Add realized PnL from closed positions
        for position in self.closed_positions:
            cash += position.realized_pnl

        return cash


# Export the main classes
__all__ = [
    "BacktestEngine",
    "VectorizedEngine",
    "EventDrivenEngine",
    "EventDrivenPortfolio",
    "BacktestResult",
    "Order",
    "Position",
    "OrderType",
    "OrderSide",
    "PositionStatus",
]
