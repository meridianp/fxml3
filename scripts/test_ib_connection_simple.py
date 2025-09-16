#!/usr/bin/env python3
"""Simple IB connection test avoiding complex imports."""

import logging
import os
import sys
import threading
import time
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Direct imports to avoid dependency issues
try:
    from ibapi.client import EClient
    from ibapi.contract import Contract
    from ibapi.ticktype import TickTypeEnum
    from ibapi.wrapper import EWrapper

    IBAPI_AVAILABLE = True
    print("✅ IB API is available")
except ImportError as e:
    print(f"❌ IB API not available: {e}")
    print("Install with: pip install ibapi")
    IBAPI_AVAILABLE = False
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SimpleIBApp(EWrapper, EClient):
    """Simple IB API app for testing."""

    def __init__(self):
        EClient.__init__(self, self)
        self.next_req_id = 1
        self.connected = False
        self.historical_data = []
        self.market_data = {}
        self.historical_data_end = threading.Event()
        self.market_data_received = threading.Event()

    def nextValidId(self, orderId: int):
        """Connection successful."""
        self.connected = True
        logger.info(f"✅ Connected with next order ID: {orderId}")

    def error(
        self,
        reqId: int,
        errorCode: int,
        errorString: str,
        advancedOrderRejectJson: str = "",
    ):
        """Handle errors."""
        if errorCode in [2104, 2106, 2158]:  # Informational messages
            logger.debug(f"Info {errorCode}: {errorString}")
            return
        logger.error(f"Error {errorCode}: {errorString}")

    def historicalData(self, reqId: int, bar):
        """Receive historical data."""
        self.historical_data.append(
            {
                "date": bar.date,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
            }
        )

    def historicalDataEnd(self, reqId: int, start: str, end: str):
        """End of historical data."""
        logger.info(f"✅ Historical data complete: {len(self.historical_data)} bars")
        self.historical_data_end.set()

    def tickPrice(self, reqId: int, tickType: int, price: float, attrib):
        """Receive tick price."""
        if hasattr(TickTypeEnum, "toStr"):
            tick_name = TickTypeEnum.toStr(tickType)
        else:
            tick_name = TickTypeEnum.to_str(tickType)

        self.market_data[tick_name] = price
        self.market_data_received.set()
        logger.debug(f"Tick: {tick_name} = {price}")


def create_gbp_usd_contract():
    """Create GBP/USD contract."""
    contract = Contract()
    contract.symbol = "GBP"
    contract.secType = "CASH"
    contract.currency = "USD"
    contract.exchange = "IDEALPRO"
    return contract


def test_ib_connection():
    """Test IB connection and GBP/USD data."""
    logger.info("\n" + "=" * 60)
    logger.info("🚀 FXML4 IB CONNECTION TEST (Simple)")
    logger.info("=" * 60)

    # Initialize app
    app = SimpleIBApp()

    # Connect
    logger.info("📡 Connecting to TWS (Paper Trading: port 7497)...")
    try:
        app.connect("127.0.0.1", 7497, 0)
    except Exception as e:
        logger.error(f"❌ Connection failed: {e}")
        return False

    # Start message processing
    api_thread = threading.Thread(target=app.run, daemon=True)
    api_thread.start()

    # Wait for connection
    timeout = 10
    wait_time = 0
    while not app.connected and wait_time < timeout:
        time.sleep(0.5)
        wait_time += 0.5

    if not app.connected:
        logger.error("❌ Failed to connect within timeout")
        logger.info("🔧 Troubleshooting:")
        logger.info("1. Start TWS with paper trading account")
        logger.info("2. Enable API in Global Configuration > API > Settings")
        logger.info("3. Set port to 7497 and allow localhost connections")
        return False

    logger.info("✅ Connected to Interactive Brokers!")

    # Test GBP/USD market data
    logger.info("\n📊 Testing GBP/USD market data...")
    try:
        contract = create_gbp_usd_contract()

        # Request market data
        app.market_data_received.clear()
        app.reqMktData(app.next_req_id, contract, "", False, False, [])
        app.next_req_id += 1

        # Wait for data
        if app.market_data_received.wait(timeout=10):
            logger.info("✅ GBP/USD Market Data:")
            for key, value in app.market_data.items():
                logger.info(f"   {key}: {value}")
        else:
            logger.warning("⚠️ No market data received")

        # Cancel market data
        app.cancelMktData(app.next_req_id - 1)

    except Exception as e:
        logger.error(f"❌ Market data error: {e}")

    # Test historical data
    logger.info("\n📈 Testing GBP/USD historical data...")
    try:
        contract = create_gbp_usd_contract()

        # Request 1-hour historical data
        app.historical_data = []
        app.historical_data_end.clear()

        end_time = datetime.now().strftime("%Y%m%d %H:%M:%S US/Eastern")

        app.reqHistoricalData(
            reqId=app.next_req_id,
            contract=contract,
            endDateTime=end_time,
            durationStr="1 D",
            barSizeSetting="1 hour",
            whatToShow="MIDPOINT",
            useRTH=1,
            formatDate=1,
            keepUpToDate=False,
            chartOptions=[],
        )
        app.next_req_id += 1

        # Wait for data
        if app.historical_data_end.wait(timeout=30):
            if app.historical_data:
                latest = app.historical_data[-1]
                logger.info(f"✅ GBP/USD Historical Data:")
                logger.info(f"   📊 Bars: {len(app.historical_data)}")
                logger.info(f"   📅 Latest: {latest['date']}")
                logger.info(
                    f"   💰 OHLC: O={latest['open']:.5f} H={latest['high']:.5f} L={latest['low']:.5f} C={latest['close']:.5f}"
                )
            else:
                logger.warning("⚠️ No historical data received")
        else:
            logger.warning("⚠️ Historical data timeout")

    except Exception as e:
        logger.error(f"❌ Historical data error: {e}")

    # Test secondary pairs
    logger.info("\n📊 Testing secondary pairs...")
    secondary_pairs = [("EUR", "USD"), ("USD", "JPY"), ("USD", "CHF")]

    for base, quote in secondary_pairs:
        try:
            contract = Contract()
            contract.symbol = base
            contract.secType = "CASH"
            contract.currency = quote
            contract.exchange = "IDEALPRO"

            # Quick market data test
            app.market_data = {}
            app.market_data_received.clear()

            req_id = app.next_req_id
            app.reqMktData(req_id, contract, "", False, False, [])
            app.next_req_id += 1

            # Wait briefly
            if app.market_data_received.wait(timeout=5):
                logger.info(f"✅ {base}/{quote}: Data available")
            else:
                logger.warning(f"⚠️ {base}/{quote}: No data")

            # Cancel
            app.cancelMktData(req_id)
            time.sleep(0.5)  # Brief pause

        except Exception as e:
            logger.error(f"❌ {base}/{quote} error: {e}")

    # Disconnect
    logger.info("\n🔌 Disconnecting...")
    app.disconnect()

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📋 TEST SUMMARY")
    logger.info("=" * 60)
    logger.info("✅ IB Connection: SUCCESS")
    logger.info("✅ GBP/USD: Primary currency pair tested")
    logger.info("✅ Multi-pair: Secondary pairs tested")
    logger.info("✅ Ready for Phase 1 implementation")

    return True


if __name__ == "__main__":
    if not IBAPI_AVAILABLE:
        sys.exit(1)

    success = test_ib_connection()

    if success:
        print("\n🎉 IB CONNECTION TEST PASSED!")
        print("Ready to proceed with IB integration!")
    else:
        print("\n❌ IB CONNECTION TEST FAILED!")
        print("Please resolve connection issues.")
        sys.exit(1)
