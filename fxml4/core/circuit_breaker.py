"""
FXML4 Circuit Breaker System

High-performance circuit breaker implementation for protecting external service calls
in the FXML4 trading system. Based on lessons learned from the PDF policy processor
project and optimized for financial trading system requirements.

Key Features:
- Lightweight in-memory state management optimized for high-frequency trading
- Service-specific configuration for database, broker APIs, and data feeds
- Async/await support for non-blocking operations
- Comprehensive metrics and monitoring integration
- Thread-safe operation for concurrent trading operations
- Configurable failure thresholds and recovery timeouts

Author: FXML4 Development Team
Created: 2024-12-28
"""

import asyncio
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar, Union

# Type variable for generic circuit breaker
T = TypeVar("T")

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states for FXML4 services."""

    CLOSED = "closed"  # Normal operation - requests flow through
    OPEN = "open"  # Service degraded - requests blocked
    HALF_OPEN = "half_open"  # Testing recovery - limited requests allowed


class ServiceType(Enum):
    """Types of services protected by circuit breakers in FXML4."""

    DATABASE = "database"  # TimescaleDB, Redis connections
    BROKER_API = "broker_api"  # Interactive Brokers, FXCM APIs
    DATA_FEED = "data_feed"  # Polygon.io, Alpha Vantage feeds
    ML_SERVICE = "ml_service"  # ML model inference services
    LLM_SERVICE = "llm_service"  # OpenAI, Anthropic API calls
    EXTERNAL_API = "external_api"  # Other external service calls
    INTERNAL_API = "internal_api"  # Internal FXML4 service calls


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""

    failure_threshold: int = 5  # Failures before opening circuit
    recovery_timeout: int = 60  # Seconds before attempting recovery
    success_threshold: int = 3  # Successes needed to close circuit
    timeout_seconds: float = 30.0  # Request timeout
    expected_exceptions: List[type] = field(default_factory=lambda: [Exception])
    exclude_exceptions: List[type] = field(default_factory=list)

    # Service-specific configurations
    @classmethod
    def for_database(cls) -> "CircuitBreakerConfig":
        """Configuration optimized for database connections."""
        return cls(
            failure_threshold=3,  # Fail fast for database issues
            recovery_timeout=30,  # Quick recovery for DB
            success_threshold=2,  # Conservative recovery
            timeout_seconds=5.0,  # Short timeout for DB queries
            exclude_exceptions=[asyncio.TimeoutError],
        )

    @classmethod
    def for_broker_api(cls) -> "CircuitBreakerConfig":
        """Configuration optimized for broker API calls."""
        return cls(
            failure_threshold=5,  # More tolerance for broker issues
            recovery_timeout=60,  # Longer recovery for brokers
            success_threshold=3,  # Ensure stability before recovery
            timeout_seconds=15.0,  # Reasonable timeout for trading
            exclude_exceptions=[],
        )

    @classmethod
    def for_data_feed(cls) -> "CircuitBreakerConfig":
        """Configuration optimized for external data feeds."""
        return cls(
            failure_threshold=10,  # High tolerance for feed issues
            recovery_timeout=120,  # Longer recovery for external feeds
            success_threshold=5,  # Ensure feed stability
            timeout_seconds=30.0,  # Allow time for data retrieval
            exclude_exceptions=[],
        )

    @classmethod
    def for_ml_service(cls) -> "CircuitBreakerConfig":
        """Configuration optimized for ML model inference."""
        return cls(
            failure_threshold=3,  # Fail fast for ML issues
            recovery_timeout=45,  # Moderate recovery time
            success_threshold=2,  # Quick recovery for ML
            timeout_seconds=10.0,  # ML inference timeout
            exclude_exceptions=[],
        )

    @classmethod
    def for_llm_service(cls) -> "CircuitBreakerConfig":
        """Configuration optimized for LLM API calls."""
        return cls(
            failure_threshold=8,  # Higher tolerance for LLM rate limits
            recovery_timeout=300,  # Long recovery for rate limit reset
            success_threshold=3,  # Ensure API stability
            timeout_seconds=60.0,  # Long timeout for LLM processing
            exclude_exceptions=[],
        )


@dataclass
class CircuitBreakerMetrics:
    """Metrics for circuit breaker monitoring."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    circuit_open_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    average_response_time: float = 0.0
    response_times: List[float] = field(default_factory=list)

    def record_success(self, response_time: float):
        """Record a successful request."""
        self.total_requests += 1
        self.successful_requests += 1
        self.last_success_time = datetime.now(timezone.utc)

        # Update average response time
        self.response_times.append(response_time)
        if len(self.response_times) > 100:  # Keep last 100 response times
            self.response_times = self.response_times[-100:]
        self.average_response_time = sum(self.response_times) / len(self.response_times)

    def record_failure(self):
        """Record a failed request."""
        self.total_requests += 1
        self.failed_requests += 1
        self.last_failure_time = datetime.now(timezone.utc)

    def record_circuit_open(self):
        """Record circuit opening event."""
        self.circuit_open_count += 1

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100.0

    @property
    def failure_rate(self) -> float:
        """Calculate failure rate as percentage."""
        return 100.0 - self.success_rate


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open and blocking requests."""

    def __init__(self, service_name: str, message: str = None):
        self.service_name = service_name
        self.message = (
            message or f"Circuit breaker '{service_name}' is open - service unavailable"
        )
        super().__init__(self.message)


class CircuitBreaker(Generic[T]):
    """
    Production-ready circuit breaker for FXML4 trading system.

    Protects external service calls with configurable failure thresholds,
    automatic recovery testing, and comprehensive metrics collection.
    Optimized for high-frequency trading system requirements.
    """

    def __init__(
        self,
        name: str,
        service_type: ServiceType,
        config: Optional[CircuitBreakerConfig] = None,
    ):
        """
        Initialize circuit breaker for a specific service.

        Args:
            name: Unique name for this circuit breaker
            service_type: Type of service being protected
            config: Optional configuration (defaults to service-appropriate config)
        """
        self.name = name
        self.service_type = service_type

        # Set service-specific configuration if not provided
        if config is None:
            config_map = {
                ServiceType.DATABASE: CircuitBreakerConfig.for_database,
                ServiceType.BROKER_API: CircuitBreakerConfig.for_broker_api,
                ServiceType.DATA_FEED: CircuitBreakerConfig.for_data_feed,
                ServiceType.ML_SERVICE: CircuitBreakerConfig.for_ml_service,
                ServiceType.LLM_SERVICE: CircuitBreakerConfig.for_llm_service,
                ServiceType.EXTERNAL_API: CircuitBreakerConfig,
                ServiceType.INTERNAL_API: CircuitBreakerConfig,
            }
            config = config_map.get(service_type, CircuitBreakerConfig)()

        self.config = config

        # State management with thread safety
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = threading.RLock()

        # Metrics collection
        self.metrics = CircuitBreakerMetrics()

        # Logging
        self.logger = logger.getChild(f"circuit_breaker.{name}")
        self.logger.info(
            f"Circuit breaker '{name}' initialized for {service_type.value} with "
            f"failure_threshold={config.failure_threshold}, "
            f"recovery_timeout={config.recovery_timeout}s"
        )

    @property
    def state(self) -> CircuitState:
        """Get current circuit state (thread-safe)."""
        with self._lock:
            return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if (
                    self._last_failure_time
                    and time.time() - self._last_failure_time
                    >= self.config.recovery_timeout
                ):
                    self.logger.info(
                        f"Recovery timeout reached, transitioning to half-open"
                    )
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                    return False
                return True
            return False

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        return self.state == CircuitState.HALF_OPEN

    def _should_count_as_failure(self, exception: Exception) -> bool:
        """Determine if exception should count as a failure."""
        if any(
            isinstance(exception, exc_type)
            for exc_type in self.config.exclude_exceptions
        ):
            return False
        return any(
            isinstance(exception, exc_type)
            for exc_type in self.config.expected_exceptions
        )

    def _on_success(self, response_time: float):
        """Handle successful request."""
        with self._lock:
            self.metrics.record_success(response_time)

            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                self.logger.debug(
                    f"Half-open success count: {self._success_count}/{self.config.success_threshold}"
                )

                if self._success_count >= self.config.success_threshold:
                    self.logger.info(
                        f"Circuit breaker '{self.name}' closing - recovery successful"
                    )
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on successful request
                self._failure_count = 0

    def _on_failure(self, exception: Exception):
        """Handle failed request."""
        with self._lock:
            if not self._should_count_as_failure(exception):
                return

            self.metrics.record_failure()
            self._failure_count += 1
            self._last_failure_time = time.time()

            self.logger.warning(
                f"Circuit breaker '{self.name}' failure {self._failure_count}/{self.config.failure_threshold}: {exception}"
            )

            if (
                self._state == CircuitState.CLOSED
                and self._failure_count >= self.config.failure_threshold
            ):
                self.logger.error(
                    f"Circuit breaker '{self.name}' opening - failure threshold exceeded"
                )
                self._state = CircuitState.OPEN
                self.metrics.record_circuit_open()
            elif self._state == CircuitState.HALF_OPEN:
                self.logger.warning(
                    f"Circuit breaker '{self.name}' reopening - half-open test failed"
                )
                self._state = CircuitState.OPEN
                self._success_count = 0
                self.metrics.record_circuit_open()

    async def call_async(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute async function with circuit breaker protection.

        Args:
            func: Async function to execute
            *args: Function positional arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit is open
            asyncio.TimeoutError: If function times out
            Exception: If function fails
        """
        if self.is_open:
            raise CircuitBreakerError(self.name)

        start_time = time.time()
        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                func(*args, **kwargs), timeout=self.config.timeout_seconds
            )

            response_time = time.time() - start_time
            self._on_success(response_time)
            return result

        except Exception as e:
            self._on_failure(e)
            raise

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute synchronous function with circuit breaker protection.

        Args:
            func: Function to execute
            *args: Function positional arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit is open
            Exception: If function fails
        """
        if self.is_open:
            raise CircuitBreakerError(self.name)

        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            response_time = time.time() - start_time
            self._on_success(response_time)
            return result

        except Exception as e:
            self._on_failure(e)
            raise

    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive metrics for monitoring."""
        with self._lock:
            return {
                "name": self.name,
                "service_type": self.service_type.value,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "config": {
                    "failure_threshold": self.config.failure_threshold,
                    "recovery_timeout": self.config.recovery_timeout,
                    "success_threshold": self.config.success_threshold,
                    "timeout_seconds": self.config.timeout_seconds,
                },
                "metrics": {
                    "total_requests": self.metrics.total_requests,
                    "successful_requests": self.metrics.successful_requests,
                    "failed_requests": self.metrics.failed_requests,
                    "success_rate": self.metrics.success_rate,
                    "failure_rate": self.metrics.failure_rate,
                    "circuit_open_count": self.metrics.circuit_open_count,
                    "average_response_time": self.metrics.average_response_time,
                    "last_failure_time": (
                        self.metrics.last_failure_time.isoformat()
                        if self.metrics.last_failure_time
                        else None
                    ),
                    "last_success_time": (
                        self.metrics.last_success_time.isoformat()
                        if self.metrics.last_success_time
                        else None
                    ),
                },
            }

    def reset(self):
        """Reset circuit breaker to closed state (for testing/emergency use)."""
        with self._lock:
            self.logger.info(f"Circuit breaker '{self.name}' manually reset")
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None


class CircuitBreakerManager:
    """
    Global manager for circuit breakers in FXML4 trading system.

    Provides centralized registration, monitoring, and management of all
    circuit breakers protecting external dependencies.
    """

    def __init__(self):
        """Initialize circuit breaker manager."""
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.RLock()
        self.logger = logger.getChild("circuit_breaker_manager")

    def register(
        self,
        name: str,
        service_type: ServiceType,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> CircuitBreaker:
        """
        Register a new circuit breaker.

        Args:
            name: Unique name for the circuit breaker
            service_type: Type of service being protected
            config: Optional custom configuration

        Returns:
            The registered circuit breaker instance
        """
        with self._lock:
            if name in self._circuit_breakers:
                self.logger.warning(
                    f"Circuit breaker '{name}' already registered, returning existing instance"
                )
                return self._circuit_breakers[name]

            circuit_breaker = CircuitBreaker(name, service_type, config)
            self._circuit_breakers[name] = circuit_breaker

            self.logger.info(
                f"Registered circuit breaker '{name}' for {service_type.value}"
            )
            return circuit_breaker

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name."""
        with self._lock:
            return self._circuit_breakers.get(name)

    def get_or_create(
        self,
        name: str,
        service_type: ServiceType,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> CircuitBreaker:
        """Get existing circuit breaker or create new one."""
        circuit_breaker = self.get(name)
        if circuit_breaker is None:
            circuit_breaker = self.register(name, service_type, config)
        return circuit_breaker

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all registered circuit breakers."""
        with self._lock:
            return {
                name: cb.get_metrics() for name, cb in self._circuit_breakers.items()
            }

    def get_unhealthy_circuits(self) -> List[str]:
        """Get list of circuit breakers that are open or have high failure rates."""
        unhealthy = []

        with self._lock:
            for name, cb in self._circuit_breakers.items():
                if cb.is_open or cb.metrics.failure_rate > 50:
                    unhealthy.append(name)

        return unhealthy

    def reset_all(self):
        """Reset all circuit breakers (emergency use only)."""
        with self._lock:
            for cb in self._circuit_breakers.values():
                cb.reset()
            self.logger.warning("All circuit breakers have been reset")

    def shutdown(self):
        """Shutdown circuit breaker manager."""
        with self._lock:
            self.logger.info(
                f"Shutting down circuit breaker manager with {len(self._circuit_breakers)} circuits"
            )
            self._circuit_breakers.clear()


# Global circuit breaker manager instance
_circuit_breaker_manager = CircuitBreakerManager()


def get_circuit_breaker_manager() -> CircuitBreakerManager:
    """Get the global circuit breaker manager instance."""
    return _circuit_breaker_manager


def circuit_breaker_decorator(
    name: str, service_type: ServiceType, config: Optional[CircuitBreakerConfig] = None
):
    """
    Decorator to automatically protect functions with circuit breaker.

    Args:
        name: Circuit breaker name
        service_type: Type of service being protected
        config: Optional configuration

    Returns:
        Decorated function with circuit breaker protection
    """

    def decorator(func):
        circuit_breaker = _circuit_breaker_manager.get_or_create(
            name, service_type, config
        )

        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await circuit_breaker.call_async(func, *args, **kwargs)

            return async_wrapper
        else:

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                return circuit_breaker.call(func, *args, **kwargs)

            return sync_wrapper

    return decorator


# Convenience functions for common FXML4 services
def get_database_circuit_breaker(name: str = "database") -> CircuitBreaker:
    """Get circuit breaker for database operations."""
    return _circuit_breaker_manager.get_or_create(name, ServiceType.DATABASE)


def get_broker_api_circuit_breaker(broker_name: str) -> CircuitBreaker:
    """Get circuit breaker for broker API operations."""
    return _circuit_breaker_manager.get_or_create(
        f"broker_{broker_name}", ServiceType.BROKER_API
    )


def get_data_feed_circuit_breaker(feed_name: str) -> CircuitBreaker:
    """Get circuit breaker for data feed operations."""
    return _circuit_breaker_manager.get_or_create(
        f"feed_{feed_name}", ServiceType.DATA_FEED
    )


def get_ml_service_circuit_breaker(model_name: str) -> CircuitBreaker:
    """Get circuit breaker for ML service operations."""
    return _circuit_breaker_manager.get_or_create(
        f"ml_{model_name}", ServiceType.ML_SERVICE
    )


def get_llm_service_circuit_breaker(provider: str) -> CircuitBreaker:
    """Get circuit breaker for LLM service operations."""
    return _circuit_breaker_manager.get_or_create(
        f"llm_{provider}", ServiceType.LLM_SERVICE
    )
