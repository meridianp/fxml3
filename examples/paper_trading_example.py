#!/usr/bin/env python
"""
Example of paper trading with Interactive Brokers in FXML4.

This script demonstrates how to use the PaperTradingEngine class to connect to
Interactive Brokers, process real-time data, and execute paper trades.
"""

import argparse
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict

import pandas as pd

from fxml4.backtesting.paper_trading import PaperTradingEngine
from fxml4.ml.gbpusd_model import load_gbpusd_model
from fxml4.strategy.gbpusd_signal_generator import GBPUSDSignalGenerator
from fxml4.strategy.ml_signal_generator import MLSignalGenerator
from fxml4.strategy.wave_signal_generator import WaveSignalGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize signal handler for graceful shutdown
engine = None
is_running = True


def signal_handler(sig, frame):
    """Handle interrupt signals to gracefully shut down."""
    global is_running
    logger.info("Shutdown signal received, stopping...")
    is_running = False


def create_signal_generators(config: Dict[str, Any]):
    """Create signal generators based on configuration.

    Args:
        config: Configuration with signal generator settings

    Returns:
        List of signal generator instances
    """
    generators = []

    # Add ML-based signal generator if enabled
    if config.get("use_ml", True):
        try:
            # Load model for GBPUSD
            model_path = config.get("model_path", "")
            if not model_path:
                # Try to use latest model
                model_dir = os.path.join(os.path.dirname(__file__), "..", "models")
                model_files = [
                    f
                    for f in os.listdir(model_dir)
                    if f.startswith("gbpusd_") and f.endswith("_metadata.json")
                ]
                if model_files:
                    # Use the most recent model
                    model_files.sort()
                    model_path = os.path.join(model_dir, model_files[-1])

            if model_path:
                model, metadata = load_gbpusd_model(model_path)
                ml_generator = MLSignalGenerator(model=model, metadata=metadata)
                ml_generator.weight = 2.0  # Higher weight for ML signals
                generators.append(ml_generator)
                logger.info(f"Added ML signal generator with model: {model_path}")
            else:
                logger.warning(
                    "No ML model found for GBPUSD, skipping ML signal generator"
                )
        except Exception as e:
            logger.error(f"Error loading ML model: {e}")

    # Add GBP/USD specific signal generator
    if config.get("use_gbpusd_generator", True):
        gbpusd_generator = GBPUSDSignalGenerator()
        gbpusd_generator.weight = 1.5
        generators.append(gbpusd_generator)
        logger.info("Added GBP/USD signal generator")

    # Add Elliott Wave signal generator if enabled
    if config.get("use_wave", True):
        wave_generator = WaveSignalGenerator()
        wave_generator.weight = 1.2
        generators.append(wave_generator)
        logger.info("Added Wave signal generator")

    return generators


def run_paper_trading(args):
    """Run the paper trading engine.

    Args:
        args: Command line arguments
    """
    global engine

    # Configure IB connection
    ib_config = {
        "host": args.host,
        "port": args.port,
        "client_id": args.client_id,
        "real_time_updates": True,
        "update_interval": 1.0,
        "tick_storage_limit": 10000,
        "candle_storage_days": 7,
    }

    # Configure risk parameters
    risk_config = {
        "max_drawdown": 5.0,  # 5% max drawdown
        "risk_per_trade": 0.01,  # 1% risk per trade
        "max_risk_multiplier": 1.5,  # Max increase in risk for strong signals
        "position_size_method": "risk_based",  # Alternative: "fixed"
    }

    # Configure paper trading engine
    symbols = args.symbols.split(",")

    # Create signal generators
    generators = create_signal_generators(
        {
            "use_ml": not args.no_ml,
            "use_gbpusd_generator": not args.no_gbpusd,
            "use_wave": not args.no_wave,
            "model_path": args.model,
        }
    )

    # Create engine configuration
    engine_config = {
        "symbols": symbols,
        "timeframes": ["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
        "base_timeframe": "1m",
        "signal_timeframe": args.timeframe,
        "risk_config": risk_config,
        "ib_config": ib_config,
        "signal_generators": generators,
        "initial_capital": args.capital,
        "max_positions": args.max_positions,
        "risk_per_trade": args.risk_per_trade / 100.0,  # Convert from percentage
        "stop_loss_pips": args.stop_loss_pips,
        "max_leverage": args.max_leverage,
        "signal_cooldown": args.cooldown,
        "enable_storage": args.store_results,
        "working_hours": {
            "enabled": args.working_hours,
            "start_time": args.start_time,
            "end_time": args.end_time,
            "weekend_trading": args.weekend_trading,
        },
    }

    # Create and start the engine
    engine = PaperTradingEngine(engine_config)

    # Connect to IB
    if not engine.connect():
        logger.error("Failed to connect to Interactive Brokers")
        return 1

    # Start the engine
    engine.start()
    logger.info(
        f"Paper trading started with {len(symbols)} symbols: {', '.join(symbols)}"
    )

    try:
        # Run until interrupted
        last_status_time = datetime.now(timezone.utc)
        status_interval = args.status_interval * 60  # Convert minutes to seconds

        while is_running:
            # Display status periodically
            now = datetime.now(timezone.utc)
            if (now - last_status_time).total_seconds() >= status_interval:
                status = engine.get_portfolio_status()
                metrics = engine.get_performance_metrics()

                logger.info(
                    f"=== Portfolio Status ({now.strftime('%Y-%m-%d %H:%M:%S UTC')}) ==="
                )
                logger.info(
                    f"Cash: ${status['cash']:.2f}, Equity: ${status['equity']:.2f}"
                )
                logger.info(f"Unrealized P&L: ${status['unrealized_pnl']:.2f}")
                logger.info(f"Open Positions: {status['positions']}")
                logger.info(
                    f"Current Drawdown: {status['drawdown']:.2f}%, Max Drawdown: {status['max_drawdown']:.2f}%"
                )
                logger.info(
                    f"Total Return: {metrics['total_return']:.2f}%, Win Rate: {metrics['win_rate']:.1f}%"
                )

                # Log position details
                if status["positions"] > 0:
                    logger.info("--- Open Positions ---")
                    for symbol, pos in status["positions_detail"].items():
                        direction = pos["direction"]
                        size = pos["size"]
                        entry = pos["entry_price"]
                        current = pos["current_price"]
                        pnl = pos["unrealized_pnl"]
                        logger.info(
                            f"{symbol}: {direction} {size} @ {entry:.5f}, Current: {current:.5f}, P&L: ${pnl:.2f}"
                        )

                last_status_time = now

            time.sleep(1.0)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
    finally:
        if engine:
            # Stop and disconnect
            engine.stop()

            # Display final performance
            final_metrics = engine.get_performance_metrics()
            logger.info("=== Final Performance Summary ===")
            logger.info(f"Initial Capital: ${final_metrics['initial_capital']:.2f}")
            logger.info(f"Final Equity: ${final_metrics['current_equity']:.2f}")
            logger.info(f"Total Return: {final_metrics['total_return']:.2f}%")
            logger.info(f"Annualized Return: {final_metrics['annualized_return']:.2f}%")
            logger.info(f"Sharpe Ratio: {final_metrics['sharpe_ratio']:.2f}")
            logger.info(f"Max Drawdown: {final_metrics['max_drawdown']:.2f}%")
            logger.info(f"Win Rate: {final_metrics['win_rate']:.1f}%")
            logger.info(f"Profit Factor: {final_metrics['profit_factor']:.2f}")
            logger.info(f"Total Trades: {final_metrics['total_trades']}")

    return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="FXML4 Paper Trading with Interactive Brokers"
    )

    # IB connection parameters
    parser.add_argument("--host", default="127.0.0.1", help="TWS/IB Gateway host")
    parser.add_argument(
        "--port",
        type=int,
        default=7497,
        help="TWS/IB Gateway port (7497 for paper trading)",
    )
    parser.add_argument(
        "--client-id", type=int, default=1, help="Client ID for IB connection"
    )

    # Trading parameters
    parser.add_argument(
        "--symbols", default="GBPUSD", help="Comma-separated list of symbols to trade"
    )
    parser.add_argument(
        "--timeframe", default="1h", help="Timeframe for signal generation"
    )
    parser.add_argument(
        "--capital", type=float, default=10000.0, help="Initial capital"
    )
    parser.add_argument(
        "--max-positions",
        type=int,
        default=5,
        help="Maximum number of concurrent positions",
    )
    parser.add_argument(
        "--risk-per-trade",
        type=float,
        default=1.0,
        help="Risk per trade (percentage of equity)",
    )
    parser.add_argument(
        "--stop-loss-pips",
        type=int,
        default=50,
        help="Default stop loss distance in pips",
    )
    parser.add_argument(
        "--max-leverage", type=float, default=20.0, help="Maximum leverage to use"
    )
    parser.add_argument(
        "--cooldown", type=int, default=60, help="Signal cooldown period in minutes"
    )

    # Signal generator options
    parser.add_argument(
        "--no-ml", action="store_true", help="Disable ML signal generator"
    )
    parser.add_argument(
        "--no-gbpusd", action="store_true", help="Disable GBP/USD signal generator"
    )
    parser.add_argument(
        "--no-wave", action="store_true", help="Disable Wave signal generator"
    )
    parser.add_argument(
        "--model", type=str, default="", help="Path to ML model for signal generation"
    )

    # Working hours
    parser.add_argument(
        "--working-hours",
        action="store_true",
        help="Enable trading only during specified hours",
    )
    parser.add_argument(
        "--start-time", default="00:00", help="Trading start time (UTC)"
    )
    parser.add_argument("--end-time", default="23:59", help="Trading end time (UTC)")
    parser.add_argument(
        "--weekend-trading", action="store_true", help="Allow trading on weekends"
    )

    # Reporting
    parser.add_argument(
        "--status-interval",
        type=int,
        default=10,
        help="Status reporting interval in minutes",
    )
    parser.add_argument(
        "--store-results", action="store_true", help="Store trading results in database"
    )

    args = parser.parse_args()

    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    return run_paper_trading(args)


if __name__ == "__main__":
    sys.exit(main())
