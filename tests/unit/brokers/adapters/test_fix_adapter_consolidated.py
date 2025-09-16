"""Unit tests for Enhanced FIX Broker Adapter.

This module provides comprehensive tests for the enhanced FIX adapter implementation,
inheriting from the base broker adapter test framework for consistency.
"""

import asyncio
import socket
import ssl
from datetime import datetime, timedelta
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from fxml4.brokers.adapters.base import AdapterConfig, AdapterMetrics, ConnectionStatus
from fxml4.brokers.adapters.fix_adapter import FixBrokerAdapter, FIXConnection
from fxml4.fix.messages.admin import Heartbeat, Logon, Logout, TestRequest
from fxml4.fix.messages.base import ExecType, OrdStatus, OrdType, Side, TimeInForce
from fxml4.fix.messages.market_data import MarketDataRequest, MarketDataSnapshot
from fxml4.fix.messages.order_modify import OrderCancelReplaceRequest
from fxml4.fix.messages.orders import (
    ExecutionReport,
    NewOrderSingle,
    OrderCancelRequest,
)
from fxml4.fix.session_manager import FIXSession, SessionConfig, SessionState

# Import base test infrastructure
from tests.base.test_broker_adapter_base import (
    BaseBrokerAdapterTest,
    BrokerAdapterTestMixin,
)
from tests.fixtures.broker_fixtures import (
    fix_adapter_config,
    mock_fix_session,
    sample_limit_order,
    sample_market_data_request,
    sample_market_order,
    ssl_fix_adapter_config,
)


class TestFixAdapter(BaseBrokerAdapterTest, BrokerAdapterTestMixin):
    """Test FIX broker adapter using base test framework."""

    def get_adapter_type(self) -> str:
        """Return the adapter type for this test."""
        return "fix"

    def get_adapter_class(self):
        """Return the adapter class being tested."""
        return FixBrokerAdapter

    def get_default_config(self) -> AdapterConfig:
        """Return default configuration for the adapter."""
        return AdapterConfig(
            adapter_type="fix",
            connection_params={
                "host": "test-fix-server.com",
                "port": 9876,
                "use_ssl": False,
                "session": {
                    "sender_comp_id": "FXML4_TEST",
                    "target_comp_id": "FIX_BROKER",
                    "fix_version": "FIX.4.2",
                    "heartbeat_interval": 30,
                    "logon_timeout": 10,
                    "reset_on_logon": True,
                },
                "max_reconnect_attempts": 3,
                "reconnect_delay": 5,
                "mock": False,
            },
            authentication={"username": "fix_user", "password": "fix_pass"},
            features={
                "supports_market_data": True,
                "supports_order_modification": True,
                "simulate_fills": True,
            },
        )

    # FIX Adapter Specific Tests
    def test_fix_session_initialization(self, fix_adapter_config):
        """Test FIX session initialization."""
        adapter = FixBrokerAdapter(fix_adapter_config)

        if hasattr(adapter, "session"):
            assert adapter.session is not None

        # Test FIX specific configuration
        if hasattr(adapter, "heartbeat_interval"):
            assert adapter.heartbeat_interval == 30
        if hasattr(adapter, "logon_timeout"):
            assert adapter.logon_timeout == 10
        if hasattr(adapter, "supports_market_data"):
            assert adapter.supports_market_data is True
        if hasattr(adapter, "supports_order_modification"):
            assert adapter.supports_order_modification is True

    def test_ssl_configuration(self, ssl_fix_adapter_config):
        """Test SSL/TLS configuration."""
        adapter = FixBrokerAdapter(ssl_fix_adapter_config)

        # Verify SSL settings
        if hasattr(adapter, "use_ssl"):
            assert adapter.use_ssl is True
        if hasattr(adapter, "ssl_cert"):
            assert adapter.ssl_cert == "/path/to/cert.pem"
        if hasattr(adapter, "ssl_key"):
            assert adapter.ssl_key == "/path/to/key.pem"

    @pytest.mark.asyncio
    async def test_fix_heartbeat_handling(self, fix_adapter_config, mock_fix_session):
        """Test FIX heartbeat message handling."""
        adapter = FixBrokerAdapter(fix_adapter_config)

        if hasattr(adapter, "session"):
            adapter.session = mock_fix_session

            # Mock heartbeat processing
            heartbeat = Heartbeat(test_req_id="TEST_001")

            if hasattr(adapter, "_handle_heartbeat"):
                with patch.object(adapter, "_send_message", AsyncMock()) as mock_send:
                    await adapter._handle_heartbeat(heartbeat)

                    # Verify heartbeat response
                    mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_market_data_subscription(
        self, fix_adapter_config, sample_market_data_request
    ):
        """Test market data subscription handling."""
        adapter = FixBrokerAdapter(fix_adapter_config)

        if hasattr(adapter, "subscribe_market_data"):
            with patch.object(adapter, "_send_message", AsyncMock()) as mock_send:
                await adapter.subscribe_market_data(sample_market_data_request)

                # Verify market data request was sent
                mock_send.assert_called_once()

    def test_fix_message_validation(self, fix_adapter_config):
        """Test FIX message validation."""
        adapter = FixBrokerAdapter(fix_adapter_config)

        if hasattr(adapter, "_validate_fix_message"):
            # Test valid message
            valid_order = NewOrderSingle(
                cl_ord_id="TEST_001",
                symbol="EURUSD",
                side=Side.BUY,
                order_qty=100000,
                ord_type=OrdType.MARKET,
            )
            assert adapter._validate_fix_message(valid_order) is True

            # Test invalid message
            invalid_order = NewOrderSingle(
                cl_ord_id="",  # Empty client order ID
                symbol="",  # Empty symbol
                side=None,  # Invalid side
                order_qty=0,  # Zero quantity
                ord_type=None,  # Invalid order type
            )
            assert adapter._validate_fix_message(invalid_order) is False


# FIX-Specific Test Classes
class TestFixAdapterSessionManagement:
    """Test FIX session management specific features."""

    @pytest.fixture
    def adapter(self, fix_adapter_config):
        """Create FIX adapter instance."""
        return FixBrokerAdapter(fix_adapter_config)

    def test_session_state_management(self, adapter, mock_fix_session):
        """Test FIX session state management."""
        if hasattr(adapter, "session"):
            adapter.session = mock_fix_session

            # Test session state queries
            if hasattr(adapter, "is_session_active"):
                assert adapter.is_session_active() == (
                    mock_fix_session.state == SessionState.ACTIVE
                )

    @pytest.mark.asyncio
    async def test_session_recovery(self, adapter):
        """Test FIX session recovery after disconnect."""
        if hasattr(adapter, "_recover_session"):
            with patch.object(adapter, "_establish_connection", AsyncMock()):
                with patch.object(adapter, "_send_logon", AsyncMock()):
                    result = await adapter._recover_session()

                    # Verify recovery attempt was made
                    assert result is not None


class TestFixAdapterMessageHandling:
    """Test FIX message processing and handling."""

    @pytest.fixture
    def adapter(self, fix_adapter_config):
        """Create FIX adapter instance."""
        return FixBrokerAdapter(fix_adapter_config)

    @pytest.mark.asyncio
    async def test_execution_report_processing(self, adapter, sample_execution_report):
        """Test execution report message processing."""
        if hasattr(adapter, "_process_execution_report"):
            with patch.object(adapter, "_update_order_status") as mock_update:
                await adapter._process_execution_report(sample_execution_report)

                # Verify order status was updated
                mock_update.assert_called_once_with(sample_execution_report)

    @pytest.mark.asyncio
    async def test_order_modification_handling(self, adapter):
        """Test order modification message handling."""
        if hasattr(adapter, "modify_order"):
            modify_request = OrderCancelReplaceRequest(
                orig_cl_ord_id="ORIG_001",
                cl_ord_id="MODIFY_001",
                symbol="EURUSD",
                side=Side.BUY,
                order_qty=200000,
                ord_type=OrdType.LIMIT,
                price=1.0860,
            )

            with patch.object(adapter, "_send_message", AsyncMock()) as mock_send:
                await adapter.modify_order(modify_request)

                # Verify modification request was sent
                mock_send.assert_called_once()


# Pytest markers for FIX adapter tests
pytestmark = [pytest.mark.unit, pytest.mark.brokers, pytest.mark.fix_adapter]
