"""Market regime classification module.

This module provides functionality for identifying and classifying market regimes
using a combination of technical market data and economic indicators. It extends
the economic regime classification with market-specific dynamics.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from fxml4.config import get_config
from fxml4.ml.economic_features import EconomicFeatureEngineer

logger = logging.getLogger(__name__)


class MarketRegimeClassifier:
    """Market regime classifier using both market and economic data."""

    def __init__(self, config: Optional[Dict] = None):
        """Initialize the market regime classifier.

        Args:
            config: Configuration dictionary.
        """
        self.config = config or {}
        self.regime_config = self.config.get("market_regimes", {})

        # Configure classifier settings
        self.n_regimes = self.regime_config.get(
            "n_regimes", get_config().get("ml.market_regimes.n_regimes", 5)
        )
        self.use_economic_data = self.regime_config.get(
            "use_economic_data",
            get_config().get("ml.market_regimes.use_economic_data", True),
        )
        self.use_pca = self.regime_config.get(
            "use_pca", get_config().get("ml.market_regimes.use_pca", True)
        )
        self.pca_components = self.regime_config.get(
            "pca_components", get_config().get("ml.market_regimes.pca_components", 5)
        )
        self.regime_window = self.regime_config.get(
            "regime_window",
            get_config().get("ml.market_regimes.regime_window", 126),  # ~6 months
        )

        # Features to use for regime classification
        self.market_features = self.regime_config.get(
            "market_features",
            [
                "volatility_20",  # Recent volatility
                "volume_ratio_10",  # Volume relative to average
                "rsi_14",  # RSI
                "bb_width",  # Bollinger Band width
                "atr_14",  # Average True Range
                "return_10",  # Medium-term return
                "return_20",  # Longer-term return
                "cci_20",  # Commodity Channel Index
                "price_position_20",  # Price position in range
            ],
        )

        # Economic indicators to use (if available)
        if self.use_economic_data:
            self.economic_features = self.regime_config.get(
                "economic_features",
                [
                    "econ_VIXCLS",  # VIX
                    "econ_T10Y2Y",  # Yield curve
                    "econ_CPIAUCSL_12m_change",  # Inflation YoY
                    "econ_UNRATE",  # Unemployment
                    "econ_GDP_4q_change",  # GDP growth
                    "econ_FEDFUNDS",  # Fed Funds rate
                ],
            )

            # Initialize economic feature engineer
            self.economic_engineer = EconomicFeatureEngineer(config)

        # Placeholder for fitted models
        self.scaler = None
        self.pca_model = None
        self.kmeans_model = None
        self.regime_labels = None
        self.regime_centers = None

        logger.info(
            f"Initialized market regime classifier with {self.n_regimes} regimes"
        )

    def fit(
        self, market_data: pd.DataFrame, economic_data: Optional[pd.DataFrame] = None
    ) -> None:
        """Fit the regime classifier model on historical data.

        Args:
            market_data: DataFrame with market features
            economic_data: Optional DataFrame with economic indicators
        """
        # Create feature matrix for regime detection
        X = self._prepare_feature_matrix(market_data, economic_data)

        if X.empty:
            logger.warning("Empty feature matrix. Cannot fit regime classifier.")
            return

        # Standardize features
        self.scaler = StandardScaler()
        X_scaled = pd.DataFrame(
            self.scaler.fit_transform(X), index=X.index, columns=X.columns
        )

        # Apply PCA if configured
        if self.use_pca and X.shape[1] > self.pca_components:
            self.pca_model = PCA(n_components=self.pca_components)
            X_pca = pd.DataFrame(
                self.pca_model.fit_transform(X_scaled), index=X_scaled.index
            )

            logger.info(
                f"PCA reduced features from {X_scaled.shape[1]} to {X_pca.shape[1]} "
                f"components explaining {sum(self.pca_model.explained_variance_ratio_):.2%} of variance"
            )

            # Use PCA output for clustering
            X_for_clustering = X_pca
        else:
            # Use scaled features directly
            X_for_clustering = X_scaled

        # Fit K-means clustering
        self.kmeans_model = KMeans(
            n_clusters=self.n_regimes, random_state=42, n_init=10
        )
        self.kmeans_model.fit(X_for_clustering)

        # Get regime labels and centers
        self.regime_labels = pd.Series(
            self.kmeans_model.labels_, index=X.index, name="market_regime"
        )

        if self.use_pca:
            # For interpretability, we want centers in original feature space
            # Transform cluster centers back to original space
            pca_centers = self.kmeans_model.cluster_centers_
            if self.pca_model is not None:
                # This is approximate - inverting PCA is not perfect
                centers_scaled = self.pca_model.inverse_transform(pca_centers)
                self.regime_centers = self.scaler.inverse_transform(centers_scaled)
            else:
                self.regime_centers = self.scaler.inverse_transform(pca_centers)
        else:
            # Transform cluster centers back to original feature space
            self.regime_centers = self.scaler.inverse_transform(
                self.kmeans_model.cluster_centers_
            )

        logger.info(f"Fitted market regime classifier with {self.n_regimes} regimes")

    def predict(
        self, market_data: pd.DataFrame, economic_data: Optional[pd.DataFrame] = None
    ) -> pd.Series:
        """Predict market regimes for the given data.

        Args:
            market_data: DataFrame with market features
            economic_data: Optional DataFrame with economic indicators

        Returns:
            Series with regime labels for each timestamp
        """
        if self.kmeans_model is None:
            logger.error("Regime classifier not fitted. Call fit() first.")
            return pd.Series(index=market_data.index)

        # Create feature matrix for regime detection
        X = self._prepare_feature_matrix(market_data, economic_data)

        if X.empty:
            logger.warning("Empty feature matrix. Cannot predict regimes.")
            return pd.Series(index=market_data.index)

        # Standardize features
        X_scaled = pd.DataFrame(
            self.scaler.transform(X), index=X.index, columns=X.columns
        )

        # Apply PCA if configured
        if self.use_pca and self.pca_model is not None:
            X_pca = pd.DataFrame(
                self.pca_model.transform(X_scaled), index=X_scaled.index
            )
            X_for_clustering = X_pca
        else:
            X_for_clustering = X_scaled

        # Predict regimes
        regime_labels = pd.Series(
            self.kmeans_model.predict(X_for_clustering),
            index=X.index,
            name="market_regime",
        )

        return regime_labels

    def detect_regime_shifts(self, regimes: pd.Series, window: int = None) -> pd.Series:
        """Detect regime shifts by comparing recent regime to historical regime.

        A regime shift is identified when the current regime differs from the
        most common regime in the lookback window.

        Args:
            regimes: Series with regime labels
            window: Lookback window (uses self.regime_window if None)

        Returns:
            Series with boolean values indicating regime shifts
        """
        window = window or self.regime_window

        if len(regimes) <= window:
            # Not enough data to detect shifts
            return pd.Series(False, index=regimes.index)

        # Calculate rolling most common regime
        rolling_mode = regimes.rolling(window=window).apply(
            lambda x: pd.Series(x).value_counts().idxmax()
        )

        # Detect shifts by comparing current regime to rolling mode
        regime_shifts = regimes != rolling_mode

        return regime_shifts

    def get_regime_characteristics(self) -> pd.DataFrame:
        """Get characteristics of each identified regime.

        Returns:
            DataFrame with regime characteristics
        """
        if self.regime_centers is None or self.kmeans_model is None:
            logger.error("Regime classifier not fitted. Call fit() first.")
            return pd.DataFrame()

        # Get feature names
        if self.use_economic_data and hasattr(self, "economic_features"):
            feature_names = self.market_features + self.economic_features
        else:
            feature_names = self.market_features

        # Create DataFrame with regime centers
        centers_df = pd.DataFrame(self.regime_centers, columns=feature_names)
        centers_df.index.name = "regime"
        centers_df.index = [f"Regime {i}" for i in range(self.n_regimes)]

        # Calculate regime frequencies if we have labels
        if self.regime_labels is not None:
            regime_counts = self.regime_labels.value_counts().sort_index()
            regime_pcts = regime_counts / regime_counts.sum()

            # Add frequency information
            centers_df["frequency"] = [
                regime_pcts.get(i, 0) for i in range(self.n_regimes)
            ]
            centers_df["count"] = [
                regime_counts.get(i, 0) for i in range(self.n_regimes)
            ]

        return centers_df

    def describe_regimes(self) -> Dict[int, Dict[str, Any]]:
        """Generate qualitative descriptions of each regime.

        Returns:
            Dictionary with regime descriptions
        """
        if self.regime_centers is None:
            logger.error("Regime classifier not fitted. Call fit() first.")
            return {}

        # Get regime characteristics
        characteristics = self.get_regime_characteristics()

        # Create dictionary to store descriptions
        regime_descriptions = {}

        # Generate descriptions for each regime
        for i in range(self.n_regimes):
            regime_key = f"Regime {i}"
            regime_char = characteristics.loc[regime_key]

            # Initialize description
            description = {
                "id": i,
                "name": regime_key,
                "frequency": regime_char.get("frequency", 0),
                "volatility": "unknown",
                "trend": "unknown",
                "volume": "unknown",
                "momentum": "unknown",
                "economic_context": "unknown" if not self.use_economic_data else {},
                "summary": "",
            }

            # Analyze volatility
            if "volatility_20" in regime_char:
                vol = regime_char["volatility_20"]
                if vol < characteristics["volatility_20"].quantile(0.33):
                    description["volatility"] = "low"
                elif vol > characteristics["volatility_20"].quantile(0.67):
                    description["volatility"] = "high"
                else:
                    description["volatility"] = "medium"

            # Analyze trend
            if "return_20" in regime_char:
                ret = regime_char["return_20"]
                if ret > 0.01:
                    description["trend"] = "strong bullish"
                elif ret > 0.002:
                    description["trend"] = "bullish"
                elif ret < -0.01:
                    description["trend"] = "strong bearish"
                elif ret < -0.002:
                    description["trend"] = "bearish"
                else:
                    description["trend"] = "sideways"

            # Analyze volume
            if "volume_ratio_10" in regime_char:
                vol_ratio = regime_char["volume_ratio_10"]
                if vol_ratio > 1.2:
                    description["volume"] = "high"
                elif vol_ratio < 0.8:
                    description["volume"] = "low"
                else:
                    description["volume"] = "average"

            # Analyze momentum
            if "rsi_14" in regime_char:
                rsi = regime_char["rsi_14"]
                if rsi > 70:
                    description["momentum"] = "overbought"
                elif rsi < 30:
                    description["momentum"] = "oversold"
                elif rsi > 55:
                    description["momentum"] = "positive"
                elif rsi < 45:
                    description["momentum"] = "negative"
                else:
                    description["momentum"] = "neutral"

            # Analyze economic context if available
            if self.use_economic_data:
                econ_context = {}

                # Inflation
                if "econ_CPIAUCSL_12m_change" in regime_char:
                    inflation = regime_char["econ_CPIAUCSL_12m_change"]
                    if inflation > 0.04:
                        econ_context["inflation"] = "high"
                    elif inflation < 0.015:
                        econ_context["inflation"] = "low"
                    else:
                        econ_context["inflation"] = "moderate"

                # Interest rates
                if "econ_FEDFUNDS" in regime_char:
                    rates = regime_char["econ_FEDFUNDS"]
                    if rates > 0.04:
                        econ_context["interest_rates"] = "high"
                    elif rates < 0.01:
                        econ_context["interest_rates"] = "low"
                    else:
                        econ_context["interest_rates"] = "moderate"

                # Yield curve
                if "econ_T10Y2Y" in regime_char:
                    curve = regime_char["econ_T10Y2Y"]
                    if curve < 0:
                        econ_context["yield_curve"] = "inverted"
                    elif curve < 0.005:
                        econ_context["yield_curve"] = "flat"
                    else:
                        econ_context["yield_curve"] = "normal"

                # Growth
                if "econ_GDP_4q_change" in regime_char:
                    growth = regime_char["econ_GDP_4q_change"]
                    if growth > 0.03:
                        econ_context["growth"] = "strong"
                    elif growth > 0.01:
                        econ_context["growth"] = "moderate"
                    elif growth > 0:
                        econ_context["growth"] = "weak"
                    else:
                        econ_context["growth"] = "negative"

                # VIX
                if "econ_VIXCLS" in regime_char:
                    vix = regime_char["econ_VIXCLS"]
                    if vix > 30:
                        econ_context["market_anxiety"] = "high"
                    elif vix < 15:
                        econ_context["market_anxiety"] = "low"
                    else:
                        econ_context["market_anxiety"] = "moderate"

                description["economic_context"] = econ_context

            # Generate summary
            summary = f"{description['trend']} trend with {description['volatility']} volatility "
            summary += f"and {description['volume']} volume. Momentum is {description['momentum']}."

            if self.use_economic_data and isinstance(
                description["economic_context"], dict
            ):
                econ = description["economic_context"]
                if econ:
                    summary += " Economic context: "
                    context_points = []

                    if "inflation" in econ:
                        context_points.append(f"{econ['inflation']} inflation")
                    if "interest_rates" in econ:
                        context_points.append(
                            f"{econ['interest_rates']} interest rates"
                        )
                    if "growth" in econ:
                        context_points.append(f"{econ['growth']} growth")
                    if "yield_curve" in econ:
                        context_points.append(f"{econ['yield_curve']} yield curve")
                    if "market_anxiety" in econ:
                        context_points.append(
                            f"{econ['market_anxiety']} market anxiety"
                        )

                    summary += ", ".join(context_points) + "."

            description["summary"] = summary
            regime_descriptions[i] = description

        return regime_descriptions

    def _prepare_feature_matrix(
        self, market_data: pd.DataFrame, economic_data: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """Prepare feature matrix for regime detection.

        Args:
            market_data: DataFrame with market features
            economic_data: Optional DataFrame with economic indicators

        Returns:
            DataFrame with selected features for regime detection
        """
        # Initialize list to store features
        selected_features = []

        # Select market features if available
        market_features = (
            market_data[self.market_features].copy()
            if all(f in market_data.columns for f in self.market_features)
            else pd.DataFrame(index=market_data.index)
        )

        if not market_features.empty:
            selected_features.append(market_features)

        # Add economic features if enabled and available
        if (
            self.use_economic_data
            and economic_data is not None
            and not economic_data.empty
        ):
            # Select features if available, otherwise return empty DataFrame
            economic_features = pd.DataFrame(index=market_data.index)

            # Check if economic features were already added with 'econ_' prefix
            if any(col.startswith("econ_") for col in market_data.columns):
                # Features already added to market data
                econ_cols = [
                    col for col in self.economic_features if col in market_data.columns
                ]
                if econ_cols:
                    economic_features = market_data[econ_cols].copy()
            else:
                # Need to create economic features
                processed_economic = self.economic_engineer.create_features(
                    economic_data
                )

                # Ensure economic data is aligned with market data
                # Resample to daily if needed
                if not isinstance(processed_economic.index, pd.DatetimeIndex):
                    logger.warning("Economic data does not have a datetime index")
                else:
                    # Create a date range spanning both datasets
                    date_range = pd.date_range(
                        start=min(
                            market_data.index.min(), processed_economic.index.min()
                        ),
                        end=max(
                            market_data.index.max(), processed_economic.index.max()
                        ),
                        freq="D",  # Daily frequency
                    )

                    # Resample economic data to daily
                    daily_economic = processed_economic.reindex(date_range).ffill()

                    # Align with market data
                    aligned_economic = daily_economic.reindex(
                        market_data.index, method="ffill"
                    )

                    # Add prefix to columns
                    aligned_economic = aligned_economic.add_prefix("econ_")

                    # Extract features if they exist
                    econ_cols = [
                        col
                        for col in self.economic_features
                        if col in aligned_economic.columns
                    ]
                    if econ_cols:
                        economic_features = aligned_economic[econ_cols].copy()

            if not economic_features.empty:
                selected_features.append(economic_features)

        # Combine all features
        if not selected_features:
            logger.warning("No features available for regime detection")
            return pd.DataFrame(index=market_data.index)

        X = pd.concat(selected_features, axis=1)

        # Handle missing values
        X = X.fillna(method="ffill").fillna(method="bfill")

        # Check if we have any remaining NaN values
        if X.isna().any().any():
            logger.warning(
                f"Feature matrix contains {X.isna().sum().sum()} NaN values after forward/backward fill"
            )
            X = X.dropna()

        return X


def classify_market_regimes(
    market_data: pd.DataFrame,
    economic_data: Optional[pd.DataFrame] = None,
    n_regimes: int = 5,
    config: Optional[Dict] = None,
) -> pd.Series:
    """Classify market regimes using market and economic data.

    Args:
        market_data: DataFrame with market features
        economic_data: Optional DataFrame with economic indicators
        n_regimes: Number of regimes to detect
        config: Optional configuration dictionary

    Returns:
        Series with regime classifications
    """
    # Create configuration if not provided
    if config is None:
        config = {"market_regimes": {"n_regimes": n_regimes}}
    elif "market_regimes" not in config:
        config["market_regimes"] = {"n_regimes": n_regimes}
    else:
        config["market_regimes"]["n_regimes"] = n_regimes

    # Create and fit classifier
    classifier = MarketRegimeClassifier(config)
    classifier.fit(market_data, economic_data)

    # Predict regimes
    regimes = classifier.predict(market_data, economic_data)

    return regimes


def get_regime_descriptions(
    market_data: pd.DataFrame,
    regimes: pd.Series,
    economic_data: Optional[pd.DataFrame] = None,
    config: Optional[Dict] = None,
) -> Dict[int, Dict[str, Any]]:
    """Get descriptions of market regimes.

    Args:
        market_data: DataFrame with market features
        regimes: Series with regime labels
        economic_data: Optional DataFrame with economic indicators
        config: Optional configuration dictionary

    Returns:
        Dictionary with regime descriptions
    """
    # Create configuration if not provided
    if config is None:
        config = {"market_regimes": {"n_regimes": regimes.nunique()}}
    elif "market_regimes" not in config:
        config["market_regimes"] = {"n_regimes": regimes.nunique()}
    else:
        config["market_regimes"]["n_regimes"] = regimes.nunique()

    # Create and fit classifier
    classifier = MarketRegimeClassifier(config)
    classifier.fit(market_data, economic_data)

    # Set regime labels
    classifier.regime_labels = regimes

    # Get regime descriptions
    descriptions = classifier.describe_regimes()

    return descriptions
