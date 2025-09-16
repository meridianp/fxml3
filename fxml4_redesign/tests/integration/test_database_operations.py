"""Integration tests for database operations."""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal

import asyncpg
import pytest
from fixtures.database_fixtures import DatabaseFixtures, generate_complete_test_dataset
from fixtures.market_data_fixtures import MarketDataGenerator


@pytest.mark.integration
@pytest.mark.requires_db
class TestDatabaseOperations:
    """Test database operations and performance."""

    @pytest.mark.asyncio
    async def test_complete_data_pipeline(self, test_db):
        """Test complete data storage and retrieval pipeline."""
        fixtures = DatabaseFixtures()

        # Generate complete dataset
        result = await generate_complete_test_dataset(test_db)

        # Verify data was created
        async with test_db.acquire() as conn:
            # Check symbols
            symbol_count = await conn.fetchval("SELECT COUNT(*) FROM trading.symbols")
            assert symbol_count == len(result["symbols"])

            # Check market data
            market_count = await conn.fetchval(
                "SELECT COUNT(*) FROM trading.market_data"
            )
            assert market_count > 0

            # Check system events
            event_count = await conn.fetchval(
                "SELECT COUNT(*) FROM trading.system_events"
            )
            assert event_count == result["events_count"]

    @pytest.mark.asyncio
    async def test_market_data_aggregation(self, test_db):
        """Test market data aggregation queries."""
        fixtures = DatabaseFixtures()

        # Create market data
        symbol = "EURUSD"
        start_time = datetime.utcnow() - timedelta(hours=24)

        async with test_db.acquire() as conn:
            # Create symbol
            await fixtures.create_test_symbols(conn)

            # Create 1-minute bars
            await fixtures.create_test_market_data(
                conn, symbol, start_time, num_bars=1440, timeframe_minutes=1
            )

            # Test aggregation to 5-minute bars
            rows = await conn.fetch(
                """
                SELECT
                    date_trunc('hour', time) +
                    interval '5 min' * floor(date_part('minute', time)::int / 5) as bucket,
                    symbol,
                    FIRST(open, time) as open,
                    MAX(high) as high,
                    MIN(low) as low,
                    LAST(close, time) as close,
                    SUM(volume) as volume
                FROM trading.market_data
                WHERE symbol = $1 AND time >= $2
                GROUP BY bucket, symbol
                ORDER BY bucket
            """,
                symbol,
                start_time,
            )

            # Should have ~288 5-minute bars (24 hours * 12 bars/hour)
            assert len(rows) > 280
            assert len(rows) < 300

            # Verify aggregation logic
            first_bar = dict(rows[0])
            assert first_bar["volume"] > 0
            assert first_bar["high"] >= first_bar["low"]
            assert first_bar["high"] >= first_bar["open"]
            assert first_bar["high"] >= first_bar["close"]

    @pytest.mark.asyncio
    async def test_concurrent_writes(self, test_db):
        """Test concurrent database writes."""
        fixtures = DatabaseFixtures()

        async with test_db.acquire() as conn:
            await fixtures.create_test_symbols(conn)

        # Create multiple concurrent writers
        async def write_market_data(symbol: str, writer_id: int):
            async with test_db.acquire() as conn:
                base_time = datetime.utcnow()
                for i in range(100):
                    await conn.execute(
                        """
                        INSERT INTO trading.market_data
                        (time, symbol, open, high, low, close, volume)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (time, symbol) DO NOTHING
                    """,
                        base_time + timedelta(seconds=i),
                        symbol,
                        Decimal("1.0850") + Decimal(str(writer_id * 0.0001)),
                        Decimal("1.0855") + Decimal(str(writer_id * 0.0001)),
                        Decimal("1.0845") + Decimal(str(writer_id * 0.0001)),
                        Decimal("1.0852") + Decimal(str(writer_id * 0.0001)),
                        1000 * writer_id,
                    )

        # Run concurrent writes
        tasks = []
        for i in range(5):  # 5 concurrent writers
            for symbol in ["EURUSD", "GBPUSD"]:
                tasks.append(write_market_data(symbol, i))

        await asyncio.gather(*tasks)

        # Verify all writes completed
        async with test_db.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(DISTINCT (time, symbol)) FROM trading.market_data"
            )
            # Should have 100 time points * 2 symbols = 200 unique entries
            assert count == 200

    @pytest.mark.asyncio
    async def test_transaction_rollback(self, test_db):
        """Test transaction rollback behavior."""
        async with test_db.acquire() as conn:
            # Start transaction
            async with conn.transaction():
                # Insert test data
                await conn.execute(
                    """
                    INSERT INTO trading.symbols (symbol, pip_size, min_tick_size)
                    VALUES ('TESTEUR', 0.0001, 0.00001)
                """
                )

                # Verify insert within transaction
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM trading.symbols WHERE symbol = 'TESTEUR'"
                )
                assert count == 1

                # Force rollback
                raise asyncpg.exceptions.PostgresError("Forced rollback")

        # Verify rollback worked
        async with test_db.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM trading.symbols WHERE symbol = 'TESTEUR'"
            )
            assert count == 0

    @pytest.mark.asyncio
    async def test_query_performance(self, test_db, performance_benchmark):
        """Test database query performance."""
        fixtures = DatabaseFixtures()

        # Create large dataset
        async with test_db.acquire() as conn:
            await fixtures.create_test_symbols(conn)

            # Create 10,000 market data points
            start_time = datetime.utcnow() - timedelta(days=7)
            await fixtures.create_test_market_data(
                conn, "EURUSD", start_time, num_bars=10000, timeframe_minutes=1
            )

        # Benchmark queries
        async with test_db.acquire() as conn:
            # Simple select
            performance_benchmark.start("simple_select")
            rows = await conn.fetch(
                "SELECT * FROM trading.market_data WHERE symbol = 'EURUSD' LIMIT 1000"
            )
            performance_benchmark.stop("simple_select")
            assert len(rows) == 1000

            # Aggregation query
            performance_benchmark.start("aggregation")
            rows = await conn.fetch(
                """
                SELECT
                    date_trunc('hour', time) as hour,
                    AVG(close) as avg_close,
                    MAX(high) as max_high,
                    MIN(low) as min_low,
                    SUM(volume) as total_volume
                FROM trading.market_data
                WHERE symbol = 'EURUSD'
                GROUP BY hour
                ORDER BY hour
            """
            )
            performance_benchmark.stop("aggregation")
            assert len(rows) > 0

            # Complex join (if tables exist)
            performance_benchmark.start("complex_query")
            rows = await conn.fetch(
                """
                SELECT
                    md.time,
                    md.symbol,
                    md.close,
                    s.pip_size,
                    md.close / s.pip_size as pips_from_base
                FROM trading.market_data md
                JOIN trading.symbols s ON md.symbol = s.symbol
                WHERE md.symbol = 'EURUSD'
                ORDER BY md.time DESC
                LIMIT 100
            """
            )
            performance_benchmark.stop("complex_query")
            assert len(rows) == 100

        # Check performance
        simple_time = performance_benchmark.get_duration("simple_select")
        agg_time = performance_benchmark.get_duration("aggregation")
        complex_time = performance_benchmark.get_duration("complex_query")

        # Performance assertions
        assert simple_time < 0.1, f"Simple select too slow: {simple_time:.3f}s"
        assert agg_time < 0.5, f"Aggregation too slow: {agg_time:.3f}s"
        assert complex_time < 0.2, f"Complex query too slow: {complex_time:.3f}s"

    @pytest.mark.asyncio
    async def test_connection_pool_behavior(self, test_db):
        """Test connection pool behavior under load."""
        # Get pool stats
        stats_before = {
            "size": test_db.get_size(),
            "free_size": test_db.get_free_size(),
            "used_size": test_db.get_size() - test_db.get_free_size(),
        }

        # Create many concurrent connections
        async def use_connection(duration: float):
            async with test_db.acquire() as conn:
                await conn.fetchval("SELECT 1")
                await asyncio.sleep(duration)

        # Run 20 concurrent tasks
        tasks = [use_connection(0.1) for _ in range(20)]
        await asyncio.gather(*tasks)

        # Check pool didn't grow beyond max_size
        stats_after = {
            "size": test_db.get_size(),
            "free_size": test_db.get_free_size(),
            "used_size": test_db.get_size() - test_db.get_free_size(),
        }

        assert stats_after["size"] <= 5  # max_size from fixture
        assert stats_after["free_size"] == stats_after["size"]  # All returned

    @pytest.mark.asyncio
    async def test_data_consistency(self, test_db):
        """Test data consistency with concurrent operations."""
        symbol = "EURUSD"

        async with test_db.acquire() as conn:
            # Create symbol
            await conn.execute(
                """
                INSERT INTO trading.symbols (symbol, pip_size, min_tick_size)
                VALUES ($1, 0.0001, 0.00001)
            """,
                symbol,
            )

            # Create initial balance
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trading.account_balance (
                    id SERIAL PRIMARY KEY,
                    balance DECIMAL(20,2),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """
            )

            await conn.execute(
                """
                INSERT INTO trading.account_balance (balance) VALUES (10000.00)
            """
            )

        # Concurrent balance updates
        async def update_balance(amount: Decimal):
            async with test_db.acquire() as conn:
                async with conn.transaction():
                    # Read current balance
                    current = await conn.fetchval(
                        "SELECT balance FROM trading.account_balance WHERE id = 1"
                    )

                    # Simulate processing delay
                    await asyncio.sleep(0.01)

                    # Update balance
                    new_balance = current + amount
                    await conn.execute(
                        "UPDATE trading.account_balance SET balance = $1 WHERE id = 1",
                        new_balance,
                    )

        # Run concurrent updates
        updates = [
            update_balance(Decimal("100")),
            update_balance(Decimal("-50")),
            update_balance(Decimal("200")),
            update_balance(Decimal("-150")),
            update_balance(Decimal("300")),
        ]

        await asyncio.gather(*updates)

        # Verify final balance
        async with test_db.acquire() as conn:
            final_balance = await conn.fetchval(
                "SELECT balance FROM trading.account_balance WHERE id = 1"
            )

            # Should be 10000 + 100 - 50 + 200 - 150 + 300 = 10400
            assert final_balance == Decimal("10400.00")

    @pytest.mark.asyncio
    async def test_event_logging_performance(self, test_db, performance_benchmark):
        """Test high-frequency event logging performance."""
        num_events = 1000

        performance_benchmark.start("event_logging")

        async def log_event(event_num: int):
            async with test_db.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO trading.system_events
                    (event_time, service_name, event_type, severity, message, details)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """,
                    datetime.utcnow(),
                    "test-service",
                    "test_event",
                    "info",
                    f"Test event {event_num}",
                    {"event_num": event_num, "test": True},
                )

        # Log events concurrently
        tasks = [log_event(i) for i in range(num_events)]
        await asyncio.gather(*tasks)

        performance_benchmark.stop("event_logging")

        # Verify all events logged
        async with test_db.acquire() as conn:
            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM trading.system_events
                WHERE service_name = 'test-service'
            """
            )
            assert count == num_events

        # Check performance
        duration = performance_benchmark.get_duration("event_logging")
        events_per_second = num_events / duration

        print(f"\nEvent logging rate: {events_per_second:.0f} events/second")
        assert (
            events_per_second > 100
        ), f"Event logging too slow: {events_per_second:.0f} events/s"
