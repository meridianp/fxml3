"""
FXCM Broker Adapter - TDD Implementation (GREEN Phase)
Minimal implementation to make tests pass
"""

import asyncio
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


class FXCMAdapter:
    """
    FXCM trading adapter for forex markets.
    GREEN phase: Minimal implementation to pass all tests.
    """

    def __init__(
        self,
        min_lot_size: float = 0.01,
        max_leverage: int = 50,
        account_balance: float = 10000,
        leverage_tiers: Optional[Dict[int, int]] = None,
        max_spread_pips: float = 5.0,
        weekend_protection: bool = False,
        check_trading_hours: bool = False,
        auto_reconnect: bool = False,
    ):
        """Initialize FXCM adapter with configuration."""
        self.min_lot_size = min_lot_size
        self.max_leverage = max_leverage
        self.account_balance = account_balance
        self.leverage_tiers = leverage_tiers or {100000: 50}
        self.max_spread_pips = max_spread_pips
        self.weekend_protection = weekend_protection
        self.check_trading_hours = check_trading_hours
        self.auto_reconnect = auto_reconnect

        # Connection state
        self.connected = True
        self.session_token = None

        # Order and position tracking
        self.orders = {}
        self.positions = {}
        self.next_order_id = 1

        # Market data
        self.market_data = {}
        self.market_prices = {}

        # Swap rates (simplified)
        self.swap_rates = {
            "EUR/USD": {"long": -0.5, "short": 0.2},
            "GBP/USD": {"long": -0.6, "short": 0.3},
            "USD/JPY": {"long": 0.3, "short": -0.6},
        }

    def place_order(self, order: Dict[str, Any]) -> int:
        """Place an order with validation."""
        # Validate symbol format
        if not self._validate_symbol_format(order.get("symbol", "")):
            raise ValueError(f"Invalid symbol format: {order.get('symbol')}")

        # Check market hours if enabled
        if self.check_trading_hours:
            symbol = order.get("symbol", "")
            if not self._is_market_open(symbol):
                raise ValueError(f"Market closed for {symbol}")

        # Check spread
        symbol = order.get("symbol", "")
        if symbol in self.market_data:
            spread = self._calculate_spread_pips(symbol)
            if spread > self.max_spread_pips:
                raise RuntimeError(f"Spread too wide: {spread:.1f} pips")

        # Check leverage
        if not self._validate_leverage(order):
            raise ValueError(f"Exceeds maximum leverage of {self.max_leverage}:1")

        # Create order
        order_id = self.next_order_id
        self.next_order_id += 1

        self.orders[order_id] = {
            **order,
            "order_id": order_id,
            "status": "PENDING",
            "quantity": order.get("quantity", 0),
            "filled": 0,
            "remaining": order.get("quantity", 0),
            "stop_loss": order.get("stop_loss"),
            "trailing_stop": order.get("trailing_stop"),
            "entry_price": order.get("entry_price"),
        }

        # Track as position if market order
        if order.get("order_type") == "market":
            self.positions[order_id] = {
                "order_id": order_id,
                "symbol": order.get("symbol"),
                "side": order.get("side"),
                "quantity": order.get("quantity"),
                "entry_price": order.get("entry_price", self._get_market_price(symbol)),
                "status": "OPEN",
                "open_time": datetime.now(),
            }

        return order_id

    def get_order_status(self, order_id: int) -> Dict[str, Any]:
        """Get status of an order."""
        if order_id not in self.orders:
            raise ValueError(f"Unknown order ID: {order_id}")

        order = self.orders[order_id]
        return {
            "order_id": order_id,
            "status": order["status"],
            "quantity": order["quantity"],
            "filled": order.get("filled", 0),
            "remaining": order.get("remaining", order["quantity"]),
            "stop_loss": order.get("stop_loss"),
        }

    def calculate_pip_value(self, symbol: str, lot_size: float, price: float) -> float:
        """Calculate pip value for a position."""
        # Standard lot = 100,000 units
        # Mini lot = 10,000 units (0.1)
        # Micro lot = 1,000 units (0.01)
        units = lot_size * 100000

        if symbol.endswith("/USD"):
            # For XXX/USD pairs, pip value = units * 0.0001
            return units * 0.0001
        elif symbol.startswith("USD/"):
            # For USD/XXX pairs, pip value = units * 0.0001 / price
            if symbol == "USD/JPY":
                # JPY pairs use 0.01 as pip
                return units * 0.01 / price
            return units * 0.0001 / price
        else:
            # For cross pairs (e.g., EUR/GBP), approximate
            return units * 0.0001

    def update_market_price(self, symbol: str, price: float) -> None:
        """Update market price for a symbol."""
        self.market_prices[symbol] = price

        # Update trailing stops
        for order_id, order in self.orders.items():
            if (
                order.get("symbol") == symbol
                and order.get("trailing_stop")
                and order.get("side") == "buy"
            ):

                entry = order.get("entry_price", 1.1000)
                trailing = (
                    order.get("trailing_stop", 0) / 10000
                )  # Convert pips to price
                profit_pips = (price - entry) * 10000

                if profit_pips > order.get("trailing_stop", 0):
                    # Move stop up
                    new_stop = price - trailing
                    if not order.get("stop_loss") or new_stop > order.get("stop_loss"):
                        order["stop_loss"] = new_stop

    def close_weekend_positions(self) -> List[Dict[str, Any]]:
        """Close all positions before weekend."""
        closed = []
        for pos_id, position in list(self.positions.items()):
            if position.get("status") == "OPEN":
                position["status"] = "CLOSED"
                closed.append(position)
                del self.positions[pos_id]
        return closed

    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Get list of open positions."""
        return [p for p in self.positions.values() if p.get("status") == "OPEN"]

    def calculate_required_margin(
        self, symbol: str, lots: float, price: float
    ) -> float:
        """Calculate required margin based on tiered leverage."""
        units = lots * 100000  # Convert to units
        total_value = units * price

        if not self.leverage_tiers:
            return total_value / self.max_leverage

        # Determine which tier the total position falls into
        applicable_leverage = 10  # Default to lowest leverage

        for tier_limit, leverage in sorted(self.leverage_tiers.items()):
            if units <= tier_limit:
                applicable_leverage = leverage
                break

        # Apply the leverage for the entire position
        return total_value / applicable_leverage

    def update_market_data(self, symbol: str, bid: float, ask: float) -> None:
        """Update market data with bid/ask prices."""
        self.market_data[symbol] = {"bid": bid, "ask": ask}

    def process_fill(self, fill_data: Dict[str, Any]) -> None:
        """Process a fill notification."""
        order_id = fill_data.get("orderId")
        if order_id not in self.orders:
            return

        order = self.orders[order_id]
        order["filled"] = fill_data.get("filled", 0)
        order["remaining"] = fill_data.get("remaining", 0)
        order["avgFillPrice"] = fill_data.get("avgFillPrice")

        if order["remaining"] == 0:
            order["status"] = "FILLED"

    def close_position(self, order_id: int, quantity: Optional[float] = None) -> int:
        """Close or partially close a position."""
        if order_id not in self.positions:
            raise ValueError(f"Position not found: {order_id}")

        position = self.positions[order_id]

        if quantity and quantity < position["quantity"]:
            # Partial close
            position["quantity"] -= quantity
            close_order_id = self.next_order_id
            self.next_order_id += 1
            return close_order_id
        else:
            # Full close
            position["status"] = "CLOSED"
            return order_id

    def get_position(self, order_id: int) -> Dict[str, Any]:
        """Get position details."""
        if order_id not in self.positions:
            return None
        return self.positions[order_id].copy()

    def calculate_swap(self, position: Dict[str, Any]) -> float:
        """Calculate overnight swap/rollover."""
        symbol = position.get("symbol", "EUR/USD")
        side = position.get("side", "buy")
        quantity = position.get("quantity", 0)

        # Get swap rate
        swap_rate = self.swap_rates.get(symbol, {}).get(
            "long" if side == "buy" else "short", 0
        )

        # Calculate days held
        open_time = position.get("open_time", datetime.now())
        current_time = position.get("current_time", datetime.now())
        days_held = (current_time - open_time).days

        if days_held > 0:
            # Simplified swap calculation (pip value * swap rate * lots * days)
            pip_value = self.calculate_pip_value(symbol, quantity, 1.1000)
            return pip_value * swap_rate * days_held

        return 0.0

    async def ensure_connection(self) -> None:
        """Ensure connection is active."""
        if self.connected:
            return

        if self.auto_reconnect and self.session_token:
            success = await self._reconnect_with_token(self.session_token)
            if success:
                self.connected = True
            else:
                raise ConnectionError("Failed to reconnect")

    async def _reconnect_with_token(self, token: str) -> bool:
        """Reconnect using session token."""
        # Simulated reconnection logic
        return True

    def _validate_symbol_format(self, symbol: str) -> bool:
        """Validate forex symbol format (XXX/YYY)."""
        # Valid forex pairs only
        valid_currencies = {"EUR", "USD", "GBP", "JPY", "CHF", "AUD", "CAD", "NZD"}

        # Check for forex format: XXX/YYY
        pattern = r"^[A-Z]{3}/[A-Z]{3}$"
        if not re.match(pattern, symbol):
            return False

        # Check if both currencies are valid forex currencies
        base, quote = symbol.split("/")
        return base in valid_currencies and quote in valid_currencies

    def _validate_leverage(self, order: Dict[str, Any]) -> bool:
        """Check if order exceeds leverage limits."""
        symbol = order.get("symbol", "EUR/USD")
        quantity = order.get("quantity", 0)
        price = self._get_market_price(symbol)

        position_value = quantity * 100000 * price
        required_margin = position_value / self.max_leverage

        return required_margin <= self.account_balance

    def _calculate_spread_pips(self, symbol: str) -> float:
        """Calculate spread in pips."""
        if symbol not in self.market_data:
            return 0

        data = self.market_data[symbol]
        spread = data["ask"] - data["bid"]

        if symbol == "USD/JPY" or symbol.endswith("/JPY"):
            return spread * 100  # JPY pairs
        else:
            return spread * 10000  # Standard pairs

    def _get_market_price(self, symbol: str) -> float:
        """Get current market price for symbol."""
        if symbol in self.market_prices:
            return self.market_prices[symbol]
        if symbol in self.market_data:
            return (
                self.market_data[symbol]["bid"] + self.market_data[symbol]["ask"]
            ) / 2
        return 1.1000  # Default

    def _is_market_open(self, symbol: str) -> bool:
        """Check if market is open for trading."""
        now = datetime.now()
        weekday = now.weekday()

        # Forex closed from Friday 5pm to Sunday 5pm EST
        if weekday == 5:  # Saturday
            return False
        if weekday == 6 and now.hour < 17:  # Sunday before 5pm
            return False
        if weekday == 4 and now.hour >= 17:  # Friday after 5pm
            return False

        return True
