#!/usr/bin/env python3
"""Simplified test of visual validation system."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Import only the chart validator
from fxml4.llm_integration.multimodal_chart_validator import MultiModalChartValidator


class SimpleVisualValidationTester:
    """Simplified test of visual validation."""

    def __init__(self):
        # Initialize with empty config
        self.chart_validator = MultiModalChartValidator(config={})
        self.test_results = {
            "with_validation": [],
            "without_validation": [],
            "validation_details": [],
        }

    async def test_visual_validation(
        self,
        symbol: str = "GBPUSD",
        start_date: str = "2024-10-01",
        end_date: str = "2024-10-31",
    ):
        """Test visual validation on historical data."""
        logger.info(f"\n{'='*60}")
        logger.info(f"TESTING VISUAL VALIDATION SYSTEM (SIMPLIFIED)")
        logger.info(f"{'='*60}")
        logger.info(f"Symbol: {symbol}")
        logger.info(f"Period: {start_date} to {end_date}")
        logger.info(f"{'='*60}\n")

        # Load historical data
        data = self._load_historical_data(symbol, start_date, end_date)
        if data is None or len(data) < 50:
            logger.error("Insufficient data for testing")
            return

        # Calculate indicators
        indicators = self._calculate_indicators(data)

        # Test each potential signal
        signals_tested = 0
        signals_validated = 0
        false_positives_caught = 0

        # Sliding window approach - adjusted for available data
        window_size = 50  # Reduced from 100
        step_size = 12  # Test every 12 hours (3 bars)

        total_windows = 0
        # Process all available data
        for i in range(window_size, len(data) - 48, step_size):
            total_windows += 1
            # Get data window
            window_data = data.iloc[i - window_size : i + 1].copy()
            window_indicators = {
                k: v.iloc[i - window_size : i + 1] if hasattr(v, "iloc") else v
                for k, v in indicators.items()
            }

            # Generate simple momentum signal
            signal = self._generate_simple_signal(window_data)

            if (
                signal and signal.get("confidence", 0) > 0.5
            ):  # Lower threshold for testing
                signals_tested += 1

                # Add price data to signal
                signal["entry_price"] = window_data["close"].iloc[-1]
                signal["symbol"] = symbol
                signal["timeframe"] = "4H"
                signal["timestamp"] = window_data.index[-1]

                # Visual validation
                try:
                    validation = await self.chart_validator.validate_trading_signal(
                        signal, window_data, window_indicators
                    )

                    # Check future performance
                    future_data = data.iloc[i + 1 : i + 49]  # Next 48 hours
                    actual_performance = self._evaluate_signal_performance(
                        signal, future_data
                    )

                    # Record results
                    result = {
                        "timestamp": signal["timestamp"],
                        "ml_confidence": signal["confidence"],
                        "visual_validation": validation.get("valid", False),
                        "llm_confidence": validation.get("llm_confidence", 0),
                        "pattern_clarity": validation.get("pattern_clarity", 0),
                        "enhanced_confidence": validation.get("enhanced_confidence", 0),
                        "actual_profitable": actual_performance["profitable"],
                        "actual_return": actual_performance["return"],
                    }

                    self.test_results["validation_details"].append(result)

                    if (
                        validation.get("valid")
                        and validation.get("enhanced_confidence", 0) > 0.75
                    ):
                        signals_validated += 1
                        self.test_results["with_validation"].append(actual_performance)

                        logger.info(f"\n--- Signal {signals_tested} ---")
                        logger.info(f"Time: {signal['timestamp']}")
                        logger.info(f"Signal Confidence: {signal['confidence']:.1%}")
                        logger.info(
                            f"Visual Validation: {'✅ PASSED' if validation.get('valid') else '❌ FAILED'}"
                        )
                        logger.info(
                            f"LLM Confidence: {validation.get('llm_confidence', 0):.1%}"
                        )
                        logger.info(
                            f"Actual Result: {'✅ Profitable' if actual_performance['profitable'] else '❌ Loss'}"
                        )
                        logger.info(f"Return: {actual_performance['return']:.2%}")
                    else:
                        # Signal rejected by validation
                        if not actual_performance["profitable"]:
                            false_positives_caught += 1
                            logger.info(f"\n✅ False positive caught by validation!")
                            logger.info(
                                f"   Would have lost: {actual_performance['return']:.2%}"
                            )

                    # Always test without validation for comparison
                    self.test_results["without_validation"].append(actual_performance)

                except Exception as e:
                    logger.error(f"Error in visual validation: {e}")
                    import traceback

                    traceback.print_exc()

        # Log summary
        logger.info(f"\nTotal windows analyzed: {total_windows}")
        logger.info(f"Signals generated: {signals_tested}")
        logger.info(f"Signals validated: {signals_validated}")
        logger.info(f"False positives caught: {false_positives_caught}")

        # Generate report
        self._generate_test_report()

    def _load_historical_data(
        self, symbol: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """Load historical price data."""
        try:
            # Try to load 4H data
            file_paths = [
                f"data/processed/4h/{symbol}_4H_features_complete.parquet",
                f"data/aggregated/{symbol}_4H_aggregated.parquet",
                f"output/{symbol}_4h_aggregated.parquet",
            ]

            for path in file_paths:
                if Path(path).exists():
                    df = pd.read_parquet(path)
                    # Filter date range
                    df = df[(df.index >= start_date) & (df.index <= end_date)]
                    logger.info(f"Loaded {len(df)} bars from {path}")
                    return df

            logger.error(f"No data file found for {symbol}")
            return None

        except Exception as e:
            logger.error(f"Error loading data: {e}")
            return None

    def _generate_simple_signal(self, data: pd.DataFrame) -> dict:
        """Generate simple momentum-based signal."""
        if len(data) < 20:
            return None

        close = data["close"]
        sma_20 = close.rolling(20).mean()

        # Calculate RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        # Generate signal based on momentum - more relaxed criteria
        current_rsi = rsi.iloc[-1]

        # Debug logging
        logger.debug(
            f"Close: {close.iloc[-1]:.5f}, SMA20: {sma_20.iloc[-1]:.5f}, RSI: {current_rsi:.1f}"
        )

        # Check for NaN
        if pd.isna(current_rsi) or pd.isna(sma_20.iloc[-1]):
            logger.debug("NaN values detected")
            return None

        # Generate buy signal - more relaxed
        if close.iloc[-1] > sma_20.iloc[-1]:
            return {
                "direction": "BUY",
                "confidence": 0.55 + min((70 - current_rsi) / 200, 0.4),
                "stop_loss": close.iloc[-1] - 0.0040,
                "take_profit": close.iloc[-1] + 0.0080,
            }
        # Generate sell signal - more relaxed
        elif close.iloc[-1] < sma_20.iloc[-1]:
            return {
                "direction": "SELL",
                "confidence": 0.55 + min((current_rsi - 30) / 200, 0.4),
                "stop_loss": close.iloc[-1] + 0.0040,
                "take_profit": close.iloc[-1] - 0.0080,
            }
        # Force some signals for testing - crossover points
        elif abs(close.iloc[-1] - sma_20.iloc[-1]) < 0.0010:  # Near SMA
            if close.iloc[-2] < sma_20.iloc[-2]:  # Crossed above
                return {
                    "direction": "BUY",
                    "confidence": 0.65,
                    "stop_loss": close.iloc[-1] - 0.0040,
                    "take_profit": close.iloc[-1] + 0.0080,
                }
            elif close.iloc[-2] > sma_20.iloc[-2]:  # Crossed below
                return {
                    "direction": "SELL",
                    "confidence": 0.65,
                    "stop_loss": close.iloc[-1] + 0.0040,
                    "take_profit": close.iloc[-1] - 0.0080,
                }

        return None

    def _calculate_indicators(self, data: pd.DataFrame) -> dict:
        """Calculate technical indicators."""
        indicators = {}

        # Moving averages
        indicators["sma_20"] = data["close"].rolling(20).mean()
        indicators["sma_50"] = data["close"].rolling(50).mean()
        indicators["ema_9"] = data["close"].ewm(span=9).mean()

        # RSI
        delta = data["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        indicators["rsi"] = 100 - (100 / (1 + rs))

        # Bollinger Bands
        bb_sma = data["close"].rolling(20).mean()
        bb_std = data["close"].rolling(20).std()
        indicators["bb_upper"] = bb_sma + (bb_std * 2)
        indicators["bb_middle"] = bb_sma
        indicators["bb_lower"] = bb_sma - (bb_std * 2)

        # Simple support/resistance
        indicators["support_levels"] = []
        indicators["resistance_levels"] = []

        return indicators

    def _evaluate_signal_performance(
        self, signal: dict, future_data: pd.DataFrame
    ) -> dict:
        """Evaluate how a signal would have performed."""
        if len(future_data) == 0:
            return {"profitable": False, "return": 0, "mae": 0}

        entry_price = signal["entry_price"]
        stop_loss = signal["stop_loss"]
        take_profit = signal["take_profit"]

        # Track performance
        if signal["direction"] == "BUY":
            # Check each bar
            for i, (timestamp, bar) in enumerate(future_data.iterrows()):
                # Check stop loss
                if bar["low"] <= stop_loss:
                    return {
                        "profitable": False,
                        "return": (stop_loss - entry_price) / entry_price,
                        "mae": (bar["low"] - entry_price) / entry_price,
                        "bars_held": i + 1,
                    }
                # Check take profit
                if bar["high"] >= take_profit:
                    return {
                        "profitable": True,
                        "return": (take_profit - entry_price) / entry_price,
                        "mae": min(
                            0,
                            (future_data["low"][: i + 1].min() - entry_price)
                            / entry_price,
                        ),
                        "bars_held": i + 1,
                    }
        else:  # SELL
            for i, (timestamp, bar) in enumerate(future_data.iterrows()):
                # Check stop loss
                if bar["high"] >= stop_loss:
                    return {
                        "profitable": False,
                        "return": (entry_price - stop_loss) / entry_price,
                        "mae": (entry_price - bar["high"]) / entry_price,
                        "bars_held": i + 1,
                    }
                # Check take profit
                if bar["low"] <= take_profit:
                    return {
                        "profitable": True,
                        "return": (entry_price - take_profit) / entry_price,
                        "mae": min(
                            0,
                            (entry_price - future_data["high"][: i + 1].max())
                            / entry_price,
                        ),
                        "bars_held": i + 1,
                    }

        # No exit hit - return final P&L
        final_price = future_data["close"].iloc[-1]
        if signal["direction"] == "BUY":
            return_pct = (final_price - entry_price) / entry_price
        else:
            return_pct = (entry_price - final_price) / entry_price

        return {
            "profitable": return_pct > 0,
            "return": return_pct,
            "mae": 0,
            "bars_held": len(future_data),
        }

    def _generate_test_report(self):
        """Generate test report."""
        logger.info(f"\n{'='*60}")
        logger.info("VISUAL VALIDATION TEST RESULTS")
        logger.info(f"{'='*60}\n")

        # Calculate metrics
        with_val = self.test_results["with_validation"]
        without_val = self.test_results["without_validation"]

        if not with_val or not without_val:
            logger.error("No results to analyze")
            return

        # Win rates
        with_val_wins = sum(1 for r in with_val if r["profitable"])
        without_val_wins = sum(1 for r in without_val if r["profitable"])

        with_val_win_rate = with_val_wins / len(with_val) if with_val else 0
        without_val_win_rate = without_val_wins / len(without_val) if without_val else 0

        # Average returns
        with_val_avg_return = (
            np.mean([r["return"] for r in with_val]) if with_val else 0
        )
        without_val_avg_return = (
            np.mean([r["return"] for r in without_val]) if without_val else 0
        )

        logger.info("📊 PERFORMANCE COMPARISON")
        logger.info("-" * 40)
        logger.info(f"{'Metric':<25} {'With Validation':>15} {'Without':>15}")
        logger.info("-" * 40)
        logger.info(f"{'Total Signals':<25} {len(with_val):>15} {len(without_val):>15}")
        logger.info(
            f"{'Win Rate':<25} {with_val_win_rate:>14.1%} {without_val_win_rate:>14.1%}"
        )
        logger.info(
            f"{'Avg Return':<25} {with_val_avg_return:>14.2%} {without_val_avg_return:>14.2%}"
        )
        logger.info(
            f"{'Signal Reduction':<25} {(1 - len(with_val)/len(without_val)):>14.1%} -"
        )

        # Save results
        results_file = f'output/visual_validation_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(results_file, "w") as f:
            json.dump(
                {
                    "summary": {
                        "with_validation_win_rate": with_val_win_rate,
                        "without_validation_win_rate": without_val_win_rate,
                        "with_validation_avg_return": with_val_avg_return,
                        "without_validation_avg_return": without_val_avg_return,
                        "signal_reduction": 1 - len(with_val) / len(without_val),
                    },
                    "detailed_results": self.test_results,
                },
                f,
                indent=2,
                default=str,
            )

        logger.info(f"\n✅ Results saved to: {results_file}")


async def main():
    """Main testing function."""
    tester = SimpleVisualValidationTester()

    # Test on GBPUSD
    await tester.test_visual_validation(
        symbol="GBPUSD", start_date="2024-10-01", end_date="2024-10-31"
    )


if __name__ == "__main__":
    # Run async main
    asyncio.run(main())
