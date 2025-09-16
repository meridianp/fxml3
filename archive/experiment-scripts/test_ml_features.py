"""
Test script for ML features and model training with FXML2 indicators.

This script loads GBPUSD data, creates technical features using the enhanced
FXML2 indicators, trains a Random Forest model, and evaluates its performance.
"""

import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import FXML4 modules
from fxml4.ml.features import (
    create_technical_features, add_lagged_features,
    calculate_weekly_pivot_points, identify_trading_sessions,
    create_target_labels, scale_features, select_features_random_forest
)
from fxml4.ml.models import ClassicMLModel

def load_sample_data(symbol='GBPUSD', year=2020, month=7, days=None):
    """
    Load a sample of GBPUSD data for testing.
    
    Args:
        symbol: Currency pair symbol
        year: Year to load data from
        month: Month to load data from
        days: List of days to load, if None loads all available days for the month
        
    Returns:
        DataFrame of OHLC data
    """
    data_frames = []
    
    try:
        base_path = f"input/C_{symbol}/year={year}/month={month}"
        
        # If days not specified, try to find all available days
        if days is None:
            import os
            if os.path.exists(base_path):
                days = [int(d.replace("day=", "")) for d in os.listdir(base_path) 
                       if d.startswith("day=")]
                days.sort()
            else:
                days = list(range(1, 21))  # Default to first 20 days if can't read directory
                
        # Try to load data for each day
        for day in days:
            try:
                path = f"{base_path}/day={day}/data.parquet"
                day_df = pd.read_parquet(path)
                data_frames.append(day_df)
                logger.info(f"Loaded data from {path}")
            except Exception as e:
                logger.warning(f"Couldn't load parquet data for {day}: {e}")
        
        # Combine all data frames
        if data_frames:
            df = pd.concat(data_frames)
            df = df.sort_index()
            
            # Remove duplicate timestamps
            if df.index.duplicated().any():
                logger.warning(f"Found {df.index.duplicated().sum()} duplicate timestamps, keeping first occurrences")
                df = df[~df.index.duplicated(keep='first')]
            
            logger.info(f"Successfully loaded {len(df)} rows from {len(data_frames)} days")
            return df
    except Exception as e:
        logger.warning(f"Error loading data: {e}")
    
    # Create synthetic data if real data not available
    logger.info("Creating synthetic data for testing")
    n_samples = 5000
    np.random.seed(42)
    
    # Create datetime index starting from specified date
    start_date = pd.Timestamp(f"{year}-{month:02d}-01")
    index = pd.date_range(start=start_date, periods=n_samples, freq='1h')
    
    # Generate random price data with some trend and volatility
    close = 100 + np.cumsum(np.random.normal(0, 0.1, n_samples))
    high = close + np.random.normal(0, 0.5, n_samples).clip(0, None)
    low = close - np.random.normal(0, 0.5, n_samples).clip(0, None)
    open_prices = close.copy()
    np.random.shuffle(open_prices)
    
    # Create dataframe
    df = pd.DataFrame({
        'open': open_prices,
        'high': high,
        'low': low,
        'close': close,
        'volume': np.random.randint(1000, 10000, n_samples)
    }, index=index)
    
    logger.info(f"Created synthetic data with {len(df)} rows")
    
    return df

def main():
    """Main function to test ML features and model training."""
    logger.info("Starting ML features and model test")
    
    # Load data - using real data from 2020 July (multiple days for better modeling)
    df = load_sample_data(symbol='GBPUSD', year=2020, month=7, days=list(range(10, 31)))
    
    # Drop columns that might cause issues (otc appears to be None/NaN)
    if 'otc' in df.columns:
        df = df.drop(columns=['otc'])
    
    # Drop columns that are not needed for ML (transactions)
    if 'transactions' in df.columns:
        df = df.drop(columns=['transactions'])
    
    # 1. Create technical features with FXML2 indicators
    logger.info("Creating technical features")
    df_features = create_technical_features(
        df,
        indicators=["sma", "ema", "rsi", "macd", "bollinger", "stoch"],
        add_enhanced_features=True
    )
    
    # 2. Add pivot points (weekly)
    logger.info("Adding pivot points")
    df_features = calculate_weekly_pivot_points(df_features)
    
    # 3. Add trading session information
    logger.info("Adding trading session information")
    df_features = identify_trading_sessions(df_features)
    
    # 4. Add lagged features
    logger.info("Adding lagged features")
    df_features = add_lagged_features(df_features)
    
    # 5. Create target labels with FXML2's volatility-adjusted method
    logger.info("Creating target labels")
    df_features = create_target_labels(
        df_features, 
        method="volatility_adjusted",
        horizon=10,
        volatility_window=20,
        volatility_multiplier=1.0,
        trend_adjusted=True,
        trend_window=100
    )
    
    # 6. Handle NaN values - first fill NaN values with more sophisticated method
    # Forward fill first, then backward fill any remaining NaNs at the start
    df_features = df_features.ffill().bfill()  # Modern approach instead of deprecated fillna(method=)
    
    # For any remaining NaNs (especially in calculated columns), replace with column median
    for col in df_features.columns:
        if df_features[col].isna().any():
            median_val = df_features[col].median()
            if pd.isna(median_val):  # If median is also NaN (e.g., all values are NaN)
                df_features[col] = df_features[col].fillna(0)
            else:
                df_features[col] = df_features[col].fillna(median_val)
    
    # Finally, drop any still problematic rows
    df_clean = df_features.dropna()
    logger.info(f"Final dataset shape after cleaning: {df_clean.shape}")
    
    # Ensure we have data
    if len(df_clean) == 0:
        raise ValueError("No data available after cleaning. Please check the data source.")
    
    # Print available features
    print("Available features:")
    for i, col in enumerate(df_clean.columns):
        print(f"{i+1:3d}. {col}")
    
    # 7. Scale features
    target_col = "target_10"
    exclude_cols = [c for c in df_clean.columns if c.startswith("target_") or c.startswith("future_return_")]
    df_scaled, scaler = scale_features(df_clean, exclude_cols=exclude_cols)
    
    # 8. Split data
    train_size = int(0.7 * len(df_scaled))
    val_size = int(0.15 * len(df_scaled))
    
    X_train = df_scaled.iloc[:train_size].drop(columns=exclude_cols)
    y_train = df_scaled.iloc[:train_size][target_col]
    
    X_val = df_scaled.iloc[train_size:train_size+val_size].drop(columns=exclude_cols)
    y_val = df_scaled.iloc[train_size:train_size+val_size][target_col]
    
    X_test = df_scaled.iloc[train_size+val_size:].drop(columns=exclude_cols)
    y_test = df_scaled.iloc[train_size+val_size:][target_col]
    
    # 9. Feature selection
    logger.info("Selecting important features")
    X_train_selected, selected_features = select_features_random_forest(
        X_train, y_train, k=20, plot=False  # Disable plotting to avoid interruptions
    )
    
    # Use selected features for validation and test sets
    X_val_selected = X_val[selected_features]
    X_test_selected = X_test[selected_features]
    
    # 10. Train model
    logger.info("Training Random Forest model")
    model = ClassicMLModel(
        model_type="random_forest",
        name=f"gbpusd_random_forest_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        n_classes=3,
        model_params={
            "n_estimators": 100,
            "max_depth": 10,
            "min_samples_split": 5,
            "min_samples_leaf": 2,
            "random_state": 42
        }
    )
    
    model.train(X_train_selected, y_train)
    
    # 11. Evaluate model
    logger.info("Evaluating model")
    # Get future returns for financial metrics
    future_returns = df_scaled.iloc[train_size+val_size:][f"future_return_{10}"]
    
    metrics = model.evaluate(X_test_selected, y_test, returns=future_returns, plot=False)
    
    # 12. Print results
    print("\nModel Evaluation Results:")
    print(f"Accuracy: {metrics['accuracy']:.4f}")
    print(f"Precision: {metrics['precision']:.4f}")
    print(f"Recall: {metrics['recall']:.4f}")
    print(f"F1 Score: {metrics['f1']:.4f}")
    
    if 'profit_factor' in metrics:
        print(f"\nFinancial Metrics:")
        print(f"Profit Factor: {metrics['profit_factor']:.4f}")
        print(f"Win Rate: {metrics['win_rate']:.4f}")
        print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.4f}")
        print(f"Max Drawdown: {metrics['max_drawdown']:.4f}")
    
    # 13. Save the model
    saved_files = model.save()
    logger.info(f"Model saved to: {saved_files['model']}")
    logger.info("Test completed successfully")

if __name__ == "__main__":
    main()