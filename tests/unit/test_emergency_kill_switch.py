"""
Unit tests for Emergency Kill Switch.

Tests critical safety mechanism for instant trading shutdown including:
- Immediate order cancellation
- Position flattening
- Connection termination
- Risk limit enforcement
- Cascade prevention
- Recovery procedures
- Audit logging
- Multi-level triggers
- Partial shutdowns
- Automatic circuit breakers
"""

import asyncio
import threading
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from freezegun import freeze_time

from core.exceptions import EmergencyShutdownError, RiskError
from core.order_management.order_types import Order, OrderSide, OrderStatus, OrderType
from core.trading.emergency_kill_switch import EmergencyKillSwitch, KillSwitchLevel


class TestEmergencyKillSwitch:
    """Test suite for emergency trading shutdown mechanism."""

    @pytest.fixture
    def kill_switch_config(self):
        """Configuration for emergency kill switch."""
        return {
            "max_daily_loss": Decimal("100000"),
            "max_position_size": Decimal("10000000"),
            "max_order_rate": 100,  # orders per minute
            "error_threshold": 10,  # errors before trigger
            "latency_threshold_ms": 1000,
            "auto_trigger_enabled": True,
            "cascade_prevention": True,
            "recovery_timeout_seconds": 300,
            "audit_logging": True,
            "notification_channels": ["email", "sms", "slack"],
            "partial_shutdown_enabled": True,
            "circuit_breaker_levels": [
                {"threshold": 0.02, "duration": 60},  # 2% loss - 1 min halt
                {"threshold": 0.05, "duration": 300},  # 5% loss - 5 min halt
                {"threshold": 0.10, "duration": 1800},  # 10% loss - 30 min halt
            ],
        }

    @pytest.fixture
    def mock_order_manager(self):
        """Mock order manager for testing."""
        order_mgr = MagicMock()
        order_mgr.active_orders = {
            "ORDER_001": Order(
                order_id="ORDER_001",
                symbol="EUR/USD",
                order_type=OrderType.MARKET,
                side=OrderSide.BUY,
                quantity=100000,
                client_id="CLIENT_001",
                status=OrderStatus.SUBMITTED,
            ),
            "ORDER_002": Order(
                order_id="ORDER_002",
                symbol="GBP/USD",
                order_type=OrderType.LIMIT,
                side=OrderSide.SELL,
                quantity=150000,
                client_id="CLIENT_001",
                status=OrderStatus.PARTIALLY_FILLED,
            ),
        }
        order_mgr.cancel_order = AsyncMock(return_value={"status": "cancelled"})
        return order_mgr

    @pytest.fixture
    def mock_execution_engine(self):
        """Mock execution engine for testing."""
        exec_engine = MagicMock()
        exec_engine.executing_orders = {"EXEC_001": {}, "EXEC_002": {}}
        exec_engine.halt_execution = AsyncMock()
        return exec_engine

    @pytest.fixture
    def mock_risk_manager(self):
        """Mock risk manager for testing."""
        risk_mgr = MagicMock()
        risk_mgr.get_current_pnl.return_value = Decimal("-50000")
        risk_mgr.get_total_exposure.return_value = Decimal("5000000")
        return risk_mgr

    @pytest.fixture
    def mock_broker_connections(self):
        """Mock broker connections for testing."""
        return {
            "IB": MagicMock(disconnect=AsyncMock()),
            "FXCM": MagicMock(disconnect=AsyncMock()),
            "OANDA": MagicMock(disconnect=AsyncMock()),
        }

    @pytest.fixture
    def mock_notification_service(self):
        """Mock notification service for testing."""
        notifier = MagicMock()
        notifier.send_alert = AsyncMock()
        return notifier

    @pytest.fixture
    def kill_switch(
        self,
        kill_switch_config,
        mock_order_manager,
        mock_execution_engine,
        mock_risk_manager,
        mock_broker_connections,
        mock_notification_service,
    ):
        """Create emergency kill switch for testing."""
        return EmergencyKillSwitch(
            config=kill_switch_config,
            order_manager=mock_order_manager,
            execution_engine=mock_execution_engine,
            risk_manager=mock_risk_manager,
            broker_connections=mock_broker_connections,
            notification_service=mock_notification_service,
        )

    @pytest.mark.asyncio
    async def test_triggers_emergency_shutdown(self, kill_switch):
        """Test immediate emergency shutdown trigger."""
        result = await kill_switch.trigger_emergency_shutdown(
            reason="Manual trigger - suspicious activity detected"
        )

        assert result["status"] == "shutdown_complete"
        assert result["level"] == KillSwitchLevel.FULL
        assert "timestamp" in result
        assert "orders_cancelled" in result
        assert "connections_terminated" in result

    @pytest.mark.asyncio
    async def test_cancels_all_active_orders(self, kill_switch, mock_order_manager):
        """Test cancellation of all active orders during shutdown."""
        await kill_switch.cancel_all_orders()

        # Verify all orders were cancelled
        assert mock_order_manager.cancel_order.call_count == 2
        mock_order_manager.cancel_order.assert_any_call(
            "ORDER_001", reason="emergency_shutdown"
        )
        mock_order_manager.cancel_order.assert_any_call(
            "ORDER_002", reason="emergency_shutdown"
        )

    @pytest.mark.asyncio
    async def test_flattens_all_positions(self, kill_switch):
        """Test position flattening during emergency shutdown."""
        positions = {
            "EUR/USD": {"quantity": 1000000, "side": "long"},
            "GBP/USD": {"quantity": -500000, "side": "short"},
        }

        result = await kill_switch.flatten_all_positions(positions)

        assert result["status"] == "positions_flattened"
        assert len(result["flatten_orders"]) == 2
        assert result["total_exposure_removed"] > 0

    @pytest.mark.asyncio
    async def test_terminates_broker_connections(
        self, kill_switch, mock_broker_connections
    ):
        """Test termination of all broker connections."""
        await kill_switch.terminate_all_connections()

        for broker_name, connection in mock_broker_connections.items():
            connection.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_monitors_risk_limits(self, kill_switch, mock_risk_manager):
        """Test automatic trigger based on risk limit breach."""
        # Simulate large loss exceeding daily limit
        mock_risk_manager.get_current_pnl.return_value = Decimal("-150000")

        triggered = await kill_switch.monitor_risk_limits()

        assert triggered is True
        assert kill_switch.is_active is True

    @pytest.mark.asyncio
    async def test_implements_circuit_breakers(self, kill_switch, mock_risk_manager):
        """Test multi-level circuit breaker implementation."""
        # Test 2% loss circuit breaker
        mock_risk_manager.get_current_pnl.return_value = Decimal("-20000")
        mock_risk_manager.get_initial_capital.return_value = Decimal("1000000")

        circuit_breaker = await kill_switch.check_circuit_breakers()

        assert circuit_breaker["triggered"] is True
        assert circuit_breaker["level"] == 0
        assert circuit_breaker["duration"] == 60

    @pytest.mark.asyncio
    async def test_prevents_cascade_failures(self, kill_switch):
        """Test cascade failure prevention mechanism."""
        # Simulate multiple rapid triggers
        for i in range(5):
            await kill_switch.record_error(f"Error_{i}")

        # Should prevent cascade after threshold
        assert kill_switch.cascade_prevention_active is False

        # Add more errors to trigger cascade prevention
        for i in range(10):
            await kill_switch.record_error(f"Critical_Error_{i}")

        assert kill_switch.cascade_prevention_active is True

    @pytest.mark.asyncio
    async def test_partial_shutdown_by_symbol(self, kill_switch):
        """Test partial shutdown for specific symbols."""
        result = await kill_switch.partial_shutdown(
            symbols=["EUR/USD", "GBP/USD"], reason="Volatility spike detected"
        )

        assert result["status"] == "partial_shutdown"
        assert result["affected_symbols"] == ["EUR/USD", "GBP/USD"]
        assert result["level"] == KillSwitchLevel.PARTIAL

    @pytest.mark.asyncio
    async def test_partial_shutdown_by_broker(
        self, kill_switch, mock_broker_connections
    ):
        """Test partial shutdown for specific broker."""
        result = await kill_switch.shutdown_broker(
            broker="IB", reason="Connection instability"
        )

        assert result["status"] == "broker_shutdown"
        assert result["broker"] == "IB"
        mock_broker_connections["IB"].disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_monitors_order_rate_limits(self, kill_switch):
        """Test order rate limit monitoring and enforcement."""
        # Simulate rapid order submissions
        for i in range(150):  # Exceed 100 orders/minute limit
            await kill_switch.record_order_submission(f"ORDER_{i:04d}")

        rate_check = await kill_switch.check_order_rate()

        assert rate_check["rate_exceeded"] is True
        assert rate_check["current_rate"] > 100

    @pytest.mark.asyncio
    async def test_monitors_system_latency(self, kill_switch):
        """Test system latency monitoring and triggers."""
        # Simulate high latency
        for i in range(10):
            await kill_switch.record_latency(1500)  # 1500ms > 1000ms threshold

        latency_check = await kill_switch.check_latency_threshold()

        assert latency_check["threshold_exceeded"] is True
        assert latency_check["average_latency"] > 1000

    @pytest.mark.asyncio
    async def test_sends_notifications(self, kill_switch, mock_notification_service):
        """Test notification sending during emergency events."""
        await kill_switch.send_emergency_notifications(
            level=KillSwitchLevel.FULL, reason="Critical system failure"
        )

        # Verify notifications sent to all channels
        assert mock_notification_service.send_alert.call_count >= 3

        calls = mock_notification_service.send_alert.call_args_list
        channels = [call[1].get("channel") for call in calls if "channel" in call[1]]
        assert "email" in channels
        assert "sms" in channels
        assert "slack" in channels

    @pytest.mark.asyncio
    async def test_creates_audit_trail(self, kill_switch):
        """Test comprehensive audit trail creation."""
        await kill_switch.trigger_emergency_shutdown(reason="Test shutdown for audit")

        audit_log = kill_switch.get_audit_log()

        assert len(audit_log) > 0
        latest_entry = audit_log[-1]
        assert "timestamp" in latest_entry
        assert "action" in latest_entry
        assert "reason" in latest_entry
        assert latest_entry["action"] == "emergency_shutdown"

    @pytest.mark.asyncio
    async def test_recovery_procedures(self, kill_switch):
        """Test system recovery after emergency shutdown."""
        # Trigger shutdown
        await kill_switch.trigger_emergency_shutdown(reason="Test")
        assert kill_switch.is_active is True

        # Simulate time passing by manipulating shutdown_time
        original_shutdown_time = kill_switch.shutdown_time
        kill_switch.shutdown_time = original_shutdown_time - timedelta(seconds=301)

        recovery_result = await kill_switch.attempt_recovery()

        assert recovery_result["status"] == "recovery_initiated"
        assert kill_switch.is_active is False
        assert "checks_passed" in recovery_result

    @pytest.mark.asyncio
    async def test_manual_override(self, kill_switch):
        """Test manual override of automatic triggers."""
        # Enable manual override
        kill_switch.set_manual_override(True, authorized_by="ADMIN_001")

        # Trigger condition that would normally cause shutdown
        await kill_switch.monitor_risk_limits()

        # Should not trigger due to override
        assert kill_switch.is_active is False
        assert kill_switch.manual_override_active is True

    @pytest.mark.asyncio
    async def test_health_check_integration(self, kill_switch):
        """Test integration with system health checks."""
        health_status = await kill_switch.perform_health_check()

        assert "status" in health_status
        assert "components" in health_status
        assert "order_manager" in health_status["components"]
        assert "execution_engine" in health_status["components"]
        assert "broker_connections" in health_status["components"]

    @pytest.mark.asyncio
    async def test_handles_concurrent_triggers(self, kill_switch):
        """Test handling of concurrent shutdown triggers."""
        # Simulate multiple concurrent triggers
        tasks = [
            kill_switch.trigger_emergency_shutdown("Reason 1"),
            kill_switch.trigger_emergency_shutdown("Reason 2"),
            kill_switch.trigger_emergency_shutdown("Reason 3"),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Should handle gracefully with only one actual shutdown
        successful_shutdowns = [
            r
            for r in results
            if isinstance(r, dict) and r.get("status") == "shutdown_complete"
        ]
        assert len(successful_shutdowns) >= 1

    @pytest.mark.asyncio
    async def test_deadman_switch(self, kill_switch):
        """Test deadman switch functionality."""
        # Start deadman switch monitoring
        await kill_switch.start_deadman_switch(timeout_seconds=5)

        # Simulate heartbeat
        for i in range(3):
            await asyncio.sleep(1)
            await kill_switch.heartbeat()

        assert kill_switch.is_active is False

        # Stop heartbeat and wait for timeout
        await asyncio.sleep(6)

        # Should trigger after timeout
        assert kill_switch.deadman_triggered is True

    @pytest.mark.asyncio
    async def test_rollback_capability(self, kill_switch):
        """Test ability to rollback recent actions."""
        # Record actions
        await kill_switch.record_action("place_order", {"order_id": "TEST_001"})
        await kill_switch.record_action("modify_order", {"order_id": "TEST_001"})

        # Trigger rollback
        rollback_result = await kill_switch.rollback_recent_actions(seconds=60)

        assert rollback_result["status"] == "rollback_complete"
        assert rollback_result["actions_rolled_back"] >= 2
