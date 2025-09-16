"""
Trading Suspension Manager for FXML4 Trading System

This module manages the suspension and resumption of trading operations based
on economic news events, ensuring the trading system avoids periods of extreme
market volatility that could result in significant losses.

Key Features:
- Automated trading suspension based on economic events
- Granular control per currency pair or global suspension
- State preservation during suspension periods
- Configurable suspension timing and criteria
- Integration with existing trading and risk management systems
- Comprehensive audit logging for all suspension actions

Suspension Types:
- Global: All trading operations suspended
- Currency-specific: Only pairs involving specific currencies
- Pair-specific: Individual trading pairs suspended
- Emergency: Immediate suspension due to critical events
"""

import asyncio
import json
import logging
import time
import uuid
import weakref
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Set

from .economic_calendar import EconomicEvent, EventImpact
from .event_classifier import EventCategory
from .news_monitor import EventAlert

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SuspensionReason(Enum):
    """Reasons for trading suspension."""

    ECONOMIC_EVENT = "economic_event"
    MARKET_VOLATILITY = "market_volatility"
    TECHNICAL_ISSUE = "technical_issue"
    RISK_BREACH = "risk_breach"
    MANUAL_OVERRIDE = "manual_override"
    EMERGENCY = "emergency"


class SuspensionStatus(Enum):
    """Trading suspension status."""

    ACTIVE = "active"  # Trading is active
    SUSPENDED = "suspended"  # Trading is suspended
    RESUMING = "resuming"  # In process of resuming
    SUSPENDING = "suspending"  # In process of suspending


class TradingState(Enum):
    """Trading system state."""

    NORMAL = "normal"
    RESTRICTED = "restricted"
    SUSPENDED = "suspended"
    EMERGENCY = "emergency"


@dataclass
class SuspensionEvent:
    """Trading suspension event record."""

    event_id: str
    timestamp: datetime
    reason: SuspensionReason
    status: SuspensionStatus
    scope: str  # "global", "currency:USD", "pair:GBPUSD"
    description: str
    economic_event_id: Optional[str] = None
    suspended_pairs: Set[str] = field(default_factory=set)
    suspension_start: Optional[datetime] = None
    suspension_end: Optional[datetime] = None
    planned_resume_time: Optional[datetime] = None
    actual_resume_time: Optional[datetime] = None
    positions_affected: int = 0
    orders_cancelled: int = 0
    manual_override: bool = False

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get suspension duration in seconds."""
        if self.suspension_start and self.actual_resume_time:
            return (self.actual_resume_time - self.suspension_start).total_seconds()
        elif self.suspension_start:
            return (datetime.utcnow() - self.suspension_start).total_seconds()
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert suspension event to dictionary."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "reason": self.reason.value,
            "status": self.status.value,
            "scope": self.scope,
            "description": self.description,
            "economic_event_id": self.economic_event_id,
            "suspended_pairs": list(self.suspended_pairs),
            "suspension_start": (
                self.suspension_start.isoformat() if self.suspension_start else None
            ),
            "suspension_end": (
                self.suspension_end.isoformat() if self.suspension_end else None
            ),
            "planned_resume_time": (
                self.planned_resume_time.isoformat()
                if self.planned_resume_time
                else None
            ),
            "actual_resume_time": (
                self.actual_resume_time.isoformat() if self.actual_resume_time else None
            ),
            "duration_seconds": self.duration_seconds,
            "positions_affected": self.positions_affected,
            "orders_cancelled": self.orders_cancelled,
            "manual_override": self.manual_override,
        }


class TradingSuspensionManager:
    """
    Manages trading suspension and resumption operations.

    Controls when trading operations should be suspended due to
    economic events and manages the graceful suspension and
    resumption of trading activities.
    """

    def __init__(self):
        # Current state
        self.global_trading_state = TradingState.NORMAL
        self.suspended_pairs: Set[str] = set()
        self.suspended_currencies: Set[str] = set()

        # Active suspensions
        self.active_suspensions: Dict[str, SuspensionEvent] = {}
        self.suspension_history: deque = deque(maxlen=1000)

        # Scheduled suspensions
        self.scheduled_suspensions: Dict[str, SuspensionEvent] = {}
        self.suspension_scheduler_task: Optional[asyncio.Task] = None

        # Event handlers
        self.suspension_listeners: List[weakref.ReferenceType] = []
        self.resume_listeners: List[weakref.ReferenceType] = []
        self.state_change_listeners: List[weakref.ReferenceType] = []

        # Configuration
        self.default_suspension_config = {
            EventImpact.CRITICAL: {
                "pre_event_minutes": 30,
                "post_event_minutes": 60,
                "scope": "currency",  # or 'global', 'pair'
            },
            EventImpact.HIGH: {
                "pre_event_minutes": 15,
                "post_event_minutes": 30,
                "scope": "currency",
            },
            EventImpact.MEDIUM: {
                "pre_event_minutes": 5,
                "post_event_minutes": 15,
                "scope": "pair",
            },
            EventImpact.LOW: {
                "pre_event_minutes": 0,
                "post_event_minutes": 0,
                "scope": "none",
            },
        }

        # Currency pair mappings for suspension
        self.currency_pairs_map = {
            "USD": {
                "EURUSD",
                "GBPUSD",
                "USDJPY",
                "USDCHF",
                "USDCAD",
                "AUDUSD",
                "NZDUSD",
            },
            "EUR": {
                "EURUSD",
                "EURGBP",
                "EURJPY",
                "EURCHF",
                "EURCAD",
                "EURAUD",
                "EURNZD",
            },
            "GBP": {
                "GBPUSD",
                "EURGBP",
                "GBPJPY",
                "GBPCHF",
                "GBPCAD",
                "GBPAUD",
                "GBPNZD",
            },
            "JPY": {
                "USDJPY",
                "EURJPY",
                "GBPJPY",
                "CHFJPY",
                "CADJPY",
                "AUDJPY",
                "NZDJPY",
            },
            "CHF": {"USDCHF", "EURCHF", "GBPCHF", "CHFJPY"},
            "CAD": {"USDCAD", "EURCAD", "GBPCAD", "CADJPY", "AUDCAD", "NZDCAD"},
            "AUD": {
                "AUDUSD",
                "EURAUD",
                "GBPAUD",
                "AUDJPY",
                "AUDCHF",
                "AUDCAD",
                "AUDNZD",
            },
            "NZD": {
                "NZDUSD",
                "EURNZD",
                "GBPNZD",
                "NZDJPY",
                "NZDCHF",
                "NZDCAD",
                "AUDNZD",
            },
        }

        # Statistics
        self.stats = {
            "total_suspensions": 0,
            "total_resumes": 0,
            "total_pairs_suspended": 0,
            "total_suspension_time_minutes": 0.0,
            "emergency_suspensions": 0,
            "manual_overrides": 0,
        }

        # Start scheduler
        self.suspension_scheduler_task = asyncio.create_task(
            self._suspension_scheduler_loop()
        )

        logger.info("TradingSuspensionManager initialized")

    async def schedule_event_suspension(
        self, alert: EventAlert, suspension_config: Dict[str, Any]
    ) -> str:
        """Schedule trading suspension for an economic event."""
        event = alert.event

        # Create suspension event
        suspension_id = str(uuid.uuid4())

        # Calculate suspension timing
        pre_event_minutes = suspension_config.get("pre_event_minutes", 15)
        post_event_minutes = suspension_config.get("post_event_minutes", 30)

        suspension_start = event.date_time - timedelta(minutes=pre_event_minutes)
        planned_resume = event.date_time + timedelta(minutes=post_event_minutes)

        # Determine suspension scope and affected pairs
        scope = suspension_config.get("scope", "currency")
        suspended_pairs = self._determine_suspended_pairs(
            event, scope, alert.affected_pairs
        )

        suspension_event = SuspensionEvent(
            event_id=suspension_id,
            timestamp=datetime.utcnow(),
            reason=SuspensionReason.ECONOMIC_EVENT,
            status=SuspensionStatus.ACTIVE,
            scope=f"{scope}:{event.currency}" if scope == "currency" else scope,
            description=f"Scheduled suspension for {event.title} ({event.currency})",
            economic_event_id=event.event_id,
            suspended_pairs=suspended_pairs,
            suspension_start=suspension_start,
            suspension_end=planned_resume,
            planned_resume_time=planned_resume,
        )

        # Schedule the suspension
        self.scheduled_suspensions[suspension_id] = suspension_event

        logger.info(
            f"Scheduled trading suspension for event '{event.title}' at {suspension_start}"
        )
        logger.info(f"  Suspended pairs: {len(suspended_pairs)} pairs")
        logger.info(f"  Planned resume: {planned_resume}")

        return suspension_id

    async def execute_immediate_suspension(
        self,
        reason: SuspensionReason,
        scope: str,
        description: str,
        duration_minutes: int = 60,
        affected_pairs: Optional[Set[str]] = None,
    ) -> str:
        """Execute immediate trading suspension."""
        suspension_id = str(uuid.uuid4())
        now = datetime.utcnow()

        # Determine suspended pairs
        if affected_pairs:
            suspended_pairs = affected_pairs
        elif scope == "global":
            suspended_pairs = set(
                pair for pairs in self.currency_pairs_map.values() for pair in pairs
            )
        elif scope.startswith("currency:"):
            currency = scope.split(":")[1]
            suspended_pairs = self.currency_pairs_map.get(currency, set())
        else:
            suspended_pairs = {scope} if scope.startswith("pair:") else set()

        suspension_event = SuspensionEvent(
            event_id=suspension_id,
            timestamp=now,
            reason=reason,
            status=SuspensionStatus.SUSPENDING,
            scope=scope,
            description=description,
            suspended_pairs=suspended_pairs,
            suspension_start=now,
            suspension_end=now + timedelta(minutes=duration_minutes),
            planned_resume_time=now + timedelta(minutes=duration_minutes),
        )

        # Execute suspension
        await self._execute_suspension(suspension_event)

        return suspension_id

    async def _execute_suspension(self, suspension_event: SuspensionEvent) -> None:
        """Execute a trading suspension."""
        logger.warning(f"Executing trading suspension: {suspension_event.description}")

        suspension_event.status = SuspensionStatus.SUSPENDING

        try:
            # Update system state
            if suspension_event.scope == "global":
                self.global_trading_state = TradingState.SUSPENDED

            # Add suspended pairs
            self.suspended_pairs.update(suspension_event.suspended_pairs)

            # Track suspended currencies
            for pair in suspension_event.suspended_pairs:
                # Extract currencies from pair (assuming format like EURUSD)
                if len(pair) == 6:
                    base_currency = pair[:3]
                    quote_currency = pair[3:]
                    self.suspended_currencies.add(base_currency)
                    self.suspended_currencies.add(quote_currency)

            # Simulate order cancellation and position management
            # In real implementation, this would:
            # 1. Cancel pending orders for suspended pairs
            # 2. Close or hedge existing positions if required
            # 3. Block new order submissions

            orders_cancelled = await self._cancel_pending_orders(
                suspension_event.suspended_pairs
            )
            positions_affected = await self._manage_existing_positions(
                suspension_event.suspended_pairs
            )

            suspension_event.orders_cancelled = orders_cancelled
            suspension_event.positions_affected = positions_affected
            suspension_event.status = SuspensionStatus.SUSPENDED

            # Store active suspension
            self.active_suspensions[suspension_event.event_id] = suspension_event

            # Update statistics
            self.stats["total_suspensions"] += 1
            self.stats["total_pairs_suspended"] += len(suspension_event.suspended_pairs)
            if suspension_event.reason == SuspensionReason.EMERGENCY:
                self.stats["emergency_suspensions"] += 1

            logger.warning(f"Trading suspension executed successfully:")
            logger.warning(
                f"  Suspended pairs: {len(suspension_event.suspended_pairs)}"
            )
            logger.warning(f"  Orders cancelled: {orders_cancelled}")
            logger.warning(f"  Positions affected: {positions_affected}")

            # Notify listeners
            await self._notify_suspension_listeners(suspension_event)
            await self._notify_state_change_listeners()

        except Exception as e:
            logger.error(f"Failed to execute trading suspension: {e}")
            suspension_event.status = (
                SuspensionStatus.ACTIVE
            )  # Revert to previous state
            raise

    async def _cancel_pending_orders(self, suspended_pairs: Set[str]) -> int:
        """Cancel pending orders for suspended pairs."""
        # Simulate order cancellation
        # In real implementation, this would interface with the order management system
        cancelled_count = (
            len(suspended_pairs) * 2
        )  # Simulate 2 orders per pair on average

        logger.info(f"Cancelled {cancelled_count} pending orders for suspended pairs")
        return cancelled_count

    async def _manage_existing_positions(self, suspended_pairs: Set[str]) -> int:
        """Manage existing positions for suspended pairs."""
        # Simulate position management
        # In real implementation, this might:
        # 1. Close positions if required by risk policy
        # 2. Apply hedging strategies
        # 3. Adjust position sizes

        affected_positions = (
            len(suspended_pairs) * 1
        )  # Simulate 1 position per pair on average

        logger.info(
            f"Managed {affected_positions} existing positions for suspended pairs"
        )
        return affected_positions

    async def resume_trading(
        self, suspension_id: str, manual_override: bool = False
    ) -> bool:
        """Resume trading for a specific suspension."""
        if suspension_id not in self.active_suspensions:
            logger.warning(f"Cannot resume: suspension {suspension_id} not found")
            return False

        suspension_event = self.active_suspensions[suspension_id]

        logger.info(f"Resuming trading for suspension: {suspension_event.description}")

        try:
            suspension_event.status = SuspensionStatus.RESUMING
            suspension_event.actual_resume_time = datetime.utcnow()
            suspension_event.manual_override = manual_override

            # Remove suspended pairs
            self.suspended_pairs -= suspension_event.suspended_pairs

            # Update currencies (remove if no pairs are suspended)
            for pair in suspension_event.suspended_pairs:
                if len(pair) == 6:
                    base_currency = pair[:3]
                    quote_currency = pair[3:]

                    # Check if currency is still suspended in other pairs
                    base_still_suspended = any(
                        p
                        for p in self.suspended_pairs
                        if p.startswith(base_currency) or p.endswith(base_currency)
                    )
                    quote_still_suspended = any(
                        p
                        for p in self.suspended_pairs
                        if p.startswith(quote_currency) or p.endswith(quote_currency)
                    )

                    if not base_still_suspended:
                        self.suspended_currencies.discard(base_currency)
                    if not quote_still_suspended:
                        self.suspended_currencies.discard(quote_currency)

            # Update global state if no suspensions remain
            if (
                not self.suspended_pairs
                and self.global_trading_state == TradingState.SUSPENDED
            ):
                self.global_trading_state = TradingState.NORMAL

            suspension_event.status = SuspensionStatus.ACTIVE  # Back to normal

            # Move to history
            del self.active_suspensions[suspension_id]
            self.suspension_history.append(suspension_event)

            # Update statistics
            self.stats["total_resumes"] += 1
            if suspension_event.duration_seconds:
                self.stats["total_suspension_time_minutes"] += (
                    suspension_event.duration_seconds / 60
                )
            if manual_override:
                self.stats["manual_overrides"] += 1

            logger.info(f"Trading resumed successfully:")
            logger.info(f"  Resumed pairs: {len(suspension_event.suspended_pairs)}")
            logger.info(f"  Duration: {suspension_event.duration_seconds:.1f} seconds")
            logger.info(f"  Manual override: {manual_override}")

            # Notify listeners
            await self._notify_resume_listeners(suspension_event)
            await self._notify_state_change_listeners()

            return True

        except Exception as e:
            logger.error(f"Failed to resume trading: {e}")
            suspension_event.status = SuspensionStatus.SUSPENDED  # Revert
            return False

    async def emergency_suspend_all(
        self, description: str = "Emergency suspension"
    ) -> str:
        """Execute emergency suspension of all trading."""
        logger.critical(f"EMERGENCY SUSPENSION: {description}")

        suspension_id = await self.execute_immediate_suspension(
            reason=SuspensionReason.EMERGENCY,
            scope="global",
            description=f"EMERGENCY: {description}",
            duration_minutes=60,  # 1 hour default
        )

        # Set emergency state
        self.global_trading_state = TradingState.EMERGENCY

        return suspension_id

    async def _suspension_scheduler_loop(self) -> None:
        """Background loop to handle scheduled suspensions and resumes."""
        logger.info("Starting trading suspension scheduler")

        while True:
            try:
                now = datetime.utcnow()

                # Check for scheduled suspensions to execute
                suspensions_to_execute = []
                for (
                    suspension_id,
                    suspension_event,
                ) in self.scheduled_suspensions.items():
                    if (
                        suspension_event.suspension_start
                        and suspension_event.suspension_start <= now
                        and suspension_event.status == SuspensionStatus.ACTIVE
                    ):
                        suspensions_to_execute.append(suspension_id)

                # Execute scheduled suspensions
                for suspension_id in suspensions_to_execute:
                    suspension_event = self.scheduled_suspensions[suspension_id]
                    logger.info(
                        f"Executing scheduled suspension: {suspension_event.description}"
                    )

                    await self._execute_suspension(suspension_event)

                    # Move from scheduled to active
                    del self.scheduled_suspensions[suspension_id]

                # Check for automatic resumes
                resumes_to_execute = []
                for suspension_id, suspension_event in self.active_suspensions.items():
                    if (
                        suspension_event.planned_resume_time
                        and suspension_event.planned_resume_time <= now
                        and suspension_event.status == SuspensionStatus.SUSPENDED
                    ):
                        resumes_to_execute.append(suspension_id)

                # Execute automatic resumes
                for suspension_id in resumes_to_execute:
                    suspension_event = self.active_suspensions[suspension_id]
                    logger.info(
                        f"Auto-resuming trading: {suspension_event.description}"
                    )

                    await self.resume_trading(suspension_id, manual_override=False)

                # Wait before next check
                await asyncio.sleep(30)  # Check every 30 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in suspension scheduler: {e}")
                await asyncio.sleep(60)  # Wait longer on error

        logger.info("Trading suspension scheduler stopped")

    def _determine_suspended_pairs(
        self, event: EconomicEvent, scope: str, affected_pairs: Set[str]
    ) -> Set[str]:
        """Determine which pairs should be suspended."""
        if scope == "global":
            # All major pairs
            return set(
                pair for pairs in self.currency_pairs_map.values() for pair in pairs
            )
        elif scope == "currency":
            # All pairs involving the event currency
            return self.currency_pairs_map.get(event.currency, set())
        elif scope == "pair":
            # Only specific pairs
            return affected_pairs
        else:
            return set()

    async def add_suspension_listener(self, callback: Callable) -> None:
        """Add suspension event listener."""
        self.suspension_listeners.append(weakref.ref(callback))

    async def add_resume_listener(self, callback: Callable) -> None:
        """Add resume event listener."""
        self.resume_listeners.append(weakref.ref(callback))

    async def add_state_change_listener(self, callback: Callable) -> None:
        """Add state change listener."""
        self.state_change_listeners.append(weakref.ref(callback))

    async def _notify_suspension_listeners(
        self, suspension_event: SuspensionEvent
    ) -> None:
        """Notify suspension listeners."""
        for listener_ref in self.suspension_listeners[:]:
            listener = listener_ref()
            if listener is None:
                self.suspension_listeners.remove(listener_ref)
            else:
                try:
                    await listener(suspension_event)
                except Exception as e:
                    logger.error(f"Suspension listener error: {e}")

    async def _notify_resume_listeners(self, suspension_event: SuspensionEvent) -> None:
        """Notify resume listeners."""
        for listener_ref in self.resume_listeners[:]:
            listener = listener_ref()
            if listener is None:
                self.resume_listeners.remove(listener_ref)
            else:
                try:
                    await listener(suspension_event)
                except Exception as e:
                    logger.error(f"Resume listener error: {e}")

    async def _notify_state_change_listeners(self) -> None:
        """Notify state change listeners."""
        for listener_ref in self.state_change_listeners[:]:
            listener = listener_ref()
            if listener is None:
                self.state_change_listeners.remove(listener_ref)
            else:
                try:
                    await listener(self.get_current_state())
                except Exception as e:
                    logger.error(f"State change listener error: {e}")

    def is_pair_suspended(self, pair: str) -> bool:
        """Check if a trading pair is currently suspended."""
        return pair in self.suspended_pairs

    def is_currency_suspended(self, currency: str) -> bool:
        """Check if a currency is currently suspended."""
        return currency in self.suspended_currencies

    def is_trading_allowed(self, pair: str) -> bool:
        """Check if trading is allowed for a specific pair."""
        return self.global_trading_state in [
            TradingState.NORMAL,
            TradingState.RESTRICTED,
        ] and not self.is_pair_suspended(pair)

    def get_current_state(self) -> Dict[str, Any]:
        """Get current trading suspension state."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "global_state": self.global_trading_state.value,
            "suspended_pairs_count": len(self.suspended_pairs),
            "suspended_currencies_count": len(self.suspended_currencies),
            "active_suspensions_count": len(self.active_suspensions),
            "scheduled_suspensions_count": len(self.scheduled_suspensions),
            "suspended_pairs": list(self.suspended_pairs),
            "suspended_currencies": list(self.suspended_currencies),
            "statistics": self.stats.copy(),
        }

    def get_active_suspensions(self) -> List[Dict[str, Any]]:
        """Get all active suspensions."""
        return [suspension.to_dict() for suspension in self.active_suspensions.values()]

    def get_scheduled_suspensions(self) -> List[Dict[str, Any]]:
        """Get all scheduled suspensions."""
        return [
            suspension.to_dict() for suspension in self.scheduled_suspensions.values()
        ]

    def get_suspension_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get suspension history."""
        recent_history = list(self.suspension_history)[-limit:]
        return [suspension.to_dict() for suspension in recent_history]

    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.suspension_scheduler_task and not self.suspension_scheduler_task.done():
            self.suspension_scheduler_task.cancel()
            try:
                await self.suspension_scheduler_task
            except asyncio.CancelledError:
                pass

        logger.info("TradingSuspensionManager cleanup completed")
