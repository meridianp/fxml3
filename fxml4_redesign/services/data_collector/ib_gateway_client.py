"""Interactive Brokers Gateway client for market data collection."""

import asyncio
import logging
import random
from collections import deque
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional


class IBGatewayClient:
    """Client for Interactive Brokers Gateway/TWS API."""

    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 1):
        """Initialize IB Gateway client.

        Args:
            host: IB Gateway host
            port: IB Gateway port (7497 for paper, 7496 for live)
            client_id: Unique client ID
        """
        self.host = host
        self.port = port
        self.client_id = client_id
        self.logger = logging.getLogger(f"IBClient-{client_id}")

        # Connection state
        self.connected = False

        # Market data subscriptions
        self.subscriptions: Dict[str, int] = {}  # symbol -> req_id
        self.req_id_counter = 1000

        # Data queues
        self.tick_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self.market_data_cache: Dict[str, Dict[str, Any]] = {}

        # For demo/testing - simulate data
        self.demo_mode = True
        self.demo_prices = {
            "EURUSD": 1.0850,
            "GBPUSD": 1.2650,
            "USDJPY": 148.50,
            "AUDUSD": 0.6550,
            "USDCHF": 0.8850,
            "USDCAD": 1.3550,
            "NZDUSD": 0.6150,
        }

    async def connect(self):
        """Connect to IB Gateway."""
        try:
            if self.demo_mode:
                self.logger.info(
                    "Running in demo mode - simulating IB Gateway connection"
                )
                self.connected = True
                # Start demo data generator
                asyncio.create_task(self._demo_data_generator())
                return

            # Real IB connection would go here
            # For now, we'll use the demo mode

            self.connected = True
            self.logger.info(f"Connected to IB Gateway at {self.host}:{self.port}")

        except Exception as e:
            self.logger.error(f"Failed to connect to IB Gateway: {e}")
            raise

    async def disconnect(self):
        """Disconnect from IB Gateway."""
        self.connected = False
        self.logger.info("Disconnected from IB Gateway")

    async def subscribe_market_data(self, symbol: str):
        """Subscribe to market data for a symbol.

        Args:
            symbol: Trading symbol (e.g., 'EURUSD')
        """
        if symbol in self.subscriptions:
            self.logger.debug(f"Already subscribed to {symbol}")
            return

        req_id = self.req_id_counter
        self.req_id_counter += 1

        self.subscriptions[symbol] = req_id
        self.market_data_cache[symbol] = {}

        self.logger.info(f"Subscribed to market data for {symbol} (req_id: {req_id})")

    async def unsubscribe_market_data(self, symbol: str):
        """Unsubscribe from market data for a symbol."""
        if symbol in self.subscriptions:
            req_id = self.subscriptions.pop(symbol)
            self.logger.info(f"Unsubscribed from {symbol} (req_id: {req_id})")

    async def get_market_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get latest market data for a symbol.

        Returns:
            Market data dict with OHLC, volume, etc.
        """
        if symbol not in self.market_data_cache:
            return None

        data = self.market_data_cache[symbol]

        # Ensure we have all required fields
        if not all(k in data for k in ["open", "high", "low", "close"]):
            return None

        return {
            "time": data.get("time", datetime.utcnow()),
            "open": data["open"],
            "high": data["high"],
            "low": data["low"],
            "close": data["close"],
            "volume": data.get("volume", 0),
            "spread": data.get("spread"),
            "bid": data.get("bid"),
            "ask": data.get("ask"),
            "bid_size": data.get("bid_size", 0),
            "ask_size": data.get("ask_size", 0),
        }

    async def get_tick_data(self, symbol: str) -> List[Dict[str, Any]]:
        """Get recent tick data for a symbol.

        Returns:
            List of recent ticks
        """
        ticks = []

        # Get up to 100 ticks from queue
        for _ in range(100):
            try:
                tick = self.tick_queue.get_nowait()
                if tick["symbol"] == symbol:
                    ticks.append(tick)
            except asyncio.QueueEmpty:
                break

        return ticks

    async def get_next_tick(self) -> Optional[Dict[str, Any]]:
        """Get next tick from the queue.

        Returns:
            Tick data or None if no tick available
        """
        try:
            return await asyncio.wait_for(self.tick_queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            return None

    async def _demo_data_generator(self):
        """Generate demo market data for testing."""
        while self.connected:
            try:
                # Generate data for each subscribed symbol
                for symbol in list(self.subscriptions.keys()):
                    if symbol not in self.demo_prices:
                        continue

                    # Get base price
                    base_price = self.demo_prices[symbol]

                    # Add some randomness
                    change = random.uniform(-0.0010, 0.0010)
                    new_price = base_price + change

                    # Update demo price
                    self.demo_prices[symbol] = new_price

                    # Create market data
                    spread = 0.0001 if symbol != "USDJPY" else 0.01

                    data = {
                        "time": datetime.utcnow(),
                        "bid": new_price - spread / 2,
                        "ask": new_price + spread / 2,
                        "last": new_price,
                        "close": new_price,
                        "bid_size": random.randint(100000, 1000000),
                        "ask_size": random.randint(100000, 1000000),
                        "volume": random.randint(1000, 10000),
                        "spread": spread,
                    }

                    # Update OHLC
                    if "open" not in self.market_data_cache[symbol]:
                        self.market_data_cache[symbol]["open"] = new_price
                        self.market_data_cache[symbol]["high"] = new_price
                        self.market_data_cache[symbol]["low"] = new_price

                    self.market_data_cache[symbol].update(data)
                    self.market_data_cache[symbol]["high"] = max(
                        self.market_data_cache[symbol]["high"], new_price
                    )
                    self.market_data_cache[symbol]["low"] = min(
                        self.market_data_cache[symbol]["low"], new_price
                    )

                    # Generate tick
                    tick = {
                        "symbol": symbol,
                        "time": datetime.utcnow(),
                        "price": new_price,
                        "size": random.randint(10000, 100000),
                        "type": random.choice(["trade", "bid", "ask"]),
                    }

                    # Add to queue if not full
                    try:
                        self.tick_queue.put_nowait(tick)
                    except asyncio.QueueFull:
                        pass

                # Sleep for a bit to simulate real tick intervals
                await asyncio.sleep(random.uniform(0.1, 0.5))

            except Exception as e:
                self.logger.error(f"Error in demo data generator: {e}")
                await asyncio.sleep(1)

    async def get_historical_data(
        self,
        symbol: str,
        end_time: datetime,
        duration: str = "1 D",
        bar_size: str = "5 mins",
        what_to_show: str = "MIDPOINT",
    ) -> List[Dict[str, Any]]:
        """Get historical data from IB.

        Args:
            symbol: Trading symbol
            end_time: End time for historical data
            duration: Duration string (e.g., "1 D", "1 W")
            bar_size: Bar size (e.g., "5 mins", "1 hour")
            what_to_show: Data type (e.g., "MIDPOINT", "TRADES")

        Returns:
            List of historical bars
        """
        # For demo, return empty list
        # Real implementation would fetch from IB API
        return []

    def is_connected(self) -> bool:
        """Check if connected to IB Gateway."""
        return self.connected
