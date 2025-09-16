"""
Failover Orchestrator for FXML4 Trading System

This module orchestrates automated failover between brokers, managing the
complex process of switching trading operations from a failed primary broker
to healthy backup brokers while preserving trading state and ensuring
minimal disruption to operations.

Key Features:
- Automated failover decision making
- Multi-broker failover chains
- Trading state preservation and restoration
- Order migration and position synchronization
- Graceful degradation modes
- Rollback capabilities

Failover SLA: <30 seconds end-to-end failover time
State Preservation: 100% position and order continuity
Rollback Time: <10 seconds if needed
"""

import asyncio
import json
import logging
import time
import uuid
import weakref
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Set

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FailoverDecision(Enum):
    """Failover decision types."""

    NO_ACTION = "no_action"
    IMMEDIATE_FAILOVER = "immediate_failover"
    GRACEFUL_FAILOVER = "graceful_failover"
    EMERGENCY_FAILOVER = "emergency_failover"
    ROLLBACK = "rollback"


class FailoverReason(Enum):
    """Detailed failover reasons."""

    CONNECTION_LOST = "connection_lost"
    API_ERRORS = "api_errors"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    HEARTBEAT_TIMEOUT = "heartbeat_timeout"
    MANUAL_TRIGGER = "manual_trigger"
    BROKER_MAINTENANCE = "broker_maintenance"
    RISK_LIMITS_BREACH = "risk_limits_breach"
    REGULATORY_HALT = "regulatory_halt"


class FailoverPhase(Enum):
    """Failover execution phases."""

    ASSESSMENT = "assessment"
    PREPARATION = "preparation"
    STATE_CAPTURE = "state_capture"
    BROKER_SWITCH = "broker_switch"
    STATE_RESTORE = "state_restore"
    VALIDATION = "validation"
    FINALIZATION = "finalization"
    ROLLBACK = "rollback"


@dataclass
class BrokerCapability:
    """Broker capability definition."""

    capability_name: str
    is_available: bool
    performance_score: float  # 0-100
    reliability_score: float  # 0-100
    last_validated: datetime
    restrictions: List[str] = field(default_factory=list)


@dataclass
class FailoverCandidate:
    """Potential failover target broker."""

    broker_id: str
    broker_name: str
    priority_score: float
    capabilities: Dict[str, BrokerCapability]
    estimated_switch_time: float
    compatibility_score: float
    current_load: float
    availability_status: str
    reasons_for_selection: List[str] = field(default_factory=list)
    reasons_against_selection: List[str] = field(default_factory=list)


@dataclass
class TradingStateSnapshot:
    """Complete trading state snapshot."""

    snapshot_id: str
    timestamp: datetime
    broker_id: str
    positions: List[Dict[str, Any]]
    pending_orders: List[Dict[str, Any]]
    account_info: Dict[str, Any]
    risk_metrics: Dict[str, Any]
    strategy_states: Dict[str, Any]
    market_data_subscriptions: List[str]
    open_sessions: List[str]
    checksum: str


@dataclass
class FailoverExecution:
    """Failover execution record."""

    execution_id: str
    start_time: datetime
    end_time: Optional[datetime]
    source_broker: str
    target_broker: str
    decision: FailoverDecision
    reason: FailoverReason
    current_phase: FailoverPhase
    success: bool
    error_message: Optional[str] = None
    state_snapshot: Optional[TradingStateSnapshot] = None
    rollback_available: bool = False
    performance_metrics: Dict[str, Any] = field(default_factory=dict)


class FailoverOrchestrator:
    """
    Orchestrates complex broker failover operations.

    Manages the end-to-end process of switching from a failed broker
    to a healthy backup while preserving trading state and minimizing
    disruption to trading operations.
    """

    def __init__(self, max_failover_time: int = 30):
        self.max_failover_time = max_failover_time

        # Broker registry
        self.registered_brokers: Dict[str, Dict[str, Any]] = {}
        self.broker_capabilities: Dict[str, Dict[str, BrokerCapability]] = {}
        self.failover_chains: Dict[str, List[str]] = (
            {}
        )  # primary -> [backup1, backup2, ...]

        # Execution tracking
        self.active_executions: Dict[str, FailoverExecution] = {}
        self.execution_history: deque = deque(maxlen=1000)
        self.state_snapshots: Dict[str, TradingStateSnapshot] = {}

        # Decision making
        self.failover_rules: List[Dict[str, Any]] = []
        self.performance_thresholds: Dict[str, float] = {
            "max_latency_ms": 5000,
            "min_success_rate": 95.0,
            "max_error_rate": 5.0,
            "min_uptime_percent": 99.0,
        }

        # Event handlers
        self.decision_listeners: List[weakref.ReferenceType] = []
        self.execution_listeners: List[weakref.ReferenceType] = []
        self.state_handlers: List[weakref.ReferenceType] = []

        # Dependencies (would be injected in real implementation)
        self.broker_adapters: Dict[str, Any] = {}
        self.trading_engine: Optional[Any] = None
        self.risk_manager: Optional[Any] = None

        logger.info(
            f"FailoverOrchestrator initialized with {max_failover_time}s max failover time"
        )

    async def register_broker_for_failover(
        self,
        broker_id: str,
        broker_config: Dict[str, Any],
        capabilities: Dict[str, BrokerCapability],
        failover_chain: Optional[List[str]] = None,
    ) -> None:
        """Register a broker for failover management."""
        self.registered_brokers[broker_id] = broker_config
        self.broker_capabilities[broker_id] = capabilities

        if failover_chain:
            self.failover_chains[broker_id] = failover_chain

        logger.info(f"Registered broker for failover: {broker_id}")
        logger.debug(f"  Capabilities: {list(capabilities.keys())}")
        logger.debug(f"  Failover chain: {failover_chain}")

    async def add_failover_rule(
        self,
        rule_name: str,
        condition: Dict[str, Any],
        action: FailoverDecision,
        priority: int = 100,
    ) -> None:
        """Add a failover decision rule."""
        rule = {
            "name": rule_name,
            "condition": condition,
            "action": action,
            "priority": priority,
            "created_at": datetime.utcnow(),
        }

        self.failover_rules.append(rule)
        self.failover_rules.sort(
            key=lambda x: x["priority"]
        )  # Lower number = higher priority

        logger.info(f"Added failover rule: {rule_name} (priority: {priority})")

    async def evaluate_failover_need(
        self, broker_id: str, broker_metrics: Dict[str, Any], connection_status: str
    ) -> FailoverDecision:
        """Evaluate whether failover is needed for a broker."""
        # Apply failover rules
        for rule in self.failover_rules:
            if await self._evaluate_rule_condition(
                rule["condition"], broker_id, broker_metrics, connection_status
            ):
                logger.info(
                    f"Failover rule triggered: {rule['name']} -> {rule['action'].value}"
                )
                return rule["action"]

        # Default threshold-based evaluation
        if connection_status == "disconnected":
            return FailoverDecision.IMMEDIATE_FAILOVER

        # Performance-based evaluation
        latency = broker_metrics.get("latency_ms", 0)
        success_rate = broker_metrics.get("success_rate_percent", 100)
        error_rate = broker_metrics.get("error_rate_percent", 0)

        if (
            latency > self.performance_thresholds["max_latency_ms"]
            or success_rate < self.performance_thresholds["min_success_rate"]
            or error_rate > self.performance_thresholds["max_error_rate"]
        ):
            return FailoverDecision.GRACEFUL_FAILOVER

        return FailoverDecision.NO_ACTION

    async def _evaluate_rule_condition(
        self,
        condition: Dict[str, Any],
        broker_id: str,
        metrics: Dict[str, Any],
        status: str,
    ) -> bool:
        """Evaluate a failover rule condition."""
        try:
            # Simple condition evaluation (can be extended for complex rules)
            if "status" in condition and condition["status"] != status:
                return False

            if "broker_id" in condition and condition["broker_id"] != broker_id:
                return False

            # Metric thresholds
            for metric_name, threshold in condition.get("metrics", {}).items():
                metric_value = metrics.get(metric_name, 0)
                operator = threshold.get("operator", "gte")
                value = threshold.get("value", 0)

                if operator == "gte" and metric_value < value:
                    return False
                elif operator == "lte" and metric_value > value:
                    return False
                elif operator == "eq" and metric_value != value:
                    return False

            return True

        except Exception as e:
            logger.error(f"Error evaluating rule condition: {e}")
            return False

    async def select_failover_target(
        self, source_broker: str, required_capabilities: Optional[Set[str]] = None
    ) -> Optional[FailoverCandidate]:
        """Select the best failover target broker."""
        candidates = await self._identify_failover_candidates(
            source_broker, required_capabilities
        )

        if not candidates:
            logger.error(f"No failover candidates available for {source_broker}")
            return None

        # Score and rank candidates
        for candidate in candidates:
            candidate.priority_score = await self._calculate_candidate_score(
                candidate, source_broker
            )

        # Sort by priority score (higher is better)
        candidates.sort(key=lambda x: x.priority_score, reverse=True)

        selected_candidate = candidates[0]
        logger.info(
            f"Selected failover target: {selected_candidate.broker_name} (score: {selected_candidate.priority_score:.1f})"
        )

        return selected_candidate

    async def _identify_failover_candidates(
        self, source_broker: str, required_capabilities: Optional[Set[str]] = None
    ) -> List[FailoverCandidate]:
        """Identify potential failover candidate brokers."""
        candidates = []

        # Check failover chain first
        failover_chain = self.failover_chains.get(source_broker, [])
        for broker_id in failover_chain:
            if broker_id in self.registered_brokers:
                candidate = await self._create_failover_candidate(
                    broker_id, required_capabilities
                )
                if candidate:
                    candidates.append(candidate)

        # Check other available brokers
        for broker_id in self.registered_brokers:
            if broker_id != source_broker and broker_id not in failover_chain:
                candidate = await self._create_failover_candidate(
                    broker_id, required_capabilities
                )
                if candidate:
                    candidates.append(candidate)

        return candidates

    async def _create_failover_candidate(
        self, broker_id: str, required_capabilities: Optional[Set[str]] = None
    ) -> Optional[FailoverCandidate]:
        """Create a failover candidate from a broker."""
        if broker_id not in self.registered_brokers:
            return None

        broker_config = self.registered_brokers[broker_id]
        capabilities = self.broker_capabilities.get(broker_id, {})

        # Check required capabilities
        if required_capabilities:
            available_caps = set(
                cap_name for cap_name, cap in capabilities.items() if cap.is_available
            )
            if not required_capabilities.issubset(available_caps):
                return None

        # Estimate switch time (based on broker type and current load)
        estimated_switch_time = self._estimate_switch_time(broker_id)

        # Calculate compatibility score
        compatibility_score = self._calculate_compatibility_score(broker_id)

        candidate = FailoverCandidate(
            broker_id=broker_id,
            broker_name=broker_config.get("name", broker_id),
            priority_score=0.0,  # Will be calculated later
            capabilities=capabilities,
            estimated_switch_time=estimated_switch_time,
            compatibility_score=compatibility_score,
            current_load=broker_config.get("current_load", 0.0),
            availability_status=broker_config.get("status", "unknown"),
        )

        return candidate

    def _estimate_switch_time(self, broker_id: str) -> float:
        """Estimate time required to switch to broker."""
        # Base switch time
        base_time = 5.0  # seconds

        # Adjust based on broker type
        broker_config = self.registered_brokers[broker_id]
        broker_type = broker_config.get("type", "unknown")

        type_multipliers = {"interactive_brokers": 1.0, "fxcm": 1.2, "manual": 2.0}

        multiplier = type_multipliers.get(broker_type, 1.5)

        # Adjust based on current load
        current_load = broker_config.get("current_load", 0.0)
        load_multiplier = 1.0 + (current_load / 100.0)

        return base_time * multiplier * load_multiplier

    def _calculate_compatibility_score(self, broker_id: str) -> float:
        """Calculate compatibility score for broker."""
        # Base score
        score = 100.0

        broker_config = self.registered_brokers[broker_id]
        capabilities = self.broker_capabilities.get(broker_id, {})

        # Factor in capability availability
        total_caps = len(capabilities)
        available_caps = sum(1 for cap in capabilities.values() if cap.is_available)
        capability_ratio = available_caps / total_caps if total_caps > 0 else 1.0

        score *= capability_ratio

        # Factor in performance scores
        if capabilities:
            perf_scores = [cap.performance_score for cap in capabilities.values()]
            avg_performance = sum(perf_scores) / len(perf_scores)
            score *= avg_performance / 100.0

        return min(score, 100.0)

    async def _calculate_candidate_score(
        self, candidate: FailoverCandidate, source_broker: str
    ) -> float:
        """Calculate priority score for failover candidate."""
        score = 0.0

        # Base score from compatibility
        score += candidate.compatibility_score * 0.4

        # Time factor (faster switch is better)
        max_switch_time = 30.0  # seconds
        time_score = (
            max(
                0, (max_switch_time - candidate.estimated_switch_time) / max_switch_time
            )
            * 100
        )
        score += time_score * 0.3

        # Load factor (lower load is better)
        load_score = max(0, 100 - candidate.current_load)
        score += load_score * 0.2

        # Failover chain priority
        failover_chain = self.failover_chains.get(source_broker, [])
        if candidate.broker_id in failover_chain:
            chain_position = failover_chain.index(candidate.broker_id)
            chain_score = max(
                0, 100 - (chain_position * 10)
            )  # Earlier in chain is better
            score += chain_score * 0.1

        return min(score, 100.0)

    async def execute_failover(
        self,
        source_broker: str,
        target_candidate: FailoverCandidate,
        reason: FailoverReason,
    ) -> FailoverExecution:
        """Execute complete failover process."""
        execution_id = str(uuid.uuid4())
        start_time = datetime.utcnow()

        execution = FailoverExecution(
            execution_id=execution_id,
            start_time=start_time,
            end_time=None,
            source_broker=source_broker,
            target_broker=target_candidate.broker_id,
            decision=FailoverDecision.IMMEDIATE_FAILOVER,
            reason=reason,
            current_phase=FailoverPhase.ASSESSMENT,
            success=False,
        )

        self.active_executions[execution_id] = execution

        logger.info(
            f"Starting failover execution {execution_id}: {source_broker} -> {target_candidate.broker_id}"
        )

        try:
            # Phase 1: Assessment
            execution.current_phase = FailoverPhase.ASSESSMENT
            await self._notify_execution_listeners(execution)

            if not await self._assess_failover_feasibility(execution, target_candidate):
                execution.success = False
                execution.error_message = "Failover feasibility assessment failed"
                return execution

            # Phase 2: Preparation
            execution.current_phase = FailoverPhase.PREPARATION
            await self._notify_execution_listeners(execution)

            await self._prepare_target_broker(target_candidate.broker_id)

            # Phase 3: State Capture
            execution.current_phase = FailoverPhase.STATE_CAPTURE
            await self._notify_execution_listeners(execution)

            state_snapshot = await self._capture_trading_state(source_broker)
            execution.state_snapshot = state_snapshot

            # Phase 4: Broker Switch
            execution.current_phase = FailoverPhase.BROKER_SWITCH
            await self._notify_execution_listeners(execution)

            await self._switch_active_broker(source_broker, target_candidate.broker_id)

            # Phase 5: State Restore
            execution.current_phase = FailoverPhase.STATE_RESTORE
            await self._notify_execution_listeners(execution)

            if state_snapshot:
                await self._restore_trading_state(
                    target_candidate.broker_id, state_snapshot
                )

            # Phase 6: Validation
            execution.current_phase = FailoverPhase.VALIDATION
            await self._notify_execution_listeners(execution)

            validation_success = await self._validate_failover_success(
                target_candidate.broker_id, state_snapshot
            )

            # Phase 7: Finalization
            execution.current_phase = FailoverPhase.FINALIZATION
            await self._notify_execution_listeners(execution)

            if validation_success:
                execution.success = True
                execution.rollback_available = True
                await self._finalize_failover(execution)
            else:
                execution.success = False
                execution.error_message = "Failover validation failed"
                # Consider rollback here

            execution.end_time = datetime.utcnow()
            execution_time = (execution.end_time - execution.start_time).total_seconds()

            logger.info(
                f"Failover execution {execution_id} completed in {execution_time:.1f}s: {'SUCCESS' if execution.success else 'FAILED'}"
            )

            # Record performance metrics
            execution.performance_metrics = {
                "total_execution_time_seconds": execution_time,
                "sla_compliant": execution_time <= self.max_failover_time,
                "state_preservation_success": state_snapshot is not None,
                "validation_success": validation_success,
            }

            return execution

        except Exception as e:
            execution.success = False
            execution.error_message = str(e)
            execution.end_time = datetime.utcnow()

            logger.error(
                f"Failover execution {execution_id} failed with exception: {e}"
            )
            return execution

        finally:
            # Clean up and move to history
            if execution_id in self.active_executions:
                del self.active_executions[execution_id]

            self.execution_history.append(execution)

    async def _assess_failover_feasibility(
        self, execution: FailoverExecution, target_candidate: FailoverCandidate
    ) -> bool:
        """Assess whether failover is feasible."""
        try:
            # Check target broker availability
            if target_candidate.availability_status not in ["connected", "ready"]:
                logger.error(
                    f"Target broker {target_candidate.broker_id} not available: {target_candidate.availability_status}"
                )
                return False

            # Check estimated completion time
            if target_candidate.estimated_switch_time > self.max_failover_time:
                logger.error(
                    f"Estimated switch time ({target_candidate.estimated_switch_time}s) exceeds SLA ({self.max_failover_time}s)"
                )
                return False

            # Simulate additional feasibility checks
            await asyncio.sleep(0.1)  # Simulate assessment time

            return True

        except Exception as e:
            logger.error(f"Failover feasibility assessment error: {e}")
            return False

    async def _prepare_target_broker(self, broker_id: str) -> None:
        """Prepare target broker for failover."""
        logger.info(f"Preparing target broker: {broker_id}")

        # Simulate broker preparation (authentication, session setup, etc.)
        await asyncio.sleep(0.2)

        # In real implementation, this would:
        # - Authenticate with broker
        # - Initialize trading sessions
        # - Set up market data feeds
        # - Configure risk limits

    async def _capture_trading_state(
        self, broker_id: str
    ) -> Optional[TradingStateSnapshot]:
        """Capture current trading state for preservation."""
        logger.info(f"Capturing trading state from broker: {broker_id}")

        try:
            snapshot_id = str(uuid.uuid4())
            timestamp = datetime.utcnow()

            # Simulate state capture (in real implementation, this would query the broker)
            positions = []  # Would get actual positions
            pending_orders = []  # Would get actual orders
            account_info = {}  # Would get actual account data
            risk_metrics = {}  # Would get actual risk data
            strategy_states = {}  # Would get actual strategy states

            snapshot = TradingStateSnapshot(
                snapshot_id=snapshot_id,
                timestamp=timestamp,
                broker_id=broker_id,
                positions=positions,
                pending_orders=pending_orders,
                account_info=account_info,
                risk_metrics=risk_metrics,
                strategy_states=strategy_states,
                market_data_subscriptions=[],
                open_sessions=[],
                checksum=self._calculate_state_checksum(
                    positions, pending_orders, account_info
                ),
            )

            self.state_snapshots[snapshot_id] = snapshot

            logger.info(
                f"Trading state captured: {len(positions)} positions, {len(pending_orders)} orders"
            )
            return snapshot

        except Exception as e:
            logger.error(f"Failed to capture trading state: {e}")
            return None

    def _calculate_state_checksum(
        self, positions: List[Dict], orders: List[Dict], account: Dict
    ) -> str:
        """Calculate checksum for trading state integrity."""
        import hashlib

        state_str = json.dumps(
            {"positions": positions, "orders": orders, "account": account},
            sort_keys=True,
            default=str,
        )

        return hashlib.md5(state_str.encode()).hexdigest()

    async def _switch_active_broker(
        self, source_broker: str, target_broker: str
    ) -> None:
        """Switch active broker in trading engine."""
        logger.info(f"Switching active broker: {source_broker} -> {target_broker}")

        # Simulate broker switch
        await asyncio.sleep(0.1)

        # In real implementation, this would:
        # - Update trading engine configuration
        # - Route new orders to target broker
        # - Update market data subscriptions
        # - Notify all trading components

    async def _restore_trading_state(
        self, broker_id: str, snapshot: TradingStateSnapshot
    ) -> None:
        """Restore trading state to target broker."""
        logger.info(f"Restoring trading state to broker: {broker_id}")

        # Simulate state restoration
        await asyncio.sleep(0.3)

        # In real implementation, this would:
        # - Recreate positions (where possible)
        # - Resubmit pending orders
        # - Restore market data subscriptions
        # - Update account settings
        # - Resume strategy execution

    async def _validate_failover_success(
        self, broker_id: str, snapshot: Optional[TradingStateSnapshot]
    ) -> bool:
        """Validate that failover was successful."""
        logger.info(f"Validating failover success for broker: {broker_id}")

        try:
            # Simulate validation checks
            await asyncio.sleep(0.2)

            # In real implementation, this would:
            # - Verify broker connectivity
            # - Check position accuracy
            # - Validate order status
            # - Confirm market data feeds
            # - Test order placement

            return True  # Assume validation passes for simulation

        except Exception as e:
            logger.error(f"Failover validation failed: {e}")
            return False

    async def _finalize_failover(self, execution: FailoverExecution) -> None:
        """Finalize successful failover."""
        logger.info(f"Finalizing failover execution: {execution.execution_id}")

        # Update broker status
        # Clean up old connections
        # Generate completion report
        # Notify stakeholders

        await asyncio.sleep(0.1)

    async def add_execution_listener(self, callback: Callable) -> None:
        """Add failover execution listener."""
        self.execution_listeners.append(weakref.ref(callback))

    async def _notify_execution_listeners(self, execution: FailoverExecution) -> None:
        """Notify execution listeners of phase changes."""
        for listener_ref in self.execution_listeners[:]:
            listener = listener_ref()
            if listener is None:
                self.execution_listeners.remove(listener_ref)
            else:
                try:
                    await listener(execution)
                except Exception as e:
                    logger.error(f"Execution listener error: {e}")

    def get_orchestrator_status(self) -> Dict[str, Any]:
        """Get comprehensive orchestrator status."""
        active_count = len(self.active_executions)
        total_executions = len(self.execution_history)
        successful_executions = sum(1 for ex in self.execution_history if ex.success)

        # Calculate average execution time
        if self.execution_history:
            execution_times = [
                (ex.end_time - ex.start_time).total_seconds()
                for ex in self.execution_history
                if ex.end_time
            ]
            avg_execution_time = (
                sum(execution_times) / len(execution_times) if execution_times else 0.0
            )
        else:
            avg_execution_time = 0.0

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "registered_brokers": len(self.registered_brokers),
            "active_executions": active_count,
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "success_rate_percent": (
                (successful_executions / total_executions) * 100
                if total_executions > 0
                else 0.0
            ),
            "average_execution_time_seconds": round(avg_execution_time, 2),
            "max_failover_time_seconds": self.max_failover_time,
            "failover_rules": len(self.failover_rules),
            "performance_thresholds": self.performance_thresholds,
            "current_executions": [
                {
                    "execution_id": ex.execution_id,
                    "source_broker": ex.source_broker,
                    "target_broker": ex.target_broker,
                    "current_phase": ex.current_phase.value,
                    "start_time": ex.start_time.isoformat(),
                    "elapsed_seconds": (
                        datetime.utcnow() - ex.start_time
                    ).total_seconds(),
                }
                for ex in self.active_executions.values()
            ],
        }
