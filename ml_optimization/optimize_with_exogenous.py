#!/usr/bin/env python3
"""
ML Model Optimization with Exogenous Data Integration

This script enhances the GBP/USD model by incorporating:
1. Economic indicators from FRED
2. Market sentiment analysis from news sources
3. Combining these exogenous features with technical indicators

Usage:
    python optimize_with_exogenous.py --symbol GBPUSD
        [--economic-only | --sentiment-only]
        [--quick]
        [--plot]
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add project root to path to import from fxml4
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

# Import ML hyperparameter optimization
from fxml2.packages.ml_hyperopt import (
    create_feature_target_splits,
    evaluate_classifier,
    optimize_hyperparameters,
    time_series_cv_split,
)

# Import FXML4 modules
from fxml4.ml.features import (
    add_lagged_features,
    calculate_weekly_pivot_points,
    create_target_labels,
    create_technical_features,
    identify_trading_sessions,
    scale_features,
    select_features_random_forest,
)
from fxml4.ml.models import ClassicMLModel

# Import custom economic and sentiment feature engineering
from ml_optimization.economic_sentiment_features import IntegratedFeatureEngineer


class MLModelWrapper:
    """Wrapper class for ClassicMLModel that provides a scikit-learn compatible interface"""

    def __init__(self, model_type, n_classes, params):
        """Initialize with model params"""
        self.model_type = model_type
        self.n_classes = n_classes
        self.params = params
        self.model = None

    def fit(self, X, y):
        """Train the model"""
        # Create a new model with a unique name
        self.model = ClassicMLModel(
            model_type=self.model_type,
            name=f"gbpusd_{self.model_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            n_classes=self.n_classes,
            model_params=self.params,
        )
        # Train the model
        self.model.train(X, y)
        return self

    def predict(self, X):
        """Make predictions"""
        return self.model.predict(X)

    def predict_proba(self, X):
        """Get prediction probabilities"""
        return self.model.predict_proba(X)


def rf_model_factory(params):
    """Factory function for Random Forest model"""
    return MLModelWrapper(
        model_type="random_forest",
        n_classes=3,  # -1, 0, 1 for down, neutral, up
        params=params,
    )


def xgb_model_factory(params):
    """Factory function for XGBoost model"""
    return MLModelWrapper(
        model_type="xgboost",
        n_classes=3,  # -1, 0, 1 for down, neutral, up
        params=params,
    )


def load_historical_data(symbol="GBPUSD", years=None, months=None, days=None):
    """
    Load historical data across multiple years/months/days.

    Args:
        symbol: Currency pair symbol
        years: List of years to load, if None uses 2020-2023
        months: List of months to load, if None uses all months
        days: List of days to load, if None loads all available days

    Returns:
        DataFrame of OHLC data
    """
    if years is None:
        years = [2020, 2021, 2022, 2023]

    if months is None:
        months = list(range(1, 13))  # All months

    data_frames = []

    for year in years:
        for month in months:
            try:
                base_path = f"input/C_{symbol}/year={year}/month={month}"

                # Check if path exists
                if not os.path.exists(base_path):
                    logger.warning(f"Path {base_path} does not exist, skipping")
                    continue

                # If days not specified, try to find all available days
                if days is None:
                    available_days = [
                        int(d.replace("day=", ""))
                        for d in os.listdir(base_path)
                        if d.startswith("day=")
                    ]
                    available_days.sort()
                else:
                    available_days = days

                # Try to load data for each day
                for day in available_days:
                    try:
                        path = f"{base_path}/day={day}/data.parquet"
                        if os.path.exists(path):
                            day_df = pd.read_parquet(path)
                            data_frames.append(day_df)
                            logger.debug(f"Loaded data from {path}")
                    except Exception as e:
                        logger.warning(
                            f"Couldn't load parquet data for {year}-{month:02d}-{day:02d}: {e}"
                        )
            except Exception as e:
                logger.warning(f"Error loading data for {year}-{month:02d}: {e}")

    # Combine all data frames
    if data_frames:
        df = pd.concat(data_frames)
        df = df.sort_index()

        # Remove duplicate timestamps
        if df.index.duplicated().any():
            logger.warning(
                f"Found {df.index.duplicated().sum()} duplicate timestamps, keeping first occurrences"
            )
            df = df[~df.index.duplicated(keep="first")]

        logger.info(f"Successfully loaded {len(df)} rows from {len(data_frames)} files")
        return df
    else:
        logger.error("No data loaded")
        return None


def prepare_features_with_exogenous(
    df, symbol, include_economic=True, include_sentiment=True, indicators=None
):
    """Prepare features for model training including exogenous data"""
    # Drop columns we don't need
    if "otc" in df.columns:
        df = df.drop(columns=["otc"])

    if "transactions" in df.columns:
        df = df.drop(columns=["transactions"])

    # 1. Create technical features with pandas_ta
    logger.info("Creating technical features")
    if indicators is None:
        indicators = ["sma", "ema", "rsi", "macd", "bollinger", "stoch", "atr", "adx"]

    df_features = create_technical_features(
        df, indicators=indicators, add_enhanced_features=True
    )

    # 2. Add pivot points (weekly)
    logger.info("Adding pivot points")
    df_features = calculate_weekly_pivot_points(df_features)

    # 3. Add trading session information
    logger.info("Adding trading session information")
    df_features = identify_trading_sessions(df_features)

    # 4. Add lagged features
    logger.info("Adding lagged features")
    df_features = add_lagged_features(df_features, lags=[1, 2, 3, 5, 10])

    # 5. Add exogenous features (economic and sentiment)
    logger.info("Adding exogenous features")

    # Initialize feature engineer
    feature_engineer = IntegratedFeatureEngineer(use_cache=True)

    # Determine date range
    if isinstance(df_features.index, pd.DatetimeIndex):
        start_date = df_features.index[0]
        end_date = df_features.index[-1]
    else:
        start_date = None
        end_date = None

    # Add integrated features
    df_features = feature_engineer.create_integrated_features(
        df_features,
        symbol,
        include_economic=include_economic,
        include_sentiment=include_sentiment,
        start_date=start_date,
        end_date=end_date,
    )

    # 6. Create target labels with volatility-adjusted method
    logger.info("Creating target labels")
    df_features = create_target_labels(
        df_features,
        method="volatility_adjusted",
        horizon=10,
        volatility_window=20,
        volatility_multiplier=1.0,
        trend_adjusted=True,
        trend_window=100,
    )

    # 7. Handle NaN values
    df_features = df_features.ffill().bfill()

    # For any remaining NaNs (especially in calculated columns), replace with column median
    for col in df_features.columns:
        if df_features[col].isna().any():
            median_val = df_features[col].median()
            if pd.isna(median_val):  # If median is also NaN (e.g., all values are NaN)
                df_features[col] = df_features[col].fillna(0)
            else:
                df_features[col] = df_features[col].fillna(median_val)

    # Drop any still problematic rows
    df_clean = df_features.dropna()
    logger.info(f"Final dataset shape after cleaning: {df_clean.shape}")

    return df_clean


def main():
    """Main optimization function with exogenous data integration"""
    parser = argparse.ArgumentParser(
        description="Optimize ML model with exogenous data"
    )
    parser.add_argument(
        "--symbol", type=str, default="GBPUSD", help="Symbol to analyze"
    )
    parser.add_argument(
        "--economic-only", action="store_true", help="Only use economic features"
    )
    parser.add_argument(
        "--sentiment-only", action="store_true", help="Only use sentiment features"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run a quick optimization with reduced data",
    )
    parser.add_argument(
        "--plot", action="store_true", help="Generate feature importance plots"
    )
    args = parser.parse_args()

    symbol = args.symbol

    logger.info(f"Starting {symbol} model optimization with exogenous data")

    # Determine which exogenous data to include
    include_economic = not args.sentiment_only
    include_sentiment = not args.economic_only

    if args.economic_only:
        logger.info("Using economic indicators only (no sentiment)")
    elif args.sentiment_only:
        logger.info("Using sentiment features only (no economic)")
    else:
        logger.info("Using both economic and sentiment features")

    # Create output directory for results
    output_dir = "ml_optimization/results"
    os.makedirs(output_dir, exist_ok=True)

    # 1. Load data - use different amount based on quick flag
    if args.quick:
        # For quick run, use just 2023 data from 3 months
        df = load_historical_data(
            symbol=symbol, years=[2023], months=[1, 2, 3]  # Just Q1 2023
        )
    else:
        # For full run, use multiple years for better generalization
        df = load_historical_data(
            symbol=symbol,
            years=[2021, 2022, 2023],
            months=[1, 2, 3, 4, 5, 6, 7, 8, 9],  # First 3 quarters
        )

    if df is None or len(df) == 0:
        logger.error("No data loaded, exiting")
        return

    # 2. Prepare features with exogenous data
    df_features = prepare_features_with_exogenous(
        df,
        symbol,
        include_economic=include_economic,
        include_sentiment=include_sentiment,
    )

    # 3. Define target and features
    target_col = "target_10"

    # Exclude non-feature columns (targets, future returns)
    exclude_cols = [
        c
        for c in df_features.columns
        if c.startswith("target_") or c.startswith("future_return_")
    ]
    feature_cols = [c for c in df_features.columns if c not in exclude_cols]

    logger.info(f"Total features: {len(feature_cols)}")
    logger.info(f"Target column: {target_col}")

    # 4. Scale features
    df_scaled, scaler = scale_features(df_features, exclude_cols=exclude_cols)

    # 5. Define parameter grid for optimization
    # Use smaller grid if quick mode is enabled
    if args.quick:
        rf_param_grid = {
            "n_estimators": [50, 100],
            "max_depth": [10, 15],
            "min_samples_split": [2, 5],
            "min_samples_leaf": [1, 2],
            "random_state": [42],  # Keep this fixed for reproducibility
        }
    else:
        rf_param_grid = {
            "n_estimators": [50, 100, 200, 300],
            "max_depth": [10, 15, 20, None],
            "min_samples_split": [2, 5, 10],
            "min_samples_leaf": [1, 2, 4],
            "random_state": [42],  # Keep this fixed for reproducibility
        }

    # 6. Run hyperparameter optimization using grid search
    logger.info("Running Random Forest hyperparameter optimization")
    # Adjust CV splits based on data size
    cv_splits = 3 if args.quick else 5

    rf_results = optimize_hyperparameters(
        df=df_scaled,
        feature_cols=feature_cols,
        target_col=target_col,
        model_factory=rf_model_factory,
        param_grid=rf_param_grid,
        cv_method="time_series",
        cv_params={"n_splits": cv_splits, "test_size": 0.2},
        optimize_method="grid",
        optimize_method_params={
            "max_combinations": 150
        },  # Ensure all 144 combinations are evaluated
        is_classifier=True,
        multi_class=True,  # 3-class problem (-1, 0, 1)
        eval_trading=True,  # Evaluate trading metrics
        metric="f1",  # Optimize for F1 score
        higher_is_better=True,
        output_dir=output_dir,
        verbose=True,
    )

    # 7. Train final model with best parameters
    logger.info("Training final model with optimized parameters")
    best_params = rf_results["best_params"]
    logger.info(f"Best parameters: {best_params}")

    # Split data into train/test
    train_size = int(0.8 * len(df_scaled))

    X_train = df_scaled.iloc[:train_size][feature_cols]
    y_train = df_scaled.iloc[:train_size][target_col]

    X_test = df_scaled.iloc[train_size:][feature_cols]
    y_test = df_scaled.iloc[train_size:][target_col]

    # Feature selection for better performance
    X_train_selected, selected_features = select_features_random_forest(
        X_train, y_train, k=30, plot=args.plot
    )

    # Use selected features for test set
    X_test_selected = X_test[selected_features]

    # Get future returns for financial metrics
    future_returns = df_scaled.iloc[train_size:][f"future_return_{10}"]

    # Train final model
    final_model = rf_model_factory(best_params)
    final_model.fit(X_train_selected, y_train)

    # 8. Evaluate final model
    # Use the underlying model's evaluate method since MLModelWrapper doesn't have it
    metrics = final_model.model.evaluate(
        X_test_selected, y_test, returns=future_returns, plot=args.plot
    )

    # 9. Print results
    print("\nFinal Model Evaluation Results:")
    print(f"Accuracy: {metrics['accuracy']:.4f}")
    print(f"Precision: {metrics['precision']:.4f}")
    print(f"Recall: {metrics['recall']:.4f}")
    print(f"F1 Score: {metrics['f1']:.4f}")

    if "profit_factor" in metrics:
        print(f"\nFinancial Metrics:")
        print(f"Profit Factor: {metrics['profit_factor']:.4f}")
        print(f"Win Rate: {metrics['win_rate']:.4f}")
        print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.4f}")
        print(f"Max Drawdown: {metrics['max_drawdown']:.4f}")

    # 10. Save the model
    model_file = f"{symbol}_exog_rf_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    saved_files = final_model.model.save(directory=output_dir, name=model_file)
    logger.info(f"Model saved to: {saved_files['model']}")

    # Save feature information
    feature_info = {
        "all_features": feature_cols,
        "selected_features": selected_features,
        "target": target_col,
        "exogenous_config": {
            "include_economic": include_economic,
            "include_sentiment": include_sentiment,
            "symbol": symbol,
        },
        "metrics": {
            "accuracy": float(metrics.get("accuracy", 0)),
            "precision": float(metrics.get("precision", 0)),
            "recall": float(metrics.get("recall", 0)),
            "f1": float(metrics.get("f1", 0)),
            "profit_factor": float(metrics.get("profit_factor", 0)),
            "win_rate": float(metrics.get("win_rate", 0)),
            "sharpe_ratio": float(metrics.get("sharpe_ratio", 0)),
            "max_drawdown": float(metrics.get("max_drawdown", 0)),
        },
    }

    with open(f"{output_dir}/{model_file}_features.json", "w") as f:
        json.dump(feature_info, f, indent=2)

    logger.info(f"Feature info saved to: {output_dir}/{model_file}_features.json")

    # 11. Compare feature importances with and without exogenous data
    if args.plot:
        try:
            # Get feature importances
            feature_importances = final_model.model.get_feature_importance()

            # Get indices of exogenous features
            economic_features = [
                f
                for f in selected_features
                if any(eco in f for eco in ["FEDFUNDS", "UNRATE", "CPI", "VIX", "T10Y"])
            ]
            sentiment_features = [f for f in selected_features if "sentiment" in f]

            # Plot feature importances
            plt.figure(figsize=(12, 10))

            # Plot all features
            plt.subplot(2, 1, 1)
            sorted_idx = feature_importances.argsort()
            plt.barh(range(len(sorted_idx)), feature_importances[sorted_idx])
            plt.yticks(
                range(len(sorted_idx)), [selected_features[i] for i in sorted_idx]
            )
            plt.xlabel("Feature Importance")
            plt.ylabel("Feature")
            plt.title(f"Feature Importance for {symbol} Model with Exogenous Data")

            # Plot just exogenous features
            plt.subplot(2, 1, 2)
            exog_features = economic_features + sentiment_features
            if exog_features:
                exog_importances = [
                    feature_importances[selected_features.index(f)]
                    for f in exog_features
                    if f in selected_features
                ]
                sorted_idx = np.argsort(exog_importances)
                plt.barh(
                    range(len(sorted_idx)), [exog_importances[i] for i in sorted_idx]
                )
                plt.yticks(
                    range(len(sorted_idx)), [exog_features[i] for i in sorted_idx]
                )
                plt.xlabel("Feature Importance")
                plt.ylabel("Exogenous Feature")
                plt.title("Importance of Economic and Sentiment Features")
            else:
                plt.text(
                    0.5,
                    0.5,
                    "No exogenous features selected",
                    horizontalalignment="center",
                    verticalalignment="center",
                )

            plt.tight_layout()
            plt.savefig(f"{output_dir}/{model_file}_feature_importance.png")
            logger.info(
                f"Feature importance plot saved to: {output_dir}/{model_file}_feature_importance.png"
            )

            # Show plots if running interactively
            plt.show()

        except Exception as e:
            logger.error(f"Error generating feature importance plots: {e}")

    logger.info("Optimization with exogenous data completed successfully")


if __name__ == "__main__":
    main()
