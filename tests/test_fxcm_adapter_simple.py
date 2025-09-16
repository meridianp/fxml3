"""Simplified test suite for FXCM Broker Adapter.

This test suite validates the core FXCM adapter functionality with focus on
the actual implemented classes, using proper mocking techniques.
"""

import asyncio
import json
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from fxml4.brokers.adapters.fxcm_container_adapter import (
    FXCMAPIError,
    FXCMBrokerAdapter,
    FXCMConnectionError,
    FXCMContainerManager,
    FXCMDataStreamer,
    FXCMOrderManager,
)
from fxml4.messaging import OrderMessage
from fxml4.messaging.messages import MessagePriority, OrderSide, OrderStatus, OrderType


class TestFXCMContainerManager:
    """Test FXCM container manager core functionality."""

    def test_container_manager_initialization(self):
        """Test container manager initialization."""
        manager = FXCMContainerManager(
            image_name="test-fxcm:latest",
            container_name="test_fxcm",
            api_port=9090,
            data_port=9091,
        )

        assert manager.image_name == "test-fxcm:latest"
        assert manager.container_name == "test_fxcm"
        assert manager.api_port == 9090
        assert manager.data_port == 9091
        assert manager.is_running is False
        assert manager.container is None

    def test_container_stats_calculation(self):
        """Test container statistics calculation."""
        manager = FXCMContainerManager()

        # Test with no container
        stats = manager.get_container_stats()
        assert stats == {}

        # Test CPU calculation
        mock_stats = {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 100000, "percpu_usage": [1, 2, 3, 4]},
                "system_cpu_usage": 1000000,
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 50000},
                "system_cpu_usage": 500000,
            },
            "memory": {"usage": 1024 * 1024 * 100, "limit": 1024 * 1024 * 1000},
            "networks": {"eth0": {"rx_bytes": 1000, "tx_bytes": 2000}},
        }

        cpu_percent = manager._calculate_cpu_percent(mock_stats)
        expected = ((100000 - 50000) / (1000000 - 500000)) * 4 * 100
        assert cpu_percent == expected


class TestFXCMOrderManager:
    """Test FXCM order manager core functionality."""

    def test_order_manager_initialization(self):
        """Test order manager initialization."""
        manager = FXCMOrderManager(
            api_url="http://test:8080",
            account_id="TEST123",
            session_id="session_test",
            timeout_seconds=15,
        )

        assert manager.api_url == "http://test:8080"
        assert manager.account_id == "TEST123"
        assert manager.session_id == "session_test"
        assert manager.timeout_seconds == 15
        assert len(manager.active_orders) == 0
        assert len(manager.order_history) == 0

    def test_performance_metrics(self):
        """Test order performance metrics tracking."""
        manager = FXCMOrderManager()

        # Initial state
        summary = manager.get_performance_summary()
        assert summary["total_orders"] == 0
        assert summary["success_rate"] == 0.0
        assert summary["average_latency_ms"] == 0.0

        # Simulate orders
        manager.order_count = 10
        manager.successful_orders = 8
        manager.failed_orders = 2
        manager.total_latency_ms = 500  # 50ms average

        summary = manager.get_performance_summary()
        assert summary["total_orders"] == 10
        assert summary["success_rate"] == 0.8
        assert summary["average_latency_ms"] == 50.0

    @pytest.mark.asyncio
    async def test_order_update_processing(self):
        """Test order status update processing."""
        manager = FXCMOrderManager()

        # Add active order
        manager.active_orders["TEST_001"] = {
            "order_id": "TEST_001",
            "status": "NEW",
            "symbol": "EUR/USD",
        }

        # Process filled update
        update_data = {
            "order_id": "TEST_001",
            "status": "FILLED",
            "filled_quantity": 100000,
            "avg_fill_price": 1.1050,
        }

        await manager.process_order_update(update_data)

        # Should be moved to history
        assert "TEST_001" not in manager.active_orders
        assert "TEST_001" in manager.order_history
        assert manager.order_history["TEST_001"]["status"] == "FILLED"


class TestFXCMDataStreamer:
    """Test FXCM data streamer core functionality."""

    def test_data_streamer_initialization(self):
        """Test data streamer initialization."""
        streamer = FXCMDataStreamer(
            data_url="ws://test:8081/data",
            symbols=["EUR/USD", "GBP/USD"],
            update_interval_ms=200,
        )

        assert streamer.data_url == "ws://test:8081/data"
        assert len(streamer.symbols) == 2
        assert "EUR/USD" in streamer.symbols
        assert streamer.update_interval_ms == 200
        assert streamer.is_connected is False

    @pytest.mark.asyncio
    async def test_market_data_processing(self):
        """Test market data processing and validation."""
        streamer = FXCMDataStreamer()

        # Valid market data
        valid_update = {
            "symbol": "EUR/USD",
            "bid": 1.1045,
            "ask": 1.1047,
            "spread": 0.0002,
            "volume": 1000000,
            "timestamp": datetime.utcnow().isoformat(),
        }

        await streamer.process_market_update(valid_update)

        # Check data storage
        assert "EUR/USD" in streamer.market_data
        data = streamer.market_data["EUR/USD"]
        assert data["bid"] == 1.1045
        assert data["ask"] == 1.1047
        assert data["spread"] == 0.0002
        assert "EUR/USD" in streamer.last_update_time

        # Invalid data (ask <= bid)
        invalid_update = {
            "symbol": "GBP/USD",
            "bid": 1.2500,
            "ask": 1.2499,  # Invalid: ask < bid
            "spread": -0.0001,
        }

        await streamer.process_market_update(invalid_update)

        # Should not be stored
        assert "GBP/USD" not in streamer.market_data

    def test_callback_management(self):
        """Test callback management functionality."""
        streamer = FXCMDataStreamer()

        callback1 = Mock()
        callback2 = Mock()

        # Add callbacks
        streamer.add_update_callback(callback1)
        streamer.add_update_callback(callback2)
        assert len(streamer.update_callbacks) == 2

        # Remove callback
        streamer.remove_update_callback(callback1)
        assert len(streamer.update_callbacks) == 1
        assert callback2 in streamer.update_callbacks

    def test_data_quality_report(self):
        """Test data quality reporting."""
        streamer = FXCMDataStreamer()
        streamer.updates_received = 100
        streamer.updates_processed = 95
        streamer.connection_start_time = datetime.utcnow()

        report = streamer.get_data_quality_report()

        assert report["total_updates_received"] == 100
        assert report["total_updates_processed"] == 95
        assert report["processing_success_rate"] == 0.95
        assert report["symbols_tracked"] == len(streamer.symbols)
        assert "connection_uptime_seconds" in report


class TestFXCMBrokerAdapter:
    """Test main FXCM broker adapter functionality."""

    def test_adapter_initialization(self):
        """Test adapter initialization with custom config."""
        config = {
            "image": "custom-fxcm:v1.0",
            "api_port": 9080,
            "data_port": 9081,
            "symbols": ["USD/JPY", "EUR/GBP"],
            "timeout_seconds": 20,
        }

        adapter = FXCMBrokerAdapter(
            username="test_user",
            password="test_pass",
            server="Demo",
            account_id="DEMO456",
            container_config=config,
        )

        assert adapter.username == "test_user"
        assert adapter.server == "Demo"
        assert adapter.account_id == "DEMO456"
        assert adapter.is_connected is False

        # Check container configuration
        assert adapter.container_manager.image_name == "custom-fxcm:v1.0"
        assert adapter.container_manager.api_port == 9080
        assert adapter.order_manager.timeout_seconds == 20
        assert "USD/JPY" in adapter.data_streamer.symbols

    @pytest.mark.asyncio
    async def test_order_execution_validation(self):
        """Test order execution validation and error handling."""
        adapter = FXCMBrokerAdapter()

        order_msg = OrderMessage(
            order_id="VAL_001",
            client_order_id="CLI_VAL_001",
            symbol="EUR/USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("100000"),
            broker="FXCM",
            account_id="TEST",
        )

        # Test not connected
        with pytest.raises(FXCMConnectionError, match="Not connected"):
            await adapter.execute_order(order_msg)

        # Test connected but no session
        adapter.is_connected = True
        adapter.session_id = None

        with pytest.raises(FXCMConnectionError, match="No active FXCM session"):
            await adapter.execute_order(order_msg)

    @pytest.mark.asyncio
    async def test_market_data_integration(self):
        """Test market data integration functionality."""
        adapter = FXCMBrokerAdapter()

        # Mock market data in streamer
        adapter.data_streamer.market_data["EUR/USD"] = {
            "bid": 1.1000,
            "ask": 1.1002,
            "spread": 0.0002,
        }

        # Test price retrieval
        price = adapter.get_current_price("EUR/USD")
        assert price is not None
        assert price["bid"] == 1.1000
        assert price["ask"] == 1.1002

        # Test non-existent symbol
        price = adapter.get_current_price("INVALID/SYMBOL")
        assert price is None

        # Test callback management
        callback = Mock()
        adapter.add_market_data_callback(callback)
        assert callback in adapter.data_streamer.update_callbacks

        adapter.remove_market_data_callback(callback)
        assert callback not in adapter.data_streamer.update_callbacks

    @pytest.mark.asyncio
    async def test_health_check_comprehensive(self):
        """Test comprehensive health check functionality."""
        adapter = FXCMBrokerAdapter()

        # Mock component states
        adapter.is_connected = True
        adapter.session_id = "test_session"
        adapter.login_time = datetime.utcnow()
        adapter.connection_count = 5

        # Mock container manager
        adapter.container_manager.is_running = True
        adapter.container_manager.health_check_failures = 1

        # Mock order manager performance
        adapter.order_manager.order_count = 50
        adapter.order_manager.successful_orders = 45
        adapter.order_manager.total_latency_ms = 2500  # 50ms average

        # Mock data streamer
        adapter.data_streamer.is_connected = True
        adapter.data_streamer.updates_received = 1000
        adapter.data_streamer.updates_processed = 995

        with patch.object(
            adapter.container_manager, "check_health", new_callable=AsyncMock
        ) as mock_health:
            mock_health.return_value = True

            with patch.object(
                adapter.container_manager, "get_container_stats"
            ) as mock_stats:
                mock_stats.return_value = {"cpu_percent": 25.0, "memory_usage_mb": 256}

                health_report = await adapter.health_check()

        # Verify health report structure
        assert "adapter" in health_report
        assert "container" in health_report
        assert "order_management" in health_report
        assert "data_streaming" in health_report

        # Check adapter status
        adapter_status = health_report["adapter"]
        assert adapter_status["is_connected"] is True
        assert adapter_status["session_id"] == "test_session"
        assert adapter_status["connection_count"] == 5

        # Check order performance
        order_perf = health_report["order_management"]
        assert order_perf["success_rate"] == 0.9  # 45/50
        assert order_perf["average_latency_ms"] == 50.0

    @pytest.mark.asyncio
    async def test_connection_context_manager(self):
        """Test connection context manager functionality."""
        adapter = FXCMBrokerAdapter()

        # Mock the connect and disconnect methods
        with patch.object(adapter, "connect", new_callable=AsyncMock) as mock_connect:
            with patch.object(
                adapter, "disconnect", new_callable=AsyncMock
            ) as mock_disconnect:

                async with adapter.connection_context() as ctx_adapter:
                    assert ctx_adapter is adapter
                    mock_connect.assert_called_once()

                mock_disconnect.assert_called_once()

    def test_adapter_representation(self):
        """Test adapter string representation."""
        adapter = FXCMBrokerAdapter()
        adapter.is_connected = True
        adapter.session_id = "test_session_123"
        adapter.account_id = "DEMO789"

        repr_str = repr(adapter)
        expected = "FXCMBrokerAdapter(connected=True, session=test_session_123, account=DEMO789)"
        assert repr_str == expected

    @pytest.mark.asyncio
    async def test_connection_error_handling(self):
        """Test connection error handling."""
        adapter = FXCMBrokerAdapter()

        # Mock container manager to fail
        with patch.object(
            adapter.container_manager, "start_container", new_callable=AsyncMock
        ) as mock_start:
            mock_start.side_effect = FXCMConnectionError("Container failed to start")

            # Should raise connection error
            with pytest.raises(FXCMConnectionError, match="Container failed to start"):
                await adapter.connect()

            assert adapter.is_connected is False
            assert adapter.session_id is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
