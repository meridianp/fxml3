#!/usr/bin/env python
"""Simple example demonstrating combined backtesting strategy.

This script shows a simplified version of backtesting with a combined strategy.
"""

import logging
import os
import random
import sys
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def generate_synthetic_data(periods=1000, symbol="GBPUSD"):
    """Generate synthetic price data for backtesting.

    Args:
        periods: Number of periods to generate.
        symbol: Trading symbol.

    Returns:
        DataFrame with synthetic data.
    """
    # Set random seed for reproducibility
    np.random.seed(42)

    # Create date range
    dates = pd.date_range(start="2024-01-01", periods=periods, freq="1h")

    # Generate random price data with trend and noise
    base_price = 1.2000  # Starting price for GBPUSD
    trend = np.linspace(0, 0.05, periods) + np.sin(np.linspace(0, 10, periods)) * 0.02
    noise = np.random.normal(0, 0.0010, periods)

    # Calculate OHLC data
    close = base_price + trend + noise
    high = close + np.abs(np.random.normal(0, 0.0015, periods))
    low = close - np.abs(np.random.normal(0, 0.0015, periods))
    open_price = close - np.random.normal(0, 0.0010, periods)

    # Create volume with some randomness
    volume = np.random.normal(1000, 200, periods)
    volume = np.abs(volume) + 100  # Ensure positive values

    # Create DataFrame
    data = pd.DataFrame(
        {
            "time": dates,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "symbol": symbol,
            "timeframe": "1h",
        }
    )

    # Add some basic indicators
    data["sma_10"] = data["close"].rolling(window=10).mean()
    data["sma_20"] = data["close"].rolling(window=20).mean()
    data["rsi"] = calculate_rsi(data["close"], 14)

    logger.info(f"Generated synthetic data, shape: {data.shape}")

    return data


def calculate_rsi(series, period=14):
    """Calculate RSI for a series.

    Args:
        series: Price series.
        period: RSI period.

    Returns:
        Series with RSI values.
    """
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


class Signal:
    """Simple signal class for backtesting."""

    def __init__(
        self,
        symbol,
        side,
        entry_price,
        timestamp,
        stop_loss=None,
        take_profit=None,
        metadata=None,
    ):
        """Initialize a signal.

        Args:
            symbol: Market symbol.
            side: 'buy' or 'sell'.
            entry_price: Signal entry price.
            timestamp: Signal timestamp.
            stop_loss: Optional stop loss price.
            take_profit: Optional take profit price.
            metadata: Optional metadata.
        """
        self.symbol = symbol
        self.side = side  # 'buy' or 'sell'
        self.entry_price = entry_price
        self.timestamp = timestamp
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.metadata = metadata or {}


class Position:
    """Position class for tracking trading positions."""

    def __init__(
        self,
        symbol,
        side,
        entry_price,
        size,
        entry_time,
        stop_loss=None,
        take_profit=None,
    ):
        """Initialize a position.

        Args:
            symbol: Market symbol.
            side: 'buy' or 'sell'.
            entry_price: Entry price.
            size: Position size.
            entry_time: Entry timestamp.
            stop_loss: Optional stop loss price.
            take_profit: Optional take profit price.
        """
        self.symbol = symbol
        self.side = side
        self.entry_price = entry_price
        self.size = size
        self.entry_time = entry_time
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.exit_price = None
        self.exit_time = None
        self.pnl = 0.0
        self.exit_reason = None

    def calculate_pnl(self, current_price):
        """Calculate unrealized P&L.

        Args:
            current_price: Current market price.

        Returns:
            Unrealized P&L.
        """
        if self.side == "buy":
            return (current_price - self.entry_price) * self.size
        else:  # 'sell'
            return (self.entry_price - current_price) * self.size


class CombinedBacktester:
    """Combined backtester implementing ML, sentiment and wave strategies."""

    def __init__(self, initial_capital=10000.0, commission=0.0001):
        """Initialize the backtester.

        Args:
            initial_capital: Initial capital.
            commission: Commission as percentage.
        """
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.equity = initial_capital
        self.commission = commission
        self.positions = {}  # symbol -> Position
        self.closed_positions = []
        self.equity_curve = []
        self.current_bars = {}  # symbol -> current bar

        # Signal weights for different sources
        self.signal_weights = {
            "ml": 0.4,
            "sentiment": 0.2,
            "wave_pattern": 0.4,
        }

        # Configure strategy parameters
        self.min_signal_strength = 0.7
        self.min_consensus_count = 2  # Minimum number of agreeing signals
        self.require_consensus = True
        self.use_adaptive_weights = True
        self.signal_cooldown = 12  # Hours between signals

    def _generate_ml_signals(self, data):
        """Generate ML-based signals.

        Args:
            data: Market data DataFrame.

        Returns:
            List of signals.
        """
        signals = []

        # Simple moving average crossover (proxy for ML model)
        for i in range(1, len(data)):
            prev = data.iloc[i - 1]
            curr = data.iloc[i]
            symbol = curr["symbol"]
            timestamp = (
                curr.name if isinstance(curr.name, pd.Timestamp) else curr["time"]
            )

            # Buy signal: SMA 10 crosses above SMA 20
            if prev["sma_10"] <= prev["sma_20"] and curr["sma_10"] > curr["sma_20"]:
                # Calculate stop loss and take profit
                stop_loss = curr["low"] * 0.995  # 0.5% below current low
                take_profit = curr["close"] * 1.015  # 1.5% above current close

                signal = Signal(
                    symbol=symbol,
                    side="buy",
                    entry_price=curr["close"],
                    timestamp=timestamp,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    metadata={
                        "source": "ml",
                        "strength": 0.8,
                        "description": "ML model predicted uptrend",
                        "features": {
                            "sma_diff": curr["sma_10"] - curr["sma_20"],
                            "rsi": curr["rsi"],
                        },
                    },
                )
                signals.append(signal)

            # Sell signal: SMA 10 crosses below SMA 20
            elif prev["sma_10"] >= prev["sma_20"] and curr["sma_10"] < curr["sma_20"]:
                # Calculate stop loss and take profit
                stop_loss = curr["high"] * 1.005  # 0.5% above current high
                take_profit = curr["close"] * 0.985  # 1.5% below current close

                signal = Signal(
                    symbol=symbol,
                    side="sell",
                    entry_price=curr["close"],
                    timestamp=timestamp,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    metadata={
                        "source": "ml",
                        "strength": 0.7,
                        "description": "ML model predicted downtrend",
                        "features": {
                            "sma_diff": curr["sma_10"] - curr["sma_20"],
                            "rsi": curr["rsi"],
                        },
                    },
                )
                signals.append(signal)

        return signals

    def _generate_sentiment_signals(self, data):
        """Generate sentiment-based signals.

        Args:
            data: Market data DataFrame.

        Returns:
            List of signals.
        """
        signals = []

        # Use RSI as a proxy for sentiment in this example
        for i in range(1, len(data)):
            curr = data.iloc[i]
            symbol = curr["symbol"]
            timestamp = (
                curr.name if isinstance(curr.name, pd.Timestamp) else curr["time"]
            )

            # Occasional sentiment signals (every 75 bars)
            if i % 75 == 0:
                rsi = curr["rsi"]

                # Oversold: Strong buy signal
                if rsi < 30:
                    stop_loss = curr["low"] * 0.99  # 1% below current low
                    take_profit = curr["close"] * 1.02  # 2% above current close

                    signal = Signal(
                        symbol=symbol,
                        side="buy",
                        entry_price=curr["close"],
                        timestamp=timestamp,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        metadata={
                            "source": "sentiment",
                            "strength": 0.85,
                            "description": "Positive market sentiment detected",
                            "sentiment_score": 0.7,
                        },
                    )
                    signals.append(signal)

                # Overbought: Strong sell signal
                elif rsi > 70:
                    stop_loss = curr["high"] * 1.01  # 1% above current high
                    take_profit = curr["close"] * 0.98  # 2% below current close

                    signal = Signal(
                        symbol=symbol,
                        side="sell",
                        entry_price=curr["close"],
                        timestamp=timestamp,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        metadata={
                            "source": "sentiment",
                            "strength": 0.8,
                            "description": "Negative market sentiment detected",
                            "sentiment_score": -0.6,
                        },
                    )
                    signals.append(signal)

        return signals

    def _generate_wave_signals(self, data):
        """Generate Elliott Wave-based signals.

        Args:
            data: Market data DataFrame.

        Returns:
            List of signals.
        """
        signals = []

        # Wave patterns appear less frequently but are higher confidence
        for i in range(1, len(data)):
            curr = data.iloc[i]
            symbol = curr["symbol"]
            timestamp = (
                curr.name if isinstance(curr.name, pd.Timestamp) else curr["time"]
            )

            # Only generate wave patterns occasionally (roughly 5-10 per 1000 bars)
            # And with more randomness to simulate real pattern detection
            if i % 100 == 0 and random.random() > 0.6:
                # Determine if bullish or bearish pattern (affected by trend)
                trend_direction = 1 if curr["sma_10"] > curr["sma_20"] else -1
                rand_factor = random.random()

                # Bias the pattern direction based on the trend (70% same direction, 30% counter-trend)
                if (trend_direction == 1 and rand_factor < 0.7) or (
                    trend_direction == -1 and rand_factor >= 0.7
                ):
                    side = "buy"
                    pattern_types = [
                        "impulse_end_5",
                        "correction_end_c",
                        "diagonal_end",
                        "triangle_end",
                        "impulse_start",
                    ]

                    # Use wider stops and higher targets for wave signals
                    stop_loss = curr["close"] * 0.985  # 1.5% below
                    take_profit = curr["close"] * 1.035  # 3.5% above
                else:
                    side = "sell"
                    pattern_types = [
                        "impulse_end_5",
                        "correction_start",
                        "diagonal_end",
                        "expanding_triangle_end",
                        "impulse_failure",
                    ]

                    # Use wider stops and higher targets for wave signals
                    stop_loss = curr["close"] * 1.015  # 1.5% above
                    take_profit = curr["close"] * 0.965  # 3.5% below

                # Select random pattern type but weight toward more reliable patterns
                pattern_type = random.choices(
                    pattern_types, weights=[0.4, 0.3, 0.15, 0.1, 0.05], k=1
                )[0]

                # Higher confidence for wave signals
                confidence = 0.7 + (random.random() * 0.25)  # 0.7 to 0.95

                signal = Signal(
                    symbol=symbol,
                    side=side,
                    entry_price=curr["close"],
                    timestamp=timestamp,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    metadata={
                        "source": "wave_pattern",
                        "strength": confidence,
                        "pattern_type": pattern_type,
                        "description": f"Elliott Wave {pattern_type} detected",
                        "wave_confidence": confidence,
                        "sentiment_correlation": 0.8 if random.random() > 0.3 else 0.5,
                    },
                )
                signals.append(signal)

        return signals

    def _adapt_weights_to_market(self, data):
        """Adapt signal weights based on market regime.

        Args:
            data: Market data.

        Returns:
            Dictionary of adapted weights.
        """
        if not self.use_adaptive_weights:
            return self.signal_weights

        # Use last 50 bars to analyze regime
        recent_data = data.iloc[-50:] if len(data) >= 50 else data

        # Calculate simple metrics to detect regime
        price_changes = recent_data["close"].pct_change().dropna()
        volatility = price_changes.std() * np.sqrt(252)  # Annualized

        # Check for trend - using simple SMA comparison
        last_bar = data.iloc[-1]
        trend_strength = (
            abs(last_bar["sma_10"] - last_bar["sma_20"]) / last_bar["close"]
        )

        # Determine regime
        if trend_strength > 0.005:  # Strong trend
            # In trending markets, ML models often perform better
            return {"ml": 0.5, "sentiment": 0.2, "wave_pattern": 0.3}
        elif volatility > 0.2:  # High volatility
            # In volatile markets, Elliott Wave patterns are more reliable
            return {"ml": 0.3, "sentiment": 0.2, "wave_pattern": 0.5}
        else:  # Ranging/sideways market
            # In ranging markets, use balanced approach
            return {"ml": 0.3, "sentiment": 0.3, "wave_pattern": 0.4}

    def _combine_signals(
        self, ml_signals, sentiment_signals, wave_signals, bar_idx, data
    ):
        """Combine signals from multiple sources with weighted approach.

        Args:
            ml_signals: ML-based signals.
            sentiment_signals: Sentiment-based signals.
            wave_signals: Wave-based signals.
            bar_idx: Current bar index.
            data: Market data DataFrame.

        Returns:
            List of combined signals.
        """
        combined_signals = []
        curr = data.iloc[bar_idx]
        timestamp = curr.name if isinstance(curr.name, pd.Timestamp) else curr["time"]
        symbol = curr["symbol"]

        # Adapt weights to market conditions
        weights = self._adapt_weights_to_market(data.iloc[: bar_idx + 1])

        # Group signals by side (buy/sell)
        buy_signals = {
            "ml": [
                s for s in ml_signals if s.side == "buy" and s.timestamp == timestamp
            ],
            "sentiment": [
                s
                for s in sentiment_signals
                if s.side == "buy" and s.timestamp == timestamp
            ],
            "wave_pattern": [
                s for s in wave_signals if s.side == "buy" and s.timestamp == timestamp
            ],
        }

        sell_signals = {
            "ml": [
                s for s in ml_signals if s.side == "sell" and s.timestamp == timestamp
            ],
            "sentiment": [
                s
                for s in sentiment_signals
                if s.side == "sell" and s.timestamp == timestamp
            ],
            "wave_pattern": [
                s for s in wave_signals if s.side == "sell" and s.timestamp == timestamp
            ],
        }

        # Process buy signals
        if any(len(sigs) > 0 for sigs in buy_signals.values()):
            # Check for consensus if required
            agreeing_sources = sum(
                1 for src, sigs in buy_signals.items() if len(sigs) > 0
            )

            if (
                not self.require_consensus
                or agreeing_sources >= self.min_consensus_count
            ):
                # Calculate weighted strength
                total_weight = 0
                weighted_strength = 0

                for src, sigs in buy_signals.items():
                    if len(sigs) > 0:
                        # Use strongest signal from each source
                        strongest = max(
                            sigs, key=lambda s: s.metadata.get("strength", 0)
                        )
                        src_weight = weights.get(src, 0.33)
                        weighted_strength += (
                            strongest.metadata.get("strength", 0.5) * src_weight
                        )
                        total_weight += src_weight

                if total_weight > 0:
                    combined_strength = weighted_strength / total_weight

                    # Only generate signal if combined strength is above threshold
                    if combined_strength >= self.min_signal_strength:
                        # Prioritize stop loss from wave signals if available
                        stop_loss = None
                        take_profit = None

                        # First check wave signals for stop levels
                        if buy_signals["wave_pattern"]:
                            wave_signal = max(
                                buy_signals["wave_pattern"],
                                key=lambda s: s.metadata.get("strength", 0),
                            )
                            stop_loss = wave_signal.stop_loss
                            take_profit = wave_signal.take_profit

                        # If no wave signal, use ML signal levels
                        elif buy_signals["ml"]:
                            ml_signal = max(
                                buy_signals["ml"],
                                key=lambda s: s.metadata.get("strength", 0),
                            )
                            stop_loss = ml_signal.stop_loss
                            take_profit = ml_signal.take_profit

                        # If still no levels, use sentiment signal levels
                        elif buy_signals["sentiment"]:
                            sent_signal = max(
                                buy_signals["sentiment"],
                                key=lambda s: s.metadata.get("strength", 0),
                            )
                            stop_loss = sent_signal.stop_loss
                            take_profit = sent_signal.take_profit

                        # Create combined signal
                        combined_signal = Signal(
                            symbol=symbol,
                            side="buy",
                            entry_price=curr["close"],
                            timestamp=timestamp,
                            stop_loss=stop_loss,
                            take_profit=take_profit,
                            metadata={
                                "source": "combined",
                                "strength": combined_strength,
                                "description": "Combined signal (buy)",
                                "agreeing_sources": agreeing_sources,
                                "weights": weights,
                                "component_signals": {
                                    "ml": len(buy_signals["ml"]),
                                    "sentiment": len(buy_signals["sentiment"]),
                                    "wave_pattern": len(buy_signals["wave_pattern"]),
                                },
                            },
                        )
                        combined_signals.append(combined_signal)

        # Process sell signals
        if any(len(sigs) > 0 for sigs in sell_signals.values()):
            # Check for consensus if required
            agreeing_sources = sum(
                1 for src, sigs in sell_signals.items() if len(sigs) > 0
            )

            if (
                not self.require_consensus
                or agreeing_sources >= self.min_consensus_count
            ):
                # Calculate weighted strength
                total_weight = 0
                weighted_strength = 0

                for src, sigs in sell_signals.items():
                    if len(sigs) > 0:
                        # Use strongest signal from each source
                        strongest = max(
                            sigs, key=lambda s: s.metadata.get("strength", 0)
                        )
                        src_weight = weights.get(src, 0.33)
                        weighted_strength += (
                            strongest.metadata.get("strength", 0.5) * src_weight
                        )
                        total_weight += src_weight

                if total_weight > 0:
                    combined_strength = weighted_strength / total_weight

                    # Only generate signal if combined strength is above threshold
                    if combined_strength >= self.min_signal_strength:
                        # Prioritize stop loss from wave signals if available
                        stop_loss = None
                        take_profit = None

                        # First check wave signals for stop levels
                        if sell_signals["wave_pattern"]:
                            wave_signal = max(
                                sell_signals["wave_pattern"],
                                key=lambda s: s.metadata.get("strength", 0),
                            )
                            stop_loss = wave_signal.stop_loss
                            take_profit = wave_signal.take_profit

                        # If no wave signal, use ML signal levels
                        elif sell_signals["ml"]:
                            ml_signal = max(
                                sell_signals["ml"],
                                key=lambda s: s.metadata.get("strength", 0),
                            )
                            stop_loss = ml_signal.stop_loss
                            take_profit = ml_signal.take_profit

                        # If still no levels, use sentiment signal levels
                        elif sell_signals["sentiment"]:
                            sent_signal = max(
                                sell_signals["sentiment"],
                                key=lambda s: s.metadata.get("strength", 0),
                            )
                            stop_loss = sent_signal.stop_loss
                            take_profit = sent_signal.take_profit

                        # Create combined signal
                        combined_signal = Signal(
                            symbol=symbol,
                            side="sell",
                            entry_price=curr["close"],
                            timestamp=timestamp,
                            stop_loss=stop_loss,
                            take_profit=take_profit,
                            metadata={
                                "source": "combined",
                                "strength": combined_strength,
                                "description": "Combined signal (sell)",
                                "agreeing_sources": agreeing_sources,
                                "weights": weights,
                                "component_signals": {
                                    "ml": len(sell_signals["ml"]),
                                    "sentiment": len(sell_signals["sentiment"]),
                                    "wave_pattern": len(sell_signals["wave_pattern"]),
                                },
                            },
                        )
                        combined_signals.append(combined_signal)

        return combined_signals

    def generate_signals(self, data):
        """Generate trading signals from data.

        This method generates signals from three separate sources (ML, sentiment,
        and Elliott Wave) and combines them using an adaptive weighting approach.

        Args:
            data: Market data DataFrame.

        Returns:
            List of signals.
        """
        # Generate signals from each source
        ml_signals = self._generate_ml_signals(data)
        sentiment_signals = self._generate_sentiment_signals(data)
        wave_signals = self._generate_wave_signals(data)

        # Collection for combined signals
        combined_signals = []

        # Keep track of the last signal time to implement cooldown
        last_signal_time = None

        # For each bar, check for and combine signals
        for i in range(1, len(data)):
            curr = data.iloc[i]
            timestamp = (
                curr.name if isinstance(curr.name, pd.Timestamp) else curr["time"]
            )

            # Apply signal cooldown
            if last_signal_time is not None:
                time_diff = (
                    timestamp - last_signal_time
                ).total_seconds() / 3600  # hours
                if time_diff < self.signal_cooldown:
                    continue

            # Combine signals for this bar
            bar_combined = self._combine_signals(
                ml_signals, sentiment_signals, wave_signals, i, data
            )

            # If we have combined signals, update the last signal time
            if bar_combined:
                last_signal_time = timestamp
                combined_signals.extend(bar_combined)

        # Include all original signals for analysis purposes
        all_signals = []
        all_signals.extend(ml_signals)
        all_signals.extend(sentiment_signals)
        all_signals.extend(wave_signals)
        all_signals.extend(combined_signals)

        return all_signals

    def execute_signal(self, signal, data_idx, data):
        """Execute a trading signal.

        Args:
            signal: Trading signal.
            data_idx: Current data index.
            data: Market data.
        """
        symbol = signal.symbol
        side = signal.side
        entry_price = signal.entry_price
        timestamp = signal.timestamp

        # Check if we already have a position in this symbol
        if symbol in self.positions:
            current_position = self.positions[symbol]

            # If the signal is in the opposite direction, close the current position
            if current_position.side != side:
                self._close_position(
                    symbol,
                    entry_price,
                    timestamp,
                    f"Reversed by {signal.metadata.get('source', 'unknown')} signal",
                )
            else:
                # Same direction, ignore
                return

        # Calculate position size (2% risk or fixed size)
        # Use more conservative position sizing to make results more realistic
        if signal.stop_loss is not None:
            risk_per_share = abs(entry_price - signal.stop_loss)
            if risk_per_share > 0:
                risk_amount = min(self.equity * 0.02, 10000)  # 2% risk, max $10k
                size = risk_amount / risk_per_share

                # Limit position size to be realistic
                max_size = min(self.equity * 0.2, 100000) / entry_price
                size = min(size, max_size)
            else:
                size = (
                    min(self.equity * 0.05, 5000) / entry_price
                )  # 5% of equity, max $5k
        else:
            size = min(self.equity * 0.05, 5000) / entry_price  # 5% of equity, max $5k

        # Apply commission
        commission_amount = entry_price * size * self.commission
        self.capital -= commission_amount

        # Create new position
        self.positions[symbol] = Position(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            size=size,
            entry_time=timestamp,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
        )

        # Update capital
        if side == "buy":
            self.capital -= entry_price * size
        else:  # 'sell'
            self.capital += entry_price * size

        logger.debug(
            f"Opened {side} position for {symbol} at {entry_price} ({size} units)"
        )

    def _close_position(self, symbol, exit_price, exit_time, reason):
        """Close a position.

        Args:
            symbol: Market symbol.
            exit_price: Exit price.
            exit_time: Exit timestamp.
            reason: Exit reason.
        """
        if symbol not in self.positions:
            return

        position = self.positions[symbol]
        position.exit_price = exit_price
        position.exit_time = exit_time
        position.exit_reason = reason

        # Calculate PnL
        if position.side == "buy":
            position.pnl = (exit_price - position.entry_price) * position.size
        else:  # 'sell'
            position.pnl = (position.entry_price - exit_price) * position.size

        # Apply commission
        commission_amount = exit_price * position.size * self.commission
        position.pnl -= commission_amount
        self.capital -= commission_amount

        # Update capital
        if position.side == "buy":
            self.capital += exit_price * position.size
        else:  # 'sell'
            self.capital -= exit_price * position.size

        # Add to closed positions and remove from open positions
        self.closed_positions.append(position)
        del self.positions[symbol]

        logger.debug(
            f"Closed {position.side} position for {symbol} at {exit_price} "
            f"(PnL: {position.pnl:.2f}, reason: {reason})"
        )

    def _update_positions(self, current_bar):
        """Update positions with current market data.

        Args:
            current_bar: Current price data.
        """
        symbol = current_bar["symbol"]
        current_price = current_bar["close"]
        timestamp = (
            current_bar.name
            if isinstance(current_bar.name, pd.Timestamp)
            else current_bar["time"]
        )

        # Update current bars dictionary
        self.current_bars[symbol] = current_bar

        # Check if we have a position in this symbol
        if symbol not in self.positions:
            return

        position = self.positions[symbol]

        # Check stop loss
        if position.stop_loss is not None:
            if (position.side == "buy" and current_price <= position.stop_loss) or (
                position.side == "sell" and current_price >= position.stop_loss
            ):
                self._close_position(
                    symbol, current_price, timestamp, "Stop loss triggered"
                )
                return

        # Check take profit
        if position.take_profit is not None:
            if (position.side == "buy" and current_price >= position.take_profit) or (
                position.side == "sell" and current_price <= position.take_profit
            ):
                self._close_position(
                    symbol, current_price, timestamp, "Take profit triggered"
                )
                return

        # Update trailing stop (very simple implementation)
        if position.side == "buy" and position.stop_loss is not None:
            new_stop = current_bar["low"] * 0.995  # 0.5% below current low
            if new_stop > position.stop_loss:
                position.stop_loss = new_stop

        elif position.side == "sell" and position.stop_loss is not None:
            new_stop = current_bar["high"] * 1.005  # 0.5% above current high
            if new_stop < position.stop_loss:
                position.stop_loss = new_stop

    def _update_equity(self):
        """Update portfolio equity."""
        # Equity = current capital + value of open positions
        self.equity = self.capital

        for symbol, position in self.positions.items():
            # Calculate unrealized PnL
            current_price = self.current_bars.get(symbol, {}).get(
                "close", position.entry_price
            )
            unrealized_pnl = position.calculate_pnl(current_price)

            # Update position PnL
            position.pnl = unrealized_pnl

            # Add to equity
            self.equity += unrealized_pnl

    def backtest(self, data):
        """Run backtest on provided data.

        Args:
            data: Market data.

        Returns:
            Dictionary with backtest results.
        """
        # Generate signals
        signals = self.generate_signals(data)
        signal_idx = 0

        # Reset state
        self.capital = self.initial_capital
        self.equity = self.initial_capital
        self.positions = {}
        self.closed_positions = []
        self.equity_curve = []

        # Process each bar
        for i in range(len(data)):
            current_bar = data.iloc[i]
            timestamp = (
                current_bar.name
                if isinstance(current_bar.name, pd.Timestamp)
                else current_bar["time"]
            )

            # Update existing positions
            self._update_positions(current_bar)

            # Check for signals at this timestamp
            while (
                signal_idx < len(signals) and signals[signal_idx].timestamp <= timestamp
            ):
                signal = signals[signal_idx]
                self.execute_signal(signal, i, data)
                signal_idx += 1

            # Update equity
            self._update_equity()

            # Add to equity curve
            self.equity_curve.append(
                {
                    "timestamp": timestamp,
                    "equity": self.equity,
                    "capital": self.capital,
                }
            )

        # Close any remaining positions at the end
        for symbol in list(self.positions.keys()):
            last_bar = data.iloc[-1]
            exit_price = last_bar["close"]
            exit_time = (
                last_bar.name
                if isinstance(last_bar.name, pd.Timestamp)
                else last_bar["time"]
            )
            self._close_position(symbol, exit_price, exit_time, "End of backtest")

        # Calculate final equity
        self._update_equity()

        # Prepare results
        results = {
            "initial_capital": self.initial_capital,
            "final_capital": self.capital,
            "final_equity": self.equity,
            "return_pct": (self.equity / self.initial_capital - 1) * 100,
            "closed_positions": self.closed_positions,
            "equity_curve": pd.DataFrame(self.equity_curve),
            "signals": signals,
            "data": data,  # Include original data
        }

        # Add some performance metrics
        if self.closed_positions:
            results["total_trades"] = len(self.closed_positions)
            results["win_count"] = sum(1 for p in self.closed_positions if p.pnl > 0)
            results["loss_count"] = results["total_trades"] - results["win_count"]
            results["win_rate"] = (
                results["win_count"] / results["total_trades"]
                if results["total_trades"] > 0
                else 0
            )
            results["avg_profit"] = (
                sum(p.pnl for p in self.closed_positions if p.pnl > 0)
                / results["win_count"]
                if results["win_count"] > 0
                else 0
            )
            results["avg_loss"] = (
                sum(p.pnl for p in self.closed_positions if p.pnl <= 0)
                / results["loss_count"]
                if results["loss_count"] > 0
                else 0
            )

            # Calculate drawdown
            if not results["equity_curve"].empty:
                equity_series = results["equity_curve"]["equity"]
                peak = equity_series.expanding().max()
                drawdown = (equity_series - peak) / peak
                results["max_drawdown_pct"] = drawdown.min() * 100

        return results


def plot_backtest_results(results):
    """Plot backtest results.

    Args:
        results: Dictionary with backtest results.
    """
    # Create figure
    fig, axes = plt.subplots(
        4, 1, figsize=(12, 22), gridspec_kw={"height_ratios": [3, 1, 1, 2]}
    )

    # Plot equity curve
    equity_curve = results["equity_curve"]
    axes[0].plot(equity_curve["timestamp"], equity_curve["equity"], label="Equity")
    axes[0].set_title("Equity Curve")
    axes[0].set_xlabel("Date")
    axes[0].set_ylabel("Equity ($)")
    axes[0].grid(True)
    axes[0].legend()

    # Plot drawdown
    equity_series = equity_curve["equity"]
    peak = equity_series.expanding().max()
    drawdown = (equity_series - peak) / peak * 100  # Convert to percentage

    axes[1].fill_between(equity_curve["timestamp"], 0, drawdown, color="red", alpha=0.3)
    axes[1].set_title("Drawdown")
    axes[1].set_xlabel("Date")
    axes[1].set_ylabel("Drawdown (%)")
    axes[1].grid(True)

    # Plot trade PnL
    closed_positions = results["closed_positions"]
    if closed_positions:
        trade_data = [
            {"entry_time": p.entry_time, "pnl": p.pnl, "side": p.side}
            for p in closed_positions
        ]
        trades_df = pd.DataFrame(trade_data)

        # Plot PnL per trade
        axes[2].bar(
            range(len(trades_df)),
            trades_df["pnl"],
            color=trades_df["pnl"].apply(lambda x: "green" if x > 0 else "red"),
        )
        axes[2].set_title("Trade PnL")
        axes[2].set_xlabel("Trade #")
        axes[2].set_ylabel("PnL ($)")
        axes[2].grid(True)

    # Plot signals by source
    signals = results["signals"]
    if signals:
        # Group signals by type
        signal_groups = {}
        for signal in signals:
            source = signal.metadata.get("source", "unknown")
            if source not in signal_groups:
                signal_groups[source] = []
            signal_groups[source].append(signal)

        # Create a dataframe for each signal source
        signal_dfs = {}
        for source, group_signals in signal_groups.items():
            source_data = [
                {
                    "timestamp": s.timestamp,
                    "side": s.side,
                    "strength": s.metadata.get("strength", 0.5),
                    "price": s.entry_price,
                }
                for s in group_signals
            ]
            if source_data:  # Check if empty
                signal_dfs[source] = pd.DataFrame(source_data)

        # Plot price on the bottom chart
        if "data" in results and not results["equity_curve"].empty:
            data = results["data"]
            equity_dates = results["equity_curve"]["timestamp"]

            # Sample some points from the equity curve timestamps
            sample_indices = np.linspace(
                0, len(equity_dates) - 1, min(len(equity_dates), 100)
            ).astype(int)
            sample_dates = equity_dates.iloc[sample_indices]

            # Find closest data points to sampled dates
            price_data = []
            for date in sample_dates:
                closest_idx = (data["time"] - date).abs().idxmin()
                price_data.append(
                    {"timestamp": date, "close": data.iloc[closest_idx]["close"]}
                )

            price_df = pd.DataFrame(price_data)
            axes[3].plot(
                price_df["timestamp"],
                price_df["close"],
                color="black",
                linewidth=1.5,
                label="Price",
            )

            # Plot signals on the price chart
            colors = {
                "ml": "blue",
                "sentiment": "green",
                "wave_pattern": "red",
                "combined": "purple",
                "unknown": "gray",
            }
            markers = {"buy": "^", "sell": "v"}
            sizes = {True: 120, False: 80}  # Larger for combined signals

            for source, df in signal_dfs.items():
                for _, row in df.iterrows():
                    axes[3].scatter(
                        row["timestamp"],
                        row["price"],
                        color=colors.get(source, "gray"),
                        marker=markers.get(row["side"], "o"),
                        s=sizes.get(source == "combined", 80),
                        alpha=min(1.0, row["strength"] + 0.3),
                        label=(
                            f"{source} ({row['side']})"
                            if source
                            not in [
                                s.get_label().split(" ")[0] for s in axes[3].collections
                            ]
                            else ""
                        ),
                    )

            # Add legend but only with unique entries
            handles, labels = axes[3].get_legend_handles_labels()
            by_label = dict(zip(labels, handles))
            axes[3].legend(by_label.values(), by_label.keys(), loc="upper left")

            axes[3].set_title("Price Chart with Signals")
            axes[3].set_xlabel("Date")
            axes[3].set_ylabel("Price")
            axes[3].grid(True)

    # Adjust layout and save
    plt.tight_layout()
    result_dir = Path("output/simple_backtest_results")
    result_dir.mkdir(exist_ok=True, parents=True)

    # Save figure
    plt.savefig(
        result_dir / f"backtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    )

    # Show figure
    if plt.isinteractive():
        plt.show()


def main():
    """Main function."""
    # Generate synthetic data
    data = generate_synthetic_data(periods=1000)

    # Create backtester
    backtester = CombinedBacktester(initial_capital=10000.0, commission=0.0001)

    # Run backtest
    logger.info("Starting backtest...")
    results = backtester.backtest(data)
    logger.info(f"Backtest completed. Final equity: ${results['final_equity']:.2f}")

    # Plot results
    plot_backtest_results(results)

    # Print summary
    print("\n=== Backtest Results Summary ===")
    print(f"Initial capital: ${results['initial_capital']:.2f}")
    print(f"Final capital: ${results['final_capital']:.2f}")
    print(f"Final equity: ${results['final_equity']:.2f}")
    print(f"Total return: {results['return_pct']:.2f}%")
    print(f"Max drawdown: {results.get('max_drawdown_pct', 0):.2f}%")
    if "win_rate" in results:
        print(f"Win rate: {results['win_rate']*100:.2f}%")
    print(f"Total trades: {results.get('total_trades', 0)}")

    # Show signal source stats
    signal_sources = {}
    for s in results["signals"]:
        source = s.metadata.get("source", "unknown")
        signal_sources[source] = signal_sources.get(source, 0) + 1

    print("\n=== Signal Source Statistics ===")
    for source, count in signal_sources.items():
        print(f"{source}: {count} signals")

    # Show exit reason stats
    exit_reasons = {}
    for p in results["closed_positions"]:
        reason = p.exit_reason
        exit_reasons[reason] = exit_reasons.get(reason, 0) + 1

    print("\n=== Exit Reason Statistics ===")
    for reason, count in exit_reasons.items():
        print(f"{reason}: {count} exits")

    print("===============================\n")


if __name__ == "__main__":
    main()
