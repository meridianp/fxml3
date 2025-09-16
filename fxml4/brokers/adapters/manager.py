"""
Broker Adapter Manager for FXML4.

This module provides centralized management for broker adapters,
handling adapter lifecycle, routing, and configuration.

CRITICAL MODULE: Central coordinator for all broker communications.
"""

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Type

from ...core.exceptions import FXMLError
from .base import BrokerAdapter, ConnectionStatus

logger = logging.getLogger(__name__)


class AdapterStatus(Enum):
    """Adapter status enumeration."""

    INACTIVE = "inactive"
    INITIALIZING = "initializing"
    ACTIVE = "active"
    ERROR = "error"
    DISCONNECTED = "disconnected"


class BrokerAdapterError(FXMLError):
    """Exception raised when broker adapter operations fail."""

    pass


class BrokerAdapterManager:
    """Manager for broker adapters.

    This class handles the lifecycle management of broker adapters,
    including initialization, monitoring, failover, and cleanup.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize broker adapter manager.

        Args:
            config: Configuration dictionary for adapter management
        """
        self.config = config or {}
        self.adapters: Dict[str, BrokerAdapter] = {}
        self.adapter_status: Dict[str, AdapterStatus] = {}
        self.adapter_configs: Dict[str, Dict[str, Any]] = {}

        # Manager state
        self.is_running = False
        self.monitoring_task: Optional[asyncio.Task] = None

        # Configuration
        self.health_check_interval = self.config.get("health_check_interval", 30)
        self.max_retry_attempts = self.config.get("max_retry_attempts", 3)
        self.retry_delay = self.config.get("retry_delay", 5)

    async def initialize(self) -> None:
        """Initialize the adapter manager."""
        try:
            logger.info("Initializing broker adapter manager")

            # Load adapter configurations
            await self._load_adapter_configs()

            # Start monitoring task
            if self.config.get("enable_monitoring", True):
                self.monitoring_task = asyncio.create_task(self._monitoring_loop())

            self.is_running = True
            logger.info("Broker adapter manager initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize adapter manager: {e}")
            raise BrokerAdapterError(f"Initialization failed: {e}") from e

    async def shutdown(self) -> None:
        """Shutdown the adapter manager and all adapters."""
        try:
            logger.info("Shutting down broker adapter manager")

            self.is_running = False

            # Cancel monitoring task
            if self.monitoring_task and not self.monitoring_task.done():
                self.monitoring_task.cancel()
                try:
                    await self.monitoring_task
                except asyncio.CancelledError:
                    pass

            # Shutdown all adapters
            shutdown_tasks = []
            for adapter_name, adapter in self.adapters.items():
                try:
                    task = asyncio.create_task(self._shutdown_adapter(adapter_name))
                    shutdown_tasks.append(task)
                except Exception as e:
                    logger.warning(
                        f"Error creating shutdown task for {adapter_name}: {e}"
                    )

            # Wait for all shutdowns to complete
            if shutdown_tasks:
                await asyncio.gather(*shutdown_tasks, return_exceptions=True)

            logger.info("Broker adapter manager shutdown complete")

        except Exception as e:
            logger.error(f"Error during adapter manager shutdown: {e}")

    async def register_adapter(
        self, name: str, adapter_class: Type[BrokerAdapter], config: Dict[str, Any]
    ) -> None:
        """Register a new broker adapter.

        Args:
            name: Unique name for the adapter
            adapter_class: Adapter class to instantiate
            config: Configuration for the adapter
        """
        try:
            if name in self.adapters:
                raise BrokerAdapterError(f"Adapter {name} already registered")

            logger.info(f"Registering adapter: {name}")

            # Store configuration
            self.adapter_configs[name] = config

            # Create adapter instance
            adapter = adapter_class(config)
            self.adapters[name] = adapter
            self.adapter_status[name] = AdapterStatus.INACTIVE

            logger.info(f"Adapter {name} registered successfully")

        except Exception as e:
            logger.error(f"Failed to register adapter {name}: {e}")
            raise BrokerAdapterError(f"Registration failed for {name}: {e}") from e

    async def start_adapter(self, name: str) -> None:
        """Start a specific adapter.

        Args:
            name: Name of the adapter to start
        """
        if name not in self.adapters:
            raise BrokerAdapterError(f"Adapter {name} not registered")

        try:
            logger.info(f"Starting adapter: {name}")
            self.adapter_status[name] = AdapterStatus.INITIALIZING

            adapter = self.adapters[name]
            await adapter.connect()

            self.adapter_status[name] = AdapterStatus.ACTIVE
            logger.info(f"Adapter {name} started successfully")

        except Exception as e:
            logger.error(f"Failed to start adapter {name}: {e}")
            self.adapter_status[name] = AdapterStatus.ERROR
            raise BrokerAdapterError(f"Start failed for {name}: {e}") from e

    async def stop_adapter(self, name: str) -> None:
        """Stop a specific adapter.

        Args:
            name: Name of the adapter to stop
        """
        await self._shutdown_adapter(name)

    async def _shutdown_adapter(self, name: str) -> None:
        """Internal method to shutdown an adapter.

        Args:
            name: Name of the adapter to shutdown
        """
        if name not in self.adapters:
            logger.warning(f"Adapter {name} not found for shutdown")
            return

        try:
            logger.info(f"Shutting down adapter: {name}")

            adapter = self.adapters[name]
            await adapter.disconnect()

            self.adapter_status[name] = AdapterStatus.INACTIVE
            logger.info(f"Adapter {name} shutdown complete")

        except Exception as e:
            logger.error(f"Error shutting down adapter {name}: {e}")
            self.adapter_status[name] = AdapterStatus.ERROR

    async def start_all_adapters(self) -> None:
        """Start all registered adapters."""
        logger.info("Starting all registered adapters")

        for name in self.adapters.keys():
            try:
                await self.start_adapter(name)
            except Exception as e:
                logger.error(f"Failed to start adapter {name}: {e}")
                # Continue with other adapters

    async def get_adapter(self, name: str) -> Optional[BrokerAdapter]:
        """Get a specific adapter by name.

        Args:
            name: Name of the adapter

        Returns:
            Adapter instance or None if not found
        """
        return self.adapters.get(name)

    def get_adapter_status(self, name: str) -> Optional[AdapterStatus]:
        """Get the status of a specific adapter.

        Args:
            name: Name of the adapter

        Returns:
            Adapter status or None if not found
        """
        return self.adapter_status.get(name)

    def list_adapters(self) -> List[Dict[str, Any]]:
        """List all registered adapters with their status.

        Returns:
            List of adapter information dictionaries
        """
        adapter_info = []

        for name, adapter in self.adapters.items():
            status = self.adapter_status.get(name, AdapterStatus.INACTIVE)

            info = {
                "name": name,
                "status": status.value,
                "adapter_type": type(adapter).__name__,
                "connection_state": getattr(adapter, "connection_state", "unknown"),
                "last_heartbeat": getattr(adapter, "last_heartbeat", None),
            }

            adapter_info.append(info)

        return adapter_info

    async def get_active_adapters(self) -> List[str]:
        """Get list of active adapter names.

        Returns:
            List of active adapter names
        """
        active_adapters = []

        for name, status in self.adapter_status.items():
            if status == AdapterStatus.ACTIVE:
                # Double-check by querying adapter directly
                adapter = self.adapters.get(name)
                if (
                    adapter
                    and hasattr(adapter, "is_connected")
                    and adapter.is_connected()
                ):
                    active_adapters.append(name)

        return active_adapters

    async def _load_adapter_configs(self) -> None:
        """Load adapter configurations from the main config."""
        try:
            # Load from configuration
            adapters_config = self.config.get("adapters", {})

            for name, config in adapters_config.items():
                if config.get("enabled", False):
                    self.adapter_configs[name] = config
                    logger.info(f"Loaded configuration for adapter: {name}")

        except Exception as e:
            logger.error(f"Failed to load adapter configurations: {e}")
            raise

    async def _monitoring_loop(self) -> None:
        """Background monitoring loop for adapter health."""
        logger.info("Starting adapter monitoring loop")

        try:
            while self.is_running:
                await asyncio.sleep(self.health_check_interval)

                if not self.is_running:
                    break

                # Check health of all adapters
                for name, adapter in self.adapters.items():
                    try:
                        await self._check_adapter_health(name, adapter)
                    except Exception as e:
                        logger.warning(f"Health check failed for adapter {name}: {e}")

        except asyncio.CancelledError:
            logger.info("Adapter monitoring loop cancelled")
        except Exception as e:
            logger.error(f"Error in adapter monitoring loop: {e}")

        logger.info("Adapter monitoring loop stopped")

    async def _check_adapter_health(self, name: str, adapter: BrokerAdapter) -> None:
        """Check health of a specific adapter.

        Args:
            name: Name of the adapter
            adapter: Adapter instance
        """
        current_status = self.adapter_status.get(name, AdapterStatus.INACTIVE)

        try:
            # Check if adapter thinks it's connected
            is_connected = hasattr(adapter, "is_connected") and adapter.is_connected()

            if current_status == AdapterStatus.ACTIVE and not is_connected:
                logger.warning(f"Adapter {name} appears disconnected")
                self.adapter_status[name] = AdapterStatus.DISCONNECTED

                # Attempt reconnection if configured
                if self.config.get("auto_reconnect", True):
                    await self._attempt_reconnect(name, adapter)

            elif current_status == AdapterStatus.DISCONNECTED and is_connected:
                logger.info(f"Adapter {name} reconnected")
                self.adapter_status[name] = AdapterStatus.ACTIVE

        except Exception as e:
            logger.error(f"Health check error for adapter {name}: {e}")
            self.adapter_status[name] = AdapterStatus.ERROR

    async def _attempt_reconnect(self, name: str, adapter: BrokerAdapter) -> None:
        """Attempt to reconnect a disconnected adapter.

        Args:
            name: Name of the adapter
            adapter: Adapter instance
        """
        logger.info(f"Attempting to reconnect adapter: {name}")

        try:
            await adapter.disconnect()
            await asyncio.sleep(self.retry_delay)
            await adapter.connect()

            self.adapter_status[name] = AdapterStatus.ACTIVE
            logger.info(f"Successfully reconnected adapter: {name}")

        except Exception as e:
            logger.error(f"Reconnection failed for adapter {name}: {e}")
            self.adapter_status[name] = AdapterStatus.ERROR

    def get_manager_status(self) -> Dict[str, Any]:
        """Get overall manager status.

        Returns:
            Dictionary with manager status information
        """
        active_count = sum(
            1
            for status in self.adapter_status.values()
            if status == AdapterStatus.ACTIVE
        )

        return {
            "is_running": self.is_running,
            "total_adapters": len(self.adapters),
            "active_adapters": active_count,
            "monitoring_enabled": self.monitoring_task is not None,
            "health_check_interval": self.health_check_interval,
            "adapters": self.list_adapters(),
        }


# Global manager instance
_manager_instance: Optional[BrokerAdapterManager] = None


async def get_manager() -> BrokerAdapterManager:
    """Get the global broker adapter manager instance.

    Returns:
        BrokerAdapterManager instance
    """
    global _manager_instance

    if _manager_instance is None:
        _manager_instance = BrokerAdapterManager()
        await _manager_instance.initialize()

    return _manager_instance


async def shutdown_manager() -> None:
    """Shutdown the global broker adapter manager."""
    global _manager_instance

    if _manager_instance is not None:
        await _manager_instance.shutdown()
        _manager_instance = None
