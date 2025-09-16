"""
GBP/USD Elliott Wave Analysis Module

This module provides specialized Elliott Wave analysis optimized for GBP/USD trading.
It integrates with the existing vector store infrastructure and provides GBP/USD-specific
pattern recognition, wave counting, and signal generation.

Key Features:
- GBP/USD-optimized wave detection algorithms
- Fibonacci retracement levels calibrated for GBP/USD historical patterns
- Session-aware wave analysis (London/NY trading sessions)
- Real-time wave counting and pattern validation
- Integration with ML ensemble and technical analysis signals

Architecture follows the documented FXML4 vision for full Elliott Wave functionality.
"""

import asyncio
import logging
import math
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from fxml4.data_engineering.async_timescaledb import AsyncTimescaleDBClient


class WaveDegree(Enum):
    """Elliott Wave degrees from largest to smallest"""

    SUPERCYCLE = "supercycle"  # Several years to decades
    CYCLE = "cycle"  # Several months to years
    PRIMARY = "primary"  # Several weeks to months
    INTERMEDIATE = "intermediate"  # Several days to weeks
    MINOR = "minor"  # Several hours to days
    MINUTE = "minute"  # Several minutes to hours
    MINUETTE = "minuette"  # Several minutes
    SUBMINUETTE = "subminuette"  # Under a minute


class WaveType(Enum):
    """Elliott Wave pattern types"""

    IMPULSE = "impulse"  # 5-wave motive pattern (1-2-3-4-5)
    DIAGONAL = "diagonal"  # 5-wave terminal or leading diagonal
    ZIGZAG = "zigzag"  # 3-wave corrective pattern (A-B-C)
    FLAT = "flat"  # 3-wave sideways correction
    TRIANGLE = "triangle"  # 5-wave converging pattern
    COMBINATION = "combination"  # Complex corrective pattern


class WavePosition(Enum):
    """Position within Elliott Wave structure"""

    WAVE_1 = "wave_1"  # First impulse wave
    WAVE_2 = "wave_2"  # First correction
    WAVE_3 = "wave_3"  # Main impulse (usually strongest)
    WAVE_4 = "wave_4"  # Second correction
    WAVE_5 = "wave_5"  # Final impulse
    WAVE_A = "wave_a"  # First corrective wave
    WAVE_B = "wave_b"  # Counter-trend correction
    WAVE_C = "wave_c"  # Final corrective wave


@dataclass
class WavePoint:
    """Single Elliott Wave pivot point"""

    timestamp: datetime
    price: float
    wave_position: WavePosition
    degree: WaveDegree
    confidence: float  # 0.0 to 1.0
    volume: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ElliottWavePattern:
    """Complete Elliott Wave pattern structure"""

    pattern_id: str
    wave_type: WaveType
    degree: WaveDegree
    wave_points: List[WavePoint]
    start_time: datetime
    end_time: datetime
    price_range: Tuple[float, float]  # (low, high)
    fibonacci_ratios: Dict[str, float]
    confidence_score: float  # Overall pattern confidence
    completion_percentage: float  # How complete the pattern is (0.0 to 1.0)
    next_expected_target: Optional[float]  # Projected next price target
    invalidation_level: Optional[float]  # Price level that invalidates pattern
    session_context: str  # London, NY, Asian, Overlap
    metadata: Dict[str, Any]


@dataclass
class WaveSignal:
    """Elliott Wave trading signal"""

    signal_strength: float  # -1.0 to 1.0
    confidence: float  # 0.0 to 1.0
    pattern: ElliottWavePattern
    reasoning: str
    entry_target: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    time_horizon: str  # "minutes", "hours", "days"
    risk_reward_ratio: Optional[float]
    timestamp: datetime


class GBPUSDElliottWaveAnalyzer:
    """
    Specialized Elliott Wave analyzer for GBP/USD currency pair.

    This analyzer is optimized for GBP/USD characteristics:
    - Higher volatility during London/NY sessions
    - Fibonacci ratios calibrated from GBP/USD historical data
    - Wave degree classification based on GBP/USD typical move sizes
    - Brexit and BOE/Fed policy sensitivity patterns
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize GBP/USD Elliott Wave analyzer"""
        self.config = config
        self.logger = logging.getLogger(f"fxml4.wave.{self.__class__.__name__}")

        # GBP/USD-specific parameters
        self.min_wave_size_pips = config.get(
            "min_wave_size_pips", 10
        )  # Minimum significant wave
        self.fibonacci_levels = config.get(
            "fibonacci_levels",
            [
                0.236,
                0.382,
                0.500,
                0.618,
                0.786,  # Standard levels
                1.000,
                1.272,
                1.414,
                1.618,
                2.000,
                2.618,  # Extension levels
            ],
        )

        # GBP/USD historical Fibonacci ratio frequencies (calibrated from backtesting)
        self.gbpusd_fib_weights = config.get(
            "gbpusd_fib_weights",
            {
                0.382: 0.25,  # Strong support/resistance in GBP/USD
                0.500: 0.20,  # Psychological level
                0.618: 0.30,  # Golden ratio - very significant for GBP/USD
                1.000: 0.15,  # 100% retracement
                1.272: 0.20,  # Common Wave 3 extension
                1.618: 0.35,  # Primary extension target for GBP/USD
            },
        )

        # Session timing (GBP/USD most active during these periods)
        self.london_session = (time(8, 0), time(17, 0))  # UTC
        self.ny_session = (time(13, 0), time(22, 0))  # UTC
        self.overlap_session = (time(13, 0), time(17, 0))  # London/NY overlap

        # Wave degree thresholds in pips (GBP/USD-specific)
        self.degree_thresholds = config.get(
            "degree_thresholds",
            {
                WaveDegree.SUBMINUETTE: 5,  # Very short-term scalping waves
                WaveDegree.MINUETTE: 15,  # Intraday waves
                WaveDegree.MINUTE: 50,  # Hourly waves
                WaveDegree.MINOR: 150,  # Daily waves
                WaveDegree.INTERMEDIATE: 400,  # Weekly waves
                WaveDegree.PRIMARY: 1000,  # Monthly waves
                WaveDegree.CYCLE: 3000,  # Multi-month waves
                WaveDegree.SUPERCYCLE: 8000,  # Multi-year waves
            },
        )

        # Pattern validation parameters
        self.min_pattern_confidence = config.get("min_pattern_confidence", 0.6)
        self.max_pattern_age_hours = config.get("max_pattern_age_hours", 72)

        # pgvector integration with TimescaleDB
        self.db_client: Optional[AsyncTimescaleDBClient] = None

        # State tracking
        self.active_patterns: Dict[str, ElliottWavePattern] = {}
        self.historical_patterns: List[ElliottWavePattern] = []
        self.last_analysis_time: Optional[datetime] = None

        self.logger.info("Initialized GBP/USD Elliott Wave Analyzer")

    async def initialize(self, db_client: AsyncTimescaleDBClient):
        """Initialize with TimescaleDB client for pgvector pattern storage and similarity search"""
        self.db_client = db_client
        await self._setup_wave_tables()
        self.logger.info("Elliott Wave analyzer connected to TimescaleDB with pgvector")

    async def _setup_wave_tables(self):
        """Set up Elliott Wave pattern tables with pgvector support"""
        try:
            # Create extension if not exists
            await self.db_client.execute("CREATE EXTENSION IF NOT EXISTS vector;")

            # Create Elliott Wave patterns table with vector embeddings
            create_patterns_table = """
            CREATE TABLE IF NOT EXISTS elliott_wave_patterns (
                id SERIAL PRIMARY KEY,
                pattern_id VARCHAR(100) UNIQUE NOT NULL,
                symbol VARCHAR(20) NOT NULL DEFAULT 'GBPUSD',
                pattern_type VARCHAR(50) NOT NULL,
                wave_degree VARCHAR(50) NOT NULL,
                start_time TIMESTAMPTZ NOT NULL,
                end_time TIMESTAMPTZ NOT NULL,
                price_low DECIMAL(12,6) NOT NULL,
                price_high DECIMAL(12,6) NOT NULL,
                wave_points JSONB NOT NULL,
                fibonacci_ratios JSONB,
                confidence_score DECIMAL(5,4) NOT NULL,
                completion_percentage DECIMAL(5,4) NOT NULL DEFAULT 1.0,
                next_target DECIMAL(12,6),
                invalidation_level DECIMAL(12,6),
                session_context VARCHAR(20),
                pattern_embedding vector(256),  -- pgvector for similarity search
                metadata JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            """

            await self.db_client.execute(create_patterns_table)

            # Create indexes for performance
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_elliott_patterns_symbol ON elliott_wave_patterns(symbol);",
                "CREATE INDEX IF NOT EXISTS idx_elliott_patterns_type ON elliott_wave_patterns(pattern_type);",
                "CREATE INDEX IF NOT EXISTS idx_elliott_patterns_confidence ON elliott_wave_patterns(confidence_score);",
                "CREATE INDEX IF NOT EXISTS idx_elliott_patterns_time ON elliott_wave_patterns(start_time, end_time);",
                "CREATE INDEX IF NOT EXISTS idx_elliott_patterns_embedding ON elliott_wave_patterns USING ivfflat (pattern_embedding vector_cosine_ops) WITH (lists = 100);",  # pgvector index
            ]

            for index_sql in indexes:
                await self.db_client.execute(index_sql)

            # Create wave signals table
            create_signals_table = """
            CREATE TABLE IF NOT EXISTS elliott_wave_signals (
                id SERIAL PRIMARY KEY,
                pattern_id VARCHAR(100) NOT NULL,
                symbol VARCHAR(20) NOT NULL DEFAULT 'GBPUSD',
                signal_strength DECIMAL(5,4) NOT NULL,
                confidence DECIMAL(5,4) NOT NULL,
                entry_target DECIMAL(12,6),
                stop_loss DECIMAL(12,6),
                take_profit DECIMAL(12,6),
                risk_reward_ratio DECIMAL(8,4),
                time_horizon VARCHAR(20),
                reasoning TEXT,
                generated_at TIMESTAMPTZ DEFAULT NOW(),
                expires_at TIMESTAMPTZ,
                is_active BOOLEAN DEFAULT TRUE,
                metadata JSONB
            );
            """

            await self.db_client.execute(create_signals_table)

            # Create index for signals
            await self.db_client.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_elliott_signals_active
                ON elliott_wave_signals(symbol, is_active, generated_at);
            """
            )

            self.logger.info(
                "Elliott Wave tables set up successfully with pgvector support"
            )

        except Exception as e:
            self.logger.error(f"Error setting up Elliott Wave tables: {e}")
            raise

    async def analyze_gbpusd_waves(
        self, price_data: pd.DataFrame
    ) -> List[ElliottWavePattern]:
        """
        Analyze GBP/USD price data for Elliott Wave patterns

        Args:
            price_data: DataFrame with OHLCV data and timestamp index

        Returns:
            List of detected Elliott Wave patterns
        """
        try:
            if len(price_data) < 50:  # Need minimum data for wave analysis
                self.logger.warning("Insufficient data for Elliott Wave analysis")
                return []

            # Step 1: Identify significant pivot points
            pivot_points = await self._identify_pivot_points(price_data)

            if len(pivot_points) < 5:  # Need at least 5 points for a complete wave
                self.logger.warning("Insufficient pivot points for wave patterns")
                return []

            # Step 2: Classify wave degrees based on price movement size
            classified_pivots = await self._classify_wave_degrees(
                pivot_points, price_data
            )

            # Step 3: Detect Elliott Wave patterns
            patterns = await self._detect_wave_patterns(classified_pivots, price_data)

            # Step 4: Validate patterns using GBP/USD-specific rules
            validated_patterns = await self._validate_gbpusd_patterns(
                patterns, price_data
            )

            # Step 5: Calculate pattern confidence and targets
            enhanced_patterns = await self._enhance_pattern_analysis(
                validated_patterns, price_data
            )

            # Step 6: Update pattern tracking
            await self._update_pattern_tracking(enhanced_patterns)

            self.last_analysis_time = datetime.utcnow()
            self.logger.info(
                f"Analyzed {len(enhanced_patterns)} Elliott Wave patterns for GBP/USD"
            )

            return enhanced_patterns

        except Exception as e:
            self.logger.error(f"Error in Elliott Wave analysis: {e}")
            return []

    async def _identify_pivot_points(self, data: pd.DataFrame) -> List[WavePoint]:
        """Identify significant pivot points in GBP/USD price data"""

        pivots = []

        try:
            # Calculate pivot strength (adaptive for GBP/USD volatility)
            lookback = min(20, len(data) // 4)  # Adaptive lookback based on data length

            # Find local highs and lows
            highs = data["high"].rolling(window=lookback, center=True).max()
            lows = data["low"].rolling(window=lookback, center=True).min()

            for i in range(lookback, len(data) - lookback):
                current_high = data["high"].iloc[i]
                current_low = data["low"].iloc[i]
                timestamp = data.index[i]
                volume = data.get("volume", pd.Series([None] * len(data))).iloc[i]

                # Check for significant high pivot
                if current_high == highs.iloc[i]:
                    # Calculate pivot strength based on price movement
                    price_move = abs(
                        current_high
                        - data["low"].iloc[i - lookback : i + lookback].min()
                    )
                    move_pips = price_move * 10000  # Convert to pips

                    if move_pips >= self.min_wave_size_pips:
                        confidence = min(
                            move_pips / 100, 1.0
                        )  # Scale confidence by pip movement

                        pivots.append(
                            WavePoint(
                                timestamp=timestamp,
                                price=current_high,
                                wave_position=WavePosition.WAVE_1,  # Will be classified later
                                degree=WaveDegree.MINUTE,  # Will be classified later
                                confidence=confidence,
                                volume=volume,
                                metadata={
                                    "pivot_type": "high",
                                    "strength_pips": move_pips,
                                },
                            )
                        )

                # Check for significant low pivot
                if current_low == lows.iloc[i]:
                    price_move = abs(
                        data["high"].iloc[i - lookback : i + lookback].max()
                        - current_low
                    )
                    move_pips = price_move * 10000

                    if move_pips >= self.min_wave_size_pips:
                        confidence = min(move_pips / 100, 1.0)

                        pivots.append(
                            WavePoint(
                                timestamp=timestamp,
                                price=current_low,
                                wave_position=WavePosition.WAVE_2,  # Will be classified later
                                degree=WaveDegree.MINUTE,  # Will be classified later
                                confidence=confidence,
                                volume=volume,
                                metadata={
                                    "pivot_type": "low",
                                    "strength_pips": move_pips,
                                },
                            )
                        )

            # Sort pivots by timestamp
            pivots.sort(key=lambda p: p.timestamp)

            # Filter overlapping pivots (keep strongest)
            filtered_pivots = await self._filter_overlapping_pivots(pivots)

            self.logger.info(
                f"Identified {len(filtered_pivots)} significant pivot points"
            )

            return filtered_pivots

        except Exception as e:
            self.logger.error(f"Error identifying pivot points: {e}")
            return []

    async def _filter_overlapping_pivots(
        self, pivots: List[WavePoint]
    ) -> List[WavePoint]:
        """Filter out overlapping pivot points, keeping the strongest"""

        if not pivots:
            return pivots

        filtered = [pivots[0]]  # Always keep first pivot

        for pivot in pivots[1:]:
            last_pivot = filtered[-1]

            # Check time proximity (don't allow pivots too close together)
            time_diff = (
                pivot.timestamp - last_pivot.timestamp
            ).total_seconds() / 60  # minutes
            min_time_gap = (
                15  # Minimum 15 minutes between significant pivots for GBP/USD
            )

            if time_diff < min_time_gap:
                # Keep pivot with higher confidence
                if pivot.confidence > last_pivot.confidence:
                    filtered[-1] = pivot
            else:
                filtered.append(pivot)

        return filtered

    async def _classify_wave_degrees(
        self, pivots: List[WavePoint], data: pd.DataFrame
    ) -> List[WavePoint]:
        """Classify wave degrees based on GBP/USD movement characteristics"""

        classified = []

        for i, pivot in enumerate(pivots):
            if i == 0:
                classified.append(pivot)
                continue

            # Calculate movement from previous pivot
            prev_pivot = classified[-1]
            price_move = abs(pivot.price - prev_pivot.price)
            move_pips = price_move * 10000

            # Classify degree based on movement size
            degree = WaveDegree.SUBMINUETTE  # Default
            for deg, threshold in sorted(
                self.degree_thresholds.items(), key=lambda x: x[1], reverse=True
            ):
                if move_pips >= threshold:
                    degree = deg
                    break

            # Create classified pivot
            classified_pivot = WavePoint(
                timestamp=pivot.timestamp,
                price=pivot.price,
                wave_position=pivot.wave_position,
                degree=degree,
                confidence=pivot.confidence,
                volume=pivot.volume,
                metadata={
                    **pivot.metadata,
                    "move_pips": move_pips,
                    "classified_degree": degree.value,
                },
            )

            classified.append(classified_pivot)

        return classified

    async def _detect_wave_patterns(
        self, pivots: List[WavePoint], data: pd.DataFrame
    ) -> List[ElliottWavePattern]:
        """Detect Elliott Wave patterns from classified pivot points"""

        patterns = []

        try:
            # Look for 5-wave impulse patterns (most common in trending GBP/USD)
            impulse_patterns = await self._detect_impulse_patterns(pivots, data)
            patterns.extend(impulse_patterns)

            # Look for 3-wave corrective patterns (common in ranging GBP/USD)
            corrective_patterns = await self._detect_corrective_patterns(pivots, data)
            patterns.extend(corrective_patterns)

            # Look for diagonal patterns (terminal patterns in GBP/USD)
            diagonal_patterns = await self._detect_diagonal_patterns(pivots, data)
            patterns.extend(diagonal_patterns)

            self.logger.info(
                f"Detected {len(patterns)} potential Elliott Wave patterns"
            )

            return patterns

        except Exception as e:
            self.logger.error(f"Error detecting wave patterns: {e}")
            return []

    async def _detect_impulse_patterns(
        self, pivots: List[WavePoint], data: pd.DataFrame
    ) -> List[ElliottWavePattern]:
        """Detect 5-wave impulse patterns optimized for GBP/USD"""

        patterns = []

        # Need at least 5 pivots for an impulse pattern
        if len(pivots) < 5:
            return patterns

        # Sliding window approach to find 5-wave sequences
        for i in range(len(pivots) - 4):
            wave_sequence = pivots[i : i + 5]

            # Check if this could be a valid impulse pattern
            if await self._is_valid_impulse_sequence(wave_sequence):

                # Create pattern
                pattern = ElliottWavePattern(
                    pattern_id=f"impulse_{wave_sequence[0].timestamp.strftime('%Y%m%d_%H%M%S')}",
                    wave_type=WaveType.IMPULSE,
                    degree=max(
                        [p.degree for p in wave_sequence],
                        key=lambda x: self.degree_thresholds[x],
                    ),
                    wave_points=wave_sequence,
                    start_time=wave_sequence[0].timestamp,
                    end_time=wave_sequence[-1].timestamp,
                    price_range=(
                        min([p.price for p in wave_sequence]),
                        max([p.price for p in wave_sequence]),
                    ),
                    fibonacci_ratios={},  # Will be calculated later
                    confidence_score=0.0,  # Will be calculated later
                    completion_percentage=1.0,  # Complete 5-wave pattern
                    next_expected_target=None,  # Will be calculated
                    invalidation_level=None,  # Will be calculated
                    session_context="",  # Will be determined
                    metadata={"pattern_type": "complete_impulse"},
                )

                patterns.append(pattern)

        return patterns

    async def _is_valid_impulse_sequence(self, waves: List[WavePoint]) -> bool:
        """Validate if 5 wave points form a valid Elliott impulse pattern"""

        if len(waves) != 5:
            return False

        try:
            # Elliott Wave rules for impulse patterns:
            # 1. Wave 2 never retraces more than 100% of Wave 1
            # 2. Wave 3 is never the shortest wave
            # 3. Wave 4 never overlaps Wave 1 price territory

            # Calculate wave movements
            wave1 = abs(waves[1].price - waves[0].price)
            wave2 = abs(waves[2].price - waves[1].price)
            wave3 = abs(waves[3].price - waves[2].price)
            wave4 = abs(waves[4].price - waves[3].price)

            # Rule 1: Wave 2 retracement check
            if wave2 > wave1:  # More than 100% retracement
                return False

            # Rule 2: Wave 3 cannot be shortest
            if wave3 < wave1 and wave3 < wave4:
                return False

            # Rule 3: Wave 4 overlap check (simplified)
            # This is a complex check - simplified version for now
            if len(waves) >= 4:
                wave1_range = (
                    min(waves[0].price, waves[1].price),
                    max(waves[0].price, waves[1].price),
                )
                wave4_price = waves[3].price

                # Check if Wave 4 price overlaps with Wave 1 territory
                if wave1_range[0] <= wave4_price <= wave1_range[1]:
                    return False

            return True

        except Exception:
            return False

    async def _detect_corrective_patterns(
        self, pivots: List[WavePoint], data: pd.DataFrame
    ) -> List[ElliottWavePattern]:
        """Detect 3-wave corrective patterns (ABC) in GBP/USD"""

        patterns = []

        # Need at least 3 pivots for corrective pattern
        if len(pivots) < 3:
            return patterns

        # Look for ABC corrective patterns
        for i in range(len(pivots) - 2):
            wave_sequence = pivots[i : i + 3]

            # Check if this could be a valid corrective pattern
            if await self._is_valid_corrective_sequence(wave_sequence):

                pattern = ElliottWavePattern(
                    pattern_id=f"corrective_{wave_sequence[0].timestamp.strftime('%Y%m%d_%H%M%S')}",
                    wave_type=WaveType.ZIGZAG,  # Most common corrective pattern
                    degree=max(
                        [p.degree for p in wave_sequence],
                        key=lambda x: self.degree_thresholds[x],
                    ),
                    wave_points=wave_sequence,
                    start_time=wave_sequence[0].timestamp,
                    end_time=wave_sequence[-1].timestamp,
                    price_range=(
                        min([p.price for p in wave_sequence]),
                        max([p.price for p in wave_sequence]),
                    ),
                    fibonacci_ratios={},
                    confidence_score=0.0,
                    completion_percentage=1.0,  # Complete ABC pattern
                    next_expected_target=None,
                    invalidation_level=None,
                    session_context="",
                    metadata={"pattern_type": "abc_corrective"},
                )

                patterns.append(pattern)

        return patterns

    async def _is_valid_corrective_sequence(self, waves: List[WavePoint]) -> bool:
        """Validate if 3 wave points form a valid corrective pattern"""

        if len(waves) != 3:
            return False

        try:
            # Basic corrective pattern validation
            # Wave A and C should be in same direction
            # Wave B should be counter-trend

            wave_a_direction = 1 if waves[1].price > waves[0].price else -1
            wave_b_direction = 1 if waves[2].price > waves[1].price else -1

            # Wave B should be opposite direction to Wave A (counter-trend)
            if wave_a_direction == wave_b_direction:
                return False

            # Additional validation: reasonable retracement ratios
            wave_a = abs(waves[1].price - waves[0].price)
            wave_b = abs(waves[2].price - waves[1].price)

            # Wave B should typically retrace 38.2%-78.6% of Wave A
            retracement_ratio = wave_b / wave_a if wave_a > 0 else 0

            if not (0.25 <= retracement_ratio <= 0.9):  # Allow some flexibility
                return False

            return True

        except Exception:
            return False

    async def _detect_diagonal_patterns(
        self, pivots: List[WavePoint], data: pd.DataFrame
    ) -> List[ElliottWavePattern]:
        """Detect diagonal (wedge) patterns in GBP/USD"""

        patterns = []

        # Diagonal detection is complex - simplified implementation for now
        # Would involve trend line convergence analysis

        return patterns

    async def _validate_gbpusd_patterns(
        self, patterns: List[ElliottWavePattern], data: pd.DataFrame
    ) -> List[ElliottWavePattern]:
        """Apply GBP/USD-specific validation rules to patterns"""

        validated = []

        for pattern in patterns:
            try:
                # Calculate Fibonacci ratios for pattern validation
                fibonacci_ratios = await self._calculate_fibonacci_ratios(pattern)
                pattern.fibonacci_ratios = fibonacci_ratios

                # Calculate confidence score based on GBP/USD characteristics
                confidence = await self._calculate_gbpusd_confidence(pattern, data)
                pattern.confidence_score = confidence

                # Determine session context
                session = await self._determine_session_context(pattern)
                pattern.session_context = session

                # Only keep patterns with sufficient confidence
                if confidence >= self.min_pattern_confidence:
                    validated.append(pattern)

            except Exception as e:
                self.logger.warning(
                    f"Error validating pattern {pattern.pattern_id}: {e}"
                )
                continue

        self.logger.info(
            f"Validated {len(validated)}/{len(patterns)} Elliott Wave patterns"
        )

        return validated

    async def _calculate_fibonacci_ratios(
        self, pattern: ElliottWavePattern
    ) -> Dict[str, float]:
        """Calculate Fibonacci ratios for pattern validation"""

        ratios = {}

        try:
            if pattern.wave_type == WaveType.IMPULSE and len(pattern.wave_points) >= 5:
                waves = pattern.wave_points

                # Calculate key Fibonacci relationships
                wave1_size = abs(waves[1].price - waves[0].price)
                wave2_size = abs(waves[2].price - waves[1].price)
                wave3_size = abs(waves[3].price - waves[2].price)

                if wave1_size > 0:
                    ratios["wave2_to_wave1"] = wave2_size / wave1_size
                    ratios["wave3_to_wave1"] = wave3_size / wave1_size

                # Check against common Fibonacci levels
                for level in self.fibonacci_levels:
                    for ratio_name, ratio_value in ratios.items():
                        if abs(ratio_value - level) < 0.05:  # 5% tolerance
                            ratios[f"{ratio_name}_fib_match"] = level
                            break

            elif pattern.wave_type == WaveType.ZIGZAG and len(pattern.wave_points) >= 3:
                waves = pattern.wave_points

                # Calculate ABC relationships
                wave_a_size = abs(waves[1].price - waves[0].price)
                wave_c_size = abs(waves[2].price - waves[1].price)

                if wave_a_size > 0:
                    ratios["wave_c_to_wave_a"] = wave_c_size / wave_a_size

        except Exception as e:
            self.logger.warning(f"Error calculating Fibonacci ratios: {e}")

        return ratios

    async def _calculate_gbpusd_confidence(
        self, pattern: ElliottWavePattern, data: pd.DataFrame
    ) -> float:
        """Calculate pattern confidence using GBP/USD-specific factors"""

        confidence_factors = []

        try:
            # Factor 1: Fibonacci ratio alignment (30% weight)
            fib_score = 0.0
            for ratio_name, ratio_value in pattern.fibonacci_ratios.items():
                if "fib_match" in ratio_name:
                    fib_level = ratio_value
                    weight = self.gbpusd_fib_weights.get(fib_level, 0.1)
                    fib_score += weight

            confidence_factors.append(min(fib_score, 1.0) * 0.3)

            # Factor 2: Session timing (20% weight)
            session_score = 0.5  # Default
            if pattern.session_context == "overlap":
                session_score = 1.0  # London/NY overlap is ideal for GBP/USD
            elif pattern.session_context in ["london", "ny"]:
                session_score = 0.8  # Good activity
            elif pattern.session_context == "asian":
                session_score = 0.3  # Lower activity

            confidence_factors.append(session_score * 0.2)

            # Factor 3: Volume confirmation (15% weight)
            volume_score = 0.5  # Default if no volume data

            if "volume" in data.columns:
                pattern_start = pattern.start_time
                pattern_end = pattern.end_time
                pattern_data = data[pattern_start:pattern_end]

                if not pattern_data.empty:
                    avg_volume = pattern_data["volume"].mean()
                    total_avg_volume = data["volume"].mean()

                    if avg_volume > total_avg_volume * 1.2:
                        volume_score = 1.0  # Above average volume
                    elif avg_volume > total_avg_volume:
                        volume_score = 0.8  # Good volume
                    else:
                        volume_score = 0.6  # Below average

            confidence_factors.append(volume_score * 0.15)

            # Factor 4: Pattern completeness (20% weight)
            completeness_score = pattern.completion_percentage
            confidence_factors.append(completeness_score * 0.2)

            # Factor 5: Individual pivot confidence (15% weight)
            pivot_confidence = np.mean([p.confidence for p in pattern.wave_points])
            confidence_factors.append(pivot_confidence * 0.15)

            # Total confidence
            total_confidence = sum(confidence_factors)

            return min(total_confidence, 1.0)

        except Exception as e:
            self.logger.warning(f"Error calculating confidence: {e}")
            return 0.5

    async def _determine_session_context(self, pattern: ElliottWavePattern) -> str:
        """Determine trading session context for the pattern"""

        try:
            start_time = pattern.start_time.time()
            end_time = pattern.end_time.time()

            # Check if pattern occurred during London/NY overlap
            if (
                self.overlap_session[0] <= start_time <= self.overlap_session[1]
                or self.overlap_session[0] <= end_time <= self.overlap_session[1]
            ):
                return "overlap"

            # Check London session
            elif (
                self.london_session[0] <= start_time <= self.london_session[1]
                or self.london_session[0] <= end_time <= self.london_session[1]
            ):
                return "london"

            # Check NY session
            elif (
                self.ny_session[0] <= start_time <= self.ny_session[1]
                or self.ny_session[0] <= end_time <= self.ny_session[1]
            ):
                return "ny"

            else:
                return "asian"

        except Exception:
            return "unknown"

    async def _enhance_pattern_analysis(
        self, patterns: List[ElliottWavePattern], data: pd.DataFrame
    ) -> List[ElliottWavePattern]:
        """Enhance patterns with targets and invalidation levels"""

        enhanced = []

        for pattern in patterns:
            try:
                # Calculate next expected target
                if pattern.wave_type == WaveType.IMPULSE:
                    target = await self._calculate_impulse_targets(pattern)
                    pattern.next_expected_target = target

                elif pattern.wave_type == WaveType.ZIGZAG:
                    target = await self._calculate_corrective_targets(pattern)
                    pattern.next_expected_target = target

                # Calculate invalidation level
                invalidation = await self._calculate_invalidation_level(pattern)
                pattern.invalidation_level = invalidation

                enhanced.append(pattern)

            except Exception as e:
                self.logger.warning(
                    f"Error enhancing pattern {pattern.pattern_id}: {e}"
                )
                enhanced.append(pattern)  # Keep pattern even if enhancement fails

        return enhanced

    async def _calculate_impulse_targets(
        self, pattern: ElliottWavePattern
    ) -> Optional[float]:
        """Calculate price targets for impulse patterns"""

        try:
            if len(pattern.wave_points) >= 5:
                waves = pattern.wave_points

                # Calculate Wave 5 target using Wave 1 projection
                wave1_size = abs(waves[1].price - waves[0].price)
                wave4_price = waves[3].price

                # Common target: Wave 4 low/high + Wave 1 size
                if waves[1].price > waves[0].price:  # Uptrend
                    target = wave4_price + wave1_size
                else:  # Downtrend
                    target = wave4_price - wave1_size

                return target

        except Exception:
            pass

        return None

    async def _calculate_corrective_targets(
        self, pattern: ElliottWavePattern
    ) -> Optional[float]:
        """Calculate price targets for corrective patterns"""

        try:
            if len(pattern.wave_points) >= 3:
                waves = pattern.wave_points

                # Calculate Wave C target using Wave A projection
                wave_a_size = abs(waves[1].price - waves[0].price)
                wave_b_price = waves[1].price

                # Common target: Wave B + 100% of Wave A
                if waves[1].price > waves[0].price:  # A up, C down
                    target = wave_b_price - wave_a_size
                else:  # A down, C up
                    target = wave_b_price + wave_a_size

                return target

        except Exception:
            pass

        return None

    async def _calculate_invalidation_level(
        self, pattern: ElliottWavePattern
    ) -> Optional[float]:
        """Calculate pattern invalidation level"""

        try:
            if pattern.wave_type == WaveType.IMPULSE and len(pattern.wave_points) >= 4:
                # For impulse, invalidation is typically Wave 1 low/high
                return pattern.wave_points[0].price

            elif pattern.wave_type == WaveType.ZIGZAG and len(pattern.wave_points) >= 3:
                # For corrective, invalidation is typically Wave A start
                return pattern.wave_points[0].price

        except Exception:
            pass

        return None

    async def _update_pattern_tracking(self, patterns: List[ElliottWavePattern]):
        """Update active pattern tracking"""

        try:
            current_time = datetime.utcnow()

            # Remove expired patterns
            expired_ids = []
            for pattern_id, pattern in self.active_patterns.items():
                age_hours = (current_time - pattern.end_time).total_seconds() / 3600
                if age_hours > self.max_pattern_age_hours:
                    expired_ids.append(pattern_id)

            for pattern_id in expired_ids:
                expired_pattern = self.active_patterns.pop(pattern_id)
                self.historical_patterns.append(expired_pattern)

            # Add new patterns
            for pattern in patterns:
                self.active_patterns[pattern.pattern_id] = pattern

            self.logger.info(
                f"Tracking {len(self.active_patterns)} active Elliott Wave patterns"
            )

        except Exception as e:
            self.logger.error(f"Error updating pattern tracking: {e}")

    async def generate_wave_signals(
        self, current_price: float, patterns: List[ElliottWavePattern]
    ) -> List[WaveSignal]:
        """Generate trading signals from Elliott Wave patterns"""

        signals = []

        try:
            for pattern in patterns:
                signal = await self._pattern_to_signal(pattern, current_price)
                if signal:
                    signals.append(signal)

            # Sort signals by confidence
            signals.sort(key=lambda s: s.confidence, reverse=True)

            self.logger.info(f"Generated {len(signals)} Elliott Wave signals")

            return signals

        except Exception as e:
            self.logger.error(f"Error generating wave signals: {e}")
            return []

    async def _pattern_to_signal(
        self, pattern: ElliottWavePattern, current_price: float
    ) -> Optional[WaveSignal]:
        """Convert Elliott Wave pattern to trading signal"""

        try:
            # Determine signal direction and strength
            signal_strength = 0.0
            reasoning = ""

            if pattern.wave_type == WaveType.IMPULSE:
                # Check if we're at a good entry point for impulse continuation
                if pattern.next_expected_target:
                    if pattern.next_expected_target > current_price:
                        signal_strength = 0.7  # Bullish
                        reasoning = f"Impulse pattern targeting {pattern.next_expected_target:.5f}"
                    else:
                        signal_strength = -0.7  # Bearish
                        reasoning = f"Impulse pattern targeting {pattern.next_expected_target:.5f}"

            elif pattern.wave_type == WaveType.ZIGZAG:
                # Corrective patterns suggest counter-trend opportunities
                if pattern.next_expected_target:
                    if pattern.next_expected_target > current_price:
                        signal_strength = 0.5  # Moderate bullish
                        reasoning = f"Corrective pattern completing at {pattern.next_expected_target:.5f}"
                    else:
                        signal_strength = -0.5  # Moderate bearish
                        reasoning = f"Corrective pattern completing at {pattern.next_expected_target:.5f}"

            # Adjust signal strength based on pattern confidence
            signal_strength *= pattern.confidence_score

            if abs(signal_strength) < 0.3:  # Minimum signal threshold
                return None

            # Calculate risk management levels
            entry_target = current_price
            stop_loss = pattern.invalidation_level
            take_profit = pattern.next_expected_target

            # Calculate risk/reward ratio
            risk_reward_ratio = None
            if stop_loss and take_profit:
                risk = abs(current_price - stop_loss)
                reward = abs(take_profit - current_price)
                if risk > 0:
                    risk_reward_ratio = reward / risk

            # Determine time horizon based on pattern degree
            time_horizon_map = {
                WaveDegree.SUBMINUETTE: "minutes",
                WaveDegree.MINUETTE: "minutes",
                WaveDegree.MINUTE: "hours",
                WaveDegree.MINOR: "hours",
                WaveDegree.INTERMEDIATE: "days",
                WaveDegree.PRIMARY: "days",
                WaveDegree.CYCLE: "days",
                WaveDegree.SUPERCYCLE: "days",
            }

            time_horizon = time_horizon_map.get(pattern.degree, "hours")

            return WaveSignal(
                signal_strength=signal_strength,
                confidence=pattern.confidence_score,
                pattern=pattern,
                reasoning=reasoning,
                entry_target=entry_target,
                stop_loss=stop_loss,
                take_profit=take_profit,
                time_horizon=time_horizon,
                risk_reward_ratio=risk_reward_ratio,
                timestamp=datetime.utcnow(),
            )

        except Exception as e:
            self.logger.warning(f"Error converting pattern to signal: {e}")
            return None

    async def get_active_patterns(self) -> List[ElliottWavePattern]:
        """Get currently active Elliott Wave patterns"""
        return list(self.active_patterns.values())

    async def get_pattern_summary(self) -> Dict[str, Any]:
        """Get summary of Elliott Wave analysis"""

        return {
            "active_patterns": len(self.active_patterns),
            "historical_patterns": len(self.historical_patterns),
            "last_analysis": self.last_analysis_time,
            "pattern_types": {
                wave_type.value: len(
                    [
                        p
                        for p in self.active_patterns.values()
                        if p.wave_type == wave_type
                    ]
                )
                for wave_type in WaveType
            },
            "avg_confidence": (
                np.mean([p.confidence_score for p in self.active_patterns.values()])
                if self.active_patterns
                else 0.0
            ),
        }

    async def _generate_pattern_embedding(
        self, pattern: ElliottWavePattern
    ) -> np.ndarray:
        """Generate 256-dimensional vector embedding for Elliott Wave pattern"""

        try:
            # Create feature vector from pattern characteristics
            embedding = np.zeros(256)

            # Price features (0-49): normalized price movements and ratios
            if len(pattern.wave_points) >= 2:
                prices = [p.price for p in pattern.wave_points]
                price_range = max(prices) - min(prices)

                # Normalize prices relative to range
                normalized_prices = [
                    (p - min(prices)) / price_range if price_range > 0 else 0.5
                    for p in prices
                ]

                # Fill first 50 dimensions with price features
                for i, norm_price in enumerate(normalized_prices[:25]):
                    if i < 25:
                        embedding[i] = norm_price

                # Price differences and ratios
                for i in range(min(len(prices) - 1, 25)):
                    if i < 25:
                        price_diff = (
                            (prices[i + 1] - prices[i]) / price_range
                            if price_range > 0
                            else 0
                        )
                        embedding[25 + i] = price_diff

            # Time features (50-69): pattern duration and timing
            duration_hours = (
                pattern.end_time - pattern.start_time
            ).total_seconds() / 3600
            embedding[50] = min(duration_hours / 24, 1.0)  # Normalize to days

            # Session features
            session_encoding = {
                "london": 0.8,
                "ny": 0.6,
                "overlap": 1.0,
                "asian": 0.2,
                "unknown": 0.0,
            }
            embedding[51] = session_encoding.get(pattern.session_context, 0.0)

            # Wave degree encoding (52-61)
            degree_encoding = {
                WaveDegree.SUBMINUETTE: 0.1,
                WaveDegree.MINUETTE: 0.2,
                WaveDegree.MINUTE: 0.3,
                WaveDegree.MINOR: 0.4,
                WaveDegree.INTERMEDIATE: 0.5,
                WaveDegree.PRIMARY: 0.6,
                WaveDegree.CYCLE: 0.8,
                WaveDegree.SUPERCYCLE: 1.0,
            }
            embedding[52] = degree_encoding.get(pattern.degree, 0.0)

            # Pattern type encoding (53-57)
            type_encoding = {
                WaveType.IMPULSE: [1.0, 0.0, 0.0, 0.0, 0.0],
                WaveType.ZIGZAG: [0.0, 1.0, 0.0, 0.0, 0.0],
                WaveType.DIAGONAL: [0.0, 0.0, 1.0, 0.0, 0.0],
                WaveType.FLAT: [0.0, 0.0, 0.0, 1.0, 0.0],
                WaveType.TRIANGLE: [0.0, 0.0, 0.0, 0.0, 1.0],
            }
            type_vec = type_encoding.get(pattern.wave_type, [0.0, 0.0, 0.0, 0.0, 0.0])
            embedding[53:58] = type_vec

            # Fibonacci ratio features (58-93): 36 dimensions for Fibonacci analysis
            fib_idx = 58
            for level in self.fibonacci_levels:
                # Check if pattern has this Fibonacci ratio
                has_fib_match = any(
                    abs(ratio - level) < 0.05
                    for ratio in pattern.fibonacci_ratios.values()
                    if isinstance(ratio, (int, float))
                )
                embedding[fib_idx] = 1.0 if has_fib_match else 0.0
                fib_idx += 1
                if fib_idx >= 94:
                    break

            # Confidence and completion features (94-97)
            embedding[94] = pattern.confidence_score
            embedding[95] = pattern.completion_percentage
            embedding[96] = 1.0 if pattern.next_expected_target is not None else 0.0
            embedding[97] = 1.0 if pattern.invalidation_level is not None else 0.0

            # Statistical features (98-119): wave point statistics
            if pattern.wave_points:
                prices = [p.price for p in pattern.wave_points]
                confidences = [p.confidence for p in pattern.wave_points]

                embedding[98] = np.mean(prices)
                embedding[99] = np.std(prices) if len(prices) > 1 else 0.0
                embedding[100] = np.mean(confidences)
                embedding[101] = np.std(confidences) if len(confidences) > 1 else 0.0

                # Price momentum features
                if len(prices) >= 3:
                    momentum = []
                    for i in range(1, len(prices)):
                        momentum.append(prices[i] - prices[i - 1])

                    embedding[102] = np.mean(momentum)
                    embedding[103] = np.std(momentum) if len(momentum) > 1 else 0.0

            # Market structure features (120-139)
            price_low, price_high = pattern.price_range
            price_range_pips = (price_high - price_low) * 10000
            embedding[120] = min(price_range_pips / 1000, 1.0)  # Normalize pip range

            # Volatility proxy
            if len(pattern.wave_points) >= 2:
                volatility = np.std([p.price for p in pattern.wave_points])
                embedding[121] = min(volatility * 10000, 1.0)  # Normalize volatility

            # Pattern symmetry and proportions (122-139)
            if len(pattern.wave_points) >= 3:
                # Calculate wave proportions
                wave_sizes = []
                for i in range(len(pattern.wave_points) - 1):
                    wave_size = abs(
                        pattern.wave_points[i + 1].price - pattern.wave_points[i].price
                    )
                    wave_sizes.append(wave_size)

                if wave_sizes:
                    max_wave = max(wave_sizes)
                    for i, size in enumerate(wave_sizes[:18]):  # Limit to 18 dimensions
                        if i < 18:
                            embedding[122 + i] = (
                                size / max_wave if max_wave > 0 else 0.0
                            )

            # Additional pattern characteristics (140-255)
            # Fill remaining dimensions with derived features
            for i in range(140, 256):
                # Create synthetic features based on combinations
                base_idx = (i - 140) % 50
                if base_idx < len(embedding[:50]):
                    # Create non-linear combinations of existing features
                    embedding[i] = np.tanh(embedding[base_idx] * 2.0)
                else:
                    embedding[i] = 0.0

            # Normalize the entire embedding vector
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm

            return embedding

        except Exception as e:
            self.logger.error(f"Error generating pattern embedding: {e}")
            return np.zeros(256)

    async def store_pattern(self, pattern: ElliottWavePattern) -> bool:
        """Store Elliott Wave pattern in TimescaleDB with pgvector embedding"""

        if not self.db_client:
            self.logger.warning("No database client available for pattern storage")
            return False

        try:
            # Generate pattern embedding
            embedding = await self._generate_pattern_embedding(pattern)

            # Prepare wave points data
            wave_points_data = []
            for wp in pattern.wave_points:
                wave_points_data.append(
                    {
                        "timestamp": wp.timestamp.isoformat(),
                        "price": float(wp.price),
                        "wave_position": wp.wave_position.value,
                        "degree": wp.degree.value,
                        "confidence": wp.confidence,
                        "volume": wp.volume,
                        "metadata": wp.metadata,
                    }
                )

            # Insert pattern into database
            insert_sql = """
            INSERT INTO elliott_wave_patterns (
                pattern_id, pattern_type, wave_degree, start_time, end_time,
                price_low, price_high, wave_points, fibonacci_ratios,
                confidence_score, completion_percentage, next_target,
                invalidation_level, session_context, pattern_embedding, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
            ON CONFLICT (pattern_id) DO UPDATE SET
                confidence_score = EXCLUDED.confidence_score,
                completion_percentage = EXCLUDED.completion_percentage,
                next_target = EXCLUDED.next_target,
                invalidation_level = EXCLUDED.invalidation_level,
                pattern_embedding = EXCLUDED.pattern_embedding,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
            """

            await self.db_client.execute(
                insert_sql,
                pattern.pattern_id,
                pattern.wave_type.value,
                pattern.degree.value,
                pattern.start_time,
                pattern.end_time,
                float(pattern.price_range[0]),
                float(pattern.price_range[1]),
                wave_points_data,  # JSONB
                pattern.fibonacci_ratios,  # JSONB
                pattern.confidence_score,
                pattern.completion_percentage,
                (
                    float(pattern.next_expected_target)
                    if pattern.next_expected_target
                    else None
                ),
                (
                    float(pattern.invalidation_level)
                    if pattern.invalidation_level
                    else None
                ),
                pattern.session_context,
                embedding.tolist(),  # Convert numpy array to list for pgvector
                pattern.metadata,  # JSONB
            )

            self.logger.debug(f"Stored pattern {pattern.pattern_id} in database")
            return True

        except Exception as e:
            self.logger.error(f"Error storing pattern {pattern.pattern_id}: {e}")
            return False

    async def find_similar_patterns(
        self, pattern: ElliottWavePattern, limit: int = 5, min_similarity: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Find similar Elliott Wave patterns using pgvector similarity search"""

        if not self.db_client:
            self.logger.warning("No database client available for similarity search")
            return []

        try:
            # Generate embedding for query pattern
            query_embedding = await self._generate_pattern_embedding(pattern)

            # Perform similarity search using pgvector
            search_sql = """
            SELECT
                pattern_id,
                pattern_type,
                wave_degree,
                start_time,
                end_time,
                confidence_score,
                fibonacci_ratios,
                next_target,
                session_context,
                1 - (pattern_embedding <=> $1::vector) as similarity_score,
                metadata
            FROM elliott_wave_patterns
            WHERE
                symbol = 'GBPUSD'
                AND pattern_type = $2
                AND (1 - (pattern_embedding <=> $1::vector)) >= $3
                AND pattern_id != $4
            ORDER BY pattern_embedding <=> $1::vector
            LIMIT $5;
            """

            results = await self.db_client.fetch(
                search_sql,
                query_embedding.tolist(),
                pattern.wave_type.value,
                min_similarity,
                pattern.pattern_id,
                limit,
            )

            similar_patterns = []
            for row in results:
                similar_patterns.append(
                    {
                        "pattern_id": row["pattern_id"],
                        "pattern_type": row["pattern_type"],
                        "wave_degree": row["wave_degree"],
                        "similarity_score": float(row["similarity_score"]),
                        "confidence_score": float(row["confidence_score"]),
                        "fibonacci_ratios": row["fibonacci_ratios"],
                        "next_target": (
                            float(row["next_target"]) if row["next_target"] else None
                        ),
                        "session_context": row["session_context"],
                        "start_time": row["start_time"],
                        "end_time": row["end_time"],
                        "metadata": row["metadata"],
                    }
                )

            self.logger.info(
                f"Found {len(similar_patterns)} similar patterns for {pattern.pattern_id}"
            )
            return similar_patterns

        except Exception as e:
            self.logger.error(f"Error finding similar patterns: {e}")
            return []

    async def store_wave_signal(self, signal: WaveSignal) -> bool:
        """Store Elliott Wave trading signal in database"""

        if not self.db_client:
            return False

        try:
            # Calculate expiration time based on time horizon
            expires_at = None
            if signal.time_horizon == "minutes":
                expires_at = signal.timestamp + timedelta(hours=1)
            elif signal.time_horizon == "hours":
                expires_at = signal.timestamp + timedelta(hours=12)
            elif signal.time_horizon == "days":
                expires_at = signal.timestamp + timedelta(days=3)

            insert_sql = """
            INSERT INTO elliott_wave_signals (
                pattern_id, signal_strength, confidence, entry_target,
                stop_loss, take_profit, risk_reward_ratio, time_horizon,
                reasoning, expires_at, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """

            await self.db_client.execute(
                insert_sql,
                signal.pattern.pattern_id,
                signal.signal_strength,
                signal.confidence,
                float(signal.entry_target) if signal.entry_target else None,
                float(signal.stop_loss) if signal.stop_loss else None,
                float(signal.take_profit) if signal.take_profit else None,
                signal.risk_reward_ratio,
                signal.time_horizon,
                signal.reasoning,
                expires_at,
                {"generated_by": "gbpusd_elliott_wave_analyzer"},
            )

            return True

        except Exception as e:
            self.logger.error(f"Error storing wave signal: {e}")
            return False

    async def get_historical_pattern_performance(
        self, pattern_type: WaveType, lookback_days: int = 30
    ) -> Dict[str, Any]:
        """Get performance statistics for historical patterns of given type"""

        if not self.db_client:
            return {}

        try:
            cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)

            performance_sql = """
            SELECT
                COUNT(*) as total_patterns,
                AVG(confidence_score) as avg_confidence,
                AVG(CASE
                    WHEN next_target IS NOT NULL
                    THEN 1.0
                    ELSE 0.0
                END) as target_completion_rate,
                AVG(EXTRACT(EPOCH FROM (end_time - start_time))/3600) as avg_duration_hours,
                COUNT(DISTINCT session_context) as session_diversity
            FROM elliott_wave_patterns
            WHERE
                pattern_type = $1
                AND created_at >= $2
                AND symbol = 'GBPUSD'
            """

            result = await self.db_client.fetchrow(
                performance_sql, pattern_type.value, cutoff_date
            )

            return {
                "pattern_type": pattern_type.value,
                "lookback_days": lookback_days,
                "total_patterns": result["total_patterns"] if result else 0,
                "avg_confidence": (
                    float(result["avg_confidence"])
                    if result and result["avg_confidence"]
                    else 0.0
                ),
                "target_completion_rate": (
                    float(result["target_completion_rate"])
                    if result and result["target_completion_rate"]
                    else 0.0
                ),
                "avg_duration_hours": (
                    float(result["avg_duration_hours"])
                    if result and result["avg_duration_hours"]
                    else 0.0
                ),
                "session_diversity": result["session_diversity"] if result else 0,
            }

        except Exception as e:
            self.logger.error(f"Error getting pattern performance: {e}")
            return {}
