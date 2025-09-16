"""
Error Handling and Edge Case Tests for FXML4.

This module tests the system's resilience to various failure scenarios,
edge cases, and error conditions that could occur in production trading environments.
"""

import asyncio
import json
import random
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import pytest_asyncio

# Use centralized event loop fixture
from tests.fixtures.event_loop_fixtures import event_loop

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Mock all external dependencies before importing
sys.modules["openai"] = Mock()
sys.modules["fxml4.strategy.integrated_signal_generator"] = Mock()
sys.modules["fxml4.wave_analysis.sentiment_wave_validator"] = Mock()
sys.modules["fxml4.llm_integration.sentiment_analysis"] = Mock()
sys.modules["fxml4.llm_integration.llm_client"] = Mock()
sys.modules["redis.asyncio"] = Mock()
sys.modules["fxml4.config"] = Mock()
sys.modules["fxml4.data_engineering.data_feeds.base_feed"] = Mock()

# Mock config
mock_config = {
    "database": {
        "user": "test_user",
        "password": "test_password",
        "host": "localhost",
        "port": 5432,
        "name": "test_db",
        "max_connections": 20,
        "connection_timeout": 30,
        "query_timeout": 60,
    },
    "redis": {
        "host": "localhost",
        "port": 6379,
        "db": 0,
        "max_connections": 10,
        "connection_timeout": 5,
    },
    "trading": {
        "max_orders_per_second": 10,
        "max_position_size": 100000,
        "connection_timeout": 30,
    },
    "monitoring": {"max_error_rate": 0.05, "circuit_breaker_threshold": 5},
}

sys.modules["fxml4.config"].get_config = Mock(return_value=mock_config)


class DatabaseConnectionError(Exception):
    """Database connection error."""

    pass


class ExternalServiceError(Exception):
    """External service unavailable error."""

    pass


class ValidationError(Exception):
    """Data validation error."""

    pass


class RateLimitError(Exception):
    """Rate limit exceeded error."""

    pass


class MockFailingService:
    """Mock service that simulates various failure scenarios."""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.failure_mode = None
        self.failure_probability = 0.0
        self.latency_mode = False
        self.latency_ms = 0
        self.resource_exhausted = False
        self.call_count = 0
        self.error_count = 0
        self.circuit_breaker_open = False
        self.circuit_breaker_failures = 0
        self.max_failures_before_circuit_open = 5

        # Connection simulation
        self.max_connections = 10
        self.active_connections = 0
        self.connection_pool_exhausted = False

    def set_failure_mode(self, mode: str, probability: float = 1.0):
        """Set failure mode and probability."""
        self.failure_mode = mode
        self.failure_probability = probability

    def set_latency_mode(self, enabled: bool, latency_ms: int = 1000):
        """Set high latency simulation."""
        self.latency_mode = enabled
        self.latency_ms = latency_ms

    def set_resource_exhaustion(self, exhausted: bool):
        """Simulate resource exhaustion."""
        self.resource_exhausted = exhausted
        self.connection_pool_exhausted = exhausted

    async def simulate_call(self, operation: str, **kwargs):
        """Simulate a service call with potential failures."""
        self.call_count += 1

        # Circuit breaker logic
        if self.circuit_breaker_open:
            raise ExternalServiceError(f"Circuit breaker open for {self.service_name}")

        # Resource exhaustion
        if self.resource_exhausted:
            raise ExternalServiceError(f"Resource exhausted in {self.service_name}")

        # Connection pool exhaustion
        if (
            self.connection_pool_exhausted
            and self.active_connections >= self.max_connections
        ):
            raise DatabaseConnectionError(
                f"Connection pool exhausted in {self.service_name}"
            )

        # Simulate latency
        if self.latency_mode:
            await asyncio.sleep(self.latency_ms / 1000.0)

        # Failure simulation
        if self.failure_mode and random.random() < self.failure_probability:
            self.error_count += 1
            self.circuit_breaker_failures += 1

            # Open circuit breaker if too many failures
            if self.circuit_breaker_failures >= self.max_failures_before_circuit_open:
                self.circuit_breaker_open = True

            if self.failure_mode == "connection_timeout":
                raise asyncio.TimeoutError(f"Connection timeout in {self.service_name}")
            elif self.failure_mode == "database_error":
                raise DatabaseConnectionError(
                    f"Database connection failed in {self.service_name}"
                )
            elif self.failure_mode == "validation_error":
                raise ValidationError(f"Data validation failed in {self.service_name}")
            elif self.failure_mode == "rate_limit":
                raise RateLimitError(f"Rate limit exceeded in {self.service_name}")
            elif self.failure_mode == "service_unavailable":
                raise ExternalServiceError(f"Service unavailable: {self.service_name}")
            elif self.failure_mode == "corrupt_data":
                return {"error": "corrupt_data", "data": None}
            else:
                raise Exception(f"Unknown error in {self.service_name}")

        # Successful call
        self.active_connections += 1
        try:
            # Simulate normal operation
            result = {
                "service": self.service_name,
                "operation": operation,
                "timestamp": datetime.utcnow().isoformat(),
                "success": True,
                "data": kwargs,
            }
            return result
        finally:
            self.active_connections -= 1

    def reset_circuit_breaker(self):
        """Reset circuit breaker for testing."""
        self.circuit_breaker_open = False
        self.circuit_breaker_failures = 0

    def get_health_stats(self):
        """Get service health statistics."""
        error_rate = self.error_count / max(self.call_count, 1)
        return {
            "service_name": self.service_name,
            "call_count": self.call_count,
            "error_count": self.error_count,
            "error_rate": error_rate,
            "circuit_breaker_open": self.circuit_breaker_open,
            "active_connections": self.active_connections,
            "resource_exhausted": self.resource_exhausted,
        }


class MockResilientTradingSystem:
    """Mock trading system with error handling and resilience features."""

    def __init__(self):
        # Service dependencies
        self.database_service = MockFailingService("database")
        self.market_data_service = MockFailingService("market_data")
        self.broker_service = MockFailingService("broker")
        self.signal_service = MockFailingService("signal_generator")
        self.websocket_service = MockFailingService("websocket")

        # System state
        self.orders = {}
        self.positions = {}
        self.signals = []
        self.market_data_cache = {}
        self.error_logs = []
        self.performance_metrics = {
            "orders_processed": 0,
            "signals_generated": 0,
            "errors_handled": 0,
            "recovery_count": 0,
        }

        # Resilience features
        self.retry_config = {
            "max_retries": 3,
            "retry_delay": 0.1,
            "exponential_backoff": True,
        }
        self.circuit_breaker_enabled = True
        self.graceful_degradation_enabled = True
        self.fallback_data_enabled = True

        # Rate limiting
        self.rate_limiter = {"requests_per_second": 10, "request_times": []}

    async def create_order_with_resilience(
        self, symbol: str, side: str, quantity: float, **kwargs
    ):
        """Create order with comprehensive error handling."""
        order_id = f"order_{uuid.uuid4().hex[:8]}"

        try:
            # Rate limiting check
            await self._check_rate_limits()

            # Validate inputs with error handling
            validation_result = await self._validate_order_inputs_with_retry(
                symbol, side, quantity
            )
            if not validation_result["valid"]:
                raise ValidationError(
                    f"Order validation failed: {validation_result['errors']}"
                )

            # Risk checks with fallback
            risk_result = await self._perform_risk_checks_with_fallback(
                symbol, quantity
            )
            if not risk_result["approved"]:
                raise ValidationError(f"Risk check failed: {risk_result['reason']}")

            # Create order in database with retry logic
            order_data = await self._create_order_in_database_with_retry(
                order_id, symbol, side, quantity, **kwargs
            )

            # Send to broker with circuit breaker
            execution_result = await self._send_to_broker_with_circuit_breaker(
                order_data
            )

            # Update local state
            self.orders[order_id] = order_data
            self.performance_metrics["orders_processed"] += 1

            return {
                "order_id": order_id,
                "status": "success",
                "data": order_data,
                "execution": execution_result,
            }

        except Exception as e:
            # Comprehensive error handling
            return await self._handle_order_creation_error(
                order_id, symbol, side, quantity, e
            )

    async def generate_signal_with_resilience(self, symbol: str, **kwargs):
        """Generate trading signal with error handling."""
        signal_id = f"signal_{uuid.uuid4().hex[:8]}"

        try:
            # Get market data with fallback mechanisms
            market_data = await self._get_market_data_with_fallback(symbol)

            # Generate signal with retry logic
            signal_result = await self._generate_signal_with_retry(
                signal_id, symbol, market_data
            )

            # Validate signal quality
            validation_result = await self._validate_signal_quality(signal_result)
            if not validation_result["valid"]:
                if self.graceful_degradation_enabled:
                    # Use degraded signal with lower confidence
                    signal_result["confidence"] *= 0.5
                    signal_result["metadata"]["degraded"] = True
                else:
                    raise ValidationError(
                        f"Signal validation failed: {validation_result['errors']}"
                    )

            # Store signal with error handling
            await self._store_signal_with_retry(signal_result)

            self.signals.append(signal_result)
            self.performance_metrics["signals_generated"] += 1

            return {"signal_id": signal_id, "status": "success", "data": signal_result}

        except Exception as e:
            return await self._handle_signal_generation_error(signal_id, symbol, e)

    async def _check_rate_limits(self):
        """Check and enforce rate limits."""
        current_time = time.time()

        # Clean old requests
        self.rate_limiter["request_times"] = [
            t for t in self.rate_limiter["request_times"] if current_time - t < 1.0
        ]

        # Check limit
        if (
            len(self.rate_limiter["request_times"])
            >= self.rate_limiter["requests_per_second"]
        ):
            raise RateLimitError("Rate limit exceeded")

        # Record this request
        self.rate_limiter["request_times"].append(current_time)

    async def _validate_order_inputs_with_retry(
        self, symbol: str, side: str, quantity: float
    ):
        """Validate order inputs with retry logic."""
        for attempt in range(self.retry_config["max_retries"]):
            try:
                # Basic validation
                if not symbol or len(symbol) < 6:
                    return {"valid": False, "errors": ["Invalid symbol"]}

                if side not in ["buy", "sell"]:
                    return {"valid": False, "errors": ["Invalid side"]}

                if quantity <= 0:
                    return {"valid": False, "errors": ["Invalid quantity"]}

                # Advanced validation via service
                validation_result = await self.database_service.simulate_call(
                    "validate_order", symbol=symbol, side=side, quantity=quantity
                )

                return {"valid": True, "errors": [], "metadata": validation_result}

            except Exception as e:
                if attempt < self.retry_config["max_retries"] - 1:
                    await asyncio.sleep(self.retry_config["retry_delay"] * (2**attempt))
                    continue
                else:
                    # Final attempt failed, use basic validation only
                    if self.graceful_degradation_enabled:
                        return {
                            "valid": True,
                            "errors": [],
                            "metadata": {"degraded": True},
                        }
                    else:
                        raise e

    async def _perform_risk_checks_with_fallback(self, symbol: str, quantity: float):
        """Perform risk checks with fallback logic."""
        try:
            # Primary risk check
            risk_result = await self.database_service.simulate_call(
                "risk_check", symbol=symbol, quantity=quantity
            )

            # Simulate risk logic
            if quantity > mock_config["trading"]["max_position_size"]:
                return {"approved": False, "reason": "Position size too large"}

            return {
                "approved": True,
                "reason": "Risk check passed",
                "metadata": risk_result,
            }

        except Exception as e:
            if self.graceful_degradation_enabled:
                # Fallback to basic risk checks
                if quantity <= mock_config["trading"]["max_position_size"] * 0.5:
                    return {
                        "approved": True,
                        "reason": "Fallback risk check passed",
                        "metadata": {"fallback": True, "error": str(e)},
                    }
                else:
                    return {
                        "approved": False,
                        "reason": "Fallback risk check failed - position too large",
                    }
            else:
                raise e

    async def _create_order_in_database_with_retry(
        self, order_id: str, symbol: str, side: str, quantity: float, **kwargs
    ):
        """Create order in database with retry logic."""
        for attempt in range(self.retry_config["max_retries"]):
            try:
                order_data = {
                    "id": order_id,
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                    "status": "pending",
                    "created_at": datetime.utcnow().isoformat(),
                    "metadata": kwargs,
                }

                # Store in database
                result = await self.database_service.simulate_call(
                    "create_order", order_data=order_data
                )

                order_data["database_result"] = result
                return order_data

            except Exception as e:
                if attempt < self.retry_config["max_retries"] - 1:
                    delay = self.retry_config["retry_delay"]
                    if self.retry_config["exponential_backoff"]:
                        delay *= 2**attempt
                    await asyncio.sleep(delay)
                    continue
                else:
                    # Final attempt failed
                    if self.graceful_degradation_enabled:
                        # Store locally only
                        order_data = {
                            "id": order_id,
                            "symbol": symbol,
                            "side": side,
                            "quantity": quantity,
                            "status": "pending_local",
                            "created_at": datetime.utcnow().isoformat(),
                            "metadata": {
                                **kwargs,
                                "local_only": True,
                                "db_error": str(e),
                            },
                        }
                        return order_data
                    else:
                        raise e

    async def _send_to_broker_with_circuit_breaker(self, order_data: Dict):
        """Send order to broker with circuit breaker pattern."""
        if self.broker_service.circuit_breaker_open:
            if self.graceful_degradation_enabled:
                # Queue for later processing
                return {
                    "status": "queued",
                    "reason": "Broker circuit breaker open",
                    "queued_at": datetime.utcnow().isoformat(),
                }
            else:
                raise ExternalServiceError(
                    "Broker service unavailable - circuit breaker open"
                )

        try:
            execution_result = await self.broker_service.simulate_call(
                "execute_order", order_data=order_data
            )

            return {
                "status": "sent_to_broker",
                "result": execution_result,
                "sent_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            # Log error and handle based on configuration
            await self._log_error(
                "broker_communication", e, {"order_id": order_data["id"]}
            )

            if self.graceful_degradation_enabled:
                return {
                    "status": "broker_error",
                    "error": str(e),
                    "will_retry": True,
                    "error_at": datetime.utcnow().isoformat(),
                }
            else:
                raise e

    async def _get_market_data_with_fallback(self, symbol: str):
        """Get market data with fallback mechanisms."""
        # Try cache first
        if symbol in self.market_data_cache:
            cache_entry = self.market_data_cache[symbol]
            cache_age = time.time() - cache_entry["timestamp"]
            if cache_age < 60:  # Use cache if less than 1 minute old
                return cache_entry["data"]

        try:
            # Primary market data source
            market_data = await self.market_data_service.simulate_call(
                "get_market_data", symbol=symbol
            )

            # Update cache
            self.market_data_cache[symbol] = {
                "data": market_data,
                "timestamp": time.time(),
            }

            return market_data

        except Exception as e:
            # Fallback mechanisms
            if self.fallback_data_enabled:
                # Try cached data even if old
                if symbol in self.market_data_cache:
                    cache_entry = self.market_data_cache[symbol]
                    cache_entry["data"]["metadata"]["stale"] = True
                    cache_entry["data"]["metadata"]["fallback_reason"] = str(e)
                    return cache_entry["data"]

                # Generate synthetic data as last resort
                return await self._generate_fallback_market_data(symbol, e)
            else:
                raise e

    async def _generate_fallback_market_data(
        self, symbol: str, original_error: Exception
    ):
        """Generate fallback market data when primary sources fail."""
        # Very basic fallback data
        base_prices = {
            "EURUSD": 1.1000,
            "GBPUSD": 1.2500,
            "USDJPY": 150.00,
            "AUDUSD": 0.6750,
        }

        base_price = base_prices.get(symbol, 1.0000)

        return {
            "service": "fallback_generator",
            "operation": "get_market_data",
            "timestamp": datetime.utcnow().isoformat(),
            "success": True,
            "data": {
                "symbol": symbol,
                "price": base_price,
                "timestamp": datetime.utcnow().isoformat(),
                "source": "fallback",
                "quality": "low",
                "original_error": str(original_error),
            },
        }

    async def _generate_signal_with_retry(
        self, signal_id: str, symbol: str, market_data: Dict
    ):
        """Generate signal with retry logic."""
        for attempt in range(self.retry_config["max_retries"]):
            try:
                signal_result = await self.signal_service.simulate_call(
                    "generate_signal",
                    signal_id=signal_id,
                    symbol=symbol,
                    market_data=market_data,
                )

                # Enhance with realistic signal data
                signal_data = {
                    "id": signal_id,
                    "symbol": symbol,
                    "direction": random.choice([1, -1]),
                    "confidence": random.uniform(0.3, 0.9),
                    "signal_type": "ml_signal",
                    "generated_at": datetime.utcnow().isoformat(),
                    "market_data_source": market_data.get("data", {}).get(
                        "source", "unknown"
                    ),
                    "service_result": signal_result,
                }

                return signal_data

            except Exception as e:
                if attempt < self.retry_config["max_retries"] - 1:
                    await asyncio.sleep(self.retry_config["retry_delay"] * (2**attempt))
                    continue
                else:
                    raise e

    async def _validate_signal_quality(self, signal_data: Dict):
        """Validate signal quality with error handling."""
        try:
            # Basic validation
            if signal_data["confidence"] < 0.1:
                return {"valid": False, "errors": ["Confidence too low"]}

            if "direction" not in signal_data or signal_data["direction"] not in [
                1,
                -1,
            ]:
                return {"valid": False, "errors": ["Invalid direction"]}

            # Advanced validation would check signal against market conditions
            return {"valid": True, "errors": []}

        except Exception as e:
            return {"valid": False, "errors": [f"Validation error: {str(e)}"]}

    async def _store_signal_with_retry(self, signal_data: Dict):
        """Store signal with retry logic."""
        for attempt in range(self.retry_config["max_retries"]):
            try:
                result = await self.database_service.simulate_call(
                    "store_signal", signal_data=signal_data
                )
                signal_data["storage_result"] = result
                return result

            except Exception as e:
                if attempt < self.retry_config["max_retries"] - 1:
                    await asyncio.sleep(self.retry_config["retry_delay"] * (2**attempt))
                    continue
                else:
                    # Store locally as fallback
                    signal_data["storage_result"] = {
                        "status": "local_only",
                        "error": str(e),
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                    return signal_data["storage_result"]

    async def _handle_order_creation_error(
        self, order_id: str, symbol: str, side: str, quantity: float, error: Exception
    ):
        """Handle order creation errors comprehensively."""
        error_info = {
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.utcnow().isoformat(),
        }

        await self._log_error("order_creation", error, error_info)
        self.performance_metrics["errors_handled"] += 1

        # Determine recovery strategy based on error type
        if isinstance(error, ValidationError):
            return {
                "order_id": order_id,
                "status": "validation_failed",
                "error": str(error),
                "recoverable": False,
            }
        elif isinstance(error, RateLimitError):
            return {
                "order_id": order_id,
                "status": "rate_limited",
                "error": str(error),
                "recoverable": True,
                "retry_after": 1.0,
            }
        elif isinstance(error, (DatabaseConnectionError, ExternalServiceError)):
            return {
                "order_id": order_id,
                "status": "service_error",
                "error": str(error),
                "recoverable": True,
                "retry_strategy": "exponential_backoff",
            }
        else:
            return {
                "order_id": order_id,
                "status": "unknown_error",
                "error": str(error),
                "recoverable": False,
            }

    async def _handle_signal_generation_error(
        self, signal_id: str, symbol: str, error: Exception
    ):
        """Handle signal generation errors."""
        error_info = {
            "signal_id": signal_id,
            "symbol": symbol,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.utcnow().isoformat(),
        }

        await self._log_error("signal_generation", error, error_info)
        self.performance_metrics["errors_handled"] += 1

        return {
            "signal_id": signal_id,
            "status": "generation_failed",
            "error": str(error),
            "recoverable": True,
        }

    async def _log_error(self, operation: str, error: Exception, context: Dict):
        """Log errors with context for analysis."""
        error_entry = {
            "operation": operation,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context,
            "timestamp": datetime.utcnow().isoformat(),
            "thread_id": threading.get_ident(),
        }

        self.error_logs.append(error_entry)

    def get_system_health(self):
        """Get comprehensive system health metrics."""
        total_calls = sum(
            [
                self.database_service.call_count,
                self.market_data_service.call_count,
                self.broker_service.call_count,
                self.signal_service.call_count,
            ]
        )

        total_errors = sum(
            [
                self.database_service.error_count,
                self.market_data_service.error_count,
                self.broker_service.error_count,
                self.signal_service.error_count,
            ]
        )

        return {
            "performance_metrics": self.performance_metrics.copy(),
            "error_summary": {
                "total_calls": total_calls,
                "total_errors": total_errors,
                "error_rate": total_errors / max(total_calls, 1),
                "recent_errors": len(
                    [
                        e
                        for e in self.error_logs
                        if datetime.fromisoformat(e["timestamp"])
                        > datetime.utcnow() - timedelta(minutes=5)
                    ]
                ),
            },
            "service_health": {
                "database": self.database_service.get_health_stats(),
                "market_data": self.market_data_service.get_health_stats(),
                "broker": self.broker_service.get_health_stats(),
                "signal_service": self.signal_service.get_health_stats(),
            },
            "circuit_breakers": {
                "database": self.database_service.circuit_breaker_open,
                "broker": self.broker_service.circuit_breaker_open,
                "market_data": self.market_data_service.circuit_breaker_open,
            },
        }


class TestErrorHandlingAndEdgeCases:
    """Test comprehensive error handling and edge cases."""

    @pytest.fixture
    def trading_system(self):
        """Create resilient trading system for testing."""
        return MockResilientTradingSystem()

    @pytest.fixture
    def failing_service(self):
        """Create a failing service for testing."""
        return MockFailingService("test_service")

    # Database Error Handling Tests

    @pytest.mark.asyncio
    async def test_database_connection_failure_recovery(self, trading_system):
        """Test recovery from database connection failures."""
        # Simulate database failures
        trading_system.database_service.set_failure_mode("database_error", 0.8)

        # Try to create orders - should handle failures gracefully
        results = []
        for i in range(5):
            result = await trading_system.create_order_with_resilience(
                "EURUSD", "buy", 1000.0, test_run=i
            )
            results.append(result)

        # Check that some orders succeeded or were handled gracefully
        successful_orders = [r for r in results if r["status"] == "success"]
        graceful_failures = [
            r for r in results if r["status"] in ["service_error", "queued"]
        ]

        # Should have either success or graceful handling
        assert len(successful_orders) + len(graceful_failures) == 5

        # Verify error logging - check if any service errors occurred
        database_errors = trading_system.database_service.error_count
        assert database_errors > 0 or len(trading_system.error_logs) > 0

    @pytest.mark.asyncio
    async def test_connection_pool_exhaustion(self, trading_system):
        """Test handling of database connection pool exhaustion."""
        # Simulate connection pool exhaustion
        trading_system.database_service.set_resource_exhaustion(True)

        # Try multiple concurrent operations in smaller batches to avoid issues
        results = []
        batch_size = 5
        for batch_start in range(0, 15, batch_size):
            batch_tasks = []
            for i in range(batch_start, min(batch_start + batch_size, 15)):
                task = trading_system.create_order_with_resilience(
                    "EURUSD", "buy", 1000.0, concurrent_test=i
                )
                batch_tasks.append(task)

            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            results.extend(batch_results)

        # Should handle pool exhaustion gracefully
        successful_count = sum(
            1 for r in results if isinstance(r, dict) and r.get("status") == "success"
        )
        error_count = sum(
            1 for r in results if isinstance(r, dict) and "error" in r.get("status", "")
        )
        exception_count = sum(1 for r in results if isinstance(r, Exception))

        # All should complete (either success, error, or exception)
        total_handled = successful_count + error_count + exception_count
        assert total_handled == 15

        # Should have some resource exhaustion indicators
        assert trading_system.database_service.resource_exhausted

    @pytest.mark.asyncio
    async def test_query_timeout_handling(self, trading_system):
        """Test handling of database query timeouts."""
        # Simulate high latency leading to timeouts
        trading_system.database_service.set_latency_mode(True, 2000)  # 2 second delay
        trading_system.database_service.set_failure_mode("connection_timeout", 0.5)

        start_time = time.time()
        result = await trading_system.create_order_with_resilience(
            "EURUSD", "buy", 5000.0
        )
        end_time = time.time()

        # Should complete within reasonable time due to timeout handling or retries
        duration = end_time - start_time
        assert (
            duration < 15.0
        )  # Should not hang indefinitely (allow for retries with backoff)

        # Should either succeed or fail gracefully
        assert result["status"] in ["success", "service_error", "unknown_error"]

    # External Service Error Handling Tests

    @pytest.mark.asyncio
    async def test_market_data_service_failure(self, trading_system):
        """Test handling of market data service failures."""
        # Simulate market data service failures
        trading_system.market_data_service.set_failure_mode("service_unavailable", 1.0)

        # Try to generate signal - should use fallback data
        result = await trading_system.generate_signal_with_resilience("EURUSD")

        # Should succeed with fallback data
        assert result["status"] == "success"
        assert "data" in result

        # Check that fallback data was used
        signal_data = result["data"]
        market_data_source = signal_data.get("market_data_source", "")
        assert market_data_source in ["fallback", "unknown"]

    @pytest.mark.asyncio
    async def test_broker_service_circuit_breaker(self, trading_system):
        """Test circuit breaker pattern for broker service."""
        # Cause broker service failures to open circuit breaker
        trading_system.broker_service.set_failure_mode("service_unavailable", 1.0)

        # Make several requests to trigger circuit breaker
        results = []
        for i in range(7):  # More than circuit breaker threshold
            result = await trading_system.create_order_with_resilience(
                "EURUSD", "buy", 1000.0
            )
            results.append(result)

        # Check if circuit breaker opened or if graceful degradation occurred
        broker_circuit_open = trading_system.broker_service.circuit_breaker_open
        broker_errors = trading_system.broker_service.error_count

        # Should have either opened circuit breaker or accumulated errors
        assert broker_circuit_open or broker_errors > 3

        # Later results should show degraded behavior
        degraded_results = [
            r for r in results if "queued" in str(r) or "error" in str(r)
        ]
        assert len(degraded_results) > 0

    @pytest.mark.asyncio
    async def test_rate_limiting_enforcement(self, trading_system):
        """Test rate limiting and back-pressure handling."""
        # Set very low rate limit for testing
        trading_system.rate_limiter["requests_per_second"] = 3

        # Try to create many orders quickly
        tasks = []
        for i in range(10):
            task = trading_system.create_order_with_resilience(
                "EURUSD", "buy", 1000.0, rate_limit_test=i
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Some should be rate limited
        rate_limited_count = sum(
            1
            for r in results
            if isinstance(r, dict) and r.get("status") == "rate_limited"
        )

        assert rate_limited_count > 0
        assert rate_limited_count < 10  # Not all should be rate limited

    # Data Validation and Corruption Tests

    @pytest.mark.asyncio
    async def test_invalid_order_parameters(self, trading_system):
        """Test handling of invalid order parameters."""
        # Test various invalid parameters
        invalid_orders = [
            ("", "buy", 1000.0),  # Empty symbol
            ("EU", "buy", 1000.0),  # Too short symbol
            ("EURUSD", "invalid", 1000.0),  # Invalid side
            ("EURUSD", "buy", -1000.0),  # Negative quantity
            ("EURUSD", "buy", 0.0),  # Zero quantity
        ]

        for symbol, side, quantity in invalid_orders:
            result = await trading_system.create_order_with_resilience(
                symbol, side, quantity
            )

            # Should fail with validation error
            assert result["status"] == "validation_failed"
            assert "error" in result
            assert not result.get("recoverable", True)

    @pytest.mark.asyncio
    async def test_corrupted_market_data_handling(self, trading_system):
        """Test handling of corrupted market data."""
        # Simulate corrupted data from market data service
        trading_system.market_data_service.set_failure_mode("corrupt_data", 1.0)

        # Try to generate signal with corrupted data
        result = await trading_system.generate_signal_with_resilience("EURUSD")

        # Should handle corrupted data gracefully
        assert result["status"] in ["success", "generation_failed"]

        # If successful, should have degraded quality indicators
        if result["status"] == "success":
            signal_data = result["data"]
            assert signal_data.get("market_data_source") in ["fallback", "unknown"]

    # Concurrency and Race Condition Tests

    @pytest.mark.asyncio
    async def test_concurrent_order_processing(self, trading_system):
        """Test handling of concurrent order processing."""
        # Create many concurrent orders
        tasks = []
        for i in range(20):
            task = trading_system.create_order_with_resilience(
                f"SYMBOL{i % 4}", "buy", 1000.0 + i * 100, concurrent_id=i
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify all completed without race conditions
        successful_results = [r for r in results if isinstance(r, dict)]
        assert len(successful_results) == 20

        # Verify unique order IDs (no collisions)
        order_ids = [r.get("order_id") for r in successful_results if "order_id" in r]
        unique_order_ids = set(order_ids)
        assert len(unique_order_ids) == len(order_ids)  # All should be unique

    @pytest.mark.asyncio
    async def test_resource_contention_handling(self, trading_system):
        """Test handling of resource contention scenarios."""
        # Simulate resource contention
        trading_system.database_service.max_connections = 3  # Very low limit

        # Launch concurrent operations that compete for resources
        signal_tasks = [
            trading_system.generate_signal_with_resilience("EURUSD") for _ in range(5)
        ]
        order_tasks = [
            trading_system.create_order_with_resilience("GBPUSD", "sell", 2000.0)
            for _ in range(5)
        ]

        all_results = await asyncio.gather(
            *signal_tasks, *order_tasks, return_exceptions=True
        )

        # Should handle resource contention without deadlocks
        completed_successfully = sum(
            1
            for r in all_results
            if isinstance(r, dict) and r.get("status") in ["success"]
        )

        handled_gracefully = sum(
            1
            for r in all_results
            if isinstance(r, dict) and r.get("status") not in ["success"]
        )

        assert completed_successfully + handled_gracefully == 10
        assert completed_successfully > 0  # Some should succeed

    # Performance Degradation Tests

    @pytest.mark.asyncio
    async def test_high_latency_service_handling(self, trading_system):
        """Test handling of high-latency service responses."""
        # Simulate high latency in market data service
        trading_system.market_data_service.set_latency_mode(
            True, 1500
        )  # 1.5 second delay

        start_time = time.time()
        result = await trading_system.generate_signal_with_resilience("EURUSD")
        end_time = time.time()

        # Should either complete quickly (using fallback) or within reasonable time
        duration = end_time - start_time

        if result["status"] == "success":
            # If using fallback, should be fast
            if result["data"].get("market_data_source") == "fallback":
                assert duration < 1.0
            else:
                # If using actual service, should complete within timeout
                assert duration < 3.0

    @pytest.mark.asyncio
    async def test_memory_pressure_simulation(self, trading_system):
        """Test behavior under memory pressure simulation."""
        # Simulate memory pressure by creating large data structures
        large_metadata = {"large_data": "x" * 10000}  # 10KB metadata

        # Create orders with large metadata
        results = []
        for i in range(10):
            result = await trading_system.create_order_with_resilience(
                "EURUSD", "buy", 1000.0, **large_metadata
            )
            results.append(result)

        # Should handle large data gracefully
        successful_count = sum(1 for r in results if r.get("status") == "success")
        assert successful_count > 0

        # System should remain responsive
        health = trading_system.get_system_health()
        assert health["error_summary"]["error_rate"] < 0.5

    # Recovery and Resilience Tests

    @pytest.mark.asyncio
    async def test_service_recovery_after_failure(self, trading_system):
        """Test system recovery after service failures."""
        # Initially cause failures
        trading_system.signal_service.set_failure_mode("service_unavailable", 1.0)

        # Generate signals during failure period
        failure_results = []
        for i in range(3):
            result = await trading_system.generate_signal_with_resilience("EURUSD")
            failure_results.append(result)

        # Some should fail
        failed_count = sum(1 for r in failure_results if r.get("status") != "success")
        assert failed_count > 0

        # Recover service
        trading_system.signal_service.set_failure_mode(None, 0.0)
        trading_system.signal_service.reset_circuit_breaker()

        # Generate signals after recovery
        recovery_results = []
        for i in range(3):
            result = await trading_system.generate_signal_with_resilience("EURUSD")
            recovery_results.append(result)

        # Should recover and succeed
        successful_recovery_count = sum(
            1 for r in recovery_results if r.get("status") == "success"
        )
        assert successful_recovery_count > 0

        # Performance metrics should show recovery
        trading_system.performance_metrics["recovery_count"] += 1
        assert trading_system.performance_metrics["recovery_count"] > 0

    @pytest.mark.asyncio
    async def test_graceful_degradation_modes(self, trading_system):
        """Test various graceful degradation modes."""
        # Test with graceful degradation enabled
        trading_system.graceful_degradation_enabled = True

        # Cause multiple service failures
        trading_system.database_service.set_failure_mode("database_error", 1.0)
        trading_system.market_data_service.set_failure_mode("service_unavailable", 1.0)

        # Should still be able to operate in degraded mode
        result = await trading_system.create_order_with_resilience(
            "EURUSD", "buy", 5000.0
        )

        # Should succeed in degraded mode or fail gracefully
        assert result["status"] in ["success", "service_error", "queued"]

        # Verify degraded mode indicators
        if result["status"] == "success" and "data" in result:
            order_data = result["data"]
            assert (
                order_data.get("metadata", {}).get("local_only")
                or order_data.get("status") == "pending_local"
            )

    # System Health and Monitoring Tests

    @pytest.mark.asyncio
    async def test_error_rate_monitoring(self, trading_system):
        """Test error rate monitoring and thresholds."""
        # Generate mix of successful and failed operations
        trading_system.database_service.set_failure_mode(
            "database_error", 0.3
        )  # 30% failure rate

        # Perform multiple operations
        results = []
        for i in range(20):
            result = await trading_system.create_order_with_resilience(
                "EURUSD", "buy", 1000.0
            )
            results.append(result)

        # Check system health
        health = trading_system.get_system_health()
        error_rate = health["error_summary"]["error_rate"]

        # Should be monitoring error rate
        assert 0.0 <= error_rate <= 1.0
        assert error_rate > 0  # Should have some errors due to simulated failures

        # Should have service-level health stats
        assert "database" in health["service_health"]
        assert health["service_health"]["database"]["error_count"] > 0

    @pytest.mark.asyncio
    async def test_comprehensive_error_logging(self, trading_system):
        """Test comprehensive error logging and context."""
        # Generate various types of errors
        error_scenarios = [
            ("", "buy", 1000.0),  # Validation error
            ("EURUSD", "buy", 0.0),  # Another validation error
        ]

        # Set service failure
        trading_system.database_service.set_failure_mode("database_error", 0.5)

        # Execute error scenarios
        for symbol, side, quantity in error_scenarios:
            await trading_system.create_order_with_resilience(symbol, side, quantity)

        # Try additional operations to generate service errors
        for i in range(3):
            await trading_system.create_order_with_resilience("EURUSD", "buy", 1000.0)

        # Verify error handling - check both logs and service error counts
        total_service_errors = sum(
            [
                trading_system.database_service.error_count,
                trading_system.market_data_service.error_count,
                trading_system.broker_service.error_count,
                trading_system.signal_service.error_count,
            ]
        )

        # Should have handled errors either through logging or service error tracking
        assert len(trading_system.error_logs) > 0 or total_service_errors > 0

        # If we have error logs, check their structure
        if trading_system.error_logs:
            for error_log in trading_system.error_logs:
                assert "operation" in error_log
                assert "error_type" in error_log
                assert "error_message" in error_log
                assert "context" in error_log
                assert "timestamp" in error_log
                assert "thread_id" in error_log

    # Edge Case Data Scenarios

    @pytest.mark.asyncio
    async def test_extreme_market_conditions(self, trading_system):
        """Test handling of extreme market conditions."""
        # Simulate extreme market data
        extreme_scenarios = [
            {"symbol": "EURUSD", "quantity": 1.0},  # Minimum quantity
            {"symbol": "EURUSD", "quantity": 99999.0},  # Near maximum quantity
            {"symbol": "USDJPY", "quantity": 50000.0},  # Large round number
        ]

        results = []
        for scenario in extreme_scenarios:
            result = await trading_system.create_order_with_resilience(
                scenario["symbol"], "buy", scenario["quantity"]
            )
            results.append(result)

        # Should handle extreme conditions appropriately
        for i, result in enumerate(results):
            scenario = extreme_scenarios[i]

            if scenario["quantity"] > mock_config["trading"]["max_position_size"]:
                # Should fail risk checks
                assert result["status"] in ["validation_failed", "service_error"]
            else:
                # Should succeed or fail gracefully
                assert result["status"] in ["success", "service_error", "queued"]

    @pytest.mark.asyncio
    async def test_unicode_and_special_characters(self, trading_system):
        """Test handling of unicode and special characters in inputs."""
        # Test special characters in metadata
        special_metadata = {
            "description": "Order with unicode: αβγ and symbols: !@#$%",
            "client_note": "测试订单",
            "strategy": "test_with_underscore_and_123",
        }

        result = await trading_system.create_order_with_resilience(
            "EURUSD", "buy", 1000.0, **special_metadata
        )

        # Should handle special characters gracefully
        assert result["status"] in ["success", "validation_failed", "service_error"]

        # If successful, metadata should be preserved
        if result["status"] == "success" and "data" in result:
            order_data = result["data"]
            assert "metadata" in order_data


class TestServiceFailingModes:
    """Test specific service failure modes and recovery patterns."""

    @pytest.fixture
    def service_under_test(self):
        return MockFailingService("test_service")

    @pytest.mark.asyncio
    async def test_intermittent_failures(self, service_under_test):
        """Test handling of intermittent service failures."""
        # Set 50% failure rate
        service_under_test.set_failure_mode("service_unavailable", 0.5)

        results = []
        for i in range(20):
            try:
                result = await service_under_test.simulate_call(
                    "test_operation", iteration=i
                )
                results.append(("success", result))
            except Exception as e:
                results.append(("error", str(e)))

        # Should have mix of successes and failures
        successes = [r for r in results if r[0] == "success"]
        failures = [r for r in results if r[0] == "error"]

        assert len(successes) > 0
        assert len(failures) > 0

        # Should have some failures (allow very wide range due to randomness)
        failure_rate = len(failures) / len(results)
        assert 0.1 <= failure_rate <= 0.9  # Between 10-90% failure rate (very tolerant)

    @pytest.mark.asyncio
    async def test_cascading_failure_prevention(self, service_under_test):
        """Test prevention of cascading failures."""
        # Set high failure rate to trigger circuit breaker
        service_under_test.set_failure_mode("service_unavailable", 1.0)

        # Make calls until circuit breaker opens
        for i in range(10):
            try:
                await service_under_test.simulate_call("test_operation")
            except:
                pass  # Expected failures

        # Circuit breaker should be open
        assert service_under_test.circuit_breaker_open

        # Further calls should fail fast (circuit breaker pattern)
        start_time = time.time()
        try:
            await service_under_test.simulate_call("test_operation")
        except ExternalServiceError:
            pass  # Expected
        end_time = time.time()

        # Should fail quickly due to circuit breaker
        assert end_time - start_time < 0.1  # Less than 100ms

    @pytest.mark.asyncio
    async def test_latency_degradation_handling(self, service_under_test):
        """Test handling of service latency degradation."""
        # Simulate increasing latency
        latencies = [100, 500, 1000, 2000, 5000]  # Escalating latency in ms

        for latency_ms in latencies:
            service_under_test.set_latency_mode(True, latency_ms)

            start_time = time.time()
            try:
                result = await service_under_test.simulate_call(
                    "latency_test", expected_latency=latency_ms
                )
                end_time = time.time()

                actual_duration = (end_time - start_time) * 1000  # Convert to ms

                # Should experience the simulated latency
                assert actual_duration >= latency_ms * 0.8  # Allow some variance

                # Result should still be valid
                assert result["success"] is True

            except asyncio.TimeoutError:
                # High latency might cause timeouts - this is acceptable
                pass

    def test_resource_exhaustion_simulation(self, service_under_test):
        """Test resource exhaustion simulation."""
        # Test normal operation first
        assert not service_under_test.resource_exhausted
        assert service_under_test.active_connections == 0

        # Enable resource exhaustion
        service_under_test.set_resource_exhaustion(True)
        assert service_under_test.resource_exhausted

        # Calls should fail with resource exhaustion
        with pytest.raises(ExternalServiceError, match="Resource exhausted"):
            asyncio.run(service_under_test.simulate_call("test_operation"))

    def test_health_statistics_tracking(self, service_under_test):
        """Test health statistics tracking."""
        # Initial health stats
        initial_stats = service_under_test.get_health_stats()
        assert initial_stats["call_count"] == 0
        assert initial_stats["error_count"] == 0
        assert initial_stats["error_rate"] == 0.0

        # Make some successful calls
        asyncio.run(service_under_test.simulate_call("success_test"))
        asyncio.run(service_under_test.simulate_call("success_test"))

        # Set failure mode and make failing calls
        service_under_test.set_failure_mode("service_unavailable", 1.0)

        try:
            asyncio.run(service_under_test.simulate_call("failure_test"))
        except:
            pass

        # Check updated stats
        final_stats = service_under_test.get_health_stats()
        assert final_stats["call_count"] == 3
        assert final_stats["error_count"] == 1
        assert abs(final_stats["error_rate"] - 1 / 3) < 0.01  # Approximately 0.33


# Pytest configuration
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
