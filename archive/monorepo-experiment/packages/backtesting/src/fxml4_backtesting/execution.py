"""
Order execution handling for backtesting.
"""

from typing import Dict, Any, Optional
from queue import Queue
import uuid
from datetime import datetime
import numpy as np

from fxml4_core.logging import get_logger
from fxml4_backtesting.events import OrderEvent, FillEvent, OrderSide, EventType

logger = get_logger(__name__)


class SlippageModel:
    """Model for calculating slippage."""
    
    def __init__(self, model_type: str = "fixed", params: Optional[Dict[str, float]] = None):
        self.model_type = model_type
        self.params = params or {}
        
        # Default parameters
        if model_type == "fixed":
            self.params.setdefault("slippage", 0.0001)  # 1 pip
        elif model_type == "linear":
            self.params.setdefault("base_slippage", 0.0001)
            self.params.setdefault("impact_coefficient", 0.00001)
        elif model_type == "square_root":
            self.params.setdefault("base_slippage", 0.0001)
            self.params.setdefault("impact_coefficient", 0.00005)
    
    def calculate_slippage(
        self,
        order: OrderEvent,
        market_price: float,
        volume: Optional[float] = None
    ) -> float:
        """Calculate slippage for order."""
        if self.model_type == "fixed":
            slippage = self.params["slippage"]
            
        elif self.model_type == "linear":
            # Linear market impact
            base = self.params["base_slippage"]
            impact = self.params["impact_coefficient"] * order.quantity
            slippage = base + impact
            
        elif self.model_type == "square_root":
            # Square root market impact (more realistic)
            base = self.params["base_slippage"]
            impact = self.params["impact_coefficient"] * np.sqrt(order.quantity)
            slippage = base + impact
            
        else:
            slippage = 0.0
        
        # Apply slippage direction
        if order.side == OrderSide.BUY:
            return market_price * slippage  # Pay more when buying
        else:
            return -market_price * slippage  # Receive less when selling


class ExecutionHandler:
    """Handle order execution with realistic fills."""
    
    def __init__(
        self,
        events_queue: Queue,
        portfolio: Any,
        commission: float = 0.001,
        slippage_model: str = "fixed",
        latency: float = 0.0
    ):
        self.events_queue = events_queue
        self.portfolio = portfolio
        self.commission = commission
        self.slippage_model = SlippageModel(slippage_model)
        self.latency = latency
        self.exchange = "BACKTEST"
        
        logger.info(
            "ExecutionHandler initialized - Commission: %.4f, Slippage: %s",
            commission,
            slippage_model
        )
    
    def execute_order(self, order: OrderEvent) -> None:
        """Execute order and generate fill event."""
        # Get current market price
        market_price = self._get_market_price(order.symbol)
        if market_price is None:
            logger.error("No market price available for %s", order.symbol)
            return
        
        # Check order type and price
        fill_price = self._calculate_fill_price(order, market_price)
        if fill_price is None:
            logger.debug("Order not filled - price conditions not met")
            return
        
        # Calculate slippage
        slippage = self.slippage_model.calculate_slippage(order, fill_price)
        fill_price += slippage
        
        # Calculate commission
        commission = self._calculate_commission(order.quantity, fill_price)
        
        # Create fill event
        fill = FillEvent(
            type=EventType.FILL,
            timestamp=datetime.now(),
            symbol=order.symbol,
            order_id=order.order_id or str(uuid.uuid4()),
            exchange=self.exchange,
            side=order.side,
            quantity=order.quantity,
            price=fill_price,
            commission=commission,
            slippage=abs(slippage),
            metadata={
                'order_type': order.order_type.value,
                'market_price': market_price,
                'original_order': order.metadata
            }
        )
        
        # Put fill in queue
        self.events_queue.put(fill)
        
        logger.info(
            "Order filled - %s %s %.4f @ %.5f (slip: %.5f, comm: %.2f)",
            order.side.value,
            order.symbol,
            order.quantity,
            fill_price,
            slippage,
            commission
        )
    
    def _get_market_price(self, symbol: str) -> Optional[float]:
        """Get current market price for symbol."""
        # Get from portfolio's current holdings
        if hasattr(self.portfolio, 'current_holdings'):
            return self.portfolio.current_holdings.get(symbol)
        
        # Get from data handler if available
        if hasattr(self.portfolio, 'data_handler'):
            latest_bar = self.portfolio.data_handler.get_latest_bar(symbol)
            if latest_bar is not None:
                return latest_bar.get('close')
        
        return None
    
    def _calculate_fill_price(
        self,
        order: OrderEvent,
        market_price: float
    ) -> Optional[float]:
        """Calculate fill price based on order type."""
        from fxml4_backtesting.events import OrderType
        
        if order.order_type == OrderType.MARKET:
            # Market orders fill at current price
            return market_price
        
        elif order.order_type == OrderType.LIMIT:
            # Limit orders fill at limit price or better
            if order.price is None:
                return None
            
            if order.side == OrderSide.BUY:
                # Buy limit fills if market <= limit
                if market_price <= order.price:
                    return order.price
            else:
                # Sell limit fills if market >= limit
                if market_price >= order.price:
                    return order.price
            
            return None
        
        elif order.order_type == OrderType.STOP:
            # Stop orders become market orders when triggered
            if order.stop_price is None:
                return None
            
            if order.side == OrderSide.BUY:
                # Buy stop triggers if market >= stop
                if market_price >= order.stop_price:
                    return market_price
            else:
                # Sell stop triggers if market <= stop
                if market_price <= order.stop_price:
                    return market_price
            
            return None
        
        elif order.order_type == OrderType.STOP_LIMIT:
            # Stop limit orders need both conditions
            if order.stop_price is None or order.price is None:
                return None
            
            # First check if stop is triggered
            stop_triggered = False
            if order.side == OrderSide.BUY:
                stop_triggered = market_price >= order.stop_price
            else:
                stop_triggered = market_price <= order.stop_price
            
            if not stop_triggered:
                return None
            
            # Then check limit price
            return self._calculate_fill_price(
                OrderEvent(
                    type=EventType.ORDER,
                    timestamp=order.timestamp,
                    symbol=order.symbol,
                    order_type=OrderType.LIMIT,
                    side=order.side,
                    quantity=order.quantity,
                    price=order.price
                ),
                market_price
            )
        
        return None
    
    def _calculate_commission(self, quantity: float, price: float) -> float:
        """Calculate commission for trade."""
        # Simple percentage commission
        return quantity * price * self.commission