#!/usr/bin/env python
"""
Test script for FRED API integration with TimescaleDB.

This script tests storing and retrieving FRED data from TimescaleDB.
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
from fxml4.data_engineering.timescaledb import TimescaleDBClient

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def test_fred_timescaledb_integration():
    """Test integration between FRED API and TimescaleDB."""
    # Get API key from environment variables
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        logger.error("FRED_API_KEY not found in environment variables")
        return False

    # Initialize FRED data feed
    logger.info("Initializing FRED data feed...")
    try:
        fred_feed = FREDDataFeed(config={"api_key": api_key})
        logger.info("FRED data feed initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize FRED data feed: {e}")
        return False

    # Initialize TimescaleDB client
    logger.info("Initializing TimescaleDB client...")
    try:
        host = os.environ.get("TIMESCALEDB_HOST", "localhost")
        port = int(os.environ.get("TIMESCALEDB_PORT", "5432"))
        dbname = os.environ.get("TIMESCALEDB_DATABASE", "fxml4")
        user = os.environ.get("TIMESCALEDB_USER", "postgres")
        password = os.environ.get("TIMESCALEDB_PASSWORD", "postgres")

        db_client = TimescaleDBClient(
            host=host, port=port, dbname=dbname, user=user, password=password
        )
        logger.info(f"TimescaleDB client initialized: {host}:{port}/{dbname}")
    except Exception as e:
        logger.error(f"Failed to initialize TimescaleDB client: {e}")
        return False

    # Test storing and retrieving data for key economic indicators
    indicators_to_test = [
        # (Indicator name, Series ID, Frequency)
        ("UNEMPLOYMENT", "UNRATE", "monthly"),
        ("CPI", "CPIAUCSL", "monthly"),
        ("GDP", "GDP", "quarterly"),
        ("FED_FUNDS_RATE", "FEDFUNDS", "daily"),
    ]

    # Store indicator data in TimescaleDB
    logger.info("Testing storage and retrieval of economic indicators...")

    for indicator_name, series_id, freq in indicators_to_test:
        try:
            # Store data in TimescaleDB
            logger.info(
                f"Storing {indicator_name} (Series ID: {series_id}) in TimescaleDB..."
            )

            # Determine the appropriate start date based on frequency
            if freq == "daily":
                start_date = datetime.now() - timedelta(days=90)  # 90 days
            elif freq == "monthly":
                start_date = datetime.now() - timedelta(days=365 * 3)  # 3 years
            else:  # quarterly or less frequent
                start_date = datetime.now() - timedelta(days=365 * 10)  # 10 years

            # Store data
            record_count = fred_feed.store_series_in_timescaledb(
                series_id=series_id, db_client=db_client, start_date=start_date
            )

            logger.info(f"Stored {record_count} records for {indicator_name}")

            if record_count == 0:
                logger.warning(f"No records stored for {indicator_name}")

        except Exception as e:
            logger.error(f"Failed to store {indicator_name} data: {e}")

    # Query the stored data to verify it's accessible
    logger.info("Verifying stored data...")

    try:
        # Connect to the database
        with db_client.get_connection() as conn:
            cursor = conn.cursor()

            # Check if exogenous_data table exists and has data
            cursor.execute(
                """
                SELECT COUNT(*) FROM exogenous_data
                WHERE source = 'fred';
            """
            )

            count = cursor.fetchone()[0]
            logger.info(f"Found {count} FRED records in exogenous_data table")

            if count == 0:
                logger.warning("No FRED data found in the database")
                return False

            # Query for each indicator to verify data
            for _, series_id, _ in indicators_to_test:
                cursor.execute(
                    """
                    SELECT
                        time,
                        indicator_name,
                        value,
                        frequency
                    FROM exogenous_data
                    WHERE
                        source = 'fred' AND
                        indicator_name = %s
                    ORDER BY time DESC
                    LIMIT 5;
                """,
                    (series_id,),
                )

                rows = cursor.fetchall()

                if not rows:
                    logger.warning(f"No data found for {series_id}")
                else:
                    logger.info(f"Found {len(rows)} records for {series_id}")
                    logger.info(f"Latest data: {rows[0][0]} - {rows[0][2]}")

    except Exception as e:
        logger.error(f"Error verifying stored data: {e}")
        return False

    logger.info("FRED-TimescaleDB integration test completed")
    return True


def main():
    logger.info("Starting FRED-TimescaleDB integration test")
    success = test_fred_timescaledb_integration()
    if success:
        logger.info("FRED-TimescaleDB integration test passed")
        return 0
    else:
        logger.error("FRED-TimescaleDB integration test failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
