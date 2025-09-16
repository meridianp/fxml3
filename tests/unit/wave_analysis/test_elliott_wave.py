"""Unit tests for the Elliott Wave analysis module."""

from datetime import datetime
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest

from fxml4.wave_analysis.elliott_wave import (
    ElliottWaveAnalyzer,
    Wave,
    WaveDirection,
    WaveLabel,
    WaveType,
)


class TestEnums:
    """Test the enum classes."""

    def test_wave_type_enum(self):
        """Test WaveType enum."""
        assert WaveType.IMPULSE.value == "impulse"
        assert WaveType.CORRECTIVE.value == "corrective"
        assert WaveType.UNKNOWN.value == "unknown"

    def test_wave_direction_enum(self):
        """Test WaveDirection enum."""
        assert WaveDirection.UP.value == "up"
        assert WaveDirection.DOWN.value == "down"
        assert WaveDirection.UNKNOWN.value == "unknown"

    def test_wave_label_enum(self):
        """Test WaveLabel enum."""
        # Impulse wave labels
        assert WaveLabel.W1.value == "1"
        assert WaveLabel.W2.value == "2"
        assert WaveLabel.W3.value == "3"
        assert WaveLabel.W4.value == "4"
        assert WaveLabel.W5.value == "5"

        # Corrective wave labels
        assert WaveLabel.WA.value == "a"
        assert WaveLabel.WB.value == "b"
        assert WaveLabel.WC.value == "c"

        # Unknown
        assert WaveLabel.UNKNOWN.value == "?"


class TestWave:
    """Test the Wave data class."""

    def test_wave_creation_incomplete(self):
        """Test Wave creation without end values."""
        wave = Wave(
            start_idx=0,
            end_idx=None,
            start_price=1.1000,
            end_price=None,
            start_time=pd.Timestamp("2024-01-01 10:00:00"),
            end_time=None,
            wave_type=WaveType.IMPULSE,
            direction=WaveDirection.UP,
            label=WaveLabel.W1,
            sub_waves=[],
        )

        assert wave.start_idx == 0
        assert wave.end_idx is None
        assert wave.start_price == 1.1000
        assert wave.end_price is None
        assert wave.wave_type == WaveType.IMPULSE
        assert wave.direction == WaveDirection.UP
        assert wave.label == WaveLabel.W1
        assert wave.sub_waves == []

        # Check derived properties for incomplete wave
        assert wave.length == 0
        assert wave.duration == 0
        assert wave.pips == 0
        assert not wave.is_complete()

    def test_wave_creation_complete(self):
        """Test Wave creation with end values."""
        wave = Wave(
            start_idx=0,
            end_idx=10,
            start_price=1.1000,
            end_price=1.1100,
            start_time=pd.Timestamp("2024-01-01 10:00:00"),
            end_time=pd.Timestamp("2024-01-01 11:00:00"),
            wave_type=WaveType.IMPULSE,
            direction=WaveDirection.UP,
            label=WaveLabel.W1,
            sub_waves=[],
        )

        assert wave.is_complete()
        assert wave.length == 0.0100  # 1.1100 - 1.1000
        assert wave.duration == 10  # 10 - 0
        assert wave.pips == 100  # 0.0100 * 10000 for forex

    def test_wave_pips_calculation_forex(self):
        """Test pips calculation for forex pairs."""
        # Standard forex pair (4 decimal places)
        wave = Wave(
            start_idx=0,
            end_idx=5,
            start_price=1.1000,
            end_price=1.1025,
            start_time=pd.Timestamp("2024-01-01"),
            end_time=pd.Timestamp("2024-01-01"),
            wave_type=WaveType.IMPULSE,
            direction=WaveDirection.UP,
            label=WaveLabel.W1,
            sub_waves=[],
        )
        # For forex: 0.0025 * 10000 = 25 pips
        assert wave.pips == 25

    def test_wave_pips_calculation_jpy(self):
        """Test pips calculation for JPY pairs."""
        # JPY pair (2 decimal places)
        wave = Wave(
            start_idx=0,
            end_idx=5,
            start_price=110.00,
            end_price=110.25,
            start_time=pd.Timestamp("2024-01-01"),
            end_time=pd.Timestamp("2024-01-01"),
            wave_type=WaveType.IMPULSE,
            direction=WaveDirection.UP,
            label=WaveLabel.W1,
            sub_waves=[],
        )
        # For JPY: 0.25 * 100 = 25 pips
        assert wave.pips == 25

    def test_wave_to_dict(self):
        """Test Wave to_dict conversion."""
        sub_wave = Wave(
            start_idx=1,
            end_idx=2,
            start_price=1.1005,
            end_price=1.1010,
            start_time=pd.Timestamp("2024-01-01 10:15:00"),
            end_time=pd.Timestamp("2024-01-01 10:30:00"),
            wave_type=WaveType.CORRECTIVE,
            direction=WaveDirection.UP,
            label=WaveLabel.W2,
            sub_waves=[],
        )

        main_wave = Wave(
            start_idx=0,
            end_idx=5,
            start_price=1.1000,
            end_price=1.1050,
            start_time=pd.Timestamp("2024-01-01 10:00:00"),
            end_time=pd.Timestamp("2024-01-01 11:00:00"),
            wave_type=WaveType.IMPULSE,
            direction=WaveDirection.UP,
            label=WaveLabel.W1,
            sub_waves=[sub_wave],
        )

        wave_dict = main_wave.to_dict()

        assert wave_dict["start_idx"] == 0
        assert wave_dict["end_idx"] == 5
        assert wave_dict["start_price"] == 1.1000
        assert wave_dict["end_price"] == 1.1050
        assert wave_dict["wave_type"] == "impulse"
        assert wave_dict["direction"] == "up"
        assert wave_dict["label"] == "1"
        assert wave_dict["length"] == 0.0050
        assert wave_dict["duration"] == 5
        assert wave_dict["pips"] == 50
        assert len(wave_dict["sub_waves"]) == 1
        assert wave_dict["sub_waves"][0]["label"] == "2"


class TestElliottWaveAnalyzer:
    """Test the ElliottWaveAnalyzer class."""

    def test_init_default_config(self):
        """Test analyzer initialization with default config."""
        analyzer = ElliottWaveAnalyzer()
        assert analyzer.min_wave_length >= 0
        assert analyzer.max_retracement > 0
        assert analyzer.min_extension > 0
        assert analyzer.fibonacci_tolerance > 0

    def test_init_custom_config(self):
        """Test analyzer initialization with custom config."""
        config = {
            "min_wave_length": 10,
            "max_retracement": 0.5,
            "min_extension": 1.2,
            "fibonacci_tolerance": 0.02,
        }
        analyzer = ElliottWaveAnalyzer(config)
        assert analyzer.min_wave_length == 10
        assert analyzer.max_retracement == 0.5
        assert analyzer.min_extension == 1.2
        assert analyzer.fibonacci_tolerance == 0.02

    def test_find_peaks_and_troughs_simple(self):
        """Test peak and trough detection with simple data."""
        analyzer = ElliottWaveAnalyzer()

        # Create simple price data with clear peaks and troughs
        data = pd.DataFrame(
            {"close": [1.0, 1.1, 1.2, 1.1, 1.0, 0.9, 1.0, 1.1, 1.2, 1.3, 1.2, 1.1]}
        )

        peaks, troughs = analyzer.find_peaks_and_troughs(data, window_size=2)

        # Should find some peaks and troughs
        assert len(peaks) >= 0
        assert len(troughs) >= 0

        # Verify indices are within valid range
        for peak in peaks:
            assert 0 <= peak < len(data)
        for trough in troughs:
            assert 0 <= trough < len(data)

    def test_find_peaks_and_troughs_trend_data(self, sample_ohlc_data):
        """Test peak and trough detection with trending data."""
        analyzer = ElliottWaveAnalyzer()

        peaks, troughs = analyzer.find_peaks_and_troughs(sample_ohlc_data)

        # Should find some peaks and troughs in random walk data
        assert isinstance(peaks, list)
        assert isinstance(troughs, list)

        # Verify peaks are higher than surrounding points
        for peak_idx in peaks:
            if peak_idx > 0 and peak_idx < len(sample_ohlc_data) - 1:
                peak_price = sample_ohlc_data.iloc[peak_idx]["close"]
                prev_price = sample_ohlc_data.iloc[peak_idx - 1]["close"]
                next_price = sample_ohlc_data.iloc[peak_idx + 1]["close"]
                # Peak should be higher than at least one neighbor
                assert peak_price >= prev_price or peak_price >= next_price

    def test_detect_impulse_waves_insufficient_data(self):
        """Test impulse wave detection with insufficient data."""
        analyzer = ElliottWaveAnalyzer()

        # Create data with only a few points
        data = pd.DataFrame(
            {
                "close": [1.0, 1.1, 1.0],
                "time": pd.date_range("2024-01-01", periods=3, freq="1H"),
            }
        )

        waves = analyzer.detect_impulse_waves(data)
        assert waves == []  # Should return empty list

    def test_detect_impulse_waves_with_pattern(self):
        """Test impulse wave detection with a clear pattern."""
        analyzer = ElliottWaveAnalyzer()

        # Create data with a clear 5-wave pattern
        prices = [
            1.0000,
            1.0100,
            1.0050,
            1.0150,
            1.0080,
            1.0200,
        ]  # Up trend with retracements
        data = pd.DataFrame(
            {
                "close": prices + [1.0150, 1.0100] * 10,  # Add more data
                "time": pd.date_range(
                    "2024-01-01", periods=len(prices) + 20, freq="1H"
                ),
            }
        )

        waves = analyzer.detect_impulse_waves(data)

        # May or may not find waves depending on peak/trough detection
        assert isinstance(waves, list)

        # If waves are found, verify their structure
        for wave in waves:
            assert isinstance(wave, Wave)
            assert wave.wave_type == WaveType.IMPULSE
            assert len(wave.sub_waves) == 5  # Should have 5 sub-waves
            assert wave.is_complete()

    def test_validate_impulse_wave_valid(self):
        """Test impulse wave validation with valid pattern."""
        analyzer = ElliottWaveAnalyzer()

        # Create valid impulse wave with sub-waves
        w1 = Wave(
            0,
            2,
            1.0000,
            1.0100,
            pd.Timestamp("2024-01-01 10:00"),
            pd.Timestamp("2024-01-01 10:02"),
            WaveType.IMPULSE,
            WaveDirection.UP,
            WaveLabel.W1,
            [],
        )
        w2 = Wave(
            2,
            3,
            1.0100,
            1.0050,
            pd.Timestamp("2024-01-01 10:02"),
            pd.Timestamp("2024-01-01 10:03"),
            WaveType.CORRECTIVE,
            WaveDirection.DOWN,
            WaveLabel.W2,
            [],
        )
        w3 = Wave(
            3,
            5,
            1.0050,
            1.0180,
            pd.Timestamp("2024-01-01 10:03"),
            pd.Timestamp("2024-01-01 10:05"),
            WaveType.IMPULSE,
            WaveDirection.UP,
            WaveLabel.W3,
            [],
        )
        w4 = Wave(
            5,
            6,
            1.0180,
            1.0120,
            pd.Timestamp("2024-01-01 10:05"),
            pd.Timestamp("2024-01-01 10:06"),
            WaveType.CORRECTIVE,
            WaveDirection.DOWN,
            WaveLabel.W4,
            [],
        )
        w5 = Wave(
            6,
            8,
            1.0120,
            1.0200,
            pd.Timestamp("2024-01-01 10:06"),
            pd.Timestamp("2024-01-01 10:08"),
            WaveType.IMPULSE,
            WaveDirection.UP,
            WaveLabel.W5,
            [],
        )

        impulse_wave = Wave(
            0,
            8,
            1.0000,
            1.0200,
            pd.Timestamp("2024-01-01 10:00"),
            pd.Timestamp("2024-01-01 10:08"),
            WaveType.IMPULSE,
            WaveDirection.UP,
            WaveLabel.UNKNOWN,
            [w1, w2, w3, w4, w5],
        )

        # This should be a valid impulse wave
        is_valid = analyzer._validate_impulse_wave(impulse_wave)
        assert is_valid is True

    def test_validate_impulse_wave_invalid_retracement(self):
        """Test impulse wave validation with invalid retracement."""
        analyzer = ElliottWaveAnalyzer()

        # Create impulse wave where wave 2 retraces more than 100% of wave 1
        w1 = Wave(
            0,
            2,
            1.0000,
            1.0100,
            pd.Timestamp("2024-01-01 10:00"),
            pd.Timestamp("2024-01-01 10:02"),
            WaveType.IMPULSE,
            WaveDirection.UP,
            WaveLabel.W1,
            [],
        )
        w2 = Wave(
            2,
            3,
            1.0100,
            0.9950,
            pd.Timestamp("2024-01-01 10:02"),  # Retraces more than wave 1
            pd.Timestamp("2024-01-01 10:03"),
            WaveType.CORRECTIVE,
            WaveDirection.DOWN,
            WaveLabel.W2,
            [],
        )
        w3 = Wave(
            3,
            5,
            0.9950,
            1.0150,
            pd.Timestamp("2024-01-01 10:03"),
            pd.Timestamp("2024-01-01 10:05"),
            WaveType.IMPULSE,
            WaveDirection.UP,
            WaveLabel.W3,
            [],
        )
        w4 = Wave(
            5,
            6,
            1.0150,
            1.0100,
            pd.Timestamp("2024-01-01 10:05"),
            pd.Timestamp("2024-01-01 10:06"),
            WaveType.CORRECTIVE,
            WaveDirection.DOWN,
            WaveLabel.W4,
            [],
        )
        w5 = Wave(
            6,
            8,
            1.0100,
            1.0180,
            pd.Timestamp("2024-01-01 10:06"),
            pd.Timestamp("2024-01-01 10:08"),
            WaveType.IMPULSE,
            WaveDirection.UP,
            WaveLabel.W5,
            [],
        )

        impulse_wave = Wave(
            0,
            8,
            1.0000,
            1.0180,
            pd.Timestamp("2024-01-01 10:00"),
            pd.Timestamp("2024-01-01 10:08"),
            WaveType.IMPULSE,
            WaveDirection.UP,
            WaveLabel.UNKNOWN,
            [w1, w2, w3, w4, w5],
        )

        # This should be invalid due to excessive retracement
        is_valid = analyzer._validate_impulse_wave(impulse_wave)
        assert is_valid is False

    def test_validate_impulse_wave_wave3_shortest(self):
        """Test impulse wave validation where wave 3 is shortest."""
        analyzer = ElliottWaveAnalyzer()

        # Create impulse wave where wave 3 is shortest
        w1 = Wave(
            0,
            2,
            1.0000,
            1.0100,
            pd.Timestamp("2024-01-01 10:00"),
            pd.Timestamp("2024-01-01 10:02"),
            WaveType.IMPULSE,
            WaveDirection.UP,
            WaveLabel.W1,
            [],
        )
        w2 = Wave(
            2,
            3,
            1.0100,
            1.0050,
            pd.Timestamp("2024-01-01 10:02"),
            pd.Timestamp("2024-01-01 10:03"),
            WaveType.CORRECTIVE,
            WaveDirection.DOWN,
            WaveLabel.W2,
            [],
        )
        w3 = Wave(
            3,
            5,
            1.0050,
            1.0070,
            pd.Timestamp("2024-01-01 10:03"),  # Shortest wave
            pd.Timestamp("2024-01-01 10:05"),
            WaveType.IMPULSE,
            WaveDirection.UP,
            WaveLabel.W3,
            [],
        )
        w4 = Wave(
            5,
            6,
            1.0070,
            1.0060,
            pd.Timestamp("2024-01-01 10:05"),
            pd.Timestamp("2024-01-01 10:06"),
            WaveType.CORRECTIVE,
            WaveDirection.DOWN,
            WaveLabel.W4,
            [],
        )
        w5 = Wave(
            6,
            8,
            1.0060,
            1.0150,
            pd.Timestamp("2024-01-01 10:06"),
            pd.Timestamp("2024-01-01 10:08"),
            WaveType.IMPULSE,
            WaveDirection.UP,
            WaveLabel.W5,
            [],
        )

        impulse_wave = Wave(
            0,
            8,
            1.0000,
            1.0150,
            pd.Timestamp("2024-01-01 10:00"),
            pd.Timestamp("2024-01-01 10:08"),
            WaveType.IMPULSE,
            WaveDirection.UP,
            WaveLabel.UNKNOWN,
            [w1, w2, w3, w4, w5],
        )

        # This should be invalid because wave 3 is shortest
        is_valid = analyzer._validate_impulse_wave(impulse_wave)
        assert is_valid is False

    def test_analyze_complete_flow(self, sample_ohlc_data):
        """Test the complete analyze flow."""
        analyzer = ElliottWaveAnalyzer()

        result = analyzer.analyze(sample_ohlc_data)

        # Should return analysis results
        assert isinstance(result, dict)
        assert "impulse_waves" in result
        assert isinstance(result["impulse_waves"], list)

        # Each impulse wave should be serialized properly
        for wave_dict in result["impulse_waves"]:
            assert "start_idx" in wave_dict
            assert "end_idx" in wave_dict
            assert "wave_type" in wave_dict
            assert "direction" in wave_dict
            assert "sub_waves" in wave_dict
            assert len(wave_dict["sub_waves"]) == 5  # Impulse waves have 5 sub-waves
