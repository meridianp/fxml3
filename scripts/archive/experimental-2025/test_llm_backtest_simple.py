#!/usr/bin/env python3
"""Simplified LLM-enhanced backtesting demo with Polygon.io data."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Import our modules
from fxml4.data.polygon_official_fetcher import PolygonDataManager
from fxml4.llm_integration.multimodal_mtf_validator import MultiTimeframeChartValidator
from fxml4.utils.timeframe_aggregator import TimeframeAggregator


@dataclass
class BacktestTrade:
    """Simple trade record."""

    timestamp: datetime
    direction: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    llm_confidence: float
    ml_confidence: float


class SimpleLLMBacktester:
    """Simplified backtester with LLM validation."""

    def __init__(self, initial_capital: float = 100000, commission: float = 0.0002):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.commission = commission
        self.trades: List[BacktestTrade] = []
        self.validated_signals = []

    async def run_backtest(
        self,
        symbol: str,
        polygon_symbol: str,
        primary_data: pd.DataFrame,
        historical_data: Dict[str, pd.DataFrame],
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, Any]:
        """Run simplified backtest with LLM validation."""

        # Initialize components
        mtf_validator = MultiTimeframeChartValidator(
            config={
                "timeframes": list(historical_data.keys()),
                "candles_per_timeframe": {"15m": 100, "1H": 100, "4H": 60, "D": 30},
            }
        )

        # Calculate indicators for all timeframes
        logger.info("Calculating indicators...")
        indicators_by_tf = {}
        for tf, data in historical_data.items():
            indicators_by_tf[tf] = self._calculate_indicators(data)

        # Generate and validate signals
        total_signals = 0
        accepted_signals = 0

        logger.info(f"Primary data length: {len(primary_data)}")
        logger.info(f"Checking for signals from index 100 to {len(primary_data)}")

        # Simple signal generation - check every 6 bars (once per day on 4H)
        for i in range(100, len(primary_data), 6):
            current_time = primary_data.index[i]

            # Skip if outside backtest period
            if current_time < start_date or current_time > end_date:
                continue

            # Generate simple signal
            signal = self._generate_signal(primary_data.iloc[: i + 1], current_time)

            if signal:
                total_signals += 1
                logger.info(f"\nValidating signal {total_signals} at {current_time}...")

                # Prepare data for validation
                aligned_data = {}
                aligned_indicators = {}

                for tf, data in historical_data.items():
                    # Get data up to signal time
                    tf_data = data[data.index <= current_time]
                    if len(tf_data) > 100:
                        tf_data = tf_data.tail(100)
                    aligned_data[tf] = tf_data

                    # Align indicators
                    if tf in indicators_by_tf:
                        aligned_indicators[tf] = self._align_indicators(
                            indicators_by_tf[tf], tf_data
                        )

                # Validate with LLM
                try:
                    validation = await mtf_validator.validate_trading_signal_mtf(
                        signal, aligned_data, aligned_indicators
                    )

                    # Record validation
                    self.validated_signals.append(
                        {
                            "timestamp": current_time,
                            "signal": signal,
                            "validation": validation,
                        }
                    )

                    # Execute if valid
                    if (
                        validation.get("valid")
                        and validation.get("llm_confidence", 0) >= 0.6
                    ):
                        accepted_signals += 1
                        logger.info(
                            f"✅ Signal ACCEPTED - LLM: {validation.get('llm_confidence', 0):.1%}"
                        )

                        # Simulate trade
                        self._execute_trade(signal, validation)
                    else:
                        logger.info(
                            f"❌ Signal REJECTED - LLM: {validation.get('llm_confidence', 0):.1%}"
                        )

                except Exception as e:
                    logger.error(f"Validation error: {e}")

        # Calculate results
        results = {
            "total_signals": total_signals,
            "accepted_signals": accepted_signals,
            "rejection_rate": (
                1 - (accepted_signals / total_signals) if total_signals > 0 else 0
            ),
            "total_trades": len(self.trades),
            "winning_trades": len([t for t in self.trades if t.pnl > 0]),
            "losing_trades": len([t for t in self.trades if t.pnl < 0]),
            "total_pnl": sum(t.pnl for t in self.trades),
            "final_capital": self.capital,
            "total_return": (self.capital - self.initial_capital)
            / self.initial_capital,
            "avg_llm_confidence": (
                np.mean(
                    [
                        v["validation"].get("llm_confidence", 0)
                        for v in self.validated_signals
                    ]
                )
                if self.validated_signals
                else 0
            ),
        }

        return results

    def _generate_signal(
        self, data: pd.DataFrame, current_time: datetime
    ) -> Dict[str, Any]:
        """Generate a simple signal with RSI filter."""
        if len(data) < 50:
            return None

        # Calculate indicators
        sma_20 = data["close"].rolling(20).mean()
        sma_50 = data["close"].rolling(50).mean()

        # Calculate RSI
        delta = data["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        current_price = data["close"].iloc[-1]
        current_rsi = rsi.iloc[-1]

        # Buy signal: Golden cross + RSI not overbought
        if (
            sma_20.iloc[-1] > sma_50.iloc[-1]
            and sma_20.iloc[-2] <= sma_50.iloc[-2]
            and current_rsi < 70
        ):

            confidence = (
                0.60 + (70 - current_rsi) / 200
            )  # Higher confidence if RSI lower
            return {
                "symbol": "GBPUSD",
                "direction": "BUY",
                "confidence": confidence,
                "entry_price": current_price,
                "stop_loss": current_price - 0.0050,
                "take_profit": current_price + 0.0100,
                "timeframe": "4H",
                "timestamp": current_time,
                "reason": f"Golden cross + RSI {current_rsi:.0f}",
            }

        # Sell signal: Death cross + RSI not oversold
        elif (
            sma_20.iloc[-1] < sma_50.iloc[-1]
            and sma_20.iloc[-2] >= sma_50.iloc[-2]
            and current_rsi > 30
        ):

            confidence = (
                0.60 + (current_rsi - 30) / 200
            )  # Higher confidence if RSI higher
            return {
                "symbol": "GBPUSD",
                "direction": "SELL",
                "confidence": confidence,
                "entry_price": current_price,
                "stop_loss": current_price + 0.0050,
                "take_profit": current_price - 0.0100,
                "timeframe": "4H",
                "timestamp": current_time,
                "reason": f"Death cross + RSI {current_rsi:.0f}",
            }

        return None

    def _calculate_indicators(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Calculate simple indicators."""
        indicators = {}

        if len(data) >= 20:
            indicators["sma_20"] = data["close"].rolling(20).mean()
        if len(data) >= 50:
            indicators["sma_50"] = data["close"].rolling(50).mean()

        return indicators

    def _align_indicators(
        self, indicators: Dict[str, Any], data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Align indicators to data index."""
        aligned = {}

        for name, ind in indicators.items():
            if isinstance(ind, pd.Series):
                aligned[name] = ind[ind.index.isin(data.index)]
            else:
                aligned[name] = ind

        return aligned

    def _execute_trade(self, signal: Dict[str, Any], validation: Dict[str, Any]):
        """Simulate trade execution."""
        # Simple fixed position sizing
        position_size = 10000  # $10k per trade
        quantity = position_size / signal["entry_price"]

        # Simulate exit at take profit or stop loss (simplified)
        if signal["direction"] == "BUY":
            # 60% chance of hitting TP based on LLM confidence
            if np.random.random() < 0.4 + validation.get("llm_confidence", 0) * 0.2:
                exit_price = signal["take_profit"]
            else:
                exit_price = signal["stop_loss"]
            pnl = (exit_price - signal["entry_price"]) * quantity
        else:
            if np.random.random() < 0.4 + validation.get("llm_confidence", 0) * 0.2:
                exit_price = signal["take_profit"]
            else:
                exit_price = signal["stop_loss"]
            pnl = (signal["entry_price"] - exit_price) * quantity

        # Apply commission
        pnl -= position_size * self.commission * 2  # Entry and exit

        # Record trade
        trade = BacktestTrade(
            timestamp=signal["timestamp"],
            direction=signal["direction"],
            entry_price=signal["entry_price"],
            exit_price=exit_price,
            quantity=quantity,
            pnl=pnl,
            llm_confidence=validation.get("llm_confidence", 0),
            ml_confidence=signal["confidence"],
        )

        self.trades.append(trade)
        self.capital += pnl


async def main():
    """Run the simplified LLM backtest."""
    logger.info("\n" + "=" * 60)
    logger.info("SIMPLIFIED LLM BACKTEST WITH POLYGON.IO DATA")
    logger.info("=" * 60)

    # Check for API key
    polygon_api_key = os.getenv("POLYGON_API_KEY")
    if not polygon_api_key:
        logger.error("POLYGON_API_KEY not found in .env file")
        return

    # Parameters
    symbol = "GBPUSD"
    polygon_symbol = "C:GBPUSD"
    start_date = datetime(2024, 1, 1)  # Full year 2024
    end_date = datetime(2024, 12, 31)
    timeframes = ["15m", "1H", "4H", "D"]

    logger.info(f"\nBacktest Setup:")
    logger.info(f"Symbol: {symbol}")
    logger.info(f"Period: {start_date.date()} to {end_date.date()}")
    logger.info(f"Timeframes: {', '.join(timeframes)}")

    # Fetch data
    logger.info("\nFetching historical data from Polygon.io...")
    data_manager = PolygonDataManager(polygon_api_key)

    # Need more historical data for 50-day SMA
    data_start = start_date - timedelta(days=90)  # 90 days buffer for indicators

    historical_data = data_manager.get_backtest_data(
        polygon_symbol, timeframes, data_start, end_date
    )

    if "4H" not in historical_data:
        logger.error("Failed to fetch 4H data")
        return

    primary_data = historical_data["4H"]
    logger.info(f"Fetched {len(primary_data)} bars of 4H data")

    # Run backtest
    backtester = SimpleLLMBacktester()

    logger.info("\nRunning backtest with LLM validation...")
    results = await backtester.run_backtest(
        symbol, polygon_symbol, primary_data, historical_data, start_date, end_date
    )

    # Display results
    logger.info("\n" + "=" * 60)
    logger.info("BACKTEST RESULTS")
    logger.info("=" * 60)

    logger.info(f"\nSignal Statistics:")
    logger.info(f"Total Signals: {results['total_signals']}")
    if results["total_signals"] > 0:
        logger.info(
            f"Accepted: {results['accepted_signals']} ({results['accepted_signals']/results['total_signals']*100:.1f}%)"
        )
        logger.info(
            f"Rejected: {results['total_signals'] - results['accepted_signals']} ({results['rejection_rate']*100:.1f}%)"
        )
    else:
        logger.info("No signals generated during backtest period")
    logger.info(f"Avg LLM Confidence: {results['avg_llm_confidence']:.1%}")

    logger.info(f"\nTrading Performance:")
    logger.info(f"Total Trades: {results['total_trades']}")
    logger.info(f"Winning Trades: {results['winning_trades']}")
    logger.info(f"Losing Trades: {results['losing_trades']}")
    if results["total_trades"] > 0:
        logger.info(
            f"Win Rate: {results['winning_trades']/results['total_trades']*100:.1f}%"
        )
    logger.info(f"Total PnL: ${results['total_pnl']:,.2f}")
    logger.info(f"Total Return: {results['total_return']:.2%}")
    logger.info(f"Final Capital: ${results['final_capital']:,.2f}")

    # Save results
    output_dir = Path("output/llm_backtest")
    output_dir.mkdir(parents=True, exist_ok=True)

    results_file = (
        output_dir / f'simple_backtest_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    )

    # Prepare serializable results
    save_results = {
        "config": {
            "symbol": symbol,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "timeframes": timeframes,
        },
        "results": results,
        "trades": [
            {
                "timestamp": t.timestamp.isoformat(),
                "direction": t.direction,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "pnl": t.pnl,
                "llm_confidence": t.llm_confidence,
            }
            for t in backtester.trades
        ],
    }

    with open(results_file, "w") as f:
        json.dump(save_results, f, indent=2)

    logger.info(f"\nResults saved to: {results_file}")

    logger.info("\n" + "=" * 60)
    logger.info("BACKTEST COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
