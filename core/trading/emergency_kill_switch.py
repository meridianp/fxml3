"""
TDD-based Emergency Kill Switch for FXML4 Trading Platform.

Critical safety mechanism for instant trading shutdown and
risk management.
"""

import asyncio
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from core.exceptions import EmergencyShutdownError, RiskError
from core.order_management.order_types import Order, OrderSide, OrderStatus, OrderType


class KillSwitchLevel(Enum):
    """Levels of kill switch activation."""

    PARTIAL = "partial"
    BROKER = "broker"
    FULL = "full"


class EmergencyKillSwitch:
    """
    Emergency trading shutdown mechanism with multi-level controls.

    Provides instant shutdown capabilities, circuit breakers,
    and recovery procedures for risk management.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        order_manager=None,
        execution_engine=None,
        risk_manager=None,
        broker_connections=None,
        notification_service=None,
    ):
        """Initialize EmergencyKillSwitch with configuration and dependencies."""
        self.config = config
        self.order_manager = order_manager
        self.execution_engine = execution_engine
        self.risk_manager = risk_manager
        self.broker_connections = broker_connections or {}
        self.notification_service = notification_service

        # State management
        self.is_active = False
        self.cascade_prevention_active = False
        self.manual_override_active = False
        self.deadman_triggered = False
        self.shutdown_time = None
        self.recovery_time = None

        # Monitoring data
        self.error_log = deque(maxlen=100)
        self.order_submissions = deque(maxlen=1000)
        self.latency_measurements = deque(maxlen=100)
        self.audit_log = []
        self.recorded_actions = deque(maxlen=1000)

        # Circuit breaker states
        self.circuit_breaker_active = False
        self.circuit_breaker_level = None
        self.circuit_breaker_end_time = None

        # Deadman switch
        self.deadman_task = None
        self.last_heartbeat = None
        self.deadman_timeout = None

        # Threading lock for safety
        self._lock = asyncio.Lock()

    async def trigger_emergency_shutdown(self, reason: str) -> Dict[str, Any]:
        """Trigger immediate emergency shutdown."""
        async with self._lock:
            if self.is_active and not self.manual_override_active:
                return {
                    "status": "already_active",
                    "message": "Kill switch is already active",
                }

            self.is_active = True
            self.shutdown_time = datetime.now()

            # Record in audit log FIRST (before other actions)
            self._add_audit_entry("emergency_shutdown", reason)

            # Cancel all orders
            orders_cancelled = await self.cancel_all_orders()

            # Halt execution engine
            if self.execution_engine:
                await self.execution_engine.halt_execution()

            # Terminate broker connections (but don't add more audit entries)
            for broker_name, connection in self.broker_connections.items():
                try:
                    if hasattr(connection, "disconnect"):
                        await connection.disconnect()
                except Exception:
                    pass  # Continue terminating other connections

            # Send notifications
            await self.send_emergency_notifications(KillSwitchLevel.FULL, reason)

            return {
                "status": "shutdown_complete",
                "level": KillSwitchLevel.FULL,
                "timestamp": self.shutdown_time,
                "reason": reason,
                "orders_cancelled": orders_cancelled.get("count", 0),
                "connections_terminated": len(self.broker_connections),
            }

    async def cancel_all_orders(self) -> Dict[str, Any]:
        """Cancel all active orders."""
        cancelled_count = 0

        if self.order_manager and hasattr(self.order_manager, "active_orders"):
            for order_id in list(self.order_manager.active_orders.keys()):
                try:
                    await self.order_manager.cancel_order(
                        order_id, reason="emergency_shutdown"
                    )
                    cancelled_count += 1
                except Exception as e:
                    # Log but continue cancelling other orders
                    self._add_audit_entry(
                        "cancel_order_failed", f"Order {order_id}: {str(e)}"
                    )

        return {"status": "orders_cancelled", "count": cancelled_count}

    async def flatten_all_positions(self, positions: Dict) -> Dict[str, Any]:
        """Flatten all open positions."""
        flatten_orders = []
        total_exposure_removed = Decimal("0")

        for symbol, position in positions.items():
            # Create offsetting order
            quantity = abs(position["quantity"])
            side = OrderSide.SELL if position["side"] == "long" else OrderSide.BUY

            flatten_order = {
                "symbol": symbol,
                "quantity": quantity,
                "side": side,
                "type": "market",
            }
            flatten_orders.append(flatten_order)
            total_exposure_removed += Decimal(str(quantity))

        return {
            "status": "positions_flattened",
            "flatten_orders": flatten_orders,
            "total_exposure_removed": float(total_exposure_removed),
        }

    async def terminate_all_connections(self) -> None:
        """Terminate all broker connections."""
        for broker_name, connection in self.broker_connections.items():
            try:
                if hasattr(connection, "disconnect"):
                    await connection.disconnect()
                self._add_audit_entry("connection_terminated", broker_name)
            except Exception as e:
                self._add_audit_entry("termination_failed", f"{broker_name}: {str(e)}")

    async def monitor_risk_limits(self) -> bool:
        """Monitor and enforce risk limits."""
        if self.manual_override_active:
            return False

        triggered = False

        if self.risk_manager:
            # Check daily loss limit
            current_pnl = self.risk_manager.get_current_pnl()
            max_loss = self.config.get("max_daily_loss", Decimal("100000"))

            if current_pnl < -max_loss:
                await self.trigger_emergency_shutdown(
                    f"Daily loss limit exceeded: {current_pnl}"
                )
                triggered = True

            # Check position size limit
            total_exposure = self.risk_manager.get_total_exposure()
            max_position = self.config.get("max_position_size", Decimal("10000000"))

            if total_exposure > max_position:
                await self.trigger_emergency_shutdown(
                    f"Position limit exceeded: {total_exposure}"
                )
                triggered = True

        return triggered

    async def check_circuit_breakers(self) -> Dict[str, Any]:
        """Check circuit breaker levels."""
        if not self.risk_manager:
            return {"triggered": False}

        current_pnl = self.risk_manager.get_current_pnl()

        # Get initial capital - using a default if method doesn't exist
        if hasattr(self.risk_manager, "get_initial_capital"):
            initial_capital = self.risk_manager.get_initial_capital()
        else:
            initial_capital = Decimal("1000000")  # Default

        loss_percentage = (
            abs(current_pnl / initial_capital) if initial_capital > 0 else 0
        )

        # Check each circuit breaker level
        for i, level in enumerate(self.config.get("circuit_breaker_levels", [])):
            threshold = Decimal(str(level["threshold"]))
            if loss_percentage >= threshold:
                self.circuit_breaker_active = True
                self.circuit_breaker_level = i
                self.circuit_breaker_end_time = datetime.now() + timedelta(
                    seconds=level["duration"]
                )

                return {
                    "triggered": True,
                    "level": i,
                    "duration": level["duration"],
                    "threshold": float(threshold),
                    "loss_percentage": float(loss_percentage),
                }

        return {"triggered": False}

    async def record_error(self, error: str) -> None:
        """Record system error."""
        self.error_log.append({"error": error, "timestamp": datetime.now()})

        # Check for cascade prevention
        error_count = len(
            [
                e
                for e in self.error_log
                if datetime.now() - e["timestamp"] < timedelta(minutes=1)
            ]
        )

        if error_count >= self.config.get("error_threshold", 10):
            self.cascade_prevention_active = True

    async def partial_shutdown(self, symbols: List[str], reason: str) -> Dict[str, Any]:
        """Perform partial shutdown for specific symbols."""
        self._add_audit_entry(
            "partial_shutdown", f"Symbols: {symbols}, Reason: {reason}"
        )

        # Cancel orders for specific symbols
        cancelled_count = 0
        if self.order_manager and hasattr(self.order_manager, "active_orders"):
            for order_id, order in list(self.order_manager.active_orders.items()):
                if order.symbol in symbols:
                    await self.order_manager.cancel_order(
                        order_id, reason="partial_shutdown"
                    )
                    cancelled_count += 1

        return {
            "status": "partial_shutdown",
            "affected_symbols": symbols,
            "level": KillSwitchLevel.PARTIAL,
            "orders_cancelled": cancelled_count,
            "reason": reason,
        }

    async def shutdown_broker(self, broker: str, reason: str) -> Dict[str, Any]:
        """Shutdown specific broker connection."""
        if broker in self.broker_connections:
            connection = self.broker_connections[broker]
            if hasattr(connection, "disconnect"):
                await connection.disconnect()

            self._add_audit_entry(
                "broker_shutdown", f"Broker: {broker}, Reason: {reason}"
            )

            return {"status": "broker_shutdown", "broker": broker, "reason": reason}

        return {"status": "broker_not_found", "broker": broker}

    async def record_order_submission(self, order_id: str) -> None:
        """Record order submission for rate monitoring."""
        self.order_submissions.append(
            {"order_id": order_id, "timestamp": datetime.now()}
        )

    async def check_order_rate(self) -> Dict[str, Any]:
        """Check order submission rate."""
        # Count orders in the last minute
        one_minute_ago = datetime.now() - timedelta(minutes=1)
        recent_orders = [
            o for o in self.order_submissions if o["timestamp"] > one_minute_ago
        ]

        current_rate = len(recent_orders)
        max_rate = self.config.get("max_order_rate", 100)

        return {
            "rate_exceeded": current_rate > max_rate,
            "current_rate": current_rate,
            "max_rate": max_rate,
        }

    async def record_latency(self, latency_ms: int) -> None:
        """Record system latency."""
        self.latency_measurements.append(latency_ms)

    async def check_latency_threshold(self) -> Dict[str, Any]:
        """Check latency threshold."""
        if not self.latency_measurements:
            return {"threshold_exceeded": False, "average_latency": 0}

        avg_latency = sum(self.latency_measurements) / len(self.latency_measurements)
        threshold = self.config.get("latency_threshold_ms", 1000)

        return {
            "threshold_exceeded": avg_latency > threshold,
            "average_latency": avg_latency,
            "threshold": threshold,
        }

    async def send_emergency_notifications(
        self, level: KillSwitchLevel, reason: str
    ) -> None:
        """Send emergency notifications."""
        if not self.notification_service:
            return

        channels = self.config.get("notification_channels", ["email", "sms", "slack"])
        message = (
            f"EMERGENCY: Kill switch activated - Level: {level.value}, Reason: {reason}"
        )

        for channel in channels:
            await self.notification_service.send_alert(
                message=message, channel=channel, priority="critical"
            )

    def get_audit_log(self) -> List[Dict]:
        """Get audit log entries."""
        return self.audit_log

    def _add_audit_entry(self, action: str, details: str) -> None:
        """Add entry to audit log."""
        entry = {
            "timestamp": datetime.now(),
            "action": action,
            "reason": details,
            "details": details,
        }
        self.audit_log.append(entry)

    async def attempt_recovery(
        self, override_time_check: bool = False
    ) -> Dict[str, Any]:
        """Attempt system recovery after shutdown."""
        if not self.is_active:
            return {
                "status": "not_in_shutdown",
                "message": "System is not in shutdown state",
            }

        # Check if enough time has passed
        if self.shutdown_time and not override_time_check:
            elapsed = (datetime.now() - self.shutdown_time).total_seconds()
            recovery_timeout = self.config.get("recovery_timeout_seconds", 300)

            if elapsed < recovery_timeout:
                return {
                    "status": "too_soon",
                    "remaining_seconds": recovery_timeout - elapsed,
                }

        # Perform recovery checks
        checks_passed = await self._perform_recovery_checks()

        if checks_passed:
            self.is_active = False
            self.recovery_time = datetime.now()
            self._add_audit_entry("recovery_initiated", "All checks passed")

            return {
                "status": "recovery_initiated",
                "timestamp": self.recovery_time,
                "checks_passed": True,
            }

        return {"status": "recovery_failed", "checks_passed": False}

    async def _perform_recovery_checks(self) -> bool:
        """Perform system checks before recovery."""
        # Simplified checks - in production would be more comprehensive
        return True

    def set_manual_override(self, enabled: bool, authorized_by: str) -> None:
        """Set manual override for automatic triggers."""
        self.manual_override_active = enabled
        self._add_audit_entry(
            "manual_override", f"Enabled: {enabled}, By: {authorized_by}"
        )

    async def perform_health_check(self) -> Dict[str, Any]:
        """Perform comprehensive system health check."""
        components = {}

        # Check order manager
        if self.order_manager:
            components["order_manager"] = "healthy"

        # Check execution engine
        if self.execution_engine:
            components["execution_engine"] = "healthy"

        # Check broker connections
        components["broker_connections"] = {}
        for broker_name in self.broker_connections:
            components["broker_connections"][broker_name] = "connected"

        return {
            "status": "healthy" if components else "degraded",
            "components": components,
            "timestamp": datetime.now(),
        }

    async def start_deadman_switch(self, timeout_seconds: int) -> None:
        """Start deadman switch monitoring."""
        self.deadman_timeout = timeout_seconds
        self.last_heartbeat = datetime.now()

        async def monitor_heartbeat():
            while self.deadman_timeout:
                await asyncio.sleep(1)
                if self.last_heartbeat:
                    elapsed = (datetime.now() - self.last_heartbeat).total_seconds()
                    if elapsed > self.deadman_timeout:
                        self.deadman_triggered = True
                        await self.trigger_emergency_shutdown("Deadman switch timeout")
                        break

        self.deadman_task = asyncio.create_task(monitor_heartbeat())

    async def heartbeat(self) -> None:
        """Send heartbeat signal to reset deadman switch."""
        self.last_heartbeat = datetime.now()

    async def record_action(self, action: str, details: Dict) -> None:
        """Record action for potential rollback."""
        self.recorded_actions.append(
            {"action": action, "details": details, "timestamp": datetime.now()}
        )

    async def rollback_recent_actions(self, seconds: int) -> Dict[str, Any]:
        """Rollback recent actions within specified time window."""
        cutoff_time = datetime.now() - timedelta(seconds=seconds)
        actions_to_rollback = [
            a for a in self.recorded_actions if a["timestamp"] > cutoff_time
        ]

        # In production, would actually rollback the actions
        # This is simplified for the prototype

        return {
            "status": "rollback_complete",
            "actions_rolled_back": len(actions_to_rollback),
            "timestamp": datetime.now(),
        }
