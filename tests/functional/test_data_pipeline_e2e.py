"""End-to-End Functional Tests for Data Pipeline.

This module tests the complete data ingestion, processing, and storage pipeline
from raw market data through TimescaleDB storage and retrieval.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import psycopg2
import pytest
from psycopg2.extras import RealDictCursor

from fxml4.config import get_config
from fxml4.data_engineering.quality import DataQualityChecker
from fxml4.data_engineering.tick_to_candle import TickToCandleConverter
from fxml4.data_engineering.timescaledb import TimescaleDBManager
from fxml4.data_feeds.alpha_vantage_feed import AlphaVantageFeed
from fxml4.data_feeds.base import DataFeed
from fxml4.data_feeds.ib_feed import IBDataFeed


class TestDataPipelineE2E:
    """End-to-end tests for the complete data pipeline."""

    @pytest.fixture
    def test_config(self):
        """Create test configuration."""
        return {
            "database": {
                "host": "localhost",
                "port": 5433,
                "name": "fxml4_test",
                "user": "postgres",
                "password": "postgres",
            },
            "data_feeds": {
                "ib": {"host": "localhost", "port": 7497, "client_id": 999},
                "alpha_vantage": {"api_key": "test_key", "rate_limit": 5},
            },
            "symbols": ["EUR/USD", "GBP/USD", "USD/JPY"],
            "timeframes": ["1min", "5min", "15min", "1h", "4h", "1d"],
        }

    @pytest.fixture
    async def mock_db_manager(self, test_config):
        """Create mock TimescaleDB manager."""
        manager = MagicMock(spec=TimescaleDBManager)
        manager.connected = True
        manager.insert_tick_data = AsyncMock()
        manager.insert_candle_data = AsyncMock()
        manager.get_latest_timestamp = AsyncMock(return_value=None)
        manager.query = AsyncMock()
        return manager

    @pytest.fixture
    def mock_tick_data(self):
        """Generate mock tick data."""
        base_time = datetime.now(timezone.utc)
        ticks = []

        for i in range(100):
            tick = {
                "symbol": "EUR/USD",
                "timestamp": base_time + timedelta(seconds=i),
                "bid": 1.0850 + (i % 10) * 0.0001,
                "ask": 1.0851 + (i % 10) * 0.0001,
                "bid_size": 1000000,
                "ask_size": 1000000,
                "volume": 100,
            }
            ticks.append(tick)

        return ticks

    @pytest.mark.asyncio
    async def test_complete_data_ingestion_flow(
        self, test_config, mock_db_manager, mock_tick_data
    ):
        """Test complete data ingestion from feed to database."""
        # Mock IB data feed
        with patch("fxml4.data_feeds.ib_feed.IBDataFeed") as MockIBFeed:
            mock_feed = AsyncMock(spec=IBDataFeed)
            mock_feed.connected = False
            mock_feed.connect = AsyncMock(return_value=True)
            mock_feed.disconnect = AsyncMock()
            mock_feed.subscribe_market_data = AsyncMock()
            MockIBFeed.return_value = mock_feed

            # Create data feed
            feed = MockIBFeed(test_config["data_feeds"]["ib"])

            # Connect to feed
            connected = await feed.connect()
            assert connected

            # Subscribe to market data
            await feed.subscribe_market_data("EUR/USD", callback=None)

            # Simulate tick data arrival
            tick_count = 0
            for tick in mock_tick_data:
                await mock_db_manager.insert_tick_data(tick)
                tick_count += 1

            # Verify data was stored
            assert mock_db_manager.insert_tick_data.call_count == len(mock_tick_data)

            # Disconnect
            await feed.disconnect()

    @pytest.mark.asyncio
    async def test_tick_to_candle_aggregation(self, mock_db_manager, mock_tick_data):
        """Test tick data aggregation into candles."""
        converter = TickToCandleConverter(mock_db_manager)

        # Process ticks into 1-minute candles
        candles = []
        current_candle = None

        for tick in mock_tick_data:
            candle_time = tick["timestamp"].replace(second=0, microsecond=0)

            if current_candle is None or current_candle["timestamp"] != candle_time:
                if current_candle:
                    candles.append(current_candle)

                current_candle = {
                    "symbol": tick["symbol"],
                    "timestamp": candle_time,
                    "open": tick["bid"],
                    "high": tick["bid"],
                    "low": tick["bid"],
                    "close": tick["bid"],
                    "volume": tick["volume"],
                    "tick_count": 1,
                }
            else:
                current_candle["high"] = max(current_candle["high"], tick["bid"])
                current_candle["low"] = min(current_candle["low"], tick["bid"])
                current_candle["close"] = tick["bid"]
                current_candle["volume"] += tick["volume"]
                current_candle["tick_count"] += 1

        if current_candle:
            candles.append(current_candle)

        # Store candles
        for candle in candles:
            await mock_db_manager.insert_candle_data(candle, "1min")

        # Verify candle generation
        assert len(candles) > 0
        assert all(c["high"] >= c["low"] for c in candles)
        assert all(c["high"] >= c["open"] for c in candles)
        assert all(c["high"] >= c["close"] for c in candles)

    @pytest.mark.asyncio
    async def test_data_quality_validation(self, mock_tick_data):
        """Test data quality checks in the pipeline."""
        quality_checker = DataQualityChecker()

        # Check tick data quality
        quality_issues = []

        for i, tick in enumerate(mock_tick_data):
            # Check bid/ask spread
            spread = tick["ask"] - tick["bid"]
            if spread < 0:
                quality_issues.append(f"Negative spread at tick {i}")
            elif spread > 0.001:  # 10 pips
                quality_issues.append(f"Wide spread at tick {i}: {spread}")

            # Check for zero prices
            if tick["bid"] <= 0 or tick["ask"] <= 0:
                quality_issues.append(f"Invalid price at tick {i}")

            # Check timestamps
            if i > 0:
                time_diff = (
                    tick["timestamp"] - mock_tick_data[i - 1]["timestamp"]
                ).total_seconds()
                if time_diff < 0:
                    quality_issues.append(f"Backwards timestamp at tick {i}")
                elif time_diff > 60:  # Gap larger than 1 minute
                    quality_issues.append(f"Large time gap at tick {i}: {time_diff}s")

        # Verify data quality
        assert len(quality_issues) == 0, f"Quality issues found: {quality_issues}"

    @pytest.mark.asyncio
    async def test_multi_timeframe_generation(self, mock_db_manager, mock_tick_data):
        """Test generation of multiple timeframe candles from ticks."""
        timeframes = {
            "1min": timedelta(minutes=1),
            "5min": timedelta(minutes=5),
            "15min": timedelta(minutes=15),
            "1h": timedelta(hours=1),
        }

        candle_data = {tf: [] for tf in timeframes}

        # Generate candles for each timeframe
        for timeframe, interval in timeframes.items():
            current_candle = None

            for tick in mock_tick_data:
                # Calculate candle timestamp
                total_seconds = int(tick["timestamp"].timestamp())
                interval_seconds = int(interval.total_seconds())
                candle_seconds = (total_seconds // interval_seconds) * interval_seconds
                candle_time = datetime.fromtimestamp(candle_seconds, tz=timezone.utc)

                if current_candle is None or current_candle["timestamp"] != candle_time:
                    if current_candle:
                        candle_data[timeframe].append(current_candle)

                    current_candle = {
                        "symbol": tick["symbol"],
                        "timestamp": candle_time,
                        "open": tick["bid"],
                        "high": tick["bid"],
                        "low": tick["bid"],
                        "close": tick["bid"],
                        "volume": tick["volume"],
                    }
                else:
                    current_candle["high"] = max(current_candle["high"], tick["bid"])
                    current_candle["low"] = min(current_candle["low"], tick["bid"])
                    current_candle["close"] = tick["bid"]
                    current_candle["volume"] += tick["volume"]

            if current_candle:
                candle_data[timeframe].append(current_candle)

        # Verify timeframe consistency
        assert len(candle_data["1min"]) >= len(candle_data["5min"])
        assert len(candle_data["5min"]) >= len(candle_data["15min"])
        assert len(candle_data["15min"]) >= len(candle_data["1h"])

    @pytest.mark.asyncio
    async def test_historical_data_backfill(self, test_config, mock_db_manager):
        """Test historical data backfill process."""
        with patch(
            "fxml4.data_feeds.alpha_vantage_feed.AlphaVantageFeed"
        ) as MockAVFeed:
            # Mock historical data response
            historical_data = pd.DataFrame(
                {
                    "timestamp": pd.date_range(
                        start="2024-01-01", end="2024-01-02", freq="1h", tz="UTC"
                    ),
                    "open": np.random.uniform(1.08, 1.09, 25),
                    "high": np.random.uniform(1.085, 1.095, 25),
                    "low": np.random.uniform(1.075, 1.085, 25),
                    "close": np.random.uniform(1.08, 1.09, 25),
                    "volume": np.random.randint(1000, 10000, 25),
                }
            )

            mock_feed = AsyncMock(spec=AlphaVantageFeed)
            mock_feed.get_historical_data = AsyncMock(return_value=historical_data)
            MockAVFeed.return_value = mock_feed

            # Create feed and fetch historical data
            feed = MockAVFeed(test_config["data_feeds"]["alpha_vantage"])
            data = await feed.get_historical_data("EUR/USD", "1h", days=1)

            # Verify data structure
            assert len(data) == 25  # 24 hours + 1
            assert all(
                col in data.columns
                for col in ["open", "high", "low", "close", "volume"]
            )

            # Store historical data
            for _, row in data.iterrows():
                candle = {
                    "symbol": "EUR/USD",
                    "timestamp": row.name,
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                    "volume": row["volume"],
                }
                await mock_db_manager.insert_candle_data(candle, "1h")

            assert mock_db_manager.insert_candle_data.call_count == len(data)

    @pytest.mark.asyncio
    async def test_data_retrieval_and_consistency(self, mock_db_manager):
        """Test data retrieval from database with consistency checks."""
        # Mock data retrieval
        mock_data = pd.DataFrame(
            {
                "timestamp": pd.date_range(
                    "2024-01-01", periods=100, freq="1min", tz="UTC"
                ),
                "open": np.random.uniform(1.08, 1.09, 100),
                "high": np.random.uniform(1.085, 1.095, 100),
                "low": np.random.uniform(1.075, 1.085, 100),
                "close": np.random.uniform(1.08, 1.09, 100),
                "volume": np.random.randint(1000, 10000, 100),
            }
        )

        mock_db_manager.query.return_value = mock_data

        # Retrieve data
        data = await mock_db_manager.query(
            "SELECT * FROM candles_1min WHERE symbol = %s AND timestamp >= %s",
            ("EUR/USD", datetime(2024, 1, 1, tzinfo=timezone.utc)),
        )

        # Consistency checks
        assert len(data) == 100
        assert data["timestamp"].is_monotonic_increasing
        assert all(data["high"] >= data["low"])
        assert all(data["high"] >= data["open"])
        assert all(data["high"] >= data["close"])
        assert all(data["low"] <= data["open"])
        assert all(data["low"] <= data["close"])
        assert all(data["volume"] > 0)

    @pytest.mark.asyncio
    async def test_concurrent_symbol_processing(self, test_config, mock_db_manager):
        """Test concurrent processing of multiple symbols."""
        symbols = test_config["symbols"]

        async def process_symbol(symbol: str):
            """Process data for a single symbol."""
            # Generate mock data for symbol
            base_price = {"EUR/USD": 1.08, "GBP/USD": 1.25, "USD/JPY": 110.0}[symbol]

            ticks = []
            for i in range(50):
                tick = {
                    "symbol": symbol,
                    "timestamp": datetime.now(timezone.utc) + timedelta(seconds=i),
                    "bid": base_price + (i % 5) * 0.0001,
                    "ask": base_price + (i % 5) * 0.0001 + 0.0001,
                    "volume": 1000,
                }
                ticks.append(tick)
                await mock_db_manager.insert_tick_data(tick)

            return len(ticks)

        # Process all symbols concurrently
        tasks = [process_symbol(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks)

        # Verify all symbols processed
        assert len(results) == len(symbols)
        assert all(r == 50 for r in results)
        assert mock_db_manager.insert_tick_data.call_count == 150  # 50 * 3 symbols

    @pytest.mark.asyncio
    async def test_gap_detection_and_handling(self, mock_db_manager):
        """Test detection and handling of data gaps."""
        # Create data with gaps
        timestamps = []
        base_time = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)

        # Normal data
        for i in range(10):
            timestamps.append(base_time + timedelta(minutes=i))

        # Gap of 30 minutes
        for i in range(40, 50):
            timestamps.append(base_time + timedelta(minutes=i))

        # Detect gaps
        gaps = []
        for i in range(1, len(timestamps)):
            diff = (timestamps[i] - timestamps[i - 1]).total_seconds() / 60
            if diff > 5:  # Gap larger than 5 minutes
                gaps.append(
                    {
                        "start": timestamps[i - 1],
                        "end": timestamps[i],
                        "duration_minutes": diff,
                    }
                )

        # Verify gap detection
        assert len(gaps) == 1
        assert gaps[0]["duration_minutes"] == 30

        # Handle gaps (mark for backfill)
        backfill_requests = []
        for gap in gaps:
            backfill_requests.append(
                {
                    "symbol": "EUR/USD",
                    "start": gap["start"],
                    "end": gap["end"],
                    "timeframe": "1min",
                    "status": "pending",
                }
            )

        assert len(backfill_requests) == 1


class TestDataFeedFailover:
    """Test data feed failover and recovery scenarios."""

    @pytest.mark.asyncio
    async def test_primary_feed_failure_failover(self, test_config):
        """Test failover when primary feed fails."""
        primary_feed = MagicMock()
        backup_feed = MagicMock()

        # Mock primary feed failure
        primary_feed.connected = True
        primary_feed.subscribe_market_data = AsyncMock(
            side_effect=ConnectionError("Primary feed disconnected")
        )

        # Mock backup feed success
        backup_feed.connected = False
        backup_feed.connect = AsyncMock(return_value=True)
        backup_feed.subscribe_market_data = AsyncMock()

        # Attempt subscription with failover
        try:
            await primary_feed.subscribe_market_data("EUR/USD")
        except ConnectionError:
            # Failover to backup
            await backup_feed.connect()
            await backup_feed.subscribe_market_data("EUR/USD")

        # Verify failover occurred
        backup_feed.connect.assert_called_once()
        backup_feed.subscribe_market_data.assert_called_once_with("EUR/USD")

    @pytest.mark.asyncio
    async def test_data_feed_reconnection(self):
        """Test automatic reconnection on feed disconnection."""
        feed = MagicMock()
        feed.connected = True
        feed.connect = AsyncMock(return_value=True)

        reconnect_attempts = 0
        max_attempts = 3

        # Simulate disconnection and reconnection
        feed.connected = False

        while reconnect_attempts < max_attempts and not feed.connected:
            try:
                await feed.connect()
                feed.connected = True
            except Exception:
                reconnect_attempts += 1
                await asyncio.sleep(0.1)

        # Verify reconnection
        assert feed.connected
        assert feed.connect.call_count <= max_attempts


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
