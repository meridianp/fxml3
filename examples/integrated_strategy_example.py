#!/usr/bin/env python
"""Example demonstrating the integrated strategy framework.

This example shows how to combine ML, Elliott Wave, and sentiment signals
into a unified trading strategy.
"""

import argparse
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from fxml4.config import load_config
from fxml4.data_engineering.data_feeds.base_feed import DataFeed
from fxml4.data_engineering.data_feeds.csv_feed import CSVDataFeed
from fxml4.llm_integration.rag import RAGClient
from fxml4.ml.features import create_technical_features
from fxml4.strategy.integrated_strategy import (
    IntegratedStrategy,
    Signal,
    SignalSource,
    SignalType,
)
from fxml4.strategy.ml_signal_generator import (
    EnsembleMLSignalGenerator,
    MLSignalGenerator,
)
from fxml4.strategy.sentiment_signal_generator import LLMSentimentSignalGenerator
from fxml4.strategy.wave_signal_generator import LLMWaveSignalGenerator
from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_forex_data(
    symbol: str,
    timeframe: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """Load forex data from CSV files.

    Args:
        symbol: Trading symbol (e.g., 'EURUSD').
        timeframe: Timeframe (e.g., '1h', '4h', '1d').
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).

    Returns:
        DataFrame with forex data.
    """
    # Default dates if not provided
    if not start_date:
        start_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    # Initialize data feed
    data_feed = CSVDataFeed(
        base_dir=os.path.join("input", f"C_{symbol}"),
        symbol=symbol,
        timeframe=timeframe,
    )

    # Load data
    data = data_feed.get_historical_data(
        start_date=start_date,
        end_date=end_date,
        include_technical_indicators=True,
    )

    logger.info(f"Loaded {len(data)} records for {symbol} ({timeframe})")
    return data


def prepare_data_for_ml(data: pd.DataFrame) -> pd.DataFrame:
    """Prepare data for ML model.

    Args:
        data: Raw market data.

    Returns:
        DataFrame with features for ML model.
    """
    # Create technical features
    features = create_technical_features(
        data,
        indicators=["sma", "ema", "rsi", "macd", "bollinger", "atr", "adx"],
        custom_indicators=[],
    )

    # Create target variable (simple example: future price movement)
    features["future_return"] = features["close"].pct_change(5).shift(-5)
    features["target"] = (features["future_return"] > 0).astype(int)

    # Drop NaN values
    features = features.dropna()

    return features


def train_simple_ml_model(features: pd.DataFrame) -> RandomForestClassifier:
    """Train a simple ML model for demonstration.

    Args:
        features: Features DataFrame.

    Returns:
        Trained ML model.
    """
    # Select features for training
    feature_columns = [
        "rsi",
        "macd",
        "macdsignal",
        "macd_hist",
        "bollinger_upper",
        "bollinger_middle",
        "bollinger_lower",
        "sma_10",
        "sma_20",
        "sma_50",
        "ema_10",
        "ema_20",
        "adx",
        "atr",
    ]

    # Make sure all feature columns exist
    available_features = [col for col in feature_columns if col in features.columns]

    # Split data into train/test
    train_size = int(len(features) * 0.8)
    train_data = features.iloc[:train_size]

    # Create simple Random Forest model
    model = RandomForestClassifier(
        n_estimators=100, min_samples_split=10, random_state=42
    )

    # Train model
    model.fit(train_data[available_features], train_data["target"])

    logger.info(f"Trained ML model with {len(available_features)} features")
    return model


def setup_integrated_strategy(
    ml_model: Any,
    wave_analyzer: Any,
    rag_client: Any,
) -> IntegratedStrategy:
    """Set up the integrated trading strategy.

    Args:
        ml_model: Trained ML model.
        wave_analyzer: Elliott Wave analyzer.
        rag_client: RAG client for LLM integration.

    Returns:
        Configured integrated strategy.
    """
    # Create integrated strategy
    strategy_config = {
        "name": "MLWaveSentimentStrategy",
        "signal_combiner": {
            "method": "weighted",
            "weights": {
                "ml": 0.5,
                "wave": 0.3,
                "sentiment": 0.2,
                "technical": 0.1,
            },
            "min_confidence": 0.6,
        },
    }

    integrated_strategy = IntegratedStrategy(strategy_config)

    # Add ML signal generator
    ml_config = {
        "threshold": 0.65,
        "probability_mode": True,
        "use_technical_features": True,
        "technical_indicators": [
            "sma",
            "ema",
            "rsi",
            "macd",
            "bollinger",
            "atr",
            "adx",
        ],
    }
    ml_generator = MLSignalGenerator(ml_model, ml_config)
    integrated_strategy.add_signal_generator(ml_generator)

    # Add Elliott Wave signal generator
    wave_config = {
        "threshold": 0.7,
        "use_llm": True,
        "llm_confidence_weight": 0.4,
        "rag": rag_client,
        "pattern_thresholds": {
            "impulse": 0.7,
            "correction": 0.65,
            "diagonal": 0.75,
            "triangle": 0.7,
            "zigzag": 0.65,
            "flat": 0.65,
        },
    }
    wave_generator = LLMWaveSignalGenerator(wave_analyzer, rag_client, wave_config)
    integrated_strategy.add_signal_generator(wave_generator)

    # Add sentiment signal generator
    sentiment_config = {
        "threshold": 0.7,
        "lookback_days": 3,
        "news_limit": 30,
        "news_api": None,  # Would need a real news API service
        "use_cache": True,
        "cache_expiry": 4,  # hours
    }
    sentiment_generator = LLMSentimentSignalGenerator(rag_client, sentiment_config)
    integrated_strategy.add_signal_generator(sentiment_generator)

    return integrated_strategy


def visualize_signals(
    data: pd.DataFrame, signals: List[Signal], title: str = "Trading Signals"
) -> None:
    """Visualize trading signals on price chart.

    Args:
        data: Market data.
        signals: List of trading signals.
        title: Chart title.
    """
    plt.figure(figsize=(12, 8))

    # Plot price data
    plt.subplot(2, 1, 1)
    plt.plot(data.index, data["close"], label="Close Price")

    # Mark signals on the chart
    for signal in signals:
        if signal.signal_type == SignalType.ENTRY_LONG:
            plt.scatter(
                signal.timestamp,
                data.loc[data.index == signal.timestamp, "close"].values[0] * 0.998,
                marker="^",
                color="green",
                s=100,
                label=f"{signal.source.value} Long ({signal.strength:.2f})",
            )
        elif signal.signal_type == SignalType.ENTRY_SHORT:
            plt.scatter(
                signal.timestamp,
                data.loc[data.index == signal.timestamp, "close"].values[0] * 1.002,
                marker="v",
                color="red",
                s=100,
                label=f"{signal.source.value} Short ({signal.strength:.2f})",
            )
        elif signal.signal_type == SignalType.EXIT_LONG:
            plt.scatter(
                signal.timestamp,
                data.loc[data.index == signal.timestamp, "close"].values[0] * 0.998,
                marker="o",
                color="orange",
                s=80,
                label=f"{signal.source.value} Exit Long ({signal.strength:.2f})",
            )
        elif signal.signal_type == SignalType.EXIT_SHORT:
            plt.scatter(
                signal.timestamp,
                data.loc[data.index == signal.timestamp, "close"].values[0] * 1.002,
                marker="o",
                color="purple",
                s=80,
                label=f"{signal.source.value} Exit Short ({signal.strength:.2f})",
            )

    plt.title(f"{title} - Price Chart")
    plt.ylabel("Price")
    plt.grid(True)

    # Add signal strengths as a subplot
    plt.subplot(2, 1, 2)

    signal_dates = [s.timestamp for s in signals]
    signal_strengths = [s.strength for s in signals]
    signal_types = [s.signal_type.value for s in signals]
    signal_sources = [s.source.value for s in signals]

    # Plot signal strengths as a bar chart
    bars = plt.bar(signal_dates, signal_strengths, alpha=0.7)

    # Color bars based on signal type
    for i, signal_type in enumerate(signal_types):
        if "entry_long" in signal_type:
            bars[i].set_color("green")
        elif "entry_short" in signal_type:
            bars[i].set_color("red")
        elif "exit" in signal_type:
            bars[i].set_color("orange")

    plt.title("Signal Strengths by Source")
    plt.ylabel("Strength")
    plt.ylim(0, 1)
    plt.grid(True)

    # Create a separate legend for signal sources
    source_colors = {
        "ML": "blue",
        "WAVE": "purple",
        "SENTIMENT": "brown",
        "ENSEMBLE": "black",
    }

    source_patches = [
        plt.Line2D(
            [0], [0], color=source_colors.get(src.upper(), "gray"), lw=3, label=src
        )
        for src in set(signal_sources)
    ]
    plt.legend(handles=source_patches, loc="upper right")

    plt.tight_layout()
    plt.show()


def main():
    """Run the integrated strategy example."""
    parser = argparse.ArgumentParser(description="Integrated Strategy Example")
    parser.add_argument("--symbol", type=str, default="EURUSD", help="Trading symbol")
    parser.add_argument("--timeframe", type=str, default="1h", help="Timeframe")
    parser.add_argument(
        "--start", type=str, default=None, help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument("--end", type=str, default=None, help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--config", type=str, default="config/default.yaml", help="Config file path"
    )

    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)

    # Load forex data
    data = load_forex_data(
        symbol=args.symbol,
        timeframe=args.timeframe,
        start_date=args.start,
        end_date=args.end,
    )

    # Prepare data for ML
    features = prepare_data_for_ml(data)

    # Train a simple ML model
    ml_model = train_simple_ml_model(features)

    # Initialize Elliott Wave analyzer (simplified)
    wave_analyzer = ElliottWaveAnalyzer()

    # Initialize RAG client (simplified)
    rag_client = RAGClient(config.get("llm", {}))

    # Set up integrated strategy
    strategy = setup_integrated_strategy(
        ml_model=ml_model, wave_analyzer=wave_analyzer, rag_client=rag_client
    )

    # Generate signals for the last 30 days of data
    test_data = data.iloc[-30:]
    all_signals = []

    for i in range(10):  # Generate signals for 10 sample points
        idx = i * 3  # Every 3 days
        if idx >= len(test_data):
            break

        current_data = test_data.iloc[: idx + 1]

        if len(current_data) < 20:  # Need enough data for features
            continue

        # Generate signal for this point
        signals = strategy.generate_signals(
            current_data, symbol=args.symbol, timeframe=args.timeframe
        )

        if signals:
            all_signals.append(signals)
            logger.info(f"Generated signal: {signals}")

    # Flatten list of signals
    flat_signals = [
        s
        for sublist in all_signals
        for s in (sublist if isinstance(sublist, list) else [sublist])
    ]

    # Visualize signals
    if flat_signals:
        visualize_signals(
            data=test_data,
            signals=flat_signals,
            title=f"{args.symbol} {args.timeframe} Integrated Strategy Signals",
        )
    else:
        logger.warning("No signals generated during test period")


if __name__ == "__main__":
    main()
