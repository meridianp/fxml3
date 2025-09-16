"""Example demonstrating enhanced Elliott Wave signal generation.

This example shows how to use the EnhancedWaveSignalGenerator with sentiment-enhanced
Elliott Wave pattern validation to generate trading signals.
"""

import logging
import os
import sys
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add the parent directory to the path to import fxml4 modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import directly from the example file to avoid external dependencies
# from fxml4.strategy.enhanced_wave_signal_generator import EnhancedWaveSignalGenerator
from fxml4.strategy.integrated_strategy import SignalSource, SignalType

# Import required modules
from fxml4.wave_analysis.elliott_wave import (
    ElliottWaveAnalyzer,
    ElliottWaveCount,
    ElliottWavePattern,
    WavePosition,
    WaveType,
)
from fxml4.wave_analysis.fibonacci import FibonacciCalculator


# Create simplified versions of components to avoid external dependencies
class SimpleEnhancedWaveSignalGenerator:
    """Simplified signal generator for the example."""

    def __init__(self, wave_validator, config=None):
        """Initialize the signal generator."""
        self.wave_validator = wave_validator
        self.config = config or {}

        # Signal configuration
        self.threshold = self.config.get("threshold", 0.65)
        self.position_weights = self.config.get(
            "position_weights",
            {
                "impulse_end_5": 0.9,  # End of impulse wave 5
                "correction_end_c": 0.8,  # End of correction wave C
                "impulse_end_3": 0.7,  # End of impulse wave 3
                "correction_end_b": 0.5,  # End of correction wave B
                "diagonal_end": 0.7,  # End of diagonal pattern
                "triangle_end": 0.6,  # End of triangle pattern
                "correction_end_a": 0.4,  # End of correction wave A
                "impulse_end_1": 0.3,  # End of impulse wave 1
            },
        )

        # Minimum confidence for signal generation
        self.min_confidence = self.config.get("min_confidence", 0.6)

        # Maximum stop loss as percentage of price
        self.max_stop_loss_pct = self.config.get("max_stop_loss_pct", 2.0)

        # Configure stop loss sizing based on pattern confidence
        self.stop_loss_confidence_scaling = self.config.get(
            "stop_loss_confidence_scaling", True
        )

        # Configure take profit level multipliers
        self.take_profit_levels = self.config.get(
            "take_profit_levels",
            {
                "conservative": 1.5,  # Risk-reward ratio for conservative target
                "moderate": 2.0,  # Risk-reward ratio for moderate target
                "aggressive": 3.0,  # Risk-reward ratio for aggressive target
            },
        )

    def _get_position_type(self, pattern):
        """Get position type string based on wave pattern."""
        if pattern["wave_type"] == "IMPULSE":
            if pattern["position"] == "END" and len(pattern["subwaves"]) >= 5:
                return "impulse_end_5"
            elif pattern["position"] == "END" and len(pattern["subwaves"]) >= 3:
                return "impulse_end_3"
            elif pattern["position"] == "END" and len(pattern["subwaves"]) >= 1:
                return "impulse_end_1"
            return "impulse_middle"

        elif pattern["wave_type"] == "CORRECTION":
            if pattern["position"] == "END" and len(pattern["subwaves"]) >= 3:
                return "correction_end_c"
            elif pattern["position"] == "END" and len(pattern["subwaves"]) >= 2:
                return "correction_end_b"
            elif pattern["position"] == "END" and len(pattern["subwaves"]) >= 1:
                return "correction_end_a"
            return "correction_middle"

        elif pattern["wave_type"] == "DIAGONAL":
            if pattern["position"] == "END":
                return "diagonal_end"
            return "diagonal_middle"

        elif pattern["wave_type"] == "TRIANGLE":
            if pattern["position"] == "END":
                return "triangle_end"
            return "triangle_middle"

        return "unknown"

    def _calculate_stop_loss_level(self, pattern, price_data, confidence, signal_type):
        """Calculate stop loss level."""
        # Get current price
        current_price = price_data["close"].iloc[-1]

        # Adjust stop distance based on confidence
        if self.stop_loss_confidence_scaling:
            base_stop_pct = self.max_stop_loss_pct * (1 - 0.5 * confidence)
        else:
            base_stop_pct = self.max_stop_loss_pct

        # Default stop loss calculation
        if signal_type == SignalType.ENTRY_LONG:
            return current_price * (1 - base_stop_pct / 100)
        else:  # SHORT
            return current_price * (1 + base_stop_pct / 100)

    def _calculate_take_profit_levels(self, entry_price, stop_loss, signal_type):
        """Calculate take profit levels."""
        # Calculate risk
        risk = abs(entry_price - stop_loss)

        take_profit_prices = {}

        for level, rr_ratio in self.take_profit_levels.items():
            reward = risk * rr_ratio

            if signal_type == SignalType.ENTRY_LONG:
                take_profit_prices[level] = entry_price + reward
            else:  # SHORT
                take_profit_prices[level] = entry_price - reward

        return take_profit_prices

    def generate_signals(self, data, news_data=None, **kwargs):
        """Generate trading signals."""
        from fxml4.strategy.integrated_strategy import Signal

        signals = []

        # Extract metadata
        symbol = kwargs.get("symbol", "GBPUSD")
        timeframe = kwargs.get("timeframe", "1H")

        # Get the latest timestamp
        latest_timestamp = data.index[-1]

        try:
            # Analyze with sentiment
            analysis_results = self.wave_validator.analyze_with_sentiment(
                data, news_data
            )

            # Extract sentiment score
            sentiment_score = analysis_results.get("sentiment_score", 0)

            # Process validated patterns
            validated_patterns = analysis_results.get("validation", [])

            # Get current price
            current_price = data["close"].iloc[-1]

            for pattern_result in validated_patterns:
                # Skip invalid patterns
                if not pattern_result.get("is_valid", False):
                    continue

                # Get pattern details and confidence
                pattern_dict = pattern_result.get("pattern", {})
                confidence = pattern_result.get("confidence", 0)

                # Skip low confidence patterns
                if confidence < self.min_confidence:
                    continue

                # Get position type
                position_type = self._get_position_type(pattern_dict)
                position_strength = self.position_weights.get(position_type, 0.5)

                # Calculate signal strength
                signal_strength = confidence * position_strength

                # Determine signal type based on pattern and position
                if "IMPULSE" in pattern_dict["wave_type"]:
                    if position_type == "impulse_end_5":
                        # End of impulse wave 5 - expect correction
                        signal_type = SignalType.ENTRY_SHORT
                        exit_signal_type = SignalType.EXIT_LONG  # Also exit longs
                    elif position_type == "impulse_end_3":
                        signal_type = SignalType.ENTRY_SHORT
                    else:
                        continue

                elif "CORRECTION" in pattern_dict["wave_type"]:
                    if position_type == "correction_end_c":
                        signal_type = SignalType.ENTRY_LONG
                        exit_signal_type = SignalType.EXIT_SHORT  # Also exit shorts
                    elif position_type == "correction_end_a":
                        signal_type = SignalType.ENTRY_LONG
                    else:
                        continue

                else:
                    # Skip other patterns
                    continue

                # Calculate stop loss and take profit
                stop_loss = self._calculate_stop_loss_level(
                    pattern=pattern_dict,
                    price_data=data,
                    confidence=confidence,
                    signal_type=signal_type,
                )

                take_profit_levels = self._calculate_take_profit_levels(
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    signal_type=signal_type,
                )

                # Create entry signal
                entry_signal = Signal(
                    signal_type=signal_type,
                    strength=signal_strength,
                    source=SignalSource.WAVE,
                    timestamp=latest_timestamp,
                    symbol=symbol,
                    timeframe=timeframe,
                    metadata={
                        "wave_pattern": pattern_dict["wave_type"],
                        "wave_position": position_type,
                        "pattern_confidence": confidence,
                        "sentiment_score": sentiment_score,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit_levels,
                        "wave_details": pattern_dict,
                    },
                )
                signals.append(entry_signal)

                # Add exit signal if applicable
                if (
                    position_type in ["impulse_end_5", "correction_end_c"]
                    and signal_strength >= self.threshold
                ):
                    exit_signal = Signal(
                        signal_type=exit_signal_type,
                        strength=signal_strength,
                        source=SignalSource.WAVE,
                        timestamp=latest_timestamp,
                        symbol=symbol,
                        timeframe=timeframe,
                        metadata={
                            "wave_pattern": pattern_dict["wave_type"],
                            "wave_position": position_type,
                            "pattern_confidence": confidence,
                            "sentiment_score": sentiment_score,
                        },
                    )
                    signals.append(exit_signal)

        except Exception as e:
            print(f"Error generating signals: {e}")

        return signals


class SimpleSentimentWaveValidator:
    """Simplified SentimentWaveValidator for the example."""

    def __init__(self, wave_analyzer, config=None):
        """Initialize the validator."""
        self.wave_analyzer = wave_analyzer
        self.config = config or {}

    def analyze_with_sentiment(self, price_data, news_data=None):
        """Analyze price data with wave detection and sentiment."""
        # Detect wave patterns
        wave_count = self.wave_analyzer.analyze(price_data)

        if not wave_count or not wave_count.waves:
            # For demonstration purposes, create a synthetic wave pattern
            pattern_type = (
                "IMPULSE"
                if "impulse" in str(price_data["close"].iloc[-20:].values)
                else "CORRECTION"
            )

            # Create a pattern
            pattern = {
                "wave_type": pattern_type,
                "start_idx": 0,
                "end_idx": len(price_data) - 10,
                "confidence": 0.75,
                "position": "END",
                "subwaves": [
                    {
                        "wave_type": "IMPULSE",
                        "start_idx": 0,
                        "end_idx": 20,
                        "confidence": 0.8,
                        "position": "END",
                    },
                    {
                        "wave_type": "CORRECTION",
                        "start_idx": 20,
                        "end_idx": 30,
                        "confidence": 0.8,
                        "position": "END",
                    },
                    {
                        "wave_type": "IMPULSE",
                        "start_idx": 30,
                        "end_idx": 60,
                        "confidence": 0.8,
                        "position": "END",
                    },
                    {
                        "wave_type": "CORRECTION",
                        "start_idx": 60,
                        "end_idx": 70,
                        "confidence": 0.8,
                        "position": "END",
                    },
                    {
                        "wave_type": "IMPULSE",
                        "start_idx": 70,
                        "end_idx": 90,
                        "confidence": 0.8,
                        "position": "END",
                    },
                ],
            }

            # For demo purposes, create a simple validation
            validation = {
                "pattern": pattern,
                "is_valid": True,
                "confidence": 0.8,
                "details": {
                    "wave_confidence": 0.75,
                    "sentiment_confidence": 0.8,
                    "rag_confidence": 0.85,
                    "sentiment_score": 0.6,
                },
            }

            recent_data = price_data.tail(20)
            price_change = (
                recent_data["close"].iloc[-1] - recent_data["close"].iloc[0]
            ) / recent_data["close"].iloc[0]
            sentiment_score = min(max(price_change * 10, -1.0), 1.0)

            return {
                "patterns": [pattern],
                "validation": [validation],
                "combined_score": 0.8,
                "sentiment_score": sentiment_score,
            }

        # Extract simple sentiment from price momentum
        recent_data = price_data.tail(20)
        price_change = (
            recent_data["close"].iloc[-1] - recent_data["close"].iloc[0]
        ) / recent_data["close"].iloc[0]
        sentiment_score = min(max(price_change * 10, -1.0), 1.0)  # Scale to [-1, 1]

        # Create validation results
        validated_patterns = []

        for wave in wave_count.waves:
            # Skip patterns with very low confidence
            if wave.confidence < 0.4:
                continue

            # Calculate base confidence from wave analysis
            wave_confidence = wave.confidence

            # Calculate sentiment confidence based on pattern type and sentiment
            if (wave.wave_type == WaveType.IMPULSE and sentiment_score > 0) or (
                wave.wave_type == WaveType.CORRECTION and sentiment_score < 0
            ):
                sentiment_confidence = 0.8
            else:
                sentiment_confidence = 0.5

            # Calculate combined confidence
            combined_confidence = 0.7 * wave_confidence + 0.3 * sentiment_confidence

            # Create validation details
            validation_details = {
                "wave_confidence": wave_confidence,
                "sentiment_confidence": sentiment_confidence,
                "sentiment_score": sentiment_score,
                "rag_confidence": 0.7,  # Default RAG confidence
            }

            # Add to validation results
            validated_patterns.append(
                {
                    "pattern": wave.to_dict(),
                    "is_valid": combined_confidence >= 0.6,
                    "confidence": combined_confidence,
                    "details": validation_details,
                }
            )

        # Calculate overall combined score
        valid_patterns = [p for p in validated_patterns if p["is_valid"]]
        combined_score = (
            sum(p["confidence"] for p in valid_patterns) / len(valid_patterns)
            if valid_patterns
            else 0.0
        )

        return {
            "patterns": [wave.to_dict() for wave in wave_count.waves],
            "validation": validated_patterns,
            "combined_score": combined_score,
            "sentiment_score": sentiment_score,
        }


def generate_wave_pattern_data(pattern_type="impulse", noise_level=0.5):
    """Generate synthetic price data with a clear Elliott Wave pattern.

    Args:
        pattern_type: Type of pattern to generate.
        noise_level: Amount of random noise to add.

    Returns:
        DataFrame with OHLCV data.
    """
    # Define base parameters
    n_samples = 200
    dates = pd.date_range(start="2025-01-01", periods=n_samples, freq="h")

    # Initialize DataFrame
    data = pd.DataFrame(
        {
            "open": np.zeros(n_samples),
            "high": np.zeros(n_samples),
            "low": np.zeros(n_samples),
            "close": np.zeros(n_samples),
            "volume": np.random.randint(100, 1000, n_samples),
        },
        index=dates,
    )

    # Generate price pattern based on type
    if pattern_type == "impulse":
        # Wave 1: Initial bullish move
        data.loc[dates[0:30], "close"] = np.linspace(100, 110, 30)
        # Wave 2: Correction (not exceeding start of wave 1)
        data.loc[dates[30:50], "close"] = np.linspace(110, 103, 20)
        # Wave 3: Strong bullish move (longest)
        data.loc[dates[50:110], "close"] = np.linspace(103, 130, 60)
        # Wave 4: Correction (not overlapping with wave 1)
        data.loc[dates[110:140], "close"] = np.linspace(130, 120, 30)
        # Wave 5: Final bullish move
        data.loc[dates[140:200], "close"] = np.linspace(120, 140, 60)

    elif pattern_type == "correction":
        # Start with a high point
        data.loc[dates[0:1], "close"] = 140
        # Wave A: Initial bearish move
        data.loc[dates[1:40], "close"] = np.linspace(140, 120, 39)
        # Wave B: Partial recovery
        data.loc[dates[40:80], "close"] = np.linspace(120, 130, 40)
        # Wave C: Final bearish move
        data.loc[dates[80:200], "close"] = np.linspace(130, 100, 120)

    elif pattern_type == "diagonal":
        # Leading diagonal in bullish trend
        # Wave 1
        data.loc[dates[0:30], "close"] = np.linspace(100, 110, 30)
        # Wave 2
        data.loc[dates[30:50], "close"] = np.linspace(110, 105, 20)
        # Wave 3 (shorter than wave 1)
        data.loc[dates[50:70], "close"] = np.linspace(105, 112, 20)
        # Wave 4
        data.loc[dates[70:90], "close"] = np.linspace(112, 108, 20)
        # Wave 5 (shorter than wave 3)
        data.loc[dates[90:200], "close"] = np.linspace(108, 115, 110)

    else:
        # Default to a simple trend
        data.loc[dates, "close"] = np.linspace(100, 120, n_samples)

    # Add noise to close prices
    if noise_level > 0:
        noise = np.random.normal(0, noise_level, n_samples)
        data["close"] = data["close"] + noise

    # Fill open, high, low based on close prices
    data["open"] = data["close"].shift(1)
    data.loc[dates[0], "open"] = data.loc[dates[0], "close"] - 0.5

    for i in range(n_samples):
        # High is higher than open and close
        data.loc[dates[i], "high"] = max(
            data.loc[dates[i], "open"], data.loc[dates[i], "close"]
        ) + abs(np.random.normal(0, 0.5))
        # Low is lower than open and close
        data.loc[dates[i], "low"] = min(
            data.loc[dates[i], "open"], data.loc[dates[i], "close"]
        ) - abs(np.random.normal(0, 0.5))

    # Add some technical indicators
    # RSI (simple calculation)
    close_diff = data["close"].diff()
    gains = close_diff.copy()
    losses = close_diff.copy()
    gains[gains < 0] = 0
    losses[losses > 0] = 0
    losses = abs(losses)

    avg_gain = gains.rolling(window=14).mean()
    avg_loss = losses.rolling(window=14).mean()

    rs = avg_gain / avg_loss
    data["rsi"] = 100 - (100 / (1 + rs))
    data["rsi"] = data["rsi"].fillna(50)

    return data


def plot_signals(price_data, signals, title=None, save_path=None):
    """Plot price data with trading signals.

    Args:
        price_data: DataFrame with price data.
        signals: List of trading signals.
        title: Optional title for the plot.
        save_path: Optional path to save the plot.
    """
    fig, ax = plt.subplots(figsize=(14, 8))

    # Plot price data
    ax.plot(price_data.index, price_data["close"], label="Close Price")

    # Plot entry signals
    long_entries = [s for s in signals if s.signal_type == SignalType.ENTRY_LONG]
    short_entries = [s for s in signals if s.signal_type == SignalType.ENTRY_SHORT]

    # Plot exit signals
    long_exits = [s for s in signals if s.signal_type == SignalType.EXIT_LONG]
    short_exits = [s for s in signals if s.signal_type == SignalType.EXIT_SHORT]

    # Get timestamps and prices for signals
    long_entry_x = [s.timestamp for s in long_entries]
    long_entry_y = [price_data.loc[s.timestamp, "close"] for s in long_entries]

    short_entry_x = [s.timestamp for s in short_entries]
    short_entry_y = [price_data.loc[s.timestamp, "close"] for s in short_entries]

    long_exit_x = [s.timestamp for s in long_exits]
    long_exit_y = [price_data.loc[s.timestamp, "close"] for s in long_exits]

    short_exit_x = [s.timestamp for s in short_exits]
    short_exit_y = [price_data.loc[s.timestamp, "close"] for s in short_exits]

    # Plot signals
    ax.scatter(
        long_entry_x, long_entry_y, marker="^", color="green", s=200, label="Long Entry"
    )
    ax.scatter(
        short_entry_x,
        short_entry_y,
        marker="v",
        color="red",
        s=200,
        label="Short Entry",
    )
    ax.scatter(
        long_exit_x, long_exit_y, marker="x", color="blue", s=200, label="Exit Long"
    )
    ax.scatter(
        short_exit_x,
        short_exit_y,
        marker="x",
        color="purple",
        s=200,
        label="Exit Short",
    )

    # Add labels and legend
    ax.set_xlabel("Date")
    ax.set_ylabel("Price")
    ax.set_title(title or "Trading Signals")
    ax.legend()
    ax.grid(True)

    # Format x-axis dates
    fig.autofmt_xdate()

    # Add stop loss and take profit levels for the first entry signal
    entry_signals = long_entries + short_entries
    if entry_signals:
        first_signal = entry_signals[0]
        if "stop_loss" in first_signal.metadata:
            stop_loss = first_signal.metadata["stop_loss"]
            ax.axhline(
                y=stop_loss,
                color="red",
                linestyle="--",
                alpha=0.7,
                label=f"Stop Loss ({stop_loss:.2f})",
            )

            if "take_profit" in first_signal.metadata:
                tp_levels = first_signal.metadata["take_profit"]
                for level_name, price in tp_levels.items():
                    ax.axhline(
                        y=price,
                        color="green",
                        linestyle="--",
                        alpha=0.7,
                        label=f"Take Profit {level_name} ({price:.2f})",
                    )

    # Update legend with these new entries
    ax.legend()

    # Add signal information as text
    if signals:
        signal_info = []
        for i, signal in enumerate(signals):
            # Format signal info
            signal_type = signal.signal_type.name
            strength = signal.strength
            wave_pattern = signal.metadata.get("wave_pattern", "Unknown")
            confidence = signal.metadata.get("pattern_confidence", 0)
            sentiment = signal.metadata.get("sentiment_score", 0)

            info = f"Signal {i+1}: {signal_type}, Strength: {strength:.2f}\n"
            info += f"   Pattern: {wave_pattern}, Confidence: {confidence:.2f}\n"
            info += f"   Sentiment: {sentiment:.2f}"

            signal_info.append(info)

        # Create text box with signal information
        signal_text = "\n\n".join(signal_info)
        props = dict(boxstyle="round", facecolor="wheat", alpha=0.6)
        ax.text(
            0.02,
            0.02,
            signal_text,
            transform=ax.transAxes,
            fontsize=10,
            verticalalignment="bottom",
            horizontalalignment="left",
            bbox=props,
        )

    if save_path:
        # Ensure directory exists
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path)
        plt.close()
        logger.info(f"Plot saved to {save_path}")
    else:
        plt.tight_layout()
        plt.show()


def main():
    """Run the enhanced Elliott Wave signal generation example."""
    logger.info("Starting enhanced Elliott Wave signal generation example")

    # Generate sample data for different pattern types
    pattern_types = ["impulse", "correction", "diagonal"]

    # Create components
    wave_analyzer = ElliottWaveAnalyzer()
    fib_calculator = FibonacciCalculator()

    # Create simplified sentiment wave validator
    wave_validator = SimpleSentimentWaveValidator(wave_analyzer)

    # Create enhanced wave signal generator
    signal_generator = SimpleEnhancedWaveSignalGenerator(
        wave_validator=wave_validator,
        config={
            "threshold": 0.6,
            "min_confidence": 0.6,
            "max_stop_loss_pct": 2.0,
            "stop_loss_confidence_scaling": True,
            "take_profit_levels": {
                "conservative": 1.5,
                "moderate": 2.0,
                "aggressive": 3.0,
            },
        },
    )

    # Process each pattern type
    for pattern_type in pattern_types:
        logger.info(f"Processing {pattern_type} pattern")

        # Generate sample data
        price_data = generate_wave_pattern_data(
            pattern_type=pattern_type, noise_level=0.5
        )

        # Generate signals
        signals = signal_generator.generate_signals(
            data=price_data, symbol="GBPUSD", timeframe="1H"
        )

        # Log signal summary
        logger.info(f"Generated {len(signals)} signals for {pattern_type} pattern")
        for i, signal in enumerate(signals):
            logger.info(
                f"Signal {i+1}: {signal.signal_type.name}, Strength: {signal.strength:.2f}"
            )

        # Plot signals
        output_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "output",
            "enhanced_wave_signals",
        )
        save_path = os.path.join(output_dir, f"{pattern_type}_signals.png")

        plot_signals(
            price_data=price_data,
            signals=signals,
            title=f"Enhanced Elliott Wave Signals - {pattern_type.capitalize()} Pattern",
            save_path=save_path,
        )


if __name__ == "__main__":
    main()
