"""
Polygon.io Data Feed Implementation
==================================

Production-ready integration with Polygon.io API for high-frequency market data.
Supports both REST API and WebSocket streaming for real-time tick data.

Features:
- Real-time WebSocket streaming
- Historical data via REST API
- High-frequency tick data
- Rate limiting and error handling
- Connection health monitoring

API Documentation: https://polygon.io/docs/
"""

import asyncio
import json
import logging
import ssl
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

import aiohttp
import websockets

from .base_feed import BaseDataFeed, MarketDataCandle, MarketDataTick

logger = logging.getLogger(__name__)


class PolygonDataFeed(BaseDataFeed):
    """Polygon.io data feed with REST API and WebSocket streaming."""

    def __init__(self, config: Dict[str, Any]):
        # Polygon allows higher rate limits (typically 1000/minute for paid plans)
        if "rate_limit" not in config:
            config["rate_limit"] = 100  # Conservative default

        super().__init__(config)

        self.api_key = config.get("api_key")
        self.rest_base_url = "https://api.polygon.io"
        self.websocket_url = "wss://socket.polygon.io"

        self.session: Optional[aiohttp.ClientSession] = None
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.websocket_task: Optional[asyncio.Task] = None
        self.subscriptions: Dict[str, Callable] = {}

        # Timeframe mapping for REST API
        self.timeframe_mapping = {
            "1m": "1/minute",
            "5m": "5/minute",
            "15m": "15/minute",
            "30m": "30/minute",
            "1h": "1/hour",
            "4h": "4/hour",
            "1d": "1/day",
            "1w": "1/week",
            "1M": "1/month",
        }

        if not self.api_key:
            logger.error("❌ Polygon.io API key is required")

    async def connect(self) -> bool:
        """Establish connections to both REST API and WebSocket."""
        try:
            if not self.api_key:
                logger.error("❌ Polygon.io API key not configured")
                return False

            # Setup REST API session
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            connector = aiohttp.TCPConnector(
                limit=20,
                limit_per_host=10,
                keepalive_timeout=60,
                enable_cleanup_closed=True,
            )

            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={
                    "User-Agent": "FXML4-Trading-System/1.0",
                    "Authorization": f"Bearer {self.api_key}",
                },
            )

            # Test REST API connection
            rest_success = await self._test_rest_connection()
            if not rest_success:
                await self.disconnect()
                return False

            # Setup WebSocket connection
            websocket_success = await self._connect_websocket()
            if not websocket_success:
                logger.warning("⚠️ WebSocket connection failed, REST API only")
                # Don't fail entirely - REST API still works

            logger.info("✅ Polygon.io connection established")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to connect to Polygon.io: {e}")
            await self.disconnect()
            return False

    async def disconnect(self):
        """Close all connections."""
        # Close WebSocket
        if self.websocket_task:
            self.websocket_task.cancel()
            try:
                await self.websocket_task
            except asyncio.CancelledError:
                pass
            self.websocket_task = None

        if self.websocket:
            await self.websocket.close()
            self.websocket = None

        # Close REST session
        if self.session:
            await self.session.close()
            self.session = None

        self.subscriptions.clear()

    async def _test_rest_connection(self) -> bool:
        """Test REST API connection."""
        try:
            url = f"{self.rest_base_url}/v2/aggs/ticker/C:EURUSD/prev"
            params = {"apikey": self.api_key}

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return "results" in data
                else:
                    logger.error(
                        f"❌ Polygon REST API test failed: HTTP {response.status}"
                    )
                    return False

        except Exception as e:
            logger.error(f"❌ Polygon REST connection test failed: {e}")
            return False

    async def _connect_websocket(self) -> bool:
        """Connect to Polygon WebSocket for real-time data."""
        try:
            # SSL context for secure WebSocket
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False

            # Connect to WebSocket
            uri = f"{self.websocket_url}/forex"
            self.websocket = await websockets.connect(
                uri,
                ssl=ssl_context,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10,
            )

            # Authenticate
            auth_message = {"action": "auth", "params": self.api_key}
            await self.websocket.send(json.dumps(auth_message))

            # Wait for auth response
            response = await asyncio.wait_for(self.websocket.recv(), timeout=10)
            auth_result = json.loads(response)

            if auth_result[0].get("status") != "auth_success":
                logger.error(f"❌ WebSocket authentication failed: {auth_result}")
                return False

            # Start message handler
            self.websocket_task = asyncio.create_task(self._websocket_message_handler())

            logger.info("✅ Polygon WebSocket connected and authenticated")
            return True

        except Exception as e:
            logger.error(f"❌ WebSocket connection failed: {e}")
            return False

    async def _websocket_message_handler(self):
        """Handle incoming WebSocket messages."""
        try:
            while self.websocket and not self.websocket.closed:
                message = await self.websocket.recv()
                data = json.loads(message)

                for item in data:
                    if item.get("ev") == "CA":  # Currency Aggregate (tick)
                        await self._handle_forex_tick(item)
                    elif item.get("ev") == "status":
                        logger.info(f"📡 WebSocket status: {item.get('message')}")

        except websockets.exceptions.ConnectionClosed:
            logger.warning("⚠️ WebSocket connection closed")
        except Exception as e:
            logger.error(f"❌ WebSocket message handler error: {e}")

    async def _handle_forex_tick(self, tick_data: Dict[str, Any]):
        """Process forex tick from WebSocket."""
        try:
            # Convert Polygon format to our MarketDataTick
            symbol = tick_data.get("pair", "").replace("/", "")
            if not symbol:
                return

            timestamp = datetime.fromtimestamp(
                tick_data.get("t", 0) / 1000, tz=timezone.utc
            )

            tick = MarketDataTick(
                timestamp=timestamp,
                symbol=symbol,
                bid=tick_data.get("b"),
                ask=tick_data.get("a"),
                last=tick_data.get("c"),  # close price
                volume=tick_data.get("v", 0),
                source="polygon",
                metadata={
                    "open": tick_data.get("o"),
                    "high": tick_data.get("h"),
                    "low": tick_data.get("l"),
                    "vwap": tick_data.get("vw"),
                    "transactions": tick_data.get("n", 0),
                },
            )

            # Call registered callback for this symbol
            callback = self.subscriptions.get(symbol)
            if callback:
                await callback(tick)

        except Exception as e:
            logger.error(f"❌ Error processing forex tick: {e}")

    async def get_real_time_quote(self, symbol: str) -> Optional[MarketDataTick]:
        """Get real-time quote via REST API."""
        if not self.session:
            logger.error("❌ Not connected to Polygon.io")
            return None

        if not self.validate_symbol(symbol):
            logger.error(f"❌ Invalid symbol: {symbol}")
            return None

        try:
            await self.rate_limiter.wait_for_slot()

            # Format symbol for Polygon (e.g., C:EURUSD)
            polygon_symbol = f"C:{symbol}"
            url = f"{self.rest_base_url}/v2/last/trade/{polygon_symbol}"
            params = {"apikey": self.api_key}

            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"❌ Polygon API error: HTTP {response.status}")
                    await self._track_request(False)
                    return None

                data = await response.json()

                if data.get("status") != "OK":
                    logger.error(
                        f"❌ Polygon API error: {data.get('message', 'Unknown error')}"
                    )
                    await self._track_request(False)
                    return None

                result = data.get("results", {})
                if not result:
                    logger.warning(f"⚠️ No data available for {symbol}")
                    await self._track_request(False)
                    return None

                # Create MarketDataTick
                tick = MarketDataTick(
                    timestamp=datetime.fromtimestamp(
                        result.get("t", 0) / 1000, tz=timezone.utc
                    ),
                    symbol=symbol,
                    last=result.get("p"),  # price
                    volume=result.get("s"),  # size
                    source="polygon",
                    metadata={
                        "exchange": result.get("x"),
                        "conditions": result.get("c", []),
                    },
                )

                await self._track_request(True)
                return tick

        except Exception as e:
            logger.error(f"❌ Error getting quote for {symbol}: {e}")
            await self._track_request(False)
            return None

    async def get_historical_data(
        self,
        symbol: str,
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[MarketDataCandle]:
        """Get historical data via REST API."""
        if not self.session:
            logger.error("❌ Not connected to Polygon.io")
            return []

        if not self.validate_symbol(symbol):
            logger.error(f"❌ Invalid symbol: {symbol}")
            return []

        try:
            await self.rate_limiter.wait_for_slot()

            # Set default time range
            if end_time is None:
                end_time = datetime.now(timezone.utc)
            if start_time is None:
                start_time = end_time - timedelta(days=30)

            # Format dates for Polygon API
            start_date = start_time.strftime("%Y-%m-%d")
            end_date = end_time.strftime("%Y-%m-%d")

            # Convert timeframe
            multiplier, timespan = self._parse_timeframe(timeframe)

            # Format symbol for Polygon
            polygon_symbol = f"C:{symbol}"

            # Build URL
            url = f"{self.rest_base_url}/v2/aggs/ticker/{polygon_symbol}/range/{multiplier}/{timespan}/{start_date}/{end_date}"

            params = {"apikey": self.api_key, "adjusted": "true", "sort": "desc"}

            if limit:
                params["limit"] = limit

            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"❌ Polygon API error: HTTP {response.status}")
                    await self._track_request(False)
                    return []

                data = await response.json()

                if data.get("status") != "OK":
                    logger.error(
                        f"❌ Polygon API error: {data.get('message', 'Unknown error')}"
                    )
                    await self._track_request(False)
                    return []

                results = data.get("results", [])
                if not results:
                    logger.warning(f"⚠️ No historical data for {symbol}")
                    await self._track_request(False)
                    return []

                # Convert to MarketDataCandle objects
                candles = []
                for result in results:
                    candle = MarketDataCandle(
                        timestamp=datetime.fromtimestamp(
                            result.get("t", 0) / 1000, tz=timezone.utc
                        ),
                        symbol=symbol,
                        timeframe=timeframe,
                        open=result.get("o", 0),
                        high=result.get("h", 0),
                        low=result.get("l", 0),
                        close=result.get("c", 0),
                        volume=result.get("v", 0),
                        source="polygon",
                        metadata={
                            "vwap": result.get("vw"),
                            "transactions": result.get("n", 0),
                        },
                    )
                    candles.append(candle)

                await self._track_request(True)
                logger.info(
                    f"✅ Retrieved {len(candles)} candles for {symbol} {timeframe}"
                )
                return candles

        except Exception as e:
            logger.error(f"❌ Error getting historical data for {symbol}: {e}")
            await self._track_request(False)
            return []

    async def subscribe_real_time(self, symbols: List[str], callback) -> bool:
        """Subscribe to real-time WebSocket feed."""
        if not self.websocket:
            logger.error("❌ WebSocket not connected")
            return False

        try:
            # Convert symbols to Polygon format
            polygon_symbols = [
                f"C.{symbol}" for symbol in symbols if self.validate_symbol(symbol)
            ]

            if not polygon_symbols:
                logger.error("❌ No valid symbols to subscribe")
                return False

            # Send subscription message
            subscribe_message = {
                "action": "subscribe",
                "params": ",".join(polygon_symbols),
            }

            await self.websocket.send(json.dumps(subscribe_message))

            # Store callbacks
            for symbol in symbols:
                if self.validate_symbol(symbol):
                    self.subscriptions[symbol] = callback

            logger.info(f"📡 Subscribed to {len(symbols)} symbols via WebSocket")
            return True

        except Exception as e:
            logger.error(f"❌ Error subscribing to real-time feed: {e}")
            return False

    async def unsubscribe_real_time(self, symbols: List[str]) -> bool:
        """Unsubscribe from real-time WebSocket feed."""
        if not self.websocket:
            return True

        try:
            # Convert symbols to Polygon format
            polygon_symbols = [
                f"C.{symbol}" for symbol in symbols if symbol in self.subscriptions
            ]

            if polygon_symbols:
                unsubscribe_message = {
                    "action": "unsubscribe",
                    "params": ",".join(polygon_symbols),
                }

                await self.websocket.send(json.dumps(unsubscribe_message))

            # Remove callbacks
            for symbol in symbols:
                self.subscriptions.pop(symbol, None)

            logger.info(f"🛑 Unsubscribed from {len(symbols)} symbols")
            return True

        except Exception as e:
            logger.error(f"❌ Error unsubscribing from real-time feed: {e}")
            return False

    def _parse_timeframe(self, timeframe: str) -> tuple:
        """Parse timeframe into multiplier and timespan for Polygon API."""
        timeframe_map = {
            "1m": (1, "minute"),
            "5m": (5, "minute"),
            "15m": (15, "minute"),
            "30m": (30, "minute"),
            "1h": (1, "hour"),
            "4h": (4, "hour"),
            "1d": (1, "day"),
            "1w": (1, "week"),
            "1M": (1, "month"),
        }

        return timeframe_map.get(timeframe, (1, "minute"))

    def validate_symbol(self, symbol: str) -> bool:
        """Validate if symbol is a forex pair."""
        # Basic forex pair validation (6 characters, currency codes)
        if len(symbol) != 6:
            return False

        major_currencies = {"USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"}
        from_currency = symbol[:3]
        to_currency = symbol[3:6]

        return from_currency in major_currencies and to_currency in major_currencies

    async def _perform_health_check(self) -> bool:
        """Health check specific to Polygon.io."""
        try:
            quote = await self.get_real_time_quote("EURUSD")
            return quote is not None and quote.last is not None
        except Exception:
            return False

    def get_supported_timeframes(self) -> List[str]:
        """Get list of supported timeframes."""
        return list(self.timeframe_mapping.keys())
