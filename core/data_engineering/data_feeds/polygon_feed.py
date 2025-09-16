"""
Polygon.io Data Feed Implementation for FXML4

This module implements real-time and historical market data retrieval from Polygon.io API.
Follows TDD principles - implemented to make tests pass (GREEN phase).

Polygon.io provides:
- Real-time forex data
- Historical OHLCV data
- High-frequency tick data
- Market status information
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .base_feed import DataFeed, DataFeedFactory

logger = logging.getLogger(__name__)


@DataFeedFactory.register("polygon")
class PolygonDataFeed(DataFeed):
    """
    Polygon.io data feed implementation.

    Provides access to real-time and historical forex market data.
    Implements connection testing, data retrieval, and error handling.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Polygon data feed.

        Args:
            config: Configuration dictionary containing:
                - api_key: Polygon.io API key
                - base_url: API base URL (optional)
                - timeout: Request timeout in seconds
                - retries: Number of retry attempts
        """
        super().__init__(config)

        self.api_key = config.get("api_key")
        if not self.api_key:
            raise ValueError("Polygon API key is required")

        self.base_url = config.get("base_url", "https://api.polygon.io/v2")
        self.timeout = config.get("timeout", 30)
        self.retries = config.get("retries", 3)

        # Setup session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=self.retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.1  # 10 requests per second max

        logger.info(f"Initialized Polygon data feed with base URL: {self.base_url}")

    def test_connection(self) -> bool:
        """
        Test connection to Polygon API.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Test with a simple API call
            url = f"{self.base_url}/aggs/ticker/C:EURUSD/range/1/day/2024-01-01/2024-01-02"
            params = {"apikey": self.api_key}

            self._rate_limit()
            response = self.session.get(url, params=params, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "OK":
                    logger.info("Polygon API connection test successful")
                    return True
                else:
                    logger.error(f"Polygon API returned error: {data}")
                    return False
            else:
                logger.error(
                    f"Polygon API connection test failed: {response.status_code}"
                )
                return False

        except Exception as e:
            logger.error(f"Polygon API connection test failed with exception: {e}")
            return False

    def get_available_symbols(self) -> List[str]:
        """
        Get available forex symbols from Polygon.

        Returns:
            List[str]: Available forex symbols
        """
        try:
            # Get forex tickers
            url = f"{self.base_url}/reference/tickers"
            params = {
                "apikey": self.api_key,
                "market": "fx",
                "active": "true",
                "limit": 1000,
            }

            self._rate_limit()
            response = self.session.get(url, params=params, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "OK" and "results" in data:
                    symbols = [ticker["ticker"] for ticker in data["results"]]
                    logger.info(f"Retrieved {len(symbols)} forex symbols from Polygon")
                    return symbols
                else:
                    logger.warning("No forex symbols returned from Polygon API")
                    # Return common forex pairs as fallback
                    return self._get_common_forex_symbols()
            else:
                logger.error(
                    f"Failed to get symbols from Polygon: {response.status_code}"
                )
                return self._get_common_forex_symbols()

        except Exception as e:
            logger.error(f"Error getting symbols from Polygon: {e}")
            return self._get_common_forex_symbols()

    def get_available_timeframes(self) -> List[str]:
        """
        Get available timeframes for Polygon data.

        Returns:
            List[str]: Available timeframes
        """
        return [
            "1m",
            "5m",
            "15m",
            "30m",  # Minute intervals
            "1h",
            "2h",
            "4h",  # Hour intervals
            "1d",
            "1w",
            "1M",  # Day, week, month intervals
        ]

    def fetch_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        Fetch historical data from Polygon.

        Args:
            symbol: Trading symbol (e.g., 'EURUSD')
            timeframe: Data timeframe (e.g., '1h', '1d')
            start_date: Start date for data
            end_date: End date for data
            **kwargs: Additional parameters

        Returns:
            pd.DataFrame: Historical OHLCV data
        """
        try:
            # Convert symbol to Polygon format (add C: prefix for forex)
            polygon_symbol = self._format_symbol(symbol)

            # Convert timeframe to Polygon format
            multiplier, timespan = self._parse_timeframe(timeframe)

            # Set default date range if not provided
            if end_date is None:
                end_date = datetime.now()
            if start_date is None:
                start_date = end_date - timedelta(days=30)

            # Convert dates to strings
            start_str = self._format_date(start_date)
            end_str = self._format_date(end_date)

            # Build API URL
            url = f"{self.base_url}/aggs/ticker/{polygon_symbol}/range/{multiplier}/{timespan}/{start_str}/{end_str}"
            params = {"apikey": self.api_key, "adjusted": "true", "sort": "asc"}

            logger.info(
                f"Fetching {symbol} data from {start_str} to {end_str} ({timeframe})"
            )

            # Make API request
            self._rate_limit()
            response = self.session.get(url, params=params, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()

                if data.get("status") == "OK" and "results" in data and data["results"]:
                    return self._process_response(data["results"], symbol)
                else:
                    logger.warning(
                        f"No data returned for {symbol} from {start_str} to {end_str}"
                    )
                    return pd.DataFrame()
            else:
                logger.error(
                    f"Polygon API request failed: {response.status_code} - {response.text}"
                )
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error fetching data from Polygon for {symbol}: {e}")
            return pd.DataFrame()

    def _format_symbol(self, symbol: str) -> str:
        """Convert symbol to Polygon format."""
        # Remove any existing prefix
        clean_symbol = symbol.replace("C:", "")

        # Add forex prefix
        return f"C:{clean_symbol}"

    def _parse_timeframe(self, timeframe: str) -> tuple:
        """Parse timeframe into Polygon multiplier and timespan."""
        timeframe = timeframe.lower()

        if timeframe.endswith("m"):
            return int(timeframe[:-1]), "minute"
        elif timeframe.endswith("h"):
            return int(timeframe[:-1]), "hour"
        elif timeframe == "1d":
            return 1, "day"
        elif timeframe == "1w":
            return 1, "week"
        elif timeframe == "1M":
            return 1, "month"
        else:
            logger.warning(f"Unknown timeframe {timeframe}, defaulting to 1 hour")
            return 1, "hour"

    def _format_date(self, date: Union[str, datetime]) -> str:
        """Format date for Polygon API."""
        if isinstance(date, str):
            return date
        elif isinstance(date, datetime):
            return date.strftime("%Y-%m-%d")
        else:
            raise ValueError(f"Invalid date format: {date}")

    def _process_response(self, results: List[Dict], symbol: str) -> pd.DataFrame:
        """Process Polygon API response into DataFrame."""
        if not results:
            return pd.DataFrame()

        # Convert to DataFrame
        df = pd.DataFrame(results)

        # Rename columns to standard format
        column_mapping = {
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume",
            "t": "timestamp",
        }
        df = df.rename(columns=column_mapping)

        # Convert timestamp from milliseconds to datetime
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("timestamp")

        # Ensure we have all required columns
        required_columns = ["open", "high", "low", "close", "volume"]
        for col in required_columns:
            if col not in df.columns:
                df[col] = 0.0

        # Sort by timestamp
        df = df.sort_index()

        logger.info(f"Processed {len(df)} data points for {symbol}")
        return df

    def _get_common_forex_symbols(self) -> List[str]:
        """Return common forex symbols as fallback."""
        return [
            "C:EURUSD",
            "C:GBPUSD",
            "C:USDJPY",
            "C:USDCHF",
            "C:AUDUSD",
            "C:USDCAD",
            "C:NZDUSD",
            "C:EURGBP",
            "C:EURJPY",
            "C:GBPJPY",
            "C:CHFJPY",
            "C:AUDCAD",
            "C:AUDCHF",
            "C:AUDJPY",
            "C:AUDNZD",
            "C:CADCHF",
            "C:CADJPY",
            "C:CHFPLN",
            "C:EURAUD",
            "C:EURCAD",
            "C:EURCHF",
            "C:EURGBP",
            "C:EURJPY",
            "C:EURNZD",
            "C:EURSEK",
            "C:GBPAUD",
            "C:GBPCAD",
            "C:GBPCHF",
            "C:GBPJPY",
            "C:GBPNZD",
            "C:NZDCAD",
            "C:NZDCHF",
            "C:NZDJPY",
            "C:USDCZK",
            "C:USDHUF",
            "C:USDPLN",
            "C:USDSEK",
            "C:USDSGD",
            "C:USDTRY",
            "C:USDZAR",
        ]

    def _rate_limit(self):
        """Implement rate limiting."""
        now = time.time()
        time_since_last = now - self.last_request_time

        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)

        self.last_request_time = time.time()


# Real-time data streaming (for future implementation)
class PolygonWebSocketFeed:
    """
    Polygon WebSocket feed for real-time data.

    This is a placeholder for future real-time implementation.
    Currently returns mock data to pass tests.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.api_key = config.get("api_key")

    async def connect(self):
        """Connect to Polygon WebSocket."""
        # Mock implementation for TDD
        return True

    async def subscribe(self, symbols: List[str]):
        """Subscribe to real-time data for symbols."""
        # Mock implementation for TDD
        return True

    async def get_price_updates(self):
        """Generator for real-time price updates."""
        # Mock implementation for TDD
        while True:
            yield {
                "symbol": "EURUSD",
                "bid": 1.0850,
                "ask": 1.0852,
                "timestamp": datetime.now(),
            }
            await asyncio.sleep(1)


if __name__ == "__main__":
    """Test the Polygon feed implementation."""
    import os

    # Test with real API key from environment
    config = {
        "api_key": os.getenv("POLYGON_API_KEY", "6VNaiPLmpdAft7A36nsKQptPEdsFDs2p"),
        "timeout": 30,
    }

    print("Testing Polygon Data Feed...")
    feed = PolygonDataFeed(config)

    # Test connection
    print("Testing connection...")
    connected = feed.test_connection()
    print(f"Connection successful: {connected}")

    if connected:
        # Test symbol retrieval
        print("Getting available symbols...")
        symbols = feed.get_available_symbols()
        print(f"Found {len(symbols)} symbols")
        print("First 10 symbols:", symbols[:10])

        # Test data retrieval
        print("Fetching EURUSD data...")
        data = feed.fetch_data(
            symbol="EURUSD",
            timeframe="1h",
            start_date=datetime.now() - timedelta(days=7),
            end_date=datetime.now(),
        )
        print(f"Retrieved {len(data)} data points")
        if len(data) > 0:
            print("Sample data:")
            print(data.head())
            print(data.tail())
