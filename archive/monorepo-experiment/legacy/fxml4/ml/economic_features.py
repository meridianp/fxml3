"""Economic feature engineering.

This module provides functionality for creating economic indicator features.
"""

import logging
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from fxml4.config import get_config

logger = logging.getLogger(__name__)


class EconomicFeatureEngineer:
    """Economic feature engineering for market data."""
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize the economic feature engineer.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.economic_config = self.config.get("economic", {})
        
        # Configure economic features
        self.regime_detection_method = self.economic_config.get(
            "regime_detection_method",
            get_config("ml.economic_features.regime_detection_method", "kmeans")
        )
        self.n_regimes = self.economic_config.get(
            "n_regimes",
            get_config("ml.economic_features.n_regimes", 3)
        )
        self.use_derived_features = self.economic_config.get(
            "use_derived_features",
            get_config("ml.economic_features.use_derived_features", True)
        )
        
        # Load indicator weights (importance for regime detection)
        self.indicator_weights = self.economic_config.get(
            "indicator_weights",
            get_config("ml.economic_features.indicator_weights", {})
        )
        
        # Default weights if none provided
        if not self.indicator_weights:
            self.indicator_weights = {
                "FEDFUNDS": 1.0,  # Fed Funds Rate
                "UNRATE": 0.8,    # Unemployment Rate
                "CPIAUCSL": 0.8,  # CPI
                "GDP": 0.6,       # GDP
                "INDPRO": 0.4,    # Industrial Production
                "RSAFS": 0.4,     # Retail Sales
                "DGS10": 0.7,     # 10-Year Treasury Rate
                "T10Y2Y": 0.9,    # 10Y-2Y Yield Spread
                "T10Y3M": 0.7,    # 10Y-3M Yield Spread
                "USREC": 1.0,     # Recession Indicator
                "VIXCLS": 0.6     # VIX
            }
        
        # Set the lookback period for rolling features
        self.lookback_periods = self.economic_config.get(
            "lookback_periods",
            get_config("ml.economic_features.lookback_periods", [3, 6, 12])
        )
        
        logger.info("Initialized economic feature engineer")
    
    def create_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Create economic features from indicator data.
        
        Args:
            data: Economic indicator data
            
        Returns:
            DataFrame with added economic features
        """
        if data.empty:
            logger.warning("Empty economic data provided")
            return data
        
        df = data.copy()
        
        # Ensure index is datetime
        if not isinstance(df.index, pd.DatetimeIndex):
            logger.warning("Economic data index is not datetime, attempting to convert")
            
            # Try to convert if there's a date column
            date_cols = [col for col in df.columns if 'date' in col.lower()]
            if date_cols:
                df[date_cols[0]] = pd.to_datetime(df[date_cols[0]])
                df.set_index(date_cols[0], inplace=True)
            else:
                logger.error("Cannot convert index to datetime, no date column found")
                return df
        
        # Create z-scores for each indicator (normalized values)
        for col in df.columns:
            df[f"{col}_zscore"] = (df[col] - df[col].mean()) / df[col].std()
        
        # Create rate of change features
        for col in df.columns:
            # Only apply to numeric columns, skip derived columns
            if not pd.api.types.is_numeric_dtype(df[col]) or '_' in col:
                continue
                
            # Current month-over-month change
            df[f"{col}_mom"] = df[col].pct_change()
            
            # Year-over-year change
            df[f"{col}_yoy"] = df[col].pct_change(12)
            
            # Rolling rates of change
            for period in self.lookback_periods:
                # Rolling average
                df[f"{col}_ma{period}"] = df[col].rolling(period).mean()
                
                # Rolling standard deviation (volatility)
                df[f"{col}_std{period}"] = df[col].rolling(period).std()
                
                # Rolling z-score (current value relative to recent history)
                rolling_mean = df[col].rolling(period).mean()
                rolling_std = df[col].rolling(period).std()
                df[f"{col}_zscore{period}"] = (df[col] - rolling_mean) / rolling_std
        
        # Create derived features if enabled
        if self.use_derived_features:
            # Yield curve features (if available)
            if 'DGS10' in df.columns and 'DGS2' in df.columns:
                df['yield_spread_10y2y'] = df['DGS10'] - df['DGS2']
                df['yield_curve_slope'] = df['yield_spread_10y2y'].rolling(3).mean()
                df['yield_curve_steepening'] = df['yield_curve_slope'].diff()
            
            # Inflation adjusted interest rates (real rates)
            if 'FEDFUNDS' in df.columns and 'CPIAUCSL_yoy' in df.columns:
                df['real_rate'] = df['FEDFUNDS'] - df['CPIAUCSL_yoy']
            
            # Economic momentum (aggregating changes across indicators)
            growth_indicators = ['GDP_yoy', 'INDPRO_yoy', 'RSAFS_yoy']
            available_indicators = [ind for ind in growth_indicators if ind in df.columns]
            
            if available_indicators:
                df['economic_momentum'] = df[available_indicators].mean(axis=1)
            
            # Inflation pressure
            inflation_indicators = ['CPIAUCSL_mom', 'CPIAUCSL_yoy']
            available_indicators = [ind for ind in inflation_indicators if ind in df.columns]
            
            if available_indicators:
                df['inflation_pressure'] = df[available_indicators].mean(axis=1)
            
            # Labor market health
            if 'UNRATE' in df.columns:
                df['labor_market_health'] = -1 * df['UNRATE_zscore']  # Invert so positive is healthy
        
        # Fill NaN values
        df = df.fillna(method='ffill').fillna(method='bfill')
        
        return df
    
    def detect_economic_regime(self, data: pd.DataFrame) -> pd.Series:
        """Detect economic regimes from economic indicator data.
        
        Args:
            data: Economic data with features
            
        Returns:
            Series with regime labels
        """
        from sklearn.preprocessing import StandardScaler
        
        if data.empty:
            logger.warning("Empty economic data provided for regime detection")
            return pd.Series()
        
        # Select features for regime detection
        # Prefer economic_momentum, inflation_pressure, etc. if available
        derived_features = [
            'economic_momentum', 'inflation_pressure', 'real_rate',
            'yield_curve_slope', 'labor_market_health'
        ]
        
        # Check which derived features are available
        available_derived = [col for col in derived_features if col in data.columns]
        
        if available_derived and len(available_derived) >= 3:
            # Use derived features if enough are available
            features = available_derived
        else:
            # Otherwise use key indicators (with weights)
            key_indicators = []
            
            # Use z-scores when available
            for indicator in self.indicator_weights.keys():
                if f"{indicator}_zscore" in data.columns:
                    key_indicators.append(f"{indicator}_zscore")
                elif indicator in data.columns:
                    key_indicators.append(indicator)
            
            # Filter for available indicators
            features = [col for col in key_indicators if col in data.columns]
        
        if not features:
            logger.warning("No suitable features found for regime detection")
            return pd.Series(0, index=data.index)
        
        # Get feature data and handle missing values
        X = data[features].copy()
        X = X.fillna(method='ffill').fillna(method='bfill').fillna(0)
        
        # Scale the data
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # Detect regimes using the specified method
        if self.regime_detection_method == 'kmeans':
            from sklearn.cluster import KMeans
            
            # Fit KMeans
            kmeans = KMeans(n_clusters=self.n_regimes, random_state=42)
            regimes = kmeans.fit_predict(X_scaled)
            
            # Create a Series with regime labels
            regime_series = pd.Series(regimes, index=data.index)
            
        elif self.regime_detection_method == 'gmm':
            from sklearn.mixture import GaussianMixture
            
            # Fit Gaussian Mixture Model
            gmm = GaussianMixture(n_components=self.n_regimes, random_state=42)
            regimes = gmm.fit_predict(X_scaled)
            
            # Create a Series with regime labels
            regime_series = pd.Series(regimes, index=data.index)
            
        elif self.regime_detection_method == 'hmm':
            from hmmlearn import hmm
            
            # Fit Hidden Markov Model
            model = hmm.GaussianHMM(n_components=self.n_regimes, random_state=42)
            regimes = model.fit_predict(X_scaled)
            
            # Create a Series with regime labels
            regime_series = pd.Series(regimes, index=data.index)
            
        else:
            logger.warning(f"Unknown regime detection method: {self.regime_detection_method}")
            regime_series = pd.Series(0, index=data.index)
        
        return regime_series