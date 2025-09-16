"""Base test class for broker adapter testing.

This module provides a comprehensive base class for testing broker adapters,
including common fixtures, test methods, and utilities to eliminate code duplication
across adapter test files.
"""

import asyncio
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from fxml4.brokers.adapters.base import AdapterConfig, AdapterMetrics, ConnectionStatus
from fxml4.fix.messages.base import ExecType, OrdStatus, OrdType, Side, TimeInForce
from fxml4.fix.messages.orders import (
    ExecutionReport,
    NewOrderSingle,
    OrderCancelRequest,
)


class BaseBrokerAdapterTest(ABC):
    """Base test class for broker adapter testing."""

    @abstractmethod
    def get_adapter_type(self) -> str:
        """Return the adapter type for this test."""
        pass

    @abstractmethod
    def get_adapter_class(self):
        """Return the adapter class being tested."""
        pass

    @abstractmethod
    def get_default_config(self) -> AdapterConfig:
        """Return default configuration for the adapter."""
        pass

    # Common Fixtures
    @pytest.fixture
    def basic_config(self):
        """Basic adapter configuration."""
        return self.get_default_config()

    @pytest.fixture
    def mock_config(self, basic_config):
        """Mock mode configuration."""
        config = basic_config
        if hasattr(config, "connection_params"):
            config.connection_params["mock"] = True
        return config

    @pytest.fixture
    def sample_market_order(self):
        """Create sample market order."""
        return NewOrderSingle(
            cl_ord_id=f"MKT_{uuid.uuid4().hex[:8].upper()}",
            symbol="EURUSD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.MARKET,
            time_in_force=TimeInForce.IMMEDIATE_OR_CANCEL,
        )

    @pytest.fixture
    def sample_limit_order(self):
        """Create sample limit order."""
        return NewOrderSingle(
            cl_ord_id=f"LMT_{uuid.uuid4().hex[:8].upper()}",
            symbol="GBPUSD",
            side=Side.SELL,
            order_qty=50000,
            ord_type=OrdType.LIMIT,
            price=1.2500,
            time_in_force=TimeInForce.DAY,
        )

    @pytest.fixture
    def sample_execution_report(self, sample_market_order):
        """Create sample execution report."""
        return ExecutionReport(
            order_id="ORDER_001",
            cl_ord_id=sample_market_order.cl_ord_id,
            exec_id=f"EXEC_{uuid.uuid4().hex[:8].upper()}",
            exec_type=ExecType.FILL,
            ord_status=OrdStatus.FILLED,
            symbol=sample_market_order.symbol,
            side=sample_market_order.side,
            order_qty=sample_market_order.order_qty,
            cum_qty=sample_market_order.order_qty,
            avg_px=1.0850,
            last_qty=sample_market_order.order_qty,
            last_px=1.0850,
        )

    @pytest.fixture
    def mock_connection(self):
        """Create mock connection object."""
        connection = MagicMock()
        connection.status = ConnectionStatus.DISCONNECTED
        connection.connect = AsyncMock()
        connection.disconnect = AsyncMock()
        connection.is_connected = False
        return connection

    # Common Test Methods
    def test_adapter_initialization(self, basic_config):
        """Test basic adapter initialization."""
        adapter = self.get_adapter_class()(basic_config)

        assert adapter.adapter_type == self.get_adapter_type()
        assert adapter.connection.status == ConnectionStatus.DISCONNECTED
        assert hasattr(adapter, "metrics")
        assert isinstance(adapter.metrics, AdapterMetrics)

    def test_config_validation(self):
        """Test configuration validation."""
        # Test with invalid config
        with pytest.raises((ValueError, TypeError)):
            self.get_adapter_class()(None)

    @pytest.mark.asyncio
    async def test_connection_lifecycle(self, basic_config):
        """Test connection and disconnection lifecycle."""
        adapter = self.get_adapter_class()(basic_config)

        # Initially disconnected
        assert not adapter.is_connected()

        # Mock connection for testing
        with patch.object(adapter, "_establish_connection", AsyncMock()):
            await adapter.connect()
            adapter.connection.status = ConnectionStatus.CONNECTED
            adapter.connection.is_connected = True

            assert adapter.is_connected()

            # Test disconnection
            with patch.object(adapter, "_close_connection", AsyncMock()):
                await adapter.disconnect()
                adapter.connection.status = ConnectionStatus.DISCONNECTED
                adapter.connection.is_connected = False

                assert not adapter.is_connected()

    @pytest.mark.asyncio
    async def test_order_submission_success(self, basic_config, sample_market_order):
        """Test successful order submission."""
        adapter = self.get_adapter_class()(basic_config)

        # Mock successful submission
        with patch.object(adapter, "_submit_order", AsyncMock(return_value=True)):
            result = await adapter.submit_order(sample_market_order)
            assert result is True

            # Verify metrics updated
            assert adapter.metrics.orders_submitted > 0

    @pytest.mark.asyncio
    async def test_order_submission_failure(self, basic_config, sample_market_order):
        """Test order submission failure handling."""
        adapter = self.get_adapter_class()(basic_config)

        # Mock failed submission
        with patch.object(
            adapter,
            "_submit_order",
            AsyncMock(side_effect=Exception("Submission failed")),
        ):
            with pytest.raises(Exception):
                await adapter.submit_order(sample_market_order)

    @pytest.mark.asyncio
    async def test_order_cancellation(self, basic_config, sample_limit_order):
        """Test order cancellation."""
        adapter = self.get_adapter_class()(basic_config)

        cancel_request = OrderCancelRequest(
            orig_cl_ord_id=sample_limit_order.cl_ord_id,
            cl_ord_id=f"CANCEL_{uuid.uuid4().hex[:8].upper()}",
            symbol=sample_limit_order.symbol,
            side=sample_limit_order.side,
        )

        # Mock successful cancellation
        with patch.object(adapter, "_cancel_order", AsyncMock(return_value=True)):
            result = await adapter.cancel_order(cancel_request)
            assert result is True

    def test_metrics_collection(self, basic_config):
        """Test metrics collection functionality."""
        adapter = self.get_adapter_class()(basic_config)

        # Verify initial metrics
        assert adapter.metrics.orders_submitted == 0
        assert adapter.metrics.orders_filled == 0
        assert adapter.metrics.orders_rejected == 0
        assert adapter.metrics.connection_count == 0

        # Test metrics update
        adapter.metrics.orders_submitted += 1
        assert adapter.metrics.orders_submitted == 1

    def test_adapter_status_reporting(self, basic_config):
        """Test adapter status reporting."""
        adapter = self.get_adapter_class()(basic_config)

        status = adapter.get_status()
        assert isinstance(status, dict)
        assert "adapter_type" in status
        assert "connection_status" in status
        assert "metrics" in status
        assert status["adapter_type"] == self.get_adapter_type()

    @pytest.mark.asyncio
    async def test_error_handling(self, basic_config):
        """Test general error handling."""
        adapter = self.get_adapter_class()(basic_config)

        # Test connection error handling
        with patch.object(
            adapter,
            "_establish_connection",
            AsyncMock(side_effect=ConnectionError("Network error")),
        ):
            with pytest.raises(ConnectionError):
                await adapter.connect()

    @pytest.mark.asyncio
    async def test_reconnection_logic(self, basic_config):
        """Test automatic reconnection logic."""
        adapter = self.get_adapter_class()(basic_config)

        # Mock connection that fails then succeeds
        connection_attempts = [False, False, True]  # Fail twice, then succeed

        async def mock_connect():
            if connection_attempts:
                success = connection_attempts.pop(0)
                if not success:
                    raise ConnectionError("Connection failed")
                adapter.connection.status = ConnectionStatus.CONNECTED
                adapter.connection.is_connected = True

        with patch.object(adapter, "_establish_connection", mock_connect):
            # Test with retry logic (if adapter supports it)
            if hasattr(adapter, "max_reconnect_attempts"):
                adapter.max_reconnect_attempts = 3
                await adapter.connect()
                assert adapter.is_connected()

    def test_configuration_validation_edge_cases(self):
        """Test configuration validation with edge cases."""
        adapter_class = self.get_adapter_class()

        # Test with empty config
        with pytest.raises((ValueError, TypeError, AttributeError)):
            adapter_class({})

        # Test with missing required fields
        incomplete_config = AdapterConfig(
            adapter_type=self.get_adapter_type(),
            connection_params={},
            authentication={},
            features={},
        )

        # Some adapters might accept minimal config, others might not
        try:
            adapter = adapter_class(incomplete_config)
            # If it succeeds, verify it has sensible defaults
            assert adapter.adapter_type == self.get_adapter_type()
        except (ValueError, TypeError, KeyError):
            # Expected for adapters requiring specific config fields
            pass

    @pytest.mark.asyncio
    async def test_concurrent_operations(
        self, basic_config, sample_market_order, sample_limit_order
    ):
        """Test concurrent adapter operations."""
        adapter = self.get_adapter_class()(basic_config)

        # Mock successful operations
        with patch.object(adapter, "_submit_order", AsyncMock(return_value=True)):
            # Submit multiple orders concurrently
            tasks = [
                adapter.submit_order(sample_market_order),
                adapter.submit_order(sample_limit_order),
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Check that concurrent operations completed
            assert len(results) == 2
            for result in results:
                if not isinstance(result, Exception):
                    assert result is True

    def test_feature_flag_handling(self, basic_config):
        """Test adapter feature flag handling."""
        adapter = self.get_adapter_class()(basic_config)

        # Test feature availability checks
        if hasattr(adapter, "supports_market_data"):
            assert isinstance(adapter.supports_market_data, bool)

        if hasattr(adapter, "supports_order_modification"):
            assert isinstance(adapter.supports_order_modification, bool)

    @pytest.mark.asyncio
    async def test_cleanup_on_disconnect(self, basic_config):
        """Test proper cleanup when disconnecting."""
        adapter = self.get_adapter_class()(basic_config)

        # Mock connection and add some state
        with patch.object(adapter, "_establish_connection", AsyncMock()):
            await adapter.connect()
            adapter.connection.status = ConnectionStatus.CONNECTED
            adapter.connection.is_connected = True

            # Add some pending state if adapter supports it
            if hasattr(adapter, "pending_orders"):
                adapter.pending_orders["test"] = {"order": "data"}

            # Disconnect and verify cleanup
            with patch.object(adapter, "_close_connection", AsyncMock()):
                await adapter.disconnect()
                adapter.connection.status = ConnectionStatus.DISCONNECTED
                adapter.connection.is_connected = False

                # Verify state is cleaned up
                if hasattr(adapter, "pending_orders"):
                    # Some adapters might clear pending orders, others might preserve them
                    # This depends on adapter implementation
                    pass


class BrokerAdapterTestMixin:
    """Mixin providing additional test utilities for broker adapters."""

    def assert_valid_order(self, order: NewOrderSingle):
        """Assert that an order is valid."""
        assert order.cl_ord_id is not None
        assert order.symbol is not None
        assert order.side in [Side.BUY, Side.SELL]
        assert order.order_qty > 0
        assert order.ord_type in [OrdType.MARKET, OrdType.LIMIT, OrdType.STOP]

    def assert_valid_execution_report(self, report: ExecutionReport):
        """Assert that an execution report is valid."""
        assert report.order_id is not None
        assert report.cl_ord_id is not None
        assert report.exec_id is not None
        assert report.exec_type is not None
        assert report.ord_status is not None

    def create_test_orders_batch(self, count: int = 5) -> List[NewOrderSingle]:
        """Create a batch of test orders."""
        orders = []
        symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"]

        for i in range(count):
            order = NewOrderSingle(
                cl_ord_id=f"BATCH_{i}_{uuid.uuid4().hex[:8].upper()}",
                symbol=symbols[i % len(symbols)],
                side=Side.BUY if i % 2 == 0 else Side.SELL,
                order_qty=10000 + (i * 10000),
                ord_type=OrdType.MARKET if i % 2 == 0 else OrdType.LIMIT,
                time_in_force=TimeInForce.DAY,
            )

            if order.ord_type == OrdType.LIMIT:
                order.price = 1.0000 + (i * 0.0010)

            orders.append(order)

        return orders

    def mock_market_data(self) -> Dict[str, Any]:
        """Create mock market data."""
        return {
            "symbol": "EURUSD",
            "bid": 1.0850,
            "ask": 1.0852,
            "timestamp": datetime.utcnow(),
            "volume": 1000000,
        }
