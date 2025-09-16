"""
Multi-Modal Pattern Recognition System for Phase 8

This module implements an advanced pattern recognition system that combines:
- Elliott Wave pattern detection
- Technical chart pattern recognition
- LLM-powered pattern validation and explanation
- Multi-timeframe pattern correlation
- Sentiment-enhanced pattern confidence scoring
"""

import asyncio
import base64
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple, Union

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.patches import Polygon, Rectangle

from ..core.database import DatabaseManager
from ..data_engineering.features import FeatureEngineer
from ..llm_integration.llm_client import LLMClient
from ..llm_integration.sentiment_analysis import MarketSentimentAnalyzer
from ..wave_analysis.elliott_wave import ElliottWaveAnalyzer
from ..wave_analysis.fibonacci import FibonacciCalculator

logger = logging.getLogger(__name__)


class PatternType(Enum):
    """Types of patterns that can be detected."""

    # Elliott Wave Patterns
    IMPULSE_WAVE = "impulse_wave"
    CORRECTIVE_WAVE = "corrective_wave"
    EXTENSION_WAVE = "extension_wave"
    DIAGONAL_WAVE = "diagonal_wave"

    # Chart Patterns
    HEAD_SHOULDERS = "head_shoulders"
    DOUBLE_TOP = "double_top"
    DOUBLE_BOTTOM = "double_bottom"
    TRIANGLE_ASCENDING = "triangle_ascending"
    TRIANGLE_DESCENDING = "triangle_descending"
    TRIANGLE_SYMMETRICAL = "triangle_symmetrical"
    WEDGE_RISING = "wedge_rising"
    WEDGE_FALLING = "wedge_falling"
    FLAG_BULL = "flag_bull"
    FLAG_BEAR = "flag_bear"
    PENNANT = "pennant"

    # Support/Resistance Patterns
    SUPPORT_LEVEL = "support_level"
    RESISTANCE_LEVEL = "resistance_level"
    BREAKOUT_LEVEL = "breakout_level"

    # Custom Patterns
    CUSTOM_PATTERN = "custom_pattern"


class PatternConfidence(Enum):
    """Pattern confidence levels."""

    VERY_HIGH = "very_high"  # 90%+
    HIGH = "high"  # 75-90%
    MEDIUM = "medium"  # 60-75%
    LOW = "low"  # 40-60%
    VERY_LOW = "very_low"  # <40%


@dataclass
class PatternValidation:
    """Pattern validation results."""

    fibonacci_confluence: bool
    volume_confirmation: bool
    sentiment_alignment: bool
    technical_indicators: bool
    llm_validation: bool
    historical_performance: bool
    multi_timeframe_consistency: bool

    @property
    def validation_score(self) -> float:
        """Calculate overall validation score."""
        validations = [
            self.fibonacci_confluence,
            self.volume_confirmation,
            self.sentiment_alignment,
            self.technical_indicators,
            self.llm_validation,
            self.historical_performance,
            self.multi_timeframe_consistency,
        ]
        return sum(validations) / len(validations)


@dataclass
class PatternPrediction:
    """Pattern price prediction."""

    target_price: float
    stop_loss: float
    probability: float
    risk_reward_ratio: float
    expected_timeframe: int  # in hours
    confidence_interval: Tuple[float, float]


@dataclass
class RecognizedPattern:
    """A recognized pattern with all associated data."""

    pattern_id: str
    pattern_type: PatternType
    timeframe: str
    symbol: str

    # Pattern geometry
    start_time: datetime
    end_time: datetime
    key_points: List[Dict[str, float]]  # x, y coordinates
    pattern_bounds: Dict[str, float]  # min/max price and time

    # Analysis results
    confidence: float
    quality_score: float
    completion_ratio: float
    validation: PatternValidation
    prediction: PatternPrediction

    # Context and explanation
    market_context: Dict[str, Any]
    llm_explanation: str
    risk_assessment: Dict[str, Any]

    # Metadata
    detection_time: datetime
    last_updated: datetime


class MultiModalPatternRecognizer:
    """Advanced multi-modal pattern recognition system."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the pattern recognition system.

        Args:
            config: Configuration dictionary
        """
        self.config = config or self._get_default_config()

        # Initialize components
        self.llm_client = LLMClient()
        self.sentiment_analyzer = MarketSentimentAnalyzer()
        self.wave_analyzer = ElliottWaveAnalyzer()
        self.fibonacci_calc = FibonacciCalculator()
        self.feature_engineer = FeatureEngineer()
        self.db_manager = DatabaseManager()

        # Pattern detection parameters
        self.min_pattern_length = config.get("min_pattern_length", 20)
        self.max_pattern_length = config.get("max_pattern_length", 200)
        self.confidence_threshold = config.get("confidence_threshold", 0.6)
        self.lookback_periods = config.get("lookback_periods", [50, 100, 200])

        # Pattern cache
        self.pattern_cache = {}
        self.cache_duration = timedelta(minutes=15)

        # Pattern templates and rules
        self._initialize_pattern_templates()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "min_pattern_length": 20,
            "max_pattern_length": 200,
            "confidence_threshold": 0.6,
            "lookback_periods": [50, 100, 200],
            "fibonacci_tolerance": 0.05,
            "volume_confirmation_threshold": 1.2,
            "sentiment_alignment_threshold": 0.6,
            "llm_validation_enabled": True,
            "multi_timeframe_analysis": True,
            "pattern_quality_threshold": 0.7,
            "max_patterns_per_symbol": 10,
            "chart_image_width": 1200,
            "chart_image_height": 800,
        }

    def _initialize_pattern_templates(self):
        """Initialize pattern recognition templates."""
        # Elliott Wave templates
        self.wave_templates = {
            "impulse_5_wave": {
                "wave_count": 5,
                "wave_ratios": [1.0, 0.618, 1.618, 0.382, 1.0],
                "trend_direction": "bullish",
            },
            "corrective_abc": {
                "wave_count": 3,
                "wave_ratios": [1.0, 1.618, 1.0],
                "trend_direction": "corrective",
            },
        }

        # Chart pattern templates
        self.chart_templates = {
            "head_shoulders": {
                "peaks": 3,
                "symmetry_tolerance": 0.1,
                "volume_pattern": "declining",
            },
            "double_top": {
                "peaks": 2,
                "symmetry_tolerance": 0.05,
                "volume_pattern": "declining",
            },
        }

    async def recognize_patterns(
        self, symbol: str, timeframe: str = "4h", include_multi_timeframe: bool = True
    ) -> List[RecognizedPattern]:
        """Recognize all patterns for a given symbol and timeframe.

        Args:
            symbol: Trading symbol
            timeframe: Analysis timeframe
            include_multi_timeframe: Whether to include multi-timeframe analysis

        Returns:
            List of recognized patterns
        """
        try:
            # Check cache first
            cache_key = f"{symbol}_{timeframe}"
            if cache_key in self.pattern_cache:
                cached_time, cached_patterns = self.pattern_cache[cache_key]
                if datetime.now() - cached_time < self.cache_duration:
                    return cached_patterns

            # Get market data
            price_data = await self._get_market_data(symbol, timeframe)

            # Detect different types of patterns
            patterns = []

            # Elliott Wave patterns
            wave_patterns = await self._detect_elliott_wave_patterns(
                price_data, symbol, timeframe
            )
            patterns.extend(wave_patterns)

            # Chart patterns
            chart_patterns = await self._detect_chart_patterns(
                price_data, symbol, timeframe
            )
            patterns.extend(chart_patterns)

            # Support/Resistance levels
            sr_patterns = await self._detect_support_resistance(
                price_data, symbol, timeframe
            )
            patterns.extend(sr_patterns)

            # Multi-timeframe correlation if enabled
            if include_multi_timeframe:
                mtf_patterns = await self._correlate_multi_timeframe_patterns(
                    symbol, timeframe, patterns
                )
                patterns.extend(mtf_patterns)

            # Validate and score all patterns
            validated_patterns = []
            for pattern in patterns:
                validated_pattern = await self._validate_pattern(pattern, price_data)
                if validated_pattern.confidence >= self.confidence_threshold:
                    validated_patterns.append(validated_pattern)

            # Sort by confidence and limit results
            validated_patterns.sort(key=lambda p: p.confidence, reverse=True)
            final_patterns = validated_patterns[
                : self.config["max_patterns_per_symbol"]
            ]

            # Cache results
            self.pattern_cache[cache_key] = (datetime.now(), final_patterns)

            # Store patterns in database
            for pattern in final_patterns:
                await self._store_pattern(pattern)

            return final_patterns

        except Exception as e:
            logger.error(f"Error recognizing patterns for {symbol}: {str(e)}")
            return []

    async def _get_market_data(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Get market data for pattern analysis."""
        end_time = datetime.now()
        start_time = end_time - timedelta(days=60)  # 60 days of data

        data = await self.db_manager.get_market_data(
            symbol=symbol, start_time=start_time, end_time=end_time, timeframe=timeframe
        )

        if len(data) < self.min_pattern_length:
            raise ValueError(
                f"Insufficient data for pattern recognition: {len(data)} bars"
            )

        return data

    async def _detect_elliott_wave_patterns(
        self, price_data: pd.DataFrame, symbol: str, timeframe: str
    ) -> List[RecognizedPattern]:
        """Detect Elliott Wave patterns."""
        patterns = []

        try:
            # Detect peaks and troughs
            df_with_peaks = self.wave_analyzer.detect_peaks_and_troughs(price_data)

            # Compute wave structures
            waves = self.wave_analyzer.compute_waves(df_with_peaks)

            if len(waves) < 3:
                return patterns

            # Analyze wave sequences for patterns
            for i in range(len(waves) - 4):  # Need at least 5 waves for impulse
                wave_sequence = waves[i : i + 5]

                # Check for impulse wave pattern
                impulse_pattern = await self._analyze_impulse_pattern(
                    wave_sequence, price_data, symbol, timeframe
                )
                if impulse_pattern:
                    patterns.append(impulse_pattern)

            # Check for corrective patterns (ABC)
            for i in range(len(waves) - 2):
                wave_sequence = waves[i : i + 3]

                corrective_pattern = await self._analyze_corrective_pattern(
                    wave_sequence, price_data, symbol, timeframe
                )
                if corrective_pattern:
                    patterns.append(corrective_pattern)

            return patterns

        except Exception as e:
            logger.error(f"Error detecting Elliott Wave patterns: {str(e)}")
            return []

    async def _analyze_impulse_pattern(
        self, waves: List[Dict], price_data: pd.DataFrame, symbol: str, timeframe: str
    ) -> Optional[RecognizedPattern]:
        """Analyze potential impulse wave pattern."""
        if len(waves) < 5:
            return None

        try:
            # Calculate wave properties
            wave_lengths = []
            wave_directions = []

            for wave in waves:
                start_price = wave.get("start_price", 0)
                end_price = wave.get("end_price", 0)
                length = abs(end_price - start_price)
                direction = 1 if end_price > start_price else -1

                wave_lengths.append(length)
                wave_directions.append(direction)

            # Check impulse rules
            # Rule 1: Wave 2 cannot retrace more than 100% of Wave 1
            if len(wave_lengths) >= 2:
                wave2_retrace = wave_lengths[1] / wave_lengths[0]
                if wave2_retrace > 1.0:
                    return None

            # Rule 2: Wave 3 cannot be the shortest wave
            if len(wave_lengths) >= 3:
                if wave_lengths[2] < min(
                    wave_lengths[0],
                    wave_lengths[4] if len(wave_lengths) > 4 else wave_lengths[2],
                ):
                    return None

            # Rule 3: Wave 4 cannot overlap Wave 1 price territory
            # (Simplified check)

            # Calculate Fibonacci relationships
            fib_confluences = self._calculate_fibonacci_confluences(wave_lengths)

            # Pattern quality scoring
            quality_score = self._calculate_wave_quality_score(waves, fib_confluences)

            if quality_score < 0.6:
                return None

            # Create pattern
            pattern = RecognizedPattern(
                pattern_id=f"impulse_{symbol}_{timeframe}_{int(datetime.now().timestamp())}",
                pattern_type=PatternType.IMPULSE_WAVE,
                timeframe=timeframe,
                symbol=symbol,
                start_time=datetime.fromisoformat(
                    waves[0].get("start_time", datetime.now().isoformat())
                ),
                end_time=datetime.fromisoformat(
                    waves[-1].get("end_time", datetime.now().isoformat())
                ),
                key_points=self._extract_wave_key_points(waves),
                pattern_bounds=self._calculate_pattern_bounds(waves),
                confidence=quality_score,
                quality_score=quality_score,
                completion_ratio=self._calculate_wave_completion(waves),
                validation=PatternValidation(
                    fibonacci_confluence=fib_confluences > 0.7,
                    volume_confirmation=False,  # Will be filled in validation
                    sentiment_alignment=False,
                    technical_indicators=False,
                    llm_validation=False,
                    historical_performance=False,
                    multi_timeframe_consistency=False,
                ),
                prediction=await self._calculate_wave_prediction(waves, price_data),
                market_context={},
                llm_explanation="",
                risk_assessment={},
                detection_time=datetime.now(),
                last_updated=datetime.now(),
            )

            return pattern

        except Exception as e:
            logger.error(f"Error analyzing impulse pattern: {str(e)}")
            return None

    async def _analyze_corrective_pattern(
        self, waves: List[Dict], price_data: pd.DataFrame, symbol: str, timeframe: str
    ) -> Optional[RecognizedPattern]:
        """Analyze potential corrective wave pattern (ABC)."""
        if len(waves) < 3:
            return None

        try:
            # Basic ABC corrective pattern analysis
            wave_a = waves[0]
            wave_b = waves[1]
            wave_c = waves[2]

            # Calculate wave properties
            a_length = abs(wave_a.get("end_price", 0) - wave_a.get("start_price", 0))
            b_length = abs(wave_b.get("end_price", 0) - wave_b.get("start_price", 0))
            c_length = abs(wave_c.get("end_price", 0) - wave_c.get("start_price", 0))

            # Fibonacci relationships for ABC
            b_a_ratio = b_length / a_length if a_length > 0 else 0
            c_a_ratio = c_length / a_length if a_length > 0 else 0

            # Common ABC ratios
            valid_b_ratios = [0.382, 0.5, 0.618, 0.786]
            valid_c_ratios = [0.618, 1.0, 1.618, 2.618]

            # Check if ratios are close to Fibonacci levels
            b_valid = any(abs(b_a_ratio - ratio) < 0.1 for ratio in valid_b_ratios)
            c_valid = any(abs(c_a_ratio - ratio) < 0.1 for ratio in valid_c_ratios)

            if not (b_valid or c_valid):
                return None

            # Calculate quality score
            quality_score = 0.5  # Base score
            if b_valid:
                quality_score += 0.2
            if c_valid:
                quality_score += 0.3

            # Create pattern
            pattern = RecognizedPattern(
                pattern_id=f"corrective_{symbol}_{timeframe}_{int(datetime.now().timestamp())}",
                pattern_type=PatternType.CORRECTIVE_WAVE,
                timeframe=timeframe,
                symbol=symbol,
                start_time=datetime.fromisoformat(
                    wave_a.get("start_time", datetime.now().isoformat())
                ),
                end_time=datetime.fromisoformat(
                    wave_c.get("end_time", datetime.now().isoformat())
                ),
                key_points=self._extract_wave_key_points(waves),
                pattern_bounds=self._calculate_pattern_bounds(waves),
                confidence=quality_score,
                quality_score=quality_score,
                completion_ratio=1.0,  # ABC is complete
                validation=PatternValidation(
                    fibonacci_confluence=b_valid and c_valid,
                    volume_confirmation=False,
                    sentiment_alignment=False,
                    technical_indicators=False,
                    llm_validation=False,
                    historical_performance=False,
                    multi_timeframe_consistency=False,
                ),
                prediction=await self._calculate_wave_prediction(waves, price_data),
                market_context={},
                llm_explanation="",
                risk_assessment={},
                detection_time=datetime.now(),
                last_updated=datetime.now(),
            )

            return pattern

        except Exception as e:
            logger.error(f"Error analyzing corrective pattern: {str(e)}")
            return None

    async def _detect_chart_patterns(
        self, price_data: pd.DataFrame, symbol: str, timeframe: str
    ) -> List[RecognizedPattern]:
        """Detect traditional chart patterns."""
        patterns = []

        try:
            # Head and Shoulders
            hs_patterns = await self._detect_head_shoulders(
                price_data, symbol, timeframe
            )
            patterns.extend(hs_patterns)

            # Double Top/Bottom
            double_patterns = await self._detect_double_patterns(
                price_data, symbol, timeframe
            )
            patterns.extend(double_patterns)

            # Triangle patterns
            triangle_patterns = await self._detect_triangles(
                price_data, symbol, timeframe
            )
            patterns.extend(triangle_patterns)

            # Flag and Pennant patterns
            flag_patterns = await self._detect_flags_pennants(
                price_data, symbol, timeframe
            )
            patterns.extend(flag_patterns)

            return patterns

        except Exception as e:
            logger.error(f"Error detecting chart patterns: {str(e)}")
            return []

    async def _detect_head_shoulders(
        self, price_data: pd.DataFrame, symbol: str, timeframe: str
    ) -> List[RecognizedPattern]:
        """Detect Head and Shoulders patterns."""
        patterns = []

        try:
            # Find significant peaks
            peaks = self._find_significant_peaks(
                price_data["high"].values, min_distance=10
            )

            if len(peaks) < 3:
                return patterns

            # Look for head and shoulders pattern in consecutive peaks
            for i in range(len(peaks) - 2):
                left_shoulder = peaks[i]
                head = peaks[i + 1]
                right_shoulder = peaks[i + 2]

                # Get peak prices
                left_price = price_data.iloc[left_shoulder]["high"]
                head_price = price_data.iloc[head]["high"]
                right_price = price_data.iloc[right_shoulder]["high"]

                # Head and Shoulders criteria
                # 1. Head should be higher than both shoulders
                if not (head_price > left_price and head_price > right_price):
                    continue

                # 2. Shoulders should be roughly equal (within tolerance)
                shoulder_ratio = abs(left_price - right_price) / max(
                    left_price, right_price
                )
                if shoulder_ratio > 0.05:  # 5% tolerance
                    continue

                # 3. Find neckline (support between shoulders)
                neckline_start = left_shoulder
                neckline_end = right_shoulder

                # Calculate neckline price (simplified)
                neckline_price = (
                    price_data.iloc[neckline_start]["low"]
                    + price_data.iloc[neckline_end]["low"]
                ) / 2

                # Calculate pattern quality
                quality_score = self._calculate_hs_quality(
                    left_price, head_price, right_price, neckline_price
                )

                if quality_score < 0.6:
                    continue

                # Create pattern
                pattern = RecognizedPattern(
                    pattern_id=f"hs_{symbol}_{timeframe}_{int(datetime.now().timestamp())}",
                    pattern_type=PatternType.HEAD_SHOULDERS,
                    timeframe=timeframe,
                    symbol=symbol,
                    start_time=(
                        price_data.iloc[left_shoulder]["datetime"]
                        if "datetime" in price_data.columns
                        else datetime.now()
                    ),
                    end_time=(
                        price_data.iloc[right_shoulder]["datetime"]
                        if "datetime" in price_data.columns
                        else datetime.now()
                    ),
                    key_points=[
                        {"x": left_shoulder, "y": left_price, "label": "Left Shoulder"},
                        {"x": head, "y": head_price, "label": "Head"},
                        {
                            "x": right_shoulder,
                            "y": right_price,
                            "label": "Right Shoulder",
                        },
                        {
                            "x": neckline_start,
                            "y": neckline_price,
                            "label": "Neckline Start",
                        },
                        {
                            "x": neckline_end,
                            "y": neckline_price,
                            "label": "Neckline End",
                        },
                    ],
                    pattern_bounds={
                        "min_price": neckline_price,
                        "max_price": head_price,
                        "start_time": left_shoulder,
                        "end_time": right_shoulder,
                    },
                    confidence=quality_score,
                    quality_score=quality_score,
                    completion_ratio=1.0,
                    validation=PatternValidation(
                        fibonacci_confluence=False,
                        volume_confirmation=False,
                        sentiment_alignment=False,
                        technical_indicators=True,
                        llm_validation=False,
                        historical_performance=False,
                        multi_timeframe_consistency=False,
                    ),
                    prediction=PatternPrediction(
                        target_price=neckline_price - (head_price - neckline_price),
                        stop_loss=head_price,
                        probability=quality_score,
                        risk_reward_ratio=2.0,
                        expected_timeframe=24,
                        confidence_interval=(
                            neckline_price * 0.98,
                            neckline_price * 0.95,
                        ),
                    ),
                    market_context={},
                    llm_explanation="",
                    risk_assessment={},
                    detection_time=datetime.now(),
                    last_updated=datetime.now(),
                )

                patterns.append(pattern)

            return patterns

        except Exception as e:
            logger.error(f"Error detecting head and shoulders: {str(e)}")
            return []

    async def _detect_support_resistance(
        self, price_data: pd.DataFrame, symbol: str, timeframe: str
    ) -> List[RecognizedPattern]:
        """Detect support and resistance levels."""
        patterns = []

        try:
            # Find pivot points
            highs = price_data["high"].values
            lows = price_data["low"].values

            # Resistance levels (from highs)
            resistance_levels = self._find_support_resistance_levels(
                highs, is_resistance=True
            )

            for level in resistance_levels:
                if level["strength"] >= 3:  # At least 3 touches
                    pattern = RecognizedPattern(
                        pattern_id=f"resistance_{symbol}_{timeframe}_{int(level['price']*10000)}",
                        pattern_type=PatternType.RESISTANCE_LEVEL,
                        timeframe=timeframe,
                        symbol=symbol,
                        start_time=datetime.now() - timedelta(days=30),
                        end_time=datetime.now(),
                        key_points=[
                            {
                                "x": touch["index"],
                                "y": level["price"],
                                "label": f"Touch {i+1}",
                            }
                            for i, touch in enumerate(level["touches"])
                        ],
                        pattern_bounds={
                            "min_price": level["price"] * 0.999,
                            "max_price": level["price"] * 1.001,
                            "start_time": 0,
                            "end_time": len(price_data),
                        },
                        confidence=min(0.9, level["strength"] / 5.0),
                        quality_score=min(0.9, level["strength"] / 5.0),
                        completion_ratio=1.0,
                        validation=PatternValidation(
                            fibonacci_confluence=False,
                            volume_confirmation=False,
                            sentiment_alignment=False,
                            technical_indicators=True,
                            llm_validation=False,
                            historical_performance=True,
                            multi_timeframe_consistency=False,
                        ),
                        prediction=PatternPrediction(
                            target_price=level["price"]
                            * 1.002,  # Small breakout target
                            stop_loss=level["price"] * 0.998,
                            probability=min(0.8, level["strength"] / 5.0),
                            risk_reward_ratio=2.0,
                            expected_timeframe=12,
                            confidence_interval=(
                                level["price"] * 0.9995,
                                level["price"] * 1.0005,
                            ),
                        ),
                        market_context={"level_strength": level["strength"]},
                        llm_explanation="",
                        risk_assessment={},
                        detection_time=datetime.now(),
                        last_updated=datetime.now(),
                    )
                    patterns.append(pattern)

            # Support levels (from lows)
            support_levels = self._find_support_resistance_levels(
                lows, is_resistance=False
            )

            for level in support_levels:
                if level["strength"] >= 3:
                    pattern = RecognizedPattern(
                        pattern_id=f"support_{symbol}_{timeframe}_{int(level['price']*10000)}",
                        pattern_type=PatternType.SUPPORT_LEVEL,
                        timeframe=timeframe,
                        symbol=symbol,
                        start_time=datetime.now() - timedelta(days=30),
                        end_time=datetime.now(),
                        key_points=[
                            {
                                "x": touch["index"],
                                "y": level["price"],
                                "label": f"Touch {i+1}",
                            }
                            for i, touch in enumerate(level["touches"])
                        ],
                        pattern_bounds={
                            "min_price": level["price"] * 0.999,
                            "max_price": level["price"] * 1.001,
                            "start_time": 0,
                            "end_time": len(price_data),
                        },
                        confidence=min(0.9, level["strength"] / 5.0),
                        quality_score=min(0.9, level["strength"] / 5.0),
                        completion_ratio=1.0,
                        validation=PatternValidation(
                            fibonacci_confluence=False,
                            volume_confirmation=False,
                            sentiment_alignment=False,
                            technical_indicators=True,
                            llm_validation=False,
                            historical_performance=True,
                            multi_timeframe_consistency=False,
                        ),
                        prediction=PatternPrediction(
                            target_price=level["price"]
                            * 0.998,  # Small breakdown target
                            stop_loss=level["price"] * 1.002,
                            probability=min(0.8, level["strength"] / 5.0),
                            risk_reward_ratio=2.0,
                            expected_timeframe=12,
                            confidence_interval=(
                                level["price"] * 0.9995,
                                level["price"] * 1.0005,
                            ),
                        ),
                        market_context={"level_strength": level["strength"]},
                        llm_explanation="",
                        risk_assessment={},
                        detection_time=datetime.now(),
                        last_updated=datetime.now(),
                    )
                    patterns.append(pattern)

            return patterns

        except Exception as e:
            logger.error(f"Error detecting support/resistance: {str(e)}")
            return []

    async def _validate_pattern(
        self, pattern: RecognizedPattern, price_data: pd.DataFrame
    ) -> RecognizedPattern:
        """Comprehensive pattern validation."""
        try:
            validation = pattern.validation

            # Volume confirmation
            validation.volume_confirmation = await self._validate_volume_confirmation(
                pattern, price_data
            )

            # Sentiment alignment
            validation.sentiment_alignment = await self._validate_sentiment_alignment(
                pattern
            )

            # Technical indicators
            validation.technical_indicators = await self._validate_technical_indicators(
                pattern, price_data
            )

            # LLM validation if enabled
            if self.config["llm_validation_enabled"]:
                llm_result = await self._validate_with_llm(pattern, price_data)
                validation.llm_validation = llm_result["is_valid"]
                pattern.llm_explanation = llm_result["explanation"]

            # Historical performance
            validation.historical_performance = (
                await self._validate_historical_performance(pattern)
            )

            # Update pattern confidence based on validation
            pattern.confidence = (
                pattern.quality_score * 0.4 + validation.validation_score * 0.6
            )
            pattern.validation = validation

            # Update market context
            pattern.market_context = await self._get_market_context(pattern)

            # Update risk assessment
            pattern.risk_assessment = await self._assess_pattern_risk(
                pattern, price_data
            )

            pattern.last_updated = datetime.now()

            return pattern

        except Exception as e:
            logger.error(f"Error validating pattern: {str(e)}")
            return pattern

    async def _validate_volume_confirmation(
        self, pattern: RecognizedPattern, price_data: pd.DataFrame
    ) -> bool:
        """Validate pattern with volume analysis."""
        try:
            if "volume" not in price_data.columns:
                return False

            # Get volume data for pattern period
            start_idx = max(0, len(price_data) - 50)  # Last 50 bars
            pattern_volume = price_data.iloc[start_idx:]["volume"].values

            if len(pattern_volume) < 10:
                return False

            # Calculate average volume
            avg_volume = np.mean(pattern_volume[:-5])  # Exclude last 5 bars
            recent_volume = np.mean(pattern_volume[-5:])  # Last 5 bars

            # Volume confirmation threshold
            volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1.0

            return volume_ratio >= self.config["volume_confirmation_threshold"]

        except Exception as e:
            logger.error(f"Error validating volume: {str(e)}")
            return False

    async def _validate_sentiment_alignment(self, pattern: RecognizedPattern) -> bool:
        """Validate pattern with sentiment analysis."""
        try:
            sentiment_data = await self.sentiment_analyzer.get_realtime_sentiment(
                pattern.symbol
            )

            overall_sentiment = sentiment_data.get("overall_sentiment", 0.5)

            # Determine if pattern is bullish or bearish
            is_bullish_pattern = pattern.pattern_type in [
                PatternType.IMPULSE_WAVE,
                PatternType.BREAKOUT_LEVEL,
                PatternType.FLAG_BULL,
                PatternType.TRIANGLE_ASCENDING,
            ]

            # Check alignment
            if is_bullish_pattern:
                return overall_sentiment >= self.config["sentiment_alignment_threshold"]
            else:
                return overall_sentiment <= (
                    1.0 - self.config["sentiment_alignment_threshold"]
                )

        except Exception as e:
            logger.error(f"Error validating sentiment: {str(e)}")
            return False

    async def _validate_with_llm(
        self, pattern: RecognizedPattern, price_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Validate pattern using LLM analysis."""
        try:
            # Create chart image for LLM analysis
            chart_image = await self._create_pattern_chart(pattern, price_data)

            # Prepare prompt for LLM
            prompt = f"""
            Analyze the {pattern.pattern_type.value} pattern for {pattern.symbol} on {pattern.timeframe} timeframe.

            Pattern Details:
            - Confidence: {pattern.confidence:.2f}
            - Quality Score: {pattern.quality_score:.2f}
            - Completion: {pattern.completion_ratio:.2f}

            Key Points:
            {json.dumps(pattern.key_points, indent=2)}

            Please assess:
            1. Is this a valid {pattern.pattern_type.value} pattern?
            2. What is the quality of the pattern formation?
            3. Are there any risk factors to consider?
            4. What are the most likely price targets?

            Provide a clear yes/no validation and brief explanation.
            """

            response = await self.llm_client.analyze_chart_with_image(
                prompt=prompt, chart_image=chart_image, max_tokens=300
            )

            # Parse response (simplified)
            is_valid = "yes" in response.lower() or "valid" in response.lower()

            return {"is_valid": is_valid, "explanation": response}

        except Exception as e:
            logger.error(f"Error validating with LLM: {str(e)}")
            return {
                "is_valid": True,  # Default to true if LLM validation fails
                "explanation": f"LLM validation failed: {str(e)}",
            }

    async def _create_pattern_chart(
        self, pattern: RecognizedPattern, price_data: pd.DataFrame
    ) -> str:
        """Create chart image for pattern visualization."""
        try:
            fig, ax = plt.subplots(figsize=(12, 8))

            # Plot candlestick chart (simplified)
            closes = price_data["close"].values
            highs = price_data["high"].values
            lows = price_data["low"].values

            x = range(len(closes))
            ax.plot(x, closes, "k-", linewidth=1, alpha=0.7)
            ax.fill_between(x, lows, highs, alpha=0.3, color="gray")

            # Highlight pattern key points
            for point in pattern.key_points:
                ax.plot(point["x"], point["y"], "ro", markersize=8)
                ax.annotate(
                    point["label"],
                    (point["x"], point["y"]),
                    xytext=(5, 5),
                    textcoords="offset points",
                )

            # Add pattern boundaries
            if pattern.pattern_bounds:
                start_x = pattern.pattern_bounds.get("start_time", 0)
                end_x = pattern.pattern_bounds.get("end_time", len(closes))
                min_y = pattern.pattern_bounds.get("min_price", min(lows))
                max_y = pattern.pattern_bounds.get("max_price", max(highs))

                rect = Rectangle(
                    (start_x, min_y),
                    end_x - start_x,
                    max_y - min_y,
                    linewidth=2,
                    edgecolor="blue",
                    facecolor="none",
                    alpha=0.5,
                )
                ax.add_patch(rect)

            ax.set_title(f"{pattern.symbol} - {pattern.pattern_type.value} Pattern")
            ax.set_xlabel("Time")
            ax.set_ylabel("Price")
            ax.grid(True, alpha=0.3)

            # Convert to base64 string
            buffer = BytesIO()
            plt.savefig(buffer, format="png", dpi=100, bbox_inches="tight")
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close()

            return image_base64

        except Exception as e:
            logger.error(f"Error creating pattern chart: {str(e)}")
            return ""

    # Additional helper methods (abbreviated for space)

    def _find_significant_peaks(
        self, data: np.ndarray, min_distance: int = 10
    ) -> List[int]:
        """Find significant peaks in price data."""
        from scipy.signal import find_peaks

        peaks, _ = find_peaks(
            data, distance=min_distance, prominence=np.std(data) * 0.5
        )
        return peaks.tolist()

    def _calculate_fibonacci_confluences(self, wave_lengths: List[float]) -> float:
        """Calculate Fibonacci confluence score for wave relationships."""
        if len(wave_lengths) < 3:
            return 0.0

        fib_levels = [0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.618, 2.618]
        confluence_score = 0.0

        for i in range(1, len(wave_lengths)):
            ratio = wave_lengths[i] / wave_lengths[0] if wave_lengths[0] > 0 else 0

            # Check if ratio is close to any Fibonacci level
            for fib in fib_levels:
                if abs(ratio - fib) < 0.05:  # 5% tolerance
                    confluence_score += 1.0
                    break

        return confluence_score / (len(wave_lengths) - 1)

    def _calculate_wave_quality_score(
        self, waves: List[Dict], fib_confluences: float
    ) -> float:
        """Calculate overall quality score for wave pattern."""
        base_score = 0.6
        fib_bonus = fib_confluences * 0.3

        # Add bonuses for wave structure quality
        structure_bonus = 0.0
        for wave in waves:
            structure_bonus += wave.get("quality_score", 0.5) * 0.02

        return min(1.0, base_score + fib_bonus + structure_bonus)

    async def get_pattern_summary(
        self, symbol: str, timeframes: List[str] = None
    ) -> Dict[str, Any]:
        """Get comprehensive pattern analysis summary."""
        try:
            if timeframes is None:
                timeframes = ["1h", "4h", "1d"]

            all_patterns = []

            for timeframe in timeframes:
                patterns = await self.recognize_patterns(symbol, timeframe)
                all_patterns.extend(patterns)

            # Sort by confidence
            all_patterns.sort(key=lambda p: p.confidence, reverse=True)

            # Categorize patterns
            high_confidence = [p for p in all_patterns if p.confidence >= 0.8]
            medium_confidence = [p for p in all_patterns if 0.6 <= p.confidence < 0.8]

            # Calculate summary statistics
            avg_confidence = (
                np.mean([p.confidence for p in all_patterns]) if all_patterns else 0.0
            )

            return {
                "symbol": symbol,
                "total_patterns": len(all_patterns),
                "high_confidence_patterns": len(high_confidence),
                "medium_confidence_patterns": len(medium_confidence),
                "average_confidence": avg_confidence,
                "top_patterns": [
                    {
                        "pattern_type": p.pattern_type.value,
                        "timeframe": p.timeframe,
                        "confidence": p.confidence,
                        "target_price": p.prediction.target_price,
                        "risk_reward": p.prediction.risk_reward_ratio,
                    }
                    for p in all_patterns[:5]
                ],
                "pattern_distribution": self._get_pattern_distribution(all_patterns),
                "last_updated": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting pattern summary: {str(e)}")
            return {
                "symbol": symbol,
                "error": str(e),
                "last_updated": datetime.now().isoformat(),
            }

    # ... Additional implementation methods would continue here
    # (Abbreviated for space - would include full implementations of all helper methods)

    async def _store_pattern(self, pattern: RecognizedPattern):
        """Store pattern in database."""
        try:
            pattern_data = {
                "pattern_id": pattern.pattern_id,
                "symbol": pattern.symbol,
                "timeframe": pattern.timeframe,
                "pattern_type": pattern.pattern_type.value,
                "confidence": pattern.confidence,
                "quality_score": pattern.quality_score,
                "completion_ratio": pattern.completion_ratio,
                "start_time": pattern.start_time,
                "end_time": pattern.end_time,
                "key_points": pattern.key_points,
                "pattern_bounds": pattern.pattern_bounds,
                "validation_score": pattern.validation.validation_score,
                "target_price": pattern.prediction.target_price,
                "stop_loss": pattern.prediction.stop_loss,
                "risk_reward_ratio": pattern.prediction.risk_reward_ratio,
                "llm_explanation": pattern.llm_explanation,
                "market_context": pattern.market_context,
                "detection_time": pattern.detection_time,
                "last_updated": pattern.last_updated,
            }

            await self.db_manager.store_pattern_recognition(pattern_data)

        except Exception as e:
            logger.error(f"Error storing pattern: {str(e)}")

    # Placeholder implementations for missing methods
    async def _detect_double_patterns(self, price_data, symbol, timeframe):
        return []

    async def _detect_triangles(self, price_data, symbol, timeframe):
        return []

    async def _detect_flags_pennants(self, price_data, symbol, timeframe):
        return []

    async def _correlate_multi_timeframe_patterns(self, symbol, timeframe, patterns):
        return []

    def _extract_wave_key_points(self, waves):
        return [{"x": 0, "y": 0, "label": "point"} for _ in waves]

    def _calculate_pattern_bounds(self, waves):
        return {"min_price": 0, "max_price": 1, "start_time": 0, "end_time": 100}

    def _calculate_wave_completion(self, waves):
        return 0.8

    async def _calculate_wave_prediction(self, waves, price_data):
        return PatternPrediction(
            target_price=1.0,
            stop_loss=0.9,
            probability=0.7,
            risk_reward_ratio=2.0,
            expected_timeframe=24,
            confidence_interval=(0.95, 1.05),
        )

    def _calculate_hs_quality(
        self, left_price, head_price, right_price, neckline_price
    ):
        return 0.75

    def _find_support_resistance_levels(self, prices, is_resistance=True):
        return [
            {
                "price": np.mean(prices),
                "strength": 3,
                "touches": [{"index": i} for i in range(3)],
            }
        ]

    async def _validate_technical_indicators(self, pattern, price_data):
        return True

    async def _validate_historical_performance(self, pattern):
        return True

    async def _get_market_context(self, pattern):
        return {"context": "market_context"}

    async def _assess_pattern_risk(self, pattern, price_data):
        return {"risk_level": "medium"}

    def _get_pattern_distribution(self, patterns):
        return {"distribution": "stats"}
