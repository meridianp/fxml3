"""Test suite for Manual Execution Adapter with Comprehensive Audit Trail.

This comprehensive TDD test suite validates the manual execution adapter that provides
discretionary trading capabilities with enterprise-grade audit trail, risk management,
and multi-broker routing for human traders in the FXML4 trading system.

Test Categories:
- Manual order entry with advanced risk calculation and position sizing
- Multi-broker routing logic (Interactive Brokers, FXCM selection)
- Comprehensive audit trail for regulatory compliance and trade rationale
- Approval workflows for large positions and high-risk trades
- Real-time risk monitoring with automatic limit enforcement
- Performance tracking with live P&L and drawdown monitoring
- Integration with RabbitMQ message routing infrastructure
"""

import asyncio
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest

from fxml4.brokers.adapters.manual_execution_adapter import (
    ApprovalWorkflow,
    BrokerSelector,
    ManualApprovalRequired,
    ManualExecutionAdapter,
    ManualExecutionError,
    ManualTradeExecution,
    ManualTradeRequest,
    RiskAssessment,
    RiskCalculator,
    TradeAuditLogger,
)
from fxml4.messaging import (
    ExecutionMessage,
    MessagePriority,
    OrderMessage,
    RiskCheckMessage,
)
from fxml4.messaging.messages import OrderSide, OrderStatus, OrderType


class TestRiskCalculator:
    """Test risk calculation and position sizing functionality."""

    def test_risk_calculator_initialization(self):
        """Test risk calculator initialization with default parameters."""
        calculator = RiskCalculator(
            max_risk_per_trade_percent=2.0,
            max_portfolio_risk_percent=6.0,
            max_position_size_usd=100000,
            leverage_limit=10.0,
        )

        assert calculator.max_risk_per_trade_percent == 2.0
        assert calculator.max_portfolio_risk_percent == 6.0
        assert calculator.max_position_size_usd == 100000
        assert calculator.leverage_limit == 10.0

    def test_position_size_calculation(self):
        """Test position size calculation based on risk parameters."""
        calculator = RiskCalculator()

        # Test with account balance and stop loss
        position_size = calculator.calculate_position_size(
            account_balance=50000,
            entry_price=1.1000,
            stop_loss_price=1.0950,  # 50 pips risk
            risk_percent=2.0,
        )

        # Risk per trade: $50,000 * 2% = $1,000
        # Price risk: 1.1000 - 1.0950 = 0.0050
        # Position size: $1,000 / 0.0050 = $200,000 notional
        # But in forex, this represents 200,000 units
        expected_size = 200000
        assert (
            abs(position_size - expected_size) < 1000
        )  # Allow small rounding differences

    def test_risk_assessment_calculation(self):
        """Test comprehensive risk assessment calculation."""
        calculator = RiskCalculator()

        assessment = calculator.assess_trade_risk(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=Decimal("100000"),
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            account_balance=Decimal("50000"),
            current_exposure=Decimal("20000"),
            open_positions=3,
        )

        assert isinstance(assessment, RiskAssessment)
        assert assessment.symbol == "EUR/USD"
        assert assessment.position_size_usd > 0
        assert assessment.risk_amount > 0
        assert assessment.risk_percent > 0
        assert assessment.total_exposure_after_trade > 20000
        assert len(assessment.risk_factors) >= 0

    def test_risk_limit_validation(self):
        """Test risk limit validation and warnings."""
        calculator = RiskCalculator(max_risk_per_trade_percent=2.0)

        # Test acceptable risk
        is_acceptable = calculator.validate_risk_limits(
            risk_amount=500,  # $500 risk
            account_balance=50000,  # 1% risk
            current_exposure=10000,
            position_size_usd=50000,
        )
        assert is_acceptable is True

        # Test excessive risk
        is_acceptable = calculator.validate_risk_limits(
            risk_amount=2000,  # $2000 risk
            account_balance=50000,  # 4% risk (exceeds 2% limit)
            current_exposure=10000,
            position_size_usd=50000,
        )
        assert is_acceptable is False

    def test_portfolio_risk_calculation(self):
        """Test portfolio-level risk calculation."""
        calculator = RiskCalculator()

        portfolio_risk = calculator.calculate_portfolio_risk(
            [
                {"symbol": "EUR/USD", "position_size": 100000, "unrealized_pnl": -500},
                {"symbol": "GBP/USD", "position_size": 75000, "unrealized_pnl": 200},
                {"symbol": "USD/JPY", "position_size": 50000, "unrealized_pnl": -100},
            ]
        )

        assert "total_exposure" in portfolio_risk
        assert "total_pnl" in portfolio_risk
        assert "risk_concentration" in portfolio_risk
        assert portfolio_risk["total_pnl"] == -400  # -500 + 200 - 100
        assert portfolio_risk["total_exposure"] == 225000  # 100k + 75k + 50k


class TestTradeAuditLogger:
    """Test comprehensive audit trail logging functionality."""

    def test_audit_logger_initialization(self):
        """Test audit logger initialization."""
        logger = TradeAuditLogger(
            log_file_path="/tmp/manual_trades.log",
            database_connection="postgresql://user:pass@db:5432/fxml4",
            retention_days=2555,  # 7 years
        )

        assert logger.log_file_path == "/tmp/manual_trades.log"
        assert logger.database_connection == "postgresql://user:pass@db:5432/fxml4"
        assert logger.retention_days == 2555

    @pytest.mark.asyncio
    async def test_trade_entry_logging(self):
        """Test comprehensive trade entry logging."""
        logger = TradeAuditLogger()

        trade_data = {
            "trade_id": "MANUAL_001",
            "trader_id": "TRADER_123",
            "symbol": "EUR/USD",
            "side": "BUY",
            "quantity": 100000,
            "entry_price": 1.1000,
            "stop_loss": 1.0950,
            "take_profit": 1.1100,
            "rationale": "Strong bullish momentum after ECB dovish stance",
            "risk_assessment": {"risk_percent": 1.8, "position_size_usd": 110000},
            "broker_selected": "IB",
            "approval_status": "AUTO_APPROVED",
        }

        with patch.object(
            logger, "_write_to_database", new_callable=AsyncMock
        ) as mock_db:
            with patch.object(
                logger, "_write_to_file", new_callable=AsyncMock
            ) as mock_file:
                await logger.log_trade_entry(trade_data)

                mock_db.assert_called_once()
                mock_file.assert_called_once()

                # Verify logged data structure
                logged_data = mock_db.call_args[0][0]
                assert logged_data["trade_id"] == "MANUAL_001"
                assert logged_data["trader_id"] == "TRADER_123"
                assert "timestamp" in logged_data
                assert "audit_hash" in logged_data  # Immutable audit trail

    @pytest.mark.asyncio
    async def test_trade_modification_logging(self):
        """Test trade modification audit logging."""
        logger = TradeAuditLogger()

        modification_data = {
            "trade_id": "MANUAL_001",
            "trader_id": "TRADER_123",
            "modification_type": "STOP_LOSS_UPDATE",
            "old_stop_loss": 1.0950,
            "new_stop_loss": 1.0975,
            "modification_reason": "Risk management adjustment after news event",
        }

        with patch.object(
            logger, "_write_to_database", new_callable=AsyncMock
        ) as mock_db:
            await logger.log_trade_modification(modification_data)

            logged_data = mock_db.call_args[0][0]
            assert logged_data["modification_type"] == "STOP_LOSS_UPDATE"
            assert "modification_timestamp" in logged_data

    def test_audit_hash_generation(self):
        """Test cryptographic hash generation for immutable audit trail."""
        logger = TradeAuditLogger()

        trade_data = {
            "trade_id": "HASH_TEST",
            "trader_id": "TRADER_456",
            "timestamp": "2024-01-01T12:00:00Z",
        }

        hash1 = logger._generate_audit_hash(trade_data)
        hash2 = logger._generate_audit_hash(trade_data)

        # Same data should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex string

        # Different data should produce different hash
        trade_data["trade_id"] = "HASH_TEST_2"
        hash3 = logger._generate_audit_hash(trade_data)
        assert hash1 != hash3


class TestApprovalWorkflow:
    """Test approval workflow for large and high-risk trades."""

    def test_approval_workflow_initialization(self):
        """Test approval workflow initialization."""
        workflow = ApprovalWorkflow(
            auto_approval_limit_usd=50000,
            manager_approval_limit_usd=200000,
            director_approval_limit_usd=500000,
            risk_score_threshold=7.5,
        )

        assert workflow.auto_approval_limit_usd == 50000
        assert workflow.manager_approval_limit_usd == 200000
        assert workflow.director_approval_limit_usd == 500000
        assert workflow.risk_score_threshold == 7.5

    @pytest.mark.asyncio
    async def test_auto_approval_logic(self):
        """Test automatic approval for low-risk trades."""
        workflow = ApprovalWorkflow()

        trade_request = ManualTradeRequest(
            trade_id="AUTO_001",
            trader_id="TRADER_123",
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=Decimal("50000"),
            position_size_usd=55000,  # Within auto-approval limit
            risk_score=3.5,  # Low risk
        )

        approval_result = await workflow.request_approval(trade_request)

        assert approval_result.approved is True
        assert approval_result.approval_type == "AUTO_APPROVED"
        assert approval_result.approver_id == "SYSTEM"
        assert approval_result.approval_time is not None

    @pytest.mark.asyncio
    async def test_manager_approval_required(self):
        """Test manager approval requirement for medium-risk trades."""
        workflow = ApprovalWorkflow()

        trade_request = ManualTradeRequest(
            trade_id="MGR_001",
            trader_id="TRADER_123",
            symbol="GBP/USD",
            side=OrderSide.SELL,
            quantity=Decimal("150000"),
            position_size_usd=180000,  # Requires manager approval
            risk_score=6.5,
        )

        # Mock pending approval (would normally wait for human approval)
        with patch.object(
            workflow, "_check_pending_approvals", new_callable=AsyncMock
        ) as mock_check:
            mock_check.return_value = {
                "approved": False,
                "approval_type": "MANAGER_REQUIRED",
                "pending_since": datetime.utcnow(),
            }

            approval_result = await workflow.request_approval(trade_request)

            assert approval_result.approved is False
            assert approval_result.approval_type == "MANAGER_REQUIRED"
            assert approval_result.approval_time is None  # Still pending

    @pytest.mark.asyncio
    async def test_high_risk_rejection(self):
        """Test automatic rejection of extremely high-risk trades."""
        workflow = ApprovalWorkflow(risk_score_threshold=8.0)

        trade_request = ManualTradeRequest(
            trade_id="RISK_001",
            trader_id="TRADER_123",
            symbol="USD/JPY",
            side=OrderSide.BUY,
            quantity=Decimal("500000"),
            position_size_usd=650000,
            risk_score=9.2,  # Extremely high risk
        )

        approval_result = await workflow.request_approval(trade_request)

        assert approval_result.approved is False
        assert approval_result.approval_type == "AUTO_REJECTED"
        assert "risk score too high" in approval_result.rejection_reason.lower()


class TestBrokerSelector:
    """Test intelligent broker selection logic."""

    def test_broker_selector_initialization(self):
        """Test broker selector initialization."""
        selector = BrokerSelector(
            available_brokers=["IB", "FXCM"],
            default_broker="IB",
            broker_preferences={"EUR/USD": "IB", "GBP/USD": "FXCM"},
        )

        assert "IB" in selector.available_brokers
        assert "FXCM" in selector.available_brokers
        assert selector.default_broker == "IB"
        assert selector.broker_preferences["EUR/USD"] == "IB"

    def test_symbol_based_broker_selection(self):
        """Test broker selection based on symbol preferences."""
        selector = BrokerSelector(
            broker_preferences={"EUR/USD": "IB", "GBP/USD": "FXCM", "USD/JPY": "IB"}
        )

        # Test preferred broker selection
        broker = selector.select_broker("EUR/USD", position_size_usd=100000)
        assert broker == "IB"

        broker = selector.select_broker("GBP/USD", position_size_usd=100000)
        assert broker == "FXCM"

        # Test fallback to default for unknown symbol
        broker = selector.select_broker("AUD/USD", position_size_usd=100000)
        assert broker == selector.default_broker

    def test_position_size_based_selection(self):
        """Test broker selection based on position size thresholds."""
        selector = BrokerSelector(
            position_size_thresholds={
                "IB": {"min": 0, "max": 200000},
                "FXCM": {"min": 50000, "max": 500000},
            }
        )

        # Small position -> IB
        broker = selector.select_broker("EUR/USD", position_size_usd=25000)
        assert broker == "IB"

        # Large position -> FXCM
        broker = selector.select_broker("EUR/USD", position_size_usd=300000)
        assert broker == "FXCM"

    @pytest.mark.asyncio
    async def test_broker_health_check(self):
        """Test broker health check integration."""
        selector = BrokerSelector()

        # Mock broker health status
        with patch.object(
            selector, "_check_broker_health", new_callable=AsyncMock
        ) as mock_health:
            mock_health.side_effect = lambda broker: broker == "IB"  # Only IB healthy

            broker = await selector.select_healthy_broker("EUR/USD", ["IB", "FXCM"])
            assert broker == "IB"

            # Test when preferred broker is unhealthy
            broker = await selector.select_healthy_broker("GBP/USD", ["FXCM", "IB"])
            assert broker == "IB"  # Falls back to healthy broker


class TestManualTradeRequest:
    """Test manual trade request data structure and validation."""

    def test_trade_request_creation(self):
        """Test manual trade request creation and validation."""
        request = ManualTradeRequest(
            trade_id="REQ_001",
            trader_id="TRADER_123",
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=Decimal("100000"),
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            take_profit=Decimal("1.1100"),
            rationale="Technical breakout with strong momentum",
            position_size_usd=110000,
            risk_score=4.2,
        )

        assert request.trade_id == "REQ_001"
        assert request.symbol == "EUR/USD"
        assert request.quantity == Decimal("100000")
        assert request.rationale == "Technical breakout with strong momentum"
        assert request.risk_score == 4.2

    def test_trade_request_validation(self):
        """Test trade request validation logic."""
        request = ManualTradeRequest(
            trade_id="VAL_001",
            trader_id="TRADER_456",
            symbol="GBP/USD",
            side=OrderSide.SELL,
            quantity=Decimal("75000"),
            entry_price=Decimal("1.2500"),
        )

        validation_result = request.validate()

        assert validation_result.is_valid is True
        assert len(validation_result.errors) == 0

        # Test invalid request (negative quantity)
        invalid_request = ManualTradeRequest(
            trade_id="INV_001",
            trader_id="TRADER_456",
            symbol="USD/JPY",
            side=OrderSide.BUY,
            quantity=Decimal("-50000"),  # Invalid negative quantity
        )

        validation_result = invalid_request.validate()
        assert validation_result.is_valid is False
        assert len(validation_result.errors) > 0


class TestManualExecutionAdapter:
    """Test main manual execution adapter integration."""

    def test_adapter_initialization(self):
        """Test manual execution adapter initialization."""
        adapter = ManualExecutionAdapter(
            trader_id="TRADER_MAIN",
            risk_limits={
                "max_risk_per_trade": 2.0,
                "max_portfolio_risk": 6.0,
                "max_position_size": 200000,
            },
            audit_config={
                "log_file": "/tmp/manual_audit.log",
                "database_url": "postgresql://localhost/fxml4",
            },
        )

        assert adapter.trader_id == "TRADER_MAIN"
        assert adapter.risk_calculator is not None
        assert adapter.audit_logger is not None
        assert adapter.approval_workflow is not None
        assert adapter.broker_selector is not None

    @pytest.mark.asyncio
    async def test_manual_trade_workflow(self):
        """Test complete manual trade workflow."""
        adapter = ManualExecutionAdapter()

        # Create trade request
        trade_request = ManualTradeRequest(
            trade_id="WORKFLOW_001",
            trader_id="TRADER_MAIN",
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=Decimal("100000"),
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            rationale="Strong technical setup with news catalyst",
        )

        # Mock broker adapters
        mock_ib_adapter = AsyncMock()
        mock_fxcm_adapter = AsyncMock()

        adapter.broker_adapters = {"IB": mock_ib_adapter, "FXCM": mock_fxcm_adapter}

        # Mock successful order execution
        mock_ib_adapter.execute_order.return_value = {
            "order_id": "IB_12345",
            "status": "FILLED",
            "fill_price": 1.1000,
            "commission": 2.50,
        }

        # Execute trade
        execution_result = await adapter.execute_manual_trade(trade_request)

        assert execution_result.success is True
        assert execution_result.execution_id is not None
        assert execution_result.broker_used == "IB"  # Default broker
        assert execution_result.order_id == "IB_12345"

    @pytest.mark.asyncio
    async def test_risk_rejection_workflow(self):
        """Test risk rejection workflow."""
        adapter = ManualExecutionAdapter()

        # High-risk trade request
        high_risk_request = ManualTradeRequest(
            trade_id="RISK_REJECT_001",
            trader_id="TRADER_RISK",
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=Decimal("1000000"),  # Very large position
            position_size_usd=1100000,
            risk_score=9.5,  # Extremely high risk
        )

        with pytest.raises(ManualExecutionError, match="Risk limits exceeded"):
            await adapter.execute_manual_trade(high_risk_request)

    @pytest.mark.asyncio
    async def test_approval_required_workflow(self):
        """Test approval required workflow."""
        adapter = ManualExecutionAdapter()

        # Trade requiring approval
        approval_request = ManualTradeRequest(
            trade_id="APPROVAL_001",
            trader_id="TRADER_APPROVAL",
            symbol="GBP/USD",
            side=OrderSide.SELL,
            quantity=Decimal("300000"),
            position_size_usd=375000,  # Requires manager approval
        )

        with pytest.raises(ManualApprovalRequired) as exc_info:
            await adapter.execute_manual_trade(approval_request)

        assert "manager approval required" in str(exc_info.value).lower()
        assert exc_info.value.approval_type == "MANAGER_REQUIRED"

    @pytest.mark.asyncio
    async def test_audit_trail_integration(self):
        """Test comprehensive audit trail integration."""
        adapter = ManualExecutionAdapter()

        trade_request = ManualTradeRequest(
            trade_id="AUDIT_001",
            trader_id="TRADER_AUDIT",
            symbol="USD/JPY",
            side=OrderSide.BUY,
            quantity=Decimal("50000"),
            rationale="Momentum breakout with strong fundamentals",
        )

        # Mock broker execution
        mock_adapter = AsyncMock()
        mock_adapter.execute_order.return_value = {
            "order_id": "AUDIT_ORDER_123",
            "status": "FILLED",
            "fill_price": 110.50,
        }
        adapter.broker_adapters = {"IB": mock_adapter}

        # Mock audit logging
        with patch.object(
            adapter.audit_logger, "log_trade_entry", new_callable=AsyncMock
        ) as mock_log:
            execution_result = await adapter.execute_manual_trade(trade_request)

            # Verify audit logging was called
            mock_log.assert_called_once()
            audit_data = mock_log.call_args[0][0]
            assert audit_data["trade_id"] == "AUDIT_001"
            assert audit_data["trader_id"] == "TRADER_AUDIT"
            assert (
                audit_data["rationale"] == "Momentum breakout with strong fundamentals"
            )

    @pytest.mark.asyncio
    async def test_multi_broker_fallback(self):
        """Test multi-broker fallback logic."""
        adapter = ManualExecutionAdapter()

        # Mock brokers with IB failing, FXCM succeeding
        mock_ib_adapter = AsyncMock()
        mock_fxcm_adapter = AsyncMock()

        mock_ib_adapter.execute_order.side_effect = Exception("IB connection failed")
        mock_fxcm_adapter.execute_order.return_value = {
            "order_id": "FXCM_67890",
            "status": "FILLED",
            "fill_price": 1.2500,
        }

        adapter.broker_adapters = {"IB": mock_ib_adapter, "FXCM": mock_fxcm_adapter}

        trade_request = ManualTradeRequest(
            trade_id="FALLBACK_001",
            trader_id="TRADER_FALLBACK",
            symbol="GBP/USD",
            side=OrderSide.SELL,
            quantity=Decimal("75000"),
        )

        execution_result = await adapter.execute_manual_trade(trade_request)

        # Should have fallen back to FXCM
        assert execution_result.success is True
        assert execution_result.broker_used == "FXCM"
        assert execution_result.order_id == "FXCM_67890"

    def test_real_time_pnl_tracking(self):
        """Test real-time P&L tracking functionality."""
        adapter = ManualExecutionAdapter()

        # Add mock positions
        adapter.active_positions = {
            "POS_001": {
                "symbol": "EUR/USD",
                "side": "BUY",
                "quantity": 100000,
                "entry_price": 1.1000,
                "current_price": 1.1050,
                "unrealized_pnl": 500.0,
            },
            "POS_002": {
                "symbol": "GBP/USD",
                "side": "SELL",
                "quantity": 75000,
                "entry_price": 1.2500,
                "current_price": 1.2475,
                "unrealized_pnl": 187.5,
            },
        }

        pnl_summary = adapter.get_real_time_pnl()

        assert pnl_summary["total_unrealized_pnl"] == 687.5
        assert pnl_summary["position_count"] == 2
        assert len(pnl_summary["positions"]) == 2
        assert pnl_summary["total_exposure"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
