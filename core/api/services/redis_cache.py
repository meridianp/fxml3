"""
Redis caching service for FXML4 API performance optimization.
"""

import asyncio
import hashlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import redis

logger = logging.getLogger(__name__)


class RedisCacheService:
    """Redis caching service with async support for high-performance data caching."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        max_connections: int = 50,
    ):
        """
        Initialize Redis cache service.

        Args:
            host: Redis server host
            port: Redis server port
            db: Redis database number
            password: Redis password (optional)
            max_connections: Maximum connection pool size
        """
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self._client = None
        self._executor = ThreadPoolExecutor(max_workers=10)

        # Cache TTL settings (in seconds)
        self.ttl_settings = {
            "market_data": 30,  # 30 seconds for market data
            "signals": 60,  # 1 minute for signals
            "features": 300,  # 5 minutes for features
            "symbols": 3600,  # 1 hour for symbols list
            "backtest": 7200,  # 2 hours for backtest results
            "default": 300,  # 5 minutes default
        }

    def _get_client(self) -> redis.Redis:
        """Get Redis client (lazy initialization)."""
        if self._client is None:
            self._client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True,
                max_connections=50,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
            logger.info(f"Connected to Redis at {self.host}:{self.port}")
        return self._client

    def _generate_cache_key(self, prefix: str, params: Dict[str, Any]) -> str:
        """
        Generate consistent cache key from prefix and parameters.

        Args:
            prefix: Cache key prefix (e.g., 'market_data', 'signals')
            params: Parameters to include in cache key

        Returns:
            Cache key string
        """
        # Sort parameters for consistency
        param_str = json.dumps(params, sort_keys=True, default=str)
        param_hash = hashlib.md5(param_str.encode()).hexdigest()[:16]
        return f"fxml4:{prefix}:{param_hash}"

    async def get(self, prefix: str, params: Dict[str, Any]) -> Optional[Any]:
        """
        Get cached data asynchronously.

        Args:
            prefix: Cache key prefix
            params: Parameters for cache key generation

        Returns:
            Cached data or None if not found
        """
        try:
            cache_key = self._generate_cache_key(prefix, params)

            # Run Redis operation in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            cached_data = await loop.run_in_executor(
                self._executor, lambda: self._get_client().get(cache_key)
            )

            if cached_data:
                logger.debug(f"Cache HIT for {prefix}: {cache_key}")
                return json.loads(cached_data)
            else:
                logger.debug(f"Cache MISS for {prefix}: {cache_key}")
                return None

        except Exception as e:
            logger.warning(f"Cache GET error for {prefix}: {e}")
            return None

    async def set(
        self, prefix: str, params: Dict[str, Any], data: Any, ttl: Optional[int] = None
    ) -> bool:
        """
        Set cached data asynchronously.

        Args:
            prefix: Cache key prefix
            params: Parameters for cache key generation
            data: Data to cache
            ttl: Time to live in seconds (optional, uses default based on prefix)

        Returns:
            True if successful, False otherwise
        """
        try:
            cache_key = self._generate_cache_key(prefix, params)
            ttl = ttl or self.ttl_settings.get(prefix, self.ttl_settings["default"])

            # Serialize data
            serialized_data = json.dumps(data, default=str)

            # Run Redis operation in thread pool
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                self._executor,
                lambda: self._get_client().setex(cache_key, ttl, serialized_data),
            )

            if success:
                logger.debug(f"Cache SET for {prefix}: {cache_key} (TTL: {ttl}s)")
                return True
            else:
                logger.warning(f"Cache SET failed for {prefix}: {cache_key}")
                return False

        except Exception as e:
            logger.warning(f"Cache SET error for {prefix}: {e}")
            return False

    async def delete(self, prefix: str, params: Dict[str, Any]) -> bool:
        """
        Delete cached data asynchronously.

        Args:
            prefix: Cache key prefix
            params: Parameters for cache key generation

        Returns:
            True if successful, False otherwise
        """
        try:
            cache_key = self._generate_cache_key(prefix, params)

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor, lambda: self._get_client().delete(cache_key)
            )

            logger.debug(f"Cache DELETE for {prefix}: {cache_key}")
            return result > 0

        except Exception as e:
            logger.warning(f"Cache DELETE error for {prefix}: {e}")
            return False

    async def flush_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a pattern.

        Args:
            pattern: Redis key pattern (e.g., 'fxml4:market_data:*')

        Returns:
            Number of keys deleted
        """
        try:
            loop = asyncio.get_event_loop()
            client = self._get_client()

            # Get all matching keys
            keys = await loop.run_in_executor(
                self._executor, lambda: client.keys(pattern)
            )

            if keys:
                # Delete all keys
                deleted = await loop.run_in_executor(
                    self._executor, lambda: client.delete(*keys)
                )
                logger.info(f"Deleted {deleted} cache keys matching pattern: {pattern}")
                return deleted
            else:
                return 0

        except Exception as e:
            logger.error(f"Cache flush pattern error for {pattern}: {e}")
            return 0

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        try:
            loop = asyncio.get_event_loop()
            client = self._get_client()

            info = await loop.run_in_executor(
                self._executor, lambda: client.info("memory")
            )

            fxml4_keys = await loop.run_in_executor(
                self._executor, lambda: len(client.keys("fxml4:*"))
            )

            return {
                "memory_used": info.get("used_memory_human", "Unknown"),
                "fxml4_keys": fxml4_keys,
                "connected_clients": info.get("connected_clients", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(info),
            }

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"error": str(e)}

    def _calculate_hit_rate(self, info: Dict) -> float:
        """Calculate cache hit rate percentage."""
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total = hits + misses
        return (hits / total * 100) if total > 0 else 0.0

    async def health_check(self) -> bool:
        """
        Check if Redis is healthy and responsive.

        Returns:
            True if healthy, False otherwise
        """
        try:
            loop = asyncio.get_event_loop()
            pong = await loop.run_in_executor(
                self._executor, lambda: self._get_client().ping()
            )
            return pong is True

        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False

    async def close(self):
        """Close Redis connection and thread pool."""
        try:
            if self._client:
                await asyncio.get_event_loop().run_in_executor(
                    self._executor, self._client.close
                )
                self._client = None

            self._executor.shutdown(wait=True)
            logger.info("Redis cache service closed")

        except Exception as e:
            logger.error(f"Error closing Redis cache service: {e}")


# Global instance
redis_cache_service = RedisCacheService()
