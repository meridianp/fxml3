"""Message Router for Broker Selection and Load Balancing.

This module provides intelligent routing of orders to appropriate
broker adapters based on symbol, order characteristics, and broker availability.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from ...fix.messages.base import FIXMessage, OrdType, Side

logger = logging.getLogger(__name__)


class BrokerStatus(Enum):
    """Broker connection status."""

    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"


class RoutingStrategy(Enum):
    """Order routing strategies."""

    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    BEST_EXECUTION = "best_execution"
    SYMBOL_AFFINITY = "symbol_affinity"
    MANUAL_ONLY = "manual_only"
    PRIMARY_BACKUP = "primary_backup"


@dataclass
class BrokerCapabilities:
    """Broker capabilities and constraints."""

    broker_type: str
    supported_symbols: Set[str]
    supported_order_types: Set[OrdType]
    max_order_size: float
    min_order_size: float
    supports_fractional: bool
    latency_ms: float
    commission_rate: float
    supports_after_hours: bool
    supported_currencies: Set[str]
    risk_limits: Dict[str, float]


@dataclass
class BrokerMetrics:
    """Real-time broker performance metrics."""

    broker_type: str
    status: BrokerStatus
    last_update: datetime
    pending_orders: int
    fill_rate_percent: float
    avg_latency_ms: float
    error_rate_percent: float
    daily_volume: float
    connection_uptime_percent: float


@dataclass
class RoutingRule:
    """Rule for routing orders to specific brokers."""

    name: str
    priority: int
    conditions: Dict[str, any]  # Conditions to match
    target_brokers: List[str]  # Eligible brokers in order of preference
    fallback_brokers: List[str]  # Fallback options
    max_daily_volume: Optional[float] = None
    enabled: bool = True


class MessageRouter:
    """Intelligent router for broker message routing.

    This class implements sophisticated routing logic to select the optimal
    broker for each order based on multiple factors including symbol coverage,
    broker capabilities, current load, and routing rules.
    """

    def __init__(
        self, default_strategy: RoutingStrategy = RoutingStrategy.BEST_EXECUTION
    ):
        """Initialize message router.

        Args:
            default_strategy: Default routing strategy to use.
        """
        self.default_strategy = default_strategy

        # Broker configuration
        self.broker_capabilities: Dict[str, BrokerCapabilities] = {}
        self.broker_metrics: Dict[str, BrokerMetrics] = {}
        self.routing_rules: List[RoutingRule] = []

        # Routing state
        self.round_robin_index = 0
        self.daily_volumes: Dict[str, float] = {}
        self.last_daily_reset = datetime.now().date()

        # Symbol-to-broker affinity mapping
        self.symbol_affinity: Dict[str, List[str]] = {}

        # Initialize default broker configurations
        self._initialize_default_brokers()
        self._initialize_default_rules()

    def _initialize_default_brokers(self) -> None:
        """Initialize default broker capabilities."""
        # Interactive Brokers configuration
        self.broker_capabilities["ib"] = BrokerCapabilities(
            broker_type="ib",
            supported_symbols={"*"},  # Supports all symbols
            supported_order_types={
                OrdType.MARKET,
                OrdType.LIMIT,
                OrdType.STOP,
                OrdType.STOP_LIMIT,
            },
            max_order_size=1000000.0,
            min_order_size=0.01,
            supports_fractional=True,
            latency_ms=50.0,
            commission_rate=0.0005,
            supports_after_hours=True,
            supported_currencies={"USD", "EUR", "GBP", "JPY", "CAD", "AUD"},
            risk_limits={"max_daily_volume": 10000000.0, "max_position": 1000000.0},
        )

        # Manual execution configuration
        self.broker_capabilities["manual"] = BrokerCapabilities(
            broker_type="manual",
            supported_symbols={"*"},  # Manual can handle any symbol
            supported_order_types={
                OrdType.MARKET,
                OrdType.LIMIT,
                OrdType.STOP,
                OrdType.STOP_LIMIT,
            },
            max_order_size=float("inf"),
            min_order_size=0.0,
            supports_fractional=True,
            latency_ms=60000.0,  # 1 minute for human review
            commission_rate=0.0,  # No automated commission
            supports_after_hours=True,
            supported_currencies={"*"},  # Manual can handle any currency
            risk_limits={},  # No automated limits for manual
        )

        # FXCM configuration
        self.broker_capabilities["fxcm"] = BrokerCapabilities(
            broker_type="fxcm",
            supported_symbols={
                "EURUSD",
                "GBPUSD",
                "USDJPY",
                "USDCHF",
                "AUDUSD",
                "USDCAD",
                "NZDUSD",
                "EURJPY",
                "GBPJPY",
                "EURGBP",
                "EURAUD",
                "EURCHF",
            },
            supported_order_types={
                OrdType.MARKET,
                OrdType.LIMIT,
                OrdType.STOP,
                OrdType.STOP_LIMIT,
            },
            max_order_size=50000000.0,  # 50M units
            min_order_size=1000.0,  # 1K units
            supports_fractional=True,
            latency_ms=100.0,
            commission_rate=0.0,  # Spread-based
            supports_after_hours=True,
            supported_currencies={
                "USD",
                "EUR",
                "GBP",
                "JPY",
                "AUD",
                "CAD",
                "CHF",
                "NZD",
            },
            risk_limits={"max_daily_volume": 100000000.0, "max_position": 10000000.0},
        )

        # Native FIX broker configuration
        self.broker_capabilities["fix"] = BrokerCapabilities(
            broker_type="fix",
            supported_symbols={"*"},  # Depends on specific FIX provider
            supported_order_types={
                OrdType.MARKET,
                OrdType.LIMIT,
                OrdType.STOP,
                OrdType.STOP_LIMIT,
            },
            max_order_size=1000000.0,
            min_order_size=0.01,
            supports_fractional=True,
            latency_ms=25.0,  # Typically very fast
            commission_rate=0.0001,
            supports_after_hours=True,
            supported_currencies={"USD", "EUR", "GBP", "JPY"},
            risk_limits={"max_daily_volume": 50000000.0},
        )

    def _initialize_default_rules(self) -> None:
        """Initialize default routing rules."""
        self.routing_rules = [
            # High priority: Large FX orders to FXCM
            RoutingRule(
                name="large_fx_to_fxcm",
                priority=1,
                conditions={
                    "symbols": [
                        "EURUSD",
                        "GBPUSD",
                        "USDJPY",
                        "USDCHF",
                        "AUDUSD",
                        "USDCAD",
                    ],
                    "min_quantity": 1000000.0,  # 1M+ units
                },
                target_brokers=["fxcm"],
                fallback_brokers=["ib", "manual"],
            ),
            # High priority: Manual review for very large orders
            RoutingRule(
                name="large_orders_manual_review",
                priority=2,
                conditions={"min_quantity": 10000000.0},  # 10M+ units/shares
                target_brokers=["manual"],
                fallback_brokers=["ib"],
            ),
            # Medium priority: Small FX orders to IB
            RoutingRule(
                name="small_fx_to_ib",
                priority=10,
                conditions={
                    "symbols": ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"],
                    "max_quantity": 100000.0,  # Under 100K units
                },
                target_brokers=["ib"],
                fallback_brokers=["fxcm", "manual"],
            ),
            # Medium priority: Equity orders to IB
            RoutingRule(
                name="equities_to_ib",
                priority=15,
                conditions={"symbol_patterns": ["*.US", "*.NASDAQ", "*.NYSE"]},
                target_brokers=["ib"],
                fallback_brokers=["manual"],
            ),
            # Low priority: Default routing
            RoutingRule(
                name="default_routing",
                priority=100,
                conditions={},  # Match all
                target_brokers=["ib", "fxcm"],
                fallback_brokers=["manual"],
            ),
        ]

    def route_order(
        self,
        order: FIXMessage,
        strategy: Optional[RoutingStrategy] = None,
        exclude_brokers: Optional[Set[str]] = None,
    ) -> Tuple[str, str]:
        """Route order to appropriate broker.

        Args:
            order: FIX order message to route.
            strategy: Routing strategy override.
            exclude_brokers: Brokers to exclude from routing.

        Returns:
            Tuple of (broker_type, routing_reason).
        """
        strategy = strategy or self.default_strategy
        exclude_brokers = exclude_brokers or set()

        # Reset daily volumes if needed
        self._reset_daily_volumes_if_needed()

        # Extract order details
        symbol = order.get_field(55, "")
        side = order.get_field(54, "")
        quantity = float(order.get_field(38, 0))
        order_type = order.get_field(40, "")

        logger.debug(
            "Routing order: symbol=%s, side=%s, qty=%.2f, type=%s",
            symbol,
            side,
            quantity,
            order_type,
        )

        # Apply routing rules first
        rule_broker = self._apply_routing_rules(order, exclude_brokers)
        if rule_broker:
            return rule_broker, f"routing_rule"

        # Apply strategy-based routing
        if strategy == RoutingStrategy.MANUAL_ONLY:
            return "manual", "manual_only_strategy"

        elif strategy == RoutingStrategy.ROUND_ROBIN:
            return self._route_round_robin(exclude_brokers), "round_robin"

        elif strategy == RoutingStrategy.LEAST_LOADED:
            return self._route_least_loaded(exclude_brokers), "least_loaded"

        elif strategy == RoutingStrategy.SYMBOL_AFFINITY:
            return (
                self._route_symbol_affinity(symbol, exclude_brokers),
                "symbol_affinity",
            )

        elif strategy == RoutingStrategy.PRIMARY_BACKUP:
            return self._route_primary_backup(exclude_brokers), "primary_backup"

        else:  # BEST_EXECUTION
            return self._route_best_execution(order, exclude_brokers), "best_execution"

    def _apply_routing_rules(
        self, order: FIXMessage, exclude_brokers: Set[str]
    ) -> Optional[Tuple[str, str]]:
        """Apply routing rules to determine broker.

        Args:
            order: FIX order message.
            exclude_brokers: Brokers to exclude.

        Returns:
            Tuple of (broker, reason) or None if no rule matches.
        """
        symbol = order.get_field(55, "")
        quantity = float(order.get_field(38, 0))

        # Sort rules by priority
        sorted_rules = sorted(self.routing_rules, key=lambda r: r.priority)

        for rule in sorted_rules:
            if not rule.enabled:
                continue

            # Check if rule conditions match
            if self._rule_matches_order(rule, order):
                # Find available broker from rule targets
                for broker in rule.target_brokers:
                    if broker in exclude_brokers:
                        continue

                    if self._is_broker_available(broker, order):
                        # Check daily volume limits
                        if rule.max_daily_volume:
                            daily_vol = self.daily_volumes.get(broker, 0.0)
                            if daily_vol + quantity > rule.max_daily_volume:
                                continue

                        logger.info(
                            "Order routed by rule '%s': %s -> %s",
                            rule.name,
                            symbol,
                            broker,
                        )
                        return broker, f"rule:{rule.name}"

                # Try fallback brokers
                for broker in rule.fallback_brokers:
                    if broker in exclude_brokers:
                        continue

                    if self._is_broker_available(broker, order):
                        logger.info(
                            "Order routed by rule '%s' fallback: %s -> %s",
                            rule.name,
                            symbol,
                            broker,
                        )
                        return broker, f"rule:{rule.name}:fallback"

        return None

    def _rule_matches_order(self, rule: RoutingRule, order: FIXMessage) -> bool:
        """Check if routing rule matches order.

        Args:
            rule: Routing rule to check.
            order: FIX order message.

        Returns:
            True if rule matches order.
        """
        symbol = order.get_field(55, "")
        quantity = float(order.get_field(38, 0))

        conditions = rule.conditions

        # Check symbol conditions
        if "symbols" in conditions:
            if symbol not in conditions["symbols"]:
                return False

        if "symbol_patterns" in conditions:
            # Simple pattern matching (could be enhanced with regex)
            matches = False
            for pattern in conditions["symbol_patterns"]:
                if pattern.endswith("*"):
                    prefix = pattern[:-1]
                    if symbol.startswith(prefix):
                        matches = True
                        break
                elif pattern.startswith("*"):
                    suffix = pattern[1:]
                    if symbol.endswith(suffix):
                        matches = True
                        break
                elif pattern == symbol:
                    matches = True
                    break

            if not matches:
                return False

        # Check quantity conditions
        if "min_quantity" in conditions:
            if quantity < conditions["min_quantity"]:
                return False

        if "max_quantity" in conditions:
            if quantity > conditions["max_quantity"]:
                return False

        # Check order type conditions
        if "order_types" in conditions:
            order_type = order.get_field(40, "")
            if order_type not in conditions["order_types"]:
                return False

        # Check side conditions
        if "sides" in conditions:
            side = order.get_field(54, "")
            if side not in conditions["sides"]:
                return False

        return True

    def _route_round_robin(self, exclude_brokers: Set[str]) -> str:
        """Route using round-robin strategy."""
        available_brokers = [
            broker
            for broker in self.broker_capabilities.keys()
            if broker not in exclude_brokers and self._is_broker_online(broker)
        ]

        if not available_brokers:
            return "manual"  # Fallback

        # Round-robin selection
        broker = available_brokers[self.round_robin_index % len(available_brokers)]
        self.round_robin_index += 1

        return broker

    def _route_least_loaded(self, exclude_brokers: Set[str]) -> str:
        """Route to least loaded broker."""
        min_load = float("inf")
        best_broker = "manual"

        for broker, metrics in self.broker_metrics.items():
            if broker in exclude_brokers or metrics.status != BrokerStatus.ONLINE:
                continue

            # Use pending orders as load metric
            if metrics.pending_orders < min_load:
                min_load = metrics.pending_orders
                best_broker = broker

        return best_broker

    def _route_symbol_affinity(self, symbol: str, exclude_brokers: Set[str]) -> str:
        """Route based on symbol affinity."""
        # Check if symbol has specific affinity
        if symbol in self.symbol_affinity:
            for broker in self.symbol_affinity[symbol]:
                if broker not in exclude_brokers and self._is_broker_online(broker):
                    return broker

        # Fall back to best execution
        return self._route_best_execution_simple(exclude_brokers)

    def _route_primary_backup(self, exclude_brokers: Set[str]) -> str:
        """Route using primary/backup strategy."""
        # Primary: IB, Backup: FXCM, Final: Manual
        primary_order = ["ib", "fxcm", "manual"]

        for broker in primary_order:
            if broker not in exclude_brokers and self._is_broker_online(broker):
                return broker

        return "manual"  # Ultimate fallback

    def _route_best_execution(
        self, order: FIXMessage, exclude_brokers: Set[str]
    ) -> str:
        """Route using best execution analysis."""
        symbol = order.get_field(55, "")
        quantity = float(order.get_field(38, 0))

        best_score = -1.0
        best_broker = "manual"

        for broker, capabilities in self.broker_capabilities.items():
            if broker in exclude_brokers:
                continue

            if not self._is_broker_available(broker, order):
                continue

            # Calculate execution score
            score = self._calculate_execution_score(broker, symbol, quantity)

            if score > best_score:
                best_score = score
                best_broker = broker

        return best_broker

    def _route_best_execution_simple(self, exclude_brokers: Set[str]) -> str:
        """Simple best execution routing."""
        # Prefer IB for general trading, FXCM for FX
        preference_order = ["ib", "fxcm", "fix", "manual"]

        for broker in preference_order:
            if broker not in exclude_brokers and self._is_broker_online(broker):
                return broker

        return "manual"

    def _calculate_execution_score(
        self, broker: str, symbol: str, quantity: float
    ) -> float:
        """Calculate execution quality score for broker.

        Args:
            broker: Broker type.
            symbol: Trading symbol.
            quantity: Order quantity.

        Returns:
            Execution score (higher is better).
        """
        capabilities = self.broker_capabilities.get(broker)
        metrics = self.broker_metrics.get(broker)

        if not capabilities or not metrics:
            return 0.0

        score = 0.0

        # Penalize if symbol not supported
        if (
            "*" not in capabilities.supported_symbols
            and symbol not in capabilities.supported_symbols
        ):
            return 0.0

        # Penalize if quantity out of range
        if (
            quantity < capabilities.min_order_size
            or quantity > capabilities.max_order_size
        ):
            return 0.0

        # Score based on latency (lower is better)
        if capabilities.latency_ms > 0:
            score += 1000.0 / capabilities.latency_ms

        # Score based on fill rate
        score += metrics.fill_rate_percent / 100.0 * 50.0

        # Score based on low error rate
        score += (100.0 - metrics.error_rate_percent) / 100.0 * 30.0

        # Score based on low commission
        score += (1.0 - capabilities.commission_rate) * 20.0

        # Penalize high load
        score -= metrics.pending_orders * 0.1

        return score

    def _is_broker_available(self, broker: str, order: FIXMessage) -> bool:
        """Check if broker is available for order.

        Args:
            broker: Broker type.
            order: FIX order message.

        Returns:
            True if broker can handle the order.
        """
        if not self._is_broker_online(broker):
            return False

        capabilities = self.broker_capabilities.get(broker)
        if not capabilities:
            return False

        # Check symbol support
        symbol = order.get_field(55, "")
        if (
            "*" not in capabilities.supported_symbols
            and symbol not in capabilities.supported_symbols
        ):
            return False

        # Check order type support
        order_type_str = order.get_field(40, "")
        try:
            order_type = OrdType(order_type_str)
            if order_type not in capabilities.supported_order_types:
                return False
        except ValueError:
            # Unknown order type
            return False

        # Check quantity limits
        quantity = float(order.get_field(38, 0))
        if (
            quantity < capabilities.min_order_size
            or quantity > capabilities.max_order_size
        ):
            return False

        return True

    def _is_broker_online(self, broker: str) -> bool:
        """Check if broker is online and available."""
        metrics = self.broker_metrics.get(broker)
        if not metrics:
            return False

        return metrics.status == BrokerStatus.ONLINE

    def _reset_daily_volumes_if_needed(self) -> None:
        """Reset daily volume tracking if new day."""
        today = datetime.now().date()
        if today > self.last_daily_reset:
            self.daily_volumes.clear()
            self.last_daily_reset = today
            logger.info("Reset daily volume tracking for new day: %s", today)

    def update_broker_metrics(self, broker: str, metrics: BrokerMetrics) -> None:
        """Update broker performance metrics.

        Args:
            broker: Broker type.
            metrics: Updated metrics.
        """
        self.broker_metrics[broker] = metrics
        logger.debug("Updated metrics for broker %s: status=%s", broker, metrics.status)

    def record_order_volume(self, broker: str, volume: float) -> None:
        """Record order volume for daily tracking.

        Args:
            broker: Broker type.
            volume: Order volume to add.
        """
        self.daily_volumes[broker] = self.daily_volumes.get(broker, 0.0) + volume

    def add_routing_rule(self, rule: RoutingRule) -> None:
        """Add custom routing rule.

        Args:
            rule: Routing rule to add.
        """
        self.routing_rules.append(rule)
        self.routing_rules.sort(key=lambda r: r.priority)
        logger.info("Added routing rule: %s (priority %d)", rule.name, rule.priority)

    def remove_routing_rule(self, rule_name: str) -> bool:
        """Remove routing rule by name.

        Args:
            rule_name: Name of rule to remove.

        Returns:
            True if rule was found and removed.
        """
        for i, rule in enumerate(self.routing_rules):
            if rule.name == rule_name:
                del self.routing_rules[i]
                logger.info("Removed routing rule: %s", rule_name)
                return True

        return False

    def set_symbol_affinity(self, symbol: str, preferred_brokers: List[str]) -> None:
        """Set broker affinity for symbol.

        Args:
            symbol: Trading symbol.
            preferred_brokers: Ordered list of preferred brokers.
        """
        self.symbol_affinity[symbol] = preferred_brokers
        logger.info("Set symbol affinity: %s -> %s", symbol, preferred_brokers)

    def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing statistics.

        Returns:
            Dictionary of routing statistics.
        """
        return {
            "total_rules": len(self.routing_rules),
            "active_rules": len([r for r in self.routing_rules if r.enabled]),
            "daily_volumes": self.daily_volumes.copy(),
            "broker_status": {
                broker: metrics.status.value
                for broker, metrics in self.broker_metrics.items()
            },
            "round_robin_index": self.round_robin_index,
            "symbol_affinities": len(self.symbol_affinity),
        }
