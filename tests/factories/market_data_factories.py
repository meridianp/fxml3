"""
Market Data Factory Definitions
==============================

Factory Boy factories for creating market data including OHLCV candlesticks,
tick data, market sessions, and related time-series data for testing.
"""

import random
from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import Any, Dict, List

import factory
import factory.fuzzy
import pandas as pd
from faker import Faker

fake = Faker()


class MarketDataFactory(factory.Factory):
    """
    Factory for creating OHLCV market data with realistic price movements.

    Generates candlestick data with proper OHLC relationships, realistic
    volume patterns, and configurable market regimes.
    """

    class Meta:
        model = dict

    # Basic identification
    symbol = factory.fuzzy.FuzzyChoice(
        ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD"]
    )
    timeframe = factory.fuzzy.FuzzyChoice(["1m", "5m", "15m", "30m", "1h", "4h", "1d"])

    # Timestamp
    timestamp = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-30d", end_date="now")
    )

    # Price data - Open price as base
    open_price = factory.fuzzy.FuzzyDecimal(1.0000, 1.5000, 4)

    # High price (must be >= open)
    high_price = factory.LazyAttribute(
        lambda obj: obj.open_price + Decimal(str(fake.random.uniform(0.0000, 0.0050)))
    )

    # Low price (must be <= open)
    low_price = factory.LazyAttribute(
        lambda obj: obj.open_price - Decimal(str(fake.random.uniform(0.0000, 0.0050)))
    )

    # Close price (between high and low)
    close_price = factory.LazyAttribute(
        lambda obj: obj.low_price
        + (Decimal(str(fake.random.uniform(0, 1))) * (obj.high_price - obj.low_price))
    )

    # Volume with realistic patterns
    volume = factory.LazyAttribute(
        lambda obj: {
            "1m": fake.random_int(100, 1000),
            "5m": fake.random_int(500, 5000),
            "15m": fake.random_int(1500, 15000),
            "30m": fake.random_int(3000, 30000),
            "1h": fake.random_int(6000, 60000),
            "4h": fake.random_int(20000, 200000),
            "1d": fake.random_int(100000, 1000000),
        }.get(obj.timeframe, 10000)
    )

    # Technical indicators (computed)
    sma_20 = factory.LazyAttribute(lambda obj: obj.close_price)  # Simplified
    ema_12 = factory.LazyAttribute(lambda obj: obj.close_price)
    rsi = factory.fuzzy.FuzzyDecimal(20.0, 80.0, 2)

    # Spread and market microstructure
    bid = factory.LazyAttribute(
        lambda obj: obj.close_price
        - (Decimal("0.0001") if "JPY" not in obj.symbol else Decimal("0.01"))
    )
    ask = factory.LazyAttribute(
        lambda obj: obj.close_price
        + (Decimal("0.0001") if "JPY" not in obj.symbol else Decimal("0.01"))
    )
    spread = factory.LazyAttribute(lambda obj: obj.ask - obj.bid)

    # Market session data
    session = factory.LazyAttribute(
        lambda obj: {
            0: "Sydney",
            1: "Sydney",
            2: "Sydney",
            3: "Sydney",
            4: "Sydney",
            5: "Sydney",
            6: "Tokyo",
            7: "Tokyo",
            8: "Tokyo",
            9: "Tokyo",
            10: "Tokyo",
            11: "Tokyo",
            12: "London",
            13: "London",
            14: "London",
            15: "London",
            16: "London",
            17: "London",
            18: "New York",
            19: "New York",
            20: "New York",
            21: "New York",
            22: "New York",
            23: "New York",
        }.get(obj.timestamp.hour, "London")
    )

    # Quality and completeness flags
    is_complete = True
    has_gaps = False
    data_source = factory.fuzzy.FuzzyChoice(
        ["IB", "Polygon", "FXCM", "Yahoo", "Alpha Vantage"]
    )

    class Params:
        # Traits for different market conditions
        trending_up = factory.Trait(
            close_price=factory.LazyAttribute(
                lambda obj: obj.open_price
                + Decimal(str(fake.random.uniform(0.0010, 0.0050)))
            ),
            high_price=factory.LazyAttribute(
                lambda obj: max(obj.open_price, obj.close_price)
                + Decimal(str(fake.random.uniform(0.0005, 0.0020)))
            ),
            low_price=factory.LazyAttribute(
                lambda obj: min(obj.open_price, obj.close_price)
                - Decimal(str(fake.random.uniform(0.0000, 0.0010)))
            ),
        )

        trending_down = factory.Trait(
            close_price=factory.LazyAttribute(
                lambda obj: obj.open_price
                - Decimal(str(fake.random.uniform(0.0010, 0.0050)))
            ),
            high_price=factory.LazyAttribute(
                lambda obj: max(obj.open_price, obj.close_price)
                + Decimal(str(fake.random.uniform(0.0000, 0.0010)))
            ),
            low_price=factory.LazyAttribute(
                lambda obj: min(obj.open_price, obj.close_price)
                - Decimal(str(fake.random.uniform(0.0005, 0.0020)))
            ),
        )

        sideways = factory.Trait(
            close_price=factory.LazyAttribute(
                lambda obj: obj.open_price
                + Decimal(str(fake.random.uniform(-0.0010, 0.0010)))
            )
        )

        high_volatility = factory.Trait(
            high_price=factory.LazyAttribute(
                lambda obj: obj.open_price
                + Decimal(str(fake.random.uniform(0.0020, 0.0100)))
            ),
            low_price=factory.LazyAttribute(
                lambda obj: obj.open_price
                - Decimal(str(fake.random.uniform(0.0020, 0.0100)))
            ),
            volume=factory.LazyAttribute(lambda obj: obj.volume * 3),
        )


class CandlestickFactory(factory.Factory):
    """
    Factory for creating individual candlestick data with enhanced features.
    """

    class Meta:
        model = dict

    # Inherit basic structure from MarketDataFactory but add candlestick-specific features
    symbol = factory.fuzzy.FuzzyChoice(["EURUSD", "GBPUSD", "USDJPY"])
    timestamp = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-7d", end_date="now")
    )
    timeframe = factory.fuzzy.FuzzyChoice(["1m", "5m", "15m", "1h", "4h"])

    # OHLCV with proper relationships
    open_price = factory.fuzzy.FuzzyDecimal(1.0500, 1.1500, 4)
    high_price = factory.LazyAttribute(
        lambda obj: obj.open_price + Decimal(str(abs(fake.random.gauss(0, 0.0020))))
    )
    low_price = factory.LazyAttribute(
        lambda obj: obj.open_price - Decimal(str(abs(fake.random.gauss(0, 0.0020))))
    )
    close_price = factory.LazyAttribute(
        lambda obj: Decimal(
            str(fake.random.uniform(float(obj.low_price), float(obj.high_price)))
        )
    )
    volume = factory.fuzzy.FuzzyInteger(1000, 50000)

    # Candlestick pattern classification
    body_size = factory.LazyAttribute(lambda obj: abs(obj.close_price - obj.open_price))
    upper_shadow = factory.LazyAttribute(
        lambda obj: obj.high_price - max(obj.open_price, obj.close_price)
    )
    lower_shadow = factory.LazyAttribute(
        lambda obj: min(obj.open_price, obj.close_price) - obj.low_price
    )
    is_bullish = factory.LazyAttribute(lambda obj: obj.close_price > obj.open_price)

    # Pattern identification
    is_doji = factory.LazyAttribute(lambda obj: obj.body_size < Decimal("0.0005"))
    is_hammer = factory.LazyAttribute(
        lambda obj: obj.lower_shadow > obj.body_size * 2
        and obj.upper_shadow < obj.body_size
    )
    is_shooting_star = factory.LazyAttribute(
        lambda obj: obj.upper_shadow > obj.body_size * 2
        and obj.lower_shadow < obj.body_size
    )


class TickDataFactory(factory.Factory):
    """
    Factory for creating tick-level market data with bid/ask quotes.
    """

    class Meta:
        model = dict

    # Basic identification
    symbol = factory.fuzzy.FuzzyChoice(["EURUSD", "GBPUSD", "USDJPY"])
    timestamp = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-1d", end_date="now")
    )

    # Bid/Ask pricing
    bid_price = factory.fuzzy.FuzzyDecimal(1.0500, 1.1500, 5)
    ask_price = factory.LazyAttribute(
        lambda obj: obj.bid_price + Decimal(str(fake.random.uniform(0.00005, 0.00020)))
    )

    # Quote sizes
    bid_size = factory.fuzzy.FuzzyDecimal(1.0, 10.0, 2)
    ask_size = factory.fuzzy.FuzzyDecimal(1.0, 10.0, 2)

    # Market microstructure
    spread = factory.LazyAttribute(lambda obj: obj.ask_price - obj.bid_price)
    mid_price = factory.LazyAttribute(lambda obj: (obj.bid_price + obj.ask_price) / 2)

    # Tick metadata
    tick_id = factory.Sequence(lambda n: n)
    exchange = factory.fuzzy.FuzzyChoice(["EBS", "Reuters", "Currenex", "FXAll"])
    is_indicative = factory.fuzzy.FuzzyChoice([True, False])


class MarketSessionFactory(factory.Factory):
    """
    Factory for creating market session data with session-specific characteristics.
    """

    class Meta:
        model = dict

    # Session identification
    session_name = factory.fuzzy.FuzzyChoice(["Sydney", "Tokyo", "London", "New York"])
    session_date = factory.LazyFunction(
        lambda: fake.date_between(start_date="-30d", end_date="today")
    )

    # Session timing
    start_time = factory.LazyAttribute(
        lambda obj: {
            "Sydney": time(22, 0),  # 22:00 UTC
            "Tokyo": time(0, 0),  # 00:00 UTC
            "London": time(8, 0),  # 08:00 UTC
            "New York": time(13, 0),  # 13:00 UTC
        }[obj.session_name]
    )

    end_time = factory.LazyAttribute(
        lambda obj: {
            "Sydney": time(7, 0),  # 07:00 UTC next day
            "Tokyo": time(9, 0),  # 09:00 UTC
            "London": time(17, 0),  # 17:00 UTC
            "New York": time(22, 0),  # 22:00 UTC
        }[obj.session_name]
    )

    # Session characteristics
    is_active = True
    average_volume = factory.LazyAttribute(
        lambda obj: {
            "Sydney": fake.random_int(50000, 150000),
            "Tokyo": fake.random_int(200000, 500000),
            "London": fake.random_int(800000, 1500000),  # Most active
            "New York": fake.random_int(600000, 1200000),
        }[obj.session_name]
    )

    average_volatility = factory.LazyAttribute(
        lambda obj: {
            "Sydney": Decimal(str(fake.random.uniform(0.005, 0.015))),
            "Tokyo": Decimal(str(fake.random.uniform(0.008, 0.020))),
            "London": Decimal(str(fake.random.uniform(0.015, 0.035))),  # Most volatile
            "New York": Decimal(str(fake.random.uniform(0.012, 0.028))),
        }[obj.session_name]
    )

    # Major currency pair activity
    primary_pairs = factory.LazyAttribute(
        lambda obj: {
            "Sydney": ["AUDUSD", "NZDUSD", "AUDJPY"],
            "Tokyo": ["USDJPY", "EURJPY", "GBPJPY"],
            "London": ["EURUSD", "GBPUSD", "EURGBP"],
            "New York": ["EURUSD", "GBPUSD", "USDCAD"],
        }[obj.session_name]
    )


class MarketDataBatchFactory(factory.Factory):
    """
    Factory for creating batches of related market data for testing scenarios.
    """

    class Meta:
        model = dict

    # Batch metadata
    batch_id = factory.Sequence(lambda n: f"BATCH_{n:06d}")
    symbol = factory.fuzzy.FuzzyChoice(["EURUSD", "GBPUSD", "USDJPY"])
    timeframe = factory.fuzzy.FuzzyChoice(["1m", "5m", "15m", "1h"])
    start_date = factory.LazyFunction(
        lambda: fake.date_between(start_date="-30d", end_date="-7d")
    )
    end_date = factory.LazyAttribute(lambda obj: obj.start_date + timedelta(days=7))

    # Data generation parameters
    regime = factory.fuzzy.FuzzyChoice(
        ["trending_up", "trending_down", "sideways", "volatile"]
    )
    volatility_factor = factory.fuzzy.FuzzyDecimal(0.5, 2.0, 1)
    volume_factor = factory.fuzzy.FuzzyDecimal(0.5, 2.0, 1)

    # Batch characteristics
    total_candles = factory.LazyAttribute(
        lambda obj: {
            "1m": int((obj.end_date - obj.start_date).total_seconds() / 60),
            "5m": int((obj.end_date - obj.start_date).total_seconds() / 300),
            "15m": int((obj.end_date - obj.start_date).total_seconds() / 900),
            "1h": int((obj.end_date - obj.start_date).total_seconds() / 3600),
        }.get(obj.timeframe, 1440)
    )

    completeness = factory.fuzzy.FuzzyDecimal(0.85, 1.0, 2)  # 85-100% data completeness
    quality_score = factory.fuzzy.FuzzyDecimal(0.80, 1.0, 2)

    # Method to generate actual data series
    def generate_series(self) -> List[Dict]:
        """Generate a series of market data based on batch parameters."""
        data_points = []
        current_time = datetime.combine(self.start_date, time(0, 0))
        current_price = Decimal("1.1000")  # Starting price

        timeframe_minutes = {"1m": 1, "5m": 5, "15m": 15, "1h": 60}.get(
            self.timeframe, 5
        )

        for i in range(self.total_candles):
            # Generate price movement based on regime
            if self.regime == "trending_up":
                price_change = fake.random.uniform(0.0000, 0.0020)
            elif self.regime == "trending_down":
                price_change = fake.random.uniform(-0.0020, 0.0000)
            elif self.regime == "volatile":
                price_change = fake.random.uniform(-0.0030, 0.0030)
            else:  # sideways
                price_change = fake.random.uniform(-0.0010, 0.0010)

            price_change *= self.volatility_factor
            current_price += Decimal(str(price_change))

            # Create candlestick
            candle = MarketDataFactory(
                symbol=self.symbol,
                timeframe=self.timeframe,
                timestamp=current_time,
                open_price=current_price,
            )

            data_points.append(candle)
            current_time += timedelta(minutes=timeframe_minutes)

        return data_points


class NewsEventFactory(factory.Factory):
    """
    Factory for creating news events that impact market data.
    """

    class Meta:
        model = dict

    # Event identification
    event_id = factory.Sequence(lambda n: f"NEWS_{n:06d}")
    timestamp = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-30d", end_date="now")
    )

    # Event details
    title = factory.Faker("sentence", nb_words=8)
    category = factory.fuzzy.FuzzyChoice(
        ["Central Bank", "Economic Data", "Political", "Market Commentary", "Earnings"]
    )
    severity = factory.fuzzy.FuzzyChoice(["Low", "Medium", "High", "Critical"])

    # Impact data
    affected_currencies = factory.LazyFunction(
        lambda: fake.random_elements(
            ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"], length=2
        )
    )
    expected_impact = factory.fuzzy.FuzzyChoice(["Bullish", "Bearish", "Neutral"])
    volatility_increase = factory.fuzzy.FuzzyDecimal(1.0, 5.0, 1)  # Multiplier

    # Market reaction (if occurred)
    actual_impact = factory.fuzzy.FuzzyChoice(
        ["Bullish", "Bearish", "Neutral", "Mixed"]
    )
    price_move_pips = factory.fuzzy.FuzzyInteger(-50, 50)  # Price movement in pips
