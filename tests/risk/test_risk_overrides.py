"""
Test risk override authority and workflow.

This module tests the risk override mechanisms that allow authorized
personnel to temporarily bypass risk limits with proper audit trails.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from fxml4.brokers.risk.manager import FXRiskManager
from fxml4.brokers.risk.models import (
    RiskCheckResult,
    RiskLimits,
    RiskOverride,
    RiskOverrideStatus,
    RiskViolationType,
)
from fxml4.fix.messages.base import Order, Side


@pytest.fixture
def risk_limits():
    """Create test risk limits."""
    limits = RiskLimits()
    limits.max_single_position_notional = 1_000_000  # $1M
    limits.max_daily_loss = 50_000  # $50K
    limits.override_authority_levels = {
        "trader": [],  # No override authority
        "senior_trader": ["position_limit"],
        "risk_manager": ["position_limit", "loss_limit", "price_deviation"],
        "chief_risk_officer": ["*"],  # Can override anything
    }
    return limits


@pytest.fixture
def risk_manager(risk_limits):
    """Create risk manager instance."""
    return FXRiskManager(limits=risk_limits)


@pytest.fixture
def sample_order():
    """Create sample order that violates limits."""
    order = Order()
    order.order_id = f"ORDER_{uuid4()}"
    order.symbol = "EUR/USD"
    order.side = Side.BUY
    order.quantity = 2_000_000  # Exceeds $1M limit
    order.price = 1.1000
    order.notional = order.quantity * order.price
    return order


class TestRiskOverrideAuthority:
    """Test risk override authority levels."""

    def test_no_override_authority(self, risk_manager, sample_order):
        """Test user with no override authority cannot override."""
        # Check without override - should fail
        result = risk_manager.check_position_limits(sample_order)
        assert result.passed is False

        # Attempt override as trader (no authority)
        override_result = risk_manager.request_override(
            order=sample_order,
            violations=result.violations,
            requested_by="trader123",
            user_role="trader",
            reason="Market opportunity",
        )

        assert override_result.approved is False
        assert override_result.status == RiskOverrideStatus.DENIED
        assert "insufficient authority" in override_result.denial_reason.lower()

    def test_partial_override_authority(self, risk_manager, sample_order):
        """Test user with partial override authority."""
        # Add loss limit violation
        risk_manager.loss_tracker.daily_loss = -50_000

        # Check limits - should have multiple violations
        result = risk_manager.validate_order(sample_order)
        assert len(result.violations) >= 2

        # Senior trader can only override position limits
        override_result = risk_manager.request_override(
            order=sample_order,
            violations=result.violations,
            requested_by="senior_trader1",
            user_role="senior_trader",
            reason="Large client order",
        )

        # Should be partially approved
        assert override_result.approved is False  # Still fails on loss limit
        assert "partial authority" in override_result.denial_reason.lower()

    def test_full_override_authority(self, risk_manager, sample_order):
        """Test user with full override authority."""
        # Add multiple violations
        risk_manager.loss_tracker.daily_loss = -50_000

        result = risk_manager.validate_order(sample_order)
        assert result.passed is False

        # Chief Risk Officer can override everything
        override_result = risk_manager.request_override(
            order=sample_order,
            violations=result.violations,
            requested_by="cro1",
            user_role="chief_risk_officer",
            reason="Strategic position approved by committee",
        )

        assert override_result.approved is True
        assert override_result.status == RiskOverrideStatus.APPROVED
        assert override_result.approved_by == "cro1"

    def test_violation_type_authority_check(self, risk_manager):
        """Test specific violation type authority checking."""
        # Risk manager can override specific types
        authority_check = risk_manager.check_override_authority(
            user_role="risk_manager",
            violation_types=[
                RiskViolationType.POSITION_LIMIT,
                RiskViolationType.PRICE_DEVIATION,
            ],
        )
        assert authority_check is True

        # But not all types
        authority_check = risk_manager.check_override_authority(
            user_role="risk_manager",
            violation_types=[
                RiskViolationType.POSITION_LIMIT,
                RiskViolationType.SYMBOL_RESTRICTION,  # Not in their authority
            ],
        )
        assert authority_check is False


class TestRiskOverrideWorkflow:
    """Test complete risk override workflow."""

    def test_override_request_creation(self, risk_manager, sample_order):
        """Test creating override request with proper data."""
        result = risk_manager.check_position_limits(sample_order)

        override_request = RiskOverride(
            override_id=f"OVERRIDE_{uuid4()}",
            order_id=sample_order.order_id,
            violations=result.violations,
            requested_by="risk_manager1",
            requested_at=datetime.now(timezone.utc),
            reason="VIP client requirement",
            status=RiskOverrideStatus.PENDING,
        )

        assert override_request.status == RiskOverrideStatus.PENDING
        assert len(override_request.violations) > 0
        assert override_request.expires_at is None  # Not yet approved

    def test_override_approval_workflow(self, risk_manager, sample_order):
        """Test complete override approval workflow."""
        # Initial check fails
        result = risk_manager.check_position_limits(sample_order)
        assert result.passed is False

        # Request override
        override = risk_manager.request_override(
            order=sample_order,
            violations=result.violations,
            requested_by="trader1",
            user_role="trader",
            reason="Large institutional order",
            approver_id="risk_manager1",
        )

        # Approve override (as risk manager)
        approval = risk_manager.approve_override(
            override_id=override.override_id,
            approved_by="risk_manager1",
            approver_role="risk_manager",
            comments="Approved with 1hr time limit",
            duration_minutes=60,
        )

        assert approval.status == RiskOverrideStatus.APPROVED
        assert approval.approved_by == "risk_manager1"
        assert approval.expires_at > datetime.now(timezone.utc)

        # Order should now pass with override
        result_with_override = risk_manager.check_position_limits(
            sample_order, override_id=override.override_id
        )
        assert result_with_override.passed is True
        assert result_with_override.override_applied is True

    def test_override_expiration(self, risk_manager, sample_order):
        """Test override expiration handling."""
        # Create and approve override with short duration
        override = RiskOverride(
            override_id=f"OVERRIDE_{uuid4()}",
            order_id=sample_order.order_id,
            violations=[],
            requested_by="trader1",
            requested_at=datetime.now(timezone.utc),
            approved_by="risk_manager1",
            approved_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),  # Expired
            status=RiskOverrideStatus.APPROVED,
        )

        # Add to active overrides
        risk_manager.active_overrides[override.override_id] = override

        # Check should fail due to expiration
        result = risk_manager.check_position_limits(
            sample_order, override_id=override.override_id
        )

        assert result.passed is False
        assert "expired" in result.violations[0].message.lower()
        assert override.status == RiskOverrideStatus.EXPIRED

    def test_override_cancellation(self, risk_manager, sample_order):
        """Test override cancellation workflow."""
        # Create approved override
        override = risk_manager.request_override(
            order=sample_order,
            violations=[],
            requested_by="trader1",
            user_role="trader",
            reason="Test override",
        )

        # Approve it
        risk_manager.approve_override(
            override_id=override.override_id,
            approved_by="risk_manager1",
            approver_role="risk_manager",
        )

        # Cancel override
        cancellation = risk_manager.cancel_override(
            override_id=override.override_id,
            cancelled_by="risk_manager1",
            reason="Market conditions changed",
        )

        assert cancellation.status == RiskOverrideStatus.CANCELLED
        assert cancellation.cancelled_by == "risk_manager1"
        assert cancellation.cancelled_at is not None

        # Override should no longer be active
        assert override.override_id not in risk_manager.active_overrides


class TestRiskOverrideAuditTrail:
    """Test risk override audit trail functionality."""

    def test_override_audit_logging(self, risk_manager, sample_order):
        """Test comprehensive audit logging of overrides."""
        # Mock audit logger
        with patch.object(risk_manager, "audit_logger") as mock_logger:
            # Request override
            override = risk_manager.request_override(
                order=sample_order,
                violations=[],
                requested_by="trader1",
                user_role="trader",
                reason="Test audit",
            )

            # Verify request logged
            mock_logger.log_override_request.assert_called_once()
            call_args = mock_logger.log_override_request.call_args[0]
            assert call_args[0] == override.override_id
            assert call_args[1] == "trader1"

            # Approve override
            risk_manager.approve_override(
                override_id=override.override_id,
                approved_by="risk_manager1",
                approver_role="risk_manager",
            )

            # Verify approval logged
            mock_logger.log_override_approval.assert_called_once()

            # Use override
            risk_manager.check_position_limits(
                sample_order, override_id=override.override_id
            )

            # Verify usage logged
            mock_logger.log_override_usage.assert_called_once()

    def test_override_history_tracking(self, risk_manager):
        """Test tracking override history."""
        # Create multiple overrides
        overrides = []
        for i in range(5):
            order = Mock(order_id=f"ORDER_{i}")
            override = risk_manager.request_override(
                order=order,
                violations=[],
                requested_by=f"trader{i}",
                user_role="trader",
                reason=f"Test override {i}",
            )
            overrides.append(override)

        # Get override history
        history = risk_manager.get_override_history(
            start_date=datetime.now(timezone.utc) - timedelta(hours=1),
            end_date=datetime.now(timezone.utc),
        )

        assert len(history) >= 5
        assert all(o.override_id in [h.override_id for h in history] for o in overrides)

    def test_override_metrics(self, risk_manager):
        """Test override metrics and reporting."""
        # Create overrides with different statuses
        for i in range(10):
            override = risk_manager.request_override(
                order=Mock(order_id=f"ORDER_{i}"),
                violations=[],
                requested_by="trader1",
                user_role="trader",
                reason="Test",
            )

            if i < 6:  # 60% approval rate
                risk_manager.approve_override(
                    override_id=override.override_id,
                    approved_by="risk_manager1",
                    approver_role="risk_manager",
                )

        # Get metrics
        metrics = risk_manager.get_override_metrics(period_days=1)

        assert metrics.total_requests == 10
        assert metrics.approved_count == 6
        assert metrics.approval_rate == 0.6
        assert "trader1" in metrics.top_requesters


class TestRiskOverrideEdgeCases:
    """Test edge cases in risk override system."""

    def test_multiple_concurrent_overrides(self, risk_manager, sample_order):
        """Test handling multiple overrides for same order."""
        # Create first override
        override1 = risk_manager.request_override(
            order=sample_order,
            violations=[],
            requested_by="trader1",
            user_role="trader",
            reason="Override 1",
        )

        # Attempt second override for same order
        override2 = risk_manager.request_override(
            order=sample_order,
            violations=[],
            requested_by="trader2",
            user_role="trader",
            reason="Override 2",
        )

        # Should handle gracefully - either reject or supersede
        assert override2.override_id != override1.override_id

        # Check active override count for order
        active_count = risk_manager.get_active_override_count(sample_order.order_id)
        assert active_count <= 1  # Should only allow one active override per order

    def test_override_during_market_hours(self, risk_manager, sample_order):
        """Test override restrictions during market hours."""
        # Mock market hours check
        with patch.object(risk_manager, "is_market_hours", return_value=True):
            override = risk_manager.request_override(
                order=sample_order,
                violations=[Mock(type=RiskViolationType.POSITION_LIMIT)],
                requested_by="trader1",
                user_role="trader",
                reason="Urgent trade",
            )

            # During market hours, might require higher authority
            if risk_manager.limits.require_higher_authority_during_market:
                assert override.status == RiskOverrideStatus.PENDING_ESCALATION

    def test_override_value_limits(self, risk_manager):
        """Test override value/notional limits."""
        # Create order exceeding override limits
        huge_order = Order()
        huge_order.order_id = "HUGE_ORDER"
        huge_order.symbol = "EUR/USD"
        huge_order.quantity = 50_000_000  # $50M
        huge_order.price = 1.1000
        huge_order.notional = 55_000_000

        # Even CRO might have limits
        override = risk_manager.request_override(
            order=huge_order,
            violations=[],
            requested_by="cro1",
            user_role="chief_risk_officer",
            reason="Large position",
        )

        # Check if there are override value limits
        if hasattr(risk_manager.limits, "max_override_notional"):
            if huge_order.notional > risk_manager.limits.max_override_notional:
                assert override.status == RiskOverrideStatus.DENIED
                assert "exceeds maximum override limit" in override.denial_reason

    @pytest.mark.parametrize("violation_count", [1, 5, 10])
    def test_multiple_violation_overrides(
        self, risk_manager, sample_order, violation_count
    ):
        """Test overriding multiple violations simultaneously."""
        # Create multiple violations
        violations = []
        for i in range(violation_count):
            violations.append(
                Mock(type=RiskViolationType.POSITION_LIMIT, message=f"Violation {i}")
            )

        # Request override for all violations
        override = risk_manager.request_override(
            order=sample_order,
            violations=violations,
            requested_by="risk_manager1",
            user_role="risk_manager",
            reason="Multiple violations override",
        )

        # Should handle all violations
        assert len(override.violations) == violation_count

        # Approve should cover all violations
        if override.status != RiskOverrideStatus.DENIED:
            approval = risk_manager.approve_override(
                override_id=override.override_id,
                approved_by="cro1",
                approver_role="chief_risk_officer",
            )
            assert approval.status == RiskOverrideStatus.APPROVED
