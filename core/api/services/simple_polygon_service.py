"""
Simple Polygon.io Live Data Service.

Direct implementation without complex dependencies.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import List

from polygon import RESTClient

from .market_data import MarketDataPoint

logger = logging.getLogger(__name__)


class SimplePolygonService:
    """Simple service for live data from Polygon.io."""

    def __init__(self):
        self.api_key = os.getenv("POLYGON_API_KEY")
        self.client = None

        if self.api_key:
            try:
                self.client = RESTClient(api_key=self.api_key)
                logger.info("Polygon.io client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Polygon client: {e}")
        else:
            logger.warning("No Polygon API key found")

    async def get_forex_data(
        self, symbol: str, timeframe: str = "1h", limit: int = 100
    ) -> List[MarketDataPoint]:
        """Get forex data from Polygon.io."""
        if not self.client:
            logger.warning("Polygon client not available")
            return []

        try:
            # Convert symbol to Polygon format
            polygon_symbol = f"C:{symbol}"

            # Calculate date range (use recent trading days to ensure we get data)
            end_date = datetime.utcnow() - timedelta(days=2)  # Go back 2 days from now
            start_date = end_date - timedelta(days=7)  # 7-day window

            # Convert timeframe to Polygon multiplier and timespan
            multiplier, timespan = self._convert_timeframe(timeframe)

            logger.info(
                f"Fetching Polygon data for {polygon_symbol}, timeframe: {multiplier}/{timespan}"
            )

            # Fetch data using polygon client (run in thread to avoid blocking)
            aggs = await asyncio.to_thread(
                self._fetch_aggs,
                polygon_symbol,
                multiplier,
                timespan,
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
                limit,
            )

            if not aggs:
                logger.warning(f"No data returned from Polygon for {polygon_symbol}")
                return []

            # Convert to MarketDataPoint objects
            data_points = []
            for agg in aggs[-limit:]:  # Get latest data points
                try:
                    # Convert timestamp from milliseconds
                    timestamp = datetime.fromtimestamp(agg.timestamp / 1000)

                    data_point = MarketDataPoint(
                        time=timestamp,
                        symbol=symbol,
                        open=float(agg.open),
                        high=float(agg.high),
                        low=float(agg.low),
                        close=float(agg.close),
                        volume=int(getattr(agg, "volume", 0)),
                        tick_count=int(getattr(agg, "transactions", 0)),
                        source="polygon_live",
                    )
                    data_points.append(data_point)

                except Exception as e:
                    logger.error(f"Error processing data point: {e}")
                    continue

            logger.info(f"Retrieved {len(data_points)} data points for {symbol}")
            return data_points

        except Exception as e:
            logger.error(f"Error fetching Polygon data for {symbol}: {e}")
            return []

    def _fetch_aggs(self, symbol, multiplier, timespan, start_date, end_date, limit):
        """Fetch aggregates from Polygon (synchronous)."""
        try:
            aggs = list(
                self.client.get_aggs(
                    ticker=symbol,
                    multiplier=multiplier,
                    timespan=timespan,
                    from_=start_date,
                    to=end_date,
                    limit=limit,
                )
            )
            return aggs
        except Exception as e:
            logger.error(f"Polygon API error: {e}")
            return []

    def _convert_timeframe(self, timeframe: str) -> tuple:
        """Convert timeframe to Polygon multiplier and timespan."""
        mapping = {
            "1m": (1, "minute"),
            "5m": (5, "minute"),
            "15m": (15, "minute"),
            "30m": (30, "minute"),
            "1h": (1, "hour"),
            "4h": (4, "hour"),
            "1d": (1, "day"),
        }
        return mapping.get(timeframe, (1, "hour"))


# Create singleton instance
simple_polygon_service = SimplePolygonService()
