"""Tests for the fractal degree handler module."""

import os
import sys
import unittest
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from fxml3.wave_analysis.elliott_wave import ElliottWaveAnalyzer
from fxml3.wave_analysis.fractal import FractalDegreeHandler


class TestFractalDegreeHandler(unittest.TestCase):
    """Test cases for the fractal degree handler."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create sample data for multiple timeframes
        self.data_frames = {}
        self.start_date = datetime(2023, 1, 1)
        
        # Daily data (more detailed)
        self.data_frames["daily"] = self._create_test_data(
            start_date=self.start_date,
            periods=60,
            freq="D",
            pattern_type="impulse"
        )
        
        # Weekly data (higher degree)
        self.data_frames["weekly"] = self._create_test_data(
            start_date=self.start_date,
            periods=20,
            freq="W",
            pattern_type="impulse"
        )
        
        # 4-hour data (lower degree)
        self.data_frames["4h"] = self._create_test_data(
            start_date=self.start_date,
            periods=120,
            freq="4H",
            pattern_type="corrective"
        )
        
        # Initialize handler
        self.handler = FractalDegreeHandler(
            base_timeframe="daily",
            higher_degrees=1,
            lower_degrees=1
        )
        
    def _create_test_data(
        self,
        start_date: datetime,
        periods: int,
        freq: str,
        pattern_type: str = "impulse"
    ) -> pd.DataFrame:
        """Create test price data with Elliott Wave patterns.
        
        Args:
            start_date: Starting date
            periods: Number of periods
            freq: Frequency ('D', 'W', '4H', etc.)
            pattern_type: 'impulse' or 'corrective'
            
        Returns:
            DataFrame with price data
        """
        # Create date range
        dates = pd.date_range(start=start_date, periods=periods, freq=freq)
        
        # Base price and volatility
        base_price = 100.0
        volatility = 1.0
        
        # Wave sizes and durations depend on pattern type
        if pattern_type == "impulse":
            # 5-wave impulse pattern (up-down-up-down-up)
            wave_durations = [int(periods * x) for x in [0.2, 0.15, 0.3, 0.15, 0.2]]
            wave_pcts = [0.15, -0.08, 0.32, -0.12, 0.18]  # Percentage moves
        else:
            # 3-wave corrective pattern (down-up-down)
            wave_durations = [int(periods * x) for x in [0.4, 0.2, 0.4]]
            wave_pcts = [-0.2, 0.12, -0.18]  # Percentage moves
            
        # Create price data with patterns
        prices = []
        current_price = base_price
        current_pos = 0
        
        for duration, pct_move in zip(wave_durations, wave_pcts):
            for i in range(duration):
                # Calculate progress through this wave (0 to 1)
                progress = i / duration
                
                # Calculate price change based on wave move
                # Use a curve for more realistic price movement
                if pct_move > 0:
                    # Upward wave (accelerates in the middle)
                    curve_factor = 4 * progress * (1 - progress)  # Parabolic curve
                    price_change = current_price * pct_move * curve_factor
                else:
                    # Downward wave (more linear)
                    price_change = current_price * pct_move * progress
                
                # Add some random noise
                noise = np.random.normal(0, volatility)
                
                # Update the price
                new_price = current_price + price_change + noise
                prices.append(max(1.0, new_price))  # Ensure price is positive
                
                current_pos += 1
                
            # Update the starting price for the next wave
            current_price = prices[-1]
        
        # If we didn't fill all periods, pad with flat prices
        while len(prices) < periods:
            prices.append(current_price)
            
        # Create DataFrame
        df = pd.DataFrame({
            'open': prices[:-1] + [prices[-1]],  # Shift by 1, repeat last price
            'high': [p * (1 + np.random.uniform(0.001, 0.01)) for p in prices],
            'low': [p * (1 - np.random.uniform(0.001, 0.01)) for p in prices],
            'close': prices,
            'volume': np.random.randint(1000, 10000, size=len(prices))
        }, index=dates)
        
        return df
    
    def test_degree_timeframe_mapping(self):
        """Test the mapping between degrees and timeframes."""
        # Test forward mapping
        self.assertEqual(self.handler._get_timeframe_from_degree("Intermediate"), "daily")
        self.assertEqual(self.handler._get_timeframe_from_degree("Primary"), "weekly")
        self.assertEqual(self.handler._get_timeframe_from_degree("Minor"), "4h")
        
        # Test reverse mapping
        self.assertEqual(self.handler._get_degree_from_timeframe("daily"), "Intermediate")
        self.assertEqual(self.handler._get_degree_from_timeframe("weekly"), "Primary")
        self.assertEqual(self.handler._get_degree_from_timeframe("4h"), "Minor")
        
        # Test default behavior
        self.assertEqual(self.handler._get_degree_from_timeframe("unknown"), "Intermediate")
        self.assertEqual(self.handler._get_timeframe_from_degree("unknown"), "daily")
    
    def test_initialize_analyzers(self):
        """Test the initialization of wave analyzers."""
        analyzers = self.handler._initialize_analyzers()
        
        # Should have analyzers for 3 timeframes (weekly, daily, 4h)
        self.assertEqual(len(analyzers), 3)
        
        # Check timeframes
        self.assertIn("weekly", analyzers)
        self.assertIn("daily", analyzers)
        self.assertIn("4h", analyzers)
        
        # Check analyzer configurations
        self.assertGreater(analyzers["weekly"].peak_detection_window, 
                          analyzers["4h"].peak_detection_window)
    
    def test_get_degrees_to_analyze(self):
        """Test the determination of degrees to analyze."""
        degrees = self.handler._get_degrees_to_analyze()
        
        # Should include Primary (higher), Intermediate (base), and Minor (lower)
        self.assertIn("Primary", degrees)
        self.assertIn("Intermediate", degrees)
        self.assertIn("Minor", degrees)
        
        # Create a handler with more degrees
        handler2 = FractalDegreeHandler(
            base_timeframe="daily",
            higher_degrees=2,
            lower_degrees=2
        )
        
        degrees2 = handler2._get_degrees_to_analyze()
        
        # Should include Cycle, Primary, Intermediate, Minor, and Minute
        self.assertIn("Cycle", degrees2)
        self.assertIn("Primary", degrees2)
        self.assertIn("Intermediate", degrees2)
        self.assertIn("Minor", degrees2)
        self.assertIn("Minute", degrees2)
    
    def test_analyze_timeframes(self):
        """Test the analysis of multiple timeframes."""
        # Analyze timeframes
        results = self.handler.analyze_timeframes(self.data_frames)
        
        # Should have analyzed all timeframes
        self.assertIn("daily", results)
        self.assertIn("weekly", results)
        self.assertIn("4h", results)
        
        # Each result should have wave_points, labeled_data, and degree
        for tf, result in results.items():
            self.assertIn("wave_points", result)
            self.assertIn("labeled_data", result)
            self.assertIn("degree", result)
    
    def test_get_wave_annotations(self):
        """Test retrieving wave annotations for different degrees."""
        # Analyze timeframes first
        self.handler.analyze_timeframes(self.data_frames)
        
        # Get annotations for impulse waves in daily timeframe (Intermediate degree)
        daily_annotations = self.handler.get_wave_annotations(
            timeframe="daily",
            wave_col="impulse_5",
            use_degree_labels=True
        )
        
        # Should have annotations for waves 1-5
        self.assertEqual(len(daily_annotations), 5)
        
        # Labels should be in Intermediate degree format: (1), (2), (3), (4), (5)
        self.assertEqual(daily_annotations[1], "(1)")
        self.assertEqual(daily_annotations[5], "(5)")
        
        # Get annotations for weekly timeframe (Primary degree)
        weekly_annotations = self.handler.get_wave_annotations(
            timeframe="weekly",
            wave_col="impulse_5",
            use_degree_labels=True
        )
        
        # Labels should be in Primary degree format: 1, 2, 3, 4, 5
        self.assertEqual(weekly_annotations[1], "1")
        self.assertEqual(weekly_annotations[5], "5")
        
        # Test standard labels
        std_annotations = self.handler.get_wave_annotations(
            timeframe="daily",
            wave_col="impulse_5",
            use_degree_labels=False
        )
        
        # Should use standard labels: 1, 2, 3, 4, 5
        self.assertEqual(std_annotations[1], "1")
        self.assertEqual(std_annotations[5], "5")
    
    def test_identify_nested_structures(self):
        """Test the identification of nested wave structures."""
        # Analyze timeframes first
        self.handler.analyze_timeframes(self.data_frames)
        
        # Identify nested structures
        relationships = self.handler._identify_nested_structures()
        
        # Should have found some relationships between waves
        self.assertGreater(len(relationships), 0)
        
        # Check structure of a relationship
        for key, rel in relationships.items():
            # Should have higher_degree and lower_degree_waves
            self.assertIn("higher_degree", rel)
            self.assertIn("lower_degree_waves", rel)
            
            # Higher degree should have these properties
            higher = rel["higher_degree"]
            self.assertIn("timeframe", higher)
            self.assertIn("degree", higher)
            self.assertIn("type", higher)
            self.assertIn("number", higher)
            self.assertIn("start", higher)
            self.assertIn("end", higher)
            
            # Skip if no lower degree waves
            if not rel["lower_degree_waves"]:
                continue
                
            # Check a lower degree wave
            for wave_key, wave in rel["lower_degree_waves"].items():
                self.assertIn("start", wave)
                self.assertIn("end", wave)
                self.assertIn("type", wave)
                self.assertIn("number", wave)
    
    def test_get_complete_wave_structure(self):
        """Test retrieving the complete nested wave structure."""
        # Analyze timeframes first
        self.handler.analyze_timeframes(self.data_frames)
        
        # Get complete structure
        structure = self.handler.get_complete_wave_structure()
        
        # Should have found some structure
        self.assertGreater(len(structure), 0)
        
        # Check structure properties
        for key, wave in structure.items():
            self.assertIn("degree", wave)
            self.assertIn("timeframe", wave)
            self.assertIn("type", wave)
            self.assertIn("number", wave)
            self.assertIn("start", wave)
            self.assertIn("end", wave)
            self.assertIn("subwaves", wave)


if __name__ == '__main__':
    unittest.main()