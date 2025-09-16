"""Example implementations of domain interfaces for testing and reference."""

from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal
import logging
from collections import defaultdict

from .interfaces import (
    IEventPublisher, IMetricsCollector, IMarketDataProvider,
    IRiskCalculator, IBrokerAdapter, IPositionRepository
)
from .models import (
    OrderRequest, OrderResponse, OrderStatus,
    MarketData, OrderSide, OrderModifyRequest
)

logger = logging.getLogger(__name__)


class MockEventPublisher(IEventPublisher):
    """Mock event publisher for testing."""
    
    def __init__(self):
        self.events: List[Tuple[str, Dict[str, Any]]] = []
    
    async def publish(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Publish an event."""
        self.events.append((event_type, event_data))
        logger.debug(f"Event published: {event_type}")
    
    async def publish_batch(self, events: List[Tuple[str, Dict[str, Any]]]) -> None:
        """Publish multiple events."""
        self.events.extend(events)
        logger.debug(f"Batch of {len(events)} events published")
    
    def get_events(self, event_type: Optional[str] = None) -> List[Tuple[str, Dict[str, Any]]]:
        """Get published events, optionally filtered by type."""
        if event_type:
            return [(t, d) for t, d in self.events if t == event_type]
        return self.events.copy()
    
    def clear_events(self) -> None:
        """Clear all published events."""
        self.events.clear()


class InMemoryMetricsCollector(IMetricsCollector):
    """In-memory metrics collector for testing."""
    
    def __init__(self):
        self.trade_outcomes: List[Dict[str, Any]] = []
        self.risk_violations: List[Dict[str, Any]] = []
        self.metrics_by_symbol: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'total_trades': 0,
            'winning_trades': 0,
            'total_pnl': Decimal('0'),
            'total_duration': 0
        })
    
    def record_trade_outcome(
        self,
        symbol: str,
        pnl: Decimal,
        duration_seconds: int,
        outcome: str
    ) -> None:
        """Record trade outcome metrics."""
        self.trade_outcomes.append({
            'symbol': symbol,
            'pnl': pnl,
            'duration_seconds': duration_seconds,
            'outcome': outcome
        })
        
        # Update symbol metrics
        metrics = self.metrics_by_symbol[symbol]
        metrics['total_trades'] += 1
        metrics['total_pnl'] += pnl
        metrics['total_duration'] += duration_seconds
        if outcome == 'win':
            metrics['winning_trades'] += 1
    
    def record_risk_violation(
        self,
        risk_type: str,
        severity: str,
        details: Dict[str, Any]
    ) -> None:
        """Record risk violation."""
        self.risk_violations.append({
            'risk_type': risk_type,
            'severity': severity,
            'details': details
        })
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of collected metrics."""
        total_trades = len(self.trade_outcomes)
        winning_trades = sum(1 for t in self.trade_outcomes if t['outcome'] == 'win')
        total_pnl = sum(t['pnl'] for t in self.trade_outcomes)
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'win_rate': winning_trades / total_trades if total_trades > 0 else 0,
            'total_pnl': float(total_pnl),
            'risk_violations': len(self.risk_violations),
            'metrics_by_symbol': {
                symbol: {
                    'total_trades': metrics['total_trades'],
                    'win_rate': metrics['winning_trades'] / metrics['total_trades'] if metrics['total_trades'] > 0 else 0,
                    'total_pnl': float(metrics['total_pnl']),
                    'avg_duration': metrics['total_duration'] / metrics['total_trades'] if metrics['total_trades'] > 0 else 0
                }
                for symbol, metrics in self.metrics_by_symbol.items()
            }
        }


class SimpleRiskCalculator(IRiskCalculator):
    """Simple implementation of risk calculator."""
    
    def calculate_position_size(
        self,
        account_balance: Decimal,
        risk_percentage: Decimal,
        stop_loss_pips: Decimal,
        pip_value: Decimal
    ) -> Decimal:
        """Calculate appropriate position size."""
        risk_amount = account_balance * (risk_percentage / 100)
        position_size = risk_amount / (stop_loss_pips * pip_value)
        return position_size
    
    def calculate_risk_amount(
        self,
        position_size: Decimal,
        entry_price: Decimal,
        stop_loss_price: Decimal,
        side: OrderSide
    ) -> Decimal:
        """Calculate risk amount for a position."""
        if side == OrderSide.BUY:
            risk_per_unit = entry_price - stop_loss_price
        else:
            risk_per_unit = stop_loss_price - entry_price
        
        return abs(risk_per_unit * position_size)
    
    def calculate_risk_reward_ratio(
        self,
        entry_price: Decimal,
        stop_loss_price: Decimal,
        take_profit_price: Decimal,
        side: OrderSide
    ) -> Decimal:
        """Calculate risk/reward ratio."""
        if side == OrderSide.BUY:
            risk = entry_price - stop_loss_price
            reward = take_profit_price - entry_price
        else:
            risk = stop_loss_price - entry_price
            reward = entry_price - take_profit_price
        
        return reward / risk if risk > 0 else Decimal('0')


class MockMarketDataProvider(IMarketDataProvider):
    """Mock market data provider for testing."""
    
    def __init__(self):
        self.prices: Dict[str, Decimal] = {
            'EURUSD': Decimal('1.0850'),
            'GBPUSD': Decimal('1.2650'),
            'USDJPY': Decimal('150.25')
        }
        self.volatilities: Dict[str, Decimal] = {
            'EURUSD': Decimal('0.008'),
            'GBPUSD': Decimal('0.010'),
            'USDJPY': Decimal('0.012')
        }
        self.correlations: Dict[Tuple[str, str], float] = {
            ('EURUSD', 'GBPUSD'): 0.75,
            ('EURUSD', 'USDJPY'): -0.30,
            ('GBPUSD', 'USDJPY'): -0.25
        }
    
    async def get_current_price(self, symbol: str) -> Decimal:
        """Get current price for a symbol."""
        return self.prices.get(symbol, Decimal('1.0'))
    
    async def get_market_data(self, symbol: str) -> MarketData:
        """Get comprehensive market data for a symbol."""
        price = self.prices.get(symbol, Decimal('1.0'))
        volatility = self.volatilities.get(symbol, Decimal('0.01'))
        
        return MarketData(
            symbol=symbol,
            current_price=price,
            bid=price - Decimal('0.0001'),
            ask=price + Decimal('0.0001'),
            volatility=volatility,
            atr=price * volatility * Decimal('1.5')
        )
    
    async def get_volatility(self, symbol: str) -> Decimal:
        """Get current volatility for a symbol."""
        return self.volatilities.get(symbol, Decimal('0.01'))
    
    async def get_correlation(self, symbol1: str, symbol2: str) -> float:
        """Get correlation between two symbols."""
        key = (symbol1, symbol2) if symbol1 < symbol2 else (symbol2, symbol1)
        return self.correlations.get(key, 0.0)
    
    def set_price(self, symbol: str, price: Decimal) -> None:
        """Set price for testing."""
        self.prices[symbol] = price
    
    def set_volatility(self, symbol: str, volatility: Decimal) -> None:
        """Set volatility for testing."""
        self.volatilities[symbol] = volatility


class MockBrokerAdapter(IBrokerAdapter):
    """Mock broker adapter for testing."""
    
    def __init__(self):
        self.orders: Dict[str, Dict[str, Any]] = {}
        self.order_counter = 0
    
    async def place_order(self, order_request: OrderRequest) -> OrderResponse:
        """Place an order with the broker."""
        self.order_counter += 1
        order_id = f"ORDER_{self.order_counter:06d}"
        
        self.orders[order_id] = {
            'request': order_request,
            'status': OrderStatus.ACCEPTED,
            'filled_quantity': Decimal('0')
        }
        
        return OrderResponse(
            broker_order_id=order_id,
            status=OrderStatus.ACCEPTED,
            symbol=order_request.symbol,
            side=order_request.side,
            quantity=order_request.quantity,
            message="Order accepted"
        )
    
    async def modify_order(self, modify_request: OrderModifyRequest) -> OrderResponse:
        """Modify an existing order."""
        order_id = modify_request.broker_order_id
        
        if order_id not in self.orders:
            return OrderResponse(
                broker_order_id=order_id,
                status=OrderStatus.REJECTED,
                symbol="",
                side=OrderSide.BUY,
                quantity=Decimal('0'),
                message="Order not found"
            )
        
        order = self.orders[order_id]
        order['status'] = OrderStatus.MODIFIED
        
        return OrderResponse(
            broker_order_id=order_id,
            status=OrderStatus.MODIFIED,
            symbol=order['request'].symbol,
            side=order['request'].side,
            quantity=order['request'].quantity,
            message="Order modified"
        )
    
    async def cancel_order(self, order_id: str) -> OrderResponse:
        """Cancel an existing order."""
        if order_id not in self.orders:
            return OrderResponse(
                broker_order_id=order_id,
                status=OrderStatus.REJECTED,
                symbol="",
                side=OrderSide.BUY,
                quantity=Decimal('0'),
                message="Order not found"
            )
        
        order = self.orders[order_id]
        order['status'] = OrderStatus.CANCELLED
        
        return OrderResponse(
            broker_order_id=order_id,
            status=OrderStatus.CANCELLED,
            symbol=order['request'].symbol,
            side=order['request'].side,
            quantity=order['request'].quantity,
            message="Order cancelled"
        )
    
    async def get_order_status(self, order_id: str) -> OrderResponse:
        """Get the status of an order."""
        if order_id not in self.orders:
            return OrderResponse(
                broker_order_id=order_id,
                status=OrderStatus.REJECTED,
                symbol="",
                side=OrderSide.BUY,
                quantity=Decimal('0'),
                message="Order not found"
            )
        
        order = self.orders[order_id]
        
        return OrderResponse(
            broker_order_id=order_id,
            status=order['status'],
            symbol=order['request'].symbol,
            side=order['request'].side,
            quantity=order['request'].quantity,
            filled_quantity=order['filled_quantity'],
            message=f"Order status: {order['status'].value}"
        )


class InMemoryPositionRepository(IPositionRepository):
    """In-memory position repository for testing."""
    
    def __init__(self):
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.position_counter = 0
    
    async def create(self, position_data: Dict[str, Any]) -> str:
        """Create a new position and return its ID."""
        self.position_counter += 1
        position_id = position_data.get('position_id', f"POS_{self.position_counter:06d}")
        
        self.positions[position_id] = position_data.copy()
        self.positions[position_id]['position_id'] = position_id
        
        return position_id
    
    async def get(self, position_id: str) -> Optional[Dict[str, Any]]:
        """Get position by ID."""
        return self.positions.get(position_id)
    
    async def update(self, position_id: str, updates: Dict[str, Any]) -> bool:
        """Update position data."""
        if position_id not in self.positions:
            return False
        
        self.positions[position_id].update(updates)
        return True
    
    async def delete(self, position_id: str) -> bool:
        """Delete a position."""
        if position_id not in self.positions:
            return False
        
        del self.positions[position_id]
        return True
    
    async def find_by_symbol(self, symbol: str) -> List[Dict[str, Any]]:
        """Find all positions for a symbol."""
        return [
            p for p in self.positions.values()
            if p.get('symbol') == symbol
        ]
    
    async def find_open_positions(self) -> List[Dict[str, Any]]:
        """Find all open positions."""
        return [
            p for p in self.positions.values()
            if p.get('state') in ['open', 'scaling_out']
        ]