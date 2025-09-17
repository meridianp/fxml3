"""
WebSocket Service for FXML4

TDD-driven implementation of WebSocket server for real-time communication.
Following Green phase - minimal implementation to pass tests.
"""

import asyncio
import json
import time
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import websockets
from websockets.legacy.server import WebSocketServerProtocol


def validate_jwt(token: str) -> Dict[str, Any]:
    """Validate JWT token (mock implementation)."""
    # In production, this would validate against real JWT
    if token == "valid_jwt_token":
        return {"user_id": "user123", "valid": True}
    return {"valid": False}


class WebSocketServer:
    """WebSocket server for real-time event broadcasting."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8765,
        rate_limit: int = 100,
        max_subscriptions: int = 50,
    ):
        """Initialize WebSocket server."""
        self.host = host
        self.port = port
        self.clients: Dict[str, Dict[str, Any]] = {}
        self.is_running = False
        self.server = None

        # Subscription management
        self.subscriptions: Dict[str, Dict[str, Set[str]]] = defaultdict(
            lambda: defaultdict(set)
        )

        # Rate limiting
        self.rate_limit = rate_limit  # Messages per second
        self.max_subscriptions = max_subscriptions
        self.client_message_counts: Dict[str, List[float]] = defaultdict(list)

        # Session management
        self.sessions: Dict[str, Dict[str, Any]] = {}

        # Market data streams
        self.market_streams: Dict[str, asyncio.Task] = {}

    async def start(self):
        """Start the WebSocket server."""
        self.server = await websockets.serve(
            self.handle_connection, self.host, self.port
        )
        self.is_running = True

    async def stop(self):
        """Stop the WebSocket server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        self.is_running = False

    async def handle_connection(
        self, websocket: WebSocketServerProtocol, path: str
    ):
        """Handle a new WebSocket connection."""
        client_id = await self.handle_client_connection(websocket)

        try:
            async for message in websocket:
                await self.handle_client_message(client_id, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.handle_client_disconnection(client_id)

    async def handle_client_connection(
        self, websocket: WebSocketServerProtocol
    ) -> str:
        """Handle new client connection."""
        client_id = str(uuid.uuid4())

        self.clients[client_id] = {
            "websocket": websocket,
            "authenticated": False,
            "user_id": None,
            "connected_at": datetime.now(),
            "subscriptions": set(),
        }

        return client_id

    async def handle_client_disconnection(self, client_id: str):
        """Handle client disconnection."""
        if client_id in self.clients:
            # Remove from all subscriptions
            for channel in list(self.subscriptions.keys()):
                for symbol in list(self.subscriptions[channel].keys()):
                    self.subscriptions[channel][symbol].discard(client_id)

            # Remove client
            del self.clients[client_id]

    async def handle_client_message(self, client_id: str, message: str):
        """Handle incoming message from client."""
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "auth":
                await self.authenticate_client(client_id, data)
            elif msg_type == "subscribe":
                self.handle_subscription(client_id, data)
            elif msg_type == "unsubscribe":
                self.handle_unsubscription(client_id, data)

        except json.JSONDecodeError:
            await self.send_error(client_id, "Invalid JSON")
        except Exception as e:
            await self.send_error(client_id, str(e))

    async def authenticate_client(
        self, client_id: str, auth_data: Dict[str, Any]
    ) -> bool:
        """Authenticate a client connection."""
        token = auth_data.get("token")

        if not token:
            return False

        # Validate JWT token
        validation_result = validate_jwt(token)

        if validation_result.get("valid"):
            self.clients[client_id]["authenticated"] = True
            self.clients[client_id]["user_id"] = validation_result.get("user_id")
            return True

        return False

    def handle_subscription(self, client_id: str, data: Dict[str, Any]):
        """Handle subscription request."""
        channel = data.get("channel")
        symbol = data.get("symbol", "*")

        self.add_subscription(client_id, channel, symbol)

    def handle_unsubscription(self, client_id: str, data: Dict[str, Any]):
        """Handle unsubscription request."""
        channel = data.get("channel")
        symbol = data.get("symbol", "*")

        self.remove_subscription(client_id, channel, symbol)

    def add_subscription(
        self, client_id: str, channel: str, symbol: str
    ) -> bool:
        """Add a subscription for a client."""
        if client_id not in self.clients:
            return False

        # Check subscription limit
        client_subs = self.clients[client_id]["subscriptions"]
        if len(client_subs) >= self.max_subscriptions:
            return False

        self.subscriptions[channel][symbol].add(client_id)
        client_subs.add(f"{channel}:{symbol}")
        return True

    def remove_subscription(self, client_id: str, channel: str, symbol: str):
        """Remove a subscription for a client."""
        if client_id in self.subscriptions[channel][symbol]:
            self.subscriptions[channel][symbol].remove(client_id)
            if client_id in self.clients:
                self.clients[client_id]["subscriptions"].discard(
                    f"{channel}:{symbol}"
                )

    def get_subscribers(self, channel: str, symbol: str) -> Set[str]:
        """Get subscribers for a channel and symbol."""
        subscribers = set()

        # Direct subscribers
        subscribers.update(self.subscriptions[channel][symbol])

        # Wildcard subscribers
        subscribers.update(self.subscriptions[channel]["*"])

        return subscribers

    async def broadcast_to_all(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients."""
        message_str = json.dumps(message)
        tasks = []

        for client_id, client_info in self.clients.items():
            ws = client_info["websocket"]
            if not ws.closed:
                tasks.append(ws.send(message_str))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def broadcast_to_channel(
        self, channel: str, symbol: str, message: Dict[str, Any]
    ):
        """Broadcast message to channel subscribers."""
        subscribers = self.get_subscribers(channel, symbol)
        message_str = json.dumps(message)
        tasks = []

        for client_id in subscribers:
            if client_id in self.clients:
                ws = self.clients[client_id]["websocket"]
                if not ws.closed:
                    tasks.append(ws.send(message_str))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def broadcast_order_update(self, order_data: Dict[str, Any]):
        """Broadcast order update event."""
        message = {
            "event_type": "order_update",
            "timestamp": datetime.now().isoformat(),
            "data": order_data,
        }

        symbol = order_data.get("symbol", "*")
        await self.broadcast_to_channel("orders", symbol, message)

    async def broadcast_position_update(
        self, symbol: str, position_data: Dict[str, Any]
    ):
        """Broadcast position update event."""
        message = {
            "event_type": "position_update",
            "timestamp": datetime.now().isoformat(),
            "data": position_data,
        }

        await self.broadcast_to_channel("positions", symbol, message)

    async def broadcast_market_data(
        self, symbol: str, market_data: Dict[str, Any]
    ):
        """Broadcast market data update."""
        message = {
            "event_type": "market_data",
            "timestamp": datetime.now().isoformat(),
            "data": market_data,
        }

        await self.broadcast_to_channel("market_data", symbol, message)

    async def send_to_client(
        self, client_id: str, message: Dict[str, Any]
    ) -> bool:
        """Send message to specific client."""
        if client_id not in self.clients:
            return False

        try:
            ws = self.clients[client_id]["websocket"]
            if not ws.closed:
                await ws.send(json.dumps(message))
                return True
            else:
                # Remove disconnected client
                await self.handle_client_disconnection(client_id)
                return False
        except Exception:
            # Remove client on error
            await self.handle_client_disconnection(client_id)
            return False

    async def send_error(self, client_id: str, error_message: str):
        """Send error message to client."""
        message = {
            "type": "error",
            "message": error_message,
            "timestamp": datetime.now().isoformat(),
        }
        await self.send_to_client(client_id, message)

    async def check_rate_limit(self, client_id: str) -> bool:
        """Check if client is within rate limit."""
        now = time.time()
        message_times = self.client_message_counts[client_id]

        # Remove old messages (older than 1 second)
        message_times[:] = [t for t in message_times if now - t < 1.0]

        # Check if within limit
        if len(message_times) >= self.rate_limit:
            return False

        # Add current message time
        message_times.append(now)
        return True

    async def create_session(self, client_id: str) -> str:
        """Create a session for reconnection."""
        if client_id not in self.clients:
            return None

        session_token = str(uuid.uuid4())
        self.sessions[session_token] = {
            "client_id": client_id,
            "user_id": self.clients[client_id].get("user_id"),
            "subscriptions": self.clients[client_id].get("subscriptions", set()).copy(),
            "created_at": datetime.now(),
        }

        return session_token

    async def handle_reconnection(
        self, websocket: WebSocketServerProtocol, session_token: str
    ) -> str:
        """Handle client reconnection with session recovery."""
        if session_token not in self.sessions:
            return None

        session = self.sessions[session_token]

        # Create new client connection
        new_client_id = await self.handle_client_connection(websocket)

        # Restore session data
        self.clients[new_client_id]["authenticated"] = True
        self.clients[new_client_id]["user_id"] = session["user_id"]

        # Restore subscriptions
        for sub in session["subscriptions"]:
            channel, symbol = sub.split(":", 1)
            self.add_subscription(new_client_id, channel, symbol)

        # Clean up session
        del self.sessions[session_token]

        return new_client_id

    async def start_market_data_stream(
        self, symbol: str, interval: float = 1.0
    ) -> asyncio.Task:
        """Start streaming market data for a symbol."""

        async def stream_market_data():
            """Stream market data at regular intervals."""
            while True:
                # Generate mock market data
                market_data = {
                    "symbol": symbol,
                    "bid": 1.0849 + (time.time() % 10) / 10000,
                    "ask": 1.0851 + (time.time() % 10) / 10000,
                    "last": 1.0850 + (time.time() % 10) / 10000,
                    "volume": int(100000 + (time.time() % 50000)),
                }

                await self.broadcast_market_data(symbol, market_data)
                await asyncio.sleep(interval)

        # Start streaming task
        task = asyncio.create_task(stream_market_data())
        self.market_streams[symbol] = task
        return task

    async def stop_market_data_stream(self, symbol: str):
        """Stop streaming market data for a symbol."""
        if symbol in self.market_streams:
            self.market_streams[symbol].cancel()
            del self.market_streams[symbol]

    def get_server_stats(self) -> Dict[str, Any]:
        """Get server statistics."""
        total_subscriptions = sum(
            len(subs)
            for channel in self.subscriptions.values()
            for subs in channel.values()
        )

        return {
            "connected_clients": len(self.clients),
            "authenticated_clients": sum(
                1 for c in self.clients.values() if c["authenticated"]
            ),
            "total_subscriptions": total_subscriptions,
            "active_sessions": len(self.sessions),
            "active_streams": len(self.market_streams),
            "is_running": self.is_running,
        }