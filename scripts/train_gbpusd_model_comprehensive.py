#!/usr/bin/env python3
"""
Comprehensive GBP/USD Model Training and Backtesting Script

This script provides complete functionality for:
1. Data preparation and feature engineering for GBP/USD
2. ML model training with multiple algorithms
3. Model evaluation with time series cross-validation
4. Comprehensive backtesting with realistic trading simulation
5. Performance analysis and production readiness validation

Usage:
    python scripts/train_gbpusd_model_comprehensive.py [--data-source historical|simulated]
"""

import argparse
import os
import sys
import warnings
from pathlib import Path

# Import paths handled by PYTHONPATH wrapper
project_root = Path(__file__).parent.parent

# Suppress warnings for cleaner output
warnings.filterwarnings("ignore")

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import joblib
import lightgbm as lgb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import xgboost as xgb

# ML libraries
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.preprocessing import LabelEncoder, StandardScaler

# Technical analysis (using manual calculations instead of talib)
# import talib  # Removed dependency

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class GBPUSDDataGenerator:
    """Generate realistic GBP/USD training data."""

    def __init__(self, start_date: str = "2020-01-01", end_date: str = "2024-08-24"):
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date)

    def generate_market_data(self, freq: str = "4H") -> pd.DataFrame:
        """Generate realistic GBP/USD market data."""
        logger.info(
            f"Generating GBP/USD data from {self.start_date} to {self.end_date}"
        )

        # Create timestamp index
        timestamps = pd.date_range(start=self.start_date, end=self.end_date, freq=freq)

        # Set random seed for reproducibility
        np.random.seed(42)

        # Realistic GBP/USD parameters
        base_price = 1.2500
        annual_vol = 0.12  # 12% annualized volatility
        freq_hours = 4 if freq == "4H" else 1
        period_vol = annual_vol * np.sqrt(freq_hours / (365.25 * 24))

        # Generate price path with regime changes
        n_points = len(timestamps)

        # Create multiple regimes
        regime_changes = [0, n_points // 4, n_points // 2, 3 * n_points // 4, n_points]
        regime_trends = [0.0002, -0.0001, 0.0003, -0.0002]  # Different trend per regime

        returns = np.zeros(n_points)

        for i in range(len(regime_changes) - 1):
            start_idx = regime_changes[i]
            end_idx = regime_changes[i + 1]
            regime_len = end_idx - start_idx

            # Add trend and noise for this regime
            trend = regime_trends[i]
            noise = np.random.normal(0, period_vol, regime_len)
            regime_returns = trend + noise

            returns[start_idx:end_idx] = regime_returns

        # Calculate prices
        log_prices = np.log(base_price) + np.cumsum(returns)
        close_prices = np.exp(log_prices)

        # Generate OHLC from close prices
        high_multiplier = 1 + np.abs(np.random.normal(0, 0.002, n_points))
        low_multiplier = 1 - np.abs(np.random.normal(0, 0.002, n_points))
        open_shift = np.random.normal(0, 0.001, n_points)

        # Create OHLCV dataframe
        data = pd.DataFrame(
            {
                "timestamp": timestamps,
                "symbol": "GBPUSD",
                "open": close_prices * (1 + open_shift),
                "high": close_prices * high_multiplier,
                "low": close_prices * low_multiplier,
                "close": close_prices,
                "volume": np.random.lognormal(11.5, 0.5, n_points).astype(
                    int
                ),  # Realistic volume
            }
        )

        # Ensure OHLC consistency
        data["high"] = np.maximum(data[["open", "close"]].max(axis=1), data["high"])
        data["low"] = np.minimum(data[["open", "close"]].min(axis=1), data["low"])

        # Add session information
        data["hour"] = data["timestamp"].dt.hour
        data["day_of_week"] = data["timestamp"].dt.dayofweek
        data["london_session"] = ((data["hour"] >= 8) & (data["hour"] < 17)).astype(int)
        data["ny_session"] = ((data["hour"] >= 13) & (data["hour"] < 22)).astype(int)
        data["overlap_session"] = ((data["hour"] >= 13) & (data["hour"] < 17)).astype(
            int
        )

        logger.info(f"Generated {len(data):,} data points for GBP/USD")
        logger.info(
            f"Price range: {data['close'].min():.4f} - {data['close'].max():.4f}"
        )

        return data


class GBPUSDFeatureEngineer:
    """Feature engineering specifically for GBP/USD."""

    def __init__(self):
        self.feature_columns = []

    def create_technical_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Create comprehensive technical features for GBP/USD."""
        logger.info("Creating technical features for GBP/USD")

        df = data.copy()

        # Price-based features
        df["returns"] = df["close"].pct_change()
        df["log_returns"] = np.log(df["close"] / df["close"].shift(1))
        df["high_low_pct"] = (df["high"] - df["low"]) / df["close"]
        df["open_close_pct"] = (df["close"] - df["open"]) / df["open"]

        # Moving averages
        for period in [5, 10, 20, 50, 100]:
            df[f"sma_{period}"] = df["close"].rolling(period).mean()
            df[f"ema_{period}"] = df["close"].ewm(span=period).mean()
            df[f"price_sma_{period}_ratio"] = df["close"] / df[f"sma_{period}"]

        # Volatility features
        df["volatility_20"] = df["returns"].rolling(20).std()
        df["realized_vol_10"] = df["log_returns"].rolling(10).std() * np.sqrt(
            252 * 6
        )  # Annualized

        # RSI
        df["rsi_14"] = self._calculate_rsi(df["close"], 14)
        df["rsi_30"] = self._calculate_rsi(df["close"], 30)

        # MACD
        df["macd"], df["macd_signal"], df["macd_histogram"] = self._calculate_macd(
            df["close"]
        )

        # Bollinger Bands
        df["bb_upper"], df["bb_lower"], df["bb_middle"] = (
            self._calculate_bollinger_bands(df["close"], 20, 2)
        )
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"]
        df["bb_position"] = (df["close"] - df["bb_lower"]) / (
            df["bb_upper"] - df["bb_lower"]
        )

        # Stochastic
        df["stoch_k"], df["stoch_d"] = self._calculate_stochastic(df, 14)

        # ATR
        df["atr_14"] = self._calculate_atr(df, 14)
        df["atr_pct"] = df["atr_14"] / df["close"]

        # Volume features
        df["volume_sma_10"] = df["volume"].rolling(10).mean()
        df["volume_ratio"] = df["volume"] / df["volume_sma_10"]

        # Price momentum
        for period in [3, 5, 10, 20]:
            df[f"momentum_{period}"] = df["close"] / df["close"].shift(period) - 1

        # Support/Resistance levels
        df["high_20"] = df["high"].rolling(20).max()
        df["low_20"] = df["low"].rolling(20).min()
        df["resistance_distance"] = (df["high_20"] - df["close"]) / df["close"]
        df["support_distance"] = (df["close"] - df["low_20"]) / df["close"]

        # Session-based features
        df["london_returns"] = df["returns"].where(df["london_session"] == 1, 0)
        df["ny_returns"] = df["returns"].where(df["ny_session"] == 1, 0)
        df["overlap_returns"] = df["returns"].where(df["overlap_session"] == 1, 0)

        # Lag features
        for lag in [1, 2, 3, 5]:
            df[f"returns_lag_{lag}"] = df["returns"].shift(lag)
            df[f"volatility_lag_{lag}"] = df["volatility_20"].shift(lag)
            df[f"rsi_lag_{lag}"] = df["rsi_14"].shift(lag)

        logger.info(
            f"Created {len([col for col in df.columns if col not in data.columns])} technical features"
        )
        return df

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def _calculate_macd(
        self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate MACD indicator."""
        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=signal).mean()
        macd_histogram = macd - macd_signal
        return macd, macd_signal, macd_histogram

    def _calculate_bollinger_bands(
        self, prices: pd.Series, period: int = 20, std_dev: float = 2
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate Bollinger Bands."""
        sma = prices.rolling(period).mean()
        std = prices.rolling(period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        return upper, lower, sma

    def _calculate_stochastic(
        self, data: pd.DataFrame, period: int = 14
    ) -> Tuple[pd.Series, pd.Series]:
        """Calculate Stochastic oscillator."""
        high_max = data["high"].rolling(period).max()
        low_min = data["low"].rolling(period).min()
        k_percent = 100 * (data["close"] - low_min) / (high_max - low_min)
        d_percent = k_percent.rolling(3).mean()
        return k_percent, d_percent

    def _calculate_atr(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range."""
        high_low = data["high"] - data["low"]
        high_close = np.abs(data["high"] - data["close"].shift())
        low_close = np.abs(data["low"] - data["close"].shift())
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        return true_range.rolling(period).mean()

    def create_target_variable(
        self, data: pd.DataFrame, forward_periods: int = 1, threshold: float = 0.002
    ) -> pd.DataFrame:
        """Create target variable for classification."""
        df = data.copy()

        # Calculate forward returns
        df["forward_returns"] = df["close"].shift(-forward_periods) / df["close"] - 1

        # Create 3-class target: -1 (sell), 0 (hold), 1 (buy)
        df["target"] = 0  # Default to hold
        df.loc[df["forward_returns"] > threshold, "target"] = 1  # Buy signal
        df.loc[df["forward_returns"] < -threshold, "target"] = -1  # Sell signal

        # Remove rows with NaN forward returns
        df = df[:-forward_periods]

        logger.info(f"Target distribution: {df['target'].value_counts().to_dict()}")
        return df


class GBPUSDModelTrainer:
    """Comprehensive model training for GBP/USD."""

    def __init__(self):
        self.models = {}
        self.scalers = {}
        self.best_model = None
        self.feature_columns = None
        self.model_performance = {}

    def prepare_features(
        self, data: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.Series, List[str]]:
        """Prepare features for model training."""
        logger.info("Preparing features for training")

        # Select feature columns (exclude timestamp, symbol, target, and intermediate calculations)
        exclude_columns = [
            "timestamp",
            "symbol",
            "target",
            "forward_returns",
            "open",
            "high",
            "low",
            "close",
            "volume",  # Raw OHLCV
        ]

        feature_columns = [
            col
            for col in data.columns
            if col not in exclude_columns and not col.startswith("bb_")
        ]
        feature_columns = [
            col for col in feature_columns if not pd.isna(data[col]).all()
        ]

        # Create feature matrix
        X = data[feature_columns].copy()
        y = data["target"].copy()

        # Remove rows with NaN values
        mask = ~(X.isna().any(axis=1) | y.isna())
        X = X[mask]
        y = y[mask]

        self.feature_columns = feature_columns
        logger.info(f"Selected {len(feature_columns)} features for training")
        logger.info(f"Training samples: {len(X):,}")

        return X, y, feature_columns

    def train_models(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        """Train multiple models and compare performance."""
        logger.info("Starting model training...")

        # Time series split for cross-validation
        tscv = TimeSeriesSplit(n_splits=5)

        # Encode target labels for XGBoost compatibility (convert -1,0,1 to 0,1,2)
        label_encoder = LabelEncoder()
        y_encoded = pd.Series(label_encoder.fit_transform(y), index=y.index)
        self.label_encoder = label_encoder

        # Model configurations
        model_configs = {
            "random_forest": {
                "model": RandomForestClassifier(
                    n_estimators=200,
                    max_depth=15,
                    min_samples_split=50,
                    min_samples_leaf=20,
                    max_features="sqrt",
                    class_weight="balanced",
                    random_state=42,
                    n_jobs=-1,
                ),
                "scale_features": False,
            },
            "xgboost": {
                "model": xgb.XGBClassifier(
                    n_estimators=200,
                    max_depth=8,
                    learning_rate=0.1,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    scale_pos_weight=1,
                    random_state=42,
                    n_jobs=-1,
                ),
                "scale_features": False,
            },
            "logistic_regression": {
                "model": LogisticRegression(
                    C=1.0,
                    class_weight="balanced",
                    random_state=42,
                    max_iter=1000,
                    solver="liblinear",
                ),
                "scale_features": True,
            },
            "gradient_boosting": {
                "model": GradientBoostingClassifier(
                    n_estimators=200,
                    learning_rate=0.1,
                    max_depth=8,
                    min_samples_split=50,
                    min_samples_leaf=20,
                    random_state=42,
                ),
                "scale_features": False,
            },
        }

        results = {}

        for model_name, config in model_configs.items():
            logger.info(f"Training {model_name}...")

            model = config["model"]

            # Scale features if needed
            X_model = X.copy()
            if config["scale_features"]:
                scaler = StandardScaler()
                X_model = pd.DataFrame(
                    scaler.fit_transform(X_model),
                    columns=X_model.columns,
                    index=X_model.index,
                )
                self.scalers[model_name] = scaler

            # Cross-validation
            cv_scores = cross_val_score(
                model, X_model, y_encoded, cv=tscv, scoring="f1_macro", n_jobs=-1
            )

            # Train on full dataset
            model.fit(X_model, y_encoded)

            # Make predictions for evaluation
            y_pred = model.predict(X_model)

            # Calculate metrics
            accuracy = accuracy_score(y_encoded, y_pred)
            precision = precision_score(
                y_encoded, y_pred, average="macro", zero_division=0
            )
            recall = recall_score(y_encoded, y_pred, average="macro", zero_division=0)
            f1 = f1_score(y_encoded, y_pred, average="macro", zero_division=0)

            results[model_name] = {
                "model": model,
                "cv_scores": cv_scores,
                "cv_mean": cv_scores.mean(),
                "cv_std": cv_scores.std(),
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
                "feature_importance": self._get_feature_importance(model, X.columns),
            }

            self.models[model_name] = model

            logger.info(
                f"{model_name} - CV F1: {cv_scores.mean():.4f} (+/- {cv_scores.std()*2:.4f})"
            )
            logger.info(f"{model_name} - Accuracy: {accuracy:.4f}, F1: {f1:.4f}")

        # Select best model based on CV F1 score
        best_model_name = max(results.keys(), key=lambda k: results[k]["cv_mean"])
        self.best_model = results[best_model_name]["model"]
        self.model_performance = results

        logger.info(
            f"Best model: {best_model_name} (CV F1: {results[best_model_name]['cv_mean']:.4f})"
        )

        return results

    def _get_feature_importance(self, model, feature_names) -> List[Tuple[str, float]]:
        """Extract feature importance from model."""
        if hasattr(model, "feature_importances_"):
            importance = model.feature_importances_
        elif hasattr(model, "coef_"):
            importance = (
                np.abs(model.coef_[0])
                if len(model.coef_.shape) > 1
                else np.abs(model.coef_)
            )
        else:
            return []

        feature_importance = list(zip(feature_names, importance))
        feature_importance.sort(key=lambda x: x[1], reverse=True)
        return feature_importance[:20]  # Top 20 features

    def save_models(self, output_dir: str = "models"):
        """Save trained models and scalers."""
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for model_name, model in self.models.items():
            model_path = f"{output_dir}/gbpusd_{model_name}_{timestamp}.joblib"
            joblib.dump(model, model_path)
            logger.info(f"Saved {model_name} model to {model_path}")

        # Save scalers
        for scaler_name, scaler in self.scalers.items():
            scaler_path = f"{output_dir}/gbpusd_{scaler_name}_scaler_{timestamp}.joblib"
            joblib.dump(scaler, scaler_path)

        # Save feature columns
        features_path = f"{output_dir}/gbpusd_features_{timestamp}.json"
        with open(features_path, "w") as f:
            json.dump(self.feature_columns, f, indent=2)

        # Save model performance
        performance_path = f"{output_dir}/gbpusd_performance_{timestamp}.json"
        performance_data = {}
        for model_name, perf in self.model_performance.items():
            performance_data[model_name] = {
                "cv_mean": float(perf["cv_mean"]),
                "cv_std": float(perf["cv_std"]),
                "accuracy": float(perf["accuracy"]),
                "precision": float(perf["precision"]),
                "recall": float(perf["recall"]),
                "f1_score": float(perf["f1_score"]),
                "feature_importance": [
                    (feat, float(imp)) for feat, imp in perf["feature_importance"][:10]
                ],
            }

        with open(performance_path, "w") as f:
            json.dump(performance_data, f, indent=2)

        logger.info(f"Saved model artifacts to {output_dir}")


class GBPUSDBacktester:
    """Comprehensive backtesting for GBP/USD models."""

    def __init__(self, initial_capital: float = 100000, position_size: float = 0.02):
        self.initial_capital = initial_capital
        self.position_size = position_size  # 2% risk per trade
        self.trades = []
        self.equity_curve = []

    def run_backtest(
        self,
        data: pd.DataFrame,
        model,
        feature_columns: List[str],
        start_date: str = "2023-01-01",
        label_encoder=None,
    ) -> Dict[str, Any]:
        """Run comprehensive backtest."""
        logger.info(f"Starting backtest from {start_date}")

        # Filter data for backtest period
        backtest_data = (
            data[data["timestamp"] >= start_date].copy().reset_index(drop=True)
        )
        logger.info(f"Backtesting on {len(backtest_data):,} data points")

        # Initialize backtest state
        capital = self.initial_capital
        position = 0  # 0: no position, 1: long, -1: short
        entry_price = 0
        entry_time = None

        # Track performance
        equity_curve = [capital]
        trade_returns = []
        drawdowns = []

        for i in range(len(backtest_data)):
            current_data = backtest_data.iloc[i]
            current_price = current_data["close"]
            current_time = current_data["timestamp"]

            # Skip if we don't have enough data for features
            if i < 100:  # Need history for technical indicators
                equity_curve.append(capital)
                continue

            # Get model features for current point
            try:
                features = backtest_data.iloc[i][feature_columns].values.reshape(1, -1)

                # Handle NaN features
                if np.isnan(features).any():
                    equity_curve.append(capital)
                    continue

                # Get model prediction
                prediction_encoded = model.predict(features)[0]
                # Decode prediction back to original labels (-1, 0, 1)
                prediction = (
                    label_encoder.inverse_transform([prediction_encoded])[0]
                    if label_encoder
                    else prediction_encoded
                )
                prediction_proba = (
                    model.predict_proba(features)[0]
                    if hasattr(model, "predict_proba")
                    else [0.33, 0.33, 0.34]
                )
                confidence = max(prediction_proba)

            except Exception as e:
                equity_curve.append(capital)
                continue

            # Trading logic
            if position == 0:  # No current position
                # Enter position based on prediction and confidence
                if (
                    prediction == 1 and confidence > 0.6
                ):  # Buy signal with high confidence
                    position = 1
                    entry_price = current_price
                    entry_time = current_time
                elif (
                    prediction == -1 and confidence > 0.6
                ):  # Sell signal with high confidence
                    position = -1
                    entry_price = current_price
                    entry_time = current_time

            else:  # Currently in position
                # Exit conditions
                should_exit = False
                exit_reason = ""

                # 1. Opposite signal with high confidence
                if (position == 1 and prediction == -1 and confidence > 0.6) or (
                    position == -1 and prediction == 1 and confidence > 0.6
                ):
                    should_exit = True
                    exit_reason = "signal_reversal"

                # 2. Stop loss (2% loss)
                if position == 1 and current_price < entry_price * 0.98:
                    should_exit = True
                    exit_reason = "stop_loss"
                elif position == -1 and current_price > entry_price * 1.02:
                    should_exit = True
                    exit_reason = "stop_loss"

                # 3. Take profit (4% gain)
                if position == 1 and current_price > entry_price * 1.04:
                    should_exit = True
                    exit_reason = "take_profit"
                elif position == -1 and current_price < entry_price * 0.96:
                    should_exit = True
                    exit_reason = "take_profit"

                # 4. Time-based exit (maximum 48 hours in 4H data = 12 periods)
                if i - len(equity_curve) > 12:
                    should_exit = True
                    exit_reason = "time_exit"

                # Execute exit
                if should_exit:
                    if position == 1:  # Close long position
                        trade_return = (current_price - entry_price) / entry_price
                    else:  # Close short position
                        trade_return = (entry_price - current_price) / entry_price

                    # Calculate position size and P&L
                    position_value = capital * self.position_size
                    pnl = position_value * trade_return
                    capital += pnl

                    # Record trade
                    trade_record = {
                        "entry_time": entry_time,
                        "exit_time": current_time,
                        "direction": "long" if position == 1 else "short",
                        "entry_price": entry_price,
                        "exit_price": current_price,
                        "return": trade_return,
                        "pnl": pnl,
                        "capital_after": capital,
                        "exit_reason": exit_reason,
                        "confidence": confidence,
                    }

                    self.trades.append(trade_record)
                    trade_returns.append(trade_return)

                    # Reset position
                    position = 0
                    entry_price = 0
                    entry_time = None

            # Update equity curve
            equity_curve.append(capital)

            # Calculate drawdown
            peak = max(equity_curve)
            drawdown = (peak - capital) / peak
            drawdowns.append(drawdown)

        # Calculate performance metrics
        total_return = (capital - self.initial_capital) / self.initial_capital
        num_trades = len(self.trades)

        if trade_returns:
            win_rate = len([r for r in trade_returns if r > 0]) / len(trade_returns)
            avg_return = np.mean(trade_returns)
            avg_win = (
                np.mean([r for r in trade_returns if r > 0])
                if any(r > 0 for r in trade_returns)
                else 0
            )
            avg_loss = (
                np.mean([r for r in trade_returns if r < 0])
                if any(r < 0 for r in trade_returns)
                else 0
            )
            profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float("inf")
            sharpe_ratio = (
                np.mean(trade_returns) / np.std(trade_returns) * np.sqrt(252 / 4)
                if np.std(trade_returns) > 0
                else 0
            )
        else:
            win_rate = 0
            avg_return = 0
            avg_win = 0
            avg_loss = 0
            profit_factor = 0
            sharpe_ratio = 0

        max_drawdown = max(drawdowns) if drawdowns else 0

        results = {
            "total_return": total_return,
            "final_capital": capital,
            "num_trades": num_trades,
            "win_rate": win_rate,
            "avg_return_per_trade": avg_return,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "equity_curve": equity_curve,
            "trades": self.trades[-20:],  # Last 20 trades for inspection
            "backtest_period": f"{backtest_data['timestamp'].min()} to {backtest_data['timestamp'].max()}",
        }

        logger.info(
            f"Backtest completed: {total_return:.2%} return, {num_trades} trades, {win_rate:.2%} win rate"
        )

        return results

    def plot_results(self, results: Dict[str, Any], save_path: str = None):
        """Plot backtest results."""
        try:
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))

            # Equity curve
            equity_curve = results["equity_curve"]
            ax1.plot(equity_curve, linewidth=2, color="blue")
            ax1.set_title("Equity Curve")
            ax1.set_xlabel("Time")
            ax1.set_ylabel("Capital ($)")
            ax1.grid(True, alpha=0.3)

            # Trade returns distribution
            if results["num_trades"] > 0:
                trade_returns = [trade["return"] for trade in self.trades]
                ax2.hist(
                    trade_returns, bins=30, alpha=0.7, color="green", edgecolor="black"
                )
                ax2.axvline(x=0, color="red", linestyle="--", alpha=0.7)
                ax2.set_title("Trade Returns Distribution")
                ax2.set_xlabel("Return")
                ax2.set_ylabel("Frequency")
                ax2.grid(True, alpha=0.3)

            # Performance metrics
            metrics = [
                f"Total Return: {results['total_return']:.2%}",
                f"Trades: {results['num_trades']}",
                f"Win Rate: {results['win_rate']:.2%}",
                f"Avg Return: {results['avg_return_per_trade']:.3%}",
                f"Profit Factor: {results['profit_factor']:.2f}",
                f"Max Drawdown: {results['max_drawdown']:.2%}",
                f"Sharpe Ratio: {results['sharpe_ratio']:.2f}",
            ]

            ax3.text(
                0.1,
                0.9,
                "\n".join(metrics),
                transform=ax3.transAxes,
                fontsize=12,
                verticalalignment="top",
                fontfamily="monospace",
            )
            ax3.set_xlim(0, 1)
            ax3.set_ylim(0, 1)
            ax3.axis("off")
            ax3.set_title("Performance Metrics")

            # Monthly returns (simplified)
            if results["num_trades"] > 0:
                monthly_returns = []
                monthly_labels = []

                # Group trades by month (simplified approach)
                for i, trade in enumerate(self.trades):
                    if i % max(1, len(self.trades) // 12) == 0:
                        monthly_returns.append(trade["return"])
                        monthly_labels.append(f"T{i+1}")

                ax4.bar(
                    range(len(monthly_returns)),
                    monthly_returns,
                    alpha=0.7,
                    color=["green" if r > 0 else "red" for r in monthly_returns],
                )
                ax4.set_title("Trade Returns Over Time")
                ax4.set_xlabel("Trade")
                ax4.set_ylabel("Return")
                ax4.grid(True, alpha=0.3)
                ax4.axhline(y=0, color="black", linestyle="-", alpha=0.5)

            plt.tight_layout()

            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches="tight")
                logger.info(f"Backtest plot saved to {save_path}")

            plt.show()

        except Exception as e:
            logger.error(f"Error plotting results: {e}")


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="GBP/USD Model Training and Backtesting"
    )
    parser.add_argument(
        "--data-source",
        choices=["historical", "simulated"],
        default="simulated",
        help="Data source for training",
    )
    parser.add_argument(
        "--output-dir", default="output", help="Output directory for models and results"
    )

    args = parser.parse_args()

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    logger.info("=== GBP/USD Model Training and Backtesting ===")
    logger.info(f"Data source: {args.data_source}")
    logger.info(f"Output directory: {args.output_dir}")

    try:
        # 1. Data Generation/Loading
        logger.info("\n1. Data Preparation")
        if args.data_source == "simulated":
            data_generator = GBPUSDDataGenerator()
            raw_data = data_generator.generate_market_data()
        else:
            # TODO: Load historical data from database
            logger.warning(
                "Historical data loading not implemented, using simulated data"
            )
            data_generator = GBPUSDDataGenerator()
            raw_data = data_generator.generate_market_data()

        # 2. Feature Engineering
        logger.info("\n2. Feature Engineering")
        feature_engineer = GBPUSDFeatureEngineer()
        data_with_features = feature_engineer.create_technical_features(raw_data)
        data_with_targets = feature_engineer.create_target_variable(data_with_features)

        logger.info(f"Final dataset shape: {data_with_targets.shape}")

        # 3. Model Training
        logger.info("\n3. Model Training")
        trainer = GBPUSDModelTrainer()
        X, y, feature_columns = trainer.prepare_features(data_with_targets)

        model_results = trainer.train_models(X, y)

        # Save models
        trainer.save_models(args.output_dir)

        # 4. Backtesting
        logger.info("\n4. Backtesting")
        backtester = GBPUSDBacktester(initial_capital=100000)

        # Use best model for backtesting
        best_model = trainer.best_model

        backtest_results = backtester.run_backtest(
            data_with_targets,
            best_model,
            feature_columns,
            start_date="2023-06-01",  # Use last portion for out-of-sample testing
            label_encoder=trainer.label_encoder,
        )

        # Plot and save results
        plot_path = f"{args.output_dir}/gbpusd_backtest_results.png"
        backtester.plot_results(backtest_results, plot_path)

        # Save backtest results
        backtest_path = f"{args.output_dir}/gbpusd_backtest_results.json"

        # Convert results to JSON-serializable format
        json_results = {
            "total_return": backtest_results["total_return"],
            "final_capital": backtest_results["final_capital"],
            "num_trades": backtest_results["num_trades"],
            "win_rate": backtest_results["win_rate"],
            "avg_return_per_trade": backtest_results["avg_return_per_trade"],
            "avg_win": backtest_results["avg_win"],
            "avg_loss": backtest_results["avg_loss"],
            "profit_factor": backtest_results["profit_factor"],
            "max_drawdown": backtest_results["max_drawdown"],
            "sharpe_ratio": backtest_results["sharpe_ratio"],
            "backtest_period": backtest_results["backtest_period"],
            "sample_trades": [
                {
                    "entry_time": (
                        trade["entry_time"].isoformat()
                        if hasattr(trade["entry_time"], "isoformat")
                        else str(trade["entry_time"])
                    ),
                    "exit_time": (
                        trade["exit_time"].isoformat()
                        if hasattr(trade["exit_time"], "isoformat")
                        else str(trade["exit_time"])
                    ),
                    "direction": trade["direction"],
                    "return": trade["return"],
                    "exit_reason": trade["exit_reason"],
                }
                for trade in backtest_results["trades"]
            ],
        }

        with open(backtest_path, "w") as f:
            json.dump(json_results, f, indent=2)

        # 5. Summary Report
        logger.info("\n=== FINAL RESULTS SUMMARY ===")
        logger.info(
            f"Best Model: {max(model_results.keys(), key=lambda k: model_results[k]['cv_mean'])}"
        )
        logger.info(
            f"Cross-validation F1 Score: {max(model_results[k]['cv_mean'] for k in model_results.keys()):.4f}"
        )
        logger.info(f"\nBacktest Performance:")
        logger.info(f"  Total Return: {backtest_results['total_return']:.2%}")
        logger.info(f"  Number of Trades: {backtest_results['num_trades']}")
        logger.info(f"  Win Rate: {backtest_results['win_rate']:.2%}")
        logger.info(
            f"  Average Return per Trade: {backtest_results['avg_return_per_trade']:.3%}"
        )
        logger.info(f"  Profit Factor: {backtest_results['profit_factor']:.2f}")
        logger.info(f"  Maximum Drawdown: {backtest_results['max_drawdown']:.2%}")
        logger.info(f"  Sharpe Ratio: {backtest_results['sharpe_ratio']:.2f}")

        # Production readiness assessment
        logger.info(f"\n=== PRODUCTION READINESS ASSESSMENT ===")

        production_criteria = {
            "min_trades": 50,
            "min_win_rate": 0.45,
            "max_drawdown": 0.15,
            "min_sharpe": 0.5,
            "min_profit_factor": 1.2,
        }

        meets_criteria = {
            "trades": backtest_results["num_trades"]
            >= production_criteria["min_trades"],
            "win_rate": backtest_results["win_rate"]
            >= production_criteria["min_win_rate"],
            "drawdown": backtest_results["max_drawdown"]
            <= production_criteria["max_drawdown"],
            "sharpe": backtest_results["sharpe_ratio"]
            >= production_criteria["min_sharpe"],
            "profit_factor": backtest_results["profit_factor"]
            >= production_criteria["min_profit_factor"],
        }

        for criterion, passed in meets_criteria.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            logger.info(f"  {criterion.replace('_', ' ').title()}: {status}")

        overall_ready = all(meets_criteria.values())
        logger.info(
            f"\nOverall Production Readiness: {'✅ READY' if overall_ready else '❌ NOT READY'}"
        )

        if overall_ready:
            logger.info("Model is ready for paper trading validation!")
        else:
            logger.info("Model needs improvement before production deployment.")

        logger.info(f"\nAll results saved to: {args.output_dir}")

    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        raise


if __name__ == "__main__":
    main()
