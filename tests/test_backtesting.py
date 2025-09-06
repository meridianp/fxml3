"""Tests for the backtesting module."""

import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

from fxml3.backtesting.performance_metrics import PerformanceMetrics
from fxml3.backtesting.wave_backtester import WaveBacktester
from fxml3.data_engineering.data_loader import ForexDataLoader
from fxml3.wave_analysis.elliott_wave import ElliottWaveAnalyzer


class TestWaveBacktester(unittest.TestCase):
    """Tests for WaveBacktester class."""
    
    def setUp(self):
        """Set up test data."""
        # Create sample data for testing
        dates = pd.date_range(start='2023-01-01', periods=200, freq='D')
        
        # Create a price pattern that resembles waves
        prices = []
        price = 100.0
        for i in range(200):
            # Add some wave-like movements
            if i < 40:  # Wave 1 (up)
                price += np.random.uniform(0.05, 0.2)
            elif i < 60:  # Wave 2 (down)
                price -= np.random.uniform(0.05, 0.15)
            elif i < 110:  # Wave 3 (up - strongest)
                price += np.random.uniform(0.1, 0.3)
            elif i < 140:  # Wave 4 (down)
                price -= np.random.uniform(0.05, 0.15)
            elif i < 180:  # Wave 5 (up)
                price += np.random.uniform(0.05, 0.2)
            else:  # After wave 5 (down)
                price -= np.random.uniform(0.1, 0.25)
                
            # Add some noise
            price += np.random.normal(0, 0.05)
            prices.append(price)
        
        # Create DataFrame with OHLCV data
        self.sample_data = pd.DataFrame({
            'open': prices,
            'high': [p + np.random.uniform(0.1, 0.5) for p in prices],
            'low': [p - np.random.uniform(0.1, 0.5) for p in prices],
            'close': [p + np.random.normal(0, 0.1) for p in prices],
            'volume': np.random.randint(1000, 10000, size=200),
        }, index=dates)
        
        # Mock ForexDataLoader
        self.mock_data_loader = MagicMock(spec=ForexDataLoader)
        self.mock_data_loader.load_data.return_value = self.sample_data
        
        # Initialize WaveBacktester with mocked dependencies
        self.backtester = WaveBacktester(data_loader=self.mock_data_loader)
    
    def test_prepare_data(self):
        """Test prepare_data method."""
        # Test with default parameters
        training_data, testing_data = self.backtester.prepare_data(
            symbol="EURUSD",
            start_date="2023-01-01",
            end_date="2023-07-20",
            timeframe="1D",
        )
        
        # Verify data was split correctly
        self.assertEqual(len(training_data) + len(testing_data), len(self.sample_data))
        self.assertAlmostEqual(len(training_data) / len(self.sample_data), 0.7, delta=0.01)
        
        # Test with custom split ratio
        training_data, testing_data = self.backtester.prepare_data(
            symbol="EURUSD",
            start_date="2023-01-01",
            end_date="2023-07-20",
            timeframe="1D",
            split_ratio=0.8,
        )
        
        # Verify custom split ratio was used
        self.assertAlmostEqual(len(training_data) / len(self.sample_data), 0.8, delta=0.01)
    
    def test_run_rolling_window_backtest(self):
        """Test run_rolling_window_backtest method."""
        # Mock wave detection to ensure we have some patterns
        with patch.object(
            ElliottWaveAnalyzer, 'detect_waves', 
            return_value={
                'impulse_5_1_start': [(10, 101.0)],
                'impulse_5_1_end': [(20, 105.0)],
                'impulse_5_2_start': [(20, 105.0)],
                'impulse_5_2_end': [(30, 103.0)],
                'impulse_5_3_start': [(30, 103.0)],
                'impulse_5_3_end': [(50, 110.0)],
                'impulse_5_4_start': [(50, 110.0)],
                'impulse_5_4_end': [(60, 107.0)],
                'impulse_5_5_start': [(60, 107.0)],
                'impulse_5_5_end': [(70, 112.0)],
            }
        ):
            # Run backtest on sample data
            results = self.backtester.run_rolling_window_backtest(
                data=self.sample_data,
                window_size=100,
                step_size=20,
                prediction_horizon=20,
            )
            
            # Verify results structure
            self.assertIn("total_windows", results)
            self.assertIn("impulse_patterns_detected", results)
            self.assertIn("corrective_patterns_detected", results)
            self.assertIn("predictions_made", results)
            self.assertIn("correct_predictions", results)
            self.assertIn("prediction_accuracy", results)
            self.assertIn("windows", results)
            
            # Verify we have some predictions
            self.assertGreater(results["predictions_made"], 0)
            
            # Verify predictions were evaluated
            self.assertGreaterEqual(results["correct_predictions"], 0)
            
            # Verify accuracy is between 0 and 1
            self.assertGreaterEqual(results["prediction_accuracy"], 0.0)
            self.assertLessEqual(results["prediction_accuracy"], 1.0)
    
    def test_backtest_multiple_timeframes(self):
        """Test backtest_multiple_timeframes method."""
        # Mock prepare_data to return our sample data
        with patch.object(
            WaveBacktester, 'prepare_data', 
            return_value=(self.sample_data.iloc[:140], self.sample_data.iloc[140:])
        ):
            # Mock run_rolling_window_backtest to return consistent results
            with patch.object(
                WaveBacktester, 'run_rolling_window_backtest', 
                return_value={
                    "total_windows": 5,
                    "impulse_patterns_detected": 2,
                    "corrective_patterns_detected": 1,
                    "predictions_made": 3,
                    "correct_predictions": 2,
                    "prediction_accuracy": 2/3,
                    "windows": [],
                }
            ):
                # Run multi-timeframe backtest
                results = self.backtester.backtest_multiple_timeframes(
                    symbol="EURUSD",
                    start_date="2023-01-01",
                    end_date="2023-07-20",
                    timeframes=["1D", "4H", "1H"],
                )
                
                # Verify results structure
                self.assertIn("1D", results)
                self.assertIn("4H", results)
                self.assertIn("1H", results)
                
                # Verify each timeframe has complete results
                for tf in ["1D", "4H", "1H"]:
                    self.assertIn("total_windows", results[tf])
                    self.assertIn("impulse_patterns_detected", results[tf])
                    self.assertIn("corrective_patterns_detected", results[tf])
                    self.assertIn("predictions_made", results[tf])
                    self.assertIn("correct_predictions", results[tf])
                    self.assertIn("prediction_accuracy", results[tf])


class TestPerformanceMetrics(unittest.TestCase):
    """Tests for PerformanceMetrics class."""
    
    def setUp(self):
        """Set up test data."""
        # Create sample backtest results
        self.sample_results = {
            "total_windows": 10,
            "impulse_patterns_detected": 5,
            "corrective_patterns_detected": 3,
            "predictions_made": 8,
            "correct_predictions": 6,
            "prediction_accuracy": 0.75,  # 6/8
            "windows": [
                {
                    "start_idx": 0,
                    "end_idx": 100,
                    "impulse_patterns": 1,
                    "corrective_patterns": 1,
                    "predictions_made": 2,
                    "correct_predictions": 2,
                    "prediction_details": [
                        {
                            "pattern_type": "impulse",
                            "predicted_direction": "down",
                            "predicted_target": 95.0,
                            "actual_outcome": 94.5,
                            "correct": True,
                            "time_to_target": 5,
                        },
                        {
                            "pattern_type": "corrective",
                            "predicted_direction": "up",
                            "predicted_target": 105.0,
                            "actual_outcome": 105.5,
                            "correct": True,
                            "time_to_target": 8,
                        },
                    ]
                },
                {
                    "start_idx": 20,
                    "end_idx": 120,
                    "impulse_patterns": 1,
                    "corrective_patterns": 0,
                    "predictions_made": 1,
                    "correct_predictions": 1,
                    "prediction_details": [
                        {
                            "pattern_type": "impulse",
                            "predicted_direction": "up",
                            "predicted_target": 110.0,
                            "actual_outcome": 110.5,
                            "correct": True,
                            "time_to_target": 10,
                        },
                    ]
                },
                {
                    "start_idx": 40,
                    "end_idx": 140,
                    "impulse_patterns": 2,
                    "corrective_patterns": 0,
                    "predictions_made": 2,
                    "correct_predictions": 1,
                    "prediction_details": [
                        {
                            "pattern_type": "impulse",
                            "predicted_direction": "up",
                            "predicted_target": 115.0,
                            "actual_outcome": 115.5,
                            "correct": True,
                            "time_to_target": 12,
                        },
                        {
                            "pattern_type": "impulse",
                            "predicted_direction": "down",
                            "predicted_target": 100.0,
                            "actual_outcome": 105.0,
                            "correct": False,
                            "time_to_target": None,
                        },
                    ]
                },
                {
                    "start_idx": 60,
                    "end_idx": 160,
                    "impulse_patterns": 1,
                    "corrective_patterns": 2,
                    "predictions_made": 3,
                    "correct_predictions": 2,
                    "prediction_details": [
                        {
                            "pattern_type": "impulse",
                            "predicted_direction": "down",
                            "predicted_target": 105.0,
                            "actual_outcome": 104.5,
                            "correct": True,
                            "time_to_target": 7,
                        },
                        {
                            "pattern_type": "corrective",
                            "predicted_direction": "up",
                            "predicted_target": 110.0,
                            "actual_outcome": 108.0,
                            "correct": False,
                            "time_to_target": None,
                        },
                        {
                            "pattern_type": "corrective",
                            "predicted_direction": "down",
                            "predicted_target": 100.0,
                            "actual_outcome": 99.5,
                            "correct": True,
                            "time_to_target": 15,
                        },
                    ]
                },
            ]
        }
        
        # Create sample actual outcomes
        self.sample_outcomes = [
            {
                "correct": True,
                "time_to_target": 5,
                "actual_price": 94.5,
                "max_favorable_move": 6.0,
                "max_adverse_move": 1.5,
                "risk_reward_ratio": 4.0,
            },
            {
                "correct": False,
                "time_to_target": None,
                "actual_price": 105.0,
                "max_favorable_move": 2.0,
                "max_adverse_move": 3.0,
                "risk_reward_ratio": 0.67,
            },
            {
                "correct": True,
                "time_to_target": 10,
                "actual_price": 110.5,
                "max_favorable_move": 5.5,
                "max_adverse_move": 1.0,
                "risk_reward_ratio": 5.5,
            },
        ]
    
    def test_calculate_metrics(self):
        """Test calculate_metrics method."""
        # Calculate metrics
        metrics = PerformanceMetrics.calculate_metrics(self.sample_results)
        
        # Verify overall metrics
        self.assertEqual(metrics["overall"]["total_windows"], 10)
        self.assertEqual(metrics["overall"]["predictions_made"], 8)
        self.assertEqual(metrics["overall"]["correct_predictions"], 6)
        self.assertEqual(metrics["overall"]["incorrect_predictions"], 2)
        self.assertEqual(metrics["overall"]["accuracy"], 0.75)
        self.assertEqual(metrics["overall"]["detection_rate"], 0.8)  # (5+3)/10
        
        # Calculate with window details
        metrics_with_windows = PerformanceMetrics.calculate_metrics(
            self.sample_results, include_windows=True
        )
        
        # Verify pattern-specific metrics
        self.assertIn("by_pattern_type", metrics_with_windows)
        self.assertIn("impulse", metrics_with_windows["by_pattern_type"])
        self.assertIn("corrective", metrics_with_windows["by_pattern_type"])
        
        # Check impulse metrics
        impulse_metrics = metrics_with_windows["by_pattern_type"]["impulse"]
        self.assertEqual(impulse_metrics["predictions"], 5)
        self.assertEqual(impulse_metrics["correct"], 4)
        self.assertEqual(impulse_metrics["accuracy"], 0.8)  # 4/5
        
        # Check corrective metrics
        corrective_metrics = metrics_with_windows["by_pattern_type"]["corrective"]
        self.assertEqual(corrective_metrics["predictions"], 3)
        self.assertEqual(corrective_metrics["correct"], 2)
        self.assertEqual(corrective_metrics["accuracy"], 2/3)  # 2/3
    
    def test_calculate_risk_reward_metrics(self):
        """Test calculate_risk_reward_metrics method."""
        # Calculate risk/reward metrics
        metrics = PerformanceMetrics.calculate_risk_reward_metrics(self.sample_outcomes)
        
        # Verify metrics
        self.assertAlmostEqual(metrics["avg_risk_reward_ratio"], (4.0 + 0.67 + 5.5) / 3, places=2)
        self.assertAlmostEqual(metrics["median_risk_reward_ratio"], 4.0, places=2)
        self.assertAlmostEqual(metrics["avg_favorable_move"], (6.0 + 2.0 + 5.5) / 3, places=2)
        self.assertAlmostEqual(metrics["max_favorable_move"], 6.0, places=2)
        self.assertAlmostEqual(metrics["avg_adverse_move"], (1.5 + 3.0 + 1.0) / 3, places=2)
        self.assertAlmostEqual(metrics["max_adverse_move"], 3.0, places=2)
        self.assertAlmostEqual(metrics["avg_time_to_target"], (5 + 10) / 2, places=2)
        self.assertAlmostEqual(metrics["win_rate"], 2/3, places=2)
    
    def test_calculate_multi_timeframe_metrics(self):
        """Test calculate_multi_timeframe_metrics method."""
        # Create multi-timeframe results
        multi_tf_results = {
            "1D": {
                "total_windows": 10,
                "impulse_patterns_detected": 5,
                "corrective_patterns_detected": 3,
                "predictions_made": 8,
                "correct_predictions": 6,
                "prediction_accuracy": 0.75,
            },
            "4H": {
                "total_windows": 20,
                "impulse_patterns_detected": 10,
                "corrective_patterns_detected": 5,
                "predictions_made": 15,
                "correct_predictions": 9,
                "prediction_accuracy": 0.6,
            },
            "1H": {
                "total_windows": 40,
                "impulse_patterns_detected": 15,
                "corrective_patterns_detected": 10,
                "predictions_made": 25,
                "correct_predictions": 20,
                "prediction_accuracy": 0.8,
            },
        }
        
        # Calculate multi-timeframe metrics
        metrics = PerformanceMetrics.calculate_multi_timeframe_metrics(multi_tf_results)
        
        # Verify overall metrics
        self.assertEqual(metrics["overall"]["total_predictions"], 8 + 15 + 25)
        self.assertEqual(metrics["overall"]["correct_predictions"], 6 + 9 + 20)
        self.assertAlmostEqual(metrics["overall"]["accuracy"], (6 + 9 + 20) / (8 + 15 + 25), places=2)
        self.assertEqual(metrics["overall"]["best_timeframe"], "1H")
        self.assertEqual(metrics["overall"]["best_accuracy"], 0.8)
        
        # Verify per-timeframe metrics
        self.assertIn("by_timeframe", metrics)
        self.assertIn("1D", metrics["by_timeframe"])
        self.assertIn("4H", metrics["by_timeframe"])
        self.assertIn("1H", metrics["by_timeframe"])
        
        # Check 1D metrics
        daily_metrics = metrics["by_timeframe"]["1D"]["overall"]
        self.assertEqual(daily_metrics["accuracy"], 0.75)
        
        # Check 4H metrics
        h4_metrics = metrics["by_timeframe"]["4H"]["overall"]
        self.assertEqual(h4_metrics["accuracy"], 0.6)
        
        # Check 1H metrics
        h1_metrics = metrics["by_timeframe"]["1H"]["overall"]
        self.assertEqual(h1_metrics["accuracy"], 0.8)
    
    def test_calculate_profitability(self):
        """Test calculate_profitability method."""
        # Calculate profitability metrics
        metrics = PerformanceMetrics.calculate_profitability(
            self.sample_outcomes,
            risk_per_trade=0.01,  # 1% risk
            account_size=10000.0,
            stop_multiplier=1.5,
        )
        
        # Verify metrics
        self.assertEqual(metrics["initial_capital"], 10000.0)
        self.assertIn("final_capital", metrics)
        self.assertIn("total_return_pct", metrics)
        self.assertEqual(metrics["win_count"], 2)
        self.assertEqual(metrics["loss_count"], 1)
        self.assertIn("avg_win_pct", metrics)
        self.assertIn("avg_loss_pct", metrics)
        self.assertIn("profit_factor", metrics)
        self.assertIn("max_drawdown_pct", metrics)
        self.assertIn("equity_curve", metrics)
        self.assertEqual(len(metrics["equity_curve"]), 4)  # Initial + 3 trades