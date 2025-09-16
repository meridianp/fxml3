"""Elliott Wave backtesting integration."""

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from ..strategy.base_strategy import BaseStrategy
from ..wave_analysis.elliott_wave import ElliottWaveAnalyzer, WaveType


class ElliottWaveBacktestStrategy(BaseStrategy):
    """Elliott Wave strategy for backtesting."""

    def __init__(
        self,
        wave_analyzer: Optional[ElliottWaveAnalyzer] = None,
        params: Optional[Dict[str, Any]] = None,
    ):
        """Initialize Elliott Wave backtest strategy."""
        default_params = {
            "min_wave_confidence": 0.7,
            "use_wave_3_only": False,
            "use_wave_5_exit": True,
            "combine_with_trend": True,
            "risk_per_trade": 0.02,
        }
        if params:
            default_params.update(params)

        super().__init__(name="ElliottWaveStrategy", params=default_params)
        self.wave_analyzer = wave_analyzer or ElliottWaveAnalyzer()

    def generate_signals(
        self, data: pd.DataFrame, features: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """Generate Elliott Wave based signals."""
        signals = pd.DataFrame(index=data.index)
        signals["signal"] = 0
        signals["strength"] = 0.0
        signals["wave_type"] = ""

        # Analyze waves
        wave_patterns = self.wave_analyzer.analyze(data)

        if not wave_patterns:
            return signals

        # Process wave patterns
        for pattern in wave_patterns:
            # Check confidence
            if pattern.confidence < self.params["min_wave_confidence"]:
                continue

            # Get pattern time range
            start_idx = pattern.points[0]["index"]
            end_idx = pattern.points[-1]["index"]

            # Generate signals based on wave type
            if self.params["use_wave_3_only"]:
                # Trade only wave 3
                if pattern.wave_type in [
                    WaveType.IMPULSE_WAVE_3,
                    WaveType.EXTENDED_WAVE_3,
                ]:
                    signals.loc[start_idx:end_idx, "signal"] = (
                        1 if pattern.direction == "up" else -1
                    )
                    signals.loc[start_idx:end_idx, "strength"] = pattern.confidence
                    signals.loc[start_idx:end_idx, "wave_type"] = str(pattern.wave_type)
            else:
                # Trade all impulse waves
                if pattern.wave_type in [
                    WaveType.IMPULSE_WAVE_1,
                    WaveType.IMPULSE_WAVE_3,
                    WaveType.IMPULSE_WAVE_5,
                    WaveType.EXTENDED_WAVE_3,
                    WaveType.EXTENDED_WAVE_5,
                ]:
                    signals.loc[start_idx:end_idx, "signal"] = (
                        1 if pattern.direction == "up" else -1
                    )
                    signals.loc[start_idx:end_idx, "strength"] = pattern.confidence
                    signals.loc[start_idx:end_idx, "wave_type"] = str(pattern.wave_type)

            # Exit signals for wave 5
            if (
                self.params["use_wave_5_exit"]
                and pattern.wave_type == WaveType.IMPULSE_WAVE_5
            ):
                # Generate exit signal at the end of wave 5
                if end_idx < len(signals):
                    signals.loc[end_idx, "signal"] = 0  # Exit signal

        # Combine with trend if configured
        if self.params["combine_with_trend"] and features is not None:
            if "trend" in features.columns:
                # Align signals with trend
                trend_mask = features["trend"] > 0
                signals.loc[~trend_mask & (signals["signal"] > 0), "signal"] = 0

                trend_mask = features["trend"] < 0
                signals.loc[~trend_mask & (signals["signal"] < 0), "signal"] = 0

        return signals

    def calculate_position_size(
        self, signal: Dict[str, Any], account_balance: float, current_price: float
    ) -> float:
        """Calculate position size for Elliott Wave signals."""
        # Base position size on wave type and confidence
        base_risk = self.params["risk_per_trade"]

        # Adjust risk based on wave type
        wave_type = signal.get("wave_type", "")
        risk_multiplier = 1.0

        if "WAVE_3" in wave_type:
            risk_multiplier = 1.5  # Larger position for wave 3
        elif "WAVE_5" in wave_type:
            risk_multiplier = 0.7  # Smaller position for wave 5
        elif "WAVE_1" in wave_type:
            risk_multiplier = 0.8  # Conservative for wave 1

        # Adjust by signal strength
        strength = signal.get("strength", 0.5)
        risk_multiplier *= 0.5 + strength

        # Calculate final position size
        adjusted_risk = base_risk * risk_multiplier
        position_value = account_balance * adjusted_risk

        return position_value / current_price
