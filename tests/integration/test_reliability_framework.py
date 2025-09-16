"""
Integration Test Reliability Framework

This module provides a comprehensive framework for enhancing integration test
reliability through automated health checks, retry mechanisms, and graceful
degradation patterns.

Key Features:
- Pre-test health validation
- Automatic retry with exponential backoff
- Service dependency management
- Test isolation and cleanup
- Performance monitoring and baseline validation
- Comprehensive error reporting and diagnostics

Test Reliability Patterns:
- Circuit breaker pattern for external services
- Bulkhead isolation for test categories
- Timeout and deadline management
- Resource leak detection and cleanup
- Test data consistency validation
"""

import asyncio
import functools
import inspect
import logging
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# Import health checking framework
from .test_health_checks import (
    DependencyType,
    HealthChecker,
    HealthCheckResult,
    HealthStatus,
    RetryConfig,
    ensure_system_health,
)

# Optional pytest import
try:
    import pytest

    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False

logger = logging.getLogger(__name__)


class TestCategory(Enum):
    """Test category classification for reliability patterns."""

    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"
    PERFORMANCE = "performance"
    STRESS = "stress"


class TestReliabilityLevel(Enum):
    """Test reliability level requirements."""

    STRICT = "strict"  # Fail fast on any issues
    MODERATE = "moderate"  # Allow degraded services
    LENIENT = "lenient"  # Continue with mocked services


@dataclass
class TestExecutionContext:
    """Context information for test execution reliability."""

    test_name: str
    category: TestCategory
    reliability_level: TestReliabilityLevel
    start_time: datetime = field(default_factory=datetime.now)
    health_results: Dict[str, HealthCheckResult] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: float = 300.0  # 5 minutes default
    cleanup_functions: List[Callable] = field(default_factory=list)
    resource_snapshots: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def duration(self) -> timedelta:
        """Get test execution duration."""
        return datetime.now() - self.start_time

    @property
    def is_timeout_exceeded(self) -> bool:
        """Check if test execution has exceeded timeout."""
        return self.duration.total_seconds() > self.timeout_seconds


@dataclass
class CircuitBreakerState:
    """Circuit breaker state for external service calls."""

    service_name: str
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    failure_threshold: int = 3
    recovery_timeout_seconds: float = 60.0
    state: str = "closed"  # closed, open, half_open

    @property
    def is_open(self) -> bool:
        """Check if circuit breaker is open (blocking calls)."""
        if self.state == "open":
            if (
                self.last_failure_time
                and datetime.now() - self.last_failure_time
                > timedelta(seconds=self.recovery_timeout_seconds)
            ):
                self.state = "half_open"
                return False
            return True
        return False

    def record_success(self):
        """Record successful call."""
        self.failure_count = 0
        self.state = "closed"
        self.last_failure_time = None

    def record_failure(self):
        """Record failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"


class ReliabilityFramework:
    """Comprehensive integration test reliability framework."""

    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreakerState] = {}
        self.health_checker = HealthChecker()
        self.active_contexts: Dict[str, TestExecutionContext] = {}
        self.global_health_cache: Optional[Dict[str, HealthCheckResult]] = None
        self.cache_expiry: Optional[datetime] = None
        self.cache_duration_seconds = 300  # 5 minutes

    async def ensure_test_readiness(
        self,
        test_name: str,
        category: TestCategory = TestCategory.INTEGRATION,
        reliability_level: TestReliabilityLevel = TestReliabilityLevel.MODERATE,
        timeout_seconds: float = 300.0,
        custom_health_config: Optional[Dict[str, Any]] = None,
    ) -> TestExecutionContext:
        """
        Ensure system readiness before test execution.

        This method performs comprehensive pre-test validation including:
        - Health checks for all dependencies
        - Resource availability validation
        - Circuit breaker status verification
        - Test isolation setup
        """
        logger.info(f"Ensuring readiness for test: {test_name}")

        context = TestExecutionContext(
            test_name=test_name,
            category=category,
            reliability_level=reliability_level,
            timeout_seconds=timeout_seconds,
        )

        try:
            # Check cached health results
            if self._is_health_cache_valid():
                logger.debug("Using cached health results")
                context.health_results = self.global_health_cache.copy()
            else:
                # Perform fresh health checks
                logger.info("Performing fresh health checks")
                context.health_results = await self.health_checker.check_all_services(
                    custom_health_config
                )
                self._update_health_cache(context.health_results)

            # Validate readiness based on reliability level
            await self._validate_test_readiness(context)

            # Setup test isolation
            await self._setup_test_isolation(context)

            # Register context for cleanup
            self.active_contexts[test_name] = context

            logger.info(f"Test readiness validated for: {test_name}")
            return context

        except Exception as e:
            logger.error(f"Test readiness validation failed for {test_name}: {e}")
            # Cleanup on failure
            await self._cleanup_test_context(context)
            raise

    async def execute_with_reliability(
        self, test_func: Callable, context: TestExecutionContext, *args, **kwargs
    ) -> Any:
        """
        Execute test function with comprehensive reliability patterns.

        Features:
        - Automatic retry with exponential backoff
        - Circuit breaker protection for external calls
        - Resource monitoring and leak detection
        - Timeout management
        - Graceful error handling and cleanup
        """
        logger.info(f"Executing test with reliability: {context.test_name}")

        retry_config = RetryConfig(
            max_attempts=context.max_retries,
            base_delay_seconds=1.0,
            max_delay_seconds=30.0,
        )

        last_exception = None

        for attempt in range(retry_config.max_attempts):
            context.retry_count = attempt

            try:
                # Check timeout before each attempt
                if context.is_timeout_exceeded:
                    raise TimeoutError(
                        f"Test execution exceeded timeout: {context.timeout_seconds}s"
                    )

                # Take resource snapshot
                await self._take_resource_snapshot(context)

                # Execute test function
                if inspect.iscoroutinefunction(test_func):
                    result = await test_func(*args, **kwargs)
                else:
                    result = test_func(*args, **kwargs)

                # Validate resource usage after execution
                await self._validate_resource_usage(context)

                logger.info(
                    f"Test executed successfully: {context.test_name} (attempt {attempt + 1})"
                )
                return result

            except Exception as e:
                last_exception = e
                logger.warning(
                    f"Test attempt {attempt + 1} failed for {context.test_name}: {e}"
                )

                # Check if we should retry
                if not self._should_retry(e, context, attempt, retry_config):
                    break

                # Calculate retry delay
                if attempt < retry_config.max_attempts - 1:
                    delay = self._calculate_retry_delay(attempt, retry_config)
                    logger.info(f"Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)

                    # Re-validate health before retry (if critical failure)
                    if self._is_critical_failure(e):
                        await self._revalidate_health(context)

        # All retries exhausted
        logger.error(
            f"Test failed after {retry_config.max_attempts} attempts: {context.test_name}"
        )
        raise last_exception

    async def cleanup_test_context(self, test_name: str):
        """Clean up test context and resources."""
        if test_name in self.active_contexts:
            context = self.active_contexts[test_name]
            await self._cleanup_test_context(context)
            del self.active_contexts[test_name]

    async def _validate_test_readiness(self, context: TestExecutionContext):
        """Validate system readiness based on test requirements."""
        health_summary = self.health_checker.get_health_summary()

        if context.reliability_level == TestReliabilityLevel.STRICT:
            # Strict mode: fail on any unhealthy services
            if health_summary["unhealthy_count"] > 0:
                unhealthy_services = [
                    name
                    for name, result in context.health_results.items()
                    if result.status == HealthStatus.UNHEALTHY
                ]
                raise RuntimeError(
                    f"Strict reliability mode: unhealthy services detected: {unhealthy_services}"
                )

        elif context.reliability_level == TestReliabilityLevel.MODERATE:
            # Moderate mode: fail only on critical service failures
            critical_failures = [
                name
                for name, result in context.health_results.items()
                if result.is_critical_failure
            ]
            if critical_failures:
                raise RuntimeError(
                    f"Critical service failures detected: {critical_failures}"
                )

        # Lenient mode: continue even with degraded services (default)
        # Just log warnings for degraded services
        degraded_services = [
            name
            for name, result in context.health_results.items()
            if result.status == HealthStatus.DEGRADED
        ]
        if degraded_services:
            logger.warning(f"Degraded services detected: {degraded_services}")

    async def _setup_test_isolation(self, context: TestExecutionContext):
        """Setup test isolation and environment."""
        # Create test-specific temporary directories
        test_temp_dir = (
            Path.cwd() / "tmp" / f"test_{context.test_name}_{int(time.time())}"
        )
        test_temp_dir.mkdir(parents=True, exist_ok=True)

        # Register cleanup
        context.cleanup_functions.append(lambda: self._cleanup_directory(test_temp_dir))

        # Setup test-specific logging if needed
        if context.category in [TestCategory.INTEGRATION, TestCategory.E2E]:
            log_file = test_temp_dir / f"{context.test_name}.log"
            context.cleanup_functions.append(lambda: self._cleanup_log_file(log_file))

        logger.debug(f"Test isolation setup complete for: {context.test_name}")

    async def _take_resource_snapshot(self, context: TestExecutionContext):
        """Take snapshot of system resources."""
        try:
            import psutil

            snapshot = {
                "timestamp": datetime.now().isoformat(),
                "memory_percent": psutil.virtual_memory().percent,
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "disk_usage_percent": psutil.disk_usage(".").used
                / psutil.disk_usage(".").total
                * 100,
                "open_files": len(psutil.Process().open_files()),
                "connections": len(psutil.net_connections()),
            }

            context.resource_snapshots.append(snapshot)

        except Exception as e:
            logger.warning(f"Failed to take resource snapshot: {e}")

    async def _validate_resource_usage(self, context: TestExecutionContext):
        """Validate resource usage and detect potential leaks."""
        if len(context.resource_snapshots) < 2:
            return

        initial = context.resource_snapshots[0]
        current = context.resource_snapshots[-1]

        # Check for memory leaks
        memory_increase = current["memory_percent"] - initial["memory_percent"]
        if memory_increase > 10:  # 10% increase threshold
            logger.warning(
                f"Potential memory leak detected: {memory_increase:.1f}% increase "
                f"during {context.test_name}"
            )

        # Check for file descriptor leaks
        fd_increase = current["open_files"] - initial["open_files"]
        if fd_increase > 20:  # 20 file descriptor threshold
            logger.warning(
                f"Potential file descriptor leak: {fd_increase} descriptors "
                f"not closed during {context.test_name}"
            )

        # Check for connection leaks
        conn_increase = current["connections"] - initial["connections"]
        if conn_increase > 10:  # 10 connection threshold
            logger.warning(
                f"Potential connection leak: {conn_increase} connections "
                f"not closed during {context.test_name}"
            )

    def _should_retry(
        self,
        exception: Exception,
        context: TestExecutionContext,
        attempt: int,
        retry_config: RetryConfig,
    ) -> bool:
        """Determine if test should be retried based on exception type and context."""
        # Don't retry if we've exhausted attempts
        if attempt >= retry_config.max_attempts - 1:
            return False

        # Don't retry assertion errors (test logic failures)
        if isinstance(exception, AssertionError):
            return False

        # Don't retry timeout errors
        if isinstance(exception, TimeoutError):
            return False

        # Don't retry in strict reliability mode
        if context.reliability_level == TestReliabilityLevel.STRICT:
            return False

        # Retry network-related errors
        if isinstance(exception, (ConnectionError, OSError)):
            return True

        # Retry temporary resource issues
        if "temporary" in str(exception).lower():
            return True

        # Default: don't retry unknown exceptions
        return False

    def _calculate_retry_delay(self, attempt: int, retry_config: RetryConfig) -> float:
        """Calculate retry delay with exponential backoff and jitter."""
        base_delay = retry_config.base_delay_seconds * (
            retry_config.exponential_base**attempt
        )
        delay = min(base_delay, retry_config.max_delay_seconds)

        if retry_config.jitter:
            import random

            jitter = random.uniform(0.5, 1.5)
            delay *= jitter

        return delay

    def _is_critical_failure(self, exception: Exception) -> bool:
        """Check if exception represents a critical system failure."""
        critical_indicators = [
            "database connection",
            "critical service",
            "authentication",
            "permission denied",
        ]

        exception_str = str(exception).lower()
        return any(indicator in exception_str for indicator in critical_indicators)

    async def _revalidate_health(self, context: TestExecutionContext):
        """Re-validate system health after critical failure."""
        logger.info("Re-validating system health after critical failure")

        # Force fresh health check
        self.global_health_cache = None
        context.health_results = await self.health_checker.check_all_services()
        self._update_health_cache(context.health_results)

        # Re-validate readiness
        await self._validate_test_readiness(context)

    def _is_health_cache_valid(self) -> bool:
        """Check if cached health results are still valid."""
        if not self.global_health_cache or not self.cache_expiry:
            return False

        return datetime.now() < self.cache_expiry

    def _update_health_cache(self, health_results: Dict[str, HealthCheckResult]):
        """Update cached health results."""
        self.global_health_cache = health_results.copy()
        self.cache_expiry = datetime.now() + timedelta(
            seconds=self.cache_duration_seconds
        )

    async def _cleanup_test_context(self, context: TestExecutionContext):
        """Clean up test context and execute cleanup functions."""
        logger.debug(f"Cleaning up test context: {context.test_name}")

        # Execute all cleanup functions
        for cleanup_func in context.cleanup_functions:
            try:
                if inspect.iscoroutinefunction(cleanup_func):
                    await cleanup_func()
                else:
                    cleanup_func()
            except Exception as e:
                logger.warning(f"Cleanup function failed: {e}")

        # Clear cleanup functions
        context.cleanup_functions.clear()

    def _cleanup_directory(self, directory_path: Path):
        """Clean up temporary directory."""
        try:
            import shutil

            if directory_path.exists():
                shutil.rmtree(directory_path)
        except Exception as e:
            logger.warning(f"Failed to cleanup directory {directory_path}: {e}")

    def _cleanup_log_file(self, log_file: Path):
        """Clean up test log file."""
        try:
            if log_file.exists():
                log_file.unlink()
        except Exception as e:
            logger.warning(f"Failed to cleanup log file {log_file}: {e}")

    def get_circuit_breaker(self, service_name: str) -> CircuitBreakerState:
        """Get or create circuit breaker for service."""
        if service_name not in self.circuit_breakers:
            self.circuit_breakers[service_name] = CircuitBreakerState(service_name)
        return self.circuit_breakers[service_name]

    async def call_with_circuit_breaker(
        self, service_name: str, func: Callable, *args, **kwargs
    ) -> Any:
        """Execute function with circuit breaker protection."""
        circuit_breaker = self.get_circuit_breaker(service_name)

        if circuit_breaker.is_open:
            raise RuntimeError(f"Circuit breaker open for service: {service_name}")

        try:
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            circuit_breaker.record_success()
            return result

        except Exception as e:
            circuit_breaker.record_failure()
            logger.warning(f"Circuit breaker recorded failure for {service_name}: {e}")
            raise


# Decorators for enhanced test reliability
def reliable_test(
    category: TestCategory = TestCategory.INTEGRATION,
    reliability_level: TestReliabilityLevel = TestReliabilityLevel.MODERATE,
    timeout_seconds: float = 300.0,
    max_retries: int = 3,
):
    """
    Decorator to enhance test reliability with automatic health checks and retry logic.

    Usage:
        @reliable_test(category=TestCategory.INTEGRATION, reliability_level=TestReliabilityLevel.STRICT)
        async def test_my_integration():
            # Test code here
            pass
    """

    def decorator(test_func: Callable):
        @functools.wraps(test_func)
        async def wrapper(*args, **kwargs):
            framework = ReliabilityFramework()
            test_name = f"{test_func.__module__}.{test_func.__name__}"

            try:
                # Ensure test readiness
                context = await framework.ensure_test_readiness(
                    test_name=test_name,
                    category=category,
                    reliability_level=reliability_level,
                    timeout_seconds=timeout_seconds,
                )
                context.max_retries = max_retries

                # Execute with reliability patterns
                result = await framework.execute_with_reliability(
                    test_func, context, *args, **kwargs
                )

                return result

            finally:
                # Ensure cleanup
                await framework.cleanup_test_context(test_name)

        return wrapper

    return decorator


def circuit_breaker(service_name: str):
    """
    Decorator to protect external service calls with circuit breaker pattern.

    Usage:
        @circuit_breaker("external_api")
        async def call_external_api():
            # API call code here
            pass
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            framework = ReliabilityFramework()
            return await framework.call_with_circuit_breaker(
                service_name, func, *args, **kwargs
            )

        return wrapper

    return decorator


# Pytest integration (if available)
if PYTEST_AVAILABLE:

    @pytest.fixture(scope="session")
    async def reliability_framework():
        """Session-level reliability framework fixture."""
        framework = ReliabilityFramework()
        yield framework

    @pytest.fixture
    async def test_context(reliability_framework, request):
        """Function-level test context fixture."""
        test_name = f"{request.module.__name__}.{request.function.__name__}"

        context = await reliability_framework.ensure_test_readiness(
            test_name=test_name,
            category=TestCategory.INTEGRATION,
            reliability_level=TestReliabilityLevel.MODERATE,
        )

        yield context

        # Cleanup
        await reliability_framework.cleanup_test_context(test_name)

    # Test markers for reliability levels
    pytest.mark.reliable_strict = pytest.mark.reliable_strict
    pytest.mark.reliable_moderate = pytest.mark.reliable_moderate
    pytest.mark.reliable_lenient = pytest.mark.reliable_lenient


# Example usage and validation
if __name__ == "__main__":

    async def example_reliable_test():
        """Example of using the reliability framework."""
        print("Testing Integration Test Reliability Framework")
        print("=" * 60)

        framework = ReliabilityFramework()

        # Test 1: Basic reliability validation
        print("\n1. Testing basic reliability validation...")
        context = await framework.ensure_test_readiness(
            test_name="example_test",
            category=TestCategory.INTEGRATION,
            reliability_level=TestReliabilityLevel.MODERATE,
        )

        print(f"   ✓ Test context created: {context.test_name}")
        print(f"   ✓ Health checks completed: {len(context.health_results)} services")
        print(f"   ✓ Category: {context.category.value}")
        print(f"   ✓ Reliability level: {context.reliability_level.value}")

        # Test 2: Circuit breaker functionality
        print("\n2. Testing circuit breaker functionality...")

        @circuit_breaker("test_service")
        async def test_service_call():
            return {"status": "success", "data": "test_data"}

        result = await test_service_call()
        print(f"   ✓ Circuit breaker call successful: {result}")

        # Test 3: Resource monitoring
        print("\n3. Testing resource monitoring...")
        await framework._take_resource_snapshot(context)
        await asyncio.sleep(0.1)  # Simulate some work
        await framework._take_resource_snapshot(context)
        await framework._validate_resource_usage(context)
        print(
            f"   ✓ Resource monitoring completed: {len(context.resource_snapshots)} snapshots"
        )

        # Cleanup
        await framework.cleanup_test_context("example_test")
        print("\n✅ All reliability framework tests passed!")

    # Run the example
    asyncio.run(example_reliable_test())
