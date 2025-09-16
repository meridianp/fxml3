"""
FXML4 Horizontal Scaling Module

Implements enterprise-grade horizontal scaling for high-frequency trading:
- Dynamic cluster management with auto-discovery
- Intelligent load balancing with latency awareness
- Auto-scaling based on trading volume and performance metrics
- Graceful node management with position migration
"""

from .auto_scaler import AutoScaler, ScalingMetrics, ScalingPolicy
from .cluster_manager import ClusterManager, ClusterStats, NodeInfo
from .load_balancer import LatencyAwareLoadBalancer, LoadBalancingStrategy
from .node_discovery import HealthChecker, NodeDiscovery

__all__ = [
    "ClusterManager",
    "NodeInfo",
    "ClusterStats",
    "LatencyAwareLoadBalancer",
    "LoadBalancingStrategy",
    "NodeDiscovery",
    "HealthChecker",
    "AutoScaler",
    "ScalingPolicy",
    "ScalingMetrics",
]
