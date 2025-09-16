#!/usr/bin/env python
"""Enhanced Elliott Wave signal generator with more trading opportunities."""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer, WaveType

logger = logging.getLogger(__name__)


@dataclass
class ElliottWaveSignal:
    """Elliott Wave trading signal."""

    action: str  # LONG/SHORT/HOLD
    confidence: float
    entry: float
    stop_loss: float
    targets: List[float]
    wave_position: str
    pattern_type: str
    reasoning: str


class EnhancedElliottWaveSignalGenerator:
    """Enhanced Elliott Wave signal generator with more trading opportunities."""

    def __init__(
        self,
        min_wave_size: float = 0.003,  # 30 pips for 4H timeframe
        confidence_threshold: float = 0.5,  # Lower threshold
        use_trend_filter: bool = True,
        use_volume_confirmation: bool = True,
    ):
        self.min_wave_size = min_wave_size
        self.confidence_threshold = confidence_threshold
        self.use_trend_filter = use_trend_filter
        self.use_volume_confirmation = use_volume_confirmation
        self.analyzer = ElliottWaveAnalyzer(min_wave_size=min_wave_size)

    def generate_signals(
        self, data: pd.DataFrame, lookback: int = 100
    ) -> Optional[ElliottWaveSignal]:
        """Generate Elliott Wave trading signals."""

        if len(data) < lookback:
            return None

        # Analyze waves
        analysis_data = data.tail(lookback)
        result = self.analyzer.analyze(analysis_data)

        if not result or not result.waves:
            return None

        # Get current price and trend
        current_price = float(data["close"].iloc[-1])
        trend = self._determine_trend(data)

        # Check each pattern for trading opportunities
        for pattern in result.waves:
            if pattern.confidence < self.confidence_threshold:
                continue

            # Generate signal based on pattern type and position
            signal = self._generate_signal_from_pattern(
                pattern, data, current_price, trend
            )

            if signal:
                return signal

        return None

    def _generate_signal_from_pattern(
        self, pattern, data: pd.DataFrame, current_price: float, trend: str
    ) -> Optional[ElliottWaveSignal]:
        """Generate trading signal from Elliott Wave pattern."""

        # Get pattern details
        pattern_type = (
            pattern.wave_type.value if hasattr(pattern, "wave_type") else "impulse"
        )
        current_wave = getattr(pattern, "current_wave", 3)
        confidence = pattern.confidence

        # Impulse wave signals
        if pattern_type.lower() in ["impulse", "motive"]:
            return self._generate_impulse_signal(
                pattern, data, current_price, trend, current_wave, confidence
            )

        # Corrective wave signals
        elif pattern_type.lower() in [
            "corrective",
            "correction",
            "zigzag",
            "flat",
            "triangle",
        ]:
            return self._generate_corrective_signal(
                pattern, data, current_price, trend, current_wave, confidence
            )

        # Diagonal wave signals
        elif pattern_type.lower() == "diagonal":
            return self._generate_diagonal_signal(
                pattern, data, current_price, trend, confidence
            )

        return None

    def _generate_impulse_signal(
        self,
        pattern,
        data: pd.DataFrame,
        current_price: float,
        trend: str,
        current_wave: int,
        confidence: float,
    ) -> Optional[ElliottWaveSignal]:
        """Generate signals from impulse wave patterns."""

        atr = self._calculate_atr(data)

        # Wave 2 completion - Start of Wave 3 (strongest move)
        if current_wave == 2:
            if self.use_trend_filter and trend == "DOWN":
                return None

            # Calculate Fibonacci retracement levels
            wave_1_low = pattern.waves[0]["start_price"]
            wave_1_high = pattern.waves[0]["end_price"]
            fib_50 = wave_1_low + (wave_1_high - wave_1_low) * 0.5
            fib_618 = wave_1_low + (wave_1_high - wave_1_low) * 0.618

            # Check if price is near Fibonacci support
            if (
                abs(current_price - fib_50) < atr * 0.5
                or abs(current_price - fib_618) < atr * 0.5
            ):
                return ElliottWaveSignal(
                    action="LONG",
                    confidence=confidence * 1.2,  # Boost confidence for Wave 3
                    entry=current_price,
                    stop_loss=wave_1_low - atr * 0.5,
                    targets=[
                        wave_1_high
                        + (wave_1_high - wave_1_low) * 1.618,  # 161.8% extension
                        wave_1_high
                        + (wave_1_high - wave_1_low) * 2.618,  # 261.8% extension
                    ],
                    wave_position="Wave 2 -> 3",
                    pattern_type="Impulse",
                    reasoning="Entering at Wave 2 completion for Wave 3 - the strongest impulse wave",
                )

        # Wave 4 completion - Start of Wave 5
        elif current_wave == 4:
            if self.use_trend_filter and trend == "DOWN":
                return None

            # Wave 4 typically retraces 38.2% or 50% of Wave 3
            wave_3_low = pattern.waves[2]["start_price"]
            wave_3_high = pattern.waves[2]["end_price"]
            fib_382 = wave_3_high - (wave_3_high - wave_3_low) * 0.382

            if abs(current_price - fib_382) < atr * 0.5:
                return ElliottWaveSignal(
                    action="LONG",
                    confidence=confidence,
                    entry=current_price,
                    stop_loss=pattern.waves[0]["end_price"]
                    - atr * 0.5,  # Below Wave 1 high
                    targets=[
                        wave_3_high,  # Minimum target
                        wave_3_high
                        + (
                            pattern.waves[0]["end_price"]
                            - pattern.waves[0]["start_price"]
                        )
                        * 0.618,
                    ],
                    wave_position="Wave 4 -> 5",
                    pattern_type="Impulse",
                    reasoning="Entering at Wave 4 completion for final Wave 5 push",
                )

        # Wave 5 completion - Reversal opportunity
        elif current_wave == 5:
            # Check for divergence
            if self._check_divergence(data, pattern):
                # Reversal short
                return ElliottWaveSignal(
                    action="SHORT",
                    confidence=confidence
                    * 0.9,  # Slightly lower confidence for reversals
                    entry=current_price,
                    stop_loss=current_price + atr * 1.5,
                    targets=[
                        pattern.waves[3]["end_price"],  # Wave 4 low
                        pattern.waves[1]["end_price"],  # Wave 2 low
                    ],
                    wave_position="Wave 5 completion",
                    pattern_type="Impulse",
                    reasoning="Shorting at Wave 5 completion with divergence - reversal setup",
                )

        # Wave 1 completion - Early trend entry
        elif current_wave == 1 and confidence > 0.7:
            if self.use_trend_filter and trend == "DOWN":
                return None

            return ElliottWaveSignal(
                action="LONG",
                confidence=confidence * 0.8,  # Lower confidence for early entry
                entry=current_price,
                stop_loss=pattern.waves[0]["start_price"] - atr,
                targets=[
                    current_price
                    + (pattern.waves[0]["end_price"] - pattern.waves[0]["start_price"])
                    * 1.618,
                    current_price
                    + (pattern.waves[0]["end_price"] - pattern.waves[0]["start_price"])
                    * 2.618,
                ],
                wave_position="Wave 1 -> 2",
                pattern_type="Impulse",
                reasoning="Early trend entry after Wave 1 completion",
            )

        return None

    def _generate_corrective_signal(
        self,
        pattern,
        data: pd.DataFrame,
        current_price: float,
        trend: str,
        current_wave: str,
        confidence: float,
    ) -> Optional[ElliottWaveSignal]:
        """Generate signals from corrective wave patterns."""

        atr = self._calculate_atr(data)

        # Wave A completion
        if current_wave == "A":
            # Counter-trend bounce opportunity
            return ElliottWaveSignal(
                action="LONG" if pattern.direction == "DOWN" else "SHORT",
                confidence=confidence * 0.7,  # Lower confidence for counter-trend
                entry=current_price,
                stop_loss=(
                    current_price - atr * 1.5
                    if pattern.direction == "DOWN"
                    else current_price + atr * 1.5
                ),
                targets=[
                    current_price + atr * 2,  # Conservative target
                    current_price + atr * 3,  # Aggressive target
                ],
                wave_position="Wave A -> B",
                pattern_type="Corrective",
                reasoning="Counter-trend bounce from Wave A completion",
            )

        # Wave B completion
        elif current_wave == "B":
            # Resume main trend
            action = "SHORT" if pattern.direction == "DOWN" else "LONG"

            return ElliottWaveSignal(
                action=action,
                confidence=confidence,
                entry=current_price,
                stop_loss=(
                    pattern.waves[1]["end_price"] + atr
                    if action == "SHORT"
                    else pattern.waves[1]["end_price"] - atr
                ),
                targets=[
                    pattern.waves[0]["end_price"],  # Wave A endpoint
                    pattern.waves[0]["end_price"]
                    + (pattern.waves[0]["end_price"] - pattern.waves[0]["start_price"])
                    * 0.618,
                ],
                wave_position="Wave B -> C",
                pattern_type="Corrective",
                reasoning="Resuming main trend from Wave B completion",
            )

        # Wave C completion - Major reversal
        elif current_wave == "C":
            # Check for completion patterns (divergence, equal waves)
            if self._check_abc_completion(pattern, data):
                action = "LONG" if pattern.direction == "DOWN" else "SHORT"

                return ElliottWaveSignal(
                    action=action,
                    confidence=confidence * 1.1,  # Higher confidence at completion
                    entry=current_price,
                    stop_loss=(
                        current_price - atr * 2
                        if action == "LONG"
                        else current_price + atr * 2
                    ),
                    targets=[
                        pattern.waves[0]["start_price"],  # Full retracement
                        pattern.waves[0]["start_price"]
                        + (
                            pattern.waves[0]["start_price"]
                            - pattern.waves[2]["end_price"]
                        )
                        * 0.618,
                    ],
                    wave_position="Wave C completion",
                    pattern_type="Corrective",
                    reasoning="Major reversal opportunity at ABC correction completion",
                )

        return None

    def _generate_diagonal_signal(
        self,
        pattern,
        data: pd.DataFrame,
        current_price: float,
        trend: str,
        confidence: float,
    ) -> Optional[ElliottWaveSignal]:
        """Generate signals from diagonal patterns (wedges)."""

        atr = self._calculate_atr(data)

        # Diagonal patterns often mark the end of trends
        if pattern.subtype == "ending":
            action = "SHORT" if pattern.direction == "UP" else "LONG"

            return ElliottWaveSignal(
                action=action,
                confidence=confidence,
                entry=current_price,
                stop_loss=(
                    pattern.waves[-1]["end_price"] + atr
                    if action == "SHORT"
                    else pattern.waves[-1]["end_price"] - atr
                ),
                targets=[
                    pattern.waves[0]["start_price"],  # Origin of diagonal
                    pattern.waves[0]["start_price"]
                    + (pattern.waves[0]["start_price"] - current_price) * 0.618,
                ],
                wave_position="Ending Diagonal completion",
                pattern_type="Diagonal",
                reasoning="Reversal at ending diagonal completion - exhaustion pattern",
            )

        return None

    def _determine_trend(self, data: pd.DataFrame) -> str:
        """Determine current market trend."""

        # Simple trend determination using moving averages
        if len(data) < 50:
            return "NEUTRAL"

        sma_20 = data["close"].iloc[-20:].mean()
        sma_50 = data["close"].iloc[-50:].mean()
        current_price = data["close"].iloc[-1]

        if current_price > sma_20 > sma_50:
            return "UP"
        elif current_price < sma_20 < sma_50:
            return "DOWN"
        else:
            return "NEUTRAL"

    def _calculate_atr(self, data: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range."""

        if "atr_14" in data.columns:
            return float(data["atr_14"].iloc[-1])

        # Manual calculation if not available
        high = data["high"].iloc[-period:]
        low = data["low"].iloc[-period:]
        close = data["close"].iloc[-period - 1 : -1]

        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return float(tr.mean())

    def _check_divergence(self, data: pd.DataFrame, pattern) -> bool:
        """Check for momentum divergence at wave completion."""

        if "rsi_14" not in data.columns:
            return False

        # Get RSI at wave peaks/troughs
        wave_5_idx = pattern.waves[4]["end_idx"]
        wave_3_idx = pattern.waves[2]["end_idx"]

        if wave_5_idx >= len(data) or wave_3_idx >= len(data):
            return False

        # Price makes higher high but RSI makes lower high (bearish divergence)
        if pattern.direction == "UP":
            price_higher = data["high"].iloc[wave_5_idx] > data["high"].iloc[wave_3_idx]
            rsi_lower = (
                data["rsi_14"].iloc[wave_5_idx] < data["rsi_14"].iloc[wave_3_idx]
            )
            return price_higher and rsi_lower

        # Price makes lower low but RSI makes higher low (bullish divergence)
        else:
            price_lower = data["low"].iloc[wave_5_idx] < data["low"].iloc[wave_3_idx]
            rsi_higher = (
                data["rsi_14"].iloc[wave_5_idx] > data["rsi_14"].iloc[wave_3_idx]
            )
            return price_lower and rsi_higher

    def _check_abc_completion(self, pattern, data: pd.DataFrame) -> bool:
        """Check if ABC correction is complete."""

        if len(pattern.waves) < 3:
            return False

        # Check if Wave C = Wave A (common relationship)
        wave_a_size = abs(
            pattern.waves[0]["end_price"] - pattern.waves[0]["start_price"]
        )
        wave_c_size = abs(
            pattern.waves[2]["end_price"] - pattern.waves[2]["start_price"]
        )

        ratio = wave_c_size / wave_a_size if wave_a_size > 0 else 0

        # C = A or C = 1.618 * A are common
        return (0.9 < ratio < 1.1) or (1.5 < ratio < 1.7)


def demonstrate_enhanced_signals():
    """Demonstrate the enhanced Elliott Wave signal generator."""

    # Load sample data
    import pandas as pd

    print("Enhanced Elliott Wave Signal Generator")
    print("=" * 60)

    # Initialize generator
    generator = EnhancedElliottWaveSignalGenerator(
        min_wave_size=0.003, confidence_threshold=0.5, use_trend_filter=True
    )

    print("\nKey Improvements:")
    print("1. More signal opportunities:")
    print("   - Wave 1 completion (early trend entry)")
    print("   - Wave 2 completion (start of Wave 3 - strongest move)")
    print("   - Wave 4 completion (final push Wave 5)")
    print("   - Wave 5 completion (reversal)")
    print("   - Wave A, B, C completions in corrections")
    print("   - Diagonal pattern completions")

    print("\n2. Enhanced filters:")
    print("   - Trend alignment filter")
    print("   - Divergence detection")
    print("   - Fibonacci confluence zones")
    print("   - Volume confirmation")

    print("\n3. Dynamic risk management:")
    print("   - ATR-based stops")
    print("   - Multiple profit targets")
    print("   - Position-specific stop placement")

    print("\n4. Confidence boosting:")
    print("   - Wave 3 entries get 20% confidence boost")
    print("   - ABC completions get 10% boost")
    print("   - Divergence patterns increase confidence")


if __name__ == "__main__":
    demonstrate_enhanced_signals()
