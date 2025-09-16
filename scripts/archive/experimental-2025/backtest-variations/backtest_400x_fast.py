#!/usr/bin/env python3
"""Fast aggressive backtest without LLM validation for quick results."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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

# Import FXML4 modules
from fxml4.data.polygon_official_fetcher import PolygonDataManager
from fxml4.features.feature_engineering import UnifiedFeatureEngineer
from fxml4.ml.features import create_basic_technical_features
from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer
from fxml4.wave_analysis.fibonacci import FibonacciCalculator


@dataclass
class FastTrade:
    """Trade record for fast backtesting."""

    timestamp: datetime
    direction: str
    entry_price: float
    exit_price: float
    position_size: float
    lots: float
    leverage_used: float
    pnl: float
    pnl_pips: float
    confidence: float
    signal_source: str
    exit_reason: str
    drawdown_at_entry: float


class FastAggressiveBacktester:
    """Fast aggressive backtesting without LLM validation."""

    def __init__(
        self,
        initial_capital: float = 10000,
        max_leverage: float = 400.0,
        target_leverage: float = 50.0,
        min_lot_size: float = 1.0,
        commission_per_lot: float = 0.02,
        max_risk_per_trade: float = 0.05,
        max_drawdown_limit: float = 0.25,
        polygon_api_key: Optional[str] = None,
    ):
        """Initialize fast backtesting system."""
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.max_leverage = max_leverage
        self.target_leverage = target_leverage
        self.min_lot_size = min_lot_size
        self.commission_per_lot = commission_per_lot
        self.max_risk_per_trade = max_risk_per_trade
        self.max_drawdown_limit = max_drawdown_limit

        # Initialize components
        self.polygon_manager = PolygonDataManager(polygon_api_key)

        # Trading records
        self.trades: List[FastTrade] = []
        self.open_positions: Dict[str, Any] = {}
        self.equity_curve = []
        self.max_drawdown = 0
        self.current_drawdown = 0
        self.peak_equity = initial_capital
        self.consecutive_losses = 0
        self.max_concurrent_positions = 10

    async def run_backtest(
        self, symbol: str, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Run fast aggressive backtest."""
        polygon_symbol = f"C:{symbol}"

        logger.info(f"\n{'='*60}")
        logger.info("FAST AGGRESSIVE BACKTEST - NO LLM VALIDATION")
        logger.info(f"{'='*60}")
        logger.info(f"Symbol: {symbol}")
        logger.info(f"Period: {start_date.date()} to {end_date.date()}")
        logger.info(f"Initial Capital: ${self.initial_capital:,.2f}")
        logger.info(f"Target Leverage: {self.target_leverage}:1")

        # Fetch only 4H data for speed
        logger.info("\nFetching 4H data from Polygon.io...")

        historical_data = self.polygon_manager.get_backtest_data(
            polygon_symbol, ["4H"], start_date - timedelta(days=100), end_date
        )

        if "4H" not in historical_data:
            logger.error("Failed to fetch data")
            return {}

        primary_data = historical_data["4H"]
        logger.info(f"Loaded {len(primary_data)} bars of 4H data")

        # Calculate basic features only
        logger.info("\nCalculating technical indicators...")
        features_df = create_basic_technical_features(primary_data)

        # Process signals
        total_signals = 0
        executed_trades = 0

        # Check every bar for signals
        for i in range(200, len(primary_data)):
            current_time = primary_data.index[i]

            # Skip if outside backtest period
            if current_time < start_date or current_time > end_date:
                continue

            # Update equity tracking
            current_equity = self._calculate_current_equity(primary_data.iloc[i])
            self.equity_curve.append(
                {"timestamp": current_time, "equity": current_equity}
            )

            # Update drawdown
            if current_equity > self.peak_equity:
                self.peak_equity = current_equity
            self.current_drawdown = (
                self.peak_equity - current_equity
            ) / self.peak_equity
            self.max_drawdown = max(self.max_drawdown, self.current_drawdown)

            # Check drawdown limit
            if self.current_drawdown >= self.max_drawdown_limit:
                if self.open_positions:
                    logger.warning(
                        f"Drawdown limit hit ({self.current_drawdown:.1%}), closing all positions"
                    )
                    self._close_all_positions(primary_data.iloc[i], current_time)
                continue

            # Dynamic position limit
            max_positions = self._calculate_dynamic_position_limit()
            if len(self.open_positions) >= max_positions:
                continue

            # Generate multiple signals
            signals = self._generate_fast_signals(
                features_df.iloc[: i + 1], current_time, primary_data.iloc[i]
            )

            # Process each signal
            for signal in signals:
                if signal:
                    total_signals += 1

                    # Check position limits
                    same_direction_positions = [
                        p
                        for p in self.open_positions.values()
                        if p["signal"]["direction"] == signal["direction"]
                    ]
                    if len(same_direction_positions) >= 3:
                        continue

                    # Calculate position size
                    position_details = self._calculate_aggressive_position(
                        signal, primary_data.iloc[i]
                    )

                    if position_details["position_size"] >= self.min_lot_size:
                        # Execute trade
                        executed_trades += 1
                        self._execute_trade(signal, position_details)

                        if executed_trades % 10 == 0:
                            logger.info(
                                f"Executed {executed_trades} trades, current equity: ${current_equity:,.2f}"
                            )

            # Check exits
            self._check_exits(primary_data.iloc[i], current_time)

        # Close remaining positions
        if self.open_positions:
            logger.info("\nClosing remaining positions...")
            self._close_all_positions(primary_data.iloc[-1], primary_data.index[-1])

        # Calculate results
        results = self._calculate_results()

        # Display summary
        logger.info(f"\n{'='*60}")
        logger.info("BACKTEST RESULTS SUMMARY")
        logger.info(f"{'='*60}")

        logger.info("\nSignal Statistics:")
        logger.info(f"Total Signals Generated: {total_signals}")
        logger.info(f"Trades Executed: {executed_trades}")

        logger.info("\nPerformance Metrics:")
        logger.info(f"Total Trades: {results['total_trades']}")
        logger.info(
            f"Winning Trades: {results['winning_trades']} ({results['win_rate']:.1%})"
        )
        logger.info(f"Average Win: ${results['avg_win']:,.2f}")
        logger.info(f"Average Loss: ${results['avg_loss']:,.2f}")
        logger.info(f"Profit Factor: {results['profit_factor']:.2f}")

        logger.info("\nCapital & Returns:")
        logger.info(f"Starting Capital: ${self.initial_capital:,.2f}")
        logger.info(f"Final Capital: ${results['final_capital']:,.2f}")
        logger.info(f"Total PnL: ${results['total_pnl']:,.2f}")
        logger.info(f"Total Return: {results['total_return']:.2%}")
        logger.info(f"Max Drawdown: {results['max_drawdown']:.2%}")
        logger.info(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")

        logger.info("\nLeverage Usage:")
        logger.info(f"Average Leverage: {results['avg_leverage']:.1f}:1")
        logger.info(f"Max Leverage Used: {results['max_leverage']:.1f}:1")

        logger.info("\nSignal Source Performance:")
        for source, stats in results.get("signal_sources", {}).items():
            logger.info(f"{source}: {stats['count']} trades, PnL: ${stats['pnl']:,.2f}")

        # Save results
        self._save_results(results, start_date, end_date)

        return results

    def _generate_fast_signals(
        self, data: pd.DataFrame, current_time: datetime, current_bar: pd.Series
    ) -> List[Dict[str, Any]]:
        """Generate signals quickly without ML or LLM."""
        signals = []

        if len(data) < 200:
            return signals

        current_price = current_bar["close"]

        # 1. MA Crossover
        ma_10 = data["close"].rolling(10).mean()
        ma_20 = data["close"].rolling(20).mean()
        ma_50 = data["close"].rolling(50).mean()

        if len(ma_10) >= 2 and not pd.isna(ma_50.iloc[-1]):
            # Golden cross
            if ma_10.iloc[-1] > ma_20.iloc[-1] and ma_10.iloc[-2] <= ma_20.iloc[-2]:
                if current_price > ma_50.iloc[-1]:
                    signals.append(
                        {
                            "direction": "BUY",
                            "confidence": 0.65,
                            "entry_price": current_price,
                            "stop_loss": ma_20.iloc[-1],
                            "take_profit": current_price
                            + 2 * (current_price - ma_20.iloc[-1]),
                            "source": "MA Cross",
                            "timestamp": current_time,
                        }
                    )
            # Death cross
            elif ma_10.iloc[-1] < ma_20.iloc[-1] and ma_10.iloc[-2] >= ma_20.iloc[-2]:
                if current_price < ma_50.iloc[-1]:
                    signals.append(
                        {
                            "direction": "SELL",
                            "confidence": 0.65,
                            "entry_price": current_price,
                            "stop_loss": ma_20.iloc[-1],
                            "take_profit": current_price
                            - 2 * (ma_20.iloc[-1] - current_price),
                            "source": "MA Cross",
                            "timestamp": current_time,
                        }
                    )

        # 2. RSI Extreme
        if "rsi_14" in data.columns:
            rsi = data["rsi_14"].iloc[-1]
            if not pd.isna(rsi):
                if rsi < 30:
                    signals.append(
                        {
                            "direction": "BUY",
                            "confidence": 0.6,
                            "entry_price": current_price,
                            "stop_loss": current_price * 0.995,
                            "take_profit": current_price * 1.010,
                            "source": "RSI Oversold",
                            "timestamp": current_time,
                        }
                    )
                elif rsi > 70:
                    signals.append(
                        {
                            "direction": "SELL",
                            "confidence": 0.6,
                            "entry_price": current_price,
                            "stop_loss": current_price * 1.005,
                            "take_profit": current_price * 0.990,
                            "source": "RSI Overbought",
                            "timestamp": current_time,
                        }
                    )

        # 3. Bollinger Band
        if all(col in data.columns for col in ["bb_upper", "bb_lower", "bb_middle"]):
            bb_upper = data["bb_upper"].iloc[-1]
            bb_lower = data["bb_lower"].iloc[-1]
            bb_middle = data["bb_middle"].iloc[-1]

            if not pd.isna(bb_upper):
                # Squeeze breakout
                bb_width = (bb_upper - bb_lower) / bb_middle
                avg_width = (
                    data["bb_width"].rolling(20).mean().iloc[-1]
                    if "bb_width" in data.columns
                    else bb_width
                )

                if bb_width < avg_width * 0.7:  # Squeeze
                    if current_price > bb_upper:
                        signals.append(
                            {
                                "direction": "BUY",
                                "confidence": 0.7,
                                "entry_price": current_price,
                                "stop_loss": bb_middle,
                                "take_profit": current_price
                                + 2 * (current_price - bb_middle),
                                "source": "BB Squeeze",
                                "timestamp": current_time,
                            }
                        )
                    elif current_price < bb_lower:
                        signals.append(
                            {
                                "direction": "SELL",
                                "confidence": 0.7,
                                "entry_price": current_price,
                                "stop_loss": bb_middle,
                                "take_profit": current_price
                                - 2 * (bb_middle - current_price),
                                "source": "BB Squeeze",
                                "timestamp": current_time,
                            }
                        )

                # Mean reversion
                elif current_price < bb_lower * 0.998:
                    signals.append(
                        {
                            "direction": "BUY",
                            "confidence": 0.55,
                            "entry_price": current_price,
                            "stop_loss": current_price * 0.995,
                            "take_profit": bb_middle,
                            "source": "BB Reversion",
                            "timestamp": current_time,
                        }
                    )
                elif current_price > bb_upper * 1.002:
                    signals.append(
                        {
                            "direction": "SELL",
                            "confidence": 0.55,
                            "entry_price": current_price,
                            "stop_loss": current_price * 1.005,
                            "take_profit": bb_middle,
                            "source": "BB Reversion",
                            "timestamp": current_time,
                        }
                    )

        # 4. MACD
        if "macd" in data.columns and "macd_signal" in data.columns:
            macd = data["macd"].iloc[-1]
            macd_signal = data["macd_signal"].iloc[-1]
            macd_prev = data["macd"].iloc[-2]
            signal_prev = data["macd_signal"].iloc[-2]

            if not pd.isna(macd) and not pd.isna(macd_prev):
                # MACD crossover
                if macd > macd_signal and macd_prev <= signal_prev:
                    signals.append(
                        {
                            "direction": "BUY",
                            "confidence": 0.6,
                            "entry_price": current_price,
                            "stop_loss": current_price * 0.996,
                            "take_profit": current_price * 1.008,
                            "source": "MACD Cross",
                            "timestamp": current_time,
                        }
                    )
                elif macd < macd_signal and macd_prev >= signal_prev:
                    signals.append(
                        {
                            "direction": "SELL",
                            "confidence": 0.6,
                            "entry_price": current_price,
                            "stop_loss": current_price * 1.004,
                            "take_profit": current_price * 0.992,
                            "source": "MACD Cross",
                            "timestamp": current_time,
                        }
                    )

        return signals

    def _calculate_dynamic_position_limit(self) -> int:
        """Calculate dynamic position limit based on drawdown."""
        if self.current_drawdown < 0.05:
            return self.max_concurrent_positions
        elif self.current_drawdown < 0.10:
            return 5
        elif self.current_drawdown < 0.15:
            return 3
        elif self.current_drawdown < 0.20:
            return 2
        else:
            return 1

    def _calculate_aggressive_position(
        self, signal: Dict[str, Any], current_bar: pd.Series
    ) -> Dict[str, Any]:
        """Calculate aggressive position size."""
        # Base calculations
        stop_distance = abs(signal["entry_price"] - signal["stop_loss"])
        stop_percentage = stop_distance / signal["entry_price"]

        # Dynamic risk based on drawdown
        if self.current_drawdown < 0.05:
            risk_percent = self.max_risk_per_trade
        elif self.current_drawdown < 0.10:
            risk_percent = self.max_risk_per_trade * 0.8
        elif self.current_drawdown < 0.15:
            risk_percent = self.max_risk_per_trade * 0.6
        else:
            risk_percent = self.max_risk_per_trade * 0.4

        # Adjust for consecutive losses
        if self.consecutive_losses > 2:
            risk_percent *= 0.7
        elif self.consecutive_losses > 4:
            risk_percent *= 0.5

        risk_amount = self.capital * risk_percent

        # Position size based on risk
        base_position = risk_amount / stop_distance

        # Apply confidence and leverage
        confidence = signal["confidence"]
        signal_leverage = self.target_leverage * confidence

        # Boost for high confidence
        if confidence > 0.65:
            signal_leverage *= 1.2

        leveraged_position = min(
            base_position * confidence, self.capital * signal_leverage
        )

        # Max position checks
        max_position = self.capital * min(self.max_leverage, signal_leverage * 2)
        position_size = min(leveraged_position, max_position)

        # Round to micro lots
        lots = max(1, round(position_size / self.min_lot_size))
        position_size = lots * self.min_lot_size

        # Calculate effective leverage
        effective_leverage = position_size / self.capital

        return {
            "position_size": position_size,
            "lots": lots,
            "effective_leverage": effective_leverage,
            "risk_amount": stop_percentage * position_size,
        }

    def _execute_trade(self, signal: Dict[str, Any], position: Dict[str, Any]):
        """Execute a trade."""
        trade_id = (
            f"trade_{len(self.trades)}_{signal['timestamp'].strftime('%Y%m%d_%H%M%S')}"
        )

        # Calculate commission
        commission = (position["position_size"] / 1000) * self.commission_per_lot * 2

        # Store open position
        self.open_positions[trade_id] = {
            "signal": signal,
            "position": position,
            "entry_time": signal["timestamp"],
            "commission": commission,
            "drawdown_at_entry": self.current_drawdown,
        }

        # Deduct commission
        self.capital -= commission

    def _check_exits(self, current_bar: pd.Series, current_time: datetime):
        """Check and process exits with trailing stops."""
        closed_trades = []

        for trade_id, position_data in self.open_positions.items():
            signal = position_data["signal"]
            position = position_data["position"]

            current_price = current_bar["close"]
            exit_price = None
            exit_reason = None

            # Calculate current P&L
            if signal["direction"] == "BUY":
                unrealized_pnl_pct = (current_price - signal["entry_price"]) / signal[
                    "entry_price"
                ]
            else:
                unrealized_pnl_pct = (signal["entry_price"] - current_price) / signal[
                    "entry_price"
                ]

            # Trailing stop logic
            if unrealized_pnl_pct > 0.003:  # 30 pips
                if signal["direction"] == "BUY":
                    signal["stop_loss"] = max(
                        signal["stop_loss"], signal["entry_price"] * 1.0005
                    )
                else:
                    signal["stop_loss"] = min(
                        signal["stop_loss"], signal["entry_price"] * 0.9995
                    )

            if unrealized_pnl_pct > 0.005:  # 50 pips
                if signal["direction"] == "BUY":
                    trail_stop = current_price * 0.997
                    signal["stop_loss"] = max(signal["stop_loss"], trail_stop)
                else:
                    trail_stop = current_price * 1.003
                    signal["stop_loss"] = min(signal["stop_loss"], trail_stop)

            # Check exits
            if signal["direction"] == "BUY":
                if current_price <= signal["stop_loss"]:
                    exit_price = signal["stop_loss"]
                    exit_reason = "Stop Loss"
                elif current_price >= signal["take_profit"]:
                    exit_price = signal["take_profit"]
                    exit_reason = "Take Profit"
            else:
                if current_price >= signal["stop_loss"]:
                    exit_price = signal["stop_loss"]
                    exit_reason = "Stop Loss"
                elif current_price <= signal["take_profit"]:
                    exit_price = signal["take_profit"]
                    exit_reason = "Take Profit"

            if exit_price:
                # Calculate PnL
                if signal["direction"] == "BUY":
                    pnl_pips = (exit_price - signal["entry_price"]) * 10000
                    pnl = (
                        (exit_price - signal["entry_price"])
                        / signal["entry_price"]
                        * position["position_size"]
                    )
                else:
                    pnl_pips = (signal["entry_price"] - exit_price) * 10000
                    pnl = (
                        (signal["entry_price"] - exit_price)
                        / signal["entry_price"]
                        * position["position_size"]
                    )

                # Subtract commission
                pnl -= position_data["commission"]

                # Update capital
                self.capital += pnl

                # Track consecutive losses
                if pnl < 0:
                    self.consecutive_losses += 1
                else:
                    self.consecutive_losses = 0

                # Record trade
                trade = FastTrade(
                    timestamp=current_time,
                    direction=signal["direction"],
                    entry_price=signal["entry_price"],
                    exit_price=exit_price,
                    position_size=position["position_size"],
                    lots=position["lots"],
                    leverage_used=position["effective_leverage"],
                    pnl=pnl,
                    pnl_pips=pnl_pips,
                    confidence=signal["confidence"],
                    signal_source=signal["source"],
                    exit_reason=exit_reason,
                    drawdown_at_entry=position_data["drawdown_at_entry"],
                )

                self.trades.append(trade)
                closed_trades.append(trade_id)

        # Remove closed trades
        for trade_id in closed_trades:
            del self.open_positions[trade_id]

    def _close_all_positions(self, current_bar: pd.Series, current_time: datetime):
        """Close all open positions."""
        for trade_id in list(self.open_positions.keys()):
            position_data = self.open_positions[trade_id]
            signal = position_data["signal"]
            position = position_data["position"]

            exit_price = current_bar["close"]

            # Calculate PnL
            if signal["direction"] == "BUY":
                pnl_pips = (exit_price - signal["entry_price"]) * 10000
                pnl = (
                    (exit_price - signal["entry_price"])
                    / signal["entry_price"]
                    * position["position_size"]
                )
            else:
                pnl_pips = (signal["entry_price"] - exit_price) * 10000
                pnl = (
                    (signal["entry_price"] - exit_price)
                    / signal["entry_price"]
                    * position["position_size"]
                )

            # Subtract commission
            pnl -= position_data["commission"]

            # Update capital
            self.capital += pnl

            # Record trade
            trade = FastTrade(
                timestamp=current_time,
                direction=signal["direction"],
                entry_price=signal["entry_price"],
                exit_price=exit_price,
                position_size=position["position_size"],
                lots=position["lots"],
                leverage_used=position["effective_leverage"],
                pnl=pnl,
                pnl_pips=pnl_pips,
                confidence=signal["confidence"],
                signal_source=signal["source"],
                exit_reason="Forced Close",
                drawdown_at_entry=position_data["drawdown_at_entry"],
            )

            self.trades.append(trade)

        self.open_positions.clear()

    def _calculate_current_equity(self, current_bar: pd.Series) -> float:
        """Calculate current equity including open positions."""
        equity = self.capital

        for position_data in self.open_positions.values():
            signal = position_data["signal"]
            position = position_data["position"]
            current_price = current_bar["close"]

            # Unrealized PnL
            if signal["direction"] == "BUY":
                unrealized_pnl = (
                    (current_price - signal["entry_price"])
                    / signal["entry_price"]
                    * position["position_size"]
                )
            else:
                unrealized_pnl = (
                    (signal["entry_price"] - current_price)
                    / signal["entry_price"]
                    * position["position_size"]
                )

            equity += unrealized_pnl

        return equity

    def _calculate_results(self) -> Dict[str, Any]:
        """Calculate backtest results."""
        if not self.trades:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "profit_factor": 0,
                "total_pnl": 0,
                "final_capital": self.capital,
                "total_return": 0,
                "max_drawdown": 0,
                "sharpe_ratio": 0,
                "avg_leverage": 0,
                "max_leverage": 0,
                "total_commission": 0,
                "signal_sources": {},
            }

        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl <= 0]

        # Basic metrics
        total_pnl = sum(t.pnl for t in self.trades)
        total_return = (self.capital - self.initial_capital) / self.initial_capital

        # Win/Loss metrics
        win_rate = len(winning_trades) / len(self.trades) if self.trades else 0
        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([abs(t.pnl) for t in losing_trades]) if losing_trades else 0

        # Profit factor
        gross_profit = sum(t.pnl for t in winning_trades) if winning_trades else 0
        gross_loss = sum(abs(t.pnl) for t in losing_trades) if losing_trades else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Risk metrics
        returns = [t.pnl / self.initial_capital for t in self.trades]
        sharpe_ratio = (
            np.mean(returns) / np.std(returns) * np.sqrt(252)
            if returns and np.std(returns) > 0
            else 0
        )

        # Leverage metrics
        leverages = [t.leverage_used for t in self.trades]
        avg_leverage = np.mean(leverages) if leverages else 0
        max_leverage = max(leverages) if leverages else 0

        # Commission
        total_commission = sum(
            t.position_size / 1000 * self.commission_per_lot * 2 for t in self.trades
        )

        # Signal source analysis
        signal_sources = {}
        for trade in self.trades:
            source = trade.signal_source
            if source not in signal_sources:
                signal_sources[source] = {"count": 0, "pnl": 0}
            signal_sources[source]["count"] += 1
            signal_sources[source]["pnl"] += trade.pnl

        return {
            "total_trades": len(self.trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "total_pnl": total_pnl,
            "final_capital": self.capital,
            "total_return": total_return,
            "max_drawdown": self.max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "avg_leverage": avg_leverage,
            "max_leverage": max_leverage,
            "avg_pnl_pips": (
                np.mean([t.pnl_pips for t in self.trades]) if self.trades else 0
            ),
            "total_commission": total_commission,
            "signal_sources": signal_sources,
        }

    def _save_results(
        self, results: Dict[str, Any], start_date: datetime, end_date: datetime
    ):
        """Save backtest results."""
        output_dir = Path("output/fast_aggressive_backtest")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Sample trades for saving (every 10th trade to keep file size reasonable)
        sample_trades = self.trades[::10] if len(self.trades) > 100 else self.trades

        save_data = {
            "config": {
                "initial_capital": self.initial_capital,
                "max_leverage": self.max_leverage,
                "target_leverage": self.target_leverage,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "results": results,
            "sample_trades": [
                {
                    "timestamp": t.timestamp.isoformat(),
                    "direction": t.direction,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "position_size": t.position_size,
                    "leverage_used": t.leverage_used,
                    "pnl": t.pnl,
                    "pnl_pips": t.pnl_pips,
                    "signal_source": t.signal_source,
                    "exit_reason": t.exit_reason,
                }
                for t in sample_trades
            ],
            "equity_curve_sample": [
                {
                    "timestamp": (
                        point["timestamp"].isoformat()
                        if hasattr(point["timestamp"], "isoformat")
                        else str(point["timestamp"])
                    ),
                    "equity": point["equity"],
                }
                for point in self.equity_curve[::50]  # Every 50th point
            ],
        }

        filename = (
            output_dir
            / f'fast_backtest_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        )
        with open(filename, "w") as f:
            json.dump(save_data, f, indent=2)

        logger.info(f"\nResults saved to: {filename}")


async def main():
    """Run the fast aggressive backtest."""
    # Check for API key
    polygon_api_key = os.getenv("POLYGON_API_KEY")
    if not polygon_api_key:
        logger.error("POLYGON_API_KEY not found in .env file")
        return

    # Initialize fast backtester
    backtester = FastAggressiveBacktester(
        initial_capital=10000,
        max_leverage=400.0,
        target_leverage=50.0,
        min_lot_size=1.0,
        commission_per_lot=0.02,
        max_risk_per_trade=0.05,
        max_drawdown_limit=0.25,
        polygon_api_key=polygon_api_key,
    )

    # Run backtest for 2024
    await backtester.run_backtest(
        symbol="GBPUSD",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 12, 31),
    )


if __name__ == "__main__":
    asyncio.run(main())
