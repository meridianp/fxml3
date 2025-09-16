"""Simplified test suite for Manual Execution Adapter.

This test suite validates the core manual execution adapter functionality
with focus on the actual implemented classes, using proper test configurations.
"""

import tempfile
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from fxml4.brokers.adapters.manual_execution_adapter import (
    ApprovalType,
    ApprovalWorkflow,
    BrokerSelector,
    ManualApprovalRequired,
    ManualExecutionAdapter,
    ManualExecutionError,
    ManualTradeRequest,
    RiskAssessment,
    RiskCalculator,
    TradeAuditLogger,
)
from fxml4.messaging.messages import OrderSide, OrderType


class TestRiskCalculator:
    """Test risk calculation functionality."""

    def test_risk_calculator_initialization(self):
        """Test risk calculator initialization."""
        calculator = RiskCalculator(
            max_risk_per_trade_percent=2.5,
            max_portfolio_risk_percent=8.0,
            max_position_size_usd=150000,
        )

        assert calculator.max_risk_per_trade_percent == 2.5
        assert calculator.max_portfolio_risk_percent == 8.0
        assert calculator.max_position_size_usd == 150000

    def test_position_size_calculation_basic(self):
        """Test basic position size calculation."""
        calculator = RiskCalculator()

        # Simple calculation test
        position_size = calculator.calculate_position_size(
            account_balance=100000,
            entry_price=1.1000,
            stop_loss_price=1.0900,  # 100 pips risk
            risk_percent=1.0,
        )

        # Risk: $100,000 * 1% = $1,000
        # Price difference: 1.1000 - 1.0900 = 0.0100
        # Position size: $1,000 / 0.0100 = 100,000
        assert position_size == 100000

    def test_risk_assessment_creation(self):
        """Test risk assessment data structure."""
        calculator = RiskCalculator()

        assessment = calculator.assess_trade_risk(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=Decimal("50000"),
            entry_price=Decimal("1.1000"),
            account_balance=Decimal("100000"),
        )

        assert isinstance(assessment, RiskAssessment)
        assert assessment.symbol == "EUR/USD"
        assert assessment.side == OrderSide.BUY
        assert assessment.quantity == Decimal("50000")
        assert assessment.position_size_usd == Decimal("55000")  # 50k * 1.1

    def test_risk_limits_validation(self):
        """Test risk limit validation logic."""
        calculator = RiskCalculator(
            max_risk_per_trade_percent=2.0,
            max_portfolio_risk_percent=80.0,  # Higher limit for test validation
        )

        # Low risk should pass
        valid = calculator.validate_risk_limits(
            risk_amount=1000,  # $1,000 risk
            account_balance=100000,  # 1% risk
            current_exposure=20000,
            position_size_usd=50000,
        )
        assert valid is True

        # High risk should fail
        invalid = calculator.validate_risk_limits(
            risk_amount=5000,  # $5,000 risk
            account_balance=100000,  # 5% risk (exceeds 2%)
            current_exposure=20000,
            position_size_usd=50000,
        )
        assert invalid is False


class TestTradeAuditLogger:
    """Test audit logging with temporary files."""

    def test_audit_logger_initialization(self):
        """Test audit logger with temporary file."""
        with tempfile.NamedTemporaryFile() as tmp:
            logger = TradeAuditLogger(log_file_path=tmp.name, retention_days=365)

            assert logger.log_file_path == tmp.name
            assert logger.retention_days == 365

    def test_audit_hash_generation(self):
        """Test cryptographic hash generation."""
        with tempfile.NamedTemporaryFile() as tmp:
            logger = TradeAuditLogger(log_file_path=tmp.name)

            test_data = {
                "trade_id": "TEST_001",
                "trader_id": "TRADER_123",
                "amount": 100000,
            }

            # Same data should produce same hash
            hash1 = logger._generate_audit_hash(test_data)
            hash2 = logger._generate_audit_hash(test_data)
            assert hash1 == hash2
            assert len(hash1) == 64  # SHA-256 produces 64-char hex string

            # Different data should produce different hash
            test_data["trade_id"] = "TEST_002"
            hash3 = logger._generate_audit_hash(test_data)
            assert hash1 != hash3

    @pytest.mark.asyncio
    async def test_trade_entry_logging(self):
        """Test trade entry logging functionality."""
        with tempfile.NamedTemporaryFile() as tmp:
            logger = TradeAuditLogger(log_file_path=tmp.name)

            trade_data = {
                "trade_id": "LOG_001",
                "trader_id": "TRADER_456",
                "symbol": "EUR/USD",
                "quantity": 100000,
            }

            # Mock database write to avoid actual DB operations
            with patch.object(logger, "_write_to_database", new_callable=AsyncMock):
                audit_hash = await logger.log_trade_entry(trade_data)

                assert isinstance(audit_hash, str)
                assert len(audit_hash) == 64

                # Verify file was written to
                tmp.seek(0)
                content = tmp.read().decode()
                assert "LOG_001" in content
                assert "TRADER_456" in content


class TestApprovalWorkflow:
    """Test approval workflow logic."""

    def test_approval_workflow_initialization(self):
        """Test approval workflow setup."""
        workflow = ApprovalWorkflow(
            auto_approval_limit_usd=25000, manager_approval_limit_usd=100000
        )

        assert workflow.auto_approval_limit_usd == 25000
        assert workflow.manager_approval_limit_usd == 100000

    @pytest.mark.asyncio
    async def test_auto_approval_small_trade(self):
        """Test auto-approval for small trades."""
        workflow = ApprovalWorkflow(auto_approval_limit_usd=50000)

        small_trade = ManualTradeRequest(
            trader_id="TRADER_AUTO",
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=Decimal("30000"),
            position_size_usd=Decimal("35000"),  # Within limit
            risk_score=3.0,  # Low risk
        )

        result = await workflow.request_approval(small_trade)

        assert result.approved is True
        assert result.approval_type == ApprovalType.AUTO_APPROVED.value
        assert result.approver_id == "SYSTEM"

    @pytest.mark.asyncio
    async def test_manager_approval_required(self):
        """Test manager approval requirement."""
        workflow = ApprovalWorkflow(
            auto_approval_limit_usd=50000, manager_approval_limit_usd=200000
        )

        large_trade = ManualTradeRequest(
            trader_id="TRADER_MGR",
            symbol="GBP/USD",
            side=OrderSide.SELL,
            quantity=Decimal("100000"),
            position_size_usd=Decimal("125000"),  # Requires manager approval
            risk_score=4.5,
        )

        result = await workflow.request_approval(large_trade)

        assert result.approved is False  # Pending approval
        assert result.approval_type == ApprovalType.MANAGER_REQUIRED.value


class TestBrokerSelector:
    """Test broker selection logic."""

    def test_broker_selector_initialization(self):
        """Test broker selector setup."""
        selector = BrokerSelector(
            available_brokers=["IB", "FXCM", "MANUAL"],
            default_broker="IB",
            broker_preferences={"EUR/USD": "IB", "GBP/USD": "FXCM"},
        )

        assert "IB" in selector.available_brokers
        assert "FXCM" in selector.available_brokers
        assert "MANUAL" in selector.available_brokers
        assert selector.default_broker == "IB"

    def test_symbol_preference_selection(self):
        """Test broker selection based on symbol preferences."""
        selector = BrokerSelector(
            broker_preferences={"EUR/USD": "IB", "GBP/USD": "FXCM"}
        )

        # Test preferred selections
        broker = selector.select_broker("EUR/USD", 100000)
        assert broker == "IB"

        broker = selector.select_broker("GBP/USD", 100000)
        assert broker == "FXCM"

        # Test fallback for unknown symbol
        broker = selector.select_broker("USD/JPY", 100000)
        assert broker == selector.default_broker

    @pytest.mark.asyncio
    async def test_healthy_broker_selection(self):
        """Test broker health-based selection."""
        selector = BrokerSelector(available_brokers=["IB", "FXCM"])

        # Mock health check: only IB is healthy
        with patch.object(
            selector, "_check_broker_health", new_callable=AsyncMock
        ) as mock_health:
            mock_health.side_effect = lambda b: b == "IB"

            broker = await selector.select_healthy_broker("EUR/USD", ["FXCM", "IB"])
            assert broker == "IB"  # Should select healthy broker


class TestManualTradeRequest:
    """Test manual trade request validation."""

    def test_trade_request_creation(self):
        """Test trade request creation."""
        request = ManualTradeRequest(
            trader_id="TRADER_REQ",
            symbol="USD/JPY",
            side=OrderSide.BUY,
            quantity=Decimal("75000"),
            entry_price=Decimal("110.50"),
            rationale="Technical breakout pattern",
        )

        assert request.trader_id == "TRADER_REQ"
        assert request.symbol == "USD/JPY"
        assert request.side == OrderSide.BUY
        assert request.quantity == Decimal("75000")
        assert request.entry_price == Decimal("110.50")

    def test_trade_request_validation_valid(self):
        """Test valid trade request validation."""
        request = ManualTradeRequest(
            trader_id="TRADER_VALID",
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=Decimal("50000"),
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),  # Valid stop loss
            take_profit=Decimal("1.1100"),  # Valid take profit
        )

        validation = request.validate()
        assert validation.is_valid is True
        assert len(validation.errors) == 0

    def test_trade_request_validation_errors(self):
        """Test trade request validation with errors."""
        invalid_request = ManualTradeRequest(
            trader_id="TRADER_INVALID",
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=Decimal("-1000"),  # Invalid negative quantity
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.1050"),  # Invalid stop loss (above entry for BUY)
        )

        validation = invalid_request.validate()
        assert validation.is_valid is False
        assert len(validation.errors) >= 2  # Should have multiple errors


class TestManualExecutionAdapter:
    """Test main manual execution adapter."""

    def test_adapter_initialization_with_temp_config(self):
        """Test adapter initialization with temporary configurations."""
        with tempfile.NamedTemporaryFile() as tmp:
            audit_config = {"log_file": tmp.name}

            adapter = ManualExecutionAdapter(
                trader_id="TRADER_MAIN",
                risk_limits={"max_risk_per_trade": 1.5},
                audit_config=audit_config,
                approval_config={"auto_approval_limit": 75000},
            )

            assert adapter.trader_id == "TRADER_MAIN"
            assert adapter.risk_calculator is not None
            assert adapter.audit_logger is not None
            assert adapter.approval_workflow is not None
            assert adapter.broker_selector is not None

    def test_broker_adapter_management(self):
        """Test broker adapter management."""
        with tempfile.NamedTemporaryFile() as tmp:
            audit_config = {"log_file": tmp.name}
            adapter = ManualExecutionAdapter(audit_config=audit_config)

            # Add mock broker adapters
            mock_ib = Mock()
            mock_fxcm = Mock()

            adapter.add_broker_adapter("IB", mock_ib)
            adapter.add_broker_adapter("FXCM", mock_fxcm)

            assert "IB" in adapter.broker_adapters
            assert "FXCM" in adapter.broker_adapters
            assert adapter.broker_adapters["IB"] == mock_ib

    @pytest.mark.asyncio
    async def test_trade_validation_rejection(self):
        """Test trade rejection for invalid requests."""
        with tempfile.NamedTemporaryFile() as tmp:
            audit_config = {"log_file": tmp.name}
            adapter = ManualExecutionAdapter(audit_config=audit_config)

            # Invalid trade request
            invalid_request = ManualTradeRequest(
                trader_id="TRADER_INVALID",
                symbol="EUR/USD",
                side=OrderSide.BUY,
                quantity=Decimal("-50000"),  # Negative quantity
            )

            with pytest.raises(ManualExecutionError, match="Invalid trade request"):
                await adapter.execute_manual_trade(invalid_request)

    @pytest.mark.asyncio
    async def test_high_risk_rejection(self):
        """Test high risk trade rejection."""
        with tempfile.NamedTemporaryFile() as tmp:
            audit_config = {"log_file": tmp.name}
            adapter = ManualExecutionAdapter(
                audit_config=audit_config,
                risk_limits={"max_position_size": 50000},  # Low limit for testing
            )

            high_risk_request = ManualTradeRequest(
                trader_id="TRADER_RISK",
                symbol="EUR/USD",
                side=OrderSide.BUY,
                quantity=Decimal("200000"),  # Large position
                entry_price=Decimal("1.1000"),
            )

            with pytest.raises(ManualExecutionError, match="Risk limits exceeded"):
                await adapter.execute_manual_trade(high_risk_request)

    def test_position_tracking(self):
        """Test position tracking functionality."""
        with tempfile.NamedTemporaryFile() as tmp:
            audit_config = {"log_file": tmp.name}
            adapter = ManualExecutionAdapter(audit_config=audit_config)

            # Add mock positions
            adapter.active_positions["POS_001"] = {
                "symbol": "EUR/USD",
                "side": "BUY",
                "quantity": 100000,
                "entry_price": 1.1000,
                "current_price": 1.1050,
                "unrealized_pnl": 500.0,
            }

            adapter.active_positions["POS_002"] = {
                "symbol": "GBP/USD",
                "side": "SELL",
                "quantity": 75000,
                "entry_price": 1.2500,
                "current_price": 1.2475,
                "unrealized_pnl": 187.5,
            }

            pnl_summary = adapter.get_real_time_pnl()

            assert pnl_summary["position_count"] == 2
            assert pnl_summary["total_unrealized_pnl"] == 687.5
            assert len(pnl_summary["positions"]) == 2

    def test_performance_metrics(self):
        """Test performance metrics tracking."""
        with tempfile.NamedTemporaryFile() as tmp:
            audit_config = {"log_file": tmp.name}
            adapter = ManualExecutionAdapter(audit_config=audit_config)

            # Simulate some executions
            adapter.execution_count = 10
            adapter.successful_executions = 8
            adapter.total_commission = Decimal("25.50")

            pnl_summary = adapter.get_real_time_pnl()
            metrics = pnl_summary["performance_metrics"]

            assert metrics["total_executions"] == 10
            assert metrics["successful_executions"] == 8
            assert metrics["success_rate"] == 80.0
            assert metrics["total_commission"] == 25.50

    def test_position_summary(self):
        """Test position summary functionality."""
        with tempfile.NamedTemporaryFile() as tmp:
            audit_config = {"log_file": tmp.name}
            adapter = ManualExecutionAdapter(audit_config=audit_config)

            # Add test position
            adapter.active_positions["TEST_POS"] = {
                "symbol": "USD/JPY",
                "quantity": 50000,
                "entry_price": 110.50,
            }

            summary = adapter.get_position_summary()

            assert summary["active_positions"] == 1
            assert len(summary["positions"]) == 1
            assert summary["positions"][0]["symbol"] == "USD/JPY"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
