"""Main entry point for FXML4.

This module provides the main entry point for the FXML4 application,
including command-line interface and application initialization.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

from fxml4.config import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments.
    
    Args:
        args: Command-line arguments to parse. If None, uses sys.argv.
        
    Returns:
        Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description="FXML4: Advanced Forex Trading Platform")
    
    parser.add_argument(
        "--config", 
        type=str, 
        help="Path to configuration file"
    )
    
    parser.add_argument(
        "--mode",
        choices=["backtest", "train", "predict", "serve", "dashboard"],
        default="backtest",
        help="Operation mode (default: backtest)",
    )
    
    parser.add_argument(
        "--symbol", 
        type=str, 
        help="Trading symbol (e.g., EURUSD)"
    )
    
    parser.add_argument(
        "--timeframe", 
        type=str, 
        help="Trading timeframe (e.g., 1h, 4h, 1d)"
    )
    
    parser.add_argument(
        "--start-date", 
        type=str, 
        help="Start date for backtesting (YYYY-MM-DD)"
    )
    
    parser.add_argument(
        "--end-date", 
        type=str, 
        help="End date for backtesting (YYYY-MM-DD)"
    )
    
    parser.add_argument(
        "--strategy", 
        type=str, 
        help="Strategy name to use"
    )
    
    parser.add_argument(
        "--debug", 
        action="store_true", 
        help="Enable debug logging"
    )
    
    return parser.parse_args(args)


def initialize_app(args: argparse.Namespace) -> None:
    """Initialize the application based on command-line arguments.
    
    Args:
        args: Parsed command-line arguments.
    """
    # Set up logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("Initializing FXML4...")
    
    # Initialize components based on mode
    if args.mode == "backtest":
        logger.info("Starting backtesting mode")
        # TODO: Initialize backtesting components
    elif args.mode == "train":
        logger.info("Starting model training mode")
        # TODO: Initialize training components
    elif args.mode == "predict":
        logger.info("Starting prediction mode")
        # TODO: Initialize prediction components
    elif args.mode == "serve":
        logger.info("Starting API server mode")
        # TODO: Initialize API server
    elif args.mode == "dashboard":
        logger.info("Starting dashboard mode")
        # TODO: Initialize dashboard


def main(args: Optional[List[str]] = None) -> int:
    """Main entry point for the application.
    
    Args:
        args: Command-line arguments. If None, uses sys.argv.
        
    Returns:
        Exit code.
    """
    try:
        parsed_args = parse_args(args)
        initialize_app(parsed_args)
        logger.info("FXML4 started successfully")
        return 0
    except Exception as e:
        logger.exception("Error starting FXML4: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())