#!/usr/bin/env python
"""Exogenous variable analysis for forex prediction - treating each symbol as endogenous."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import os
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

import json

import requests
import statsmodels.api as sm

# API libraries
from fredapi import Fred
from sklearn.ensemble import RandomForestRegressor
from sklearn.feature_selection import SelectKBest, f_regression, mutual_info_regression
from sklearn.linear_model import LassoCV, RidgeCV

# Statistical and ML libraries
from sklearn.preprocessing import StandardScaler
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.tsa.stattools import grangercausalitytests


class ExogenousVariableAnalyzer:
    """Analyze each forex pair using all other variables as exogenous predictors."""

    def __init__(self):
        # API keys
        self.fred_key = os.getenv("FRED_API_KEY", "5dfb1a7abe234caa5831f1a180a1bf1d")
        self.alpha_key = os.getenv("ALPHA_VANTAGE_API_KEY", "V10FRLTU9WKTQMD9")
        self.polygon_key = os.getenv(
            "POLYGON_API_KEY", "6VNaiPLmpdAft7A36nsKQptPEdsFDs2p"
        )

        # Initialize FRED
        self.fred = Fred(api_key=self.fred_key)

        # Define all exogenous variables
        self.exogenous_variables = {
            # Other forex pairs (will be added dynamically)
            "forex_pairs": [],
            # Dollar indices
            "dollar_indices": {
                "DXY": "DTWEXAFEGS",
                "DXY_BROAD": "DTWEXBGS",
                "DXY_EM": "DTWEXEMEGS",  # Emerging markets
            },
            # Interest rates and yield curve
            "interest_rates": {
                "FED_RATE": "DFF",
                "US_2Y": "DGS2",
                "US_5Y": "DGS5",
                "US_10Y": "DGS10",
                "US_30Y": "DGS30",
                "YIELD_CURVE_10Y2Y": None,  # Calculate: 10Y - 2Y
                "YIELD_CURVE_30Y5Y": None,  # Calculate: 30Y - 5Y
                "TED_SPREAD": "TEDRATE",
                "REAL_RATES": "DFII10",  # 10Y TIPS
            },
            # Volatility indices
            "volatility": {
                "VIX": "VIXCLS",
                "VXN": "VXNCLS",  # NASDAQ volatility
                "MOVE": "BAMLM0A0",  # Bond volatility
                "VXEEM": "VXEEMCLS",  # EM volatility
                "GVZ": "GVZCLS",  # Gold volatility
            },
            # Economic indicators
            "economic": {
                "US_CPI": "CPIAUCSL",
                "US_PPI": "PPIACO",
                "US_GDP": "GDP",
                "US_UNEMPLOYMENT": "UNRATE",
                "US_NFP": "PAYEMS",
                "US_RETAIL": "RSAFS",
                "US_INDUSTRIAL": "INDPRO",
                "US_CONSUMER_CONF": "UMCSENT",
                "US_PMI_MFG": "MANEMP",  # Manufacturing employment proxy
                "US_HOUSING": "HOUST",
            },
            # Commodities
            "commodities": {
                "GOLD": "GOLDAMGBD228NLBM",
                "SILVER": "SLVPRUSD",
                "OIL_WTI": "DCOILWTICO",
                "OIL_BRENT": "DCOILBRENTEU",
                "COPPER": "PCOPPUSDM",
                "NATGAS": "DHHNGSP",
                "WHEAT": "PWHEAMTUSDM",
                "CORN": "PMAIZMTUSDM",
            },
            # Stock indices (would need separate data source)
            "equity_indices": {
                "SPX": "SP500",
                "NDX": "NASDAQCOM",
                "DJI": "DJIA",
                "RUT": "RUT",  # Russell 2000
                "EEM": None,  # Emerging markets ETF
                "EFA": None,  # Developed markets ETF
            },
            # Credit and funding
            "credit": {
                "HY_SPREAD": "BAMLH0A0HYM2",  # High yield spread
                "IG_SPREAD": "BAMLC0A0CM",  # Investment grade spread
                "LIBOR_3M": "USD3MTD156N",
                "SOFR": "SOFR",
                "COMMERCIAL_PAPER": "DCPN3M",
            },
        }

        # Lag configurations for different variable types
        self.lag_config = {
            "forex_pairs": [1, 2, 3, 5, 10],  # Multiple lags for other currencies
            "dollar_indices": [1, 2, 5],
            "interest_rates": [1, 5, 20],  # Slower moving
            "volatility": [1, 2, 3],  # Fast moving
            "economic": [1, 5, 20],  # Monthly data, use longer lags
            "commodities": [1, 2, 5, 10],
            "equity_indices": [1, 2, 5],
            "credit": [1, 5, 10],
        }

    def fetch_all_exogenous_data(
        self, forex_symbols: List[str], start_date: str, end_date: str
    ) -> pd.DataFrame:
        """Fetch all exogenous variables data."""
        print("Fetching comprehensive exogenous data...")

        all_data = {}

        # 1. Fetch FRED data
        for category, variables in self.exogenous_variables.items():
            if category == "forex_pairs":
                continue  # Handle separately

            if isinstance(variables, dict):
                for name, fred_id in variables.items():
                    if fred_id:  # Skip calculated fields
                        try:
                            data = self.fred.get_series(
                                fred_id,
                                observation_start=start_date,
                                observation_end=end_date,
                            )
                            if not data.empty:
                                all_data[name] = data
                                print(f"  ✅ {name}")
                        except Exception as e:
                            print(f"  ❌ {name}: {str(e)[:50]}")

        # 2. Calculate derived indicators
        if "US_2Y" in all_data and "US_10Y" in all_data:
            all_data["YIELD_CURVE_10Y2Y"] = all_data["US_10Y"] - all_data["US_2Y"]

        if "US_5Y" in all_data and "US_30Y" in all_data:
            all_data["YIELD_CURVE_30Y5Y"] = all_data["US_30Y"] - all_data["US_5Y"]

        # 3. Add forex data from Polygon
        for symbol in forex_symbols:
            # This would use Polygon API in production
            # For now, we'll use placeholder
            print(f"  📊 Adding {symbol} as exogenous variable")

        # Create combined DataFrame
        df = pd.DataFrame(all_data)
        df = df.ffill().fillna(method="bfill")

        print(f"\n✅ Total exogenous variables: {len(df.columns)}")

        return df

    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def create_lagged_features(
        self, data: pd.DataFrame, target_symbol: str, target_data: pd.DataFrame = None
    ) -> pd.DataFrame:
        """Create lagged features for all exogenous variables AND technical indicators for target."""
        # Ensure consistent timezone handling
        if hasattr(data.index, "tz"):
            index = (
                data.index.tz_localize(None)
                if data.index.tz is not None
                else data.index
            )
        else:
            index = data.index

        features = pd.DataFrame(index=index)

        # FIRST: Add technical indicators for the TARGET (endogenous) variable
        if target_data is not None and len(target_data) > 0:
            print(f"  Adding technical indicators for {target_symbol}...")

            # Ensure target_data has same timezone handling
            if hasattr(target_data.index, "tz") and target_data.index.tz is not None:
                target_data = target_data.copy()
                target_data.index = target_data.index.tz_localize(None)

            # Price-based indicators
            close = (
                target_data["close"] if "close" in target_data.columns else target_data
            )
            high = target_data["high"] if "high" in target_data.columns else close
            low = target_data["low"] if "low" in target_data.columns else close
            volume = target_data["volume"] if "volume" in target_data.columns else None

            # 1. Moving Averages
            features[f"{target_symbol}_sma_5"] = close.rolling(5).mean()
            features[f"{target_symbol}_sma_20"] = close.rolling(20).mean()
            features[f"{target_symbol}_sma_50"] = close.rolling(50).mean()
            features[f"{target_symbol}_sma_200"] = close.rolling(200).mean()

            features[f"{target_symbol}_ema_12"] = close.ewm(span=12).mean()
            features[f"{target_symbol}_ema_26"] = close.ewm(span=26).mean()

            # 2. Price relationships
            features[f"{target_symbol}_price_to_sma20"] = (
                close / features[f"{target_symbol}_sma_20"]
            )
            features[f"{target_symbol}_price_to_sma50"] = (
                close / features[f"{target_symbol}_sma_50"]
            )

            # 3. Momentum indicators
            features[f"{target_symbol}_rsi_14"] = self.calculate_rsi(close, 14)
            features[f"{target_symbol}_rsi_7"] = self.calculate_rsi(close, 7)

            # 4. MACD
            macd = (
                features[f"{target_symbol}_ema_12"]
                - features[f"{target_symbol}_ema_26"]
            )
            features[f"{target_symbol}_macd"] = macd
            features[f"{target_symbol}_macd_signal"] = macd.ewm(span=9).mean()
            features[f"{target_symbol}_macd_hist"] = (
                macd - features[f"{target_symbol}_macd_signal"]
            )

            # 5. Bollinger Bands
            bb_sma = close.rolling(20).mean()
            bb_std = close.rolling(20).std()
            features[f"{target_symbol}_bb_upper"] = bb_sma + (2 * bb_std)
            features[f"{target_symbol}_bb_lower"] = bb_sma - (2 * bb_std)
            features[f"{target_symbol}_bb_width"] = (
                features[f"{target_symbol}_bb_upper"]
                - features[f"{target_symbol}_bb_lower"]
            )
            features[f"{target_symbol}_bb_position"] = (
                close - features[f"{target_symbol}_bb_lower"]
            ) / features[f"{target_symbol}_bb_width"]

            # 6. ATR (Average True Range)
            tr = pd.DataFrame(index=close.index)
            tr["hl"] = high - low
            tr["hc"] = abs(high - close.shift(1))
            tr["lc"] = abs(low - close.shift(1))
            true_range = tr.max(axis=1)
            features[f"{target_symbol}_atr_14"] = true_range.rolling(14).mean()
            features[f"{target_symbol}_atr_7"] = true_range.rolling(7).mean()

            # 7. Stochastic
            low_14 = low.rolling(14).min()
            high_14 = high.rolling(14).max()
            features[f"{target_symbol}_stoch_k"] = (
                100 * (close - low_14) / (high_14 - low_14)
            )
            features[f"{target_symbol}_stoch_d"] = (
                features[f"{target_symbol}_stoch_k"].rolling(3).mean()
            )

            # 8. Rate of Change
            features[f"{target_symbol}_roc_1"] = close.pct_change(1)
            features[f"{target_symbol}_roc_5"] = close.pct_change(5)
            features[f"{target_symbol}_roc_10"] = close.pct_change(10)
            features[f"{target_symbol}_roc_20"] = close.pct_change(20)

            # 9. Volatility
            features[f"{target_symbol}_volatility_5"] = (
                close.pct_change().rolling(5).std()
            )
            features[f"{target_symbol}_volatility_20"] = (
                close.pct_change().rolling(20).std()
            )
            features[f"{target_symbol}_volatility_ratio"] = (
                features[f"{target_symbol}_volatility_5"]
                / features[f"{target_symbol}_volatility_20"]
            )

            # 10. Support/Resistance levels
            features[f"{target_symbol}_resistance_20"] = high.rolling(20).max()
            features[f"{target_symbol}_support_20"] = low.rolling(20).min()
            features[f"{target_symbol}_sr_position"] = (
                close - features[f"{target_symbol}_support_20"]
            ) / (
                features[f"{target_symbol}_resistance_20"]
                - features[f"{target_symbol}_support_20"]
            )

            # 11. Volume indicators (if available)
            if volume is not None:
                features[f"{target_symbol}_volume_sma"] = volume.rolling(20).mean()
                features[f"{target_symbol}_volume_ratio"] = (
                    volume / features[f"{target_symbol}_volume_sma"]
                )
                features[f"{target_symbol}_obv"] = (
                    volume * ((close > close.shift(1)) * 2 - 1)
                ).cumsum()

            # 12. Pattern indicators
            features[f"{target_symbol}_higher_high"] = (
                (high > high.shift(1)) & (high.shift(1) > high.shift(2))
            ).astype(int)
            features[f"{target_symbol}_lower_low"] = (
                (low < low.shift(1)) & (low.shift(1) < low.shift(2))
            ).astype(int)

            # 13. Lagged prices for the target
            for lag in [1, 2, 3, 5, 10, 20]:
                features[f"{target_symbol}_close_lag{lag}"] = close.shift(lag)
                features[f"{target_symbol}_return_lag{lag}"] = close.pct_change(lag)

        for col in data.columns:
            # Determine category
            category = None
            for cat, vars in self.exogenous_variables.items():
                if isinstance(vars, dict) and col in vars:
                    category = cat
                    break

            if category is None:
                # Assume it's a forex pair
                category = "forex_pairs"

            # Get lags for this category
            lags = self.lag_config.get(category, [1, 2, 5])

            # Create lagged features
            for lag in lags:
                features[f"{col}_lag{lag}"] = data[col].shift(lag)

        # Add technical transformations
        # 1. Moving averages
        for col in data.columns:
            if col in ["VIX", "DXY", "US_10Y", "GOLD", "OIL_WTI"]:
                features[f"{col}_ma5"] = data[col].rolling(5).mean()
                features[f"{col}_ma20"] = data[col].rolling(20).mean()
                features[f"{col}_ma_diff"] = (
                    features[f"{col}_ma5"] - features[f"{col}_ma20"]
                )

        # 2. Rate of change
        for col in data.columns:
            features[f"{col}_roc1"] = data[col].pct_change(1)
            features[f"{col}_roc5"] = data[col].pct_change(5)

        # 3. Volatility
        for col in ["VIX", "DXY", "GOLD", "OIL_WTI"]:
            if col in data.columns:
                features[f"{col}_vol5"] = data[col].pct_change().rolling(5).std()

        # 4. Cross-asset relationships
        if "VIX" in data.columns and "DXY" in data.columns:
            features["VIX_DXY_ratio"] = data["VIX"] / data["DXY"]

        if "GOLD" in data.columns and "DXY" in data.columns:
            features["GOLD_DXY_ratio"] = data["GOLD"] / data["DXY"]

        if "OIL_WTI" in data.columns and "DXY" in data.columns:
            features["OIL_DXY_ratio"] = data["OIL_WTI"] / data["DXY"]

        # Remove features with too many NaNs
        features = features.dropna(thresh=len(features) * 0.8, axis=1)

        return features

    def select_relevant_features(
        self, X: pd.DataFrame, y: pd.Series, n_features: int = 50
    ) -> Tuple[List[str], pd.DataFrame]:
        """Select most relevant features for prediction."""

        # Remove NaN rows
        mask = ~(X.isna().any(axis=1) | y.isna())
        X_clean = X[mask]
        y_clean = y[mask]

        if len(X_clean) < 100:
            print("⚠️  Insufficient data for feature selection")
            return X.columns.tolist()[:n_features], X

        # 1. Mutual Information
        mi_selector = SelectKBest(
            score_func=mutual_info_regression, k=min(n_features, len(X.columns))
        )
        mi_selector.fit(X_clean, y_clean)
        mi_scores = pd.Series(mi_selector.scores_, index=X.columns)

        # 2. F-statistic
        f_selector = SelectKBest(
            score_func=f_regression, k=min(n_features, len(X.columns))
        )
        f_selector.fit(X_clean, y_clean)
        f_scores = pd.Series(f_selector.scores_, index=X.columns)

        # 3. LASSO feature importance
        lasso = LassoCV(cv=5, random_state=42, max_iter=2000)
        lasso.fit(X_clean, y_clean)
        lasso_importance = pd.Series(np.abs(lasso.coef_), index=X.columns)

        # 4. Random Forest importance
        rf = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        rf.fit(X_clean, y_clean)
        rf_importance = pd.Series(rf.feature_importances_, index=X.columns)

        # Combine scores (normalize first)
        mi_scores_norm = (mi_scores - mi_scores.min()) / (
            mi_scores.max() - mi_scores.min() + 1e-10
        )
        f_scores_norm = (f_scores - f_scores.min()) / (
            f_scores.max() - f_scores.min() + 1e-10
        )
        lasso_norm = (lasso_importance - lasso_importance.min()) / (
            lasso_importance.max() - lasso_importance.min() + 1e-10
        )
        rf_norm = (rf_importance - rf_importance.min()) / (
            rf_importance.max() - rf_importance.min() + 1e-10
        )

        # Combined score
        combined_score = (mi_scores_norm + f_scores_norm + lasso_norm + rf_norm) / 4

        # Select top features
        top_features = combined_score.nlargest(n_features).index.tolist()

        # Check for multicollinearity using VIF
        X_selected = X_clean[top_features]

        # Remove highly correlated features
        corr_matrix = X_selected.corr().abs()
        upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
        to_drop = [column for column in upper.columns if any(upper[column] > 0.95)]

        final_features = [f for f in top_features if f not in to_drop]

        print(
            f"\n✅ Selected {len(final_features)} features from {len(X.columns)} candidates"
        )

        # Print top 10 features
        print("\nTop 10 most important features:")
        for i, feat in enumerate(final_features[:10]):
            print(f"  {i+1}. {feat}: {combined_score[feat]:.3f}")

        return final_features, X[final_features]

    def granger_causality_test(
        self, cause_series: pd.Series, effect_series: pd.Series, maxlag: int = 5
    ) -> Dict:
        """Test if cause_series Granger-causes effect_series."""
        try:
            # Prepare data
            data = pd.DataFrame(
                {"effect": effect_series, "cause": cause_series}
            ).dropna()

            if len(data) < maxlag * 3:
                return {"significant": False, "p_value": 1.0}

            # Run test
            results = grangercausalitytests(
                data[["effect", "cause"]], maxlag=maxlag, verbose=False
            )

            # Get minimum p-value across lags
            min_p_value = 1.0
            best_lag = 1

            for lag in range(1, maxlag + 1):
                p_value = results[lag][0]["ssr_ftest"][1]
                if p_value < min_p_value:
                    min_p_value = p_value
                    best_lag = lag

            return {
                "significant": min_p_value < 0.05,
                "p_value": min_p_value,
                "best_lag": best_lag,
            }

        except Exception as e:
            return {"significant": False, "p_value": 1.0, "error": str(e)}

    def analyze_symbol_with_exogenous(
        self,
        target_symbol: str,
        target_data: pd.Series,
        exogenous_data: pd.DataFrame,
        other_forex_data: Dict[str, pd.Series],
        target_df: Optional[pd.DataFrame] = None,
    ) -> Dict:
        """Analyze a single symbol using all exogenous variables."""
        print(f"\n{'='*70}")
        print(f"Analyzing {target_symbol} as endogenous variable")
        print(f"{'='*70}")

        # Add other forex pairs to exogenous data
        for symbol, data in other_forex_data.items():
            if symbol != target_symbol:
                exogenous_data[symbol] = data

        # Create lagged features
        print("\nCreating lagged features...")
        # Use provided target_df or create from Series
        if target_df is None:
            target_df = pd.DataFrame({"close": target_data})
        features = self.create_lagged_features(exogenous_data, target_symbol, target_df)

        # Target variable (future return)
        y = target_data.pct_change().shift(-1)  # Next period return

        # Select relevant features
        selected_features, X_selected = self.select_relevant_features(features, y)

        # Granger causality tests for top features
        print("\nGranger Causality Tests (top 10 features):")
        granger_results = {}

        for feat in selected_features[:10]:
            if feat in features.columns:
                # Extract base variable name (remove _lag suffix)
                base_var = feat.split("_lag")[0].split("_ma")[0].split("_roc")[0]

                if base_var in exogenous_data.columns:
                    result = self.granger_causality_test(
                        exogenous_data[base_var], target_data
                    )
                    granger_results[feat] = result

                    if result["significant"]:
                        print(
                            f"  ✅ {feat}: p-value={result['p_value']:.4f}, lag={result.get('best_lag', 'N/A')}"
                        )
                    else:
                        print(f"  ❌ {feat}: p-value={result['p_value']:.4f}")

        # Build predictive model
        print("\nBuilding predictive model...")

        # Split data
        split_idx = int(len(X_selected) * 0.8)
        X_train = X_selected.iloc[:split_idx]
        X_test = X_selected.iloc[split_idx:]
        y_train = y.iloc[:split_idx]
        y_test = y.iloc[split_idx:]

        # Remove NaN
        train_mask = ~(X_train.isna().any(axis=1) | y_train.isna())
        test_mask = ~(X_test.isna().any(axis=1) | y_test.isna())

        X_train_clean = X_train[train_mask]
        y_train_clean = y_train[train_mask]
        X_test_clean = X_test[test_mask]
        y_test_clean = y_test[test_mask]

        if len(X_train_clean) < 50 or len(X_test_clean) < 10:
            print("⚠️  Insufficient data for modeling")
            return {
                "target_symbol": target_symbol,
                "selected_features": selected_features,
                "granger_results": granger_results,
            }

        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train_clean)
        X_test_scaled = scaler.transform(X_test_clean)

        # Multiple models
        models = {
            "Ridge": RidgeCV(cv=5),
            "Lasso": LassoCV(cv=5, max_iter=2000),
            "RF": RandomForestRegressor(n_estimators=100, random_state=42),
        }

        results = {}

        for name, model in models.items():
            model.fit(X_train_scaled, y_train_clean)

            # Predictions
            y_pred_train = model.predict(X_train_scaled)
            y_pred_test = model.predict(X_test_scaled)

            # Directional accuracy
            train_dir_acc = np.mean(np.sign(y_pred_train) == np.sign(y_train_clean))
            test_dir_acc = np.mean(np.sign(y_pred_test) == np.sign(y_test_clean))

            # R-squared
            train_r2 = model.score(X_train_scaled, y_train_clean)
            test_r2 = model.score(X_test_scaled, y_test_clean)

            results[name] = {
                "train_dir_accuracy": train_dir_acc,
                "test_dir_accuracy": test_dir_acc,
                "train_r2": train_r2,
                "test_r2": test_r2,
            }

            print(f"\n{name} Model:")
            print(f"  Train Direction Accuracy: {train_dir_acc:.2%}")
            print(f"  Test Direction Accuracy: {test_dir_acc:.2%}")
            print(f"  Test R²: {test_r2:.3f}")

        # Feature importance from best model
        best_model_name = max(results.items(), key=lambda x: x[1]["test_dir_accuracy"])[
            0
        ]
        best_model = models[best_model_name]

        feature_importance = None
        if hasattr(best_model, "feature_importances_"):
            feature_importance = pd.Series(
                best_model.feature_importances_, index=selected_features
            ).sort_values(ascending=False)
        elif hasattr(best_model, "coef_"):
            feature_importance = pd.Series(
                np.abs(best_model.coef_), index=selected_features
            ).sort_values(ascending=False)

        return {
            "target_symbol": target_symbol,
            "selected_features": selected_features,
            "granger_results": granger_results,
            "model_results": results,
            "best_model": best_model_name,
            "feature_importance": feature_importance,
            "n_features": len(selected_features),
            "n_samples": len(X_train_clean) + len(X_test_clean),
        }

    def analyze_all_symbols(
        self,
        forex_symbols: List[str],
        forex_data: Dict[str, pd.DataFrame],
        start_date: str,
        end_date: str,
    ) -> Dict[str, Dict]:
        """Analyze each symbol as endogenous with all others as exogenous."""

        # Fetch exogenous data once
        exogenous_data = self.fetch_all_exogenous_data(
            forex_symbols, start_date, end_date
        )

        # Results for each symbol
        all_results = {}

        # Prepare forex data (use close prices)
        forex_series = {}
        for symbol, df in forex_data.items():
            if "close" in df.columns:
                forex_series[symbol] = df["close"]

        # Analyze each symbol
        for target_symbol in forex_symbols:
            if target_symbol not in forex_series:
                print(f"\n⚠️  No data for {target_symbol}")
                continue

            # Get other forex data (excluding target)
            other_forex = {k: v for k, v in forex_series.items() if k != target_symbol}

            # Analyze - pass full DataFrame if available for technical indicators
            target_series = forex_series[target_symbol]
            target_df = forex_data.get(
                target_symbol, pd.DataFrame({"close": target_series})
            )

            results = self.analyze_symbol_with_exogenous(
                target_symbol,
                target_series,
                exogenous_data.copy(),
                other_forex,
                target_df,
            )

            all_results[target_symbol] = results

        # Summary
        print(f"\n{'='*70}")
        print("EXOGENOUS ANALYSIS SUMMARY")
        print(f"{'='*70}")

        for symbol, results in all_results.items():
            if "model_results" in results:
                best_model = results["best_model"]
                best_accuracy = results["model_results"][best_model][
                    "test_dir_accuracy"
                ]
                n_causal = sum(
                    1
                    for r in results["granger_results"].values()
                    if r.get("significant", False)
                )

                print(f"\n{symbol}:")
                print(f"  Best Model: {best_model}")
                print(f"  Test Accuracy: {best_accuracy:.2%}")
                print(f"  Granger-Causal Features: {n_causal}")
                print(f"  Total Features Used: {results['n_features']}")

                # Top causal features
                if n_causal > 0:
                    print(f"  Key Drivers:")
                    for feat, gr in results["granger_results"].items():
                        if gr.get("significant", False):
                            print(f"    - {feat} (p={gr['p_value']:.4f})")

        return all_results


def main():
    """Run exogenous variable analysis for forex symbols."""
    print("=" * 80)
    print("FOREX ENDOGENOUS/EXOGENOUS VARIABLE ANALYSIS")
    print("=" * 80)

    # Initialize analyzer
    analyzer = ExogenousVariableAnalyzer()

    # Symbols to analyze
    symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]

    # Date range
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=365 * 2)).strftime("%Y-%m-%d")

    print(f"\nAnalysis Period: {start_date} to {end_date}")
    print(f"Symbols: {', '.join(symbols)}")

    # Load forex data (simplified - in production use actual data loader)
    from scripts.simple_backtest_real_data import load_data

    forex_data = {}
    for symbol in symbols:
        df = load_data(symbol, start_date, end_date)
        if df is not None:
            forex_data[symbol] = df

    if len(forex_data) < 2:
        print("❌ Insufficient forex data for analysis")
        return

    # Run analysis
    results = analyzer.analyze_all_symbols(symbols, forex_data, start_date, end_date)

    # Save results
    output_dir = Path("output/exogenous_analysis")
    output_dir.mkdir(exist_ok=True, parents=True)

    # Save detailed results
    for symbol, result in results.items():
        if "feature_importance" in result and result["feature_importance"] is not None:
            result["feature_importance"].to_csv(
                output_dir / f"{symbol}_feature_importance.csv"
            )

    print(f"\n✅ Analysis complete! Results saved to: {output_dir}")

    return results


if __name__ == "__main__":
    main()
