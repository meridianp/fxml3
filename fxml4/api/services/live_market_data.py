"""
Live Market Data Service for FXML4 API.

This service provides real-time market data using Polygon.io and other external sources.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fxml4.data.polygon_fetcher import PolygonDataFetcher

from .market_data import MarketDataPoint

logger = logging.getLogger(__name__)


class LiveMarketDataService:
    """Service for retrieving live market data from external sources."""

    def __init__(self):
        self.polygon_fetcher = None
        self._initialize_polygon()

    def _initialize_polygon(self):
        """Initialize Polygon.io data fetcher."""
        try:
            api_key = os.getenv("POLYGON_API_KEY")
            if not api_key:
                logger.warning(
                    "No Polygon.io API key found. Live data will be limited."
                )
                return

            self.polygon_fetcher = PolygonDataFetcher(
                api_key=api_key, use_official_client=True, cache_enabled=True
            )
            logger.info("Polygon.io data fetcher initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Polygon.io fetcher: {e}")

    async def get_live_ohlcv_data(
        self,
        symbol: str,
        timeframe: str = "1h",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[MarketDataPoint]:
        """Get live OHLCV data for a symbol."""
        try:
            if not self.polygon_fetcher:
                raise Exception("Polygon.io fetcher not available")

            # Convert forex symbol format if needed
            polygon_symbol = self._convert_symbol_format(symbol)

            # Set default time range if not provided
            if not end_time:
                end_time = datetime.utcnow()
            if not start_time:
                start_time = end_time - timedelta(hours=limit)

            # Convert timeframe to Polygon format
            polygon_timeframe = self._convert_timeframe(timeframe)

            # Fetch data from Polygon
            logger.info(
                f"Fetching live data for {symbol} ({polygon_symbol}) {timeframe}"
            )

            # Use the polygon fetcher's get_historical_data method
            data_frame = await asyncio.to_thread(
                self.polygon_fetcher.get_historical_data,
                symbols=[polygon_symbol],
                start_date=start_time.strftime("%Y-%m-%d"),
                end_date=end_time.strftime("%Y-%m-%d"),
                timeframe=polygon_timeframe,
            )

            # Convert to MarketDataPoint objects
            data_points = []
            if data_frame is not None and not data_frame.empty:
                for _, row in data_frame.iterrows():
                    data_point = MarketDataPoint(
                        time=(
                            row.name
                            if hasattr(row.name, "to_pydatetime")
                            else datetime.fromisoformat(str(row.name))
                        ),
                        symbol=symbol,
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=int(row.get("volume", 0)),
                        tick_count=int(
                            row.get("vwap", 0)
                        ),  # Use VWAP as tick_count placeholder
                        source="polygon_live",
                    )
                    data_points.append(data_point)

            # Limit results
            data_points = data_points[-limit:] if limit else data_points

            logger.info(f"Retrieved {len(data_points)} live data points for {symbol}")
            return data_points

        except Exception as e:
            logger.error(f"Error fetching live data for {symbol}: {e}")
            # Return empty list instead of raising to allow graceful degradation
            return []

    def _convert_symbol_format(self, symbol: str) -> str:
        """Convert FXML4 symbol format to Polygon format."""
        # Convert forex pairs to Polygon format
        forex_mapping = {
            "EURUSD": "C:EURUSD",
            "GBPUSD": "C:GBPUSD",
            "USDJPY": "C:USDJPY",
            "USDCHF": "C:USDCHF",
            "AUDUSD": "C:AUDUSD",
            "USDCAD": "C:USDCAD",
            "NZDUSD": "C:NZDUSD",
            "EURGBP": "C:EURGBP",
        }

        return forex_mapping.get(symbol, f"C:{symbol}")

    def _convert_timeframe(self, timeframe: str) -> str:
        """Convert FXML4 timeframe to Polygon timeframe."""
        timeframe_mapping = {
            "1m": "1/minute",
            "5m": "5/minute",
            "15m": "15/minute",
            "30m": "30/minute",
            "1h": "1/hour",
            "4h": "4/hour",
            "1d": "1/day",
        }

        return timeframe_mapping.get(timeframe, "1/hour")


# Create singleton instance
live_market_data_service = LiveMarketDataService()
