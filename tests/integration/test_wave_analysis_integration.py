"""Integration tests for Elliott Wave analysis components.

This module contains integration tests for the Elliott Wave analyzer, Fibonacci calculator,
and fractal analysis components working together.
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

from fxml4.strategy.integrated_strategy import SignalSource, SignalType
from fxml4.strategy.wave_signal_generator import WaveSignalGenerator
from fxml4.wave_analysis.elliott_wave import (
    ElliottWaveAnalyzer,
    ElliottWavePattern,
    WaveType,
)
from fxml4.wave_analysis.fibonacci import FibonacciCalculator
from fxml4.wave_analysis.fractal import FractalDegreeHandler


class MockRagSystem:
    """Mock RAG system for testing."""

    def query(self, query_text):
        """Mock query response."""
        return """
        This pattern appears to be a valid Elliott Wave structure.
        The impulse wave structure shows good adherence to Elliott Wave rules
        with proper wave proportions and relationships.

        Confidence: 0.85
        """


class TestWaveAnalysisIntegration(unittest.TestCase):
    """Integration tests for Elliott Wave analysis components."""

    def setUp(self):
        """Set up test environment."""
        self.wave_analyzer = ElliottWaveAnalyzer()
        self.fib_calculator = FibonacciCalculator()
        self.fractal_handler = FractalDegreeHandler()

        # Create sample data with a clear impulse pattern
        self.dates = pd.date_range(start="2025-01-01", periods=100, freq="H")
        self.data = pd.DataFrame(
            {
                "open": np.zeros(100),
                "high": np.zeros(100),
                "low": np.zeros(100),
                "close": np.zeros(100),
                "volume": np.random.randint(100, 1000, 100),
            },
            index=self.dates,
        )

        # Create impulse wave pattern (1-2-3-4-5)
        # Wave 1: Bullish move
        self.data.loc[self.dates[0:20], "close"] = np.linspace(100, 110, 20)
        # Wave 2: Correction (not exceeding start of wave 1)
        self.data.loc[self.dates[20:30], "close"] = np.linspace(110, 103, 10)
        # Wave 3: Strong bullish move (longest)
        self.data.loc[self.dates[30:60], "close"] = np.linspace(103, 125, 30)
        # Wave 4: Correction (not overlapping with wave 1)
        self.data.loc[self.dates[60:70], "close"] = np.linspace(125, 118, 10)
        # Wave 5: Final bullish move
        self.data.loc[self.dates[70:100], "close"] = np.linspace(118, 130, 30)

        # Set open, high, low based on close for simplicity
        self.data["open"] = self.data["close"] - 0.5
        self.data["high"] = self.data["close"] + 0.5
        self.data["low"] = self.data["close"] - 0.8

    def test_wave_analysis_with_fibonacci(self):
        """Test Elliott Wave analyzer with Fibonacci calculator."""
        # Analyze the data with wave analyzer
        wave_count = self.wave_analyzer.analyze(self.data)

        # Verify wave count is detected
        self.assertIsNotNone(wave_count)
        self.assertTrue(len(wave_count.waves) > 0)

        # Get the latest wave pattern
        last_wave = wave_count.waves[-1]

        # Verify it's an impulse pattern
        self.assertEqual(last_wave.wave_type, WaveType.IMPULSE)

        # Calculate Fibonacci retracement levels
        retracement_levels = self.fib_calculator.calculate_retracement_levels(
            start_price=100,  # Approximate start of the whole move
            end_price=130,  # Approximate end of the move
        )

        # Verify retracement levels are correct
        self.assertAlmostEqual(retracement_levels[0.236], 122.96, delta=0.01)
        self.assertAlmostEqual(retracement_levels[0.382], 118.46, delta=0.01)
        self.assertAlmostEqual(retracement_levels[0.5], 115.00, delta=0.01)
        self.assertAlmostEqual(retracement_levels[0.618], 111.54, delta=0.01)
        self.assertAlmostEqual(retracement_levels[0.786], 106.44, delta=0.01)

        # Calculate Fibonacci extension levels
        extension_levels = self.fib_calculator.calculate_extension_levels(
            start_price=100,  # Start of wave 1
            end_price=110,  # End of wave 1
            retracement_price=103,  # End of wave 2
        )

        # Verify extension levels are correct
        self.assertAlmostEqual(extension_levels[1.0], 113.00, delta=0.01)
        self.assertAlmostEqual(extension_levels[1.618], 119.14, delta=0.01)
        self.assertAlmostEqual(extension_levels[2.618], 129.18, delta=0.01)

        # Verify wave relationships using Fibonacci calculator
        is_valid = self.fib_calculator.validate_impulse_wave_relationships(
            wave_1_length=10,  # 110 - 100
            wave_3_length=22,  # 125 - 103
            wave_5_length=12,  # 130 - 118
        )

        self.assertTrue(is_valid)

    def test_fractal_analysis_integration(self):
        """Test fractal analysis integration with Elliott Wave analysis."""
        # Create multi-timeframe data
        hourly_data = self.data.copy()

        # Create 4-hour data by resampling
        four_hour_data = hourly_data.resample("4H").agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )

        # Initialize fractal handler with both timeframes
        self.fractal_handler.add_timeframe_data("1H", hourly_data)
        self.fractal_handler.add_timeframe_data("4H", four_hour_data)

        # Get fractal degrees
        fractal_degrees = self.fractal_handler.analyze_fractal_degrees()

        # Verify fractal degrees were calculated
        self.assertTrue(len(fractal_degrees) > 0)

        # Verify the 4H timeframe has higher degree waves than 1H
        highest_1h_degree = max(
            [
                d.value
                for tf, degrees in fractal_degrees.items()
                if tf == "1H"
                for d in degrees
            ]
        )
        lowest_4h_degree = min(
            [
                d.value
                for tf, degrees in fractal_degrees.items()
                if tf == "4H"
                for d in degrees
            ]
        )

        self.assertLessEqual(highest_1h_degree, lowest_4h_degree)

    def test_wave_signal_generator(self):
        """Test wave signal generator with Elliott Wave analysis."""
        # Create mock RAG system
        mock_rag = MockRagSystem()

        # Create wave signal generator
        config = {
            "threshold": 0.6,
            "use_llm": True,
            "rag": mock_rag,
        }
        wave_signal_generator = WaveSignalGenerator(self.wave_analyzer, config)

        # Generate signals
        signals = wave_signal_generator.generate_signals(
            self.data, symbol="EURUSD", timeframe="1H"
        )

        # Verify signals are generated
        self.assertTrue(len(signals) > 0)

        # Check for proper signal types based on the impulse pattern we created
        signal_types = [signal.signal_type for signal in signals]

        # After completion of an impulse pattern, we expect ENTRY_SHORT or EXIT_LONG signals
        expected_types = [SignalType.ENTRY_SHORT, SignalType.EXIT_LONG]

        # At least one of the expected signal types should be present
        self.assertTrue(
            any(signal_type in expected_types for signal_type in signal_types)
        )

        # Verify signal source is WAVE
        for signal in signals:
            self.assertEqual(signal.source, SignalSource.WAVE)

        # Verify signal metadata contains wave information
        for signal in signals:
            self.assertIn("pattern_type", signal.metadata)
            self.assertIn("wave_confidence", signal.metadata)
            self.assertIn("pattern_details", signal.metadata)


if __name__ == "__main__":
    unittest.main()
