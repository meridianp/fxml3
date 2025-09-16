"""
Auto Scaler for FXML4 Trading Infrastructure

Intelligent auto-scaling based on trading metrics and system performance:
- Trading volume-aware scaling policies
- Latency-based scaling decisions
- Cost-optimized scaling strategies
- Predictive scaling for market events
"""

import asyncio
import json
import logging
import statistics
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from .cluster_manager import ClusterStats, NodeInfo, NodeType


class ScalingDirection(Enum):
    """Scaling direction enumeration"""

    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    NO_CHANGE = "no_change"


class ScalingTrigger(Enum):
    """Scaling trigger types"""

    CPU_UTILIZATION = "cpu_utilization"
    MEMORY_UTILIZATION = "memory_utilization"
    LATENCY_THRESHOLD = "latency_threshold"
    REQUEST_RATE = "request_rate"
    QUEUE_LENGTH = "queue_length"
    TRADING_VOLUME = "trading_volume"
    ERROR_RATE = "error_rate"
    CUSTOM_METRIC = "custom_metric"


@dataclass
class ScalingMetrics:
    """Current metrics for scaling decisions"""

    timestamp: float = field(default_factory=time.time)

    # System metrics
    cpu_utilization: float = 0.0
    memory_utilization: float = 0.0
    network_utilization: float = 0.0
    disk_utilization: float = 0.0

    # Performance metrics
    average_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    request_rate: float = 0.0
    error_rate: float = 0.0

    # Trading-specific metrics
    orders_per_second: float = 0.0
    positions_count: int = 0
    trading_volume_usd: float = 0.0
    active_strategies: int = 0
    market_volatility: float = 0.0

    # Queue metrics
    order_queue_length: int = 0
    execution_queue_length: int = 0
    data_processing_queue_length: int = 0

    # Business metrics
    revenue_per_hour: float = 0.0
    cost_per_hour: float = 0.0
    profit_margin: float = 0.0


@dataclass
class ScalingRule:
    """Individual scaling rule configuration"""

    name: str
    trigger: ScalingTrigger
    node_type: NodeType

    # Thresholds
    scale_up_threshold: float
    scale_down_threshold: float

    # Constraints
    min_instances: int = 1
    max_instances: int = 10
    cooldown_seconds: float = 300.0  # 5 minutes

    # Scaling behavior
    scale_up_step: int = 1
    scale_down_step: int = 1

    # Evaluation period
    evaluation_period_seconds: float = 60.0
    evaluation_points: int = 3

    # Weights and priorities
    priority: int = 1
    weight: float = 1.0
    enabled: bool = True


@dataclass
class ScalingPolicy:
    """Complete scaling policy with multiple rules"""

    name: str
    rules: List[ScalingRule] = field(default_factory=list)

    # Global constraints
    max_total_instances: int = 50
    max_cost_per_hour: float = 1000.0

    # Policy behavior
    aggressive_scaling: bool = False
    predictive_scaling: bool = True
    cost_optimization: bool = True

    # Market hours consideration
    market_hours_multiplier: float = 1.5
    off_hours_scale_down: bool = True


@dataclass
class ScalingDecision:
    """Scaling decision with reasoning"""

    timestamp: float = field(default_factory=time.time)
    node_type: NodeType
    direction: ScalingDirection
    instances_change: int = 0
    current_instances: int = 0
    target_instances: int = 0

    # Decision reasoning
    triggered_rules: List[str] = field(default_factory=list)
    metric_values: Dict[str, float] = field(default_factory=dict)
    confidence_score: float = 0.0
    estimated_cost_impact: float = 0.0

    # Constraints applied
    constraints_applied: List[str] = field(default_factory=list)


class MarketConditionAnalyzer:
    """Analyzes market conditions for predictive scaling"""

    def __init__(self):
        self.volatility_history: deque = deque(maxlen=100)
        self.volume_history: deque = deque(maxlen=100)
        self.news_sentiment: float = 0.0  # -1 to 1

    def update_market_data(
        self, volatility: float, volume: float, sentiment: Optional[float] = None
    ):
        """Update market condition data"""
        self.volatility_history.append(volatility)
        self.volume_history.append(volume)
        if sentiment is not None:
            self.news_sentiment = sentiment

    def predict_scaling_need(self, hours_ahead: int = 1) -> Dict[str, float]:
        """Predict scaling need based on market conditions"""
        if len(self.volatility_history) < 10:
            return {"scaling_factor": 1.0, "confidence": 0.0}

        # Calculate trends
        recent_volatility = statistics.mean(list(self.volatility_history)[-10:])
        avg_volatility = statistics.mean(self.volatility_history)
        volatility_trend = (
            recent_volatility / avg_volatility if avg_volatility > 0 else 1.0
        )

        recent_volume = statistics.mean(list(self.volume_history)[-10:])
        avg_volume = statistics.mean(self.volume_history)
        volume_trend = recent_volume / avg_volume if avg_volume > 0 else 1.0

        # Predict scaling factor
        base_scaling = (volatility_trend + volume_trend) / 2.0
        sentiment_factor = 1.0 + (abs(self.news_sentiment) * 0.2)

        scaling_factor = base_scaling * sentiment_factor
        confidence = min(len(self.volatility_history) / 100.0, 1.0)

        return {
            "scaling_factor": max(
                0.5, min(3.0, scaling_factor)
            ),  # Clamp between 0.5x and 3x
            "confidence": confidence,
            "volatility_trend": volatility_trend,
            "volume_trend": volume_trend,
            "sentiment_factor": sentiment_factor,
        }


class AutoScaler:
    """
    Intelligent auto-scaler for FXML4 trading infrastructure

    Features:
    - Multiple scaling policies with rule-based decisions
    - Trading-aware metrics and thresholds
    - Predictive scaling for market events
    - Cost optimization and resource constraints
    - Real-time performance monitoring
    """

    def __init__(self):
        self.policies: Dict[str, ScalingPolicy] = {}
        self.active_policy: Optional[str] = None

        # Metrics and history
        self.current_metrics = ScalingMetrics()
        self.metrics_history: deque = deque(maxlen=1000)
        self.scaling_history: deque = deque(maxlen=100)

        # Node tracking
        self.current_instances: Dict[NodeType, int] = defaultdict(int)
        self.target_instances: Dict[NodeType, int] = defaultdict(int)
        self.last_scaling_time: Dict[NodeType, float] = defaultdict(float)

        # Market analysis
        self.market_analyzer = MarketConditionAnalyzer()

        # Callbacks for scaling actions
        self.scale_up_callbacks: List[Callable[[NodeType, int], None]] = []
        self.scale_down_callbacks: List[Callable[[NodeType, int], None]] = []

        # Control
        self.running = False
        self.evaluation_task = None
        self.lock = threading.RLock()

        self.logger = logging.getLogger("AutoScaler")

    def add_scaling_policy(self, policy: ScalingPolicy):
        """Add scaling policy"""
        self.policies[policy.name] = policy
        self.logger.info(f"Added scaling policy: {policy.name}")

    def set_active_policy(self, policy_name: str):
        """Set active scaling policy"""
        if policy_name in self.policies:
            self.active_policy = policy_name
            self.logger.info(f"Activated scaling policy: {policy_name}")
        else:
            raise ValueError(f"Policy {policy_name} not found")

    def update_metrics(self, metrics: ScalingMetrics):
        """Update current metrics for scaling evaluation"""
        with self.lock:
            self.current_metrics = metrics
            self.metrics_history.append(metrics)

            # Update market analyzer
            self.market_analyzer.update_market_data(
                metrics.market_volatility, metrics.trading_volume_usd
            )

    def update_instance_counts(self, instance_counts: Dict[NodeType, int]):
        """Update current instance counts"""
        with self.lock:
            self.current_instances.update(instance_counts)

    async def start(self, evaluation_interval: float = 30.0):
        """Start auto-scaling evaluation loop"""
        if self.running:
            return

        self.running = True
        self.logger.info("Starting auto-scaler")

        self.evaluation_task = asyncio.create_task(
            self._evaluation_loop(evaluation_interval)
        )

    async def stop(self):
        """Stop auto-scaler"""
        if not self.running:
            return

        self.running = False
        self.logger.info("Stopping auto-scaler")

        if self.evaluation_task:
            self.evaluation_task.cancel()
            try:
                await self.evaluation_task
            except asyncio.CancelledError:
                pass

    async def _evaluation_loop(self, interval: float):
        """Main evaluation loop"""
        while self.running:
            try:
                if self.active_policy:
                    scaling_decisions = self.evaluate_scaling_needs()

                    for decision in scaling_decisions:
                        await self._execute_scaling_decision(decision)

                await asyncio.sleep(interval)

            except Exception as e:
                self.logger.error(f"Evaluation loop error: {e}")
                await asyncio.sleep(interval)

    def evaluate_scaling_needs(self) -> List[ScalingDecision]:
        """Evaluate scaling needs based on active policy"""
        if not self.active_policy:
            return []

        with self.lock:
            policy = self.policies[self.active_policy]
            decisions = []

            # Group rules by node type for combined evaluation
            rules_by_type: Dict[NodeType, List[ScalingRule]] = defaultdict(list)
            for rule in policy.rules:
                if rule.enabled:
                    rules_by_type[rule.node_type].append(rule)

            # Evaluate each node type
            for node_type, rules in rules_by_type.items():
                decision = self._evaluate_node_type_scaling(node_type, rules, policy)
                if decision.direction != ScalingDirection.NO_CHANGE:
                    decisions.append(decision)

            return decisions

    def _evaluate_node_type_scaling(
        self, node_type: NodeType, rules: List[ScalingRule], policy: ScalingPolicy
    ) -> ScalingDecision:
        """Evaluate scaling for specific node type"""
        current_instances = self.current_instances[node_type]

        # Collect rule evaluations
        scale_up_votes = 0
        scale_down_votes = 0
        triggered_rules = []
        metric_values = {}

        for rule in rules:
            # Check cooldown period
            if (
                time.time() - self.last_scaling_time[node_type]
            ) < rule.cooldown_seconds:
                continue

            # Get metric value for this rule
            metric_value = self._get_metric_value(rule.trigger)
            metric_values[rule.trigger.value] = metric_value

            # Evaluate rule
            if self._should_scale_up(rule, metric_value):
                scale_up_votes += rule.priority * rule.weight
                triggered_rules.append(f"{rule.name} (scale up)")
            elif self._should_scale_down(rule, metric_value):
                scale_down_votes += rule.priority * rule.weight
                triggered_rules.append(f"{rule.name} (scale down)")

        # Make scaling decision
        decision = ScalingDecision(
            node_type=node_type,
            current_instances=current_instances,
            triggered_rules=triggered_rules,
            metric_values=metric_values,
        )

        # Determine direction and magnitude
        if scale_up_votes > scale_down_votes:
            decision.direction = ScalingDirection.SCALE_UP
            decision.instances_change = self._calculate_scale_up_amount(rules, policy)
        elif scale_down_votes > scale_up_votes:
            decision.direction = ScalingDirection.SCALE_DOWN
            decision.instances_change = self._calculate_scale_down_amount(rules, policy)
        else:
            decision.direction = ScalingDirection.NO_CHANGE
            decision.instances_change = 0

        # Apply constraints
        decision = self._apply_constraints(decision, rules, policy)

        # Calculate confidence and cost impact
        decision.confidence_score = self._calculate_confidence_score(
            scale_up_votes, scale_down_votes, len(rules)
        )
        decision.estimated_cost_impact = self._estimate_cost_impact(decision)

        return decision

    def _get_metric_value(self, trigger: ScalingTrigger) -> float:
        """Get current metric value for trigger"""
        metrics = self.current_metrics

        metric_map = {
            ScalingTrigger.CPU_UTILIZATION: metrics.cpu_utilization,
            ScalingTrigger.MEMORY_UTILIZATION: metrics.memory_utilization,
            ScalingTrigger.LATENCY_THRESHOLD: metrics.average_latency_ms,
            ScalingTrigger.REQUEST_RATE: metrics.request_rate,
            ScalingTrigger.TRADING_VOLUME: metrics.trading_volume_usd,
            ScalingTrigger.ERROR_RATE: metrics.error_rate,
            ScalingTrigger.QUEUE_LENGTH: metrics.order_queue_length,
        }

        return metric_map.get(trigger, 0.0)

    def _should_scale_up(self, rule: ScalingRule, metric_value: float) -> bool:
        """Check if rule indicates scale up"""
        if len(self.metrics_history) < rule.evaluation_points:
            return False

        # Check recent metric history
        recent_metrics = list(self.metrics_history)[-rule.evaluation_points :]
        recent_values = [
            self._get_metric_value_from_metrics(rule.trigger, m) for m in recent_metrics
        ]

        # All recent values must exceed threshold
        return all(value >= rule.scale_up_threshold for value in recent_values)

    def _should_scale_down(self, rule: ScalingRule, metric_value: float) -> bool:
        """Check if rule indicates scale down"""
        if len(self.metrics_history) < rule.evaluation_points:
            return False

        # Check recent metric history
        recent_metrics = list(self.metrics_history)[-rule.evaluation_points :]
        recent_values = [
            self._get_metric_value_from_metrics(rule.trigger, m) for m in recent_metrics
        ]

        # All recent values must be below threshold
        return all(value <= rule.scale_down_threshold for value in recent_values)

    def _get_metric_value_from_metrics(
        self, trigger: ScalingTrigger, metrics: ScalingMetrics
    ) -> float:
        """Get metric value from specific metrics object"""
        metric_map = {
            ScalingTrigger.CPU_UTILIZATION: metrics.cpu_utilization,
            ScalingTrigger.MEMORY_UTILIZATION: metrics.memory_utilization,
            ScalingTrigger.LATENCY_THRESHOLD: metrics.average_latency_ms,
            ScalingTrigger.REQUEST_RATE: metrics.request_rate,
            ScalingTrigger.TRADING_VOLUME: metrics.trading_volume_usd,
            ScalingTrigger.ERROR_RATE: metrics.error_rate,
            ScalingTrigger.QUEUE_LENGTH: metrics.order_queue_length,
        }

        return metric_map.get(trigger, 0.0)

    def _calculate_scale_up_amount(
        self, rules: List[ScalingRule], policy: ScalingPolicy
    ) -> int:
        """Calculate number of instances to scale up"""
        # Use the maximum scale up step from triggered rules
        max_step = max((rule.scale_up_step for rule in rules), default=1)

        # Apply predictive scaling if enabled
        if policy.predictive_scaling:
            prediction = self.market_analyzer.predict_scaling_need()
            scaling_factor = prediction["scaling_factor"]
            if scaling_factor > 1.2:  # Only scale up if prediction is significant
                max_step = int(max_step * min(scaling_factor, 2.0))

        return max_step

    def _calculate_scale_down_amount(
        self, rules: List[ScalingRule], policy: ScalingPolicy
    ) -> int:
        """Calculate number of instances to scale down"""
        # Use the minimum scale down step from triggered rules
        min_step = min((rule.scale_down_step for rule in rules), default=1)

        # Be more conservative with scale down
        return min_step

    def _apply_constraints(
        self, decision: ScalingDecision, rules: List[ScalingRule], policy: ScalingPolicy
    ) -> ScalingDecision:
        """Apply constraints to scaling decision"""
        constraints_applied = []

        # Find applicable constraints for this node type
        min_instances = min((rule.min_instances for rule in rules), default=1)
        max_instances = max((rule.max_instances for rule in rules), default=10)

        # Calculate target instances
        if decision.direction == ScalingDirection.SCALE_UP:
            target = decision.current_instances + decision.instances_change
        elif decision.direction == ScalingDirection.SCALE_DOWN:
            target = decision.current_instances - decision.instances_change
        else:
            target = decision.current_instances

        # Apply min/max constraints
        if target < min_instances:
            target = min_instances
            constraints_applied.append(f"min_instances ({min_instances})")

        if target > max_instances:
            target = max_instances
            constraints_applied.append(f"max_instances ({max_instances})")

        # Apply global constraints
        total_instances = sum(self.current_instances.values())
        if (
            total_instances >= policy.max_total_instances
            and decision.direction == ScalingDirection.SCALE_UP
        ):
            target = decision.current_instances
            decision.direction = ScalingDirection.NO_CHANGE
            constraints_applied.append(
                f"max_total_instances ({policy.max_total_instances})"
            )

        # Update decision
        decision.target_instances = target
        decision.instances_change = abs(target - decision.current_instances)
        decision.constraints_applied = constraints_applied

        # Update direction based on final target
        if target > decision.current_instances:
            decision.direction = ScalingDirection.SCALE_UP
        elif target < decision.current_instances:
            decision.direction = ScalingDirection.SCALE_DOWN
        else:
            decision.direction = ScalingDirection.NO_CHANGE

        return decision

    def _calculate_confidence_score(
        self, scale_up_votes: float, scale_down_votes: float, num_rules: int
    ) -> float:
        """Calculate confidence score for scaling decision"""
        if num_rules == 0:
            return 0.0

        total_votes = scale_up_votes + scale_down_votes
        if total_votes == 0:
            return 0.0

        # Higher difference in votes = higher confidence
        vote_difference = abs(scale_up_votes - scale_down_votes)
        max_possible_difference = num_rules * 1.0  # Assuming weight=1, priority=1

        return min(vote_difference / max_possible_difference, 1.0)

    def _estimate_cost_impact(self, decision: ScalingDecision) -> float:
        """Estimate cost impact of scaling decision"""
        # Placeholder cost estimation
        cost_per_instance_per_hour = {
            NodeType.API: 0.50,
            NodeType.TRADING: 2.00,
            NodeType.ML_INFERENCE: 1.50,
            NodeType.WEBSOCKET: 0.30,
            NodeType.BACKGROUND_WORKER: 0.25,
        }

        cost_per_hour = cost_per_instance_per_hour.get(decision.node_type, 1.00)

        if decision.direction == ScalingDirection.SCALE_UP:
            return decision.instances_change * cost_per_hour
        elif decision.direction == ScalingDirection.SCALE_DOWN:
            return -decision.instances_change * cost_per_hour
        else:
            return 0.0

    async def _execute_scaling_decision(self, decision: ScalingDecision):
        """Execute scaling decision"""
        with self.lock:
            self.scaling_history.append(decision)

            if decision.direction == ScalingDirection.SCALE_UP:
                self.logger.info(
                    f"Scaling up {decision.node_type.value}: "
                    f"{decision.current_instances} -> {decision.target_instances} "
                    f"(+{decision.instances_change})"
                )

                # Notify scale up callbacks
                for callback in self.scale_up_callbacks:
                    try:
                        callback(decision.node_type, decision.instances_change)
                    except Exception as e:
                        self.logger.error(f"Scale up callback error: {e}")

            elif decision.direction == ScalingDirection.SCALE_DOWN:
                self.logger.info(
                    f"Scaling down {decision.node_type.value}: "
                    f"{decision.current_instances} -> {decision.target_instances} "
                    f"(-{decision.instances_change})"
                )

                # Notify scale down callbacks
                for callback in self.scale_down_callbacks:
                    try:
                        callback(decision.node_type, decision.instances_change)
                    except Exception as e:
                        self.logger.error(f"Scale down callback error: {e}")

            # Update tracking
            self.target_instances[decision.node_type] = decision.target_instances
            self.last_scaling_time[decision.node_type] = time.time()

    def add_scale_up_callback(self, callback: Callable[[NodeType, int], None]):
        """Add callback for scale up events"""
        self.scale_up_callbacks.append(callback)

    def add_scale_down_callback(self, callback: Callable[[NodeType, int], None]):
        """Add callback for scale down events"""
        self.scale_down_callbacks.append(callback)

    def get_scaling_history(self, limit: int = 50) -> List[ScalingDecision]:
        """Get recent scaling decisions"""
        with self.lock:
            history = list(self.scaling_history)
            return history[-limit:] if len(history) > limit else history

    def get_scaling_summary(self) -> Dict[str, Any]:
        """Get comprehensive scaling summary"""
        with self.lock:
            recent_decisions = self.get_scaling_history(20)

            return {
                "active_policy": self.active_policy,
                "current_instances": dict(self.current_instances),
                "target_instances": dict(self.target_instances),
                "recent_decisions": len(recent_decisions),
                "total_scale_ups": sum(
                    1
                    for d in recent_decisions
                    if d.direction == ScalingDirection.SCALE_UP
                ),
                "total_scale_downs": sum(
                    1
                    for d in recent_decisions
                    if d.direction == ScalingDirection.SCALE_DOWN
                ),
                "current_metrics": self.current_metrics.__dict__,
                "market_prediction": self.market_analyzer.predict_scaling_need(),
            }


# Predefined scaling policies
def create_standard_trading_policy() -> ScalingPolicy:
    """Create standard trading scaling policy"""
    rules = [
        # API servers based on request rate and latency
        ScalingRule(
            name="API High Request Rate",
            trigger=ScalingTrigger.REQUEST_RATE,
            node_type=NodeType.API,
            scale_up_threshold=1000.0,  # requests/second
            scale_down_threshold=300.0,
            min_instances=2,
            max_instances=20,
            scale_up_step=2,
            scale_down_step=1,
            priority=2,
        ),
        ScalingRule(
            name="API High Latency",
            trigger=ScalingTrigger.LATENCY_THRESHOLD,
            node_type=NodeType.API,
            scale_up_threshold=100.0,  # milliseconds
            scale_down_threshold=20.0,
            min_instances=2,
            max_instances=20,
            scale_up_step=1,
            scale_down_step=1,
            priority=3,
        ),
        # Trading nodes based on volume and queue length
        ScalingRule(
            name="Trading High Volume",
            trigger=ScalingTrigger.TRADING_VOLUME,
            node_type=NodeType.TRADING,
            scale_up_threshold=1_000_000.0,  # USD volume
            scale_down_threshold=100_000.0,
            min_instances=1,
            max_instances=10,
            scale_up_step=1,
            scale_down_step=1,
            priority=3,
        ),
        ScalingRule(
            name="Trading Queue Length",
            trigger=ScalingTrigger.QUEUE_LENGTH,
            node_type=NodeType.TRADING,
            scale_up_threshold=100.0,
            scale_down_threshold=10.0,
            min_instances=1,
            max_instances=10,
            scale_up_step=2,
            scale_down_step=1,
            priority=2,
        ),
    ]

    return ScalingPolicy(
        name="Standard Trading",
        rules=rules,
        max_total_instances=50,
        max_cost_per_hour=500.0,
        predictive_scaling=True,
        cost_optimization=True,
    )


# Example usage and testing
if __name__ == "__main__":
    import random

    async def main():
        print("FXML4 Auto Scaler Test")
        print("=" * 40)

        # Create auto scaler
        scaler = AutoScaler()

        # Add callbacks
        def on_scale_up(node_type: NodeType, instances: int):
            print(f"SCALE UP: {node_type.value} +{instances}")

        def on_scale_down(node_type: NodeType, instances: int):
            print(f"SCALE DOWN: {node_type.value} -{instances}")

        scaler.add_scale_up_callback(on_scale_up)
        scaler.add_scale_down_callback(on_scale_down)

        # Add standard trading policy
        policy = create_standard_trading_policy()
        scaler.add_scaling_policy(policy)
        scaler.set_active_policy("Standard Trading")

        # Initialize instance counts
        scaler.update_instance_counts(
            {
                NodeType.API: 3,
                NodeType.TRADING: 2,
                NodeType.ML_INFERENCE: 1,
                NodeType.WEBSOCKET: 2,
            }
        )

        # Start auto scaler
        await scaler.start(evaluation_interval=10.0)

        # Simulate metrics over time
        for i in range(20):
            # Generate realistic metrics
            base_load = 50.0

            # Simulate increasing load over time
            load_multiplier = 1.0 + (i / 20.0) * 2.0

            # Add some randomness
            noise = random.uniform(0.8, 1.2)

            metrics = ScalingMetrics(
                cpu_utilization=min(95.0, base_load * load_multiplier * noise),
                memory_utilization=min(90.0, base_load * load_multiplier * noise * 0.8),
                average_latency_ms=max(1.0, 20.0 * load_multiplier * noise),
                request_rate=500.0 * load_multiplier * noise,
                trading_volume_usd=100_000.0 * load_multiplier * noise,
                orders_per_second=10.0 * load_multiplier * noise,
                order_queue_length=int(20.0 * load_multiplier * noise),
                error_rate=min(10.0, 1.0 * load_multiplier * noise),
                market_volatility=random.uniform(0.1, 0.8),
            )

            scaler.update_metrics(metrics)

            # Print current state
            if i % 5 == 0:
                summary = scaler.get_scaling_summary()
                print(f"\nIteration {i}:")
                print(f"  CPU: {metrics.cpu_utilization:.1f}%")
                print(f"  Latency: {metrics.average_latency_ms:.1f}ms")
                print(f"  Request rate: {metrics.request_rate:.1f}/s")
                print(f"  Trading volume: ${metrics.trading_volume_usd:,.0f}")
                print(f"  Current instances: {summary['current_instances']}")
                print(f"  Recent decisions: {summary['recent_decisions']}")

            await asyncio.sleep(1.0)  # Wait 1 second between updates

        # Stop auto scaler
        await scaler.stop()

        # Print final summary
        print("\nFinal Scaling Summary:")
        summary = scaler.get_scaling_summary()
        print(f"Total scale ups: {summary['total_scale_ups']}")
        print(f"Total scale downs: {summary['total_scale_downs']}")
        print(f"Final instances: {summary['current_instances']}")

        # Print scaling history
        history = scaler.get_scaling_history()
        print(f"\nScaling History ({len(history)} decisions):")
        for decision in history[-5:]:  # Last 5 decisions
            print(
                f"  {decision.timestamp:.0f}: {decision.node_type.value} "
                f"{decision.direction.value} {decision.instances_change} "
                f"(confidence: {decision.confidence_score:.2f})"
            )

        print("\nAuto scaler test completed!")

    # Run the test
    asyncio.run(main())
