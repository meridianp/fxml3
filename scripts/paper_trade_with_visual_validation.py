#!/usr/bin/env python3
"""Paper trading with multi-modal LLM visual validation."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
import logging
import pickle
import signal
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

from fxml4.llm_integration.multi_source_sentiment import MultiSourceSentimentAggregator

# Import our modules
from fxml4.llm_integration.multimodal_chart_validator import MultiModalChartValidator
from fxml4.llm_integration.realtime_market_analyst import RealtimeMarketAnalyst

# Import components
from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.wrapper import EWrapper


class VisualValidationTrader(EWrapper, EClient):
    """Paper trader with multi-modal visual validation."""

    def __init__(self):
        EClient.__init__(self, self)
        self.connected = False
        self.next_order_id = None
        self.positions = {}
        self.account_info = {}
        self.market_data = {}
        self.pending_orders = {}
        self.completed_orders = {}

        # Price and indicator history
        self.price_history = []
        self.ohlc_data = pd.DataFrame()
        self.indicators = {}

        # ML model
        self.model = None
        self.scaler = None
        self.load_model()

        # Multi-modal components
        self.chart_validator = MultiModalChartValidator()
        self.market_analyst = RealtimeMarketAnalyst()
        self.sentiment_aggregator = MultiSourceSentimentAggregator()

        # Trading parameters
        self.min_confidence = 0.75  # Higher threshold with visual validation
        self.risk_per_trade = 0.01
        self.max_positions = 2
        self.last_trade_time = 0
        self.trade_cooldown = 600  # 10 minutes

        # Async event loop for LLM calls
        self.loop = asyncio.new_event_loop()
        self.async_thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.async_thread.start()

    def _run_event_loop(self):
        """Run async event loop in separate thread."""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def load_model(self):
        """Load ML model."""
        model_path = Path("models/GBPUSD_100x_simple")
        if model_path.exists():
            try:
                with open(model_path / "model.pkl", "rb") as f:
                    self.model = pickle.load(f)
                with open(model_path / "scaler.pkl", "rb") as f:
                    self.scaler = pickle.load(f)
                logger.info("ML model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load model: {e}")

    def calculate_indicators(self):
        """Calculate technical indicators."""
        if len(self.ohlc_data) < 50:
            return

        try:
            # Price-based indicators
            self.indicators["sma_20"] = self.ohlc_data["close"].rolling(20).mean()
            self.indicators["sma_50"] = self.ohlc_data["close"].rolling(50).mean()
            self.indicators["ema_9"] = self.ohlc_data["close"].ewm(span=9).mean()

            # RSI
            delta = self.ohlc_data["close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            self.indicators["rsi"] = 100 - (100 / (1 + rs))

            # Bollinger Bands
            bb_sma = self.ohlc_data["close"].rolling(20).mean()
            bb_std = self.ohlc_data["close"].rolling(20).std()
            self.indicators["bb_upper"] = bb_sma + (bb_std * 2)
            self.indicators["bb_middle"] = bb_sma
            self.indicators["bb_lower"] = bb_sma - (bb_std * 2)

            # Support/Resistance (simplified)
            self.indicators["support_levels"] = self._find_support_resistance("support")
            self.indicators["resistance_levels"] = self._find_support_resistance(
                "resistance"
            )

            # Volume trend
            self.indicators["volume_trend"] = (
                "increasing"
                if (
                    self.ohlc_data["volume"].tail(5).mean()
                    > self.ohlc_data["volume"].tail(20).mean()
                )
                else "decreasing"
            )

        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")

    def _find_support_resistance(self, type="support", lookback=50):
        """Find support/resistance levels."""
        if len(self.ohlc_data) < lookback:
            return []

        levels = []

        if type == "support":
            # Find local minima
            lows = self.ohlc_data["low"].tail(lookback)
            for i in range(2, len(lows) - 2):
                if (
                    lows.iloc[i] < lows.iloc[i - 1]
                    and lows.iloc[i] < lows.iloc[i - 2]
                    and lows.iloc[i] < lows.iloc[i + 1]
                    and lows.iloc[i] < lows.iloc[i + 2]
                ):
                    levels.append(lows.iloc[i])
        else:
            # Find local maxima
            highs = self.ohlc_data["high"].tail(lookback)
            for i in range(2, len(highs) - 2):
                if (
                    highs.iloc[i] > highs.iloc[i - 1]
                    and highs.iloc[i] > highs.iloc[i - 2]
                    and highs.iloc[i] > highs.iloc[i + 1]
                    and highs.iloc[i] > highs.iloc[i + 2]
                ):
                    levels.append(highs.iloc[i])

        return sorted(levels)

    async def generate_validated_signal(self):
        """Generate and validate trading signal with visual confirmation."""
        if len(self.ohlc_data) < 50 or not self.model:
            return None

        try:
            # Generate ML signal
            features = self._prepare_features()
            if features is None:
                return None

            # Get ML prediction
            X = np.array(features).reshape(1, -1)
            if self.scaler:
                X = self.scaler.transform(X)

            prediction = self.model.predict(X)[0]
            ml_confidence = 0.7  # Default confidence

            if hasattr(self.model, "predict_proba"):
                probabilities = self.model.predict_proba(X)[0]
                if prediction == 1:
                    ml_confidence = (
                        probabilities[2] if len(probabilities) > 2 else probabilities[1]
                    )
                elif prediction == -1:
                    ml_confidence = probabilities[0]

            if prediction == 0 or ml_confidence < 0.6:
                return None

            # Create signal
            current_price = self.ohlc_data["close"].iloc[-1]
            signal = {
                "symbol": "GBPUSD",
                "direction": "BUY" if prediction > 0 else "SELL",
                "confidence": ml_confidence,
                "entry_price": current_price,
                "stop_loss": current_price - (0.0040 if prediction > 0 else -0.0040),
                "take_profit": current_price + (0.0080 if prediction > 0 else -0.0080),
                "timeframe": "4H",
                "timestamp": datetime.now(),
            }

            # Get sentiment
            sentiment = await self.sentiment_aggregator.get_aggregated_sentiment(
                "GBPUSD"
            )

            # Visual validation
            validation = await self.chart_validator.validate_trading_signal(
                signal, self.ohlc_data, self.indicators
            )

            # Check if validated
            if (
                validation.get("valid")
                and validation.get("enhanced_confidence", 0) >= self.min_confidence
            ):
                signal["validation"] = validation
                signal["sentiment"] = sentiment
                signal["final_confidence"] = validation["enhanced_confidence"]

                # Generate report
                report = await self.chart_validator.generate_analysis_report(
                    validation, None  # Chart already generated
                )

                logger.info(f"\n{'='*60}")
                logger.info("VALIDATED TRADING SIGNAL")
                logger.info(f"{'='*60}")
                logger.info(report)
                logger.info(f"{'='*60}")

                return signal
            else:
                logger.info(
                    f"Signal rejected by visual validation: {validation.get('overall_assessment')}"
                )
                return None

        except Exception as e:
            logger.error(f"Error generating validated signal: {e}")
            return None

    def _prepare_features(self):
        """Prepare features for ML model."""
        try:
            if len(self.ohlc_data) < 50:
                return None

            close = self.ohlc_data["close"]

            # Calculate features matching the model
            features = [
                # Returns
                (close.iloc[-1] / close.iloc[-2] - 1) if len(close) > 1 else 0,
                (close.iloc[-1] / close.iloc[-3] - 1) if len(close) > 2 else 0,
                (close.iloc[-1] / close.iloc[-5] - 1) if len(close) > 4 else 0,
                (close.iloc[-1] / close.iloc[-9] - 1) if len(close) > 8 else 0,
                # SMA slopes
                (
                    (
                        self.indicators.get("sma_20", pd.Series()).iloc[-1]
                        - self.indicators.get("sma_20", pd.Series()).iloc[-5]
                    )
                    / self.indicators.get("sma_20", pd.Series()).iloc[-5]
                    if "sma_20" in self.indicators
                    and len(self.indicators["sma_20"]) > 5
                    else 0
                ),
                (
                    (
                        self.indicators.get("sma_50", pd.Series()).iloc[-1]
                        - self.indicators.get("sma_50", pd.Series()).iloc[-5]
                    )
                    / self.indicators.get("sma_50", pd.Series()).iloc[-5]
                    if "sma_50" in self.indicators
                    and len(self.indicators["sma_50"]) > 5
                    else 0
                ),
                0,  # Placeholder for another slope
                # RSI
                (
                    self.indicators.get("rsi", pd.Series()).iloc[-1]
                    if "rsi" in self.indicators
                    else 50
                ),
                # Volatility
                close.pct_change().rolling(20).std().iloc[-1] if len(close) > 20 else 0,
                # ATR approximation
                (self.ohlc_data["high"] - self.ohlc_data["low"])
                .rolling(14)
                .mean()
                .iloc[-1],
                # Time features
                datetime.now().hour,
                datetime.now().weekday(),
                # Session indicators
                1 if 8 <= datetime.now().hour < 16 else 0,  # London
                1 if 13 <= datetime.now().hour < 22 else 0,  # NY
                (
                    1 if datetime.now().hour >= 23 or datetime.now().hour < 8 else 0
                ),  # Asian
            ]

            return features

        except Exception as e:
            logger.error(f"Error preparing features: {e}")
            return None

    def execute_signal(self, signal):
        """Execute validated signal."""
        if not self.connected or not signal:
            return

        # Check cooldown
        if time.time() - self.last_trade_time < self.trade_cooldown:
            logger.info("Trade cooldown active")
            return

        # Check position limits
        if len(self.positions) >= self.max_positions:
            logger.info("Maximum positions reached")
            return

        # Calculate position size
        position_size = self.calculate_position_size(signal)
        if position_size == 0:
            return

        # Create order
        contract = self.create_forex_contract("GBPUSD")

        order = Order()
        order.action = signal["direction"]
        order.totalQuantity = position_size
        order.orderType = "MKT"

        # Place order
        order_id = self.next_order_id
        self.placeOrder(order_id, contract, order)
        self.next_order_id += 1

        logger.info(f"\n{'='*60}")
        logger.info("EXECUTING VALIDATED TRADE")
        logger.info(f"{'='*60}")
        logger.info(f"Direction: {signal['direction']}")
        logger.info(f"Size: {position_size:,} units")
        logger.info(f"Entry: {signal['entry_price']:.5f}")
        logger.info(f"Stop: {signal['stop_loss']:.5f}")
        logger.info(f"Target: {signal['take_profit']:.5f}")
        logger.info(f"ML Confidence: {signal['confidence']:.1%}")
        logger.info(f"Visual Confidence: {signal['validation']['llm_confidence']:.1%}")
        logger.info(f"Final Confidence: {signal['final_confidence']:.1%}")
        logger.info(f"{'='*60}")

        self.last_trade_time = time.time()

        # Store order info
        self.pending_orders[order_id] = {
            "signal": signal,
            "quantity": position_size,
            "timestamp": datetime.now(),
        }

    def calculate_position_size(self, signal):
        """Calculate position size based on risk."""
        if "NetLiquidation" not in self.account_info:
            return 0

        account_value = self.account_info["NetLiquidation"]
        risk_amount = account_value * self.risk_per_trade

        # Calculate based on stop loss
        stop_distance = abs(signal["entry_price"] - signal["stop_loss"])
        position_size = risk_amount / stop_distance

        # Apply maximum position constraint
        max_position_value = account_value * 3.2  # 3.2x leverage max
        max_position_size = max_position_value / signal["entry_price"]

        position_size = min(position_size, max_position_size)

        # Round to 1000 units
        position_size = round(position_size / 1000) * 1000

        # Minimum 25k units
        return max(int(position_size), 25000)

    # IB API callbacks
    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        if errorCode not in [2104, 2106, 2158]:
            logger.error(f"Error {errorCode}: {errorString}")

    def nextValidId(self, orderId):
        self.next_order_id = orderId
        self.connected = True
        logger.info("Connected to IB API")

        self.reqAccountSummary(1, "All", "NetLiquidation,BuyingPower")
        self.reqPositions()

    def accountSummary(self, reqId, account, tag, value, currency):
        self.account_info[tag] = float(value) if value else 0

    def accountSummaryEnd(self, reqId):
        logger.info(
            f"Account loaded: ${self.account_info.get('NetLiquidation', 0):,.2f}"
        )

        # Start market data
        contract = self.create_forex_contract("GBPUSD")
        self.reqMktData(1, contract, "", False, False, [])
        self.reqRealTimeBars(2, contract, 5, "MIDPOINT", True, [])

    def realtimeBar(self, reqId, time, open_, high, low, close, volume, wap, count):
        """Process real-time bars."""
        # Add to OHLC data
        new_bar = pd.DataFrame(
            {
                "open": [open_],
                "high": [high],
                "low": [low],
                "close": [close],
                "volume": [volume],
            },
            index=[pd.Timestamp.fromtimestamp(time)],
        )

        self.ohlc_data = pd.concat([self.ohlc_data, new_bar]).tail(200)

        # Recalculate indicators
        self.calculate_indicators()

    def tickPrice(self, reqId, tickType, price, attrib):
        if tickType == 4:  # Last price
            self.market_data["last"] = price

    def position(self, account, contract, position, avgCost):
        symbol = f"{contract.symbol}{contract.currency}"
        self.positions[symbol] = {"size": position, "avg_cost": avgCost}

    def create_forex_contract(self, symbol):
        contract = Contract()
        contract.symbol = symbol[:3]
        contract.secType = "CASH"
        contract.currency = symbol[3:]
        contract.exchange = "IDEALPRO"
        return contract


async def check_for_signals(trader):
    """Async function to check for trading signals."""
    while True:
        try:
            if len(trader.ohlc_data) >= 50:
                signal = await trader.generate_validated_signal()
                if signal:
                    trader.execute_signal(signal)

            await asyncio.sleep(60)  # Check every minute

        except Exception as e:
            logger.error(f"Error checking signals: {e}")
            await asyncio.sleep(10)


def main():
    """Main entry point."""
    trader = VisualValidationTrader()

    # Connect to IB
    logger.info("Starting Visual Validation Paper Trader...")
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

    # Start signal checking in async loop
    future = asyncio.run_coroutine_threadsafe(check_for_signals(trader), trader.loop)

    # Signal handler
    running = True

    def signal_handler(sig, frame):
        nonlocal running
        logger.info("Shutting down...")
        running = False
        trader.loop.call_soon_threadsafe(trader.loop.stop)

    signal.signal(signal.SIGINT, signal_handler)

    logger.info("\n" + "=" * 60)
    logger.info("VISUAL VALIDATION PAPER TRADING ACTIVE")
    logger.info("=" * 60)
    logger.info("- ML model generates signals")
    logger.info("- Technical chart is created")
    logger.info("- Multi-modal LLM validates the setup")
    logger.info("- Only high-confidence validated trades execute")
    logger.info(f"- Minimum confidence: {trader.min_confidence:.0%}")
    logger.info("Press Ctrl+C to stop")
    logger.info("")

    # Main loop
    last_status = time.time()
    while running:
        try:
            # Status update every 5 minutes
            if time.time() - last_status > 300:
                logger.info(f"\n--- Status {datetime.now().strftime('%H:%M:%S')} ---")
                logger.info(
                    f"Account: ${trader.account_info.get('NetLiquidation', 0):,.2f}"
                )
                logger.info(f"Positions: {len(trader.positions)}")
                logger.info(f"OHLC bars: {len(trader.ohlc_data)}")
                if "last" in trader.market_data:
                    logger.info(f"GBPUSD: {trader.market_data['last']:.5f}")
                last_status = time.time()

            time.sleep(1)

        except Exception as e:
            logger.error(f"Error in main loop: {e}")

    # Cleanup
    trader.disconnect()
    logger.info("Disconnected from IB API")

    return 0


if __name__ == "__main__":
    sys.exit(main())
