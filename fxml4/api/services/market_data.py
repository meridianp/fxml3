"""
Market Data Service for FXML4 API.

This service provides access to market data from TimescaleDB and external feeds.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import asyncpg
import pandas as pd
from pydantic import BaseModel

from fxml4.api.services.redis_cache import redis_cache_service
from fxml4.config import get_config
from fxml4.core.database_pool import get_pool_manager

logger = logging.getLogger(__name__)


class MarketDataPoint(BaseModel):
    """Market data point model."""

    time: datetime
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    tick_count: Optional[int] = 0
    source: str


class MarketDataService:
    """Service for retrieving market data from TimescaleDB and external feeds."""

    def __init__(self):
        self.config = get_config()
        self._pool_manager = None

    async def get_pool_manager(self):
        """Get the optimized database pool manager."""
        if self._pool_manager is None:
            self._pool_manager = await get_pool_manager()
        return self._pool_manager

    async def get_connection_pool(self):
        """Alias for get_pool_manager for backwards compatibility."""
        return await self.get_pool_manager()

    async def get_ohlcv_data(
        self,
        symbol: str,
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = 1000,
    ) -> List[MarketDataPoint]:
        """
        Get OHLCV data from TimescaleDB with Redis caching for performance.

        Args:
            symbol: Trading symbol (e.g., 'EURUSD')
            timeframe: Timeframe ('1m', '5m', '15m', '30m', '1h', '4h', '1d')
            start_time: Start time for data range
            end_time: End time for data range
            limit: Maximum number of data points to return

        Returns:
            List of market data points
        """
        # Set default time range if not provided
        if end_time is None:
            end_time = datetime.utcnow()
        if start_time is None:
            start_time = end_time - timedelta(days=30)

        # Create cache key parameters
        cache_params = {
            "symbol": symbol,
            "timeframe": timeframe,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "limit": limit,
        }

        # Try to get from cache first
        try:
            cached_data = await redis_cache_service.get("market_data", cache_params)
            if cached_data:
                # Convert cached data back to MarketDataPoint objects
                data_points = []
                for item in cached_data:
                    data_points.append(
                        MarketDataPoint(
                            time=datetime.fromisoformat(
                                item["time"].replace("Z", "+00:00")
                            ),
                            symbol=item["symbol"],
                            open=item["open"],
                            high=item["high"],
                            low=item["low"],
                            close=item["close"],
                            volume=item["volume"],
                            tick_count=item.get("tick_count", 0),
                            source=item.get("source", "timescaledb"),
                        )
                    )
                logger.info(
                    f"Cache HIT: Retrieved {len(data_points)} cached data points for {symbol} {timeframe}"
                )
                return data_points
        except Exception as cache_error:
            logger.warning(f"Cache retrieval failed: {cache_error}")

        # Cache miss - get from database using optimized pool manager
        try:
            pool_manager = await self.get_pool_manager()

            # Use optimized connection pooling with automatic management
            query = """
            SELECT * FROM get_ohlcv($1, $2, $3, $4)
            ORDER BY time DESC
            LIMIT $5
            """

            rows = await pool_manager.execute(
                query, symbol, timeframe, start_time, end_time, limit
            )

            # Convert to MarketDataPoint objects
            data_points = []
            cache_data = []  # For storing in cache

            for row in reversed(rows):  # Reverse to get chronological order
                data_point = MarketDataPoint(
                    time=row["time"],
                    symbol=row["symbol"],
                    open=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=row["volume"],
                    tick_count=row["tick_count"],
                    source="timescaledb",
                )
                data_points.append(data_point)

                # Prepare for cache storage
                cache_data.append(
                    {
                        "time": data_point.time.isoformat(),
                        "symbol": data_point.symbol,
                        "open": data_point.open,
                        "high": data_point.high,
                        "low": data_point.low,
                        "close": data_point.close,
                        "volume": data_point.volume,
                        "tick_count": data_point.tick_count,
                        "source": data_point.source,
                    }
                )

                # Cache the results asynchronously (don't wait for it)
                if cache_data:
                    asyncio.create_task(
                        redis_cache_service.set("market_data", cache_params, cache_data)
                    )

                logger.info(
                    f"Database: Retrieved {len(data_points)} data points for {symbol} {timeframe}"
                )
                return data_points

        except Exception as e:
            logger.error(f"Error retrieving OHLCV data: {e}")
            # Fall back to external feeds if database fails
            return await self._get_external_data(
                symbol, timeframe, start_time, end_time, limit
            )

    async def _get_external_data(
        self,
        symbol: str,
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = 1000,
    ) -> List[MarketDataPoint]:
        """Fallback method to get data from external feeds."""
        try:
            from fxml4.data_engineering.data_feeds.base_feed import DataFeedFactory

            # Determine appropriate feed based on symbol
            if symbol.startswith(
                ("EUR", "GBP", "USD", "JPY", "AUD", "CAD", "CHF", "NZD")
            ):
                feed_type = "alpha_vantage"
                feed_config = (
                    self.config.get("data", {})
                    .get("data_feeds", {})
                    .get("alpha_vantage", {})
                )
            else:
                feed_type = "polygon"
                feed_config = (
                    self.config.get("data", {}).get("data_feeds", {}).get("polygon", {})
                )

            # Create feed instance
            feed = DataFeedFactory.create(feed_type, feed_config)

            # Convert timeframe to external feed format
            external_timeframe = self._convert_timeframe(timeframe)

            # Fetch data
            data = feed.fetch_data(
                symbol=symbol,
                timeframe=external_timeframe,
                start_date=start_time,
                end_date=end_time,
                limit=limit,
            )

            # Convert DataFrame to MarketDataPoint objects
            data_points = []
            if not data.empty:
                for idx, row in data.iterrows():
                    data_points.append(
                        MarketDataPoint(
                            time=(
                                idx
                                if isinstance(idx, datetime)
                                else pd.to_datetime(idx)
                            ),
                            symbol=symbol,
                            open=float(row.get("open", row.get("Open", 0))),
                            high=float(row.get("high", row.get("High", 0))),
                            low=float(row.get("low", row.get("Low", 0))),
                            close=float(row.get("close", row.get("Close", 0))),
                            volume=int(row.get("volume", row.get("Volume", 0))),
                            tick_count=0,
                            source=feed_type,
                        )
                    )

            logger.info(
                f"Retrieved {len(data_points)} data points from {feed_type} for {symbol}"
            )
            return data_points

        except Exception as e:
            logger.error(f"Error retrieving external data: {e}")
            return []

    def _convert_timeframe(self, timeframe: str) -> str:
        """Convert internal timeframe to external feed format."""
        timeframe_map = {
            "1m": "1min",
            "5m": "5min",
            "15m": "15min",
            "30m": "30min",
            "1h": "60min",
            "4h": "4hour",
            "1d": "daily",
        }
        return timeframe_map.get(timeframe, timeframe)

    async def get_latest_tick(
        self, symbol: str, tick_type: str = "trade"
    ) -> Optional[Dict[str, Any]]:
        """Get the latest tick data for a symbol."""
        try:
            pool_manager = await self.get_pool_manager()

            query = "SELECT * FROM get_latest_tick($1, $2)"
            row = await pool_manager.fetchrow(query, symbol, tick_type)

            if row:
                return {
                    "time": row["time"],
                    "price": row["price"],
                    "size": row["size"],
                    "symbol": symbol,
                    "tick_type": tick_type,
                }
            return None

        except Exception as e:
            logger.error(f"Error retrieving latest tick: {e}")
            return None

    async def store_market_data(
        self, symbol: str, data_points: List[MarketDataPoint], timeframe: str = "1m"
    ) -> bool:
        """Store market data in TimescaleDB."""
        try:
            pool_manager = await self.get_pool_manager()

            if timeframe == "1m":
                # Insert into market_data_1m table
                insert_query = """
                INSERT INTO market_data_1m (time, symbol, open, high, low, close, volume, tick_count, source)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (time, symbol) DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    tick_count = EXCLUDED.tick_count,
                    source = EXCLUDED.source
                """

                for point in data_points:
                    await pool_manager.execute(
                        insert_query,
                        point.time,
                        point.symbol,
                        point.open,
                        point.high,
                        point.low,
                        point.close,
                        point.volume,
                        point.tick_count,
                        point.source,
                    )
            else:
                logger.warning(
                    f"Direct storage for timeframe {timeframe} not supported. Use 1m data and continuous aggregates."
                )
                return False

            logger.info(f"Stored {len(data_points)} data points for {symbol}")
            return True

        except Exception as e:
            logger.error(f"Error storing market data: {e}")
            return False

    async def get_available_symbols(self) -> List[str]:
        """Get list of available symbols in the database."""
        try:
            pool_manager = await self.get_pool_manager()

            query = "SELECT name FROM symbols ORDER BY name"
            rows = await pool_manager.execute(query)

            return [row["name"] for row in rows]

        except Exception as e:
            logger.error(f"Error retrieving symbols: {e}")
            return ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]  # Default symbols

    async def close(self):
        """Close database connection pool."""
        if self._pool_manager:
            await self._pool_manager.close()
            self._pool_manager = None


# Global instance
market_data_service = MarketDataService()
