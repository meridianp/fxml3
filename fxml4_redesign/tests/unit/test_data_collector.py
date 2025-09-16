"""Unit tests for Data Collector Service."""

import asyncio
import json
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, call, patch

import pandas as pd
import pytest
from services.data_collector.data_aggregator import DataAggregator
from services.data_collector.indicator_calculator import IndicatorCalculator
from services.data_collector.main import DataCollectorService


class TestDataCollectorService:
    """Test DataCollectorService functionality."""

    @pytest.fixture
    def data_collector(
        self,
        test_config,
        mock_db_pool,
        mock_rabbitmq_connection,
        mock_redis_client,
        mock_ib_gateway_client,
    ):
        """Create DataCollectorService with mocks."""
        service = DataCollectorService(test_config)

        # Inject mocks
        service.db_pool = mock_db_pool
        service.rabbitmq_connection, service.rabbitmq_channel = mock_rabbitmq_connection
        service.redis_client = mock_redis_client
        service.ib_client = mock_ib_gateway_client

        return service

    def test_initialization(self, test_config):
        """Test service initialization."""
        service = DataCollectorService(test_config)

        assert service.service_name == "data-collector"
        assert isinstance(service.aggregator, DataAggregator)
        assert isinstance(service.indicator_calculator, IndicatorCalculator)
        assert service.all_symbols == []
        assert len(service.active_symbols) == 0
        assert service.slow_interval == 300
        assert service.fast_interval == 30
        assert service.buffer_size == 100

    @pytest.mark.asyncio
    async def test_service_setup(self, data_collector, mock_db_pool):
        """Test service setup."""
        # Mock database response for symbols
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch.return_value = [
            {
                "symbol": "EURUSD",
                "pip_size": Decimal("0.0001"),
                "min_tick_size": Decimal("0.00001"),
            },
            {
                "symbol": "GBPUSD",
                "pip_size": Decimal("0.0001"),
                "min_tick_size": Decimal("0.00001"),
            },
        ]

        # Mock RabbitMQ setup
        data_collector.setup_rabbitmq = AsyncMock()

        await data_collector.service_setup()

        # Verify IB client connection
        data_collector.ib_client.connect.assert_called_once()

        # Verify symbols loaded
        assert data_collector.all_symbols == ["EURUSD", "GBPUSD"]

        # Verify subscriptions
        assert data_collector.ib_client.subscribe_market_data.call_count == 2
        data_collector.ib_client.subscribe_market_data.assert_any_call("EURUSD")
        data_collector.ib_client.subscribe_market_data.assert_any_call("GBPUSD")

        # Verify RabbitMQ setup
        data_collector.setup_rabbitmq.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_symbols(self, data_collector, mock_db_pool):
        """Test loading symbols from database."""
        # Mock database response
        mock_rows = [
            {
                "symbol": "EURUSD",
                "pip_size": Decimal("0.0001"),
                "min_tick_size": Decimal("0.00001"),
            },
            {
                "symbol": "GBPUSD",
                "pip_size": Decimal("0.0001"),
                "min_tick_size": Decimal("0.00001"),
            },
            {
                "symbol": "USDJPY",
                "pip_size": Decimal("0.01"),
                "min_tick_size": Decimal("0.001"),
            },
        ]
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch.return_value = (
            mock_rows
        )

        await data_collector.load_symbols()

        # Verify symbols loaded
        assert data_collector.all_symbols == ["EURUSD", "GBPUSD", "USDJPY"]

        # Verify cache was populated
        assert data_collector.redis_client.setex.call_count == 3

        # Check cache calls
        for row in mock_rows:
            expected_key = f"symbol:info:{row['symbol']}"
            expected_value = json.dumps(
                {
                    "pip_size": float(row["pip_size"]),
                    "min_tick_size": float(row["min_tick_size"]),
                }
            )

            # Find the matching call
            found = False
            for call_args in data_collector.redis_client.setex.call_args_list:
                if (
                    call_args[0][0] == expected_key
                    and call_args[0][2] == expected_value
                ):
                    found = True
                    break
            assert found, f"Cache not set for {row['symbol']}"

    @pytest.mark.asyncio
    async def test_subscribe_symbols_with_errors(self, data_collector):
        """Test symbol subscription with some failures."""
        # Make second subscription fail
        data_collector.ib_client.subscribe_market_data.side_effect = [
            None,  # Success
            Exception("Subscription failed"),  # Failure
            None,  # Success
        ]

        symbols = ["EURUSD", "GBPUSD", "USDJPY"]
        await data_collector.subscribe_symbols(symbols)

        # All symbols should be attempted
        assert data_collector.ib_client.subscribe_market_data.call_count == 3

    @pytest.mark.asyncio
    async def test_store_market_data(
        self, data_collector, mock_db_pool, sample_market_data
    ):
        """Test storing market data."""
        await data_collector.store_market_data("EURUSD", sample_market_data)

        # Verify database insert
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.execute.assert_called_once()

        # Check SQL
        call_args = conn.execute.call_args
        sql = call_args[0][0]
        assert "INSERT INTO trading.market_data" in sql
        assert "ON CONFLICT" in sql

        # Check parameters
        params = call_args[0][1:]
        assert params[0] == sample_market_data["time"]
        assert params[1] == "EURUSD"
        assert params[2] == sample_market_data["open"]

    @pytest.mark.asyncio
    async def test_calculate_and_store_indicators(self, data_collector, mock_db_pool):
        """Test indicator calculation and storage."""
        # Mock market data from database
        mock_rows = []
        base_time = datetime.utcnow()
        for i in range(100):
            mock_rows.append(
                {
                    "time": base_time - timedelta(hours=i),
                    "open": 1.0850 + i * 0.0001,
                    "high": 1.0855 + i * 0.0001,
                    "low": 1.0845 + i * 0.0001,
                    "close": 1.0852 + i * 0.0001,
                    "volume": 1000 + i * 10,
                }
            )

        mock_db_pool.acquire.return_value.__aenter__.return_value.fetch.return_value = (
            mock_rows
        )

        # Mock indicator calculation
        with patch.object(
            data_collector.indicator_calculator, "calculate_all"
        ) as mock_calc:
            # Create mock indicator dataframe
            mock_indicators = pd.DataFrame(
                [
                    {
                        "rsi_14": 55.5,
                        "atr_14": 0.0012,
                        "sma_20": 1.0848,
                        "sma_50": 1.0845,
                        "sma_200": 1.0840,
                        "ema_9": 1.0849,
                        "ema_21": 1.0847,
                        "bb_upper": 1.0860,
                        "bb_middle": 1.0848,
                        "bb_lower": 1.0836,
                        "macd": 0.0002,
                        "macd_signal": 0.0001,
                        "macd_histogram": 0.0001,
                        "adx": 25.5,
                        "plus_di": 22.3,
                        "minus_di": 18.7,
                        "stoch_k": 65.2,
                        "stoch_d": 62.8,
                    }
                ],
                index=[base_time],
            )

            mock_calc.return_value = mock_indicators

            await data_collector.calculate_and_store_indicators("EURUSD", "4H")

        # Verify indicator storage
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        assert conn.execute.call_count == 1

        # Verify cache update
        data_collector.redis_client.setex.assert_called()

    @pytest.mark.asyncio
    async def test_publish_market_update(self, data_collector, sample_market_data):
        """Test publishing market updates."""
        # Mock indicator cache
        mock_indicators = {"rsi_14": 55.5, "macd": 0.0002}
        data_collector.cache_json_get = AsyncMock(return_value=mock_indicators)

        # Mock publish_message
        data_collector.publish_message = AsyncMock()

        # Test 4H update
        await data_collector.publish_market_update("EURUSD", sample_market_data, "4H")

        # Verify message published
        data_collector.publish_message.assert_called_once()
        call_args = data_collector.publish_message.call_args

        assert call_args[0][0] == "market.data"  # Exchange
        assert "market.ready.EURUSD" in call_args[0][1]  # Routing key

        message = call_args[0][2]
        assert message["symbol"] == "EURUSD"
        assert message["timeframe"] == "4H"
        assert message["data"] == sample_market_data
        assert message["indicators"] == mock_indicators

    @pytest.mark.asyncio
    async def test_publish_tick_stream(self, data_collector, sample_tick_data):
        """Test publishing tick stream."""
        data_collector.publish_message = AsyncMock()

        await data_collector.publish_tick_stream("EURUSD", sample_tick_data)

        # Verify message published
        data_collector.publish_message.assert_called_once()
        call_args = data_collector.publish_message.call_args

        assert call_args[0][0] == "market.data"  # Exchange
        assert "market.tick.EURUSD" in call_args[0][1]  # Routing key

        message = call_args[0][2]
        assert message["symbol"] == "EURUSD"
        assert message["ticks"] == sample_tick_data
        assert message["count"] == len(sample_tick_data)

    @pytest.mark.asyncio
    async def test_flush_tick_buffer(self, data_collector, mock_db_pool):
        """Test flushing tick buffer to database."""
        # Add ticks to buffer
        base_time = datetime.utcnow()
        data_collector.tick_buffer = [
            {
                "symbol": "EURUSD",
                "time": base_time,
                "price": 1.0850,
                "size": 100,
                "type": "trade",
            },
            {
                "symbol": "EURUSD",
                "time": base_time + timedelta(seconds=1),
                "price": 1.0851,
                "size": 200,
                "type": "trade",
            },
            {
                "symbol": "GBPUSD",
                "time": base_time,
                "price": 1.2650,
                "size": 150,
                "type": "trade",
            },
        ]

        # Mock aggregator
        with patch.object(
            data_collector.aggregator, "aggregate_ticks_to_seconds"
        ) as mock_agg:
            mock_agg.return_value = [
                (base_time, "EURUSD", 1.0850, 1.0851, 1.0850, 1.0851, 300, 2)
            ]

            await data_collector.flush_tick_buffer()

        # Verify buffer cleared
        assert len(data_collector.tick_buffer) == 0

        # Verify database insert
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.executemany.assert_called()

    @pytest.mark.asyncio
    async def test_check_symbol_activation(self, data_collector, mock_db_pool):
        """Test symbol activation logic."""
        # Mock database responses
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value

        # Test activation due to recent signals
        conn.fetchval.side_effect = [5, 0]  # 5 recent signals, 0 trades

        await data_collector.check_symbol_activation("EURUSD")

        assert "EURUSD" in data_collector.active_symbols

        # Reset
        data_collector.active_symbols.clear()
        conn.fetchval.side_effect = [0, 2]  # 0 signals, 2 active trades

        await data_collector.check_symbol_activation("GBPUSD")

        assert "GBPUSD" in data_collector.active_symbols

    @pytest.mark.asyncio
    async def test_slow_collection_loop(self, data_collector):
        """Test slow collection loop iteration."""
        data_collector.all_symbols = ["EURUSD", "GBPUSD"]
        data_collector.running = True

        # Mock methods
        data_collector.ib_client.get_market_data.return_value = {
            "time": datetime.utcnow(),
            "open": 1.0850,
            "high": 1.0855,
            "low": 1.0845,
            "close": 1.0852,
            "volume": 1000,
        }

        data_collector.store_market_data = AsyncMock()
        data_collector.calculate_and_store_indicators = AsyncMock()
        data_collector.publish_market_update = AsyncMock()

        # Run one iteration
        async def run_one_iteration():
            task = asyncio.create_task(data_collector.slow_collection_loop())
            await asyncio.sleep(0.1)  # Let it run briefly
            data_collector.running = False
            await asyncio.sleep(0.1)  # Let it finish
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await run_one_iteration()

        # Verify data collection for all symbols
        assert data_collector.ib_client.get_market_data.call_count >= 2
        assert data_collector.store_market_data.call_count >= 2
        assert data_collector.calculate_and_store_indicators.call_count >= 2
        assert data_collector.publish_market_update.call_count >= 2

    @pytest.mark.asyncio
    async def test_fast_collection_loop(self, data_collector):
        """Test fast collection loop iteration."""
        data_collector.active_symbols = {"EURUSD"}
        data_collector.running = True

        # Mock methods
        data_collector.ib_client.get_tick_data.return_value = [
            {"time": datetime.utcnow(), "price": 1.0850, "size": 100}
        ]
        data_collector.ib_client.get_market_data.return_value = {
            "time": datetime.utcnow(),
            "close": 1.0850,
        }

        data_collector.store_market_data = AsyncMock()
        data_collector.publish_tick_stream = AsyncMock()
        data_collector.publish_market_update = AsyncMock()

        # Run one iteration
        async def run_one_iteration():
            task = asyncio.create_task(data_collector.fast_collection_loop())
            await asyncio.sleep(0.1)
            data_collector.running = False
            await asyncio.sleep(0.1)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await run_one_iteration()

        # Verify fast collection
        assert data_collector.ib_client.get_tick_data.called
        assert len(data_collector.tick_buffer) > 0  # Ticks added to buffer

    @pytest.mark.asyncio
    async def test_heartbeat_loop(self, data_collector):
        """Test heartbeat loop."""
        data_collector.running = True
        data_collector.active_symbols = {"EURUSD", "GBPUSD"}
        data_collector.all_symbols = ["EURUSD", "GBPUSD", "USDJPY"]

        data_collector.publish_message = AsyncMock()
        data_collector.health_check = AsyncMock(return_value={"status": "healthy"})

        # Run one iteration
        async def run_one_iteration():
            task = asyncio.create_task(data_collector.heartbeat_loop())
            await asyncio.sleep(0.1)
            data_collector.running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await run_one_iteration()

        # Should publish heartbeat and metrics
        assert data_collector.publish_message.call_count >= 2

        # Check heartbeat message
        heartbeat_call = None
        for call_args in data_collector.publish_message.call_args_list:
            if "system.heartbeat" in call_args[0][1]:
                heartbeat_call = call_args
                break

        assert heartbeat_call is not None
        message = heartbeat_call[0][2]
        assert message["active_symbols"] == ["EURUSD", "GBPUSD"]
        assert message["total_symbols"] == 3

    @pytest.mark.asyncio
    async def test_error_handling_in_loops(self, data_collector):
        """Test error handling in collection loops."""
        data_collector.all_symbols = ["EURUSD"]
        data_collector.running = True

        # Make market data fail
        data_collector.ib_client.get_market_data.side_effect = Exception(
            "Connection error"
        )
        data_collector.log_error = AsyncMock()

        # Run slow collection briefly
        async def run_with_error():
            task = asyncio.create_task(data_collector.slow_collection_loop())
            await asyncio.sleep(0.1)
            data_collector.running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await run_with_error()

        # Verify error was logged
        data_collector.log_error.assert_called()
        error_arg = data_collector.log_error.call_args[0][0]
        assert str(error_arg) == "Connection error"


class TestDataCollectorIntegration:
    """Integration tests for DataCollectorService."""

    @pytest.mark.asyncio
    async def test_symbol_activation_deactivation(self, data_collector, mock_db_pool):
        """Test symbol activation and deactivation cycle."""
        data_collector.all_symbols = ["EURUSD", "GBPUSD"]

        # Mock database to activate EURUSD
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchval.side_effect = [1, 0]  # Signal for EURUSD

        await data_collector.check_symbol_activation("EURUSD")
        assert "EURUSD" in data_collector.active_symbols

        # Set last update time to trigger deactivation
        data_collector.symbol_last_update["EURUSD"] = datetime.utcnow() - timedelta(
            hours=1
        )

        # Run symbol activation loop once
        data_collector.running = True

        async def run_activation_check():
            task = asyncio.create_task(data_collector.symbol_activation_loop())
            await asyncio.sleep(0.1)
            data_collector.running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Mock no active signals/trades
        conn.fetchval.side_effect = [0, 0, 0, 0]

        await run_activation_check()

        # EURUSD should be deactivated due to staleness
        assert "EURUSD" not in data_collector.active_symbols

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_tick_processing_performance(
        self, data_collector, performance_benchmark
    ):
        """Benchmark tick processing performance."""
        # Generate large number of ticks
        num_ticks = 10000
        base_time = datetime.utcnow()

        performance_benchmark.start("tick_processing")

        # Add ticks to buffer
        for i in range(num_ticks):
            data_collector.tick_buffer.append(
                {
                    "symbol": "EURUSD",
                    "time": base_time + timedelta(milliseconds=i),
                    "price": Decimal("1.0850") + Decimal(str(i * 0.00001)),
                    "size": 100 + i,
                    "type": "trade",
                }
            )

        # Mock aggregator
        with patch.object(
            data_collector.aggregator, "aggregate_ticks_to_seconds"
        ) as mock_agg:
            mock_agg.return_value = []  # Empty aggregation result

            # Process buffer
            await data_collector.flush_tick_buffer()

        performance_benchmark.stop("tick_processing")

        # Verify buffer cleared
        assert len(data_collector.tick_buffer) == 0

        # Check performance
        duration = performance_benchmark.get_duration("tick_processing")
        assert duration < 0.5, f"Processing {num_ticks} ticks took {duration:.2f}s"
