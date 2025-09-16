#!/usr/bin/env python3
"""
Test the GBP/USD ML pipeline integration with Google Vertex AI.

This script:
1. Loads GBP/USD historical data
2. Prepares features and targets
3. Tests the local ML pipeline
4. Integrates with Google Vertex AI for model registration
"""

import logging
import os
import sys
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sklearn.model_selection import train_test_split

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

# Import Vertex AI
import sys

# FXML4 imports
from fxml4.ml.gbpusd_model import GBPUSDModel, train_gbpusd_model
from fxml4.strategy.gbpusd_signal_generator import (
    GBPUSDSignalGenerator,
    create_ensemble_generator,
)

sys.path.append(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ml")
)
from vertex_ai import VertexAIModel, check_vertex_availability, get_default_project_id

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def test_local_pipeline():
    """Test the local ML pipeline for GBP/USD."""
    # Load data
    logger.info("Loading GBP/USD data")
    data = pd.read_parquet("output/C_GBPUSD_4h.parquet")

    # Create model
    logger.info("Creating GBP/USD model")
    model = GBPUSDModel(
        model_type="random_forest",
        model_params={"n_estimators": 100, "max_depth": 10, "random_state": 42},
    )

    # Prepare features
    logger.info("Preparing features")
    features = model.prepare_features(
        data, target_horizon=12, add_lag_features=True, create_target=True
    )

    # Split data into train and test sets
    target_col = "target_12"
    X = features.drop(columns=[target_col])
    y = features[target_col]

    # Use time-based train-test split (last 20% as test)
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    logger.info(f"Training set: {len(X_train)} samples")
    logger.info(f"Test set: {len(X_test)} samples")

    # Scale features
    X_train_scaled = model.scale_features(X_train, refit=True)[0]
    X_test_scaled = model.scale_features(X_test, refit=False)[0]

    # Train model
    logger.info("Training model")
    model.model.fit(X_train_scaled, y_train)

    # Evaluate model
    y_pred = model.model.predict(X_test_scaled)

    from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, average="weighted")
    recall = recall_score(y_test, y_pred, average="weighted")
    f1 = f1_score(y_test, y_pred, average="weighted")

    logger.info(f"Accuracy: {accuracy:.4f}")
    logger.info(f"Precision: {precision:.4f}")
    logger.info(f"Recall: {recall:.4f}")
    logger.info(f"F1 Score: {f1:.4f}")

    # Calculate feature importance
    model._store_feature_importance()
    top_features = model.get_top_features(n=10)
    logger.info("Top 10 features:")
    for _, row in top_features.iterrows():
        logger.info(f"  {row['feature']}: {row['importance']:.4f}")

    # Save model
    logger.info("Saving model")
    model.save(directory="models")

    return model


def test_vertex_ai_integration(model):
    """Test integration with Google Vertex AI."""
    if not check_vertex_availability():
        logger.error(
            "Vertex AI integration not available. Please install required packages."
        )
        return

    # Get project ID
    project_id = get_default_project_id()
    logger.info(f"Using Google Cloud project: {project_id}")

    # Create a Vertex AI model wrapper
    vertex_model = VertexAIModel(
        project_id=project_id,
        location="us-central1",
        staging_bucket=f"gs://{project_id}-fxml4-models",
    )

    # Register model with Vertex AI
    try:
        logger.info(f"Registering model {model.name} with Vertex AI")
        result = vertex_model.register_model(
            model=model,
            version=datetime.now().strftime("v%Y%m%d"),
            description="GBP/USD prediction model for 4h timeframe",
            labels={
                "symbol": "GBPUSD",
                "timeframe": "4h",
                "environment": "development",
            },
        )

        logger.info(f"Model registered with Vertex AI: {result['vertex_model_id']}")
        return result
    except Exception as e:
        logger.error(f"Error registering model with Vertex AI: {e}")
        return None


def test_signal_generation(model):
    """Test signal generation using the trained model."""
    # Load data
    data = pd.read_parquet("output/C_GBPUSD_4h.parquet")

    # Create signal generator
    logger.info("Creating signal generator")
    signal_generator = GBPUSDSignalGenerator(
        model=model, config={"threshold": 0.65, "probability_mode": True}
    )

    # Generate signals for the last 30 data points
    recent_data = data.tail(30)
    signals = signal_generator.generate_signals(
        recent_data, symbol="GBPUSD", timeframe="4h"
    )

    logger.info(f"Generated {len(signals)} signals")
    for signal in signals:
        logger.info(
            f"Signal: {signal.signal_type}, Strength: {signal.strength:.4f}, Time: {signal.timestamp}"
        )

    # Test backtesting
    logger.info("Running backtest")
    results = signal_generator.backtest(data.tail(500), target_horizon=12)

    # Calculate performance metrics
    if not results.empty:
        total_trades = len(results[results["prediction"] != 0])
        winning_trades = len(
            results[(results["prediction"] != 0) & (results["signal_return"] > 0)]
        )
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        logger.info(f"Backtest results:")
        logger.info(f"  Total trades: {total_trades}")
        logger.info(f"  Win rate: {win_rate:.4f}")
        logger.info(f"  Final return: {results['cum_return'].iloc[-1]:.4f}")
        logger.info(f"  Max drawdown: {results['drawdown'].min():.4f}")

    return signals


def main():
    """Main function."""
    logger.info("Testing GBP/USD ML pipeline with Vertex AI integration")

    # Test local pipeline
    model = test_local_pipeline()

    # Test signal generation
    signals = test_signal_generation(model)

    # Skip Vertex AI integration for now
    logger.warning("Skipping Vertex AI integration for this test")

    logger.info("Test completed successfully")


if __name__ == "__main__":
    main()
