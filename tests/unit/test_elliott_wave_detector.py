"""
Unit tests for Elliott Wave Pattern Detection.

Tests comprehensive Elliott Wave analysis including:
- Impulse wave (5-wave) pattern detection
- Corrective wave (3-wave) pattern detection
- Wave degree identification
- Fibonacci ratio validation
- Wave counting algorithms
- Pattern validation rules
- Multi-timeframe analysis
- Real-time wave updates
- Historical pattern recognition
- Wave projection and targets
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from freezegun import freeze_time

from core.analysis.elliott_wave_detector import (
    ElliottWaveDetector,
    WaveCount,
    WaveDegree,
    WavePattern,
    WaveType,
)


class TestElliottWaveDetector:
    """Test suite for Elliott Wave pattern detection."""

    @pytest.fixture
    def wave_config(self):
        """Configuration for Elliott Wave detector."""
        return {
            "min_wave_size": 50,  # Minimum pips for wave
            "fibonacci_tolerance": 0.05,  # 5% tolerance
            "wave_degrees": ["minute", "minor", "intermediate", "primary", "cycle"],
            "enable_multi_timeframe": True,
            "timeframes": ["M1", "M5", "M15", "H1", "H4", "D1"],
            "pattern_confidence_threshold": 0.75,
            "wave_overlap_rules": True,
            "alternation_principle": True,
            "fibonacci_ratios": {
                "wave_2_retracement": [0.382, 0.5, 0.618],
                "wave_3_extension": [1.618, 2.618, 3.618],
                "wave_4_retracement": [0.236, 0.382, 0.5],
                "wave_5_extension": [0.618, 1.0, 1.618],
            },
        }

    @pytest.fixture
    def sample_price_data(self):
        """Generate sample price data for testing."""
        # Create idealized Elliott Wave pattern with clear pivots
        dates = pd.date_range(start="2025-01-01", periods=100, freq="h")

        # Create clear wave pattern with distinct pivots
        prices = []
        base_price = 1.0500

        # Add some initial flat prices for stability
        for i in range(5):
            prices.append(base_price + np.random.uniform(-0.0001, 0.0001))

        # Wave 1 up - clear uptrend
        wave_1_start = base_price
        wave_1_end = base_price + 0.0200
        for i in range(10):
            progress = i / 9
            prices.append(wave_1_start + (wave_1_end - wave_1_start) * progress)

        # Small consolidation at top
        for i in range(3):
            prices.append(wave_1_end + np.random.uniform(-0.0002, 0.0002))

        # Wave 2 down - 50% retracement
        wave_2_end = wave_1_start + (wave_1_end - wave_1_start) * 0.5
        for i in range(8):
            progress = i / 7
            prices.append(wave_1_end - (wave_1_end - wave_2_end) * progress)

        # Small consolidation at bottom
        for i in range(3):
            prices.append(wave_2_end + np.random.uniform(-0.0002, 0.0002))

        # Wave 3 up - 1.618x wave 1
        wave_3_length = (wave_1_end - wave_1_start) * 1.618
        wave_3_end = wave_2_end + wave_3_length
        for i in range(15):
            progress = i / 14
            prices.append(wave_2_end + wave_3_length * progress)

        # Small consolidation at top
        for i in range(3):
            prices.append(wave_3_end + np.random.uniform(-0.0002, 0.0002))

        # Wave 4 down - 38.2% retracement of wave 3
        wave_4_end = wave_3_end - (wave_3_end - wave_2_end) * 0.382
        for i in range(8):
            progress = i / 7
            prices.append(wave_3_end - (wave_3_end - wave_4_end) * progress)

        # Small consolidation at bottom
        for i in range(3):
            prices.append(wave_4_end + np.random.uniform(-0.0002, 0.0002))

        # Wave 5 up - equal to wave 1
        wave_5_end = wave_4_end + (wave_1_end - wave_1_start)
        for i in range(10):
            progress = i / 9
            prices.append(wave_4_end + (wave_5_end - wave_4_end) * progress)

        # Fill rest with slight downtrend (corrective)
        remaining = 100 - len(prices)
        for i in range(remaining):
            prices.append(wave_5_end - i * 0.0003)

        return pd.DataFrame(
            {
                "timestamp": dates[: len(prices)],
                "open": prices[: len(dates)],
                "high": [p + 0.0002 for p in prices[: len(dates)]],
                "low": [p - 0.0002 for p in prices[: len(dates)]],
                "close": [p + 0.0001 for p in prices[: len(dates)]],
                "volume": np.random.randint(1000, 10000, len(dates)),
            }
        )

    @pytest.fixture
    def elliott_wave_detector(self, wave_config):
        """Create Elliott Wave detector for testing."""
        return ElliottWaveDetector(config=wave_config)

    @pytest.mark.asyncio
    async def test_detects_impulse_wave_pattern(
        self, elliott_wave_detector, sample_price_data
    ):
        """Test detection of 5-wave impulse pattern."""
        result = await elliott_wave_detector.detect_impulse_wave(sample_price_data)

        assert result["pattern_found"] is True
        assert result["wave_count"] == 5
        assert result["pattern_type"] == WaveType.IMPULSE
        assert "waves" in result
        assert len(result["waves"]) == 5
        assert result["confidence"] > 0.75

    @pytest.mark.asyncio
    async def test_detects_corrective_wave_pattern(
        self, elliott_wave_detector, sample_price_data
    ):
        """Test detection of 3-wave corrective pattern."""
        result = await elliott_wave_detector.detect_corrective_wave(sample_price_data)

        assert result["pattern_found"] is True
        assert result["wave_count"] == 3
        assert result["pattern_type"] == WaveType.CORRECTIVE
        assert "waves" in result
        assert result["waves"][0]["label"] == "A"
        assert result["waves"][1]["label"] == "B"
        assert result["waves"][2]["label"] == "C"

    @pytest.mark.asyncio
    async def test_validates_fibonacci_ratios(
        self, elliott_wave_detector, sample_price_data
    ):
        """Test validation of Fibonacci relationships between waves."""
        waves = await elliott_wave_detector.identify_waves(sample_price_data)
        validation = await elliott_wave_detector.validate_fibonacci_ratios(waves)

        assert validation["valid"] is True
        assert "wave_2_retracement" in validation
        assert "wave_3_extension" in validation
        assert "wave_4_retracement" in validation

        # Check specific Fibonacci ratios
        assert 0.35 < validation["wave_2_retracement"] < 0.65  # Near 0.5
        assert 1.5 < validation["wave_3_extension"] < 1.8  # Near 1.618

    @pytest.mark.asyncio
    async def test_identifies_wave_degree(
        self, elliott_wave_detector, sample_price_data
    ):
        """Test identification of wave degree (timeframe)."""
        result = await elliott_wave_detector.identify_wave_degree(sample_price_data)

        assert "degree" in result
        assert result["degree"] in [
            "minute",
            "minor",
            "intermediate",
            "primary",
            "cycle",
        ]
        assert "timeframe" in result
        assert "amplitude" in result
        assert "duration" in result

    @pytest.mark.asyncio
    async def test_applies_elliott_wave_rules(self, elliott_wave_detector):
        """Test application of Elliott Wave rules."""
        waves = [
            {"wave": 1, "start": 1.0500, "end": 1.0700, "type": "impulse"},
            {"wave": 2, "start": 1.0700, "end": 1.0600, "type": "corrective"},
            {"wave": 3, "start": 1.0600, "end": 1.0950, "type": "impulse"},
            {"wave": 4, "start": 1.0950, "end": 1.0850, "type": "corrective"},
            {"wave": 5, "start": 1.0850, "end": 1.1050, "type": "impulse"},
        ]

        rules_check = await elliott_wave_detector.check_elliott_rules(waves)

        assert rules_check["wave_2_not_beyond_wave_1"] is True
        assert rules_check["wave_3_not_shortest"] is True
        assert rules_check["wave_4_not_overlap_wave_1"] is True
        assert rules_check["all_rules_passed"] is True

    @pytest.mark.asyncio
    async def test_handles_wave_alternation(self, elliott_wave_detector):
        """Test alternation principle in corrective waves."""
        waves = [
            {"wave": 2, "pattern": "zigzag", "complexity": "simple"},
            {"wave": 4, "pattern": "flat", "complexity": "complex"},
        ]

        alternation = await elliott_wave_detector.check_alternation(waves)

        assert alternation["alternation_present"] is True
        assert alternation["wave_2_pattern"] != alternation["wave_4_pattern"]

    @pytest.mark.asyncio
    async def test_multi_timeframe_analysis(
        self, elliott_wave_detector, sample_price_data
    ):
        """Test wave detection across multiple timeframes."""
        result = await elliott_wave_detector.analyze_multiple_timeframes(
            sample_price_data, timeframes=["M5", "M15", "H1"]
        )

        assert "M5" in result
        assert "M15" in result
        assert "H1" in result
        assert result["dominant_pattern"] is not None
        assert "confluence_score" in result

    @pytest.mark.asyncio
    async def test_real_time_wave_counting(
        self, elliott_wave_detector, sample_price_data
    ):
        """Test real-time wave counting as new data arrives."""
        # Initial wave count
        initial_count = await elliott_wave_detector.count_waves(sample_price_data[:50])

        # Add new data
        updated_count = await elliott_wave_detector.update_wave_count(
            sample_price_data[:60], initial_count
        )

        assert updated_count["wave_count"] >= initial_count["wave_count"]
        assert "current_wave" in updated_count
        assert "next_expected_wave" in updated_count

    @pytest.mark.asyncio
    async def test_wave_projection_and_targets(self, elliott_wave_detector):
        """Test calculation of wave projections and price targets."""
        current_waves = [
            {"wave": 1, "start": 1.0500, "end": 1.0700},
            {"wave": 2, "start": 1.0700, "end": 1.0600},
            {"wave": 3, "start": 1.0600, "end": 1.0950},
        ]

        projection = await elliott_wave_detector.project_next_wave(current_waves)

        assert "wave_4_targets" in projection
        assert len(projection["wave_4_targets"]) > 0
        assert projection["wave_4_targets"][0] < current_waves[2]["end"]
        assert "wave_5_targets" in projection
        assert "confidence_levels" in projection

    @pytest.mark.asyncio
    async def test_identifies_wave_extensions(self, elliott_wave_detector):
        """Test identification of extended waves."""
        waves = [
            {"wave": 1, "length": 200},
            {"wave": 3, "length": 500},  # Extended wave
            {"wave": 5, "length": 180},
        ]

        extensions = await elliott_wave_detector.identify_extensions(waves)

        assert extensions["has_extension"] is True
        assert extensions["extended_wave"] == 3
        assert extensions["extension_ratio"] > 2.0

    @pytest.mark.asyncio
    async def test_handles_complex_corrections(self, elliott_wave_detector):
        """Test detection of complex corrective patterns."""
        correction_data = {
            "pattern": "WXY",
            "waves": [
                {"label": "W", "type": "zigzag"},
                {"label": "X", "type": "connector"},
                {"label": "Y", "type": "flat"},
            ],
        }

        result = await elliott_wave_detector.identify_complex_correction(
            correction_data
        )

        assert result["pattern_type"] == "complex"
        assert result["structure"] == "WXY"
        assert len(result["components"]) == 3

    @pytest.mark.asyncio
    async def test_wave_invalidation_levels(self, elliott_wave_detector):
        """Test calculation of wave invalidation levels."""
        current_pattern = {
            "type": "impulse",
            "current_wave": 4,
            "waves": [
                {"wave": 1, "start": 1.0500, "end": 1.0700},
                {"wave": 2, "start": 1.0700, "end": 1.0600},
                {"wave": 3, "start": 1.0600, "end": 1.0950},
                {"wave": 4, "start": 1.0950, "end": 1.0850},
            ],
        }

        invalidation = await elliott_wave_detector.calculate_invalidation_levels(
            current_pattern
        )

        assert "wave_4_invalidation" in invalidation
        assert (
            invalidation["wave_4_invalidation"] == 1.0700
        )  # Wave 4 cannot enter wave 1 territory
        assert "pattern_invalidation" in invalidation

    @pytest.mark.asyncio
    async def test_historical_pattern_matching(self, elliott_wave_detector):
        """Test matching current pattern against historical patterns."""
        current_pattern = {
            "type": "impulse",
            "waves": [1, 2, 3, 4],
            "ratios": {"wave_2": 0.5, "wave_3": 1.618},
        }

        historical_matches = await elliott_wave_detector.find_historical_matches(
            current_pattern, min_similarity=0.8
        )

        assert "matches" in historical_matches
        assert "best_match" in historical_matches
        assert "average_outcome" in historical_matches
        assert historical_matches["confidence"] >= 0.0

    @pytest.mark.asyncio
    async def test_wave_channeling(self, elliott_wave_detector):
        """Test creation of trend channels for wave patterns."""
        waves = [
            {"wave": 1, "start": (0, 1.0500), "end": (10, 1.0700)},
            {"wave": 2, "start": (10, 1.0700), "end": (15, 1.0600)},
            {"wave": 3, "start": (15, 1.0600), "end": (30, 1.0950)},
            {"wave": 4, "start": (30, 1.0950), "end": (35, 1.0850)},
        ]

        channel = await elliott_wave_detector.create_wave_channel(waves)

        assert "upper_trendline" in channel
        assert "lower_trendline" in channel
        assert "wave_5_target_zone" in channel
        assert channel["channel_valid"] is True

    @pytest.mark.asyncio
    async def test_sub_wave_analysis(self, elliott_wave_detector):
        """Test analysis of sub-waves within larger waves."""
        wave_3_data = pd.DataFrame(
            {
                "price": [
                    1.0600,
                    1.0650,
                    1.0620,
                    1.0700,
                    1.0680,
                    1.0750,
                    1.0730,
                    1.0800,
                    1.0780,
                    1.0850,
                    1.0950,
                ]
            }
        )

        sub_waves = await elliott_wave_detector.analyze_sub_waves(
            wave_3_data, parent_wave=3
        )

        assert "sub_wave_count" in sub_waves
        assert sub_waves["sub_wave_count"] == 5  # Wave 3 should have 5 sub-waves
        assert "sub_wave_degree" in sub_waves
        assert sub_waves["follows_fractal_nature"] is True

    @pytest.mark.asyncio
    async def test_momentum_divergence_detection(self, elliott_wave_detector):
        """Test detection of momentum divergence at wave endings."""
        wave_data = {
            "prices": [1.0850, 1.0900, 1.0950, 1.1000, 1.1050],
            "momentum": [50, 45, 40, 35, 30],  # Declining momentum
        }

        divergence = await elliott_wave_detector.check_momentum_divergence(wave_data)

        assert divergence["divergence_detected"] is True
        assert divergence["type"] == "bearish"
        assert divergence["wave_ending_signal"] is True

    @pytest.mark.asyncio
    async def test_wave_confluence_analysis(self, elliott_wave_detector):
        """Test confluence of multiple wave counts and patterns."""
        patterns = [
            {"source": "primary_count", "target": 1.1000, "confidence": 0.8},
            {"source": "alternate_count", "target": 1.0980, "confidence": 0.6},
            {"source": "fibonacci_projection", "target": 1.1010, "confidence": 0.75},
        ]

        confluence = await elliott_wave_detector.analyze_confluence(patterns)

        assert "confluence_zone" in confluence
        assert "strength" in confluence
        assert confluence["strength"] > 0.7
        assert "target_range" in confluence

    @pytest.mark.asyncio
    async def test_adaptive_wave_counting(
        self, elliott_wave_detector, sample_price_data
    ):
        """Test adaptive wave counting that adjusts to market conditions."""
        # Test in trending market
        trending_result = await elliott_wave_detector.adaptive_count(
            sample_price_data, market_condition="trending"
        )

        # Test in ranging market
        ranging_data = sample_price_data.copy()
        ranging_data["close"] = ranging_data["close"].apply(
            lambda x: x + np.random.uniform(-0.002, 0.002)
        )

        ranging_result = await elliott_wave_detector.adaptive_count(
            ranging_data, market_condition="ranging"
        )

        assert trending_result["pattern_clarity"] > ranging_result["pattern_clarity"]
        assert "adjusted_parameters" in ranging_result

    @pytest.mark.asyncio
    async def test_generates_wave_alerts(self, elliott_wave_detector):
        """Test generation of alerts for wave completions and opportunities."""
        current_state = {
            "current_wave": 4,
            "completion": 0.85,
            "next_wave_projection": 5,
            "invalidation_level": 1.0700,
        }

        alerts = await elliott_wave_detector.generate_alerts(current_state)

        assert len(alerts) > 0
        assert any(alert["type"] == "wave_completion" for alert in alerts)
        assert any("action" in alert for alert in alerts)
        assert any("risk_level" in alert for alert in alerts)

    @pytest.mark.asyncio
    async def test_pattern_confidence_scoring(self, elliott_wave_detector):
        """Test confidence scoring for detected patterns."""
        pattern = {
            "waves": 5,
            "fibonacci_accuracy": 0.92,
            "rule_violations": 0,
            "alternation_present": True,
            "channel_conformity": 0.88,
        }

        confidence = await elliott_wave_detector.calculate_confidence(pattern)

        assert 0 <= confidence["overall_score"] <= 1
        assert "breakdown" in confidence
        assert "reliability_rating" in confidence
        assert confidence["overall_score"] > 0.8  # High confidence for good pattern
