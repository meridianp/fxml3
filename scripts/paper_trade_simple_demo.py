#!/usr/bin/env python3
"""Simple paper trading demo with IB API."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import logging
import signal
import threading
import time
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Import IB API
from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.wrapper import EWrapper


class PaperTrader(EWrapper, EClient):
    """Simple paper trader using 100:1 leverage strategy."""

    def __init__(self):
        EClient.__init__(self, self)
        self.connected = False
        self.next_order_id = None
        self.positions = {}
        self.account_info = {}
        self.market_data = {}
        self.pending_orders = {}
        self.completed_orders = {}

        # Load 100x model predictions
        self.load_model_config()

        # Trading parameters
        self.leverage = 100
        self.risk_per_trade = 0.015  # 1.5% risk
        self.min_lot = 1000  # Micro lot

    def load_model_config(self):
        """Load 100x model configuration."""
        config_path = Path("models/GBPUSD_100x_simple/config.json")
        if config_path.exists():
            with open(config_path, "r") as f:
                self.model_config = json.load(f)
                logger.info(
                    f"Loaded GBPUSD model - Accuracy: {self.model_config['accuracy']:.1%}"
                )
        else:
            logger.warning("No model config found")
            self.model_config = None

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        """Handle errors."""
        if errorCode in [2104, 2106, 2158]:  # Ignore market data farm messages
            return
        logger.error(f"Error {errorCode}: {errorString}")

    def nextValidId(self, orderId):
        """Connected and received next order ID."""
        self.next_order_id = orderId
        self.connected = True
        logger.info(f"Connected! Next order ID: {orderId}")

        # Request account info
        self.reqAccountSummary(
            1, "All", "NetLiquidation,TotalCashValue,BuyingPower,GrossPositionValue"
        )

        # Request positions
        self.reqPositions()

    def accountSummary(self, reqId, account, tag, value, currency):
        """Receive account info."""
        self.account_info[tag] = float(value) if value else 0
        logger.info(f"{tag}: ${float(value):,.2f} {currency}")

    def accountSummaryEnd(self, reqId):
        """Account summary complete."""
        logger.info("Account info received")

        # Start market data for GBPUSD
        contract = self.create_forex_contract("GBPUSD")
        self.reqMktData(1, contract, "", False, False, [])

    def position(self, account, contract, position, avgCost):
        """Receive position info."""
        symbol = f"{contract.symbol}{contract.currency}"
        self.positions[symbol] = {
            "size": position,
            "avg_cost": avgCost,
            "current_price": 0,
            "unrealized_pnl": 0,
        }
        logger.info(f"Position: {symbol} - {position:,.0f} units @ {avgCost:.5f}")

    def positionEnd(self):
        """All positions received."""
        logger.info(f"Total positions: {len(self.positions)}")

    def tickPrice(self, reqId, tickType, price, attrib):
        """Receive price tick."""
        # Store bid/ask prices
        if tickType == 1:  # Bid
            self.market_data["bid"] = price
        elif tickType == 2:  # Ask
            self.market_data["ask"] = price
        elif tickType == 4:  # Last
            self.market_data["last"] = price

        # Update position P&L if we have a position
        if "GBPUSD" in self.positions and "last" in self.market_data:
            pos = self.positions["GBPUSD"]
            pos["current_price"] = self.market_data["last"]
            pos["unrealized_pnl"] = (pos["current_price"] - pos["avg_cost"]) * pos[
                "size"
            ]

    def create_forex_contract(self, symbol):
        """Create forex contract."""
        contract = Contract()
        contract.symbol = symbol[:3]
        contract.secType = "CASH"
        contract.currency = symbol[3:]
        contract.exchange = "IDEALPRO"
        return contract

    def place_order(self, action, quantity):
        """Place a market order."""
        if not self.connected or self.next_order_id is None:
            logger.error("Not connected")
            return

        # Create contract
        contract = self.create_forex_contract("GBPUSD")

        # Create order
        order = Order()
        order.action = action  # "BUY" or "SELL"
        order.totalQuantity = quantity
        order.orderType = "MKT"

        # Place order
        order_id = self.next_order_id
        self.placeOrder(order_id, contract, order)
        self.next_order_id += 1

        logger.info(f"Placed {action} order for {quantity:,} units of GBPUSD")

        # Store pending order
        self.pending_orders[order_id] = {
            "symbol": "GBPUSD",
            "action": action,
            "quantity": quantity,
            "status": "PENDING",
        }

    def orderStatus(
        self,
        orderId,
        status,
        filled,
        remaining,
        avgFillPrice,
        permId,
        parentId,
        lastFillPrice,
        clientId,
        whyHeld,
        mktCapPrice,
    ):
        """Order status update."""
        if orderId in self.pending_orders:
            self.pending_orders[orderId]["status"] = status
            self.pending_orders[orderId]["filled"] = filled
            self.pending_orders[orderId]["avg_price"] = avgFillPrice

            logger.info(
                f"Order {orderId} - Status: {status}, Filled: {filled:,} @ {avgFillPrice:.5f}"
            )

            if status in ["Filled", "Cancelled"]:
                # Move to completed
                self.completed_orders[orderId] = self.pending_orders.pop(orderId)

    def calculate_position_size(self):
        """Calculate position size for 100:1 leverage."""
        if "NetLiquidation" not in self.account_info:
            return 0

        account_value = self.account_info["NetLiquidation"]
        risk_amount = account_value * self.risk_per_trade

        # Assume 10 pip stop loss
        stop_pips = 10
        pip_value = 0.0001  # For GBPUSD

        # Position size = Risk Amount / (Stop Loss in Pips * Pip Value)
        # With 100:1 leverage, we can control large positions
        position_size = risk_amount / (stop_pips * pip_value)

        # Round to nearest micro lot (1000 units)
        position_size = round(position_size / 1000) * 1000

        # Apply leverage limit
        max_position = account_value * self.leverage
        position_size = min(position_size, max_position)

        return int(position_size)


def main():
    """Main trading loop."""
    # Create trader
    trader = PaperTrader()

    # Connect to IB
    logger.info("Connecting to IB API...")
    trader.connect("127.0.0.1", 4002, 1)

    # Start API thread
    api_thread = threading.Thread(target=trader.run, daemon=True)
    api_thread.start()

    # Wait for connection
    timeout = 10
    start = time.time()
    while not trader.connected and time.time() - start < timeout:
        time.sleep(0.1)

    if not trader.connected:
        logger.error("Failed to connect to IB API")
        return 1

    # Signal handler for clean shutdown
    running = True

    def signal_handler(sig, frame):
        nonlocal running
        logger.info("Shutting down...")
        running = False

    signal.signal(signal.SIGINT, signal_handler)

    # Trading loop
    last_trade_time = 0
    trade_cooldown = 300  # 5 minutes between trades

    logger.info("\n" + "=" * 60)
    logger.info("PAPER TRADING WITH 100:1 LEVERAGE")
    logger.info("=" * 60)
    logger.info("Press Ctrl+C to stop")
    logger.info("")

    while running:
        try:
            current_time = time.time()

            # Print status every 30 seconds
            if int(current_time) % 30 == 0:
                if trader.account_info:
                    logger.info(
                        f"\n--- Status Update {datetime.now().strftime('%H:%M:%S')} ---"
                    )
                    logger.info(
                        f"Account Value: ${trader.account_info.get('NetLiquidation', 0):,.2f}"
                    )

                    if trader.market_data:
                        bid = trader.market_data.get("bid", 0)
                        ask = trader.market_data.get("ask", 0)
                        spread = (ask - bid) * 10000 if bid and ask else 0
                        logger.info(
                            f"GBPUSD: Bid={bid:.5f}, Ask={ask:.5f}, Spread={spread:.1f} pips"
                        )

                    if trader.positions:
                        for symbol, pos in trader.positions.items():
                            if pos["size"] != 0:
                                logger.info(
                                    f"Position: {symbol} - {pos['size']:,.0f} units, "
                                    f"P&L: ${pos['unrealized_pnl']:,.2f}"
                                )

            # Demo trading logic (every 5 minutes)
            if current_time - last_trade_time > trade_cooldown:
                if "bid" in trader.market_data and "ask" in trader.market_data:
                    # Simple demo: alternate between buy and sell
                    current_position = trader.positions.get("GBPUSD", {}).get("size", 0)

                    if current_position == 0:
                        # No position - open one
                        position_size = trader.calculate_position_size()
                        if position_size > 0:
                            # Demo: randomly buy or sell
                            import random

                            action = random.choice(["BUY", "SELL"])
                            logger.info(
                                f"\n*** TRADING SIGNAL: {action} {position_size:,} units ***"
                            )
                            trader.place_order(action, position_size)
                            last_trade_time = current_time
                    else:
                        # Have position - close it
                        action = "SELL" if current_position > 0 else "BUY"
                        quantity = abs(current_position)
                        logger.info(
                            f"\n*** CLOSING POSITION: {action} {quantity:,} units ***"
                        )
                        trader.place_order(action, quantity)
                        last_trade_time = current_time

            time.sleep(1)

        except Exception as e:
            logger.error(f"Error in trading loop: {e}")

    # Disconnect
    trader.disconnect()
    logger.info("Disconnected from IB API")

    return 0


if __name__ == "__main__":
    sys.exit(main())
