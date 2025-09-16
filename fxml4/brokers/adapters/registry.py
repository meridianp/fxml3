"""
Broker Adapter Registry for FXML4.

This module provides a registry for broker adapter classes,
enabling dynamic adapter discovery and instantiation.

CRITICAL MODULE: Central registry for broker adapter types.
"""

import logging
from typing import Any, Dict, List, Optional, Type

from .base import BrokerAdapter

logger = logging.getLogger(__name__)


class BrokerAdapterRegistry:
    """Registry for broker adapter classes.

    This class maintains a registry of available broker adapter classes
    and provides methods for discovery and instantiation.
    """

    def __init__(self):
        """Initialize the broker adapter registry."""
        self._adapters: Dict[str, Type[BrokerAdapter]] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}

    def register(
        self,
        name: str,
        adapter_class: Type[BrokerAdapter],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a broker adapter class.

        Args:
            name: Unique name for the adapter
            adapter_class: Adapter class to register
            metadata: Optional metadata about the adapter
        """
        if not issubclass(adapter_class, BrokerAdapter):
            raise ValueError(f"Adapter class must inherit from BrokerAdapter")

        if name in self._adapters:
            logger.warning(f"Overriding existing adapter registration: {name}")

        self._adapters[name] = adapter_class
        self._metadata[name] = metadata or {}

        logger.info(f"Registered broker adapter: {name}")

    def unregister(self, name: str) -> None:
        """Unregister a broker adapter class.

        Args:
            name: Name of the adapter to unregister
        """
        if name in self._adapters:
            del self._adapters[name]
            del self._metadata[name]
            logger.info(f"Unregistered broker adapter: {name}")
        else:
            logger.warning(f"Adapter not found for unregistration: {name}")

    def get_adapter_class(self, name: str) -> Optional[Type[BrokerAdapter]]:
        """Get a registered adapter class by name.

        Args:
            name: Name of the adapter

        Returns:
            Adapter class or None if not found
        """
        return self._adapters.get(name)

    def list_adapters(self) -> List[str]:
        """List all registered adapter names.

        Returns:
            List of registered adapter names
        """
        return list(self._adapters.keys())

    def get_metadata(self, name: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a registered adapter.

        Args:
            name: Name of the adapter

        Returns:
            Metadata dictionary or None if not found
        """
        return self._metadata.get(name)

    def create_adapter(
        self, name: str, config: Dict[str, Any]
    ) -> Optional[BrokerAdapter]:
        """Create an instance of a registered adapter.

        Args:
            name: Name of the adapter
            config: Configuration for the adapter

        Returns:
            Adapter instance or None if not found
        """
        adapter_class = self.get_adapter_class(name)
        if adapter_class is None:
            logger.error(f"Adapter class not found: {name}")
            return None

        try:
            return adapter_class(config)
        except Exception as e:
            logger.error(f"Failed to create adapter {name}: {e}")
            return None

    def get_registry_info(self) -> Dict[str, Any]:
        """Get information about the registry.

        Returns:
            Dictionary with registry information
        """
        adapters_info = []

        for name, adapter_class in self._adapters.items():
            metadata = self._metadata.get(name, {})

            info = {
                "name": name,
                "class_name": adapter_class.__name__,
                "module": adapter_class.__module__,
                "metadata": metadata,
            }

            adapters_info.append(info)

        return {"total_adapters": len(self._adapters), "adapters": adapters_info}


# Global registry instance
_registry_instance: Optional[BrokerAdapterRegistry] = None


def get_registry() -> BrokerAdapterRegistry:
    """Get the global broker adapter registry instance.

    Returns:
        BrokerAdapterRegistry instance
    """
    global _registry_instance

    if _registry_instance is None:
        _registry_instance = BrokerAdapterRegistry()

        # Register built-in adapters
        _register_builtin_adapters(_registry_instance)

    return _registry_instance


def _register_builtin_adapters(registry: BrokerAdapterRegistry) -> None:
    """Register built-in adapter classes.

    Args:
        registry: Registry instance to register adapters with
    """
    try:
        # Import and register adapters - using lazy imports to avoid circular dependencies

        # Register placeholder adapters until actual implementations are available
        logger.info("Registering built-in adapter placeholders")

        # Note: Actual adapter registration will happen when the adapter modules are loaded

    except Exception as e:
        logger.warning(f"Could not register some built-in adapters: {e}")


def register_adapter(
    name: str,
    adapter_class: Type[BrokerAdapter],
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Register an adapter with the global registry.

    Args:
        name: Unique name for the adapter
        adapter_class: Adapter class to register
        metadata: Optional metadata about the adapter
    """
    registry = get_registry()
    registry.register(name, adapter_class, metadata)
