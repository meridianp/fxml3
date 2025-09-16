"""
Test emergency stop and kill switch functionality.

This module tests the emergency procedures for immediately halting
all trading activity in crisis situations.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from enum import Enum
from unittest.mock import AsyncMock, Mock, call, patch

import pytest

from fxml4.brokers.risk.emergency import EmergencyStopManager
from fxml4.brokers.risk.manager import FXRiskManager
from fxml4.brokers.risk.models import (
    EmergencyStopReason,
    EmergencyStopStatus,
    RiskCheckResult,
    RiskViolationType,
)
from fxml4.fix.messages.base import Order, OrdType, Side


class EmergencyLevel(Enum):
    """Emergency severity levels."""

    WARNING = 1
    CRITICAL = 2
    SHUTDOWN = 3


@pytest.fixture
def risk_manager():
    """Create risk manager with emergency stop capability."""
    manager = FXRiskManager()
    manager.emergency_manager = EmergencyStopManager()
    return manager


@pytest.fixture
def sample_orders():
    """Create sample orders for testing."""
    orders = []
    for i in range(5):
        order = Order()
        order.order_id = f"TEST_ORDER_{i}"
        order.symbol = "EUR/USD"
        order.side = Side.BUY if i % 2 == 0 else Side.SELL
        order.quantity = 100_000 * (i + 1)
        order.price = 1.1000 + i * 0.0001
        order.order_type = OrdType.LIMIT
        orders.append(order)
    return orders


class TestEmergencyStopActivation:
    """Test emergency stop activation mechanisms."""

    def test_manual_emergency_stop(self, risk_manager):
        """Test manual activation of emergency stop."""
        # Activate emergency stop
        result = risk_manager.activate_emergency_stop(
            reason=EmergencyStopReason.MANUAL,
            activated_by="risk_manager_1",
            comments="Suspicious market activity detected",
        )

        assert result.success is True
        assert result.status == EmergencyStopStatus.ACTIVE
        assert risk_manager.emergency_manager.is_active is True
        assert result.activated_at <= datetime.now(timezone.utc)

        # Verify all trading is blocked
        order = Order()
        order.order_id = "POST_STOP_1"
        order.symbol = "EUR/USD"
        order.side = Side.BUY
        order.quantity = 100_000

        validation = risk_manager.validate_order(order)
        assert validation.passed is False
        assert any(
            v.type == RiskViolationType.EMERGENCY_STOP for v in validation.violations
        )

    def test_automatic_loss_limit_trigger(self, risk_manager):
        """Test automatic emergency stop on catastrophic loss."""
        # Configure automatic triggers
        risk_manager.emergency_manager.loss_limit_trigger = 100_000  # $100K

        # Simulate catastrophic loss
        risk_manager.loss_tracker.daily_loss = -120_000

        # Check should trigger emergency stop
        risk_manager.check_emergency_conditions()

        assert risk_manager.emergency_manager.is_active is True
        assert risk_manager.emergency_manager.reason == EmergencyStopReason.LOSS_LIMIT
        assert risk_manager.emergency_manager.auto_triggered is True

    def test_system_error_trigger(self, risk_manager):
        """Test emergency stop on critical system errors."""
        # Simulate critical system errors
        errors = [
            "Database connection lost",
            "Market data feed disconnected",
            "Risk calculation engine failure",
            "Order routing system offline",
        ]

        for error in errors:
            risk_manager.report_critical_error(
                component="core_system",
                error_message=error,
                severity=EmergencyLevel.CRITICAL,
            )

        # Should trigger after threshold
        if (
            risk_manager.critical_error_count
            >= risk_manager.emergency_manager.error_threshold
        ):
            assert risk_manager.emergency_manager.is_active is True
            assert (
                risk_manager.emergency_manager.reason
                == EmergencyStopReason.SYSTEM_ERROR
            )

    def test_market_condition_trigger(self, risk_manager):
        """Test emergency stop on extreme market conditions."""
        # Configure market condition triggers
        risk_manager.emergency_manager.volatility_trigger = 0.05  # 5% move

        # Simulate extreme market move
        risk_manager.process_market_update(
            symbol="EUR/USD", old_price=1.1000, new_price=1.0400  # 5.5% drop
        )

        # Should trigger emergency stop
        risk_manager.check_emergency_conditions()

        assert risk_manager.emergency_manager.is_active is True
        assert (
            risk_manager.emergency_manager.reason
            == EmergencyStopReason.MARKET_CONDITION
        )
        assert "volatility" in risk_manager.emergency_manager.details.lower()


class TestEmergencyStopOperations:
    """Test operations during emergency stop."""

    @pytest.mark.asyncio
    async def test_cancel_all_pending_orders(self, risk_manager, sample_orders):
        """Test cancellation of all pending orders."""
        # Add pending orders
        for order in sample_orders:
            risk_manager.pending_orders[order.order_id] = order

        # Activate emergency stop
        risk_manager.activate_emergency_stop(
            reason=EmergencyStopReason.MANUAL, activated_by="admin"
        )

        # Should cancel all orders
        cancelled_orders = await risk_manager.emergency_cancel_all_orders()

        assert len(cancelled_orders) == len(sample_orders)
        assert len(risk_manager.pending_orders) == 0

        # Verify each order was cancelled
        for order_id in cancelled_orders:
            assert order_id in [o.order_id for o in sample_orders]

    def test_position_freeze(self, risk_manager):
        """Test position freezing during emergency stop."""
        # Create positions
        risk_manager.positions = {
            "EUR/USD": Mock(symbol="EUR/USD", net_quantity=1_000_000),
            "GBP/USD": Mock(symbol="GBP/USD", net_quantity=-500_000),
            "USD/JPY": Mock(symbol="USD/JPY", net_quantity=2_000_000),
        }

        # Activate emergency stop with position freeze
        risk_manager.activate_emergency_stop(
            reason=EmergencyStopReason.MANUAL,
            activated_by="risk_officer",
            freeze_positions=True,
        )

        # Try to modify positions
        order = Order()
        order.symbol = "EUR/USD"
        order.side = Side.SELL  # Would reduce position
        order.quantity = 500_000

        result = risk_manager.validate_order(order)

        assert result.passed is False
        assert "positions frozen" in result.violations[0].message.lower()

    def test_close_all_positions_mode(self, risk_manager):
        """Test emergency mode that only allows position closing."""
        # Set up positions
        risk_manager.positions = {
            "EUR/USD": Mock(symbol="EUR/USD", net_quantity=1_000_000, side=Side.BUY),
            "GBP/USD": Mock(symbol="GBP/USD", net_quantity=-500_000, side=Side.SELL),
        }

        # Activate emergency stop with close-only mode
        risk_manager.activate_emergency_stop(
            reason=EmergencyStopReason.MANUAL, activated_by="cro", mode="close_only"
        )

        # Test various orders
        test_cases = [
            # (symbol, side, quantity, should_pass)
            ("EUR/USD", Side.SELL, 500_000, True),  # Closing long - OK
            ("EUR/USD", Side.SELL, 1_500_000, False),  # Over-closing - NOT OK
            ("EUR/USD", Side.BUY, 100_000, False),  # Adding to position - NOT OK
            ("GBP/USD", Side.BUY, 300_000, True),  # Closing short - OK
            ("USD/JPY", Side.BUY, 100_000, False),  # New position - NOT OK
        ]

        for symbol, side, quantity, should_pass in test_cases:
            order = Order()
            order.symbol = symbol
            order.side = side
            order.quantity = quantity

            result = risk_manager.validate_order(order)
            assert (
                result.passed == should_pass
            ), f"Failed for {symbol} {side} {quantity}"

    def test_notification_cascade(self, risk_manager):
        """Test notification system during emergency stop."""
        # Mock notification channels
        notifications_sent = []

        with patch.object(risk_manager, "send_notification") as mock_notify:
            mock_notify.side_effect = (
                lambda channel, message, priority: notifications_sent.append(
                    (channel, priority)
                )
            )

            # Activate emergency stop
            risk_manager.activate_emergency_stop(
                reason=EmergencyStopReason.LOSS_LIMIT, activated_by="system"
            )

            # Verify notifications sent to all channels
            expected_channels = ["email", "sms", "slack", "pagerduty"]
            sent_channels = [n[0] for n in notifications_sent]

            for channel in expected_channels:
                assert channel in sent_channels

            # Verify high priority
            assert all(n[1] == "CRITICAL" for n in notifications_sent)


class TestEmergencyStopDeactivation:
    """Test emergency stop deactivation and recovery."""

    def test_manual_deactivation(self, risk_manager):
        """Test manual deactivation of emergency stop."""
        # First activate
        risk_manager.activate_emergency_stop(
            reason=EmergencyStopReason.MANUAL, activated_by="admin"
        )

        assert risk_manager.emergency_manager.is_active is True

        # Now deactivate
        result = risk_manager.deactivate_emergency_stop(
            deactivated_by="admin",
            verification_code="CONFIRM-12345",
            comments="Issue resolved, resuming normal operations",
        )

        assert result.success is True
        assert risk_manager.emergency_manager.is_active is False
        assert result.deactivated_at is not None

        # Verify trading resumed
        order = Order()
        order.symbol = "EUR/USD"
        order.side = Side.BUY
        order.quantity = 100_000
        order.price = 1.1000
        order.notional = 110_000

        validation = risk_manager.validate_order(order)
        assert validation.passed is True  # Should pass now

    def test_deactivation_requires_authorization(self, risk_manager):
        """Test deactivation requires proper authorization."""
        # Activate emergency stop
        risk_manager.activate_emergency_stop(
            reason=EmergencyStopReason.MANUAL, activated_by="trader"
        )

        # Try to deactivate without proper auth
        result = risk_manager.deactivate_emergency_stop(
            deactivated_by="trader", verification_code="WRONG-CODE"  # Not authorized
        )

        assert result.success is False
        assert "authorization" in result.error_message.lower()
        assert risk_manager.emergency_manager.is_active is True  # Still active

    def test_gradual_resumption(self, risk_manager):
        """Test gradual resumption of trading after emergency stop."""
        # Activate and then deactivate with gradual resumption
        risk_manager.activate_emergency_stop(
            reason=EmergencyStopReason.MANUAL, activated_by="admin"
        )

        risk_manager.deactivate_emergency_stop(
            deactivated_by="admin",
            verification_code="CONFIRM-12345",
            gradual_resumption=True,
            resumption_phases=[
                {"duration_minutes": 15, "limit_factor": 0.25},  # 25% limits
                {"duration_minutes": 30, "limit_factor": 0.50},  # 50% limits
                {"duration_minutes": 60, "limit_factor": 1.00},  # Full limits
            ],
        )

        # Check limits are reduced
        assert risk_manager.is_in_resumption_mode is True
        assert risk_manager.current_limit_factor == 0.25

        # Large order should fail due to reduced limits
        order = Order()
        order.symbol = "EUR/USD"
        order.side = Side.BUY
        order.quantity = 1_000_000  # Would be OK normally
        order.price = 1.1000
        order.notional = 1_100_000

        result = risk_manager.validate_order(order)
        assert result.passed is False
        assert "resumption mode" in result.violations[0].message.lower()

    def test_post_emergency_audit(self, risk_manager):
        """Test post-emergency audit trail."""
        # Activate emergency stop
        activation = risk_manager.activate_emergency_stop(
            reason=EmergencyStopReason.LOSS_LIMIT, activated_by="system"
        )

        # Simulate some blocked activities
        for i in range(10):
            order = Order()
            order.order_id = f"BLOCKED_{i}"
            risk_manager.validate_order(order)

        # Deactivate
        deactivation = risk_manager.deactivate_emergency_stop(
            deactivated_by="cro", verification_code="CONFIRM-99999"
        )

        # Get audit report
        audit_report = risk_manager.get_emergency_stop_audit(activation.stop_id)

        assert audit_report.stop_id == activation.stop_id
        assert (
            audit_report.duration
            == deactivation.deactivated_at - activation.activated_at
        )
        assert audit_report.orders_blocked == 10
        assert audit_report.activated_by == "system"
        assert audit_report.deactivated_by == "cro"


class TestEmergencyStopIntegration:
    """Test emergency stop integration with other systems."""

    @pytest.mark.asyncio
    async def test_broker_connection_freeze(self, risk_manager):
        """Test freezing all broker connections."""
        # Mock broker connections
        risk_manager.broker_connections = {
            "IB": AsyncMock(),
            "FIX": AsyncMock(),
            "REST_API": AsyncMock(),
        }

        # Activate emergency stop
        risk_manager.activate_emergency_stop(
            reason=EmergencyStopReason.MANUAL, activated_by="admin"
        )

        # Should disconnect all brokers
        for broker_name, connection in risk_manager.broker_connections.items():
            connection.disconnect.assert_called_once()
            connection.freeze_orders.assert_called_once()

    def test_database_state_persistence(self, risk_manager):
        """Test emergency stop state is persisted."""
        with patch("fxml4.brokers.risk.emergency.save_to_database") as mock_save:
            # Activate emergency stop
            activation = risk_manager.activate_emergency_stop(
                reason=EmergencyStopReason.MANUAL, activated_by="admin"
            )

            # Verify saved to database
            mock_save.assert_called()
            saved_data = mock_save.call_args[0][0]

            assert saved_data["stop_id"] == activation.stop_id
            assert saved_data["reason"] == EmergencyStopReason.MANUAL.value
            assert saved_data["is_active"] is True

    def test_monitoring_system_alerts(self, risk_manager):
        """Test monitoring system integration."""
        # Mock monitoring system
        with patch("fxml4.brokers.risk.monitoring.send_metric") as mock_metric:
            # Activate emergency stop
            risk_manager.activate_emergency_stop(
                reason=EmergencyStopReason.SYSTEM_ERROR, activated_by="system"
            )

            # Verify metrics sent
            expected_metrics = [
                ("emergency_stop.activated", 1),
                ("emergency_stop.reason", "SYSTEM_ERROR"),
                ("trading.enabled", 0),
            ]

            for metric_name, value in expected_metrics:
                mock_metric.assert_any_call(metric_name, value)


class TestEmergencyStopEdgeCases:
    """Test edge cases and failure scenarios."""

    def test_concurrent_activation_attempts(self, risk_manager):
        """Test handling concurrent activation attempts."""
        # First activation
        result1 = risk_manager.activate_emergency_stop(
            reason=EmergencyStopReason.MANUAL, activated_by="admin1"
        )

        # Second activation attempt
        result2 = risk_manager.activate_emergency_stop(
            reason=EmergencyStopReason.LOSS_LIMIT, activated_by="admin2"
        )

        assert result1.success is True
        assert result2.success is False
        assert "already active" in result2.error_message.lower()

    def test_deactivation_during_market_stress(self, risk_manager):
        """Test preventing deactivation during ongoing crisis."""
        # Activate due to market condition
        risk_manager.activate_emergency_stop(
            reason=EmergencyStopReason.MARKET_CONDITION, activated_by="system"
        )

        # Market still volatile
        risk_manager.current_market_volatility = 0.08  # 8% - still high

        # Try to deactivate
        result = risk_manager.deactivate_emergency_stop(
            deactivated_by="admin",
            verification_code="CONFIRM-12345",
            force=False,  # Not forcing
        )

        assert result.success is False
        assert "market conditions" in result.error_message.lower()

        # Force deactivation should work
        result = risk_manager.deactivate_emergency_stop(
            deactivated_by="admin", verification_code="CONFIRM-12345", force=True
        )

        assert result.success is True

    def test_emergency_stop_timeout(self, risk_manager):
        """Test automatic timeout of emergency stop."""
        # Configure timeout
        risk_manager.emergency_manager.auto_timeout_hours = 4

        # Activate with auto-timeout
        activation_time = datetime.now(timezone.utc) - timedelta(hours=5)

        with patch("fxml4.brokers.risk.emergency.datetime") as mock_datetime:
            mock_datetime.now.return_value = activation_time

            risk_manager.activate_emergency_stop(
                reason=EmergencyStopReason.MANUAL, activated_by="admin"
            )

        # Check timeout
        risk_manager.check_emergency_stop_timeout()

        # Should be auto-deactivated
        assert risk_manager.emergency_manager.is_active is False
        assert risk_manager.emergency_manager.auto_deactivated is True
