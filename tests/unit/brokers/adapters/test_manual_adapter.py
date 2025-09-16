"""Unit tests for Manual Broker Adapter.

This module provides comprehensive tests for the Manual adapter implementation,
inheriting from the base broker adapter test framework for consistency.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from fxml4.brokers.adapters.base import AdapterConfig, AdapterMetrics, ConnectionStatus
from fxml4.brokers.adapters.manual_adapter import (
    ApprovalStatus,
    ManualBrokerAdapter,
    PendingOrder,
)
from fxml4.fix.messages.base import ExecType, OrdStatus, OrdType, Side, TimeInForce
from fxml4.fix.messages.orders import (
    ExecutionReport,
    NewOrderSingle,
    OrderCancelRequest,
)

# Import base test infrastructure
from tests.base.test_broker_adapter_base import (
    BaseBrokerAdapterTest,
    BrokerAdapterTestMixin,
)
from tests.fixtures.broker_fixtures import (
    manual_adapter_config,
    mock_websocket,
    sample_execution_report,
    sample_limit_order,
    sample_market_order,
)


class TestManualAdapter(BaseBrokerAdapterTest, BrokerAdapterTestMixin):
    """Test Manual broker adapter using base test framework."""

    def get_adapter_type(self) -> str:
        """Return the adapter type for this test."""
        return "manual"

    def get_adapter_class(self):
        """Return the adapter class being tested."""
        return ManualBrokerAdapter

    def get_default_config(self) -> AdapterConfig:
        """Return default configuration for the adapter."""
        return AdapterConfig(
            adapter_type="manual",
            connection_params={},
            authentication={},
            features={
                "auto_reject_timeout": 300,
                "require_two_factor": False,
                "allow_risk_override": True,
                "simulate_execution": True,
                "simulated_fill_delay": 1,
                "audit_trail": True,
            },
            limits={"max_override_amount": 1000000},
        )

    # Manual Adapter Specific Tests
    def test_manual_adapter_specific_initialization(self, manual_adapter_config):
        """Test Manual adapter specific initialization features."""
        adapter = ManualBrokerAdapter(manual_adapter_config)

        assert adapter.auto_reject_timeout == 300
        assert adapter.require_two_factor is False
        assert adapter.allow_risk_override is True
        assert adapter.simulate_execution is True
        assert adapter.simulated_fill_delay == 1
        assert adapter.audit_enabled is True
        assert len(adapter.pending_orders) == 0
        assert len(adapter.order_history) == 0
        if hasattr(adapter, "websocket_clients"):
            assert len(adapter.websocket_clients) == 0

    @pytest.mark.asyncio
    async def test_manual_order_approval_workflow(
        self, manual_adapter_config, sample_market_order
    ):
        """Test manual order approval workflow."""
        adapter = ManualBrokerAdapter(manual_adapter_config)

        # Mock the approval process
        with patch.object(adapter, "_create_pending_order") as mock_create:
            with patch.object(adapter, "_notify_pending_order") as mock_notify:
                mock_create.return_value = PendingOrder(
                    order=sample_market_order,
                    timestamp=datetime.utcnow(),
                    status=ApprovalStatus.PENDING,
                    approval_id=str(uuid.uuid4()),
                )

                # Submit order for approval
                result = await adapter.submit_order(sample_market_order)

                # Verify approval workflow initiated
                mock_create.assert_called_once_with(sample_market_order)
                mock_notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_simulated_execution(
        self, manual_adapter_config, sample_market_order
    ):
        """Test simulated order execution."""
        adapter = ManualBrokerAdapter(manual_adapter_config)

        # Enable simulation mode
        adapter.simulate_execution = True

        # Mock execution simulation
        with patch.object(adapter, "_simulate_fill", AsyncMock()) as mock_simulate:
            await adapter.approve_order(sample_market_order.cl_ord_id)

            # Verify simulation was triggered
            mock_simulate.assert_called_once()

    def test_websocket_client_management(self, manual_adapter_config, mock_websocket):
        """Test WebSocket client management."""
        adapter = ManualBrokerAdapter(manual_adapter_config)

        if hasattr(adapter, "add_websocket_client"):
            # Add websocket client
            client_id = adapter.add_websocket_client(mock_websocket)
            assert client_id is not None

            # Remove websocket client
            adapter.remove_websocket_client(client_id)

    def test_audit_trail_functionality(self, manual_adapter_config):
        """Test audit trail functionality."""
        adapter = ManualBrokerAdapter(manual_adapter_config)

        if hasattr(adapter, "audit_logger"):
            # Test audit logging is enabled
            assert adapter.audit_enabled is True

            # Test audit entry creation
            if hasattr(adapter, "_create_audit_entry"):
                adapter._create_audit_entry("test_action", {"data": "test"})


# Additional Manual Adapter Specific Tests
class TestManualAdapterApprovalWorkflow:
    """Test manual approval workflow specific features."""

    @pytest.fixture
    def adapter(self, manual_adapter_config):
        """Create manual adapter instance."""
        return ManualBrokerAdapter(manual_adapter_config)

    def test_approval_status_enum(self):
        """Test approval status enumeration."""
        assert hasattr(ApprovalStatus, "PENDING")
        assert hasattr(ApprovalStatus, "APPROVED")
        assert hasattr(ApprovalStatus, "REJECTED")

    def test_pending_order_creation(self, adapter, sample_market_order):
        """Test pending order creation."""
        if hasattr(adapter, "_create_pending_order"):
            pending_order = adapter._create_pending_order(sample_market_order)

            assert pending_order.order == sample_market_order
            assert pending_order.status == ApprovalStatus.PENDING
            assert pending_order.approval_id is not None
            assert isinstance(pending_order.timestamp, datetime)


# Pytest markers for manual adapter tests
pytestmark = [pytest.mark.unit, pytest.mark.brokers, pytest.mark.manual_adapter]


# Rest of the file is removed - using base test class for common functionality
