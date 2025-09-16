"""
Latency-Aware Load Balancer

Intelligent load balancing for FXML4 trading systems:
- Multiple load balancing strategies optimized for trading
- Latency-aware routing for microsecond performance
- Session affinity for stateful trading connections
- Circuit breaker patterns for fault tolerance
"""

import hashlib
import heapq
import random
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .cluster_manager import NodeInfo, NodeStatus


class LoadBalancingStrategy(Enum):
    """Load balancing strategy enumeration"""

    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LEAST_LATENCY = "least_latency"
    CONSISTENT_HASH = "consistent_hash"
    POWER_OF_TWO = "power_of_two"
    ADAPTIVE = "adaptive"


@dataclass
class LoadBalancerStats:
    """Load balancer statistics"""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    circuit_breaker_trips: int = 0
    average_response_time_ms: float = 0.0
    requests_per_second: float = 0.0
    node_selection_time_us: float = 0.0

    @property
    def success_rate(self) -> float:
        """Request success rate percentage"""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100.0

    @property
    def error_rate(self) -> float:
        """Request error rate percentage"""
        return 100.0 - self.success_rate


@dataclass
class NodeMetrics:
    """Per-node load balancing metrics"""

    node_id: str
    request_count: int = 0
    success_count: int = 0
    error_count: int = 0
    total_latency_ms: float = 0.0
    last_request_time: float = field(default_factory=time.time)
    circuit_breaker_state: str = "closed"  # closed, open, half_open
    consecutive_failures: int = 0

    @property
    def average_latency_ms(self) -> float:
        """Average latency for this node"""
        return (
            self.total_latency_ms / self.request_count
            if self.request_count > 0
            else 0.0
        )

    @property
    def success_rate(self) -> float:
        """Success rate for this node"""
        if self.request_count == 0:
            return 100.0
        return (self.success_count / self.request_count) * 100.0


class CircuitBreaker:
    """Circuit breaker implementation for fault tolerance"""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        test_request_threshold: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.test_request_threshold = test_request_threshold

        self.state = "closed"  # closed, open, half_open
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.test_request_count = 0

        self.lock = threading.Lock()

    def can_proceed(self) -> bool:
        """Check if request can proceed through circuit breaker"""
        with self.lock:
            if self.state == "closed":
                return True
            elif self.state == "open":
                if time.time() - self.last_failure_time >= self.recovery_timeout:
                    self.state = "half_open"
                    self.test_request_count = 0
                    return True
                return False
            else:  # half_open
                return self.test_request_count < self.test_request_threshold

    def record_success(self):
        """Record successful request"""
        with self.lock:
            if self.state == "half_open":
                self.test_request_count += 1
                if self.test_request_count >= self.test_request_threshold:
                    self.state = "closed"
                    self.failure_count = 0
            elif self.state == "closed":
                self.failure_count = 0

    def record_failure(self):
        """Record failed request"""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.state == "half_open":
                self.state = "open"
            elif (
                self.state == "closed" and self.failure_count >= self.failure_threshold
            ):
                self.state = "open"


class LatencyAwareLoadBalancer:
    """
    High-performance load balancer optimized for trading systems

    Features:
    - Multiple load balancing algorithms
    - Latency-aware routing for sub-millisecond performance
    - Circuit breaker pattern for fault tolerance
    - Session affinity for stateful connections
    - Real-time performance monitoring
    """

    def __init__(
        self, strategy: LoadBalancingStrategy = LoadBalancingStrategy.LEAST_LATENCY
    ):
        self.strategy = strategy
        self.nodes: List[NodeInfo] = []
        self.node_metrics: Dict[str, NodeMetrics] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}

        # Strategy-specific state
        self.round_robin_index = 0
        self.consistent_hash_ring: Dict[int, str] = {}

        # Session affinity
        self.session_affinity: Dict[str, str] = {}  # session_id -> node_id
        self.session_timeout = 3600.0  # 1 hour

        # Performance tracking
        self.stats = LoadBalancerStats()
        self.request_history: deque = deque(maxlen=1000)

        # Threading
        self.lock = threading.RLock()

        # Adaptive strategy learning
        self.strategy_performance: Dict[LoadBalancingStrategy, float] = defaultdict(
            float
        )
        self.strategy_switch_threshold = (
            0.8  # Switch if current strategy performs < 80%
        )

    def update_nodes(self, nodes: List[NodeInfo]):
        """Update available nodes"""
        with self.lock:
            self.nodes = [node for node in nodes if node.is_available]

            # Initialize metrics for new nodes
            for node in self.nodes:
                if node.node_id not in self.node_metrics:
                    self.node_metrics[node.node_id] = NodeMetrics(node.node_id)
                    self.circuit_breakers[node.node_id] = CircuitBreaker()

            # Clean up metrics for removed nodes
            current_node_ids = {node.node_id for node in self.nodes}
            removed_nodes = set(self.node_metrics.keys()) - current_node_ids
            for node_id in removed_nodes:
                del self.node_metrics[node_id]
                del self.circuit_breakers[node_id]

            # Rebuild consistent hash ring if using that strategy
            if self.strategy == LoadBalancingStrategy.CONSISTENT_HASH:
                self._rebuild_consistent_hash_ring()

    def select_node(
        self,
        session_id: Optional[str] = None,
        request_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[NodeInfo]:
        """Select best node for request"""
        start_time = time.time()

        with self.lock:
            if not self.nodes:
                return None

            # Check session affinity first
            if session_id and session_id in self.session_affinity:
                node_id = self.session_affinity[session_id]
                node = self._find_node_by_id(node_id)
                if node and self._can_use_node(node):
                    self._update_node_selection_time(start_time)
                    return node
                else:
                    # Remove stale session affinity
                    del self.session_affinity[session_id]

            # Select node based on strategy
            node = self._select_node_by_strategy(request_metadata)

            if node and session_id:
                # Create session affinity
                self.session_affinity[session_id] = node.node_id

            self._update_node_selection_time(start_time)
            return node

    def _select_node_by_strategy(
        self, request_metadata: Optional[Dict[str, Any]]
    ) -> Optional[NodeInfo]:
        """Select node based on current strategy"""
        available_nodes = [node for node in self.nodes if self._can_use_node(node)]

        if not available_nodes:
            return None

        if self.strategy == LoadBalancingStrategy.ROUND_ROBIN:
            return self._select_round_robin(available_nodes)
        elif self.strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
            return self._select_least_connections(available_nodes)
        elif self.strategy == LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN:
            return self._select_weighted_round_robin(available_nodes)
        elif self.strategy == LoadBalancingStrategy.LEAST_LATENCY:
            return self._select_least_latency(available_nodes)
        elif self.strategy == LoadBalancingStrategy.CONSISTENT_HASH:
            return self._select_consistent_hash(available_nodes, request_metadata)
        elif self.strategy == LoadBalancingStrategy.POWER_OF_TWO:
            return self._select_power_of_two(available_nodes)
        elif self.strategy == LoadBalancingStrategy.ADAPTIVE:
            return self._select_adaptive(available_nodes)
        else:
            # Default to round robin
            return self._select_round_robin(available_nodes)

    def _can_use_node(self, node: NodeInfo) -> bool:
        """Check if node can be used (circuit breaker check)"""
        if node.node_id not in self.circuit_breakers:
            return True

        return self.circuit_breakers[node.node_id].can_proceed()

    def _select_round_robin(self, nodes: List[NodeInfo]) -> NodeInfo:
        """Round robin selection"""
        node = nodes[self.round_robin_index % len(nodes)]
        self.round_robin_index += 1
        return node

    def _select_least_connections(self, nodes: List[NodeInfo]) -> NodeInfo:
        """Select node with least active connections"""
        return min(nodes, key=lambda n: n.active_connections)

    def _select_weighted_round_robin(self, nodes: List[NodeInfo]) -> NodeInfo:
        """Weighted round robin based on node capacity"""
        # Weight by inverse of load score (lower load = higher weight)
        weights = [1.0 / (node.load_score + 0.1) for node in nodes]
        total_weight = sum(weights)

        # Select based on weighted probability
        r = random.uniform(0, total_weight)
        cumulative_weight = 0

        for i, weight in enumerate(weights):
            cumulative_weight += weight
            if r <= cumulative_weight:
                return nodes[i]

        return nodes[-1]  # Fallback

    def _select_least_latency(self, nodes: List[NodeInfo]) -> NodeInfo:
        """Select node with lowest average latency"""

        # Combine current latency with historical performance
        def get_effective_latency(node: NodeInfo) -> float:
            current_latency = node.average_latency_ms
            metrics = self.node_metrics.get(node.node_id)
            historical_latency = metrics.average_latency_ms if metrics else 0

            # Weight: 70% current, 30% historical
            return current_latency * 0.7 + historical_latency * 0.3

        return min(nodes, key=get_effective_latency)

    def _select_consistent_hash(
        self, nodes: List[NodeInfo], request_metadata: Optional[Dict[str, Any]]
    ) -> NodeInfo:
        """Consistent hash selection"""
        if not request_metadata or "hash_key" not in request_metadata:
            # Fallback to least latency if no hash key
            return self._select_least_latency(nodes)

        hash_key = str(request_metadata["hash_key"])
        hash_value = int(hashlib.md5(hash_key.encode()).hexdigest(), 16)

        # Find the closest node in the hash ring
        if not self.consistent_hash_ring:
            self._rebuild_consistent_hash_ring()

        # Find closest hash value
        closest_hash = min(
            self.consistent_hash_ring.keys(), key=lambda h: abs(h - hash_value)
        )

        node_id = self.consistent_hash_ring[closest_hash]
        return self._find_node_by_id(node_id)

    def _select_power_of_two(self, nodes: List[NodeInfo]) -> NodeInfo:
        """Power of two random choices"""
        if len(nodes) == 1:
            return nodes[0]

        # Select two random nodes and choose the one with better performance
        candidates = random.sample(nodes, min(2, len(nodes)))
        return min(candidates, key=lambda n: n.load_score)

    def _select_adaptive(self, nodes: List[NodeInfo]) -> NodeInfo:
        """Adaptive selection that learns from performance"""
        # Switch strategies based on recent performance
        current_performance = self._calculate_recent_performance()

        if current_performance < self.strategy_switch_threshold:
            # Try a different strategy
            best_strategy = max(self.strategy_performance.items(), key=lambda x: x[1])[
                0
            ]
            if best_strategy != self.strategy:
                old_strategy = self.strategy
                self.strategy = best_strategy
                # Recursively select with new strategy
                result = self._select_node_by_strategy(None)
                self.strategy = old_strategy  # Restore for next time
                return result

        # Use current strategy
        return self._select_least_latency(nodes)  # Default to least latency

    def _rebuild_consistent_hash_ring(self):
        """Rebuild consistent hash ring for available nodes"""
        self.consistent_hash_ring.clear()

        for node in self.nodes:
            # Create multiple hash points per node for better distribution
            for i in range(100):  # 100 virtual nodes per physical node
                hash_key = f"{node.node_id}:{i}"
                hash_value = int(hashlib.md5(hash_key.encode()).hexdigest(), 16)
                self.consistent_hash_ring[hash_value] = node.node_id

    def _find_node_by_id(self, node_id: str) -> Optional[NodeInfo]:
        """Find node by ID"""
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None

    def _update_node_selection_time(self, start_time: float):
        """Update node selection timing statistics"""
        selection_time_us = (time.time() - start_time) * 1_000_000
        self.stats.node_selection_time_us = (
            self.stats.node_selection_time_us * 0.9
        ) + (selection_time_us * 0.1)

    def record_request_result(self, node_id: str, success: bool, latency_ms: float):
        """Record result of request to node"""
        with self.lock:
            # Update global stats
            self.stats.total_requests += 1
            if success:
                self.stats.successful_requests += 1
                self.circuit_breakers[node_id].record_success()
            else:
                self.stats.failed_requests += 1
                self.circuit_breakers[node_id].record_failure()

            # Update node metrics
            if node_id in self.node_metrics:
                metrics = self.node_metrics[node_id]
                metrics.request_count += 1
                if success:
                    metrics.success_count += 1
                    metrics.total_latency_ms += latency_ms
                else:
                    metrics.error_count += 1
                    metrics.consecutive_failures += 1 if not success else 0

                metrics.last_request_time = time.time()

            # Update historical data
            self.request_history.append(
                {
                    "timestamp": time.time(),
                    "node_id": node_id,
                    "success": success,
                    "latency_ms": latency_ms,
                }
            )

            # Update strategy performance tracking
            self.strategy_performance[self.strategy] = (
                self.strategy_performance[self.strategy] * 0.95
                + (1.0 if success else 0.0) * 0.05
            )

    def _calculate_recent_performance(self) -> float:
        """Calculate recent performance (last 100 requests)"""
        recent_requests = list(self.request_history)[-100:]
        if not recent_requests:
            return 1.0

        success_count = sum(1 for req in recent_requests if req["success"])
        return success_count / len(recent_requests)

    def get_node_stats(self, node_id: str) -> Optional[NodeMetrics]:
        """Get statistics for specific node"""
        return self.node_metrics.get(node_id)

    def get_load_balancer_stats(self) -> LoadBalancerStats:
        """Get comprehensive load balancer statistics"""
        with self.lock:
            # Update derived statistics
            if self.stats.total_requests > 0:
                total_latency = sum(
                    req["latency_ms"] for req in self.request_history if req["success"]
                )
                successful_requests = sum(
                    1 for req in self.request_history if req["success"]
                )
                if successful_requests > 0:
                    self.stats.average_response_time_ms = (
                        total_latency / successful_requests
                    )

            # Calculate requests per second
            if self.request_history:
                time_span = (
                    self.request_history[-1]["timestamp"]
                    - self.request_history[0]["timestamp"]
                )
                if time_span > 0:
                    self.stats.requests_per_second = (
                        len(self.request_history) / time_span
                    )

            return self.stats

    def get_comprehensive_report(self) -> Dict[str, Any]:
        """Get comprehensive load balancer report"""
        with self.lock:
            node_reports = {}
            for node_id, metrics in self.node_metrics.items():
                circuit_breaker = self.circuit_breakers[node_id]
                node_reports[node_id] = {
                    "metrics": metrics.__dict__,
                    "circuit_breaker_state": circuit_breaker.state,
                    "failure_count": circuit_breaker.failure_count,
                }

            return {
                "strategy": self.strategy.value,
                "stats": self.stats.__dict__,
                "nodes": node_reports,
                "active_sessions": len(self.session_affinity),
                "strategy_performance": dict(self.strategy_performance),
                "recent_performance": self._calculate_recent_performance(),
            }

    def cleanup_sessions(self):
        """Clean up expired session affinities"""
        with self.lock:
            current_time = time.time()
            expired_sessions = [
                session_id
                for session_id, node_id in self.session_affinity.items()
                if node_id in self.node_metrics
                and current_time - self.node_metrics[node_id].last_request_time
                > self.session_timeout
            ]

            for session_id in expired_sessions:
                del self.session_affinity[session_id]


# Example usage and testing
if __name__ == "__main__":
    import random

    from .cluster_manager import NodeType

    print("FXML4 Load Balancer Test")
    print("=" * 40)

    # Create test nodes
    nodes = []
    for i in range(5):
        node = NodeInfo(
            node_id=f"api-node-{i}",
            node_type=NodeType.API,
            host=f"10.0.1.{i+10}",
            port=8000 + i,
            cpu_cores=8,
            memory_gb=16,
            status=NodeStatus.HEALTHY,
        )
        # Simulate different performance characteristics
        node.cpu_usage = random.uniform(20, 80)
        node.memory_usage = random.uniform(30, 70)
        node.average_latency_ms = random.uniform(1, 20)
        node.active_connections = random.randint(10, 100)
        nodes.append(node)

    # Test different load balancing strategies
    strategies = [
        LoadBalancingStrategy.ROUND_ROBIN,
        LoadBalancingStrategy.LEAST_CONNECTIONS,
        LoadBalancingStrategy.LEAST_LATENCY,
        LoadBalancingStrategy.POWER_OF_TWO,
    ]

    for strategy in strategies:
        print(f"\nTesting {strategy.value}:")

        load_balancer = LatencyAwareLoadBalancer(strategy)
        load_balancer.update_nodes(nodes)

        # Simulate requests
        node_selection_count = defaultdict(int)

        for i in range(100):
            selected_node = load_balancer.select_node(f"session-{i % 20}")
            if selected_node:
                node_selection_count[selected_node.node_id] += 1

                # Simulate request execution
                success = random.random() > 0.05  # 95% success rate
                latency = random.uniform(1, 50)

                load_balancer.record_request_result(
                    selected_node.node_id, success, latency
                )

        # Print distribution
        print("  Selection distribution:")
        for node_id, count in node_selection_count.items():
            print(f"    {node_id}: {count} requests")

        # Print performance stats
        stats = load_balancer.get_load_balancer_stats()
        print(f"  Success rate: {stats.success_rate:.1f}%")
        print(f"  Avg response time: {stats.average_response_time_ms:.2f}ms")
        print(f"  Selection time: {stats.node_selection_time_us:.2f}μs")

    # Test session affinity
    print(f"\nTesting session affinity:")
    load_balancer = LatencyAwareLoadBalancer(LoadBalancingStrategy.LEAST_LATENCY)
    load_balancer.update_nodes(nodes)

    # Make multiple requests with same session ID
    session_id = "test-session-123"
    selected_nodes = []

    for _ in range(10):
        node = load_balancer.select_node(session_id)
        if node:
            selected_nodes.append(node.node_id)
            # Record successful request to maintain affinity
            load_balancer.record_request_result(node.node_id, True, 10.0)

    print(f"Session affinity test - selected nodes: {set(selected_nodes)}")
    print(f"Should be 1 unique node for session affinity")

    # Get comprehensive report
    report = load_balancer.get_comprehensive_report()
    print(f"\nLoad balancer report:")
    print(f"Active sessions: {report['active_sessions']}")
    print(f"Recent performance: {report['recent_performance']:.3f}")

    print("\nLoad balancer test completed!")
