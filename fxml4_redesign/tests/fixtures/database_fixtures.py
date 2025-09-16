"""Database fixtures for testing."""

import asyncio
import random
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List

import asyncpg


class DatabaseFixtures:
    """Helper class to generate database test data."""

    @staticmethod
    async def create_test_symbols(conn: asyncpg.Connection) -> List[str]:
        """Create test symbols in database."""
        symbols = [
            ("EURUSD", Decimal("0.0001"), Decimal("0.00001")),
            ("GBPUSD", Decimal("0.0001"), Decimal("0.00001")),
            ("USDJPY", Decimal("0.01"), Decimal("0.001")),
            ("AUDUSD", Decimal("0.0001"), Decimal("0.00001")),
            ("USDCAD", Decimal("0.0001"), Decimal("0.00001")),
        ]

        await conn.executemany(
            """
            INSERT INTO trading.symbols (symbol, pip_size, min_tick_size, active)
            VALUES ($1, $2, $3, true)
            ON CONFLICT (symbol) DO NOTHING
        """,
            symbols,
        )

        return [s[0] for s in symbols]

    @staticmethod
    async def create_test_market_data(
        conn: asyncpg.Connection,
        symbol: str,
        start_time: datetime,
        num_bars: int = 100,
        timeframe_minutes: int = 5,
    ) -> List[Dict[str, Any]]:
        """Create test market data bars."""
        bars = []
        base_price = Decimal("1.0850") if "USD" in symbol else Decimal("110.50")
        volatility = Decimal("0.0005") if "USD" in symbol else Decimal("0.05")

        for i in range(num_bars):
            time = start_time + timedelta(minutes=i * timeframe_minutes)

            # Generate OHLC with some randomness
            open_price = base_price + (Decimal(random.random() - 0.5) * volatility)
            high_price = open_price + (Decimal(random.random()) * volatility)
            low_price = open_price - (Decimal(random.random()) * volatility)
            close_price = low_price + (
                Decimal(random.random()) * (high_price - low_price)
            )

            volume = random.randint(100, 10000)
            spread = Decimal("0.0001") if "USD" in symbol else Decimal("0.01")

            bar = {
                "time": time,
                "symbol": symbol,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume,
                "spread": spread,
                "tick_count": random.randint(10, 100),
            }

            bars.append(bar)
            base_price = close_price  # Next bar starts from previous close

        # Insert into database
        await conn.executemany(
            """
            INSERT INTO trading.market_data
            (time, symbol, open, high, low, close, volume, spread, tick_count)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (time, symbol) DO NOTHING
        """,
            [
                (
                    b["time"],
                    b["symbol"],
                    b["open"],
                    b["high"],
                    b["low"],
                    b["close"],
                    b["volume"],
                    b["spread"],
                    b["tick_count"],
                )
                for b in bars
            ],
        )

        return bars

    @staticmethod
    async def create_test_indicators(
        conn: asyncpg.Connection,
        symbol: str,
        timeframe: str,
        market_data: List[Dict[str, Any]],
    ):
        """Create test technical indicators."""
        indicators = []

        for i, bar in enumerate(market_data):
            if i < 20:  # Skip early bars for indicator calculation
                continue

            # Generate realistic indicator values
            close = float(bar["close"])

            indicator = {
                "time": bar["time"],
                "symbol": symbol,
                "timeframe": timeframe,
                "rsi_14": 30 + random.random() * 40,  # RSI between 30-70
                "atr_14": float(bar["high"] - bar["low"]) * 1.5,
                "sma_20": close + (random.random() - 0.5) * 0.001,
                "sma_50": close + (random.random() - 0.5) * 0.002,
                "sma_200": close + (random.random() - 0.5) * 0.005,
                "ema_9": close + (random.random() - 0.5) * 0.0005,
                "ema_21": close + (random.random() - 0.5) * 0.001,
                "bb_upper": close + 0.002,
                "bb_middle": close,
                "bb_lower": close - 0.002,
                "macd_line": (random.random() - 0.5) * 0.001,
                "macd_signal": (random.random() - 0.5) * 0.0008,
                "macd_histogram": (random.random() - 0.5) * 0.0002,
                "adx": 15 + random.random() * 35,  # ADX between 15-50
                "plus_di": 10 + random.random() * 30,
                "minus_di": 10 + random.random() * 30,
                "stoch_k": 20 + random.random() * 60,
                "stoch_d": 20 + random.random() * 60,
            }

            indicators.append(indicator)

        # Insert into database
        if indicators:
            await conn.executemany(
                """
                INSERT INTO trading.indicators
                (time, symbol, timeframe, rsi_14, atr_14, sma_20, sma_50, sma_200,
                 ema_9, ema_21, bb_upper, bb_middle, bb_lower, macd_line,
                 macd_signal, macd_histogram, adx, plus_di, minus_di, stoch_k, stoch_d)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
                        $14, $15, $16, $17, $18, $19, $20, $21)
                ON CONFLICT (time, symbol, timeframe) DO NOTHING
            """,
                [
                    (
                        ind["time"],
                        ind["symbol"],
                        ind["timeframe"],
                        ind["rsi_14"],
                        ind["atr_14"],
                        ind["sma_20"],
                        ind["sma_50"],
                        ind["sma_200"],
                        ind["ema_9"],
                        ind["ema_21"],
                        ind["bb_upper"],
                        ind["bb_middle"],
                        ind["bb_lower"],
                        ind["macd_line"],
                        ind["macd_signal"],
                        ind["macd_histogram"],
                        ind["adx"],
                        ind["plus_di"],
                        ind["minus_di"],
                        ind["stoch_k"],
                        ind["stoch_d"],
                    )
                    for ind in indicators
                ],
            )

        return indicators

    @staticmethod
    async def create_test_signals(
        conn: asyncpg.Connection, symbol: str, num_signals: int = 5
    ) -> List[Dict[str, Any]]:
        """Create test trading signals."""
        signals = []
        base_time = datetime.utcnow() - timedelta(hours=24)

        for i in range(num_signals):
            signal_time = base_time + timedelta(hours=i * 4)
            direction = random.choice(["BUY", "SELL"])
            base_price = Decimal("1.0850") if "USD" in symbol else Decimal("110.50")

            signal = {
                "signal_time": signal_time,
                "symbol": symbol,
                "timeframe": "4H",
                "direction": direction,
                "entry_price": base_price
                + Decimal(random.random() - 0.5) * Decimal("0.001"),
                "stop_loss": (
                    base_price - Decimal("0.003")
                    if direction == "BUY"
                    else base_price + Decimal("0.003")
                ),
                "take_profit": (
                    base_price + Decimal("0.003")
                    if direction == "BUY"
                    else base_price - Decimal("0.003")
                ),
                "confidence": 0.6 + random.random() * 0.3,
                "source": random.choice(["ml_model", "technical", "elliott_wave"]),
                "status": random.choice(["pending", "active", "expired"]),
                "metadata": {
                    "model_version": "1.0",
                    "indicators_used": ["rsi", "macd", "bb"],
                },
            }

            signals.append(signal)

        # Insert into database
        await conn.executemany(
            """
            INSERT INTO trading.trading_signals
            (signal_time, symbol, timeframe, direction, entry_price, stop_loss,
             take_profit, confidence, source, status, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        """,
            [
                (
                    s["signal_time"],
                    s["symbol"],
                    s["timeframe"],
                    s["direction"],
                    s["entry_price"],
                    s["stop_loss"],
                    s["take_profit"],
                    s["confidence"],
                    s["source"],
                    s["status"],
                    s["metadata"],
                )
                for s in signals
            ],
        )

        return signals

    @staticmethod
    async def create_test_trades(
        conn: asyncpg.Connection, symbol: str, num_trades: int = 3
    ) -> List[Dict[str, Any]]:
        """Create test trades."""
        trades = []
        base_time = datetime.utcnow() - timedelta(days=7)

        for i in range(num_trades):
            entry_time = base_time + timedelta(days=i)
            direction = random.choice(["BUY", "SELL"])
            base_price = Decimal("1.0850") if "USD" in symbol else Decimal("110.50")
            entry_price = base_price + Decimal(random.random() - 0.5) * Decimal("0.001")

            trade = {
                "trade_id": f"TEST-{symbol}-{i:03d}",
                "symbol": symbol,
                "direction": direction,
                "entry_price": entry_price,
                "entry_time": entry_time,
                "position_size": Decimal("10000"),
                "stop_loss": (
                    entry_price - Decimal("0.003")
                    if direction == "BUY"
                    else entry_price + Decimal("0.003")
                ),
                "take_profit": (
                    entry_price + Decimal("0.003")
                    if direction == "BUY"
                    else entry_price - Decimal("0.003")
                ),
                "status": random.choice(["open", "closed"]),
                "exit_price": (
                    entry_price + Decimal(random.random() - 0.5) * Decimal("0.002")
                    if random.random() > 0.5
                    else None
                ),
                "exit_time": (
                    entry_time + timedelta(hours=random.randint(1, 48))
                    if random.random() > 0.5
                    else None
                ),
                "pnl": Decimal(random.randint(-100, 200)),
                "commission": Decimal("2.50"),
                "metadata": {"strategy": "test_strategy"},
            }

            trades.append(trade)

        # Insert into database
        await conn.executemany(
            """
            INSERT INTO trading.trades
            (trade_id, symbol, direction, entry_price, entry_time, position_size,
             stop_loss, take_profit, status, exit_price, exit_time, pnl,
             commission, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        """,
            [
                (
                    t["trade_id"],
                    t["symbol"],
                    t["direction"],
                    t["entry_price"],
                    t["entry_time"],
                    t["position_size"],
                    t["stop_loss"],
                    t["take_profit"],
                    t["status"],
                    t["exit_price"],
                    t["exit_time"],
                    t["pnl"],
                    t["commission"],
                    t["metadata"],
                )
                for t in trades
            ],
        )

        return trades

    @staticmethod
    async def create_test_system_events(
        conn: asyncpg.Connection, service_name: str, num_events: int = 10
    ) -> List[Dict[str, Any]]:
        """Create test system events."""
        events = []
        base_time = datetime.utcnow() - timedelta(hours=1)

        event_types = ["startup", "shutdown", "error", "warning", "info"]
        severities = ["error", "warning", "info", "debug"]

        for i in range(num_events):
            event_time = base_time + timedelta(minutes=i * 6)
            event_type = random.choice(event_types)

            event = {
                "event_time": event_time,
                "service_name": service_name,
                "event_type": event_type,
                "severity": (
                    "error" if event_type == "error" else random.choice(severities)
                ),
                "message": f"Test {event_type} event {i}",
                "details": {"test": True, "index": i, "random_value": random.random()},
            }

            events.append(event)

        # Insert into database
        await conn.executemany(
            """
            INSERT INTO trading.system_events
            (event_time, service_name, event_type, severity, message, details)
            VALUES ($1, $2, $3, $4, $5, $6)
        """,
            [
                (
                    e["event_time"],
                    e["service_name"],
                    e["event_type"],
                    e["severity"],
                    e["message"],
                    e["details"],
                )
                for e in events
            ],
        )

        return events

    @staticmethod
    async def cleanup_test_data(conn: asyncpg.Connection):
        """Clean up all test data."""
        tables = [
            "trading.trades",
            "trading.trading_signals",
            "trading.indicators",
            "trading.market_data",
            "trading.system_events",
            "trading.symbols",
        ]

        for table in tables:
            await conn.execute(f"TRUNCATE TABLE {table} CASCADE")


# Fixture generator functions
async def generate_complete_test_dataset(conn: asyncpg.Connection):
    """Generate a complete test dataset."""
    fixtures = DatabaseFixtures()

    # Create symbols
    symbols = await fixtures.create_test_symbols(conn)

    # For each symbol, create market data, indicators, signals, and trades
    for symbol in symbols[:2]:  # Just use first 2 symbols for speed
        # Create market data
        start_time = datetime.utcnow() - timedelta(days=7)
        market_data = await fixtures.create_test_market_data(
            conn, symbol, start_time, num_bars=200
        )

        # Create indicators
        await fixtures.create_test_indicators(conn, symbol, "4H", market_data)

        # Create signals
        await fixtures.create_test_signals(conn, symbol, num_signals=5)

        # Create trades
        await fixtures.create_test_trades(conn, symbol, num_trades=3)

    # Create system events
    await fixtures.create_test_system_events(conn, "test-service", num_events=20)

    return {
        "symbols": symbols,
        "market_data_count": len(symbols) * 200,
        "signals_count": len(symbols) * 5,
        "trades_count": len(symbols) * 3,
        "events_count": 20,
    }
