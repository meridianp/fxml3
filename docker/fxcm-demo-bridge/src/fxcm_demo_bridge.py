#!/usr/bin/env python3
"""FXCM Demo Bridge Service.

Containerized service that bridges FXCM demo account with FXML4
via the existing ForexConnect infrastructure using RabbitMQ messaging.
"""

import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
import pika
import redis
import websockets
import yaml
from aiohttp import web


class FXCMDemoBridge:
    """FXCM Demo Account Bridge Service."""

    def __init__(self):
        """Initialize FXCM demo bridge."""
        self.config = self.load_config()
        self.setup_logging()

        # Connection states
        self.fxcm_connected = False
        self.rabbitmq_connected = False
        self.redis_connected = False

        # Service components
        self.app = None
        self.websocket_server = None
        self.rabbitmq_connection = None
        self.redis_client = None

        # Demo account data
        self.demo_credentials = {
            "username": "0x0c9@quatumchain.com",
            "password": "QkPh4%mVHKQ6Li",
            "server": "FXCM-USDDemo1",
        }

        # Mock account state (would be real FXCM data in production)
        self.account_state = {
            "account_id": "FXCM_DEMO_001",
            "balance": 50000.00,
            "equity": 50000.00,
            "margin_used": 0.00,
            "margin_available": 50000.00,
            "unrealized_pl": 0.00,
            "currency": "USD",
            "connected": False,
        }

        self.positions = {}
        self.market_prices = {
            "EURUSD": {"bid": 1.0850, "ask": 1.0852},
            "GBPUSD": {"bid": 1.2720, "ask": 1.2722},
            "USDJPY": {"bid": 149.85, "ask": 149.87},
        }

        self.websocket_clients = set()
        self.running = False

        self.logger.info("FXCM Demo Bridge initialized")

    def load_config(self) -> Dict[str, Any]:
        """Load configuration."""
        config_path = Path("/app/config/bridge_config.yaml")
        if config_path.exists():
            with open(config_path) as f:
                return yaml.safe_load(f)

        # Default configuration
        return {
            "api": {"host": "0.0.0.0", "port": 8080},
            "websocket": {"host": "0.0.0.0", "port": 8081},
            "rabbitmq": {
                "host": os.getenv("RABBITMQ_HOST", "rabbitmq"),
                "port": int(os.getenv("RABBITMQ_PORT", 5672)),
                "username": os.getenv("RABBITMQ_USER", "guest"),
                "password": os.getenv("RABBITMQ_PASS", "guest"),
            },
            "redis": {
                "host": os.getenv("REDIS_HOST", "redis"),
                "port": int(os.getenv("REDIS_PORT", 6379)),
                "db": int(os.getenv("REDIS_DB", 0)),
            },
            "fxcm": {
                "demo_mode": True,
                "update_interval": 1.0,
                "symbols": ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD"],
            },
        }

    def setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler("/app/logs/fxcm_demo_bridge.log"),
            ],
        )
        self.logger = logging.getLogger(__name__)

    async def start(self):
        """Start the FXCM demo bridge service."""
        self.logger.info("Starting FXCM Demo Bridge Service...")
        self.running = True

        # Setup signal handlers
        for sig in [signal.SIGTERM, signal.SIGINT]:
            signal.signal(sig, self._signal_handler)

        try:
            # Initialize connections
            await self.connect_redis()
            await self.connect_rabbitmq()
            await self.simulate_fxcm_connection()

            # Start services
            await asyncio.gather(
                self.start_http_api(),
                self.start_websocket_server(),
                self.start_market_data_publisher(),
                self.start_account_monitor(),
                self.process_rabbitmq_messages(),
            )

        except Exception as e:
            self.logger.error(f"Error starting bridge service: {e}")
            await self.shutdown()

    async def connect_redis(self):
        """Connect to Redis."""
        try:
            self.redis_client = redis.Redis(
                host=self.config["redis"]["host"],
                port=self.config["redis"]["port"],
                db=self.config["redis"]["db"],
                decode_responses=True,
            )

            # Test connection
            await asyncio.get_event_loop().run_in_executor(None, self.redis_client.ping)

            self.redis_connected = True
            self.logger.info("Connected to Redis")

        except Exception as e:
            self.logger.error(f"Redis connection failed: {e}")

    async def connect_rabbitmq(self):
        """Connect to RabbitMQ."""
        try:
            credentials = pika.PlainCredentials(
                self.config["rabbitmq"]["username"], self.config["rabbitmq"]["password"]
            )

            parameters = pika.ConnectionParameters(
                host=self.config["rabbitmq"]["host"],
                port=self.config["rabbitmq"]["port"],
                credentials=credentials,
            )

            self.rabbitmq_connection = pika.BlockingConnection(parameters)
            channel = self.rabbitmq_connection.channel()

            # Declare exchanges and queues for FXML4 integration
            channel.exchange_declare(exchange="fxcm.market_data", exchange_type="topic")
            channel.exchange_declare(
                exchange="fxcm.account_updates", exchange_type="topic"
            )
            channel.exchange_declare(exchange="fxcm.orders", exchange_type="direct")

            # Declare queues
            channel.queue_declare(queue="fxcm.prices", durable=True)
            channel.queue_declare(queue="fxcm.account", durable=True)
            channel.queue_declare(queue="fxcm.positions", durable=True)
            channel.queue_declare(queue="fxml4.orders", durable=True)

            # Bind queues
            channel.queue_bind(
                exchange="fxcm.market_data", queue="fxcm.prices", routing_key="price.*"
            )
            channel.queue_bind(
                exchange="fxcm.account_updates",
                queue="fxcm.account",
                routing_key="account.*",
            )
            channel.queue_bind(
                exchange="fxcm.account_updates",
                queue="fxcm.positions",
                routing_key="position.*",
            )

            self.rabbitmq_connected = True
            self.logger.info("Connected to RabbitMQ")

        except Exception as e:
            self.logger.error(f"RabbitMQ connection failed: {e}")

    async def simulate_fxcm_connection(self):
        """Simulate FXCM demo connection."""
        self.logger.info(
            f"Simulating FXCM connection to {self.demo_credentials['server']}"
        )
        self.logger.info(f"Demo account: {self.demo_credentials['username']}")

        # Simulate connection delay
        await asyncio.sleep(2)

        self.fxcm_connected = True
        self.account_state["connected"] = True
        self.account_state["last_update"] = datetime.utcnow().isoformat()

        self.logger.info("FXCM demo connection established")

    async def start_http_api(self):
        """Start HTTP API server."""
        self.app = web.Application()

        # API routes
        self.app.router.add_get("/health", self.health_check)
        self.app.router.add_get("/account", self.get_account_info)
        self.app.router.add_get("/positions", self.get_positions)
        self.app.router.add_get("/prices", self.get_market_prices)
        self.app.router.add_post("/orders", self.place_order)
        self.app.router.add_delete("/positions/{position_id}", self.close_position)
        self.app.router.add_get("/status", self.get_bridge_status)

        # CORS middleware
        self.app.middlewares.append(self.cors_middleware)

        runner = web.AppRunner(self.app)
        await runner.setup()

        site = web.TCPSite(
            runner, self.config["api"]["host"], self.config["api"]["port"]
        )
        await site.start()

        self.logger.info(
            f"HTTP API started on {self.config['api']['host']}:{self.config['api']['port']}"
        )

    async def cors_middleware(self, request, handler):
        """CORS middleware for API requests."""
        response = await handler(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PUT, DELETE, OPTIONS"
        )
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response

    async def start_websocket_server(self):
        """Start WebSocket server for real-time updates."""

        async def websocket_handler(websocket, path):
            self.websocket_clients.add(websocket)
            self.logger.info(f"WebSocket client connected: {websocket.remote_address}")

            try:
                # Send initial data
                await self.send_to_websocket(
                    websocket,
                    {
                        "type": "welcome",
                        "message": "Connected to FXCM Demo Bridge",
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )

                # Keep connection alive
                async for message in websocket:
                    # Handle client messages if needed
                    try:
                        data = json.loads(message)
                        await self.handle_websocket_message(websocket, data)
                    except json.JSONDecodeError:
                        await self.send_to_websocket(
                            websocket,
                            {"type": "error", "message": "Invalid JSON format"},
                        )

            except websockets.exceptions.ConnectionClosed:
                pass
            except Exception as e:
                self.logger.error(f"WebSocket error: {e}")
            finally:
                self.websocket_clients.discard(websocket)
                self.logger.info(f"WebSocket client disconnected")

        self.websocket_server = await websockets.serve(
            websocket_handler,
            self.config["websocket"]["host"],
            self.config["websocket"]["port"],
        )

        self.logger.info(
            f"WebSocket server started on {self.config['websocket']['host']}:{self.config['websocket']['port']}"
        )

    async def start_market_data_publisher(self):
        """Publish market data updates."""
        while self.running:
            try:
                if self.fxcm_connected:
                    # Update prices with small random movements
                    import random

                    for symbol, prices in self.market_prices.items():
                        movement = random.uniform(-0.0005, 0.0005)
                        new_bid = prices["bid"] + movement
                        new_ask = new_bid + 0.0002  # 2 pip spread

                        self.market_prices[symbol] = {
                            "bid": round(new_bid, 5),
                            "ask": round(new_ask, 5),
                            "timestamp": datetime.utcnow().isoformat(),
                        }

                    # Publish to RabbitMQ
                    if self.rabbitmq_connected:
                        await self.publish_market_data()

                    # Broadcast to WebSocket clients
                    await self.broadcast_to_websockets(
                        {
                            "type": "market_data",
                            "data": self.market_prices,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )

                    # Update Redis cache
                    if self.redis_connected:
                        await self.update_redis_cache()

                await asyncio.sleep(self.config["fxcm"]["update_interval"])

            except Exception as e:
                self.logger.error(f"Market data publisher error: {e}")
                await asyncio.sleep(5)

    async def start_account_monitor(self):
        """Monitor and update account information."""
        while self.running:
            try:
                if self.fxcm_connected:
                    # Update account state
                    self.update_account_state()

                    # Update positions P&L
                    self.update_positions_pl()

                    # Publish account updates
                    if self.rabbitmq_connected:
                        await self.publish_account_updates()

                    # Broadcast to WebSocket clients
                    await self.broadcast_to_websockets(
                        {
                            "type": "account_update",
                            "data": self.account_state,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )

                await asyncio.sleep(5)  # Update every 5 seconds

            except Exception as e:
                self.logger.error(f"Account monitor error: {e}")
                await asyncio.sleep(10)

    def update_account_state(self):
        """Update account state with current P&L."""
        total_pl = sum(pos.get("unrealized_pl", 0) for pos in self.positions.values())

        self.account_state.update(
            {
                "unrealized_pl": total_pl,
                "equity": self.account_state["balance"] + total_pl,
                "last_update": datetime.utcnow().isoformat(),
            }
        )

    def update_positions_pl(self):
        """Update positions with current P&L."""
        for position_id, position in self.positions.items():
            symbol = position["symbol"]
            if symbol in self.market_prices:
                current_price = self.market_prices[symbol][
                    "ask" if position["side"] == "long" else "bid"
                ]

                price_diff = current_price - position["open_price"]
                if position["side"] == "short":
                    price_diff = -price_diff

                position["current_price"] = current_price
                position["unrealized_pl"] = price_diff * position["quantity"]
                position["last_update"] = datetime.utcnow().isoformat()

    async def publish_market_data(self):
        """Publish market data to RabbitMQ."""
        try:
            channel = self.rabbitmq_connection.channel()

            for symbol, prices in self.market_prices.items():
                message = {
                    "symbol": symbol,
                    "bid": prices["bid"],
                    "ask": prices["ask"],
                    "timestamp": prices["timestamp"],
                    "source": "fxcm_demo",
                }

                channel.basic_publish(
                    exchange="fxcm.market_data",
                    routing_key=f"price.{symbol.lower()}",
                    body=json.dumps(message),
                )

        except Exception as e:
            self.logger.error(f"Failed to publish market data: {e}")

    async def publish_account_updates(self):
        """Publish account updates to RabbitMQ."""
        try:
            channel = self.rabbitmq_connection.channel()

            # Account update
            account_message = {
                "type": "account_update",
                "data": self.account_state,
                "timestamp": datetime.utcnow().isoformat(),
            }

            channel.basic_publish(
                exchange="fxcm.account_updates",
                routing_key="account.update",
                body=json.dumps(account_message),
            )

            # Position updates
            if self.positions:
                positions_message = {
                    "type": "positions_update",
                    "data": list(self.positions.values()),
                    "timestamp": datetime.utcnow().isoformat(),
                }

                channel.basic_publish(
                    exchange="fxcm.account_updates",
                    routing_key="position.update",
                    body=json.dumps(positions_message),
                )

        except Exception as e:
            self.logger.error(f"Failed to publish account updates: {e}")

    async def process_rabbitmq_messages(self):
        """Process incoming RabbitMQ messages from FXML4."""

        def callback(ch, method, properties, body):
            try:
                message = json.loads(body)
                asyncio.create_task(self.handle_fxml4_message(message))
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                self.logger.error(f"Error processing RabbitMQ message: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        try:
            channel = self.rabbitmq_connection.channel()
            channel.basic_consume(queue="fxml4.orders", on_message_callback=callback)

            # Start consuming in a separate thread
            def consume_messages():
                channel.start_consuming()

            await asyncio.get_event_loop().run_in_executor(None, consume_messages)

        except Exception as e:
            self.logger.error(f"RabbitMQ message processing error: {e}")

    async def handle_fxml4_message(self, message: Dict[str, Any]):
        """Handle messages from FXML4."""
        message_type = message.get("type")

        if message_type == "place_order":
            await self.execute_order(message["data"])
        elif message_type == "close_position":
            await self.execute_position_close(message["data"])
        else:
            self.logger.warning(f"Unknown message type: {message_type}")

    async def update_redis_cache(self):
        """Update Redis cache with current data."""
        try:
            pipeline = self.redis_client.pipeline()

            # Cache market data
            for symbol, prices in self.market_prices.items():
                pipeline.hset(f"fxcm:prices:{symbol}", mapping=prices)
                pipeline.expire(f"fxcm:prices:{symbol}", 60)

            # Cache account data
            pipeline.hset("fxcm:account", mapping=self.account_state)
            pipeline.expire("fxcm:account", 60)

            # Cache positions
            for position_id, position in self.positions.items():
                pipeline.hset(f"fxcm:position:{position_id}", mapping=position)
                pipeline.expire(f"fxcm:position:{position_id}", 300)

            await asyncio.get_event_loop().run_in_executor(None, pipeline.execute)

        except Exception as e:
            self.logger.error(f"Redis cache update error: {e}")

    # HTTP API Handlers

    async def health_check(self, request):
        """Health check endpoint."""
        status = {
            "status": "healthy" if self.running else "unhealthy",
            "fxcm_connected": self.fxcm_connected,
            "rabbitmq_connected": self.rabbitmq_connected,
            "redis_connected": self.redis_connected,
            "websocket_clients": len(self.websocket_clients),
            "timestamp": datetime.utcnow().isoformat(),
        }
        return web.json_response(status)

    async def get_account_info(self, request):
        """Get account information."""
        if not self.fxcm_connected:
            return web.json_response({"error": "Not connected to FXCM"}, status=503)

        return web.json_response(self.account_state)

    async def get_positions(self, request):
        """Get current positions."""
        if not self.fxcm_connected:
            return web.json_response({"error": "Not connected to FXCM"}, status=503)

        return web.json_response(list(self.positions.values()))

    async def get_market_prices(self, request):
        """Get current market prices."""
        if not self.fxcm_connected:
            return web.json_response({"error": "Not connected to FXCM"}, status=503)

        return web.json_response(self.market_prices)

    async def place_order(self, request):
        """Place a trading order."""
        if not self.fxcm_connected:
            return web.json_response({"error": "Not connected to FXCM"}, status=503)

        try:
            order_data = await request.json()
            result = await self.execute_order(order_data)
            return web.json_response(result)

        except Exception as e:
            self.logger.error(f"Order placement error: {e}")
            return web.json_response({"error": str(e)}, status=400)

    async def close_position(self, request):
        """Close a position."""
        position_id = request.match_info["position_id"]

        if position_id not in self.positions:
            return web.json_response({"error": "Position not found"}, status=404)

        try:
            result = await self.execute_position_close({"position_id": position_id})
            return web.json_response(result)

        except Exception as e:
            self.logger.error(f"Position close error: {e}")
            return web.json_response({"error": str(e)}, status=400)

    async def get_bridge_status(self, request):
        """Get comprehensive bridge status."""
        status = {
            "service": "FXCM Demo Bridge",
            "version": "1.0.0",
            "connections": {
                "fxcm": {
                    "connected": self.fxcm_connected,
                    "server": self.demo_credentials["server"],
                    "account": self.demo_credentials["username"],
                },
                "rabbitmq": {
                    "connected": self.rabbitmq_connected,
                    "host": self.config["rabbitmq"]["host"],
                },
                "redis": {
                    "connected": self.redis_connected,
                    "host": self.config["redis"]["host"],
                },
            },
            "clients": {"websocket": len(self.websocket_clients)},
            "data": {
                "positions": len(self.positions),
                "symbols": len(self.market_prices),
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

        return web.json_response(status)

    # Trading Operations

    async def execute_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a trading order."""
        symbol = order_data["symbol"]
        side = order_data["side"]
        quantity = order_data["quantity"]

        if symbol not in self.market_prices:
            raise ValueError(f"Symbol {symbol} not available")

        # Get execution price
        execution_price = self.market_prices[symbol]["ask" if side == "buy" else "bid"]

        # Create position
        position_id = f"FXCM_POS_{len(self.positions) + 1:04d}"
        position = {
            "position_id": position_id,
            "symbol": symbol,
            "side": "long" if side == "buy" else "short",
            "quantity": quantity,
            "open_price": execution_price,
            "current_price": execution_price,
            "unrealized_pl": 0.0,
            "timestamp": datetime.utcnow().isoformat(),
        }

        self.positions[position_id] = position

        # Update account
        commission = 2.50
        self.account_state["balance"] -= commission
        self.account_state["margin_used"] += abs(quantity) * 0.02
        self.account_state["margin_available"] = (
            self.account_state["balance"] - self.account_state["margin_used"]
        )

        result = {
            "order_id": position_id,
            "status": "FILLED",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "fill_price": execution_price,
            "commission": commission,
            "timestamp": datetime.utcnow().isoformat(),
        }

        self.logger.info(f"Order executed: {result}")
        return result

    async def execute_position_close(
        self, close_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Close a position."""
        position_id = close_data["position_id"]
        position = self.positions.get(position_id)

        if not position:
            raise ValueError(f"Position {position_id} not found")

        # Get close price
        symbol = position["symbol"]
        close_price = self.market_prices[symbol][
            "bid" if position["side"] == "long" else "ask"
        ]

        # Calculate P&L
        price_diff = close_price - position["open_price"]
        if position["side"] == "short":
            price_diff = -price_diff

        realized_pl = price_diff * position["quantity"]

        # Update account
        self.account_state["balance"] += realized_pl
        self.account_state["margin_used"] -= abs(position["quantity"]) * 0.02
        self.account_state["margin_available"] = (
            self.account_state["balance"] - self.account_state["margin_used"]
        )

        # Remove position
        del self.positions[position_id]

        result = {
            "position_id": position_id,
            "close_price": close_price,
            "realized_pl": realized_pl,
            "timestamp": datetime.utcnow().isoformat(),
        }

        self.logger.info(f"Position closed: {result}")
        return result

    # WebSocket Operations

    async def send_to_websocket(self, websocket, message):
        """Send message to specific WebSocket client."""
        try:
            await websocket.send(json.dumps(message))
        except Exception as e:
            self.logger.error(f"WebSocket send error: {e}")

    async def broadcast_to_websockets(self, message):
        """Broadcast message to all WebSocket clients."""
        if not self.websocket_clients:
            return

        disconnected = set()

        for client in self.websocket_clients:
            try:
                await client.send(json.dumps(message))
            except Exception:
                disconnected.add(client)

        # Remove disconnected clients
        self.websocket_clients -= disconnected

    async def handle_websocket_message(self, websocket, message):
        """Handle WebSocket message from client."""
        msg_type = message.get("type")

        if msg_type == "subscribe":
            # Handle subscription request
            symbols = message.get("symbols", [])
            await self.send_to_websocket(
                websocket,
                {
                    "type": "subscribed",
                    "symbols": symbols,
                    "message": f"Subscribed to {len(symbols)} symbols",
                },
            )

        elif msg_type == "get_status":
            # Send current status
            await self.send_to_websocket(
                websocket,
                {
                    "type": "status",
                    "data": {
                        "account": self.account_state,
                        "positions": list(self.positions.values()),
                        "prices": self.market_prices,
                    },
                },
            )

    # Lifecycle Management

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        self.logger.info(f"Received signal {signum}, shutting down...")
        asyncio.create_task(self.shutdown())

    async def shutdown(self):
        """Shutdown the bridge service."""
        self.logger.info("Shutting down FXCM Demo Bridge...")
        self.running = False

        # Close WebSocket server
        if self.websocket_server:
            self.websocket_server.close()
            await self.websocket_server.wait_closed()

        # Close WebSocket clients
        if self.websocket_clients:
            await asyncio.gather(
                *[client.close() for client in self.websocket_clients],
                return_exceptions=True,
            )

        # Close RabbitMQ connection
        if self.rabbitmq_connection and not self.rabbitmq_connection.is_closed:
            self.rabbitmq_connection.close()

        # Close Redis connection
        if self.redis_client:
            self.redis_client.close()

        self.logger.info("FXCM Demo Bridge shutdown complete")


async def main():
    """Main entry point."""
    bridge = FXCMDemoBridge()

    try:
        await bridge.start()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        bridge.logger.error(f"Fatal error: {e}")
    finally:
        await bridge.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
