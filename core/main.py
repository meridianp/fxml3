"""Main entry point for FXML4 trading system.

This module provides the main entry point for running the FXML4 system
with various modes and configurations.
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from fxml4.api.main import app as api_app
from fxml4.backtesting.engine import BacktestEngine
from fxml4.config import Config, get_config
from fxml4.data_engineering.data_feeds import DataFeedFactory
from fxml4.ml.model_registry import ModelRegistry
from fxml4.risk_management.live import LiveRiskManager as RiskManager
from fxml4.strategy.dynamic_exit_strategy import (
    DynamicExitStrategy as ExitStrategyManager,
)
from fxml4.strategy.integrated_signal_generator import (
    IntegratedSignalGenerator as SignalGenerator,
)
from fxml4.utils.logging import setup_logging

logger = logging.getLogger(__name__)


class FXML4Application:
    """Main application class for FXML4 trading system."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize the application.

        Args:
            config_path: Path to configuration file
        """
        # Load configuration
        self.config = get_config(config_path)

        # Setup logging
        setup_logging(
            level=self.config.get("logging.level", "INFO"),
            log_file=self.config.get("logging.file"),
        )

        logger.info("FXML4 Application initialized")

        # Initialize components
        self.model_registry = None
        self.signal_generator = None
        self.risk_manager = None
        self.backtest_engine = None

    def initialize_components(self):
        """Initialize application components."""
        logger.info("Initializing application components")

        # Initialize model registry
        self.model_registry = ModelRegistry(
            storage_path=self.config.get("model_registry.storage_path")
        )

        # Initialize signal generator
        self.signal_generator = SignalGenerator(self.config)

        # Initialize risk manager
        self.risk_manager = RiskManager(self.config)

        # Initialize backtest engine
        self.backtest_engine = BacktestEngine(self.config)

        logger.info("All components initialized successfully")

    def run_backtest(
        self,
        strategy: str,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str = "1h",
        initial_capital: float = 10000.0,
    ):
        """Run a backtest.

        Args:
            strategy: Strategy name
            symbol: Trading symbol
            start_date: Backtest start date
            end_date: Backtest end date
            timeframe: Data timeframe
            initial_capital: Initial capital
        """
        logger.info(
            "Running backtest: strategy=%s, symbol=%s, period=%s to %s",
            strategy,
            symbol,
            start_date,
            end_date,
        )

        # Load data
        data_feed = DataFeedFactory.create(
            self.config.get("data_feed.type", "csv"), self.config.get("data_feed", {})
        )

        data = data_feed.fetch_data(
            symbol=symbol, timeframe=timeframe, start_date=start_date, end_date=end_date
        )

        # Run backtest
        results = self.backtest_engine.run(
            strategy_name=strategy, data=data, initial_capital=initial_capital
        )

        # Log results
        logger.info("Backtest completed:")
        logger.info("  Total Return: %.2f%%", results.get("total_return", 0) * 100)
        logger.info("  Sharpe Ratio: %.2f", results.get("sharpe_ratio", 0))
        logger.info("  Max Drawdown: %.2f%%", results.get("max_drawdown", 0) * 100)
        logger.info("  Total Trades: %d", results.get("total_trades", 0))

        return results

    def run_live_trading(self, strategy: str, symbols: list, **kwargs):
        """Run live trading.

        Args:
            strategy: Strategy name
            symbols: List of trading symbols
            **kwargs: Additional arguments
        """
        logger.info("Starting live trading: strategy=%s, symbols=%s", strategy, symbols)

        # TODO: Implement live trading logic
        raise NotImplementedError("Live trading not yet implemented")

    def run_api_server(self, host: str = "0.0.0.0", port: int = 8000):
        """Run the API server.

        Args:
            host: Server host
            port: Server port
        """
        import uvicorn

        logger.info("Starting API server on %s:%d", host, port)
        uvicorn.run(api_app, host=host, port=port)

    def run_data_collection(self, symbols: list, timeframe: str, **kwargs):
        """Run data collection.

        Args:
            symbols: List of symbols to collect data for
            timeframe: Timeframe for data collection
            **kwargs: Additional arguments
        """
        logger.info(
            "Starting data collection: symbols=%s, timeframe=%s", symbols, timeframe
        )

        data_feed = DataFeedFactory.create(
            self.config.get("data_feed.type", "ib"), self.config.get("data_feed", {})
        )

        for symbol in symbols:
            try:
                data = data_feed.fetch_data(
                    symbol=symbol, timeframe=timeframe, **kwargs
                )

                # Save data if CSV feed is configured
                if hasattr(data_feed, "save_data"):
                    data_feed.save_data(data, symbol, timeframe)

                logger.info("Collected %d bars for %s", len(data), symbol)

            except Exception as e:
                logger.error("Error collecting data for %s: %s", symbol, e)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="FXML4 Trading System")
    parser.add_argument("--config", type=str, help="Path to configuration file")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Backtest command
    backtest_parser = subparsers.add_parser("backtest", help="Run backtest")
    backtest_parser.add_argument("--strategy", required=True, help="Strategy name")
    backtest_parser.add_argument("--symbol", required=True, help="Trading symbol")
    backtest_parser.add_argument(
        "--start-date", required=True, help="Start date (YYYY-MM-DD)"
    )
    backtest_parser.add_argument(
        "--end-date", required=True, help="End date (YYYY-MM-DD)"
    )
    backtest_parser.add_argument("--timeframe", default="1h", help="Timeframe")
    backtest_parser.add_argument(
        "--capital", type=float, default=10000, help="Initial capital"
    )

    # Live trading command
    live_parser = subparsers.add_parser("live", help="Run live trading")
    live_parser.add_argument("--strategy", required=True, help="Strategy name")
    live_parser.add_argument(
        "--symbols", nargs="+", required=True, help="Trading symbols"
    )

    # API server command
    api_parser = subparsers.add_parser("api", help="Run API server")
    api_parser.add_argument("--host", default="0.0.0.0", help="Server host")
    api_parser.add_argument("--port", type=int, default=8000, help="Server port")

    # Data collection command
    data_parser = subparsers.add_parser("collect", help="Collect market data")
    data_parser.add_argument(
        "--symbols", nargs="+", required=True, help="Symbols to collect"
    )
    data_parser.add_argument("--timeframe", default="1h", help="Timeframe")
    data_parser.add_argument(
        "--days", type=int, default=30, help="Number of days to collect"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Create application
    app = FXML4Application(config_path=args.config)

    try:
        if args.command == "backtest":
            app.initialize_components()
            app.run_backtest(
                strategy=args.strategy,
                symbol=args.symbol,
                start_date=datetime.strptime(args.start_date, "%Y-%m-%d"),
                end_date=datetime.strptime(args.end_date, "%Y-%m-%d"),
                timeframe=args.timeframe,
                initial_capital=args.capital,
            )

        elif args.command == "live":
            app.initialize_components()
            app.run_live_trading(strategy=args.strategy, symbols=args.symbols)

        elif args.command == "api":
            app.run_api_server(host=args.host, port=args.port)

        elif args.command == "collect":
            from datetime import timedelta

            end_date = datetime.now()
            start_date = end_date - timedelta(days=args.days)

            app.run_data_collection(
                symbols=args.symbols,
                timeframe=args.timeframe,
                start_date=start_date,
                end_date=end_date,
            )

    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error("Application error: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
