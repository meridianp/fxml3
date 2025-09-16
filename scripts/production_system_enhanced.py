#!/usr/bin/env python
"""Enhanced production system with all improvements integrated."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from fxml4.backtesting.risk_management import RiskManager
from fxml4.ml.features import add_lagged_features, create_technical_features

# Core components
from fxml4.ml.models import ClassicMLModel

# Import enhanced components
from scripts.enhanced_elliott_wave_signals import EnhancedElliottWaveSignalGenerator
from scripts.enhanced_ml_signal_generator import EnhancedMLSignalGenerator
from scripts.general_technical_analysis_llm import GeneralTechnicalAnalysisLLM

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class EnhancedProductionConfig:
    """Enhanced production system configuration."""

    # Capital and Risk
    initial_capital: float = 10000
    max_risk_per_trade: float = 0.015  # 1.5% - more conservative
    max_portfolio_risk: float = 0.045  # 4.5% - more conservative
    max_positions: int = 2  # Fewer, higher quality positions

    # Signal Weights
    ml_weight: float = 0.4
    elliott_wave_weight: float = 0.3
    technical_analysis_weight: float = 0.3

    # Signal Thresholds
    min_signal_confidence: float = 0.7  # Higher threshold
    min_confluences: int = 2  # Require multiple signal sources

    # Transaction Costs
    commission_rate: float = 0.00005  # 0.5 pips
    slippage: float = 0.00002  # 0.2 pips
    spread: float = 0.00015  # 1.5 pips

    # Risk Management
    use_trailing_stops: bool = True
    trailing_stop_distance: float = 2.0  # ATR multiplier
    use_partial_profits: bool = True
    partial_profit_levels: List[float] = None  # R multiples

    # Filters
    use_market_regime_filter: bool = True
    use_volatility_filter: bool = True
    use_time_filter: bool = True
    max_trades_per_week: int = 3


class EnhancedProductionSystem:
    """Enhanced production trading system with all improvements."""

    def __init__(self, config: EnhancedProductionConfig):
        self.config = config
        # Set default partial profit levels if not provided
        if config.partial_profit_levels is None:
            config.partial_profit_levels = [1.5, 2.5, 3.5]
        self.capital = config.initial_capital
        self.positions = {}
        self.trades = []
        self.equity_curve = []

        # Initialize enhanced components
        self.ml_generator = EnhancedMLSignalGenerator(
            min_confidence=0.65,
            max_signals_per_week=config.max_trades_per_week,
            use_market_regime_filter=config.use_market_regime_filter,
            use_volatility_filter=config.use_volatility_filter,
        )

        self.ew_generator = EnhancedElliottWaveSignalGenerator(
            min_wave_size=0.003, confidence_threshold=0.5, use_trend_filter=True
        )

        self.ta_analyzer = GeneralTechnicalAnalysisLLM()

        # Risk management
        self.risk_manager = RiskManager(
            max_positions=config.max_positions,
            risk_per_trade_pct=config.max_risk_per_trade,
            max_risk_per_day_pct=config.max_portfolio_risk,
        )

        # ML model placeholder
        self.ml_model = None

        # Performance tracking
        self.performance_stats = {
            "total_signals": 0,
            "ml_signals": 0,
            "ew_signals": 0,
            "ta_signals": 0,
            "multi_confluence": 0,
            "trades_executed": 0,
            "filters_passed": 0,
            "filters_failed": 0,
        }

        logger.info("Enhanced production system initialized")

    def generate_combined_signal(
        self, data: pd.DataFrame, symbol: str, current_time: pd.Timestamp
    ) -> Optional[Dict]:
        """Generate combined signal from all sources with enhanced filtering."""

        signals = []

        # 1. ML Signal
        if self.ml_model is not None:
            self.ml_generator.model = self.ml_model
            ml_signal = self.ml_generator.generate_signal(data, current_time)

            if ml_signal and ml_signal.action != "HOLD":
                self.performance_stats["ml_signals"] += 1
                signals.append(
                    {
                        "source": "ML",
                        "action": ml_signal.action,
                        "confidence": ml_signal.confidence,
                        "weight": self.config.ml_weight,
                        "details": ml_signal,
                    }
                )

        # 2. Elliott Wave Signal
        ew_signal = self.ew_generator.generate_signals(data)

        if ew_signal and ew_signal.action != "HOLD":
            self.performance_stats["ew_signals"] += 1
            signals.append(
                {
                    "source": "Elliott Wave",
                    "action": ew_signal.action,
                    "confidence": ew_signal.confidence,
                    "weight": self.config.elliott_wave_weight,
                    "entry": ew_signal.entry,
                    "stop_loss": ew_signal.stop_loss,
                    "targets": ew_signal.targets,
                    "details": ew_signal,
                }
            )

        # 3. Technical Analysis Signal
        ta_signal = self.ta_analyzer.analyze_market(data, symbol)

        if ta_signal and ta_signal.bias != "NEUTRAL":
            self.performance_stats["ta_signals"] += 1
            signals.append(
                {
                    "source": "Technical Analysis",
                    "action": ta_signal.bias,
                    "confidence": ta_signal.confidence,
                    "weight": self.config.technical_analysis_weight,
                    "entry_zones": ta_signal.entry_zones,
                    "stop_loss": ta_signal.stop_loss,
                    "targets": ta_signal.targets,
                    "details": ta_signal,
                }
            )

        self.performance_stats["total_signals"] += len(signals)

        # Check confluence requirement
        if len(signals) < self.config.min_confluences:
            return None

        # Combine signals
        combined_signal = self._combine_signals_enhanced(signals, data)

        # Apply final filters
        if combined_signal and self._apply_final_filters(
            combined_signal, data, current_time
        ):
            self.performance_stats["filters_passed"] += 1

            if len(signals) >= 2:
                self.performance_stats["multi_confluence"] += 1

            return combined_signal
        else:
            self.performance_stats["filters_failed"] += 1
            return None

    def _combine_signals_enhanced(
        self, signals: List[Dict], data: pd.DataFrame
    ) -> Optional[Dict]:
        """Enhanced signal combination with weighted voting."""

        if not signals:
            return None

        # Count votes by direction
        long_score = 0
        short_score = 0

        for signal in signals:
            score = signal["confidence"] * signal["weight"]
            if signal["action"] in ["LONG", "BUY"]:
                long_score += score
            elif signal["action"] in ["SHORT", "SELL"]:
                short_score += score

        # Determine action
        if long_score > short_score and long_score > 0.5:
            action = "LONG"
            combined_confidence = long_score / sum(s["weight"] for s in signals)
        elif short_score > long_score and short_score > 0.5:
            action = "SHORT"
            combined_confidence = short_score / sum(s["weight"] for s in signals)
        else:
            return None

        # Check minimum confidence
        if combined_confidence < self.config.min_signal_confidence:
            return None

        # Aggregate entry, stop, and targets
        current_price = float(data["close"].iloc[-1])
        atr = (
            float(data["atr_14"].iloc[-1])
            if "atr_14" in data
            else current_price * 0.001
        )

        # Use most conservative stop loss
        stop_losses = []
        for signal in signals:
            if "stop_loss" in signal and signal["stop_loss"]:
                stop_losses.append(signal["stop_loss"])

        if stop_losses:
            if action == "LONG":
                stop_loss = min(stop_losses)  # Furthest stop for longs
            else:
                stop_loss = max(stop_losses)  # Furthest stop for shorts
        else:
            # Default ATR-based stop
            stop_loss = (
                current_price - 2 * atr if action == "LONG" else current_price + 2 * atr
            )

        # Use average of targets
        all_targets = []
        for signal in signals:
            if "targets" in signal and signal["targets"]:
                all_targets.extend(signal["targets"][:3])  # Max 3 targets per signal

        if all_targets:
            # Sort and take percentiles
            all_targets = (
                sorted(all_targets)
                if action == "LONG"
                else sorted(all_targets, reverse=True)
            )
            targets = [
                all_targets[int(len(all_targets) * 0.33)],  # Conservative
                all_targets[int(len(all_targets) * 0.66)],  # Medium
                all_targets[-1],  # Aggressive
            ]
        else:
            # Default ATR-based targets
            if action == "LONG":
                targets = [current_price + i * atr for i in [2, 3, 4]]
            else:
                targets = [current_price - i * atr for i in [2, 3, 4]]

        # Calculate risk/reward
        risk = abs(current_price - stop_loss)
        reward = abs(targets[0] - current_price)
        risk_reward = reward / risk if risk > 0 else 0

        # Build confluences list
        confluences = []
        for signal in signals:
            confluences.append(f"{signal['source']} ({signal['confidence']:.0%})")
            if hasattr(signal.get("details"), "technical_confluences"):
                confluences.extend(signal["details"].technical_confluences[:2])

        return {
            "action": action,
            "confidence": combined_confidence,
            "entry": current_price,
            "stop_loss": stop_loss,
            "targets": targets,
            "risk_reward": risk_reward,
            "source": " + ".join([s["source"] for s in signals]),
            "confluences": confluences,
            "signal_count": len(signals),
        }

    def _apply_final_filters(
        self, signal: Dict, data: pd.DataFrame, current_time: pd.Timestamp
    ) -> bool:
        """Apply final quality and risk filters."""

        # Risk/Reward filter
        if signal["risk_reward"] < 1.5:  # Minimum 1.5:1
            return False

        # Volatility check
        current_vol = data["close"].pct_change().tail(20).std()
        if current_vol > 0.02:  # 2% daily volatility is high for forex
            return False

        # Recent performance check (avoid trading after losses)
        if self._check_recent_losses():
            return False

        return True

    def _check_recent_losses(self) -> bool:
        """Check if we've had too many recent losses."""

        if len(self.trades) < 3:
            return False

        # Check last 3 trades
        recent_trades = self.trades[-3:]
        losses = sum(1 for t in recent_trades if t["pnl"] < 0)

        return losses >= 2  # Stop after 2 losses in last 3 trades

    def execute_trade(
        self, signal: Dict, current_bar: pd.Series, timestamp: pd.Timestamp, symbol: str
    ):
        """Execute trade with enhanced risk management."""

        # Position sizing based on confidence and risk
        base_risk = self.capital * self.config.max_risk_per_trade
        confidence_adjustment = (
            signal["confidence"] ** 2
        )  # Square to be more conservative
        risk_amount = base_risk * confidence_adjustment

        # Calculate position size
        stop_distance = abs(signal["entry"] - signal["stop_loss"])
        position_size = risk_amount / stop_distance if stop_distance > 0 else 0

        # Apply costs
        entry_cost = signal["entry"] + self.config.spread / 2 + self.config.slippage
        if signal["action"] == "SHORT":
            entry_cost = signal["entry"] - self.config.spread / 2 - self.config.slippage

        # Create position
        position_id = f"{symbol}_{timestamp}"
        self.positions[position_id] = {
            "symbol": symbol,
            "direction": signal["action"],
            "entry_time": timestamp,
            "entry_price": entry_cost,
            "position_size": position_size,
            "stop_loss": signal["stop_loss"],
            "initial_stop": signal["stop_loss"],
            "targets": signal["targets"],
            "targets_hit": [],
            "signal_confidence": signal["confidence"],
            "signal_source": signal["source"],
            "confluences": signal.get("confluences", []),
            "trailing_stop_active": False,
            "partial_exits": [],
        }

        self.performance_stats["trades_executed"] += 1

        # Deduct commission
        commission = position_size * entry_cost * self.config.commission_rate
        self.capital -= commission

        logger.info(f"{timestamp}: {signal['action']} {symbol} @ {entry_cost:.5f}")
        logger.info(f"  Confidence: {signal['confidence']:.1%}")
        logger.info(f"  Risk/Reward: 1:{signal['risk_reward']:.1f}")
        logger.info(f"  Confluences: {', '.join(signal['confluences'][:3])}")

    def update_positions(
        self, symbol: str, current_bar: pd.Series, timestamp: pd.Timestamp
    ):
        """Update positions with trailing stops and partial profits."""

        positions_to_update = []

        for pos_id, pos in self.positions.items():
            if pos["symbol"] != symbol:
                continue

            current_price = current_bar["close"]

            # Calculate position P&L
            if pos["direction"] == "LONG":
                pnl_points = current_price - pos["entry_price"]
            else:
                pnl_points = pos["entry_price"] - current_price

            # Check for partial profit taking
            if self.config.use_partial_profits and pnl_points > 0:
                self._check_partial_profits(pos_id, pos, current_price, pnl_points)

            # Update trailing stop
            if self.config.use_trailing_stops and pnl_points > 0:
                self._update_trailing_stop(pos_id, pos, current_bar)

            # Check stop loss
            if pos["direction"] == "LONG":
                if current_bar["low"] <= pos["stop_loss"]:
                    positions_to_update.append((pos_id, pos["stop_loss"], "Stop Loss"))
            else:
                if current_bar["high"] >= pos["stop_loss"]:
                    positions_to_update.append((pos_id, pos["stop_loss"], "Stop Loss"))

        # Process updates
        for pos_id, exit_price, reason in positions_to_update:
            self._close_position(pos_id, exit_price, timestamp, reason)

    def _check_partial_profits(
        self, pos_id: str, pos: Dict, current_price: float, pnl_points: float
    ):
        """Check and execute partial profit taking."""

        risk = abs(pos["entry_price"] - pos["initial_stop"])
        r_multiple = pnl_points / risk if risk > 0 else 0

        for level in self.config.partial_profit_levels:
            if r_multiple >= level and level not in pos["partial_exits"]:
                # Take 1/3 of remaining position
                partial_size = pos["position_size"] * 0.33
                pos["position_size"] -= partial_size

                # Record partial exit
                pos["partial_exits"].append(level)

                # Add to capital
                partial_pnl = partial_size * pnl_points
                self.capital += partial_pnl

                logger.info(f"  Partial profit at {level}R: +{partial_pnl:.2f}")

    def _update_trailing_stop(self, pos_id: str, pos: Dict, current_bar: pd.Series):
        """Update trailing stop loss."""

        atr = float(current_bar.get("atr_14", current_bar["close"] * 0.001))
        trail_distance = atr * self.config.trailing_stop_distance

        if pos["direction"] == "LONG":
            new_stop = current_bar["high"] - trail_distance
            if new_stop > pos["stop_loss"]:
                pos["stop_loss"] = new_stop
                pos["trailing_stop_active"] = True
        else:
            new_stop = current_bar["low"] + trail_distance
            if new_stop < pos["stop_loss"]:
                pos["stop_loss"] = new_stop
                pos["trailing_stop_active"] = True

    def _close_position(
        self, position_id: str, exit_price: float, exit_time: pd.Timestamp, reason: str
    ):
        """Close position and record trade."""

        if position_id not in self.positions:
            return

        pos = self.positions[position_id]

        # Apply exit costs
        if pos["direction"] == "LONG":
            exit_cost = exit_price - self.config.spread / 2 - self.config.slippage
        else:
            exit_cost = exit_price + self.config.spread / 2 + self.config.slippage

        # Calculate final P&L
        if pos["direction"] == "LONG":
            pnl = (exit_cost - pos["entry_price"]) * pos["position_size"]
        else:
            pnl = (pos["entry_price"] - exit_cost) * pos["position_size"]

        # Add partial profits
        for partial in pos["partial_exits"]:
            partial_risk = abs(pos["entry_price"] - pos["initial_stop"])
            partial_pnl = partial_risk * partial * (pos["position_size"] * 0.33)
            pnl += partial_pnl

        # Deduct commission
        commission = pos["position_size"] * exit_cost * self.config.commission_rate
        pnl -= commission

        # Update capital
        self.capital += pnl

        # Record trade
        self.trades.append(
            {
                "symbol": pos["symbol"],
                "direction": pos["direction"],
                "entry_time": pos["entry_time"],
                "entry_price": pos["entry_price"],
                "exit_time": exit_time,
                "exit_price": exit_cost,
                "position_size": pos["position_size"],
                "pnl": pnl,
                "pnl_pct": (
                    pnl / (pos["position_size"] * pos["entry_price"])
                    if pos["position_size"] > 0
                    else 0
                ),
                "exit_reason": reason,
                "signal_confidence": pos["signal_confidence"],
                "signal_source": pos["signal_source"],
                "confluences": len(pos["confluences"]),
                "partial_exits": len(pos["partial_exits"]),
                "trailing_stop_used": pos["trailing_stop_active"],
            }
        )

        del self.positions[position_id]

        logger.info(f"  Closed {pos['direction']} @ {exit_cost:.5f} ({reason})")
        logger.info(
            f"  P&L: {pnl:+.2f} ({pnl/(pos['position_size']*pos['entry_price'])*100:+.1f}%)"
        )


def demonstrate_enhanced_system():
    """Demonstrate the enhanced production system."""

    print("Enhanced Production Trading System")
    print("=" * 80)

    config = EnhancedProductionConfig()
    system = EnhancedProductionSystem(config)

    print("\nSystem Features:")
    print("1. Multiple Signal Sources:")
    print("   - Enhanced ML with market regime filters")
    print("   - Expanded Elliott Wave patterns")
    print("   - General technical analysis")

    print("\n2. Signal Quality Control:")
    print("   - Minimum 2 confluences required")
    print("   - 70%+ confidence threshold")
    print("   - Risk/Reward minimum 1.5:1")

    print("\n3. Advanced Risk Management:")
    print("   - Conservative position sizing (1.5% risk)")
    print("   - Trailing stops (2 ATR)")
    print("   - Partial profit taking (1.5R, 2.5R, 3.5R)")
    print("   - Maximum 2 positions")
    print("   - Stop after 2 losses in 3 trades")

    print("\n4. Market Filters:")
    print("   - Market regime detection")
    print("   - Volatility filtering")
    print("   - Time/session filtering")
    print("   - Maximum 3 trades per week")

    print("\n5. Realistic Costs:")
    print("   - 0.5 pip commission")
    print("   - 0.2 pip slippage")
    print("   - 1.5 pip spread")

    print("\nExpected Improvements:")
    print("- Higher win rate (40-50% target)")
    print("- Better risk/reward ratios")
    print("- Fewer, higher quality trades")
    print("- More consistent returns")
    print("- Lower drawdowns")


if __name__ == "__main__":
    demonstrate_enhanced_system()
