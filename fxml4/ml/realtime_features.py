"""
Real-time Feature Generator for ML Models.

This module provides classes and utilities for generating features in real-time
from streaming market data for input into machine learning models.
"""

import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from fxml4.data_engineering.live_data_handler import LiveDataHandler
from fxml4.data_engineering.timeframe_conversion import TimeframeConverter
from fxml4.ml.features import (
    add_pivot_points,
    add_session_features,
    calculate_technical_features,
)

# Configure logging
logger = logging.getLogger(__name__)


class RealtimeFeatureGenerator:
    """
    Generates features in real-time from streaming market data.

    This class subscribes to real-time market data, processes it, and generates
    features for machine learning models in a streaming fashion.
    """

    def __init__(
        self,
        live_data_handler: LiveDataHandler,
        feature_config: Dict[str, Any],
        model_metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the RealtimeFeatureGenerator.

        Args:
            live_data_handler: LiveDataHandler instance for market data
            feature_config: Configuration for feature generation, including:
                symbol: Symbol to generate features for
                timeframe: Timeframe to generate features for
                feature_list: List of features to generate
                lookback: Number of periods to include for each feature
                prediction_horizon: Future prediction horizon in candles
                include_pivots: Whether to include pivot points
                include_sessions: Whether to include session features
                include_exogenous: Whether to include exogenous data
            model_metadata: Optional metadata from a trained model, including:
                feature_list: List of features used by the model
                scaler: Fitted sklearn scaler for feature normalization
                feature_importance: Feature importance scores
        """
        self.live_data_handler = live_data_handler
        self.config = feature_config
        self.model_metadata = model_metadata

        # Extract configuration
        self.symbol = feature_config.get("symbol", "GBPUSD")
        self.timeframe = feature_config.get("timeframe", "1h")
        self.feature_list = feature_config.get("feature_list", [])
        self.lookback = feature_config.get("lookback", 30)  # Default 30 periods
        self.prediction_horizon = feature_config.get(
            "prediction_horizon", 12
        )  # Default 12 periods

        # Feature inclusion flags
        self.include_pivots = feature_config.get("include_pivots", False)
        self.include_sessions = feature_config.get("include_sessions", False)
        self.include_exogenous = feature_config.get("include_exogenous", False)

        # Feature callbacks
        self.feature_callbacks = []

        # Data storage
        self.raw_data = {}  # Raw market data by symbol
        self.feature_data = {}  # Generated features by symbol

        # Scaling
        self.scaler = None
        if model_metadata and "scaler" in model_metadata:
            self.scaler = model_metadata["scaler"]

        # Model-specific feature list
        self.model_feature_list = None
        if model_metadata and "feature_list" in model_metadata:
            self.model_feature_list = model_metadata["feature_list"]

        # Last feature generation time
        self.last_feature_time = {}

        # Threading
        self.feature_lock = threading.Lock()

        logger.info(
            f"Initialized RealtimeFeatureGenerator for {self.symbol} on {self.timeframe} timeframe"
        )

        # Register for data updates
        self._register_data_callbacks()

    def _register_data_callbacks(self):
        """Register callbacks with the LiveDataHandler for data updates."""
        if not self.live_data_handler:
            logger.error("No LiveDataHandler provided, cannot register callbacks")
            return

        # Subscribe to the symbol if not already subscribed
        self.live_data_handler.subscribe_symbol(self.symbol)

        # Register for candle updates
        self.live_data_handler.register_candle_callback(
            self.symbol, self.timeframe, self._on_candle_update
        )

        # If using pivot points, we need daily data
        if self.include_pivots:
            self.live_data_handler.register_candle_callback(
                self.symbol, "1d", self._on_daily_candle_update
            )

        logger.info(f"Registered data callbacks for {self.symbol} on {self.timeframe}")

    def _on_candle_update(self, symbol: str, timeframe: str, candles: pd.DataFrame):
        """
        Callback handler for candle updates.

        Args:
            symbol: Symbol
            timeframe: Timeframe
            candles: Candle data as DataFrame
        """
        if symbol != self.symbol or timeframe != self.timeframe:
            return

        # Store the raw data
        with self.feature_lock:
            self.raw_data[symbol] = candles.copy()

        # Generate features
        self._generate_features(symbol)

    def _on_daily_candle_update(
        self, symbol: str, timeframe: str, candles: pd.DataFrame
    ):
        """
        Callback handler for daily candle updates (for pivot points).

        Args:
            symbol: Symbol
            timeframe: Timeframe
            candles: Candle data as DataFrame
        """
        if symbol != self.symbol or timeframe != "1d":
            return

        # Store the daily data
        with self.feature_lock:
            self.raw_data[f"{symbol}_daily"] = candles.copy()

    def _generate_features(self, symbol: str):
        """
        Generate features for the specified symbol.

        Args:
            symbol: Symbol to generate features for
        """
        # Get the current time
        now = datetime.now(timezone.utc)

        # Check if we recently generated features
        if symbol in self.last_feature_time:
            # Don't generate features more often than every 15 seconds
            if (now - self.last_feature_time[symbol]).total_seconds() < 15:
                return

        # Update last feature generation time
        self.last_feature_time[symbol] = now

        try:
            # Get raw market data
            with self.feature_lock:
                if symbol not in self.raw_data or self.raw_data[symbol].empty:
                    logger.warning(
                        f"No raw data available for {symbol}, skipping feature generation"
                    )
                    return

                # Make a copy to avoid modifying the original
                data = self.raw_data[symbol].copy()

            # Ensure we have enough data
            if len(data) < self.lookback:
                logger.warning(
                    f"Not enough data for {symbol}: {len(data)} < {self.lookback}, skipping feature generation"
                )
                return

            # Calculate technical features
            feature_df = calculate_technical_features(
                data, feature_list=self.feature_list, lookback=self.lookback
            )

            # Add pivot points if requested
            if self.include_pivots and f"{symbol}_daily" in self.raw_data:
                daily_data = self.raw_data[f"{symbol}_daily"].copy()
                if not daily_data.empty:
                    feature_df = add_pivot_points(feature_df, daily_data)

            # Add session features if requested
            if self.include_sessions:
                feature_df = add_session_features(feature_df)

            # Add exogenous data if requested
            if self.include_exogenous:
                feature_df = self._add_exogenous_data(feature_df, symbol)

            # Handle NaN values
            feature_df.fillna(0, inplace=True)

            # Check if we have model-specific feature list
            if self.model_feature_list:
                # Filter features to match model requirements
                missing_features = set(self.model_feature_list) - set(
                    feature_df.columns
                )
                if missing_features:
                    logger.warning(f"Missing features for {symbol}: {missing_features}")

                    # Add missing features with zeros
                    for feature in missing_features:
                        feature_df[feature] = 0

                # Reorder columns to match model expectations
                available_features = [
                    col for col in self.model_feature_list if col in feature_df.columns
                ]
                feature_df = feature_df[available_features]

            # Apply scaling if a scaler is available
            if self.scaler:
                # Scale numerical features
                try:
                    feature_values = feature_df.values

                    # Handle case where feature matrix needs reshaping
                    if len(feature_values.shape) == 1:
                        feature_values = feature_values.reshape(1, -1)

                    scaled_values = self.scaler.transform(feature_values)
                    feature_df = pd.DataFrame(
                        scaled_values,
                        index=feature_df.index,
                        columns=feature_df.columns,
                    )
                except Exception as e:
                    logger.error(f"Error scaling features for {symbol}: {e}")

            # Store the feature data
            with self.feature_lock:
                self.feature_data[symbol] = feature_df.copy()

            # Notify callbacks
            self._notify_feature_callbacks(symbol)

            logger.debug(
                f"Generated {len(feature_df.columns)} features for {symbol} at {now}"
            )

        except Exception as e:
            logger.error(f"Error generating features for {symbol}: {e}")

    def _add_exogenous_data(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """
        Add exogenous data to the feature DataFrame.

        Args:
            df: Feature DataFrame
            symbol: Symbol

        Returns:
            DataFrame with exogenous features added
        """
        try:
            # This is placeholder for adding economic indicators, sentiment, etc.
            # In a real implementation, you would fetch this data from your exogenous data source
            # For now, we'll just log a message
            logger.warning(f"Adding exogenous data is not implemented yet")
            return df
        except Exception as e:
            logger.error(f"Error adding exogenous data: {e}")
            return df

    def get_latest_features(self, symbol: str = None) -> pd.DataFrame:
        """
        Get the latest generated features.

        Args:
            symbol: Symbol to get features for (defaults to self.symbol)

        Returns:
            DataFrame with the latest features
        """
        symbol = symbol or self.symbol

        with self.feature_lock:
            if symbol not in self.feature_data or self.feature_data[symbol].empty:
                logger.warning(f"No feature data available for {symbol}")
                return pd.DataFrame()

            # Return the latest row
            return self.feature_data[symbol].iloc[[-1]].copy()

    def get_features_history(
        self, symbol: str = None, n_periods: int = 10
    ) -> pd.DataFrame:
        """
        Get historical generated features.

        Args:
            symbol: Symbol to get features for (defaults to self.symbol)
            n_periods: Number of periods to return

        Returns:
            DataFrame with historical features
        """
        symbol = symbol or self.symbol

        with self.feature_lock:
            if symbol not in self.feature_data or self.feature_data[symbol].empty:
                logger.warning(f"No feature data available for {symbol}")
                return pd.DataFrame()

            # Return the last n_periods rows
            return self.feature_data[symbol].iloc[-n_periods:].copy()

    def register_feature_callback(self, callback: Callable[[str, pd.DataFrame], None]):
        """
        Register a callback for feature updates.

        Args:
            callback: Function to call with (symbol, feature_df) when features are updated
        """
        if callback not in self.feature_callbacks:
            self.feature_callbacks.append(callback)

    def unregister_feature_callback(
        self, callback: Callable[[str, pd.DataFrame], None]
    ):
        """
        Unregister a feature callback.

        Args:
            callback: Function to unregister
        """
        if callback in self.feature_callbacks:
            self.feature_callbacks.remove(callback)

    def _notify_feature_callbacks(self, symbol: str):
        """
        Notify callbacks of feature updates.

        Args:
            symbol: Symbol for which features were updated
        """
        if not self.feature_callbacks:
            return

        with self.feature_lock:
            if symbol not in self.feature_data or self.feature_data[symbol].empty:
                return

            # Get the latest features
            feature_df = self.feature_data[symbol].copy()

        # Call each callback
        for callback in self.feature_callbacks:
            try:
                callback(symbol, feature_df)
            except Exception as e:
                logger.error(f"Error in feature callback: {e}")

    def stop(self):
        """Stop the feature generator and clean up resources."""
        # Unregister callbacks from live data handler
        if self.live_data_handler:
            try:
                self.live_data_handler.unregister_candle_callback(
                    self.symbol, self.timeframe, self._on_candle_update
                )

                if self.include_pivots:
                    self.live_data_handler.unregister_candle_callback(
                        self.symbol, "1d", self._on_daily_candle_update
                    )

                logger.info(f"Unregistered data callbacks for {self.symbol}")
            except Exception as e:
                logger.error(f"Error unregistering callbacks: {e}")


class StreamingPredictor:
    """
    Makes predictions from streaming feature data.

    This class consumes real-time features and applies a machine learning model
    to make predictions on streaming data.
    """

    def __init__(
        self,
        model,
        feature_generator: RealtimeFeatureGenerator,
        prediction_config: Dict[str, Any],
    ):
        """
        Initialize the StreamingPredictor.

        Args:
            model: Trained model (sklearn, xgboost, etc.)
            feature_generator: RealtimeFeatureGenerator instance
            prediction_config: Configuration for predictions, including:
                symbol: Symbol to predict for
                confidence_threshold: Threshold for prediction confidence
                cooldown_periods: Number of periods to wait between predictions
        """
        self.model = model
        self.feature_generator = feature_generator
        self.config = prediction_config

        # Extract configuration
        self.symbol = prediction_config.get("symbol", feature_generator.symbol)
        self.confidence_threshold = prediction_config.get("confidence_threshold", 0.6)
        self.cooldown_periods = prediction_config.get("cooldown_periods", 3)

        # Prediction storage
        self.predictions = pd.DataFrame()

        # Cooldown tracking
        self.last_prediction_time = None
        self.periods_since_last_prediction = 0

        # Prediction callbacks
        self.prediction_callbacks = []

        # Threading
        self.prediction_lock = threading.Lock()

        logger.info(f"Initialized StreamingPredictor for {self.symbol}")

        # Register for feature updates
        self._register_feature_callbacks()

    def _register_feature_callbacks(self):
        """Register callbacks with the RealtimeFeatureGenerator for feature updates."""
        if not self.feature_generator:
            logger.error(
                "No RealtimeFeatureGenerator provided, cannot register callbacks"
            )
            return

        # Register for feature updates
        self.feature_generator.register_feature_callback(self._on_feature_update)

        logger.info(f"Registered feature callback for {self.symbol}")

    def _on_feature_update(self, symbol: str, feature_df: pd.DataFrame):
        """
        Callback handler for feature updates.

        Args:
            symbol: Symbol
            feature_df: Feature data as DataFrame
        """
        if symbol != self.symbol:
            return

        # Generate prediction
        self._generate_prediction(feature_df)

    def _generate_prediction(self, feature_df: pd.DataFrame):
        """
        Generate a prediction from feature data.

        Args:
            feature_df: Feature data as DataFrame
        """
        # Get the current time
        now = datetime.now(timezone.utc)

        # Check cooldown
        if self.last_prediction_time:
            # If we have a specific cooldown in periods
            if self.periods_since_last_prediction < self.cooldown_periods:
                self.periods_since_last_prediction += 1
                return

        try:
            # Get the latest features (last row)
            latest_features = feature_df.iloc[[-1]]

            # Apply model
            prediction_probas = self.model.predict_proba(latest_features)
            prediction_class = self.model.predict(latest_features)[0]

            # Get the probability for the predicted class
            # Assuming binary classification with classes [0, 1]
            # Adjust for multi-class as needed
            confidence = prediction_probas[0][prediction_class]

            # Store the prediction
            prediction = {
                "timestamp": latest_features.index[0],
                "symbol": self.symbol,
                "class": prediction_class,
                "confidence": confidence,
                "features": latest_features,
            }

            with self.prediction_lock:
                # Add to predictions
                new_row = pd.DataFrame(
                    [
                        {
                            "timestamp": prediction["timestamp"],
                            "symbol": prediction["symbol"],
                            "class": prediction["class"],
                            "confidence": prediction["confidence"],
                        }
                    ]
                )

                # Add the new prediction to the beginning
                self.predictions = pd.concat([new_row, self.predictions])

                # Limit to the last 100 predictions
                if len(self.predictions) > 100:
                    self.predictions = self.predictions.iloc[:100]

            # Reset cooldown
            self.last_prediction_time = now
            self.periods_since_last_prediction = 0

            # Only notify if confidence exceeds threshold
            if confidence >= self.confidence_threshold:
                self._notify_prediction_callbacks(prediction)

            logger.debug(
                f"Generated prediction for {self.symbol}: class={prediction_class}, confidence={confidence:.2f}"
            )

        except Exception as e:
            logger.error(f"Error generating prediction: {e}")

    def get_latest_prediction(self) -> Dict[str, Any]:
        """
        Get the latest prediction.

        Returns:
            Dictionary with the latest prediction
        """
        with self.prediction_lock:
            if self.predictions.empty:
                return {}

            latest = self.predictions.iloc[0]
            return {
                "timestamp": latest["timestamp"],
                "symbol": latest["symbol"],
                "class": latest["class"],
                "confidence": latest["confidence"],
            }

    def get_prediction_history(self, n_predictions: int = 10) -> pd.DataFrame:
        """
        Get historical predictions.

        Args:
            n_predictions: Number of predictions to return

        Returns:
            DataFrame with historical predictions
        """
        with self.prediction_lock:
            return self.predictions.head(n_predictions).copy()

    def register_prediction_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """
        Register a callback for prediction updates.

        Args:
            callback: Function to call with prediction dict when predictions are generated
        """
        if callback not in self.prediction_callbacks:
            self.prediction_callbacks.append(callback)

    def unregister_prediction_callback(
        self, callback: Callable[[Dict[str, Any]], None]
    ):
        """
        Unregister a prediction callback.

        Args:
            callback: Function to unregister
        """
        if callback in self.prediction_callbacks:
            self.prediction_callbacks.remove(callback)

    def _notify_prediction_callbacks(self, prediction: Dict[str, Any]):
        """
        Notify callbacks of prediction updates.

        Args:
            prediction: Prediction dictionary
        """
        if not self.prediction_callbacks:
            return

        # Call each callback
        for callback in self.prediction_callbacks:
            try:
                callback(prediction)
            except Exception as e:
                logger.error(f"Error in prediction callback: {e}")

    def stop(self):
        """Stop the predictor and clean up resources."""
        # Unregister callbacks from feature generator
        if self.feature_generator:
            try:
                self.feature_generator.unregister_feature_callback(
                    self._on_feature_update
                )
                logger.info(f"Unregistered feature callback for {self.symbol}")
            except Exception as e:
                logger.error(f"Error unregistering callback: {e}")
