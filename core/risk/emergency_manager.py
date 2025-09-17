"""
Emergency Manager for FXML4

Emergency kill switch and circuit breaker implementation for risk management.
Provides automated emergency actions when critical conditions are detected.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class EmergencyLevel(str, Enum):
    """Emergency severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class EmergencyAction(str, Enum):
    """Emergency actions that can be taken."""

    ALERT = "alert"
    REDUCE_POSITION = "reduce_position"
    CLOSE_POSITION = "close_position"
    CLOSE_ALL_POSITIONS = "close_all_positions"
    HALT_TRADING = "halt_trading"
    FULL_SHUTDOWN = "full_shutdown"


@dataclass
class EmergencyCondition:
    """Condition that triggers emergency action."""

    name: str
    check_function: Callable
    level: EmergencyLevel
    actions: List[EmergencyAction]
    threshold: Any
    cooldown_minutes: int = 5
    last_triggered: Optional[datetime] = None


@dataclass
class EmergencyEvent:
    """Emergency event record."""

    timestamp: datetime
    level: EmergencyLevel
    condition_name: str
    description: str
    actions_taken: List[EmergencyAction]
    metadata: Dict[str, Any] = field(default_factory=dict)


class EmergencyManager:
    """Manager for emergency kill switch and critical risk events."""

    def __init__(
        self,
        max_daily_loss: Decimal = Decimal("0.1"),  # 10% max daily loss
        max_drawdown: Decimal = Decimal("0.15"),  # 15% max drawdown
        max_consecutive_losses: int = 5,
        margin_call_level: Decimal = Decimal("100"),  # 100% margin level
    ):
        """Initialize emergency manager."""
        self.max_daily_loss = max_daily_loss
        self.max_drawdown = max_drawdown
        self.max_consecutive_losses = max_consecutive_losses
        self.margin_call_level = margin_call_level

        # State tracking
        self.is_halted = False
        self.halt_reason = None
        self.halt_timestamp = None
        self.consecutive_losses = 0
        self.daily_loss = Decimal("0")

        # Emergency conditions
        self.conditions: List[EmergencyCondition] = []
        self.event_history: List[EmergencyEvent] = []

        # Callbacks for actions
        self.action_callbacks: Dict[EmergencyAction, List[Callable]] = {
            action: [] for action in EmergencyAction
        }

        # Initialize default conditions
        self._initialize_default_conditions()

    def _initialize_default_conditions(self):
        """Set up default emergency conditions."""
        # Daily loss limit
        self.add_condition(
            EmergencyCondition(
                name="daily_loss_limit",
                check_function=self._check_daily_loss,
                level=EmergencyLevel.EMERGENCY,
                actions=[
                    EmergencyAction.CLOSE_ALL_POSITIONS,
                    EmergencyAction.HALT_TRADING,
                ],
                threshold=self.max_daily_loss,
            )
        )

        # Drawdown limit
        self.add_condition(
            EmergencyCondition(
                name="max_drawdown",
                check_function=self._check_drawdown,
                level=EmergencyLevel.CRITICAL,
                actions=[
                    EmergencyAction.REDUCE_POSITION,
                    EmergencyAction.ALERT,
                ],
                threshold=self.max_drawdown,
            )
        )

        # Consecutive losses
        self.add_condition(
            EmergencyCondition(
                name="consecutive_losses",
                check_function=self._check_consecutive_losses,
                level=EmergencyLevel.WARNING,
                actions=[EmergencyAction.ALERT],
                threshold=self.max_consecutive_losses,
            )
        )

        # Margin call
        self.add_condition(
            EmergencyCondition(
                name="margin_call",
                check_function=self._check_margin_level,
                level=EmergencyLevel.EMERGENCY,
                actions=[
                    EmergencyAction.CLOSE_ALL_POSITIONS,
                    EmergencyAction.FULL_SHUTDOWN,
                ],
                threshold=self.margin_call_level,
            )
        )

    def add_condition(self, condition: EmergencyCondition):
        """Add an emergency condition to monitor."""
        self.conditions.append(condition)

    def register_action_callback(
        self, action: EmergencyAction, callback: Callable
    ):
        """Register a callback for an emergency action."""
        self.action_callbacks[action].append(callback)

    async def check_conditions(
        self, market_data: Dict[str, Any]
    ) -> List[EmergencyEvent]:
        """Check all emergency conditions and trigger actions if needed."""
        triggered_events = []

        for condition in self.conditions:
            # Check cooldown
            if condition.last_triggered:
                elapsed = datetime.now() - condition.last_triggered
                if elapsed < timedelta(minutes=condition.cooldown_minutes):
                    continue

            # Check condition
            try:
                is_triggered = await self._execute_check(
                    condition.check_function, market_data
                )

                if is_triggered:
                    # Create emergency event
                    event = EmergencyEvent(
                        timestamp=datetime.now(),
                        level=condition.level,
                        condition_name=condition.name,
                        description=f"{condition.name} threshold exceeded",
                        actions_taken=condition.actions,
                        metadata=market_data,
                    )

                    # Execute actions
                    await self._execute_emergency_actions(
                        condition.actions, event
                    )

                    # Record event
                    self.event_history.append(event)
                    triggered_events.append(event)

                    # Update last triggered time
                    condition.last_triggered = datetime.now()

            except Exception as e:
                # Log error but don't crash
                print(f"Error checking condition {condition.name}: {e}")

        return triggered_events

    async def _execute_check(
        self, check_function: Callable, data: Dict[str, Any]
    ) -> bool:
        """Execute a condition check function."""
        if asyncio.iscoroutinefunction(check_function):
            return await check_function(data)
        return check_function(data)

    async def _execute_emergency_actions(
        self, actions: List[EmergencyAction], event: EmergencyEvent
    ):
        """Execute emergency actions."""
        for action in actions:
            # Execute registered callbacks
            for callback in self.action_callbacks[action]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event)
                    else:
                        callback(event)
                except Exception as e:
                    print(f"Error executing action {action}: {e}")

            # Handle built-in actions
            if action == EmergencyAction.HALT_TRADING:
                self.halt_trading(event.description)
            elif action == EmergencyAction.FULL_SHUTDOWN:
                await self.emergency_shutdown()

    def halt_trading(self, reason: str):
        """Halt all trading activities."""
        self.is_halted = True
        self.halt_reason = reason
        self.halt_timestamp = datetime.now()

    def resume_trading(self):
        """Resume trading after halt."""
        self.is_halted = False
        self.halt_reason = None
        self.halt_timestamp = None

    async def emergency_shutdown(self):
        """Perform emergency shutdown of all systems."""
        # This would trigger a complete system shutdown
        self.is_halted = True
        self.halt_reason = "EMERGENCY SHUTDOWN"
        self.halt_timestamp = datetime.now()

        # Additional shutdown logic would go here
        # - Close all positions
        # - Cancel all pending orders
        # - Disconnect from brokers
        # - Send emergency notifications

    def update_daily_loss(self, pnl: Decimal):
        """Update daily P&L tracking."""
        self.daily_loss = pnl

    def update_consecutive_losses(self, is_loss: bool):
        """Update consecutive loss counter."""
        if is_loss:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

    def _check_daily_loss(self, data: Dict[str, Any]) -> bool:
        """Check if daily loss limit exceeded."""
        account_balance = data.get("account_balance", Decimal("100000"))
        daily_pnl = data.get("daily_pnl", self.daily_loss)

        if daily_pnl < 0:
            loss_percentage = abs(daily_pnl) / account_balance
            return loss_percentage > self.max_daily_loss

        return False

    def _check_drawdown(self, data: Dict[str, Any]) -> bool:
        """Check if drawdown limit exceeded."""
        drawdown = data.get("current_drawdown", Decimal("0"))
        return abs(drawdown) > self.max_drawdown

    def _check_consecutive_losses(self, data: Dict[str, Any]) -> bool:
        """Check if consecutive loss limit exceeded."""
        consecutive = data.get("consecutive_losses", self.consecutive_losses)
        return consecutive >= self.max_consecutive_losses

    def _check_margin_level(self, data: Dict[str, Any]) -> bool:
        """Check if margin level is critical."""
        margin_level = data.get("margin_level", Decimal("200"))
        return margin_level < self.margin_call_level

    def get_status(self) -> Dict[str, Any]:
        """Get current emergency manager status."""
        return {
            "is_halted": self.is_halted,
            "halt_reason": self.halt_reason,
            "halt_timestamp": self.halt_timestamp.isoformat()
            if self.halt_timestamp
            else None,
            "consecutive_losses": self.consecutive_losses,
            "daily_loss": str(self.daily_loss),
            "active_conditions": len(self.conditions),
            "recent_events": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "level": e.level.value,
                    "condition": e.condition_name,
                    "description": e.description,
                }
                for e in self.event_history[-5:]  # Last 5 events
            ],
        }

    def reset_daily_stats(self):
        """Reset daily statistics (called at day start)."""
        self.daily_loss = Decimal("0")
        self.consecutive_losses = 0

    def get_event_history(
        self,
        level: Optional[EmergencyLevel] = None,
        since: Optional[datetime] = None,
    ) -> List[EmergencyEvent]:
        """Get emergency event history with optional filters."""
        events = self.event_history

        if level:
            events = [e for e in events if e.level == level]

        if since:
            events = [e for e in events if e.timestamp >= since]

        return events