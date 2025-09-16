"""Service registry for dependency injection and service management.

This module provides a simple service registry pattern to manage
optional dependencies and provide graceful degradation.
"""

import logging
from functools import wraps
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class ServiceRegistry:
    """Simple service registry for dependency injection."""

    def __init__(self):
        """Initialize the service registry."""
        self._services: Dict[str, Any] = {}
        self._service_factories: Dict[str, Callable] = {}
        self._availability_checks: Dict[str, Callable] = {}
        self._fallbacks: Dict[str, Any] = {}

    def register(
        self, name: str, service: Any, availability_check: Optional[Callable] = None
    ) -> None:
        """Register a service instance.

        Args:
            name: Service name
            service: Service instance
            availability_check: Optional function to check if service is available
        """
        self._services[name] = service
        if availability_check:
            self._availability_checks[name] = availability_check

        logger.info(f"Registered service: {name}")

    def register_factory(
        self,
        name: str,
        factory: Callable,
        availability_check: Optional[Callable] = None,
    ) -> None:
        """Register a service factory function.

        Args:
            name: Service name
            factory: Factory function that creates the service
            availability_check: Optional function to check if service can be created
        """
        self._service_factories[name] = factory
        if availability_check:
            self._availability_checks[name] = availability_check

        logger.info(f"Registered service factory: {name}")

    def register_fallback(self, name: str, fallback: Any) -> None:
        """Register a fallback service for when the main service is unavailable.

        Args:
            name: Service name
            fallback: Fallback service instance or factory
        """
        self._fallbacks[name] = fallback
        logger.info(f"Registered fallback for service: {name}")

    def is_available(self, name: str) -> bool:
        """Check if a service is available.

        Args:
            name: Service name

        Returns:
            bool: True if service is available
        """
        # Check if we have an availability check function
        if name in self._availability_checks:
            try:
                return self._availability_checks[name]()
            except Exception as e:
                logger.warning(f"Availability check for {name} failed: {e}")
                return False

        # Check if service is registered
        if name in self._services:
            return True

        # Check if factory is registered
        if name in self._service_factories:
            return True

        return False

    def get(self, name: str, default: Optional[Any] = None) -> Any:
        """Get a service instance.

        Args:
            name: Service name
            default: Default value if service not available

        Returns:
            Service instance or default

        Raises:
            ServiceNotAvailableError: If service not available and no default provided
        """
        # Try to get existing instance
        if name in self._services:
            return self._services[name]

        # Try to create from factory
        if name in self._service_factories:
            try:
                service = self._service_factories[name]()
                self._services[name] = service  # Cache the instance
                return service
            except Exception as e:
                logger.error(f"Failed to create service {name}: {e}")

        # Use default if provided
        if default is not None:
            return default

        # Raise error if nothing available
        raise ServiceNotAvailableError(f"Service '{name}' is not available")

    def get_fallback(self, name: str) -> Optional[Any]:
        """Get fallback service if main service is unavailable.

        Args:
            name: Service name

        Returns:
            Fallback service instance or None
        """
        if name in self._fallbacks:
            fallback = self._fallbacks[name]
            # If fallback is a factory, call it
            if callable(fallback):
                try:
                    return fallback()
                except Exception as e:
                    logger.error(f"Failed to create fallback for {name}: {e}")
                    return None
            return fallback
        return None

    def list_services(self) -> Dict[str, bool]:
        """List all registered services and their availability.

        Returns:
            Dict mapping service names to availability status
        """
        all_services = set()
        all_services.update(self._services.keys())
        all_services.update(self._service_factories.keys())
        all_services.update(self._fallbacks.keys())

        return {name: self.is_available(name) for name in all_services}


class ServiceNotAvailableError(Exception):
    """Exception raised when a requested service is not available."""

    pass


# Global service registry instance
_registry = ServiceRegistry()


def get_service_registry() -> ServiceRegistry:
    """Get the global service registry instance.

    Returns:
        ServiceRegistry: Global service registry
    """
    return _registry


# Convenience functions
def register_service(
    name: str, service: Any, availability_check: Optional[Callable] = None
) -> None:
    """Register a service in the global registry."""
    _registry.register(name, service, availability_check)


def is_service_available(name: str) -> bool:
    """Check if a service is available in the global registry."""
    return _registry.is_available(name)


def get_service(name: str, default: Optional[Any] = None) -> Any:
    """Get a service from the global registry."""
    return _registry.get(name, default)


# Decorator for optional service dependencies
def requires_service(service_name: str, fallback_value: Optional[Any] = None):
    """Decorator to mark functions that require a specific service.

    Args:
        service_name: Name of required service
        fallback_value: Value to return if service not available
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not is_service_available(service_name):
                if fallback_value is not None:
                    return fallback_value
                raise ServiceNotAvailableError(
                    f"Required service '{service_name}' not available"
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator
