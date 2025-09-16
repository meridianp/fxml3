#!/usr/bin/env python
"""Integration tests for enhanced production system."""

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).parent.parent.parent))

from scripts.enhanced_elliott_wave_signals import ElliottWaveSignal
from scripts.enhanced_ml_signal_generator import MLSignal
from scripts.general_technical_analysis_llm import TechnicalAnalysisSignal
from scripts.production_system_enhanced import (
    EnhancedProductionConfig,
    EnhancedProductionSystem,
)


class TestEnhancedProductionSystemIntegration(unittest.TestCase):
    """Integration tests for Enhanced Production System."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = EnhancedProductionConfig(
            initial_capital=10000,
            max_risk_per_trade=0.015,
            max_portfolio_risk=0.045,
            max_positions=2,
            min_confluences=2,
            min_signal_confidence=0.7,
        )

        self.system = EnhancedProductionSystem(self.config)

        # Create sample market data
        self.sample_data = self._create_sample_data()
        self.symbol = "EURUSD"
        self.current_time = pd.Timestamp.now()

    def _create_sample_data(self, bars=200):
        """Create sample OHLCV data with indicators."""
        dates = pd.date_range(end=datetime.now(), periods=bars, freq="4h")

        # Generate trending data
        base_price = 1.1000
        trend = np.linspace(0, 0.05, bars)  # 5% uptrend
        noise = np.random.normal(0, 0.001, bars)

        close_prices = base_price + trend + noise

        data = pd.DataFrame(
            {
                "open": close_prices + np.random.uniform(-0.0002, 0.0002, bars),
                "high": close_prices + np.abs(np.random.uniform(0, 0.0005, bars)),
                "low": close_prices - np.abs(np.random.uniform(0, 0.0005, bars)),
                "close": close_prices,
                "volume": np.random.uniform(900000, 1100000, bars),
                "rsi_14": 50 + 20 * np.sin(np.linspace(0, 4 * np.pi, bars)),
                "atr_14": np.full(bars, 0.0015),
                "adx": np.random.uniform(20, 30, bars),
            },
            index=dates,
        )

        return data

    def test_system_initialization(self):
        """Test system initialization."""
        self.assertEqual(self.system.capital, 10000)
        self.assertEqual(len(self.system.positions), 0)
        self.assertEqual(len(self.system.trades), 0)
        self.assertIsNotNone(self.system.ml_generator)
        self.assertIsNotNone(self.system.ew_generator)
        self.assertIsNotNone(self.system.ta_analyzer)
        self.assertIsNotNone(self.system.risk_manager)

    def test_generate_combined_signal_no_confluences(self):
        """Test signal generation with insufficient confluences."""
        # Mock generators to return only one signal
        self.system.ml_generator.generate_signal = Mock(return_value=None)
        self.system.ew_generator.generate_signals = Mock(return_value=None)
        self.system.ta_analyzer.analyze_market = Mock(
            return_value=TechnicalAnalysisSignal(
                bias="NEUTRAL",
                confidence=0.5,
                entry_zones=[1.105],
                stop_loss=1.100,
                targets=[1.110],
                key_levels={},
                technical_confluences=[],
                market_structure="ranging",
                risk_reward=1.0,
                time_horizon="swing",
            )
        )

        signal = self.system.generate_combined_signal(
            self.sample_data, self.symbol, self.current_time
        )

        self.assertIsNone(signal)  # Should fail min confluence requirement

    def test_generate_combined_signal_with_confluences(self):
        """Test signal generation with multiple confluences."""
        # Mock ML signal
        ml_signal = MLSignal(
            action="LONG",
            confidence=0.75,
            predicted_return=0.002,
            market_regime="strong_uptrend",
            volatility_regime="normal_volatility",
            trend_strength=0.7,
            feature_importance={},
            filters_passed=["market_regime", "volatility"],
            filters_failed=[],
        )

        # Mock Elliott Wave signal
        ew_signal = ElliottWaveSignal(
            action="LONG",
            confidence=0.8,
            entry=1.105,
            stop_loss=1.100,
            targets=[1.110, 1.115],
            wave_position="Wave 2 -> 3",
            pattern_type="Impulse",
            reasoning="Wave 3 entry",
        )

        # Mock signals
        self.system.ml_generator.generate_signal = Mock(return_value=ml_signal)
        self.system.ew_generator.generate_signals = Mock(return_value=ew_signal)
        self.system.ta_analyzer.analyze_market = Mock(
            return_value=TechnicalAnalysisSignal(
                bias="NEUTRAL",
                confidence=0.5,
                entry_zones=[1.105],
                stop_loss=1.100,
                targets=[1.110],
                key_levels={},
                technical_confluences=[],
                market_structure="trending_up",
                risk_reward=1.0,
                time_horizon="swing",
            )
        )

        signal = self.system.generate_combined_signal(
            self.sample_data, self.symbol, self.current_time
        )

        self.assertIsNotNone(signal)
        self.assertEqual(signal["action"], "LONG")
        self.assertGreaterEqual(signal["confidence"], 0.7)
        self.assertEqual(signal["signal_count"], 2)
        self.assertIn("ML", signal["source"])
        self.assertIn("Elliott Wave", signal["source"])

    def test_combine_signals_enhanced(self):
        """Test enhanced signal combination logic."""
        signals = [
            {
                "source": "ML",
                "action": "LONG",
                "confidence": 0.75,
                "weight": 0.4,
                "details": Mock(),
            },
            {
                "source": "Elliott Wave",
                "action": "LONG",
                "confidence": 0.8,
                "weight": 0.3,
                "stop_loss": 1.100,
                "targets": [1.110, 1.115],
                "details": Mock(),
            },
            {
                "source": "Technical Analysis",
                "action": "SHORT",
                "confidence": 0.6,
                "weight": 0.3,
                "stop_loss": 1.108,
                "targets": [1.095],
                "details": Mock(),
            },
        ]

        combined = self.system._combine_signals_enhanced(signals, self.sample_data)

        self.assertIsNotNone(combined)
        self.assertEqual(combined["action"], "LONG")  # 2 LONG vs 1 SHORT
        self.assertGreater(combined["confidence"], 0.7)
        self.assertIsInstance(combined["stop_loss"], float)
        self.assertIsInstance(combined["targets"], list)
        self.assertGreater(combined["risk_reward"], 0)

    def test_apply_final_filters(self):
        """Test final quality filters."""
        # Good signal
        good_signal = {"risk_reward": 2.0, "confidence": 0.75}

        self.assertTrue(
            self.system._apply_final_filters(
                good_signal, self.sample_data, self.current_time
            )
        )

        # Bad risk/reward
        bad_rr_signal = {"risk_reward": 1.2, "confidence": 0.75}  # Below 1.5 minimum

        self.assertFalse(
            self.system._apply_final_filters(
                bad_rr_signal, self.sample_data, self.current_time
            )
        )

        # High volatility
        high_vol_data = self.sample_data.copy()
        high_vol_data["close"] = high_vol_data["close"] + np.random.normal(
            0, 0.01, len(high_vol_data)
        )

        self.assertFalse(
            self.system._apply_final_filters(
                good_signal, high_vol_data, self.current_time
            )
        )

    def test_check_recent_losses(self):
        """Test recent loss checking."""
        # No trades - should pass
        self.assertFalse(self.system._check_recent_losses())

        # Add some trades
        self.system.trades = [{"pnl": 100}, {"pnl": -50}, {"pnl": 75}]

        # Only 1 loss in last 3 - should pass
        self.assertFalse(self.system._check_recent_losses())

        # Add more losses
        self.system.trades.extend([{"pnl": -100}, {"pnl": -75}])

        # 2 losses in last 3 - should fail
        self.assertTrue(self.system._check_recent_losses())

    def test_execute_trade(self):
        """Test trade execution."""
        signal = {
            "action": "LONG",
            "confidence": 0.8,
            "entry": 1.105,
            "stop_loss": 1.100,
            "targets": [1.110, 1.115, 1.120],
            "source": "ML + Elliott Wave",
            "confluences": ["Wave 3", "Uptrend", "RSI support"],
            "risk_reward": 2.0,
        }

        current_bar = self.sample_data.iloc[-1]

        initial_capital = self.system.capital

        self.system.execute_trade(signal, current_bar, self.current_time, self.symbol)

        # Check position created
        self.assertEqual(len(self.system.positions), 1)
        position_id = list(self.system.positions.keys())[0]
        position = self.system.positions[position_id]

        self.assertEqual(position["symbol"], self.symbol)
        self.assertEqual(position["direction"], "LONG")
        self.assertEqual(position["signal_confidence"], 0.8)
        self.assertGreater(position["position_size"], 0)

        # Check capital reduced by commission
        self.assertLess(self.system.capital, initial_capital)

    def test_update_positions_stop_loss(self):
        """Test position update with stop loss hit."""
        # Create a position
        position_id = f"{self.symbol}_{self.current_time}"
        self.system.positions[position_id] = {
            "symbol": self.symbol,
            "direction": "LONG",
            "entry_time": self.current_time,
            "entry_price": 1.105,
            "position_size": 100000,
            "stop_loss": 1.100,
            "initial_stop": 1.100,
            "targets": [1.110, 1.115],
            "targets_hit": [],
            "signal_confidence": 0.8,
            "signal_source": "Test",
            "confluences": [],
            "trailing_stop_active": False,
            "partial_exits": [],
        }

        # Create bar that hits stop loss
        stop_bar = pd.Series(
            {
                "open": 1.102,
                "high": 1.103,
                "low": 1.099,  # Below stop
                "close": 1.101,
                "volume": 1000000,
            }
        )

        self.system.update_positions(self.symbol, stop_bar, self.current_time)

        # Position should be closed
        self.assertEqual(len(self.system.positions), 0)
        self.assertEqual(len(self.system.trades), 1)

        # Check trade record
        trade = self.system.trades[0]
        self.assertEqual(trade["exit_reason"], "Stop Loss")
        self.assertLess(trade["pnl"], 0)  # Should be a loss

    def test_update_positions_trailing_stop(self):
        """Test trailing stop update."""
        # Create a profitable position
        position_id = f"{self.symbol}_{self.current_time}"
        self.system.positions[position_id] = {
            "symbol": self.symbol,
            "direction": "LONG",
            "entry_time": self.current_time,
            "entry_price": 1.100,
            "position_size": 100000,
            "stop_loss": 1.095,
            "initial_stop": 1.095,
            "targets": [1.110, 1.115],
            "targets_hit": [],
            "signal_confidence": 0.8,
            "signal_source": "Test",
            "confluences": [],
            "trailing_stop_active": False,
            "partial_exits": [],
        }

        # Create bar with profit
        profit_bar = pd.Series(
            {
                "open": 1.108,
                "high": 1.110,  # Profitable
                "low": 1.107,
                "close": 1.109,
                "volume": 1000000,
                "atr_14": 0.0015,
            }
        )

        self.system.update_positions(self.symbol, profit_bar, self.current_time)

        # Check trailing stop updated
        position = self.system.positions[position_id]
        self.assertTrue(position["trailing_stop_active"])
        self.assertGreater(position["stop_loss"], position["initial_stop"])

    def test_check_partial_profits(self):
        """Test partial profit taking."""
        position_id = "test_position"
        position = {
            "entry_price": 1.100,
            "initial_stop": 1.095,
            "position_size": 100000,
            "partial_exits": [],
        }

        # Current price at 1.5R
        current_price = 1.1075  # Risk = 0.005, 1.5R = 0.0075
        pnl_points = 0.0075

        initial_size = position["position_size"]
        initial_capital = self.system.capital

        self.system._check_partial_profits(
            position_id, position, current_price, pnl_points
        )

        # Check partial exit taken
        self.assertIn(1.5, position["partial_exits"])
        self.assertLess(position["position_size"], initial_size)
        self.assertGreater(self.system.capital, initial_capital)

    def test_performance_stats_tracking(self):
        """Test performance statistics tracking."""
        # Generate some signals and track stats

        # Mock ML signal
        ml_signal = MLSignal(
            action="LONG",
            confidence=0.75,
            predicted_return=0.002,
            market_regime="strong_uptrend",
            volatility_regime="normal_volatility",
            trend_strength=0.7,
            feature_importance={},
            filters_passed=["market_regime"],
            filters_failed=[],
        )

        self.system.ml_generator.generate_signal = Mock(return_value=ml_signal)
        self.system.ew_generator.generate_signals = Mock(return_value=None)
        self.system.ta_analyzer.analyze_market = Mock(
            return_value=TechnicalAnalysisSignal(
                bias="NEUTRAL",
                confidence=0.5,
                entry_zones=[1.105],
                stop_loss=1.100,
                targets=[1.110],
                key_levels={},
                technical_confluences=[],
                market_structure="ranging",
                risk_reward=1.0,
                time_horizon="swing",
            )
        )

        # Generate signal (should fail confluence requirement)
        signal = self.system.generate_combined_signal(
            self.sample_data, self.symbol, self.current_time
        )

        # Check stats updated
        self.assertEqual(self.system.performance_stats["ml_signals"], 1)
        self.assertEqual(self.system.performance_stats["total_signals"], 1)
        self.assertEqual(self.system.performance_stats["multi_confluence"], 0)

    def test_config_validation(self):
        """Test configuration validation."""
        # Test partial profit levels initialization
        config = EnhancedProductionConfig()
        system = EnhancedProductionSystem(config)

        self.assertIsNotNone(config.partial_profit_levels)
        self.assertEqual(config.partial_profit_levels, [1.5, 2.5, 3.5])

        # Test all config values
        self.assertEqual(config.initial_capital, 10000)
        self.assertEqual(config.max_risk_per_trade, 0.015)
        self.assertEqual(config.max_positions, 2)
        self.assertEqual(config.min_signal_confidence, 0.7)
        self.assertEqual(config.min_confluences, 2)

    def test_full_trading_cycle(self):
        """Test a complete trading cycle from signal to exit."""
        # Mock a strong multi-confluence signal
        ml_signal = MLSignal(
            action="LONG",
            confidence=0.8,
            predicted_return=0.003,
            market_regime="strong_uptrend",
            volatility_regime="normal_volatility",
            trend_strength=0.8,
            feature_importance={},
            filters_passed=["all"],
            filters_failed=[],
        )

        ew_signal = ElliottWaveSignal(
            action="LONG",
            confidence=0.85,
            entry=1.105,
            stop_loss=1.100,
            targets=[1.110, 1.115, 1.120],
            wave_position="Wave 2 -> 3",
            pattern_type="Impulse",
            reasoning="Strong wave 3",
        )

        self.system.ml_generator.generate_signal = Mock(return_value=ml_signal)
        self.system.ew_generator.generate_signals = Mock(return_value=ew_signal)
        self.system.ta_analyzer.analyze_market = Mock(
            return_value=TechnicalAnalysisSignal(
                bias="LONG",
                confidence=0.75,
                entry_zones=[1.105, 1.104],
                stop_loss=1.099,
                targets=[1.112, 1.118],
                key_levels={"support": [1.100], "resistance": [1.115]},
                technical_confluences=["MA support", "Uptrend"],
                market_structure="trending_up",
                risk_reward=2.5,
                time_horizon="swing",
            )
        )

        # Generate signal
        signal = self.system.generate_combined_signal(
            self.sample_data, self.symbol, self.current_time
        )

        self.assertIsNotNone(signal)
        self.assertEqual(signal["signal_count"], 3)  # All 3 sources

        # Execute trade
        current_bar = self.sample_data.iloc[-1]
        self.system.execute_trade(signal, current_bar, self.current_time, self.symbol)

        self.assertEqual(len(self.system.positions), 1)
        self.assertEqual(self.system.performance_stats["trades_executed"], 1)

        # Update with profit and exit
        profit_bar = pd.Series(
            {
                "open": 1.109,
                "high": 1.111,  # Hit first target
                "low": 1.108,
                "close": 1.110,
                "volume": 1000000,
                "atr_14": 0.0015,
            }
        )

        position_id = list(self.system.positions.keys())[0]
        self.system._close_position(position_id, 1.110, self.current_time, "Target")

        # Check trade completed
        self.assertEqual(len(self.system.positions), 0)
        self.assertEqual(len(self.system.trades), 1)

        trade = self.system.trades[0]
        self.assertGreater(trade["pnl"], 0)  # Profitable
        self.assertEqual(trade["confluences"], 3)


if __name__ == "__main__":
    unittest.main()
