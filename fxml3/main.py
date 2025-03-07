"""Main entry point for the FXML3 application."""

import argparse
import logging
import os
import sys
from typing import List, Optional

from fxml3.config import Config


def setup_logging(log_level: str) -> None:
    """Set up logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("fxml3.log"),
        ],
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description="FXML3 - AI-Enhanced Elliott Wave Analysis")
    
    parser.add_argument(
        "--config", 
        type=str, 
        default="config/default.yaml",
        help="Path to configuration file",
    )
    
    parser.add_argument(
        "--mode",
        type=str,
        choices=["fetch", "analyze", "backtest", "train", "ui"],
        default="ui",
        help="Operation mode",
    )
    
    parser.add_argument(
        "--symbols",
        type=str,
        nargs="+",
        help="Forex symbols to analyze (overrides config)",
    )
    
    parser.add_argument(
        "--timeframes",
        type=str,
        nargs="+",
        help="Timeframes to analyze (overrides config)",
    )
    
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date for data (YYYY-MM-DD)",
    )
    
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date for data (YYYY-MM-DD)",
    )
    
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level",
    )
    
    return parser.parse_args()


def load_config(config_path: str) -> Config:
    """Load configuration from file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Loaded configuration
    """
    if not os.path.exists(config_path):
        logging.error(f"Configuration file not found: {config_path}")
        print(f"Error: Configuration file not found: {config_path}")
        sys.exit(1)
        
    return Config.from_yaml(config_path)


def update_config_from_args(config: Config, args: argparse.Namespace) -> Config:
    """Update configuration with command line arguments.
    
    Args:
        config: Configuration object
        args: Command line arguments
        
    Returns:
        Updated configuration
    """
    # Update data configuration
    if args.symbols:
        config.data.symbols = args.symbols
    
    if args.timeframes:
        config.data.timeframes = args.timeframes
    
    if args.start_date:
        config.data.start_date = args.start_date
    
    if args.end_date:
        config.data.end_date = args.end_date
    
    # Update logging level
    if args.log_level:
        config.log_level = args.log_level
    
    return config


def run_fetch_mode(config: Config) -> None:
    """Run the data fetching mode.
    
    Args:
        config: Application configuration
    """
    from fxml3.data_engineering.data_loader import ForexDataLoader
    
    logging.info("Running in data fetch mode")
    logging.info(f"Fetching data for symbols: {config.data.symbols}")
    logging.info(f"Timeframes: {config.data.timeframes}")
    
    loader = ForexDataLoader(data_source=config.data.source)
    
    for symbol in config.data.symbols:
        for timeframe in config.data.timeframes:
            logging.info(f"Fetching {symbol} {timeframe} data")
            # Implement actual fetching logic


def run_analyze_mode(config: Config) -> None:
    """Run the wave analysis mode.
    
    Args:
        config: Application configuration
    """
    from fxml3.wave_analysis.elliott_wave import ElliottWaveAnalyzer
    
    logging.info("Running in wave analysis mode")
    logging.info(f"Analyzing waves for symbols: {config.data.symbols}")
    
    analyzer = ElliottWaveAnalyzer(
        fib_tolerance=config.wave.fib_tolerance,
        min_wave_size=config.wave.min_wave_size,
    )
    
    # Implement actual analysis logic


def run_backtest_mode(config: Config) -> None:
    """Run the backtesting mode.
    
    Args:
        config: Application configuration
    """
    logging.info("Running in backtest mode")
    # Implement backtesting logic


def run_train_mode(config: Config) -> None:
    """Run the RL training mode.
    
    Args:
        config: Application configuration
    """
    logging.info("Running in training mode")
    # Implement RL training logic


def run_ui_mode(config: Config) -> None:
    """Run the UI mode.
    
    Args:
        config: Application configuration
    """
    logging.info("Running in UI mode")
    logging.info(f"Using {config.ui.framework} framework")
    
    if config.ui.framework.lower() == "streamlit":
        # We don't import streamlit here because it has side effects
        # Instead, we'll call the streamlit module directly
        logging.info(f"Starting Streamlit on port {config.ui.port}")
        print(f"To start the Streamlit UI, run: streamlit run fxml3/ui/streamlit_app.py")
    else:
        logging.error(f"Unsupported UI framework: {config.ui.framework}")


def main() -> None:
    """Main entry point for the application."""
    args = parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Update configuration from command line arguments
    config = update_config_from_args(config, args)
    
    # Set up logging
    setup_logging(config.log_level)
    
    logging.info("Starting FXML3 application")
    
    # Run the selected mode
    mode_handlers = {
        "fetch": run_fetch_mode,
        "analyze": run_analyze_mode,
        "backtest": run_backtest_mode,
        "train": run_train_mode,
        "ui": run_ui_mode,
    }
    
    mode_handler = mode_handlers.get(args.mode)
    if mode_handler:
        mode_handler(config)
    else:
        logging.error(f"Unsupported mode: {args.mode}")
        sys.exit(1)
    
    logging.info("FXML3 application completed")


if __name__ == "__main__":
    main()