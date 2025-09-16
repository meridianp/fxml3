#!/usr/bin/env python3
"""Paper trading with 100:1 leverage models."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import json
import logging
import signal
import time
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Import paper trading engine
from fxml4.backtesting.paper_trading import PaperTradingEngine
from fxml4.strategy.ml_signal_generator import MLSignalGenerator

# Global variables
engine = None
is_running = True


def signal_handler(sig, frame):
    """Handle shutdown signal."""
    global is_running
    logger.info("Shutdown signal received...")
    is_running = False
    if engine:
        engine.stop()


def create_100x_config():
    """Create configuration for 100:1 leverage paper trading."""

    # Use GBPUSD (our best model with 46.6% accuracy)
    symbols = ["GBPUSD"]

    # Create signal generators
    signal_generators = []

    # Check for GBPUSD model
    model_path = Path("models/GBPUSD_100x_simple")
    if model_path.exists():
        logger.info(f"Loading GBPUSD 100x model from {model_path}")

        # Create custom signal generator for 100x leverage
        class Leverage100xSignalGenerator:
            def __init__(self, model_path):
                self.model_path = model_path
                self.symbol = "GBPUSD"
                import joblib

                self.model = joblib.load(model_path / "model.pkl")
                self.scaler = joblib.load(model_path / "scaler.pkl")
                with open(model_path / "config.json", "r") as f:
                    self.config = json.load(f)
                self.features = self.config["features"]

            def generate_signals(self, data, current_positions=None):
                """Generate trading signals."""
                try:
                    # Get latest data for symbol
                    if self.symbol not in data:
                        return []

                    df = data[self.symbol].get("4h")  # Use 4H timeframe
                    if df is None or len(df) < 50:
                        return []

                    # Prepare features
                    latest = df.iloc[-1]
                    features = []
                    for feat in self.features:
                        if feat in latest:
                            features.append(latest[feat])
                        else:
                            features.append(0)  # Default value

                    # Scale and predict
                    import numpy as np

                    X = np.array(features).reshape(1, -1)
                    X_scaled = self.scaler.transform(X)

                    prediction = self.model.predict(X_scaled)[0]
                    probability = self.model.predict_proba(X_scaled)[0]

                    # Generate signal if confident
                    signals = []
                    if prediction != 0:  # Not neutral
                        # Get confidence (probability of predicted class)
                        confidence = max(probability)

                        if confidence > 0.6:  # 60% confidence threshold
                            signal = {
                                "symbol": self.symbol,
                                "direction": "long" if prediction > 0 else "short",
                                "strength": confidence,
                                "entry_price": float(latest["close"]),
                                "timestamp": df.index[-1],
                                "timeframe": "4h",
                                "strategy": "100x_leverage",
                                # 100:1 leverage specific
                                "leverage": 100,
                                "risk_pct": 0.015,  # 1.5% risk per trade
                                "stop_pips": 10,  # Tight stop for high leverage
                                "target_pips": 30,  # 3:1 R:R
                            }
                            signals.append(signal)
                            logger.info(
                                f"Generated {signal['direction']} signal for {self.symbol} "
                                f"with {confidence:.1%} confidence"
                            )

                    return signals

                except Exception as e:
                    logger.error(f"Error generating signals: {e}")
                    return []

        generator = Leverage100xSignalGenerator(model_path)
        signal_generators.append(generator)

    # Paper trading configuration
    config = {
        "symbols": symbols,
        "timeframes": ["1m", "5m", "15m", "1h", "4h"],
        "base_timeframe": "1m",
        "signal_timeframe": "4h",
        "initial_capital": 100000,  # $100k starting capital
        "max_positions": 3,  # Maximum 3 concurrent positions
        # IB connection
        "ib_config": {
            "host": "127.0.0.1",
            "port": 4002,
            "client_id": 1,
            "real_time_updates": True,
            "update_interval": 1.0,
            "tick_storage_limit": 10000,
            "candle_storage_days": 7,
        },
        # Risk management for 100:1 leverage
        "risk_config": {
            "max_risk_per_trade": 0.015,  # 1.5% risk per trade
            "max_portfolio_risk": 0.05,  # 5% max portfolio risk
            "stop_loss_atr_multiplier": 0.5,
            "take_profit_atr_multiplier": 1.5,
            "max_leverage": 100,
            "position_sizing_method": "fixed_risk",
            # Circuit breakers
            "daily_loss_limit": -0.05,  # -5% daily
            "weekly_loss_limit": -0.10,  # -10% weekly
            "monthly_loss_limit": -0.15,  # -15% monthly
        },
        # Position sizing
        "position_size_config": {
            "method": "fixed_risk",
            "risk_per_trade": 0.015,
            "min_position_size": 1000,  # Minimum 1 micro lot
            "max_position_size": 500000,  # Maximum 500 micro lots
            "round_to": 100,  # Round to nearest 100 units
        },
        # Signal generators
        "signal_generators": signal_generators,
        # Working hours - trade 24/5
        "working_hours": {
            "start_hour": 0,
            "end_hour": 24,
            "trading_days": [0, 1, 2, 3, 4],  # Monday to Friday
        },
        # Storage
        "enable_storage": True,
        "store_ticks": False,  # Don't store all ticks
        "store_trades": True,
        "store_portfolio_snapshots": True,
        "snapshot_interval": 300,  # Every 5 minutes
    }

    return config


def main():
    """Main entry point."""
    global engine

    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Create configuration
        config = create_100x_config()

        if not config["signal_generators"]:
            logger.error("No signal generators available!")
            logger.error(
                "Please train models first: python scripts/train_simple_100x_models.py"
            )
            return 1

        # Create paper trading engine
        logger.info("Creating paper trading engine...")
        engine = PaperTradingEngine(config)

        # Start engine
        logger.info("Starting paper trading with 100:1 leverage...")
        logger.info(f"Initial capital: ${config['initial_capital']:,.2f}")
        logger.info(f"Max leverage: {config['risk_config']['max_leverage']}:1")
        logger.info(
            f"Risk per trade: {config['risk_config']['max_risk_per_trade']*100:.1f}%"
        )
        logger.info("=" * 60)

        engine.start()

        # Status update interval
        last_status = time.time()
        status_interval = 60  # seconds

        # Main loop
        while is_running and engine.is_running:
            current_time = time.time()

            # Print status periodically
            if current_time - last_status >= status_interval:
                portfolio = engine.get_portfolio_status()

                logger.info("\n" + "=" * 60)
                logger.info(
                    f"PORTFOLIO STATUS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                logger.info("=" * 60)
                logger.info(f"Equity: ${portfolio['equity']:,.2f}")
                logger.info(f"Cash: ${portfolio['cash']:,.2f}")
                logger.info(
                    f"P&L: ${portfolio['equity'] - config['initial_capital']:,.2f} "
                    f"({(portfolio['equity']/config['initial_capital'] - 1)*100:+.2f}%)"
                )

                # Open positions
                if portfolio["positions"]:
                    logger.info("\nOpen Positions:")
                    for symbol, pos in portfolio["positions"].items():
                        logger.info(
                            f"  {symbol}: {pos['size']:,} units @ {pos['avg_price']:.5f}"
                        )
                        if "unrealized_pnl" in pos:
                            logger.info(
                                f"    Unrealized P&L: ${pos['unrealized_pnl']:,.2f}"
                            )

                # Recent trades
                if portfolio["trades"]:
                    recent = portfolio["trades"][-3:]
                    logger.info(f"\nLast {len(recent)} Trades:")
                    for trade in recent:
                        logger.info(
                            f"  {trade['timestamp']} - {trade['symbol']} "
                            f"{trade['action']} {trade['size']:,} @ {trade['price']:.5f}"
                        )

                last_status = current_time

            time.sleep(1)

    except Exception as e:
        logger.error(f"Error in paper trading: {e}", exc_info=True)
        return 1

    finally:
        # Clean shutdown
        if engine:
            logger.info("Stopping paper trading engine...")
            engine.stop()

            # Final summary
            portfolio = engine.get_portfolio_status()
            logger.info("\n" + "=" * 60)
            logger.info("FINAL RESULTS")
            logger.info("=" * 60)
            logger.info(f"Starting capital: ${config['initial_capital']:,.2f}")
            logger.info(f"Final equity: ${portfolio['equity']:,.2f}")
            logger.info(
                f"Total P&L: ${portfolio['equity'] - config['initial_capital']:,.2f}"
            )
            logger.info(
                f"Return: {(portfolio['equity']/config['initial_capital'] - 1)*100:+.2f}%"
            )
            logger.info(f"Total trades: {len(portfolio['trades'])}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
