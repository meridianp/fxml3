"""Event-driven backtesting engine for FXML4.

This module provides an event-driven backtesting engine for realistic trading simulation.
"""

import logging
import time
import uuid
from collections import deque
from datetime import datetime, timedelta
from queue import Queue
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import pandas as pd

from fxml4.backtesting.backtest_engine import BacktestResult, PositionStatus
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union, TYPE_CHECKING

# Conditional import to avoid circular imports
if TYPE_CHECKING:
    from fxml4.backtesting.performance_metrics import PerformanceAnalyzer, PerformanceMetrics
from fxml4.backtesting.event import (
    Event,
    EventType,
    EventUnion,
    FillEvent,
    MarketEvent,
    OrderEvent,
    SignalEvent,
)
from fxml4.backtesting.execution import ExecutionHandler, SlippageModel
from fxml4.config import get_config

logger = logging.getLogger(__name__)


class Portfolio:
    """Portfolio class for tracking positions, equity, and generating orders."""
    
    def __init__(
        self,
        initial_capital: float = 10000.0,
        fee_model: Optional[str] = None,
        risk_manager: Optional[Any] = None,
    ):
        """Initialize the portfolio.
        
        Args:
            initial_capital: Initial capital.
            fee_model: Fee model to use.
            risk_manager: Risk manager to use.
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.equity = initial_capital
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.closed_positions: List[Dict[str, Any]] = []
        self.orders: Dict[str, OrderEvent] = {}
        self.pending_orders: Dict[str, OrderEvent] = {}
        self.market_data: Dict[str, pd.DataFrame] = {}
        self.current_bars: Dict[str, pd.Series] = {}
        self.equity_curve: List[Dict[str, Any]] = []
        self.fee_model = fee_model
        self.risk_manager = risk_manager
        
        logger.info("Initialized portfolio with $%.2f capital", initial_capital)
    
    def update_market_data(self, market_event: MarketEvent) -> None:
        """Update portfolio with new market data.
        
        Args:
            market_event: New market data event.
        """
        symbol = market_event.symbol
        self.current_bars[symbol] = market_event.data
        
        # Append to market data history
        if symbol not in self.market_data:
            self.market_data[symbol] = pd.DataFrame()
        
        bar_dict = market_event.data.to_dict()
        bar_dict["timestamp"] = market_event.timestamp
        
        self.market_data[symbol] = pd.concat([
            self.market_data[symbol],
            pd.DataFrame([bar_dict])
        ])
        
        # Update portfolio value
        self._update_positions_value()
    
    def _update_positions_value(self) -> None:
        """Update the value of all open positions."""
        unrealized_pnl = 0.0
        
        for symbol, position in self.positions.items():
            if symbol in self.current_bars:
                current_price = self.current_bars[symbol].get("close", 0)
                position_size = position["size"]
                avg_price = position["avg_price"]
                
                if position["side"] == "buy":
                    unrealized_pnl += (current_price - avg_price) * position_size
                else:
                    unrealized_pnl += (avg_price - current_price) * position_size
                
                # Update position unrealized P&L
                position["unrealized_pnl"] = unrealized_pnl
                position["current_price"] = current_price
                position["current_value"] = position_size * current_price
        
        # Update portfolio equity
        self.equity = self.current_capital + unrealized_pnl
    
    def update_fill(self, fill_event: FillEvent) -> None:
        """Update portfolio based on fill event.
        
        Args:
            fill_event: Fill event.
        """
        # Find corresponding order
        order_id = fill_event.order_id
        order = self.orders.get(order_id)
        
        if order is None:
            logger.warning("Fill for unknown order: %s", order_id)
            return
        
        symbol = fill_event.symbol
        side = fill_event.side
        quantity = fill_event.quantity
        filled_price = fill_event.filled_price
        commission = fill_event.commission
        
        # Update working capital (subtract commission)
        self.current_capital -= commission
        
        # Check if opening or closing a position
        if symbol in self.positions and (
            (side == "sell" and self.positions[symbol]["side"] == "buy") or
            (side == "buy" and self.positions[symbol]["side"] == "sell")
        ):
            # Closing (or reducing) an existing position
            self._process_position_close(fill_event)
        else:
            # Opening (or adding to) a position
            self._process_position_open(fill_event)
        
        # Remove from pending orders if exists
        if order_id in self.pending_orders:
            del self.pending_orders[order_id]
        
        # Update equity
        self._update_positions_value()
        
        # Log the fill
        logger.debug(
            "Portfolio updated after fill: %s %s %s @ %s (Commission: %s)",
            symbol,
            side,
            quantity,
            filled_price,
            commission,
        )
        
        # Add equity curve point
        self.equity_curve.append({
            "timestamp": fill_event.timestamp,
            "equity": self.equity,
            "capital": self.current_capital,
        })
    
    def _process_position_open(self, fill_event: FillEvent) -> None:
        """Process a fill event that opens or adds to a position.
        
        Args:
            fill_event: Fill event.
        """
        symbol = fill_event.symbol
        side = fill_event.side
        quantity = fill_event.quantity
        filled_price = fill_event.filled_price
        
        # Calculate position cost
        position_cost = filled_price * quantity
        
        # Update capital
        if side == "buy":
            # Buying reduces capital
            self.current_capital -= position_cost
        else:
            # Short selling increases capital (margin account)
            self.current_capital += position_cost
        
        # Update positions
        if symbol in self.positions:
            # Adding to existing position
            current_size = self.positions[symbol]["size"]
            current_avg_price = self.positions[symbol]["avg_price"]
            current_cost = current_size * current_avg_price
            
            # Calculate new average price (weighted average)
            new_size = current_size + quantity
            new_cost = current_cost + (quantity * filled_price)
            new_avg_price = new_cost / new_size if new_size > 0 else 0
            
            # Update position
            self.positions[symbol]["size"] = new_size
            self.positions[symbol]["avg_price"] = new_avg_price
            self.positions[symbol]["last_update"] = fill_event.timestamp
            self.positions[symbol]["avg_fill_price"] = (
                (self.positions[symbol]["avg_fill_price"] * current_size + filled_price * quantity) / 
                new_size
            )
        else:
            # Creating new position
            self.positions[symbol] = {
                "symbol": symbol,
                "side": side,
                "size": quantity,
                "avg_price": filled_price,
                "avg_fill_price": filled_price,
                "open_time": fill_event.timestamp,
                "last_update": fill_event.timestamp,
                "unrealized_pnl": 0.0,
                "realized_pnl": 0.0,
                "current_price": filled_price,
                "current_value": quantity * filled_price,
                "status": "open",
            }
    
    def _process_position_close(self, fill_event: FillEvent) -> None:
        """Process a fill event that closes or reduces a position.
        
        Args:
            fill_event: Fill event.
        """
        symbol = fill_event.symbol
        side = fill_event.side
        quantity = fill_event.quantity
        filled_price = fill_event.filled_price
        
        # Get current position
        position = self.positions.get(symbol)
        
        if position is None:
            logger.warning("Attempting to close non-existent position: %s", symbol)
            return
        
        # Calculate P&L
        current_side = position["side"]
        current_size = position["size"]
        avg_price = position["avg_price"]
        
        # Determine how much of the position is being closed
        close_quantity = min(quantity, current_size)
        
        # Calculate P&L
        if current_side == "buy" and side == "sell":
            # Long position being closed
            pnl = (filled_price - avg_price) * close_quantity
        elif current_side == "sell" and side == "buy":
            # Short position being closed
            pnl = (avg_price - filled_price) * close_quantity
        else:
            # Should never happen (adding to position instead of closing)
            logger.warning("Inconsistent sides in position close: %s vs %s", current_side, side)
            return
        
        # Update capital with proceeds and P&L
        if side == "sell":
            # Selling returns capital
            self.current_capital += filled_price * close_quantity
        else:
            # Buying to cover a short position costs capital
            self.current_capital -= filled_price * close_quantity
        
        # Update realized P&L
        position["realized_pnl"] += pnl
        
        # Update position size
        new_size = current_size - close_quantity
        
        if new_size <= 0:
            # Position is fully closed
            position["size"] = 0
            position["status"] = "closed"
            position["close_time"] = fill_event.timestamp
            position["close_price"] = filled_price
            
            # Move to closed positions
            closed_position = position.copy()
            self.closed_positions.append(closed_position)
            
            # Remove from open positions
            del self.positions[symbol]
            
            logger.debug(
                "Closed %s position for %s: P&L = %.2f",
                current_side,
                symbol,
                pnl,
            )
        else:
            # Position is partially closed
            position["size"] = new_size
            position["last_update"] = fill_event.timestamp
            
            logger.debug(
                "Partially closed %s position for %s: %s -> %s, P&L = %.2f",
                current_side,
                symbol,
                current_size,
                new_size,
                pnl,
            )
    
    def create_order(
        self,
        signal_event: SignalEvent,
    ) -> Optional[OrderEvent]:
        """Create an order based on a signal event.
        
        Args:
            signal_event: Signal event.
            
        Returns:
            Order event if created, None otherwise.
        """
        symbol = signal_event.symbol
        signal_type = signal_event.signal_type
        signal_data = signal_event.signal_data
        
        # Generate unique order ID
        order_id = f"order-{uuid.uuid4()}"
        
        # Process different signal types
        if signal_type == "entry":
            order = self._create_entry_order(order_id, signal_event)
        elif signal_type == "exit":
            order = self._create_exit_order(order_id, signal_event)
        elif signal_type == "adjust":
            order = self._create_adjust_order(order_id, signal_event)
        else:
            logger.warning("Unknown signal type: %s", signal_type)
            return None
        
        if order:
            # Apply risk management if available
            if self.risk_manager:
                order = self.risk_manager.process_order(order, self)
            
            # Save the order
            self.orders[order_id] = order
            self.pending_orders[order_id] = order
            
            logger.debug(
                "Created order %s: %s %s %s %s @ %s",
                order_id,
                symbol,
                signal_type,
                order.order_type,
                order.side,
                order.price or order.stop_price or "MARKET",
            )
        
        return order
    
    def _create_entry_order(
        self,
        order_id: str,
        signal_event: SignalEvent,
    ) -> Optional[OrderEvent]:
        """Create an entry order based on a signal event.
        
        Args:
            order_id: Order ID.
            signal_event: Signal event.
            
        Returns:
            Order event if created, None otherwise.
        """
        symbol = signal_event.symbol
        signal_data = signal_event.signal_data
        
        # Check if we already have a position in this symbol
        if symbol in self.positions:
            logger.debug("Position already exists for %s, skipping entry", symbol)
            return None
        
        # Extract signal data
        side = signal_data.get("side", "buy")
        order_type = signal_data.get("order_type", "market")
        price = signal_data.get("price")
        stop_price = signal_data.get("stop_price")
        limit_price = signal_data.get("limit_price")
        time_in_force = signal_data.get("time_in_force", "GTC")
        
        # Calculate position size
        quantity = self._calculate_position_size(signal_event)
        
        if quantity <= 0:
            logger.warning("Invalid position size: %s", quantity)
            return None
        
        # Create order event
        order = OrderEvent(
            timestamp=signal_event.timestamp,
            order_id=order_id,
            symbol=symbol,
            order_type=order_type,
            side=side,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            limit_price=limit_price,
            time_in_force=time_in_force,
            signal_id=str(id(signal_event)),
            additional_params=signal_data.get("additional_params", {}),
        )
        
        return order
    
    def _create_exit_order(
        self,
        order_id: str,
        signal_event: SignalEvent,
    ) -> Optional[OrderEvent]:
        """Create an exit order based on a signal event.
        
        Args:
            order_id: Order ID.
            signal_event: Signal event.
            
        Returns:
            Order event if created, None otherwise.
        """
        symbol = signal_event.symbol
        signal_data = signal_event.signal_data
        
        # Check if we have a position to exit
        if symbol not in self.positions:
            logger.debug("No position for %s, skipping exit", symbol)
            return None
        
        # Extract signal data
        order_type = signal_data.get("order_type", "market")
        price = signal_data.get("price")
        stop_price = signal_data.get("stop_price")
        limit_price = signal_data.get("limit_price")
        time_in_force = signal_data.get("time_in_force", "GTC")
        quantity = signal_data.get("quantity", self.positions[symbol]["size"])
        
        # Determine side (opposite of current position)
        current_side = self.positions[symbol]["side"]
        exit_side = "sell" if current_side == "buy" else "buy"
        
        # Create order event
        order = OrderEvent(
            timestamp=signal_event.timestamp,
            order_id=order_id,
            symbol=symbol,
            order_type=order_type,
            side=exit_side,
            quantity=min(quantity, self.positions[symbol]["size"]),
            price=price,
            stop_price=stop_price,
            limit_price=limit_price,
            time_in_force=time_in_force,
            signal_id=str(id(signal_event)),
            additional_params=signal_data.get("additional_params", {}),
        )
        
        return order
    
    def _create_adjust_order(
        self,
        order_id: str,
        signal_event: SignalEvent,
    ) -> Optional[OrderEvent]:
        """Create an order to adjust an existing position.
        
        Args:
            order_id: Order ID.
            signal_event: Signal event.
            
        Returns:
            Order event if created, None otherwise.
        """
        symbol = signal_event.symbol
        signal_data = signal_event.signal_data
        
        # Check if we have a position to adjust
        if symbol not in self.positions:
            logger.debug("No position for %s, skipping adjustment", symbol)
            return None
        
        # Extract signal data
        order_type = signal_data.get("order_type", "market")
        price = signal_data.get("price")
        stop_price = signal_data.get("stop_price")
        limit_price = signal_data.get("limit_price")
        time_in_force = signal_data.get("time_in_force", "GTC")
        
        # Determine adjustment direction
        current_side = self.positions[symbol]["side"]
        current_size = self.positions[symbol]["size"]
        action = signal_data.get("action", "increase")
        
        if action == "increase":
            # Adding to existing position
            side = current_side
            adjustment_pct = signal_data.get("adjustment_pct", 0.5)
            quantity = current_size * adjustment_pct
        elif action == "decrease":
            # Reducing existing position
            side = "sell" if current_side == "buy" else "buy"
            adjustment_pct = signal_data.get("adjustment_pct", 0.5)
            quantity = current_size * adjustment_pct
        else:
            logger.warning("Unknown adjustment action: %s", action)
            return None
        
        # Create order event
        order = OrderEvent(
            timestamp=signal_event.timestamp,
            order_id=order_id,
            symbol=symbol,
            order_type=order_type,
            side=side,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            limit_price=limit_price,
            time_in_force=time_in_force,
            signal_id=str(id(signal_event)),
            additional_params=signal_data.get("additional_params", {}),
        )
        
        return order
    
    def _calculate_position_size(self, signal_event: SignalEvent) -> float:
        """Calculate position size based on risk parameters.
        
        Args:
            signal_event: Signal event.
            
        Returns:
            Position size.
        """
        symbol = signal_event.symbol
        signal_data = signal_event.signal_data
        
        # Extract risk parameters
        risk_pct = signal_data.get("risk_pct", 0.02)
        stop_loss = signal_data.get("stop_loss")
        position_sizing_method = signal_data.get("position_sizing", "risk_pct")
        
        # Set current price from market data
        if symbol in self.current_bars:
            current_price = self.current_bars[symbol].get("close", 0)
        else:
            logger.warning("No current price data for %s", symbol)
            return 0
        
        # Calculate position size based on chosen method
        if position_sizing_method == "fixed_amount":
            # Fixed amount of capital
            fixed_amount = signal_data.get("fixed_amount", self.equity * 0.1)
            return fixed_amount / current_price
        
        elif position_sizing_method == "fixed_risk":
            # Fixed amount at risk
            risk_amount = signal_data.get("risk_amount", self.equity * risk_pct)
            
            if stop_loss is None:
                # Default to 2% risk if no stop loss
                price_risk = current_price * 0.02
            else:
                # Use specified stop loss
                price_risk = abs(current_price - stop_loss)
            
            return risk_amount / price_risk if price_risk > 0 else 0
        
        elif position_sizing_method == "percent_equity":
            # Percentage of equity
            equity_pct = signal_data.get("equity_pct", 0.1)
            return (self.equity * equity_pct) / current_price
        
        elif position_sizing_method == "fixed_quantity":
            # Fixed quantity
            return signal_data.get("quantity", 1)
        
        elif position_sizing_method == "risk_pct":
            # Risk percentage of equity
            risk_amount = self.equity * risk_pct
            
            if stop_loss is None:
                # Default to 2% risk if no stop loss
                price_risk = current_price * 0.02
            else:
                # Use specified stop loss
                price_risk = abs(current_price - stop_loss)
            
            return risk_amount / price_risk if price_risk > 0 else 0
        
        else:
            logger.warning("Unknown position sizing method: %s", position_sizing_method)
            return 0
    
    def get_current_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get current open positions.
        
        Returns:
            Dictionary of open positions.
        """
        return self.positions
    
    def get_closed_positions(self) -> List[Dict[str, Any]]:
        """Get closed positions.
        
        Returns:
            List of closed positions.
        """
        return self.closed_positions
    
    def get_equity_curve(self) -> pd.DataFrame:
        """Get equity curve as a DataFrame.
        
        Returns:
            Equity curve DataFrame.
        """
        return pd.DataFrame(self.equity_curve)
    
    def calculate_metrics(self) -> Dict[str, float]:
        """Calculate portfolio performance metrics.
        
        Returns:
            Dictionary of performance metrics.
        """
        metrics = {}
        
        # Basic metrics
        metrics["initial_capital"] = self.initial_capital
        metrics["final_capital"] = self.current_capital
        metrics["final_equity"] = self.equity
        
        # Return metrics
        total_return = self.equity - self.initial_capital
        metrics["total_return"] = total_return
        metrics["return_pct"] = (total_return / self.initial_capital) * 100
        
        # Trade metrics
        win_count = sum(1 for p in self.closed_positions if p["realized_pnl"] > 0)
        loss_count = sum(1 for p in self.closed_positions if p["realized_pnl"] <= 0)
        total_trades = win_count + loss_count
        
        metrics["total_trades"] = total_trades
        metrics["win_count"] = win_count
        metrics["loss_count"] = loss_count
        metrics["win_rate"] = win_count / total_trades if total_trades > 0 else 0
        
        # P&L metrics
        total_profit = sum(p["realized_pnl"] for p in self.closed_positions if p["realized_pnl"] > 0)
        total_loss = sum(p["realized_pnl"] for p in self.closed_positions if p["realized_pnl"] <= 0)
        
        metrics["total_profit"] = total_profit
        metrics["total_loss"] = total_loss
        metrics["profit_factor"] = abs(total_profit / total_loss) if total_loss != 0 else float("inf")
        metrics["average_profit"] = total_profit / win_count if win_count > 0 else 0
        metrics["average_loss"] = total_loss / loss_count if loss_count > 0 else 0
        metrics["average_trade"] = (total_profit + total_loss) / total_trades if total_trades > 0 else 0
        
        # Calculate max drawdown if we have equity data
        if self.equity_curve:
            equity_df = pd.DataFrame(self.equity_curve)
            equity_df["peak"] = equity_df["equity"].cummax()
            equity_df["drawdown"] = (equity_df["equity"] - equity_df["peak"]) / equity_df["peak"]
            max_drawdown = equity_df["drawdown"].min()
            metrics["max_drawdown"] = max_drawdown
            metrics["max_drawdown_pct"] = max_drawdown * 100
        
        return metrics
    
    def reset(self) -> None:
        """Reset the portfolio to initial state."""
        self.current_capital = self.initial_capital
        self.equity = self.initial_capital
        self.positions.clear()
        self.closed_positions.clear()
        self.orders.clear()
        self.pending_orders.clear()
        self.market_data.clear()
        self.current_bars.clear()
        self.equity_curve.clear()
        
        logger.debug("Reset portfolio state")


class EventQueue:
    """Queue for processing events in event-driven backtesting."""
    
    def __init__(self, max_size: int = 10000):
        """Initialize the event queue.
        
        Args:
            max_size: Maximum size of the queue.
        """
        self.queue: deque = deque(maxlen=max_size)
        self.event_counter: Dict[EventType, int] = {
            event_type: 0 for event_type in EventType
        }
    
    def put(self, event: EventUnion) -> None:
        """Add an event to the queue.
        
        Args:
            event: Event to add.
        """
        self.queue.append(event)
        self.event_counter[event.type] += 1
    
    def get(self) -> Optional[EventUnion]:
        """Get the next event from the queue.
        
        Returns:
            Next event if available, None otherwise.
        """
        if not self.queue:
            return None
        
        return self.queue.popleft()
    
    def peek(self) -> Optional[EventUnion]:
        """Peek at the next event without removing it.
        
        Returns:
            Next event if available, None otherwise.
        """
        if not self.queue:
            return None
        
        return self.queue[0]
    
    def is_empty(self) -> bool:
        """Check if the queue is empty.
        
        Returns:
            True if the queue is empty, False otherwise.
        """
        return len(self.queue) == 0
    
    def size(self) -> int:
        """Get the current size of the queue.
        
        Returns:
            Current size of the queue.
        """
        return len(self.queue)
    
    def clear(self) -> None:
        """Clear the queue."""
        self.queue.clear()
        for event_type in self.event_counter:
            self.event_counter[event_type] = 0
    
    def get_stats(self) -> Dict[str, int]:
        """Get queue statistics.
        
        Returns:
            Dictionary of queue statistics.
        """
        return {
            "current_size": len(self.queue),
            "events_processed": {
                event_type.name: count
                for event_type, count in self.event_counter.items()
            }
        }


class EventDrivenEngine:
    """Event-driven backtesting engine."""
    
    def __init__(
        self,
        data_handler: Optional[Callable] = None,
        strategy: Optional[Callable] = None,
        portfolio: Optional[Portfolio] = None,
        execution_handler: Optional[ExecutionHandler] = None,
        initial_capital: float = 10000.0,
        fee_model: Optional[str] = None,
    ):
        """Initialize the event-driven backtesting engine.
        
        Args:
            data_handler: Data handler function.
            strategy: Strategy function.
            portfolio: Portfolio instance.
            execution_handler: Execution handler instance.
            initial_capital: Initial capital.
            fee_model: Fee model to use.
        """
        self.event_queue = EventQueue()
        
        # Initialize components
        self.portfolio = portfolio or Portfolio(
            initial_capital=initial_capital,
            fee_model=fee_model,
        )
        self.execution_handler = execution_handler or ExecutionHandler()
        
        # Set strategy function
        self.strategy = strategy
        
        # Set data handler function
        self.data_handler = data_handler
        
        # Backtest state
        self.current_timestamp: Optional[datetime] = None
        self.start_timestamp: Optional[datetime] = None
        self.end_timestamp: Optional[datetime] = None
        self.symbols: Set[str] = set()
        self.is_running: bool = False
        self.performance_metrics: Dict[str, Any] = {}
        
        logger.info("Initialized event-driven backtesting engine")
    
    def load_data(
        self,
        data: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
        date_col: str = "time",
    ) -> None:
        """Load data for backtesting.
        
        Args:
            data: Price data, either a single DataFrame or a dict of DataFrames by symbol.
            date_col: Date/time column name.
        """
        # Handle single DataFrame or dict of DataFrames
        if isinstance(data, pd.DataFrame):
            # Single DataFrame, should have a 'symbol' column
            if "symbol" not in data.columns:
                raise ValueError("DataFrame must have a 'symbol' column")
            
            # Convert to dict of DataFrames
            data_dict = {}
            for symbol, group in data.groupby("symbol"):
                data_dict[symbol] = group.copy()
        else:
            # Dict of DataFrames by symbol
            data_dict = data
        
        # Register symbols
        self.symbols = set(data_dict.keys())
        
        # Determine overall date range
        start_dates = []
        end_dates = []
        
        for symbol, df in data_dict.items():
            # Ensure data is sorted by date
            if date_col in df.columns:
                df = df.sort_values(date_col)
                start_dates.append(df[date_col].iloc[0])
                end_dates.append(df[date_col].iloc[-1])
        
        # Set overall date range
        if start_dates and end_dates:
            self.start_timestamp = min(start_dates)
            self.end_timestamp = max(end_dates)
        
        # Generate market events from data
        self._generate_market_events(data_dict, date_col)
        
        logger.info(
            "Loaded data for %d symbols from %s to %s (%d events)",
            len(self.symbols),
            self.start_timestamp,
            self.end_timestamp,
            self.event_queue.size(),
        )
    
    def _generate_market_events(
        self,
        data_dict: Dict[str, pd.DataFrame],
        date_col: str = "time",
    ) -> None:
        """Generate market events from data.
        
        Args:
            data_dict: Dict of DataFrames by symbol.
            date_col: Date/time column name.
        """
        # Create a sorted list of all timestamps
        all_timestamps = []
        
        for symbol, df in data_dict.items():
            if date_col in df.columns:
                timestamps = df[date_col].tolist()
                all_timestamps.extend([(ts, symbol, i) for i, ts in enumerate(timestamps)])
        
        # Sort by timestamp
        all_timestamps.sort()
        
        # Generate market events
        for timestamp, symbol, idx in all_timestamps:
            df = data_dict[symbol]
            bar = df.iloc[idx]
            
            # Create market event
            event = MarketEvent(
                timestamp=timestamp,
                symbol=symbol,
                timeframe="unknown",  # Could extract from df metadata
                data=bar,
            )
            
            # Add to queue
            self.event_queue.put(event)
    
    def run(self) -> BacktestResult:
        """Run the backtest.
        
        Returns:
            Backtest results.
        """
        if not self.strategy:
            raise ValueError("Strategy function not specified")
        
        if self.event_queue.is_empty():
            raise ValueError("No data loaded")
        
        # Reset backtest state
        self.is_running = True
        self.portfolio.reset()
        self.execution_handler.clear()
        
        # Start backtest
        start_time = time.time()
        logger.info("Starting backtest with %d events", self.event_queue.size())
        
        # Process events
        while not self.event_queue.is_empty() and self.is_running:
            event = self.event_queue.get()
            
            if event is None:
                continue
            
            # Update current timestamp
            self.current_timestamp = event.timestamp
            
            # Process event based on type
            if event.type == EventType.MARKET:
                self._process_market_event(event)
            elif event.type == EventType.SIGNAL:
                self._process_signal_event(event)
            elif event.type == EventType.ORDER:
                self._process_order_event(event)
            elif event.type == EventType.FILL:
                self._process_fill_event(event)
            elif event.type == EventType.CUSTOM:
                self._process_custom_event(event)
        
        # Calculate performance metrics
        self.performance_metrics = self._calculate_performance()
        
        # Log backtest completion
        elapsed = time.time() - start_time
        logger.info(
            "Backtest completed in %.2f seconds. Final equity: $%.2f",
            elapsed,
            self.portfolio.equity,
        )
        
        # Convert positions to trade format for advanced metrics
        trades_list = []
        for pos in self.portfolio.get_closed_positions():
            trades_list.append({
                'entry_time': pos['open_time'],
                'exit_time': pos.get('close_time'),
                'symbol': pos['symbol'],
                'side': pos['side'],
                'pnl': pos.get('realized_pnl', 0),
                'entry_price': pos['avg_price'],
                'exit_price': pos.get('close_price', 0),
                'quantity': pos['size'],
                'commission': pos.get('commission', 0),
                'slippage': pos.get('slippage', 0),
                'metadata': pos.get('metadata', {}),
            })
            
        # Advanced metrics calculation using PerformanceAnalyzer if available
        advanced_metrics = None
        drawdown_analysis = None
        risk_analysis = None
        monte_carlo_results = None
        
        try:
            from fxml4.backtesting.performance_metrics import PerformanceAnalyzer
            
            # Get equity curve for analysis
            equity_df = self.portfolio.get_equity_curve()
            
            # Initialize performance analyzer
            analyzer = PerformanceAnalyzer(
                risk_free_rate=0.02,
                annualization_factor=252,
            )
            
            # Calculate comprehensive metrics
            metrics_obj = analyzer.calculate_metrics(
                equity_curve=equity_df,
                trades=trades_list,
                include_benchmark=False,
            )
            
            # Store the metrics object
            advanced_metrics = metrics_obj
            
            # Analyze drawdowns
            drawdown_analysis = analyzer.analyze_drawdowns(
                equity_df,
                min_drawdown_pct=0.01,
                top_n=5,
            )
            
            # Analyze risk contribution
            risk_analysis = analyzer.risk_contribution_analysis(trades_list)
            
            # Run Monte Carlo simulation
            if len(trades_list) >= 20:
                monte_carlo_results = analyzer.create_monte_carlo_simulation(
                    trades=trades_list,
                    initial_capital=self.portfolio.initial_capital,
                    num_simulations=500,
                )
                
            # Use advanced metrics if available
            if hasattr(metrics_obj, 'sharpe_ratio'):
                self.performance_metrics['sharpe_ratio'] = metrics_obj.sharpe_ratio
            if hasattr(metrics_obj, 'sortino_ratio'):
                self.performance_metrics['sortino_ratio'] = metrics_obj.sortino_ratio
            if hasattr(metrics_obj, 'max_drawdown_pct'):
                self.performance_metrics['max_drawdown_pct'] = metrics_obj.max_drawdown_pct
            if hasattr(metrics_obj, 'win_rate'):
                self.performance_metrics['win_rate'] = metrics_obj.win_rate
            if hasattr(metrics_obj, 'profit_factor'):
                self.performance_metrics['profit_factor'] = metrics_obj.profit_factor
            if hasattr(metrics_obj, 'annualized_return'):
                self.performance_metrics['annualized_return'] = metrics_obj.annualized_return
                
        except ImportError:
            logger.debug("PerformanceAnalyzer not available, using basic metrics only")
        
        # Create result object
        result = BacktestResult(
            strategy_name=self.strategy.__name__ if hasattr(self.strategy, "__name__") else "Unknown",
            symbol=", ".join(self.symbols),
            timeframe="unknown",  # Could extract from data
            start_date=self.start_timestamp or datetime.now(),
            end_date=self.end_timestamp or datetime.now(),
            initial_capital=self.portfolio.initial_capital,
            final_capital=self.portfolio.equity,
            total_return=self.performance_metrics.get("total_return", 0),
            total_return_pct=self.performance_metrics.get("return_pct", 0),
            annualized_return=self.performance_metrics.get("annualized_return", 0),
            max_drawdown=self.performance_metrics.get("max_drawdown", 0),
            max_drawdown_pct=self.performance_metrics.get("max_drawdown_pct", 0),
            sharpe_ratio=self.performance_metrics.get("sharpe_ratio", 0),
            sortino_ratio=self.performance_metrics.get("sortino_ratio", 0),
            win_rate=self.performance_metrics.get("win_rate", 0),
            profit_factor=self.performance_metrics.get("profit_factor", 0),
            avg_profit_per_trade=self.performance_metrics.get("average_profit", 0),
            avg_loss_per_trade=self.performance_metrics.get("average_loss", 0),
            trades=self._convert_positions_to_trades(),
            equity_curve=self.portfolio.get_equity_curve(),
            performance_metrics=advanced_metrics,
            drawdown_analysis=drawdown_analysis,
            risk_analysis=risk_analysis,
            monte_carlo_results=monte_carlo_results,
        )
        
        # Auto-generate performance report if enabled in configuration
        from fxml4.config import get_config
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
        
        self.is_running = False
        return result
    
    def _process_market_event(self, event: MarketEvent) -> None:
        """Process a market event.
        
        Args:
            event: Market event.
        """
        # Update portfolio with new market data
        self.portfolio.update_market_data(event)
        
        # Process any pending orders with new bar
        fills = self.execution_handler.process_bar(
            event.data,
            self.portfolio.market_data.get(event.symbol),
        )
        
        # Add fill events to queue
        for fill in fills:
            self.event_queue.put(fill)
        
        # Generate strategy signals
        if self.strategy:
            signals = self.strategy(
                event.symbol,
                event.data,
                self.portfolio.market_data.get(event.symbol),
                self.portfolio,
            )
            
            # Add signal events to queue
            if signals:
                for signal_type, signal_data in signals.items():
                    signal = SignalEvent(
                        timestamp=event.timestamp,
                        symbol=event.symbol,
                        signal_type=signal_type,
                        signal_data=signal_data,
                    )
                    self.event_queue.put(signal)
    
    def _process_signal_event(self, event: SignalEvent) -> None:
        """Process a signal event.
        
        Args:
            event: Signal event.
        """
        # Generate order from signal
        order = self.portfolio.create_order(event)
        
        # Add order event to queue
        if order:
            self.event_queue.put(order)
    
    def _process_order_event(self, event: OrderEvent) -> None:
        """Process an order event.
        
        Args:
            event: Order event.
        """
        # Process order with execution handler
        fill = self.execution_handler.process_order(
            event,
            self.portfolio.current_bars.get(event.symbol, pd.Series()),
            self.portfolio.market_data.get(event.symbol),
        )
        
        # Add fill event to queue if executed immediately
        if fill:
            self.event_queue.put(fill)
    
    def _process_fill_event(self, event: FillEvent) -> None:
        """Process a fill event.
        
        Args:
            event: Fill event.
        """
        # Update portfolio with fill
        self.portfolio.update_fill(event)
    
    def _process_custom_event(self, event: Event) -> None:
        """Process a custom event.
        
        Args:
            event: Custom event.
        """
        # Custom events can be handled by extensions
        logger.debug("Processed custom event: %s", event)
    
    def _calculate_performance(self) -> Dict[str, Any]:
        """Calculate performance metrics for the backtest.
        
        Returns:
            Dictionary of performance metrics.
        """
        # Get basic metrics from portfolio
        metrics = self.portfolio.calculate_metrics()
        
        # Get equity curve for additional metrics
        equity_df = self.portfolio.get_equity_curve()
        
        # Calculate additional metrics
        if not equity_df.empty and len(equity_df) > 1:
            # Calculate daily returns
            equity_df["date"] = pd.to_datetime(equity_df["timestamp"]).dt.date
            daily_equity = equity_df.groupby("date")["equity"].last().reset_index()
            daily_equity["return"] = daily_equity["equity"].pct_change()
            
            # Calculate Sharpe ratio (annualized)
            if len(daily_equity) > 1:
                returns = daily_equity["return"].dropna()
                sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0
                metrics["sharpe_ratio"] = sharpe_ratio
                
                # Calculate Sortino ratio (annualized)
                downside_returns = returns[returns < 0]
                sortino_ratio = (returns.mean() / downside_returns.std()) * np.sqrt(252) if len(downside_returns) > 0 and downside_returns.std() > 0 else 0
                metrics["sortino_ratio"] = sortino_ratio
                
                # Calculate annualized return
                total_days = (
                    daily_equity["date"].iloc[-1] - daily_equity["date"].iloc[0]
                ).days
                years = total_days / 365
                annualized_return = (
                    (1 + metrics["return_pct"] / 100) ** (1 / years) - 1
                ) * 100 if years > 0 else 0
                metrics["annualized_return"] = annualized_return
                
                # Maximum consecutive wins/losses
                trades = self.portfolio.get_closed_positions()
                if trades:
                    trades_df = pd.DataFrame(trades)
                    if not trades_df.empty and "realized_pnl" in trades_df.columns:
                        trades_df["is_win"] = trades_df["realized_pnl"] > 0
                        
                        # Use a rolling sum to identify streaks
                        trades_df["streak"] = (trades_df["is_win"] != trades_df["is_win"].shift()).cumsum()
                        streaks = trades_df.groupby(["is_win", "streak"]).size().reset_index(name="count")
                        
                        # Get maximum win and loss streaks
                        max_win_streak = streaks[streaks["is_win"]]["count"].max() if not streaks[streaks["is_win"]].empty else 0
                        max_loss_streak = streaks[~streaks["is_win"]]["count"].max() if not streaks[~streaks["is_win"]].empty else 0
                        
                        metrics["max_win_streak"] = max_win_streak
                        metrics["max_loss_streak"] = max_loss_streak
        
        return metrics
    
    def _convert_positions_to_trades(self) -> List[Any]:
        """Convert closed positions to trade list.
        
        Returns:
            List of trades.
        """
        from fxml4.backtesting.backtest_engine import OrderSide, Position, PositionStatus
        
        trades = []
        
        for pos in self.portfolio.get_closed_positions():
            # Convert to Position object
            side = OrderSide.BUY if pos["side"] == "buy" else OrderSide.SELL
            
            trade = Position(
                position_id=str(pos.get("id", len(trades) + 1)),
                symbol=pos["symbol"],
                side=side,
                entry_price=pos["avg_price"],
                entry_timestamp=pos["open_time"],
                quantity=pos["size"],
                status=PositionStatus.CLOSED,
                exit_price=pos.get("close_price", 0),
                exit_timestamp=pos.get("close_time"),
                pnl=pos.get("realized_pnl", 0),
                pnl_pct=(pos.get("realized_pnl", 0) / (pos["avg_price"] * pos["size"])) * 100 if pos["avg_price"] and pos["size"] else 0,
            )
            
            trades.append(trade)
        
        return trades
    
    def stop(self) -> None:
        """Stop the backtest execution."""
        self.is_running = False
        logger.info("Backtest stopped by user")
    
    def get_results(self) -> Dict[str, Any]:
        """Get backtest results.
        
        Returns:
            Dictionary of backtest results.
        """
        return {
            "metrics": self.performance_metrics,
            "equity_curve": self.portfolio.get_equity_curve(),
            "trades": self.portfolio.get_closed_positions(),
            "event_stats": self.event_queue.get_stats(),
        }


def run_event_driven_backtest(
    strategy: Callable,
    data: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
    initial_capital: float = 10000.0,
    fee_model: Optional[str] = None,
    slippage_model: Optional[SlippageModel] = None,
    date_col: str = "time",
) -> BacktestResult:
    """Run an event-driven backtest.
    
    Args:
        strategy: Strategy function.
        data: Price data.
        initial_capital: Initial capital.
        fee_model: Fee model name.
        slippage_model: Slippage model instance.
        date_col: Date/time column name.
        
    Returns:
        Backtest results.
    """
    # Initialize components
    portfolio = Portfolio(initial_capital=initial_capital, fee_model=fee_model)
    execution_handler = ExecutionHandler(slippage_model=slippage_model)
    
    # Initialize engine
    engine = EventDrivenEngine(
        strategy=strategy,
        portfolio=portfolio,
        execution_handler=execution_handler,
    )
    
    # Load data
    engine.load_data(data, date_col=date_col)
    
    # Run backtest
    results = engine.run()
    
    return results