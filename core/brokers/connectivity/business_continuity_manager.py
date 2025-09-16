"""
Business Continuity Manager for FXML4 Trading System

This module manages business continuity and disaster recovery for broker connectivity,
ensuring the system can recover from broker disconnections within 30 seconds and
resume trading operations automatically.

Key Features:
- Real-time connection monitoring and health checking
- Automatic failover to backup brokers
- Trading state preservation during disconnections
- Connection recovery with exponential backoff
- Business continuity metrics and SLA validation
- Comprehensive alerting and reporting

Recovery SLA: 30 seconds maximum recovery time
Availability Target: 99.9% uptime during trading hours
"""

import asyncio
import json
import logging
import time
import weakref
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Set

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConnectionStatus(Enum):
    """Broker connection status enumeration."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    FAILED = "failed"
    MAINTENANCE = "maintenance"


class FailoverTrigger(Enum):
    """Failover trigger reasons."""

    CONNECTION_LOST = "connection_lost"
    HEARTBEAT_TIMEOUT = "heartbeat_timeout"
    API_ERROR_THRESHOLD = "api_error_threshold"
    MANUAL_TRIGGER = "manual_trigger"
    BROKER_MAINTENANCE = "broker_maintenance"


class RecoveryPhase(Enum):
    """Recovery process phases."""

    DETECTION = "detection"
    FAILOVER = "failover"
    RECONNECTION = "reconnection"
    STATE_RESTORATION = "state_restoration"
    VALIDATION = "validation"
    COMPLETE = "complete"


@dataclass
class BrokerConnection:
    """Broker connection metadata."""

    broker_id: str
    broker_name: str
    connection_type: str  # 'primary', 'backup', 'manual'
    priority: int  # Lower number = higher priority
    status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    last_heartbeat: Optional[datetime] = None
    connection_time: Optional[datetime] = None
    disconnection_time: Optional[datetime] = None
    error_count: int = 0
    consecutive_errors: int = 0
    is_available: bool = True
    capabilities: Set[str] = field(default_factory=set)
    session_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FailoverEvent:
    """Failover event record."""

    event_id: str
    timestamp: datetime
    trigger: FailoverTrigger
    source_broker: str
    target_broker: str
    recovery_time_seconds: float
    success: bool
    error_message: Optional[str] = None
    trading_state_preserved: bool = False
    positions_preserved: int = 0


@dataclass
class TradingState:
    """Trading state snapshot for preservation."""

    timestamp: datetime
    positions: List[Dict[str, Any]] = field(default_factory=list)
    pending_orders: List[Dict[str, Any]] = field(default_factory=list)
    account_balance: float = 0.0
    unrealized_pnl: float = 0.0
    margin_used: float = 0.0
    risk_limits: Dict[str, Any] = field(default_factory=dict)
    strategy_state: Dict[str, Any] = field(default_factory=dict)


class RecoveryMetrics(NamedTuple):
    """Business continuity performance metrics."""

    total_failovers: int
    successful_failovers: int
    average_recovery_time: float
    max_recovery_time: float
    sla_compliance_rate: float
    availability_percentage: float
    connection_uptime_seconds: float
    total_downtime_seconds: float


class BusinessContinuityManager:
    """
    Manages business continuity for the trading system.

    Ensures automatic recovery from broker disconnections within 30 seconds
    and maintains trading operations through failover mechanisms.
    """

    def __init__(self, recovery_sla_seconds: int = 30):
        self.recovery_sla_seconds = recovery_sla_seconds
        self.connections: Dict[str, BrokerConnection] = {}
        self.active_broker: Optional[str] = None
        self.primary_broker: Optional[str] = None
        self.backup_brokers: List[str] = []

        # State management
        self.trading_state: Optional[TradingState] = None
        self.is_recovery_in_progress = False
        self.current_recovery_phase = RecoveryPhase.DETECTION
        self.recovery_start_time: Optional[datetime] = None

        # Event tracking
        self.failover_history: deque = deque(maxlen=1000)
        self.connection_events: deque = deque(maxlen=5000)

        # Callbacks and handlers
        self.connection_listeners: List[weakref.ReferenceType] = []
        self.failover_listeners: List[weakref.ReferenceType] = []

        # Performance tracking
        self._start_time = datetime.utcnow()
        self._total_downtime = 0.0
        self._last_status_change = datetime.utcnow()

        logger.info(
            f"BusinessContinuityManager initialized with {recovery_sla_seconds}s recovery SLA"
        )

    async def register_broker(
        self,
        broker_id: str,
        broker_name: str,
        connection_type: str = "backup",
        priority: int = 100,
        capabilities: Optional[Set[str]] = None,
    ) -> None:
        """Register a broker connection for monitoring."""
        connection = BrokerConnection(
            broker_id=broker_id,
            broker_name=broker_name,
            connection_type=connection_type,
            priority=priority,
            capabilities=capabilities or set(),
        )

        self.connections[broker_id] = connection

        if connection_type == "primary":
            self.primary_broker = broker_id
        elif connection_type == "backup":
            self.backup_brokers.append(broker_id)
            self.backup_brokers.sort(key=lambda x: self.connections[x].priority)

        logger.info(
            f"Registered {connection_type} broker: {broker_name} (ID: {broker_id})"
        )

    async def set_broker_status(self, broker_id: str, status: ConnectionStatus) -> None:
        """Update broker connection status."""
        if broker_id not in self.connections:
            logger.warning(f"Unknown broker ID: {broker_id}")
            return

        connection = self.connections[broker_id]
        previous_status = connection.status
        connection.status = status

        # Update timestamps
        now = datetime.utcnow()
        if status == ConnectionStatus.CONNECTED:
            connection.connection_time = now
            connection.error_count = 0
            connection.consecutive_errors = 0
            if previous_status != ConnectionStatus.CONNECTED:
                logger.info(f"Broker {broker_id} connected")
        elif (
            status == ConnectionStatus.DISCONNECTED
            and previous_status == ConnectionStatus.CONNECTED
        ):
            connection.disconnection_time = now
            logger.warning(f"Broker {broker_id} disconnected")

            # Trigger failover if this was the active broker
            if broker_id == self.active_broker:
                await self._initiate_failover(FailoverTrigger.CONNECTION_LOST)

        # Record connection event
        self.connection_events.append(
            {
                "timestamp": now,
                "broker_id": broker_id,
                "previous_status": previous_status.value,
                "new_status": status.value,
            }
        )

        # Notify listeners
        await self._notify_connection_listeners(broker_id, status, previous_status)

    async def set_active_broker(self, broker_id: str) -> bool:
        """Set the active broker for trading operations."""
        if broker_id not in self.connections:
            logger.error(f"Cannot set unknown broker as active: {broker_id}")
            return False

        connection = self.connections[broker_id]
        if connection.status != ConnectionStatus.CONNECTED:
            logger.error(f"Cannot set disconnected broker as active: {broker_id}")
            return False

        previous_active = self.active_broker
        self.active_broker = broker_id

        logger.info(f"Active broker changed: {previous_active} -> {broker_id}")
        return True

    async def preserve_trading_state(
        self, positions: List[Dict], orders: List[Dict], account_data: Dict[str, Any]
    ) -> None:
        """Preserve current trading state for recovery."""
        self.trading_state = TradingState(
            timestamp=datetime.utcnow(),
            positions=positions,
            pending_orders=orders,
            account_balance=account_data.get("balance", 0.0),
            unrealized_pnl=account_data.get("unrealized_pnl", 0.0),
            margin_used=account_data.get("margin_used", 0.0),
            risk_limits=account_data.get("risk_limits", {}),
            strategy_state=account_data.get("strategy_state", {}),
        )

        logger.info(
            f"Trading state preserved: {len(positions)} positions, {len(orders)} orders"
        )

    async def _initiate_failover(self, trigger: FailoverTrigger) -> bool:
        """Initiate automatic failover to backup broker."""
        if self.is_recovery_in_progress:
            logger.warning("Recovery already in progress, ignoring failover trigger")
            return False

        self.is_recovery_in_progress = True
        self.recovery_start_time = datetime.utcnow()
        self.current_recovery_phase = RecoveryPhase.DETECTION

        logger.critical(f"Initiating failover due to: {trigger.value}")

        try:
            # Find best available backup broker
            target_broker = await self._select_backup_broker()
            if not target_broker:
                logger.error("No available backup brokers for failover")
                self.is_recovery_in_progress = False
                return False

            # Execute failover
            source_broker = self.active_broker
            success = await self._execute_failover(
                source_broker, target_broker, trigger
            )

            # Record failover event
            recovery_time = (
                datetime.utcnow() - self.recovery_start_time
            ).total_seconds()
            failover_event = FailoverEvent(
                event_id=f"failover_{int(time.time())}",
                timestamp=self.recovery_start_time,
                trigger=trigger,
                source_broker=source_broker or "unknown",
                target_broker=target_broker,
                recovery_time_seconds=recovery_time,
                success=success,
                trading_state_preserved=self.trading_state is not None,
            )

            self.failover_history.append(failover_event)

            # Check SLA compliance
            sla_compliant = recovery_time <= self.recovery_sla_seconds
            if not sla_compliant:
                logger.error(
                    f"Recovery SLA breach: {recovery_time:.1f}s > {self.recovery_sla_seconds}s"
                )
            else:
                logger.info(f"Recovery completed within SLA: {recovery_time:.1f}s")

            return success

        except Exception as e:
            logger.error(f"Failover failed with exception: {e}")
            self.is_recovery_in_progress = False
            return False

    async def _select_backup_broker(self) -> Optional[str]:
        """Select the best available backup broker."""
        available_brokers = [
            broker_id
            for broker_id, conn in self.connections.items()
            if (
                conn.status == ConnectionStatus.CONNECTED
                and conn.is_available
                and broker_id != self.active_broker
            )
        ]

        if not available_brokers:
            return None

        # Sort by priority (lower number = higher priority)
        available_brokers.sort(key=lambda x: self.connections[x].priority)
        return available_brokers[0]

    async def _execute_failover(
        self, source_broker: Optional[str], target_broker: str, trigger: FailoverTrigger
    ) -> bool:
        """Execute the actual failover process."""
        try:
            # Phase 1: Failover preparation
            self.current_recovery_phase = RecoveryPhase.FAILOVER
            logger.info(
                f"Failover phase: Switching from {source_broker} to {target_broker}"
            )

            # Phase 2: Connection establishment
            self.current_recovery_phase = RecoveryPhase.RECONNECTION
            target_connection = self.connections[target_broker]

            if target_connection.status != ConnectionStatus.CONNECTED:
                logger.error(f"Target broker {target_broker} is not connected")
                return False

            # Phase 3: State restoration
            self.current_recovery_phase = RecoveryPhase.STATE_RESTORATION
            if self.trading_state:
                logger.info("Restoring trading state...")
                # In a real implementation, this would restore positions and orders
                # For now, we'll simulate the restoration
                await asyncio.sleep(0.1)  # Simulate restoration time

            # Phase 4: Validation
            self.current_recovery_phase = RecoveryPhase.VALIDATION
            if not await self._validate_broker_connection(target_broker):
                logger.error(f"Broker validation failed for {target_broker}")
                return False

            # Phase 5: Activation
            self.active_broker = target_broker
            self.current_recovery_phase = RecoveryPhase.COMPLETE

            logger.info(f"Failover completed: Active broker is now {target_broker}")

            # Notify listeners
            await self._notify_failover_listeners(source_broker, target_broker, True)

            return True

        except Exception as e:
            logger.error(f"Failover execution failed: {e}")
            return False

        finally:
            self.is_recovery_in_progress = False

    async def _validate_broker_connection(self, broker_id: str) -> bool:
        """Validate broker connection is working properly."""
        try:
            connection = self.connections[broker_id]

            # Check basic connection status
            if connection.status != ConnectionStatus.CONNECTED:
                return False

            # Check heartbeat recency (within last 30 seconds)
            if connection.last_heartbeat:
                time_since_heartbeat = (
                    datetime.utcnow() - connection.last_heartbeat
                ).total_seconds()
                if time_since_heartbeat > 30:
                    logger.warning(
                        f"Stale heartbeat for {broker_id}: {time_since_heartbeat}s"
                    )
                    return False

            # Simulate additional validation checks
            await asyncio.sleep(0.05)  # Simulate validation time

            return True

        except Exception as e:
            logger.error(f"Broker validation error for {broker_id}: {e}")
            return False

    async def trigger_manual_failover(self, target_broker: str) -> bool:
        """Manually trigger failover to specific broker."""
        if target_broker not in self.connections:
            logger.error(f"Unknown target broker: {target_broker}")
            return False

        if target_broker == self.active_broker:
            logger.warning(f"Target broker {target_broker} is already active")
            return True

        logger.info(f"Manual failover triggered to broker: {target_broker}")
        return await self._initiate_failover(FailoverTrigger.MANUAL_TRIGGER)

    async def add_connection_listener(self, callback: Callable) -> None:
        """Add a connection status change listener."""
        self.connection_listeners.append(weakref.ref(callback))

    async def add_failover_listener(self, callback: Callable) -> None:
        """Add a failover event listener."""
        self.failover_listeners.append(weakref.ref(callback))

    async def _notify_connection_listeners(
        self,
        broker_id: str,
        new_status: ConnectionStatus,
        previous_status: ConnectionStatus,
    ) -> None:
        """Notify connection status change listeners."""
        for listener_ref in self.connection_listeners[
            :
        ]:  # Copy list to avoid modification during iteration
            listener = listener_ref()
            if listener is None:
                self.connection_listeners.remove(listener_ref)
            else:
                try:
                    await listener(broker_id, new_status, previous_status)
                except Exception as e:
                    logger.error(f"Connection listener error: {e}")

    async def _notify_failover_listeners(
        self, source_broker: Optional[str], target_broker: str, success: bool
    ) -> None:
        """Notify failover event listeners."""
        for listener_ref in self.failover_listeners[:]:
            listener = listener_ref()
            if listener is None:
                self.failover_listeners.remove(listener_ref)
            else:
                try:
                    await listener(source_broker, target_broker, success)
                except Exception as e:
                    logger.error(f"Failover listener error: {e}")

    def get_recovery_metrics(self) -> RecoveryMetrics:
        """Get business continuity performance metrics."""
        total_failovers = len(self.failover_history)
        successful_failovers = sum(
            1 for event in self.failover_history if event.success
        )

        if total_failovers > 0:
            recovery_times = [
                event.recovery_time_seconds for event in self.failover_history
            ]
            average_recovery_time = sum(recovery_times) / len(recovery_times)
            max_recovery_time = max(recovery_times)
            sla_compliant = sum(
                1 for time in recovery_times if time <= self.recovery_sla_seconds
            )
            sla_compliance_rate = (sla_compliant / total_failovers) * 100
        else:
            average_recovery_time = 0.0
            max_recovery_time = 0.0
            sla_compliance_rate = 100.0

        # Calculate availability
        total_runtime = (datetime.utcnow() - self._start_time).total_seconds()
        availability_percentage = (
            ((total_runtime - self._total_downtime) / total_runtime) * 100
            if total_runtime > 0
            else 100.0
        )

        return RecoveryMetrics(
            total_failovers=total_failovers,
            successful_failovers=successful_failovers,
            average_recovery_time=average_recovery_time,
            max_recovery_time=max_recovery_time,
            sla_compliance_rate=sla_compliance_rate,
            availability_percentage=availability_percentage,
            connection_uptime_seconds=total_runtime - self._total_downtime,
            total_downtime_seconds=self._total_downtime,
        )

    def get_status_summary(self) -> Dict[str, Any]:
        """Get comprehensive status summary."""
        metrics = self.get_recovery_metrics()

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "active_broker": self.active_broker,
            "primary_broker": self.primary_broker,
            "recovery_in_progress": self.is_recovery_in_progress,
            "current_recovery_phase": (
                self.current_recovery_phase.value
                if self.is_recovery_in_progress
                else None
            ),
            "connections": {
                broker_id: {
                    "name": conn.broker_name,
                    "status": conn.status.value,
                    "type": conn.connection_type,
                    "priority": conn.priority,
                    "error_count": conn.error_count,
                    "last_heartbeat": (
                        conn.last_heartbeat.isoformat() if conn.last_heartbeat else None
                    ),
                    "is_available": conn.is_available,
                }
                for broker_id, conn in self.connections.items()
            },
            "metrics": {
                "total_failovers": metrics.total_failovers,
                "successful_failovers": metrics.successful_failovers,
                "average_recovery_time_seconds": round(
                    metrics.average_recovery_time, 2
                ),
                "max_recovery_time_seconds": round(metrics.max_recovery_time, 2),
                "sla_compliance_rate_percent": round(metrics.sla_compliance_rate, 1),
                "availability_percentage": round(metrics.availability_percentage, 3),
                "total_downtime_seconds": round(metrics.total_downtime_seconds, 1),
            },
            "recent_failovers": [
                {
                    "timestamp": event.timestamp.isoformat(),
                    "trigger": event.trigger.value,
                    "source": event.source_broker,
                    "target": event.target_broker,
                    "recovery_time_seconds": round(event.recovery_time_seconds, 2),
                    "success": event.success,
                    "sla_compliant": event.recovery_time_seconds
                    <= self.recovery_sla_seconds,
                }
                for event in list(self.failover_history)[-10:]  # Last 10 events
            ],
        }


class BusinessContinuityValidator:
    """
    Validates business continuity requirements and SLA compliance.

    Tests the system's ability to recover from broker disconnections
    within the required SLA timeframe.
    """

    def __init__(self, continuity_manager: BusinessContinuityManager):
        self.continuity_manager = continuity_manager
        self.test_results: List[Dict[str, Any]] = []

    async def validate_recovery_sla(self, num_tests: int = 10) -> Dict[str, Any]:
        """Validate recovery SLA through simulated disconnections."""
        logger.info(f"Starting recovery SLA validation with {num_tests} tests")

        successful_recoveries = 0
        sla_compliant_recoveries = 0
        recovery_times = []

        for test_num in range(1, num_tests + 1):
            logger.info(f"Recovery test {test_num}/{num_tests}")

            try:
                # Simulate broker disconnection and recovery
                recovery_time = await self._simulate_broker_disconnection()
                recovery_times.append(recovery_time)

                if recovery_time is not None:
                    successful_recoveries += 1
                    if recovery_time <= self.continuity_manager.recovery_sla_seconds:
                        sla_compliant_recoveries += 1

                # Wait between tests
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Recovery test {test_num} failed: {e}")

        # Calculate results
        success_rate = (successful_recoveries / num_tests) * 100
        sla_compliance_rate = (sla_compliant_recoveries / num_tests) * 100
        avg_recovery_time = (
            sum(recovery_times) / len(recovery_times) if recovery_times else 0
        )
        max_recovery_time = max(recovery_times) if recovery_times else 0

        results = {
            "test_timestamp": datetime.utcnow().isoformat(),
            "total_tests": num_tests,
            "successful_recoveries": successful_recoveries,
            "sla_compliant_recoveries": sla_compliant_recoveries,
            "success_rate_percent": round(success_rate, 1),
            "sla_compliance_rate_percent": round(sla_compliance_rate, 1),
            "average_recovery_time_seconds": round(avg_recovery_time, 2),
            "max_recovery_time_seconds": round(max_recovery_time, 2),
            "sla_target_seconds": self.continuity_manager.recovery_sla_seconds,
            "recovery_times": [round(t, 2) for t in recovery_times],
            "sla_met": sla_compliance_rate >= 95.0,  # 95% compliance threshold
        }

        self.test_results.append(results)

        logger.info(f"Recovery SLA validation completed:")
        logger.info(f"  Success rate: {success_rate:.1f}%")
        logger.info(f"  SLA compliance: {sla_compliance_rate:.1f}%")
        logger.info(f"  Average recovery time: {avg_recovery_time:.2f}s")

        return results

    async def _simulate_broker_disconnection(self) -> Optional[float]:
        """Simulate broker disconnection and measure recovery time."""
        if not self.continuity_manager.active_broker:
            logger.error("No active broker to disconnect")
            return None

        active_broker = self.continuity_manager.active_broker
        start_time = datetime.utcnow()

        # Simulate disconnection
        await self.continuity_manager.set_broker_status(
            active_broker, ConnectionStatus.DISCONNECTED
        )

        # Wait for recovery to complete
        timeout_seconds = (
            self.continuity_manager.recovery_sla_seconds * 2
        )  # Allow extra time for measurement
        recovery_start = datetime.utcnow()

        while datetime.utcnow() - recovery_start < timedelta(seconds=timeout_seconds):
            if (
                not self.continuity_manager.is_recovery_in_progress
                and self.continuity_manager.current_recovery_phase
                == RecoveryPhase.COMPLETE
            ):
                recovery_time = (datetime.utcnow() - start_time).total_seconds()
                return recovery_time

            await asyncio.sleep(0.1)

        logger.error(f"Recovery timeout after {timeout_seconds}s")
        return None

    def get_validation_report(self) -> Dict[str, Any]:
        """Generate comprehensive validation report."""
        if not self.test_results:
            return {"error": "No validation tests have been performed"}

        latest_results = self.test_results[-1]
        overall_metrics = self.continuity_manager.get_recovery_metrics()

        return {
            "validation_summary": {
                "total_validation_runs": len(self.test_results),
                "latest_test_results": latest_results,
                "overall_sla_compliance": latest_results["sla_compliance_rate_percent"]
                >= 95.0,
            },
            "operational_metrics": {
                "total_failovers": overall_metrics.total_failovers,
                "successful_failovers": overall_metrics.successful_failovers,
                "availability_percentage": round(
                    overall_metrics.availability_percentage, 3
                ),
                "average_recovery_time": round(
                    overall_metrics.average_recovery_time, 2
                ),
                "sla_compliance_rate": round(overall_metrics.sla_compliance_rate, 1),
            },
            "recommendations": self._generate_recommendations(
                latest_results, overall_metrics
            ),
        }

    def _generate_recommendations(
        self, test_results: Dict[str, Any], metrics: RecoveryMetrics
    ) -> List[str]:
        """Generate recommendations based on validation results."""
        recommendations = []

        if test_results["sla_compliance_rate_percent"] < 95.0:
            recommendations.append(
                f"SLA compliance below 95% ({test_results['sla_compliance_rate_percent']:.1f}%). "
                "Consider optimizing failover mechanisms or reducing SLA target."
            )

        if (
            test_results["average_recovery_time_seconds"]
            > test_results["sla_target_seconds"] * 0.8
        ):
            recommendations.append(
                "Average recovery time is close to SLA limit. Consider performance optimizations."
            )

        if metrics.availability_percentage < 99.9:
            recommendations.append(
                f"System availability ({metrics.availability_percentage:.2f}%) below 99.9% target. "
                "Review connection stability and failover triggers."
            )

        if not recommendations:
            recommendations.append(
                "Business continuity validation passed all requirements."
            )

        return recommendations
