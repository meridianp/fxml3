#!/usr/bin/env python3
"""Sophisticated ML-based paper trading for IB with 4:1 leverage."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import logging
import pickle
import signal
import threading
import time
from collections import deque
from datetime import datetime, timedelta
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


class MLPaperTrader(EWrapper, EClient):
    """Sophisticated ML-based paper trader optimized for 4:1 leverage."""

    def __init__(self):
        EClient.__init__(self, self)
        self.connected = False
        self.next_order_id = None
        self.positions = {}
        self.account_info = {}
        self.market_data = {}
        self.pending_orders = {}
        self.completed_orders = {}

        # Price history for feature calculation
        self.price_history = deque(maxlen=100)  # Keep last 100 prices
        self.bar_data = {}  # Store OHLC data

        # ML model components
        self.model = None
        self.scaler = None
        self.model_config = None
        self.load_ml_model()

        # Trading parameters optimized for 4:1 leverage
        self.max_leverage = 3.2  # Use 80% of available leverage
        self.risk_per_trade = 0.01  # 1% risk per trade
        self.min_confidence = 0.65  # 65% confidence threshold
        self.stop_loss_pips = 40  # Wider stop for 4:1 leverage
        self.take_profit_ratio = 2.0  # 2:1 reward:risk

        # Position management
        self.max_positions = 3
        self.position_cooldown = 300  # 5 minutes between trades
        self.last_trade_time = 0

        # Performance tracking
        self.trades_today = []
        self.daily_pnl = 0
        self.win_count = 0
        self.loss_count = 0

    def load_ml_model(self):
        """Load the ML model for predictions."""
        # Try to load GBPUSD model (our best performer)
        model_paths = [
            "models/GBPUSD_100x_simple",
            "models/GBPUSD_4h_model",
            "models/GBPUSD",
        ]

        for path in model_paths:
            model_path = Path(path)
            if model_path.exists():
                try:
                    # Load model
                    model_file = model_path / "model.pkl"
                    if not model_file.exists():
                        # Try other common names
                        for name in ["rf_model.pkl", "model.joblib"]:
                            if (model_path / name).exists():
                                model_file = model_path / name
                                break

                    with open(model_file, "rb") as f:
                        self.model = pickle.load(f)

                    # Load scaler
                    scaler_file = model_path / "scaler.pkl"
                    if scaler_file.exists():
                        with open(scaler_file, "rb") as f:
                            self.scaler = pickle.load(f)

                    # Load config
                    config_file = model_path / "config.json"
                    if config_file.exists():
                        with open(config_file, "r") as f:
                            self.model_config = json.load(f)

                    logger.info(f"Loaded ML model from {path}")
                    if self.model_config:
                        logger.info(
                            f"Model accuracy: {self.model_config.get('accuracy', 'N/A')}"
                        )
                    return True

                except Exception as e:
                    logger.error(f"Failed to load model from {path}: {e}")

        logger.warning("No ML model found - will use technical indicators only")
        return False

    def calculate_features(self):
        """Calculate features for ML prediction."""
        if len(self.price_history) < 50:
            return None

        try:
            # Convert price history to list
            prices = list(self.price_history)

            # Calculate returns
            returns_1 = (prices[-1] - prices[-2]) / prices[-2] if len(prices) > 1 else 0
            returns_2 = (prices[-1] - prices[-3]) / prices[-3] if len(prices) > 2 else 0
            returns_4 = (prices[-1] - prices[-5]) / prices[-5] if len(prices) > 4 else 0
            returns_8 = (prices[-1] - prices[-9]) / prices[-9] if len(prices) > 8 else 0

            # Calculate SMAs
            sma_8 = sum(prices[-8:]) / 8 if len(prices) >= 8 else prices[-1]
            sma_20 = sum(prices[-20:]) / 20 if len(prices) >= 20 else prices[-1]
            sma_50 = sum(prices[-50:]) / 50 if len(prices) >= 50 else prices[-1]

            # SMA slopes
            sma_8_slope = (
                (sma_8 - sum(prices[-12:-4]) / 8) / sma_8 if len(prices) >= 12 else 0
            )
            sma_20_slope = (
                (sma_20 - sum(prices[-24:-4]) / 20) / sma_20 if len(prices) >= 24 else 0
            )
            sma_50_slope = (
                (sma_50 - sum(prices[-54:-4]) / 50) / sma_50 if len(prices) >= 54 else 0
            )

            # RSI calculation
            gains = []
            losses = []
            for i in range(1, min(15, len(prices))):
                change = prices[-i] - prices[-i - 1]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))

            avg_gain = sum(gains) / len(gains) if gains else 0
            avg_loss = sum(losses) / len(losses) if losses else 0
            rs = avg_gain / avg_loss if avg_loss != 0 else 0
            rsi_14 = 100 - (100 / (1 + rs))

            # Volatility
            returns = [
                (prices[i] - prices[i - 1]) / prices[i - 1]
                for i in range(max(1, len(prices) - 20), len(prices))
            ]
            volatility = (
                (sum(r**2 for r in returns) / len(returns)) ** 0.5 if returns else 0
            )

            # ATR approximation
            atr = (
                sum(
                    abs(prices[i] - prices[i - 1])
                    for i in range(max(1, len(prices) - 14), len(prices))
                )
                / 14
            )

            # Time features
            now = datetime.now()
            hour = now.hour
            day_of_week = now.weekday()

            # Session indicators
            is_london = 1 if 8 <= hour < 16 else 0
            is_ny = 1 if 13 <= hour < 22 else 0
            is_asian = 1 if hour >= 23 or hour < 8 else 0

            # Create feature vector
            features = [
                returns_1,
                returns_2,
                returns_4,
                returns_8,
                sma_8_slope,
                sma_20_slope,
                sma_50_slope,
                rsi_14,
                volatility,
                atr,
                hour,
                day_of_week,
                is_london,
                is_ny,
                is_asian,
            ]

            return features

        except Exception as e:
            logger.error(f"Error calculating features: {e}")
            return None

    def generate_ml_signal(self):
        """Generate trading signal using ML model."""
        if not self.model:
            return self.generate_technical_signal()

        features = self.calculate_features()
        if features is None:
            return None

        try:
            # Scale features if scaler available
            import numpy as np

            X = np.array(features).reshape(1, -1)

            if self.scaler:
                X = self.scaler.transform(X)

            # Get prediction and probability
            prediction = self.model.predict(X)[0]

            # Get probability if available
            if hasattr(self.model, "predict_proba"):
                probabilities = self.model.predict_proba(X)[0]
                # Get confidence for the predicted class
                if prediction == 1:  # Long
                    confidence = (
                        probabilities[2] if len(probabilities) > 2 else probabilities[1]
                    )
                elif prediction == -1:  # Short
                    confidence = probabilities[0]
                else:  # No trade
                    confidence = 0
            else:
                confidence = 0.7  # Default confidence if not available

            if prediction != 0 and confidence >= self.min_confidence:
                return {
                    "direction": "BUY" if prediction > 0 else "SELL",
                    "confidence": confidence,
                    "source": "ML_MODEL",
                }

        except Exception as e:
            logger.error(f"Error generating ML signal: {e}")

        return None

    def generate_technical_signal(self):
        """Generate signal using technical indicators."""
        if len(self.price_history) < 50:
            return None

        try:
            prices = list(self.price_history)

            # Calculate indicators
            sma_20 = sum(prices[-20:]) / 20
            sma_50 = sum(prices[-50:]) / 50

            # Current price
            current_price = prices[-1]

            # Trend signal
            if current_price > sma_20 > sma_50:
                # Uptrend
                signal_direction = "BUY"
                confidence = 0.7
            elif current_price < sma_20 < sma_50:
                # Downtrend
                signal_direction = "SELL"
                confidence = 0.7
            else:
                return None

            # RSI filter
            features = self.calculate_features()
            if features:
                rsi = features[7]  # RSI is at index 7
                if signal_direction == "BUY" and rsi > 70:
                    return None  # Overbought
                elif signal_direction == "SELL" and rsi < 30:
                    return None  # Oversold

            return {
                "direction": signal_direction,
                "confidence": confidence,
                "source": "TECHNICAL",
            }

        except Exception as e:
            logger.error(f"Error generating technical signal: {e}")
            return None

    def calculate_position_size(self):
        """Calculate optimal position size for 4:1 leverage."""
        if "NetLiquidation" not in self.account_info:
            return 0

        account_value = self.account_info["NetLiquidation"]
        risk_amount = account_value * self.risk_per_trade

        # Position sizing with stop loss
        pip_value = 0.0001  # GBPUSD
        stop_loss_value = self.stop_loss_pips * pip_value

        # Calculate position size
        if "last" in self.market_data:
            current_price = self.market_data["last"]
            position_size = risk_amount / (stop_loss_value * current_price)
        else:
            position_size = risk_amount / stop_loss_value

        # Apply leverage constraint
        max_position_value = account_value * self.max_leverage
        max_position_size = max_position_value / 1.34  # Approximate GBPUSD rate

        position_size = min(position_size, max_position_size)

        # Round to nearest 1000 units
        position_size = round(position_size / 1000) * 1000

        # Minimum position size
        position_size = max(position_size, 25000)  # Minimum 25k units

        return int(position_size)

    def place_trade(self, signal):
        """Place a trade based on signal."""
        if not self.connected or self.next_order_id is None:
            return

        # Check position limits
        current_position = self.positions.get("GBPUSD", {}).get("size", 0)
        if len(self.pending_orders) > 0 or abs(current_position) > 0:
            logger.info("Already have position or pending order")
            return

        # Check cooldown
        if time.time() - self.last_trade_time < self.position_cooldown:
            return

        # Calculate position size
        position_size = self.calculate_position_size()
        if position_size == 0:
            return

        # Create contract
        contract = self.create_forex_contract("GBPUSD")

        # Create market order
        order = Order()
        order.action = signal["direction"]
        order.totalQuantity = position_size
        order.orderType = "MKT"

        # Place order
        order_id = self.next_order_id
        self.placeOrder(order_id, contract, order)
        self.next_order_id += 1

        # Log trade
        current_price = self.market_data.get("last", 0)
        logger.info(f"\n{'='*60}")
        logger.info(f"TRADE SIGNAL - {datetime.now().strftime('%H:%M:%S')}")
        logger.info(f"{'='*60}")
        logger.info(f"Direction: {signal['direction']}")
        logger.info(f"Confidence: {signal['confidence']:.1%}")
        logger.info(f"Source: {signal['source']}")
        logger.info(f"Position Size: {position_size:,} units")
        logger.info(f"Entry Price: {current_price:.5f}")
        logger.info(f"Stop Loss: {self.stop_loss_pips} pips")
        logger.info(f"Take Profit: {self.stop_loss_pips * self.take_profit_ratio} pips")
        logger.info(
            f"Risk: ${self.account_info.get('NetLiquidation', 0) * self.risk_per_trade:,.2f}"
        )
        logger.info(f"{'='*60}")

        # Store pending order
        self.pending_orders[order_id] = {
            "symbol": "GBPUSD",
            "action": signal["direction"],
            "quantity": position_size,
            "entry_price": current_price,
            "stop_loss": current_price
            - (
                self.stop_loss_pips
                * 0.0001
                * (1 if signal["direction"] == "BUY" else -1)
            ),
            "take_profit": current_price
            + (
                self.stop_loss_pips
                * self.take_profit_ratio
                * 0.0001
                * (1 if signal["direction"] == "BUY" else -1)
            ),
            "status": "PENDING",
            "timestamp": datetime.now(),
        }

        self.last_trade_time = time.time()

    def check_exit_conditions(self):
        """Check if current position should be closed."""
        if "GBPUSD" not in self.positions:
            return

        position = self.positions["GBPUSD"]
        if position["size"] == 0:
            return

        current_price = self.market_data.get("last", 0)
        if current_price == 0:
            return

        # Find the original order info
        for order_id, order_info in self.completed_orders.items():
            if order_info.get("quantity", 0) == abs(position["size"]):
                entry_price = order_info.get("entry_price", position["avg_cost"])
                stop_loss = order_info.get("stop_loss")
                take_profit = order_info.get("take_profit")

                # Check stop loss
                if position["size"] > 0:  # Long position
                    if current_price <= stop_loss:
                        logger.info(
                            f"STOP LOSS HIT - Closing long position at {current_price:.5f}"
                        )
                        self.close_position("SELL", abs(position["size"]))
                        self.loss_count += 1
                    elif current_price >= take_profit:
                        logger.info(
                            f"TAKE PROFIT HIT - Closing long position at {current_price:.5f}"
                        )
                        self.close_position("SELL", abs(position["size"]))
                        self.win_count += 1
                else:  # Short position
                    if current_price >= stop_loss:
                        logger.info(
                            f"STOP LOSS HIT - Closing short position at {current_price:.5f}"
                        )
                        self.close_position("BUY", abs(position["size"]))
                        self.loss_count += 1
                    elif current_price <= take_profit:
                        logger.info(
                            f"TAKE PROFIT HIT - Closing short position at {current_price:.5f}"
                        )
                        self.close_position("BUY", abs(position["size"]))
                        self.win_count += 1
                break

    def close_position(self, action, quantity):
        """Close a position."""
        contract = self.create_forex_contract("GBPUSD")

        order = Order()
        order.action = action
        order.totalQuantity = quantity
        order.orderType = "MKT"

        order_id = self.next_order_id
        self.placeOrder(order_id, contract, order)
        self.next_order_id += 1

        logger.info(f"Closing position: {action} {quantity:,} units")

    # IB API callbacks
    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        if errorCode not in [2104, 2106, 2158]:
            logger.error(f"Error {errorCode}: {errorString}")

    def nextValidId(self, orderId):
        self.next_order_id = orderId
        self.connected = True
        logger.info("Connected to IB API")

        # Request account summary
        self.reqAccountSummary(
            1, "All", "NetLiquidation,TotalCashValue,BuyingPower,GrossPositionValue"
        )

        # Request positions
        self.reqPositions()

    def accountSummary(self, reqId, account, tag, value, currency):
        self.account_info[tag] = float(value) if value else 0

    def accountSummaryEnd(self, reqId):
        logger.info("Account info received")
        logger.info(
            f"Net Liquidation: ${self.account_info.get('NetLiquidation', 0):,.2f}"
        )

        # Start market data for GBPUSD
        contract = self.create_forex_contract("GBPUSD")
        self.reqMktData(1, contract, "", False, False, [])

        # Request 5-second bars for better data
        self.reqRealTimeBars(2, contract, 5, "MIDPOINT", True, [])

    def position(self, account, contract, position, avgCost):
        symbol = f"{contract.symbol}{contract.currency}"
        self.positions[symbol] = {
            "size": position,
            "avg_cost": avgCost,
            "current_price": 0,
            "unrealized_pnl": 0,
        }

    def positionEnd(self):
        logger.info(f"Positions loaded: {len(self.positions)}")

    def tickPrice(self, reqId, tickType, price, attrib):
        if tickType == 1:  # Bid
            self.market_data["bid"] = price
        elif tickType == 2:  # Ask
            self.market_data["ask"] = price
        elif tickType == 4:  # Last
            self.market_data["last"] = price
            self.price_history.append(price)

            # Update position P&L
            if "GBPUSD" in self.positions:
                pos = self.positions["GBPUSD"]
                pos["current_price"] = price
                pos["unrealized_pnl"] = (price - pos["avg_cost"]) * pos["size"]

    def realtimeBar(self, reqId, time, open_, high, low, close, volume, wap, count):
        """Process real-time bar data."""
        self.bar_data = {
            "time": time,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }

        # Add close price to history
        self.price_history.append(close)

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
        if orderId in self.pending_orders:
            self.pending_orders[orderId]["status"] = status
            self.pending_orders[orderId]["filled"] = filled
            self.pending_orders[orderId]["avg_price"] = avgFillPrice

            if status == "Filled":
                # Move to completed
                order_info = self.pending_orders.pop(orderId)
                order_info["fill_price"] = avgFillPrice
                self.completed_orders[orderId] = order_info

                # Track daily trades
                self.trades_today.append(order_info)

    def create_forex_contract(self, symbol):
        contract = Contract()
        contract.symbol = symbol[:3]
        contract.secType = "CASH"
        contract.currency = symbol[3:]
        contract.exchange = "IDEALPRO"
        return contract


def main():
    """Main trading loop."""
    # Create trader
    trader = MLPaperTrader()

    # Connect to IB
    logger.info("Starting ML Paper Trader...")
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

    # Signal handler
    running = True

    def signal_handler(sig, frame):
        nonlocal running
        logger.info("Shutting down...")
        running = False

    signal.signal(signal.SIGINT, signal_handler)

    # Trading loop
    last_signal_check = 0
    signal_check_interval = 60  # Check for signals every minute
    last_status_update = 0
    status_update_interval = 300  # Status update every 5 minutes

    logger.info("\n" + "=" * 60)
    logger.info("ML PAPER TRADING SYSTEM ACTIVE")
    logger.info("=" * 60)
    logger.info("Model: GBPUSD")
    logger.info(f"Risk per trade: {trader.risk_per_trade*100:.1f}%")
    logger.info(f"Stop loss: {trader.stop_loss_pips} pips")
    logger.info(f"Take profit: {trader.stop_loss_pips * trader.take_profit_ratio} pips")
    logger.info("Press Ctrl+C to stop")
    logger.info("")

    while running:
        try:
            current_time = time.time()

            # Check for trading signals
            if current_time - last_signal_check >= signal_check_interval:
                if len(trader.price_history) >= 50:
                    signal = trader.generate_ml_signal()
                    if signal:
                        logger.info(
                            f"\nSignal detected: {signal['direction']} "
                            f"(Confidence: {signal['confidence']:.1%})"
                        )
                        trader.place_trade(signal)

                last_signal_check = current_time

            # Check exit conditions for open positions
            trader.check_exit_conditions()

            # Status update
            if current_time - last_status_update >= status_update_interval:
                if trader.account_info:
                    logger.info(f"\n{'='*60}")
                    logger.info(
                        f"STATUS UPDATE - {datetime.now().strftime('%H:%M:%S')}"
                    )
                    logger.info(f"{'='*60}")

                    # Account status
                    net_liq = trader.account_info.get("NetLiquidation", 0)
                    logger.info(f"Account Value: ${net_liq:,.2f}")

                    # Market data
                    if trader.market_data:
                        bid = trader.market_data.get("bid", 0)
                        ask = trader.market_data.get("ask", 0)
                        last = trader.market_data.get("last", 0)
                        spread = (ask - bid) * 10000 if bid and ask else 0
                        logger.info(f"GBPUSD: {last:.5f} (Spread: {spread:.1f} pips)")

                    # Position status
                    if "GBPUSD" in trader.positions:
                        pos = trader.positions["GBPUSD"]
                        if pos["size"] != 0:
                            logger.info(f"\nOpen Position:")
                            logger.info(f"  Size: {pos['size']:,} units")
                            logger.info(f"  Entry: {pos['avg_cost']:.5f}")
                            logger.info(f"  Current: {pos['current_price']:.5f}")
                            logger.info(f"  P&L: ${pos['unrealized_pnl']:,.2f}")

                    # Daily performance
                    if trader.trades_today:
                        logger.info(f"\nToday's Performance:")
                        logger.info(f"  Trades: {len(trader.trades_today)}")
                        logger.info(f"  Wins: {trader.win_count}")
                        logger.info(f"  Losses: {trader.loss_count}")
                        if trader.win_count + trader.loss_count > 0:
                            win_rate = trader.win_count / (
                                trader.win_count + trader.loss_count
                            )
                            logger.info(f"  Win Rate: {win_rate:.1%}")

                last_status_update = current_time

            time.sleep(1)

        except Exception as e:
            logger.error(f"Error in trading loop: {e}", exc_info=True)

    # Disconnect
    trader.disconnect()
    logger.info("\nDisconnected from IB API")

    # Final summary
    logger.info("\n" + "=" * 60)
    logger.info("TRADING SESSION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total Trades: {len(trader.trades_today)}")
    logger.info(f"Wins: {trader.win_count}")
    logger.info(f"Losses: {trader.loss_count}")
    if trader.win_count + trader.loss_count > 0:
        win_rate = trader.win_count / (trader.win_count + trader.loss_count)
        logger.info(f"Win Rate: {win_rate:.1%}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
