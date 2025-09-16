"""
WebSocket Service for FXML4 API.

This service provides real-time market data and trading updates via WebSocket.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import redis.asyncio as redis
from fastapi import WebSocket, WebSocketDisconnect

from fxml4.api.services.market_data import market_data_service
from fxml4.config import get_config

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and message broadcasting."""

    def __init__(self):
        # Active connections by connection ID
        self.connections: Dict[str, WebSocket] = {}
        # Subscriptions: connection_id -> set of subscription keys
        self.subscriptions: Dict[str, Set[str]] = {}
        # Reverse mapping: subscription_key -> set of connection_ids
        self.subscribers: Dict[str, Set[str]] = {}
        self.redis_client: Optional[redis.Redis] = None

    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.connections[client_id] = websocket
        self.subscriptions[client_id] = set()
        logger.info(
            f"Client {client_id} connected. Total connections: {len(self.connections)}"
        )

        # Initialize Redis connection if not already done
        if self.redis_client is None:
            await self._init_redis()

    async def disconnect(self, client_id: str):
        """Handle client disconnection."""
        if client_id in self.connections:
            # Remove all subscriptions for this client
            if client_id in self.subscriptions:
                for sub_key in self.subscriptions[client_id]:
                    if sub_key in self.subscribers:
                        self.subscribers[sub_key].discard(client_id)
                        if not self.subscribers[sub_key]:
                            del self.subscribers[sub_key]
                del self.subscriptions[client_id]

            del self.connections[client_id]
            logger.info(
                f"Client {client_id} disconnected. Total connections: {len(self.connections)}"
            )

    async def subscribe(self, client_id: str, subscription_key: str):
        """Subscribe a client to a data stream."""
        if client_id in self.subscriptions:
            self.subscriptions[client_id].add(subscription_key)

            if subscription_key not in self.subscribers:
                self.subscribers[subscription_key] = set()
            self.subscribers[subscription_key].add(client_id)

            logger.info(f"Client {client_id} subscribed to {subscription_key}")

            # Send confirmation
            await self.send_personal_message(
                client_id,
                {
                    "type": "subscription_confirmed",
                    "subscription": subscription_key,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

    async def unsubscribe(self, client_id: str, subscription_key: str):
        """Unsubscribe a client from a data stream."""
        if client_id in self.subscriptions:
            self.subscriptions[client_id].discard(subscription_key)

        if subscription_key in self.subscribers:
            self.subscribers[subscription_key].discard(client_id)
            if not self.subscribers[subscription_key]:
                del self.subscribers[subscription_key]

        logger.info(f"Client {client_id} unsubscribed from {subscription_key}")

        # Send confirmation
        await self.send_personal_message(
            client_id,
            {
                "type": "unsubscription_confirmed",
                "subscription": subscription_key,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    async def send_personal_message(self, client_id: str, message: dict):
        """Send a message to a specific client."""
        if client_id in self.connections:
            try:
                await self.connections[client_id].send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending message to {client_id}: {e}")
                await self.disconnect(client_id)

    async def broadcast_to_subscribers(self, subscription_key: str, message: dict):
        """Broadcast a message to all subscribers of a specific key."""
        if subscription_key in self.subscribers:
            disconnected_clients = []

            for client_id in self.subscribers[subscription_key]:
                try:
                    if client_id in self.connections:
                        await self.connections[client_id].send_text(json.dumps(message))
                except Exception as e:
                    logger.error(f"Error broadcasting to {client_id}: {e}")
                    disconnected_clients.append(client_id)

            # Clean up disconnected clients
            for client_id in disconnected_clients:
                await self.disconnect(client_id)

    async def _init_redis(self):
        """Initialize Redis connection for pub/sub."""
        try:
            config = get_config()
            redis_config = config.get("redis", {})

            self.redis_client = redis.Redis(
                host=redis_config.get("host", "localhost"),
                port=redis_config.get("port", 6379),
                db=redis_config.get("db", 0),
                decode_responses=True,
            )

            # Test connection
            await self.redis_client.ping()
            logger.info("Redis connection established for WebSocket service")

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None


class WebSocketService:
    """Main WebSocket service for handling real-time data streams."""

    def __init__(self):
        self.manager = ConnectionManager()
        self._background_tasks: Set[asyncio.Task] = set()

    async def start_background_tasks(self):
        """Start background tasks for data streaming."""
        # Start market data streaming task
        task = asyncio.create_task(self._stream_market_data())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        logger.info("WebSocket background tasks started")

    async def stop_background_tasks(self):
        """Stop all background tasks."""
        for task in self._background_tasks:
            task.cancel()

        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)

        logger.info("WebSocket background tasks stopped")

    async def handle_client_message(self, client_id: str, message: dict):
        """Handle incoming messages from clients."""
        try:
            message_type = message.get("type")

            if message_type == "subscribe":
                subscription = message.get("subscription")
                if subscription:
                    await self.manager.subscribe(client_id, subscription)

            elif message_type == "unsubscribe":
                subscription = message.get("subscription")
                if subscription:
                    await self.manager.unsubscribe(client_id, subscription)

            elif message_type == "ping":
                await self.manager.send_personal_message(
                    client_id,
                    {"type": "pong", "timestamp": datetime.utcnow().isoformat()},
                )

            elif message_type == "get_symbols":
                symbols = await market_data_service.get_available_symbols()
                await self.manager.send_personal_message(
                    client_id,
                    {
                        "type": "symbols",
                        "data": symbols,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )

            elif message_type == "get_latest_tick":
                symbol = message.get("symbol")
                if symbol:
                    tick_data = await market_data_service.get_latest_tick(symbol)
                    await self.manager.send_personal_message(
                        client_id,
                        {
                            "type": "tick_data",
                            "symbol": symbol,
                            "data": tick_data,
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    )

            else:
                await self.manager.send_personal_message(
                    client_id,
                    {
                        "type": "error",
                        "message": f"Unknown message type: {message_type}",
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )

        except Exception as e:
            logger.error(f"Error handling client message: {e}")
            await self.manager.send_personal_message(
                client_id,
                {
                    "type": "error",
                    "message": "Internal server error",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

    async def _stream_market_data(self):
        """Background task to stream market data updates."""
        while True:
            try:
                # Get active subscriptions
                active_symbols = set()
                for subscription_key in self.manager.subscribers:
                    if subscription_key.startswith(
                        "tick:"
                    ) or subscription_key.startswith("ohlcv:"):
                        symbol = subscription_key.split(":", 1)[1]
                        active_symbols.add(symbol)

                # Stream tick data for subscribed symbols
                for symbol in active_symbols:
                    try:
                        tick_data = await market_data_service.get_latest_tick(symbol)
                        if tick_data:
                            # Broadcast to tick subscribers
                            await self.manager.broadcast_to_subscribers(
                                f"tick:{symbol}",
                                {
                                    "type": "tick_update",
                                    "symbol": symbol,
                                    "data": tick_data,
                                    "timestamp": datetime.utcnow().isoformat(),
                                },
                            )
                    except Exception as e:
                        logger.error(f"Error streaming data for {symbol}: {e}")

                # Wait before next update
                await asyncio.sleep(1.0)  # 1 second updates

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in market data streaming task: {e}")
                await asyncio.sleep(5.0)  # Wait before retrying

    async def connect_client(self, websocket: WebSocket, client_id: str):
        """Connect a new WebSocket client."""
        await self.manager.connect(websocket, client_id)

    async def disconnect_client(self, client_id: str):
        """Disconnect a WebSocket client."""
        await self.manager.disconnect(client_id)

    async def handle_websocket(self, websocket: WebSocket, client_id: str):
        """Main WebSocket connection handler."""
        await self.connect_client(websocket, client_id)

        try:
            # Send welcome message
            await self.manager.send_personal_message(
                client_id,
                {
                    "type": "welcome",
                    "message": "Connected to FXML4 WebSocket",
                    "client_id": client_id,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

            while True:
                # Wait for messages from client
                data = await websocket.receive_text()

                try:
                    message = json.loads(data)
                    await self.handle_client_message(client_id, message)
                except json.JSONDecodeError:
                    await self.manager.send_personal_message(
                        client_id,
                        {
                            "type": "error",
                            "message": "Invalid JSON format",
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    )

        except WebSocketDisconnect:
            logger.info(f"Client {client_id} disconnected")
        except Exception as e:
            logger.error(f"Error in WebSocket handler: {e}")
        finally:
            await self.disconnect_client(client_id)


# Global service instance
websocket_service = WebSocketService()
