#!/usr/bin/env python
"""
Test script for FRED API connection.

This script tests connectivity to the FRED API and
performs basic operations to validate the integration.
"""

import logging
import os
import sys
from datetime import datetime, timedelta

import pandas as pd
from dotenv import load_dotenv

# Add the parent directory to the sys.path to import fxml4
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fxml4.data_engineering.data_feeds.fred_feed import COMMON_INDICATORS, FREDDataFeed

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def test_fred_api_connection():
    """Test connection to FRED API and fetch some basic data."""
    # Get API key from environment variables
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        logger.error("FRED_API_KEY not found in environment variables")
        return False

    logger.info("Initializing FRED data feed...")
    try:
        fred_feed = FREDDataFeed(config={"api_key": api_key})
        logger.info("FRED data feed initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize FRED data feed: {e}")
        return False

    # Test getting available series
    logger.info("Getting available series...")
    try:
        series_list = fred_feed.get_available_series()
        logger.info(f"Retrieved {len(series_list)} series")

        # Display the first few series
        if series_list:
            logger.info("Sample series:")
            for i, series in enumerate(series_list[:5]):
                logger.info(
                    f"  {i+1}. {series['name']} ({series['series_id']}): {series['title']}"
                )
    except Exception as e:
        logger.error(f"Failed to get available series: {e}")
        return False

    # Test getting a specific series
    logger.info("Testing retrieval of specific series...")
    for indicator_name, series_id in [
        ("UNEMPLOYMENT", "UNRATE"),
        ("GDP", "GDP"),
        ("CPI", "CPIAUCSL"),
        ("FED_FUNDS_RATE", "FEDFUNDS"),
    ]:
        try:
            logger.info(f"Fetching {indicator_name} (Series ID: {series_id})...")
            start_date = datetime.now() - timedelta(days=365 * 2)  # 2 years ago

            df = fred_feed.get_series(series_id=series_id, start_date=start_date)

            if df.empty:
                logger.warning(f"No data returned for {indicator_name}")
            else:
                logger.info(f"Retrieved {len(df)} data points for {indicator_name}")
                logger.info(
                    f"Latest data: {df['value'].iloc[-1]} ({df.index[-1].strftime('%Y-%m-%d')})"
                )
                logger.info(f"Metadata: {df.attrs}")
        except Exception as e:
            logger.error(f"Failed to get {indicator_name} data: {e}")

    # Test getting multiple series at once
    logger.info("Testing retrieval of multiple series...")
    try:
        multi_series = fred_feed.get_consolidated_series(
            series_ids=["UNRATE", "CPIAUCSL", "GDP", "FEDFUNDS"],
            start_date=datetime.now() - timedelta(days=365 * 5),  # 5 years ago
        )

        if multi_series.empty:
            logger.warning("No data returned for multiple series")
        else:
            logger.info(
                f"Retrieved data with {len(multi_series)} rows and {len(multi_series.columns)} columns"
            )
            logger.info(f"Columns: {multi_series.columns.tolist()}")
            logger.info(
                f"Date range: {multi_series.index[0]} to {multi_series.index[-1]}"
            )
    except Exception as e:
        logger.error(f"Failed to get multiple series: {e}")

    # Test getting economic calendar
    logger.info("Testing economic calendar retrieval...")
    try:
        calendar = fred_feed.get_economic_calendar()

        if calendar.empty:
            logger.warning("No upcoming releases found")
        else:
            logger.info(f"Retrieved {len(calendar)} upcoming releases")
            if len(calendar) > 0:
                logger.info("Next few releases:")
                for i, (_, release) in enumerate(calendar.head(5).iterrows()):
                    logger.info(
                        f"  {i+1}. {release.get('name', 'Unknown')} - {release.get('release_date', 'Unknown date')}"
                    )
    except Exception as e:
        logger.error(f"Failed to get economic calendar: {e}")

    logger.info("FRED API connection test completed")
    return True


def main():
    logger.info("Starting FRED API connection test")
    success = test_fred_api_connection()
    if success:
        logger.info("FRED API connection test passed")
        return 0
    else:
        logger.error("FRED API connection test failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
