"""API Dependencies for Broker Abstraction System.

This module provides dependency injection for FastAPI routes.
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml

from ..brokers.adapters.manager import BrokerAdapterManager
from ..brokers.messaging.router import MessageRouter
from ..brokers.risk import FXRiskManager, create_risk_limits_from_config
from ..brokers.risk.integration import RiskAwareBrokerManager

logger = logging.getLogger(__name__)

# Global instances (singleton pattern)
_risk_manager: Optional[FXRiskManager] = None
_adapter_manager: Optional[BrokerAdapterManager] = None
_risk_broker_manager: Optional[RiskAwareBrokerManager] = None
_message_router: Optional[MessageRouter] = None


@lru_cache(maxsize=1)
def get_risk_config():
    """Load risk configuration from file."""
    config_path = Path(__file__).parent.parent.parent / "config" / "risk_limits.yaml"

    if config_path.exists():
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    else:
        logger.warning("Risk config not found, using defaults")
        return {}


def get_risk_manager() -> FXRiskManager:
    """Get or create risk manager instance."""
    global _risk_manager

    if _risk_manager is None:
        config = get_risk_config()
        limits = create_risk_limits_from_config(config)
        _risk_manager = FXRiskManager(limits, enable_all_checks=True)
        logger.info("Created FX Risk Manager instance")

    return _risk_manager


def get_adapter_manager() -> BrokerAdapterManager:
    """Get or create adapter manager instance."""
    global _adapter_manager

    if _adapter_manager is None:
        _adapter_manager = BrokerAdapterManager()
        logger.info("Created Broker Adapter Manager instance")

    return _adapter_manager


def get_message_router() -> MessageRouter:
    """Get or create message router instance."""
    global _message_router

    if _message_router is None:
        _message_router = MessageRouter()
        logger.info("Created Message Router instance")

    return _message_router


def get_risk_broker_manager() -> RiskAwareBrokerManager:
    """Get or create risk-aware broker manager instance."""
    global _risk_broker_manager

    if _risk_broker_manager is None:
        adapter_manager = get_adapter_manager()
        risk_manager = get_risk_manager()
        router = get_message_router()

        _risk_broker_manager = RiskAwareBrokerManager(
            adapter_manager=adapter_manager, risk_manager=risk_manager, router=router
        )
        logger.info("Created Risk-Aware Broker Manager instance")

    return _risk_broker_manager


def init_dependencies():
    """Initialize all dependencies.

    This should be called during application startup.
    """
    logger.info("Initializing API dependencies...")

    # Initialize all singletons
    get_risk_manager()
    get_adapter_manager()
    get_message_router()
    get_risk_broker_manager()

    logger.info("API dependencies initialized successfully")


def cleanup_dependencies():
    """Cleanup dependencies.

    This should be called during application shutdown.
    """
    global _risk_manager, _adapter_manager, _risk_broker_manager, _message_router

    logger.info("Cleaning up API dependencies...")

    # Reset all singletons
    _risk_manager = None
    _adapter_manager = None
    _risk_broker_manager = None
    _message_router = None

    logger.info("API dependencies cleaned up")
