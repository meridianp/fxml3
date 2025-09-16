"""Sentiment-enhanced Elliott Wave pattern validator.

This module implements integration between sentiment analysis and Elliott Wave pattern validation,
using market sentiment data to validate or enhance confidence in detected patterns.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from fxml4.llm_integration.rag import RAG
from fxml4.llm_integration.sentiment_analysis import MarketSentimentAnalyzer
from fxml4.wave_analysis.elliott_wave import (
    ElliottWaveAnalyzer,
    ElliottWaveCount,
    ElliottWavePattern,
    WaveType,
)

logger = logging.getLogger(__name__)


class SentimentWaveValidator:
    """Validates Elliott Wave patterns using sentiment analysis.

    This class integrates market sentiment analysis with Elliott Wave pattern detection
    to provide enhanced pattern validation and confidence scoring.
    """

    def __init__(
        self,
        wave_analyzer: ElliottWaveAnalyzer,
        sentiment_analyzer: MarketSentimentAnalyzer,
        rag: Optional[RAG] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the sentiment-enhanced wave validator.

        Args:
            wave_analyzer: Elliott Wave analyzer component.
            sentiment_analyzer: Market sentiment analyzer component.
            rag: RAG system for knowledge-backed validation (optional).
            config: Configuration dictionary.
        """
        self.wave_analyzer = wave_analyzer
        self.sentiment_analyzer = sentiment_analyzer
        self.rag = rag
        self.config = config or {}

        # Configuration parameters
        self.sentiment_weight = self.config.get("sentiment_weight", 0.3)
        self.rag_weight = self.config.get("rag_weight", 0.3)
        self.wave_weight = self.config.get("wave_weight", 0.4)
        self.min_confidence = self.config.get("min_confidence", 0.6)

        # Sentiment-pattern correlations
        # Key: Wave type and position tuple (e.g., ('IMPULSE', 'START'))
        # Value: Expected sentiment (positive values mean bullish sentiment)
        self.expected_sentiment = {
            (WaveType.IMPULSE, "START"): 0.6,  # Strongly bullish at start of impulse
            (WaveType.IMPULSE, "MIDDLE"): 0.4,  # Moderately bullish during impulse
            (
                WaveType.IMPULSE,
                "END",
            ): 0.2,  # Weakly bullish at end of impulse (exhaustion)
            (
                WaveType.CORRECTION,
                "START",
            ): -0.3,  # Moderately bearish at start of correction
            (WaveType.CORRECTION, "MIDDLE"): -0.2,  # Slightly bearish during correction
            (WaveType.CORRECTION, "END"): 0.3,  # Turning bullish at end of correction
            (
                WaveType.DIAGONAL,
                "START",
            ): 0.3,  # Moderately bullish at start of diagonal
            (WaveType.DIAGONAL, "MIDDLE"): 0.1,  # Slightly bullish during diagonal
            (
                WaveType.DIAGONAL,
                "END",
            ): -0.2,  # Turning bearish at end of diagonal (often reversal)
            (
                WaveType.TRIANGLE,
                "START",
            ): 0.0,  # Neutral at start of triangle (consolidation)
            (WaveType.TRIANGLE, "MIDDLE"): 0.0,  # Neutral during triangle
            (
                WaveType.TRIANGLE,
                "END",
            ): 0.3,  # Turning bullish at end of triangle (breakout)
        }

        # Tolerance for sentiment matching
        self.sentiment_tolerance = self.config.get("sentiment_tolerance", 0.4)

        logger.info("Initialized SentimentWaveValidator")

    def validate_wave_pattern(
        self,
        pattern: ElliottWavePattern,
        price_data: pd.DataFrame,
        news_data: Optional[pd.DataFrame] = None,
        pattern_position: str = "END",  # START, MIDDLE, or END
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """Validate an Elliott Wave pattern using sentiment analysis.

        Args:
            pattern: The Elliott Wave pattern to validate.
            price_data: Price data containing the pattern.
            news_data: News data for sentiment analysis (optional).
            pattern_position: Position within the pattern (START, MIDDLE, END).

        Returns:
            Tuple of (is_valid, confidence_score, validation_details).
        """
        validation_details = {}

        try:
            # Step 1: Get base confidence from wave pattern
            base_confidence = pattern.confidence
            validation_details["wave_confidence"] = base_confidence

            # Step 2: Get sentiment data
            if news_data is None:
                # Get sentiment from price action if no news data
                sentiment_score = self._get_sentiment_from_price(price_data)
            else:
                # Get sentiment from news data
                sentiment_score = self.sentiment_analyzer.analyze_sentiment(news_data)

            validation_details["sentiment_score"] = sentiment_score

            # Step 3: Check if sentiment matches expected sentiment for this pattern and position
            pattern_key = (pattern.wave_type, pattern_position)
            expected_sentiment = self.expected_sentiment.get(pattern_key, 0)
            sentiment_diff = abs(sentiment_score - expected_sentiment)

            # Calculate sentiment confidence (1.0 if perfect match, decreasing as difference increases)
            sentiment_confidence = max(
                0, 1.0 - (sentiment_diff / self.sentiment_tolerance)
            )
            validation_details["sentiment_confidence"] = sentiment_confidence
            validation_details["expected_sentiment"] = expected_sentiment

            # Step 4: Use RAG for knowledge-backed validation if available
            rag_confidence = 0.5  # Default neutral value
            if self.rag:
                rag_confidence = self._get_rag_validation(
                    pattern, price_data, sentiment_score
                )

            validation_details["rag_confidence"] = rag_confidence

            # Step 5: Combine confidence scores with weights
            combined_confidence = (
                base_confidence * self.wave_weight
                + sentiment_confidence * self.sentiment_weight
                + rag_confidence * self.rag_weight
            )

            # Determine if pattern is valid based on minimum confidence threshold
            is_valid = combined_confidence >= self.min_confidence

            return is_valid, combined_confidence, validation_details

        except Exception as e:
            logger.exception("Error validating wave pattern: %s", e)
            return False, 0.0, {"error": str(e)}

    def _get_sentiment_from_price(self, price_data: pd.DataFrame) -> float:
        """Extract sentiment score from price action.

        This is a simplified approach when news data is not available.

        Args:
            price_data: Price data DataFrame.

        Returns:
            Sentiment score (-1 to 1, where 1 is most bullish).
        """
        try:
            # Use the most recent N periods
            recent_data = price_data.tail(20)

            # Calculate return
            returns = (recent_data["close"].pct_change() * 100).dropna()

            # Calculate momentum indicators if not in data
            if "rsi" not in recent_data.columns:
                # Simple RSI calculation (14-period)
                delta = recent_data["close"].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                recent_rsi = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
            else:
                recent_rsi = recent_data["rsi"].iloc[-1]

            # Get average volume change
            if "volume" in recent_data.columns:
                volume_change = recent_data["volume"].pct_change().mean()
            else:
                volume_change = 0

            # Get price trend (positive = bullish)
            price_trend = returns.mean()

            # Convert RSI to -1 to 1 scale (50 is neutral)
            rsi_score = (recent_rsi - 50) / 50

            # Volume factor (-1 to 1 scale, positive volume change is bullish in an up trend)
            volume_score = min(max(volume_change, -1), 1) * np.sign(price_trend)

            # Combine factors with different weights
            sentiment_score = (rsi_score * 0.7) + (volume_score * 0.3)

            # Ensure result is between -1 and 1
            sentiment_score = min(max(sentiment_score, -1.0), 1.0)

            return sentiment_score

        except Exception as e:
            logger.exception("Error calculating sentiment from price: %s", e)
            return 0.0  # Neutral sentiment if calculation fails

    def _get_rag_validation(
        self,
        pattern: ElliottWavePattern,
        price_data: pd.DataFrame,
        sentiment_score: float,
    ) -> float:
        """Get validation from the RAG system.

        Args:
            pattern: Elliott Wave pattern.
            price_data: Price data.
            sentiment_score: Current sentiment score.

        Returns:
            Confidence score from RAG (0 to 1).
        """
        try:
            # Create a detailed description of the pattern
            pattern_desc = pattern.to_dict()
            pattern_type = pattern.wave_type.value

            # Format recent price data
            recent_data = price_data.tail(10).copy()
            if isinstance(recent_data.index, pd.DatetimeIndex):
                recent_data.index = recent_data.index.strftime("%Y-%m-%d %H:%M")
            price_table = recent_data[["open", "high", "low", "close"]].to_string()

            # Create sentiment description
            if sentiment_score > 0.5:
                sentiment_desc = f"strongly bullish ({sentiment_score:.2f})"
            elif sentiment_score > 0.2:
                sentiment_desc = f"moderately bullish ({sentiment_score:.2f})"
            elif sentiment_score > -0.2:
                sentiment_desc = f"neutral ({sentiment_score:.2f})"
            elif sentiment_score > -0.5:
                sentiment_desc = f"moderately bearish ({sentiment_score:.2f})"
            else:
                sentiment_desc = f"strongly bearish ({sentiment_score:.2f})"

            # Craft query for RAG system
            query = f"""
            As an Elliott Wave expert, validate this {pattern_type} pattern:

            Pattern details: {pattern_desc}

            Recent price action:
            {price_table}

            Current market sentiment is {sentiment_desc}.

            Questions:
            1. Does this pattern adhere to Elliott Wave rules and guidelines?
            2. Does the market sentiment align with what you would expect for this pattern?
            3. What is your confidence level in this being a valid {pattern_type} pattern?

            Rate confidence from 0 to 1, where 1 is highest confidence.
            """

            # Get response from RAG
            response = self.rag.query(query)

            # Extract confidence from response
            import re

            # Try to find a direct confidence score
            confidence_pattern = r"confidence[:\s]+(\d+\.\d+)"
            match = re.search(confidence_pattern, response, re.IGNORECASE)
            if match:
                confidence = float(match.group(1))
                return max(0, min(1, confidence))

            # Try to find a percentage
            percentage_pattern = r"(\d+)%"
            match = re.search(percentage_pattern, response)
            if match:
                confidence = float(match.group(1)) / 100.0
                return max(0, min(1, confidence))

            # Default to a moderate confidence if we can't extract it
            return 0.7

        except Exception as e:
            logger.exception("Error getting RAG validation: %s", e)
            return 0.5  # Neutral confidence if RAG validation fails

    def analyze_with_sentiment(
        self,
        price_data: pd.DataFrame,
        news_data: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        """Analyze price data with sentiment-enhanced validation.

        Args:
            price_data: Price data for analysis.
            news_data: News data for sentiment analysis (optional).

        Returns:
            Dictionary with analysis results.
        """
        results = {
            "patterns": [],
            "validation": [],
            "combined_score": 0.0,
        }

        try:
            # Step 1: Perform Elliott Wave analysis
            wave_count = self.wave_analyzer.analyze(price_data)

            if not wave_count or not wave_count.waves:
                return results

            # Step 2: Get sentiment score
            if news_data is None:
                sentiment_score = self._get_sentiment_from_price(price_data)
            else:
                sentiment_score = self.sentiment_analyzer.analyze_sentiment(news_data)

            results["sentiment_score"] = sentiment_score

            # Step 3: Validate each wave pattern with sentiment
            validated_patterns = []
            for wave in wave_count.waves:
                # Skip very low confidence patterns
                if wave.confidence < 0.4:
                    continue

                # Determine pattern position
                if wave.position:
                    pattern_position = wave.position.value
                else:
                    pattern_position = "END"  # Default to end if not specified

                # Validate pattern
                is_valid, confidence, details = self.validate_wave_pattern(
                    wave, price_data, news_data, pattern_position
                )

                # Add to results
                validated_patterns.append(
                    {
                        "pattern": wave.to_dict(),
                        "is_valid": is_valid,
                        "confidence": confidence,
                        "details": details,
                    }
                )

            results["patterns"] = [wave.to_dict() for wave in wave_count.waves]
            results["validation"] = validated_patterns

            # Calculate combined confidence score (average of valid patterns)
            valid_patterns = [p for p in validated_patterns if p["is_valid"]]
            if valid_patterns:
                results["combined_score"] = sum(
                    p["confidence"] for p in valid_patterns
                ) / len(valid_patterns)

            return results

        except Exception as e:
            logger.exception("Error in sentiment-enhanced wave analysis: %s", e)
            return results
