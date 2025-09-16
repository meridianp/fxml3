"""
Direct HTTP-based Polygon.io service for real market data.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import List

import aiohttp

from .market_data import MarketDataPoint

logger = logging.getLogger(__name__)


class DirectPolygonService:
    """Direct HTTP service for Polygon.io real market data."""

    def __init__(self):
        self.api_key = os.getenv("POLYGON_API_KEY")
        self.base_url = "https://api.polygon.io/v2"

        if self.api_key:
            logger.info("Direct Polygon.io service initialized")
        else:
            logger.warning("No Polygon API key found")

    async def get_real_forex_data(
        self, symbol: str, timeframe: str = "1h", limit: int = 100
    ) -> List[MarketDataPoint]:
        """Get real forex data from Polygon.io via HTTP."""
        if not self.api_key:
            logger.warning("No API key available")
            return []

        try:
            # Use recent trading days
            end_date = datetime.utcnow() - timedelta(days=2)  # Friday if it's weekend
            start_date = end_date - timedelta(days=5)  # Go back 5 days

            # Format for Polygon
            polygon_symbol = f"C:{symbol}"
            multiplier, timespan = self._convert_timeframe(timeframe)

            # Build URL
            url = (
                f"{self.base_url}/aggs/ticker/{polygon_symbol}/range/"
                f"{multiplier}/{timespan}/"
                f"{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}"
                f"?apikey={self.api_key}"
            )

            logger.info(f"Fetching from: {url}")

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._process_polygon_data(data, symbol, limit)
                    else:
                        logger.error(
                            f"Polygon API error: {response.status} - {await response.text()}"
                        )
                        return []

        except Exception as e:
            logger.error(f"Error fetching data from Polygon: {e}")
            return []

    def _process_polygon_data(
        self, data: dict, symbol: str, limit: int
    ) -> List[MarketDataPoint]:
        """Process Polygon.io response data."""
        try:
            if data.get("status") != "OK":
                logger.warning(f"Polygon API status: {data.get('status')}")
                return []

            results = data.get("results", [])
            if not results:
                logger.warning("No results from Polygon API")
                return []

            data_points = []
            # Get the most recent data points
            for result in results[-limit:]:
                try:
                    # Convert timestamp from milliseconds
                    timestamp = datetime.fromtimestamp(result["t"] / 1000)

                    data_point = MarketDataPoint(
                        time=timestamp,
                        symbol=symbol,
                        open=float(result["o"]),
                        high=float(result["h"]),
                        low=float(result["l"]),
                        close=float(result["c"]),
                        volume=int(result.get("v", 0)),
                        tick_count=int(result.get("n", 0)),
                        source="polygon_real",
                    )
                    data_points.append(data_point)

                except Exception as e:
                    logger.error(f"Error processing data point: {e}")
                    continue

            logger.info(f"Processed {len(data_points)} real data points for {symbol}")
            return data_points

        except Exception as e:
            logger.error(f"Error processing Polygon data: {e}")
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
direct_polygon_service = DirectPolygonService()
