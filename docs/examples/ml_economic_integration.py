#!/usr/bin/env python3
"""
Example of integrating economic data with ML models.

This script demonstrates how to:
1. Load market data and economic indicators
2. Create features using both market and economic data
3. Train ML models with and without economic features
4. Compare performance of both approaches
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

# Add the parent directory to the path to allow importing fxml4
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from dotenv import load_dotenv

from fxml4.data_engineering.timescaledb import TimescaleDBClient
from fxml4.ml.economic_features import create_economic_features, detect_regime
from fxml4.ml.features import create_ml_features

# Load environment variables
load_dotenv()


# Connect to TimescaleDB
def get_db_client() -> TimescaleDBClient:
    """Get a TimescaleDB client."""
    host = os.environ.get("TIMESCALEDB_HOST", "localhost")
    port = int(os.environ.get("TIMESCALEDB_PORT", "5432"))
    dbname = os.environ.get("TIMESCALEDB_DATABASE", "fxml4")
    user = os.environ.get("TIMESCALEDB_USER", "postgres")
    password = os.environ.get("TIMESCALEDB_PASSWORD", "postgres")

    return TimescaleDBClient(
        host=host, port=port, dbname=dbname, user=user, password=password
    )


def load_market_data(
    symbol: str, timeframe: str, start_date: datetime, end_date: datetime
) -> pd.DataFrame:
    """
    Load market data from TimescaleDB.

    Args:
        symbol: Symbol to load data for
        timeframe: Timeframe to load (e.g., "1h", "4h", "1d")
        start_date: Start date for data
        end_date: End date for data

    Returns:
        DataFrame with market data
    """
    db_client = get_db_client()
    return db_client.get_ohlcv_data(
        symbol=symbol, timeframe=timeframe, start_time=start_date, end_time=end_date
    )


def load_economic_data(
    indicators: List[str],
    start_date: datetime,
    end_date: datetime,
    source: str = "fred",
) -> pd.DataFrame:
    """
    Load economic data from TimescaleDB.

    Args:
        indicators: List of indicator names to load
        start_date: Start date for data
        end_date: End date for data
        source: Data source (default: "fred")

    Returns:
        DataFrame with economic data (indicator values in columns)
    """
    db_client = get_db_client()

    # Connect to database
    with db_client.get_connection() as conn:
        cursor = conn.cursor()

        # Check if exogenous_data table exists
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'exogenous_data'
            );
        """
        )

        if not cursor.fetchone()[0]:
            raise ValueError("exogenous_data table does not exist in TimescaleDB")

        # Fetch data for all indicators
        placeholders = ", ".join(["%s"] * len(indicators))
        query = f"""
            SELECT time, indicator_name, value
            FROM exogenous_data
            WHERE source = %s
              AND indicator_name IN ({placeholders})
              AND time BETWEEN %s AND %s
            ORDER BY time, indicator_name;
        """

        cursor.execute(query, [source] + indicators + [start_date, end_date])
        data = cursor.fetchall()

        if not data:
            print(f"No economic data found for indicators {indicators}")
            return pd.DataFrame()

        # Process the data into a wide format DataFrame
        records = []
        for time, indicator, value in data:
            records.append({"time": time, "indicator": indicator, "value": value})

        # Create DataFrame
        df = pd.DataFrame(records)

        # Pivot to have indicators as columns
        pivoted = df.pivot(index="time", columns="indicator", values="value")

        # Make sure all requested indicators are included
        for indicator in indicators:
            if indicator not in pivoted.columns:
                pivoted[indicator] = np.nan

        return pivoted


def create_labels(
    data: pd.DataFrame, lookahead: int = 5, threshold: float = 0.0
) -> pd.Series:
    """
    Create classification labels based on future returns.

    Args:
        data: DataFrame with OHLC price data
        lookahead: Number of bars to look ahead
        threshold: Return threshold for classification

    Returns:
        Series with classification labels (1 for up, 0 for down)
    """
    # Calculate future return
    future_returns = data["close"].pct_change(lookahead).shift(-lookahead)

    # Create labels: 1 for positive return above threshold, 0 for negative return below threshold
    labels = (future_returns > threshold).astype(int)

    return labels


def train_test_split_by_time(
    data: pd.DataFrame, test_size: float = 0.2
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """
    Split data into training and testing sets based on time.

    Args:
        data: DataFrame with features and label column
        test_size: Fraction of data to use for testing

    Returns:
        X_train, X_test, y_train, y_test
    """
    # Determine split point
    split_idx = int(len(data) * (1 - test_size))

    # Split data
    train_data = data.iloc[:split_idx]
    test_data = data.iloc[split_idx:]

    # Extract features and labels
    X_train = train_data.drop("label", axis=1)
    y_train = train_data["label"]
    X_test = test_data.drop("label", axis=1)
    y_test = test_data["label"]

    return X_train, X_test, y_train, y_test


def evaluate_model(
    model, X_test: pd.DataFrame, y_test: pd.Series, model_name: str
) -> Dict:
    """
    Evaluate classification model and print results.

    Args:
        model: Trained classification model
        X_test: Test features
        y_test: Test labels
        model_name: Name of the model for reporting

    Returns:
        Dictionary with evaluation metrics
    """
    # Make predictions
    y_pred = model.predict(X_test)

    # Calculate metrics
    accuracy = accuracy_score(y_test, y_pred)
    conf_matrix = confusion_matrix(y_test, y_pred)
    class_report = classification_report(y_test, y_pred, output_dict=True)

    # Print results
    print(f"\n{model_name} Performance:")
    print(f"Accuracy: {accuracy:.4f}")
    print("\nConfusion Matrix:")
    print(conf_matrix)
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))

    # Calculate precision, recall, and F1 for the positive class (label 1)
    precision = class_report["1"]["precision"]
    recall = class_report["1"]["recall"]
    f1 = class_report["1"]["f1-score"]

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "confusion_matrix": conf_matrix,
        "classification_report": class_report,
    }


def plot_feature_importance(
    model, feature_names: List[str], model_name: str, top_n: int = 20
):
    """
    Plot feature importance from a trained model.

    Args:
        model: Trained model with feature_importances_ attribute
        feature_names: List of feature names
        model_name: Name of the model for plot title
        top_n: Number of top features to display
    """
    # Get feature importances
    importances = model.feature_importances_

    # Sort feature importances in descending order
    indices = np.argsort(importances)[::-1]

    # Take top N features
    top_indices = indices[:top_n]
    top_importances = importances[top_indices]
    top_features = [feature_names[i] for i in top_indices]

    # Plot
    plt.figure(figsize=(12, 8))
    plt.title(f"Top {top_n} Feature Importances - {model_name}")
    plt.bar(range(top_n), top_importances, align="center")
    plt.xticks(range(top_n), top_features, rotation=90)
    plt.tight_layout()
    plt.savefig(f"{model_name}_feature_importance.png")
    print(f"Saved feature importance chart to {model_name}_feature_importance.png")


def create_model_config(include_economic_data: bool = True) -> Dict:
    """
    Create model configuration with or without economic features.

    Args:
        include_economic_data: Whether to include economic features

    Returns:
        Configuration dictionary
    """
    config = {
        "features": {
            "technical_indicators": True,
            "price_patterns": True,
            "volume_analysis": True,
            "session_features": True,
            "wave_features": False,
            "economic_features": include_economic_data,
        }
    }
    return config


def main():
    # Load environment variables
    load_dotenv()

    # Define parameters
    symbol = "EURUSD"
    timeframe = "1d"
    start_date = datetime(2018, 1, 1)
    end_date = datetime(2023, 12, 31)

    # Load market data
    print(
        f"Loading market data for {symbol} ({timeframe}) from {start_date.date()} to {end_date.date()}..."
    )
    market_data = load_market_data(symbol, timeframe, start_date, end_date)

    if market_data.empty:
        print(
            "No market data found. Please make sure market data is loaded in TimescaleDB."
        )
        return 1

    print(f"Loaded {len(market_data)} bars of market data.")

    # Load economic indicators
    indicators = [
        "UNRATE",  # Unemployment Rate
        "CPIAUCSL",  # Consumer Price Index
        "GDP",  # Gross Domestic Product
        "FEDFUNDS",  # Federal Funds Rate
        "T10Y2Y",  # 10Y-2Y Treasury Spread (yield curve)
        "VIXCLS",  # VIX Volatility Index
        "INDPRO",  # Industrial Production
        "RSAFS",  # Retail Sales
        "HOUST",  # Housing Starts
        "UMCSENT",  # Consumer Sentiment
    ]

    print(f"Loading economic indicators: {', '.join(indicators)}...")
    economic_data = load_economic_data(indicators, start_date, end_date)

    if economic_data.empty:
        print(
            "No economic data found. Please run scripts/collect_economic_data.py to collect FRED data."
        )
        return 1

    print(f"Loaded economic data with shape: {economic_data.shape}")

    # Create labels (1 for price up, 0 for price down after 5 days)
    print("Creating classification labels...")
    market_data["label"] = create_labels(market_data, lookahead=5, threshold=0.0)

    # Create standard features (without economic data)
    print("Creating standard features...")
    config_without_econ = create_model_config(include_economic_data=False)
    standard_features = create_ml_features(market_data, config=config_without_econ)

    # Create features with economic data
    print("Creating features with economic data...")
    config_with_econ = create_model_config(include_economic_data=True)
    econ_features = create_ml_features(
        market_data, economic_data, config=config_with_econ
    )

    # Add labels to feature sets
    standard_features["label"] = market_data["label"]
    econ_features["label"] = market_data["label"]

    # Drop rows with NaN values
    standard_features = standard_features.dropna()
    econ_features = econ_features.dropna()

    # Train-test split
    print("Splitting data into training and testing sets...")
    X_train_std, X_test_std, y_train_std, y_test_std = train_test_split_by_time(
        standard_features
    )
    X_train_econ, X_test_econ, y_train_econ, y_test_econ = train_test_split_by_time(
        econ_features
    )

    # Train Random Forest models
    print("Training Random Forest model without economic features...")
    rf_std = RandomForestClassifier(
        n_estimators=100, max_depth=10, min_samples_split=10, random_state=42
    )
    rf_std.fit(X_train_std, y_train_std)

    print("Training Random Forest model with economic features...")
    rf_econ = RandomForestClassifier(
        n_estimators=100, max_depth=10, min_samples_split=10, random_state=42
    )
    rf_econ.fit(X_train_econ, y_train_econ)

    # Evaluate models
    std_metrics = evaluate_model(rf_std, X_test_std, y_test_std, "Standard Model")
    econ_metrics = evaluate_model(
        rf_econ, X_test_econ, y_test_econ, "Economic-Enhanced Model"
    )

    # Plot feature importances
    plot_feature_importance(rf_std, X_train_std.columns.tolist(), "Standard_Model")
    plot_feature_importance(
        rf_econ, X_train_econ.columns.tolist(), "Economic_Enhanced_Model"
    )

    # Compare models
    print("\nModel Comparison:")
    print(
        f"{'Metric':<20} {'Standard Model':<15} {'Economic Model':<15} {'Difference':<15}"
    )
    print("-" * 65)

    for metric in ["accuracy", "precision", "recall", "f1"]:
        std_val = std_metrics[metric]
        econ_val = econ_metrics[metric]
        diff = econ_val - std_val
        diff_pct = diff / std_val * 100 if std_val != 0 else float("inf")

        print(
            f"{metric:<20} {std_val:>12.4f} {econ_val:>14.4f} {diff:>+10.4f} ({diff_pct:>+.2f}%)"
        )

    # Visualize comparison
    plt.figure(figsize=(10, 6))
    metrics = ["accuracy", "precision", "recall", "f1"]
    x = np.arange(len(metrics))
    width = 0.35

    plt.bar(
        x - width / 2, [std_metrics[m] for m in metrics], width, label="Standard Model"
    )
    plt.bar(
        x + width / 2,
        [econ_metrics[m] for m in metrics],
        width,
        label="Economic-Enhanced Model",
    )

    plt.xlabel("Metrics")
    plt.ylabel("Score")
    plt.title("Model Performance Comparison")
    plt.xticks(x, metrics)
    plt.legend()
    plt.grid(axis="y", linestyle="--", alpha=0.7)

    plt.tight_layout()
    plt.savefig("model_comparison.png")
    print("Saved model comparison chart to model_comparison.png")

    return 0


if __name__ == "__main__":
    sys.exit(main())
