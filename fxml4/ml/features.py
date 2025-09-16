"""Feature engineering for machine learning.

This module provides functions for feature engineering in financial market data.
"""

import logging
import warnings
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def create_basic_technical_features(
    data: pd.DataFrame,
    indicators: Optional[List[str]] = None,
    ma_periods: Optional[List[int]] = None,
    include_original: bool = True,
    fillna: bool = True,
    add_enhanced_features: bool = True,
) -> pd.DataFrame:
    """Fallback implementation for technical indicators without pandas_ta.

    Args:
        data: Market data with OHLC columns
        indicators: List of indicator types to include
        ma_periods: List of periods for moving averages
        include_original: Whether to include original columns
        fillna: Whether to fill NaN values
        add_enhanced_features: Whether to add enhanced/composite features

    Returns:
        DataFrame with added technical features
    """
    # Make a copy of the dataframe
    df = data.copy()

    # Set default indicators and periods if not provided
    if indicators is None:
        # From FXML2: Include technical indicators, session-based, and pivot points
        indicators = [
            "sma",
            "ema",
            "rsi",
            "bollinger",
            "macd",
            "stoch",
            "atr",
            "adx",
            "zigzag",
        ]

    if ma_periods is None:
        # Using FXML2 specific periods: 5, 21, 55, 200
        ma_periods = [5, 21, 55, 200]

    # Check if required columns exist
    required_cols = ["open", "high", "low", "close"]
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        logger.warning(f"Missing required columns: {missing_cols}")
        return df

    # Moving Averages
    if "sma" in indicators:
        for period in ma_periods:
            df[f"sma_{period}"] = df["close"].rolling(window=period).mean()

    if "ema" in indicators:
        for period in ma_periods:
            df[f"ema_{period}"] = (
                df["close"].ewm(span=period, min_periods=period, adjust=False).mean()
            )

    # Relative Strength Index
    if "rsi" in indicators:
        # Calculate RSI without pandas_ta
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()

        rs = avg_gain / avg_loss
        df["rsi_14"] = 100 - (100 / (1 + rs))

    # Bollinger Bands (using params from FXML2: length=20, std=2.0)
    if "bollinger" in indicators:
        period = 20
        std_dev = 2

        df["bb_middle"] = df["close"].rolling(window=period).mean()
        df["bb_std"] = df["close"].rolling(window=period).std()
        df["bb_upper"] = df["bb_middle"] + (df["bb_std"] * std_dev)
        df["bb_lower"] = df["bb_middle"] - (df["bb_std"] * std_dev)
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"]

        # Add Bollinger Band Squeeze indicator (from FXML2)
        if add_enhanced_features:
            squeeze_window = 20
            squeeze_threshold = 0.05
            ratio = (df["bb_width"] / df["bb_middle"]).rolling(squeeze_window).mean()
            df["bb_squeeze"] = (ratio < squeeze_threshold).astype(int)

    # MACD implementation
    if "macd" in indicators:
        # MACD Implementation without TA lib
        # Using params from FXML2: fast=12, slow=26, signal=9
        fast_period = 12
        slow_period = 26
        signal_period = 9

        # Calculate MACD
        ema_fast = (
            df["close"]
            .ewm(span=fast_period, min_periods=fast_period, adjust=False)
            .mean()
        )
        ema_slow = (
            df["close"]
            .ewm(span=slow_period, min_periods=slow_period, adjust=False)
            .mean()
        )
        df["macd"] = ema_fast - ema_slow
        df["macd_signal"] = (
            df["macd"]
            .ewm(span=signal_period, min_periods=signal_period, adjust=False)
            .mean()
        )
        df["macd_hist"] = df["macd"] - df["macd_signal"]

        # Add MACD crossover signals (from FXML2)
        if add_enhanced_features:
            m = df["macd"]
            s = df["macd_signal"]
            df["macd_cross_up"] = ((m > s) & (m.shift(1) <= s.shift(1))).astype(int)
            df["macd_cross_down"] = ((m < s) & (m.shift(1) >= s.shift(1))).astype(int)
            # Add signal strength based on histogram value (from FXML2)
            df["macd_cross_strength"] = 0.0
            df.loc[df["macd_cross_up"] == 1, "macd_cross_strength"] = df.loc[
                df["macd_cross_up"] == 1, "macd_hist"
            ]
            df.loc[df["macd_cross_down"] == 1, "macd_cross_strength"] = -df.loc[
                df["macd_cross_down"] == 1, "macd_hist"
            ]

    # Stochastic Oscillator (using params from FXML2: k=14, d=3)
    if "stoch" in indicators:
        k_period = 14
        d_period = 3

        # Calculate %K
        low_min = df["low"].rolling(window=k_period).min()
        high_max = df["high"].rolling(window=k_period).max()
        df["stoch_k"] = 100 * ((df["close"] - low_min) / (high_max - low_min))

        # Calculate %D (3-period SMA of %K)
        df["stoch_d"] = df["stoch_k"].rolling(window=d_period).mean()

    # Average True Range
    if "atr" in indicators:
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()

        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)

        df["atr_14"] = true_range.rolling(window=14).mean()

    # ADX (Average Directional Index) - basic calculation
    if "adx" in indicators:
        # Prepare components for ADX calculation
        high_change = df["high"].diff()
        low_change = -df["low"].diff()

        # +DM and -DM
        plus_dm = ((high_change > low_change) & (high_change > 0)).astype(
            float
        ) * high_change
        minus_dm = ((low_change > high_change) & (low_change > 0)).astype(
            float
        ) * low_change

        # ATR (already calculated, but we'll use it here)
        atr = df.get("atr_14", true_range.rolling(window=14).mean())

        # +DI and -DI (we'll use a simplified version with smoothed DM/ATR)
        plus_di = 100 * plus_dm.rolling(window=14).mean() / atr
        minus_di = 100 * minus_dm.rolling(window=14).mean() / atr

        # Calculate DX
        dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).abs())

        # Calculate ADX (14-period smoothed average of DX)
        df["adx_14"] = dx.rolling(window=14).mean()
        df["di_plus_14"] = plus_di
        df["di_minus_14"] = minus_di

    # Add basic price features
    # Daily returns
    df["daily_return"] = df["close"].pct_change()

    # Volatility (matches FXML2)
    df["volatility_14"] = df["close"].pct_change().rolling(window=14).std() * 100

    # Add weekly change (matches FXML2)
    df["weekly_change"] = (
        (df["close"] - df["close"].shift(5 * 24)) / df["close"].shift(5 * 24) * 100
    )  # 5 days' worth of hourly data

    # Fill NA values if requested
    if fillna:
        df = (
            df.ffill().bfill()
        )  # Use new recommended methods instead of deprecated fillna(method=)

    # Add enhanced pivot-related features if requested
    if add_enhanced_features and any(
        col for col in df.columns if col.endswith(("_r1", "_s1", "_r2", "_s2"))
    ):
        # Add pivot breakout indicators
        pivot_cols = [
            col
            for col in df.columns
            if any(x in col for x in ["_r1", "_s1", "_r2", "_s2"])
        ]
        for col in pivot_cols:
            if "r1" in col:
                # Resistance breakout
                prefix = col.split("_r1")[0]
                if f"{prefix}_r1" in df.columns:
                    df[f"{prefix}_breakout_up"] = (
                        df["close"] > df[f"{prefix}_r1"]
                    ).astype(int)
            elif "s1" in col:
                # Support breakout
                prefix = col.split("_s1")[0]
                if f"{prefix}_s1" in df.columns:
                    df[f"{prefix}_breakout_down"] = (
                        df["close"] < df[f"{prefix}_s1"]
                    ).astype(int)

    # Drop original columns if not requested
    if not include_original:
        df = df.drop(columns=required_cols)

    return df


def create_technical_features(
    data: pd.DataFrame,
    indicators: Optional[List[str]] = None,
    ma_periods: Optional[List[int]] = None,
    include_original: bool = True,
    fillna: bool = True,
    add_enhanced_features: bool = True,
) -> pd.DataFrame:
    """Create technical indicators as features.

    Args:
        data: Market data with OHLC columns
        indicators: List of indicator types to include
        ma_periods: List of periods for moving averages
        include_original: Whether to include original columns
        fillna: Whether to fill NaN values
        add_enhanced_features: Whether to add enhanced/composite features

    Returns:
        DataFrame with added technical features
    """
    # Try to import pandas_ta, with a special fix for newer versions of numpy
    try:
        # First make sure NaN is defined for pandas_ta
        import numpy as np

        np.NaN = float("nan")  # Define NaN for pandas_ta compatibility
        import pandas_ta as ta
    except ImportError as e:
        # Fall back to basic indicators if pandas_ta can't be imported
        logger.warning(
            f"Using fallback technical indicators due to pandas_ta import issue: {str(e)}"
        )
        return create_basic_technical_features(
            data,
            indicators,
            ma_periods,
            include_original,
            fillna,
            add_enhanced_features,
        )
    except Exception as e:
        logger.warning(
            f"Error importing pandas_ta: {str(e)}, using fallback indicators"
        )
        return create_basic_technical_features(
            data,
            indicators,
            ma_periods,
            include_original,
            fillna,
            add_enhanced_features,
        )

    # Make a copy of the dataframe
    df = data.copy()

    # Set default indicators and periods if not provided
    if indicators is None:
        # From FXML2: Include standard indicators, plus pattern detection and session-based features
        indicators = [
            "sma",
            "ema",
            "rsi",
            "macd",
            "bollinger",
            "stoch",
            "atr",
            "adx",
            "zigzag",
            "pivot_points",
            "session_indicators",
        ]

    if ma_periods is None:
        # Using FXML2 specific periods: 5, 21, 55, 200
        ma_periods = [5, 21, 55, 200]

    # Check if required columns exist
    required_cols = ["open", "high", "low", "close"]
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        logger.warning(f"Missing required columns: {missing_cols}")
        return df

    # Moving Averages
    if "sma" in indicators:
        for period in ma_periods:
            df[f"sma_{period}"] = ta.sma(df["close"], length=period)

    if "ema" in indicators:
        for period in ma_periods:
            df[f"ema_{period}"] = ta.ema(df["close"], length=period)

    # Relative Strength Index
    if "rsi" in indicators:
        df["rsi_14"] = ta.rsi(df["close"], length=14)

    # Bollinger Bands (using params from FXML2: length=20, std=2.0)
    if "bollinger" in indicators:
        bbands = ta.bbands(df["close"], length=20, std=2)
        if not bbands.empty:
            df["bb_upper"] = bbands["BBU_20_2.0"]
            df["bb_middle"] = bbands["BBM_20_2.0"]
            df["bb_lower"] = bbands["BBL_20_2.0"]
            df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"]

            # Add Bollinger Band Squeeze indicator (from FXML2)
            if add_enhanced_features:
                squeeze_window = 20
                squeeze_threshold = 0.05
                ratio = (
                    (df["bb_width"] / df["bb_middle"]).rolling(squeeze_window).mean()
                )
                df["bb_squeeze"] = (ratio < squeeze_threshold).astype(int)

    # MACD (using params from FXML2: fast=12, slow=26, signal=9)
    if "macd" in indicators:
        macd_result = ta.macd(df["close"], fast=12, slow=26, signal=9)
        if not macd_result.empty:
            df["macd"] = macd_result["MACD_12_26_9"]
            df["macd_signal"] = macd_result["MACDs_12_26_9"]
            df["macd_hist"] = macd_result["MACDh_12_26_9"]

            # Add MACD crossover signals (from FXML2)
            if add_enhanced_features:
                m = df["macd"]
                s = df["macd_signal"]
                df["macd_cross_up"] = ((m > s) & (m.shift(1) <= s.shift(1))).astype(int)
                df["macd_cross_down"] = ((m < s) & (m.shift(1) >= s.shift(1))).astype(
                    int
                )

                # Add signal strength based on histogram value (from FXML2)
                df["macd_cross_strength"] = 0.0
                df.loc[df["macd_cross_up"] == 1, "macd_cross_strength"] = df.loc[
                    df["macd_cross_up"] == 1, "macd_hist"
                ]
                df.loc[df["macd_cross_down"] == 1, "macd_cross_strength"] = -df.loc[
                    df["macd_cross_down"] == 1, "macd_hist"
                ]

    # Stochastic Oscillator (using params from FXML2: k=14, d=3)
    if "stoch" in indicators:
        stoch = ta.stoch(df["high"], df["low"], df["close"], k=14, d=3)
        if not stoch.empty:
            df["stoch_k"] = stoch["STOCHk_14_3_3"]
            df["stoch_d"] = stoch["STOCHd_14_3_3"]

    # Average True Range
    if "atr" in indicators:
        df["atr_14"] = ta.atr(df["high"], df["low"], df["close"], length=14)

    # Average Directional Index
    if "adx" in indicators:
        adx = ta.adx(df["high"], df["low"], df["close"], length=14)
        if not adx.empty:
            df["adx_14"] = adx["ADX_14"]
            df["di_plus_14"] = adx["DMP_14"]
            df["di_minus_14"] = adx["DMN_14"]

    # Commodity Channel Index
    if "cci" in indicators:
        df["cci_20"] = ta.cci(df["high"], df["low"], df["close"], length=20)

    # Rate of Change
    if "roc" in indicators:
        df["roc_10"] = ta.roc(df["close"], length=10)

    # Percentage Price Oscillator
    if "ppo" in indicators:
        ppo = ta.ppo(df["close"], fast=12, slow=26, signal=9)
        if not ppo.empty:
            df["ppo"] = ppo["PPO_12_26_9"]
            df["ppo_signal"] = ppo["PPOs_12_26_9"]
            df["ppo_hist"] = ppo["PPOh_12_26_9"]

    # Add enhanced pivot-related features if requested
    if add_enhanced_features:
        # Add pivot breakout indicators
        pivot_cols = [
            col
            for col in df.columns
            if any(x in col for x in ["_r1", "_s1", "_r2", "_s2"])
        ]
        for col in pivot_cols:
            if "r1" in col:
                # Resistance breakout
                prefix = col.split("_r1")[0]
                if f"{prefix}_r1" in df.columns:
                    df[f"{prefix}_breakout_up"] = (
                        df["close"] > df[f"{prefix}_r1"]
                    ).astype(int)
            elif "s1" in col:
                # Support breakout
                prefix = col.split("_s1")[0]
                if f"{prefix}_s1" in df.columns:
                    df[f"{prefix}_breakout_down"] = (
                        df["close"] < df[f"{prefix}_s1"]
                    ).astype(int)

            # Add additional R2/S2 breakouts
            if "r2" in col:
                prefix = col.split("_r2")[0]
                if f"{prefix}_r2" in df.columns:
                    df[f"{prefix}_breakout_r2"] = (
                        df["close"] > df[f"{prefix}_r2"]
                    ).astype(int)
            elif "s2" in col:
                prefix = col.split("_s2")[0]
                if f"{prefix}_s2" in df.columns:
                    df[f"{prefix}_breakout_s2"] = (
                        df["close"] < df[f"{prefix}_s2"]
                    ).astype(int)

        # Add confluence indicators (combining multiple signals)
        # This follows FXML2's advanced_pivot_and_confluence function
        if all(col in df.columns for col in ["bb_squeeze", "macd_cross_up", "close"]):
            for prefix in ["weekly", "daily", "london", "newyork", "tokyo", "sydney"]:
                r1_col = f"{prefix}_r1"
                s1_col = f"{prefix}_s1"

                if r1_col in df.columns and s1_col in df.columns:
                    # Bullish confluence: BB Squeeze + MACD Cross Up + Price > R1
                    df[f"{prefix}_confluence_bull"] = (
                        (df["bb_squeeze"] == 1)
                        & (df["macd_cross_up"] == 1)
                        & (df["close"] > df[r1_col])
                    ).astype(int)

                    # Bearish confluence: BB Squeeze + MACD Cross Down + Price < S1
                    df[f"{prefix}_confluence_bear"] = (
                        (df["bb_squeeze"] == 1)
                        & (df["macd_cross_down"] == 1)
                        & (df["close"] < df[s1_col])
                    ).astype(int)

    # Fill NA values if requested
    if fillna:
        df = (
            df.ffill().bfill()
        )  # Use new recommended methods instead of deprecated fillna(method=)

    # Drop original columns if not requested
    if not include_original:
        df = df.drop(columns=required_cols)

    return df


def add_lagged_features(
    data: pd.DataFrame,
    columns: List[str] = None,
    lags: List[int] = None,
    include_returns: bool = True,
) -> pd.DataFrame:
    """Add lagged features to the data.

    Args:
        data: DataFrame with features
        columns: Columns to create lags for (defaults to key indicators if None)
        lags: List of lag periods (defaults to [1, 2, 5] from FXML2 if None)
        include_returns: Whether to include returns

    Returns:
        DataFrame with added lagged features
    """
    df = data.copy()

    # Set default columns if not provided (from FXML2)
    if columns is None:
        columns = ["close", "bb_width", "macd", "stoch_k", "rsi_14"]
        # Use only columns that exist in the dataframe
        columns = [col for col in columns if col in df.columns]

    # Set default lags if not provided (from FXML2)
    if lags is None:
        lags = [1, 2, 5]  # FXML2 standard

    # Check if all columns exist
    missing_cols = [col for col in columns if col not in df.columns]
    if missing_cols:
        logger.warning(f"Missing columns for lagging: {missing_cols}")
        # Remove missing columns from the list
        columns = [col for col in columns if col in df.columns]

    # Create lagged features
    for col in columns:
        for lag in lags:
            df[f"{col}_lag_{lag}"] = df[col].shift(lag)

            # Add returns if requested
            if include_returns and "close" in col:
                df[f"return_{lag}"] = df["close"].pct_change(lag)

    return df


def create_target_labels(
    data: pd.DataFrame,
    method: str = "fixed_threshold",
    horizon: int = 10,
    threshold: float = 0.001,
    n_classes: int = 3,
    volatility_adjusted: bool = False,
    trend_adjusted: bool = False,
    volatility_window: int = 20,
    volatility_multiplier: float = 1.0,
    trend_window: int = 100,
) -> pd.DataFrame:
    """Create target labels for supervised learning using methods from FXML2.

    CRITICAL: This function creates labels using future data, which is appropriate for
    training but requires careful handling during backtesting to prevent look-ahead bias.

    WARNING: The target labels created here use shift(-horizon) which looks into the future.
    This is ONLY valid for:
    1. Training data preparation (where we know future outcomes)
    2. Backtesting where the target at time t uses data at time t+horizon

    DO NOT use these targets for real-time prediction without proper temporal validation.

    Args:
        data: DataFrame with close prices
        method: Method for creating labels
            - 'fixed_threshold': Use fixed threshold for returns
            - 'quantile': Use quantile-based thresholds
            - 'mean_std': Use mean and std for thresholds
            - 'volatility_adjusted': Adjust threshold based on local volatility (from FXML2)
            - 'dynamic_quantile': Use rolling quantile-based thresholds (from FXML2)
        horizon: Number of periods ahead for prediction
        threshold: Threshold for classification (fixed threshold method)
        n_classes: Number of classes (2 or 3)
        volatility_adjusted: Whether to adjust thresholds based on volatility
        trend_adjusted: Whether to adjust thresholds based on market trend
        volatility_window: Window size for volatility calculation
        volatility_multiplier: Multiplier to apply to volatility for thresholding
        trend_window: Window size for trend calculation

    Returns:
        DataFrame with added target column
    """
    df = data.copy()

    # Check if close column exists
    if "close" not in df.columns:
        logger.error("No 'close' column found for creating target labels")
        return df

    # TEMPORAL VALIDATION: Calculate future return using proper indexing
    # This INTENTIONALLY uses future data for training purposes
    # The last 'horizon' rows will have NaN targets, which is correct
    future_return = df["close"].shift(-horizon) / df["close"] - 1

    # Add warning about temporal alignment
    logger.warning(
        f"Target labels use future data with horizon={horizon}. "
        f"Last {horizon} rows will have NaN targets. "
        f"Ensure proper temporal splitting in train/test."
    )

    # Handle FXML2 advanced labeling methods
    if method == "volatility_adjusted" or volatility_adjusted:
        # Calculate rolling volatility (FXML2 approach)
        returns = df["close"].pct_change()
        volatility = returns.rolling(window=volatility_window).std()
        df[f"volatility_{volatility_window}"] = volatility

        # Create volatility-adjusted thresholds
        upper_thresholds = volatility * volatility_multiplier
        lower_thresholds = -volatility * volatility_multiplier

        # Adjust thresholds by trend if requested
        if trend_adjusted:
            # Calculate trend using moving average (FXML2 approach)
            trend = (
                df["close"]
                .rolling(window=trend_window)
                .mean()
                .pct_change(trend_window // 2)
            )
            max_trend = trend.abs().quantile(
                0.95
            )  # Use 95th percentile to avoid extreme values
            normalized_trend = trend / max_trend
            normalized_trend = np.clip(normalized_trend, -1, 1)  # Ensure range [-1, 1]

            # Store trend information
            df[f"trend_{trend_window}"] = normalized_trend

            # Adjust thresholds - lower threshold in uptrend, higher threshold in downtrend
            trend_adjustment = normalized_trend * volatility * 0.3  # 30% adjustment
            upper_thresholds = upper_thresholds - trend_adjustment
            lower_thresholds = lower_thresholds + trend_adjustment

        # Generate labels
        if n_classes == 3:
            target = np.zeros(len(df))
            for i in range(len(future_return)):
                if pd.isna(upper_thresholds.iloc[i]) or pd.isna(future_return.iloc[i]):
                    target[i] = np.nan
                elif future_return.iloc[i] > upper_thresholds.iloc[i]:
                    target[i] = 1
                elif future_return.iloc[i] < lower_thresholds.iloc[i]:
                    target[i] = -1
                else:
                    target[i] = 0
        else:  # 2 classes
            target = np.where(future_return > 0, 1, 0)

        # Add threshold columns
        df[f"upper_threshold_{horizon}"] = upper_thresholds
        df[f"lower_threshold_{horizon}"] = lower_thresholds

    elif method == "dynamic_quantile":  # FXML2 advanced method
        # Use a larger window for stable quantiles
        window = volatility_window * 5

        if n_classes == 3:
            # Calculate rolling quantiles
            upper_q = 0.75  # 75th percentile
            lower_q = 0.25  # 25th percentile

            # Calculate rolling quantiles of future returns
            upper_rolling = future_return.rolling(
                window=window, min_periods=window // 2
            ).quantile(upper_q)
            lower_rolling = future_return.rolling(
                window=window, min_periods=window // 2
            ).quantile(lower_q)

            # Adjust by trend if requested
            if trend_adjusted:
                # Calculate trend
                trend = (
                    df["close"]
                    .rolling(window=trend_window)
                    .mean()
                    .pct_change(trend_window // 2)
                )
                max_trend = trend.abs().quantile(0.95)
                normalized_trend = trend / max_trend
                normalized_trend = np.clip(normalized_trend, -1, 1)

                # Store trend
                df[f"trend_{trend_window}"] = normalized_trend

                # Calculate adjustment
                volatility = future_return.rolling(window=volatility_window).std()
                trend_adjustment = normalized_trend * volatility * 0.3

                # Adjust thresholds
                upper_rolling = upper_rolling - trend_adjustment
                lower_rolling = lower_rolling + trend_adjustment

            # Generate labels
            target = np.zeros(len(future_return))
            for i in range(len(future_return)):
                if pd.isna(upper_rolling.iloc[i]) or pd.isna(future_return.iloc[i]):
                    target[i] = np.nan
                elif future_return.iloc[i] > upper_rolling.iloc[i]:
                    target[i] = 1
                elif future_return.iloc[i] < lower_rolling.iloc[i]:
                    target[i] = -1
                else:
                    target[i] = 0

            # Add threshold columns
            df[f"upper_threshold_{horizon}"] = upper_rolling
            df[f"lower_threshold_{horizon}"] = lower_rolling
        else:  # 2 classes
            # For binary classification, use rolling median
            rolling_median = future_return.rolling(
                window=window, min_periods=window // 2
            ).median()
            target = np.zeros(len(future_return))
            for i in range(len(future_return)):
                if pd.isna(rolling_median.iloc[i]) or pd.isna(future_return.iloc[i]):
                    target[i] = np.nan
                elif future_return.iloc[i] > rolling_median.iloc[i]:
                    target[i] = 1
                else:
                    target[i] = 0

            # Add threshold column
            df[f"threshold_{horizon}"] = rolling_median

    # Standard labeling methods
    elif method == "fixed_threshold":
        if n_classes == 2:
            # Binary classification (up/down)
            target = np.where(future_return > threshold, 1, 0)
        else:
            # Ternary classification (up/neutral/down)
            target = np.zeros(len(df))
            target[future_return > threshold] = 1
            target[future_return < -threshold] = -1

    elif method == "quantile":
        if n_classes == 2:
            # Binary classification (up/down)
            median = future_return.median()
            target = np.where(future_return > median, 1, 0)
        else:
            # Ternary classification (up/neutral/down)
            q_low = future_return.quantile(0.33)
            q_high = future_return.quantile(0.67)
            target = np.zeros(len(df))
            target[future_return > q_high] = 1
            target[future_return < q_low] = -1

    elif method == "mean_std":
        mean = future_return.mean()
        std = future_return.std()

        if n_classes == 2:
            # Binary classification (up/down)
            target = np.where(future_return > mean, 1, 0)
        else:
            # Ternary classification (up/neutral/down)
            target = np.zeros(len(df))
            target[future_return > mean + 0.5 * std] = 1
            target[future_return < mean - 0.5 * std] = -1

    else:
        logger.error(f"Unknown labeling method: {method}")
        return df

    # Add target column
    df[f"target_{horizon}"] = target

    # Add future return column
    df[f"future_return_{horizon}"] = future_return

    return df


def scale_features(
    data: pd.DataFrame,
    scaler_object: Optional[object] = None,
    exclude_cols: Optional[List[str]] = None,
    refit: bool = True,
) -> Tuple[pd.DataFrame, object]:
    """Scale features using MinMaxScaler.

    Args:
        data: DataFrame with features
        scaler_object: Pre-fitted scaler (optional)
        exclude_cols: Columns to exclude from scaling
        refit: Whether to fit the scaler on this data

    Returns:
        Tuple of (scaled DataFrame, scaler object)
    """
    from sklearn.preprocessing import MinMaxScaler

    # Make a copy
    df = data.copy()

    # Identify columns to scale
    if exclude_cols is None:
        exclude_cols = []

    # Add any target columns to exclude_cols
    target_cols = [col for col in df.columns if col.startswith("target_")]
    exclude_cols.extend(target_cols)

    # Columns to scale
    scale_cols = [col for col in df.columns if col not in exclude_cols]

    # Create or use provided scaler
    if scaler_object is None:
        scaler = MinMaxScaler()
    else:
        scaler = scaler_object

    # Handle infinite values
    df.replace([np.inf, -np.inf], np.nan, inplace=True)

    # Fill NA values with column median
    for col in scale_cols:
        if df[col].isna().any():
            median_val = df[col].median()
            if pd.isna(median_val):  # If median is also NaN (all values are NaN)
                df[col] = df[col].fillna(0)
            else:
                df[col] = df[col].fillna(median_val)

    # Scale features
    if refit:
        scaled_values = scaler.fit_transform(df[scale_cols])
    else:
        scaled_values = scaler.transform(df[scale_cols])

    # Replace original values with scaled values
    for i, col in enumerate(scale_cols):
        df[col] = scaled_values[:, i]

    return df, scaler


def validate_temporal_integrity(
    data: pd.DataFrame, feature_cols: List[str], target_col: str, horizon: int = 10
) -> Dict[str, bool]:
    """Validate that features don't contain look-ahead bias.

    This function performs several checks to ensure temporal integrity:
    1. Check that feature calculations don't use future data
    2. Validate target alignment with prediction horizon
    3. Check for any NaN patterns that might indicate data leakage

    Args:
        data: DataFrame with features and targets
        feature_cols: List of feature column names to validate
        target_col: Target column name
        horizon: Prediction horizon used for target creation

    Returns:
        Dictionary with validation results
    """
    validation_results = {
        "temporal_integrity_passed": True,
        "issues_found": [],
        "warnings": [],
    }

    try:
        # Check 1: Verify target alignment
        if target_col in data.columns:
            # Count NaN values in target - should be exactly 'horizon' at the end
            target_nan_count = data[target_col].isna().sum()
            expected_nan_count = horizon

            if target_nan_count != expected_nan_count:
                validation_results["issues_found"].append(
                    f"Target NaN count ({target_nan_count}) doesn't match expected ({expected_nan_count})"
                )
                validation_results["temporal_integrity_passed"] = False

            # Check that NaNs are at the end
            last_valid_idx = data[target_col].last_valid_index()
            if last_valid_idx is not None:
                expected_last_valid = len(data) - horizon - 1
                actual_last_valid = data.index.get_loc(last_valid_idx)

                if (
                    abs(actual_last_valid - expected_last_valid) > 1
                ):  # Allow 1 position tolerance
                    validation_results["warnings"].append(
                        f"Target NaN pattern may be incorrect. Last valid index: {actual_last_valid}, expected: {expected_last_valid}"
                    )

        # Check 2: Feature validation
        for col in feature_cols:
            if col not in data.columns:
                continue

            # Check for suspicious patterns (e.g., too many NaNs at the beginning)
            first_valid_idx = data[col].first_valid_index()
            if first_valid_idx is not None:
                first_valid_pos = data.index.get_loc(first_valid_idx)
                if first_valid_pos > len(data) * 0.2:  # More than 20% NaN at start
                    validation_results["warnings"].append(
                        f"Feature '{col}' has late start (position {first_valid_pos}), check calculation window"
                    )

        # Check 3: Correlation analysis between features and future data
        # This is a more advanced check to detect subtle look-ahead bias
        if len(data) > horizon * 2:
            for col in feature_cols[
                :5
            ]:  # Check first 5 features to avoid performance issues
                if col not in data.columns:
                    continue

                try:
                    # Compare feature at time t with price at time t+horizon
                    feature_current = data[col].iloc[:-horizon]
                    price_future = data["close"].iloc[horizon:]

                    if (
                        len(feature_current) == len(price_future)
                        and len(feature_current) > 0
                    ):
                        # Calculate correlation
                        corr = np.corrcoef(
                            feature_current.dropna(),
                            price_future.iloc[: len(feature_current.dropna())],
                        )[0, 1]

                        # Suspiciously high correlation might indicate look-ahead bias
                        if abs(corr) > 0.95:
                            validation_results["warnings"].append(
                                f"Feature '{col}' has very high correlation ({corr:.3f}) with future prices"
                            )
                except Exception as e:
                    validation_results["warnings"].append(
                        f"Could not validate correlation for feature '{col}': {str(e)}"
                    )

    except Exception as e:
        validation_results["issues_found"].append(f"Validation error: {str(e)}")
        validation_results["temporal_integrity_passed"] = False

    return validation_results


def create_train_test_split(
    data: pd.DataFrame,
    target_col: str,
    train_size: float = 0.7,
    val_size: float = 0.15,
    shuffle: bool = False,
    random_state: int = 42,
) -> Dict[str, pd.DataFrame]:
    """Create train/validation/test split for time series data.

    Args:
        data: DataFrame with features and target
        target_col: Name of target column
        train_size: Fraction of data for training
        val_size: Fraction of data for validation
        shuffle: Whether to shuffle the data
        random_state: Random state for reproducibility

    Returns:
        Dictionary with X_train, y_train, X_val, y_val, X_test, y_test
    """
    from sklearn.model_selection import train_test_split

    # Check if target column exists
    if target_col not in data.columns:
        logger.error(f"Target column '{target_col}' not found")
        return {}

    # Split features and target
    X = data.drop(columns=[target_col])
    y = data[target_col]

    # Calculate test size
    test_size = 1.0 - train_size - val_size

    if shuffle:
        # Shuffle and split
        X_train_val, X_test, y_train_val, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state
        )

        # Split train_val into train and validation
        val_size_adjusted = val_size / (train_size + val_size)
        X_train, X_val, y_train, y_val = train_test_split(
            X_train_val,
            y_train_val,
            test_size=val_size_adjusted,
            random_state=random_state,
        )
    else:
        # Time-ordered split
        train_end = int(len(data) * train_size)
        val_end = int(len(data) * (train_size + val_size))

        X_train = X.iloc[:train_end]
        y_train = y.iloc[:train_end]

        X_val = X.iloc[train_end:val_end]
        y_val = y.iloc[train_end:val_end]

        X_test = X.iloc[val_end:]
        y_test = y.iloc[val_end:]

    return {
        "X_train": X_train,
        "y_train": y_train,
        "X_val": X_val,
        "y_val": y_val,
        "X_test": X_test,
        "y_test": y_test,
    }


def select_features_random_forest(
    X: pd.DataFrame,
    y: pd.Series,
    k: int = 10,
    n_estimators: int = 100,
    random_state: int = 42,
    plot: bool = False,
) -> Tuple[pd.DataFrame, List[str]]:
    """Select features using Random Forest feature importance.

    Args:
        X: Feature DataFrame
        y: Target series
        k: Number of features to select
        n_estimators: Number of trees in the forest
        random_state: Random state for reproducibility
        plot: Whether to plot feature importance

    Returns:
        Tuple of (DataFrame with selected features, list of feature names)
    """
    import matplotlib.pyplot as plt
    from sklearn.ensemble import RandomForestClassifier

    # Create and fit Random Forest
    rf = RandomForestClassifier(n_estimators=n_estimators, random_state=random_state)
    rf.fit(X, y)

    # Get feature importance
    feature_importance = rf.feature_importances_

    # Create DataFrame with feature names and importance
    importance_df = pd.DataFrame(
        {"feature": X.columns, "importance": feature_importance}
    )

    # Sort by importance
    importance_df = importance_df.sort_values("importance", ascending=False)

    # Plot if requested
    if plot:
        plt.figure(figsize=(12, 8))

        # Plot top k features
        plt.barh(importance_df["feature"][:k], importance_df["importance"][:k])
        plt.xlabel("Importance")
        plt.ylabel("Feature")
        plt.title(f"Top {k} Features by Importance")
        plt.tight_layout()
        plt.show()

    # Select top k features
    selected_features = importance_df["feature"][:k].tolist()

    return X[selected_features], selected_features


def calculate_weekly_pivot_points(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate weekly pivot points based on weekly data, then forward-fill onto the original index.

    This function resamples data to weekly (Sunday-based), calculates pivot points, and
    then maps these values back to the original data index, creating features that indicate
    distance to various pivot levels.

    Args:
        df: DataFrame with OHLC price data

    Returns:
        DataFrame with added pivot point columns:
        - PP: Pivot Point
        - R1, R2, R3: Resistance levels
        - S1, S2, S3: Support levels
        - distance_to_PP, distance_to_R1, etc.: Distance from current price to pivot levels (%)
        - pivot_breakout_up, pivot_breakout_down: Breakout indicators (from FXML2)
    """
    logger.info("Calculating weekly pivot points")

    # Make a copy of the dataframe
    result_df = df.copy()

    # Check if required columns exist
    required_cols = ["high", "low", "close"]
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        logger.warning(f"Missing required columns for pivot points: {missing_cols}")
        return df

    # Resample to weekly data (Sunday-based)
    df_weekly = df.resample("W-SUN", closed="right", label="right").agg(
        {"high": "max", "low": "min", "close": "last"}
    )

    # Calculate pivot points
    df_weekly["PP"] = (df_weekly["high"] + df_weekly["low"] + df_weekly["close"]) / 3
    df_weekly["R1"] = 2 * df_weekly["PP"] - df_weekly["low"]
    df_weekly["S1"] = 2 * df_weekly["PP"] - df_weekly["high"]
    df_weekly["R2"] = df_weekly["PP"] + (df_weekly["high"] - df_weekly["low"])
    df_weekly["S2"] = df_weekly["PP"] - (df_weekly["high"] - df_weekly["low"])
    df_weekly["R3"] = df_weekly["high"] + 2 * (df_weekly["PP"] - df_weekly["low"])
    df_weekly["S3"] = df_weekly["low"] - 2 * (df_weekly["high"] - df_weekly["PP"])

    # Forward fill weekly pivot values across the original index
    # We only keep the pivot columns
    pivot_cols = ["PP", "R1", "S1", "R2", "S2", "R3", "S3"]
    df_weekly = df_weekly[pivot_cols].reindex(df.index, method="ffill")

    # Add pivot columns to the result dataframe
    for col in pivot_cols:
        result_df[col] = df_weekly[col]

    # Calculate distance to pivot points as percentage of current price
    for col in pivot_cols:
        result_df[f"distance_to_{col}"] = (
            result_df[col] / result_df["close"] - 1
        ) * 100

    # Calculate additional features: pivot breakouts
    result_df["above_R1"] = (result_df["close"] > result_df["R1"]).astype(int)
    result_df["below_S1"] = (result_df["close"] < result_df["S1"]).astype(int)
    result_df["between_S1_R1"] = (
        (result_df["close"] >= result_df["S1"])
        & (result_df["close"] <= result_df["R1"])
    ).astype(int)

    # Calculate if price is near a pivot point (within 0.1%)
    for col in pivot_cols:
        result_df[f"near_{col}"] = (
            abs(result_df["close"] - result_df[col]) / result_df["close"] < 0.001
        ).astype(int)

    # Add FXML2 specific pivot breakout indicators
    # Pivot breakout indicators (track if price breaks R1/S1 levels)
    result_df["close_prev"] = result_df["close"].shift(1)

    # Upward breakout: Price moves from below R1 to above R1
    result_df["pivot_breakout_up"] = (
        (result_df["close"] > result_df["R1"])
        & (result_df["close_prev"] <= result_df["R1"])
    ).astype(int)

    # Downward breakout: Price moves from above S1 to below S1
    result_df["pivot_breakout_down"] = (
        (result_df["close"] < result_df["S1"])
        & (result_df["close_prev"] >= result_df["S1"])
    ).astype(int)

    # Additional R2/S2 breakouts (from FXML2)
    result_df["pivot_breakout_r2"] = (
        (result_df["close"] > result_df["R2"])
        & (result_df["close_prev"] <= result_df["R2"])
    ).astype(int)

    result_df["pivot_breakout_s2"] = (
        (result_df["close"] < result_df["S2"])
        & (result_df["close_prev"] >= result_df["S2"])
    ).astype(int)

    # Clean up temporary columns
    result_df.drop(["close_prev"], axis=1, inplace=True, errors="ignore")

    logger.info("Weekly pivot points calculated and mapped to data index")
    return result_df


def identify_trading_sessions(df: pd.DataFrame) -> pd.DataFrame:
    """Identify major forex trading sessions and their overlaps.

    Args:
        df: DataFrame with datetime index

    Returns:
        DataFrame with added session and overlap columns
    """
    # Make a copy to avoid modifying the input
    result_df = df.copy()

    # Ensure index is timezone aware
    if result_df.index.tz is None:
        logger.info("Converting index to UTC timezone")
        result_df.index = pd.to_datetime(result_df.index, utc=True)

    # Extract hour from index (in UTC)
    hours = result_df.index.hour

    # Define session hours (UTC)
    # From FXML2: London (8-17), New York (13-22), Tokyo (0-9), Sydney (21-6)
    is_london = ((hours >= 8) & (hours < 17)).astype(int)
    is_newyork = ((hours >= 13) & (hours < 22)).astype(int)
    is_tokyo = ((hours >= 0) & (hours < 9)).astype(int)
    is_sydney = ((hours >= 21) | (hours < 6)).astype(int)

    # Add session columns
    result_df["is_london_session"] = is_london
    result_df["is_newyork_session"] = is_newyork
    result_df["is_tokyo_session"] = is_tokyo
    result_df["is_sydney_session"] = is_sydney

    # Identify session overlaps
    result_df["is_london_ny_overlap"] = (is_london & is_newyork).astype(int)
    result_df["is_tokyo_london_overlap"] = (is_tokyo & is_london).astype(int)
    result_df["is_sydney_tokyo_overlap"] = (is_sydney & is_tokyo).astype(int)

    # Calculate session time distances (in hours)
    for session, (start_hour, end_hour) in [
        ("london", (8, 17)),
        ("newyork", (13, 22)),
        ("tokyo", (0, 9)),
        ("sydney", (21, 6)),
    ]:
        # Calculate today's session open and close times
        date_str = result_df.index.strftime("%Y-%m-%d")
        if start_hour < end_hour:
            # Normal case (e.g., London 8-17)
            open_times = pd.to_datetime(
                date_str + " " + f"{start_hour:02d}:00:00", utc=True
            )
            close_times = pd.to_datetime(
                date_str + " " + f"{end_hour:02d}:00:00", utc=True
            )
        else:
            # Overnight case (e.g., Sydney 21-6)
            open_times = pd.to_datetime(
                date_str + " " + f"{start_hour:02d}:00:00", utc=True
            )

            # For close time, use next day
            next_day = (
                pd.to_datetime(date_str, utc=True) + pd.Timedelta(days=1)
            ).strftime("%Y-%m-%d")
            close_times = pd.to_datetime(
                next_day + " " + f"{end_hour:02d}:00:00", utc=True
            )

        # Calculate time differences in hours
        dist_to_open = abs((result_df.index - open_times).total_seconds() / 3600)
        dist_to_close = abs((result_df.index - close_times).total_seconds() / 3600)

        # Add to result DataFrame
        result_df[f"dist_{session}_open"] = dist_to_open
        result_df[f"dist_{session}_close"] = dist_to_close

    logger.info("Added trading session identification and time distance features")
    return result_df


def calculate_session_pivot_levels(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate session-specific pivot levels for major forex trading sessions.

    Args:
        df: DataFrame with OHLC data and session columns

    Returns:
        DataFrame with additional pivot columns for each session (London, NY, Tokyo, Sydney)
    """
    # Ensure we have session columns
    if "is_london_session" not in df.columns:
        df = identify_trading_sessions(df)

    # Make a copy to avoid modifying the input
    result_df = df.copy()

    # Check required columns
    required_cols = ["open", "high", "low", "close"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        logger.warning(f"Missing required columns for session pivots: {missing_cols}")
        return df

    # Calculate pivot points for each session
    for session in ["london", "newyork", "tokyo", "sydney"]:
        session_col = f"is_{session}_session"
        if session_col not in result_df.columns:
            continue

        # Get session boundaries
        session_changes = result_df[session_col].diff()
        session_starts = result_df[session_changes == 1].index

        # Skip if no session changes
        if len(session_starts) < 2:
            continue

        # For each session start, calculate pivot levels for the previous session
        for i, start_idx in enumerate(session_starts):
            if i == 0:
                # Skip first session as we don't have previous data
                continue

            # Get previous session data
            prev_start = session_starts[i - 1]
            prev_session = result_df.loc[prev_start:start_idx][
                result_df[session_col] == 1
            ]

            if prev_session.empty:
                continue

            # Calculate pivot levels
            high = prev_session["high"].max()
            low = prev_session["low"].min()
            close = prev_session["close"].iloc[-1]

            pp = (high + low + close) / 3
            r1 = 2 * pp - low
            s1 = 2 * pp - high
            r2 = pp + (high - low)
            s2 = pp - (high - low)
            r3 = high + 2 * (pp - low)
            s3 = low - 2 * (high - pp)

            # Column names for this session
            s_pp = f"{session}_pp"
            s_r1 = f"{session}_r1"
            s_r2 = f"{session}_r2"
            s_r3 = f"{session}_r3"
            s_s1 = f"{session}_s1"
            s_s2 = f"{session}_s2"
            s_s3 = f"{session}_s3"

            # Ensure columns exist
            for col in [s_pp, s_r1, s_r2, s_r3, s_s1, s_s2, s_s3]:
                if col not in result_df.columns:
                    result_df[col] = np.nan

            # Set pivot levels for the current session
            next_session = result_df.loc[start_idx:][result_df[session_col] == 1]
            if not next_session.empty:
                current_end = next_session.index[-1]
                result_df.loc[start_idx:current_end, s_pp] = pp
                result_df.loc[start_idx:current_end, s_r1] = r1
                result_df.loc[start_idx:current_end, s_r2] = r2
                result_df.loc[start_idx:current_end, s_r3] = r3
                result_df.loc[start_idx:current_end, s_s1] = s1
                result_df.loc[start_idx:current_end, s_s2] = s2
                result_df.loc[start_idx:current_end, s_s3] = s3

    # Also add daily pivot points as a fallback
    # Resample to daily data
    df_daily = (
        df.resample("D").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    )

    # Calculate pivot points for each day
    df_daily["daily_pp"] = (df_daily["high"] + df_daily["low"] + df_daily["close"]) / 3
    df_daily["daily_r1"] = 2 * df_daily["daily_pp"] - df_daily["low"]
    df_daily["daily_s1"] = 2 * df_daily["daily_pp"] - df_daily["high"]
    df_daily["daily_r2"] = df_daily["daily_pp"] + (df_daily["high"] - df_daily["low"])
    df_daily["daily_s2"] = df_daily["daily_pp"] - (df_daily["high"] - df_daily["low"])
    df_daily["daily_r3"] = df_daily["high"] + 2 * (
        df_daily["daily_pp"] - df_daily["low"]
    )
    df_daily["daily_s3"] = df_daily["low"] - 2 * (
        df_daily["high"] - df_daily["daily_pp"]
    )

    # Forward fill to original index
    pivot_cols = [
        "daily_pp",
        "daily_r1",
        "daily_s1",
        "daily_r2",
        "daily_s2",
        "daily_r3",
        "daily_s3",
    ]
    df_daily = df_daily[pivot_cols].reindex(df.index, method="ffill")

    # Add to result dataframe
    for col in pivot_cols:
        result_df[col] = df_daily[col]

    # Calculate distance to daily pivot points
    for col in pivot_cols:
        result_df[f"distance_to_{col}"] = (
            result_df[col] / result_df["close"] - 1
        ) * 100

    logger.info("Session and daily pivot points calculated")
    return result_df
