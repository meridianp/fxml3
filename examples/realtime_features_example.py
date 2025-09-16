#!/usr/bin/env python
"""
Example of real-time feature generation and prediction for FXML4.

This script demonstrates how to use the RealtimeFeatureGenerator and StreamingPredictor
classes to generate features and make predictions in real-time using live data from
Interactive Brokers.
"""

import argparse
import json
import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from fxml4.data_engineering.live_data_handler import (
    ConnectionState,
    LiveDataHandler,
    MarketStatus,
)
from fxml4.ml.realtime_features import RealtimeFeatureGenerator, StreamingPredictor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global variables for signal handling
live_data_handler = None
feature_generator = None
predictor = None
is_running = True
status_lock = threading.Lock()
latest_status = {}
latest_features = {}
latest_prediction = {}


def signal_handler(sig, frame):
    """Handle interrupt signals to gracefully shut down."""
    global is_running
    logger.info("Shutdown signal received, stopping...")
    is_running = False


def status_callback(status: Dict[str, Any]):
    """Callback for connection and market status changes."""
    global latest_status
    with status_lock:
        latest_status = status.copy()

    logger.info(
        f"Status update: Connection={status['connection_state']}, Market={status['market_status']}"
    )


def feature_callback(symbol: str, feature_df: pd.DataFrame):
    """Callback for feature updates."""
    global latest_features

    # Store the latest features
    latest_features[symbol] = feature_df.copy()

    # Log basic info
    num_features = len(feature_df.columns)
    latest_time = feature_df.index[-1] if not feature_df.empty else "N/A"

    logger.info(
        f"Feature update for {symbol}: {num_features} features, timestamp: {latest_time}"
    )


def prediction_callback(prediction: Dict[str, Any]):
    """Callback for prediction updates."""
    global latest_prediction

    # Store the latest prediction
    latest_prediction = prediction.copy()

    # Log prediction details
    symbol = prediction.get("symbol", "unknown")
    pred_class = prediction.get("class", "unknown")
    confidence = prediction.get("confidence", 0.0)
    timestamp = prediction.get("timestamp", "unknown")

    signal_type = "BUY" if pred_class == 1 else "SELL"

    logger.info(
        f"*** PREDICTION for {symbol}: {signal_type} with {confidence:.2%} confidence at {timestamp}"
    )


def load_model(model_path: str):
    """Load a trained model from disk.

    Args:
        model_path: Path to the model file

    Returns:
        Tuple of (model, metadata)
    """
    if not os.path.exists(model_path):
        logger.error(f"Model file {model_path} not found")
        return None, None

    try:
        # Load model
        model = joblib.load(model_path)

        # Load metadata if available
        metadata_path = model_path.replace(".joblib", "_metadata.json")
        if os.path.exists(metadata_path):
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
        else:
            metadata = {}

        # Load scaler if available
        scaler_path = model_path.replace(".joblib", "_scaler.joblib")
        if os.path.exists(scaler_path):
            metadata["scaler"] = joblib.load(scaler_path)

        logger.info(f"Loaded model from {model_path}")
        return model, metadata

    except Exception as e:
        logger.error(f"Error loading model: {e}")
        return None, None


def find_latest_model(models_dir: str, symbol: str = "gbpusd"):
    """Find the latest model file for a symbol.

    Args:
        models_dir: Directory to search in
        symbol: Symbol to find model for (default: 'gbpusd')

    Returns:
        Path to the latest model file or None if not found
    """
    try:
        # List all model files for the symbol
        model_files = [
            f
            for f in os.listdir(models_dir)
            if f.startswith(f"{symbol.lower()}_") and f.endswith("_metadata.json")
        ]

        if not model_files:
            return None

        # Sort by date (assuming format symbol_model_YYYYMMDD_HHMMSS)
        model_files.sort(reverse=True)

        # Return the path to the newest model file (joblib file, not metadata)
        newest_model = model_files[0].replace("_metadata.json", ".joblib")
        return os.path.join(models_dir, newest_model)

    except Exception as e:
        logger.error(f"Error finding latest model: {e}")
        return None


def print_status_summary():
    """Print a summary of the current status."""
    global latest_status, latest_features, latest_prediction

    with status_lock:
        status = latest_status.copy() if latest_status else {}

    if not status:
        logger.info("No status information available yet")
        return

    print("\n===== System Status =====")
    print(f"Connection: {status.get('connection_state', 'Unknown')}")
    print(f"Market Status: {status.get('market_status', 'Unknown')}")
    print(f"Trading Hours: {'Yes' if status.get('is_trading_hours', False) else 'No'}")
    print(f"Active Symbols: {', '.join(status.get('active_symbols', []))}")

    print("\n===== Latest Features =====")
    for symbol, features in latest_features.items():
        if features.empty:
            continue

        latest_time = features.index[-1]
        num_features = len(features.columns)
        print(f"\nSymbol: {symbol}")
        print(f"Time: {latest_time}")
        print(f"Feature Count: {num_features}")

        # Print top 5 features by absolute value
        if not features.empty:
            last_row = features.iloc[-1]
            top_features = last_row.abs().sort_values(ascending=False).head(5)
            print("Top Features:")
            for name, value in top_features.items():
                print(f"  {name}: {last_row[name]:.4f}")

    print("\n===== Latest Prediction =====")
    if latest_prediction:
        symbol = latest_prediction.get("symbol", "unknown")
        pred_class = latest_prediction.get("class", "unknown")
        confidence = latest_prediction.get("confidence", 0.0)
        timestamp = latest_prediction.get("timestamp", "unknown")

        signal_type = "BUY" if pred_class == 1 else "SELL"

        print(f"Symbol: {symbol}")
        print(f"Signal: {signal_type}")
        print(f"Confidence: {confidence:.2%}")
        print(f"Time: {timestamp}")
    else:
        print("No predictions available yet")


def run_realtime_features(args):
    """Run the realtime feature generation and prediction example.

    Args:
        args: Command line arguments
    """
    global live_data_handler, feature_generator, predictor, is_running

    # Parse symbols
    symbol = args.symbol

    # Configure LiveDataHandler
    live_data_config = {
        "market_type": args.market_type,
        "symbols": [symbol],
        "timeframes": args.timeframes.split(","),
        "base_timeframe": "1m",
        "observe_market_hours": not args.ignore_market_hours,
        "ib_config": {
            "host": args.host,
            "port": args.port,
            "client_id": args.client_id,
            "real_time_updates": True,
            "update_interval": 0.5,  # Process ticks every 0.5 seconds
        },
    }

    # Find or load model
    model, metadata = None, None
    if args.model_path:
        model, metadata = load_model(args.model_path)
    else:
        # Find latest model
        model_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
        latest_model_path = find_latest_model(model_dir, symbol)
        if latest_model_path:
            model, metadata = load_model(latest_model_path)

    # If no model found, create a dummy model
    if model is None:
        logger.warning("No model found, creating a dummy random forest model")
        model = RandomForestClassifier(n_estimators=10)
        model.fit(np.random.rand(100, 10), np.random.randint(0, 2, 100))
        metadata = {"feature_list": [f"feature_{i}" for i in range(10)]}

    try:
        # Create and start LiveDataHandler
        logger.info("Creating LiveDataHandler...")
        live_data_handler = LiveDataHandler(live_data_config)

        # Register status callback
        live_data_handler.register_status_callback(status_callback)

        # Start the handler
        logger.info("Starting LiveDataHandler...")
        live_data_handler.start()

        # Wait for connection and market data
        logger.info("Waiting for connection and market data...")
        time.sleep(5)

        # Configure feature generator
        feature_config = {
            "symbol": symbol,
            "timeframe": args.timeframe,
            "feature_list": metadata.get(
                "feature_list", ["close", "open", "high", "low", "volume"]
            ),
            "lookback": args.lookback,
            "prediction_horizon": args.prediction_horizon,
            "include_pivots": args.include_pivots,
            "include_sessions": args.include_sessions,
        }

        # Create feature generator
        logger.info("Creating RealtimeFeatureGenerator...")
        feature_generator = RealtimeFeatureGenerator(
            live_data_handler=live_data_handler,
            feature_config=feature_config,
            model_metadata=metadata,
        )

        # Register feature callback
        feature_generator.register_feature_callback(feature_callback)

        # Configure predictor
        prediction_config = {
            "symbol": symbol,
            "confidence_threshold": args.confidence_threshold,
            "cooldown_periods": args.cooldown_periods,
        }

        # Create predictor
        logger.info("Creating StreamingPredictor...")
        predictor = StreamingPredictor(
            model=model,
            feature_generator=feature_generator,
            prediction_config=prediction_config,
        )

        # Register prediction callback
        predictor.register_prediction_callback(prediction_callback)

        # Run main loop
        logger.info("Running main loop, press Ctrl+C to stop...")
        last_status_time = time.time()
        status_interval = args.status_interval

        while is_running:
            # Print status summary periodically
            now = time.time()
            if now - last_status_time >= status_interval:
                print_status_summary()
                last_status_time = now

            # Sleep to avoid high CPU usage
            time.sleep(1.0)

    except KeyboardInterrupt:
        logger.info("Interrupted by user, shutting down...")

    except Exception as e:
        logger.error(f"Error in realtime feature generation: {e}")

    finally:
        # Stop components in reverse order
        if predictor:
            logger.info("Stopping StreamingPredictor...")
            predictor.stop()

        if feature_generator:
            logger.info("Stopping RealtimeFeatureGenerator...")
            feature_generator.stop()

        if live_data_handler:
            logger.info("Stopping LiveDataHandler...")
            live_data_handler.stop()

        logger.info("Shutdown complete")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="FXML4 Real-time Feature Generation and Prediction"
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

    # Symbol and timeframes
    parser.add_argument(
        "--symbol", default="GBPUSD", help="Symbol to generate features for"
    )
    parser.add_argument(
        "--timeframe", default="1h", help="Timeframe for feature generation"
    )
    parser.add_argument(
        "--timeframes",
        default="1m,5m,15m,1h,4h,1d",
        help="Comma-separated list of timeframes to process",
    )

    # Market parameters
    parser.add_argument(
        "--market-type",
        default="forex",
        choices=["forex", "us_equities"],
        help="Market type (affects trading hours)",
    )
    parser.add_argument(
        "--ignore-market-hours",
        action="store_true",
        help="Ignore market hours (treat market as always open)",
    )

    # Feature generation
    parser.add_argument(
        "--lookback",
        type=int,
        default=30,
        help="Lookback period for feature generation",
    )
    parser.add_argument(
        "--prediction-horizon",
        type=int,
        default=12,
        help="Prediction horizon in candles",
    )
    parser.add_argument(
        "--include-pivots",
        action="store_true",
        help="Include pivot points in feature generation",
    )
    parser.add_argument(
        "--include-sessions",
        action="store_true",
        help="Include session features in feature generation",
    )

    # Model parameters
    parser.add_argument(
        "--model-path", type=str, default="", help="Path to the trained model file"
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.6,
        help="Confidence threshold for predictions",
    )
    parser.add_argument(
        "--cooldown-periods",
        type=int,
        default=3,
        help="Cooldown periods between predictions",
    )

    # Display options
    parser.add_argument(
        "--status-interval",
        type=int,
        default=30,
        help="Interval in seconds between status displays",
    )

    args = parser.parse_args()

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run the example
    run_realtime_features(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
