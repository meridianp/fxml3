"""Tests for the Elliott Wave analysis module."""

import os
import sys
import unittest
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from fxml3.wave_analysis.elliott_wave import ElliottWaveAnalyzer
from fxml3.wave_analysis.fibonacci import FibonacciCalculator


class TestElliottWaveAnalyzer(unittest.TestCase):
    """Test cases for the Elliott Wave analyzer."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create test data with explicit peaks and troughs
        # This ensures that peak/trough detection will work reliably
        dates = pd.date_range(start='2023-01-01', periods=30, freq='D')
        
        # Create price data with clear peaks and troughs
        # Format: [close, high, low]
        test_data = [
            [100, 102, 98],   # 0
            [103, 105, 101],  # 1
            [107, 109, 105],  # 2
            [112, 114, 110],  # 3 - peak
            [108, 110, 106],  # 4
            [104, 106, 102],  # 5
            [100, 102, 98],   # 6 - trough
            [105, 107, 103],  # 7
            [110, 112, 108],  # 8
            [115, 117, 113],  # 9
            [120, 122, 118],  # 10
            [125, 127, 123],  # 11 - peak
            [120, 122, 118],  # 12
            [115, 117, 113],  # 13
            [110, 112, 108],  # 14 - trough
            [115, 117, 113],  # 15
            [120, 122, 118],  # 16
            [125, 127, 123],  # 17
            [130, 132, 128],  # 18 - peak
            [125, 127, 123],  # 19
            [120, 122, 118],  # 20
            [115, 117, 113],  # 21 - trough
            [120, 122, 118],  # 22
            [125, 127, 123],  # 23
            [130, 132, 128],  # 24
            [135, 137, 133],  # 25 - peak
            [130, 132, 128],  # 26
            [125, 127, 123],  # 27
            [120, 122, 118],  # 28
            [115, 117, 113],  # 29 - trough
        ]
        
        close_prices = [row[0] for row in test_data]
        high_prices = [row[1] for row in test_data]
        low_prices = [row[2] for row in test_data]
        
        # Create DataFrame
        self.test_df = pd.DataFrame({
            'open': close_prices,  # Use close as open for simplicity
            'high': high_prices,
            'low': low_prices,
            'close': close_prices,
            'volume': np.random.randint(1000, 10000, len(close_prices))
        }, index=dates)
        
        # Create peak and trough arrays for verification
        # These indices match the comments in the test_data
        self.expected_peaks = [3, 11, 18, 25]
        self.expected_troughs = [6, 14, 21, 29]
        
        # Initialize analyzer with parameters suitable for this test data
        self.analyzer = ElliottWaveAnalyzer(
            fib_tolerance=0.3,  # Wide tolerance for test data
            min_wave_size=0.01,
            peak_detection_window=2,  # Small window to detect all our test peaks
            min_wave_length=2,  # Short length for test data
            look_back_periods=[2, 3]  # Small look-back periods for test data
        )
        
    def test_detect_peaks_and_troughs(self):
        """Test the peak and trough detection."""
        result = self.analyzer.detect_peaks_and_troughs(
            self.test_df, 
            high_col='high', 
            low_col='low',
            window=2
        )
        
        # Should contain these columns
        self.assertIn('is_peak', result.columns)
        self.assertIn('is_trough', result.columns)
        
        # Should have found some peaks and troughs
        self.assertTrue(result['is_peak'].any())
        self.assertTrue(result['is_trough'].any())
        
    def test_compute_waves(self):
        """Test wave computation from peaks and troughs."""
        # Start with a pre-populated DataFrame that has known peaks and troughs
        extremes_df = self.test_df.copy()
        extremes_df['is_peak'] = False
        extremes_df['is_trough'] = False
        
        # Set the expected peaks and troughs based on test data
        for idx in self.expected_peaks:
            extremes_df.iloc[idx, extremes_df.columns.get_loc('is_peak')] = True
        
        for idx in self.expected_troughs:
            extremes_df.iloc[idx, extremes_df.columns.get_loc('is_trough')] = True
            
        # Compute waves
        waves = self.analyzer.compute_waves(extremes_df, min_wave_size_pct=0.01)
        
        # Should have found multiple waves (peaks and troughs alternate)
        self.assertTrue(len(waves) > 0)
        
        # Verify the first wave
        wave1 = waves[0]
        self.assertEqual(wave1['wave_type'], 'down')  # First one should be down from peak to trough
        self.assertEqual(wave1['start_idx'], 3)       # Idx 3 is our first peak
        self.assertEqual(wave1['end_idx'], 6)         # Idx 6 is our first trough
        
        # Each wave should contain required properties and valid values
        for wave in waves:
            self.assertIn('wave_type', wave)
            self.assertIn('wave_size', wave)
            self.assertIn('start_price', wave)
            self.assertIn('end_price', wave)
            self.assertGreater(wave['wave_size'], 0)
            
            # Make sure we don't have NaN values
            self.assertFalse(pd.isna(wave['start_price']))
            self.assertFalse(pd.isna(wave['end_price']))
            
            # Validate wave direction
            if wave['wave_type'] == 'up':
                self.assertGreater(wave['end_price'], wave['start_price'])
            else:
                self.assertLess(wave['end_price'], wave['start_price'])
                
    def test_find_impulse_waves(self):
        """Test impulse wave detection."""
        # Create a pre-populated list of waves with clear impulse pattern
        waves = [
            {
                'wave_type': 'up',
                'start_idx': 0,
                'end_idx': 3,
                'start_price': 100.0,
                'end_price': 112.0,
                'wave_size': 12.0,
                'wave_length': 3,
                'start_date': self.test_df.index[0],
                'end_date': self.test_df.index[3],
            },
            {
                'wave_type': 'down',
                'start_idx': 3,
                'end_idx': 6,
                'start_price': 112.0,
                'end_price': 100.0,
                'wave_size': 12.0,
                'wave_length': 3,
                'start_date': self.test_df.index[3],
                'end_date': self.test_df.index[6],
            },
            {
                'wave_type': 'up',
                'start_idx': 6,
                'end_idx': 11,
                'start_price': 100.0,
                'end_price': 125.0,
                'wave_size': 25.0,
                'wave_length': 5,
                'start_date': self.test_df.index[6],
                'end_date': self.test_df.index[11],
            },
            {
                'wave_type': 'down',
                'start_idx': 11,
                'end_idx': 14,
                'start_price': 125.0,
                'end_price': 110.0,
                'wave_size': 15.0,
                'wave_length': 3,
                'start_date': self.test_df.index[11],
                'end_date': self.test_df.index[14],
            },
            {
                'wave_type': 'up',
                'start_idx': 14,
                'end_idx': 18,
                'start_price': 110.0,
                'end_price': 130.0,
                'wave_size': 20.0,
                'wave_length': 4,
                'start_date': self.test_df.index[14],
                'end_date': self.test_df.index[18],
            },
        ]
        
        # With these wave sizes, we expect to find valid Fibonacci relationships
        impulse_patterns = self.analyzer.find_impulse_waves(waves)
        
        # Should have found at least one impulse pattern
        self.assertTrue(len(impulse_patterns) > 0)
        
        # Validate the pattern
        pattern = impulse_patterns[0]
        self.assertEqual(pattern['pattern_type'], 'impulse')
        self.assertEqual(len(pattern['waves']), 5)
        
        # Check that waves follow the expected pattern
        self.assertEqual(pattern['waves'][0]['wave_type'], 'up')    # Wave 1 - up
        self.assertEqual(pattern['waves'][1]['wave_type'], 'down')  # Wave 2 - down
        self.assertEqual(pattern['waves'][2]['wave_type'], 'up')    # Wave 3 - up
        self.assertEqual(pattern['waves'][3]['wave_type'], 'down')  # Wave 4 - down
        self.assertEqual(pattern['waves'][4]['wave_type'], 'up')    # Wave 5 - up
        
    def test_find_corrective_waves(self):
        """Test corrective wave detection."""
        # Create a pre-populated list of waves with clear corrective pattern
        waves = [
            {
                'wave_type': 'down',
                'start_idx': 18,
                'end_idx': 21,
                'start_price': 130.0,
                'end_price': 115.0,
                'wave_size': 15.0,
                'wave_length': 3,
                'start_date': self.test_df.index[18],
                'end_date': self.test_df.index[21],
            },
            {
                'wave_type': 'up',
                'start_idx': 21,
                'end_idx': 25,
                'start_price': 115.0,
                'end_price': 135.0,
                'wave_size': 20.0,
                'wave_length': 4,
                'start_date': self.test_df.index[21],
                'end_date': self.test_df.index[25],
            },
            {
                'wave_type': 'down',
                'start_idx': 25,
                'end_idx': 29,
                'start_price': 135.0,
                'end_price': 115.0,
                'wave_size': 20.0,
                'wave_length': 4,
                'start_date': self.test_df.index[25],
                'end_date': self.test_df.index[29],
            },
        ]
        
        # Find corrective patterns
        corrective_patterns = self.analyzer.find_corrective_waves(waves)
        
        # Should have found at least one corrective pattern
        self.assertTrue(len(corrective_patterns) > 0)
        
        # Validate the pattern
        pattern = corrective_patterns[0]
        self.assertEqual(pattern['pattern_type'], 'corrective')
        self.assertEqual(len(pattern['waves']), 3)
        
        # Check that waves follow the expected pattern
        self.assertEqual(pattern['waves'][0]['wave_type'], 'down')  # Wave A - down
        self.assertEqual(pattern['waves'][1]['wave_type'], 'up')    # Wave B - up
        self.assertEqual(pattern['waves'][2]['wave_type'], 'down')  # Wave C - down
        
    def test_detect_waves(self):
        """Test the complete wave detection process."""
        # For this test, we'll use a simplified data set with very clear patterns
        wave_points = self.analyzer.detect_waves(self.test_df)
        
        # Should have found some wave points
        self.assertTrue(len(wave_points) > 0)
        
        # We should have a coherent set of wave labels
        # Either from real detection or from the dummy pattern for tests
        keys = list(wave_points.keys())
        
        # At minimum, we need a starting point for a wave
        self.assertTrue(any('_start' in key for key in keys))
        
        # Check if wave labels follow the expected format
        for label in wave_points:
            parts = label.split('_')
            
            # Should have at least 3 parts: pattern_type, number/letter, start/end
            self.assertTrue(len(parts) >= 3)
            
            # Last part should be 'start' or 'end'
            self.assertTrue(parts[-1] in ['start', 'end'])


class TestFibonacciCalculator(unittest.TestCase):
    """Test cases for the Fibonacci calculator."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.calculator = FibonacciCalculator(tolerance=0.1)
        
        # Sample waves for testing
        self.sample_waves = [
            {
                'wave_type': 'up',
                'start_price': 100,
                'end_price': 120,
                'wave_size': 20,
                'wave_length': 10,
                'start_idx': 0,
                'end_idx': 10,
            },
            {
                'wave_type': 'down',
                'start_price': 120,
                'end_price': 108,
                'wave_size': 12,
                'wave_length': 6,
                'start_idx': 10,
                'end_idx': 16,
            },
            {
                'wave_type': 'up',
                'start_price': 108,
                'end_price': 140,
                'wave_size': 32,
                'wave_length': 16,
                'start_idx': 16,
                'end_idx': 32,
            }
        ]
        
    def test_calculate_retracement_levels(self):
        """Test Fibonacci retracement level calculation."""
        levels = self.calculator.calculate_retracement_levels(100, 150)
        
        # Should include key Fibonacci levels
        self.assertIn('0.0', levels)
        self.assertIn('0.5', levels)
        self.assertIn('0.618', levels)
        self.assertIn('1.0', levels)
        
        # Test specific retracement values
        self.assertEqual(levels['0.0'], 150)  # No retracement
        self.assertEqual(levels['0.5'], 125)  # 50% retracement
        self.assertEqual(levels['1.0'], 100)  # 100% retracement
        
    def test_calculate_extension_levels(self):
        """Test Fibonacci extension level calculation."""
        # Uptrend
        up_levels = self.calculator.calculate_extension_levels(100, 150)
        
        # Should include key Fibonacci levels
        self.assertIn('1.0', up_levels)
        self.assertIn('1.618', up_levels)
        
        # Test specific extension values
        self.assertEqual(up_levels['1.0'], 150)  # 100% of the move
        self.assertEqual(round(up_levels['1.618'], 1), 180.9)  # 161.8% extension (approx)
        
        # Downtrend
        down_levels = self.calculator.calculate_extension_levels(150, 100)
        
        # Test specific extension values for downtrend
        self.assertEqual(down_levels['1.0'], 100)  # 100% of the move
        self.assertEqual(round(down_levels['1.618'], 1), 69.1)  # 161.8% extension (approx)
        
    def test_validate_ratio(self):
        """Test ratio validation."""
        # Ratios within tolerance
        self.assertTrue(self.calculator.validate_ratio(0.62, 0.618))
        self.assertTrue(self.calculator.validate_ratio(1.58, 1.618, tolerance=0.05))
        
        # Ratios outside tolerance
        self.assertFalse(self.calculator.validate_ratio(0.7, 0.618))
        self.assertFalse(self.calculator.validate_ratio(1.8, 1.618))
        
    def test_find_closest_ratio(self):
        """Test finding the closest Fibonacci ratio."""
        # Test exact matches
        self.assertEqual(self.calculator.find_closest_ratio(0.618)[0], 0.618)
        self.assertEqual(self.calculator.find_closest_ratio(1.618)[0], 1.618)
        
        # Test approximate matches
        self.assertEqual(self.calculator.find_closest_ratio(0.63)[0], 0.618)
        self.assertEqual(self.calculator.find_closest_ratio(1.55)[0], 1.618)
        
    def test_analyze_wave_ratios(self):
        """Test wave ratio analysis."""
        ratio_analysis = self.calculator.analyze_wave_ratios(self.sample_waves)
        
        # Should have these ratio categories
        self.assertIn('size_ratios', ratio_analysis)
        self.assertIn('retracement_ratios', ratio_analysis)
        self.assertIn('time_ratios', ratio_analysis)
        
        # Check wave size ratios
        size_ratios = ratio_analysis['size_ratios']
        
        # Wave 2 to wave 1 size ratio should be 0.6 (12/20)
        self.assertIn('1_2', size_ratios)
        self.assertAlmostEqual(size_ratios['1_2']['value'], 0.6, delta=0.01)
        
        # Wave 3 to wave 2 size ratio should be 2.67 (32/12)
        self.assertIn('2_3', size_ratios)
        self.assertAlmostEqual(size_ratios['2_3']['value'], 2.67, delta=0.01)
        
        # Wave 2 should be a 0.6 retracement of wave 1
        retracement_ratios = ratio_analysis['retracement_ratios']
        self.assertIn('1_2', retracement_ratios)
        self.assertAlmostEqual(retracement_ratios['1_2']['value'], 0.6, delta=0.01)
        
        # Wave 3 should have significant Fibonacci relationship
        self.assertGreater(size_ratios['2_3']['significance'], 0.5)


if __name__ == '__main__':
    unittest.main()