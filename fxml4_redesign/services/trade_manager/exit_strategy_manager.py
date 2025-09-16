"""Exit Strategy Manager - Handles stop loss, take profit, and trailing stops."""

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from shared.schemas.broker_messages import (
    BrokerMessageFactory,
    OrderModifyRequest,
    OrderRequest,
    OrderSide,
    OrderType,
    TimeInForce,
)

logger = logging.getLogger(__name__)


class ExitReason(str, Enum):
    """Reasons for position exit."""

    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"
    TIME_EXIT = "time_exit"
    SIGNAL_EXIT = "signal_exit"
    MANUAL_EXIT = "manual_exit"
    RISK_LIMIT = "risk_limit"
    DRAWDOWN_LIMIT = "drawdown_limit"


class ExitLevel(str, Enum):
    """Exit level definitions."""

    STOP_LOSS = "stop_loss"
    TAKE_PROFIT_1 = "take_profit_1"
    TAKE_PROFIT_2 = "take_profit_2"
    TAKE_PROFIT_3 = "take_profit_3"
    TRAILING_STOP = "trailing_stop"
    BREAK_EVEN = "break_even"


class ExitStrategy:
    """Exit strategy configuration."""

    def __init__(self, strategy_config: Dict[str, Any]):
        self.strategy_id = strategy_config.get("strategy_id")
        self.name = strategy_config.get("name", "default")

        # Stop loss
        self.stop_loss_type = strategy_config.get(
            "stop_loss_type", "fixed"
        )  # fixed, atr, percent
        self.stop_loss_value = Decimal(str(strategy_config.get("stop_loss_value", 50)))
        self.stop_loss_atr_multiplier = Decimal(
            str(strategy_config.get("stop_loss_atr_multiplier", 2))
        )

        # Take profit levels
        self.take_profit_levels = []
        for i in range(1, 4):
            tp_config = strategy_config.get(f"take_profit_{i}", {})
            if tp_config:
                self.take_profit_levels.append(
                    {
                        "level": i,
                        "target": Decimal(str(tp_config.get("target", 100 * i))),
                        "exit_percent": Decimal(
                            str(tp_config.get("exit_percent", 33.33))
                        ),
                        "move_stop_to_breakeven": tp_config.get(
                            "move_stop_to_breakeven", i == 1
                        ),
                    }
                )

        # Trailing stop
        self.trailing_stop_enabled = strategy_config.get("trailing_stop_enabled", True)
        self.trailing_stop_activation = Decimal(
            str(strategy_config.get("trailing_stop_activation", 50))
        )
        self.trailing_stop_distance = Decimal(
            str(strategy_config.get("trailing_stop_distance", 30))
        )
        self.trailing_stop_type = strategy_config.get(
            "trailing_stop_type", "pips"
        )  # pips, atr, percent

        # Time-based exits
        self.time_exit_enabled = strategy_config.get("time_exit_enabled", False)
        self.max_hold_hours = strategy_config.get("max_hold_hours", 72)
        self.weekend_exit_enabled = strategy_config.get("weekend_exit_enabled", True)

        # Risk-based exits
        self.daily_loss_limit = Decimal(
            str(strategy_config.get("daily_loss_limit", 0.05))
        )  # 5%
        self.drawdown_limit = Decimal(
            str(strategy_config.get("drawdown_limit", 0.10))
        )  # 10%

        # Dynamic adjustments
        self.adjust_stops_on_volatility = strategy_config.get(
            "adjust_stops_on_volatility", True
        )
        self.tighten_stops_on_news = strategy_config.get("tighten_stops_on_news", True)


class ExitStrategyManager:
    """Manages exit strategies and order placement."""

    def __init__(self):
        self.strategies: Dict[str, ExitStrategy] = {}
        self.position_strategies: Dict[str, str] = {}  # position_id -> strategy_id
        self.exit_orders: Dict[str, Dict[str, Any]] = {}  # position_id -> orders
        self.market_conditions: Dict[str, Any] = {}
        self._lock = asyncio.Lock()

        # Load default strategies
        self._load_default_strategies()

    async def initialize(self):
        """Initialize exit strategy manager."""
        logger.info("Exit Strategy Manager initialized")

    def _load_default_strategies(self):
        """Load default exit strategies."""
        # Conservative strategy
        self.strategies["conservative"] = ExitStrategy(
            {
                "strategy_id": "conservative",
                "name": "Conservative",
                "stop_loss_type": "fixed",
                "stop_loss_value": 30,
                "take_profit_1": {
                    "target": 50,
                    "exit_percent": 50,
                    "move_stop_to_breakeven": True,
                },
                "take_profit_2": {
                    "target": 100,
                    "exit_percent": 30,
                    "move_stop_to_breakeven": False,
                },
                "take_profit_3": {
                    "target": 150,
                    "exit_percent": 20,
                    "move_stop_to_breakeven": False,
                },
                "trailing_stop_enabled": True,
                "trailing_stop_activation": 50,
                "trailing_stop_distance": 20,
            }
        )

        # Aggressive strategy
        self.strategies["aggressive"] = ExitStrategy(
            {
                "strategy_id": "aggressive",
                "name": "Aggressive",
                "stop_loss_type": "atr",
                "stop_loss_atr_multiplier": 1.5,
                "take_profit_1": {
                    "target": 100,
                    "exit_percent": 30,
                    "move_stop_to_breakeven": True,
                },
                "take_profit_2": {
                    "target": 200,
                    "exit_percent": 30,
                    "move_stop_to_breakeven": False,
                },
                "take_profit_3": {
                    "target": 300,
                    "exit_percent": 40,
                    "move_stop_to_breakeven": False,
                },
                "trailing_stop_enabled": True,
                "trailing_stop_activation": 100,
                "trailing_stop_distance": 50,
                "trailing_stop_type": "atr",
            }
        )

        # Scalping strategy
        self.strategies["scalping"] = ExitStrategy(
            {
                "strategy_id": "scalping",
                "name": "Scalping",
                "stop_loss_type": "fixed",
                "stop_loss_value": 10,
                "take_profit_1": {
                    "target": 15,
                    "exit_percent": 100,
                    "move_stop_to_breakeven": False,
                },
                "trailing_stop_enabled": False,
                "time_exit_enabled": True,
                "max_hold_hours": 1,
            }
        )

    async def assign_strategy(
        self,
        position_id: str,
        strategy_id: Optional[str] = None,
        custom_config: Optional[Dict[str, Any]] = None,
    ) -> ExitStrategy:
        """Assign exit strategy to position."""
        async with self._lock:
            if custom_config:
                # Create custom strategy
                strategy = ExitStrategy(custom_config)
                self.strategies[f"custom_{position_id}"] = strategy
                self.position_strategies[position_id] = f"custom_{position_id}"
            else:
                # Use existing strategy
                strategy_id = strategy_id or "conservative"
                if strategy_id not in self.strategies:
                    strategy_id = "conservative"
                self.position_strategies[position_id] = strategy_id
                strategy = self.strategies[strategy_id]

            logger.info(
                f"Assigned strategy '{strategy.name}' to position {position_id}"
            )
            return strategy

    async def calculate_exit_levels(
        self,
        position_data: Dict[str, Any],
        market_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Decimal]:
        """Calculate exit levels for a position."""
        strategy_id = self.position_strategies.get(
            position_data["position_id"], "conservative"
        )
        strategy = self.strategies[strategy_id]

        entry_price = Decimal(str(position_data["entry_price"]))
        side = OrderSide(position_data["side"])
        symbol = position_data["symbol"]

        # Get ATR if needed
        atr = Decimal("0")
        if market_data and "atr" in market_data:
            atr = Decimal(str(market_data["atr"]))

        # Calculate stop loss
        if strategy.stop_loss_type == "fixed":
            sl_distance = self._pips_to_price(symbol, strategy.stop_loss_value)
        elif strategy.stop_loss_type == "atr" and atr > 0:
            sl_distance = atr * strategy.stop_loss_atr_multiplier
        elif strategy.stop_loss_type == "percent":
            sl_distance = entry_price * strategy.stop_loss_value / 100
        else:
            sl_distance = self._pips_to_price(symbol, 50)  # Default

        if side == OrderSide.BUY:
            stop_loss = entry_price - sl_distance
        else:
            stop_loss = entry_price + sl_distance

        levels = {"stop_loss": stop_loss}

        # Calculate take profit levels
        for tp in strategy.take_profit_levels:
            tp_distance = self._pips_to_price(symbol, tp["target"])
            if side == OrderSide.BUY:
                tp_price = entry_price + tp_distance
            else:
                tp_price = entry_price - tp_distance
            levels[f"take_profit_{tp['level']}"] = tp_price

        # Adjust for market conditions
        if strategy.adjust_stops_on_volatility and market_data:
            levels = await self._adjust_for_volatility(levels, market_data)

        return levels

    async def create_exit_orders(
        self,
        position_data: Dict[str, Any],
        exit_levels: Dict[str, Decimal],
        broker_adapter: Any,
    ) -> Dict[str, str]:
        """Create exit orders for a position."""
        position_id = position_data["position_id"]
        symbol = position_data["symbol"]
        side = OrderSide(position_data["side"])
        quantity = Decimal(str(position_data["quantity"]))

        strategy_id = self.position_strategies.get(position_id, "conservative")
        strategy = self.strategies[strategy_id]

        order_ids = {}

        # Create stop loss order
        if "stop_loss" in exit_levels:
            stop_side = OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY
            stop_order = BrokerMessageFactory.create_order_request(
                symbol=symbol,
                side=stop_side,
                quantity=quantity,
                order_type=OrderType.STOP,
                stop_price=exit_levels["stop_loss"],
                time_in_force=TimeInForce.GTC,
                metadata={"position_id": position_id, "exit_type": "stop_loss"},
            )

            response = await broker_adapter.place_order(stop_order)
            if response.status == "ACCEPTED":
                order_ids["stop_loss"] = response.broker_order_id
                logger.info(
                    f"Created stop loss order {response.broker_order_id} for position {position_id}"
                )

        # Create take profit orders
        remaining_quantity = quantity
        for tp in strategy.take_profit_levels:
            tp_key = f"take_profit_{tp['level']}"
            if tp_key in exit_levels and remaining_quantity > 0:
                tp_quantity = quantity * tp["exit_percent"] / 100
                tp_quantity = min(tp_quantity, remaining_quantity)

                tp_side = OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY
                tp_order = BrokerMessageFactory.create_order_request(
                    symbol=symbol,
                    side=tp_side,
                    quantity=tp_quantity,
                    order_type=OrderType.LIMIT,
                    price=exit_levels[tp_key],
                    time_in_force=TimeInForce.GTC,
                    metadata={
                        "position_id": position_id,
                        "exit_type": tp_key,
                        "exit_level": tp["level"],
                    },
                )

                response = await broker_adapter.place_order(tp_order)
                if response.status == "ACCEPTED":
                    order_ids[tp_key] = response.broker_order_id
                    remaining_quantity -= tp_quantity
                    logger.info(
                        f"Created {tp_key} order {response.broker_order_id} for position {position_id}"
                    )

        # Store exit orders
        async with self._lock:
            self.exit_orders[position_id] = {
                "order_ids": order_ids,
                "levels": exit_levels,
                "created_at": datetime.utcnow(),
            }

        return order_ids

    async def update_trailing_stop(
        self, position_data: Dict[str, Any], current_price: Decimal, broker_adapter: Any
    ) -> Optional[str]:
        """Update trailing stop for position."""
        position_id = position_data["position_id"]
        strategy_id = self.position_strategies.get(position_id, "conservative")
        strategy = self.strategies[strategy_id]

        if not strategy.trailing_stop_enabled:
            return None

        entry_price = Decimal(str(position_data["entry_price"]))
        side = OrderSide(position_data["side"])
        symbol = position_data["symbol"]

        # Check if trailing stop should be activated
        activation_distance = self._pips_to_price(
            symbol, strategy.trailing_stop_activation
        )

        if side == OrderSide.BUY:
            if current_price < entry_price + activation_distance:
                return None
        else:
            if current_price > entry_price - activation_distance:
                return None

        # Calculate new trailing stop level
        trail_distance = self._pips_to_price(symbol, strategy.trailing_stop_distance)

        if side == OrderSide.BUY:
            new_stop = current_price - trail_distance
            current_stop = Decimal(str(position_data.get("stop_loss", 0)))
            if new_stop <= current_stop:
                return None
        else:
            new_stop = current_price + trail_distance
            current_stop = Decimal(str(position_data.get("stop_loss", float("inf"))))
            if new_stop >= current_stop:
                return None

        # Get current stop order
        exit_info = self.exit_orders.get(position_id, {})
        stop_order_id = exit_info.get("order_ids", {}).get("stop_loss")

        if stop_order_id:
            # Modify existing stop order
            modify_request = BrokerMessageFactory.create_order_modify_request(
                broker_order_id=stop_order_id, stop_price=new_stop
            )

            response = await broker_adapter.modify_order(modify_request)
            if response.status == "MODIFIED":
                logger.info(
                    f"Updated trailing stop for position {position_id} to {new_stop}"
                )
                return stop_order_id

        return None

    async def check_time_exits(
        self, position_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[ExitReason]]:
        """Check if position should be exited based on time."""
        position_id = position_data["position_id"]
        strategy_id = self.position_strategies.get(position_id, "conservative")
        strategy = self.strategies[strategy_id]

        if not strategy.time_exit_enabled:
            return False, None

        # Check max hold time
        opened_at = position_data.get("opened_at")
        if opened_at:
            hold_time = datetime.utcnow() - opened_at
            if hold_time.total_seconds() / 3600 > strategy.max_hold_hours:
                return True, ExitReason.TIME_EXIT

        # Check weekend exit
        if strategy.weekend_exit_enabled:
            now = datetime.utcnow()
            # Friday after 16:00 UTC
            if now.weekday() == 4 and now.hour >= 16:
                return True, ExitReason.TIME_EXIT

        return False, None

    async def move_stop_to_breakeven(
        self, position_data: Dict[str, Any], broker_adapter: Any
    ) -> bool:
        """Move stop loss to breakeven."""
        position_id = position_data["position_id"]
        entry_price = Decimal(str(position_data["entry_price"]))

        # Add small buffer for spread/commission
        symbol = position_data["symbol"]
        buffer = self._pips_to_price(symbol, 2)

        side = OrderSide(position_data["side"])
        if side == OrderSide.BUY:
            breakeven_price = entry_price + buffer
        else:
            breakeven_price = entry_price - buffer

        # Get current stop order
        exit_info = self.exit_orders.get(position_id, {})
        stop_order_id = exit_info.get("order_ids", {}).get("stop_loss")

        if stop_order_id:
            modify_request = BrokerMessageFactory.create_order_modify_request(
                broker_order_id=stop_order_id, stop_price=breakeven_price
            )

            response = await broker_adapter.modify_order(modify_request)
            if response.status == "MODIFIED":
                logger.info(
                    f"Moved stop to breakeven for position {position_id} at {breakeven_price}"
                )
                return True

        return False

    async def cancel_exit_orders(
        self, position_id: str, broker_adapter: Any
    ) -> List[str]:
        """Cancel all exit orders for a position."""
        exit_info = self.exit_orders.get(position_id, {})
        order_ids = exit_info.get("order_ids", {})

        cancelled = []
        for exit_type, order_id in order_ids.items():
            response = await broker_adapter.cancel_order(order_id)
            if response.status in ["CANCELLED", "PENDING_CANCEL"]:
                cancelled.append(order_id)
                logger.info(
                    f"Cancelled {exit_type} order {order_id} for position {position_id}"
                )

        # Remove from tracking
        if position_id in self.exit_orders:
            del self.exit_orders[position_id]

        return cancelled

    async def get_exit_status(self, position_id: str) -> Dict[str, Any]:
        """Get exit order status for position."""
        exit_info = self.exit_orders.get(position_id, {})

        return {
            "position_id": position_id,
            "has_exits": bool(exit_info),
            "order_ids": exit_info.get("order_ids", {}),
            "levels": exit_info.get("levels", {}),
            "created_at": exit_info.get("created_at"),
            "strategy": self.position_strategies.get(position_id, "unknown"),
        }

    def _pips_to_price(self, symbol: str, pips: Decimal) -> Decimal:
        """Convert pips to price for a symbol."""
        # JPY pairs
        if "JPY" in symbol:
            return pips * Decimal("0.01")
        # Standard pairs
        else:
            return pips * Decimal("0.0001")

    async def _adjust_for_volatility(
        self, levels: Dict[str, Decimal], market_data: Dict[str, Any]
    ) -> Dict[str, Decimal]:
        """Adjust exit levels based on market volatility."""
        volatility_ratio = Decimal(str(market_data.get("volatility_ratio", 1.0)))

        if volatility_ratio > 1.5:
            # High volatility - widen stops
            multiplier = Decimal("1.2")
        elif volatility_ratio < 0.7:
            # Low volatility - tighten stops
            multiplier = Decimal("0.8")
        else:
            return levels

        # Adjust levels (implementation simplified)
        # In production, this would be more sophisticated
        return levels
