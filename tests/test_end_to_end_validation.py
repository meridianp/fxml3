"""
Tests for FXML4 End-to-End Trading Workflow Validation

This test suite validates the end-to-end validation system itself:
- Component initialization and health checks
- Workflow stage tracking and SLA compliance
- Performance measurement and reporting
- Error handling and recovery
- Integration with live trading components
"""

import asyncio

# Direct import to avoid __init__.py issues
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch

import pytest

sys.path.insert(0, "/home/cnross/code/fxml4")

from fxml4.core.exceptions import ValidationError as CoreValidationError
from fxml4.live_trading.end_to_end_validator import (
    EndToEndValidator,
    StageResult,
    WorkflowStage,
    WorkflowValidationResult,
)


@pytest.fixture
async def validator_config():
    """Test configuration for validator"""
    return {
        "orchestrator": {"test_mode": True},
        "ml": {"mock_signals": True},
        "risk_management": {"test_mode": True},
        "ib_adapter": {"paper_trading": True, "test_mode": True},
        "market_data": {"test_mode": True},
        "performance": {"test_mode": True},
    }


@pytest.fixture
async def mock_validator(validator_config):
    """Create validator with mocked components"""
    validator = EndToEndValidator(validator_config)

    # Mock all components
    validator.orchestrator = AsyncMock()
    validator.signal_generator = AsyncMock()
    validator.risk_manager = AsyncMock()
    validator.ib_adapter = AsyncMock()
    validator.market_data_feed = AsyncMock()
    validator.performance_tracker = AsyncMock()

    # Configure mock health checks
    validator.orchestrator.initialize = AsyncMock()
    validator.signal_generator.initialize = AsyncMock()
    validator.risk_manager.initialize = AsyncMock()
    validator.ib_adapter.initialize = AsyncMock()
    validator.market_data_feed.initialize = AsyncMock()
    validator.performance_tracker.initialize = AsyncMock()

    validator.ib_adapter.check_connection = AsyncMock()
    validator.market_data_feed.check_connection = AsyncMock()
    validator.signal_generator.health_check = AsyncMock()
    validator.risk_manager.health_check = AsyncMock()
    validator.performance_tracker.health_check = AsyncMock()

    return validator


@pytest.fixture
def sample_market_data():
    """Sample market data for testing"""
    base_time = datetime.utcnow()
    market_data = []

    for i in range(100):
        timestamp = base_time - timedelta(minutes=100 - i)
        price = 1.3000 + (i * 0.0001)  # Trending upward
        market_data.append(
            {
                "timestamp": timestamp.isoformat(),
                "open": price,
                "high": price + 0.0005,
                "low": price - 0.0005,
                "close": price + 0.0002,
                "volume": 1000 + (i * 10),
            }
        )

    return market_data


class TestEndToEndValidator:
    """Test suite for EndToEndValidator"""

    @pytest.mark.asyncio
    async def test_validator_initialization(self, validator_config):
        """Test validator initialization"""
        validator = EndToEndValidator(validator_config)

        # Check initial state
        assert validator.config == validator_config
        assert len(validator.validation_results) == 0
        assert validator.sla_targets["total_workflow_seconds"] == 30.0
        assert validator.orchestrator is None

    @pytest.mark.asyncio
    async def test_component_initialization_success(self, mock_validator):
        """Test successful component initialization"""
        await mock_validator.initialize_components()

        # Verify all components were initialized
        mock_validator.orchestrator.initialize.assert_called_once()
        mock_validator.signal_generator.initialize.assert_called_once()
        mock_validator.risk_manager.initialize.assert_called_once()
        mock_validator.ib_adapter.initialize.assert_called_once()
        mock_validator.market_data_feed.initialize.assert_called_once()
        mock_validator.performance_tracker.initialize.assert_called_once()

        # Verify health checks were performed
        mock_validator.ib_adapter.check_connection.assert_called_once()
        mock_validator.market_data_feed.check_connection.assert_called_once()
        mock_validator.signal_generator.health_check.assert_called_once()
        mock_validator.risk_manager.health_check.assert_called_once()
        mock_validator.performance_tracker.health_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_component_initialization_failure(self, mock_validator):
        """Test component initialization failure handling"""
        # Make one component fail initialization
        mock_validator.ib_adapter.initialize.side_effect = Exception(
            "IB connection failed"
        )

        with pytest.raises(ValidationError) as exc_info:
            await mock_validator.initialize_components()

        assert "Component initialization failed" in str(exc_info.value)
        assert "IB connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_health_check_failure(self, mock_validator):
        """Test health check failure handling"""
        # Make health check fail
        mock_validator.ib_adapter.check_connection.side_effect = Exception(
            "IB health check failed"
        )

        with pytest.raises(ValidationError) as exc_info:
            await mock_validator.initialize_components()

        assert "Interactive Brokers health check failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_stage_tracking_context_manager(self, mock_validator):
        """Test stage tracking context manager"""
        # Test successful stage
        async with mock_validator._track_stage(
            WorkflowStage.MARKET_DATA_INGESTION
        ) as stage:
            assert stage.stage == WorkflowStage.MARKET_DATA_INGESTION
            assert stage.start_time > 0
            assert not stage.success  # Not yet completed
            await asyncio.sleep(0.01)  # Small delay

        # After context manager
        assert stage.success is True
        assert stage.end_time > stage.start_time
        assert stage.duration_ms > 0
        assert stage.error_message is None

    @pytest.mark.asyncio
    async def test_stage_tracking_with_exception(self, mock_validator):
        """Test stage tracking with exception"""
        with pytest.raises(ValueError):
            async with mock_validator._track_stage(
                WorkflowStage.ML_SIGNAL_GENERATION
            ) as stage:
                raise ValueError("Test error")

        # Verify error was captured
        assert stage.success is False
        assert stage.error_message == "Test error"
        assert stage.duration_ms > 0

    @pytest.mark.asyncio
    async def test_data_quality_assessment(self, mock_validator, sample_market_data):
        """Test market data quality assessment"""
        # Test with good data
        quality_score = await mock_validator._assess_data_quality(sample_market_data)
        assert quality_score >= 90.0

        # Test with missing data
        bad_data = [{"open": 1.3000}]  # Missing required fields
        quality_score = await mock_validator._assess_data_quality(bad_data)
        assert quality_score < 50.0

        # Test with empty data
        quality_score = await mock_validator._assess_data_quality([])
        assert quality_score == 0.0

    @pytest.mark.asyncio
    async def test_ml_features_preparation(self, mock_validator, sample_market_data):
        """Test ML features preparation"""
        features = await mock_validator._prepare_ml_features(sample_market_data)

        # Verify required features
        required_features = [
            "price",
            "sma_10",
            "sma_20",
            "volatility",
            "rsi",
            "volume_avg",
            "high_low_ratio",
        ]
        for feature in required_features:
            assert feature in features
            assert isinstance(features[feature], (int, float))

        # Test with insufficient data
        short_data = sample_market_data[:5]
        features = await mock_validator._prepare_ml_features(short_data)
        assert "price" in features
        assert features["rsi"] == 50.0  # Default neutral RSI

    @pytest.mark.asyncio
    async def test_rsi_calculation(self, mock_validator):
        """Test RSI calculation"""
        # Test with trending up data
        closes_up = [
            1.0,
            1.1,
            1.2,
            1.3,
            1.4,
            1.5,
            1.6,
            1.7,
            1.8,
            1.9,
            2.0,
            2.1,
            2.2,
            2.3,
            2.4,
            2.5,
        ]
        rsi_up = await mock_validator._calculate_rsi(closes_up)
        assert rsi_up > 70  # Overbought

        # Test with trending down data
        closes_down = list(reversed(closes_up))
        rsi_down = await mock_validator._calculate_rsi(closes_down)
        assert rsi_down < 30  # Oversold

        # Test with insufficient data
        short_closes = [1.0, 1.1, 1.2]
        rsi_neutral = await mock_validator._calculate_rsi(short_closes)
        assert rsi_neutral == 50.0  # Default neutral

    @pytest.mark.asyncio
    async def test_single_workflow_validation_success(
        self, mock_validator, sample_market_data
    ):
        """Test successful single workflow validation"""
        # Configure mocks for successful workflow
        mock_validator.market_data_feed.get_real_time_data.return_value = (
            sample_market_data
        )

        # Mock signal
        mock_signal = Mock()
        mock_signal.strength = 0.8
        mock_signal.direction = "BUY"
        mock_signal.confidence = 0.9
        mock_signal.entry_price = 1.3000
        mock_validator.signal_generator.generate_signal.return_value = mock_signal

        # Mock risk assessment
        mock_risk = Mock()
        mock_risk.risk_score = 0.3
        mock_risk.recommended_size = 10000
        mock_risk.approved = True
        mock_risk.risk_factors = []
        mock_validator.risk_manager.assess_trade_risk.return_value = mock_risk

        # Mock broker execution
        mock_execution = Mock()
        mock_execution.fill_price = 1.3005
        mock_execution.execution_time = datetime.utcnow()
        mock_execution.status = "FILLED"
        mock_execution.execution_id = "test_exec_001"
        mock_validator.ib_adapter.execute_paper_order.return_value = mock_execution
        mock_validator.ib_adapter.get_positions.return_value = []
        mock_validator.ib_adapter.get_account_info.return_value = {"balance": 10000}

        # Mock position tracking
        mock_position = Mock()
        mock_position.position_id = "test_pos_001"
        mock_position.unrealized_pnl = 50.0
        mock_position.size = 10000
        mock_position.entry_price = 1.3005
        mock_validator.performance_tracker.update_position.return_value = mock_position

        # Run validation
        result = await mock_validator.validate_single_workflow("GBPUSD")

        # Verify results
        assert isinstance(result, WorkflowValidationResult)
        assert result.symbol == "GBPUSD"
        assert len(result.stage_results) == 6  # All stages completed
        assert all(stage.success for stage in result.stage_results)
        assert result.total_duration_seconds > 0

        # Verify all stages were executed
        executed_stages = [stage.stage for stage in result.stage_results]
        expected_stages = [
            WorkflowStage.MARKET_DATA_INGESTION,
            WorkflowStage.ML_SIGNAL_GENERATION,
            WorkflowStage.RISK_CHECK,
            WorkflowStage.ORDER_CREATION,
            WorkflowStage.BROKER_EXECUTION,
            WorkflowStage.POSITION_TRACKING,
        ]
        for stage in expected_stages:
            assert stage in executed_stages

    @pytest.mark.asyncio
    async def test_single_workflow_validation_risk_rejection(
        self, mock_validator, sample_market_data
    ):
        """Test workflow with risk rejection"""
        # Configure mocks
        mock_validator.market_data_feed.get_real_time_data.return_value = (
            sample_market_data
        )

        mock_signal = Mock()
        mock_signal.strength = 0.8
        mock_validator.signal_generator.generate_signal.return_value = mock_signal

        # Mock risk rejection
        mock_risk = Mock()
        mock_risk.approved = False
        mock_risk.risk_factors = ["High volatility", "Excessive position size"]
        mock_validator.risk_manager.assess_trade_risk.return_value = mock_risk

        # Run validation - should fail at risk check
        with pytest.raises(ValidationError) as exc_info:
            await mock_validator.validate_single_workflow("GBPUSD")

        assert "Risk check failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_sla_compliance_checking(self, mock_validator, sample_market_data):
        """Test SLA compliance checking"""
        # Configure for fast execution (should pass SLA)
        mock_validator.market_data_feed.get_real_time_data.return_value = (
            sample_market_data
        )

        mock_signal = Mock()
        mock_signal.strength = 0.8
        mock_validator.signal_generator.generate_signal.return_value = mock_signal

        mock_risk = Mock()
        mock_risk.approved = True
        mock_risk.recommended_size = 10000
        mock_validator.risk_manager.assess_trade_risk.return_value = mock_risk

        mock_execution = Mock()
        mock_execution.fill_price = 1.3005
        mock_execution.status = "FILLED"
        mock_validator.ib_adapter.execute_paper_order.return_value = mock_execution
        mock_validator.ib_adapter.get_positions.return_value = []
        mock_validator.ib_adapter.get_account_info.return_value = {"balance": 10000}

        mock_position = Mock()
        mock_position.position_id = "test_pos_001"
        mock_validator.performance_tracker.update_position.return_value = mock_position

        # Run validation
        result = await mock_validator.validate_single_workflow("GBPUSD")

        # Should be compliant (execution is fast in test)
        assert result.sla_compliant
        assert result.sla_margin_seconds > 0

    @pytest.mark.asyncio
    async def test_multiple_workflows_validation(
        self, mock_validator, sample_market_data
    ):
        """Test multiple workflows validation"""
        # Configure mocks for successful workflows
        mock_validator.market_data_feed.get_real_time_data.return_value = (
            sample_market_data
        )

        mock_signal = Mock()
        mock_signal.strength = 0.8
        mock_validator.signal_generator.generate_signal.return_value = mock_signal

        mock_risk = Mock()
        mock_risk.approved = True
        mock_risk.recommended_size = 10000
        mock_validator.risk_manager.assess_trade_risk.return_value = mock_risk

        mock_execution = Mock()
        mock_execution.fill_price = 1.3005
        mock_execution.status = "FILLED"
        mock_validator.ib_adapter.execute_paper_order.return_value = mock_execution
        mock_validator.ib_adapter.get_positions.return_value = []
        mock_validator.ib_adapter.get_account_info.return_value = {"balance": 10000}

        mock_position = Mock()
        mock_position.position_id = "test_pos_001"
        mock_validator.performance_tracker.update_position.return_value = mock_position

        # Run multiple validations
        results = await mock_validator.validate_multiple_workflows(
            count=3, symbol="GBPUSD"
        )

        # Verify results structure
        assert "validation_summary" in results
        assert "performance_metrics" in results
        assert "stage_performance" in results
        assert "quality_analysis" in results

        # Verify validation summary
        summary = results["validation_summary"]
        assert summary["total_workflows"] == 3
        assert summary["sla_compliance_rate"] >= 0

    @pytest.mark.asyncio
    async def test_performance_metrics_calculation(self, mock_validator):
        """Test performance metrics calculation"""
        # Create mock workflow result
        result = WorkflowValidationResult(
            workflow_id="test_001",
            symbol="GBPUSD",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow() + timedelta(seconds=5),
            total_duration_ms=5000,
            sla_compliant=True,
        )

        # Add stage results
        stage_result = StageResult(
            stage=WorkflowStage.MARKET_DATA_INGESTION,
            start_time=time.perf_counter(),
            end_time=time.perf_counter() + 0.5,
            duration_ms=500,
            success=True,
        )
        result.stage_results.append(stage_result)

        # Calculate metrics
        metrics = await mock_validator._calculate_workflow_metrics(result)

        # Verify metrics
        assert "total_duration_seconds" in metrics
        assert "sla_margin_seconds" in metrics
        assert "stage_count" in metrics
        assert "success_rate" in metrics
        assert f"{WorkflowStage.MARKET_DATA_INGESTION.value}_duration_ms" in metrics

    @pytest.mark.asyncio
    async def test_validation_report_generation(self, mock_validator):
        """Test validation report generation"""
        # Add some mock results
        result1 = WorkflowValidationResult(
            workflow_id="test_001",
            symbol="GBPUSD",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow() + timedelta(seconds=5),
            total_duration_ms=5000,
            sla_compliant=True,
        )

        result2 = WorkflowValidationResult(
            workflow_id="test_002",
            symbol="GBPUSD",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow() + timedelta(seconds=35),
            total_duration_ms=35000,
            sla_compliant=False,
        )

        mock_validator.validation_results = [result1, result2]

        # Generate report
        report = await mock_validator.generate_validation_report()

        # Verify report content
        assert "FXML4 END-TO-END TRADING WORKFLOW VALIDATION REPORT" in report
        assert "SLA COMPLIANCE SUMMARY" in report
        assert "PERFORMANCE STATISTICS" in report
        assert "RECENT VALIDATION RESULTS" in report
        assert "2" in report  # Total workflows
        assert "test_001" in report
        assert "test_002" in report

    @pytest.mark.asyncio
    async def test_cleanup(self, mock_validator):
        """Test cleanup functionality"""
        await mock_validator.cleanup()

        # Verify cleanup was called on components
        mock_validator.orchestrator.shutdown.assert_called_once()
        mock_validator.ib_adapter.disconnect.assert_called_once()
        mock_validator.market_data_feed.disconnect.assert_called_once()


@pytest.mark.integration
class TestEndToEndValidatorIntegration:
    """Integration tests for end-to-end validator"""

    @pytest.mark.asyncio
    async def test_validator_with_real_components_mock(self, validator_config):
        """Test validator with more realistic component mocking"""
        validator = EndToEndValidator(validator_config)

        # Mock components with more realistic behavior
        with (
            patch(
                "fxml4.live_trading.orchestrator.LiveTradingOrchestrator"
            ) as mock_orchestrator_class,
            patch(
                "fxml4.ml.models.signal_generator.SignalGenerator"
            ) as mock_signal_class,
            patch("fxml4.risk_management.risk_manager.RiskManager") as mock_risk_class,
            patch("fxml4.brokers.adapters.ib_adapter.IBAdapter") as mock_ib_class,
            patch(
                "fxml4.data_engineering.data_feeds.market_data.MarketDataFeed"
            ) as mock_data_class,
            patch(
                "fxml4.live_trading.performance.LivePerformanceTracker"
            ) as mock_perf_class,
        ):

            # Configure mock instances
            mock_orchestrator = AsyncMock()
            mock_orchestrator_class.return_value = mock_orchestrator

            # Initialize validator
            await validator.initialize_components()

            # Verify components were created
            assert validator.orchestrator is not None
            assert validator.signal_generator is not None
            assert validator.risk_manager is not None
            assert validator.ib_adapter is not None
            assert validator.market_data_feed is not None
            assert validator.performance_tracker is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
