#!/usr/bin/env python3
"""
FXML4 Business Continuity Validation Script

This script validates that the FXML4 trading system can recover from broker
disconnections within 30 seconds and resume trading operations automatically.

Key Validations:
- Broker disconnection detection time
- Automatic failover trigger and execution
- Trading state preservation during failover
- Recovery time SLA compliance (<30 seconds)
- System availability and uptime metrics
- Comprehensive business continuity reporting

Usage:
    python scripts/prove_business_continuity.py [--mode comprehensive|quick|stress]
    python scripts/prove_business_continuity.py --test-count 20 --sla-seconds 30
    python scripts/prove_business_continuity.py --output-file business_continuity_report.html
"""

import argparse
import asyncio
import json
import logging
import statistics
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fxml4.brokers.connectivity.business_continuity_manager import (
    BrokerConnection,
    BusinessContinuityManager,
    BusinessContinuityValidator,
    ConnectionStatus,
    FailoverTrigger,
)
from fxml4.brokers.connectivity.connection_monitor import (
    ConnectionMonitor,
    HealthStatus,
)
from fxml4.brokers.connectivity.failover_orchestrator import (
    BrokerCapability,
    FailoverDecision,
    FailoverOrchestrator,
    FailoverReason,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class BusinessContinuityProofSystem:
    """
    Comprehensive business continuity validation system.

    Tests and validates all aspects of business continuity including
    broker failover, connection recovery, and trading state preservation.
    """

    def __init__(self, sla_seconds: int = 30):
        self.sla_seconds = sla_seconds
        self.continuity_manager = BusinessContinuityManager(
            recovery_sla_seconds=sla_seconds
        )
        self.connection_monitor = ConnectionMonitor(
            heartbeat_interval=5, timeout_threshold=15
        )
        self.failover_orchestrator = FailoverOrchestrator(max_failover_time=sla_seconds)
        self.validator = BusinessContinuityValidator(self.continuity_manager)

        # Test results
        self.test_results: Dict[str, Any] = {}
        self.performance_metrics: Dict[str, Any] = {}
        self.validation_report: Dict[str, Any] = {}

    async def initialize_test_environment(self) -> None:
        """Initialize the test environment with mock brokers."""
        logger.info("Initializing business continuity test environment...")

        # Register test brokers
        await self._setup_test_brokers()

        # Configure failover rules
        await self._setup_failover_rules()

        # Start monitoring services
        await self.connection_monitor.start_monitoring()

        logger.info("Test environment initialized successfully")

    async def _setup_test_brokers(self) -> None:
        """Set up test brokers for continuity testing."""
        # Primary broker (Interactive Brokers)
        await self.continuity_manager.register_broker(
            broker_id="ib_primary",
            broker_name="Interactive Brokers Primary",
            connection_type="primary",
            priority=10,
            capabilities={
                "real_time_data",
                "order_execution",
                "position_tracking",
                "risk_management",
                "market_hours_trading",
            },
        )

        # Backup broker 1 (FXCM)
        await self.continuity_manager.register_broker(
            broker_id="fxcm_backup1",
            broker_name="FXCM Backup Primary",
            connection_type="backup",
            priority=20,
            capabilities={
                "real_time_data",
                "order_execution",
                "position_tracking",
                "forex_trading",
                "market_hours_trading",
            },
        )

        # Backup broker 2 (Manual)
        await self.continuity_manager.register_broker(
            broker_id="manual_backup2",
            broker_name="Manual Trading Backup",
            connection_type="backup",
            priority=30,
            capabilities={"manual_execution", "position_tracking", "risk_override"},
        )

        # Add connection monitoring
        await self.connection_monitor.add_connection(
            "ib_primary",
            "http://localhost:8001/api/brokers/ib",
            heartbeat_endpoint="http://localhost:8001/health",
        )
        await self.connection_monitor.add_connection(
            "fxcm_backup1",
            "http://localhost:8002/api/brokers/fxcm",
            heartbeat_endpoint="http://localhost:8002/health",
        )
        await self.connection_monitor.add_connection(
            "manual_backup2",
            "http://localhost:8003/api/brokers/manual",
            heartbeat_endpoint="http://localhost:8003/health",
        )

        # Register with failover orchestrator
        capabilities_ib = {
            "real_time_data": BrokerCapability(
                "real_time_data", True, 95.0, 98.0, datetime.utcnow()
            ),
            "order_execution": BrokerCapability(
                "order_execution", True, 92.0, 97.0, datetime.utcnow()
            ),
            "position_tracking": BrokerCapability(
                "position_tracking", True, 98.0, 99.0, datetime.utcnow()
            ),
        }

        capabilities_fxcm = {
            "real_time_data": BrokerCapability(
                "real_time_data", True, 88.0, 95.0, datetime.utcnow()
            ),
            "order_execution": BrokerCapability(
                "order_execution", True, 85.0, 92.0, datetime.utcnow()
            ),
            "forex_trading": BrokerCapability(
                "forex_trading", True, 90.0, 96.0, datetime.utcnow()
            ),
        }

        capabilities_manual = {
            "manual_execution": BrokerCapability(
                "manual_execution", True, 70.0, 85.0, datetime.utcnow()
            ),
            "risk_override": BrokerCapability(
                "risk_override", True, 80.0, 90.0, datetime.utcnow()
            ),
        }

        await self.failover_orchestrator.register_broker_for_failover(
            "ib_primary",
            {
                "name": "Interactive Brokers",
                "type": "interactive_brokers",
                "status": "connected",
                "current_load": 15.0,
            },
            capabilities_ib,
            failover_chain=["fxcm_backup1", "manual_backup2"],
        )

        await self.failover_orchestrator.register_broker_for_failover(
            "fxcm_backup1",
            {
                "name": "FXCM",
                "type": "fxcm",
                "status": "connected",
                "current_load": 25.0,
            },
            capabilities_fxcm,
        )

        await self.failover_orchestrator.register_broker_for_failover(
            "manual_backup2",
            {
                "name": "Manual Trading",
                "type": "manual",
                "status": "ready",
                "current_load": 5.0,
            },
            capabilities_manual,
        )

        # Set initial states
        await self.continuity_manager.set_broker_status(
            "ib_primary", ConnectionStatus.CONNECTED
        )
        await self.continuity_manager.set_broker_status(
            "fxcm_backup1", ConnectionStatus.CONNECTED
        )
        await self.continuity_manager.set_broker_status(
            "manual_backup2", ConnectionStatus.CONNECTED
        )

        # Set active broker
        await self.continuity_manager.set_active_broker("ib_primary")

    async def _setup_failover_rules(self) -> None:
        """Set up failover decision rules."""
        # Immediate failover for connection loss
        await self.failover_orchestrator.add_failover_rule(
            "immediate_connection_loss",
            {"status": "disconnected"},
            FailoverDecision.IMMEDIATE_FAILOVER,
            priority=10,
        )

        # Graceful failover for performance degradation
        await self.failover_orchestrator.add_failover_rule(
            "performance_degradation",
            {"metrics": {"latency_ms": {"operator": "gte", "value": 3000}}},
            FailoverDecision.GRACEFUL_FAILOVER,
            priority=20,
        )

        # Warning for moderate latency
        await self.failover_orchestrator.add_failover_rule(
            "latency_warning",
            {"metrics": {"latency_ms": {"operator": "gte", "value": 1000}}},
            FailoverDecision.NO_ACTION,  # Just monitoring
            priority=30,
        )

    async def run_comprehensive_validation(
        self, test_count: int = 15
    ) -> Dict[str, Any]:
        """Run comprehensive business continuity validation."""
        logger.info(
            f"Starting comprehensive business continuity validation with {test_count} tests"
        )

        start_time = datetime.utcnow()
        results = {
            "test_timestamp": start_time.isoformat(),
            "test_configuration": {
                "sla_seconds": self.sla_seconds,
                "test_count": test_count,
                "test_type": "comprehensive",
            },
            "individual_tests": {},
        }

        try:
            # Test 1: Connection Detection Speed
            logger.info("Test 1: Connection detection speed")
            detection_results = await self._test_connection_detection_speed()
            results["individual_tests"]["connection_detection"] = detection_results

            # Test 2: Automatic Failover Execution
            logger.info("Test 2: Automatic failover execution")
            failover_results = await self._test_automatic_failover(test_count // 3)
            results["individual_tests"]["automatic_failover"] = failover_results

            # Test 3: Trading State Preservation
            logger.info("Test 3: Trading state preservation")
            state_preservation_results = await self._test_state_preservation()
            results["individual_tests"][
                "state_preservation"
            ] = state_preservation_results

            # Test 4: Recovery Time SLA Compliance
            logger.info("Test 4: Recovery time SLA compliance")
            sla_compliance_results = await self.validator.validate_recovery_sla(
                test_count // 2
            )
            results["individual_tests"]["sla_compliance"] = sla_compliance_results

            # Test 5: Multiple Failover Chain
            logger.info("Test 5: Multiple failover chain testing")
            chain_results = await self._test_failover_chain()
            results["individual_tests"]["failover_chain"] = chain_results

            # Test 6: System Availability Metrics
            logger.info("Test 6: System availability metrics")
            availability_results = await self._test_system_availability()
            results["individual_tests"]["system_availability"] = availability_results

            # Test 7: Stress Testing
            logger.info("Test 7: Stress testing under load")
            stress_results = await self._test_stress_conditions()
            results["individual_tests"]["stress_testing"] = stress_results

            # Calculate overall results
            results["overall_results"] = self._calculate_overall_results(
                results["individual_tests"]
            )

            # Generate recommendations
            results["recommendations"] = self._generate_recommendations(results)

            execution_time = (datetime.utcnow() - start_time).total_seconds()
            results["execution_time_seconds"] = round(execution_time, 2)

            logger.info(f"Comprehensive validation completed in {execution_time:.1f}s")
            return results

        except Exception as e:
            logger.error(f"Comprehensive validation failed: {e}")
            results["error"] = str(e)
            results["success"] = False
            return results

    async def _test_connection_detection_speed(self) -> Dict[str, Any]:
        """Test connection issue detection speed."""
        detection_times = []

        for i in range(5):
            start_time = datetime.utcnow()

            # Simulate connection issue
            original_status = ConnectionStatus.CONNECTED
            await self.continuity_manager.set_broker_status(
                "ib_primary", ConnectionStatus.DISCONNECTED
            )

            # Wait for detection (should be nearly immediate)
            detection_timeout = 10.0  # seconds
            detection_start = datetime.utcnow()

            while (
                datetime.utcnow() - detection_start
            ).total_seconds() < detection_timeout:
                status_summary = self.continuity_manager.get_status_summary()
                if status_summary["recovery_in_progress"]:
                    detection_time = (datetime.utcnow() - start_time).total_seconds()
                    detection_times.append(detection_time)
                    break
                await asyncio.sleep(0.1)

            # Restore connection for next test
            await self.continuity_manager.set_broker_status(
                "ib_primary", original_status
            )
            await asyncio.sleep(1)  # Brief pause between tests

        avg_detection_time = (
            sum(detection_times) / len(detection_times) if detection_times else 10.0
        )
        max_detection_time = max(detection_times) if detection_times else 10.0

        return {
            "test_name": "connection_detection_speed",
            "total_tests": 5,
            "successful_detections": len(detection_times),
            "average_detection_time_seconds": round(avg_detection_time, 3),
            "max_detection_time_seconds": round(max_detection_time, 3),
            "target_detection_time_seconds": 5.0,
            "sla_met": max_detection_time <= 5.0,
            "detection_times": [round(t, 3) for t in detection_times],
        }

    async def _test_automatic_failover(self, test_count: int = 5) -> Dict[str, Any]:
        """Test automatic failover execution."""
        failover_results = []

        for i in range(test_count):
            logger.info(f"Automatic failover test {i+1}/{test_count}")

            # Setup: Ensure primary is active
            await self.continuity_manager.set_broker_status(
                "ib_primary", ConnectionStatus.CONNECTED
            )
            await self.continuity_manager.set_active_broker("ib_primary")

            # Preserve some mock trading state
            await self.continuity_manager.preserve_trading_state(
                positions=[{"symbol": "GBPUSD", "size": 100000, "side": "long"}],
                orders=[
                    {
                        "id": "order123",
                        "symbol": "GBPUSD",
                        "size": 50000,
                        "side": "short",
                        "status": "pending",
                    }
                ],
                account_data={"balance": 10000.0, "unrealized_pnl": 150.0},
            )

            start_time = datetime.utcnow()

            # Trigger disconnection
            await self.continuity_manager.set_broker_status(
                "ib_primary", ConnectionStatus.DISCONNECTED
            )

            # Wait for automatic failover
            failover_timeout = self.sla_seconds * 2
            failover_start = datetime.utcnow()
            failover_success = False

            while (
                datetime.utcnow() - failover_start
            ).total_seconds() < failover_timeout:
                status = self.continuity_manager.get_status_summary()
                if (
                    not status["recovery_in_progress"]
                    and status["active_broker"]
                    and status["active_broker"] != "ib_primary"
                ):
                    failover_success = True
                    break
                await asyncio.sleep(0.1)

            end_time = datetime.utcnow()
            execution_time = (end_time - start_time).total_seconds()

            result = {
                "test_number": i + 1,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "execution_time_seconds": round(execution_time, 2),
                "success": failover_success,
                "sla_compliant": execution_time <= self.sla_seconds,
                "target_broker": status["active_broker"] if failover_success else None,
            }

            failover_results.append(result)

            # Brief pause between tests
            await asyncio.sleep(2)

        # Calculate summary statistics
        successful_failovers = sum(1 for r in failover_results if r["success"])
        sla_compliant_failovers = sum(1 for r in failover_results if r["sla_compliant"])
        execution_times = [
            r["execution_time_seconds"] for r in failover_results if r["success"]
        ]

        avg_execution_time = (
            sum(execution_times) / len(execution_times) if execution_times else 0.0
        )
        max_execution_time = max(execution_times) if execution_times else 0.0

        return {
            "test_name": "automatic_failover",
            "total_tests": test_count,
            "successful_failovers": successful_failovers,
            "sla_compliant_failovers": sla_compliant_failovers,
            "success_rate_percent": round((successful_failovers / test_count) * 100, 1),
            "sla_compliance_rate_percent": round(
                (sla_compliant_failovers / test_count) * 100, 1
            ),
            "average_execution_time_seconds": round(avg_execution_time, 2),
            "max_execution_time_seconds": round(max_execution_time, 2),
            "target_sla_seconds": self.sla_seconds,
            "individual_results": failover_results,
        }

    async def _test_state_preservation(self) -> Dict[str, Any]:
        """Test trading state preservation during failover."""
        test_positions = [
            {"symbol": "GBPUSD", "size": 100000, "side": "long", "entry_price": 1.2800},
            {"symbol": "EURUSD", "size": 75000, "side": "short", "entry_price": 1.0950},
        ]

        test_orders = [
            {
                "id": "order001",
                "symbol": "GBPUSD",
                "size": 50000,
                "side": "short",
                "price": 1.2850,
                "status": "pending",
            },
            {
                "id": "order002",
                "symbol": "USDCHF",
                "size": 80000,
                "side": "long",
                "price": 0.9200,
                "status": "pending",
            },
        ]

        test_account = {
            "balance": 25000.0,
            "unrealized_pnl": 320.50,
            "margin_used": 3500.0,
            "risk_limits": {"max_position_size": 200000, "max_daily_loss": 1000.0},
        }

        # Preserve state before failover
        await self.continuity_manager.preserve_trading_state(
            positions=test_positions, orders=test_orders, account_data=test_account
        )

        # Execute failover
        await self.continuity_manager.set_broker_status(
            "ib_primary", ConnectionStatus.DISCONNECTED
        )

        # Wait for failover to complete
        await asyncio.sleep(5)

        # Check if state is preserved
        preserved_state = self.continuity_manager.trading_state
        state_preserved = preserved_state is not None

        positions_preserved = (
            len(preserved_state.positions) == len(test_positions)
            if state_preserved
            else False
        )
        orders_preserved = (
            len(preserved_state.pending_orders) == len(test_orders)
            if state_preserved
            else False
        )
        account_preserved = (
            preserved_state.account_balance == test_account["balance"]
            if state_preserved
            else False
        )

        return {
            "test_name": "state_preservation",
            "state_preserved": state_preserved,
            "positions_preserved": positions_preserved,
            "orders_preserved": orders_preserved,
            "account_data_preserved": account_preserved,
            "original_positions_count": len(test_positions),
            "original_orders_count": len(test_orders),
            "preserved_positions_count": (
                len(preserved_state.positions) if state_preserved else 0
            ),
            "preserved_orders_count": (
                len(preserved_state.pending_orders) if state_preserved else 0
            ),
            "preservation_score": sum(
                [
                    state_preserved,
                    positions_preserved,
                    orders_preserved,
                    account_preserved,
                ]
            )
            * 25.0,
            "success": state_preserved
            and positions_preserved
            and orders_preserved
            and account_preserved,
        }

    async def _test_failover_chain(self) -> Dict[str, Any]:
        """Test failover chain (primary -> backup1 -> backup2)."""
        chain_results = []

        # Test 1: Primary to Backup1
        logger.info("Testing failover: Primary -> Backup1")
        await self.continuity_manager.set_broker_status(
            "ib_primary", ConnectionStatus.CONNECTED
        )
        await self.continuity_manager.set_active_broker("ib_primary")

        start_time = datetime.utcnow()
        await self.continuity_manager.set_broker_status(
            "ib_primary", ConnectionStatus.DISCONNECTED
        )

        # Wait for failover to backup1
        await asyncio.sleep(3)
        status = self.continuity_manager.get_status_summary()
        execution_time = (datetime.utcnow() - start_time).total_seconds()

        chain_results.append(
            {
                "stage": "primary_to_backup1",
                "source_broker": "ib_primary",
                "target_broker": status["active_broker"],
                "execution_time_seconds": round(execution_time, 2),
                "success": status["active_broker"] == "fxcm_backup1",
                "sla_compliant": execution_time <= self.sla_seconds,
            }
        )

        # Test 2: Backup1 to Backup2
        logger.info("Testing failover: Backup1 -> Backup2")
        start_time = datetime.utcnow()
        await self.continuity_manager.set_broker_status(
            "fxcm_backup1", ConnectionStatus.DISCONNECTED
        )

        # Wait for failover to backup2
        await asyncio.sleep(3)
        status = self.continuity_manager.get_status_summary()
        execution_time = (datetime.utcnow() - start_time).total_seconds()

        chain_results.append(
            {
                "stage": "backup1_to_backup2",
                "source_broker": "fxcm_backup1",
                "target_broker": status["active_broker"],
                "execution_time_seconds": round(execution_time, 2),
                "success": status["active_broker"] == "manual_backup2",
                "sla_compliant": execution_time <= self.sla_seconds,
            }
        )

        # Calculate chain performance
        total_successful = sum(1 for r in chain_results if r["success"])
        total_sla_compliant = sum(1 for r in chain_results if r["sla_compliant"])
        total_execution_time = sum(r["execution_time_seconds"] for r in chain_results)

        return {
            "test_name": "failover_chain",
            "total_stages": len(chain_results),
            "successful_stages": total_successful,
            "sla_compliant_stages": total_sla_compliant,
            "total_execution_time_seconds": round(total_execution_time, 2),
            "average_stage_time_seconds": round(
                total_execution_time / len(chain_results), 2
            ),
            "chain_success_rate_percent": round(
                (total_successful / len(chain_results)) * 100, 1
            ),
            "chain_sla_compliance_percent": round(
                (total_sla_compliant / len(chain_results)) * 100, 1
            ),
            "individual_stages": chain_results,
        }

    async def _test_system_availability(self) -> Dict[str, Any]:
        """Test system availability metrics."""
        metrics = self.continuity_manager.get_recovery_metrics()

        # Simulate some operating time
        operating_time_hours = 24.0  # Simulate 24 hours

        return {
            "test_name": "system_availability",
            "total_failovers": metrics.total_failovers,
            "successful_failovers": metrics.successful_failovers,
            "availability_percentage": round(metrics.availability_percentage, 3),
            "connection_uptime_seconds": round(metrics.connection_uptime_seconds, 1),
            "total_downtime_seconds": round(metrics.total_downtime_seconds, 1),
            "average_recovery_time_seconds": round(metrics.average_recovery_time, 2),
            "max_recovery_time_seconds": round(metrics.max_recovery_time, 2),
            "sla_compliance_rate_percent": round(metrics.sla_compliance_rate, 1),
            "target_availability_percent": 99.9,
            "availability_sla_met": metrics.availability_percentage >= 99.9,
            "recovery_sla_met": metrics.average_recovery_time <= self.sla_seconds,
        }

    async def _test_stress_conditions(self) -> Dict[str, Any]:
        """Test business continuity under stress conditions."""
        stress_results = []

        # Stress Test 1: Rapid successive failovers
        logger.info("Stress test: Rapid successive failovers")
        rapid_failover_times = []

        for i in range(3):
            start_time = datetime.utcnow()

            # Trigger failover
            current_broker = self.continuity_manager.active_broker
            if current_broker == "ib_primary":
                await self.continuity_manager.set_broker_status(
                    "ib_primary", ConnectionStatus.DISCONNECTED
                )
                await asyncio.sleep(2)
                # Restore for next test
                await self.continuity_manager.set_broker_status(
                    "ib_primary", ConnectionStatus.CONNECTED
                )
            else:
                # Trigger manual failover back to primary
                await self.continuity_manager.trigger_manual_failover("ib_primary")

            execution_time = (datetime.utcnow() - start_time).total_seconds()
            rapid_failover_times.append(execution_time)

            await asyncio.sleep(1)  # Brief pause

        avg_rapid_time = sum(rapid_failover_times) / len(rapid_failover_times)

        stress_results.append(
            {
                "stress_type": "rapid_successive_failovers",
                "test_count": len(rapid_failover_times),
                "average_time_seconds": round(avg_rapid_time, 2),
                "max_time_seconds": round(max(rapid_failover_times), 2),
                "all_within_sla": all(
                    t <= self.sla_seconds for t in rapid_failover_times
                ),
            }
        )

        # Stress Test 2: Multiple broker failures
        logger.info("Stress test: Multiple broker failures")
        multi_failure_start = datetime.utcnow()

        # Simulate multiple brokers failing
        await self.continuity_manager.set_broker_status(
            "ib_primary", ConnectionStatus.FAILED
        )
        await self.continuity_manager.set_broker_status(
            "fxcm_backup1", ConnectionStatus.FAILED
        )

        # System should fallback to manual broker
        await asyncio.sleep(3)
        status = self.continuity_manager.get_status_summary()
        multi_failure_time = (datetime.utcnow() - multi_failure_start).total_seconds()

        stress_results.append(
            {
                "stress_type": "multiple_broker_failures",
                "execution_time_seconds": round(multi_failure_time, 2),
                "final_broker": status["active_broker"],
                "recovery_successful": status["active_broker"] == "manual_backup2",
                "within_sla": multi_failure_time
                <= self.sla_seconds * 1.5,  # Allow extra time for extreme scenario
            }
        )

        return {
            "test_name": "stress_testing",
            "stress_scenarios": len(stress_results),
            "scenarios_passed": sum(
                1
                for r in stress_results
                if r.get("recovery_successful", r.get("all_within_sla", False))
            ),
            "individual_stress_tests": stress_results,
            "overall_stress_performance": (
                "PASS"
                if all(
                    r.get("recovery_successful", r.get("all_within_sla", False))
                    for r in stress_results
                )
                else "FAIL"
            ),
        }

    def _calculate_overall_results(
        self, individual_tests: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate overall validation results."""
        # Define test weights
        test_weights = {
            "connection_detection": 15,
            "automatic_failover": 25,
            "state_preservation": 20,
            "sla_compliance": 25,
            "failover_chain": 10,
            "system_availability": 3,
            "stress_testing": 2,
        }

        weighted_score = 0.0
        total_weight = sum(test_weights.values())

        # Calculate weighted scores
        for test_name, weight in test_weights.items():
            if test_name in individual_tests:
                test_result = individual_tests[test_name]

                # Determine test score based on test type
                if test_name == "connection_detection":
                    score = 100 if test_result["sla_met"] else 50
                elif test_name == "automatic_failover":
                    score = test_result["sla_compliance_rate_percent"]
                elif test_name == "state_preservation":
                    score = test_result["preservation_score"]
                elif test_name == "sla_compliance":
                    score = test_result["sla_compliance_rate_percent"]
                elif test_name == "failover_chain":
                    score = test_result["chain_sla_compliance_percent"]
                elif test_name == "system_availability":
                    score = (
                        100
                        if (
                            test_result["availability_sla_met"]
                            and test_result["recovery_sla_met"]
                        )
                        else 50
                    )
                elif test_name == "stress_testing":
                    score = (
                        100
                        if test_result["overall_stress_performance"] == "PASS"
                        else 0
                    )
                else:
                    score = 0

                weighted_score += score * weight / 100.0

        overall_score = (weighted_score / total_weight) * 100

        # Determine overall grade
        if overall_score >= 95:
            grade = "EXCELLENT"
        elif overall_score >= 85:
            grade = "GOOD"
        elif overall_score >= 75:
            grade = "ACCEPTABLE"
        elif overall_score >= 65:
            grade = "MARGINAL"
        else:
            grade = "UNACCEPTABLE"

        return {
            "overall_score": round(overall_score, 1),
            "grade": grade,
            "sla_compliant": overall_score >= 85,
            "production_ready": overall_score >= 90,
            "test_weights": test_weights,
            "weighted_contributions": {
                test_name: round(
                    (
                        individual_tests[test_name].get(
                            "sla_compliance_rate_percent", 0
                        )
                        * weight
                        / total_weight
                    ),
                    1,
                )
                for test_name, weight in test_weights.items()
                if test_name in individual_tests
            },
        }

    def _generate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on test results."""
        recommendations = []

        overall_score = results["overall_results"]["overall_score"]
        individual_tests = results["individual_tests"]

        # Overall performance recommendations
        if overall_score < 90:
            recommendations.append(
                f"Overall performance score ({overall_score:.1f}%) below production threshold (90%). "
                "Review and optimize all business continuity components before live deployment."
            )

        # Connection detection recommendations
        if "connection_detection" in individual_tests:
            detection_result = individual_tests["connection_detection"]
            if not detection_result["sla_met"]:
                recommendations.append(
                    f"Connection detection time ({detection_result['max_detection_time_seconds']:.1f}s) "
                    f"exceeds target (5.0s). Optimize monitoring frequency and alert mechanisms."
                )

        # Failover recommendations
        if "automatic_failover" in individual_tests:
            failover_result = individual_tests["automatic_failover"]
            if failover_result["sla_compliance_rate_percent"] < 95:
                recommendations.append(
                    f"Automatic failover SLA compliance ({failover_result['sla_compliance_rate_percent']:.1f}%) "
                    "below 95% target. Optimize broker switching mechanisms and reduce failover overhead."
                )

        # State preservation recommendations
        if "state_preservation" in individual_tests:
            state_result = individual_tests["state_preservation"]
            if not state_result["success"]:
                recommendations.append(
                    "Trading state preservation failed. Implement robust state capture and restoration mechanisms "
                    "to ensure position and order continuity during failovers."
                )

        # Availability recommendations
        if "system_availability" in individual_tests:
            availability_result = individual_tests["system_availability"]
            if not availability_result["availability_sla_met"]:
                recommendations.append(
                    f"System availability ({availability_result['availability_percentage']:.2f}%) "
                    "below 99.9% target. Improve connection stability and reduce downtime duration."
                )

        # Stress testing recommendations
        if "stress_testing" in individual_tests:
            stress_result = individual_tests["stress_testing"]
            if stress_result["overall_stress_performance"] != "PASS":
                recommendations.append(
                    "System failed stress testing scenarios. Strengthen failover mechanisms to handle "
                    "rapid successive failures and multiple broker outages."
                )

        # Add positive recommendations if performance is good
        if overall_score >= 95:
            recommendations.append(
                "Excellent business continuity performance! System demonstrates robust failover capabilities "
                "and meets all production readiness criteria."
            )
        elif overall_score >= 85:
            recommendations.append(
                "Good business continuity performance. Minor optimizations recommended before production deployment."
            )

        return recommendations

    async def cleanup(self) -> None:
        """Clean up test environment."""
        logger.info("Cleaning up test environment...")
        await self.connection_monitor.stop_monitoring()
        logger.info("Test environment cleanup completed")


def generate_html_report(results: Dict[str, Any], output_file: str) -> None:
    """Generate HTML report from test results."""
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>FXML4 Business Continuity Validation Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
            .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
            .success {{ color: green; }}
            .warning {{ color: orange; }}
            .error {{ color: red; }}
            .metric {{ margin: 10px 0; }}
            .test-result {{ background-color: #f9f9f9; padding: 10px; margin: 10px 0; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>FXML4 Business Continuity Validation Report</h1>
            <p><strong>Generated:</strong> {results['test_timestamp']}</p>
            <p><strong>Test Type:</strong> {results['test_configuration']['test_type']}</p>
            <p><strong>SLA Target:</strong> {results['test_configuration']['sla_seconds']} seconds</p>
        </div>

        <div class="section">
            <h2>Overall Results</h2>
            <div class="metric">
                <strong>Overall Score:</strong>
                <span class="{'success' if results['overall_results']['overall_score'] >= 90 else 'warning' if results['overall_results']['overall_score'] >= 75 else 'error'}">
                    {results['overall_results']['overall_score']:.1f}% ({results['overall_results']['grade']})
                </span>
            </div>
            <div class="metric">
                <strong>Production Ready:</strong>
                <span class="{'success' if results['overall_results']['production_ready'] else 'error'}">
                    {'YES' if results['overall_results']['production_ready'] else 'NO'}
                </span>
            </div>
        </div>

        <div class="section">
            <h2>Individual Test Results</h2>
    """

    # Add individual test results
    for test_name, test_result in results["individual_tests"].items():
        html_content += f"""
        <div class="test-result">
            <h3>{test_name.replace('_', ' ').title()}</h3>
        """

        if test_name == "connection_detection":
            html_content += f"""
            <p><strong>Average Detection Time:</strong> {test_result['average_detection_time_seconds']:.3f}s</p>
            <p><strong>Max Detection Time:</strong> {test_result['max_detection_time_seconds']:.3f}s</p>
            <p><strong>SLA Met:</strong> <span class="{'success' if test_result['sla_met'] else 'error'}">{'YES' if test_result['sla_met'] else 'NO'}</span></p>
            """
        elif test_name == "automatic_failover":
            html_content += f"""
            <p><strong>Success Rate:</strong> {test_result['success_rate_percent']:.1f}%</p>
            <p><strong>SLA Compliance:</strong> {test_result['sla_compliance_rate_percent']:.1f}%</p>
            <p><strong>Average Execution Time:</strong> {test_result['average_execution_time_seconds']:.2f}s</p>
            """
        elif test_name == "sla_compliance":
            html_content += f"""
            <p><strong>SLA Compliance Rate:</strong> {test_result['sla_compliance_rate_percent']:.1f}%</p>
            <p><strong>Average Recovery Time:</strong> {test_result['average_recovery_time_seconds']:.2f}s</p>
            <p><strong>SLA Met:</strong> <span class="{'success' if test_result['sla_met'] else 'error'}">{'YES' if test_result['sla_met'] else 'NO'}</span></p>
            """

        html_content += "</div>"

    # Add recommendations
    html_content += f"""
        </div>

        <div class="section">
            <h2>Recommendations</h2>
            <ul>
    """

    for recommendation in results["recommendations"]:
        html_content += f"<li>{recommendation}</li>"

    html_content += """
            </ul>
        </div>

        <div class="section">
            <h2>Test Configuration</h2>
            <p><strong>Execution Time:</strong> {:.2f} seconds</p>
        </div>
    </body>
    </html>
    """.format(
        results.get("execution_time_seconds", 0)
    )

    with open(output_file, "w") as f:
        f.write(html_content)

    logger.info(f"HTML report generated: {output_file}")


async def main():
    """Main entry point for business continuity validation."""
    parser = argparse.ArgumentParser(description="FXML4 Business Continuity Validation")

    parser.add_argument(
        "--mode",
        choices=["comprehensive", "quick", "stress"],
        default="comprehensive",
        help="Validation mode",
    )
    parser.add_argument(
        "--test-count", type=int, default=15, help="Number of tests to run"
    )
    parser.add_argument(
        "--sla-seconds", type=int, default=30, help="Recovery SLA in seconds"
    )
    parser.add_argument("--output-file", type=str, help="Output HTML report file")

    args = parser.parse_args()

    # Initialize validation system
    proof_system = BusinessContinuityProofSystem(sla_seconds=args.sla_seconds)

    try:
        # Initialize test environment
        await proof_system.initialize_test_environment()

        # Run validation based on mode
        if args.mode == "comprehensive":
            results = await proof_system.run_comprehensive_validation(args.test_count)
        elif args.mode == "quick":
            results = await proof_system.run_comprehensive_validation(
                max(3, args.test_count // 3)
            )
        else:  # stress mode
            results = await proof_system._test_stress_conditions()

        # Display results
        print("\n" + "=" * 80)
        print("FXML4 BUSINESS CONTINUITY VALIDATION RESULTS")
        print("=" * 80)

        if "overall_results" in results:
            overall = results["overall_results"]
            print(
                f"\nOVERALL SCORE: {overall['overall_score']:.1f}% ({overall['grade']})"
            )
            print(f"SLA COMPLIANT: {'YES' if overall['sla_compliant'] else 'NO'}")
            print(f"PRODUCTION READY: {'YES' if overall['production_ready'] else 'NO'}")

        print(
            f"\nExecution Time: {results.get('execution_time_seconds', 0):.1f} seconds"
        )

        # Generate detailed output if requested
        if args.output_file:
            generate_html_report(results, args.output_file)
            print(f"\nDetailed HTML report generated: {args.output_file}")

        # Print recommendations
        if "recommendations" in results and results["recommendations"]:
            print("\nRECOMMENDATIONS:")
            for i, rec in enumerate(results["recommendations"], 1):
                print(f"{i}. {rec}")

        print("\n" + "=" * 80)

        # Set exit code based on results
        if "overall_results" in results:
            exit_code = 0 if results["overall_results"]["production_ready"] else 1
        else:
            exit_code = 1

        return exit_code

    except Exception as e:
        logger.error(f"Validation failed: {e}")
        return 1

    finally:
        await proof_system.cleanup()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
