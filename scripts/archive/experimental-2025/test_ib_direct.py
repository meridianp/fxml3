#!/usr/bin/env python3
"""
Interactive Brokers TWS API direct test using previously successful code.

This script tests fetching and saving historical data from Interactive Brokers.
"""

import argparse
import logging
import os
import time
from datetime import datetime, timedelta
from threading import Thread

import pandas as pd
import pytz

from ibapi.client import EClient
from ibapi.common import BarData
from ibapi.contract import Contract
from ibapi.wrapper import EWrapper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class IBApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.data = []
        self.data_received = False

    def historicalData(self, reqId, bar):
        self.data.append([bar.date, bar.open, bar.high, bar.low, bar.close, bar.volume])
        logger.debug(
            f"Received bar: {bar.date} - OHLC: {bar.open}/{bar.high}/{bar.low}/{bar.close}"
        )

    def historicalDataEnd(self, reqId, start, end):
        logger.info(
            f"Historical data retrieval completed - received {len(self.data)} bars"
        )
        self.data_received = True

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        logger.error(f"Error {errorCode}: {errorString}")


def test_fetch_data(
    symbol: str,
    host: str = "127.0.0.1",
    port: int = 7496,
    duration: str = "1 D",
    bar_size: str = "1 hour",
    print_only: bool = True,
    save_path: str = None,
):
    app = IBApp()
    app.connect(host, port, 0)  # Connect to TWS or IB Gateway using client ID 0

    # Start the socket in a separate thread
    api_thread = Thread(target=app.run)
    api_thread.start()
    logger.info(f"Connecting to IB API at {host}:{port}")
    time.sleep(1)  # Give time for connection to establish

    # Define the contract
    contract = Contract()

    # Handle both formats: GBPUSD and GBP.USD
    if "." in symbol:
        base_currency = symbol.split(".")[0]
        quote_currency = symbol.split(".")[1]
    else:
        base_currency = symbol[:3]
        quote_currency = symbol[3:]

    contract.symbol = base_currency
    contract.secType = "CASH"
    contract.currency = quote_currency
    contract.exchange = "IDEALPRO"

    logger.info(
        f"Created Forex contract - Base: {base_currency}, Quote: {quote_currency}"
    )

    # Clear previous data
    app.data = []
    app.data_received = False

    # Request historical data
    end_date_str = datetime.now().strftime("%Y%m%d %H:%M:%S")
    end_date_with_tz = f"{end_date_str} US/Eastern"
    logger.info(f"Requesting {bar_size} data for {symbol} with duration {duration}")
    logger.info(f"End time: {end_date_with_tz}")

    app.reqHistoricalData(
        1, contract, end_date_with_tz, duration, bar_size, "MIDPOINT", 1, 1, False, []
    )

    # Wait for data to be retrieved
    max_wait_time = 30  # seconds
    wait_time = 0
    wait_interval = 0.5  # seconds

    while not app.data_received and wait_time < max_wait_time:
        time.sleep(wait_interval)
        wait_time += wait_interval

    # Process data
    if len(app.data) > 0:
        df = pd.DataFrame(
            app.data, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )

        # Format the timestamp based on the format returned by IB
        # Sometimes comes as "YYYYMMDD  HH:MM:SS" and sometimes as a unix timestamp
        if isinstance(df["timestamp"].iloc[0], str) and " " in df["timestamp"].iloc[0]:
            df["timestamp"] = pd.to_datetime(df["timestamp"], format="%Y%m%d  %H:%M:%S")
        else:
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")

        df = df.set_index("timestamp")
        df = df.sort_index()

        if print_only:
            logger.info(f"Retrieved {len(df)} bars of data for {symbol}:")
            logger.info(f"\n{df.head(10).to_string()}")

        if save_path:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            df.to_parquet(save_path, index=True, engine="pyarrow", compression="snappy")
            logger.info(f"Saved data to {save_path}")

        app.disconnect()
        return True
    else:
        logger.error(f"No data received for {symbol}")
        app.disconnect()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Test Interactive Brokers data retrieval"
    )
    parser.add_argument("--symbol", default="GBPUSD", help="Symbol to test")
    parser.add_argument("--host", default="127.0.0.1", help="TWS host")
    parser.add_argument("--port", type=int, default=7496, help="TWS port")
    parser.add_argument("--duration", default="1 D", help="Data duration")
    parser.add_argument("--bar-size", default="1 hour", help="Bar size")
    parser.add_argument("--save", action="store_true", help="Save data to file")
    args = parser.parse_args()

    save_path = None
    if args.save:
        save_path = f"./output/{args.symbol}_test_data.parquet"

    if test_fetch_data(
        args.symbol,
        args.host,
        args.port,
        args.duration,
        args.bar_size,
        print_only=not args.save,
        save_path=save_path,
    ):
        logger.info("Test completed successfully")
        return 0
    else:
        logger.error("Test failed")
        return 1


if __name__ == "__main__":
    main()
