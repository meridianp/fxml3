#!/usr/bin/env python3
"""Test Interactive Brokers connection with local ibapi."""

import logging
import os
import sys
import threading
import time
from datetime import datetime

# Add parent directory to path to find local ibapi
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Import IB API
try:
    from ibapi.client import EClient
    from ibapi.contract import Contract
    from ibapi.order import Order
    from ibapi.wrapper import EWrapper

    logger.info("IB API loaded successfully")
except ImportError as e:
    logger.error(f"Failed to import IB API: {e}")
    sys.exit(1)


class TestApp(EWrapper, EClient):
    """Simple IB API test application."""

    def __init__(self):
        EClient.__init__(self, self)
        self.connected = False
        self.nextOrderId = None
        self.account_data = {}

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        """Handle errors from IB."""
        if errorCode == 502:
            logger.error("Cannot connect to TWS. Please ensure TWS/Gateway is running.")
        elif errorCode == 504:
            logger.error("Not connected to TWS.")
        elif errorCode in [2104, 2106, 2158]:
            # Ignore market data farm messages
            pass
        else:
            logger.error(f"Error {errorCode}: {errorString}")

    def nextValidId(self, orderId):
        """Receive next valid order ID."""
        self.nextOrderId = orderId
        self.connected = True
        logger.info(f"Connected! Next order ID: {orderId}")

        # Request account data
        self.reqAccountSummary(1, "All", "NetLiquidation,TotalCashValue,BuyingPower")

    def accountSummary(self, reqId, account, tag, value, currency):
        """Receive account summary."""
        logger.info(f"Account {account} - {tag}: {value} {currency}")
        self.account_data[tag] = value

    def accountSummaryEnd(self, reqId):
        """Account summary complete."""
        logger.info("Account summary received")

        # Create a test forex contract
        contract = Contract()
        contract.symbol = "GBP"
        contract.secType = "CASH"
        contract.currency = "USD"
        contract.exchange = "IDEALPRO"

        # Request market data
        self.reqMktData(1, contract, "", False, False, [])

    def tickPrice(self, reqId, tickType, price, attrib):
        """Receive price tick."""
        from ibapi.ticktype import TickTypeEnum

        tick_name = TickTypeEnum.to_str(tickType)
        logger.info(f"Price tick - {tick_name}: {price}")

    def tickSize(self, reqId, tickType, size):
        """Receive size tick."""
        from ibapi.ticktype import TickTypeEnum

        tick_name = TickTypeEnum.to_str(tickType)
        logger.info(f"Size tick - {tick_name}: {size}")


def main():
    """Test IB connection."""
    # Parse arguments
    import argparse

    parser = argparse.ArgumentParser(description="Test IB API connection")
    parser.add_argument("--port", type=int, default=4002, help="IB API port")
    parser.add_argument("--host", default="127.0.0.1", help="IB API host")
    parser.add_argument("--client-id", type=int, default=1, help="Client ID")
    args = parser.parse_args()

    # Create app
    app = TestApp()

    # Connect
    logger.info(f"Connecting to IB API at {args.host}:{args.port}")
    app.connect(args.host, args.port, args.client_id)

    # Start message processing thread
    api_thread = threading.Thread(target=app.run, daemon=True)
    api_thread.start()

    # Wait for connection
    timeout = 10
    start_time = time.time()
    while not app.connected and time.time() - start_time < timeout:
        time.sleep(0.1)

    if not app.connected:
        logger.error("Failed to connect to IB API")
        logger.error("Please ensure:")
        logger.error("1. TWS or IB Gateway is running")
        logger.error("2. API connections are enabled in TWS/Gateway")
        logger.error("3. Port 4002 is configured for API connections")
        logger.error("4. 'Enable ActiveX and Socket Clients' is checked")
        return 1

    # Let it run for a few seconds to receive data
    logger.info("Receiving data...")
    time.sleep(5)

    # Disconnect
    app.disconnect()
    logger.info("Test complete!")

    # Summary
    if app.account_data:
        logger.info("\nAccount Summary:")
        for key, value in app.account_data.items():
            logger.info(f"  {key}: {value}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
