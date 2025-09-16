"""
Cluster Manager

Centralized management of FXML4 trading cluster:
- Node lifecycle management and health monitoring
- Service discovery and registration
- Load distribution and failover coordination
- Performance monitoring and optimization
"""

import asyncio
import json
import logging
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set


class NodeStatus(Enum):
    """Node status enumeration"""

    STARTING = "starting"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILING = "failing"
    OFFLINE = "offline"
    DRAINING = "draining"


class NodeType(Enum):
    """Node type enumeration"""

    API = "api"
    TRADING = "trading"
    ML_INFERENCE = "ml_inference"
    WEBSOCKET = "websocket"
    BACKGROUND_WORKER = "background_worker"


@dataclass
class NodeInfo:
    """Information about a cluster node"""

    node_id: str
    node_type: NodeType
    host: str
    port: int
    status: NodeStatus = NodeStatus.STARTING
    cpu_cores: int = 1
    memory_gb: int = 1
    last_heartbeat: float = field(default_factory=time.time)
    startup_time: float = field(default_factory=time.time)
    version: str = "1.0.0"
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Performance metrics
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    active_connections: int = 0
    requests_per_second: float = 0.0
    average_latency_ms: float = 0.0
    error_rate: float = 0.0

    # Trading-specific metrics
    active_positions: int = 0
    orders_per_second: float = 0.0
    pnl_today: float = 0.0

    @property
    def is_healthy(self) -> bool:
        """Check if node is healthy"""
        return self.status in [NodeStatus.HEALTHY, NodeStatus.DEGRADED]

    @property
    def is_available(self) -> bool:
        """Check if node is available for work"""
        return self.status == NodeStatus.HEALTHY

    @property
    def load_score(self) -> float:
        """Calculate node load score (0-1, lower is better)"""
        cpu_score = self.cpu_usage / 100.0
        memory_score = self.memory_usage / 100.0
        latency_score = min(self.average_latency_ms / 100.0, 1.0)  # Normalize to 100ms

        # Weighted combination
        return cpu_score * 0.4 + memory_score * 0.3 + latency_score * 0.3

    def update_metrics(self, metrics: Dict[str, Any]):
        """Update node metrics"""
        self.cpu_usage = metrics.get("cpu_usage", self.cpu_usage)
        self.memory_usage = metrics.get("memory_usage", self.memory_usage)
        self.active_connections = metrics.get(
            "active_connections", self.active_connections
        )
        self.requests_per_second = metrics.get(
            "requests_per_second", self.requests_per_second
        )
        self.average_latency_ms = metrics.get(
            "average_latency_ms", self.average_latency_ms
        )
        self.error_rate = metrics.get("error_rate", self.error_rate)
        self.active_positions = metrics.get("active_positions", self.active_positions)
        self.orders_per_second = metrics.get(
            "orders_per_second", self.orders_per_second
        )
        self.pnl_today = metrics.get("pnl_today", self.pnl_today)
        self.last_heartbeat = time.time()


@dataclass
class ClusterStats:
    """Cluster-wide statistics"""

    total_nodes: int = 0
    healthy_nodes: int = 0
    degraded_nodes: int = 0
    failing_nodes: int = 0
    offline_nodes: int = 0

    total_cpu_cores: int = 0
    total_memory_gb: int = 0
    average_cpu_usage: float = 0.0
    average_memory_usage: float = 0.0

    total_connections: int = 0
    total_requests_per_second: float = 0.0
    average_latency_ms: float = 0.0
    cluster_error_rate: float = 0.0

    # Trading metrics
    total_active_positions: int = 0
    total_orders_per_second: float = 0.0
    cluster_pnl_today: float = 0.0

    @property
    def health_percentage(self) -> float:
        """Percentage of healthy nodes"""
        return (
            (self.healthy_nodes / self.total_nodes * 100)
            if self.total_nodes > 0
            else 0.0
        )

    @property
    def resource_utilization(self) -> float:
        """Overall resource utilization"""
        return (self.average_cpu_usage + self.average_memory_usage) / 2.0


class ClusterManager:
    """
    Central cluster management system for FXML4

    Manages the lifecycle and coordination of all nodes in the trading cluster.
    Provides service discovery, health monitoring, and performance optimization.
    """

    def __init__(self, cluster_id: str = None):
        self.cluster_id = cluster_id or str(uuid.uuid4())
        self.nodes: Dict[str, NodeInfo] = {}
        self.node_types: Dict[NodeType, Set[str]] = defaultdict(set)

        # Health monitoring
        self.heartbeat_timeout = 30.0  # seconds
        self.health_check_interval = 10.0  # seconds

        # Event callbacks
        self.node_added_callbacks: List[Callable[[NodeInfo], None]] = []
        self.node_removed_callbacks: List[Callable[[NodeInfo], None]] = []
        self.node_status_changed_callbacks: List[
            Callable[[NodeInfo, NodeStatus], None]
        ] = []

        # Performance tracking
        self.performance_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=100)
        )

        # Threading
        self.lock = threading.RLock()
        self.running = False
        self.health_check_task = None

        # Logging
        self.logger = logging.getLogger(f"ClusterManager.{self.cluster_id}")

    def start(self):
        """Start the cluster manager"""
        with self.lock:
            if self.running:
                return

            self.running = True
            self.logger.info(f"Starting cluster manager {self.cluster_id}")

            # Start health monitoring
            self.health_check_task = threading.Thread(
                target=self._health_check_loop, daemon=True
            )
            self.health_check_task.start()

    def stop(self):
        """Stop the cluster manager"""
        with self.lock:
            if not self.running:
                return

            self.running = False
            self.logger.info(f"Stopping cluster manager {self.cluster_id}")

            if self.health_check_task:
                self.health_check_task.join(timeout=5.0)

    def register_node(self, node_info: NodeInfo) -> bool:
        """Register a new node in the cluster"""
        with self.lock:
            if node_info.node_id in self.nodes:
                self.logger.warning(f"Node {node_info.node_id} already registered")
                return False

            self.nodes[node_info.node_id] = node_info
            self.node_types[node_info.node_type].add(node_info.node_id)

            self.logger.info(
                f"Registered node {node_info.node_id} ({node_info.node_type.value})"
            )

            # Notify callbacks
            for callback in self.node_added_callbacks:
                try:
                    callback(node_info)
                except Exception as e:
                    self.logger.error(f"Node added callback error: {e}")

            return True

    def unregister_node(self, node_id: str) -> bool:
        """Unregister a node from the cluster"""
        with self.lock:
            if node_id not in self.nodes:
                return False

            node_info = self.nodes[node_id]
            del self.nodes[node_id]
            self.node_types[node_info.node_type].discard(node_id)

            self.logger.info(f"Unregistered node {node_id}")

            # Notify callbacks
            for callback in self.node_removed_callbacks:
                try:
                    callback(node_info)
                except Exception as e:
                    self.logger.error(f"Node removed callback error: {e}")

            return True

    def update_node_metrics(self, node_id: str, metrics: Dict[str, Any]) -> bool:
        """Update node performance metrics"""
        with self.lock:
            if node_id not in self.nodes:
                return False

            node = self.nodes[node_id]
            old_status = node.status

            node.update_metrics(metrics)

            # Update performance history
            self.performance_history[node_id].append(
                {
                    "timestamp": time.time(),
                    "cpu_usage": node.cpu_usage,
                    "memory_usage": node.memory_usage,
                    "latency_ms": node.average_latency_ms,
                    "load_score": node.load_score,
                }
            )

            # Update node status based on metrics
            new_status = self._calculate_node_status(node)
            if new_status != old_status:
                node.status = new_status

                # Notify callbacks
                for callback in self.node_status_changed_callbacks:
                    try:
                        callback(node, old_status)
                    except Exception as e:
                        self.logger.error(f"Status changed callback error: {e}")

            return True

    def _calculate_node_status(self, node: NodeInfo) -> NodeStatus:
        """Calculate node status based on metrics"""
        # Check heartbeat
        time_since_heartbeat = time.time() - node.last_heartbeat
        if time_since_heartbeat > self.heartbeat_timeout:
            return NodeStatus.OFFLINE

        # Check performance metrics
        if node.error_rate > 10.0:  # > 10% error rate
            return NodeStatus.FAILING

        if node.cpu_usage > 90.0 or node.memory_usage > 95.0:
            return NodeStatus.FAILING

        if (
            node.cpu_usage > 80.0
            or node.memory_usage > 85.0
            or node.average_latency_ms > 100.0
        ):
            return NodeStatus.DEGRADED

        return NodeStatus.HEALTHY

    def get_nodes_by_type(
        self, node_type: NodeType, only_available: bool = True
    ) -> List[NodeInfo]:
        """Get nodes by type"""
        with self.lock:
            node_ids = self.node_types[node_type]
            nodes = [
                self.nodes[node_id] for node_id in node_ids if node_id in self.nodes
            ]

            if only_available:
                nodes = [node for node in nodes if node.is_available]

            return nodes

    def get_best_node_for_work(self, node_type: NodeType) -> Optional[NodeInfo]:
        """Get the best available node for work based on load"""
        available_nodes = self.get_nodes_by_type(node_type, only_available=True)

        if not available_nodes:
            return None

        # Return node with lowest load score
        return min(available_nodes, key=lambda node: node.load_score)

    def get_cluster_stats(self) -> ClusterStats:
        """Get comprehensive cluster statistics"""
        with self.lock:
            stats = ClusterStats()

            if not self.nodes:
                return stats

            # Count nodes by status
            status_counts = defaultdict(int)
            for node in self.nodes.values():
                status_counts[node.status] += 1

            stats.total_nodes = len(self.nodes)
            stats.healthy_nodes = status_counts[NodeStatus.HEALTHY]
            stats.degraded_nodes = status_counts[NodeStatus.DEGRADED]
            stats.failing_nodes = status_counts[NodeStatus.FAILING]
            stats.offline_nodes = status_counts[NodeStatus.OFFLINE]

            # Aggregate resources and performance
            total_cpu = sum(node.cpu_cores for node in self.nodes.values())
            total_memory = sum(node.memory_gb for node in self.nodes.values())

            healthy_nodes = [node for node in self.nodes.values() if node.is_healthy]

            if healthy_nodes:
                stats.total_cpu_cores = total_cpu
                stats.total_memory_gb = total_memory
                stats.average_cpu_usage = sum(
                    node.cpu_usage for node in healthy_nodes
                ) / len(healthy_nodes)
                stats.average_memory_usage = sum(
                    node.memory_usage for node in healthy_nodes
                ) / len(healthy_nodes)
                stats.total_connections = sum(
                    node.active_connections for node in healthy_nodes
                )
                stats.total_requests_per_second = sum(
                    node.requests_per_second for node in healthy_nodes
                )
                stats.average_latency_ms = sum(
                    node.average_latency_ms for node in healthy_nodes
                ) / len(healthy_nodes)
                stats.cluster_error_rate = sum(
                    node.error_rate for node in healthy_nodes
                ) / len(healthy_nodes)

                # Trading metrics
                stats.total_active_positions = sum(
                    node.active_positions for node in healthy_nodes
                )
                stats.total_orders_per_second = sum(
                    node.orders_per_second for node in healthy_nodes
                )
                stats.cluster_pnl_today = sum(node.pnl_today for node in healthy_nodes)

            return stats

    def drain_node(self, node_id: str, timeout: float = 300.0) -> bool:
        """Gracefully drain a node (stop accepting new work)"""
        with self.lock:
            if node_id not in self.nodes:
                return False

            node = self.nodes[node_id]
            if node.status == NodeStatus.DRAINING:
                return True

            node.status = NodeStatus.DRAINING
            self.logger.info(f"Started draining node {node_id}")

            # In a real implementation, would notify the node to stop accepting work
            # and wait for existing work to complete

            return True

    def _health_check_loop(self):
        """Background health monitoring loop"""
        while self.running:
            try:
                with self.lock:
                    current_time = time.time()

                    # Check for offline nodes
                    for node in list(self.nodes.values()):
                        if (
                            current_time - node.last_heartbeat
                        ) > self.heartbeat_timeout:
                            if node.status != NodeStatus.OFFLINE:
                                old_status = node.status
                                node.status = NodeStatus.OFFLINE

                                self.logger.warning(f"Node {node.node_id} is offline")

                                # Notify callbacks
                                for callback in self.node_status_changed_callbacks:
                                    try:
                                        callback(node, old_status)
                                    except Exception as e:
                                        self.logger.error(
                                            f"Status changed callback error: {e}"
                                        )

                time.sleep(self.health_check_interval)

            except Exception as e:
                self.logger.error(f"Health check error: {e}")

    def add_node_added_callback(self, callback: Callable[[NodeInfo], None]):
        """Add callback for node addition events"""
        self.node_added_callbacks.append(callback)

    def add_node_removed_callback(self, callback: Callable[[NodeInfo], None]):
        """Add callback for node removal events"""
        self.node_removed_callbacks.append(callback)

    def add_node_status_changed_callback(
        self, callback: Callable[[NodeInfo, NodeStatus], None]
    ):
        """Add callback for node status change events"""
        self.node_status_changed_callbacks.append(callback)

    def get_node_performance_history(
        self, node_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get performance history for a node"""
        with self.lock:
            if node_id not in self.performance_history:
                return []

            history = list(self.performance_history[node_id])
            return history[-limit:] if len(history) > limit else history

    def get_cluster_topology(self) -> Dict[str, Any]:
        """Get cluster topology information"""
        with self.lock:
            topology = {
                "cluster_id": self.cluster_id,
                "nodes": {},
                "node_types": {},
                "stats": self.get_cluster_stats().__dict__,
            }

            # Node details
            for node_id, node in self.nodes.items():
                topology["nodes"][node_id] = {
                    "type": node.node_type.value,
                    "host": node.host,
                    "port": node.port,
                    "status": node.status.value,
                    "load_score": node.load_score,
                    "uptime_seconds": time.time() - node.startup_time,
                }

            # Nodes by type
            for node_type, node_ids in self.node_types.items():
                topology["node_types"][node_type.value] = {
                    "count": len(node_ids),
                    "healthy": len(
                        [nid for nid in node_ids if self.nodes[nid].is_healthy]
                    ),
                    "nodes": list(node_ids),
                }

            return topology


# Example usage and testing
if __name__ == "__main__":
    import random

    print("FXML4 Cluster Manager Test")
    print("=" * 40)

    # Create cluster manager
    manager = ClusterManager("test-cluster")

    # Add event callbacks
    def on_node_added(node: NodeInfo):
        print(f"Node added: {node.node_id} ({node.node_type.value})")

    def on_node_status_changed(node: NodeInfo, old_status: NodeStatus):
        print(f"Node {node.node_id} status: {old_status.value} -> {node.status.value}")

    manager.add_node_added_callback(on_node_added)
    manager.add_node_status_changed_callback(on_node_status_changed)

    # Start manager
    manager.start()

    # Register test nodes
    nodes = []
    for i in range(5):
        node = NodeInfo(
            node_id=f"api-node-{i}",
            node_type=NodeType.API,
            host=f"10.0.1.{i+10}",
            port=8000 + i,
            cpu_cores=8,
            memory_gb=16,
        )
        nodes.append(node)
        manager.register_node(node)

    # Register trading nodes
    for i in range(3):
        node = NodeInfo(
            node_id=f"trading-node-{i}",
            node_type=NodeType.TRADING,
            host=f"10.0.2.{i+10}",
            port=9000 + i,
            cpu_cores=16,
            memory_gb=32,
        )
        nodes.append(node)
        manager.register_node(node)

    # Simulate metric updates
    for _ in range(10):
        for node in nodes:
            metrics = {
                "cpu_usage": random.uniform(20, 90),
                "memory_usage": random.uniform(30, 80),
                "active_connections": random.randint(10, 100),
                "requests_per_second": random.uniform(100, 1000),
                "average_latency_ms": random.uniform(1, 50),
                "error_rate": random.uniform(0, 5),
                "orders_per_second": random.uniform(10, 100),
                "active_positions": random.randint(0, 50),
                "pnl_today": random.uniform(-1000, 2000),
            }
            manager.update_node_metrics(node.node_id, metrics)

    # Get cluster statistics
    stats = manager.get_cluster_stats()
    print(f"\nCluster Statistics:")
    print(f"Total nodes: {stats.total_nodes}")
    print(f"Healthy nodes: {stats.healthy_nodes}")
    print(f"Health percentage: {stats.health_percentage:.1f}%")
    print(f"Average CPU usage: {stats.average_cpu_usage:.1f}%")
    print(f"Average memory usage: {stats.average_memory_usage:.1f}%")
    print(f"Total requests/sec: {stats.total_requests_per_second:.1f}")
    print(f"Average latency: {stats.average_latency_ms:.2f}ms")
    print(f"Total positions: {stats.total_active_positions}")
    print(f"Cluster P&L today: ${stats.cluster_pnl_today:.2f}")

    # Test node selection
    best_api_node = manager.get_best_node_for_work(NodeType.API)
    if best_api_node:
        print(
            f"\nBest API node: {best_api_node.node_id} (load: {best_api_node.load_score:.3f})"
        )

    best_trading_node = manager.get_best_node_for_work(NodeType.TRADING)
    if best_trading_node:
        print(
            f"Best trading node: {best_trading_node.node_id} (load: {best_trading_node.load_score:.3f})"
        )

    # Get topology
    topology = manager.get_cluster_topology()
    print(f"\nCluster topology:")
    for node_type, info in topology["node_types"].items():
        print(f"  {node_type}: {info['healthy']}/{info['count']} healthy")

    # Stop manager
    manager.stop()

    print("\nCluster manager test completed!")
