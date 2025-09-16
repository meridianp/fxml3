"""Market data fixtures for testing."""

import random
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


class MarketDataGenerator:
    """Generate realistic market data for testing."""

    # Symbol configurations
    SYMBOL_CONFIG = {
        "EURUSD": {
            "base_price": Decimal("1.0850"),
            "volatility": Decimal("0.0005"),
            "pip_size": Decimal("0.0001"),
            "typical_spread": Decimal("0.0001"),
            "trend_factor": 0.0001,
        },
        "GBPUSD": {
            "base_price": Decimal("1.2650"),
            "volatility": Decimal("0.0008"),
            "pip_size": Decimal("0.0001"),
            "typical_spread": Decimal("0.0002"),
            "trend_factor": 0.0002,
        },
        "USDJPY": {
            "base_price": Decimal("110.50"),
            "volatility": Decimal("0.05"),
            "pip_size": Decimal("0.01"),
            "typical_spread": Decimal("0.01"),
            "trend_factor": 0.01,
        },
        "AUDUSD": {
            "base_price": Decimal("0.7250"),
            "volatility": Decimal("0.0006"),
            "pip_size": Decimal("0.0001"),
            "typical_spread": Decimal("0.0002"),
            "trend_factor": 0.00015,
        },
    }

    @classmethod
    def generate_tick_data(
        cls,
        symbol: str,
        start_time: datetime,
        duration_seconds: int = 60,
        ticks_per_second: float = 2.0,
    ) -> List[Dict[str, Any]]:
        """Generate realistic tick data."""
        config = cls.SYMBOL_CONFIG.get(symbol, cls.SYMBOL_CONFIG["EURUSD"])

        ticks = []
        current_price = config["base_price"]
        current_time = start_time

        # Number of ticks to generate
        num_ticks = int(duration_seconds * ticks_per_second)

        # Generate price movement with random walk
        for i in range(num_ticks):
            # Time between ticks (with some jitter)
            time_increment = 1.0 / ticks_per_second + random.uniform(-0.1, 0.1)
            current_time += timedelta(seconds=time_increment)

            # Price movement (random walk with slight trend)
            price_change = Decimal(str(random.gauss(0, float(config["volatility"]))))
            trend = Decimal(str(config["trend_factor"] * np.sin(i / 100)))
            current_price += price_change + trend

            # Generate bid/ask
            half_spread = config["typical_spread"] / 2
            bid = current_price - half_spread
            ask = current_price + half_spread

            # Random size
            size = random.randint(100, 10000) * 100

            tick = {
                "symbol": symbol,
                "time": current_time,
                "bid": bid,
                "ask": ask,
                "price": current_price,
                "size": size,
                "type": random.choice(["trade", "quote"]),
            }

            ticks.append(tick)

        return ticks

    @classmethod
    def generate_ohlc_data(
        cls,
        symbol: str,
        start_time: datetime,
        num_bars: int = 100,
        timeframe: str = "5m",
    ) -> pd.DataFrame:
        """Generate realistic OHLC data."""
        config = cls.SYMBOL_CONFIG.get(symbol, cls.SYMBOL_CONFIG["EURUSD"])

        # Parse timeframe
        timeframe_map = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "4h": 240,
            "1d": 1440,
        }
        minutes = timeframe_map.get(timeframe, 5)

        # Generate data
        data = []
        current_price = config["base_price"]

        for i in range(num_bars):
            bar_time = start_time + timedelta(minutes=i * minutes)

            # Generate intrabar movements
            movements = []
            for _ in range(minutes):
                change = Decimal(str(random.gauss(0, float(config["volatility"]))))
                movements.append(current_price + change)

            # Create OHLC
            open_price = current_price
            high_price = max(movements)
            low_price = min(movements)
            close_price = movements[-1]

            # Volume (higher during "active" hours)
            hour = bar_time.hour
            if 8 <= hour <= 16:  # London/NY hours
                volume = random.randint(500, 5000)
            else:
                volume = random.randint(100, 1000)

            # Update current price
            current_price = close_price

            data.append(
                {
                    "time": bar_time,
                    "open": float(open_price),
                    "high": float(high_price),
                    "low": float(low_price),
                    "close": float(close_price),
                    "volume": volume,
                }
            )

        return pd.DataFrame(data).set_index("time")

    @classmethod
    def generate_market_snapshot(
        cls, symbol: str, timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Generate a market snapshot with all current data."""
        if timestamp is None:
            timestamp = datetime.utcnow()

        config = cls.SYMBOL_CONFIG.get(symbol, cls.SYMBOL_CONFIG["EURUSD"])

        # Base price with some randomness
        base = config["base_price"]
        current_price = base + Decimal(
            str(random.gauss(0, float(config["volatility"])))
        )

        # Spread
        spread = config["typical_spread"] * Decimal(str(random.uniform(0.8, 1.5)))
        bid = current_price - spread / 2
        ask = current_price + spread / 2

        return {
            "symbol": symbol,
            "timestamp": timestamp,
            "bid": float(bid),
            "ask": float(ask),
            "mid": float(current_price),
            "spread": float(spread),
            "bid_size": random.randint(100, 5000) * 1000,
            "ask_size": random.randint(100, 5000) * 1000,
            "daily_high": float(current_price + config["volatility"] * 5),
            "daily_low": float(current_price - config["volatility"] * 5),
            "daily_volume": random.randint(10000, 100000),
        }

    @classmethod
    def generate_order_book(
        cls, symbol: str, levels: int = 10, timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Generate a realistic order book."""
        if timestamp is None:
            timestamp = datetime.utcnow()

        config = cls.SYMBOL_CONFIG.get(symbol, cls.SYMBOL_CONFIG["EURUSD"])

        # Get current market price
        snapshot = cls.generate_market_snapshot(symbol, timestamp)
        mid_price = Decimal(str(snapshot["mid"]))
        pip_size = config["pip_size"]

        # Generate bid levels
        bids = []
        for i in range(levels):
            price = mid_price - (i + 1) * pip_size
            size = (
                random.randint(100, 5000) * 1000 * (levels - i)
            )  # Larger sizes closer to mid
            bids.append({"price": float(price), "size": size})

        # Generate ask levels
        asks = []
        for i in range(levels):
            price = mid_price + (i + 1) * pip_size
            size = random.randint(100, 5000) * 1000 * (levels - i)
            asks.append({"price": float(price), "size": size})

        return {
            "symbol": symbol,
            "timestamp": timestamp,
            "bids": bids,
            "asks": asks,
            "mid_price": float(mid_price),
            "spread": float(asks[0]["price"] - bids[0]["price"]),
        }

    @classmethod
    def generate_market_event(
        cls, symbol: str, event_type: str = "news", impact: str = "medium"
    ) -> Dict[str, Any]:
        """Generate a market event (news, economic data, etc.)."""
        impact_map = {"low": 0.0002, "medium": 0.0005, "high": 0.001}

        event_types = {
            "news": {"description": "Breaking news event", "duration_minutes": 30},
            "economic": {
                "description": "Economic data release",
                "duration_minutes": 60,
            },
            "central_bank": {
                "description": "Central bank announcement",
                "duration_minutes": 120,
            },
        }

        config = cls.SYMBOL_CONFIG.get(symbol, cls.SYMBOL_CONFIG["EURUSD"])
        event_config = event_types.get(event_type, event_types["news"])

        return {
            "symbol": symbol,
            "event_type": event_type,
            "impact": impact,
            "timestamp": datetime.utcnow(),
            "description": event_config["description"],
            "expected_volatility": float(config["volatility"])
            * (1 + impact_map[impact]),
            "duration_minutes": event_config["duration_minutes"],
            "direction_bias": random.choice(["bullish", "bearish", "neutral"]),
        }

    @classmethod
    def generate_trading_session_data(
        cls, symbol: str, session: str = "london"
    ) -> Dict[str, Any]:
        """Generate data for a trading session."""
        sessions = {
            "sydney": {"start": 22, "end": 7, "volatility_mult": 0.7},
            "tokyo": {"start": 0, "end": 9, "volatility_mult": 0.8},
            "london": {"start": 8, "end": 17, "volatility_mult": 1.2},
            "newyork": {"start": 13, "end": 22, "volatility_mult": 1.3},
        }

        session_config = sessions.get(session, sessions["london"])
        config = cls.SYMBOL_CONFIG.get(symbol, cls.SYMBOL_CONFIG["EURUSD"])

        # Generate session data
        now = datetime.utcnow()
        session_start = now.replace(hour=session_config["start"], minute=0, second=0)

        return {
            "symbol": symbol,
            "session": session,
            "start_time": session_start,
            "end_time": session_start.replace(hour=session_config["end"]),
            "expected_volatility": float(
                config["volatility"] * Decimal(str(session_config["volatility_mult"]))
            ),
            "typical_volume": random.randint(50000, 200000),
            "active": session_config["start"] <= now.hour < session_config["end"],
        }


class IndicatorDataGenerator:
    """Generate technical indicator data for testing."""

    @staticmethod
    def generate_indicators(ohlc_data: pd.DataFrame) -> pd.DataFrame:
        """Generate common technical indicators."""
        df = ohlc_data.copy()

        # Simple Moving Averages
        df["sma_20"] = df["close"].rolling(window=20).mean()
        df["sma_50"] = df["close"].rolling(window=50).mean()
        df["sma_200"] = df["close"].rolling(window=200).mean()

        # Exponential Moving Averages
        df["ema_9"] = df["close"].ewm(span=9, adjust=False).mean()
        df["ema_21"] = df["close"].ewm(span=21, adjust=False).mean()

        # RSI
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df["rsi_14"] = 100 - (100 / (1 + rs))

        # Bollinger Bands
        df["bb_middle"] = df["close"].rolling(window=20).mean()
        bb_std = df["close"].rolling(window=20).std()
        df["bb_upper"] = df["bb_middle"] + (bb_std * 2)
        df["bb_lower"] = df["bb_middle"] - (bb_std * 2)

        # MACD
        exp1 = df["close"].ewm(span=12, adjust=False).mean()
        exp2 = df["close"].ewm(span=26, adjust=False).mean()
        df["macd"] = exp1 - exp2
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_histogram"] = df["macd"] - df["macd_signal"]

        # ATR
        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift())
        low_close = np.abs(df["low"] - df["close"].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        df["atr_14"] = true_range.rolling(window=14).mean()

        # Stochastic
        low_14 = df["low"].rolling(window=14).min()
        high_14 = df["high"].rolling(window=14).max()
        df["stoch_k"] = 100 * ((df["close"] - low_14) / (high_14 - low_14))
        df["stoch_d"] = df["stoch_k"].rolling(window=3).mean()

        # ADX
        df["plus_dm"] = np.where(
            (df["high"] - df["high"].shift()) > (df["low"].shift() - df["low"]),
            np.maximum(df["high"] - df["high"].shift(), 0),
            0,
        )
        df["minus_dm"] = np.where(
            (df["low"].shift() - df["low"]) > (df["high"] - df["high"].shift()),
            np.maximum(df["low"].shift() - df["low"], 0),
            0,
        )

        df["plus_di"] = 100 * (df["plus_dm"].rolling(window=14).mean() / df["atr_14"])
        df["minus_di"] = 100 * (df["minus_dm"].rolling(window=14).mean() / df["atr_14"])
        df["dx"] = 100 * (
            np.abs(df["plus_di"] - df["minus_di"]) / (df["plus_di"] + df["minus_di"])
        )
        df["adx"] = df["dx"].rolling(window=14).mean()

        return df


class SignalDataGenerator:
    """Generate trading signal data for testing."""

    @staticmethod
    def generate_signal(
        symbol: str,
        signal_type: str = "technical",
        confidence_range: Tuple[float, float] = (0.6, 0.9),
    ) -> Dict[str, Any]:
        """Generate a trading signal."""
        config = MarketDataGenerator.SYMBOL_CONFIG.get(
            symbol, MarketDataGenerator.SYMBOL_CONFIG["EURUSD"]
        )

        # Current market price
        current_price = config["base_price"] + Decimal(
            str(random.gauss(0, float(config["volatility"])))
        )

        # Signal direction
        direction = random.choice(["BUY", "SELL"])

        # Risk parameters
        risk_reward_ratio = random.uniform(1.5, 3.0)
        stop_distance = config["volatility"] * Decimal(str(random.uniform(20, 40)))

        if direction == "BUY":
            entry_price = current_price
            stop_loss = entry_price - stop_distance
            take_profit = entry_price + (
                stop_distance * Decimal(str(risk_reward_ratio))
            )
        else:
            entry_price = current_price
            stop_loss = entry_price + stop_distance
            take_profit = entry_price - (
                stop_distance * Decimal(str(risk_reward_ratio))
            )

        # Signal metadata
        signal_metadata = {
            "technical": {
                "indicators_triggered": random.sample(
                    ["rsi_oversold", "macd_cross", "bb_squeeze", "ema_cross"],
                    k=random.randint(2, 3),
                ),
                "pattern": random.choice(["flag", "triangle", "channel", "none"]),
            },
            "ml_model": {
                "model_version": "2.1.0",
                "feature_importance": {
                    "rsi": random.random(),
                    "macd": random.random(),
                    "volume": random.random(),
                },
                "prediction_probability": random.uniform(0.6, 0.95),
            },
            "elliott_wave": {
                "wave_count": random.choice(["12345", "ABC"]),
                "current_wave": random.choice(["3", "5", "C"]),
                "wave_degree": random.choice(["primary", "intermediate", "minor"]),
            },
        }

        return {
            "signal_id": f'SIG-{symbol}-{datetime.utcnow().strftime("%Y%m%d%H%M%S")}',
            "symbol": symbol,
            "signal_type": signal_type,
            "direction": direction,
            "entry_price": float(entry_price),
            "stop_loss": float(stop_loss),
            "take_profit": float(take_profit),
            "confidence": random.uniform(*confidence_range),
            "risk_reward_ratio": risk_reward_ratio,
            "timeframe": random.choice(["15m", "1h", "4h"]),
            "timestamp": datetime.utcnow(),
            "expiry": datetime.utcnow() + timedelta(hours=random.randint(1, 24)),
            "metadata": signal_metadata.get(signal_type, {}),
        }
