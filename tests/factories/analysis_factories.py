"""
Analysis and Pattern Factory Definitions
========================================

Factory Boy factories for creating Elliott Wave patterns, technical indicators,
market regime data, and sentiment analysis artifacts for testing.
"""

import json
import random
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List

import factory
import factory.fuzzy
from faker import Faker

fake = Faker()


class WavePatternFactory(factory.Factory):
    """
    Factory for creating Elliott Wave patterns with realistic wave structures.

    Generates Elliott Wave analysis data including wave counts, degrees,
    Fibonacci relationships, and pattern validation.
    """

    class Meta:
        model = dict

    # Pattern identification
    pattern_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    symbol = factory.fuzzy.FuzzyChoice(["EURUSD", "GBPUSD", "USDJPY", "USDCHF"])
    timeframe = factory.fuzzy.FuzzyChoice(["1h", "4h", "1d", "1w"])

    # Wave pattern details
    wave_type = factory.fuzzy.FuzzyChoice(["impulse", "corrective"])
    pattern_name = factory.LazyAttribute(
        lambda obj: (
            fake.random_element(
                [
                    "Five Wave Impulse",
                    "Three Wave Correction",
                    "ABC Correction",
                    "Double Zigzag",
                    "Triple Zigzag",
                    "Flat Correction",
                    "Triangle",
                    "Expanding Triangle",
                    "Contracting Triangle",
                ]
            )
            if obj.wave_type == "corrective"
            else fake.random_element(
                [
                    "Impulse Wave",
                    "Extended Wave 1",
                    "Extended Wave 3",
                    "Extended Wave 5",
                    "Leading Diagonal",
                    "Ending Diagonal",
                ]
            )
        )
    )

    # Wave degree (Elliott Wave degree hierarchy)
    wave_degree = factory.fuzzy.FuzzyChoice(
        [
            "Grand Supercycle",
            "Supercycle",
            "Cycle",
            "Primary",
            "Intermediate",
            "Minor",
            "Minute",
            "Minuette",
            "Subminuette",
        ]
    )

    # Wave structure
    wave_count = factory.LazyAttribute(
        lambda obj: 5 if obj.wave_type == "impulse" else fake.random_int(3, 9)
    )
    current_wave = factory.LazyAttribute(lambda obj: fake.random_int(1, obj.wave_count))

    # Price points (wave pivots)
    start_price = factory.fuzzy.FuzzyDecimal(1.0000, 1.5000, 4)
    end_price = factory.LazyAttribute(
        lambda obj: obj.start_price + Decimal(str(fake.random.uniform(-0.0200, 0.0200)))
    )

    # Wave pivot points (simplified for 5-wave structure)
    wave_pivots = factory.LazyAttribute(
        lambda obj: [
            {
                "wave": i,
                "price": obj.start_price
                + Decimal(str(fake.random.uniform(-0.0100, 0.0100))),
                "time": fake.date_time_between(start_date="-30d", end_date="now"),
            }
            for i in range(1, obj.wave_count + 1)
        ]
    )

    # Fibonacci relationships
    fib_retracements = factory.LazyFunction(
        lambda: {
            "23.6%": Decimal(str(fake.random.uniform(0.225, 0.247))),
            "38.2%": Decimal(str(fake.random.uniform(0.372, 0.392))),
            "50.0%": Decimal(str(fake.random.uniform(0.490, 0.510))),
            "61.8%": Decimal(str(fake.random.uniform(0.608, 0.628))),
            "78.6%": Decimal(str(fake.random.uniform(0.776, 0.796))),
        }
    )

    fib_extensions = factory.LazyFunction(
        lambda: {
            "127.2%": Decimal(str(fake.random.uniform(1.262, 1.282))),
            "161.8%": Decimal(str(fake.random.uniform(1.608, 1.628))),
            "200.0%": Decimal(str(fake.random.uniform(1.990, 2.010))),
            "261.8%": Decimal(str(fake.random.uniform(2.608, 2.628))),
        }
    )

    # Pattern validation
    confidence_score = factory.fuzzy.FuzzyDecimal(0.3, 0.95, 2)
    pattern_complete = factory.fuzzy.FuzzyChoice([True, False])
    validation_rules_passed = factory.fuzzy.FuzzyInteger(5, 15)
    validation_rules_total = factory.fuzzy.FuzzyInteger(15, 20)

    # Analysis metadata
    identified_at = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-7d", end_date="now")
    )
    last_updated = factory.LazyAttribute(
        lambda obj: obj.identified_at + timedelta(hours=fake.random_int(1, 48))
    )
    analyst = factory.fuzzy.FuzzyChoice(
        ["ML_Model", "Pattern_Recognition", "LLM_Analysis"]
    )

    # Technical context
    trend_direction = factory.fuzzy.FuzzyChoice(["bullish", "bearish", "sideways"])
    market_structure = factory.fuzzy.FuzzyChoice(
        ["trending", "corrective", "consolidation"]
    )
    volume_confirmation = factory.fuzzy.FuzzyChoice([True, False])

    # Time analysis
    time_duration_days = factory.LazyAttribute(
        lambda obj: (
            (obj.wave_pivots[-1]["time"] - obj.wave_pivots[0]["time"]).days
            if obj.wave_pivots
            else fake.random_int(1, 30)
        )
    )

    class Params:
        # Traits for different pattern types
        impulse_wave = factory.Trait(
            wave_type="impulse",
            wave_count=5,
            pattern_name="Five Wave Impulse",
            confidence_score=factory.fuzzy.FuzzyDecimal(0.6, 0.9, 2),
        )

        correction_wave = factory.Trait(
            wave_type="corrective",
            wave_count=3,
            pattern_name="ABC Correction",
            confidence_score=factory.fuzzy.FuzzyDecimal(0.4, 0.8, 2),
        )

        high_confidence = factory.Trait(
            confidence_score=factory.fuzzy.FuzzyDecimal(0.8, 0.95, 2),
            validation_rules_passed=factory.fuzzy.FuzzyInteger(12, 18),
            volume_confirmation=True,
            pattern_complete=True,
        )


class TechnicalIndicatorFactory(factory.Factory):
    """
    Factory for creating technical indicator calculations and signals.
    """

    class Meta:
        model = dict

    # Indicator identification
    indicator_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    indicator_name = factory.fuzzy.FuzzyChoice(
        [
            "SMA",
            "EMA",
            "RSI",
            "MACD",
            "Bollinger Bands",
            "ATR",
            "Stochastic",
            "Williams %R",
            "CCI",
            "ADX",
            "Parabolic SAR",
        ]
    )
    symbol = factory.fuzzy.FuzzyChoice(["EURUSD", "GBPUSD", "USDJPY"])
    timeframe = factory.fuzzy.FuzzyChoice(["5m", "15m", "1h", "4h", "1d"])

    # Indicator parameters
    period = factory.LazyAttribute(
        lambda obj: {
            "SMA": fake.random_element([10, 20, 50, 100, 200]),
            "EMA": fake.random_element([12, 26, 50, 100]),
            "RSI": fake.random_element([14, 21]),
            "ATR": fake.random_element([14, 20]),
            "Stochastic": fake.random_element([14, 21]),
            "ADX": fake.random_element([14, 20]),
        }.get(obj.indicator_name, 14)
    )

    # Current values
    current_value = factory.LazyAttribute(
        lambda obj: {
            "SMA": fake.random.uniform(1.0000, 1.2000),
            "EMA": fake.random.uniform(1.0000, 1.2000),
            "RSI": fake.random.uniform(20.0, 80.0),
            "ATR": fake.random.uniform(0.0050, 0.0200),
            "Stochastic": fake.random.uniform(20.0, 80.0),
            "Williams %R": fake.random.uniform(-80.0, -20.0),
            "CCI": fake.random.uniform(-200.0, 200.0),
            "ADX": fake.random.uniform(20.0, 60.0),
        }.get(obj.indicator_name, fake.random.uniform(0.0, 100.0))
    )

    # Historical values (last 5 periods)
    historical_values = factory.LazyAttribute(
        lambda obj: [
            obj.current_value + fake.random.uniform(-0.1, 0.1) * obj.current_value
            for _ in range(5)
        ]
    )

    # Signal analysis
    signal_type = factory.fuzzy.FuzzyChoice(["buy", "sell", "neutral"])
    signal_strength = factory.fuzzy.FuzzyDecimal(0.1, 1.0, 2)

    # Overbought/Oversold levels (for oscillators)
    overbought_level = factory.LazyAttribute(
        lambda obj: {
            "RSI": 70.0,
            "Stochastic": 80.0,
            "Williams %R": -20.0,
            "CCI": 100.0,
        }.get(obj.indicator_name, None)
    )

    oversold_level = factory.LazyAttribute(
        lambda obj: {
            "RSI": 30.0,
            "Stochastic": 20.0,
            "Williams %R": -80.0,
            "CCI": -100.0,
        }.get(obj.indicator_name, None)
    )

    # Multi-value indicators (like MACD, Bollinger Bands)
    secondary_value = factory.LazyAttribute(
        lambda obj: {
            "MACD": fake.random.uniform(-0.0020, 0.0020),  # MACD Signal
            "Bollinger Bands": obj.current_value
            + fake.random.uniform(0.0050, 0.0150),  # Upper Band
        }.get(obj.indicator_name, None)
    )

    tertiary_value = factory.LazyAttribute(
        lambda obj: {
            "MACD": fake.random.uniform(-0.0010, 0.0010),  # MACD Histogram
            "Bollinger Bands": obj.current_value
            - fake.random.uniform(0.0050, 0.0150),  # Lower Band
        }.get(obj.indicator_name, None)
    )

    # Calculation timestamp
    calculated_at = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-1d", end_date="now")
    )


class MarketRegimeFactory(factory.Factory):
    """
    Factory for creating market regime classifications and transitions.
    """

    class Meta:
        model = dict

    # Regime identification
    regime_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    symbol = factory.fuzzy.FuzzyChoice(["EURUSD", "GBPUSD", "USDJPY"])
    timeframe = factory.fuzzy.FuzzyChoice(["1h", "4h", "1d"])

    # Regime classification
    current_regime = factory.fuzzy.FuzzyChoice(
        ["trending_up", "trending_down", "sideways", "volatile"]
    )
    regime_strength = factory.fuzzy.FuzzyDecimal(0.3, 1.0, 2)
    regime_confidence = factory.fuzzy.FuzzyDecimal(0.5, 0.95, 2)

    # Regime characteristics
    volatility_level = factory.fuzzy.FuzzyChoice(["low", "medium", "high", "extreme"])
    trend_strength = factory.fuzzy.FuzzyDecimal(0.0, 1.0, 2)
    mean_reversion_tendency = factory.fuzzy.FuzzyDecimal(0.0, 1.0, 2)

    # Quantitative measures
    volatility_value = factory.fuzzy.FuzzyDecimal(0.005, 0.030, 4)  # Daily volatility
    trend_slope = factory.fuzzy.FuzzyDecimal(-0.002, 0.002, 6)  # Price slope per period
    autocorrelation = factory.fuzzy.FuzzyDecimal(-0.5, 0.8, 2)  # Return autocorrelation

    # Regime duration
    regime_start = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-30d", end_date="-1d")
    )
    regime_duration_hours = factory.LazyAttribute(
        lambda obj: (datetime.utcnow() - obj.regime_start).total_seconds() / 3600
    )

    # Previous regime
    previous_regime = factory.fuzzy.FuzzyChoice(
        ["trending_up", "trending_down", "sideways", "volatile"]
    )
    regime_transition_probability = factory.LazyFunction(
        lambda: {
            "trending_up": fake.random.uniform(0.05, 0.30),
            "trending_down": fake.random.uniform(0.05, 0.30),
            "sideways": fake.random.uniform(0.20, 0.60),
            "volatile": fake.random.uniform(0.10, 0.40),
        }
    )

    # Market microstructure
    average_spread = factory.fuzzy.FuzzyDecimal(0.0001, 0.0005, 5)
    bid_ask_volatility = factory.fuzzy.FuzzyDecimal(0.0001, 0.0003, 5)
    order_flow_imbalance = factory.fuzzy.FuzzyDecimal(-0.5, 0.5, 2)

    # Machine learning features
    regime_features = factory.LazyFunction(
        lambda: {
            "return_variance": fake.random.uniform(0.0001, 0.001),
            "volume_trend": fake.random.uniform(-0.2, 0.2),
            "price_momentum": fake.random.uniform(-0.1, 0.1),
            "mean_reversion_speed": fake.random.uniform(0.1, 0.8),
            "jump_frequency": fake.random.uniform(0.0, 0.1),
        }
    )

    # Analysis metadata
    identified_at = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-1h", end_date="now")
    )
    model_version = factory.Sequence(
        lambda n: f"regime_model_v{n}.{fake.random_int(0, 9)}"
    )


class SentimentDataFactory(factory.Factory):
    """
    Factory for creating market sentiment analysis data from various sources.
    """

    class Meta:
        model = dict

    # Sentiment identification
    sentiment_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    symbol = factory.fuzzy.FuzzyChoice(["EURUSD", "GBPUSD", "USDJPY"])
    timestamp = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-24h", end_date="now")
    )

    # Sentiment sources
    data_source = factory.fuzzy.FuzzyChoice(
        [
            "Twitter",
            "Reddit",
            "News Articles",
            "Economic Calendar",
            "Central Bank Communications",
            "Analyst Reports",
            "COT Report",
        ]
    )

    # Sentiment scores
    overall_sentiment = factory.fuzzy.FuzzyDecimal(
        -1.0, 1.0, 2
    )  # -1 (bearish) to +1 (bullish)
    sentiment_strength = factory.fuzzy.FuzzyDecimal(0.1, 1.0, 2)
    confidence = factory.fuzzy.FuzzyDecimal(0.3, 0.9, 2)

    # Detailed sentiment breakdown
    bullish_mentions = factory.fuzzy.FuzzyInteger(0, 100)
    bearish_mentions = factory.fuzzy.FuzzyInteger(0, 100)
    neutral_mentions = factory.fuzzy.FuzzyInteger(0, 50)
    total_mentions = factory.LazyAttribute(
        lambda obj: obj.bullish_mentions + obj.bearish_mentions + obj.neutral_mentions
    )

    # Sentiment categories
    economic_sentiment = factory.fuzzy.FuzzyDecimal(-1.0, 1.0, 2)
    technical_sentiment = factory.fuzzy.FuzzyDecimal(-1.0, 1.0, 2)
    geopolitical_sentiment = factory.fuzzy.FuzzyDecimal(-1.0, 1.0, 2)
    central_bank_sentiment = factory.fuzzy.FuzzyDecimal(-1.0, 1.0, 2)

    # Key sentiment drivers
    top_keywords = factory.LazyFunction(
        lambda: fake.random_elements(
            [
                "inflation",
                "interest_rates",
                "gdp",
                "unemployment",
                "fed",
                "ecb",
                "brexit",
                "trade_war",
                "earnings",
                "recession",
                "recovery",
                "volatility",
            ],
            length=fake.random_int(3, 6),
        )
    )

    # News sentiment
    news_headline = factory.Faker("sentence", nb_words=10)
    news_sentiment_score = factory.fuzzy.FuzzyDecimal(-1.0, 1.0, 2)
    news_impact_score = factory.fuzzy.FuzzyChoice(["low", "medium", "high", "critical"])

    # Social media metrics
    retweets = (
        factory.fuzzy.FuzzyInteger(0, 1000) if fake.random.random() > 0.5 else None
    )
    likes = factory.fuzzy.FuzzyInteger(0, 5000) if fake.random.random() > 0.5 else None
    engagement_rate = factory.fuzzy.FuzzyDecimal(0.01, 0.15, 3)

    # Analyst sentiment
    analyst_rating = factory.fuzzy.FuzzyChoice(
        ["Strong Sell", "Sell", "Hold", "Buy", "Strong Buy"]
    )
    price_target = factory.fuzzy.FuzzyDecimal(1.0000, 1.3000, 4)
    target_horizon_days = factory.fuzzy.FuzzyInteger(30, 365)

    # Sentiment momentum
    sentiment_change_24h = factory.fuzzy.FuzzyDecimal(-0.5, 0.5, 2)
    sentiment_volatility = factory.fuzzy.FuzzyDecimal(0.1, 1.0, 2)

    class Params:
        # Traits for different sentiment scenarios
        bullish_sentiment = factory.Trait(
            overall_sentiment=factory.fuzzy.FuzzyDecimal(0.3, 1.0, 2),
            bullish_mentions=factory.fuzzy.FuzzyInteger(50, 150),
            bearish_mentions=factory.fuzzy.FuzzyInteger(0, 30),
            analyst_rating=factory.fuzzy.FuzzyChoice(["Buy", "Strong Buy"]),
        )

        bearish_sentiment = factory.Trait(
            overall_sentiment=factory.fuzzy.FuzzyDecimal(-1.0, -0.3, 2),
            bullish_mentions=factory.fuzzy.FuzzyInteger(0, 30),
            bearish_mentions=factory.fuzzy.FuzzyInteger(50, 150),
            analyst_rating=factory.fuzzy.FuzzyChoice(["Sell", "Strong Sell"]),
        )

        high_confidence = factory.Trait(
            confidence=factory.fuzzy.FuzzyDecimal(0.7, 0.9, 2),
            total_mentions=factory.fuzzy.FuzzyInteger(200, 500),
            sentiment_strength=factory.fuzzy.FuzzyDecimal(0.6, 1.0, 2),
        )

        news_driven = factory.Trait(
            data_source="News Articles",
            news_impact_score="high",
            sentiment_strength=factory.fuzzy.FuzzyDecimal(0.7, 1.0, 2),
        )


class PatternRecognitionFactory(factory.Factory):
    """
    Factory for creating chart pattern recognition results.
    """

    class Meta:
        model = dict

    # Pattern identification
    pattern_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    symbol = factory.fuzzy.FuzzyChoice(["EURUSD", "GBPUSD", "USDJPY"])
    timeframe = factory.fuzzy.FuzzyChoice(["15m", "1h", "4h", "1d"])

    # Pattern details
    pattern_type = factory.fuzzy.FuzzyChoice(
        [
            "Head and Shoulders",
            "Inverse Head and Shoulders",
            "Double Top",
            "Double Bottom",
            "Triple Top",
            "Triple Bottom",
            "Ascending Triangle",
            "Descending Triangle",
            "Symmetrical Triangle",
            "Flag",
            "Pennant",
            "Wedge",
            "Cup and Handle",
            "Rectangle",
            "Channel",
            "Support",
            "Resistance",
        ]
    )

    pattern_direction = factory.LazyAttribute(
        lambda obj: {
            "Head and Shoulders": "bearish",
            "Inverse Head and Shoulders": "bullish",
            "Double Top": "bearish",
            "Double Bottom": "bullish",
            "Ascending Triangle": "bullish",
            "Descending Triangle": "bearish",
            "Cup and Handle": "bullish",
        }.get(obj.pattern_type, fake.random_element(["bullish", "bearish", "neutral"]))
    )

    # Pattern geometry
    pattern_height = factory.fuzzy.FuzzyDecimal(0.0050, 0.0300, 4)  # Price range
    pattern_width_hours = factory.fuzzy.FuzzyInteger(6, 240)  # Time duration
    breakout_level = factory.fuzzy.FuzzyDecimal(1.0500, 1.2000, 4)

    # Pattern validation
    confidence_score = factory.fuzzy.FuzzyDecimal(0.4, 0.9, 2)
    volume_confirmation = factory.fuzzy.FuzzyChoice([True, False])
    pattern_complete = factory.fuzzy.FuzzyChoice([True, False])

    # Target projections
    price_target = factory.LazyAttribute(
        lambda obj: obj.breakout_level
        + (
            obj.pattern_height
            if obj.pattern_direction == "bullish"
            else -obj.pattern_height
        )
    )
    target_probability = factory.fuzzy.FuzzyDecimal(0.3, 0.8, 2)

    # Risk management
    stop_loss_level = factory.LazyAttribute(
        lambda obj: obj.breakout_level
        - (
            obj.pattern_height * Decimal("0.3")
            if obj.pattern_direction == "bullish"
            else obj.pattern_height * Decimal("0.3")
        )
    )
    risk_reward_ratio = factory.LazyAttribute(
        lambda obj: (
            abs(obj.price_target - obj.breakout_level)
            / abs(obj.stop_loss_level - obj.breakout_level)
            if obj.stop_loss_level != obj.breakout_level
            else Decimal("0")
        )
    )

    # Pattern recognition metadata
    detected_at = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-24h", end_date="now")
    )
    detection_method = factory.fuzzy.FuzzyChoice(
        ["ML_Model", "Technical_Analysis", "Hybrid"]
    )
    last_updated = factory.LazyAttribute(
        lambda obj: obj.detected_at + timedelta(hours=1)
    )

    class Params:
        # Traits for different pattern scenarios
        breakout_pattern = factory.Trait(
            pattern_complete=True,
            volume_confirmation=True,
            confidence_score=factory.fuzzy.FuzzyDecimal(0.7, 0.9, 2),
            target_probability=factory.fuzzy.FuzzyDecimal(0.6, 0.8, 2),
        )

        developing_pattern = factory.Trait(
            pattern_complete=False,
            confidence_score=factory.fuzzy.FuzzyDecimal(0.4, 0.7, 2),
            volume_confirmation=factory.fuzzy.FuzzyChoice([True, False]),
        )
