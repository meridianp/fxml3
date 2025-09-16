"""
Test Suite for FXML4 Business Continuity System

This test suite validates the business continuity functionality including:
- Broker connection monitoring and failover
- Trading state preservation and restoration
- Recovery time SLA compliance
- Connection health monitoring
- Failover orchestration and decision making

Test Categories:
- Unit tests for individual components
- Integration tests for end-to-end workflows
- Performance tests for SLA validation
- Stress tests for extreme scenarios
"""

import asyncio
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch

import pytest

from fxml4.brokers.connectivity.business_continuity_manager import (
    BrokerConnection,
    BusinessContinuityManager,
    BusinessContinuityValidator,
    ConnectionStatus,
    FailoverTrigger,
    TradingState,
)
from fxml4.brokers.connectivity.connection_monitor import (
    AlertSeverity,
    ConnectionMonitor,
    HealthStatus,
)
from fxml4.brokers.connectivity.failover_orchestrator import (
    BrokerCapability,
    FailoverCandidate,
    FailoverDecision,
    FailoverOrchestrator,
    FailoverReason,
)


@pytest.fixture
async def business_continuity_manager():
    """Create a BusinessContinuityManager instance for testing."""
    manager = BusinessContinuityManager(recovery_sla_seconds=30)

    # Register test brokers
    await manager.register_broker("ib_primary", "Interactive Brokers", "primary", 10)
    await manager.register_broker("fxcm_backup", "FXCM Backup", "backup", 20)
    await manager.register_broker("manual_backup", "Manual Backup", "backup", 30)

    # Set initial states
    await manager.set_broker_status("ib_primary", ConnectionStatus.CONNECTED)
    await manager.set_broker_status("fxcm_backup", ConnectionStatus.CONNECTED)
    await manager.set_broker_status("manual_backup", ConnectionStatus.CONNECTED)
    await manager.set_active_broker("ib_primary")

    yield manager


@pytest.fixture
async def connection_monitor():
    """Create a ConnectionMonitor instance for testing."""
    monitor = ConnectionMonitor(heartbeat_interval=5, timeout_threshold=15)

    # Add test connections
    await monitor.add_connection(
        "test_broker1", "http://localhost:8001/api", "http://localhost:8001/health"
    )
    await monitor.add_connection(
        "test_broker2", "http://localhost:8002/api", "http://localhost:8002/health"
    )

    yield monitor

    # Cleanup
    if monitor.is_monitoring:
        await monitor.stop_monitoring()


@pytest.fixture
async def failover_orchestrator():
    """Create a FailoverOrchestrator instance for testing."""
    orchestrator = FailoverOrchestrator(max_failover_time=30)

    # Register test brokers with capabilities
    capabilities_primary = {
        "real_time_data": BrokerCapability(
            "real_time_data", True, 95.0, 98.0, datetime.utcnow()
        ),
        "order_execution": BrokerCapability(
            "order_execution", True, 92.0, 97.0, datetime.utcnow()
        ),
    }

    capabilities_backup = {
        "real_time_data": BrokerCapability(
            "real_time_data", True, 88.0, 95.0, datetime.utcnow()
        ),
        "order_execution": BrokerCapability(
            "order_execution", True, 85.0, 92.0, datetime.utcnow()
        ),
    }

    await orchestrator.register_broker_for_failover(
        "primary_broker",
        {
            "name": "Primary",
            "type": "interactive_brokers",
            "status": "connected",
            "current_load": 15.0,
        },
        capabilities_primary,
        failover_chain=["backup_broker"],
    )

    await orchestrator.register_broker_for_failover(
        "backup_broker",
        {"name": "Backup", "type": "fxcm", "status": "connected", "current_load": 25.0},
        capabilities_backup,
    )

    yield orchestrator


class TestBusinessContinuityManager:
    """Test cases for BusinessContinuityManager."""

    @pytest.mark.asyncio
    async def test_broker_registration(self, business_continuity_manager):
        """Test broker registration functionality."""
        manager = business_continuity_manager

        assert "ib_primary" in manager.connections
        assert "fxcm_backup" in manager.connections
        assert "manual_backup" in manager.connections

        # Test broker properties
        ib_connection = manager.connections["ib_primary"]
        assert ib_connection.broker_name == "Interactive Brokers"
        assert ib_connection.connection_type == "primary"
        assert ib_connection.priority == 10

    @pytest.mark.asyncio
    async def test_broker_status_updates(self, business_continuity_manager):
        """Test broker status update functionality."""
        manager = business_continuity_manager

        # Test status change
        await manager.set_broker_status("ib_primary", ConnectionStatus.DISCONNECTED)

        connection = manager.connections["ib_primary"]
        assert connection.status == ConnectionStatus.DISCONNECTED
        assert connection.disconnection_time is not None

    @pytest.mark.asyncio
    async def test_active_broker_management(self, business_continuity_manager):
        """Test active broker management."""
        manager = business_continuity_manager

        # Test setting active broker
        result = await manager.set_active_broker("fxcm_backup")
        assert result is True
        assert manager.active_broker == "fxcm_backup"

        # Test setting disconnected broker as active (should fail)
        await manager.set_broker_status("manual_backup", ConnectionStatus.DISCONNECTED)
        result = await manager.set_active_broker("manual_backup")
        assert result is False

    @pytest.mark.asyncio
    async def test_trading_state_preservation(self, business_continuity_manager):
        """Test trading state preservation functionality."""
        manager = business_continuity_manager

        # Test state preservation
        test_positions = [{"symbol": "GBPUSD", "size": 100000, "side": "long"}]
        test_orders = [{"id": "order123", "symbol": "EURUSD", "size": 50000}]
        test_account = {"balance": 10000.0, "unrealized_pnl": 150.0}

        await manager.preserve_trading_state(test_positions, test_orders, test_account)

        assert manager.trading_state is not None
        assert len(manager.trading_state.positions) == 1
        assert len(manager.trading_state.pending_orders) == 1
        assert manager.trading_state.account_balance == 10000.0
        assert manager.trading_state.unrealized_pnl == 150.0

    @pytest.mark.asyncio
    async def test_automatic_failover_trigger(self, business_continuity_manager):
        """Test automatic failover triggering."""
        manager = business_continuity_manager

        # Mock the failover execution to avoid complex setup
        original_method = manager._execute_failover
        manager._execute_failover = AsyncMock(return_value=True)

        # Trigger failover by disconnecting active broker
        await manager.set_broker_status("ib_primary", ConnectionStatus.DISCONNECTED)

        # Give some time for failover to be triggered
        await asyncio.sleep(0.1)

        # Check that failover was initiated
        assert manager.is_recovery_in_progress or len(manager.failover_history) > 0

        # Restore original method
        manager._execute_failover = original_method

    @pytest.mark.asyncio
    async def test_recovery_metrics(self, business_continuity_manager):
        """Test recovery metrics calculation."""
        manager = business_continuity_manager

        metrics = manager.get_recovery_metrics()

        assert hasattr(metrics, "total_failovers")
        assert hasattr(metrics, "successful_failovers")
        assert hasattr(metrics, "average_recovery_time")
        assert hasattr(metrics, "availability_percentage")

        # Initially should have no failovers
        assert metrics.total_failovers == 0
        assert metrics.availability_percentage >= 99.0  # Should be high initially

    @pytest.mark.asyncio
    async def test_manual_failover(self, business_continuity_manager):
        """Test manual failover triggering."""
        manager = business_continuity_manager

        # Mock the failover execution
        manager._execute_failover = AsyncMock(return_value=True)

        # Trigger manual failover
        result = await manager.trigger_manual_failover("fxcm_backup")

        # Check that manual failover was processed
        assert result is True or manager.is_recovery_in_progress

    @pytest.mark.asyncio
    async def test_status_summary(self, business_continuity_manager):
        """Test status summary generation."""
        manager = business_continuity_manager

        summary = manager.get_status_summary()

        assert "timestamp" in summary
        assert "active_broker" in summary
        assert "connections" in summary
        assert "metrics" in summary

        # Check broker connections in summary
        assert len(summary["connections"]) == 3
        assert "ib_primary" in summary["connections"]


class TestBusinessContinuityValidator:
    """Test cases for BusinessContinuityValidator."""

    @pytest.mark.asyncio
    async def test_validator_initialization(self, business_continuity_manager):
        """Test validator initialization."""
        validator = BusinessContinuityValidator(business_continuity_manager)

        assert validator.continuity_manager == business_continuity_manager
        assert isinstance(validator.test_results, list)

    @pytest.mark.asyncio
    async def test_recovery_sla_validation(self, business_continuity_manager):
        """Test recovery SLA validation."""
        validator = BusinessContinuityValidator(business_continuity_manager)

        # Mock the simulation method to return predictable results
        async def mock_simulate_disconnection():
            return 15.0  # 15 seconds recovery time

        validator._simulate_broker_disconnection = mock_simulate_disconnection

        # Run validation with few tests for speed
        results = await validator.validate_recovery_sla(num_tests=3)

        assert "test_timestamp" in results
        assert "total_tests" in results
        assert "successful_recoveries" in results
        assert "sla_compliance_rate_percent" in results

        assert results["total_tests"] == 3
        # With 15s recovery time, should be SLA compliant (< 30s)
        assert results["sla_compliance_rate_percent"] > 0

    @pytest.mark.asyncio
    async def test_validation_report_generation(self, business_continuity_manager):
        """Test validation report generation."""
        validator = BusinessContinuityValidator(business_continuity_manager)

        # Add some test results
        test_result = {
            "test_timestamp": datetime.utcnow().isoformat(),
            "total_tests": 5,
            "sla_compliance_rate_percent": 80.0,
            "average_recovery_time_seconds": 25.0,
        }
        validator.test_results.append(test_result)

        report = validator.get_validation_report()

        assert "validation_summary" in report
        assert "operational_metrics" in report
        assert "recommendations" in report

        # Check that recommendations are generated
        assert isinstance(report["recommendations"], list)


class TestConnectionMonitor:
    """Test cases for ConnectionMonitor."""

    @pytest.mark.asyncio
    async def test_connection_addition(self, connection_monitor):
        """Test connection addition functionality."""
        monitor = connection_monitor

        assert "test_broker1" in monitor.monitored_connections
        assert "test_broker2" in monitor.monitored_connections

        # Test connection configuration
        config = monitor.monitored_connections["test_broker1"]
        assert config["endpoint_url"] == "http://localhost:8001/api"
        assert config["heartbeat_endpoint"] == "http://localhost:8001/health"

    @pytest.mark.asyncio
    async def test_monitoring_lifecycle(self, connection_monitor):
        """Test monitoring start/stop lifecycle."""
        monitor = connection_monitor

        # Start monitoring
        await monitor.start_monitoring()
        assert monitor.is_monitoring is True
        assert monitor.monitor_task is not None

        # Stop monitoring
        await monitor.stop_monitoring()
        assert monitor.is_monitoring is False

    @pytest.mark.asyncio
    async def test_connection_status_retrieval(self, connection_monitor):
        """Test connection status retrieval."""
        monitor = connection_monitor

        status = monitor.get_connection_status("test_broker1")

        assert status is not None
        assert "broker_id" in status
        assert "current_status" in status
        assert "endpoint_url" in status
        assert "performance_metrics" in status

        # Test non-existent broker
        status = monitor.get_connection_status("non_existent")
        assert status is None

    @pytest.mark.asyncio
    async def test_monitoring_summary(self, connection_monitor):
        """Test monitoring summary generation."""
        monitor = connection_monitor

        summary = monitor.get_monitoring_summary()

        assert "timestamp" in summary
        assert "monitoring_active" in summary
        assert "total_connections" in summary
        assert "connection_health" in summary
        assert "connections" in summary

        # Check health breakdown
        health = summary["connection_health"]
        assert "healthy" in health
        assert "warning" in health
        assert "critical" in health
        assert "unknown" in health

    @pytest.mark.asyncio
    async def test_alert_management(self, connection_monitor):
        """Test alert acknowledgment and resolution."""
        monitor = connection_monitor

        # Generate a test alert
        await monitor._generate_alert(
            "test_broker1",
            AlertSeverity.WARNING,
            "test_alert",
            "Test Alert",
            "This is a test alert",
        )

        # Check that alert was created
        assert len(monitor.alert_history) > 0

        latest_alert = monitor.alert_history[-1]
        alert_id = latest_alert.alert_id

        # Test acknowledgment
        result = await monitor.acknowledge_alert(alert_id)
        assert result is True
        assert latest_alert.acknowledged is True

        # Test resolution
        result = await monitor.resolve_alert(alert_id)
        assert result is True
        assert latest_alert.resolved is True


class TestFailoverOrchestrator:
    """Test cases for FailoverOrchestrator."""

    @pytest.mark.asyncio
    async def test_broker_registration_for_failover(self, failover_orchestrator):
        """Test broker registration for failover."""
        orchestrator = failover_orchestrator

        assert "primary_broker" in orchestrator.registered_brokers
        assert "backup_broker" in orchestrator.registered_brokers

        # Test failover chain
        assert "primary_broker" in orchestrator.failover_chains
        assert "backup_broker" in orchestrator.failover_chains["primary_broker"]

    @pytest.mark.asyncio
    async def test_failover_rule_addition(self, failover_orchestrator):
        """Test failover rule addition."""
        orchestrator = failover_orchestrator

        await orchestrator.add_failover_rule(
            "test_rule",
            {"status": "disconnected"},
            FailoverDecision.IMMEDIATE_FAILOVER,
            priority=50,
        )

        assert len(orchestrator.failover_rules) > 0

        # Find the added rule
        test_rule = None
        for rule in orchestrator.failover_rules:
            if rule["name"] == "test_rule":
                test_rule = rule
                break

        assert test_rule is not None
        assert test_rule["action"] == FailoverDecision.IMMEDIATE_FAILOVER
        assert test_rule["priority"] == 50

    @pytest.mark.asyncio
    async def test_failover_need_evaluation(self, failover_orchestrator):
        """Test failover need evaluation."""
        orchestrator = failover_orchestrator

        # Add test rule
        await orchestrator.add_failover_rule(
            "disconnection_rule",
            {"status": "disconnected"},
            FailoverDecision.IMMEDIATE_FAILOVER,
        )

        # Test evaluation for disconnected broker
        decision = await orchestrator.evaluate_failover_need(
            "primary_broker",
            {"latency_ms": 1000, "success_rate_percent": 95.0},
            "disconnected",
        )

        assert decision == FailoverDecision.IMMEDIATE_FAILOVER

        # Test evaluation for healthy broker
        decision = await orchestrator.evaluate_failover_need(
            "primary_broker",
            {"latency_ms": 100, "success_rate_percent": 99.0},
            "connected",
        )

        assert decision == FailoverDecision.NO_ACTION

    @pytest.mark.asyncio
    async def test_failover_target_selection(self, failover_orchestrator):
        """Test failover target selection."""
        orchestrator = failover_orchestrator

        candidate = await orchestrator.select_failover_target("primary_broker")

        assert candidate is not None
        assert isinstance(candidate, FailoverCandidate)
        assert candidate.broker_id == "backup_broker"
        assert candidate.priority_score >= 0

    @pytest.mark.asyncio
    async def test_failover_execution_phases(self, failover_orchestrator):
        """Test failover execution phases."""
        orchestrator = failover_orchestrator

        # Create a failover candidate
        candidate = FailoverCandidate(
            broker_id="backup_broker",
            broker_name="Backup Broker",
            priority_score=85.0,
            capabilities={},
            estimated_switch_time=15.0,
            compatibility_score=90.0,
            current_load=20.0,
            availability_status="connected",
        )

        # Mock the validation methods for testing
        orchestrator._assess_failover_feasibility = AsyncMock(return_value=True)
        orchestrator._prepare_target_broker = AsyncMock()
        orchestrator._capture_trading_state = AsyncMock(return_value=None)
        orchestrator._switch_active_broker = AsyncMock()
        orchestrator._restore_trading_state = AsyncMock()
        orchestrator._validate_failover_success = AsyncMock(return_value=True)
        orchestrator._finalize_failover = AsyncMock()

        # Execute failover
        execution = await orchestrator.execute_failover(
            "primary_broker", candidate, FailoverReason.CONNECTION_LOST
        )

        assert execution is not None
        assert execution.source_broker == "primary_broker"
        assert execution.target_broker == "backup_broker"
        assert execution.reason == FailoverReason.CONNECTION_LOST
        assert execution.success is True

    @pytest.mark.asyncio
    async def test_orchestrator_status(self, failover_orchestrator):
        """Test orchestrator status retrieval."""
        orchestrator = failover_orchestrator

        status = orchestrator.get_orchestrator_status()

        assert "timestamp" in status
        assert "registered_brokers" in status
        assert "active_executions" in status
        assert "total_executions" in status
        assert "success_rate_percent" in status
        assert "performance_thresholds" in status

        # Check broker count
        assert status["registered_brokers"] == 2


@pytest.mark.integration
class TestBusinessContinuityIntegration:
    """Integration tests for business continuity system."""

    @pytest.mark.asyncio
    async def test_end_to_end_failover(
        self, business_continuity_manager, connection_monitor
    ):
        """Test end-to-end failover process."""
        manager = business_continuity_manager

        # Preserve trading state
        await manager.preserve_trading_state(
            positions=[{"symbol": "GBPUSD", "size": 100000}],
            orders=[{"id": "test_order", "symbol": "EURUSD"}],
            account_data={"balance": 10000.0},
        )

        # Trigger failover by disconnecting primary
        original_active = manager.active_broker

        # Mock the failover execution for integration testing
        manager._execute_failover = AsyncMock(return_value=True)

        await manager.set_broker_status("ib_primary", ConnectionStatus.DISCONNECTED)

        # Allow some time for failover processing
        await asyncio.sleep(0.2)

        # Verify that failover was triggered or completed
        assert (
            manager.is_recovery_in_progress
            or len(manager.failover_history) > 0
            or manager.active_broker != original_active
        )

    @pytest.mark.asyncio
    async def test_multiple_broker_failure_scenario(self, business_continuity_manager):
        """Test scenario with multiple broker failures."""
        manager = business_continuity_manager

        # Mock failover execution
        manager._execute_failover = AsyncMock(return_value=True)

        # Simulate multiple failures
        await manager.set_broker_status("ib_primary", ConnectionStatus.FAILED)
        await manager.set_broker_status("fxcm_backup", ConnectionStatus.FAILED)

        # Allow processing time
        await asyncio.sleep(0.1)

        # System should have attempted failover or be in recovery
        status = manager.get_status_summary()
        assert (
            manager.is_recovery_in_progress
            or len(manager.failover_history) > 0
            or status["active_broker"] == "manual_backup"
        )

    @pytest.mark.asyncio
    async def test_recovery_metrics_after_failover(self, business_continuity_manager):
        """Test recovery metrics after simulated failover."""
        manager = business_continuity_manager

        # Simulate a completed failover by directly adding to history
        from fxml4.brokers.connectivity.business_continuity_manager import FailoverEvent

        failover_event = FailoverEvent(
            event_id="test_failover_001",
            timestamp=datetime.utcnow(),
            trigger=FailoverTrigger.CONNECTION_LOST,
            source_broker="ib_primary",
            target_broker="fxcm_backup",
            recovery_time_seconds=25.0,
            success=True,
            trading_state_preserved=True,
        )

        manager.failover_history.append(failover_event)

        # Get metrics
        metrics = manager.get_recovery_metrics()

        assert metrics.total_failovers == 1
        assert metrics.successful_failovers == 1
        assert metrics.average_recovery_time == 25.0
        assert metrics.sla_compliance_rate == 100.0  # 25s < 30s SLA


@pytest.mark.performance
class TestBusinessContinuityPerformance:
    """Performance tests for business continuity system."""

    @pytest.mark.asyncio
    async def test_failover_speed_benchmark(self, business_continuity_manager):
        """Benchmark failover execution speed."""
        manager = business_continuity_manager

        # Mock fast failover execution
        async def fast_mock_failover(source, target, trigger):
            await asyncio.sleep(0.01)  # Simulate very fast failover
            return True

        manager._execute_failover = fast_mock_failover

        # Measure failover trigger speed
        start_time = time.perf_counter()

        await manager.set_broker_status("ib_primary", ConnectionStatus.DISCONNECTED)
        await asyncio.sleep(0.1)  # Allow processing

        elapsed_time = time.perf_counter() - start_time

        # Should trigger very quickly (within 1 second including processing)
        assert elapsed_time < 1.0

    @pytest.mark.asyncio
    async def test_concurrent_health_checks(self, connection_monitor):
        """Test concurrent health check performance."""
        monitor = connection_monitor

        # Mock HTTP health checks to return quickly
        async def fast_http_check(endpoint, headers):
            await asyncio.sleep(0.001)  # 1ms simulated response
            return True, 1.0, None

        monitor._perform_http_health_check = fast_http_check

        # Start monitoring
        await monitor.start_monitoring()

        # Let it run for a short time
        await asyncio.sleep(1.0)

        # Check that health checks were performed
        for broker_id in monitor.monitored_connections:
            config = monitor.monitored_connections[broker_id]
            assert config["total_checks"] > 0

        await monitor.stop_monitoring()

    @pytest.mark.asyncio
    async def test_state_preservation_performance(self, business_continuity_manager):
        """Test state preservation performance with large datasets."""
        manager = business_continuity_manager

        # Create large test datasets
        large_positions = [
            {"symbol": f"PAIR{i:03d}", "size": 100000, "side": "long"}
            for i in range(100)
        ]

        large_orders = [
            {"id": f"order_{i:03d}", "symbol": f"PAIR{i:03d}", "size": 50000}
            for i in range(200)
        ]

        large_account = {
            "balance": 100000.0,
            "positions": {f"PAIR{i:03d}": {"pnl": i * 10.5} for i in range(100)},
        }

        # Measure preservation time
        start_time = time.perf_counter()

        await manager.preserve_trading_state(
            large_positions, large_orders, large_account
        )

        preservation_time = time.perf_counter() - start_time

        # Should preserve state quickly (within 1 second even for large datasets)
        assert preservation_time < 1.0

        # Verify all data was preserved
        state = manager.trading_state
        assert len(state.positions) == 100
        assert len(state.pending_orders) == 200


@pytest.mark.stress
class TestBusinessContinuityStress:
    """Stress tests for business continuity system."""

    @pytest.mark.asyncio
    async def test_rapid_connection_changes(self, business_continuity_manager):
        """Test rapid connection status changes."""
        manager = business_continuity_manager

        # Mock failover to prevent actual execution
        manager._execute_failover = AsyncMock(return_value=True)

        # Rapid status changes
        for i in range(20):
            if i % 2 == 0:
                await manager.set_broker_status(
                    "ib_primary", ConnectionStatus.DISCONNECTED
                )
            else:
                await manager.set_broker_status(
                    "ib_primary", ConnectionStatus.CONNECTED
                )

            await asyncio.sleep(0.01)  # Brief pause

        # System should remain stable
        status = manager.get_status_summary()
        assert len(status["connections"]) == 3  # All brokers still registered

    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self, connection_monitor):
        """Test memory usage under continuous monitoring load."""
        monitor = connection_monitor

        # Mock health checks to generate metrics rapidly
        async def rapid_check(broker_id, config):
            from fxml4.brokers.connectivity.connection_monitor import (
                HealthCheckResult,
                HealthStatus,
            )

            return HealthCheckResult(
                broker_id=broker_id,
                timestamp=datetime.utcnow(),
                status=HealthStatus.HEALTHY,
                latency_ms=100.0,
                success=True,
                check_duration_ms=5.0,
            )

        monitor._check_connection_health = rapid_check

        # Run monitoring for extended period
        await monitor.start_monitoring()
        await asyncio.sleep(2.0)  # Run for 2 seconds
        await monitor.stop_monitoring()

        # Check that metrics collections have reasonable sizes
        for broker_id in monitor.monitored_connections:
            metrics = monitor.connection_metrics[broker_id]
            health_history = monitor.health_history[broker_id]

            # Should have collected data but not excessive amounts
            assert len(metrics) < 1000  # maxlen should limit collection size
            assert len(health_history) < 1000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
