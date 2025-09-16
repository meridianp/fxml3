"""
Unit tests for Market Data Processing System.

Tests comprehensive market data functionality including:
- Real-time data ingestion from multiple sources
- Data normalization and validation
- Order book management
- Tick data processing
- Bar aggregation (OHLCV)
- Market depth analysis
- Data quality monitoring
- Latency tracking
- Symbol mapping
- Corporate actions handling
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from freezegun import freeze_time

from core.data.market_data_processor import (
    BarData,
    DataQualityMonitor,
    DataSource,
    MarketDataProcessor,
    MarketDataType,
    OrderBook,
    TickData,
)


class TestMarketDataProcessor:
    """Test suite for market data processing system."""

    @pytest.fixture
    def processor_config(self):
        """Configuration for market data processor."""
        return {
            "data_sources": {
                "primary": "interactive_brokers",
                "secondary": "polygon",
                "tertiary": "alpaca",
            },
            "symbols": ["EUR/USD", "GBP/USD", "USD/JPY", "BTC/USD"],
            "processing": {
                "normalize_timestamps": True,
                "validate_prices": True,
                "detect_outliers": True,
                "handle_gaps": True,
                "buffer_size": 10000,
            },
            "aggregation": {
                "timeframes": ["1m", "5m", "15m", "1h", "4h", "1d"],
                "volume_bars": True,
                "range_bars": True,
                "renko_bars": True,
            },
            "quality": {
                "max_spread_pct": 0.1,
                "max_latency_ms": 100,
                "min_tick_rate": 10,
                "stale_threshold_seconds": 5,
            },
            "storage": {
                "enable_persistence": True,
                "compression": "zstd",
                "retention_days": 30,
            },
        }

    @pytest.fixture
    def sample_tick_data(self):
        """Generate sample tick data."""
        return [
            TickData(
                symbol="EUR/USD",
                timestamp=datetime.now(),
                bid=Decimal("1.0500"),
                ask=Decimal("1.0502"),
                bid_size=1000000,
                ask_size=1500000,
                last=Decimal("1.0501"),
                volume=100000,
            ),
            TickData(
                symbol="EUR/USD",
                timestamp=datetime.now() + timedelta(milliseconds=100),
                bid=Decimal("1.0501"),
                ask=Decimal("1.0503"),
                bid_size=1200000,
                ask_size=1300000,
                last=Decimal("1.0502"),
                volume=150000,
            ),
        ]

    @pytest.fixture
    def sample_order_book(self):
        """Generate sample order book data."""
        return {
            "symbol": "EUR/USD",
            "timestamp": datetime.now(),
            "bids": [
                {"price": Decimal("1.0500"), "size": 1000000, "orders": 5},
                {"price": Decimal("1.0499"), "size": 2000000, "orders": 8},
                {"price": Decimal("1.0498"), "size": 1500000, "orders": 6},
            ],
            "asks": [
                {"price": Decimal("1.0502"), "size": 1500000, "orders": 7},
                {"price": Decimal("1.0503"), "size": 2500000, "orders": 10},
                {"price": Decimal("1.0504"), "size": 2000000, "orders": 8},
            ],
        }

    @pytest.fixture
    def market_data_processor(self, processor_config):
        """Create market data processor for testing."""
        return MarketDataProcessor(config=processor_config)

    @pytest.mark.asyncio
    async def test_connects_to_multiple_data_sources(self, market_data_processor):
        """Test connection to multiple data sources."""
        result = await market_data_processor.connect_all_sources()

        assert result["status"] == "connected"
        assert "sources" in result
        assert len(result["sources"]) == 3
        assert all(s["connected"] for s in result["sources"].values())
        assert result["primary_source"] == "interactive_brokers"

    @pytest.mark.asyncio
    async def test_ingests_real_time_tick_data(
        self, market_data_processor, sample_tick_data
    ):
        """Test real-time tick data ingestion."""
        for tick in sample_tick_data:
            result = await market_data_processor.process_tick(tick)

            assert result["status"] == "processed"
            assert "latency_ms" in result
            assert result["latency_ms"] < 10
            assert "normalized" in result
            assert result["normalized"] is True

    @pytest.mark.asyncio
    async def test_validates_and_normalizes_data(self, market_data_processor):
        """Test data validation and normalization."""
        # Test with invalid data
        invalid_tick = TickData(
            symbol="EUR/USD",
            timestamp=datetime.now(),
            bid=Decimal("1.0510"),
            ask=Decimal("1.0500"),  # Invalid: ask < bid
            bid_size=1000000,
            ask_size=1500000,
            last=Decimal("1.0505"),
            volume=100000,
        )

        result = await market_data_processor.validate_tick(invalid_tick)

        assert result["valid"] is False
        assert "errors" in result
        assert "inverted_spread" in result["errors"]

        # Test normalization
        normalized = await market_data_processor.normalize_tick(invalid_tick)
        assert normalized["bid"] < normalized["ask"]

    @pytest.mark.asyncio
    async def test_manages_order_book(self, market_data_processor, sample_order_book):
        """Test order book management and updates."""
        # Initialize order book
        result = await market_data_processor.update_order_book(sample_order_book)

        assert result["status"] == "updated"
        assert "depth" in result
        assert result["depth"]["bid_levels"] == 3
        assert result["depth"]["ask_levels"] == 3
        assert "spread" in result
        assert result["spread"] == Decimal("0.0002")

        # Get best bid/ask
        bbo = await market_data_processor.get_best_bid_offer("EUR/USD")

        assert bbo["bid"] == Decimal("1.0500")
        assert bbo["ask"] == Decimal("1.0502")
        assert bbo["spread_bps"] == 2.0

    @pytest.mark.asyncio
    async def test_aggregates_bars_multiple_timeframes(
        self, market_data_processor, sample_tick_data
    ):
        """Test bar aggregation for multiple timeframes."""
        # Process ticks
        for tick in sample_tick_data * 100:  # Generate more data
            await market_data_processor.process_tick(tick)

        # Get aggregated bars
        bars = await market_data_processor.get_bars(symbol="EUR/USD", timeframe="1m")

        assert "bars" in bars
        assert len(bars["bars"]) > 0

        bar = bars["bars"][0]
        assert "open" in bar
        assert "high" in bar
        assert "low" in bar
        assert "close" in bar
        assert "volume" in bar
        assert "timestamp" in bar

    @pytest.mark.asyncio
    async def test_creates_volume_bars(self, market_data_processor):
        """Test volume-based bar aggregation."""
        # Generate tick data with varying volumes
        for i in range(100):
            tick = TickData(
                symbol="EUR/USD",
                timestamp=datetime.now() + timedelta(seconds=i),
                bid=Decimal("1.0500") + Decimal(str(i * 0.0001)),
                ask=Decimal("1.0502") + Decimal(str(i * 0.0001)),
                bid_size=1000000,
                ask_size=1500000,
                last=Decimal("1.0501") + Decimal(str(i * 0.0001)),
                volume=10000 * (i % 10 + 1),
            )
            await market_data_processor.process_tick(tick)

        # Get volume bars
        volume_bars = await market_data_processor.get_volume_bars(
            symbol="EUR/USD", volume_threshold=500000
        )

        assert "bars" in volume_bars
        assert all(bar["volume"] >= 500000 for bar in volume_bars["bars"])

    @pytest.mark.asyncio
    async def test_creates_range_bars(self, market_data_processor):
        """Test range-based bar aggregation."""
        # Generate tick data with price movements
        for i in range(100):
            tick = TickData(
                symbol="EUR/USD",
                timestamp=datetime.now() + timedelta(seconds=i),
                bid=Decimal("1.0500") + Decimal(str((i % 20) * 0.0001)),
                ask=Decimal("1.0502") + Decimal(str((i % 20) * 0.0001)),
                bid_size=1000000,
                ask_size=1500000,
                last=Decimal("1.0501") + Decimal(str((i % 20) * 0.0001)),
                volume=100000,
            )
            await market_data_processor.process_tick(tick)

        # Get range bars
        range_bars = await market_data_processor.get_range_bars(
            symbol="EUR/USD", price_range=Decimal("0.0010")
        )

        assert "bars" in range_bars
        for bar in range_bars["bars"]:
            bar_range = bar["high"] - bar["low"]
            assert bar_range >= Decimal("0.0010")

    @pytest.mark.asyncio
    async def test_detects_outliers_and_anomalies(self, market_data_processor):
        """Test outlier detection in market data."""
        # Normal tick
        normal_tick = TickData(
            symbol="EUR/USD",
            timestamp=datetime.now(),
            bid=Decimal("1.0500"),
            ask=Decimal("1.0502"),
            bid_size=1000000,
            ask_size=1500000,
            last=Decimal("1.0501"),
            volume=100000,
        )

        # Outlier tick (large price jump)
        outlier_tick = TickData(
            symbol="EUR/USD",
            timestamp=datetime.now() + timedelta(milliseconds=100),
            bid=Decimal("1.1000"),  # 500 pip jump
            ask=Decimal("1.1002"),
            bid_size=1000000,
            ask_size=1500000,
            last=Decimal("1.1001"),
            volume=100000,
        )

        # Process normal tick
        await market_data_processor.process_tick(normal_tick)

        # Check outlier detection
        outlier_check = await market_data_processor.detect_outlier(outlier_tick)

        assert outlier_check["is_outlier"] is True
        assert "deviation_sigma" in outlier_check
        assert outlier_check["deviation_sigma"] > 3
        assert "action" in outlier_check
        assert outlier_check["action"] == "filter"

    @pytest.mark.asyncio
    async def test_handles_data_gaps(self, market_data_processor):
        """Test handling of gaps in market data."""
        # Create data with gap
        tick1 = TickData(
            symbol="EUR/USD",
            timestamp=datetime.now(),
            bid=Decimal("1.0500"),
            ask=Decimal("1.0502"),
            bid_size=1000000,
            ask_size=1500000,
            last=Decimal("1.0501"),
            volume=100000,
        )

        tick2 = TickData(
            symbol="EUR/USD",
            timestamp=datetime.now() + timedelta(minutes=5),  # 5 minute gap
            bid=Decimal("1.0510"),
            ask=Decimal("1.0512"),
            bid_size=1000000,
            ask_size=1500000,
            last=Decimal("1.0511"),
            volume=100000,
        )

        await market_data_processor.process_tick(tick1)

        gap_detection = await market_data_processor.detect_gap(tick2)

        assert gap_detection["gap_detected"] is True
        assert gap_detection["gap_duration_seconds"] == 300
        assert "interpolation_method" in gap_detection
        assert gap_detection["interpolation_method"] == "linear"

    @pytest.mark.asyncio
    async def test_monitors_data_quality(self, market_data_processor, sample_tick_data):
        """Test data quality monitoring and metrics."""
        # Process ticks
        for tick in sample_tick_data:
            await market_data_processor.process_tick(tick)

        # Get quality metrics
        quality = await market_data_processor.get_quality_metrics("EUR/USD")

        assert "tick_rate" in quality
        assert "average_spread" in quality
        assert "latency_p50" in quality
        assert "latency_p99" in quality
        assert "completeness" in quality
        assert "quality_score" in quality
        assert quality["quality_score"] > 0.8

    @pytest.mark.asyncio
    async def test_tracks_latency_metrics(self, market_data_processor):
        """Test latency tracking and alerting."""
        # Simulate high latency tick
        tick = TickData(
            symbol="EUR/USD",
            timestamp=datetime.now() - timedelta(milliseconds=150),  # 150ms old
            bid=Decimal("1.0500"),
            ask=Decimal("1.0502"),
            bid_size=1000000,
            ask_size=1500000,
            last=Decimal("1.0501"),
            volume=100000,
        )

        result = await market_data_processor.process_tick(tick)

        assert "latency_ms" in result
        assert result["latency_ms"] >= 150
        assert "latency_alert" in result
        assert result["latency_alert"] is True

    @pytest.mark.asyncio
    async def test_handles_symbol_mapping(self, market_data_processor):
        """Test symbol mapping across different data sources."""
        # Map symbols between sources
        mappings = await market_data_processor.get_symbol_mappings("EUR/USD")

        assert "interactive_brokers" in mappings
        assert mappings["interactive_brokers"] == "EUR.USD"
        assert "polygon" in mappings
        assert mappings["polygon"] == "C:EURUSD"
        assert "alpaca" in mappings

        # Reverse mapping
        original = await market_data_processor.map_to_standard_symbol(
            "EUR.USD", "interactive_brokers"
        )
        assert original == "EUR/USD"

    @pytest.mark.asyncio
    async def test_handles_corporate_actions(self, market_data_processor):
        """Test handling of corporate actions (splits, dividends)."""
        # Simulate stock split
        action = {
            "symbol": "AAPL",
            "type": "split",
            "ratio": 4,
            "ex_date": datetime.now().date(),
            "record_date": datetime.now().date() - timedelta(days=1),
        }

        result = await market_data_processor.process_corporate_action(action)

        assert result["status"] == "processed"
        assert result["adjustments_applied"] is True
        assert "affected_bars" in result
        assert result["split_factor"] == 4

    @pytest.mark.asyncio
    async def test_market_depth_analysis(
        self, market_data_processor, sample_order_book
    ):
        """Test market depth analysis and liquidity metrics."""
        await market_data_processor.update_order_book(sample_order_book)

        depth_analysis = await market_data_processor.analyze_market_depth("EUR/USD")

        assert "total_bid_volume" in depth_analysis
        assert "total_ask_volume" in depth_analysis
        assert "bid_ask_imbalance" in depth_analysis
        assert "weighted_mid_price" in depth_analysis
        assert "liquidity_score" in depth_analysis

    @pytest.mark.asyncio
    async def test_data_compression_and_storage(
        self, market_data_processor, sample_tick_data
    ):
        """Test data compression and storage optimization."""
        # Process and store ticks
        for tick in sample_tick_data * 1000:  # Large dataset
            await market_data_processor.process_tick(tick)

        # Compress data
        compression_result = await market_data_processor.compress_historical_data(
            symbol="EUR/USD",
            start_date=datetime.now() - timedelta(days=1),
            compression="zstd",
        )

        assert compression_result["status"] == "compressed"
        assert "compression_ratio" in compression_result
        assert compression_result["compression_ratio"] > 2.0
        assert "original_size_mb" in compression_result
        assert "compressed_size_mb" in compression_result

    @pytest.mark.asyncio
    async def test_handles_multiple_symbols_concurrently(self, market_data_processor):
        """Test concurrent processing of multiple symbols."""
        symbols = ["EUR/USD", "GBP/USD", "USD/JPY", "BTC/USD"]
        tasks = []

        for symbol in symbols:
            tick = TickData(
                symbol=symbol,
                timestamp=datetime.now(),
                bid=Decimal("1.0500"),
                ask=Decimal("1.0502"),
                bid_size=1000000,
                ask_size=1500000,
                last=Decimal("1.0501"),
                volume=100000,
            )
            tasks.append(market_data_processor.process_tick(tick))

        results = await asyncio.gather(*tasks)

        assert all(r["status"] == "processed" for r in results)
        assert len(results) == len(symbols)

    @pytest.mark.asyncio
    async def test_failover_between_data_sources(self, market_data_processor):
        """Test automatic failover between data sources."""
        # Simulate primary source failure
        await market_data_processor.simulate_source_failure("interactive_brokers")

        # Check failover
        status = await market_data_processor.get_connection_status()

        assert status["primary_source"] == "polygon"  # Failover to secondary
        assert status["failover_active"] is True
        assert "failover_reason" in status

        # Process tick should still work
        tick = TickData(
            symbol="EUR/USD",
            timestamp=datetime.now(),
            bid=Decimal("1.0500"),
            ask=Decimal("1.0502"),
            bid_size=1000000,
            ask_size=1500000,
            last=Decimal("1.0501"),
            volume=100000,
        )

        result = await market_data_processor.process_tick(tick)
        assert result["status"] == "processed"
        assert result["source"] == "polygon"

    @pytest.mark.asyncio
    async def test_snapshot_and_recovery(self, market_data_processor, sample_tick_data):
        """Test market data snapshot and recovery."""
        # Process some data
        for tick in sample_tick_data:
            await market_data_processor.process_tick(tick)

        # Create snapshot
        snapshot = await market_data_processor.create_snapshot()

        assert snapshot["status"] == "created"
        assert "snapshot_id" in snapshot
        assert "timestamp" in snapshot
        assert "symbols" in snapshot
        assert len(snapshot["symbols"]) > 0

        # Simulate crash and recovery
        await market_data_processor.clear_state()

        # Recover from snapshot
        recovery = await market_data_processor.recover_from_snapshot(
            snapshot["snapshot_id"]
        )

        assert recovery["status"] == "recovered"
        assert recovery["symbols_recovered"] == snapshot["symbols"]

    @pytest.mark.asyncio
    async def test_calculates_vwap(self, market_data_processor):
        """Test VWAP (Volume-Weighted Average Price) calculation."""
        # Generate trades with different prices and volumes
        trades = [
            {"price": Decimal("1.0500"), "volume": 100000},
            {"price": Decimal("1.0510"), "volume": 150000},
            {"price": Decimal("1.0505"), "volume": 200000},
            {"price": Decimal("1.0515"), "volume": 50000},
        ]

        for trade in trades:
            tick = TickData(
                symbol="EUR/USD",
                timestamp=datetime.now(),
                bid=trade["price"] - Decimal("0.0001"),
                ask=trade["price"] + Decimal("0.0001"),
                bid_size=1000000,
                ask_size=1500000,
                last=trade["price"],
                volume=trade["volume"],
            )
            await market_data_processor.process_tick(tick)

        vwap = await market_data_processor.calculate_vwap("EUR/USD")

        assert "vwap" in vwap
        assert vwap["vwap"] > Decimal("1.0500")
        assert vwap["vwap"] < Decimal("1.0515")
        assert "total_volume" in vwap
        assert vwap["total_volume"] == 500000

    @pytest.mark.asyncio
    async def test_market_session_handling(self, market_data_processor):
        """Test handling of different market sessions."""
        # Check current session
        session = await market_data_processor.get_current_session("EUR/USD")

        assert "session" in session
        assert session["session"] in ["Sydney", "Tokyo", "London", "New York", "Closed"]
        assert "is_open" in session
        assert "next_session" in session
        assert "session_high" in session
        assert "session_low" in session
