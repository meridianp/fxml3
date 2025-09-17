"""
Trading Event Integration for FXML4

Integrates WebSocket service with trading components for real-time events.
"""

import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from core.services.websocket_service import WebSocketServer
from core.trading.execution import ExecutionEngine
from core.trading.orders import OrderManager, OrderState
from core.trading.positions import PositionManager


class TradingEventBroadcaster:
    """Broadcasts trading events through WebSocket."""

    def __init__(
        self,
        websocket_server: WebSocketServer,
        order_manager: Optional[OrderManager] = None,
        position_manager: Optional[PositionManager] = None,
        execution_engine: Optional[ExecutionEngine] = None,
    ):
        """Initialize trading event broadcaster."""
        self.ws_server = websocket_server
        self.order_manager = order_manager
        self.position_manager = position_manager
        self.execution_engine = execution_engine

        # Register event hooks
        self._register_hooks()

    def _register_hooks(self):
        """Register hooks with trading components."""
        if self.order_manager:
            # Hook into order state changes
            self.order_manager.add_state_change_callback(self._on_order_state_change)

        if self.position_manager:
            # Hook into position updates
            self.position_manager.add_update_callback(self._on_position_update)

        if self.execution_engine:
            # Hook into execution events
            self.execution_engine.add_fill_callback(self._on_order_fill)

    async def _on_order_state_change(self, order_id: str, old_state: OrderState, new_state: OrderState, order_data: Dict[str, Any]):
        """Handle order state change event."""
        event_data = {
            "order_id": order_id,
            "symbol": order_data.get("symbol"),
            "side": order_data.get("side"),
            "quantity": order_data.get("quantity"),
            "old_status": old_state.value if old_state else None,
            "status": new_state.value,
            "timestamp": datetime.now().isoformat(),
        }

        # Add additional fields based on state
        if new_state == OrderState.FILLED:
            event_data["filled_quantity"] = order_data.get("filled_quantity")
            event_data["average_price"] = float(order_data.get("average_fill_price", 0))

        await self.ws_server.broadcast_order_update(event_data)

    async def _on_position_update(self, position_id: str, position_data: Dict[str, Any]):
        """Handle position update event."""
        event_data = {
            "position_id": position_id,
            "symbol": position_data.get("symbol"),
            "quantity": position_data.get("quantity"),
            "entry_price": float(position_data.get("entry_price", 0)),
            "current_price": float(position_data.get("current_price", 0)),
            "unrealized_pnl": float(position_data.get("unrealized_pnl", 0)),
            "realized_pnl": float(position_data.get("realized_pnl", 0)),
            "is_open": position_data.get("is_open", True),
            "timestamp": datetime.now().isoformat(),
        }

        symbol = position_data.get("symbol")
        await self.ws_server.broadcast_position_update(symbol, event_data)

    async def _on_order_fill(self, order_id: str, fill_data: Dict[str, Any]):
        """Handle order fill event."""
        event_data = {
            "order_id": order_id,
            "symbol": fill_data.get("symbol"),
            "status": "FILLED",
            "filled_quantity": fill_data.get("quantity"),
            "fill_price": float(fill_data.get("price", 0)),
            "commission": float(fill_data.get("commission", 0)),
            "timestamp": datetime.now().isoformat(),
            "execution_id": fill_data.get("execution_id"),
        }

        await self.ws_server.broadcast_order_update(event_data)

    async def broadcast_market_tick(self, symbol: str, bid: Decimal, ask: Decimal, last: Decimal, volume: int):
        """Broadcast market data tick."""
        market_data = {
            "symbol": symbol,
            "bid": float(bid),
            "ask": float(ask),
            "last": float(last),
            "volume": volume,
            "spread": float(ask - bid),
            "timestamp": datetime.now().isoformat(),
        }

        await self.ws_server.broadcast_market_data(symbol, market_data)

    async def broadcast_risk_alert(self, alert_data: Dict[str, Any]):
        """Broadcast risk management alert."""
        message = {
            "event_type": "risk_alert",
            "timestamp": datetime.now().isoformat(),
            "data": alert_data,
        }

        # Broadcast to all clients (important alerts)
        await self.ws_server.broadcast_to_all(message)

    async def broadcast_system_status(self, status: str, details: Optional[Dict[str, Any]] = None):
        """Broadcast system status update."""
        message = {
            "event_type": "system_status",
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "details": details or {},
        }

        await self.ws_server.broadcast_to_all(message)


class EnhancedOrderManager(OrderManager):
    """OrderManager with WebSocket event support."""

    def __init__(self, ws_server: Optional[WebSocketServer] = None, **kwargs):
        """Initialize enhanced order manager."""
        super().__init__(**kwargs)
        self.ws_server = ws_server
        self.state_change_callbacks = []

    def add_state_change_callback(self, callback):
        """Add callback for state changes."""
        self.state_change_callbacks.append(callback)

    async def update_order_state(self, order_id: str, new_state: OrderState, **kwargs):
        """Update order state with WebSocket broadcast."""
        order = self.orders.get(order_id)
        if not order:
            return None

        old_state = order.state
        result = await super().update_order_state(order_id, new_state, **kwargs)

        # Broadcast state change
        if self.ws_server and old_state != new_state:
            order_data = order.to_dict()
            await self.ws_server.broadcast_order_update(order_data)

        # Call registered callbacks
        for callback in self.state_change_callbacks:
            if asyncio.iscoroutinefunction(callback):
                await callback(order_id, old_state, new_state, order_data)
            else:
                callback(order_id, old_state, new_state, order_data)

        return result


class EnhancedPositionManager(PositionManager):
    """PositionManager with WebSocket event support."""

    def __init__(self, ws_server: Optional[WebSocketServer] = None, **kwargs):
        """Initialize enhanced position manager."""
        super().__init__(**kwargs)
        self.ws_server = ws_server
        self.update_callbacks = []

    def add_update_callback(self, callback):
        """Add callback for position updates."""
        self.update_callbacks.append(callback)

    async def update_position_from_order(self, position_id: str, order):
        """Update position with WebSocket broadcast."""
        result = await super().update_position_from_order(position_id, order)

        if self.ws_server and result:
            position_data = result.to_dict()
            await self.ws_server.broadcast_position_update(
                result.symbol, position_data
            )

        # Call registered callbacks
        for callback in self.update_callbacks:
            if asyncio.iscoroutinefunction(callback):
                await callback(position_id, position_data)
            else:
                callback(position_id, position_data)

        return result


class EnhancedExecutionEngine(ExecutionEngine):
    """ExecutionEngine with WebSocket event support."""

    def __init__(self, ws_server: Optional[WebSocketServer] = None, **kwargs):
        """Initialize enhanced execution engine."""
        super().__init__(**kwargs)
        self.ws_server = ws_server
        self.fill_callbacks = []

    def add_fill_callback(self, callback):
        """Add callback for order fills."""
        self.fill_callbacks.append(callback)

    async def handle_fill(self, order, fill: Dict[str, Any]):
        """Handle fill with WebSocket broadcast."""
        await super().handle_fill(order, fill)

        if self.ws_server:
            fill_data = {
                "order_id": order.order_id,
                "symbol": order.symbol,
                "quantity": fill["quantity"],
                "price": fill["price"],
                "commission": fill.get("commission", 0),
                "execution_id": fill.get("execution_id"),
            }

            await self.ws_server.broadcast_order_update({
                "order_id": order.order_id,
                "status": "FILL",
                **fill_data,
            })

        # Call registered callbacks
        for callback in self.fill_callbacks:
            if asyncio.iscoroutinefunction(callback):
                await callback(order.order_id, fill)
            else:
                callback(order.order_id, fill)


class MarketDataStreamer:
    """Streams market data through WebSocket."""

    def __init__(self, ws_server: WebSocketServer, data_provider=None):
        """Initialize market data streamer."""
        self.ws_server = ws_server
        self.data_provider = data_provider
        self.active_streams: Dict[str, asyncio.Task] = {}

    async def start_streaming(self, symbol: str, interval: float = 1.0):
        """Start streaming market data for a symbol."""
        if symbol in self.active_streams:
            return  # Already streaming

        async def stream_loop():
            """Main streaming loop."""
            while True:
                try:
                    # Get market data from provider
                    if self.data_provider:
                        data = await self.data_provider.get_quote(symbol)
                    else:
                        # Mock data for testing
                        import random
                        base_price = 1.0850
                        data = {
                            "bid": base_price + random.uniform(-0.001, 0.001),
                            "ask": base_price + random.uniform(0, 0.002),
                            "last": base_price + random.uniform(-0.0005, 0.0015),
                            "volume": random.randint(100000, 500000),
                        }

                    # Broadcast to subscribers
                    await self.ws_server.broadcast_market_data(symbol, data)

                    await asyncio.sleep(interval)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    print(f"Error streaming {symbol}: {e}")
                    await asyncio.sleep(interval * 2)  # Back off on error

        # Start streaming task
        task = asyncio.create_task(stream_loop())
        self.active_streams[symbol] = task

    async def stop_streaming(self, symbol: str):
        """Stop streaming market data for a symbol."""
        if symbol in self.active_streams:
            self.active_streams[symbol].cancel()
            del self.active_streams[symbol]

    async def stop_all_streams(self):
        """Stop all active streams."""
        for task in self.active_streams.values():
            task.cancel()
        self.active_streams.clear()