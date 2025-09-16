"""
Comprehensive test suite for FXML4 Circuit Breaker System.

Tests all aspects of the circuit breaker implementation including:
- State transitions (closed -> open -> half-open -> closed)
- Service-specific configurations
- Async and sync operation protection
- Metrics collection and monitoring
- Thread safety and concurrent operations
- Error handling and edge cases
- Manager functionality and global state

Author: FXML4 Development Team
Created: 2024-12-28
"""

import asyncio
import threading
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from fxml4.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerManager,
    CircuitState,
    ServiceType,
    circuit_breaker_decorator,
    get_broker_api_circuit_breaker,
    get_circuit_breaker_manager,
    get_data_feed_circuit_breaker,
    get_database_circuit_breaker,
    get_llm_service_circuit_breaker,
    get_ml_service_circuit_breaker,
)


class TestCircuitBreakerConfig:
    """Test circuit breaker configuration for different service types."""

    def test_default_config(self):
        """Test default configuration values."""
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.recovery_timeout == 60
        assert config.success_threshold == 3
        assert config.timeout_seconds == 30.0
        assert config.expected_exceptions == [Exception]
        assert config.exclude_exceptions == []

    def test_database_config(self):
        """Test database-specific configuration."""
        config = CircuitBreakerConfig.for_database()
        assert config.failure_threshold == 3  # Fail fast for DB
        assert config.recovery_timeout == 30  # Quick recovery
        assert config.success_threshold == 2  # Conservative
        assert config.timeout_seconds == 5.0  # Short timeout
        assert asyncio.TimeoutError in config.exclude_exceptions

    def test_broker_api_config(self):
        """Test broker API-specific configuration."""
        config = CircuitBreakerConfig.for_broker_api()
        assert config.failure_threshold == 5  # More tolerance
        assert config.recovery_timeout == 60  # Longer recovery
        assert config.success_threshold == 3  # Ensure stability
        assert config.timeout_seconds == 15.0  # Trading timeout

    def test_data_feed_config(self):
        """Test data feed-specific configuration."""
        config = CircuitBreakerConfig.for_data_feed()
        assert config.failure_threshold == 10  # High tolerance
        assert config.recovery_timeout == 120  # Long recovery
        assert config.success_threshold == 5  # Feed stability
        assert config.timeout_seconds == 30.0  # Data retrieval time

    def test_ml_service_config(self):
        """Test ML service-specific configuration."""
        config = CircuitBreakerConfig.for_ml_service()
        assert config.failure_threshold == 3  # Fail fast for ML
        assert config.recovery_timeout == 45  # Moderate recovery
        assert config.success_threshold == 2  # Quick ML recovery
        assert config.timeout_seconds == 10.0  # ML inference timeout

    def test_llm_service_config(self):
        """Test LLM service-specific configuration."""
        config = CircuitBreakerConfig.for_llm_service()
        assert config.failure_threshold == 8  # Rate limit tolerance
        assert config.recovery_timeout == 300  # Rate limit reset
        assert config.success_threshold == 3  # API stability
        assert config.timeout_seconds == 60.0  # LLM processing time


class TestCircuitBreakerMetrics:
    """Test circuit breaker metrics collection."""

    def test_initial_metrics(self):
        """Test initial metrics state."""
        cb = CircuitBreaker("test", ServiceType.DATABASE)
        metrics = cb.metrics

        assert metrics.total_requests == 0
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 0
        assert metrics.circuit_open_count == 0
        assert metrics.last_failure_time is None
        assert metrics.last_success_time is None
        assert metrics.average_response_time == 0.0
        assert metrics.success_rate == 100.0
        assert metrics.failure_rate == 0.0

    def test_success_recording(self):
        """Test recording successful requests."""
        cb = CircuitBreaker("test", ServiceType.DATABASE)

        cb.metrics.record_success(0.1)
        cb.metrics.record_success(0.2)

        assert cb.metrics.total_requests == 2
        assert cb.metrics.successful_requests == 2
        assert cb.metrics.failed_requests == 0
        assert cb.metrics.success_rate == 100.0
        assert cb.metrics.failure_rate == 0.0
        assert (
            abs(cb.metrics.average_response_time - 0.15) < 1e-10
        )  # Fix floating point precision
        assert cb.metrics.last_success_time is not None

    def test_failure_recording(self):
        """Test recording failed requests."""
        cb = CircuitBreaker("test", ServiceType.DATABASE)

        cb.metrics.record_failure()
        cb.metrics.record_failure()

        assert cb.metrics.total_requests == 2
        assert cb.metrics.successful_requests == 0
        assert cb.metrics.failed_requests == 2
        assert cb.metrics.success_rate == 0.0
        assert cb.metrics.failure_rate == 100.0
        assert cb.metrics.last_failure_time is not None

    def test_mixed_success_failure(self):
        """Test mixed success and failure recording."""
        cb = CircuitBreaker("test", ServiceType.DATABASE)

        cb.metrics.record_success(0.1)
        cb.metrics.record_failure()
        cb.metrics.record_success(0.2)
        cb.metrics.record_failure()

        assert cb.metrics.total_requests == 4
        assert cb.metrics.successful_requests == 2
        assert cb.metrics.failed_requests == 2
        assert cb.metrics.success_rate == 50.0
        assert cb.metrics.failure_rate == 50.0

    def test_response_time_window(self):
        """Test response time window management."""
        cb = CircuitBreaker("test", ServiceType.DATABASE)

        # Record more than 100 response times
        for i in range(150):
            cb.metrics.record_success(i * 0.001)

        # Should keep only last 100 response times
        assert len(cb.metrics.response_times) == 100
        assert cb.metrics.response_times[0] == 0.05  # 50th item (0-indexed)


class TestCircuitBreakerStates:
    """Test circuit breaker state transitions."""

    def test_initial_state(self):
        """Test circuit breaker starts in closed state."""
        cb = CircuitBreaker("test", ServiceType.DATABASE)
        assert cb.state == CircuitState.CLOSED
        assert cb.is_closed
        assert not cb.is_open
        assert not cb.is_half_open

    def test_failure_threshold_opening(self):
        """Test circuit opens when failure threshold is reached."""
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker("test", ServiceType.DATABASE, config)

        # Simulate failures below threshold
        for i in range(2):
            cb._on_failure(Exception("test error"))
            assert cb.state == CircuitState.CLOSED

        # Trigger threshold
        cb._on_failure(Exception("test error"))
        assert cb.state == CircuitState.OPEN
        assert cb.is_open
        assert cb.metrics.circuit_open_count == 1

    def test_recovery_timeout_transition(self):
        """Test transition from open to half-open after timeout."""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=1)
        cb = CircuitBreaker("test", ServiceType.DATABASE, config)

        # Trigger circuit open
        cb._on_failure(Exception("error1"))
        cb._on_failure(Exception("error2"))
        assert cb.state == CircuitState.OPEN

        # Before timeout
        assert cb.is_open

        # After timeout
        time.sleep(1.1)
        assert not cb.is_open  # This triggers the timeout check
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_success_recovery(self):
        """Test successful recovery from half-open to closed."""
        config = CircuitBreakerConfig(
            failure_threshold=2, recovery_timeout=0.1, success_threshold=2
        )
        cb = CircuitBreaker("test", ServiceType.DATABASE, config)

        # Open the circuit
        cb._on_failure(Exception("error1"))
        cb._on_failure(Exception("error2"))
        assert cb.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(0.2)
        _ = cb.is_open  # Trigger timeout check
        assert cb.state == CircuitState.HALF_OPEN

        # Successful recoveries
        cb._on_success(0.1)
        assert cb.state == CircuitState.HALF_OPEN  # Still half-open

        cb._on_success(0.1)
        assert cb.state == CircuitState.CLOSED  # Now closed

    def test_half_open_failure_reopening(self):
        """Test circuit reopens if half-open test fails."""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=0.1)
        cb = CircuitBreaker("test", ServiceType.DATABASE, config)

        # Open the circuit
        cb._on_failure(Exception("error1"))
        cb._on_failure(Exception("error2"))

        # Wait for recovery timeout
        time.sleep(0.2)
        _ = cb.is_open  # Trigger timeout check
        assert cb.state == CircuitState.HALF_OPEN

        # Fail during half-open
        cb._on_failure(Exception("half-open failure"))
        assert cb.state == CircuitState.OPEN
        assert cb.metrics.circuit_open_count == 2

    def test_reset_functionality(self):
        """Test manual circuit reset."""
        config = CircuitBreakerConfig(failure_threshold=2)
        cb = CircuitBreaker("test", ServiceType.DATABASE, config)

        # Open the circuit
        cb._on_failure(Exception("error1"))
        cb._on_failure(Exception("error2"))
        assert cb.state == CircuitState.OPEN

        # Reset
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0
        assert cb._success_count == 0
        assert cb._last_failure_time is None


class TestCircuitBreakerExecution:
    """Test circuit breaker function execution protection."""

    @pytest.fixture
    def mock_function(self):
        """Create mock function for testing."""
        return Mock(return_value="success")

    @pytest.fixture
    def mock_async_function(self):
        """Create mock async function for testing."""
        async_mock = Mock()
        async_mock.return_value = asyncio.Future()
        async_mock.return_value.set_result("async_success")
        return async_mock

    def test_sync_function_success(self, mock_function):
        """Test successful synchronous function execution."""
        cb = CircuitBreaker("test", ServiceType.DATABASE)

        result = cb.call(mock_function, "arg1", key="arg2")

        assert result == "success"
        mock_function.assert_called_once_with("arg1", key="arg2")
        assert cb.metrics.successful_requests == 1
        assert cb.metrics.total_requests == 1

    def test_sync_function_failure(self, mock_function):
        """Test synchronous function failure handling."""
        cb = CircuitBreaker("test", ServiceType.DATABASE)
        mock_function.side_effect = Exception("test error")

        with pytest.raises(Exception, match="test error"):
            cb.call(mock_function)

        assert cb.metrics.failed_requests == 1
        assert cb.metrics.total_requests == 1
        assert cb._failure_count == 1

    def test_sync_function_circuit_open(self, mock_function):
        """Test synchronous function blocked when circuit is open."""
        config = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker("test", ServiceType.DATABASE, config)

        # Open the circuit
        mock_function.side_effect = Exception("test error")
        with pytest.raises(Exception):
            cb.call(mock_function)

        assert cb.state == CircuitState.OPEN

        # Next call should be blocked
        mock_function.side_effect = None
        mock_function.return_value = "success"

        with pytest.raises(CircuitBreakerError):
            cb.call(mock_function)

        # Function should not be called
        assert mock_function.call_count == 1

    @pytest.mark.asyncio
    async def test_async_function_success(self):
        """Test successful asynchronous function execution."""
        cb = CircuitBreaker("test", ServiceType.DATABASE)

        async def async_func(arg1, key=None):
            return f"async_success_{arg1}_{key}"

        result = await cb.call_async(async_func, "test", key="value")

        assert result == "async_success_test_value"
        assert cb.metrics.successful_requests == 1

    @pytest.mark.asyncio
    async def test_async_function_failure(self):
        """Test asynchronous function failure handling."""
        cb = CircuitBreaker("test", ServiceType.DATABASE)

        async def failing_async_func():
            raise Exception("async test error")

        with pytest.raises(Exception, match="async test error"):
            await cb.call_async(failing_async_func)

        assert cb.metrics.failed_requests == 1
        assert cb._failure_count == 1

    @pytest.mark.asyncio
    async def test_async_function_timeout(self):
        """Test asynchronous function timeout handling."""
        config = CircuitBreakerConfig(timeout_seconds=0.1)
        cb = CircuitBreaker("test", ServiceType.DATABASE, config)

        async def slow_async_func():
            await asyncio.sleep(0.2)
            return "should not reach here"

        with pytest.raises(asyncio.TimeoutError):
            await cb.call_async(slow_async_func)

        assert cb.metrics.failed_requests == 1

    @pytest.mark.asyncio
    async def test_async_function_circuit_open(self):
        """Test asynchronous function blocked when circuit is open."""
        config = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker("test", ServiceType.DATABASE, config)

        # Open the circuit
        async def failing_func():
            raise Exception("test error")

        with pytest.raises(Exception):
            await cb.call_async(failing_func)

        assert cb.state == CircuitState.OPEN

        # Next call should be blocked
        async def success_func():
            return "success"

        with pytest.raises(CircuitBreakerError):
            await cb.call_async(success_func)


class TestCircuitBreakerExceptionHandling:
    """Test circuit breaker exception handling and filtering."""

    def test_exclude_exceptions(self):
        """Test that excluded exceptions don't count as failures."""
        config = CircuitBreakerConfig(
            failure_threshold=2, exclude_exceptions=[ValueError, TypeError]
        )
        cb = CircuitBreaker("test", ServiceType.DATABASE, config)

        # These should not count as failures
        cb._on_failure(ValueError("excluded"))
        cb._on_failure(TypeError("also excluded"))

        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0
        assert cb.metrics.failed_requests == 0  # Not recorded as failures

    def test_expected_exceptions(self):
        """Test that only expected exceptions count as failures."""
        config = CircuitBreakerConfig(
            failure_threshold=2, expected_exceptions=[RuntimeError]
        )
        cb = CircuitBreaker("test", ServiceType.DATABASE, config)

        # This should count as failure
        cb._on_failure(RuntimeError("expected"))
        assert cb._failure_count == 1

        # This should not count as failure
        cb._on_failure(ValueError("not expected"))
        assert cb._failure_count == 1

    def test_exclude_overrides_expected(self):
        """Test that exclude_exceptions overrides expected_exceptions."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            expected_exceptions=[Exception],  # Catch all
            exclude_exceptions=[ValueError],  # But exclude ValueError
        )
        cb = CircuitBreaker("test", ServiceType.DATABASE, config)

        cb._on_failure(RuntimeError("should count"))
        assert cb._failure_count == 1

        cb._on_failure(ValueError("should not count"))
        assert cb._failure_count == 1  # Still 1


class TestCircuitBreakerManager:
    """Test circuit breaker manager functionality."""

    def test_register_circuit_breaker(self):
        """Test registering a new circuit breaker."""
        manager = CircuitBreakerManager()

        cb = manager.register("test_db", ServiceType.DATABASE)

        assert cb.name == "test_db"
        assert cb.service_type == ServiceType.DATABASE
        assert manager.get("test_db") is cb

    def test_register_duplicate_returns_existing(self):
        """Test registering duplicate returns existing instance."""
        manager = CircuitBreakerManager()

        cb1 = manager.register("test_db", ServiceType.DATABASE)
        cb2 = manager.register("test_db", ServiceType.BROKER_API)

        assert cb1 is cb2  # Same instance returned

    def test_get_or_create(self):
        """Test get_or_create functionality."""
        manager = CircuitBreakerManager()

        # Should create new
        cb1 = manager.get_or_create("new_cb", ServiceType.DATABASE)
        assert cb1.name == "new_cb"

        # Should return existing
        cb2 = manager.get_or_create("new_cb", ServiceType.BROKER_API)
        assert cb1 is cb2

    def test_get_all_metrics(self):
        """Test getting metrics for all circuit breakers."""
        manager = CircuitBreakerManager()

        cb1 = manager.register("cb1", ServiceType.DATABASE)
        cb2 = manager.register("cb2", ServiceType.BROKER_API)

        # Generate some metrics
        cb1._on_success(0.1)
        cb2._on_failure(Exception("test"))

        metrics = manager.get_all_metrics()

        assert len(metrics) == 2
        assert "cb1" in metrics
        assert "cb2" in metrics
        assert metrics["cb1"]["metrics"]["successful_requests"] == 1
        assert metrics["cb2"]["metrics"]["failed_requests"] == 1

    def test_get_unhealthy_circuits(self):
        """Test identifying unhealthy circuit breakers."""
        manager = CircuitBreakerManager()

        # Healthy circuit
        cb1 = manager.register("healthy", ServiceType.DATABASE)
        cb1._on_success(0.1)

        # Open circuit
        config = CircuitBreakerConfig(failure_threshold=1)
        cb2 = manager.register("open", ServiceType.BROKER_API, config)
        cb2._on_failure(Exception("test"))

        # High failure rate circuit
        cb3 = manager.register("high_failure", ServiceType.DATA_FEED)
        for _ in range(10):
            cb3._on_failure(Exception("test"))
        cb3._on_success(0.1)  # 90% failure rate

        unhealthy = manager.get_unhealthy_circuits()

        assert "healthy" not in unhealthy
        assert "open" in unhealthy
        assert "high_failure" in unhealthy

    def test_reset_all(self):
        """Test resetting all circuit breakers."""
        manager = CircuitBreakerManager()

        # Create circuits and make them unhealthy
        config = CircuitBreakerConfig(failure_threshold=1)
        cb1 = manager.register("cb1", ServiceType.DATABASE, config)
        cb2 = manager.register("cb2", ServiceType.BROKER_API, config)

        cb1._on_failure(Exception("test"))
        cb2._on_failure(Exception("test"))

        assert cb1.state == CircuitState.OPEN
        assert cb2.state == CircuitState.OPEN

        manager.reset_all()

        assert cb1.state == CircuitState.CLOSED
        assert cb2.state == CircuitState.CLOSED

    def test_shutdown(self):
        """Test manager shutdown."""
        manager = CircuitBreakerManager()

        manager.register("cb1", ServiceType.DATABASE)
        manager.register("cb2", ServiceType.BROKER_API)

        assert len(manager._circuit_breakers) == 2

        manager.shutdown()

        assert len(manager._circuit_breakers) == 0


class TestCircuitBreakerDecorator:
    """Test circuit breaker decorator functionality."""

    def test_sync_function_decorator(self):
        """Test decorator on synchronous function."""

        @circuit_breaker_decorator("test_sync", ServiceType.DATABASE)
        def test_function(x, y):
            return x + y

        result = test_function(2, 3)
        assert result == 5

        # Check circuit breaker was created
        manager = get_circuit_breaker_manager()
        cb = manager.get("test_sync")
        assert cb is not None
        assert cb.metrics.successful_requests == 1

    @pytest.mark.asyncio
    async def test_async_function_decorator(self):
        """Test decorator on asynchronous function."""

        @circuit_breaker_decorator("test_async", ServiceType.DATABASE)
        async def async_test_function(x, y):
            return x * y

        result = await async_test_function(3, 4)
        assert result == 12

        # Check circuit breaker was created
        manager = get_circuit_breaker_manager()
        cb = manager.get("test_async")
        assert cb is not None
        assert cb.metrics.successful_requests == 1

    def test_decorator_with_custom_config(self):
        """Test decorator with custom configuration."""
        custom_config = CircuitBreakerConfig(failure_threshold=10)

        @circuit_breaker_decorator("custom_config", ServiceType.DATABASE, custom_config)
        def test_function():
            return "test"

        result = test_function()
        assert result == "test"

        # Check custom configuration was applied
        manager = get_circuit_breaker_manager()
        cb = manager.get("custom_config")
        assert cb.config.failure_threshold == 10


class TestConvenienceFunctions:
    """Test convenience functions for common FXML4 services."""

    def test_get_database_circuit_breaker(self):
        """Test database circuit breaker convenience function."""
        cb = get_database_circuit_breaker()

        assert cb.name == "database"
        assert cb.service_type == ServiceType.DATABASE
        assert cb.config.failure_threshold == 3  # Database-specific config

    def test_get_broker_api_circuit_breaker(self):
        """Test broker API circuit breaker convenience function."""
        cb = get_broker_api_circuit_breaker("ib")

        assert cb.name == "broker_ib"
        assert cb.service_type == ServiceType.BROKER_API
        assert cb.config.failure_threshold == 5  # Broker-specific config

    def test_get_data_feed_circuit_breaker(self):
        """Test data feed circuit breaker convenience function."""
        cb = get_data_feed_circuit_breaker("polygon")

        assert cb.name == "feed_polygon"
        assert cb.service_type == ServiceType.DATA_FEED
        assert cb.config.failure_threshold == 10  # Feed-specific config

    def test_get_ml_service_circuit_breaker(self):
        """Test ML service circuit breaker convenience function."""
        cb = get_ml_service_circuit_breaker("xgboost")

        assert cb.name == "ml_xgboost"
        assert cb.service_type == ServiceType.ML_SERVICE
        assert cb.config.failure_threshold == 3  # ML-specific config

    def test_get_llm_service_circuit_breaker(self):
        """Test LLM service circuit breaker convenience function."""
        cb = get_llm_service_circuit_breaker("openai")

        assert cb.name == "llm_openai"
        assert cb.service_type == ServiceType.LLM_SERVICE
        assert cb.config.failure_threshold == 8  # LLM-specific config


class TestThreadSafety:
    """Test thread safety of circuit breaker operations."""

    def test_concurrent_state_changes(self):
        """Test concurrent state changes are handled safely."""
        config = CircuitBreakerConfig(failure_threshold=5)
        cb = CircuitBreaker("concurrent_test", ServiceType.DATABASE, config)

        def worker_success():
            for _ in range(10):
                cb._on_success(0.1)
                time.sleep(0.001)

        def worker_failure():
            for _ in range(10):
                cb._on_failure(Exception("test"))
                time.sleep(0.001)

        # Start concurrent operations
        threads = []
        for _ in range(2):
            t1 = threading.Thread(target=worker_success)
            t2 = threading.Thread(target=worker_failure)
            threads.extend([t1, t2])
            t1.start()
            t2.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Verify final state is consistent
        assert (
            cb.metrics.total_requests
            == cb.metrics.successful_requests + cb.metrics.failed_requests
        )
        assert cb._failure_count >= 0
        assert cb._success_count >= 0

    def test_concurrent_metrics_collection(self):
        """Test concurrent metrics collection."""
        cb = CircuitBreaker("metrics_test", ServiceType.DATABASE)
        results = []

        def collect_metrics():
            for _ in range(5):
                results.append(cb.get_metrics())
                time.sleep(0.01)

        def generate_activity():
            for _ in range(10):
                cb._on_success(0.1)
                time.sleep(0.01)

        # Start concurrent operations
        t1 = threading.Thread(target=collect_metrics)
        t2 = threading.Thread(target=generate_activity)

        t1.start()
        t2.start()

        t1.join()
        t2.join()

        # Verify all metrics collections succeeded
        assert len(results) == 5
        for metrics in results:
            assert "name" in metrics
            assert "state" in metrics
            assert "metrics" in metrics


class TestIntegrationScenarios:
    """Test realistic integration scenarios for FXML4 trading system."""

    @pytest.mark.asyncio
    async def test_database_connection_scenario(self):
        """Test database connection protection scenario."""
        db_cb = get_database_circuit_breaker("timescaledb")

        # Simulate database connection function
        connection_attempts = 0

        async def connect_to_database():
            nonlocal connection_attempts
            connection_attempts += 1

            if connection_attempts <= 3:
                raise ConnectionError("Database connection failed")
            return {"status": "connected", "pool_size": 10}

        # First 3 attempts should fail and open circuit
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await db_cb.call_async(connect_to_database)

        assert db_cb.state == CircuitState.OPEN

        # Next attempt should be blocked by circuit breaker
        with pytest.raises(CircuitBreakerError):
            await db_cb.call_async(connect_to_database)

        # Connection attempts should still be 3 (blocked by CB)
        assert connection_attempts == 3

    @pytest.mark.asyncio
    async def test_broker_api_failover_scenario(self):
        """Test broker API failover scenario."""
        ib_cb = get_broker_api_circuit_breaker("ib")
        fxcm_cb = get_broker_api_circuit_breaker("fxcm")

        # Simulate IB API failure
        async def ib_place_order(symbol, quantity):
            raise ConnectionError("IB API unavailable")

        # Simulate FXCM API success
        async def fxcm_place_order(symbol, quantity):
            return {"order_id": "FXCM123", "status": "submitted"}

        # Fail IB circuit breaker
        for _ in range(5):
            with pytest.raises(ConnectionError):
                await ib_cb.call_async(ib_place_order, "GBPUSD", 10000)

        assert ib_cb.state == CircuitState.OPEN

        # Should failover to FXCM
        result = await fxcm_cb.call_async(fxcm_place_order, "GBPUSD", 10000)
        assert result["order_id"] == "FXCM123"
        assert fxcm_cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_ml_model_inference_scenario(self):
        """Test ML model inference protection scenario."""
        ml_cb = get_ml_service_circuit_breaker("signal_generator")

        inference_count = 0

        async def generate_trading_signal(market_data):
            nonlocal inference_count
            inference_count += 1

            # Simulate model overload after 2 successful inferences
            if inference_count <= 2:
                return {"signal": "BUY", "confidence": 0.85}
            else:
                raise RuntimeError("Model inference timeout")

        # First 2 inferences succeed
        result1 = await ml_cb.call_async(generate_trading_signal, {"price": 1.3000})
        result2 = await ml_cb.call_async(generate_trading_signal, {"price": 1.3010})

        assert result1["signal"] == "BUY"
        assert result2["signal"] == "BUY"
        assert ml_cb.state == CircuitState.CLOSED

        # Next 3 fail and open circuit
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await ml_cb.call_async(generate_trading_signal, {"price": 1.3020})

        assert ml_cb.state == CircuitState.OPEN

        # Trading system should handle gracefully with fallback
        with pytest.raises(CircuitBreakerError):
            await ml_cb.call_async(generate_trading_signal, {"price": 1.3030})

    def test_comprehensive_system_health_check(self):
        """Test comprehensive system health monitoring."""
        # Create circuit breakers for all FXML4 services
        db_cb = get_database_circuit_breaker()
        ib_cb = get_broker_api_circuit_breaker("ib")
        fxcm_cb = get_broker_api_circuit_breaker("fxcm")
        polygon_cb = get_data_feed_circuit_breaker("polygon")
        ml_cb = get_ml_service_circuit_breaker("ensemble")
        llm_cb = get_llm_service_circuit_breaker("openai")

        # Simulate some service issues
        ib_cb._on_failure(Exception("IB connection lost"))
        polygon_cb._on_failure(Exception("Rate limit exceeded"))

        # Get system health status
        manager = get_circuit_breaker_manager()
        all_metrics = manager.get_all_metrics()
        unhealthy_circuits = manager.get_unhealthy_circuits()

        # Verify health monitoring
        assert len(all_metrics) >= 6  # All services registered
        assert "database" in all_metrics
        assert "broker_ib" in all_metrics
        assert "feed_polygon" in all_metrics

        # Some circuits should be healthy, others may have issues
        healthy_count = len(all_metrics) - len(unhealthy_circuits)
        assert healthy_count >= 4  # At least database, FXCM, ML, LLM should be healthy
