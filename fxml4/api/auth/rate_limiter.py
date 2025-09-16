"""
Production-ready rate limiting system for FXML4 trading platform.

This module provides comprehensive rate limiting functionality including:
- User-based rate limiting (100 requests/minute per user)
- IP-based rate limiting (1000 requests/minute per IP)
- DDoS protection with burst detection
- Redis-based sliding window implementation
- Integration with JWT authentication
- Middleware integration for FastAPI
- Rate limit status and reset information
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis
from fastapi import HTTPException, Request, Response

from fxml4.config import get_config

# Configure logging
logger = logging.getLogger(__name__)

# Configuration
config = get_config()


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting system."""

    # Rate limits
    user_requests_per_minute: int = 100
    ip_requests_per_minute: int = 1000

    # Burst and DDoS protection
    burst_multiplier: float = 1.5  # Allow 1.5x burst capacity
    ddos_threshold_multiplier: float = 5.0  # DDoS if 5x normal rate

    # Sliding window configuration
    sliding_window_seconds: int = 60
    cleanup_interval_seconds: int = 300  # Clean up old entries every 5 minutes

    # Redis configuration
    redis_key_prefix: str = "rate_limit:"
    redis_expiry_seconds: int = 3600  # Keep keys for 1 hour

    # Whitelisted endpoints (no rate limiting)
    whitelisted_endpoints: List[str] = None

    def __post_init__(self):
        """Validate configuration values."""
        if self.user_requests_per_minute <= 0:
            raise ValueError("user_requests_per_minute must be positive")

        if self.ip_requests_per_minute <= 0:
            raise ValueError("ip_requests_per_minute must be positive")

        if self.burst_multiplier < 1.0:
            raise ValueError("burst_multiplier must be >= 1.0")

        if self.sliding_window_seconds <= 0:
            raise ValueError("sliding_window_seconds must be positive")

        # Set default whitelisted endpoints
        if self.whitelisted_endpoints is None:
            self.whitelisted_endpoints = [
                "/health",
                "/metrics",
                "/docs",
                "/openapi.json",
                "/favicon.ico",
            ]


@dataclass
class RateLimitInfo:
    """Information about current rate limit status."""

    limit: int
    remaining: int
    reset_time: datetime
    retry_after: int

    def is_exceeded(self) -> bool:
        """Check if rate limit is exceeded."""
        return self.remaining <= 0

    def to_headers(self) -> Dict[str, str]:
        """Convert to HTTP headers."""
        return {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(0, self.remaining)),
            "X-RateLimit-Reset": str(int(self.reset_time.timestamp())),
            "Retry-After": str(self.retry_after),
        }


class RateLimitExceededError(HTTPException):
    """Exception raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str,
        limit_type: str,
        limit: int,
        retry_after: int,
        headers: Optional[Dict[str, str]] = None,
    ):
        super().__init__(status_code=429, detail=message, headers=headers)
        self.message = message
        self.limit_type = limit_type
        self.limit = limit
        self.retry_after = retry_after


class RateLimiter:
    """Redis-based rate limiter with sliding window implementation."""

    def __init__(
        self,
        config: Optional[RateLimitConfig] = None,
        redis_client: Optional[aioredis.Redis] = None,
    ):
        """Initialize rate limiter."""
        self.config = config or RateLimitConfig()

        # Initialize Redis client
        if redis_client:
            self.redis = redis_client
        else:
            # Use environment variable or default Redis URL
            import os

            redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
            self.redis = aioredis.from_url(redis_url, decode_responses=True)

        # Background cleanup task (only start if not in test mode)
        self._cleanup_task = None
        if not self._is_test_mode():
            self._start_cleanup_task()

    def _is_test_mode(self) -> bool:
        """Check if running in test mode."""
        import os

        return os.environ.get("PYTEST_CURRENT_TEST") is not None

    def _start_cleanup_task(self):
        """Start background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def _periodic_cleanup(self):
        """Periodically clean up old entries."""
        while True:
            try:
                await asyncio.sleep(self.config.cleanup_interval_seconds)
                await self.cleanup_old_entries()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in rate limiter cleanup: {e}")

    def _generate_user_key(self, user_id: str) -> str:
        """Generate Redis key for user rate limiting."""
        return f"{self.config.redis_key_prefix}user:{user_id}"

    def _generate_ip_key(self, ip_address: str) -> str:
        """Generate Redis key for IP rate limiting."""
        return f"{self.config.redis_key_prefix}ip:{ip_address}"

    async def check_user_rate_limit(
        self, user_id: str, bypass_limit: bool = False
    ) -> RateLimitInfo:
        """
        Check user-based rate limit.

        Args:
            user_id: User identifier
            bypass_limit: Whether to bypass rate limiting (for privileged users)

        Returns:
            RateLimitInfo with current limit status
        """
        if bypass_limit:
            return RateLimitInfo(
                limit=self.config.user_requests_per_minute,
                remaining=self.config.user_requests_per_minute,
                reset_time=datetime.now(timezone.utc) + timedelta(minutes=1),
                retry_after=0,
            )

        try:
            current_time = time.time()
            window_start = current_time - self.config.sliding_window_seconds
            key = self._generate_user_key(user_id)

            # Use Redis pipeline for atomic operations
            pipe = self.redis.pipeline()

            # Remove old entries
            pipe.zremrangebyscore(key, 0, window_start)

            # Count current requests
            pipe.zcount(key, window_start, current_time)

            # Add current request
            pipe.zadd(key, {str(current_time): current_time})

            # Set expiry
            pipe.expire(key, self.config.redis_expiry_seconds)

            # Execute pipeline
            results = await pipe.execute()
            current_count = results[1] + 1  # +1 for the current request

            # Calculate limits with burst protection
            base_limit = self.config.user_requests_per_minute
            burst_limit = int(base_limit * self.config.burst_multiplier)

            # Determine remaining requests
            remaining = max(0, burst_limit - current_count)

            # Calculate reset time
            reset_time = datetime.now(timezone.utc) + timedelta(
                seconds=self.config.sliding_window_seconds
            )

            return RateLimitInfo(
                limit=base_limit,
                remaining=remaining,
                reset_time=reset_time,
                retry_after=self.config.sliding_window_seconds if remaining == 0 else 0,
            )

        except Exception as e:
            logger.error(f"Error checking user rate limit for {user_id}: {e}")

            # Fail-open: allow request but with conservative limits
            return RateLimitInfo(
                limit=self.config.user_requests_per_minute,
                remaining=self.config.user_requests_per_minute // 2,
                reset_time=datetime.now(timezone.utc) + timedelta(minutes=1),
                retry_after=0,
            )

    async def check_ip_rate_limit(self, ip_address: str) -> RateLimitInfo:
        """
        Check IP-based rate limit with DDoS protection.

        Args:
            ip_address: Client IP address

        Returns:
            RateLimitInfo with current limit status
        """
        if not ip_address:
            # Handle missing IP address gracefully
            return RateLimitInfo(
                limit=self.config.ip_requests_per_minute,
                remaining=self.config.ip_requests_per_minute // 2,
                reset_time=datetime.now(timezone.utc) + timedelta(minutes=1),
                retry_after=0,
            )

        try:
            current_time = time.time()
            window_start = current_time - self.config.sliding_window_seconds
            key = self._generate_ip_key(ip_address)

            # Use Redis pipeline for atomic operations
            pipe = self.redis.pipeline()

            # Remove old entries
            pipe.zremrangebyscore(key, 0, window_start)

            # Count current requests
            pipe.zcount(key, window_start, current_time)

            # Add current request
            pipe.zadd(key, {str(current_time): current_time})

            # Set expiry
            pipe.expire(key, self.config.redis_expiry_seconds)

            # Execute pipeline
            results = await pipe.execute()
            current_count = results[1] + 1  # +1 for the current request

            # Calculate limits and DDoS detection
            base_limit = self.config.ip_requests_per_minute
            ddos_threshold = int(base_limit * self.config.ddos_threshold_multiplier)

            # Check for potential DDoS
            is_ddos = current_count >= ddos_threshold
            retry_after = self.config.sliding_window_seconds

            if is_ddos:
                # Extended retry for DDoS protection
                retry_after = self.config.sliding_window_seconds * 2
                logger.warning(
                    f"Potential DDoS detected from IP {ip_address}: {current_count} requests"
                )

            # Calculate remaining requests
            remaining = max(0, base_limit - current_count)

            # Calculate reset time
            reset_time = datetime.now(timezone.utc) + timedelta(seconds=retry_after)

            return RateLimitInfo(
                limit=base_limit,
                remaining=remaining,
                reset_time=reset_time,
                retry_after=retry_after if remaining == 0 else 0,
            )

        except Exception as e:
            logger.error(f"Error checking IP rate limit for {ip_address}: {e}")

            # Fail-open: allow request but with conservative limits
            return RateLimitInfo(
                limit=self.config.ip_requests_per_minute,
                remaining=self.config.ip_requests_per_minute // 2,
                reset_time=datetime.now(timezone.utc) + timedelta(minutes=1),
                retry_after=0,
            )

    async def cleanup_old_entries(self):
        """Clean up old entries from all rate limit keys."""
        try:
            current_time = time.time()
            cutoff_time = current_time - self.config.redis_expiry_seconds

            # Use Lua script for efficient cleanup
            lua_script = """
            local keys = redis.call('KEYS', ARGV[1])
            local cutoff = tonumber(ARGV[2])
            local cleaned = 0

            for i = 1, #keys do
                local removed = redis.call('ZREMRANGEBYSCORE', keys[i], 0, cutoff)
                cleaned = cleaned + removed

                -- Remove empty keys
                if redis.call('ZCARD', keys[i]) == 0 then
                    redis.call('DEL', keys[i])
                end
            end

            return cleaned
            """

            pattern = f"{self.config.redis_key_prefix}*"
            cleaned = await self.redis.eval(lua_script, 0, pattern, cutoff_time)

            if cleaned > 0:
                logger.debug(f"Cleaned up {cleaned} old rate limit entries")

        except Exception as e:
            logger.error(f"Error during rate limit cleanup: {e}")

    async def reset_user_rate_limit(self, user_id: str):
        """Reset rate limit for a specific user (admin function)."""
        try:
            key = self._generate_user_key(user_id)
            await self.redis.delete(key)
            logger.info(f"Reset rate limit for user {user_id}")
        except Exception as e:
            logger.error(f"Error resetting rate limit for user {user_id}: {e}")

    async def reset_ip_rate_limit(self, ip_address: str):
        """Reset rate limit for a specific IP address (admin function)."""
        try:
            key = self._generate_ip_key(ip_address)
            await self.redis.delete(key)
            logger.info(f"Reset rate limit for IP {ip_address}")
        except Exception as e:
            logger.error(f"Error resetting rate limit for IP {ip_address}: {e}")

    async def close(self):
        """Clean up resources and stop background tasks."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        if hasattr(self.redis, "close"):
            await self.redis.close()

    async def get_rate_limit_stats(self) -> Dict[str, Any]:
        """Get overall rate limiting statistics."""
        try:
            pattern = f"{self.config.redis_key_prefix}*"
            keys = await self.redis.keys(pattern)

            user_keys = [k for k in keys if ":user:" in k]
            ip_keys = [k for k in keys if ":ip:" in k]

            return {
                "total_tracked_users": len(user_keys),
                "total_tracked_ips": len(ip_keys),
                "config": {
                    "user_limit": self.config.user_requests_per_minute,
                    "ip_limit": self.config.ip_requests_per_minute,
                    "sliding_window_seconds": self.config.sliding_window_seconds,
                    "burst_multiplier": self.config.burst_multiplier,
                    "ddos_threshold_multiplier": self.config.ddos_threshold_multiplier,
                },
            }

        except Exception as e:
            logger.error(f"Error getting rate limit stats: {e}")
            return {"error": str(e)}


class RateLimitMiddleware:
    """FastAPI middleware for rate limiting."""

    def __init__(self, rate_limiter: RateLimiter):
        """Initialize middleware with rate limiter."""
        self.rate_limiter = rate_limiter

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded headers (behind proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct client IP
        return request.client.host if request.client else "unknown"

    def _is_whitelisted(self, request: Request) -> bool:
        """Check if request endpoint is whitelisted."""
        path = request.url.path
        return any(
            path.startswith(whitelist)
            for whitelist in self.rate_limiter.config.whitelisted_endpoints
        )

    def _is_privileged_user(self, user) -> bool:
        """Check if user has privileges to bypass rate limits."""
        if not user or not hasattr(user, "roles"):
            return False

        privileged_roles = {"admin", "system", "service"}
        user_roles = {
            role.name.lower() if hasattr(role, "name") else str(role).lower()
            for role in user.roles
        }

        return bool(privileged_roles.intersection(user_roles))

    async def process_request(self, request: Request, call_next, user=None):
        """Process request through rate limiting."""

        # Skip rate limiting for whitelisted endpoints
        if self._is_whitelisted(request):
            response = await call_next(request)
            return response

        # Get client IP
        client_ip = self._get_client_ip(request)

        # Check rate limits
        rate_limit_infos = []

        # Check IP rate limit (always applied)
        ip_limit_info = await self.rate_limiter.check_ip_rate_limit(client_ip)
        rate_limit_infos.append(("ip", ip_limit_info))

        # Check user rate limit (if authenticated)
        if user:
            bypass_limit = self._is_privileged_user(user)
            user_limit_info = await self.rate_limiter.check_user_rate_limit(
                user.id, bypass_limit=bypass_limit
            )
            rate_limit_infos.append(("user", user_limit_info))

        # Check if any rate limit is exceeded
        for limit_type, limit_info in rate_limit_infos:
            if limit_info.is_exceeded():
                headers = limit_info.to_headers()
                raise RateLimitExceededError(
                    message=f"Rate limit exceeded for {limit_type}",
                    limit_type=limit_type,
                    limit=limit_info.limit,
                    retry_after=limit_info.retry_after,
                    headers=headers,
                )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        if rate_limit_infos:
            # Use the most restrictive limit for headers (typically user limit)
            primary_limit_info = rate_limit_infos[-1][
                1
            ]  # Last one (user if available, otherwise IP)
            headers = primary_limit_info.to_headers()

            for key, value in headers.items():
                response.headers[key] = value

        return response


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create global rate limiter instance."""
    global _rate_limiter

    if _rate_limiter is None:
        _rate_limiter = RateLimiter()

    return _rate_limiter


async def check_rate_limit(request: Request, user=None) -> None:
    """
    Convenience function to check rate limits in route handlers.

    Usage:
        @app.post("/api/trading/orders")
        async def create_order(request: Request, user: User = Depends(get_current_user)):
            await check_rate_limit(request, user)
            # ... rest of handler
    """
    rate_limiter = get_rate_limiter()
    middleware = RateLimitMiddleware(rate_limiter)

    # Dummy call_next function
    async def dummy_call_next(req):
        return Response()

    # This will raise RateLimitExceededError if limit is exceeded
    await middleware.process_request(request, dummy_call_next, user)
