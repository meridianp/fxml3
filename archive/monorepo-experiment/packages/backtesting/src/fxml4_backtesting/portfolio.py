"""
Portfolio management for backtesting.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List, Optional
from queue import Queue
import pandas as pd
import numpy as np
import uuid

from fxml4_core.logging import get_logger
from fxml4_backtesting.events import (
    Event, MarketEvent, SignalEvent, OrderEvent, 
    FillEvent, OrderType, OrderSide, EventType
)

logger = get_logger(__name__)


@dataclass
class Position:
    """Position in a single asset."""
    symbol: str
    quantity: float
    average_price: float
    current_price: float
    opened_at: datetime
    last_updated: datetime
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    commission_paid: float = 0.0
    
    @property
    def market_value(self) -> float:
        """Current market value of position."""
        return self.quantity * self.current_price
    
    @property
    def cost_basis(self) -> float:
        """Total cost basis of position."""
        return self.quantity * self.average_price
    
    def update_price(self, price: float) -> None:
        """Update current price and unrealized P&L."""
        self.current_price = price
        self.unrealized_pnl = (price - self.average_price) * self.quantity
        self.last_updated = datetime.now()


class Portfolio:
    """Portfolio for tracking positions and generating orders."""
    
    def __init__(
        self,
        initial_capital: float,
        events_queue: Queue,
        data_handler: Any,
        risk_manager: Optional[Any] = None
    ):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.events_queue = events_queue
        self.data_handler = data_handler
        self.risk_manager = risk_manager
        
        # Positions
        self.positions: Dict[str, Position] = {}
        self.closed_positions: List[Dict[str, Any]] = []
        
        # Orders
        self.pending_orders: Dict[str, OrderEvent] = {}
        self.order_history: List[OrderEvent] = []
        
        # Performance tracking
        self.equity_curve: List[Dict[str, Any]] = []
        self.current_holdings: Dict[str, float] = {}
        
        # Initialize equity curve
        self._update_equity_curve()
        
        logger.info("Portfolio initialized with capital: %.2f", initial_capital)
    
    @property
    def equity(self) -> float:
        """Total equity (cash + positions)."""
        positions_value = sum(pos.market_value for pos in self.positions.values())
        return self.current_capital + positions_value
    
    @property
    def cash(self) -> float:
        """Available cash."""
        return self.current_capital
    
    @property
    def margin_used(self) -> float:
        """Margin used by positions."""
        # Simple calculation - can be enhanced
        return sum(abs(pos.market_value) for pos in self.positions.values())
    
    def update_market_data(self, event: MarketEvent) -> None:
        """Update portfolio with new market data."""
        symbol = event.symbol
        price = event.data.get('close', 0)
        
        # Update position if exists
        if symbol in self.positions:
            self.positions[symbol].update_price(price)
        
        # Update current holdings
        self.current_holdings[symbol] = price
        
        # Update equity curve
        self._update_equity_curve()
    
    def update_signal(self, event: SignalEvent) -> None:
        """Generate orders from signal."""
        # Apply risk management
        if self.risk_manager:
            if not self.risk_manager.validate_signal(event, self):
                logger.debug("Signal rejected by risk manager")
                return
        
        # Generate order
        order = self._create_order_from_signal(event)
        
        if order:
            # Add to pending orders
            self.pending_orders[order.order_id] = order
            self.order_history.append(order)
            
            # Put order in events queue
            self.events_queue.put(order)
            
            logger.info(
                "Generated %s order for %s: %.4f @ %.5f",
                order.side.value,
                order.symbol,
                order.quantity,
                order.price or 0
            )
    
    def update_fill(self, event: FillEvent) -> None:
        """Update portfolio with fill event."""
        symbol = event.symbol
        quantity = event.quantity
        price = event.price
        commission = event.commission
        
        # Update cash
        if event.side == OrderSide.BUY:
            cost = quantity * price + commission
            self.current_capital -= cost
        else:
            proceeds = quantity * price - commission
            self.current_capital += proceeds
        
        # Update or create position
        if symbol not in self.positions:
            if event.side == OrderSide.BUY:
                self.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=quantity,
                    average_price=price,
                    current_price=price,
                    opened_at=event.timestamp,
                    last_updated=event.timestamp,
                    commission_paid=commission
                )
            # If selling without position, log error
            else:
                logger.error("Attempting to sell %s without position", symbol)
                return
        else:
            position = self.positions[symbol]
            
            if event.side == OrderSide.BUY:
                # Average up
                total_cost = position.cost_basis + (quantity * price)
                position.quantity += quantity
                position.average_price = total_cost / position.quantity
                position.commission_paid += commission
            else:
                # Reduce or close position
                if quantity >= position.quantity:
                    # Close position
                    realized_pnl = (price - position.average_price) * position.quantity
                    position.realized_pnl += realized_pnl
                    
                    # Record closed position
                    self.closed_positions.append({
                        'symbol': symbol,
                        'entry_price': position.average_price,
                        'exit_price': price,
                        'quantity': position.quantity,
                        'realized_pnl': realized_pnl - position.commission_paid - commission,
                        'opened_at': position.opened_at,
                        'closed_at': event.timestamp,
                        'commission': position.commission_paid + commission
                    })
                    
                    # Remove position
                    del self.positions[symbol]
                else:
                    # Partial close
                    realized_pnl = (price - position.average_price) * quantity
                    position.realized_pnl += realized_pnl
                    position.quantity -= quantity
                    position.commission_paid += commission
        
        # Remove from pending orders
        if event.order_id in self.pending_orders:
            del self.pending_orders[event.order_id]
        
        # Update equity curve
        self._update_equity_curve()
        
        logger.info(
            "Fill executed - %s %s: %.4f @ %.5f (commission: %.2f)",
            event.side.value,
            symbol,
            quantity,
            price,
            commission
        )
    
    def _create_order_from_signal(self, signal: SignalEvent) -> Optional[OrderEvent]:
        """Create order from signal."""
        symbol = signal.symbol
        
        # Determine order side
        if signal.signal_type == 'BUY':
            side = OrderSide.BUY
        elif signal.signal_type == 'SELL':
            side = OrderSide.SELL
        else:
            logger.warning("Unknown signal type: %s", signal.signal_type)
            return None
        
        # Calculate quantity
        quantity = self._calculate_position_size(signal)
        
        if quantity <= 0:
            logger.debug("Zero quantity calculated for signal")
            return None
        
        # Create order
        order = OrderEvent(
            type=EventType.ORDER,
            timestamp=datetime.now(),
            symbol=symbol,
            order_type=OrderType.MARKET,
            side=side,
            quantity=quantity,
            price=signal.price if signal.price else None,
            order_id=str(uuid.uuid4()),
            metadata={
                'signal_strength': signal.strength,
                'signal_metadata': signal.metadata
            }
        )
        
        return order
    
    def _calculate_position_size(self, signal: SignalEvent) -> float:
        """Calculate position size for signal."""
        # Simple fixed fractional position sizing
        if signal.quantity:
            return signal.quantity
        
        # Use 2% of equity per trade as default
        risk_per_trade = 0.02
        position_value = self.equity * risk_per_trade
        
        # Get current price
        current_price = signal.price
        if not current_price and signal.symbol in self.current_holdings:
            current_price = self.current_holdings[signal.symbol]
        
        if not current_price or current_price <= 0:
            return 0.0
        
        # Calculate quantity
        quantity = position_value / current_price
        
        # Apply signal strength
        quantity *= signal.strength
        
        return round(quantity, 4)
    
    def _update_equity_curve(self) -> None:
        """Update equity curve with current values."""
        equity_point = {
            'timestamp': datetime.now(),
            'equity': self.equity,
            'cash': self.current_capital,
            'positions_value': sum(pos.market_value for pos in self.positions.values()),
            'positions_count': len(self.positions),
            'unrealized_pnl': sum(pos.unrealized_pnl for pos in self.positions.values()),
            'margin_used': self.margin_used
        }
        
        self.equity_curve.append(equity_point)
    
    def get_current_positions(self) -> Dict[str, Position]:
        """Get current open positions."""
        return self.positions.copy()
    
    def get_position_summary(self) -> pd.DataFrame:
        """Get summary of all positions."""
        if not self.positions:
            return pd.DataFrame()
        
        data = []
        for symbol, pos in self.positions.items():
            data.append({
                'symbol': symbol,
                'quantity': pos.quantity,
                'avg_price': pos.average_price,
                'current_price': pos.current_price,
                'market_value': pos.market_value,
                'unrealized_pnl': pos.unrealized_pnl,
                'realized_pnl': pos.realized_pnl,
                'total_pnl': pos.unrealized_pnl + pos.realized_pnl
            })
        
        return pd.DataFrame(data)