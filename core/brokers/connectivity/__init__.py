"""
FXML4 Broker Connectivity Package

This package provides comprehensive business continuity and connection management
for the FXML4 trading system, ensuring reliable broker connectivity and
automatic failover capabilities.

Key Components:
- BusinessContinuityManager: Core business continuity orchestration
- ConnectionMonitor: Real-time connection health monitoring
- FailoverOrchestrator: Automated failover decision making and execution

Features:
- Sub-30 second recovery from broker disconnections
- Automatic failover to backup brokers
- Trading state preservation and restoration
- Real-time connection health monitoring
- Comprehensive performance metrics and reporting
"""

from .business_continuity_manager import (
    BrokerConnection,
    BusinessContinuityManager,
    BusinessContinuityValidator,
    ConnectionStatus,
    FailoverEvent,
    FailoverTrigger,
    RecoveryMetrics,
    RecoveryPhase,
    TradingState,
)
from .connection_monitor import (
    AlertSeverity,
    ConnectionAlert,
    ConnectionMetrics,
    ConnectionMonitor,
    HealthCheckResult,
    HealthStatus,
    NetworkTester,
)
from .failover_orchestrator import (
    BrokerCapability,
    FailoverCandidate,
    FailoverDecision,
    FailoverExecution,
    FailoverOrchestrator,
    FailoverPhase,
    FailoverReason,
    TradingStateSnapshot,
)

__all__ = [
    # Business Continuity Manager
    "BusinessContinuityManager",
    "BusinessContinuityValidator",
    "ConnectionStatus",
    "FailoverTrigger",
    "RecoveryPhase",
    "BrokerConnection",
    "FailoverEvent",
    "TradingState",
    "RecoveryMetrics",
    # Connection Monitor
    "ConnectionMonitor",
    "HealthStatus",
    "AlertSeverity",
    "ConnectionMetrics",
    "HealthCheckResult",
    "ConnectionAlert",
    "NetworkTester",
    # Failover Orchestrator
    "FailoverOrchestrator",
    "FailoverDecision",
    "FailoverReason",
    "FailoverPhase",
    "BrokerCapability",
    "FailoverCandidate",
    "TradingStateSnapshot",
    "FailoverExecution",
]

__version__ = "1.0.0"
__author__ = "FXML4 Development Team"
__description__ = (
    "Business continuity and broker connectivity management for FXML4 trading system"
)
