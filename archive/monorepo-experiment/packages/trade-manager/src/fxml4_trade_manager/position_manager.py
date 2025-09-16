"""Position Manager - Handles position lifecycle and state management."""

from typing import Dict, Any, List, Optional, Tuple
from datetime import timedelta
from decimal import Decimal
import asyncio
import logging
from enum import Enum

from .domain import (
    OrderSide, OrderType, TimeInForce, OrderStatus,
    ITimeProvider, IPositionManager, IEventPublisher,
    IMetricsCollector, UTCTimeProvider
)

logger = logging.getLogger(__name__)


class PositionState(str, Enum):
    """Position lifecycle states."""
    PENDING = "pending"
    OPENING = "opening"
    OPEN = "open"
    SCALING_OUT = "scaling_out"
    CLOSING = "closing"
    CLOSED = "closed"
    ERROR = "error"


class Position:
    """Position object with complete state tracking."""
    
    def __init__(self, position_data: Dict[str, Any], time_provider: ITimeProvider):
        self._time_provider = time_provider
        
        # Identifiers
        self.position_id = position_data['position_id']
        self.signal_id = position_data.get('signal_id')
        self.trade_id = position_data.get('trade_id')
        
        # Position details
        self.symbol = position_data['symbol']
        self.side = OrderSide(position_data['side'])
        self.state = PositionState(position_data.get('state', PositionState.PENDING))
        
        # Quantities
        self.target_quantity = Decimal(str(position_data['target_quantity']))
        self.filled_quantity = Decimal(str(position_data.get('filled_quantity', 0)))
        self.remaining_quantity = Decimal(str(position_data.get('remaining_quantity', 0)))
        
        # Prices
        self.target_entry = Decimal(str(position_data.get('target_entry', 0)))
        self.avg_entry_price = Decimal(str(position_data.get('avg_entry_price', 0)))
        self.current_price = Decimal(str(position_data.get('current_price', 0)))
        
        # Risk management
        self.stop_loss = Decimal(str(position_data.get('stop_loss', 0)))
        self.take_profit_1 = Decimal(str(position_data.get('take_profit_1', 0)))
        self.take_profit_2 = Decimal(str(position_data.get('take_profit_2', 0)))
        self.take_profit_3 = Decimal(str(position_data.get('take_profit_3', 0)))
        
        # Trailing stop
        self.trailing_stop_active = position_data.get('trailing_stop_active', False)
        self.trailing_stop_distance = Decimal(str(position_data.get('trailing_stop_distance', 0)))
        self.highest_price = Decimal(str(position_data.get('highest_price', 0)))
        self.lowest_price = Decimal(str(position_data.get('lowest_price', 0)))
        
        # P&L tracking
        self.realized_pnl = Decimal(str(position_data.get('realized_pnl', 0)))
        self.unrealized_pnl = Decimal(str(position_data.get('unrealized_pnl', 0)))
        self.commission = Decimal(str(position_data.get('commission', 0)))
        
        # Orders
        self.entry_orders: List[str] = position_data.get('entry_orders', [])
        self.exit_orders: List[str] = position_data.get('exit_orders', [])
        self.stop_order_id = position_data.get('stop_order_id')
        self.tp_order_ids = position_data.get('tp_order_ids', {})
        
        # Timing
        self.created_at = position_data.get('created_at', self._time_provider.now())
        self.opened_at = position_data.get('opened_at')
        self.closed_at = position_data.get('closed_at')
        self.last_updated = position_data.get('last_updated', self._time_provider.now())
        
        # Metadata
        self.broker = position_data.get('broker')
        self.strategy = position_data.get('strategy')
        self.metadata = position_data.get('metadata', {})
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert position to dictionary."""
        return {
            'position_id': self.position_id,
            'signal_id': self.signal_id,
            'trade_id': self.trade_id,
            'symbol': self.symbol,
            'side': self.side.value,
            'state': self.state.value,
            'target_quantity': str(self.target_quantity),
            'filled_quantity': str(self.filled_quantity),
            'remaining_quantity': str(self.remaining_quantity),
            'target_entry': str(self.target_entry),
            'avg_entry_price': str(self.avg_entry_price),
            'current_price': str(self.current_price),
            'stop_loss': str(self.stop_loss),
            'take_profit_1': str(self.take_profit_1),
            'take_profit_2': str(self.take_profit_2),
            'take_profit_3': str(self.take_profit_3),
            'trailing_stop_active': self.trailing_stop_active,
            'trailing_stop_distance': str(self.trailing_stop_distance),
            'highest_price': str(self.highest_price),
            'lowest_price': str(self.lowest_price),
            'realized_pnl': str(self.realized_pnl),
            'unrealized_pnl': str(self.unrealized_pnl),
            'commission': str(self.commission),
            'entry_orders': self.entry_orders,
            'exit_orders': self.exit_orders,
            'stop_order_id': self.stop_order_id,
            'tp_order_ids': self.tp_order_ids,
            'created_at': self.created_at.isoformat() if hasattr(self.created_at, 'isoformat') else self.created_at,
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'last_updated': self.last_updated.isoformat() if hasattr(self.last_updated, 'isoformat') else self.last_updated,
            'broker': self.broker,
            'strategy': self.strategy,
            'metadata': self.metadata
        }
    
    def update_price(self, price: Decimal):
        """Update current price and P&L."""
        self.current_price = price
        
        # Update highest/lowest for trailing stop
        if self.side == OrderSide.BUY:
            if price > self.highest_price:
                self.highest_price = price
        else:
            if self.lowest_price == 0 or price < self.lowest_price:
                self.lowest_price = price
        
        # Calculate unrealized P&L
        if self.filled_quantity > 0:
            if self.side == OrderSide.BUY:
                self.unrealized_pnl = (price - self.avg_entry_price) * self.filled_quantity
            else:
                self.unrealized_pnl = (self.avg_entry_price - price) * self.filled_quantity
        
        self.last_updated = self._time_provider.now()
    
    def add_fill(self, quantity: Decimal, price: Decimal, commission: Decimal = Decimal('0')):
        """Add a fill to the position."""
        # Update average entry price
        total_value = (self.avg_entry_price * self.filled_quantity) + (price * quantity)
        self.filled_quantity += quantity
        self.avg_entry_price = total_value / self.filled_quantity if self.filled_quantity > 0 else price
        
        # Update remaining quantity if this is first fill
        if self.remaining_quantity == 0:
            self.remaining_quantity = self.filled_quantity
        
        # Update commission
        self.commission += commission
        
        # Update state
        if self.state == PositionState.OPENING and self.filled_quantity >= self.target_quantity:
            self.state = PositionState.OPEN
            self.opened_at = self._time_provider.now()
        
        self.last_updated = self._time_provider.now()
    
    def add_exit(self, quantity: Decimal, price: Decimal, commission: Decimal = Decimal('0')):
        """Add an exit to the position."""
        if quantity > self.remaining_quantity:
            quantity = self.remaining_quantity
        
        # Calculate realized P&L for this exit
        if self.side == OrderSide.BUY:
            pnl = (price - self.avg_entry_price) * quantity
        else:
            pnl = (self.avg_entry_price - price) * quantity
        
        self.realized_pnl += pnl
        self.remaining_quantity -= quantity
        self.commission += commission
        
        # Update state
        if self.remaining_quantity == 0:
            self.state = PositionState.CLOSED
            self.closed_at = self._time_provider.now()
        elif self.state == PositionState.OPEN:
            self.state = PositionState.SCALING_OUT
        
        self.last_updated = self._time_provider.now()


class PositionManager(IPositionManager):
    """Manages position lifecycle and state transitions."""
    
    def __init__(
        self,
        time_provider: Optional[ITimeProvider] = None,
        event_publisher: Optional[IEventPublisher] = None,
        metrics_collector: Optional[IMetricsCollector] = None
    ):
        self._time_provider = time_provider or UTCTimeProvider()
        self._event_publisher = event_publisher
        self._metrics_collector = metrics_collector
        
        self.positions: Dict[str, Position] = {}
        self.positions_by_signal: Dict[str, List[str]] = {}
        self.positions_by_symbol: Dict[str, List[str]] = {}
        self.closed_positions: Dict[str, Position] = {}
        self._lock = asyncio.Lock()
        
    async def create_position(self, position_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new position."""
        async with self._lock:
            position = Position(position_data, self._time_provider)
            self.positions[position.position_id] = position
            
            # Index by signal
            if position.signal_id:
                if position.signal_id not in self.positions_by_signal:
                    self.positions_by_signal[position.signal_id] = []
                self.positions_by_signal[position.signal_id].append(position.position_id)
            
            # Index by symbol
            if position.symbol not in self.positions_by_symbol:
                self.positions_by_symbol[position.symbol] = []
            self.positions_by_symbol[position.symbol].append(position.position_id)
            
            logger.info(f"Created position {position.position_id} for {position.symbol}")
            
            # Publish event if publisher available
            if self._event_publisher:
                await self._event_publisher.publish(
                    'position.created',
                    position.to_dict()
                )
            
            return position.to_dict()
    
    async def get_position(self, position_id: str) -> Optional[Dict[str, Any]]:
        """Get position by ID."""
        position = self.positions.get(position_id)
        return position.to_dict() if position else None
    
    async def get_positions_by_signal(self, signal_id: str) -> List[Position]:
        """Get all positions for a signal."""
        position_ids = self.positions_by_signal.get(signal_id, [])
        return [self.positions[pid] for pid in position_ids if pid in self.positions]
    
    async def get_positions_by_symbol(self, symbol: str) -> List[Position]:
        """Get all positions for a symbol."""
        position_ids = self.positions_by_symbol.get(symbol, [])
        return [self.positions[pid] for pid in position_ids if pid in self.positions]
    
    async def get_open_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions."""
        return [
            p.to_dict() for p in self.positions.values() 
            if p.state in [PositionState.OPEN, PositionState.SCALING_OUT]
        ]
    
    async def update_position_state(self, position_id: str, new_state: PositionState) -> bool:
        """Update position state."""
        async with self._lock:
            position = self.positions.get(position_id)
            if not position:
                return False
            
            old_state = position.state
            position.state = new_state
            position.last_updated = self._time_provider.now()
            
            # Handle state transitions
            if new_state == PositionState.OPEN and not position.opened_at:
                position.opened_at = self._time_provider.now()
            elif new_state == PositionState.CLOSED and not position.closed_at:
                position.closed_at = self._time_provider.now()
                await self._close_position(position)
            
            logger.info(f"Position {position_id} state changed: {old_state} -> {new_state}")
            return True
    
    async def update_position_fill(
        self, 
        position_id: str, 
        quantity: Decimal, 
        price: Decimal,
        commission: Decimal = Decimal('0')
    ) -> bool:
        """Update position with a fill."""
        async with self._lock:
            position = self.positions.get(position_id)
            if not position:
                return False
            
            position.add_fill(quantity, price, commission)
            logger.info(
                f"Position {position_id} filled: {quantity} @ {price}, "
                f"total filled: {position.filled_quantity}/{position.target_quantity}"
            )
            return True
    
    async def update_position_exit(
        self,
        position_id: str,
        quantity: Decimal,
        price: Decimal,
        commission: Decimal = Decimal('0')
    ) -> bool:
        """Update position with an exit."""
        async with self._lock:
            position = self.positions.get(position_id)
            if not position:
                return False
            
            position.add_exit(quantity, price, commission)
            logger.info(
                f"Position {position_id} exit: {quantity} @ {price}, "
                f"remaining: {position.remaining_quantity}, "
                f"realized P&L: {position.realized_pnl}"
            )
            
            # Move to closed if fully exited
            if position.state == PositionState.CLOSED:
                await self._close_position(position)
            
            return True
    
    async def update_position_price(self, position_id: str, price: Decimal) -> bool:
        """Update position current price."""
        position = self.positions.get(position_id)
        if not position:
            return False
        
        position.update_price(price)
        return True
    
    async def update_stop_loss(self, position_id: str, new_stop: Decimal) -> bool:
        """Update position stop loss."""
        async with self._lock:
            position = self.positions.get(position_id)
            if not position:
                return False
            
            old_stop = position.stop_loss
            position.stop_loss = new_stop
            position.last_updated = self._time_provider.now()
            
            logger.info(f"Position {position_id} stop loss updated: {old_stop} -> {new_stop}")
            return True
    
    async def activate_trailing_stop(
        self, 
        position_id: str, 
        distance: Decimal
    ) -> bool:
        """Activate trailing stop for position."""
        async with self._lock:
            position = self.positions.get(position_id)
            if not position:
                return False
            
            position.trailing_stop_active = True
            position.trailing_stop_distance = distance
            position.last_updated = self._time_provider.now()
            
            # Initialize highest/lowest price
            if position.side == OrderSide.BUY:
                position.highest_price = position.current_price
            else:
                position.lowest_price = position.current_price
            
            logger.info(f"Position {position_id} trailing stop activated: distance={distance}")
            return True
    
    async def calculate_trailing_stop(self, position_id: str) -> Optional[Decimal]:
        """Calculate current trailing stop level."""
        position = self.positions.get(position_id)
        if not position or not position.trailing_stop_active:
            return None
        
        if position.side == OrderSide.BUY:
            return position.highest_price - position.trailing_stop_distance
        else:
            return position.lowest_price + position.trailing_stop_distance
    
    async def get_position_metrics(self, position_id: str) -> Dict[str, Any]:
        """Get detailed position metrics."""
        position = self.positions.get(position_id)
        if not position:
            return {}
        
        # Calculate metrics
        total_pnl = position.realized_pnl + position.unrealized_pnl
        pnl_percent = (total_pnl / (position.avg_entry_price * position.filled_quantity) * 100) if position.filled_quantity > 0 else 0
        
        # Time metrics
        if position.opened_at:
            duration = (position.closed_at or self._time_provider.now()) - position.opened_at
            duration_minutes = duration.total_seconds() / 60
        else:
            duration_minutes = 0
        
        return {
            'position_id': position.position_id,
            'symbol': position.symbol,
            'side': position.side.value,
            'state': position.state.value,
            'filled_quantity': float(position.filled_quantity),
            'remaining_quantity': float(position.remaining_quantity),
            'avg_entry_price': float(position.avg_entry_price),
            'current_price': float(position.current_price),
            'realized_pnl': float(position.realized_pnl),
            'unrealized_pnl': float(position.unrealized_pnl),
            'total_pnl': float(total_pnl),
            'pnl_percent': float(pnl_percent),
            'commission': float(position.commission),
            'duration_minutes': duration_minutes,
            'risk_reward_ratio': self._calculate_risk_reward(position)
        }
    
    async def cleanup_stale_positions(self, max_age_hours: int = 24):
        """Clean up old closed positions."""
        async with self._lock:
            cutoff_time = self._time_provider.now() - timedelta(hours=max_age_hours)
            positions_to_remove = []
            
            for pos_id, position in self.closed_positions.items():
                if position.closed_at and position.closed_at < cutoff_time:
                    positions_to_remove.append(pos_id)
            
            for pos_id in positions_to_remove:
                del self.closed_positions[pos_id]
            
            if positions_to_remove:
                logger.info(f"Cleaned up {len(positions_to_remove)} stale positions")
    
    async def _close_position(self, position: Position):
        """Move position to closed positions."""
        # Remove from active positions
        if position.position_id in self.positions:
            del self.positions[position.position_id]
        
        # Remove from indexes
        if position.signal_id and position.signal_id in self.positions_by_signal:
            self.positions_by_signal[position.signal_id].remove(position.position_id)
            if not self.positions_by_signal[position.signal_id]:
                del self.positions_by_signal[position.signal_id]
        
        if position.symbol in self.positions_by_symbol:
            self.positions_by_symbol[position.symbol].remove(position.position_id)
            if not self.positions_by_symbol[position.symbol]:
                del self.positions_by_symbol[position.symbol]
        
        # Add to closed positions
        self.closed_positions[position.position_id] = position
        
        # Publish event if publisher available
        if self._event_publisher:
            await self._event_publisher.publish(
                'position.closed',
                position.to_dict()
            )
        
        # Record metrics if collector available
        if self._metrics_collector and position.opened_at:
            duration = (position.closed_at - position.opened_at).total_seconds()
            outcome = 'win' if position.realized_pnl > 0 else 'loss'
            self._metrics_collector.record_trade_outcome(
                position.symbol,
                position.realized_pnl,
                int(duration),
                outcome
            )
    
    def _calculate_risk_reward(self, position: Position) -> float:
        """Calculate risk/reward ratio for position."""
        if position.stop_loss == 0 or position.avg_entry_price == 0:
            return 0
        
        # Calculate risk
        if position.side == OrderSide.BUY:
            risk = position.avg_entry_price - position.stop_loss
            reward = position.take_profit_1 - position.avg_entry_price if position.take_profit_1 > 0 else 0
        else:
            risk = position.stop_loss - position.avg_entry_price
            reward = position.avg_entry_price - position.take_profit_1 if position.take_profit_1 > 0 else 0
        
        return float(reward / risk) if risk > 0 else 0