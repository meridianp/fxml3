"""
Order execution handling for backtesting.
"""

import logging
import uuid
from datetime import datetime
from queue import Queue
from typing import Any, Dict, Optional

import numpy as np

from fxml4.backtesting.events import EventType, FillEvent, OrderEvent, OrderSide

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class SlippageModel:
    """Model for calculating slippage."""

    def __init__(
        self, model_type: str = "fixed", params: Optional[Dict[str, float]] = None
    ):
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
        self, order: OrderEvent, market_price: float, volume: Optional[float] = None
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
        latency: float = 0.0,
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
            slippage_model,
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
                "order_type": order.order_type.value,
                "market_price": market_price,
                "original_order": order.metadata,
            },
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
            commission,
        )

    def _get_market_price(self, symbol: str) -> Optional[float]:
        """Get current market price for symbol."""
        # Get from portfolio's current holdings
        if hasattr(self.portfolio, "current_holdings"):
            return self.portfolio.current_holdings.get(symbol)

        # Get from data handler if available
        if hasattr(self.portfolio, "data_handler"):
            latest_bar = self.portfolio.data_handler.get_latest_bar(symbol)
            if latest_bar is not None:
                return latest_bar.get("close")

        return None

    def _calculate_fill_price(
        self, order: OrderEvent, market_price: float
    ) -> Optional[float]:
        """Calculate fill price based on order type."""
        from fxml4.backtesting.events import OrderType

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
                    price=order.price,
                ),
                market_price,
            )

        return None

    def _calculate_commission(self, quantity: float, price: float) -> float:
        """Calculate commission for trade."""
        # Simple percentage commission
        return quantity * price * self.commission


class SimulatedExecutionHandler:
    """Simulated execution handler for backtesting that matches test expectations.

    This class implements the interface expected by the backtesting test suite,
    providing realistic order execution simulation with commission and slippage.
    """

    def __init__(
        self,
        commission: float = 0.001,
        slippage_pips: float = 0.5,
        slippage_model: str = "fixed",
        max_slippage_pips: float = 2.0,
    ):
        """Initialize the simulated execution handler.

        Args:
            commission: Commission rate (default 0.1% = 0.001)
            slippage_pips: Fixed slippage in pips (default 0.5 pips)
            slippage_model: Slippage model ('fixed' or 'variable')
            max_slippage_pips: Maximum slippage in pips for variable model
        """
        self.commission = commission
        self.slippage_pips = slippage_pips
        self.slippage_model = slippage_model
        self.max_slippage_pips = max_slippage_pips
        self.exchange = "SIMULATED"

        logger.info(
            f"SimulatedExecutionHandler initialized - Commission: "
            f"{commission:.4f}, Slippage: {slippage_pips} pips "
            f"({slippage_model} model)"
        )

    def execute_order(
        self,
        order: Dict[str, Any],
        current_price: float,
        spread: float = 0.0002,
        volume: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Execute order and return fill event.

        Args:
            order: Order dictionary with keys: timestamp, symbol, order_type,
                   quantity, direction, price (optional)
            current_price: Current market price
            spread: Bid-ask spread
            volume: Available volume (for variable slippage model)

        Returns:
            Fill event dictionary or None if order cannot be filled
        """
        try:
            # Determine if this is a market or limit order
            order_type = order.get("order_type", "MARKET")
            direction = order.get("direction", "BUY")
            quantity = order.get("quantity", 0)
            symbol = order.get("symbol", "UNKNOWN")
            timestamp = order.get("timestamp", datetime.now())

            # Calculate execution price
            execution_price = self._calculate_execution_price(
                order_type, direction, current_price, spread, order.get("price")
            )

            if execution_price is None:
                # Order cannot be filled (e.g., limit order not reached)
                return None

            # Apply slippage
            slippage_amount = self._calculate_slippage(
                execution_price, direction, quantity, volume
            )
            final_price = execution_price + slippage_amount

            # Calculate fill cost and commission
            fill_cost = final_price * quantity
            commission = fill_cost * self.commission

            # Create fill event that matches the test expectations
            fill_event = {
                "timestamp": timestamp,
                "symbol": symbol,
                "exchange": self.exchange,
                "quantity": quantity,
                "direction": direction,
                "fill_cost": fill_cost,
                "commission": commission,
                "fill_price": final_price,
                "slippage": abs(slippage_amount),
                "order_type": order_type,
            }

            logger.debug(
                f"Order executed: {direction} {quantity} {symbol} @ "
                f"{final_price:.5f} (slippage: {slippage_amount:.5f}, "
                f"commission: {commission:.2f})"
            )

            return fill_event

        except Exception as e:
            logger.error(f"Error executing order: {str(e)}")
            return None

    def _calculate_execution_price(
        self,
        order_type: str,
        direction: str,
        current_price: float,
        spread: float,
        limit_price: Optional[float] = None,
    ) -> Optional[float]:
        """Calculate the price at which the order should be executed."""

        if order_type.upper() == "MARKET":
            # Market orders execute at current price plus spread
            if direction.upper() == "BUY":
                return current_price + spread / 2  # Pay the ask
            else:
                return current_price - spread / 2  # Receive the bid

        elif order_type.upper() == "LIMIT":
            if limit_price is None:
                return None

            # Limit orders only execute if the limit price is reached
            if direction.upper() == "BUY":
                # Buy limit order executes if market price <= limit price
                ask_price = current_price + spread / 2
                if ask_price <= limit_price:
                    return limit_price
            else:
                # Sell limit order executes if market price >= limit price
                bid_price = current_price - spread / 2
                if bid_price >= limit_price:
                    return limit_price

            return None  # Limit not reached

        else:
            # Default to market execution for unknown order types
            return current_price

    def _calculate_slippage(
        self,
        execution_price: float,
        direction: str,
        quantity: float,
        volume: Optional[float] = None,
    ) -> float:
        """Calculate slippage amount."""

        if self.slippage_model == "fixed":
            # Fixed slippage in pips (1 pip = 0.0001 for 4-decimal currencies)
            slippage_amount = self.slippage_pips * 0.0001

        elif self.slippage_model == "variable":
            # Variable slippage based on order size vs available volume
            if volume and quantity > volume:
                # Large order relative to volume - more slippage
                volume_ratio = quantity / volume
                slippage_pips = min(
                    self.slippage_pips * volume_ratio, self.max_slippage_pips
                )
            else:
                slippage_pips = self.slippage_pips

            # Add some randomness (±50% of base slippage)
            import random

            random_factor = random.uniform(0.5, 1.5)
            slippage_amount = slippage_pips * 0.0001 * random_factor

        else:
            slippage_amount = 0.0

        # Apply slippage direction - adverse for the trader
        if direction.upper() == "BUY":
            return slippage_amount  # Pay more when buying
        else:
            return -slippage_amount  # Receive less when selling
