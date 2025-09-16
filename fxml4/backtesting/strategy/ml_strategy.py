"""
ML Strategy Bridge for Backtesting

This module provides integration between ML models and the backtesting framework.
"""

from abc import abstractmethod
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd

from ..events import EventType, SignalEvent
from ..portfolio import Portfolio
from ..strategy import Signal, Strategy


class MLStrategy(Strategy):
    """
    Base class for ML-based trading strategies.

    This bridges ML model predictions with the backtesting framework.
    """

    def __init__(
        self,
        model: Any,
        feature_columns: List[str],
        prediction_threshold: float = 0.5,
        position_size: float = 1000,
        risk_manager: Optional[Any] = None,
        signal_filters: Optional[List[Any]] = None,
    ):
        """
        Initialize ML Strategy.

        Args:
            model: Trained ML model with predict/predict_proba methods
            feature_columns: List of feature column names
            prediction_threshold: Threshold for generating signals
            position_size: Base position size
            risk_manager: Optional risk management component
            signal_filters: Optional list of signal filters
        """
        super().__init__()
        self.model = model
        self.feature_columns = feature_columns
        self.prediction_threshold = prediction_threshold
        self.position_size = position_size
        self.risk_manager = risk_manager
        self.signal_filters = signal_filters or []

    def calculate_signals(
        self, data: pd.DataFrame, portfolio: Portfolio
    ) -> List[SignalEvent]:
        """
        Calculate trading signals from ML model predictions.

        Args:
            data: Market data
            portfolio: Current portfolio state

        Returns:
            List of SignalEvent objects
        """
        # Prepare features
        features = self._prepare_features(data)

        # Get model predictions
        predictions = self._get_predictions(features)

        # Generate raw signals
        raw_signals = self._generate_signals(predictions, data, portfolio)

        # Apply filters
        filtered_signals = self._apply_filters(raw_signals, data, portfolio)

        # Apply risk management
        if self.risk_manager:
            filtered_signals = self._apply_risk_management(filtered_signals, portfolio)

        return filtered_signals

    def _prepare_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Prepare features for ML model."""
        # Get the latest row
        latest = data.iloc[-1]

        # Extract features
        features = {}
        for col in self.feature_columns:
            if col in latest.index:
                features[col] = latest[col]
            else:
                # Try to calculate the feature
                features[col] = self._calculate_feature(col, data)

        return pd.DataFrame([features])

    def _calculate_feature(self, feature_name: str, data: pd.DataFrame) -> float:
        """Calculate a feature if not directly available."""
        # Common technical indicators
        if feature_name == "rsi":
            return self._calculate_rsi(data["close"])
        elif feature_name == "sma_20":
            return data["close"].rolling(20).mean().iloc[-1]
        elif feature_name == "ema_50":
            return data["close"].ewm(span=50).mean().iloc[-1]
        elif feature_name == "atr":
            return self._calculate_atr(data)
        else:
            return np.nan

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate RSI."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs)).iloc[-1]

    def _calculate_atr(self, data: pd.DataFrame, period: int = 14) -> float:
        """Calculate ATR."""
        high_low = data["high"] - data["low"]
        high_close = abs(data["high"] - data["close"].shift())
        low_close = abs(data["low"] - data["close"].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        return true_range.rolling(period).mean().iloc[-1]

    @abstractmethod
    def _get_predictions(self, features: pd.DataFrame) -> Union[np.ndarray, pd.Series]:
        """
        Get predictions from ML model.

        Must be implemented by subclasses.
        """
        pass

    def _generate_signals(
        self,
        predictions: Union[np.ndarray, pd.Series],
        data: pd.DataFrame,
        portfolio: Portfolio,
    ) -> List[SignalEvent]:
        """Generate signals from predictions."""
        signals = []

        # Get current price
        current_price = data["close"].iloc[-1]
        timestamp = data.index[-1]

        # Determine signal type based on prediction
        if isinstance(predictions, np.ndarray):
            prediction = predictions[0]
        else:
            prediction = predictions.iloc[0]

        # Generate signal based on threshold
        if prediction > self.prediction_threshold:
            # Buy signal
            signal = SignalEvent(
                timestamp=timestamp,
                symbol=data.attrs.get("symbol", "EURUSD"),
                signal_type="BUY",
                strength=float(prediction),
                price=current_price,
                quantity=self.position_size,
                metadata={
                    "model_prediction": float(prediction),
                    "features": features.to_dict(),
                },
            )
            signals.append(signal)
        elif prediction < (1 - self.prediction_threshold):
            # Sell signal
            signal = SignalEvent(
                timestamp=timestamp,
                symbol=data.attrs.get("symbol", "EURUSD"),
                signal_type="SELL",
                strength=float(1 - prediction),
                price=current_price,
                quantity=self.position_size,
                metadata={
                    "model_prediction": float(prediction),
                    "features": features.to_dict(),
                },
            )
            signals.append(signal)

        return signals

    def _apply_filters(
        self, signals: List[SignalEvent], data: pd.DataFrame, portfolio: Portfolio
    ) -> List[SignalEvent]:
        """Apply signal filters."""
        filtered_signals = signals

        for filter_func in self.signal_filters:
            filtered_signals = filter_func(filtered_signals, data, portfolio)

        return filtered_signals

    def _apply_risk_management(
        self, signals: List[SignalEvent], portfolio: Portfolio
    ) -> List[SignalEvent]:
        """Apply risk management rules."""
        # Let risk manager adjust signals
        return self.risk_manager.adjust_signals(signals, portfolio)


class ClassificationMLStrategy(MLStrategy):
    """ML Strategy for classification models (buy/sell/hold)."""

    def _get_predictions(self, features: pd.DataFrame) -> np.ndarray:
        """Get predictions from classification model."""
        # Get class probabilities
        if hasattr(self.model, "predict_proba"):
            # Assuming classes are [sell, hold, buy] or [0, 1, 2]
            probas = self.model.predict_proba(features)
            # Return buy probability
            return probas[:, -1]  # Last class is typically 'buy'
        else:
            # Direct prediction
            predictions = self.model.predict(features)
            # Convert to probability-like values
            return (predictions + 1) / 3  # Map [-1, 0, 1] to [0, 0.33, 0.66]


class RegressionMLStrategy(MLStrategy):
    """ML Strategy for regression models (price/return prediction)."""

    def __init__(self, *args, prediction_type: str = "return", **kwargs):
        """
        Initialize regression strategy.

        Args:
            prediction_type: 'return' or 'price'
        """
        super().__init__(*args, **kwargs)
        self.prediction_type = prediction_type

    def _get_predictions(self, features: pd.DataFrame) -> pd.Series:
        """Get predictions from regression model."""
        predictions = self.model.predict(features)

        if self.prediction_type == "return":
            # Convert return prediction to signal strength
            # Positive return -> buy signal (>0.5)
            # Negative return -> sell signal (<0.5)
            return pd.Series(1 / (1 + np.exp(-predictions * 100)))  # Sigmoid scaling
        else:
            # Price prediction - compare with current price
            current_price = features.iloc[0].get("close", 1.0)
            price_change = (predictions - current_price) / current_price
            return pd.Series(1 / (1 + np.exp(-price_change * 1000)))  # Sigmoid scaling


class EnsembleMLStrategy(MLStrategy):
    """ML Strategy using ensemble of models."""

    def __init__(
        self,
        models: List[Any],
        weights: Optional[List[float]] = None,
        voting: str = "soft",
        *args,
        **kwargs,
    ):
        """
        Initialize ensemble strategy.

        Args:
            models: List of ML models
            weights: Optional weights for each model
            voting: 'soft' (average probabilities) or 'hard' (majority vote)
        """
        super().__init__(models[0], *args, **kwargs)  # Use first model as base
        self.models = models
        self.weights = weights or [1.0 / len(models)] * len(models)
        self.voting = voting

    def _get_predictions(self, features: pd.DataFrame) -> np.ndarray:
        """Get ensemble predictions."""
        all_predictions = []

        for model, weight in zip(self.models, self.weights):
            if hasattr(model, "predict_proba"):
                pred = model.predict_proba(features)[:, -1]
            else:
                pred = model.predict(features)
                pred = (pred + 1) / 3  # Normalize to [0, 1]
            all_predictions.append(pred * weight)

        if self.voting == "soft":
            # Weighted average
            return np.sum(all_predictions, axis=0)
        else:
            # Hard voting
            votes = np.array([p > 0.5 for p in all_predictions])
            return np.average(votes, weights=self.weights, axis=0)


class WaveMLStrategy(MLStrategy):
    """ML Strategy incorporating Elliott Wave analysis."""

    def __init__(
        self,
        ml_model: Any,
        wave_analyzer: Any,
        wave_weight: float = 0.3,
        *args,
        **kwargs,
    ):
        """
        Initialize Wave ML Strategy.

        Args:
            ml_model: ML model for predictions
            wave_analyzer: Elliott Wave analyzer
            wave_weight: Weight given to wave analysis (0-1)
        """
        super().__init__(ml_model, *args, **kwargs)
        self.wave_analyzer = wave_analyzer
        self.wave_weight = wave_weight

    def _generate_signals(
        self,
        predictions: Union[np.ndarray, pd.Series],
        data: pd.DataFrame,
        portfolio: Portfolio,
    ) -> List[SignalEvent]:
        """Generate signals combining ML and Wave analysis."""
        # Get base ML signals
        ml_signals = super()._generate_signals(predictions, data, portfolio)

        # Get wave analysis
        wave_patterns = self.wave_analyzer.analyze(data)

        # Combine signals
        combined_signals = []
        for signal in ml_signals:
            # Adjust signal strength based on wave analysis
            wave_score = self._get_wave_score(wave_patterns, signal.signal_type)

            # Combine ML and wave scores
            combined_strength = (
                signal.strength * (1 - self.wave_weight) + wave_score * self.wave_weight
            )

            # Update signal
            signal.strength = combined_strength
            signal.metadata["wave_score"] = wave_score
            signal.metadata["wave_patterns"] = [str(p) for p in wave_patterns]

            # Only keep strong signals
            if combined_strength > self.prediction_threshold:
                combined_signals.append(signal)

        return combined_signals

    def _get_wave_score(self, wave_patterns: List[Any], signal_type: str) -> float:
        """Calculate wave analysis score for signal."""
        if not wave_patterns:
            return 0.5  # Neutral

        # Get the most recent/relevant pattern
        pattern = wave_patterns[0]

        # Score based on wave type and signal alignment
        if signal_type == "BUY":
            if pattern.wave_type in ["IMPULSE_UP", "WAVE_3_UP", "WAVE_5_UP"]:
                return 0.8
            elif pattern.wave_type in ["CORRECTIVE_DOWN", "WAVE_C_DOWN"]:
                return 0.3  # Counter-trend
            else:
                return 0.5
        else:  # SELL
            if pattern.wave_type in ["IMPULSE_DOWN", "WAVE_3_DOWN", "WAVE_5_DOWN"]:
                return 0.8
            elif pattern.wave_type in ["CORRECTIVE_UP", "WAVE_B_UP"]:
                return 0.3  # Counter-trend
            else:
                return 0.5


# Signal Filters
def trend_filter(
    signals: List[SignalEvent], data: pd.DataFrame, portfolio: Portfolio
) -> List[SignalEvent]:
    """Filter signals based on trend alignment."""
    # Calculate trend
    sma_fast = data["close"].rolling(20).mean().iloc[-1]
    sma_slow = data["close"].rolling(50).mean().iloc[-1]

    trend_up = sma_fast > sma_slow

    filtered = []
    for signal in signals:
        if (signal.signal_type == "BUY" and trend_up) or (
            signal.signal_type == "SELL" and not trend_up
        ):
            filtered.append(signal)

    return filtered


def volatility_filter(
    signals: List[SignalEvent],
    data: pd.DataFrame,
    portfolio: Portfolio,
    min_volatility: float = 0.0005,
    max_volatility: float = 0.005,
) -> List[SignalEvent]:
    """Filter signals based on volatility conditions."""
    # Calculate recent volatility
    returns = data["close"].pct_change()
    volatility = returns.rolling(20).std().iloc[-1]

    if min_volatility <= volatility <= max_volatility:
        return signals
    else:
        return []  # No signals in extreme volatility


def time_filter(
    signals: List[SignalEvent],
    data: pd.DataFrame,
    portfolio: Portfolio,
    allowed_hours: List[int] = None,
) -> List[SignalEvent]:
    """Filter signals based on time of day."""
    if allowed_hours is None:
        allowed_hours = list(range(8, 17))  # 8 AM to 5 PM

    current_hour = data.index[-1].hour

    if current_hour in allowed_hours:
        return signals
    else:
        return []
