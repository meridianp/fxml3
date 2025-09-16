"""
Comprehensive TDD test suite for rate limiting system.

This module tests the production-ready rate limiting system including:
- User-based rate limiting (100 requests/minute per user)
- IP-based rate limiting (1000 requests/minute per IP)
- DDoS protection with burst detection
- Redis-based sliding window implementation
- Integration with JWT authentication
- Middleware integration and security headers
- Rate limit status and reset information
- Bypass mechanisms for privileged users
"""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
import redis.asyncio as aioredis
from fastapi import HTTPException, Request, Response
from fastapi.testclient import TestClient

from fxml4.api.auth.models import User
from fxml4.api.auth.rate_limiter import (
    RateLimitConfig,
    RateLimiter,
    RateLimitExceededError,
    RateLimitInfo,
    RateLimitMiddleware,
)


@pytest.mark.auth
@pytest.mark.security
class TestRateLimitConfig:
    """Test rate limiting configuration management."""

    def test_rate_limit_config_default_values(self):
        """Test default rate limit configuration values."""
        config = RateLimitConfig()

        # Verify default limits
        assert config.user_requests_per_minute == 100
        assert config.ip_requests_per_minute == 1000
        assert config.burst_multiplier == 1.5
        assert config.sliding_window_seconds == 60
        assert config.cleanup_interval_seconds == 300  # 5 minutes
        assert config.ddos_threshold_multiplier == 5.0

        # Verify Redis configuration
        assert config.redis_key_prefix == "rate_limit:"
        assert config.redis_expiry_seconds == 3600  # 1 hour

    def test_rate_limit_config_custom_values(self):
        """Test custom rate limit configuration."""
        config = RateLimitConfig(
            user_requests_per_minute=50,
            ip_requests_per_minute=500,
            burst_multiplier=2.0,
            sliding_window_seconds=30,
            ddos_threshold_multiplier=10.0,
        )

        assert config.user_requests_per_minute == 50
        assert config.ip_requests_per_minute == 500
        assert config.burst_multiplier == 2.0
        assert config.sliding_window_seconds == 30
        assert config.ddos_threshold_multiplier == 10.0

    def test_rate_limit_config_validation(self):
        """Test rate limit configuration validation."""
        # Test invalid values
        with pytest.raises(
            ValueError, match="user_requests_per_minute must be positive"
        ):
            RateLimitConfig(user_requests_per_minute=0)

        with pytest.raises(ValueError, match="ip_requests_per_minute must be positive"):
            RateLimitConfig(ip_requests_per_minute=-1)

        with pytest.raises(ValueError, match="burst_multiplier must be >= 1.0"):
            RateLimitConfig(burst_multiplier=0.5)

        with pytest.raises(ValueError, match="sliding_window_seconds must be positive"):
            RateLimitConfig(sliding_window_seconds=0)


@pytest.mark.auth
@pytest.mark.security
class TestRateLimitInfo:
    """Test rate limit information structures."""

    def test_rate_limit_info_creation(self):
        """Test rate limit info creation."""
        now = datetime.now(timezone.utc)
        reset_time = now + timedelta(minutes=1)

        info = RateLimitInfo(
            limit=100, remaining=75, reset_time=reset_time, retry_after=60
        )

        assert info.limit == 100
        assert info.remaining == 75
        assert info.reset_time == reset_time
        assert info.retry_after == 60

    def test_rate_limit_info_exceeded_calculation(self):
        """Test rate limit exceeded status calculation."""
        now = datetime.now(timezone.utc)
        reset_time = now + timedelta(minutes=1)

        # Not exceeded
        info = RateLimitInfo(
            limit=100, remaining=25, reset_time=reset_time, retry_after=60
        )
        assert not info.is_exceeded()

        # Exceeded
        info_exceeded = RateLimitInfo(
            limit=100, remaining=0, reset_time=reset_time, retry_after=60
        )
        assert info_exceeded.is_exceeded()

    def test_rate_limit_info_to_headers(self):
        """Test conversion to HTTP headers."""
        now = datetime.now(timezone.utc)
        reset_time = now + timedelta(minutes=1)

        info = RateLimitInfo(
            limit=100, remaining=75, reset_time=reset_time, retry_after=60
        )

        headers = info.to_headers()

        assert headers["X-RateLimit-Limit"] == "100"
        assert headers["X-RateLimit-Remaining"] == "75"
        assert headers["X-RateLimit-Reset"] == str(int(reset_time.timestamp()))
        assert headers["Retry-After"] == "60"


@pytest.mark.auth
@pytest.mark.security
class TestRateLimiter:
    """Test core rate limiting functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis_mock = AsyncMock(spec=aioredis.Redis)
        # Mock pipeline for atomic operations
        pipeline_mock = AsyncMock()
        pipeline_mock.execute.return_value = [
            None,
            0,
            None,
            None,
        ]  # Default pipeline results
        redis_mock.pipeline.return_value = pipeline_mock
        return redis_mock

    @pytest.fixture
    def rate_limiter(self, mock_redis):
        """Create rate limiter with mock Redis."""
        config = RateLimitConfig(
            user_requests_per_minute=100,
            ip_requests_per_minute=1000,
            sliding_window_seconds=60,
        )
        return RateLimiter(config=config, redis_client=mock_redis)

    @pytest.mark.asyncio
    async def test_check_user_rate_limit_within_limit(self, rate_limiter, mock_redis):
        """Test user rate limiting within allowed limits."""
        # Mock pipeline results - [removed_count, current_count, zadd_result, expire_result]
        pipeline_mock = mock_redis.pipeline.return_value
        pipeline_mock.execute.return_value = [
            0,
            49,
            1,
            True,
        ]  # 49 existing + 1 current = 50 total

        user_id = "test-user-123"
        result = await rate_limiter.check_user_rate_limit(user_id)

        assert not result.is_exceeded()
        assert result.limit == 100
        assert result.remaining == 100  # burst_limit (150) - current_count (50) = 100

        # Verify Redis pipeline was used
        mock_redis.pipeline.assert_called_once()
        pipeline_mock.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_user_rate_limit_exceeded(self, rate_limiter, mock_redis):
        """Test user rate limiting when limit exceeded."""
        # Mock pipeline results - user has made 160 requests (over burst limit of 150)
        pipeline_mock = mock_redis.pipeline.return_value
        pipeline_mock.execute.return_value = [
            0,
            159,
            1,
            True,
        ]  # 159 existing + 1 current = 160 total

        user_id = "test-user-456"
        result = await rate_limiter.check_user_rate_limit(user_id)

        assert result.is_exceeded()
        assert result.limit == 100
        assert result.remaining == 0
        assert result.retry_after == 60

    @pytest.mark.asyncio
    async def test_check_ip_rate_limit_within_limit(self, rate_limiter, mock_redis):
        """Test IP rate limiting within allowed limits."""
        # Mock pipeline results - IP has made 500 requests
        pipeline_mock = mock_redis.pipeline.return_value
        pipeline_mock.execute.return_value = [
            0,
            499,
            1,
            True,
        ]  # 499 existing + 1 current = 500 total

        ip_address = "192.168.1.100"
        result = await rate_limiter.check_ip_rate_limit(ip_address)

        assert not result.is_exceeded()
        assert result.limit == 1000
        assert result.remaining == 500

    @pytest.mark.asyncio
    async def test_check_ip_rate_limit_exceeded(self, rate_limiter, mock_redis):
        """Test IP rate limiting when limit exceeded."""
        # Mock pipeline results - IP has made 1200 requests (over limit)
        pipeline_mock = mock_redis.pipeline.return_value
        pipeline_mock.execute.return_value = [
            0,
            1199,
            1,
            True,
        ]  # 1199 existing + 1 current = 1200 total

        ip_address = "192.168.1.200"
        result = await rate_limiter.check_ip_rate_limit(ip_address)

        assert result.is_exceeded()
        assert result.limit == 1000
        assert result.remaining == 0

    @pytest.mark.asyncio
    async def test_burst_protection(self, rate_limiter, mock_redis):
        """Test burst protection with multiplier."""
        config = RateLimitConfig(
            user_requests_per_minute=100,
            burst_multiplier=1.5,  # Allow up to 150 requests in burst
        )
        rate_limiter.config = config

        # Mock pipeline results - user made 125 requests (within burst limit)
        pipeline_mock = mock_redis.pipeline.return_value
        pipeline_mock.execute.return_value = [
            0,
            124,
            1,
            True,
        ]  # 124 existing + 1 current = 125 total

        user_id = "burst-test-user"
        result = await rate_limiter.check_user_rate_limit(user_id)

        # Should not be exceeded due to burst allowance
        assert not result.is_exceeded()
        assert result.remaining == 25  # burst_limit (150) - current_count (125) = 25

    @pytest.mark.asyncio
    async def test_ddos_detection(self, rate_limiter, mock_redis):
        """Test DDoS detection with threshold multiplier."""
        # Mock pipeline results - IP made 6000 requests (6x normal limit)
        pipeline_mock = mock_redis.pipeline.return_value
        pipeline_mock.execute.return_value = [
            0,
            5999,
            1,
            True,
        ]  # 5999 existing + 1 current = 6000 total

        ip_address = "192.168.1.300"
        result = await rate_limiter.check_ip_rate_limit(ip_address)

        # Should detect potential DDoS
        assert result.is_exceeded()
        assert result.remaining == 0

        # Should have extended retry time for DDoS
        assert result.retry_after == 120  # 2x normal rate limit (60 * 2)

    @pytest.mark.asyncio
    async def test_sliding_window_cleanup(self, rate_limiter, mock_redis):
        """Test sliding window cleanup of old entries."""
        user_id = "cleanup-test-user"
        pipeline_mock = mock_redis.pipeline.return_value
        pipeline_mock.execute.return_value = [0, 10, 1, True]

        await rate_limiter.check_user_rate_limit(user_id)

        # Verify pipeline operations were called
        mock_redis.pipeline.assert_called_once()
        pipeline_mock.zremrangebyscore.assert_called_once()
        pipeline_mock.zcount.assert_called_once()
        pipeline_mock.zadd.assert_called_once()
        pipeline_mock.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_connection_error_handling(self, rate_limiter, mock_redis):
        """Test handling Redis connection errors."""
        # Mock Redis pipeline error
        mock_redis.pipeline.side_effect = Exception("Redis connection failed")

        user_id = "error-test-user"

        # Should not raise exception, but allow request (fail-open for availability)
        result = await rate_limiter.check_user_rate_limit(user_id)

        # In error cases, should allow the request but with conservative limits
        assert not result.is_exceeded()
        assert result.remaining == 50  # Half the normal limit as fallback

    @pytest.mark.asyncio
    async def test_privileged_user_bypass(self, rate_limiter, mock_redis):
        """Test bypassing rate limits for privileged users."""
        privileged_user_id = "admin-user-123"

        # Check with bypass enabled - should not even call Redis
        result = await rate_limiter.check_user_rate_limit(
            privileged_user_id, bypass_limit=True
        )

        assert not result.is_exceeded()
        assert result.remaining == 100  # Full limit available for privileged users
        # Redis should not be called when bypassing
        mock_redis.pipeline.assert_not_called()


@pytest.mark.auth
@pytest.mark.security
class TestRateLimitMiddleware:
    """Test rate limiting middleware integration."""

    @pytest.fixture
    def mock_rate_limiter(self):
        """Create mock rate limiter."""
        rate_limiter_mock = AsyncMock(spec=RateLimiter)
        # Add config attribute
        rate_limiter_mock.config = RateLimitConfig()
        return rate_limiter_mock

    @pytest.fixture
    def rate_limit_middleware(self, mock_rate_limiter):
        """Create rate limit middleware."""
        return RateLimitMiddleware(rate_limiter=mock_rate_limiter)

    @pytest.fixture
    def mock_request(self):
        """Create mock FastAPI request."""
        request = Mock(spec=Request)
        request.client.host = "192.168.1.100"
        request.headers = {"Authorization": "Bearer test-jwt-token"}
        request.url.path = "/api/trading/orders"
        request.method = "POST"
        return request

    @pytest.fixture
    def mock_user(self):
        """Create mock user for testing."""
        user = Mock(spec=User)
        user.id = "test-user-789"
        user.username = "trader_test"
        user.roles = [Mock(name="trader")]
        return user

    @pytest.mark.asyncio
    async def test_middleware_request_within_limits(
        self, rate_limit_middleware, mock_rate_limiter, mock_request, mock_user
    ):
        """Test middleware processing request within rate limits."""
        # Mock rate limit responses - both user and IP within limits
        user_limit_info = RateLimitInfo(
            limit=100,
            remaining=75,
            reset_time=datetime.now(timezone.utc) + timedelta(minutes=1),
            retry_after=60,
        )
        ip_limit_info = RateLimitInfo(
            limit=1000,
            remaining=900,
            reset_time=datetime.now(timezone.utc) + timedelta(minutes=1),
            retry_after=60,
        )

        mock_rate_limiter.check_user_rate_limit.return_value = user_limit_info
        mock_rate_limiter.check_ip_rate_limit.return_value = ip_limit_info

        # Mock call_next function
        async def mock_call_next(request):
            response = Mock(spec=Response)
            response.headers = {}
            return response

        # Process request through middleware
        response = await rate_limit_middleware.process_request(
            mock_request, mock_call_next, mock_user
        )

        # Verify rate limit headers were added
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    @pytest.mark.asyncio
    async def test_middleware_user_rate_limit_exceeded(
        self, rate_limit_middleware, mock_rate_limiter, mock_request, mock_user
    ):
        """Test middleware handling user rate limit exceeded."""
        # Mock rate limit response - user limit exceeded
        user_limit_info = RateLimitInfo(
            limit=100,
            remaining=0,
            reset_time=datetime.now(timezone.utc) + timedelta(minutes=1),
            retry_after=60,
        )
        ip_limit_info = RateLimitInfo(
            limit=1000,
            remaining=900,
            reset_time=datetime.now(timezone.utc) + timedelta(minutes=1),
            retry_after=60,
        )

        mock_rate_limiter.check_user_rate_limit.return_value = user_limit_info
        mock_rate_limiter.check_ip_rate_limit.return_value = ip_limit_info

        async def mock_call_next(request):
            return Mock(spec=Response)

        # Should raise rate limit exceeded error
        with pytest.raises(RateLimitExceededError) as exc_info:
            await rate_limit_middleware.process_request(
                mock_request, mock_call_next, mock_user
            )

        error = exc_info.value
        assert error.limit_type == "user"
        assert error.retry_after == 60
        assert "rate limit exceeded" in error.message.lower()

    @pytest.mark.asyncio
    async def test_middleware_ip_rate_limit_exceeded(
        self, rate_limit_middleware, mock_rate_limiter, mock_request, mock_user
    ):
        """Test middleware handling IP rate limit exceeded."""
        # Mock rate limit responses - IP limit exceeded
        user_limit_info = RateLimitInfo(
            limit=100,
            remaining=75,
            reset_time=datetime.now(timezone.utc) + timedelta(minutes=1),
            retry_after=60,
        )
        ip_limit_info = RateLimitInfo(
            limit=1000,
            remaining=0,
            reset_time=datetime.now(timezone.utc) + timedelta(minutes=1),
            retry_after=60,
        )

        mock_rate_limiter.check_user_rate_limit.return_value = user_limit_info
        mock_rate_limiter.check_ip_rate_limit.return_value = ip_limit_info

        async def mock_call_next(request):
            return Mock(spec=Response)

        # Should raise rate limit exceeded error for IP
        with pytest.raises(RateLimitExceededError) as exc_info:
            await rate_limit_middleware.process_request(
                mock_request, mock_call_next, mock_user
            )

        error = exc_info.value
        assert error.limit_type == "ip"

    @pytest.mark.asyncio
    async def test_middleware_unauthenticated_user_ip_only(
        self, rate_limit_middleware, mock_rate_limiter, mock_request
    ):
        """Test middleware processing unauthenticated request (IP-based only)."""
        # Remove authorization header
        mock_request.headers = {}

        # Mock IP rate limit response
        ip_limit_info = RateLimitInfo(
            limit=1000,
            remaining=900,
            reset_time=datetime.now(timezone.utc) + timedelta(minutes=1),
            retry_after=60,
        )

        mock_rate_limiter.check_ip_rate_limit.return_value = ip_limit_info

        async def mock_call_next(request):
            response = Mock(spec=Response)
            response.headers = {}
            return response

        # Process unauthenticated request
        response = await rate_limit_middleware.process_request(
            mock_request, mock_call_next, user=None
        )

        # Should only check IP rate limit, not user rate limit
        mock_rate_limiter.check_ip_rate_limit.assert_called_once()
        mock_rate_limiter.check_user_rate_limit.assert_not_called()

        # Should still add IP rate limit headers
        assert "X-RateLimit-Limit" in response.headers

    @pytest.mark.asyncio
    async def test_middleware_whitelisted_endpoints(
        self, rate_limit_middleware, mock_rate_limiter, mock_request, mock_user
    ):
        """Test middleware bypassing rate limits for whitelisted endpoints."""
        # Set request to health check endpoint (should be whitelisted)
        mock_request.url.path = "/health"

        async def mock_call_next(request):
            response = Mock(spec=Response)
            response.headers = {}
            return response

        response = await rate_limit_middleware.process_request(
            mock_request, mock_call_next, mock_user
        )

        # Should not check rate limits for whitelisted endpoints
        mock_rate_limiter.check_user_rate_limit.assert_not_called()
        mock_rate_limiter.check_ip_rate_limit.assert_not_called()


@pytest.mark.auth
@pytest.mark.security
class TestRateLimitingIntegration:
    """Test rate limiting integration scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_requests_same_user(self):
        """Test concurrent requests from same user."""
        config = RateLimitConfig(user_requests_per_minute=10, sliding_window_seconds=60)

        # Mock Redis for concurrent testing
        mock_redis = AsyncMock(spec=aioredis.Redis)
        pipeline_mock = AsyncMock()
        pipeline_mock.execute.return_value = [
            0,
            4,
            1,
            True,
        ]  # 4 existing + 1 current = 5 total per request
        mock_redis.pipeline.return_value = pipeline_mock

        rate_limiter = RateLimiter(config=config, redis_client=mock_redis)
        user_id = "concurrent-test-user"

        # Simulate 3 concurrent requests
        tasks = [rate_limiter.check_user_rate_limit(user_id) for _ in range(3)]

        results = await asyncio.gather(*tasks)

        # All should pass since each sees 5 total requests < burst limit (15)
        for result in results:
            assert not result.is_exceeded()

    @pytest.mark.asyncio
    async def test_rate_limit_reset_timing(self):
        """Test rate limit reset timing accuracy."""
        config = RateLimitConfig(sliding_window_seconds=60)  # Use default 60 seconds

        mock_redis = AsyncMock(spec=aioredis.Redis)
        # Mock pipeline
        pipeline_mock = AsyncMock()
        pipeline_mock.execute.return_value = [0, 0, 1, True]  # No existing requests
        mock_redis.pipeline.return_value = pipeline_mock

        rate_limiter = RateLimiter(config=config, redis_client=mock_redis)
        user_id = "timing-test-user"

        # Check rate limit
        result = await rate_limiter.check_user_rate_limit(user_id)

        # Verify reset time is approximately 60 seconds from now
        now = datetime.now(timezone.utc)
        expected_reset = now + timedelta(seconds=60)

        # Allow for reasonable timing differences (within 5 seconds)
        time_diff = abs((result.reset_time - expected_reset).total_seconds())
        assert time_diff < 5

    def test_rate_limit_key_generation(self):
        """Test Redis key generation for different limit types."""
        config = RateLimitConfig(redis_key_prefix="test_rate_limit:")
        mock_redis = AsyncMock()
        rate_limiter = RateLimiter(config=config, redis_client=mock_redis)

        # Test user key generation
        user_key = rate_limiter._generate_user_key("user123")
        assert user_key == "test_rate_limit:user:user123"

        # Test IP key generation
        ip_key = rate_limiter._generate_ip_key("192.168.1.1")
        assert ip_key == "test_rate_limit:ip:192.168.1.1"

    @pytest.mark.asyncio
    async def test_cleanup_old_entries_performance(self):
        """Test performance of cleanup operations."""
        config = RateLimitConfig(sliding_window_seconds=60)
        mock_redis = AsyncMock(spec=aioredis.Redis)

        rate_limiter = RateLimiter(config=config, redis_client=mock_redis)

        # Test cleanup with many entries
        await rate_limiter.cleanup_old_entries()

        # Should call Redis cleanup operations efficiently
        mock_redis.eval.assert_called()  # Should use Lua script for atomic cleanup


@pytest.mark.auth
@pytest.mark.security
class TestRateLimitingErrorScenarios:
    """Test error handling and edge cases in rate limiting."""

    @pytest.mark.asyncio
    async def test_malformed_ip_address_handling(self):
        """Test handling of malformed IP addresses."""
        config = RateLimitConfig()
        mock_redis = AsyncMock(spec=aioredis.Redis)
        rate_limiter = RateLimiter(config=config, redis_client=mock_redis)

        # Test various malformed IP addresses
        malformed_ips = ["invalid.ip", "999.999.999.999", "", None]

        for ip in malformed_ips:
            try:
                result = await rate_limiter.check_ip_rate_limit(ip)
                # Should handle gracefully, not crash
                assert isinstance(result, RateLimitInfo)
            except Exception as e:
                # If exception is raised, it should be a known type
                assert isinstance(e, (ValueError, TypeError))

    @pytest.mark.asyncio
    async def test_extremely_high_request_volume(self):
        """Test handling of extremely high request volumes."""
        config = RateLimitConfig(user_requests_per_minute=1000000)  # Very high limit
        mock_redis = AsyncMock(spec=aioredis.Redis)
        # Mock pipeline - user made 1499999 requests, limit is 1000000 with 1.5x burst = 1500000
        pipeline_mock = AsyncMock()
        pipeline_mock.execute.return_value = [
            0,
            1499998,
            1,
            True,
        ]  # 1499998 existing + 1 current = 1499999
        mock_redis.pipeline.return_value = pipeline_mock

        rate_limiter = RateLimiter(config=config, redis_client=mock_redis)

        result = await rate_limiter.check_user_rate_limit("high-volume-user")

        assert not result.is_exceeded()
        assert (
            result.remaining == 1
        )  # burst_limit (1500000) - current_count (1499999) = 1

    @pytest.mark.asyncio
    async def test_time_synchronization_issues(self):
        """Test handling of time synchronization issues."""
        config = RateLimitConfig(sliding_window_seconds=60)
        mock_redis = AsyncMock(spec=aioredis.Redis)

        # Mock Redis returning inconsistent timestamps
        mock_redis.zcount.return_value = 50

        rate_limiter = RateLimiter(config=config, redis_client=mock_redis)

        # Should handle gracefully even with time sync issues
        result = await rate_limiter.check_user_rate_limit("time-sync-test-user")
        assert isinstance(result, RateLimitInfo)
