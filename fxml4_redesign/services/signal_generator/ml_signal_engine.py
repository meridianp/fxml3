"""ML Signal Engine for generating machine learning based trading signals."""

import json
import logging
import os
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import xgboost as xgb

# ML libraries
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


class MLSignalEngine:
    """Machine Learning signal generation engine."""

    def __init__(self):
        """Initialize ML signal engine."""
        self.models: Dict[str, Any] = {}
        self.scalers: Dict[str, StandardScaler] = {}
        self.feature_columns = []
        self.models_path = Path("models/ml_signals")
        self.models_path.mkdir(parents=True, exist_ok=True)

        # Model configuration
        self.lookback_periods = [5, 10, 20, 50]
        self.confidence_threshold = 0.55
        self.retrain_interval_days = 7
        self.last_retrain_date = {}

        # Feature engineering parameters
        self.atr_multipliers = [0.5, 1.0, 2.0]
        self.ma_periods = [9, 20, 50, 200]

    async def load_models(self):
        """Load trained models from disk."""
        try:
            # Load ensemble models for each symbol
            for symbol in ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]:
                model_file = self.models_path / f"{symbol}_ensemble_model.pkl"
                scaler_file = self.models_path / f"{symbol}_scaler.pkl"

                if model_file.exists() and scaler_file.exists():
                    with open(model_file, "rb") as f:
                        self.models[symbol] = pickle.load(f)

                    with open(scaler_file, "rb") as f:
                        self.scalers[symbol] = pickle.load(f)

                    logger.info(f"Loaded model for {symbol}")
                else:
                    # Create default model
                    await self.create_default_model(symbol)

            # Load feature columns
            features_file = self.models_path / "feature_columns.json"
            if features_file.exists():
                with open(features_file, "r") as f:
                    self.feature_columns = json.load(f)
            else:
                self.feature_columns = self._get_default_features()

        except Exception as e:
            logger.error(f"Error loading models: {e}")
            # Fall back to default models
            await self.create_default_models()

    async def create_default_model(self, symbol: str):
        """Create a default model for a symbol."""
        try:
            # Create ensemble model
            rf_model = RandomForestClassifier(
                n_estimators=100, max_depth=10, min_samples_split=20, random_state=42
            )

            xgb_model = xgb.XGBClassifier(
                n_estimators=100, max_depth=6, learning_rate=0.1, random_state=42
            )

            ensemble = VotingClassifier(
                estimators=[("rf", rf_model), ("xgb", xgb_model)], voting="soft"
            )

            # Create dummy training data for initialization
            n_samples = 1000
            n_features = len(self._get_default_features())

            X_dummy = np.random.randn(n_samples, n_features)
            y_dummy = np.random.choice(
                [0, 1, 2], size=n_samples
            )  # 0=sell, 1=neutral, 2=buy

            # Fit models
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X_dummy)
            ensemble.fit(X_scaled, y_dummy)

            # Store models
            self.models[symbol] = ensemble
            self.scalers[symbol] = scaler

            logger.info(f"Created default model for {symbol}")

        except Exception as e:
            logger.error(f"Error creating default model for {symbol}: {e}")

    async def create_default_models(self):
        """Create default models for all symbols."""
        symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
        for symbol in symbols:
            await self.create_default_model(symbol)

    def _get_default_features(self) -> List[str]:
        """Get default feature column names."""
        features = []

        # Price features
        features.extend(["open", "high", "low", "close"])

        # Technical indicators
        features.extend(
            [
                "rsi_14",
                "atr_14",
                "sma_20",
                "sma_50",
                "sma_200",
                "ema_9",
                "ema_21",
                "bb_upper",
                "bb_middle",
                "bb_lower",
                "macd_line",
                "macd_signal",
                "macd_histogram",
                "adx",
                "plus_di",
                "minus_di",
                "stoch_k",
                "stoch_d",
            ]
        )

        # Engineered features
        for period in self.lookback_periods:
            features.extend(
                [
                    f"price_change_{period}",
                    f"volatility_{period}",
                    f"rsi_change_{period}",
                    f"volume_ma_{period}",
                ]
            )

        # Price relative to MA
        for ma_period in self.ma_periods:
            features.append(f"price_vs_ma_{ma_period}")

        return features

    async def generate_signals(
        self, symbol: str, data: pd.DataFrame
    ) -> List[Dict[str, Any]]:
        """Generate ML signals for a symbol.

        Args:
            symbol: Trading symbol
            data: OHLCV data with indicators

        Returns:
            List of ML signals
        """
        try:
            if symbol not in self.models:
                logger.warning(f"No model available for {symbol}")
                return []

            if len(data) < 200:
                logger.debug(f"Insufficient data for {symbol}: {len(data)} bars")
                return []

            # Engineer features
            features_df = self._engineer_features(data)

            if features_df.empty:
                logger.warning(f"No features generated for {symbol}")
                return []

            # Prepare latest features
            latest_features = self._prepare_features(features_df.iloc[-1:])

            if latest_features is None:
                return []

            # Generate prediction
            model = self.models[symbol]
            scaler = self.scalers[symbol]

            # Scale features
            X_scaled = scaler.transform(latest_features)

            # Get prediction and probabilities
            prediction = model.predict(X_scaled)[0]
            probabilities = model.predict_proba(X_scaled)[0]

            # Convert prediction to signal
            signals = []

            # Map prediction to direction (0=sell, 1=neutral, 2=buy)
            if prediction == 2:  # Buy signal
                direction = "BUY"
                confidence = probabilities[2]
            elif prediction == 0:  # Sell signal
                direction = "SELL"
                confidence = probabilities[0]
            else:  # Neutral
                direction = "NEUTRAL"
                confidence = probabilities[1]

            # Only generate signal if confidence is above threshold
            if confidence >= self.confidence_threshold and direction != "NEUTRAL":
                current_price = float(data["close"].iloc[-1])
                atr = (
                    float(data["atr_14"].iloc[-1])
                    if "atr_14" in data
                    else current_price * 0.001
                )

                # Calculate entry, stop loss, and targets
                if direction == "BUY":
                    entry_price = current_price
                    stop_loss = current_price - (atr * 2.0)
                    take_profit_1 = current_price + (atr * 2.0)
                    take_profit_2 = current_price + (atr * 3.0)
                    take_profit_3 = current_price + (atr * 4.0)
                else:  # SELL
                    entry_price = current_price
                    stop_loss = current_price + (atr * 2.0)
                    take_profit_1 = current_price - (atr * 2.0)
                    take_profit_2 = current_price - (atr * 3.0)
                    take_profit_3 = current_price - (atr * 4.0)

                # Create signal
                signal = {
                    "timestamp": data.index[-1],
                    "symbol": symbol,
                    "direction": direction,
                    "confidence": float(confidence),
                    "model_name": "ensemble_v1",
                    "model_version": "1.0",
                    "entry_price": entry_price,
                    "stop_loss": stop_loss,
                    "take_profit_1": take_profit_1,
                    "take_profit_2": take_profit_2,
                    "take_profit_3": take_profit_3,
                    "features": latest_features.iloc[0].to_dict(),
                    "probabilities": {
                        "sell": float(probabilities[0]),
                        "neutral": float(probabilities[1]),
                        "buy": float(probabilities[2]),
                    },
                    "metadata": {
                        "atr": float(atr),
                        "current_price": current_price,
                        "feature_count": len(latest_features.columns),
                        "data_points": len(data),
                    },
                }

                signals.append(signal)
                logger.info(
                    f"Generated ML signal for {symbol}: {direction} ({confidence:.3f})"
                )

            return signals

        except Exception as e:
            logger.error(f"Error generating ML signals for {symbol}: {e}")
            return []

    def _engineer_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Engineer features from raw data.

        Args:
            data: Raw OHLCV data with indicators

        Returns:
            DataFrame with engineered features
        """
        df = data.copy()

        try:
            # Price-based features
            df["price_change_1"] = df["close"].pct_change()

            # Lookback features
            for period in self.lookback_periods:
                if len(df) > period:
                    # Price changes
                    df[f"price_change_{period}"] = df["close"].pct_change(period)

                    # Volatility (rolling std)
                    df[f"volatility_{period}"] = df["close"].rolling(period).std()

                    # RSI changes
                    if "rsi_14" in df.columns:
                        df[f"rsi_change_{period}"] = df["rsi_14"].diff(period)

                    # Volume MA (if volume exists)
                    if "volume" in df.columns:
                        df[f"volume_ma_{period}"] = df["volume"].rolling(period).mean()
                    else:
                        df[f"volume_ma_{period}"] = 0

            # Price relative to moving averages
            for ma_period in self.ma_periods:
                ma_col = f"sma_{ma_period}"
                if ma_col in df.columns:
                    df[f"price_vs_ma_{ma_period}"] = (df["close"] - df[ma_col]) / df[
                        ma_col
                    ]
                else:
                    # Calculate if not available
                    if len(df) >= ma_period:
                        ma = df["close"].rolling(ma_period).mean()
                        df[f"price_vs_ma_{ma_period}"] = (df["close"] - ma) / ma
                    else:
                        df[f"price_vs_ma_{ma_period}"] = 0

            # Bollinger Band position
            if all(col in df.columns for col in ["bb_upper", "bb_lower", "bb_middle"]):
                df["bb_position"] = (df["close"] - df["bb_lower"]) / (
                    df["bb_upper"] - df["bb_lower"]
                )
            else:
                df["bb_position"] = 0.5

            # MACD features
            if all(col in df.columns for col in ["macd_line", "macd_signal"]):
                df["macd_signal_cross"] = np.where(
                    df["macd_line"] > df["macd_signal"], 1, -1
                )
                df["macd_signal_cross_change"] = df["macd_signal_cross"].diff()
            else:
                df["macd_signal_cross"] = 0
                df["macd_signal_cross_change"] = 0

            # ADX trend strength
            if "adx" in df.columns:
                df["trend_strength"] = np.where(
                    df["adx"] > 25,
                    1,  # Strong trend
                    np.where(df["adx"] > 20, 0.5, 0),  # Weak/no trend
                )
            else:
                df["trend_strength"] = 0.5

            # RSI overbought/oversold
            if "rsi_14" in df.columns:
                df["rsi_overbought"] = np.where(df["rsi_14"] > 70, 1, 0)
                df["rsi_oversold"] = np.where(df["rsi_14"] < 30, 1, 0)
            else:
                df["rsi_overbought"] = 0
                df["rsi_oversold"] = 0

            return df

        except Exception as e:
            logger.error(f"Error engineering features: {e}")
            return pd.DataFrame()

    def _prepare_features(self, features_df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """Prepare features for model prediction.

        Args:
            features_df: DataFrame with engineered features

        Returns:
            DataFrame with selected features ready for prediction
        """
        try:
            # Select feature columns that exist in the data
            available_features = [
                col for col in self.feature_columns if col in features_df.columns
            ]

            if not available_features:
                logger.warning("No feature columns available")
                return None

            # Select features
            X = features_df[available_features].copy()

            # Handle missing values
            X = X.fillna(method="ffill").fillna(0)

            # Ensure we have the right number of features
            missing_features = set(self.feature_columns) - set(available_features)
            for feature in missing_features:
                X[feature] = 0

            # Reorder columns to match training
            X = X[self.feature_columns]

            return X

        except Exception as e:
            logger.error(f"Error preparing features: {e}")
            return None

    async def save_models(self):
        """Save models to disk."""
        try:
            for symbol, model in self.models.items():
                model_file = self.models_path / f"{symbol}_ensemble_model.pkl"
                scaler_file = self.models_path / f"{symbol}_scaler.pkl"

                with open(model_file, "wb") as f:
                    pickle.dump(model, f)

                if symbol in self.scalers:
                    with open(scaler_file, "wb") as f:
                        pickle.dump(self.scalers[symbol], f)

            # Save feature columns
            features_file = self.models_path / "feature_columns.json"
            with open(features_file, "w") as f:
                json.dump(self.feature_columns, f)

            logger.info("Models saved successfully")

        except Exception as e:
            logger.error(f"Error saving models: {e}")

    async def check_retrain_schedule(self):
        """Check if models need retraining."""
        current_date = datetime.now().date()

        for symbol in self.models.keys():
            last_retrain = self.last_retrain_date.get(symbol)

            if (
                not last_retrain
                or (current_date - last_retrain).days >= self.retrain_interval_days
            ):

                logger.info(f"Scheduling retrain for {symbol}")
                # In a real implementation, this would trigger a retraining task
                # For now, just update the last retrain date
                self.last_retrain_date[symbol] = current_date

    def create_training_labels(
        self, data: pd.DataFrame, atr_multiplier: float = 1.0
    ) -> np.ndarray:
        """Create training labels based on future price movements.

        Args:
            data: OHLCV data
            atr_multiplier: ATR multiplier for significant moves

        Returns:
            Array of labels (0=sell, 1=neutral, 2=buy)
        """
        labels = np.full(len(data), 1)  # Default to neutral

        if "atr_14" not in data.columns:
            return labels

        for i in range(len(data) - 20):  # Look ahead 20 periods
            current_price = data["close"].iloc[i]
            atr = data["atr_14"].iloc[i]

            if pd.isna(atr) or atr == 0:
                continue

            # Look at future prices (next 5-20 periods)
            future_prices = data["close"].iloc[i + 1 : i + 21]

            if len(future_prices) == 0:
                continue

            # Calculate max profit/loss in both directions
            max_profit_long = (future_prices.max() - current_price) / (
                atr * atr_multiplier
            )
            max_loss_long = (current_price - future_prices.min()) / (
                atr * atr_multiplier
            )

            # Determine label based on significant moves
            if max_profit_long >= 2.0 and max_profit_long > max_loss_long:
                labels[i] = 2  # Buy signal
            elif max_loss_long >= 2.0 and max_loss_long > max_profit_long:
                labels[i] = 0  # Sell signal
            # else remains neutral (1)

        return labels
