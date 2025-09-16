"""GBPUSD ML model implementation.

This module implements ML models specifically optimized for GBP/USD trading
on the 4-hour timeframe.
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
import xgboost as xgb
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

from fxml4.ml.features import (
    create_technical_features, 
    add_lagged_features,
    calculate_weekly_pivot_points,
    calculate_session_pivot_levels
)
from fxml4.config import get_config

logger = logging.getLogger(__name__)


class GBPUSDModel:
    """ML model for GBP/USD trading."""
    
    def __init__(
        self,
        model_type: str = "random_forest",
        model_params: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
        n_classes: int = 3,
        random_state: int = 42
    ):
        """Initialize the GBP/USD model.
        
        Args:
            model_type: Type of model to use ('random_forest', 'xgboost', 'logistic')
            model_params: Parameters for the model
            name: Name of the model (defaults to model_type + timestamp)
            n_classes: Number of classes for classification (3 for -1, 0, 1)
            random_state: Random state for reproducibility
        """
        self.model_type = model_type
        self.model_params = model_params or {}
        self.n_classes = n_classes
        self.random_state = random_state
        
        # Set default model parameters
        self._set_default_params()
        
        # Create model
        self.model = self._create_model()
        
        # Set model name
        if name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.name = f"gbpusd_{model_type}_{timestamp}"
        else:
            self.name = name
        
        # Initialize feature importance and feature names
        self.feature_importance = None
        self.feature_names = None
        
        # Initialize scaler
        self.scaler = None
        
        logger.info(f"Initialized GBP/USD model: {self.name}")
    
    def _set_default_params(self):
        """Set default model parameters based on model type."""
        if self.model_type == "logistic":
            defaults = {
                "C": 1.0,
                "penalty": "l2",
                "solver": "liblinear",
                "max_iter": 1000,
                "random_state": self.random_state
            }
        elif self.model_type == "random_forest":
            defaults = {
                "n_estimators": 200,
                "max_depth": 15,
                "min_samples_split": 5,
                "min_samples_leaf": 2,
                "class_weight": "balanced",
                "random_state": self.random_state
            }
        elif self.model_type == "xgboost":
            defaults = {
                "n_estimators": 200,
                "max_depth": 6,
                "learning_rate": 0.1,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "objective": "multi:softmax" if self.n_classes > 2 else "binary:logistic",
                "num_class": self.n_classes if self.n_classes > 2 else None,
                "random_state": self.random_state
            }
            
            # Remove None values
            defaults = {k: v for k, v in defaults.items() if v is not None}
        else:
            defaults = {}
        
        # Update with user-provided parameters
        for key, value in self.model_params.items():
            defaults[key] = value
        
        self.model_params = defaults
    
    def _create_model(self) -> Any:
        """Create model based on model type."""
        if self.model_type == "logistic":
            return LogisticRegression(**self.model_params)
        elif self.model_type == "random_forest":
            return RandomForestClassifier(**self.model_params)
        elif self.model_type == "xgboost":
            return xgb.XGBClassifier(**self.model_params)
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")
    
    def prepare_features(
        self,
        data: pd.DataFrame,
        target_horizon: int = 12,
        target_threshold: float = 0.001,
        add_lag_features: bool = True,
        add_pivot_points: bool = True,
        add_session_features: bool = True,
        add_enhanced_features: bool = True,
        labeling_method: str = "fixed_threshold",
        create_target: bool = True
    ) -> pd.DataFrame:
        """Prepare features for model training or prediction.
        
        Args:
            data: Raw price data with OHLC columns
            target_horizon: Number of periods ahead for the target (default: 12 for 4h timeframe)
            target_threshold: Minimum price change for classification (default: 0.001 or 0.1%)
            add_lag_features: Whether to add lagged features
            add_pivot_points: Whether to add pivot point analysis features
            add_session_features: Whether to add trading session features
            add_enhanced_features: Whether to add enhanced/composite features
            labeling_method: Method for creating target labels
                - fixed_threshold: Use fixed threshold for returns
                - volatility_adjusted: Adjust threshold based on local volatility
                - dynamic_quantile: Use dynamic quantiles for thresholds
                - trend_adjusted: Adjust threshold based on market trend
            create_target: Whether to create target variable
            
        Returns:
            DataFrame with prepared features
        """
        # Make sure we have a copy to avoid modifying the original
        features = data.copy()
        
        # Ensure the dataframe has a datetime index
        if not isinstance(features.index, pd.DatetimeIndex):
            logger.warning("Converting index to DatetimeIndex")
            features.index = pd.to_datetime(features.index)
        
        # Get important columns
        ohlc_columns = ['open', 'high', 'low', 'close']
        
        # Make sure we have these columns
        for col in ohlc_columns:
            if col not in features.columns:
                raise ValueError(f"Missing required column: {col}")
        
        # Add trading session features
        if add_session_features:
            logger.info("Adding trading session features")
            try:
                features = identify_trading_sessions(features)
            except Exception as e:
                logger.error(f"Error adding trading session features: {e}")
        
        # Create technical features - using exact parameters from FXML2
        features = create_technical_features(
            features,
            indicators=['sma', 'ema', 'rsi', 'macd', 'bollinger', 'stoch', 'atr', 'adx'],
            ma_periods=[5, 21, 55, 200],  # FXML2 specific periods
            include_original=True,
            fillna=True,
            add_enhanced_features=add_enhanced_features
        )
        
        # Add custom features for 4h timeframe
        # Daily range as percentage of price
        features['daily_range_pct'] = (features['high'].rolling(6).max() - features['low'].rolling(6).min()) / features['close'] * 100
        
        # Volatility indicators - from FXML2
        if 'volatility_14' not in features.columns:
            features['volatility_14'] = features['close'].pct_change().rolling(14).std() * 100
        
        # Weekly open/close change - from FXML2
        if 'weekly_change' not in features.columns:
            features['weekly_change'] = (features['close'] - features['close'].shift(42)) / features['close'].shift(42) * 100
        
        # Add pivot point analysis features
        if add_pivot_points:
            logger.info("Adding pivot point analysis features")
            try:
                # Add weekly pivot points
                features = calculate_weekly_pivot_points(features)
                
                # Add session/daily pivot points
                features = calculate_session_pivot_levels(features)
                
                # Add key pivot point features for model
                pivot_cols = ['PP', 'R1', 'S1', 'R2', 'S2', 'R3', 'S3']
                
                # Calculate historical pivot point effectiveness
                # How often price reaches R1, S1 within N periods
                window = target_horizon
                
                # For each pivot level, check if price reached it within window
                for col in ['R1', 'R2', 'S1', 'S2']:
                    if col in features.columns:
                        # Create binary columns for whether price hit the level
                        if col.startswith('R'):  # Resistance level
                            features[f'hit_{col}_{window}'] = features['high'].rolling(window).max() >= features[col]
                        else:  # Support level
                            features[f'hit_{col}_{window}'] = features['low'].rolling(window).min() <= features[col]
                
                # Add enhanced pivot-based features if requested
                if add_enhanced_features:
                    # These are recalculated in create_technical_features but we'll ensure they're all added here
                    # Add pivot breakout indicators
                    pivot_cols = [col for col in features.columns if any(x in col for x in ["_r1", "_s1", "_r2", "_s2"])]
                    for col in pivot_cols:
                        if "r1" in col.lower():
                            # Resistance breakout
                            prefix = col.split("_r1")[0]
                            if f"{prefix}_r1" in features.columns:
                                features[f"{prefix}_breakout_up"] = (features["close"] > features[f"{prefix}_r1"]).astype(int)
                        elif "s1" in col.lower():
                            # Support breakout
                            prefix = col.split("_s1")[0]
                            if f"{prefix}_s1" in features.columns:
                                features[f"{prefix}_breakout_down"] = (features["close"] < features[f"{prefix}_s1"]).astype(int)
                
                logger.info("Pivot point features added successfully")
            except Exception as e:
                logger.error(f"Error adding pivot point features: {e}")
        
        # Add enhanced confluence indicators from FXML2
        if add_enhanced_features:
            logger.info("Adding enhanced confluence indicators")
            try:
                # Ensure required components exist
                if all(col in features.columns for col in ["bb_squeeze", "macd_cross_up", "close"]):
                    # Add confluence indicators for different pivot types
                    for prefix in ["weekly", "daily", "london", "newyork", "tokyo", "sydney"]:
                        r1_col = f"{prefix}_r1"
                        s1_col = f"{prefix}_s1"
                        
                        if r1_col in features.columns and s1_col in features.columns:
                            # Bullish confluence: BB Squeeze + MACD Cross Up + Price > R1
                            features[f"{prefix}_confluence_bull"] = (
                                (features["bb_squeeze"] == 1) &
                                (features["macd_cross_up"] == 1) &
                                (features["close"] > features[r1_col])
                            ).astype(int)
                            
                            # Bearish confluence: BB Squeeze + MACD Cross Down + Price < S1
                            features[f"{prefix}_confluence_bear"] = (
                                (features["bb_squeeze"] == 1) &
                                (features["macd_cross_down"] == 1) &
                                (features["close"] < features[s1_col])
                            ).astype(int)
            except Exception as e:
                logger.error(f"Error adding enhanced confluence indicators: {e}")
                
        # Add lagged features if requested
        if add_lag_features:
            logger.info("Adding lagged features")
            # Use FXML2 exact lag columns and values
            lag_columns = [
                'close', 'bb_width', 'macd', 'rsi_14', 'atr_14', 
                'adx_14', 'volatility_14', 'daily_range_pct'
            ]
            
            # Add pivot distance columns if they exist
            pivot_distance_cols = [col for col in features.columns if col.startswith('distance_to_')]
            lag_columns.extend(pivot_distance_cols)
            
            # Add session distance columns if they exist
            session_distance_cols = [col for col in features.columns if col.startswith('dist_')]
            lag_columns.extend(session_distance_cols)
            
            # Add confluence signal columns if they exist
            confluence_cols = [col for col in features.columns if 'confluence' in col]
            lag_columns.extend(confluence_cols)
            
            # Only use columns that exist
            lag_columns = [col for col in lag_columns if col in features.columns]
            
            features = add_lagged_features(
                features,
                columns=lag_columns,
                lags=[1, 2, 5],  # FXML2 specific lags
                include_returns=True
            )
        
        # Create target variable if requested
        if create_target:
            if labeling_method == "fixed_threshold":
                # Basic threshold labeling (original method)
                future_return = features['close'].shift(-target_horizon) / features['close'] - 1
                
                # Create target based on threshold
                target = np.zeros(len(features))
                target[future_return > target_threshold] = 1
                target[future_return < -target_threshold] = -1
                
                # Add target column
                features[f'target_{target_horizon}'] = target
                
                # Also add raw future return
                features[f'future_return_{target_horizon}'] = future_return
            
            elif labeling_method == "volatility_adjusted":
                # Calculate local volatility for dynamically adjusting the threshold
                returns = features['close'].pct_change()
                volatility = returns.rolling(window=20).std()
                
                # Calculate future return
                future_return = features['close'].shift(-target_horizon) / features['close'] - 1
                
                # Calculate adjusted thresholds based on volatility
                vol_multiplier = 1.5  # Adjust this parameter as needed
                upper_threshold = volatility * vol_multiplier
                lower_threshold = -volatility * vol_multiplier
                
                # Create target based on volatility-adjusted thresholds
                target = np.zeros(len(features))
                for i in range(len(features)):
                    if pd.isna(upper_threshold.iloc[i]) or pd.isna(future_return.iloc[i]):
                        target[i] = np.nan
                    elif future_return.iloc[i] > upper_threshold.iloc[i]:
                        target[i] = 1
                    elif future_return.iloc[i] < lower_threshold.iloc[i]:
                        target[i] = -1
                    else:
                        target[i] = 0
                
                # Add target columns
                features[f'target_{target_horizon}'] = target
                features[f'future_return_{target_horizon}'] = future_return
                features[f'vol_upper_threshold_{target_horizon}'] = upper_threshold
                features[f'vol_lower_threshold_{target_horizon}'] = lower_threshold
            
            elif labeling_method == "trend_adjusted":
                # Calculate trend using moving average
                trend_window = 100
                trend = features['close'].rolling(window=trend_window).mean().pct_change(trend_window // 2)
                
                # Normalize trend to range [-1, 1] for threshold adjustment
                max_trend = trend.abs().quantile(0.95)  # Use 95th percentile to avoid outliers
                normalized_trend = trend / max_trend
                normalized_trend = np.clip(normalized_trend, -1, 1)
                
                # Calculate future return
                future_return = features['close'].shift(-target_horizon) / features['close'] - 1
                
                # Adjust thresholds based on trend
                # In uptrend: easier to go long (lower threshold), harder to go short (higher threshold)
                trend_adjustment = normalized_trend * target_threshold * 0.5
                up_thresh = target_threshold - trend_adjustment  # Lower threshold in uptrend
                down_thresh = -target_threshold + trend_adjustment  # Higher threshold in uptrend
                
                # Create target based on trend-adjusted thresholds
                target = np.zeros(len(features))
                for i in range(len(features)):
                    if pd.isna(up_thresh.iloc[i]) or pd.isna(future_return.iloc[i]):
                        target[i] = np.nan
                    elif future_return.iloc[i] > up_thresh.iloc[i]:
                        target[i] = 1
                    elif future_return.iloc[i] < down_thresh.iloc[i]:
                        target[i] = -1
                    else:
                        target[i] = 0
                
                # Add target columns
                features[f'target_{target_horizon}'] = target
                features[f'future_return_{target_horizon}'] = future_return
                features[f'trend_{trend_window}'] = normalized_trend
                features[f'up_thresh_trend_adjusted_{target_horizon}'] = up_thresh
                features[f'down_thresh_trend_adjusted_{target_horizon}'] = down_thresh
            
            else:
                # Default to fixed threshold if unknown method
                logger.warning(f"Unknown labeling method '{labeling_method}', using fixed threshold")
                future_return = features['close'].shift(-target_horizon) / features['close'] - 1
                
                # Create target based on threshold
                target = np.zeros(len(features))
                target[future_return > target_threshold] = 1
                target[future_return < -target_threshold] = -1
                
                # Add target column
                features[f'target_{target_horizon}'] = target
                features[f'future_return_{target_horizon}'] = future_return
        
        # Drop rows with NaN values
        features = features.dropna()
        
        logger.info(f"Prepared {len(features)} rows with {len(features.columns)} features")
        
        return features
    
    def scale_features(
        self,
        features: pd.DataFrame,
        target_col: Optional[str] = None,
        refit: bool = True
    ) -> Tuple[pd.DataFrame, MinMaxScaler]:
        """Scale features using MinMaxScaler.
        
        Args:
            features: DataFrame with features
            target_col: Name of target column to exclude from scaling
            refit: Whether to fit the scaler on this data
            
        Returns:
            Tuple of (scaled features DataFrame, fitted scaler)
        """
        # Make a copy of the features
        X = features.copy()
        
        # Extract target if provided
        y = None
        if target_col is not None and target_col in X.columns:
            y = X[target_col].copy()
            X = X.drop(columns=[target_col])
        
        # Store feature names
        self.feature_names = X.columns.tolist()
        
        # Create or use existing scaler
        if self.scaler is None or refit:
            self.scaler = MinMaxScaler()
            X_scaled = self.scaler.fit_transform(X)
        else:
            X_scaled = self.scaler.transform(X)
        
        # Convert back to DataFrame
        X_scaled_df = pd.DataFrame(X_scaled, index=X.index, columns=X.columns)
        
        # Add target back if provided
        if y is not None:
            X_scaled_df[target_col] = y
        
        return X_scaled_df
    
    def train(
        self,
        features: pd.DataFrame,
        target_col: str,
        test_size: float = 0.2,
        use_cv: bool = False,
        n_splits: int = 5
    ) -> Dict[str, Any]:
        """Train the model on prepared features.
        
        Args:
            features: DataFrame with features and target
            target_col: Name of target column
            test_size: Fraction of data to use for testing
            use_cv: Whether to use cross-validation
            n_splits: Number of cross-validation splits
            
        Returns:
            Dictionary with training results
        """
        from sklearn.model_selection import train_test_split, TimeSeriesSplit
        
        # Make sure target column exists
        if target_col not in features.columns:
            raise ValueError(f"Target column '{target_col}' not found in features")
        
        # Split features and target
        X = features.drop(columns=[target_col])
        y = features[target_col]
        
        # Scale features
        X_scaled = self.scale_features(X, refit=True)
        
        # Split into train and test sets with time series order
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=test_size, shuffle=False
        )
        
        logger.info(f"Training {self.model_type} model on {len(X_train)} samples")
        
        # Check for class imbalance
        class_counts = pd.Series(y_train).value_counts()
        logger.info(f"Class distribution: {class_counts.to_dict()}")
        
        # Train the model
        if use_cv:
            # Use time series cross-validation
            from sklearn.model_selection import cross_val_score
            
            cv = TimeSeriesSplit(n_splits=n_splits)
            cv_scores = cross_val_score(self.model, X_scaled, y, cv=cv, scoring='f1_weighted')
            
            logger.info(f"Cross-validation scores: {cv_scores}")
            logger.info(f"Mean CV score: {cv_scores.mean():.4f}")
            
            # Train final model on all data
            self.model.fit(X_scaled, y)
        else:
            # Train on training set
            self.model.fit(X_train, y_train)
        
        # Store feature importance if available
        self._store_feature_importance()
        
        # Evaluate on test set
        y_pred = self.model.predict(X_test)
        
        results = {
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred, average='weighted'),
            "recall": recall_score(y_test, y_pred, average='weighted'),
            "f1": f1_score(y_test, y_pred, average='weighted'),
            "test_size": len(X_test),
            "class_distribution": class_counts.to_dict(),
        }
        
        if use_cv:
            results["cv_scores"] = cv_scores.tolist()
            results["cv_mean"] = cv_scores.mean()
        
        logger.info(f"Training results: {results}")
        
        return results
    
    def predict(self, features: pd.DataFrame) -> np.ndarray:
        """Make predictions with the trained model.
        
        Args:
            features: DataFrame with prepared features
            
        Returns:
            Array of predicted values (-1, 0, 1)
        """
        # Scale features
        X_scaled = self.scale_features(features, refit=False)
        
        # Make predictions
        try:
            return self.model.predict(X_scaled)
        except Exception as e:
            logger.error(f"Error making predictions: {e}")
            # Return neutral predictions as fallback
            return np.zeros(len(features))
    
    def predict_proba(self, features: pd.DataFrame) -> np.ndarray:
        """Make probability predictions with the trained model.
        
        Args:
            features: DataFrame with prepared features
            
        Returns:
            Array of class probabilities
        """
        # Scale features
        X_scaled = self.scale_features(features, refit=False)
        
        # Make probability predictions
        try:
            return self.model.predict_proba(X_scaled)
        except Exception as e:
            logger.error(f"Error making probability predictions: {e}")
            # Return equal probabilities as fallback
            if self.n_classes == 3:
                return np.ones((len(features), 3)) / 3
            else:
                return np.ones((len(features), 2)) / 2
    
    def _store_feature_importance(self):
        """Store feature importance if available."""
        if hasattr(self.model, "feature_importances_"):
            self.feature_importance = self.model.feature_importances_
        elif self.model_type == "logistic":
            # For logistic regression, use coefficients as feature importance
            if self.n_classes == 2:
                self.feature_importance = np.abs(self.model.coef_[0])
            else:
                # Average absolute coefficients for multi-class
                self.feature_importance = np.mean(np.abs(self.model.coef_), axis=0)
    
    def get_top_features(self, n: int = 10) -> pd.DataFrame:
        """Get the top N most important features.
        
        Args:
            n: Number of top features to return
            
        Returns:
            DataFrame with feature names and importance
        """
        if self.feature_importance is None or self.feature_names is None:
            logger.warning("Feature importance not available")
            return pd.DataFrame()
        
        # Create DataFrame with feature names and importance
        feature_df = pd.DataFrame({
            'feature': self.feature_names,
            'importance': self.feature_importance
        })
        
        # Sort by importance and get top N
        return feature_df.sort_values('importance', ascending=False).head(n)
    
    def save(self, directory: str = 'models'):
        """Save the model to a file.
        
        Args:
            directory: Directory to save the model in
        """
        # Create directory if it doesn't exist
        os.makedirs(directory, exist_ok=True)
        
        # Save model
        model_path = os.path.join(directory, f'{self.name}.joblib')
        joblib.dump(self.model, model_path)
        
        # Save scaler
        scaler_path = os.path.join(directory, f'{self.name}_scaler.joblib')
        joblib.dump(self.scaler, scaler_path)
        
        # Save metadata
        metadata = {
            'name': self.name,
            'model_type': self.model_type,
            'model_params': self.model_params,
            'n_classes': self.n_classes,
            'random_state': self.random_state,
            'feature_names': self.feature_names,
        }
        
        import json
        metadata_path = os.path.join(directory, f'{self.name}_metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=4)
        
        logger.info(f"Model saved to {model_path}")
        logger.info(f"Scaler saved to {scaler_path}")
        logger.info(f"Metadata saved to {metadata_path}")
    
    @classmethod
    def load(cls, name: str, directory: str = 'models') -> 'GBPUSDModel':
        """Load a model from a file.
        
        Args:
            name: Name of the model
            directory: Directory containing the model
            
        Returns:
            Loaded model
        """
        import json
        
        # Load metadata
        metadata_path = os.path.join(directory, f'{name}_metadata.json')
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        # Create model instance
        model = cls(
            model_type=metadata['model_type'],
            model_params=metadata['model_params'],
            name=metadata['name'],
            n_classes=metadata['n_classes'],
            random_state=metadata['random_state']
        )
        
        # Load model
        model_path = os.path.join(directory, f'{name}.joblib')
        model.model = joblib.load(model_path)
        
        # Load scaler
        scaler_path = os.path.join(directory, f'{name}_scaler.joblib')
        model.scaler = joblib.load(scaler_path)
        
        # Set feature names
        model.feature_names = metadata.get('feature_names')
        
        # Store feature importance
        model._store_feature_importance()
        
        logger.info(f"Model loaded from {model_path}")
        
        return model


def train_gbpusd_model(
    data_path: str,
    model_type: str = 'random_forest',
    timeframe: str = '4h',
    target_horizon: int = 12,
    model_params: Optional[Dict[str, Any]] = None,
    save_dir: str = 'models'
) -> GBPUSDModel:
    """Train a model for GBP/USD prediction.
    
    Args:
        data_path: Path to the data file
        model_type: Type of model to train
        timeframe: Timeframe of the data
        target_horizon: Number of periods ahead for the target
        model_params: Parameters for the model
        save_dir: Directory to save the model
        
    Returns:
        Trained model
    """
    # Load data
    if data_path.endswith('.parquet'):
        data = pd.read_parquet(data_path)
    elif data_path.endswith('.csv'):
        data = pd.read_csv(data_path, index_col=0, parse_dates=True)
    else:
        raise ValueError(f"Unsupported file format: {data_path}")
    
    logger.info(f"Loaded data with {len(data)} rows")
    
    # Create model
    model = GBPUSDModel(model_type=model_type, model_params=model_params)
    
    # Prepare features
    features = model.prepare_features(
        data,
        target_horizon=target_horizon,
        add_lag_features=True,
        create_target=True
    )
    
    logger.info(f"Prepared features with {len(features)} rows and {len(features.columns)} columns")
    
    # Train model
    target_col = f'target_{target_horizon}'
    results = model.train(
        features,
        target_col=target_col,
        test_size=0.2,
        use_cv=True,
        n_splits=5
    )
    
    # Save model
    model.save(directory=save_dir)
    
    return model


def load_and_evaluate_model(
    model_name: str,
    data_path: str,
    target_horizon: int = 12,
    directory: str = 'models'
) -> Dict[str, Any]:
    """Load and evaluate a model on test data.
    
    Args:
        model_name: Name of the model to load
        data_path: Path to the test data
        target_horizon: Number of periods ahead for the target
        directory: Directory containing the model
        
    Returns:
        Dictionary with evaluation results
    """
    # Load model
    model = GBPUSDModel.load(model_name, directory)
    
    # Load data
    if data_path.endswith('.parquet'):
        data = pd.read_parquet(data_path)
    elif data_path.endswith('.csv'):
        data = pd.read_csv(data_path, index_col=0, parse_dates=True)
    else:
        raise ValueError(f"Unsupported file format: {data_path}")
    
    # Prepare features
    features = model.prepare_features(
        data,
        target_horizon=target_horizon,
        add_lag_features=True,
        create_target=True
    )
    
    # Split features and target
    target_col = f'target_{target_horizon}'
    X = features.drop(columns=[target_col])
    y = features[target_col]
    
    # Make predictions
    y_pred = model.predict(X)
    
    # Calculate metrics
    results = {
        "accuracy": accuracy_score(y, y_pred),
        "precision": precision_score(y, y_pred, average='weighted'),
        "recall": recall_score(y, y_pred, average='weighted'),
        "f1": f1_score(y, y_pred, average='weighted'),
        "test_size": len(X),
    }
    
    logger.info(f"Evaluation results: {results}")
    
    return results


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # Example usage
    train_gbpusd_model(
        data_path='input/C_GBPUSD_4h.parquet',
        model_type='random_forest',
        timeframe='4h',
        target_horizon=12,
        save_dir='models'
    )