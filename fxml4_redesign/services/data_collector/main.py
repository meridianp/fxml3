"""Data Collector Service - Dual-speed market data collection."""

import asyncio
import sys
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set

from data_aggregator import DataAggregator
from ib_gateway_client import IBGatewayClient
from indicator_calculator import IndicatorCalculator
from shared.config.rabbitmq_config import (
    Exchanges,
    Queues,
    RoutingKeys,
    format_routing_key,
)
from shared.utils.base_service import BaseService, ServiceConfig


class DataCollectorService(BaseService):
    """Dual-speed data collection service."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__("data-collector", config)

        # IB Gateway client
        self.ib_client: Optional[IBGatewayClient] = None

        # Components
        self.aggregator = DataAggregator()
        self.indicator_calculator = IndicatorCalculator()

        # Symbol management
        self.all_symbols: List[str] = []
        self.active_symbols: Set[str] = set()
        self.symbol_last_update: Dict[str, datetime] = {}

        # Collection intervals
        self.slow_interval = 300  # 5 minutes for 4H data
        self.fast_interval = 30  # 30 seconds for 1m data

        # Buffer for batch inserts
        self.tick_buffer: List[Dict[str, Any]] = []
        self.buffer_size = 100
        self.last_flush = datetime.utcnow()

    async def service_setup(self):
        """Set up data collector service."""
        # Initialize IB Gateway connection
        self.ib_client = IBGatewayClient(
            host=self.config.get("ib_gateway_host"),
            port=self.config.get("ib_gateway_port"),
            client_id=self.config.get("ib_client_id"),
        )

        # Connect to IB Gateway
        await self.ib_client.connect()

        # Load symbols from database
        await self.load_symbols()

        # Subscribe to initial symbols
        await self.subscribe_symbols(self.all_symbols)

        # Set up RabbitMQ
        await self.setup_rabbitmq()

        self.logger.info(
            f"Data collector initialized with {len(self.all_symbols)} symbols"
        )

    async def service_teardown(self):
        """Clean up resources."""
        if self.ib_client:
            await self.ib_client.disconnect()

    async def service_run(self):
        """Main service loop."""
        # Start collection tasks
        self.add_task(self.slow_collection_loop())
        self.add_task(self.fast_collection_loop())
        self.add_task(self.tick_processor_loop())
        self.add_task(self.buffer_flush_loop())
        self.add_task(self.heartbeat_loop())
        self.add_task(self.symbol_activation_loop())

        # Wait for shutdown
        while self.running:
            await asyncio.sleep(1)

    async def setup_rabbitmq(self):
        """Set up RabbitMQ exchanges and queues."""
        # Declare exchanges
        await self.rabbitmq_channel.declare_exchange(
            Exchanges.MARKET_DATA, type="topic", durable=True
        )

        self.logger.info("RabbitMQ setup complete")

    async def load_symbols(self):
        """Load symbols from database."""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT symbol, pip_size, min_tick_size
                FROM trading.symbols
                WHERE active = true
                ORDER BY symbol
            """
            )

            self.all_symbols = [row["symbol"] for row in rows]

            # Store symbol info in cache
            for row in rows:
                await self.cache_json_set(
                    f"symbol:info:{row['symbol']}",
                    {
                        "pip_size": float(row["pip_size"]),
                        "min_tick_size": float(row["min_tick_size"]),
                    },
                    ttl=86400,  # 24 hours
                )

    async def subscribe_symbols(self, symbols: List[str]):
        """Subscribe to market data for symbols."""
        for symbol in symbols:
            try:
                await self.ib_client.subscribe_market_data(symbol)
                self.logger.info(f"Subscribed to {symbol}")
            except Exception as e:
                self.logger.error(f"Failed to subscribe to {symbol}: {e}")

    async def slow_collection_loop(self):
        """Slow collection loop for all symbols (5-minute intervals)."""
        while self.running:
            try:
                start_time = datetime.utcnow()

                # Collect data for all symbols
                for symbol in self.all_symbols:
                    if not self.running:
                        break

                    try:
                        # Get latest market data
                        data = await self.ib_client.get_market_data(symbol)

                        if data:
                            # Store in database
                            await self.store_market_data(symbol, data)

                            # Calculate indicators
                            await self.calculate_and_store_indicators(symbol, "4H")

                            # Publish to RabbitMQ
                            await self.publish_market_update(symbol, data, "4H")

                            # Update last update time
                            self.symbol_last_update[symbol] = datetime.utcnow()

                    except Exception as e:
                        self.logger.error(f"Error collecting data for {symbol}: {e}")
                        await self.log_error(e, {"symbol": symbol, "loop": "slow"})

                # Sleep for remaining time
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                sleep_time = max(0, self.slow_interval - elapsed)

                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

            except Exception as e:
                self.logger.error(f"Error in slow collection loop: {e}")
                await asyncio.sleep(10)

    async def fast_collection_loop(self):
        """Fast collection loop for active symbols (30-second intervals)."""
        while self.running:
            try:
                start_time = datetime.utcnow()

                # Collect data only for active symbols
                for symbol in self.active_symbols:
                    if not self.running:
                        break

                    try:
                        # Get tick data
                        ticks = await self.ib_client.get_tick_data(symbol)

                        if ticks:
                            # Add to buffer
                            for tick in ticks:
                                self.tick_buffer.append(
                                    {
                                        "symbol": symbol,
                                        "time": tick["time"],
                                        "price": tick["price"],
                                        "size": tick.get("size", 0),
                                        "type": tick.get("type", "trade"),
                                    }
                                )

                            # Get latest market data
                            data = await self.ib_client.get_market_data(symbol)

                            if data:
                                # Store 1-minute data
                                await self.store_market_data(
                                    symbol, data, timeframe="1m"
                                )

                                # Publish tick stream
                                await self.publish_tick_stream(symbol, ticks)

                                # Publish 1-minute update
                                await self.publish_market_update(symbol, data, "1m")

                    except Exception as e:
                        self.logger.error(f"Error in fast collection for {symbol}: {e}")
                        await self.log_error(e, {"symbol": symbol, "loop": "fast"})

                # Sleep for remaining time
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                sleep_time = max(0, self.fast_interval - elapsed)

                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

            except Exception as e:
                self.logger.error(f"Error in fast collection loop: {e}")
                await asyncio.sleep(5)

    async def tick_processor_loop(self):
        """Process incoming ticks from IB Gateway."""
        while self.running:
            try:
                # Process ticks from IB Gateway callback
                tick = await self.ib_client.get_next_tick()

                if tick:
                    # Add to buffer
                    self.tick_buffer.append(tick)

                    # Check if symbol should be activated
                    symbol = tick["symbol"]
                    if symbol not in self.active_symbols:
                        await self.check_symbol_activation(symbol)

            except Exception as e:
                self.logger.error(f"Error processing tick: {e}")
                await asyncio.sleep(0.1)

    async def buffer_flush_loop(self):
        """Periodically flush tick buffer to database."""
        while self.running:
            try:
                # Flush every 5 seconds or when buffer is full
                if (
                    len(self.tick_buffer) >= self.buffer_size
                    or (datetime.utcnow() - self.last_flush).total_seconds() > 5
                ):

                    if self.tick_buffer:
                        await self.flush_tick_buffer()

                await asyncio.sleep(1)

            except Exception as e:
                self.logger.error(f"Error in buffer flush: {e}")
                await asyncio.sleep(5)

    async def flush_tick_buffer(self):
        """Flush tick buffer to database."""
        if not self.tick_buffer:
            return

        # Copy buffer and clear
        ticks = self.tick_buffer.copy()
        self.tick_buffer.clear()
        self.last_flush = datetime.utcnow()

        # Group by symbol for efficient insertion
        symbol_ticks = {}
        for tick in ticks:
            symbol = tick["symbol"]
            if symbol not in symbol_ticks:
                symbol_ticks[symbol] = []
            symbol_ticks[symbol].append(tick)

        # Batch insert
        async with self.db_pool.acquire() as conn:
            for symbol, symbol_tick_list in symbol_ticks.items():
                # Aggregate to 1-second bars
                second_bars = self.aggregator.aggregate_ticks_to_seconds(
                    symbol_tick_list
                )

                # Insert bars
                if second_bars:
                    await conn.executemany(
                        """
                        INSERT INTO trading.market_data
                        (time, symbol, open, high, low, close, volume, tick_count)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT (time, symbol) DO UPDATE SET
                            high = GREATEST(market_data.high, EXCLUDED.high),
                            low = LEAST(market_data.low, EXCLUDED.low),
                            close = EXCLUDED.close,
                            volume = market_data.volume + EXCLUDED.volume,
                            tick_count = market_data.tick_count + EXCLUDED.tick_count
                    """,
                        second_bars,
                    )

        self.logger.debug(f"Flushed {len(ticks)} ticks to database")

    async def store_market_data(
        self, symbol: str, data: Dict[str, Any], timeframe: str = None
    ):
        """Store market data in database."""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO trading.market_data
                (time, symbol, open, high, low, close, volume, spread)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (time, symbol) DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    spread = EXCLUDED.spread
            """,
                data["time"],
                symbol,
                data["open"],
                data["high"],
                data["low"],
                data["close"],
                data.get("volume", 0),
                data.get("spread"),
            )

    async def calculate_and_store_indicators(self, symbol: str, timeframe: str):
        """Calculate and store technical indicators."""
        try:
            # Get recent price data
            async with self.db_pool.acquire() as conn:
                # Use appropriate continuous aggregate
                table_name = (
                    f"market_data_{timeframe.lower()}"
                    if timeframe != "tick"
                    else "market_data"
                )

                rows = await conn.fetch(
                    f"""
                    SELECT bucket as time, open, high, low, close, volume
                    FROM trading.{table_name}
                    WHERE symbol = $1
                    ORDER BY bucket DESC
                    LIMIT 500
                """,
                    symbol,
                )

                if len(rows) < 50:  # Need minimum data for indicators
                    return

                # Convert to dataframe
                import pandas as pd

                df = pd.DataFrame([dict(row) for row in rows])
                df = df.sort_values("time")
                df.set_index("time", inplace=True)

                # Calculate indicators
                indicators = self.indicator_calculator.calculate_all(df)

                # Store latest values
                latest = indicators.iloc[-1]

                await conn.execute(
                    """
                    INSERT INTO trading.indicators
                    (time, symbol, timeframe, rsi_14, atr_14, sma_20, sma_50, sma_200,
                     ema_9, ema_21, bb_upper, bb_middle, bb_lower, macd_line,
                     macd_signal, macd_histogram, adx, plus_di, minus_di, stoch_k, stoch_d)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
                            $14, $15, $16, $17, $18, $19, $20, $21)
                    ON CONFLICT (time, symbol, timeframe) DO UPDATE SET
                        rsi_14 = EXCLUDED.rsi_14,
                        atr_14 = EXCLUDED.atr_14,
                        sma_20 = EXCLUDED.sma_20,
                        sma_50 = EXCLUDED.sma_50,
                        sma_200 = EXCLUDED.sma_200,
                        ema_9 = EXCLUDED.ema_9,
                        ema_21 = EXCLUDED.ema_21,
                        bb_upper = EXCLUDED.bb_upper,
                        bb_middle = EXCLUDED.bb_middle,
                        bb_lower = EXCLUDED.bb_lower,
                        macd_line = EXCLUDED.macd_line,
                        macd_signal = EXCLUDED.macd_signal,
                        macd_histogram = EXCLUDED.macd_histogram,
                        adx = EXCLUDED.adx,
                        plus_di = EXCLUDED.plus_di,
                        minus_di = EXCLUDED.minus_di,
                        stoch_k = EXCLUDED.stoch_k,
                        stoch_d = EXCLUDED.stoch_d
                """,
                    df.index[-1],
                    symbol,
                    timeframe,
                    latest.get("rsi_14"),
                    latest.get("atr_14"),
                    latest.get("sma_20"),
                    latest.get("sma_50"),
                    latest.get("sma_200"),
                    latest.get("ema_9"),
                    latest.get("ema_21"),
                    latest.get("bb_upper"),
                    latest.get("bb_middle"),
                    latest.get("bb_lower"),
                    latest.get("macd"),
                    latest.get("macd_signal"),
                    latest.get("macd_histogram"),
                    latest.get("adx"),
                    latest.get("plus_di"),
                    latest.get("minus_di"),
                    latest.get("stoch_k"),
                    latest.get("stoch_d"),
                )

                # Cache indicators
                await self.cache_json_set(
                    f"indicators:{symbol}:{timeframe}",
                    latest.to_dict(),
                    ttl=600,  # 10 minutes
                )

        except Exception as e:
            self.logger.error(f"Error calculating indicators for {symbol}: {e}")
            await self.log_error(e, {"symbol": symbol, "timeframe": timeframe})

    async def publish_market_update(
        self, symbol: str, data: Dict[str, Any], timeframe: str
    ):
        """Publish market update to RabbitMQ."""
        message = {
            "symbol": symbol,
            "timeframe": timeframe,
            "data": data,
            "indicators": await self.cache_json_get(f"indicators:{symbol}:{timeframe}"),
        }

        # Publish based on timeframe
        if timeframe == "4H":
            routing_key = format_routing_key(RoutingKeys.MARKET_READY, symbol=symbol)
        else:
            routing_key = format_routing_key(RoutingKeys.MARKET_1MIN, symbol=symbol)

        await self.publish_message(Exchanges.MARKET_DATA, routing_key, message)

    async def publish_tick_stream(self, symbol: str, ticks: List[Dict[str, Any]]):
        """Publish tick stream to RabbitMQ."""
        message = {"symbol": symbol, "ticks": ticks, "count": len(ticks)}

        routing_key = format_routing_key(RoutingKeys.MARKET_TICK, symbol=symbol)

        await self.publish_message(Exchanges.MARKET_DATA, routing_key, message)

    async def check_symbol_activation(self, symbol: str):
        """Check if symbol should be activated for fast collection."""
        # Get recent signals for this symbol
        async with self.db_pool.acquire() as conn:
            recent_signals = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM trading.trading_signals
                WHERE symbol = $1
                AND signal_time > NOW() - INTERVAL '30 minutes'
                AND status IN ('pending', 'active')
            """,
                symbol,
            )

            # Check recent trades
            active_trades = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM trading.trades
                WHERE symbol = $1
                AND status = 'open'
            """,
                symbol,
            )

        # Activate if there are recent signals or active trades
        if recent_signals > 0 or active_trades > 0:
            if symbol not in self.active_symbols:
                self.active_symbols.add(symbol)
                self.logger.info(f"Activated fast collection for {symbol}")
                await self.log_event(
                    "symbol_activated", f"Fast collection activated for {symbol}"
                )

    async def symbol_activation_loop(self):
        """Periodically check which symbols should be active."""
        while self.running:
            try:
                # Check all symbols
                for symbol in self.all_symbols:
                    await self.check_symbol_activation(symbol)

                # Deactivate stale symbols
                current_time = datetime.utcnow()
                symbols_to_deactivate = []

                for symbol in self.active_symbols:
                    last_update = self.symbol_last_update.get(symbol)
                    if (
                        last_update
                        and (current_time - last_update).total_seconds() > 1800
                    ):  # 30 minutes
                        symbols_to_deactivate.append(symbol)

                for symbol in symbols_to_deactivate:
                    self.active_symbols.remove(symbol)
                    self.logger.info(f"Deactivated fast collection for {symbol}")

                # Sleep for 1 minute
                await asyncio.sleep(60)

            except Exception as e:
                self.logger.error(f"Error in symbol activation loop: {e}")
                await asyncio.sleep(60)

    async def heartbeat_loop(self):
        """Send periodic heartbeats."""
        while self.running:
            try:
                # Send heartbeat
                await self.publish_message(
                    Exchanges.SYSTEM,
                    format_routing_key(
                        RoutingKeys.SYSTEM_HEARTBEAT, service=self.service_name
                    ),
                    {
                        "active_symbols": list(self.active_symbols),
                        "total_symbols": len(self.all_symbols),
                        "buffer_size": len(self.tick_buffer),
                        "health": await self.health_check(),
                    },
                )

                # Send metrics
                await self.publish_message(
                    Exchanges.SYSTEM,
                    format_routing_key(
                        RoutingKeys.SYSTEM_METRICS, service=self.service_name
                    ),
                    {
                        "tick_buffer_size": len(self.tick_buffer),
                        "active_symbols_count": len(self.active_symbols),
                        "total_symbols_count": len(self.all_symbols),
                    },
                )

                await asyncio.sleep(30)

            except Exception as e:
                self.logger.error(f"Error in heartbeat loop: {e}")
                await asyncio.sleep(30)


if __name__ == "__main__":
    # Load configuration
    config = ServiceConfig.from_env()

    # Create and run service
    service = DataCollectorService(config)
    asyncio.run(service.run())
