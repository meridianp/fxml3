"""
FRED (Federal Reserve Economic Data) API client for FXML4.

This module provides functionality to fetch economic data from the Federal Reserve
Economic Data API and process it for integration into the FXML4 platform.
"""

import os
import logging
import json
from typing import Dict, List, Optional, Union, Any
from datetime import datetime, timedelta, timezone
import time

import pandas as pd
import numpy as np
import requests
from urllib.parse import urlencode

from .base_feed import DataFeed, DataFeedFactory

logger = logging.getLogger(__name__)

# FRED API endpoints
FRED_API_BASE_URL = "https://api.stlouisfed.org/fred"
SERIES_ENDPOINT = f"{FRED_API_BASE_URL}/series/observations"
SERIES_INFO_ENDPOINT = f"{FRED_API_BASE_URL}/series"
RELEASES_ENDPOINT = f"{FRED_API_BASE_URL}/releases"
CATEGORIES_ENDPOINT = f"{FRED_API_BASE_URL}/category/series"

# Common economic indicators and their FRED series IDs
COMMON_INDICATORS = {
    "GDP": "GDP",                   # Gross Domestic Product
    "RGDP": "GDPC1",                # Real Gross Domestic Product
    "UNEMPLOYMENT": "UNRATE",       # Unemployment Rate
    "CPI": "CPIAUCSL",              # Consumer Price Index for All Urban Consumers: All Items
    "CORE_CPI": "CPILFESL",         # Consumer Price Index for All Urban Consumers: All Items Less Food and Energy
    "PCE": "PCE",                   # Personal Consumption Expenditures
    "CORE_PCE": "PCEPILFE",         # Personal Consumption Expenditures Excluding Food and Energy
    "RETAIL_SALES": "RSXFS",        # Advance Retail Sales: Retail Trade
    "INDUSTRIAL_PRODUCTION": "INDPRO", # Industrial Production Index
    "HOUSING_STARTS": "HOUST",      # Housing Starts: Total: New Privately Owned Housing Units Started
    "FED_FUNDS_RATE": "FEDFUNDS",   # Federal Funds Effective Rate
    "10Y_TREASURY": "GS10",         # 10-Year Treasury Constant Maturity Rate
    "2Y_TREASURY": "GS2",           # 2-Year Treasury Constant Maturity Rate
    "10Y2Y_SPREAD": "T10Y2Y",       # 10-Year Treasury Constant Maturity Minus 2-Year Treasury Constant Maturity
    "10Y3M_SPREAD": "T10Y3M",       # 10-Year Treasury Constant Maturity Minus 3-Month Treasury Constant Maturity
    "USD_INDEX": "DTWEXBGS",        # Trade Weighted U.S. Dollar Index: Broad, Goods and Services
    "VIX": "VIXCLS",                # CBOE Volatility Index: VIX
    "M2_MONEY_SUPPLY": "M2SL",      # M2 Money Stock
    "HIGH_YIELD_SPREAD": "BAMLH0A0HYM2", # ICE BofA US High Yield Index Option-Adjusted Spread
    "RECESSION_PROB": "RECPROUSM156N", # Smoothed U.S. Recession Probabilities
}

# Frequency mapping
FREQUENCY_MAPPING = {
    'd': 'daily',
    'w': 'weekly',
    'bw': 'biweekly',
    'm': 'monthly',
    'q': 'quarterly',
    'sa': 'semiannual',
    'a': 'annual',
}


@DataFeedFactory.register("fred")
class FREDDataFeed(DataFeed):
    """Data feed for FRED (Federal Reserve Economic Data)."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the FRED data feed.
        
        Args:
            config: Configuration dictionary with the following keys:
                api_key: FRED API key
                use_cache: Whether to cache responses (default: True)
                cache_dir: Directory to store cache files (default: '.cache/fred')
                max_retries: Maximum number of retries for API requests (default: 3)
                retry_delay: Delay between retries in seconds (default: 1.0)
        """
        super().__init__(config)
        
        # Required configuration
        self.api_key = config.get("api_key", os.environ.get("FRED_API_KEY"))
        if not self.api_key:
            raise ValueError("FRED API key not provided. Set config['api_key'] or FRED_API_KEY environment variable.")
        
        # Optional configuration
        self.use_cache = config.get("use_cache", True)
        self.cache_dir = config.get("cache_dir", ".cache/fred")
        self.max_retries = config.get("max_retries", 3)
        self.retry_delay = config.get("retry_delay", 1.0)
        
        # Set up cache directory if needed
        if self.use_cache and not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)
        
        # Track API rate limits
        self.api_calls = 0
        self.api_call_limit = 120  # FRED allows 120 requests per minute
        self.api_call_reset_time = time.time() + 60  # Reset after 60 seconds
        
        logger.info(f"Initialized FRED data feed with API key: {self.api_key[:4]}***")
    
    def _make_api_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make an API request to FRED.
        
        Args:
            endpoint: API endpoint URL
            params: Query parameters
            
        Returns:
            JSON response as dictionary
            
        Raises:
            Exception: If the API request fails
        """
        # Add API key and format to parameters
        params["api_key"] = self.api_key
        params["file_type"] = "json"
        
        # Check cache first if enabled
        if self.use_cache:
            cache_key = f"{endpoint}_{urlencode(sorted(params.items()))}"
            cache_path = os.path.join(self.cache_dir, f"{hash(cache_key)}.json")
            
            if os.path.exists(cache_path):
                try:
                    with open(cache_path, 'r') as f:
                        cache_data = json.load(f)
                        if 'timestamp' in cache_data:
                            # Check if cache is less than 24 hours old
                            cache_time = cache_data['timestamp']
                            if time.time() - cache_time < 86400:  # 24 hours
                                logger.debug(f"Using cached response for {endpoint}")
                                return cache_data['data']
                except Exception as e:
                    logger.warning(f"Error reading cache: {e}")
        
        # Apply rate limiting
        self._apply_rate_limit()
        
        # Make request with retries
        for attempt in range(self.max_retries):
            try:
                response = requests.get(endpoint, params=params)
                response.raise_for_status()
                
                # Parse JSON response
                data = response.json()
                
                # Cache response if enabled
                if self.use_cache:
                    cache_data = {
                        'timestamp': time.time(),
                        'data': data
                    }
                    with open(cache_path, 'w') as f:
                        json.dump(cache_data, f)
                
                return data
            
            except Exception as e:
                logger.warning(f"API request failed (attempt {attempt+1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
                else:
                    raise Exception(f"Failed to fetch data from FRED after {self.max_retries} attempts: {e}")
    
    def _apply_rate_limit(self):
        """Apply API rate limiting."""
        current_time = time.time()
        
        # Reset counter if past reset time
        if current_time > self.api_call_reset_time:
            self.api_calls = 0
            self.api_call_reset_time = current_time + 60
        
        # Check if we're at the limit
        if self.api_calls >= self.api_call_limit:
            # Sleep until reset time
            sleep_time = max(0, self.api_call_reset_time - current_time)
            logger.warning(f"FRED API rate limit reached. Sleeping for {sleep_time:.2f} seconds.")
            time.sleep(sleep_time)
            self.api_calls = 0
            self.api_call_reset_time = time.time() + 60
        
        # Increment counter
        self.api_calls += 1
    
    def get_series(
        self,
        series_id: str,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        frequency: Optional[str] = None,
        aggregation_method: Optional[str] = None,
        **kwargs: Any
    ) -> pd.DataFrame:
        """
        Get time series data for a FRED series.
        
        Args:
            series_id: FRED series ID (e.g., "UNRATE" for unemployment rate)
            start_date: Start date for data (default: 5 years ago)
            end_date: End date for data (default: today)
            frequency: Data frequency ('d', 'w', 'm', 'q', 'sa', 'a')
            aggregation_method: Aggregation method for frequency conversion
                               ('avg', 'sum', 'eop')
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            DataFrame with time series data
            
        Raises:
            ValueError: If series_id is not provided
        """
        if not series_id:
            raise ValueError("series_id is required")
        
        # Process dates
        if start_date is None:
            start_date = datetime.now() - timedelta(days=365*5)  # 5 years ago
        if end_date is None:
            end_date = datetime.now()
        
        # Convert dates to strings if needed
        if isinstance(start_date, datetime):
            start_date = start_date.strftime("%Y-%m-%d")
        if isinstance(end_date, datetime):
            end_date = end_date.strftime("%Y-%m-%d")
        
        # Set up parameters
        params = {
            "series_id": series_id,
            "observation_start": start_date,
            "observation_end": end_date,
        }
        
        # Add optional parameters
        if frequency:
            params["frequency"] = frequency
        if aggregation_method:
            params["aggregation_method"] = aggregation_method
        
        # Add any additional parameters
        params.update(kwargs)
        
        # Make API request
        try:
            result = self._make_api_request(SERIES_ENDPOINT, params)
            
            # Get series information for metadata
            series_info = self._make_api_request(SERIES_INFO_ENDPOINT, {"series_id": series_id})
            
            # Process data
            observations = result.get("observations", [])
            if not observations:
                logger.warning(f"No data returned for series {series_id}")
                return pd.DataFrame()
            
            # Create DataFrame
            df = pd.DataFrame(observations)
            
            # Convert date to datetime
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
            
            # Convert value column to numeric
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            
            # Get metadata from series info
            metadata = {
                "series_id": series_id,
                "title": series_info.get("seriess", [{}])[0].get("title", ""),
                "units": series_info.get("seriess", [{}])[0].get("units", ""),
                "frequency": series_info.get("seriess", [{}])[0].get("frequency_short", ""),
                "seasonal_adjustment": series_info.get("seriess", [{}])[0].get("seasonal_adjustment_short", ""),
                "last_updated": series_info.get("seriess", [{}])[0].get("last_updated", "")
            }
            
            # Add metadata as attributes
            for key, value in metadata.items():
                df.attrs[key] = value
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to get FRED series {series_id}: {e}")
            raise
    
    def get_multiple_series(
        self,
        series_ids: List[str],
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        frequency: Optional[str] = None,
        **kwargs: Any
    ) -> Dict[str, pd.DataFrame]:
        """
        Get multiple time series at once.
        
        Args:
            series_ids: List of FRED series IDs
            start_date: Start date for data
            end_date: End date for data
            frequency: Data frequency
            **kwargs: Additional parameters
            
        Returns:
            Dictionary mapping series IDs to DataFrames
        """
        result = {}
        
        for series_id in series_ids:
            try:
                df = self.get_series(
                    series_id=series_id,
                    start_date=start_date,
                    end_date=end_date,
                    frequency=frequency,
                    **kwargs
                )
                result[series_id] = df
                
            except Exception as e:
                logger.error(f"Error fetching series {series_id}: {e}")
                result[series_id] = pd.DataFrame()
        
        return result
    
    def get_consolidated_series(
        self,
        series_ids: List[str],
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        frequency: Optional[str] = None,
        **kwargs: Any
    ) -> pd.DataFrame:
        """
        Get multiple time series and consolidate them into a single DataFrame.
        
        Args:
            series_ids: List of FRED series IDs
            start_date: Start date for data
            end_date: End date for data
            frequency: Data frequency
            **kwargs: Additional parameters
            
        Returns:
            DataFrame with all series as columns
        """
        # Get data for each series
        series_data = self.get_multiple_series(
            series_ids=series_ids,
            start_date=start_date,
            end_date=end_date,
            frequency=frequency,
            **kwargs
        )
        
        # Create empty DataFrame with date index
        all_dates = []
        for df in series_data.values():
            if not df.empty:
                all_dates.extend(df.index.tolist())
        
        if not all_dates:
            logger.warning("No data found for any series")
            return pd.DataFrame()
        
        # Create consolidated DataFrame with unique dates as index
        unique_dates = sorted(set(all_dates))
        result = pd.DataFrame(index=unique_dates)
        
        # Add each series as a column
        for series_id, df in series_data.items():
            if not df.empty:
                result[series_id] = df["value"]
        
        # Sort index
        result.sort_index(inplace=True)
        
        return result
    
    def get_indicator_by_name(
        self, 
        indicator_name: str,
        **kwargs: Any
    ) -> pd.DataFrame:
        """
        Get data for a common indicator by its name.
        
        Args:
            indicator_name: Name of the indicator (e.g., "UNEMPLOYMENT")
            **kwargs: Additional parameters for get_series()
            
        Returns:
            DataFrame with indicator data
            
        Raises:
            ValueError: If indicator_name is not in the common indicators list
        """
        if indicator_name not in COMMON_INDICATORS:
            valid_indicators = list(COMMON_INDICATORS.keys())
            raise ValueError(f"Unknown indicator: {indicator_name}. Valid indicators: {valid_indicators}")
        
        series_id = COMMON_INDICATORS[indicator_name]
        return self.get_series(series_id=series_id, **kwargs)
    
    def get_available_series(self) -> List[Dict[str, Any]]:
        """
        Get a list of common economic indicators available in FRED.
        
        Returns:
            List of dictionaries with indicator information
        """
        result = []
        
        for name, series_id in COMMON_INDICATORS.items():
            try:
                # Get series info
                series_info = self._make_api_request(
                    SERIES_INFO_ENDPOINT, 
                    {"series_id": series_id}
                )
                
                if "seriess" in series_info and series_info["seriess"]:
                    info = series_info["seriess"][0]
                    result.append({
                        "name": name,
                        "series_id": series_id,
                        "title": info.get("title", ""),
                        "frequency": info.get("frequency_short", ""),
                        "units": info.get("units", ""),
                        "seasonal_adjustment": info.get("seasonal_adjustment_short", ""),
                        "last_updated": info.get("last_updated", "")
                    })
            except Exception as e:
                logger.warning(f"Error getting info for series {series_id}: {e}")
        
        return result
    
    def get_economic_calendar(
        self,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None
    ) -> pd.DataFrame:
        """
        Get an economic calendar of upcoming and recent data releases.
        
        Args:
            start_date: Start date for releases (default: 7 days ago)
            end_date: End date for releases (default: 30 days from now)
            
        Returns:
            DataFrame with release information
        """
        # Set default dates
        if start_date is None:
            start_date = datetime.now() - timedelta(days=7)
        if end_date is None:
            end_date = datetime.now() + timedelta(days=30)
        
        # Convert dates to strings if needed
        if isinstance(start_date, datetime):
            start_date = start_date.strftime("%Y-%m-%d")
        if isinstance(end_date, datetime):
            end_date = end_date.strftime("%Y-%m-%d")
        
        # Get releases
        params = {
            "realtime_start": start_date,
            "realtime_end": end_date,
            "limit": 1000,
            "order_by": "release_date",
            "sort_order": "asc"
        }
        
        try:
            result = self._make_api_request(RELEASES_ENDPOINT, params)
            releases = result.get("releases", [])
            
            if not releases:
                logger.warning("No releases found in the specified date range")
                return pd.DataFrame()
            
            # Create DataFrame
            df = pd.DataFrame(releases)
            
            # Convert date columns to datetime
            for col in ["release_date", "last_updated"]:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col])
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to get economic calendar: {e}")
            return pd.DataFrame()
    
    def store_series_in_timescaledb(
        self,
        series_id: str,
        db_client,
        start_date: Optional[Union[str, datetime]] = None,
        **kwargs: Any
    ) -> int:
        """
        Fetch a series and store it in TimescaleDB.
        
        Args:
            series_id: FRED series ID
            db_client: TimescaleDB client instance
            start_date: Start date for data
            **kwargs: Additional parameters for get_series()
            
        Returns:
            Number of records stored
        """
        try:
            # Import the necessary module
            from fxml4.data_engineering.timescaledb import TimescaleDBClient
            
            # Check if db_client is a TimescaleDBClient
            if not isinstance(db_client, TimescaleDBClient):
                raise TypeError("db_client must be a TimescaleDBClient instance")
            
            # Get the series data
            df = self.get_series(series_id=series_id, start_date=start_date, **kwargs)
            
            if df.empty:
                logger.warning(f"No data returned for series {series_id}")
                return 0
            
            # Get series metadata
            metadata = {k: df.attrs.get(k) for k in df.attrs}
            
            # Get frequency string
            freq_code = metadata.get("frequency", "")
            frequency = FREQUENCY_MAPPING.get(freq_code, "unknown")
            
            # Prepare data for exogenous_data table
            records = []
            for timestamp, row in df.iterrows():
                records.append({
                    "time": timestamp,
                    "source": "fred",
                    "indicator_name": series_id,
                    "value": row["value"],
                    "frequency": frequency,
                    "metadata": json.dumps(metadata)
                })
            
            # Create table if it doesn't exist
            with db_client.get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if exogenous_data table exists
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'exogenous_data'
                    );
                """)
                
                table_exists = cursor.fetchone()[0]
                
                if not table_exists:
                    # Create the table
                    cursor.execute("""
                        CREATE TABLE exogenous_data (
                            time TIMESTAMPTZ NOT NULL,
                            source TEXT NOT NULL,
                            indicator_name TEXT NOT NULL,
                            value DOUBLE PRECISION NOT NULL,
                            frequency TEXT NOT NULL,
                            metadata JSONB,
                            
                            PRIMARY KEY (time, source, indicator_name)
                        );
                    """)
                    
                    # Convert to hypertable
                    cursor.execute("""
                        SELECT create_hypertable('exogenous_data', 'time');
                    """)
                    
                    # Create index
                    cursor.execute("""
                        CREATE INDEX idx_exogenous_data_indicator 
                        ON exogenous_data (indicator_name, time DESC);
                    """)
                    
                    conn.commit()
                
                # Insert data in batches
                batch_size = 1000
                for i in range(0, len(records), batch_size):
                    batch = records[i:i+batch_size]
                    
                    values_str = []
                    params = []
                    
                    for record in batch:
                        values_str.append("(%s, %s, %s, %s, %s, %s::jsonb)")
                        params.extend([
                            record["time"],
                            record["source"],
                            record["indicator_name"],
                            record["value"],
                            record["frequency"],
                            record["metadata"]
                        ])
                    
                    query = f"""
                        INSERT INTO exogenous_data 
                            (time, source, indicator_name, value, frequency, metadata)
                        VALUES {','.join(values_str)}
                        ON CONFLICT (time, source, indicator_name) 
                        DO UPDATE SET 
                            value = EXCLUDED.value,
                            frequency = EXCLUDED.frequency,
                            metadata = EXCLUDED.metadata
                    """
                    
                    cursor.execute(query, params)
                    conn.commit()
            
            return len(records)
            
        except Exception as e:
            logger.error(f"Error storing series {series_id} in TimescaleDB: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return 0