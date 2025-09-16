#!/usr/bin/env python
"""Debug version of improved backtest to understand filtering."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import json

import joblib
import numpy as np
import pandas as pd

from fxml4.strategy.market_regime_detector import MarketRegimeDetector, RegimeConfig

# Load model and data
symbol = "GBPUSD"
model = joblib.load(f"models/{symbol}/best_model_lightgbm.joblib")
scaler = joblib.load(f"models/{symbol}/scaler.joblib")

with open(f"models/{symbol}/selected_features.json", "r") as f:
    features = json.load(f)

df = pd.read_parquet(f"data/features/{symbol}_4h_features_advanced.parquet")
test_data = df["2023-01-01":"2024-06-30"]

# Initialize regime detector
regime_detector = MarketRegimeDetector(
    RegimeConfig(adx_trend_threshold=25.0, efficiency_threshold=0.3)
)

print("DEBUGGING SIGNAL GENERATION AND FILTERING")
print("=" * 60)

# Track statistics
total_signals = 0
high_confidence_signals = 0
tradeable_regimes = 0
rejected_signals = []

# Sample first 500 bars
for i in range(100, min(600, len(test_data))):
    current_bar = test_data.iloc[i]
    current_time = test_data.index[i]

    # Get signal
    try:
        X = test_data[features].iloc[i : i + 1]
        if not X.isnull().any().any():
            X_scaled = scaler.transform(X)
            pred = model.predict(X_scaled)[0]
            proba = model.predict_proba(X_scaled)[0]
            signal = pred - 1
            confidence = max(proba)

            if signal != 0:
                total_signals += 1

                if confidence > 0.65:
                    high_confidence_signals += 1

                    # Check regime
                    global_idx = df.index.get_loc(current_time)
                    regime_analysis = regime_detector.analyze_market(df, global_idx)

                    if regime_analysis["is_tradeable"]:
                        tradeable_regimes += 1
                    else:
                        rejected_signals.append(
                            {
                                "time": current_time,
                                "signal": signal,
                                "confidence": confidence,
                                "regime": regime_analysis["market_regime"].value,
                                "volatility": regime_analysis[
                                    "volatility_regime"
                                ].value,
                                "trend_strength": regime_analysis["trend_strength"],
                                "efficiency": regime_analysis["market_efficiency"],
                            }
                        )
    except Exception as e:
        continue

print(f"\nSignal Statistics (first 500 bars):")
print(f"Total non-zero signals: {total_signals}")
print(f"High confidence (>0.65): {high_confidence_signals}")
print(f"Tradeable after regime filter: {tradeable_regimes}")
print(f"Rejected by regime filter: {len(rejected_signals)}")

if rejected_signals:
    print(f"\nSample Rejected Signals:")
    for r in rejected_signals[:5]:
        print(
            f"  {r['time']}: {r['regime']}, vol={r['volatility']}, "
            f"trend={r['trend_strength']:.1f}, eff={r['efficiency']:.2f}"
        )

# Check ADX values
print(f"\nADX Analysis:")
adx_values = test_data["adx_14"].dropna()
print(f"Mean ADX: {adx_values.mean():.2f}")
print(f"ADX > 25: {(adx_values > 25).sum()} bars ({(adx_values > 25).mean()*100:.1f}%)")
print(f"ADX > 20: {(adx_values > 20).sum()} bars ({(adx_values > 20).mean()*100:.1f}%)")

# Check efficiency
print(f"\nMarket Efficiency Analysis:")
closes = test_data["close"]
net_changes = abs(closes.rolling(20).apply(lambda x: x.iloc[-1] - x.iloc[0]))
total_moves = closes.diff().abs().rolling(20).sum()
efficiency = (net_changes / total_moves).dropna()
print(f"Mean Efficiency: {efficiency.mean():.3f}")
print(
    f"Efficiency > 0.3: {(efficiency > 0.3).sum()} bars ({(efficiency > 0.3).mean()*100:.1f}%)"
)

print("\nRECOMMENDATION: Loosen regime filters for more trading opportunities")
