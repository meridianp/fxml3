#!/usr/bin/env python3
"""Simple test to verify IB connection and data fetching."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Import IB data fetcher
from fxml4.data.ib_mtf_data_fetcher import IBMultiTimeframeDataFetcher


def test_ib_connection():
    """Test basic IB connection and data fetching."""
    logger.info("\n" + "=" * 60)
    logger.info("TESTING INTERACTIVE BROKERS CONNECTION")
    logger.info("=" * 60)

    # Initialize IB data fetcher
    logger.info("\nConnecting to IB TWS API on port 4002...")
    fetcher = IBMultiTimeframeDataFetcher(host="127.0.0.1", port=4002, client_id=0)

    if not fetcher.connected:
        logger.error("Failed to connect to Interactive Brokers")
        logger.info("\nTroubleshooting:")
        logger.info("1. Make sure TWS or IB Gateway is running")
        logger.info("2. Enable API connections in TWS Global Configuration")
        logger.info("3. Add '127.0.0.1' to trusted IPs in API settings")
        logger.info("4. Check that port 4002 is correct for paper trading")
        return

    logger.info("✅ Successfully connected to Interactive Brokers!")

    # Test fetching data for GBPUSD
    symbol = "GBPUSD"
    timeframes = ["15m", "1H", "4H", "D"]

    logger.info(f"\nFetching multi-timeframe data for {symbol}...")
    logger.info(f"Timeframes: {', '.join(timeframes)}")

    try:
        data = fetcher.fetch_multi_timeframe_data(symbol=symbol, timeframes=timeframes)

        logger.info("\nData received:")
        for tf, df in data.items():
            if not df.empty:
                logger.info(f"\n{tf} timeframe:")
                logger.info(f"  - Bars: {len(df)}")
                logger.info(f"  - First: {df.index[0]}")
                logger.info(f"  - Last: {df.index[-1]}")
                logger.info(f"  - Latest close: {df['close'].iloc[-1]:.5f}")

                # Show last few bars
                logger.info(f"  - Last 3 bars:")
                for idx in range(-3, 0):
                    bar = df.iloc[idx]
                    logger.info(
                        f"    {df.index[idx]}: O={bar['open']:.5f} H={bar['high']:.5f} L={bar['low']:.5f} C={bar['close']:.5f}"
                    )
            else:
                logger.info(f"\n{tf} timeframe: No data received")

    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # Disconnect
        logger.info("\nDisconnecting from IB...")
        fetcher.disconnect()

    logger.info("\nTest complete!")


if __name__ == "__main__":
    test_ib_connection()
