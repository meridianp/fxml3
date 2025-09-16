#!/usr/bin/env python
"""Ensemble model combining ML predictions with Elliott Wave signals."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import json
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from fxml4.features.feature_engineering import UnifiedFeatureEngineer
from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer


class EnsembleMLElliottWave:
    """Ensemble model combining ML predictions with Elliott Wave analysis."""

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.feature_engineer = UnifiedFeatureEngineer()
        self.elliott_analyzer = ElliottWaveAnalyzer()
        self.risk_manager = None
        self.position_sizer = None

        # Load ML model
        self.ml_model, self.scaler, self.feature_names = self._load_latest_model()

        # Signal weights
        self.ml_weight = 0.6
        self.elliott_weight = 0.4

    def _load_latest_model(self):
        """Load the latest trained model."""
        model_dir = Path(f"models/{self.symbol}")
        if not model_dir.exists():
            return None, None, None

        # Find latest model (any type)
        model_files = list(model_dir.glob("*_model_*.joblib"))
        if not model_files:
            return None, None, None

        latest_model = sorted(model_files)[-1]
        timestamp_parts = latest_model.stem.split("_")[2:]
        timestamp = "_".join(timestamp_parts)

        model = joblib.load(latest_model)
        scaler = joblib.load(model_dir / f"scaler_{timestamp}.joblib")

        with open(model_dir / f"metadata_{timestamp}.json", "r") as f:
            metadata = json.load(f)

        return model, scaler, metadata["feature_names"]

    def generate_ensemble_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate ensemble signals combining ML and Elliott Wave."""

        # 1. Generate features
        df_features = self.feature_engineer.generate_features(df)

        # 2. Get ML predictions
        ml_signals = self._get_ml_signals(df_features)

        # 3. Get Elliott Wave signals
        elliott_signals = self._get_elliott_wave_signals(df)

        # 4. Combine signals
        ensemble_signals = self._combine_signals(ml_signals, elliott_signals)

        # 5. Apply risk filters
        filtered_signals = self._apply_risk_filters(ensemble_signals, df_features)

        # 6. Calculate position sizes
        position_sizes = self._calculate_position_sizes(filtered_signals, df_features)

        # Create output dataframe
        results = pd.DataFrame(index=df.index)
        results["ml_signal"] = ml_signals
        results["elliott_signal"] = elliott_signals
        results["ensemble_signal"] = filtered_signals
        results["position_size"] = position_sizes
        results["confidence"] = self._calculate_confidence(ml_signals, elliott_signals)

        return results

    def _get_ml_signals(self, df_features: pd.DataFrame) -> pd.Series:
        """Get ML model predictions."""
        if self.ml_model is None:
            return pd.Series(0, index=df_features.index)

        # Prepare features
        X = df_features[self.feature_names]

        # Handle missing values
        X_filled = X.fillna(method="ffill").fillna(0)

        # Scale and predict
        X_scaled = self.scaler.transform(X_filled)

        # Handle XGBoost/LightGBM label shifting
        model_type = type(self.ml_model).__name__
        if "XGB" in model_type or "LGBM" in model_type:
            predictions = self.ml_model.predict(X_scaled) - 1
        else:
            predictions = self.ml_model.predict(X_scaled)

        return pd.Series(predictions, index=df_features.index)

    def _get_elliott_wave_signals(self, df: pd.DataFrame) -> pd.Series:
        """Get Elliott Wave signals."""
        signals = pd.Series(0, index=df.index)

        try:
            # Analyze Elliott Wave patterns
            wave_count = self.elliott_analyzer.analyze(df)

            if wave_count and wave_count.waves:
                for wave in wave_count.waves:
                    # Generate signals based on wave type and position
                    if wave.wave_type.value == "IMPULSE":
                        # Impulse waves - trend following
                        if wave.position.value == "START":
                            signals.iloc[wave.start_idx : wave.start_idx + 5] = (
                                1  # Buy at start
                            )
                        elif wave.position.value == "END":
                            signals.iloc[wave.end_idx - 5 : wave.end_idx] = (
                                -1
                            )  # Sell at end

                    elif wave.wave_type.value == "CORRECTION":
                        # Corrective waves - counter trend
                        if wave.position.value == "START":
                            signals.iloc[wave.start_idx : wave.start_idx + 3] = (
                                -1
                            )  # Sell
                        elif wave.position.value == "END":
                            signals.iloc[wave.end_idx - 3 : wave.end_idx] = 1  # Buy

                    # Add wave confidence factor
                    if hasattr(wave, "confidence"):
                        confidence_factor = wave.confidence
                        affected_indices = range(
                            wave.start_idx, min(wave.end_idx + 1, len(signals))
                        )
                        for idx in affected_indices:
                            if signals.iloc[idx] != 0:
                                signals.iloc[idx] *= confidence_factor

        except Exception as e:
            print(f"Elliott Wave analysis error: {e}")

        # Normalize to -1, 0, 1
        signals = signals.apply(lambda x: 1 if x > 0.5 else (-1 if x < -0.5 else 0))

        return signals

    def _combine_signals(
        self, ml_signals: pd.Series, elliott_signals: pd.Series
    ) -> pd.Series:
        """Combine ML and Elliott Wave signals."""
        # Weighted combination
        combined = ml_signals * self.ml_weight + elliott_signals * self.elliott_weight

        # Convert to discrete signals
        ensemble_signals = pd.Series(0, index=ml_signals.index)

        # Strong signals (both agree)
        strong_buy = (ml_signals == 1) & (elliott_signals == 1)
        strong_sell = (ml_signals == -1) & (elliott_signals == -1)

        ensemble_signals[strong_buy] = 1
        ensemble_signals[strong_sell] = -1

        # Medium signals (weighted average > threshold)
        medium_buy = (combined > 0.3) & ~strong_buy
        medium_sell = (combined < -0.3) & ~strong_sell

        ensemble_signals[medium_buy] = 1
        ensemble_signals[medium_sell] = -1

        return ensemble_signals

    def _apply_risk_filters(
        self, signals: pd.Series, df_features: pd.DataFrame
    ) -> pd.Series:
        """Apply risk management filters to signals."""
        filtered_signals = signals.copy()

        # 1. Volatility filter - reduce position in high volatility
        if "atr_14" in df_features.columns:
            high_vol_threshold = df_features["atr_14"].quantile(0.8)
            high_vol_mask = df_features["atr_14"] > high_vol_threshold
            filtered_signals[high_vol_mask] = 0  # No trading in extreme volatility

        # 2. Trend alignment filter
        if "sma_50" in df_features.columns and "sma_200" in df_features.columns:
            uptrend = df_features["sma_50"] > df_features["sma_200"]
            downtrend = df_features["sma_50"] < df_features["sma_200"]

            # Don't sell in strong uptrend or buy in strong downtrend
            filtered_signals[(filtered_signals == -1) & uptrend] = 0
            filtered_signals[(filtered_signals == 1) & downtrend] = 0

        # 3. Support/Resistance filter
        if "price_to_resistance" in df_features.columns:
            near_resistance = df_features["price_to_resistance"] > 0.98
            near_support = (
                df_features["price_to_support"] < 1.02
                if "price_to_support" in df_features.columns
                else False
            )

            # Don't buy near resistance or sell near support
            filtered_signals[(filtered_signals == 1) & near_resistance] = 0
            if isinstance(near_support, pd.Series):
                filtered_signals[(filtered_signals == -1) & near_support] = 0

        return filtered_signals

    def _calculate_position_sizes(
        self, signals: pd.Series, df_features: pd.DataFrame
    ) -> pd.Series:
        """Calculate dynamic position sizes based on risk and confidence."""
        position_sizes = pd.Series(0.0, index=signals.index)

        # Base position size (2% of capital)
        base_size = 0.02

        for i in range(len(signals)):
            if signals.iloc[i] == 0:
                continue

            size = base_size

            # 1. Adjust for volatility (lower size in high volatility)
            if "atr_14" in df_features.columns:
                atr = df_features["atr_14"].iloc[i]
                avg_atr = df_features["atr_14"].rolling(50).mean().iloc[i]
                if pd.notna(avg_atr) and avg_atr > 0:
                    vol_ratio = atr / avg_atr
                    size *= 2 - vol_ratio  # Reduce size if vol > average

            # 2. Adjust for trend strength
            if "adx_14" in df_features.columns:
                adx = df_features["adx_14"].iloc[i]
                if pd.notna(adx):
                    if adx > 25:  # Strong trend
                        size *= 1.2
                    elif adx < 20:  # Weak trend
                        size *= 0.8

            # 3. Adjust for win rate (if available from past performance)
            # This would require tracking historical performance

            # 4. Kelly Criterion adjustment (simplified)
            # Assuming 50% win rate and 1.5:1 reward/risk
            kelly_fraction = 0.167  # (0.5 * 1.5 - 0.5) / 1.5
            size = min(size, base_size * kelly_fraction * 2)  # Conservative Kelly

            # 5. Maximum position size cap
            size = min(size, 0.05)  # Never more than 5% per trade

            position_sizes.iloc[i] = size

        return position_sizes

    def _calculate_confidence(
        self, ml_signals: pd.Series, elliott_signals: pd.Series
    ) -> pd.Series:
        """Calculate confidence score for each signal."""
        confidence = pd.Series(0.5, index=ml_signals.index)

        # High confidence when both agree
        agreement = (ml_signals == elliott_signals) & (ml_signals != 0)
        confidence[agreement] = 0.8

        # Low confidence when they disagree
        disagreement = (
            (ml_signals != elliott_signals) & (ml_signals != 0) & (elliott_signals != 0)
        )
        confidence[disagreement] = 0.3

        # Medium confidence when only one has signal
        one_signal = ((ml_signals != 0) & (elliott_signals == 0)) | (
            (ml_signals == 0) & (elliott_signals != 0)
        )
        confidence[one_signal] = 0.5

        return confidence


def backtest_ensemble_strategy(symbol: str):
    """Backtest the ensemble strategy."""
    print(f"\n{'='*60}")
    print(f"Backtesting Ensemble Strategy for {symbol}")
    print(f"{'='*60}")

    # Load data
    from scripts.simple_backtest_real_data import load_data

    df = load_data(symbol, "2024-01-01", "2025-06-01")
    if df is None or len(df) < 200:
        print(f"❌ Insufficient data for {symbol}")
        return None

    print(f"✅ Loaded {len(df)} 4H bars")

    # Initialize ensemble model
    ensemble = EnsembleMLElliottWave(symbol)

    if ensemble.ml_model is None:
        print(f"❌ No ML model found for {symbol}")
        return None

    # Generate signals
    print("Generating ensemble signals...")
    signals_df = ensemble.generate_ensemble_signals(df)

    # Simple backtest
    initial_capital = 100000
    capital = initial_capital
    position = 0
    trades = []

    for i in range(len(signals_df) - 1):
        signal = signals_df["ensemble_signal"].iloc[i]
        position_size = signals_df["position_size"].iloc[i]
        confidence = signals_df["confidence"].iloc[i]

        if signal == 0 or position_size == 0:
            continue

        current_price = df["close"].iloc[i]

        # Close opposite position if any
        if position != 0 and np.sign(position) != np.sign(signal):
            pnl = position * (current_price - entry_price)
            capital += pnl
            trades.append(
                {
                    "exit_time": df.index[i],
                    "exit_price": current_price,
                    "pnl": pnl,
                    "return": pnl / abs(position * entry_price),
                }
            )
            position = 0

        # Open new position
        if position == 0 and signal != 0:
            position_value = capital * position_size
            position = signal * position_value / current_price
            entry_price = current_price
            trades.append(
                {
                    "entry_time": df.index[i],
                    "entry_price": current_price,
                    "signal": signal,
                    "size": position_size,
                    "confidence": confidence,
                }
            )

    # Close final position
    if position != 0:
        final_price = df["close"].iloc[-1]
        pnl = position * (final_price - entry_price)
        capital += pnl
        trades[-1]["exit_price"] = final_price
        trades[-1]["pnl"] = pnl

    # Calculate metrics
    total_return = (capital - initial_capital) / initial_capital
    completed_trades = [t for t in trades if "pnl" in t]

    if completed_trades:
        wins = len([t for t in completed_trades if t["pnl"] > 0])
        win_rate = wins / len(completed_trades)

        returns = [t["return"] for t in completed_trades if "return" in t]
        if returns:
            sharpe = (
                np.mean(returns) / np.std(returns) * np.sqrt(252)
                if np.std(returns) > 0
                else 0
            )
        else:
            sharpe = 0
    else:
        win_rate = 0
        sharpe = 0

    # Signal analysis
    ml_signals = signals_df["ml_signal"].value_counts()
    elliott_signals = signals_df["elliott_signal"].value_counts()
    ensemble_signals = signals_df["ensemble_signal"].value_counts()

    print(f"\n{'='*40}")
    print("BACKTEST RESULTS")
    print(f"{'='*40}")
    print(f"Total Return: {total_return:.2%}")
    print(f"Win Rate: {win_rate:.2%}")
    print(f"Sharpe Ratio: {sharpe:.2f}")
    print(f"Total Trades: {len(completed_trades)}")

    print(f"\nSignal Analysis:")
    print(f"ML Signals - Buy: {ml_signals.get(1, 0)}, Sell: {ml_signals.get(-1, 0)}")
    print(
        f"Elliott Signals - Buy: {elliott_signals.get(1, 0)}, Sell: {elliott_signals.get(-1, 0)}"
    )
    print(
        f"Ensemble Signals - Buy: {ensemble_signals.get(1, 0)}, Sell: {ensemble_signals.get(-1, 0)}"
    )

    avg_confidence = signals_df["confidence"].mean()
    print(f"\nAverage Confidence: {avg_confidence:.2%}")

    return {
        "total_return": total_return,
        "win_rate": win_rate,
        "sharpe_ratio": sharpe,
        "total_trades": len(completed_trades),
    }


def main():
    """Run ensemble backtests for all symbols."""
    symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]

    print("Ensemble ML + Elliott Wave Strategy Backtest")
    print("=" * 60)

    results = {}
    for symbol in symbols:
        try:
            result = backtest_ensemble_strategy(symbol)
            if result:
                results[symbol] = result
        except Exception as e:
            print(f"❌ Error testing {symbol}: {e}")
            import traceback

            traceback.print_exc()

    # Summary
    if results:
        print(f"\n{'='*60}")
        print("ENSEMBLE STRATEGY SUMMARY")
        print(f"{'='*60}")
        print(
            f"{'Symbol':<10} {'Return':>10} {'Sharpe':>10} {'Win Rate':>10} {'Trades':>10}"
        )
        print(f"{'-'*50}")

        for symbol, res in results.items():
            print(
                f"{symbol:<10} {res['total_return']:>9.1%} "
                f"{res['sharpe_ratio']:>10.2f} "
                f"{res['win_rate']:>9.1%} "
                f"{res['total_trades']:>10}"
            )


if __name__ == "__main__":
    main()
