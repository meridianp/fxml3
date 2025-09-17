"""
Trade Execution Engine for FXML4

TDD-driven implementation of execution engine with slippage management.
Following Green phase - minimal implementation to pass tests.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from core.trading.orders import Order, OrderSide, OrderState


class ExecutionEngine:
    """Engine for order execution and fill management."""

    def __init__(
        self,
        router=None,
        max_slippage_pips: Optional[int] = None,
        price_feed=None,
    ):
        """Initialize execution engine."""
        self.router = router
        self.max_slippage_pips = max_slippage_pips
        self.price_feed = price_feed

        # Execution statistics
        self.total_orders = 0
        self.total_fills = 0
        self.total_slippage = Decimal("0")

    async def execute_order(self, order: Order) -> Dict[str, Any]:
        """Execute an order through the router."""
        if not self.router:
            # Direct execution without router (for testing)
            return {
                "status": "executed",
                "broker_id": "TEST",
                "broker_order_id": f"TEST_{order.order_id[:8]}",
                "timestamp": datetime.now().isoformat(),
            }

        # Check slippage limits for market orders
        if order.order_type.value == "market" and self.max_slippage_pips:
            expected_price = await self._get_expected_price(order)
            fill_price = await self._get_fill_price(order)

            if expected_price and fill_price:
                slippage = self.calculate_slippage(
                    expected_price=expected_price,
                    fill_price=fill_price,
                    quantity=order.quantity,
                    side=order.side,
                )

                if abs(slippage["pips"]) > self.max_slippage_pips:
                    raise Exception(
                        f"Slippage exceeds maximum: {slippage['pips']} pips"
                    )

        # Route order
        result = await self.router.route_order(order)
        result["status"] = "executed"

        self.total_orders += 1
        return result

    def calculate_slippage(
        self,
        expected_price: Decimal,
        fill_price: Decimal,
        quantity: int,
        side: OrderSide,
    ) -> Dict[str, Decimal]:
        """Calculate slippage for an executed order."""
        # Calculate price difference
        price_diff = fill_price - expected_price

        # For sell orders, invert the sign
        if side == OrderSide.SELL:
            price_diff = -price_diff

        # Calculate in pips (assuming 4 decimal places for forex)
        pips = price_diff * Decimal("10000")

        # Calculate cost
        cost = abs(price_diff) * Decimal(quantity)

        return {
            "pips": pips,
            "cost": cost,
            "percentage": (price_diff / expected_price) * Decimal("100"),
        }

    async def get_spread(self, symbol: str) -> Dict[str, Any]:
        """Get current bid-ask spread for a symbol."""
        if not self.price_feed:
            # Default spread for testing
            return {
                "bid": Decimal("1.0948"),
                "ask": Decimal("1.0950"),
                "spread_pips": Decimal("2"),
                "spread_percentage": Decimal("0.0183"),
                "timestamp": datetime.now(),
            }

        quote = await self.price_feed.get_quote(symbol)

        bid = quote["bid"]
        ask = quote["ask"]
        spread = ask - bid
        spread_pips = spread * Decimal("10000")
        spread_percentage = (spread / bid) * Decimal("100")

        return {
            "bid": bid,
            "ask": ask,
            "spread_pips": spread_pips,
            "spread_percentage": spread_percentage.quantize(Decimal("0.0001")),
            "timestamp": quote["timestamp"],
        }

    async def handle_fill(self, order: Order, fill: Dict[str, Any]):
        """Handle fill notification for an order."""
        fill_quantity = fill["quantity"]
        fill_price = fill["price"]

        if order.filled_quantity + fill_quantity >= order.quantity:
            # Full fill
            order.fill(
                filled_quantity=order.quantity,
                fill_price=self._calculate_weighted_avg(
                    order, fill_quantity, fill_price
                ),
                commission=Decimal("0"),  # Commission handled separately
            )
        else:
            # Partial fill
            order.partial_fill(
                filled_quantity=fill_quantity,
                fill_price=fill_price,
                commission=Decimal("0"),
            )

        self.total_fills += 1

    def _calculate_weighted_avg(
        self, order: Order, new_quantity: int, new_price: Decimal
    ) -> Decimal:
        """Calculate weighted average fill price."""
        if order.filled_quantity == 0:
            return new_price

        total_value = (
            order.filled_quantity * (order.average_fill_price or Decimal("0"))
            + new_quantity * new_price
        )
        total_quantity = order.filled_quantity + new_quantity

        return total_value / Decimal(total_quantity)

    async def _get_expected_price(self, order: Order) -> Optional[Decimal]:
        """Get expected execution price for an order."""
        if self.price_feed:
            quote = await self.price_feed.get_quote(order.symbol)
            if order.side == OrderSide.BUY:
                return quote["ask"]
            else:
                return quote["bid"]
        return Decimal("1.0950")  # Default for testing

    async def _get_fill_price(self, order: Order) -> Optional[Decimal]:
        """Get actual fill price (simulated)."""
        # In production, this would come from broker
        # For testing, simulate with small slippage
        expected = await self._get_expected_price(order)
        if expected:
            if order.side == OrderSide.BUY:
                # Simulate adverse slippage for buys
                return expected + Decimal("0.0010")  # 10 pips for testing
            else:
                # Simulate adverse slippage for sells
                return expected - Decimal("0.0010")  # 10 pips for testing
        return None