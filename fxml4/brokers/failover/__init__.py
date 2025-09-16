"""
Broker Failover Management for FXML4 Trading System.

Provides automatic failover capabilities between brokers to ensure
business continuity during connection failures.
"""

from .health_monitor import BrokerHealthMonitor
from .notification import FailoverNotificationService
from .service import BrokerFailoverService

__all__ = [
    "BrokerFailoverService",
    "BrokerHealthMonitor",
    "FailoverNotificationService",
]
