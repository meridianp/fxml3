#!/usr/bin/env python3
"""Start paper trading with 100:1 leverage models."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import argparse
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

# Check if IB API is available
try:
    from ibapi.client import EClient
    from ibapi.contract import Contract
    from ibapi.wrapper import EWrapper

    IB_API_AVAILABLE = True
except ImportError:
    logger.error("IB API not available. Please install ibapi package.")
    logger.error("To install: pip install ibapi")
    logger.error("Or download from Interactive Brokers website")
    IB_API_AVAILABLE = False

from fxml4.backtesting.paper_trading import PaperTradingEngine
from fxml4.strategy.ml_signal_generator import MLSignalGenerator

# Global variables for signal handling
engine = None
is_running = True


def signal_handler(sig, frame):
    """Handle interrupt signals to gracefully shut down."""
    global is_running
    logger.info("Shutdown signal received, stopping...")
    is_running = False
    if engine:
        engine.stop()


def create_100x_signal_generator(symbol: str):
    """Create signal generator for 100:1 leverage trading.

    Args:
        symbol: Trading symbol (e.g., 'GBPUSD')

    Returns:
        Signal generator instance or None if model not found
    """
    # Check for 100x leverage models
    model_paths = [
        f"models/{symbol}_100x_simple/model.pkl",
        f"models/{symbol}_100x_leverage/rf_model.pkl",
    ]

    for model_path in model_paths:
        if Path(model_path).exists():
            logger.info(f"Found 100x model for {symbol}: {model_path}")

            # Load model config
            config_path = Path(model_path).parent / "config.json"
            if config_path.exists():
                with open(config_path, "r") as f:
                    config = json.load(f)
                    logger.info(f"Model accuracy: {config.get('accuracy', 'N/A')}")

            # Create ML signal generator
            generator = MLSignalGenerator(
                model_path=str(Path(model_path).parent),
                symbol=symbol,
                min_confidence=0.6,  # Higher confidence for 100:1 leverage
                position_size_method="dynamic",
            )
            return generator

    logger.warning(f"No 100x model found for {symbol}")
    return None


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Start paper trading with 100:1 leverage"
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["GBPUSD"],
        help="Symbols to trade (default: GBPUSD)",
    )
    parser.add_argument(
        "--capital", type=float, default=10000, help="Initial capital (default: 10000)"
    )
    parser.add_argument(
        "--port", type=int, default=4002, help="IB API port (default: 4002)"
    )
    parser.add_argument(
        "--max-positions",
        type=int,
        default=5,
        help="Maximum concurrent positions (default: 5)",
    )
    parser.add_argument(
        "--risk-per-trade",
        type=float,
        default=1.5,
        help="Risk per trade in % (default: 1.5)",
    )
    parser.add_argument(
        "--leverage", type=float, default=100, help="Account leverage (default: 100)"
    )
    parser.add_argument(
        "--min-lot-size",
        type=int,
        default=1000,
        help="Minimum lot size in units (default: 1000)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test connection only, don't start trading",
    )
    args = parser.parse_args()

    # Check if IB API is available
    if not IB_API_AVAILABLE:
        logger.error("Cannot start paper trading without IB API")
        logger.error("Please install: pip install ibapi")
        return 1

    # Test connection first
    if args.dry_run:
        logger.info("Running in dry-run mode - testing connection only")
        from scripts.test_ib_connection import test_connection

        if test_connection("127.0.0.1", args.port, 1):
            logger.info("Connection test successful!")
            return 0
        else:
            logger.error("Connection test failed!")
            return 1

    # Create signal generators for each symbol
    signal_generators = []
    for symbol in args.symbols:
        generator = create_100x_signal_generator(symbol)
        if generator:
            signal_generators.append(generator)

    if not signal_generators:
        logger.error("No signal generators available. Please train 100x models first.")
        logger.info("Run: python scripts/train_simple_100x_models.py")
        return 1

    # Paper trading configuration
    config = {
        "symbols": args.symbols,
        "timeframes": ["1m", "5m", "15m", "1h", "4h"],
        "base_timeframe": "1m",
        "signal_timeframe": "4h",  # We use 4H models
        "initial_capital": args.capital,
        "max_positions": args.max_positions,
        # IB connection settings
        "ib_config": {
            "host": "127.0.0.1",
            "port": args.port,
            "client_id": 1,
            "real_time_updates": True,
            "update_interval": 1.0,
        },
        # Risk management for 100:1 leverage
        "risk_config": {
            "max_risk_per_trade": args.risk_per_trade / 100,  # Convert to decimal
            "max_portfolio_risk": 0.10,  # 10% max portfolio risk
            "stop_loss_atr_multiplier": 0.5,  # Tight stops for 100:1
            "take_profit_atr_multiplier": 1.5,  # 3:1 R:R ratio
            "max_leverage": args.leverage,
            "min_position_size": args.min_lot_size,
            "position_sizing_method": "volatility_adjusted",
        },
        # Signal generators
        "signal_generators": signal_generators,
        # Trading hours (24/5 for forex)
        "working_hours": {
            "start_hour": 0,
            "end_hour": 24,
            "trading_days": [0, 1, 2, 3, 4],  # Monday to Friday
        },
        # Store results in database
        "enable_storage": True,
        # 100:1 leverage specific settings
        "leverage_config": {
            "account_leverage": args.leverage,
            "micro_lot_size": 1000,
            "min_position_units": args.min_lot_size,
            "max_total_exposure_pct": 5.0,  # Max 5x account size
            "circuit_breakers": {
                "daily_loss_limit": -0.05,
                "weekly_loss_limit": -0.10,
                "monthly_loss_limit": -0.15,
            },
        },
    }

    # Create paper trading engine
    global engine
    try:
        logger.info("Creating paper trading engine...")
        engine = PaperTradingEngine(config)

        # Set up signal handler
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Start paper trading
        logger.info("Starting paper trading with 100:1 leverage...")
        logger.info(f"Symbols: {args.symbols}")
        logger.info(f"Initial capital: ${args.capital:,.2f}")
        logger.info(f"Leverage: {args.leverage}:1")
        logger.info(f"Risk per trade: {args.risk_per_trade}%")
        logger.info(f"Max positions: {args.max_positions}")

        engine.start()

        # Main loop - print status every minute
        last_status_time = time.time()
        status_interval = 60  # seconds

        while is_running and engine.is_running:
            current_time = time.time()

            if current_time - last_status_time >= status_interval:
                # Get portfolio status
                portfolio = engine.get_portfolio_status()

                logger.info("=" * 60)
                logger.info("PORTFOLIO STATUS")
                logger.info("=" * 60)
                logger.info(f"Equity: ${portfolio['equity']:,.2f}")
                logger.info(f"Cash: ${portfolio['cash']:,.2f}")
                logger.info(
                    f"P&L: ${portfolio['equity'] - args.capital:,.2f} "
                    f"({(portfolio['equity'] / args.capital - 1) * 100:.2f}%)"
                )

                # Show positions
                if portfolio["positions"]:
                    logger.info("\nOpen Positions:")
                    for symbol, pos in portfolio["positions"].items():
                        logger.info(
                            f"  {symbol}: {pos['size']:,} units @ {pos['avg_price']:.5f} "
                            f"(P&L: ${pos['unrealized_pnl']:,.2f})"
                        )

                # Show recent trades
                recent_trades = portfolio["trades"][-5:]  # Last 5 trades
                if recent_trades:
                    logger.info("\nRecent Trades:")
                    for trade in recent_trades:
                        logger.info(
                            f"  {trade['timestamp']} - {trade['symbol']} "
                            f"{trade['action']} {trade['size']:,} @ {trade['price']:.5f}"
                        )

                last_status_time = current_time

            time.sleep(1)

        # Shutdown
        logger.info("Shutting down paper trading engine...")
        engine.stop()

        # Final report
        final_portfolio = engine.get_portfolio_status()
        logger.info("\n" + "=" * 60)
        logger.info("FINAL RESULTS")
        logger.info("=" * 60)
        logger.info(f"Starting capital: ${args.capital:,.2f}")
        logger.info(f"Final equity: ${final_portfolio['equity']:,.2f}")
        logger.info(f"Total P&L: ${final_portfolio['equity'] - args.capital:,.2f}")
        logger.info(
            f"Return: {(final_portfolio['equity'] / args.capital - 1) * 100:.2f}%"
        )
        logger.info(f"Total trades: {len(final_portfolio['trades'])}")

    except Exception as e:
        logger.error(f"Error in paper trading: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
