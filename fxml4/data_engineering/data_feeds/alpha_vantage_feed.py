"""Alpha Vantage data feed implementation.

This module implements a data feed for Alpha Vantage financial data API.
It provides access to financial market data as well as economic indicators
and commodity data.
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union

import pandas as pd
import requests

from .base_feed import DataFeed, DataFeedFactory

logger = logging.getLogger(__name__)

# Default timeframes available from Alpha Vantage
TIMEFRAME_MAPPING = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "60m": "60min",
    "1h": "60min",
    "1d": "daily",
    "1w": "weekly",
    "1M": "monthly",
}

# Default limit settings for different timeframes
OUTPUT_SIZE_MAPPING = {
    "1m": "compact",  # Last 100 data points
    "5m": "compact",
    "15m": "compact",
    "30m": "compact",
    "60m": "compact",
    "1h": "compact",
    "1d": "full",  # Full historical data (up to 20+ years)
    "1w": "full",
    "1M": "full",
}

# Economic indicators available from Alpha Vantage
ECONOMIC_INDICATORS = [
    "REAL_GDP",  # Real Gross Domestic Product
    "REAL_GDP_PER_CAPITA",  # Real GDP per capita
    "TREASURY_YIELD",  # Treasury yield of a given maturity
    "FEDERAL_FUNDS_RATE",  # Federal funds rate (interest rate)
    "CPI",  # Consumer Price Index
    "INFLATION",  # Inflation rates (consumer prices)
    "RETAIL_SALES",  # Advance Retail Sales
    "DURABLES",  # Manufacturers' new orders of durable goods
    "UNEMPLOYMENT",  # Unemployment rate
    "NONFARM_PAYROLL",  # Total nonfarm payroll
]

# Commodity data endpoints available from Alpha Vantage
COMMODITY_ENDPOINTS = [
    "WTI",  # West Texas Intermediate (WTI) crude oil prices
    "BRENT",  # Brent (Europe) crude oil prices
    "NATURAL_GAS",  # Henry Hub natural gas spot prices
    "COPPER",  # Global price of copper
    "ALUMINUM",  # Global price of aluminum
    "WHEAT",  # Global price of wheat
    "CORN",  # Global price of corn
    "COTTON",  # Global price of cotton
    "SUGAR",  # Global price of sugar
    "COFFEE",  # Global price of coffee
    "ALL_COMMODITIES",  # Global price index of all commodities
]


@DataFeedFactory.register("alpha_vantage")
class AlphaVantageDataFeed(DataFeed):
    """Data feed implementation for Alpha Vantage financial API.

    This class provides methods to access:
    - Market data (stocks, forex, cryptocurrencies)
    - Economic indicators (GDP, inflation, unemployment, etc.)
    - Commodity prices (oil, gas, metals, agricultural products)

    The API supports different data frequencies and historical ranges
    depending on the data type and endpoint.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize the Alpha Vantage data feed.

        Args:
            config: Configuration dictionary with the following keys:
                api_key: Alpha Vantage API key
                base_url: Base URL for API requests (default: 'https://www.alphavantage.co/query')
                request_timeout: Timeout for API requests in seconds (default: 30)
                api_calls_per_minute: Number of API calls allowed per minute (default: 5 for free tier, 75 for premium)
                cache_data: Whether to cache API responses (default: True)
                cache_expiry: Cache expiry time in seconds (default: 3600, 1 hour)
                default_output_size: Default output size for requests (default: 'compact')
                premium_tier: Premium tier level (default: False)
        """
        super().__init__(config)

        # API configuration
        self.api_key = config.get("api_key")
        if not self.api_key:
            raise ValueError("Alpha Vantage API key is required")

        self.base_url = config.get("base_url", "https://www.alphavantage.co/query")
        self.request_timeout = config.get("request_timeout", 30)

        # Premium tier features
        self.premium_tier = config.get("premium_tier", False)

        # Rate limiting based on tier
        self.api_calls_per_minute = config.get(
            "api_calls_per_minute", 75 if self.premium_tier else 5
        )
        self.call_interval = 60.0 / self.api_calls_per_minute
        self.last_call_time = 0.0

        # Premium tier allows for larger output size and more data points
        if self.premium_tier:
            # Update default output size mappings for premium tier
            global OUTPUT_SIZE_MAPPING
            for key in OUTPUT_SIZE_MAPPING:
                OUTPUT_SIZE_MAPPING[key] = (
                    "full"  # Get full data for all timeframes with premium
                )

        # Caching
        self.cache_data = config.get("cache_data", True)
        self.cache_expiry = config.get("cache_expiry", 3600)  # 1 hour
        self.cache = {}  # {function_name_symbol_interval: (timestamp, data)}

        # Output size
        self.default_output_size = config.get("default_output_size", "compact")

        # List of supported symbols and timeframes
        self.supported_symbols = config.get(
            "symbols", ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]
        )

        tier_info = "premium" if self.premium_tier else "free"
        logger.info(
            f"Initialized Alpha Vantage data feed ({tier_info} tier) with API key ending in ...{self.api_key[-4:]} ({self.api_calls_per_minute} calls/minute)"
        )

    def _respect_rate_limit(self):
        """Ensure API rate limits are respected."""
        current_time = time.time()
        elapsed = current_time - self.last_call_time

        if elapsed < self.call_interval:
            sleep_time = self.call_interval - elapsed
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)

        self.last_call_time = time.time()

    def test_connection(self) -> bool:
        """
        Test connection to Alpha Vantage API.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Use a simple API call to test connection
            params = {
                "function": "GLOBAL_QUOTE",
                "symbol": "MSFT",  # Use a common stock symbol
                "apikey": self.api_key,
            }

            self._respect_rate_limit()

            response = requests.get(
                self.base_url, params=params, timeout=self.request_timeout
            )

            if response.status_code == 200:
                data = response.json()

                # Check for API error messages
                if "Error Message" in data:
                    logger.error(f"Alpha Vantage API error: {data['Error Message']}")
                    return False
                elif "Information" in data:
                    # This usually means rate limit or demo key limitations
                    logger.warning(
                        f"Alpha Vantage API information: {data['Information']}"
                    )
                    # Still consider this a successful connection for demo keys
                    return True
                elif "Global Quote" in data:
                    logger.info("Alpha Vantage API connection test successful")
                    return True
                else:
                    logger.warning("Alpha Vantage API returned unexpected format")
                    return True  # Consider successful if no explicit error
            else:
                logger.error(
                    f"Alpha Vantage API connection test failed: HTTP {response.status_code}"
                )
                return False

        except Exception as e:
            logger.error(
                f"Alpha Vantage API connection test failed with exception: {e}"
            )
            return False

    def _get_cache_key(self, function: str, symbol: str, interval: str) -> str:
        """Generate a cache key.

        Args:
            function: API function name
            symbol: Symbol being requested
            interval: Data interval

        Returns:
            Cache key string
        """
        return f"{function}_{symbol}_{interval}"

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache for a given key is valid.

        Args:
            cache_key: Cache key to check

        Returns:
            True if cache is valid, False otherwise
        """
        if not self.cache_data or cache_key not in self.cache:
            return False

        timestamp, _ = self.cache[cache_key]
        return (time.time() - timestamp) < self.cache_expiry

    def _request_data(self, params: Dict[str, str]) -> Dict[str, Any]:
        """Make a request to the Alpha Vantage API.

        Args:
            params: Request parameters

        Returns:
            Response data as dictionary

        Raises:
            ConnectionError: If the API request fails
            ValueError: If the API returns an error message
        """
        # Add API key to parameters
        params["apikey"] = self.api_key

        # Generate cache key if applicable
        cache_key = None
        if self.cache_data:
            function = params.get("function", "")
            symbol = params.get("symbol", "")
            interval = params.get("interval", params.get("outputsize", ""))
            cache_key = self._get_cache_key(function, symbol, interval)

            if self._is_cache_valid(cache_key):
                logger.debug(f"Using cached data for {cache_key}")
                _, data = self.cache[cache_key]
                return data

        # Respect rate limits
        self._respect_rate_limit()

        try:
            logger.debug(f"Making Alpha Vantage API request with params: {params}")
            response = requests.get(
                self.base_url, params=params, timeout=self.request_timeout
            )
            response.raise_for_status()

            data = response.json()

            # Check for API error messages
            if "Error Message" in data:
                raise ValueError(f"Alpha Vantage API error: {data['Error Message']}")

            if "Information" in data:
                logger.info(f"Alpha Vantage API info: {data['Information']}")

            # Cache the response if enabled
            if self.cache_data and cache_key:
                self.cache[cache_key] = (time.time(), data)

            return data

        except requests.RequestException as e:
            raise ConnectionError(f"Failed to connect to Alpha Vantage API: {e}")

    def _format_symbol_for_av(self, symbol: str) -> str:
        """Format symbol for Alpha Vantage API.

        Args:
            symbol: Symbol to format

        Returns:
            Formatted symbol
        """
        # Handle different symbol formats
        if "." in symbol:
            # Convert forex pairs from "EUR.USD" to "EURUSD"
            return symbol.replace(".", "")
        return symbol

    def _parse_forex_data(self, data: Dict[str, Any], timeframe: str) -> pd.DataFrame:
        """Parse forex data from Alpha Vantage response.

        Args:
            data: Response data from API
            timeframe: Timeframe requested

        Returns:
            DataFrame with parsed data

        Raises:
            ValueError: If data cannot be parsed
        """
        # For intraday data
        if timeframe in ["1m", "5m", "15m", "30m", "60m", "1h"]:
            time_series_key = f"Time Series FX ({TIMEFRAME_MAPPING[timeframe]})"
        else:  # For daily, weekly, monthly
            time_series_key = f"Time Series FX ({TIMEFRAME_MAPPING[timeframe]})"

        if time_series_key not in data:
            # Try alternate format for some responses
            alt_key = next(
                (k for k in data.keys() if k.startswith("Time Series")), None
            )
            if not alt_key:
                available_keys = list(data.keys())
                raise ValueError(
                    f"Could not find time series data in response. Available keys: {available_keys}"
                )
            time_series_key = alt_key

        time_series = data[time_series_key]

        # Parse the time series data
        parsed_data = []
        for timestamp_str, values in time_series.items():
            timestamp = pd.to_datetime(timestamp_str)
            parsed_data.append(
                {
                    "timestamp": timestamp,
                    "open": float(values["1. open"]),
                    "high": float(values["2. high"]),
                    "low": float(values["3. low"]),
                    "close": float(values["4. close"]),
                    "volume": float(
                        values.get("5. volume", 0)
                    ),  # Some don't have volume
                }
            )

        # Convert to DataFrame
        df = pd.DataFrame(parsed_data)

        # Set timestamp as index and sort
        df = df.set_index("timestamp")
        df = df.sort_index()

        return df

    def _parse_stock_data(self, data: Dict[str, Any], timeframe: str) -> pd.DataFrame:
        """Parse stock data from Alpha Vantage response.

        Args:
            data: Response data from API
            timeframe: Timeframe requested

        Returns:
            DataFrame with parsed data

        Raises:
            ValueError: If data cannot be parsed
        """
        # For intraday data
        if timeframe in ["1m", "5m", "15m", "30m", "60m", "1h"]:
            time_series_key = f"Time Series ({TIMEFRAME_MAPPING[timeframe]})"
        else:  # For daily, weekly, monthly
            if timeframe == "1d":
                time_series_key = "Time Series (Daily)"
            elif timeframe == "1w":
                time_series_key = "Weekly Time Series"
            else:  # Monthly
                time_series_key = "Monthly Time Series"

        if time_series_key not in data:
            # Try alternate format for some responses
            alt_key = next(
                (k for k in data.keys() if k.startswith("Time Series")), None
            )
            if not alt_key:
                available_keys = list(data.keys())
                raise ValueError(
                    f"Could not find time series data in response. Available keys: {available_keys}"
                )
            time_series_key = alt_key

        time_series = data[time_series_key]

        # Parse the time series data
        parsed_data = []
        for timestamp_str, values in time_series.items():
            timestamp = pd.to_datetime(timestamp_str)
            entry = {
                "timestamp": timestamp,
                "open": float(values.get("1. open", values.get("open", 0))),
                "high": float(values.get("2. high", values.get("high", 0))),
                "low": float(values.get("3. low", values.get("low", 0))),
                "close": float(values.get("4. close", values.get("close", 0))),
                "volume": float(values.get("5. volume", values.get("volume", 0))),
            }
            parsed_data.append(entry)

        # Convert to DataFrame
        df = pd.DataFrame(parsed_data)

        # Set timestamp as index and sort
        df = df.set_index("timestamp")
        df = df.sort_index()

        return df

    def fetch_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Fetch data from Alpha Vantage.

        Args:
            symbol: Trading symbol (e.g., "EURUSD", "IBM")
            timeframe: Timeframe for the data (e.g., "1m", "1h", "1d")
            start_date: Start date for the data
            end_date: End date for the data
            **kwargs: Additional arguments:
                data_type: Type of data to retrieve (default: "forex", other options: "stock")
                adjusted: Whether to use adjusted stock data (default: True)
                extended_hours: Include extended hours data for stocks (default: True)

        Returns:
            DataFrame containing the fetched data

        Raises:
            ValueError: If the timeframe is not supported
            ConnectionError: If the API request fails
        """
        if timeframe not in TIMEFRAME_MAPPING:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        # Format symbol for Alpha Vantage
        av_symbol = self._format_symbol_for_av(symbol)

        # Get data type and other parameters
        data_type = kwargs.get("data_type", "forex").lower()
        output_size = kwargs.get(
            "output_size", OUTPUT_SIZE_MAPPING.get(timeframe, self.default_output_size)
        )

        # Set up request parameters
        params = {"outputsize": output_size}

        # Different requests based on data type
        if data_type == "forex":
            # Handle forex data
            if timeframe in ["1m", "5m", "15m", "30m", "60m", "1h"]:
                params["function"] = "FX_INTRADAY"
                params["interval"] = TIMEFRAME_MAPPING[timeframe]
                params["from_symbol"] = av_symbol[:3]  # Base currency
                params["to_symbol"] = av_symbol[3:]  # Quote currency
            else:
                params["function"] = "FX_DAILY"
                if timeframe == "1w":
                    params["function"] = "FX_WEEKLY"
                elif timeframe == "1M":
                    params["function"] = "FX_MONTHLY"
                params["from_symbol"] = av_symbol[:3]
                params["to_symbol"] = av_symbol[3:]

        elif data_type == "stock":
            # Handle stock data
            adjusted = kwargs.get("adjusted", True)
            extended_hours = kwargs.get("extended_hours", True)

            if timeframe in ["1m", "5m", "15m", "30m", "60m", "1h"]:
                params["function"] = "TIME_SERIES_INTRADAY"
                params["symbol"] = av_symbol
                params["interval"] = TIMEFRAME_MAPPING[timeframe]
                if adjusted:
                    params["adjusted"] = "true"
                if extended_hours:
                    params["extended_hours"] = "true"
            else:
                if timeframe == "1d":
                    params["function"] = "TIME_SERIES_DAILY"
                    if adjusted:
                        params["function"] = "TIME_SERIES_DAILY_ADJUSTED"
                elif timeframe == "1w":
                    params["function"] = "TIME_SERIES_WEEKLY"
                    if adjusted:
                        params["function"] = "TIME_SERIES_WEEKLY_ADJUSTED"
                else:  # Monthly
                    params["function"] = "TIME_SERIES_MONTHLY"
                    if adjusted:
                        params["function"] = "TIME_SERIES_MONTHLY_ADJUSTED"
                params["symbol"] = av_symbol
        else:
            raise ValueError(f"Unsupported data type: {data_type}")

        # Make the API request
        data = self._request_data(params)

        # Parse the response based on data type
        try:
            if data_type == "forex":
                df = self._parse_forex_data(data, timeframe)
            else:  # stock
                df = self._parse_stock_data(data, timeframe)

            # Apply date filtering
            if start_date is not None or end_date is not None:
                # Convert string dates to datetime if needed
                if isinstance(start_date, str):
                    start_date = pd.to_datetime(start_date)
                if isinstance(end_date, str):
                    end_date = pd.to_datetime(end_date)

                # Filter by date
                if start_date is not None:
                    df = df[df.index >= start_date]
                if end_date is not None:
                    df = df[df.index <= end_date]

            logger.info(f"Retrieved {len(df)} rows of {timeframe} data for {symbol}")
            return df

        except Exception as e:
            logger.error(f"Error parsing Alpha Vantage data: {e}")
            raise

    def get_available_symbols(self) -> List[str]:
        """Get the list of available symbols.

        Returns:
            List of available symbols
        """
        return self.supported_symbols

    def get_available_timeframes(self) -> List[str]:
        """Get the list of available timeframes.

        Returns:
            List of available timeframes
        """
        return list(TIMEFRAME_MAPPING.keys())

    def get_available_economic_indicators(self) -> List[str]:
        """Get the list of available economic indicators.

        Returns:
            List of available economic indicators
        """
        return ECONOMIC_INDICATORS

    def get_available_commodities(self) -> List[str]:
        """Get the list of available commodity endpoints.

        Returns:
            List of available commodity endpoints
        """
        return COMMODITY_ENDPOINTS

    def search_symbol(self, keywords: str) -> pd.DataFrame:
        """Search for symbols based on keywords.

        Args:
            keywords: Keywords to search for

        Returns:
            DataFrame with search results

        Raises:
            ConnectionError: If the API request fails
        """
        params = {"function": "SYMBOL_SEARCH", "keywords": keywords}

        data = self._request_data(params)

        # Parse the search results
        if "bestMatches" in data:
            matches = data["bestMatches"]
            if not matches:
                return pd.DataFrame()

            results = []
            for match in matches:
                results.append(
                    {
                        "symbol": match.get("1. symbol", ""),
                        "name": match.get("2. name", ""),
                        "type": match.get("3. type", ""),
                        "region": match.get("4. region", ""),
                        "market_open": match.get("5. marketOpen", ""),
                        "market_close": match.get("6. marketClose", ""),
                        "timezone": match.get("7. timezone", ""),
                        "currency": match.get("8. currency", ""),
                        "match_score": float(match.get("9. matchScore", 0)),
                    }
                )

            return pd.DataFrame(results)
        else:
            logger.warning("No best matches found in Alpha Vantage search response")
            return pd.DataFrame()

    def get_exchange_rate(
        self, from_currency: str, to_currency: str
    ) -> Dict[str, float]:
        """Get current exchange rate between two currencies.

        Args:
            from_currency: From currency code
            to_currency: To currency code

        Returns:
            Dictionary with exchange rate data

        Raises:
            ConnectionError: If the API request fails
        """
        params = {
            "function": "CURRENCY_EXCHANGE_RATE",
            "from_currency": from_currency,
            "to_currency": to_currency,
        }

        data = self._request_data(params)

        # Parse the exchange rate data
        if "Realtime Currency Exchange Rate" in data:
            exchange_data = data["Realtime Currency Exchange Rate"]

            return {
                "from_currency": exchange_data.get("1. From_Currency Code", ""),
                "from_currency_name": exchange_data.get("2. From_Currency Name", ""),
                "to_currency": exchange_data.get("3. To_Currency Code", ""),
                "to_currency_name": exchange_data.get("4. To_Currency Name", ""),
                "exchange_rate": float(exchange_data.get("5. Exchange Rate", 0)),
                "last_refreshed": exchange_data.get("6. Last Refreshed", ""),
                "timezone": exchange_data.get("7. Time Zone", ""),
            }
        else:
            logger.warning("No exchange rate data found in Alpha Vantage response")
            return {}

    def clear_cache(self):
        """Clear the data cache."""
        self.cache = {}
        logger.info("Alpha Vantage data cache cleared")

    def get_economic_indicator(
        self,
        indicator: str,
        interval: str = None,
        outputsize: str = "compact",
        maturity: str = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Fetch economic indicator data from Alpha Vantage.

        Args:
            indicator: Economic indicator to fetch (e.g., "REAL_GDP", "INFLATION")
            interval: Data interval for indicators that support it (e.g., "daily", "weekly", "monthly", "quarterly", "annual")
            outputsize: Output size ("compact" or "full")
            maturity: Maturity for treasury yield data (e.g., "3month", "2year", "10year")
            **kwargs: Additional parameters to pass to the API

        Returns:
            DataFrame containing the economic indicator data

        Raises:
            ValueError: If the indicator is not supported or parameters are invalid
            ConnectionError: If the API request fails
        """
        # Set up request parameters
        params = {"function": indicator, "datatype": "json"}

        # Add interval if provided
        if interval:
            params["interval"] = interval

        # Add outputsize if applicable
        if outputsize:
            params["outputsize"] = outputsize

        # Add maturity for treasury yield data
        if maturity and indicator == "TREASURY_YIELD":
            params["maturity"] = maturity

        # Add any additional parameters
        for key, value in kwargs.items():
            params[key] = value

        # Make the API request
        data = self._request_data(params)

        # Parse the response based on the indicator
        try:
            # Extract the data section based on what's in the response
            data_key = next((k for k in data.keys() if k != "Meta Data"), None)

            if not data_key:
                raise ValueError(f"Could not find data in response for {indicator}")

            time_series = data[data_key]

            # Parse the time series data
            parsed_data = []
            for timestamp_str, values in time_series.items():
                timestamp = pd.to_datetime(timestamp_str)

                # Get the first value (different indicators have different field names)
                value_key = next(iter(values.keys()))
                value = float(values[value_key])

                parsed_data.append({"timestamp": timestamp, "value": value})

            # Convert to DataFrame
            df = pd.DataFrame(parsed_data)

            # Set timestamp as index and sort
            df = df.set_index("timestamp")
            df = df.sort_index()

            logger.info(f"Retrieved {len(df)} rows of {indicator} data")
            return df

        except Exception as e:
            logger.error(f"Error parsing Alpha Vantage economic data: {e}")
            raise

    def get_commodity_data(
        self,
        commodity: str,
        interval: str = "monthly",
        outputsize: str = "compact",
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Fetch commodity price data from Alpha Vantage.

        Args:
            commodity: Commodity to fetch (e.g., "WTI", "BRENT", "NATURAL_GAS", "COPPER")
            interval: Data interval ("daily", "weekly", "monthly", "quarterly", "annual")
            outputsize: Output size ("compact" or "full")
            **kwargs: Additional parameters to pass to the API

        Returns:
            DataFrame containing the commodity price data

        Raises:
            ValueError: If the commodity is not supported or parameters are invalid
            ConnectionError: If the API request fails
        """
        # Set up request parameters
        params = {"function": commodity, "interval": interval, "datatype": "json"}

        # Add outputsize if applicable
        if outputsize:
            params["outputsize"] = outputsize

        # Add any additional parameters
        for key, value in kwargs.items():
            params[key] = value

        # Make the API request
        data = self._request_data(params)

        # Parse the response
        try:
            # Extract the data section based on what's in the response
            data_key = next((k for k in data.keys() if k != "Meta Data"), None)

            if not data_key:
                raise ValueError(f"Could not find data in response for {commodity}")

            time_series = data[data_key]

            # Parse the time series data
            parsed_data = []
            for timestamp_str, values in time_series.items():
                timestamp = pd.to_datetime(timestamp_str)

                # Get the price value (different commodities may have different field names)
                value_key = next(iter(values.keys()))
                value = float(values[value_key])

                parsed_data.append({"timestamp": timestamp, "value": value})

            # Convert to DataFrame
            df = pd.DataFrame(parsed_data)

            # Set timestamp as index and sort
            df = df.set_index("timestamp")
            df = df.sort_index()

            logger.info(
                f"Retrieved {len(df)} rows of {commodity} data with {interval} interval"
            )
            return df

        except Exception as e:
            logger.error(f"Error parsing Alpha Vantage commodity data: {e}")
            raise
