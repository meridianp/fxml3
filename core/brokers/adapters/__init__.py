"""Broker Adapter Framework.

This module provides the base framework for broker adapters,
including abstract interfaces and common functionality.
"""

from .base import AdapterConfig, BrokerAdapter, BrokerConnection

# Native FIX Protocol Broker Adapter
from .fix_adapter import FixBrokerAdapter
from .fix_rabbitmq_adapter import FixRabbitMQAdapter

# FXCM Broker Adapter
from .fxcm_adapter import FXCMBrokerAdapter
from .fxcm_rabbitmq_adapter import FXCMRabbitMQAdapter

# Interactive Brokers Adapter
from .ib_adapter import IBBrokerAdapter
from .ib_fix_translator import IBFIXTranslator
from .ib_rabbitmq_adapter import IBRabbitMQAdapter
from .manager import BrokerAdapterManager

# Manual Broker Adapter
from .manual_adapter import ApprovalStatus, ManualBrokerAdapter, PendingOrder
from .manual_rabbitmq_adapter import ManualRabbitMQAdapter
from .registry import BrokerAdapterRegistry

__all__ = [
    # Base framework
    "BrokerAdapter",
    "BrokerConnection",
    "AdapterConfig",
    "BrokerAdapterManager",
    "BrokerAdapterRegistry",
    # FIX Protocol adapter
    "FixBrokerAdapter",
    "FixRabbitMQAdapter",
    # Interactive Brokers adapter
    "IBBrokerAdapter",
    "IBRabbitMQAdapter",
    "IBFIXTranslator",
    # FXCM adapter
    "FXCMBrokerAdapter",
    "FXCMRabbitMQAdapter",
    # Manual adapter
    "ManualBrokerAdapter",
    "ManualRabbitMQAdapter",
    "PendingOrder",
    "ApprovalStatus",
]
