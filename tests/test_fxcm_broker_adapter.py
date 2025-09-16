"""Test suite for FXCM Broker Adapter with Containerized forex-connect Integration.

This comprehensive TDD test suite validates the FXCM broker adapter that integrates
with the forex-connect API through containerized deployment. The adapter provides
real-time market data, order execution, and position management for FXML4 trading.

Test Categories:
- Container orchestration and lifecycle management
- FXCM forex-connect API integration and authentication
- Real-time market data streaming and processing
- Order placement, modification, and cancellation
- Position tracking and P&L calculation
- Error handling and connection resilience
- Performance benchmarks for <100ms order acknowledgment
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

import docker
from fxml4.brokers.adapters.fxcm_container_adapter import (
    FXCMAPIError,
    FXCMBrokerAdapter,
    FXCMConnectionError,
    FXCMContainerManager,
    FXCMDataStreamer,
    FXCMOrderManager,
)
from fxml4.messaging import (
    ExecutionMessage,
    MessagePriority,
    OrderMessage,
    RiskCheckMessage,
)
from fxml4.messaging.messages import OrderSide, OrderStatus, OrderType


class TestFXCMContainerManager:
    """Test FXCM container orchestration and lifecycle management."""

    def test_container_manager_initialization(self):
        """Test container manager initialization with Docker configuration."""
        manager = FXCMContainerManager(
            image_name="fxml4/fxcm-forex-connect:latest",
            container_name="fxcm_bridge",
            api_port=8080,
            data_port=8081,
        )

        assert manager.image_name == "fxml4/fxcm-forex-connect:latest"
        assert manager.container_name == "fxcm_bridge"
        assert manager.api_port == 8080
        assert manager.data_port == 8081
        assert manager.container is None
        assert manager.is_running is False

    @pytest.mark.asyncio
    async def test_container_startup_and_health_check(self):
        """Test container startup with health checks."""
        manager = FXCMContainerManager()

        # Mock Docker client
        mock_client = Mock()
        mock_container = Mock()
        mock_container.id = "test_container_id"
        mock_container.status = "running"
        mock_container.reload.return_value = None
        mock_client.containers.run.return_value = mock_container

        with patch("docker.from_env", return_value=mock_client):
            await manager.start_container()

            assert manager.container == mock_container
            assert manager.is_running is True

            # Verify Docker run parameters
            mock_client.containers.run.assert_called_once()
            call_args = mock_client.containers.run.call_args
            assert call_args[1]["image"] == manager.image_name
            assert call_args[1]["detach"] is True
            assert call_args[1]["ports"] == {
                "8080/tcp": manager.api_port,
                "8081/tcp": manager.data_port,
            }

    @pytest.mark.asyncio
    async def test_container_health_monitoring(self):
        """Test container health monitoring and recovery."""
        manager = FXCMContainerManager()

        # Mock healthy container
        mock_container = Mock()
        mock_container.status = "running"
        mock_container.reload.return_value = None
        manager.container = mock_container
        manager.is_running = True

        # Test health check
        is_healthy = await manager.check_health()
        assert is_healthy is True

        # Test unhealthy container
        mock_container.status = "exited"
        is_healthy = await manager.check_health()
        assert is_healthy is False
        assert manager.is_running is False

    @pytest.mark.asyncio
    async def test_container_cleanup(self):
        """Test container cleanup and resource disposal."""
        manager = FXCMContainerManager()

        mock_container = Mock()
        mock_container.stop.return_value = None
        mock_container.remove.return_value = None
        manager.container = mock_container
        manager.is_running = True

        await manager.stop_container()

        mock_container.stop.assert_called_once()
        mock_container.remove.assert_called_once()
        assert manager.container is None
        assert manager.is_running is False


class TestFXCMOrderManager:
    """Test FXCM order management and execution."""

    def test_order_manager_initialization(self):
        """Test order manager initialization."""
        order_manager = FXCMOrderManager(
            api_url="http://localhost:8080",
            account_id="FXCM_DEMO_123",
            session_id="session_abc_123",
        )

        assert order_manager.api_url == "http://localhost:8080"
        assert order_manager.account_id == "FXCM_DEMO_123"
        assert order_manager.session_id == "session_abc_123"
        assert len(order_manager.active_orders) == 0
        assert len(order_manager.order_history) == 0

    @pytest.mark.asyncio
    async def test_market_order_placement(self):
        """Test market order placement with FXCM API."""
        order_manager = FXCMOrderManager()

        # Create test order message
        order_msg = OrderMessage(
            order_id="FXCM_ORD_001",
            client_order_id="CLI_FXCM_001",
            symbol="EUR/USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("100000"),
            broker="FXCM",
            account_id="FXCM_DEMO_123",
            priority=MessagePriority.HIGH,
        )

        # Mock FXCM API response
        mock_response = {
            "order_id": "FXCM_ORD_001",
            "status": "NEW",
            "message": "Order placed successfully",
            "timestamp": datetime.utcnow().isoformat(),
        }

        with patch("aiohttp.ClientSession.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value.__aenter__.return_value.json = AsyncMock(
                return_value=mock_response
            )
            mock_post.return_value.__aenter__.return_value.status = 200

            result = await order_manager.place_order(order_msg)

            assert result["order_id"] == "FXCM_ORD_001"
            assert result["status"] == "NEW"
            assert "FXCM_ORD_001" in order_manager.active_orders

    @pytest.mark.asyncio
    async def test_limit_order_with_price(self):
        """Test limit order placement with specified price."""
        order_manager = FXCMOrderManager()

        order_msg = OrderMessage(
            order_id="FXCM_LIM_001",
            client_order_id="CLI_LIM_001",
            symbol="GBP/USD",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal("50000"),
            price=Decimal("1.2500"),
            broker="FXCM",
            account_id="FXCM_DEMO_123",
        )

        mock_response = {
            "order_id": "FXCM_LIM_001",
            "status": "NEW",
            "limit_price": 1.2500,
            "message": "Limit order placed successfully",
        }

        with patch("aiohttp.ClientSession.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value.__aenter__.return_value.json = AsyncMock(
                return_value=mock_response
            )
            mock_post.return_value.__aenter__.return_value.status = 200

            result = await order_manager.place_order(order_msg)

            assert result["limit_price"] == 1.2500
            assert result["status"] == "NEW"

    @pytest.mark.asyncio
    async def test_order_cancellation(self):
        """Test order cancellation functionality."""
        order_manager = FXCMOrderManager()

        # Add order to active orders
        order_manager.active_orders["FXCM_CAN_001"] = {
            "order_id": "FXCM_CAN_001",
            "status": "NEW",
            "symbol": "USD/JPY",
        }

        mock_response = {
            "order_id": "FXCM_CAN_001",
            "status": "CANCELLED",
            "message": "Order cancelled successfully",
        }

        with patch(
            "aiohttp.ClientSession.delete", new_callable=AsyncMock
        ) as mock_delete:
            mock_delete.return_value.__aenter__.return_value.json = AsyncMock(
                return_value=mock_response
            )
            mock_delete.return_value.__aenter__.return_value.status = 200

            result = await order_manager.cancel_order("FXCM_CAN_001")

            assert result["status"] == "CANCELLED"
            assert "FXCM_CAN_001" not in order_manager.active_orders

    @pytest.mark.asyncio
    async def test_order_status_updates(self):
        """Test order status update processing."""
        order_manager = FXCMOrderManager()

        # Mock order update from FXCM
        update_data = {
            "order_id": "FXCM_UPD_001",
            "status": "FILLED",
            "filled_quantity": 75000,
            "avg_fill_price": 1.1050,
            "commission": 2.50,
        }

        await order_manager.process_order_update(update_data)

        # Verify order is moved to history
        assert "FXCM_UPD_001" in order_manager.order_history
        filled_order = order_manager.order_history["FXCM_UPD_001"]
        assert filled_order["status"] == "FILLED"
        assert filled_order["filled_quantity"] == 75000


class TestFXCMDataStreamer:
    """Test FXCM real-time data streaming functionality."""

    def test_data_streamer_initialization(self):
        """Test data streamer initialization."""
        streamer = FXCMDataStreamer(
            data_url="ws://localhost:8081/market_data",
            symbols=["EUR/USD", "GBP/USD", "USD/JPY"],
            update_interval_ms=100,
        )

        assert streamer.data_url == "ws://localhost:8081/market_data"
        assert len(streamer.symbols) == 3
        assert streamer.update_interval_ms == 100
        assert streamer.is_connected is False
        assert len(streamer.market_data) == 0

    @pytest.mark.asyncio
    async def test_websocket_connection_and_subscription(self):
        """Test WebSocket connection and symbol subscription."""
        streamer = FXCMDataStreamer()

        mock_websocket = AsyncMock()
        mock_websocket.send = AsyncMock()
        mock_websocket.recv = AsyncMock()

        with patch("websockets.connect", return_value=mock_websocket):
            await streamer.connect()

            assert streamer.is_connected is True

            # Verify subscription messages sent
            mock_websocket.send.assert_called()
            calls = mock_websocket.send.call_args_list
            assert len(calls) >= len(streamer.symbols)

    @pytest.mark.asyncio
    async def test_market_data_processing(self):
        """Test real-time market data processing."""
        streamer = FXCMDataStreamer(symbols=["EUR/USD"])

        # Mock market data update
        market_update = {
            "symbol": "EUR/USD",
            "bid": 1.1045,
            "ask": 1.1047,
            "timestamp": datetime.utcnow().isoformat(),
            "spread": 0.0002,
        }

        await streamer.process_market_update(market_update)

        # Verify data storage
        assert "EUR/USD" in streamer.market_data
        eurusd_data = streamer.market_data["EUR/USD"]
        assert eurusd_data["bid"] == 1.1045
        assert eurusd_data["ask"] == 1.1047
        assert eurusd_data["spread"] == 0.0002

    @pytest.mark.asyncio
    async def test_data_streaming_performance(self):
        """Test data streaming performance and latency."""
        streamer = FXCMDataStreamer(update_interval_ms=50)

        start_time = time.time()
        updates_processed = 0

        # Simulate rapid market data updates
        for i in range(100):
            update = {
                "symbol": "EUR/USD",
                "bid": 1.1000 + (i * 0.0001),
                "ask": 1.1002 + (i * 0.0001),
                "timestamp": datetime.utcnow().isoformat(),
            }
            await streamer.process_market_update(update)
            updates_processed += 1

        end_time = time.time()
        processing_time = end_time - start_time

        # Performance assertions
        assert updates_processed == 100
        assert processing_time < 1.0  # Should process 100 updates in < 1 second

        # Verify latest data
        latest_data = streamer.market_data["EUR/USD"]
        assert latest_data["bid"] == 1.1099  # Last update


class TestFXCMBrokerAdapter:
    """Test main FXCM broker adapter integration."""

    def test_adapter_initialization(self):
        """Test FXCM adapter initialization with configuration."""
        adapter = FXCMBrokerAdapter(
            username="demo_user",
            password="demo_pass",
            server="Demo",
            account_id="DEMO123",
            container_config={
                "image": "fxml4/fxcm-connect:latest",
                "api_port": 8080,
                "data_port": 8081,
            },
        )

        assert adapter.username == "demo_user"
        assert adapter.server == "Demo"
        assert adapter.account_id == "DEMO123"
        assert adapter.is_connected is False
        assert adapter.container_manager is not None
        assert adapter.order_manager is not None
        assert adapter.data_streamer is not None

    @pytest.mark.asyncio
    async def test_adapter_connection_workflow(self):
        """Test complete adapter connection workflow."""
        adapter = FXCMBrokerAdapter()

        # Mock dependencies
        adapter.container_manager = AsyncMock()
        adapter.container_manager.start_container = AsyncMock()
        adapter.container_manager.check_health = AsyncMock(return_value=True)

        mock_login_response = {
            "session_id": "session_123",
            "status": "connected",
            "account_id": "DEMO123",
        }

        with patch("aiohttp.ClientSession.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value.__aenter__.return_value.json = AsyncMock(
                return_value=mock_login_response
            )
            mock_post.return_value.__aenter__.return_value.status = 200

            await adapter.connect()

            assert adapter.is_connected is True
            assert adapter.session_id == "session_123"
            adapter.container_manager.start_container.assert_called_once()

    @pytest.mark.asyncio
    async def test_order_execution_integration(self):
        """Test end-to-end order execution through adapter."""
        adapter = FXCMBrokerAdapter()
        adapter.is_connected = True
        adapter.session_id = "test_session"

        # Mock order manager
        adapter.order_manager = AsyncMock()
        mock_order_result = {
            "order_id": "FXCM_INT_001",
            "status": "FILLED",
            "fill_price": 1.1050,
            "commission": 2.75,
        }
        adapter.order_manager.place_order = AsyncMock(return_value=mock_order_result)

        # Create order message
        order_msg = OrderMessage(
            order_id="FXCM_INT_001",
            client_order_id="CLI_INT_001",
            symbol="EUR/USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("100000"),
            broker="FXCM",
            account_id="DEMO123",
        )

        result = await adapter.execute_order(order_msg)

        assert result["status"] == "FILLED"
        assert result["fill_price"] == 1.1050
        adapter.order_manager.place_order.assert_called_once_with(order_msg)

    @pytest.mark.asyncio
    async def test_position_tracking(self):
        """Test position tracking and P&L calculation."""
        adapter = FXCMBrokerAdapter()
        adapter.is_connected = True

        # Mock position data from FXCM
        position_data = {
            "symbol": "EUR/USD",
            "side": "LONG",
            "quantity": 100000,
            "open_price": 1.1000,
            "current_price": 1.1050,
            "unrealized_pnl": 500.00,
            "margin_used": 1100.00,
        }

        with patch("aiohttp.ClientSession.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(
                return_value=[position_data]
            )
            mock_get.return_value.__aenter__.return_value.status = 200

            positions = await adapter.get_positions()

            assert len(positions) == 1
            position = positions[0]
            assert position["symbol"] == "EUR/USD"
            assert position["unrealized_pnl"] == 500.00

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self):
        """Test error handling and recovery mechanisms."""
        adapter = FXCMBrokerAdapter()

        # Test connection failure
        with patch(
            "aiohttp.ClientSession.post", side_effect=Exception("Connection failed")
        ):
            with pytest.raises(FXCMConnectionError):
                await adapter.connect()

        # Test API error handling
        adapter.is_connected = True
        mock_error_response = {"error": "INVALID_SYMBOL", "message": "Symbol not found"}

        with patch("aiohttp.ClientSession.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value.__aenter__.return_value.json = AsyncMock(
                return_value=mock_error_response
            )
            mock_post.return_value.__aenter__.return_value.status = 400

            order_msg = OrderMessage(
                order_id="ERROR_001",
                client_order_id="CLI_ERROR_001",
                symbol="INVALID_SYMBOL",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=Decimal("100000"),
                broker="FXCM",
                account_id="DEMO123",
            )

            with pytest.raises(FXCMAPIError):
                await adapter.execute_order(order_msg)

    @pytest.mark.asyncio
    async def test_performance_benchmarks(self):
        """Test performance benchmarks for order execution latency."""
        adapter = FXCMBrokerAdapter()
        adapter.is_connected = True

        # Mock fast order response
        adapter.order_manager = AsyncMock()
        mock_fast_response = {
            "order_id": "PERF_001",
            "status": "NEW",
            "ack_time_ms": 45,  # Sub-100ms target
        }
        adapter.order_manager.place_order = AsyncMock(return_value=mock_fast_response)

        order_msg = OrderMessage(
            order_id="PERF_001",
            client_order_id="CLI_PERF_001",
            symbol="EUR/USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("100000"),
            broker="FXCM",
            account_id="DEMO123",
        )

        # Measure execution time
        start_time = time.time()
        result = await adapter.execute_order(order_msg)
        end_time = time.time()

        execution_time_ms = (end_time - start_time) * 1000

        # Performance assertions
        assert execution_time_ms < 100  # <100ms latency target
        assert result["ack_time_ms"] == 45

    @pytest.mark.asyncio
    async def test_adapter_cleanup(self):
        """Test adapter cleanup and resource disposal."""
        adapter = FXCMBrokerAdapter()
        adapter.is_connected = True

        # Mock cleanup operations
        adapter.container_manager = AsyncMock()
        adapter.container_manager.stop_container = AsyncMock()
        adapter.data_streamer = AsyncMock()
        adapter.data_streamer.disconnect = AsyncMock()

        await adapter.disconnect()

        assert adapter.is_connected is False
        adapter.container_manager.stop_container.assert_called_once()
        adapter.data_streamer.disconnect.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
